"""SERP collection orchestration: statuses, persistence, resume, human-pause.

No network — every test drives a FakeDriver. The behaviours pinned here are the ones whose
absence caused the previous collector to report success while returning nothing:

* a blocked page and a genuinely empty result set must end up as DIFFERENT statuses;
* nothing is ever swallowed into a bare empty list;
* each query is persisted as it completes, so a crash at query 47 keeps queries 1-46.
"""
import json
from pathlib import Path

import pytest

from modules import serp_collector as sc

QROWS = [
    {"rank": 1, "search_query": "acne treatment Guntur"},
    {"rank": 2, "search_query": "best skin doctor in Guntur"},
    {"rank": 3, "search_query": "hair fall treatment Guntur"},
]

ORGANIC_PAGE = """<html><body><textarea name="q">acne treatment Guntur</textarea>
<div id="search"><div id="rso">
 <div class="MjjYud"><div class="tF2Cxc"><div class="yuRUbf">
   <a href="https://www.practo.com/guntur/acne"><h3 class="LC20lb">Acne care Guntur</h3></a>
 </div><div class="VwiC3b">Top dermatologists.</div></div></div>
</div></div></body></html>"""

EMPTY_PAGE = """<html><body><textarea name="q">obscure query</textarea>
<div id="search"><div id="rso"></div></div>
<p>Your search - obscure query - did not match any documents.</p></body></html>"""

BLOCKED_PAGE = """<html><body><form id="captcha-form"></form>
<iframe src="https://www.google.com/recaptcha/api2/anchor"></iframe>
<p>Our systems have detected unusual traffic from your computer network.</p></body></html>"""


class FakeDriver:
    """Scripted driver: maps query text -> (html, final_url) or raises."""

    def __init__(self, script, screenshot=True):
        self.script = script
        self.calls = []
        self.started = self.stopped = False
        self._screenshot = screenshot

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def fetch(self, query_text, screenshot_path=None):
        self.calls.append(query_text)
        item = self.script.get(query_text, ORGANIC_PAGE)
        if isinstance(item, Exception):
            raise item
        html, url = item if isinstance(item, tuple) else (item, "https://www.google.com/search")
        if self._screenshot and screenshot_path:
            Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
            Path(screenshot_path).write_bytes(b"\x89PNG fake")
        return sc.FetchResult(html=html, final_url=url, screenshot_path=screenshot_path)


def collect(tmp_path, script, **kw):
    driver = FakeDriver(script)
    data = sc.collect_serps(QROWS, driver=driver, run_dir=tmp_path, pace=lambda: None,
                            sleep=lambda s: None, **kw)
    return driver, data


# --- status discrimination: the core defect this module exists to fix -------------

def test_blocked_page_is_recorded_as_blocked_not_as_empty_results(tmp_path):
    _, data = collect(tmp_path, {"acne treatment Guntur": BLOCKED_PAGE}, max_block_retries=0)
    log = sc.read_fetch_log(tmp_path)
    assert log["1"]["status"] == sc.STATUS_BLOCKED
    # and it must NOT appear as a successfully-captured query
    assert all(q["rank"] != 1 for q in data["queries"])


def test_genuinely_empty_serp_is_zero_results_not_blocked(tmp_path):
    _, data = collect(tmp_path, {"acne treatment Guntur": EMPTY_PAGE})
    log = sc.read_fetch_log(tmp_path)
    assert log["1"]["status"] == sc.STATUS_ZERO
    entry = next(q for q in data["queries"] if q["rank"] == 1)
    assert entry["blocks"] == []


def test_readable_page_with_no_blocks_and_no_empty_marker_is_an_anomaly(tmp_path):
    """Not blocked, page rendered, yet nothing parsed -> flag for a human, never silently zero."""
    odd = "<html><body><div id='search'><div id='rso'><div class='xx'>?</div></div></div></body></html>"
    _, _ = collect(tmp_path, {"acne treatment Guntur": odd})
    assert sc.read_fetch_log(tmp_path)["1"]["status"] == sc.STATUS_ANOMALY


def test_driver_exception_is_recorded_as_error_with_message(tmp_path):
    _, _ = collect(tmp_path, {"acne treatment Guntur": RuntimeError("browser died")})
    rec = sc.read_fetch_log(tmp_path)["1"]
    assert rec["status"] == sc.STATUS_ERROR
    assert "browser died" in rec["error"]


def test_one_failing_query_does_not_abort_the_run(tmp_path):
    _, data = collect(tmp_path, {"acne treatment Guntur": RuntimeError("boom")})
    log = sc.read_fetch_log(tmp_path)
    assert log["2"]["status"] == sc.STATUS_PARSED
    assert log["3"]["status"] == sc.STATUS_PARSED
    assert len(data["queries"]) == 2


# --- persistence & resume ---------------------------------------------------------

def test_each_query_is_persisted_as_it_completes(tmp_path):
    collect(tmp_path, {})
    for rank in (1, 2, 3):
        assert (tmp_path / "serp" / "pages" / f"q{rank:03d}.json").exists()
        assert (tmp_path / "serp" / "html" / f"q{rank:03d}.html").exists()
    assert (tmp_path / "serp" / "fetch_log.json").exists()


def test_resume_skips_already_captured_queries(tmp_path):
    collect(tmp_path, {})
    driver2 = FakeDriver({})
    sc.collect_serps(QROWS, driver=driver2, run_dir=tmp_path, pace=lambda: None,
                     sleep=lambda s: None)
    assert driver2.calls == [], "resume re-fetched queries that were already captured"


def test_resume_retries_blocked_and_error_queries(tmp_path):
    collect(tmp_path, {"acne treatment Guntur": BLOCKED_PAGE,
                       "hair fall treatment Guntur": RuntimeError("x")}, max_block_retries=0)
    driver2 = FakeDriver({})  # everything succeeds this time
    sc.collect_serps(QROWS, driver=driver2, run_dir=tmp_path, pace=lambda: None,
                     sleep=lambda s: None)
    assert sorted(driver2.calls) == sorted(["acne treatment Guntur", "hair fall treatment Guntur"])
    log = sc.read_fetch_log(tmp_path)
    assert log["1"]["status"] == sc.STATUS_PARSED
    assert log["3"]["status"] == sc.STATUS_PARSED


def test_raw_html_is_retained_so_a_parser_fix_can_reparse_without_rescraping(tmp_path):
    collect(tmp_path, {})
    saved = (tmp_path / "serp" / "html" / "q001.html").read_text(encoding="utf-8")
    assert "<h3" in saved


# --- human-in-the-loop CAPTCHA pause ----------------------------------------------

def test_block_invokes_the_pause_hook_and_retries(tmp_path):
    seen = []

    class OnceBlocked(FakeDriver):
        def fetch(self, query_text, screenshot_path=None):
            if query_text == "acne treatment Guntur" and not seen:
                return sc.FetchResult(html=BLOCKED_PAGE, final_url="https://www.google.com/sorry/index",
                                      screenshot_path=None)
            return super().fetch(query_text, screenshot_path)

    def pause(info):
        seen.append(info)
        return True  # operator solved it

    driver = OnceBlocked({})
    sc.collect_serps(QROWS, driver=driver, run_dir=tmp_path, pause_cb=pause,
                     pace=lambda: None, sleep=lambda s: None)
    assert len(seen) == 1
    assert seen[0]["query"] == "acne treatment Guntur"
    assert sc.read_fetch_log(tmp_path)["1"]["status"] == sc.STATUS_PARSED


def test_pause_hook_declining_leaves_the_query_blocked(tmp_path):
    driver = FakeDriver({"acne treatment Guntur": BLOCKED_PAGE})
    sc.collect_serps(QROWS, driver=driver, run_dir=tmp_path,
                     pause_cb=lambda info: False, pace=lambda: None, sleep=lambda s: None)
    assert sc.read_fetch_log(tmp_path)["1"]["status"] == sc.STATUS_BLOCKED


# --- dataset contract --------------------------------------------------------------

def test_output_matches_the_web_screens_top_level_contract(tmp_path):
    _, data = collect(tmp_path, {})
    assert set(data) == {"meta", "queries"}
    meta = data["meta"]
    for k in ("num_screenshots", "num_queries_expected", "unmatched_queries",
              "tile_h", "tile_overlap"):
        assert k in meta
    assert meta["num_queries_expected"] == 3


def test_unmatched_queries_lists_what_was_not_captured(tmp_path):
    collect(tmp_path, {"acne treatment Guntur": BLOCKED_PAGE}, max_block_retries=0)
    data = sc.finalize(tmp_path, QROWS)
    assert data["meta"]["unmatched_queries"] == ["acne treatment Guntur"]
    assert data["meta"]["num_screenshots"] == 2


def test_each_query_entry_keeps_its_screenshot_reference_for_serp_proof(tmp_path):
    _, data = collect(tmp_path, {})
    for q in data["queries"]:
        assert q["screenshot"], "report.serp_proof needs a per-query artifact reference"
        assert (tmp_path / "serp" / "screenshots" / q["screenshot"]).exists()


def test_run_summary_counts_every_status(tmp_path):
    _, data = collect(tmp_path, {"acne treatment Guntur": BLOCKED_PAGE,
                                 "hair fall treatment Guntur": EMPTY_PAGE},
                      max_block_retries=0)
    summary = sc.run_summary(tmp_path, QROWS)
    assert summary["counts"][sc.STATUS_BLOCKED] == 1
    assert summary["counts"][sc.STATUS_ZERO] == 1
    assert summary["counts"][sc.STATUS_PARSED] == 1
    assert summary["total_queries"] == 3
    assert summary["captured_serps"] == 2  # parsed + zero_results
    assert summary["yield"] == pytest.approx(2 / 3)


def test_web_signal_degrades_loudly_when_most_queries_blocked(tmp_path):
    blocked_all = {q["search_query"]: BLOCKED_PAGE for q in QROWS}
    collect(tmp_path, blocked_all, max_block_retries=0)
    summary = sc.run_summary(tmp_path, QROWS)
    assert summary["web_signal"] == "absent"


def test_web_signal_is_full_when_everything_captured(tmp_path):
    collect(tmp_path, {})
    assert sc.run_summary(tmp_path, QROWS)["web_signal"] == "full"


# --- block detection unit ----------------------------------------------------------

@pytest.mark.parametrize("html,url", [
    (BLOCKED_PAGE, "https://www.google.com/search"),
    ("<html>ok</html>", "https://www.google.com/sorry/index?continue=x"),
    ("<html>ok</html>", "https://consent.google.com/m?continue=x"),
    ("<html><body>To continue, please prove you're not a robot</body></html>",
     "https://www.google.com/search"),
])
def test_strong_block_detection_catches_every_wall(html, url):
    assert sc.detect_block(html, url)


def test_normal_serp_is_not_flagged_as_blocked():
    assert not sc.detect_block(ORGANIC_PAGE, "https://www.google.com/search?q=x")


def test_inline_captcha_without_url_change_is_still_detected():
    """The precise hole in the old collector: it only checked the URL."""
    assert sc.detect_block(BLOCKED_PAGE, "https://www.google.com/search?q=acne")
