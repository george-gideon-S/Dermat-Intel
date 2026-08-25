# Next task — the admin automation console

Build the admin control layer that turns a market analysis from a multi-day manual
pipeline into one form submission, and put its output on dated, comparable dashboards.

---

## 0 · Read this first — the project documentation was deleted

The previous session removed the entire UI layer ahead of this rebuild, and that included
`CLAUDE.md`, `ARCHITECTURE.md`, `README.md` and `SESSION_LOG.md`. **Nothing in the repo
explains itself any more.** Everything you need is either in this file or recoverable from
git history (`git show edf35eb^:CLAUDE.md`). Start by reading the surviving code.

### What survives, and what it does

| Path | Role |
|---|---|
| `modules/maps_collector.py` | **The Google Maps scraper.** Playwright, worker-thread, consent handling, glyph cleaning, dedup by CID, cross-query detail cache, OSM geocode fallback, `mock=True` mode |
| `modules/reviews_collector.py` | Google Maps reviews scraper — resume-safe, throttle backoff |
| `modules/query_generator.py` | Builds and parses the query set; derives category / user-intent / search-strength |
| `modules/web_collector.py` | Google **web** SERP collector (headful — see the blocker below) |
| `modules/web_screens.py` | Turns SERP screenshots into a structured dataset; owned-vs-borrowed visibility |
| `modules/screenshot_slicer.py` | Tiles tall SERP screenshots into legible chunks |
| `modules/vulnerability.py` | **The scoring system** (detailed in §4) |
| `modules/reviews_nlp.py` | Free VADER sentiment, themes, pain points, referral rate |
| `modules/analytics.py`, `modules/report.py` | KPI/data-prep and the clinic-facing report content |
| `modules/unify_results.py` | Merges the Maps view and the web signal per clinic |
| `modules/storage.py` | The JSON state store — **see §5, this is what has to change** |
| `run_pipeline.py` | Headless runner: scrape → score → export. `--mock` works offline |
| `collect_extras.py` | Reviews + web collection |
| `design/` | 15.3 MB of brand/reference material. **Preserve.** |
| `tests/` | 133 passing tests |

Deleted and **not** to be resurrected: `web/`, `components/`, `app.py`, `derma_web.py`,
`docs/`. A new UI is being designed separately.

### Non-negotiable constraints

1. **No paid APIs. No API keys. Ever.** Free and local tools only. This is foundational.
2. **Never disable TLS verification.** No `NODE_TLS_REJECT_UNAUTHORIZED=0`, no
   `http.sslVerify=false`.
3. `modules/` is the asset. Extend it; do not rewrite what already works.

### Environment gotchas that have already cost days

- **TLS interception on this machine breaks HTTPS for Python `requests` and npm.** `curl`
  works, because it uses schannel and the Windows certificate store. Shell out to curl for
  downloads. For `requests`, pass `verify=` the exported cert bundle.
- **This machine runs the embeddable Python distribution.** Its `python310._pth` forces
  isolated mode: the script's own directory is **not** added to `sys.path` and `PYTHONPATH`
  is ignored. Every entry point needs the explicit bootstrap that `conftest.py`,
  `run_pipeline.py` and `collect_extras.py` already carry. The interpreter is
  `C:\Users\SALE PITCHAIAH\AppData\Local\Programs\Python\Python310\python.exe` — plain
  `python` on PATH is broken.
- **Playwright's sync API refuses to run on a thread that already has an asyncio loop.**
  Every scraper wraps its browser work in a worker thread (`_run_browser`). Any async web
  framework you choose will hit this — reuse the existing pattern.
- **Google Maps throttles rapid review requests.** Backoff, CID-URL fallback, never cache
  empty results, resume by re-running.

---

## 1 · The product

An operator opens an admin console, fills in five fields, and presses one button. The system
then generates the query set, scrapes every source, scores the market, and publishes a dated
snapshot to a dashboard — with no further human involvement.

Analyses are re-run **quarterly**. Every run is a new dated snapshot; **old snapshots stay
readable forever**, so a clinic can see where it stood in March and where it stands now.

**The existing Guntur dermatology data is over a month old. Treat it as the first historical
snapshot, and run a fresh analysis for today as the second** — that pair is what proves the
time-series works.

---

## 2 · The intake form — five fields

| # | Field | Notes |
|---|---|---|
| 1 | **Area** | City / town / village / metro, plus state. Free text |
| 2 | **Practice** | Dermatology, cardiology, orthopaedics, neurology, … |
| 3 | **Subject type** | `individual clinics` · `multi-speciality hospitals` · `both` |
| 4 | **Query threshold** | How many distinct queries to run. Pre-filled from research (§3) but operator-editable |
| 5 | **Snapshot date** | Defaults to today |

**Why field 3 exists, and what it changes downstream.** We analyse *one practice in one
area*, but a multi-speciality hospital runs many practices at once. It will therefore
out-rank a solo practitioner on volume signals that say nothing about dermatology
specifically. Decide explicitly how the scoring treats the two populations — separate
leagues, a normalising factor, or a hard filter — and make the choice visible in the output
rather than buried in the maths.

---

## 3 · Query generation, and the threshold research

**Research the right query threshold per practice, and make the research good.** The number
must be defensible, not guessed. Base it on how many distinct conditions, treatments and
buying intents a specialty actually has — dermatology's surface is far wider than, say,
nephrology's. Bias upward: too many queries costs runtime, too few produces a biased market
picture. Record the reasoning per practice so the number can be defended later.

Two hard rules for the generated queries:

- **Ask the same condition several ways.** Real patients phrase the same need very
  differently ("hair fall treatment", "hair loss doctor", "why is my hair thinning"). One
  phrasing per condition under-samples the market.
- **Never include "near me".** That phrase resolves against the *searcher's* location, so
  results depend on where the query is run from rather than on the target area. It makes
  runs irreproducible and snapshots incomparable — which destroys the whole point of a
  time series.

---

## 4 · Extraction — three sources

**a. Google Maps.** Everything per clinic: name, address, phone, website, rating, review
count, review text, coordinates, category, hours. `modules/maps_collector.py` already does
this and works headless.

**b. Google web search.** All organic results, ads, local pack and AI overview blocks.

> ⚠️ **The blocker that decides whether "one click" is honest.** Google web search is
> **hard-blocked headless** — every method tried returned an instant `/sorry` reCAPTCHA
> (requests with `gbv`/`igu`, headless Playwright, real Chrome, stealth plugins, every URL
> variant). The *only* thing that has ever worked is **headful with a human solving the
> CAPTCHA**, using a persistent profile so it is solved once or twice per session.
>
> **Do not promise full automation of this step before proving it.** Either find a
> genuinely working free path, or design the console to pause and hand this one step to the
> operator, then resume automatically. An honest semi-automated pipeline beats a fully
> automated one that silently returns nothing.

**c. Third-party health blogs — new work.** After the web results are in, identify results
that are *not* clinic sites: aggregators and editorial "best dermatologists in X" listicles.
Open them and harvest the practitioners they recommend. This surfaces clinics that rank
nowhere themselves but are being recommended by others, and it is how borrowed authority
gets measured.

**Search GitHub for existing free tooling before building any scraper from scratch** — there
is mature open-source work in this space. Evaluate against the no-paid-API rule and the TLS
constraint above.

---

## 5 · The scoring system

The current score is **0–100 = 0.6 × Maps + 0.4 × Web**, where higher means a bigger gap
between local demand and online presence:

- **Maps** = *gap* (max 58: no/weaker website 22, buried below avg position 7 → 12, few
  reviews 10, weak rating 8, no phone 6) + *reach* (max 42: demand 16, high-intent share 14,
  central location 12).
- **Web** = invisibility, where **owned** (your own domain ranking, or a paid placement you
  control) beats **borrowed** (Practo, JustDial, social) and places-only counts as invisible.
- Labels: Critical 80+ · High 60–79 · Medium 40–59 · Low 0–39.

**It is calibrated for dermatology in Guntur.** Before it is applied to another practice or
another city, decide what is universal and what is local — review-count thresholds and
"central location" in particular are city-shaped. State the calibration per snapshot so two
snapshots are only ever compared on the same basis.

**Framing matters: the product is sold to the clinics themselves.** Language is
opportunity/diagnostic, never accusatory. Severity uses a calm sand-to-clay palette, never
red.

---

## 6 · The data model — the part that does not exist yet

Today `modules/storage.py` writes flat JSON to `.cache/` and **overwrites it on every run**.
There is exactly one snapshot and no history. Quarterly re-runs with permanent access to
prior results cannot be built on that, so this is the foundational change.

Design a store keyed by **(area, practice, subject type, snapshot date)** that:

- keeps every historical run immutably;
- lets a dashboard load "the run from 12 March" as easily as "the latest";
- supports "what changed between two snapshots" per clinic (rank moved, reviews gained,
  website appeared) — the delta is the most valuable thing a returning client sees;
- survives a schema change, since the scoring will evolve between quarters. Version each
  snapshot with the scoring rules that produced it, or old dashboards will silently
  re-render under new maths and show movement that never happened.

---

## 7 · The dashboards

- Every (area, practice) pair has a dashboard, updated when a fresh analysis publishes.
- A **timeline dropdown** — last 3 months / 6 months / 1 year / all — selects which
  snapshot(s) are shown.
- Historical snapshots stay accessible to any clinic, permanently.
- Show change over time, not just current state.

Note that the UI is being redesigned separately. **Build the backend so the dashboard is a
consumer of a clean API, not a renderer coupled to the pipeline** — that coupling is what
the deleted UI got wrong.

---

## 8 · Deliverable

**A frontend and a backend for the admin console**, wrapping the surviving `modules/` rather
than replacing them.

- **Backend:** an API over the intake form, the pipeline, the snapshot store, and the
  dashboard queries. Runs are long — return a job id and stream progress; do not block a
  request for a scrape that takes an hour.
- **Frontend:** the five-field form, live run progress with per-stage status, a run history,
  and the ability to re-run or roll back a snapshot.
- **Failure is normal, not exceptional.** Scrapes get throttled, CAPTCHAs appear, networks
  drop. Every stage must be resumable and must report *what* failed and *what partial data
  survived*. `maps_collector` is already resume-safe — preserve that property end to end.

---

## 9 · Decide these before building

1. Does the web-search CAPTCHA get solved automatically, or does the console pause for an
   operator? This shapes the whole architecture.
2. Where does the snapshot store live — SQLite, Postgres, versioned files?
3. How do multi-speciality hospitals score against individual clinics?
4. Which parts of the scoring are universal and which are recalibrated per area/practice?
5. What is the run cadence enforcement — is the quarterly cycle scheduled, or operator-triggered?

---

## 10 · Done means

- One form submission produces a complete, dated, published snapshot with no manual steps
  beyond any CAPTCHA explicitly designed for.
- The month-old Guntur dermatology data is loaded as a historical snapshot, and a fresh
  run for today sits beside it.
- The dashboard's timeline dropdown moves between them and shows what changed.
- `pytest` is green, and the new logic is tested to the standard `modules/` already sets.
