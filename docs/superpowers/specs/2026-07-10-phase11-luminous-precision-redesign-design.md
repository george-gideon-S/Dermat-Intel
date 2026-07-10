# Phase 11 — "Luminous Precision" Redesign · Design Spec

**Date:** 2026-07-10 · **Status:** approved by George (this session) · **Supersedes:** the
"Warm Intelligence" visual direction (`docs/redesign/BRAND_GUIDE.md` v1) as the *aesthetic*;
carries over its non-aesthetic doctrine (see §2).

## 0 · Goal

Rebuild the product to studio quality around three pages plus one new page, on a brand system
derived precisely from the Superpower-style design inspiration
(`design/Design Inspiration/*.png`), to sell Derma Intel subscriptions to Guntur dermatology
clinics and cross-sell Trinade website builds.

**Pages:**
1. **Home** — storytelling sales narrative ending in a personalized paywall gate + pricing.
2. **Your Clinic** — paid, per-clinic analytics dashboard (powered by `modules/report.py`).
3. **The Market** — paid, all-dermatologists analytics dashboard.
4. **Build with Trinade** (new) — website-request form + consultation booking (FCFS exclusivity).

## 1 · Decisions log (locked with George, 2026-07-10)

| Decision | Choice |
|---|---|
| Pricing ladder | **Two plans only.** Monthly **₹4,499/mo** (hero, "cancel anytime") · Annual **₹3,999/mo billed yearly** (₹47,988/yr, "save ₹6,000/yr"). One-time tier dropped entirely. |
| Price anchor | Value framing ("less than the revenue of one new patient"), never fake urgency. Real scarcity only (website-build FCFS; optionally "launch pricing for the first N clinics" with a true N). |
| Checkout | **Razorpay payment links** — public URLs in `config.py` (`RAZORPAY_LINK_MONTHLY`, `RAZORPAY_LINK_ANNUAL`), pasted by George from his Razorpay dashboard. Not secrets; safe to commit. Until real links exist, buttons render a "payments opening soon → WhatsApp us" fallback. |
| Public data privacy | **Anonymize until paid.** Real clinic names/scores never ship in the public payload (view-source-proof, not CSS blur). Real names appear only in the private dist. |
| Roadmap features | Social-media analysis (Instagram/YouTube/X) etc. sold honestly as *"ships to all subscribers"*, clearly labeled upcoming — never implied as current. |
| Brand | v2 "Luminous Precision" supersedes v1 aesthetics per George's brief; `web/` ownership transfers to this workstream (parallel session's Increments A–C get rebuilt). |

## 2 · Brand v2 — "Luminous Precision"

**DNA (from the inspiration, copied precisely):** cool airy gray canvas; diffuse *grainy*
tri-color gradient fields on hero cards; dot-matrix numerals for every hero number;
ruler/tick strips as the measurement motif; pill-shaped sidebar tabs with per-item status
chips; floating glass status pills; a single restrained lime accent; neutral grotesque type
with huge size contrast; generous space.

**Carried over from v1 (non-aesthetic doctrine):**
- *Diagnose, don't accuse* voice — gaps are opportunity; plain, declarative, sentence case.
- Color does two jobs, kept visually distinct: **categorical** (hue = a thing) vs
  **sequential** (magnitude). Magnitude re-lands as **gradient intensity**, never alarm-red.
- **Tokens by name, never raw values.** Fonts vendored offline (base64 woff2, no CDN).
- Numbers are precise, sourced, tabular.

**System specifics:**
- **Canvas** `#E9EAEC`-family cool gray · white cards · near-black ink · **lime** (`#D8F34E`
  family) as the only flat saturated accent (chips, live badges, ink-on-lime CTAs).
- **Gradient triads** (each with an assigned meaning):
  green→orange = opportunity/growth · orange→slate-blue = status/score ·
  pink→magenta = alerts/connect-actions.
  Recipe: layered oversized radial gradients + SVG `feTurbulence` grain overlay (or
  pre-rendered noise PNG at low opacity) — diffuse light, never flat CSS gradients.
- **Type:** Geist (UI/body — kept, already vendored) · **Doto** (OFL variable dot-matrix —
  all hero numerals; vendor offline) · Geist 700/800 tightened for display. Bricolage retires.
- **Components codified in the guide:** grain-gradient KPI card (3 sizes) · dot-matrix numeral
  block · ruler-tick strip · pill sidebar tab + status chip · floating glass status pill ·
  **liquid-glass usage map** (allowed: nav, paywall gate, floating pills, modal chrome;
  banned: behind charts, behind body text). Liquid-glass module:
  `~/.claude/skills/liquid-glass/liquid-glass.js` → copy into `web/vendor/`.
- **Motion doctrine** (via motion-design + gsap-* skills): calm-confident; 300–500 ms;
  expo/power easing; staggered reveals; numerals count up in dot-matrix; ticks draw in
  sequence; `prefers-reduced-motion` respected via `gsap.matchMedia()`.

**Phase A deliverables** (in `docs/redesign/v2/`): `tokens-v2.css` · `BRAND_GUIDE_V2.md` ·
an HTML guide page **built in the system itself** · a print booklet · `DESIGN.md`
(Stitch-semantic format). Structural completeness checked against the FPA / Optty sample
guides (`design/Brand Identity Design Samples/`) — borrow their *coverage* (logo usage, color
jobs, type scale, motion, iconography, do/don'ts, applications), not their aesthetics.

## 3 · Architecture — two dists (the privacy mechanism)

`web/build_web.py` produces **two artifacts**:

| Dist | Contents | Payload | Distribution |
|---|---|---|---|
| **Public** | Home (+ Build-with-Trinade page) | Aggregates + anonymized teasers only. Real names/scores **never present** (view-source-proof). Clinic self-lookup via fuzzy-matchable name hashes + rank *bucket* only. | Vercel, public URL |
| **Private** | All pages | Full data, real names | Handed to paying clinics / sales meetings |

Anonymization + payload-split logic is **TDD'd** (`tests/`). `modules/` and the existing 135
tests stay untouched and green.

## 4 · Home — the sales narrative (StoryBrand: doctor = hero, Trinade = guide)

1. **Hook** — luminous near-blank canvas; real Guntur queries type themselves; dot-matrix
   counter climbs to **80**. "Your patients are searching. Right now."
2. **The market** — 34 clinics materialize as a beeswarm; demand distribution builds.
   Aggregate, real.
3. **The gap** — beeswarm splits: **15 of 34 invisible online**; anonymized teasers
   ("Clinic G — 4.9★, 200+ reviews, zero web presence") on grain-gradient cards.
4. **The turn** — owned vs borrowed visibility (butterfly motif): what the visible few own.
5. **Find yourself** — search box → match → **liquid-glass gate card**: real rank *bucket*
   ("✓ We found you. You're one of the 15…") plus a **decorative** frosted score glyph —
   the real score is *not* in the public payload (§3), so the frosting hides a placeholder,
   not a leakable value. Loss aversion is the conversion mechanic. Unlock CTA → pricing.
6. **The offer** — two plan cards + value anchor + honestly-labeled roadmap benefits +
   the **website-build FCFS cross-sell card** → Build-with-Trinade page.

GSAP pinned-scroll choreography throughout; acts sit on their assigned gradient triads.

## 5 · Dashboards — deeper visualization vocabulary (all ECharts, restyled to tokens-v2)

**Your Clinic:** visibility-score hero (grain-gradient card, Doto numerals, ruler gauge) ·
rank bump chart across query intents · you-vs-market dumbbell/slope panel · 5-check scorecard
as pill rows with status chips · SERP-proof screenshot gallery · patient-voice panel
(sentiment strip, pain-point chips, referral rate) · prescriptive "what to fix first" list.

**The Market:** opportunity quadrant map (demand × visibility scatter — the money chart) ·
beeswarm score distribution · owned-vs-borrowed butterfly · intent × category heatmap ·
review-landscape scatter (rating × volume, bubble = demand) · dot-matrix waffle for
share-of-search · ranked table with inline spark-bars.

## 6 · Build with Trinade (new page)

Form (clinic, contact, current site, goals) + honest FCFS exclusivity copy + 1-1 / in-person
consultation booking. Static-safe submission: prefilled **WhatsApp deep-link** primary +
copy-to-clipboard fallback (no form backend without a server).

## 7 · Constraints & non-goals

- **No paid APIs, no API keys, no server** (foundational). Everything offline/self-contained;
  fonts + libs vendored. Secrets rule per CLAUDE.md (Razorpay *links* are public, not secrets).
- `modules/` + 135 tests untouched; only `web/build_web.py` gains logic (TDD'd).
- Playwright screenshot QA after every phase.
- **Non-goals:** real auth/accounts, payment webhooks, server-side anything, CMS,
  fold-review-NLP-into-score (separate candidate), mobile app.

## 8 · Success criteria

1. Brand guide v2 exists as tokens + HTML page + booklet + DESIGN.md, and the HTML page is
   itself proof of the system.
2. Public dist: view-source contains zero real clinic names/scores; self-lookup works; both
   Razorpay links (or fallback) reachable; the story reads as a sale, not a demo.
3. Private dist: all pages on the new system; every chart in §5 present with real data.
4. `pytest -q` green (135 + new build tests). Reduced-motion honored. Offline single-file
   dists still open with no network.
5. The taste bar: passes taste-skill pre-flight (no templated hero/feature-grid defaults);
   inspiration details (grain gradients, dot numerals, ruler ticks, glass pills, lime chips)
   present and precise.

**Build order:** A (foundation) → B (home) → C (Your Clinic) → D (Market) → E (Build page).
