"""Derma Intel v3 — reference-atlas colour sampler.

Pillow port of the sister project's `sample-reference.ps1`, with two additions that
make a bad probe detectable instead of something you catch by eye:

  * ``sigma``   — mean per-channel standard deviation across the patch. A patch that
                  straddles an edge (probe missed its target, or landed on a boundary)
                  has a high sigma. Flat surfaces sit near 0.
  * ``delta``   — max-min channel spread of the sampled colour. Tells you whether a
                  surface is genuinely hue-neutral (delta ~0) or carries chroma.

Both feed the ``warnings`` list, which is the honest half of the output: every probe
whose sample contradicts its declared ``expect`` is named, so the atlas can say why a
value was discarded rather than quietly dropping it.

Sampling modes (identical to the reference implementation):
  avg        whole-patch mean                      -> flat surfaces, gradient bands
  minluma    mean of the darkest 12% of pixels     -> text strokes (a naive mean of a
                                                      text patch returns the background)
  maxchroma  mean of the top 12% by chroma         -> tiny saturated objects (a pill's
                                                      patch is mostly surrounding card)

White-point calibration is per image: one probe declared the anchor is scaled to
#FFFFFF and every other probe in that image takes the same per-channel gain. Both raw
and calibrated values are emitted -- the atlas reconciles them, this script does not.

    python docs/redesign/v3/tools/sample_reference.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev

from PIL import Image

ROOT = Path(__file__).resolve().parents[4]  # tools -> v3 -> redesign -> docs -> repo
V3 = ROOT / "docs" / "redesign" / "v3"
PROBES = V3 / "reference-probes.json"
OUT = V3 / "reference-samples.json"

TAKE_FRACTION = 0.12  # the reference implementation's top/bottom slice
NEUTRAL_MAX_DELTA = 12  # channel spread at or below this reads as hue-neutral
CHROMATIC_MIN_DELTA = 25  # a "chromatic" probe should clear this
# Sigma only means something for `avg` mode. minluma/maxchroma EXIST because their
# patch straddles (text on background, pill on card) -- a high sigma there is the
# point, not a fault. Flat surfaces must be tight; gradient bands legitimately vary.
EDGE_SIGMA_FLAT = 8.0
EDGE_SIGMA_GRADIENT = 26.0


def _luma(px: tuple[int, int, int]) -> float:
    return 0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]


def _chroma(px: tuple[int, int, int]) -> int:
    return max(px) - min(px)


def sample_patch(img: Image.Image, fx: float, fy: float, rad: int, mode: str) -> dict:
    """Sample a (2r+1)^2 patch at fractional coords and reduce it by `mode`."""
    w, h = img.size
    cx, cy = int(fx * w), int(fy * h)
    px: list[tuple[int, int, int]] = []
    for dx in range(-rad, rad + 1):
        for dy in range(-rad, rad + 1):
            x, y = cx + dx, cy + dy
            if 0 <= x < w and 0 <= y < h:
                px.append(img.getpixel((x, y))[:3])

    if mode == "minluma":
        take = max(1, int(len(px) * TAKE_FRACTION))
        sel = sorted(px, key=_luma)[:take]
    elif mode == "maxchroma":
        take = max(1, int(len(px) * TAKE_FRACTION))
        sel = sorted(px, key=_chroma, reverse=True)[:take]
    else:
        sel = px

    rgb = tuple(round(mean(c[i] for c in sel)) for i in range(3))
    # sigma is measured over the WHOLE patch, not the selection -- it describes how
    # uniform the sampled region is, which is what tells us the probe hit its target.
    sigma = mean(pstdev([c[i] for c in px]) for i in range(3)) if len(px) > 1 else 0.0
    return {"rgb": rgb, "sigma": round(sigma, 1), "delta": _chroma(rgb)}


def to_hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(int(v) for v in rgb))


def check(name: str, s: dict, expect: str | None, mode: str, img_name: str) -> str | None:
    """Return a warning string when a sample contradicts what the probe claimed to target."""
    if mode == "avg":
        limit = EDGE_SIGMA_FLAT if expect == "neutral" else EDGE_SIGMA_GRADIENT
        if s["sigma"] > limit:
            return (f"{img_name}/{name}: sigma {s['sigma']} > {limit} — patch straddles "
                    f"an edge, sample unreliable")
    if expect == "neutral" and s["delta"] > NEUTRAL_MAX_DELTA:
        return (f"{img_name}/{name}: expected neutral but channel spread is {s['delta']} "
                f"({to_hex(s['rgb'])}) — probe likely missed onto a coloured element")
    if expect == "chromatic" and s["delta"] < CHROMATIC_MIN_DELTA:
        return (f"{img_name}/{name}: expected chromatic but channel spread is only "
                f"{s['delta']} ({to_hex(s['rgb'])}) — probe likely missed the target")
    return None


def main() -> None:
    cfg = json.loads(PROBES.read_text(encoding="utf-8"))
    base = ROOT / cfg["baseDir"]
    out = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "note": ("raw = as sampled; calibrated = scaled so the image's white anchor maps "
                 "to #FFFFFF. Neither is the final token value — see ATLAS.md for the "
                 "reconciliation rule."),
        "images": {},
        "warnings": [],
    }

    for entry in cfg["images"]:
        path = base / entry["file"]
        if not path.exists():
            out["warnings"].append(f"MISSING IMAGE: {entry['file']}")
            continue

        img = Image.open(path).convert("RGB")
        raw = {p["name"]: sample_patch(img, p["x"], p["y"], p["r"], p["mode"])
               for p in entry["probes"]}

        for p in entry["probes"]:
            warn = check(p["name"], raw[p["name"]], p.get("expect"), p["mode"], entry["file"])
            if warn:
                out["warnings"].append(warn)

        anchor = entry.get("white")
        gains = None
        if anchor and anchor in raw and all(v > 0 for v in raw[anchor]["rgb"]):
            gains = [255.0 / v for v in raw[anchor]["rgb"]]

        probes_out = {}
        for p in entry["probes"]:
            name = p["name"]
            s = raw[name]
            rec = {
                "raw": to_hex(s["rgb"]),
                "mode": p["mode"],
                "sigma": s["sigma"],
                "delta": s["delta"],
            }
            if p.get("note"):
                rec["note"] = p["note"]
            if gains:
                rec["calibrated"] = to_hex([min(255, round(v * g))
                                            for v, g in zip(s["rgb"], gains)])
            probes_out[name] = rec

        out["images"][entry["file"]] = {
            "size": f"{img.size[0]}x{img.size[1]}",
            "whiteAnchor": anchor,
            "whiteGain": [round(g, 3) for g in gains] if gains else None,
            "probes": probes_out,
        }
        print(f"sampled {entry['file']}  ({len(probes_out)} probes)")

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    if out["warnings"]:
        print(f"\n{len(out['warnings'])} warning(s) — these are evidence, not failures:")
        for w in out["warnings"]:
            print(f"  ! {w}")


if __name__ == "__main__":
    main()
