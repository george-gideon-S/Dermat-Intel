"""Unified scored rows -> the plain dict modules/report consumes. No network.

This adapter was deleted with the UI layer; it is recovered from git 2ff72b3:web/build_web.py
and re-tested here, because without it nothing can build the doctor-facing report at all.

It also carries the subject-type league split: a multi-specialty hospital and a solo
practitioner are not comparable units, so market averages are computed per league. Averaging a
hospital's several-thousand reviews into a solo clinic's benchmark makes every small clinic
look worse than it is, on a signal that says nothing about its dermatology.
"""
import math

import pytest

from modules import packs, report_adapter as ra

ROW = {
    "name": "Skin Perfect Clinic",
    "place_url": "https://www.google.com/maps/place/?q=place_id:ChIJabc",
    "website": "https://skinperfect.example",
    "formatted_phone_number": "+91 90000 11111",
    "rating": 4.9, "user_ratings_total": 636, "appearances": 22,
    "web_owned_appearances": 4, "web_borrowed_appearances": 9,
    "in_places_count": 7, "web_appearances": 13, "has_own_site": True,
    "types": "Skin care clinic",
}
HOSPITAL = dict(ROW, name="Ramesh Multi-speciality Hospital", user_ratings_total=5200,
                types="Hospital", place_url="https://maps.google.com/?cid=999")


# --- field mapping -------------------------------------------------------------

def test_maps_every_field_report_consumes():
    d = ra.norm_clinic(ROW)
    assert set(d) >= {"name", "key", "has_website", "owned", "borrowed", "places", "reviews",
                      "rating", "appearances", "has_phone", "web_appearances",
                      "has_own_site", "platforms"}


def test_key_is_the_shared_clinic_identity():
    """Must match maps_collector.dedup_key or the web and Maps halves join to nothing."""
    from modules.maps_collector import dedup_key
    assert ra.norm_clinic(ROW)["key"] == dedup_key(ROW["place_url"])


def test_falls_back_to_lowercased_name_when_the_url_has_no_id():
    d = ra.norm_clinic({"name": "Odd Clinic", "place_url": ""})
    assert d["key"] == "odd clinic"


def test_missing_website_and_phone_become_false_not_crash():
    d = ra.norm_clinic({"name": "X", "place_url": "", "website": None,
                        "formatted_phone_number": None})
    assert d["has_website"] is False and d["has_phone"] is False


def test_nan_numbers_become_zero():
    """pandas hands NaN through; report's arithmetic would silently produce NaN scores."""
    d = ra.norm_clinic({"name": "X", "place_url": "", "user_ratings_total": float("nan"),
                        "rating": float("nan"), "web_appearances": float("nan")})
    assert d["reviews"] == 0 and d["rating"] == 0.0 and d["web_appearances"] == 0
    assert not math.isnan(d["rating"])


def test_blank_website_string_is_not_a_website():
    assert ra.norm_clinic(dict(ROW, website="   "))["has_website"] is False


def test_counts_are_ints():
    d = ra.norm_clinic(dict(ROW, web_owned_appearances=4.0, in_places_count=7.7))
    assert isinstance(d["owned"], int) and isinstance(d["places"], int)
    assert d["places"] == 8


# --- market dict ---------------------------------------------------------------

def test_market_from_rows_provides_the_three_keys_report_needs():
    m = ra.market_from_rows([ROW, dict(ROW, name="B", user_ratings_total=100, appearances=10)])
    assert set(m) >= {"avg_reviews", "avg_rating", "median_appearances"}
    assert m["avg_reviews"] == pytest.approx((636 + 100) / 2)


def test_market_never_divides_by_zero_on_an_empty_market():
    m = ra.market_from_rows([])
    assert m["avg_reviews"] >= 1 and m["avg_rating"] == 0.0


# --- subject-type leagues ------------------------------------------------------

def test_league_split_keeps_hospitals_out_of_the_clinic_average():
    ctx = packs.load("guntur-ap", "dermatology", subject_type="both")
    rows = [ROW, dict(ROW, name="B", user_ratings_total=200), HOSPITAL]
    leagues = ra.markets_by_league(rows, ctx)
    assert "clinic" in leagues and "hospital" in leagues
    assert leagues["clinic"]["avg_reviews"] == pytest.approx((636 + 200) / 2)
    assert leagues["hospital"]["avg_reviews"] == pytest.approx(5200)


def test_a_hospital_does_not_drag_the_clinic_benchmark(sample=None):
    ctx = packs.load("guntur-ap", "dermatology", subject_type="both")
    clinics_only = ra.markets_by_league([ROW, dict(ROW, name="B", user_ratings_total=200)], ctx)
    with_hospital = ra.markets_by_league(
        [ROW, dict(ROW, name="B", user_ratings_total=200), HOSPITAL], ctx)
    assert clinics_only["clinic"]["avg_reviews"] == with_hospital["clinic"]["avg_reviews"]


def test_subject_class_is_attached_to_every_normalised_clinic():
    ctx = packs.load("guntur-ap", "dermatology")
    assert ra.norm_clinic(ROW, ctx=ctx)["subject_class"] == "clinic"
    assert ra.norm_clinic(HOSPITAL, ctx=ctx)["subject_class"] == "hospital"


def test_classification_report_exposes_how_labels_were_reached():
    """Maps category strings are often absent — the June snapshot has none at all — so a
    reader must be able to see that the leagues rest on name heuristics alone."""
    ctx = packs.load("guntur-ap", "dermatology")
    rep = ra.classification_report([dict(ROW, types=""), dict(HOSPITAL, types="Hospital")], ctx)
    assert rep["counts"]["category"] == 1      # the hospital had a category string
    assert rep["counts"]["name"] == 1          # the clinic was matched on its name
    assert rep["total"] == 2


def test_a_name_only_label_is_marked_as_such():
    ctx = packs.load("guntur-ap", "dermatology")
    d = ra.norm_clinic(dict(ROW, types=""), ctx=ctx)
    assert d["subject_class"] == "clinic"
    assert d["subject_basis"] == "name"


def test_a_bare_practitioner_name_stays_unclassified():
    """'Dr. Sneha Kovi' carries no facility signal; inventing one would fake a league."""
    ctx = packs.load("guntur-ap", "dermatology")
    d = ra.norm_clinic({"name": "Dr. Sneha Kovi", "place_url": "", "types": ""}, ctx=ctx)
    assert d["subject_class"] == "ambiguous"
    assert d["subject_basis"] == "unclassified"


def test_ambiguous_subjects_get_their_own_league_rather_than_being_hidden():
    ctx = packs.load("guntur-ap", "dermatology")
    odd = dict(ROW, name="Dr. Sneha Kovi", types="")   # real June row: no facility word
    leagues = ra.markets_by_league([odd], ctx)
    assert "ambiguous" in leagues


def test_narrowed_subject_type_filters_rows_but_keeps_ambiguous():
    ctx = packs.load("guntur-ap", "dermatology", subject_type="individual")
    rows = [ROW, HOSPITAL, dict(ROW, name="Aesthetica", types="")]
    kept = ra.filter_rows(rows, ctx)
    names = {r["name"] for r in kept}
    assert "Skin Perfect Clinic" in names
    assert "Ramesh Multi-speciality Hospital" not in names
    assert "Aesthetica" in names


# --- integration with report ---------------------------------------------------

def test_adapter_output_scores_through_report_end_to_end():
    from modules import report
    d = ra.norm_clinic(ROW)
    market = ra.market_from_rows([ROW])
    score = report.visibility_score(d, market)
    assert 0 <= score <= 100
    breakdown = report.visibility_breakdown(d, market)
    assert {b["key"] for b in breakdown} == {"website", "search", "maps", "reviews",
                                             "phone", "breadth"}


def test_scores_stay_in_range_for_a_completely_empty_clinic():
    from modules import report
    d = ra.norm_clinic({"name": "Ghost", "place_url": ""})
    assert report.visibility_score(d, ra.market_from_rows([])) == 0
