"""Tier-A SERP driver: nodriver + the real installed Chrome.

Why nodriver rather than the Playwright stack the Maps collector uses: measured on this
machine 2026-08-18, Playwright fails Google's gate even headful, with stealth patches and a
persistent profile (the old collector managed ~17.5% of queries). nodriver speaks CDP directly
without the automation surface Playwright exposes, and cleared Google in the same conditions.

Two operational facts, both measured, are encoded here:

* **The first query on a cold profile draws a CAPTCHA; a warmed session then runs clean.** So
  the profile lives outside the run directory and is never wiped between runs, and `start()`
  warms the session before the first query.
* **Google ignores `uule`.** Geo comes from the city named in the query text (see
  modules/query_builder), never from a URL parameter and never from "near me". A query without
  a city returns whatever city this machine's IP resolves to.

nodriver is asyncio-native, so the browser lives on a dedicated thread with its own event
loop — mirroring why maps_collector wraps sync Playwright in a thread, and keeping the browser
off any event loop the API server owns.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Optional

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")

from modules import serp_collector, serp_parser
from modules.serp_collector import FetchResult

SEARCH_URL = "https://www.google.com/search"
DEFAULT_NUM = 20


def _chrome_path() -> Optional[str]:
    for p in (r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if Path(p).exists():
            return p
    return None  # let nodriver discover it


class _Loop:
    """A private asyncio loop on its own thread; the browser never leaves it."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name="serp-driver", daemon=True)
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def call(self, coro, timeout: float = 180.0):
        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return fut.result(timeout)

    def shutdown(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=10)


#: Climb from the "AI Overview" heading to the overview's own container, stopping at the size
#: discontinuity — the same rule serp_parser._ai_root_from_heading applies server-side, kept
#: in step so the element we click inside is the element we later parse.
_JS_AI_ROOT = """
  // textContent, not innerText: innerText reports only what is VISUALLY rendered, so a
  // collapsed overview measured 18 characters where the DOM held 132 — and the
  // "can't generate" test then ran against text too short to contain the phrase, marking a
  // refusal as a successful generation.
  const tlen = e => e ? (e.textContent || '').replace(/\\s+/g,' ').trim().length : 0;
  const heads = [...document.querySelectorAll('[role="heading"]')]
      .filter(h => /^ai overview/i.test((h.textContent||'').trim()));
  const attr = document.querySelector('[data-attrid="AIOverview"]');
  let root = attr || null;
  if (!root && heads.length) {
    root = heads[0];
    while (root.parentElement && !['BODY','HTML'].includes(root.parentElement.tagName)) {
      if (tlen(root.parentElement) > Math.max(600, tlen(root) * 2)) break;
      root = root.parentElement;
    }
  }
"""

# Raw: every backslash below belongs to the JavaScript regex, not to Python. Without
# the r-prefix Python turned \x00 and \x7F into real control characters and shipped a
# NUL into the page script.
_JS_AI_STATE = "(() => {" + _JS_AI_ROOT + r"""
  if (!root) return JSON.stringify({present:false});
  const raw = (root.textContent || '').replace(/\s+/g,' ').trim();
  // Strip Google's notice bar before judging. The apology renders ABOVE the answer while it
  // streams in, so testing the raw text declared every overview unavailable on the first look
  // and the wait exited after 0.0s with a placeholder.
  const clean = raw
    .replace(/an ai overview is not available for this search/ig,' ')
    .replace(/can'?t generate an ai overview( right now)?\.?/ig,' ')
    .replace(/error translating content\.?/ig,' ')
    .replace(/(please )?try again later\.?/ig,' ')
    .replace(/people also ask/ig,' ')
    .replace(/[^\x00-\x7F]{2,}\s+English/ig,' ')
    .replace(/ai overview/ig,' ')
    .replace(/\s+/g,' ').trim();
  const more = [...root.querySelectorAll('div[role="button"],button,a,span[role="button"]')]
      .filter(b => /^(show more|show all|see more|more)$/i.test((b.innerText||'').trim()));
  return JSON.stringify({present:true, length:clean.length, raw_length:raw.length,
                         unavailable: clean.length < 60, expandable:more.length>0});
})()"""

_JS_AI_EXPAND = "(() => {" + _JS_AI_ROOT + """
  if (!root) return 'no-overview';
  const more = [...root.querySelectorAll('div[role="button"],button,a,span[role="button"]')]
      .filter(b => /^(show more|show all|see more|more)$/i.test((b.innerText||'').trim()));
  if (!more.length) return 'no-button';
  more[0].click();
  return 'clicked';
})()"""

#: "More places" sits under the local pack. Matched on its own label rather than a class,
#: because the label is the one thing Google keeps stable.
_JS_MORE_PLACES = """(() => {
  const cands = [...document.querySelectorAll('a,button,div[role="button"],g-more-link')]
      .filter(e => /^(more places|view all|more businesses|show more places)$/i
                   .test((e.innerText||'').trim()));
  if (!cands.length) return 'no-button';
  const a = cands[0].closest('a') || cands[0].querySelector('a') || cands[0];
  if (a.tagName === 'A' && a.href) return 'href:' + a.href;
  a.click();
  return 'clicked';
})()"""


class NodriverSerpDriver:
    """SerpDriver implementation. One browser for the whole run; one tab per query."""

    def __init__(self, profile_dir: Optional[str] = None, headless: bool = False,
                 settle_s: float = 4.0, ads_settle_s: float = 2.5,
                 gl: str = "in", hl: str = "en", num: int = DEFAULT_NUM,
                 ai_wait_s: float = 25.0, expand_ai: bool = True,
                 more_places: bool = True, more_places_wait_s: float = 6.0):
        self.profile_dir = profile_dir or config.SERP_PROFILE_DIR
        self.headless = headless
        self.settle_s = settle_s
        self.ads_settle_s = ads_settle_s
        self.gl, self.hl, self.num = gl, hl, num
        # An AI overview streams in AFTER first paint; reading the page at 6.5 s captured
        # Google's "can't generate an AI overview right now" placeholder on every single one
        # of 22 captures across two runs. Nothing here is worth having without this wait.
        self.ai_wait_s = ai_wait_s
        self.expand_ai = expand_ai
        self.more_places = more_places
        self.more_places_wait_s = more_places_wait_s
        self._loop: Optional[_Loop] = None
        self._browser = None
        self._page = None        # the tab the last fetch used

    # ---------------------------------------------------------------- lifecycle
    def start(self) -> None:
        import nodriver as uc

        Path(self.profile_dir).mkdir(parents=True, exist_ok=True)
        self._loop = _Loop()

        async def _boot():
            browser = await uc.start(
                browser_executable_path=_chrome_path(),
                user_data_dir=self.profile_dir,
                headless=self.headless,
                browser_args=["--window-size=1366,900", f"--lang={self.hl}-IN"],
            )
            page = await browser.get(f"https://www.google.com/?hl={self.hl}&gl={self.gl}")
            await page.sleep(3.0)   # session warm-up: cold profiles draw a CAPTCHA
            return browser

        self._browser = self._loop.call(_boot(), timeout=180)

    def stop(self) -> None:
        if self._browser is not None:
            try:
                self._browser.stop()
            except Exception:
                pass
            self._browser = None
        if self._loop is not None:
            self._loop.shutdown()
            self._loop = None

    # ---------------------------------------------------------------- fetch
    def search_url(self, query_text: str) -> str:
        return (f"{SEARCH_URL}?q={urllib.parse.quote_plus(query_text)}"
                f"&gl={self.gl}&hl={self.hl}&num={self.num}&pws=0")

    def is_blocked(self) -> Optional[bool]:
        """Is the browser CURRENTLY sitting on a wall?

        Reads the page already loaded — no new Google request, so polling this while a human
        works on the CAPTCHA costs nothing against the request budget that caused the wall.

        Returns None when the answer is unknown (no browser, or the read failed), so a caller
        can tell "not blocked" from "could not tell" and never treat a failed probe as a solve.
        """
        if self._browser is None or self._loop is None:
            return None

        async def _probe():
            # The tab the last fetch used — NOT main_tab. nodriver's main_tab is not
            # necessarily the tab showing the CAPTCHA, so probing it read a different page
            # entirely: a solved wall was never noticed and the run sat there until timeout.
            page = self._page or self._browser.main_tab
            html = await page.get_content()
            url = str(getattr(page, "url", "") or "")
            return bool(serp_collector.detect_block(html, url))

        try:
            return self._loop.call(_probe(), timeout=45)
        except Exception:
            return None

    async def _eval(self, page, expression: str, default=None):
        """Run JS in the page. A page that refuses to evaluate must not fail the capture."""
        try:
            return await page.evaluate(expression, await_promise=False)
        except Exception:
            return default

    async def _settle_ai_overview(self, page) -> dict:
        """Wait for the AI overview to finish generating, then expand it.

        It streams in after first paint, so a fixed sleep reads a placeholder or a half-built
        answer. Poll instead, and stop on whichever comes first: Google says it cannot
        generate one, the text stops growing, or the budget runs out. A query with no overview
        at all costs the full wait exactly once — there is no way to distinguish "none" from
        "not yet" without waiting.
        """
        state = {"present": False, "available": False, "waited_s": 0.0,
                 "expanded": False, "settled": "timeout", "length": 0}
        deadline = time.monotonic() + self.ai_wait_s
        stable, last_len = 0, -1
        while time.monotonic() < deadline:
            raw = await self._eval(page, _JS_AI_STATE)
            try:
                cur = json.loads(raw) if isinstance(raw, str) else {}
            except (TypeError, ValueError):
                cur = {}
            if cur.get("present"):
                state["present"] = True
                state["length"] = cur.get("length", 0)
                if cur.get("unavailable"):
                    state.update(available=False, settled="unavailable")
                    break
                state["available"] = True
                stable = stable + 1 if cur.get("length") == last_len else 0
                last_len = cur.get("length")
                if stable >= 2:                 # two identical reads ~1.6 s apart
                    state["settled"] = "stable"
                    break
            await page.sleep(0.8)
        state["waited_s"] = round(self.ai_wait_s - max(0.0, deadline - time.monotonic()), 1)

        if state["available"] and self.expand_ai:
            # "Show more" reveals the rest of the answer — and the clinics named in it.
            if await self._eval(page, _JS_AI_EXPAND) == "clicked":
                state["expanded"] = True
                await page.sleep(1.5)
        return state

    async def _collect_more_places(self, page, serp_url: str) -> dict:
        """Open the local pack's full list and read the names in order.

        Costs ONE extra Google page load per query, and Google's wall is measured in requests,
        not queries: 15 queries with this enabled cost ~43 loads and drew a CAPTCHA at exactly
        the point 40 bare queries do.

        Deliberately does NOT navigate back to the SERP afterwards. The HTML, the final URL and
        the screenshot are all captured before this runs, so nothing downstream needs the
        results page again — and the next query navigates away regardless. That return trip was
        a third of the cost of this feature and bought nothing.
        """
        out = {"status": "not_attempted", "names": [], "url": "", "requests": 0}
        result = await self._eval(page, _JS_MORE_PLACES)
        if result in (None, "no-button"):
            out["status"] = "no_button"          # this SERP had no expandable local pack
            return out
        try:
            if isinstance(result, str) and result.startswith("href:"):
                out["url"] = result[5:]
                page = await self._browser.get(out["url"])
            out["requests"] = 1
            await page.sleep(self.more_places_wait_s)
            html = await page.get_content()
            out["url"] = out["url"] or str(getattr(page, "url", "") or "")
            names = serp_parser.local_listing_names(html)
            out["names"] = names
            out["status"] = "ok" if names else "empty"
        except Exception as exc:
            out["status"] = f"failed:{type(exc).__name__}"
        return out

    def fetch(self, query_text: str, screenshot_path: Optional[str] = None) -> FetchResult:
        if self._browser is None:
            raise RuntimeError("driver not started")
        serp_url = self.search_url(query_text)

        async def _go():
            page = await self._browser.get(serp_url)
            self._page = page          # what is_blocked() must probe
            requests = 1
            await page.sleep(self.settle_s)
            # Ads inject after first paint; without this wait the sponsored blocks — half of
            # the OWNED signal — silently never appear.
            await page.sleep(self.ads_settle_s)

            extras = {}
            html = await page.get_content()
            # Skip every interaction on a wall: the page is a CAPTCHA, there is nothing to
            # expand, and poking at it wastes the budget the collector is about to record.
            walled = bool(serp_collector.detect_block(
                html, str(getattr(page, "url", "") or "")))
            if not walled and self.ai_wait_s > 0:
                extras["ai"] = await self._settle_ai_overview(page)
            html = await page.get_content()   # re-read: generated + expanded overview
            url = str(getattr(page, "url", "") or "")

            # The screenshot is EVIDENCE for this HTML, so it is taken here — after the
            # overview has generated and been expanded, and before anything navigates away.
            # Taking it last put it after the "More places" round trip, which reloads the SERP
            # from scratch: the picture then showed a page with no AI overview yet and no
            # expansion, while the stored HTML showed both.
            shot = await self._screenshot(page, screenshot_path)

            if not walled and self.more_places:
                extras["more_places"] = await self._collect_more_places(page, serp_url)
                requests += (extras["more_places"] or {}).get("requests", 0)

            # Google's wall counts REQUESTS. Recording them per query is the only way to know
            # what the real budget was spent on.
            extras["google_requests"] = requests
            return html, url, shot, extras

        html, url, shot, extras = self._loop.call(_go(), timeout=480)
        return FetchResult(html=html, final_url=url, screenshot_path=shot, extras=extras)

    async def _screenshot(self, page, screenshot_path: Optional[str]):
        """Full-page capture. Evidence is nice to have; the capture itself is never lost."""
        if not screenshot_path:
            return None
        Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            await page.save_screenshot(str(screenshot_path), full_page=True)
            return str(screenshot_path)
        except Exception:
            return None


def build_driver(**kw) -> NodriverSerpDriver:
    return NodriverSerpDriver(**kw)
