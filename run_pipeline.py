"""Headless pipeline runner — scrape all saved queries, score, and export, without the UI.

Usage:
    python run_pipeline.py          # live Google Maps scrape
    python run_pipeline.py --mock   # instant deterministic sample data

Reads the 50 queries you saved in the app (Tab 1), writes the same outputs the app uses, so opening
Results are written to data/ and .cache/ for whatever consumes them next.
"""
# This machine runs the embeddable Python distribution, whose python310._pth
# forces isolated mode: the script directory is NOT added to sys.path and
# PYTHONPATH is ignored. Same bootstrap conftest.py uses, so the CLI runs.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))

import sys
from datetime import datetime
from pathlib import Path

import config
from modules import maps_collector, query_generator, storage, vulnerability


def load_queries() -> list[dict]:
    rows = storage.load_rows(storage.QUERIES_JSON)
    if rows:
        return rows
    import openpyxl  # fallback: rebuild query rows from the saved workbook
    p = Path(config.QUERIES_XLSX)
    if not p.exists():
        return []
    ws = openpyxl.load_workbook(p).active
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r and r[1]:
            out.append({"rank": r[0], "search_query": r[1], "category": r[2],
                        "user_intent": r[3], "search_strength_score": r[4]})
    return out


def main() -> int:
    mock = "--mock" in sys.argv
    qrows = load_queries()
    if not qrows:
        print("No queries found. Open the app, paste 50 queries in Tab 1, then re-run.")
        return 1

    print(f"Running pipeline on {len(qrows)} queries (mock={mock}) ...", flush=True)

    def cb(i, n, q):
        print(f"[{i}/{n}] {q}", flush=True)

    rows = maps_collector.collect(qrows, mock=mock, progress_cb=cb)

    storage.save_rows(storage.RESULTS_JSON, rows)
    query_generator.save_queries_xlsx(qrows)
    maps_collector.save_results_xlsx(rows)
    scored = vulnerability.score_clinics(vulnerability.aggregate_clinics(rows))
    top = vulnerability.top_n(scored, 10)
    vulnerability.save_vulnerable_xlsx(top)
    storage.save_meta({"last_run": datetime.now().isoformat(timespec="seconds")})

    ok = sum(1 for r in rows if r.get("status") == "OK")
    uniq = 0 if scored is None or scored.empty else len(scored)
    print(f"\nDONE: {len(rows)} rows ({ok} OK, {len(rows) - ok} failed), "
          f"{uniq} unique clinics, top {len(top)} vulnerable exported.", flush=True)
    print("Results written to data/ and .cache/", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
