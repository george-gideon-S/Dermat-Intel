"""Pure-logic tests for modules.web_screens — the screenshot-derived google-search dataset.

No vision, no network: synthetic web_screens fixtures exercise query reconciliation, clinic mapping,
and the owned-vs-borrowed per-clinic aggregation that feeds the 40% web term.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl

from modules import web_screens as ws


# --------------------------------------------------------------------------- query normalization / match
def test_norm_lowercases_and_strips_punctuation():
    assert ws._norm("  Best Dermatologist, in Guntur!  ") == "best dermatologist in guntur"


def test_match_query_exact():
    qrows = [{"rank": 1, "search_query": "best dermatologist in Guntur"},
             {"rank": 7, "search_query": "acne treatment in Guntur"}]
    m = ws.match_query("best dermatologist in Guntur", qrows)
    assert m["rank"] == 1 and m["match_confidence"] == "exact"


def test_match_query_fuzzy_tolerates_minor_ocr_noise():
    qrows = [{"rank": 7, "search_query": "acne treatment in Guntur"}]
    m = ws.match_query("acne treatment in guntur ", qrows)   # casing/space only
    assert m["rank"] == 7 and m["match_confidence"] in ("exact", "fuzzy")


def test_match_query_unmatched_returns_none_rank():
    qrows = [{"rank": 1, "search_query": "best dermatologist in Guntur"}]
    m = ws.match_query("a totally different phrase", qrows)
    assert m["rank"] is None and m["match_confidence"] == "unmatched"


# --------------------------------------------------------------------------- reconcile (78 vs 80)
def test_reconcile_maps_by_search_box_and_reports_missing():
    parts = [
        {"queries": [{"index": 0, "search_box_text": "best dermatologist in Guntur",
                      "readable": True, "blocks": []}]},
        {"queries": [{"index": 1, "search_box_text": "skin specialist in Guntur",
                      "readable": True, "blocks": []}]},
    ]
    manifest = {"num_screenshots": 2, "num_queries_expected": 3,
                "screenshots": [{"index": 0, "screenshot": "a.png"},
                                {"index": 1, "screenshot": "b.png"}]}
    qrows = [{"rank": 1, "search_query": "best dermatologist in Guntur"},
             {"rank": 2, "search_query": "skin specialist in Guntur"},
             {"rank": 3, "search_query": "acne treatment in Guntur"}]
    out = ws.reconcile(parts, manifest, qrows)
    assert len(out["queries"]) == 2
    assert out["queries"][0]["rank"] == 1 and out["queries"][0]["screenshot"] == "a.png"
    # the query with no screenshot is reported, not silently dropped
    assert out["meta"]["unmatched_queries"] == ["acne treatment in Guntur"]
    assert out["meta"]["num_screenshots"] == 2 and out["meta"]["num_queries_expected"] == 3


# --------------------------------------------------------------------------- clinic mapping
def _clinics():
    return [
        {"name": "Dr Sowmya Skin Hair Laser Clinic", "website": "https://drsowmyaskinclinics.com/",
         "place_url": "https://www.google.com/maps/place/?cid=1"},
        {"name": "Chandana Skin Clinic | Dermatologist", "website": "",
         "place_url": "https://www.google.com/maps/place/?cid=2"},
        {"name": "Skin Perfect Clinic", "website": "",
         "place_url": "https://www.google.com/maps/place/?cid=3"},
    ]


def test_block_maps_to_clinic_by_domain_and_name():
    prepared = ws.prepare_clinics(_clinics())
    # own-domain organic -> Sowmya
    b1 = {"title": "Dr Sowmya Skin,Hair,Laser Clinic | Guntur", "domain": "drsowmyaskinclinics.com",
          "url": "", "block_type": "organic", "platform": "clinic_site"}
    assert ws.map_block(b1, prepared)[0] == "1"
    # generic aggregator page -> maps to nobody
    b2 = {"title": "Best Dermatologists in Guntur", "domain": "practo.com", "url": "",
          "block_type": "organic", "platform": "practo"}
    assert ws.map_block(b2, prepared)[0] is None


# --------------------------------------------------------------------------- owned vs borrowed (the core)
def _web_screens():
    return {"queries": [
        {"rank": 1, "search_query": "best dermatologist in Guntur", "readable": True, "blocks": [
            {"position": 1, "block_type": "places", "platform": "clinic_site",
             "title": "Skin Perfect Clinic", "domain": "", "rating": 4.9, "reviews": 611},
            {"position": 4, "block_type": "organic", "platform": "practo",
             "title": "Best Dermatologists in Guntur - Practo", "domain": "practo.com"},
            {"position": 5, "block_type": "organic", "platform": "clinic_site",
             "title": "Dr Sowmya Skin,Hair,Laser Clinic | Guntur", "domain": "drsowmyaskinclinics.com"},
            {"position": 7, "block_type": "organic", "platform": "justdial",
             "title": "Chandana Skin Clinic - Justdial", "domain": "justdial.com"},
        ]},
        {"rank": 2, "search_query": "skin specialist in Guntur", "readable": True, "blocks": [
            {"position": 1, "block_type": "sponsored_top", "platform": "clinic_site",
             "title": "Chandana Skin Clinic - Book Now", "domain": "chandanaskinclinic.com"},
            {"position": 6, "block_type": "organic", "platform": "practo",
             "title": "Dr Sowmya on Practo", "domain": "practo.com"},
        ]},
    ]}


def test_aggregate_owned_borrowed_places_semantics():
    agg = ws.aggregate_web_by_clinic(_web_screens(), _clinics())
    sowmya, chandana, perfect = agg["1"], agg["2"], agg["3"]

    # Sowmya: own-site organic in q1 (OWNED), named on Practo in q2 (BORROWED)
    assert sowmya["web_owned_appearances"] == 1
    assert sowmya["web_borrowed_appearances"] == 1
    assert sowmya["web_appearances"] == 2
    assert sowmya["has_own_site"] is True          # ranks organically on its own domain
    assert sowmya["web_best_position"] == 5

    # Chandana: justdial in q1 (BORROWED), paid ad in q2 (OWNED via ad, but NOT own-site organic)
    assert chandana["web_owned_appearances"] == 1
    assert chandana["web_borrowed_appearances"] == 1
    assert chandana["sponsored_count"] == 1
    assert chandana["has_own_site"] is False        # only an ad, never an organic own-site rank

    # Skin Perfect: appears ONLY in the Places pack -> NOT owned, NOT borrowed (Maps re-surfaced)
    assert perfect["web_appearances"] == 1
    assert perfect["in_places_count"] == 1
    assert perfect["web_owned_appearances"] == 0
    assert perfect["web_borrowed_appearances"] == 0

    # every clinic flagged with web_data so the score's web term activates
    assert all(v["web_data"] is True for v in agg.values())


def test_aggregate_marks_clinic_with_no_web_presence():
    screens = {"queries": [{"rank": 1, "search_query": "x", "readable": True, "blocks": [
        {"position": 1, "block_type": "organic", "platform": "practo",
         "title": "Best Dermatologists in Guntur", "domain": "practo.com"}]}]}
    agg = ws.aggregate_web_by_clinic(screens, _clinics())
    # generic practo page maps to nobody -> all three clinics have zero presence (a real signal)
    assert all(v["web_appearances"] == 0 for v in agg.values())
    assert all(v["web_data"] is True for v in agg.values())


# --------------------------------------------------------------------------- export
def test_to_rows_and_save_xlsx(tmp_path):
    rows = ws.to_rows(_web_screens(), _clinics())
    assert rows and {"query", "block_type", "platform", "title", "mapped_clinic",
                     "is_own_site", "position"} <= set(rows[0])
    out = ws.save_search_xlsx(rows, str(tmp_path / "g.xlsx"))
    wsheet = openpyxl.load_workbook(out).active
    assert wsheet.max_row == len(rows) + 1     # header + data
    assert wsheet["A1"].value is not None
