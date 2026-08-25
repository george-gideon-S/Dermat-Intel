"""Bridge: scored/unified clinic rows -> the plain dict modules/report consumes.

Recovered from `git show 2ff72b3:web/build_web.py` (it was deleted with the UI layer, which
left `modules/report.py` with no way to be fed) and extended with the subject-type leagues.

Why leagues: a multi-specialty hospital and a solo practitioner are not comparable units. The
hospital wins on review volume and appearance counts through sheer institutional size, none of
which says anything about its dermatology. Pooling them makes every small clinic look weak
against a benchmark it could never meet, so market averages are computed per league and the
league is a visible column rather than buried arithmetic.
"""
from __future__ import annotations

import math
import statistics
from typing import Optional

from modules import packs
from modules.maps_collector import dedup_key

LEAGUES = ("clinic", "hospital", "ambiguous")


def _isna(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    return False


def _num0(v) -> int:
    return 0 if _isna(v) else int(round(float(v)))


def _text(v) -> str:
    return "" if _isna(v) else str(v).strip()


def _row_get(row, key, default=None):
    """Accept a dict or a pandas Series without importing pandas."""
    try:
        val = row.get(key, default)
    except AttributeError:  # pragma: no cover
        val = getattr(row, key, default)
    return default if val is None else val


def clinic_key(row) -> str:
    """The identity every other module keys on — CID first, lowercased name as fallback."""
    return dedup_key(_text(_row_get(row, "place_url", ""))) or _text(_row_get(row, "name", "")).lower()


def norm_clinic(row, ctx=None) -> dict:
    """Normalize one scored row into report's input dict."""
    website = _text(_row_get(row, "website", ""))
    phone = _text(_row_get(row, "formatted_phone_number", ""))
    rating = _row_get(row, "rating", None)
    out = {
        "name": _row_get(row, "name", ""),
        "key": clinic_key(row),
        "has_website": bool(website),
        "owned": _num0(_row_get(row, "web_owned_appearances", 0)),
        "borrowed": _num0(_row_get(row, "web_borrowed_appearances", 0)),
        "places": _num0(_row_get(row, "in_places_count", 0)),
        "reviews": _num0(_row_get(row, "user_ratings_total", 0)),
        "rating": 0.0 if _isna(rating) else float(rating),
        "appearances": _num0(_row_get(row, "appearances", 0)),
        "has_phone": bool(phone),
        "web_appearances": _num0(_row_get(row, "web_appearances", 0)),
        "has_own_site": bool(_row_get(row, "has_own_site", False))
                        if not _isna(_row_get(row, "has_own_site", None)) else False,
        "platforms": list(_row_get(row, "platforms", []) or []),
    }
    if ctx is not None:
        cls, basis = ctx.classify_subject_with_basis(out["name"], _text(_row_get(row, "types", "")))
        out["subject_class"] = cls
        out["subject_basis"] = basis
    return out


def classification_report(rows, ctx) -> dict:
    """How each subject label was reached — a completeness field for the run manifest.

    Google Maps category strings are frequently absent (the June snapshot has none at all), so
    the split between category-based and name-based labels is the honest measure of how much
    to trust the leagues. A high `unclassified` count means the leagues are thin, not that the
    market is unusual.
    """
    counts = {"category": 0, "name": 0, "unclassified": 0}
    for row in rows or []:
        _, basis = ctx.classify_subject_with_basis(
            _text(_row_get(row, "name", "")), _text(_row_get(row, "types", "")))
        counts[basis] = counts.get(basis, 0) + 1
    total = sum(counts.values()) or 1
    return {"counts": counts, "total": total,
            "category_pct": round(100.0 * counts["category"] / total, 1),
            "unclassified_pct": round(100.0 * counts["unclassified"] / total, 1)}


def norm_clinics(rows, ctx=None, web_by_clinic: Optional[dict] = None) -> list[dict]:
    """Normalize many rows, attaching the platform list the scorecard names."""
    web_by_clinic = web_by_clinic or {}
    out = []
    for row in rows:
        d = norm_clinic(row, ctx=ctx)
        if not d["platforms"]:
            d["platforms"] = (web_by_clinic.get(d["key"]) or {}).get("platforms", [])
        out.append(d)
    return out


# ------------------------------------------------------------------ market stats
def market_from_rows(rows) -> dict:
    """The `market` dict report compares a clinic against.

    Mirrors analytics.kpis, but tolerates an empty market: a zero divisor here would turn
    every 'reviews vs market' component into a NaN score rather than an honest zero.
    """
    reviews, ratings, appearances = [], [], []
    for row in rows or []:
        r = _row_get(row, "user_ratings_total", None)
        if not _isna(r):
            reviews.append(float(r))
        g = _row_get(row, "rating", None)
        if not _isna(g):
            ratings.append(float(g))
        a = _row_get(row, "appearances", None)
        if not _isna(a):
            appearances.append(float(a))
    return {
        "avg_reviews": max(1.0, statistics.fmean(reviews)) if reviews else 1.0,
        "avg_rating": round(statistics.fmean(ratings), 2) if ratings else 0.0,
        "median_appearances": statistics.median(appearances) if appearances else 0.0,
        "n_clinics": len(list(rows or [])),
    }


def league_of(row, ctx) -> str:
    return ctx.classify_subject(_text(_row_get(row, "name", "")), _text(_row_get(row, "types", "")))


def markets_by_league(rows, ctx) -> dict:
    """One market dict per subject league present in the data."""
    buckets: dict[str, list] = {}
    for row in rows or []:
        buckets.setdefault(league_of(row, ctx), []).append(row)
    return {league: market_from_rows(items) for league, items in buckets.items()}


def market_for(row, ctx, leagues: dict) -> dict:
    """The benchmark a given clinic should be judged against — its own league."""
    league = league_of(row, ctx)
    return leagues.get(league) or market_from_rows([])


def filter_rows(rows, ctx) -> list:
    """Apply the run's subject_type filter. Ambiguous rows always survive: dropping them would
    hide real clinics because a category string was blank."""
    return [r for r in (rows or []) if ctx.includes_subject(league_of(r, ctx))]


def league_counts(rows, ctx) -> dict:
    counts = {k: 0 for k in LEAGUES}
    for row in rows or []:
        counts[league_of(row, ctx)] = counts.get(league_of(row, ctx), 0) + 1
    return counts
