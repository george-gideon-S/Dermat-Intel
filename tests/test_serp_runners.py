"""The two unattended runners and the review page.

No network and no browser — every test drives the same FakeDriver the collector tests use.
What is pinned here is the behaviour that decides whether an unattended run is honest:

* stopping early must never shrink the dataset's denominator, or a half-finished run would
  report a flattering yield against the queries it happened to try;
* a query set that changed since the run started must be refused, because the fetch log is
  keyed by rank and would otherwise re-label captured SERPs;
* the operator must be beeped at once per wall, not once per retry;
* a cooldown must actually stop the next session, or a scheduler firing every 15 minutes
  turns straight back into the hammering that draws the wall.
"""
import json
import os
import time
import types
from pathlib import Path

import pytest

from modules import serp_collector as sc
from modules import serp_report, serp_session as S
from tools import serp_attended

from tests.test_serp_collector import (BLOCKED_PAGE, EMPTY_PAGE, ORGANIC_PAGE, FakeDriver)

QROWS = [{"rank": i, "search_query": f"query number {i} Guntur", "category": "Discovery",
          "user_intent": "find a clinic", "search_strength_score": 5} for i in range(1, 9)]


def collect(tmp_path, script=None, rows=None, **kw):
    driver = FakeDriver(script or {})
    data = sc.collect_serps(rows or QROWS, driver=driver, run_dir=tmp_path,
                            pace=lambda: None, sleep=lambda s: None, **kw)
    return driver, data


# --------------------------------------------------------------- stop_cb contract
def test_stop_cb_ends_the_session_after_the_requested_number_of_queries(tmp_path):
    seen = []

    def stop(info):
        seen.append(info["attempted"])
        return info["attempted"] >= 3

    driver, _ = collect(tmp_path, stop_cb=stop)
    assert len(driver.calls) == 3
    assert seen == [1, 2, 3]


def test_stopping_early_still_finalizes_against_the_full_query_set(tmp_path):
    """The denominator must stay the whole run, or a 3-of-8 session reads as complete."""
    _, data = collect(tmp_path, stop_cb=lambda info: info["attempted"] >= 3)
    assert data["meta"]["num_queries_expected"] == len(QROWS)
    assert data["meta"]["num_screenshots"] == 3
    assert len(data["meta"]["unmatched_queries"]) == len(QROWS) - 3

    summary = sc.run_summary(tmp_path, QROWS)
    assert summary["total_queries"] == len(QROWS)
    assert summary["captured_serps"] == 3
    assert summary["web_signal"] == "partial"


def test_stop_cb_stops_the_browser_and_leaves_the_run_resumable(tmp_path):
    driver, _ = collect(tmp_path, stop_cb=lambda info: True)
    assert driver.stopped, "an early stop must still shut the browser down"

    driver2, data = collect(tmp_path)          # resume: no stop_cb this time
    assert driver2.calls == [q["search_query"] for q in QROWS[1:]]
    assert data["meta"]["num_screenshots"] == len(QROWS)


def test_absent_stop_cb_leaves_collection_behaviour_unchanged(tmp_path):
    driver, data = collect(tmp_path)
    assert len(driver.calls) == len(QROWS)
    assert data["meta"]["num_screenshots"] == len(QROWS)


def test_stop_cb_reports_the_status_of_the_query_that_just_finished(tmp_path):
    got = {}

    def stop(info):
        got[info["rank"]] = info["status"]
        return False

    collect(tmp_path, script={QROWS[1]["search_query"]: (BLOCKED_PAGE, "https://www.google.com/sorry/index"),
                              QROWS[2]["search_query"]: EMPTY_PAGE},
            stop_cb=stop, max_block_retries=0)
    assert got[1] == sc.STATUS_PARSED
    assert got[2] == sc.STATUS_BLOCKED
    assert got[3] == sc.STATUS_ZERO


# --------------------------------------------------------------- declined-pause economics
BLOCK = (BLOCKED_PAGE, "https://www.google.com/sorry/index")
ONE_QUERY = [{"rank": 1, "search_query": "acne treatment Guntur"}]


def test_a_declined_pause_stops_retrying_however_high_the_retry_budget(tmp_path):
    """--retries buys HUMAN solve attempts, not looks at the wall.

    Each retry is a slow /sorry page load against an already-flagged session, which is the one
    thing likely to extend the flag. Before this was pinned, `--retries 5` fetched the wall six
    times after nobody answered.
    """
    for retries in (1, 5, 20):
        run = tmp_path / f"r{retries}"
        driver = FakeDriver({ONE_QUERY[0]["search_query"]: BLOCK})
        asked = []
        sc.collect_serps(ONE_QUERY, driver=driver, run_dir=run,
                         pause_cb=lambda info: asked.append(1) or False,
                         pace=lambda: None, sleep=lambda s: None,
                         max_block_retries=retries)
        assert len(driver.calls) == 2, f"retries={retries} fetched the wall {len(driver.calls)}x"
        assert len(asked) == 1, "the operator must be asked once, not once per retry"
        assert sc.read_fetch_log(run)["1"]["status"] == sc.STATUS_BLOCKED


def test_a_human_who_keeps_solving_still_gets_every_retry(tmp_path):
    """The cap on declines must not cost a present operator their solve attempts."""

    class Stubborn(FakeDriver):
        n = 0

        def fetch(self, query_text, screenshot_path=None):
            self.n += 1
            self.calls.append(query_text)
            if self.n <= 3:
                return sc.FetchResult(html=BLOCKED_PAGE, final_url=BLOCK[1])
            return sc.FetchResult(html=ORGANIC_PAGE, final_url="https://www.google.com/search")

    driver, solves = Stubborn({}), []
    sc.collect_serps(ONE_QUERY, driver=driver, run_dir=tmp_path,
                     pause_cb=lambda info: solves.append(1) or True,
                     pace=lambda: None, sleep=lambda s: None, max_block_retries=5)
    assert len(solves) == 3
    assert sc.read_fetch_log(tmp_path)["1"]["status"] == sc.STATUS_PARSED


def test_the_unattended_default_still_retries_once_for_a_transient_interstitial(tmp_path):
    """With no pause hook at all, one retry survives — a consent redirect clears on it."""
    driver = FakeDriver({ONE_QUERY[0]["search_query"]: BLOCK})
    sc.collect_serps(ONE_QUERY, driver=driver, run_dir=tmp_path,
                     pace=lambda: None, sleep=lambda s: None)
    assert len(driver.calls) == 2
    assert sc.read_fetch_log(tmp_path)["1"]["status"] == sc.STATUS_BLOCKED


# --------------------------------------------------------------- query-set guard
def test_fingerprint_is_recorded_on_first_use(tmp_path):
    fp = S.ensure_fingerprint(tmp_path, QROWS)
    assert S.read_state(tmp_path)["query_fingerprint"] == fp


def test_a_changed_query_set_is_refused_rather_than_silently_resumed(tmp_path):
    S.ensure_fingerprint(tmp_path, QROWS)
    reworded = [dict(q) for q in QROWS]
    reworded[4]["search_query"] = "something else entirely"
    with pytest.raises(S.SessionRefused) as exc:
        S.ensure_fingerprint(tmp_path, reworded)
    assert "keyed by rank" in str(exc.value)


def test_reordering_queries_changes_the_fingerprint(tmp_path):
    """Same phrases at different ranks is exactly the case that corrupts a resume."""
    swapped = [dict(q) for q in QROWS]
    swapped[0]["search_query"], swapped[1]["search_query"] = (
        swapped[1]["search_query"], swapped[0]["search_query"])
    assert S.query_fingerprint(QROWS) != S.query_fingerprint(swapped)


def test_an_unchanged_query_set_passes_repeatedly(tmp_path):
    fp = S.ensure_fingerprint(tmp_path, QROWS)
    assert S.ensure_fingerprint(tmp_path, list(QROWS)) == fp


# --------------------------------------------------------------- cooldown
def test_cooldown_blocks_the_next_session_until_it_expires(tmp_path):
    assert S.cooldown_remaining(tmp_path) <= 0
    S.set_cooldown(tmp_path, minutes=30, reason="after a clean batch")
    assert 0 < S.cooldown_remaining(tmp_path) <= 30 * 60
    S.clear_cooldown(tmp_path)
    assert S.cooldown_remaining(tmp_path) <= 0


def test_an_unparseable_cooldown_marker_does_not_wedge_the_run_forever(tmp_path):
    S.write_state(tmp_path, {"next_earliest": "not-a-timestamp"})
    assert S.cooldown_remaining(tmp_path) == 0.0


def test_session_history_accumulates_and_counts_walls(tmp_path):
    S.record_session(tmp_path, mode="batch", outcome="capped", attempted=30, captured=30,
                     blocked=0)
    S.record_session(tmp_path, mode="batch", outcome="blocked", attempted=7, captured=6,
                     blocked=1)
    state = S.read_state(tmp_path)
    assert [s["n"] for s in state["sessions"]] == [1, 2]
    assert state["blocks_seen"] == 1
    assert state["last_outcome"] == "blocked"


# --------------------------------------------------------------- single-session lock
@pytest.fixture
def lockdir(tmp_path, monkeypatch):
    """Point the machine-wide lock at a temp dir so tests never touch the real profile."""
    monkeypatch.setattr(S.config, "BROWSER_DIR", str(tmp_path / "browser"))
    monkeypatch.setattr(S, "_LOCAL_HOLDER", None)
    yield tmp_path
    S._LOCAL_HOLDER = None


def test_a_second_session_is_refused_while_one_holds_the_lock(lockdir):
    first = S.SessionLock(mode="attended", run_id="r1")
    first.acquire()
    try:
        with pytest.raises(S.SessionRefused) as exc:
            S.SessionLock(mode="batch", run_id="r2").acquire()
        assert "already running" in str(exc.value)
    finally:
        first.release()


def test_the_lock_is_released_so_the_next_session_can_start(lockdir):
    with S.SessionLock(mode="batch", run_id="r1"):
        pass
    second = S.SessionLock(mode="batch", run_id="r2")
    second.acquire()                                     # must not raise
    assert S.lock_path().exists()
    second.release()


def test_a_second_session_in_the_same_process_is_also_refused(lockdir):
    """A pid check alone compares our own pid against itself and lets it straight through."""
    first = S.SessionLock(mode="attended", run_id="r1")
    first.acquire()
    try:
        with pytest.raises(S.SessionRefused):
            S.SessionLock(mode="batch", run_id="r2").acquire()
    finally:
        first.release()


def test_a_lock_left_by_a_dead_process_is_taken_over_not_honoured(lockdir):
    """A crash must never wedge the pipeline behind a lock nobody holds."""
    from modules import atomicio
    dead_pid = 999_999_999
    atomicio.write_json(S.lock_path(), {"pid": dead_pid, "mode": "batch",
                                        "run_id": "r0", "started_at": "2026-01-01T00:00:00"})
    taken = S.SessionLock(mode="batch", run_id="r1")
    taken.acquire()                                      # must not raise
    from modules.atomicio import read_json
    assert read_json(S.lock_path())["pid"] == os.getpid()
    taken.release()


def test_releasing_a_lock_someone_else_took_over_does_not_delete_theirs(lockdir):
    from modules import atomicio
    mine = S.SessionLock(mode="batch", run_id="r1")
    mine.acquire()
    atomicio.write_json(S.lock_path(), {"pid": os.getpid() + 1, "mode": "attended",
                                        "run_id": "r2", "started_at": "now"})
    mine.release()
    assert S.lock_path().exists(), "must not delete a lock that is no longer ours"


def test_a_corrupt_lock_file_does_not_block_a_session(lockdir):
    S.lock_path().parent.mkdir(parents=True, exist_ok=True)
    S.lock_path().write_text("{ not json", encoding="utf-8")
    lock = S.SessionLock(mode="batch", run_id="r1")
    lock.acquire()                                       # must not raise
    lock.release()


def test_the_lock_guards_the_shared_browser_profile_not_one_run(lockdir):
    """Two different runs still collide: they share one Chrome profile by design."""
    assert str(S.lock_path()).startswith(str(S.config.BROWSER_DIR))
    first = S.SessionLock(mode="batch", run_id="run-a")
    first.acquire()
    with pytest.raises(S.SessionRefused):
        S.SessionLock(mode="batch", run_id="run-b").acquire()
    first.release()


# --------------------------------------------------------------- status counting
def test_status_counts_measure_against_the_whole_query_set(tmp_path):
    collect(tmp_path, stop_cb=lambda info: info["attempted"] >= 2)
    st = S.status_counts(tmp_path, QROWS)
    assert st["captured"] == 2
    assert st["total"] == len(QROWS)
    assert st["n_pending"] == len(QROWS) - 2
    assert st["yield"] == pytest.approx(2 / len(QROWS))


def test_blocked_queries_stay_pending_so_a_resume_retries_them(tmp_path):
    collect(tmp_path,
            script={QROWS[0]["search_query"]: (BLOCKED_PAGE, "https://www.google.com/sorry/i")},
            max_block_retries=0)
    st = S.status_counts(tmp_path, QROWS)
    assert st["counts"][sc.STATUS_BLOCKED] == 1
    assert QROWS[0] in st["pending"]


# --------------------------------------------------------------- attended session
def _attended(tmp_path, **overrides):
    from tools import serp_attended
    args = types.SimpleNamespace(pace_min=0, pace_max=0, breather=0, breather_every=10,
                                 wait=0.0, retries=5, max=0, no_sound=True, no_toast=True,
                                 no_report=True, no_mobile=True, ntfy_topic="")
    for k, v in overrides.items():
        setattr(args, k, v)
    handle = S.RunHandle(run_id="r", run_dir=str(tmp_path), ctx=None, qrows=QROWS)
    return serp_attended.AttendedSession(handle, args)


def test_one_wall_beeps_once_even_though_the_collector_retries(tmp_path, monkeypatch):
    """The retry loop calls pause repeatedly; the operator must not be beeped each time."""
    beeps = []
    monkeypatch.setattr(S, "wall_alert",
                        lambda *a, **k: beeps.append(a) or
                        {"sound": True, "toast": True, "mobile": True})
    monkeypatch.setattr(S, "operator_available", lambda: True)
    monkeypatch.setattr(serp_attended.AttendedSession, "wait_for_clear",
                        lambda self, minutes: False)
    session = _attended(tmp_path)

    assert session.pause({"rank": 4, "query": "q"}) is False    # nobody answered
    assert session.pause({"rank": 4, "query": "q"}) is False    # collector retries
    assert session.pause({"rank": 4, "query": "q"}) is False
    assert len(beeps) == 1
    assert session.gave_up is True


def test_a_solved_wall_retries_the_query_and_keeps_the_session_alive(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "wall_alert",
                        lambda *a, **k: {"sound": False, "toast": False,
                                         "mobile": False})
    monkeypatch.setattr(S, "operator_available", lambda: True)
    monkeypatch.setattr(serp_attended.AttendedSession, "wait_for_clear",
                        lambda self, minutes: True)
    session = _attended(tmp_path)
    assert session.pause({"rank": 4, "query": "q"}) is True
    assert session.gave_up is False
    assert session.solves == 1
    assert session.stop({"attempted": 1, "status": sc.STATUS_PARSED}) is False


def test_giving_up_skips_the_collectors_backoff_sleep(tmp_path, monkeypatch):
    """Once nobody is coming, sleeping 30s per retry only delays the honest recording."""
    slept = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    session = _attended(tmp_path)
    session.sleep(30)
    session.gave_up = True
    session.sleep(30)
    assert slept == [30]


def test_no_console_means_the_session_stops_instead_of_waiting(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "wall_alert",
                        lambda *a, **k: {"sound": False, "toast": False,
                                         "mobile": False})
    monkeypatch.setattr(S, "operator_available", lambda: False)
    session = _attended(tmp_path)
    assert session.pause({"rank": 2, "query": "q"}) is False
    assert session.gave_up is True
    assert session.stop({"attempted": 1, "status": sc.STATUS_BLOCKED}) is True



# --------------------------------------------------------------- automatic wall clearing
def test_a_solved_wall_is_detected_without_the_operator_touching_the_console(tmp_path,
                                                                             monkeypatch):
    """Solving the CAPTCHA in Chrome is enough — pressing ENTER must not be required.

    Nothing here solves the CAPTCHA. The driver reports the page it already has loaded, so
    this only NOTICES that a human cleared it.
    """
    monkeypatch.setattr(S, "wall_alert",
                        lambda *a, **k: {"sound": False, "toast": False,
                                         "mobile": False})
    monkeypatch.setattr(S, "operator_available", lambda: False)   # no console at all
    monkeypatch.setattr(time, "sleep", lambda s: None)

    class Watcher:
        def __init__(self):
            self.looks = 0

        def is_blocked(self):
            self.looks += 1
            return self.looks < 3        # a person clears it on the third look

    session = _attended(tmp_path, wait=1.0)
    session.driver = Watcher()
    assert session.pause({"rank": 4, "query": "q"}) is True
    assert session.gave_up is False
    assert session.solves == 1


def test_an_unknown_block_state_is_never_read_as_solved(tmp_path, monkeypatch):
    """A failed probe returns None. Treating that as 'cleared' would resume into the wall."""
    monkeypatch.setattr(S, "wall_alert",
                        lambda *a, **k: {"sound": False, "toast": False,
                                         "mobile": False})
    monkeypatch.setattr(S, "operator_available", lambda: False)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    session = _attended(tmp_path, wait=0.02)
    session.driver = type("Blind", (), {"is_blocked": lambda self: None})()
    assert session.pause({"rank": 4, "query": "q"}) is False
    assert session.gave_up is True


def test_a_driver_that_cannot_report_block_state_still_works(tmp_path, monkeypatch):
    """is_blocked is optional on the SerpDriver contract; its absence must not crash."""
    monkeypatch.setattr(S, "wall_alert",
                        lambda *a, **k: {"sound": False, "toast": False,
                                         "mobile": False})
    monkeypatch.setattr(S, "operator_available", lambda: False)
    session = _attended(tmp_path, wait=0.01)
    session.driver = object()                 # no is_blocked at all
    assert session.pause({"rank": 2, "query": "q"}) is False
    assert session.gave_up is True


def test_time_behind_a_wall_is_banked_not_counted_as_scraping(tmp_path):
    """A wall that stood ten minutes must not make the run look ten minutes slower."""
    S.begin_session(tmp_path, "attended", "r")
    S.heartbeat(tmp_path)
    S.begin_block(tmp_path)
    assert S.timer_state(tmp_path)["status"] == "blocked"
    S.end_block(tmp_path)
    t = S.timer_state(tmp_path)
    assert t["status"] == "running", "the clock restarts the moment the wall clears"
    assert t["walls_cleared"] == 1
    assert t["paused_s"] >= 0

def test_max_caps_the_attended_session(tmp_path):
    session = _attended(tmp_path, max=3)
    assert session.stop({"attempted": 2, "status": sc.STATUS_PARSED}) is False
    assert session.stop({"attempted": 3, "status": sc.STATUS_PARSED}) is True




# --------------------------------------------------------------- HTTP 403 hard block
FORBIDDEN = ("<html><head><title>Error 403 (Forbidden)!!1</title></head><body>"
             "<p><b>403.</b> <ins>That\u2019s an error.</ins></p><p>Your client does not have "
             "permission to get URL <code>/search?q=x&amp;gl=in</code> from this server. "
             "<ins>That\u2019s all we know.</ins></p></body></html>")


def test_a_403_is_a_block_not_a_parse_anomaly():
    """It renders no results scaffolding, so it used to be filed as a parser problem.

    Four queries in a live run were recorded that way — a wall reported as bad parsing.
    """
    assert sc.detect_block(FORBIDDEN, "https://www.google.com/search?q=x") == "http:403"
    status, detail = sc.classify(FORBIDDEN, "https://www.google.com/search?q=x", [])
    assert status == sc.STATUS_BLOCKED
    assert detail == "http:403"


@pytest.mark.parametrize("reason,kind", [
    ("http:403", sc.BLOCK_DENIED),
    ("url:sorry", sc.BLOCK_CAPTCHA),
    ("dom:recaptcha", sc.BLOCK_CAPTCHA),
    ("text:unusual", sc.BLOCK_CAPTCHA),
    ("url:consent.google.com", sc.BLOCK_CONSENT),
])
def test_walls_are_classified_by_what_can_be_done_about_them(reason, kind):
    assert sc.block_kind(reason) == kind


def test_a_403_never_wakes_a_human(tmp_path, monkeypatch):
    """There is no CAPTCHA on a 403, so waiting for someone burns the whole window."""
    alerts = []
    monkeypatch.setattr(S, "wall_alert", lambda *a, **k: alerts.append(a) or
                        {"sound": True, "toast": True, "mobile": True})
    waited = []
    monkeypatch.setattr(serp_attended.AttendedSession, "wait_for_clear",
                        lambda self, minutes: waited.append(minutes) or True)
    session = _attended(tmp_path)
    assert session.pause({"rank": 9, "query": "q", "reason": "http:403"}) is False
    assert session.gave_up is True
    assert waited == [], "a 403 must not start a wait — nobody can clear it"
    assert alerts, "but the operator must still be told"


def test_a_captcha_still_waits(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "wall_alert", lambda *a, **k: {"sound": 1, "toast": 1, "mobile": 1})
    monkeypatch.setattr(S, "operator_available", lambda: True)
    waited = []
    monkeypatch.setattr(serp_attended.AttendedSession, "wait_for_clear",
                        lambda self, minutes: waited.append(minutes) or True)
    session = _attended(tmp_path)
    assert session.pause({"rank": 9, "query": "q", "reason": "url:sorry"}) is True
    assert waited, "a solvable wall must still wait for the human"


def test_saved_bytes_repair_a_status_the_old_detector_got_wrong(tmp_path):
    """Blocked is never anything else — and the saved HTML is the evidence."""
    rows = [{"rank": 1, "search_query": "q one"}]
    driver = FakeDriver({"q one": (FORBIDDEN, "https://www.google.com/search?q=x")})
    monkey = sc.detect_block
    try:
        sc.detect_block = lambda html, url="": None          # the old, blind detector
        sc.collect_serps(rows, driver=driver, run_dir=tmp_path,
                         pace=lambda: None, sleep=lambda s: None, max_block_retries=0)
        assert sc.read_fetch_log(tmp_path)["1"]["status"] == sc.STATUS_ANOMALY
    finally:
        sc.detect_block = monkey

    out = serp_report.repair_statuses(tmp_path, rows)
    assert out["n"] == 1 and out["fixed"][0]["kind"] == sc.BLOCK_DENIED
    assert sc.read_fetch_log(tmp_path)["1"]["status"] == sc.STATUS_BLOCKED

# --------------------------------------------------------------- run-level clock
def test_the_clock_belongs_to_the_run_not_to_one_session(tmp_path):
    """Resuming used to restart at zero: a run 40 queries deep reported a few seconds."""
    S.begin_session(tmp_path, "attended", "r")
    S.heartbeat(tmp_path, query_done=True)
    S.end_session(tmp_path)
    banked = S.timer_state(tmp_path)["elapsed_s"]

    S.begin_session(tmp_path, "attended", "r")          # resume
    t = S.timer_state(tmp_path)
    assert t["elapsed_s"] >= banked, "a resumed run must not restart the clock at zero"
    assert t["status"] == "running"


def test_a_killed_session_still_banks_the_time_it_earned(tmp_path):
    """No end_session runs when a runner is killed; the next start must not discard it."""
    S.begin_session(tmp_path, "attended", "r")
    S.heartbeat(tmp_path, query_done=True)
    state = S.read_state(tmp_path)
    state["active"]["started_at"] = "2026-08-21T10:00:00"
    state["active"]["last_beat"] = "2026-08-21T10:05:00"
    S.write_state(tmp_path, state)

    S.begin_session(tmp_path, "attended", "r")          # orphan banked here
    assert S.timer_state(tmp_path)["elapsed_s"] >= 300, "the killed session's 5 min was lost"


def test_heartbeats_while_waiting_are_not_counted_as_queries(tmp_path):
    """The wait loop beats every few seconds; counting those reported 117 queries against 42."""
    S.begin_session(tmp_path, "attended", "r")
    S.heartbeat(tmp_path, query_done=True)
    for _ in range(20):
        S.heartbeat(tmp_path)                            # liveness only
    assert S.timer_state(tmp_path)["queries"] == 1


def test_a_wall_freezes_the_clock_and_clearing_it_resumes(tmp_path):
    S.begin_session(tmp_path, "attended", "r")
    S.heartbeat(tmp_path, query_done=True)
    S.begin_block(tmp_path)
    frozen = S.timer_state(tmp_path)
    assert frozen["status"] == "blocked"
    time.sleep(1.1)
    assert S.timer_state(tmp_path)["elapsed_s"] == pytest.approx(frozen["elapsed_s"], abs=0.2), \
        "the clock must not advance while a human is being waited on"
    S.end_block(tmp_path)
    resumed = S.timer_state(tmp_path)
    assert resumed["status"] == "running"
    assert resumed["walls_cleared"] == 1
    assert resumed["paused_s"] >= 1.0, "the wall's duration must be banked, not counted"


def test_walls_cleared_survives_a_session_restart(tmp_path):
    S.begin_session(tmp_path, "attended", "r")
    S.begin_block(tmp_path)
    S.end_block(tmp_path)
    S.end_session(tmp_path)
    S.begin_session(tmp_path, "attended", "r")
    assert S.timer_state(tmp_path)["walls_cleared"] == 1

# --------------------------------------------------------------- batch session
def _batch(tmp_path, **overrides):
    from tools import serp_batch
    args = types.SimpleNamespace(batch=30, pace_min=0, pace_max=0, breather=0,
                                 breather_every=10, max_anomalies=3, rest=150,
                                 block_rest=360, notify_on_block=False, no_report=True)
    for k, v in overrides.items():
        setattr(args, k, v)
    handle = S.RunHandle(run_id="r", run_dir=str(tmp_path), ctx=None, qrows=QROWS)
    return serp_batch.BatchSession(handle, args)


def test_batch_stops_on_the_first_wall_rather_than_grinding(tmp_path):
    session = _batch(tmp_path)
    assert session.stop({"attempted": 1, "status": sc.STATUS_PARSED, "rank": 1}) is False
    assert session.stop({"attempted": 2, "status": sc.STATUS_BLOCKED, "rank": 2}) is True
    assert session.blocked_at == {"rank": 2, "query": None}


def test_batch_stops_at_its_cap(tmp_path):
    session = _batch(tmp_path, batch=3)
    for i in (1, 2):
        assert session.stop({"attempted": i, "status": sc.STATUS_PARSED, "rank": i}) is False
    assert session.stop({"attempted": 3, "status": sc.STATUS_PARSED, "rank": 3}) is True


def test_a_run_of_anomalies_stops_the_batch_but_one_does_not(tmp_path):
    session = _batch(tmp_path, max_anomalies=3)
    assert session.stop({"attempted": 1, "status": sc.STATUS_ANOMALY, "rank": 1}) is False
    assert session.stop({"attempted": 2, "status": sc.STATUS_PARSED, "rank": 2}) is False
    assert session.non_terminal == 0, "a good page must reset the anomaly streak"
    for i in (3, 4):
        assert session.stop({"attempted": i, "status": sc.STATUS_ERROR, "rank": i}) is False
    assert session.stop({"attempted": 5, "status": sc.STATUS_ERROR, "rank": 5}) is True


def test_batch_never_passes_a_pause_hook_so_it_cannot_wait_on_a_human(tmp_path):
    """An overnight session must record the wall and leave, not park on a callback."""
    import inspect
    from tools import serp_batch
    src = inspect.getsource(serp_batch.main)
    assert "pause_cb=None" in src
    assert "max_block_retries=0" in src


# --------------------------------------------------------------- the review page
def _run_with_data(tmp_path):
    (tmp_path / ".cache").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".cache" / "query_rows.json").write_text(json.dumps(QROWS), encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps(
        {"run_id": "test-run", "geography": "guntur-ap", "practice": "dermatology",
         "subject_type": "both", "run_date": "2026-08-21", "query_threshold": len(QROWS)}),
        encoding="utf-8")
    collect(tmp_path,
            script={QROWS[1]["search_query"]: (BLOCKED_PAGE, "https://www.google.com/sorry/i"),
                    QROWS[2]["search_query"]: EMPTY_PAGE},
            stop_cb=lambda info: info["attempted"] >= 5, max_block_retries=0)
    return tmp_path


def test_report_counts_against_the_full_query_set_not_what_was_tried(tmp_path):
    run = _run_with_data(tmp_path)
    data = serp_report.collect_data(run, qrows=QROWS)
    assert data["meta"]["total"] == len(QROWS)
    assert data["meta"]["captured"] == 4        # 5 attempted, 1 of them blocked
    assert data["meta"]["yield"] == pytest.approx(4 / len(QROWS))


def test_report_lists_every_query_including_the_ones_holding_no_data(tmp_path):
    run = _run_with_data(tmp_path)
    data = serp_report.collect_data(run, qrows=QROWS)
    assert len(data["queries"]) == len(QROWS)
    by_status = {q["rank"]: q["status"] for q in data["queries"]}
    assert by_status[2] == sc.STATUS_BLOCKED
    assert by_status[3] == sc.STATUS_ZERO
    assert by_status[8] == "not_attempted", "queries never reached must say so, not vanish"


def test_report_keeps_the_block_reason_so_a_gap_can_be_explained(tmp_path):
    run = _run_with_data(tmp_path)
    data = serp_report.collect_data(run, qrows=QROWS)
    blocked = next(q for q in data["queries"] if q["status"] == sc.STATUS_BLOCKED)
    assert blocked["detail"]


def test_report_separates_owned_from_borrowed(tmp_path):
    run = _run_with_data(tmp_path)
    data = serp_report.collect_data(run, qrows=QROWS)
    practo = next(d for d in data["domains"] if "practo" in d["domain"])
    assert practo["bucket"] == "aggregator"
    assert serp_report.domain_bucket("clinic_site", "skinlane.in") == "clinic"
    assert serp_report.domain_bucket("instagram", "instagram.com") == "social"
    assert serp_report.domain_bucket("other", "mayoclinic.org") == "reference"


@pytest.mark.parametrize("hostile", [
    "read more </script><script>alert(1)</script>",
    "code: <!-- <script src=x>",                  # script-data-escaped, never closed
    "<!--<script>",
    "a < b and c </SCRIPT >",
])
def test_embedded_data_can_never_break_out_of_the_script_block(hostile):
    """Google's text reaching a <script> block is the page's one injection surface.

    Escaping only `</` is insufficient: `<!--` followed by `<script` puts the HTML tokenizer
    into its script-data-escaped state, where the page's own closing tag stops closing
    anything and the document renders blank. No `<` may survive at all.
    """
    blob = serp_report.embed_json({"snippet": hostile})
    assert "<" not in blob
    assert json.loads(blob)["snippet"] == hostile, "escaping must survive a JSON round-trip"


def test_a_hostile_snippet_leaves_exactly_one_closing_script_tag_in_the_page(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"run_id": "x"}), encoding="utf-8")
    rows = [{"rank": 1, "search_query": "q", "category": "Discovery"}]
    (tmp_path / "serp" / "pages").mkdir(parents=True)
    (tmp_path / "serp" / "pages" / "q001.json").write_text(json.dumps({
        "rank": 1, "index": 1, "blocks": [{"position": 1, "block_type": "organic",
                                           "platform": "clinic_site", "title": "<!--<script>",
                                           "domain": "x.in", "url": "https://x.in",
                                           "snippet": "</script><script>alert(1)</script>"}]}),
        encoding="utf-8")
    html = Path(serp_report.build_report(tmp_path, qrows=rows)).read_text(encoding="utf-8")
    assert html.count("</script>") == 1
    assert html.rstrip().endswith("</html>")


def test_report_writes_a_self_contained_page(tmp_path):
    run = _run_with_data(tmp_path)
    path = Path(serp_report.build_report(run, qrows=QROWS))
    html = path.read_text(encoding="utf-8")
    assert path.name == serp_report.REPORT_NAME
    assert "__DATA__" not in html, "the placeholder must be replaced"
    assert "<title>Google Search extraction</title>" in html
    assert "http://" not in html.split("<script>")[0], "no external assets"


def test_report_survives_a_run_with_nothing_captured_yet(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"run_id": "empty"}), encoding="utf-8")
    data = serp_report.collect_data(tmp_path, qrows=QROWS)
    assert data["meta"]["captured"] == 0
    assert data["meta"]["yield"] == 0.0
    assert all(q["status"] == "not_attempted" for q in data["queries"])
    assert serp_report.build_report(tmp_path, qrows=QROWS)


def test_report_handles_a_run_with_no_queries_at_all(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"run_id": "none"}), encoding="utf-8")
    data = serp_report.collect_data(tmp_path, qrows=[])
    assert data["meta"]["total"] == 0
    assert data["meta"]["yield"] == 0.0     # must not divide by zero
    assert serp_report.build_report(tmp_path, qrows=[])
