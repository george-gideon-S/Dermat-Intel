# Phase A — "Luminous Precision" Brand Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **This session:** executing inline (design-taste work; the inspiration analysis lives in-session).

**Goal:** Produce the complete v2 brand system — tokens, component recipes, brand guide (MD + HTML + booklet PDF), and Stitch `DESIGN.md` — that Phases B–E consume.

**Architecture:** Everything lands in `docs/redesign/v2/` except fonts (`web/vendor/`). The HTML guide is a single offline file built *in* the system itself (the proof). No `modules/` changes; zero test impact. Visual QA via Playwright screenshots (repo convention).

**Tech Stack:** Plain HTML/CSS/JS (no framework, matches `web/`), Doto + Geist woff2 vendored offline, Playwright (installed) for QA + PDF print, liquid-glass module from `~/.claude/skills/liquid-glass/`.

**Spec:** `docs/superpowers/specs/2026-07-10-phase11-luminous-precision-redesign-design.md` §2.
**Constraint reminders:** no CDN/network at runtime; TLS-intercepted machine — downloads via PowerShell (schannel) or `requests` + `%USERPROFILE%\node_ca_bundle.pem`; never disable TLS verification.

---

### Task 1: Extract the structural checklist from the sample brand guides

**Files:**
- Read: `design/Brand Identity Design Samples/FPA-v2026.pdf`, `Optty-2025.pdf` (Coca-Cola optional)
- Create: `docs/redesign/v2/GUIDE_COVERAGE.md` (working note, committed)

- [ ] **Step 1:** Read 8–12 representative pages of each PDF (Read tool, `pages` param). Record *section inventory only* (what a complete guide covers), not aesthetics.
- [ ] **Step 2:** Write `GUIDE_COVERAGE.md`: two-column table — "FPA/Optty covers" vs "Derma Intel v2 needs it? (yes/no/why)". Explicitly decide against sections a 4-page digital product doesn't need (e.g. stationery, vehicle livery).
- [ ] **Step 3:** Commit: `docs(brand-v2): guide coverage checklist from FPA/Optty samples`

### Task 2: Vendor the Doto dot-matrix font offline

**Files:**
- Create: `web/vendor/doto-500.woff2`, `web/vendor/doto-700.woff2` (static instances)

- [ ] **Step 1:** Fetch Google Fonts CSS with a woff2-capable UA, then the woff2 URLs it references (PowerShell/schannel):

```powershell
$css = Invoke-WebRequest -Uri "https://fonts.googleapis.com/css2?family=Doto:wght@500;700&display=swap" -Headers @{ "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36" } -UseBasicParsing
# parse url(...) entries per weight, Invoke-WebRequest each to web/vendor/doto-<w>.woff2
```

- [ ] **Step 2:** Verify magic bytes are `wOF2` and size > 10 KB each:

```powershell
[System.Text.Encoding]::ASCII.GetString((Get-Content "web\vendor\doto-500.woff2" -Encoding Byte -TotalCount 4))  # expect wOF2
```

- [ ] **Step 3:** Render a smoke HTML (scratchpad) with `@font-face` + digits `0123456789`, screenshot via Playwright, confirm dot-matrix glyphs (not fallback).
- [ ] **Step 4:** Commit: `chore(web): vendor Doto 500/700 woff2 offline (OFL) — dot-matrix numerals`

### Task 3: `tokens-v2.css` — the single source of truth

**Files:**
- Create: `docs/redesign/v2/tokens-v2.css`

- [ ] **Step 1:** Write the full token sheet. Canonical values (tune only during Task 4 visual QA):

```css
:root {
  /* Surfaces — cool, airy, luminous */
  --canvas:    #E9EAEC;  /* page ground — never pure white */
  --canvas-2:  #E2E4E7;  /* recessed wells / hover ground */
  --surface:   #FFFFFF;  /* cards */
  --surface-2: #F5F6F7;  /* nested panels, pill tabs at rest */
  /* Ink */
  --ink:   #131417;  --ink-2: #5C6066;  --ink-3: #9FA3A9;
  /* The one flat accent */
  --lime:      #D9F24F;  --lime-ink: #131417;   /* text on lime is always ink */
  /* Gradient triads (grain-gradient fields; meaning-bound) */
  --tri-opp-a: #3FA544;  --tri-opp-b: #9BC34A;  --tri-opp-c: #E8973A; /* opportunity/growth */
  --tri-sta-a: #E8973A;  --tri-sta-b: #D9B39A;  --tri-sta-c: #8B97A8; /* status/score */
  --tri-ale-a: #E86FA4;  --tri-ale-b: #ED4B78;  --tri-ale-c: #F0A8B8; /* alerts/connect */
  /* Lines & elevation */
  --line: rgba(19,20,23,.10);  --line-2: rgba(19,20,23,.05);
  --shadow-card: 0 1px 2px rgba(19,20,23,.04), 0 12px 32px -16px rgba(19,20,23,.14);
  --shadow-float: 0 24px 56px -20px rgba(19,20,23,.22);
  /* Radii — "curved boxy" */
  --r-card: 24px;  --r-tab: 18px;  --r-pill: 999px;  --r-chip: 8px;
  /* Type */
  --sans: "Geist", system-ui, sans-serif;
  --dot:  "Doto", "Geist Mono", monospace;      /* hero numerals ONLY */
  --mono: "Geist Mono", ui-monospace, monospace; /* small labels, table numerals */
  /* Motion (motion-design doctrine: calm-confident) */
  --dur-quick: 240ms; --dur-base: 380ms; --dur-slow: 520ms;
  --ease-out: cubic-bezier(.22,.9,.24,1); --ease-in-out: cubic-bezier(.6,0,.2,1);
}
```

  Plus (same file): a type scale block (`--fs-hero` 64/48/36 clamp … `--fs-micro` 11px uppercase tracked), spacing steps (4/8/12/16/24/32/48/80), and z-layers.
- [ ] **Step 2:** Comment every token group with its *job* (mirroring v1's style) + the two color-job rules (categorical = triad identity; magnitude = gradient intensity, never alarm-red).
- [ ] **Step 3:** Commit: `feat(brand-v2): tokens-v2.css — Luminous Precision token sheet`

### Task 4: Component recipes + styleframe (the visual gate)

**Files:**
- Create: `docs/redesign/v2/components.css` (recipes), `docs/redesign/v2/styleframe.html` (test bench)

- [ ] **Step 1:** Implement the six codified components in `components.css`, consuming ONLY tokens:
  1. **Grain-gradient card** — the load-bearing recipe:

```css
.grain-card {
  position: relative; border-radius: var(--r-card); overflow: hidden;
  color: #fff; box-shadow: var(--shadow-card);
}
.grain-card::before { /* diffuse light: oversized, offset radials — never a flat linear */
  content: ""; position: absolute; inset: -40%;
  background:
    radial-gradient(60% 55% at 22% 78%, var(--g-a) 0%, transparent 62%),
    radial-gradient(70% 60% at 80% 18%, var(--g-c) 0%, transparent 66%),
    radial-gradient(90% 80% at 55% 50%, var(--g-b) 0%, transparent 75%);
  filter: blur(28px) saturate(1.05);
}
.grain-card::after { /* the grain that makes it premium */
  content: ""; position: absolute; inset: 0; opacity: .16; mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/></filter><rect width='160' height='160' filter='url(%23n)' opacity='0.6'/></svg>");
}
.grain-card--opp { --g-a: var(--tri-opp-a); --g-b: var(--tri-opp-b); --g-c: var(--tri-opp-c); }
.grain-card--sta { --g-a: var(--tri-sta-a); --g-b: var(--tri-sta-b); --g-c: var(--tri-sta-c); }
.grain-card--ale { --g-a: var(--tri-ale-a); --g-b: var(--tri-ale-b); --g-c: var(--tri-ale-c); }
```

  2. **Dot numeral block** (`.dot-num` — Doto, sizes hero/large/mid, optional count-up hook class)
  3. **Ruler strip** (`.ruler` — repeating-linear-gradient ticks, every 5th taller via layered gradient, optional marker)
  4. **Pill tab** (`.pill-tab` — icon + label + trailing status chip, rest/hover/active states)
  5. **Glass pill** (`.glass-pill` — backdrop-filter blur + hairline + shadow-float; liquid-glass JS optional enhancement)
  6. **Lime chip** (`.chip-lime` — the only flat accent; uppercase micro label)
- [ ] **Step 2:** Build `styleframe.html`: one screen, all six components with realistic Derma content (score 71, rank #12, "15 of 34 invisible", clinic pill tabs). `@font-face` pointing at `../../../web/vendor/*.woff2` (relative — this file is for internal QA, not shipping).
- [ ] **Step 3:** Playwright screenshot at 1440×900 (scratchpad script, repo pattern) → compare against `design/Design Inspiration/` shots side by side. Iterate until the grain field reads as diffuse light (checklist: no visible gradient banding; grain present but not noisy at 100% zoom; Doto digits legible; ticks crisp at 1px).
- [ ] **Step 4:** Contrast checks: white-on-triad hero text and ink-on-lime ≥ 4.5:1 (compute; darken triad stops if needed).
- [ ] **Step 5:** Commit: `feat(brand-v2): component recipes + styleframe (grain card, dot numerals, ruler, pills, chips)`

### Task 5: `BRAND_GUIDE_V2.md` — the doctrine

**Files:**
- Create: `docs/redesign/v2/BRAND_GUIDE_V2.md`

- [ ] **Step 1:** Write sections per `GUIDE_COVERAGE.md` decisions. Must include: essence & the three principles (carry-overs restated); **clinical-mirror voice** (consultation/examination/follow-up/treatment; do/don't copy examples incl. pricing copy from spec §1); logo treatment for v2 (wordmark on canvas, lime-dot variant; ink tile mark); color jobs + triad meanings + the lime rule; type roles (Geist/Doto/Geist Mono) + scale; the six components with usage rules; **liquid-glass usage map** (allowed: nav, gate, pills, modal chrome — banned: behind charts/text); motion doctrine (durations/easings from tokens, count-up + tick-draw signatures, reduced-motion first-class); chart styling rules for ECharts (grid = line-2, categorical = triad identities, magnitude = intensity); do/don't gallery (min 8 pairs); accessibility (contrast table, focus states).
- [ ] **Step 2:** Cross-check every named token/class exists in `tokens-v2.css`/`components.css`. Fix drift.
- [ ] **Step 3:** Commit: `docs(brand-v2): BRAND_GUIDE_V2.md — Luminous Precision doctrine`

### Task 6: The HTML brand guide (built in the system)

**Files:**
- Create: `docs/redesign/v2/brand-guide.html` (single file, offline: inlines tokens-v2.css + components.css + base64 fonts)

- [ ] **Step 1:** Build the page: sticky pill-tab side nav (§sections), hero (wordmark + dot-numeral "v2.0" + ruler), then one section per BRAND_GUIDE_V2.md chapter rendered *as* the system: live token swatches (computed from CSS vars, not hardcoded), the six components live, triad cards with meaning labels, type specimens, motion demos (hover/count-up; static under reduced-motion), the do/don't gallery.
- [ ] **Step 2:** Font embedding: small Python snippet (scratchpad) base64-inlines the four woff2 files into a `<style>` block (pattern: `web/vendor_assets.py`).
- [ ] **Step 3:** Playwright QA: screenshots at 1440 + 768 widths; console-error check must be clean; total file < 4 MB.
- [ ] **Step 4:** Run taste-skill pre-flight against the page (no templated defaults, spacing rhythm, type contrast).
- [ ] **Step 5:** Commit: `feat(brand-v2): brand-guide.html — interactive guide built in the system`

### Task 7: Stitch `DESIGN.md`

**Files:**
- Create: `docs/redesign/v2/DESIGN.md`

- [ ] **Step 1:** Using stitch-skill's semantic format: encode tokens, type scale, component inventory, layout rules (asymmetric grids, gapless bento where used), motion rules, and anti-generic constraints from the guide.
- [ ] **Step 2:** Validate it stands alone (a Stitch/agent consumer never sees our repo): no relative references except font names.
- [ ] **Step 3:** Commit: `docs(brand-v2): DESIGN.md — Stitch-semantic design system export`

### Task 8: Print booklet

**Files:**
- Create: `docs/redesign/v2/brand-booklet.html`, `docs/redesign/v2/Derma-Intel-Brand-Guide-v2.pdf`

- [ ] **Step 1:** Booklet HTML: A4 landscape pages via `@page` + `page-break-*`; cover, contents, one chapter per spread; footer folios with ruler motif. Reuses the same inlined CSS/fonts as Task 6.
- [ ] **Step 2:** Print via Playwright (scratchpad script): `page.pdf(format="A4", landscape=True, print_background=True)`.
- [ ] **Step 3:** Read 3–4 pages of the PDF back (Read tool) to verify render fidelity (fonts embedded, gradients present, no clipped pages).
- [ ] **Step 4:** Commit: `feat(brand-v2): print booklet HTML + Derma-Intel-Brand-Guide-v2.pdf`

### Task 9: Wire the project to v2

**Files:**
- Modify: `CLAUDE.md` (brand pointer + current-state), `docs/redesign/BRAND_GUIDE.md` (add superseded banner at top)

- [ ] **Step 1:** CLAUDE.md: point "brand locked" line to v2 files; note v1 superseded-but-kept.
- [ ] **Step 2:** v1 BRAND_GUIDE.md: prepend a one-line superseded banner linking to v2.
- [ ] **Step 3:** `python -m pytest -q` → expect the full suite green (no logic touched; this is the regression tripwire).
- [ ] **Step 4:** Commit: `docs(brand-v2): project wiring — v2 is the canonical brand`

---

**Out of scope for this plan (own plans, in order):** Phase B home rebuild · Phase C Your Clinic · Phase D Market · Phase E Build-with-Trinade page. Each consumes `docs/redesign/v2/` and must not fork token values.
