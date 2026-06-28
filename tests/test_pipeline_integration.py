"""End-to-end mock pipeline: queries -> 750 result rows -> 3 Excel exports that open cleanly."""
from pathlib import Path

import openpyxl

from modules import maps_collector as mc, query_generator as qg, vulnerability as vuln


def test_full_mock_pipeline_writes_three_xlsx(tmp_path):
    # Step 1 — 50 queries
    pasted = ", ".join(f"'query {i} dermatologist Guntur'" for i in range(1, 51))
    qrows = qg.parse_pasted_queries(pasted)
    assert len(qrows) == 50
    qx = qg.save_queries_xlsx(qrows, str(tmp_path / "q.xlsx"))

    # Step 2 — maps data (mock): 50 queries x 15 = 750 rows
    rows = mc.collect(qrows, mock=True)
    assert len(rows) == 50 * 15
    rx = mc.save_results_xlsx(rows, str(tmp_path / "r.xlsx"))

    # Step 3/4 — aggregate, score, export top 10
    scored = vuln.score_clinics(vuln.aggregate_clinics(rows))
    assert not scored.empty
    top = vuln.top_n(scored, 10)
    assert 0 < len(top) <= 10
    vx = vuln.save_vulnerable_xlsx(top, str(tmp_path / "v.xlsx"))

    # all three workbooks exist and open cleanly
    for p in (qx, rx, vx):
        assert Path(p).exists()
        openpyxl.load_workbook(p)
