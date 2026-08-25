"""Parse a REAL Google SERP captured from live Guntur search (2026-08-18, nodriver + Chrome).

The synthetic fixtures in test_serp_parser.py prove the parser matches our *assumptions* about
Google's markup. This file proves it matches Google. When Google changes its DOM, this is the
test that fails — which is the point: the parser degrading to zero blocks must be loud.

The fixture is the #search subtree with scripts/styles/images stripped (81 KB of the original
1.5 MB). No network.
"""
from pathlib import Path

import pytest

from modules import serp_parser as sp

FIXTURE = Path(__file__).parent / "fixtures" / "serp_guntur_skin_doctor.html"
QUERY = "best skin doctor in Guntur"


@pytest.fixture(scope="module")
def html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_fixture_is_present_and_looks_like_a_serp(html):
    assert FIXTURE.exists(), "real-SERP fixture missing — re-capture with the spike script"
    assert sp.looks_readable(html)


def test_extracts_both_local_pack_and_organic_from_real_markup(html):
    blocks = sp.parse_blocks(html)
    kinds = {b["block_type"] for b in blocks}
    assert any(sp.is_local_pack(k) for k in kinds), "local pack lost — Google's local markup likely changed"
    assert "organic" in kinds, "organic results lost — anchor>h3 pattern likely changed"
    assert len(blocks) >= 8, f"suspiciously few blocks parsed: {len(blocks)}"


def test_real_local_pack_carries_names_ratings_and_review_counts(html):
    places = [b for b in sp.parse_blocks(html) if sp.is_local_pack(b["block_type"])]
    assert len(places) >= 3
    assert all(p["title"] for p in places)
    # Ratings on this market cluster at 4.8-5.0; any parse that yields None for all of them
    # means the aria-label format moved.
    assert any(p["rating"] is not None for p in places)
    assert any(p["reviews"] for p in places)
    for p in places:
        if p["reviews"] is not None:
            assert p["reviews"] > 0
        if p["rating"] is not None:
            assert 0.0 < p["rating"] <= 5.0


def test_known_guntur_clinic_appears_in_the_local_pack(html):
    """A name from the June snapshot must still be recognisable — proves we parse the
    same market the historical dataset describes, not a different city's pack."""
    titles = " | ".join(b["title"].lower() for b in sp.parse_blocks(html))
    assert "skin" in titles
    assert any(tok in titles for tok in ("akshay", "skin lane", "skin perfect"))


def test_positions_are_continuous_and_start_at_one_on_real_html(html):
    blocks = sp.parse_blocks(html)
    assert [b["position"] for b in blocks] == list(range(1, len(blocks) + 1))


def test_every_real_block_satisfies_the_nine_key_contract(html):
    nine = {"position", "block_type", "platform", "title", "domain", "url",
            "rating", "reviews", "snippet"}
    for b in sp.parse_blocks(html):
        assert set(b) == nine


def test_no_duplicate_urls_from_nested_result_containers(html):
    urls = [b["url"] for b in sp.parse_blocks(html) if b["url"]]
    assert len(urls) == len(set(urls))


def test_search_box_text_round_trips_the_query(html):
    assert sp.search_box_text(html).lower() == QUERY.lower()


def test_organic_results_are_real_http_urls_with_domains(html):
    organic = [b for b in sp.parse_blocks(html) if b["block_type"] == "organic"]
    assert organic
    for b in organic:
        assert b["url"].startswith("http")
        assert b["domain"] and "google.com" not in b["domain"]


# --- paid results, from a SERP that actually served ads -----------------------

ADS_FIXTURE = Path(__file__).parent / "fixtures" / "serp_guntur_hairfall_ads.html"


@pytest.fixture(scope="module")
def ads_html() -> str:
    return ADS_FIXTURE.read_text(encoding="utf-8")


def test_paid_results_are_detected_on_a_real_ad_serving_serp(ads_html):
    """Regression guard: `#tads` exists but ships empty, and keying on it returned zero ads.
    An ad is OWNED visibility, so losing ads silently deflates every advertiser's score."""
    ads = [b for b in sp.parse_blocks(ads_html) if b["block_type"].startswith("sponsored")]
    assert len(ads) >= 2, "paid results lost — ad markup likely moved again"
    assert {a["domain"] for a in ads} >= {"kolorshairandskin.com", "vcaretrichology.com"}


def test_ad_titles_are_advertiser_names_not_google_chrome_or_urls(ads_html):
    ads = [b for b in sp.parse_blocks(ads_html) if b["block_type"].startswith("sponsored")]
    for a in ads:
        assert "http" not in a["title"], f"display URL leaked into title: {a['title']!r}"
        assert "ad centre" not in a["title"].lower(), "picked up Google's ad-settings control"
        assert a["title"].strip()


def test_ads_and_organics_share_one_continuous_position_sequence(ads_html):
    blocks = sp.parse_blocks(ads_html)
    assert [b["position"] for b in blocks] == list(range(1, len(blocks) + 1))
    kinds = {b["block_type"] for b in blocks}
    assert "organic" in kinds and "sponsored_mid" in kinds
    assert any(sp.is_local_pack(k) for k in kinds), "the map box must still be recognised"
