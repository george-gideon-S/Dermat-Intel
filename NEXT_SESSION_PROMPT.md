# Build the admin automation — a one-click market-intelligence engine

> **This is a loop, not a prompt.** You are not writing code once and stopping. You run
> research → spec → build → adversarial review → test → prove-on-live-data, and you keep
> looping a module until it survives its own tests. Roles below.

---

## 0 · Where you are starting from

The UI layer was deleted deliberately. A full redesign is coming; **do not rebuild any
frontend until explicitly told to.**

**What survives and works:**

| Path | What it is |
|---|---|
| `modules/maps_collector.py` | **The working Google Maps scraper.** Playwright, consent handling, glyph cleaning, CID dedup, detail cache, OSM geocode fallback. This is the proven asset — extend it, do not rewrite it from scratch. |
| `modules/reviews_collector.py` | Google Maps reviews scraper, resume-safe, throttle backoff |
| `modules/query_generator.py` | Builds and parses the query set |
| `modules/storage.py` | JSON state store |
| `modules/vulnerability.py` | Internal opportunity score (higher = weaker prospect) |
| `modules/report.py` | Clinic-facing visibility score 0–100 (higher = more findable) |
| `modules/web_collector.py` | Google **web** search scraper — *partially broken, see §4* |
| `modules/web_screens.py`, `screenshot_slicer.py` | The manual-screenshot fallback that §4 must replace |
| `modules/analytics.py`, `reviews_nlp.py`, `unify_results.py` | Aggregation, review NLP, merge |
| `run_pipeline.py`, `collect_extras.py`, `config.py` | CLI entry points and settings |
| `design/` | 15.3 MB of reference imagery — **do not touch** |
| `tests/` | 133 passing tests |

**What was deleted** (recoverable from git at `2ff72b3` if the redesign wants it): the entire
`web/` dashboard, the Streamlit app, and `docs/` including a *measured* brand atlas and
`palette.json` derived from sampling the reference images. Retrieve those before inventing a
new palette from nothing.

---

## 1 · What the product does

One admin fills a form, hits enter, and a complete market analysis for a geography +
specialty runs end to end and lands in a dashboard. Today that work is manual and takes days.

**The input form:**

1. **Geography** — city / town / village / metro area, plus state.
2. **Practice** — the medical specialty (dermatology, cardiology, orthopaedics, neurology…).
3. **Subject type**, because a single-specialty clinic and a multi-specialty hospital are not
   comparable units:
   - individual practitioner clinics
   - multi-specialty hospitals
   - both
4. **Query threshold** — how many distinct search queries to run (see §2).

**Then, unattended:** generate queries → scrape Google Maps → scrape Google web search →
follow third-party listicles → score → write a timestamped snapshot → refresh the dashboard.

---

## 2 · Query generation — research task, not a constant

Do not guess the thresholds. **Research a defensible query count per specialty** and justify
each number from evidence, not intuition. Bias high: a thin query set produces a confident
wrong answer, which is worse than a slow one.

Rules that survived the last build and still apply:

- **Ask each condition several ways.** Patients phrase the same need very differently
  ("hair fall treatment", "hair loss doctor", "baldness specialist"). One phrasing per
  condition under-samples the market.
- **Never use "near me".** It resolves against the searcher's own location, which makes the
  result set depend on where the scraper is sitting rather than on the market. It poisons
  every comparison.
- Queries are currently tuned for **Andhra Pradesh**. Treat the phrasing set as
  **demographic configuration**, not hardcoded strings — expansion to other regions must be a
  config change, not a code change.

---

## 3 · Extraction sources

1. **Google Maps** — the full record per clinic: name, rating, review count, reviews, phone,
   website, address, coordinates, place URL. `maps_collector.py` already does this well.
2. **Google web search** — the organic results, local pack, ads and AI overviews for each
   query. **This is the part that is broken.** See §4.
3. **Third-party listicles** — after the web results are in, identify non-clinical sites
   (health blogs, "best dermatologists in X" roundups, directories), open them, and extract
   the practitioners they recommend. These shape local reputation and are invisible to a
   Maps-only view.

**Free and keyless.** No paid APIs, no billing, no trial keys. That constraint is
load-bearing — the product's margin depends on it.

---

## 4 · The hard problem: Google web extraction

**Be precise about what failed, because "it didn't work" hides the actual obstacle.**

`web_collector.py` scrapes Google web search, but **Google blocks headless browsers.** It
needs a headful browser and a human CAPTCHA solve. The previous build worked around this by
having a person capture SERP screenshots manually, tiling them with `screenshot_slicer.py`,
reading them with vision, and aggregating in `web_screens.py`. That produced **1,122 result
blocks across 78 SERPs** — real data, and roughly 40% of every clinic's score. It is also
entirely manual, which is incompatible with "one click".

**Your task: find the breakthrough.** Research hard and widely — GitHub, Medium, X, HN,
scraping communities. Evaluate and actually test the candidate approaches:

- Mature open-source SERP libraries and their current block rates
- Undetected/stealth browser automation and browser-fingerprint evasion
- Alternative surfaces exposing the same data (non-Google engines with comparable local
  coverage, syndicated indices, public datasets)
- Residential/rotating egress, request pacing, session warming
- Hybrid: cheap automated bulk with a human step only on hard blocks

**Judge candidates on:** success rate over a real 80-query run · cost (must be free) ·
fragility (how fast does it break when Google changes) · legal and ToS posture · whether it
degrades gracefully or fails silently.

**Do not report success from a 5-query smoke test.** Prove it at full scale, twice, on
different days.

---

## 5 · Data model — snapshots, not overwrites

Every run writes a **timestamped snapshot**, and nothing is ever overwritten. Cadence is
roughly **quarterly**, and a clinic must be able to read its own history.

- Snapshot key: `(geography, practice, subject_type, run_date)`
- The dashboard gets a **timeline selector** — last 3 months / 6 months / 1 year / all
- Comparison across snapshots is the actual product value: *is this clinic gaining or losing
  ground?* Design the schema so a diff between two snapshots is cheap and obvious.

**Your first acceptance test is already sitting in the repo.** The existing Guntur
dermatology data is over a month old. Treat it as **snapshot #1**, run a fresh analysis today
as **snapshot #2**, and prove the time-series, the diff and the timeline selector all work on
real data rather than on fixtures.

---

## 6 · Scoring

A scoring system already exists and is tested — **understand it before replacing it.**

- `vulnerability.py` — internal opportunity score, *higher = weaker = better sales prospect*
- `report.py` — clinic-facing visibility 0–100, *higher = more findable*; a 60/40 blend of
  Maps and Web signal, with a six-component breakdown (website 30 · search 30 · maps 15 ·
  reviews 15 · phone 5 · breadth 5)

The two scores point in **opposite directions** by design. Never mix them in one surface.

**Traps confirmed by measurement in the last build — do not rediscover them the hard way:**

- **Rating is nearly useless.** 28 of 34 Guntur clinics sat between 4.8 and 5.0. It cannot
  differentiate; never build a ranking on it.
- **AI overviews had zero local clinics** across 39 blocks. Worth reporting as a market fact,
  worthless as a per-clinic metric.
- **Review NLP rested on ~10 reviews per clinic, with no dates.** Never present it as trend
  or as deep analysis.
- **Three denominators, never conflate them:** 50 Maps queries · 78 captured SERPs · 80 total
  queries. Every figure must state which one it is counting against.

---

## 7 · Build order — backend first, and stop

**Backend only.** When the backend is complete, verified and demonstrated, **stop and wait.**
Do not begin the frontend until explicitly told to go ahead.

Suggested sequence:

1. Research spike on §4 — nothing else matters if Google extraction stays manual
2. Query generation + threshold research (§2)
3. Extraction orchestration: Maps → web → listicles, resumable, rate-limited
4. Snapshot schema and storage (§5)
5. Scoring integration (§6)
6. The one-click job runner: form input → queued job → progress → completed snapshot

---

## 8 · The loop

Run this as a multi-agent loop, not a single pass. Roles:

- **Researchers** — find and evaluate approaches; bring evidence and working code, not links
- **Builders** — implement one module at a time against a written spec
- **Adversarial reviewers** — try to *break* what the builders produced; assume it is wrong
  and prove it
- **Test authors** — write tests that would fail if the module were subtly broken, not tests
  that restate the implementation
- **Test runners** — execute against live data and report what actually happened

**A module is done when:** its tests pass · a reviewer failed to break it · it ran on real
data at full scale · and its failure modes are known and handled.

**Loop until dry:** keep iterating a module while reviewers are still finding real defects.
Two consecutive clean rounds means move on.

---

## 9 · Verification — the standing rule

**Never assume it works. Prove it.**

Write tests that check for what was *missed*, not just what was produced: silently skipped
queries, dropped clinics, partial pages, truncated result sets, retries that swallowed an
error, a scrape that "succeeded" with zero rows. Prefer a test that reproduces a real failure
over ten that assert happy paths.

When you report status, report what you measured. If something is unverified, say so.

---

## 10 · Environment — this machine will bite you

- **`python` on PATH is broken.** It resolves to a Windows Store alias pointing at a missing
  miniconda. Use:
  `C:\Users\SALE PITCHAIAH\AppData\Local\Programs\Python\Python310\python.exe`
- **That runtime is the embeddable distribution** with a hand-written `python310._pth`, which
  forces isolated mode: a script's own directory is **not** added to `sys.path` and
  `PYTHONPATH` is **ignored**. `run_pipeline.py` and `collect_extras.py` already carry a
  bootstrap; **every new entry point needs the same three lines** or it cannot import
  `config`.
- **TLS interception breaks `requests` and npm** on this machine. **`curl` works** — it uses
  schannel and the Windows certificate store. **Never disable TLS verification.**
- **Playwright is installed and working** — it is how Maps scraping already succeeds.
- Windows Defender is disabled by a rogue antivirus registration (`dnot.sh`). Known,
  unresolved, does not block the work.
- Secrets live in a gitignored `.env`. Never inline a key on a command line.

---

## 11 · Bring back decisions, do not silently make them

Surface these rather than choosing alone: the Google extraction approach and its trade-offs ·
per-specialty query thresholds and the evidence behind them · the snapshot schema · anything
that would cost money · anything that changes the meaning of an existing score.
