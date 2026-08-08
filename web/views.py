"""Presentation-layer derived views for the v3 dashboards.

Every function here is PURE and consumes only what `modules/` already computes — this
is the presentation layer, and `modules/` stays frozen. Each one has a test file under
`tests/` (see the P2 section of the v3 plan); they are written test-first because the
dashboards are authored against their output and a wrong shape here is invisible until
a panel silently renders nothing.

Why a separate module rather than more of `build_web.py`: `build_web.py` is the
orchestrator (load caches -> score -> assemble -> inline -> write). These are pure
transforms with no I/O, so they test without touching the filesystem.
"""

from __future__ import annotations

import math
from collections import Counter
from statistics import median

# ── the four score bands. These are the SAME thresholds the visibility jewel
# state-maps on (docs/redesign/v3/ATLAS.md §5.2), so the colour a doctor sees and
# the band the market view counts can never disagree.
BANDS = [
    (0, 20, "alarm", "Nearly invisible"),
    (21, 50, "caution", "Below market"),
    (51, 79, "steady", "Partway there"),
    (80, 100, "clear", "Strong"),
]

# Platform families for SERP ownership. Anything unlisted falls to "other".
AGGREGATORS = {"justdial", "practo", "lybrate", "skedoc", "apollo247", "drlogy", "traya"}
SOCIAL = {"instagram", "facebook", "youtube"}

# Block types in the order a patient's eye travels down a Google results page.
BLOCK_ORDER = ["sponsored_top", "places", "sponsored_mid", "organic", "ai_overview"]

_CENTER = (16.3067, 80.4365)  # config.TARGET_LOCATION_LATLNG


def _isna(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


# ─────────────────────────────────────────────────────────── geography
def km_from_core(lat, lng, center: tuple[float, float] | None = None) -> float | None:
    """Kilometres from the Guntur city core.

    Deliberately re-implements `vulnerability._km_from_core` rather than importing a
    private name from a frozen module. `tests/test_km_from_core.py` pins the two
    together by asserting agreement across all 34 live clinics, so the duplication is
    documented and cannot drift silently.
    """
    if _isna(lat) or _isna(lng):
        return None
    cy, cx = center or _CENTER
    return math.hypot((float(lat) - cy) * 111.0, (float(lng) - cx) * 106.6)


# ─────────────────────────────────────────────────────────── distribution
def visibility_bands(clinics: list[dict]) -> dict:
    """Band counts plus the EMPIRICAL gaps in the visibility distribution.

    The gaps are computed, never hard-coded: the Guntur market happens to split at
    20->31 and 50->66 today, but a re-scrape would move them. The market view draws
    those voids as "the market splits here", so they have to come from the data.
    """
    vals = sorted(int(c["visibility"]) for c in clinics
                  if c.get("visibility") is not None)
    bands = [{"lo": lo, "hi": hi, "key": key, "label": label,
              "count": sum(1 for v in vals if lo <= v <= hi)}
             for lo, hi, key, label in BANDS]

    # Largest consecutive jumps between occupied values. Ties break on the lower
    # bound so the output is deterministic for screenshot verification.
    jumps = sorted(
        ({"lo": a, "hi": b, "size": b - a} for a, b in zip(vals, vals[1:]) if b - a > 1),
        key=lambda g: (-g["size"], g["lo"]),
    )
    return {"bands": bands, "gaps": jumps[:2], "values": vals,
            "min": vals[0] if vals else 0, "max": vals[-1] if vals else 0}


def band_of(visibility) -> str:
    """The band key a score falls in — the jewel recipe selector."""
    if visibility is None:
        return "alarm"
    v = int(visibility)
    for lo, hi, key, _ in BANDS:
        if lo <= v <= hi:
            return key
    return "clear" if v > 100 else "alarm"


# ─────────────────────────────────────────────────────────── the prescription
def plan_impact(clinic: dict, clinics: list[dict], market: dict) -> dict:
    """What each fix is worth, in points AND in market rank.

    The rank delta is the persuasive number the product has never had: "close this and
    you move #28 -> #19". It is computed by re-scoring the clinic with one component
    maxed and re-ranking it against the *unchanged* market — so it answers "if only I
    improve", which is the honest reading of a single clinic's decision.

    `clinic` and `clinics` are the normalized dicts `modules.report` consumes.
    Inputs are never mutated.
    """
    from modules import report

    def score(c):
        return report.visibility_score(c, market)

    # Rank through report.rank_by_visibility itself rather than reimplementing it.
    # The module ranks ORDINALLY (sort position), so ties get distinct ranks; a
    # competition ranking here would disagree with the clinic's published
    # `visibility_rank` whenever scores tie, and the header and the plan would show
    # two different numbers for the same fact.
    key_of = clinic.get("key")
    present = any(c.get("key") == key_of for c in clinics)

    def rank_for(variant):
        """1-based rank of `variant` against the unchanged rest of the market.

        The subject is SUBSTITUTED IN PLACE, never appended. `sorted()` is stable, so
        an appended subject would land last within its tie group and report a worse
        rank than the same clinic's published `visibility_rank`. Preserving position
        makes `plan.now.rank` reproduce that number exactly.
        """
        lst = ([variant if c.get("key") == key_of else c for c in clinics]
               if present else list(clinics) + [variant])
        for d in report.rank_by_visibility(lst, market):
            if d.get("key") == key_of:
                return d["rank"]
        return len(lst)

    now = score(clinic)
    rank_now = rank_for(clinic)

    # Maxing a component means satisfying whatever `report._components` measures.
    maxed = {
        "website": lambda c: {**c, "has_website": True},
        "search": lambda c: {**c, "owned": max(c.get("owned") or 0, report.OWNED_FULL)},
        "maps": lambda c: {**c, "places": max(c.get("places") or 0, report.PLACES_FULL)},
        "reviews": lambda c: {**c, "reviews": max(c.get("reviews") or 0,
                                                  market.get("avg_reviews") or 0)},
        "phone": lambda c: {**c, "has_phone": True},
        "breadth": lambda c: {**c, "web_appearances": max(c.get("web_appearances") or 0,
                                                          report.BREADTH_FULL)},
    }

    steps = []
    for comp in report.visibility_breakdown(clinic, market):
        key = comp["key"]
        lift = comp["max"] - comp["earned"]
        if lift < 2 or key not in maxed:
            continue  # already earned, or within rounding noise
        variant = maxed[key](clinic)
        after = score(variant)
        steps.append({
            "key": key,
            "label": comp["label"],
            "lift": round(lift),
            "vis_after": after,
            "rank_after": rank_for(variant),
        })
    steps.sort(key=lambda s: (-s["lift"], s["key"]))  # deterministic

    def compound(keys):
        c = dict(clinic)
        for k in keys:
            c = maxed[k](c)
        return {"vis": score(c), "rank": rank_for(c)}

    top2 = [s["key"] for s in steps[:2]]
    return {
        "now": {"vis": now, "rank": rank_now},
        "steps": steps,
        "compound": {"top2": compound(top2), "all": compound([s["key"] for s in steps])},
    }


# ─────────────────────────────────────────────────────────── SERP real estate
def _kind_of(platform: str, mapped_key: str) -> str:
    """Who owns this block: one of our clinics, an aggregator, a social profile, or
    somebody outside the Guntur market entirely."""
    p = (platform or "").lower()
    if mapped_key:
        return "own_clinic"
    if p in AGGREGATORS:
        return "aggregator"
    if p in SOCIAL:
        return "social"
    return "other"


def serp_ownership(block_rows: list[dict]) -> dict:
    """Who actually owns the Guntur dermatology result pages.

    Aggregated from the 1122-block corpus. We ship the AGGREGATE, never the raw rows —
    the matrix is ~19 domains and the drill-ins slice from it, so the payload carries
    ~12 KB instead of ~250 KB of JSON nobody scrolls.
    """
    by_domain: dict[str, dict] = {}
    by_type: Counter = Counter()
    queries: set = set()
    mapped = 0
    local_share: dict[str, dict] = {t: {"local": 0, "other": 0} for t in BLOCK_ORDER}

    for r in block_rows:
        btype = r.get("block_type") or "organic"
        key = r.get("mapped_key") or ""
        by_type[btype] += 1
        if r.get("query"):
            queries.add(r["query"])
        if key:
            mapped += 1
        bucket = local_share.setdefault(btype, {"local": 0, "other": 0})
        bucket["local" if key else "other"] += 1

        # Places blocks carry no domain; group them under their platform instead so
        # the local pack still appears in the matrix rather than as one blank row.
        domain = (r.get("domain") or "").strip().lower() or f"({r.get('platform') or 'unknown'})"
        d = by_domain.setdefault(domain, {
            "domain": domain, "platform": r.get("platform") or "other",
            "kind": _kind_of(r.get("platform"), key), "clinic_key": key or "",
            "clinic": r.get("mapped_clinic") or "",
            "blocks": 0, "queries": set(), "positions": [],
            "by_type": Counter(),
        })
        d["blocks"] += 1
        d["by_type"][btype] += 1
        if r.get("query"):
            d["queries"].add(r["query"])
        pos = r.get("position")
        if not _isna(pos):
            d["positions"].append(int(pos))
        if key and not d["clinic_key"]:  # first mapping wins, then it is stable
            d["clinic_key"], d["clinic"] = key, r.get("mapped_clinic") or ""
            d["kind"] = "own_clinic"

    domains = []
    for d in by_domain.values():
        positions = sorted(d["positions"])
        domains.append({
            "domain": d["domain"],
            "platform": d["platform"],
            "kind": d["kind"],
            "clinic_key": d["clinic_key"],
            "clinic": d["clinic"],
            "blocks": d["blocks"],
            "queries": len(d["queries"]),
            "by_type": {t: d["by_type"].get(t, 0) for t in BLOCK_ORDER},
            "best_position": positions[0] if positions else None,
            "median_position": round(median(positions), 1) if positions else None,
        })
    domains.sort(key=lambda d: (-d["blocks"], d["domain"]))

    total = len(block_rows)
    return {
        "totals": {
            "blocks": total,
            "queries": len(queries),
            "mapped": mapped,
            "unmapped": total - mapped,
            "by_type": {t: by_type.get(t, 0) for t in BLOCK_ORDER},
        },
        "domains": domains,
        "local_share": {t: local_share.get(t, {"local": 0, "other": 0}) for t in BLOCK_ORDER},
    }


def serp_page(block_rows: list[dict], query: str) -> list[dict]:
    """The ordered result page for ONE query — the data behind the redrawn SERP panel.

    Ordered the way a patient's eye travels: paid top, the local pack, paid mid, then
    organic. Within a group, by position; blocks with no position sort last but keep
    their relative order (stable), so a partially-extracted SERP degrades rather than
    scrambling.
    """
    rank = {t: i for i, t in enumerate(BLOCK_ORDER)}
    rows = [r for r in block_rows if (r.get("query") or "") == query]
    rows = sorted(
        enumerate(rows),
        key=lambda pair: (
            rank.get(pair[1].get("block_type"), len(BLOCK_ORDER)),
            float("inf") if _isna(pair[1].get("position")) else int(pair[1]["position"]),
            pair[0],
        ),
    )
    return [{
        "type": r.get("block_type") or "organic",
        "position": None if _isna(r.get("position")) else int(r["position"]),
        "domain": r.get("domain") or "",
        "platform": r.get("platform") or "other",
        "title": r.get("title") or "",
        "mapped_key": r.get("mapped_key") or "",
        "clinic": r.get("mapped_clinic") or "",
        "is_own_site": bool(r.get("is_own_site")),
        "kind": _kind_of(r.get("platform"), r.get("mapped_key") or ""),
    } for _, r in rows]


# ─────────────────────────────────────────────────────────── rail facets
def presence_of(clinic: dict) -> str:
    """own | borrowed | invisible — the clinic's web-estate group.

    Deliberately stricter than v2's `groupOf()` in app.js, in two ways:

    * A paid placement counts as OWNED. The ad points at the clinic's own site, so
      they control the destination — v2 called that "borrowed", which it is not.
    * Places-only presence counts as INVISIBLE. The local pack is Google Maps
      re-surfaced (`modules/web_screens.py` excludes it from web visibility for
      exactly this reason), so a clinic that appears *only* there is invisible in
      web search, and the facet label says so.

    Net effect on the live 34: own 12 / borrowed 2 / invisible 20, where v2 showed
    10 / 9 / 15. The counts moved because the rule got more honest, not because the
    data changed.
    """
    web = clinic.get("web") or {}
    if web.get("has_own_site") or (web.get("owned") or 0) > 0:
        return "own"
    if (web.get("borrowed") or 0) > 0 or web.get("platforms"):
        return "borrowed"
    return "invisible"


def market_facets(clinics: list[dict]) -> dict:
    """The counts behind the console rail's filter rows.

    Every facet count sums to len(clinics) except `ads`, which is a flag not a
    partition — the rail renders it as a single toggle rather than a group.
    """
    verdicts: Counter = Counter()
    presence: Counter = Counter()
    bands: Counter = Counter()
    for c in clinics:
        verdicts[c.get("verdict") or ""] += 1
        presence[presence_of(c)] += 1
        bands[band_of(c.get("visibility"))] += 1

    return {
        "verdict": [{"key": v, "label": v, "count": n}
                    for v, n in sorted(verdicts.items(), key=lambda kv: (-kv[1], kv[0]))],
        "presence": [{"key": k, "label": lbl, "count": presence.get(k, 0)} for k, lbl in
                     [("own", "Own site ranks"), ("borrowed", "Directories only"),
                      ("invisible", "Invisible in search")]],
        "band": [{"key": key, "label": label, "count": bands.get(key, 0)}
                 for _, _, key, label in reversed(BANDS)],
        "ads": sum(1 for c in clinics if (c.get("sponsored") or 0) > 0),
        "total": len(clinics),
    }
