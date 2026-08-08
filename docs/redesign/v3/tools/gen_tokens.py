"""Derma Intel v3 — palette.json -> CSS custom properties + the JS palette object.

ECharts cannot resolve CSS custom properties, so the palette has to exist twice: once
for CSS and once for JS. Authoring it twice is how v2's palette drifted (`web/app.js`
duplicated the token hexes as literals). Here one tree walk emits both forms from a
single source, so drift is structurally impossible.

Naming rule: the JSON path joined with "-" becomes the CSS custom property.

    jewel.clear.core   ->   --jewel-clear-core        (CSS)
                       ->   DI.P.jewel.clear.core     (JS)

Keys beginning with "$" are documentation and are skipped.

Importable: `build_web.py` calls palette_css()/palette_js() at build time; nothing is
written to disk, so there is no stale-generated-file failure mode.

    python docs/redesign/v3/tools/gen_tokens.py --check    # print what would be emitted
"""

from __future__ import annotations

import json
from pathlib import Path

V3 = Path(__file__).resolve().parents[1]
PALETTE = V3 / "palette.json"


def _walk(node, prefix=()):
    """Yield (path_tuple, value) for every leaf, skipping $-prefixed doc keys."""
    for key, value in node.items():
        if key.startswith("$"):
            continue
        path = prefix + (key,)
        if isinstance(value, dict):
            yield from _walk(value, path)
        else:
            yield path, value


def load_palette(path: Path | None = None) -> dict:
    return json.loads((path or PALETTE).read_text(encoding="utf-8"))


def palette_css(palette: dict) -> str:
    """Emit the `:root` block. One custom property per leaf."""
    lines = [
        "/* GENERATED from docs/redesign/v3/palette.json — do not edit by hand. */",
        ":root {",
    ]
    for path, value in _walk(palette):
        lines.append(f"  --{'-'.join(path)}: {value};")
    lines.append("}")
    return "\n".join(lines)


def palette_js(palette: dict) -> str:
    """Emit the frozen JS palette object ECharts reads."""
    tree: dict = {}
    for path, value in _walk(palette):
        node = tree
        for part in path[:-1]:
            node = node.setdefault(part, {})
        node[path[-1]] = value
    body = json.dumps(tree, indent=2, sort_keys=False)
    return (
        "/* GENERATED from docs/redesign/v3/palette.json — do not edit by hand. */\n"
        "window.DI = window.DI || {};\n"
        f"DI.P = Object.freeze({body});\n"
    )


def css_names(palette: dict) -> list[str]:
    """Every custom-property name this palette emits (used by the token test)."""
    return [f"--{'-'.join(path)}" for path, _ in _walk(palette)]


if __name__ == "__main__":
    p = load_palette()
    print(palette_css(p))
    print()
    print(palette_js(p))
