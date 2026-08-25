"""The HTTP surface over the JobRunner. No browser, no live server (FastAPI TestClient).

The API is what the future dashboard will consume, and what an operator hits to launch a run.
The job itself is stubbed to a no-op so these tests exercise the endpoints and the run store,
not the scraper. What matters: submitting returns a job+run id, the single-job rule returns 409
rather than corrupting a second run, and every historical snapshot is readable back — including
its manifest and a diff against another snapshot.
"""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api import app as app_module
from modules import runstore


@pytest.fixture
def client(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "RUNS_DIR", str(tmp_path / "runs"))
    (tmp_path / "runs").mkdir()
    # Stub the runner: create a finalized run without scraping anything.
    def fake_run(self, geography, specialty, subject_type="both", query_threshold=None,
                 run_date=None, progress_cb=None):
        from modules import jobs
        run = runstore.create_run(root=str(tmp_path / "runs"), geography=geography,
                                  practice=specialty, subject_type=subject_type,
                                  run_date=run_date or "2026-08-18",
                                  query_threshold=query_threshold or 100)
        runstore.update_manifest(run.path, denominators={"total_queries": query_threshold or 100,
                                                         "captured_serps": 90, "maps_query_count": 100},
                                 web_signal="full")
        runstore.finalize_run(run.path)
        return jobs.Job(run_id=run.run_id, run_dir=run.path, status="complete")
    monkeypatch.setattr(app_module.jobs.JobRunner, "run", fake_run)
    return TestClient(app_module.app)


def test_submit_returns_job_and_run_id(client):
    r = client.post("/jobs", json={"geography": "guntur-ap", "specialty": "dermatology",
                                   "subject_type": "both", "query_threshold": 100})
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"].startswith("guntur-ap_dermatology_both_")
    assert body["status"] == "complete"


def test_unknown_pack_is_a_400_not_a_500(client):
    r = client.post("/jobs", json={"geography": "atlantis", "specialty": "dermatology"})
    assert r.status_code == 400


def test_list_runs_returns_the_snapshot_index(client):
    client.post("/jobs", json={"geography": "guntur-ap", "specialty": "dermatology",
                               "run_date": "2026-06-28"})
    r = client.get("/runs")
    assert r.status_code == 200
    assert any(run["run_id"].endswith("2026-06-28") for run in r.json()["runs"])


def test_get_manifest_of_a_run(client):
    sub = client.post("/jobs", json={"geography": "guntur-ap", "specialty": "dermatology",
                                     "query_threshold": 100}).json()
    r = client.get(f"/runs/{sub['run_id']}/manifest")
    assert r.status_code == 200
    assert r.json()["web_signal"] == "full"
    assert r.json()["denominators"]["captured_serps"] == 90


def test_missing_run_is_404(client):
    assert client.get("/runs/does_not_exist/manifest").status_code == 404


def test_second_concurrent_job_returns_409(client, monkeypatch):
    """The lock is a JobAlreadyRunning; the API must translate it to 409, not crash."""
    from modules import jobs

    def busy(self, **kw):
        raise jobs.JobAlreadyRunning("busy")
    monkeypatch.setattr(app_module.jobs.JobRunner, "run", busy)
    r = client.post("/jobs", json={"geography": "guntur-ap", "specialty": "dermatology"})
    assert r.status_code == 409


def test_diff_endpoint_compares_two_snapshots(client, monkeypatch):
    a = client.post("/jobs", json={"geography": "guntur-ap", "specialty": "dermatology",
                                   "run_date": "2026-06-28"}).json()["run_id"]
    b = client.post("/jobs", json={"geography": "guntur-ap", "specialty": "dermatology",
                                   "run_date": "2026-08-18"}).json()["run_id"]

    monkeypatch.setattr(app_module, "_load_diff",
                        lambda x, y: {"a": x, "b": y, "new": [], "lost": [], "changed": []})
    r = client.get(f"/diff?a={a}&b={b}")
    assert r.status_code == 200
    assert r.json()["a"] == a and r.json()["b"] == b


def test_available_packs_are_exposed_for_the_form(client):
    r = client.get("/packs")
    assert r.status_code == 200
    body = r.json()
    assert "guntur-ap" in body["geographies"]
    assert "dermatology" in body["specialties"]
