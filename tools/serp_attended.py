"""Option B — the attended SERP runner: run straight through, shout when Google blocks.

This is the path that actually produced 82/100 on 2026-08-19, formalised. The operator is not
watching the screen; they are in the room. When Google puts up a wall the script beeps, raises
a balloon, writes a flag file, and waits — the browser window is already open on the CAPTCHA.
Press ENTER once it is solved and the same query is retried immediately, session warmth intact.

    python tools/serp_attended.py --run last
    python tools/serp_attended.py --run guntur-ap_dermatology_both_2026-08-19 --max 5
    python tools/serp_attended.py --geo guntur-ap --specialty dermatology --threshold 100

Exit codes (so a wrapper can tell the three real outcomes apart):
    0  every query captured
    10 stopped with queries still pending (unsolved wall, or --max reached)
    2  refused before touching the browser (bad arguments, finalized run, query-set drift)
    1  unexpected failure

Never solves a CAPTCHA. The only thing that clears a wall here is a person.
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


class AttendedSession:
    """Holds the one piece of state the collector callbacks must share: did we give up?

    Once the operator has failed to answer a wall, every later callback must become a no-op —
    otherwise the collector's retry loop re-notifies and re-waits on the same query, and the
    operator gets beeped at repeatedly for a wall nobody is going to clear.
    """

    def __init__(self, handle, args):
        self.handle = handle
        self.args = args
        self.gave_up = False
        self.driver = None
        self.blocks_seen = 0
        self.solves = 0
        self.attempted = 0
        self.captured_at_start = S.status_counts(handle.run_dir, handle.qrows)["captured"]
        self.started = time.monotonic()

    # ---- collector callbacks -------------------------------------------------
    def pace(self) -> None:
        time.sleep(random.uniform(self.args.pace_min, self.args.pace_max))

    def breather(self) -> None:
        if self.args.breather <= 0:
            return
        print(f"   breather {self.args.breather:.0f}s …", flush=True)
        time.sleep(self.args.breather)

    def sleep(self, seconds: float) -> None:
        """The collector's post-decline backoff. Pointless once we have given up — skip it."""
        if self.gave_up:
            return
        time.sleep(seconds)

    def progress(self, i: int, n: int, query: str) -> None:
        S.heartbeat(self.handle.run_dir, query_done=True)
        st = S.status_counts(self.handle.run_dir, self.handle.qrows)
        elapsed = time.monotonic() - self.started
        print(f"[{i:>3}/{n}] captured={st['captured']:<3} pending={st['n_pending']:<3} "
              f"{S.human_duration(elapsed):>8}  {query[:52]}", flush=True)

    def wait_for_clear(self, minutes: float) -> bool:
        """Wait for the wall to come down. Returns True the moment it does.

        Watches TWO signals, and either one is enough:

        * the page itself — polled every few seconds, costing no Google request because it
          reads the DOM already loaded. The instant the CAPTCHA is solved the block markers
          disappear and the run continues, without the operator touching this console;
        * the ENTER key, for an operator who would rather say so explicitly.

        Nothing here solves a CAPTCHA. It only notices that a human already did — the
        difference between watching a door and picking a lock.

        The clock is paused for the whole wait and banked, so a wall that stood for ten minutes
        does not make the run look ten minutes slower. A heartbeat still goes out each poll so
        the page reads `blocked` rather than decaying into `stalled`.
        """
        deadline = time.monotonic() + max(0.0, minutes) * 60
        try:
            import msvcrt
        except ImportError:                                   # pragma: no cover - POSIX
            msvcrt = None
        if msvcrt is not None:                                # drop keys queued before the wall
            try:
                while msvcrt.kbhit():
                    msvcrt.getwch()
            except Exception:
                pass

        last_note = 0.0
        while time.monotonic() < deadline:
            # Optional capability: the SerpDriver contract does not require it, so a driver
            # that cannot report block state simply leaves the ENTER key as the only signal.
            probe = getattr(self.driver, "is_blocked", None)
            if callable(probe):
                blocked = probe()
                if blocked is False:                          # not None — None means unknown
                    print("   wall cleared — detected automatically, resuming.", flush=True)
                    return True
            if msvcrt is not None:
                try:
                    while msvcrt.kbhit():
                        if msvcrt.getwch() in ("\r", "\n"):
                            print("   thanks — resuming.", flush=True)
                            return True
                except Exception:
                    pass
            S.heartbeat(self.handle.run_dir)
            remaining = deadline - time.monotonic()
            if time.monotonic() - last_note > 20:
                last_note = time.monotonic()
                print(f"   waiting for the CAPTCHA to be solved… "
                      f"({S.human_duration(remaining)} left; solving it in Chrome is enough, "
                      f"ENTER also works)", flush=True)
            time.sleep(3.0)
        return False

    def pause(self, info: dict) -> bool:
        """Google put up a wall. Get a human, or decide nobody is coming."""
        if self.gave_up:
            return False
        self.blocks_seen += 1
        rank, query = info.get("rank"), info.get("query", "")
        kind = serp_collector.block_kind(info.get("reason"))

        if kind == serp_collector.BLOCK_DENIED:
            # A 403 is not a CAPTCHA. There is no puzzle on the page, so waiting for a human
            # would burn the whole --wait window on something nobody can clear from a keyboard.
            # Say so, stop, and let the session end — the profile or the IP needs a rest, not
            # an operator.
            S.write_flag(self.handle.run_dir, BLOCK_FLAG,
                         f"HARD BLOCK (HTTP 403) at q{rank}: {query}\n"
                         f"Google refused the request outright — no CAPTCHA to solve.\n"
                         f"Let the session rest before resuming; there is nothing to click.")
            S.wall_alert(self.handle.run_id, rank, f"[403 hard block] {query}",
                         topic=self.args.ntfy_topic, sound=not self.args.no_sound,
                         toast=not self.args.no_toast, mobile=not self.args.no_mobile)
            print("   HTTP 403 — Google refused outright. No CAPTCHA to solve; stopping so "
                  "the session can rest.", flush=True)
            self.gave_up = True
            return False
        S.safe_update_manifest(self.handle.run_dir, awaiting_human=True, awaiting_query=info)
        S.write_flag(self.handle.run_dir, BLOCK_FLAG,
                     f"blocked at q{rank}: {query}\nreason: {info.get('reason')}\n"
                     f"url: {info.get('url')}\nSolve the CAPTCHA in the open Chrome window.")
        sent = S.wall_alert(self.handle.run_id, rank, query,
                            topic=self.args.ntfy_topic,
                            sound=not self.args.no_sound,
                            toast=not self.args.no_toast,
                            mobile=not self.args.no_mobile)
        if not sent["mobile"]:
            print("   (no phone alert — set NTFY_TOPIC in .env or pass --ntfy-topic)",
                  flush=True)

        if not callable(getattr(self.driver, "is_blocked", None))                 and not S.operator_available():
            # Nothing to watch and nobody to ask.
            print("   no console and no browser to watch — recording the block.", flush=True)
            self.gave_up = True
            return False

        S.begin_block(self.handle.run_dir)      # stop the clock; the wait is not scrape time
        try:
            solved = self.wait_for_clear(self.args.wait)
        except KeyboardInterrupt:
            # The prompt offers Ctrl-C as "give up". Taking that offer must record the wall
            # exactly as a timeout does — otherwise the session reads as merely 'interrupted',
            # the walled query is left with no status at all, and the sticky note that tells
            # the next operator a wall is waiting never gets written.
            print("\n   giving up on this wall — recording it and stopping.", flush=True)
            self.gave_up = True
            return False
        S.end_block(self.handle.run_dir)        # bank the wait, restart the clock
        if solved:
            self.solves += 1
            print(f"   retrying q{rank}.", flush=True)
            S.clear_flag(self.handle.run_dir, BLOCK_FLAG)
            S.safe_update_manifest(self.handle.run_dir, awaiting_human=False)
            return True

        print(f"   nobody answered within {self.args.wait} min — recording the block "
              f"and stopping cleanly. Re-run to resume.", flush=True)
        self.gave_up = True
        return False

    def stop(self, info: dict) -> bool:
        """End the session: after an unsolved wall, or once --max queries have been tried."""
        self.attempted = info.get("attempted", self.attempted)
        if self.gave_up:
            return True
        if self.args.max and self.attempted >= self.args.max:
            print(f"   --max {self.args.max} reached — stopping.", flush=True)
            return True
        return False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Attended Google SERP capture — beeps for a human on CAPTCHA (Option B)")
    p.add_argument("--run", metavar="RUN_ID", help="attach to a snapshot; 'last' = newest open run")
    p.add_argument("--geo", "--geography", dest="geo", help="geography pack, e.g. guntur-ap")
    p.add_argument("--specialty", help="specialty pack, e.g. dermatology")
    p.add_argument("--subject", default="both", choices=list(packs.SUBJECT_TYPES))
    p.add_argument("--threshold", type=int, default=None, help="query count (default: pack)")
    p.add_argument("--date", default=None, help="snapshot date YYYY-MM-DD (default: today)")
    p.add_argument("--notes", default="", help="free text stored in the manifest")
    p.add_argument("--max", type=int, default=0,
                   help="stop after N queries this session (0 = until done or blocked)")
    p.add_argument("--wait", type=float, default=15.0,
                   help="minutes to wait for a human on each CAPTCHA (default 15)")
    p.add_argument("--retries", type=int, default=5,
                   help="how many times one query may be re-solved before giving up")
    p.add_argument("--pace-min", type=float, default=5.0, dest="pace_min")
    p.add_argument("--pace-max", type=float, default=15.0, dest="pace_max")
    p.add_argument("--breather", type=float, default=75.0,
                   help="seconds of extra rest every --breather-every queries (0 = off)")
    p.add_argument("--breather-every", type=int, default=10, dest="breather_every")
    p.add_argument("--no-sound", action="store_true", help="do not sound the wall alarm")
    p.add_argument("--no-mobile", action="store_true", dest="no_mobile",
                   help="do not push a phone alert")
    p.add_argument("--ntfy-topic", default="", dest="ntfy_topic",
                   help="ntfy.sh topic for phone alerts (default: NTFY_TOPIC from .env)")
    p.add_argument("--no-toast", action="store_true", help="do not raise a Windows balloon")
    p.add_argument("--no-report", action="store_true", help="skip the HTML report at the end")
    return p


def _validate(args) -> None:
    if args.pace_min < 0 or args.pace_max < args.pace_min:
        raise S.SessionRefused("--pace-min must be >= 0 and <= --pace-max")
    if args.retries < 1:
        raise S.SessionRefused("--retries must be at least 1, or a wall can never be solved")
    if args.max < 0:
        raise S.SessionRefused("--max cannot be negative")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _validate(args)
        handle = S.resolve(args, root=config.RUNS_DIR)
        S.ensure_fingerprint(handle.run_dir, handle.qrows)
    except (S.SessionRefused, packs.PackNotFound, packs.InvalidPack) as exc:
        print(f"refused: {exc}")
        return 2

    st = S.status_counts(handle.run_dir, handle.qrows)
    S.print_header(handle, "ATTENDED SERP CAPTURE  (Option B — notify on block)",
                   {"wait": f"{args.wait:g} min per CAPTCHA",
                    "cap": f"{args.max} queries" if args.max else "until done or blocked"})
    if not st["n_pending"]:
        print("nothing pending — every query in this run is already captured.")
        S.publish_web_signal(handle.run_dir, handle.qrows)
        if not args.no_report:
            print(f"report: {serp_report.build_report(handle.run_dir)}")
        return 0

    session = AttendedSession(handle, args)
    S.clear_flag(handle.run_dir, BLOCK_FLAG)
    lock = S.SessionLock(mode="attended", run_id=handle.run_id)
    try:
        lock.acquire()
    except S.SessionRefused as exc:
        print(f"refused: {exc}")
        return 2

    driver = None
    started_at = S.now_iso()
    interrupted = failed = False
    S.begin_session(handle.run_dir, "attended", handle.run_id)

    try:
        driver = S.build_driver(handle.ctx)
        session.driver = driver
        serp_collector.collect_serps(
            handle.qrows, driver, run_dir=handle.run_dir,
            progress_cb=session.progress, pause_cb=session.pause, stop_cb=session.stop,
            pace=session.pace, sleep=session.sleep,
            breather=session.breather if args.breather > 0 else None,
            breather_every=args.breather_every,
            max_block_retries=args.retries)
    except KeyboardInterrupt:
        interrupted = True
        print("\ninterrupted — every completed query is already on disk.", flush=True)
    except Exception as exc:
        failed = True
        print(f"\nsession failed: {type(exc).__name__}: {exc}", flush=True)
    finally:
        # collect_serps stops the driver on its normal path; this covers the abort paths.
        # NodriverSerpDriver.stop() is idempotent, so calling it twice is safe.
        try:
            if driver is not None:
                driver.stop()
        except Exception as exc:
            print(f"   (browser shutdown: {type(exc).__name__}: {exc})", flush=True)
        # Reconcile whatever DID land, even after an interrupt — collect_serps' own finalize()
        # is skipped when the exception unwinds past it.
        try:
            serp_collector.finalize(handle.run_dir, handle.qrows)
        except Exception as exc:
            print(f"   (finalize: {type(exc).__name__}: {exc})", flush=True)
        S.end_session(handle.run_dir)     # the clock stops on EVERY exit path
        lock.release()

    code = _report(handle, session, args, started_at, interrupted)
    return 1 if failed else code


def _report(handle, session, args, started_at, interrupted) -> int:
    summary = S.publish_web_signal(handle.run_dir, handle.qrows)
    st = S.status_counts(handle.run_dir, handle.qrows)
    gained = st["captured"] - session.captured_at_start
    elapsed = time.monotonic() - session.started
    outcome = ("interrupted" if interrupted else
               "blocked" if session.gave_up else
               "capped" if (args.max and session.attempted >= args.max) else
               "complete" if not st["n_pending"] else "stopped")

    S.record_session(handle.run_dir, mode="attended", outcome=outcome,
                     started_at=started_at, ended_at=S.now_iso(),
                     attempted=session.attempted, captured=gained,
                     blocked=session.blocks_seen, solves=session.solves,
                     elapsed_s=round(elapsed))
    if session.gave_up:
        S.write_flag(handle.run_dir, BLOCK_FLAG,
                     "session ended on an unsolved CAPTCHA. Re-run to resume.")
    else:
        S.clear_flag(handle.run_dir, BLOCK_FLAG)
        S.safe_update_manifest(handle.run_dir, awaiting_human=False)
        if gained:
            # A human just drove this session to completion, so any cooldown the batch runner
            # parked behind — most likely "after a wall" for a wall that has now demonstrably
            # been cleared — is stale. Leaving it would keep scheduled batches exiting early
            # for hours, still citing a wall nobody is behind any more.
            S.clear_cooldown(handle.run_dir)

    print("-" * 72)
    print(f" outcome    : {outcome}")
    print(f" this session: {session.attempted} attempted, {gained} newly captured, "
          f"{session.blocks_seen} wall(s), {session.solves} solved, "
          f"{S.human_duration(elapsed)}")
    print(f" run total  : {st['captured']}/{st['total']} captured "
          f"({summary['yield']*100:.0f}%)  web_signal={summary['web_signal']}")
    if st["n_pending"]:
        print(f" pending    : {st['n_pending']} — re-run to resume "
              f"(`--run {handle.run_id}`)")
    for label, key in (("blocked", serp_collector.STATUS_BLOCKED),
                       ("anomalies", serp_collector.STATUS_ANOMALY),
                       ("errors", serp_collector.STATUS_ERROR)):
        if st["counts"][key]:
            print(f" {label:11s}: {st['counts'][key]}")
    if not args.no_report:
        try:
            print(f" report     : {serp_report.build_report(handle.run_dir)}")
        except Exception as exc:
            print(f" report     : failed ({type(exc).__name__}: {exc})")
    print("=" * 72, flush=True)
    return 0 if not st["n_pending"] else 10


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\naborted.")
        raise SystemExit(130)
