"""Geography/specialty packs and the RunContext they build. No network.

Packs turn "Guntur" and "dermatology" from hardcoded strings scattered across six modules into
data, so a new market is a config change rather than a code change. The tests that matter most
are the ones proving the *shipped* packs are internally consistent and that a missing context
still reproduces today's Guntur behaviour byte-for-byte — otherwise de-hardcoding silently
changes results for the existing snapshot.
"""
import json
from pathlib import Path

import pytest

from modules import packs

PACKS_DIR = Path(__file__).resolve().parent.parent / "packs"


# --- loading ------------------------------------------------------------------

def test_ships_guntur_and_dermatology_packs():
    assert (PACKS_DIR / "geography" / "guntur-ap.json").exists()
    assert (PACKS_DIR / "specialty" / "dermatology.json").exists()


def test_load_builds_a_runcontext_with_both_packs():
    ctx = packs.load("guntur-ap", "dermatology")
    assert ctx.city == "Guntur"
    assert ctx.state == "Andhra Pradesh"
    assert ctx.specialist_noun == "dermatologist"
    assert ctx.gl == "in" and ctx.hl == "en"


def test_unknown_pack_names_fail_loudly():
    with pytest.raises(packs.PackNotFound):
        packs.load("atlantis", "dermatology")
    with pytest.raises(packs.PackNotFound):
        packs.load("guntur-ap", "astrology")


def test_available_packs_are_discoverable_for_the_admin_form():
    geos = packs.available_geographies()
    specs = packs.available_specialties()
    assert "guntur-ap" in geos and "dermatology" in specs


# --- validation ---------------------------------------------------------------

def test_validator_rejects_a_specialty_with_a_single_phrasing():
    """'Ask each condition several ways' is structural: one phrasing under-samples demand."""
    bad = {"id": "x", "name": "X", "specialist_noun": "doc",
           "conditions": [{"id": "c", "phrasings": ["only one"]}]}
    with pytest.raises(packs.InvalidPack) as e:
        packs.validate_specialty(bad)
    assert "phrasings" in str(e.value)


def test_validator_rejects_geography_without_coordinates():
    with pytest.raises(packs.InvalidPack):
        packs.validate_geography({"id": "g", "city": "G", "state": "S"})


def test_shipped_packs_pass_their_own_validators():
    packs.validate_geography(json.loads((PACKS_DIR / "geography" / "guntur-ap.json").read_text(encoding="utf-8")))
    packs.validate_specialty(json.loads((PACKS_DIR / "specialty" / "dermatology.json").read_text(encoding="utf-8")))


def test_every_shipped_condition_has_at_least_two_phrasings():
    spec = json.loads((PACKS_DIR / "specialty" / "dermatology.json").read_text(encoding="utf-8"))
    for cond in spec["conditions"]:
        assert len(cond["phrasings"]) >= 2, f"{cond['id']} under-samples its condition"


def test_shipped_threshold_carries_its_evidence():
    """A number without a rationale is intuition; the brief asks for defensible thresholds."""
    ctx = packs.load("guntur-ap", "dermatology")
    assert ctx.default_query_threshold == 100
    assert len(ctx.spec.get("threshold_rationale", "")) > 200
    ev = ctx.spec["threshold_evidence"]
    assert ev["clinics_total"] == 34
    assert ev["queries_to_100pct_discovery"] == 24
    assert ev["phrasing_floor"] == 88


# --- context behaviour --------------------------------------------------------

def test_context_exposes_the_stopword_set_used_for_clinic_name_matching():
    ctx = packs.load("guntur-ap", "dermatology")
    toks = ctx.name_stopwords()
    assert "guntur" in toks          # city never distinguishes one local clinic from another
    assert "dermatologist" in toks   # nor does the specialty
    assert "skin" in toks


def test_context_reports_that_the_city_must_appear_in_queries():
    """Google ignores uule, so the city in the query text is the only geo control."""
    ctx = packs.load("guntur-ap", "dermatology")
    assert ctx.requires_city_in_query is True


def test_query_threshold_can_be_overridden_per_run():
    ctx = packs.load("guntur-ap", "dermatology", query_threshold=60)
    assert ctx.query_threshold == 60
    assert ctx.default_query_threshold == 100  # the pack default is still visible


def test_threshold_defaults_to_the_pack_when_not_overridden():
    assert packs.load("guntur-ap", "dermatology").query_threshold == 100


def test_maps_search_suffix_is_the_city_not_a_hardcoded_literal():
    ctx = packs.load("guntur-ap", "dermatology")
    assert ctx.maps_search_suffix == "Guntur"


def test_subject_type_defaults_to_both_and_is_validated():
    assert packs.load("guntur-ap", "dermatology").subject_type == "both"
    with pytest.raises(packs.InvalidPack):
        packs.load("guntur-ap", "dermatology", subject_type="dentists")


# --- subject-type classification ----------------------------------------------

@pytest.mark.parametrize("name,category,expected", [
    ("Sri Ramakrishna Multi-speciality Hospital", "Hospital", "hospital"),
    ("Skin Perfect Clinic", "Skin care clinic", "clinic"),
    ("Dr Sowmya Skin Clinic", "Dermatologist", "clinic"),
    ("Guntur Medical College", "", "hospital"),
])
def test_subject_class_uses_category_first_then_name_tokens(name, category, expected):
    ctx = packs.load("guntur-ap", "dermatology")
    assert ctx.classify_subject(name, category) == expected


def test_unclassifiable_subjects_are_marked_ambiguous_not_silently_bucketed():
    """A wrong bucket would average a hospital against solo practitioners; say 'unknown'.

    'Dr. Sneha Kovi' is a real example from the June snapshot: a practitioner name with no
    facility word at all, and no Maps category to fall back on.
    """
    ctx = packs.load("guntur-ap", "dermatology")
    assert ctx.classify_subject("Dr. Sneha Kovi", "") == "ambiguous"


def test_a_facility_word_in_the_name_is_enough_to_classify_a_clinic():
    ctx = packs.load("guntur-ap", "dermatology")
    assert ctx.classify_subject("Aesthetica Skin Studio", "") == "clinic"
    assert ctx.classify_subject("Leelavathi Advanced Skin & Laser Centre", "") == "clinic"


def test_subject_filter_keeps_ambiguous_rows_visible_in_both_mode():
    ctx = packs.load("guntur-ap", "dermatology", subject_type="both")
    assert ctx.includes_subject("clinic") and ctx.includes_subject("hospital")
    assert ctx.includes_subject("ambiguous")


def test_subject_filter_excludes_the_other_league_when_narrowed():
    ctx = packs.load("guntur-ap", "dermatology", subject_type="individual")
    assert ctx.includes_subject("clinic")
    assert not ctx.includes_subject("hospital")
    assert ctx.includes_subject("ambiguous"), "ambiguous must stay visible, not vanish"


# --- legacy equivalence: the guard against silently changing snapshot #1 -------

def test_legacy_context_reproduces_todays_hardcoded_guntur_behaviour():
    ctx = packs.legacy_context()
    assert ctx.city == "Guntur"
    assert ctx.specialist_noun == "dermatologist"
    assert ctx.maps_search_suffix == "Guntur"
    assert "guntur" in ctx.name_stopwords()


def test_legacy_stopwords_match_the_web_collector_set_exactly():
    """web_collector._TOKEN_STOPWORDS is what the June snapshot was matched with; drifting
    from it would re-map blocks to different clinics and change historical scores."""
    from modules.web_collector import _TOKEN_STOPWORDS
    assert packs.legacy_context().name_stopwords() == set(_TOKEN_STOPWORDS)
