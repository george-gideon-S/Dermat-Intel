"""Build the query set programmatically. Replaces the manual LLM copy-paste round trip.

The old flow printed a prompt, a human pasted it into a free LLM, then pasted the answer back.
That made "one click" impossible and left the guarantees to a person: it is why the June set
contains six "near me" queries and why its size drifted from the configured 50 to 80.

Pipeline: seeds -> autocomplete expansion -> dedupe -> derive -> validate -> rank.

Two rules are enforced as hard failures rather than warnings, because violating either
produces data that looks fine and means something else:

* **No "near me".** It resolves against the searcher's location, so the result set describes
  wherever the scraper sits rather than the market, and every cross-run comparison is poisoned.
* **Every query names the city.** Measured 2026-08-18: Google ignores the `uule` parameter, and
  this machine's IP geolocates to Vijayawada, ~30 km from Guntur. An unqualified query returns
  a healthy-looking SERP for the wrong city.

Autocomplete is an expansion source, never the only one: coverage is very uneven (acne, eczema,
scar and keloid return zero city-qualified suggestions for Guntur), so templates carry the
floor and suggestions add the phrasings real patients type.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from typing import Optional

from modules import httpget, packs
from modules.query_generator import derive_category, derive_strength

AUTOCOMPLETE = "https://suggestqueries.google.com/complete/search"

BANNED_PATTERNS = [
    r"\bnear\s*me\b", r"\bnear\s*by\b", r"\bnearby\b", r"\baround me\b",
    r"\bclosest\b", r"\bclose to me\b", r"\bin my area\b", r"\bnear my location\b",
]
_BANNED_RE = re.compile("|".join(BANNED_PATTERNS), re.I)

# Suggestion noise: Guntur is also famous for chillies and biryani.
_OFFTOPIC = re.compile(
    r"\b(recipe|biryani|chilli|chili|mirchi|hotel|restaurant|movie|cinema|job|jobs|"
    r"salary|college|school|admission|weather|train|bus|pincode|property|plot|rent)\b", re.I)

# Words that are legitimate in any market's queries. Everything a query contains must be either
# here, in the specialty's own vocabulary, or the city name — anything else is almost always a
# proper noun, which in this domain means a clinic or a doctor. Google's autocomplete returns
# those constantly ("kavitha skin doctor in guntur"), and they are the one kind of query that
# cannot measure a market: they measure one business, and whoever is named wins by definition.
_GENERIC_VOCAB = {
    # structure
    "in", "at", "for", "the", "and", "or", "of", "a", "an", "to", "with", "my", "me", "is",
    "are", "was", "on", "by", "from", "near", "best", "top", "good", "better", "which",
    "what", "where", "who", "how", "why", "when", "all", "any", "list", "vs", "versus",
    # quality / person qualifiers
    "famous", "leading", "popular", "known", "experienced", "senior", "expert", "professional",
    "qualified", "certified", "trusted", "reputed", "affordable", "cheap", "budget", "low",
    "high", "quality", "female", "lady", "ladies", "male", "gents", "women", "womens", "men",
    "mens", "child", "children", "kids", "pediatric", "paediatric", "baby", "adult", "young",
    "new", "old", "government", "private", "govt",
    # place-type and contact words (NOT place names)
    "city", "town", "area", "clinic", "clinics", "hospital", "hospitals", "centre", "center",
    "care", "contact", "number", "phone", "mobile", "address", "location", "timings", "timing",
    "hours", "open", "now", "today", "online", "home", "visit", "service", "services",
    # practitioner + commerce
    "doctor", "doctors", "dr", "physician", "specialist", "specialists", "surgeon",
    "consultation", "appointment", "appointments", "book", "booking", "slot",
    "fee", "fees", "cost", "costs", "price", "prices", "pricing", "charges",
    "review", "reviews", "rating", "ratings", "rated", "feedback",
    # products, so a genuine Product-Based query is not mistaken for a brand name
    "machine", "machines", "device", "devices", "equipment", "tool", "tools", "cream",
    "creams", "ointment", "gel", "lotion", "serum", "shampoo", "soap", "tablet", "tablets",
    "capsule", "capsules", "medicine", "medicines", "product", "products", "kit", "kits",
    "oil", "oils", "supplement", "supplements", "spray", "foam", "sunscreen", "moisturizer",
    "moisturiser", "wash", "face",
}


#: Template groups beyond discovery/condition/pricing that still earn their own phrasings.
#: "Trust & Social Proof" and "Comparison" were retired — see `query writing.md`. Their
#: templates fold into Discovery, because "best rated dermatologist in Guntur" is the same
#: intent as "best dermatologist in Guntur" wearing a different hat.
COMMERCIAL_GROUPS = ("Appointment & Booking",)


class QuerySetInvalid(Exception):
    """The generated set breaks a rule that would corrupt the measurement."""


# ------------------------------------------------------------------ autocomplete
def fetch_suggestions(seed: str, gl: str = "in", hl: str = "en", timeout: int = 15,
                      pause: float = 0.4) -> list[str]:
    """Google's keyless suggest endpoint. Raises httpget.FetchError when unreachable.

    The polite delay lives here rather than in the calling loop so that it is coupled to the
    request it paces: stubbing this function in tests removes the I/O and the sleep together,
    instead of leaving a test suite that waits on delays for requests it never makes.
    """
    url = (f"{AUTOCOMPLETE}?client=firefox&hl={hl}&gl={gl}"
           f"&q={urllib.parse.quote_plus(seed)}")
    data = httpget.get_json(url, timeout=timeout)
    if pause:
        time.sleep(pause)
    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
        return [s for s in data[1] if isinstance(s, str)]
    return []


# ------------------------------------------------------------------ generation
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (s or "").lower())).strip()


def allowed_vocabulary(ctx) -> set:
    """Every word a query for this market is allowed to contain."""
    ctx = packs.resolve(ctx)
    vocab = set(_GENERIC_VOCAB) | topic_tokens(ctx)
    vocab.update(_norm(ctx.city).split())
    vocab.update(_norm(ctx.state).split())
    vocab.update(t.lower() for t in (ctx.geo.get("city_tokens") or []))
    for item in list(ctx.conditions) + list(ctx.treatments):
        for phrase in item.get("phrasings") or []:
            vocab.update(_norm(phrase).split())
    for noun in [ctx.specialist_noun] + (ctx.spec.get("specialist_synonyms") or []) \
            + (ctx.spec.get("facility_nouns") or []):
        vocab.update(_norm(noun).split())
    return {t for t in vocab if t}


def unknown_tokens(query: str, vocab: set) -> list:
    """Words in the query that this market's vocabulary does not account for.

    Numbers pass. Everything else that is unrecognised is treated as a proper noun — the
    practical signature of a clinic name, a doctor's name, or a neighbourhood.
    """
    return [t for t in _norm(query).split()
            if t not in vocab and not t.isdigit() and len(t) > 2]


#: Street-type words that appear inside locality names ("Amaravati Road", "Chandramouli
#: Nagar"). They identify a KIND of place, not a place, so blocking them would reject
#: unrelated queries while catching nothing a real locality name does not already catch.
_PLACE_SUFFIXES = {"road", "nagar", "street", "colony", "extension", "cross", "main",
                   "circle", "junction", "gardens", "layout", "phase", "sector", "block"}


def sub_places(ctx) -> set:
    """Neighbourhood names that must not appear in a query for a small market."""
    ctx = packs.resolve(ctx)
    if ctx.geo.get("allow_locality_queries"):
        return set()
    out = set()
    for loc in (ctx.geo.get("localities") or []):
        out.update(_norm(loc).split())
    city_words = set(_norm(ctx.city).split())
    return {t for t in out if t and t not in city_words and t not in _PLACE_SUFFIXES}


def is_acceptable(query: str, city: str, topic_tokens: set,
                  vocab: Optional[set] = None, banned_places: Optional[set] = None) -> bool:
    """A query is usable only if it names the market, avoids 'near me', and is on-topic.

    `vocab` and `banned_places` add the two rules that keep a query measuring a MARKET rather
    than one business or one street — see `query writing.md`. Both are optional so that the
    core acceptability test stays callable on its own.
    """
    q = (query or "").strip()
    if len(q) < 8:
        return False
    if _BANNED_RE.search(q):
        return False
    if city.lower() not in q.lower():
        return False
    if _OFFTOPIC.search(q):
        return False
    toks = set(_norm(q).split())
    if banned_places and (toks & banned_places):
        return False           # names a neighbourhood inside a market small enough not to have one
    if vocab is not None and unknown_tokens(q, vocab):
        return False           # names a specific clinic or doctor
    return bool(toks & topic_tokens)


def topic_tokens(ctx) -> set:
    """Words that mark a query as being about this specialty at all."""
    out = {_norm(ctx.specialist_noun)}
    for syn in (ctx.spec.get("specialist_synonyms") or []) + (ctx.spec.get("facility_nouns") or []):
        out.update(_norm(syn).split())
    for group in (ctx.conditions, ctx.treatments):
        for item in group:
            for phrase in item.get("phrasings") or []:
                out.update(_norm(phrase).split())
    out.update(t.lower() for t in (ctx.spec.get("specialty_tokens") or []))
    return {t for t in out if len(t) >= 3}


def template_pools(ctx) -> dict:
    """Candidate queries grouped by purpose.

    Grouping (rather than one flat list) is what lets selection guarantee that every condition
    is asked several ways even at a small threshold. A flat list ordered by search strength
    puts all the head terms first, so truncating it drops whole conditions off the end — the
    exact under-sampling the brief warns produces a confident wrong answer.
    """
    city = ctx.city
    templates = ctx.spec.get("phrasing_templates") or {}
    nouns = [ctx.specialist_noun] + (ctx.spec.get("specialist_synonyms") or [])
    facility = (ctx.spec.get("facility_nouns") or ["clinic"])[0]

    def fmt(tpl: str, **kw) -> str:
        return re.sub(r"\s+", " ", tpl.format(**kw)).strip()

    discovery = [fmt(t, specialist=n, city=city, facility=facility)
                 for t in templates.get("Discovery", []) for n in nouns]

    # Variants are ordered PHRASING-first, then alternate templates. Depth-N selection is
    # meant to add a different way of asking, so template-first ordering would hand back the
    # same phrasing reworded and leave the condition still asked only one way.
    cond_templates = templates.get("Condition-Based", ["{phrasing} in {city}"])
    per_condition = []
    for item in list(ctx.conditions) + list(ctx.treatments):
        phrasings = item.get("phrasings") or []
        variants = [fmt(cond_templates[0], phrasing=p, city=city) for p in phrasings]
        variants += [fmt(t, phrasing=p, city=city)
                     for t in cond_templates[1:] for p in phrasings]
        if variants:
            per_condition.append({"id": item.get("id"), "phrasings": phrasings,
                                  "variants": variants})

    pricing = [fmt(t, phrasing=(i.get("phrasings") or [""])[0], city=city,
                   specialist=ctx.specialist_noun)
               for i in list(ctx.treatments) + list(ctx.conditions)
               for t in templates.get("Pricing", [])]
    commercial = {g: [fmt(t, specialist=n, city=city, facility=facility)
                      for t in templates.get(g, []) for n in nouns[:2]]
                  for g in COMMERCIAL_GROUPS}
    # Neighbourhood queries only make sense in a market big enough that patients actually
    # search by neighbourhood. In a city the size of Guntur, "dermatologist in guntur kothapet"
    # splits one small market into slivers and measures a street rather than the city.
    locality = ([f"{n} in {loc} {city}"
                 for loc in (ctx.geo.get("localities") or []) for n in nouns[:2]]
                if ctx.geo.get("allow_locality_queries") else [])

    return {"discovery": discovery, "per_condition": per_condition, "pricing": pricing,
            "commercial": commercial, "locality": locality}


def build_with_report(ctx, pause: float = 0.4, use_autocomplete: bool = True) -> tuple:
    """Generate the query set and a provenance report."""
    ctx = packs.resolve(ctx)
    city = ctx.city
    want = int(ctx.query_threshold or ctx.default_query_threshold or 50)
    topics = topic_tokens(ctx)
    vocab = allowed_vocabulary(ctx)
    banned_places = sub_places(ctx)

    pools = template_pools(ctx)
    accepted: list[str] = []
    seen: set[str] = set()

    def take(q: str) -> bool:
        key = _norm(q)
        if not key or key in seen or len(accepted) >= want:
            return False
        if not is_acceptable(q, city, topics, vocab=vocab, banned_places=banned_places):
            return False
        seen.add(key)
        accepted.append(q.strip())
        return True

    # Autocomplete is gathered up front so real patient phrasings compete for slots rather
    # than only filling leftovers — templates guarantee coverage, suggestions add reality.
    suggestions: list[str] = []
    error = ""
    if use_autocomplete:
        # Guard against an item with no phrasings: indexing [0] here (outside the fetch
        # try/except) would raise IndexError and take the whole build down. Conditions are
        # validated to have >=2 phrasings, but treatments are not, so a pack could ship one bare.
        probe = ([f"{ctx.specialist_noun} in {city}"]
                 + [f"{s} in {city}" for s in (ctx.spec.get("specialist_synonyms") or [])]
                 + [f"{c['phrasings'][0]} in {city}" for c in ctx.conditions if c.get("phrasings")]
                 + [f"{t['phrasings'][0]} in {city}" for t in ctx.treatments if t.get("phrasings")])
        for seed in probe:
            try:
                suggestions.extend(fetch_suggestions(seed, gl=ctx.gl, hl=ctx.hl, pause=pause))
            except httpget.FetchError as exc:
                error = str(exc)
                break

    # Selection order matters more than it looks: each stage is a guarantee, and later stages
    # only get the slots earlier ones leave. Conditions get one phrasing each before ANY gets
    # a second, so a small threshold degrades by asking every condition once rather than by
    # dropping whole conditions off the end.
    # 1. a few head terms
    for q in pools["discovery"][:3]:
        take(q)
    # 2. one phrasing for every condition and treatment
    for group in pools["per_condition"]:
        take(group["variants"][0])
    # 3. category variety, so the set is not all one intent
    for q in pools["pricing"][:2]:
        take(q)
    for group_name in COMMERCIAL_GROUPS:
        for q in pools["commercial"].get(group_name, [])[:2]:
            take(q)

    # 4. reserve up to a quarter of the set for real autocomplete phrasings
    from_autocomplete = 0
    reserve = max(0, min(len(suggestions), want // 4))
    for s in suggestions:
        if from_autocomplete >= reserve:
            break
        if take(s):
            from_autocomplete += 1

    # 5. second phrasing per condition — the "ask it several ways" guarantee
    for group in pools["per_condition"]:
        if len(group["variants"]) > 1:
            take(group["variants"][1])

    # 6. fill with remaining depth: further phrasings, more discovery, locality long tail
    rest = ([v for g in pools["per_condition"] for v in g["variants"][2:]]
            + pools["discovery"][3:] + pools["pricing"][2:]
            + [q for g in pools["commercial"].values() for q in g[2:]]
            + pools["locality"])
    for q in rest:
        if len(accepted) >= want:
            break
        take(q)
    for s in suggestions:
        if len(accepted) >= want:
            break
        if take(s):
            from_autocomplete += 1

    if len(accepted) < want:
        for q in _pad(ctx, want - len(accepted), seen, topics, vocab, banned_places):
            take(q)

    rows = _rank(accepted[:want], ctx)
    from_templates = len(rows) - from_autocomplete

    # Enforce the exact count against `want`, not against len(rows) — comparing len(rows) to
    # min(want, len(rows)) is always true and made the "exactly N queries" gate a no-op. If the
    # packs genuinely cannot fill the threshold, that is a real misconfiguration to surface
    # loudly, not to paper over with a short set.
    validate(rows, city=city, expected=want, vocab=vocab, banned_places=banned_places)
    coverage = condition_coverage(rows, pools["per_condition"])
    report = {
        "requested": want,
        "produced": len(rows),
        "condition_coverage": coverage,
        "from_templates": from_templates,
        "from_autocomplete": from_autocomplete,
        "query_source": ("templates_only" if from_autocomplete == 0 else "templates+autocomplete"),
        "autocomplete_error": error,
        "autocomplete_suggestions_seen": len(suggestions),
        "city": city,
        "specialty": ctx.spec.get("id"),
    }
    return rows, report


def condition_coverage(rows: list[dict], per_condition: list[dict]) -> dict:
    """How many conditions ended up asked more than one way.

    A threshold below ~2x the number of conditions cannot ask them all several ways — that is
    arithmetic, not a bug. What matters is that the shortfall is stated in the run manifest
    rather than left for a reader to assume full coverage.
    """
    text = " || ".join((r.get("search_query") or "").lower() for r in rows)
    asked_twice, shortfall = 0, []
    for group in per_condition:
        hits = sum(1 for p in group["phrasings"] if p.lower() in text)
        if hits >= 2:
            asked_twice += 1
        else:
            shortfall.append({"condition": group["id"], "phrasings_asked": hits})
    return {"conditions": len(per_condition), "asked_twice": asked_twice,
            "shortfall": shortfall,
            "minimum_for_full_coverage": 2 * len(per_condition)}


def _pad(ctx, n: int, seen: set, topics: set,
         vocab: Optional[set] = None, banned_places: Optional[set] = None) -> list[str]:
    """Extra combinations when templates + autocomplete fall short of the threshold.

    Must NOT mutate the caller's `seen`: the caller re-checks each returned candidate through
    take(), which rejects anything already in `seen`. If _pad pre-inserted its own candidates
    there, take() would reject every one and padding would silently contribute nothing. So it
    reads `seen` to skip already-emitted queries but tracks its own output in a local set.
    """
    out, city = [], ctx.city
    emitted: set = set()
    nouns = [ctx.specialist_noun] + (ctx.spec.get("specialist_synonyms") or [])
    qualifiers = ["best", "top", "experienced", "female", "senior", "affordable", "famous"]

    def consider(cand: str) -> bool:
        key = _norm(cand)
        if key in seen or key in emitted or not is_acceptable(
                cand, city, topics, vocab=vocab, banned_places=banned_places):
            return False
        emitted.add(key)
        out.append(cand)
        return len(out) >= n

    for item in list(ctx.conditions) + list(ctx.treatments):
        for phrase in item.get("phrasings") or []:
            for qual in qualifiers:
                if consider(f"{qual} {phrase} in {city}"):
                    return out
    for qual in qualifiers:
        for noun in nouns:
            if consider(f"{qual} {noun} in {city}"):
                return out
    return out


def _rank(queries: list[str], ctx) -> list[dict]:
    n = len(queries)
    rows = []
    for i, q in enumerate(queries, start=1):
        cat = derive_category(q)
        rows.append({
            "rank": i,
            "search_query": q,
            "category": cat,
            "user_intent": intent_for(cat, ctx),
            "search_strength_score": derive_strength(i, cat, n),
        })
    return rows


def intent_for(category: str, ctx) -> str:
    """Intent copy written from the run's own market and specialty, not a hardcoded city."""
    city, spec = ctx.city, (ctx.specialist_noun or "specialist")
    return {
        "Discovery": f"Wants to discover the leading {spec}s in {city}.",
        "Doctor-Based": f"Wants a {city} {spec} who treats one specific condition.",
        "Condition-Based": f"Is searching for treatment of a specific condition in {city}.",
        "Product-Based": f"Is looking for a machine, device or product rather than a {city} clinic.",
        "Pricing": f"Wants to know consultation fees / treatment costs in {city}.",
        "Appointment & Booking": f"Is ready to book or consult a {spec} in {city}.",
    }.get(category, f"Wants to discover the leading {spec}s in {city}.")


def build(ctx, **kw) -> list[dict]:
    return build_with_report(ctx, **kw)[0]


# ------------------------------------------------------------------ validation
def validate(rows: list[dict], city: str, expected: Optional[int] = None,
             vocab: Optional[set] = None, banned_places: Optional[set] = None) -> bool:
    """Hard gate. Each failure here would silently corrupt the market measurement."""
    if expected is not None and len(rows) != expected:
        raise QuerySetInvalid(f"expected {expected} queries, got {len(rows)}")
    seen = set()
    for r in rows:
        q = str(r.get("search_query") or "")
        if _BANNED_RE.search(q):
            raise QuerySetInvalid(
                f"'near me' style query would measure the scraper's location, not the market: {q!r}")
        if city and city.lower() not in q.lower():
            raise QuerySetInvalid(
                f"query does not name the city, so Google will answer for the scraper's own "
                f"location (uule is ignored): {q!r}")
        toks = set(_norm(q).split())
        if banned_places and (toks & banned_places):
            raise QuerySetInvalid(
                f"query names a neighbourhood inside a market too small to have separate "
                f"sub-markets, so it measures a street rather than the city: {q!r}")
        if vocab is not None:
            unknown = unknown_tokens(q, vocab)
            if unknown:
                raise QuerySetInvalid(
                    f"query names something specific ({', '.join(unknown)}) — a clinic or "
                    f"doctor named in the query wins it by definition, which measures one "
                    f"business rather than the market: {q!r}")
        key = _norm(q)
        if key in seen:
            raise QuerySetInvalid(f"duplicate query: {q!r}")
        seen.add(key)
    ranks = [r.get("rank") for r in rows]
    if ranks != list(range(1, len(rows) + 1)):
        raise QuerySetInvalid("ranks must be contiguous 1..N")
    return True
