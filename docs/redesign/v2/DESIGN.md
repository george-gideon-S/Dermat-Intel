# Design System: Derma Intel — "Luminous Precision"

A premium market-intelligence diagnostic for dermatology clinics. This document is the
single source of truth for generating any Derma Intel screen. It is self-contained:
follow it without access to any other file.

## 1. Visual Theme & Atmosphere

A luminous, gallery-airy analytics interface: **crisp measuring instruments sitting on
diffuse colored light.** The canvas is a cool light gray — never pure white — on which
white cards visibly float. Hero numbers render as round-dot dot-matrix readouts, like
laboratory equipment. Soft, grainy, out-of-focus color fields (light through frosted
glass) carry meaning; everything else is calm, neutral, and precise.

- **Density:** airy (3/10) — generous space, few elements per view, huge number-to-label
  size contrast.
- **Variance:** offset asymmetric (5/10) — mixed card sizes in the same row, sidebar +
  main split, KPI strips with uneven rhythm. Never three equal cards in a row.
- **Motion:** fluid and calm (5/10) — numbers count up, tick marks draw in sequence,
  reveals stagger. Nothing bounces.

The mood in one line: *a clinical instrument that loves its patient — precise, warm-lit,
unhurried, expensive.*

## 2. Color Palette & Roles

- **Canvas Gray** (#E9EAEC) — page background. The brand never sits on pure white.
- **Recessed Gray** (#E2E4E7) — wells, hover grounds, table stripes.
- **Card White** (#FFFFFF) — cards and panels; the floating layer above the canvas.
- **Nested White** (#F5F6F7) — nested panels and pill tabs at rest.
- **Ink** (#131417) — primary text, icons, hero numerals on light. Never pure black.
- **Muted Ink** (#5C6066) — secondary text, captions, metadata.
- **Faint Ink** (#9FA3A9) — decorative/disabled/ghost values ONLY, never information.
- **Signal Lime** (#D9F24F) — the ONLY flat saturated accent. Tiny doses: status chips,
  live badges, active-tab marker dots, dark-text CTAs. Text on lime is always Ink.
  **Maximum 3 lime moments per viewport.** Lime is never a background surface.

**The gradient triads** — soft, grainy, diffuse color fields used on hero KPI cards.
Each triad is a fixed *meaning*; built as overlapping blurred radial gradients (one
white light-bleed at a top corner, deep stop at bottom-left, glow at center, third stop
at top-right) with a subtle film-grain noise overlay (~18% opacity). Never a flat,
banded linear gradient.

- **GROWTH field** — deep green (#2E9E44) → yellow-green (#A8C84B) → warm orange
  (#E8973A). Meaning: opportunity, demand, improvement.
- **STATUS field** — slate (#97A2B2) → orange center-glow (#ED9A3E) → light slate
  (#C7CDD6). Meaning: scores, standing, benchmarks.
- **ALERT field** — dusty rose (#E39CB4) → hot pink center (#EE6D96) → pale pink
  (#F2C6D2). Meaning: gaps, risks, connect-actions.

**Color discipline:** category = which triad; magnitude = the field's intensity
(full / subdued / ghost via opacity). Never encode magnitude with a hue change, and
alarm-red does not exist anywhere in the system.

## 3. Typography Rules

- **Words — Geist** (sans-serif): all UI, body, and headlines. Headlines weight 700,
  tracking −0.02em, sentence case, controlled scale (clamp 32–84px display range).
  Body 16px, relaxed leading (1.55), 65ch max width.
- **Hero numerals — Doto** (round-dot dot-matrix, roundness 100, weight 700): every
  hero number, score, rank, and count-up. NUMERALS ONLY — Doto never sets words, body
  text, or table data. Ghost/pending values render in Faint Ink.
- **Micro-labels & data — Geist Mono**: 11px uppercase labels tracked +0.08em, table
  numerals (right-aligned), sourced data lines.
- The signature: a huge Doto numeral over a tiny mono uppercase label. Do not flatten
  this contrast.
- **Banned:** Inter, generic system serifs, any serif in the dashboard, dot-matrix for
  words.

## 4. Component Stylings

- **Grain-field KPI card:** 24px radius, diffuse triad field with film grain and a
  white corner light-bleed; white centered label (14px), giant Doto numeral, short
  white sub-line, optional white ruler strip with position marker. Display surface
  only — never body copy, never charts on it. Max 2 full-intensity fields per screen
  region. White text sits over the field's deep zones with a soft dark lift-shadow.
- **Pill sidebar tabs:** 18px radius rows; icon + label + trailing status chip (mono,
  e.g. "71/100", "Missing"). Rest = nested white; hover = white; active = white + soft
  card shadow + a small lime marker dot with a lime halo.
- **Glass status pill:** fully rounded, frosted (background blur ~14px), hairline white
  border, floating shadow; short statements like "↗ Market improving +3.2 · 90 days".
- **Ruler strip:** the measurement motif — 1px tick marks every 8px, taller every 5th,
  with a 3px position marker. Attach to scores and benchmarks; decorative use banned.
- **Lime chip:** fully rounded, lime fill, 11px uppercase ink text ("TOTAL", "LIVE ·
  Q3", "BEST VALUE").
- **Buttons:** ink fill with white text (primary) or ink-on-lime (emphasis); flat, no
  glow; tactile 1px press translate. One primary CTA per view.
- **Cards/panels:** white, 24px radius, soft diffuse shadow (no hard borders heavier
  than 1px at 10% ink).
- **Inputs:** label above, helper/error below, 18px radius, 2px ink focus ring.
- **Loaders/pending:** dot-matrix ghost numerals ("##") and skeleton blocks matching
  layout — no circular spinners.
- **Empty states:** a composed grain-field card at ghost intensity with instructions.

## 5. Layout Principles

Max-width ~1400px centered; CSS grid; sidebar (≈270px) + main split for dashboards.
KPI strips are baseline-aligned rows of Doto numerals with uneven, content-driven
rhythm. Mixed card sizes in the same grid (one 2×, several 1×) — never three equal
cards. Spacing on a 4px scale; section rhythm 48–80px, `clamp()` on mobile. Single
column below 768px, no horizontal scroll, 44px touch targets, full-height sections
via dynamic viewport height (never fixed screen height).

## 6. Motion & Interaction

Calm-confident. Feedback 240ms, reveals/moves 380ms, hero moments 520ms; decelerating
cubic-bezier easing (no bounce, no linear movement). Signatures: numerals **count up**
like an instrument settling; ruler ticks **draw in sequence**; grain fields **breathe**
(very slow ambient scale/opacity); list reveals stagger 40–70ms. Transforms and opacity
only. Reduced-motion is first-class: all animation durations drop to zero and the page
must read fully static.

## 7. Anti-Patterns (Banned)

- Alarm-red, neon glows, purple/blue AI gradients, oversaturated accent abuse.
- Pure black (#000000) or pure-white page canvas.
- Flat linear gradients posing as grain fields (no bleed, no grain = banned).
- Doto/dot-matrix for words; Inter; serifs in the dashboard.
- Body copy or charts on gradient fields; liquid-glass/frosted panels behind data.
- Hue ramps for magnitude; a triad used against its meaning (pink growth, green alert).
- Three equal cards in a row; centered hero with a lonely centered CTA.
- Emojis in UI; AI copy clichés ("Elevate", "Seamless", "Unleash"); fake round numbers.
- "Scroll to explore" hints, bouncing chevrons, custom cursors.
- Generic placeholder names — use realistic Indian clinic/doctor names when mocking
  (e.g. "Dr. Lakshmi Skin & Hair Clinic", "Sri Venkateswara Derma Care").
- More than 3 lime moments in a viewport; lime as a surface.
- Bounce easing; parallax or ambient motion that survives reduced-motion.
