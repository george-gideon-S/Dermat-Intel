# Spec — Google SERP screenshot → structured dataset → unified web signal

**Date:** 2026-06-30 · **Status:** approved, executing · Derma Intel
Companion: [PROMPT.md](../../../PROMPT.md), [ARCHITECTURE.md](../../../ARCHITECTURE.md), [CLAUDE.md](../../../CLAUDE.md)

## Problem
Live Google **web**-search scraping is hard-blocked (confirmed; that's why this task exists). Instead we
have **78 manually-captured full-page SERP PNGs** for the 80-query set. Turn them into a structured,
clinic-mapped google-search dataset (kept **independent** of the Maps dataset), then unify the two and
feed the **40% Google-web term** of the opportunity score (`vulnerability.blend_final` /
`web_relevance_vuln`).

## Hard constraints
100% free, no API keys, no paid services · Python 3.10 / Windows · never disable TLS · do not re-attempt
live web-search scraping · keep `pytest` green (currently **97**) · commit frequently to local `master`.

## Ground truth (verified this session)
- Corpus: **78 PNGs**, ~1500 px wide, **4,392–11,086 px tall** (avg ~7,464). Dark-mode SERPs.
- Queries: **80** in `.cache/query_rows.json` (rank 1–80). → **2 queries have no screenshot** (reconcile).
- Clinics: `aggregate_clinics(result_rows.json)` → **34 unique** (20 with website, 14 without).
- Maps xlsx (`google_maps_results.xlsx`) is **appearance-level: 750 rows**, not clinic-level.
- The 40% web term is wired in exactly **one** place: `web/build_web.py._attach_web` (loads
  `web_raw.json` → `match_clinics_web` → attaches `web_appearances`+`web_data` → `score_clinics`).
  `run_pipeline.py` has **no** web seam. `web_relevance_vuln` tests pin the current formula exactly.
- Deps: Pillow 10.0.0 present; **Tesseract absent** (no binary, no pytesseract).

## Extraction method (decided)
**Claude vision via the Read tool, on tiled images.** Rationale: OCR needs an absent binary (painful on
this TLS-intercepted machine) and loses block-type semantics (Sponsored / Places / AI Overview); vision
reads SERP structure natively. **Tiling is mandatory** — a full 1500×7464 page downscales to ~8 px text
(illegible); validated that 1500×1600 tiles read at ~native resolution (clinic names, ratings, URLs all
sharp). One-time vision pass → persisted JSON (never redone); everything downstream is a deterministic,
unit-tested script.

## Execution model — hybrid (decided)
1. `screenshot_slicer.py` (Pillow, smoke-tested) slices each PNG into `.cache/web_tiles/<rank>/` at
   **1500×1600, 180 px overlap**, and writes a **manifest** (rank → tiles + screenshot + query).
2. **Lock the schema on a diverse sample** (~6 screenshots spanning Discovery / Condition / Pricing /
   Near-Me / Trust / Booking) read by the orchestrator → finalize fields + a gold example + extraction
   rules. (NOT ranks 1–3, which are near-identical Discovery queries.)
3. **Dispatch parallel subagents** (~8, bounded by tiles-per-agent), each: read its tiles, **write**
   `.cache/web_screens_part_<k>.json`, return a short count summary. Strict shared schema + gold example.
4. **Merge + validate:** dedupe overlap-duplicated blocks by `(block_type, title, position)`;
   schema-check; **spot-check** ≥1 query per agent against the image; reconcile 78-vs-80.

## Schema — `.cache/web_screens.json` (source of truth)
```jsonc
{ "meta": { "num_queries_expected": 80, "num_screenshots": 78, "unmatched_queries": [...],
            "tile_height": 1600, "tile_overlap": 180 },
  "queries": [ {
    "rank": 1, "search_query": "best dermatologist in Guntur",
    "search_box_text": "best dermatologist in Guntur",   // READ from tile-0 → authoritative mapping
    "screenshot": "screencapture-...png", "match_confidence": "exact|order|fuzzy",
    "readable": true,                                      // false if blocked/unreadable capture
    "blocks": [ {
      "position": 1,                          // vertical ordinal on the page (1 = topmost)
      "block_type": "places",                 // sponsored_top|sponsored_mid|places|organic|ai_overview
      "platform": "practo",                   // practo|justdial|lybrate|instagram|youtube|facebook|
                                              //   traya|skedoc|clinic_site|other  (coarse, from domain)
      "title": "...", "url": "", "domain": "",
      "rating": 4.9, "reviews": 611, "snippet": "..."     // when visibly shown
    } ] } ] }
```
**Perception vs identity split:** subagents record only what's on screen (incl. a coarse `platform`
guess). Clinic identity (`mapped_clinic`, `is_own_site`) is resolved later by deterministic code against
the 34 clinics — keeps the fuzzy part minimal and the testable part large.

## Mapping + dataset — `modules/web_screens.py` (pure logic, TDD)
- Reuse `web_collector.domain_of` / `_name_tokens` / `_result_matches_clinic` / `maps_collector.dedup_key`.
- Per block → `mapped_clinic`, `mapped_key`, `is_own_site`.
  - `is_own_site` = block maps to clinic **and** platform ∉ {aggregators ∪ social} (covers both
    domain-match and name-match owned presence, incl. clinics with no Maps website).
- Per-clinic aggregation across the 80 queries:
  - `web_appearances` — queries with **any** appearance (continuity with existing contract).
  - `web_owned_appearances` — queries with an **OWNED** appearance: **own-site organic OR paid ad**.
  - `web_borrowed_appearances` — queries where the clinic appears **only** via aggregator/social.
  - `web_best_position`, `has_own_site`, `in_places_any`, `sponsored_any`, `ai_overview_mentions`,
    `web_data: True`.
- **`places` presence is captured & reported but is NOT "owned web visibility"** — the local pack is
  Maps data re-surfaced; counting it would conflate the independent datasets and double-count the Maps
  60%. (Places still flows into unify as a cross-signal.)
- Export `data/google_search_results.xlsx` (one row per result block: query, rank, block_type, platform,
  title, domain/url, position, mapped clinic, is_own_site). **Independent of Maps.**

## Scoring — `web_relevance_vuln` enrichment (backward-compatible)
```
if not web_data: return None
if owned/borrowed keys absent:   # old/mock/live-collector data
    return round(100*(1 - min(web_appearances/10, 1)))     # UNCHANGED → pinned tests stay green
# presence-weighted path:
owned_v    = min(web_owned_appearances / OWNED_FULL, 1)
borrowed_v = min(web_borrowed_appearances / BORROWED_FULL, 1)
visibility = min(1, OWNED_W*owned_v + BORROWED_W*borrowed_v)   # owned dominates; borrowed ~partial credit
return round(100*(1 - visibility))                            # higher = more invisible = bigger opportunity
```
`OWNED_FULL`, `BORROWED_FULL`, `OWNED_W`, `BORROWED_W` **calibrated after** inspecting the extracted
distribution (80-query corpus), documented inline like prior calibrations. A clinic visible only via
Practo/JustDial stays ~high-invisibility (big opportunity); a clinic whose own site ranks drops low.

## Unify — `unify_results.py` (Task 2, separate; built only after Task 1 commits)
- Maps side: `aggregate_clinics(result_rows.json)` → 34 clinics (clean dedup keys), not a literal
  sheet-join on stuffed names.
- Web side: per-clinic signal from `web_screens.json`.
- Join on `dedup_key` → `data/unified_results.xlsx` (Maps signals ‖ search-presence signals: sponsored?,
  own-site rank?, AI-overview?, platform mix, owned/borrowed counts).
- Expose `web_signal_by_clinic()` returning the per-clinic dict for scoring.

## Wiring (Task 2)
Extend `build_web.py._attach_web` to **prefer the screenshot/unified signal when present** (attach
`web_owned_appearances`, `web_borrowed_appearances`, `web_appearances`, `web_data` + flags), falling back
to `web_raw.json`/`match_clinics_web`. No change to `run_pipeline.py` scoring contract beyond what flows
through `score_clinics`.

## Tests, paths, hygiene
- New: `tests/test_web_screens.py`, `tests/test_unify.py` (fixture JSON — never live vision data).
  Extend `tests/test_vulnerability.py` for the new score branch. **All 97 stay green.**
- Config: add `WEB_SCREENS_CACHE`, `SEARCH_RESULTS_XLSX`, `UNIFIED_XLSX`.
- Gitignore: `.cache/web_tiles/`, `.cache/web_screens*.json`, `data/google_search_results.xlsx`,
  `data/unified_results.xlsx`. Tiles are ephemeral (regenerable, deletable post-pass).

## Sequencing & deliverables
Task 1 end-to-end (slice → vision → dataset xlsx → tests → **commit**), then Task 2 (unify → wiring →
tests → **commit**). Datasets independent while building. Final report: the **2 missing queries** and any
clinics with **zero web presence** (a strong signal in itself).

## Risks / known trade-offs
- Vision variance across subagents → mitigated by shared schema + gold example + spot-check.
- Web-invisibility intentionally overlaps the Maps "no website" gap (two lenses; bounded by 40% blend).
- Coarse `platform` from partly-legible URLs → deterministic re-classification + domain match correct it.
