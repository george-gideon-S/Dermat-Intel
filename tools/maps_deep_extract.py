"""Deep Google Maps extraction: every listing, every field, every review.

Written after the v1 collector was found to capture 34 clinics where the live listing holds 97
(it stopped after 12 feed scrolls AND capped 15 results per query). Here the feed is scrolled
until Google itself says "You've reached the end of the list", and nothing is capped.

Design notes that matter operationally:

* **Reviews are sorted NEWEST FIRST before reading.** Google's default order is "most relevant",
  which is scrambled, so you cannot tell where new reviews end and old ones begin. Sorting by
  date is what makes the quarterly re-run cheap: it reads from the top and stops at the first
  review id it already has.
* **Nothing may hang.** Every page op has a timeout and every loop has a wall-clock budget, so a
  slow clinic is abandoned with partial data rather than stalling the whole run (v1 froze on
  clinic 16 for 10+ minutes).
* **A stripped page is a transport failure, not a clinic with no reviews.** Google intermittently
  serves a page whose name renders but whose rating and reviews do not; that is retried, never
  recorded as a genuine zero.

Selectors verified against the live DOM 2026-08-19:
  listing link  div[role="feed"] a[href*="/maps/place/"]   name h1.DUwDvf
  category      button[jsaction*="category"]               address [data-item-id="address"]
  phone         [data-item-id^="phone:tel:"]               plus code [data-item-id="oloc"]
  website       [data-item-id="authority"]                 hours [jsaction*="openhours"] -> table.eK4R0e
  histogram     aria-label "5 stars, 606 reviews"          topics [role="radio"] "... mentioned in N reviews"
  review block  [data-review-id]                           author .d4r55   date .rsqaWe
  customer text .wiI7pd OUTSIDE .CDe7pd                    owner reply inside .CDe7pd
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import json
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from modules.place_fields import (category_relevance, classify_website, clean_name,
                                  ids_from_href)

# Wall-clock budgets. Without these a single slow clinic stalls the entire run.
NAV_TIMEOUT_MS = 45000
OP_TIMEOUT_MS = 15000
REVIEW_BUDGET_S = 420      # max time spent loading one clinic's reviews
PLACE_BUDGET_S = 600       # hard ceiling for one clinic, everything included


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}".encode("ascii", "replace").decode(), flush=True)


# ---------------------------------------------------------------- small helpers
def dismiss_consent(page):
    for label in ("Reject all", "Accept all", "I agree"):
        try:
            page.get_by_role("button", name=label).first.click(timeout=2500)
            return
        except Exception:
            pass


def safe_text(page, sel, timeout=2500):
    try:
        return page.locator(sel).first.inner_text(timeout=timeout).strip()
    except Exception:
        return ""


def scroll_feed_to_end(page, max_rounds=250, budget_s=300):
    """Scroll until Google declares the end of the list."""
    t0, last, stable = time.time(), 0, 0
    for i in range(max_rounds):
        if time.time() - t0 > budget_s:
            log("    feed scroll budget reached")
            break
        try:
            page.evaluate("""() => { const f=document.querySelector('div[role="feed"]');
                                     if(f) f.scrollTo(0,f.scrollHeight); }""")
        except Exception:
            pass
        time.sleep(1.1)
        try:
            n = page.locator('div[role="feed"] a[href*="/maps/place/"]').count()
            ended = "reached the end of the list" in page.content()
        except Exception:
            n, ended = last, False
        stable = stable + 1 if n == last else 0
        last = n
        if i % 5 == 0:
            log(f"    feed scroll {i}: {n} places (end={ended})")
        if ended and stable >= 2:
            log(f"    END OF LIST: {n} places after {i} scrolls")
            return n
        if stable >= 15:
            return n
    return last


# ---------------------------------------------------------------- reviews
def unique_review_count(page) -> int:
    """Distinct review ids, not elements: one card repeats its id on nested buttons (~7x)."""
    try:
        return page.evaluate("""() => new Set([...document.querySelectorAll('[data-review-id]')]
            .map(e => e.getAttribute('data-review-id'))).size""")
    except Exception:
        return 0


def open_reviews(page) -> bool:
    """Google varies this layout between loads, so try each mechanism rather than assume one."""
    for attempt in (
        lambda: page.get_by_role("tab", name=re.compile("Reviews", re.I)).first.click(timeout=4000),
        lambda: page.locator('button[aria-label*="review" i]').first.click(timeout=3000),
        lambda: page.locator('button[jsaction*="moreReviews"]').first.click(timeout=3000),
    ):
        try:
            attempt()
            time.sleep(2.5)
            if unique_review_count(page):
                return True
        except Exception:
            continue
    for _ in range(6):
        try:
            page.evaluate("""() => { const ds=[...document.querySelectorAll('div')]
                .filter(e=>typeof e.className==='string'&&e.className.includes('m6QErb')
                        &&e.scrollHeight>e.clientHeight+40);
                ds.forEach(d=>d.scrollTo(0,d.scrollHeight)); }""")
        except Exception:
            pass
        time.sleep(1.1)
        if unique_review_count(page):
            return True
    return False


def sort_reviews_newest(page) -> bool:
    """Switch the review order to Newest.

    This is what makes the next quarterly run cheap: in date order the scraper can read from the
    top and stop at the first review it already holds. In Google's default "most relevant" order
    new and old are interleaved, so there is no safe stopping point and the whole list must be
    re-read every time.
    """
    for opener in (
        lambda: page.get_by_role("button", name=re.compile(r"^Sort", re.I)).first.click(timeout=4000),
        lambda: page.locator('button[aria-label*="Sort" i]').first.click(timeout=3000),
        lambda: page.locator('button:has-text("Sort")').first.click(timeout=3000),
    ):
        try:
            opener()
            time.sleep(1.5)
            for picker in (
                lambda: page.get_by_role("menuitemradio", name=re.compile("Newest", re.I)).first.click(timeout=3000),
                lambda: page.locator('[role="menuitemradio"]:has-text("Newest")').first.click(timeout=3000),
                lambda: page.locator('div[role="menu"] >> text=Newest').first.click(timeout=3000),
            ):
                try:
                    picker()
                    time.sleep(2.5)
                    return True
                except Exception:
                    continue
        except Exception:
            continue
    return False


def load_all_reviews(page, expected=None, budget_s=REVIEW_BUDGET_S, known_ids=None):
    """Scroll until every review is loaded, then expand each one fully.

    Stops early only for a real reason: the expected total is reached, a review we already have
    is seen (incremental mode), or the wall-clock budget expires. Otherwise it keeps waiting -
    Google delivers in bursts and pauses mid-list, so an impatient loop silently truncates.
    """
    t0, last, stable = time.time(), 0, 0
    hit_known = False
    while time.time() - t0 < budget_s:
        try:
            page.evaluate("""() => { const ds=[...document.querySelectorAll('div')]
                .filter(e=>typeof e.className==='string'&&e.className.includes('m6QErb')
                        &&e.scrollHeight>e.clientHeight+40);
                ds.forEach(d=>d.scrollTo(0,d.scrollHeight)); }""")
        except Exception:
            pass
        time.sleep(1.0)
        n = unique_review_count(page)
        if known_ids:
            try:
                ids = page.evaluate("""() => [...new Set([...document.querySelectorAll('[data-review-id]')]
                    .map(e => e.getAttribute('data-review-id')))]""")
                if any(i in known_ids for i in ids):
                    hit_known = True
                    break
            except Exception:
                pass
        if expected and n >= expected:
            break
        stable = stable + 1 if n == last else 0
        last = n
        if stable >= 20:      # ~20s of no growth: the list really has ended
            break
    # Expand every truncated review. A transparent overlay blocks normal clicks, so click in JS.
    for _ in range(6):
        try:
            clicked = page.evaluate("""() => { let n=0;
                document.querySelectorAll('button').forEach(b => {
                  const t=(b.innerText||'').trim().toLowerCase();
                  if(t==='more'||t==='see more'||t==='read more'){ b.click(); n++; } });
                return n; }""")
            time.sleep(1.2)
            if not clicked:
                break
        except Exception:
            break
    return last, hit_known


def parse_reviews(html: str) -> list:
    """Split each review into the customer's words and (the presence of) the owner's reply.

    The owner reply sits inside .CDe7pd; the customer's text is the .wiI7pd outside it. Only the
    fact of a reply is kept, not its text - an owner's marketing copy is not patient sentiment.
    """
    soup = BeautifulSoup(html, "lxml")
    best: dict = {}
    for el in soup.select("[data-review-id]"):
        rid = el.get("data-review-id")
        if not rid:
            continue
        if rid not in best or len(el.get_text(" ", strip=True)) > len(best[rid].get_text(" ", strip=True)):
            best[rid] = el
    out = []
    for rid, r in best.items():
        if not r.select_one(".d4r55") and not r.select_one(".wiI7pd"):
            continue
        has_reply = r.select_one(".CDe7pd") is not None
        resp = r.select_one(".CDe7pd")
        if resp:
            resp.extract()
        author = r.select_one(".d4r55")
        date = r.select_one(".rsqaWe") or r.select_one(".DZSIDd")
        text_el = r.select_one(".wiI7pd") or r.select_one(".MyEned")
        text = text_el.get_text(" ", strip=True) if text_el else ""
        stars = None
        for a in r.select("[aria-label]"):
            m = re.match(r"^(\d)\s+stars?$", (a.get("aria-label") or "").strip())
            if m:
                stars = int(m.group(1))
                break
        out.append({
            "review_id": rid,
            "author": author.get_text(" ", strip=True) if author else "",
            "rating": stars,
            "relative_date": date.get_text(" ", strip=True) if date else "",
            "text": text,
            # flags a review that still looks cut off, so truncation cannot pass silently
            "maybe_truncated": bool(text) and text.rstrip().endswith(("…", "...", "More")),
            "has_owner_reply": has_reply,
        })
    return out


# ---------------------------------------------------------------- about tab
def extract_about(page) -> dict:
    """Read the About tab: service options, accessibility, amenities, payments."""
    about = {}
    for opener in (
        lambda: page.get_by_role("tab", name=re.compile("About", re.I)).first.click(timeout=4000),
        lambda: page.locator('button[aria-label*="About" i]').first.click(timeout=3000),
    ):
        try:
            opener()
            time.sleep(2.0)
            break
        except Exception:
            continue
    try:
        soup = BeautifulSoup(page.content(), "lxml")
        current = None
        for el in soup.select("h2, h3, li"):
            txt = el.get_text(" ", strip=True)
            if not txt:
                continue
            if el.name in ("h2", "h3"):
                if len(txt) < 60:
                    current = txt
                    about.setdefault(current, [])
            elif current:
                clean = re.sub(r"^(Has|Serves|Offers)\s+", "", txt).strip()
                if clean and clean not in about[current] and len(clean) < 80:
                    about[current].append(clean)
    except Exception:
        pass
    return {k: v for k, v in about.items() if v} or None


# ---------------------------------------------------------------- one place
def extract_place(page, href, listing_category="", known_ids=None) -> dict:
    t_start = time.time()
    page.goto(href, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    time.sleep(4.0)
    dismiss_consent(page)
    time.sleep(0.8)

    def item(item_id):
        try:
            e = page.locator(f'[data-item-id="{item_id}"]').first
            return (e.get_attribute("aria-label") or e.inner_text() or "").strip()
        except Exception:
            return ""

    rec = {"place_url": href, "captured_at": datetime.now().isoformat(timespec="seconds")}
    rec.update(ids_from_href(href))
    rec.update(clean_name(safe_text(page, "h1.DUwDvf")))

    # BOTH categories: the results list and the place page can disagree, and hiding that
    # behind a single value would make the mismatch invisible.
    rec["category"] = safe_text(page, 'button[jsaction*="category"]')
    rec["listing_category"] = listing_category
    rec["category_mismatch"] = bool(listing_category and rec["category"]
                                    and listing_category.strip().lower() != rec["category"].strip().lower())
    rec.update(category_relevance(rec["category"] or listing_category, rec["name_clean"]))

    rec["address"] = re.sub(r"^Address:\s*", "", item("address")).strip()
    rec["plus_code"] = re.sub(r"^Plus code:\s*", "", item("oloc")).strip()
    try:
        ph = page.locator('[data-item-id^="phone:tel:"]').first
        rec["phone"] = re.sub(r"^Phone:\s*", "", (ph.get_attribute("aria-label") or "")).strip()
    except Exception:
        rec["phone"] = ""
    try:
        w = page.locator('[data-item-id="authority"]').first
        rec.update(classify_website((w.get_attribute("href") or "").strip(), rec["name_clean"]))
    except Exception:
        rec.update(classify_website("", rec["name_clean"]))

    # one JS pass over every aria-label: rating, total, star histogram, topics
    rating, total, hist = None, None, {}
    try:
        labels = page.evaluate("""() => [...document.querySelectorAll('[aria-label]')]
            .map(e => e.getAttribute('aria-label')).filter(Boolean)""")
        for al in labels:
            al = al.strip()
            if rating is None:
                m = re.match(r"^([0-9.]+)\s+stars?$", al)
                if m:
                    rating = float(m.group(1))
            if total is None:
                m = re.match(r"^([\d,]+)\s+reviews?$", al)
                if m:
                    total = int(m.group(1).replace(",", ""))
            m = re.match(r"^(\d) stars?, ([\d,]+) reviews?$", al)
            if m:
                hist[m.group(1)] = int(m.group(2).replace(",", ""))
    except Exception:
        pass
    rec["rating"], rec["reviews_total"] = rating, total
    rec["rating_histogram"] = hist or None
    if hist and total:
        s = sum(hist.values())
        rec["histogram_sum"], rec["histogram_reconciles"] = s, (s == total)

    topics = {}
    try:
        for a in page.locator('[role="radio"]').all()[:40]:
            al = (a.get_attribute("aria-label") or "").strip()
            m = re.match(r"^(.*?),?\s*mentioned in\s+([\d,]+)\s+reviews?$", al, re.I)
            if m:
                topics[m.group(1).strip()] = int(m.group(2).replace(",", ""))
    except Exception:
        pass
    rec["topics"] = topics or None

    gaps = []
    try:
        for e in page.locator("span.DkEaL").all()[:30]:
            t = (e.inner_text() or "").strip()
            if t.lower().startswith("add "):
                gaps.append(t)
    except Exception:
        pass
    rec["google_profile_gaps"] = gaps or None

    try:
        rec["has_photos"] = page.locator(
            'button[aria-label^="Photo of"], button[aria-label^="Photos of"]').count() > 0
    except Exception:
        rec["has_photos"] = False

    # hours sit behind a dropdown arrow until clicked
    for sel in ('[jsaction*="openhours"]', 'button[data-item-id*="oh"]', 'img[aria-label="Hours"]'):
        try:
            page.locator(sel).first.click(timeout=2500)
            time.sleep(1.2)
            break
        except Exception:
            continue
    hours = {}
    try:
        soup = BeautifulSoup(page.content(), "lxml")
        for tr in soup.select("table.eK4R0e tr"):
            day, val = tr.select_one("td.ylH6lf"), tr.select_one("td.mxowUb")
            if day and val:
                raw_h = val.get("aria-label") or val.get_text(" ", strip=True)
                hours[day.get_text(" ", strip=True)] = re.sub(
                    r"\s+", " ", raw_h.replace(" ", " ").replace(" ", " ")).strip()
    except Exception:
        pass
    rec["hours"] = hours or None

    rec["about"] = extract_about(page)

    # ---- reviews, newest first, all of them ----
    rec["reviews"], rec["reviews_error"] = [], ""
    rec["sorted_newest"] = False
    if time.time() - t_start < PLACE_BUDGET_S and open_reviews(page):
        rec["sorted_newest"] = sort_reviews_newest(page)
        loaded, hit_known = load_all_reviews(page, expected=total, known_ids=known_ids)
        rec["reviews"] = parse_reviews(page.content())
        rec["stopped_at_known_review"] = hit_known
        log(f"    reviews loaded={loaded} parsed={len(rec['reviews'])} newest_first={rec['sorted_newest']}")
    else:
        rec["reviews_error"] = "reviews pane did not open"
        log("    reviews: PANE DID NOT OPEN (flagged)")

    rec["reviews_captured"] = len(rec["reviews"])
    rec["owner_replies"] = sum(1 for r in rec["reviews"] if r.get("has_owner_reply"))
    rec["truncated_reviews"] = sum(1 for r in rec["reviews"] if r.get("maybe_truncated"))
    if rec["reviews_total"]:
        rec["reviews_coverage"] = round(rec["reviews_captured"] / rec["reviews_total"], 3)
    # relative dates only ("3 months ago") - the capture time is the anchor that dates them
    rec["date_anchor"] = rec["captured_at"]
    rec["extract_seconds"] = round(time.time() - t_start, 1)

    missing = [f for f in ("name_clean", "category", "address", "plus_code", "phone", "website",
                           "rating", "reviews_total") if not rec.get(f)]
    for f, ok in (("hours", rec.get("hours")), ("photos", rec.get("has_photos")),
                  ("about", rec.get("about")), ("reviews", rec.get("reviews"))):
        if not ok:
            missing.append(f)
    rec["missing_fields"] = missing
    return rec


# ---------------------------------------------------------------- live status
def write_status(out: _Path, **fields):
    """Status file the live page polls, so the operator can see progress and elapsed time."""
    p = out / "status.json"
    cur = {}
    if p.exists():
        try:
            cur = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            cur = {}
    cur.update(fields)
    p.write_text(json.dumps(cur, indent=2), encoding="utf-8")


def write_summary(out: _Path):
    """Compact per-clinic summaries for the live page (full detail stays in places/)."""
    rows = []
    for f in sorted((out / "places").glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append({k: d.get(k) for k in (
            "listing_position", "name_clean", "name_raw", "category", "listing_category",
            "category_mismatch", "relevance", "basis", "address", "plus_code", "phone",
            "website", "website_type", "has_own_website", "rating", "reviews_total",
            "reviews_captured", "reviews_coverage", "owner_replies", "truncated_reviews",
            "has_photos", "hours", "topics", "about", "rating_histogram",
            "google_profile_gaps", "place_id", "feature_id", "missing_fields",
            "sorted_newest", "extract_seconds", "error", "listing_name")})
    rows.sort(key=lambda r: r.get("listing_position") or 9999)
    (out / "data.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="dermatologists in Guntur")
    ap.add_argument("--out", default="runs/maps_deep/guntur_dermatologists")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pace", type=float, default=3.0)
    ap.add_argument("--incremental", action="store_true",
                    help="stop each clinic's review scroll at the first already-known review")
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()

    out = _Path(args.out)
    (out / "places").mkdir(parents=True, exist_ok=True)
    started = time.time()
    write_status(out, started_at=started, finished=False, done=0, total=0,
                 current="starting", query=args.query, errors=0)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        ctx = browser.new_context(locale="en-IN", viewport={"width": 1400, "height": 950},
                                  user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                                              "Chrome/151.0 Safari/537.36"))
        ctx.set_default_timeout(OP_TIMEOUT_MS)
        ctx.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        page = ctx.new_page()

        links_file = out / "listing_links.json"
        if links_file.exists():
            links = json.loads(links_file.read_text(encoding="utf-8"))
            log(f"reusing {len(links)} cached listing links")
        else:
            url = f"https://www.google.com/maps/search/{args.query.replace(' ', '+')}/?hl=en"
            log(f"listing: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            time.sleep(4)
            dismiss_consent(page)
            time.sleep(2)
            scroll_feed_to_end(page)
            seen, links = set(), []
            for a in page.locator('div[role="feed"] a[href*="/maps/place/"]').all():
                href = a.get_attribute("href") or ""
                if href and href not in seen:
                    seen.add(href)
                    links.append({"href": href, "aria_label": a.get_attribute("aria-label") or ""})
            links_file.write_text(json.dumps(links, indent=2, ensure_ascii=False), encoding="utf-8")
            log(f"captured {len(links)} unique places")

        if args.limit:
            links = links[:args.limit]
        write_status(out, total=len(links))

        errors = 0
        for i, l in enumerate(links, start=1):
            ids = ids_from_href(l["href"])
            key = (ids["place_id"] or ids["feature_id"].replace(":", "_")
                   or re.sub(r"\W+", "_", l["aria_label"])[:60] or f"place_{i}")
            dest = out / "places" / f"{key}.json"
            write_status(out, current=l["aria_label"][:70], done=i - 1, errors=errors,
                         elapsed=round(time.time() - started))
            if dest.exists():
                continue
            log(f"[{i}/{len(links)}] {l['aria_label'][:52]}")

            known = None
            if args.incremental and dest.exists():
                try:
                    prev = json.loads(dest.read_text(encoding="utf-8"))
                    known = {r["review_id"] for r in prev.get("reviews", []) if r.get("review_id")}
                except Exception:
                    known = None
            try:
                rec = extract_place(page, l["href"], known_ids=known)
                # a stripped page is a transport failure, not a clinic with no reviews
                if rec.get("reviews_total") is None and not rec.get("reviews"):
                    log("    degraded page - retrying once")
                    time.sleep(15)
                    rec = extract_place(page, l["href"], known_ids=known)
                rec.update({"listing_position": i, "source_query": args.query,
                            "listing_name": l["aria_label"]})
                dest.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
                flag = f" | MISSING: {','.join(rec['missing_fields'])}" if rec["missing_fields"] else ""
                log(f"    {rec['name_clean'][:32]} | {rec['category'][:16]} | {rec['relevance']}"
                    f" | {rec['reviews_captured']}/{rec['reviews_total']} rev"
                    f" | {rec['extract_seconds']}s{flag}")
            except Exception as exc:
                errors += 1
                log(f"    ERROR {type(exc).__name__}: {str(exc)[:120]}")
                dest.write_text(json.dumps({"place_url": l["href"], "error": str(exc)[:300],
                                            "listing_name": l["aria_label"],
                                            "listing_position": i}, indent=2), encoding="utf-8")
                # a broken page can poison the tab; start a clean one
                try:
                    page.close()
                    page = ctx.new_page()
                except Exception:
                    pass
            n = write_summary(out)
            write_status(out, done=i, saved=n, errors=errors, elapsed=round(time.time() - started))
            time.sleep(args.pace if i % 10 else args.pace * 4)

        browser.close()
    write_summary(out)
    write_status(out, finished=True, elapsed=round(time.time() - started), current="done")
    log(f"done in {round((time.time()-started)/60,1)} min -> {out}")


if __name__ == "__main__":
    raise SystemExit(main())
