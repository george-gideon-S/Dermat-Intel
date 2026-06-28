# Derma Intel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a free (no API keys) Streamlit dermatologist market-intelligence dashboard for Guntur, India — manual-AI-paste query generation, free Google Maps scraping, 14 analytics charts, a 0–100 Vulnerability Index, and Excel/PDF exports.

**Architecture:** Layered pipeline with one-way data flow: `query_generator` (parse pasted queries) → `maps_collector` (Playwright scrape, cached) → `vulnerability` (score) / `analytics` (charts) → Streamlit `app.py` + 4 tab components. Pure logic is isolated from I/O and browser-driving so it can be unit-tested; the scraper is thin over testable extraction helpers and always has a deterministic mock mode.

**Tech Stack:** Python 3.10, Streamlit, pandas, openpyxl, Plotly, Altair, kaleido, Playwright (Chromium), fpdf2, requests, pytest.

---

## Build Notes (read first)

- **Project root** = the current working directory `E:\TRINADE\Dermat Analytics and Websites\`. All paths below are relative to it. (The spec's `derma-intel/` is conceptual; we do not nest.)
- **Git**: local repo, local commits only as checkpoints. Never push.
- **Run the app:** `streamlit run app.py`
- **Run tests:** `python -m pytest -q`
- **Data contract (the dict every layer passes around).** A *query row*:
  `{rank:int, search_query:str, category:str, user_intent:str, search_strength_score:int}`.
  A *result row* (one clinic appearance) has these keys exactly:
  `name, rating, user_ratings_total, types, formatted_address, formatted_phone_number, website,
  opening_hours, business_status, price_level, lat, lng, place_url, place_id,
  source_query_rank, source_query, source_category, result_position, fetched_at, status`.
  Missing values are `None` (numbers) or `""` (strings); `status` is `"OK"` or `"FETCH_FAILED"`.
- **Categories (canonical 7):** `Discovery, Comparison, Trust & Social Proof, Pricing, Condition-Based,
  Appointment & Booking, Near Me / Local`.
- **Spec reference:** `Claude Code Prompt.md` holds the exact UI layouts and chart list. Tasks that
  assemble verbose UI/charts cite spec sections rather than duplicating them; this is intentional, the
  spec is the approved detailed design.

> **Spec correction applied in this plan (Task 2):** the "Near Me / Local" keyword rule must NOT include
> the city name (`"in guntur"`), because every query mentions Guntur and would wrongly collapse into that
> category. Near-Me triggers only on explicit proximity words (`near me`, `nearby`, `around me`, etc.).

---

## File Structure

| File | Responsibility |
|---|---|
| `config.py` | Constants + scraper settings (no keys) |
| `requirements.txt` | Pinned deps |
| `modules/query_generator.py` | Build AI prompt, parse pasted queries, derive metadata, save xlsx |
| `modules/maps_collector.py` | Result-row model, mock mode, dedup key, listing extraction, Playwright scrape, OSM geocode, save xlsx |
| `modules/vulnerability.py` | Score, label, opportunity note, top-10 select, save xlsx |
| `modules/analytics.py` | Data-prep helpers + 14 chart builders |
| `components/tab_queries.py` | Tab 1: paste workflow + table |
| `components/tab_results.py` | Tab 2: 3-panel results browser |
| `components/tab_analytics.py` | Tab 3: render 14 charts |
| `components/tab_vulnerable.py` | Tab 4: 10 cards + Excel/PDF export |
| `app.py` | Page config, sidebar, pipeline runner, tab wiring |
| `tests/` | pytest suites mirroring `modules/` + AppTest smoke tests |
| `data/`, `.cache/` | outputs + cache (`.gitkeep`) |
| `README.md` | setup (incl. `playwright install chromium`) + launch |

---

## Task 0: Scaffolding

**Files:**
- Create: `config.py`, `requirements.txt`, `.gitignore`, `data/.gitkeep`, `.cache/.gitkeep`,
  `modules/__init__.py`, `components/__init__.py`, `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Init git + dirs**

```bash
cd "E:/TRINADE/Dermat Analytics and Websites"
git init
mkdir -p modules components tests data .cache
```

- [ ] **Step 2: Write `requirements.txt`** (Python 3.10 compatible; bump if an install fails)

```
streamlit==1.41.1
pandas==2.2.3
openpyxl==3.1.5
plotly==5.24.1
altair==5.5.0
kaleido==0.2.1
playwright==1.49.1
fpdf2==2.8.2
requests==2.32.3
pytest==8.3.4
```

- [ ] **Step 3: Write `config.py`** — exactly the constants from the spec's Config section (TARGET_CITY,
  TARGET_LOCATION_LATLNG, SPECIALTY, NUM_QUERIES=50, RESULTS_PER_QUERY=15, MAPS_RADIUS_M=15000,
  CACHE_DIR, DATA_DIR, and the SCRAPER_* settings + USE_OSM_FALLBACK + SCRAPER_LOCALE + SCRAPER_USER_AGENT).
  Add helper `CATEGORIES = [...7...]` and `CATEGORY_COLORS = {category: hex}` for colour-coding.

- [ ] **Step 4: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.cache/*.json
data/*.xlsx
.pytest_cache/
```

- [ ] **Step 5: `.gitkeep` files + empty `__init__.py` + `tests/conftest.py`** (conftest adds repo root to
  `sys.path` so `import modules...` works).

- [ ] **Step 6: Install + verify**

Run: `python -m pip install -r requirements.txt` then `python -m playwright install chromium`
Then: `python -c "import streamlit, pandas, plotly, altair, openpyxl, fpdf, playwright, kaleido; print('ok')"`
Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "chore: scaffold derma-intel project (config, deps, dirs)"
```

---

## Task 1: query_generator — `build_ai_prompt()`

**Files:** Create `modules/query_generator.py`; Test `tests/test_query_generator.py`

- [ ] **Step 1: Failing test**

```python
from modules.query_generator import build_ai_prompt

def test_prompt_demands_50_and_format():
    p = build_ai_prompt()
    assert "exactly 50" in p.lower()
    assert "comma-separated" in p.lower()
    assert "'best dermatologist in Guntur'" in p   # format example present
    assert "Guntur" in p
```

- [ ] **Step 2: Run → FAIL** — `python -m pytest tests/test_query_generator.py::test_prompt_demands_50_and_format -v` (ImportError/AttributeError)

- [ ] **Step 3: Implement** `build_ai_prompt()` returning the exact prompt text from spec Step 1(a).

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit** `git add -A && git commit -m "feat: query_generator.build_ai_prompt"`

---

## Task 2: query_generator — parse + derive metadata

**Files:** Modify `modules/query_generator.py`; Test `tests/test_query_generator.py`

Interfaces:
`parse_pasted_queries(text:str) -> list[dict]`, `derive_category(q:str) -> str`,
`derive_intent(category:str) -> str`, `derive_strength(rank:int, category:str, n_total:int) -> int`.

- [ ] **Step 1: Failing tests** (covers quotes, numbering, brackets, dedup, and category rules)

```python
import pytest
from modules.query_generator import parse_pasted_queries, derive_category

def test_parse_simple_single_quotes():
    rows = parse_pasted_queries("'best dermatologist in Guntur', 'skin specialist near me'")
    assert [r["search_query"] for r in rows] == ["best dermatologist in Guntur", "skin specialist near me"]
    assert rows[0]["rank"] == 1 and rows[1]["rank"] == 2

def test_parse_double_quotes_newlines_numbering_brackets():
    raw = '[\n 1. "acne treatment doctor Guntur",\n 2. "dermatologist fees Guntur"\n]'
    rows = parse_pasted_queries(raw)
    assert [r["search_query"] for r in rows] == ["acne treatment doctor Guntur", "dermatologist fees Guntur"]

def test_parse_dedup_case_insensitive_and_empties():
    rows = parse_pasted_queries("'a clinic', 'A Clinic', '', '  '")
    assert [r["search_query"] for r in rows] == ["a clinic"]

@pytest.mark.parametrize("q,cat", [
    ("acne treatment doctor Guntur", "Condition-Based"),
    ("hair fall specialist Guntur", "Condition-Based"),
    ("dermatologist fees in Guntur", "Pricing"),
    ("best rated skin doctor reviews Guntur", "Trust & Social Proof"),
    ("book dermatologist appointment Guntur", "Appointment & Booking"),
    ("dermatologist vs cosmetologist Guntur", "Comparison"),
    ("skin specialist near me", "Near Me / Local"),
    ("best dermatologist in Guntur", "Discovery"),      # city name must NOT trigger Near-Me
])
def test_derive_category(q, cat):
    assert derive_category(q) == cat

def test_all_rows_have_five_fields():
    rows = parse_pasted_queries("'best dermatologist in Guntur'")
    assert set(rows[0]) == {"rank","search_query","category","user_intent","search_strength_score"}
    assert 1 <= rows[0]["search_strength_score"] <= 10
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
import re

_QUOTED = re.compile(r"""['"]([^'"]+)['"]""")

_CATEGORY_RULES = [   # (compiled keyword regex, category) — first match wins, order matters
    (r"\b(acne|pimple|hair fall|hair loss|dandruff|eczema|psoriasis|fungal|rash|"
     r"skin allergy|allergy|pigmentation|melasma|wart|mole|vitiligo|scar)\b", "Condition-Based"),
    (r"\b(fee|fees|cost|price|charges|cheap|affordable)\b|₹", "Pricing"),
    (r"\b(review|reviews|rating|ratings|best rated|top rated|feedback)\b", "Trust & Social Proof"),
    (r"\b(appointment|book|booking|consult|consultation)\b", "Appointment & Booking"),
    (r"\b(vs|versus|compare|comparison|better|or)\b", "Comparison"),
    (r"\b(near me|nearby|near by|around me|closest|close to me|in my area)\b", "Near Me / Local"),
    (r"\b(best|top|good|famous|leading|specialist|doctor|dermatologist)\b", "Discovery"),
]

def derive_category(q: str) -> str:
    ql = q.lower()
    for pattern, cat in _CATEGORY_RULES:
        if re.search(pattern, ql):
            return cat
    return "Discovery"

_INTENT = {
    "Discovery": "Wants to discover the leading dermatologists in Guntur.",
    "Comparison": "Is comparing dermatologists to pick the best option.",
    "Trust & Social Proof": "Is checking ratings and reviews before trusting a clinic.",
    "Pricing": "Wants to know consultation fees / treatment costs.",
    "Condition-Based": "Is searching for treatment of a specific skin/hair condition.",
    "Appointment & Booking": "Is ready to book or consult a dermatologist.",
    "Near Me / Local": "Wants a dermatologist physically close to them.",
}

def derive_intent(category: str) -> str:
    return _INTENT.get(category, _INTENT["Discovery"])

_CAT_WEIGHT = {"Discovery":2,"Near Me / Local":2,"Trust & Social Proof":1,
               "Appointment & Booking":1,"Pricing":1,"Comparison":0,"Condition-Based":1}

def derive_strength(rank: int, category: str, n_total: int) -> int:
    base = round(10 - 9 * (rank - 1) / max(1, n_total - 1))   # rank 1 -> ~10, last -> ~1
    return max(1, min(10, base + _CAT_WEIGHT.get(category, 0) - 1))

def parse_pasted_queries(text: str) -> list[dict]:
    if not text:
        return []
    candidates = _QUOTED.findall(text)
    if not candidates:                          # fallback: split on commas/newlines if no quotes
        candidates = re.split(r"[,\n]+", text)
    seen, cleaned = set(), []
    for c in candidates:
        s = re.sub(r"^\s*\d+[.)]\s*", "", c).strip().strip("[]").strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key); cleaned.append(s)
    n = len(cleaned)
    rows = []
    for i, q in enumerate(cleaned, start=1):
        cat = derive_category(q)
        rows.append({"rank": i, "search_query": q, "category": cat,
                     "user_intent": derive_intent(cat),
                     "search_strength_score": derive_strength(i, cat, n)})
    return rows
```

- [ ] **Step 4: Run → PASS** (`python -m pytest tests/test_query_generator.py -v`)

- [ ] **Step 5: Commit** `git commit -am "feat: robust query parse + category/intent/score derivation"`

---

## Task 3: query_generator — `save_queries_xlsx`

**Files:** Modify `modules/query_generator.py`; Test `tests/test_query_generator.py`

`save_queries_xlsx(rows:list[dict], path:str|None=None) -> str` writes the formatted workbook.

- [ ] **Step 1: Failing test**

```python
import openpyxl
from modules.query_generator import parse_pasted_queries, save_queries_xlsx

def test_save_xlsx(tmp_path):
    rows = parse_pasted_queries("'best dermatologist in Guntur', 'acne treatment Guntur'")
    out = save_queries_xlsx(rows, str(tmp_path/"q.xlsx"))
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    assert [c.value for c in ws[1]] == ["Rank","Search Query","Category","User Intent","Search Strength Score"]
    assert ws[1][0].font.bold is True
    assert ws.freeze_panes == "A2"
    assert ws.max_row == 3   # header + 2 rows
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement** using openpyxl: write header row (bold, `PatternFill("solid", fgColor="DDEEFF")`),
  data rows, auto-width (max cell len per column, capped ~60), `ws.freeze_panes="A2"`. Ensure parent dir
  exists. Default path `data/search_queries_50.xlsx`.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit** `git commit -am "feat: save_queries_50.xlsx with formatting"`

---

## Task 4: maps_collector — model, mock mode, dedup key, listing extraction

**Files:** Create `modules/maps_collector.py`; Test `tests/test_maps_collector.py`, fixture
`tests/fixtures/listing_sample.json` (a captured listing's raw fields)

Interfaces: `RESULT_COLUMNS:list[str]`, `empty_result_row()->dict`, `make_mock_results(queries)->list[dict]`,
`dedup_key(place_url:str)->str`, `parse_listing(raw:dict, query_row:dict, position:int)->dict`.

- [ ] **Step 1: Failing tests**

```python
from modules.maps_collector import (RESULT_COLUMNS, make_mock_results, dedup_key, parse_listing)

QROWS = [{"rank":1,"search_query":"best dermatologist in Guntur","category":"Discovery",
          "user_intent":"x","search_strength_score":10}]

def test_mock_results_shape():
    rows = make_mock_results(QROWS, per_query=15)
    assert len(rows) == 15
    assert set(RESULT_COLUMNS).issubset(rows[0].keys())
    assert rows[0]["source_query"] == "best dermatologist in Guntur"
    assert rows[0]["result_position"] == 1

def test_dedup_key_from_cid_url():
    u = "https://www.google.com/maps/place/?q=place_id:ChIJabc&cid=12345"
    assert dedup_key(u) == "12345" or "ChIJabc" in dedup_key(u)

def test_parse_listing_maps_fields():
    raw = {"name":"Skin Clinic","rating":4.6,"reviews":120,"address":"MG Road, Guntur",
            "phone":"+91 90000 11111","website":"http://x.com","types":"Dermatologist",
            "lat":16.30,"lng":80.43,"url":"https://www.google.com/maps/place/?cid=99",
            "closed":False}
    row = parse_listing(raw, QROWS[0], position=3)
    assert row["name"]=="Skin Clinic" and row["rating"]==4.6 and row["user_ratings_total"]==120
    assert row["result_position"]==3 and row["source_query_rank"]==1
    assert row["business_status"]=="OPERATIONAL" and row["status"]=="OK"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement** the model + pure helpers. `RESULT_COLUMNS` = the 20-key contract from Build Notes.
  `empty_result_row()` returns all keys with None/"" defaults. `make_mock_results` fabricates deterministic
  varied rows (some missing website/phone/low rating) for demos/tests. `dedup_key` extracts `cid=` or
  `place_id:` from the URL (fallback: the URL itself). `parse_listing` maps raw scrape fields → the contract,
  sets `fetched_at = datetime.now().isoformat()`, `business_status` from the `closed` flag,
  `source_*`/`result_position` from args, `status="OK"`. No browser here.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit** `git commit -am "feat: maps_collector model + mock + listing parse (pure, tested)"`

---

## Task 5: maps_collector — Playwright scrape + OSM geocode + cache

**Files:** Modify `modules/maps_collector.py`; Test `tests/test_maps_collector.py` (cache + geocode mocked)

Interfaces:
`geocode_osm(address:str)->tuple[float,float]|None`,
`scrape_query(page, query_row, max_results, cache)->list[dict]`,
`collect(query_rows, mock=False, progress_cb=None)->list[dict]`.

- [ ] **Step 1: Failing tests** (no network)

```python
import json
from modules import maps_collector as mc

def test_geocode_osm_parses(monkeypatch):
    class R:
        status_code=200
        def json(self): return [{"lat":"16.31","lon":"80.44"}]
    monkeypatch.setattr(mc.requests, "get", lambda *a, **k: R())
    assert mc.geocode_osm("MG Road, Guntur") == (16.31, 80.44)

def test_collect_mock_does_not_touch_network(monkeypatch):
    monkeypatch.setattr(mc, "_run_browser", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no net")))
    rows = mc.collect([{"rank":1,"search_query":"q","category":"Discovery",
                        "user_intent":"x","search_strength_score":9}], mock=True)
    assert len(rows) == 15 and rows[0]["status"]=="OK"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**
  - `geocode_osm`: GET `https://nominatim.openstreetmap.org/search?q=...&format=json&limit=1` with a UA
    header; return (lat,lng) or None; swallow errors.
  - `_run_browser(...)`: opens Playwright Chromium (`SCRAPER_HEADLESS`, UA, locale), navigates to
    `https://www.google.com/maps/search/<urlencoded "{query} Guntur">`, dismisses consent, scrolls the
    `[role=feed]` panel until ≥`max_results` cards or no growth, extracts each card's fields (name, rating,
    reviews, types, address, phone via detail panel, website, closed label, href→lat/lng/cid). Polite
    randomized delay (`SCRAPER_MIN/MAX_DELAY_S`), exponential backoff (2/4/8s, max `SCRAPER_MAX_RETRIES`)
    on timeout. Returns list of `raw` dicts.
  - `scrape_query`: checks `cache` (keyed by query) first; else calls `_run_browser`, maps each raw via
    `parse_listing`, dedups by `dedup_key` reusing cached detail, fills missing lat/lng via `geocode_osm`
    when `USE_OSM_FALLBACK`, writes cache. On persistent failure append one `empty_result_row()` with
    `status="FETCH_FAILED"`.
  - `collect`: loads `.cache/maps_raw.json`; if `mock` → `make_mock_results` per query; else loops queries
    calling `scrape_query`, invoking `progress_cb(i, n, query)`; persists cache; returns all rows.
  - Browser-driving (`_run_browser`) is verified manually in Task 16, not unit-tested.

- [ ] **Step 4: Run → PASS** (mock + geocode tests)

- [ ] **Step 5: Commit** `git commit -am "feat: Playwright Google Maps scraper + OSM fallback + caching"`

---

## Task 6: maps_collector — `save_results_xlsx`

**Files:** Modify `modules/maps_collector.py`; Test `tests/test_maps_collector.py`

- [ ] **Step 1: Failing test** — build rows via `make_mock_results`, save, reload with openpyxl, assert header
  frozen (`A2`), row count = data+1, alternating fill present on row 3 vs row 2, all `RESULT_COLUMNS` present.

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement** `save_results_xlsx(rows, path="data/google_maps_results_50.xlsx")` — header bold,
  freeze `A2`, alternating row fill (white / `F3F4F6`), columns in `RESULT_COLUMNS` order.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit** `git commit -am "feat: save google_maps_results_50.xlsx"`

---

## Task 7: vulnerability — score, label, opportunity note

**Files:** Create `modules/vulnerability.py`; Test `tests/test_vulnerability.py`

Interfaces: `compute_score(c:dict)->int`, `label_for(score:int)->tuple[str,str]`,
`build_opportunity_note(c:dict)->str`. `c` is an aggregated unique-clinic dict with keys
`name, website, rating, user_ratings_total, result_position_avg, appearances,
formatted_phone_number, business_status`.

- [ ] **Step 1: Failing tests** (each formula branch + boundaries)

```python
from modules.vulnerability import compute_score, label_for, build_opportunity_note

BASE = {"name":"X","website":"http://x","rating":4.8,"user_ratings_total":200,
        "result_position_avg":2,"appearances":10,"formatted_phone_number":"+91","business_status":"OPERATIONAL"}

def test_score_zero_for_strong_clinic():
    assert compute_score(BASE) == 0

def test_score_accumulates_and_caps():
    c = {**BASE, "website":"", "rating":2.0, "user_ratings_total":5, "result_position_avg":9,
         "appearances":2, "formatted_phone_number":None, "business_status":"CLOSED"}
    assert compute_score(c) == 100   # 30+20+15+10+15+10+5=105 -> cap 100

def test_label_boundaries():
    assert label_for(80)[0]=="Critical"
    assert label_for(79)[0]=="High"
    assert label_for(60)[0]=="High"
    assert label_for(59)[0]=="Medium"
    assert label_for(40)[0]=="Medium"
    assert label_for(39)[0]=="Low"

def test_note_mentions_fired_factors():
    c = {**BASE, "website":"", "user_ratings_total":8, "appearances":3}
    note = build_opportunity_note(c)
    assert "website" in note.lower() and "8" in note and "3" in note
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement** `compute_score` exactly per spec formula (None-safe), `min(score,100)`.
  `label_for`: 80–100 Critical `#DC2626`, 60–79 High `#EA580C`, 40–59 Medium `#CA8A04`, 0–39 Low `#16A34A`.
  `build_opportunity_note`: collect clauses for each fired factor, join into one sentence ending with the
  opportunity framing from spec Step 4.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit** `git commit -am "feat: vulnerability score + label + opportunity note"`

---

## Task 8: vulnerability — aggregate uniques, select top 10, save xlsx

**Files:** Modify `modules/vulnerability.py`; Test `tests/test_vulnerability.py`

Interfaces: `aggregate_clinics(result_rows)->pandas.DataFrame` (one row per unique clinic with
appearances, result_position_avg, and first-seen detail), `score_clinics(df)->df` (adds
`vulnerability_score/label/label_color/opportunity_notes`), `top_n(df, n=10)->df`,
`save_vulnerable_xlsx(df, path="data/vulnerable_10.xlsx")->str`.

- [ ] **Step 1: Failing test** — feed `make_mock_results` rows; assert `aggregate_clinics` collapses
  duplicates by `dedup_key`/name, `score_clinics` adds the 4 columns, `top_n` returns ≤10 sorted desc by
  score; `save_vulnerable_xlsx` produces a workbook whose Clinic Name cells carry a hyperlink and Score
  column has fills, header frozen `A2`.

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement.** Aggregate via pandas groupby on dedup key; `appearances=count`,
  `result_position_avg=mean(result_position)`; keep max rating / max reviews / any website / any phone.
  `save_vulnerable_xlsx` columns per spec Step 4, red gradient via per-cell `PatternFill` scaled by score,
  `ws.cell(...).hyperlink = place_url` on Clinic Name, bold header, freeze `A2`.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit** `git commit -am "feat: aggregate uniques + top-10 vulnerable export"`

---

## Task 9: analytics — data-prep helpers

**Files:** Create `modules/analytics.py`; Test `tests/test_analytics.py`

Pure helpers feeding the charts (so charts stay thin): `kpis(result_rows)->dict`
(`unique_clinics, avg_rating, median_reviews, pct_with_website`), `category_distribution(query_rows)->df`,
`appearance_counts(result_rows)->df`, `quadrant_frame(result_rows)->df` (per-clinic appearances+rating+zone),
`presence_funnel(result_rows)->list[tuple[str,int]]`.

- [ ] **Step 1: Failing tests** — with a small hand-built result set assert: `kpis` counts uniques and
  `pct_with_website` correctly; `appearance_counts` ranks the most-appeared clinic first; `quadrant_frame`
  assigns "Vulnerable" to a high-appearance low-rating clinic; `presence_funnel` is monotonically
  non-increasing.

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement** the helpers with pandas; NaN/empty-safe (`if df.empty: return ...`).

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit** `git commit -am "feat: analytics data-prep helpers (tested)"`

---

## Task 10: analytics — 14 chart builders

**Files:** Modify `modules/analytics.py`; Test `tests/test_analytics.py`

Each builder takes the relevant DataFrame and returns a Plotly figure / Altair chart. Build all 14 exactly
per spec Step 3 (donut, top-clinics bar, KPI values, rating-vs-reviews scatter, ratings histogram + mean
line, review box-by-category, clinic×category heatmap (Altair), ranked appearances bar, website stacked bar,
treemap, OSM `scatter_mapbox`, quadrant scatter with median/3.5 guide lines + zone labels, no-website bar,
presence funnel). Use `config.CATEGORY_COLORS`; blues/teals positive, reds/oranges gaps.

- [ ] **Step 1: Failing smoke test**

```python
import pandas as pd
from modules import analytics, maps_collector
QR = [{"rank":1,"search_query":"best dermatologist in Guntur","category":"Discovery","user_intent":"x","search_strength_score":10}]
ROWS = maps_collector.make_mock_results(QR, per_query=15)

def test_every_chart_builds_and_handles_empty():
    figs = analytics.build_all(QR, ROWS)        # dict name->figure
    assert len(figs) >= 12 and all(v is not None for v in figs.values())
    empty = analytics.build_all([], [])         # must not raise
    assert empty is not None
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement** each builder + a `build_all(query_rows, result_rows)->dict` that returns every
  figure keyed by name, each wrapped so an empty/NaN frame yields a placeholder figure instead of raising.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit** `git commit -am "feat: 14 analytics chart builders + build_all"`

---

## Task 11: components/tab_queries.py

**Files:** Create `components/tab_queries.py`; Test `tests/test_app_smoke.py`

`render(state)` implements spec Tab 1 State A (prompt `st.code` + paste `st.text_area` + Parse button →
`parse_pasted_queries`→`save_queries_xlsx`→set `queries_ready`) and State B (donut + filters + `st.dataframe`
with `column_config` + download). Pure data via `modules.query_generator`.

- [ ] **Step 1: Failing AppTest smoke** (shared file, see below) — assert app runs with no queries and Tab 1
  shows the prompt code block; then inject pasted text into the text_area, click Parse, assert
  `queries_ready` true and dataframe present.

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement** per spec. Colour-code category via small CSS inject + `SelectboxColumn`.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit** `git commit -am "feat: Tab 1 query setup + table"`

---

## Task 12: components/tab_results.py

**Files:** Create `components/tab_results.py`; Test `tests/test_app_smoke.py`

`render(state)` = spec Tab 2 three-panel `st.columns([1,2,1.5])`: query list (count badges, sets
`selected_query`), clinic cards (≤15, position badge, ★rating/reviews, website/phone chips, sets
`selected_clinic`), detail panel (full fields + maps button + "appeared in X queries" + vuln pre-score badge
via `vulnerability.compute_score`).

- [ ] **Step 1: Failing AppTest smoke** — with mock results loaded, Tab 2 renders without exception and shows
  ≥1 clinic card.
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Implement** per spec.
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit** `git commit -am "feat: Tab 2 maps results browser"`

---

## Task 13: components/tab_analytics.py

**Files:** Create `components/tab_analytics.py`; Test `tests/test_app_smoke.py`

`render(state)` lays out the 14 charts exactly per spec Step 3 layout, each with an insight `st.caption`
and a PNG download button (`fig.to_image(format="png")` via kaleido; wrap in try/except → hide button if
kaleido fails). Empty data → `st.info("No data yet — run the pipeline")`.

- [ ] **Step 1: Failing AppTest smoke** — Tab 3 with mock data renders, no exception.
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Implement** per spec.
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit** `git commit -am "feat: Tab 3 analytics dashboard"`

---

## Task 14: components/tab_vulnerable.py + PDF export

**Files:** Create `components/tab_vulnerable.py`; Test `tests/test_app_smoke.py`, `tests/test_pdf.py`

`render(state)` = spec Tab 4: computed overview paragraph (local, from aggregates), 10 bordered cards
(rows 1–6 incl. gauge + opportunity note + maps button), bottom Excel + PDF buttons.
`build_pdf_brief(top10_df)->bytes` via fpdf2.

- [ ] **Step 1: Failing tests** — `test_pdf`: `build_pdf_brief(df)` returns bytes starting with `b"%PDF"`;
  AppTest: Tab 4 renders 10 cards with mock data.
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Implement** — overview string from `vulnerability` aggregates; cards; `build_pdf_brief`
  one-page summary table.
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit** `git commit -am "feat: Tab 4 vulnerable-10 + PDF brief"`

---

## Task 15: app.py — page config, sidebar, pipeline, wiring

**Files:** Create `app.py`; Test `tests/test_app_smoke.py`

`app.py`: `st.set_page_config(...)` per spec; init `st.session_state`; load existing `data/*.xlsx` if present
(`@st.cache_data`); sidebar (Data Status dots, ▶ Run Pipeline → `maps_collector.collect`→`analytics`→
`vulnerability`, ⟳ Re-run warning, last-run from `metadata.json`, quick stats); 4 `st.tabs` calling each
`render`. Run Pipeline disabled until `queries_ready`. Offer a "Use mock data" toggle so the app is fully
demoable without scraping.

- [ ] **Step 1: Write the shared AppTest smoke harness** `tests/test_app_smoke.py`

```python
from streamlit.testing.v1 import AppTest

def test_app_boots_no_exception():
    at = AppTest.from_file("app.py", default_timeout=30).run()
    assert not at.exception

def test_pipeline_with_mock(monkeypatch):
    at = AppTest.from_file("app.py", default_timeout=60)
    at.session_state["use_mock"] = True
    at.run()
    assert not at.exception
```

- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Implement** `app.py` wiring per spec Step 5.
- [ ] **Step 4: Run → PASS** (`python -m pytest tests/test_app_smoke.py -v`)
- [ ] **Step 5: Commit** `git commit -am "feat: app.py sidebar + pipeline + tab wiring"`

---

## Task 16: README + full verification

**Files:** Create `README.md`

- [ ] **Step 1:** Write `README.md`: what it is, "no API keys", setup
  (`pip install -r requirements.txt`, `playwright install chromium`), how to generate queries (paste flow),
  one-line launch `streamlit run app.py`, mock-mode note.
- [ ] **Step 2: Full test run** — `python -m pytest -q` → all green.
- [ ] **Step 3: Manual app verify (mock)** — `streamlit run app.py`, paste a sample 50-query list, enable
  mock data, run pipeline, confirm all 4 tabs render, all 3 xlsx export, PDF downloads.
- [ ] **Step 4: Live scrape smoke (real)** — run pipeline on **2** queries (not 50) with mock off; confirm
  real clinics appear and `google_maps_results_50.xlsx` populates. (User runs the full 50 later.)
- [ ] **Step 5: Commit** `git commit -am "docs: README + final verification"`

---

## Self-Review (completed)

- **Spec coverage:** every spec section maps to a task — Step 1→Tasks 1–3 & 11; Step 2→Tasks 4–6 & 12;
  Step 3→Tasks 9–10 & 13; Step 4→Tasks 7–8 & 14; Step 5→Tasks 11–15; error-handling/quality woven into each
  (empty-safe charts, FETCH_FAILED rows, try/except, caching, load-from-disk); deliverables checklist→Tasks
  0 & 16.
- **Placeholder scan:** none — code provided for logic tasks; UI/chart tasks cite exact spec sections by
  design.
- **Type consistency:** the 20-key result-row contract and 5-key query-row contract are defined once
  (Build Notes) and reused; `dedup_key`, `compute_score`, `label_for`, `build_all`, `collect`, `render`
  names are stable across tasks.
- **Spec correction:** Near-Me category rule no longer matches the city name (fixed in Task 2).
