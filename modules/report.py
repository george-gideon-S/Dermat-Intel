"""Doctor-facing content engine — the "Your clinic" report + the comparative market view.

Turns the scored clinic data into plain-language, **higher-is-better** signals a dermatologist instantly
understands. Unlike the internal opportunity score (higher = weaker = a better sales prospect), these are
clinic-facing: an Online Visibility score, a five-check scorecard, you-vs-market benchmarks, a one-line
verdict, the market summary + the clinic's rank, and the real-SERP "proof" (a high-demand patient search
where the clinic is absent while competitors show up). Pure functions over a normalized clinic dict:

    {name, key, has_website, owned, borrowed, places, reviews, rating, appearances,
     has_phone, web_appearances, has_own_site, platforms[]}
"""
from __future__ import annotations

_PLATFORM_LABEL = {
    "practo": "Practo", "justdial": "JustDial", "lybrate": "Lybrate", "skedoc": "Skedoc",
    "sulekha": "Sulekha", "drlogy": "Drlogy", "apollo247": "Apollo 24|7",
    "bajajfinservhealth": "Bajaj Health", "instagram": "Instagram", "facebook": "Facebook",
    "youtube": "YouTube", "traya": "Traya",
}
OWNED_FULL = 6        # own-site/ad appearances that count as "fully visible in search"
PLACES_FULL = 8       # map-pack appearances that count as fully present on Maps
BREADTH_FULL = 10     # total search appearances that count as broadly findable


def _label_platforms(platforms) -> list[str]:
    return [_PLATFORM_LABEL.get(p, str(p).title()) for p in (platforms or [])]


def _present_label(x: str) -> str:
    return _PLATFORM_LABEL.get(x, x) if x else ""


# --------------------------------------------------------------------------- Online Visibility (higher=better)
def visibility_score(c: dict, market: dict) -> int:
    """0–100 clinic-facing "how findable are you online" score (higher = more present).

    Website 30 · own-site ranks in search 30 · on the Maps pack 15 · reviews vs market 15 ·
    phone 5 · breadth of search presence 5.
    """
    avg_rev = market.get("avg_reviews") or 1
    s = 0.0
    s += 30 if c.get("has_website") else 0
    s += 30 * min((c.get("owned") or 0) / OWNED_FULL, 1.0)
    s += 15 * min((c.get("places") or 0) / PLACES_FULL, 1.0)
    s += 15 * min((c.get("reviews") or 0) / avg_rev, 1.0)
    s += 5 if c.get("has_phone") else 0
    s += 5 * min((c.get("web_appearances") or 0) / BREADTH_FULL, 1.0)
    return round(s)


# --------------------------------------------------------------------------- five-check scorecard
def scorecard(c: dict, market: dict) -> list[dict]:
    """Five plain checks (good | warn | bad) a doctor reads at a glance."""
    avg_rev = market.get("avg_reviews") or 1
    reviews = c.get("reviews") or 0
    owned, borrowed = c.get("owned") or 0, c.get("borrowed") or 0
    places = c.get("places") or 0
    plats = ", ".join(_label_platforms(c.get("platforms"))) or "directories"

    website = {"key": "website", "label": "Own website",
               "status": "good" if c.get("has_website") else "bad",
               "value": "Yes" if c.get("has_website") else "None",
               "note": "Patients can learn about you and book online." if c.get("has_website")
               else "Patients who Google you have no site of yours to land on."}

    if c.get("has_own_site") or owned > 0:
        search = {"status": "good", "value": "Your site ranks",
                  "note": "Your own clinic website shows up in Google search results."}
    elif borrowed > 0 or c.get("platforms"):
        search = {"status": "warn", "value": f"Only via {plats}",
                  "note": f"You're found only through {plats} — you don't own that listing or the patient."}
    else:
        search = {"status": "bad", "value": "Not found",
                  "note": "Your clinic doesn't appear in Google web search at all."}
    search.update({"key": "search", "label": "Google search"})

    maps = {"key": "maps", "label": "Google Maps",
            "status": "good" if places > 0 else "bad",
            "value": "In the map pack" if places > 0 else "Not in the pack",
            "note": "You appear on the map when patients search nearby." if places > 0
            else "You're missing from the local map results."}

    rstat = "good" if reviews >= avg_rev else ("warn" if reviews >= 0.75 * avg_rev else "bad")
    rev = {"key": "reviews", "label": "Google reviews", "status": rstat,
           "value": f"{reviews} vs {round(avg_rev)} avg",
           "note": "Above the Guntur average." if rstat == "good"
           else "Below the Guntur average — more reviews build trust."}

    phone = {"key": "phone", "label": "Phone listed",
             "status": "good" if c.get("has_phone") else "bad",
             "value": "Yes" if c.get("has_phone") else "None",
             "note": "Patients can call you directly." if c.get("has_phone")
             else "No number for patients to call."}
    return [website, search, maps, rev, phone]


# --------------------------------------------------------------------------- one-line verdict
def verdict(c: dict, market: dict) -> str:
    has_site = bool(c.get("has_website"))
    owned = c.get("owned") or 0
    places = c.get("places") or 0
    if not has_site and owned == 0:
        return ("Trusted in person but invisible online — no website, and your clinic doesn't rank "
                "in Google search." if places > 0
                else "Almost no online presence — patients searching Google won't find you.")
    if not has_site and owned > 0:
        return "You rank in search but have no website to send those patients to."
    if has_site and owned == 0:
        return "You have a website, but it isn't ranking — patients aren't finding it in Google search."
    return "Solid online presence — only a few gaps left to close."


# --------------------------------------------------------------------------- you-vs-market benchmarks
def benchmarks(c: dict, market: dict) -> list[dict]:
    rev, arev = c.get("reviews") or 0, round(market.get("avg_reviews") or 0)
    rat, arat = c.get("rating") or 0, market.get("avg_rating") or 0
    app, mapp = c.get("appearances") or 0, market.get("median_appearances") or 0
    return [
        {"key": "reviews", "label": "Google reviews", "you": rev, "market": arev, "better": rev >= arev},
        {"key": "rating", "label": "Rating", "you": rat, "market": arat, "better": rat >= arat},
        {"key": "demand", "label": "Patient searches you show in", "you": app, "market": mapp,
         "better": app >= mapp},
    ]


# --------------------------------------------------------------------------- market view: summary + rank
def market_summary(clinics: list[dict], market: dict) -> dict:
    n = len(clinics)
    no_website = sum(1 for c in clinics if not c.get("has_website"))
    return {
        "total": n,
        "no_website": no_website,
        "no_website_pct": round(100 * no_website / n) if n else 0,
        "zero_web_presence": sum(1 for c in clinics if (c.get("web_appearances") or 0) == 0),
        "own_site": sum(1 for c in clinics if c.get("has_own_site")),
        "avg_rating": market.get("avg_rating"),
        "avg_reviews": round(market.get("avg_reviews") or 0),
    }


def rank_by_visibility(clinics: list[dict], market: dict) -> list[dict]:
    """Clinics sorted by visibility (best first), each tagged with `visibility` and 1-based `rank`."""
    ordered = sorted(clinics, key=lambda c: visibility_score(c, market), reverse=True)
    out = []
    for i, c in enumerate(ordered, start=1):
        d = dict(c)
        d["visibility"] = visibility_score(c, market)
        d["rank"] = i
        out.append(d)
    return out


def visibility_rank(identifier: str, clinics: list[dict], market: dict) -> tuple[int, int]:
    """(rank, total) of a clinic by online visibility — e.g. 'you rank 28 of 34'."""
    ranked = rank_by_visibility(clinics, market)
    for d in ranked:
        if identifier in (d.get("key"), d.get("name")):
            return d["rank"], len(ranked)
    return len(ranked), len(ranked)


# --------------------------------------------------------------------------- the real-SERP proof
def serp_proof(clinic_key: str, web_screens: dict, clinics: list[dict],
               query_rows: list[dict]) -> dict | None:
    """The most persuasive evidence: the highest-demand patient search where this clinic is ABSENT
    while competitors/aggregators show up. Returns {query, screenshot, strength, present[]} or None."""
    from modules.web_screens import map_block, prepare_clinics

    prepared = prepare_clinics(clinics)
    name_by_key = {c["key"]: c["name"] for c in prepared}
    strength = {q.get("search_query"): (q.get("search_strength_score") or 0) for q in query_rows}

    best = None
    for q in web_screens.get("queries", []):
        blocks = q.get("blocks", [])
        if not blocks:
            continue
        if any(map_block(b, prepared)[0] == clinic_key for b in blocks):
            continue  # the clinic IS here — not proof of absence
        present: list[str] = []
        for b in blocks:
            k, _ = map_block(b, prepared)
            label = name_by_key.get(k) if k else _present_label(b.get("platform") or b.get("domain") or "")
            if label and label not in present:
                present.append(label)
            if len(present) >= 4:
                break
        st = strength.get(q.get("search_query"), 0)
        cand = {"query": q.get("search_query"), "screenshot": q.get("screenshot"),
                "strength": st, "present": present}
        if best is None or st > best["strength"]:
            best = cand
    return best
