# V0 · Card inventory + grid system — the v4 gate document

> **Status: APPROVED by George, 2026-08-15 — the 35 cards as listed, no trims.**
> Open question 2 (the "AI answers" tile) stays **rejected** as written; open question 3 (the
> raster amendment) is **deferred to V4**, where it only becomes live if the generated-gradient
> background actually wins the comparison.
> Approved plan: `~/.claude/plans/the-current-website-feels-bubbly-gosling.md`. Every data path
> below exists in the shipped payload (`window.__DATA__`, 192.8 KB, 34 clinics) — 71 paths
> verified against `web/build_web.py` / `web/views.py` / the live dist; every number below
> reproduces from the payload; the whole document survived a five-way adversarial review
> (paths · numbers · design laws · traps · completeness) and the 14 confirmed defects are
> fixed in this revision. **No new data is scraped or computed — every card runs on fields
> already in the payload.**

**The count: 35 cards — 19 on Your Clinic, 16 on The Market**, plus the map surface's two
attached components (the on-map KPI tile trio and the pin pop-card; counted, 37). Target was
25–35. The picker screen (V2) has its own card grammar and gets its own mini-gate — it is
deliberately not part of this count.

The three denominators, kept straight throughout: **50 Maps queries · 78 captured result
pages · 80 searches total.** Cards state their own denominator; nothing says "queries" bare.

---

## 1 · The grid

| Property | Value |
|---|---|
| Reference width | 1440 · container 1392 (24px page margins) |
| Columns | **12**, `fr`-based (exact column 101.33px at 1440 — don't round to integer px) · 16px gutters |
| Row unit | **96px** · 16px row gap |
| Card sizes | `stat` 3c×2r (336×208) · `wide` 4c×2r (453×208) · `half` 6c×2r (688×208) · `tall` 3c×3r (336×320) · `panel` 6c×3r (688×320) · `band` 12c×3r (1392×320) · `hero` 12c×4r (1392×432) |
| Radii / rungs | Cards 24px on the v3 glass ladder — **Card** rung default, **Elevated** on hover-lift, **Inner** for nested tiles (one level max). |

**The dark side of the ladder (new, V1).** Cards overlapping the background subject's dark
zone flip to a **dark-translucent primitive** (per the Glucose references). This does not
exist in the v3 ladder, so V1 extends `palette.json` (the plan permits it) with:

- **`glassDark` as a two-rung pair** — surface + nested tile, one level max, defined
  relative step (the dark counterpart of "inner is brighter than its parent by one level").
- **Dark-surface numeral registers** — `dot-on-dark` and `display-light-on-dark`. Without
  them the dark cards have no legal numeral: dot-ink (`#232323`) is illegible on dark, and
  dot-white is atlas-restricted to jewel heroes. The "dot-white = jewel heroes only" law is
  hereby scoped to **light surfaces**.
- **Provenance:** before authoring the tokens, run `sample_reference.py` probes against the
  Glucose reference images (dark-tile field / ink-on-dark anchors) and append a dark section
  to the atlas — the measurement chain (reference → sampler → atlas → palette.json) stays
  unbroken.
- **Dependency on the V4 background choice (the one assumption this doc carries).** The dark
  rung exists because the background subject has a dark zone. That holds for the map and
  dot-map variants; if the generated-gradient variant wins and reads light throughout, the
  dark cards need a different anchor (a self-carried dark surface rather than a borrowed one).
  This changes **no card's content, size, or position** — only which primitive some of them
  wear. Re-validate at V4 before V5 builds the cards.

Every card: quiet sentence-case grey label (no uppercase-tracked eyebrows — banned), one
numeral in its correct register, one small viz, `↗` in the corner only where a drawer
exists. Text is caption, never paragraph — all v3 explanatory prose moves into drawers or
dies. **Edge-cropped viz** (the v3 signature detail) is specified per card: YC-16's mini-map,
YC-04's track, MK-07's strip run off the card's bottom edge.

**Numeral register rule (atlas):** counts something countable → **dot-ink** (Doto,
digits-only — units/denominators ride the proportional face at ~40% numeral height).
Spans, ratios, percentages and **positions** → **display-light** (Geist 300).
**State-mapped jewel heroes → dot-white**; the index jewel's hero rides display-light, per
the reference's own "7-10" evidence (ATLAS §6).

### Reflow

| Breakpoint | Columns | Size remap |
|---|---|---|
| ≥1152 | 12 | as specified |
| 744–1151 | 8 | `stat`/`wide`→4c (two per row); **three-`wide` rows split 4+4 then 8** (YC-A: jewels side-by-side, teaser full-width below; MK-B: jewel+mirage, nobody's-ground full-width); `half`/`panel`/`tall`→adapted (`half`/`panel`→8c, `tall`→4c); `band`/`hero`→8c |
| 431–743 | 4 | `stat`→2c (pairs), everything else→4c |
| ≤430 (390 ref) | 4 | `stat`→2c pairs, **except dense-census cards (YC-07, YC-17, MK-07) which go full-width** so dots stay ≥ legible pitch; instruments full-width; map hero 4r→3r; table becomes a card list |

Per-card mobile adaptations (the cards that would otherwise break at 4c):
**MK-11** → horizontal scroll inside the card (`overflow-x` container), top-8 domains +
"(other)" (the top-N trim applies at every width — the matrix shows top 12 + "(other)" at
1440); **MK-12** → keep the centre spine, labels appear on hover/selected only;
**MK-01** → the 7 filter pills collapse to one "Filters (n)" pill, the KPI tiles stack
below the map; **MK-16** → column-drop order before the ≤430 card-list switch:
`web_score`, `sponsored`, `pos_avg`, `maps_score` go first; name + visibility + rank +
reviews survive longest. Mini-viz are **inline SVG** (not ECharts) except where noted, so
the 390px no-collapsed-charts check has fewer instances to trip.

Reading order = DOM order = the row order below; it survives every reflow (hero trio first,
prescription last on Your Clinic; map first, table last on The Market).

---

## 2 · Page anatomy

**Shell (V1, both pages):** top pill nav `Your Clinic · The Market` (active = solid dark
pill), top-right utility cluster — clinic switcher (**custom popover listbox, never a native
`<select>`** — the verifier counts them), settings, notifications, avatar — and the
editorial title block top-left. The 250px rail and all 13 facet rows are deleted; of their
functions: band ×4 + presence ×3 survive as MK-01's on-map pills, the **ads flag becomes a
toggle in MK-13's card header**, and the **verdict facet (5 rows) is killed** — verdict
becomes the clinic subtitle instead of a filter (rejected-list entry below). A shared shell
footer carries all three vintages (`vintages.maps / serp / build`) on both pages — the v3
rail footer's honesty rule ("one date implies a freshness the corpus does not have")
survives the rail's deletion.

**Your Clinic title block:** display line = `display_name`, calm subtitle = **`verdict`** —
the one-line diagnosis that today surfaces only as truncated rail facet labels (which v4
deletes); it has never been displayed on the clinic's own report.

**The Market title block:** "The Guntur market" + subtitle "34 clinics · 80 searches read ·
1,122 blocks across 78 result pages" (the subtitle keeps the denominator discipline — it
also pre-answers the 78-vs-80 question a sceptical clinic owner will ask).

---

## 3 · Your Clinic — 19 cards

| # | Card | Size | Viz · register | Data (exact paths) |
|---|---|---|---|---|
| YC-01 | **Visibility jewel** | wide | State-mapped mesh jewel (band recipe via `band_of`) · dot-white hero | `visibility` |
| YC-02 | **Market rank jewel** | wide | **Index** jewel (never state-mapped) · display-light `#12 /34` (see register rule §1) | `visibility_rank`, `visibility_total` |
| YC-03 | **What's possible** | wide | Dark-glass teaser · display-light-on-dark span `#26 → #9` (a real clinic: `plan.now.rank` 26 → `compound.top2.rank` 9) · lime featured pill (№1) | `plan.now.{vis,rank}`, `plan.compound.top2.rank`, `plan.compound.all.{vis,rank}` |
| YC-04 | **The 60/40 blend** | stat | Two labelled segments + hairline track, edge-cropped (no gauge — `web_score` is near-binary: 28/34 sit at exactly 0 or 100) · dot-ink pair · worst side gets a **lime row/pill treatment (№2), never a lime segment fill** (chart-fill lime is banned) | `maps_score`, `web_score` |
| YC-05 | **Average Maps position** | stat | Tick ruler, one glowing marker, no target line · display-light `10.5` | `pos_avg` (range 2.46–14.0) |
| YC-06 | **Ready-to-book share** | stat | 10-dot meter row · display-light `19.1%` | `high_intent` |
| YC-07 | **Demand census** | stat | 50-dot census (lit = appeared) · dot-ink `14`, "/50 Maps searches" in the proportional face | `appearances` |
| YC-08 | **The examination** | half | 5 compact instrument rows (status dot + micro-viz each: filament / 78-dot census / span ruler / dumbbell / filament) · `↗` drawer keeps v3's deep copy | `scorecard[5]` (website · search · **"in the local pack"** · reviews · phone) |
| YC-09 | **Score anatomy** | half | 6 earned/max hairline bars — where your 100 points went · dot-ink earned, ink-3 max | `breakdown[6]` (website 30 · search 30 · maps 15 · reviews 15 · phone 5 · breadth 5) — **shipped, rendered nowhere in v3** |
| YC-10 | **The page patients see** | panel | Redrawn SERP rows (kind swatch + type tag + **display-light position** — a rank is a span, not a count), **dashed ghost row = your absence**; query stepper (up to 8 pages by contract — 5 ship today); caption names the query via `proof.strength` ("the highest-demand search you're missing") | `proof.query`, `proof.strength`, `serp.pages{q}[]` |
| YC-11 | **Who's there instead** | tall | 4 rows (every clinic ships exactly 4), kind swatch + name — the competitors on that page | `proof.present[]` — **shipped, never rendered in v3** |
| YC-12 | **Intent polar** | tall | 6-spoke polar, dashed market polygon, dead stubs for absent categories | `intents[]` (`n` shown as spoke caption), `intents_market` |
| YC-13 | **Your web ground** | stat | Owned/borrowed dot pair + platform chips + best organic position (display-light `#7`, `never` when null) | `web.owned`, `web.borrowed`, `web.platforms[]`, `web.best_position` |
| YC-14 | **Reviews vs the market** | stat | Dumbbell: you ↔ market median · dot-ink | `reviews`, `kpis.median_reviews` (154 — the payload's canonical value; don't recompute) |
| YC-15 | **Sponsored presence** | stat | Filament bar vs market leader · dot-ink `0` — "appeared as an ad on 0 of the 78 result pages read" (27 of 34 clinics never have; leader: 31). *`sponsored` counts ad **appearances** on captured pages, never "ads bought" — we cannot see spend.* | `sponsored` |
| YC-16 | **Where you sit** | stat | Mini dot-map, km rings, your pin glowing, edge-cropped · display-light `1.5 km` | `lat`, `lng`, `km_core` |
| YC-17 | **Patient voice** | half | Jittered sentiment dot grid (one dot per review read) · display-light `%` positive · honesty caption **"from your {nlp.n} most recent reviews"** (n is 10 for 29 clinics, 20 for 2 — never hardcode 10) | `nlp.n`, `nlp.pos`, `nlp.sentiment` |
| YC-18 | **Praised / flagged** | half | ≤3 + ≤3 pill rows + referral line + `recent6mo` recency line · **same dynamic honesty caption as YC-17** | `nlp.themes[]`, `nlp.pains[]`, `nlp.referral`, `nlp.recent6mo` |
| YC-19 | **The prescription** | band | Dark-glass action surface (see §5 note): dose-card stack (toggleable steps recompute projection) + shared projection ruler with a **glowing point marker, never a line**, + lime "now" dot (№3) + action-family jewel chip — **two stops: rose → hot pink, lime core omitted** (the YC lime budget is fully spent by 03/04/19) | `plan.steps[]`, `plan.compound`, `visibility` (all 34, for re-rank) |

**Bento rows at 1440:** A `01+02+03` (4+4+4) · B `04+05+06+07` (3+3+3+3) · C `08+09` (6+6) ·
D `10+11+12` (6+3+3) · E `13+14+15+16` (3+3+3+3) · F `17+18` (6+6) · G `19` (12).

**Interactivity: Your Clinic is a static-read page.** Hover = class-toggle highlight only;
no card on it emits filters (v3's clinic-page polar toggle is dropped — MK-15 keeps the
category toggle on the page it filters). The cross-filter buses live on The Market.

### States (Your Clinic)

- **No NLP (3 clinics):** YC-17/18 render a quiet "No reviews read yet" state.
- **Zero plan steps (1 clinic — Dr Sowmya):** YC-19 → "Nothing to prescribe — already at
  the ceiling"; **YC-03 mirrors it** (its span would degenerate) with the same copy.
- **`proof` null:** the win copy "You're on every page we read" renders **only when
  `web_available && proof == null`** — with `web_available: false` the same null means "web
  not read", never a win. (Zero live instances today; state specced for refreshes.)
- **Nothing-clinic web ground (YC-13):** owned 0 · borrowed 0 · platforms [] → "Not seen on
  the open web yet" + `never`.
- **All-absent intents (YC-12):** all six spokes dead-stubbed, caption "Not seen in any
  tracked search category".
- **Null `lat/lng/km_core`:** YC-16 (and the MK-01 pin) render "location not resolved",
  numeral em-dash. (None ship today; the geocode fallback can fail on refresh.)
- **Dataset absent (`web_available: false`):** YC-04 renders the Maps segment alone with
  caption "web not yet read"; YC-10/11/13 hide; the 60/40 headline becomes Maps-only —
  matching `vulnerability.py`'s own fallback. `reviews_available: false` hides YC-14/17/18.
- **Subject change (top-bar switcher / MK-16 row click):** all 19 cards recompute in place,
  open drawers close, scroll position resets to top; the remembered picker choice
  (namespaced `localStorage` key, V2) updates to the new subject.
- **First paint:** shell → title → hero row A → remaining rows; KPI numerals count up with
  the per-column dot stagger while jewel gradients settle — then stillness (atlas motion
  law). Initial-mount budget for V6's verifier: interactive < 1.5 s on the reference
  machine, no layout shift after the hero row lands.

---

## 4 · The Market — 16 cards

| # | Card | Size | Viz · register | Data (exact paths) |
|---|---|---|---|---|
| MK-01 | **The Guntur map** | hero | The map surface (432px tall — ~58% of the content area below the shell at 1440×900): 34 glow-halo pins coloured by band; **glass filter pills float on it** (band ×4 · presence ×3) on the **Veil rung over the dark map zone** (Float stays reserved for the summary pill; cap total backdrop-filter area — pills only, never the whole surface) | `clinics[].lat/lng/visibility/key` + `facets.band`, `facets.presence` |
| MK-01a | · KPI tile trio (on-map, dark) | 3 tiles | dot-on-dark register (§1). **Tile 1 is the live filter readout: it counts the clinics in view and goes lime-pill "N · of 34" when a filter narrows the market; click clears all filters** (v3's kpi-strip readout, relocated). Tiles 2–3: `20 invisible in search` · `154 median reviews` | `facets.total`, `facets.presence` (invisible 20), `kpis.median_reviews` |
| MK-01b | · Pin pop-card | overlay | The privacy-limited card, **exactly** the approved six fields: name, visibility, rank, reviews, rating, has-website. Nothing else — no plan, no breakdown. Click-through sets the subject and opens Your Clinic. | `display_name`, `visibility`, `visibility_rank`, `reviews`, `rating`, `has_website` |
| MK-02 | **Market pulse jewel** | wide | Caution-family jewel (state-mapped to invisible share 20/34) · dot-white `20` /34 invisible | `facets.presence` |
| MK-03 | **Nobody's ground** | wide | Share meter + dot-ink `563` of 1,122 blocks (50.2% — "half" is fair) — **half the market's search real estate belongs to no local clinic**. Lime featured pill (№1, the page's one lime) | `serp.ownership.totals` (blocks 1122, unmapped 563) |
| MK-04 | **The website mirage** | wide | Dumbbell 20 → 10 · dot-ink — 20 clinics list a website on Maps; **only 10 rank organically with one** · reconciling caption: "2 more reach the page only by paying" (keeps the presence facet's own 12 / borrowed 2 / invisible 20 doctrine intact — a paid placement is OWNED) | count of `has_website` (20) vs `web.has_own_site` (10) |
| MK-05 | **Organic is leaking** | stat | Meter · display-light `35%` — 235 of 673 organic blocks are local | `serp.ownership.local_share.organic` |
| MK-06 | **Ads nobody runs** | stat | dot-ink `27` /34 **never appeared as an ad on any of the 78 pages read**; caption: "one advertiser — a four-branch chain — holds 55 of the market's 169 sponsored blocks" | `clinics[].sponsored`, `serp.ownership.domains[]` (kolorshairandskin.com: 55 ad blocks of its 59 total) |
| MK-07 | **The review economy** | stat | 34-dot strip (√ scale), edge-cropped, median as a **glowing point marker (never a line)** · dot-ink median `154` (the payload's canonical `kpis` value), caption mean 306 · range 22–2,085 | `clinics[].reviews`, `kpis.median_reviews`, `kpis.avg_reviews` |
| MK-08 | **The four bands** | stat | 4 band rows of dots (10 · 13 · 5 · 6), band-keyed chroma dots — the only band chroma outside jewels **and the map surface** (pins + pills; the full chroma census is in §5) | `bands.bands[4]` — **shipped, unread in v3** (only `gaps` was read) |
| MK-09 | **Opportunity map** | panel | ECharts scatter demand × visibility + brush (re-armed after every setOption) + zone plates on silent z:0 series — flagship cross-filter, unchanged | `appearances`, `visibility`, `reviews`, `display_name`, `key` |
| MK-10 | **The visibility league** | panel | Hairline bars + terminal dots, **empirical gap voids labelled** (50→66, 20→31); sort segmented control (visibility / reviews / demand); row click selects everywhere | `visibility`, `visibility_rank`, `reviews`, `appearances`, `bands.gaps` |
| MK-11 | **Who owns the results** | band | Domain × block-type dot-column matrix, **top 12 domains + "(other)" at 1440** (top 8 below 744), per-type local-share ticks, `↗` per-domain drawer. The `ai_overview` column reads 0 local across all 39 blocks — the matrix shows it; no card is built on it | `serp.ownership.domains[]`, `.totals.by_type`, `.local_share` (all 5 types — 4 were shipped unread) |
| MK-12 | **Own vs borrowed ground** | panel | Centre-spine butterfly, 34 rows, hollow zero-dots for the nothing-clinics | `web.owned`, `web.borrowed` per clinic |
| MK-13 | **Who pays for the page** | panel | Filament shelf, all 34 rows, empty rows kept — the emptiness is the chart; counts captioned "/78 result pages"; **card header carries the ads-flag toggle** (the rail facet's survivor) | `sponsored` per clinic (0×27 · 1,1,2,2,7,23,31) |
| MK-14 | **How far the market gets** | half | Tick-ruler funnel steps 34 → 32 → 19 → 19 → 17, dot-ink counts, no trapezoid | `funnel[5]` |
| MK-15 | **Demand & depth** | half | 6 category rows: demand count bar + median-position span (display-light) — what patients search, and how deep results go; rows toggle the category filter | `categories[]`, `intents_market` (medians 8.0–10.0) |
| MK-16 | **Every clinic** | band | Sortable table, **neutral-ink** visibility track bar, row click sets the subject → that clinic's report; **`web_score` column renders as the two-state mark (own-ground dot / em-dash), never a bare numeral** (28/34 sit at exactly 0 or 100 — a numeral column would fake granularity) | `display_name`, `visibility`, `visibility_rank`, `maps_score`, `web_score`, `pos_avg`, `reviews`, `appearances`, `sponsored` |

**Bento rows at 1440:** A `01` (12×4) · B `02+03+04` (4+4+4) · C `05+06+07+08` (3+3+3+3) ·
D `09+10` (6+6) · E `11` (12) · F `12+13` (6+6) · G `14+15` (6+6) · H `16` (12).

**The map asset budget (binding):** the dist has **188 KB of headroom** (1041 KB now, 1229 KB
cap) and the offline law forces the map inline. Budget: **≤100 KB inline SVG**,
path-simplified, one `<path>` per road class; the dot-matrix variant is generated as **a few
compressed paths, never per-dot nodes** (~9,000 dot elements would also wreck the 0.2 ms
hover contract). To widen the margin, the **~35 KB payload prune moves forward from V5 to
V3** (the fields are enumerated in §7 — the prune list is exhaustive there).

**Cross-filter (3-bus survives) — sources *and* consumers:**
- *Filter sources:* MK-01 pills, MK-09 brush, MK-15 rows, MK-13's header ads toggle.
- *Filter consumers:* MK-01 pins + MK-01a tile 1 (the readout) + MK-09 + MK-12 + MK-13 +
  MK-16 follow the filter; **MK-10 deliberately does not** (the league always shows all 34 —
  v3's call, kept); MK-02..08, MK-11, MK-14, MK-15 are static aggregates.
- *Select sources:* MK-01 pins, MK-10 rows, MK-16 rows. Select = highlight everywhere;
  **click-through on MK-01b / MK-16 sets the subject** (and the remembered picker key).
- *Hover* stays class-toggle-only — never `setOption` (the 0.2 ms contract).

---

## 5 · Law compliance census (per page)

| Law | Your Clinic | The Market |
|---|---|---|
| Jewels ≤3, never on an ordinary card | 3: YC-01 (state-mapped) · YC-02 (index) · YC-19 chip — legal because the prescription band is the **action surface** (the reference's Connect-tracker analogue, ATLAS §8), not an ordinary card; chip recipe is two-stop rose→pink | 1: MK-02 (caution) |
| Lime ≤3, sanctioned roles only | **Exactly 3 — zero headroom:** YC-03 featured pill · YC-04 worst-side pill (row treatment, never a segment fill) · YC-19 now-dot. The YC-19 chip ships **without** its lime sensor core for this reason | 2: MK-03 featured pill · MK-01a live-readout pill (lime only while a filter is active) |
| Band chroma outside jewels | none (YC-01 is the jewel itself) | MK-08 dots · MK-01 pins + pills — deliberate, counted, nothing else (MK-16's track bar is neutral ink) |
| Registers | counts → dot-ink · spans/ratios/positions → display-light (incl. YC-10's SERP positions) · state-mapped jewel heroes → dot-white · index hero → display-light · dark surfaces → the V1 dark registers | same |
| Banned | No uppercase-tracked eyebrows · no native `<select>` (sort = segmented control; clinic switcher = custom popover) · no `<img>` (maps inline SVG; *raster background variant needs a scoped amendment — see Open questions*) · no weight ≥700 · no red · no target lines (all markers are glowing points) | same |
| Prose | `prose_level: caption` max on every card; paragraphs live only in drawers | same |

**Verifier port (new V6 scope):** `verify_dashboard.py` is hard-wired to the v3 DOM (`.rail`,
`.switch button[data-page]`, 19 `[data-panel]`s, "select propagates to the rail"). The port
happens **in the same phase that builds the new shell**, and adds checks for the new laws:
glassDark tokens sourced from `palette.json` only, the two-stop chip recipe, a
`background-image` raster scan (today's check only counts `<img>` elements — a CSS raster
would pass silently), and the map byte budget.

## 6 · Traps honoured (live-confirmed)

1. **`rating`**: no card. 28/34 sit in 4.8–5.0. Appears only in MK-01b (explicitly sanctioned
   by the plan's privacy decision, twice) and inside the fixed `funnel` step labels — where,
   verified, "+ Rating > 4" cuts zero clinics (19→19): quiet proof the trap is real.
2. **`ai_overview`**: no card. 0 local across all 39 blocks; visible only as a matrix column.
3. **Review NLP**: two cards only, **both** carrying the dynamic honesty caption "from your
   {nlp.n} most recent reviews"; no trends, no rankings, no cross-clinic comparison.
4. **`web_score`**: never a gauge/spectrum/bare numeral — YC-04 renders two labelled
   segments; MK-16's column is a two-state mark.
5. **`sponsored` semantics**: it counts ad **appearances across the 78 captured pages**,
   never purchases — no card says "bought"; YC-15/MK-06/MK-13 all carry the /78 caption.
6. **Denominators**: YC-07 "/50 Maps searches" · local-pack, blocks, ads "/78 result pages" ·
   "80 searches" only in the title blocks, never beside a block count without the 78.

**Rejected cards** (considered, killed): rating benchmark dumbbell (trap 1) · "AI answers"
stat tile (trap 2 — arguable as a market-wide sales stat, see Open questions) · sentiment
trend line (no dates in NLP) · web-score gauge (trap 4) · quadrant chart on rating axes
(v3 already rejected; `payload.quadrant` deliberately unshipped) · per-clinic `intents`
league (n too small per category) · **verdict as a filter facet** (5 free-text rows made a
poor rail facet; verdict is now the clinic subtitle — its filter role dies with the rail).

## 7 · Payload reconciliation

- **Revived dead fields** (grep-confirmed zero JS references in v3): `breakdown[6]` (YC-09) ·
  `proof.present[]` (YC-11) · `proof.strength` (YC-10 caption) · `web.best_position` (YC-13) ·
  `bands.bands` (MK-08) · `local_share` non-organic types (MK-11) · `nlp.recent6mo` (YC-18).
- **Promoted, not revived:** `verdict` (rail facet label → clinic subtitle) · `facets` (rail
  rows → MK-01 pills + MK-13 toggle) · `plan.now` (already rendered in v3's prescription;
  YC-03 adds a second consumer) · `vintages` (rail footer → shell footer).
- **Still deliberately unused — this list is the exhaustive V3 prune list (~35 KB):**
  `benchmarks[3]` (reviews/demand rows duplicated by YC-14/YC-07 from raw fields; rating row
  is trap 1) · `notes`/`label`/`score` (internal prospecting voice — wrong register for a
  clinic-facing report) · `market.*` (duplicates `kpis`/`facets`) · `median_appearances` ·
  `address`/`phone`/`website`/`place_url` (identity strings; pop-card scope is fixed) ·
  `nlp.neg` (implied by `pos`) · `nlp.sentiment` beyond YC-17's grid · `proof.screenshot`
  (names an asset that no longer ships) · `web.appearances` (legacy) · `web.in_places` (the
  raw input behind "places-only = invisible"; the doctrine ships as `facets.presence`) ·
  `generated_at` (superseded by `vintages`) · `city` (title copy is authored) ·
  `contact.whatsapp` (still `""`; wire when George fills `config.WHATSAPP_NUMBER`) ·
  `kpis.avg_rating`/`unique_clinics`/`no_website_count`/`pct_with_website`/`total_appearances`.
  **Kept as gates, not display:** `web_available`, `reviews_available` (§3 States).
- **No new payload keys are required for any card above.**

## 8 · v3 → v4 mapping (losses are named, not hidden)

| v3 panel (19) | Becomes |
|---|---|
| twin-jewels | YC-01 + YC-02 (context dot-column → YC-01's `↗` drawer) |
| split-score (3 ideas packed) | YC-04 + YC-05 + YC-06 |
| examination | YC-08 (rack kept; drawer keeps depth) |
| intent-polar | YC-12 (its clinic-page filter toggle is **dropped** — Your Clinic is now static-read; MK-15 keeps the toggle) |
| serp-page | YC-10 + YC-11 |
| prescription | YC-03 (teaser) + YC-19 |
| voice (3 ideas) | YC-17 + YC-18 |
| constellation | YC-16 (mini) + MK-01 (full surface) |
| market-jewels | MK-02 (+ MK-01a tiles) |
| kpi-strip | MK-01a (incl. the **live filter readout**, relocated to tile 1) + MK-03 + MK-07 |
| opportunity | MK-09 |
| league | MK-10 |
| serp-ownership (argument + matrix) | MK-03/04/05 (argument tiles) + MK-11 (matrix) |
| ad-shelf | MK-06 (stat) + MK-13 (shelf + ads toggle) |
| owned-borrowed | MK-12 |
| funnel | MK-14 |
| categories | MK-15 (merged with `intents_market` depth) |
| market-map | MK-01 (promoted to the hero surface) |
| all-clinics | MK-16 |
| *rail (non-panel)* | facets → MK-01 pills + MK-13 toggle (verdict facet killed) · vintages → shell footer · clinic switch → top-bar popover |

## 9 · Open questions for George (everything else above is asserted)

1. **Approve the 35 as listed?** Trims I'd volunteer if you want fewer: YC-11 folds into
   YC-10's footer (−1), MK-06 folds into MK-13's header (−1), MK-08 folds into MK-10 (−1) → 32.
2. **"AI answers" tile**: the plan lists `ai_overview` as a trap, so it's rejected — but as a
   *market-wide* sales stat ("39 AI answers on Guntur searches · no local clinic in any of
   them") it's strong and honest. If you want it as MK-17, I'd pair it with one §9.1 trim so
   the official count stays ≤35.
3. **The raster background amendment**: if V4's gradient variant ships as a baked WebP, the
   no-raster law needs a scoped exemption (one allowlisted `background-image`, byte-counted
   against the same headroom as the map). The map/dot variants stay pure SVG and need
   nothing. OK to amend the law *only if* that variant wins?
