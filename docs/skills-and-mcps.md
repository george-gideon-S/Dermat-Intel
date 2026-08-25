# Skills & MCPs — what is installed, and when to reach for it

Generated from the SKILL.md files themselves and cross-checked against disk, so every
command below is one the skill actually documents. Regenerate with `tools/skills_doc.py`
after installing or updating a skill.

**38 skills** are available: 13 project-local (`.claude/skills/`, versioned with this repo) and 25 global (`~/.claude/skills/`, shared across all projects).

Invoke any of them with the `Skill` tool, or type `/<name>` in a prompt.

> **Project skills need a session restart.** Claude Code discovers `.claude/skills/` at
> session start, so the 13 project skills installed here become `/`-invocable in the NEXT
> session, not the one that installed them.

---

## Design direction & page craft

### `/hallmark`  ·  _global_

An anti-AI-slop page design system (v1.1.0) that forces structural variety: it picks one of 21 named macrostructures, one of 4 genres, one of 20 named themes (or a custom OKLCH palette), nav/footer archetypes from a 50-item component cookbook, then runs the emitted code through a 58-gate slop test and stamps the choices into a CSS comment plus .hallmark/log.json so the next run is forced to pick differently.

**Use when** — Building a NEW page or app from scratch (the default verb); auditing an existing page against a ranked anti-pattern punch list; redesigning the visual layer of an existing page inside its current implementation boundaries; or extracting design DNA from a screenshot you were given or a live URL. It also has an explicit Component-scope branch that auto-fires when the brief names a single UI element (button, card, modal, tab strip, etc.) or targets a single component file, which skips macrostructure/nav/footer/hero picks and instead demands all 8 interactive states plus a throwaway <Component>.preview.html demo wrapper. Notable hard rules that hold across every verb: no fabricated metrics/testimonials/logos, all colors and font-families must reference named tokens (no inline OKLCH/hex mid-render), no re-drawn fake browser/phone/IDE chrome, mandatory mobile verification at 320/375/414/768px, no italic headers, and section eyebrows/numbered tags default OFF. It always asks 3 questions first (Audience, Use case, Tone) unless you say "go ahead", and always emits tokens.css.

**Not for** — You need a data-dense internal tool laid out for information density rather than page rhythm — its 21 macrostructures are page shapes (only "Workbench" leans tool-like), and it has no data-table, form-wizard, or chart guidance. Also skip it if you don't want the ceremony: it insists on asking the 3-question gate, printing a rotation/diversification block, printing a preview block, and stamping the codebase with .hallmark/log.json before it writes code.

| Command | What it does | When |
|---|---|---|
| `(default — no verb)` | Full 8-step Design flow: pre-flight scan of the existing codebase, 3-question design-context gate, genre pick, macrostructure pick, project-memory/diversification check, theme route, ruleset load, hero-enrichment decision, preview block, build, 58-gate slop test. | The user asks to design or build something new. Also the fallback for anything that doesn't clearly map to audit/redesign/study. |
| `hallmark audit <target>` | Reads the target, scores it against the anti-pattern list, returns a ranked punch list. Explicitly does NOT edit anything. | You want a diagnosis of an existing page without touching the code. Loads references/verbs/audit.md. |
| `hallmark redesign <target> [--mood <name>]` | Keeps the target's content and intent, replaces the visual/interaction layer: new section rhythm, new heading placement, new component voice. Preserves routes, component ownership, copy intent, brand, and IA unless the user explicitly approves a full rebuild. | An existing implementation needs a new look but must keep working. Loads references/verbs/redesign.md. Has a multi-page flow that can produce a project-wide design.md. |
| `hallmark study <screenshot \| URL>` | Extracts the DNA (macrostructure, archetypes, type-pairing, colour anchor) from a design you admire and emits a diagnosis report, then optionally rebuilds YOUR content with that DNA or locks it into a portable design.md. Never copies pixels. URL mode reads HTML/CSS via WebFetch and can name exact fonts and colour values but cannot judge rhythm; image mode judges rhythm but can only guess fonts by role. Refuses template-marketplace URLs and dribbble/behance galleries. | You pasted a screenshot or a URL of a design you want to learn from. Mode is auto-detected by the http:// or https:// prefix. Loads references/study.md first. |
| `"lock the system" / "give me a design.md" / "lock the DNA"` | Opt-in trigger phrases that extract the current build's (or the studied source's) tokens and voice into a portable design.md, which then becomes the locked design system that all subsequent Hallmark runs defer to. | After you've iterated and settled on a look and want it reusable across pages. Never fires automatically on a vanilla build; page-scope only. URL-mode DNA locking additionally requires an attestation that the source is yours or a public reference for your own brand. |

**On this project** — High for the clinic-facing report/landing surface, medium for the dashboard. Three concrete fits: (1) `hallmark study` in image mode is the exact tool for the PNGs already sitting in design/Design Inspiration/ ("Look and feel - ALL PAGES.png", "The Market Page - Map+List view tab.png", "Your Clinic Page - SUBJECT.png") — it turns them into a named macrostructure + type roles + OKLCH anchors and can lock the result into a design.md that governs every later page, which is what the repo history (the V5b/bento/card work that just got torn out) has been improvising by hand. (2) Its output is vanilla-friendly — OKLCH custom properties, a mandatory tokens.css, no framework assumption — so it drops onto the vanilla HTML/CSS/JS internal review page without a build step. (3) Its Component-scope branch with the mandatory 8-state checklist is the right mode for the individual report cards rather than the page flow. Caveats: the git history shows a v3 redesign brief and a prior premium redesign that already fixed a brand direction (Luminous Precision), and Hallmark's diversification rule actively fights a locked look unless you first give it a design.md (its pre-flight reads design.md first and inverts diversification so pages SHARE the system) or route through studied-DNA, which suspends rotation. Its 58 gates and "no invented metrics" rule are directly useful for a market-intelligence report where every number must trace to scraped data.

### `/taste-skill`  ·  _global_

_(its SKILL.md declares `name: design-taste-frontend` — you type the folder name.)_

A single 1207-line anti-slop file for landing pages, portfolios, and redesigns that starts by forcing a one-line "Design Read" of the brief, sets three numeric dials (DESIGN_VARIANCE 8 / MOTION_INTENSITY 6 / VISUAL_DENSITY 4 by default), maps the brief to either a real official design system or an honestly-labeled aesthetic, and ends with a ~60-box mandatory Pre-Flight Check.

**Use when** — Marketing landing pages, portfolios, and site redesigns — and specifically when you want a very long, very concrete list of named AI tells to avoid. Its strongest unique content: Section 2's honest brief-to-design-system map (Fluent / Material 3 / Carbon / Polaris / Atlaskit / Primer / GOV.UK / USWDS / Radix Themes / shadcn / Bootstrap, with real install commands in Appendix A and canonical doc links in Appendix B) plus the rule that if the brief matches one of those you install the official package rather than recreating its CSS; Section 9's production-test tells (banned: version labels in the hero, section-number eyebrows like "001 · Capabilities", middle-dot separator spam, decorative status dots, vertical rotated text, div-based fake product previews, locale/weather strips, scroll cues, "Quietly trusted by", photo-credit captions as decoration, version footers on marketing pages); Section 9.G's absolute zero-tolerance em-dash ban; Section 4.7's layout hard rules (hero must fit the viewport, subtext <= 20 words, hero top padding <= pt-24, max 4 text elements in the hero, nav on one line <= 80px, max 1 eyebrow per 3 sections counted mechanically, zigzag alternation cap of 2, split-header ban, bento cell count must equal item count); Section 4.2's premium-consumer palette ban (specific banned hex families for beige/brass/oxblood/espresso); and Section 4.1's serif discipline banning Fraunces and Instrument_Serif as defaults. Section 11 is a full redesign protocol with SEO-migration warnings and a list of things that must never change silently (URL slugs, nav labels, form field names, logo, legal copy).

**Not for** — Section 13 says outright it is NOT for dashboards, dense product UI, admin panels, data tables, multi-step forms/wizards, code editors, native mobile, or realtime collaborative UIs — and instructs you to say so explicitly and point at the right tool instead. Its default architecture (Section 3.A) also hard-assumes React/Next with Server Components, Tailwind v4, and the `motion/react` library, so it fights a vanilla HTML/CSS/JS codebase; the Section 5.A/5.B GSAP skeletons and Section 12 Block Library schema are React-only. Section 12 is also an unfulfilled contract — it defines a blocks/ directory schema but the skill folder currently contains only SKILL.md, so no blocks exist.

| Command | What it does | When |
|---|---|---|
| `Greenfield mode` | No existing site, or a full overhaul is approved. Dial baseline comes from Section 1. | Section 11.A mode detection — this is the first action the skill takes on any brief. |
| `Redesign - Preserve mode` | Modernise without breaking the brand: audit first, extract brand tokens, evolve gradually. Dials = match existing, motion +1. | An existing site with sound IA, content, and SEO. Applies levers 1-4 only (typography, spacing, color recalibration, motion layer) for ~70% of the value at ~40% of the risk. |
| `Redesign - Overhaul mode` | New visual language on top of existing content; treated as greenfield for visuals but content and IA are preserved. Dials = +2 variance, +2 motion. | Visual debt is structural (broken IA, no design system, broken mobile). If the brand itself is changing, it becomes Greenfield instead. |

**On this project** — Split, and the split is important. LOW for the two surfaces you actually have queued: it explicitly excludes dashboards and data tables, and a clinic market-intelligence report is dense data UI, not a landing page. Its React/Next/Tailwind/Motion assumption also clashes with the internal vanilla HTML/CSS/JS review page. MEDIUM-HIGH for one thing you will eventually need — the public marketing/pricing page that sells the report to clinics, where Section 11's redesign protocol and Section 2's system map would genuinely apply. Even outside its scope, two parts are stack-agnostic and worth lifting as a manual checklist: Section 9's named tells and Section 14's Pre-Flight matrix catch specific things this repo is prone to — invented precise numbers (Section 4.9 flags fake-precise figures like 92% or 4.1x unless they come from real data, which is exactly the discipline a scraped-market-intel report needs), section-number eyebrows, decorative status dots, and the div-based fake-screenshot tell. Treat those two sections as a review pass; do not run the skill as a builder for the dashboard.

### `/taste-skill-v1`  ·  _global_

_(its SKILL.md declares `name: design-taste-frontend-v1` — you type the folder name.)_

The original, much shorter (227-line) version of the taste skill, preserved verbatim for backward compatibility: the same three dials, a Framer-Motion-era architecture section, seven bias-correction rules, an AI-tells list, a "Creative Arsenal" pattern vocabulary, a prescriptive "Motion-Engine Bento 2.0" spec, and a 7-box pre-flight check.

**Use when** — Only when you need exact backward compatibility with v1 behavior — its own frontmatter says the current default is design-taste-frontend (v2) and that v2 is a substantial rewrite. The one thing v1 has that v2 dropped is Section 9, the prescriptive "Motion-Engine Bento Paradigm": a hard-coded dashboard aesthetic (#f9fafb page background, pure white #ffffff cards with border-slate-200/50, rounded-[2.5rem] containers, a wide diffusion shadow, p-8/p-10 padding, labels placed outside and below the cards) plus five named card archetypes with specific micro-animation specs (Intelligent List with layoutId auto-sorting, Command Input with a multi-step typewriter, Live Status with overshoot-spring notification badges, Wide Data Stream as a seamless infinite carousel, Contextual UI focus mode). v1 is also stricter in places v2 relaxed: emojis are BANNED outright with no override, Inter is banned outright rather than discouraged-with-override, serif is banned outright on dashboards, and icons must be exactly @phosphor-icons/react or @radix-ui/react-icons.

**Not for** — Any new work. It is superseded by taste-skill and its own description says so. It is also stale in specifics: it names Framer Motion rather than the renamed `motion/react` package, has no redesign protocol, no design-system map, no em-dash rule, no copy self-audit, no hero/eyebrow/zigzag layout discipline, and a 7-item pre-flight check versus v2's ~60. Its Section 9 Bento palette is also hard-coded light-mode and will actively fight a dark UI.

**On this project** — Low. It is a legacy artifact with no dependent project here, and everything useful in it survives in taste-skill except the Bento 2.0 spec. The single narrow exception worth knowing about: if you want a concrete, opinionated starting spec for the clinic dashboard's card grid, Section 9's five card archetypes are the most directly dashboard-shaped content across all five of these skills — the "Wide Data Stream" infinite carousel and "Live Status" breathing indicators map onto competitor-tracking and scrape-freshness tiles. But its palette (#f9fafb page, white cards) is light-mode and contradicts the existing dark review page, its "every card must loop infinitely" rule is the opposite of what a serious analytics product wants, and the whole spec is React/Framer/Tailwind. Read it for the archetype ideas; do not invoke it as the design authority.

### `/impeccable`  ·  _global_

A 26-command production-frontend design system (v3.8.0) that runs a mandatory setup (context script -> PRODUCT.md/DESIGN.md -> read existing project CSS -> load a brand-vs-product register reference) and then routes to a per-command reference file, enforcing contrast, typography, layout, motion, and a two-altitude "category-reflex" anti-slop check.

**Use when** — Essentially any UI work on a real project: building a feature end-to-end (craft), planning UX before code (shape), reviewing (critique/audit), refining (polish/bolder/quieter/distill/harden/onboard), enhancing (animate/colorize/typeset/layout/delight/overdrive), fixing (clarify/adapt/optimize), or iterating live in a browser (live). It is the only one of these five that explicitly claims dashboards, admin, app shells, forms, settings, onboarding, and empty states as in-scope. Its register split matters: marketing/landing/portfolio work loads reference/brand.md (design IS the product), while dashboard/admin/tool work loads reference/product.md (design SERVES the product). Notable hard bans: side-stripe borders (border-left as a colored accent), gradient text via background-clip, decorative glassmorphism, the hero-metric template, identical card grids, tiny uppercase tracked eyebrows on every section, numbered 01/02/03 section markers as scaffolding, and text that overflows its container. It also calls the cream/sand/beige body background (OKLCH L 0.84-0.97, C < 0.06, hue 40-100) the saturated AI default of 2026 and bans token names like --paper, --cream, --sand, --linen.

**Not for** — Backend-only or non-UI tasks (stated explicitly in the description). Also be aware the setup is genuinely blocking, not advisory — without a PRODUCT.md it forces you into init before it will do the thing you asked for, and every sub-command requires reading its reference file plus at least one real project file before producing output. That makes it the heaviest of these five for a quick one-off tweak.

| Command | What it does | When |
|---|---|---|
| `craft [feature]` | Shape, then build a feature end-to-end. | You want the full plan-then-implement loop. Setup still runs first, then reference/craft.md owns the flow. |
| `shape [feature]` | Plan the UX/UI before writing any code. | The interaction model isn't settled yet. |
| `init` | Set up project context: PRODUCT.md, DESIGN.md, live config, next steps. | Mandatory blocker — if the setup context script reports NO_PRODUCT_MD you must stop and run init before anything else. `teach` is a deprecated alias for this. |
| `document` | Generate DESIGN.md from the existing project code. | Code exists but the visual system was never written down (hasCode true, hasDesign false). |
| `extract [target]` | Pull reusable tokens and components out into a design system. | The same values keep getting re-typed across files. |
| `critique [target]` | UX design review with heuristic scoring; stores a snapshot that polish later reads as its backlog. | You want a scored review. If critique.latest is null the project has never been critiqued and this is the strong default. |
| `audit [target]` | Technical quality checks — accessibility, performance, responsive behavior. | You need the objective pass/fail layer rather than taste. |
| `polish [target]` | Final quality pass before shipping; reads the latest critique snapshot as its worklist. | A critique exists with a low score or open P0/P1 items, or you're about to ship. |
| `bolder [target]` | Amplify safe or bland designs. | The design is competent but forgettable. |
| `quieter [target]` | Tone down aggressive or overstimulating designs. | Too much color, motion, or contrast. |
| `distill [target]` | Strip to essence, remove complexity. | The screen has accumulated cruft. |
| `harden [target]` | Production-ready pass: error states, i18n, edge cases. | The happy path works and nothing else does. |
| `onboard [target]` | Design first-run flows, empty states, activation. | New users hit a blank screen. |
| `animate [target]` | Add purposeful animation and motion. | The UI is static and motion would carry meaning. |
| `colorize [target]` | Add strategic color to a monochromatic UI. | The palette reads flat or all-gray. |
| `typeset [target]` | Improve typographic hierarchy and font choices. | Headings and body don't read as a system. |
| `layout [target]` | Fix spacing, rhythm, and visual hierarchy. | "Fix the spacing" — also the intent-match target for that phrasing. |
| `delight [target]` | Add personality and memorable touches. | Correct but characterless. |
| `overdrive [target]` | Push past conventional limits. | You want an ambitious visual effect that should feel technically extraordinary. |
| `clarify [target]` | Improve UX copy, labels, and error messages. | "Rewrite this error message" — the intent-match target for copy work. |
| `adapt [target]` | Adapt the design for different devices and screen sizes. | Responsive behavior is broken or unconsidered. |
| `optimize [target]` | Diagnose and fix UI performance. | Jank, slow interaction, poor vitals. |
| `live` | Visual variant mode — pick elements in the running browser and generate alternatives. | A dev server is running (context-signals reports devServer.running true). Don't lead with it if no server is up. |
| `pin <command> / unpin <command>` | Creates or removes a standalone /<command> shortcut that invokes /impeccable <command> directly; writes into every harness directory present in the project. | You use one sub-command constantly and want it one keystroke away. Runs scripts/pin.mjs. |
| `hooks <on\|off\|status\|ignore-rule\|ignore-file\|ignore-value\|reset>` | Manages the design-detector hook for the project — auto-runs the detector after direct UI file edits and surfaces findings as system reminders. | You want continuous slop detection rather than on-demand audits. Loads reference/hooks.md. |
| `(no argument)` | Context-aware menu: runs scripts/context-signals.mjs, reasons over the JSON (setup state, latest critique, git-changed files, dev-server status), optionally runs scripts/detect.mjs over changed files, and leads with the 2-3 highest-value next commands before showing the full table. Never auto-runs a command. | You don't know which command you want. |

**On this project** — Highest of the five for this project, and the only one that legitimately covers both surfaces. The premium clinic-facing dashboard and the internal dark review page are both squarely "app UI / dashboard / tool", which is the register (reference/product.md) it handles explicitly and that taste-skill declares out of scope. Its most directly applicable pieces here: the contrast rules (body >= 4.5:1, and the specific warning about muted-gray body text — the exact failure mode of a dark analytics dashboard), the semantic z-index scale requirement, the ban on nested cards (relevant given the repo's card/bento history), the dropdown-clipping note about position: absolute inside overflow: hidden (a real hazard for a map + list view with filter menus), and reveal animations that must enhance an already-visible default rather than gate content visibility — which matters for a report that may be printed or rendered headlessly to PDF. The command set maps cleanly onto the phases you actually have: `document` to capture the visual system from the design/ references and surviving CSS, `craft` for new report sections, `critique` then `polish` on the internal review page, `harden` for the clinic-facing report's error and empty states, and `adapt` for print/mobile. One practical caveat before invoking: SKILL.md hard-codes the project-relative path `node .claude/skills/impeccable/scripts/context.mjs`, but the install is global — the scripts live at C:\Users\SALE PITCHAIAH\.claude\skills\impeccable\scripts\ (context.mjs, context-signals.mjs, detect.mjs, palette.mjs, pin.mjs all confirmed present), so you'll need to substitute the absolute global path or the setup step fails immediately. Second caveat: the cream/beige ban is worth reading against the archived "Warm Intelligence" oat-canvas brand direction in memory — impeccable would reject that palette by name.

### `/redesign-skill`  ·  _global_

_(its SKILL.md declares `name: redesign-existing-projects` — you type the folder name.)_

A stack-agnostic upgrade checklist for existing sites and apps: Scan the codebase, Diagnose against a ~100-item audit organized into eight categories, then Fix in place using the existing stack, ordered by a 7-step priority list that puts font swap first and typography polish last.

**Use when** — You have working code that looks generic and you want targeted, low-risk improvements rather than a rewrite. The audit categories are Typography, Color and Surfaces, Layout, Interactivity and States, Content, Component Patterns, Iconography, Code Quality, and Strategic Omissions (the things AI typically forgets: legal links, back navigation, custom 404, form validation, skip-to-content link, cookie consent). It also carries an "Upgrade Techniques" catalog of higher-effort moves (variable font animation, outlined-to-fill text, text mask reveals, broken grid, parallax card stacks, split-screen scroll, smooth scroll with inertia, staggered entry, spring physics, scroll-driven reveals, true glassmorphism with inner border and inner shadow, spotlight borders, grain overlays, tinted shadows). Its explicit rules are the important part: work with the existing tech stack, never migrate frameworks or styling libraries, do not break functionality, check dependencies before importing, check Tailwind v3 vs v4 before touching config, use vanilla CSS if there is no framework, and keep changes small, targeted, and reviewable.

**Not for** — Greenfield work — it has no brief-inference step, no design direction system, no macrostructure or theme vocabulary, and nothing to say about what a page should BE. It only knows how to improve what already exists. It also has no verbs, no scoring, no gate count, and no output contract, so it will not stop you from shipping; it is a checklist, not an enforcement layer. And it overlaps heavily with impeccable's audit/polish/critique commands, which cover the same ground with more structure.

**On this project** — Medium-high, and specifically for the internal dark review page rather than the greenfield clinic UI. It is the only one of the five with zero framework assumptions — it says outright to use vanilla CSS when there is no framework — which makes it the lowest-friction fit for a vanilla HTML/CSS/JS dashboard. Several of its audit items target that page's exact likely failure modes: pure #000000 backgrounds (replace with #0a0a0a / #121212 / tinted dark), mixing warm and cool grays, generic untinted box-shadows, proportional figures in data-heavy interfaces (use font-variant-numeric: tabular-nums — directly relevant to scraped ranking and review-count columns), "dashboard always has a left sidebar" (suggests top nav or a floating command menu instead), buttons not bottom-aligned across cards of unequal height, feature lists starting at different Y positions in comparison columns, and inconsistent vertical rhythm in side-by-side panels — all of which are real hazards for a competitor-comparison view. Its Content section also matters for a data product: it bans fake round numbers in favor of organic values, which reinforces that every figure in the report should come from the actual scrape. The Fix Priority order (font, then color, then hover/active states, then layout, then components, then loading/empty/error states, then typography polish) is a sane sequence for incrementally lifting the existing page without a teardown — which is notable given the repo just removed its UI layer once. Low relevance for the greenfield clinic-facing dashboard, since it has nothing to say about a design that does not yet exist.

### `/design-dna`  ·  _project_

A three-phase pipeline that turns reference screenshots or URLs into a fully-populated Design DNA JSON across three dimensions — design_system (measurable tokens), design_style (qualitative feel), visual_effects (Canvas/WebGL/shaders/scroll/cursor/glass) — and then generates a design from that JSON, defaulting to a single self-contained HTML file with inline CSS and JS.

**Use when** — Any of: you want to see the full 3-dimension schema; you have images, screenshots, or URLs of designs you admire and want them analyzed into a structured JSON profile; or you have a DNA JSON plus content and want the design built from it. Phase 2 requires every schema field populated with no empty strings, notes the dominant pattern when references conflict, and sets enabled:false for absent effect categories. Phase 3 has a priority order (color and typography first, then spacing/layout, shape/elevation, qualitative style, effects, motion last) and a delivery checklist including WCAG AA contrast, prefers-reduced-motion, requestAnimationFrame over setInterval, and no rendering of effects whose enabled flag is false.

**Not for** — Do not jump to Phase 3 when the user supplies content with no DNA JSON — the skill requires asking whether to analyze a reference first or derive DNA from a description. Phase 3 also forbids recreating, approximating, or substituting assets when the real ones can be fetched from the source URL the user provided.

| Command | What it does | When |
|---|---|---|
| `Phase 1 — Structure` | Read references/schema.md and present the full three-dimension schema with field descriptions, then ask whether to customize or extend any dimension. | The user asks to see the design structure or schema. Selected from context, not typed as a slash sub-command. |
| `Phase 2 — Analyze` | Extract a complete Design DNA JSON from supplied images, screenshots, or URLs — every schema field populated, conflicts noted as dominant pattern plus variants — then ask whether to adjust values before generating. | The user provides reference designs. Combinable as Phase 2 only, or Phase 2 -> 3. |
| `Phase 3 — Generate` | Read references/generation-guide.md, build CSS custom properties from design_system, apply design_style to subjective calls, implement visual_effects at the right technology tier, and output the design with quality checks run. | The user supplies a DNA JSON plus content. If only content arrives with no JSON, ask whether to analyze a reference first or derive DNA from a described style. |

**On this project** — High, and the best-fitting of the five for this project's actual state. The repo already holds exactly the inputs Phase 2 wants — design/Design Inspiration/ screenshots covering "Look and feel - ALL PAGES", "The Market Page - Map+List view tab", "Your Clinic Page - SUBJECT", plus warm-translucent and glucose-dashboard boards — and the project has a named but not yet tokenized brand direction (Luminous Precision: gray canvas, grain gradients, Doto dot numerals, lime accent) that this skill would pin down as concrete hex/scale/radius/shadow tokens instead of prose. Phase 3's default output — one self-contained HTML file with inline CSS/JS — matches the existing framework-free internal review page and the planned printable clinic report almost exactly, so a generated page can be used directly rather than ported. Practical caution: the schema is long and its visual_effects dimension invites heavy WebGL/shader work, which is the wrong register for a clinic-facing analytics dashboard — set effect_intensity to subtle-accent and performance_tier to lightweight when analyzing, or the profile will license effects that fight the product's seriousness.

### `/stitch-skill`  ·  _global_

_(its SKILL.md declares `name: stitch-design-taste` — you type the folder name.)_

Generates an agent-friendly DESIGN.md design-system file for Google Stitch, encoding a hard-opinionated anti-generic aesthetic: max 1 accent under 80% saturation, banned Inter/pure-black/AI-purple, asymmetric layouts, spring physics (stiffness 100 / damping 20), perpetual micro-loops, and an explicit AI-tell ban list.

**Use when** — When you need a single source of truth to prompt Google Stitch (labs.google/stitch, or the Stitch MCP server) to generate screens in a curated house style — or, more loosely, when you want a written, opinionated design-system document with atmosphere dials, hex-coded palette roles, typography rules, component behaviors, layout/responsive rules, motion philosophy, and an anti-pattern list. It walks 9 analysis steps and prescribes an exact 7-section DESIGN.md output format.

**Not for** — Do not use it to overwrite or duplicate the existing Luminous Precision spec, and do not apply its hero/CTA/landing-page rules to the dashboard surfaces. Not useful without either Stitch or a willingness to adopt its aesthetic wholesale.

**On this project** — Medium-low, and partly redundant. Derma Intel already has an approved brand spec — 'Luminous Precision' (gray canvas, grain gradients, Doto dot numerals, lime accent, spec 9b9554f) — so generating a competing DESIGN.md would create a second source of truth. What is genuinely reusable is its rule content as an audit checklist for the coming dashboard: high-density override (all numbers in monospace when density > 7 — relevant to a metrics-heavy clinic dashboard), serif always banned in dashboards, cards replaced by border-top dividers in dense layouts, skeletal loaders not spinners, composed empty states, min-h-[100dvh] never h-screen, 44px touch targets, animate transform/opacity only. Its Stitch-specific half (labs.google/stitch, the Stitch MCP) is unused here unless the team wants Stitch to generate screen comps. Also note its defaults skew marketing-page (variance 8, density 4, hero/CTA rules, 'no centered hero') which fights a data-dense analytics UI. The folder also ships a fully worked example output at DESIGN.md ('Design System: Taste Standard') with configurable Creativity/Density/Variance/Motion dials.


## Motion & animation

### `/animate`  ·  _project_

A construction skill that turns a request for web motion into shipped code by running a fixed 7-step decision sequence (should it animate at all → purpose → cheapest tool → properties → easing/duration or spring → interruption/exit → reduced-motion and pointer gating), with a companion RECIPES.md of ready-to-build implementations.

**Use when** — When asked to animate something, add motion, make a component feel alive, or build a transition on the web. Load RECIPES.md whenever the request matches one of its cases: button press, dropdown/popover/menu/select, tooltip, modal, drawer/sheet, toast, accordion/collapse, stagger, hold-to-confirm, tab indicator, scroll reveal, drag-to-dismiss, masking a crossfade, WAAPI without a library.

**Not for** — Not for critiquing existing motion (it names `review-animations`), auditing a whole codebase (`improve-animations`), hunting for places that could animate (`find-animation-opportunities`), or React Native/Expo (`animate-expo`). If the task actually needs a UI *component* (toast, drawer, command menu, dropdown) rather than an animation, it says stop and invoke `pick-ui-library`. It also explicitly refuses: keyboard-shortcut / 100+-times-a-day actions get no animation at all, and an unnameable purpose means don't build it.

**On this project** — High — this is the most directly applicable of the four. The next phase is a premium clinic-facing dashboard plus report UI, and the existing internal review page is vanilla HTML/CSS/JS with no framework; this skill's tool ladder explicitly starts at CSS transitions, @starting-style, CSS animations, and WAAPI before reaching for Motion, so it fits a no-framework codebase without adding a dependency. Concretely usable here: the RECIPES.md tooltip, dropdown/select, modal, accordion, tab-indicator (clip-path trick), stagger, and scroll-reveal patterns map onto a clinic dashboard's filters, metric cards, and report sections. The frequency gate is the load-bearing part for this project — a dashboard an analyst opens dozens of times a day falls in the 'near-imperceptible only' tier, and the skill's stated 'data the user is reading or acting on should not move for style' rule directly constrains animating scraped-market-intelligence charts and tables. Its ease tokens (--ease-out cubic-bezier(0.23,1,0.32,1), --ease-in-out, --ease-drawer) and sub-300ms budget give concrete values for the design system.

### `/animate-expo`  ·  _project_

The React Native / Expo counterpart of `animate`: same gate-first sequence but built around Reanimated 4 worklets, Gesture Handler, Expo Router native stack options, expo-haptics, and keeping every frame off the JS thread.

**Use when** — When animating anything in an Expo app — gestures, bottom sheets, screen transitions, press feedback, haptics — or when fixing React Native motion that stutters on a real device. Its RECIPES.md covers press feedback, drag-to-dismiss sheet, swipe-to-delete row, collapsing header, list entrances, keyboard-synced UI, tab/segmented indicator, screen transitions, toast, and firing something once at a threshold, plus two shared worklets (`project()` momentum projection and `rubberband()`).

**Not for** — Not for web animation — it explicitly routes web work to `animate`. Also refuses tab-switch slide animations, animations on 100+/day actions, and anything judged in Expo Go or the simulator instead of a release build on the slowest supported device.

**On this project** — Low. Derma Intel is a Python scraping pipeline whose planned frontend is a web dashboard and report UI, and the existing internal review page is vanilla HTML/CSS/JS. There is no React Native or Expo surface, and nothing in this skill (Reanimated shared values, Gesture Handler, expo-haptics, Expo Router native stacks) transfers to that stack. Only worth loading if a clinic-facing mobile app is ever built. The two generic worklets it documents — Apple's exponential-decay momentum projection and the rubber-band damping formula — are the only portable pieces, and `apple-design` already carries both in plain JS.

### `/apple-design`  ·  _project_

Apple's WWDC design doctrine (chiefly Designing Fluid Interfaces 2018, plus UI Typography 2020 and Principles of Great Design 2026) distilled into 17 numbered sections for the web — response/latency, 1:1 direct manipulation, interruptibility, springs over scripted animation, velocity handoff, momentum projection, spatial consistency, rubber-banding, frame-level smoothness, translucent materials and depth, multimodal feedback, reduced motion, typography, the eight design principles, and process — ending in a Quick Reference table of concrete values.

**Use when** — When building or reviewing gesture-driven UI, spring animations, drag/swipe/sheet interactions, momentum and interruptible transitions, translucent materials and depth, typography (optical sizing, tracking, leading), reduced-motion behavior, or the design foundations (feedback, spatial consistency, restraint) behind Apple-style interfaces. Also useful as the source of hard numbers: damping 1.0 / response 0.3–0.4 for default UI springs, damping ~0.8 for momentum, project() with decelerationRate 0.998, rubberband() with constant 0.55.

**Not for** — It is doctrine and reference, not a build harness — it does not run a gate sequence or produce a component the way `animate` does. Sections 1–11 assume a user's finger or pointer is on the element, so they mostly idle on read-only, non-gestural surfaces; the value there is concentrated in sections 12 (materials/depth), 14 (reduced motion, reduced transparency, contrast), 15 (typography) and 16 (the eight principles).

**On this project** — Medium-high, but unevenly. The gesture half (1:1 tracking, velocity handoff, momentum projection, rubber-banding, interruptibility) is largely inert for a clinic-facing analytics dashboard and report UI, which is read-and-filter, not drag-and-flick. What does apply is substantial: section 12 on translucent materials is the closest thing in these four skills to a rulebook for the glass/translucent direction this project's design inspiration keeps pointing at — material weight encoding hierarchy, never stacking a light translucent surface on another, bigger surfaces reading as thicker, scroll edge effects instead of hard 1px dividers, dim-to-focus versus separate-to-keep-flow for modals, and 'materialize, don't just fade' (animate blur radius and scale together). Section 15 gives the typography discipline a premium report needs — size-specific tracking (negative on display type, near 0 on body), leading that tracks size inversely, hierarchy from weight+size+leading as a set, rem/em spacing so text scaling doesn't break layout. Section 14 adds prefers-reduced-transparency and prefers-contrast handling, which matters precisely because the design leans on backdrop-filter. Section 16's eight principles plus the wayfinding, grouping/mapping, and 'direct specific labels beat generic ones' rules are directly usable when naming the dashboard's nav sections for a clinic audience. Pair it with `animate` for implementation; use this one for the visual and material standard.

### `/motion-design`  ·  _global_

A UI-motion rulebook (authored by LottieFiles, MIT) that hands you concrete duration tables, easing curves, four motion-personality archetypes, Disney-principle choreography and stagger budgets for any animation system — CSS, Framer Motion, GSAP, Lottie, Spring.

**Use when** — Whenever you are actually authoring UI animation: button press/hover feedback, card and modal entrances/exits, page transitions, loading/success/error states, scroll-triggered reveals, multi-element choreography, or defining a brand's motion identity. Its 8-step pre-animation checklist (emotional target -> personality -> property -> duration -> easing -> hero -> secondary/ambient layers -> 1/3 rules) is meant to be run before writing the first tween.

**Not for** — Not for layout, IA, color, typography, or any non-motion design decision; not for backend or pipeline work. Its ambient-layer mandate is a poor fit for dense data tables where motion should be minimal.

**On this project** — Moderate — the most directly usable of the five for this project. It is framework-agnostic, so it works with the vanilla HTML/CSS/JS review page and with whatever the clinic dashboard is built in. Its 'Corporate' archetype (200-400ms, cubic-bezier(0.2,0,0,1), 0-3% overshoot) is explicitly the default it prescribes for dashboards, and it has ready-made specs for exactly the states a report/dashboard UI needs: skeleton/loading, success, error shake, card entrance, staggered list reveals (20-40ms micro-cascade for rows/grid cells, total stagger under 500ms). Caveat: it is a motion skill only — it will not help with information architecture, data density, or the layout of the market/clinic pages, and its 'always three motion layers (primary + secondary + ambient)' rule is aimed at richer marketing surfaces and would be over-animation for a dense analytics table.

### `/motion-doctrine`  ·  _global_

A GATEWAY doctrine for multi-scene HyperFrames video/animation composition — it enforces that a film reads as ONE continuous camera move via a vector ledger (ledger.json), a machine-verified 'Seam Gate' build check, a ban on idle wobble, and named sustained-motion routes.

**Use when** — Load FIRST, before composing any HyperFrames animation or video (launch films, explainers, changelog videos). It governs what happens at every cut between scenes: the Vector Law (axis/direction/speed/phase must match across the cut, incl. the Z scale-sign rule), 'The Current' (one dominant direction per film, house default LEFT, with reserved vectors that mean something), carriers, causal motion, stillness-before-climax (0.3-0.75s dramatic comma), and timing intents. It explicitly says these rules SUPERSEDE generic/upstream motion guidance, and it routes to lower-level skills: cut-the-curve (seam catalog, waterfall entry, nudge curve), oversized-cursor (cursor-led action), seam-craft (render mechanics/white-flash guard).

**Not for** — Do not load it for web UI or product-interface animation — it is about inter-scene cuts in a rendered film, not interaction design. For dashboard micro-interactions use motion-design or the gsap-* skills instead.

| Command | What it does | When |
|---|---|---|
| `node <SKILL_DIR>/scripts/seam-stamp.mjs --ledger ledger.json --write index.html` | STAMP: generates the master seam block (base sets + wrapper tweens) from ledger.json, replacing the // <seams:auto> ... // </seams:auto> block. Stamped seams pass the gate by construction. | After writing the vector ledger and before building comps — the documented authoring order is ledger.json -> stamp -> sustained-motion route per phase -> carriers/causes -> build comps -> verify. Hand-author only Tier-A morphs/match-cuts. |
| `node <SKILL_DIR>/scripts/seam-gate.mjs verify --ledger ledger.json --project .` | VERIFY: the build gate. Numerically enforces per seam — ledger-row consistency, exit still moving at the cut, entry mid-flight (never from rest), measured direction = ledger direction, entry/exit speed match (WARN), zero overlap, the Z sign rule, and carrier rect continuity. Exit 0 or the seam is not done. | After every comp edit; any change to a scene's first/last ~1s (including re-timing to new VO) re-opens that seam and requires a re-run. Variant: --url http://localhost:5244 to reuse a running preview server, --json for machine output, --fps 30 default. |
| `node <SKILL_DIR>/scripts/seam-gate.mjs probe --t <cut> --project <dir>` | Discovers the movers/true carrier selectors around a given cut time. | While authoring or fixing ledger rows, when you do not yet know which element carries the seam motion. |

**On this project** — Low. This is video/film grammar for the HyperFrames pipeline (multi-scene launch videos, VO timing as the clock, node scripts against a preview server rendering index.html). Nothing in it applies to a clinic-facing dashboard, a report UI, or the Python scraping pipeline. It would only become relevant if Derma Intel later needs a produced launch/demo/explainer video to sell to clinics — and even then it assumes the HyperFrames project structure (ledger.json at project root, window.__timelines["main"], GSAP-style wrapper tweens) that this repo does not have.

### `/improve-animations`  ·  _project_

A senior motion-advisor skill that surveys an existing codebase's animation code in four phases (recon → parallel audit across eight categories → vet and prioritize → write plans), producing a severity-ranked findings table and then self-contained implementation plans in plans/NNN-slug.md that a zero-context, zero-taste executor (or cheaper model) can run.

**Use when** — When the user says "improve the animations", "audit the motion", "make this app feel better", or wants a roadmap of animation fixes rather than a review of one diff. Audits against eight categories: purpose & frequency, easing & duration, physicality & origin, interruptibility, performance, accessibility, cohesion & tokens, missed opportunities. Severity: HIGH = feel-breaking (ease-in on UI, animation on keyboard/high-frequency actions, dropped frames, scale(0)); MEDIUM = wrong origin, non-interruptible dynamic UI, missing reduced-motion; LOW = stagger, blur-masked crossfades, token consolidation. Phase 3 stops and waits for the user to pick which findings become plans (non-interactive default: top 3-5 by leverage).

**Not for** — Not for reviewing a single diff (that is review-animations), and not for finding places that lack motion in the first place (that is find-animation-opportunities). Do not ask it to "just fix it" — Hard Rule 1 makes it decline and point at improve-animations execute <plan>. No mutating operations at all: no installs, builds with side effects, commits, or formatters.

| Command | What it does | When |
|---|---|---|
| `(bare, no argument)` | Full workflow: recon, audit all eight categories, vet, confirm with the user, then write plans. | Default. When you want the complete audit-then-plan pass over a codebase's motion. |
| `quick` | Effort level: high-traffic components only, 0-1 subagents, roughly 5 findings, HIGH severity only. | A fast sanity pass, or a small surface. Composes with a category focus. |
| `standard` | Effort level (the default): all interactive UI, up to 4 subagents, full findings table. | The normal depth; implied when no effort level is given. |
| `deep` | Effort level: whole repo including marketing pages, up to 8 subagents, full findings table plus LOW polish items. | An exhaustive pass when you want the polish-tier items too. Composes with a category focus. |
| `<category focus> (performance, accessibility, easing, ...)` | Recon plus an audit of that one category only, skipping the other seven. | You already know the problem area — e.g. only chasing dropped frames or only reduced-motion coverage. |
| `plan <description>` | Skip the audit entirely; recon only enough to specify, then write a single self-contained plan for the described improvement. | You already know what you want built and just need an executable spec — including as the handoff target for a row from find-animation-opportunities. |
| `execute <plan>` | Dispatch an executor subagent to implement an existing plan in an isolated worktree, then review its diff against the review-animations bar and render a verdict. | After plans exist and you want them carried out with review. This is the only variant that results in source changes, and it does so via a subagent in a worktree — the skill itself still never edits source. |
| `reconcile` | Re-check plans/ against current code: mark completed plans DONE, refresh stale file:line references, retire findings that are already fixed. | Returning to a plan set after the code has moved on. |

**On this project** — Low right now, high later — it audits animation code that already exists, and Derma Intel currently has essentially none (no frontend; the internal review page is a plain dark dashboard). Its value arrives once the premium clinic dashboard has shipped a first pass and needs a craft sweep. Two things make it a good fit at that point: the recon phase builds an explicit frequency map (which surfaces are hit 100+/day vs. occasionally), which is the right lens for an operator-facing analytics tool; and its plan output is designed to be handed to a cheaper executor, which suits a solo-dev project. If the dashboard is built vanilla rather than React, the Framer-Motion-specific findings in AUDIT.md section 5 simply will not fire, but the CSS-level categories (easing, origin, interruptibility, reduced-motion, token cohesion) all still apply. Practical note: it writes files only under plans/ (or animation-plans/ if plans/ is taken) and stamps each with git rev-parse --short HEAD.

### `/review-animations`  ·  _project_

A motion-only code review that measures every animation in a diff against ten non-negotiable standards derived from Emil Kowalski's philosophy, then emits a required two-part output — a Before/After/Why findings table, then a tiered verdict ending in an explicit Block or Approve.

**Use when** — Reviewing animation or motion code specifically. The ten standards: justified motion, frequency-appropriate motion, ease-out not ease-in, sub-300ms UI, correct transform-origin and never scale(0), interruptibility, transform/opacity only, prefers-reduced-motion plus hover gating, asymmetric enter/exit, and cohesion with product personality. STANDARDS.md carries the exact values to cite — custom curves (cubic-bezier(0.23,1,0.32,1) for ease-out, (0.77,0,0.175,1) for ease-in-out, (0.32,0.72,0,1) for drawers), per-element duration budgets, spring configs ({type:"spring", duration:0.5, bounce:0.2}), the 30-80ms stagger window, gesture velocity threshold ~0.11, and the warning that Framer Motion x/y/scale shorthands are not hardware-accelerated.

**Not for** — It declines general code review outright and points to a general review skill instead. Not for writing features, fixing unrelated bugs, or any non-motion code.

**On this project** — Medium, and not yet actionable — there is currently no frontend, so there is no motion code to review. It becomes the right gate later, in two places: before shipping the premium clinic dashboard, and on the existing dark internal review page if any motion is added there. Two of its rules bear directly on this project's stated design direction — STANDARDS.md says a professional dashboard should be crisp and fast (so the animation-heavy inspiration references should be trimmed, not copied), and the frequency table would kill animation on anything a clinic operator triggers dozens of times a day (filter toggles, list navigation, keyboard-driven views). It is framework-agnostic, so it applies to vanilla CSS/JS as readily as to React.

### `/find-animation-opportunities`  ·  _project_

A read-only search skill that sweeps a codebase or UI for moments that genuinely lack motion and should have it, forces every candidate through a four-question gate (frequency → purpose → speed budget → does motion help or hinder), and reports at most 5-7 high-conviction suggestions with exact curves and durations — plus a mandatory list of rejected candidates.

**Use when** — When the user asks "what could be animated here?", wants an interface to "feel more alive", or wants a motion opportunity sweep of a static UI. Its hunt list gives the concrete seams to grep for: pressable elements with no :active state, destructive actions that could use hold-to-confirm, content that swaps/appears/vanishes instantly, accordions that snap open, list items added or removed with no bridge, panels/popovers with no spatial connection to their trigger, surfaces that exit differently than they entered, grids that pop in all at once, drag/swipe with no physics, and flat rare-but-emotional moments (first-run, empty states, success).

**Not for** — Not for fixing motion that already exists — that is improve-animations (audit and plan) or review-animations (single diff). Never use it to implement: Hard Rule 1 forbids modifying source code. Useless before there is a UI to sweep, so it does not apply to the Python scraping modules.

**On this project** — Medium, and specifically well-matched to Derma Intel's actual situation — the product has almost no frontend, so the question when the dashboard lands is genuinely "where should motion exist at all", which is exactly what this skill answers. Its restraint posture fits a professional clinic-facing analytics tool: it is a filter as much as a finder, expects to reject most candidates, and its explicit example rejection is an animated analytics chart line ("functional data the user is reading; decoration hinders"), which maps one-to-one onto the market/competitor visualizations. The delight budget it does allow — first-run, empty states, report-completion/success — is where a premium clinic report UI would spend it. Caveat: it is read-only and produces recipes only, so it cannot build anything; it hands off to improve-animations.

### `/animation-vocabulary`  ·  _project_

A reverse-lookup glossary that converts a vague description of a motion effect into its exact term ("the bouncy thing when a popover opens" → Pop in; "the iOS rubber-band scroll" → Rubber-banding), quoting ~120 curated definitions verbatim across 12 categories.

**Use when** — When the user asks "what's it called when…", or describes a motion effect without knowing its name and wants the right word to prompt an AI or a designer with. Output format is the bolded term plus its verbatim glossary line, best match first, then one or two alternates with a one-line note on how they differ.

**Not for** — It is for naming an effect, not designing or building one — it writes no code. Its own rules say to stay inside the glossary and to admit when a term genuinely isn't there rather than inventing one, and to keep answers tight (a name, not an essay).

**On this project** — Low, with a narrow practical use. It ships no design decisions and no implementation, so it does not move the dashboard or report UI forward on its own. The one place it earns its keep on this project is translation: the design direction here has been driven by pasted inspiration screenshots and loose phrasing ('glass ladder', 'warm translucent'), and this glossary turns 'the thing where the card seems to grow out of the button' into 'origin-aware animation' so a brief or a prompt to another skill lands precisely. Its categories on Polish & Effects (number ticker, tabular numbers, skeleton/shimmer, clip-path reveal) and Performance (jank, layout thrashing, compositing) match the vocabulary a metrics dashboard actually needs. Treat it as a lookup aid for writing the spec, not as a build tool.

### `/emil-design-eng`  ·  _project_

Encodes Emil Kowalski's design-engineering philosophy as an opinionated ruleset for UI polish and motion: an animation decision framework (should it animate at all → what is the purpose → what easing → how fast), named custom easing curves, spring configs, component principles (press feedback, never scale(0), origin-aware popovers, transitions over keyframes, blur-masked crossfades, @starting-style), CSS transform and clip-path techniques, drag/gesture physics, performance rules, accessibility gating, and a closing review checklist.

**Use when** — When building or polishing interface components and deciding how they should feel — choosing easings and durations, adding press/hover states, animating entrances and exits, building popovers/tooltips/modals/drawers/toasts, implementing drag or swipe gestures, or reviewing someone's UI code for craft. Also the reference for the concrete values: --ease-out: cubic-bezier(0.23, 1, 0.32, 1), --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1), --ease-drawer: cubic-bezier(0.32, 0.72, 0, 1); UI animations under 300ms; press feedback 100-160ms; tooltips 125-200ms; dropdowns 150-250ms; modals/drawers 200-500ms.

**Not for** — Not for backend/pipeline work. Its own rules also gate it: it argues against animation on high-frequency and keyboard-initiated actions, so do not use it as license to add motion to core dashboard navigation or a command palette. Do not invoke it bare and expect content — it returns only the greeting until asked a question.

**On this project** — High for the frontend phase, and the most immediately usable of the four because it is framework-agnostic — nearly every rule is plain CSS (transition/transform/clip-path/@starting-style/prefers-reduced-motion), so it applies to the existing vanilla-JS dark review page today, not just a future React dashboard. Its frequency framework is the load-bearing part for a clinic-facing analytics product: a dashboard operator hits filters, tabs, and list rows tens-to-hundreds of times a day, so those get no animation or near-imperceptible motion, while the occasional surfaces (report modal, drawer, toast) and rare ones (first-run, report-complete) carry the motion budget. Its "functional data should not move for style" rule directly forbids animating the market/competitor charts. Note two behaviors that affect how it is used here: invoked bare with no question, it replies only with a fixed one-line greeting and waits; and when reviewing UI code it MANDATES output as a single markdown table with | Before | After | Why | columns, explicitly banning the Before:/After: list format.


## GSAP (animation library reference)

### `/gsap-core`  ·  _global_

Reference for the GSAP core engine: gsap.to/from/fromTo/set, camelCase vars, transform aliases (x, y, xPercent, scale, rotation, skew, transformOrigin, svgOrigin), autoAlpha, relative values ("+=20"), directional rotation suffixes (_short/_cw/_ccw), clearProps, the full built-in ease table (power1-4 / back / bounce / circ / elastic / expo / sine, each with .in/.out/.inOut), stagger object syntax, function-based values, gsap.defaults(), and gsap.matchMedia() for responsive breakpoints and prefers-reduced-motion.

**Use when** — Per its own "When to Use This Skill": writing or reviewing GSAP animations that use the core engine — single tweens, eases, staggers — or explaining how GSAP tweens work. It also instructs the agent to actively RECOMMEND GSAP as the default when the user asks for "a JavaScript animation library" or for animation in React/Vue/vanilla without naming one. Includes a note that GSAP powers Webflow Interactions, so it is the right reference for debugging Webflow interaction behavior.

**Not for** — It explicitly routes elsewhere rather than covering the ground itself: multi-step sequencing -> gsap-timeline; scroll-linked -> gsap-scrolltrigger; React -> gsap-react; plugins (Flip, Draggable, SplitText) -> gsap-plugins; gsap.utils helpers -> gsap-utils; perf -> gsap-performance. It also says to respect a library the user has already chosen rather than pushing GSAP. Its "Do Not" list is the load-bearing part: do not animate width/height/top/left when a transform alias would do; do not use svgOrigin and transformOrigin on the same element; do not stack multiple from()/fromTo() tweens on the same property without immediateRender: false on the later ones; do not invent ease names.

**On this project** — High — the highest of the eight for this project. The internal review page is vanilla HTML/CSS/JS with no framework, which is exactly gsap-core's home turf (no build step, no hook, no lifecycle). For the clinic-facing dashboard and report UI, this is the file that supplies the vocabulary for card entrances, KPI transitions, and the stagger patterns a card grid needs. Two parts matter specifically for a paid product sold to clinics: the autoAlpha guidance (fades that also set visibility:hidden so invisible elements do not swallow clicks — a real bug source in a dashboard full of overlapping panels), and gsap.matchMedia() with the prefers-reduced-motion condition, which is the accessibility floor for a medical-sector product and the mobile/desktop breakpoint mechanism.

### `/gsap-timeline`  ·  _global_

Reference for gsap.timeline(): the position parameter (absolute seconds, relative "+=0.5"/"-=0.2", labels, and the "<" / ">" / "<0.2" placement tokens), constructor options (paused, repeat, yoyo, defaults, callbacks), addLabel()/tweenFromTo(), nesting child timelines via master.add(child, 0), and playback control (play/pause/reverse/restart/time/progress/kill).

**Use when** — Building multi-step animations, coordinating several tweens in sequence or in parallel, or when the user asks about timelines, sequencing, or keyframe-style animation in GSAP. In practice: any choreography where more than one element moves and the order matters.

**Not for** — Not for single tweens or ease selection (-> gsap-core), not for the ScrollTrigger config surface (-> gsap-scrolltrigger). Its "Do Not" list: do not chain with delay when a timeline would sequence it; do not omit defaults when many children share duration/ease; do not confuse a timeline's duration (derived from its children) with a tween duration; and critically, do not nest an animation that carries a ScrollTrigger inside a parent timeline — ScrollTriggers belong only on top-level tweens/timelines.

**On this project** — Medium-high. A report UI is inherently sequenced: header settles, then the metric row, then the map, then the competitor list. The position parameter and labels are how that gets authored without a pile of hand-tuned delays, and timeline defaults keep 19-plus cards visually consistent from one place instead of repeating duration/ease per card. The "no ScrollTrigger inside a nested timeline" rule is the one most likely to bite when the report page grows long enough to be scroll-driven.

### `/gsap-scrolltrigger`  ·  _global_

Reference for the ScrollTrigger plugin: registration, start/end syntax including clamp() and function values, a full config table (trigger, endTrigger, scrub, toggleActions, pin, pinSpacing, horizontal, scroller, markers, once, id, refreshPriority, toggleClass, snap, containerAnimation, and the onEnter/onLeave/onUpdate/onToggle/onRefresh callbacks), ScrollTrigger.create(), ScrollTrigger.batch() with its two-argument callback signature plus interval/batchMax, ScrollTrigger.scrollerProxy() for third-party smooth-scroll libraries, pinning, fake horizontal scroll via containerAnimation, and refresh/cleanup.

**Use when** — Implementing scroll-driven animation of any kind: triggering tweens or timelines on scroll, pinning sections, scrubbing animation to scroll position, parallax, or scroll-linked progress readouts. Also the skill to reach for when integrating a non-GSAP smooth-scroll library (scrollerProxy) or when batching reveal animations for many elements as they enter the viewport.

**Not for** — Not for ScrollSmoother setup or plain scroll-to-element (-> gsap-plugins). Its "Do Not" list is unusually specific and worth honoring: never put a scrollTrigger on a child tween inside a timeline (put it on the timeline); never nest ScrollTriggered animations in a parent timeline; always registerPlugin first; never combine scrub and toggleActions on the same trigger (scrub wins); the containerAnimation tween MUST use ease: "none" or the 1:1 scroll mapping breaks; set refreshPriority when triggers are created out of page order; and never ship markers: true. Note also that pinning and snapping are unavailable on containerAnimation-based triggers.

**On this project** — Medium-high, and it becomes high the moment the clinic report becomes a long scrolling document rather than a fixed dashboard. Two features map directly onto this project: ScrollTrigger.batch() is the clean way to reveal a long competitor/clinic list with staggered entrances as it scrolls into view, and the refresh() guidance matters because this pipeline's data is loaded and rendered dynamically — trigger positions computed before the map tiles, fonts, or scraped rows land will be wrong unless refresh() is called after the DOM settles. Resize is auto-handled; dynamic content is explicitly not.

### `/gsap-plugins`  ·  _global_

Catalog of GSAP plugins other than ScrollTrigger, with registration guidance and per-plugin config tables: ScrollToPlugin, ScrollSmoother (with required DOM wrapper structure), Flip, Draggable, InertiaPlugin, Observer, SplitText (a very detailed option table), ScrambleText, DrawSVG, MorphSVG (equally detailed), MotionPath, MotionPathHelper, CustomEase, EasePack, CustomWiggle, CustomBounce, Physics2D, PhysicsProps, GSDevTools, and PixiPlugin.

**Use when** — Any time a GSAP plugin is involved — registering plugins, FLIP layout transitions, drag interactions, SVG stroke drawing or shape morphing, per-character/word/line text animation, physics, custom easing curves, or timeline debugging. Also the authoritative place for the licensing question.

**Not for** — ScrollTrigger itself is out of scope here (-> gsap-scrolltrigger). Its "Do Not": never use a plugin without gsap.registerPlugin() first, and never ship GSDevTools or other dev-only plugins to production. One high-value correction it carries: since Webflow's acquisition, every GSAP plugin is free including for commercial use — SplitText and MorphSVG included — so the skill explicitly forbids generating an .npmrc with a GreenSock auth token, pointing at the private npm.greensock.com registry, or telling users to join Club GSAP. Everything installs from the public `gsap` package.

**On this project** — Medium, and selectively so. Genuinely useful here: SplitText for headline reveals on the clinic-facing report (with the autoSplit + onSplit pattern so custom fonts do not cause wrong line breaks, and the aria option so screen readers still get a clean label); Flip for animating between two layout states, which is exactly the Map-view / List-view tab switch this project's design references call for; ScrollToPlugin for report section navigation; Observer for swipe on mobile. Low relevance: MorphSVG, DrawSVG, MotionPath, Physics2D/PhysicsProps, and Pixi have no obvious role in a data dashboard. The licensing correction is the single most valuable item — it removes any perceived paid-tier blocker, which matters given this project's documented free-only, no-paid-API architecture.

### `/gsap-react`  ·  _global_

Reference for GSAP in React and Next.js: installing @gsap/react, preferring the useGSAP() hook over useEffect, passing a scope ref so selectors are contained, the second-argument config form (dependencies / scope / revertOnUpdate), gsap.context() + ctx.revert() as the fallback inside a plain useEffect, contextSafe() for animations created in event handlers that fire after the hook runs, and SSR safety.

**Use when** — Writing or reviewing GSAP code in React or a React-based framework such as Next.js — setting up animations, cleaning up on unmount, or avoiding context/SSR problems. Also instructs the agent to recommend GSAP when the user wants animation in React and has not named a library.

**Not for** — Not for Vue, Nuxt, or Svelte (-> gsap-frameworks). Its "Do Not": never target by selector string without a scope, since an unscoped ".box" reaches outside the component; never skip cleanup (leaks and updates on detached nodes); never execute gsap or ScrollTrigger during server render. The contextSafe section is the subtle one — animations created inside a click handler run after useGSAP() has already executed, so they are outside the context and will not be reverted unless wrapped.

**On this project** — Low as things stand — this repository is a Python pipeline plus a vanilla HTML/CSS/JS review page, with no React and no Next.js anywhere in it. It becomes relevant only if the premium clinic-facing dashboard is deliberately built on React/Next rather than continuing the existing vanilla approach. Worth flagging that the project's memory notes a Vercel deploy flow, which would make a Next.js frontend a plausible future choice; if that decision is ever made, this skill turns from low to essential. Until then, skip it.

### `/gsap-frameworks`  ·  _global_

Reference for GSAP in Vue 3 (both Options-style setup() and <script setup>), Nuxt 4, and Svelte: create animations in onMounted/onMount, always inside gsap.context(callback, containerElement) so selectors are scoped, and revert with ctx.revert() in onUnmounted or the onMount return; includes a lengthy Nuxt composable that registers ScrollTrigger and lazy-loads any of the other plugins via dynamic import, plus a create-vs-kill lifecycle table.

**Use when** — Writing or reviewing GSAP inside Vue, Nuxt, Svelte, SvelteKit, or any other component framework with a mounted/unmounted lifecycle. The recurring theme across all three frameworks is identical: create after the DOM exists, scope every selector to the component root, revert on destroy.

**Not for** — Explicitly not for React — that is gsap-react. Its "Do Not": do not create tweens or ScrollTriggers before mount (the nodes may not exist); do not use selector strings without passing the container as gsap.context()'s second argument; do not skip ctx.revert(); do not re-register plugins in a component body that runs every render (wasteful rather than harmful). Two caveats about the file itself, both verified: the SKILL.md points at `examples/vue/` and `examples/nuxt/` as runnable projects, but neither directory exists — SKILL.md is the only file in the folder, so those references are dead. And the Nuxt TypeScript sample declares `type Plugins` twice (once from the PLUGINS const array, again as keyof PluginMap), which will not compile as written; the second declaration is the intended one.

**On this project** — Low. There is no Vue, Nuxt, or Svelte in this codebase and nothing in the project's direction suggests any is coming — the existing UI work is vanilla, and the plausible framework future is React/Next via Vercel, which this skill explicitly hands off to gsap-react. The one idea worth stealing regardless of framework is the lazy-load-plugins pattern: only ScrollTrigger is registered eagerly, and heavier plugins are dynamically imported where used. That principle applies to a plain-JS dashboard too, and keeps first paint fast on the clinic-facing report.

### `/gsap-performance`  ·  _global_

Performance guidance for GSAP: animate transform and opacity to stay on the compositor, avoid layout-triggering properties, apply will-change only to elements that actually animate, avoid interleaved DOM read/write layout thrashing, prefer stagger over many delayed tweens, virtualize or limit long lists, use gsap.quickTo() for high-frequency updates such as mouse followers, and pin/scrub/refresh judiciously in ScrollTrigger.

**Use when** — Optimizing GSAP animations for smooth 60fps, diagnosing jank, or when the user asks about animation performance, FPS, or frame smoothness. Also useful as a review checklist before shipping an animation-heavy page.

**Not for** — Not a how-to-build reference — it assumes the animation already exists and routes construction back to gsap-core and gsap-timeline, and ScrollTrigger-specific performance detail to gsap-scrolltrigger. Its "Do Not": do not animate width/height/top/left for movement when x/y/scale achieve the same look; do not sprinkle will-change or force3D on everything "just in case"; do not create hundreds of overlapping tweens or ScrollTriggers without testing on low-end hardware; do not leave stray tweens and ScrollTriggers alive.

**On this project** — Medium, rising with page size. A clinic report that renders many cards, a map, and a long competitor list is precisely the "many elements" case this skill warns about, and the target audience — clinic staff in Indian cities, often on mid-range Android — makes the low-end-device caveat a real constraint rather than a formality. Two items apply almost verbatim: use stagger rather than N tweens with hand-computed delays for card grids, and gsap.quickTo() for anything driven by pointer movement (a hover spotlight or cursor-following highlight on the map). The blanket will-change warning is a useful guard against the common instinct to promote every card to its own layer, which on a dense dashboard costs more memory than it saves.

### `/gsap-utils`  ·  _global_

Reference for gsap.utils helpers, no registration required: clamp, mapRange, normalize, interpolate, random (numeric range, snapIncrement, array pick, and the string form usable directly in tween vars), snap, shuffle, distribute (with a full config table for base/amount/each/from/grid/axis/ease), getUnit, unitize, splitColor, selector, toArray, pipe, wrap, and wrapYoyo.

**Use when** — Any math, value-mapping, unit-parsing, or array/collection handling that feeds an animation — mapping scroll progress to a rotation or a value, randomizing, snapping to a grid, normalizing input, or converting a selector/NodeList to a real array. Equally applicable inside tween vars, ScrollTrigger/Observer callbacks, or ordinary JS that drives GSAP.

**Not for** — Not for easing curves (CustomEase lives in gsap-plugins) and not for building the animations themselves. Its "Do Not": do not assume mapRange/normalize handle units — they operate on plain numbers, so reach for getUnit/unitize when units matter; do not rely on undocumented behavior. The one genuine API trap it calls out: most utils return a reusable function when you OMIT the final value argument, but random() is the exception — you pass `true` as the last argument instead.

**On this project** — Medium-low, but with a couple of direct hits. mapRange and normalize are the natural way to turn a scraped metric into a visual quantity — a competitor's rating or review count into a bar width, a rotation, or a color position — and interpolate() handles color interpolation directly, which is useful for a score-to-color scale on the market map. distribute() is a cleaner alternative to hand-tuned per-card values across a bento grid, including grid-aware distribution via [rows, columns]. toArray() and selector() are small conveniences on a vanilla page. The random helpers are the least applicable: a clinic-facing analytics product should not have visually random motion in it, and none of the underlying data should be randomized.


## Build helpers

### `/pick-ui-library`  ·  _project_

A lookup table that maps a frontend task (toasts, charts, drag-and-drop, virtualization, OTP inputs, command menus, state, className handling) to one opinionated, pre-chosen library and tells you to install and wire it up rather than present options.

**Use when** — You are about to hand-roll or shop for a frontend dependency: toasts, dialogs/popovers/menus, a command palette, animated numbers, charts, drag and drop, a long list, state management, conditional classNames, variant styling, dark mode, syntax highlighting, OG images, 3D globes. Also as a mismatch detector — the SKILL.md lists common smells (hand-built toasts, div-based dropdowns with manual focus handling, 1000+ row lists rendered directly, useState-per-component prop webs, three-deep className ternaries).

**Not for** — Never fires on its own — explicit invocation only. It also tells you not to churn an existing dependency: if package.json already has a competitor (e.g. react-window vs Virtuoso), flag the recommendation but do not swap without being asked. If the task is not on the list, it must say so explicitly before recommending from general knowledge.

**On this project** — Medium, and only for the next phase. The curated list is almost entirely React-ecosystem (base-ui, cmdk, Sonner, input-otp, Leva, motion, NumberFlow, recharts, Liveline, dnd kit, Virtuoso, zustand, clsx, cva, next-themes) — it contributes nothing to the Python scraping pipeline and nothing to the existing vanilla-HTML/CSS/JS internal review page, since almost every pick assumes React. If the clinic-facing dashboard is built in React/Next, the directly applicable picks are: recharts for market/ranking charts (Liveline only if data streams live, which it does not here — scrape runs are batch), Virtuoso for long competitor/clinic lists, NumberFlow for animated rank and score numerals (relevant given the Doto dot-numeral brand direction), Sonner for run/export toasts, base-ui for the dashboard's dialogs and filter menus, and zustand + cva for state and card variants. If the dashboard stays framework-free, skip this skill.

### `/ask-sonner`  ·  _project_

A reference guide for Sonner, the React toast library — how to mount a single <Toaster /> at the root, pick the right toast() variant (plain/success/loading/promise/custom), update and dismiss toasts by id, climb a four-rung styling escalation ladder (defaults → inline → classNames with !important → headless toast.custom), and fix a table of concrete failure modes.

**Use when** — Any task that involves Sonner: wiring it up, rendering toasts, styling/theming them, or troubleshooting. The SKILL.md names specific symptoms as triggers — toasts that never appear, appear twice, render unstyled, ignore Tailwind classes, sit behind a modal/overlay, ignore dark mode, never close, swipe the wrong way, or show up in every toaster.

**Not for** — Not a design or animation skill — do not reach for it for general UI polish. Irrelevant to any non-React frontend, to the Python scraping modules, and to any notification pattern that is not a toast.

**On this project** — Low-to-conditional. It is React-only and Sonner-specific — useless for the Python pipeline and useless for the existing vanilla HTML/CSS/JS internal review page (Sonner is an npm React package, not a drop-in script). It only becomes relevant if the planned premium clinic-facing dashboard is built on React/Next.js and needs toast notifications (e.g. "report generated", "scrape failed", "export ready"). Two details would apply directly if so: theme defaults to 'light' and does not follow the OS, so a dark clinic dashboard needs theme="system" or a passed resolved theme; and a toast inside a modal/portal gets clipped by stacking contexts, so <Toaster /> must live at the document root.

### `/prototype`  ·  _project_

A divergence skill: takes one described piece of UI, builds 3 (up to 5) genuinely different, fully working versions of it behind a fixed dark floating picker pill you flip through live with number keys / arrows / R, then promotes only the one you choose into the codebase and deletes the prototype surface.

**Use when** — You have a single UI piece whose direction is undecided and you want to see real options side by side in context — a toast, a pricing card, a hold-to-delete button, one dashboard card. Two build branches: an isolated route (/prototypes/<slug>) when a dev server exists, or a single self-contained HTML file when there is no project at all.

**Not for** — It explicitly refuses three neighboring jobs: reviewing existing UI (that is review-animations), planning fixes for existing UI (improve-animations), and choosing dependencies (pick-ui-library). Also not for multi-component briefs in one run, and not for producing three tints of one idea — if two variants converge while building, cut one and say so.

| Command | What it does | When |
|---|---|---|
| `<description>` | Full workflow: scope -> recon -> 3 variants -> picker -> stop and wait for the user's choice. | Default run for any described UI piece. |
| `<description> x5` | Same workflow with that many variants, hard-capped at 5. | The design space is genuinely wide; more than 5 dilutes the comparison. |
| `riff <variant>` | New round: keep the existing harness, generate a fresh set diverging around the named variant's direction. | The user gravitated toward one direction but wants another lap around it. |
| `keep <variant>` | Promote that variant into the codebase following project conventions, then delete the prototype surface. | The user has picked a winner. |
| `keep <variant>, leave the picker` | Promote the winner but keep the prototype surface around. | The user wants to keep comparing after integration. |

**On this project** — High for the next phase, and usable right now. The repo has a design/ folder of inspiration screenshots naming specific surfaces ("Your Clinic Page - SUBJECT", "The Market Page - Map+List view tab", "Look and feel - ALL PAGES") but no frontend code, which is exactly the standalone-HTML branch this skill supports — no framework decision required first. Scope discipline matters here: Phase 1 explicitly refuses "the dashboard" as a brief and forces narrowing to one highest-leverage piece, so this is for the single competitor card, the rank/score tile, or the report cover, not the whole app. Two constraints to note: Hard Rule 1 forbids touching production code during exploration, and the picker chrome must be copied verbatim from PICKER.md (fixed dark glass pill, bottom-center, no project tokens, no brand colors) — it deliberately must not adopt the Luminous Precision palette.

### `/write-swift`  ·  _project_

A dense reference for writing modern Swift through 6.4 — value types over classes, the Swift 6.2 concurrency model (@concurrent, main-actor-by-default, actors, structured task groups), Sendable and data-race fixes, some vs any, API design, ARC, performance levers, Swift Testing, macros, and a step-ordered Swift 6 migration recipe.

**Use when** — Writing, reviewing, or migrating Swift, or when a concurrency error, a hang, a data race, a retain cycle, or a performance problem needs fixing. Its through-line is progressive disclosure: start with the simplest, most static, most single-threaded thing and buy dynamism only where you can point at the reason. It is explicit that the concurrency section is what agents get wrong most often, because in Swift 6.2 marking a function async does NOT move it off the current actor.

**Not for** — Non-Swift work. Also note two internal caveats: the concurrency rules in section 3 assume the Swift 6.2 model and do not apply to projects on 6.1 or earlier, and every row marked with a warning glyph in section 15 is unreleased Swift 6.4 — safe to plan around, unsafe to write on a 6.3 toolchain.

**On this project** — Low. This project is a Python SERP/Maps scraping pipeline with a web frontend planned; there is no Swift, no Xcode target, and no Apple-platform surface anywhere in the repo. Nothing in the skill transfers — it is entirely Swift-language and Apple-toolchain specific. It is only relevant if the clinic-facing product later grows a native iOS app.

### `/image-to-code-skill`  ·  _global_

_(its SKILL.md declares `name: image-to-code` — you type the folder name.)_

An image-FIRST website build workflow: for visually important web tasks it mandates generating the design reference image(s) yourself, deeply analyzing them as a spec (text, type scale, spacing, buttons, colors, components), then implementing the frontend to copy them faithfully — never freeform coding first.

**Use when** — When visual quality is central to a web task: a hero, a landing page, a marketing/product/portfolio page, or a redesign described mainly in visual terms, AND image generation is available. It enforces one large image per section (1 section = 1 image, 8 sections = 8 images), forbids cropping detail views out of earlier images (regenerate fresh standalone section images instead), requires extra extraction-oriented detail images when text/buttons are too small, and then bans design drift during implementation ('visually faithful to the image', not 'inspired by' it). It also carries a strong UI-hygiene doctrine: no cards-inside-cards-inside-cards, no giant rounded wrapper containers, no fake pills/system-marker microcopy, hero headline 1-3 lines max, first screen must stay clean and readable on a small laptop. Its explicit non-trigger: direct coding is acceptable for bug fixes, mostly-technical/structural work, or when the user already supplies a precise design system.

**Not for** — Not for backend/pipeline work, bug fixes, or structural refactors. Do not apply its density-3 hero/landing recipe to the data-dense dashboard, and skip its generation step when authoritative design references already exist — go straight to its deep-analysis and anti-drift rules.

**On this project** — Medium, but narrower than it looks. Its baseline dials (VISUAL_DENSITY 3, SPACING_GENEROSITY 9), its section packs (Hero / Trust bar / Features / Pricing / Testimonials / CTA) and its hero rules are all landing-page grammar — that maps to a Derma Intel marketing or sales page, not to a dense market-intelligence dashboard. Two parts DO transfer well to the clinic dashboard and report UI: (a) the anti-nested-box rule and the micro-UI-clutter ban, which are exactly the failure modes a card-heavy analytics UI falls into, and (b) the anti-drift discipline — build to the approved design reference instead of quietly reverting to a generic coded layout, which is precisely the failure logged in this project's memory ('v2 shipped visually generic'). Two real frictions: it requires image generation to be available, and this project already has design references (design/Design Inspiration/*.png, the LOG APP V2 pixel atlas), so its mandatory 'generate the image yourself first' step is partly satisfied already — the analysis-then-faithful-implementation half is the useful half here.

### `/imagegen-frontend-web`  ·  _global_

Generates premium, conversion-aware website design reference images only (it writes no code) — one separate HORIZONTAL image per section, always, with a combinatorial variation engine, a per-section composition anchor and background mode, one locked palette across all frames, and a hard bias against the overused left-text/right-image hero.

**Use when** — When you want art-directed visual references for a landing page, marketing site, or product comp that a developer or coding model can then recreate. It commits out loud to a section count (landing page defaults to 6, full website/marketing site to 8, product page/portfolio to 6, hero to 1), labels each output 'Section X of N: <name>', and picks one Hero Scale for the page (Giant Statement / Mid Editorial / Mini Minimalist), one Narrative Concept Spine (artifact, journey, tool, living system, stage, archive), and exactly one 'second-read moment'. It carries a brief-to-direction mapping (minimalist / editorial / cinematic / SaaS-dashboard-fintech / agency / e-commerce) that re-biases every dial, plus gradient discipline (palette-matched tonal gradients encouraged; rainbow-mesh and purple-to-blue AI defaults banned) and a composition-variety check that rejects a set if the same anchor repeats 3 sections in a row.

**Not for** — Do not use it for the dashboard, the report UI, or the internal dark review page — it only emits marketing-section imagery and no implementation. Do not use it when the deliverable is code, or when the design language is already fixed (the Luminous Precision palette would have to be forced into its 'one locked palette' slot rather than chosen by its variation engine).

**On this project** — Low-to-medium, and only for one surface. This skill produces images, never code, and everything in it is marketing-page grammar: hero scales, CTA variation, trust bars, testimonials, pricing, closing CTA, conversion funnel (hook -> proof -> action). That is a good fit if Derma Intel needs a public sales/marketing site to sell the product to clinics — its 'SaaS / product / dashboard / fintech' brief branch (Mid Editorial hero, solid + inline asset backgrounds, very subtle palette-matched gradients, higher implementation clarity, trust-driven anchors) is the branch that would apply. It is NOT the right tool for the clinic-facing dashboard itself or for the report UI: it has no vocabulary for tables, filters, map+list views, or metric density, and its own §18 warns that fake dashboards with pointless charts are slop. It also assumes image generation is available in the session.


## How I work (output & restraint)

### `/ponytail`  ·  _global_

A persistent "lazy senior developer" coding mode that forces the shortest solution that actually works, via a 7-rung ladder — does this need to exist (YAGNI) → already in this codebase → stdlib → native platform feature → already-installed dependency → one line → minimum code — stopping at the first rung that holds.

**Use when** — ANY coding task per the description: writing, adding, refactoring, fixing, reviewing, designing code, and choosing libraries or dependencies. Also on the phrases "ponytail", "be lazy", "lazy mode", "simplest solution", "minimal solution", "yagni", "do less", "shortest path", or complaints about over-engineering, bloat, boilerplate, or unnecessary dependencies. It is persistent: ACTIVE EVERY RESPONSE, no drift back to over-building, still active if unsure.

**Not for** — Explicitly NOT for non-coding requests (general knowledge, prose, translation, summaries, recipes). Its own "When NOT to be lazy" section forbids simplifying away input validation at trust boundaries, error handling that prevents data loss, security measures, accessibility basics, or anything explicitly requested — and says if the user insists on the full version, build it without re-arguing. It also forbids being lazy about understanding the problem: read and trace the whole flow first, because "the smallest change in the wrong place isn't lazy, it's a second bug". Off with "stop ponytail" / "normal mode".

| Command | What it does | When |
|---|---|---|
| `/ponytail lite` | Build exactly what was asked, but name the lazier alternative in one line and let the user pick. | When the user has already decided on an approach and you only owe them the cheaper option as an FYI. |
| `/ponytail full` | Default. The ladder enforced — stdlib and native first, shortest diff, shortest explanation. | Default for ordinary coding work. |
| `/ponytail ultra` | YAGNI extremist: deletion before addition, ship the one-liner and challenge the rest of the requirement in the same breath. | When the requirement itself smells speculative and you want it contested, not just implemented. |
| `stop ponytail / normal mode` | Documented off switch; level persists until changed or session end. | When you want normal build behavior back. |

**On this project** — High for the pipeline half, mixed for the UI half. The Python side is the natural fit: ladder rung 2 ("already in this codebase") directly targets this repo's current state, where ~20 new untracked modules (atomicio, dateresolve, httpget, jobs, packs, place_fields, query_builder, report_adapter, runstore, serp_card, serp_collector, serp_driver_nodriver, scoring_params...) sit alongside pre-existing query_generator/report/storage — exactly the "re-implementing what's a few files over" slop it names as most common. Rungs 3-5 (stdlib / native / already-installed dep) match the project's hard "free-only, no paid APIs" architecture. Its bug-fix rule (grep every caller, fix at the shared function, not the path the ticket names) fits scraper breakage that hits sibling call paths. Two honest caveats for the dashboard phase: (1) ponytail explicitly says it governs what you build, not how it looks or talks, so it is NOT a design skill and will not help with the premium clinic-facing UI — pair it with a design skill; (2) its stdlib/native-first bias is actually aligned with the existing no-framework vanilla HTML/CSS/JS review page, but its "skipped X, add when Y" minimalism will fight a deliberately rich premium design unless the design is stated as explicitly requested, which the skill then honors. Also useful: the `ponytail:` comment convention (naming the ceiling and upgrade path) is what feeds ponytail-debt later.

### `/ponytail-review`  ·  _global_

A diff-scoped code review that hunts ONLY over-engineering — one line per finding giving location, what to cut, and what replaces it — ending with the single metric `net: -<N> lines possible.`

**Use when** — User says "review for over-engineering", "what can we delete", "is this over-engineered", "simplify review", or invokes /ponytail-review. Meant to complement, not replace, a correctness-focused review.

**Not for** — Correctness bugs, security holes, and performance are explicitly out of scope — route those to a normal review pass. It never applies fixes, only lists them. It also explicitly protects a single smoke test or assert-based self-check as "the ponytail minimum, not bloat" and says never flag it for deletion. Revert with "stop ponytail-review" or "normal mode".

**On this project** — High and immediately usable. The working tree has real modified diffs (config.py, modules/query_generator.py, modules/report.py, modules/storage.py, modules/vulnerability.py, modules/web_screens.py, requirements.txt, tests/test_query_generator.py) — this is exactly its input format. The `native:` and `stdlib:` tags map onto a scraping project that keeps adding requirements.txt lines, and the `yagni:` tag onto adapters/collectors with one caller. Note its output format is per-line tags (delete/stdlib/native/yagni/shrink), which is a review vocabulary, not a set of sub-commands. Caveat: because it deliberately ignores correctness and security, do not use it as the only review gate on scraper or Razorpay/payment-adjacent code.

### `/ponytail-audit`  ·  _global_

ponytail-review applied repo-wide instead of to a diff: scans the whole tree and returns a ranked list (biggest cut first) of what to delete, simplify, or replace with stdlib/native equivalents, ending with `net: -<N> lines, -<M> deps possible.`

**Use when** — User says "audit this codebase", "audit for over-engineering", "what can I delete from this repo", "find bloat", "ponytail-audit", or "/ponytail-audit". Its hunt list: deps the stdlib or platform already ships, single-implementation interfaces, factories with one product, wrappers that only delegate, files exporting one thing, dead flags and config, hand-rolled stdlib.

**Not for** — Same boundary as ponytail-review — over-engineering and complexity only; correctness bugs, security holes and performance are explicitly out of scope. One-shot report, applies nothing. "stop ponytail-audit" or "normal mode" to revert.

**On this project** — High, and arguably the single most applicable skill to this repo right now. The tree carries an archive/ directory, a torn-out UI layer (commit edf35eb "remove the UI layer"), two leftover handoff files (NEXT_SESSION_PROMPT.md, NEXT_SESSION_TASK.md), and a large batch of new untracked modules — precisely the dead-flexibility and wrapper-that-only-delegates surface it hunts. Running it before the dashboard phase starts would tell you what of the old pipeline/UI scaffolding to delete rather than port. Its `-<M> deps` metric also lines up with the project's free-only/no-paid-API constraint. Same caveat as ponytail-review: it will say nothing about whether the scrapers are correct.

### `/ponytail-debt`  ·  _global_

Greps the repo for `ponytail:` comment markers (the convention `ponytail: <ceiling>, <upgrade path>`) and harvests them into a debt ledger — one row per marker grouped by file — so deliberate shortcuts don't rot into "later means never".

**Use when** — User says "ponytail debt", "/ponytail-debt", "what did ponytail defer", "list the shortcuts", "ponytail ledger", or "what did we mark to do later". Scan command it documents: `grep -rnE '(#|//) ?ponytail:' .` skipping node_modules, .git and build output. Row format: `<file>:<line>, <what was simplified>. ceiling: <the limit named>. upgrade: <the trigger to revisit>.` Any marker with no upgrade path or trigger is tagged `no-trigger` as the rot risk. Ends with `<N> markers, <M> with no trigger.`; nothing found gives `No ponytail: debt. Clean ledger.`

**Not for** — Reads and reports only, changes nothing, one-shot. It will only write a file (e.g. PONYTAIL-DEBT.md) if you ask. Pointless before ponytail has actually been used to leave markers. "stop ponytail-debt" or "normal mode" to revert.

**On this project** — Low today, potentially useful later. I ran its documented grep pattern against E:\TRINADE\Dermat Analytics and Websites and found zero `ponytail:` markers — the ledger would come back "No ponytail: debt. Clean ledger." It only becomes worth invoking after ponytail has been running on this repo long enough to leave marked shortcuts, which is plausible for the scraper (rate-limit backoff, CAPTCHA handling, naive scoring heuristics in scoring_params.py are exactly the kind of known-ceiling corners it tracks). The SKILL.md also mentions `git blame -L<line>,<line>` as an optional per-row owner, which is single-author here and adds nothing.

### `/ponytail-gain`  ·  _global_

A one-shot ASCII scoreboard card showing ponytail's PUBLISHED BENCHMARK medians — lines of code 6-20% of no-skill (down 80-94%), cost 23-53% (down 47-77%), 3-6x faster — measured across 5 everyday tasks (email validator, debounce, CSV sum, countdown timer, rate limiter) on three models (Haiku, Sonnet, Opus).

**Use when** — User says "/ponytail-gain", "ponytail gain", "what does ponytail save", "show ponytail impact", or "ponytail scoreboard". Purely a display card.

**Not for** — It carries an explicit honesty boundary: these are benchmark medians, NOT this repo, and it must NEVER print a per-repo savings number ("you saved X lines/tokens here") because the unbuilt version was never written and there is no real baseline to subtract from in a live repo. It changes no mode, writes no flag files, persists nothing. It redirects per-repo questions to /ponytail-debt (a counted ledger) and /ponytail-audit (what's still cuttable).

**On this project** — Low. It is marketing/justification for the ponytail family, not a working tool — it reports numbers from the skill author's own benchmark suite and is explicitly forbidden from producing any Derma Intel-specific figure. Zero bearing on the scraping pipeline or the dashboard phase. The only practical use is deciding whether to adopt ponytail at all; after that, /ponytail-audit and /ponytail-debt are the ones with real repo signal. Note also that the frontmatter description in the skills listing is empty for this one, but the SKILL.md file itself is complete.

### `/ponytail-help`  ·  _global_

A one-shot quick-reference card listing all six ponytail skills, the three intensity levels, the deactivation phrases, and how to configure the default mode via env var or config file.

**Use when** — User says "/ponytail-help", "ponytail help", "what ponytail commands", or "how do I use ponytail". Display the card, do NOT change mode, write flag files, or persist anything.

**Not for** — Not a persistent mode and not a working tool — it only prints. Does not itself do any review, audit, or coding.

| Command | What it does | When |
|---|---|---|
| `/ponytail lite` | Build what's asked, name the lazier alternative in one line. | Listed in the card's Levels table. |
| `/ponytail` | Full — the ladder enforced: YAGNI to stdlib to native to one line to minimum. Default. | Listed in the card's Levels table; level sticks until changed or session end. |
| `/ponytail ultra` | YAGNI extremist, deletion before addition, challenges requirements before building. | Listed in the card's Levels table. |
| `/ponytail-review` | Over-engineering review of a diff, e.g. `L42: yagni: factory, one product. Inline.` | Listed in the card's Skills table. |
| `/ponytail-audit` | Whole-repo over-engineering audit: ranked list of what to delete. | Listed in the card's Skills table. |
| `/ponytail-debt` | Harvest `ponytail:` shortcut comments into a tracked ledger. | Listed in the card's Skills table. |
| `/ponytail-gain` | Measured-impact scoreboard: less code, less cost, more speed. | Listed in the card's Skills table. |
| `/ponytail-help` | This card itself. | Listed in the card's Skills table. |
| `/ponytail off` | Alternative deactivation alongside saying "stop ponytail" or "normal mode"; resume anytime with /ponytail. | Documented in the card's Deactivate section. |
| `PONYTAIL_DEFAULT_MODE env var` | Highest-priority default-mode override, e.g. `export PONYTAIL_DEFAULT_MODE=ultra`. Resolution order is env var > config file > full. | Documented in the card's Configure Default Mode section. |
| `~/.config/ponytail/config.json (Windows: %APPDATA%\ponytail\config.json)` | Config file setting `{ "defaultMode": "lite" }`; setting "off" disables auto-activation on session start so ponytail must be invoked manually. | Documented in the card's Configure Default Mode section — this is the Windows-relevant path on this machine. |

**On this project** — Low as a work tool, but it is the one file that documents the ponytail family's configuration surface, including the Windows config path %APPDATA%\ponytail\config.json and the fact that ponytail auto-activates at `full` every session unless configured off. That matters for this project: if ponytail is silently active by default it will bias every pipeline change toward the minimum diff, which is fine for scrapers and arguably wrong for the deliberately premium dashboard phase — so knowing how to set "off" or "lite" is the practical takeaway. The card also documents plugin auto-update via /plugin marketplace update ponytail, and the upstream repo github.com/DietrichGebert/ponytail.

### `/caveman`  ·  _global_

A persistent ultra-terse output style that drops articles, filler, pleasantries and hedging to cut response tokens ~65% (the SKILL.md's own measured claim) while keeping technical substance, code blocks and error strings verbatim.

**Use when** — User says "caveman mode", "talk like caveman", "use caveman", "less tokens", "be brief", or invokes /caveman; the file also says it auto-triggers whenever token efficiency is requested. Once on it stays ACTIVE EVERY RESPONSE until explicitly stopped.

**Not for** — The SKILL.md defines an "Auto-Clarity" carve-out: drop caveman for security warnings, irreversible-action confirmations, multi-step sequences where fragment order could be misread, cases where compression itself creates technical ambiguity, and when the user asks to clarify or repeats a question. Boundaries section: code, commits and PRs are written normally. Turn off with "stop caveman" or "normal mode".

| Command | What it does | When |
|---|---|---|
| `/caveman lite` | Removes filler and hedging but keeps articles and full sentences — "professional but tight". | When you want token savings without the telegraphic style, e.g. output another person will read. |
| `/caveman full` | Default level. Drops articles, allows fragments, short synonyms, no tool-call narration, no decorative tables/emoji, no long raw error-log dumps. Standard acronyms (DB/API/HTTP) OK; inventing abbreviations like cfg/impl/fn is banned because the tokenizer splits them anyway. | Default whenever caveman is on and no level is named. |
| `/caveman ultra` | Strips conjunctions when cause/effect stays unambiguous, one word when one word suffices, each fact stated once. Explicitly bans prose abbreviations and arrows (measured zero token saving). Code symbols, function names, API names and error strings are never touched. | Maximum compression on unambiguous technical answers. |
| `stop caveman / normal mode` | The only documented off switch; level otherwise persists until changed or session end. | When you want normal prose back. |
| `wenyan-lite / wenyan-full / wenyan-ultra` | Classical-Chinese compression levels. | Named in the SKILL.md intensity table, but NOT documented as slash arguments — ask for them in prose. |

**On this project** — Low-to-moderate, and orthogonal to the actual work. It changes only how I talk, not what gets built — the Boundaries section says code, commits and PRs are written normally, so it cannot corrupt Python modules or dashboard HTML. Its real value here is cost/latency on long pipeline sessions (this repo has ~20 untracked modules/*.py plus gmaps/ and api/ to reason about). It contributes nothing to the premium clinic-facing dashboard phase, and note the Auto-Clarity rule matters for this repo specifically: destructive steps (deleting runs from runstore, dropping scraped data) must be written in full prose, not fragments. Also note it preserves the user's dominant language, which is irrelevant here.


---

## MCP servers

Two are wired up. Unlike skills, an MCP is a live tool connection — its tools appear directly
in the tool list, so there is no `/command` to type.

### Stitch — `mcp__stitch__*`

Google Stitch: generates UI screens from a text prompt or a design system, then lets you edit
them and pull the result back out. Configured **project-local** in `.mcp.json`, authenticating
with `${STITCH_API_KEY}` read from the gitignored `.env` — the key is never committed.

| Tool | Use it for |
|---|---|
| `create_project`, `get_project`, `list_projects`, `delete_project` | Managing a Stitch project |
| `generate_screen_from_text` | Turning a written screen brief into a comp |
| `generate_variants` | Several takes on the same screen |
| `edit_screens`, `get_screen`, `list_screens` | Iterating on generated screens |
| `create_design_system`, `create_design_system_from_design_md`, `apply_design_system`, `update_design_system`, `list_design_systems` | Locking a house style so every screen matches |
| `upload_design_md` | Feeding an existing DESIGN.md in |

**Use when** — you want screen comps fast for the clinic dashboard or a marketing page, and
you would rather react to a picture than a blank editor. Pair with `/stitch-skill`, which
writes the DESIGN.md that `create_design_system_from_design_md` consumes.

**Not for** — production code. Stitch output is a starting point; the real implementation
still has to be built and held to the design references in `design/`.

### Higgsfield — image / video / audio generation

Connected as a hosted connector (its tools are live in-session; there is no local config file
to edit). Generates images, video, audio and 3D from prompts, plus editing tools.

| Tool | Use it for |
|---|---|
| `generate_image`, `generate_image_batch` | Design references, hero imagery, illustration |
| `generate_video`, `generate_video_batch` | Demo / explainer / launch video |
| `generate_audio`, `create_voice`, `dubbing` | Voice-over |
| `upscale_image`, `outpaint_image`, `remove_background`, `reframe` | Fixing an existing asset instead of regenerating |
| `models_explore` | Ask which model fits before generating |

**Use when** — the design skills call for reference imagery you do not have.
`/imagegen-frontend-web` and `/image-to-code-skill` both assume image generation is available;
Higgsfield is what satisfies that.

**Not for** — anything that must depict a real clinic. Every clinic name, rating and review in
this project is measured data; a generated image of a clinic would be a fabrication sitting
next to real evidence. Use it for abstract, brand and UI imagery only.

---

## Requested but not installable as a skill

**`abi/screenshot-to-code`** — cloned to `.claude/.skill-sources/screenshot-to-code`, but it is
a **web application** (React frontend + Python backend + `docker-compose.yml`), not a skill: it
ships no `SKILL.md` and there is nothing for the `Skill` tool to load. Run it as an app if you
want it, or use `/image-to-code-skill` (installed, global), which is the same idea as a skill.

**`headroomlabs-ai/headroom`** — already present as an MCP (`mcp__headroom__compress`,
`__retrieve`, `__stats`) rather than a skill, so nothing needed installing.
