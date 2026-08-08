"""Build the v3 contact sheet — the qualitative half of verification.

Numeric probes prove the tokens are right; they cannot tell you whether the thing
looks like the reference. This pairs each rebuilt surface with its before-state
and with the reference images it was derived from, on one page, so the judgement
is made side by side rather than from memory.

    python docs/redesign/v3/tools/contact_sheet.py
"""

from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
V3 = ROOT / "docs" / "redesign" / "v3"
VER = V3 / "verification"
REF = ROOT / "design" / "Design Inspiration"
OUT = VER / "contact-sheet.html"

PAIRS = [
    ("Your Clinic", "before/clinic-1440.png", "clinic-1440.png",
     "One KPI card, five identical grey rows, a raw dark screenshot, six flat "
     "prescription rows — against eight panels, five different instruments, a "
     "redrawn results page and a plan that projects rank."),
    ("The Market", "before/market-1440.png", "market-1440.png",
     "Seven static charts with tooltips — against eleven cross-filtered panels, "
     "including the 1122-block SERP ownership matrix that had never been built."),
]

PHONE = [("Your Clinic · 390", "clinic-390.png"), ("The Market · 390", "market-390.png")]

REFS = [
    ("Design Inpsiration - dashboard snapshot 2.png", "The composition ground truth"),
    ("Design inspiration - cards.png", "Score jewel — sand melting into vivid green"),
    ("Design Inspiration - cards 1.png", "Index jewel — slate frame, blazing core"),
    ("Design Inspiration - cards 2.png", "The nested inner card, brightest in the system"),
    ("Design Inspiration - sidebar navbar.png", "Rail rows floating on the field"),
    ("Design Inspiration - cards 3.png", "Stat cards + the edge-cropped mini-viz"),
]


def uri(path: Path) -> str | None:
    if not path.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def fig(src: str | None, caption: str, missing: str) -> str:
    body = (f'<img src="{src}" alt="{caption}" loading="lazy">' if src
            else f'<div class="missing">{missing}</div>')
    return f'<figure>{body}<figcaption>{caption}</figcaption></figure>'


def main() -> None:
    blocks = []
    for title, before, after, note in PAIRS:
        blocks.append(f"""
    <section>
      <h2>{title}</h2>
      <p class="note">{note}</p>
      <div class="pair">
        {fig(uri(VER / before), "before — v2", "no before shot; run shoot_pages.py before rebuilding")}
        {fig(uri(VER / after), "after — v3", "no after shot; run verify_dashboard.py")}
      </div>
    </section>""")

    phone = "".join(fig(uri(VER / f), c, "missing") for c, f in PHONE)
    blocks.append(f"""
    <section><h2>390 px</h2>
      <p class="note">The rail collapses to a top filter strip; every panel reflows
      rather than shrinking. No chart collapses to zero height.</p>
      <div class="phones">{phone}</div>
    </section>""")

    refs = "".join(fig(uri(REF / f), c, "reference image not found") for f, c in REFS)
    blocks.append(f"""
    <section><h2>The reference</h2>
      <p class="note">Every value in the v3 system was sampled from these by
      <code>tools/sample_reference.py</code> and reconciled in <code>ATLAS.md</code>.
      Judge the rebuild against them, not against the old build.</p>
      <div class="refs">{refs}</div>
    </section>""")

    OUT.write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Derma Intel v3 — contact sheet</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin:0; background:#EDEDED; color:#232323;
         font:400 15px/1.55 ui-sans-serif,system-ui,sans-serif; }}
  .wrap {{ max-width:1500px; margin:0 auto; padding:48px 28px 80px; }}
  h1 {{ font-size:1.7rem; font-weight:500; letter-spacing:-.02em; margin:0 0 6px; }}
  h2 {{ font-size:1.2rem; font-weight:500; letter-spacing:-.02em; margin:56px 0 6px; }}
  .lede, .note {{ color:#5A5A5A; max-width:78ch; margin:0 0 20px; }}
  .note {{ font-size:.9rem; color:#8C8C8C; }}
  .pair {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; align-items:start; }}
  .phones {{ display:flex; gap:20px; flex-wrap:wrap; }}
  .phones figure {{ width:300px; }}
  .refs {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:20px; }}
  figure {{ margin:0; }}
  img {{ width:100%; display:block; border-radius:14px;
        box-shadow:0 8px 28px rgba(35,35,35,.10); background:#fff; }}
  figcaption {{ font-size:.78rem; color:#8C8C8C; padding-top:8px; }}
  .missing {{ padding:40px; border:1px dashed #B0B0B0; border-radius:14px;
             color:#8C8C8C; font-size:.85rem; }}
  code {{ font-family:ui-monospace,monospace; font-size:.85em; color:#5A5A5A; }}
</style></head>
<body><div class="wrap">
  <h1>Derma Intel v3 — contact sheet</h1>
  <p class="lede">The qualitative half of verification. The probe harness proves the
  tokens are right; this page is where you decide whether it looks like the thing it
  was derived from.</p>
  {''.join(blocks)}
</div></body></html>""", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
