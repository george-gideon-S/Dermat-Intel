"""Load the geography + specialty packs that define a run, and compose the search query.

A run is (geography, specialty). Everything market-specific or specialty-specific is data in
gmaps/packs/, so covering a new city or a new specialty is a JSON file, never a code change.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

PACKS_DIR = Path(__file__).resolve().parent / "packs"


#: Rough national bounding boxes (lat_lo, lat_hi, lng_lo, lng_hi) used only as a sanity check on
#: a geography pack's viewport. Deliberately generous - the job is to catch a transposed or
#: mistyped coordinate, not to police borders. Unknown country codes skip the check.
COUNTRY_BOUNDS = {
    "IN": (6.0, 37.5, 68.0, 97.5),      "US": (18.0, 72.0, -180.0, -66.0),
    "GB": (49.5, 61.0, -8.7, 2.0),      "AE": (22.5, 26.5, 51.0, 56.5),
    "AU": (-44.0, -10.0, 112.0, 154.0), "CA": (41.5, 83.5, -141.0, -52.0),
    "SG": (1.1, 1.5, 103.5, 104.1),     "MY": (0.8, 7.5, 99.5, 119.5),
    "ZA": (-35.0, -22.0, 16.0, 33.0),   "NZ": (-47.5, -34.0, 166.0, 179.0),
    "LK": (5.9, 10.0, 79.5, 82.0),      "BD": (20.5, 26.7, 88.0, 92.7),
    "NP": (26.3, 30.5, 80.0, 88.3),     "PK": (23.5, 37.1, 60.8, 77.9),
    "AT": (46.3, 49.1, 9.5, 17.2),      "DE": (47.2, 55.1, 5.8, 15.1),
    "FR": (41.3, 51.2, -5.2, 9.6),      "ES": (35.9, 43.8, -9.4, 4.4),
    "IT": (35.4, 47.1, 6.6, 18.6),      "NL": (50.7, 53.6, 3.3, 7.3),
}


class PackNotFound(Exception):
    """Named pack does not exist. Fail loudly rather than silently survey the wrong market."""


class InvalidPack(Exception):
    """Pack exists but is malformed."""


def _read(kind: str, name: str) -> dict:
    path = PACKS_DIR / kind / f"{name}.json"
    if not path.exists():
        raise PackNotFound(f"no {kind} pack named {name!r} (looked in {path})")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InvalidPack(f"{path} is not valid JSON: {exc}") from exc


def available_geographies() -> list[str]:
    d = PACKS_DIR / "geographies"
    return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []


def available_specialties() -> list[str]:
    d = PACKS_DIR / "specialties"
    return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []


def _require_str_list(pack: dict, key: str, required: bool = False) -> None:
    """A list of strings, or a clear error.

    Type checks belong here, not at first use. A pack whose relevant_categories is the STRING
    "dermatologist" passes a truthiness check, then iterates as 14 single characters - so every
    category silently stops matching and an entire market is declared irrelevant. A pack holding
    integers raises TypeError inside the browser session, 40 minutes into a run.
    """
    val = pack.get(key)
    if val is None:
        if required:
            raise InvalidPack(f"{pack.get('id')!r}: {key} is required")
        return
    if isinstance(val, str):
        raise InvalidPack(
            f"{pack.get('id')!r}: {key} must be a LIST of strings, got a plain string "
            f"({val[:40]!r}) - a string iterates as single characters and silently matches nothing")
    if not isinstance(val, list):
        raise InvalidPack(f"{pack.get('id')!r}: {key} must be a list, got {type(val).__name__}")
    bad = [v for v in val if not isinstance(v, str)]
    if bad:
        raise InvalidPack(f"{pack.get('id')!r}: {key} contains non-string entries: {bad[:3]}")
    if required and not val:
        raise InvalidPack(f"{pack.get('id')!r}: {key} is empty")


def validate_specialty(pack: dict) -> dict:
    if not isinstance(pack, dict):
        raise InvalidPack(f"specialty pack must be a JSON object, got {type(pack).__name__}")
    for key in ("id", "specialist_singular", "specialist_plural"):
        if not pack.get(key) or not isinstance(pack[key], str):
            raise InvalidPack(f"specialty pack missing or non-string {key}")
    _require_str_list(pack, "relevant_categories", required=True)
    for key in ("adjacent_categories", "irrelevant_categories", "name_strong",
                "name_veto", "facility_nouns", "specialist_synonyms"):
        _require_str_list(pack, key)
    tpl = pack.get("primary_query")
    if tpl is not None:
        if not isinstance(tpl, str):
            raise InvalidPack(f"{pack.get('id')!r}: primary_query must be a string")
        try:
            tpl.format(specialists="x", specialist="x", city="x", place="x")
        except (KeyError, IndexError, ValueError) as exc:
            raise InvalidPack(
                f"{pack.get('id')!r}: primary_query has an unusable placeholder ({exc}). "
                f"Available: {{specialists}} {{specialist}} {{city}} {{place}}") from exc
    return pack


def validate_geography(pack: dict) -> dict:
    if not isinstance(pack, dict):
        raise InvalidPack(f"geography pack must be a JSON object, got {type(pack).__name__}")
    for key in ("id", "city"):
        if not pack.get(key) or not isinstance(pack[key], str):
            raise InvalidPack(f"geography pack missing or non-string {key}")
    _require_str_list(pack, "city_tokens")
    _require_str_list(pack, "localities")
    _require_str_list(pack, "chain_domains")

    # A transposed lat/lng is a plausible authoring slip and silently anchors the map to the
    # wrong hemisphere - the run then surveys an empty ocean and reports it as the market.
    vp = pack.get("viewport")
    if vp is not None:
        if not isinstance(vp, dict):
            raise InvalidPack(f"{pack.get('id')!r}: viewport must be an object")
        lat, lng = vp.get("lat"), vp.get("lng")
        if lat is None or lng is None:
            raise InvalidPack(f"{pack.get('id')!r}: viewport needs both lat and lng")
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError) as exc:
            raise InvalidPack(f"{pack.get('id')!r}: viewport lat/lng must be numbers") from exc
        if not -90 <= lat <= 90:
            raise InvalidPack(f"{pack.get('id')!r}: viewport lat {lat} is out of range (-90..90)")
        if not -180 <= lng <= 180:
            raise InvalidPack(f"{pack.get('id')!r}: viewport lng {lng} is out of range (-180..180)")

        # Range checks alone do NOT catch a transposition: Guntur is 16.31,80.44 and the swapped
        # pair 80.44,16.31 is a perfectly valid coordinate - in the Indian Ocean. Only a country
        # bounds check finds it, which is why the country code is worth carrying in the pack.
        cc = (pack.get("country_code") or "").upper()
        if not cc:
            raise InvalidPack(
                f"{pack.get('id')!r}: a viewport requires country_code, otherwise a mistyped or "
                f"transposed coordinate cannot be detected (both halves of a swap are usually "
                f"valid numbers).")
        box = COUNTRY_BOUNDS.get(cc)
        if box:
            lat_lo, lat_hi, lng_lo, lng_hi = box
            if not (lat_lo <= lat <= lat_hi and lng_lo <= lng <= lng_hi):
                swapped = lat_lo <= lng <= lat_hi and lng_lo <= lat <= lng_hi
                hint = " - lat and lng look transposed" if swapped else ""
                raise InvalidPack(
                    f"{pack.get('id')!r}: viewport ({lat}, {lng}) is outside {cc}{hint}. "
                    f"Expected lat {lat_lo}..{lat_hi}, lng {lng_lo}..{lng_hi}.")
    return pack


@dataclass
class RunContext:
    geo: dict = field(default_factory=dict)
    spec: dict = field(default_factory=dict)
    #: UI language is pinned to English for extraction regardless of the market. Every field we
    #: read is an English aria-label or category string; letting Google localise the interface
    #: would silently empty them. The market's own language belongs in the query text, not here.
    extract_hl: str = "en"

    # ---- geography
    @property
    def city(self) -> str:
        return self.geo.get("city", "")

    @property
    def gl(self) -> str:
        return self.geo.get("gl", "in")

    @property
    def timezone(self) -> str:
        return self.geo.get("timezone", "Asia/Kolkata")

    @property
    def place_qualifier(self) -> str:
        """How the place is named inside the query text.

        The admin area is added ONLY for places whose name is genuinely ambiguous, because it
        narrows the result set: measured 2026-08-20, "best dermatologists in Guntur, Andhra
        Pradesh" returned 48 places where "dermatologists in Guntur" returned 98, with Google
        reporting end-of-list cleanly both times. The clinics that drop out are the small,
        unranked ones - exactly the prospects the survey exists to find.

        So a well-known city is named bare, and a pack sets qualify_with_admin_area only when
        the place name really does collide across states or countries.
        """
        city = self.geo.get("city") or ""
        if not self.geo.get("qualify_with_admin_area"):
            return city
        return self.geo.get("place_qualifier") or ", ".join(
            x for x in (city, self.geo.get("admin_area")) if x)

    @property
    def viewport(self) -> dict | None:
        return self.geo.get("viewport")

    @property
    def chain_domains(self) -> set:
        return {d.lower() for d in (self.geo.get("chain_domains") or [])}

    # ---- specialty
    @property
    def specialist_plural(self) -> str:
        return self.spec.get("specialist_plural", "")

    @property
    def display_name(self) -> str:
        return self.spec.get("display_name", self.spec.get("id", ""))

    def search_query(self, template: str | None = None) -> str:
        """The single Maps query for the run.

        One query, deliberately. Condition searches ("psoriasis treatment") are how patients use
        Google *search*; on Maps they mostly re-return the same clinics the specialist query
        already found, at several hours of extra scraping for little new coverage.

        The template is the PLAIN form, not "best ...". Measured 2026-08-20 on the same market:
        "dermatologists in Guntur" -> 98 places; "best dermatologists in Guntur, Andhra Pradesh"
        -> 48. Both ended cleanly, so "best" is not a filter Google ignores - it shifts the
        request from "list businesses of this type" to "rank the notable ones", and the tail it
        removes is the small unranked clinics that make up most of the sales prospects.
        """
        tpl = template or self.spec.get("primary_query") or "{specialists} in {place}"
        return tpl.format(specialists=self.specialist_plural,
                          specialist=self.spec.get("specialist_singular", ""),
                          city=self.city, place=self.place_qualifier).strip()

    def maps_url(self, query: str | None = None) -> str:
        """Search URL, geo-anchored twice: the qualifier in the text and the viewport in the URL."""
        import urllib.parse
        q = urllib.parse.quote_plus(query or self.search_query())
        vp = self.viewport or {}
        anchor = (f"/@{vp['lat']},{vp['lng']},{vp.get('zoom', 13)}z"
                  if vp.get("lat") is not None and vp.get("lng") is not None else "")
        return (f"https://www.google.com/maps/search/{q}{anchor}"
                f"/?hl={self.extract_hl}&gl={self.gl}")

    def as_manifest(self) -> dict:
        return {"geography": self.geo.get("id"), "specialty": self.spec.get("id"),
                "city": self.city, "country": self.geo.get("country"),
                "gl": self.gl, "extract_hl": self.extract_hl,
                "timezone": self.timezone, "query": self.search_query()}


def load(geography: str, specialty: str) -> RunContext:
    geo = validate_geography(_read("geographies", geography))
    spec = validate_specialty(_read("specialties", specialty))
    return RunContext(geo=geo, spec=spec)
