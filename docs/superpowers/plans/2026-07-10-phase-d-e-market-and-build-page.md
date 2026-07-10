# Phases D + E — Market Deep Charts & Build-with-Trinade Page

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or
> superpowers:executing-plans. **This session:** executing inline.

**Goal:** D — "The Market" tab becomes the data-rich half of the paid report (spec §5).
E — the treatment-tier landing page ships in the public dist (spec §6).

**Doctrine reminders:** categorical = triad deep stops (≤4 hues) + ink for "you" ·
magnitude = intensity ramp of ONE hue · tooltips = glass pill · hero numerals Doto ·
alarm-red does not exist.

---

### Task D1: Market view rebuild (`web/app.js` marketView/marketCharts + `styles.css`)

Layout: stats → **Opportunity map** (full-width money chart) → grid2 [league | beeswarm +
review-landscape] → grid2 [owned-vs-borrowed butterfly | one-dot-per-clinic waffle +
categories] → **intent × clinic heatmap** → table with spark-bars.

- [ ] **Opportunity map upgrade** (ch-quad, h≈420): bubble size = √reviews (clamp 8–26);
  color job: invisible = alert rose, visible = slate, you = ink + lime border; median
  crosshairs; quadrant caption labels via `graphic` ("high demand · low visibility — the
  opportunity corner").
- [ ] **Score beeswarm** (ch-swarm): x = visibility 0–100, y = deterministic jitter
  (name-hash), slate dots, you = ink/lime; hidden y-axis; names in tooltip.
- [ ] **Review landscape** (ch-trust): x = reviews, y = rating (≥3.5), bubble = demand,
  same color job as the map.
- [ ] **Butterfly** (ch-owned): clinics with any web signal, owned ← (growth, negative axis)
  vs borrowed → (orange); abs-value axis labels; replaces the single stacked bar.
- [ ] **Waffle** (DOM): one dot per clinic — growth = ranks own site, slate = directories
  only, alert = invisible; title = clinic name; legend chips. The public page's dot motif,
  now with names.
- [ ] **Heatmap** (ch-heat): x = top-12 clinics by visibility, y = intent categories,
  value = avg position; visualMap = ONE-hue intensity (deep growth at #1 → faint);
  blank cell = not seen.
- [ ] **Table spark-bars**: Vis column gets an inline bar (`.spark > i` width = vis%).
- [ ] Playwright QA + commit.

### Task E1: Build-with-Trinade page (public dist)

**Files:** Create `web/template-build.html` · Modify `web/build_web.py` (`build_public()`
also emits `dist/public/build.html`) · Modify `web/story2.js` (offer build-card CTA →
`build.html`; WhatsApp becomes the page's job)

- [ ] Page (static, self-contained, v2, no GSAP/ECharts): topbar (wordmark → `index.html`) ·
  grain-STATUS hero ("The treatment · Website + Visibility Build · from ₹49,999" with Doto
  price + FCFS slots line) · "how it works" 3 steps (examination fee credited ≤90 days →
  build → optional retainer ₹4,999/mo) · **request form** (name, clinic, phone, current
  site?, goals textarea) → primary **"Send via WhatsApp"** (wa.me prefilled composed
  message; hidden if no number) + **"Copy request"** clipboard fallback · honest-scarcity
  copy, zero fake urgency · footer.
- [ ] Placeholders `{{STYLES}} {{DATA}} {{BUILD_JS}}` (inline JS in template is fine —
  compose message, clipboard). DATA = pricing only (no clinic data → leak-safe by
  construction; still passes through the scan surfaces).
- [ ] build_public(): render + write `build.html`; vercel cleanUrls serves `/build`.
- [ ] story2.js offer card: "Request a consultation" → `build.html`.
- [ ] Playwright QA (form → wa.me href correct, clipboard fallback, console clean) ·
  rebuild public · full pytest · CLAUDE.md row (public dist = home + build page) · memory ·
  commit.
