"""Snapshot store: run identity, manifest, immutability, and the no-stray-writes guard.

No network. The behaviours here exist because a `run_pipeline.py --mock` run once overwrote a
month-old real dataset in place: runs must be isolated, finalized runs must be immutable, and
no writer may escape the active run directory.
"""
from pathlib import Path

import pytest

import config
from modules import runstore

PARAMS = dict(geography="guntur-ap", practice="dermatology", subject_type="both",
              run_date="2026-08-18", query_threshold=80)


@pytest.fixture(autouse=True)
def _restore_config():
    """Every test gets the legacy layout back, whatever it did to config."""
    yield
    config.deactivate_run()


# --- run identity -------------------------------------------------------------

def test_run_id_encodes_the_snapshot_key():
    rid = runstore.make_run_id(**{k: PARAMS[k] for k in
                                  ("geography", "practice", "subject_type", "run_date")})
    assert rid == "guntur-ap_dermatology_both_2026-08-18"


def test_run_ids_collide_only_with_a_suffix(tmp_path):
    a = runstore.create_run(tmp_path, **PARAMS)
    b = runstore.create_run(tmp_path, **PARAMS)
    assert a.run_id != b.run_id
    assert b.run_id.startswith("guntur-ap_dermatology_both_2026-08-18")
    assert Path(a.path).exists() and Path(b.path).exists()


def test_create_run_builds_the_expected_subdirectories(tmp_path):
    run = runstore.create_run(tmp_path, **PARAMS)
    for sub in (".cache", "data", "serp", "checkpoints"):
        assert (Path(run.path) / sub).is_dir()


# --- manifest -----------------------------------------------------------------

def test_manifest_records_the_intake_parameters(tmp_path):
    run = runstore.create_run(tmp_path, **PARAMS)
    m = runstore.read_manifest(run.path)
    assert m["geography"] == "guntur-ap"
    assert m["practice"] == "dermatology"
    assert m["subject_type"] == "both"
    assert m["run_date"] == "2026-08-18"
    assert m["query_threshold"] == 80
    assert m["status"] == "running"


def test_manifest_carries_the_three_denominators_separately(tmp_path):
    """Maps queries, captured SERPs and total queries are different numbers and every
    downstream figure must state which one it counts against."""
    run = runstore.create_run(tmp_path, **PARAMS)
    runstore.update_manifest(run.path, denominators={
        "maps_query_count": 50, "captured_serps": 78, "total_queries": 80})
    d = runstore.read_manifest(run.path)["denominators"]
    assert (d["maps_query_count"], d["captured_serps"], d["total_queries"]) == (50, 78, 80)


def test_manifest_stores_the_scoring_constants_actually_used(tmp_path):
    """Without this, re-rendering an old snapshot under new rules silently changes history."""
    run = runstore.create_run(tmp_path, **PARAMS)
    runstore.update_manifest(run.path, scoring={"scoring_version": "june-legacy",
                                                "DEMAND_FULL": 25, "OWNED_FULL": 6})
    assert runstore.read_manifest(run.path)["scoring"]["DEMAND_FULL"] == 25


def test_update_manifest_merges_rather_than_replaces(tmp_path):
    run = runstore.create_run(tmp_path, **PARAMS)
    runstore.update_manifest(run.path, completeness={"clinics": 34})
    runstore.update_manifest(run.path, web_signal="full")
    m = runstore.read_manifest(run.path)
    assert m["completeness"]["clinics"] == 34 and m["web_signal"] == "full"
    assert m["geography"] == "guntur-ap"  # original keys survive


# --- immutability -------------------------------------------------------------

def test_finalize_marks_the_run_complete(tmp_path):
    run = runstore.create_run(tmp_path, **PARAMS)
    runstore.finalize_run(run.path)
    m = runstore.read_manifest(run.path)
    assert m["status"] == "complete"
    assert m["finalized_at"]


def test_writing_to_a_finalized_run_raises(tmp_path):
    run = runstore.create_run(tmp_path, **PARAMS)
    runstore.finalize_run(run.path)
    with pytest.raises(runstore.RunFinalized):
        runstore.update_manifest(run.path, completeness={"clinics": 99})


def test_finalizing_twice_raises(tmp_path):
    run = runstore.create_run(tmp_path, **PARAMS)
    runstore.finalize_run(run.path)
    with pytest.raises(runstore.RunFinalized):
        runstore.finalize_run(run.path)


# --- index --------------------------------------------------------------------

def test_index_lists_runs_newest_first(tmp_path):
    runstore.create_run(tmp_path, **{**PARAMS, "run_date": "2026-06-28"})
    runstore.create_run(tmp_path, **{**PARAMS, "run_date": "2026-08-18"})
    ids = [r["run_id"] for r in runstore.list_runs(tmp_path)]
    assert ids[0].endswith("2026-08-18")


def test_index_survives_a_finalize(tmp_path):
    run = runstore.create_run(tmp_path, **PARAMS)
    runstore.finalize_run(run.path)
    entry = next(r for r in runstore.list_runs(tmp_path) if r["run_id"] == run.run_id)
    assert entry["status"] == "complete"


def test_list_runs_filters_by_snapshot_key(tmp_path):
    runstore.create_run(tmp_path, **PARAMS)
    runstore.create_run(tmp_path, **{**PARAMS, "practice": "cardiology"})
    derm = runstore.list_runs(tmp_path, practice="dermatology")
    assert len(derm) == 1 and derm[0]["practice"] == "dermatology"


# --- activation / the no-stray-writes guard ------------------------------------

def test_activating_a_run_repoints_every_artifact_path(tmp_path):
    run = runstore.create_run(tmp_path, **PARAMS)
    runstore.activate(run.path)
    for value in (config.DATA_DIR, config.CACHE_DIR, config.QUERIES_XLSX,
                  config.RESULTS_XLSX, config.VULNERABLE_XLSX, config.MAPS_CACHE,
                  config.WEB_SCREENS_CACHE, config.UNIFIED_XLSX, config.SEARCH_RESULTS_XLSX,
                  config.SCREENSHOTS_DIR, config.WEB_TILES_DIR):
        assert str(run.path) in str(value), f"path escaped the run dir: {value}"


def test_storage_paths_follow_activation_despite_module_level_names(tmp_path):
    """storage.QUERIES_JSON was captured at import time — the shim must still track the run."""
    from modules import storage
    run = runstore.create_run(tmp_path, **PARAMS)
    runstore.activate(run.path)
    assert str(run.path) in str(storage.QUERIES_JSON)
    assert str(run.path) in str(storage.RESULTS_JSON)
    assert str(run.path) in storage.queries_json()


def test_writers_do_not_escape_the_active_run_directory(tmp_path):
    """The structural guard: exercise the real writers, then assert every file landed inside."""
    from modules import storage, maps_collector, query_generator
    run = runstore.create_run(tmp_path, **PARAMS)
    runstore.activate(run.path)

    qrows = [{"rank": 1, "search_query": "acne treatment Guntur", "category": "Condition-Based",
              "user_intent": "x", "search_strength_score": 9}]
    rows = maps_collector.make_mock_results(qrows, per_query=2)
    storage.save_rows(storage.RESULTS_JSON, rows)
    storage.save_rows(storage.QUERIES_JSON, qrows)
    query_generator.save_queries_xlsx(qrows)
    maps_collector.save_results_xlsx(rows)

    written = {p.resolve() for p in Path(run.path).rglob("*") if p.is_file()}
    assert written, "nothing was written — the guard would pass vacuously"
    run_root = str(Path(run.path).resolve())
    for p in written:
        assert str(p).startswith(run_root)


def test_browser_profile_is_never_run_scoped(tmp_path):
    """Cookies/solved-CAPTCHA state must outlive a run or every quarter re-pays the CAPTCHA."""
    run = runstore.create_run(tmp_path, **PARAMS)
    runstore.activate(run.path)
    assert str(run.path) not in config.SERP_PROFILE_DIR
    assert str(Path(config.BASE_DIR)) in config.SERP_PROFILE_DIR


def test_deactivate_restores_the_legacy_layout(tmp_path):
    run = runstore.create_run(tmp_path, **PARAMS)
    runstore.activate(run.path)
    config.deactivate_run()
    assert str(run.path) not in config.CACHE_DIR
    assert config.ACTIVE_RUN_DIR is None
