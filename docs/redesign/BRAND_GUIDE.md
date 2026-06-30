# Derma Intel — Brand Identity Guide

**"Warm Intelligence"** · v1.0 · 2026-06-30 · Units-led direction
Companion files: [`tokens.css`](tokens.css) (drop-in variables) · [`brand-styleframe.png`](brand-styleframe.png) (the system, rendered) · brief [`PREMIUM_REDESIGN_BRIEF.md`](PREMIUM_REDESIGN_BRIEF.md)

> **What this is.** The foundational visual system for Derma Intel — typography, color, spacing, sizing,
> components, charts, motion. It is established *first*; the dashboard (`web/`, owned by a parallel
> session) is polished against it *after* its layout + charts land. **Apply tokens by name; never
> hard-code raw values.** Keep it essential — this is a working system, not a 47-page manual.

---

## 1 · Essence & voice

Derma Intel is a **premium market-intelligence diagnostic** sold to dermatology clinics: *"here is where
you stand vs. the Guntur market, and what to fix."* It must feel **expensive, confident, and warm** —
never clinical-cold, never accusatory.

Three principles (the lens for every decision):

| | |
|---|---|
| **DIAGNOSE, don't accuse** | Gaps are framed as *opportunity*. The tone is a trusted advisor, not a scold. |
| **VIBRANT, but organized** | Saturated color is a feature, held calm by the oat canvas, generous space, and a strict grid. |
| **NUMBERS you can trust** | Every figure is tabular mono, precise, and sourced. Rigor reads as premium. |

**Voice:** plain, declarative, sentence-case. Short confident headlines ("Trusted in person, invisible
online."), specific numbers, no jargon ("owned/borrowed" → "ranks its own site" / "found only via Practo").

---

## 2 · Logo & mark

- **Wordmark:** `Derma Intel.` set in **Bricolage Grotesque 800**, tracking `-0.02em`, sentence case.
  The **terminal period is the brand accent** (`--purple` default; may take any one rainbow hue per
  context — never multi-colored at once).
- **Mark:** a rounded-square tile (`--r-mark` 14px) on `--ink`, holding a Bricolage **`D`** in `--paper`.
  Favicon / collapsed-nav use. A pixel-grid `D` is an allowed alt (ties to the grid motif, §9).
- **Clear space:** ≥ the cap-height of the `D` on all sides. **Min size:** mark 20px; wordmark 96px wide.
- **Don't:** stretch, add gradients/bevels, outline, recolor the whole wordmark, or place on a busy photo
  without a solid chip behind it.

---

## 3 · Color

The system is **one warm ground + one ink + a saturated rainbow.** See [`tokens.css`](tokens.css) for the
canonical values.

### Ground & ink
| Token | Hex | Use |
|---|---|---|
| `--paper` | `#F4E9E1` | Page canvas. **The brand never sits on pure white.** |
| `--paper-2` | `#EFE5D9` | Wells, hovers, table stripes |
| `--surface` | `#FFFFFF` | Cards / panels |
| `--ink` | `#0B0B0C` | Text, CTAs, mark |
| `--ink-2` / `--ink-3` | `#54504A` / `#8A847B` | Muted / faint |

### The rainbow (brand accents)
`--cobalt #1F6BF0` · `--amber #FFB200` · `--orange #FB5A1E` · `--red #ED3A36` · `--grass #16A64C` ·
`--lavender #A98BF2` · `--purple #9B3FEE`

**Roles:** `--brand` = purple (logo dot, primary CTA, focus). `--brand-2` = cobalt (secondary/info).
`--positive` = grass (has-website / up). `--warning` = amber. `--critical` = red (categorical "no site" /
true alerts only).

### The one discipline that keeps it premium, not chaotic
Color does **two different jobs** — keep them visually distinct:

1. **Categorical** (the rainbow): each hue = a different *thing* (an intent, a category, a presence-type).
   Use the fixed order `--chart-1…7`. **Max ~6 hues in one view.**
2. **Sequential** (the opportunity scale): hue encodes *magnitude*, low→high —
   `--opp-low` amber → `--opp-med` orange → `--opp-high` deep-orange → `--opp-crit` clay.
   **Never** use the rainbow for a magnitude, and never the gradient for categories.

**Usage rules:** one dominant accent per surface; saturated color carries *meaning*, never decoration;
keep large flat color blocks to ≤2 per screen region so the oat canvas can breathe. Body text is always
`--ink`/`--ink-2`, never a rainbow hue. Ensure ≥4.5:1 contrast for text on any color block (white text on
cobalt/orange/red/green/purple; ink text on amber/lavender/oat).

---

## 4 · Typography

Three free, self-hostable faces. **Pairing logic:** characterful display + neutral body + tabular mono.

| Role | Family | Weight |
|---|---|---|
| Display / headlines | **Bricolage Grotesque** | 800 (700 for section heads) |
| Body / UI | **Geist** | 400 / 500 / 600 |
| **All numerals + micro-labels** | **Geist Mono** | 400 / 500 (tabular) |

### Hierarchy
| Step | Token | Font · weight | Size | Tracking / LH | Use |
|---|---|---|---|---|---|
| Hero | `--t-display` | Bricolage 800 | 40→68px | `-.025em` / `.98` | Page headline |
| H1 | `--t-h1` | Bricolage 800 | 30→44px | `-.025em` / `1.08` | Section hero |
| H2 | `--t-h2` | Bricolage 700 | 22→30px | `-.02em` / `1.08` | Section head |
| H3 | `--t-h3` | Bricolage 700 | 19px | `-.01em` | Card title |
| Lede | `--t-lede` | Geist 400 | 17px | `1.5` | Intro paragraph |
| Body | `--t-body` | Geist 400 | 15px | `1.55` | Default copy |
| Small | `--t-small` | Geist 400 | 13px | — | Secondary |
| Label | `--t-label` | **Geist Mono 500** | 11px | `.14em`, UPPERCASE | Eyebrow / micro-label |
| Data / KPI | — | **Geist Mono 500** | per context | tabular (`tnum`) | Every number |

### Rules
- **Numbers are always Geist Mono, tabular.** KPIs, ratings, counts, axis labels, table figures, scores.
- **Display is always roman** — no italic headers (a reliable AI tell). Emphasize with weight/accent color.
- **Headlines are sentence case.** UPPERCASE is reserved for mono micro-labels only.
- Headline length ≤ ~7 words; size *down* one step past ~50 chars so it never wraps to 4 lines.
- `::selection` uses a 12% brand-purple wash.

---

## 5 · Spacing & layout

- **8px base scale** — `--s1`(4) … `--s9`(96). Compose padding/gaps from these only.
- **Content width** `--maxw` 1240px; **page gutter** `--gutter` 40px (→24px ≤900px, →16px ≤560px).
- **Section rhythm:** vertical padding `--s8` (64px) desktop, `--s7` (48px) compact. Group related
  blocks tighter (`--s4`/`--s5`) than sections separate (`--s8`).
- **Graph-paper grid** is the layout's heartbeat: a `--grid-cell` 32px unit. Use it as a faint background
  texture (`--line-2`) and to align tiles/cards. Keep it **barely visible** behind dense data.

---

## 6 · Sizing (the consistency rules)

| Thing | Token | Value |
|---|---|---|
| Pill (buttons, tags, marquee, badges) | `--r-pill` | 999px |
| Card / panel | `--r-card` | 26px |
| Tile / KPI / chart card | `--r-tile` | 18px |
| Input / small element | `--r-sm` | 12px |
| Logo mark | `--r-mark` | 14px |
| Hairline border | `--bw-hair` | 1px `--line` |
| Emphasis outline (tag pills) | `--bw-strong` | 1.5px `--ink` |
| Shadow (resting / raised / popover) | `--shadow-sm` / `-md` / `-pop` | low-spread, warm |

**Rule:** radius is tiered by element size — big surfaces round more (cards 26), small controls less
(inputs 12), interactive pills fully. Never mix sharp 0–4px corners into this system; never exceed 28px.

---

## 7 · Components

Brief specs — full markup is the dashboard session's job; these define the *shape language*.

- **Card** — `--surface`, `--bw-hair` `--line`, `--r-card`, `--shadow-md`, padding `--s5`/`--s6`.
- **Index tile** — saturated rainbow block, `--r-tile`, white (or ink on amber/lavender) text; top row =
  mono number `01` + `↗`, bottom = Bricolage 700 label. Used for ranked/sectioned navigation.
- **Button (pill)** — `--r-pill`, Bricolage 700, padding `13px 22px`. *Primary* = `--ink` on light or
  `--brand` purple; *secondary* = amber/outline. Hover: lift 1px + shadow, `--dur-ui`.
- **Tag / chip (pill)** — `--bw-strong` `--ink` outline, mono 12px, padding `7px 14px`. For
  intent/status filters.
- **Marquee ticker** — full-width pill, saturated bg with *contrasting* rainbow text (e.g. amber on red,
  grass on cobalt), `⚡`/`◆` separators, Bricolage 700. A signature motif; use sparingly (1 per page).
- **KPI block** — `--r-tile` card; mono label, big mono value, mono context line. Promote the headline
  KPI to a filled `--brand` block (white text).
- **Badge / score pill** — `--r-pill`, filled with the matching opportunity-scale color, mono label.

---

## 8 · Charts (the part that makes it *ours*)

Charts are where the rainbow earns its keep. Mirror [`tokens.css`](tokens.css) in JS:

```js
// Derma Intel · ECharts brand mirror
const BRAND = {
  ink: "#0B0B0C", ink2: "#54504A", paper: "#F4E9E1", surface: "#FFFFFF",
  line: "rgba(11,11,12,.10)", mono: '"Geist Mono", monospace', sans: '"Geist", sans-serif',
  categorical: ["#1F6BF0", "#FB5A1E", "#16A64C", "#9B3FEE", "#FFB200", "#ED3A36", "#A98BF2"],
  opportunity: ["#FFB200", "#FB5A1E", "#E8531E", "#B5431F"], // sequential — magnitude only
};
const tooltip = {
  backgroundColor: BRAND.surface, borderColor: "rgba(11,11,12,.14)", borderWidth: 1,
  textStyle: { color: BRAND.ink, fontFamily: BRAND.sans, fontSize: 12 },
  extraCssText: "border-radius:12px;box-shadow:0 10px 30px -12px rgba(0,0,0,.25)",
};
const axis = {
  axisLine: { lineStyle: { color: "rgba(11,11,12,.14)" } }, axisTick: { show: false },
  splitLine: { lineStyle: { color: "rgba(11,11,12,.08)" } },
  axisLabel: { color: BRAND.ink2, fontFamily: BRAND.mono, fontSize: 11 },
};
```

**Rules**
- **Categorical charts** (bars, scatter, donut by type) → `BRAND.categorical` in order; **≤6 hues**.
- **Opportunity score** (any magnitude encoding) → `BRAND.opportunity` gradient; top stays clay.
- **Bars:** `itemStyle.borderRadius` 6 (rounded caps). **Donut:** `radius ["58%","82%"]`, `padAngle` 3,
  `itemStyle.borderRadius` 6, label in the hole (mono).
- **Axes:** mono labels, no ticks, faint splitLines, no mode-bar/clutter. **Numbers tabular.**
- **Entrance:** `animationDuration` `--dur-chart` (720ms), `animationEasing` `"cubicOut"`. KPI numerals
  count up on reveal.
- Optional faint graph-paper backplate behind a hero chart; never behind a dense one.

---

## 9 · Motion principles

GSAP-driven (vendored offline), restrained, **`prefers-reduced-motion`-safe**. Animate `transform` +
`opacity` only.

- **Orchestrated load:** staggered fade + rise (y 10–14px), `--dur-reveal`, `--ease-out`, ~70ms stagger.
- **Hero:** optional Bricolage headline reveal (SplitText, words).
- **Scroll:** ScrollTrigger section reveals, fire once.
- **Charts:** ECharts entrance easing + KPI count-up.
- **Micro:** card hover lift (1px + shadow), pill press, `--dur-micro`/`--dur-ui` with named easings only.
- **Reduced motion:** spatial motion collapses to ≤120ms opacity; charts render instantly.
- *Cut motion before adding it* — if removing an animation loses no information, remove it.

---

## 10 · Grid & pixel motif

The **graph-paper grid** (`--grid-cell` 32px, `--line-2` lines) is the brand's connective texture —
faint page backplates, tile alignment, chart wells. The **pixel mark** (a small icon built from
rainbow grid cells — heart, spark, check) is the playful Units nod; use one per page max, as a detail
that rewards a closer look — never as primary UI.

---

## 11 · Don'ts

- ✗ Pure-white page background (use `--paper` oat).
- ✗ Generic Inter / Roboto / system display; ✗ italic headers; ✗ ALL-CAPS headlines.
- ✗ Proportional figures for data — numbers are **mono + tabular**, always.
- ✗ Rainbow as decoration — every hue must encode something.
- ✗ >6 hues in one chart; ✗ rainbow for a magnitude; ✗ gradient for categories.
- ✗ Alarm-red as the opportunity top (use `--opp-crit` clay — diagnostic, not accusatory).
- ✗ Sharp 0–4px corners or >28px radius creeping into the rounded system.
- ✗ Heavy/glassy drop-shadows — keep them low-spread and warm.
- ✗ Hard-coded hex/px in components — reference tokens by name.

---

## 12 · Tokens

Canonical values live in [`tokens.css`](tokens.css) — colors, type scale, spacing, radii, borders,
motion, chart order. The dashboard session imports/copies it into the app `:root`; this guide explains
*how* to apply them.

## 13 · Fonts & vendoring

All three faces are **free / OFL** and **must be vendored offline** (base64 `woff2`, inlined into the
single `dist` HTML — no CDN, no server; consistent with the project's no-paid-API / offline rule):

| Face | Source | Weights to vendor |
|---|---|---|
| **Bricolage Grotesque** | Google Fonts (OFL) | 700, 800 |
| **Geist** | Google Fonts / Vercel (OFL) — *already vendored in `web/vendor/`* | 400, 500, 600 |
| **Geist Mono** | Google Fonts / Vercel (OFL) — *already vendored* | 400, 500 |

Only **Bricolage Grotesque** is new to vendor. (Units' actual Bunch/Alfabet/Aeonik are paid and are
deliberately substituted with these free equivalents.)
