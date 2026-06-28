# Claude Code Prompts

## Dermat Analytics

> **REVISION (v2 — 100% free / no API keys).**
> This version removes every paid service and every API key. Two architectural changes:
> 1. **Query generation is manual** — the app gives you a prompt to paste into any free AI tool (ChatGPT / Claude / Gemini / Perplexity), and you paste the result back. No Anthropic API.
> 2. **Maps data is collected by free Google Maps scraping (Playwright, no API key)** — same source as the paid Places API, so same accuracy. OpenStreetMap (keyless) is a free fallback.
> All other AI calls (opportunity notes, summary) are now generated locally from the data via templates.
> ⚠️ Note: scraping Google Maps is against Google's ToS and is more fragile than an API. At this low volume (~50 queries, run occasionally from your own IP with polite delays) it is low-risk and needs no proxies, but the collector is built to degrade gracefully (caching, retries, FETCH_FAILED rows, mock-data mode). A 100%-clean OpenStreetMap-only path is available as an alternative (trade-off: no ratings/reviews).

## Project Overview

Build a full-stack Dermatologist Search Intelligence Platform for Guntur, India.
**No paid APIs. No API keys. Runs entirely free.**
The system:

1. Provides a ready-made AI prompt the user copies into any free AI tool to generate 50 high-intent
   dermatology search queries, then pastes the result back into the app (which parses + validates them)
2. Scrapes Google Maps (free, no API key, via Playwright) for each query and collects top 15 results
   (~750 total appearance rows)
3. Runs deep competitive analytics with 12+ interactive charts
4. Scores clinics on a Vulnerability Index (0–100) and exports the 10 most vulnerable
5. Surfaces everything through a beautiful, multi-tab Streamlit dashboard

---

## Tech Stack

- Language: Python 3.10+
- UI: Streamlit (wide layout)
- AI: **None at runtime — no API keys.**
  - Query generation: done manually by the user in any free AI tool via a provided copy-paste prompt.
  - Narrative text (opportunity notes, Tab-4 summary): generated locally from the data via templates.
- Maps data: **Google Maps scraping via Playwright (free, no API key, headless Chromium).**
  - Free fallback: OpenStreetMap Nominatim/Overpass (keyless) for geocoordinates and gap-filling.
- Data: openpyxl / pandas for Excel
- Charts: Plotly Express + Altair (+ kaleido for per-chart PNG export)
- Extras: fpdf2 (PDF export), requests (OSM fallback calls)

> Removed from the original stack: `anthropic`, Google Places API, `python-dotenv` (no secrets to load),
> `streamlit-aggrid` (native `st.dataframe` + `column_config` already covers Tab 1).

---

## Project File Structure

derma-intel/
├── app.py                    # Streamlit entry point with 4 tabs
├── config.py                 # Constants: city, specialty, counts, paths, scraper settings
├── requirements.txt
├── README.md
├── metadata.json             # Last-run timestamp + run stats (created at runtime)
├── data/
│   ├── search_queries_50.xlsx
│   ├── google_maps_results_50.xlsx
│   ├── vulnerable_10.xlsx
│   └── .gitkeep
├── .cache/
│   ├── maps_raw.json         # Scrape cache keyed by query+place to avoid duplicate work
│   └── .gitkeep
├── modules/
│   ├── query_generator.py    # Step 1: build copy-paste AI prompt + parse pasted queries
│   ├── maps_collector.py     # Step 2: Google Maps scraping (Playwright) + OSM fallback
│   ├── analytics.py          # Step 3: all Plotly/Altair chart builders
│   └── vulnerability.py      # Step 4: scoring + local opportunity notes + top 10 export
└── components/
    ├── tab_queries.py        # Tab 1 UI (paste-prompt workflow + 50-query table)
    ├── tab_results.py        # Tab 2 UI
    ├── tab_analytics.py      # Tab 3 UI
    └── tab_vulnerable.py     # Tab 4 UI

> Removed `.env` — there are no keys. All configuration lives in `config.py`.

---

## Config (config.py)

TARGET_CITY = "Guntur, Andhra Pradesh, India"
TARGET_LOCATION_LATLNG = "16.3067,80.4365"
SPECIALTY = "dermatologist"
NUM_QUERIES = 50
RESULTS_PER_QUERY = 15
MAPS_RADIUS_M = 15000
CACHE_DIR = ".cache"
DATA_DIR = "data"

# --- Scraper settings (free Google Maps scraping) ---
SCRAPER_HEADLESS = True
SCRAPER_MIN_DELAY_S = 1.5        # randomized polite delay between actions (anti rate-limit)
SCRAPER_MAX_DELAY_S = 3.5
SCRAPER_PAGE_TIMEOUT_S = 30
SCRAPER_MAX_RETRIES = 3
USE_OSM_FALLBACK = True          # use OpenStreetMap (keyless) to geocode / fill gaps
SCRAPER_LOCALE = "en-IN"
SCRAPER_USER_AGENT = (           # realistic UA to reduce friction
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

> No `AI_MODEL`, no `ANTHROPIC_API_KEY`, no `GOOGLE_PLACES_API_KEY`.

---

## Step 1: Query Generation — Manual AI Paste (modules/query_generator.py)

**No API calls.** The user generates the 50 queries themselves in any free AI tool, guided by a prompt
the app provides, then pastes the result back. Three functions:

### a) `build_ai_prompt() -> str`
Returns a ready-to-copy prompt string. Tab 1 renders it in a `st.code()` block (built-in copy button).
The prompt instructs the AI to output the queries in the exact comma-separated single-quoted format and
nothing else:

```
You are a local SEO and healthcare search-behavior expert for India.

Generate exactly 50 high-intent Google search queries that people in Guntur, Andhra Pradesh
use before visiting a dermatologist. Base them on real doctor-search behavior: best/top ranking
terms, near-me local intent, fees, reviews, appointment booking, comparison, and symptom /
condition-based searches (acne, hair fall, pigmentation, eczema, psoriasis, fungal infection, etc.).
Order them by estimated monthly search strength (strongest first).

Return ONLY the 50 queries as a single comma-separated list of single-quoted strings.
No numbering, no explanation, no markdown, no headings. Use this exact format:

'best dermatologist in Guntur', 'skin specialist near me Guntur', 'dermatologist fees in Guntur', 'acne treatment doctor Guntur', ...

Make sure there are exactly 50 quoted queries.
```

### b) `parse_pasted_queries(text: str) -> list[dict]`
A robust parser for whatever the user pastes back. It MUST tolerate:
- single `'` or double `"` quotes
- leading/trailing whitespace and newlines
- optional numbering (`1. 'abc'`), bullets (`- 'abc'`), or surrounding brackets `[ ... ]`
- queries separated by commas and/or newlines
- de-duplicate (case-insensitive), strip empties

For each query it returns a dict with all 5 fields the rest of the app expects:
- `rank` — 1..N by paste order
- `search_query` — the cleaned string
- `category` — **auto-derived** by keyword rules (see below)
- `user_intent` — **auto-derived** templated sentence per category
- `search_strength_score` — **auto-derived** integer 1–10 (from rank position + a small category weight)

**Category derivation (case-insensitive keyword rules, first match wins, in this order):**
1. condition words (acne, pimple, hair fall, hair loss, dandruff, eczema, psoriasis, fungal, rash,
   skin allergy, pigmentation, melasma, wart, mole, vitiligo, scar) → `"Condition-Based"`
2. "fee", "fees", "cost", "price", "charges", "₹", "cheap", "affordable" → `"Pricing"`
3. "review", "reviews", "rating", "ratings", "best rated", "top rated", "feedback" → `"Trust & Social Proof"`
4. "appointment", "book", "booking", "consult", "consultation", "online consultation" → `"Appointment & Booking"`
5. " vs ", " or ", "compare", "better", "best vs" → `"Comparison"`
6. "near me", "nearby", "near by", "around me", "closest", "close to me", "in my area" → `"Near Me / Local"`
   (NOTE: do NOT match the bare city name "guntur" here — every query mentions Guntur, so it must not
   collapse them all into Near Me / Local.)
7. "best", "top", "good", "famous", "leading", "specialist", "doctor" (and none above) → `"Discovery"`
8. default → `"Discovery"`

**Validation:** do NOT crash if the count != 50. Show the parsed count and the per-category breakdown,
warn if not exactly 50, and let the user proceed with whatever parsed (min 1) or re-paste.

### c) `save_queries_xlsx(rows) -> str`
Saves to `data/search_queries_50.xlsx` with:
- Auto-adjusted column widths
- Bold header row with light blue background fill (#DDEEFF)
- Freeze top row
- Columns: Rank, Search Query, Category, User Intent, Search Strength Score

After a successful parse + save, set `st.session_state["queries_ready"] = True` so the rest of the
pipeline unlocks.

---

## Step 2: Google Maps Data Collection — Free Scraping (modules/maps_collector.py)

**No API key.** Uses Playwright (headless Chromium) to scrape Google Maps search results — the same
source as the paid Places API, so the same data and accuracy, for free.

One-time setup (documented in README): `pip install playwright` then `playwright install chromium`.

For each of the 50 queries:
a) Open Google Maps search:
   `https://www.google.com/maps/search/{url-encoded "{search_query} Guntur"}` with locale en-IN.
   - Handle the consent / cookie interstitial if present (click reject/accept).
   - Wait for the results feed (`role="feed"`) to load.
b) Scroll the results panel to lazy-load up to 15 listings (Google loads ~10–20 at a time on scroll).
c) For each of the top 15 listings extract:
   - `name`
   - `rating` (float or None)
   - `user_ratings_total` (int or None)
   - `types` (category label shown, e.g. "Dermatologist", "Skin care clinic")
   - `formatted_address`
   - `formatted_phone_number` (open the listing's detail panel if needed; else None)
   - `website` (or None)
   - `opening_hours` / open-now status (if shown)
   - `business_status` — derive: "Permanently closed"/"Temporarily closed" labels → CLOSED variants;
     otherwise "OPERATIONAL"
   - `price_level` (rarely shown for clinics; default None)
   - `lat`, `lng` (parse from the listing URL)
   - `place_url` — the Google Maps URL (stable unique key)
   - `place_id` / CID (parse from the URL when available)
d) Assemble a row with all of the above PLUS:
   - `source_query_rank` (from Step 1)
   - `source_query` (the query string)
   - `source_category` (derived category from Step 1)
   - `result_position` (1 to 15)
   - `fetched_at` (ISO timestamp)

**Dedup optimization:** cache each clinic's full detail by `place_url`/CID. If the same clinic appears
across multiple queries, reuse the cached detail instead of re-opening the panel — large speed-up, same data.

**Free fallback (config `USE_OSM_FALLBACK`):**
- If a clinic is missing lat/lng, geocode its address with OpenStreetMap **Nominatim** (keyless, free)
  for the map chart.
- If Google Maps scraping is blocked/unavailable entirely, optionally fall back to OSM **Overpass** for a
  basic clinic list (note: OSM has no ratings/reviews — those columns will be None).

Error handling:
- Randomized polite delay (`SCRAPER_MIN_DELAY_S`–`SCRAPER_MAX_DELAY_S`) between listings/queries.
- Exponential backoff (2s, 4s, 8s — max 3 retries) on timeouts / soft-blocks.
- On persistent failure for a listing, insert a row with `status="FETCH_FAILED"`.
- Cache raw scraped JSON in `.cache/maps_raw.json` keyed by query (and place) so re-runs skip done work.
- **Mock/sample-data mode:** always provide a `collect(mock=True)` path that loads bundled/generated
  sample rows, so the dashboard and analytics are fully demoable without scraping.

Show in Streamlit:
- `st.progress()` bar with "Scraping query 12/50: best skin doctor Guntur…"
- **Estimated time preview** (not cost — it's free): "This will scrape ~50 queries (~X–Y minutes) using a
  background browser."
- Confirmation dialog: "This will open a headless browser and scrape ~50 Google Maps searches
  (~X–Y minutes). Continue?"

Save to `data/google_maps_results_50.xlsx`:
- Up to 750 rows (50 queries × 15 results)
- Freeze header row
- Alternating row fill (white / light gray)
- All collected columns

---

## Step 3: Analytics Engine (modules/analytics.py)

Build these charts using Plotly Express / Plotly Graph Objects / Altair.
All charts: consistent colour scheme (blues/teals for positive, reds/oranges for negative/gaps).
Each chart function returns a Plotly figure or Altair chart.

> Notes for the free-data version:
> - `category` comes from the **derived** query category (Step 1) — category-based charts are unchanged.
> - Some scraped clinics may have missing `rating`/`user_ratings_total` — every chart must drop/handle
>   NaN gracefully. Missing rating/reviews is itself a vulnerability signal (on-theme).
> - `price_level` is usually None (no current chart depends on it).

MARKET OVERVIEW GROUP:

1. Donut chart — query category distribution (% of 50 queries per category)
2. Horizontal bar — top 15 most-appeared clinics across all 50 queries (x=appearance count)
3. 4 KPI metric cards: total unique clinics, avg rating, median review count, % with website

RATINGS & REVIEWS GROUP:
4. Scatter — rating (x) vs. user_ratings_total (y), bubble size = appearance count,
   colour = category, hover = clinic name + address
5. Histogram — distribution of ratings (0–5) with mean line
6. Box plot — review count distribution by query category
7. Heatmap — clinic (y) vs. query category (x), value = number of appearances

PRESENCE & VISIBILITY GROUP:
8. Ranked horizontal bar — all clinics sorted by total appearances (top 20)
9. Stacked bar — website presence vs. no website per query category
10. Treemap — clinics sized by review volume, coloured by rating tier
11. Map scatter (Plotly scatter_mapbox with open-street-map tile, no Mapbox token) — pin per unique clinic,
    colour = rating (red <3, yellow 3–4, green >4), hover = name + rating + reviews

COMPETITIVE GAPS GROUP:
12. Quadrant scatter — x=appearances, y=rating; draw quadrant lines at median x and 3.5 y.
    Label quadrant zones: "Stars" (high appear, high rating), "Hidden Gems" (low appear,
    high rating), "Vulnerable" (high appear, low rating), "Off-Radar" (low, low)
13. Bar — clinics with 0 website sorted by appearances descending (top 15 shown)
14. Funnel — "Online Presence Completeness": step 1=all clinics, step 2=has phone,
    step 3=has website, step 4=rating>4, step 5=reviews>50

---

## Step 4: Vulnerability Scoring (modules/vulnerability.py)

Compute a Vulnerability Score (0–100) for each unique clinic using this formula:

score = 0
if website is None or website == "":   score += 30
if rating < 3.5 or rating is None:    score += 20
if user_ratings_total < 20:           score += 15
if result_position_avg > 8:           score += 10  # appears late in results
if appearances_in_results < 5:        score += 15  # low demand visibility
if formatted_phone_number is None:    score += 10
if business_status != "OPERATIONAL":  score += 5

# Cap at 100

Add columns:

- `vulnerability_score` (int 0–100)
- `vulnerability_label`:
  - 80–100 → "Critical" (color: #DC2626)
  - 60–79 → "High" (color: #EA580C)
  - 40–59 → "Medium" (color: #CA8A04)
  - 0–39  → "Low"    (color: #16A34A)
- `opportunity_notes` — **generated locally via templates (no API).**
  `build_opportunity_note(clinic)` composes one fluent sentence from whichever vulnerability factors
  fired, e.g.:
  - no website → "…has no website…"
  - low/missing rating → "…a {rating or 'missing'} rating…"
  - few reviews → "…only {reviews} reviews…"
  - low appearances → "…appears in just {n} of 50 searches…"
  - no phone → "…no listed phone number…"
  Ending with an opportunity framing, e.g.:
  "{Clinic} has no website and only 12 reviews despite appearing in 9 of 50 searches — a clear
  opportunity to capture untapped local demand with a basic digital-presence upgrade."
  Deterministic, free, no paste needed.
  (Optional enhancement: the user MAY paste AI-written notes via the same paste pattern as Step 1,
  but the default is the local template.)

Select top 10 by `vulnerability_score` (descending).
Save to `data/vulnerable_10.xlsx`:

- Columns: Rank, Clinic Name, Address, Phone, Rating, Reviews, Website,
  Total Appearances, Vulnerability Score, Label, Opportunity Notes, Google Maps URL
- Conditional formatting on Vulnerability Score: red gradient
- Clinic Name column hyperlinked to the Google Maps URL (`place_url`)
- Bold header, freeze row 1

---

## Step 5: Streamlit UI (app.py + components/)

### Global Layout

st.set_page_config(page_title="Derma Intel — Guntur", layout="wide",
page_icon="🔬", initial_sidebar_state="expanded")

### Sidebar

- App title + tagline
- **Data Status panel** (replaces the old API-key status — there are no keys):
  ✓/✗ dots for (a) Queries loaded, (b) Maps data collected, (c) Vulnerability computed
- "▶ Run Pipeline" button — runs scrape → analytics → scoring in sequence with progress
  (disabled until queries are loaded)
- "⟳ Re-run" checkbox (warns before overwriting)
- Last run timestamp (loaded from metadata.json)
- Divider
- Quick stats: total clinics, unique clinics, queries run, vulnerable identified

### Tab 1 — Query Setup & Top 50 (components/tab_queries.py)

**State A — no queries yet (Step 1 setup):**
- Heading "Step 1 — Generate your 50 queries (free, manual)"
- Instructions: "Copy the prompt below → paste it into any free AI tool (ChatGPT, Claude, Gemini,
  Perplexity, Copilot) → copy its answer → paste it in the box → click Parse."
- `st.code(build_ai_prompt())` (built-in copy button)
- `st.text_area` labelled "Paste the AI's 50 queries here ('abc', 'xyz', …)"
- "Parse & Save Queries" button → parse, show parsed count + per-category breakdown, save xlsx,
  set `queries_ready`, toast success

**State B — queries exist:**
- Top: small donut chart (category breakdown) in a right-aligned col
- Filter row: multiselect for category, text search box, sort by rank/score
- Display using `st.dataframe` with `column_config`:
  - rank: `st.column_config.NumberColumn` width=60
  - search_query: `st.column_config.TextColumn` width=280
  - category: `st.column_config.SelectboxColumn` (colour-coded via CSS injection)
  - user_intent: `st.column_config.TextColumn` (truncated, expandable)
  - search_strength_score: `st.column_config.ProgressColumn` (0–10)
- Export button: `st.download_button` for the xlsx
- "↻ Replace queries" expander to paste a fresh set

### Tab 2 — Maps Results (components/tab_results.py)

Three-panel layout using st.columns([1, 2, 1.5]):

LEFT PANEL — Query List:
- Scrollable list of 50 queries with result count badge
- Clicking a query sets `st.session_state["selected_query"]`

CENTRE PANEL — Clinic Cards (max 15 per query):
- For each result: card showing:
    - Clinic name (bold), position badge (#1 in green, #10+ in gray)
    - ★ {rating} ({review_count} reviews)
    - Website: 🌐 linked (green) or "No website" (gray)
    - Phone: 📞 or "No phone" (gray)
- Each card is clickable: sets `st.session_state["selected_clinic"]`
- Global search bar above cards

RIGHT PANEL — Clinic Detail:
- Full name, address, phone, rating, reviews, hours, business_status
- Website link (if exists)
- Google Maps link button (`place_url`)
- "Appeared in X queries" with expandable list of those queries
- Vulnerability pre-score badge (colour-coded)

### Tab 3 — Analytics (components/tab_analytics.py)

Render all 14 charts from analytics.py.
Layout:
st.header("📊 Market Intelligence Dashboard")

st.subheader("Market Overview")
col1, col2, col3, col4 = st.columns(4)  # KPI cards
col_left, col_right = st.columns(2)     # donut + bar

st.subheader("Ratings & Reviews")
st.plotly_chart(scatter_chart, use_container_width=True)
col_left, col_right = st.columns(2)     # histogram + box plot
st.altair_chart(heatmap, use_container_width=True)

st.subheader("Presence & Visibility")
col_left, col_right = st.columns(2)     # ranked bar + stacked bar
st.plotly_chart(treemap, use_container_width=True)
st.plotly_chart(map_chart, use_container_width=True)

st.subheader("Competitive Gaps")
st.plotly_chart(quadrant_scatter, use_container_width=True)
col_left, col_right = st.columns(2)     # no-website bar + funnel

Each chart: st.caption("💡 Insight: [one-line takeaway]") below the chart.
Add a small PNG download button per chart using fig.to_image() (kaleido).

### Tab 4 — Vulnerable 10 (components/tab_vulnerable.py)

st.header("🚨 Top 10 Clinics That Need Your Help Most")

**Overview narrative — generated locally (no API):** a computed paragraph from aggregates, e.g.
"Of {N} unique clinics analysed, {k} show critical gaps: {a} lack a website, {b} have under 20 reviews,
{c} have no phone listed. The 10 below represent the highest-opportunity targets."

For each of the 10 clinics, render a card (use st.container with a border):
Row 1: [Clinic Name (large)] ........... [Score badge: e.g. "87 / Critical" in red]
Row 2: 📍 Address | 📞 Phone
Row 3: ★ {rating} ({reviews} reviews) | 🌐 {website or "No website"}
Row 4: Vulnerability gauge bar (Plotly indicator or CSS progress bar)
Row 5: 💡 "{opportunity_notes}" (italic, muted text)
Row 6: [🔗 View on Google Maps] button

At the bottom:
col1, col2 = st.columns(2)
col1: "📥 Download Excel" (download_button for xlsx)
col2: "📄 Export PDF Brief" (generates one-page PDF using fpdf2 and serves as download)

---

## Error Handling & Quality Requirements

- All scraping/parsing/IO: try/except with st.error() messages and st.toast() notifications
- No API keys anywhere — nothing to leak, no `.env` checks
- Long operations: show st.progress() + st.status() context manager
- DataFrames: validate before export — no NaN in name/address columns; fill others with defaults
- Charts: handle empty DataFrame gracefully — show st.info("No data yet — run the pipeline")
- Excel files: must open cleanly in Excel and Google Sheets (no merged cells in data area)
- Caching: use @st.cache_data decorators on all data-loading functions
- On first run: if data/*.xlsx exist, load from disk without scraping
- Scraper must degrade gracefully and offer a mock/sample-data mode so the UI always works
- README.md: setup (incl. `playwright install chromium`), how to paste the queries, one-line launch command

## Deliverables Checklist

- [ ] app.py — main Streamlit entry point
- [ ] config.py — all constants + scraper settings (no keys)
- [ ] requirements.txt — pinned deps (streamlit, pandas, openpyxl, plotly, altair, kaleido,
      playwright, fpdf2, requests)
- [ ] README.md — setup + launch guide (no keys; includes `playwright install chromium` + paste-queries steps)
- [ ] modules/query_generator.py  (build prompt + parse pasted queries + save xlsx)
- [ ] modules/maps_collector.py    (Playwright Google Maps scraper + OSM fallback + mock mode)
- [ ] modules/analytics.py
- [ ] modules/vulnerability.py     (scoring + local template opportunity notes + top 10 export)
- [ ] components/tab_queries.py    (paste workflow + 50-query table)
- [ ] components/tab_results.py
- [ ] components/tab_analytics.py
- [ ] components/tab_vulnerable.py
- [ ] data/ directory with placeholder .gitkeep
- [ ] .cache/ directory with placeholder .gitkeep

Start by creating the project structure and requirements.txt, then build module by module.
Test each module independently before wiring into the Streamlit app. No API keys are required at any step.
