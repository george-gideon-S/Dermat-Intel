"""Public-dist anonymizer (spec 2026-07-10 §3 — "anonymize until paid").

Pure functions: full payload in → public payload out. The public payload is what ships
to Vercel, so the invariant is absolute: no real clinic name token, exact review count,
exact score, or website URL may survive. `tests/test_public_data.py` enforces it; the
build adds a second tripwire against the rendered HTML.

The self-lookup uses salted FNV-1a 32-bit hashes — deterministic and trivially mirrored
in client JS (`Math.imul(h ^ c, 16777619) >>> 0`). Obfuscation, not security: the names
are public Google data; what we refuse to publish is the *assessment* attached to them.
"""
from __future__ import annotations

import math
import re

FNV_BASIS = 2166136261
FNV_PRIME = 16777619

# Generic words that don't identify a clinic — dropped so only distinctive tokens remain.
STOP = {
    "clinic", "clinics", "skin", "hair", "care", "dr", "doctor", "the", "and",
    "centre", "center", "hospital", "derma", "dermatology", "dermatologist",
    "cosmetic", "laser", "guntur",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def fnv1a(s: str) -> int:
    h = FNV_BASIS
    for ch in s:
        h = ((h ^ ord(ch)) * FNV_PRIME) & 0xFFFFFFFF
    return h


def name_tokens(name: str) -> list:
    toks = _TOKEN_RE.findall((name or "").lower())
    return [t for t in toks if len(t) >= 3 and t not in STOP]


def norm_full(name: str) -> str:
    """Whole-name normalization for the exact-match hash (keeps generic words)."""
    return "".join(_TOKEN_RE.findall((name or "").lower()))


def rank_bucket(rank: int, total: int) -> str:
    if rank <= 10:
        return "top 10"
    if rank <= 20:
        return "11–20"
    return f"21–{total}"


def reviews_band(n) -> str:
    n = n or 0
    if n >= 200:
        return "200+"
    if n >= 100:
        return "100+"
    if n >= 50:
        return "50+"
    return "under 50"


def rating_band(r):
    if not r:
        return None
    return f"{math.floor(float(r) * 2) / 2:.1f}+"


def _beeswarm(clinics: list, salt: str) -> list:
    order = sorted(range(len(clinics)), key=lambda i: clinics[i].get("appearances") or 0)
    n = len(order)
    xs = {}
    for pos, idx in enumerate(order):
        xs[idx] = 50 if n == 1 else round(4 + 92 * pos / (n - 1))
    return [
        {
            "x": xs[i],
            "y": fnv1a((c.get("name") or "") + salt) % 61 - 30,
            "inv": not c.get("has_website"),
        }
        for i, c in enumerate(clinics)
    ]


def _lookup(clinics: list, salt: str) -> list:
    out = []
    for c in clinics:
        name = c.get("name") or ""
        out.append({
            "h": fnv1a(norm_full(name) + salt),
            "t": [fnv1a(t + salt) for t in name_tokens(name)],
            "inv": not c.get("has_website"),
            "bucket": rank_bucket(c.get("visibility_rank") or 1,
                                  c.get("visibility_total") or len(clinics)),
        })
    return out


def _teasers(clinics: list, median_app: float) -> list:
    invisible = [c for c in clinics if not c.get("has_website")]
    invisible.sort(key=lambda c: c.get("appearances") or 0, reverse=True)
    out = []
    for i, c in enumerate(invisible[:3]):
        out.append({
            "letter": chr(ord("A") + i),
            "rating_band": rating_band(c.get("rating")),
            "reviews_band": reviews_band(c.get("reviews")),
            "demand": "high" if (c.get("appearances") or 0) > median_app else "steady",
        })
    return out


def _sample_queries(qrows: list, clinics: list, limit: int = 8) -> list:
    banned = set()
    for c in clinics:
        banned.update(name_tokens(c.get("name") or ""))
    out = []
    for row in qrows:
        q = str(row.get("query") or "").strip()
        if not q:
            continue
        if set(_TOKEN_RE.findall(q.lower())) & banned:
            continue  # branded query — would leak a clinic name
        out.append(q)
        if len(out) >= limit:
            break
    return out


def _owned_borrowed(clinics: list) -> dict:
    owned = borrowed_only = invisible = 0
    for c in clinics:
        web = c.get("web") or {}
        if c.get("has_own_site"):
            owned += 1
        elif (web.get("borrowed") or 0) > 0:
            borrowed_only += 1
        else:
            invisible += 1
    return {"owned": owned, "borrowed_only": borrowed_only, "invisible": invisible}


def build_public_payload(full: dict, qrows: list, cfg: dict, salt: str) -> dict:
    clinics = full.get("clinics") or []
    k = full.get("kpis") or {}
    return {
        "generated_at": full.get("generated_at"),
        "city": full.get("city"),
        "kpis": {
            "unique_clinics": k.get("unique_clinics"),
            "no_website_count": k.get("no_website_count"),
            "avg_rating": k.get("avg_rating"),
            "pct_with_website": k.get("pct_with_website"),
            "queries": k.get("queries"),
        },
        "beeswarm": _beeswarm(clinics, salt),
        "lookup": _lookup(clinics, salt),
        "teasers": _teasers(clinics, float(full.get("median_appearances") or 0)),
        "queries": _sample_queries(qrows, clinics),
        "owned_borrowed": _owned_borrowed(clinics),
        "pricing": {
            "report": cfg.get("report"),
            "monitor_qtr": cfg.get("monitor_qtr"),
            "monitor_yr": cfg.get("monitor_yr"),
            "build_from": cfg.get("build_from"),
            "retainer_mo": cfg.get("retainer_mo"),
            "rzp_report": cfg.get("rzp_report") or "",
            "rzp_monitor_qtr": cfg.get("rzp_monitor_qtr") or "",
            "rzp_monitor_yr": cfg.get("rzp_monitor_yr") or "",
            "whatsapp": cfg.get("whatsapp") or "",
        },
    }
