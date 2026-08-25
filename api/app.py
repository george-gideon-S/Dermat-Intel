"""HTTP surface over the JobRunner — what the future dashboard and an operator both call.

Write path is one endpoint: POST /jobs launches a market analysis. Everything else is reads
over the immutable snapshot store, so the dashboard is a pure consumer of historical runs and
never needs to understand scraping.

The runner enforces one-job-at-a-time with a process lock; here that surfaces as HTTP 409
rather than a stack trace. A run is scraping-heavy and long, so POST /jobs runs it inline and
returns when the snapshot is finalized — progress during a run is observable through the run's
manifest (GET /runs/{id}/manifest carries web_signal and awaiting_human).
"""
from __future__ import annotations

# Embeddable-Python bootstrap: the interpreter runs isolated, so the repo root is not on
# sys.path unless we put it there. Every entry point needs these three lines.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

import config
from modules import jobs, marketdata, packs, runstore, snapshot_diff

app = FastAPI(title="Derma Intel — Market Intelligence", version="1.0")


class JobRequest(BaseModel):
    geography: str
    specialty: str
    subject_type: str = "both"
    query_threshold: Optional[int] = None
    run_date: Optional[str] = None
    mock: bool = False


@app.get("/packs")
def list_packs():
    """The choices an admin form offers."""
    return {"geographies": packs.available_geographies(),
            "specialties": packs.available_specialties(),
            "subject_types": list(packs.SUBJECT_TYPES)}


@app.post("/jobs")
def submit_job(req: JobRequest):
    # Validate the request at the boundary: an unknown pack or bad subject_type is a 400, and
    # rejecting it here (before the runner acquires the job lock) means a malformed request
    # can never block a real run.
    try:
        packs.load(req.geography, req.specialty, req.subject_type, req.query_threshold)
    except (packs.PackNotFound, packs.InvalidPack) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        runner = jobs.JobRunner(root=config.RUNS_DIR, mock=req.mock)
        job = runner.run(geography=req.geography, specialty=req.specialty,
                         subject_type=req.subject_type, query_threshold=req.query_threshold,
                         run_date=req.run_date)
    except jobs.JobAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (packs.PackNotFound, packs.InvalidPack) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"run_id": job.run_id, "status": job.status, "stages": job.stages,
            "errors": job.errors}


@app.post("/jobs/{run_id}/resume")
def resume_job(run_id: str):
    try:
        job = jobs.JobRunner(root=config.RUNS_DIR).resume(run_id)
    except jobs.JobAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (packs.PackNotFound, packs.InvalidPack) as exc:
        # A run whose pack was renamed/removed can't be resumed — a 400, not an unhandled 500.
        raise HTTPException(status_code=400, detail=str(exc))
    return {"run_id": job.run_id, "status": job.status, "stages": job.stages}


@app.get("/runs")
def list_runs(geography: Optional[str] = None, specialty: Optional[str] = None,
              subject_type: Optional[str] = None):
    filters = {}
    if geography:
        filters["geography"] = geography
    if specialty:
        filters["practice"] = specialty
    if subject_type:
        filters["subject_type"] = subject_type
    return {"runs": runstore.list_runs(config.RUNS_DIR, **filters)}


def _manifest_or_404(run_id: str) -> dict:
    path = runstore.run_path(config.RUNS_DIR, run_id)
    m = runstore.read_manifest(path)
    if not m:
        raise HTTPException(status_code=404, detail=f"no run {run_id!r}")
    return m


@app.get("/runs/{run_id}/manifest")
def get_manifest(run_id: str):
    return _manifest_or_404(run_id)


@app.get("/runs/{run_id}/clinics")
def get_clinics(run_id: str):
    _manifest_or_404(run_id)
    return {"run_id": run_id,
            "clinics": snapshot_diff.load_clinics(runstore.run_path(config.RUNS_DIR, run_id))}


@app.get("/runs/{run_id}/serp-proof/{clinic_key}")
def get_serp_proof(run_id: str, clinic_key: str):
    from modules import atomicio, report, storage
    _manifest_or_404(run_id)
    run_dir = runstore.run_path(config.RUNS_DIR, run_id)
    screens = atomicio.read_json(_Path(run_dir) / ".cache" / "web_screens.json", default={})
    query_rows = atomicio.read_json(_Path(run_dir) / ".cache" / "query_rows.json", default=[])
    # serp_proof needs the clinic list to know which clinic each SERP block maps to. Passing
    # only 3 args (the earlier bug) raised TypeError on every call, silently swallowed as a
    # benign 404 — so the doctor-facing proof card never rendered.
    rows = atomicio.read_json(_Path(run_dir) / ".cache" / "result_rows.json", default=[]) or []
    clinics = [{"name": r.get("name"), "website": r.get("website"), "place_url": r.get("place_url")}
               for r in rows]
    try:
        proof = report.serp_proof(clinic_key, screens, clinics, query_rows)
    except Exception as exc:  # genuinely-absent proof is a 404; a code error must not hide here
        raise HTTPException(status_code=404, detail=f"no proof available: {exc}")
    return proof or {}


def _load_diff(run_id_a: str, run_id_b: str) -> dict:
    """Indirected so tests can stub the heavy xlsx load."""
    return snapshot_diff.diff_by_id(config.RUNS_DIR, run_id_a, run_id_b)


@app.get("/diff")
def diff(a: str = Query(...), b: str = Query(...)):
    _manifest_or_404(a)
    _manifest_or_404(b)
    return _load_diff(a, b)


@app.get("/market/{geography}/{specialty}/clinics")
def market_clinics(geography: str, specialty: str, run: Optional[str] = None):
    """Clinic rows from a Google-Maps survey snapshot, joined with their coordinates.

    A different snapshot tree from the SERP runs above (runs/gmaps/); the join and its
    loud-degradation rules live in modules/marketdata.py. `run` pins a snapshot by id;
    omitted, the newest complete survey for the pack wins.
    """
    try:
        target = (marketdata.run_dir(geography, specialty, run) if run
                  else marketdata.latest_run(geography, specialty))
        return marketdata.load_market(target)
    except marketdata.MarketRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
