"""Open the aggregator roundups a run's SERPs surfaced, and read their numbered lists.

"Best laser treatments in Guntur" on Practo or JustDial is a ranked recommendation, and a
clinic sitting at #1 on it has borrowed authority that a Maps-only view cannot see. This pass
opens those pages and records who they list, IN THEIR ORDER.

    python tools/serp_listicles.py --run last --dry-run    # list what would be opened
    python tools/serp_listicles.py --run last --max 15

**It never touches Google.** These are practo.com, justdial.com and the like, so the work costs
nothing against the per-session CAPTCHA budget the SERP capture has to ration — which is why it
is a separate pass rather than something the runners do mid-scrape.

Clinic sites are deliberately skipped: a clinic's own site lists one clinic, itself, and opening
it would tell us only what the SERP already showed.
"""
# Embeddable-Python bootstrap: isolated mode keeps the script's own directory off sys.path.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse

import config
from modules import atomicio, listicles, runstore, serp_collector, serp_entities
from modules import serp_report, serp_session as S


def candidates(data: dict, ctx) -> list:
    """Roundup / directory URLs across every captured query, de-duplicated."""
    screens = {"queries": data["queries"]}
    return listicles.find_candidates(screens, ctx)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Open aggregator roundups and read their rankings")
    p.add_argument("--run", required=True, metavar="RUN_ID", help="run id, or 'last'")
    p.add_argument("--max", type=int, default=20, help="pages to open (default 20)")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    p.add_argument("--wait", type=float, default=4.0, help="seconds to let each page settle")
    args = p.parse_args(argv)

    run_id = args.run
    if run_id == "last":
        runs = runstore.list_runs(config.RUNS_DIR)
        if not runs:
            print("no runs yet.")
            return 2
        run_id = runs[0]["run_id"]
    run_dir = runstore.run_path(config.RUNS_DIR, run_id)
    manifest = runstore.read_manifest(run_dir)
    if not manifest:
        print(f"no such run: {run_id}")
        return 2

    qrows = S.load_query_rows(run_dir)
    data = serp_report.collect_data(run_dir, qrows=qrows)
    ctx = serp_report._context(manifest)
    found = candidates(data, ctx)
    print(f"{run_id}: {len(found)} aggregator/roundup pages found in the captured SERPs")
    for c in found[:args.max]:
        print(f"   {c['domain']:28s} {str(c['title'])[:58]}")
    if args.dry_run:
        print("\ndry run — nothing opened.")
        return 0
    if not found:
        return 0

    lock = S.SessionLock(mode="listicles", run_id=run_id)
    try:
        lock.acquire()
    except S.SessionRefused as exc:
        print(f"refused: {exc}")
        return 2

    driver, pages = None, []
    try:
        driver = S.build_driver(ctx, settle_s=args.wait, ads_settle_s=0.5)
        driver.start()
        for i, cand in enumerate(found[:args.max], start=1):
            print(f"[{i}/{min(len(found), args.max)}] {cand['url'][:78]}", flush=True)
            entry = {"url": cand["url"], "domain": cand["domain"],
                     "title": cand["title"], "query": cand["query"],
                     "platform": cand["platform"], "entries": [], "error": ""}
            try:
                res = driver.fetch_url(cand["url"]) if hasattr(driver, "fetch_url") else None
                html = res if isinstance(res, str) else _raw_get(driver, cand["url"], args.wait)
                entry["entries"] = listicles.extract_entries(html)
                print(f"      {len(entry['entries'])} listed")
            except Exception as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
                print(f"      failed: {entry['error']}")
            pages.append(entry)
    finally:
        try:
            if driver is not None:
                driver.stop()
        finally:
            lock.release()

    # Rank clinics by how many roundups list them, keeping the best position each achieved.
    stats: dict = {}
    for page in pages:
        for e in page["entries"]:
            name = serp_entities.clean_name(e["name"])
            if len(name) < 4:
                continue
            key = serp_entities.canonical(name)
            st = stats.setdefault(key, {"name": name, "pages": 0, "best": 10 ** 6})
            st["pages"] += 1
            st["best"] = min(st["best"], e.get("stated_number") or e["position"])
    ranked = sorted(({"name": s["name"], "pages": s["pages"],
                      "best": (None if s["best"] >= 10 ** 6 else s["best"])}
                     for s in stats.values()),
                    key=lambda c: (-c["pages"], c["best"] if c["best"] is not None else 999))

    payload = {"collected_at": S.now_iso(), "pages": pages, "clinics": ranked,
               "n_candidates": len(found), "n_opened": len(pages)}
    atomicio.write_json(serp_collector.serp_dir(run_dir) / "listicles.json", payload, indent=2)
    print(f"\nopened {len(pages)} pages, {sum(len(p['entries']) for p in pages)} listings, "
          f"{len(ranked)} distinct clinics")
    for c in ranked[:15]:
        print(f"   {c['pages']}x  best #{c['best']}  {c['name']}")
    print(f"\nwritten: {serp_collector.serp_dir(run_dir) / 'listicles.json'}")
    print(f"report  : {serp_report.build_report(run_dir, qrows=qrows)}")
    return 0


def _raw_get(driver, url: str, wait: float) -> str:
    """Fetch a non-Google page through the same browser, without the SERP interactions."""
    async def _go():
        page = await driver._browser.get(url)
        await page.sleep(wait)
        return await page.get_content()
    return driver._loop.call(_go(), timeout=180)


if __name__ == "__main__":
    raise SystemExit(main())
