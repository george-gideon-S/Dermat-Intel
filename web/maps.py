"""Guntur map geometry — projection, simplification, and the two SVG renderings.

Pure functions over plain lists. No I/O, no network, no Pillow: the raw OSM
extract is fetched and reduced ONCE by ``docs/redesign/v4/tools/fetch_osm.py``
into the small committed ``web/guntur-geo.json``, and the build only renders it.
That is what keeps the dist offline and the build reproducible from a clone.

TWO RENDERINGS, ONE EXTRACT
---------------------------
* ``render_map``    — the styled map: major roads, water, parks. One ``<path>``
                      per class, because a path per WAY would be ~300 elements
                      of chrome for no visual gain.
* ``render_dotmap`` — the same city as a dot matrix, which is the on-brand
                      variant: the identity already runs the dot at three scales
                      (matrix numerals, dot-column histograms, the scatter
                      field) and a dotted Guntur makes it four.

The dot map is the size-sensitive one. A dot per lit grid cell would be a few
thousand SVG nodes — hundreds of KB, and enough DOM to threaten the 0.2 ms hover
contract. Instead the lit cells are run-length encoded into horizontal bars and
emitted as ONE path, which is then filled with a one-dot ``<pattern>``. The dots
are painted by the pattern, so their count costs nothing: the file scales with
the city's SILHOUETTE, not with the number of dots.

NO COLOUR IS AUTHORED HERE. Every element carries a class and the fills live in
``web/css/16-map.css`` against palette tokens, so the one-place-for-colour rule
survives a build-time-generated SVG.
"""

from __future__ import annotations

import json
from pathlib import Path

# The Guntur bounding box, from the v4 plan.
BBOX = (16.28, 80.41, 16.33, 80.46)  # south, west, north, east

# Same degree-to-km constants as views.km_from_core, so the map and the
# distance-from-core readings cannot disagree about the shape of the city.
KM_PER_DEG_LAT = 111.0
KM_PER_DEG_LNG = 106.6

VIEW_W = 1000
# Height follows from the bbox's true aspect rather than being assumed square.
VIEW_H = round(VIEW_W
               * ((BBOX[2] - BBOX[0]) * KM_PER_DEG_LAT)
               / ((BBOX[3] - BBOX[1]) * KM_PER_DEG_LNG))

# Road classes, coarsest first. The reference map treatment is "desaturated and
# simplified — major roads, water, parks; no clutter", so residential is read for
# the dot matrix's silhouette but never drawn on the styled map.
ROAD_CLASSES = ("trunk", "primary", "secondary", "tertiary")


def project(lat: float, lng: float) -> tuple[float, float]:
    """lat/lng -> viewBox coordinates. Equirectangular, which is exact enough
    across 5 km and matches km_from_core's own approximation."""
    s, w, n, e = BBOX
    x = (lng - w) / (e - w) * VIEW_W
    y = (n - lat) / (n - s) * VIEW_H          # SVG y grows downward
    return x, y


def _perp_distance(pt, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = pt, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return ((px - (ax + t * dx)) ** 2 + (py - (ay + t * dy)) ** 2) ** 0.5


def simplify(points: list, tol: float = 1.0) -> list:
    """Ramer-Douglas-Peucker. Iterative, because a 300-point way recursing in
    Python is fine but a pathological one is not."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo + 1:
            continue
        worst, worst_i = tol, -1
        for i in range(lo + 1, hi):
            d = _perp_distance(points[i], points[lo], points[hi])
            if d > worst:
                worst, worst_i = d, i
        if worst_i >= 0:
            keep[worst_i] = True
            stack.append((lo, worst_i))
            stack.append((worst_i, hi))
    return [p for p, k in zip(points, keep) if k]


def project_way(geometry: list, tol: float = 1.0) -> list:
    """An OSM ``out geom`` way -> simplified integer viewBox points.

    Rounded to whole units on purpose: at a 1000-unit viewBox one unit is ~5 m,
    finer than anything legible, and integers roughly halve the JSON."""
    pts = [project(p["lat"], p["lon"]) for p in geometry]
    pts = simplify(pts, tol)
    out, last = [], None
    for x, y in pts:
        p = (round(x), round(y))
        if p != last:            # rounding can collapse neighbours
            out.append(p)
            last = p
    return out


def svg_path(ways: list) -> str:
    """Many ways -> one path's `d`. Absolute moves, relative lines: the deltas
    are small integers, so this is markedly shorter than absolute `L`."""
    parts = []
    for way in ways:
        if len(way) < 2:
            continue
        x0, y0 = way[0]
        parts.append(f"M{x0} {y0}")
        cx, cy = x0, y0
        for x, y in way[1:]:
            parts.append(f"l{x - cx} {y - cy}")
            cx, cy = x, y
    return "".join(parts)


# ── The dot matrix ───────────────────────────────────────────────────────────

def rasterize(ways: list, cols: int, rows: int) -> set:
    """Which grid cells the city touches. Every segment is walked rather than
    only its endpoints sampled, or a long straight road would light two cells
    and leave a gap where the road plainly is."""
    cw, ch = VIEW_W / cols, VIEW_H / rows
    cells = set()

    def light(x, y):
        c, r = int(x / cw), int(y / ch)
        if 0 <= c < cols and 0 <= r < rows:
            cells.add((c, r))

    for way in ways:
        for (x0, y0), (x1, y1) in zip(way, way[1:]):
            steps = int(max(abs(x1 - x0) / cw, abs(y1 - y0) / ch)) + 1
            for i in range(steps + 1):
                t = i / steps
                light(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
    return cells


def row_runs(cells: set) -> list:
    """Lit cells -> [(row, first_col, last_col)] horizontal runs. This is the
    compression: a solid band of 40 cells becomes one triple instead of 40."""
    by_row = {}
    for c, r in cells:
        by_row.setdefault(r, []).append(c)
    runs = []
    for r in sorted(by_row):
        cs = sorted(by_row[r])
        start = prev = cs[0]
        for c in cs[1:]:
            if c != prev + 1:
                runs.append((r, start, prev))
                start = c
            prev = c
        runs.append((r, start, prev))
    return runs


def runs_path(runs: list, cols: int, rows: int) -> str:
    """Runs -> one path of rectangles. Filled with the dot pattern, so each
    rectangle becomes a row of dots and the dots themselves cost no bytes.

    Integer coordinates and RELATIVE moves. `z` returns the current point to the
    start of its subpath, so each rectangle can step from the last one by a small
    delta instead of restating an absolute position — which is most of the
    difference between a dot map that fits the budget and one that does not."""
    cw, ch = VIEW_W / cols, VIEW_H / rows
    h = max(1, round(ch))
    parts = ["M0 0"]
    cx = cy = 0
    for r, c0, c1 in runs:
        x, y = round(c0 * cw), round(r * ch)
        w = max(1, round((c1 - c0 + 1) * cw))
        parts.append(f"m{x - cx} {y - cy}h{w}v{h}h-{w}z")
        cx, cy = x, y
    return "".join(parts)


# ── Rendering ────────────────────────────────────────────────────────────────

def _svg_open(extra_class: str) -> str:
    # `meet`, not `slice`. preserveAspectRatio is an SVG ATTRIBUTE — there is no
    # CSS property of that name, so this cannot be overridden from a stylesheet
    # and has to be right here. Cover-scaling sized the dot pattern off the
    # viewport's aspect ratio, which grew 8px dots in a short window and 15px
    # dots in a tall one; a texture needs a predictable pitch more than it needs
    # to reach every corner.
    return (f'<svg class="map {extra_class}" viewBox="0 0 {VIEW_W} {VIEW_H}" '
            f'preserveAspectRatio="xMidYMid meet" aria-hidden="true" '
            f'xmlns="http://www.w3.org/2000/svg">')


def render_map(geo: dict) -> str:
    """The styled map. Water and parks are areas and paint first; roads are
    strokes and sit on top, thickest class last so junctions read correctly."""
    out = [_svg_open("map--real")]
    for key in ("green", "water"):
        d = svg_path(geo.get(key, []))
        if d:
            out.append(f'<path class="map__{key}" d="{d}"/>')
    for cls in ROAD_CLASSES:
        d = svg_path(geo.get("roads", {}).get(cls, []))
        if d:
            out.append(f'<path class="map__road map__road--{cls}" d="{d}"/>')
    out.append("</svg>")
    return "".join(out)


def render_dotmap(geo: dict) -> str:
    """The dot matrix. One pattern, one path — the dot count is free."""
    grid = geo.get("dots", {})
    cols, rows = grid.get("cols", 0), grid.get("rows", 0)
    runs = [tuple(r) for r in grid.get("runs", [])]
    if not runs:
        return ""
    pitch = VIEW_W / cols
    d = runs_path(runs, cols, rows)
    return "".join([
        _svg_open("map--dots"),
        f'<defs><pattern id="di-dotgrid" width="{pitch:.3f}" height="{pitch:.3f}" '
        f'patternUnits="userSpaceOnUse">',
        f'<circle class="map__dot" cx="{pitch / 2:.3f}" cy="{pitch / 2:.3f}" '
        f'r="{pitch * 0.28:.3f}"/>',
        '</pattern></defs>',
        f'<path class="map__dotfill" fill="url(#di-dotgrid)" d="{d}"/>',
        "</svg>",
    ])


def load_geo(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
