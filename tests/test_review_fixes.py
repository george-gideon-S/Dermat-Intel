"""Regression tests for defects an adversarial review found that the module's own tests missed.

Each test is named for the specific defect. They exist so the bug cannot silently return: a
review is only worth as much as the test that pins its finding.
"""
import math

import pytest


# --- #7: _pad poisoned the caller's `seen` set, so padding contributed nothing --------------
def test_pad_does_not_mutate_the_callers_seen_set():
    from modules import packs, query_builder as qb
    ctx = packs.load("guntur-ap", "dermatology")
    seen = set()
    out = qb._pad(ctx, 10, seen, qb.topic_tokens(ctx))
    assert len(out) == 10
    assert seen == set(), "_pad mutated seen; take() would then reject every padding candidate"
    # and every returned candidate is actually acceptable (city, on-topic, no near-me)
    for q in out:
        assert "guntur" in q.lower() and "near me" not in q.lower()


def test_build_reaches_the_threshold_even_when_padding_is_required(monkeypatch):
    """A specialty with few templates must still be filled to `want` by padding, not fall short."""
    from modules import packs, query_builder as qb
    monkeypatch.setattr(qb, "fetch_suggestions", lambda *a, **k: [])
    ctx = packs.load("guntur-ap", "dermatology", query_threshold=140)  # above template supply
    rows = qb.build(ctx)
    assert len(rows) == 140
    assert len({r["search_query"].lower() for r in rows}) == 140


# --- #8: validate(expected=min(want,len(rows))) made the exact-count gate a no-op -----------
def test_validate_actually_enforces_the_exact_count():
    from modules import query_builder as qb
    rows = [{"rank": 1, "search_query": "acne treatment in Guntur"}]
    with pytest.raises(qb.QuerySetInvalid):
        qb.validate(rows, city="Guntur", expected=5)   # 1 != 5 must now fire


# --- #9: a treatment with no phrasings crashed the whole build ------------------------------
def test_pack_validator_rejects_a_phrasingless_treatment():
    from modules import packs
    bad = {"id": "x", "name": "X", "specialist_noun": "d",
           "conditions": [{"id": "c", "phrasings": ["a", "b"]}],
           "treatments": [{"id": "t", "phrasings": []}]}
    with pytest.raises(packs.InvalidPack):
        packs.validate_specialty(bad)


def test_build_survives_a_treatment_with_empty_phrasings(monkeypatch):
    """Even if a pack slips past validation, the autocomplete probe must not IndexError."""
    from modules import packs, query_builder as qb
    ctx = packs.load("guntur-ap", "dermatology", query_threshold=30)
    ctx.spec["treatments"] = list(ctx.spec["treatments"]) + [{"id": "bare", "phrasings": []}]
    calls = []
    monkeypatch.setattr(qb, "fetch_suggestions", lambda seed, **k: calls.append(seed) or [])
    rows = qb.build(ctx)          # must not raise
    assert len(rows) == 30


# --- #5: str(NaN) == "nan" is truthy, so a websiteless clinic read as having a website -------
def test_has_text_is_nan_safe():
    from modules import snapshot_diff as sd
    assert sd._has_text(float("nan")) is False
    assert sd._has_text(None) is False
    assert sd._has_text("   ") is False
    assert sd._has_text("https://x.example") is True


def test_diff_website_signal_is_not_flipped_by_nan():
    """An xlsx-loaded clinic with an empty website cell (NaN) must read has_website False."""
    from modules import snapshot_diff as sd
    a = [{"key": "k", "name": "X", "has_website": sd._has_text(float("nan")), "reviews": 10}]
    b = [{"key": "k", "name": "X", "has_website": sd._has_text(float("nan")), "reviews": 10}]
    d = sd.diff_clinics(a, b)
    # both sides websiteless -> no spurious website_lost/gained, so not "changed"
    assert d["changed"] == []


# --- #6: score_clinics averaged reviews across ALL leagues, dragging the clinic benchmark ----
def test_scoring_by_league_keeps_a_hospital_out_of_the_clinic_average():
    import pandas as pd
    from modules import jobs, packs, scoring_params as sp
    ctx = packs.load("guntur-ap", "dermatology", subject_type="both")
    params = sp.ScoringParams.legacy()
    clinics = pd.DataFrame([
        {"name": "Small Skin Clinic", "types": "Skin care clinic", "website": "x",
         "user_ratings_total": 40, "rating": 4.6, "appearances": 10,
         "result_position_avg": 3.0, "formatted_phone_number": "1", "business_status": "OPERATIONAL",
         "lat": 16.30, "lng": 80.43, "place_url": "?cid=1"},
        {"name": "Beta Skin Clinic", "types": "Dermatologist", "website": "y",
         "user_ratings_total": 60, "rating": 4.7, "appearances": 8,
         "result_position_avg": 4.0, "formatted_phone_number": "1", "business_status": "OPERATIONAL",
         "lat": 16.31, "lng": 80.44, "place_url": "?cid=2"},
    ])
    hospital = pd.DataFrame([
        {"name": "Giant Multi-speciality Hospital", "types": "Hospital", "website": "z",
         "user_ratings_total": 8000, "rating": 4.9, "appearances": 5,
         "result_position_avg": 6.0, "formatted_phone_number": "1", "business_status": "OPERATIONAL",
         "lat": 16.32, "lng": 80.45, "place_url": "?cid=3"},
    ])

    clinics_only = jobs._score_by_league(clinics.copy(), ctx, params)
    with_hospital = jobs._score_by_league(pd.concat([clinics, hospital], ignore_index=True), ctx, params)

    def score_of(df, name):
        return float(df[df["name"] == name]["maps_score"].iloc[0])

    # the clinics' maps_score must be identical whether or not the hospital is in the frame
    assert score_of(clinics_only, "Small Skin Clinic") == score_of(with_hospital, "Small Skin Clinic")
    assert score_of(clinics_only, "Beta Skin Clinic") == score_of(with_hospital, "Beta Skin Clinic")


# --- #1: _stage_maps discarded its computed status and always reported "ok" ------------------
def test_maps_stage_reports_partial_on_a_wholesale_throttle(tmp_path, monkeypatch):
    from modules import jobs, packs
    # every query returns a single FETCH_FAILED row (no OK clinics) -> the market was throttled
    monkeypatch.setattr(jobs, "collect_maps_checkpointed",
                        lambda qrows, run_dir, progress_cb=None, mock=False:
                        [{"name": "x", "status": "FETCH_FAILED", "place_url": "",
                          "source_query": q["search_query"]} for q in qrows])
    monkeypatch.setattr(jobs.storage, "save_rows", lambda *a, **k: None)
    monkeypatch.setattr(jobs.maps_collector, "save_results_xlsx", lambda *a, **k: None)

    class R:
        ctx = packs.load("guntur-ap", "dermatology")
        run_dir = str(tmp_path)
        mock = False
        query_rows = [{"rank": i, "search_query": f"q{i} in Guntur"} for i in range(1, 11)]
        errors = []
        def sub_progress(self, s): return None
        def set_denominator(self, **k): pass
    res = jobs._stage_maps(R())
    assert res.status == "partial", "a wholesale Maps failure must not be reported as ok"


def test_maps_stage_reports_ok_when_queries_yield_clinics(tmp_path, monkeypatch):
    from modules import jobs, packs
    monkeypatch.setattr(jobs, "collect_maps_checkpointed",
                        lambda qrows, run_dir, progress_cb=None, mock=False:
                        [{"name": f"c{q['rank']}", "status": "OK", "place_url": "",
                          "source_query": q["search_query"]} for q in qrows])
    monkeypatch.setattr(jobs.storage, "save_rows", lambda *a, **k: None)
    monkeypatch.setattr(jobs.maps_collector, "save_results_xlsx", lambda *a, **k: None)

    class R:
        ctx = packs.load("guntur-ap", "dermatology")
        run_dir = str(tmp_path)
        mock = False
        query_rows = [{"rank": i, "search_query": f"q{i} in Guntur"} for i in range(1, 11)]
        errors = []
        def sub_progress(self, s): return None
        def set_denominator(self, **k): pass
    assert jobs._stage_maps(R()).status == "ok"


# --- #12: single-token clinics false-matched unrelated listicle names -----------------------
def test_listicle_match_does_not_bind_on_a_short_shared_fragment():
    from modules import listicles, packs
    ctx = packs.load("guntur-ap", "dermatology")
    # clinic distinctive token is the 2-char "vp" — too short to be a safe single-token match
    clinics = [{"key": "k1", "name": "VP Skin Clinic Guntur"}]
    screens = {"queries": [{"search_query": "best dermatologist in Guntur", "blocks": [
        {"block_type": "organic", "platform": "other", "title": "roundup",
         "domain": "b.example", "url": "https://b.example/best"}]}]}
    page = "<h3>VP Enterprises Textiles</h3>"   # shares 'vp' but is not the clinic
    result = listicles.collect(screens, clinics, ctx, fetch=lambda u: page)
    assert not result["mentions"].get("k1"), "short-token false match bound an unrelated name"


# --- #13 / #14: error mapping for resume and diff of nonexistent runs -----------------------
def test_cli_diff_rejects_a_nonexistent_run(tmp_path, monkeypatch, capsys):
    import config
    from run_market import cmd_diff
    monkeypatch.setattr(config, "RUNS_DIR", str(tmp_path))

    class Args:
        diff = ["no_such_a", "no_such_b"]
    assert cmd_diff(Args()) == 2
    assert "no such run" in capsys.readouterr().out
