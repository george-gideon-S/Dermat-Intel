"""One-click market analysis from the command line — the CLI half of the JobRunner.

    python run_market.py --geo guntur-ap --specialty dermatology --subject both --threshold 100
    python run_market.py --resume guntur-ap_dermatology_both_2026-08-18
    python run_market.py --list
    python run_market.py --diff RUN_A RUN_B
    python run_market.py --packs

Same JobRunner as the API, so a run launched here is identical to one launched over HTTP and
lands in the same immutable snapshot store. `--mock` runs the whole pipeline on deterministic
offline data — useful for exercising the orchestration without opening a browser.
"""
# Embeddable-Python bootstrap: isolated mode keeps the script's own directory off sys.path.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))

import argparse
import json

import config
from modules import jobs, packs, runstore, snapshot_diff


def _progress(evt: dict) -> None:
    stage = evt.get("stage", "?")
    if evt.get("status") == "progress":
        print(f"  [{stage}] {evt.get('i')}/{evt.get('n')} {str(evt.get('label',''))[:48]}",
              flush=True)
    else:
        counts = evt.get("counts") or {}
        tail = " ".join(f"{k}={v}" for k, v in counts.items())
        flag = " (awaiting human — solve the CAPTCHA in the browser window)" if evt.get("awaiting_human") else ""
        print(f"[{stage}] {evt.get('status')} {tail}{flag}", flush=True)


def cmd_run(args) -> int:
    runner = jobs.JobRunner(root=config.RUNS_DIR, mock=args.mock)
    try:
        job = runner.run(geography=args.geo, specialty=args.specialty,
                         subject_type=args.subject, query_threshold=args.threshold,
                         run_date=args.date, progress_cb=_progress)
    except jobs.JobAlreadyRunning as exc:
        print(f"refused: {exc}")
        return 2
    except (packs.PackNotFound, packs.InvalidPack) as exc:
        print(f"bad market: {exc}")
        return 2
    print(f"\n{job.status.upper()}  run_id={job.run_id}")
    for stage, status in job.stages.items():
        print(f"   {stage:10s} {status}")
    if job.errors:
        print("   errors:", "; ".join(job.errors[:5]))
    return 0 if job.status == "complete" else 1


def cmd_resume(args) -> int:
    try:
        job = jobs.JobRunner(root=config.RUNS_DIR).resume(args.resume, progress_cb=_progress)
    except FileNotFoundError as exc:
        print(exc)
        return 2
    print(f"{job.status.upper()}  run_id={job.run_id}")
    return 0 if job.status == "complete" else 1


def cmd_list(_args) -> int:
    runs = runstore.list_runs(config.RUNS_DIR)
    if not runs:
        print("no runs yet.")
        return 0
    print(f"{'run_id':52s} {'status':10s} {'web':8s} date")
    for r in runs:
        print(f"{r['run_id']:52s} {str(r.get('status')):10s} "
              f"{str(r.get('web_signal') or '-'):8s} {r.get('run_date')}")
    return 0


def cmd_diff(args) -> int:
    a, b = args.diff
    # Verify both runs exist first: diff_by_id reads a missing manifest/clinics as empty
    # defaults, so diffing a typo'd run id would otherwise print a confident all-zero diff.
    for rid in (a, b):
        if not runstore.read_manifest(runstore.run_path(config.RUNS_DIR, rid)):
            print(f"no such run: {rid}")
            return 2
    d = snapshot_diff.diff_by_id(config.RUNS_DIR, a, b)
    s = d["summary"]
    print(f"{d['run_a']}  ->  {d['run_b']}")
    if not d["scores_comparable"]:
        print(f"  ! {d.get('comparability_note')}")
    print(f"  new clinics : {s['new']}")
    print(f"  lost clinics: {s['lost']}")
    print(f"  changed     : {s['changed']}  (of {s['clinics_a']} -> {s['clinics_b']})")
    for c in d["changed"][:15]:
        bits = [f"{k}{'+' if (isinstance(v,(int,float)) and v>0) else ''}{v}"
                for k, v in c["deltas"].items()]
        if c["website_gained"]:
            bits.append("website+")
        if c["website_lost"]:
            bits.append("website-")
        print(f"     {str(c['name'])[:40]:40s} {' '.join(bits)}")
    return 0


def cmd_packs(_args) -> int:
    print(json.dumps({"geographies": packs.available_geographies(),
                      "specialties": packs.available_specialties(),
                      "subject_types": list(packs.SUBJECT_TYPES)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Derma Intel market-intelligence runner")
    p.add_argument("--geo", "--geography", dest="geo", help="geography pack id, e.g. guntur-ap")
    p.add_argument("--specialty", dest="specialty", help="specialty pack id, e.g. dermatology")
    p.add_argument("--subject", default="both", choices=list(packs.SUBJECT_TYPES))
    p.add_argument("--threshold", type=int, default=None, help="query count (default: pack)")
    p.add_argument("--date", default=None, help="snapshot date YYYY-MM-DD (default: today)")
    p.add_argument("--mock", action="store_true", help="deterministic offline data, no browser")
    p.add_argument("--resume", metavar="RUN_ID", help="resume an interrupted run")
    p.add_argument("--list", action="store_true", help="list snapshots")
    p.add_argument("--diff", nargs=2, metavar=("RUN_A", "RUN_B"), help="diff two snapshots")
    p.add_argument("--packs", action="store_true", help="list available packs")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.packs:
        return cmd_packs(args)
    if args.list:
        return cmd_list(args)
    if args.diff:
        return cmd_diff(args)
    if args.resume:
        return cmd_resume(args)
    if args.geo and args.specialty:
        return cmd_run(args)
    build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
