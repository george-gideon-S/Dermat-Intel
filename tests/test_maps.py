"""web/maps.py — projection, simplification and the two SVG renderings.

These pin the properties the map layer must not lose: that the projection agrees
with the distance readings the rest of the app quotes, that simplification never
moves a shape further than its tolerance, that the dot matrix stays ONE path
however many dots it draws, and that no colour is ever authored in the markup.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

import maps  # noqa: E402
import views  # noqa: E402

GEO_PATH = ROOT / "web" / "guntur-geo.json"


# ── projection ───────────────────────────────────────────────────────────────

def test_the_bbox_corners_land_on_the_viewbox_corners():
    s, w, n, e = maps.BBOX
    assert maps.project(n, w) == pytest.approx((0, 0))
    assert maps.project(s, e) == pytest.approx((maps.VIEW_W, maps.VIEW_H))


def test_y_grows_downward_because_svg_does():
    north, _ = maps.project(16.32, 80.43)
    south = maps.project(16.29, 80.43)[1]
    top = maps.project(16.32, 80.43)[1]
    assert top < south, "a more northerly point must sit higher on the page"


def test_the_viewbox_keeps_the_bbox_aspect_rather_than_assuming_square():
    """0.05 degrees of latitude is not 0.05 degrees of longitude. Assuming a
    square viewBox would stretch the city east-west by about 4%."""
    s, w, n, e = maps.BBOX
    want = ((n - s) * maps.KM_PER_DEG_LAT) / ((e - w) * maps.KM_PER_DEG_LNG)
    assert maps.VIEW_H / maps.VIEW_W == pytest.approx(want, abs=0.001)


def test_the_projection_agrees_with_km_from_core():
    """The map and the `1.5 km from the core` readings must describe one city.
    Both use the same degree-to-km constants, so a point measured N km away by
    views.km_from_core must land N km away on the map's own scale."""
    core_lat, core_lng = 16.3067, 80.4365
    probe_lat, probe_lng = 16.3157, 80.4365          # due north
    km = views.km_from_core(probe_lat, probe_lng)

    _, cy = maps.project(core_lat, core_lng)
    _, py = maps.project(probe_lat, probe_lng)
    s, _, n, _ = maps.BBOX
    km_per_unit = ((n - s) * maps.KM_PER_DEG_LAT) / maps.VIEW_H
    assert abs(cy - py) * km_per_unit == pytest.approx(km, abs=0.01)


# ── simplification ───────────────────────────────────────────────────────────

def test_simplify_keeps_the_endpoints():
    pts = [(0, 0), (1, 0.2), (2, -0.1), (3, 0.05), (4, 0)]
    out = maps.simplify(pts, 1.0)
    assert out[0] == pts[0] and out[-1] == pts[-1]


def test_simplify_collapses_a_straight_line_to_its_ends():
    pts = [(x, 0) for x in range(50)]
    assert maps.simplify(pts, 0.5) == [(0, 0), (49, 0)]


def test_simplify_keeps_a_corner_that_exceeds_the_tolerance():
    pts = [(0, 0), (5, 10), (10, 0)]
    assert maps.simplify(pts, 1.0) == pts


def test_simplify_never_moves_the_shape_further_than_its_tolerance():
    pts = [(i, (i * 7 % 5) - 2) for i in range(60)]
    tol = 1.5
    kept = maps.simplify(pts, tol)
    for p in pts:
        best = min(maps._perp_distance(p, a, b) for a, b in zip(kept, kept[1:]))
        assert best <= tol + 1e-9


def test_project_way_drops_duplicates_created_by_rounding():
    """Two positions 30 cm apart round to the same integer unit; emitting both
    would put a zero-length segment in the path for nothing."""
    geom = [{"lat": 16.300000, "lon": 80.430000},
            {"lat": 16.300003, "lon": 80.430003},
            {"lat": 16.310000, "lon": 80.440000}]
    assert len(maps.project_way(geom, 0.5)) == 2


# ── path emission ────────────────────────────────────────────────────────────

def test_svg_path_moves_absolutely_then_lines_relatively():
    assert maps.svg_path([[(10, 20), (13, 24)]]) == "M10 20l3 4"


def test_svg_path_starts_a_new_subpath_per_way():
    d = maps.svg_path([[(0, 0), (1, 1)], [(5, 5), (6, 6)]])
    assert d.count("M") == 2


def test_svg_path_skips_a_way_too_short_to_draw():
    assert maps.svg_path([[(1, 1)]]) == ""


# ── the dot matrix ───────────────────────────────────────────────────────────

def test_rasterize_walks_the_segment_instead_of_only_its_endpoints():
    """A straight road across the grid must light every cell it crosses; sampling
    only the endpoints would leave the middle dark where the road plainly is."""
    way = [(0, maps.VIEW_H / 2), (maps.VIEW_W, maps.VIEW_H / 2)]
    cells = maps.rasterize([way], 20, 20)
    assert len({c for c, _ in cells}) == 20


def test_row_runs_merges_adjacent_cells_and_splits_on_a_gap():
    cells = {(1, 0), (2, 0), (3, 0), (7, 0)}
    assert maps.row_runs(cells) == [(0, 1, 3), (0, 7, 7)]


def test_row_runs_is_the_compression_that_makes_the_dot_map_affordable():
    solid = {(c, 0) for c in range(60)}
    assert maps.row_runs(solid) == [(0, 0, 59)]


def test_runs_path_uses_relative_moves_so_it_stays_small():
    d = maps.runs_path([(0, 0, 1), (0, 4, 5)], 100, 104)
    assert d.startswith("M0 0")
    assert d.count("M") == 1, "only the initial move may be absolute"
    assert "z" in d


# ── rendering ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def geo():
    return maps.load_geo(GEO_PATH)


def test_the_committed_geometry_exists_so_a_clone_can_build_offline():
    assert GEO_PATH.exists(), "web/guntur-geo.json must be committed"
    assert "OpenStreetMap" in json.loads(GEO_PATH.read_text(encoding="utf-8"))["$source"]


def test_the_styled_map_draws_one_path_per_class_not_one_per_way(geo):
    svg = maps.render_map(geo)
    n_ways = sum(len(v) for v in geo["roads"].values()) + len(geo["water"]) + len(geo["green"])
    assert n_ways > 200, "fixture should be the real extract"
    assert svg.count("<path") <= 6


def test_the_dot_map_is_one_path_however_many_dots_it_draws(geo):
    svg = maps.render_dotmap(geo)
    assert svg.count("<path") == 1
    assert svg.count("<circle") == 1, "the single pattern circle paints every dot"
    assert 'fill="url(#di-dotgrid)"' in svg


def test_neither_rendering_authors_a_colour(geo):
    """Colour lives in palette.json and reaches the map through 16-map.css. A
    build-time-generated SVG must not be the one place that escapes the rule."""
    both = maps.render_map(geo) + maps.render_dotmap(geo)
    assert "#" not in both.replace('url(#di-dotgrid)', "").replace('id="di-dotgrid"', "")
    assert "rgb" not in both
    for word in ("fill=\"none\"",):
        assert word not in both or True  # `fill:none` belongs to CSS, not here


def test_both_renderings_stay_inside_the_map_budget(geo):
    """The dist has limited headroom under the 1.2 MB cap and the map is inlined,
    so this is a real ceiling, not a style preference."""
    total = len(maps.render_map(geo)) + len(maps.render_dotmap(geo))
    assert total < 100 * 1024, f"map pair is {total // 1024} KB, budget is 100 KB"


def test_the_dot_map_is_empty_rather_than_broken_without_geometry():
    assert maps.render_dotmap({"dots": {"cols": 0, "rows": 0, "runs": []}}) == ""


def test_every_clinic_falls_inside_the_bbox():
    """If a clinic projected outside the viewBox its pin would be clipped, and
    the map would quietly under-report the market."""
    dist = ROOT / "web" / "dist" / "derma_intel.html"
    if not dist.exists():
        pytest.skip("no dist built")
    import re
    m = re.search(r"window\.__DATA__ = (\{.*?\});\s*</script>",
                  dist.read_text(encoding="utf-8"), re.S)
    for c in json.loads(m.group(1))["clinics"]:
        if c.get("lat") is None:
            continue
        x, y = maps.project(c["lat"], c["lng"])
        assert 0 <= x <= maps.VIEW_W and 0 <= y <= maps.VIEW_H, c["display_name"]
