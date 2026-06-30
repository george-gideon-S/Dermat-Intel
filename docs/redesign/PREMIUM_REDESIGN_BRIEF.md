# Premium Redesign Brief — Derma Intel (Phase 11)

**Date:** 2026-06-30 · **Status:** brief (to be brainstormed into a spec next session)
Companion: [CLAUDE.md](../../CLAUDE.md) · [ARCHITECTURE.md](../../ARCHITECTURE.md) · [DESIGN.md](../../DESIGN.md) ·
current UI audit [docs/redesign/REDESIGN.md](REDESIGN.md)

## Why this phase
Derma Intel is being **sold to the dermatology clinics of Guntur** as a "here's where you stand vs. the
market" report — and as a wedge to **also build them a website**. The dashboard must therefore look and
feel like an **expensive, studio-quality product**: premium motion, premium icons, premium UI, premium
UX. Current UI ("Quiet Precision") is clean but restrained; the next level is *intentional, cinematic,
unmistakably-not-AI* craft that justifies a paid engagement.

## Deliverables
1. **Brand Identity Design Guide** (new doc, e.g. `docs/redesign/BRAND_GUIDE.md` + image boards) covering:
   **Color palette** · **Typography** · **Logo / mark** · **Iconography** · **Motion principles** ·
   **Components** · **Website system** (layout grid, sections) · **Don'ts**. Craft with `brandkit`
   (image boards), `/impeccable brand`, and `soft-skill` / `taste-skill` standards.
2. **Redesigned premium dashboard** — rebuild the `web/` front-end to the new brand: studio-quality UI,
   **premium motion (GSAP)**, premium iconography, refined UX. Fold in the **deferred web-visibility
   feature** (surface OWNED vs BORROWED + the 15 zero-web-presence clinics — see below).
3. **(Upsell, optional/next) per-clinic website/report template** — a premium one-pager a clinic could
   adopt, generated from the same data. This is the commercial hook; scope it after the dashboard.

## Hard constraints (carry over — do not break)
- **100% free, no API keys, no paid services.** Vendor everything **offline** (GSAP, icons, fonts) into
  the single self-contained `web/dist/derma_intel.html` — **no CDN, no server** (works on `file://`).
- **Never disable TLS.** On this TLS-intercepted machine, `git clone` needs
  `git -c http.sslBackend=schannel ...` (Windows store); Node downloads use `NODE_EXTRA_CA_CERTS`
  (`%USERPROFILE%\node_ca_bundle.pem`). Never `http.sslVerify=false` / `NODE_TLS_REJECT_UNAUTHORIZED=0`.
- **Don't touch the data layer's correctness.** The Python pipeline + opportunity score + the screenshot
  web dataset are done and tested (**121 pytest green**). The redesign is presentation-only: it changes
  `web/template.html`, `web/styles.css`, `web/app.js`, `web/vendor/`, and the `build_web.py` *payload
  shape* — not `modules/`. Keep pytest green; QA the UI with Playwright screenshots.
- Platform **Python 3.10 / Windows**; the build stays `python derma_web.py` (build + open, no server).

## What to surface that the data already supports (currently hidden in the UI)
The 40% web term is **live** but the front-end doesn't yet *tell the story*. The payload
(`build_web._clinic`) does **not** yet carry the web signal. Add per-clinic
`web = {owned, borrowed, appearances, has_own_site, invisibility, platforms[]}` (tiny addition to
`web_screens.aggregate_web_by_clinic` to also return the borrowed platforms per clinic) and render:
- a **"Web visibility"** block in the clinic detail (clinic-facing copy, no "owned/borrowed" jargon):
  own-site ranks → *"Ranks its own site in N of 78 Google searches"*; aggregators-only → *"Found only
  via Practo, JustDial — its own site never ranks"*; Maps-pack-only / absent → *"Invisible in Google
  web search."*
- a hero KPI substantiating "invisible online": **15 of 34 clinics have zero web presence**.

## The installed skills (global, in `~/.claude/skills/`) and how to use them
Invoke as slash commands / via the Skill tool. **Process skills first, then implementation.**

| Skill (slash) | Use for |
|---|---|
| `/impeccable <sub>` | The design driver. Subcommands: `shape` `craft` `brand` `audit` `critique` `polish` `animate` `bolder` `quieter` `colorize` `delight` `layout` `typeset` `adapt` `clarify` `distill` `harden` `onboard` `optimize` `init` `document` `extract` `live` (+ `pin` to make `/audit` etc.). Run `/impeccable init` once. Authoritative install for full hooks/CLI: `npx impeccable install`. |
| `/taste-skill` | Anti-slop frontend; audit-first redesign, infers design direction. |
| `/redesign-skill` | Upgrade existing UI to premium without breaking it (audit → high-end standards). |
| `/soft-skill` | "Design like a high-end agency" — exact fonts/spacing/shadows/cards/animations that read expensive; blocks cheap defaults. |
| `/brandkit` | **Brand-identity image boards** — logo systems, identity decks, palette/type boards (image generation). |
| `/imagegen-frontend-web`, `/imagegen-frontend-mobile` | Premium per-section design *reference images* (one image per section) to implement against. |
| `/hallmark` | Anti-AI-slop build/audit/redesign; `hallmark study <url|screenshot>` to extract design DNA. |
| `/gsap-core` `/gsap-timeline` `/gsap-scrolltrigger` `/gsap-plugins` `/gsap-react` `/gsap-utils` `/gsap-performance` `/gsap-frameworks` | **Premium motion** — GSAP API, timelines, scroll-driven/pinned animation, plugins, perf. Our app is vanilla JS, so use `gsap-core`/`timeline`/`scrolltrigger`/`plugins`/`performance`. |
| `/minimalist-skill`, `/brutalist-skill`, `/stitch-skill`, `/image-to-code-skill`, `/output-skill` | Style variants / helpers (optional). |

(Sources kept in `~/.claude/.skill-sources/`; re-install/update via `npx skills add <repo>` or
`/plugin marketplace add greensock/gsap-skills`.)

## Suggested sequence (brainstorm each before building)
1. `/impeccable init` + `hallmark study` a couple of reference SaaS/medical-premium sites → design DNA.
2. **Brand guide** with `brandkit` + `/impeccable brand` → palette, type, logo, icon, motion, don'ts.
3. Design system in `web/styles.css` (tokens) → component-by-component redesign with `soft-skill`/`taste-skill`.
4. **Motion** with GSAP (vendored offline) via `gsap-*` — orchestrated load, scroll reveals, chart entrances, micro-interactions; respect `prefers-reduced-motion`.
5. Wire the web-visibility story into the payload + UI. Playwright screenshot QA each step. Keep pytest green. Commit frequently.
