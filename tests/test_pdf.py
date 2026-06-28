from components.tab_vulnerable import build_pdf_brief
from modules import maps_collector, vulnerability


def test_pdf_brief_returns_pdf_bytes():
    qr = [{"rank": 1, "search_query": "q", "category": "Discovery",
           "user_intent": "x", "search_strength_score": 9}]
    rows = maps_collector.make_mock_results(qr, per_query=15)
    top = vulnerability.top_n(
        vulnerability.score_clinics(vulnerability.aggregate_clinics(rows)), 10)
    data = build_pdf_brief(top)
    assert isinstance(data, (bytes, bytearray))
    assert bytes(data[:4]) == b"%PDF"
