"""Decide whether a place is relevant to the specialty being surveyed.

Three buckets, deliberately not two:

* **relevant**   - core to the specialty (a Dermatologist, for dermatology)
* **adjacent**   - plausibly offers the service but is not a comparable business unit
                   (a multispecialty hospital competes for the same patient, yet ranking a solo
                   practitioner against it on review volume says nothing useful)
* **irrelevant** - a different trade entirely (a dental clinic, a diagnostic lab, a gym)

Merging 'adjacent' into either side is what makes a market report wrong: fold it into relevant
and hospitals swamp the rankings; fold it into irrelevant and you lose real competitors.

The rules live in packs/base.json (shared) plus each specialty pack (specific). This module
IMPLEMENTS that specification rather than restating it - an earlier version hardcoded its own
lists and silently contradicted the spec file, which is how 83 categories ended up governed by
a document nothing loaded.

Matching is EXACT on the normalized category, never substring: substring matching makes the
category "Clinic" match "Dental clinic" and drags whole trades into the survey.
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

RELEVANT, ADJACENT, IRRELEVANT = "relevant", "adjacent", "irrelevant"

BASE_PATH = Path(__file__).resolve().parent / "packs" / "base.json"

#: one step down / one step up. Name evidence is softer than Google's own category, so it may
#: move the verdict at most one step and can never flip relevant to irrelevant in a single hop.
_DOWN = {RELEVANT: ADJACENT, ADJACENT: IRRELEVANT, IRRELEVANT: IRRELEVANT}
_UP = {IRRELEVANT: ADJACENT, ADJACENT: RELEVANT, RELEVANT: RELEVANT}


class BasePackMissing(Exception):
    """packs/base.json is absent or unreadable - fail loudly rather than fall back to guesswork."""


@lru_cache(maxsize=1)
def load_base(path: str | None = None) -> dict:
    p = Path(path) if path else BASE_PATH
    if not p.exists():
        raise BasePackMissing(f"shared relevance base not found at {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BasePackMissing(f"{p} is not valid JSON: {exc}") from exc


def norm_category(s: str) -> str:
    """Normalize for exact comparison, per base.matching.normalization."""
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFKC", s).replace("’", "'").replace(" ", " ")
    s = s.replace("-", " ").replace("&", " and ").casefold().strip().rstrip(".")
    s = re.sub(r"\s+", " ", s)
    return (s.replace("centre", "center")
             .replace("speciality", "specialty")
             .replace("paediatric", "pediatric")
             .replace("orthopaedic", "orthopedic")
             .replace("gynaecolog", "gynecolog"))


def _token_hit(token: str, text: str) -> bool:
    """base.matching.name_token_rule.

    Tokens of 3 characters or fewer need BOTH word boundaries; longer tokens match as
    left-anchored prefixes so 'dermat' covers dermatology and dermatologist. Without the
    right-hand boundary on short tokens, the ENT pack's 'ent' matches 'Enterprises'.
    """
    tok = norm_category(token)
    if not tok:
        return False
    left = r"(?<![a-z0-9])"
    right = r"(?![a-z0-9])" if len(tok.replace(" ", "")) <= 3 else ""
    return re.search(left + re.escape(tok) + right, text) is not None


def _anchor(cat: str, pack: dict, base: dict) -> tuple:
    """(verdict, source) from the category alone. First match wins, per base.matching.precedence.

    Pack lists are checked BEFORE the shared base because a pack's own lists always override:
    dermatology claims beauty salon and spa, physiotherapy claims gym and massage, and a dental
    clinic is noise for dermatology but the whole market for dentistry.
    """
    if not cat:
        return None, "no_category"
    for key, verdict in (("relevant_categories", RELEVANT),
                         ("irrelevant_categories", IRRELEVANT),
                         ("adjacent_categories", ADJACENT)):
        if cat in {norm_category(c) for c in pack.get(key, []) or []}:
            return verdict, "category"
    if cat in {norm_category(c) for c in base.get("universally_irrelevant", [])}:
        return IRRELEVANT, "base_universally_irrelevant"
    if cat in {norm_category(c) for c in base.get("generic_medical_adjacent", [])}:
        return ADJACENT, "base_generic_medical"
    return None, "category_unlisted"


def classify(category: str, name: str, pack: dict, base: dict | None = None) -> dict:
    """-> {relevance, basis}, implementing base.matching.precedence rules 1-6.

    `basis` records WHY: a verdict reached from a business name is weaker evidence than one
    reached from Google's own category, and a reader deserves to see which it was.
    """
    base = base if base is not None else load_base()
    cat = norm_category(category)
    nm = norm_category(name)

    strong = next((t for t in pack.get("name_strong", []) if _token_hit(t, nm)), None)
    veto = next((t for t in pack.get("name_veto", []) if _token_hit(t, nm)), None)
    # A name carrying both a strong and a veto token is self-contradictory, so it counts as no
    # signal at all and the category anchor stands ("Dr Vijay's Skin and Dental Clinic").
    if strong and veto:
        strong = veto = None

    anchor, source = _anchor(cat, pack, base)

    # Rule 4: a non-medical anchor is HARD - no name movement in either direction, so a
    # restaurant called "Skin Bar" can never become a clinic.
    if source == "base_universally_irrelevant":
        return {"relevance": IRRELEVANT, "basis": "base_universally_irrelevant"}

    if anchor == RELEVANT:                                   # rule 1
        if veto:
            return {"relevance": ADJACENT, "basis": f"category_relevant_veto_capped:{veto}"}
        return {"relevance": RELEVANT, "basis": "category"}

    if anchor == IRRELEVANT:                                 # rule 2
        if strong:
            return {"relevance": ADJACENT, "basis": f"category_irrelevant_strong_capped:{strong}"}
        return {"relevance": IRRELEVANT, "basis": "category"}

    if anchor == ADJACENT:                                   # rules 3 and 5
        b = "category" if source == "category" else source
        if veto:
            return {"relevance": IRRELEVANT, "basis": f"{b}_veto:{veto}"}
        if strong:
            return {"relevance": RELEVANT, "basis": f"{b}_strong:{strong}"}
        return {"relevance": ADJACENT, "basis": b}

    # rule 6: unknown or absent category
    if veto:
        return {"relevance": IRRELEVANT, "basis": f"{source}_veto:{veto}"}
    if strong:
        return {"relevance": RELEVANT, "basis": f"{source}_strong:{strong}"}
    # Never default an unknown category to irrelevant: skipping is irreversible data loss,
    # whereas extracting one place too many only costs time. Logged for curation.
    return {"relevance": ADJACENT, "basis": source}


def extraction_tier(relevance: str) -> str:
    """full = everything incl. every review; minimal = card data only, page never opened.

    Reviews are cheap per unit but the page-open is not: ~40s fixed + 0.18s per review. Skipping
    the open saves the whole 40s, whereas skipping only the reviews would save about two.
    """
    return "full" if relevance in (RELEVANT, ADJACENT) else "minimal"


def specialty_junk_tokens(pack: dict) -> set:
    """Words that must not be used to tell two local businesses apart, for name cleaning.

    Every dermatology clinic contains 'skin'; every dental one contains 'dental'. Those describe
    the trade, not the business.
    """
    out = set()
    for key in ("name_strong", "name_veto", "specialty_tokens"):
        for t in pack.get(key, []) or []:
            out.update(re.split(r"[^a-z0-9]+", str(t).lower()))
    for key in ("specialist_singular", "specialist_plural"):
        if pack.get(key):
            out.update(re.split(r"[^a-z0-9]+", str(pack[key]).lower()))
    for noun in pack.get("facility_nouns", []) or []:
        out.update(re.split(r"[^a-z0-9]+", str(noun).lower()))
    return {t for t in out if len(t) >= 3}
