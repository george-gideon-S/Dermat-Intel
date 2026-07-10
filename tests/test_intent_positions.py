"""Tests for build_web.intent_positions — per-clinic average position by query category,
plus per-category market medians. Feeds the 'Where you rank, by what patients want'
dot-strip in the clinic report (Phase C)."""
from web.build_web import intent_positions


def key_of(row):
    return (row.get("place_url") or row.get("name") or "").lower()


QROWS = [
    {"query": "best dermatologist in guntur", "category": "Discovery"},
    {"query": "acne treatment guntur", "category": "Condition-Based"},
    {"query": "skin doctor fees guntur", "category": "Pricing"},
]


def rows():
    return [
        # clinic A: Discovery twice (pos 1, 3 -> avg 2.0), Condition once (pos 5)
        {"status": "OK", "place_url": "https://maps/a", "name": "A",
         "query": "best dermatologist in guntur", "position": 1},
        {"status": "OK", "place_url": "https://maps/a", "name": "A",
         "query": "best dermatologist in guntur", "position": 3},
        {"status": "OK", "place_url": "https://maps/a", "name": "A",
         "query": "acne treatment guntur", "position": 5},
        # clinic B: Discovery once (pos 8); never in Pricing/Condition
        {"status": "OK", "place_url": "https://maps/b", "name": "B",
         "query": "best dermatologist in guntur", "position": 8},
        # non-OK rows are ignored
        {"status": "EMPTY", "place_url": "https://maps/b", "name": "B",
         "query": "skin doctor fees guntur", "position": 1},
        # unknown query (no category) is ignored
        {"status": "OK", "place_url": "https://maps/a", "name": "A",
         "query": "mystery query", "position": 2},
    ]


def test_per_clinic_average_positions():
    out = intent_positions(rows(), QROWS, key_of)
    a = {e["cat"]: e for e in out["https://maps/a"]}
    assert a["Discovery"]["pos"] == 2.0 and a["Discovery"]["n"] == 2
    assert a["Condition-Based"]["pos"] == 5.0 and a["Condition-Based"]["n"] == 1
    assert "Pricing" not in a                       # never appeared -> omitted


def test_market_medians_per_category():
    out = intent_positions(rows(), QROWS, key_of)
    m = out["_market"]
    # Discovery avg positions: A=2.0, B=8.0 -> median 5.0
    assert m["Discovery"] == 5.0
    assert m["Condition-Based"] == 5.0              # only A
    assert "Pricing" not in m                       # no OK appearances at all


def test_empty_inputs():
    assert intent_positions([], QROWS, key_of) == {"_market": {}}
