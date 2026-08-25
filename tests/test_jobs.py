"""The JobRunner: one form submission -> a finished snapshot, unattended. No network.

Every collector is stubbed. What these tests defend is the orchestration, and specifically the
failure modes the plan calls out:

* **Stages are checkpointed and resumable.** A crash must not restart from zero, and — the
  original sin of the old collectors — must not lose a stage that had already finished.
* **One job at a time.** Two concurrent scrapes would share one browser profile and one set of
  run paths and corrupt each other.
* **Blocked/partial SERP degrades loudly**, and the manifest records web_signal so a Maps-only
  run is visibly Maps-only rather than silently scoring clinics as invisible.
* **The maps checkpoint wrapper persists per query**, so the "all-or-nothing at end of
  collect()" data-loss class cannot happen here.
"""
import json
from pathlib import Path

import pytest

from modules import jobs, runstore


@pytest.fixture
def runs_root(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "RUNS_DIR", str(tmp_path / "runs"))
    (tmp_path / "runs").mkdir()
    yield tmp_path / "runs"
    config.deactivate_run()


@pytest.fixture
def fake_stages(monkeypatch):
    """Replace every stage's real work with a recorder, so orchestration is tested in isolation."""
    calls = []

    def rec(name):
        def _stage(runner, **kw):
            calls.append(name)
            return jobs.StageResult(status="ok", counts={name: 1})
        return _stage

    for name in jobs.STAGE_ORDER:
        monkeypatch.setitem(jobs.STAGE_IMPL, name, rec(name))
    return calls


def _submit(runs_root, **kw):
    params = dict(geography="guntur-ap", specialty="dermatology",
                  subject_type="both", query_threshold=12)
    params.update(kw)
    return jobs.JobRunner(root=str(runs_root)).run(**params)


# --- happy path ---------------------------------------------------------------

def test_runs_all_stages_in_order(runs_root, fake_stages):
    job = _submit(runs_root)
    assert fake_stages == list(jobs.STAGE_ORDER)
    assert job.status == "complete"


def test_creates_a_snapshot_directory_and_finalizes_it(runs_root, fake_stages):
    job = _submit(runs_root)
    m = runstore.read_manifest(job.run_dir)
    assert m["status"] == "complete"
    assert m["geography"] == "guntur-ap" and m["subject_type"] == "both"


def test_finalized_run_is_immutable(runs_root, fake_stages):
    job = _submit(runs_root)
    with pytest.raises(runstore.RunFinalized):
        runstore.update_manifest(job.run_dir, notes="tamper")


def test_run_id_encodes_the_snapshot_key(runs_root, fake_stages):
    job = _submit(runs_root, run_date="2026-08-18")
    assert job.run_id == "guntur-ap_dermatology_both_2026-08-18"


def test_progress_is_reported_per_stage(runs_root, fake_stages):
    seen = []
    jobs.JobRunner(root=str(runs_root)).run(
        geography="guntur-ap", specialty="dermatology", subject_type="both",
        query_threshold=12, progress_cb=lambda s: seen.append((s["stage"], s["status"])))
    stages = [s for s, _ in seen]
    for name in jobs.STAGE_ORDER:
        assert name in stages


# --- single-job lock ----------------------------------------------------------

def test_second_concurrent_job_is_refused(runs_root, monkeypatch):
    started = {"n": 0}

    def slow_queries(runner, **kw):
        started["n"] += 1
        # while inside a stage, a second submission must be refused
        with pytest.raises(jobs.JobAlreadyRunning):
            jobs.JobRunner(root=str(runs_root)).run(
                geography="guntur-ap", specialty="dermatology",
                subject_type="both", query_threshold=12)
        return jobs.StageResult(status="ok", counts={})

    monkeypatch.setitem(jobs.STAGE_IMPL, "queries", slow_queries)
    for name in jobs.STAGE_ORDER[1:]:
        monkeypatch.setitem(jobs.STAGE_IMPL, name,
                            lambda runner, **kw: jobs.StageResult(status="ok", counts={}))
    _submit(runs_root)
    assert started["n"] == 1


def test_lock_is_released_after_a_failed_job(runs_root, monkeypatch):
    def boom(runner, **kw):
        raise RuntimeError("kaboom")
    monkeypatch.setitem(jobs.STAGE_IMPL, "queries", boom)
    with pytest.raises(RuntimeError):
        _submit(runs_root)
    # a fresh job can still acquire the lock
    for name in jobs.STAGE_ORDER:
        monkeypatch.setitem(jobs.STAGE_IMPL, name,
                            lambda runner, **kw: jobs.StageResult(status="ok", counts={}))
    assert _submit(runs_root).status == "complete"


# --- resume -------------------------------------------------------------------

def test_completed_stages_are_skipped_on_resume(runs_root, monkeypatch):
    ran = []
    for name in jobs.STAGE_ORDER:
        monkeypatch.setitem(jobs.STAGE_IMPL, name,
                            (lambda nm: lambda runner, **kw: (ran.append(nm),
                             jobs.StageResult(status="ok", counts={}))[1])(name))
    job = _submit(runs_root, run_date="2026-08-18")
    first = list(ran)
    ran.clear()
    # resume the same run: nothing should re-run, because all stages checkpointed ok
    jobs.JobRunner(root=str(runs_root)).resume(job.run_id)
    assert first == list(jobs.STAGE_ORDER)
    assert ran == []


def test_resume_reruns_only_the_unfinished_stage(runs_root, monkeypatch):
    ran = []

    def ok(nm):
        return lambda runner, **kw: (ran.append(nm), jobs.StageResult(status="ok", counts={}))[1]

    # fail at 'reviews' the first time
    def fail_reviews(runner, **kw):
        ran.append("reviews")
        raise RuntimeError("throttled")

    for name in jobs.STAGE_ORDER:
        monkeypatch.setitem(jobs.STAGE_IMPL, name, ok(name))
    monkeypatch.setitem(jobs.STAGE_IMPL, "reviews", fail_reviews)
    with pytest.raises(RuntimeError):
        _submit(runs_root, run_date="2026-08-18")
    assert "unify" not in ran            # never reached the later stages

    ran.clear()
    monkeypatch.setitem(jobs.STAGE_IMPL, "reviews", ok("reviews"))
    jobs.JobRunner(root=str(runs_root)).resume("guntur-ap_dermatology_both_2026-08-18")
    assert "queries" not in ran          # the stage before the failure was not repeated
    assert ran[0] == "reviews"           # resumed exactly at the failed stage
    assert "score" in ran


# --- checkpoint wrapper: the end-of-batch fix ---------------------------------

def test_maps_checkpoint_persists_after_each_query(tmp_path, monkeypatch):
    """The old collect() saved only at the end; a crash at query N of M lost all N.

    The wrapper drives the collector one query at a time and checkpoints between, so an
    interruption keeps everything captured so far.
    """
    calls = []

    def fake_collect(query_rows, mock=False, progress_cb=None):
        calls.append([q["rank"] for q in query_rows])
        return [{"name": f"c{query_rows[0]['rank']}", "status": "OK",
                 "place_url": "", "source_query": query_rows[0]["search_query"]}]

    monkeypatch.setattr(jobs.maps_collector, "collect", fake_collect)
    qrows = [{"rank": i, "search_query": f"q{i} in Guntur"} for i in range(1, 6)]
    out = jobs.collect_maps_checkpointed(qrows, run_dir=str(tmp_path), progress_cb=None)
    assert [c[0] for c in calls] == [1, 2, 3, 4, 5]      # one query per call
    assert all(len(c) == 1 for c in calls)
    assert len(out) == 5
    # a checkpoint file exists and lists the completed ranks
    cp = json.loads((tmp_path / "checkpoints" / "maps.json").read_text())
    assert set(cp["done_ranks"]) == {1, 2, 3, 4, 5}


def test_maps_checkpoint_resumes_and_skips_done_queries(tmp_path, monkeypatch):
    done = []

    def fake_collect(query_rows, mock=False, progress_cb=None):
        done.append(query_rows[0]["rank"])
        return [{"name": f"c{query_rows[0]['rank']}", "status": "OK", "place_url": ""}]

    monkeypatch.setattr(jobs.maps_collector, "collect", fake_collect)
    qrows = [{"rank": i, "search_query": f"q{i} in Guntur"} for i in range(1, 6)]
    # pretend 1..3 were already done in a prior interrupted run
    (tmp_path / "checkpoints").mkdir(parents=True)
    (tmp_path / "checkpoints" / "maps.json").write_text(json.dumps(
        {"done_ranks": [1, 2, 3],
         "rows": [{"name": "c1", "status": "OK", "place_url": ""}]}))
    jobs.collect_maps_checkpointed(qrows, run_dir=str(tmp_path), progress_cb=None)
    assert done == [4, 5]                # only the unfinished queries re-run


def test_reviews_checkpoint_chunks_and_persists(tmp_path, monkeypatch):
    seen_chunks = []

    def fake_reviews(clinics, mock=False, progress_cb=None, cap=None):
        seen_chunks.append(len(clinics))
        return {c["key"]: [{"text": "ok"}] for c in clinics}

    monkeypatch.setattr(jobs.reviews_collector, "collect_reviews", fake_reviews)
    monkeypatch.setattr(jobs.reviews_nlp, "analyze_all", lambda reviews: reviews)
    clinics = [{"key": f"k{i}", "name": f"c{i}", "place_url": ""} for i in range(12)]
    out = jobs.collect_reviews_checkpointed(clinics, run_dir=str(tmp_path), chunk=5)
    assert seen_chunks == [5, 5, 2]     # bounded loss: at most one chunk on a crash
    assert len(out) == 12


# --- loud degradation ---------------------------------------------------------

def test_partial_serp_yield_sets_web_signal_partial(runs_root, monkeypatch):
    for name in jobs.STAGE_ORDER:
        monkeypatch.setitem(jobs.STAGE_IMPL, name,
                            lambda runner, **kw: jobs.StageResult(status="ok", counts={}))

    def partial_serp(runner, **kw):
        runner.record_web_signal("partial", {"captured_serps": 40, "total_queries": 100})
        return jobs.StageResult(status="partial", counts={"captured": 40})

    monkeypatch.setitem(jobs.STAGE_IMPL, "serp", partial_serp)
    job = _submit(runs_root)
    m = runstore.read_manifest(job.run_dir)
    assert m["web_signal"] == "partial"
    assert m["denominators"]["captured_serps"] == 40


def test_manifest_records_denominators_and_scoring_params(runs_root, monkeypatch):
    for name in jobs.STAGE_ORDER:
        monkeypatch.setitem(jobs.STAGE_IMPL, name,
                            lambda runner, **kw: jobs.StageResult(status="ok", counts={}))

    def serp(runner, **kw):
        runner.record_web_signal("full", {"captured_serps": 96, "total_queries": 100})
        return jobs.StageResult(status="ok", counts={})

    def score(runner, **kw):
        runner.record_scoring()
        return jobs.StageResult(status="ok", counts={})

    monkeypatch.setitem(jobs.STAGE_IMPL, "serp", serp)
    monkeypatch.setitem(jobs.STAGE_IMPL, "score", score)
    job = _submit(runs_root, query_threshold=100)
    m = runstore.read_manifest(job.run_dir)
    assert m["denominators"]["total_queries"] == 100
    assert m["scoring"]["scoring_version"]
    # OWNED_FULL must have scaled up from the June 6 at 96 captured SERPs
    assert m["scoring"]["OWNED_FULL"] >= 6
