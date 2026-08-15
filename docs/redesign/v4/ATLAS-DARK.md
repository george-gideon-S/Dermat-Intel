# Derma Intel v4 — Atlas addendum: the dark side of the glass ladder

> **What this is.** The measured basis for the one thing v4 adds to the v3 identity: a **dark
> rung** on the glass ladder, for cards that float over the background subject. Everything else
> in [`../v3/ATLAS.md`](../v3/ATLAS.md) carries forward unchanged — this addendum does not
> overturn a single v3 finding, it extends the ladder downward.
>
> **Sampled by** `tools/sample_reference.py` (a v4 copy of the v3 sampler, plus a `maxluma`
> mode) against the probe map in `reference-probes.json`. Raw output:
> `reference-samples.json` (committed, rerunnable). **35 probes across 4 images, 2 warnings.**
>
> **The fidelity contract is unchanged:** reference images → this atlas → `palette.json` →
> tokens → the app. Fix downstream, never upstream.

---

## 0 · Honesty box

The four references are **3D device renders of a photographed human torso under warm studio
light**. Three consequences, stated up front:

1. **Every dark sample carries a warm cast** (R > G > B, mean channel spread **9.4**). That is
   the *subject* showing through the card, not the card's own hue.
2. **The white anchors are light cards, not pure white**, so calibration gains run 1.09–1.18.
   One anchor (`Glucose 2 / light-card-face`, sigma 19.4) straddles an edge → **every
   calibrated value from Glucose 2 is discarded**; its raw values are still used for the
   surface consensus.
3. **`maxluma` on thin light glyphs under-reads.** Antialiasing means the brightest 12% of a
   glyph patch is dimmer than the glyph's true colour, so light ink is stated **brighter**
   than its raw sample — the exact mirror of the v3 rule for `minluma` and dark ink.

### What the sampler flagged

| Probe | Sample | Why it matters |
|---|---|---|
| `Glucose 2 / light-card-face` | `#D9D9D9`, sigma **19.4** | Anchor straddles an edge → Glucose 2's gain of 1.175 is untrustworthy → its calibrated column is discarded. |
| `Warm Translucent / panel-numeral` | `#AC846B`, luma **141** | Declared `light`, came back mid — the probe missed the gauge figure and sampled the panel. **Rejected**; the dark-ink ramp rests on the five Glucose hits. |

The second warning is the new `expect: "light"` gate doing its job. v3 declared
`expect: "dark"` on every text probe but never checked it, so a probe that missed onto its
own background was silently accepted. Both luma gates are now enforced — see the v4 sampler's
docstring.

### Confidence, graded

| Finding | Confidence | Basis |
|---|---|---|
| Dark surfaces are the **same white veil** at low alpha | **High — measured** | 13 card probes across 3 images; 4 independent alpha solves |
| Alpha centre `.20` | **Medium-high — measured, spread** | 4 within-image pairs: .198 · .142 · .337 · .268 |
| Ink-on-dark primary = pure white | **High — measured** | 5 `maxluma` hits, all calibrating to `#FFFFFF`, deltas 3–6 |
| Ink-on-dark secondary `.80` | **Medium — single hit** | one probe, raw .75 / calibrated .87, antialias floor |
| Nested rung, border, hairline, ring | **Derived** | no nested tile or hairline exists in the reference at probe scale |

---

## 1 · The load-bearing discovery: the dark rung is not a new material

The v3 ladder is **white at alpha over a light field**. The obvious assumption for a dark card
is that it must be a *dark* fill — a different material. **The measurements say otherwise.**

Every dark card in the references is **brighter than the subject it covers**, never darker:

| Image | Bare subject | Card over it | Step |
|---|---|---|---|
| Glucose 3 · pair A | `#170F04` (luma 16.1) | `#443F35` (luma 63.4) | **+47.3** |
| Glucose 1 · pair A | `#1B130A` (luma 20.4) | `#383532` (luma 53.6) | **+33.2** |
| Warm Translucent | `#261512` (luma 25.7) | `#805D59` (luma 103.0) | **+77.3** |
| Warm Translucent | `#3E261F` (luma 44.4) | `#765D60` (luma 100.8) | **+56.4** |

Solving `step = α × (255 − backdrop)` for each pair:

```
Glucose 3 A :  47.3 / (255 − 16.1) = 47.3 / 238.9  → α = 0.198
Glucose 1 A :  33.2 / (255 − 20.4) = 33.2 / 234.6  → α = 0.142
Warm      1 :  77.3 / (255 − 25.7) = 77.3 / 229.3  → α = 0.337
Warm      2 :  56.4 / (255 − 44.4) = 56.4 / 210.6  → α = 0.268
```

> **The dark rung is `rgba(255,255,255,~.20)` — the same white veil as every other rung on the
> ladder, over a dark backdrop instead of a light one.**

The two Glucose solves (`.198`, `.142`) are weighted above the two Warm solves (`.337`,
`.268`): the Glucose set is our actual shell reference, and the Warm image is a different
product with a visibly heavier panel. **Centre taken: `.20`.**

This is why the identity holds together. There is no second material to reconcile, no dark
palette to keep in sync with a light one, and `prefers-reduced-transparency` collapses the
dark rung exactly the way it collapses the light ones.

**Cross-check.** The light Card rung is `rgba(255,255,255,.80)` over field `#EDEDED` (237):
`.80×255 + .20×237 = 251.4` → `#FBFBFB`, which is exactly the committed `sf.flatCard`. Running
the same arithmetic at `.20` over a luma-30 backdrop gives **75**, against a measured card
median of **69.6** across 13 probes (mean 68.4, range 53.6–82.3). The model reproduces.

### The 13 surface probes

| Image | Probes (raw) |
|---|---|
| Glucose 3 | `#443F35` · `#4D4944` · `#453F3A` · `#413D3A` · `#504A46` · `#57514D` |
| Glucose 1 | `#383532` · `#3C3934` · `#4C4842` · `#4F4B45` · `#514D49` |
| Glucose 2 | `#494540` · `#423E39` |

Median luma **69.6** · mean **68.4** · **mean channel spread 9.4** (all warm).

---

## 2 · The warm cast is the subject, and it is neutralised

Every v3 neutral probe returned **delta 0 — R=G=B exactly** (ATLAS §1). Every v4 dark-surface
probe returns **delta 6–15, always warm**. That difference is itself the evidence:

- Our light cards sit on a **hue-neutral field**, so they measure neutral.
- The reference's dark cards sit on a **warm photograph**, and are translucent enough that the
  photograph's hue reads through.

So the cast belongs to the reference's subject, not to the card material. **We take the step
and the alpha; we never take the hue.** Our own background subject (a desaturated Guntur map,
a dot matrix, or a generated ground — V4 decides) supplies whatever tint reads through, which
is the correct behaviour for a translucent surface and the same way the light ladder already
works.

---

## 3 · Ink on dark

`maxluma`, five hits across two images, every one calibrating to pure white:

| Probe | Raw | Calibrated | Delta |
|---|---|---|---|
| Glucose 3 · `hero-numeral-on-dark` (the "149") | `#FFFCF9` | `#FFFFFF` | 6 |
| Glucose 3 · `hero-numeral-on-dark-2` (the "23") | `#FCFBF8` | `#FFFFFF` | 4 |
| Glucose 3 · `label-on-dark` | `#F7F5F1` | `#FFFFFF` | 6 |
| Glucose 1 · `hero-numeral-on-dark` | `#FDFBF7` | `#FFFFFF` | 6 |
| Glucose 1 · `hero-numeral-on-dark-2` | `#F5F4F2` | `#FFFFFF` | 3 |

> **Primary ink on dark is `#FFFFFF`.** Measured, five independent hits, near-neutral throughout.

**Secondary** rests on one probe, `Glucose 1 / muted-on-dark` = `#D4D0CC` (luma 208.7),
calibrated `#ECE8E3` (luma ≈ 232), sitting on a card of luma ≈ 72:

```
raw basis        : (208.7 − 72) / (255 − 72) = 0.747
calibrated basis : (232.0 − 72) / (255 − 72) = 0.874
antialias floor  : the true glyph is brighter than either
```

Band `.75–.87` → **`.80` taken**. Single hit, so graded medium.

**Tertiary** is derived by mirroring the proportions of the light ink ramp (`#232323` →
`#5A5A5A` → `#8C8C8C` → `#B0B0B0`, i.e. drops of roughly 23% / 21% / 15% of the field):
white → `.80` → **`.58`**.

---

## 4 · The dark rungs, as authored

Authored in `../v3/palette.json` under two new families, `sfDark` and `inkDark` — because
**that file remains the only place in the repo where a colour is written.** `gen_tokens.py`
walks the same tree, so these emit both the CSS custom properties and the `DI.P` object with
no change to the generator.

| Token | Value | Basis |
|---|---|---|
| `--sfDark-surface` | `rgba(255,255,255,.20)` | **measured** — 4 alpha solves, centre |
| `--sfDark-nested` | `rgba(255,255,255,.26)` | derived — one clearly visible level, no more |
| `--sfDark-border` | `rgba(255,255,255,.14)` | derived — the luminous hairline at dark scale |
| `--sfDark-ring` | `rgba(0,0,0,.24)` | derived — a shadow is invisible on dark; the card is separated by a darkening ring instead |
| `--sfDark-flatSurface` | `#4B4B4B` | derived — `.20` over a luma-30 backdrop, for `prefers-reduced-transparency` |
| `--sfDark-flatNested` | `#595959` | derived — same, at `.26` |
| `--inkDark-1` | `#FFFFFF` | **measured** — 5 hits |
| `--inkDark-2` | `rgba(255,255,255,.80)` | measured, single hit |
| `--inkDark-3` | `rgba(255,255,255,.58)` | derived — mirrors the light ramp's proportions |
| `--inkDark-hair` | `rgba(255,255,255,.14)` | derived |

**Blur is not colour and is not authored here.** The light ladder runs `blur(14px)` on Card and
`blur(26px)` on Float. The dark rung sits over an image rather than a flat field, so legibility
needs more than Card and less than Float: **`blur(18px)`, no `saturate()`** (the background
subject is already desaturated by design). It lives with the other non-colour tokens.

---

## 5 · Laws for the dark rung

1. **Two rungs, one level of nesting — exactly like the light side.** `surface` holds the card;
   `nested` holds a tile inside it. There is no third rung and no nesting past one level.
2. **A rung is chosen by role, never by taste** — and on the dark side, never by *aesthetics
   over the subject*. A card goes dark **only** because it overlaps the background subject's
   dark zone; a card on the light field stays light-translucent. Mixing the two on the same
   ground is the failure mode this addendum exists to prevent.
3. **Dark ink is only ever legal on a dark rung.** `--inkDark-*` on a light card is invisible,
   and `--ink-1` on a dark card is unreadable. The pairing is fixed.
4. **`dot-white` stays scoped to jewel heroes *on light surfaces*.** The v3 law ("dot-white:
   jewel hero numerals only") was written when every surface was light. Dark cards get their
   own numeral registers — `dot-on-dark` and `display-light-on-dark`, both riding
   `--inkDark-1` — so a dark KPI tile is not forced to either an illegible `dot-ink` or an
   unsanctioned `dot-white`. This is a **scoping** of the v3 law, not a repeal.
5. **`prefers-reduced-transparency` collapses the dark rungs to their flat equivalents**, same
   as the light ones.
6. **No new chroma.** The dark rung introduces zero hues: two white alphas, one black alpha,
   two flat greys. Every jewel, lime and data hue is unchanged, and the censuses (≤3 jewels,
   ≤3 limes per page) are unaffected.

---

## 6 · What this does *not* change

- The field is still `#EDEDED`, still hue-neutral.
- The five light rungs, the ink ramp, lime `#DCF306`, the five jewel families and their
  state-map, the three numeral registers, tick rulers, dot columns — all unchanged.
- Nothing at weight 700. No uppercase-tracked eyebrows. No red.
- **The v3 sampler, its probe map and its samples are untouched** — `docs/redesign/v3/` is
  byte-identical after this pass, so the v3 atlas remains reproducible.

## 7 · Also measured: Doto's ink coverage, and where the dot register stops working

Not a dark-rung finding, but it came out of the same measure-don't-guess pass and V5 will
need it when it places 35 cards full of numerals.

The picker's visibility numerals were set in Doto and were barely readable. Sampling the
rendered page rather than trusting the eye: the ink is exactly `--ink-1` (`#232323`, confirmed
by reading the darkest pixel in the glyph box) — but **only 3% of the glyph box carries any
ink at all.** Doto draws a dot grid with the off-dots absent, so it is pale by construction.

Ink coverage of a rendered "13", swept:

| | 300 | 400 | 500 | 600 |
|---|---|---|---|---|
| **ROND 100** | 3.2% | 4.6% | 5.7% | 7.4% |
| **ROND 0** | 3.8% | 5.6% | 7.6% | 9.4% |

Three things fall out:

1. **Coverage tracks weight, not size.** 36px and 44px measure identically — scaling a faint
   Doto numeral up does not make it darker, only bigger and faint.
2. **Square dots buy ~25% more ink than round.** We cannot spend it: `ROND 100` is the
   identity.
3. **Weight cannot rescue it.** Even 600 — the legal ceiling — tops out near 9%.

> **The rule this gives us: Doto is a LARGE register, and on small type it is a texture, not a
> numeral.** It earns its keep at hero scale and on the jewels, where it is white on saturated
> colour. Below roughly the medium register on a light field, a Doto numeral is decoration.

### The size floor, confirmed a second time on the built page

The rule above was derived on the picker. When the 19 Your Clinic cards landed, the same
measurement run against the real dashboard put numbers on how far it generalises:

| Register, as rendered on the clinic page | Ink coverage |
|---|---|
| Doto 24px, weight 500 (the small stat tier) | **2.1 – 5.5%** |
| Doto 36px, weight 500 | **5.1%** |
| display-light (Geist 300) | **69.3%** |

A 13-to-33× difference, on cards whose entire job is to be scanned. Seven cards were affected.

> **So the register rule keeps its logic and gains a FLOOR.** A count still *wants* the dot
> register — but below the medium step the dot register does not exist, and the numeral takes
> the light face instead. This is a refinement, not a repeal: nothing about "counts are
> dot-matrix, spans are light" changes, it simply stops applying at a size where the face
> cannot deliver ink.

**Where Doto survives:** the jewel heroes, and only there. White on saturated chroma at 54px+
is the one context in this product where the dot grid has both the scale and the contrast to
read as a numeral. Exactly one `.dot-num` element now remains on the whole clinic page, and it
is the visibility jewel's hero.

**Still open for George:** even at 36px on the light field, Doto measures ~5%. If the dot
register is to appear anywhere outside a jewel, it needs a hero-scale slot of its own. Retiring
`dot-ink` from light surfaces altogether is the logical end of this measurement, but it is a
brand call rather than a legibility one, so it has not been taken.

The register rule already pointed here — *"if it counts something countable it is dot-matrix;
if it spans, it is light"* — and a visibility score is an index on 0–100, not a count of
countable things, exactly like the rank span that already rides `display-light` on the clinic
hero. The picker's numerals are display-light for that reason, and it is a correct reading of
the existing rule rather than an exception to it.

## 8 · Open dependency

The dark rung assumes **the background subject has a dark zone**. That holds for the map and
dot-matrix variants. If V4's generated-gradient variant wins and reads light throughout, these
tokens still exist and stay correct — but fewer cards use them, and any card that must stay
dark carries its own ground rather than borrowing the subject's. Re-validate at V4 before V5
builds the cards. This changes no card's content, size or position — only which primitive it
wears (`V0_CARD_INVENTORY.md` §1).
