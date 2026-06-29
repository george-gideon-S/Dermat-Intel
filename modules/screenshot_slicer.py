"""Slice tall full-page Google SERP PNGs into legible, overlapping vertical tiles.

Why: a full-page SERP capture is ~1500x7500px. Claude's vision (via the Read tool) downscales any
image to a bounded long edge, so a whole page renders at ~8px text — illegible. Cut into 1500x1600
tiles and each reads at ~native resolution (clinic names, ratings, URLs all sharp). Tiles overlap so a
result block straddling a cut still appears whole in at least one tile. Tiles are ephemeral scratch
(gitignored, regenerable); the durable artifact is the extracted .cache/web_screens.json.

Pure tiling math (`_tile_offsets`) is unit-tested; Pillow I/O is smoke-tested on a synthetic image.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")

TILE_H = 1600   # near-native legible tile height
OVERLAP = 180   # vertical overlap so a result block split across a cut appears whole in one tile


def _tile_offsets(height: int, tile_h: int = TILE_H, overlap: int = OVERLAP) -> list[tuple[int, int]]:
    """Vertical (y0, y1) spans covering [0, height] with `overlap` between consecutive tiles.

    The last tile is clamped to `height` (so it may be shorter and overlap the prior tile by more).
    """
    if height <= tile_h:
        return [(0, height)]
    step = tile_h - overlap
    offsets: list[tuple[int, int]] = []
    y = 0
    while True:
        y1 = min(y + tile_h, height)
        offsets.append((y, y1))
        if y1 >= height:
            break
        y += step
    return offsets


def tile_image(src: str, out_dir: str, tile_h: int = TILE_H, overlap: int = OVERLAP) -> list[dict]:
    """Crop `src` into vertical tiles under `out_dir`; return one record per tile."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    img = Image.open(src)
    try:
        w, h = img.size
        recs: list[dict] = []
        for i, (y0, y1) in enumerate(_tile_offsets(h, tile_h, overlap)):
            fp = out / f"tile_{i:02d}_{y0}-{y1}.png"
            img.crop((0, y0, w, y1)).save(fp)
            recs.append({"file": str(fp), "index": i, "y0": y0, "y1": y1, "w": w, "h": y1 - y0})
    finally:
        img.close()
    return recs


def list_screenshots(screenshots_dir: str) -> list[str]:
    """All .png screenshots in `screenshots_dir`, sorted by filename (timestamp order)."""
    return [str(p) for p in sorted(Path(screenshots_dir).glob("*.png"), key=lambda p: p.name)]


def build_manifest(screenshots_dir: str, query_rows: list[dict], tiles_root: str,
                   tile_h: int = TILE_H, overlap: int = OVERLAP) -> dict:
    """Slice every screenshot into `tiles_root/<index>/` and return a manifest.

    Each entry pairs a screenshot with its query *by order, as a HINT only* (`assumed_query`). The
    vision pass reads the actual search box and the final mapping reconciles by that text — order is
    never trusted on its own, because the 2 missing screenshots could be interior.
    """
    shots = list_screenshots(screenshots_dir)
    root = Path(tiles_root)
    entries = []
    for idx, shot in enumerate(shots):
        recs = tile_image(shot, str(root / f"{idx:02d}"), tile_h, overlap)
        hint = query_rows[idx] if idx < len(query_rows) else {}
        entries.append({
            "index": idx,
            "screenshot": Path(shot).name,
            "assumed_rank": hint.get("rank"),
            "assumed_query": hint.get("search_query"),
            "tiles": [r["file"] for r in recs],
        })
    return {
        "num_screenshots": len(shots),
        "num_queries_expected": len(query_rows),
        "tile_h": tile_h,
        "overlap": overlap,
        "screenshots": entries,
    }


def slice_corpus(screenshots_dir: str | None = None, tiles_root: str | None = None,
                 query_rows: list[dict] | None = None) -> dict:
    """Slice the real corpus and persist the manifest next to the tiles. Returns the manifest."""
    screenshots_dir = screenshots_dir or config.SCREENSHOTS_DIR
    tiles_root = tiles_root or config.WEB_TILES_DIR
    if query_rows is None:
        from modules import storage
        query_rows = storage.load_rows(storage.QUERIES_JSON) or []
    man = build_manifest(screenshots_dir, query_rows, tiles_root)
    Path(tiles_root).mkdir(parents=True, exist_ok=True)
    with open(Path(tiles_root) / "manifest.json", "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)
    return man


if __name__ == "__main__":  # pragma: no cover - manual slice run
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    m = slice_corpus()
    total = sum(len(e["tiles"]) for e in m["screenshots"])
    print(f"sliced {m['num_screenshots']} screenshots -> {total} tiles "
          f"({m['num_queries_expected']} queries expected)")
