"""Third-party roundups: the practitioners other people recommend.

A Maps-only view sees the clinics that rank on Google Maps. It cannot see that a local health
blog's "10 best dermatologists in Guntur" recommends a practitioner who never showed up in the
scrape — and that absence is exactly the kind of thing a clinic paying for a market report
wants to know. So this stage reads the roundup pages already sitting in the SERP capture,
extracts the names they list, matches them to the run's clinics, and **surfaces the leftovers**
rather than dropping them.

Two deliberate limits, both from the plan:

* Mentions are market CONTEXT, not a score input, in v1. Feeding them into scoring would make
  snapshot #2 incomparable with a June snapshot that has no listicle signal.
* Fetching is injected. The job runner passes a browser-backed fetcher (real Chrome, so it
  survives this machine's TLS interception); tests pass a stub. This module never imports a
  browser and never blocks the run — a fetch failure is recorded and skipped.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from bs4 import BeautifulSoup

from modules import packs
from modules.web_collector import domain_of

_ROUNDUP_RE = re.compile(
    r"\b(best|top|leading|famous)\b.*\b(dermatolog|skin|hair|doctor|clinic|specialist)"
    r"|\btop\s*\d+\b|\b\d+\s+best\b|\bbest\s+\d+\b", re.I)

# Directory/aggregator hosts whose listing pages are effectively roundups.
_DIRECTORY_HOSTS = {"practo", "justdial", "lybrate", "sulekha", "skedoc", "drlogy",
                    "bajajfinservhealth", "apollo247"}


def is_roundup(title: str) -> bool:
    return bool(_ROUNDUP_RE.search(title or ""))


def find_candidates(screens: dict, ctx=None) -> list[dict]:
    """Roundup/directory URLs from the SERP capture, de-duplicated by URL.

    A clinic's own site is never a candidate — it lists one clinic (itself), not a field.
    """
    ctx = packs.resolve(ctx)
    seen, out = set(), []
    for q in screens.get("queries") or []:
        for b in q.get("blocks") or []:
            if b.get("block_type") not in ("organic", "sponsored_top", "sponsored_mid"):
                continue
            if b.get("platform") == "clinic_site":
                continue
            url = (b.get("url") or "").strip()
            if not url or url in seen:
                continue
            dom = domain_of(b.get("domain") or url)
            host = dom.split(".")[0] if dom else ""
            if is_roundup(b.get("title", "")) or host in _DIRECTORY_HOSTS:
                seen.add(url)
                out.append({"url": url, "domain": dom, "platform": b.get("platform"),
                            "title": b.get("title", ""),
                            "query": q.get("search_query")})
    return out


#: A leading ordinal on a roundup entry: "1.", "2)", "#3", "07 -".
_ORDINAL_RE = re.compile(r"^\s*#?\s*(\d{1,3})\s*[.):\-–—]?\s+")


def extract_entries(html: str) -> list[dict]:
    """Practitioners from a roundup, IN THE ORDER THE PAGE RANKS THEM.

    The ranking is the point. A "10 best dermatologists in Guntur" page is an ordered
    recommendation, and being #1 on it is a different fact from being #9 — returning a bare
    set of names throws away the only thing that made the page worth opening.

    Position comes from the page's own numbering when it prints one ("3. Dr X"), and falls
    back to document order when it does not, with `numbered` recording which happened so a
    reader never mistakes reading order for an editor's ranking.
    """
    soup = BeautifulSoup(html or "", "lxml")
    out, seen = [], set()

    def add(text: str, tag: str) -> None:
        text = re.sub(r"\s+", " ", text or "").strip()
        if not text:
            return
        m = _ORDINAL_RE.match(text)
        stated = int(m.group(1)) if m else None
        if m:
            text = text[m.end():].strip()
        # Section headers ("Best Dermatologists in Guntur") are not entries.
        if not text or len(text) > 80 or is_roundup(text):
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        out.append({"position": len(out) + 1, "stated_number": stated,
                    "name": text, "tag": tag})

    # Ordered lists first: when a roundup uses <ol>, that IS its ranking.
    for ol in soup.find_all("ol"):
        for li in ol.find_all("li", recursive=False):
            strong = li.find(["h2", "h3", "h4", "strong", "b", "a"])
            add(strong.get_text(" ", strip=True) if strong else li.get_text(" ", strip=True),
                "ol")
    for tag in soup.find_all(["h2", "h3", "h4", "strong", "b"]):
        add(tag.get_text(" ", strip=True), tag.name)
    return out


def extract_names(html: str) -> list[str]:
    """Back-compat: just the names, in rank order."""
    return [e["name"] for e in extract_entries(html)]


def _distinctive_tokens(name: str, stop: set) -> set:
    """A clinic name's identifying words, with the city and specialty words stripped — those
    appear in every local clinic's name and would match everything."""
    toks = re.findall(r"[a-z0-9]+", (name or "").lower())
    return {t for t in toks if len(t) >= 3 and t not in stop}


def _match(name: str, clinic_tokens: list[tuple], ctx, stop: set) -> Optional[dict]:
    """First run-clinic whose distinctive tokens are largely present in the listicle name.

    Same shape as the SERP block matcher: a clinic with <=2 distinctive tokens needs all of
    them present, otherwise at least two — enough to bind "VCare Hair & Skin Clinic" to a
    "VCare Skin Clinic" listing without matching every generic skin clinic to each other.

    The listicle-name side is stopword-filtered the same way the clinic side is, so a shared
    generic word (a specialty term the base stopwords miss on one side) can't create a match.
    And a single-distinctive-token clinic must match a reasonably distinctive token (length >=4),
    otherwise a two-letter fragment would bind unrelated clinics that happen to share it.
    """
    ntoks = {t for t in re.findall(r"[a-z0-9]+", (name or "").lower())
             if t not in stop and len(t) >= 3}
    for clinic, ctoks in clinic_tokens:
        if not ctoks:
            continue
        overlap = ctoks & ntoks
        if len(ctoks) == 1:
            tok = next(iter(ctoks))
            if len(tok) >= 4 and tok in ntoks:
                return clinic
            continue
        need = len(ctoks) if len(ctoks) == 2 else 2
        if len(overlap) >= need:
            return clinic
    return None


def collect(screens: dict, clinics: list[dict], ctx=None,
            fetch: Optional[Callable[[str], str]] = None, max_pages: int = 12) -> dict:
    """Fetch each roundup, extract names, split into matched mentions vs unmatched discoveries."""
    ctx = packs.resolve(ctx)
    fetch = fetch or (lambda url: "")
    stop = ctx.name_stopwords()
    clinic_tokens = [(c, _distinctive_tokens(c.get("name", ""), stop)) for c in clinics]
    candidates = find_candidates(screens, ctx)[:max_pages]
    mentions: dict[str, list] = {}
    unmatched: dict[str, dict] = {}
    errors: list[str] = []

    for cand in candidates:
        try:
            html = fetch(cand["url"])
        except Exception as exc:
            errors.append(f"{cand['url']}: {type(exc).__name__}: {exc}")
            continue
        for name in extract_names(html):
            hit = _match(name, clinic_tokens, ctx, stop)
            record = {"source_url": cand["url"], "source_domain": cand["domain"],
                      "source_title": cand["title"], "matched_text": name}
            if hit:
                mentions.setdefault(hit["key"], []).append(record)
            else:
                key = name.lower()
                if key not in unmatched:
                    unmatched[key] = {"name": name, "sources": []}
                unmatched[key]["sources"].append(cand["url"])

    unmatched_list = sorted(unmatched.values(), key=lambda u: (-len(u["sources"]), u["name"]))
    return {
        "mentions": mentions,
        "unmatched": unmatched_list,
        "errors": errors,
        "n_candidates": len(candidates),
        "n_mentions": sum(len(v) for v in mentions.values()),
        "n_unmatched": len(unmatched_list),
    }


def collect_from_run(run_dir, ctx, driver_factory=None, fetch: bool = False) -> dict:
    """Job-stage entry: read the run's SERP dataset + clinics, optionally fetch, persist result.

    `fetch=False` (the default) records the candidate roundups and their titles without opening
    a browser — useful and safe even when a live fetch isn't wanted. `fetch=True` uses a
    browser-backed fetcher so the pages themselves are read.
    """
    from pathlib import Path
    import config
    from modules import atomicio, report_adapter as ra, storage, vulnerability

    screens = atomicio.read_json(config.WEB_SCREENS_CACHE, default={}) or {}
    rows = storage.load_rows(storage.RESULTS_JSON) or []
    clinic_df = vulnerability.aggregate_clinics(rows)
    clinics = [ra.norm_clinic(r) for r in clinic_df.to_dict("records")]

    fetcher = None
    if fetch and driver_factory is not None:
        fetcher = _browser_fetcher(driver_factory)
    result = collect(screens, clinics, ctx, fetch=fetcher)
    atomicio.write_json(Path(run_dir) / "data" / "listicle_mentions.json", result, indent=2)
    return result


def _browser_fetcher(driver_factory) -> Callable[[str], str]:  # pragma: no cover - live only
    """A fetcher that reuses the SERP browser session (real Chrome, TLS-interception-safe)."""
    driver = driver_factory()
    started = {"v": False}

    def _fetch(url: str) -> str:
        if not started["v"]:
            driver.start()
            started["v"] = True
        res = driver.fetch(url)
        return res.html

    return _fetch
