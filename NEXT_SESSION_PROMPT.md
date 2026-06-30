# NEXT SESSION PROMPT — Derma Intel, Phase 11: Premium Redesign

> Paste everything below the line into a fresh Claude Code session opened in
> `E:\TRINADE\Dermat Analytics and Websites`. It is self-contained; it also points you to the
> in-repo docs to read first.

---

You are continuing work on **Derma Intel** (project root: `E:\TRINADE\Dermat Analytics and Websites`,
git branch `master`, local only).

## 0) Read these first (in order), then confirm the hard rules
`CLAUDE.md` → `ARCHITECTURE.md` → `DESIGN.md` → `SESSION_LOG.md` → `docs/redesign/PREMIUM_REDESIGN_BRIEF.md`
(this phase's brief) → `docs/redesign/REDESIGN.md` (the earlier UI audit).

**Hard rules (non-negotiable):**
- **100% free, no API keys, no paid services — ever.** Free/local tools only.
- **Never disable TLS verification.** This machine has corporate TLS interception: `git clone` must use
  `git -c http.sslBackend=schannel clone …` (Windows cert store); Node/npm downloads rely on
  `NODE_EXTRA_CA_CERTS=%USERPROFILE%\node_ca_bundle.pem` (already set). Never `http.sslVerify=false` or
  `NODE_TLS_REJECT_UNAUTHORIZED=0`.
- **Python 3.10 / Windows.** Don't re-attempt live Google/Bing/DDG web-search scraping (confirmed blocked).
- **Keep `pytest` green (currently 121).** Logic is TDD'd. Commit frequently to local `master` with the
  trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## 1) What Derma Intel is
A **100% free, no-API-key market-intelligence platform** that finds the dermatology clinics in **Guntur,
Andhra Pradesh** with the biggest gap between their **local demand** and their **online presence** — the
best prospects for digital-marketing help. It is being **sold to the clinics themselves** ("here's where
you stand vs. the Guntur market and what to fix"), and as a wedge to **also build them a website**. So the
framing is opportunity/diagnostic (never accusatory), and the product must look **premium and expensive**.

## 2) How it works internally (data → score → UI)
One pure-Python **data layer** in `modules/`, two thin **front-ends** over the same JSON/Excel.

- **Queries** (free, manual): the app prints a copy-paste prompt; the user pastes ~80 search queries back;
  `query_generator` parses them and derives category / intent / strength. → `.cache/query_rows.json` (80).
- **Google Maps** (free Playwright scrape, headless, worker-thread for Streamlit's asyncio safety):
  `maps_collector` → ≈750 appearance rows → `vulnerability.aggregate_clinics` → **34 unique clinics**.
- **Reviews + NLP** (free, VADER): `reviews_collector` + `reviews_nlp` → per-clinic sentiment, pains,
  word-of-mouth/referral rate → "Patient voice" panel (display only, not yet scored).
- **Google web (the 40% term)** — live scraping is blocked, so the user saved **78 full-page SERP
  screenshots**; `screenshot_slicer` Pillow-tiles them (full pages downscale to illegible in vision),
  Claude-vision extracts **78 queries / ~1122 result blocks** → `.cache/web_screens.json`; `web_screens`
  maps blocks to clinics and computes per-clinic **OWNED** (own-site organic / paid ad) vs **BORROWED**
  (aggregator/social-only) visibility (Places-pack excluded — it's Maps re-surfaced); `unify_results`
  merges Maps ‖ web → `unified_results.xlsx`.
- **Opportunity score** (`vulnerability.py`): **0–100 = 0.6 × Maps + 0.4 × Web**.
  Maps = GAP (presence weakness, 58) + REACH (value/demand, 42); Web = invisibility (presence-weighted
  owned/borrowed). Bands: Critical 80+, High 60–79, Medium 40–59, Low 0–39 (calm sand→clay, never red).
- **Front-ends:** **Streamlit** (`app.py`, ops console) and the **PRIMARY premium web app** (`web/`):
  `build_web.py` reuses the modules → one JSON `payload` → inlines CSS + base64 Geist fonts + ECharts +
  data + `app.js` into a single offline `web/dist/derma_intel.html` (no server; `python derma_web.py` =
  build + open). **This `web/` app is what you are redesigning.**

Run: `python derma_web.py` (build+open dashboard) · `python -m pytest -q` (121) ·
`python run_pipeline.py` (Maps scrape) · `python modules/web_screens.py` / `modules/unify_results.py`
(rebuild the web dataset).

## 3) What's done so far (Phases 0–10)
Free/no-keys pivot → core pipeline + scoring → Streamlit app → live Maps scraping (TLS cert-bundle +
worker-thread fixes) → premium web UI ("Quiet Precision") → scoring recalibration → opportunity model
(GAP+REACH, 60/40 blend) → reviews-NLP + headful web collector → 80-query expansion → docs → **Phase 10:
the screenshot→google-search dataset and the 40% web term went LIVE** (78 queries/~1122 blocks; **15 of
34 clinics have zero web presence**; the blend moved 31/34 clinics ≥10 pts; dashboard `web_available=True`).
**Current state: 80 queries · 34 clinics scored on the full 60/40 blend · 121 pytest green · dashboard
built.** Full history in `SESSION_LOG.md`.

## 4) YOUR TASK — Phase 11: premium redesign (see `docs/redesign/PREMIUM_REDESIGN_BRIEF.md`)
Make Derma Intel look and feel like an **expensive, studio-quality product** — premium motion, premium
icons, premium UI, premium UX — good enough to sell to clinics and to upsell website builds. Deliverables:
1. **Brand Identity Design Guide** (`docs/redesign/BRAND_GUIDE.md` + image boards): Color palette,
   Typography, Logo/mark, Iconography, Motion principles, Components, Website system, **Don'ts**.
2. **Redesigned premium dashboard** (`web/`): studio-quality UI, **GSAP motion (vendored offline)**,
   premium icons, refined UX. Fold in the **deferred web-visibility feature** — surface OWNED vs BORROWED
   and the 15 zero-web-presence clinics (the payload `build_web._clinic` doesn't carry the web signal yet;
   add it + a small `platforms` return in `web_screens.aggregate_web_by_clinic`). Details in the brief.
3. **(Upsell, next) per-clinic premium website/report template** from the same data.

**Presentation-only:** change `web/template.html`, `web/styles.css`, `web/app.js`, `web/vendor/`, and the
`build_web.py` payload shape — **not** `modules/` correctness. Stay **self-contained/offline** (vendor
GSAP + icons + fonts; no CDN, no server). Keep `pytest` green; QA with Playwright screenshots.

## 5) Installed design skills (global `~/.claude/skills/`) — your toolkit + slash commands
- **`/impeccable <sub>`** — design driver. Subs: `init shape craft brand audit critique polish animate
  bolder quieter colorize delight layout typeset adapt clarify distill harden onboard optimize document
  extract live` (+ `pin` to alias e.g. `/audit`). Run `/impeccable init` once. For full hooks/CLI:
  `npx impeccable install`.
- **`/taste-skill`** (anti-slop frontend, audit-first redesign) · **`/redesign-skill`** (upgrade existing
  UI to premium) · **`/soft-skill`** (design like a high-end agency; expensive fonts/spacing/shadows).
- **`/brandkit`** (brand-identity image boards: logo, palette, type) · **`/imagegen-frontend-web`** /
  **`/imagegen-frontend-mobile`** (premium per-section reference images).
- **`/hallmark`** (anti-AI-slop build/audit/redesign; `study <url|screenshot>` extracts design DNA).
- **GSAP motion:** **`/gsap-core` `/gsap-timeline` `/gsap-scrolltrigger` `/gsap-plugins`
  `/gsap-performance` `/gsap-utils` `/gsap-react` `/gsap-frameworks`** (our app is vanilla JS → use core /
  timeline / scrolltrigger / plugins / performance).
- Variants/helpers: `/minimalist-skill` `/brutalist-skill` `/stitch-skill` `/image-to-code-skill`
  `/output-skill`.

## 6) Process
Use the **brainstorming skill BEFORE building** (this is creative UI work). Suggested order: `/impeccable
init` + `hallmark study` references → **Brand Guide** (`brandkit` + `/impeccable brand`) → design-system
tokens in `styles.css` → component-by-component redesign (`soft-skill`/`taste-skill`) → **GSAP motion**
(vendored, `prefers-reduced-motion`-safe) → wire the web-visibility story → Playwright screenshot QA →
commit frequently. Get design approval before implementing.
