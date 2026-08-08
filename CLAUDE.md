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
| **Public sales site (anonymized)** | `python web/build_web.py --public` → `web/dist/public/` (`index.html` home + `build.html` treatment page; ~288 KB, no ECharts; Vercel-ready; leak-scanned — real clinic names never ship) |
| Streamlit console (fallback / ops) | `streamlit run app.py` |
| Scrape clinics from Google Maps | `python run_pipeline.py` (resume-safe; only scrapes uncached queries) |
| Reviews + NLP | `python collect_extras.py --reviews` |
| Google web relevance (headful, manual CAPTCHA) | `python collect_extras.py --web` |
| Slice SERP screenshots → tiles | `python modules/screenshot_slicer.py` (Pillow; `.cache/web_tiles/` + manifest) |
| Build google-search dataset (after vision extraction) | `python modules/web_screens.py` → `web_screens.json` + `data/google_search_results.xlsx` |
| Unify Maps + search → 40% web term | `python modules/unify_results.py` → `data/unified_results.xlsx` |
| Tests | `python -m pytest -q` (**373 passing**) |
| **Verify the v3 dashboards** | `python docs/redesign/v3/tools/verify_dashboard.py` (22 checks: design laws · cross-filter flows · perf · shots) |
| Re-sample the reference images | `python docs/redesign/v3/tools/sample_reference.py` → `reference-samples.json` |
| Rebuild the tree-shaken ECharts bundle | `python web/build_echarts.py` (568 KB vs 1006 KB; vendor-time only) |
| Contact sheet (before/after/reference) | `python docs/redesign/v3/tools/contact_sheet.py` (gitignored, ~13 MB) |

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
- **Premium web** (`web/`, v2 "Luminous Precision", two dists):
  - **Private report app** (`build()` → `dist/derma_intel.html` + `dist/index.html`): the paid
    two-tab report (Your Clinic / The Market). Sources: `template.html`, `styles.css`, `app.js`
    (+ tokens/components inlined from `docs/redesign/v2/`). ECharts + Doto/Geist; no GSAP.
  - **Public sales home** (`build_public()` → `dist/public/`): six-act GSAP story + gate +
    pricing. Sources: `template-public.html`, `public.css`, `story2.js`, `public_data.py`
    (anonymizer — leak tripwire at build). The old scroll story (`shell.js`/`story.js`) was
    retired in Phase C; git history keeps it.
  - Shared: `vendor/` (ECharts, GSAP, liquid-glass, Geist/Geist Mono/Doto), `vendor_assets.py`.

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
- Logic-heavy code is TDD'd; keep `pytest` green (**373 tests**, verified 2026-08-08). Commit frequently to local `master`
  (no remote). End commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Gitignored: `.cache/*.json`, `.cache/web_tiles/`, `data/*.xlsx`, `data/Full Page Screenshots/`,
  `web/dist/`, `metadata.json`, **`.env`**, **`.env.local`**, **`.claude/settings.local.json`**.
- Visual/functional QA of the web app is done with **Playwright screenshots** + a headless functional
  suite (see `tests/` and the scratchpad scripts pattern in SESSION_LOG.md).

## Secrets — hard rule
**Never hardcode a secret, never commit one, never echo one into a shell command or log.**
- Source of truth is **`.env`** (gitignored). `.env.example` (committed) lists the required names, no values.
- `.mcp.json` **is committed** and must only ever reference `${VAR}` — never a literal key.
- Current secrets: `STITCH_API_KEY` (also persisted as a Windows **user env var** so `${STITCH_API_KEY}`
  resolves for the Stitch MCP and for `@google/stitch-sdk`).
- To read a key in a script, load it from `.env` / `os.environ`. Do **not** paste it onto a command line —
  the tool-call classifier will (correctly) block you.

## Skills & tooling — MANDATORY, load every session
These are installed globally in `~/.claude/skills/`. Use them; do not freelance past them.

**Design & UI**
- **`impeccable`** — the primary UI craft skill. Own the whole loop: `audit` → `craft` → `animate` →
  `polish`. Default choice for any dashboard/page/component work.
- **`hallmark`** — use for its `study` / extraction mode only: turn `design/Design Inspiration/*.png`
  and the brand PDFs into a concrete design language. Not a second opinion on impeccable.
- **`taste-skill`** (`design-taste-frontend`) — run its **pre-flight anti-slop check** on the storytelling
  home page before calling it done. Catches templated hero/feature-grid defaults.
- **`liquid-glass`** — Apple-style refraction (real `feDisplacementMap`, Chromium; frosted fallback
  elsewhere). Drop-in module lives at `~/.claude/skills/liquid-glass/liquid-glass.js`; copy it into
  `web/vendor/`. Use on **chrome** (nav, modals, overlay cards) — never behind numbers or charts,
  and never let refraction carry meaning.

**Motion** (the site is motion-rich; GSAP 3.13 is already vendored in `web/vendor/`)
- **`motion-design`** (LottieFiles) — decide *what* the motion should be: timing, easing, choreography,
  emotional register. Consult **before** writing tweens.
- **`gsap-core` / `gsap-timeline` / `gsap-scrolltrigger` / `gsap-plugins` / `gsap-utils` /
  `gsap-performance`** — then implement. `gsap-scrolltrigger` owns the pinned scroll story;
  `gsap-performance` is mandatory before any "it feels janky" fix. (`gsap-react` / `gsap-frameworks`
  are installed but unused — this app is vanilla JS.)

**UI generation**
- **`stitch-skill`** — emits a semantic `DESIGN.md`. That file is the input to the **Stitch MCP**
  (`create_design_system_from_design_md`), which is the intended pipeline. See "Google Stitch" below.

**Discipline**
- **`karpathy-guidelines`** — think before coding, simplicity first, **surgical changes**, verify against
  explicit success criteria. The "surgical changes" rule is load-bearing here: Phase 11 is
  **presentation-only** — keep `modules/` and the tests intact.

**Deliberately NOT part of this project's workflow** (installed, but they fight the locked brand or
duplicate the above — do not invoke): `gpt-tasteskill`, `soft-skill`, `redesign-skill`, `brutalist-skill`,
`minimalist-skill`, `taste-skill-v1`, `image-to-code-skill`, `imagegen-frontend-*`, `brandkit`.
The **`headroom`** MCP (context compression) is connected globally but must **not** be used here:
it is lossy, and design work depends on exact CSS/DOM/pixel values.

## Codebase memory (`codebase-memory-mcp`)
100% local, no API key — consistent with the no-paid-APIs rule. **Query it before grepping** when you
need architecture or call paths.
- Project name: **`E-TRINADE-Dermat-Analytics-and-Websites`** (885 nodes / 2168 edges, mode `full`).
- Useful tools: `get_architecture` (Leiden clusters = the real seams), `search_code`, `search_graph`,
  `trace_path`, `get_code_snippet`, `detect_changes` (run after big refactors, then re-`index_repository`).
- **Graph UI: http://localhost:9749** — browses every indexed project under `E:\TRINADE`.
  The binary at `~/.codebase-memory-mcp/bin/` is the **UI build** (v0.8.1) and `ui=true` is persisted, so
  the server exposes it automatically. To start it standalone:
  `Start-Process "$env:USERPROFILE\.codebase-memory-mcp\bin\codebase-memory-mcp.exe" -ArgumentList "--ui=true" -WindowStyle Hidden`
  (It is an stdio MCP server first — it exits instantly if stdin is closed, so don't pipe `/dev/null` into it.)

## Google Stitch (AI UI generation)
Configured in the committed `.mcp.json` as an **http** MCP at `https://stitch.googleapis.com/mcp`,
authenticated with the `X-Goog-Api-Key` header sourced from `${STITCH_API_KEY}`. Verified working.
- Tools: `create_project`, `generate_screen_from_text`, `edit_screens`, `generate_variants`,
  `upload_design_md`, `create_design_system_from_design_md`, `apply_design_system`, `list_screens`,
  `get_screen`, `list_design_systems`, `update_design_system`, plus project CRUD.
- **Intended flow:** `stitch-skill` writes `DESIGN.md` → `create_design_system_from_design_md` →
  `generate_screen_from_text` → pull HTML → re-implement against `docs/redesign/tokens.css`.
  Treat Stitch output as **reference**, never as shipped markup — it does not know our brand tokens.
- Screen generation takes minutes per call. There is also `@google/stitch-sdk` (npm), same `STITCH_API_KEY`.

## Ownership & guardrails
- **`web/` is owned by the Phase-11 redesign workstream** (this project's active design effort;
  the earlier parallel-session split is over).
- The brand is **"Luminous Precision" v2** (2026-07-10): cool gray canvas + grain-gradient triads +
  Doto dot-matrix numerals + single lime accent + Geist/Geist Mono. Source of truth:
  `docs/redesign/v2/` (`tokens-v2.css`, `components.css`, `BRAND_GUIDE_V2.md`, `brand-guide.html`,
  `DESIGN.md` for Stitch, booklet PDF). v1 "Warm Intelligence" (`docs/redesign/BRAND_GUIDE.md`)
  is superseded — kept as history only. Business model + page specs:
  `docs/superpowers/specs/2026-07-10-phase11-luminous-precision-redesign-design.md`
  (diagnostic ladder: Report ₹4,999 → Monitoring ₹9,999/yr → Build ₹49,999+ · two-dist privacy split).
- Phase 11 is **presentation-only**: `modules/` and the test suite stay green and untouched
  (only `web/build_web.py` may gain TDD'd logic for the two-dist split).

## Current state (2026-08-08) — v3 "instrument-grade" dashboards SHIPPED
80 queries · 34 clinics · the 60/40 blend live · **373 tests pass** · private dist **1041 KB**
(was 1322) · public dist byte-identical throughout.

### The v3 rebuild (P0–P6, all gates cleared)
The v2 report app was **scrapped**, not tweaked: `web/styles.css` and `web/app.js` are
deleted. `web/` now holds `css/` (7 files) + `js/` (9 IIFEs on `window.DI`), concatenated
by `build_web.py`. No bundler, no imports — **the numeric prefix IS the load order**
(`70-app` must precede the panel files, and a test asserts it).

- **Identity re-derived by MEASURING** (`docs/redesign/v3/`): a probe map + Pillow sampler
  over the 9 reference images, reconciled in `ATLAS.md`. It overturned v2: the canvas is
  hue-neutral `#EDEDED` (every neutral probe returned R=G=B exactly), cards run a
  **five-rung glass ladder**, **nothing renders at weight 700**, the score jewel is
  green-dominant (v2 mis-attributed the orange), and lime measured to `#DCF306`.
  The sampler adds patch **sigma** + channel **delta** so a probe that misses is
  detected, not caught by eye — it auto-flagged `field-mid` landing on a jewel.
- **`palette.json` is the ONLY place a colour is authored.** `gen_tokens.py` emits both
  the CSS custom properties and the JS object ECharts reads, so the v2 palette
  duplication cannot recur. Enforced by `tests/test_v3_source_laws.py`.
- **Jewels STATE-MAP** — the visibility hero's recipe follows the score band, so a 34
  renders in caution and can never read as reassuring. This is the deliberate divergence
  from the Log App (theirs never change); see `ATLAS.md` §9.
- **`web/views.py`** — pure derived views (`plan_impact`, `serp_ownership`, `serp_page`,
  `visibility_bands`, `market_facets`, `km_from_core`). `modules/` untouched.
- **Cross-filtered**: 3 bus channels with a cost contract — hover NEVER calls
  `setOption` (0.2 ms), filter is one memoised recompute (27 ms round-trip).
- **19 panels**: Your Clinic (twin jewels · split-score · examination rack · intent polar
  · redrawn SERP · prescription stack · patient voice · constellation) and The Market
  (jewels · KPI strip · opportunity map with brush · league · **SERP ownership matrix** ·
  ad shelf · owned-vs-borrowed · funnel · categories · map · table).
- **The raw SERP screenshot is gone** — replaced by the result page redrawn in our own
  components, with the clinic's absence as a literal dashed gap. `_copy_proof` and
  `dist/proof/` are deleted, so the private dist is **truly self-contained** at last.
- **Payload 193 KB** (was 215): surfaces `pos_avg`, `high_intent`, `lat/lng/km_core`,
  the `maps_score`/`web_score` split, `sponsored`, `plan`, and the 1122-block SERP
  aggregate; drops the unread `top10` (40 KB of duplicated clinics), `rating_distribution`,
  `headline_*`, `lede`.

### Gotchas this rebuild paid for (do not relearn them)
- **npm cannot reach the registry** through the TLS interception — it ignores
  `NODE_EXTRA_CA_CERTS` *and* `--use-system-ca`. **`curl` works** (schannel → Windows
  store), which is how `build_echarts.py` fetches tarballs. Never disable verification.
- **ECharts ignores `itemStyle` callbacks** for `opacity`/`borderWidth` (only `color`
  works) — three series rendered invisible. Use **per-datum `itemStyle`**.
- A **`markArea` on the same series** as its marks paints over them; give plates their
  own silent `z:0` series.
- **Chromium `full_page` screenshots do not repaint `<canvas>`** on long pages. Size the
  viewport to the document instead (`shoot_tall` in the verifier).
- `Object.assign(el.style, …)` **silently drops custom properties** — use `setProperty`.
- `[hidden]` is only `display:none` at UA level; any `display` rule defeats it.

### Deliberate calls worth knowing
- `presence_of` is stricter than v2: a **paid placement is OWNED** (you control the
  destination) and **places-only is INVISIBLE** (the local pack is Maps re-surfaced).
  Live: own 12 / borrowed 2 / invisible 20, where v2 showed 10 / 9 / 15.
- `payload.quadrant` is **not shipped** — `analytics.quadrant_frame` cuts zones on
  *rating*, a trap here (28 of 34 sit between 4.8–5.0); the opportunity map cuts on the
  axes it plots.
- The `maps` scorecard check is **relabelled in panel copy** to "in the local pack"
  because it measures local-pack presence across the 78 SERPs, not Google Maps presence.
  `modules/report.py` stays byte-identical.
- `design/` (13 MB of reference images + brand PDFs) is **still untracked**. The probe
  map reads from it, so verification cannot be reproduced from a fresh clone until it is
  committed or relocated — George's call.

### Next candidates
- **WS-2: the public homepage** (`web/dist/public/`) is still v2 and untouched by this
  rebuild — it is the remaining "empty and centred" surface.
- Fold review-NLP (referral / word-of-mouth) into the numeric score.
- `config.WHATSAPP_NUMBER` and the Razorpay links are still `""`.

## Environment note — git over TLS interception
`git clone` (e.g. installing skills) hits the same MITM cert wall as Node downloads. Fix without weakening
TLS: `git -c http.sslBackend=schannel clone …` (uses the Windows cert store, which trusts the corporate
root). Never `http.sslVerify=false`.
