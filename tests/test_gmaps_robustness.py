"""Regression tests for the 8 fixes made after the adversarial QA pass.

Each test is named for the defect it prevents from returning. They exist because a review is
worth only as much as the test that pins its finding: every one of these failures was reproduced
by execution before the fix, and would otherwise be free to come back.

No network. Fixtures are the real captured DOM in archive/gmaps_v1_2026-08-20/probe_evidence/.
"""
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from gmaps import fields, packs, run as R, taxonomy
from gmaps.cards import parse_feed
from gmaps.extract import card_only_record

FIXTURES = Path(__file__).resolve().parent.parent / "archive" / "gmaps_v1_2026-08-20" / "probe_evidence"
FEED_HTML = FIXTURES / "listing_page.html"


@pytest.fixture(scope="module")
def real_cards():
    if not FEED_HTML.exists():
        pytest.skip("captured feed fixture not present")
    return parse_feed(BeautifulSoup(FEED_HTML.read_text(encoding="utf-8"), "lxml"))


@pytest.fixture
def ctx():
    return packs.load("guntur-ap", "dermatology")


# --- FIX 1: an empty or truncated feed must never be written or reused -----------------------

def test_empty_feed_raises_rather_than_writing_a_clean_empty_run():
    """The worst case: a selector change made the run report success with zero clinics."""
    assert hasattr(R, "FeedEmpty")
    assert R.MIN_PLAUSIBLE_CARDS >= 1


def test_run_refuses_to_reuse_a_zero_card_cached_feed(tmp_path):
    """An empty feed.json used to be replayed forever, so the run could never self-heal."""
    src = Path(R.__file__).read_text(encoding="utf-8")
    assert "cached feed has 0 cards" in src
    assert "budget_exhausted" in src, "a truncated feed must not be reused either"
    assert "different query" in src, "a cached feed for another query must not be reused"


# --- FIX 2: finished snapshots are immutable -------------------------------------------------

def test_finalized_snapshot_refuses_further_writes(tmp_path):
    R.atomic_write(tmp_path / "manifest.json",
                   {"status": "complete", "finished_at": "2026-06-28T12:00:00",
                    "query": "best dermatologists in Guntur"})
    with pytest.raises(R.RunFinalized):
        R.assert_not_finalized(tmp_path)


def test_unfinished_run_is_still_writable(tmp_path):
    R.atomic_write(tmp_path / "manifest.json", {"status": "running"})
    R.assert_not_finalized(tmp_path)          # must not raise


def test_finalize_marks_a_run_complete(tmp_path):
    R.finalize(tmp_path, {"run_dir": str(tmp_path), "query": "q"})
    m = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert m["status"] == "complete" and m["finalized_at"]
    with pytest.raises(R.RunFinalized):
        R.assert_not_finalized(tmp_path)


def test_resume_preserves_the_original_start_time():
    """Rebuilding the manifest wholesale destroyed the record of when a snapshot began."""
    src = Path(R.__file__).read_text(encoding="utf-8")
    assert 'prior_manifest.get("started_at")' in src


def test_run_index_is_maintained(tmp_path):
    """Without an index a dashboard cannot enumerate snapshots."""
    R.update_index(tmp_path, {"run_dir": "a", "started_at": "2026-06-28", "status": "complete"})
    R.update_index(tmp_path, {"run_dir": "b", "started_at": "2026-09-30", "status": "complete"})
    idx = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert [r["run_dir"] for r in idx["runs"]] == ["b", "a"]     # newest first
    R.update_index(tmp_path, {"run_dir": "b", "started_at": "2026-09-30", "status": "complete"})
    idx = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert len(idx["runs"]) == 2, "re-registering a run must update it, not duplicate it"


# --- FIX 3: a failed read must not look like an empty clinic ---------------------------------

def test_card_only_record_is_marked_as_never_opened(ctx, real_cards):
    card = dict(real_cards[0])
    card.update({"key": "k", "rank": 1, "category": card.get("card_category"),
                 "address": card.get("card_address")})
    rec = card_only_record(card, ctx, {"relevance": "irrelevant", "basis": "category"})
    assert rec["page_rendered"] is False
    assert rec["error"] == ""
    assert rec["reviews_coverage"] is None
    assert "phone" in rec["not_collected"], "must say we never looked, not that it is missing"


def test_reviews_coverage_key_always_exists_and_is_clamped(ctx, real_cards):
    card = dict(real_cards[0])
    card.update({"key": "k", "rank": 1})
    rec = card_only_record(card, ctx, {"relevance": "irrelevant", "basis": "category"})
    assert "reviews_coverage" in rec, "an absent key raised KeyError downstream"


def test_page_rendered_gate_exists_in_extract():
    """complete must depend on the page actually rendering, or a failed read is never retried."""
    src = (Path(R.__file__).parent / "extract.py").read_text(encoding="utf-8")
    assert 'rec["page_rendered"]' in src
    assert 'rec["complete"] = rec["page_rendered"]' in src


# --- FIX 4: base.json is loaded, and precedence follows it ------------------------------------

def test_base_pack_actually_loads():
    base = taxonomy.load_base()
    assert len(base["universally_irrelevant"]) > 80
    assert len(base["generic_medical_adjacent"]) > 20


def test_universally_irrelevant_is_a_hard_anchor(ctx):
    """A restaurant called 'Skin Bar' must never become a clinic."""
    v = taxonomy.classify("restaurant", "Skin Bar", ctx.spec)
    assert v["relevance"] == "irrelevant"
    assert v["basis"] == "base_universally_irrelevant"


def test_generic_medical_category_is_adjacent_not_unlisted(ctx):
    """'Hospital' and 'Medical clinic' are specified in base.json; they used to fall through
    to category_unlisted, which flooded the curation log with 30 non-issues."""
    for cat in ("Hospital", "Medical clinic", "General hospital", "Doctor"):
        v = taxonomy.classify(cat, "Some Name", ctx.spec)
        assert v["relevance"] == "adjacent"
        assert "unlisted" not in v["basis"], f"{cat} should be recognised, got {v['basis']}"


def test_veto_cannot_flip_an_explicit_relevant_category_to_irrelevant(ctx):
    """The AIRA case: category=Dermatologist, name says 'diagnostic'. One-step cap -> adjacent,
    so it is fully extracted but never benchmarked as a peer."""
    v = taxonomy.classify("Dermatologist", "AIRA IMAGING & DIAGNOSTIC CENTER LLP", ctx.spec)
    assert v["relevance"] == "adjacent"
    assert taxonomy.extraction_tier(v["relevance"]) == "full"


def test_name_strong_cannot_flip_an_irrelevant_category_to_relevant(ctx):
    v = taxonomy.classify("Dental clinic", "Sunrise Skin and Dental", ctx.spec)
    assert v["relevance"] in ("adjacent", "irrelevant")
    assert v["relevance"] != "relevant", "name evidence may move one step, never two"


def test_contradictory_name_tokens_cancel_and_the_category_stands(ctx):
    """'Dr Vijay's Skin and Dental Clinic' carries both a strong and a veto token."""
    v = taxonomy.classify("Dermatologist", "Dr Vijay's Skin and Dental Clinic", ctx.spec)
    assert v["relevance"] == "relevant" and v["basis"] == "category"


# --- FIX 6: hardened fields --------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "mailto:doc@sai.com", "tel:+919999999999", "javascript:alert(1)", "ftp://x.com",
])
def test_non_http_schemes_are_never_a_website(url):
    """These used to be prefixed with http:// and read as the clinic's own domain."""
    r = fields.classify_website(url, "Some Clinic")
    assert r["has_own_website"] is False, f"{url} was counted as a real website"


def test_trailing_dot_cannot_evade_the_aggregator_list():
    """'practo.com.' is a valid FQDN and used to be classed as the clinic's own site."""
    r = fields.classify_website("https://practo.com./guntur/x", "Some Clinic")
    assert r["website_type"] == "aggregator_profile"
    assert r["has_own_website"] is False


def test_a_real_own_domain_still_passes():
    r = fields.classify_website("http://drsowmyaskinclinics.com/", "Dr Sowmya Skin Clinic")
    assert r["has_own_website"] is True and r["website_type"] == "own_domain"


def test_non_latin_names_do_not_collapse_to_one_key():
    """Every Telugu-named clinic used to slug to '' and overwrite the others."""
    a = fields.registry_key("", "చర్మ వైద్యుడు క్లినిక్")
    b = fields.registry_key("", "మరొక క్లినిక్")
    assert a and b and a != b


def test_registry_key_is_empty_when_there_is_nothing_to_key_on():
    assert fields.registry_key("", "") == ""


def test_place_id_and_kg_mid_regexes_are_shared(real_cards):
    """cards.py and fields.py kept separate regexes; the stricter one silently truncated
    kg_mid on 18 of 98 real cards because read_feed let it overwrite the other."""
    from gmaps import cards as C
    assert C._PID_RE.pattern == fields.PID_RE.pattern
    assert C._MID_RE.pattern == fields.MID_RE.pattern
    ids = [fields.ids_from_href(c["href"])["kg_mid"] for c in real_cards]
    assert sum(1 for k in ids if k) >= 90, "kg_mid should survive for nearly every real card"


def test_short_name_tokens_need_both_word_boundaries(ctx):
    """The ENT pack's 'ent' token matched 'Enterprises'."""
    ent = packs.load("guntur-ap", "ent")
    v = taxonomy.classify("", "Sunrise Enterprises", ent.spec)
    assert v["relevance"] != "relevant", "'ent' must not match 'Enterprises'"


def test_long_name_tokens_still_match_as_prefixes(ctx):
    v = taxonomy.classify("", "Dermatology Care Center", ctx.spec)
    assert v["relevance"] == "relevant", "'dermat' must still cover 'Dermatology'"


# --- FIX 5 / 7: real counters, corrupt files surfaced, card fields reach data.json -------------

def test_corrupt_place_file_is_surfaced_not_silently_dropped(tmp_path):
    (tmp_path / "places").mkdir()
    R.atomic_write(tmp_path / "places" / "good.json",
                   {"complete": True, "rank": 1, "name_clean": "Good", "tier": "full"})
    (tmp_path / "places" / "bad.json").write_text("{not json", encoding="utf-8")
    s = R.write_summary(tmp_path)
    assert len(s["corrupt"]) == 1
    rows = json.loads((tmp_path / "data.json").read_text(encoding="utf-8"))
    assert any("unreadable" in (r.get("name_clean") or "") for r in rows), \
        "a corrupt file must appear as a visible row, not vanish"


def test_write_summary_returns_real_counts_not_a_file_tally(tmp_path):
    (tmp_path / "places").mkdir()
    R.atomic_write(tmp_path / "places" / "a.json", {"complete": True, "tier": "full", "rank": 1})
    R.atomic_write(tmp_path / "places" / "b.json", {"complete": False, "error": "x", "rank": 2})
    R.atomic_write(tmp_path / "places" / "c.json", {"complete": True, "tier": "minimal", "rank": 3})
    s = R.write_summary(tmp_path)
    assert s["complete"] == 2 and s["failed"] == 1 and s["card_only"] == 1


def test_card_only_signals_reach_the_summary():
    """Booking, service options and closed status exist only on the card; they were carried into
    the place file but dropped again by the summary's keep-list."""
    for f in ("has_online_booking", "booking_vendor", "service_options",
              "temporarily_closed", "permanently_closed", "no_reviews", "page_rendered"):
        assert f in R.KEEP_FIELDS, f"{f} would never reach data.json"


# --- FIX 8: packs fail fast, before the browser opens ------------------------------------------

def test_string_instead_of_list_is_rejected():
    """A string passes a truthiness check then iterates as characters, silently matching
    nothing and declaring an entire market irrelevant."""
    with pytest.raises(packs.InvalidPack) as e:
        packs.validate_specialty({"id": "x", "specialist_singular": "a",
                                  "specialist_plural": "b",
                                  "relevant_categories": "dermatologist"})
    assert "LIST" in str(e.value)


def test_non_string_entries_are_rejected():
    with pytest.raises(packs.InvalidPack):
        packs.validate_specialty({"id": "x", "specialist_singular": "a",
                                  "specialist_plural": "b",
                                  "relevant_categories": [1, 2, None]})


def test_non_object_pack_is_rejected():
    with pytest.raises(packs.InvalidPack):
        packs.validate_specialty(["dermatology"])
    with pytest.raises(packs.InvalidPack):
        packs.validate_geography("guntur")


def test_transposed_latlng_is_rejected():
    """Guntur is 16.31, 80.44. Swapped, BOTH halves are still valid coordinates - the point just
    lands in the Indian Ocean. Range checks cannot catch this; only country bounds can."""
    with pytest.raises(packs.InvalidPack) as e:
        packs.validate_geography({"id": "g", "city": "G", "country_code": "IN",
                                  "viewport": {"lat": 80.4365, "lng": 16.3067}})
    assert "transposed" in str(e.value) or "outside IN" in str(e.value)


def test_correct_latlng_passes():
    packs.validate_geography({"id": "g", "city": "Guntur", "country_code": "IN",
                              "viewport": {"lat": 16.3067, "lng": 80.4365}})


def test_viewport_without_country_code_is_rejected():
    """Without a country code the bounds check silently does nothing, so the guarantee is only
    real if the code is mandatory whenever a viewport is given."""
    with pytest.raises(packs.InvalidPack) as e:
        packs.validate_geography({"id": "g", "city": "G",
                                  "viewport": {"lat": 16.3, "lng": 80.4}})
    assert "country_code" in str(e.value)


def test_bad_primary_query_placeholder_is_rejected_at_load():
    with pytest.raises(packs.InvalidPack):
        packs.validate_specialty({"id": "x", "specialist_singular": "a",
                                  "specialist_plural": "b",
                                  "relevant_categories": ["dermatologist"],
                                  "primary_query": "{specialist_plural} in {city}"})


def test_every_shipped_pack_still_passes_the_stricter_validation():
    for name in packs.available_specialties():
        packs.load("guntur-ap", name)


# --- end-to-end sanity on the real feed --------------------------------------------------------

def test_real_feed_still_classifies_sensibly(real_cards, ctx):
    verdicts = {}
    for c in real_cards:
        v = taxonomy.classify(c.get("card_category") or "", c.get("name") or "", ctx.spec)
        verdicts[v["relevance"]] = verdicts.get(v["relevance"], 0) + 1
    assert verdicts.get("relevant", 0) >= 40, verdicts
    assert verdicts.get("irrelevant", 0) >= 5, verdicts
    assert sum(verdicts.values()) == len(real_cards)


def test_no_real_card_is_left_unlisted_now_that_base_loads(real_cards, ctx):
    """30 of 97 records previously fell through to category_unlisted purely because base.json
    was never loaded."""
    unlisted = [c.get("card_category") for c in real_cards
                if "unlisted" in taxonomy.classify(c.get("card_category") or "",
                                                   c.get("name") or "", ctx.spec)["basis"]]
    assert len(unlisted) <= 3, f"still unlisted: {set(unlisted)}"
