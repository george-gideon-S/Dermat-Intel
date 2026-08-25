"""Diffing two snapshots — the actual product value: is a clinic gaining or losing ground?

No network. The pure diff works on clinic lists; the run loader is smoke-tested against the
real June snapshot (diffing it with itself must be all-zeros).

The one subtle rule: scores from two runs are only comparable if they were computed with the
same scoring version and denominators. A rescaled OWNED_FULL makes a 62 in June and a 62 today
mean different things, so the diff marks score deltas non_comparable while still reporting the
RAW signal deltas (reviews gained, website appeared), which are always comparable.
"""
from pathlib import Path

import pytest

from modules import snapshot_diff as sd

A = [
    {"key": "k1", "name": "Alpha Skin", "rating": 4.5, "reviews": 100, "has_website": False,
     "maps_position": 5.0, "owned": 2, "visibility_score": 40, "vulnerability_score": 70},
    {"key": "k2", "name": "Beta Derma", "rating": 4.8, "reviews": 200, "has_website": True,
     "maps_position": 2.0, "owned": 6, "visibility_score": 80, "vulnerability_score": 30},
]
B = [
    # k1 improved: gained reviews, got a website, ranks higher
    {"key": "k1", "name": "Alpha Skin", "rating": 4.6, "reviews": 150, "has_website": True,
     "maps_position": 3.0, "owned": 4, "visibility_score": 65, "vulnerability_score": 45},
    # k2 gone, k3 new
    {"key": "k3", "name": "Gamma Clinic", "rating": 5.0, "reviews": 12, "has_website": False,
     "maps_position": 8.0, "owned": 0, "visibility_score": 20, "vulnerability_score": 85},
]


def test_new_and_lost_clinics_are_identified():
    d = sd.diff_clinics(A, B)
    assert {c["key"] for c in d["new"]} == {"k3"}
    assert {c["key"] for c in d["lost"]} == {"k2"}


def test_changed_clinic_reports_field_deltas():
    d = sd.diff_clinics(A, B)
    k1 = next(c for c in d["changed"] if c["key"] == "k1")
    assert k1["deltas"]["reviews"] == 50           # 100 -> 150
    assert k1["deltas"]["visibility_score"] == 25  # 40 -> 65
    assert k1["website_gained"] is True


def test_website_loss_is_flagged_too():
    a = [{"key": "k", "name": "X", "has_website": True, "reviews": 10}]
    b = [{"key": "k", "name": "X", "has_website": False, "reviews": 10}]
    d = sd.diff_clinics(a, b)
    c = d["changed"][0]
    assert c["website_lost"] is True and c["website_gained"] is False


def test_unchanged_clinic_is_not_listed_as_changed():
    same = [{"key": "k", "name": "X", "reviews": 10, "rating": 4.5, "has_website": True,
             "visibility_score": 50}]
    d = sd.diff_clinics(same, [dict(same[0])])
    assert d["changed"] == []


def test_rank_movement_direction():
    d = sd.diff_clinics(A, B)
    k1 = next(c for c in d["changed"] if c["key"] == "k1")
    # maps_position 5 -> 3 is an improvement (lower is better); delta stored as raw change
    assert k1["deltas"]["maps_position"] == -2.0


def test_comparable_when_versions_match():
    d = sd.diff_clinics(A, B, comparable=True)
    assert d["scores_comparable"] is True
    k1 = next(c for c in d["changed"] if c["key"] == "k1")
    assert "visibility_score" in k1["deltas"]


def test_non_comparable_scores_keep_raw_deltas_but_flag_scores():
    d = sd.diff_clinics(A, B, comparable=False)
    assert d["scores_comparable"] is False
    k1 = next(c for c in d["changed"] if c["key"] == "k1")
    # raw signal deltas survive...
    assert k1["deltas"]["reviews"] == 50
    # ...but score deltas are quarantined
    assert "visibility_score" not in k1["deltas"]
    assert k1["score_deltas_uncomparable"]["visibility_score"] == 25


def test_market_summary_counts():
    d = sd.diff_clinics(A, B)
    assert d["summary"]["new"] == 1
    assert d["summary"]["lost"] == 1
    assert d["summary"]["changed"] == 1
    assert d["summary"]["clinics_a"] == 2 and d["summary"]["clinics_b"] == 2


# --- version guard from manifests ---------------------------------------------

def test_versions_comparable_helper():
    ma = {"scoring": {"scoring_version": "params-1", "OWNED_FULL": 6}}
    mb = {"scoring": {"scoring_version": "params-1", "OWNED_FULL": 6}}
    assert sd.scores_comparable(ma, mb) is True


def test_versions_incomparable_when_owned_full_differs():
    ma = {"scoring": {"scoring_version": "params-1", "OWNED_FULL": 6}}
    mb = {"scoring": {"scoring_version": "params-1", "OWNED_FULL": 12}}
    assert sd.scores_comparable(ma, mb) is False


def test_versions_incomparable_when_version_differs():
    ma = {"scoring": {"scoring_version": "june-legacy", "OWNED_FULL": 6}}
    mb = {"scoring": {"scoring_version": "params-1", "OWNED_FULL": 6}}
    assert sd.scores_comparable(ma, mb) is False


# --- run loader (real June snapshot) ------------------------------------------

JUNE = Path("runs/guntur-ap_dermatology_both_2026-06-28")


@pytest.mark.skipif(not JUNE.exists(), reason="June snapshot not present")
def test_loading_clinics_from_the_real_june_run():
    clinics = sd.load_clinics(str(JUNE))
    assert len(clinics) == 34
    # Values, not just keys: an earlier loader returned 34 rows of Nones because it read the
    # xlsx display headers. A real name and a non-empty join key are what the diff needs.
    assert all(c["name"] for c in clinics), "clinic names did not load"
    assert all(c["key"] for c in clinics), "join keys are empty — diff would drop every clinic"
    assert len({c["key"] for c in clinics}) == 34, "keys are not unique"


@pytest.mark.skipif(not JUNE.exists(), reason="June snapshot not present")
def test_diffing_the_june_run_with_itself_is_all_zeros():
    d = sd.diff_runs(str(JUNE), str(JUNE))
    assert d["summary"]["new"] == 0
    assert d["summary"]["lost"] == 0
    assert d["summary"]["changed"] == 0
