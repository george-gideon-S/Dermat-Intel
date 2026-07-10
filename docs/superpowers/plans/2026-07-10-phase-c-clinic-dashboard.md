# Phase C — "Your Clinic" Dashboard (private dist → v2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or
> superpowers:executing-plans. **This session:** executing inline.

**Goal:** The paid report app in the v2 system: private dist becomes a clean two-tab report
(Your Clinic / The Market) with the deeper clinic-view charts from spec §5. The old scroll
story leaves the private bundle (the public page owns marketing now).

**Architecture:** `build()` re-renders `template.html` (rewritten, v2) with tokens-v2 +
components + rewritten `styles.css`; bundle = ECharts + payload + `app.js` only (GSAP,
Bricolage, shell.js, story.js dropped — files deleted; git history keeps them). `app.js`
keeps its render structure; clinic view upgraded, market view recolored (Phase D redoes it).

**Spec:** 2026-07-10 spec §5 "Your Clinic". **Tests:** new TDD for the intent-positions
payload helper; suite stays green (Streamlit smoke tests are unaffected).

---

### Task 1: Intent-positions payload (TDD)

**Files:** Modify `web/build_web.py` · Test `tests/test_intent_positions.py`

- [ ] Pure helper in build_web:

```python
def intent_positions(ok_rows, qrows, key_of) -> dict:
    """Per clinic-key: [{cat, pos (avg, 1dp), n}] for categories it appears in,
    plus '_market': {cat: median_avg_pos} across clinics. Query->category via qrows."""
```

  Tests: fixture 2 clinics × 3 queries/2 categories; assert avg positions, category mapping,
  market medians, missing-category omitted.
- [ ] Wire into `build_payload()`: each clinic dict gains `intents`; payload gains
  `intents_market`. Commit.

### Task 2: v2 private shell

**Files:** Rewrite `web/template.html`, `web/styles.css` · Modify `build()` · Delete
`web/shell.js`, `web/story.js`

- [ ] template.html: v2 head (canvas theme), static glass topbar (wordmark + two pill-tab
  nav buttons + "report for" select slot rendered by app.js), `<main id="app">`, scripts:
  echarts → data → app → `DI.renderApp("clinic")`. No GSAP/story/shell placeholders.
- [ ] styles.css rewritten: app layout on tokens (appmain grid, cards, section rhythm,
  scorecard pill rows, dumbbell rows, proof frame, table, chips) — no raw hex beyond tokens.
- [ ] build(): fonts → v2 list (shared `_FONTS_V2`), inline tokens-v2 + components + styles;
  drop `{{GSAP}}/{{SHELL_JS}}/{{STORY_JS}}`. `derma_web.py` opener unchanged
  (`dist/derma_intel.html` still written). Commit.

### Task 3: Clinic view upgrade (app.js)

- [ ] Color object → v2: ink #131417, ink-3 #9FA3A9, line rgba(19,20,23,.10); categorical =
  triad deep stops [growth #2E9E44, status-slate #97A2B2, alert #EE6D96] + ink for "you";
  magnitude = intensity of one hue; tooltip = glass-pill style.
- [ ] Hero → `.grain-card--status`: Doto visibility score + "/100", rank + percentile line,
  `.ruler` with marker at score%, verdict beneath on canvas.
- [ ] 5-check scorecard → `.pill-tab`-style rows: label + value + trailing status chip
  (good=lime chip · warn=mono chip · miss=alert-tint chip).
- [ ] "You vs market" → DOM **dumbbell rows** (reviews / rating / demand): market dot (ink-3)
  vs you dot (ink) on a ruler track, mono values at ends; peers line kept as caption.
- [ ] NEW **"Where you rank, by what patients want"** — intent-positions dot strip: per
  category row, x = avg SERP/Maps position (1 best, log-ish scale), you-dot (ink) vs market
  median tick; categories you never appear in render as ghost "not seen" rows (the sell).
- [ ] Breakdown chart: keep stacked earned/gap, recolor (earned = growth deep, gap =
  rgba-ink .07). Patient voice: sentiment strip (pos% growth / neg% alert on one bar),
  theme chips (lime-tint good / alert-tint pains), referral + recency line in mono.
- [ ] Fix-first: rec rows + lift chips (+N in Doto small), what-if line, CTAs → WhatsApp
  links from `D.pricing`? (private payload has no pricing — CTAs become plain
  "Book the walkthrough" buttons wired to `wa.me` only if configured at build; else static).
  Method details kept. Commit.

### Task 4: Market view minimal v2 (full redo = Phase D)

- [ ] Recolor charts via the shared C object; stats row → dot-num KPIs; table pills → v2
  chips; "you" highlight = ink + lime dot. No structural change. Commit.

### Task 5: Build + QA + wiring

- [ ] `python web/build_web.py` (private) — screenshots: clinic view (hero/scorecard/
  dumbbells/intents/voice/fixes), market view, selector switch, console clean, reduced OK.
- [ ] `python -m pytest -q` green. CLAUDE.md front-ends section updated (story retired from
  private; public page owns marketing). Memory. Commit.
