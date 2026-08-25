"""Read model over a gmaps survey snapshot: clinic rows with coordinates.

The gmaps summary (data.json) deliberately drops lat/lng/place_url (KEEP_FIELDS in
gmaps/run.py) because the live viewer never needed them. Any consumer that has to place a
clinic on a map does, so this module joins data.json with feed.json's cards — the cheapest
coordinate source — and falls back to places/<key>.json per missing key. Join key is
place_id (== key): "Join on place_id. Never on name or address."
(gmaps/docs/05-output-schema.md).

Degradation is loud: a missing run raises MarketRunNotFound naming the searched path; a
missing/unreadable feed.json becomes a warning plus per-row coords_missing flags, never a
silently thinner list.
"""
from __future__ import annotations

import json
from pathlib import Path

import config


class MarketRunNotFound(Exception):
    pass


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def latest_run(geography: str, specialty: str) -> Path:
    """Newest runs/gmaps/{geography}_{specialty}_<date>/ by name (dates sort lexically).

    Directory names are the contract (index.json stores repo-relative Windows paths that
    break under relocated roots, so it is deliberately not consulted). Underscore-prefixed
    dirs are aborted runs and never candidates.
    """
    root = Path(config.GMAPS_RUNS_DIR)
    prefix = f"{geography}_{specialty}_"
    candidates = sorted(
        p for p in (root.glob(prefix + "*") if root.exists() else [])
        if p.is_dir() and not p.name.startswith("_")
    )
    if not candidates:
        raise MarketRunNotFound(
            f"no gmaps run for {geography}/{specialty} under {root}"
        )
    return candidates[-1]


def run_dir(geography: str, specialty: str, run_id: str) -> Path:
    """A pinned snapshot by id; 404-able."""
    path = Path(config.GMAPS_RUNS_DIR) / run_id
    if not path.is_dir() or run_id.startswith("_"):
        raise MarketRunNotFound(f"no gmaps run {run_id!r} under {config.GMAPS_RUNS_DIR}")
    return path


def load_market(run: Path) -> dict:
    rows = _read_json(run / "data.json")
    warnings: list[str] = []

    coords: dict[str, tuple] = {}
    feed_path = run / "feed.json"
    try:
        for card in _read_json(feed_path).get("cards", []):
            key = card.get("key") or card.get("place_id")
            if key and card.get("lat") is not None:
                coords[key] = (card["lat"], card["lng"])
    except (OSError, ValueError) as exc:
        warnings.append(f"feed.json unreadable ({exc.__class__.__name__}) — "
                        "coordinates fall back to places/ per clinic")

    manifest = {}
    try:
        manifest = _read_json(run / "manifest.json")
    except (OSError, ValueError):
        warnings.append("manifest.json unreadable — captured_at/run_health unknown")
    health = manifest.get("run_health")
    if health and health != "complete":
        warnings.append(f"run health: {health} — some place pages failed during capture")

    clinics = []
    counts = {"captured": len(rows), "relevant": 0, "adjacent": 0, "irrelevant": 0}
    for row in rows:
        key = row.get("key")
        latlng = coords.get(key)
        if latlng is None:
            try:
                place = _read_json(run / "places" / f"{key}.json")
                if place.get("lat") is not None:
                    latlng = (place["lat"], place["lng"])
            except (OSError, ValueError):
                latlng = None
        relevance = row.get("relevance", "irrelevant")
        if relevance in counts:
            counts[relevance] += 1
        clinics.append({
            "key": key,
            "name": row.get("name_clean") or row.get("name_raw") or "",
            "phone": row.get("phone") or "",
            "rating": row.get("rating"),
            "reviews_total": row.get("reviews_total"),
            "address": row.get("address") or "",
            "lat": latlng[0] if latlng else None,
            "lng": latlng[1] if latlng else None,
            "coords_missing": latlng is None,
            "relevance": relevance,
            "tier": row.get("tier"),
            "has_own_website": bool(row.get("has_own_website")),
        })

    missing = sum(1 for c in clinics if c["coords_missing"])
    if missing:
        warnings.append(f"{missing} of {len(clinics)} places have no coordinates")

    return {
        "run_id": run.name,
        "geography": manifest.get("geography"),
        "specialty": manifest.get("specialty"),
        "city": manifest.get("city"),
        "captured_at": manifest.get("finished_at") or manifest.get("started_at"),
        "counts": counts,
        "warnings": warnings,
        "clinics": clinics,
    }
