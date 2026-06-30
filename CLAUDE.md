# CLAUDE.md — Derma Intel

Working memory + instructions for Claude Code. **Read this first every session.** Companion docs:
[ARCHITECTURE.md](ARCHITECTURE.md) (how it's built), [DESIGN.md](DESIGN.md) (UI + scoring rationale),
[SESSION_LOG.md](SESSION_LOG.md) (history), [README.md](README.md) (user guide), [PROMPT.md](PROMPT.md)
(the Phase-10 screenshot brief, now complete).

## What this is
A **100% free, no-API-key** market-intelligence platform that finds the dermatology clinics in
**Guntur, Andhra Pradesh** with the biggest gap between their **local demand** and their **online
presence** — i.e. the best prospects for digital-marketing help. The product is pivoting to be **sold
to the clinics themselves** as a "here's where you stand vs. the market" report, so framing is
opportunity/diagnostic, not accusatory.

## Non-negotiable constraints
- **NO paid APIs. NO API keys. Ever.** Free / local tools only. This is foundational (user decision).
- **NEVER disable TLS verification** (no `NODE_TLS_REJECT_UNAUTHORIZED=0`). Use the cert bundle (below).
- Don't reintroduce keyed/paid services; don't re-attempt raw Google/Bing/DDG SERP scraping (blocked).
- Platform: **Python 3.10, Windows**. Playwright + Chromium already installed.

## How to run
| Goal | Command |
|---|---|
| Premium web dashboard (PRIMARY) | `python derma_web.py` → builds + opens `web/dist/derma_intel.html` (self-contained, offline, **no server**) |
| Streamlit console (fallback / ops) | `streamlit run app.py` |
| Scrape clinics from Google Maps | `python run_pipeline.py` (resume-safe; only scrapes uncached queries) |
| Reviews + NLP | `python collect_extras.py --reviews` |
| Google web relevance (headful, manual CAPTCHA) | `python collect_extras.py --web` |
| Slice SERP screenshots → tiles | `python modules/screenshot_slicer.py` (Pillow; `.cache/web_tiles/` + manifest) |
| Build google-search dataset (after vision extraction) | `python modules/web_screens.py` → `web_screens.json` + `data/google_search_results.xlsx` |
| Unify Maps + search → 40% web term | `python modules/unify_results.py` → `data/unified_results.xlsx` |
| Tests | `python -m pytest -q` (121 passing) |

## Environment gotchas (these cost hours last time — heed them)
- **TLS interception** on this machine breaks HTTPS downloads (Node + Python `requests`). Fix already
  applied: `NODE_EXTRA_CA_CERTS` → `%USERPROFILE%\node_ca_bundle.pem` (exported Windows cert store).
  For Python downloads pass `verify=` that bundle. Do NOT disable verification.
- **Streamlit + Playwright**: Streamlit's script thread has a running asyncio loop; Playwright's *sync*
  API refuses there ("Sync API inside the asyncio loop"). Every scraper runs the sync work in a
  **worker thread** (`_run_browser` wrappers). Never inline sync Playwright on the loop thread.
- **Google WEB search is hard-blocked headless** (instant `/sorry` reCAPTCHA — every method tried:
  requests `gbv/igu`, headless Playwright + real Chrome + stealth + all URL variants). Only
  **headful with a human CAPTCHA solve** works (`web_collector.collect_web_interactive`, persistent
  profile so you solve once or twice). Google **Maps** scraping works headless fine.
- Google Maps **throttles** rapid review requests → backoff + CID-URL fallback + never-cache-empties;
  resume by re-running the collector.

## Module map (`modules/`)
- `query_generator.py` — builds the AI-paste prompt; robust parser; derives category / user_intent /
  search_strength; writes `data/search_queries.xlsx`.
- `maps_collector.py` — Playwright Google **Maps** scraper (worker-thread, consent, glyph-clean,
  dedup by CID), `mock=True` mode, OSM geocode fallback, **cross-query detail cache**, results xlsx.
- `vulnerability.py` — the **opportunity score** (see below), `aggregate_clinics` (+`high_intent_share`),
  labels, opportunity notes, top-10 xlsx, the 60/40 web blend.
- `analytics.py` — KPIs + chart builders (Streamlit) + tested data-prep helpers.
- `storage.py` — JSON state store (`.cache/query_rows.json`, `result_rows.json`) + `metadata.json`.
- `web_collector.py` — Google **web** SERP collector (headful interactive) + `match_clinics_web`.
- `reviews_collector.py` — Google Maps **reviews** scraper (resume-safe, throttle backoff).
- `reviews_nlp.py` — **free** VADER NLP: sentiment, themes, pain points, referral rate, recency.
- `screenshot_slicer.py` — Pillow tiling of the tall full-page SERP PNGs into legible overlapping tiles
  (a whole page downscales to illegible in Claude vision) + manifest. Tiles are ephemeral/gitignored.
- `web_screens.py` — **screenshot google-search dataset**: reconcile screenshots→queries (map by
  search-box text, **never order**; report the 78-vs-80 gap), clinic mapping (reuses `web_collector`
  helpers), block normalization, per-clinic **OWNED-vs-BORROWED** web visibility, and
  `google_search_results.xlsx`. Independent of the Maps dataset.
- `unify_results.py` — merge the clinic-level Maps view + the screenshot web signal →
  `unified_results.xlsx`; exposes the per-clinic web signal that feeds the 40% web term.

## Front ends
- **Streamlit**: `app.py` + `components/` (`tab_queries`, `tab_results`, `tab_analytics`,
  `tab_vulnerable`, `_format`).
- **Premium web** (`web/`): `build_web.py` reuses the modules → one JSON payload → inlines CSS +
  base64 Geist fonts + ECharts + data + `app.js` into a single offline `dist/derma_intel.html`.
  Sources: `template.html`, `styles.css`, `app.js`, `vendor/` (ECharts + Geist), `vendor_assets.py`.

## Data (ALL gitignored)
- `.cache/`: `query_rows.json` (80 queries), `result_rows.json` (≈750 appearance rows → 34 unique
  clinics), `maps_raw.json`, `maps_details.json`, `reviews_raw.json`, `reviews_nlp.json`,
  `web_raw.json`, `web_profile/` (persistent Chrome profile for headful web), **`web_screens.json`**
  (extracted SERP dataset — 78 queries, ~1122 blocks), **`web_tiles/`** (ephemeral SERP tiles + manifest).
- `data/`: `search_queries.xlsx` (80), `google_maps_results.xlsx`, `vulnerable_10.xlsx`,
  **`google_search_results.xlsx`** (one row per SERP block), **`unified_results.xlsx`** (Maps ‖ web per
  clinic), **`Full Page Screenshots/`** (78 full-page Google SERP PNGs, extracted).
- `metadata.json`: last-run timestamp.

## The opportunity score (`vulnerability.py`)
Final **0–100 = 0.6 × Maps + 0.4 × Web** (web term only when web data exists, else Maps-only).
Non-operational clinics ×0.4. Higher = bigger opportunity.
- **Maps = GAP (weakness, max 58)** + **REACH (value, continuous, max 42)**:
  - GAP: no/weaker website **22**, buried (avg pos > 7) **12**, few reviews (< market avg) **10**,
    weak rating (< 4.8) **8**, no phone **6**.
  - REACH: demand **16** (appearances/25, capped), high-intent **14** (share in Pricing/Booking/
    Near-Me), central location **12** (≤ 3 km from city core).
- **Web (LIVE via screenshots)** = invisibility from the screenshot dataset: **OWNED** (own-site organic
  ranking or paid ad) drives visibility, **BORROWED** (aggregator/social-only, e.g. Practo/JustDial)
  earns partial credit, **Places-only / absent = fully invisible** (the Places pack is Maps re-surfaced,
  excluded so the 40% web term doesn't echo the 60% Maps term). `web_relevance_vuln` keeps a
  backward-compatible legacy `web_appearances` path. Calibrated: `OWNED_FULL=6`, `BORROWED_FULL=12`,
  `BORROWED_CREDIT=0.35`. Wired in via `build_web._attach_web` (prefers screenshots over the live cache).
- Labels: **Critical 80+, High 60–79, Medium 40–59, Low 0–39** (calm sand→clay palette, never red).
- **Reviews-NLP** (sentiment / pain points / referral rate) currently feeds the "Patient voice" panel,
  **not** the numeric score yet (referral rate + review velocity are the intended word-of-mouth inputs).

## Conventions
- Logic-heavy code is TDD'd; keep `pytest` green (**121 tests**). Commit frequently to local `master`
  (no remote). End commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Gitignored: `.cache/*.json`, `.cache/web_tiles/`, `data/*.xlsx`, `data/Full Page Screenshots/`,
  `web/dist/`, `metadata.json`.
- Visual/functional QA of the web app is done with **Playwright screenshots** + a headless functional
  suite (see `tests/` and the scratchpad scripts pattern in SESSION_LOG.md).

## Current state (2026-06-30)
80 queries · 34 clinics scored with the **full 60/40 blend now LIVE** (Maps + Google-web from the
screenshot dataset) · reviews-NLP for 31 clinics · premium web dashboard built (`web_available=True`) ·
**135 tests pass**.
- **Doctor-facing content engine built** (`modules/report.py`, TDD): per-clinic **Online Visibility**
  score (higher=better) + rank, 5-check scorecard, you-vs-market benchmarks, plain verdict, and the
  real-SERP **proof**; `payload.market` summary. Wired into the payload via `build_web._attach_reports`.
  Powers a planned **two-view** product — ① "Your Clinic" report + ② "Market" dashboard. Content/structure
  spec: [docs/redesign/CONTENT_SPEC.md](docs/redesign/CONTENT_SPEC.md) (visual build is Phase 11).
- **Screenshot dataset done**: 78 SERP screenshots → 440 tiles → vision-extracted **78 queries / ~1122
  blocks** → `web_screens.json` + `google_search_results.xlsx` (Task 1), unified into `unified_results.xlsx`
  feeding the 40% web term (Task 2). Spec: `docs/superpowers/specs/2026-06-30-google-serp-screenshot-dataset-design.md`.
- **78-vs-80**: the 2 queries with no screenshot are rank 50 *"best dermatologist in Guntur for
  pigmentation"* and rank 69 *"urticaria hives treatment Guntur"*. All 78 mapped exact by search-box text.
- **15 of 34 clinics have ZERO web presence** (top opportunities pair this with high Maps demand).
- **NEXT — Phase 11: premium redesign** (runs in a parallel session). Make the dashboard studio-quality
  (premium motion via GSAP, premium icons/UI/UX) to sell to Guntur clinics + upsell website builds; craft
  a Brand Identity Guide. Brief: [docs/redesign/PREMIUM_REDESIGN_BRIEF.md](docs/redesign/PREMIUM_REDESIGN_BRIEF.md);
  paste-ready kickoff: [NEXT_SESSION_PROMPT.md](NEXT_SESSION_PROMPT.md). Design skills installed globally
  (`~/.claude/skills/`): `impeccable`, `taste-skill`, `redesign-skill`, `soft-skill`, `brandkit`,
  `hallmark`, `gsap-*` (8), imagegen-web/mobile. The redesign folds in the still-deferred owned/borrowed +
  zero-web-presence UI surfacing. Presentation-only — keep `modules/` + the 121 tests intact.
- **Other candidates**: fold review-NLP (referral/word-of-mouth) into the numeric score.

## Environment note — git over TLS interception
`git clone` (e.g. installing skills) hits the same MITM cert wall as Node downloads. Fix without weakening
TLS: `git -c http.sslBackend=schannel clone …` (uses the Windows cert store, which trusts the corporate
root). Never `http.sslVerify=false`.
