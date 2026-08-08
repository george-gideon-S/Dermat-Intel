"""Integration: the live payload actually carries what the v3 panels are authored against.

The unit suites prove each view is correct in isolation. This one proves the wiring —
a field that silently stops flowing out of `build_payload()` is invisible until a panel
renders blank, which is exactly the failure mode this catches.

Skips cleanly when the caches are absent (a fresh clone has no `.cache/*.json`).
"""

import pytest

from web import build_web, views

pytestmark = pytest.mark.usefixtures()


@pytest.fixture(scope="module")
def payload():
    p = build_web.build_payload()
    if not p.get("clinics"):
        pytest.skip("no scraped data in .cache/ — integration test needs the live corpus")
    return p


# ─────────────────────────────────────────────── per-clinic fields
V3_CLINIC_FIELDS = ["key", "pos_avg", "high_intent", "lat", "lng", "km_core",
                    "maps_score", "web_score", "sponsored"]


@pytest.mark.parametrize("field", V3_CLINIC_FIELDS)
def test_every_clinic_carries_the_new_field(payload, field):
    missing = [c["display_name"] for c in payload["clinics"] if field not in c]
    assert not missing, f"{field} missing on {len(missing)} clinics"


def test_keys_are_unique_across_clinics(payload):
    """The cross-filter bus addresses panels by clinic key; a collision would make two
    clinics highlight as one."""
    keys = [c["key"] for c in payload["clinics"]]
    assert len(keys) == len(set(keys))
    assert all(keys)


def test_coordinates_sit_inside_the_guntur_bounding_box(payload):
    for c in payload["clinics"]:
        if c["lat"] is None:
            continue
        assert 16.2 < c["lat"] < 16.4, c["display_name"]
        assert 80.3 < c["lng"] < 80.6, c["display_name"]


def test_km_core_agrees_with_the_coordinates(payload):
    for c in payload["clinics"]:
        if c["lat"] is None or c["km_core"] is None:
            continue
        assert c["km_core"] == pytest.approx(
            round(views.km_from_core(c["lat"], c["lng"]), 2), abs=0.01)


def test_the_blend_reconstructs_the_published_score(payload):
    """0.6*maps + 0.4*web is the documented blend; if it stops holding, the split-score
    panel would be showing two numbers that do not add up to the headline."""
    for c in payload["clinics"]:
        if c["maps_score"] is None or c["web_score"] is None:
            continue
        blended = round(0.6 * c["maps_score"] + 0.4 * c["web_score"])
        assert abs(blended - c["score"]) <= 1, c["display_name"]


def test_best_position_is_null_not_zero_when_never_ranked(payload):
    """Zero would render as 'position 0', which is better than #1 and a lie."""
    for c in payload["clinics"]:
        bp = c["web"].get("best_position")
        assert bp is None or bp >= 1, c["display_name"]


def test_visibility_rank_is_a_dense_permutation(payload):
    ranks = sorted(c["visibility_rank"] for c in payload["clinics"])
    assert ranks == list(range(1, len(payload["clinics"]) + 1))


# ─────────────────────────────────────────────── plan
def test_every_clinic_has_a_plan(payload):
    for c in payload["clinics"]:
        plan = c["plan"]
        assert plan["now"]["rank"] == c["visibility_rank"], c["display_name"]
        assert plan["now"]["vis"] == c["visibility"], c["display_name"]


def test_plan_projections_never_worsen_rank(payload):
    for c in payload["clinics"]:
        plan = c["plan"]
        for step in plan["steps"]:
            assert step["rank_after"] <= plan["now"]["rank"], c["display_name"]
        assert plan["compound"]["all"]["rank"] <= plan["now"]["rank"]


# ─────────────────────────────────────────────── market views
def test_serp_totals_match_the_known_corpus(payload):
    t = payload["serp"]["ownership"]["totals"]
    assert t["blocks"] == 1122
    assert t["queries"] == 78
    assert t["mapped"] + t["unmapped"] == t["blocks"]
    assert sum(t["by_type"].values()) == t["blocks"]


def test_serp_pages_are_ordered_and_non_empty(payload):
    pages = payload["serp"]["pages"]
    assert pages, "the redrawn-SERP panel needs at least one page"
    order = {t: i for i, t in enumerate(views.BLOCK_ORDER)}
    for query, rows in pages.items():
        assert rows, query
        seen = [order[r["type"]] for r in rows]
        assert seen == sorted(seen), f"{query} is out of block order"


def test_quadrant_is_not_shipped(payload):
    """The opportunity map cuts its zones on demand x visibility — the axes it
    plots. analytics.quadrant_frame cuts on rating, which is a known trap here
    (28 of 34 clinics sit between 4.8 and 5.0), so shipping it would only supply
    labels that contradict the chart."""
    assert "quadrant" not in payload


def test_funnel_is_monotonically_non_increasing(payload):
    counts = [s["count"] for s in payload["funnel"]]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] == len(payload["clinics"])


def test_bands_and_facets_agree_with_the_clinic_list(payload):
    n = len(payload["clinics"])
    assert sum(b["count"] for b in payload["bands"]["bands"]) == n
    assert payload["facets"]["total"] == n
    for facet in ("presence", "band", "verdict"):
        assert sum(r["count"] for r in payload["facets"][facet]) == n, facet


def test_median_reviews_present_and_below_the_skewed_mean(payload):
    k = payload["kpis"]
    assert k["median_reviews"] > 0
    assert k["median_reviews"] < k["avg_reviews"], "mean should be the skewed one"


# ─────────────────────────────────────────────── removals
@pytest.mark.parametrize("dead", ["top10", "rating_distribution", "headline_lead",
                                  "headline_hl", "lede"])
def test_dead_v2_keys_are_gone(payload, dead):
    """They were never read by the app; top10 alone was 40 KB of duplicated clinics."""
    assert dead not in payload


def test_public_payload_contract_still_satisfied(payload):
    """build_public() consumes these; removing one would break the public dist."""
    for key in ("clinics", "kpis", "generated_at", "city", "median_appearances"):
        assert key in payload
    for key in ("unique_clinics", "no_website_count", "avg_rating",
                "pct_with_website", "queries"):
        assert key in payload["kpis"]
