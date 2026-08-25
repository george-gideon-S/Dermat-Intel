"""Re-parse a run's saved SERP HTML with the current parser — no re-scraping.

Raw HTML is retained per query for exactly this reason: a parser fix must be applicable to
runs already captured, or every selector correction would mean paying Google's CAPTCHA budget
again to re-measure a market we already have on disk.

    python tools/reparse.py --run last --dry-run
    python tools/reparse.py --run guntur-ap_dermatology_both_2026-08-19

It rewrites `serp/pages/*.json` and the AI-overview half of `serp/extras/*.json`, then reports
what moved. It never touches the fetch log's statuses: whether a query was captured is a fact
about the fetch, not about how well we parsed it afterwards.

What it CANNOT recover is anything that required interacting with the live page — an AI
overview that was still generating when the HTML was saved, an overview that was never
expanded, or the local list behind "More places". Those are reported as unavailable, because
that is what the saved bytes actually contain.
"""
# Embeddable-Python bootstrap: isolated mode keeps the script's own directory off sys.path.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
from collections import Counter

import config
from modules import atomicio, runstore, serp_collector, serp_parser, serp_report
from modules import serp_session as S


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Re-parse saved SERP HTML with the current parser")
    p.add_argument("--run", required=True, metavar="RUN_ID", help="run id, or 'last'")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    args = p.parse_args(argv)

    run_id = args.run
    if run_id == "last":
        runs = runstore.list_runs(config.RUNS_DIR)
        if not runs:
            print("no runs yet.")
            return 2
        run_id = runs[0]["run_id"]

    run_dir = runstore.run_path(config.RUNS_DIR, run_id)
    if not runstore.read_manifest(run_dir):
        print(f"no such run: {run_id}")
        return 2
    qrows = {int(q["rank"]): q for q in S.load_query_rows(run_dir) if q.get("rank") is not None}
    html_dir = serp_collector.serp_dir(run_dir) / "html"
    files = sorted(html_dir.glob("q*.html"))
    if not files:
        print(f"{run_id} has no saved HTML to re-parse.")
        return 2

    before, after = Counter(), Counter()
    changed, ai_now = 0, Counter()
    for path in files:
        try:
            rank = int(path.stem.lstrip("q"))
        except ValueError:
            continue
        old = atomicio.read_json(serp_collector._paths(run_dir, rank)["page"], default={}) or {}
        for b in old.get("blocks") or []:
            before[b.get("block_type")] += 1

        html = path.read_text(encoding="utf-8", errors="replace")
        entry = serp_parser.parse_serp(html, query_row=qrows.get(rank, {}),
                                       screenshot_name=old.get("screenshot"), index=rank)
        for b in entry["blocks"]:
            after[b["block_type"]] += 1
        if [b.get("block_type") for b in old.get("blocks") or []] != \
                [b["block_type"] for b in entry["blocks"]]:
            changed += 1

        detail = serp_parser.ai_overview_detail(html)
        ai_now["present" if detail else "absent"] += 1
        if detail:
            ai_now["available" if detail["available"] else "declined"] += 1

        if not args.dry_run:
            atomicio.write_json(serp_collector._paths(run_dir, rank)["page"], entry, indent=2)
            extras = serp_collector.read_extras(run_dir, rank)
            # Preserve anything only a live session could have produced; replace only the
            # part that is derivable from the saved bytes.
            extras.update({"rank": rank, "query": (qrows.get(rank) or {}).get("search_query"),
                           "ai_overview": detail, "reparsed": True})
            if extras.get("ai_overview") or extras.get("more_places"):
                atomicio.write_json(serp_collector.extras_path(run_dir, rank), extras, indent=2)

    if not args.dry_run:
        repaired = serp_report.repair_statuses(run_dir, list(qrows.values()))
    else:
        repaired = {"fixed": [], "n": 0}
    if repaired["n"]:
        print(f"\nSTATUS CORRECTIONS ({repaired['n']}) — the saved bytes are a wall:")
        for f in repaired["fixed"]:
            print(f"   q{f['rank']}: {f['was']} -> blocked ({f['reason']}, {f['kind']})")

    print(f"{run_id}: re-parsed {len(files)} saved SERPs "
          f"({'dry run' if args.dry_run else 'written'})\n")
    keys = sorted(set(before) | set(after), key=lambda k: -(after[k] + before[k]))
    print(f"{'block type':28s} {'before':>8s} {'after':>8s}  delta")
    for k in keys:
        d = after[k] - before[k]
        print(f"{str(k):28s} {before[k]:>8d} {after[k]:>8d}  {d:+d}" if d else
              f"{str(k):28s} {before[k]:>8d} {after[k]:>8d}")
    print(f"\nqueries whose block list changed: {changed}")
    print(f"AI overview: {ai_now['present']} present, {ai_now['available']} generated, "
          f"{ai_now['declined']} declined by Google, {ai_now['absent']} none on page")
    if ai_now["available"] == 0 and ai_now["present"]:
        print("  NOTE: every saved overview is a refusal. Saved HTML cannot tell us whether a")
        print("  longer wait would have produced one — only a fresh capture can.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
