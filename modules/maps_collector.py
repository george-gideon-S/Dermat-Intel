"""Step 2 — Google Maps data collection (free, no API key).

Primary path: scrape Google Maps with Playwright (same source as the paid Places API).
Pure, testable helpers (model / mock / dedup / listing-parse) are kept separate from the
browser-driving code so they can be unit-tested without a network or browser.
A deterministic `mock=True` mode makes the whole dashboard demoable offline.
"""
from __future__ import annotations

import json
import random
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")


# --------------------------------------------------------------------------- data model
RESULT_COLUMNS = [
    "name", "rating", "user_ratings_total", "types", "formatted_address",
    "formatted_phone_number", "website", "opening_hours", "business_status", "price_level",
    "lat", "lng", "place_url", "place_id",
    "source_query_rank", "source_query", "source_category", "result_position",
    "fetched_at", "status",
]


def empty_result_row() -> dict:
    """A result row with safe defaults: '' for strings, None for numbers."""
    return {
        "name": "", "rating": None, "user_ratings_total": None, "types": "",
        "formatted_address": "", "formatted_phone_number": None, "website": "",
        "opening_hours": "", "business_status": "OPERATIONAL", "price_level": None,
        "lat": None, "lng": None, "place_url": "", "place_id": "",
        "source_query_rank": None, "source_query": "", "source_category": "",
        "result_position": None, "fetched_at": "", "status": "OK",
    }


def dedup_key(place_url: str) -> str:
    """Stable identity for a clinic, extracted from its Google Maps URL."""
    if not place_url:
        return ""
    m = re.search(r"[?&]cid=([0-9]+)", place_url)
    if m:
        return m.group(1)
    m = re.search(r"place_id:([A-Za-z0-9_\-]+)", place_url)
    if m:
        return m.group(1)
    m = re.search(r"!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)", place_url)  # feature-id form
    if m:
        return m.group(1)
    return place_url


def parse_listing(raw: dict, query_row: dict, position: int) -> dict:
    """Map a raw scraped/mock listing dict onto the canonical result-row contract."""
    row = empty_result_row()
    url = raw.get("url", "") or ""
    row.update(
        name=raw.get("name", "") or "",
        rating=raw.get("rating"),
        user_ratings_total=raw.get("reviews"),
        types=raw.get("types", "") or "",
        formatted_address=raw.get("address", "") or "",
        formatted_phone_number=raw.get("phone"),
        website=raw.get("website", "") or "",
        opening_hours=raw.get("opening_hours", "") or "",
        business_status=(raw.get("status_label") or "CLOSED") if raw.get("closed") else "OPERATIONAL",
        price_level=raw.get("price_level"),
        lat=raw.get("lat"),
        lng=raw.get("lng"),
        place_url=url,
        place_id=dedup_key(url),
        source_query_rank=query_row.get("rank"),
        source_query=query_row.get("search_query", ""),
        source_category=query_row.get("category", ""),
        result_position=position,
        fetched_at=datetime.now().isoformat(timespec="seconds"),
        status="OK",
    )
    return row


# --------------------------------------------------------------------------- mock data
_MOCK_NAMES = [
    "Sai Skin & Hair Clinic", "Guntur Derma Care", "Sri Sai Skin Clinic",
    "Lakshmi Skin Care Centre", "Apollo Skin Clinic", "Sravani Dermatology",
    "Vasavi Skin & Laser Clinic", "Sunrise Skin Hospital", "Sree Ramya Skin Clinic",
    "Amaravathi Skin Care", "Renova Skin Clinic", "Padma Dermatology Centre",
    "Care Well Skin Clinic", "Glow Derma Clinic", "Sushrutha Skin Clinic",
    "NRI Skin Institute", "Vijaya Skin Care", "KIMS Skin Department",
    "Hema Skin & Cosmetology", "Sri Krishna Skin Clinic", "Deccan Derma",
    "Pranaam Skin Clinic", "Akshara Skin Care", "Tejaswi Dermatology",
    "Manipal Skin Clinic", "Skin Solutions Guntur", "Aesthetica Skin Studio",
    "Reddy's Skin & Laser",
]


def _mock_pool() -> list[dict]:
    """Deterministic pool of fake Guntur clinics with realistic variety (no randomness)."""
    ratings = [None, 2.8, 3.2, 3.6, 4.0, 4.3, 4.6, 4.9]
    reviews = [0, 5, 12, 18, 40, 90, 150, 320]
    pool = []
    for idx, name in enumerate(_MOCK_NAMES):
        website = "" if idx % 3 == 0 else f"https://{re.sub(r'[^a-z]', '', name.lower())[:12]}.example.com"
        phone = None if idx % 4 == 0 else f"+91 9{(40000000 + idx * 137):08d}"
        pool.append({
            "name": name,
            "rating": ratings[idx % len(ratings)],
            "reviews": reviews[idx % len(reviews)],
            "types": "Dermatologist" if idx % 2 == 0 else "Skin care clinic",
            "address": f"{idx + 1}-{idx * 3 + 7}, Brodipet, Guntur, Andhra Pradesh 522002",
            "phone": phone,
            "website": website,
            "opening_hours": "Mon-Sat 10:00-20:00",
            "closed": (idx % 13 == 0 and idx != 0),
            "status_label": "TEMPORARILY_CLOSED",
            "price_level": None,
            "lat": round(16.2990 + (idx % 9) * 0.0035, 6),
            "lng": round(80.4250 + (idx % 7) * 0.0040, 6),
            "url": f"https://www.google.com/maps/place/?cid={1000 + idx}",
        })
    return pool


def make_mock_results(query_rows: list[dict], per_query: int | None = None) -> list[dict]:
    """Build deterministic result rows so clinics overlap across queries (realistic appearances)."""
    per_query = per_query or config.RESULTS_PER_QUERY
    pool = _mock_pool()
    rows: list[dict] = []
    for q in query_rows:
        start = (int(q.get("rank", 1)) * 2) % len(pool)  # shift the window per query
        for pos in range(1, per_query + 1):
            raw = pool[(start + pos - 1) % len(pool)]
            rows.append(parse_listing(raw, q, pos))
    return rows


# --------------------------------------------------------------------------- OSM fallback
def geocode_osm(address: str):
    """Free, keyless geocoding via OpenStreetMap Nominatim. Returns (lat, lng) or None."""
    if not address:
        return None
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "derma-intel/1.0 (research)"},
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data:
            return None
        return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception:
        return None


# --------------------------------------------------------------------------- cache
def _load_cache() -> dict:
    try:
        with open(config.MAPS_CACHE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    Path(config.MAPS_CACHE).parent.mkdir(parents=True, exist_ok=True)
    with open(config.MAPS_CACHE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=2)


def _polite_sleep() -> None:
    time.sleep(random.uniform(config.SCRAPER_MIN_DELAY_S, config.SCRAPER_MAX_DELAY_S))


# --------------------------------------------------------------------------- scraper
def _extract_cards(page, max_results: int) -> list[dict]:
    """Extract up to `max_results` listing dicts from a loaded Google Maps results feed.

    NOTE: Google Maps markup is unstable; this uses resilient anchor + aria-label parsing and
    is the part to tune during live verification (plan Task 16). Pure helpers above are tested.
    """
    raws: list[dict] = []
    links = page.locator('a[href*="/maps/place/"]')
    count = min(links.count(), max_results)
    for i in range(count):
        link = links.nth(i)
        raw = {"name": "", "url": ""}
        try:
            raw["url"] = link.get_attribute("href") or ""
            raw["name"] = (link.get_attribute("aria-label") or "").strip()
            card = link.locator("xpath=..")
            text = card.inner_text(timeout=2000)
            # rating + reviews e.g. "4.6\n(120)"
            m = re.search(r"(\d\.\d)\s*\(?\s*([\d,]+)\)?", text)
            if m:
                raw["rating"] = float(m.group(1))
                raw["reviews"] = int(m.group(2).replace(",", ""))
            # crude address line (last comma-bearing line)
            for line in reversed(text.splitlines()):
                if "Guntur" in line or "," in line:
                    raw["address"] = line.strip()
                    break
            # lat/lng from the place URL (!3dLAT!4dLNG)
            mll = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", raw["url"])
            if mll:
                raw["lat"], raw["lng"] = float(mll.group(1)), float(mll.group(2))
            raw["closed"] = "Permanently closed" in text or "Temporarily closed" in text
            wl = card.locator('a[href^="http"]:not([href*="google.com"])')
            if wl.count() > 0:
                raw["website"] = wl.first.get_attribute("href") or ""
        except Exception:
            pass
        raws.append(raw)
    return raws


def _run_browser(query: str, max_results: int) -> list[dict]:
    """Open Google Maps for a query and return raw listing dicts. Network/browser side-effect."""
    from playwright.sync_api import sync_playwright

    term = urllib.parse.quote_plus(f"{query} {config.SPECIALTY} Guntur")
    url = f"https://www.google.com/maps/search/{term}"
    raws: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=config.SCRAPER_HEADLESS)
        context = browser.new_context(
            locale=config.SCRAPER_LOCALE, user_agent=config.SCRAPER_USER_AGENT
        )
        page = context.new_page()
        page.set_default_timeout(config.SCRAPER_PAGE_TIMEOUT_S * 1000)
        try:
            page.goto(url, wait_until="domcontentloaded")
            # consent screen
            for label in ("Reject all", "Accept all", "I agree"):
                try:
                    btn = page.get_by_role("button", name=label)
                    if btn.count() > 0:
                        btn.first.click(timeout=3000)
                        break
                except Exception:
                    pass
            try:
                page.wait_for_selector('a[href*="/maps/place/"]', timeout=12000)
            except Exception:
                pass
            # scroll the feed to lazy-load results
            feed = page.locator('[role="feed"]')
            last = 0
            for _ in range(12):
                links = page.locator('a[href*="/maps/place/"]')
                n = links.count()
                if n >= max_results or n == last:
                    if n == last:
                        break
                last = n
                try:
                    if feed.count() > 0:
                        feed.evaluate("el => el.scrollBy(0, el.scrollHeight)")
                    else:
                        page.mouse.wheel(0, 3000)
                except Exception:
                    page.mouse.wheel(0, 3000)
                time.sleep(1.2)
            raws = _extract_cards(page, max_results)
        finally:
            browser.close()
    return raws


def scrape_query(query_row: dict, max_results: int, cache: dict) -> list[dict]:
    """Scrape one query (cache-first), map to result rows, dedupe + OSM-geocode gaps."""
    q = query_row["search_query"]
    if q in cache:
        raws = cache[q]
    else:
        raws = []
        for attempt in range(config.SCRAPER_MAX_RETRIES):
            try:
                raws = _run_browser(q, max_results)
                if raws:
                    break
            except Exception:
                time.sleep(2 ** (attempt + 1))
        cache[q] = raws
        _polite_sleep()

    if not raws:
        fail = empty_result_row()
        fail.update(source_query_rank=query_row.get("rank"), source_query=q,
                    source_category=query_row.get("category", ""), result_position=1,
                    status="FETCH_FAILED", fetched_at=datetime.now().isoformat(timespec="seconds"))
        return [fail]

    rows, seen = [], set()
    for pos, raw in enumerate(raws[:max_results], start=1):
        row = parse_listing(raw, query_row, pos)
        key = dedup_key(row["place_url"]) or row["name"].lower()
        if config.USE_OSM_FALLBACK and (row["lat"] is None or row["lng"] is None) and row["formatted_address"]:
            geo = geocode_osm(row["formatted_address"])
            if geo:
                row["lat"], row["lng"] = geo
        if key and key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def collect(query_rows: list[dict], mock: bool = False, progress_cb=None) -> list[dict]:
    """Collect result rows for all queries. `mock=True` returns deterministic offline data."""
    if mock:
        rows: list[dict] = []
        for q in query_rows:
            rows.extend(make_mock_results([q], per_query=config.RESULTS_PER_QUERY))
        return rows

    cache = _load_cache()
    all_rows: list[dict] = []
    n = len(query_rows)
    for i, q in enumerate(query_rows, start=1):
        if progress_cb:
            progress_cb(i, n, q["search_query"])
        all_rows.extend(scrape_query(q, config.RESULTS_PER_QUERY, cache))
    _save_cache(cache)
    return all_rows


# --------------------------------------------------------------------------- excel
def save_results_xlsx(rows: list[dict], path: str | None = None) -> str:
    """Write result rows to a formatted .xlsx (bold frozen header, alternating row fill)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    path = path or config.RESULTS_XLSX
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Maps Results"

    header_fill = PatternFill("solid", fgColor="DDEEFF")
    bold = Font(bold=True)
    headers = [c.replace("_", " ").title() for c in RESULT_COLUMNS]
    for col, name in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.font = bold
        cell.fill = header_fill

    alt_fill = PatternFill("solid", fgColor="F3F4F6")
    for r_idx, row in enumerate(rows, start=2):
        for c_idx, key in enumerate(RESULT_COLUMNS, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=row.get(key))
            if r_idx % 2 == 1:  # alternating shade
                cell.fill = alt_fill

    for c_idx, key in enumerate(RESULT_COLUMNS, start=1):
        longest = len(headers[c_idx - 1])
        for row in rows:
            longest = max(longest, len(str(row.get(key, ""))))
        ws.column_dimensions[get_column_letter(c_idx)].width = min(longest + 2, 50)

    ws.freeze_panes = "A2"
    wb.save(path)
    return path
