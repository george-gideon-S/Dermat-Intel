"""Build a single self-contained HTML review page for a deep-extraction run.

Purpose is verification, not decoration: an operator needs to see every field for every place,
spot what is missing, and judge whether the extraction is trustworthy - so gaps are rendered as
loudly as values, and the distinction between "the clinic has no website" and "we failed to
read one" is kept visible rather than flattened into a blank cell.
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import html
import json

FIELDS = [
    ("listing_position", "#"), ("name_clean", "Name (cleaned)"), ("name_raw", "Name (raw)"),
    ("category", "Category"), ("relevance", "Relevance"), ("address", "Address"),
    ("plus_code", "Plus code"), ("phone", "Phone"), ("website", "Website"),
    ("website_type", "Website type"), ("rating", "Rating"), ("reviews_total", "Reviews (total)"),
    ("reviews_captured", "Reviews (captured)"), ("owner_responses", "Owner replies"),
    ("has_photos", "Photos"), ("hours", "Hours"), ("topics", "Topics"),
    ("rating_histogram", "Star spread"), ("google_profile_gaps", "Google says missing"),
    ("place_id", "Place ID"), ("feature_id", "Feature ID (CID)"),
]


def esc(v):
    return html.escape("" if v is None else str(v))


def fmt(key, val):
    if val is None or val == "" or val == [] or val == {}:
        return '<span class="miss">not found</span>'
    if key == "hours" and isinstance(val, dict):
        return "<br>".join(f"{esc(d)}: {esc(t)}" for d, t in val.items())
    if key == "topics" and isinstance(val, dict):
        top = sorted(val.items(), key=lambda kv: -kv[1])[:8]
        return " ".join(f'<span class="chip">{esc(k)} <b>{v}</b></span>' for k, v in top)
    if key == "rating_histogram" and isinstance(val, dict):
        tot = sum(val.values()) or 1
        bars = ""
        for star in ("5", "4", "3", "2", "1"):
            n = val.get(star, 0)
            bars += (f'<div class="bar"><i>{star}</i>'
                     f'<u style="width:{max(1, round(100*n/tot))}%"></u><s>{n}</s></div>')
        return bars
    if key == "google_profile_gaps" and isinstance(val, list):
        return " ".join(f'<span class="gap">{esc(x)}</span>' for x in val)
    if key == "website" and val:
        return f'<a href="{esc(val)}" target="_blank" rel="noopener">{esc(val)[:46]}</a>'
    if key == "has_photos":
        return "yes" if val else '<span class="miss">no</span>'
    return esc(val)


def build(run_dir: _Path, out_file: _Path, query: str) -> dict:
    places = []
    for f in sorted((run_dir / "places").glob("*.json")):
        try:
            places.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    places.sort(key=lambda r: r.get("listing_position") or 9999)

    ok = [p for p in places if not p.get("error")]
    errs = [p for p in places if p.get("error")]
    stats = {
        "total": len(places), "extracted": len(ok), "errors": len(errs),
        "relevant": sum(1 for p in ok if p.get("relevance") == "relevant"),
        "adjacent": sum(1 for p in ok if p.get("relevance") == "adjacent"),
        "irrelevant": sum(1 for p in ok if p.get("relevance") == "irrelevant"),
        "no_website": sum(1 for p in ok if not p.get("has_own_website")),
        "reviews": sum(p.get("reviews_captured") or 0 for p in ok),
        "with_hours": sum(1 for p in ok if p.get("hours")),
        "with_plus": sum(1 for p in ok if p.get("plus_code")),
        "with_phone": sum(1 for p in ok if p.get("phone")),
    }

    cards = []
    for p in ok:
        rel = p.get("relevance") or "unknown"
        miss = p.get("missing_fields") or []
        rows = "".join(
            f'<tr><th>{esc(lbl)}</th><td>{fmt(k, p.get(k))}</td></tr>'
            for k, lbl in FIELDS)
        revs = ""
        for r in (p.get("reviews") or [])[:6]:
            resp = r.get("owner_response")
            revs += (
                f'<div class="rev"><div class="rh"><b>{esc(r.get("author"))}</b>'
                f'<span class="st">{"*" * (r.get("rating") or 0)}</span>'
                f'<span class="dt">{esc(r.get("relative_date"))}</span></div>'
                f'<p>{esc((r.get("text") or "")[:400])}</p>'
                + (f'<div class="own"><b>Owner replied:</b> {esc(resp.get("text","")[:260])}</div>'
                   if resp else "") + "</div>")
        more = len(p.get("reviews") or []) - 6
        if more > 0:
            revs += f'<div class="more">+ {more} more reviews captured</div>'
        cards.append(f"""
<details class="card {rel}">
  <summary>
    <span class="pos">{esc(p.get("listing_position"))}</span>
    <span class="nm">{esc(p.get("name_clean") or p.get("listing_name"))}</span>
    <span class="tag {rel}">{esc(rel)}</span>
    <span class="cat">{esc(p.get("category") or "-")}</span>
    <span class="rt">{esc(p.get("rating") or "-")} ({esc(p.get("reviews_total") or 0)})</span>
    {'<span class="tag nw">no website</span>' if not p.get("has_own_website") else ''}
    {f'<span class="tag mi">{len(miss)} missing</span>' if miss else '<span class="tag okk">complete</span>'}
  </summary>
  <div class="body"><table>{rows}</table>
  <div class="revs"><h4>Reviews captured: {p.get("reviews_captured")} of {p.get("reviews_total") or "?"}
    &nbsp;|&nbsp; owner replies: {p.get("owner_responses") or 0}</h4>{revs or '<i>none captured</i>'}</div></div>
</details>""")

    err_html = ""
    if errs:
        err_html = '<h3>Failed to extract</h3><ul>' + "".join(
            f'<li>{esc(e.get("listing_name"))} - {esc(e.get("error"))[:120]}</li>' for e in errs) + "</ul>"

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Maps extraction - {esc(query)}</title><style>
:root{{--bg:#0e1116;--fg:#e6edf3;--mut:#8b949e;--line:#22272e;--card:#161b22;
--ok:#3fb950;--warn:#d29922;--bad:#f85149;--accent:#58a6ff}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,Segoe UI,sans-serif}}
header{{padding:22px 26px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:5}}
h1{{margin:0 0 4px;font-size:19px}} .sub{{color:var(--mut);font-size:13px}}
.stats{{display:flex;flex-wrap:wrap;gap:9px;margin-top:13px}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:7px;padding:7px 12px}}
.stat b{{font-size:17px;display:block}} .stat span{{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.4px}}
main{{padding:18px 26px 60px;max-width:1180px}}
.card{{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--line);
border-radius:8px;margin-bottom:9px}}
.card.relevant{{border-left-color:var(--ok)}} .card.adjacent{{border-left-color:var(--warn)}}
.card.irrelevant{{border-left-color:var(--bad)}}
summary{{cursor:pointer;padding:11px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
summary::-webkit-details-marker{{display:none}}
.pos{{color:var(--mut);min-width:26px;font-variant-numeric:tabular-nums}}
.nm{{font-weight:600;flex:1;min-width:220px}}
.cat,.rt{{color:var(--mut);font-size:12px}}
.tag{{font-size:11px;padding:2px 7px;border-radius:99px;border:1px solid var(--line)}}
.tag.relevant{{color:var(--ok)}} .tag.adjacent{{color:var(--warn)}} .tag.irrelevant{{color:var(--bad)}}
.tag.nw{{color:#ff7b72;border-color:#5d1a17;background:#2d1113}}
.tag.mi{{color:var(--warn)}} .tag.okk{{color:var(--ok)}}
.body{{padding:4px 14px 16px;border-top:1px solid var(--line)}}
table{{width:100%;border-collapse:collapse;margin:10px 0}}
th{{text-align:left;color:var(--mut);font-weight:500;width:170px;vertical-align:top;padding:5px 8px 5px 0;font-size:12px}}
td{{padding:5px 0;vertical-align:top;word-break:break-word}}
.miss{{color:var(--bad);font-style:italic;opacity:.85}}
.chip{{display:inline-block;background:#1f2630;border-radius:99px;padding:2px 9px;margin:2px 3px 2px 0;font-size:12px}}
.gap{{display:inline-block;background:#2d2211;color:var(--warn);border-radius:4px;padding:2px 7px;margin-right:4px}}
.bar{{display:flex;align-items:center;gap:7px;margin:2px 0}}
.bar i{{font-style:normal;color:var(--mut);width:10px}}
.bar u{{height:8px;background:var(--accent);border-radius:3px;text-decoration:none;display:block}}
.bar s{{text-decoration:none;color:var(--mut);font-size:11px}}
.revs h4{{margin:14px 0 8px;font-size:13px;color:var(--mut);font-weight:500}}
.rev{{border-top:1px solid var(--line);padding:9px 0}}
.rh{{display:flex;gap:9px;align-items:center;font-size:12px}}
.st{{color:var(--warn);letter-spacing:1px}} .dt{{color:var(--mut)}}
.rev p{{margin:5px 0;color:#c9d1d9}}
.own{{background:#11202e;border-left:2px solid var(--accent);padding:6px 10px;margin-top:5px;font-size:13px}}
.more{{color:var(--mut);font-size:12px;padding-top:8px}}
a{{color:var(--accent)}}
.filters{{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}}
button{{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px;
padding:6px 12px;cursor:pointer;font-size:12px}}
button.on{{border-color:var(--accent);color:var(--accent)}}
</style></head><body>
<header>
  <h1>Google Maps extraction &mdash; {esc(query)}</h1>
  <div class="sub">Every place the live listing returned, scrolled to the end of the list.
  Click a row to see every field and its reviews. Red italics mean the field was not found.</div>
  <div class="stats">
    <div class="stat"><b>{stats['total']}</b><span>places found</span></div>
    <div class="stat"><b>{stats['extracted']}</b><span>extracted</span></div>
    <div class="stat"><b>{stats['relevant']}</b><span>skin-relevant</span></div>
    <div class="stat"><b>{stats['adjacent']}</b><span>adjacent</span></div>
    <div class="stat"><b>{stats['irrelevant']}</b><span>not relevant</span></div>
    <div class="stat"><b>{stats['no_website']}</b><span>no own website</span></div>
    <div class="stat"><b>{stats['reviews']:,}</b><span>reviews captured</span></div>
    <div class="stat"><b>{stats['with_phone']}</b><span>have phone</span></div>
    <div class="stat"><b>{stats['with_hours']}</b><span>have hours</span></div>
    <div class="stat"><b>{stats['errors']}</b><span>failed</span></div>
  </div>
  <div class="filters">
    <button class="on" data-f="all">All</button>
    <button data-f="relevant">Skin-relevant</button>
    <button data-f="adjacent">Adjacent</button>
    <button data-f="irrelevant">Not relevant</button>
    <button data-f="nowebsite">No website</button>
    <button data-f="missing">Has missing fields</button>
  </div>
</header>
<main>{''.join(cards)}{err_html}</main>
<script>
document.querySelectorAll('.filters button').forEach(b => b.onclick = () => {{
  document.querySelectorAll('.filters button').forEach(x => x.classList.remove('on'));
  b.classList.add('on');
  const f = b.dataset.f;
  document.querySelectorAll('.card').forEach(c => {{
    let show = true;
    if (f === 'nowebsite') show = !!c.querySelector('.tag.nw');
    else if (f === 'missing') show = !!c.querySelector('.tag.mi');
    else if (f !== 'all') show = c.classList.contains(f);
    c.style.display = show ? '' : 'none';
  }});
}});
</script></body></html>"""
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(doc, encoding="utf-8")
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="runs/maps_deep/guntur_dermatologists")
    ap.add_argument("--out", default="runs/maps_deep/guntur_dermatologists/extraction_review.html")
    ap.add_argument("--query", default="dermatologists in Guntur")
    args = ap.parse_args()
    stats = build(_Path(args.run), _Path(args.out), args.query)
    print(json.dumps(stats, indent=2))
    print(f"-> {args.out}")


if __name__ == "__main__":
    raise SystemExit(main())
