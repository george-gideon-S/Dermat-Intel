"""Shared machinery for the two unattended SERP runners.

`tools/serp_batch.py` (Option A, scheduler-driven batches) and `tools/serp_attended.py`
(Option B, notify-on-block) drive the same proven collector over the same snapshot. They
differ only in what happens when Google puts up a wall. Everything they agree on lives here:
attaching to a run, guarding the query set against drift, the operator notification, the
runner's own state file, and reading progress back out of the fetch log.

Three measured facts from the 2026-08-19 100-query proof run shape this module:

* Google challenges this residential IP roughly every ~40 sustained queries. The clean
  stretches ran 1->40 and 42->82 at a median 20 s per query.
* Once flagged, the wall stands until a human clears it — the q41 block held for 110 minutes
  and ended only because someone solved it. Continuing to fetch while flagged costs a page
  load per query and returns nothing, so both runners stop rather than grind.
* Every capture is checkpointed per query, so stopping is free: a resumed session re-fetches
  only what is not already terminal.

Nothing here solves a CAPTCHA. The human-solve path is the only path.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")

from modules import atomicio, packs, runstore, serp_collector

STATE_NAME = "runner_state.json"

#: Session cap. Measured challenge threshold is ~40 sustained queries; 30 leaves headroom for
#: the extra interactions each SERP will carry once the Step-2 fields land (AI-overview
#: expansion, "More places", ad settle) without re-measuring the threshold from scratch.
DEFAULT_BATCH = 30


class SessionRefused(Exception):
    """The runner will not start. Carries a human-readable reason; never a stack trace."""


# ------------------------------------------------------------------ run attachment
@dataclass
class RunHandle:
    run_id: str
    run_dir: str
    ctx: object
    qrows: list = field(default_factory=list)
    manifest: dict = field(default_factory=dict)
    created: bool = False


def query_rows_path(run_dir) -> Path:
    return Path(run_dir) / ".cache" / "query_rows.json"


def query_fingerprint(qrows: list) -> str:
    """Identity of a query set, as (rank, query) pairs.

    The fetch log is keyed by RANK, so a rebuilt query set that assigns rank 41 to a different
    phrase would inherit rank 41's 'parsed' status and silently mis-attribute a captured SERP
    to a query that was never run. Every session verifies this before fetching anything.
    """
    payload = json.dumps(
        [[int(r.get("rank") or 0), (r.get("search_query") or "").strip()] for r in qrows],
        ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_query_rows(run_dir) -> list:
    rows = atomicio.read_json(query_rows_path(run_dir), default=None)
    return rows if isinstance(rows, list) else []


def attach(root: Optional[str], run_id: str) -> RunHandle:
    """Attach to an existing snapshot. Refuses anything that would corrupt a resume."""
    path = runstore.run_path(root or config.RUNS_DIR, run_id)
    manifest = runstore.read_manifest(path)
    if not manifest:
        raise SessionRefused(f"no run {run_id!r} under {root or config.RUNS_DIR}")
    if manifest.get("status") == "complete":
        raise SessionRefused(
            f"{run_id} is finalized — snapshots are immutable. Start a new run instead.")
    qrows = load_query_rows(path)
    if not qrows:
        raise SessionRefused(
            f"{run_id} has no .cache/query_rows.json. Its query set is unknown, and rebuilding "
            f"one now could re-number ranks that the fetch log already records as captured.")
    ctx = packs.load(manifest["geography"], manifest["practice"],
                     manifest.get("subject_type", "both"), manifest.get("query_threshold"))
    return RunHandle(run_id=run_id, run_dir=str(path), ctx=ctx, qrows=qrows, manifest=manifest)


def create(root: Optional[str], geography: str, specialty: str, subject_type: str = "both",
           query_threshold: Optional[int] = None, run_date: Optional[str] = None,
           notes: str = "") -> RunHandle:
    """Create a snapshot and build its query set. SERP-only: no Maps, no scoring."""
    from modules import query_builder, storage

    ctx = packs.load(geography, specialty, subject_type, query_threshold)
    run = runstore.create_run(root=root or config.RUNS_DIR, geography=geography,
                              practice=specialty, subject_type=subject_type,
                              run_date=run_date, query_threshold=ctx.query_threshold,
                              packs=ctx.as_manifest(), notes=notes)
    runstore.activate(run.path)          # storage.QUERIES_JSON now resolves inside the run
    try:
        qrows, _report = query_builder.build_with_report(ctx)
        storage.save_rows(storage.QUERIES_JSON, qrows)
        if not qrows:
            raise SessionRefused("query builder produced no queries — check the specialty pack")
    except query_builder.QuerySetInvalid as exc:
        # A misconfigured threshold or a thin pack is an operator mistake, not a crash: it
        # should read as `refused: …` and exit 2 like every other bad argument, rather than
        # ending the command in a traceback.
        _discard_run(root or config.RUNS_DIR, run)
        raise SessionRefused(f"query set could not be built: {exc}") from exc
    except BaseException:
        # The run directory and its index row exist before the query set does. Leaving a
        # query-less run behind would make it the newest open run, so `--run last` would
        # resolve to a snapshot that attach() then refuses — the failure would outlive the
        # command that caused it.
        _discard_run(root or config.RUNS_DIR, run)
        raise
    finally:
        runstore.deactivate()
    return RunHandle(run_id=run.run_id, run_dir=str(run.path), ctx=ctx, qrows=qrows,
                     manifest=runstore.read_manifest(run.path), created=True)


def _discard_run(root, run) -> None:
    """Remove a run that never got a query set, and its index row. Best-effort."""
    import shutil
    try:
        shutil.rmtree(run.path, ignore_errors=True)
    except Exception:
        pass
    try:
        idx_path = runstore.index_path(root)
        idx = atomicio.read_json(idx_path, default={"runs": []}) or {"runs": []}
        idx["runs"] = [r for r in idx.get("runs", []) if r.get("run_id") != run.run_id]
        atomicio.write_json(idx_path, idx, indent=2)
    except Exception:
        pass


def resolve(args, root: Optional[str] = None) -> RunHandle:
    """`--run RUN_ID` attaches; `--geo/--specialty` creates. Latest-run shorthand: `--run last`."""
    root = root or config.RUNS_DIR
    run_id = getattr(args, "run", None)
    if run_id:
        if run_id == "last":
            open_runs = [r for r in runstore.list_runs(root) if r.get("status") != "complete"]
            if not open_runs:
                raise SessionRefused("no unfinalized run to resume (`--run last`)")
            run_id = open_runs[0]["run_id"]
        return attach(root, run_id)
    if getattr(args, "geo", None) and getattr(args, "specialty", None):
        return create(root, args.geo, args.specialty, args.subject,
                      getattr(args, "threshold", None), getattr(args, "date", None),
                      notes=getattr(args, "notes", "") or "")
    raise SessionRefused("give either --run RUN_ID (or --run last) or --geo + --specialty")


# ------------------------------------------------------------------ runner state
def state_path(run_dir) -> Path:
    return serp_collector.serp_dir(run_dir) / STATE_NAME


def read_state(run_dir) -> dict:
    return atomicio.read_json(state_path(run_dir), default={}) or {}


def write_state(run_dir, state: dict) -> None:
    atomicio.write_json(state_path(run_dir), state, indent=2)


def ensure_fingerprint(run_dir, qrows: list) -> str:
    """Record the query-set identity on first use; refuse to run against a changed one."""
    fp = query_fingerprint(qrows)
    state = read_state(run_dir)
    known = state.get("query_fingerprint")
    if known and known != fp:
        raise SessionRefused(
            "the query set changed since this run started (fingerprint "
            f"{known} -> {fp}). The fetch log is keyed by rank, so continuing would attribute "
            "already-captured SERPs to different queries. Start a new run instead.")
    if not known:
        state["query_fingerprint"] = fp
        state.setdefault("created_at", now_iso())
        write_state(run_dir, state)
    return fp


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def record_session(run_dir, **fields) -> dict:
    """Append one session to the state file's history and update the top-level markers."""
    state = read_state(run_dir)
    sessions = list(state.get("sessions") or [])
    sessions.append({"n": len(sessions) + 1, **fields})
    state["sessions"] = sessions[-50:]          # bounded: a state file is not a log
    state["last_session_at"] = fields.get("ended_at") or now_iso()
    state["last_outcome"] = fields.get("outcome")
    if fields.get("blocked"):
        state["blocks_seen"] = int(state.get("blocks_seen") or 0) + int(fields["blocked"])
        state["last_block_at"] = fields.get("ended_at") or now_iso()
    write_state(run_dir, state)
    return state


def set_cooldown(run_dir, minutes: float, reason: str = "") -> str:
    """Park the next session until `minutes` from now. Returns the ISO deadline."""
    until = (datetime.now() + timedelta(minutes=float(minutes))).isoformat(timespec="seconds")
    state = read_state(run_dir)
    state["next_earliest"] = until
    state["cooldown_reason"] = reason
    state["cooldown_minutes"] = round(float(minutes), 1)
    write_state(run_dir, state)
    return until


def cooldown_remaining(run_dir) -> float:
    """Seconds still to wait before another session is allowed. <= 0 means go."""
    until = read_state(run_dir).get("next_earliest")
    if not until:
        return 0.0
    try:
        return (datetime.fromisoformat(until) - datetime.now()).total_seconds()
    except (TypeError, ValueError):
        return 0.0        # an unparseable marker must not wedge the run forever


def clear_cooldown(run_dir) -> None:
    state = read_state(run_dir)
    for key in ("next_earliest", "cooldown_reason", "cooldown_minutes"):
        state.pop(key, None)
    write_state(run_dir, state)


# ------------------------------------------------------------------ single-session lock
def lock_path() -> Path:
    """Guards the BROWSER PROFILE, not the run.

    The profile at .browser/serp_profile/ is deliberately shared across every run — its warmed
    cookie state is what keeps the scraper unblocked. That makes it the resource two runners
    actually collide over: a second Chrome pointed at a user-data-dir already in use either
    refuses to start or corrupts the profile, and the corrupted profile is the expensive half,
    since rebuilding it re-pays the cold-start CAPTCHA tax. So the lock is global.
    """
    return Path(config.BROWSER_DIR) / "serp_session.lock"


def _pid_alive(pid: int) -> bool:
    """Best-effort liveness check. Unsure -> True, so a stale lock is never assumed."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION, STILL_ACTIVE = 0x1000, 259
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return code.value == STILL_ACTIVE
                return True
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return True


#: The session held by THIS process, if any. A pid check alone cannot see a second session
#: inside one interpreter — it would compare our own pid against itself and let it through.
_LOCAL_HOLDER: Optional["SessionLock"] = None


class SessionLock:
    """Refuse to start a second scraping session on this machine.

    Not a security boundary — a cooperative guard against the specific accident of leaving the
    attended runner open while a scheduled batch fires. A lock left behind by a crashed process
    is detected as stale and taken over, so a crash never wedges the pipeline.
    """

    def __init__(self, mode: str = "serp", run_id: str = ""):
        self.mode, self.run_id = mode, run_id
        self.path = lock_path()
        self.held = False

    def acquire(self) -> None:
        global _LOCAL_HOLDER
        if _LOCAL_HOLDER is not None and _LOCAL_HOLDER is not self:
            raise SessionRefused(
                f"a SERP session is already running in this process "
                f"({_LOCAL_HOLDER.mode} on {_LOCAL_HOLDER.run_id})")
        holder = atomicio.read_json(self.path, default=None)
        if isinstance(holder, dict):
            pid = int(holder.get("pid") or 0)
            if pid and pid != os.getpid() and _pid_alive(pid):
                raise SessionRefused(
                    f"another SERP session is already running (pid {pid}, "
                    f"{holder.get('mode')} on {holder.get('run_id')}, started "
                    f"{holder.get('started_at')}). Two sessions share one Chrome profile and "
                    f"would corrupt it. Wait for it, or stop it first.")
            if pid:
                print(f"   (taking over a stale lock from pid {pid})", flush=True)
        atomicio.write_json(self.path, {"pid": os.getpid(), "mode": self.mode,
                                        "run_id": self.run_id, "started_at": now_iso()})
        self.held = True
        _LOCAL_HOLDER = self

    def release(self) -> None:
        global _LOCAL_HOLDER
        if not self.held:
            return
        self.held = False
        if _LOCAL_HOLDER is self:
            _LOCAL_HOLDER = None
        holder = atomicio.read_json(self.path, default=None)
        if isinstance(holder, dict) and int(holder.get("pid") or 0) != os.getpid():
            return                      # someone else took over; not ours to delete
        try:
            self.path.unlink()
        except (OSError, FileNotFoundError):
            pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()
        return False


# ------------------------------------------------------------------ run timer
#: A session with no heartbeat for this long is not working, whatever its lock says.
STALL_AFTER_S = 240


def _session_elapsed(active: dict, until=None) -> float:
    """Scraping seconds this session contributed: wall-clock minus banked wall time."""
    started = _parse(active.get("started_at"))
    if not started:
        return 0.0
    end = until or _parse(active.get("ended_at")) or _parse(active.get("last_beat")) or started
    return max(0.0, (end - started).total_seconds() - float(active.get("paused_s") or 0.0))


def begin_session(run_dir, mode: str, run_id: str = "") -> None:
    """Start the clock for THIS session, without resetting the RUN's clock.

    Banks any previous session that never got to stop itself — a killed runner leaves `active`
    behind, and overwriting it here would silently discard the time it earned.
    """
    state = read_state(run_dir)
    orphan = state.get("active")
    if orphan:
        state["run_elapsed_s"] = round(
            float(state.get("run_elapsed_s") or 0.0) + _session_elapsed(orphan), 1)
        orphan["ended_at"] = orphan.get("last_beat") or now_iso()
        state["last_active"] = orphan
    state["active"] = {"mode": mode, "run_id": run_id, "pid": os.getpid(),
                       "started_at": now_iso(), "last_beat": now_iso(),
                       "queries": 0, "paused_s": 0.0}
    write_state(run_dir, state)


def heartbeat(run_dir, query_done: bool = False) -> None:
    """Mark forward progress. Without these the clock reads 'stalled' even while the process
    is alive — a wedged browser holds its lock perfectly well.

    `query_done` is what separates a captured query from a liveness ping. The waiting loop
    beats every few seconds to prove it is alive; counting those as queries reported 117
    against a run that had captured 42.
    """
    state = read_state(run_dir)
    active = state.get("active")
    if not active:
        return
    active["last_beat"] = now_iso()
    if query_done:
        active["queries"] = int(active.get("queries") or 0) + 1
    write_state(run_dir, state)


def end_session(run_dir) -> None:
    """Stop the clock. Called on every exit path — clean, blocked, interrupted or failed."""
    state = read_state(run_dir)
    active = state.pop("active", None)
    if active:
        active["ended_at"] = now_iso()
        state["run_elapsed_s"] = round(
            float(state.get("run_elapsed_s") or 0.0) + _session_elapsed(active), 1)
        state["last_active"] = active
    write_state(run_dir, state)


def begin_block(run_dir) -> None:
    """A wall went up. Stop the clock — the wait is not scraping time."""
    state = read_state(run_dir)
    active = state.get("active")
    if not active or active.get("blocked_since"):
        return
    active["blocked_since"] = now_iso()
    write_state(run_dir, state)


def end_block(run_dir) -> None:
    """The wall cleared. Bank the wait and let the clock run again."""
    state = read_state(run_dir)
    active = state.get("active")
    if not active or not active.get("blocked_since"):
        return
    started = _parse(active.pop("blocked_since"))
    if started:
        waited = max(0.0, (datetime.now() - started).total_seconds())
        active["paused_s"] = round(float(active.get("paused_s") or 0.0) + waited, 1)
        state["walls_cleared"] = int(state.get("walls_cleared") or 0) + 1
    active["last_beat"] = now_iso()
    write_state(run_dir, state)


def _parse(ts):
    try:
        return datetime.fromisoformat(ts) if ts else None
    except (TypeError, ValueError):
        return None


def timer_state(run_dir) -> dict:
    """What the clock should read, and whether it is still ticking.

    The clock belongs to the RUN, not to one session. Resuming a run used to restart it at
    zero, so a run 40 queries deep reported a few seconds. Finished sessions are banked in
    `run_elapsed_s` and the live session adds to that total.

    Time behind a CAPTCHA is banked separately and never counted: the clock measures scraping,
    so a wall that stood ten minutes must not make the run look ten minutes slower.

    Five states, and the page must tell them apart: running, blocked (waiting on a human),
    idle, stalled (alive but not progressing) and died (process gone, clock never stopped).
    """
    state = read_state(run_dir)
    banked = float(state.get("run_elapsed_s") or 0.0)
    active = state.get("active")
    finished = state.get("last_active") or {}

    if not active:
        return {"running": False, "status": "idle",
                "started_at": finished.get("started_at"), "ended_at": finished.get("ended_at"),
                "elapsed_s": max(0.0, banked), "session_s": _session_elapsed(finished),
                "paused_s": float(finished.get("paused_s") or 0.0),
                "walls_cleared": int(state.get("walls_cleared") or 0),
                "queries": finished.get("queries", 0)}

    started, beat = _parse(active.get("started_at")), _parse(active.get("last_beat"))
    blocked_since = _parse(active.get("blocked_since"))
    alive = _pid_alive(int(active.get("pid") or 0))
    since_beat = (datetime.now() - beat).total_seconds() if beat else 0.0

    if not alive:
        status = "died"
    elif blocked_since:
        status = "blocked"
    elif since_beat > STALL_AFTER_S:
        status = "stalled"
    else:
        status = "running"

    # The clock only advances while work is actually happening.
    until = (datetime.now() if status == "running"
             else blocked_since if status == "blocked"
             else beat or started)
    session_s = _session_elapsed(active, until=until)
    return {"running": status == "running", "status": status,
            "started_at": active.get("started_at"), "last_beat": active.get("last_beat"),
            "blocked_since": active.get("blocked_since"), "ended_at": None,
            "elapsed_s": max(0.0, banked + session_s), "session_s": session_s,
            "paused_s": float(active.get("paused_s") or 0.0),
            "walls_cleared": int(state.get("walls_cleared") or 0),
            "seconds_since_beat": round(since_beat), "queries": active.get("queries", 0)}


# ------------------------------------------------------------------ progress
def status_counts(run_dir, qrows: list) -> dict:
    """Per-status counts over the FULL query set, plus what is still outstanding."""
    log = serp_collector.read_fetch_log(run_dir)
    counts = {s: 0 for s in (serp_collector.STATUS_PARSED, serp_collector.STATUS_ZERO,
                             serp_collector.STATUS_BLOCKED, serp_collector.STATUS_ANOMALY,
                             serp_collector.STATUS_ERROR)}
    pending = []
    for q in qrows:
        st = log.get(str(q.get("rank")), {}).get("status")
        if st in counts:
            counts[st] += 1
        if st not in serp_collector.TERMINAL_OK:
            pending.append(q)
    captured = counts[serp_collector.STATUS_PARSED] + counts[serp_collector.STATUS_ZERO]
    return {"counts": counts, "captured": captured, "total": len(qrows),
            "pending": pending, "n_pending": len(pending),
            "yield": captured / max(len(qrows), 1)}


def human_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return (f"{h}h " if h else "") + (f"{m}m " if h or m else "") + f"{s}s"


def print_header(handle: RunHandle, title: str, extra: Optional[dict] = None) -> None:
    st = status_counts(handle.run_dir, handle.qrows)
    print("=" * 72)
    print(f" {title}")
    print("=" * 72)
    print(f" run        : {handle.run_id}")
    print(f" market     : {handle.ctx.display_name} / {handle.ctx.spec.get('name')} "
          f"/ {handle.ctx.subject_type}")
    print(f" captured   : {st['captured']}/{st['total']}   pending: {st['n_pending']}")
    for key, val in (extra or {}).items():
        print(f" {key:11s}: {val}")
    print("-" * 72, flush=True)


# ------------------------------------------------------------------ operator notification
_PS_SCRIPT = """
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Warning
$n.Visible = $true
$n.ShowBalloonTip(30000, '{title}', '{message}', [System.Windows.Forms.ToolTipIcon]::Warning)
Start-Sleep -Seconds 12
$n.Dispose()
"""


def _ps_quote(s: str) -> str:
    """Escape for a PowerShell single-quoted literal (no interpolation happens inside one)."""
    return str(s).replace("'", "''").replace("\r", " ").replace("\n", " ")[:180]


def notify(title: str, message: str, sound: bool = True, toast: bool = True) -> None:
    """Get a human's attention. Every layer is best-effort and independently guarded.

    Console first because it always works; the sound is what actually reaches someone in
    another room; the balloon is a bonus that must never be allowed to fail the run.
    """
    bar = "!" * 72
    print(f"\n{bar}\n  {title}\n  {message}\n{bar}\n", flush=True)
    if sound:
        try:
            import winsound
            for _ in range(3):
                winsound.Beep(880, 220)
                winsound.Beep(660, 220)
        except Exception:
            try:
                sys.stdout.write("\a\a\a")
                sys.stdout.flush()
            except Exception:
                pass
    if toast and os.name == "nt":
        try:
            script = _PS_SCRIPT.format(title=_ps_quote(title), message=_ps_quote(message))
            subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                 "-Command", script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            pass


#: The CAPTCHA alarm. Deliberately unlike any other sound this project makes: a two-tone
#: siren, ~2 seconds, so it is recognisable from another room without looking at the screen.
#: Everything else the runner does is silent, so this sound means exactly one thing.
ALARM_PATTERN = ((1245, 130), (932, 130)) * 4


def alarm(seconds: float = 2.0) -> None:
    """Sound the wall alarm. Best-effort: audio must never fail a capture."""
    try:
        import winsound
        played = 0.0
        while played < seconds:
            for freq, ms in ALARM_PATTERN:
                winsound.Beep(freq, ms)
                played += ms / 1000.0
                if played >= seconds:
                    break
    except Exception:
        try:
            sys.stdout.write("\a\a\a")
            sys.stdout.flush()
        except Exception:
            pass


def mobile_topic() -> str:
    """The ntfy topic to push to, or '' when the operator has not opted in.

    Mobile alerts are OFF until a topic is configured, because pushing to ntfy sends the
    message to a third-party server. Set NTFY_TOPIC in the gitignored .env (or pass
    --ntfy-topic) to turn them on.
    """
    return (os.environ.get("NTFY_TOPIC") or "").strip()


def push_mobile(title: str, message: str, topic: str = "", priority: str = "urgent") -> bool:
    """Send a phone alert via ntfy.sh. Free, no account, no API key.

    Uses curl rather than `requests` because this machine's TLS interception breaks Python's
    certificate handling while curl, on schannel and the Windows certificate store, works —
    the same reason every other outbound fetch here shells out.

    A public ntfy topic is readable by anyone who knows its name, so the message carries only
    the run id and the query number, never captured data. Best-effort throughout: a failed
    push must never interrupt a capture.
    """
    topic = (topic or mobile_topic()).strip()
    if not topic:
        return False
    url = f"https://ntfy.sh/{urllib.parse.quote(topic.lstrip('/'))}"
    try:
        subprocess.run(
            ["curl", "-fsS", "--max-time", "12",
             "-H", f"Title: {title[:120]}",
             "-H", f"Priority: {priority}",
             "-H", "Tags: rotating_light",
             "-d", message[:500], url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False


def wall_alert(run_id: str, rank, query: str, topic: str = "",
               sound: bool = True, toast: bool = True, mobile: bool = True) -> dict:
    """Everything that happens the moment Google puts up a wall.

    Three channels because they fail differently: the console is always there but only if you
    are looking, the alarm reaches the room, and the push reaches you when you are not in it.
    """
    sent = {"sound": False, "toast": False, "mobile": False}
    title = f"CAPTCHA — query {rank}"
    body = (f"Google blocked {run_id} at query {rank}. Solve it in the Chrome window; "
            f"the run resumes by itself and the clock restarts.")
    print("\n" + "!" * 72)
    print(f"  {title}")
    print(f"  {body}")
    print("!" * 72 + "\n", flush=True)
    if sound:
        alarm()
        sent["sound"] = True
    if toast and os.name == "nt":
        notify(title, body, sound=False, toast=True)
        sent["toast"] = True
    if mobile:
        sent["mobile"] = push_mobile(title, body, topic)
    return sent


def write_flag(run_dir, name: str, text: str) -> None:
    """Drop a visible marker file — how a person (or a scheduler) sees state without a console."""
    try:
        atomicio.write_text(serp_collector.serp_dir(run_dir) / name,
                            f"{now_iso()}\n{text}\n")
    except Exception:
        pass


def clear_flag(run_dir, name: str) -> None:
    try:
        (serp_collector.serp_dir(run_dir) / name).unlink()
    except (OSError, FileNotFoundError):
        pass


# ------------------------------------------------------------------ operator wait
def operator_available() -> bool:
    """Is there a console a person could actually type into?"""
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except Exception:
        return False


def wait_for_operator(timeout_s: float, poll_s: float = 0.25) -> bool:
    """Block until the operator presses Enter, or the timeout expires.

    Returns True only if a person actually responded. A scheduled run has no console, so this
    returns False immediately rather than parking a headless process for an hour.
    """
    if timeout_s <= 0 or not operator_available():
        return False
    deadline = time.monotonic() + timeout_s
    last_shown = -1
    try:
        import msvcrt
    except ImportError:
        msvcrt = None
    # Drain anything typed BEFORE the wall appeared. The post-solve retry takes ~20 s and looks
    # unresponsive, so an impatient double-tap at an earlier wall is easy; without this, that
    # stale keystroke satisfies the next wait instantly and the runner retries a wall nobody
    # has touched, burning a solve attempt and reading as though a human answered.
    if msvcrt is not None:
        try:
            while msvcrt.kbhit():
                msvcrt.getwch()
        except Exception:
            pass
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        shown = int(remaining // 15)
        if shown != last_shown:
            last_shown = shown
            print(f"   waiting for you… press ENTER when the CAPTCHA is solved "
                  f"({human_duration(remaining)} left, Ctrl-C to give up)", flush=True)
        if msvcrt is not None:
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\r", "\n"):
                    return True
            time.sleep(poll_s)
        else:  # pragma: no cover - POSIX fallback
            import select
            ready, _, _ = select.select([sys.stdin], [], [], poll_s)
            if ready:
                sys.stdin.readline()
                return True
    return False


# ------------------------------------------------------------------ collaborators
def build_driver(ctx, settle_s: float = 4.0, ads_settle_s: float = 2.5):
    """Always headful. Headless is the configuration Google blocks — see the 08-18 measurement."""
    from modules import serp_driver_nodriver
    return serp_driver_nodriver.build_driver(
        gl=getattr(ctx, "gl", "in"), hl=getattr(ctx, "hl", "en"),
        headless=False, settle_s=settle_s, ads_settle_s=ads_settle_s)


def safe_update_manifest(run_dir, **fields) -> None:
    """Manifest updates are telemetry; a finalized run must not crash a runner."""
    try:
        runstore.update_manifest(run_dir, **fields)
    except (runstore.RunFinalized, OSError):
        pass


def publish_web_signal(run_dir, qrows: list) -> dict:
    """Write the SERP dataset summary to the manifest so the yield is never inferred later."""
    summary = serp_collector.run_summary(run_dir, qrows)
    safe_update_manifest(run_dir, web_signal=summary["web_signal"],
                         serp_progress={"captured_serps": summary["captured_serps"],
                                        "total_queries": summary["total_queries"],
                                        "yield": round(summary["yield"], 4),
                                        "updated_at": now_iso()})
    return summary
