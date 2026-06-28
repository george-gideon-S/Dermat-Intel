import pandas as pd

from modules import analytics, maps_collector

QR = [
    {"rank": r, "search_query": f"q{r}", "category": cat, "user_intent": "x",
     "search_strength_score": 9}
    for r, cat in enumerate(
        ["Discovery", "Pricing", "Near Me / Local", "Trust & Social Proof", "Condition-Based"],
        start=1)
]
ROWS = maps_collector.make_mock_results(QR, per_query=15)


# ---------------------------------------------------------------- data-prep helpers
def test_kpis_counts_uniques_and_website_pct():
    k = analytics.kpis(ROWS)
    assert k["unique_clinics"] > 0
    assert 0 <= k["pct_with_website"] <= 100
    assert 0 <= k["avg_rating"] <= 5


def test_appearance_counts_ranks_desc():
    d = analytics.appearance_counts(ROWS)
    assert list(d["appearances"]) == sorted(d["appearances"], reverse=True)


def test_quadrant_zone_for_high_appear_low_rating():
    rows = [
        {**maps_collector.empty_result_row(), "name": "BadButPopular", "rating": 2.0,
         "user_ratings_total": 4, "place_url": "https://maps.google.com/?cid=1",
         "result_position": 1, "status": "OK"}
        for _ in range(20)
    ] + [
        {**maps_collector.empty_result_row(), "name": "QuietGood", "rating": 4.8,
         "user_ratings_total": 90, "place_url": "https://maps.google.com/?cid=2",
         "result_position": 2, "status": "OK"}
    ]
    df = analytics.quadrant_frame(rows)
    zone = dict(zip(df["name"], df["zone"]))
    assert zone["BadButPopular"] == "Vulnerable"


def test_presence_funnel_monotonic_non_increasing():
    steps = analytics.presence_funnel(ROWS)
    values = [v for _, v in steps]
    assert values == sorted(values, reverse=True)


# ---------------------------------------------------------------- chart builders
def test_every_chart_builds_and_handles_empty():
    figs = analytics.build_all(QR, ROWS)
    assert len(figs) >= 12
    assert all(v is not None for v in figs.values())
    # empty inputs must not raise and must still return figures
    empty = analytics.build_all([], [])
    assert empty is not None
    assert all(v is not None for v in empty.values())
