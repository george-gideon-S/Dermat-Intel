"""Parse a Google SERP's HTML into the web_screens.json block contract. Pure: no I/O, no network.

This replaces the manual pipeline's Claude-vision extraction of screenshot tiles. It emits the
identical structure, so web_screens / unify_results / report consume it unchanged:

    query entry -> {index, screenshot, rank, search_query, search_box_text,
                    match_confidence, readable, blocks[]}
    block       -> EXACTLY {position, block_type, platform, title, domain, url,
                            rating, reviews, snippet}

Two rules carry the most weight and are easy to get subtly wrong:

* `position` is ONE continuous top-to-bottom sequence across every block type — it is the
  reader's eye travelling down the page, not a per-type ranking. Scoring reads it as
  "how far down before this clinic appears".
* Ads count as OWNED visibility while `places` does not (the local pack is Maps data
  re-surfaced), so misclassifying an ad row as organic moves a clinic's score.

Selectors are tiered: a stable structural signal first (container ids, the anchor>h3 pattern),
then class names, which Google rotates. `PARSER_VERSION` is stamped into the dataset meta and
raw HTML is retained per query, so a selector fix can re-parse old runs without re-scraping.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from bs4 import BeautifulSoup

from modules.web_collector import _clean, domain_of, _unwrap_google_redirect
from modules.web_screens import (AGGREGATOR_PLATFORMS, BORROWED_PLATFORMS,
                                 HOSPITAL_FRAGMENTS, SOCIAL_PLATFORMS)

PARSER_VERSION = "serp-dom-1"

# domain fragment -> platform label. Substring match, so m./www./regional hosts all resolve.
_PLATFORM_BY_FRAGMENT = {p: p for p in (AGGREGATOR_PLATFORMS | SOCIAL_PLATFORMS | {"traya"})}

# Hosts that are neither a local clinic's property nor a directory listing one: national health
# encyclopaedias, search/retail, and reference sites. They rank for symptom queries constantly,
# so leaving them in the clinic_site bucket would quietly inflate every market's owned share.
_NON_CLINIC_FRAGMENTS = (
    "google.", "gstatic", "googleadservices", "blogspot.",
    "mayoclinic.org", "healthline.com", "webmd.com", "medicalnewstoday.com",
    "clevelandclinic.org", "nih.gov", "who.int", "aad.org", "nhs.uk", "wikipedia.org",
    "quora.com", "reddit.com", "pinterest.", "linkedin.com", "twitter.com", "x.com",
    "amazon.", "flipkart.com", "nykaa.com", "purplle.com", "meesho.com",
    "1mg.com", "netmeds.com", "pharmeasy.in", "tatahealth.com",
    "timesofindia.", "indianexpress.com", "ndtv.com", "hindustantimes.com",
)

_AD_ROW_CLASSES = {"uEierd", "vdQmEd", "KoyxIe"}
_LOCAL_ROW_CLASSES = {"uMdZh", "VkpGBb"}
_ORGANIC_CLASSES = {"tF2Cxc", "MjjYud", "g"}

_RATING_RE = re.compile(r"Rated\s+([\d.]+)\s+out of\s+5(?:,\s*([\d,]+)\s+user reviews)?", re.I)
_PAREN_COUNT_RE = re.compile(r"\(([\d,]+)\)")
# Quote-agnostic: attribute quoting varies between Google's renderings and saved fixtures.
_RESULTS_SCAFFOLD_RE = re.compile(r"""id=['"]?(search|rso)['"]?""", re.I)


def _classes(el) -> set:
    c = el.get("class")
    return set(c) if c else set()


def _txt(el, limit: int = 400) -> str:
    if el is None:
        return ""
    return _clean(el.get_text(" ", strip=True))[:limit]


def classify_platform(domain: str, url: str = "") -> str:
    """Map a result domain to the platform vocabulary web_screens scores against.

    Three-way, and the middle case is the one that matters: a known aggregator/social host is
    BORROWED visibility, a national health encyclopaedia or shopping site is neither (it can
    never be a local clinic's property), and what remains is treated as a clinic's own site.

    Calling every unknown domain `clinic_site` would hand `owned` credit — 30 of the 100
    visibility points — to results like mayoclinic.org that no Guntur clinic owns. The
    authoritative own-site test downstream is still domain equality against the clinic's own
    website (web_screens._is_own_site); this label is the fallback for clinics whose Maps
    record has no website recorded.
    """
    d = (domain or "").lower()
    if not d:
        return "other"
    for frag, label in _PLATFORM_BY_FRAGMENT.items():
        if frag in d:
            return label
    for frag in _NON_CLINIC_FRAGMENTS:
        if frag in d:
            return "other"
    # A hospital's own site is a real property, but not a clinic's — and this market is
    # measured on single-specialty clinics. Labelling it separately keeps it OUT of the owned
    # clinic signal without deleting it from the page.
    for frag in HOSPITAL_FRAGMENTS:
        if frag in d:
            return "hospital"
    return "clinic_site"


def _block(position, block_type, *, title="", url="", domain=None, platform=None,
           rating=None, reviews=None, snippet="") -> dict:
    """Build a block with EXACTLY the nine contract keys, in the contract's order."""
    dom = domain if domain is not None else domain_of(url)
    return {
        "position": position,
        "block_type": block_type,
        "platform": platform if platform is not None else classify_platform(dom, url),
        "title": _clean(title),
        "domain": dom or "",
        "url": url or "",
        "rating": rating,
        "reviews": reviews,
        "snippet": _clean(snippet),
    }


# --------------------------------------------------------------------- per-type extraction
def _parse_rating_reviews(el) -> tuple[Optional[float], Optional[int]]:
    """Read rating/review count from the aria-label, which survives class churn.

    'Rated 4.9 out of 5, 348 user reviews' -> (4.9, 348). Falls back to the visible
    '(1,204)' count. The thousands separator matters: '(1,204)' must not become 1.
    """
    rating = reviews = None
    for node in [el] + el.find_all(attrs={"aria-label": True}, limit=12):
        label = node.get("aria-label") if hasattr(node, "get") else None
        if not label:
            continue
        m = _RATING_RE.search(label)
        if m:
            try:
                rating = float(m.group(1))
            except ValueError:
                rating = None
            if m.group(2):
                reviews = int(m.group(2).replace(",", ""))
            break
    if reviews is None:
        m = _PAREN_COUNT_RE.search(el.get_text(" ", strip=True))
        if m:
            reviews = int(m.group(1).replace(",", ""))
    return rating, reviews


def _extract_local(el, position: int) -> Optional[dict]:
    details = el.find(class_="rllt__details") or el
    name_el = details.find(class_="dbg0pd") or details.find(class_="OSrXXb")
    title = _txt(name_el, 200)
    if not title:
        return None
    rating, reviews = _parse_rating_reviews(details)
    # Address/category lines: the detail divs after the name, minus the rating line.
    lines = [_txt(d, 200) for d in details.find_all("div", recursive=False)]
    extras = [ln for ln in lines if ln and ln != title and not ln.startswith(title)]
    snippet = " · ".join(x for x in extras if x)[:400]
    return _block(position, "places", title=title, url="", domain="",
                  platform="clinic_site", rating=rating, reviews=reviews, snippet=snippet)


def _ad_headline(raw: str) -> str:
    """Ad units render 'Brand https://display.url › path › path Body copy…' as one text run.

    Keep the brand headline: everything before the display URL. Without this the title field
    carries the URL twice and reads as noise in the report.
    """
    cut = re.split(r"\s*https?://", raw, maxsplit=1)[0]
    return (cut or raw).strip(" ·|—-")[:200]


def _extract_ad(el, position: int, kind: str) -> Optional[dict]:
    a = el.find("a", href=True)
    if not a:
        return None
    url = _unwrap_google_redirect(a["href"])
    if not url.startswith("http"):
        return None
    # The ad's own anchor text carries the advertiser headline. Do NOT prefer role="heading"
    # here: inside an ad unit that is Google's "My Ad Centre" control, not the advertiser.
    raw_title = _txt(a.find(["span", "div"]) or a, 240) or _txt(a, 240)
    snippet_el = el.find(class_="MUxGbd") or el.find(class_="Va3FIb")
    snippet = _txt(snippet_el, 400) or _txt(el, 400)
    return _block(position, kind, title=_ad_headline(raw_title), url=url, snippet=snippet)


def _extract_organic(el, position: int) -> Optional[dict]:
    h3 = el.find("h3")
    if not h3:
        return None
    a = h3.find_parent("a", href=True) or el.find("a", href=True)
    if not a:
        return None
    url = _unwrap_google_redirect(a["href"])
    if not url.startswith("http"):
        return None
    dom = domain_of(url)
    if not dom or dom.endswith("google.com"):
        return None
    snip_el = el.find(class_="VwiC3b") or el.find(class_="MUxGbd") or el.find(class_="lEBKkf")
    rating, reviews = _parse_rating_reviews(el)
    return _block(position, "organic", title=_txt(h3, 300), url=url, domain=dom,
                  rating=rating, reviews=reviews, snippet=_txt(snip_el, 400))


#: Chrome renders the overview with an out-of-band notice bar: a translation offer, and when
#: that fails, an apology. Both sit INSIDE the overview container and ahead of the answer, so
#: searching for these phrases anywhere in the text marked real overviews as refusals.
_AI_BOILERPLATE = re.compile(
    r"an ai overview is not available for this search|"
    r"can'?t generate an ai overview(?: right now)?\.?|"
    r"error translating content\.?|(?:please )?try again later\.?|"
    r"^\s*ai overview\b|\bshow (?:more|all|less)\b|\bai mode\b", re.I)

#: The language toggle Google prints beside the overview, e.g. "తెలుగు English".
_AI_LANG_TOGGLE = re.compile(r"[^\x00-\x7F]{2,}\s+English\b", re.I)

#: Chrome wraps the overview in page furniture that is not part of the answer: the location
#: chooser above it, and on some queries a whole "People also ask" block sharing its container.
#: Both were being read as the opening words of the AI's reply.
_AI_FURNITURE = re.compile(
    r"[\w\s,.'-]{0,60}?\u2219\s*Choose area|"      # "Guntur, Andhra Pradesh ∙ Choose area"
    r"\bPeople also ask\b|\bRelated searches\b|\bFeedback\b|"
    r"\bSponsored\b|\bShow more\b|\bShow all\b", re.I)

#: The heading that divides the furniture from the answer.
_AI_HEADING = re.compile(r"\bAI\s+Overview\b", re.I)

#: Below this many characters of real content, there is no answer — only the notice bar.
AI_MIN_REAL_CHARS = 60

#: Full overviews run long. The old 600-character cap silently truncated every one of them
#: mid-sentence, so any clinic named past that point was invisible.
AI_TEXT_LIMIT = 20000


#: Google's own footer, printed at the end of every generated overview. Measured on 25 of 25
#: available captures, so it is a reliable end-of-answer boundary. Everything after it belongs
#: to the next section of the page — usually "People also ask", whose questions and answers
#: were otherwise being read as the tail of the AI's reply.
_AI_FOOTER = re.compile(r"AI responses may include mistakes", re.I)


def ai_clean_text(text: str) -> str:
    """The overview with Google's page furniture removed — what the AI actually said.

    The answer does not start where its container starts, and does not end where it ends.
    Above it sit a location chooser, a failed-translation apology, and on some queries an
    entire "People also ask" block; below it sit that block's answers. All inside the same
    element. Reading the container top-to-bottom therefore opened one answer with
    "People also ask Who are some famous skin specialists in Guntur?" and closed another with
    "Which doctor is the best for skin? An error has occurred."

    Two boundaries fix it. The "AI Overview" heading divides the furniture from the answer —
    split on it and keep the longest piece. Google's "AI responses may include mistakes"
    footer ends the answer — cut there.
    """
    out = _AI_LANG_TOGGLE.sub(" ", text or "")
    out = _AI_BOILERPLATE.sub(" ", out)
    parts = _AI_HEADING.split(out)
    out = max(parts, key=len) if parts else out
    footer = _AI_FOOTER.search(out)
    if footer:
        out = out[:footer.start()]
    out = _AI_LANG_TOGGLE.sub(" ", out)
    out = _AI_FURNITURE.sub(" ", out)
    return re.sub(r"\s+", " ", out).strip(" .\u00b7|\u2014-")


def ai_is_unavailable(text: str) -> bool:
    """True only when nothing but the notice bar is left.

    Deliberately NOT "the page mentions 'can't generate'": that phrase appears above a
    perfectly good overview whenever the translation widget fails, and testing for it directly
    threw away every real answer on the page.
    """
    return len(ai_clean_text(text)) < AI_MIN_REAL_CHARS


def _extract_ai_overview(el, position: int) -> dict:
    text = ai_clean_text(_txt(el, AI_TEXT_LIMIT))
    # An overview Google refused to generate is not an overview. Counting it as one is how a
    # market ends up reporting "AI overview present" for a search that never had one.
    kind = "ai_overview_unavailable" if len(text) < AI_MIN_REAL_CHARS else "ai_overview"
    return _block(position, kind, title="AI Overview", url="", domain="",
                  platform="other", snippet=text)


# --------------------------------------------------------------------- AI overview detail
#: Lead-in words that mark a line as prose about a clinic rather than the clinic's name.
_AI_NOISE_RE = re.compile(
    r"^(here|these|this|the following|based on|according to|note|disclaimer|"
    r"it'?s|you (?:may|should|can)|consult|always|generative ai|ai overview|learn more|"
    r"show more|show all|sources?)\b", re.I)

#: A clinic name in this domain nearly always carries one of these.
#: Stems, not whole words: a trailing \b made "derma" fail to match "Dermacare", so a clinic
#: whose name IS the hint was the one kind that got dropped.
_CLINIC_HINT_RE = re.compile(
    r"\b(?:clinic\w*|hospital\w*|centre\w*|center\w*|institute\w*|care\w*|skin\w*|hair\w*|"
    r"laser\w*|derma\w*|dermatolog\w*|cosmet\w*|aesthet\w*|tricholog\w*|dr\.?|doctor\w*)", re.I)

#: Things that pass the clinic hint but are not a clinic. Widening the hint to stems let three
#: kinds of impostor through: the titles of the listicles Google cites, the name of the
#: condition being asked about (via the "derma" stem in "dermatitis"), and Google's own UI
#: labels. Each would have been reported as a clinic the AI recommended.
_AI_NOT_A_CLINIC_RE = re.compile(
    r"^\s*\d+\s*\+?\s|"                                       # "21+ Best Doctors in ..."
    r"\bbest\b[^|]*\b(?:doctors?|clinics?|dermatologists?|hospitals?|surgeons?)\b"
    r"[^|]*\b(?:in|for|near)\b|"                              # a listicle's title
    r"^(?:my ad cent(?:re|er)|local\s+\w+\s+clinics?|choose area|sponsored|people also ask|"
    r"ai overview|things to know|more places|top \w+ clinics?)\s*$|"
    # section labels the overview uses to group its recommendations, with or without a
    # trailing "in <city>" ("Popular Clinics in Guntur")
    r"^(?:independent|multi[\s-]?speciali?ty|general|private|government|top|leading|other|"
    r"popular|best|nearby|local)\b[^|]*\b(?:clinics|hospitals|cent(?:re|er)s|doctors|"
    r"dermatologists)(?:\s+in\s+[\w\s]+)?\s*$|"
    # treatments and medicines described as care options, not places
    r"\b(?:drugs?|medication\w*|tablets?|capsules?|ointments?|creams?|antifungal\w*|"
    r"antibiotic\w*|steroid\w*|therapy|therapies|procedures?)\b|"
    r"^(?:topical|oral|systemic|advanced|specialised|specialized|home|self)\s+care\s*$|"
    r"\b(?:dermatitis|eczema|psoriasis|vitiligo|acne|alopecia|urticaria|melasma|"
    r"ringworm|hyperhidrosis|keloid)\b", re.I)


def ai_recommended_clinics(el) -> list[dict]:
    """Clinics the overview names, in the order it names them.

    Order is the whole point — an AI overview is a ranked recommendation, and being named
    first is not the same as being named last. Deduplicated on first appearance so a clinic
    repeated in the prose keeps its earliest position.

    Structure first (list items and headings), then bolded runs, because Google renders the
    same recommendation list three different ways depending on the query.
    """
    out: list[dict] = []
    seen: set = set()

    def add(name: str, source: str, url: str = "") -> None:
        name = _clean(name).strip(" .,:;–—-·|")
        if not (2 < len(name) <= 120) or _AI_NOISE_RE.match(name):
            return
        # A clinic or a doctor is a proper noun. A run of prose lifted out of the answer
        # ("specific skin or hair concern") is not, and starts lower-case.
        if not name[:1].isupper():
            return
        if not _CLINIC_HINT_RE.search(name) or _AI_NOT_A_CLINIC_RE.search(name):
            return
        key = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
        if not key or key in seen:
            return
        seen.add(key)
        out.append({"position": len(out) + 1, "name": name, "source": source,
                    "url": url, "domain": domain_of(url) if url else ""})

    for li in el.find_all("li"):
        strong = li.find(["b", "strong"]) or li.find(attrs={"role": "heading"})
        text = _txt(strong, 120) if strong else _txt(li, 160).split("  ")[0]
        # A list item usually reads "Name — description"; keep the part before the dash.
        add(re.split(r"\s[–—:-]\s", text, maxsplit=1)[0], "list")

    for node in el.find_all(["b", "strong"]):
        add(_txt(node, 120), "bold")

    for head in el.find_all(attrs={"role": "heading"}):
        add(_txt(head, 120), "heading")

    for a in el.find_all("a", href=True):
        url = _unwrap_google_redirect(a["href"])
        if url.startswith("http"):
            add(_txt(a, 120), "link", url)
    return out


def ai_source_links(el) -> list[dict]:
    """Sites the overview cites, in order — the 'borrowed authority' behind the answer."""
    out, seen = [], set()
    for a in el.find_all("a", href=True):
        url = _unwrap_google_redirect(a["href"])
        if not url.startswith("http"):
            continue
        dom = domain_of(url)
        if not dom or dom.endswith("google.com") or url in seen:
            continue
        seen.add(url)
        out.append({"position": len(out) + 1, "title": _txt(a, 160), "url": url,
                    "domain": dom, "platform": classify_platform(dom, url)})
    return out


def local_listing_names(html: str) -> list[dict]:
    """Clinic names from an expanded local listing, in the order Google ranks them.

    The "More places" view is the same `rllt__details` markup as the three-row pack on the
    SERP, just longer, so the pack extractor is reused rather than duplicated.
    """
    out, seen = [], set()
    for kind, el in _walk(BeautifulSoup(html or "", "lxml")):
        if kind != "places":
            continue
        block = _extract_local(el, len(out) + 1)
        if not block:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", block["title"].lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"position": len(out) + 1, "name": block["title"],
                    "rating": block["rating"], "reviews": block["reviews"],
                    "snippet": block["snippet"]})
    return out


def ai_overview_detail(html: str) -> Optional[dict]:
    """The full AI overview for one SERP, or None when the page carries no overview at all."""
    soup = BeautifulSoup(html or "", "lxml")
    el = None
    for kind, node in _walk(soup):
        if kind == "ai_overview":
            el = node
            break
    if el is None:
        return None
    text = ai_clean_text(_txt(el, AI_TEXT_LIMIT))
    unavailable = len(text) < AI_MIN_REAL_CHARS
    return {
        "present": True,
        "available": not unavailable,
        "text": text,
        "text_length": len(text),
        "truncated": len(text) >= AI_TEXT_LIMIT,
        "recommended_clinics": [] if unavailable else ai_recommended_clinics(el),
        "sources": [] if unavailable else ai_source_links(el),
    }


# --------------------------------------------------------------------- document-order walk
def _is_ad_row(el) -> bool:
    """Detect a paid result by attribute, not by container id.

    `#tads` still exists on modern SERPs but ships EMPTY — the served ads render in a
    separately-named container ("Sponsored results") whose class names are volatile. What is
    stable is the ad markup itself: `data-text-ad` / `data-ta-slot` on the unit. Keying on the
    old container ids silently returned zero ads, which costs half the OWNED signal (an ad is
    owned visibility exactly like an own-site organic hit).
    """
    if el.has_attr("data-text-ad") or el.has_attr("data-ta-slot"):
        return True
    return bool(_classes(el) & _AD_ROW_CLASSES) and el.find("a", href=True) is not None


def _tlen(el) -> int:
    return len(el.get_text(" ", strip=True)) if el is not None else 0


#: Markers that mean an element has stopped being the overview and started being the results.
_RESULT_MARKERS = ("h3",)
_RESULT_CLASSES = ("rllt__details", "g", "MjjYud", "tF2Cxc")


def _holds_results(el) -> bool:
    if any(el.find(tag) for tag in _RESULT_MARKERS):
        return True
    if el.find(attrs={"data-text-ad": True}) or el.find(attrs={"data-ta-slot": True}):
        return True
    return any(el.find(class_=c) for c in _RESULT_CLASSES)


def _ai_root_from_heading(head):
    """Climb from the "AI Overview" heading to the whole overview, and no further.

    Sizing this on a text-length discontinuity was wrong, and measurement caught it: the
    overview's first ~120 characters are a *failed translation* notice ("An AI Overview is not
    available… Error translating content"), and the generated answer follows it inside a much
    larger ancestor. Stopping at the size jump therefore captured the apology and discarded the
    answer — on a page that really did name three clinics and quote a fee range.

    Climb on structure instead: keep going while the ancestor contains no organic result, local
    row or ad, and take the last one that qualifies. That is the largest region that is still
    only the overview.
    """
    node, best = head, head
    while True:
        parent = node.parent
        if parent is None or getattr(parent, "name", None) in (None, "body", "html",
                                                               "[document]"):
            return best
        if _holds_results(parent):
            return best
        best, node = parent, parent


def _ai_roots(soup) -> set:
    """Identity set of the AI-overview containers on this page."""
    roots = {id(el) for el in soup.find_all(attrs={"data-attrid": "AIOverview"})}
    for head in soup.find_all(attrs={"role": "heading"}):
        if _txt(head, 40).lower().startswith("ai overview"):
            roots.add(id(_ai_root_from_heading(head)))
    return roots


def _walk(soup) -> Iterable[tuple[str, object]]:
    """Depth-first in document order, yielding (kind, element) and not descending into a hit.

    Not descending is what keeps a result from being emitted twice — Google nests
    MjjYud > tF2Cxc > yuRUbf, and every one of those would otherwise look like a result.
    """
    ai_roots = _ai_roots(soup)

    def visit(el):
        if not getattr(el, "name", None):
            return
        cls = _classes(el)
        if _is_ad_row(el):
            yield "sponsored", el
            return
        if cls & _LOCAL_ROW_CLASSES and el.find(class_="rllt__details"):
            yield "places", el
            return
        if id(el) in ai_roots:
            yield "ai_overview", el
            return
        # An organic wrapper that CONTAINS the map box is not one result — Google nests the
        # whole local pack inside an MjjYud on some layouts. Claiming it here consumed all
        # three pack rows as a single organic hit, and the map box vanished from the page
        # while "More places" still returned 21 clinics from the same query.
        if (cls & _ORGANIC_CLASSES) and el.find("h3") and not el.find(class_="rllt__details"):
            yield "organic", el
            return
        for child in el.children:
            yield from visit(child)

    yield from visit(soup)


def parse_blocks(html: str) -> list[dict]:
    """All result blocks on the page, numbered 1..N in one continuous down-page sequence."""
    soup = BeautifulSoup(html or "", "lxml")
    blocks: list[dict] = []
    seen_urls: set[str] = set()
    for kind, el in _walk(soup):
        pos = len(blocks) + 1
        if kind == "places":
            b = _extract_local(el, pos)
        elif kind == "sponsored":
            b = _extract_ad(el, pos, "sponsored_top")  # zone assigned below
        elif kind == "ai_overview":
            b = _extract_ai_overview(el, pos)
        else:
            b = _extract_organic(el, pos)
        if not b:
            continue
        if b["url"]:
            key = b["url"].split("#")[0]
            if key in seen_urls:
                continue
            seen_urls.add(key)
        blocks.append(b)
    return _assign_zones(blocks)


def _assign_zones(blocks: list[dict]) -> list[dict]:
    """Label every movable block by WHERE ON THE PAGE it sits.

    Google moves all three of these: the ad rail, the AI overview and the map box each appear
    above the results on one query and partway down on the next. A block a searcher meets
    before any result is a different signal from one they scroll past to reach, and from one
    below everything — the cheapest real estate on the page.

    Two anchors, because the map box is both a result and a thing being zoned:

    * ads and the AI overview are placed against RESULTS — organic rows and the map box alike.
      An overview under the map box is one the reader meets second, and calling it `top`
      contradicts what is on screen.
    * the map box is placed against the ORGANIC run only. Measuring it against a set that
      includes itself would make every pack `top` by definition.
    """
    organic = [i for i, b in enumerate(blocks) if b["block_type"] == "organic"]
    results = [i for i, b in enumerate(blocks)
               if b["block_type"] == "organic" or is_local_pack(b["block_type"])]

    def zone(i: int, anchor: list) -> str:
        if not anchor:
            return "top"
        if i < anchor[0]:
            return "top"
        return "bottom" if i > anchor[-1] else "mid"

    for i, b in enumerate(blocks):
        kind = b["block_type"]
        if kind.startswith("sponsored"):
            b["block_type"] = "sponsored_" + zone(i, results)
        elif is_local_pack(kind):
            b["block_type"] = "local_pack_" + zone(i, organic)
        elif kind.startswith("ai_overview") and kind != "ai_overview_unavailable":
            # An overview is only ever top or mid: Google never renders one below the results.
            b["block_type"] = ("ai_overview_top" if zone(i, results) == "top"
                               else "ai_overview_mid")
    return blocks


#: Every AI-overview flavour, for consumers that need to treat them as one family.
AI_BLOCK_TYPES = ("ai_overview_top", "ai_overview_mid", "ai_overview_unavailable")
#: The map box on the SERP itself. "places" is the legacy name the June corpus recorded.
LOCAL_PACK_TYPES = ("places", "local_pack_top", "local_pack_mid", "local_pack_bottom")
#: The expanded list behind "More places". Carries its parent box's zone.
LOCAL_PACK_MORE_TYPES = ("local_pack_more_top", "local_pack_more_mid",
                         "local_pack_more_bottom")


def is_ai_block(block_type: str) -> bool:
    return str(block_type or "").startswith("ai_overview")


def is_local_pack(block_type: str) -> bool:
    """The map box itself — never the expanded list behind it."""
    bt = str(block_type or "")
    return bt in LOCAL_PACK_TYPES


def is_local_pack_more(block_type: str) -> bool:
    return str(block_type or "").startswith("local_pack_more")


def local_pack_zone(blocks: list[dict]) -> str:
    """Which zone this page's map box landed in — the zone its expanded list inherits."""
    for b in blocks or []:
        if is_local_pack(b.get("block_type")):
            bt = str(b.get("block_type"))
            return bt.rsplit("_", 1)[-1] if bt != "places" else "top"
    return "top"


def search_box_text(html: str) -> str:
    """The query Google echoes back — authoritative for reconciling a capture to a query row."""
    soup = BeautifulSoup(html or "", "lxml")
    ta = soup.find("textarea", attrs={"name": "q"}) or soup.find("input", attrs={"name": "q"})
    if ta is None:
        return ""
    return _clean(ta.get("value") or ta.get_text(" ", strip=True) or "")


def looks_readable(html: str) -> bool:
    """Did the results *scaffolding* render?

    Structure, not size: a genuine zero-result SERP is small but well-formed, while Google's
    block page is a few KB with no results container at all. Sizing this on length would
    label an honest empty result unreadable and a block page readable — exactly backwards.
    Deciding whether a page is *blocked* belongs to serp_collector, not here.
    """
    if not html:
        return False
    low = html.lower()
    return bool(_RESULTS_SCAFFOLD_RE.search(low)) or ("<h3" in low)


def parse_serp(html: str, query_row: dict | None = None,
               screenshot_name: str | None = None, index: int | None = None) -> dict:
    """HTML -> one web_screens `queries[]` entry."""
    qr = query_row or {}
    blocks = parse_blocks(html)
    return {
        "index": index if index is not None else qr.get("rank"),
        "screenshot": screenshot_name,
        "rank": qr.get("rank"),
        "search_query": qr.get("search_query"),
        "search_box_text": search_box_text(html) or (qr.get("search_query") or ""),
        "match_confidence": "exact" if qr.get("search_query") else "unmatched",
        "readable": looks_readable(html),
        "blocks": blocks,
    }


def block_type_distribution(entries: list[dict]) -> dict:
    """Share of each block type across a run — the sanity gate against silent DOM drift."""
    counts: dict[str, int] = {}
    for e in entries:
        for b in e.get("blocks", []):
            counts[b["block_type"]] = counts.get(b["block_type"], 0) + 1
    total = sum(counts.values()) or 1
    return {"counts": counts, "total": total,
            "share": {k: round(v / total, 4) for k, v in counts.items()}}
