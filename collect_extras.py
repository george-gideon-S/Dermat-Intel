"""Collect the optional extra signals, then rebuild the dashboard with `python derma_web.py`.

  python collect_extras.py --reviews     # scrape Google Maps reviews for every clinic + run NLP
  python collect_extras.py --web         # scrape Google WEB search (opens a real browser; solve the
                                         #   one-time CAPTCHA if shown — headless is blocked by Google)
  python collect_extras.py --reviews --web

Reviews are reliable and resume-safe (re-run to fill any clinics Google throttled). Google web search
requires a headful browser on your desktop; set DERMA_WEB_HEADLESS=1 to force headless (returns nothing
on a flagged network).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from modules import reviews_collector as rc, reviews_nlp as rn, storage, web_collector as wc


def main() -> int:
    args = set(sys.argv[1:])
    if not (args & {"--reviews", "--web"}):
        args = {"--reviews"}  # default
    ok = [r for r in (storage.load_rows(storage.RESULTS_JSON) or []) if r.get("status") == "OK"]
    if not ok:
        print("No clinic data yet — run `python run_pipeline.py` first.")
        return 1

    if "--reviews" in args:
        clinics = rc.clinics_from_rows(ok)
        print(f"Scraping reviews for {len(clinics)} clinics (resume-safe)…")
        reviews = rc.collect_reviews(
            clinics, progress_cb=lambda i, n, nm: print(f"  [{i}/{n}] {nm[:42]}", flush=True))
        rn.analyze_all(reviews)
        got = sum(1 for v in reviews.values() if v)
        print(f"Reviews + NLP done for {got}/{len(clinics)} clinics.")

    if "--web" in args:
        qrows = storage.load_rows(storage.QUERIES_JSON) or []
        print(f"Opening ONE Chrome window for {len(qrows)} Google searches.")
        print("  → When a CAPTCHA appears, just solve it in that window — the script WAITS for you")
        print("    and continues automatically. You usually only solve once or twice (cookies stick),")
        print("    and it saves after every query, so you can stop and resume anytime.\n")
        web = wc.collect_web_interactive(
            qrows, progress_cb=lambda i, n, q: print(f"  [{i}/{n}] {q[:42]}", flush=True))
        got = sum(1 for v in web.values() if v)
        print(f"Google web results captured for {got}/{len(qrows)} queries.")

    print("\nNow rebuild the dashboard:  python derma_web.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
