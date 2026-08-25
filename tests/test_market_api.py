"""GET /market/{geography}/{specialty}/clinics — the survey read surface.

The gmaps summary (data.json) deliberately drops coordinates; the endpoint joins it with
feed.json (and falls back to places/<key>.json) so callers get mappable rows. The
laws under test: coordinates arrive, counts are honest, degradation is loud (warnings /
404s with named paths), and a missing run can never read as an empty market.
"""
import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api import app as app_module


def _mkrun(root, name, *, feed=True, manifest=True):
    run = root / name
    (run / "places").mkdir(parents=True)
    rows = [
        {"key": "K1", "name_clean": "Aura Skin Clinic", "phone": "094909 03999",
         "rating": 4.9, "reviews_total": 639, "address": "Old Club Rd, Kothapeta, Guntur",
         "relevance": "relevant", "tier": "full", "has_own_website": False},
        {"key": "K2", "name_clean": "General Hospital", "phone": "0863 111111",
         "rating": 4.1, "reviews_total": 120, "address": "Brodipet, Guntur",
         "relevance": "adjacent", "tier": "full", "has_own_website": True},
        # minimal tier: no phone key at all (not_collected), coords only in places/
        {"key": "K3", "name_clean": "Some Dental", "rating": 4.8, "reviews_total": 28,
         "address": "Seelam Vari St", "relevance": "irrelevant", "tier": "minimal",
         "has_own_website": False},
    ]
    (run / "data.json").write_text(json.dumps(rows), encoding="utf-8")
    if feed:
        cards = [{"key": "K1", "lat": 16.2991916, "lng": 80.4517515},
                 {"key": "K2", "lat": 16.3100, "lng": 80.4400}]
        (run / "feed.json").write_text(json.dumps({"cards": cards}), encoding="utf-8")
    (run / "places" / "K3.json").write_text(
        json.dumps({"key": "K3", "lat": 16.2882369, "lng": 80.4488292}), encoding="utf-8")
    if manifest:
        (run / "manifest.json").write_text(json.dumps(
            {"geography": "guntur-ap", "specialty": "dermatology", "city": "Guntur",
             "finished_at": "2026-08-21T00:35:01", "status": "complete",
             "run_health": "partial"}), encoding="utf-8")
    return run


@pytest.fixture
def client(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "GMAPS_RUNS_DIR", str(tmp_path / "gmaps"), raising=False)
    (tmp_path / "gmaps").mkdir()
    return TestClient(app_module.app)


def test_join_produces_coordinates_and_honest_counts(client, tmp_path):
    _mkrun(tmp_path / "gmaps", "guntur-ap_dermatology_2026-08-20")
    r = client.get("/market/guntur-ap/dermatology/clinics")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "guntur-ap_dermatology_2026-08-20"
    assert body["counts"] == {"captured": 3, "relevant": 1, "adjacent": 1, "irrelevant": 1}
    by_key = {c["key"]: c for c in body["clinics"]}
    assert by_key["K1"]["lat"] == 16.2991916 and by_key["K1"]["lng"] == 80.4517515
    assert by_key["K1"]["phone"] == "094909 03999"
    assert by_key["K3"]["phone"] == ""  # minimal tier: absent, never None/KeyError


def test_places_fallback_covers_keys_missing_from_feed(client, tmp_path):
    _mkrun(tmp_path / "gmaps", "guntur-ap_dermatology_2026-08-20")
    r = client.get("/market/guntur-ap/dermatology/clinics")
    k3 = next(c for c in r.json()["clinics"] if c["key"] == "K3")
    assert k3["lat"] == 16.2882369 and not k3["coords_missing"]


def test_missing_feed_is_a_named_warning_not_a_silent_gap(client, tmp_path):
    run = _mkrun(tmp_path / "gmaps", "guntur-ap_dermatology_2026-08-20")
    (run / "feed.json").unlink()
    r = client.get("/market/guntur-ap/dermatology/clinics")
    assert r.status_code == 200
    body = r.json()
    assert any("feed.json" in w for w in body["warnings"])
    # K3 still mappable via places/; K1/K2 have no places file -> flagged, not dropped
    by_key = {c["key"]: c for c in body["clinics"]}
    assert by_key["K3"]["lat"] == 16.2882369
    assert by_key["K1"]["coords_missing"] is True
    assert len(body["clinics"]) == 3


def test_partial_run_health_is_surfaced(client, tmp_path):
    _mkrun(tmp_path / "gmaps", "guntur-ap_dermatology_2026-08-20")
    r = client.get("/market/guntur-ap/dermatology/clinics")
    assert any("run health" in w for w in r.json()["warnings"])


def test_missing_run_is_404_with_the_searched_path(client, tmp_path):
    r = client.get("/market/guntur-ap/dermatology/clinics")
    assert r.status_code == 404
    assert "gmaps" in r.json()["detail"]


def test_latest_run_wins_and_aborted_dirs_are_ignored(client, tmp_path):
    root = tmp_path / "gmaps"
    _mkrun(root, "guntur-ap_dermatology_2026-07-01")
    _mkrun(root, "guntur-ap_dermatology_2026-08-20")
    (root / "_aborted_best-query_2026-09-99").mkdir()
    r = client.get("/market/guntur-ap/dermatology/clinics")
    assert r.json()["run_id"] == "guntur-ap_dermatology_2026-08-20"


def test_pinned_run_param(client, tmp_path):
    root = tmp_path / "gmaps"
    _mkrun(root, "guntur-ap_dermatology_2026-07-01")
    _mkrun(root, "guntur-ap_dermatology_2026-08-20")
    r = client.get("/market/guntur-ap/dermatology/clinics",
                   params={"run": "guntur-ap_dermatology_2026-07-01"})
    assert r.json()["run_id"] == "guntur-ap_dermatology_2026-07-01"
    assert client.get("/market/guntur-ap/dermatology/clinics",
                      params={"run": "nope"}).status_code == 404
