# -*- coding: utf-8 -*-
"""
modules/serp_card.py  --  parse ONE Google Maps results-feed card without opening the place.

Traced against a real 98-card scrolled feed (probe/listing_page.html, Guntur dermatologists).
Every selector below is verified present in that capture; counts are in the docstring of
parse_feed().
"""
from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------- constants

CARD_SEL = 'div[role="feed"] div[role="article"]'          # primary, semantic
CARD_SEL_FALLBACK = 'div[role="feed"] div.Nv2PK'           # class-based twin

_PID_RE = re.compile(r"!19s(Ch[A-Za-z0-9_\-]+)")
_FID_RE = re.compile(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", re.I)
_MID_RE = re.compile(r"!16s(%2Fg%2F[a-z0-9_]+)", re.I)
_LL_RE = re.compile(r"!3d(-?[\d.]+)!4d(-?[\d.]+)")
_NUM_RE = re.compile(r"[\d][\d,.  ']*")
_MIDDOT = "·"

# Google renders icon-only chips (wheelchair, etc.) as Private-Use-Area glyphs.
_PUA = re.compile(r"[-]")


def _txt(node) -> str:
    """Normalised visible text: NFKC, NBSP/narrow-NBSP -> space, PUA glyphs stripped."""
    if node is None:
        return ""
    s = node.get_text(" ", strip=True)
    s = unicodedata.normalize("NFKC", s)
    s = _PUA.sub("", s)
    s = s.replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def _int(s: str):
    m = _NUM_RE.search(s or "")
    if not m:
        return None
    digits = re.sub(r"[^\d]", "", m.group(0))
    return int(digits) if digits else None


def _float(s: str):
    m = re.search(r"\d+(?:[.,]\d+)?", s or "")
    return float(m.group(0).replace(",", ".")) if m else None


# ---------------------------------------------------------------- sub-parsers

def _info_rows(card):
    """The stacked info lines under the name.

    Real DOM (verified):
        div.UaQhfb
          div.NrDZNb   -> name
          div.W4Efsd   -> RATING row   (contains div.AJB7ye)
          div.W4Efsd   -> WRAPPER      (contains the nested rows below)
              div.W4Efsd -> "<category> · <address>"
              div.W4Efsd -> "<Open|Closed> · <...>"      (may be absent: 10/98)

    Discriminated by CONTENT, not by position, so a missing rating row cannot shift things.
    """
    ua = card.select_one("div.UaQhfb")
    if ua is None:
        return None, []
    direct = [d for d in ua.find_all("div", recursive=False)
              if "W4Efsd" in (d.get("class") or [])]
    rating_row = next((d for d in direct if d.select_one("div.AJB7ye")), None)
    wrapper = next((d for d in direct
                    if d is not rating_row
                    and d.find("div", class_="W4Efsd", recursive=False)), None)
    if wrapper is None:                      # single-line layout: rows live directly on UaQhfb
        rows = [d for d in direct if d is not rating_row]
    else:
        rows = [d for d in wrapper.find_all("div", recursive=False)
                if "W4Efsd" in (d.get("class") or [])]
    return rating_row, rows


def _split_category_address(row):
    """Category + address out of the '<category> · <address>' line.

    DOM-first: the line is a list of sibling <span>s. span[0] is the category. Every later
    span opens with its own <span aria-hidden="true">·</span> separator span, so the middot
    is NEVER inside the address text -- there is no delimiter to split on and commas /
    periods / colons inside the address (73/98 contain them) are harmless.

    Icon chips (e.g. "Wheelchair accessible entrance") occupy their own middot-prefixed span
    and are skipped via the google-symbols class / PUA-glyph test. When several text spans
    survive, the LAST is the address -- Google puts the address last.

    Text fallback (used only if the span layout is gone) splits on the middot and applies the
    same rule: first segment = category, last non-icon segment = address.
    """
    if row is None:
        return "", ""
    spans = row.find_all("span", recursive=False)

    if spans:
        category = _txt(spans[0])
        address = ""
        for sp in spans[1:]:
            inner = sp.find_all("span", recursive=False)
            # drop the aria-hidden middot separator span
            body = [s for s in inner if s.get("aria-hidden") != "true"] or [sp]
            if any("google-symbols" in (s.get("class") or []) for s in body):
                continue                       # icon chip, not text
            val = _txt(body[-1])
            if val:
                address = val                  # keep overwriting -> last text span wins
        if category:
            return category, address

    # ---- text fallback ----
    parts = [p.strip() for p in _txt(row).split(_MIDDOT)]
    parts = [p for p in parts if p]
    if not parts:
        return "", ""
    return parts[0], (parts[-1] if len(parts) > 1 else "")


_CLOSED_WORDS = ("temporarily closed", "permanently closed", "closed")


def _parse_status(row):
    t = _txt(row)
    if not t:
        return {"status_text": "", "open_now": None, "temporarily_closed": False,
                "permanently_closed": False}
    low = t.casefold()
    temp = low.startswith("temporarily closed")
    perm = low.startswith("permanently closed")
    if temp or perm:
        open_now = False
    elif low.startswith("open"):
        open_now = True
    elif low.startswith("closes soon"):
        open_now = True
    elif low.startswith("closed"):
        open_now = False
    else:
        open_now = None
    return {"status_text": t, "open_now": open_now,
            "temporarily_closed": temp, "permanently_closed": perm}


def _is_ad(card) -> bool:
    """Ad / Sponsored marker.

    NOT VERIFIABLE from the Guntur capture -- it contains ZERO ads, so every branch below is
    defensive rather than measured. Deliberately avoids guessing an obfuscated class name and
    keys off things Google cannot change without changing the user-visible page:
    an explicit aria-label, a standalone 'Ad'/'Sponsored' word, or an ad-click href.
    Note 'Book online' links (a.A1zNzb -> justdial/remedo/healthplix, 6/98 cards) are booking
    partners, NOT ads, and must not trip this.
    """
    if card.select_one('[aria-label="Ad"], [aria-label="Sponsored"], [aria-label="Ads"]'):
        return True
    for sp in card.find_all(["span", "div"]):
        if sp.find(True) is None:                       # leaf node only
            t = _txt(sp).casefold().strip(" ·")
            if t in ("ad", "ads", "sponsored"):
                return True
    for a in card.select("a[href]"):
        h = a["href"]
        if "/aclk?" in h or "googleadservices.com" in h:
            return True
    return False


# ---------------------------------------------------------------- public API

def parse_card(card) -> dict:
    """One div[role=article] -> flat dict. Never raises; missing fields come back None/''."""
    a = card.select_one("a.hfpxzc[href]") or card.select_one('a[href*="/maps/place/"]')
    href = (a.get("href") if a else "") or ""

    name = (a.get("aria-label") if a else "") or ""
    if not name:
        name = _txt(card.select_one("div.qBF1Pd"))

    rating_row, rows = _info_rows(card)
    cat_row = rows[0] if rows else None
    status_row = rows[1] if len(rows) > 1 else None
    category, address = _split_category_address(cat_row)

    rating = _float(_txt(card.select_one("span.MW4etd")))
    reviews = _int(_txt(card.select_one("span.UY7F9")))
    if reviews is None:
        zk = card.select_one("span.ZkP5Je[aria-label]")
        if zk:
            m = re.search(r"([\d,.  ']+)\s*reviews?", zk["aria-label"], re.I)
            if m:
                reviews = _int(m.group(1))
    no_reviews = bool(rating_row) and "no reviews" in _txt(rating_row).casefold()

    m = _PID_RE.search(href)
    fid = _FID_RE.search(href)
    mid = _MID_RE.search(href)
    ll = _LL_RE.search(href)

    return {
        "place_id": m.group(1) if m else "",
        "feature_id": fid.group(1) if fid else "",
        "kg_mid": mid.group(1).replace("%2F", "/") if mid else "",
        "lat": float(ll.group(1)) if ll else None,
        "lng": float(ll.group(2)) if ll else None,
        "href": href,
        "name": name,
        "card_category": category,
        "card_address": address,
        "rating": rating,
        "reviews_total": reviews,
        "no_reviews": no_reviews,
        "review_snippet": _txt(card.select_one("div.ah5Ghc")),
        "is_ad": _is_ad(card),
        **_parse_status(status_row),
    }


def parse_feed(soup) -> list[dict]:
    """All cards of a scrolled results feed, in rank order.

    Measured on probe/listing_page.html (98 cards, 97 distinct place_ids -- one duplicate):
        card container          98/98
        href + place_id         98/98
        name                    98/98
        card_category           98/98   <-- the field the relevance gate needs
        card_address            96/98   (2 places genuinely show no address line)
        rating                  94/98   (4 show "No reviews")
        reviews_total           74/98   (absent on the 20 first-batch cards -- see notes)
        status_text             88/98
        is_ad                    0/98   (no ads in the capture; detector unverified)
    """
    cards = soup.select(CARD_SEL) or soup.select(CARD_SEL_FALLBACK)
    return [parse_card(c) for c in cards]
