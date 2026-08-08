"""Source-level design laws + template integrity.

The Playwright verifier checks the RENDERED page; these check the SOURCE, so they
run in milliseconds and fail a commit before anything is built. Between them they
make the atlas's rules greppable facts rather than good intentions.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
V3 = ROOT / "docs" / "redesign" / "v3"

CSS_FILES = sorted((WEB / "css").glob("*.css"))
JS_FILES = sorted((WEB / "js").glob("*.js"))
TOKEN_FILES = [V3 / "tokens-v3.css", V3 / "components-v3.css"]


def strip_comments(text: str, js: bool) -> str:
    """Remove comments so prose about a banned pattern is not mistaken for one."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    if js:
        text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    return text


def test_the_v3_source_tree_exists():
    assert CSS_FILES and JS_FILES


# ── the palette is the only place a colour is authored ──────────────────────
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGBA = re.compile(r"\brgba?\(\s*\d")


def _colour_body(path):
    body = strip_comments(path.read_text(encoding="utf-8"), js=False)
    # The grain texture is an inline SVG data URI, not colour.
    body = re.sub(r"url\(\"data:image/svg\+xml[^\"]*\"\)", "", body)
    # A mask-image's colour stops are an ALPHA channel, not paint: `#000` there
    # means "opaque", and routing it through the palette would be nonsense.
    body = re.sub(r"(-webkit-)?mask-image\s*:[^;]+;", "", body)
    return body


@pytest.mark.parametrize("path", CSS_FILES + TOKEN_FILES, ids=lambda p: p.name)
def test_no_raw_hex_anywhere_in_css(path):
    """A hex is always palette colour, so it belongs in palette.json — this is the
    rule that stops the CSS and the ECharts palette drifting the way v2's did."""
    found = HEX.findall(_colour_body(path))
    assert not found, f"raw hex in {path.name}: {found[:5]}"


@pytest.mark.parametrize("path", CSS_FILES, ids=lambda p: p.name)
def test_the_app_layer_authors_no_colour_at_all(path):
    """Stricter than the token layer: web/css/** consumes tokens and nothing else.
    Structural neutrals (shadow alphas, the drawer scrim) live in the token layer
    where they can be reviewed as a set, not scattered through the app."""
    found = RGBA.findall(_colour_body(path))
    assert len(found) <= 1, f"{len(found)} rgba literals in {path.name}; use a token"


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_no_raw_colour_in_js(path):
    body = strip_comments(path.read_text(encoding="utf-8"), js=True)
    assert not HEX.findall(body), f"raw hex in {path.name}: {HEX.findall(body)[:5]}"


# ── typography ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("path", CSS_FILES + TOKEN_FILES, ids=lambda p: p.name)
def test_weight_700_is_never_authored(path):
    body = strip_comments(path.read_text(encoding="utf-8"), js=False)
    hits = re.findall(r"font-weight\s*:\s*(\d{3})", body)
    assert all(int(w) < 700 for w in hits), f"weight >= 700 in {path.name}: {hits}"


@pytest.mark.parametrize("path", CSS_FILES + TOKEN_FILES, ids=lambda p: p.name)
def test_no_uppercase_tracked_eyebrows(path):
    """`text-transform: uppercase` next to positive letter-spacing is the AI-slop
    eyebrow the atlas bans."""
    body = strip_comments(path.read_text(encoding="utf-8"), js=False)
    for block in re.findall(r"\{[^{}]*\}", body):
        if "uppercase" in block and re.search(r"letter-spacing\s*:\s*0?\.\d+em", block):
            pytest.fail(f"uppercase + tracking in {path.name}: {block[:80]}")


# ── determinism and offline ─────────────────────────────────────────────────
@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_no_math_random(path):
    """Seeded jitter only — verifier screenshots have to reproduce byte for byte."""
    body = strip_comments(path.read_text(encoding="utf-8"), js=True)
    assert "Math.random" not in body, f"Math.random() in {path.name}"


@pytest.mark.parametrize("path", JS_FILES + CSS_FILES, ids=lambda p: p.name)
def test_no_remote_urls(path):
    """The dist is offline and self-contained; a remote URL would break that.

    The XML namespace URIs are identifiers, not addresses — nothing is fetched
    from them — so they are the one allowed exception.
    """
    body = strip_comments(path.read_text(encoding="utf-8"), js=path.suffix == ".js")
    body = body.replace("http://www.w3.org/2000/svg", "").replace("http://www.w3.org/1999/xlink", "")
    assert "http://" not in body and "https://" not in body, f"remote URL in {path.name}"


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_no_innerhtml_assignment(path):
    """Clinic names come from scraped listings and are untrusted. Every text path
    goes through textContent/createTextNode; the one HTML string (ECharts tooltip
    formatters) is escaped at source."""
    body = strip_comments(path.read_text(encoding="utf-8"), js=True)
    assert not re.search(r"\.innerHTML\s*=", body), f"innerHTML assignment in {path.name}"


def test_no_img_elements_are_ever_built():
    """The raw SERP screenshot is gone and the redrawn panel replaces it, so the
    app never constructs an <img>. Matches element CONSTRUCTION only — role="img"
    is a correct ARIA role on the jewels and must not trip this."""
    build = re.compile(r"""(createElement\(\s*["']img["']|\bh\(\s*["']img[.\s"'])""")
    for path in JS_FILES:
        body = strip_comments(path.read_text(encoding="utf-8"), js=True)
        assert not build.search(body), f"<img> constructed in {path.name}"


# ── template integrity ──────────────────────────────────────────────────────
TEMPLATE = (WEB / "template.html").read_text(encoding="utf-8")


def test_echarts_placeholder_keeps_its_exact_byte_sequence():
    """build_web.py string-replaces this literal to swap in the SRI-pinned CDN tag
    when no bundle is vendored. Reformatting it silently kills that fallback."""
    assert "<script>{{ECHARTS}}</script>" in TEMPLATE


@pytest.mark.parametrize("token", ["{{STYLES}}", "{{ECHARTS}}", "{{DATA}}", "{{APP_JS}}"])
def test_each_placeholder_appears_exactly_once(token):
    assert TEMPLATE.count(token) == 1


def test_template_has_no_native_select_or_image():
    assert "<select" not in TEMPLATE
    assert "<img" not in TEMPLATE


def test_template_mounts_both_pages():
    assert 'data-page="clinic"' in TEMPLATE
    assert 'data-page="market"' in TEMPLATE


def test_bundle_lists_match_the_files_on_disk():
    """A file added to web/js but missing from _V3_JS would simply never ship."""
    from web import build_web
    assert [f"{n}.css" for n in build_web._V3_CSS] == [p.name for p in CSS_FILES]
    js_expected = [f"{n}.js" for n in build_web._V3_JS if n != "10-palette"]
    assert js_expected == [p.name for p in JS_FILES]


def test_the_app_core_is_ordered_before_the_panels():
    """Panels call DI.app.register() at parse time, so the core must load first.
    Getting this wrong renders a blank page with no console error worth reading."""
    from web import build_web
    order = build_web._V3_JS
    assert order.index("70-app") < order.index("80-panels-clinic")
    assert order.index("70-app") < order.index("85-panels-market")
    assert order.index("00-util") == 0
    assert order.index("10-palette") < order.index("50-charts")
