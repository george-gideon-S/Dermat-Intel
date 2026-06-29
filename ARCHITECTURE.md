# Architecture — Derma Intel

How the system is built and how data flows. See [CLAUDE.md](CLAUDE.md) for the quick reference and
[DESIGN.md](DESIGN.md) for the UI/scoring rationale.

## 1. High-level shape

```
                 (manual, free)                 (free Playwright)
  AI tool ──prompt──► you paste 50 queries ──► Google MAPS scrape ──► .cache/result_rows.json
                                                                        (≈750 rows → 34 clinics)
                                                                              │
  Google MAPS reviews ──► reviews_collector ──► reviews_nlp ──► .cache/reviews_nlp.json
                                                                              │
  Google WEB (headful) ──► web_collector ──► .cache/web_raw.json             │
                                                                              ▼
                                            modules/vulnerability.py  ── opportunity score (0–100)
                                                                              │
                         ┌────────────────────────────────────────────────────┴───────────┐
                         ▼                                                                  ▼
            web/build_web.py → dist/derma_intel.html                         app.py (Streamlit)
            (PRIMARY: self-contained, offline)                              (fallback / operations)
```

**One data layer, two front ends.** All intelligence lives in `modules/`; both UIs are thin presenters
over the same JSON/Excel outputs. Deleting `web/` doesn't affect Streamlit and vice-versa.

## 2. Layers

### Data layer (`modules/`) — pure logic, unit-tested
| Module | Responsibility | Key outputs |
|---|---|---|
| `query_generator` | Build the copy-paste AI prompt; parse pasted queries; derive category / intent / strength | `data/search_queries.xlsx`, query rows |
| `maps_collector` | Scrape Google **Maps** (Playwright, worker-thread, consent, dedup by CID, detail-panel enrichment, OSM geocode fallback); `mock=True` mode; **cross-query detail cache** | `result_rows.json`, `google_maps_results.xlsx` |
| `vulnerability` | Aggregate appearance rows → unique clinics (+`high_intent_share`); compute the opportunity score; labels; opportunity notes; 60/40 web blend | scored DataFrame, `vulnerable_10.xlsx` |
| `analytics` | KPIs + ECharts/Plotly-Altair chart builders (Streamlit) + tested data-prep helpers | figures, KPI dict |
| `reviews_collector` | Scrape **all** Google Maps reviews per clinic (resume-safe, throttle backoff, CID fallback) | `reviews_raw.json` |
| `reviews_nlp` | Free offline NLP (VADER): sentiment, themes, pain points, referral rate, recency | `reviews_nlp.json` |
| `web_collector` | Google **web** SERP (headful interactive, persistent profile) + match results to clinics | `web_raw.json` |
| `screenshot_slicer` | Pillow-tile the tall full-page SERP PNGs into legible overlapping tiles + manifest | `.cache/web_tiles/` |
| `web_screens` | **Screenshot** google-search dataset: reconcile→queries (by search-box text), clinic map, **owned/borrowed** web signal | `web_screens.json`, `google_search_results.xlsx` |
| `unify_results` | Merge Maps clinic view + screenshot web signal → per-clinic 40%-web input | `unified_results.xlsx` |
| `storage` | JSON state store + metadata | `.cache/*.json`, `metadata.json` |

### Presentation layer
- **Streamlit** (`app.py` + `components/`): sidebar (data status, Run Pipeline, mock toggle, stats) +
  4 tabs (Queries paste workflow, Results 3-panel browser, Analytics charts, Vulnerable-10 cards +
  Excel/PDF). The operational console: where you generate queries, run scrapes, and export.
- **Premium web** (`web/`): `build_web.py` calls the modules, assembles ONE `payload` JSON
  (KPIs, scored clinics, top-10, category mix, rating distribution, funnel, per-clinic review-NLP,
  web-relevance), and **inlines** CSS + base64 Geist fonts + ECharts + payload + `app.js` into a single
  `dist/derma_intel.html`. Opened via `file://` — no server, fully offline. `derma_web.py` = build+open.

### Orchestration (root CLIs)
- `run_pipeline.py` — load queries → `maps_collector.collect` → score → write all exports + JSON state.
  Resume-safe (cached queries skipped). `--mock` for instant sample data.
- `collect_extras.py` — `--reviews` (auto, resume-safe) and `--web` (headful, one-time CAPTCHA).
- `derma_web.py` — rebuild + open the premium dashboard.

## 3. Data flow & stores

1. **Queries**: paste AI output → `parse_pasted_queries` → `query_rows.json` + `search_queries.xlsx`.
2. **Maps**: `collect` opens each query on Maps, scrapes ≤15 listings, enriches via the place panel
   (clean phone/website/address from stable `data-item-id` attrs), dedups by CID, caches raw per query
   (`maps_raw.json`) and per place (`maps_details.json`) → assembled `result_rows.json`.
3. **Aggregate + score**: `aggregate_clinics` collapses ≈750 rows → 34 unique clinics with appearances,
   avg position, best-known fields, and high-intent share → `score_clinics` adds the 0–100 score, label,
   and opportunity note → `top_n` → `vulnerable_10.xlsx`.
4. **Reviews**: `collect_reviews` → `reviews_raw.json`; `analyze_all` → `reviews_nlp.json`
   (joined to clinics by `dedup_key(place_url) or name.lower()`).
5. **Web**: `collect_web_interactive` → `web_raw.json`; `match_clinics_web` → per-clinic web visibility
   → blended as the 40% term.
6. **Render**: `build_web.py` reads all of the above (gracefully degrades if any are missing) → payload
   → `dist/derma_intel.html`. Streamlit reads the same JSON state live.

## 4. Resilience patterns
- **Worker-thread Playwright** everywhere (Streamlit asyncio safety).
- **Never cache empty/failed scrapes** → automatic retry on re-run (queries, reviews, web).
- **Cross-query detail cache** → each unique clinic's panel opened once (~10× fewer opens).
- **Mock mode** end-to-end so the whole app is demoable offline with zero scraping.
- **Graceful absence**: build/score work with any subset of {maps, reviews, web} present.
- **Cert bundle** for all downloads; **headful + human** for Google web (the only thing Google won't
  let us automate for free).

## 5. Testing
- `pytest` (97): logic modules (parser, scoring, analytics helpers, web matching, NLP) via TDD;
  Streamlit `AppTest` smoke; end-to-end mock pipeline; PDF export.
- Web UI: Playwright full-page + per-section screenshots for visual QA, and a headless functional
  suite (charts render, row→detail linking, table sort/filter, no horizontal overflow, empty state).

## 6. Google-web 40% — LIVE (Phase 10)
The **screenshot → google-search dataset** path is built and wired (SESSION_LOG Phase 10):
`screenshot_slicer` (tile the manual SERP PNGs) → **Claude-vision extraction** (one-time, persisted to
`web_screens.json`) → `web_screens` (reconcile by search-box text + clinic map + **owned/borrowed**
visibility) → `unify_results` → `build_web._attach_web` feeds `vulnerability.web_relevance_vuln`
(presence-weighted, backward-compatible). 78 queries / ~1122 blocks; the blend moved 31/34 clinics ≥10 pts.

## 7. Not yet wired (roadmap)
- **Review-NLP into the score** (word-of-mouth factor) — currently display-only.
- Surface the owned/borrowed web signals + the zero-web-presence flag in the dashboard UI.
