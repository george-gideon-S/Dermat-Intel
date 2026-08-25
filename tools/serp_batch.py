"""Option A — batched SERP capture: a short session, then get off Google's lawn.

Google challenged this residential IP at query 41 and again at query 83 on 2026-08-19 — a wall
roughly every ~40 sustained queries. This runner never goes near that: it captures at most
--batch queries (default 30), parks itself behind a cooldown, and exits. A scheduler re-invokes
it later and it resumes exactly where it stopped. 100 queries becomes 3-4 short sessions across
a day, ~45 minutes of actual scraping, with nobody in the room.

    python tools/serp_batch.py --run last                      # one batch, then exit
    python tools/serp_batch.py --run last --batch 30 --rest 150
    python tools/serp_batch.py --geo guntur-ap --specialty dermatology --threshold 100
    python tools/serp_batch.py --run last --print-schedule     # the schtasks line to register

If a wall does appear mid-batch the session stops immediately rather than grinding: while
flagged, every further fetch costs a page load and returns nothing, and hammering a flagged
session is the one thing likely to extend the flag. The block is recorded (never as empty),
a longer cooldown is set, and the next invocation retries it.

That retry is also the measurement we do not yet have: **does a block expire on its own?**
Every session is appended to serp/runner_state.json with what it found, so after two or three
blocked-then-retried cycles the history answers it directly — if a later session runs clean
with no human involved, the wall self-expired and this runner is fully unattended.

Exit codes, chosen so a scheduler can branch on them:
    0  every query captured — the run's SERP stage is done
    10 batch finished, queries still pending — come back after the cooldown
    20 blocked — a CAPTCHA; cooling down longer, retry later
    21 stalled — nothing captured and it was NOT a wall; needs a human to look
    30 too early — a cooldown is still active, nothing was done
    2  refused before touching the browser
    1  unexpected failure

Never solves a CAPTCHA.
"""
# Embeddable-Python bootstrap: isolated mode keeps the script's own directory off sys.path.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import random
import time

import config
from modules import packs, serp_collector, serp_report, serp_session as S

BLOCK_FLAG = "BLOCKED.txt"
STALL_FLAG = "STALLED.txt"

EXIT_DONE, EXIT_MORE, EXIT_BLOCKED, EXIT_EARLY, EXIT_REFUSED = 0, 10, 20, 30, 2
EXIT_STALLED = 21


class BatchSession:
    """One scheduled session: fetch up to N, stop on the first wall."""

    def __init__(self, handle, args):
        self.handle = handle
        self.args = args
        self.attempted = 0
        self.blocked_at = None
        self.stalled_at = None
        self.non_terminal = 0
        self.captured_at_start = S.status_counts(handle.run_dir, handle.qrows)["captured"]
        self.started = time.monotonic()

    def pace(self) -> None:
        time.sleep(random.uniform(self.args.pace_min, self.args.pace_max))

    def breather(self) -> None:
        if self.args.breather <= 0:
            return
        print(f"   breather {self.args.breather:.0f}s …", flush=True)
        time.sleep(self.args.breather)

    def progress(self, i: int, n: int, query: str) -> None:
        S.heartbeat(self.handle.run_dir, query_done=True)
        print(f"[{self.attempted + 1:>3}/{self.args.batch}] q{i} of {n}  {query[:56]}",
              flush=True)

    def stop(self, info: dict) -> bool:
        self.attempted = info.get("attempted", self.attempted)
        status = info.get("status")
        if status == serp_collector.STATUS_BLOCKED:
            self.blocked_at = {"rank": info.get("rank"), "query": info.get("query")}
            print(f"   BLOCKED at q{info.get('rank')} — stopping this session.", flush=True)
            return True
        if status not in serp_collector.TERMINAL_OK:
            # An anomaly or driver error is not a wall, but a run of them means something
            # changed. Tolerate a few, then stop rather than burn the whole batch on it.
            self.non_terminal += 1
            if self.non_terminal >= self.args.max_anomalies:
                # Recorded as its own outcome. Reporting this as a clean capped batch would
                # make a session that captured NOTHING indistinguishable from one that
                # captured everything it set out to — and a scheduler would keep firing into
                # it forever, making no progress, with every tick reading as healthy.
                self.stalled_at = {"rank": info.get("rank"), "query": info.get("query"),
                                   "status": status, "streak": self.non_terminal}
                print(f"   {self.non_terminal} non-terminal results in a row "
                      f"(last: {status}) — stopping.", flush=True)
                return True
        else:
            self.non_terminal = 0
        return self.attempted >= self.args.batch


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Batched unattended Google SERP capture (Option A)")
    p.add_argument("--run", metavar="RUN_ID", help="attach to a snapshot; 'last' = newest open run")
    p.add_argument("--geo", "--geography", dest="geo", help="geography pack, e.g. guntur-ap")
    p.add_argument("--specialty", help="specialty pack, e.g. dermatology")
    p.add_argument("--subject", default="both", choices=list(packs.SUBJECT_TYPES))
    p.add_argument("--threshold", type=int, default=None, help="query count (default: pack)")
    p.add_argument("--date", default=None, help="snapshot date YYYY-MM-DD (default: today)")
    p.add_argument("--notes", default="", help="free text stored in the manifest")
    p.add_argument("--batch", type=int, default=S.DEFAULT_BATCH,
                   help=f"queries per session (default {S.DEFAULT_BATCH}; measured wall ~40)")
    p.add_argument("--rest", type=float, default=150.0,
                   help="minutes to wait after a clean batch (default 150)")
    p.add_argument("--block-rest", type=float, default=360.0, dest="block_rest",
                   help="minutes to wait after a wall (default 360)")
    p.add_argument("--force", action="store_true", help="ignore an active cooldown")
    p.add_argument("--max-anomalies", type=int, default=3, dest="max_anomalies",
                   help="consecutive non-terminal results tolerated before stopping")
    p.add_argument("--pace-min", type=float, default=5.0, dest="pace_min")
    p.add_argument("--pace-max", type=float, default=15.0, dest="pace_max")
    p.add_argument("--breather", type=float, default=75.0,
                   help="seconds of extra rest every --breather-every queries (0 = off)")
    p.add_argument("--breather-every", type=int, default=10, dest="breather_every")
    p.add_argument("--notify-on-block", action="store_true", dest="notify_on_block",
                   help="beep if a wall appears (off by default — this runs overnight)")
    p.add_argument("--no-report", action="store_true", help="skip the HTML report")
    p.add_argument("--print-schedule", action="store_true", dest="print_schedule",
                   help="print the schtasks command to register this batch, and exit")
    p.add_argument("--status", action="store_true",
                   help=f"print progress and exit ({EXIT_DONE} = done, {EXIT_MORE} = pending)")
    return p


def _validate(args) -> None:
    if (args.status or args.print_schedule) and not args.run:
        # These two only ever REPORT on a run, but they sit after run resolution, and
        # resolution creates a run when given --geo/--specialty. A command that reads as
        # read-only would otherwise mint a throwaway snapshot carrying today's date, which
        # then wins every later `--run last` lookup and quietly steals the scraper's
        # scarce per-wall query budget away from the run actually in progress.
        raise S.SessionRefused(
            "--status and --print-schedule report on an existing run: pass --run RUN_ID "
            "(or --run last). They will not create one.")
    if args.batch < 1:
        raise S.SessionRefused("--batch must be at least 1")
    if args.batch > 40:
        raise S.SessionRefused(
            f"--batch {args.batch} is at or past the measured wall (~40 queries on this IP). "
            f"Use --batch 30 and let the scheduler come back.")
    if args.pace_min < 0 or args.pace_max < args.pace_min:
        raise S.SessionRefused("--pace-min must be >= 0 and <= --pace-max")
    if args.rest < 0 or args.block_rest < 0:
        raise S.SessionRefused("cooldowns cannot be negative")


def cmd_print_schedule(handle, args) -> int:
    """Write a launcher .bat and print the command that registers it.

    Printed, never executed: registering a scheduled task changes machine configuration, and
    that is the operator's call rather than this script's.

    The indirection through a .bat is not decoration. Both the interpreter path
    ("SALE PITCHAIAH") and the repo path ("Dermat Analytics and Websites") contain spaces, and
    `schtasks /TR` takes one string that it re-parses — getting two nested quoting levels right
    there is a coin flip that fails silently as a task which never runs. A .bat owns its own
    quoting, so the scheduler only ever sees a single program path.
    """
    python = _sys.executable
    script = str(_Path(__file__).resolve())
    # Bake this invocation's tuning into the launcher. A task registered from the printed
    # command passes no arguments, so anything not baked in silently reverts to the defaults —
    # printing a schedule derived from --rest while the runner used 150 would be a lie.
    tuning = (f"--batch {args.batch} --rest {args.rest:g} --block-rest {args.block_rest:g} "
              f"--pace-min {args.pace_min:g} --pace-max {args.pace_max:g} "
              f"--breather {args.breather:g} --breather-every {args.breather_every}")
    if args.notify_on_block:
        tuning += " --notify-on-block"
    bat = _Path(handle.run_dir) / "serp_batch.bat"
    bat.write_text(
        "@echo off\r\n"
        "rem Auto-generated launcher for the batched SERP runner. Safe to delete.\r\n"
        f'"{python}" "{script}" --run {handle.run_id} {tuning} %*\r\n'
        "exit /b %errorlevel%\r\n", encoding="utf-8")

    task = f"DermaIntel SERP {handle.run_id}"
    # Fire well inside the cooldown, not level with it. set_cooldown counts from when a session
    # ENDS, so a trigger spaced exactly --rest apart always lands a little early and wastes a
    # whole period doing nothing — the effective cadence silently doubles.
    every = max(5, int(args.rest / 4))
    print(f"launcher written: {bat}\n")
    print("Run it by hand any time:\n")
    print(f'  "{bat}"\n')
    print("Or register it to repeat (review this before running it — it changes machine "
          "configuration). In PowerShell:\n")
    print(f'  $A = New-ScheduledTaskAction -Execute "{bat}"')
    print(f'  $T = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) '
          f'-RepetitionInterval (New-TimeSpan -Minutes {every})')
    print(f'  Register-ScheduledTask -TaskName "{task}" -Action $A -Trigger $T '
          f'-Description "Batched Google SERP capture"\n')
    print("IMPORTANT: leave it as 'run only when the user is logged on'. The scraper drives a")
    print("VISIBLE Chrome, and a task configured to run whether-logged-on-or-not has no")
    print("desktop to draw it on, so every session would fail.\n")
    print(f"The task fires every {every} min; the runner's own cooldown ({args.rest:g} min")
    print(f"after a clean batch) decides whether it actually does anything —")
    print(f"exit {EXIT_EARLY} = too early, nothing done, no browser opened.")
    print("Remove it later with:\n")
    print(f'  Unregister-ScheduledTask -TaskName "{task}" -Confirm:$false')
    return 0


def cmd_status(handle) -> int:
    st = S.status_counts(handle.run_dir, handle.qrows)
    state = S.read_state(handle.run_dir)
    remaining = S.cooldown_remaining(handle.run_dir)
    S.print_header(handle, "SERP BATCH STATUS", {
        "cooldown": (f"{S.human_duration(remaining)} left ({state.get('cooldown_reason','')})"
                     if remaining > 0 else "clear — a session may start now"),
        "walls hit": state.get("blocks_seen", 0),
        "sessions": len(state.get("sessions") or []),
    })
    for s in (state.get("sessions") or [])[-8:]:
        print(f"   #{s.get('n'):<3} {str(s.get('mode','?')):9s} {str(s.get('outcome','?')):11s} "
              f"attempted={s.get('attempted',0):<3} captured={s.get('captured',0):<3} "
              f"blocked={s.get('blocked',0):<2} {s.get('ended_at','')}")
    for label, key in (("blocked", serp_collector.STATUS_BLOCKED),
                       ("anomalies", serp_collector.STATUS_ANOMALY),
                       ("errors", serp_collector.STATUS_ERROR)):
        if st["counts"][key]:
            print(f" {label:11s}: {st['counts'][key]}")
    return EXIT_DONE if not st["n_pending"] else EXIT_MORE


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _validate(args)
        handle = S.resolve(args, root=config.RUNS_DIR)
        S.ensure_fingerprint(handle.run_dir, handle.qrows)
    except (S.SessionRefused, packs.PackNotFound, packs.InvalidPack) as exc:
        print(f"refused: {exc}")
        return EXIT_REFUSED

    if args.print_schedule:
        return cmd_print_schedule(handle, args)
    if args.status:
        return cmd_status(handle)

    st = S.status_counts(handle.run_dir, handle.qrows)
    if not st["n_pending"]:
        print(f"{handle.run_id}: all {st['total']} queries captured — nothing to do.")
        S.publish_web_signal(handle.run_dir, handle.qrows)
        if not args.no_report:
            print(f"report: {serp_report.build_report(handle.run_dir)}")
        return EXIT_DONE

    remaining = S.cooldown_remaining(handle.run_dir)
    if remaining > 0 and not args.force:
        state = S.read_state(handle.run_dir)
        print(f"cooling down: {S.human_duration(remaining)} left "
              f"({state.get('cooldown_reason', 'rest')}) — nothing done. "
              f"Use --force to override.")
        return EXIT_EARLY

    S.print_header(handle, "BATCHED SERP CAPTURE  (Option A — unattended)",
                   {"batch": f"{args.batch} queries this session",
                    "rest": f"{args.rest:g} min clean / {args.block_rest:g} min after a wall"})

    session = BatchSession(handle, args)
    lock = S.SessionLock(mode="batch", run_id=handle.run_id)
    try:
        lock.acquire()
    except S.SessionRefused as exc:
        print(f"refused: {exc}")
        return EXIT_REFUSED

    driver = None
    started_at = S.now_iso()
    interrupted = failed = False
    S.begin_session(handle.run_dir, "batch", handle.run_id)

    try:
        driver = S.build_driver(handle.ctx)
        serp_collector.collect_serps(
            handle.qrows, driver, run_dir=handle.run_dir,
            progress_cb=session.progress, stop_cb=session.stop,
            pace=session.pace,
            breather=session.breather if args.breather > 0 else None,
            breather_every=args.breather_every,
            # No human is watching, so a wall must be recorded on the first look rather than
            # retried behind a backoff that would burn minutes achieving nothing.
            max_block_retries=0, pause_cb=None)
    except KeyboardInterrupt:
        interrupted = True
        print("\ninterrupted — every completed query is already on disk.", flush=True)
    except Exception as exc:
        failed = True
        print(f"\nsession failed: {type(exc).__name__}: {exc}", flush=True)
        # Count what this session actually got before it died. Recording a flat zero would
        # under-report real captures and make the session history lie about a partial run.
        gained = (S.status_counts(handle.run_dir, handle.qrows)["captured"]
                  - session.captured_at_start)
        S.record_session(handle.run_dir, mode="batch", outcome="failed",
                         started_at=started_at, ended_at=S.now_iso(),
                         attempted=session.attempted, captured=gained, blocked=0,
                         error=f"{type(exc).__name__}: {exc}")
        # Rest before trying again: a failure that repeats every scheduler tick is a way of
        # hammering Google that looks like nothing is happening.
        S.set_cooldown(handle.run_dir, args.rest, "after a failed session")
    finally:
        _close(driver, handle)
        S.end_session(handle.run_dir)     # the clock stops on EVERY exit path
        lock.release()

    if failed:
        # Publish before leaving. _finish is skipped on this path, and without this the
        # manifest's web_signal keeps last session's numbers while the fetch log has moved on —
        # so the run's headline figure silently lags whatever actually got captured.
        S.publish_web_signal(handle.run_dir, handle.qrows)
        return 1
    return _finish(handle, session, args, started_at, interrupted)


def _close(driver, handle) -> None:
    """collect_serps stops the driver on its normal path; this covers the abort paths."""
    try:
        if driver is not None:
            driver.stop()
    except Exception as exc:
        print(f"   (browser shutdown: {type(exc).__name__}: {exc})", flush=True)
    try:
        serp_collector.finalize(handle.run_dir, handle.qrows)
    except Exception as exc:
        print(f"   (finalize: {type(exc).__name__}: {exc})", flush=True)


def _finish(handle, session, args, started_at, interrupted) -> int:
    summary = S.publish_web_signal(handle.run_dir, handle.qrows)
    st = S.status_counts(handle.run_dir, handle.qrows)
    gained = st["captured"] - session.captured_at_start
    elapsed = time.monotonic() - session.started
    blocked = session.blocked_at is not None

    if not st["n_pending"]:
        outcome, code = "complete", EXIT_DONE
        S.clear_cooldown(handle.run_dir)
    elif blocked:
        outcome, code = "blocked", EXIT_BLOCKED
        until = S.set_cooldown(handle.run_dir, args.block_rest, "after a wall")
        S.write_flag(handle.run_dir, BLOCK_FLAG,
                     f"blocked at q{session.blocked_at['rank']}: {session.blocked_at['query']}\n"
                     f"next attempt not before {until}\n"
                     f"Solve it sooner by running tools/serp_attended.py --run "
                     f"{handle.run_id}")
        if args.notify_on_block:
            S.notify("SERP run blocked",
                     f"{handle.run_id}: wall at q{session.blocked_at['rank']}. "
                     f"Next attempt after {until}.")
    elif interrupted:
        outcome, code = "interrupted", EXIT_MORE
    elif session.stalled_at is not None:
        # Nothing is being captured and nothing is a wall — the DOM changed, the driver is
        # failing, or the machine is offline. Saying "capped" here would let a scheduler fire
        # into a dead run indefinitely with every tick reporting success.
        outcome, code = "stalled", EXIT_STALLED
        S.set_cooldown(handle.run_dir, args.rest, "after a stalled session")
        S.write_flag(handle.run_dir, STALL_FLAG,
                     f"{session.stalled_at['streak']} non-terminal results in a row, last at "
                     f"q{session.stalled_at['rank']} ({session.stalled_at['status']}).\n"
                     f"Nothing was captured. This is not a CAPTCHA — check the browser, the\n"
                     f"network, and whether Google's DOM moved (re-parse serp/html/ to tell).")
    else:
        outcome, code = "capped", EXIT_MORE
        S.set_cooldown(handle.run_dir, args.rest, "after a clean batch")
        S.clear_flag(handle.run_dir, BLOCK_FLAG)
        S.clear_flag(handle.run_dir, STALL_FLAG)

    S.record_session(handle.run_dir, mode="batch", outcome=outcome,
                     started_at=started_at, ended_at=S.now_iso(),
                     attempted=session.attempted, captured=gained,
                     blocked=1 if blocked else 0, elapsed_s=round(elapsed),
                     blocked_at=session.blocked_at, stalled_at=session.stalled_at)

    print("-" * 72)
    print(f" outcome    : {outcome}")
    print(f" this session: {session.attempted} attempted, {gained} newly captured, "
          f"{S.human_duration(elapsed)}")
    print(f" run total  : {st['captured']}/{st['total']} captured "
          f"({summary['yield']*100:.0f}%)  web_signal={summary['web_signal']}")
    if st["n_pending"]:
        nxt = S.read_state(handle.run_dir).get("next_earliest")
        print(f" pending    : {st['n_pending']}" + (f" — next session after {nxt}" if nxt else ""))
    if not args.no_report:
        try:
            print(f" report     : {serp_report.build_report(handle.run_dir)}")
        except Exception as exc:
            print(f" report     : failed ({type(exc).__name__}: {exc})")
    print("=" * 72, flush=True)
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\naborted.")
        raise SystemExit(130)
