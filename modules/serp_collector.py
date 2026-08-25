"""Collect Google web SERPs for a query set — the automated replacement for manual screenshots.

Design rules, each one a direct response to how the previous collector failed:

1. **Blocked is never empty.** Every query ends in exactly one recorded status:
   parsed / zero_results / blocked / parse_anomaly / error. The old collector detected blocks
   by URL substring only, so an inline CAPTCHA that kept the /search URL fell through to
   "no results found" and was indistinguishable from a market where the clinic truly ranks
   nowhere. That produced a 17.5% yield that read as success.
2. **Nothing is swallowed.** No bare `except: return []`. An exception is a status with a
   message attached.
3. **Persist per query.** HTML, screenshot, parsed page and the fetch log are written as each
   query completes, so a crash at query 47 of 80 keeps 46 captures. Raw HTML is always kept:
   a later parser fix can re-parse historical runs without re-scraping Google.
4. **Degrade loudly.** A run that loses most of its queries reports web_signal absent/partial
   so scoring falls back to Maps-only *and says so*, rather than quietly scoring a clinic as
   invisible on the web when it was really the scraper that failed.

The driver is swappable (`SerpDriver`): nodriver is Tier A, SeleniumBase would be Tier B, and
tests inject a fake. This module never imports a browser.
"""
from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Protocol

from modules import atomicio, serp_parser

STATUS_PARSED = "parsed"
STATUS_ZERO = "zero_results"
STATUS_BLOCKED = "blocked"
STATUS_ANOMALY = "parse_anomaly"
STATUS_ERROR = "error"

#: statuses that mean "we have this query's SERP and need not fetch it again"
TERMINAL_OK = {STATUS_PARSED, STATUS_ZERO}

# Google's verification walls. Checked against BOTH the final URL and the body, because the
# inline interstitial keeps the /search URL.
_BLOCK_URL_MARKERS = ("/sorry/", "consent.google.com", "/interstitial")
_BLOCK_BODY_MARKERS = (
    "unusual traffic", "not a robot", "our systems have detected",
    "systems have detected unusual", "captcha-form",
)
_BLOCK_DOM_RE = re.compile(
    r"""(id=['"]?captcha-form|src=['"][^'"]*recaptcha|class=['"][^'"]*g-recaptcha)""", re.I)

# Google's own "no results" phrasing — the only thing that licenses calling a page zero_results.
_EMPTY_MARKERS = (
    "did not match any documents",
    "your search -", "no results found for",
    "try different keywords",
)


@dataclass
class FetchResult:
    """What a driver returns for one query. `html` is whatever rendered — including a wall.

    `extras` carries anything that required INTERACTION rather than just reading the first
    paint: the AI overview after it finished generating and was expanded, and the local-pack
    list behind "More places". It is a plain dict so a driver that cannot interact (the test
    fake, a future HTTP-only driver) simply leaves it empty.
    """
    html: str = ""
    final_url: str = ""
    screenshot_path: Optional[str] = None
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    extras: dict = field(default_factory=dict)


class SerpDriver(Protocol):  # pragma: no cover - structural type
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def fetch(self, query_text: str, screenshot_path: Optional[str] = None) -> FetchResult: ...


# ------------------------------------------------------------------ detection
# Google's hard refusal. Unlike /sorry/ this keeps the /search URL, shows no CAPTCHA and
# offers a human nothing to solve — so it must be detected by BODY, and it must be told apart
# from a CAPTCHA before anyone is woken up to fix it.
_BLOCK_403_RE = re.compile(
    r"does not have permission to get URL|"
    r"Error\s*403\s*\(Forbidden\)|"
    r"\b403\.\s*(?:</b>\s*)?<?ins>?\s*That[\u2019']s an error",
    re.I)

#: Kinds of wall, because the right response differs. A CAPTCHA is worth waking someone for;
#: a 403 is not — nobody can clear it from the keyboard.
BLOCK_CAPTCHA = "captcha"
BLOCK_DENIED = "denied"
BLOCK_CONSENT = "consent"


def block_kind(reason: str) -> str:
    """Classify a block reason into what can actually be done about it."""
    r = (reason or "").lower()
    if "403" in r or "denied" in r:
        return BLOCK_DENIED
    if "consent" in r:
        return BLOCK_CONSENT
    return BLOCK_CAPTCHA


def detect_block(html: str, final_url: str = "") -> Optional[str]:
    """Return a block reason, or None. Strong: URL *and* DOM *and* body text.

    Applied to every page load, not just the human-assisted path — that asymmetry is what
    let the unattended collector mistake CAPTCHAs for empty markets.

    The 403 check earns its place the hard way: a hard refusal renders no results scaffolding,
    so it fell through to `parse_anomaly` — "page did not render results scaffolding" — which
    reads as a parser problem rather than as Google shutting the door. Two queries in a live
    run were filed that way before this existed.
    """
    url = (final_url or "").lower()
    for marker in _BLOCK_URL_MARKERS:
        if marker in url:
            return f"url:{marker.strip('/')}"
    body = (html or "")
    if _BLOCK_403_RE.search(body):
        return "http:403"
    if _BLOCK_DOM_RE.search(body):
        return "dom:recaptcha"
    low = body.lower()
    for marker in _BLOCK_BODY_MARKERS:
        if marker in low:
            return f"text:{marker.split()[0]}"
    return None


def looks_empty(html: str) -> bool:
    """True only when Google explicitly says it found nothing."""
    low = (html or "").lower()
    return any(m in low for m in _EMPTY_MARKERS)


def classify(html: str, final_url: str, blocks: list) -> tuple[str, Optional[str]]:
    """(status, detail) for one fetched page."""
    reason = detect_block(html, final_url)
    if reason:
        return STATUS_BLOCKED, reason
    if blocks:
        return STATUS_PARSED, None
    if not serp_parser.looks_readable(html):
        return STATUS_ANOMALY, "page did not render results scaffolding"
    if looks_empty(html):
        return STATUS_ZERO, None
    return STATUS_ANOMALY, "results container rendered but no blocks parsed"


# ------------------------------------------------------------------ run-dir layout
def serp_dir(run_dir) -> Path:
    return Path(run_dir) / "serp"


def _paths(run_dir, rank: int) -> dict:
    s = serp_dir(run_dir)
    return {
        "html": s / "html" / f"q{rank:03d}.html",
        "screenshot": s / "screenshots" / f"q{rank:03d}.png",
        "page": s / "pages" / f"q{rank:03d}.json",
        "extras": s / "extras" / f"q{rank:03d}.json",
    }


def extras_path(run_dir, rank: int) -> Path:
    return _paths(run_dir, rank)["extras"]


def read_extras(run_dir, rank: int) -> dict:
    return atomicio.read_json(_paths(run_dir, rank)["extras"], default={}) or {}


def fetch_log_path(run_dir) -> Path:
    return serp_dir(run_dir) / "fetch_log.json"


def read_fetch_log(run_dir) -> dict:
    return atomicio.read_json(fetch_log_path(run_dir), default={}) or {}


def _record(run_dir, rank: int, **fields) -> None:
    log = read_fetch_log(run_dir)
    log[str(rank)] = {**log.get(str(rank), {}), **fields}
    atomicio.write_json(fetch_log_path(run_dir), log, indent=2)


# ------------------------------------------------------------------ collection
def _pace(min_s: float = 5.0, max_s: float = 15.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


def collect_serps(query_rows: list[dict], driver, run_dir,
                  progress_cb: Optional[Callable] = None,
                  pause_cb: Optional[Callable[[dict], bool]] = None,
                  pace: Optional[Callable[[], None]] = None,
                  max_block_retries: int = 1,
                  breather_every: int = 10,
                  breather: Optional[Callable[[], None]] = None,
                  sleep: Optional[Callable[[float], None]] = None,
                  stop_cb: Optional[Callable[[dict], bool]] = None) -> dict:
    """Fetch every query that isn't already captured; return the web_screens dataset.

    `pause_cb(info) -> bool` is the human-CAPTCHA hook: called when a wall is hit, it should
    surface the visible browser window and return True once a person has cleared it.

    `stop_cb(info) -> bool` is asked after each query completes whether to end the session
    early. It exists so a caller can cap a session at N queries or abandon it the moment
    Google puts up a wall, WITHOUT slicing `query_rows` — the full set must still reach
    `finalize`, or web_screens.json would be rewritten containing only the slice. Stopping
    here rather than by raising also keeps the browser shutdown and the reconciliation on
    the normal path.
    """
    run_dir = Path(run_dir)
    pace = pace or _pace
    log = read_fetch_log(run_dir)
    started = False
    n = len(query_rows)
    attempted = 0

    for i, qrow in enumerate(query_rows, start=1):
        rank = qrow.get("rank") or i
        query_text = (qrow.get("search_query") or "").strip()
        if not query_text:
            _record(run_dir, rank, status=STATUS_ERROR, error="empty search_query",
                    query=query_text)
            continue
        prior = log.get(str(rank), {}).get("status")
        if prior in TERMINAL_OK:
            continue  # resume: already captured

        if progress_cb:
            progress_cb(i, n, query_text)
        if not started:
            driver.start()
            started = True
        elif i > 1:
            pace()
            if breather and breather_every and (i - 1) % breather_every == 0:
                breather()

        status = _fetch_one(run_dir, driver, qrow, rank, query_text, pause_cb,
                            max_block_retries, sleep or time.sleep)
        attempted += 1
        if stop_cb and stop_cb({"rank": rank, "query": query_text, "status": status,
                                "attempted": attempted, "i": i, "n": n}):
            break

    if started:
        try:
            driver.stop()
        except Exception:  # a stop failure must not lose a completed run
            pass
    return finalize(run_dir, query_rows)


def _fetch_one(run_dir, driver, qrow, rank, query_text, pause_cb, max_block_retries,
               sleep=time.sleep) -> str:
    paths = _paths(run_dir, rank)
    attempts = 0
    declined = False
    while True:
        try:
            res = driver.fetch(query_text, screenshot_path=str(paths["screenshot"]))
        except Exception as exc:  # recorded, never swallowed
            # detail=None explicitly: _record shallow-merges onto the prior entry, so a rank
            # that was 'blocked' before would keep the old block reason next to the new error
            # and every reader would explain this failure with the previous one.
            _record(run_dir, rank, status=STATUS_ERROR, error=f"{type(exc).__name__}: {exc}",
                    detail=None, query=query_text,
                    at=datetime.now().isoformat(timespec="seconds"))
            return STATUS_ERROR

        html = res.html or ""
        blocks = serp_parser.parse_blocks(html) if html else []
        status, detail = classify(html, res.final_url or "", blocks)

        if status == STATUS_BLOCKED and attempts < max_block_retries and not declined:
            attempts += 1
            cleared = bool(pause_cb({"rank": rank, "query": query_text,
                                     "reason": detail, "url": res.final_url})) if pause_cb else False
            if cleared:
                continue      # a human cleared it — retry, and they may be asked again
            # Nobody cleared it. Asking a second time cannot change that answer, and each
            # extra look costs a slow /sorry page load against an already-flagged session —
            # which is the one thing likely to extend the flag. So allow exactly the single
            # unattended retry that clears a transient interstitial (a consent redirect), then
            # accept the block however high max_block_retries was set for the solve path.
            declined = True
            sleep(min(30 * attempts, 60))
            continue

        atomicio.write_text(paths["html"], html)
        entry = serp_parser.parse_serp(html, query_row=qrow,
                                       screenshot_name=paths["screenshot"].name, index=rank)
        # Trust the driver's report, not the filesystem. A rank re-fetched after an earlier
        # non-terminal attempt already has that attempt's PNG on disk; if this fetch's
        # screenshot save fails, `exists()` would present the OLD image — often the CAPTCHA
        # itself — as evidence for a SERP that parsed cleanly.
        shot_ok = bool(res.screenshot_path) and paths["screenshot"].exists()
        if not shot_ok:
            entry["screenshot"] = None
        if status in TERMINAL_OK:
            atomicio.write_json(paths["page"], entry, indent=2)
            # The interaction results cost a wait and a second page load each — persist them
            # with the capture so a later crash never makes us pay for them twice.
            ai_detail = serp_parser.ai_overview_detail(html)
            if res.extras or ai_detail:
                atomicio.write_json(paths["extras"], {
                    "rank": rank, "query": query_text, "at": res.fetched_at,
                    "ai_overview": ai_detail,
                    "ai_capture": (res.extras or {}).get("ai"),
                    "more_places": (res.extras or {}).get("more_places"),
                    "google_requests": (res.extras or {}).get("google_requests"),
                }, indent=2)
        _record(run_dir, rank, status=status, detail=detail, query=query_text,
                final_url=res.final_url, blocks=len(blocks), screenshot=shot_ok,
                at=res.fetched_at,
                ai=_ai_summary(ai_detail if status in TERMINAL_OK else None),
                more_places=len(((res.extras or {}).get("more_places") or {}).get("names") or []),
                requests=(res.extras or {}).get("google_requests"))
        return status


def _ai_summary(detail) -> Optional[str]:
    """One word for the fetch log: none / unavailable / N chars."""
    if not detail:
        return None
    if not detail.get("available"):
        return "unavailable"
    return f"{detail.get('text_length', 0)}c/{len(detail.get('recommended_clinics') or [])}rec"


# ------------------------------------------------------------------ finalize / summary
def finalize(run_dir, query_rows: list[dict]) -> dict:
    """Reconcile per-query pages into the web_screens.json dataset shape."""
    run_dir = Path(run_dir)
    log = read_fetch_log(run_dir)
    entries, captured_ranks = [], set()
    for qrow in query_rows:
        rank = qrow.get("rank")
        if log.get(str(rank), {}).get("status") not in TERMINAL_OK:
            continue
        page = atomicio.read_json(_paths(run_dir, rank)["page"], default=None)
        if page:
            entries.append(page)
            captured_ranks.add(rank)
    entries.sort(key=lambda e: (e.get("index") is None, e.get("index")))

    unmatched = [q.get("search_query") for q in query_rows if q.get("rank") not in captured_ranks]
    data = {
        "meta": {
            "num_screenshots": len(entries),
            "num_queries_expected": len(query_rows),
            "unmatched_queries": unmatched,
            "tile_h": None,        # kept for shape compatibility with the screenshot pipeline
            "tile_overlap": None,
            "parser_version": serp_parser.PARSER_VERSION,
            "captured_at": datetime.now().isoformat(timespec="seconds"),
        },
        "queries": entries,
    }
    atomicio.write_json(serp_dir(run_dir) / "web_screens.json", data, indent=2)
    return data


def run_summary(run_dir, query_rows: list[dict]) -> dict:
    """Per-status counts + the loud-degradation verdict for the run manifest."""
    log = read_fetch_log(run_dir)
    counts = {s: 0 for s in (STATUS_PARSED, STATUS_ZERO, STATUS_BLOCKED,
                             STATUS_ANOMALY, STATUS_ERROR)}
    for qrow in query_rows:
        st = log.get(str(qrow.get("rank")), {}).get("status")
        if st in counts:
            counts[st] += 1
    total = len(query_rows) or 1
    captured = counts[STATUS_PARSED] + counts[STATUS_ZERO]
    ratio = captured / total
    if ratio >= 0.95:
        signal = "full"
    elif ratio > 0.0:
        signal = "partial"
    else:
        signal = "absent"
    return {
        "counts": counts,
        "total_queries": len(query_rows),
        "captured_serps": captured,
        "yield": ratio,
        "web_signal": signal,
        "blocked_queries": [q.get("search_query") for q in query_rows
                            if log.get(str(q.get("rank")), {}).get("status") == STATUS_BLOCKED],
    }
