# V4 · The background subject — four built, one chosen

> **Chosen: the dot matrix.** Shipping as `build_web.py`'s default. It is one flag to
> change — `python web/build_web.py --subject=map|mesh|none` — and every variant stays
> in the tree, so this is a reversible call, not a one-way door.
>
> Evidence: `verification/background-variants.png` (all four at 1440) and
> `verification/background-detail.png` (the same region at 1:1, which is the one that
> actually decides it — at half scale every variant looks like nothing).

---

## What was built

| # | Variant | How | Cost |
|---|---|---|---|
| 1 | **none** | the flat `#EDEDED` field — what V1–V3 shipped | 0 |
| 2 | **map** | the styled Guntur extract, inline SVG at `.34` | 8 KB |
| 3 | **dots** | the same extract as a halftone, inline SVG at `.30` | 13 KB |
| 4 | **mesh** | a CSS mesh in the jewel grammar, with a genuine dark zone | ~0 |

The plan reserved slot 4 for a **Higgsfield-generated raster**. It was not generated, for
three reasons, and the CSS mesh stands in its place:

1. **The identity already has a gradient grammar.** ATLAS §5: two to four radials over one
   base linear, every radial anchored outside the box so the colour arrives from off-canvas,
   plus `feTurbulence` grain at 14%. A mesh written in that grammar is more on-brand than
   any generated image could be, because it is literally the same language as the jewels.
2. **It ships as markup, not a raster.** No `<img>`, so V0's open question 3 — the law
   amendment a baked WebP would have required — never has to be answered, and there is no
   image competing for the dist's remaining headroom.
3. **The account has 10 credits on a free plan**, which does not cover a generation.
   Proceeding would have meant a purchase, and buying credits is George's call, not mine.

The Higgsfield route stays open if he wants it — see *Still on the table* below.

---

## Why the dot matrix wins

**It makes the motif land at a fourth scale.** The identity already runs the dot at three:
dot-matrix numerals, dot-column histograms, the scatter field. A Guntur drawn as dots makes
it four, and rhymes with everything already built. This was the plan's own prediction, and
the 1:1 crop confirms it — the dotted street network is instantly *ours* in a way the line
map is not.

**It stays a ground.** At `.30` the dots read as texture in the gaps between cards and
disappear behind them. Nothing competes with a numeral, which is the entire test a subject
has to pass.

**It is the real city.** The ground is Guntur's actual arterial network, not decoration —
the same extract, the same projection, the same degree-to-km constants as the "1.5 km from
the core" readings. That is worth having under a report about that city.

**It costs 13 KB** and needs no coordinated card work.

### Why not the others

**map** — genuinely attractive, but at texture opacity you lose *map* and keep *lines*. In
the 1:1 crop the strokes read as arbitrary marks above the card; the thing that makes it a
map (labels, recognisable form, hierarchy you can follow) is exactly what gets held back to
stop it competing. The dot version keeps its character at low opacity because dots are a
texture by nature.

**mesh** — the most striking of the four, and the only one with a dark zone, which is what
the measured dark rung was built for. Two problems, one of them shipping-blocking:

- **It breaks the top bar.** The bar is Veil rung, `rgba(255,255,255,.38)`, so the dark
  corner bleeds straight through it and the utility icons — drawn in `--ink-3` — go
  near-invisible. Fixing it means an opaque bar, which costs the glass.
- **It needs V5 to cooperate.** A dark zone under light cards is a legibility fault, not a
  look; it only works when the cards over it flip to the dark rung. That is a coordinated
  change across the bento, not a background choice.

It stays in the tree because it is the one variant that exercises `sfDark`/`inkDark`, and
because it is the natural ground if the design ever goes dark-led.

---

## What this settles for V5

The V0 inventory carried exactly one open assumption (§1, *Dependency on the V4 background
choice*): the dark card rung assumed the subject has a dark zone. **It does not.** The dots
variant reads light throughout, so:

- **No card borrows a dark ground.** `body[data-subject="dark"]` never matches, and
  `.panel--dark` keeps its self-carried `--sfDark-flatSurface` base.
- **The dark rung still ships and is still correct** — it is now used by cards that choose
  to be dark on their own (YC-03's teaser and YC-19's prescription band in the inventory),
  not by cards that inherit darkness from behind.
- **No card's content, size or position changes.** Exactly as the inventory predicted: only
  which primitive some of them wear.

---

## Still on the table

If George wants the Higgsfield ground after all, the work is small: generate at 1440×950 or
larger, bake to WebP, add it as `--subject=gen`, and amend the no-raster law with a
background-only allowlist **plus a `background-image` scan in the verifier** — today's check
counts `<img>` elements only, so a CSS raster would pass silently and the exemption would be
an unenforced hole. Cost is a credit purchase first.
