# Derma Intel Scroll Experience — Implementation Plan

> **For agentic workers:** implement task-by-task. Steps use checkbox (`- [ ]`) syntax.
> Spec: [docs/superpowers/specs/2026-06-30-derma-intel-scroll-experience-design.md](../specs/2026-06-30-derma-intel-scroll-experience-design.md).
> Brand authority: [docs/redesign/BRAND_GUIDE.md](../../redesign/BRAND_GUIDE.md) + tokens.css.

**Goal:** Replace the static Home with an immersive, scroll-scrubbed story (hook → Search Tunnel → proof → market → the turn → ₹1500 paywall → tabs), laptop-native and Vercel-ready.

**Architecture:** One self-contained offline build. Front-end split: `shell.js` (state/nav/localStorage/reduced-motion), `story.js` (7 acts + tunnel + GSAP + paywall), `app.js` (the two tab views + ECharts). `build_web.py` inlines CSS/JS/fonts/ECharts/**GSAP** and emits a portable `dist/index.html` + bundled `dist/proof/`. No `modules/` changes.

**Tech stack:** Vanilla JS, GSAP + ScrollTrigger + SplitText (vendored offline), ECharts (vendored), Bricolage/Geist/Geist Mono (vendored), Python 3.10 build.

**QA convention:** each task → `python web/build_web.py` + Playwright screenshot (`scratchpad/shoot*.py`) at 1280/1366/1536 and/or behavior check. Final gate: `pytest -q` green (137). Commit after each task.

---

## Task 0: Vendor GSAP offline
**Files:** Create `web/vendor/gsap.min.js`, `web/vendor/ScrollTrigger.min.js`, `web/vendor/SplitText.min.js`; scratchpad downloader.
- [ ] Download the three from jsDelivr (`/npm/gsap@3/dist/...`) via `requests` + `verify=` the Windows cert bundle (mirror `get_bricolage.py`). GSAP is free as of 2025; self-host (no CDN).
- [ ] Verify each file > 10 KB and defines `gsap` / `ScrollTrigger` / `SplitText`.
- [ ] Commit: `chore(web): vendor GSAP + ScrollTrigger + SplitText offline`.

## Task 1: Fluid root scale + retire sidebar (kills "oversized")
**Files:** Modify `web/styles.css`.
- [ ] Add `:root{ font-size: clamp(13px, 0.55vw + 8px, 17px) }`; convert hero/paddings/cards/fact-numbers and the old `.main`/`.side` from fixed px → `rem`/`clamp()`; acts use `min-height:100svh`.
- [ ] Remove the `.layout`/`.side` sidebar rules; add `.topbar` (wordmark + progress rail) and `.pillnav` styles.
- [ ] **Verify:** build + screenshot at 1280/1366/1536 — content fits the viewport, no oversized feel.
- [ ] Commit: `feat(web): fluid laptop-native root scale; retire sidebar shell`.

## Task 2: Shell + state module
**Files:** Create `web/shell.js`; modify `web/template.html`, `web/build_web.py` (inline shell.js).
- [ ] `shell.js`: export state (`{state:'story'|'app', view, unlocked}`), `localStorage` get/set for `derma_unlocked`, `prefersReducedMotion()`, nav render + wiring, `enterApp()/showStory()`.
- [ ] `template.html`: top bar + `#story` mount + `#app` mount + reduced-motion-safe base.
- [ ] **Verify:** build; shell renders; nav toggles story/app; unlock flag persists across reload.
- [ ] Commit: `feat(web): experience shell + persistent state`.

## Task 3: Build inlines GSAP + emits Vercel-ready dist
**Files:** Modify `web/build_web.py`.
- [ ] Inline `gsap.min.js`, `ScrollTrigger.min.js`, `SplitText.min.js` (script tags, before story.js).
- [ ] Copy proof screenshots actually referenced (home sample + each clinic's `proof.screenshot`) from `data/Full Page Screenshots/` into `dist/proof/`; rewrite the `SERP()` path base to `proof/` (deploy-safe, no `../../data`).
- [ ] Emit `dist/index.html` (in addition to/instead of `derma_intel.html`).
- [ ] **Verify:** build; open `dist/index.html` from `file://` — GSAP present (`window.gsap`), proof images load from `proof/`.
- [ ] Commit: `feat(build): inline GSAP; emit portable dist/index.html + bundled proof/`.

## Task 4: Act sections skeleton + reduced-motion fallback
**Files:** Create `web/story.js`; modify `web/build_web.py` (inline story.js), `web/styles.css` (act layout).
- [ ] `story.js`: render 7 `<section class="act" data-act="N">` from `window.__DATA__`; register `gsap.registerPlugin(ScrollTrigger, SplitText)`; if `prefersReducedMotion()` → skip all ScrollTriggers (sections read as a static stacked narrative).
- [ ] **Verify:** build; reduced-motion → clean stacked page; motion → empty acts scroll. No console errors.
- [ ] Commit: `feat(web): story act skeleton + reduced-motion path`.

## Task 5: Act 1 (Hook) + Act 3 (Proof)
**Files:** Modify `web/story.js`, `web/styles.css`.
- [ ] Act 1: centered search field; `SplitText` types "best dermatologist in Guntur"; subtle caret; scroll cue.
- [ ] Act 3: pinned SERP screenshot (bundled), a scrubbed highlight sweep + "Is your clinic on it?" line.
- [ ] **Verify:** build + screenshot at scroll y for each act (1366).
- [ ] Commit: `feat(web): story Act 1 hook + Act 3 proof`.

## Task 6: Act 2 — the Search Tunnel
**Files:** Modify `web/story.js`, `web/styles.css`.
- [ ] `.tunnel` with `perspective:1000px`; N `.ring` frames (brand grid) at increasing `translateZ`; a subset host clinic chips from data — most dark, ~visible-count rainbow-lit.
- [ ] Pin the act; `scrub` maps scroll → forward `translateZ` sweep (transform/opacity only); depth opacity/scale falloff.
- [ ] `34 → 15 invisible` counter tween on scroll progress.
- [ ] Reduced-motion → 3–4 static layered frames + the counter as a stat.
- [ ] **Verify:** screenshot mid-scrub at 1280/1366; reduced-motion static.
- [ ] Commit: `feat(web): Act 2 Search Tunnel (scroll-scrubbed, data-driven)`.

## Task 7: Act 4 (Market build) + Act 5 (The turn)
**Files:** Modify `web/story.js`, `web/styles.css`.
- [ ] Act 4: on scrub, a compact visibility-league draws in (CSS bars or a lightweight ECharts with `animationDuration` tied to enter) + rainbow category bloom.
- [ ] Act 5: focus narrows to one blurred, locked clinic slot; "But where do YOU stand?".
- [ ] **Verify:** screenshots; reduced-motion shows final states.
- [ ] Commit: `feat(web): Act 4 market build + Act 5 the turn`.

## Task 8: Act 6 — simulated ₹1500 paywall
**Files:** Modify `web/story.js`, `web/shell.js`, `web/styles.css`.
- [ ] Paywall scene: "See your clinic's report + the full Guntur market — ₹1500", Trinade branding, one `Pay ₹1500` action; honest demo-unlock note; **no real fields/credentials**.
- [ ] On Pay → ~1.2s simulated processing → success beat (locked slot fills rainbow + check) → `setUnlocked(true)` → reveal pill nav + enable tabs. "I've already paid" restore.
- [ ] **Verify:** click Pay → tabs reachable; reload keeps unlock; relock restores gate.
- [ ] Commit: `feat(web): Act 6 simulated ₹1500 paywall + unlock`.

## Task 9: Act 7 + tab gating + cursor parallax
**Files:** Modify `web/shell.js`, `web/app.js`, `web/story.js`, `web/styles.css`.
- [ ] Pill nav (Story · Your Clinic · All Clinics); tabs gated on `unlocked` (else bounce to gate).
- [ ] Add a fixed `.cursor-bg` layer (brand grid + soft rainbow blobs) on tab views; `gsap.quickTo` translate with pointer (throttled, subtle); off under reduced-motion.
- [ ] Entrance reveals on first tab view (staggered, transform/opacity).
- [ ] **Verify:** screenshot tabs; confirm cursor layer present + no jank; reduced-motion disables it.
- [ ] Commit: `feat(web): pill nav, tab gating, cursor-tied parallax`.

## Task 10: Vercel-ready + full QA
**Files:** Create `web/vercel.json` (or `vercel.json` at root pointing at `web/dist`); modify `README`/docs note.
- [ ] `vercel.json`: static, no build, output `web/dist`; SPA-safe (serve index.html). Confirm `dist/` is fully portable (no absolute/`../../` paths).
- [ ] **Verify:** `pytest -q` green (137); Playwright run of acts at 1280/1366/1536 + reduced-motion on/off + unlock flow; `file://` parity.
- [ ] Commit: `chore(web): Vercel-ready static dist + deploy notes`.

---

## Self-review
- **Spec coverage:** shell/states (T1–2), tunnel (T6), GSAP/motion + reduced-motion (T0,3,4,+each), responsive (T1), paywall (T8), tabs+cursor (T9), deployment (T3,T10), data flow (reuse `__DATA__`, no modules), QA (T10). ✓
- **No placeholders:** every task names exact files + a concrete verify + commit. ✓
- **Naming consistency:** `setUnlocked`/`derma_unlocked`/`prefersReducedMotion`/`enterApp` used consistently across shell/story/app. ✓
