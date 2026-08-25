"""Re-apply the current query-writing rules to a run's stored query set.

The rules in `query writing.md` evolve. When they do, a run built under the old rules still
carries queries the new rules forbid, and re-categorises differently. This re-reads the run's
own query set, drops what the rules now reject, re-derives every category, and rewrites the
fingerprint the runners check.

    python tools/apply_query_rules.py --run last --dry-run
    python tools/apply_query_rules.py --run guntur-ap_dermatology_both_2026-08-19

**Ranks are never renumbered.** The fetch log, the saved HTML and the screenshots are all keyed
by rank, so shifting them would re-attribute captured SERPs to different queries. Dropped ranks
simply leave gaps, and their captured artifacts stay on disk — unreferenced, not deleted, so a
later decision to restore a query loses nothing.

A dropped query that was already captured leaves the run with FEWER total queries, so the
denominator shrinks and the yield goes up. That is not the run getting better; it is the run
being measured against a smaller, more honest set. The summary says so explicitly.
"""
# Embeddable-Python bootstrap: isolated mode keeps the script's own directory off sys.path.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import json
from datetime import datetime

import config
from modules import atomicio, packs, query_builder as qb, runstore, serp_collector
from modules import serp_session as S
from modules.query_generator import derive_category


def rule_violation(q: str, ctx, vocab, banned_places) -> str:
    """Why this query is no longer allowed, or '' if it is fine."""
    toks = set(qb._norm(q).split())
    hit = toks & banned_places
    if hit:
        return f"names a sub-place ({', '.join(sorted(hit))}) in a small city"
    unknown = qb.unknown_tokens(q, vocab)
    if unknown:
        return f"names something specific ({', '.join(unknown)}) — a clinic or doctor"
    if qb._BANNED_RE.search(q):
        return "'near me' style query"
    if ctx.city and ctx.city.lower() not in q.lower():
        return "does not name the city"
    return ""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Re-apply query-writing rules to a run")
    p.add_argument("--run", required=True, metavar="RUN_ID", help="run id, or 'last'")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="report what would change, write nothing")
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
    rows = S.load_query_rows(run_dir)
    if not rows:
        print(f"{run_id} has no .cache/query_rows.json")
        return 2

    ctx = packs.load(manifest["geography"], manifest["practice"],
                     manifest.get("subject_type", "both"), manifest.get("query_threshold"))
    vocab, banned_places = qb.allowed_vocabulary(ctx), qb.sub_places(ctx)
    log = serp_collector.read_fetch_log(run_dir)

    kept, dropped, recategorised = [], [], []
    for r in rows:
        q = r.get("search_query") or ""
        why = rule_violation(q, ctx, vocab, banned_places)
        if why:
            dropped.append({"rank": r.get("rank"), "query": q, "reason": why,
                            "was_captured": log.get(str(r.get("rank")), {}).get("status")
                            in serp_collector.TERMINAL_OK})
            continue
        new_cat = derive_category(q)
        if new_cat != r.get("category"):
            recategorised.append((r.get("rank"), q, r.get("category"), new_cat))
        row = dict(r)
        row["category"] = new_cat
        row["user_intent"] = qb.intent_for(new_cat, ctx)
        kept.append(row)

    print(f"{run_id}: {len(rows)} queries -> {len(kept)} kept, {len(dropped)} dropped\n")
    if dropped:
        print("DROPPED (rank kept as a gap; captured artifacts stay on disk):")
        for d in dropped:
            mark = "captured" if d["was_captured"] else "never run"
            print(f"  {d['rank']:>3} [{mark:9s}] {d['query']}")
            print(f"      {d['reason']}")
        print()
    if recategorised:
        print(f"RE-CATEGORISED ({len(recategorised)}):")
        for rank, q, old, new in recategorised[:60]:
            print(f"  {rank:>3} {old:22s} -> {new:22s} {q}")
        if len(recategorised) > 60:
            print(f"  … and {len(recategorised) - 60} more")
        print()

    counts: dict = {}
    for r in kept:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    print("CATEGORY MIX:", json.dumps(counts, indent=2))

    captured_before = sum(1 for r in rows
                          if log.get(str(r.get("rank")), {}).get("status")
                          in serp_collector.TERMINAL_OK)
    captured_after = sum(1 for r in kept
                         if log.get(str(r.get("rank")), {}).get("status")
                         in serp_collector.TERMINAL_OK)
    print(f"\nCOVERAGE: {captured_before}/{len(rows)} -> {captured_after}/{len(kept)}")
    print("  (the yield moves because the denominator shrank, not because more was captured)")

    if args.dry_run:
        print("\ndry run — nothing written.")
        return 0

    backup = _Path(run_dir) / ".cache" / f"query_rows.pre-rules-{datetime.now():%Y%m%d-%H%M%S}.json"
    atomicio.write_json(backup, rows, indent=2)
    atomicio.write_json(S.query_rows_path(run_dir), kept, indent=2)

    # The runners refuse to continue against a changed query set. This IS a deliberate change,
    # so re-stamp the fingerprint — and keep the old one, so the reason a resume was ever
    # refused stays answerable.
    state = S.read_state(run_dir)
    old_fp = state.get("query_fingerprint")
    state["query_fingerprint"] = S.query_fingerprint(kept)
    history = list(state.get("query_set_history") or [])
    history.append({"at": S.now_iso(), "from": old_fp, "to": state["query_fingerprint"],
                    "dropped": [d["rank"] for d in dropped], "kept": len(kept),
                    "reason": "re-applied query writing rules"})
    state["query_set_history"] = history
    S.write_state(run_dir, state)

    S.safe_update_manifest(run_dir, query_threshold=len(kept),
                           query_rules_applied_at=S.now_iso())
    print(f"\nwritten. backup: {backup}")
    print(f"fingerprint {old_fp} -> {state['query_fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
