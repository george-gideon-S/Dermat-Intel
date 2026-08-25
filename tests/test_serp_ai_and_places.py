"""AI overview scoping/honesty and the expanded local list.

Pinned here because each of these was a live defect found by measurement, not by review:

* the overview container was resolved to an ancestor 40x too wide (4,839 chars against an
  overview of 117), which was then truncated to 600 — so the field held unrelated page text
  AND the oversized element swallowed 11 real organic/ad results on one run alone;
* Google's "can't generate an AI overview right now" was being counted as an AI overview,
  across all 22 captures in two runs;
* "More places" was never opened, so every query reported exactly 3 clinics when Google
  ranks 20.
"""
import pathlib

import pytest

from modules import serp_parser as sp

FIXTURE = pathlib.Path("runs/guntur-ap_dermatology_both_2026-08-19/serp/html/q008.html")

pytestmark = pytest.mark.skipif(not FIXTURE.exists(),
                                reason="needs a captured SERP with an AI overview")


@pytest.fixture(scope="module")
def html():
    return FIXTURE.read_text(encoding="utf-8", errors="replace")


# --------------------------------------------------------------- scoping
def test_the_whole_overview_is_captured_not_just_its_notice_bar(html):
    """The answer sits BELOW a failed-translation notice inside the same container.

    Scoping to the notice (~132 chars) threw away a 4,600-character answer that named four
    clinics and quoted a fee range, while reporting the query as "Google declined".
    """
    detail = sp.ai_overview_detail(html)
    assert detail is not None and detail["present"]
    assert detail["available"] is True
    assert detail["text_length"] > 1000, (
        f"only {detail['text_length']} chars — scoped to the notice bar again")


def test_the_oversized_container_no_longer_hides_real_results(html):
    """The mis-scoped element was consumed whole, so results inside it were never emitted."""
    kinds = [b["block_type"] for b in sp.parse_blocks(html)]
    assert kinds.count("organic") >= 5, "organic results must not vanish into the overview"
    assert any(k.startswith("ai_overview") for k in kinds)


def test_an_ai_overview_block_is_emitted_exactly_once(html):
    kinds = [b["block_type"] for b in sp.parse_blocks(html)]
    assert len([k for k in kinds if k.startswith("ai_overview")]) == 1


# --------------------------------------------------------------- availability honesty
def test_the_notice_bar_alone_does_not_mark_a_real_overview_as_declined(html):
    """This page carries BOTH the apology and a real answer; the answer wins."""
    kinds = {b["block_type"] for b in sp.parse_blocks(html)}
    assert any(k in ("ai_overview_top", "ai_overview_mid") for k in kinds)
    assert "ai_overview_unavailable" not in kinds


def test_a_page_with_only_the_notice_bar_is_recorded_as_declined():
    page = ("<html><body><div id='search'><div><div role='heading'>AI Overview</div>"
            "An AI Overview is not available for this search. "
            "Can't generate an AI overview right now. Try again later."
            "</div></div></body></html>")
    d = sp.ai_overview_detail(page)
    assert d is not None and d["available"] is False
    assert {b["block_type"] for b in sp.parse_blocks(page)} == {"ai_overview_unavailable"}


def test_an_overview_is_labelled_top_or_mid_by_where_it_sits():
    """It opens some SERPs and sits among the results on others; those are different signals."""
    head = ("<div><div role='heading'>AI Overview</div><p>Guntur clinics that treat this "
            "condition include Skin Perfect Clinic and Chandana Skin Clinic today.</p></div>")
    organic = ("<div class='MjjYud'><div class='yuRUbf'><a href='https://x.in'>"
               "<h3>A result</h3></a></div></div>")
    top = sp.parse_blocks(f"<html><body><div id='search'>{head}{organic}</div></body></html>")
    mid = sp.parse_blocks(f"<html><body><div id='search'>{organic}{head}</div></body></html>")
    assert [b["block_type"] for b in top][0] == "ai_overview_top"
    assert [b["block_type"] for b in mid if sp.is_ai_block(b["block_type"])] == ["ai_overview_mid"]


@pytest.mark.parametrize("text,unavailable", [
    ("An AI Overview is not available for this search", True),
    ("Can't generate an AI overview right now. Try again later.", True),
    ("Error translating content. Please try again later.", True),
    # The notice bar sitting ABOVE a real answer must not condemn the answer.
    ("Can't generate an AI overview right now. Try again later. For eczema treatment in "
     "Guntur you can visit Dr Ragini's Skin & Hair Clinic or Skin Perfect Clinic.", False),
    ("Dermatologists in Guntur commonly treat eczema with topical steroids and emollients.",
     False),
])
def test_availability_is_decided_on_what_remains_after_the_notice_bar(text, unavailable):
    assert sp.ai_is_unavailable(text) is unavailable


def test_a_declined_overview_reports_no_clinics_or_sources():
    page = ("<html><body><div id='search'><div><div role='heading'>AI Overview</div>"
            "Can't generate an AI overview right now. Try again later."
            "</div></div></body></html>")
    d = sp.ai_overview_detail(page)
    assert d["recommended_clinics"] == [] and d["sources"] == []


def test_real_clinics_are_recovered_from_a_live_capture(html):
    """The four the eczema overview actually names, in the order it names them."""
    names = [c["name"] for c in sp.ai_overview_detail(html)["recommended_clinics"]]
    assert names, "the overview names clinics; none were extracted"
    assert any("Skin Perfect" in n for n in names)
    for junk in ("Atopic dermatitis", "My Ad Centre", "Local Skin Clinics"):
        assert not any(junk.lower() in n.lower() for n in names), f"{junk!r} is not a clinic"


def test_listicle_titles_and_prose_are_not_counted_as_clinics():
    for junk in ("21+ Best Doctors for Eczema Treatment in Guntur",
                 "Best Doctors For Eczema Treatment In Guntur",
                 "specific skin or hair concern", "Multi-Specialty Hospitals",
                 "Independent Skin Clinics"):
        page = (f"<html><body><div id='search'><div><div role='heading'>AI Overview</div>"
                f"<p>Guntur has many options for treatment of the skin and hair today.</p>"
                f"<ul><li><b>{junk}</b></li><li><b>Skin Perfect Clinic</b></li></ul>"
                f"</div></div></body></html>")
        names = [c["name"] for c in sp.ai_overview_detail(page)["recommended_clinics"]]
        assert "Skin Perfect Clinic" in names
        assert junk not in names, f"{junk!r} was counted as a clinic"


def test_a_page_with_no_overview_returns_none():
    assert sp.ai_overview_detail("<html><body><div id='search'></div></body></html>") is None



# --------------------------------------------------------------- page furniture
def test_the_location_chooser_is_not_read_as_the_start_of_the_answer():
    """Query 8 opened with "Guntur, Andhra Pradesh ∙ Choose area" — the chooser, not the AI."""
    page = ("<html><body><div id='search'><div>"
            "Guntur, Andhra Pradesh \u2219 Choose area"
            "<div role='heading'>AI Overview</div>"
            "<p>For eczema treatment in Guntur, consult Skin Perfect Clinic or "
            "Chandana Skin Clinic for topical therapy.</p></div></div></body></html>")
    text = sp.ai_overview_detail(page)["text"]
    assert not text.lower().startswith("guntur, andhra pradesh")
    assert "Choose area" not in text
    assert text.startswith("For eczema treatment")


def test_people_also_ask_above_the_answer_is_not_read_as_the_answer():
    """Query 3 opened with "People also ask Who are some famous skin specialists…"."""
    page = ("<html><body><div id='search'><div>"
            "People also ask Who are some famous skin specialists in Guntur?"
            "<div role='heading'>AI Overview</div>"
            "<p>Guntur has several highly regarded dermatologists treating acne and "
            "hair loss at clinics across the city.</p></div></div></body></html>")
    text = sp.ai_overview_detail(page)["text"]
    assert not text.lower().startswith("people also ask")
    assert text.startswith("Guntur has several")


def test_everything_after_googles_footer_is_dropped():
    """"AI responses may include mistakes" ends the answer — 25 of 25 live captures carry it."""
    page = ("<html><body><div id='search'><div><div role='heading'>AI Overview</div>"
            "<p>Guntur clinics treating this condition include Skin Perfect Clinic and "
            "Chandana Skin Clinic for ongoing care.</p>"
            "<span>AI responses may include mistakes. Learn more</span>"
            "<span>Which doctor is the best for skin? An error has occurred.</span>"
            "</div></div></body></html>")
    text = sp.ai_overview_detail(page)["text"]
    assert "Skin Perfect Clinic" in text
    assert "AI responses may include mistakes" not in text
    assert "An error has occurred" not in text
    assert "Which doctor is the best" not in text

# --------------------------------------------------------------- recommended clinics
AI_HTML = """<html><body><div id="search"><div>
 <div role="heading">AI Overview</div>
 <p>Here are some highly rated options in Guntur.</p>
 <ol>
   <li><b>Skin Perfect Clinic</b> — known for acne care</li>
   <li><b>Dr Ragini's Skin &amp; Hair Clinic</b> — laser treatments</li>
   <li><b>Kesavam Dermacare</b> — general dermatology</li>
 </ol>
 <a href="https://www.practo.com/guntur/x">Practo listing</a>
</div></div></body></html>"""


def test_clinics_are_extracted_in_the_order_the_ai_names_them():
    d = sp.ai_overview_detail(AI_HTML)
    assert d["available"] is True
    names = [c["name"] for c in d["recommended_clinics"]]
    assert names[:3] == ["Skin Perfect Clinic", "Dr Ragini's Skin & Hair Clinic",
                         "Kesavam Dermacare"]
    assert [c["position"] for c in d["recommended_clinics"]][:3] == [1, 2, 3]


def test_prose_lines_are_not_mistaken_for_clinic_names():
    names = [c["name"] for c in sp.ai_overview_detail(AI_HTML)["recommended_clinics"]]
    assert not any(n.lower().startswith("here are") for n in names)


def test_a_clinic_named_twice_keeps_its_earliest_position():
    doubled = AI_HTML.replace("</ol>", "</ol><p><b>Skin Perfect Clinic</b> is popular.</p>")
    recs = sp.ai_overview_detail(doubled)["recommended_clinics"]
    assert [c["name"] for c in recs].count("Skin Perfect Clinic") == 1
    assert next(c for c in recs if c["name"] == "Skin Perfect Clinic")["position"] == 1


def test_sources_cited_by_the_overview_are_captured_with_their_platform():
    srcs = sp.ai_overview_detail(AI_HTML)["sources"]
    assert srcs and srcs[0]["domain"].endswith("practo.com")
    assert srcs[0]["platform"] == "practo"


def test_full_text_is_kept_far_past_the_old_600_character_cap(html):
    """A real capture runs to thousands of characters; 600 cut every one of them off."""
    d = sp.ai_overview_detail(html)
    assert d["text_length"] > 3000, "the overview must not be truncated at 600 again"
    assert d["truncated"] is False


# --------------------------------------------------------------- expanded local list
LOCAL_HTML = """<html><body><div id="search">
 <div class="uMdZh"><div class="rllt__details"><div class="dbg0pd"><span class="OSrXXb">Skin Perfect Clinic</span></div>
   <div><span aria-label="Rated 4.9 out of 5, 636 user reviews"></span>Dermatologist</div></div></div>
 <div class="uMdZh"><div class="rllt__details"><div class="dbg0pd"><span class="OSrXXb">Kesavam Dermacare</span></div>
   <div>Skin clinic</div></div></div>
 <div class="uMdZh"><div class="rllt__details"><div class="dbg0pd"><span class="OSrXXb">Skin Perfect Clinic</span></div>
   <div>Dermatologist</div></div></div>
</div></body></html>"""


def test_more_places_names_come_back_in_rank_order():
    names = sp.local_listing_names(LOCAL_HTML)
    assert [n["name"] for n in names] == ["Skin Perfect Clinic", "Kesavam Dermacare"]
    assert [n["position"] for n in names] == [1, 2]


def test_more_places_deduplicates_without_renumbering_gaps():
    positions = [n["position"] for n in sp.local_listing_names(LOCAL_HTML)]
    assert positions == list(range(1, len(positions) + 1))


def test_more_places_keeps_rating_and_review_count():
    first = sp.local_listing_names(LOCAL_HTML)[0]
    assert first["rating"] == 4.9 and first["reviews"] == 636


def test_an_empty_local_listing_is_an_empty_list_not_an_error():
    assert sp.local_listing_names("<html><body></body></html>") == []
    assert sp.local_listing_names("") == []
