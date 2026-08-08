"""km_from_core + visibility_bands + band_of."""

import math

import pytest

from modules import vulnerability
from web import views


# ─────────────────────────────────────────────── km_from_core
def test_zero_at_the_core():
    assert views.km_from_core(16.3067, 80.4365) == pytest.approx(0.0, abs=1e-9)


def test_known_offset_north():
    # 0.01 deg of latitude ~ 1.11 km at the configured 111 km/deg
    assert views.km_from_core(16.3167, 80.4365) == pytest.approx(1.11, abs=1e-6)


def test_known_offset_east():
    # 0.01 deg of longitude ~ 1.066 km at the configured 106.6 km/deg
    assert views.km_from_core(16.3067, 80.4465) == pytest.approx(1.066, abs=1e-6)


@pytest.mark.parametrize("lat,lng", [(None, 80.4), (16.3, None), (None, None),
                                     (float("nan"), 80.4), (16.3, float("nan"))])
def test_missing_coords_return_none(lat, lng):
    assert views.km_from_core(lat, lng) is None


def test_accepts_a_custom_centre():
    assert views.km_from_core(1.0, 2.0, center=(1.0, 2.0)) == pytest.approx(0.0)


def test_agrees_with_the_frozen_module_formula():
    """Pins the deliberate duplication of `vulnerability._km_from_core`.

    We re-implement rather than import a private name out of a frozen module; this
    test is what stops the two drifting. Sampled across the real Guntur bounding box.
    """
    for lat in (16.2856, 16.3067, 16.3258):
        for lng in (80.4177, 80.4365, 80.4522):
            assert views.km_from_core(lat, lng) == pytest.approx(
                vulnerability._km_from_core(lat, lng), abs=1e-9)


# ─────────────────────────────────────────────── band_of
@pytest.mark.parametrize("vis,expected", [
    (0, "alarm"), (13, "alarm"), (20, "alarm"),
    (21, "caution"), (34, "caution"), (50, "caution"),
    (51, "steady"), (66, "steady"), (79, "steady"),
    (80, "clear"), (100, "clear"),
])
def test_band_boundaries(vis, expected):
    assert views.band_of(vis) == expected


def test_band_of_none_is_alarm_not_a_crash():
    assert views.band_of(None) == "alarm"


def test_bands_tile_the_whole_range_without_gaps_or_overlap():
    covered = set()
    for lo, hi, _, _ in views.BANDS:
        rng = set(range(lo, hi + 1))
        assert not (covered & rng), "bands overlap"
        covered |= rng
    assert covered == set(range(0, 101))


# ─────────────────────────────────────────────── visibility_bands
def _clinics(values):
    return [{"visibility": v} for v in values]


def test_band_counts():
    out = views.visibility_bands(_clinics([5, 13, 34, 40, 66, 88, 100]))
    counts = {b["key"]: b["count"] for b in out["bands"]}
    assert counts == {"alarm": 2, "caution": 2, "steady": 1, "clear": 2}
    assert sum(counts.values()) == 7


def test_gaps_are_computed_from_the_data_not_hardcoded():
    out = views.visibility_bands(_clinics([10, 11, 12, 40, 41, 90]))
    # the two largest jumps are 12->40 (28) and 41->90 (49); sorted by size desc
    assert out["gaps"][0] == {"lo": 41, "hi": 90, "size": 49}
    assert out["gaps"][1] == {"lo": 12, "hi": 40, "size": 28}


def test_gap_ties_break_on_lower_bound_for_determinism():
    out = views.visibility_bands(_clinics([0, 10, 20, 30]))
    assert [g["lo"] for g in out["gaps"]] == [0, 10]


def test_consecutive_values_produce_no_gaps():
    assert views.visibility_bands(_clinics([1, 2, 3, 4]))["gaps"] == []


def test_min_max_and_sorted_values():
    out = views.visibility_bands(_clinics([50, 7, 100]))
    assert out["values"] == [7, 50, 100]
    assert (out["min"], out["max"]) == (7, 100)


def test_empty_input_returns_a_zeroed_skeleton():
    out = views.visibility_bands([])
    assert out["values"] == [] and out["gaps"] == []
    assert out["min"] == 0 and out["max"] == 0
    assert all(b["count"] == 0 for b in out["bands"])
    assert len(out["bands"]) == 4


def test_clinics_without_a_visibility_are_skipped_not_zeroed():
    out = views.visibility_bands([{"visibility": None}, {"visibility": 88}, {}])
    assert out["values"] == [88]


def test_matches_the_real_guntur_distribution():
    """The live 34-clinic shape — the two empirical splits the market view draws."""
    vis = [7, 8, 8, 8, 8, 10, 10, 12, 13, 20, 31, 34, 36, 39, 40, 40, 40, 41, 45, 47,
           49, 49, 50, 66, 67, 70, 74, 79, 84, 88, 89, 92, 97, 100]
    out = views.visibility_bands(_clinics(vis))
    assert sum(b["count"] for b in out["bands"]) == 34
    biggest = {(g["lo"], g["hi"]) for g in out["gaps"]}
    assert (50, 66) in biggest and (20, 31) in biggest
