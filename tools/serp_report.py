"""Build the Google Search review page for a run — every query on one self-contained page.

    python tools/serp_report.py --run last
    python tools/serp_report.py --run guntur-ap_dermatology_both_2026-08-19 --open
    python tools/serp_report.py --run last --out E:/somewhere/serp.html

The page is written into the run directory so its relative screenshot links resolve. Writing
it elsewhere with --out keeps the data but loses the screenshots, which is usually what you
want when sending it to someone.
"""
# Embeddable-Python bootstrap: isolated mode keeps the script's own directory off sys.path.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import webbrowser

import config
from modules import runstore, serp_report, serp_session as S


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Build the Google SERP review page for a run")
    p.add_argument("--run", required=True, metavar="RUN_ID",
                   help="run id, or 'last' for the newest run")
    p.add_argument("--out", default=None, help="write somewhere other than the run directory")
    p.add_argument("--open", action="store_true", dest="open_it",
                   help="open the page in the default browser")
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

    qrows = S.load_query_rows(run_dir)
    if not qrows:
        print(f"{run_id} has no .cache/query_rows.json — nothing to report on.")
        return 2

    path = serp_report.build_report(run_dir, out_path=args.out, qrows=qrows)
    data = serp_report.collect_data(run_dir, qrows=qrows)
    m = data["meta"]
    print(f"{path}")
    print(f"  {m['captured']}/{m['total']} queries captured ({m['yield']*100:.0f}%), "
          f"{m['total_blocks']} blocks, {len(data['domains'])} sites, "
          f"{len(data['places'])} local-pack names")
    if args.open_it:
        webbrowser.open(_Path(path).resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
