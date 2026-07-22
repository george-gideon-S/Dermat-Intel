# Derma Intel — v3 "Instrument-Grade" Redesign Brief (for Fable 5)

> **Paste this whole file as the opening prompt of the next session.** It is the situation,
> the diagnosis, the corrective canon, and the workstream plan. Read it, load your skills,
> then brainstorm the plan with me before building.

---

## 0 · Who you are and what this is

You are **Claude Fable 5**, continuing the **Derma Intel** project (`E:\TRINADE\Dermat
Analytics and Websites`) — a free, offline, no-API-key market-intelligence product sold to
dermatology clinics in **Guntur, AP**. The business model is locked (the **diagnostic ladder**:
Report ₹4,999 → Monitoring ₹9,999/yr → Website Build from ₹49,999 + retainer ₹4,999/mo) and
the code/data pipeline is done and **must not regress** (154 pytest green, two-dist privacy
split with a build-time leak scan, `modules/` frozen).

**The last redesign (v2 "Luminous Precision", phases A–E) shipped functional but visually
generic.** George's honest verdict, which is correct: the site looks basic, empty, and
templated; the gradients aren't doing work; the graphs are thin; the storytelling is flat.
**Your job this session cycle is to make it look like a $50k studio-grade instrument
dashboard — not a template — and to make the homepage a motion-graphic sales experience.**
This is presentation-only. Do not touch `modules/` or the tests.

**Start by loading skills** (`using-superpowers` → `brainstorming`), then read §1 (canon) and
§2 (diagnosis) **before proposing anything**. Do NOT jump to code. Brainstorm the plan with me,
per workstream, then write specs/plans, then build with tight visual-QA loops.

---

## 1 · The corrective canon — READ THESE FIRST (source-of-truth order)

The v2 brand was extracted from the Superpower health-dashboard reference too shallowly. A
**sister project extracted the SAME reference with pixel-measured rigor** — that is now your
gold standard for *how deep the extraction must go*. Read, in order:

1. `E:\TRINADE\LOG APP V2\docs\redesign\02-reference-atlas.md` — **pixel-sampled ground truth**
   (the load-bearing file): the 5-tier glass **brightness ladder**, the **5 mesh-jewel recipes**
   with sampled anchors + bloom, the **light** type weights (nothing at 700; display numerals
   300–350), the "dot at three scales" motif, exact geometry. **When anything disagrees, the
   reference images win, then this atlas, then everything else.**
2. `E:\TRINADE\LOG APP V2\docs\redesign\01-inspiration-analysis.md` — the DNA read + carry/
   don't-carry discipline.
3. `E:\TRINADE\LOG APP V2\docs\07-design-system.md` — how they turned the atlas into tokens.
4. `E:\TRINADE\LOG APP V2\docs\redesign\brand-guide.html` + `brand-booklet.html` — the rendered
   system (open in the browser). **Study the glass cards, the mesh jewels, the numeral
   registers.** This is the fidelity bar. (These belong to a *different product* — take the
   **material system and rigor**, not their copy, layout, or Work-Log content.)
5. **Our own reference images:** `design\Design Inspiration\*.png` (the 9 Superpower shots) —
   re-study them *through the dermatology lens*: what is a "score jewel", a "biomarker card",
   a "biological-age index" when the subject is a clinic's online visibility, not a body?
6. Our current v2 system to evolve (not worship): `docs\redesign\v2\` (tokens-v2.css,
   components.css, BRAND_GUIDE_V2.md, DESIGN.md).

**Deliverable of the re-extraction:** a **v3 token + component upgrade** (call it
`docs\redesign\v3\`), and an updated brand guide/DESIGN.md. Use **hallmark `study`** to
re-extract and **impeccable** to build. Port the atlas's rigor into the *dermat* context.

---

## 2 · The diagnosis — every red flag, grounded, with the fix direction

George's review, mapped to what's actually on screen (verified against the live build):

**A. Flat, generic surfaces — the #1 problem.** Cards are flat `#FFFFFF` on flat `#E9EAEC`.
The reference is a **5-step luminous glass ladder**: field `#EDEDED` → rail-veil `#F1F1F1`
(white 38% + blur 8) → card `#FCFCFC` (white 80% + blur 14) → elevated `#FDFDFD` → nested
`#FFFFFF`, + a **floating translucent pill** (white 55% + blur 24–28, content ghosts through).
Cards must read *brighter and lit-from-within*, not paper-flat. **liquid-glass.js is already
vendored** — use it on chrome per its usage map.

**B. Gradients wasted.** One lonely, **too-pastel** hero gradient; everything else flat.
The reference runs **twin+ mesh jewels** with **2–3× more saturation** and a **colored bloom**
(soft glow beyond the card edge), each with an assigned role (Score = sand-peach→vivid green;
Index = slate→blazing orange core; Action = hot-pink + lime core; Calm = mint→teal→deep sea;
Caution = butter→amber→coral). **Re-map our triads to real jewels** (Visibility Score jewel,
Market-Rank Index jewel, Opportunity/Action jewel) and crank saturation + add bloom.

**C. Everything is over-weighted.** We set Doto 700 and Geist 700 everywhere. The reference is
**light**: wordmark ~600, display ~500, **big numerals 300–350 light**, labels sentence-case
grey. Introduce the **three numeral registers**: `dot-ink` (naked KPI), `dot-white` (jewel
heroes), and a **new `display-light`** proportional face for ranges/durations. The heaviness is
a big reason it reads generic.

**D. The "vertical examination bars" (5-point examination + treatment-plan rows) are dead.**
Flat identical grey rounded rectangles stacked like disabled form fields — zero craft, zero
data-viz. Redesign them as **instrument rows**: think measured tick-gauges, a small dot-column
or ruler per check, status via the jewel/lime system, a real sense of "reading an instrument."

**E. "What patients actually see" — the dark Google screenshot — REMOVE IT.** It's the worst
element: a raw dark SERP screenshot dropped into a luminous light system — jarring, low-fi,
off-brand, and it dominates. **Delete the raw image.** Replace with a **branded, redrawn
representation**: a stylized in-system "search result" mock (your own components, light, on-
brand) showing competitors present and **the clinic absent** — the loss-aversion beat, but
crafted. (The SERP proof data still exists in the payload; just render it as design, not a photo.)

**F. The dropdown breaks the language.** The "report for" `<select>` is a plain native control.
Make it a **branded glass/pill selector** consistent with the system.

**G. Graphs are thin and cramped, don't fill their space.** The dumbbell labels collide with the
ruler; the breakdown is plain grey bars; the intent strip is sparse; charts feel unfinished and
leave dead card space. **Beautify every chart** to the reference's chart language (monochrome
furniture + data-hue only, scatter-dot / dot-column motifs, tick-ruler gauges, tinted soft
shadows) and **size them to fill their containers**. Make each chart a considered instrument.

**H. Homepage is empty and centered.** The six acts are single centered headlines with vast
whitespace — reads as unfinished, not premium. George wants a **dashboard-grade, dense,
cinematic storytelling experience** — luminous data-world motion, gradient jewels doing the
talking, plans presented as part of the narrative, not a bland grid at the end.

**I. Plan/stat coherence.** The stats, the plan cards, and the info don't feel like one system.
Decide **where plan details live** in the story (recommendation: a "prescription" jewel moment
that pays off the diagnosis, plus a crafted pricing act) and make every stat a jewel/register.

**J. Brand not extracted in the dermat perspective.** Translate, don't transplant: the reference
is a *body* health dashboard; ours is a *clinic visibility* diagnostic. Re-cast every reference
pattern into our domain with the clinical-mirror voice already locked (examination → follow-up
→ treatment).

---

## 3 · The motion-graphic / video layer (the new ambition)

George wants **motion-graphic storytelling built from frames of a generated video**. You have
the tools:

- **`scroll-world` skill** (+ **Higgsfield MCP**, connected): builds a **scroll-scrubbed,
  continuous camera fly-through** landing experience from Higgsfield-generated scenes. This is
  the intended hero mechanic — as the visitor scrolls, the camera flies through a luminous
  "Guntur dermatology data-world" that resolves into the dashboard.
- **`hyperframes` skills** (`motion-doctrine` → `cut-the-curve`, `seam-craft`, `captions-
  overlay`, `oversized-cursor`): the motion *law* for making multi-scene motion feel like ONE
  continuous move, seam-correct, no idle wobble. Load `motion-doctrine` FIRST before composing
  any video/animation.
- **`motion-design` + `gsap-*`** (scrolltrigger/timeline/core/performance): the in-page motion
  once frames exist.

**Two production paths — pick per beat, propose to George:**
1. **Higgsfield MCP in-session** — generate the fly-through scenes + seams directly (scroll-world
   drives this). Fastest loop.
2. **Gemini Omni (George runs it)** — if you want a specific hero film, **write the video prompt
   and give it to George**; he'll return the file, you slice it to frames and scroll-scrub it.

A starter hero-film prompt is in **Appendix A** — refine it in the brainstorm, then either run it
via Higgsfield or hand it to George for Gemini Omni. Motion must **perform, not decorate** —
reduced-motion stays a first-class static path.

---

## 4 · Workstreams — divide and conquer (George's explicit ask: one focused part at a time)

Do these as **separate brainstorm → spec → plan → build → visual-QA cycles**, in this order.
Don't batch them; each gets its own focus and its own approval gate.

- **WS-1 · Re-extraction & v3 design system** (foundation). Port the atlas rigor into dermat:
  glass brightness ladder, jewel recipes (saturated + bloom), light type + 3 numeral registers,
  the dot-motif, branded selector, instrument-row pattern, redrawn-SERP component. Output:
  `docs\redesign\v3\` tokens/components + updated guide + DESIGN.md. **Everything downstream
  consumes this — do it first, get it approved.**
- **WS-2 · Homepage: storytelling + motion.** Rebuild the six acts as a dense, luminous,
  motion-graphic experience (scroll-world/Higgsfield frames + GSAP). Fix the emptiness, place
  the plans in the narrative, land the gate + pricing as crafted beats. Typography + spacing pass.
- **WS-3 · "Your Clinic" report as a dashboard.** Glass-jewel hero (Visibility Score jewel +
  Rank Index jewel), redesign the 5-point examination instrument rows, **remove the dark
  screenshot** (branded SERP viz instead), rebuild every chart, the treatment-plan "prescription."
- **WS-4 · "The Market" as a dashboard.** Reskin the deep charts (opportunity map, beeswarm,
  butterfly, heatmap, waffle) into the jewel/glass system; make them fill space; polish.
- **WS-5 · Motion & micro-interaction system-wide.** Count-ups, gradient drift/bloom, tick-draw,
  staggered reveals, cursor-led beats; performance pass (`gsap-performance`); reduced-motion.

For each: run **`taste-skill` pre-flight** (anti-slop) before calling it done, and **QA with
Playwright screenshots** at 1440 + 390, reading the images back and iterating until it matches
the reference fidelity. `karpathy-guidelines` (surgical, verify against criteria) and
`ponytail` (don't over-build) keep it disciplined.

---

## 5 · Skills & MCPs to use (all installed/connected)

**Design/craft:** `hallmark` (study/re-extract), `impeccable` (the build loop — primary),
`taste-skill` (anti-slop pre-flight), `liquid-glass` (glass chrome — already vendored).
**Motion:** `motion-design` (choreography intent), `gsap-core/timeline/scrolltrigger/
performance` (implement), `scroll-world` (scroll-scrubbed hero), `hyperframes` →
`motion-doctrine` first, then `cut-the-curve`/`seam-craft`/`captions-overlay`/`oversized-cursor`.
**Generation:** **Higgsfield MCP** (video/image frames), **Stitch MCP** (screen references →
re-implement against our tokens, never ship its markup).
**Memory:** **codebase-memory-mcp** — query the graph before grepping (project indexed:
`E-TRINADE-Dermat-Analytics-and-Websites`; graph UI at **http://localhost:9749**). Preview the
site locally with `python -m http.server 8090 --bind 127.0.0.1` from `web\dist` (home at
`/public/`, report at `/`).
**Discipline:** `karpathy-guidelines`, `ponytail`.

---

## 6 · Guardrails (do not break)

- **Presentation only.** `modules/` and the **154 pytest** stay green and untouched. Only
  `web/` + `docs/redesign/` change; `web/build_web.py` may gain TDD'd view logic only.
- **Two-dist privacy holds.** Public dist keeps zero real clinic names/scores; the **build-time
  leak scan must still pass** (scan authored surfaces, not base64 blobs; STOP-list generics).
- **No paid APIs / no keys at runtime.** Dists stay **offline & self-contained** — vendor every
  font/lib as base64/local; Higgsfield/Gemini frames are baked in at build as local assets, not
  fetched live. Razorpay links + WhatsApp number are config, still George's to fill.
- **Don't regress the business model** (diagnostic ladder) or the clinical-mirror voice.
- Secrets rule: `.env`/config only, never inline a key. Commit frequently to local `master`,
  `Co-Authored-By: Claude …`.

---

## 7 · Definition of done (the bar)

Screenshot the three surfaces at 1440 and put them beside `design\Design Inspiration\*.png` and
the LOG APP V2 `brand-guide.html`. It's done when: **cards read as luminous glass**, **mesh
jewels are saturated and bloom**, **numerals are light and instrument-grade**, **no flat dead
bars, no raw screenshot**, **every chart is beautiful and fills its space**, **the homepage
plays as a motion-graphic story** (not empty), and **taste-skill pre-flight passes**. George
should look at it and feel it's worth ₹4,999 — and want to show it off.

**First move:** load `superpowers:using-superpowers` and `superpowers:brainstorming`, read the
canon (§1), then brainstorm **WS-1** with me. Don't build until the v3 system is approved.

---

## Appendix A · Starter hero-film prompt (for Higgsfield MCP or Gemini Omni)

> Refine in the brainstorm before generating. Target: a seamless, scroll-scrubbable ~12–20s
> loopable flight, light/luminous, no text (text is added in-page), 16:9 + a 9:16 variant.

```
A continuous, slow cinematic camera flight through an abstract luminous data-world for a
premium dermatology market-intelligence product. Cool near-white (#EDEDED) infinite studio
space, soft volumetric light. Floating frosted-glass cards and softly glowing mesh-gradient
"jewels" (sand-peach melting into vivid green; cool slate around a blazing orange core; a
hot-pink jewel with a lime core) drift like instruments in space. Dot-matrix numerals and
tick-ruler gauges made of light hang in the air. The camera glides forward with no cuts,
weaving between the glass cards, passing through a cloud of small colored dots (a scatter
map of clinics) that part around the lens, then settles as the world resolves into a clean
dashboard. Calm, confident, instrument-grade, expensive. Soft depth of field, gentle bloom,
grain-free, no logos, no text, no people. Palette: neutral greys, one acid-lime accent,
saturated mesh gradients. Motion: smooth, weighty, decelerating — one unbroken move.
```

Alternate ambient loops (one per act, if the fly-through is too much for a first pass): a slow
drifting single mesh jewel with bloom; a scatter-dot field gently parallaxing; a tick-ruler
gauge whose marker eases into place. Keep them subtle — they sit *behind* crafted UI, never
carry meaning, and yield to reduced-motion.
