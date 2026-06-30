# Content & Structure Spec — Two Views (Phase 11)

**Date:** 2026-06-30 · Companion to [PREMIUM_REDESIGN_BRIEF.md](PREMIUM_REDESIGN_BRIEF.md).
This is the **content/feature** definition (what each view says + which payload fields feed it). The
**visual** session owns look/motion. The Python content engine is **built, wired, and tested** (135
pytest green) — every field below is already in the `build_web.py` payload.

## The product: one dataset, two clearly separated views
- **① "Your Clinic" report (primary — conversion).** A doctor sees *their own* standing: how findable
  they are, the proof, the gaps, and the fix. Default landing; pick-your-clinic (or one report per clinic).
- **② "The Market" dashboard (secondary — motivation).** Where they rank vs all 34 Guntur clinics — the
  comparative pressure that makes them act.
Keep them **separate** (two tabs/screens or two well-divided sections). Lead with ①; ② is "see the rest
of the market." Never blend the doctor's own report into a competitor leaderboard.

## Golden rule on scores
- **Doctor-facing = `visibility` (0–100, higher = better)** + `visibility_rank` ("you rank #26 of 34").
- The internal **`score`/opportunity** (higher = weaker = better sales prospect) is a **seller** metric —
  do **not** show it raw to doctors. Use it only in an internal/seller mode, if at all.

## Payload contract (already available per clinic)
`visibility` · `visibility_rank` · `visibility_total` · `verdict` (one plain line) ·
`web {owned, borrowed, appearances, has_own_site, in_places, platforms[]}` ·
`scorecard[ {key,label,status: good|warn|bad,value,note} ]` (website · search · maps · reviews · phone) ·
`benchmarks[ {key,label,you,market,better} ]` (reviews · rating · demand) ·
`proof {query, screenshot, strength, present[]}` (highest-demand search where the clinic is **absent**;
`present` = who shows up instead) · plus existing `name, display_name, rating, reviews, appearances,
has_website, website, phone, address, place_url, nlp`.
Top level: `payload.market { total, no_website, no_website_pct, zero_web_presence, own_site, avg_rating,
avg_reviews }`, `payload.kpis`, `payload.categories`, `payload.rating_distribution`.

---

## VIEW ① "Your Clinic" report — persuasion arc: You → Proof → Why → Gap → Fix → CTA

1. **Hero / verdict.** *"Dr. {name}, here's how patients find you online in Guntur."* Show the big
   **Online Visibility {visibility}/100** and **rank #{visibility_rank} of {visibility_total}**, then the
   `verdict` line. (e.g. Keerthi: 10/100, #28 — "Almost no online presence.")
2. **Scorecard** (the glance). Render `scorecard[]` as 5 rows with a good/warn/bad mark, `label`, `value`,
   `note`. This is the instant diagnosis: Website ✗ · Google search ✗ · Maps ✓ · Reviews ⚠ · Phone ✓.
3. **Proof** (the gut-punch). "What patients actually see." Use `proof`: *"When patients search
   **{proof.query}**, your clinic doesn't appear — instead they find {proof.present joined}."* Show the
   real screenshot (`data/Full Page Screenshots/{proof.screenshot}`). The visual session decides how to
   embed (cropped top-of-page / tile); keep it offline. This single element converts skeptics.
4. **Why it matters** (context, 2 captions): everyone's well-rated (`avg_rating` 4.84) → reputation isn't
   the lever, **presence** is; patients are searching a lot (demand). Pulls from `payload.market` + benchmarks.
5. **You vs the market** (`benchmarks[]`): Reviews 258 vs 306 · Rating 4.9 vs 4.84 ✓ · Shows in 9 vs 14.5
   searches. Plain "you / market / better?" rows. Comparison creates urgency without naming rivals.
6. **What you'd fix → CTA.** Turn each failing scorecard check into a service line:
   no website → *"We build you a fast, professional website"*; not in search → *"We get you ranking for
   the searches your patients use"*; reviews below avg → *"A simple review system."* End with a clear CTA
   ("See my full report" / "Book a 15-min walkthrough" / "Build my website") — **replace** the current
   "View on Google Maps"/phone buttons (those are seller tools).

## VIEW ② "The Market" dashboard — where you stand vs everyone

1. **Headline stats** (`payload.market`): *"34 clinics · 15 are invisible in Google web search · only 10
   rank their own site."* Lead with the web-invisibility stat (substantiates "invisible online").
2. **Visibility league** — clinics ranked by `visibility` (higher=better), the doctor's row highlighted
   ("You — #26"). This is the motivating mirror of today's "approach first" list, flipped positive.
3. **Two simple, captioned charts** (cut the rest):
   - **Website coverage** (donut, `market.no_website`): caption *"Half of Guntur skin clinics have no
     website — patients find Practo or a competitor instead."*
   - **What patients search for** (the `categories` bar, relabel): *"~80 searches a month — every one a
     patient you could be the answer to."*
   Optional **"You are here"** 2×2 (Demand × Online presence) with one dot = the clinic.
4. **Cut from the doctor-facing product** (keep only in an internal seller mode): the demand-vs-reviews
   **scatter**, the **rating histogram** (replace with the one-line "everyone's 4.8★" point), and the raw
   **34-clinic table**. They're analyst tools, not doctor persuasion.

## Copy: plain-language swaps (apply throughout)
opportunity/Critical → **Online Visibility 14/100**; "appears in 9/80" → **"shows in 9 of 80 patient
searches"**; "high-intent share" → **"patients ready to book"**; "No / weaker website" → **"No website"**;
"owned/borrowed" (never shown) → **"your site ranks" / "found only via Practo, JustDial."**

## Trust builders
- One plain method line: *"We searched 80 real patient queries on Google and recorded who showed up —
  Google Maps & Search, June 2026."*
- Only real, sourced numbers (no invented revenue). The SERP screenshot is the proof.
- Lead the patient-voice (`nlp`) with what patients **praise**, then one pain point.
