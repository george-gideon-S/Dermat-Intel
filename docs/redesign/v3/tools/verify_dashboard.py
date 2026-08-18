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
    if (!el.closest('.canvas:not([hidden])') && !el.closest('.topbar') || el.closest('.shellfoot')) return false;
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

        # ── The picker gates the dashboard on first visit ──────────────────
        # Every check below inspects the DASHBOARD, and a fresh browser context
        # has no remembered choice, so the picker is up. Walk through it the way
        # a user would rather than seeding storage: it needs no knowledge of the
        # clinic keys, and it exercises the real path on every run. The picker
        # gets its own dedicated pass at the end, on a second clean context.
        if page.is_visible("#picker"):
            page.locator(".pk__card").first.click()
        page.wait_for_timeout(600)
        rep.check("the dashboard is reachable through the picker",
                  page.is_hidden("#picker") and page.is_visible("#canvas"))

        # ── Pass 1 · design laws, on BOTH pages ────────────────────────────
        # Evaluating once at boot only ever inspected the clinic page, so the
        # market page's eleven panels were never checked by any of the ten laws.
        for page_name in ("clinic", "market"):
            page.click(f'.switch button[data-page="{page_name}"]')
            page.wait_for_timeout(1100)
            print(f"\ndesign laws · {page_name}")
            laws = page.evaluate(LAWS_JS.replace("%RETIRED%", json.dumps(RETIRED)))
            tag = f"[{page_name}] "
            rep.check(tag + "field is the v3 token",
                      laws["field"] == "rgb(237, 237, 237)", laws["field"])
            rep.check(tag + "no weight >= 700", not laws["weight700"], laws["weight700"])
            rep.check(tag + "no uppercase-tracked eyebrows", not laws["eyebrows"], laws["eyebrows"])
            rep.check(tag + "no native <select>", laws["selects"] == 0, laws["selects"])
            rep.check(tag + "no raster <img>", laws["images"] == 0, laws["images"])
            rep.check(tag + "jewel census <= 3", laws["jewels"] <= 3, laws["jewels"])
            rep.check(tag + "lime census <= 3", laws["lime"] <= 3, laws["lime"])
            rep.check(tag + "no retired v2 colours", not laws["retired"], laws["retired"])
            rep.check(tag + "edge-crops are clipped", laws["uncropped"] == 0, laws["uncropped"])
            rep.check(tag + "every panel is named", not laws["unnamed"], laws["unnamed"])
        page.click('.switch button[data-page="clinic"]')
        page.wait_for_timeout(700)

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
        rep.check("select propagates to the top bar", before != after, f"{before!r} -> {after!r}")

        page.click('.switch button[data-page="clinic"]')
        page.wait_for_timeout(700)
        # `or bool(hero)` made this unfailable. Assert the hero actually shows the
        # NEW subject's rank, which is a fact only a real propagation produces.
        #
        # Resolved against a candidate list and read defensively. page.inner_text
        # on a missing selector does not fail the check — it RAISES at the 30 s
        # timeout and takes the whole run down, so every check after it silently
        # never executes. A verifier that stops reporting the moment one id
        # changes is worse than one that reports a failure, and the v4 cutover
        # renames a panel per page.
        want_rank = page.evaluate("DI.store.view().subject.visibility_rank")
        hero = ""
        for sel in ('[data-panel="yc01-visibility"] .j-sub',
                    '[data-panel="twin-jewels"] .j-sub'):
            loc = page.locator(sel)
            if loc.count():
                hero = loc.first.inner_text()
                break
        rep.check("select propagates to the hero", f"{want_rank} of " in hero,
                  f"expected rank {want_rank} in {hero[:52]!r}" if hero
                  else "no visibility-jewel sub-line found on the clinic page")

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
        # v4: the kpi-strip is gone. Its live readout moved onto the map card as
        # MK-01a's first tile, which becomes a BUTTON only while a filter is
        # active — so reading `.tile--act` proves both the count and the reset
        # affordance appeared together.
        strip = page.inner_text('[data-panel="mk01-map"] .tile--act')
        rep.check("filter reaches a panel", str(n_after) in strip, f"readout shows {strip!r}")

        page.evaluate("() => { DI.store.clearFilters(); DI.bus.emit('filter', {}); }")
        page.wait_for_timeout(400)
        rep.check("clearing restores the market",
                  page.evaluate("DI.store.view().filtered.length") == n_before)

        # A REAL pointer drag on the opportunity map. The previous filter check
        # called DI.store.toggleFacet directly, so it passed while the advertised
        # brush gesture was completely inert — the panel promised "drag a box to
        # filter" and dragging did nothing at all.
        page.click('.switch button[data-page="market"]')
        page.wait_for_timeout(1000)
        chart = page.locator('[data-panel="mk09-opportunity"] .chart')
        chart.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        box = chart.bounding_box()
        page.mouse.move(box["x"] + box["width"] * 0.28, box["y"] + box["height"] * 0.18)
        page.mouse.down()
        for i in range(1, 21):
            page.mouse.move(box["x"] + box["width"] * (0.28 + 0.58 * i / 20),
                            box["y"] + box["height"] * (0.18 + 0.62 * i / 20))
        page.mouse.up()
        page.wait_for_timeout(700)
        brushed = page.evaluate("DI.store.view().filtered.length")
        rep.check("brush-drag actually filters", 0 < brushed < n_before,
                  f"{n_before} -> {brushed}")
        page.evaluate("() => { DI.store.clearFilters(); DI.bus.emit('filter', {}); }")
        page.wait_for_timeout(300)

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

        # ── Pass 6 · the picker, on a context with genuinely empty storage ──
        # A second context, because the first one has the key seeded and there
        # is no honest way to un-remember inside it.
        print("\nfirst run · the clinic picker")
        fresh = browser.new_context(viewport={"width": 1440, "height": 950})
        fp = fresh.new_page()
        pick_errors = []
        fp.on("pageerror", lambda e: pick_errors.append(str(e)))
        fp.goto(DIST.as_uri())
        fp.wait_for_selector("body[data-di-ready='1']", timeout=30000)
        fp.wait_for_timeout(500)

        rep.check("first run shows the picker, not the dashboard",
                  fp.is_visible("#picker") and fp.is_hidden("#canvas"))
        n_cards = fp.locator(".pk__card").count()
        rep.check("the picker lists every clinic", n_cards == fp.evaluate("DI.CL.length"),
                  f"{n_cards} cards")

        fp.fill(".pk__search", "keerthi")
        fp.wait_for_timeout(250)
        rep.check("search narrows the picker",
                  fp.locator(".pk__card").count() < n_cards,
                  f"{fp.locator('.pk__card').count()} match 'keerthi'")

        fp.fill(".pk__search", "zzzznotaclinic")
        fp.wait_for_timeout(250)
        rep.check("the picker has an empty state",
                  fp.is_visible(".pk__empty") and fp.locator(".pk__card").count() == 0)

        fp.fill(".pk__search", "")
        fp.wait_for_timeout(250)
        # Shot here, while the picker is actually on screen — after the reload
        # below it is remembered and gone.
        fp.screenshot(path=str(OUT / "picker-1440.png"), full_page=False)

        want = fp.evaluate("DI.CL[5].display_name")
        fp.locator(".pk__card").nth(5).click()
        fp.wait_for_timeout(700)
        rep.check("choosing a clinic enters the dashboard",
                  fp.is_hidden("#picker") and fp.is_visible("#canvas"))
        rep.check("the chosen clinic becomes the subject",
                  fp.evaluate("DI.store.view().subject.display_name") == want,
                  want[:40])

        # The whole point of the screen: it must not ask twice.
        fp.reload()
        fp.wait_for_selector("body[data-di-ready='1']", timeout=30000)
        fp.wait_for_timeout(500)
        rep.check("the choice is remembered across a reload",
                  fp.is_hidden("#picker")
                  and fp.evaluate("DI.store.view().subject.display_name") == want)

        # The key is namespaced because Chromium treats every file:// document
        # as ONE shared origin — a bare key would collide with any other local
        # page the user has open, including older builds of this report.
        rep.check("the storage key is namespaced",
                  fp.evaluate("Object.keys(localStorage).every(k => k.startsWith('derma-intel.'))"),
                  fp.evaluate("Object.keys(localStorage).join(',')"))

        rep.check("the picker raises no console errors", not pick_errors, pick_errors[:3])
        fresh.close()

        browser.close()

    print(f"\n{len(rep.rows) - len(rep.failed)}/{len(rep.rows)} checks passed")
    for name, _, detail in rep.failed:
        print(f"  FAILED: {name}  {detail}")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(run())
