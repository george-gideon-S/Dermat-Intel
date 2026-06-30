# Derma Intel — Scroll Experience (a Trinade product) · Design Spec

**Date:** 2026-06-30 · **Status:** approved design → implementation
**Brand authority:** [docs/redesign/BRAND_GUIDE.md](../../redesign/BRAND_GUIDE.md) + [tokens.css](../../redesign/tokens.css) ("Warm Intelligence").
**Supersedes** the static three-view Home; **keeps** the two analytical tab screens (Your Clinic / All Clinics).

## 1 · Goal
Turn the dashboard into an immersive, **scroll-driven story** that feels **captivating · analytical · fluid · premium · clearly structured**, scaled for a **real laptop** (not "oversized at 125%"). The story reveals product → insight → value, folds a **₹1500 paywall** in as its climax, and lands on the two polished, cursor-alive tab screens.

## 2 · Hard constraints (carry over — do not break)
- **100% free · no API keys · no paid services · offline-capable.** GSAP is vendored offline (download via `verify=` the Windows cert bundle, inline through `build_web.py` — same path as Bricolage). No CDN, no runtime server calls.
- **No `modules/` changes.** The story reads the existing `window.__DATA__`. Keep **pytest green (137)**.
- **Never disable TLS.** `git -c http.sslBackend=schannel …`; Node via `NODE_EXTRA_CA_CERTS`.
- **No real payment processing.** The ₹1500 gate is a *designed simulated* unlock (localStorage). Real payment happens via Trinade outside the app.

## 3 · States & shell
Retire the 236px sidebar. New shell = a slim **top bar** (`Trinade · Derma Intel` wordmark · thin scroll-progress rail · a "skip" affordance for returning users). Three states:
- `story` — the scroll narrative (free).
- `gate` — the paywall (Act 6), reached at the end of the story.
- `app` — the two tabs, behind a **top pill nav** (Story · Your Clinic · All Clinics).

`localStorage.derma_unlocked` persists the unlock; an already-unlocked visitor may jump straight to `app` (and replay the story via the nav). No-JS / reduced-motion → the whole thing degrades to a readable stacked page.

## 4 · Narrative spine (7 acts)
Each act is a `100svh` section; motion is **scroll-scrubbed**, transform/opacity only.

1. **Hook** — `Trinade · Derma Intel`. A search field materialises; the query *"best dermatologist in Guntur"* types itself (SplitText). Premise: *every day, patients in Guntur search.*
2. **The Search Tunnel** *(insight)* — pinned + scrubbed. Camera flies forward through receding **search-result frames** built from the brand grid (CSS `perspective` + `translateZ`). Walls carry real clinic fragments from the payload — most **dark/empty** (the 15 invisible), a few **rainbow-lit** (the visible). A `34 → 15 invisible` counter ticks with progress.
3. **The Proof** *(proof)* — emerge onto the real Google SERP (bundled screenshot); a highlight sweep: *"This is the page patients get. Is your clinic on it?"*
4. **The Market** *(landscape)* — frames reassemble into the **visibility league** (bars draw in on scrub) and the **rainbow categories** bloom.
5. **The turn to "you"** — *"But where do YOU stand?"* Focus narrows to one clinic slot — blurred, **locked**.
6. **The Gate** *(climax)* — *"See your clinic's report + the full Guntur market — ₹1500."* Premium simulated checkout ("secured by Trinade") → success beat (locked slot fills with rainbow + check) → `localStorage.derma_unlocked=1` → nav + tabs reveal. Small "I've already paid" restore.
7. **Post-unlock** — pill nav appears; enter Your Clinic / All Clinics.

## 5 · The Search Tunnel — mechanics
- Container with `perspective: ~1000px`; N nested frame layers each at increasing `translateZ`, scroll maps to a forward `translateZ` sweep so frames grow and pass the camera.
- Frames are brand-grid rectangles; a subset host lightweight clinic chips (name + faded vs rainbow-lit) — **rendered DOM, not the heavy PNGs**, so the tunnel stays light.
- Depth cues: opacity/scale falloff toward the vanishing point; the lit clinics pulse subtly.
- **Reduced-motion / no-JS:** collapses to a static stacked layered composition (3–4 frames, the counter shown as a stat) that still tells the "most are invisible" story.

## 6 · Motion system (GSAP, vendored offline)
- Vendor `gsap.min.js` + `ScrollTrigger.min.js` + `SplitText.min.js` → `web/vendor/`; inline via `build_web.py` `_VENDOR`/script-inline path. (GSAP is free as of 2025; we still self-host — no CDN.)
- **Native scroll + ScrollTrigger scrub** (NOT ScrollSmoother — it hijacks the scrollbar and is the main cause of laptop jank; native is smoother + accessible). Per-act `ScrollTrigger` with `pin` + `scrub` where an act needs to hold.
- Number count-ups via a small `onUpdate` tween. Cursor motion (Act 7 tabs) via `gsap.quickTo` on a background parallax layer (grid + soft rainbow blobs), throttled.
- **`prefers-reduced-motion: reduce`** → ScrollTriggers killed; sections become static; cursor parallax off. This is a first-class path, designed up front.
- Perf: animate only `transform`/`opacity`; promote layers with `will-change`; no layout-affecting props.

## 7 · Responsive / laptop-native
- Root fluid scale: `:root{ font-size: clamp(13px, 0.55vw + 8px, 17px) }`; express type/space/sizing in `rem` + `clamp()` + `svh` so the layout **fits the viewport** instead of overflowing at 125%.
- Replace remaining fixed px (hero, paddings, the old sidebar) with fluid units. Acts use `min-height: 100svh` (no iOS jump).
- Target band **1280–1600 logical px** feels laptop-native; keep mobile functional (acts stack, tunnel → static).

## 8 · Paywall (Act 6) — simulated gate
- A designed checkout scene: amount **₹1500**, Trinade branding, a UPI-style affordance, one clear **Pay ₹1500** action. On click → a ~1.2s simulated "processing" → success animation → set `localStorage.derma_unlocked=1` → reveal nav + tabs.
- **Honest framing:** a line stating this is a demo unlock; real billing handled by Trinade. No card/UPI fields are real; **no credentials collected**.
- Returning unlocked users skip Act 6. A subtle "I've already paid → restore" relocks/unlocks for demoing.

## 9 · Tabs (post-unlock) — polish + cursor motion
- Your Clinic / All Clinics keep their content (report + market + charts already brand-polished) but gain: a **cursor-tied background parallax** layer (brand grid + soft rainbow, `gsap.quickTo`, subtle/controlled), entrance reveals on first view, and the new fluid sizing. Old sidebar → top pill nav + the "you" context chip.

## 10 · Architecture / code structure
Split the growing front-end for isolation (each file one clear purpose; `build_web.py` inlines all):
- `web/template.html` — new shell: top bar, `#story` mount, `#app` mount, reduced-motion-safe markup.
- `web/story.js` — the 7 acts, the Search Tunnel, GSAP timelines, the paywall, state transitions. Reads `window.__DATA__`.
- `web/app.js` — the two tab views + ECharts (existing, lightly adapted to the new shell + cursor layer).
- `web/shell.js` (small) — shared state (`unlocked`, `state`, nav), localStorage, reduced-motion detection.
- `web/styles.css` — extend with the fluid root scale, act layout, tunnel, paywall, top-bar/pill-nav, cursor layer.
- `web/build_web.py` — vendor + inline GSAP; copy the referenced **proof images into `dist/` with deploy-safe relative paths**; emit `dist/index.html`.
- **No `modules/` changes.**

## 11 · Deployment (Vercel-ready) — build, don't deploy
- Build emits a **self-contained static `web/dist/`**: `index.html` (Vercel serves at `/`) with CSS/JS/fonts/ECharts/GSAP inlined, **plus** a `dist/proof/` folder holding only the proof screenshots actually referenced (copied from the gitignored `data/Full Page Screenshots/`), with paths rewritten to deploy-relative (`proof/<file>` — never `../../data`).
- Add a minimal `vercel.json` (or document: framework "Other", output dir `web/dist`, no build command) so `vercel deploy web/dist` / drag-drop just works.
- **I make it deploy-ready; I do not deploy** (Vercel account/auth + outward-facing = user's action). Bitly URL-shortening is the user's post-deploy step. Keep everything path-portable so the same `dist/` works on `file://` and on Vercel.

## 12 · Data flow
Unchanged pipeline. `build_web.build()` → `window.__DATA__` (clinics, market, kpis, categories, generated_at, median_appearances). Story + tunnel + paywall + tabs all read it. Add only **presentation-shaped** payload fields if needed (e.g., a precomputed visible/invisible split for the tunnel) inside `build_web` — never in `modules/`.

## 13 · QA
- `pytest -q` stays green (presentation-only).
- Playwright: scrub the story (screenshot each act), at **1280 / 1366 / 1536**; `prefers-reduced-motion` on/off; the unlock flow (Pay → tabs reachable; reload preserves unlock); the `dist/` opens correctly from `file://` (deploy parity).
- Perf sanity: transform/opacity only; no long tasks on scroll.

## 14 · Non-goals (YAGNI)
- No real payment gateway / backend / auth. No ScrollSmoother. No CMS. No new data collection. No `modules/` refactor. No mobile-first redesign (mobile must *work*, not be the focus).

## 15 · Implementation phases
1. **Fluid foundation** — root scale + responsive rework of existing screens (kills "oversized"); top-bar/pill-nav shell; retire sidebar. Build + screenshot at 1280/1366/1536.
2. **GSAP vendored + scaffolding** — vendor gsap/ScrollTrigger/SplitText; inline in build; reduced-motion plumbing; act-section skeleton.
3. **Acts 1–5** — hook, the Search Tunnel, proof, market build, the turn. Scrub + pins + count-ups.
4. **Act 6 paywall** — simulated checkout + unlock + reveal.
5. **Act 7 + tabs** — pill nav, gating, cursor parallax, entrance reveals.
6. **Vercel-ready build** — `dist/index.html` + bundled `proof/` + `vercel.json`; `file://` + deploy parity check.
7. **QA pass** — pytest, multi-viewport + reduced-motion screenshots, unlock flow; commit.
