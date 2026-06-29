# Design — Derma Intel

The product, visual, and scoring design decisions. See [ARCHITECTURE.md](ARCHITECTURE.md) for how it's
wired and [docs/redesign/REDESIGN.md](docs/redesign/REDESIGN.md) for the original audit of the Streamlit
version that motivated the premium web UI.

## Product framing
The dashboard answers one question first: **"Which clinics have the most untapped opportunity, and
why?"** It's being positioned to **sell to clinics** ("here's where you stand vs. the Guntur market and
what to fix"), so the language is **opportunity/diagnostic, never accusatory** — the score is shown as an
"opportunity score," gaps are paired with the demand/reach that makes fixing them worthwhile.

## Visual system — "Quiet Precision"
Refined editorial minimalism (Apple-level restraint), deliberately distinct from the old dark Streamlit.
- **Theme:** warm-paper light surface (`#FAFAF7`), white panels, deep warm ink (`#16150F`), hairline
  borders, soft low-spread shadows. Subtle glass only on the sticky header.
- **Accent:** a single clinical **teal** (`#0F766E`). Opportunity intensity uses a **calm sand→clay**
  sequential (`#D9CDB4 → #D8B36A → #C8843F → #A6502A`) — premium, not alarmist red.
- **Type:** **Geist Sans** (UI/body) + **Geist Mono** (all numerals/labels, tabular figures). Vendored
  (base64-inlined) for offline use; distinctive, professional, not Inter/Roboto/system.
- **Space/motion:** 8px scale, generous section rhythm; one orchestrated staggered page-load
  (fade+rise); restrained hover states; ECharts entrance easing. No decorative animation.
- Self-contained: ECharts + fonts + data + CSS + JS all inlined into one `.html` (works on `file://`,
  offline, no server — which also removed the earlier "localhost is down" fragility).

## Information architecture (answer-first narrative)
Top-to-bottom scroll, most-important-first (the old Streamlit buried the payload in the last tab):
1. **Hero + KPIs** — headline ("Trusted in person, invisible online.") + 4 mono KPIs (unique clinics,
   no/weaker website, avg rating, average reviews).
2. **The opportunity** — ranked top-10 clinics with inline score bars + a linked detail panel
   (stats, the auto-written opportunity note, and the **"Patient voice"** review-NLP block).
3. **Competitive landscape** — demand-vs-reputation scatter, coloured by has-website; the clay
   cluster (in-demand, no website) is the visible opportunity.
4. **Market composition** — website-gap donut, search-demand-by-intent bar, rating-distribution
   histogram (shows reputation is uniformly high → presence is the lever).
5. **Explore** — searchable/sortable table of all clinics.

## Chart rationale (curated, not decorative)
Cut from 14 near-equal charts to **4 decision charts + 2 reading aids**, each tied to a question:
opportunity rows ("who first?"), landscape scatter ("where does demand meet weak presence?"),
website-gap donut ("how big is the gap?"), demand-by-intent bar ("what do people search?"),
rating histogram ("is rating a differentiator? — no"), KPI strip ("state in 5 seconds"). Removed
redundant/low-value charts (duplicate appearance bars, box-plot, treemap, heatmap, raw map).

## Scoring design — opportunity = weakness × value
The score deliberately fuses two ideas, because in a uniformly well-rated market (Guntur avg 4.84★)
pure "weakness" doesn't discriminate:
- **GAP (online-presence weakness, 58 pts, binary):** no/weaker website 22, buried in search 12,
  few reviews (below market avg) 10, weak rating (<4.8) 8, no phone 6.
- **REACH (value at stake, 42 pts, continuous):** demand 16 (more search appearances = bigger prize —
  **deliberately flipped** from an earlier "low-demand = vulnerable" rule), high-intent 14 (share of
  Pricing/Booking/Near-Me searches = ready-to-book patients), central location 12 (denser catchment).
- **Operational gate:** closed clinics ×0.4 (you can't sell to a closed business).
- **Blend:** final = 0.6 × Maps + 0.4 × Google-web relevance (web = how invisible the clinic is in
  normal web search; activates once web data is collected).
- **Bands:** Critical 80+, High 60–79, Medium 40–59, Low 0–39.

Calibration history: thresholds were tuned for this market (rating <4.8 since the average is 4.8;
few-reviews uses the market **average**; demand <20-of-50 reframed as continuous upside). See
SESSION_LOG.md.

## Review intelligence ("Patient voice")
Free offline NLP (VADER + keyword aspect buckets) surfaces, per clinic: sentiment split, **what
patients praise**, **pain points**, **word-of-mouth / referral rate**, and review recency. This is the
clinic-facing selling depth ("here's what your patients actually say") and the basis for a future
word-of-mouth scoring factor — the data-driven proxy for the offline-reputation dynamic that matters
for Guntur's word-of-mouth-driven (esp. older) patients.

## Principles to preserve
Restraint over decoration · insight density over chart count · one coherent chart aesthetic · honest
empty/loading states · the calm (non-alarmist) palette · answer-first ordering · everything offline and
free.
