"""Build the self-contained brand guide: inline tokens + components + base64 fonts.

Usage:  python docs/redesign/v2/build_guide.py
Output: docs/redesign/v2/brand-guide.html  (single offline file)
"""
from __future__ import annotations

import base64
import pathlib

V2 = pathlib.Path(__file__).parent
VENDOR = V2.parent.parent.parent / "web" / "vendor"

FONTS = [
    # family, file, weight descriptor
    ("Geist", "geist-400.woff2", "400"),
    ("Geist", "geist-500.woff2", "500"),
    ("Geist", "geist-600.woff2", "600"),
    ("Geist", "geist-700.woff2", "700"),
    ("Geist Mono", "geistmono-400.woff2", "400"),
    ("Geist Mono", "geistmono-500.woff2", "500"),
    ("Doto", "doto-var.woff2", "100 900"),
]


def font_css() -> str:
    rules = []
    for family, fname, weight in FONTS:
        data = base64.b64encode((VENDOR / fname).read_bytes()).decode()
        rules.append(
            f"@font-face{{font-family:\"{family}\";"
            f"src:url(data:font/woff2;base64,{data}) format(\"woff2\");"
            f"font-weight:{weight};font-display:swap;}}"
        )
    return "<style>\n" + "\n".join(rules) + "\n</style>"


def build(src_name: str, dest_name: str) -> pathlib.Path:
    src = (V2 / src_name).read_text(encoding="utf-8")
    tokens = (V2 / "tokens-v2.css").read_text(encoding="utf-8")
    components = (V2 / "components.css").read_text(encoding="utf-8")

    out = (
        src.replace("<!--BUILD:FONTS-->", font_css())
        .replace("<!--BUILD:TOKENS-->", f"<style>\n{tokens}\n</style>")
        .replace("<!--BUILD:COMPONENTS-->", f"<style>\n{components}\n</style>")
    )
    for marker in ("<!--BUILD:", ):
        assert marker not in out, f"unresolved build marker in output ({marker})"

    dest = V2 / dest_name
    dest.write_text(out, encoding="utf-8")
    return dest


if __name__ == "__main__":
    for src_name, dest_name in [
        ("brand-guide.src.html", "brand-guide.html"),
        ("brand-booklet.src.html", "brand-booklet.html"),
    ]:
        p = build(src_name, dest_name)
        print(f"built {p.name}  ({p.stat().st_size / 1024:.0f} KB)")
