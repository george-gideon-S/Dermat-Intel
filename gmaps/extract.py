"""Google Maps extraction for one (city, specialty): one query, tiered by relevance.

The shape of the run:

  1. Search "<best specialists> in <city>", scroll the feed until Google says the list has ended.
  2. Read every result CARD - name, category, rating, review count, address, place id - without
     opening anything.
  3. Decide relevance from the card. Measured on 98 real cards: the card verdict agrees with the
     page verdict 99% of the time, with ZERO false negatives, so gating here never loses a place
     worth extracting.
  4. relevant / adjacent -> open the place and extract everything, including every review.
     irrelevant          -> keep the card's name + address only. Never open it.

Step 4 is where the time goes. Measured cost per opened place: ~40s fixed + 0.18s per review.
The fixed page-open dominates, so not opening an irrelevant place saves the whole 40s, whereas
merely skipping its reviews would have saved a couple of seconds.

Selectors verified against live DOM captures kept in archive/gmaps_v1_2026-08-20/probe_evidence/.
"""
from __future__ import annotations

import re
import time
from datetime import datetime

from bs4 import BeautifulSoup

from gmaps import taxonomy
from gmaps.cards import parse_feed
from gmaps.fields import classify_website, clean_name, ids_from_href, registry_key

NAV_TIMEOUT_MS = 45000
OP_TIMEOUT_MS = 15000
REVIEW_BUDGET_S = 420
PLACE_BUDGET_S = 600


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}".encode("ascii", "replace").decode(), flush=True)


# ---------------------------------------------------------------- feed
def dismiss_consent(page):
    for label in ("Reject all", "Accept all", "I agree"):
        try:
            page.get_by_role("button", name=label).first.click(timeout=2500)
            return
        except Exception:
            pass


def scroll_feed_to_end(page, budget_s=420, max_rounds=300):
    """Scroll until the feed stops growing.

    Google's end-of-list sentinel is an English sentence, so it is used only as a fast path.
    The authoritative stop is structural - the card count stopping growing - which behaves the
    same in any interface language.
    """
    t0, last, stable = time.time(), 0, 0
    for i in range(max_rounds):
        if time.time() - t0 > budget_s:
            log("    feed budget reached")
            return last, "budget_exhausted"
        try:
            page.evaluate("""() => { const f=document.querySelector('div[role="feed"]');
                                     if(f) f.scrollTo(0,f.scrollHeight); }""")
        except Exception:
            pass
        time.sleep(1.1)
        try:
            n = page.locator('div[role="feed"] div[role="article"]').count()
            sentinel = "reached the end of the list" in page.content()
        except Exception:
            n, sentinel = last, False
        stable = stable + 1 if n == last else 0
        last = n
        if i % 5 == 0:
            log(f"    feed scroll {i}: {n} cards")
        if sentinel and stable >= 2:
            log(f"    end of list ({n} cards, sentinel)")
            return n, "end_of_list_sentinel"
        if stable >= 15:
            log(f"    end of list ({n} cards, no growth)")
            return n, "no_growth"
    return last, "max_rounds"


def read_feed(page) -> list[dict]:
    """Parse every card in the feed. No place is opened here."""
    soup = BeautifulSoup(page.content(), "lxml")
    cards = parse_feed(soup)
    out, seen = [], {}
    for i, c in enumerate(cards, start=1):
        href = c.get("href") or ""
        key = registry_key(href, c.get("name", ""))
        # The card parser namespaces its fields (card_category / card_address) to keep them
        # distinct from the place page's own values. Alias them once here so everything
        # downstream reads one set of names.
        c.setdefault("category", c.get("card_category") or "")
        c.setdefault("address", c.get("card_address") or "")
        c.setdefault("review_count", c.get("reviews_total"))
        c["rank"] = i
        c["key"] = key
        c.update({k: v for k, v in ids_from_href(href).items() if v is not None})
        if key in seen:
            # Google genuinely lists the same place twice in one feed; keep the better rank and
            # retain the duplicate for provenance rather than silently discarding it.
            c["dup_of_rank"] = seen[key]
            out.append(c)
            continue
        seen[key] = i
        out.append(c)
    return out


# ---------------------------------------------------------------- reviews
def unique_review_count(page) -> int:
    """Distinct review ids: one card repeats its id on nested buttons, inflating a raw count ~7x."""
    try:
        return page.evaluate("""() => new Set([...document.querySelectorAll('[data-review-id]')]
            .map(e => e.getAttribute('data-review-id'))).size""")
    except Exception:
        return 0


def open_reviews(page) -> bool:
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
    """Order reviews by date.

    This is what makes the next quarterly run cheap: in date order the scraper reads from the top
    and stops at the first review it already holds. In Google's default "most relevant" order new
    and old are interleaved, so there is no safe stopping point.
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
    """Scroll until every review is loaded, then expand each one.

    Stops early only for a real reason: the expected total is reached, an already-known review is
    seen (incremental mode), or the budget expires. Google delivers reviews in bursts with pauses
    between, so an impatient loop quits during a pause and silently reports a partial list as
    complete - that bug capped an earlier run at 75%.
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
        if stable >= 20:
            break
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
    """Separate the customer's words from the owner's reply.

    The owner reply sits inside .CDe7pd; the customer's text is the .wiI7pd outside it. Only the
    fact of a reply is kept - an owner's marketing copy is not patient sentiment.
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
        out.append({"review_id": rid,
                    "author": author.get_text(" ", strip=True) if author else "",
                    "rating": stars,
                    "relative_date": date.get_text(" ", strip=True) if date else "",
                    "text": text,
                    "has_owner_reply": has_reply})
    return out


# ---------------------------------------------------------------- about
def extract_about(page) -> dict | None:
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
    about, current = {}, None
    try:
        soup = BeautifulSoup(page.content(), "lxml")
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


# ---------------------------------------------------------------- one place, full tier
def extract_place(page, card: dict, ctx, known_ids=None) -> dict:
    """Open a place and take everything: contact block, hours, About, and every review."""
    t0 = time.time()
    href = card["href"]
    page.goto(href, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    time.sleep(4.0)
    dismiss_consent(page)
    time.sleep(0.8)

    def txt(sel):
        try:
            return page.locator(sel).first.inner_text(timeout=2500).strip()
        except Exception:
            return ""

    def item(item_id):
        try:
            e = page.locator(f'[data-item-id="{item_id}"]').first
            return (e.get_attribute("aria-label") or e.inner_text() or "").strip()
        except Exception:
            return ""

    junk = taxonomy.specialty_junk_tokens(ctx.spec)
    rec = {"key": card["key"], "tier": "full", "complete": False,
           "place_url": href, "captured_at": datetime.now().isoformat(timespec="seconds")}
    # Carried from the results card. Booking, service options and closed-status exist ONLY on the
    # card - open the place and they are gone - so they must be copied through here or lost.
    # `status_text` / `open_now` are deliberately NOT carried: "Open - closes 7 pm" describes the
    # moment of the scrape, so it is stale an hour later and meaningless in a quarterly snapshot.
    rec.update({k: card.get(k) for k in
                ("rank", "place_id", "feature_id", "kg_mid", "lat", "lng", "dup_of_rank",
                 "has_online_booking", "booking_url", "booking_vendor", "service_options",
                 "permanently_closed", "temporarily_closed", "is_ad", "review_snippet")})
    rec.update(clean_name(txt("h1.DUwDvf") or card.get("name", ""), junk_extra=junk))

    rec["category"] = txt('button[jsaction*="category"]')
    rec["card_category"] = card.get("category") or ""
    # The card category is query-biased (Google shows the one that matched the search) while the
    # page shows the primary. Measured 12.2% disagreement, so both are kept rather than picking.
    rec["category_mismatch"] = bool(rec["card_category"] and rec["category"]
                                    and taxonomy.norm_category(rec["card_category"])
                                    != taxonomy.norm_category(rec["category"]))
    rec.update(taxonomy.classify(rec["category"] or rec["card_category"], rec["name_clean"], ctx.spec))

    rec["address"] = re.sub(r"^Address:\s*", "", item("address")).strip() or card.get("address", "")
    rec["plus_code"] = re.sub(r"^Plus code:\s*", "", item("oloc")).strip()
    try:
        ph = page.locator('[data-item-id^="phone:tel:"]').first
        rec["phone"] = re.sub(r"^Phone:\s*", "", (ph.get_attribute("aria-label") or "")).strip()
    except Exception:
        rec["phone"] = ""
    try:
        w = page.locator('[data-item-id="authority"]').first
        rec.update(classify_website((w.get_attribute("href") or "").strip(),
                                    rec["name_clean"], ctx.chain_domains))
    except Exception:
        rec.update(classify_website("", rec["name_clean"], ctx.chain_domains))

    rating, total, hist, topics = None, None, {}, {}
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
            m = re.match(r"^(.*?),?\s*mentioned in\s+([\d,]+)\s+reviews?$", al, re.I)
            if m:
                topics[m.group(1).strip()] = int(m.group(2).replace(",", ""))
    except Exception:
        pass
    rec["rating"] = rating if rating is not None else card.get("rating")
    rec["reviews_total"] = total if total is not None else card.get("review_count")
    # the histogram separates a 4.9 built on 638 reviews from a 4.9 built on 9
    rec["rating_histogram"] = hist or None
    if hist and rec["reviews_total"]:
        s = sum(hist.values())
        rec["histogram_sum"], rec["histogram_reconciles"] = s, s == rec["reviews_total"]
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
                    r"\s+", " ", raw_h.replace(" ", " ").replace(" ", " ")).strip()
    except Exception:
        pass
    rec["hours"] = hours or None
    rec["about"] = extract_about(page)

    rec["reviews"], rec["reviews_error"], rec["sorted_newest"] = [], "", False
    if time.time() - t0 < PLACE_BUDGET_S and open_reviews(page):
        rec["sorted_newest"] = sort_reviews_newest(page)
        loaded, hit_known = load_all_reviews(page, expected=rec["reviews_total"],
                                             known_ids=known_ids)
        rec["reviews"] = parse_reviews(page.content())
        rec["stopped_at_known_review"] = hit_known
        log(f"    reviews {len(rec['reviews'])}/{rec['reviews_total']} newest={rec['sorted_newest']}")
    else:
        rec["reviews_error"] = "reviews pane did not open"
        log("    reviews: pane did not open (flagged)")

    rec["reviews_captured"] = len(rec["reviews"])
    rec["owner_replies"] = sum(1 for r in rec["reviews"] if r.get("has_owner_reply"))
    # Always present, so a consumer never hits a KeyError, and clamped so a mid-scroll total
    # change cannot report 333% coverage. None means "no denominator", not "zero coverage".
    if rec.get("reviews_total"):
        rec["reviews_coverage"] = round(
            min(1.0, rec["reviews_captured"] / rec["reviews_total"]), 3)
    elif rec.get("reviews_total") == 0:
        rec["reviews_coverage"] = 1.0        # zero of zero really is complete
    else:
        rec["reviews_coverage"] = None
    # reviews carry only relative dates; the capture time is what makes them resolvable later
    rec["date_anchor"] = rec["captured_at"]
    rec["extract_seconds"] = round(time.time() - t0, 1)

    missing = [f for f in ("name_clean", "category", "address", "plus_code", "phone", "website",
                           "rating", "reviews_total") if not rec.get(f)]
    for f, ok in (("hours", rec.get("hours")), ("photos", rec.get("has_photos")),
                  ("about", rec.get("about")), ("reviews", rec.get("reviews"))):
        if not ok:
            missing.append(f)
    rec["missing_fields"] = missing

    # Did the page actually render? A stripped or blocked page yields a record that is
    # byte-identical to a genuinely sparse clinic - and because completeness gates the retry,
    # marking it complete meant a failed read was never retried, on this run or any later one.
    # A real profile shows at least one of: category, address, phone, or a review count.
    rec["page_rendered"] = bool(rec.get("name_clean")) and any(
        (rec.get("category"), rec.get("address"), rec.get("phone"),
         rec.get("reviews_total") is not None))
    rec["error"] = "" if rec["page_rendered"] else "page did not render any profile field"
    rec["complete"] = rec["page_rendered"]
    return rec


def card_only_record(card: dict, ctx, verdict: dict) -> dict:
    """The minimal record for a place judged irrelevant: name and address, nothing more.

    Deliberately sparse. This business is outside the specialty being surveyed, so the only
    reasons to keep it at all are (a) to show it was seen and consciously excluded, and (b) to
    let a reader audit that call. Its rating, review count, booking links and opening status are
    facts about a business nobody is reporting on, so collecting them adds noise and invites
    someone downstream to analyse a market we never surveyed.

    The identifiers stay because they are the audit trail: without place_id there is no way to
    confirm next quarter that the same business was excluded for the same reason.
    """
    junk = taxonomy.specialty_junk_tokens(ctx.spec)
    rec = {"key": card["key"], "tier": "minimal", "complete": True,
           "place_url": card.get("href", ""),
           "captured_at": datetime.now().isoformat(timespec="seconds")}
    # Identity and position only - the audit trail. No commercial fields.
    rec.update({k: card.get(k) for k in
                ("rank", "place_id", "feature_id", "kg_mid", "lat", "lng", "dup_of_rank")})
    rec.update(clean_name(card.get("name", ""), junk_extra=junk))
    rec["category"] = ""
    rec["card_category"] = card.get("category") or ""     # the evidence for the exclusion
    rec["category_mismatch"] = False
    rec.update(verdict)
    rec["address"] = card.get("address") or ""
    rec["address_is_partial"] = True      # the card shows a shortened address, not the full one
    rec["reviews"], rec["reviews_captured"], rec["owner_replies"] = [], 0, 0
    rec["reviews_coverage"] = None
    rec["extract_seconds"] = 0.0
    # Deliberately not opened, so there is no page to have rendered. Kept explicit so this is
    # never confused with a full-tier record whose page failed to load.
    rec["page_rendered"] = False
    rec["error"] = ""
    rec["skipped_reason"] = "not relevant to this specialty - not opened"
    # Two different kinds of absence, kept apart on purpose:
    #   not_collected -> we chose not to gather it, so we never looked
    #   missing_fields -> the source had a slot for it and it was genuinely empty
    # Collapsing them would let "we didn't look" read as "the clinic doesn't have one".
    rec["not_collected"] = ["phone", "website", "plus_code", "hours", "about", "reviews",
                            "topics", "rating_histogram", "rating", "reviews_total",
                            "booking", "service_options", "closed_status"]
    rec["missing_fields"] = [f for f in ("name_clean", "address") if not rec.get(f)]
    return rec
