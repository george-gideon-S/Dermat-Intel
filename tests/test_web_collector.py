"""Pure-function tests for modules.web_collector — NO live scraping / no browser / no network.

Covers: domain parsing, Google-redirect unwrapping, result normalization, clinic-result matching,
and the per-clinic web-visibility metric calculation, all on synthetic data.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root for config/modules

from modules import web_collector as wc


# --------------------------------------------------------------------------- domain_of
def test_domain_strips_scheme_and_www():
    assert wc.domain_of("https://www.ChandanaSkinClinic.com/page") == "chandanaskinclinic.com"


def test_domain_handles_bare_and_protocol_relative():
    assert wc.domain_of("drrameshskin.in/about") == "drrameshskin.in"
    assert wc.domain_of("//sub.example.co.in/x") == "sub.example.co.in"


def test_domain_keeps_subdomain():
    assert wc.domain_of("https://drraginipuvvala.getmy.clinic/?utm=x") == "drraginipuvvala.getmy.clinic"


def test_domain_empty_inputs():
    assert wc.domain_of("") == ""
    assert wc.domain_of(None) == ""


def test_domain_garbage_never_matches_real_domain():
    # unparseable junk must not coincide with a real registrable domain
    d = wc.domain_of("not a url at all")
    assert d == "" or " " in d or "." not in d


# --------------------------------------------------------------------------- redirect unwrap
def test_unwrap_google_redirect_relative():
    href = "/url?q=https://drsnehakovi.com/&sa=U&ved=abc"
    assert wc._unwrap_google_redirect(href) == "https://drsnehakovi.com/"


def test_unwrap_google_redirect_absolute():
    href = "https://www.google.com/url?q=https%3A%2F%2Fexample.com%2Fa&sa=U"
    assert wc._unwrap_google_redirect(href) == "https://example.com/a"


def test_unwrap_passthrough_for_plain_url():
    assert wc._unwrap_google_redirect("https://practo.com/x") == "https://practo.com/x"


# --------------------------------------------------------------------------- normalization
def test_normalize_dedupes_and_renumbers():
    raw = [
        {"url": "https://practo.com/a", "title": "A"},
        {"url": "https://practo.com/a#frag", "title": "A dup"},  # same after #-strip
        {"url": "https://justdial.com/b", "title": "B"},
    ]
    out = wc._normalize_results(raw, max_results=10)
    assert [r["url"] for r in out] == ["https://practo.com/a", "https://justdial.com/b"]
    assert [r["position"] for r in out] == [1, 2]
    assert out[0]["domain"] == "practo.com"


def test_normalize_drops_google_internal_and_nonhttp():
    raw = [
        {"url": "https://support.google.com/websearch", "title": "help"},
        {"url": "/maps/place/x", "title": "rel"},
        {"url": "https://realclinic.com", "title": "Real"},
    ]
    out = wc._normalize_results(raw, max_results=10)
    assert len(out) == 1
    assert out[0]["domain"] == "realclinic.com"


def test_normalize_respects_max_results():
    raw = [{"url": f"https://site{i}.com", "title": str(i)} for i in range(10)]
    out = wc._normalize_results(raw, max_results=3)
    assert len(out) == 3
    assert out[-1]["position"] == 3


# --------------------------------------------------------------------------- name tokens
def test_name_tokens_drop_specialty_stopwords():
    toks = wc._name_tokens("Chandana Skin Clinic | Dermatologist | Laser hair reduction")
    assert "chandana" in toks
    # generic specialty/location words are removed so they don't match every result
    assert "skin" not in toks and "clinic" not in toks and "dermatologist" not in toks


def test_name_tokens_keyword_stuffed_name():
    toks = wc._name_tokens(
        "Dr Ragini's Skin & Hair Clinic / Best dermatologist (skin doctor) in Guntur")
    assert "ragini" in toks
    assert "guntur" not in toks  # location stopword


# --------------------------------------------------------------------------- matching
def test_match_by_domain():
    res = {"title": "Some unrelated title", "url": "https://chandanaskinclinic.com/contact",
           "domain": "chandanaskinclinic.com", "position": 2}
    assert wc._result_matches_clinic(res, set(), "chandanaskinclinic.com") is True


def test_match_by_domain_subdomain():
    res = {"title": "x", "url": "https://www.drraginipuvvala.getmy.clinic/",
           "domain": "drraginipuvvala.getmy.clinic", "position": 1}
    assert wc._result_matches_clinic(res, set(), "drraginipuvvala.getmy.clinic") is True


def test_match_by_name_token_in_title():
    res = {"title": "Chandana Skin Clinic - Best in Guntur", "url": "https://practo.com/chandana",
           "domain": "practo.com", "position": 4}
    # distinctive token 'chandana' present -> match even though domain differs
    assert wc._result_matches_clinic(res, {"chandana"}, "") is True


def test_no_match_when_unrelated():
    res = {"title": "Unrelated Pharmacy Guntur", "url": "https://practo.com/other",
           "domain": "practo.com", "position": 6}
    assert wc._result_matches_clinic(res, {"chandana", "ragini"}, "chandanaskinclinic.com") is False


def test_multitoken_name_needs_two_hits():
    # name with several distinctive tokens needs >=2 to match (avoids spurious single-word hits)
    tokens = {"sowmya", "kothapeta", "chandramouli"}
    one_hit = {"title": "Dr Sowmya is great", "url": "https://x.com", "domain": "x.com", "position": 1}
    two_hit = {"title": "Dr Sowmya clinic kothapeta", "url": "https://x.com", "domain": "x.com", "position": 1}
    assert wc._result_matches_clinic(one_hit, tokens, "") is False
    assert wc._result_matches_clinic(two_hit, tokens, "") is True


# --------------------------------------------------------------------------- metrics
def _clinics():
    return [
        {"name": "Chandana Skin Clinic | Dermatologist", "website": "https://chandanaskinclinic.com/",
         "place_url": "https://www.google.com/maps/place/?cid=111"},
        {"name": "Dr Ragini's Skin & Hair Clinic", "website": "https://drraginipuvvala.getmy.clinic/",
         "place_url": "https://www.google.com/maps/place/?cid=222"},
        {"name": "Invisible Clinic No Web Presence", "website": "",
         "place_url": "https://www.google.com/maps/place/?cid=333"},
    ]


def test_match_clinics_web_counts_and_best_position():
    web = {
        "q1": [
            {"title": "Chandana Skin Clinic Guntur", "url": "https://chandanaskinclinic.com/",
             "domain": "chandanaskinclinic.com", "position": 1},
            {"title": "Practo dermatologists", "url": "https://practo.com/guntur",
             "domain": "practo.com", "position": 2},
        ],
        "q2": [
            {"title": "Top skin clinics", "url": "https://chandanaskinclinic.com/services",
             "domain": "chandanaskinclinic.com", "position": 5},
            {"title": "Dr Ragini's Skin & Hair Clinic", "url": "https://drraginipuvvala.getmy.clinic/",
             "domain": "drraginipuvvala.getmy.clinic", "position": 3},
        ],
    }
    out = wc.match_clinics_web(web, _clinics())
    chandana = out["111"]
    ragini = out["222"]
    invisible = out["333"]

    assert chandana["web_appearances"] == 2          # appears in q1 and q2
    assert chandana["web_best_position"] == 1         # best (lowest) position
    assert ragini["web_appearances"] == 1
    assert ragini["web_best_position"] == 3
    assert invisible["web_appearances"] == 0
    assert invisible["web_best_position"] is None
    # every clinic is flagged as having web data computed
    assert all(v["web_data"] is True for v in out.values())


def test_match_clinics_web_one_appearance_per_query():
    # two results match the same clinic within one query -> counts as a single appearance
    web = {
        "q1": [
            {"title": "Chandana Skin Clinic", "url": "https://chandanaskinclinic.com/a",
             "domain": "chandanaskinclinic.com", "position": 2},
            {"title": "Chandana Skin Clinic reviews", "url": "https://practo.com/chandana",
             "domain": "practo.com", "position": 7},
        ],
    }
    out = wc.match_clinics_web(web, _clinics())
    assert out["111"]["web_appearances"] == 1
    assert out["111"]["web_best_position"] == 2  # the better of the two matched positions


def test_match_clinics_web_handles_empty_serps():
    web = {"q1": [], "q2": None}
    out = wc.match_clinics_web(web, _clinics())
    assert out["111"]["web_appearances"] == 0
    assert out["111"]["web_best_position"] is None
    assert out["111"]["web_data"] is True


def test_match_clinics_web_key_falls_back_to_name():
    clinics = [{"name": "Solo Clinic", "website": "", "place_url": ""}]
    web = {"q": [{"title": "Solo Clinic Guntur", "url": "https://x.com", "domain": "x.com", "position": 1}]}
    out = wc.match_clinics_web(web, clinics)
    assert "solo clinic" in out
    assert out["solo clinic"]["web_appearances"] == 1


# --------------------------------------------------------------------------- mock collect
def test_collect_web_mock_is_deterministic_and_keyed():
    rows = [{"search_query": "best dermatologist in Guntur"},
            {"search_query": "skin specialist in Guntur"}]
    a = wc.collect_web(rows, mock=True)
    b = wc.collect_web(rows, mock=True)
    assert set(a.keys()) == {"best dermatologist in Guntur", "skin specialist in Guntur"}
    assert a == b  # deterministic
    first = a["best dermatologist in Guntur"]
    assert first and all({"title", "url", "domain", "position"} <= set(r) for r in first)
    assert [r["position"] for r in first] == list(range(1, len(first) + 1))


def test_search_google_empty_query_returns_empty():
    assert wc.search_google("") == []
    assert wc.search_google("   ") == []
