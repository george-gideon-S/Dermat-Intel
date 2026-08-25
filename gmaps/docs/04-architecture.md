# Architecture, files and paths

Where everything lives, what each piece is responsible for, and how data flows.

---

## Design principles

1. **Data, not code.** A new city or specialty is a JSON file. Nothing market-specific or
   specialty-specific is compiled into logic.
2. **Decide before you spend.** Relevance is judged from the free results card, so the expensive
   page-open only happens for clinics worth opening.
3. **Absence must be explainable.** Every empty field says whether it was empty at the source or
   never looked at.
4. **Nothing may hang.** Every page operation has a timeout; every loop has a wall-clock budget.
5. **Crash-safe writes.** Each clinic is its own file, written temp-then-rename.

---

## File layout

```
gmaps/
  run.py           the command you run: orchestration, resume, status, summaries
  extract.py       feed reading, tier decision, place extraction (full + card-only)
  cards.py         results-card parser — the free tier of data
  taxonomy.py      relevant / adjacent / not relevant, for any specialty
  fields.py        name cleaning, website classification, stable identifiers
  packs.py         pack loading, query composition, URL building
  ui.py            local live-progress page (small web server)
  packs/
    base.json                     universally irrelevant categories
    geographies/guntur-ap.json    city, admin area, timezone, viewport, chain domains
    specialties/*.json            10 specialties
  docs/            this documentation

archive/gmaps_v1_2026-08-20/      the previous implementation, preserved
  tools/, modules/                the v1 scripts
  probe_evidence/*.html           real captured DOM — lets selectors be re-verified offline,
                                  without touching Google
```

### Module responsibilities

| Module | Owns | Deliberately does NOT |
|---|---|---|
| `cards.py` | parsing one results card | know about specialties or open pages |
| `taxonomy.py` | the relevance verdict | touch a browser |
| `fields.py` | name/website/ID derivation | know the market or specialty |
| `extract.py` | browser interaction, both tiers | decide run policy or write files |
| `run.py` | orchestration, resume, status | parse HTML |
| `packs.py` | loading config, composing the query | scrape |

`taxonomy.py`, `fields.py` and `cards.py` are **pure** — no browser, no network — which is why
they can be tested offline against saved HTML.

---

## Data flow

```
packs/  ──►  packs.load()  ──►  RunContext (city, specialty, query, timezone, hl/gl)
                                     │
                                     ▼
                    run.py opens Maps ──► scroll to end of list
                                     │
                                     ▼
                    extract.read_feed() ──► cards.parse_feed()
                                     │              (free: name, category, rating,
                                     │               booking, closed status, place_id)
                                     ▼
                    taxonomy.classify() per card  ──►  tier decision
                          │                                    │
                 relevant/adjacent                      not relevant
                          │                                    │
                          ▼                                    ▼
             extract.extract_place()               extract.card_only_record()
             (Overview + About + ALL reviews)      (card data only, 0 seconds)
                          │                                    │
                          └──────────────┬─────────────────────┘
                                         ▼
                            places/<place_id>.json   (one file per clinic)
                                         │
                                         ▼
                          data.json + status.json  ──►  ui.py live page
```

---

## Output layout

```
runs/gmaps/<geo>_<specialty>_<YYYY-MM-DD>/
  manifest.json     what was run: query, packs, city, timezone, counts, timings
  feed.json         every card as captured, plus feed_end_reason
  status.json       live progress: done/total, elapsed, current clinic, errors
  data.json         one compact row per clinic — what the live page reads
  places/
    ChIJ....json    one file per clinic, full detail including every review
```

**Why one file per clinic:** a crash costs at most the clinic in flight; resume is a directory
listing; and no single large file can be corrupted by an interrupted write.

**Why `data.json` is separate:** the summary is small enough to poll every 3 seconds. Full review
text lives in the per-place files and is fetched only when a card is expanded.

---

## Identity

The registry key, in order of preference:

1. `place_id` — `ChIJCfMja_F1SjoRTfRlLzq-oFA`
2. `feature_id` — `0x3a4a75f16b23f309:0x50a0be3a2f65f44d`
3. a normalised-name fallback

Both primary forms come free from the result link and are **locale-independent**. They survive a
clinic renaming itself, which names and URLs do not — and that is precisely what a quarterly
comparison depends on. **A name or an address must never be an identity key.**

Google sometimes lists the same place twice in one feed (measured: `SITARA SKIN AND LASER` at
ranks 19 and 21). Duplicates are detected by key, the better rank is kept, and the duplicate is
retained in `feed.json` marked `dup_of_rank` — kept for provenance rather than silently dropped.

---

## Timeouts and budgets

| Limit | Value | Why |
|---|---|---|
| Page operation | 15s | nothing waits forever on a selector |
| Navigation | 45s | |
| Reviews per clinic | 7 min | a 639-review clinic takes ~2 min; the ceiling catches pathological cases |
| Whole clinic | 10 min | hard stop |
| Feed scroll | 7 min | |

The earlier version had no wall-clock budgets and **froze for over 10 minutes on a single
clinic**, stalling the entire run. Every loop now checks elapsed time, not just iteration count.

---

## Environment constraints (this machine)

- **Use the full interpreter path.** `python` on PATH is a broken Windows Store alias:
  `C:\Users\SALE PITCHAIAH\AppData\Local\Programs\Python\Python310\python.exe`
- **`python -m gmaps.run` does not work.** This is the embeddable distribution running in isolated
  mode, so the working directory is not on `sys.path`. Invoke by path — `gmaps/run.py` carries a
  bootstrap that adds the repo root itself.
- TLS interception breaks some HTTPS clients; the browser is unaffected.
- Playwright drives Maps successfully headless. (The *Google-search* side needs a different driver
  — that is a separate part of the product.)

---

## Relationship to the rest of the project

This package covers **Google Maps only**, and is intentionally separate from the Google-search
work. Maps supplies the clinic universe — who exists, contact details, reviews. Google search
supplies visibility — who ranks for which patient query. The condition-query lists inside the
specialty packs belong to that other half and are unused here.
