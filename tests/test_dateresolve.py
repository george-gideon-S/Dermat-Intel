"""Anchor Google's relative review dates to absolute ones. No network.

Google returns "2 months ago", which is only meaningful relative to when it was scraped. Left
as-is, a June review reads as "2 months ago" forever, so a quarterly diff would compare two
snapshots whose dates both drift — the recency signal silently rots. Resolving at capture time
against the capture date is what makes review age comparable across snapshots.

Precision is deliberately coarse (Google's own precision) and recorded as such: "2 months ago"
is not a day, and pretending otherwise would invent data.
"""
from datetime import date

import pytest

from modules import dateresolve as dr

ANCHOR = date(2026, 6, 29)  # the June snapshot's capture date


@pytest.mark.parametrize("text,expected_days", [
    ("a day ago", 1),
    ("2 days ago", 2),
    ("a week ago", 7),
    ("3 weeks ago", 21),
    ("a month ago", 30),
    ("2 months ago", 60),
    ("11 months ago", 330),
    ("a year ago", 365),
    ("2 years ago", 730),
])
def test_relative_phrases_convert_to_day_offsets(text, expected_days):
    assert dr.relative_to_days(text) == expected_days


@pytest.mark.parametrize("text", ["", None, "recently", "sometime", "just now-ish", "??"])
def test_unparseable_phrases_return_none_rather_than_guessing(text):
    assert dr.relative_to_days(text) is None


def test_resolves_to_an_absolute_iso_date_against_the_anchor():
    assert dr.resolve("2 months ago", ANCHOR) == "2026-04-30"


def test_resolution_precision_is_reported_not_implied():
    assert dr.precision_of("3 days ago") == "day"
    assert dr.precision_of("2 weeks ago") == "week"
    assert dr.precision_of("5 months ago") == "month"
    assert dr.precision_of("a year ago") == "year"


def test_resolve_review_keeps_the_raw_string_alongside_the_resolved_date():
    """The original text is evidence; never overwrite it."""
    review = {"author": "A", "rating": 5, "relative_date": "2 months ago", "text": "good"}
    out = dr.resolve_review(review, ANCHOR)
    assert out["relative_date"] == "2 months ago"
    assert out["reviewed_on"] == "2026-04-30"
    assert out["reviewed_on_precision"] == "month"
    assert out["captured_on"] == "2026-06-29"


def test_resolve_review_marks_unresolvable_dates_explicitly():
    out = dr.resolve_review({"relative_date": "recently"}, ANCHOR)
    assert out["reviewed_on"] is None
    assert out["reviewed_on_precision"] is None
    assert out["captured_on"] == "2026-06-29"


def test_resolve_review_does_not_mutate_the_input():
    review = {"relative_date": "2 days ago"}
    dr.resolve_review(review, ANCHOR)
    assert "reviewed_on" not in review


def test_resolve_all_handles_the_reviews_cache_shape_and_skips_meta():
    cache = {
        "0x1:0xA": [{"relative_date": "2 days ago"}, {"relative_date": "a year ago"}],
        "0x1:0xB": [{"relative_date": "3 months ago"}],
        "_meta": {"collected_at": "2026-06-29T13:47:00", "n_clinics": 2},
    }
    out = dr.resolve_all(cache, ANCHOR)
    assert "_meta" in out and out["_meta"]["n_clinics"] == 2
    assert out["0x1:0xA"][0]["reviewed_on"] == "2026-06-27"
    assert out["0x1:0xB"][0]["reviewed_on"] == "2026-03-31"


def test_anchor_accepts_an_iso_string_as_well_as_a_date():
    assert dr.resolve("2 days ago", "2026-06-29") == "2026-06-27"


def test_coverage_reports_how_many_dates_resolved():
    cache = {"c1": [{"relative_date": "2 days ago"}, {"relative_date": "mystery"}]}
    cov = dr.coverage(dr.resolve_all(cache, ANCHOR))
    assert cov["reviews"] == 2
    assert cov["resolved"] == 1
    assert cov["unresolved"] == 1
