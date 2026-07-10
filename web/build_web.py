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
    # Brand display face (Warm Intelligence) — vendored offline, see docs/redesign/BRAND_GUIDE.md §10
    ("Bricolage Grotesque", 700, "bricolage-700.woff2"),
    ("Bricolage Grotesque", 800, "bricolage-800.woff2"),
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


def _num0(v):
    return 0 if _isna(v) else int(round(float(v)))


def _norm_clinic(row) -> dict:
    """Normalize a scored clinic row into the plain dict modules.report consumes."""
    key = maps_collector.dedup_key(row.get("place_url") or "") or str(row.get("name") or "").lower()
    web = "" if _isna(row.get("website")) else str(row.get("website")).strip()
    phone = "" if _isna(row.get("formatted_phone_number")) else str(row.get("formatted_phone_number")).strip()
    return {
        "name": row.get("name"), "key": key, "has_website": bool(web),
        "owned": _num0(row.get("web_owned_appearances")),
        "borrowed": _num0(row.get("web_borrowed_appearances")),
        "places": _num0(row.get("in_places_count")),
        "reviews": _num0(row.get("user_ratings_total")),
        "rating": 0.0 if _isna(row.get("rating")) else float(row.get("rating")),
        "appearances": _num0(row.get("appearances")),
        "has_phone": bool(phone),
        "web_appearances": _num0(row.get("web_appearances")),
        "has_own_site": bool(row.get("has_own_site")) if not _isna(row.get("has_own_site")) else False,
        "platforms": [],
    }


def _attach_reports(clinics, top10, scored, qrows, k, med_app) -> dict:
    """Attach doctor-facing report fields (visibility, scorecard, benchmarks, verdict, SERP proof) to
    each clinic dict in place; return the market-summary dict. Safe no-op if web data is absent."""
    from modules import report, web_screens as ws_mod
    screens = ws_mod.load_web_screens()
    has_web = bool(screens.get("queries"))
    clist = [{"name": r.get("name"), "website": r.get("website"), "place_url": r.get("place_url")}
             for _, r in scored.iterrows()]
    web_by = ws_mod.aggregate_web_by_clinic(screens, clist) if has_web else {}
    market = {"avg_reviews": float(k["avg_reviews"]), "avg_rating": float(k["avg_rating"]),
              "median_appearances": med_app}

    norm = {}
    for _, r in scored.iterrows():
        nc = _norm_clinic(r)
        nc["platforms"] = (web_by.get(nc["key"]) or {}).get("platforms", [])
        norm[nc["key"]] = nc
    norm_list = list(norm.values())
    ranked = {d["key"]: d for d in report.rank_by_visibility(norm_list, market)}
    total = len(norm_list)
    cache: dict = {}

    def fields(key):
        if key in cache:
            return cache[key]
        nc = norm.get(key)
        if not nc:
            cache[key] = {}
            return {}
        rk = ranked.get(key, {})
        out = {
            "visibility": rk.get("visibility"), "visibility_rank": rk.get("rank"),
            "visibility_total": total,
            "web": {"owned": nc["owned"], "borrowed": nc["borrowed"], "appearances": nc["web_appearances"],
                    "has_own_site": nc["has_own_site"], "in_places": nc["places"],
                    "platforms": nc["platforms"]},
            "scorecard": report.scorecard(nc, market),
            "benchmarks": report.benchmarks(nc, market),
            "breakdown": report.visibility_breakdown(nc, market),
            "verdict": report.verdict(nc, market),
            "proof": report.serp_proof(key, screens, clist, qrows) if has_web else None,
        }
        cache[key] = out
        return out

    def key_of(c):
        return maps_collector.dedup_key(c.get("place_url") or "") or str(c.get("name") or "").lower()

    for c in clinics:
        c.update(fields(key_of(c)))
    for c in top10:
        c.update(fields(key_of(c)))
    return report.market_summary(norm_list, market)


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


def intent_positions(ok_rows, qrows, key_of) -> dict:
    """Per clinic-key: [{cat, pos (avg, 1dp), n}] for every query category the clinic
    actually appears in, plus '_market': {cat: median of clinic averages}. Feeds the
    'Where you rank, by what patients want' strip in the clinic report."""
    cat_of = {str(q.get("query") or "").strip().lower(): q.get("category") for q in qrows}
    acc: dict = {}
    for r in ok_rows:
        cat = cat_of.get(str(r.get("query") or "").strip().lower())
        pos = r.get("position")
        if not cat or _isna(pos):
            continue
        key = key_of(r)
        acc.setdefault(key, {}).setdefault(cat, []).append(float(pos))

    out: dict = {}
    market: dict = {}
    for key, cats in acc.items():
        entries = []
        for cat, positions in cats.items():
            avg = round(sum(positions) / len(positions), 1)
            entries.append({"cat": cat, "pos": avg, "n": len(positions)})
            market.setdefault(cat, []).append(avg)
        entries.sort(key=lambda e: e["pos"])
        out[key] = entries
    out["_market"] = {
        cat: round(sorted(v)[len(v) // 2] if len(v) % 2 else
                   (sorted(v)[len(v) // 2 - 1] + sorted(v)[len(v) // 2]) / 2, 1)
        for cat, v in market.items()
    }
    return out


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
    payload["market"] = _attach_reports(clinics, top10, scored, qrows, k, med_app)

    payload["kpis"] = {
        "unique_clinics": int(k["unique_clinics"]), "no_website_count": no_web,
        "avg_rating": round(float(k["avg_rating"]), 2), "avg_reviews": int(k["avg_reviews"]),
        "pct_with_website": round(float(k["pct_with_website"]), 1),
        "total_appearances": len(ok), "queries": len(qrows),
    }
    ip = intent_positions(ok, qrows, lambda r: maps_collector.dedup_key(r.get("place_url") or "")
                          or str(r.get("name") or "").lower())
    for c in clinics + top10:
        ck = maps_collector.dedup_key(c.get("place_url") or "") or str(c.get("name") or "").lower()
        c["intents"] = ip.get(ck, [])
    payload["intents_market"] = ip.get("_market", {})

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


def _font_face_css(fonts=None) -> str:
    blocks = []
    for fam, wt, fname in (fonts or _FONTS):
        p = VENDOR / fname
        if not p.exists():
            continue
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        blocks.append(
            f'@font-face{{font-family:"{fam}";font-style:normal;font-weight:{wt};'
            f'font-display:swap;src:url(data:font/woff2;base64,{b64}) format("woff2");}}'
        )
    return "\n".join(blocks)


# Public dist: v2 brand — Doto replaces Bricolage; weight "100 900" = the variable range.
_FONTS_PUBLIC = [
    ("Geist", 400, "geist-400.woff2"), ("Geist", 500, "geist-500.woff2"),
    ("Geist", 600, "geist-600.woff2"), ("Geist", 700, "geist-700.woff2"),
    ("Geist Mono", 400, "geistmono-400.woff2"), ("Geist Mono", 500, "geistmono-500.woff2"),
    ("Doto", "100 900", "doto-var.woff2"),
]


# GSAP (vendored offline) — order matters: core first, then plugins.
_GSAP = ["gsap.min.js", "ScrollTrigger.min.js", "SplitText.min.js", "ScrollToPlugin.min.js"]
_SHOTS = WEB.parent / "data" / "Full Page Screenshots"


def _gsap_js() -> str:
    parts = []
    for fn in _GSAP:
        p = VENDOR / fn
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _copy_proof(payload) -> int:
    """Bundle the SERP proof screenshots the app references into dist/proof/ — deploy-safe
    (no ../../data escape, so the same dist/ works on file:// and on Vercel)."""
    import shutil
    dest = DIST / "proof"
    dest.mkdir(parents=True, exist_ok=True)
    names = {(c.get("proof") or {}).get("screenshot") for c in payload.get("clinics", [])}
    names.discard(None)
    n = 0
    for name in names:
        src = _SHOTS / name
        if src.exists():
            try:
                shutil.copyfile(src, dest / name)
                n += 1
            except Exception:
                pass
    return n


def build() -> str:
    payload = build_payload()
    template = (WEB / "template.html").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    shell_js = (WEB / "shell.js").read_text(encoding="utf-8")
    story_js = (WEB / "story.js").read_text(encoding="utf-8")
    app_js = (WEB / "app.js").read_text(encoding="utf-8")
    gsap_js = _gsap_js()

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
            .replace("{{GSAP}}", gsap_js)
            .replace("{{DATA}}", data_json)
            .replace("{{SHELL_JS}}", shell_js)
            .replace("{{STORY_JS}}", story_js)
            .replace("{{APP_JS}}", app_js))

    n_proof = _copy_proof(payload)
    out = DIST / "index.html"            # Vercel serves this at /
    out.write_text(html, encoding="utf-8")
    (DIST / "derma_intel.html").write_text(html, encoding="utf-8")  # back-compat for the local opener
    (DIST / "vercel.json").write_text('{\n  "cleanUrls": true,\n  "trailingSlash": false\n}\n', encoding="utf-8")  # static deploy config
    n = payload["kpis"]["unique_clinics"]
    print(f"Built {out}  ({len(html) // 1024} KB, {n} clinics, {n_proof} proof imgs)")
    return str(out)


V2 = WEB.parent / "docs" / "redesign" / "v2"


def _leak_scan(scan_text: str, full_payload: dict) -> None:
    """Second tripwire (first is tests/test_public_data.py): no distinctive clinic-name
    token may appear in any surface a name could travel through — the payload JSON and
    our authored template/css/js. Vendored blobs (base64 fonts, minified GSAP) are
    excluded: names cannot enter them, and random substrings false-positive there."""
    from web import public_data
    low = scan_text.lower()
    for c in full_payload.get("clinics", []):
        for tok in public_data.name_tokens(c.get("name") or ""):
            if len(tok) > 3 and tok in low:
                raise RuntimeError(f"PUBLIC LEAK: clinic name token {tok!r} found in public output")


def build_public() -> str:
    """Build the anonymized public dist (spec 2026-07-10 §3): dist/public/index.html.
    Home story only — no ECharts, no real names, no exact per-clinic figures."""
    from web import public_data

    full = build_payload()
    qrows = storage.load_rows(storage.QUERIES_JSON) or []
    cfg = {
        "report": config.PRICE_REPORT, "monitor_qtr": config.PRICE_MONITOR_QTR,
        "monitor_yr": config.PRICE_MONITOR_YR, "build_from": config.PRICE_BUILD_FROM,
        "retainer_mo": config.PRICE_RETAINER_MO,
        "rzp_report": config.RAZORPAY_LINK_REPORT,
        "rzp_monitor_qtr": config.RAZORPAY_LINK_MONITOR_QTR,
        "rzp_monitor_yr": config.RAZORPAY_LINK_MONITOR_YR,
        "whatsapp": config.WHATSAPP_NUMBER,
    }
    payload = public_data.build_public_payload(full, qrows, cfg, salt=config.PUBLIC_SALT)

    template = (WEB / "template-public.html").read_text(encoding="utf-8")
    styles = "\n".join([
        _font_face_css(_FONTS_PUBLIC),
        (V2 / "tokens-v2.css").read_text(encoding="utf-8"),
        (V2 / "components.css").read_text(encoding="utf-8"),
        (WEB / "public.css").read_text(encoding="utf-8"),
    ])
    # An inline <script> ends at a literal "</script" — liquid-glass's header comment
    # contains one as a usage example. Escape ONLY that sequence (a broad "</" escape
    # corrupts regex literals like /</g in code).
    lg = (VENDOR / "liquid-glass.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
    story2 = (WEB / "story2.js").read_text(encoding="utf-8").replace(
        "{{SALT}}", config.PUBLIC_SALT).replace("</script", "<\\/script")
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    html = (template
            .replace("{{STYLES}}", styles)
            .replace("{{GSAP}}", _gsap_js())
            .replace("{{LIQUID_GLASS}}", lg)
            .replace("{{DATA}}", data_json)
            .replace("{{STORY2_JS}}", story2))

    # Leak surfaces: everything we author + the data. Not the vendored binaries.
    scan_text = "\n".join([template, (WEB / "public.css").read_text(encoding="utf-8"),
                           story2, data_json])
    _leak_scan(scan_text, full)

    out_dir = DIST / "public"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    (out_dir / "vercel.json").write_text(
        '{\n  "cleanUrls": true,\n  "trailingSlash": false\n}\n', encoding="utf-8")
    print(f"Built {out}  ({len(html) // 1024} KB, {len(payload['lookup'])} clinics anonymized)")
    return str(out)


if __name__ == "__main__":
    if "--public" in sys.argv:
        build_public()
    else:
        build()
