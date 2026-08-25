"""Field-derivation rules for Google Maps place records. Pure functions: no browser, no I/O.

Specialty-agnostic and market-agnostic. Everything that varies by specialty (which categories
count as relevant) or by market (city name, language) lives in packs, not here.

Derived from 98 real Guntur listings and re-checked against a completed 97-place run.
"""
from __future__ import annotations

import html
import re
import unicodedata

# --------------------------------------------------------------------------- shared lexicons
SUPERLATIVE = {"best", "top", "no1", "leading", "famous", "renowned", "trusted", "finest",
               "premier", "award", "winning", "rated", "affordable", "cheap", "no"}
ROLE = {"doctor", "dr", "physician", "surgeon", "specialist", "consultant", "clinic",
        "hospital", "multispeciality", "multispecialty", "care", "centre", "center"}
ENTITY = {"clinic", "clinics", "centre", "center", "hospital", "hospitals", "polyclinic",
          "poly", "institute", "studio", "care"}
DEGREE = {"mbbs", "md", "ms", "mch", "dm", "dnb", "ddvl", "dvl", "dvd", "dpm", "dgo", "dch",
          "bds", "mds", "bams", "bhms", "phd", "frcs", "mrcp", "facs", "dmre", "dlo", "do"}
STOPWORDS = {"the", "and", "in", "of", "for", "at", "a", "an", "&", "|", "-"}

PROMO_RE = re.compile(r"\b(best|top|no\.?\s*1|#1|leading|famous|renowned|award[- ]winning)\b", re.I)
CLAIM_RE = re.compile(r"\b(\d[\d,]*\s*[k+]?\s*(patients|clients|treatments|years))\b", re.I)


def _norm_text(s: str) -> str:
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[​-‏‪-‮﻿]", "", s)
    s = s.replace("’", "'").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def tokens(s: str) -> list[str]:
    """Words, with glued CamelCase split apart so 'SkinClinic' -> ['skin', 'clinic']."""
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s or "")
    return [t for t in re.split(r"[^A-Za-z0-9]+", s.lower()) if t]


# --------------------------------------------------------------------------- name cleaning
def clean_name(raw: str, junk_extra: set | None = None) -> dict:
    """Strip SEO padding from a listing name, keeping the real business name.

    Listings are stuffed like "Chandana Skin Clinic | Dermatologist | Laser Scar Treatment".
    The segment before the first | or / is reliably the actual name. A hyphen is NOT a separator:
    it usually marks a branch ("- kothapeta") that distinguishes two genuinely different
    locations, so cutting there would merge distinct businesses.

    Any word not in the junk lexicon is treated as a brand token, which is what protects a real
    name like "Skin Perfect Clinic" ('perfect' is unknown) from being deleted as boilerplate.

    `junk_extra` receives the active specialty's own vocabulary (skin, hair, dental, cardiac...)
    so the same routine works for every specialty.

    Returns name_raw / name_clean / name_key / name_dropped / name_was_cleaned. The raw string is
    never mutated: it is the provenance field, and how much padding a clinic uses is itself a
    signal about their SEO posture.
    """
    junk = SUPERLATIVE | ROLE | ENTITY | DEGREE | (junk_extra or set())
    meaningful = SUPERLATIVE | DEGREE | (junk_extra or set()) | (ROLE - ENTITY)

    def is_junk_segment(seg: str) -> bool:
        toks = [t for t in tokens(seg) if t not in STOPWORDS]
        if not toks:
            return True
        return all(t in junk for t in toks) and any(t in meaningful for t in toks)

    raw = raw or ""
    norm = _norm_text(raw)
    dropped: list[str] = []

    parts = [p.strip() for p in re.split(r"\s*(?:\|\||\||/(?!\d)|•|·|¦)\s*", norm) if p.strip()]
    if not parts:
        parts = [norm]
    idx = 0
    while idx < len(parts) - 1 and PROMO_RE.search(parts[idx]) and is_junk_segment(parts[idx]):
        dropped.append(parts[idx])
        idx += 1
    name = parts[idx]
    dropped.extend(p for i, p in enumerate(parts) if i != idx and p not in dropped)

    def _paren(m):
        inner = m.group(1)
        if re.search(r"\bdr\b", inner, re.I):
            return m.group(0)          # never delete a person's name
        if is_junk_segment(inner):
            dropped.append(inner.strip())
            return " "
        return m.group(0)
    name = re.sub(r"\(([^)]*)\)", _paren, name)

    changed = True
    while changed:
        changed = False
        m = re.search(r"^(.*?)[,;:]\s+(.+)$|^(.*?)\s+[-–—]\s+(.+)$", name)
        if m:
            head = m.group(1) if m.group(1) is not None else m.group(3)
            tail = m.group(2) if m.group(2) is not None else m.group(4)
            if head and tail and (PROMO_RE.search(tail) or CLAIM_RE.search(tail)
                                  or all(t in DEGREE for t in tokens(tail))):
                dropped.append(tail.strip())
                name, changed = head.strip(), True

    # trailing degrees: "Dr. N.V. Ramana Rao M.D D.P.M" -> "Dr. N.V. Ramana Rao".
    # The dotted-or-3-char guard keeps initials ("Dr Seetharam K A") intact.
    toks = name.split()
    while len(toks) > 2:
        bare = re.sub(r"[^A-Za-z]", "", toks[-1]).lower()
        if bare in DEGREE and ("." in toks[-1] or len(bare) >= 3):
            dropped.append(toks.pop())
        else:
            break
    name = " ".join(toks)

    name = re.sub(r"\s{2,}", " ", name).strip(" .,;:|/-&")
    if name.count("(") != name.count(")"):
        name = re.sub(r"[()]", "", name).strip()
    if len(re.sub(r"[^A-Za-z0-9]", "", name)) < 2:
        name = norm
    return {"name_raw": raw, "name_clean": name,
            "name_key": re.sub(r"[^a-z0-9]", "", name.lower()),
            "name_dropped": [d for d in dropped if d],
            "name_was_cleaned": name != norm}


# --------------------------------------------------------------------------- website
MULTI_LABEL_PLATFORMS = ("sites.google.com", "business.site")
SELF_REF = {"google.com", "google.co.in", "goo.gl", "maps.app.goo.gl"}
BUILDER = {"business.site", "getmy.clinic", "wixsite.com", "blogspot.com", "weebly.com",
           "webnode.com", "godaddysites.com", "square.site", "wordpress.com", "carrd.co",
           "netlify.app", "vercel.app", "github.io"}
LINK_HUB = {"linktr.ee", "bio.link", "beacons.ai", "taplink.cc", "campsite.bio", "lnk.bio",
            "linkin.bio", "msha.ke", "solo.to", "allmylinks.com", "linkpop.com"}
SOCIAL = {"instagram.com", "facebook.com", "fb.com", "fb.me", "youtube.com", "youtu.be",
          "twitter.com", "x.com", "linkedin.com", "pinterest.com", "threads.net",
          "tiktok.com", "wa.me", "whatsapp.com", "t.me"}
#: healthcare directories/marketplaces - a profile here is NOT the clinic's own site
AGGREGATOR = {"practo.com", "justdial.com", "jdmart.com", "apollo247.com", "lybrate.com",
              "skedoc.com", "drlogy.com", "bajajfinservhealth.in", "sulekha.com",
              "docon.co.in", "docgenie.in", "mymedisage.com", "medibuddy.in", "credihealth.com",
              "medindia.net", "quikr.com", "indiamart.com", "yellowpages.in", "sehat.com",
              "healthgrades.com", "clinicspots.com", "medicalbharat.com", "zocdoc.com",
              "vaidam.com", "medifee.com", "doctoriduniya.com", "hexahealth.com"}
_MULTI_SUFFIXES = ("co.in", "net.in", "org.in", "ac.in", "gen.in", "firm.in", "ind.in",
                   "co.uk", "org.uk", "ac.uk", "com.au", "co.nz", "com.br", "co.za", "com.sg")


def domain_of(url: str) -> str:
    m = re.match(r"https?://([^/?#]+)", (url or "").strip(), re.I)
    host = (m.group(1) if m else "").lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def etld1(host: str) -> str:
    """eTLD+1, aware of multi-label suffixes so docon.co.in does not collapse to co.in."""
    parts = (host or "").split(".")
    if len(parts) < 2:
        return host or ""
    if ".".join(parts[-2:]) in _MULTI_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def classify_website(url: str, business_name: str = "", chain_domains: set | None = None) -> dict:
    """own_domain | chain_corporate | google_business_site | aggregator_profile |
    social_profile | link_aggregator | none

    "Has no website" is usually the single biggest sales signal in a market report, so calling a
    Practo profile a website would hide a real prospect, and calling a real site a profile would
    invent one.
    """
    raw = (url or "").strip()
    none_result = {"website": url or "", "website_domain": "", "website_type": "none",
                   "has_own_website": False, "insecure_http": False,
                   "website_matches_name": None}
    if raw.lower() in ("", "n/a", "null", "-", "none"):
        return none_result

    # Only http(s) is a website. A scheme-with-no-slashes (mailto:, tel:, javascript:) used to be
    # prefixed with "http://" and then read as a real domain - "mailto:doc@x.com" became an
    # own_domain, inventing a website for a clinic that has none.
    m_scheme = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):", raw)
    if m_scheme:
        if m_scheme.group(1).lower() not in ("http", "https"):
            return {**none_result, "website_type": "unsupported_scheme"}
    else:
        raw = "http://" + raw

    scheme = raw.split("://", 1)[0].lower()
    host = domain_of(raw)
    # A trailing dot is a valid FQDN form ("practo.com.") and used to evade every domain list,
    # turning a Practo profile into the clinic's own site.
    host = host.rstrip(".")
    if not host or "." not in host or host.startswith("."):
        return {**none_result, "website": url, "website_domain": host,
                "website_type": "unparseable"}
    root = etld1(host)

    if any(host == p or host.endswith("." + p) for p in MULTI_LABEL_PLATFORMS):
        wtype = "google_business_site"
    elif root in SELF_REF:
        wtype = "none"
    elif root in BUILDER:
        wtype = "google_business_site"
    elif root in LINK_HUB:
        wtype = "link_aggregator"
    elif root in SOCIAL:
        wtype = "social_profile"
    elif root in AGGREGATOR:
        wtype = "aggregator_profile"
    elif chain_domains and root in chain_domains:
        wtype = "chain_corporate"
    else:
        wtype = "own_domain"

    label = root.split(".")[0] if root else ""
    name_toks = [t for t in tokens(business_name)
                 if len(t) >= 4 and t not in (SUPERLATIVE | ROLE | ENTITY)]
    matches = None
    if name_toks and label:
        flat = re.sub(r"[^a-z0-9]", "", (business_name or "").lower())
        matches = any(t in label for t in name_toks) or (len(label) >= 5 and label in flat)

    return {"website": url, "website_domain": host, "website_type": wtype,
            # http-only is recorded but never a downgrade: many real clinic sites are http
            "insecure_http": scheme == "http",
            "has_own_website": wtype in ("own_domain", "chain_corporate", "google_business_site"),
            "website_matches_name": matches}


# --------------------------------------------------------------------------- identifiers
# Single source of truth for the identifiers. cards.py imports these rather than keeping its own
# copies: two slightly different regexes for the same field silently truncated kg_mid on 18 of 98
# real cards, because whichever module ran last overwrote the other's value.
PID_RE = re.compile(r"!19s(Ch[A-Za-z0-9_-]+)")            # not all place ids begin ChIJ
FID_RE = re.compile(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", re.I)
MID_RE = re.compile(r"!16s(%2F[a-z]%2F[A-Za-z0-9_]+)", re.I)   # /g/, /m/, ... not just /g/
LL_RE = re.compile(r"!3d(-?[\d.]+)!4d(-?[\d.]+)")


def ids_from_href(href: str) -> dict:
    """Stable identifiers, read from the listing link before any page is opened.

    place_id is the join key across quarterly snapshots: it survives a clinic renaming itself,
    which names and URLs do not.
    """
    out = {"feature_id": "", "place_id": "", "kg_mid": "", "lat": None, "lng": None}
    href = href or ""
    m = FID_RE.search(href)
    if m:
        out["feature_id"] = m.group(1)
    m = PID_RE.search(href)
    if m:
        out["place_id"] = m.group(1)
    m = MID_RE.search(href)
    if m:
        out["kg_mid"] = m.group(1).replace("%2F", "/")
    m = LL_RE.search(href)
    if m:
        out["lat"], out["lng"] = float(m.group(1)), float(m.group(2))
    return out


def name_slug(name: str) -> str:
    """A filesystem-safe identity fragment that survives non-Latin scripts.

    A Latin-only slug returns '' for a wholly Telugu or Arabic name, so every such clinic
    collapsed onto the same key and overwrote the others. Falling back to a hash of the
    normalized name keeps them distinct.
    """
    slug = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    if slug:
        return slug[:72]
    import hashlib
    norm = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", name or "").strip().casefold())
    if not norm:
        return ""
    return "h" + hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def registry_key(href: str, name: str = "") -> str:
    """The identity a place is tracked by across queries and across quarters.

    Returns "" when there is nothing to key on at all, so the caller can quarantine the record
    instead of silently filing every anonymous card under one shared key.
    """
    ids = ids_from_href(href)
    if ids["place_id"]:
        return ids["place_id"]
    if ids["feature_id"]:
        return ids["feature_id"]
    slug = name_slug(name)
    return ("name:" + slug) if slug else ""
