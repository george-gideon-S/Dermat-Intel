"""Build the self-contained premium web app (web/dist/derma_intel.html).

Reuses the existing Python modules to compute one JSON payload, then inlines CSS, fonts (base64),
ECharts, the payload, and app.js into a single offline HTML file. No server, no API keys.
"""
import base64
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root for config/modules

import config
from modules import analytics, maps_collector, reviews_nlp, storage, vulnerability, web_collector

WEB = Path(__file__).resolve().parent
VENDOR = WEB / "vendor"
DIST = WEB / "dist"
DIST.mkdir(parents=True, exist_ok=True)

_FONTS = [
    ("Geist", 400, "geist-400.woff2"), ("Geist", 500, "geist-500.woff2"),
    ("Geist", 600, "geist-600.woff2"), ("Geist", 700, "geist-700.woff2"),
    ("Geist Mono", 400, "geistmono-400.woff2"), ("Geist Mono", 500, "geistmono-500.woff2"),
]


def _isna(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


_NAME_SPLIT = re.compile(r"\s*[/|]\s*")


def _display_name(n: str) -> str:
    """Google Maps names are keyword-stuffed (Name / Dermatologist / Best skin clinic ...).
    Show the primary segment for a clean, premium read; keep the full name for tooltips."""
    n = (n or "").strip()
    first = _NAME_SPLIT.split(n)[0].strip(" -–·")
    return first if len(first) >= 4 else n


def _num(v, nd=None):
    if _isna(v):
        return None
    return round(float(v), nd) if nd is not None else int(round(float(v)))


def _clinic(row, nlp_map=None) -> dict:
    full = str(row.get("name") or "")
    disp = _display_name(full)
    web = "" if _isna(row.get("website")) else str(row.get("website")).strip()
    phone = None if _isna(row.get("formatted_phone_number")) else str(row.get("formatted_phone_number")).strip()
    raw_notes = "" if _isna(row.get("opportunity_notes")) else str(row.get("opportunity_notes"))
    notes = raw_notes.replace(full, disp) if full and disp != full else raw_notes
    d = {
        "name": full,
        "display_name": disp,
        "rating": _num(row.get("rating"), 1),
        "reviews": _num(row.get("user_ratings_total")),
        "appearances": _num(row.get("appearances")) or 0,
        "has_website": bool(web),
        "website": web,
        "phone": phone,
        "address": "" if _isna(row.get("formatted_address")) else str(row.get("formatted_address")),
        "place_url": "" if _isna(row.get("place_url")) else str(row.get("place_url")),
        "score": _num(row.get("vulnerability_score")) or 0,
        "label": str(row.get("vulnerability_label") or "Low"),
        "notes": notes,
    }
    key = maps_collector.dedup_key(d["place_url"]) or full.lower()
    n = (nlp_map or {}).get(key)
    if n and n.get("n_reviews"):
        names = lambda items: [(t[0] if isinstance(t, (list, tuple)) else t) for t in (items or [])][:3]
        d["nlp"] = {
            "n": n.get("n_reviews"),
            "sentiment": n.get("avg_sentiment"),
            "pos": n.get("pos_pct"), "neg": n.get("neg_pct"),
            "themes": names(n.get("top_positive_themes")),
            "pains": names(n.get("top_negative_themes")),
            "referral": n.get("referral_mention_rate"),
            "recent6mo": (n.get("recency_summary") or {}).get("last_6mo"),
        }
    return d


def _attach_web(agg):
    """Attach Google-web visibility to the aggregated clinics (enables the 40% web blend).

    Prefers the richer screenshot-derived signal (owned vs borrowed presence) when it exists; falls
    back to the legacy live-collector cache (appearances-only). Neither present -> Maps-only score.
    """
    from modules import unify_results, web_screens
    clinics = [{"name": r.get("name"), "website": r.get("website"), "place_url": r.get("place_url")}
               for _, r in agg.iterrows()]

    screens = web_screens.load_web_screens()
    if screens.get("queries"):  # screenshot dataset present -> presence-weighted owned/borrowed signal
        web_by = web_screens.aggregate_web_by_clinic(screens, clinics)
        return unify_results.unify(agg, web_by)

    try:
        web_by_query = web_collector._load_cache()
    except Exception:
        web_by_query = {}
    if not web_by_query:
        return agg  # no web data collected yet -> score stays Maps-only
    match = web_collector.match_clinics_web(web_by_query, clinics)

    def key_of(r):
        return maps_collector.dedup_key(r.get("place_url") or "") or str(r.get("name") or "").lower()

    agg = agg.copy()
    agg["web_appearances"] = agg.apply(lambda r: (match.get(key_of(r)) or {}).get("web_appearances", 0), axis=1)
    agg["web_data"] = True
    return agg


def _load_nlp() -> dict:
    try:
        with open(reviews_nlp.nlp_cache_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        data.pop("_meta", None)
        return data
    except Exception:
        return {}


def _rating_bins(clinics) -> list:
    edges = [(0, 3.5, "< 3.5"), (3.5, 4.0, "3.5–4.0"), (4.0, 4.5, "4.0–4.5"),
             (4.5, 4.8, "4.5–4.8"), (4.8, 5.01, "4.8–5.0")]
    out = [{"bin": lbl, "count": 0} for _, _, lbl in edges]
    for c in clinics:
        r = c["rating"]
        if r is None:
            continue
        for i, (lo, hi, _) in enumerate(edges):
            if lo <= r < hi:
                out[i]["count"] += 1
                break
    return out


def build_payload() -> dict:
    rows = storage.load_rows(storage.RESULTS_JSON) or []
    qrows = storage.load_rows(storage.QUERIES_JSON) or []
    ok = [r for r in rows if r.get("status") == "OK"]
    payload = {
        "generated_at": (storage.load_meta() or {}).get("last_run") or datetime.now().isoformat(timespec="seconds"),
        "city": config.TARGET_CITY,
        "kpis": {"unique_clinics": 0, "no_website_count": 0, "avg_rating": 0,
                 "avg_reviews": 0, "pct_with_website": 0,
                 "total_appearances": len(ok), "queries": len(qrows)},
        "clinics": [], "top10": [], "categories": [], "rating_distribution": [],
        "median_appearances": 0,
    }
    if not ok:
        return payload

    agg = _attach_web(vulnerability.aggregate_clinics(ok))
    scored = vulnerability.score_clinics(agg)
    if scored is None or scored.empty:
        return payload
    k = analytics.kpis(ok)
    nlp_map = _load_nlp()
    clinics = [_clinic(r, nlp_map) for _, r in scored.sort_values("vulnerability_score", ascending=False).iterrows()]
    top10 = [_clinic(r, nlp_map) for _, r in vulnerability.top_n(scored, 10).iterrows()]
    no_web = sum(1 for c in clinics if not c["has_website"])
    pct_no = round(100 - k["pct_with_website"], 1)
    med_app = float(scored["appearances"].median())

    payload["kpis"] = {
        "unique_clinics": int(k["unique_clinics"]), "no_website_count": no_web,
        "avg_rating": round(float(k["avg_rating"]), 2), "avg_reviews": int(k["avg_reviews"]),
        "pct_with_website": round(float(k["pct_with_website"]), 1),
        "total_appearances": len(ok), "queries": len(qrows),
    }
    payload["clinics"] = clinics
    payload["top10"] = top10
    payload["categories"] = analytics.category_distribution(qrows).to_dict("records") if qrows else []
    payload["rating_distribution"] = _rating_bins(clinics)
    payload["median_appearances"] = round(med_app, 1)
    payload["headline_lead"] = "Trusted in person,"
    payload["headline_hl"] = "invisible online."
    payload["lede"] = (
        f"Across {len(qrows)} high-intent Guntur searches we mapped {k['unique_clinics']} unique "
        f"dermatology clinics averaging {round(float(k['avg_rating']),2)}★ — yet {no_web} of them "
        f"({pct_no:.0f}%) have no website at all. The clearest opportunities are the established, "
        f"in-demand clinics with no digital home."
    )
    payload["web_available"] = bool("web_data" in scored.columns and scored["web_data"].any())
    payload["reviews_available"] = any(c.get("nlp") for c in clinics)
    return payload


def _font_face_css() -> str:
    blocks = []
    for fam, wt, fname in _FONTS:
        p = VENDOR / fname
        if not p.exists():
            continue
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        blocks.append(
            f'@font-face{{font-family:"{fam}";font-style:normal;font-weight:{wt};'
            f'font-display:swap;src:url(data:font/woff2;base64,{b64}) format("woff2");}}'
        )
    return "\n".join(blocks)


def build() -> str:
    payload = build_payload()
    template = (WEB / "template.html").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    app_js = (WEB / "app.js").read_text(encoding="utf-8")

    echarts_path = VENDOR / "echarts.min.js"
    if echarts_path.exists():
        echarts_js = echarts_path.read_text(encoding="utf-8")
    else:  # graceful fallback to CDN if assets were never vendored (SRI-pinned to echarts 5.5.1)
        echarts_js = ""
        sri = "sha384-Mx5lkUEQPM1pOJCwFtUICyX45KNojXbkWdYhkKUKsbv391mavbfoAmONbzkgYPzR"
        template = template.replace(
            "<script>{{ECHARTS}}</script>",
            f'<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js" '
            f'integrity="{sri}" crossorigin="anonymous"></script>')

    css = _font_face_css() + "\n" + styles
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")  # avoid closing the <script>

    html = (template
            .replace("{{STYLES}}", css)
            .replace("{{ECHARTS}}", echarts_js)
            .replace("{{DATA}}", data_json)
            .replace("{{APP_JS}}", app_js))

    out = DIST / "derma_intel.html"
    out.write_text(html, encoding="utf-8")
    n = payload["kpis"]["unique_clinics"]
    print(f"Built {out}  ({len(html) // 1024} KB, {n} clinics)")
    return str(out)


if __name__ == "__main__":
    build()
