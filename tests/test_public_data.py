"""Tests for web/public_data.py — the public-dist anonymizer (spec 2026-07-10 §3).

The invariant that matters: NOTHING identifying survives into the public payload —
no real clinic name token, no exact review count, no exact score, no website URL.
"""
import json
import math

import pytest

from web import public_data as pd


# ---------------------------------------------------------------- fixture
def full_payload():
    """Minimal fake of build_web.build_payload() output — 4 clinics, 2 invisible."""
    clinics = [
        {"name": "Sri Venkateswara Skin & Hair Clinic", "appearances": 40, "has_website": True,
         "rating": 4.9, "reviews": 212, "score": 55, "visibility_rank": 1, "visibility_total": 4,
         "website": "https://svskin.example", "has_own_site": True,
         "web": {"owned": 5, "borrowed": 2}},
        {"name": "Lakshmi Derma Care", "appearances": 30, "has_website": False,
         "rating": 4.8, "reviews": 180, "score": 82, "visibility_rank": 3, "visibility_total": 4,
         "website": "", "has_own_site": False, "web": {"owned": 0, "borrowed": 3}},
        {"name": "Guntur Skin Clinic", "appearances": 22, "has_website": False,
         "rating": 4.6, "reviews": 61, "score": 74, "visibility_rank": 4, "visibility_total": 4,
         "website": "", "has_own_site": False, "web": {"owned": 0, "borrowed": 0}},
        {"name": "Ramachandra Cosmetic Centre", "appearances": 9, "has_website": True,
         "rating": 4.2, "reviews": 35, "score": 40, "visibility_rank": 2, "visibility_total": 4,
         "website": "https://rc.example", "has_own_site": False,
         "web": {"owned": 0, "borrowed": 4}},
    ]
    return {
        "generated_at": "2026-07-10T12:00:00",
        "city": "Guntur, Andhra Pradesh, India",
        "kpis": {"unique_clinics": 4, "no_website_count": 2, "avg_rating": 4.62,
                 "avg_reviews": 122, "pct_with_website": 50.0, "queries": 80,
                 "total_appearances": 101},
        "clinics": clinics,
        "median_appearances": 26.0,
    }


def qrows():
    return [
        {"query": "best dermatologist in guntur"},
        {"query": "skin specialist near me guntur"},
        {"query": "acne treatment cost guntur"},
        {"query": "Lakshmi Derma Care reviews"},          # branded -> must be excluded
        {"query": "pigmentation treatment guntur"},
        {"query": "hair fall doctor guntur"},
        {"query": "laser hair removal price guntur"},
        {"query": "eczema specialist guntur"},
        {"query": "dermatologist open sunday guntur"},
        {"query": "venkateswara skin clinic timings"},    # branded -> must be excluded
    ]


def cfg():
    return {"report": 4999, "monitor_qtr": 2999, "monitor_yr": 9999,
            "build_from": 49999, "retainer_mo": 4999,
            "rzp_report": "", "rzp_monitor_qtr": "", "rzp_monitor_yr": "",
            "whatsapp": "919999999999"}


def build():
    return pd.build_public_payload(full_payload(), qrows(), cfg(), salt="test-salt")


# ---------------------------------------------------------------- fnv1a
def test_fnv1a_known_vectors():
    # Canonical FNV-1a 32-bit: fnv1a("") == offset basis; "a"/"abc" well-known values.
    assert pd.fnv1a("") == 2166136261
    assert pd.fnv1a("a") == 0xE40C292C
    assert pd.fnv1a("abc") == 0x1A47E90B


def test_name_tokens_drop_generic_words():
    toks = pd.name_tokens("Sri Venkateswara Skin & Hair Clinic")
    assert "venkateswara" in toks and "sri" in toks
    assert "skin" not in toks and "clinic" not in toks and "hair" not in toks


def test_rank_bucket_edges():
    assert pd.rank_bucket(1, 34) == "top 10"
    assert pd.rank_bucket(10, 34) == "top 10"
    assert pd.rank_bucket(11, 34) == "11–20"
    assert pd.rank_bucket(21, 34) == "21–34"


def test_bands_never_exact():
    assert pd.reviews_band(212) == "200+"
    assert pd.reviews_band(180) == "100+"
    assert pd.reviews_band(61) == "50+"
    assert pd.reviews_band(35) == "under 50"
    assert pd.rating_band(4.9) == "4.5+"
    assert pd.rating_band(4.2) == "4.0+"
    assert pd.rating_band(None) is None


# ---------------------------------------------------------------- payload shape
def test_kpis_pass_through_aggregates_only():
    p = build()
    assert p["kpis"]["unique_clinics"] == 4
    assert p["kpis"]["no_website_count"] == 2
    assert p["kpis"]["queries"] == 80


def test_beeswarm_positions_bounded_and_deterministic():
    a, b = build()["beeswarm"], build()["beeswarm"]
    assert a == b                                  # deterministic (salted hash jitter)
    assert len(a) == 4
    for dot in a:
        assert 4 <= dot["x"] <= 96
        assert -30 <= dot["y"] <= 30
        assert set(dot) == {"x", "y", "inv"}       # nothing else rides along
    assert sum(1 for d in a if d["inv"]) == 2


def test_lookup_hashed_and_flagged():
    p = build()
    assert len(p["lookup"]) == 4
    for e in p["lookup"]:
        assert set(e) == {"h", "t", "inv", "bucket"}
        assert isinstance(e["h"], int) and all(isinstance(x, int) for x in e["t"])
    # the invisible clinic is findable by its distinctive token hash
    lakshmi = pd.fnv1a("lakshmi" + "test-salt")
    hits = [e for e in p["lookup"] if lakshmi in e["t"]]
    assert len(hits) == 1 and hits[0]["inv"] is True


def test_teasers_are_banded_and_lettered():
    t = build()["teasers"]
    assert len(t) == 2                              # only 2 invisible clinics in fixture
    assert [x["letter"] for x in t] == ["A", "B"]
    for x in t:
        assert set(x) == {"letter", "rating_band", "reviews_band", "demand"}
        assert x["demand"] in ("high", "steady")


def test_queries_exclude_branded():
    qs = build()["queries"]
    assert 0 < len(qs) <= 8
    joined = " ".join(qs).lower()
    assert "lakshmi" not in joined and "venkateswara" not in joined


def test_owned_borrowed_aggregates():
    ob = build()["owned_borrowed"]
    assert ob == {"owned": 1, "borrowed_only": 2, "invisible": 1}


def test_pricing_from_cfg():
    p = build()["pricing"]
    assert p["report"] == 4999 and p["monitor_yr"] == 9999
    assert p["whatsapp"] == "919999999999"


# ---------------------------------------------------------------- THE invariant
def test_no_identifying_data_survives():
    blob = json.dumps(build(), ensure_ascii=False).lower()
    for clinic in full_payload()["clinics"]:
        for tok in pd.name_tokens(clinic["name"]):
            assert tok not in blob, f"name token leaked: {tok}"
        if clinic["website"]:
            assert clinic["website"].lower() not in blob
    # exact review counts / scores must not appear as keys or JSON values anywhere
    for needle in ('"reviews"', '"score"', '"rating"', ": 212", ": 180", ": 82", ": 74"):
        assert needle not in blob, f"identifying value leaked: {needle}"
