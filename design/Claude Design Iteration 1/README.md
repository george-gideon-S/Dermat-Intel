# Claude Design Iteration 1 — Derma Intel

Design output for **The Market Page**, the brand identity system behind it, and the
evidence it was derived from. Drop this folder at the repo root.

Produced against `master` on 2026-08-26. Governed by `CLAUDE.md`: free and keyless
throughout, degrade loudly, and no generated imagery of a real clinic.

---

## What is here

| File | Stage | What it is |
|---|---|---|
| `01 Evidence Board.dc.html` | 1 | What is measurably *in* the reference image. 16 sampled hex values with source coordinates, geometry, type ratios, and the fog dissected by row-scanning the pixels. Ends with seven corrections to the brief's own reading of the reference. |
| `02 Direction Board.dc.html` | 2 | Colour, three type roles, the 92-glaze rule, two competing wireframes, the widget-to-list answer, the one real risk — then a self-critique against what a generic dark-map brief would produce. |
| `03 Token Board.dc.html` | 3 | Every value the build reads, plus a **plain copyable token block** at the bottom (deliverable §8.1). Includes the measured WCAG contrast table that changed the palette. |
| `04 Atmosphere Assets.dc.html` | 4 | The three generated plates with verbatim provenance — purpose, model, exact prompt, job id, date — and the record of what failed. |
| `05 Market Page Comps.dc.html` | 5 | Eight full-fidelity 1920×1080 comps plus twelve storyboard frames for the two motions. |

Open any `.dc.html` directly in a browser. `support.js` must sit beside them.

## Directories

- `assets/map/guntur-basemap-v3.png` — the dark basemap. Real OpenStreetMap geometry,
  45 tiles at z15, every pixel reclassified into the token palette. Baked at
  lat 16.28208–16.32992, lng 80.39300–80.47700, 1848×1097. **Dots and terrain share
  this one projection** — change the bounds and the dot maths in comp 05 must change with it.
  © OpenStreetMap contributors.
- `assets/atmosphere/` — grain, fog and cover plates. Abstract only.
- `data/market.json` — the 20 Aug 2026 snapshot joined with `feed.json` coordinates:
  92 clinics with name, phone, rating, reviews, address, lat/lng, relevance, website flag.
- `evidence/` — zoomed crops of the reference used on the Stage 1 board.
- `ref/` — the two reference images, copied from `design/Design Inspiration/`.

## Facts every screen is built on

Verified against `data.json`, `feed.json` and `manifest.json` — not restated from the brief.

- 92 places · 50 relevant · 31 adjacent · 11 irrelevant
- 48 relevant clinics carry a rating · mean **4.590** · median 72.5 reviews · max 773
- **35 of 48 have no website of their own**
- Coordinate bounds lat 16.2176–16.5124, lng 80.3450–80.6387
- **All 92 places have coordinates.** The missing-coordinate row state is therefore a
  designed contingency with no instance in this run, and comp 07 says so on its face.
- `run_health: partial` · 9 review-pane failures · 10 card-only records

## Two things the data corrected in the brief

1. **The flat-scale problem is inverted, not flat.** 14 of 48 clinics sit *below* 4.6;
   the compression is at the top. Twelve sit at exactly 5.0 with a median of 82 reviews
   against a market median of 73 — so *Dr Vijay's Skin and Dental Clinic* (5.0, one review)
   outranks *Chandana Skin Clinic* (4.6, 385 reviews) on any five-star scale. This is why
   the vernier exists, and why no rating is ever drawn without its confidence weight.

2. **Fitting the map to the stated bounds destroys the city.** 87 of 92 clinics sit inside
   a 4.5 km box; five are spread across 33 km. The default view fits the core and holds the
   five outliers as off-frame bearing chips rather than dropping them.

## Still to come

Stage 6 (the guide, 16 sections), Stage 7 (the booklet + PDF), Stage 8 (final critique),
and the nine page docs of deliverable §8.2.
