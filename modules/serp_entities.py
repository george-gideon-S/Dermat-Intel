"""Who the SERP is talking about: build a clinic roster, then link results to it.

A SERP-only run has no Maps scrape to lean on, but it does not need one — the local pack, the
"More places" list and the AI overview between them name most of the market. This module turns
those mentions into one roster, then attributes the rest of the page to it: a sponsored ad, an
Instagram profile, a YouTube channel.

Three rules shape the matching, each earned:

* **Names arrive filthy.** Google carries a clinic's whole SEO title —
  "SKIN LANE CLINIC-Kothapet /Dr.AKSHAY JAIN /Best Dermatologist in Guntur /Trichologist /..."
  — so the head of the name is taken and the keyword tail dropped, or every clinic in the city
  would look like a different business on every query.
* **Generic words never match.** "skin", "clinic", "guntur" appear in nearly every name here.
  Matching leans on the DISTINCTIVE tokens only, which is why "Leelavathi" binds two spellings
  of the same clinic while two unrelated "skin clinic"s stay apart.
* **A miss is a miss.** Anything unmatched is returned as unlinked rather than guessed at.
  A wrongly attributed ad moves a clinic's paid-visibility signal, which is worse than a gap.
"""
from __future__ import annotations

import re
from typing import Optional

from modules import packs, serp_parser

#: Words that appear in nearly every clinic name in this domain, so they identify nobody.
GENERIC_NAME_TOKENS = {
    "the", "and", "for", "in", "of", "at", "best", "top", "famous", "leading", "clinic",
    "clinics", "hospital", "hospitals", "centre", "center", "care", "skin", "hair", "laser",
    "derma", "dermatology", "dermatologist", "dermatologists", "cosmetic", "cosmetology",
    "cosmetologist", "trichologist", "aesthetic", "aesthetics", "doctor", "doctors", "dr",
    "specialist", "treatment", "treatments", "advanced", "super", "multi", "speciality",
    "specialty", "medical", "health", "healthcare", "institute", "solutions", "studio",
}

#: Where a Google-carried name stops being a name and starts being keyword stuffing.
_TAIL_SPLIT = re.compile(r"\s*[|/]\s*|\s+[-–—]\s+")
_SOCIAL_HOSTS = {"instagram": "Instagram", "youtube": "YouTube", "facebook": "Facebook"}


def clean_name(raw: str) -> str:
    """The clinic's actual name, with the SEO tail removed."""
    text = re.sub(r"\s+", " ", str(raw or "")).strip()
    if not text:
        return ""
    head = _TAIL_SPLIT.split(text)[0].strip(" .,:;-–—·")
    # A head that collapsed to almost nothing means the separator was part of the name.
    return (head if len(head) >= 4 else text)[:120]


def canonical(name: str) -> str:
    """Spelling-insensitive key. Centre/Center and &/and are the same business."""
    text = clean_name(name).lower()
    text = text.replace("&", " and ").replace("centre", "center")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def distinctive(name: str, extra_stop: Optional[set] = None) -> set:
    """The identifying words of a name — everything generic removed."""
    stop = GENERIC_NAME_TOKENS | (extra_stop or set())
    return {t for t in canonical(name).split() if len(t) >= 3 and t not in stop}


def same_clinic(a: str, b: str, extra_stop: Optional[set] = None) -> bool:
    """Do two spellings denote one business?"""
    if not a or not b:
        return False
    if canonical(a) == canonical(b):
        return True
    ta, tb = distinctive(a, extra_stop), distinctive(b, extra_stop)
    if not ta or not tb:
        return False
    overlap = ta & tb
    smaller = min(len(ta), len(tb))
    if smaller == 1:
        # One distinctive word each: demand it be the same, reasonably long word.
        return bool(overlap) and max(len(t) for t in overlap) >= 4
    return len(overlap) >= 2 or (len(overlap) == smaller and smaller >= 1)


# ------------------------------------------------------------------ roster
def build_roster(queries: list[dict], ctx=None) -> list[dict]:
    """Every clinic the SERP names, merged across spellings, with where it was seen.

    `subject_class` comes from the specialty pack's own rules, so "ignore multispeciality
    hospitals" is a decision the caller can apply — and can also un-apply, since the hospitals
    are still counted rather than silently dropped.
    """
    ctx = packs.resolve(ctx)
    stop = {t.lower() for t in (ctx.geo.get("city_tokens") or [])}
    entries: list[dict] = []

    def record(name: str, source: str, rank, position) -> None:
        name = clean_name(name)
        if len(name) < 4:
            return
        for e in entries:
            if same_clinic(e["name"], name, stop):
                e["variants"].add(name)
                e["sources"].setdefault(source, 0)
                e["sources"][source] += 1
                e["queries"].add(rank)
                if position and position < (e["best_position"] or 10 ** 6):
                    e["best_position"] = position
                # Keep the shortest spelling as the display name — it is the one without
                # the keyword tail.
                if len(name) < len(e["name"]):
                    e["name"] = name
                return
        entries.append({"name": name, "variants": {name}, "sources": {source: 1},
                        "queries": {rank}, "best_position": position})

    for q in queries:
        rank = q.get("rank")
        for b in q.get("blocks") or []:
            if serp_parser.is_local_pack(b.get("block_type")):
                record(b.get("title"), "map_results", rank, b.get("position"))
        for p in q.get("more_places") or []:
            record(p.get("name"), "map_more", rank, p.get("position"))
        ai = q.get("ai") or {}
        for c in (ai.get("recommended_clinics") or []):
            record(c.get("name"), "ai_overview", rank, c.get("position"))

    out = []
    for e in entries:
        cls, basis = ctx.classify_subject_with_basis(e["name"], "")
        out.append({
            "name": e["name"],
            "variants": sorted(e["variants"]),
            "sources": e["sources"],
            "queries": len(e["queries"]),
            "best_position": e["best_position"],
            "subject_class": cls,
            "subject_basis": basis,
        })
    out.sort(key=lambda c: (-c["queries"], c["best_position"] or 999))
    return out


# ------------------------------------------------------------------ linking
def link_block(block: dict, roster: list[dict], ctx=None) -> Optional[str]:
    """The roster clinic a result belongs to, or None.

    Tries the visible title first, then the domain — an ad or an Instagram profile often
    carries the brand in one and not the other.
    """
    ctx = packs.resolve(ctx)
    stop = {t.lower() for t in (ctx.geo.get("city_tokens") or [])}
    title = clean_name(block.get("title") or "")
    domain = (block.get("domain") or "").split(".")[0]
    for candidate in (title, domain):
        if not candidate or len(candidate) < 4:
            continue
        for clinic in roster:
            if same_clinic(clinic["name"], candidate, stop):
                return clinic["name"]
            if any(same_clinic(v, candidate, stop) for v in clinic["variants"]):
                return clinic["name"]
    return None


def social_platform(block: dict) -> Optional[str]:
    host = (block.get("domain") or "").lower()
    for frag, label in _SOCIAL_HOSTS.items():
        if frag in host:
            return label
    return None


def annotate(queries: list[dict], roster: list[dict], ctx=None) -> dict:
    """Attach a linked clinic to every ad, social result and own-site hit. Counts what stuck.

    Own-site results are NOT opened — the requirement is only to note that a clinic's own
    domain appeared, which the platform label already tells us.
    """
    ctx = packs.resolve(ctx)
    stats = {"sponsored": 0, "sponsored_linked": 0, "social": 0, "social_linked": 0,
             "clinic_site": 0, "clinic_site_linked": 0}
    for q in queries:
        for b in q.get("blocks") or []:
            kind = b.get("block_type") or ""
            plat = social_platform(b)
            is_ad = kind.startswith("sponsored")
            is_own = b.get("platform") == "clinic_site" and kind == "organic"
            if not (is_ad or plat or is_own):
                continue
            linked = link_block(b, roster, ctx)
            b["linked_clinic"] = linked
            if plat:
                b["social_platform"] = plat
                stats["social"] += 1
                stats["social_linked"] += bool(linked)
            if is_ad:
                stats["sponsored"] += 1
                stats["sponsored_linked"] += bool(linked)
            if is_own:
                stats["clinic_site"] += 1
                stats["clinic_site_linked"] += bool(linked)
    return stats


def split_by_subject(roster: list[dict]) -> dict:
    """Clinics vs multispeciality hospitals vs unclassified — counted, never silently dropped."""
    out = {"clinic": [], "hospital": [], "ambiguous": []}
    for c in roster:
        out.setdefault(c["subject_class"], []).append(c)
    return out
