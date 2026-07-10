# Derma Intel — Brand Identity Guide v2

**"Luminous Precision"** · v2.0 · 2026-07-10 · Superpower-derived direction
Companion files: [`tokens-v2.css`](tokens-v2.css) (canonical values) · [`components.css`](components.css)
(the six codified components) · [`styleframe.html`](styleframe.html) (QA bench) ·
[`GUIDE_COVERAGE.md`](GUIDE_COVERAGE.md) (what this guide covers and why) ·
spec `docs/superpowers/specs/2026-07-10-phase11-luminous-precision-redesign-design.md`.
**Supersedes** `../BRAND_GUIDE.md` ("Warm Intelligence") — v1 kept as history.

> **Purpose.** Not to make every output look the same — to make every output *distinctly
> Derma Intel*. Apply tokens by name; never hard-code raw values. Audience: future
> sessions and collaborators building the product's four pages.

---

## 1 · Brand story — the texture is the meaning

Derma Intel is a **premium diagnostic** sold to dermatology clinics: *here is where you
stand in your market, and what to fix.* The visual system carries that promise:

- The **grain-gradient field** is the market itself — hundreds of patients searching,
  diffuse, noisy, unresolved. Light through frosted glass.
- The **dot-matrix numeral** and the **ruler tick** are what Derma Intel does to that
  noise: resolve it into a precise, instrument-grade reading.

Crisp measurement sitting on diffuse light — **that contrast IS the brand.** If a layout
loses it (noise everywhere, or sterile precision with no life), it isn't Derma Intel.

Three principles, carried over from v1 (the lens for every decision):

| | |
|---|---|
| **DIAGNOSE, don't accuse** | Gaps are opportunity. Trusted advisor, never a scold. |
| **LUMINOUS, but organized** | Color is light, not paint — held calm by the gray canvas, generous space, a strict grid. |
| **NUMBERS you can trust** | Every figure precise, sourced, instrument-rendered. Rigor reads as premium. |

## 2 · Voice — the clinical mirror

We speak the customer's own professional language. The product funnel mirrors a
doctor's funnel, and so does every line of copy:

| Ours | Say it as |
|---|---|
| The report | **the examination** — "You'd never treat before an examination. Neither would we." |
| Monitoring plan | **follow-up visits** — "Re-examine every quarter." |
| Website build | **the treatment** |
| Score movement | **improving / stable / needs attention** (never "failing") |

Personality spectrum (the dot marks us):

```
Calm      ●———————— Energetic        Clinical  ——●—————— Warm
Confident —●——————— Boastful         Premium   ●———————— Flashy
Data      —●——————— Story            Precise   ●———————— Loose
```

Plain, declarative, sentence case. Short confident headlines ("Your patients are
searching. Right now."). Specific numbers over adjectives. No fake urgency — real
scarcity only (FCFS build slots). Roadmap features are "ships to all subscribers,"
never implied as current.

## 3 · Logo

- **Wordmark:** `Derma Intel.` in **Geist 700**, tracking `-0.02em`. The terminal
  period is set in `--lime` — the one place lime touches the wordmark. A muted
  context suffix in `--ink-3` may follow (e.g. `Guntur`).
- **Mark:** rounded-square tile (`--r-chip`) in `--ink`, holding a Geist **D** in
  `--surface`; a 5×7 dot-matrix **D** (Doto-style) is the preferred alt — it ties the
  mark to the numeral motif. *Symbolism: each dot is a data point — a patient searching.*
- **Which version when:** nav → mark · page header → wordmark · favicon → mark.
- **Minimums:** mark 20px · wordmark 96px wide. **Clear space:** the cap-height of the D.
- **Don't:** gradients on the logo, outlining, recoloring the wordmark, multi-color,
  stretching, rotating, dot-matrix for the *words* of the wordmark.

## 4 · Color

One cool ground + one ink + one flat accent + three meaning-bound light fields.
Canonical values live in [`tokens-v2.css`](tokens-v2.css) — reference by name.

**Ground & ink:** `--canvas` #E9EAEC (page — never pure white) · `--canvas-2` (wells,
stripes) · `--surface` #FFFFFF (cards float on the gray) · `--surface-2` (nested, tabs
at rest) · `--ink` #131417 · `--ink-2` (secondary) · `--ink-3` (faint, decorative only).

**Lime** `--lime` #D9F24F — the ONLY flat saturated color. Jobs: status chips, live
badges, the active-tab marker dot, ink-on-lime CTAs. Text on lime is always `--ink`
(14.7:1). **≤3 lime moments per viewport.**

**The triads** (grain-gradient fields; each is a categorical *identity*):

| Triad | Meaning | Stops (a → b → c) |
|---|---|---|
| **GROWTH** | opportunity, demand, improvement | deep green → yellow-green → warm orange |
| **STATUS** | scores, standing, benchmarks | slate → orange glow (center) → light slate |
| **ALERT** | gaps, risks, connect-actions | dusty rose → hot pink (center) → pale pink |

**The discipline (unchanged from v1, restated for v2):** color does two jobs and they
never mix. *Categorical* = which triad (which meaning). *Magnitude* = field intensity
via `--field-dim` (1 full · .55 subdued · .3 ghost) — **never** a hue change, never
alarm-red. Proportional use: canvas ~70% · surface ~20% · ink ~8% · lime + fields ~2%.

## 5 · Typography

| Face | Role | Never |
|---|---|---|
| **Geist** (`--sans`) | every word: UI, body, headlines | — |
| **Doto** (`--dot`, `font-variation-settings: var(--dot-round)`) | hero numerals ONLY | words, body, table data |
| **Geist Mono** (`--mono`) | micro-labels, table numerals, sourced data | headlines |

Scale: `--fs-hero` (clamp 48–84) · `--fs-display` (32–48) · `--fs-title` 24 ·
`--fs-body` 16 · `--fs-small` 14 · `--fs-micro` 11 uppercase tracked (`--ls-micro`).
Weights: 400 body / 500 medium / 600 semibold / 700 display. Micro-labels are always
`--mono` uppercase. Huge size contrast between a hero numeral and its label is a
brand signature — don't flatten it.

## 6 · The six components (`components.css`)

1. **`.grain-card`** (+ `--growth/--status/--alert`) — the signature surface. Display
   only: dot numerals + short labels (`.gc-label`, `.gc-sub`). Never body copy, never
   charts, never more than 2 full-intensity fields per screen region. White text sits
   over mid/deep field zones (lift-shadows are built in).
2. **`.dot-num`** (+ `--hero/--small/--ghost`) — Doto at ROND 100. `--ghost` (`--ink-3`)
   is the paywall placeholder / pending state.
3. **`.ruler`** (+ `--on-field`, `.ruler-marker` with `--pos`) — the measurement motif.
   Any score, position, or benchmark may carry one; decorative use is banned.
4. **`.pill-tab`** — sidebar nav; trailing `.pt-status` chip carries per-item state;
   active = white + `--shadow-card` + lime `.pt-dot`.
5. **`.glass-pill`** — floating status (backdrop blur). Short statements only.
6. **`.chip-lime`** — micro uppercase status. The accent budget lives here.

## 7 · Geometry

"Curved boxy": `--r-card` 24 (cards/fields) · `--r-tab` 18 (tabs/inputs) · `--r-chip` 8
(small square-ish) · `--r-pill` 999 (pills/chips). Spacing on the 4px scale
(`--sp-1…8`); section rhythm uses `--sp-7/8`. Cards sit on the canvas with
`--shadow-card`; nothing outlined heavier than `--line`.

## 8 · Motion — calm-confident

Durations/easings are tokens: `--dur-quick` 240ms (feedback) · `--dur-base` 380ms
(reveals/moves) · `--dur-slow` 520ms (hero moments) · `--ease-out` default,
`--ease-in-out` for in-page moves. Never bounce; never linear for movement.

**Signatures:** numerals **count up** in Doto (the instrument settles) · ruler ticks
**draw in sequence** · grain fields **breathe** (very slow, subtle scale/opacity —
ambient only) · reveals stagger 40–70ms.

**Reduced motion is first-class:** tokens zero out under `prefers-reduced-motion`;
GSAP work uses `gsap.matchMedia()`; the narrative must read fully static.

**Liquid-glass usage map** (module: `web/vendor/liquid-glass.js`, from
`~/.claude/skills/liquid-glass/`): **allowed** — nav chrome, the paywall gate card,
floating pills, modal chrome. **Banned** — behind charts, behind body text, on elements
> ~800px, or carrying meaning (Chromium-only; frosted fallback elsewhere).

## 9 · Iconography

Stroke icons, 1.5px, rounded caps/joins, 20 or 24px grid, `--ink` or `--ink-2` only —
never a triad color, never filled. The product needs ~12 (nav, checks, arrows, search,
phone, WhatsApp, lock, star, chart, doc, pin, plus); add only on real need.

## 10 · Charts (ECharts doctrine)

- Grid lines `--line-2`; axis labels `--mono` `--fs-micro` `--ink-2`; no axis boxes.
- **Categorical** series → triad identities (their `-a` stop as the flat series color:
  growth green / status slate / alert rose) + `--ink` for "you". Max 4 series hues.
- **Magnitude** → opacity/intensity ramps of ONE triad hue, never a hue ramp.
- "You vs market" always: you = `--ink` (or lime marker), market = `--ink-3`.
- Tooltips render as `.glass-pill`. Empty/loading numerals use `.dot-num--ghost`.
- Hero numbers near charts are Doto; in-table numbers are `--mono`, right-aligned.

## 11 · Accessibility (computed, WCAG 2.1)

| Pair | Ratio | Verdict |
|---|---|---|
| `--ink` on `--canvas` | 15.30:1 | body ✓ |
| `--ink-2` on `--canvas` | 5.25:1 | secondary ✓ |
| `--ink-2` on `--surface` | 6.33:1 | secondary ✓ |
| `--ink` on `--lime` | 14.70:1 | CTA ✓ |
| `--ink-3` anywhere | 2.11:1 | **decorative/disabled only — never information** |
| white on field deep zones (e.g. growth-a) | 3.45:1 | display numerals ≥ 32px + lift-shadow only |
| white on field light zones | < 3:1 | **banned for text** — place text over deep zones |

Focus: 2px `--ink` ring offset 2px (lime dot marker on dark). Every interactive element
keyboard-reachable; the gate and forms fully labeled.

## 12 · Misuse — never do these

1. Grain gradient behind body text or a chart. 2. Doto for words. 3. A triad used for
the wrong meaning (pink "growth", green "alert"). 4. Hue ramps for magnitude. 5. Lime
as a large background or > 3 moments/viewport. 6. Pure-white page canvas. 7. Flat CSS
linear-gradient posing as a field (no bleed, no grain). 8. Liquid-glass behind data.
9. Alarm-red anywhere. 10. Bounce easing / decorative parallax under reduced-motion.

## 13 · Closing note

We sell precision about someone's market. A layout that is imprecise — misaligned,
overloud, decorated — contradicts the product before a word is read. The system above
is small on purpose: master the contrast of crisp instruments on diffuse light, and
every page will be distinctly Derma Intel.
