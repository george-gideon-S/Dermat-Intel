"""Rebuild the June 2026 Guntur dermatology run as snapshot #1.

Why this tool exists: on 2026-08-18 a `run_pipeline.py --mock` run overwrote `.cache/
result_rows.json` and two workbooks with 28 synthetic clinics, because the old layout wrote
every run to one shared tree. The genuine June data survives only in the scraper caches.

So the flat result rows are **reconstructed from `maps_raw.json` via the already-tested
`maps_collector.parse_listing`**, never read from `result_rows.json`. The tool refuses to run
if it detects the mock fingerprint, rather than quietly enshrining fake data as history.

Review dates are anchored to the capture date (2026-06-29) so review age stays comparable
against future snapshots. Known gaps are recorded in the manifest as completeness fields
rather than silently diffing to zero next quarter:
  * 3 of 34 clinics were throttled out of the review scrape;
  * 78 of 80 SERPs were captured;
  * 4 historical queries used the banned "near me" phrasing (recorded, not retro-fixed).

Usage:
    python tools/backfill_june_snapshot.py [--dry-run]
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import shutil
from datetime import datetime

import config
from modules import atomicio, dateresolve, maps_collector, runstore

CAPTURE_DATE = "2026-06-29"     # from the SERP screenshot filenames
RUN_DATE = "2026-06-28"         # maps_raw.json mtime — the run's start
LEGACY_CACHE = _Path(config.BASE_DIR) / ".cache"
LEGACY_DATA = _Path(config.BASE_DIR) / "data"

COPY_CACHE = ["maps_raw.json", "maps_details.json", "reviews_raw.json", "reviews_nlp.json",
              "query_rows.json", "web_screens.json", "web_raw.json"]
COPY_DATA = ["unified_results.xlsx", "google_search_results.xlsx"]

MOCK_MARKERS = ("example.com", '"place_id": "100')


def _looks_like_mock(rows) -> bool:
    """The mock pool uses *.example.com websites and sequential place ids."""
    sample = str(rows[:50])
    return any(m in sample for m in MOCK_MARKERS)


def reconstruct_result_rows(maps_raw: dict, query_rows: list[dict]) -> list[dict]:
    """Rebuild the 20-key flat rows from the raw per-query scrape."""
    by_query = {str(q.get("search_query")): q for q in query_rows}
    out = []
    for query, listings in (maps_raw or {}).items():
        qrow = by_query.get(query, {"rank": None, "search_query": query, "category": None})
        for i, raw in enumerate(listings or [], start=1):
            out.append(maps_collector.parse_listing(raw, qrow, i))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    maps_raw = atomicio.read_json(LEGACY_CACHE / "maps_raw.json", default=None)
    query_rows = atomicio.read_json(LEGACY_CACHE / "query_rows.json", default=None)
    if not maps_raw or not query_rows:
        print("ABORT: .cache/maps_raw.json or query_rows.json missing — nothing to backfill.")
        return 1

    rows = reconstruct_result_rows(maps_raw, query_rows)
    clinics = {maps_collector.dedup_key(r.get("place_url", "")) or (r.get("name") or "").lower()
               for r in rows}
    clinics.discard("")
    if _looks_like_mock(rows):
        print("ABORT: reconstructed rows look like mock data — refusing to enshrine fakes.")
        return 1

    reviews_raw = atomicio.read_json(LEGACY_CACHE / "reviews_raw.json", default={}) or {}
    resolved = dateresolve.resolve_all(reviews_raw, CAPTURE_DATE)
    cov = dateresolve.coverage(resolved)
    reviewed_clinics = len([k for k in resolved if k != "_meta"])
    web = atomicio.read_json(LEGACY_CACHE / "web_screens.json", default={}) or {}
    meta = web.get("meta", {})
    shots = list((LEGACY_DATA / "Full Page Screenshots").glob("*.png"))
    near_me = [q.get("search_query") for q in query_rows
               if "near me" in str(q.get("search_query", "")).lower()]

    print(f"reconstructed rows : {len(rows)} from {len(maps_raw)} maps queries")
    print(f"unique clinics     : {len(clinics)}")
    print(f"queries            : {len(query_rows)}   (near-me violations: {len(near_me)})")
    print(f"SERPs captured     : {meta.get('num_screenshots')} of "
          f"{meta.get('num_queries_expected')}   screenshots on disk: {len(shots)}")
    print(f"review coverage    : {reviewed_clinics} clinics, {cov['reviews']} reviews, "
          f"{cov['resolved_pct']}% dated")
    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    run = runstore.create_run(
        geography="guntur-ap", practice="dermatology", subject_type="both",
        run_date=RUN_DATE, query_threshold=len(query_rows),
        packs={"geography": "guntur-ap", "specialty": "dermatology"},
        notes="Backfilled from the June 2026 caches. Flat rows reconstructed from maps_raw.json "
              "via parse_listing; result_rows.json was destroyed by a --mock run on 2026-08-18.")
    dest = _Path(run.path)
    print(f"\nrun: {run.run_id}")

    for name in COPY_CACHE:
        src = LEGACY_CACHE / name
        if src.exists():
            shutil.copy2(src, dest / ".cache" / name)
    for name in COPY_DATA:
        src = LEGACY_DATA / name
        if src.exists():
            shutil.copy2(src, dest / "data" / name)

    shots_dir = dest / "serp" / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    for png in shots:
        shutil.copy2(png, shots_dir / png.name)

    atomicio.write_json(dest / ".cache" / "result_rows.json", rows)
    atomicio.write_json(dest / ".cache" / "reviews_raw.json", resolved, indent=2)

    runstore.update_manifest(
        run.path,
        denominators={"maps_query_count": len(maps_raw),
                      "captured_serps": int(meta.get("num_screenshots") or len(shots)),
                      "total_queries": len(query_rows)},
        scoring={"scoring_version": "june-legacy",
                 "note": "Scored under the pre-parameterisation constants: DEMAND_FULL=25, "
                         "OWNED_FULL=6, BORROWED_FULL=12, PLACES_FULL=8, BREADTH_FULL=10."},
        completeness={
            "clinics": len(clinics),
            "result_rows": len(rows),
            "review_clinics": reviewed_clinics,
            "review_clinics_missing": max(0, len(clinics) - reviewed_clinics),
            "reviews": cov["reviews"],
            "reviews_dated_pct": cov["resolved_pct"],
            "serps_captured": int(meta.get("num_screenshots") or 0),
            "serps_expected": int(meta.get("num_queries_expected") or len(query_rows)),
            "unmatched_queries": meta.get("unmatched_queries", []),
            "near_me_queries": near_me,
            "screenshots_on_disk": len(shots),
        },
        web_signal="full",
        source="backfill",
        capture_date=CAPTURE_DATE,
        backfilled_at=datetime.now().isoformat(timespec="seconds"),
    )
    for name in COPY_CACHE + ["result_rows.json"]:
        p = dest / ".cache" / name
        if p.exists():
            runstore.record_artifact(run.path, name, f".cache/{name}", captured_at=CAPTURE_DATE)

    runstore.finalize_run(run.path)
    print(f"finalized -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
