"""`payload.geo` — the projection MK-01 draws its pins with.

The map card clones the styled SVG out of `<template id="di-mapcard">` and lays a
second SVG of 34 pins over it in the same viewBox. The browser therefore has to
reproduce `maps.project` exactly; the alternative — recomputing VIEW_H in JS from
the bbox and the degree constants — puts every pin a fraction of a kilometre off
the moment the two roundings disagree.

So the bbox and the viewBox travel in the payload, and these tests pin the JS
formula (transcribed below, once) to the Python one it mirrors.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

import maps  # noqa: E402

MARKET_JS = (ROOT / "web" / "js" / "85-panels-market.js").read_text(encoding="utf-8")


def js_project(lat, lng, geo):
    """The exact arithmetic 85-panels-market.js::project performs, in Python.

    Transcribed by hand, and kept honest by
    `test_the_js_projection_is_the_one_transcribed_here`, which greps the shipped
    source for the two expressions below.
    """
    s, w, n, e = geo["bbox"]
    vw, vh = geo["view"]
    return ((lng - w) / (e - w) * vw, (n - lat) / (n - s) * vh)


@pytest.fixture(scope="module")
def geo_block():
    """What build_payload ships. Built from maps' own constants, not restated."""
    return {"bbox": list(maps.BBOX), "view": [maps.VIEW_W, maps.VIEW_H]}


def test_the_shipped_block_is_maps_own_constants(geo_block):
    assert geo_block["bbox"] == [16.28, 80.41, 16.33, 80.46]
    assert geo_block["view"] == [1000, 1041]
    assert maps.VIEW_H == 1041, "VIEW_H is computed in Python and must not drift"


def test_the_js_formula_agrees_with_maps_project_across_the_bbox(geo_block):
    s, w, n, e = maps.BBOX
    for i in range(11):
        for j in range(11):
            lat = s + (n - s) * i / 10
            lng = w + (e - w) * j / 10
            assert js_project(lat, lng, geo_block) == pytest.approx(
                maps.project(lat, lng), abs=1e-9)


def test_the_js_formula_agrees_on_every_live_clinic(geo_block):
    dist = ROOT / "web" / "dist" / "derma_intel.html"
    if not dist.exists():
        pytest.skip("no dist built")
    m = re.search(r"window\.__DATA__ = (\{.*?\});\s*</script>",
                  dist.read_text(encoding="utf-8"), re.S)
    data = json.loads(m.group(1))
    clinics = [c for c in data["clinics"] if c.get("lat") is not None]
    assert clinics, "the live payload should carry located clinics"
    for c in clinics:
        assert js_project(c["lat"], c["lng"], geo_block) == pytest.approx(
            maps.project(c["lat"], c["lng"]), abs=1e-9)


def test_the_js_projection_is_the_one_transcribed_here():
    """A regression guard on the transcription above: if the panel's arithmetic
    is edited, this test's twin stops being a twin and nothing else would notice."""
    # `s0` in the panel only because `s` is already the SVG element builder.
    assert "(lng - w) / (e - w) * vw" in MARKET_JS
    assert "(n - lat) / (n - s0) * vh" in MARKET_JS


def test_the_panel_never_auto_fits_to_the_clinic_cloud():
    """v3's market map fitted the projection to the clinics' own extents, which
    puts the pins in a coordinate space unrelated to the rendered SVG. The card
    reads the bbox from the payload instead, and must keep doing so."""
    assert "Math.min(...lats)" not in MARKET_JS
    assert "ctx.D.geo" in MARKET_JS
