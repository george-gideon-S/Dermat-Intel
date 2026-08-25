"""Central configuration for Derma Intel.

No API keys are used anywhere in this project — it runs entirely on free tools.
"""
from pathlib import Path

# --- Target market ---
TARGET_CITY = "Guntur, Andhra Pradesh, India"
TARGET_LOCATION_LATLNG = "16.3067,80.4365"
SPECIALTY = "dermatologist"

# --- Pipeline sizing ---
NUM_QUERIES = 50
RESULTS_PER_QUERY = 15
MAPS_RADIUS_M = 15000

# --- Paths (absolute, anchored to this file) ---
BASE_DIR = Path(__file__).resolve().parent

# Runs are snapshots: every artifact for one (geography, practice, subject_type, run_date)
# lives under runs/<run_id>/ and is never overwritten by a later run. activate_run() repoints
# the path constants below at a run directory; modules that read config.<PATH> at call time
# follow automatically. (Only four module-level captures exist and they are resolved lazily —
# see modules/storage.py and modules/web_collector.py.)
RUNS_DIR = str(BASE_DIR / "runs")

# The Google-Maps survey snapshots (gmaps/run.py) live in their own tree — a different
# pipeline from the SERP runs above. Read them via modules/marketdata.py.
GMAPS_RUNS_DIR = str(BASE_DIR / "runs" / "gmaps")

# The browser profile must NOT be run-scoped: cookies and solved-CAPTCHA state are what keep
# the SERP scraper unblocked, and they have to survive across quarterly runs.
BROWSER_DIR = str(BASE_DIR / ".browser")
SERP_PROFILE_DIR = str(BASE_DIR / ".browser" / "serp_profile")

ACTIVE_RUN_DIR = None  # None -> legacy flat layout (data/ + .cache/ at the repo root)


def _apply_roots(root: Path) -> None:
    """Point every derived path at `root`. Called at import, and again by activate_run()."""
    global DATA_DIR, CACHE_DIR, QUERIES_XLSX, RESULTS_XLSX, VULNERABLE_XLSX, MAPS_CACHE
    global SCREENSHOTS_DIR, WEB_TILES_DIR, WEB_SCREENS_CACHE, SEARCH_RESULTS_XLSX, UNIFIED_XLSX
    DATA_DIR = str(root / "data")
    CACHE_DIR = str(root / ".cache")
    QUERIES_XLSX = str(root / "data" / "search_queries.xlsx")
    RESULTS_XLSX = str(root / "data" / "google_maps_results.xlsx")
    VULNERABLE_XLSX = str(root / "data" / "vulnerable_10.xlsx")
    MAPS_CACHE = str(root / ".cache" / "maps_raw.json")
    # --- Google-web SERP dataset (free: automated capture + DOM extraction) ---
    SCREENSHOTS_DIR = str(root / "serp" / "screenshots")  # one PNG per query (serp_proof evidence)
    WEB_TILES_DIR = str(root / ".cache" / "web_tiles")    # ephemeral legible tiles (gitignored)
    WEB_SCREENS_CACHE = str(root / ".cache" / "web_screens.json")  # SERP dataset (source of truth)
    SEARCH_RESULTS_XLSX = str(root / "data" / "google_search_results.xlsx")
    UNIFIED_XLSX = str(root / "data" / "unified_results.xlsx")


_apply_roots(BASE_DIR)
METADATA_FILE = str(BASE_DIR / "metadata.json")  # global "last run" marker, never run-scoped


def activate_run(run_dir) -> str:
    """Repoint all artifact paths at a run snapshot directory. Returns the active dir."""
    global ACTIVE_RUN_DIR
    root = Path(run_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    _apply_roots(root)
    ACTIVE_RUN_DIR = str(root)
    return ACTIVE_RUN_DIR


def deactivate_run() -> None:
    """Restore the legacy flat layout (used by tests and the pre-snapshot CLI)."""
    global ACTIVE_RUN_DIR
    _apply_roots(BASE_DIR)
    ACTIVE_RUN_DIR = None

# --- Scraper settings (free Google Maps scraping via Playwright) ---
SCRAPER_HEADLESS = True
SCRAPER_MIN_DELAY_S = 1.5          # randomized polite delay between actions (anti rate-limit)
SCRAPER_MAX_DELAY_S = 3.5
SCRAPER_PAGE_TIMEOUT_S = 30
SCRAPER_MAX_RETRIES = 3
SCRAPER_OPEN_DETAILS = True        # open each place panel for clean website/phone/address (slower, accurate)
USE_OSM_FALLBACK = True            # use OpenStreetMap Nominatim (keyless) to geocode gaps
SCRAPER_LOCALE = "en-IN"
SCRAPER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# --- Query categories (canonical 6) ---
# See `query writing.md` for the rules that assign these. Two former categories were retired:
# "Comparison" (an artefact of one template, never a real patient intent) and
# "Trust & Social Proof" (a "best rated X" search is the same discovery intent as "best X",
# so splitting them fragmented the discovery count without telling us anything new).
CATEGORIES = [
    "Discovery",
    "Doctor-Based",
    "Condition-Based",
    "Product-Based",
    "Pricing",
    "Appointment & Booking",
]
CATEGORY_COLORS = {
    "Discovery": "#2563EB",             # blue
    "Doctor-Based": "#7C3AED",          # violet
    "Condition-Based": "#DB2777",       # pink
    "Product-Based": "#0D9488",         # teal
    "Pricing": "#CA8A04",               # amber
    "Appointment & Booking": "#0891B2", # cyan
}

# --- Vulnerability labels: (min_score_inclusive, label, hex_color) high -> low ---
VULN_LABELS = [
    (80, "Critical", "#DC2626"),
    (60, "High", "#EA580C"),
    (40, "Medium", "#CA8A04"),
    (0, "Low", "#16A34A"),
]

# --- Go-to-market (public links & prices; NOT secrets — see spec 2026-07-10 §1) ---
# Razorpay payment links are public URLs George creates in his Razorpay dashboard and pastes
# here. Empty string -> the CTA falls back to WhatsApp; empty WhatsApp -> plain "contact" note.
PRICE_REPORT = 4999          # Visibility Report (one-time "examination")
PRICE_MONITOR_QTR = 2999     # Monitoring, per quarter (anchor)
PRICE_MONITOR_YR = 9999      # Monitoring, per year (hero of tier 2)
PRICE_BUILD_FROM = 49999     # Website + Visibility Build, "from"
PRICE_RETAINER_MO = 4999     # Growth Retainer, per month
RAZORPAY_LINK_REPORT = ""      # e.g. https://rzp.io/l/...
RAZORPAY_LINK_MONITOR_QTR = ""
RAZORPAY_LINK_MONITOR_YR = ""
WHATSAPP_NUMBER = ""           # E.164 digits only, e.g. "919999999999"
PUBLIC_SALT = "derma-intel-2026"  # public self-lookup hash salt (obfuscation, not security)

# --- .env (gitignored) -> environment, so secrets and endpoints never enter the repo ---
def _load_dotenv(path=None) -> None:
    """Minimal loader: KEY=VALUE lines, '#' comments, existing environment always wins."""
    import os
    target = Path(path) if path else (BASE_DIR / ".env")
    try:
        for line in target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except (OSError, UnicodeDecodeError):
        pass


_load_dotenv()
