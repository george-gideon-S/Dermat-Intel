"""Programmatic query generation. No network: autocomplete is always stubbed.

This replaces a manual round trip (a human pasted a prompt into an LLM and pasted the answer
back), so the guarantees the human used to provide must now be enforced in code:

* every condition asked several ways — one phrasing under-samples the market;
* no "near me" — it resolves against the scraper's location, not the market;
* every query names the city — Google ignores uule, so this is the ONLY geo control, and an
  unqualified query silently returns the wrong city's results;
* exactly the requested number of queries, ranked 1..N.
"""
import pytest

from modules import packs, query_builder as qb


@pytest.fixture
def ctx():
    return packs.load("guntur-ap", "dermatology", query_threshold=40)


@pytest.fixture
def no_autocomplete(monkeypatch):
    """Template-only generation: the offline path."""
    monkeypatch.setattr(qb, "fetch_suggestions", lambda *a, **k: [])


# --- seeds and templates -------------------------------------------------------

def test_every_condition_is_asked_several_ways_at_the_real_threshold(no_autocomplete):
    """At the measured dermatology threshold (100) full coverage must actually happen."""
    ctx = packs.load("guntur-ap", "dermatology")
    rows, report = qb.build_with_report(ctx)
    text = " || ".join(r["search_query"].lower() for r in rows)
    for cond in ctx.conditions:
        hits = sum(1 for p in cond["phrasings"] if p.lower() in text)
        assert hits >= 2, f"condition {cond['id']} asked fewer than 2 ways"
    assert report["condition_coverage"]["shortfall"] == []


def test_every_condition_gets_one_phrasing_before_any_gets_two(ctx, no_autocomplete):
    """Degrading below the floor must thin coverage evenly, never drop whole conditions."""
    rows = qb.build(ctx)          # threshold 40, below the ~42 needed for full 2x coverage
    text = " || ".join(r["search_query"].lower() for r in rows)
    for cond in ctx.conditions:
        hits = sum(1 for p in cond["phrasings"] if p.lower() in text)
        assert hits >= 1, f"condition {cond['id']} dropped entirely"


def test_a_threshold_below_the_phrasing_floor_reports_its_shortfall(ctx, no_autocomplete):
    """21 conditions+treatments cannot be asked twice inside 40 queries; say so explicitly."""
    _, report = qb.build_with_report(ctx)
    cov = report["condition_coverage"]
    assert cov["minimum_for_full_coverage"] > report["requested"]
    assert cov["shortfall"], "under-coverage was silently hidden"
    assert cov["asked_twice"] < cov["conditions"]


def test_every_query_names_the_city(ctx, no_autocomplete):
    """The uule parameter is ignored by Google; the city in the text is the only geo control."""
    for r in qb.build(ctx):
        assert "guntur" in r["search_query"].lower(), r["search_query"]


def test_no_near_me_queries_are_ever_emitted(ctx, no_autocomplete):
    for r in qb.build(ctx):
        assert "near me" not in r["search_query"].lower()
        assert "nearby" not in r["search_query"].lower()


def test_exact_threshold_is_honoured_and_ranks_are_contiguous(ctx, no_autocomplete):
    rows = qb.build(ctx)
    assert len(rows) == 40
    assert [r["rank"] for r in rows] == list(range(1, 41))


def test_rows_match_the_downstream_contract(ctx, no_autocomplete):
    for r in qb.build(ctx):
        assert set(r) == {"rank", "search_query", "category", "user_intent",
                          "search_strength_score"}
        assert 1 <= r["search_strength_score"] <= 10


def test_queries_are_unique(ctx, no_autocomplete):
    rows = qb.build(ctx)
    seen = [r["search_query"].lower() for r in rows]
    assert len(seen) == len(set(seen))


def test_category_mix_is_varied_and_never_near_me(ctx, no_autocomplete):
    cats = {r["category"] for r in qb.build(ctx)}
    # "Near Me / Local" is deliberately unreachable — it would measure the scraper's location
    assert "Near Me / Local" not in cats
    assert len(cats) >= 3, f"query set is too single-minded: {cats}"


def test_intent_text_uses_the_context_city_and_specialty(ctx, no_autocomplete):
    rows = qb.build(ctx)
    intents = " ".join(r["user_intent"] for r in rows).lower()
    assert "guntur" in intents
    assert "dermatologist" in intents


# --- autocomplete expansion ----------------------------------------------------

def test_autocomplete_suggestions_are_merged_in(ctx, monkeypatch):
    monkeypatch.setattr(qb, "fetch_suggestions",
                        lambda seed, **k: ["experienced acne doctor in guntur"]
                        if "acne" in seed else [])
    rows = qb.build(ctx)
    assert any("experienced acne doctor" in r["search_query"].lower() for r in rows)


# --- rule 3: no sub-places in a small city -------------------------------------

def test_sub_place_suggestions_are_rejected_in_a_small_city(ctx, monkeypatch):
    """A neighbourhood query measures a street, not the market — see `query writing.md`."""
    monkeypatch.setattr(qb, "fetch_suggestions",
                        lambda seed, **k: ["best acne doctor in guntur lakshmipuram",
                                           "skin specialist in guntur kothapet"])
    for r in qb.build(ctx):
        q = r["search_query"].lower()
        assert "lakshmipuram" not in q and "kothapet" not in q


def test_no_generated_query_names_a_locality(ctx, no_autocomplete):
    banned = qb.sub_places(ctx)
    assert banned, "the Guntur pack lists localities, so there is something to block"
    for r in qb.build(ctx):
        assert not (set(qb._norm(r["search_query"]).split()) & banned)


def test_a_large_market_may_opt_back_into_locality_queries(ctx):
    """The rule is about market size, not a blanket ban — metros keep the behaviour."""
    assert qb.sub_places(ctx), "Guntur blocks localities"
    ctx.geo["allow_locality_queries"] = True
    assert qb.sub_places(ctx) == set()
    assert qb.template_pools(ctx)["locality"], "and the locality pool comes back"


def test_place_type_words_are_not_treated_as_place_names(ctx):
    """'Amaravati Road' must block 'amaravati', not the word 'road'."""
    banned = qb.sub_places(ctx)
    assert "amaravati" in banned
    assert "road" not in banned and "nagar" not in banned


# --- rule 4: never name a clinic or a doctor -----------------------------------

def test_suggestions_naming_a_person_or_clinic_are_rejected(ctx, monkeypatch):
    """Whoever is named wins the query by definition, so it measures one business."""
    monkeypatch.setattr(qb, "fetch_suggestions",
                        lambda seed, **k: ["kavitha skin doctor in guntur",
                                           "krishnamurthy skin specialist in guntur"])
    for r in qb.build(ctx):
        q = r["search_query"].lower()
        assert "kavitha" not in q and "krishnamurthy" not in q


def test_unknown_tokens_identifies_the_offending_word(ctx):
    vocab = qb.allowed_vocabulary(ctx)
    assert qb.unknown_tokens("kavitha skin doctor in guntur", vocab) == ["kavitha"]
    assert qb.unknown_tokens("best skin doctor in guntur", vocab) == []


def test_legitimate_qualifiers_survive_the_vocabulary_check(ctx):
    """The allowlist must not quietly eat real patient phrasings."""
    vocab = qb.allowed_vocabulary(ctx)
    for q in ["lady skin doctor in guntur", "pediatric dermatologist in guntur",
              "best hair fall doctor in guntur", "acne cream in guntur",
              "government skin hospital in guntur", "skin doctor in guntur open now"]:
        assert qb.unknown_tokens(q, vocab) == [], q


def test_validate_refuses_a_set_that_breaks_either_new_rule(ctx):
    vocab, banned = qb.allowed_vocabulary(ctx), qb.sub_places(ctx)
    for bad in ("dermatologist in guntur kothapet", "kavitha skin doctor in guntur"):
        rows = [{"rank": 1, "search_query": bad}]
        with pytest.raises(qb.QuerySetInvalid):
            qb.validate(rows, city=ctx.city, vocab=vocab, banned_places=banned)


def test_offtopic_suggestions_are_filtered_out(ctx, monkeypatch):
    monkeypatch.setattr(qb, "fetch_suggestions",
                        lambda seed, **k: ["guntur biryani recipe", "guntur chilli price"])
    for r in qb.build(ctx):
        assert "biryani" not in r["search_query"].lower()
        assert "chilli" not in r["search_query"].lower()


def test_suggestions_without_the_city_are_rejected(ctx, monkeypatch):
    monkeypatch.setattr(qb, "fetch_suggestions",
                        lambda seed, **k: ["acne treatment in hyderabad", "acne treatment cream"])
    for r in qb.build(ctx):
        assert "hyderabad" not in r["search_query"].lower()
        assert "guntur" in r["search_query"].lower()


def test_near_me_suggestions_are_rejected_even_when_google_offers_them(ctx, monkeypatch):
    """Autocomplete really does return 'skin doctor guntur near me'."""
    monkeypatch.setattr(qb, "fetch_suggestions",
                        lambda seed, **k: ["skin doctor guntur near me"])
    for r in qb.build(ctx):
        assert "near me" not in r["search_query"].lower()


def test_autocomplete_failure_degrades_to_templates_with_a_flag(ctx, monkeypatch):
    def boom(*a, **k):
        raise qb.httpget.FetchError("no network")
    monkeypatch.setattr(qb, "fetch_suggestions", boom)
    rows, report = qb.build_with_report(ctx)
    assert len(rows) == 40
    assert report["query_source"] == "templates_only"
    assert report["autocomplete_error"]


def test_report_records_source_counts(ctx, monkeypatch):
    monkeypatch.setattr(qb, "fetch_suggestions",
                        lambda seed, **k: ["best acne treatment in guntur city"] if "acne" in seed else [])
    rows, report = qb.build_with_report(ctx)
    assert report["query_source"] == "templates+autocomplete"
    assert report["from_autocomplete"] >= 1
    assert report["from_templates"] >= 1
    assert report["requested"] == 40 and report["produced"] == len(rows)


# --- validation ----------------------------------------------------------------

def test_validator_rejects_a_near_me_query():
    with pytest.raises(qb.QuerySetInvalid) as e:
        qb.validate([{"rank": 1, "search_query": "dermatologist near me Guntur"}],
                    city="Guntur", expected=1)
    assert "near me" in str(e.value).lower()


def test_validator_rejects_a_query_missing_the_city():
    with pytest.raises(qb.QuerySetInvalid) as e:
        qb.validate([{"rank": 1, "search_query": "acne treatment"}], city="Guntur", expected=1)
    assert "city" in str(e.value).lower()


def test_validator_rejects_a_short_set():
    with pytest.raises(qb.QuerySetInvalid):
        qb.validate([{"rank": 1, "search_query": "acne treatment in Guntur"}],
                    city="Guntur", expected=5)


def test_validator_rejects_duplicate_queries():
    rows = [{"rank": 1, "search_query": "acne treatment in Guntur"},
            {"rank": 2, "search_query": "Acne Treatment in guntur"}]
    with pytest.raises(qb.QuerySetInvalid) as e:
        qb.validate(rows, city="Guntur", expected=2)
    assert "duplicate" in str(e.value).lower()


def test_validator_accepts_a_clean_set():
    rows = [{"rank": 1, "search_query": "acne treatment in Guntur"},
            {"rank": 2, "search_query": "best dermatologist in Guntur"}]
    assert qb.validate(rows, city="Guntur", expected=2) is True


# --- scale ---------------------------------------------------------------------

def test_can_produce_the_recommended_hundred_queries(no_autocomplete):
    """The measured dermatology threshold; templates alone must be able to reach it."""
    ctx = packs.load("guntur-ap", "dermatology")
    rows = qb.build(ctx)
    assert ctx.query_threshold == 100
    assert len(rows) == 100
    assert len({r["search_query"].lower() for r in rows}) == 100
