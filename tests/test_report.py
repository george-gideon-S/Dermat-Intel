"""Tests for modules.report — the doctor-facing per-clinic + market content engine.

Plain-language, higher-is-better metrics for the "Your clinic" report and the comparative market view.
Pure functions over normalized clinic dicts; no DataFrame/network coupling.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules import report as R

MARKET = {"avg_reviews": 300, "avg_rating": 4.8, "median_appearances": 12}


def _clinic(**kw):
    base = {"name": "X", "key": "x", "has_website": False, "owned": 0, "borrowed": 0, "places": 0,
            "reviews": 0, "rating": 0.0, "appearances": 0, "has_phone": False, "web_appearances": 0,
            "has_own_site": False, "platforms": []}
    base.update(kw)
    return base


# --------------------------------------------------------------------------- visibility score (higher=better)
def test_visibility_score_full_presence_is_high():
    c = _clinic(has_website=True, owned=8, places=8, reviews=400, has_phone=True,
                web_appearances=12, has_own_site=True)
    assert R.visibility_score(c, MARKET) >= 90


def test_visibility_score_maps_only_no_website_is_low_mid():
    c = _clinic(places=8, reviews=300, has_phone=True, web_appearances=5)
    assert 30 <= R.visibility_score(c, MARKET) <= 50


def test_visibility_score_zero_presence_is_near_zero():
    assert R.visibility_score(_clinic(reviews=40), MARKET) <= 12


def test_visibility_score_website_and_ranking_beats_bare():
    strong = _clinic(has_website=True, owned=5, has_own_site=True, places=5, reviews=300,
                     has_phone=True, web_appearances=8)
    weak = _clinic(places=5, reviews=300, has_phone=True)
    assert R.visibility_score(strong, MARKET) > R.visibility_score(weak, MARKET)


def test_visibility_breakdown_components_sum_to_score():
    c = _clinic(has_website=True, owned=8, places=8, reviews=400, has_phone=True, web_appearances=12)
    comps = R.visibility_breakdown(c, MARKET)
    assert {x["key"] for x in comps} == {"website", "search", "maps", "reviews", "phone", "breadth"}
    assert all(0 <= x["earned"] <= x["max"] for x in comps)
    # the breakdown is the score, decomposed (rounding across 6 parts stays within a few points)
    assert abs(sum(x["earned"] for x in comps) - R.visibility_score(c, MARKET)) <= 6


def test_visibility_breakdown_zero_clinic_is_mostly_gaps():
    comps = {x["key"]: x for x in R.visibility_breakdown(_clinic(reviews=0), MARKET)}
    assert comps["website"]["earned"] == 0 and comps["website"]["max"] == 30
    assert comps["search"]["earned"] == 0
    assert comps["phone"]["earned"] == 0


# --------------------------------------------------------------------------- scorecard (plain checks)
def test_scorecard_flags_zero_web_clinic():
    c = _clinic(places=2, reviews=250, has_phone=True)
    checks = {x["key"]: x for x in R.scorecard(c, MARKET)}
    assert checks["website"]["status"] == "bad"
    assert checks["search"]["status"] == "bad"
    assert checks["maps"]["status"] == "good"
    assert checks["reviews"]["status"] in ("warn", "bad")     # 250 vs 300 avg
    assert checks["phone"]["status"] == "good"


def test_scorecard_borrowed_only_warns_and_names_platforms():
    c = _clinic(borrowed=4, platforms=["justdial", "practo"])
    search = next(x for x in R.scorecard(c, MARKET) if x["key"] == "search")
    assert search["status"] == "warn"
    assert "practo" in search["value"].lower() or "justdial" in search["value"].lower()


def test_scorecard_own_site_is_good_on_search():
    c = _clinic(owned=6, has_own_site=True, has_website=True)
    search = next(x for x in R.scorecard(c, MARKET) if x["key"] == "search")
    assert search["status"] == "good"


# --------------------------------------------------------------------------- verdict (one plain line)
def test_verdict_invisible_online_pattern():
    v = R.verdict(_clinic(places=6, reviews=320, has_phone=True), MARKET).lower()
    assert "invisible" in v or "no website" in v


# --------------------------------------------------------------------------- benchmarks (you vs market)
def test_benchmarks_compare_to_market():
    bm = {b["key"]: b for b in R.benchmarks(_clinic(reviews=258, rating=4.9, appearances=20), MARKET)}
    assert bm["reviews"]["you"] == 258 and bm["reviews"]["market"] == 300
    assert bm["reviews"]["better"] is False
    assert bm["rating"]["better"] is True            # 4.9 vs 4.8


# --------------------------------------------------------------------------- market summary + rank
def _scored():
    return [
        _clinic(name="A", key="a", has_website=True, owned=8, places=8, reviews=400, has_phone=True,
                web_appearances=12, has_own_site=True),
        _clinic(name="B", key="b", places=6, reviews=300, has_phone=True, web_appearances=4),
        _clinic(name="C", key="c", reviews=40),
    ]


def test_market_summary_counts():
    s = R.market_summary(_scored(), MARKET)
    assert s["total"] == 3
    assert s["no_website"] == 2
    assert s["zero_web_presence"] == 1               # C never appears in search
    assert s["own_site"] == 1                         # only A ranks its own site


def test_rank_by_visibility_orders_best_first():
    ranked = R.rank_by_visibility(_scored(), MARKET)
    assert ranked[0]["name"] == "A" and ranked[0]["rank"] == 1
    assert R.visibility_rank("c", _scored(), MARKET) == (3, 3)


# --------------------------------------------------------------------------- SERP proof (the killer evidence)
def test_serp_proof_finds_absent_high_demand_query():
    screens = {"queries": [
        {"rank": 1, "search_query": "best dermatologist in Guntur", "screenshot": "a.png", "blocks": [
            {"block_type": "organic", "platform": "practo", "title": "Best Dermatologists - Practo",
             "domain": "practo.com", "position": 1}]},
    ]}
    clinics = [{"name": "Ghost Clinic", "website": "", "place_url": "https://www.google.com/maps/place/?cid=1"}]
    qrows = [{"rank": 1, "search_query": "best dermatologist in Guntur", "search_strength_score": 10}]
    proof = R.serp_proof("1", screens, clinics, qrows)
    assert proof is not None
    assert proof["screenshot"] == "a.png"
    assert proof["query"] == "best dermatologist in Guntur"
    assert any("practo" in p.lower() for p in proof["present"])


def test_serp_proof_none_when_clinic_appears_everywhere():
    screens = {"queries": [
        {"rank": 1, "search_query": "x", "screenshot": "a.png", "blocks": [
            {"block_type": "organic", "platform": "clinic_site", "title": "Ghost Clinic Guntur",
             "domain": "ghostclinic.com", "position": 1}]},
    ]}
    clinics = [{"name": "Ghost Clinic", "website": "https://ghostclinic.com",
                "place_url": "https://www.google.com/maps/place/?cid=1"}]
    qrows = [{"rank": 1, "search_query": "x", "search_strength_score": 10}]
    assert R.serp_proof("1", screens, clinics, qrows) is None
