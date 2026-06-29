"""Step 3 — Google Maps reviews collection (free, no API key).

Scrapes ALL Google Maps reviews per clinic with Playwright — the same surface
maps_collector.py already scrapes successfully. Mirrors that module's proven
patterns: the `_run_browser` worker-thread wrapper (Streamlit's asyncio loop
blocks the sync Playwright API, so the sync calls must run on a thread with no
event loop), consent handling, `_clean()` glyph stripping, UA/locale from config,
polite randomized delays, per-clinic graceful failure, and resume-from-cache.

Pure helpers (clinic-list extraction, mock data) are kept separate from the
browser-driving code so they can be unit-tested without a network or browser.
"""
from __future__ import annotations

import json
import random
import re
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")

from modules.maps_collector import _clean, dedup_key

# Cap reviews per clinic to bound run time (the pane can hold hundreds).
MAX_REVIEWS_PER_CLINIC = 150
# How many scroll attempts that load no new reviews before we stop.
_NO_GROWTH_LIMIT = 4
# Absolute ceiling on scroll iterations (safety against an infinite pane).
_MAX_SCROLLS = 80


def reviews_cache_path() -> str:
    return str(Path(config.CACHE_DIR) / "reviews_raw.json")


# --------------------------------------------------------------------------- clinic list
def clinics_from_rows(result_rows: list[dict]) -> list[dict]:
    """Collapse appearance rows into one {key, name, place_url} per unique clinic.

    Uses the same dedup identity as maps_collector/vulnerability so review data
    lines up 1:1 with the scored clinic table. Skips failed rows and rows with no
    usable Maps URL (reviews can't be opened without a place page).
    """
    seen: dict[str, dict] = {}
    for r in result_rows:
        if r.get("status") == "FETCH_FAILED":
            continue
        name = str(r.get("name") or "").strip()
        url = str(r.get("place_url") or "").strip()
        if not name or not url:
            continue
        key = dedup_key(url) or name.lower()
        if key not in seen:
            seen[key] = {"key": key, "name": name, "place_url": url}
    return list(seen.values())


# --------------------------------------------------------------------------- mock data
def _mock_reviews_for(name: str, n: int = 6) -> list[dict]:
    """Deterministic, varied fake reviews for offline demos / tests (no randomness, no network)."""
    templates = [
        (5, "Excellent doctor, very friendly staff. Highly recommend this clinic to everyone!", "2 weeks ago", None),
        (5, "Dr was amazing, clean clinic and short wait time. My friend referred me here.", "1 month ago",
         "Thank you for your kind words, we are glad we could help!"),
        (4, "Good treatment results for my acne. A bit expensive but worth the money.", "2 months ago", None),
        (2, "Waited over an hour past my appointment time. Staff was rude at reception.", "3 months ago",
         "We apologise for the wait, we are working on our scheduling."),
        (1, "Very poor experience. The treatment did not work and the cost was too high.", "5 months ago", None),
        (5, "Best dermatologist in town. I told my whole family about this place.", "a year ago", None),
    ]
    out = []
    for i in range(n):
        rating, text, rel, owner = templates[i % len(templates)]
        out.append({
            "author": f"Patient {i + 1}",
            "rating": rating,
            "text": text,
            "relative_date": rel,
            "owner_response": owner,
        })
    return out


def make_mock_reviews(clinics: list[dict], per_clinic: int = 6) -> dict:
    """Deterministic reviews keyed by clinic key — mirrors collect_reviews' return shape."""
    return {c["key"]: _mock_reviews_for(c["name"], per_clinic) for c in clinics}


# --------------------------------------------------------------------------- cache
def _load_cache() -> dict:
    try:
        with open(reviews_cache_path(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    Path(config.CACHE_DIR).mkdir(parents=True, exist_ok=True)
    with open(reviews_cache_path(), "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=2)


def _polite_sleep() -> None:
    time.sleep(random.uniform(config.SCRAPER_MIN_DELAY_S, config.SCRAPER_MAX_DELAY_S))


# --------------------------------------------------------------------------- parsing helpers
_REL_DATE_RE = re.compile(
    r"\b(?:a|an|\d+)\s+(?:second|minute|hour|day|week|month|year)s?\s+ago\b", re.I
)


def _parse_rating(aria: str) -> int | None:
    """Pull a 1-5 star rating from a review's aria-label, e.g. '4 stars' / 'Rated 5.0 out of 5'."""
    if not aria:
        return None
    m = re.search(r"(\d(?:[.,]\d)?)\s*star", aria, re.I)
    if not m:
        m = re.search(r"Rated\s+(\d(?:[.,]\d)?)", aria, re.I)
    if not m:
        m = re.search(r"(\d(?:[.,]\d)?)\s*(?:out of|/)\s*5", aria, re.I)
    if m:
        try:
            return int(round(float(m.group(1).replace(",", "."))))
        except ValueError:
            return None
    return None


def _parse_relative_date(text: str) -> str | None:
    """Extract a '2 months ago'-style token from a blob of card text."""
    if not text:
        return None
    m = _REL_DATE_RE.search(text)
    return m.group(0).strip() if m else None


# --------------------------------------------------------------------------- scraper
def _open_reviews_tab(page) -> None:
    """Click into the Reviews tab of an already-loaded place panel (best effort)."""
    for name in ("Reviews", "Reviews for", "More reviews"):
        try:
            tab = page.get_by_role("tab", name=re.compile(name, re.I))
            if tab.count() > 0:
                tab.first.click(timeout=4000)
                return
        except Exception:
            pass
    # fallback: a button/link whose aria-label mentions reviews
    for sel in ('button[aria-label*="Reviews" i]', 'button[jsaction*="moreReviews"]'):
        try:
            b = page.locator(sel).first
            if b.count() > 0:
                b.click(timeout=4000)
                return
        except Exception:
            pass


def _set_sort_newest(page) -> None:
    """Open the sort menu and choose Newest (best effort; markup is unstable)."""
    for sel in ('button[aria-label*="Sort" i]', 'button[data-value="Sort"]',
                'button[jsaction*="sort" i]'):
        try:
            b = page.locator(sel).first
            if b.count() > 0:
                b.click(timeout=4000)
                break
        except Exception:
            pass
    else:
        return
    try:
        page.wait_for_timeout(600)
        item = page.get_by_role("menuitemradio", name=re.compile("Newest", re.I))
        if item.count() == 0:
            item = page.get_by_role("menuitem", name=re.compile("Newest", re.I))
        if item.count() > 0:
            item.first.click(timeout=4000)
            page.wait_for_timeout(800)
    except Exception:
        pass


def _scrollable_reviews_pane(page):
    """Locate the scrollable reviews container (the feed that holds review cards)."""
    for sel in ('div.m6QErb[aria-label]', 'div.m6QErb.DxyBCb', 'div[role="feed"]'):
        loc = page.locator(sel)
        if loc.count() > 0:
            return loc.first
    return None


def _expand_more_buttons(page) -> None:
    """Click 'More' links so truncated review text is fully present in the DOM."""
    try:
        more = page.locator('button[aria-label="See more" i], button:has-text("More")')
        for i in range(min(more.count(), 30)):
            try:
                more.nth(i).click(timeout=600)
            except Exception:
                pass
    except Exception:
        pass


def _extract_reviews(page, cap: int) -> list[dict]:
    """Extract up to `cap` review dicts from the loaded, scrolled reviews pane.

    Targets Google's current review-card structure (div.jftiEf cards, .d4r55 author,
    [role=img][aria-label*=star] rating, .wiI7pd text, .rsqaWe relative date,
    .CDe7pd owner response). Markup is unstable, so this is the part to re-tune if
    Google changes it. Falls back to text heuristics where class names are missing.
    """
    _expand_more_buttons(page)
    out: list[dict] = []
    cards = page.locator("div.jftiEf")
    count = cards.count()
    if count == 0:  # fallback: cards carry data-review-id
        cards = page.locator("div[data-review-id]")
        count = cards.count()

    for i in range(min(count, cap)):
        card = cards.nth(i)
        rev = {"author": None, "rating": None, "text": "",
               "relative_date": None, "owner_response": None}
        try:
            # author
            author = None
            for sel in ("div.d4r55", "button.al6Kxe div", "div.WNxzHc"):
                loc = card.locator(sel)
                if loc.count() > 0:
                    author = _clean(loc.first.inner_text(timeout=800))
                    if author:
                        break
            rev["author"] = author or None

            # rating — the star widget aria-label
            aria = ""
            stars = card.locator('[role="img"][aria-label*="star" i], span[aria-label*="star" i]')
            if stars.count() > 0:
                aria = stars.first.get_attribute("aria-label") or ""
            if not aria:
                any_img = card.locator('[aria-label*="star" i]')
                if any_img.count() > 0:
                    aria = any_img.first.get_attribute("aria-label") or ""
            rev["rating"] = _parse_rating(aria)

            # review body text
            text = ""
            for sel in ("span.wiI7pd", "div.MyEned", "div.Jtu6Td"):
                loc = card.locator(sel)
                if loc.count() > 0:
                    text = _clean(loc.first.inner_text(timeout=800))
                    if text:
                        break
            rev["text"] = text

            # relative date
            rel = None
            for sel in ("span.rsqaWe", "span.dehysf"):
                loc = card.locator(sel)
                if loc.count() > 0:
                    rel = _clean(loc.first.inner_text(timeout=800))
                    if rel:
                        break
            if not rel:
                rel = _parse_relative_date(_clean(_safe_inner_text(card)))
            rev["relative_date"] = rel or None

            # owner response (clinic reply)
            owner = None
            for sel in ("div.CDe7pd", "div.wiI7pd.CDe7pd", 'div[class*="CDe7pd"]'):
                loc = card.locator(sel)
                if loc.count() > 0:
                    owner = _clean(loc.first.inner_text(timeout=800))
                    if owner:
                        break
            # strip a leading "Response from the owner" prefix + its date
            if owner:
                owner = re.sub(r"^Response from the owner\s*", "", owner, flags=re.I).strip()
                owner = _REL_DATE_RE.sub("", owner).strip()
            rev["owner_response"] = owner or None
        except Exception:
            pass
        # keep only cards that yielded something meaningful
        if rev["rating"] is not None or rev["text"] or rev["author"]:
            out.append(rev)
    return out


def _safe_inner_text(locator) -> str:
    try:
        return locator.inner_text(timeout=1200)
    except Exception:
        return ""


def _cid_url(clinic: dict) -> str | None:
    """Build a stable `?cid=<decimal>` URL from a hex feature-id key, when available.

    Google sometimes serves a degraded "limited view" (no Reviews tab) for a raw
    `/data=` deep link but resolves the canonical `?cid=` form fully — so this is
    tried as a fallback when the primary URL lands in limited view.
    """
    key = clinic.get("key") or ""
    m = re.search(r":0x([0-9a-fA-F]+)$", key)  # feature-id form 0x...:0x<cid-hex>
    if m:
        try:
            return f"https://www.google.com/maps?cid={int(m.group(1), 16)}&hl=en"
        except ValueError:
            return None
    if key.isdigit():  # already a decimal cid
        return f"https://www.google.com/maps?cid={key}&hl=en"
    return None


def _is_limited_view(page) -> bool:
    """True if Google served the throttled 'limited view' panel (no reviews available)."""
    try:
        return page.locator(':has-text("limited view")').count() > 0
    except Exception:
        return False


def _open_place(page, url: str) -> None:
    """Navigate to a place URL and clear the consent screen (shared by primary + fallback)."""
    page.goto(url, wait_until="domcontentloaded")
    for label in ("Reject all", "Accept all", "I agree"):
        try:
            btn = page.get_by_role("button", name=label)
            if btn.count() > 0:
                btn.first.click(timeout=3000)
                break
        except Exception:
            pass
    try:
        page.wait_for_selector("button[data-item-id], a[data-item-id], div[role='main']",
                               timeout=10000)
    except Exception:
        pass


def _scrape_one(page, clinic: dict, cap: int) -> list[dict]:
    """Open one clinic's place page, go to Reviews, sort Newest, scroll, extract.

    If the primary URL lands in Google's throttled "limited view" (no Reviews tab),
    retry once via the canonical `?cid=` URL form, which often resolves fully.
    """
    _open_place(page, clinic["place_url"])
    if _is_limited_view(page):  # primary URL throttled -> try the cid form
        alt = _cid_url(clinic)
        if alt and alt != clinic["place_url"]:
            _open_place(page, alt)

    _open_reviews_tab(page)
    try:
        page.wait_for_selector("div.jftiEf, div[data-review-id]", timeout=10000)
    except Exception:
        return []  # no reviews surfaced (limited view / clinic genuinely has none)
    _set_sort_newest(page)

    pane = _scrollable_reviews_pane(page)
    last = 0
    stale = 0
    for _ in range(_MAX_SCROLLS):
        cards = page.locator("div.jftiEf")
        n = cards.count()
        if n == 0:
            n = page.locator("div[data-review-id]").count()
        if n >= cap:
            break
        if n == last:
            stale += 1
            if stale >= _NO_GROWTH_LIMIT:
                break
        else:
            stale = 0
        last = n
        try:
            if pane is not None:
                pane.evaluate("el => el.scrollBy(0, el.scrollHeight)")
            else:
                page.mouse.wheel(0, 3000)
        except Exception:
            page.mouse.wheel(0, 3000)
        page.wait_for_timeout(int(random.uniform(900, 1500)))

    return _extract_reviews(page, cap)


def _run_browser(clinics: list[dict], cap: int, progress_cb=None,
                 cache: dict | None = None) -> dict:
    """Run the sync-Playwright review scrape in a worker thread.

    Streamlit's script-runner thread has a *running* asyncio loop, and Playwright's
    sync API refuses to run there. A fresh worker thread has no event loop, so the
    sync API works — while the caller's loop and progress callbacks stay on the
    main thread (mirrors maps_collector._run_browser).
    """
    box: dict = {}

    def _work():
        try:
            box["out"] = _run_browser_impl(clinics, cap, progress_cb, cache)
        except BaseException as exc:  # captured and re-raised on the caller thread
            box["err"] = exc

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    t.join()
    if "err" in box:
        raise box["err"]
    return box.get("out", {})


def _run_browser_impl(clinics: list[dict], cap: int, progress_cb=None,
                      cache: dict | None = None) -> dict:
    """Open each clinic, scrape its reviews. Network/browser side-effect.

    Resumes from `cache` (skips clinics already scraped). Per-clinic failures are
    swallowed so one bad clinic never aborts the batch.
    """
    from playwright.sync_api import sync_playwright

    cache = {} if cache is None else cache
    out: dict = {}
    n = len(clinics)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=config.SCRAPER_HEADLESS)
        context = browser.new_context(
            locale=config.SCRAPER_LOCALE, user_agent=config.SCRAPER_USER_AGENT
        )
        page = context.new_page()
        page.set_default_timeout(config.SCRAPER_PAGE_TIMEOUT_S * 1000)
        try:
            for i, clinic in enumerate(clinics, start=1):
                key = clinic["key"]
                if progress_cb:
                    progress_cb(i, n, clinic["name"])
                if key in cache:  # resume: already scraped this clinic
                    out[key] = cache[key]
                    continue
                # Google intermittently serves a throttled "limited view" with no
                # reviews; retry with backoff (a fresh page often resolves it).
                reviews: list[dict] = []
                for attempt in range(config.SCRAPER_MAX_RETRIES):
                    try:
                        reviews = _scrape_one(page, clinic, cap)
                    except Exception:
                        reviews = []  # graceful per-clinic failure
                    if reviews:
                        break
                    if attempt < config.SCRAPER_MAX_RETRIES - 1:
                        time.sleep(2 ** (attempt + 1))  # cooldown before retry
                out[key] = reviews
                if reviews:  # only cache non-empty results (retry empties next run)
                    cache[key] = reviews
                _polite_sleep()
        finally:
            browser.close()
    return out


def collect_reviews(clinics: list[dict], mock: bool = False, progress_cb=None,
                    cap: int = MAX_REVIEWS_PER_CLINIC) -> dict:
    """Collect reviews for each clinic, keyed by clinic key.

    Args:
        clinics: list of {"key", "name", "place_url"} (see `clinics_from_rows`).
        mock: when True, returns deterministic offline data (no network/browser).
        progress_cb: optional callable(i, n, clinic_name).
        cap: max reviews per clinic.

    Returns: {clinic_key: [ {author, rating, text, relative_date, owner_response}, ... ]}.
    Caches to .cache/reviews_raw.json and resumes from it on the next run.
    """
    if mock:
        return make_mock_reviews(clinics)

    cache = _load_cache()
    out = _run_browser(clinics, cap, progress_cb, cache)
    _save_cache(cache)
    out["_meta"] = {
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "n_clinics": len([k for k in out if k != "_meta"]),
        "cap": cap,
    }
    return out
