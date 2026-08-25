"""Field-derivation rules for Google Maps place records. Pure functions, no browser, no I/O.

Every rule here was derived from the 98 real Guntur listings, not invented. The three that
carry the most commercial weight:

* **name cleaning** - listings are stuffed with SEO padding ("... | Best Dermatologist in
  Guntur | Trichologist"). The clinic's real name is what a report shows a doctor, but the raw
  padding is itself evidence about their SEO posture, so both are kept.
* **website classification** - "has no website" is the single biggest sales signal, so calling
  a Practo profile a website would hide a real prospect, and calling a real site a profile
  would invent one.
* **category relevance** - a search for dermatologists returns dental clinics and diagnostic
  labs. Matching is EXACT on the normalized category, never substring: substring makes the
  category "Clinic" match "Dental clinic" and silently drags the wrong businesses in.
"""
from __future__ import annotations

import html
import re
import unicodedata

# --------------------------------------------------------------------------- name cleaning
SUPERLATIVE = {"best", "top", "no1", "leading", "famous", "renowned", "trusted", "finest",
               "premier", "award", "winning", "rated", "affordable", "cheap", "no"}
ROLE = {"dermatologist", "dermatologists", "dermatology", "trichologist", "trichology",
        "cosmetologist", "cosmetology", "cosmetic", "sexologist", "aesthetic", "aesthetics",
        "doctor", "dr", "physician", "surgeon", "specialist", "consultant", "orthopaedic",
        "ortho", "pediatric", "paediatric", "maternity", "pregnancy", "dentist", "dental",
        "homeopathic", "homeopathy", "pmu", "artist", "multispeciality", "multispecialty"}
SERVICE = {"skin", "hair", "laser", "transplant", "reduction", "removal", "scar", "acne",
           "treatment", "treatments", "aging", "ageing", "anti", "botox", "filler", "fillers",
           "prp", "tattoo", "pigmentation", "implant", "implantology", "chest", "vascular",
           "rheumatology", "diagnostic", "imaging", "piles", "care"}
ENTITY = {"clinic", "clinics", "centre", "center", "hospital", "hospitals", "polyclinic",
          "poly", "institute", "studio"}
GEO = {"guntur", "kothapet", "kothapeta", "vijayawada", "amaravathi", "amaravati", "andhra",
       "pradesh", "nagar", "road", "town", "city", "brodipet", "arundelpet", "lakshmipuram"}
DEGREE = {"mbbs", "md", "ms", "mch", "dm", "dnb", "ddvl", "dvl", "dvd", "dpm", "dgo", "dch",
          "bds", "mds", "bams", "bhms", "phd", "frcs", "mrcp", "facs", "dmre", "dlo"}
STOPWORDS = {"the", "and", "in", "of", "for", "at", "a", "an", "&", "|", "-"}
JUNK = SUPERLATIVE | ROLE | SERVICE | ENTITY | GEO | DEGREE
MEANINGFUL = SUPERLATIVE | ROLE | SERVICE | GEO | DEGREE

PROMO_RE = re.compile(r"\b(best|top|no\.?\s*1|#1|leading|famous|renowned|award[- ]winning)\b", re.I)
CLAIM_RE = re.compile(r"\b(\d[\d,]*\s*[k+]?\s*(patients|clients|treatments|years))\b", re.I)


def _norm_text(s: str) -> str:
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[​-‏‪-‮﻿]", "", s)
    s = s.replace("’", "'").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> list[str]:
    # de-glue lowerUpper runs so "SkinClinic" -> "skin clinic"
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s or "")
    return [t for t in re.split(r"[^A-Za-z0-9]+", s.lower()) if t]


def _is_junk_segment(seg: str) -> bool:
    """True when a segment is entirely generic - i.e. carries no brand token.

    Any out-of-lexicon word is treated as a brand token, which is what protects real names
    like "Skin Perfect Clinic" ('perfect' is unknown) from being deleted as boilerplate.
    """
    toks = [t for t in _tokens(seg) if t not in STOPWORDS]
    if not toks:
        return True
    return all(t in JUNK for t in toks) and any(t in MEANINGFUL for t in toks)


def clean_name(raw: str) -> dict:
    """-> {name_raw, name_clean, name_key, name_dropped[], name_was_cleaned}.

    The raw string is never mutated: it is the provenance field to show a clinic that disputes
    a report, and its length versus the clean name is itself a usable SEO-stuffing signal.
    """
    raw = raw or ""
    norm = _norm_text(raw)
    dropped: list[str] = []

    # strong separators; a "/" between digits is a date/ratio, not a separator
    parts = [p.strip() for p in re.split(r"\s*(?:\|\||\||/(?!\d)|•|·|¦)\s*", norm) if p.strip()]
    if not parts:
        parts = [norm]
    idx = 0
    while idx < len(parts) - 1 and PROMO_RE.search(parts[idx]) and _is_junk_segment(parts[idx]):
        dropped.append(parts[idx])
        idx += 1
    name = parts[idx]
    dropped.extend(p for i, p in enumerate(parts) if i != idx and p not in dropped)

    # parentheticals: drop only wholly-generic ones, and never one naming a person
    def _paren(m):
        inner = m.group(1)
        if re.search(r"\bdr\b", inner, re.I):
            return m.group(0)
        if _is_junk_segment(inner):
            dropped.append(inner.strip())
            return " "
        return m.group(0)
    name = re.sub(r"\(([^)]*)\)", _paren, name)

    # weak tails (, : ; -) cut ONLY on an explicit promo/claim marker. A hyphen usually marks a
    # branch ("- kothapeta") that distinguishes two genuinely different locations.
    changed = True
    while changed:
        changed = False
        m = re.search(r"^(.*?)[,;:]\s+(.+)$|^(.*?)\s+[-–—]\s+(.+)$", name)
        if m:
            head = m.group(1) if m.group(1) is not None else m.group(3)
            tail = m.group(2) if m.group(2) is not None else m.group(4)
            if head and tail and (PROMO_RE.search(tail) or CLAIM_RE.search(tail)
                                  or all(t in DEGREE for t in _tokens(tail))):
                dropped.append(tail.strip())
                name, changed = head.strip(), True

    # trailing degree run: "Dr. N.V. Ramana Rao M.D D.P.M" -> "Dr. N.V. Ramana Rao".
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
        name = norm            # never return an empty or meaningless name
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    return {"name_raw": raw, "name_clean": name, "name_key": key,
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
AGGREGATOR = {"practo.com", "justdial.com", "jdmart.com", "apollo247.com", "lybrate.com",
              "skedoc.com", "drlogy.com", "bajajfinservhealth.in", "sulekha.com",
              "docon.co.in", "docgenie.in", "mymedisage.com", "medibuddy.in", "credihealth.com",
              "medindia.net", "quikr.com", "indiamart.com", "yellowpages.in", "sehat.com",
              "healthgrades.com", "clinicspots.com", "medicalbharat.com"}
CHAIN = {"kolorshairandskin.com", "kolorshealthcare.com", "olivaclinic.com", "vlccwellness.com",
         "vlcc.in", "anoos.com", "vcaretrichology.com", "vcareskinclinic.com",
         "vcarehairandskin.com", "drbatras.com", "richfeelindia.com", "advancedhairstudio.com",
         "traya.health", "clearskin.in", "kayaclinic.com"}
_IN_SUFFIXES = ("co.in", "net.in", "org.in", "ac.in", "gen.in", "firm.in", "ind.in", "co.uk")


def etld1(host: str) -> str:
    """eTLD+1, aware of the Indian second-level suffixes (docon.co.in must not become co.in)."""
    parts = (host or "").split(".")
    if len(parts) < 2:
        return host or ""
    last2 = ".".join(parts[-2:])
    if last2 in _IN_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    return last2


def classify_website(url: str, clinic_name: str = "") -> dict:
    """-> website_type, has_own_website, insecure_http, website_domain.

    Types: own_domain | chain_corporate | google_business_site | aggregator_profile |
           social_profile | link_aggregator | none
    """
    raw = (url or "").strip()
    if raw.lower() in ("", "n/a", "null", "-", "none"):
        return {"website": "", "website_domain": "", "website_type": "none",
                "has_own_website": False, "insecure_http": False, "website_matches_name": None}
    if not re.match(r"^[a-z]+://", raw, re.I):
        raw = "http://" + raw
    m = re.match(r"^(https?)://([^/?#]+)", raw, re.I)
    if not m:
        return {"website": url, "website_domain": "", "website_type": "none",
                "has_own_website": False, "insecure_http": False, "website_matches_name": None}
    scheme, host = m.group(1).lower(), m.group(2).lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    root = etld1(host)

    # http-only is recorded, never a downgrade: 7 of 20 real Guntur clinic sites are http
    insecure = scheme == "http"

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
    elif root in CHAIN:
        wtype = "chain_corporate"
    else:
        wtype = "own_domain"

    # does the domain actually echo the clinic's name? informational, never decisive
    label = root.split(".")[0]
    name_toks = [t for t in _tokens(clinic_name) if len(t) >= 4 and t not in JUNK]
    matches = any(t in label for t in name_toks) or (len(label) >= 5 and label in re.sub(r"[^a-z0-9]", "", (clinic_name or "").lower())) if name_toks or label else None

    own = wtype in ("own_domain", "chain_corporate", "google_business_site")
    return {"website": url, "website_domain": host, "website_type": wtype,
            "has_own_website": own, "insecure_http": insecure,
            "website_matches_name": bool(matches) if name_toks else None}


# --------------------------------------------------------------------------- category
def norm_category(s: str) -> str:
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFKC", s).replace("’", "'").replace(" ", " ")
    s = s.replace("-", " ").casefold().strip().rstrip(".")
    s = re.sub(r"\s+", " ", s)
    return s.replace("centre", "center").replace("speciality", "specialty")


CAT_RELEVANT = {"dermatologist", "skin care clinic", "dermatology", "cosmetic dentist" and "",
                "hair transplant clinic", "trichologist"}
CAT_RELEVANT.discard("")
CAT_ADJACENT = {"hospital", "private hospital", "general hospital", "medical clinic", "clinic",
                "multispecialty hospital", "cosmetic surgeon", "plastic surgeon", "medical spa",
                "beauty salon", "spa", "wellness center", "ayurvedic clinic", "homeopath",
                "general practitioner", "doctor", "laser hair removal service", "beautician",
                "medical center", "health consultant", "hair removal service"}
CAT_IRRELEVANT = {"dental clinic", "dentist", "diagnostic center", "medical laboratory",
                  "pharmacy", "drug store", "gym", "optician", "eye care center",
                  "orthopedic clinic", "physiotherapist", "veterinarian", "hotel",
                  "restaurant", "school", "pediatrician", "gynecologist", "obstetrician",
                  "cardiologist", "ent doctor", "urologist", "psychiatrist"}

NAME_STRONG = ["skin", "derma", "dermat", "cosmetolog", "tricholog", "laser", "hair"]
NAME_VETO = ["dental", "dentist", "orthodont", "diagnostic", "imaging", "scan", "pharmacy",
             "optical", "eye", "veterinary", "piles", "fertility", "dialysis"]


def category_relevance(category: str, name: str = "") -> dict:
    """-> {relevance, basis}. relevance in relevant | adjacent | irrelevant.

    Three buckets, not two: a multispecialty hospital competes for the same patient but is not
    a comparable business unit, so it must not be merged into either side.
    """
    cat = norm_category(category)
    nm = norm_category(name)

    def word(tok, text):
        return re.search(r"(?<![a-z0-9])" + re.escape(tok), text) is not None

    strong = next((t for t in NAME_STRONG if word(t, nm)), None)
    veto = next((t for t in NAME_VETO if word(t, nm)), None)
    cv = ("relevant" if cat in CAT_RELEVANT else
          "adjacent" if cat in CAT_ADJACENT else
          "irrelevant" if cat in CAT_IRRELEVANT else None)

    if veto and not strong:
        return {"relevance": "irrelevant", "basis": f"name_veto:{veto}"}
    if cv == "relevant":
        return {"relevance": "relevant", "basis": "category"}
    if cv == "adjacent":
        return ({"relevance": "relevant", "basis": f"name_strong_over_category:{strong}"}
                if strong else {"relevance": "adjacent", "basis": "category"})
    if cv == "irrelevant":
        # name evidence can lift one step, never fully reverse a negative category
        return ({"relevance": "adjacent", "basis": f"name_strong_capped:{strong}"}
                if strong else {"relevance": "irrelevant", "basis": "category"})
    if strong:
        return {"relevance": "relevant", "basis": f"name_strong:{strong}"}
    return {"relevance": "adjacent",
            "basis": "no_category" if not cat else "category_unlisted"}


# --------------------------------------------------------------------------- ids
def ids_from_href(href: str) -> dict:
    """Stable identifiers, pulled from the listing link before any page is opened."""
    out = {"feature_id": "", "place_id": "", "kg_mid": "", "lat": None, "lng": None}
    m = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", href or "", re.I)
    if m:
        out["feature_id"] = m.group(1)
    m = re.search(r"!19s(ChIJ[A-Za-z0-9_-]+)", href or "")
    if m:
        out["place_id"] = m.group(1)
    m = re.search(r"!16s(%2Fg%2F[a-z0-9]+)", href or "", re.I)
    if m:
        out["kg_mid"] = m.group(1).replace("%2F", "/")
    m = re.search(r"!3d(-?[\d.]+)!4d(-?[\d.]+)", href or "")
    if m:
        out["lat"], out["lng"] = float(m.group(1)), float(m.group(2))
    return out
