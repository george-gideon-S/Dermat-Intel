"""Tests for modules.screenshot_slicer — tiling math (pure) + Pillow slicing (smoke).

Full-page Google SERP PNGs are far too tall to read at once (they downscale to illegible);
we slice them into overlapping, near-native-resolution vertical tiles for the vision pass.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from modules import screenshot_slicer as sl


# --------------------------------------------------------------------------- _tile_offsets
def test_single_tile_when_shorter_than_tile_height():
    assert sl._tile_offsets(1000, tile_h=1600, overlap=180) == [(0, 1000)]


def test_offsets_cover_full_height_contiguously_with_overlap():
    offs = sl._tile_offsets(6382, tile_h=1600, overlap=180)
    # starts at the top, ends exactly at the bottom
    assert offs[0][0] == 0
    assert offs[-1][1] == 6382
    # every pixel covered: each tile starts no lower than the previous tile's bottom (no gaps)
    for (y0, _), (_, prev_y1) in zip(offs[1:], offs[:-1]):
        assert y0 <= prev_y1
    # consecutive step is tile_h - overlap (except the final clamped tile)
    assert offs[1][0] - offs[0][0] == 1600 - 180


def test_no_tile_exceeds_image_height():
    offs = sl._tile_offsets(11086, tile_h=1600, overlap=180)
    assert all(0 <= y0 < y1 <= 11086 for y0, y1 in offs)
    assert offs[-1][1] == 11086


def test_exact_height_equal_to_tile_height_is_single_tile():
    assert sl._tile_offsets(1600, tile_h=1600, overlap=180) == [(0, 1600)]


# --------------------------------------------------------------------------- tile_image (smoke)
def test_tile_image_writes_legible_tiles(tmp_path):
    # a synthetic 500x2000 image -> tiles of <=600 tall with 100 overlap
    src = tmp_path / "fake_serp.png"
    Image.new("RGB", (500, 2000), (20, 20, 20)).save(src)
    out = tmp_path / "tiles"
    recs = sl.tile_image(str(src), str(out), tile_h=600, overlap=100)

    assert len(recs) >= 3
    # files exist, widths preserved, heights match the offsets, none taller than tile_h
    for rec in recs:
        p = Path(rec["file"])
        assert p.exists()
        w, h = Image.open(p).size
        assert w == 500
        assert h == rec["y1"] - rec["y0"]
        assert h <= 600
    # full vertical coverage: union of [y0,y1) spans 0..2000
    assert recs[0]["y0"] == 0 and recs[-1]["y1"] == 2000


# --------------------------------------------------------------------------- listing / manifest
def test_list_screenshots_sorted_by_name(tmp_path):
    for name in ["screencapture-b.png", "screencapture-a.png", "notes.txt"]:
        (tmp_path / name).write_bytes(b"x")
    got = [Path(p).name for p in sl.list_screenshots(str(tmp_path))]
    assert got == ["screencapture-a.png", "screencapture-b.png"]  # png only, name-sorted


def test_build_manifest_pairs_by_order_as_hint(tmp_path):
    # two screenshots, three queries -> manifest has 2 entries, ordered, with query hints
    shots = tmp_path / "shots"
    shots.mkdir()
    Image.new("RGB", (300, 700), (0, 0, 0)).save(shots / "screencapture-2026-01.png")
    Image.new("RGB", (300, 700), (0, 0, 0)).save(shots / "screencapture-2026-02.png")
    qrows = [{"rank": 1, "search_query": "alpha"}, {"rank": 2, "search_query": "beta"},
             {"rank": 3, "search_query": "gamma"}]
    man = sl.build_manifest(str(shots), qrows, str(tmp_path / "tiles"),
                            tile_h=400, overlap=80)
    assert man["num_screenshots"] == 2
    assert man["num_queries_expected"] == 3
    entries = man["screenshots"]
    assert [e["index"] for e in entries] == [0, 1]
    assert entries[0]["assumed_query"] == "alpha" and entries[1]["assumed_query"] == "beta"
    assert all(len(e["tiles"]) >= 1 for e in entries)
