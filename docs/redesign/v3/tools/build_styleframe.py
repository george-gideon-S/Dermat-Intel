"""Build the Gate A styleframe — every measured v3 decision rendered live.

Self-contained output (fonts base64, palette generated from palette.json) so it can
be opened over file:// and probed by the verifier. This is the artefact Gate A judges:
the glass ladder, the five jewel recipes, the three numeral registers, the lime census,
the instrument furniture, and the calibration swatch strip the probe harness targets.

    python docs/redesign/v3/tools/build_styleframe.py
"""

from __future__ import annotations

import base64
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
V3 = ROOT / "docs" / "redesign" / "v3"
VENDOR = ROOT / "web" / "vendor"
OUT = V3 / "styleframe.html"

sys.path.insert(0, str(V3 / "tools"))
from gen_tokens import load_palette, palette_css  # noqa: E402

FONTS = [
    ("Geist", 300, "geist-300.woff2"),
    ("Geist", 400, "geist-400.woff2"),
    ("Geist", 500, "geist-500.woff2"),
    ("Geist", 600, "geist-600.woff2"),
    ("Geist Mono", 400, "geistmono-400.woff2"),
    ("Doto", "100 900", "doto-var.woff2"),
]


def font_face_css() -> str:
    out = []
    for family, weight, filename in FONTS:
        path = VENDOR / filename
        if not path.exists():
            continue
        b64 = base64.b64encode(path.read_bytes()).decode()
        out.append(
            f'@font-face{{font-family:"{family}";font-weight:{weight};font-style:normal;'
            f'font-display:swap;src:url(data:font/woff2;base64,{b64}) format("woff2");}}'
        )
    return "\n".join(out)


def tick_ruler(n: int = 34, pos: float = 0.5, tone: str = "ink") -> str:
    """Ticks at 45% alpha, major every 6th, one full-alpha marker with a glow."""
    pitch, h = 8, 22
    w = n * pitch
    ticks = []
    for i in range(n):
        x = i * pitch + pitch / 2
        major = i % 6 == 0
        hh = 15 if major else 9
        ticks.append(f'<rect x="{x:.1f}" y="{h - hh}" width="1.5" height="{hh}" rx=".7"/>')
    colour = "var(--ink-2)" if tone == "ink" else "var(--ink-onMesh)"
    mx = pos * w
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none" '
        f'style="color:{colour}">'
        f'<g fill="currentColor" opacity="var(--tick-alpha)">{"".join(ticks)}</g>'
        f'<rect x="{mx:.1f}" y="0" width="3" height="{h}" rx="1.5" fill="currentColor">'
        f'</rect></svg>'
    )


def dot_column(values: list[float], highlight: int | None = None, tone: str = "white") -> str:
    """Dot-column histogram; per-dot alpha modulated so it shimmers, not a bar chart."""
    cell, cols = 5, len(values)
    max_v = max(values) or 1
    rows = 9
    w, h = cols * cell * 2, rows * cell + 4
    colour = "var(--ink-onMesh)" if tone == "white" else "var(--ink-2)"
    dots = []
    for i, v in enumerate(values):
        n = max(1, round(v / max_v * rows))
        # Alpha is per COLUMN (driven by its value), with a sine on the column index
        # so the field shimmers instead of reading as a flat bar chart. Doing this
        # per-dot-row instead would fade the base of every column into nothing.
        a = 0.42 + 0.5 * (v / max_v) * (0.6 + 0.4 * math.sin(i * 1.7 + 1))
        a = min(0.95, max(0.30, a))
        if highlight is not None and i == highlight:
            a = 1.0
        for r in range(n):
            cy = h - 3 - r * cell
            dots.append(f'<circle cx="{i * cell * 2 + cell}" cy="{cy}" r="{cell * 0.34:.2f}" '
                        f'opacity="{a:.2f}"/>')
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none" '
            f'style="color:{colour}"><g fill="currentColor">{"".join(dots)}</g></svg>')


# Real Derma Intel numbers (the 34-clinic visibility distribution)
VIS = [7, 8, 8, 8, 8, 10, 10, 12, 13, 20, 31, 34, 36, 39, 40, 40, 40, 41, 45, 47,
       49, 49, 50, 66, 67, 70, 74, 79, 84, 88, 89, 92, 97, 100]

JEWELS = [
    ("clear", "Online visibility", "88", "Strong — 5 of 34", "80–100", "measured"),
    ("steady", "Online visibility", "66", "Partway — 24 of 34", "51–79", "measured"),
    ("caution", "Online visibility", "34", "Below market — 27 of 34", "21–50", "derived"),
    ("alarm", "Online visibility", "13", "Nearly invisible — 32 of 34", "0–20", "measured"),
    ("index", "Market rank", "27", "of 34 in Guntur", "always", "measured"),
]


def build() -> str:
    palette = load_palette()

    jewel_cards = []
    for fam, label, num, sub, band, basis in JEWELS:
        viz = (tick_ruler(34, 26 / 34, "white") if fam == "index"
               else dot_column(VIS, highlight=VIS.index(int(num)) if int(num) in VIS else None))
        jewel_cards.append(f"""
      <figure class="jfig">
        <div class="jewel jewel--{fam}">
          <div class="j-label">{label}</div>
          <div class="dot-num dot-num--white">{num}</div>
          <div class="j-sub">{sub}</div>
          <div class="j-viz">{viz}</div>
        </div>
        <figcaption><b>{fam}</b> · {band} <span class="basis basis--{basis}">{basis}</span></figcaption>
      </figure>""")

    swatches = ["sf-field", "ink-1", "ink-3", "sf-flatCard", "sf-flatInner", "accent-lime",
                "jewel-clear-core", "jewel-index-core"]
    strip = "".join(f'<i style="background:var(--{s})" title="--{s}"></i>' for s in swatches)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Derma Intel v3 — Gate A styleframe</title>
<style>
{font_face_css()}
{palette_css(palette)}
{(V3 / 'tokens-v3.css').read_text(encoding='utf-8')}
{(V3 / 'components-v3.css').read_text(encoding='utf-8')}

*,*::before,*::after {{ box-sizing: border-box; }}
body {{ margin:0; background: var(--sf-field); color: var(--ink-1);
        font: var(--fw-body) var(--fs-body)/var(--lh-body) var(--sans);
        -webkit-font-smoothing: antialiased; }}
.wrap {{ max-width: 1180px; margin: 0 auto; padding: var(--sp-8) var(--sp-6) var(--sp-8); }}
h1 {{ font: var(--fw-medium) var(--fs-section)/1.1 var(--sans); letter-spacing: var(--ls-tight);
      margin: 0 0 var(--sp-2); }}
h2 {{ font: var(--fw-medium) var(--fs-section)/1.15 var(--sans); letter-spacing: var(--ls-tight);
      margin: var(--sp-8) 0 var(--sp-2); }}
.sub {{ color: var(--ink-3); font-size: var(--fs-body); margin: 0 0 var(--sp-5); max-width: 68ch; }}
.wordmark {{ font-weight: var(--fw-semi); letter-spacing: var(--ls-tight); font-size: var(--fs-title); }}
.wordmark span {{ color: var(--ink-4); font-weight: var(--fw-body); }}

.ladder {{ display:flex; gap: var(--sp-4); align-items: stretch; }}
.ladder > div {{ flex:1; padding: var(--sp-4); font-size: var(--fs-micro); color: var(--ink-2);
                 min-height: 116px; }}
.ladder code {{ display:block; font-family: var(--mono); color: var(--ink-3); margin-top: var(--sp-1); }}
.nest {{ padding: var(--sp-4); }}
.nest .g-inner {{ padding: var(--sp-3); font-size: var(--fs-micro); color: var(--ink-2); }}

/* 3-up keeps each jewel near the reference's measured 460x300; 5-up would compress
   them to half scale and the fidelity proof would be dishonest. */
.jgrid {{ display:grid; grid-template-columns: repeat(3, 1fr); gap: var(--sp-5) var(--sp-4); }}
.jfig {{ margin:0; }}
.jewel {{ aspect-ratio: 460/300; }}
.jgrid .dot-num--white {{ font-size: 3.6rem; }}
figcaption {{ font-size: var(--fs-micro); color: var(--ink-3); margin-top: var(--sp-2); }}
figcaption b {{ color: var(--ink-2); font-weight: var(--fw-medium); }}
.basis {{ border-radius: var(--r-pill); padding: 1px 7px; margin-left: 3px; }}
.basis--measured {{ background: var(--data-track); color: var(--ink-2); }}
.basis--derived {{ background: var(--zone-hidden); color: var(--ink-2); }}

.regs {{ display:flex; gap: var(--sp-8); align-items: flex-end; flex-wrap: wrap; }}
.reg small {{ display:block; color: var(--ink-3); font-size: var(--fs-micro); margin-top: var(--sp-2); }}
.row {{ display:flex; align-items:center; gap: var(--sp-3); }}

.limerow {{ display:flex; align-items:center; gap: var(--sp-4); flex-wrap: wrap; }}
.inst {{ display:grid; grid-template-columns: 200px 1fr; gap: var(--sp-4) var(--sp-5);
         align-items:center; }}
.inst .k {{ font-size: var(--fs-small); color: var(--ink-2); }}
.wgrid {{ display:grid; grid-template-columns: repeat(2,1fr); gap: var(--sp-4); }}
.note {{ padding: var(--sp-4); font-size: var(--fs-small); color: var(--ink-2); }}
.note b {{ font-weight: var(--fw-medium); color: var(--ink-1); }}
table {{ border-collapse: collapse; width: 100%; font-size: var(--fs-small); }}
th, td {{ text-align: left; padding: 7px 12px 7px 0; color: var(--ink-2); font-weight: var(--fw-body); }}
th {{ color: var(--ink-3); font-size: var(--fs-micro); }}
tr + tr td {{ border-top: 1px solid var(--ink-hair); }}
</style></head>
<body><div class="wrap">

<div class="wordmark">derma intel <span>guntur</span></div>
<h1 style="margin-top:var(--sp-5)">v3 — the measured system</h1>
<p class="sub">Every value below was sampled from <code>design/Design Inspiration/</code> by
<code>tools/sample_reference.py</code> and reconciled in <code>ATLAS.md</code>. Nothing here was
chosen by eye. The fidelity contract runs reference&nbsp;→&nbsp;atlas&nbsp;→&nbsp;palette&nbsp;→&nbsp;tokens&nbsp;→&nbsp;app;
fix downstream, never upstream.</p>

<h2>The glass ladder</h2>
<p class="sub">There is no single glass recipe — there is a ladder, and each rung is a recipe
<em>over the field</em> rather than a flat hex, because what the eye reads is the step. Measured raw
deltas within single images: field&nbsp;→&nbsp;+7 veil&nbsp;→&nbsp;+10–17 card&nbsp;→&nbsp;+7 inner.</p>
<div class="ladder">
  <div class="g-veil">Veil<code>white .38 · blur 8</code></div>
  <div class="g-card">Card<code>white .80 · blur 14</code></div>
  <div class="g-elev">Elevated<code>white .92</code></div>
  <div class="g-card nest">Card holding an inner
    <div class="g-inner">Inner — the brightest surface in the system<code>white .97</code></div>
  </div>
  <div class="g-float">Float<code>white .55 · blur 26 · saturate 140%</code></div>
</div>

<h2>Five mesh jewels</h2>
<p class="sub">2–4 radials over one base linear, every radial anchored <em>outside</em> the box so
colour arrives from off-card. Three voices each: pale frame → vivid core → deep anchor, plus a tinted
bloom past the edge. <b>Our divergence from the Log App:</b> the visibility jewel <em>state-maps</em> —
the colour drains of green as the score falls, so a 34 can never render as reassuring.</p>
<div class="jgrid">{"".join(jewel_cards)}</div>

<h2>Three numeral registers</h2>
<p class="sub">If it counts something countable it is dot-matrix; if it <em>spans</em>, it is light.
Off-dots are never drawn. Nothing in the system renders at weight 700 — the face is not shipped.</p>
<div class="regs">
  <div class="reg"><span class="dot-num">1122</span><small>1 · dot-ink — KPI metrics, stat values</small></div>
  <div class="reg">
    <div class="jewel jewel--caution" style="width:190px;aspect-ratio:460/300;padding:var(--sp-3)">
      <div class="dot-num dot-num--white" style="font-size:3rem">34</div>
    </div>
    <small>2 · dot-white — jewel heroes only</small>
  </div>
  <div class="reg">
    <div class="row"><span class="disp">#28 → #19</span></div>
    <small>3 · display-light 300 — spans, ranks, ratios</small>
  </div>
  <div class="reg">
    <div class="row"><span class="disp">6.4</span><span class="unit">avg position</span></div>
    <small>units ride the proportional face, baseline-aligned</small>
  </div>
</div>

<h2>The accent — one lime, five measured hits</h2>
<p class="sub">Sampled with <code>maxchroma</code> across five images; band centre
<code>#DCF306</code>. Ink text on lime, always. <b>Maximum three per page</b>, and the verifier counts
them.</p>
<div class="limerow">
  <span class="pill pill--lime">Total</span>
  <span class="pill pill--lime">Worst gap</span>
  <span class="pill">In range</span>
  <span class="pill">Below market</span>
  <span class="pill pill--value">27 / 34</span>
</div>

<h2>Instrument furniture</h2>
<p class="sub">Ticks at 45% alpha with one full-alpha marker carrying a glow — that contrast is what
makes it read as a measurement instrument rather than a bar chart. Quota-free by rule: no target line,
ever.</p>
<div class="inst">
  <div class="k">Tick ruler · rank 27 of 34</div>
  <div class="ruler" style="color:var(--ink-2)">{tick_ruler(34, 26/34)}</div>
  <div class="k">Dot column · 34-clinic distribution</div>
  <div>{dot_column(VIS, highlight=10, tone="ink")}</div>
  <div class="k">Filament · 11 of 78 searches</div>
  <div class="filament" style="color:var(--data-owned)">
    <div class="filament__fill" style="width:14%"></div></div>
  <div class="k">Filament · never bought an ad</div>
  <div class="filament" style="color:var(--data-absent)">
    <div class="filament__fill" style="width:0%"></div></div>
</div>

<h2>What this overturns from v2</h2>
<div class="wgrid">
  <div class="g-card note">
    <b>The canvas was never cool-tinted.</b> Every neutral probe returned R=G=B exactly.
    v2's <code>#E9EAEC</code> canvas and <code>#131417</code> ink have no measured basis
    → <code>#EDEDED</code> / <code>#232323</code>.
  </div>
  <div class="g-card note">
    <b>Cards are not flat white.</b> v2 painted <code>#FFFFFF</code> on everything. The reference runs
    five rungs, and a nested card is measurably brighter than its parent (<code>#FAFAFA</code> inside
    <code>#F3F3F3</code>).
  </div>
  <div class="g-card note">
    <b>Weight 700 is wrong everywhere.</b> v2 set <code>--fw-display:700</code> and dot numerals at
    700. Nothing in the reference exceeds 600; hero numerals sit near 320.
  </div>
  <div class="g-card note">
    <b>The score jewel is not orange.</b> Green owns everything below y≈0.45. The blazing orange
    belongs to the <em>Index</em> jewel — v2 mis-attributed it, and its triads were 2–3× too pastel.
  </div>
</div>

<h2>Calibration swatch strip</h2>
<p class="sub">Flat, stable targets for the headless probe harness. Without it every probe lands on a
gradient blend and the tolerances stop meaning anything.</p>
<div class="probestrip" data-verify="probestrip">{strip}</div>

</div></body></html>
"""


if __name__ == "__main__":
    html = build()
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(html) // 1024} KB)")
