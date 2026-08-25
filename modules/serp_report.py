"""Build the Google-Search review page: every query in a run, on one self-contained page.

The Maps page (`gmaps/ui.py`) reviews ONE query's clinics. Google Search is the opposite shape
— the unit of analysis is the query, and a market is only legible across all hundred of them.
So this page carries the whole run: every query, captured or not, with its blocks in the exact
top-to-bottom order a searcher would meet them.

Two rules the page inherits from the collector, because a review surface that quietly drops
data is worse than no review surface:

* **Nothing is hidden.** A query that was blocked, errored or never attempted appears in the
  list with its reason, not as an absence. The header counts against the FULL query set, so
  the yield on screen can never flatter the run.
* **Owned and borrowed stay distinguishable.** A clinic ranking on its own domain, a clinic
  being written about on Practo, and a clinic appearing only in the local pack are three
  different facts. They are coloured differently and counted separately.

Output is one HTML file with the data embedded, written to `<run_dir>/serp_report.html`, so it
opens from disk with no server and can be sent to someone as a single attachment. Screenshots
stay as relative links into `serp/screenshots/`, so the page is richer in place but still
readable anywhere.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from modules import atomicio, packs, serp_collector, serp_entities, serp_parser
from modules.web_screens import AGGREGATOR_PLATFORMS, SOCIAL_PLATFORMS

REPORT_NAME = "serp_report.html"


# ------------------------------------------------------------------ classification
def domain_bucket(platform: str, domain: str) -> str:
    """Four buckets the report colours by: owned / aggregator / social / reference."""
    p = (platform or "").lower()
    if p in AGGREGATOR_PLATFORMS:
        return "aggregator"
    if p in SOCIAL_PLATFORMS:
        return "social"
    if p == "hospital":
        return "hospital"
    if p == "clinic_site":
        return "clinic"
    return "reference"


# ------------------------------------------------------------------ assembly
def _extras(run_dir, qrows: list) -> dict:
    """rank -> the interaction artifacts (settled AI overview, expanded local list)."""
    out = {}
    for q in qrows:
        rank = q.get("rank")
        if rank is None:
            continue
        data = serp_collector.read_extras(run_dir, int(rank))
        if data:
            out[int(rank)] = data
    return out


def _from_more(extras: dict) -> list:
    """Clinics captured behind the local pack's "More places" control.

    Kept separate from the three the SERP shows, and rendered as an empty section rather than
    omitted, so a reader can tell "Google showed nobody else" from "nobody clicked the button".
    """
    stats: dict = {}
    for rank, data in extras.items():
        for entry in ((data.get("more_places") or {}).get("names") or []):
            name = (entry.get("name") or "").strip() if isinstance(entry, dict) else str(entry)
            if not name:
                continue
            pos = entry.get("position") if isinstance(entry, dict) else None
            st = stats.setdefault(name, {"name": name, "queries": set(), "best": 10 ** 6})
            st["queries"].add(rank)
            st["best"] = min(st["best"], pos or 10 ** 6)
    return sorted(({"name": s["name"], "queries": len(s["queries"]),
                    "best": (None if s["best"] >= 10 ** 6 else s["best"])}
                   for s in stats.values()),
                  key=lambda p: (-p["queries"], p["best"] if p["best"] is not None else 999))


def _from_more_queries(queries: list) -> list:
    """Run-wide "More places" roll-up, built from the DEDUPED per-query lists.

    Reading the raw extras here instead would re-introduce the three map-box clinics that the
    per-query pass just removed, so the page would disagree with itself.
    """
    stats: dict = {}
    for q in queries:
        for entry in q.get("more_places") or []:
            name = (entry.get("name") or "").strip()
            if not name:
                continue
            st = stats.setdefault(name, {"name": name, "queries": set(), "best": 10 ** 6})
            st["queries"].add(q.get("rank"))
            st["best"] = min(st["best"], entry.get("position") or 10 ** 6)
    return sorted(({"name": s["name"], "queries": len(s["queries"]),
                    "best": (None if s["best"] >= 10 ** 6 else s["best"])}
                   for s in stats.values()),
                  key=lambda p: (-p["queries"], p["best"] if p["best"] is not None else 999))


def _ai_summary(extras: dict, qrows: list) -> dict:
    """What the AI overviews across this run actually contain.

    Counted against every captured query, and 'Google declined to generate one' is kept
    distinct from 'we never waited long enough to find out' — before the wait existed, all 22
    captures were the placeholder and every one of them was being reported as an overview.
    """
    available, unavailable, clinics = [], [], {}
    for rank, data in extras.items():
        ai = data.get("ai_overview") or {}
        if not ai.get("present"):
            continue
        (available if ai.get("available") else unavailable).append(rank)
        for rec in (ai.get("recommended_clinics") or []):
            name = (rec.get("name") or "").strip()
            if not name:
                continue
            st = clinics.setdefault(name, {"name": name, "queries": set(), "best": 10 ** 6})
            st["queries"].add(rank)
            st["best"] = min(st["best"], rec.get("position") or 10 ** 6)
    ranked = sorted(({"name": s["name"], "queries": len(s["queries"]),
                      "best": (None if s["best"] >= 10 ** 6 else s["best"])}
                     for s in clinics.values()),
                    key=lambda c: (-c["queries"], c["best"] if c["best"] is not None else 999))
    return {"with_overview": len(available), "declined": len(unavailable),
            "checked": len(extras), "recommended_clinics": ranked}


def repair_statuses(run_dir, qrows) -> dict:
    """Re-judge saved HTML and correct statuses the old detector got wrong.

    Normally a re-parse never touches the fetch log: whether a query was captured is a fact
    about the fetch, not about how well we parsed it afterwards. A block is the exception. If
    the saved bytes are a wall, the query was never captured, and leaving it filed as
    `parse_anomaly` breaks the one invariant this collector exists to hold — blocked is never
    anything else. The bytes are the evidence, so the correction is a restoration, not a guess.
    """
    log = serp_collector.read_fetch_log(run_dir)
    fixed = []
    for q in qrows:
        rank = q.get("rank")
        rec = log.get(str(rank))
        if not rec or rec.get("status") == serp_collector.STATUS_BLOCKED:
            continue
        path = serp_collector._paths(run_dir, int(rank))["html"]
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8", errors="replace")
        reason = serp_collector.detect_block(html, rec.get("final_url") or "")
        if not reason:
            continue
        fixed.append({"rank": rank, "was": rec.get("status"), "reason": reason,
                      "kind": serp_collector.block_kind(reason)})
        rec.update(status=serp_collector.STATUS_BLOCKED, detail=reason)
        log[str(rank)] = rec
    if fixed:
        atomicio.write_json(serp_collector.fetch_log_path(run_dir), log, indent=2)
    return {"fixed": fixed, "n": len(fixed)}


def session_state(run_dir) -> dict:
    """Is a scraper actually working on THIS run right now, and is it stuck on a wall?

    Read from the same two artifacts the runners write, so the page cannot claim a run is
    live when the process behind it has died — a progress bar that keeps looking healthy
    after the scraper is gone is worse than no progress bar.
    """
    from modules import serp_session as S
    holder = atomicio.read_json(S.lock_path(), default=None)
    running = False
    if isinstance(holder, dict):
        try:
            running = (str(holder.get("run_id") or "") == Path(run_dir).name
                       and S._pid_alive(int(holder.get("pid") or 0)))
        except (TypeError, ValueError):
            running = False
    return {"running": running,
            "wall": (serp_collector.serp_dir(run_dir) / "BLOCKED.txt").exists()}


def _page_entries(run_dir) -> dict:
    """rank -> parsed page. Read from serp/pages/, the per-query checkpoints."""
    pages = {}
    pdir = serp_collector.serp_dir(run_dir) / "pages"
    if not pdir.exists():
        return pages
    for path in sorted(pdir.glob("q*.json")):
        entry = atomicio.read_json(path, default=None)
        if isinstance(entry, dict):
            rank = entry.get("rank") or entry.get("index")
            if rank is not None:
                pages[int(rank)] = entry
    return pages


def collect_data(run_dir, qrows: Optional[list] = None) -> dict:
    """Everything the page renders, assembled from the run's own artifacts."""
    run_dir = Path(run_dir)
    from modules import runstore, serp_session

    manifest = runstore.read_manifest(run_dir)
    qrows = qrows if qrows is not None else serp_session.load_query_rows(run_dir)
    log = serp_collector.read_fetch_log(run_dir)
    pages = _page_entries(run_dir)
    state = serp_session.read_state(run_dir)

    queries, status_counts, type_counts = [], defaultdict(int), defaultdict(int)
    cat_total, cat_done = defaultdict(int), defaultdict(int)
    dom_stats: dict = {}
    place_stats: dict = {}

    for q in qrows:
        rank = q.get("rank")
        rec = log.get(str(rank), {}) or {}
        status = rec.get("status") or "not_attempted"
        page = pages.get(int(rank)) if rank is not None else None
        blocks = (page or {}).get("blocks") or []
        category = q.get("category") or "—"

        status_counts[status] += 1
        cat_total[category] += 1
        if status in serp_collector.TERMINAL_OK:
            cat_done[category] += 1

        for b in blocks:
            btype = b.get("block_type") or "other"
            type_counts[btype] += 1
            if serp_parser.is_local_pack(btype):
                name = (b.get("title") or "").strip()
                if name:
                    st = place_stats.setdefault(name, {
                        "name": name, "queries": set(), "best": 10 ** 6,
                        "rating": None, "reviews": None})
                    st["queries"].add(rank)
                    st["best"] = min(st["best"], b.get("position") or 10 ** 6)
                    if b.get("rating") is not None:
                        st["rating"] = b["rating"]
                    if b.get("reviews") is not None:
                        st["reviews"] = max(st["reviews"] or 0, b["reviews"])
                continue
            dom = (b.get("domain") or "").strip().lower()
            if not dom:
                continue
            st = dom_stats.setdefault(dom, {
                "domain": dom, "platform": b.get("platform") or "other",
                "bucket": domain_bucket(b.get("platform"), dom),
                "queries": set(), "best": 10 ** 6, "positions": [],
                "types": defaultdict(int), "title": b.get("title") or "", "url": b.get("url") or ""})
            st["queries"].add(rank)
            pos = b.get("position") or 10 ** 6
            st["best"] = min(st["best"], pos)
            st["positions"].append(pos)
            st["types"][btype] += 1

        queries.append({
            "rank": rank,
            "query": q.get("search_query") or "",
            "category": category,
            "intent": q.get("user_intent") or "",
            "strength": q.get("search_strength_score"),
            "status": status,
            "detail": rec.get("detail") or rec.get("error") or "",
            "at": rec.get("at") or "",
            "requests": rec.get("requests") or 0,
            "final_url": rec.get("final_url") or "",
            "screenshot": (f"serp/screenshots/q{int(rank):03d}.png"
                           if rank is not None and rec.get("screenshot") else None),
            "search_box_text": (page or {}).get("search_box_text") or "",
            "n_blocks": len(blocks),
            "blocks": blocks,
        })

    domains = sorted(
        ({"domain": s["domain"], "platform": s["platform"], "bucket": s["bucket"],
          "queries": len(s["queries"]), "best": (None if s["best"] >= 10 ** 6 else s["best"]),
          "avg": round(sum(s["positions"]) / len(s["positions"]), 1) if s["positions"] else None,
          "types": dict(s["types"]), "title": s["title"], "url": s["url"]}
         for s in dom_stats.values()),
        key=lambda d: (-d["queries"], d["best"] if d["best"] is not None else 999))

    places = sorted(
        ({"name": s["name"], "queries": len(s["queries"]),
          "best": (None if s["best"] >= 10 ** 6 else s["best"]),
          "rating": s["rating"], "reviews": s["reviews"]}
         for s in place_stats.values()),
        key=lambda p: (-p["queries"], p["best"] if p["best"] is not None else 999))

    # Two distinct populations, never merged into one count. The map box shows three clinics
    # on the SERP itself; the rest only exist behind "More places". Reporting them together
    # would let a clinic that is merely reachable read as one Google actually surfaced.
    extras = _extras(run_dir, qrows)
    ai = _ai_summary(extras, qrows)
    for q in queries:
        detail = (extras.get(int(q["rank"])) if q.get("rank") is not None else None) or {}
        q["ai"] = detail.get("ai_overview")
        # "More places" reopens the SAME box, so its list REPEATS the three already on the
        # SERP before continuing. Counting them in both places double-counts a clinic's
        # visibility and makes the deeper list look three clinics longer than it is.
        pack_names = [b.get("title") for b in (q.get("blocks") or [])
                      if serp_parser.is_local_pack(b.get("block_type"))]
        raw_more = (detail.get("more_places") or {}).get("names") or []
        zone = serp_parser.local_pack_zone(q.get("blocks") or [])
        more, dropped = [], 0
        for entry in raw_more:
            name = entry.get("name") or ""
            if any(serp_entities.same_clinic(name, p) for p in pack_names):
                dropped += 1
                continue
            entry = dict(entry)
            entry["position"] = len(more) + 1
            # The expanded list inherits the zone of the map box it was opened from: it is
            # the same box, one click deeper, so it cannot sit somewhere else on the page.
            entry["block_type"] = "local_pack_more_" + zone
            more.append(entry)
        q["more_places"] = more
        q["more_places_deduped"] = dropped

    # Built AFTER the loop above: it rolls up the DEDUPED per-query lists, and those do not
    # exist until the loop has run.
    places_from_more = _from_more_queries(queries)

    # Who the page is talking about, and which results belong to whom. Built from the SERP
    # itself — the local pack, the expanded list and the AI overview name most of the market,
    # so a SERP-only run needs no Maps scrape to attribute an ad or an Instagram profile.
    ctx = _context(manifest)
    roster = serp_entities.build_roster(queries, ctx)
    link_stats = serp_entities.annotate(queries, roster, ctx)
    by_subject = serp_entities.split_by_subject(roster)
    listicles = atomicio.read_json(serp_collector.serp_dir(run_dir) / "listicles.json",
                                   default=None) or {}

    captured = sum(status_counts[s] for s in serp_collector.TERMINAL_OK)
    total = len(qrows)
    return {
        "meta": {
            "run_id": manifest.get("run_id") or run_dir.name,
            "geography": manifest.get("geography"), "practice": manifest.get("practice"),
            "subject_type": manifest.get("subject_type"), "run_date": manifest.get("run_date"),
            "threshold": manifest.get("query_threshold"),
            "web_signal": manifest.get("web_signal"),
            "parser_version": serp_parser.PARSER_VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "captured": captured, "total": total,
            "yield": round(captured / total, 4) if total else 0.0,
            "total_blocks": sum(type_counts.values()),
            "google_requests": sum(q.get("requests") or 0 for q in queries),
        },
        "status_counts": dict(status_counts),
        "type_counts": dict(type_counts),
        "categories": sorted(({"category": c, "total": cat_total[c], "done": cat_done[c]}
                              for c in cat_total), key=lambda c: -c["total"]),
        "queries": queries,
        "domains": domains,
        "places": places,
        "places_from_more": places_from_more,
        "ai": ai,
        "roster": roster,
        "subjects": {k: len(v) for k, v in by_subject.items()},
        "hospitals": by_subject.get("hospital") or [],
        "links": link_stats,
        "listicles": listicles,
        "timer": serp_session.timer_state(run_dir),
        "sessions": state.get("sessions") or [],
        "session": session_state(run_dir),
    }


def _context(manifest: dict):
    """The run's own market definition, so subject classification uses ITS pack rules."""
    if not manifest.get("geography") or not manifest.get("practice"):
        return packs.legacy_context()
    try:
        return packs.load(manifest["geography"], manifest["practice"],
                          manifest.get("subject_type", "both"))
    except (packs.PackNotFound, packs.InvalidPack):
        return packs.legacy_context()


def embed_json(payload) -> str:
    """Serialize for a <script> block.

    Result titles and snippets are Google's text, not ours, and every `<` in them is a hazard
    to the HTML tokenizer rather than to JSON. Escaping only `</` is not enough: a snippet
    carrying `<!--` followed by `<script` pushes the tokenizer into its script-data-escaped
    state, where the page's own `</script>` stops being a closing tag and the whole document
    collapses into one unterminated block — a blank page. Escaping EVERY `<` removes the
    entire class, since `\\u003c` is the same string to JSON and inert to the tokenizer.
    U+2028/9 are escaped for a related reason: JS line terminators that JSON treats as
    ordinary characters.
    """
    blob = json.dumps(payload, ensure_ascii=False, default=str)
    return (blob.replace("<", "\\u003c")
                .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def build_report(run_dir, out_path: Optional[str] = None, qrows: Optional[list] = None) -> str:
    data = collect_data(run_dir, qrows=qrows)
    html = PAGE.replace("__DATA__", embed_json(data))
    target = Path(out_path) if out_path else Path(run_dir) / REPORT_NAME
    atomicio.write_text(target, html)
    return str(target)


# ------------------------------------------------------------------ the page
PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Google Search extraction</title><style>
:root{--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--line:#21262d;--card:#161b22;--card2:#1c2129;
--ok:#3fb950;--warn:#d29922;--bad:#f85149;--acc:#58a6ff;--vio:#bc8cff;--pink:#f778ba}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:14px 24px;border-bottom:1px solid var(--line);position:sticky;top:0;
background:rgba(13,17,23,.97);backdrop-filter:blur(8px);z-index:10}
.top{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
h1{margin:0;font-size:18px;letter-spacing:-.2px}
.sub{color:var(--mut);font-size:12.5px}
.live{margin-left:auto;display:flex;align-items:center;gap:8px;font-size:12px;color:var(--mut)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--ok);animation:pulse 1.4s infinite}
.dot.off{background:var(--mut);animation:none}
.dot.wall{background:var(--bad);animation:pulse .7s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
.prog{height:4px;background:var(--line);border-radius:3px;margin-top:10px;overflow:hidden}
.prog i{display:block;height:100%;background:linear-gradient(90deg,var(--acc),var(--vio));
width:0;transition:width .6s ease}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin-top:11px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 12px;min-width:78px}
.stat b{font-size:17px;display:block;font-variant-numeric:tabular-nums}
.stat span{color:var(--mut);font-size:10px;text-transform:uppercase;letter-spacing:.5px}
.stat.good b{color:var(--ok)} .stat.warn b{color:var(--warn)} .stat.bad b{color:var(--bad)}
.strip{display:flex;flex-wrap:wrap;gap:2px;margin-top:11px}
.cell{width:11px;height:11px;border-radius:2px;background:var(--line);cursor:pointer}
.cell.parsed{background:var(--ok)} .cell.zero_results{background:#1f6feb}
.cell.blocked{background:var(--bad)} .cell.parse_anomaly{background:var(--warn)}
.cell.error{background:var(--pink)} .cell.not_attempted{background:#30363d}
.cell:hover{outline:2px solid var(--fg)}
nav{display:flex;gap:7px;margin-top:12px;flex-wrap:wrap;align-items:center}
button{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:7px;
padding:6px 12px;cursor:pointer;font-size:12px;transition:.15s;font-family:inherit}
button:hover{border-color:var(--mut)}
button.on{border-color:var(--acc);color:var(--acc);background:#0d2036}
input.search{background:var(--card);border:1px solid var(--line);border-radius:7px;color:var(--fg);
padding:6px 11px;font-size:12px;min-width:210px;font-family:inherit}
select{background:var(--card);border:1px solid var(--line);border-radius:7px;color:var(--fg);
padding:6px 9px;font-size:12px;font-family:inherit}
#shown{font-size:12px;color:var(--mut)}
main{padding:16px 24px 90px;max-width:1280px}
.card{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--mut);
border-radius:9px;margin-bottom:8px}
.card.parsed{border-left-color:var(--ok)}
.card.zero_results{border-left-color:#1f6feb}
.card.blocked{border-left-color:var(--bad);background:linear-gradient(90deg,#241214 0%,var(--card) 22%)}
.card.parse_anomaly{border-left-color:var(--warn);background:linear-gradient(90deg,#241d0c 0%,var(--card) 22%)}
.card.error{border-left-color:var(--pink);background:linear-gradient(90deg,#2a1220 0%,var(--card) 22%)}
.card.not_attempted{border-left-color:#30363d;opacity:.85}
summary{cursor:pointer;padding:10px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;list-style:none}
summary::-webkit-details-marker{display:none}
.rk{color:var(--mut);min-width:30px;font-variant-numeric:tabular-nums;font-size:12px}
.qt{font-weight:600;flex:1;min-width:220px}
.meta{color:var(--mut);font-size:12px}
.tag{font-size:10.5px;padding:2px 8px;border-radius:99px;border:1px solid var(--line);white-space:nowrap}
.tag.parsed{color:#0d1117;background:var(--ok);border-color:var(--ok);font-weight:600}
.tag.zero_results{color:#fff;background:#1f6feb;border-color:#1f6feb;font-weight:600}
.tag.blocked{color:#0d1117;background:var(--bad);border-color:var(--bad);font-weight:600}
.tag.parse_anomaly{color:#0d1117;background:var(--warn);border-color:var(--warn);font-weight:600}
.tag.error{color:#0d1117;background:var(--pink);border-color:var(--pink);font-weight:600}
.tag.not_attempted{color:var(--mut)}
.tag.cat{color:var(--acc);border-color:#1f3b5c}
/* Tables scroll inside their own box. Without this a narrow window makes the whole PAGE
   scroll sideways, which drags the sticky header off screen and hides the run's totals. */
.body{padding:4px 16px 16px;border-top:1px solid var(--line);overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:460px}
thead th{text-align:left;color:var(--mut);font-weight:500;font-size:11px;
text-transform:uppercase;letter-spacing:.5px;padding:8px 8px 8px 0;border-bottom:1px solid var(--line)}
td{padding:7px 8px 7px 0;vertical-align:top;font-size:13px;border-bottom:1px solid #1b2027}
tr:last-child td{border-bottom:none}
.pos{color:var(--mut);font-variant-numeric:tabular-nums;width:34px}
.bt{font-size:10px;padding:2px 7px;border-radius:99px;white-space:nowrap;font-weight:600}
.bt.organic{color:#cfe6ff;background:#12314f}
.bt.places,.bt.local_pack_top,.bt.local_pack_mid,.bt.local_pack_bottom{color:#b7f0c6;background:#10331d}
.bt.local_pack_more_top,.bt.local_pack_more_mid,.bt.local_pack_more_bottom{color:#8fd6a8;background:#0c2717}
.bt.sponsored_top,.bt.sponsored_mid,.bt.sponsored_bottom{color:#f2dda6;background:#3a2c0c}
.bt.ai_overview,.bt.ai_overview_top,.bt.ai_overview_mid{color:#e5d0ff;background:#2d1f47}
.bt.ai_overview_unavailable{color:var(--mut);background:#22272e}
.lk{font-size:10px;padding:2px 7px;border-radius:4px;color:#cfe6ff;background:#12314f;white-space:nowrap}
.lk.no{color:var(--mut);background:#22272e}
.bt.other{color:var(--mut);background:#22272e}
.bk{font-size:10px;padding:2px 7px;border-radius:4px;white-space:nowrap}
.bk.clinic{color:#b7f0c6;background:#10331d}
.bk.aggregator{color:#f2dda6;background:#3a2c0c}
.bk.social{color:#e5d0ff;background:#2d1f47}
.bk.reference{color:var(--mut);background:#22272e}
.bk.hospital{color:#f2b8b5;background:#3a1416}
.ttl{font-weight:500}
.dm{color:var(--acc);font-size:12px;word-break:break-all}
.sn{color:#9aa4af;font-size:12px;margin-top:3px;line-height:1.45}
.rt{color:var(--warn);font-size:12px;white-space:nowrap}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.empty{color:var(--mut);padding:40px;text-align:center}
.note{border:1px solid #5d2220;background:#2a1416;color:#ffb4ae;border-radius:8px;
padding:10px 13px;margin-bottom:10px;font-size:13px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:14px 16px;
margin-bottom:12px;overflow-x:auto}
.panel h3{margin:0 0 11px;font-size:12px;text-transform:uppercase;letter-spacing:.6px;color:var(--mut)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
.bar{display:flex;align-items:center;gap:9px;margin:5px 0}
.bar i{font-style:normal;font-size:11.5px;color:var(--mut);width:104px;flex:none}
.bar u{height:9px;border-radius:5px;text-decoration:none;display:block;min-width:3px;background:var(--acc)}
.bar u.organic{background:#1f6feb} .bar u.places,.bar u.local_pack_top,.bar u.local_pack_mid,.bar u.local_pack_bottom,.bar u.local_pack_more_top,.bar u.local_pack_more_mid,.bar u.local_pack_more_bottom{background:var(--ok)}
.bar u.sponsored_top,.bar u.sponsored_mid,.bar u.sponsored_bottom{background:var(--warn)} .bar u.ai_overview{background:var(--vio)}
.bar s{text-decoration:none;color:var(--mut);font-size:11.5px;font-variant-numeric:tabular-nums}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:9px;font-size:11.5px;color:var(--mut)}
.legend span{display:flex;align-items:center;gap:6px}
.sw{width:11px;height:11px;border-radius:3px;display:inline-block}
</style></head><body>
<header>
  <div class="top">
    <h1>Google Search extraction</h1>
    <span class="sub" id="sub"></span>
    <span class="live" id="live" style="display:none">
      <span class="dot" id="dot"></span><span id="livetxt">connecting…</span>
      <span id="clock" class="stat time" style="padding:3px 10px;min-width:0"></span></span>
  </div>
  <div class="prog" id="progwrap" style="display:none"><i id="bar"></i></div>
  <div class="stats" id="stats"></div>
  <div class="strip" id="strip"></div>
  <nav>
    <button class="on" data-v="queries">Queries</button>
    <button data-v="overview">Overview</button>
    <button data-v="domains">Sites</button>
    <button data-v="places">Local pack</button>
    <button data-v="ai">AI overviews</button>
    <button data-v="clinics">Clinics</button>
    <button data-v="aggregators">Aggregators</button>
    <button data-v="gaps">Gaps</button>
    <span style="width:14px"></span>
    <select id="fstatus"><option value="all">every status</option></select>
    <select id="ftype"><option value="all">any block type</option></select>
    <select id="fcat"><option value="all">any category</option></select>
    <input class="search" id="search" placeholder="search query / clinic / domain…">
    <span id="shown"></span>
  </nav>
  <div class="legend">
    <span><i class="sw" style="background:var(--ok)"></i>parsed</span>
    <span><i class="sw" style="background:#1f6feb"></i>zero results</span>
    <span><i class="sw" style="background:var(--bad)"></i>blocked</span>
    <span><i class="sw" style="background:var(--warn)"></i>anomaly</span>
    <span><i class="sw" style="background:var(--pink)"></i>error</span>
    <span><i class="sw" style="background:#30363d"></i>not attempted</span>
  </div>
</header>
<main id="main"></main>
<script>
/* __DATA__ is the whole dataset for a static file, or null for the live server — in which
   case the page fetches data.json and keeps re-fetching while the scraper works. */
let D = __DATA__;
const LIVE = (D === null);
const $ = s => document.querySelector(s);
const esc = s => (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const TYPES = {organic:'organic',places:'local-pack',
  local_pack_top:'local-pack · top',local_pack_mid:'local-pack · mid',
  local_pack_bottom:'local-pack · bottom',
  local_pack_more_top:'local-pack-more · top',local_pack_more_mid:'local-pack-more · mid',
  local_pack_more_bottom:'local-pack-more · bottom',
  sponsored_top:'sponsored · top',
  sponsored_mid:'sponsored · mid',sponsored_bottom:'sponsored · bottom',
  ai_overview:'AI overview',ai_overview_top:'AI overview · top',
  ai_overview_mid:'AI overview · mid',
  ai_overview_unavailable:'AI overview · declined'};
const STATUS = {parsed:'parsed',zero_results:'zero results',blocked:'blocked',
  parse_anomaly:'anomaly',error:'error',not_attempted:'not attempted'};
let view='queries', term='', fstatus='all', ftype='all', fcat='all', open=new Set();
let CLOCK_SYNC=Date.now();   // when the current D.timer.elapsed_s was measured

/* ---------------------------------------------------------------- header */
function head(){
  const m=D.meta;
  $('#sub').textContent = `${m.run_id} · ${m.practice||''} · ${m.subject_type||''} · ${m.run_date||''}`
    + ` · parser ${m.parser_version}` + ` · built ${(m.generated_at||'').replace('T',' ')}`;
  const sc=D.status_counts||{};
  const cls = m.yield>=0.95?'good':(m.yield>0?'warn':'bad');
  const el=(b,l,c='')=>`<div class="stat ${c}"><b>${b}</b><span>${l}</span></div>`;
  $('#stats').innerHTML =
    el(`${m.captured}/${m.total}`,'captured',cls) +
    el(Math.round((m.yield||0)*100)+'%','yield',cls) +
    el(m.web_signal||'—','web signal',cls) +
    el((m.total_blocks||0).toLocaleString(),'blocks parsed') +
    el(m.google_requests||0,'google requests') +
    el(D.domains.length,'distinct sites') +
    el(D.places.length,'clinics seen in maps') +
    ((sc.blocked||0)?el(sc.blocked,'blocked','bad'):'') +
    ((sc.not_attempted||0)?el(sc.not_attempted,'not attempted','warn'):'') +
    ((sc.parse_anomaly||0)?el(sc.parse_anomaly,'anomalies','warn'):'') +
    ((sc.error||0)?el(sc.error,'errors','bad'):'');
  $('#strip').innerHTML = D.queries.map(q=>
    `<div class="cell ${q.status}" data-rank="${q.rank}" title="q${q.rank} · ${esc(STATUS[q.status]||q.status)} · ${esc(q.query)}"></div>`).join('');
  $('#strip').querySelectorAll('.cell').forEach(c=>c.onclick=()=>{
    /* Drop the filters first. Clicking a cell is a request to SEE that query, and an active
       filter that excludes it would otherwise make the click do nothing at all. */
    const r=c.dataset.rank;
    open.add(String(r));
    clearFilters(false);
    setView('queries');
    const card=document.getElementById('q'+r);
    if(card){ card.open=true; card.scrollIntoView({behavior:'smooth',block:'center'}); }
  });
  fill('#fstatus', Object.keys(STATUS).filter(s=>(sc[s]||0)>0).map(s=>[s,`${STATUS[s]} (${sc[s]})`]));
  fill('#ftype', Object.entries(D.type_counts).sort((a,b)=>b[1]-a[1])
    .map(([t,n])=>[t,`${TYPES[t]||t} (${n})`]));
  fill('#fcat', D.categories.map(c=>[c.category,`${c.category} (${c.total})`]));
}
function fill(sel, pairs){
  const el=$(sel), first=el.options[0];
  el.innerHTML=''; el.appendChild(first);
  pairs.forEach(([v,l])=>{const o=document.createElement('option');o.value=v;o.textContent=l;el.appendChild(o);});
}

/* ---------------------------------------------------------------- blocks */
/* The order a reader wants, which is NOT document order: the AI's answer first, then the map
   box, then the deeper map list, then paid, then organic. Blocks keep their true `position`
   (how far down the page they really sat) — only the grouping changes. */
const ORDER = ['ai_overview_top','ai_overview_mid','ai_overview_unavailable','ai_overview',
  'local_pack_top','local_pack_mid','local_pack_bottom','places',
  'local_pack_more_top','local_pack_more_mid','local_pack_more_bottom',
  'sponsored_top','sponsored_mid','sponsored_bottom','organic'];
const orderOf = t => { const i = ORDER.indexOf(t); return i < 0 ? ORDER.length : i; };
const AITYPES = ['ai_overview_top','ai_overview_mid','ai_overview_unavailable','ai_overview'];
const LOCALPACK = ['local_pack_top','local_pack_mid','local_pack_bottom','places',
  'local_pack_more_top','local_pack_more_mid','local_pack_more_bottom'];

function sortForReading(rows){
  return rows.slice().sort((a,b)=>{
    const d = orderOf(a.block_type) - orderOf(b.block_type);
    return d !== 0 ? d : ((a.position||0) - (b.position||0));
  });
}

function blockRows(blocks, total){
  /* "the filter hid them" and "there were none" are different facts. Saying the second when
     the first is true reports a captured SERP as empty — the exact confusion this whole
     subsystem exists to prevent. */
  if(!blocks.length) return total
    ? `<tr><td colspan="4" class="meta">all ${total} blocks on this page are hidden by the
       active filter &mdash; <button data-clear style="padding:2px 8px">clear filters</button></td></tr>`
    : '<tr><td colspan="4" class="meta">no blocks parsed on this page</td></tr>';
  return sortForReading(blocks).map(b=>{
    const t=b.block_type||'other';
    const bucket = LOCALPACK.includes(t) ? 'clinic' :
      (b.platform==='clinic_site'?'clinic':
       (['practo','justdial','lybrate','sulekha','skedoc','drlogy','apollo247','bajajfinservhealth'].includes(b.platform)?'aggregator':
        (['instagram','youtube','facebook'].includes(b.platform)?'social':'reference')));
    const rt = (b.rating!=null||b.reviews!=null)
      ? `<div class="rt">★${b.rating??'—'}${b.reviews!=null?' ('+b.reviews.toLocaleString()+')':''}</div>` : '';
    /* The AI overview is rendered HERE, in its ordered place, with its full text and the
       clinics it names. It used to also get its own panel above the table, so every query
       with an overview showed it twice. */
    const aiBody = AITYPES.includes(t) && b.ai ? aiInline(b.ai) : '';
    return `<tr>
      <td class="pos">${b.position}</td>
      <td style="width:118px"><span class="bt ${t}">${esc(TYPES[t]||t)}</span></td>
      <td>
        <div class="ttl">${esc(b.title)||'<span class="meta">untitled</span>'}</div>
        ${b.url?`<a class="dm" href="${esc(b.url)}" target="_blank" rel="noopener">${esc(b.domain||b.url)}</a>`
               :(b.domain?`<div class="dm">${esc(b.domain)}</div>`:'')}
        ${b.snippet&&!aiBody?`<div class="sn">${esc(b.snippet)}</div>`:''}
        ${aiBody}
      </td>
      <td style="width:170px">${rt}<span class="bk ${bucket}">${bucket}</span>
        ${b.social_platform?`<span class="lk">${esc(b.social_platform)}</span>`:''}
        ${(t.startsWith('sponsored')||b.social_platform)
          ? (b.linked_clinic?`<span class="lk">→ ${esc(b.linked_clinic)}</span>`
                            :'<span class="lk no">unlinked</span>') : ''}</td>
    </tr>`;
  }).join('');
}

function aiInline(a){
  if(!a||!a.present) return '';
  if(!a.available) return `<div class="sn">Google declined to generate one for this search.
    We waited for it &mdash; this is a refusal, not a timeout.</div>`;
  const recs=(a.recommended_clinics||[]);
  return `<div class="sn" style="white-space:pre-wrap;max-height:260px;overflow:auto">${esc(a.text)}</div>
    <div class="meta" style="margin-top:6px">${a.text_length.toLocaleString()} characters${
      a.truncated?' <span style="color:var(--warn)">(truncated)</span>':''}</div>
    ${recs.length?`<div style="margin-top:6px"><b class="meta">Clinics the AI names, in order</b>
      ${recs.map(r=>`<div class="sn">${r.position}. ${esc(r.name)}</div>`).join('')}</div>`
      :'<div class="meta" style="margin-top:6px">The overview names no clinic.</div>'}`;
}

function queryCard(q){
  const rows = rowsFor(q);
  const shown = filterRows(rows);
  const counts = {};
  rows.forEach(b=>counts[b.block_type]=(counts[b.block_type]||0)+1);
  const chips = Object.entries(counts).sort((a,b)=>orderOf(a[0])-orderOf(b[0]))
    .map(([t,n])=>`<span class="bt ${t}">${esc(TYPES[t]||t)} ${n}</span>`).join(' ');
  const isOpen = open.has(String(q.rank));
  const bad = ['blocked','error','parse_anomaly','not_attempted'].includes(q.status);
  return `<details class="card ${q.status}" id="q${q.rank}" data-rank="${q.rank}" ${isOpen?'open':''}>
    <summary>
      <span class="rk">${q.rank}</span>
      <span class="qt">${esc(q.query)}</span>
      <span class="tag cat">${esc(q.category)}</span>
      <span class="tag ${q.status}">${esc(STATUS[q.status]||q.status)}</span>
      ${q.n_blocks?`<span class="meta">${q.n_blocks} blocks</span>`:''}
      ${chips}
    </summary>
    <div class="body">
      ${bad?`<div class="note"><b>${esc(STATUS[q.status]||q.status)}</b>${
        q.detail?' — '+esc(q.detail):''}. This query holds no data; it is counted against the
        run's total, not hidden from it. Re-running the collector retries it.</div>`:''}
      <div class="meta" style="margin:2px 0 9px">
        ${q.intent?esc(q.intent)+' · ':''}${q.strength!=null?'strength '+q.strength+' · ':''}
        ${q.at?'captured '+esc(q.at.replace('T',' ')):''}
        ${q.screenshot?` · <a href="${esc(q.screenshot)}" target="_blank">screenshot</a>`:''}
        ${q.search_box_text&&q.search_box_text!==q.query
          ? ` · <span style="color:var(--warn)">Google echoed “${esc(q.search_box_text)}”</span>`:''}
      </div>
      ${rows.length?`<table><thead><tr>
        <th>#</th><th>type</th><th>result</th><th>signal</th></tr></thead>
        <tbody>${blockRows(shown, rows.length)}</tbody></table>`:''}
    </div></details>`;
}

/* One list per query: the parsed blocks, plus the "More places" entries folded in as rows of
   their own type. The AI overview carries its full detail here so it renders exactly once, in
   its ordered position — it used to appear both as a panel above the table and as a row in it. */
function rowsFor(q){
  const blocks = (q.blocks||[]).map(b =>
    AITYPES.includes(b.block_type) ? Object.assign({}, b, {ai:q.ai}) : b);
  const more = (q.more_places||[]).map(p => ({
    position: p.position, block_type: p.block_type || 'local_pack_more_top',
    platform: 'clinic_site', title: p.name, domain: '', url: '',
    rating: p.rating, reviews: p.reviews, snippet: p.snippet || ''}));
  return blocks.concat(more);
}

function filterRows(rows){
  let out = rows;
  if(ftype!=='all') out = out.filter(x=>x.block_type===ftype);
  if(term) out = out.filter(x=>((x.title||'')+' '+(x.domain||'')+' '+(x.snippet||'')
    ).toLowerCase().includes(term));
  return out;
}

/* ---------------------------------------------------------------- views */
function viewQueries(){
  let rows=D.queries.slice();
  if(fstatus!=='all') rows=rows.filter(q=>q.status===fstatus);
  if(fcat!=='all') rows=rows.filter(q=>q.category===fcat);
  if(ftype!=='all') rows=rows.filter(q=>(q.blocks||[]).some(b=>b.block_type===ftype));
  if(term) rows=rows.filter(q=>(q.query||'').toLowerCase().includes(term)
    || (q.blocks||[]).some(b=>((b.title||'')+' '+(b.domain||'')+' '+(b.snippet||'')).toLowerCase().includes(term)));
  note(rows.length, D.queries.length, 'queries');
  return rows.length?rows.map(queryCard).join(''):'<div class="empty">nothing matches</div>';
}

function viewOverview(){
  const tc=D.type_counts, tot=Object.values(tc).reduce((a,b)=>a+b,0)||1;
  const bars=Object.entries(tc).sort((a,b)=>b[1]-a[1]).map(([t,n])=>
    `<div class="bar"><i>${esc(TYPES[t]||t)}</i><u class="${t}" style="width:${Math.max(3,Math.round(300*n/tot))}px"></u>
     <s>${n} · ${Math.round(100*n/tot)}%</s></div>`).join('');
  const buckets={clinic:0,aggregator:0,social:0,reference:0};
  D.domains.forEach(d=>buckets[d.bucket]+=d.queries);
  const btot=Object.values(buckets).reduce((a,b)=>a+b,0)||1;
  const bbars=Object.entries(buckets).map(([k,n])=>
    `<div class="bar"><i>${k}</i><u style="width:${Math.max(3,Math.round(300*n/btot))}px;background:${
      {clinic:'var(--ok)',aggregator:'var(--warn)',social:'var(--vio)',reference:'var(--mut)'}[k]}"></u>
     <s>${n} appearances · ${Math.round(100*n/btot)}%</s></div>`).join('');
  const cats=D.categories.map(c=>{
    const pct=c.total?Math.round(100*c.done/c.total):0;
    return `<div class="bar"><i>${esc(c.category)}</i><u style="width:${Math.max(3,pct*2)}px;background:${
      pct===100?'var(--ok)':'var(--warn)'}"></u><s>${c.done}/${c.total} captured</s></div>`;}).join('');
  const sess=(D.sessions||[]).slice().reverse().map(s=>
    `<tr><td>#${s.n}</td><td>${esc(s.mode||'')}</td><td>${esc(s.outcome||'')}</td>
     <td>${s.attempted||0} tried</td><td>${s.captured||0} new</td>
     <td>${s.blocked?'<span style="color:var(--bad)">'+s.blocked+' wall</span>':''}</td>
     <td class="meta">${esc((s.ended_at||'').replace('T',' '))}</td></tr>`).join('');
  note(D.queries.length, D.queries.length, 'queries');
  return `<div class="grid">
    <div class="panel"><h3>Block mix — what a searcher actually meets</h3>${bars}</div>
    <div class="panel"><h3>Owned vs borrowed — appearances by site type</h3>${bbars}
      <div class="legend"><span><i class="sw" style="background:var(--ok)"></i>clinic's own site (owned)</span>
      <span><i class="sw" style="background:var(--warn)"></i>aggregator (borrowed)</span>
      <span><i class="sw" style="background:var(--vio)"></i>social</span>
      <span><i class="sw" style="background:var(--mut)"></i>reference / national</span></div></div>
    <div class="panel"><h3>Capture by query category</h3>${cats}</div>
    ${sess?`<div class="panel"><h3>Collection sessions</h3><table><tbody>${sess}</tbody></table></div>`:''}
  </div>`;
}

function viewDomains(){
  let rows=D.domains.slice();
  if(term) rows=rows.filter(d=>(d.domain+' '+(d.title||'')).toLowerCase().includes(term));
  note(rows.length, D.domains.length, 'sites');
  if(!rows.length) return '<div class="empty">nothing matches</div>';
  return `<div class="panel"><table><thead><tr>
    <th>site</th><th>type</th><th>queries</th><th>best pos</th><th>avg pos</th><th>appears as</th>
    </tr></thead><tbody>${rows.map(d=>`<tr>
      <td><div class="ttl">${esc(d.domain)}</div>${d.title?`<div class="sn">${esc(d.title)}</div>`:''}</td>
      <td><span class="bk ${d.bucket}">${d.bucket}</span></td>
      <td style="font-variant-numeric:tabular-nums"><b>${d.queries}</b></td>
      <td class="pos">${d.best??'—'}</td><td class="pos">${d.avg??'—'}</td>
      <td>${Object.entries(d.types).map(([t,n])=>`<span class="bt ${t}">${esc(TYPES[t]||t)} ${n}</span>`).join(' ')}</td>
    </tr>`).join('')}</tbody></table></div>`;
}

function viewPlaces(){
  const t=term;
  const shown=D.places.filter(p=>!t||p.name.toLowerCase().includes(t));
  const more=(D.places_from_more||[]).filter(p=>!t||p.name.toLowerCase().includes(t));
  note(shown.length+more.length, D.places.length+(D.places_from_more||[]).length,
       'clinics seen in maps');

  const fromResults = shown.length
    ? `<table><thead><tr><th>clinic</th><th>queries</th><th>best pos</th><th>rating</th></tr></thead>
       <tbody>${shown.map(p=>`<tr>
        <td class="ttl">${esc(p.name)}</td>
        <td style="font-variant-numeric:tabular-nums"><b>${p.queries}</b></td>
        <td class="pos">${p.best??'—'}</td>
        <td class="rt">${p.rating!=null?'★'+p.rating:'—'}${p.reviews!=null?' ('+p.reviews.toLocaleString()+')':''}</td>
       </tr>`).join('')}</tbody></table>`
    : '<div class="empty">no map results captured</div>';

  /* Empty and not-yet-collected are different facts, and the section says which. */
  const fromMore = more.length
    ? `<table><thead><tr><th>clinic</th><th>queries</th><th>best pos</th></tr></thead>
       <tbody>${more.map(p=>`<tr><td class="ttl">${esc(p.name)}</td>
        <td style="font-variant-numeric:tabular-nums"><b>${p.queries}</b></td>
        <td class="pos">${p.best??'—'}</td></tr>`).join('')}</tbody></table>`
    : `<p class="meta" style="margin:0">Not collected yet — the runner does not click
       &ldquo;More places&rdquo;. This is empty because nobody has looked, not because Google
       showed nobody.</p>`;

  return `<div class="panel"><h3>local-pack</h3>
      <p class="meta" style="margin:-4px 0 10px">The clinics Google puts on the results page
      itself — usually three. Appearing here is real visibility.</p>${fromResults}</div>
    <div class="panel"><h3>local-pack-more</h3>
      <p class="meta" style="margin:-4px 0 10px">The clinics that only appear after clicking
      &ldquo;More places&rdquo;. Reachable, but a searcher has to ask for them.</p>${fromMore}</div>`;
}

function aiPanel(q){
  /* Printed inside the query card so the answer sits next to the results it displaced. */
  const a=q.ai;
  if(!a||!a.present) return '';
  if(!a.available) return `<div class="panel" style="margin:8px 0">
    <h3>AI overview</h3><p class="meta" style="margin:0">Google declined to generate one for
    this search (&ldquo;can&rsquo;t generate an AI overview right now&rdquo;). We waited for it —
    this is a refusal, not a timeout.</p></div>`;
  const recs=(a.recommended_clinics||[]);
  return `<div class="panel" style="margin:8px 0">
    <h3>AI overview &mdash; ${a.text_length.toLocaleString()} characters${
      a.truncated?' <span style="color:var(--warn)">(truncated)</span>':''}</h3>
    <div class="sn" style="white-space:pre-wrap;max-height:320px;overflow:auto;font-size:13px">${esc(a.text)}</div>
    ${recs.length?`<h3 style="margin-top:12px">Clinics the AI names, in order</h3>
      <table><tbody>${recs.map(r=>`<tr>
        <td class="pos" style="width:34px">${r.position}</td>
        <td class="ttl">${esc(r.name)}</td>
        <td style="width:90px" class="meta">${esc(r.source||'')}</td></tr>`).join('')}</tbody></table>`
      :'<p class="meta" style="margin:10px 0 0">The overview names no clinic.</p>'}
  </div>`;
}

function viewAi(){
  const a=D.ai||{with_overview:0,declined:0,checked:0,recommended_clinics:[]};
  let rows=D.queries.filter(q=>q.ai&&q.ai.present);
  if(term) rows=rows.filter(q=>(q.query+' '+(q.ai.text||'')).toLowerCase().includes(term));
  note(rows.length, D.queries.filter(q=>q.ai&&q.ai.present).length, 'queries with an AI overview');
  const recs=a.recommended_clinics||[];
  return `<div class="panel"><h3>AI overviews across the run</h3>
      <div class="bar"><i>generated</i><u style="width:${Math.max(3,a.with_overview*6)}px;background:var(--ok)"></u>
        <s>${a.with_overview}</s></div>
      <div class="bar"><i>Google declined</i><u style="width:${Math.max(3,a.declined*6)}px;background:var(--warn)"></u>
        <s>${a.declined}</s></div>
      <p class="meta" style="margin:8px 0 0">Checked on ${a.checked} captured queries. A
      declined overview is Google refusing, measured after waiting for generation — not a
      capture that gave up early.</p></div>
    ${recs.length?`<div class="panel"><h3>Clinics recommended by AI, ranked by how often</h3>
      <table><thead><tr><th>clinic</th><th>queries</th><th>best position</th></tr></thead>
      <tbody>${recs.map(r=>`<tr><td class="ttl">${esc(r.name)}</td>
        <td style="font-variant-numeric:tabular-nums"><b>${r.queries}</b></td>
        <td class="pos">${r.best??'—'}</td></tr>`).join('')}</tbody></table></div>`
      :`<div class="panel"><h3>Clinics recommended by AI</h3>
        <p class="meta" style="margin:0">None yet — no generated overview has named a clinic.</p></div>`}
    ${rows.length?rows.map(q=>`<div class="panel"><h3>q${q.rank} &middot; ${esc(q.query)}</h3>
      ${aiPanel(q).replace('<div class="panel" style="margin:8px 0">','<div>')}</div>`).join('')
      :'<div class="empty">no AI overview captured on any query yet</div>'}`;
}

function viewClinics(){
  /* Multispeciality hospitals are excluded from the market view by request — but COUNTED and
     listed below it, because a hospital silently deleted is indistinguishable from one that
     was never found. */
  const all=D.roster||[];
  let rows=all.filter(c=>c.subject_class!=='hospital');
  const hosp=all.filter(c=>c.subject_class==='hospital');
  if(term) rows=rows.filter(c=>c.name.toLowerCase().includes(term));
  note(rows.length, all.filter(c=>c.subject_class!=='hospital').length, 'clinics');
  const src=c=>Object.keys(c.sources||{}).map(k=>
    `<span class="lk">${({map_results:'maps',map_more:'more',ai_overview:'AI'})[k]||k}</span>`).join(' ');
  return `<div class="panel"><h3>Everyone the search results name &mdash; ${rows.length} clinics</h3>
    <p class="meta" style="margin:-4px 0 10px">Merged across spellings, so
    &ldquo;Centre&rdquo; and &ldquo;Center&rdquo; are one business. Built from the map box, the
    expanded list and the AI overview &mdash; no Maps scrape needed.</p>
    <table><thead><tr><th>clinic</th><th>queries</th><th>best pos</th><th>seen in</th><th>class</th></tr></thead>
    <tbody>${rows.map(c=>`<tr>
      <td class="ttl">${esc(c.name)}${(c.variants||[]).length>1
        ? `<div class="sn">also: ${esc(c.variants.filter(v=>v!==c.name).join(' · '))}</div>`:''}</td>
      <td style="font-variant-numeric:tabular-nums"><b>${c.queries}</b></td>
      <td class="pos">${c.best_position??'—'}</td>
      <td>${src(c)}</td>
      <td class="meta">${esc(c.subject_class)}<span class="sn"> ${esc(c.subject_basis||'')}</span></td>
    </tr>`).join('')}</tbody></table></div>
    <div class="panel"><h3>Multispeciality hospitals &mdash; ${hosp.length}, excluded from the market view</h3>
    <p class="meta" style="margin:-4px 0 10px">A hospital runs many practices at once, so it
    out-ranks a solo clinic on volume signals that say nothing about dermatology. Listed here
    rather than deleted.</p>
    ${hosp.length?`<table><tbody>${hosp.map(c=>`<tr><td class="ttl">${esc(c.name)}</td>
      <td style="font-variant-numeric:tabular-nums">${c.queries}x</td>
      <td class="meta">${esc(c.subject_basis||'')}</td></tr>`).join('')}</tbody></table>`
      :'<p class="meta" style="margin:0">None found in this run.</p>'}</div>
    <div class="panel"><h3>Attribution</h3>
      <div class="bar"><i>ads linked</i><u style="width:${Math.max(3,(D.links.sponsored_linked||0)*4)}px;background:var(--warn)"></u>
        <s>${D.links.sponsored_linked||0} of ${D.links.sponsored||0}</s></div>
      <div class="bar"><i>social linked</i><u style="width:${Math.max(3,(D.links.social_linked||0)*4)}px;background:var(--vio)"></u>
        <s>${D.links.social_linked||0} of ${D.links.social||0}</s></div>
      <div class="bar"><i>own-site hits</i><u style="width:${Math.max(3,(D.links.clinic_site||0)/2)}px;background:var(--ok)"></u>
        <s>${D.links.clinic_site||0} results on a clinic's own domain (never opened)</s></div>
      <p class="meta" style="margin:8px 0 0">Unlinked ads and profiles stay visible as
      &ldquo;unlinked&rdquo; rather than being guessed at &mdash; a wrongly attributed ad moves a
      clinic's paid-visibility score.</p></div>`;
}

function viewAggregators(){
  const L=D.listicles||{};
  const pages=L.pages||[];
  if(!pages.length) return `<div class="panel"><h3>Aggregator pages</h3>
    <p class="meta" style="margin:0">Not collected yet. Run
    <code>tools/serp_listicles.py --run &lt;run&gt;</code> &mdash; it opens the Practo/JustDial
    style roundups already found in these results and reads their numbered lists. It touches
    those sites, never Google, so it costs nothing against the CAPTCHA budget.</p></div>`;
  let rows=pages;
  if(term) rows=rows.filter(p=>(p.url+' '+(p.title||'')).toLowerCase().includes(term));
  note(rows.length, pages.length, 'aggregator pages');
  const ranked=L.clinics||[];
  return `${ranked.length?`<div class="panel"><h3>Clinics the aggregators rank</h3>
    <table><thead><tr><th>clinic</th><th>pages</th><th>best rank</th></tr></thead><tbody>
    ${ranked.map(c=>`<tr><td class="ttl">${esc(c.name)}</td>
      <td style="font-variant-numeric:tabular-nums"><b>${c.pages}</b></td>
      <td class="pos">${c.best??'—'}</td></tr>`).join('')}</tbody></table></div>`:''}
    ${rows.map(p=>`<div class="panel">
      <h3>${esc(p.domain||'')} &mdash; ${(p.entries||[]).length} listed</h3>
      <div class="sn" style="margin:-4px 0 8px">${esc(p.title||'')}<br>
        <a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.url)}</a>
        ${p.error?` <span style="color:var(--bad)">${esc(p.error)}</span>`:''}</div>
      ${(p.entries||[]).length?`<table><tbody>${p.entries.map(e=>`<tr>
        <td class="pos" style="width:44px">${e.stated_number??e.position}${
          e.stated_number?'':'<span class="sn"> ~</span>'}</td>
        <td class="ttl">${esc(e.name)}</td></tr>`).join('')}</tbody></table>
        <p class="meta" style="margin:8px 0 0">A tilde marks reading order where the page
        printed no number of its own.</p>`:''}
    </div>`).join('')}`;
}

function viewGaps(){
  const bad=D.queries.filter(q=>!['parsed','zero_results'].includes(q.status));
  /* Count against ITSELF. Routing this through the filter warning would report the captured
     queries as "hidden by filters" — as though the good data were being suppressed. */
  note(bad.length, bad.length, bad.length===1?'query with no data':'queries with no data');
  if(!bad.length) return `<div class="panel"><h3>Gaps</h3>
    <p style="color:var(--ok);margin:0">Every one of the ${D.queries.length} queries in this run
    was captured. Nothing is missing from the dataset.</p></div>`;
  return `<div class="panel"><h3>${bad.length} of ${D.queries.length} queries hold no data</h3>
    <p class="meta" style="margin:0 0 10px">These are counted against the run's denominator. A
    clinic that looks invisible on the web could simply be invisible in <i>this</i> sample —
    re-run the collector to retry them before reading anything into a low score.</p>
    <table><thead><tr><th>#</th><th>query</th><th>status</th><th>reason</th><th>when</th></tr></thead>
    <tbody>${bad.map(q=>`<tr><td class="pos">${q.rank}</td><td class="ttl">${esc(q.query)}</td>
      <td><span class="tag ${q.status}">${esc(STATUS[q.status]||q.status)}</span></td>
      <td class="sn">${esc(q.detail||'—')}</td>
      <td class="meta">${esc((q.at||'').replace('T',' '))}</td></tr>`).join('')}</tbody></table></div>`;
}

function note(shown,total,unit){
  const hidden=total-shown;
  $('#shown').innerHTML = hidden>0
    ? `showing <b>${shown}</b> of ${total} ${unit} — <b>${hidden} hidden by filters</b>
       <button data-clear style="padding:2px 8px;margin-left:6px">clear</button>`
    : `showing all <b>${shown}</b> ${unit}`;
  $('#shown').style.color = hidden>0?'var(--warn)':'var(--mut)';
}

function clearFilters(rerender){
  term='';fstatus='all';ftype='all';fcat='all';
  $('#search').value='';$('#fstatus').value='all';$('#ftype').value='all';$('#fcat').value='all';
  if(rerender!==false) render();
}

function render(){
  const fn={queries:viewQueries,overview:viewOverview,domains:viewDomains,
            places:viewPlaces,ai:viewAi,clinics:viewClinics,
            aggregators:viewAggregators,gaps:viewGaps}[view];
  $('#main').innerHTML = fn();
  $('#main').querySelectorAll('details').forEach(d=>d.addEventListener('toggle',()=>{
    const k=d.dataset.rank; if(d.open) open.add(String(k)); else open.delete(String(k));
  }));
  /* Bind every clear button — the header's and any inside a card. Keying on a single id
     bound only the first one, leaving the rest dead. */
  document.querySelectorAll('[data-clear]').forEach(b=>b.onclick=()=>clearFilters());
}
function setView(v){
  view=v;
  document.querySelectorAll('nav button[data-v]').forEach(b=>b.classList.toggle('on',b.dataset.v===v));
  render();
}
document.querySelectorAll('nav button[data-v]').forEach(b=>b.onclick=()=>setView(b.dataset.v));
$('#search').oninput=e=>{term=e.target.value.toLowerCase().trim();render();};
$('#fstatus').onchange=e=>{fstatus=e.target.value;render();};
$('#ftype').onchange=e=>{ftype=e.target.value;render();};
$('#fcat').onchange=e=>{fcat=e.target.value;render();};

/* ---------------------------------------------------------------- live mode */
function signature(d){
  if(!d) return '';
  const sc=d.status_counts||{}, s=d.session||{};
  return [d.meta.captured,d.meta.total,d.meta.total_blocks,sc.blocked||0,
          sc.parse_anomaly||0,sc.error||0,(d.queries||[]).length,
          s.running?1:0,s.wall?1:0].join('|');
}

/* head() rebuilds the filter dropdowns from the new counts, which would silently reset a
   filter the reader had set. Put their choices back, falling back only if an option really
   has gone away. */
function restoreFilters(){
  const put=(sel,val)=>{const el=$(sel); el.value=val; if(el.value!==val) el.value='all'; return el.value;};
  fstatus=put('#fstatus',fstatus); ftype=put('#ftype',ftype); fcat=put('#fcat',fcat);
  $('#search').value=term;
}

function hhmmss(s){ s=Math.max(0,Math.floor(s));
  const h=Math.floor(s/3600), m=Math.floor(s%3600/60), x=s%60;
  return (h?h+'h ':'')+(h||m?m+'m ':'')+x+'s'; }

/* The clock only advances while the scraper is confirmed to be making progress. It freezes on
   finish, on a wall, on a stall (alive but no heartbeat) and when the process has died — a
   timer still counting after the scraper vanished is how a dead run looks healthy. */
function renderClock(){
  const el=$('#clock'); if(!el||!D||!D.timer) return;
  const t=D.timer, tick=(t.status==='running');
  const base=t.elapsed_s||0;
  const shown = tick ? base + (Date.now()-CLOCK_SYNC)/1000 : base;
  const label={running:'running for',idle:'took',stalled:'STALLED at',died:'STOPPED at'}[t.status]||'';
  el.innerHTML=`<b>${hhmmss(shown)}</b><span>${label}</span>`;
  el.style.borderColor = (t.status==='stalled'||t.status==='died') ? 'var(--bad)' : 'var(--line)';
}

function renderLive(){
  if(!LIVE||!D) return;
  renderClock();
  const m=D.meta, s=D.session||{};
  $('#bar').style.width=(m.total?Math.round(100*m.captured/m.total):0)+'%';
  const dot=$('#dot');
  dot.className='dot'+(s.wall?' wall':(s.running?'':' off'));
  $('#livetxt').innerHTML = s.wall
    ? '<b style="color:var(--bad)">CAPTCHA — solve it in the Chrome window, then press ENTER in the runner console</b>'
    : (s.running ? `extracting… <b>${m.captured}</b>/${m.total} captured`
                 : `not running · ${m.captured}/${m.total} captured`);
}

async function poll(){
  try{
    const r=await fetch('data.json?t='+Date.now());
    if(!r.ok) return;
    const d=await r.json();
    const changed = signature(d)!==signature(D);
    D=d; CLOCK_SYNC=Date.now();
    if(changed){
      const y=window.scrollY;          // a re-render must not throw away the reader's place
      head(); restoreFilters(); render();
      window.scrollTo(0,y);
    }
    renderLive();
  }catch(e){}
}

if(LIVE){
  $('#live').style.display='flex';
  $('#progwrap').style.display='block';
  poll();
  setInterval(poll,3000);
  setInterval(renderClock,1000);      // the clock ticks every second between polls
}else{
  head(); render();
}
</script></body></html>"""
