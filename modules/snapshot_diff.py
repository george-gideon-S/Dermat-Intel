"""Compare two snapshots — the reason the product exists.

A single report tells a clinic where it stands. The comparison tells it whether it is gaining
or losing ground, which is what a quarterly subscription is actually selling. So the diff is
built to make "what changed" cheap and obvious: new clinics, clinics that dropped out, and
per-field deltas for the ones present in both.

Scores need a guard. `report.py`/`vulnerability.py` scores depend on saturation constants that
scale with each run's query counts, so a 62 scored under June's denominators and a 62 scored
under a 100-query run are not the same 62. When the two runs' scoring versions or constants
differ, score deltas are quarantined under `score_deltas_uncomparable` and the diff says
`scores_comparable: false` — while the RAW signals (reviews gained, website appeared, rank
moved) are always reported, because those are facts about the clinic, not about the scoring.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from modules import atomicio, runstore

# Fields whose delta is a plain numeric change.
_NUMERIC_FIELDS = ("rating", "reviews", "maps_position", "owned", "borrowed",
                   "places", "web_appearances", "appearances")
# Fields that only mean anything if the two runs are score-comparable.
_SCORE_FIELDS = ("visibility_score", "vulnerability_score")


def _num(v):
    try:
        if v is None:
            return None
        f = float(v)
        return f if f == f else None   # drop NaN
    except (TypeError, ValueError):
        return None


def _has_text(v) -> bool:
    """True only for a real non-empty string. Guards against pandas NaN, whose str() is 'nan'."""
    if v is None:
        return False
    if isinstance(v, float) and v != v:   # NaN
        return False
    return bool(str(v).strip())


def _delta(a, b):
    na, nb = _num(a), _num(b)
    if na is None or nb is None:
        return None
    d = nb - na
    return round(d, 3) if isinstance(d, float) else d


def diff_clinics(a: list[dict], b: list[dict], comparable: bool = True) -> dict:
    """Pure diff of two clinic lists keyed on `key`."""
    ai = {c.get("key"): c for c in a if c.get("key")}
    bi = {c.get("key"): c for c in b if c.get("key")}

    new = [bi[k] for k in bi if k not in ai]
    lost = [ai[k] for k in ai if k not in bi]

    changed = []
    for k in ai:
        if k not in bi:
            continue
        ca, cb = ai[k], bi[k]
        deltas, uncomparable = {}, {}
        for f in _NUMERIC_FIELDS:
            if f in ca or f in cb:
                d = _delta(ca.get(f), cb.get(f))
                if d not in (None, 0):
                    deltas[f] = d
        for f in _SCORE_FIELDS:
            d = _delta(ca.get(f), cb.get(f))
            if d in (None, 0):
                continue
            (deltas if comparable else uncomparable)[f] = d

        wa, wb = bool(ca.get("has_website")), bool(cb.get("has_website"))
        entry = {
            "key": k, "name": cb.get("name") or ca.get("name"),
            "deltas": deltas,
            "website_gained": (not wa) and wb,
            "website_lost": wa and (not wb),
        }
        if uncomparable:
            entry["score_deltas_uncomparable"] = uncomparable
        if deltas or entry["website_gained"] or entry["website_lost"] or uncomparable:
            changed.append(entry)

    changed.sort(key=lambda e: e["name"] or "")
    return {
        "scores_comparable": comparable,
        "new": sorted(new, key=lambda c: c.get("name") or ""),
        "lost": sorted(lost, key=lambda c: c.get("name") or ""),
        "changed": changed,
        "summary": {"new": len(new), "lost": len(lost), "changed": len(changed),
                    "clinics_a": len(ai), "clinics_b": len(bi)},
    }


# ------------------------------------------------------------------ version guard
def scores_comparable(manifest_a: dict, manifest_b: dict) -> bool:
    """Two runs' scores mean the same thing only if version AND saturation constants match."""
    sa = (manifest_a or {}).get("scoring") or {}
    sb = (manifest_b or {}).get("scoring") or {}
    if sa.get("scoring_version") != sb.get("scoring_version"):
        return False
    for key in ("DEMAND_FULL", "OWNED_FULL", "BORROWED_FULL", "PLACES_FULL", "BREADTH_FULL"):
        if sa.get(key) != sb.get(key):
            return False
    return True


# ------------------------------------------------------------------ run loader
def load_clinics(run_dir) -> list[dict]:
    """Read one snapshot's scored clinics into the diff's flat shape.

    Prefers a clinics.json if present; otherwise reads the unified xlsx the scoring stage
    writes. Keeps only the fields the diff compares, keyed by the shared clinic identity.
    """
    run_dir = Path(run_dir)
    cached = atomicio.read_json(run_dir / "data" / "clinics.json", default=None)
    rows = cached if cached is not None else _read_unified_xlsx(run_dir / "data" / "unified_results.xlsx")
    from modules.maps_collector import dedup_key
    out = []
    for r in rows:
        key = dedup_key(str(r.get("place_url") or "")) or str(r.get("name") or "").strip().lower()
        out.append({
            "key": key,
            "name": r.get("name"),
            "rating": _num(r.get("rating")),
            "reviews": _num(r.get("user_ratings_total")),
            # NaN-safe: pandas reads an empty xlsx cell as float('nan'), and str(nan) == "nan"
            # is truthy — so a naive truthiness check marks a websiteless clinic as having one,
            # flipping the website_gained/website_lost signal in the diff.
            "has_website": _has_text(r.get("website")),
            "maps_position": _num(r.get("result_position_avg")),
            "owned": _num(r.get("web_owned_appearances")),
            "borrowed": _num(r.get("web_borrowed_appearances")),
            "places": _num(r.get("in_places_count")),
            "appearances": _num(r.get("appearances")),
            "web_appearances": _num(r.get("web_appearances")),
            "vulnerability_score": _num(r.get("vulnerability_score")),
            "visibility_score": _num(r.get("visibility_score")),
        })
    return out


#: unified_results.xlsx uses display headers and omits place_url, so it is only a lossy
#: fallback. The canonical source is data/clinics.json, written by the score stage.
_XLSX_HEADER_MAP = {
    "Clinic": "name", "Rating": "rating", "Reviews": "user_ratings_total",
    "Website": "website", "Maps Appearances": "appearances",
    "Web Appearances": "web_appearances", "Owned (own-site/ads)": "web_owned_appearances",
    "Borrowed (aggregators)": "web_borrowed_appearances", "In Places": "in_places_count",
    "Opportunity Score": "vulnerability_score",
}


def _read_unified_xlsx(path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    import pandas as pd
    df = pd.read_excel(path).rename(columns=_XLSX_HEADER_MAP)
    return df.to_dict("records")


def build_clinic_records(scored_df, ctx=None, params=None) -> list[dict]:
    """Canonical per-clinic records for the diff, from a scored dataframe.

    This is where the clinic identity (dedup_key over place_url) and BOTH scores are captured
    together — the xlsx has neither the place_url nor the clinic-facing visibility score, so it
    can never be the source of truth for a diff.
    """
    from modules import report, report_adapter as ra
    rows = scored_df.to_dict("records") if hasattr(scored_df, "to_dict") else list(scored_df)
    leagues = ra.markets_by_league(rows, ctx) if ctx is not None else {}
    flat_market = ra.market_from_rows(rows)
    out = []
    for r in rows:
        norm = ra.norm_clinic(r, ctx=ctx)
        market = ra.market_for(r, ctx, leagues) if ctx is not None else flat_market
        out.append({
            "key": norm["key"],
            "name": norm["name"],
            "rating": _num(r.get("rating")),
            "reviews": norm["reviews"],
            "has_website": norm["has_website"],
            "maps_position": _num(r.get("result_position_avg")),
            "owned": norm["owned"],
            "borrowed": norm["borrowed"],
            "places": norm["places"],
            "appearances": norm["appearances"],
            "web_appearances": norm["web_appearances"],
            "subject_class": norm.get("subject_class"),
            "vulnerability_score": _num(r.get("vulnerability_score")),
            "visibility_score": report.visibility_score(norm, market, params=params),
        })
    return out


def write_clinics_json(run_dir, scored_df, ctx=None, params=None) -> str:
    """Persist the canonical clinic records so any later diff reads them, not the lossy xlsx."""
    records = build_clinic_records(scored_df, ctx=ctx, params=params)
    dest = Path(run_dir) / "data" / "clinics.json"
    atomicio.write_json(dest, records, indent=2)
    return str(dest)


def diff_runs(run_a_dir, run_b_dir) -> dict:
    """Diff two snapshots by directory, applying the score-comparability guard from manifests."""
    ma = runstore.read_manifest(run_a_dir)
    mb = runstore.read_manifest(run_b_dir)
    comparable = scores_comparable(ma, mb)
    d = diff_clinics(load_clinics(run_a_dir), load_clinics(run_b_dir), comparable=comparable)
    d["run_a"] = Path(run_a_dir).name
    d["run_b"] = Path(run_b_dir).name
    d["run_a_date"] = ma.get("run_date")
    d["run_b_date"] = mb.get("run_date")
    if not comparable:
        d["comparability_note"] = (
            f"scores computed under different rules "
            f"({ma.get('scoring', {}).get('scoring_version')} vs "
            f"{mb.get('scoring', {}).get('scoring_version')}); raw-signal deltas are comparable, "
            f"score deltas are not")
    return d


def diff_by_id(root, run_id_a: str, run_id_b: str) -> dict:
    return diff_runs(str(runstore.run_path(root, run_id_a)),
                     str(runstore.run_path(root, run_id_b)))
