# PROMPT — Next session

Paste this to start the next session.

---

You are continuing work on **Derma Intel** (project root: `E:\TRINADE\Dermat Analytics and Websites`).

**First, get full context — read these in order:** `CLAUDE.md` (constraints, run commands, module map,
environment gotchas, current state), then `ARCHITECTURE.md`, `DESIGN.md`, and `SESSION_LOG.md`. Confirm
the hard rules: **100% free, no API keys, no paid services; Python 3.10 / Windows; never disable TLS.**
Don't re-attempt live Google/Bing/DDG web-search scraping — it's confirmed blocked (that's *why* this
task exists).

## Background for this task
Automated Google **web** search is hard-blocked. So instead, I manually captured **full-page
screenshots** of the Google results page for (nearly) all 80 search queries. They live in:

`E:\TRINADE\Dermat Analytics and Websites\data\Full Page Screenshots\` — **78 PNGs**, named
`screencapture-google-search-<date>-<time>.png` (timestamp-ordered, **not** query-named, so part of the
job is figuring out which query each screenshot belongs to — read the query from the search box shown in
the image, and/or align by order to `.cache/query_rows.json`; reconcile the 78-vs-80 gap and report it).

Each screenshot contains a mix of these block types (my observations):
1. **Sponsored results — top** (ads above everything)
2. **Sponsored results — in-between** (ads lower in the page, not at the top)
3. **Places + Map** (the local pack)
4. **General/organic results**, which include: **AI overview** (with info + recommendations),
   **Instagram**, the clinic's **own website**, **Practo**, **JustDial**, **Lybrate**, **YouTube**,
   **Traya**, **Skedoc**, etc.

## Task 1 — extract & structure the screenshots, map to clinics
Build a script/pipeline that turns these screenshots into a **structured google-search dataset**. For
each query (screenshot), capture each result block with at least: `query`, `block_type`
(sponsored_top / sponsored_mid / places / organic / ai_overview), `source/platform`
(own_website / practo / justdial / lybrate / instagram / youtube / traya / skedoc / other),
`title`, `domain`/`url` (if legible), `position`, and the **clinic it maps to** (match against the 34
clinics from Maps — use `vulnerability.aggregate_clinics` on `.cache/result_rows.json` for names +
website domains; reuse `web_collector._clean` / `dedup_key` / matching ideas).

**Extraction approach is the first decision (brainstorm it):** free + no-keys options are
(a) **Claude vision via the `Read` tool** — read each PNG and extract structured JSON; most accurate for
SERP layout (it can see "Sponsored", the map pack, AI overview, logos) and needs no OCR install, but
it's ~78 reads done by the agent, not a deterministic script; or (b) **Tesseract/pytesseract OCR** for a
repeatable script — but it needs the Tesseract binary installed and loses layout/visual cues. Given this
is a one-time corpus of 78 images, lean toward the vision approach to build the dataset, persisted so it
needn't be redone. Decide and document it. Persist to `.cache/web_screens.json` and export
`data/google_search_results.xlsx`.

## Task 2 — keep the two datasets independent, then unify
The **Maps** dataset (`google_maps_results.xlsx`) and the **Google-search** dataset
(`google_search_results.xlsx`) must be developed **separately and independently** — do not mix them
while building. Once both are complete, write a **separate unify script** that merges the two Excel
sheets into a unified per-clinic view (e.g., `data/unified_results.xlsx`), keyed by clinic, combining
Maps presence/score signals with the search-presence signals (sponsored? which platforms rank?
AI-overview mention? own-site ranking?). This unified dataset is what should feed the **40% Google-web
term** of the opportunity score (see `vulnerability.blend_final` / `web_relevance_vuln`).

## Working style
Brainstorm the schema + extraction method before building (use the brainstorming skill). Build
incrementally with tests; keep `pytest` green (currently 97); commit frequently to local `master` with
the Co-Authored-By trailer. Match existing conventions (gitignored data, worker-thread Playwright only
where scraping, graceful empty states). Report the 78-vs-80 reconciliation and any clinics with no
search presence (a meaningful signal in itself).
