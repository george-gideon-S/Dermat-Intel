# Phase B — Public Home Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or
> superpowers:executing-plans. Steps use checkbox syntax.
> **This session:** executing inline (design-taste work; Phase A context in-session).

**Goal:** Ship the public sales home — six-act GSAP narrative → personalized liquid-glass gate →
diagnostic-ladder pricing — as a separate anonymized dist, leaving the private dist untouched.

**Architecture:** `build_web.py` gains `build_public()`: full payload → `web/public_data.py`
(pure, TDD'd anonymizer) → render `web/template-public.html` with tokens-v2 + components +
`web/public.css` + `web/story2.js` + GSAP + liquid-glass + Doto. Output `web/dist/public/`
(index.html + vercel.json). **No ECharts in the public bundle** (acts use DOM+GSAP). Private
dist (`dist/index.html` etc.) unchanged this phase.

**Tech Stack:** Python 3.10 + pytest (payload logic) · vanilla JS + GSAP ScrollTrigger/SplitText
(vendored) · liquid-glass.js · tokens-v2/components.css · Playwright QA.

**Spec:** `docs/superpowers/specs/2026-07-10-phase11-luminous-precision-redesign-design.md` §3–§4.

---

### Task 1: Foundations — config, liquid-glass vendor, web package

**Files:** Modify `config.py` · Create `web/__init__.py` (empty) · Copy
`~/.claude/skills/liquid-glass/liquid-glass.js` → `web/vendor/liquid-glass.js`

- [ ] Append to `config.py` (public URLs/prices — NOT secrets; George fills links from his
  Razorpay dashboard; empty string ⇒ CTA falls back to WhatsApp; empty WhatsApp ⇒ tel/plain note):

```python
# --- Go-to-market (public links & prices; not secrets — see spec §1 decisions) ---
PRICE_REPORT = 4999          # Visibility Report (one-time "examination")
PRICE_MONITOR_QTR = 2999     # Monitoring, per quarter (anchor)
PRICE_MONITOR_YR = 9999      # Monitoring, per year (hero of tier 2)
PRICE_BUILD_FROM = 49999     # Website + Visibility Build, "from"
PRICE_RETAINER_MO = 4999     # Growth Retainer, per month
RAZORPAY_LINK_REPORT = ""      # e.g. https://rzp.io/l/...
RAZORPAY_LINK_MONITOR_QTR = ""
RAZORPAY_LINK_MONITOR_YR = ""
WHATSAPP_NUMBER = ""           # E.164 digits only, e.g. "919999999999"
PUBLIC_SALT = "derma-intel-2026"  # hash salt for the public self-lookup (obfuscation, not security)
```

- [ ] Copy liquid-glass.js; commit `chore(web): vendor liquid-glass + go-to-market config`.

### Task 2: `web/public_data.py` — TDD'd anonymizer (the privacy mechanism)

**Files:** Create `web/public_data.py` · Test `tests/test_public_data.py`

Pure functions; input = the full `build_payload()` dict; output = the public payload.
**Invariant: no real clinic name, exact review count, exact score, or website URL survives.**

- [ ] Write failing tests first (fixture = minimal fake full-payload with 4 clinics), then implement:

```python
FNV = 2166136261; PRIME = 16777619
def fnv1a(s: str) -> int:                      # mirrors JS: Math.imul(h ^ c, PRIME) >>> 0
    h = FNV
    for ch in s: h = ((h ^ ord(ch)) * PRIME) & 0xFFFFFFFF
    return h

STOP = {"clinic","clinics","skin","hair","care","dr","doctor","the","and","centre","center",
        "hospital","derma","dermatology","dermatologist","cosmetic","laser","guntur"}
def name_tokens(name: str) -> list[str]:      # distinctive, normalized tokens
    toks = re.findall(r"[a-z0-9]+", (name or "").lower())
    return [t for t in toks if len(t) >= 3 and t not in STOP]

def rank_bucket(rank: int, total: int) -> str:  # visibility rank, higher=better product framing
    return "top 10" if rank <= 10 else ("11–20" if rank <= 20 else f"21–{total}")

def reviews_band(n):  # bands only — exact counts identify clinics via Google Maps
    return "200+" if n >= 200 else "100+" if n >= 100 else "50+" if n >= 50 else "under 50"
def rating_band(r):  return f"{math.floor(r*2)/2:.1f}+" if r else None
```

  `build_public_payload(full, salt)` returns:
  - `kpis` (aggregates verbatim: queries, unique_clinics, no_website_count, avg_rating, pct_with_website)
  - `beeswarm`: per clinic `{x, y, inv}` — x = demand percentile 4–96, y = `fnv1a(name+salt) % 61 - 30`,
    `inv = not has_website`. No names.
  - `lookup`: per clinic `{h: fnv1a(norm_full_name+salt), t: [fnv1a(tok+salt)...], inv, bucket}`
  - `teasers`: top-3 invisible by appearances → `{letter (A/B/C by teaser order — decoupled from rank),
    rating_band, reviews_band, demand: "high"|"steady" (vs median)}`
  - `queries`: ≤8 sample query strings, none containing any clinic's distinctive token
  - `owned_borrowed`: aggregate counts {owned_only, borrowed_only, both, invisible}
  - `pricing`: from config (prices, links, whatsapp)
  - `generated_at`, `city`
- [ ] Invariant tests: serialize public payload → assert no distinctive token of any fixture clinic
  name appears; assert no `"reviews":` exact ints; assert fnv1a test vectors match JS
  (`fnv1a("abc") == 1134309195`, verify by hand-running the JS algorithm once in Playwright eval).
- [ ] `python -m pytest tests/test_public_data.py -q` green → commit.

### Task 3: `build_public()` in build_web.py

**Files:** Modify `web/build_web.py` · Test `tests/test_public_data.py::test_build_public_smoke`

- [ ] `_FONTS_PUBLIC` = Geist 400/500/600/700 + Geist Mono 400/500 + `("Doto", "100 900", "doto-var.woff2")`
  (extend `_font_face_css` to accept a fonts list param; default stays `_FONTS`).
- [ ] `build_public()`: full payload → `public_data.build_public_payload` → template-public
  placeholders `{{STYLES}} {{GSAP}} {{LIQUID_GLASS}} {{DATA}} {{STORY2_JS}}` → write
  `dist/public/index.html` + `vercel.json`. STYLES = fonts + tokens-v2.css + components.css +
  public.css (read from `docs/redesign/v2/`).
- [ ] **Leak tripwire in the build:** after render, for every clinic in the FULL payload assert no
  distinctive name token (>3 chars) appears in the public HTML; raise on hit.
- [ ] Smoke test (monkeypatched tiny payload) + run real build → commit.

### Task 4: Public shell — template + css

**Files:** Create `web/template-public.html`, `web/public.css`

- [ ] Template: v2 head (title "Derma Intel — Where does your clinic stand online? · Trinade",
  description, canvas theme-color), fixed glass top bar (wordmark + "Get your report" CTA),
  `<main id="story2">`, script order gsap → liquid-glass → data → story2 → boot.
- [ ] public.css: act layout primitives on tokens (act sections `min-height:100dvh`, pinned stage
  classes, hook type styles, beeswarm dot `.bee` (10px, `--r-pill`, ink at .25 / lime for "you"),
  gate card, pricing grid — all consuming tokens-v2/components; no raw hex).

### Task 5: Acts 1–2 — Hook + The Market (story2.js part 1)

**Files:** Create `web/story2.js`

- [ ] `DI2` namespace; build acts into `#story2`; ScrollTrigger pinned scenes; SplitText headline.
  Act 1 "Your patients are searching. Right now.": queries type/cycle (from `payload.queries`),
  Doto counter counts 0→queries total (`--dur-slow`, once, on enter).
  Act 2: beeswarm dots fly in (stagger 40–70ms) to `{x,y}` positions on a demand axis with ruler
  strip; headline "34 clinics compete for them." (numbers from kpis — never hardcoded).
- [ ] Reduced-motion: acts render final-state static (no pins, no tweens — guard all GSAP behind
  `DI2.reduced`).

### Task 6: Acts 3–4 — The Gap + The Turn

- [ ] Act 3: scrub timeline — invisible dots (inv) desaturate+drop below a drawn line; counter
  "15 have no website at all"; three grain-card teasers (ALERT triad, letters + bands) slide in.
- [ ] Act 4: owned-vs-borrowed — mirrored bars (GROWTH vs STATUS fields at `--field-dim:.55`)
  from `owned_borrowed` aggregates; copy: what the visible few own vs rent (Practo shadows).

### Task 7: Act 5 — Find yourself (the gate)

- [ ] Search input (label "Find your clinic"); on submit: normalize+tokenize input, fnv1a with salt
  (JS mirror of Task 2), score = matched token hashes / clinic tokens, best ≥ .5 wins; exact
  full-hash short-circuits.
- [ ] Match → liquid-glass gate card (`liquidGlass()` enhance; backdrop fallback automatic):
  "✓ We found you." + rank bucket line + `inv` line ("one of the 15 invisible online") + a
  **decorative** frosted `.dot-num--ghost` score glyph + dual CTA:
  `Get your report — ₹4,999` (razorpay link or `wa.me` fallback) · `Book the walkthrough` (wa.me
  prefilled "Namaste! I'd like the Derma Intel visibility report for <typed name>").
  No match → calm fallback card: "We map 34 Guntur clinics — tell us yours on WhatsApp."
- [ ] Gate scrolls into Act 6 on "see plans".

### Task 8: Act 6 — The offer (diagnostic ladder) + footer

- [ ] Three cards: **Report hero** (grain GROWTH, ₹ from payload.pricing, dual CTA, "fee credited
  toward your build within 90 days"), **Monitoring** (surface card, ₹9,999/yr vs ₹2,999/qtr anchor,
  "follow-up visits", chip "ships-to-subscribers roadmap: social analysis"), **Build** (STATUS field,
  "from ₹49,999 · FCFS slots · report fee credited" → WhatsApp).
  Clinical-mirror lede: "You'd never treat before an examination. Neither would we."
- [ ] Footer: Trinade line, generated_at, "data from public Google results", no fake urgency
  anywhere. Commit.

### Task 9: QA + wiring

- [ ] Playwright QA (scratchpad): console clean · act screenshots at 1440/390 · gate flow with a
  real clinic name (private payload names read from `.cache` locally, NOT from the page) ·
  reduced-motion static render · grep built HTML for real names (belt over Task 3's braces).
- [ ] taste-skill pre-flight on the page; fix what it catches.
- [ ] Full `python -m pytest -q` (137 + new) green.
- [ ] CLAUDE.md: add public build row to the run table (`python web/build_web.py --public`? No —
  keep `python -c "from web.build_web import build_public; build_public()"` documented, or add a
  `--public` argv flag in Task 3 — flag preferred). Memory update. Final commit.
