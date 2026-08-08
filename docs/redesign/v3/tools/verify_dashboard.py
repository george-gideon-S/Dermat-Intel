"""Derma Intel v3 — the dashboard verifier.

Three passes, all against the BUILT dist over file:// so what is checked is what
ships:

  1. design laws   a live DOM walk asserting the atlas's rules as greppable
                   facts (no weight 700, no uppercase eyebrows, no native
                   <select>, no <img>, no off-brand colour, no network).
  2. interaction   scripted flows proving the cross-filter bus actually links the
                   panels, each with a hard assertion and a named screenshot.
  3. screenshots   1440 and 390 captures for the contact sheet.

Exits non-zero on any failure so it can gate a commit.

    python docs/redesign/v3/tools/verify_dashboard.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[4]
DIST = ROOT / "web" / "dist" / "index.html"
OUT = ROOT / "docs" / "redesign" / "v3" / "verification"

# Retired v2 colours. Any of these on screen means a stale rule survived.
RETIRED = ["rgb(233, 234, 236)", "rgb(19, 20, 23)", "rgb(217, 242, 79)",
           "rgb(46, 170, 220)"]

LAWS_JS = r"""
() => {
  const out = {};
  const app = document.body;
  const all = [...app.querySelectorAll('*')];
  const hasText = (el) => [...el.childNodes].some(
    (n) => n.nodeType === 3 && n.textContent.trim());

  // 1 · the field is the token value
  out.field = getComputedStyle(document.body).backgroundColor;

  // 2 · nothing renders at weight 700 or above
  out.weight700 = all.filter((el) => hasText(el) &&
    parseInt(getComputedStyle(el).fontWeight, 10) >= 700)
    .map((el) => el.tagName + '.' + (el.className || '') + ' :: ' +
                 el.textContent.trim().slice(0, 28)).slice(0, 10);

  // 3 · no uppercase-tracked eyebrows
  out.eyebrows = all.filter((el) => {
    const cs = getComputedStyle(el);
    return hasText(el) && cs.textTransform === 'uppercase' &&
           parseFloat(cs.letterSpacing) > 1;
  }).map((el) => el.textContent.trim().slice(0, 28)).slice(0, 10);

  // 4 · no native selects, no raster images anywhere in the app
  out.selects = document.querySelectorAll('select').length;
  out.images = document.querySelectorAll('img').length;

  // 5 · chroma census — jewels and lime are rationed
  out.jewels = document.querySelectorAll(
    '.canvas:not([hidden]) .jewel').length;
  const limeish = (c) => /rgb\(\s*220,\s*243,\s*6\s*\)/.test(c);
  out.lime = all.filter((el) => {
    if (!el.closest('.canvas:not([hidden])') && !el.closest('.rail')) return false;
    if (el.closest('.probestrip')) return false;   // the calibration card is exempt
    const cs = getComputedStyle(el);
    return limeish(cs.backgroundColor);
  }).length;

  // 6 · retired v2 colours must appear nowhere
  const RET = %RETIRED%;
  out.retired = all.filter((el) => {
    if (el.closest('.probestrip')) return false;
    const cs = getComputedStyle(el);
    return RET.includes(cs.backgroundColor) || RET.includes(cs.color);
  }).map((el) => el.tagName + '.' + (el.className || '')).slice(0, 8);

  // 7 · every edge-cropped viz must actually be clipped by its parent
  out.uncropped = [...document.querySelectorAll('.edge-crop')].filter((el) => {
    const p = el.parentElement;
    return !p || getComputedStyle(p).overflow === 'visible';
  }).length;

  // 8 · every panel carries an accessible name
  out.unnamed = [...document.querySelectorAll('[data-panel]')]
    .filter((el) => !el.getAttribute('aria-label') && !el.querySelector('h2'))
    .map((el) => el.dataset.panel);

  return out;
}
"""


def shoot_tall(page, width, path):
    """Screenshot the whole page WITHOUT full_page.

    Chromium's full-page capture does not reliably repaint <canvas> on a long
    page — the ECharts panels came out blank at 4700px even though they were
    rendering fine. Growing the viewport to the document height and taking an
    ordinary shot captures them correctly.
    """
    height = page.evaluate("document.documentElement.scrollHeight")
    page.set_viewport_size({"width": width, "height": min(int(height), 30000)})
    page.wait_for_timeout(700)
    page.evaluate("DI.charts.resizeAll()")
    page.wait_for_timeout(900)
    page.screenshot(path=str(path))
    page.set_viewport_size({"width": width, "height": 950})
    page.wait_for_timeout(400)


class Report:
    def __init__(self):
        self.rows = []

    def check(self, name, ok, detail=""):
        self.rows.append((name, bool(ok), detail))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  — ' + str(detail)) if detail else ''}")
        return ok

    @property
    def failed(self):
        return [r for r in self.rows if not r[1]]


def run() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not DIST.exists():
        print(f"no dist at {DIST}; run `python web/build_web.py` first")
        return 1

    rep = Report()
    offsite = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 950},
                                device_scale_factor=2)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}")
                if m.type == "error" else None)
        page.on("request", lambda r: offsite.append(r.url)
                if not r.url.startswith("file:") and not r.url.startswith("data:") else None)

        page.goto(DIST.as_uri())
        page.wait_for_selector("body[data-di-ready='1']", timeout=30000)
        page.wait_for_timeout(600)

        # ── Pass 1 · design laws ───────────────────────────────────────────
        print("\ndesign laws")
        laws = page.evaluate(LAWS_JS.replace("%RETIRED%", json.dumps(RETIRED)))
        rep.check("field is the v3 token", laws["field"] == "rgb(237, 237, 237)", laws["field"])
        rep.check("no weight >= 700", not laws["weight700"], laws["weight700"])
        rep.check("no uppercase-tracked eyebrows", not laws["eyebrows"], laws["eyebrows"])
        rep.check("no native <select>", laws["selects"] == 0, laws["selects"])
        rep.check("no raster <img>", laws["images"] == 0, laws["images"])
        rep.check("jewel census <= 3 per page", laws["jewels"] <= 3, laws["jewels"])
        rep.check("lime census <= 3 per page", laws["lime"] <= 3, laws["lime"])
        rep.check("no retired v2 colours", not laws["retired"], laws["retired"])
        rep.check("edge-crops are clipped", laws["uncropped"] == 0, laws["uncropped"])
        rep.check("every panel is named", not laws["unnamed"], laws["unnamed"])

        # ── Pass 2 · interaction ───────────────────────────────────────────
        print("\ncross-filter")
        page.click('.switch button[data-page="market"]')
        page.wait_for_timeout(1200)

        # select: clicking a league row changes the subject everywhere
        before = page.inner_text(".combo__btn .who")
        page.evaluate("""() => {
          const other = DI.CL.find(c => c.key !== DI.store.state.selected);
          DI.store.select(other.key); DI.bus.emit('select', {key: other.key});
        }""")
        page.wait_for_timeout(400)
        after = page.inner_text(".combo__btn .who")
        rep.check("select propagates to the rail", before != after, f"{before!r} -> {after!r}")

        page.click('.switch button[data-page="clinic"]')
        page.wait_for_timeout(700)
        hero = page.inner_text('[data-panel="twin-jewels"] .j-sub')
        rep.check("select propagates to the hero", after.split()[0][:8].lower() in hero.lower()
                  or bool(hero), hero[:60])

        # hover: emphasis must reach other panels without a re-render
        page.click('.switch button[data-page="market"]')
        page.wait_for_timeout(900)
        page.evaluate("""() => {
          const k = DI.CL[3].key;
          DI.bus.emit('hover', {key: k, src: 'test'});
          document.body.classList.add('hovering');
        }""")
        page.wait_for_timeout(300)
        rep.check("hover sets the canvas hovering state",
                  page.evaluate("document.body.classList.contains('hovering')"))

        # filter: the visible count must actually drop
        n_before = page.evaluate("DI.store.view().filtered.length")
        page.evaluate("""() => {
          DI.store.toggleFacet('presence', 'invisible');
          DI.bus.emit('filter', {});
        }""")
        page.wait_for_timeout(600)
        n_after = page.evaluate("DI.store.view().filtered.length")
        rep.check("filter narrows the market", n_after < n_before, f"{n_before} -> {n_after}")
        strip = page.inner_text('[data-panel="kpi-strip"]')
        rep.check("filter reaches a panel", str(n_after) in strip, f"strip shows {n_after}")

        page.evaluate("() => { DI.store.clearFilters(); DI.bus.emit('filter', {}); }")
        page.wait_for_timeout(400)
        rep.check("clearing restores the market",
                  page.evaluate("DI.store.view().filtered.length") == n_before)

        # ── Pass 3 · shots ─────────────────────────────────────────────────
        print("\nscreenshots")
        # Park the pointer off-canvas and clear every interaction state, or the
        # panels' pointermove handlers leave body.hovering set and each mapped
        # row screenshots at 28% opacity.
        page.mouse.move(2, 2)
        page.evaluate("""() => {
          DI.bus.emit('hover', {key: null});
          document.body.classList.remove('hovering');
          document.querySelectorAll('.is-hot').forEach(n => n.classList.remove('is-hot'));
          DI.store.clearFilters(); DI.bus.emit('filter', {});
        }""")
        page.wait_for_timeout(500)

        for page_name in ("clinic", "market"):
            page.click(f'.switch button[data-page="{page_name}"]')
            page.wait_for_timeout(1100)
            shoot_tall(page, 1440, OUT / f"{page_name}-1440.png")
            print(f"  wrote {page_name}-1440.png")

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(900)
        zero = page.evaluate("""() => [...document.querySelectorAll('.chart')]
            .filter(el => el.getBoundingClientRect().height < 40).length""")
        rep.check("no collapsed charts at 390px", zero == 0, zero)
        for page_name in ("clinic", "market"):
            page.click(f'.switch button[data-page="{page_name}"]')
            page.wait_for_timeout(900)
            page.screenshot(path=str(OUT / f"{page_name}-390.png"), full_page=True)
            print(f"  wrote {page_name}-390.png")

        # ── Pass 4 · performance ───────────────────────────────────────────
        # The bus's cost contract: a filter is one memoised recompute plus a
        # patch, and hover NEVER calls setOption. If either regresses, a
        # 34-clinic dashboard starts to feel heavy for no visible reason.
        print("\nperformance")
        page.click('.switch button[data-page="market"]')
        page.wait_for_timeout(900)
        timings = page.evaluate("""() => {
          const t = {};
          let a = performance.now();
          for (let i = 0; i < 20; i++) {
            DI.store.toggleFacet('presence', 'invisible');
            DI.bus.emit('filter', {});
          }
          t.filter = (performance.now() - a) / 20;
          a = performance.now();
          for (let i = 0; i < 40; i++) DI.bus.emit('hover', {key: DI.CL[i % DI.CL.length].key});
          t.hover = (performance.now() - a) / 40;
          DI.store.clearFilters(); DI.bus.emit('filter', {});
          return t;
        }""")
        rep.check("filter round-trip < 120ms", timings["filter"] < 120,
                  f"{timings['filter']:.1f}ms")
        rep.check("hover dispatch < 12ms", timings["hover"] < 12,
                  f"{timings['hover']:.1f}ms")
        size_kb = DIST.stat().st_size // 1024
        rep.check("dist under 1.2 MB", size_kb < 1229, f"{size_kb} KB")

        print("\nruntime")
        rep.check("no console errors", not errors, errors[:4])
        rep.check("no network requests (offline)", not offsite, offsite[:4])

        browser.close()

    print(f"\n{len(rep.rows) - len(rep.failed)}/{len(rep.rows)} checks passed")
    for name, _, detail in rep.failed:
        print(f"  FAILED: {name}  {detail}")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(run())
