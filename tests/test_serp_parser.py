"""SERP DOM parsing -> the web_screens.json block contract.

No network: every fixture is inline HTML mirroring markup captured from live Guntur SERPs
on 2026-08-18 (nodriver + real Chrome).

The contract these tests defend is consumed unchanged by web_screens/unify_results/report:
a block carries EXACTLY 9 keys, block_type comes from a closed set, and `position` is one
continuous top-to-bottom sequence across ALL block types (not per-type ranking).
"""
import pytest

from modules import serp_parser as sp
from modules.web_screens import VALID_BLOCK_TYPES

NINE_KEYS = {"position", "block_type", "platform", "title", "domain", "url",
             "rating", "reviews", "snippet"}


# --- fixtures mirroring real captured markup ---------------------------------

ORGANIC_HTML = """
<div id="search"><div id="rso">
  <div class="MjjYud"><div class="tF2Cxc">
    <div class="yuRUbf"><a href="https://www.practo.com/guntur/treatment/acne">
      <h3 class="LC20lb MBeuO DKV0Md">Best Acne Treatment in Guntur - Practo</h3></a></div>
    <div class="VwiC3b"><span>Book an appointment with top dermatologists in Guntur.</span></div>
  </div></div>
  <div class="MjjYud"><div class="tF2Cxc">
    <div class="yuRUbf"><a href="https://drsowmyaskinclinics.com/">
      <h3 class="LC20lb MBeuO DKV0Md">Dr Sowmya Skin Clinic | Guntur</h3></a></div>
    <div class="VwiC3b"><span>Skin, hair and laser clinic in Guntur.</span></div>
  </div></div>
</div></div>
"""

LOCAL_PACK_HTML = """
<div id="search">
 <div aria-level="2" role="heading" aria-label="Places: Location results for best skin doctor in Guntur">
   <div class="YzSd aTI8gc">Places</div></div>
 <div class="uMdZh tIxNaf rllt__borderless"><div class="VkpGBb"><div class="mTwRT">
   <div id="pv-/g/11mxnsl1p1" role="button"><div class="cXedhc"><div class="vwVdIc vyFC0c"><div>
     <div jsname="MZArnb" class="rllt__details">
       <div class="dbg0pd" aria-level="3" role="heading"><span class="OSrXXb">Skin Lane Clinic</span></div>
       <div><span><span class="Y0A0hc" aria-label="Rated 4.9 out of 5, 348 user reviews" role="img">
         <span class="yi40Hd YrbPuc" aria-hidden="true">4.9</span>
         <span class="RDApEe YrbPuc" aria-hidden="true">(348)</span></span></span> · Dermatologist</div>
       <div>SKIN LANE CLINIC, Menakshi Hospital, Pattabhipuram Rd</div>
     </div></div></div></div></div></div></div></div>
 <div class="uMdZh tIxNaf rllt__borderless"><div class="VkpGBb"><div class="mTwRT">
   <div id="pv-/g/11xyz" role="button"><div class="cXedhc"><div class="vwVdIc vyFC0c"><div>
     <div jsname="MZArnb" class="rllt__details">
       <div class="dbg0pd" aria-level="3" role="heading"><span class="OSrXXb">Chandana Skin Clinic</span></div>
       <div><span><span class="Y0A0hc" aria-label="Rated 4.8 out of 5, 1,204 user reviews" role="img">
         <span class="yi40Hd YrbPuc">4.8</span><span class="RDApEe YrbPuc">(1,204)</span></span></span> · Skin care clinic</div>
       <div>Brodipet, Guntur</div>
     </div></div></div></div></div></div></div></div>
</div>
"""

ADS_HTML = """
<div id="tvcap"><div id="tads">
  <div class="uEierd">
    <div><span class="U3A9Ac">Sponsored</span></div>
    <a class="sVXRqc" href="https://www.kayaclinic.com/guntur"><div><span>Kaya Clinic Guntur - Book Today</span></div></a>
    <div class="MUxGbd">Expert dermatologists. Same-day appointments.</div>
  </div>
</div></div>
<div id="search"><div id="rso">
  <div class="MjjYud"><div class="tF2Cxc"><div class="yuRUbf">
    <a href="https://example-clinic.com/"><h3 class="LC20lb">Example Clinic</h3></a></div></div></div>
</div></div>
<div id="bottomads">
  <div class="uEierd">
    <div><span class="U3A9Ac">Sponsored</span></div>
    <a class="sVXRqc" href="https://www.oliva.clinic/"><div><span>Oliva Skin Clinic</span></div></a>
  </div>
</div>
"""

AI_OVERVIEW_HTML = """
<div id="search">
  <div data-attrid="AIOverview"><div role="heading" aria-level="2">AI Overview</div>
    <div class="LT6XE">Hair fall can be treated with minoxidil, PRP therapy and dietary changes.</div>
    <a href="https://www.mayoclinic.org/hair-loss">Mayo Clinic</a>
  </div>
  <div id="rso"><div class="MjjYud"><div class="tF2Cxc"><div class="yuRUbf">
    <a href="https://www.healthline.com/hair"><h3 class="LC20lb">Hair loss causes</h3></a></div></div></div></div>
</div>
"""


# --- block contract ----------------------------------------------------------

def test_every_block_has_exactly_the_nine_contract_keys():
    entry = sp.parse_serp(ORGANIC_HTML)
    assert entry["blocks"], "parser produced no blocks"
    for b in entry["blocks"]:
        assert set(b.keys()) == NINE_KEYS, f"key drift: {set(b.keys()) ^ NINE_KEYS}"


def test_block_types_are_from_the_closed_set():
    for html in (ORGANIC_HTML, LOCAL_PACK_HTML, ADS_HTML, AI_OVERVIEW_HTML):
        for b in sp.parse_serp(html)["blocks"]:
            assert b["block_type"] in VALID_BLOCK_TYPES


# --- organic -----------------------------------------------------------------

def test_organic_extracts_title_url_domain_snippet():
    blocks = sp.parse_serp(ORGANIC_HTML)["blocks"]
    assert [b["block_type"] for b in blocks] == ["organic", "organic"]
    first = blocks[0]
    assert first["title"] == "Best Acne Treatment in Guntur - Practo"
    assert first["url"] == "https://www.practo.com/guntur/treatment/acne"
    assert first["domain"] == "practo.com"
    assert "top dermatologists" in first["snippet"]


def test_organic_platform_classifies_aggregator_and_clinic_site():
    blocks = sp.parse_serp(ORGANIC_HTML)["blocks"]
    assert blocks[0]["platform"] == "practo"          # known aggregator
    assert blocks[1]["platform"] == "clinic_site"     # unknown domain -> own property


# --- local pack --------------------------------------------------------------

def test_places_blocks_parse_name_rating_and_reviews():
    blocks = sp.parse_serp(LOCAL_PACK_HTML)["blocks"]
    places = [b for b in blocks if sp.is_local_pack(b["block_type"])]
    assert len(places) == 2
    assert places[0]["title"] == "Skin Lane Clinic"
    assert places[0]["rating"] == 4.9
    assert places[0]["reviews"] == 348
    assert "Pattabhipuram" in places[0]["snippet"]


def test_places_review_count_handles_thousands_separator():
    """'(1,204)' must not parse as 1."""
    places = [b for b in sp.parse_serp(LOCAL_PACK_HTML)["blocks"] if sp.is_local_pack(b["block_type"])]
    assert places[1]["reviews"] == 1204
    assert places[1]["rating"] == 4.8


# --- ads ---------------------------------------------------------------------

def test_ads_split_into_zones_by_where_they_sit():
    """ADS_HTML models Google's real layout: one ad above the results, one below all of them."""
    blocks = sp.parse_serp(ADS_HTML)["blocks"]
    kinds = [b["block_type"] for b in blocks]
    assert "sponsored_top" in kinds
    assert "sponsored_bottom" in kinds, "an ad below every result is bottom, not mid"
    top = next(b for b in blocks if b["block_type"] == "sponsored_top")
    assert top["domain"] == "kayaclinic.com"


def test_an_ad_between_results_is_mid_not_bottom():
    """The three zones must be distinguishable: bottom is the cheapest real estate there is."""
    organic = ("<div class='MjjYud'><div class='yuRUbf'><a href='https://a.in'>"
               "<h3>First</h3></a></div></div>")
    ad = ("<div data-text-ad='1'><a href='https://ad.example/x'>"
          "<span>An advertiser</span></a></div>")
    organic2 = ("<div class='MjjYud'><div class='yuRUbf'><a href='https://b.in'>"
                "<h3>Second</h3></a></div></div>")
    kinds = [b["block_type"] for b in
             sp.parse_blocks(f"<html><body><div id='search'>{organic}{ad}{organic2}</div>"
                             f"</body></html>")]
    assert kinds == ["organic", "sponsored_mid", "organic"]


def test_empty_ad_container_yields_no_sponsored_blocks():
    """Google ships #tads with empty rows before ads inject; that is not an ad."""
    html = '<div id="tads"><div class="GUyUUb"><div></div></div></div><div id="rso"></div>'
    assert [b for b in sp.parse_serp(html)["blocks"] if "sponsored" in b["block_type"]] == []


# --- AI overview -------------------------------------------------------------

def test_ai_overview_is_captured_as_one_block():
    blocks = sp.parse_serp(AI_OVERVIEW_HTML)["blocks"]
    ai = [b for b in blocks if sp.is_ai_block(b["block_type"])]
    assert len(ai) == 1
    assert "minoxidil" in ai[0]["snippet"]


# --- position continuity (the contract's subtlest rule) ----------------------

def test_position_is_continuous_across_mixed_block_types():
    html = ADS_HTML + LOCAL_PACK_HTML
    blocks = sp.parse_serp(html)["blocks"]
    positions = [b["position"] for b in blocks]
    assert positions == list(range(1, len(blocks) + 1)), positions


def test_position_follows_document_order_not_type_grouping():
    """sponsored_top precedes organic precedes bottomads in the DOM, so it must in positions."""
    blocks = sp.parse_serp(ADS_HTML)["blocks"]
    kinds = [b["block_type"] for b in blocks]
    assert kinds.index("sponsored_top") < kinds.index("organic") < kinds.index("sponsored_bottom")


def test_nested_elements_do_not_double_count():
    blocks = sp.parse_serp(ORGANIC_HTML)["blocks"]
    urls = [b["url"] for b in blocks]
    assert len(urls) == len(set(urls)), f"duplicate blocks emitted: {urls}"


# --- query entry shape --------------------------------------------------------

def test_query_entry_carries_the_web_screens_per_query_fields():
    qrow = {"rank": 7, "search_query": "acne treatment Guntur"}
    entry = sp.parse_serp(ORGANIC_HTML, query_row=qrow, screenshot_name="q007.png")
    for field in ("index", "screenshot", "rank", "search_query", "search_box_text",
                  "match_confidence", "readable", "blocks"):
        assert field in entry
    assert entry["rank"] == 7
    assert entry["search_query"] == "acne treatment Guntur"
    assert entry["screenshot"] == "q007.png"
    assert entry["match_confidence"] == "exact"


def test_zero_result_page_is_readable_but_empty_not_an_error():
    entry = sp.parse_serp("<div id='search'><div id='rso'></div></div>")
    assert entry["blocks"] == []
    assert entry["readable"] is True


def test_garbage_html_marked_unreadable():
    entry = sp.parse_serp("")
    assert entry["readable"] is False
    assert entry["blocks"] == []


# --- domain handling ----------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://www.practo.com/guntur", "practo.com"),
    ("http://drlogy.com/x?y=1", "drlogy.com"),
])
def test_domain_reuses_the_proven_web_collector_helper(url, expected):
    """Same normalisation as the rest of the pipeline — clinics must key identically."""
    assert sp.domain_of(url) == expected


def test_platform_resolves_host_prefixes_even_though_domain_keeps_them():
    """domain_of keeps 'm.', so platform matching is substring-based, not equality."""
    assert sp.domain_of("https://m.facebook.com/clinic") == "m.facebook.com"
    assert sp.classify_platform("m.facebook.com") == "facebook"
    assert sp.classify_platform("www.practo.com") == "practo"


@pytest.mark.parametrize("domain", [
    "mayoclinic.org", "healthline.com", "wikipedia.org", "nih.gov",
    "amazon.in", "nykaa.com", "reddit.com",
])
def test_national_authorities_and_retail_are_not_clinic_sites(domain):
    """These rank for symptom queries everywhere; crediting them as a local clinic's own
    property would inflate `owned`, which is worth 30 of the 100 visibility points."""
    assert sp.classify_platform(domain) == "other"


def test_an_ordinary_unknown_domain_is_still_treated_as_a_clinic_site():
    assert sp.classify_platform("drsowmyaskinclinics.com") == "clinic_site"


def test_ai_overview_snippet_drops_its_own_heading_text():
    ai = [b for b in sp.parse_serp(AI_OVERVIEW_HTML)["blocks"]
          if sp.is_ai_block(b["block_type"])][0]
    assert not ai["snippet"].lower().startswith("ai overview")


def test_block_type_distribution_reports_shares_for_the_drift_gate():
    entries = [sp.parse_serp(ORGANIC_HTML), sp.parse_serp(LOCAL_PACK_HTML)]
    dist = sp.block_type_distribution(entries)
    assert dist["counts"]["organic"] == 2
    assert dist["counts"]["local_pack_top"] == 2
    assert abs(sum(dist["share"].values()) - 1.0) < 1e-6
