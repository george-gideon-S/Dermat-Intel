"""Denominator-coupled scoring constants become functions of the run's actual query counts.

No network. The constants were tuned for one specific run shape — 50 Maps queries, 78 captured
SERPs, 80 total queries — and hardcoded. `DEMAND_FULL = 25` literally meant "25 of 50
searches", and `OWNED_FULL = 6` meant "6 of 78 SERPs". Run 100 queries instead and those
numbers quietly mean something different: saturation arrives earlier, scores compress, and two
snapshots stop being comparable while still looking like plain numbers.

The rule these tests enforce: derivation at June's denominators must reproduce June's
constants EXACTLY, so snapshot #1 is unchanged, and scale proportionally beyond that.
"""
import pytest

from modules import report, scoring_params as sp, vulnerability as vu

JUNE = dict(maps_query_count=50, captured_serps=78, total_queries=80)


# --- legacy pinning: the guard that snapshot #1 keeps its meaning ---------------

def test_june_denominators_reproduce_the_shipped_constants_exactly():
    p = sp.ScoringParams.derive(**JUNE)
    assert p.DEMAND_FULL == vu.DEMAND_FULL == 25
    assert p.OWNED_FULL == vu.OWNED_FULL == 6
    assert p.BORROWED_FULL == vu.BORROWED_FULL == 12
    assert p.PLACES_FULL == report.PLACES_FULL == 8
    assert p.BREADTH_FULL == report.BREADTH_FULL == 10


def test_report_and_vulnerability_agree_on_owned_full():
    """Both modules define OWNED_FULL=6; a single source stops them drifting apart."""
    p = sp.ScoringParams.derive(**JUNE)
    assert p.OWNED_FULL == report.OWNED_FULL == vu.OWNED_FULL


def test_legacy_helper_matches_derivation_at_june_denominators():
    assert sp.ScoringParams.legacy() == sp.ScoringParams.derive(**JUNE)


# --- scaling -------------------------------------------------------------------

def test_demand_full_is_half_the_maps_query_count():
    """'Appears in 25 of 50 searches' is a HALF, not the number 25."""
    assert sp.ScoringParams.derive(maps_query_count=100, captured_serps=78,
                                   total_queries=80).DEMAND_FULL == 50
    assert sp.ScoringParams.derive(maps_query_count=30, captured_serps=78,
                                   total_queries=80).DEMAND_FULL == 15


def test_serp_coupled_constants_scale_with_captured_serps():
    p = sp.ScoringParams.derive(maps_query_count=50, captured_serps=156, total_queries=160)
    assert p.OWNED_FULL == 12
    assert p.BORROWED_FULL == 24
    assert p.PLACES_FULL == 16
    assert p.BREADTH_FULL == 20


def test_constants_are_monotonic_in_their_denominator():
    prev = None
    for serps in (40, 78, 100, 160):
        p = sp.ScoringParams.derive(maps_query_count=50, captured_serps=serps, total_queries=80)
        if prev is not None:
            assert p.OWNED_FULL >= prev
        prev = p.OWNED_FULL


def test_tiny_runs_keep_a_sane_floor():
    """A 5-SERP run must not make one appearance mean 'fully visible'."""
    p = sp.ScoringParams.derive(maps_query_count=4, captured_serps=5, total_queries=5)
    assert p.OWNED_FULL >= 3
    assert p.PLACES_FULL >= 4
    assert p.BREADTH_FULL >= 5
    assert p.DEMAND_FULL >= 1


def test_zero_denominators_do_not_divide_by_zero():
    p = sp.ScoringParams.derive(maps_query_count=0, captured_serps=0, total_queries=0)
    assert p.DEMAND_FULL >= 1 and p.OWNED_FULL >= 3


# --- denominator discipline ----------------------------------------------------

def test_params_carry_all_three_denominators_separately():
    p = sp.ScoringParams.derive(**JUNE)
    assert (p.maps_query_count, p.captured_serps, p.total_queries) == (50, 78, 80)


def test_per_clinic_web_rate_divides_by_captured_serps_not_total_queries():
    """Dividing by 80 would penalise every clinic for 2 SERPs nobody captured."""
    p = sp.ScoringParams.derive(**JUNE)
    assert p.web_rate(39) == pytest.approx(0.5)          # 39 of 78
    assert p.web_rate(39) != pytest.approx(39 / 80)


def test_market_coverage_claims_divide_by_total_queries():
    p = sp.ScoringParams.derive(**JUNE)
    assert p.coverage_rate(78) == pytest.approx(78 / 80)


def test_maps_demand_rate_divides_by_maps_query_count():
    p = sp.ScoringParams.derive(**JUNE)
    assert p.maps_rate(25) == pytest.approx(0.5)


def test_manifest_dict_records_what_was_used():
    d = sp.ScoringParams.derive(**JUNE).as_manifest()
    assert d["scoring_version"] == sp.SCORING_VERSION
    assert d["DEMAND_FULL"] == 25 and d["captured_serps"] == 78


# --- integration with the scorers ----------------------------------------------

CLINIC = {"website": "", "result_position_avg": 9.0, "user_ratings_total": 5,
          "rating": 4.2, "formatted_phone_number": "", "appearances": 25,
          "high_intent_share": 0.5, "lat": 16.3067, "lng": 80.4365}


def test_compute_score_without_params_is_unchanged():
    """Existing callers and the 133 legacy tests must see identical numbers."""
    assert vu.compute_score(CLINIC) == vu.compute_score(CLINIC, params=sp.ScoringParams.legacy())


def test_compute_score_with_scaled_params_moves_the_demand_term():
    """At 100 Maps queries, 25 appearances is half the demand it was at 50."""
    legacy = vu.compute_score(CLINIC, params=sp.ScoringParams.legacy())
    scaled = vu.compute_score(CLINIC, params=sp.ScoringParams.derive(
        maps_query_count=100, captured_serps=78, total_queries=80))
    assert scaled < legacy


def test_web_relevance_uses_params_owned_full():
    c = {"web_data": True, "web_owned_appearances": 6, "web_borrowed_appearances": 0}
    assert vu.web_relevance_vuln(c) == 0          # 6 of 78 saturates under June params
    doubled = sp.ScoringParams.derive(maps_query_count=50, captured_serps=156, total_queries=160)
    assert vu.web_relevance_vuln(c, params=doubled) == 50   # 6 of 12 now


def test_report_components_accept_params_and_default_to_legacy():
    market = {"avg_reviews": 20.0}
    c = {"has_website": True, "owned": 6, "places": 8, "reviews": 20,
         "has_phone": True, "web_appearances": 10}
    assert report.visibility_score(c, market) == 100
    assert report.visibility_score(c, market, params=sp.ScoringParams.legacy()) == 100
    doubled = sp.ScoringParams.derive(maps_query_count=50, captured_serps=156, total_queries=160)
    assert report.visibility_score(c, market, params=doubled) < 100


# --- the false prose ------------------------------------------------------------

def test_opportunity_note_states_the_real_query_count_not_a_hardcoded_fifty():
    """'appears in 48 of 50 searches' was already false — the June run used 80 queries."""
    c = dict(CLINIC, name="X", appearances=48)
    note = vu.build_opportunity_note(
        c, params=sp.ScoringParams.derive(maps_query_count=100, captured_serps=78,
                                          total_queries=100))
    assert "of 100 searches" in note
    assert "of 50 searches" not in note


def test_opportunity_note_defaults_to_the_legacy_denominator():
    c = dict(CLINIC, name="X", appearances=48)
    assert "of 50 searches" in vu.build_opportunity_note(c)


def test_no_hardcoded_denominator_literals_remain_in_scoring_paths():
    """A literal 50/78/80 in a scoring formula is how the denominators got conflated before."""
    import inspect
    for fn in (vu.compute_score, vu.web_relevance_vuln, report._components):
        src = inspect.getsource(fn)
        for bad in ("/ 50", "/ 78", "/ 80", "/50", "/78", "/80"):
            assert bad not in src, f"{fn.__name__} still divides by a hardcoded denominator"
