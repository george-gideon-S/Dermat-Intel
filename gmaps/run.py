"""Run one Google Maps survey: one city, one specialty, one query.

    python -m gmaps.run --geo guntur-ap --specialty dermatology
    python -m gmaps.run --list-packs
    python -m gmaps.run --geo guntur-ap --specialty dermatology --incremental   # quarterly re-run

Resumable: each place is its own file and is only re-done if it is missing or incomplete, so a
killed run resumes without re-scraping and without double counting.
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import json
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from gmaps import packs, taxonomy
from gmaps.extract import (NAV_TIMEOUT_MS, OP_TIMEOUT_MS, card_only_record, dismiss_consent,
                           extract_place, log, read_feed, scroll_feed_to_end)


def atomic_write(path: _Path, payload) -> None:
    """Write via a temp file in the same directory: a killed run must never leave half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def write_status(out: _Path, **fields) -> None:
    p = out / "status.json"
    cur = {}
    if p.exists():
        try:
            cur = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            cur = {}
    cur.update(fields)
    atomic_write(p, cur)


KEEP_FIELDS = (
    "rank", "key", "tier", "name_clean", "name_raw", "category", "card_category",
    "category_mismatch", "relevance", "basis", "address", "address_is_partial",
    "plus_code", "phone", "website", "website_type", "has_own_website", "rating",
    "reviews_total", "reviews_captured", "reviews_coverage", "owner_replies",
    "has_photos", "hours", "topics", "about", "rating_histogram",
    "google_profile_gaps", "place_id", "feature_id", "missing_fields", "not_collected",
    "sorted_newest", "extract_seconds", "skipped_reason", "error", "complete",
    # carried from the results card - these exist ONLY there and vanish once a place is opened.
    # status_text / open_now are excluded on purpose: "Open - closes 7 pm" is true only at the
    # instant of the scrape and is noise in a quarterly snapshot.
    "has_online_booking", "booking_url", "booking_vendor", "service_options",
    "temporarily_closed", "permanently_closed", "no_reviews",
    "is_ad", "review_snippet", "page_rendered", "reviews_error",
)


def write_summary(out: _Path) -> dict:
    """Compact per-place rows for the live page; full detail stays in places/.

    Returns real counts rather than a file tally. An unreadable place file used to be skipped
    with `except: continue`, so a torn write silently removed a clinic from data.json AND from
    the run's own count - the loss was invisible in every artifact.
    """
    rows, corrupt, complete, failed, card_only = [], [], 0, 0, 0
    for f in sorted((out / "places").glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            corrupt.append({"file": f.name, "error": f"{type(exc).__name__}: {exc}"})
            # A corrupt file becomes a VISIBLE row, not a silent omission.
            rows.append({"key": f.stem, "name_clean": f"<unreadable: {f.name}>",
                         "complete": False, "error": f"corrupt place file: {exc}",
                         "rank": 9998})
            continue
        if d.get("complete"):
            complete += 1
        else:
            failed += 1
        if d.get("tier") == "minimal":
            card_only += 1
        rows.append({k: d.get(k) for k in KEEP_FIELDS})
    rows.sort(key=lambda r: r.get("rank") or 9999)
    atomic_write(out / "data.json", rows)
    return {"rows": len(rows), "complete": complete, "failed": failed,
            "card_only": card_only, "corrupt": corrupt}


class RunFinalized(Exception):
    """A finished snapshot is immutable. Ported back from modules/runstore.py, whose guarantee
    this package had lost: without it a later run silently rewrote a historical snapshot's
    manifest, and — because the feed is cached — could even stamp it with a query that was
    never executed."""


class FeedEmpty(Exception):
    """The results feed produced no usable cards. Almost always a selector change, never a town
    with no clinics. Writing this out would hand a dashboard an empty market as fact."""


MIN_PLAUSIBLE_CARDS = 1


def assert_not_finalized(out: _Path) -> None:
    """Refuse to write into a finished snapshot."""
    mf = out / "manifest.json"
    if not mf.exists():
        return
    try:
        m = json.loads(mf.read_text(encoding="utf-8"))
    except Exception:
        return
    if m.get("status") == "complete" or m.get("finalized_at"):
        raise RunFinalized(
            f"{out.name} is a finalized snapshot (finished {m.get('finished_at')}, "
            f"query {m.get('query')!r}). Refusing to write into it.\n"
            f"To re-survey this market, run without --out so a new dated directory is created, "
            f"or pass --allow-overwrite if you truly intend to replace history.")


def finalize(out: _Path, manifest: dict) -> None:
    """Mark a run complete and immutable."""
    atomic_write(out / "manifest.json",
                 {**manifest, "status": "complete",
                  "finalized_at": datetime.now().isoformat(timespec="seconds")})


def update_index(root: _Path, manifest: dict) -> None:
    """Maintain runs/gmaps/index.json so a dashboard can enumerate snapshots without a directory
    scan, and so a quarterly comparison can find its predecessor."""
    idx_path = root / "index.json"
    idx = {"runs": []}
    if idx_path.exists():
        try:
            idx = json.loads(idx_path.read_text(encoding="utf-8")) or {"runs": []}
        except Exception:
            idx = {"runs": []}
    rows = [r for r in idx.get("runs", []) if r.get("run_dir") != manifest.get("run_dir")]
    rows.append({k: manifest.get(k) for k in
                 ("run_dir", "geography", "specialty", "city", "query", "started_at",
                  "finished_at", "status", "places", "run_health", "feed_end_reason",
                  "pack_fingerprint")})
    rows.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    idx["runs"] = rows
    atomic_write(idx_path, idx)


def pack_fingerprint(ctx) -> dict:
    """A hash of the rules a run was scored with.

    A quarterly tightening of one pack token silently changes verdicts between snapshots; without
    this, that shift is indistinguishable from a real change in the market.
    """
    import hashlib

    def h(obj):
        return hashlib.sha1(json.dumps(obj, sort_keys=True,
                                       ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    return {"specialty_pack": h(ctx.spec), "geography_pack": h(ctx.geo)}


def place_path(out: _Path, key: str) -> _Path:
    return out / "places" / (key.replace(":", "_").replace("/", "_") + ".json")


def is_done(path: _Path) -> bool:
    """Completeness lives inside the file, not in whether the file exists.

    An error stub is a file too; keying on existence alone would mark failures as finished and
    they would never be retried.
    """
    if not path.exists():
        return False
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("complete"))
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Google Maps market survey: one city, one specialty")
    ap.add_argument("--geo")
    ap.add_argument("--specialty")
    ap.add_argument("--query", help="override the search query text")
    ap.add_argument("--out", help="run directory (default: runs/gmaps/<geo>_<specialty>_<date>)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pace", type=float, default=3.0)
    ap.add_argument("--incremental", action="store_true",
                    help="stop each place's review scroll at the first already-known review")
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--list-packs", action="store_true")
    ap.add_argument("--allow-overwrite", action="store_true",
                    help="permit writing into a finalized snapshot (destroys history)")
    args = ap.parse_args()

    if args.list_packs:
        print(json.dumps({"geographies": packs.available_geographies(),
                          "specialties": packs.available_specialties()}, indent=2))
        return 0
    if not (args.geo and args.specialty):
        ap.print_help()
        return 2

    try:
        ctx = packs.load(args.geo, args.specialty)
    except (packs.PackNotFound, packs.InvalidPack) as exc:
        print("pack error:", exc)
        return 2

    query = args.query or ctx.search_query()
    out = _Path(args.out or f"runs/gmaps/{args.geo}_{args.specialty}_"
                            f"{datetime.now().strftime('%Y-%m-%d')}")
    if not args.allow_overwrite:
        try:
            assert_not_finalized(out)
        except RunFinalized as exc:
            print(f"\nREFUSED: {exc}\n")
            return 3
    (out / "places").mkdir(parents=True, exist_ok=True)

    started = time.time()
    prior = {}
    if args.incremental:
        for f in (out / "places").glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                ids = {r["review_id"] for r in d.get("reviews", []) if r.get("review_id")}
                if ids:
                    prior[d.get("key")] = ids
            except Exception:
                pass
        log(f"incremental: {len(prior)} places have known reviews")

    # Preserve the original start time across resumes: rebuilding it unconditionally destroyed
    # the record of when a snapshot actually began.
    prior_manifest = {}
    if (out / "manifest.json").exists():
        try:
            prior_manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        except Exception:
            prior_manifest = {}
    now_iso = datetime.now().isoformat(timespec="seconds")
    manifest = {**ctx.as_manifest(), "query": query, "run_dir": str(out),
                "started_at": prior_manifest.get("started_at") or now_iso,
                "last_run_at": now_iso,
                "resumed": bool(prior_manifest),
                "status": "running",
                "incremental": args.incremental,
                "limit": args.limit or None,
                # a --limit run surveys a subset; without this recorded, comparing it to a full
                # snapshot fabricates dozens of "closures" that never happened
                "partial_survey": bool(args.limit),
                "pack_fingerprint": pack_fingerprint(ctx),
                "gmaps_version": "2.0"}
    atomic_write(out / "manifest.json", manifest)
    write_status(out, started_at=started, finished=False, done=0, total=0,
                 query=query, city=ctx.city, specialty=ctx.display_name,
                 current="opening search", errors=0)

    log(f"market : {ctx.city} ({ctx.geo.get('country')})")
    log(f"speciality: {ctx.display_name}")
    log(f"query  : {query}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        c = browser.new_context(locale=f"{ctx.extract_hl}-{ctx.gl.upper()}",
                                timezone_id=ctx.timezone,
                                viewport={"width": 1400, "height": 950},
                                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                                            "Chrome/151.0 Safari/537.36"))
        c.set_default_timeout(OP_TIMEOUT_MS)
        c.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        page = c.new_page()

        feed_file = out / "feed.json"
        feed, feed_reason = None, ""
        if feed_file.exists():
            cached = json.loads(feed_file.read_text(encoding="utf-8"))
            cached_cards = cached.get("cards") or []
            cached_reason = cached.get("feed_end_reason", "")
            cached_query = cached.get("query", "")
            # A cached feed is only reusable if it is non-empty, ended cleanly, and answered THIS
            # query. Reusing blindly meant an empty or truncated capture was replayed forever, and
            # a different --specialty silently re-processed the previous specialty's feed.
            if not cached_cards:
                log("cached feed has 0 cards - discarding and re-capturing")
            elif cached_reason in ("budget_exhausted", "max_rounds"):
                log(f"cached feed ended on {cached_reason} (incomplete) - re-capturing")
            elif cached_query and cached_query != query:
                log(f"cached feed was for a different query ({cached_query!r}) - re-capturing")
            else:
                feed, feed_reason = cached_cards, cached_reason
                log(f"reusing captured feed: {len(feed)} cards ({cached_reason})")

        if feed is None:
            url = ctx.maps_url(query)
            log(f"opening {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            time.sleep(4)
            dismiss_consent(page)
            time.sleep(2)
            n, feed_reason = scroll_feed_to_end(page)
            feed = read_feed(page)
            # Abort BEFORE writing anything. An empty feed is a selector change, not an empty
            # market, and persisting it would both publish a false result and poison later runs.
            if len(feed) < MIN_PLAUSIBLE_CARDS:
                write_status(out, finished=False, run_health="failed",
                             error="feed produced 0 cards", elapsed=round(time.time() - started))
                browser.close()
                raise FeedEmpty(
                    f"the results feed produced {len(feed)} cards for {query!r} "
                    f"(scroll ended: {feed_reason}).\nThis is almost certainly a Google markup "
                    f"change, not an empty market. Nothing has been written.\n"
                    f"Re-verify the card selectors against "
                    f"archive/gmaps_v1_2026-08-20/probe_evidence/listing_page.html")
            atomic_write(feed_file, {"query": query, "captured_at":
                                     datetime.now().isoformat(timespec="seconds"),
                                     "cards": feed, "count": len(feed),
                                     "feed_end_reason": feed_reason})
            log(f"feed captured: {len(feed)} cards ({feed_reason})")

        if args.limit:
            feed = feed[:args.limit]

        # Decide the tier for every card BEFORE opening anything, so the run knows its own size.
        for card in feed:
            v = taxonomy.classify(card.get("category") or "", card.get("name") or "", ctx.spec)
            card["verdict"] = v
            card["tier"] = taxonomy.extraction_tier(v["relevance"])
        full = [c for c in feed if c["tier"] == "full" and not c.get("dup_of_rank")]
        minimal = [c for c in feed if c["tier"] == "minimal" and not c.get("dup_of_rank")]
        log(f"tiering: {len(full)} to open in full, {len(minimal)} card-only "
            f"(saves ~{round(len(minimal)*40/60)} min)")
        # Total is the number of PLACES that will be written, not the number of cards. Google
        # lists some places twice (measured: SITARA SKIN AND LASER at ranks 19 and 21), so
        # counting cards left the progress stuck at 97/98 forever.
        planned = len(full) + len(minimal)
        write_status(out, total=planned, feed_cards=len(feed),
                     duplicates=len(feed) - planned,
                     to_open=len(full), card_only=len(minimal))

        # card-only places first: they cost nothing and make the page useful immediately
        for card in minimal:
            path = place_path(out, card["key"])
            if is_done(path):
                continue
            atomic_write(path, card_only_record(card, ctx, card["verdict"]))
        write_summary(out)
        # card-only places are finished work and must count toward progress
        write_status(out, done=len(minimal))

        errors = 0
        for i, card in enumerate(full, start=1):
            path = place_path(out, card["key"])
            if is_done(path):
                continue
            write_status(out, current=(card.get("name") or "")[:70],
                         done=len(minimal) + i - 1,
                         errors=errors, elapsed=round(time.time() - started))
            log(f"[{i}/{len(full)}] {(card.get('name') or '')[:52]}")
            try:
                rec = extract_place(page, card, ctx, known_ids=prior.get(card["key"]))
                # A stripped page is a transport failure, not a clinic with no reviews.
                if rec.get("reviews_total") is None and not rec.get("reviews"):
                    log("    degraded page - retrying once")
                    time.sleep(15)
                    rec = extract_place(page, card, ctx, known_ids=prior.get(card["key"]))
                atomic_write(path, rec)
                flag = f" | MISSING: {','.join(rec['missing_fields'])}" if rec["missing_fields"] else ""
                log(f"    {rec['name_clean'][:32]} | {rec['category'][:16]} | {rec['relevance']}"
                    f" | {rec['reviews_captured']}/{rec['reviews_total']} rev"
                    f" | {rec['extract_seconds']}s{flag}")
            except Exception as exc:
                errors += 1
                log(f"    ERROR {type(exc).__name__}: {str(exc)[:120]}")
                atomic_write(path, {"key": card["key"], "rank": card.get("rank"),
                                    "name_clean": card.get("name"), "complete": False,
                                    "error": str(exc)[:300], "place_url": card.get("href")})
                try:            # a broken page can poison the tab; start a clean one
                    page.close()
                    page = c.new_page()
                except Exception:
                    pass
            s = write_summary(out)
            write_status(out, done=len(minimal) + i, errors=errors,
                         failed_places=s["failed"], corrupt_files=len(s["corrupt"]),
                         elapsed=round(time.time() - started))
            time.sleep(args.pace if i % 10 else args.pace * 4)

        browser.close()

    s = write_summary(out)
    surveyed = s["complete"]
    review_failures = 0
    for f in (out / "places").glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("reviews_error"):
                review_failures += 1
        except Exception:
            pass

    # A run's health must be a stated verdict, not something a reader infers from silence.
    fail_rate = s["failed"] / max(1, s["rows"])
    if s["rows"] == 0:
        health = "failed"
    elif fail_rate > 0.25 or s["corrupt"]:
        health = "degraded"
    elif s["failed"] or review_failures or feed_reason in ("budget_exhausted", "max_rounds"):
        health = "partial"
    else:
        health = "ok"

    elapsed = round(time.time() - started)
    final = {**manifest,
             "finished_at": datetime.now().isoformat(timespec="seconds"),
             "elapsed_seconds": elapsed,
             "feed_cards": len(feed),
             "feed_end_reason": feed_reason,
             # counts of what was SURVEYED, not a tally of files: the old count included error
             # stubs and card-only rows and so overstated coverage
             "places": s["rows"],
             "places_complete": s["complete"],
             "places_failed": s["failed"],
             "places_card_only": s["card_only"],
             "corrupt_files": s["corrupt"],
             "review_pane_failures": review_failures,
             "errors": errors,
             "run_health": health}
    finalize(out, final)
    update_index(out.parent, {**final, "status": "complete"})
    write_status(out, finished=True, elapsed=elapsed, current="done",
                 run_health=health, failed_places=s["failed"],
                 corrupt_files=len(s["corrupt"]), review_pane_failures=review_failures)

    log(f"done in {round(elapsed/60,1)} min | health={health} | {s['complete']} complete, "
        f"{s['failed']} failed, {s['card_only']} card-only, {review_failures} review-pane "
        f"failures -> {out}")
    return 0 if health in ("ok", "partial") else 1


def cli() -> int:
    """Turn the two refuse-to-proceed conditions into clear messages and non-zero exits,
    rather than a stack trace that a scheduler would treat as an ordinary crash."""
    try:
        return main()
    except FeedEmpty as exc:
        print(f"\nABORTED: {exc}\n")
        return 4
    except RunFinalized as exc:
        print(f"\nREFUSED: {exc}\n")
        return 3
    except (packs.PackNotFound, packs.InvalidPack) as exc:
        print(f"\nPACK ERROR: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
