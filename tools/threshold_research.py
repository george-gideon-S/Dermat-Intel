"""Evidence for the per-specialty query threshold. Read-only: measures, never writes config.

Two independent measurements, because either alone is misleading:

1. **Discovery saturation** — replay the June snapshot's Maps scrape in query order and count
   cumulative unique clinics. This answers "how many queries before we stop finding new
   clinics", i.e. the floor below which the market is under-sampled. It can only measure up to
   the 50 queries actually run, so a curve still climbing at the end is evidence the real
   threshold is HIGHER than the data can prove — never evidence that 50 is enough.

2. **Phrasing breadth** — how many distinct real phrasings Google's own autocomplete offers
   per condition seed. Discovery saturation says when Maps stops yielding new clinics; breadth
   says how many ways patients actually ask, which is what the web/SERP half of the score
   samples. A specialty with 12 conditions and wide phrasing needs more queries than one with
   4 narrow ones, at the same saturation point.

The bias is deliberately high: a thin query set produces a confident wrong answer, which is
worse than a slow run.

Usage:
    python tools/threshold_research.py [--run RUN_ID] [--no-autocomplete] [--json OUT]
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import json
import random
import statistics
import time
import urllib.parse

import config
from modules import atomicio, httpget, maps_collector, runstore

AUTOCOMPLETE = "https://suggestqueries.google.com/complete/search"

# Dermatology condition seeds — the vocabulary a patient would actually type.
DERM_SEEDS = [
    "acne treatment", "pimples treatment", "hair fall treatment", "hair loss treatment",
    "dandruff treatment", "psoriasis treatment", "eczema treatment", "fungal infection skin",
    "skin allergy treatment", "pigmentation treatment", "dark spots treatment",
    "vitiligo treatment", "wart removal", "mole removal", "scar removal treatment",
    "laser hair removal", "skin whitening treatment", "hair transplant",
    "prp treatment for hair", "chemical peel", "botox treatment", "keloid treatment",
]
SPECIALTY_SEEDS = ["dermatologist", "skin doctor", "skin specialist", "skin clinic",
                   "cosmetologist", "trichologist"]


# ------------------------------------------------------------------ 1. saturation
def discovery_curve(maps_raw: dict, query_rows: list[dict]) -> dict:
    """Cumulative unique clinics as queries are consumed, in the order they were run."""
    order = [q.get("search_query") for q in sorted(query_rows, key=lambda r: (r.get("rank") or 0))]
    order = [q for q in order if q in maps_raw] + [q for q in maps_raw if q not in set(order)]

    seen, curve = set(), []
    for i, q in enumerate(order, start=1):
        for raw in maps_raw.get(q) or []:
            key = maps_collector.dedup_key(raw.get("url", "")) or (raw.get("name") or "").lower()
            if key:
                seen.add(key)
        curve.append({"queries": i, "clinics": len(seen), "query": q})
    return {"order": order, "curve": curve, "total_clinics": len(seen)}


def marginal_yield(curve: list[dict], window: int = 10) -> list[dict]:
    """New clinics per query over a trailing window — the knee detector."""
    out = []
    for i in range(len(curve)):
        lo = max(0, i - window + 1)
        gained = curve[i]["clinics"] - (curve[lo - 1]["clinics"] if lo > 0 else 0)
        spent = i - lo + 1
        out.append({"queries": curve[i]["queries"], "clinics": curve[i]["clinics"],
                    "new_per_query": round(gained / spent, 3)})
    return out


def shuffled_curves(maps_raw: dict, trials: int = 40, seed: int = 7) -> dict:
    """Query order was strength-ranked, which front-loads discovery and flatters saturation.

    Re-running in random orders shows how much of the early plateau is an artifact of ordering
    rather than of the market — the honest saturation point is the pessimistic one.
    """
    rng = random.Random(seed)
    queries = list(maps_raw.keys())
    at = {}
    for _ in range(trials):
        rng.shuffle(queries)
        seen = set()
        for i, q in enumerate(queries, start=1):
            for raw in maps_raw.get(q) or []:
                key = maps_collector.dedup_key(raw.get("url", "")) or (raw.get("name") or "").lower()
                if key:
                    seen.add(key)
            at.setdefault(i, []).append(len(seen))
    return {i: {"mean": round(statistics.mean(v), 2),
                "min": min(v), "max": max(v)} for i, v in sorted(at.items())}


def coverage_points(curve: list[dict], total: int) -> dict:
    """Queries needed to reach 80/90/95/100% of the clinics the whole set ever found."""
    marks = {}
    for pct in (0.8, 0.9, 0.95, 1.0):
        need = pct * total
        hit = next((c["queries"] for c in curve if c["clinics"] >= need), None)
        marks[f"{int(pct * 100)}%"] = hit
    return marks


# ------------------------------------------------------------------ 2. breadth
def suggestions(seed: str, gl: str = "in", hl: str = "en") -> list[str]:
    url = (f"{AUTOCOMPLETE}?client=firefox&hl={hl}&gl={gl}"
           f"&q={urllib.parse.quote_plus(seed)}")
    try:
        data = httpget.get_json(url, timeout=15)
    except httpget.FetchError:
        return []
    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
        return [s for s in data[1] if isinstance(s, str)]
    return []


def breadth(seeds: list[str], city: str = "Guntur", pause: float = 1.0) -> dict:
    """Distinct phrasings per seed, bare and city-qualified. City-qualified is the one that
    matters: it is the only form that samples this market rather than the nation."""
    rows, all_bare, all_city = [], set(), set()
    for seed in seeds:
        bare = suggestions(seed)
        time.sleep(pause)
        local = suggestions(f"{seed} in {city}")
        time.sleep(pause)
        all_bare.update(bare)
        all_city.update(local)
        rows.append({"seed": seed, "bare": len(bare), "city_qualified": len(local),
                     "sample_city": local[:3]})
    return {"per_seed": rows,
            "distinct_bare": len(all_bare),
            "distinct_city": len(all_city),
            "mean_bare": round(statistics.mean([r["bare"] for r in rows]), 2) if rows else 0,
            "mean_city": round(statistics.mean([r["city_qualified"] for r in rows]), 2) if rows else 0}


# ------------------------------------------------------------------ recommendation
def recommend(total_clinics: int, marks: dict, curve_end_slope: float,
              n_conditions: int, mean_phrasings: float, ran_queries: int) -> dict:
    """Threshold = enough queries to ask every condition several ways, floored by saturation.

    Deliberately biased high, and honest about the ceiling: saturation measured over N queries
    can never justify a threshold below N when the curve is still rising at N.
    """
    phrasing_floor = int(round(n_conditions * max(2.0, min(mean_phrasings, 4.0))))
    saturation_floor = marks.get("95%") or ran_queries
    still_climbing = curve_end_slope > 0.0
    floor = max(phrasing_floor, saturation_floor)
    if still_climbing:
        floor = max(floor, ran_queries)          # the data cannot prove a lower number
    recommended = int(round(floor * 1.15 / 5.0) * 5)   # +15% headroom, rounded to 5
    return {
        "phrasing_floor": phrasing_floor,
        "saturation_floor_95pct": saturation_floor,
        "curve_still_climbing_at_end": still_climbing,
        "recommended": recommended,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="guntur-ap_dermatology_both_2026-06-28")
    ap.add_argument("--no-autocomplete", action="store_true")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    run_dir = runstore.run_path(run_id=args.run)
    maps_raw = atomicio.read_json(_Path(run_dir) / ".cache" / "maps_raw.json", default=None)
    query_rows = atomicio.read_json(_Path(run_dir) / ".cache" / "query_rows.json", default=None)
    if not maps_raw:
        print(f"ABORT: no maps_raw.json in {run_dir}")
        return 1

    dc = discovery_curve(maps_raw, query_rows or [])
    curve = dc["curve"]
    total = dc["total_clinics"]
    mg = marginal_yield(curve)
    marks = coverage_points(curve, total)
    shuffles = shuffled_curves(maps_raw)

    print("=" * 72)
    print("1. MAPS DISCOVERY SATURATION  (snapshot #1: Guntur dermatology, June 2026)")
    print("=" * 72)
    print(f"Maps queries replayed : {len(curve)}")
    print(f"Unique clinics found  : {total}")
    print()
    print(f"{'after N queries':>16} | {'clinics':>7} | {'new/query (10q window)':>22}")
    print("-" * 54)
    for row in mg:
        if row["queries"] % 5 == 0 or row["queries"] in (1, len(mg)):
            print(f"{row['queries']:>16} | {row['clinics']:>7} | {row['new_per_query']:>22}")
    print()
    print("queries needed to reach coverage of all clinics ever found:")
    for pct, n in marks.items():
        print(f"   {pct:>4} of {total} clinics : {n} queries")

    print()
    print("order-independence check (40 random query orders — the June order was")
    print("strength-ranked, which front-loads discovery and flatters saturation):")
    print(f"{'after N':>9} | {'mean clinics':>12} | {'worst case':>10}")
    print("-" * 38)
    for n in (5, 10, 15, 20, 25, 30, 40, 50):
        if n in shuffles:
            s = shuffles[n]
            print(f"{n:>9} | {s['mean']:>12} | {s['min']:>10}")

    end_slope = mg[-1]["new_per_query"] if mg else 0.0
    print()
    print(f"marginal yield over the final 10 queries: {end_slope} new clinics/query")
    print("  (> 0 means the market was STILL yielding new clinics when the run ended —")
    print("   50 queries did not exhaust Guntur dermatology)")

    breadth_data = None
    if not args.no_autocomplete:
        print()
        print("=" * 72)
        print("2. PHRASING BREADTH  (Google autocomplete, free + keyless)")
        print("=" * 72)
        print(f"probing {len(DERM_SEEDS)} condition seeds + {len(SPECIALTY_SEEDS)} specialty seeds ...")
        breadth_data = breadth(DERM_SEEDS + SPECIALTY_SEEDS)
        print()
        print(f"{'seed':<30} | {'bare':>5} | {'+city':>5} | example city-qualified phrasing")
        print("-" * 100)
        for r in breadth_data["per_seed"]:
            ex = r["sample_city"][1] if len(r["sample_city"]) > 1 else (
                r["sample_city"][0] if r["sample_city"] else "")
            print(f"{r['seed']:<30} | {r['bare']:>5} | {r['city_qualified']:>5} | {ex[:44]}")
        print()
        print(f"distinct phrasings, bare seeds        : {breadth_data['distinct_bare']}")
        print(f"distinct phrasings, city-qualified    : {breadth_data['distinct_city']}")
        print(f"mean suggestions per seed (bare/city) : "
              f"{breadth_data['mean_bare']} / {breadth_data['mean_city']}")

    print()
    print("=" * 72)
    print("3. RECOMMENDATION")
    print("=" * 72)
    rec = recommend(total, marks, end_slope, n_conditions=len(DERM_SEEDS),
                    mean_phrasings=(breadth_data["mean_city"] if breadth_data else 2.0),
                    ran_queries=len(curve))
    print(f"phrasing floor  ({len(DERM_SEEDS)} conditions x phrasings) : {rec['phrasing_floor']}")
    print(f"saturation floor (95% clinic coverage)          : {rec['saturation_floor_95pct']}")
    print(f"curve still climbing at end of measured data    : {rec['curve_still_climbing_at_end']}")
    print(f"--> RECOMMENDED dermatology threshold           : {rec['recommended']}")
    print()
    print("Caveats you should weigh before accepting:")
    if rec["curve_still_climbing_at_end"]:
        print(" * Saturation is measured over 50 Maps queries only and the curve had NOT")
        print("   flattened — the data cannot justify any number below 50.")
    else:
        print(" * Discovery saturated inside the measured range, but saturation only answers")
        print("   'how many queries to FIND every clinic'. The score measures how often each")
        print("   clinic appears ACROSS the query set, so the threshold must serve phrasing")
        print("   coverage, not discovery — those are different jobs and differ ~3x here.")
    print(" * The June set actually ran 80 queries total (50 Maps + 78 SERPs captured);")
    print("   snapshot comparability argues for staying at or above 80.")
    print(" * Cost of going higher is runtime, not money: ~25-40 min per 80 SERP queries.")

    if args.json:
        atomicio.write_json(args.json, {"discovery": dc, "marginal": mg, "marks": marks,
                                        "shuffles": shuffles, "breadth": breadth_data,
                                        "recommendation": rec}, indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
