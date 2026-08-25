"""Turn Google's relative review dates into absolute ones, anchored to the capture date.

Google gives "2 months ago" and nothing else. That phrase is only interpretable relative to
when it was read, so storing it raw makes review recency un-diffable: the same June review
still reads "2 months ago" next quarter, and any trend computed from it is an artifact of when
you looked rather than of the market.

Resolving at capture time fixes that. Two honesty rules:

* the raw phrase is kept — it is the evidence, the resolved date is the interpretation;
* precision is recorded ("month", not a day). "2 months ago" is a ~30-day bucket, and
  reporting it as an exact day would be inventing data the source never had.

reviews_nlp already warns that ~10 reviews per clinic is too thin for trend claims; this
module makes the dates comparable, it does not make the sample bigger.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional, Union

_UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365, "hour": 0, "minute": 0, "second": 0}
_REL_RE = re.compile(
    r"\b(?:(\d+)|(a|an))\s+(second|minute|hour|day|week|month|year)s?\s+ago\b", re.I)

DateLike = Union[date, str]


def _as_date(anchor: DateLike) -> date:
    if isinstance(anchor, date):
        return anchor
    return date.fromisoformat(str(anchor)[:10])


def relative_to_days(text: Optional[str]) -> Optional[int]:
    """'2 months ago' -> 60. Returns None when the phrase is not a relative date."""
    if not text:
        return None
    m = _REL_RE.search(str(text))
    if not m:
        return None
    n = int(m.group(1)) if m.group(1) else 1
    return n * _UNIT_DAYS[m.group(3).lower()]


def precision_of(text: Optional[str]) -> Optional[str]:
    """The granularity Google actually gave us — never finer than the source."""
    if not text:
        return None
    m = _REL_RE.search(str(text))
    if not m:
        return None
    unit = m.group(3).lower()
    return unit if unit in ("day", "week", "month", "year") else "day"


def resolve(text: Optional[str], anchor: DateLike) -> Optional[str]:
    """Absolute ISO date for a relative phrase, or None if it cannot be parsed."""
    days = relative_to_days(text)
    if days is None:
        return None
    return (_as_date(anchor) - timedelta(days=days)).isoformat()


def resolve_review(review: dict, anchor: DateLike) -> dict:
    """Copy of `review` with absolute date fields added; the raw phrase is preserved."""
    out = dict(review or {})
    raw = out.get("relative_date")
    out["reviewed_on"] = resolve(raw, anchor)
    out["reviewed_on_precision"] = precision_of(raw)
    out["captured_on"] = _as_date(anchor).isoformat()
    return out


def resolve_all(reviews_by_clinic: dict, anchor: DateLike) -> dict:
    """Resolve a whole reviews_raw.json cache. The `_meta` key is passed through untouched."""
    out = {}
    for key, value in (reviews_by_clinic or {}).items():
        if key == "_meta":
            out[key] = value
            continue
        out[key] = [resolve_review(r, anchor) for r in (value or [])]
    return out


def coverage(resolved_by_clinic: dict) -> dict:
    """How much of the corpus carries a usable date — a completeness field, not a score."""
    reviews = resolved = 0
    for key, value in (resolved_by_clinic or {}).items():
        if key == "_meta":
            continue
        for r in value or []:
            reviews += 1
            if r.get("reviewed_on"):
                resolved += 1
    return {"reviews": reviews, "resolved": resolved, "unresolved": reviews - resolved,
            "resolved_pct": round(100.0 * resolved / reviews, 1) if reviews else 0.0}
