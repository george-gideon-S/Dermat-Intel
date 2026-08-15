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
from web import maps, views

WEB = Path(__file__).resolve().parent
V3 = WEB.parent / "docs" / "redesign" / "v3"
sys.path.insert(0, str(V3 / "tools"))

import gen_tokens  # noqa: E402 — needs the path above; palette.json -> CSS vars + JS object

VENDOR = WEB / "vendor"
DIST = WEB / "dist"
DIST.mkdir(parents=True, exist_ok=True)

# v2 "Luminous Precision" fonts (both dists) — Doto's weight is the variable range.
_FONTS_PRIVATE = [
    ("Geist", 300, "geist-300.woff2"), ("Geist", 400, "geist-400.woff2"),
    ("Geist", 500, "geist-500.woff2"), ("Geist", 600, "geist-600.woff2"),
    ("Geist Mono", 400, "geistmono-400.woff2"), ("Geist Mono", 500, "geistmono-500.woff2"),
    ("Doto", "100 900", "doto-var.woff2"),
]

# The public dist still ships the v2 face set — it is not part of this rebuild and
# its output must stay byte-identical.
_FONTS_V2 = [
    ("Geist", 400, "geist-400.woff2"), ("Geist", 500, "geist-500.woff2"),
    ("Geist", 600, "geist-600.woff2"), ("Geist", 700, "geist-700.woff2"),
    ("Geist Mono", 400, "geistmono-400.woff2"), ("Geist Mono", 500, "geistmono-500.woff2"),
    ("Doto", "100 900", "doto-var.woff2"),
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
    # v3: fields the pipeline already computes that v2 dropped on the floor. Each one
    # drives a panel — average Maps position, ready-to-book share, the 60/40 split
    # behind the blended score, ad spend, and the coordinates for the constellation.
    lat, lng = _num(row.get("lat"), 6), _num(row.get("lng"), 6)
    d.update({
        "key": key,
        "pos_avg": _num(row.get("result_position_avg"), 2),
        "high_intent": _num(row.get("high_intent_share"), 3),
        "lat": lat,
        "lng": lng,
        "km_core": _num(views.km_from_core(lat, lng), 2),
        "maps_score": _num(row.get("maps_score")),
        "web_score": _num(row.get("web_score")),
        "sponsored": _num(row.get("sponsored_count")) or 0,
    })
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


def _attach_reports(clinics, scored, qrows, k, med_app) -> dict:
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
    best_pos = {k: (v or {}).get("web_best_position") for k, v in (web_by or {}).items()}
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
                    "platforms": nc["platforms"],
                    # null for the 15 clinics with no organic result at all — the UI
                    # must render "never" rather than a misleading position 0.
                    "best_position": best_pos.get(key)},
            "scorecard": report.scorecard(nc, market),
            "benchmarks": report.benchmarks(nc, market),
            "breakdown": report.visibility_breakdown(nc, market),
            "verdict": report.verdict(nc, market),
            "proof": report.serp_proof(key, screens, clist, qrows) if has_web else None,
            # v3: what each fix is worth, in points AND in market rank.
            "plan": views.plan_impact(nc, norm_list, market),
        }
        cache[key] = out
        return out

    def key_of(c):
        return maps_collector.dedup_key(c.get("place_url") or "") or str(c.get("name") or "").lower()

    for c in clinics:
        c.update(fields(key_of(c)))

    # v3 SERP real estate. The 1122-row block table is aggregated here and only the
    # AGGREGATE ships — plus a handful of full result pages for the redrawn-SERP
    # panel. Shipping the raw rows would cost ~250 KB of JSON nobody scrolls.
    serp = {"ownership": views.serp_ownership([]), "pages": {}}
    if has_web:
        block_rows = ws_mod.to_rows(screens, clist)
        pages = []
        for c in clinics:
            q = ((c.get("proof") or {}).get("query") or "").strip()
            if q and q not in pages:
                pages.append(q)
        serp = {
            "ownership": views.serp_ownership(block_rows),
            "pages": {q: views.serp_page(block_rows, q) for q in pages[:8]},
        }
    return {"market": report.market_summary(norm_list, market), "serp": serp}


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
    # Field names differ between test fixtures and the live pipeline:
    # qrows: query|search_query · rows: query|source_query, position|result_position,
    # and live rows carry source_category directly (preferred).
    cat_of = {str(q.get("query") or q.get("search_query") or "").strip().lower(): q.get("category")
              for q in qrows}
    acc: dict = {}
    for r in ok_rows:
        if r.get("status") not in (None, "OK"):
            continue  # defensive: callers pass OK rows, but never trust it
        cat = r.get("source_category") or cat_of.get(
            str(r.get("query") or r.get("source_query") or "").strip().lower())
        pos = r.get("position") if not _isna(r.get("position")) else r.get("result_position")
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
        "clinics": [], "categories": [], "median_appearances": 0,
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
    no_web = sum(1 for c in clinics if not c["has_website"])
    pct_no = round(100 - k["pct_with_website"], 1)
    med_app = float(scored["appearances"].median())
    attached = _attach_reports(clinics, scored, qrows, k, med_app)
    payload["market"] = attached["market"]
    payload["serp"] = attached["serp"]

    payload["kpis"] = {
        "unique_clinics": int(k["unique_clinics"]), "no_website_count": no_web,
        "avg_rating": round(float(k["avg_rating"]), 2), "avg_reviews": int(k["avg_reviews"]),
        # the mean (306) is skewed by two outliers; the median (154) is the honest
        # central tendency and is what the market view leads with.
        "median_reviews": int(k["median_reviews"]),
        "pct_with_website": round(float(k["pct_with_website"]), 1),
        "total_appearances": len(ok), "queries": len(qrows),
    }
    ip = intent_positions(ok, qrows, lambda r: maps_collector.dedup_key(r.get("place_url") or "")
                          or str(r.get("name") or "").lower())
    for c in clinics:
        ck = maps_collector.dedup_key(c.get("place_url") or "") or str(c.get("name") or "").lower()
        c["intents"] = ip.get(ck, [])
    payload["intents_market"] = ip.get("_market", {})

    payload["clinics"] = clinics
    payload["categories"] = analytics.category_distribution(qrows).to_dict("records") if qrows else []
    payload["median_appearances"] = round(med_app, 1)
    # presence_funnel has been tested in modules/analytics.py since day one and
    # never reached the UI.
    payload["funnel"] = [{"step": s, "count": n} for s, n in analytics.presence_funnel(ok)]
    payload["bands"] = views.visibility_bands(clinics)
    payload["facets"] = views.market_facets(clinics)
    payload["web_available"] = bool("web_data" in scored.columns and scored["web_data"].any())
    payload["reviews_available"] = any(c.get("nlp") for c in clinics)
    return payload


def _font_face_css(fonts=None) -> str:
    blocks = []
    for fam, wt, fname in (fonts or _FONTS_V2):
        p = VENDOR / fname
        if not p.exists():
            continue
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        blocks.append(
            f'@font-face{{font-family:"{fam}";font-style:normal;font-weight:{wt};'
            f'font-display:swap;src:url(data:font/woff2;base64,{b64}) format("woff2");}}'
        )
    return "\n".join(blocks)


_FONTS_PUBLIC = _FONTS_V2


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


# v3 bundle order. CSS: palette -> tokens -> components -> app layers. JS: each
# file is an IIFE hanging off window.DI, so order is the dependency graph and
# there is no bundler, no import statements, no build step beyond concatenation.
_V3_CSS = ["00-reset", "10-shell", "15-picker", "16-map", "20-panels", "25-clinic",
           "27-market", "30-charts", "40-responsive"]
# Numeric prefix IS the load order: the panel files call DI.app.register() at parse
# time, so the app core has to be defined before them.
_V3_JS = ["00-util", "10-palette", "20-store", "30-bus", "40-topbar", "45-picker", "50-charts",
          "60-instruments", "70-app", "80-panels-clinic", "85-panels-market"]


SUBJECTS = ("none", "map", "dots", "mesh")


def _subject_block(which: str) -> str:
    """The background subject the cards float over — the whole element, because
    the variant has to reach the CSS as a class.

    Geometry for `map` and `dots` is rendered from the committed
    web/guntur-geo.json at build time, so the dist stays offline and
    self-contained: no tiles, no runtime fetch, no <img>. `mesh` is pure CSS.
    The markup carries classes only; every colour reaches it through
    web/css/16-map.css and therefore through palette.json."""
    if which not in SUBJECTS:
        raise ValueError(f"unknown subject {which!r}; expected one of {SUBJECTS}")
    inner = ""
    if which in ("map", "dots"):
        geo = maps.load_geo(WEB / "guntur-geo.json")
        inner = maps.render_dotmap(geo) if which == "dots" else maps.render_map(geo)
    return (f'<div class="subject subject--{which}" id="subject" '
            f'data-subject="{which}" aria-hidden="true">{inner}</div>')


def _vintages() -> dict:
    """Three datasets, three dates. Shipping one 'generated_at' across all of them
    implies a freshness the corpus does not have, so the rail states each."""
    def stamp(path):
        try:
            return datetime.fromtimestamp(Path(path).stat().st_mtime).strftime("%d %b %Y")
        except Exception:
            return None
    return {
        "maps": stamp(storage.RESULTS_JSON),
        "serp": stamp(getattr(config, "WEB_SCREENS_JSON", "") or
                      Path(storage.RESULTS_JSON).parent / "web_screens.json"),
        "build": datetime.now().strftime("%d %b %Y"),
    }


def build(subject: str = "dots") -> str:
    """Private dist — the paid report app (v3 'instrument-grade' dashboards)."""
    payload = build_payload()
    payload["contact"] = {"whatsapp": config.WHATSAPP_NUMBER}
    payload["vintages"] = _vintages()
    template = (WEB / "template.html").read_text(encoding="utf-8")

    # Tree-shaken ECharts (~568 KB) when it has been vendored; the full UMD build
    # otherwise; the SRI-pinned CDN tag only if neither exists.
    echarts_js = ""
    for name in ("echarts-custom.min.js", "echarts.min.js"):
        p = VENDOR / name
        if p.exists():
            echarts_js = p.read_text(encoding="utf-8")
            break
    if not echarts_js:
        sri = "sha384-Mx5lkUEQPM1pOJCwFtUICyX45KNojXbkWdYhkKUKsbv391mavbfoAmONbzkgYPzR"
        template = template.replace(
            "<script>{{ECHARTS}}</script>",
            f'<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js" '
            f'integrity="{sri}" crossorigin="anonymous"></script>')

    palette = gen_tokens.load_palette()
    css = "\n".join([
        _font_face_css(_FONTS_PRIVATE),
        gen_tokens.palette_css(palette),
        (V3 / "tokens-v3.css").read_text(encoding="utf-8"),
        (V3 / "components-v3.css").read_text(encoding="utf-8"),
        *[(WEB / "css" / f"{n}.css").read_text(encoding="utf-8") for n in _V3_CSS],
    ])
    # 10-palette.js is generated in memory and never written to disk, so there is
    # no stale-generated-file failure mode.
    app_js = "\n".join([
        gen_tokens.palette_js(palette) if n == "10-palette"
        else (WEB / "js" / f"{n}.js").read_text(encoding="utf-8")
        for n in _V3_JS
    ])
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")  # avoid closing the <script>

    html = (template
            .replace("{{STYLES}}", css)
            .replace("{{ECHARTS}}", echarts_js)
            .replace("{{DATA}}", data_json)
            .replace("{{APP_JS}}", app_js)
            .replace("{{SUBJECT}}", _subject_block(subject)))

    out = DIST / "index.html"            # Vercel serves this at /
    out.write_text(html, encoding="utf-8")
    (DIST / "derma_intel.html").write_text(html, encoding="utf-8")  # back-compat for the local opener
    (DIST / "vercel.json").write_text('{\n  "cleanUrls": true,\n  "trailingSlash": false\n}\n', encoding="utf-8")  # static deploy config
    n = payload["kpis"]["unique_clinics"]
    print(f"Built {out}  ({len(html) // 1024} KB, {n} clinics)")
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

    # Build-with-Trinade page (spec §6) — same styles, pricing-only payload (leak-safe
    # by construction), served at /build via cleanUrls.
    build_tpl = (WEB / "template-build.html").read_text(encoding="utf-8")
    build_data = json.dumps({"pricing": payload["pricing"]})
    _leak_scan(build_tpl + "\n" + build_data, full)  # authored surfaces only, not base64 fonts
    build_html = build_tpl.replace("{{STYLES}}", styles).replace("{{DATA}}", build_data)
    (out_dir / "build.html").write_text(build_html, encoding="utf-8")

    (out_dir / "vercel.json").write_text(
        '{\n  "cleanUrls": true,\n  "trailingSlash": false\n}\n', encoding="utf-8")
    print(f"Built {out} + build.html  ({len(html) // 1024} KB, {len(payload['lookup'])} clinics anonymized)")
    return str(out)


if __name__ == "__main__":
    if "--public" in sys.argv:
        build_public()
    else:
        # --subject=none|map|dots|mesh selects the background the cards float
        # over. V4 built all four and compared them at 1:1; the dot matrix won
        # and is the default. See docs/redesign/v4/BACKGROUND-DECISION.md — every
        # variant stays in the tree, so this is one flag, not a one-way door.
        which = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--subject=")),
                     "dots")
        if which not in SUBJECTS:
            raise SystemExit(f"--subject must be one of {SUBJECTS}")
        build(subject=which)
