"""market_facets (the rail's filter counts) + the palette single source of truth."""

import json
import sys
from pathlib import Path

import pytest

from web import views

V3 = Path(__file__).resolve().parents[1] / "docs" / "redesign" / "v3"
sys.path.insert(0, str(V3 / "tools"))
import gen_tokens  # noqa: E402


def clinic(**over):
    base = {"visibility": 40, "verdict": "Solid online presence.",
            "web": {"has_own_site": False, "owned": 0, "borrowed": 0, "platforms": []},
            "sponsored": 0}
    base.update(over)
    return base


# ─────────────────────────────────────────────── presence_of
def test_own_site_beats_everything():
    assert views.presence_of(clinic(web={"has_own_site": True, "owned": 0,
                                         "borrowed": 5, "platforms": ["practo"]})) == "own"


def test_paid_placement_alone_still_counts_as_owned():
    assert views.presence_of(clinic(web={"has_own_site": False, "owned": 3,
                                         "borrowed": 0, "platforms": []})) == "own"


def test_directories_only_is_borrowed():
    assert views.presence_of(clinic(web={"has_own_site": False, "owned": 0,
                                         "borrowed": 2, "platforms": ["practo"]})) == "borrowed"


def test_platform_tag_with_no_borrowed_count_is_still_borrowed():
    assert views.presence_of(clinic(web={"has_own_site": False, "owned": 0,
                                         "borrowed": 0, "platforms": ["instagram"]})) == "borrowed"


def test_nothing_at_all_is_invisible():
    assert views.presence_of(clinic()) == "invisible"


def test_missing_web_block_does_not_crash():
    assert views.presence_of({"visibility": 10}) == "invisible"


# ─────────────────────────────────────────────── market_facets
def test_partition_facets_sum_to_the_clinic_count():
    clinics = [clinic(visibility=v) for v in (5, 34, 66, 90, 12)]
    out = views.market_facets(clinics)
    assert out["total"] == 5
    for facet in ("verdict", "presence", "band"):
        assert sum(r["count"] for r in out[facet]) == 5, facet


def test_ads_is_a_flag_count_not_a_partition():
    clinics = [clinic(sponsored=31), clinic(sponsored=0), clinic(sponsored=7)]
    assert views.market_facets(clinics)["ads"] == 2


def test_presence_rows_are_always_all_three_in_fixed_order():
    out = views.market_facets([clinic()])
    assert [r["key"] for r in out["presence"]] == ["own", "borrowed", "invisible"]


def test_band_rows_run_best_to_worst():
    out = views.market_facets([clinic()])
    assert [r["key"] for r in out["band"]] == ["clear", "steady", "caution", "alarm"]


def test_verdict_rows_sorted_by_count_desc_then_text():
    clinics = ([clinic(verdict="B")] * 3) + ([clinic(verdict="A")] * 3) + [clinic(verdict="C")]
    out = views.market_facets(clinics)
    assert [r["key"] for r in out["verdict"]] == ["A", "B", "C"]


def test_empty_input():
    out = views.market_facets([])
    assert out["total"] == 0 and out["ads"] == 0
    assert len(out["presence"]) == 3 and len(out["band"]) == 4


def test_band_counts_agree_with_visibility_bands():
    """The rail and the market view must never disagree about the same clinics."""
    clinics = [clinic(visibility=v) for v in (5, 13, 34, 40, 66, 88, 100)]
    facets = {r["key"]: r["count"] for r in views.market_facets(clinics)["band"]}
    bands = {b["key"]: b["count"] for b in views.visibility_bands(clinics)["bands"]}
    assert facets == bands


# ─────────────────────────────────────────────── palette single source of truth
@pytest.fixture(scope="module")
def palette():
    return gen_tokens.load_palette()


def test_every_leaf_emits_exactly_one_custom_property(palette):
    names = gen_tokens.css_names(palette)
    assert len(names) == len(set(names)), "duplicate custom-property name"
    css = gen_tokens.palette_css(palette)
    for name in names:
        assert f"  {name}: " in css


def test_naming_rule_is_path_joined_with_dashes(palette):
    assert "--jewel-clear-core" in gen_tokens.css_names(palette)
    assert "--sf-field" in gen_tokens.css_names(palette)


def test_doc_keys_are_not_emitted(palette):
    assert any(k.startswith("$") for k in palette), "fixture should carry doc keys"
    assert "--$comment" not in gen_tokens.palette_css(palette)
    assert "$comment" not in gen_tokens.palette_js(palette)


def test_js_object_round_trips_to_the_same_tree(palette):
    js = gen_tokens.palette_js(palette)
    body = js[js.index("Object.freeze(") + len("Object.freeze("):js.rindex(");")]
    parsed = json.loads(body)
    expected = {k: v for k, v in palette.items() if not k.startswith("$")}
    assert parsed == expected


def test_css_and_js_carry_identical_leaf_values(palette):
    """The whole point of the file: the two forms cannot drift."""
    css = gen_tokens.palette_css(palette)
    for path, value in gen_tokens._walk(palette):
        assert f"--{'-'.join(path)}: {value};" in css


def test_the_five_jewel_families_all_exist(palette):
    assert set(palette["jewel"]) == {"clear", "steady", "caution", "alarm", "index"}
    for family, voices in palette["jewel"].items():
        assert {"frame", "core", "anchor", "bloom"} <= set(voices), family


def test_band_keys_and_jewel_families_line_up():
    """A band with no jewel recipe would render an unstyled hero."""
    families = set(gen_tokens.load_palette()["jewel"])
    band_keys = {key for _, _, key, _ in views.BANDS}
    assert band_keys < families
    assert families - band_keys == {"index"}
