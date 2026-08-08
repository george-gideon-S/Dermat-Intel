"""serp_ownership + serp_page — the 1122-block corpus, aggregated for the UI."""

import pytest

from web import views


def block(**over):
    base = {"query": "best dermatologist in Guntur", "block_type": "organic",
            "platform": "clinic_site", "domain": "example.com", "position": 3,
            "mapped_key": "", "mapped_clinic": "", "is_own_site": False, "title": "t"}
    base.update(over)
    return base


# ─────────────────────────────────────────────── serp_ownership
def test_totals_account_for_every_row():
    rows = [block(), block(block_type="places"), block(block_type="sponsored_top")]
    out = views.serp_ownership(rows)
    assert out["totals"]["blocks"] == 3
    assert sum(out["totals"]["by_type"].values()) == 3


def test_mapped_plus_unmapped_equals_blocks():
    rows = [block(mapped_key="k1"), block(mapped_key=""), block(mapped_key="k2")]
    out = views.serp_ownership(rows)
    t = out["totals"]
    assert t["mapped"] == 2 and t["unmapped"] == 1
    assert t["mapped"] + t["unmapped"] == t["blocks"]


def test_domain_matrix_is_exact():
    rows = [
        block(domain="practo.com", platform="practo", block_type="organic"),
        block(domain="practo.com", platform="practo", block_type="organic"),
        block(domain="practo.com", platform="practo", block_type="places"),
        block(domain="skinperfect.in", platform="clinic_site", mapped_key="k1"),
    ]
    out = views.serp_ownership(rows)
    practo = next(d for d in out["domains"] if d["domain"] == "practo.com")
    assert practo["blocks"] == 3
    assert practo["by_type"]["organic"] == 2
    assert practo["by_type"]["places"] == 1
    assert practo["by_type"]["sponsored_top"] == 0


@pytest.mark.parametrize("platform,mapped,expected", [
    ("practo", "", "aggregator"),
    ("justdial", "", "aggregator"),
    ("skedoc", "", "aggregator"),
    ("instagram", "", "social"),
    ("facebook", "", "social"),
    ("clinic_site", "k1", "own_clinic"),
    ("practo", "k1", "own_clinic"),      # a mapping always wins over the platform
    ("clinic_site", "", "other"),        # a clinic site we could not map is out-of-market
    ("something_new", "", "other"),
])
def test_kind_classification(platform, mapped, expected):
    out = views.serp_ownership([block(platform=platform, mapped_key=mapped,
                                      domain=f"{platform}.com")])
    assert out["domains"][0]["kind"] == expected


def test_domains_sorted_by_blocks_desc_then_name():
    rows = ([block(domain="b.com")] * 2) + [block(domain="a.com")] + [block(domain="c.com")]
    out = views.serp_ownership(rows)
    assert [d["domain"] for d in out["domains"]] == ["b.com", "a.com", "c.com"]


def test_positions_summarised_per_domain():
    rows = [block(domain="x.com", position=p) for p in (9, 1, 5)]
    d = views.serp_ownership(rows)["domains"][0]
    assert d["best_position"] == 1
    assert d["median_position"] == 5.0


def test_missing_positions_do_not_crash_the_summary():
    rows = [block(domain="x.com", position=None), block(domain="x.com", position=None)]
    d = views.serp_ownership(rows)["domains"][0]
    assert d["best_position"] is None and d["median_position"] is None


def test_query_count_is_distinct_not_row_count():
    rows = [block(query="q1"), block(query="q1"), block(query="q2")]
    out = views.serp_ownership(rows)
    assert out["totals"]["queries"] == 2
    assert out["domains"][0]["queries"] == 2


def test_places_blocks_have_no_domain_and_group_under_their_platform():
    """Otherwise the local pack collapses into one nameless row."""
    out = views.serp_ownership([block(block_type="places", domain="", platform="places")])
    assert out["domains"][0]["domain"] == "(places)"


def test_local_share_splits_each_block_type():
    rows = [block(block_type="organic", mapped_key="k1"),
            block(block_type="organic", mapped_key=""),
            block(block_type="organic", mapped_key="")]
    share = views.serp_ownership(rows)["local_share"]["organic"]
    assert share == {"local": 1, "other": 2}


def test_every_block_type_is_present_even_at_zero():
    """The matrix always renders all five columns; absent types must not vanish."""
    out = views.serp_ownership([block()])
    assert list(out["totals"]["by_type"]) == views.BLOCK_ORDER
    assert list(out["domains"][0]["by_type"]) == views.BLOCK_ORDER


def test_empty_input_returns_a_zeroed_skeleton():
    out = views.serp_ownership([])
    assert out["totals"]["blocks"] == 0
    assert out["totals"]["mapped"] == 0
    assert out["domains"] == []
    assert set(out["local_share"]) == set(views.BLOCK_ORDER)


def test_domain_case_and_whitespace_are_normalised():
    rows = [block(domain="Practo.COM"), block(domain=" practo.com ")]
    out = views.serp_ownership(rows)
    assert len(out["domains"]) == 1 and out["domains"][0]["blocks"] == 2


# ─────────────────────────────────────────────── serp_page
def test_page_ordering_follows_the_eye_down_the_page():
    rows = [
        block(block_type="organic", position=1),
        block(block_type="ai_overview", position=1),
        block(block_type="places", position=1),
        block(block_type="sponsored_mid", position=1),
        block(block_type="sponsored_top", position=1),
    ]
    got = [b["type"] for b in views.serp_page(rows, "best dermatologist in Guntur")]
    assert got == ["sponsored_top", "places", "sponsored_mid", "organic", "ai_overview"]


def test_within_a_group_sorted_by_position():
    rows = [block(position=p) for p in (7, 2, 5)]
    got = [b["position"] for b in views.serp_page(rows, "best dermatologist in Guntur")]
    assert got == [2, 5, 7]


def test_blocks_without_a_position_sort_last_and_stay_stable():
    rows = [block(position=None, domain="first.com"),
            block(position=None, domain="second.com"),
            block(position=4, domain="ranked.com")]
    got = [b["domain"] for b in views.serp_page(rows, "best dermatologist in Guntur")]
    assert got == ["ranked.com", "first.com", "second.com"]


def test_only_the_requested_query_is_returned():
    rows = [block(query="q1"), block(query="q2")]
    assert len(views.serp_page(rows, "q1")) == 1


def test_unknown_query_returns_empty():
    assert views.serp_page([block()], "no such query") == []


def test_row_contract():
    row = views.serp_page([block(mapped_key="k1", mapped_clinic="Skin Perfect",
                                 is_own_site=True)], "best dermatologist in Guntur")[0]
    assert set(row) == {"type", "position", "domain", "platform", "title",
                        "mapped_key", "clinic", "is_own_site", "kind"}
    assert row["clinic"] == "Skin Perfect"
    assert row["is_own_site"] is True
    assert row["kind"] == "own_clinic"
