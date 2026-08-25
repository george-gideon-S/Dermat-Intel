"""Snapshot store: one immutable directory per (geography, practice, subject_type, run_date).

The product's value is the comparison between quarters, which only works if a run can never
damage an earlier one. The previous layout wrote every artifact to a single shared `data/` +
`.cache/` tree, so a second run — including an accidental `--mock` — silently replaced the
first. That happened, and it destroyed a month-old dataset.

Layout:

    runs/index.json                                   # every run, newest first
    runs/<geo>_<practice>_<subject>_<date>/
        manifest.json    # params, denominators, scoring constants used, completeness
        .cache/  data/  serp/  checkpoints/

`activate()` repoints config's artifact paths at a run, so the existing collectors write into
the snapshot without knowing snapshots exist. The browser profile is deliberately NOT
run-scoped: its warmed cookie state is what keeps the SERP scraper unblocked.

Manifests record the scoring constants a run actually used. A later scoring change therefore
cannot silently rewrite an old snapshot's meaning — the diff can see the versions differ and
say so instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")

from modules import atomicio

MANIFEST_NAME = "manifest.json"
INDEX_NAME = "index.json"
SUBDIRS = (".cache", "data", "serp", "checkpoints")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class RunFinalized(Exception):
    """Raised on any attempt to modify a run that has been finalized."""


@dataclass
class Run:
    run_id: str
    path: str


def _slug(s: str) -> str:
    return _SLUG_RE.sub("-", str(s or "").strip().lower()).strip("-")


def make_run_id(geography: str, practice: str, subject_type: str, run_date: str) -> str:
    return f"{_slug(geography)}_{_slug(practice)}_{_slug(subject_type)}_{run_date}"


def runs_root(root=None) -> Path:
    return Path(root or config.RUNS_DIR)


def manifest_path(run_path) -> Path:
    return Path(run_path) / MANIFEST_NAME


def read_manifest(run_path) -> dict:
    return atomicio.read_json(manifest_path(run_path), default={}) or {}


def _assert_open(run_path) -> dict:
    m = read_manifest(run_path)
    if m.get("status") == "complete":
        raise RunFinalized(f"{Path(run_path).name} is finalized; snapshots are immutable")
    return m


# ------------------------------------------------------------------ create / update
def create_run(root=None, *, geography: str, practice: str, subject_type: str,
               run_date: Optional[str] = None, query_threshold: Optional[int] = None,
               packs: Optional[dict] = None, notes: Optional[str] = None) -> Run:
    """Create a fresh run directory. Never reuses an existing id — collisions get a suffix."""
    root = runs_root(root)
    run_date = run_date or datetime.now().strftime("%Y-%m-%d")
    base = make_run_id(geography, practice, subject_type, run_date)
    run_id, n = base, 1
    while (root / run_id).exists():
        n += 1
        run_id = f"{base}-{chr(ord('a') + n - 1)}"   # -b, -c, ...
    path = root / run_id
    for sub in SUBDIRS:
        (path / sub).mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "geography": geography,
        "practice": practice,
        "subject_type": subject_type,
        "run_date": run_date,
        "query_threshold": query_threshold,
        "packs": packs or {},
        "notes": notes or "",
        "status": "running",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "denominators": {},
        "scoring": {},
        "completeness": {},
        "artifacts": {},
    }
    atomicio.write_json(path / MANIFEST_NAME, manifest, indent=2)
    _index_upsert(root, manifest)
    return Run(run_id=run_id, path=str(path))


def update_manifest(run_path, **fields) -> dict:
    """Shallow-merge fields into the manifest. Refuses to touch a finalized run."""
    m = _assert_open(run_path)
    m.update(fields)
    m["updated_at"] = datetime.now().isoformat(timespec="seconds")
    atomicio.write_json(manifest_path(run_path), m, indent=2)
    _index_upsert(Path(run_path).parent, m)
    return m


def record_artifact(run_path, name: str, rel_path: str, captured_at: Optional[str] = None) -> None:
    """Stamp when an artifact was captured — the data files themselves carry no timestamps."""
    m = _assert_open(run_path)
    arts = dict(m.get("artifacts") or {})
    arts[name] = {"path": rel_path,
                  "captured_at": captured_at or datetime.now().isoformat(timespec="seconds")}
    update_manifest(run_path, artifacts=arts)


def finalize_run(run_path) -> dict:
    m = _assert_open(run_path)
    m["status"] = "complete"
    m["finalized_at"] = datetime.now().isoformat(timespec="seconds")
    atomicio.write_json(manifest_path(run_path), m, indent=2)
    _index_upsert(Path(run_path).parent, m)
    return m


# ------------------------------------------------------------------ index
def index_path(root=None) -> Path:
    return runs_root(root) / INDEX_NAME


def _index_upsert(root, manifest: dict) -> None:
    root = Path(root)
    idx = atomicio.read_json(root / INDEX_NAME, default={"runs": []}) or {"runs": []}
    rows = [r for r in idx.get("runs", []) if r.get("run_id") != manifest.get("run_id")]
    rows.append({k: manifest.get(k) for k in
                 ("run_id", "geography", "practice", "subject_type", "run_date",
                  "query_threshold", "status", "created_at", "finalized_at", "web_signal")})
    rows.sort(key=lambda r: (r.get("run_date") or "", r.get("created_at") or ""), reverse=True)
    idx["runs"] = rows
    atomicio.write_json(root / INDEX_NAME, idx, indent=2)


def list_runs(root=None, **filters) -> list[dict]:
    """Runs newest-first, optionally filtered by any snapshot-key field."""
    idx = atomicio.read_json(index_path(root), default={"runs": []}) or {"runs": []}
    rows = idx.get("runs", [])
    for key, val in filters.items():
        rows = [r for r in rows if r.get(key) == val]
    return rows


def find_run(root=None, run_id: str = "") -> Optional[dict]:
    for r in list_runs(root):
        if r.get("run_id") == run_id:
            return r
    return None


def run_path(root=None, run_id: str = "") -> Path:
    return runs_root(root) / run_id


# ------------------------------------------------------------------ activation
def activate(run_path) -> str:
    """Point config's artifact paths at this run for the rest of the process."""
    return config.activate_run(run_path)


def deactivate() -> None:
    config.deactivate_run()
