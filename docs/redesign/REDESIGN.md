# Derma Intel — Premium Interface Redesign

Redesign of the existing Streamlit analytics app into a premium, self-contained local web
interface, with Streamlit retained as an operational fallback. This document is the full record of
audit → diagnosis → architecture → migration → implementation → chart rationale → QA → testing →
fallback.

---

## 1. Existing interface audit

**What it is.** A Streamlit app (`app.py` + `components/` + `modules/`) for Guntur dermatologist
market intelligence. Current live dataset: 50 queries → 750 appearance rows → 34 unique clinics →
top-10 "vulnerable" (highest-opportunity) clinics.

**Page structure (as built):**
- **Sidebar** — title/tagline, three data-status dots (queries / maps / vulnerability), "Use mock
  data" toggle, **▶ Run Pipeline** button, last-run timestamp, then three stacked `st.metric` quick
  stats (Queries, Appearance rows, Vulnerable).
- **Tab 1 — Queries**: paste-the-AI-prompt workflow + a `st.dataframe` of the 50 queries + a small
  donut.
- **Tab 2 — Results**: three columns `[1, 2, 1.5]` — scrollable query buttons | clinic cards (≤15) |
  a text detail panel with a vulnerability pre-score badge.
- **Tab 3 — Analytics**: a `st.header` then 14 Plotly/Altair charts stacked in `st.columns` groups
  (Market Overview / Ratings & Reviews / Presence & Visibility / Competitive Gaps), each with an
  `st.caption` insight line.
- **Tab 4 — Vulnerable 10**: a computed overview sentence, then 10 bordered cards (name, score badge,
  address/phone, rating/reviews/website, a `st.progress` gauge, opportunity note, Maps link), then
  Excel + PDF download buttons.

**Intended workflow:** generate queries → run pipeline → skim the market → read analytics → act on
the top-10 opportunities.

**Experienced workflow (where it breaks):**
1. **The payload is last.** The product's entire reason to exist — *"here are the 10 clinics to call
   and why"* — lives in **Tab 4**, behind three tabs. The user must click Queries → Results →
   Analytics before reaching the conclusion. The answer should be first; here it is last.
2. **Tabs hide the story.** Only one section is visible at a time. There is no glanceable overview
   and no narrative thread connecting sections; the user must remember state across tab switches.
3. **No emphasis gradient in Analytics.** 14 charts render at roughly equal visual weight, stacked
   vertically with heavy scroll. The 2–3 charts that actually drive a decision (the competitive
   quadrant, the no-website ranking) look identical in importance to incidental ones.
4. **Redundancy.** "Top-15 most-appeared clinics" (chart 2) and "ranked appearances top-20" (chart 8)
   are the same bar chart twice. The donut appears in both Tab 1 and Tab 3.
5. **Split, cramped KPIs.** The four headline numbers exist as tiny sidebar `st.metric`s *and* again
   atop Analytics — attention is split and neither placement reads as a confident headline.

**Layout / spacing / sizing issues (concrete):**
- The sidebar permanently consumes ~21rem even on the analytics-heavy tabs where it's mostly idle.
- `st.columns([1,2,1.5])` and `st.columns(2)` produce uneven gutters and force charts into widths
  they don't suit — the Tab-1/Tab-3 donut is squeezed into a 1-of-4 column and renders tiny.
- `use_container_width=True` stretches every chart to full width regardless of whether the chart
  benefits, so a funnel and a treemap get the same canvas as a dense scatter.
- Card and chart vertical rhythm is whatever Streamlit's default block gap is (~1rem) everywhere —
  no deliberate spacing scale, so sections don't feel grouped.

**Chart usability issues:**
- Plotly defaults dominate: visible mode-bars, gridlines, boxed legends, default categorical colors,
  axis clutter. The charts read as *technical output*, not designed communication.
- Several charts are low-decision-value as drawn: a ratings histogram with a mean line, a review
  box-plot by category, a treemap sized by reviews — they show data but don't answer a question.
- The map (`scatter_mapbox`) and Altair heatmap each pull a different rendering engine and visual
  language into the same tab, so the analytics page lacks one coherent chart aesthetic.

**Fallbacks / compromises already forced by the current approach:**
- PNG export was downgraded from server-side `kaleido` to Plotly's client modebar because kaleido is
  slow/flaky — i.e., a feature already bent around Streamlit/runtime limits.
- Per-chart caching (`@st.cache_data`) exists purely to survive Streamlit's rerun-everything model.
- Live scraping had to be moved onto a worker thread because Streamlit's script thread runs an
  asyncio loop that Playwright's sync API refuses (documented in `maps_collector._run_browser`).

---

## 2. Exact diagnosis

| Symptom | Root cause | Class |
|---|---|---|
| Conclusion (top-10) reached last | Tab ordering puts the answer last | **Poor design** (fixable anywhere) |
| No at-a-glance overview | Tab model shows one section at a time | **Streamlit limitation** |
| 14 equal-weight charts, heavy scroll | No emphasis hierarchy / curation | **Poor design** |
| Duplicate charts (appearances ×2, donut ×2) | No editorial pass on the chart set | **Poor design** |
| KPIs cramped + duplicated | Sidebar `st.metric` + Analytics repeat | **Poor design** |
| Uneven gutters, squished donut, stretched funnel | `st.columns` + `use_container_width` coarseness | **Streamlit limitation** |
| "Technical, cluttered" charts | Plotly defaults; constrained theming in Streamlit | **Mostly Streamlit limitation** |
| No cross-chart linking / filtering | Streamlit rerun model, no client state | **Streamlit limitation** |
| Generic dark theme, weak type, no motion | Streamlit theming ceiling | **Streamlit limitation** |

**What works and must be preserved (do not touch):**
- The **Python pipeline + data model**: `query_generator`, `maps_collector` (incl. the threading and
  cross-query detail-cache fixes), `vulnerability` scoring, `analytics` aggregation helpers,
  `storage`. This is solid, tested (45 tests), and produces clean data.
- The **vulnerability score + opportunity notes** — the analytical core.
- **Mock mode**, the **Excel/PDF exports**, and the **manual-paste query workflow** — these are
  operational actions, best left in the Streamlit console.

**What is structurally wrong and must be redesigned:** the *presentation & information architecture*
— ordering, hierarchy, layout, chart selection, and visual language. None of that lives in the data
layer, so the redesign is a pure front-end re-architecture on top of the same data.

---

## 3. Replacement architecture & tech stack

**Decision: a self-contained static HTML app, generated by a Python build step, opened directly in
the browser (file://). No server.** Charting by **ECharts**; type by **Geist Sans/Mono**; both
vendored locally for full offline self-containment.

```
modules/ (unchanged)  ──►  web/build_web.py  ──►  web/dist/derma_intel.html  ──►  open in browser
        analytics/vulnerability        (reuses Python logic,        (single file: inlined CSS,
        /storage produce data           computes one JSON payload)   ECharts, fonts, data, app JS)
```

**Why this beats continuing in Streamlit (and why static over a server):**
- **Full design control.** Real CSS = true grid, sticky glass header, a deliberate spacing/type
  scale, motion, and one coherent chart aesthetic — none of which Streamlit allows.
- **The answer can come first.** A scroll narrative (overview → opportunity → landscape → detail)
  replaces hide-one-tab-at-a-time, fixing the #1 flow failure.
- **No server lifecycle.** The app is one file opened via `file://`. This directly removes the
  "localhost is down" fragility hit earlier — nothing to keep running, works offline, instant.
- **Reuses 100% of the Python logic.** The build step calls the existing modules; zero data-layer
  duplication. Single source of truth.
- **Premium charts.** ECharts gives designed defaults, smooth motion, and rich interaction (linked
  highlights, custom tooltips) far beyond themed Plotly.

Static (build-step) was chosen over a FastAPI/Flask server because the heavy, stateful action
(scraping) is already a CLI/Streamlit concern; the web layer only needs to *present* results, and a
server would re-introduce exactly the lifecycle fragility we just removed. Trade-off accepted: the
web app is a viewer; (re)generating data is `python run_pipeline.py` then a one-command rebuild.

**Design system (the "Quiet Precision" direction):**
- **Theme:** warm-paper light surface (`#FAFAF7`), white panels, deep warm ink (`#16150F`), one
  restrained clinical-teal accent (`#0F766E`), and a calm sand→clay sequential for opportunity
  intensity (premium, not alarmist).
- **Type:** Geist Sans (UI/body) + Geist Mono (all numerals/labels, tabular) — distinctive,
  professional, not Inter/Roboto/system.
- **Space:** an 8px-based scale; generous section padding; consistent 1px hairline borders + soft,
  low-spread shadows for layered calm (subtle glass only on the sticky header).
- **Motion:** one orchestrated staggered load (fade+rise); restrained hover states; ECharts entrance
  easing. No decorative animation.

---

## 4. Migration & dependency analysis

**New dependencies:** none required at runtime for viewing (the dist file is self-contained). Build
step uses only already-installed `pandas`/`openpyxl` via existing modules + stdlib. `requests` (already
present) is used once by `web/vendor_assets.py` to fetch ECharts/fonts (cached in `web/vendor/`, so it
runs offline thereafter). **No new pip installs, no Node, no API keys** — consistent with the project's
free/no-keys constraint.

**Frontend structure:**
```
web/
  vendor_assets.py     # one-time: fetch ECharts + Geist into web/vendor/
  vendor/              # echarts.min.js + 6 Geist woff2 (committed-ignored or kept)
  template.html        # page shell with {{PLACEHOLDERS}}
  styles.css           # design system + layout (source)
  app.js               # render + charts + interactions (source)
  build_web.py         # loads data via modules, inlines everything → dist/derma_intel.html
  dist/derma_intel.html# the shipped, self-contained app
derma_web.py           # root launcher: build + open in default browser
```

**Data flow change:** Streamlit read JSON/session and rendered per-rerun. Now `build_web.py` calls
`storage.load_rows`, `vulnerability.aggregate_clinics/score_clinics/top_n`, and `analytics` helpers
once, assembles a single `payload` JSON (KPIs, scored clinics, top-10, category mix, funnel, rating
distribution, website-by-category), and inlines it into the HTML. The browser renders entirely from
that embedded payload — no fetch, no CORS, no server.

**What stays in Streamlit (fallback / operational console):** the manual-paste query workflow, the
**Run Pipeline** action (scraping), mock mode, and Excel/PDF generation. Streamlit remains the
"control room"; the web app is the "showroom."

**Interoperability:** both read the same `.cache/*.json` + `data/*.xlsx`. Run order:
`run_pipeline.py` (or Streamlit Run Pipeline) → `python derma_web.py` (rebuild + open). The web
build is idempotent and safe to re-run anytime.

**Test implications:** Python data tests are unaffected (45 still pass). New front-end verification is
done by loading `dist/derma_intel.html` in headless Chromium (Playwright, already installed) and
asserting charts mount, the table sorts/filters, there are no console errors, and the layout holds at
narrow widths.

**Risks & mitigations:**
- *Stale view after a new scrape* → the launcher always rebuilds before opening; README documents it.
- *Empty/partial data* (no pipeline run yet, all FETCH_FAILED) → build emits a graceful empty state
  with instructions, never a broken page.
- *Offline/asset-missing* → assets are vendored & inlined; if `web/vendor` is missing the build falls
  back to CDN `<script>`/`<link>` and notes it.
- *Very wide clinic names / missing fields* → defensive formatting (the data has keyword-stuffed
  names and missing websites by design).
- *Narrow screens* → responsive CSS (single-column reflow); charts resize via ECharts `resize()`.

**Edge cases handled in the build/app:** zero clinics; clinics with no rating/reviews/website/phone;
ties in vulnerability score; long names; no coordinates (map dot skipped); chart with a single
category.

---

## 5. Implementation

Files added (data layer untouched):
- `web/styles.css` — the "Quiet Precision" design system (tokens, type scale, components, motion,
  responsive). `web/template.html` — semantic shell with `{{PLACEHOLDERS}}`. `web/app.js` — renders
  the narrative from the inlined payload, builds the ECharts charts, and wires interactions.
- `web/build_web.py` — calls the existing modules, assembles one JSON payload, and inlines CSS +
  base64 fonts + ECharts + payload + app.js into `web/dist/derma_intel.html` (one offline file).
- `web/vendor_assets.py` + `web/vendor/` — ECharts 5.5.1 and Geist Sans/Mono, fetched once via the
  Windows cert bundle, committed for offline/repeatable builds.
- `derma_web.py` — root launcher: rebuild from latest data + open in the browser.

Narrative & hierarchy (the re-architecture): **answer first**. The page reads top-to-bottom as
(1) at-a-glance headline + KPIs → (2) the ranked top-10 opportunities with a linked detail panel →
(3) the competitive landscape → (4) market composition → (5) full explorable table. The old "most
important content last, one tab at a time" model is gone. A single staggered load animation, a glass
sticky header, a restrained teal accent, tabular Geist Mono numerals, and an 8px spacing scale carry
the premium feel.

Polish details: keyword-stuffed Google Maps names are reduced to their primary segment for display
(full name preserved in `title`/tooltips); the alarmist red vulnerability palette from the data layer
is re-mapped to a calm sand→clay scale; insight callouts state the takeaway in one sentence per
section.

## 6. Chart redesign rationale

Curated from **14 undifferentiated charts down to 4 decision-oriented visuals + 2 reading aids**,
each tied to a question:

| Visual | Question it answers | Why it replaces what was there |
|---|---|---|
| **Top-10 opportunity rows** (HTML + score bars) | "Who do I call first, and how urgent?" | A ranked list with inline score bars + key facts beats a bare bar chart — more context per row, and it *is* the product's answer, now placed first. |
| **Competitive landscape scatter** (appearances × reviews × has-website × score) | "Where is demand meeting weak presence?" | Fuses the old quadrant + appearance bars + website bar into one relationship view. Colour = has-website makes the opportunity cluster (clay, right side) self-evident. |
| **Online-presence donut** (center: "14/34 no website") | "How big is the digital gap?" | A single, centrally-labelled binary ring — direct, unlike the old stacked-by-category bar. |
| **Search-demand bar** (ranked categories) | "What are people actually searching?" | Ranked horizontal bar replaces the criticised donut; ordered, labelled, instantly readable. |
| **Reputation histogram** | "Is rating a differentiator?" | Shows ratings cluster at 4.5–5.0 → reputation is *not* the lever; presence is. Reframes the whole analysis. |
| **KPI strip** | "What's the state of the market in 5 seconds?" | Four confident mono numbers, once, at the top (previously split between sidebar and analytics tab). |

Removed as low-decision-value or redundant: the duplicate appearance bars, the review box-plot by
category, the reviews treemap, the clinic×category heatmap, and the raw map scatter (location is in
the table + Maps links; it added little decision value and a second rendering engine).

## 7. Visual QA review & fixes

Method: rendered `dist/derma_intel.html` in headless Chromium at 1440px and 412px, captured full-page
and per-section screenshots, and reviewed against the design principles. Issues found and fixed
properly (not cosmetically):
1. **Keyword-stuffed names** broke hierarchy and wrapped the detail panel into 4+ lines → added a
   primary-segment name cleaner in the build; applied to rows, detail, table, and tooltips.
2. **Auto-shown chart tooltip on load** floated over the scatter's axis (clutter) → removed the
   forced `showTip`; the linked highlight now uses emphasis only.
3. **Alarmist red** score palette clashed with the calm system → re-mapped to sand→clay.
4. **Horizontal overflow at 390px** (54px) traced via DOM inspection to grid/flex items defaulting to
   `min-width:auto` (nowrap names) → set `min-width:0` on the opportunity grid items so names
   ellipsize; table given an `overflow-x:auto` scroll wrapper.

## 8. Functional testing results

Headless Chromium suite (`qa_functional.py`) — **15/15 passing**:
no page/console errors · all 4 charts render canvases · 4 KPI cards · 10 opportunity rows · clicking a
row activates it and updates the detail panel · detail Maps action present · table shows all 34 ·
search filters · sort-by-reviews orders descending · **no horizontal overflow at 390px** · empty
state renders when data is absent. The Python data suite remains green (**45/45**, modules unchanged).

## 9. Streamlit fallback

Streamlit is fully retained as the operational console and fallback: `streamlit run app.py` still
runs the manual-paste query workflow, the **Run Pipeline** scrape (with the worker-thread +
detail-cache fixes), mock mode, and Excel/PDF export — all reading/writing the same files. The web
app is a presentation layer over the identical data; deleting `web/` changes nothing about Streamlit.
Typical loop: refresh data in Streamlit (or `python run_pipeline.py`) → `python derma_web.py` to
rebuild and view the premium interface.
