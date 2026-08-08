# Derma Intel v3 — Reference Atlas

> **What this is.** Measured ground truth for the v3 identity, sampled from the nine reference
> screenshots in `design/Design Inspiration/` by `tools/sample_reference.py` against the probe map in
> `reference-probes.json`. Raw output: `reference-samples.json` (committed, rerunnable).
>
> **The fidelity contract.** `reference images → this atlas → palette.json → tokens-v3.css → the
> dashboards`. **Fix downstream, never upstream.** When the guide, the app and this atlas disagree,
> the reference images win, then this atlas, then everything else. If the app looks wrong you fix the
> app; you do not edit the atlas to match it.
>
> **Status: awaiting Gate A.**

---

## 0 · Honesty box

The references are **tilted 3D device renders** photographed under a grey studio cast with
depth-of-field blur. They are not flat UI captures. Three consequences, stated up front:

1. **Raw samples read darker than the flat UI truly is** (the studio cast).
2. **Calibrated values overshoot** wherever the white anchor was not itself pure white.
3. **Thin text strokes never sample their true darkest** (antialiasing), so ink is stated *darker*
   than its raw sample.

**The reconciliation rule, applied throughout:**

> **Relative relationships come from raw deltas within one image. Absolute values come from
> cross-image consensus.**

### What the sampler flagged (evidence, not failures)

The v3 sampler adds two numbers the sister project's did not have — `sigma` (per-channel standard
deviation across the patch) and `delta` (channel spread of the result) — so a probe that misses its
target is *detected* rather than caught by eye. Three probes were rejected on that basis:

| Probe | Sample | Why rejected |
|---|---|---|
| `dashboard snapshot 2 / field-mid` | `#588B5E`, delta **51** | Declared `neutral`, came back saturated green — the probe landed on the Score jewel, not the field. *(The sister project hit the same miss at the same coordinate.)* |
| `dashboard snapshot 1 / healthimproving-pill` | `#DFDFDF`, sigma **30.4** | This image's **white anchor** straddles an edge → its gain of 1.143 is untrustworthy → **every calibrated value from dashboard snapshot 1 is discarded.** Raw only. |
| `dashboard snapshot 2 / field-far-left` | `#AFAFAF` | Landed on the grey studio backdrop *outside the tablet bezel*, not on the UI field. Excluded from the field consensus. |

Three further probes returned their surrounding surface instead of their target
(`dotmatrix-ink-43` → `#F3F3F3`, `display-num-ink` → `#DCDCDC`, `tab-inactive-grey` → `#E1E1E1`).
All are `minluma` probes on dot-matrix glyphs, which are mostly holes. They are recorded and
excluded; the ink ramp rests on the probes that did land.

### Confidence, graded per category

| Category | Confidence | Basis |
|---|---|---|
| Field, ladder deltas, ink, lime | **High — measured** | 7 independent field hits; ladder deltas within single images; 5-hit lime band |
| Score / Index / Action jewel anchors | **High — measured** | Diagonal ramp walks, sigma < 3 on every band probe |
| `clear` / `steady` / `caution` / `alarm` recipe *composition* | **Medium — tuned** | Anchors measured; the radial layering and stop positions are authored |
| Chart data hues | **Low — visually read** | Scatter dots are 5–8px; too small to probe reliably. Re-verify when built. |

---

## 1 · The field is hue-neutral, and it is `#EDEDED`

**Seven independent raw hits** across five images: `#E2E2E2` ×5 (sidebar ×3, dash-2, short-cards),
`#E3E3E3`, `#E0E0E0`, plus `#E2E2E2` on dash-1. Raw field consensus = **`#E2E2E2`**.

**Every neutral probe in the entire run returned `delta = 0`** — R, G and B exactly equal. The field,
the cards, the rail rows and the whole ink ramp are **hue-neutral**. This kills v2's cool-tinted
`#E9EAEC` canvas and `#131417` ink: there is no measured basis for either tint.

**Which calibration to trust.** Four images carry a white anchor. Only one is credible:

| Image | Anchor | Raw | Gain | Field calibrates to | Verdict |
|---|---|---|---|---|---|
| dashboard snapshot 2 | `upload-card-white` | `#F3F3F3` | **1.049** | **`#EDEDED`** | ✅ anchor sigma 0.0, a real white card — **taken** |
| cards 1 / 2 / 3 | white card | `#F3F3F3` | 1.049 | — | ✅ agrees, same gain |
| sidebar navbar | selected rail row | `#E5E5E5` | 1.114 | `#FCFCFC` | ❌ too bright — the anchor is a *tonal* row, not white |
| short cards | `inrange-pill-white` | `#C0C0C0` | **1.328** | `#FFFFFF` | ❌ nonsense — anchor is in deep shadow |
| dashboard snapshot 1 | float pill | `#DFDFDF` | 1.143 | `#FFFFFF` | ❌ anchor sigma 30.4 — rejected |

> **`--field: #EDEDED`** — from the single trustworthy gain, cross-checked by three images landing on
> the identical 1.049.

---

## 2 · The brightness ladder (the load-bearing discovery)

There is **no single glass recipe**. There is a ladder, and every rung is a *recipe over the field*,
not a flat hex — because what the eye reads is the step, not the colour.

**Raw deltas, measured within single images** (so the studio cast cancels):

```
sidebar navbar :  field #E2E2E2 → rail row #E9E9E9  (+7) → value pill #EFEFEF (+13)
cards 2        :  field #E9E9E9 → card    #F3F3F3  (+10) → inner card #FAFAFA (+7 above card)
short cards    :  field #E2E2E2 → band    #F6F6F6         → float pill #F1F1F1–#F6F6F6
```

`cards 2` is the money shot: a **nested inner card measurably brighter than the card containing it**
(`#FAFAFA` inside `#F3F3F3`). The inner card is the brightest surface in the system.

| Rung | Flat equivalent | Recipe over the field | Evidence |
|---|---|---|---|
| **Field** | `#EDEDED` | — | 7 raw hits at `#E2E2E2`; calibrated `#EDEDED` |
| **Sunken** (wells) | `#E6E6E6` | — | derived (−3%) |
| **Veil** (rail rows, filter rows) | `#F4F4F4` | `rgba(255,255,255,.38)` + `blur(8px)` | sidebar `#E9E9E9` vs field `#E2E2E2` → +7 |
| **Card** (every content panel) | `#FBFBFB` | `rgba(255,255,255,.80)` + `blur(14px)` | `#F3F3F3` in 4 images; +10 to +17 over field |
| **Elevated** (selected, hover-lifted) | `#FDFDFD` | `rgba(255,255,255,.92)` + shadow | value pill `#EFEFEF`, +13 inside a row |
| **Inner** (nested — **brightest**) | `#FFFFFF` | `rgba(255,255,255,.97)` | cards-2 `#FAFAFA` inside `#F3F3F3` |
| **Float** (the summary pill only) | translucent | `rgba(255,255,255,.55)` + `blur(26px)` + `saturate(140%)` | short-cards: scatter dots **visibly ghost through** it |

Shared card furniture:
```css
box-shadow: 0 8px 28px rgba(35,35,35,.07), 0 1px 2px rgba(35,35,35,.05),
            inset 0 0 0 1px rgba(255,255,255,.75);   /* luminous top hairline */
```

**Laws.** Pick the rung by *role*, never by taste. An inner card is always brighter than its parent,
by exactly one level. Heavy blur belongs to the Float rung alone. Nesting never goes past one level.
`prefers-reduced-transparency` collapses every rung to its flat equivalent.

---

## 3 · Ink ramp — also hue-neutral

Every ink probe returned `delta = 0`.

| Role | Value | Evidence |
|---|---|---|
| **Ink** (primary) | `#232323` | `wordmark-ink` raw `#232323`; `tab-active-ink` `#2C2C2C`. Stated at the darkest reliable sample — antialiasing means thin strokes never reach their true darkest. |
| **Ink-2** (secondary) | `#5A5A5A` | `name-ink` `#4C4C4C`, `dotmatrix-ink-21` `#505050`, `dotmatrix-ink-103` `#464646` |
| **Ink-3** (muted labels) | `#8C8C8C` | `biomarkers-ink` `#8E8E8E` |
| **Ink-4** (faint / disabled) | `#B0B0B0` | `sub-grey-text` `#A7A7A7`, `body-grey-text` `#AEAEAE` |
| **Hairline** | `rgba(35,35,35,.09)` | derived |

---

## 4 · The accent — acid lime, five independent hits

Sampled with `maxchroma` (a 10px pill's patch is mostly surrounding card; the top 12% by chroma *is*
the pill):

| Probe | Raw |
|---|---|
| Go Pro pill — sidebar | `#DFF602` |
| "Total" pill — dash 2 | `#DBF30A` |
| "Total" pill — dash 1 | `#DFF405` |
| Progress dot — cards 4 | `#DFF606` |
| Sensor core inside the pink jewel — cards 2 | `#D2EA08` |

Band: R 210–223 · G 234–246 · B 2–10. **Centre of band = `#DCF306`.**

> **`--accent: #DCF306`** · text on lime is always **ink** (`#232323`), never white
> · **≤3 elements per page**, and the census is enforced by the verifier.

Sanctioned roles, and no others: the featured metric pill (one per strip, max) · the worst-performing
row in the split-score stack · the journey/"now" dot · the sensor core.

**Never**: lime text, lime borders, lime fills on charts, lime washes, or a second accent.

---

## 5 · Mesh jewels

**Grammar** (this is the transferable part, independent of hue): **2–4 radial gradients layered over
one base linear**, with every radial anchored **outside or at the edge of the box**
(`at 82% -10%`, `at 28% 105%`) so the colour appears to *arrive from off-card* rather than sit inside
it. Three named voices per jewel: **pale frame → vivid core → deep anchor**. Each casts a **bloom** —
a tinted glow past its own edge. SVG `feTurbulence` grain at **14%** kills banding.

### 5.1 Measured anchors

**Score ramp** (`cards.png`, probes walking a diagonal y 0.20 → 0.68 — this is why we get a *ramp*
and not a colour):

| y | Sample | Reading |
|---|---|---|
| 0.20 | `#E6CBAC` | sand-peach top |
| 0.27 | `#E2C18F` | warmer sand |
| **0.38** | **`#9AC361`** | **the yellow-green transition band** |
| 0.52 | `#399F3A` | vivid green |
| 0.58 | `#278D2C` | deep green |

Cross-checked: dash-1 `score-sand-top #D9BC78`, `score-green-low #34833A`; cards-3
`green-band-top #3A8241`.

**Green owns everything below y ≈ 0.45.** This is not an orange card — v2's reading was wrong.

**Index ramp** (`cards 1`): slate frame `#E2E2E1` / `#BCBAB7` (delta 1 and 5 — **the frame is
essentially neutral grey**) → blazing core `#F37E1C` / `#F37922` (delta 215) → amber floor `#E1A162`
→ rose bleed `#E09E90`.

**Action ramp** (`cards 2`): rose edge `#ECC6C7` → hot pink `#F36D92` / `#F46892` → lime sensor core
`#D2EA08`.

### 5.2 The five v3 families

Three families rest on measured anchors. Two are **derived** — the reference contains no mint/teal
surface and no butter/coral surface — and are marked as such.

| Family | Voices | Basis | Role in this product |
|---|---|---|---|
| **clear** | sand `#E6CBAC` → transition `#9AC361` → green `#399F3A` → deep `#25822B` | **measured** | Visibility 80–100 · "owned real estate" |
| **steady** | sand `#E6CBAC` → warm `#D8BC77` → olive `#9AC361` → green only at the base | **measured** (same ramp, green entering later) | Visibility 51–79 |
| **caution** | butter `#F6E3BC` → amber `#F59B33` → coral `#DE5B3D` | **derived**, anchored on measured index amber `#E1A162` + core `#F37E1C` | Visibility 21–50 · "invisible share" |
| **alarm** | rose `#ECC6C7` → hot pink `#F36D92` → deep `#C0355F` | **measured** (Action ramp; deep anchor derived) | Visibility 0–20 |
| **index** | slate `#BCBAB7` → blazing `#F37E1C` → amber `#E1A162` → rose `#E09E90` | **measured** | Market Rank — an index, never state-mapped |

**Census: max 3 jewels per page. Never on an ordinary card.** At chip scale the multi-radial recipes
turn to mud — reduce to two stops below ~150×80.

---

## 6 · Typography

**Weights 300 / 400 / 500 / 600. Nothing renders at 700, ever** — enforced at the font level by not
shipping the 700 face, and asserted by the verifier against computed styles.

Evidence: the reference's heaviest element is the wordmark at ~600; the person-name reads as a
*medium*, not a bold; and the big duration figure "7-10" is unmistakably a **light** proportional
face, not dot-matrix.

### The three numeral registers

| Register | Face | Used for |
|---|---|---|
| **dot-ink** | Doto, `ROND 100`, ~320 weight, ink | Naked KPI-strip metrics, small stat values |
| **dot-white** | Doto, `ROND 100`, ~320 weight, white | Jewel hero numerals only |
| **display-light** | Geist **300**, proportional, 48–56px | Spans and ratios — average position, `#28 → #19`, `/34` |

> **The register rule: if it counts something countable, it is dot-matrix. If it spans, it is light.**

**Dot-matrix off-dots are not drawn at all.** A visible grid behind the glyph makes it read as a
novelty font; with the grid absent it reads as an instrument. Dot radius ≈ 0.31 × cell (≈62% of
pitch). Doto is **digits-only** in our usage — currency and mixed strings ride `display-light`.

Labels are **sentence-case grey**. Uppercase-tracked eyebrows are banned. Units render in the
proportional face at ~40% of the numeral height, baseline-aligned to the numeral's bottom.

---

## 7 · Geometry and instrument furniture

| Element | Value |
|---|---|
| Jewel radius / proportion | 28px · ~1.5:1 landscape |
| Card / inner / row / pill radius | 24 / 20 / 16 / 999px |
| Rail | 250px · rows ~52px · icons 18px at stroke 1.5 |
| Tick ruler | 8px pitch · major every 6th · ticks at **45% alpha** · one full-alpha marker with a 6px glow · **no target line, ever** |
| Dot column | dot Ø 55–60% of pitch · per-dot alpha modulated so it shimmers rather than reading as a bar chart |
| Mini-viz | **edge-cropped** — runs off the card's bottom edge (`bottom:-6px` + parent `overflow:hidden`), clipped by the radius |
| Shadows | soft, diffuse, neutral. Nothing hard, nothing black. Jewels add their tinted bloom. |

**Motion**: ease-out only — `--ease-cine cubic-bezier(.16,1,.3,1)`, `--ease-ui cubic-bezier(.32,.72,0,1)`.
Durations 160 micro / 240 state / 380 reveal / 560 hero. On first paint the KPI numerals count up with
a per-column dot stagger while jewel gradients settle — **then stillness.** No idle wobble.

---

## 8 · The dermat translation table

The reference is a *body*-health dashboard. Ours is a *clinic-visibility* diagnostic. We take the
structure and re-point the content; we carry over no imagery, copy, mark, or data.

| Reference | Derma Intel |
|---|---|
| Superpower Score jewel | **Online Visibility** score (state-mapped) |
| Biological-age index jewel | **Market Rank** index — where you stand among 34 Guntur clinics |
| Connect-tracker Action jewel | The **prescription** CTA |
| Biomarker stat card | An **examination instrument row** |
| Scatter-dot biomarker timeline | **SERP ownership** — who holds the Guntur result pages |
| Tick-ruler pacing gauge | Rank marker · local-pack span · plan projection |
| Supplements row | The **treatment plan** prescription stack |
| Upload-records card | (dropped — no analogue) |
| Health-records object slot | The report object in the plan header |

---

## 9 · Divergence list — how v3 sits *beside* the Log App, not on top of it

Both products derive from the same reference, so they are **siblings by design**: the glass ladder,
the dot-matrix register and the neutral field are properties of the *reference*, not of either brand,
and sharing them is what makes the two feel like one house. The differentiation is structural:

| # | Divergence | Why |
|---|---|---|
| 1 | **Jewels state-map.** Our Visibility jewel changes recipe with the score band; theirs never change. | Ours is a *diagnostic*. A 34 must not render in a reassuring green. The colour draining of green as the score falls **is** the diagnosis. |
| 2 | **Five families tuned to clinical severity** (clear · steady · caution · alarm · index) rather than to product surfaces (score · index · action · calm · caution). | Our families are named for what the *patient-facing reality* is, not for which card they sit on. |
| 3 | **`display-light` carries ranks and ratios**, not durations (`#28 → #19`, `6.4 avg position`, `/34`). | We have no durations. We have standings. |
| 4 | **Accent independently measured to `#DCF306`** (theirs: `#DDF20A`). | Same band, our own five-hit centre. Not copied. |
| 5 | **No console-promo rung, no lifecycle-status pills.** Our rail carries *market facets*, not app navigation. | Different product shape: one report, two views, 34 subjects. |
| 6 | **Instrument vocabulary is dermatology-specific** — filaments, dot censuses over 78 queries, the SERP ownership matrix, a clinic constellation. | None of these exist in a work-log tool. |

---

## 10 · Corrections vs v2 (what this atlas overturns)

1. **The canvas is not cool-tinted.** v2's `#E9EAEC` and ink `#131417` have no measured basis —
   every neutral probe is exactly R=G=B. → `#EDEDED` / `#232323`.
2. **Cards are not flat white.** v2 painted `#FFFFFF` everywhere; the reference runs a **five-rung
   ladder** where a nested card is measurably brighter than its parent.
3. **Weight 700 is wrong everywhere.** v2 set `--fw-display: 700` and `.dot-num { font-weight: 700 }`.
   Nothing in the reference renders above 600, and hero numerals sit at ~300–350.
4. **The Score jewel is not orange-heavy.** Green owns everything below y≈0.45. v2 mis-attributed the
   blazing orange, which belongs to the *Index* jewel.
5. **v2's triads are 2–3× too pastel.** v2 green `#2E9E44` vs the ramp's `#399F3A → #278D2C`; and v2
   used flat three-stop triads where the reference layers radials anchored off-card.
6. **There is no bloom in v2.** Every jewel in the reference tints the field beyond its own edge.
7. **One gradient is not a system.** v2 shipped a single `grain-card` on the report hero; the
   reference runs 2–3 jewels per screen as the only chroma surfaces in an otherwise neutral UI.
8. **Lime was `#D9F24F` in v2** — too pale and too green. Measured centre is `#DCF306`.
