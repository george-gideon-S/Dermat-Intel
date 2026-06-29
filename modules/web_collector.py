"""Step 3 — Google WEB-search visibility collector (free, no API key).

Measures each clinic's organic Google Search visibility across the 50 query set — the future
40% web component of the vulnerability blend (see vulnerability.blend_final / web_relevance_vuln).

ONLY Google is used (no Bing/DuckDuckGo, no paid SERP API).

How the bot-wall was cracked (see the module's accompanying notes):
  * Plain headless `https://www.google.com/search?...` — and the `gbv=1`/`igu=1` basic-HTML and
    `requests`-only variants — are all rejected: headless gets bounced to `/sorry/index`
    ("unusual traffic … not a robot" reCAPTCHA), and a cookieless `requests` hit gets the
    `enablejs` interstitial. Google Web Search guards far more aggressively than Google Maps.
  * The reliable free path is a REAL desktop browser: launch the installed Google Chrome
    (`channel="chrome"`) **headful** with a **persistent context**, mask the obvious automation
    signals, warm up on `google.com`, accept the consent cookie once, then drive the search box
    like a human and reuse the same profile/cookies for every query. The first query may surface a
    one-time CAPTCHA the human solves; cookies then carry the rest of the run.

Everything here degrades gracefully: if Google blocks (e.g. running headless on a flagged network),
`search_google` returns `[]` and the pipeline simply records "no web data" for that query rather
than crashing. Pure helpers (domain parse / matching / metrics) are kept network-free and unit-tested.
"""
from __future__ import annotations

import json
import random
import re
import threading
import time
import urllib.parse
from pathlib import Path
from urllib.parse import urlparse

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")

# Reuse the proven, already-tested helpers from the Maps collector.
from modules.maps_collector import _clean, dedup_key

# --------------------------------------------------------------------------- settings
WEB_CACHE = str(Path(config.CACHE_DIR) / "web_raw.json")

# Try the real installed Chrome first (its fingerprint matches a genuine browser, which is what
# lets the headful path through Google's wall); fall back to bundled Chromium if Chrome is absent.
_CHROME_CHANNEL = "chrome"
# Headful is what actually passes Google Web Search. Headless is detected and bounced to /sorry/,
# so the default mirrors a real desktop run. Flip via env for CI/experiments.
import os
_WEB_HEADLESS = os.environ.get("DERMA_WEB_HEADLESS", "0") == "1"
_PROFILE_DIR = str(Path(config.CACHE_DIR) / "web_profile")

_RESULT_DOMAINS_TO_DROP = {
    "google.com", "google.co.in", "webcache.googleusercontent.com",
    "translate.google.com", "policies.google.com", "support.google.com",
    "accounts.google.com", "maps.google.com",
}

# Anti-automation init script: erase the most common headless / Playwright tells.
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-IN', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
const _q = window.navigator.permissions && window.navigator.permissions.query;
if (_q) {
  window.navigator.permissions.query = (p) =>
    p && p.name === 'notifications'
      ? Promise.resolve({state: Notification.permission})
      : _q(p);
}
"""

_CONSENT_LABELS = ("Accept all", "I agree", "Accept the use of cookies",
                   "Aceptar todo", "Reject all")


# --------------------------------------------------------------------------- pure helpers
def domain_of(url: str) -> str:
    """Registrable-ish host of a URL, lower-cased, without a leading 'www.'.

    Tolerates protocol-relative ('//x.com/...') and bare ('x.com/path') inputs so it works on
    both result hrefs and the clinics' own stored website strings. Returns '' when unparseable.
    """
    if not url:
        return ""
    u = url.strip()
    if u.startswith("//"):
        u = "http:" + u
    if "://" not in u:
        u = "http://" + u
    try:
        host = (urlparse(u).hostname or "").lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _unwrap_google_redirect(href: str) -> str:
    """Turn a Google '/url?q=<real>&...' redirect (basic-HTML SERP) into the real target URL."""
    if not href:
        return ""
    if href.startswith("/url?") or "google.com/url?" in href:
        try:
            qs = urllib.parse.urlparse(href).query
            params = urllib.parse.parse_qs(qs)
            for key in ("q", "url"):
                if key in params and params[key]:
                    return params[key][0]
        except Exception:
            return href
    return href


def _normalize_results(raw: list[dict], max_results: int) -> list[dict]:
    """De-dupe by domain+url, drop Google-internal links, re-number positions 1..N."""
    out: list[dict] = []
    seen: set[str] = set()
    for r in raw:
        url = (r.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        dom = domain_of(url)
        if not dom or dom in _RESULT_DOMAINS_TO_DROP:
            continue
        key = url.split("#")[0]
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "title": _clean(r.get("title") or ""),
            "url": url,
            "domain": dom,
            "position": len(out) + 1,
        })
        if len(out) >= max_results:
            break
    return out


# --------------------------------------------------------------------------- matching / metrics
_TOKEN_STOPWORDS = {
    "the", "and", "in", "of", "for", "best", "top", "skin", "clinic", "clinics",
    "hospital", "hospitals", "centre", "center", "care", "dr", "drs", "doctor",
    "dermatologist", "dermatology", "cosmetologist", "cosmetic", "laser", "hair",
    "guntur", "near", "me", "specialist",
}


def _name_tokens(name: str) -> set[str]:
    """Distinctive lower-case word tokens of a clinic name (Google Maps names are keyword-stuffed,
    so generic specialty/location words are dropped to avoid matching every result)."""
    cleaned = _clean(name).lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    toks = {t for t in cleaned.split() if len(t) >= 3 and t not in _TOKEN_STOPWORDS}
    return toks


def _result_matches_clinic(result: dict, name_tokens: set[str], clinic_domain: str) -> bool:
    """A result counts for a clinic if its own website domain shows up in the result URL/domain,
    OR enough of the clinic's distinctive name tokens appear in the result title."""
    if clinic_domain:
        rdom = result.get("domain", "")
        if rdom == clinic_domain or rdom.endswith("." + clinic_domain) or clinic_domain.endswith("." + rdom):
            return True
        if clinic_domain in (result.get("url") or "").lower():
            return True
    if name_tokens:
        title = _clean(result.get("title") or "").lower()
        title = re.sub(r"[^a-z0-9\s]", " ", title)
        title_words = set(title.split())
        hits = name_tokens & title_words
        # 1 distinctive token is enough for a very specific name (few tokens); otherwise need >=2.
        need = 1 if len(name_tokens) <= 2 else 2
        if len(hits) >= need:
            return True
    return False


def match_clinics_web(web_by_query: dict, clinics: list[dict]) -> dict:
    """Per-clinic web-visibility metrics from the collected SERPs.

    Returns {clinic_key: {"web_appearances": int, "web_best_position": int|None, "web_data": True}}.
    `clinic_key` mirrors the Maps identity (dedup_key(place_url) or lowercased name) so it joins
    straight onto the aggregated clinic rows. A clinic matches a result when its cleaned name tokens
    appear in the result title OR its own website domain appears in any result URL.
    """
    prepared = []
    for c in clinics:
        key = dedup_key(c.get("place_url", "")) or str(c.get("name") or "").strip().lower()
        if not key:
            continue
        prepared.append((key, _name_tokens(c.get("name", "")), domain_of(c.get("website", ""))))

    out: dict[str, dict] = {
        key: {"web_appearances": 0, "web_best_position": None, "web_data": True}
        for key, _, _ in prepared
    }

    for results in web_by_query.values():
        if not results:
            continue
        for key, tokens, dom in prepared:
            for res in results:
                if _result_matches_clinic(res, tokens, dom):
                    rec = out[key]
                    rec["web_appearances"] += 1
                    pos = res.get("position")
                    if pos is not None and (rec["web_best_position"] is None or pos < rec["web_best_position"]):
                        rec["web_best_position"] = pos
                    break  # at most one appearance per query per clinic
    return out


# --------------------------------------------------------------------------- mock
def _mock_results_for(query: str, max_results: int) -> list[dict]:
    """Deterministic offline SERP so the pipeline is demoable without scraping."""
    base = [
        ("https://www.practo.com/guntur/dermatologist", "Best Dermatologists in Guntur - Practo"),
        ("https://drraginipuvvala.getmy.clinic/", "Dr Ragini's Skin & Hair Clinic, Guntur"),
        ("https://chandanaskinclinic.com/", "Chandana Skin Clinic | Dermatologist Guntur"),
        ("https://www.justdial.com/Guntur/Dermatologists", "Skin Doctors in Guntur - Justdial"),
        ("https://drsowmyaskinclinics.com/", "Dr Sowmya Skin Hair Laser Clinic - Guntur"),
        ("https://www.lybrate.com/guntur/dermatologist", "Top Skin Specialists in Guntur - Lybrate"),
    ]
    h = abs(hash(query)) % len(base)
    rotated = base[h:] + base[:h]
    return _normalize_results(
        [{"url": u, "title": t} for u, t in rotated], max_results
    )


# --------------------------------------------------------------------------- browser (threaded)
def _run_browser(query: str, max_results: int) -> list[dict]:
    """Run the sync-Playwright Google-Search scrape in a worker thread.

    Identical rationale to maps_collector._run_browser: Streamlit's script thread already has a
    running asyncio loop and Playwright's sync API refuses to start there ("Sync API inside the
    asyncio loop"). A fresh worker thread has no loop, so the sync API works; the caller's loop and
    any progress callbacks stay on the main thread. Errors are captured and re-raised on the caller.
    """
    box: dict = {}

    def _work():
        try:
            box["results"] = _run_browser_impl(query, max_results)
        except BaseException as exc:  # captured, re-raised on caller thread
            box["err"] = exc

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    t.join()
    if "err" in box:
        raise box["err"]
    return box.get("results", [])


def _launch_context(p, headless=None):
    """Persistent Chrome context (real channel first, bundled Chromium as fallback)."""
    hl = _WEB_HEADLESS if headless is None else headless
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-gpu",
        "--window-size=1366,768",
    ]
    if hl:  # explicit new-headless if someone forces headless mode
        args.append("--headless=new")
    Path(_PROFILE_DIR).mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        user_data_dir=_PROFILE_DIR,
        headless=hl,
        args=args,
        locale=config.SCRAPER_LOCALE,
        timezone_id="Asia/Kolkata",
        viewport={"width": 1366, "height": 768},
        user_agent=config.SCRAPER_USER_AGENT,
        ignore_default_args=["--enable-automation"],
    )
    try:
        return p.chromium.launch_persistent_context(channel=_CHROME_CHANNEL, **kwargs)
    except Exception:
        # Real Chrome not installed — fall back to bundled Chromium (more likely to be blocked,
        # but still the right code path; returns [] gracefully if Google bounces it).
        return p.chromium.launch_persistent_context(**kwargs)


def _handle_consent(page) -> None:
    for label in _CONSENT_LABELS:
        try:
            btn = page.get_by_role("button", name=re.compile(re.escape(label), re.I))
            if btn.count() > 0:
                btn.first.click(timeout=2500)
                time.sleep(1.0)
                return
        except Exception:
            pass


def _blocked(page) -> bool:
    try:
        return "/sorry/" in page.url or "consent.google.com" in page.url
    except Exception:
        return False


def _extract_serp(page, max_results: int) -> list[dict]:
    """Pull organic results from a loaded SERP.

    Primary: anchors that wrap an <h3> inside the main results column (current Google markup).
    Fallback: basic-HTML '/url?q=' redirect anchors (the gbv=1 no-JS layout).
    """
    raw: list[dict] = []
    try:
        anchors = page.locator("div#search a:has(h3), div#rso a:has(h3), a:has(h3)")
        n = anchors.count()
        for i in range(min(n, max_results * 2)):
            a = anchors.nth(i)
            href = a.get_attribute("href") or ""
            if not href.startswith("http"):
                continue
            h3 = a.locator("h3").first
            title = ""
            if h3.count() > 0:
                try:
                    title = h3.inner_text(timeout=1200)
                except Exception:
                    title = ""
            raw.append({"url": href, "title": title})
    except Exception:
        pass

    if not raw:  # basic-HTML fallback (gbv=1)
        try:
            anchors = page.locator('a[href^="/url?q="], a[href*="google.com/url?q="]')
            n = anchors.count()
            for i in range(min(n, max_results * 2)):
                a = anchors.nth(i)
                href = _unwrap_google_redirect(a.get_attribute("href") or "")
                if not href.startswith("http"):
                    continue
                try:
                    title = a.inner_text(timeout=1000)
                except Exception:
                    title = ""
                raw.append({"url": href, "title": title})
        except Exception:
            pass

    return _normalize_results(raw, max_results)


def _run_browser_impl(query: str, max_results: int) -> list[dict]:
    """Open Google Web Search for one query and return normalized organic results.

    Strategy that passes the wall on a real desktop: warm up on google.com, accept consent once,
    then drive the search box like a human (type + Enter) rather than deep-linking /search.
    Returns [] (never raises for an ordinary block) when Google serves /sorry/ or consent walls.
    """
    from playwright.sync_api import sync_playwright

    # AI queries already imply specialty; ensure the city is present (mirrors maps_collector).
    search_text = query if "guntur" in query.lower() else f"{query} Guntur"

    with sync_playwright() as p:
        ctx = _launch_context(p)
        try:
            ctx.add_init_script(_STEALTH_JS)
        except Exception:
            pass
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(config.SCRAPER_PAGE_TIMEOUT_S * 1000)
        results: list[dict] = []
        try:
            # 1) warm up + consent on the homepage (reuses persistent cookies on later queries)
            try:
                page.goto("https://www.google.com/?hl=en&gl=in", wait_until="domcontentloaded")
                time.sleep(random.uniform(0.8, 1.6))
                _handle_consent(page)
            except Exception:
                pass

            # 2) human-like search via the box (deep-linking /search is flagged faster)
            navigated = False
            try:
                box = page.locator('textarea[name="q"], input[name="q"]').first
                if box.count() > 0:
                    box.click()
                    box.fill("")
                    box.type(search_text, delay=random.randint(60, 130))
                    time.sleep(random.uniform(0.4, 1.0))
                    try:
                        with page.expect_navigation(timeout=12000, wait_until="domcontentloaded"):
                            box.press("Enter")
                    except Exception:
                        pass
                    navigated = True
            except Exception:
                navigated = False

            # 3) fallback: direct /search URL if the box wasn't available
            if not navigated:
                term = urllib.parse.quote_plus(search_text)
                url = f"https://www.google.com/search?q={term}&num={max(max_results, 10)}&hl=en&gl=in&pws=0"
                try:
                    page.goto(url, wait_until="domcontentloaded")
                except Exception:
                    pass

            time.sleep(random.uniform(1.0, 2.0))
            _handle_consent(page)

            if _blocked(page):
                return []  # graceful: Google served the CAPTCHA / consent wall

            try:
                page.wait_for_selector("div#search, div#rso, a:has(h3)", timeout=8000)
            except Exception:
                pass

            results = _extract_serp(page, max_results)
        finally:
            try:
                ctx.close()
            except Exception:
                pass
        return results


# --------------------------------------------------------------------------- public scrape
def search_google(query: str, max_results: int = 10) -> list[dict]:
    """Return up to `max_results` organic Google results for `query`.

    Each result: {"title": str, "url": str, "domain": str, "position": int (1-based)}.
    Consent-safe and block-safe: returns [] (never raises) if Google blocks or no results parse.
    """
    if not query or not str(query).strip():
        return []
    try:
        return _run_browser(str(query), max_results)
    except Exception:
        return []


# --------------------------------------------------------------------------- cache
def _load_cache() -> dict:
    try:
        with open(WEB_CACHE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    Path(WEB_CACHE).parent.mkdir(parents=True, exist_ok=True)
    with open(WEB_CACHE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=2)


def _polite_sleep() -> None:
    # Web search needs gentler pacing than Maps; 5-15s human-like gaps reduce the block rate.
    time.sleep(random.uniform(5.0, 15.0))


def collect_web_interactive(query_rows, max_results: int = 10, progress_cb=None,
                            solve_timeout: float = 300.0) -> dict:
    """Human-in-the-loop Google collection.

    Opens ONE persistent, visible Chrome window reused across every query and PAUSES for you to
    solve any CAPTCHA (polls until the /sorry wall clears, up to `solve_timeout`s). Because the
    profile is persistent (`.cache/web_profile/`), Google's cookies usually clear the wall after one
    or two solves and the rest flow automatically. Cache-first (`.cache/web_raw.json`), saved after
    every success so you can quit and resume. Returns {query: [results]}.
    """
    from playwright.sync_api import sync_playwright

    cache = _load_cache()
    queries = [q.get("search_query", "") for q in query_rows if q.get("search_query")]
    out = {q: cache[q] for q in queries if cache.get(q)}
    todo = [q for q in queries if not cache.get(q)]
    if not todo:
        return out

    with sync_playwright() as p:
        ctx = _launch_context(p, headless=False)  # always visible so you can solve the CAPTCHA
        try:
            ctx.add_init_script(_STEALTH_JS)
        except Exception:
            pass
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(config.SCRAPER_PAGE_TIMEOUT_S * 1000)
        try:
            page.goto("https://www.google.com/?hl=en&gl=in", wait_until="domcontentloaded")
            time.sleep(1.0)
            _handle_consent(page)
        except Exception:
            pass

        n = len(todo)
        for i, query in enumerate(todo, start=1):
            if progress_cb:
                progress_cb(i, n, query)
            search_text = query if "guntur" in query.lower() else f"{query} Guntur"
            term = urllib.parse.quote_plus(search_text)
            url = f"https://www.google.com/search?q={term}&num={max(max_results, 10)}&hl=en&gl=in&pws=0"
            try:
                page.goto(url, wait_until="domcontentloaded")
            except Exception:
                pass
            time.sleep(1.0)
            _handle_consent(page)

            if _blocked(page):
                print(f"   CAPTCHA shown — solve it in the browser window for query {i}/{n}; "
                      f"I'll continue automatically once it clears...", flush=True)
                waited = 0.0
                while _blocked(page) and waited < solve_timeout:
                    time.sleep(3.0)
                    waited += 3.0
                if _blocked(page):
                    print(f"   Skipped '{query}' (not solved in {int(solve_timeout)}s) — "
                          f"re-run --web to retry it.", flush=True)
                    continue
                _handle_consent(page)

            try:
                page.wait_for_selector("div#search, div#rso, a:has(h3)", timeout=8000)
            except Exception:
                pass
            res = _extract_serp(page, max_results)
            if res:
                cache[query] = res
                out[query] = res
                _save_cache(cache)  # persist after each success (resume-safe)
            time.sleep(random.uniform(1.5, 3.5))  # session is warm now; gentler pacing is fine

        try:
            ctx.close()
        except Exception:
            pass
    return out


# --------------------------------------------------------------------------- collect
def collect_web(query_rows: list[dict], mock: bool = False, progress_cb=None) -> dict:
    """Collect organic Google results for every query, keyed by the query string.

    Returns {search_query: [result, ...]}. Cache-first via .cache/web_raw.json; **failed/empty
    scrapes are never cached** (so a blocked query is retried next run). `mock=True` returns
    deterministic offline SERPs. Polite randomized 5-15s gaps between live queries.
    """
    if mock:
        out: dict[str, list[dict]] = {}
        for q in query_rows:
            query = q.get("search_query", "")
            if query:
                out[query] = _mock_results_for(query, config.RESULTS_PER_QUERY)
        return out

    cache = _load_cache()
    results_by_query: dict[str, list[dict]] = {}
    n = len(query_rows)
    for i, q in enumerate(query_rows, start=1):
        query = q.get("search_query", "")
        if not query:
            continue
        if progress_cb:
            progress_cb(i, n, query)

        if cache.get(query):  # reuse only non-empty cached results (never a past failure)
            results_by_query[query] = cache[query]
            continue

        results = search_google(query, config.RESULTS_PER_QUERY)
        if results:  # don't cache failures/empties → retried next run
            cache[query] = results
            _save_cache(cache)  # persist incrementally so a mid-run block doesn't lose progress
        results_by_query[query] = results
        _polite_sleep()

    return results_by_query


if __name__ == "__main__":  # pragma: no cover - manual smoke run
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    qs = [{"search_query": "best dermatologist in Guntur"}]
    print(json.dumps(collect_web(qs), ensure_ascii=False, indent=2))
