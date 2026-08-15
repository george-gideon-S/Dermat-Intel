"""Fetch the Guntur OSM extract and reduce it to the small committed geometry.

Run this ONCE (or to refresh the map). The build never touches the network:

    raw Overpass JSON  ->  .cache/osm_guntur.json   (2.3 MB, gitignored)
                       ->  web/guntur-geo.json      (small, COMMITTED)

The committed file is what `web/build_web.py` renders, so a fresh clone can
build the dist with no network and no Overpass dependency.

    python docs/redesign/v4/tools/fetch_osm.py            # use the cache if present
    python docs/redesign/v4/tools/fetch_osm.py --refetch  # re-hit Overpass

WHY curl AND NOT requests. This machine sits behind TLS interception: Python's
`requests` and npm both fail on the MITM certificate, while curl uses schannel
and the Windows certificate store and works. That is the same reason
`web/build_echarts.py` shells out to curl. Verification is NEVER disabled.

Overpass is free and unkeyed, which keeps the project's no-paid-APIs rule intact.
The data is © OpenStreetMap contributors, ODbL — attribution ships in the geo
file and is rendered in the dist's footer.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "web"))

import maps  # noqa: E402  (needs the path above)

RAW = ROOT / ".cache" / "osm_guntur.json"
OUT = ROOT / "web" / "guntur-geo.json"

S, W, N, E = maps.BBOX
QUERY = f"""[out:json][timeout:90];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary)(_link)?$"]({S},{W},{N},{E});
  way["waterway"~"^(river|stream|canal|drain)$"]({S},{W},{N},{E});
  way["natural"="water"]({S},{W},{N},{E});
  way["landuse"~"^(park|grass|forest|recreation_ground|village_green|cemetery)$"]({S},{W},{N},{E});
  way["leisure"~"^(park|garden|pitch|playground)$"]({S},{W},{N},{E});
  way["highway"="residential"]({S},{W},{N},{E});
);
out geom;"""

# Grid for the dot matrix, chosen by measuring rather than by taste. Path size
# against resolution, on the real extract:
#
#     cols   dot pitch   runs   path
#       72       74 m     346    6.2 KB
#      100       53 m    1048   17.6 KB
#      132       40 m    2586   37.4 KB
#
# 100 puts a dot every ~53 m, which lands about 14 px apart on a 1440 viewport —
# far enough to read as DOTS rather than a grey wash, close enough that the
# street grid is still legibly a city. It also keeps the pair (8 KB styled +
# ~18 KB dots) at a quarter of the 100 KB budget, which matters because the dist
# has ~160 KB of headroom left under the cap.
DOT_COLS = 100


def fetch() -> None:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    print("fetching from Overpass (free, unkeyed)…")
    r = subprocess.run(
        ["curl", "-s", "-m", "180", "-G", "https://overpass-api.de/api/interpreter",
         "--data-urlencode", f"data={QUERY}", "-o", str(RAW),
         "-w", "%{http_code}"],
        capture_output=True, text=True, check=True)
    if r.stdout.strip() != "200":
        raise SystemExit(f"Overpass returned HTTP {r.stdout.strip()}")
    print(f"  wrote {RAW.relative_to(ROOT)}  ({RAW.stat().st_size // 1024} KB)")


def _classify(tags: dict) -> str | None:
    hw = tags.get("highway", "").replace("_link", "")
    if hw in maps.ROAD_CLASSES:
        return hw
    if hw == "motorway":
        return "trunk"                      # one class coarser; there is one
    if hw == "residential":
        return "residential"
    if tags.get("waterway") or tags.get("natural") == "water":
        return "water"
    if tags.get("landuse") or tags.get("leisure"):
        return "green"
    return None


def reduce_extract() -> dict:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    roads = {c: [] for c in maps.ROAD_CLASSES}
    water, green, residential = [], [], []

    for el in raw.get("elements", []):
        geom = el.get("geometry")
        if not geom:
            continue
        kind = _classify(el.get("tags", {}))
        if kind is None:
            continue
        # Areas keep more detail than lines: a park simplified hard stops
        # looking like a park. Residential is only ever rasterised, so it is
        # simplified hardest of all.
        tol = 2.5 if kind == "residential" else (0.8 if kind in ("water", "green") else 1.2)
        pts = maps.project_way(geom, tol)
        if len(pts) < 2:
            continue
        if kind == "water":
            water.append(pts)
        elif kind == "green":
            green.append(pts)
        elif kind == "residential":
            residential.append(pts)
        else:
            roads[kind].append(pts)

    # The dot matrix reads the ARTERIAL network only — the same ways the styled
    # map draws — and deliberately not the 3,538 residential streets.
    #
    # This was settled by rendering both. Rasterising every road lights nearly
    # every cell, and the result is a uniform wall of dots: technically the city,
    # legibly a grey texture, and useless as a ground for cards to sit on. The
    # arterial network instead traces Guntur's actual shape in dots — which is
    # the point of the variant, since the identity already runs the dot at three
    # scales and this makes it four. It is also half the bytes.
    #
    # Residential is still fetched: it costs nothing (the cache is gitignored),
    # and a density-modulated halftone may want it later.
    skeleton = water + green + [w for c in roads.values() for w in c]
    rows = round(DOT_COLS * maps.VIEW_H / maps.VIEW_W)
    cells = maps.rasterize(skeleton, DOT_COLS, rows)
    runs = maps.row_runs(cells)

    return {
        "$source": "OpenStreetMap contributors, ODbL — overpass-api.de",
        "$bbox": list(maps.BBOX),
        "$view": [maps.VIEW_W, maps.VIEW_H],
        "roads": roads,
        "water": water,
        "green": green,
        "dots": {"cols": DOT_COLS, "rows": rows, "runs": [list(r) for r in runs]},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true",
                    help="re-hit Overpass instead of reusing .cache/osm_guntur.json")
    args = ap.parse_args()

    if args.refetch or not RAW.exists():
        fetch()
    else:
        print(f"using cached {RAW.relative_to(ROOT)} (--refetch to renew)")

    geo = reduce_extract()
    OUT.write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")

    n_roads = sum(len(v) for v in geo["roads"].values())
    print(f"  roads {n_roads} · water {len(geo['water'])} · green {len(geo['green'])}"
          f" · dot runs {len(geo['dots']['runs'])}")
    print(f"  wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size // 1024} KB)")

    real = maps.render_map(geo)
    dots = maps.render_dotmap(geo)
    print(f"  rendered: styled map {len(real) // 1024} KB · dot map {len(dots) // 1024} KB"
          f"  (budget 100 KB for the pair)")


if __name__ == "__main__":
    main()
