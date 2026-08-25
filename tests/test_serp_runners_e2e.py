"""End-to-end wiring for both runners: main() from argv to exit code, no browser, no network.

The unit tests pin each callback's logic. These pin the thing unit tests cannot see — that the
whole entry point is actually wired together: argument names match attribute names, the run
resolves, the collector is called with the arguments each runner intends, the manifest and
state file are updated, the report builds, and the exit code matches what a scheduler is told
to expect. A typo in an argparse `dest` passes every unit test and fails on first live use.
"""
import json

import pytest

from modules import runstore, serp_collector as sc, serp_session as S
from tests.test_serp_collector import BLOCKED_PAGE, ORGANIC_PAGE, FakeDriver

QROWS = [{"rank": i, "search_query": f"skin doctor number {i} Guntur", "category": "Discovery",
          "user_intent": "find a clinic", "search_strength_score": 5} for i in range(1, 11)]


@pytest.fixture
def market(tmp_path, monkeypatch):
    """A real snapshot on disk, with a fake driver and an isolated lock."""
    root = tmp_path / "runs"
    root.mkdir()
    monkeypatch.setattr(S.config, "RUNS_DIR", str(root))
    monkeypatch.setattr(S.config, "BROWSER_DIR", str(tmp_path / "browser"))
    monkeypatch.setattr(S, "_LOCAL_HOLDER", None)

    run = runstore.create_run(root=str(root), geography="guntur-ap", practice="dermatology",
                              subject_type="both", run_date="2026-08-21",
                              query_threshold=len(QROWS))
    (S.query_rows_path(run.path)).parent.mkdir(parents=True, exist_ok=True)
    S.query_rows_path(run.path).write_text(json.dumps(QROWS), encoding="utf-8")

    drivers = []

    def fake_build_driver(ctx, **kw):
        d = FakeDriver(fake_build_driver.script)
        drivers.append(d)
        return d

    fake_build_driver.script = {}
    monkeypatch.setattr(S, "build_driver", fake_build_driver)
    monkeypatch.setattr(S, "wall_alert",
                        lambda *a, **k: {"sound": False, "toast": False,
                                         "mobile": False})

    yield type("Market", (), {"root": str(root), "run_id": run.run_id, "path": run.path,
                              "drivers": drivers, "build": fake_build_driver})
    S._LOCAL_HOLDER = None


def state(market):
    return S.read_state(market.path)


def counts(market):
    return S.status_counts(market.path, QROWS)


# ------------------------------------------------------------------ Option A: batch
def test_batch_captures_one_batch_then_parks_behind_a_cooldown(market):
    from tools import serp_batch
    code = serp_batch.main(["--run", market.run_id, "--batch", "4",
                            "--pace-min", "0", "--pace-max", "0", "--breather", "0"])
    assert code == serp_batch.EXIT_MORE
    assert counts(market)["captured"] == 4
    assert len(market.drivers[0].calls) == 4
    assert market.drivers[0].stopped, "the browser must be closed between batches"
    assert S.cooldown_remaining(market.path) > 0
    assert state(market)["sessions"][-1]["outcome"] == "capped"


def test_a_second_invocation_inside_the_cooldown_does_nothing(market):
    from tools import serp_batch
    common = ["--run", market.run_id, "--batch", "4", "--pace-min", "0", "--pace-max", "0",
              "--breather", "0"]
    serp_batch.main(common)
    before = counts(market)["captured"]
    code = serp_batch.main(common)
    assert code == serp_batch.EXIT_EARLY
    assert counts(market)["captured"] == before, "a cooled-down invocation must not scrape"
    assert len(market.drivers) == 1, "and must not even open a browser"


def test_force_overrides_the_cooldown_and_resumes_where_it_stopped(market):
    from tools import serp_batch
    common = ["--run", market.run_id, "--batch", "4", "--pace-min", "0", "--pace-max", "0",
              "--breather", "0"]
    serp_batch.main(common)
    serp_batch.main(common + ["--force"])
    assert counts(market)["captured"] == 8
    assert market.drivers[1].calls == [q["search_query"] for q in QROWS[4:8]], \
        "the second batch must continue, not restart"


def test_batch_runs_to_completion_over_successive_invocations(market):
    from tools import serp_batch
    common = ["--run", market.run_id, "--batch", "4", "--pace-min", "0", "--pace-max", "0",
              "--breather", "0", "--force"]
    codes = [serp_batch.main(common) for _ in range(3)]
    assert codes[-1] == serp_batch.EXIT_DONE
    assert counts(market)["captured"] == len(QROWS)
    assert S.cooldown_remaining(market.path) <= 0, "a finished run must not stay parked"


def test_batch_stops_on_a_wall_and_sets_the_longer_cooldown(market):
    from tools import serp_batch
    market.build.script = {QROWS[2]["search_query"]: (BLOCKED_PAGE,
                                                      "https://www.google.com/sorry/index")}
    code = serp_batch.main(["--run", market.run_id, "--batch", "8", "--pace-min", "0",
                            "--pace-max", "0", "--breather", "0", "--block-rest", "360",
                            "--rest", "150"])
    assert code == serp_batch.EXIT_BLOCKED
    assert len(market.drivers[0].calls) == 3, "must stop at the wall, not grind the batch out"
    assert counts(market)["counts"][sc.STATUS_BLOCKED] == 1
    assert S.cooldown_remaining(market.path) > 150 * 60, "a wall earns the longer rest"
    assert (S.serp_collector.serp_dir(market.path) / "BLOCKED.txt").exists()


def test_a_walled_query_is_retried_by_the_next_invocation(market):
    from tools import serp_batch
    market.build.script = {QROWS[2]["search_query"]: (BLOCKED_PAGE,
                                                      "https://www.google.com/sorry/index")}
    serp_batch.main(["--run", market.run_id, "--batch", "8", "--pace-min", "0",
                     "--pace-max", "0", "--breather", "0"])
    market.build.script = {}                      # the wall cleared
    serp_batch.main(["--run", market.run_id, "--batch", "8", "--pace-min", "0",
                     "--pace-max", "0", "--breather", "0", "--force"])
    assert QROWS[2]["search_query"] in market.drivers[1].calls
    assert counts(market)["counts"][sc.STATUS_BLOCKED] == 0


def test_the_session_history_records_what_a_self_expiry_probe_needs(market):
    """The open question is whether a wall clears without a human. The log must answer it."""
    from tools import serp_batch
    market.build.script = {QROWS[1]["search_query"]: (BLOCKED_PAGE,
                                                      "https://www.google.com/sorry/index")}
    serp_batch.main(["--run", market.run_id, "--batch", "8", "--pace-min", "0",
                     "--pace-max", "0", "--breather", "0"])
    market.build.script = {}
    serp_batch.main(["--run", market.run_id, "--batch", "20", "--pace-min", "0",
                     "--pace-max", "0", "--breather", "0", "--force"])

    sessions = state(market)["sessions"]
    assert [s["outcome"] for s in sessions] == ["blocked", "complete"]
    assert sessions[0]["blocked"] == 1 and sessions[0]["blocked_at"]["rank"] == 2
    # mode distinguishes an unattended recovery from a human one: 'batch' never solves.
    assert all(s["mode"] == "batch" for s in sessions)
    assert all(s["started_at"] and s["ended_at"] for s in sessions)


def test_report_only_flags_never_create_a_run(market):
    """`--status` reads as read-only; it must not mint a snapshot that steals `--run last`."""
    from tools import serp_batch
    before = {p.name for p in (market.path.parent if hasattr(market.path, "parent")
                               else __import__("pathlib").Path(market.root)).iterdir()}
    for flag in ("--status", "--print-schedule"):
        code = serp_batch.main(["--geo", "guntur-ap", "--specialty", "dermatology", flag])
        assert code == serp_batch.EXIT_REFUSED, f"{flag} must refuse, not create"
    from pathlib import Path
    after = {p.name for p in Path(market.root).iterdir()}
    assert after == before, "no run directory may appear"
    assert S.resolve(type("A", (), {"run": "last"}), root=market.root).run_id == market.run_id


def test_a_stall_is_not_reported_as_a_clean_batch(market, monkeypatch):
    """Nothing captured, no wall: a scheduler must be able to tell this from success."""
    from tools import serp_batch

    class Broken(FakeDriver):
        def fetch(self, query_text, screenshot_path=None):
            self.calls.append(query_text)
            raise RuntimeError("driver exploded")

    monkeypatch.setattr(S, "build_driver", lambda ctx, **kw: Broken({}))
    code = serp_batch.main(["--run", market.run_id, "--batch", "30", "--max-anomalies", "3",
                            "--pace-min", "0", "--pace-max", "0", "--breather", "0"])
    assert code == serp_batch.EXIT_STALLED
    assert code != serp_batch.EXIT_MORE, "a stall must not share the healthy exit code"
    last = state(market)["sessions"][-1]
    assert last["outcome"] == "stalled"
    assert last["captured"] == 0
    assert S.read_state(market.path)["cooldown_reason"] == "after a stalled session"
    assert (S.serp_collector.serp_dir(market.path) / "STALLED.txt").exists()
    assert counts(market)["counts"][sc.STATUS_ERROR] == 3


def test_a_stall_stops_after_the_tolerance_rather_than_burning_the_batch(market, monkeypatch):
    from tools import serp_batch

    class Broken(FakeDriver):
        def fetch(self, query_text, screenshot_path=None):
            self.calls.append(query_text)
            raise RuntimeError("boom")

    drivers = []

    def build(ctx, **kw):
        d = Broken({})
        drivers.append(d)
        return d

    monkeypatch.setattr(S, "build_driver", build)
    serp_batch.main(["--run", market.run_id, "--batch", "30", "--max-anomalies", "2",
                     "--pace-min", "0", "--pace-max", "0", "--breather", "0"])
    assert len(drivers[0].calls) == 2, "must stop at the tolerance, not attempt all 30"


def test_a_failed_query_build_leaves_no_orphan_run_behind(tmp_path, monkeypatch):
    """An orphan with no query set becomes `--run last` and then refuses to attach."""
    from modules import query_builder, runstore
    root = tmp_path / "runs"
    root.mkdir()
    monkeypatch.setattr(S.config, "RUNS_DIR", str(root))

    def explode(ctx, **kw):
        raise query_builder.QuerySetInvalid("expected 100000 queries, got 583")

    monkeypatch.setattr(query_builder, "build_with_report", explode)
    with pytest.raises(S.SessionRefused) as exc:
        S.create(str(root), "guntur-ap", "dermatology", "both")
    assert "query set could not be built" in str(exc.value)
    assert list(root.iterdir()) == [root / "index.json"] or not any(
        p.is_dir() for p in root.iterdir()), "the half-made run must be removed"
    assert runstore.list_runs(str(root)) == [], "and its index row with it"


def test_a_failed_query_build_refuses_cleanly_instead_of_crashing(tmp_path, monkeypatch):
    from modules import query_builder
    from tools import serp_batch
    root = tmp_path / "runs"
    root.mkdir()
    monkeypatch.setattr(S.config, "RUNS_DIR", str(root))
    monkeypatch.setattr(query_builder, "build_with_report",
                        lambda ctx, **kw: (_ for _ in ()).throw(
                            query_builder.QuerySetInvalid("too few")))
    assert serp_batch.main(["--geo", "guntur-ap", "--specialty", "dermatology"]) == \
        serp_batch.EXIT_REFUSED


# ------------------------------------------------------------------ Option B: attended
def test_attended_captures_everything_and_reports_done(market):
    from tools import serp_attended
    code = serp_attended.main(["--run", market.run_id, "--pace-min", "0", "--pace-max", "0",
                               "--breather", "0", "--no-sound", "--no-toast"])
    assert code == 0
    assert counts(market)["captured"] == len(QROWS)
    assert state(market)["sessions"][-1]["outcome"] == "complete"


def test_attended_max_caps_the_session_and_leaves_it_resumable(market):
    from tools import serp_attended
    code = serp_attended.main(["--run", market.run_id, "--max", "3", "--pace-min", "0",
                               "--pace-max", "0", "--breather", "0", "--no-sound", "--no-toast"])
    assert code == 10
    assert counts(market)["captured"] == 3
    assert state(market)["sessions"][-1]["outcome"] == "capped"


def test_attended_with_nobody_present_records_the_wall_and_stops(market, monkeypatch):
    from tools import serp_attended
    monkeypatch.setattr(S, "operator_available", lambda: False)
    market.build.script = {QROWS[1]["search_query"]: (BLOCKED_PAGE,
                                                      "https://www.google.com/sorry/index")}
    code = serp_attended.main(["--run", market.run_id, "--pace-min", "0", "--pace-max", "0",
                               "--breather", "0", "--no-sound", "--no-toast"])
    assert code == 10
    assert counts(market)["counts"][sc.STATUS_BLOCKED] == 1
    assert counts(market)["captured"] == 1, "the query before the wall must survive"
    assert state(market)["sessions"][-1]["outcome"] == "blocked"


def test_attended_resumes_past_a_solved_wall(market, monkeypatch):
    """The measured 82/100 shape: wall, human solves, the session runs on."""
    from tools import serp_attended
    monkeypatch.setattr(S, "operator_available", lambda: True)
    monkeypatch.setattr(serp_attended.AttendedSession, "wait_for_clear",
                        lambda self, minutes: True)

    walls = {"n": 0}

    class WallOnce(FakeDriver):
        def fetch(self, query_text, screenshot_path=None):
            if query_text == QROWS[3]["search_query"] and walls["n"] == 0:
                walls["n"] += 1
                self.calls.append(query_text)
                return sc.FetchResult(html=BLOCKED_PAGE,
                                      final_url="https://www.google.com/sorry/index")
            return super().fetch(query_text, screenshot_path)

    monkeypatch.setattr(S, "build_driver", lambda ctx, **kw: WallOnce({}))
    code = serp_attended.main(["--run", market.run_id, "--pace-min", "0", "--pace-max", "0",
                               "--breather", "0", "--no-sound", "--no-toast"])
    assert code == 0
    assert counts(market)["captured"] == len(QROWS)
    assert state(market)["sessions"][-1]["solves"] == 1


def test_a_human_solving_a_wall_releases_the_batch_cooldown(market, monkeypatch):
    """Otherwise scheduled batches keep standing down for hours, citing a cleared wall."""
    from tools import serp_attended, serp_batch
    market.build.script = {QROWS[1]["search_query"]: (BLOCKED_PAGE,
                                                      "https://www.google.com/sorry/index")}
    assert serp_batch.main(["--run", market.run_id, "--batch", "8", "--pace-min", "0",
                            "--pace-max", "0", "--breather", "0"]) == serp_batch.EXIT_BLOCKED
    assert S.cooldown_remaining(market.path) > 0
    assert S.read_state(market.path)["cooldown_reason"] == "after a wall"

    market.build.script = {}                       # the operator solved it
    monkeypatch.setattr(S, "operator_available", lambda: True)
    monkeypatch.setattr(serp_attended.AttendedSession, "wait_for_clear",
                        lambda self, minutes: True)
    serp_attended.main(["--run", market.run_id, "--pace-min", "0", "--pace-max", "0",
                        "--breather", "0", "--no-sound", "--no-toast"])
    assert S.cooldown_remaining(market.path) <= 0, "the cleared wall must release the cooldown"


def test_giving_up_at_the_prompt_records_the_wall_like_a_timeout_does(market, monkeypatch):
    """Ctrl-C is offered as 'give up'; taking it must not lose the wall."""
    from tools import serp_attended

    def interrupt(self, minutes):
        raise KeyboardInterrupt

    monkeypatch.setattr(S, "operator_available", lambda: True)
    monkeypatch.setattr(serp_attended.AttendedSession, "wait_for_clear", interrupt)
    market.build.script = {QROWS[1]["search_query"]: (BLOCKED_PAGE,
                                                      "https://www.google.com/sorry/index")}
    code = serp_attended.main(["--run", market.run_id, "--pace-min", "0", "--pace-max", "0",
                               "--breather", "0", "--no-sound", "--no-toast"])
    assert code == 10
    assert state(market)["sessions"][-1]["outcome"] == "blocked", "not merely 'interrupted'"
    assert counts(market)["counts"][sc.STATUS_BLOCKED] == 1, "the wall must be on record"
    assert (S.serp_collector.serp_dir(market.path) / "BLOCKED.txt").exists()


def test_a_finished_run_is_not_rescraped_by_either_runner(market):
    from tools import serp_attended, serp_batch
    serp_attended.main(["--run", market.run_id, "--pace-min", "0", "--pace-max", "0",
                        "--breather", "0", "--no-sound", "--no-toast"])
    n_before = len(market.drivers)
    assert serp_batch.main(["--run", market.run_id]) == serp_batch.EXIT_DONE
    assert serp_attended.main(["--run", market.run_id]) == 0
    assert len(market.drivers) == n_before, "nothing left to do must not open a browser"


# ------------------------------------------------------------------ shared guarantees
def test_each_runner_publishes_the_web_signal_to_the_manifest(market):
    from tools import serp_batch
    serp_batch.main(["--run", market.run_id, "--batch", "4", "--pace-min", "0",
                     "--pace-max", "0", "--breather", "0"])
    manifest = runstore.read_manifest(market.path)
    assert manifest["web_signal"] == "partial"
    assert manifest["serp_progress"]["captured_serps"] == 4
    assert manifest["serp_progress"]["total_queries"] == len(QROWS)


def test_each_runner_leaves_a_readable_report_behind(market):
    from modules import serp_report
    from tools import serp_batch
    serp_batch.main(["--run", market.run_id, "--batch", "4", "--pace-min", "0",
                     "--pace-max", "0", "--breather", "0"])
    page = market.path if hasattr(market.path, "exists") else market.path
    from pathlib import Path
    html = (Path(page) / serp_report.REPORT_NAME).read_text(encoding="utf-8")
    assert "Google Search extraction" in html
    assert '"total": 10' in html.replace(" ", " "), "the report counts all ten queries"


def test_the_lock_stops_a_batch_starting_while_an_attended_session_holds_it(market):
    from tools import serp_batch
    held = S.SessionLock(mode="attended", run_id=market.run_id)
    held.acquire()
    try:
        assert serp_batch.main(["--run", market.run_id, "--batch", "2"]) == serp_batch.EXIT_REFUSED
        assert counts(market)["captured"] == 0
    finally:
        held.release()


def test_the_lock_is_released_after_a_normal_session(market):
    from tools import serp_batch
    serp_batch.main(["--run", market.run_id, "--batch", "2", "--pace-min", "0",
                     "--pace-max", "0", "--breather", "0"])
    assert not S.lock_path().exists()
    assert S._LOCAL_HOLDER is None
