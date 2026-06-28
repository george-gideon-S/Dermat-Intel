from streamlit.testing.v1 import AppTest

from modules import maps_collector, query_generator, vulnerability


def _mock_state():
    qr = query_generator.parse_pasted_queries(
        "'best dermatologist in Guntur', 'acne treatment Guntur', 'skin doctor fees Guntur', "
        "'dermatologist near me', 'best rated skin clinic reviews Guntur'"
    )
    rows = maps_collector.make_mock_results(qr, per_query=15)
    scored = vulnerability.score_clinics(vulnerability.aggregate_clinics(rows))
    top = vulnerability.top_n(scored, 10)
    return qr, rows, scored, top


def test_app_boots_no_exception():
    at = AppTest.from_file("app.py", default_timeout=30).run()
    assert not at.exception


def test_app_boots_with_mock_toggle():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["use_mock"] = True
    at.run()
    assert not at.exception


def test_app_renders_all_tabs_with_data():
    qr, rows, scored, top = _mock_state()
    at = AppTest.from_file("app.py", default_timeout=120)
    at.session_state["_loaded"] = True  # don't let disk-load override our injected data
    at.session_state["query_rows"] = qr
    at.session_state["result_rows"] = rows
    at.session_state["scored_df"] = scored
    at.session_state["top_df"] = top
    at.session_state["queries_ready"] = True
    at.session_state["maps_ready"] = True
    at.session_state["vuln_ready"] = True
    at.run()
    assert not at.exception
    # sanity: sidebar (3) + Tab-3 KPI (4) metrics all rendered -> every tab executed
    assert len(at.metric) >= 6
