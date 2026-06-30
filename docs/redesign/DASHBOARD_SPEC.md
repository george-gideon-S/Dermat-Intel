# Three-View Dashboard — Structure & Content Spec (Phase 11 rough sketch)

**Date:** 2026-06-30 · **Status:** approved page-by-page (doctor + analyst + designer brainstorm) ·
Companion: [CONTENT_SPEC.md](CONTENT_SPEC.md) (engine/payload), [PREMIUM_REDESIGN_BRIEF.md](PREMIUM_REDESIGN_BRIEF.md) (visual phase).

## What this is
A **three-part experience** for selling Derma Intel to Guntur dermatologists: a **Home** entry, a
**"Your Clinic"** personalized report (primary/conversion), and an **"All Clinics"** market view
(secondary/motivation). This spec is **structure + content + copy + charts** only — **build it rough; the
parallel session polishes the visual design + motion.** The data engine + payload are already built and
tested (135 pytest green); every field used below already exists in the payload (one small addition noted).

## The job (synthesis of the three lenses)
The product's real job is to **manufacture a trustworthy moment of recognition** — *"patients genuinely
can't find me"* — and **immediately offer a way out.** Every screen serves it three ways:
- **Doctor** (buyer): plain, personal, proof-driven, ends in a clear next step. No jargon, never insulting.
- **Analyst** (credibility): transparent method/sample/date; honest proxies; context (median + spread,
  percentile); fair comparison (peers/locality). **Rigor lives one layer down** (expanders/tooltips), so
  the surface stays simple.
- **Designer** (comprehension): one message per screen; progressive disclosure; few, captioned,
  comparable charts; one CTA; guided, optional onboarding.

Guiding rule: a chart that doesn't advance the recognition→action moment is decoration — cut it.

## Shell & navigation
Left **sidebar** (units-style colored boxes): brand/logo = **Home** (entry); two prominent tab boxes
**① Your Clinic** and **② All Clinics** = the dashboard views; a **◇ Take the tour** control. Simple JS
router (`state.view ∈ {home, clinic, market}`, `state.clinicKey`); re-render `#app` on change. The picked
clinic persists across tabs (so All Clinics keeps the "You" anchor).

## Scores — the golden rule
Doctors see **`visibility` (0–100, higher = better)** + rank/percentile. The internal **opportunity
`score`** (higher = weaker prospect) is **seller-only** — never shown raw to a doctor.

---

## PAGE 1 — HOME (frame the decision, earn trust, route)
**Single message:** *"What this is, why you can trust it, and your door in."*
1. **Hero** — H1 *"Your patients are searching. Can they find you?"*; sub explains the product; buttons
   **See your clinic →** (primary) · **Explore the market**.
2. **Trust strip** — *"80 real patient searches · Google Maps + Search · 34 clinics · June 2026,"* source
   chips, inline **"What we can & can't claim"** expander (snapshot; searches = demand *proxy*).
3. **3 big facts** — **34** clinics · **15** invisible in Google search · only **10** rank their own site
   (`market.total / zero_web_presence / own_site`).
4. **Proof teaser** — a real SERP screenshot + *"This is the page patients get. Is your clinic on it?"* →
   Check your clinic.
5. **Two doors** — cards mirroring the sidebar boxes (① personal report / ② market).
6. **How it works** — *1 pick · 2 see proof · 3 get fixes.*
**Charts:** none (landing). **Onboarding:** tour step 1 points at the two doors.

## PAGE 2 — YOUR CLINIC (primary; arc: You → Proof → Why → Gap → Fix)
**Single message:** *"Where you stand online, proof you can't argue with, and what to fix first."*
0. **Selector** — searchable; defaults to a high-opportunity **example** with hint *"Example — pick yours."*
1. **Headline** — name · area; big **Visibility N/100**; **Rank #r/34** + percentile (*"lower than 8 in 10
   clinics"*); **verdict** line. Chart **#1 position marker**.
2. **Scorecard** — 5 point-wise cards (Website · Search · Maps · Reviews · Phone): status colour + value +
   plain note (`scorecard[]`).
3. **SERP proof** — real screenshot + *"Search '{proof.query}' — you're not here. Patients find
   {proof.present}."* + **visibility-leak** line *80 searches → appear in {web.appearances} → own site in
   {web.owned}.*
4. **You vs market + peers** — Chart **#2**: normalized bars (Reviews · Rating · Demand) vs market baseline,
   **and vs "clinics like you"** (peer group = clinics in a comparable **review band**, computed
   client-side; area as an optional refinement).
5. **Visibility breakdown** — Chart **#3**: the 6 components (Website/Search/Maps/Reviews/Phone/Breadth)
   **earned vs gap**; the gaps map 1:1 to the fixes. Sourced from a new `visibility_breakdown` (below).
6. **Patient voice** — praise chips → top pain → 70% positive → referral/recency (`nlp`, if present).
7. **What to fix → CTA** — ranked fixes from failing checks, each: action + why + **estimated lift**
   (*"+30 visibility"*); optional **what-if** (*"top 2 → ~55, rank ~#12, estimated"*); one CTA.
8. **Method (collapsed)** — "checked across 78 searches · June 2026" + caveats.
**Charts (3):** position marker · you-vs-market(+peer) bars · visibility breakdown — plus proof screenshot,
leak funnel, patient-voice mini-bar. **Onboarding:** steps 2–6 (selector → score → scorecard → proof → fix).

## PAGE 3 — ALL CLINICS (motivation; "where everyone stands & where you fit")
**Single message:** *"The whole market — and your place in it."*
1. **Summary** — *34 clinics · 15 invisible (44%) · 10 own-site · median rating ~4.9★ · reviews: show the
   **median + range**, noting the 306 **mean** is skewed by a few large chains* + persistent **"You"** chip
   (carried selection). Median + spread, not bare means.
2. **Visibility league** — Chart **#1**: all 34 ranked by visibility, **your row highlighted**, median line.
3. **Demand × Visibility** — Chart **#2**: annotated quadrant (x = searches-shown-in = demand *proxy*, y =
   visibility), your dot highlighted, median crosshairs, quadrant labels (*"high demand · low visibility =
   biggest upside"*).
4. **How clinics get found** — Chart **#3**: stacked bar (own site / only via Practo-JustDial / invisible).
   Folds in the old website donut.
5. **What patients search** — Chart **#4**: category bar (`categories`).
6. **Table** — all 34, sortable; Clinic · Visibility · Rank · Website · Own-site · **Found via** · Reviews ·
   ★ · Searches; your row highlighted; row ▸ expands → snapshot + **"Open full report"** → jumps to ① with
   that clinic.
7. **Area filter** — group/filter by locality parsed from `address` (light; degrade gracefully).
8. **Caveats + method** — collapsed footnote (proxy demand, single snapshot, coverage, June 2026).
**Onboarding:** final step (league → upside corner).

## Onboarding tour (short · optional · contextual · dismissible)
Spotlight overlay + callout, one element at a time, Next/Skip, `localStorage` "seen" flag, re-triggerable
via **◇ Take the tour**. ~6 stops on *meaningful* things only (never obvious UI): two doors → clinic
selector → Visibility score+rank → scorecard → **SERP proof** → All-Clinics league. Switches view as needed.

## Data contract
All views render from the **existing payload** (`clinics[]` with `visibility, visibility_rank/total, web
{owned,borrowed,appearances,has_own_site,in_places,platforms}, scorecard[], benchmarks[], verdict, proof,
nlp`; plus `market`, `categories`, `median_appearances`). Derived **client-side** from it: percentile,
peer group (review band / area), area/locality (parsed from `address`), what-if lift, league/quadrant/
stacked/category series. **One Python addition** (single-source the score formula, TDD): `report.
visibility_breakdown(c, market) -> [{component, earned, max}]`, surfaced per clinic in the payload — so the
breakdown chart + what-if reuse the engine instead of re-implementing weights in JS.

## Build approach (rough sketch)
Rewrite `web/template.html` (shell), `web/app.js` (router + sidebar + 3 views + tour), `web/styles.css`
(rough, reuse `:root` tokens; premium CSS preserved in git history). Charts via the vendored ECharts.
Add `visibility_breakdown` to `report.py` (TDD) + payload. Keep `modules/` correctness + the 135 tests
green; QA the sketch with a Playwright screenshot. **Out of scope (rough):** visual polish, GSAP motion,
final copy, PDF leave-behind, "your twin"/neighborhood-deep features, animated patient's-eye walkthrough
(the proof is a static screenshot for now). These are Phase-11 / later.
