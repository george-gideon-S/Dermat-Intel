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
DATA_DIR = str(BASE_DIR / "data")
CACHE_DIR = str(BASE_DIR / ".cache")
QUERIES_XLSX = str(BASE_DIR / "data" / "search_queries.xlsx")
RESULTS_XLSX = str(BASE_DIR / "data" / "google_maps_results.xlsx")
VULNERABLE_XLSX = str(BASE_DIR / "data" / "vulnerable_10.xlsx")
MAPS_CACHE = str(BASE_DIR / ".cache" / "maps_raw.json")
METADATA_FILE = str(BASE_DIR / "metadata.json")

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

# --- Query categories (canonical 7) ---
CATEGORIES = [
    "Discovery",
    "Comparison",
    "Trust & Social Proof",
    "Pricing",
    "Condition-Based",
    "Appointment & Booking",
    "Near Me / Local",
]
CATEGORY_COLORS = {
    "Discovery": "#2563EB",             # blue
    "Comparison": "#0D9488",            # teal
    "Trust & Social Proof": "#7C3AED",  # violet
    "Pricing": "#CA8A04",               # amber
    "Condition-Based": "#DB2777",       # pink
    "Appointment & Booking": "#0891B2", # cyan
    "Near Me / Local": "#16A34A",       # green
}

# --- Vulnerability labels: (min_score_inclusive, label, hex_color) high -> low ---
VULN_LABELS = [
    (80, "Critical", "#DC2626"),
    (60, "High", "#EA580C"),
    (40, "Medium", "#CA8A04"),
    (0, "Low", "#16A34A"),
]
