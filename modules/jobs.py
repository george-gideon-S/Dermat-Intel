"""The JobRunner: one form submission -> one finished, immutable snapshot, unattended.

A job walks a fixed sequence of stages, each checkpointed so a crash resumes where it stopped
rather than restarting from zero. Two of the stages wrap the existing collectors to fix their
one shared defect: `maps_collector.collect` and `reviews_collector.collect_reviews` both saved
their cache only after the whole batch returned, so an interruption at query 47 of 80 lost all
47. The wrappers here drive those collectors in small units and checkpoint between them, so the
most an interruption can cost is one query (maps) or one five-clinic chunk (reviews).

Only one job runs at a time, enforced by a process lock: two concurrent scrapes would share
one browser profile and one set of run-scoped paths and corrupt each other.

Stage failures are explicit. A blocked or partial SERP capture degrades loudly — the manifest
records `web_signal`, scoring falls back to Maps-only, and the run says so — instead of
silently scoring every clinic as invisible on the web when it was the scraper that failed.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")

from modules import (atomicio, dateresolve, maps_collector, packs, reviews_collector,
                     reviews_nlp, runstore, scoring_params, serp_collector, storage,
                     unify_results, vulnerability)

# Stage order is fixed; finalize happens after the loop, not as a stage.
STAGE_ORDER = ("queries", "maps", "reviews", "serp", "listicles", "unify", "score")

_RUN_LOCK = threading.Lock()


class JobAlreadyRunning(Exception):
    """A second job was submitted while one holds the lock."""


@dataclass
class StageResult:
    status: str                       # ok | partial | skipped | failed
    counts: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class Job:
    run_id: str
    run_dir: str
    status: str = "running"
    stages: dict = field(default_factory=dict)
    awaiting_human: bool = False
    errors: list = field(default_factory=list)


# ------------------------------------------------------------------ checkpoint wrappers
def _cp_path(run_dir, name) -> Path:
    return Path(run_dir) / "checkpoints" / f"{name}.json"


def collect_maps_checkpointed(query_rows, run_dir, progress_cb=None, mock=False) -> list:
    """Drive the Maps collector one query at a time, checkpointing after each.

    `maps_collector.collect` launches a fresh browser per query already, so calling it once per
    query adds no real cost — but it does load and save its own `maps_raw.json` each time, which
    turns the collector's end-of-batch save into a per-query save for free.
    """
    cp = atomicio.read_json(_cp_path(run_dir, "maps"),
                            default={"done_ranks": [], "rows": []}) or {"done_ranks": [], "rows": []}
    done = set(cp.get("done_ranks") or [])
    rows = list(cp.get("rows") or [])
    n = len(query_rows)
    for i, q in enumerate(query_rows, start=1):
        rank = q.get("rank") or i
        if rank in done:
            continue
        if progress_cb:
            progress_cb(i, n, q.get("search_query", ""))
        rows.extend(maps_collector.collect([q], mock=mock))
        done.add(rank)
        atomicio.write_json(_cp_path(run_dir, "maps"),
                            {"done_ranks": sorted(done), "rows": rows})
    return rows


def collect_reviews_checkpointed(clinics, run_dir, chunk=5, mock=False, progress_cb=None,
                                 anchor=None) -> dict:
    """Collect reviews in small chunks, checkpointing between, then run NLP.

    Chunking bounds the loss on a crash to at most `chunk` clinics while keeping the collector's
    shared-browser reuse. Review dates are resolved to absolute at capture (`anchor`) because
    the raw "2 months ago" strings rot: next quarter they would silently mean a different date.
    """
    cp = atomicio.read_json(_cp_path(run_dir, "reviews"),
                            default={"done_keys": [], "reviews": {}}) or {"done_keys": [], "reviews": {}}
    done = set(cp.get("done_keys") or [])
    reviews = dict(cp.get("reviews") or {})
    pending = [c for c in clinics if c.get("key") not in done]
    total = len(pending)
    for start in range(0, len(pending), chunk):
        batch = pending[start:start + chunk]
        # Report progress across ALL pending clinics from here, not per-chunk. Forwarding the
        # runner's callback into collect_reviews would make its denominator the chunk size (5),
        # so the bar would read "3/5" and reset every chunk instead of advancing "8/12".
        if progress_cb:
            for j, c in enumerate(batch):
                progress_cb(start + j + 1, total, c.get("name", ""))
        got = reviews_collector.collect_reviews(batch, mock=mock)
        for k, v in got.items():
            if k == "_meta":
                continue
            reviews[k] = v
        for c in batch:
            done.add(c.get("key"))
        atomicio.write_json(_cp_path(run_dir, "reviews"),
                            {"done_keys": sorted(done), "reviews": reviews})
    if anchor is not None:
        reviews = dateresolve.resolve_all(reviews, anchor)
        # Persist the RESOLVED dates back to the reviews cache. The collector wrote raw
        # "2 months ago" strings; without this write the live snapshot's reviews_raw.json keeps
        # only relative phrases (which rot next quarter) while the June backfill stores absolute
        # dates — two schemas for the same immutable artifact. Resolve-at-capture must reach disk.
        reviews_collector._save_cache(reviews)
    reviews_nlp.analyze_all(reviews)
    return reviews


# ------------------------------------------------------------------ real stage impls
def _stage_queries(runner, **kw) -> StageResult:
    from modules import query_builder
    rows, report = query_builder.build_with_report(runner.ctx)
    storage.save_rows(storage.QUERIES_JSON, rows)
    runner.query_rows = rows
    runner.set_denominator(total_queries=len(rows))
    runstore.record_artifact(runner.run_dir, "query_rows", ".cache/query_rows.json")
    return StageResult(status="ok", counts={"queries": len(rows)}, extra={"report": report})


def _stage_maps(runner, **kw) -> StageResult:
    qrows = runner.query_rows or storage.load_rows(storage.QUERIES_JSON) or []
    rows = collect_maps_checkpointed(qrows, run_dir=runner.run_dir,
                                     progress_cb=runner.sub_progress("maps"), mock=runner.mock)
    storage.save_rows(storage.RESULTS_JSON, rows)
    try:
        maps_collector.save_results_xlsx(rows)
    except Exception as exc:  # xlsx is a convenience export, never the source of truth
        runner.errors.append(f"maps xlsx: {exc}")
    ok = [r for r in rows if r.get("status") == "OK"]
    runner.set_denominator(maps_query_count=len(qrows))
    # Degrade loudly: a query "succeeds" if it yielded >=1 OK clinic row (a FETCH_FAILED query
    # yields exactly one non-OK row). If most queries returned nothing, the Maps scrape was
    # throttled, and the stage must SAY partial rather than reporting a wipeout as clean.
    queries_with_data = len({r.get("source_query") for r in ok if r.get("source_query")})
    yield_ratio = queries_with_data / max(len(qrows), 1)
    status = "ok" if (not qrows or yield_ratio >= 0.9) else "partial"
    return StageResult(status=status, counts={"rows": len(rows), "clinics_ok": len(ok),
                                              "queries_with_data": queries_with_data})


def _stage_reviews(runner, **kw) -> StageResult:
    rows = storage.load_rows(storage.RESULTS_JSON) or []
    ok = [r for r in rows if r.get("status") == "OK"]
    clinics = reviews_collector.clinics_from_rows(ok)
    reviews = collect_reviews_checkpointed(clinics, run_dir=runner.run_dir, chunk=5,
                                           mock=runner.mock, anchor=runner.run_date,
                                           progress_cb=runner.sub_progress("reviews"))
    got = sum(1 for v in reviews.values() if v)
    # Reviews are always OK-partial: Google throttles some clinics, and re-running fills them.
    return StageResult(status="ok", counts={"clinics": len(clinics), "with_reviews": got})


def _stage_serp(runner, **kw) -> StageResult:
    qrows = runner.query_rows or storage.load_rows(storage.QUERIES_JSON) or []
    if runner.mock:
        # No browser in mock mode: emit an empty SERP dataset and degrade to Maps-only, loudly.
        empty = {"meta": {"num_screenshots": 0, "num_queries_expected": len(qrows),
                          "unmatched_queries": [q.get("search_query") for q in qrows],
                          "mock": True}, "queries": []}
        atomicio.write_json(config.WEB_SCREENS_CACHE, empty)
        runner.record_web_signal("absent", {"captured_serps": 0, "total_queries": len(qrows)})
        return StageResult(status="skipped", counts={"mock": True})
    driver = runner.build_serp_driver()
    data = serp_collector.collect_serps(qrows, driver, run_dir=runner.run_dir,
                                        progress_cb=runner.sub_progress("serp"),
                                        pause_cb=runner.pause_cb)
    summary = serp_collector.run_summary(runner.run_dir, qrows)
    # Downstream (web_screens / unify) reads the dataset from the cache path.
    atomicio.write_json(config.WEB_SCREENS_CACHE, data)
    runner.record_web_signal(summary["web_signal"],
                             {"captured_serps": summary["captured_serps"],
                              "total_queries": summary["total_queries"]})
    runner.awaiting_human = False
    status = "ok" if summary["web_signal"] == "full" else summary["web_signal"]
    return StageResult(status=status, counts=summary["counts"],
                       extra={"blocked": summary["blocked_queries"]})


def _stage_listicles(runner, **kw) -> StageResult:
    """Third-party roundups. Never blocks the run: a failure here is logged and skipped."""
    try:
        from modules import listicles
        result = listicles.collect_from_run(runner.run_dir, runner.ctx,
                                            driver_factory=runner.build_serp_driver,
                                            fetch=runner.fetch_listicles)
        return StageResult(status="ok", counts={"mentions": result.get("n_mentions", 0),
                                                "unmatched": result.get("n_unmatched", 0)})
    except Exception as exc:
        runner.errors.append(f"listicles: {type(exc).__name__}: {exc}")
        return StageResult(status="skipped", counts={}, errors=[str(exc)])


def _stage_unify(runner, **kw) -> StageResult:
    from modules import web_screens
    rows = storage.load_rows(storage.RESULTS_JSON) or []
    maps_df = vulnerability.aggregate_clinics(rows)
    screens = atomicio.read_json(config.WEB_SCREENS_CACHE, default={}) or {}
    clinics = [{"name": r.get("name"), "website": r.get("website"), "place_url": r.get("place_url")}
               for _, r in maps_df.iterrows()]
    web_by = web_screens.aggregate_web_by_clinic(screens, clinics) if screens.get("queries") else {}
    runner.unified = unify_results.unify(maps_df, web_by)
    runner.web_by = web_by
    return StageResult(status="ok", counts={"clinics": int(len(runner.unified))})


def _stage_score(runner, **kw) -> StageResult:
    params = runner.scoring_params()
    scored = _score_by_league(runner.unified, runner.ctx, params)
    unify_results.save_unified_xlsx(scored)
    try:
        top = vulnerability.top_n(scored, 10)
        vulnerability.save_vulnerable_xlsx(top)
    except Exception as exc:
        runner.errors.append(f"vulnerable xlsx: {exc}")
    runner.scored = scored
    # Canonical clinic records (real dedup_key + both scores) so snapshot diffs read these,
    # not the display-only xlsx which has neither the place_url nor the visibility score.
    from modules import snapshot_diff
    snapshot_diff.write_clinics_json(runner.run_dir, scored, ctx=runner.ctx, params=params)
    runner.record_scoring()
    return StageResult(status="ok", counts={"scored": int(len(scored))})


def _score_by_league(unified, ctx, params):
    """Score each subject league against ITS OWN market average, then recombine.

    vulnerability.score_clinics derives avg_reviews from the frame it is handed (the market the
    few-reviews penalty compares against). Handing it the whole frame lets a multi-specialty
    hospital's several-thousand reviews inflate the average and unfairly penalise every solo
    clinic — the exact cross-league contamination the subject leagues exist to prevent. So we
    split by league, score each subframe, and concatenate. `both` runs get per-league averages;
    a single-league (individual/hospitals) run is unaffected because there is only one league.
    """
    import pandas as pd
    from modules import report_adapter as ra
    if unified is None or unified.empty or ctx is None:
        return vulnerability.score_clinics(unified, params=params)
    rows = unified.to_dict("records")
    league = [ra.league_of(r, ctx) for r in rows]
    unified = unified.copy()
    unified["subject_class"] = league
    parts = [vulnerability.score_clinics(sub.drop(columns=["subject_class"]), params=params)
             for _, sub in unified.groupby("subject_class", sort=False)]
    return pd.concat(parts, ignore_index=True) if parts else unified


#: dispatch table — tests replace entries here to isolate orchestration from real work
STAGE_IMPL: dict[str, Callable] = {
    "queries": _stage_queries,
    "maps": _stage_maps,
    "reviews": _stage_reviews,
    "serp": _stage_serp,
    "listicles": _stage_listicles,
    "unify": _stage_unify,
    "score": _stage_score,
}


# ------------------------------------------------------------------ the runner
class JobRunner:
    def __init__(self, root: Optional[str] = None, mock: bool = False,
                 fetch_listicles: bool = False):
        self.root = root or config.RUNS_DIR
        self.mock = mock
        self.fetch_listicles = fetch_listicles
        self.ctx = None
        self.run_dir = ""
        self.run_id = ""
        self.run_date = None
        self.query_rows = None
        self.unified = None
        self.web_by = {}
        self.scored = None
        self.denominators = {}
        self.web_signal = None
        self.errors: list = []
        self.awaiting_human = False
        self._progress_cb = None
        self._job: Optional[Job] = None

    # --- submission ------------------------------------------------------------
    def run(self, geography: str, specialty: str, subject_type: str = "both",
            query_threshold: Optional[int] = None, run_date: Optional[str] = None,
            progress_cb: Optional[Callable] = None) -> Job:
        if not _RUN_LOCK.acquire(blocking=False):
            raise JobAlreadyRunning("another market analysis is already running")
        try:
            self._progress_cb = progress_cb
            self.ctx = packs.load(geography, specialty, subject_type, query_threshold)
            self.run_date = run_date or datetime.now().strftime("%Y-%m-%d")
            run = runstore.create_run(
                root=self.root, geography=geography, practice=specialty,
                subject_type=subject_type, run_date=self.run_date,
                query_threshold=self.ctx.query_threshold, packs=self.ctx.as_manifest())
            self._bind(run.run_id, run.path)
            self.set_denominator(total_queries=self.ctx.query_threshold,
                                 maps_query_count=self.ctx.query_threshold)
            return self._execute()
        finally:
            _RUN_LOCK.release()

    def resume(self, run_id: str, progress_cb: Optional[Callable] = None) -> Job:
        if not _RUN_LOCK.acquire(blocking=False):
            raise JobAlreadyRunning("another market analysis is already running")
        try:
            self._progress_cb = progress_cb
            path = str(runstore.run_path(self.root, run_id))
            manifest = runstore.read_manifest(path)
            if not manifest:
                raise FileNotFoundError(f"no run {run_id!r} to resume")
            self.ctx = packs.load(manifest["geography"], manifest["practice"],
                                  manifest.get("subject_type", "both"),
                                  manifest.get("query_threshold"))
            self.run_date = manifest.get("run_date")
            self.denominators = dict(manifest.get("denominators") or {})
            self._bind(run_id, path)
            if manifest.get("status") == "complete":
                # Already a finished, immutable snapshot — nothing to resume.
                job = self._job
                job.status = "complete"
                job.stages = {s: "ok (cached)" for s in STAGE_ORDER}
                runstore.deactivate()
                return job
            return self._execute()
        finally:
            _RUN_LOCK.release()

    # --- execution -------------------------------------------------------------
    def _bind(self, run_id, path) -> None:
        self.run_id = run_id
        self.run_dir = str(path)
        runstore.activate(path)
        self._job = Job(run_id=run_id, run_dir=str(path))

    def _execute(self) -> Job:
        job = self._job
        cp = self._load_job_checkpoint()
        try:
            for stage in STAGE_ORDER:
                if cp.get("stages", {}).get(stage) == "ok":
                    job.stages[stage] = "ok (cached)"
                    continue
                self._emit(stage, "start")
                result = STAGE_IMPL[stage](self)
                job.stages[stage] = result.status
                if result.errors:
                    job.errors.extend(result.errors)
                self._checkpoint_stage(stage, result)
                self._emit(stage, result.status, result.counts)
            job.status = "complete"
            job.errors.extend(self.errors)
            runstore.update_manifest(self.run_dir, completeness=self._completeness(job),
                                     errors=job.errors)
            runstore.finalize_run(self.run_dir)
        except Exception as exc:
            job.status = "failed"
            job.errors.append(f"{type(exc).__name__}: {exc}")
            try:
                runstore.update_manifest(self.run_dir, status="failed",
                                         errors=job.errors)
            except runstore.RunFinalized:
                pass
            raise
        finally:
            runstore.deactivate()
        return job

    # --- checkpoints -----------------------------------------------------------
    def _job_cp_path(self) -> Path:
        return Path(self.run_dir) / "checkpoints" / "job.json"

    def _load_job_checkpoint(self) -> dict:
        return atomicio.read_json(self._job_cp_path(), default={"stages": {}}) or {"stages": {}}

    def _checkpoint_stage(self, stage, result: StageResult) -> None:
        cp = self._load_job_checkpoint()
        cp.setdefault("stages", {})[stage] = "ok" if result.status in ("ok", "partial", "skipped") else "failed"
        cp["updated_at"] = datetime.now().isoformat(timespec="seconds")
        atomicio.write_json(self._job_cp_path(), cp)

    # --- manifest recording ----------------------------------------------------
    def set_denominator(self, **kw) -> None:
        self.denominators.update({k: v for k, v in kw.items() if v is not None})

    def record_web_signal(self, signal: str, denominators: Optional[dict] = None) -> None:
        self.web_signal = signal
        if denominators:
            self.set_denominator(**denominators)
        runstore.update_manifest(self.run_dir, web_signal=signal,
                                 denominators=self.denominators)

    def scoring_params(self):
        d = self.denominators
        return scoring_params.ScoringParams.derive(
            maps_query_count=d.get("maps_query_count") or d.get("total_queries") or 0,
            captured_serps=d.get("captured_serps") or 0,
            total_queries=d.get("total_queries") or 0,
            rating_threshold=self.ctx.geo.get("rating_threshold", 4.8) if self.ctx else 4.8)

    def record_scoring(self) -> None:
        runstore.update_manifest(self.run_dir, denominators=self.denominators,
                                 scoring=self.scoring_params().as_manifest())

    def _completeness(self, job: Job) -> dict:
        out = {"stage_status": dict(job.stages), "web_signal": self.web_signal}
        if self.scored is not None:
            try:
                from modules import report_adapter as ra
                out["clinics"] = int(len(self.scored))
                if self.ctx is not None:
                    rows = self.scored.to_dict("records")
                    out["classification"] = ra.classification_report(rows, self.ctx)
                    out["league_counts"] = ra.league_counts(rows, self.ctx)
            except Exception:
                pass
        return out

    # --- collaborators ---------------------------------------------------------
    def build_serp_driver(self):
        from modules import serp_driver_nodriver
        return serp_driver_nodriver.build_driver(
            gl=self.ctx.gl if self.ctx else "in",
            hl=self.ctx.hl if self.ctx else "en")

    def pause_cb(self, info: dict) -> bool:
        """Human-CAPTCHA hook. Surfaces awaiting_human in the manifest; unattended -> False.

        The browser window is visible, so a person watching can solve it, but a headless
        overnight run must not hang forever — it records the block and lets the collector
        degrade loudly rather than wait for a human who isn't there.
        """
        self.awaiting_human = True
        try:
            runstore.update_manifest(self.run_dir, awaiting_human=True, awaiting_query=info)
        except runstore.RunFinalized:
            pass
        return False

    def sub_progress(self, stage: str):
        def _cb(i, n, label):
            if self._progress_cb:
                self._progress_cb({"stage": stage, "status": "progress",
                                   "i": i, "n": n, "label": label,
                                   "run_id": self.run_id})
        return _cb

    def _emit(self, stage: str, status: str, counts: Optional[dict] = None) -> None:
        if self._progress_cb:
            self._progress_cb({"stage": stage, "status": status,
                               "counts": counts or {}, "run_id": self.run_id,
                               "awaiting_human": self.awaiting_human})
