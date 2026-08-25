"""Geography and specialty packs: the market definition as data, not code.

Before this, "Guntur" and "dermatology" were literals scattered through six modules — a query
prompt, a Maps search suffix, a name-matching stopword list, report copy, a rating threshold.
Expanding to a second city or specialty meant editing code in all of them. A pack is a JSON
file; `load()` turns two of them into a `RunContext` that those call sites accept.

Compatibility rule: every de-hardcoded function takes `ctx=None`, and `legacy_context()`
reproduces the current Guntur/dermatology behaviour exactly. The June snapshot was scored with
those literals, so any drift in (say) the stopword set would re-map SERP blocks to different
clinics and quietly rewrite history.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")

PACKS_DIR = Path(config.BASE_DIR) / "packs"
SUBJECT_TYPES = ("individual", "hospitals", "both")

# Generic words that never distinguish one local clinic from another. Kept identical to
# web_collector._TOKEN_STOPWORDS minus the market-specific entries, which come from the packs.
BASE_NAME_STOPWORDS = {
    "the", "and", "in", "of", "for", "best", "top", "clinic", "clinics",
    "hospital", "hospitals", "centre", "center", "care", "dr", "drs", "doctor",
    "near", "me", "specialist",
}


class PackNotFound(Exception):
    """Named pack does not exist — fail loudly rather than silently using a default market."""


class InvalidPack(Exception):
    """Pack exists but is malformed or internally inconsistent."""


# ------------------------------------------------------------------ validation
def validate_geography(pack: dict) -> dict:
    for key in ("id", "city", "state"):
        if not pack.get(key):
            raise InvalidPack(f"geography pack missing required field: {key}")
    latlng = pack.get("latlng")
    if not (isinstance(latlng, (list, tuple)) and len(latlng) == 2):
        raise InvalidPack("geography pack needs latlng [lat, lng] — it anchors the REACH term")
    return pack


def validate_specialty(pack: dict) -> dict:
    for key in ("id", "name", "specialist_noun"):
        if not pack.get(key):
            raise InvalidPack(f"specialty pack missing required field: {key}")
    conditions = pack.get("conditions") or []
    if not conditions:
        raise InvalidPack("specialty pack needs at least one condition")
    for cond in conditions:
        if len(cond.get("phrasings") or []) < 2:
            raise InvalidPack(
                f"condition {cond.get('id')!r} needs >= 2 phrasings: patients phrase the same "
                f"need very differently, and one phrasing under-samples the market")
    # Treatments are optional, but a listed treatment with no phrasing is a latent crash: the
    # query builder indexes phrasings[0]. Require at least one so the pack fails here, loudly,
    # not mid-run.
    for tx in pack.get("treatments") or []:
        if not (tx.get("phrasings") or []):
            raise InvalidPack(f"treatment {tx.get('id')!r} needs at least one phrasing")
    return pack


# ------------------------------------------------------------------ loading
def _read(kind: str, name: str) -> dict:
    path = PACKS_DIR / kind / f"{name}.json"
    if not path.exists():
        raise PackNotFound(f"no {kind} pack named {name!r} (looked in {path})")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InvalidPack(f"{path} is not valid JSON: {exc}") from exc


def available_geographies() -> list[str]:
    d = PACKS_DIR / "geography"
    return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []


def available_specialties() -> list[str]:
    d = PACKS_DIR / "specialty"
    return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []


@dataclass
class RunContext:
    """Everything a run needs to know about *which market* it is measuring."""
    geo: dict = field(default_factory=dict)
    spec: dict = field(default_factory=dict)
    subject_type: str = "both"
    query_threshold: Optional[int] = None

    # ---- geography
    @property
    def city(self) -> str:
        return self.geo.get("city", "")

    @property
    def state(self) -> str:
        return self.geo.get("state", "")

    @property
    def display_name(self) -> str:
        return self.geo.get("display_name") or f"{self.city}, {self.state}".strip(", ")

    @property
    def latlng(self) -> tuple:
        ll = self.geo.get("latlng") or [None, None]
        return (ll[0], ll[1])

    @property
    def gl(self) -> str:
        return self.geo.get("gl", "in")

    @property
    def hl(self) -> str:
        return self.geo.get("hl", "en")

    @property
    def locale(self) -> str:
        return self.geo.get("locale", "en-IN")

    @property
    def requires_city_in_query(self) -> bool:
        return bool(self.geo.get("requires_city_in_query", True))

    @property
    def maps_search_suffix(self) -> str:
        """Appended to a Maps query that doesn't already name the market."""
        return self.city

    # ---- specialty
    @property
    def specialist_noun(self) -> str:
        return self.spec.get("specialist_noun", "")

    @property
    def default_query_threshold(self) -> Optional[int]:
        return self.spec.get("default_query_threshold")

    @property
    def conditions(self) -> list:
        return self.spec.get("conditions") or []

    @property
    def treatments(self) -> list:
        return self.spec.get("treatments") or []

    def name_stopwords(self) -> set:
        """Tokens that must not be used to match a clinic name to a search result."""
        return (BASE_NAME_STOPWORDS
                | {t.lower() for t in (self.spec.get("specialty_tokens") or [])}
                | {t.lower() for t in (self.geo.get("city_tokens") or [])})

    # ---- subject type
    def classify_subject_with_basis(self, name: str, category: str = "") -> tuple:
        """(clinic|hospital|ambiguous, basis).

        A multi-specialty hospital and a solo practitioner are not comparable units — the
        hospital wins on volume signals that say nothing about its dermatology. Anything the
        rules cannot place stays `ambiguous` and is reported as such, never silently bucketed.

        The basis is returned because the Maps category is often blank (the June snapshot has
        no `types` values at all), leaving only name heuristics. A reader needs to know which
        evidence produced the label — "hospital by category" and "hospital because the name
        contains 'hospital'" are not equally trustworthy.
        """
        rules = self.spec.get("subject_type_rules") or {}
        cat = (category or "").strip().lower()
        nm = (name or "").strip().lower()
        if cat:
            for s in rules.get("hospital_category_strings") or []:
                if s.lower() in cat:
                    return "hospital", "category"
            for s in rules.get("clinic_category_strings") or []:
                if s.lower() in cat:
                    return "clinic", "category"
        for tok in rules.get("hospital_name_tokens") or []:
            if tok.lower() in nm:
                return "hospital", "name"
        for tok in (rules.get("clinic_name_tokens") or []) + (self.spec.get("facility_nouns") or []):
            if tok.lower() in nm:
                return "clinic", "name"
        return "ambiguous", "unclassified"

    def classify_subject(self, name: str, category: str = "") -> str:
        return self.classify_subject_with_basis(name, category)[0]

    def includes_subject(self, subject_class: str) -> bool:
        """Ambiguous rows stay visible under every filter — dropping them hides real clinics."""
        if subject_class == "ambiguous" or self.subject_type == "both":
            return True
        if self.subject_type == "individual":
            return subject_class == "clinic"
        if self.subject_type == "hospitals":
            return subject_class == "hospital"
        return True

    def as_manifest(self) -> dict:
        return {"geography": self.geo.get("id"), "specialty": self.spec.get("id"),
                "subject_type": self.subject_type, "query_threshold": self.query_threshold}


def load(geography: str, specialty: str, subject_type: str = "both",
         query_threshold: Optional[int] = None) -> RunContext:
    if subject_type not in SUBJECT_TYPES:
        raise InvalidPack(f"subject_type must be one of {SUBJECT_TYPES}, got {subject_type!r}")
    geo = validate_geography(_read("geography", geography))
    spec = validate_specialty(_read("specialty", specialty))
    return RunContext(geo=geo, spec=spec, subject_type=subject_type,
                      query_threshold=query_threshold or spec.get("default_query_threshold"))


def legacy_context() -> RunContext:
    """The pre-pack behaviour, for `ctx=None` call sites and for scoring snapshot #1.

    Built from config + the literals that were compiled into the modules, so existing
    behaviour is reproduced exactly rather than approximated by the Guntur pack.
    """
    from modules.web_collector import _TOKEN_STOPWORDS

    city = str(getattr(config, "TARGET_CITY", "Guntur")).split(",")[0].strip()
    lat, lng = 16.3067, 80.4365
    try:
        lat, lng = [float(x) for x in str(config.TARGET_LOCATION_LATLNG).split(",")]
    except Exception:
        pass
    geo = {"id": "legacy", "city": city, "state": "Andhra Pradesh", "latlng": [lat, lng],
           "gl": "in", "hl": "en", "locale": getattr(config, "SCRAPER_LOCALE", "en-IN"),
           "city_tokens": [city.lower()], "requires_city_in_query": True}
    spec = {"id": "legacy", "name": "Legacy", "specialist_noun": getattr(config, "SPECIALTY", ""),
            "conditions": [{"id": "legacy", "phrasings": ["a", "b"]}],
            "specialty_tokens": sorted(set(_TOKEN_STOPWORDS) - BASE_NAME_STOPWORDS),
            "default_query_threshold": getattr(config, "NUM_QUERIES", None)}
    ctx = RunContext(geo=geo, spec=spec, subject_type="both",
                     query_threshold=getattr(config, "NUM_QUERIES", None))
    return ctx


def resolve(ctx: Optional[RunContext]) -> RunContext:
    """Every de-hardcoded call site starts with this: `ctx = packs.resolve(ctx)`."""
    return ctx if ctx is not None else legacy_context()
