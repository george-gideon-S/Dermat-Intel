"""Serve the codebase-memory knowledge graph as an interactive map on localhost.

The MCP writes its index to .codebase-memory/graph.db.zst — a zstd-compressed SQLite
file of (nodes, edges). This reads it directly, keeps the code entities worth looking at
(functions, methods, classes, routes) and drops the ~24k Variable nodes that would bury
them, lays the result out with a force simulation, and writes ONE self-contained HTML
page which it then serves.

    python tools/graph_viewer.py                 # build + serve on http://127.0.0.1:8765
    python tools/graph_viewer.py --port 9000
    python tools/graph_viewer.py --no-serve      # just write the page

Re-run it after re-indexing; the page is derived data and lives in the gitignored
.codebase-memory/viewer/.
"""
from __future__ import annotations

# Embeddable-Python bootstrap: the interpreter runs isolated, so the repo root is not on
# sys.path unless we put it there. Every entry point needs these three lines.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import io
import json
import sqlite3
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / ".codebase-memory" / "graph.db.zst"
OUT_DIR = ROOT / ".codebase-memory" / "viewer"

# What a human actually wants to see: the call graph, not every local variable.
KEEP_LABELS = {"Function", "Method", "Class", "Route"}
KEEP_EDGES = {"CALLS", "TESTS", "DEFINES_METHOD", "HANDLES", "HTTP_CALLS"}


def load_graph(artifact: Path) -> tuple[list[dict], list[tuple[int, int, str]]]:
    """Decompress the artifact to a temp file and pull nodes + edges out of SQLite."""
    import zstandard

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "graph.db"
        with artifact.open("rb") as fi, db.open("wb") as fo:
            zstandard.ZstdDecompressor().copy_stream(fi, fo)
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row

        nodes: dict[int, dict] = {}
        for r in con.execute(
            "SELECT id, label, name, qualified_name, file_path, start_line, properties "
            "FROM nodes WHERE label IN (%s)" % ",".join("?" * len(KEEP_LABELS)),
            tuple(KEEP_LABELS),
        ):
            try:
                props = json.loads(r["properties"] or "{}")
            except (ValueError, TypeError):
                props = {}
            f = (r["file_path"] or "").replace("\\", "/")
            nodes[int(r["id"])] = {
                "id": int(r["id"]),
                "name": r["name"] or "?",
                "qn": r["qualified_name"] or "",
                "label": r["label"],
                "file": f,
                "line": int(r["start_line"] or 0),
                # Root-level files share one bucket; otherwise the legend fills with
                # single-file "folders" named config.py, run_market.py, ...
                "group": f.split("/")[0] if "/" in f else "root",
                "cx": int(props.get("complexity") or 0),
                "lines": int(props.get("lines") or 0),
                # is_test is not always populated by the indexer, so fall back to the
                # convention the suite actually follows: tests/ or a test_ prefix.
                "test": bool(props.get("is_test")) or f.startswith("tests/")
                        or f.split("/")[-1].startswith("test_"),
                "route": props.get("route_path") or "",
            }

        edges = []
        for r in con.execute(
            "SELECT source_id, target_id, type FROM edges WHERE type IN (%s)"
            % ",".join("?" * len(KEEP_EDGES)),
            tuple(KEEP_EDGES),
        ):
            s, t = int(r["source_id"]), int(r["target_id"])
            if s in nodes and t in nodes and s != t:
                edges.append((s, t, r["type"]))
        con.close()
    return list(nodes.values()), edges


def layout(nodes, edges, iters: int = 320) -> None:
    """Fruchterman-Reingold layout, computed here so the browser opens to a settled map.

    Scaling matters more than iteration count: repulsion is k^2/d and attraction d^2/k
    around an ideal edge length k, with per-step displacement capped by a cooling
    temperature. Get that ratio wrong and every node drifts to the rim, leaving a hollow
    ring instead of the module structure you are trying to see.
    """
    import math

    import numpy as np

    n = len(nodes)
    idx = {node["id"]: i for i, node in enumerate(nodes)}
    rng = np.random.RandomState(7)

    area = 1_400_000.0
    k = math.sqrt(area / max(n, 1))          # ideal distance between neighbours
    temp = 0.10 * math.sqrt(area)

    # Seed each folder in its own sector: a sane basin for the simulation to fall into,
    # so subsystems land together instead of being shredded across the canvas.
    groups = sorted({node["group"] for node in nodes})
    ring = {g: i for i, g in enumerate(groups)}
    pos = np.zeros((n, 2), dtype=np.float32)
    for node in nodes:
        i, gi = idx[node["id"]], ring[node["group"]]
        a = 2 * math.pi * gi / max(len(groups), 1)
        pos[i] = [math.cos(a) * k * 4 + rng.randn() * k,
                  math.sin(a) * k * 4 + rng.randn() * k]

    src = np.array([idx[s] for s, _, _ in edges], dtype=np.int32)
    dst = np.array([idx[t] for _, t, _ in edges], dtype=np.int32)
    deg = np.ones(n, dtype=np.float32)
    for s, t, _ in edges:
        deg[idx[s]] += 1
        deg[idx[t]] += 1

    eps = 1e-3
    for _ in range(iters):
        diff = pos[:, None, :] - pos[None, :, :]
        dist = np.sqrt((diff * diff).sum(-1)) + eps
        force = (diff / dist[:, :, None] * (k * k / dist)[:, :, None]).sum(1)

        if len(src):
            ed = pos[src] - pos[dst]
            ed_d = np.sqrt((ed * ed).sum(-1)) + eps
            pull = ed / ed_d[:, None] * (ed_d * ed_d / k)[:, None]
            np.add.at(force, src, -pull)
            np.add.at(force, dst, pull)

        force -= pos * 0.06 * k              # gentle centring so components stay on screen

        mag = np.sqrt((force * force).sum(-1)) + eps
        pos += force / mag[:, None] * np.minimum(mag, temp)[:, None]
        temp = max(temp * 0.97, 0.6)

    pos -= pos.mean(0)
    for node in nodes:
        i = idx[node["id"]]
        node["x"], node["y"] = round(float(pos[i][0]), 1), round(float(pos[i][1]), 1)
        node["deg"] = int(deg[i] - 1)


PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__PROJECT__ — knowledge graph</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  html, body { margin:0; height:100%; background:#0d1117; color:#c9d1d9;
    font:13px/1.5 ui-sans-serif, system-ui, "Segoe UI", sans-serif; overflow:hidden; }
  #cv { position:fixed; inset:0; cursor:grab; }
  #cv.drag { cursor:grabbing; }
  .panel { position:fixed; background:rgba(22,27,34,.94); border:1px solid #30363d;
    border-radius:10px; backdrop-filter:blur(8px); }
  #ui { top:14px; left:14px; padding:14px; width:288px; max-height:calc(100vh - 28px);
    overflow:auto; }
  h1 { margin:0 0 2px; font-size:14px; font-weight:600; color:#e6edf3; }
  .sub { color:#7d8590; font-size:11px; margin-bottom:12px; }
  input[type=search] { width:100%; padding:7px 10px; margin-bottom:10px; background:#0d1117;
    border:1px solid #30363d; border-radius:7px; color:#e6edf3; font:inherit; outline:none; }
  input[type=search]:focus { border-color:#58a6ff; }
  .row { display:flex; align-items:center; gap:8px; padding:3px 0; cursor:pointer;
    user-select:none; }
  .row:hover { color:#e6edf3; }
  .sw { width:10px; height:10px; border-radius:3px; flex:none; }
  .row.off { opacity:.35; }
  .row .n { margin-left:auto; color:#7d8590; font-variant-numeric:tabular-nums; font-size:11px; }
  .sec { margin:12px 0 5px; font-size:10px; letter-spacing:.08em; text-transform:uppercase;
    color:#7d8590; }
  #tip { position:fixed; padding:9px 11px; pointer-events:none; display:none; max-width:340px;
    z-index:9; }
  #tip b { color:#e6edf3; display:block; margin-bottom:3px; font-size:13px; }
  #tip .m { color:#7d8590; font-size:11px; font-family:ui-monospace, monospace;
    word-break:break-all; }
  #tip .s { color:#58a6ff; font-size:11px; margin-top:5px; }
  #det { bottom:14px; left:318px; padding:13px; width:400px; display:none; max-height:44vh;
    overflow:auto; }
  #det h2 { margin:0 0 3px; font-size:13px; color:#e6edf3; }
  #det .m { color:#7d8590; font-size:11px; font-family:ui-monospace,monospace;
    word-break:break-all; margin-bottom:9px; white-space:pre-line; }
  #det ul { margin:3px 0 9px; padding-left:16px; }
  #det li { color:#8b949e; font-size:11px; font-family:ui-monospace,monospace;
    cursor:pointer; padding:1px 0; }
  #det li:hover { color:#58a6ff; }
  #det .k { font-size:10px; letter-spacing:.06em; text-transform:uppercase; color:#7d8590; }
  #hint { bottom:14px; right:14px; padding:8px 12px; color:#7d8590; font-size:11px; }
  button.x { position:absolute; top:9px; right:11px; background:none; border:0;
    color:#7d8590; cursor:pointer; font-size:16px; line-height:1; }
</style></head><body>
<canvas id="cv"></canvas>
<div id="ui" class="panel">
  <h1>__PROJECT__</h1>
  <div class="sub">__NNODES__ code entities · __NEDGES__ relationships<br>indexed __WHEN__</div>
  <input type="search" id="q" placeholder="Search functions…" autocomplete="off">
  <div class="sec">Folders</div><div id="groups"></div>
  <div class="sec">Show</div>
  <div class="row" id="tt"><span class="sw" style="background:#8b949e"></span>tests
    <span class="n" id="ttn"></span></div>
  <div class="sec">Edges</div><div id="etypes"></div>
</div>
<div id="tip" class="panel"></div>
<div id="det" class="panel"><button class="x" onclick="clearSel()">×</button><div id="detc"></div></div>
<div id="hint" class="panel">drag to pan · scroll to zoom · click a node</div>
<script>
const DATA = __DATA__;
const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
const N = DATA.nodes, E = DATA.edges;
const byId = new Map(N.map(n => [n.id, n]));
const PAL = ['#58a6ff','#3fb950','#d29922','#f85149','#bc8cff','#39c5cf','#db6d28',
             '#a5d6ff','#7ee787','#ffa198','#d2a8ff','#56d4dd'];
const groups = [...new Set(N.map(n => n.group))].sort();
const gcol = new Map(groups.map((g,i) => [g, PAL[i % PAL.length]]));
const etypes = [...new Set(E.map(e => e[2]))].sort();
const offG = new Set(), offE = new Set();
let showTests = true, sel = null;
let scale = 1, ox = 0, oy = 0;

const adj = new Map();
for (const e of E) {
  const s = e[0], t = e[1];
  if (!adj.has(s)) adj.set(s, new Set());
  if (!adj.has(t)) adj.set(t, new Set());
  adj.get(s).add(t); adj.get(t).add(s);
}
const vis = n => !offG.has(n.group) && (showTests || !n.test);
const rad = n => Math.min(3 + Math.sqrt(n.deg) * 1.5, 13);
const sx = n => n.x*scale + ox, sy = n => n.y*scale + oy;

function resize() {
  const d = window.devicePixelRatio || 1;
  cv.width = innerWidth * d; cv.height = innerHeight * d;
  cv.style.width = innerWidth + 'px'; cv.style.height = innerHeight + 'px';
  ctx.setTransform(d,0,0,d,0,0); draw();
}
function fit() {
  const v = N.filter(vis); if (!v.length) return;
  const xs = v.map(n=>n.x), ys = v.map(n=>n.y);
  const minx = Math.min(...xs), maxx = Math.max(...xs);
  const miny = Math.min(...ys), maxy = Math.max(...ys);
  scale = Math.min((innerWidth-380)/(maxx-minx+120), (innerHeight-140)/(maxy-miny+120), 2.2);
  ox = innerWidth/2 + 130 - ((maxx+minx)/2)*scale;
  oy = innerHeight/2 - ((maxy+miny)/2)*scale;
}

function draw() {
  ctx.clearRect(0,0,innerWidth,innerHeight);
  const q = document.getElementById('q').value.trim().toLowerCase();
  const near = sel ? adj.get(sel.id) : null;

  ctx.lineWidth = 1;
  if (sel) {
    for (const e of E) {
      if (offE.has(e[2])) continue;
      if (e[0] !== sel.id && e[1] !== sel.id) continue;
      const a = byId.get(e[0]), b = byId.get(e[1]);
      if (!a || !b || !vis(a) || !vis(b)) continue;
      ctx.strokeStyle = 'rgba(88,166,255,.75)';
      ctx.beginPath(); ctx.moveTo(sx(a),sy(a)); ctx.lineTo(sx(b),sy(b)); ctx.stroke();
    }
  } else {
    ctx.strokeStyle = 'rgba(139,148,158,.11)';
    ctx.beginPath();
    for (const e of E) {
      if (offE.has(e[2])) continue;
      const a = byId.get(e[0]), b = byId.get(e[1]);
      if (!a || !b || !vis(a) || !vis(b)) continue;
      ctx.moveTo(sx(a),sy(a)); ctx.lineTo(sx(b),sy(b));
    }
    ctx.stroke();
  }
  for (const n of N) {
    if (!vis(n)) continue;
    const hit = q && (n.name.toLowerCase().includes(q) || n.file.toLowerCase().includes(q));
    const dim = (q && !hit) || (sel && sel.id !== n.id && !near.has(n.id));
    ctx.globalAlpha = dim ? 0.13 : 1;
    ctx.beginPath(); ctx.arc(sx(n), sy(n), rad(n), 0, 6.284);
    ctx.fillStyle = gcol.get(n.group); ctx.fill();
    if (n.label === 'Route') { ctx.strokeStyle='#ffffff'; ctx.lineWidth=1.6; ctx.stroke(); }
    if (hit || (sel && sel.id === n.id)) {
      ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(sx(n),sy(n),rad(n)+3.5,0,6.284); ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
  if (scale > 1.15) {
    ctx.fillStyle = '#8b949e'; ctx.font = '10px ui-sans-serif, system-ui';
    for (const n of N) {
      if (!vis(n) || n.deg < 2) continue;
      if (sel && sel.id !== n.id && !near.has(n.id)) continue;
      ctx.fillText(n.name, sx(n)+rad(n)+4, sy(n)+3);
    }
  }
}
function pick(mx,my) {
  let best = null, bd = 1e9;
  for (const n of N) {
    if (!vis(n)) continue;
    const d = Math.hypot(sx(n)-mx, sy(n)-my);
    if (d < rad(n)+5 && d < bd) { bd = d; best = n; }
  }
  return best;
}
let drag = null;
cv.addEventListener('mousedown', e => {
  drag = {x:e.clientX, y:e.clientY, ox:ox, oy:oy, moved:false};
  cv.classList.add('drag');
});
addEventListener('mouseup', e => {
  if (drag && !drag.moved) { sel = pick(e.clientX, e.clientY) || null; showDetail(); }
  drag = null; cv.classList.remove('drag'); draw();
});
addEventListener('mousemove', e => {
  if (drag) {
    if (Math.abs(e.clientX-drag.x) + Math.abs(e.clientY-drag.y) > 3) drag.moved = true;
    ox = drag.ox + e.clientX - drag.x; oy = drag.oy + e.clientY - drag.y; draw(); return;
  }
  const n = pick(e.clientX, e.clientY), tip = document.getElementById('tip');
  if (n) {
    tip.style.display = 'block';
    tip.style.left = Math.min(e.clientX+14, innerWidth-354) + 'px';
    tip.style.top = (e.clientY+14) + 'px';
    tip.replaceChildren();
    const b = document.createElement('b'); b.textContent = n.name;
    const m = document.createElement('div'); m.className='m'; m.textContent = n.file+':'+n.line;
    const s = document.createElement('div'); s.className='s';
    s.textContent = n.label + ' · ' + n.deg + ' links · complexity ' + n.cx + ' · '
      + n.lines + ' lines' + (n.route ? ' · ' + n.route : '');
    tip.append(b,m,s);
  } else tip.style.display = 'none';
});
cv.addEventListener('wheel', e => {
  e.preventDefault();
  const f = e.deltaY < 0 ? 1.12 : 1/1.12, ns = Math.max(.15, Math.min(6, scale*f));
  ox = e.clientX - (e.clientX-ox) * (ns/scale); oy = e.clientY - (e.clientY-oy) * (ns/scale);
  scale = ns; draw();
}, {passive:false});

function showDetail() {
  const d = document.getElementById('det'), c = document.getElementById('detc');
  if (!sel) { d.style.display='none'; return; }
  const uniq = ids => [...new Set(ids)].map(i => byId.get(i)).filter(Boolean);
  const outs = uniq(E.filter(e => e[0]===sel.id).map(e => e[1]));
  const ins  = uniq(E.filter(e => e[1]===sel.id).map(e => e[0]));
  c.replaceChildren();
  const h2 = document.createElement('h2'); h2.textContent = sel.name;
  const m = document.createElement('div'); m.className = 'm';
  m.textContent = sel.qn + '\n' + sel.file + ':' + sel.line;
  c.append(h2, m);
  const list = (title, arr) => {
    if (!arr.length) return;
    const k = document.createElement('div'); k.className='k';
    k.textContent = title + ' (' + arr.length + ')';
    const ul = document.createElement('ul');
    for (const node of arr.slice(0,40)) {
      const li = document.createElement('li');
      li.textContent = node.name + '  —  ' + node.file.split('/').pop();
      li.onclick = () => { sel = node; showDetail(); centerOn(node); };
      ul.appendChild(li);
    }
    c.append(k, ul);
  };
  list('calls out to', outs); list('called by', ins);
  d.style.display='block'; draw();
}
function centerOn(n) {
  scale = Math.max(scale, 1.4);
  ox = innerWidth/2 + 130 - n.x*scale; oy = innerHeight/2 - n.y*scale; draw();
}
window.clearSel = () => { sel = null; showDetail(); draw(); };

const gd = document.getElementById('groups');
for (const g of groups) {
  const cnt = N.filter(n => n.group === g).length;
  const r = document.createElement('div'); r.className = 'row';
  const sw = document.createElement('span'); sw.className='sw'; sw.style.background = gcol.get(g);
  const lb = document.createElement('span'); lb.textContent = g;
  const nn = document.createElement('span'); nn.className='n'; nn.textContent = cnt;
  r.append(sw, lb, nn);
  r.onclick = () => { offG.has(g) ? offG.delete(g) : offG.add(g); r.classList.toggle('off'); draw(); };
  gd.appendChild(r);
}
const ed = document.getElementById('etypes');
for (const t of etypes) {
  const r = document.createElement('div'); r.className='row';
  const sw = document.createElement('span'); sw.className='sw'; sw.style.background='#484f58';
  const lb = document.createElement('span'); lb.textContent = t.toLowerCase();
  const nn = document.createElement('span'); nn.className='n';
  nn.textContent = E.filter(e => e[2]===t).length;
  r.append(sw, lb, nn);
  r.onclick = () => { offE.has(t) ? offE.delete(t) : offE.add(t); r.classList.toggle('off'); draw(); };
  ed.appendChild(r);
}
document.getElementById('ttn').textContent = N.filter(n => n.test).length;
document.getElementById('tt').onclick = function() {
  showTests = !showTests; this.classList.toggle('off'); draw();
};
document.getElementById('q').addEventListener('input', draw);
addEventListener('resize', resize);
addEventListener('keydown', e => { if (e.key === 'Escape') clearSel(); });
fit(); resize();
</script></body></html>"""


def build(nodes, edges, project: str, when: str) -> str:
    payload = {
        "nodes": [
            {k: n[k] for k in
             ("id", "name", "qn", "label", "file", "line", "group", "cx", "lines",
              "test", "route", "x", "y", "deg")}
            for n in nodes
        ],
        "edges": [[s, t, ty] for s, t, ty in edges],
    }
    return (PAGE
            .replace("__PROJECT__", project)
            .replace("__NNODES__", f"{len(nodes):,}")
            .replace("__NEDGES__", f"{len(edges):,}")
            .replace("__WHEN__", when)
            .replace("__DATA__", json.dumps(payload, separators=(",", ":"))))


def main() -> None:
    ap = argparse.ArgumentParser(description="Serve the codebase-memory knowledge graph.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-serve", action="store_true")
    ap.add_argument("--rebuild", action="store_true",
                    help="re-read the index even if the page is already current")
    args = ap.parse_args()

    if not ARTIFACT.exists():
        raise SystemExit(f"no index at {ARTIFACT} — run the codebase-memory indexer first")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    page = OUT_DIR / "index.html"

    # Decompressing 27 MB and re-running the layout costs ~50s. Do it only when the index
    # is newer than the page, so restarting the server binds its port immediately.
    current = page.exists() and page.stat().st_mtime >= ARTIFACT.stat().st_mtime
    if current and not args.rebuild:
        print(f"page is current ({page.stat().st_size/1024:.0f} KB) — pass --rebuild to redo it")
    else:
        meta = json.loads((ARTIFACT.parent / "artifact.json").read_text(encoding="utf-8"))
        print(f"reading {ARTIFACT.name} ...")
        nodes, edges = load_graph(ARTIFACT)
        print(f"  {len(nodes):,} entities, {len(edges):,} relationships (Variables dropped)")
        print("laying out ...")
        layout(nodes, edges)
        page.write_text(build(nodes, edges, meta.get("project", "codebase"),
                              meta.get("indexed_at", "")[:16].replace("T", " ")),
                        encoding="utf-8")
        print(f"wrote {page}  ({page.stat().st_size/1024:.0f} KB)")

    if args.no_serve:
        return
    import http.server
    import socketserver

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(OUT_DIR), **kw)

        def log_message(self, *a):  # keep the console quiet
            pass

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as srv:
        print(f"serving http://127.0.0.1:{args.port}/  (ctrl-c to stop)")
        srv.serve_forever()


if __name__ == "__main__":
    main()
