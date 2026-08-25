# Running it, and what can go wrong

Operational guide: commands, timings, recovery, and an honest list of what is still broken.

---

## Running a survey

Always invoke by **path**, never `-m` (see Environment below).

```bash
"C:/Users/SALE PITCHAIAH/AppData/Local/Programs/Python/Python310/python.exe" gmaps/run.py --geo guntur-ap --specialty dermatology
```

Useful flags:

| Flag | Effect |
|---|---|
| `--list-packs` | show available cities and specialties |
| `--limit N` | first N results only — use this to smoke-test before a real run |
| `--query "..."` | override the search text |
| `--out DIR` | choose the run directory |
| `--incremental` | quarterly re-run: stop each clinic's reviews at the first already-known review |
| `--headful` | show the browser (useful when something looks wrong) |
| `--pace SECONDS` | delay between clinics (default 3) |

### The live page

```bash
"C:/Users/SALE PITCHAIAH/AppData/Local/Programs/Python/Python310/python.exe" gmaps/ui.py --run runs/gmaps/<run-dir> --port 8765
```

Opens `http://127.0.0.1:8765/index.html`. Refreshes every 3 seconds, shows an elapsed timer, and
adds clinics as they are captured **without losing your scroll position or any card you have
open**. Filters for not-relevant, missing fields and category mismatches; reviews load on demand
when a card is expanded.

---

## What a run costs

Measured, not estimated (98 places, Guntur dermatology):

```
one clinic  ≈ 40 seconds fixed  +  0.18 seconds per review
```

| | |
|---|---|
| Full Guntur dermatology run | **116 minutes**, 98 places, 12,777 reviews |
| Clinics never opened (not relevant) | 12 → about 8 minutes saved |
| Longest single clinic | 136 s (639 reviews) |

The fixed page-open dominates, which is why *not opening* an irrelevant clinic is worth far more
than skipping its reviews. Savings scale with how off-target the search is:

| Specialty on the same feed | Opened | Skipped | Saved |
|---|---|---|---|
| Dermatology | 86 | 12 | ~8 min |
| Dentistry | 41 | 57 | ~38 min |
| Cardiology | 30 | 68 | ~45 min |

**Quarterly re-runs should be far cheaper** with `--incremental`: reviews are read newest-first
and stop at the first already-known review, so only genuinely new reviews are fetched. *(Designed
and implemented; not yet measured on a real second quarter.)*

---

## If a run is interrupted

Just run the same command again.

Every finished clinic is already on disk and is skipped. Incomplete ones and error stubs are
retried. Writes are temp-then-rename, so a kill mid-write cannot leave a half-written file.

To force one clinic to be redone, delete its file from `places/`.

---

## Reading the health of a run

Before trusting any output, check these four:

| Check | Where | Bad sign |
|---|---|---|
| Did the feed complete? | `feed.json` → `feed_end_reason` | `budget_exhausted` means the market was not fully seen |
| How many failed? | `status.json` → `errors` | anything above zero deserves a look |
| Are reviews complete? | per-place `reviews_coverage` | well below 1.0 |
| Do the stars add up? | `histogram_reconciles` | `false` |

---

## Known defects — read before trusting a run

Found by adversarial testing. **These are real and currently unfixed.**

### 🔴 Critical — a totally failed scrape reports success

If Google changes the results markup, the scroll finds zero cards and the run writes
`finished: true, errors: 0` with zero places, exiting cleanly. **A broken scrape is
indistinguishable from a town with no clinics**, and a dashboard would present the empty market as
fact.

*Fix required:* abort with a non-zero exit when the feed is empty or implausibly small, and record
a `run_health` verdict in the manifest.

### 🔴 Critical — finished snapshots are not immutable

Nothing prevents a later run writing into a completed run's directory. Individual clinic files
survive (they are skipped as complete), but the run's `manifest.json` and `status.json` are
overwritten — `finished_at` is destroyed and the snapshot stops reporting as finished.

For a quarterly product whose whole value is comparing June with September, this is the most
dangerous gap in the system. The previous implementation (`modules/runstore.py`) had
`finalize_run()` and a `RunFinalized` exception; that guarantee has not yet been ported.

*Fix required:* finalize a completed run and refuse writes into it.

### 🟠 High — closed businesses were being dropped

`cards.py` reads `permanently_closed` / `temporarily_closed`, but they were not carried into the
saved record, so a shut-down clinic looked like a live competitor. **Fixed** — both flags plus
the permanently/temporarily-closed flags are now carried through for opened clinics. The
moment-in-time `status_text` / `open_now` fields are deliberately NOT collected. No page-level
business status is read yet, so a clinic marked closed only on its own page can still slip through.

### 🟡 Medium — many failures are swallowed silently

Numerous `except Exception: pass` blocks mean *"no About section"* and *"About extraction crashed"*
currently look identical, as do a missing hours table, missing topics, and a failed aria-label
sweep (which would leave rating, review total and histogram all empty).

*Fix required:* record a per-field extraction status rather than an indistinguishable empty.

### 🟡 Medium — no run index

There is no `runs/index.json`, so a dashboard cannot enumerate available snapshots without
scanning directories.

### ⚪ Unverified assumptions

- **The 10 specialty packs**: only dermatology's category vocabulary is checked against live data,
  from one Indian tier-2 city. The other nine are plausible but unproven.
- **`hl=en` result invariance**: whether Google returns the same result *set* in a non-English
  market under an English interface is untested.
- **Machine-translated reviews**: if Google auto-translates a review under `hl=en`, the review ID
  is unchanged, so nothing in the pipeline would notice.
- **Ad detection**: `is_ad` exists but no ads appeared in the capture, so it has never fired.

---

## Environment

| Constraint | Consequence |
|---|---|
| `python` on PATH is a broken Windows Store alias | always use the full interpreter path |
| Embeddable distribution, isolated mode | **`python -m gmaps.run` fails** — invoke `gmaps/run.py` by path |
| TLS interception on this machine | affects some HTTPS clients, not the browser |
| Playwright headless works for Maps | the Google-*search* half needs a different driver |

## Adding a city or a specialty

**City:** copy `packs/geographies/guntur-ap.json`, change city, admin area, timezone, viewport
coordinates and `gl`. Include the admin area — a bare place name is ambiguous across states and
countries.

**Specialty:** copy any file in `packs/specialties/`, set the relevant / adjacent / irrelevant
category lists using real Google Business Profile category names, plus `name_strong` and
`name_veto` tokens. On first use in a new specialty, run with `--limit 20` and check the verdicts
before committing to a full run.

## Re-verifying selectors without touching Google

`archive/gmaps_v1_2026-08-20/probe_evidence/` holds real captured DOM — the results feed, a place
Overview, a reviews pane and an expanded hours table. Selector changes can be tested against those
offline, which is both faster and avoids the throttling that repeated live probing triggers.
