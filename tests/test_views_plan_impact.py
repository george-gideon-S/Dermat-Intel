"""plan_impact — the projected rank delta behind the prescription stack.

This is the most persuasive number in the product ("close this and you move #28 -> #19")
and it is entirely new, so its invariants are pinned hard.
"""

import pytest

from modules import report
from web import views

MARKET = {"avg_reviews": 300.0, "avg_rating": 4.8, "median_appearances": 14.5}


def clinic(**over):
    """A clinic earning nothing: no site, no search, no pack, no reviews, no phone."""
    base = {"key": "subject", "name": "Subject", "has_website": False, "owned": 0,
            "borrowed": 0, "places": 0, "reviews": 0, "rating": 4.5, "appearances": 10,
            "has_phone": False, "web_appearances": 0, "has_own_site": False,
            "platforms": []}
    base.update(over)
    return base


def _market(n=5, **over):
    """A field of `n` mid-scoring rivals, distinct keys."""
    out = []
    for i in range(n):
        c = clinic(key=f"rival{i}", name=f"Rival {i}", has_website=True,
                   places=4, reviews=150, has_phone=True)
        c.update(over)
        out.append(c)
    return out


def test_website_step_is_worth_exactly_thirty_points():
    out = views.plan_impact(clinic(), _market(), MARKET)
    website = next(s for s in out["steps"] if s["key"] == "website")
    assert website["lift"] == 30
    assert website["vis_after"] == out["now"]["vis"] + 30


def test_rank_never_gets_worse_after_a_fix():
    out = views.plan_impact(clinic(), _market(8), MARKET)
    for step in out["steps"]:
        assert step["rank_after"] <= out["now"]["rank"], step["key"]


def test_a_fully_maxed_clinic_has_no_steps():
    maxed = clinic(has_website=True, owned=report.OWNED_FULL, places=report.PLACES_FULL,
                   reviews=int(MARKET["avg_reviews"]), has_phone=True,
                   web_appearances=report.BREADTH_FULL)
    out = views.plan_impact(maxed, _market(), MARKET)
    assert out["steps"] == []
    assert out["now"]["vis"] == 100


def test_steps_are_sorted_by_lift_descending_then_key():
    out = views.plan_impact(clinic(), _market(), MARKET)
    order = [(-s["lift"], s["key"]) for s in out["steps"]]
    assert order == sorted(order)


def test_compound_never_exceeds_one_hundred():
    out = views.plan_impact(clinic(), _market(), MARKET)
    assert out["compound"]["all"]["vis"] <= 100
    assert out["compound"]["top2"]["vis"] <= 100


def test_compound_all_is_at_least_compound_top2():
    out = views.plan_impact(clinic(), _market(), MARKET)
    assert out["compound"]["all"]["vis"] >= out["compound"]["top2"]["vis"]


def test_lift_always_equals_the_projected_delta():
    """Regression: `lift` used to come from visibility_breakdown (which rounds each
    component) while `vis_after` came from visibility_score (which rounds the sum), so
    a card could read "+7" beside a score that moved 8. The card shows both numbers
    together, so they must be the same arithmetic.

    The fixture is deliberately non-integral — places=4 of 8 and web_appearances=9 of
    10 both produce half-point residues, which is what made the old code disagree.
    """
    c = clinic(has_website=True, places=4, web_appearances=9, reviews=90, has_phone=True)
    out = views.plan_impact(c, _market(), MARKET)
    assert out["steps"], "fixture should still have headroom"
    for s in out["steps"]:
        assert s["lift"] == s["vis_after"] - out["now"]["vis"], s["key"]


def test_compound_top2_is_at_least_the_best_single_step():
    out = views.plan_impact(clinic(), _market(), MARKET)
    best = max(s["vis_after"] for s in out["steps"])
    assert out["compound"]["top2"]["vis"] >= best


def test_a_degenerate_market_average_does_not_promise_a_phantom_review_gain():
    """Regression: maxing reviews used `avg_reviews or 0` where the frozen module
    divides by `avg_reviews or 1`. With a zero market average the step advertised
    +15 points that the projection never delivered."""
    c = clinic(reviews=0)
    for market in ({"avg_reviews": 0.0}, {}):
        out = views.plan_impact(c, [c], market)
        for s in out["steps"]:
            assert s["vis_after"] > out["now"]["vis"], f"{s['key']} promised nothing"


def test_inputs_are_never_mutated():
    c = clinic()
    snapshot = dict(c)
    market = _market()
    market_snapshot = [dict(x) for x in market]
    views.plan_impact(c, market, MARKET)
    assert c == snapshot
    assert market == market_snapshot


def test_steps_below_the_noise_floor_are_dropped():
    """A component already within 2 points of its max is not worth prescribing."""
    almost = clinic(has_website=True, owned=report.OWNED_FULL, places=report.PLACES_FULL,
                    reviews=int(MARKET["avg_reviews"]), has_phone=True,
                    web_appearances=report.BREADTH_FULL - 1)  # breadth short by 0.5 pts
    out = views.plan_impact(almost, _market(), MARKET)
    assert all(s["key"] != "breadth" for s in out["steps"])


def test_rank_is_measured_against_an_unchanged_market():
    """'If only I improve' — rivals do not also get better."""
    rivals = _market(3)
    out = views.plan_impact(clinic(), rivals, MARKET)
    best = max(s["vis_after"] for s in out["steps"])
    rival_scores = [report.visibility_score(r, MARKET) for r in rivals]
    expected = sum(1 for s in rival_scores if s > best) + 1
    assert min(s["rank_after"] for s in out["steps"]) == expected


def test_subject_is_excluded_from_its_own_ranking_field():
    """The clinic must not be counted as its own rival (which would offset every rank)."""
    solo = views.plan_impact(clinic(), [clinic()], MARKET)   # same key -> excluded
    assert solo["now"]["rank"] == 1


def test_empty_market_leaves_the_clinic_ranked_first():
    out = views.plan_impact(clinic(), [], MARKET)
    assert out["now"]["rank"] == 1
    assert all(s["rank_after"] == 1 for s in out["steps"])


def test_every_step_carries_the_full_contract():
    out = views.plan_impact(clinic(), _market(), MARKET)
    assert out["steps"], "fixture should have gaps to fix"
    for s in out["steps"]:
        assert set(s) == {"key", "label", "lift", "vis_after", "rank_after"}
        assert isinstance(s["lift"], int) and s["lift"] >= 2
        assert 0 <= s["vis_after"] <= 100


def test_now_rank_reproduces_the_modules_own_ranking_under_ties():
    """Regression: ordinal ranking is ORDER-DEPENDENT when scores tie.

    `report.rank_by_visibility` ranks by sort position and `sorted()` is stable, so a
    subject appended to the list lands last within its tie group and reports a worse
    rank than its own published `visibility_rank`. plan_impact must substitute the
    subject in place. Caught in the live payload: two clinics disagreed by 1-2 places.
    """
    tied = [clinic(key=f"c{i}", name=f"C{i}", has_website=True, places=4,
                   reviews=150, has_phone=True) for i in range(5)]
    for subject in tied:
        expected = next(d["rank"] for d in report.rank_by_visibility(tied, MARKET)
                        if d["key"] == subject["key"])
        assert views.plan_impact(subject, tied, MARKET)["now"]["rank"] == expected


def test_a_subject_absent_from_the_list_is_still_ranked():
    """plan_impact is also called with a market that excludes the subject."""
    out = views.plan_impact(clinic(), _market(4), MARKET)
    assert 1 <= out["now"]["rank"] <= 5


@pytest.mark.parametrize("key,gap,expected_lift", [
    ("website", {"has_website": False}, 30),
    ("search", {"owned": 0}, 30),
    ("maps", {"places": 0}, 15),
    ("reviews", {"reviews": 0}, 15),
    ("phone", {"has_phone": False}, 5),
    ("breadth", {"web_appearances": 0}, 5),
])
def test_every_recipe_produces_its_step(key, gap, expected_lift):
    """Mutation guard: five of the six `maxed` recipes could be DELETED outright
    and the suite stayed green, because only `website` was pinned by a test that
    asserted its step exists. Each recipe now has to earn its component's points.
    """
    maxed_out = dict(has_website=True, owned=report.OWNED_FULL, places=report.PLACES_FULL,
                     reviews=int(MARKET["avg_reviews"]), has_phone=True,
                     web_appearances=report.BREADTH_FULL)
    c = clinic(**{**maxed_out, **gap})
    out = views.plan_impact(c, _market(), MARKET)
    step = next((s for s in out["steps"] if s["key"] == key), None)
    assert step is not None, f"{key} recipe produced no step"
    assert step["lift"] == expected_lift
    assert step["vis_after"] == out["now"]["vis"] + expected_lift


@pytest.mark.parametrize("market", [{"avg_reviews": 0.0}, {}, {"avg_reviews": None}])
def test_the_reviews_recipe_mirrors_the_frozen_divisor(market):
    """Kills the `market.get("avg_reviews") or 1` -> `or 0` mutation.

    report._components divides by `avg_reviews or 1`, so in a degenerate market a
    single review maxes the component and the fix IS worth its 15 points. With
    `or 0` the recipe sets reviews to max(existing, 0) — it changes nothing, the
    lift computes to 0, and the step silently vanishes from the plan. Asserting
    the step is ABSENT would pass either way; the invariant that separates them is
    that the recipe must actually earn the component.
    """
    c = clinic(reviews=0)
    out = views.plan_impact(c, [c], market)
    step = next((s for s in out["steps"] if s["key"] == "reviews"), None)
    assert step is not None, "the reviews fix is worth 15 points and must be offered"
    assert step["lift"] == 15
    assert step["vis_after"] == out["now"]["vis"] + 15


def test_rank_after_a_fix_respects_the_subject_s_position_among_ties():
    """Mutation guard for the append-vs-substitute bug.

    The existing regression test only checked `now.rank`, which the mutation does
    not disturb: appending leaves the original subject in the list, and
    rank_by_visibility returns the first key match. Only a variant whose score
    CHANGED separates the two — appended, the higher-scoring variant sorts to the
    front and reports rank 1; substituted in place, the subject lands at its own
    position within the new tie.

    Four rivals with a website; the subject without one, sitting at index 3. After
    the +30 fix all five tie, and a stable sort must leave the subject 4th.
    """
    rivals = [clinic(key=f"c{i}", name=f"C{i}", has_website=True, places=4,
                     reviews=150, has_phone=True) for i in range(5)]
    subject = clinic(key="subject", has_website=False, places=4,
                     reviews=150, has_phone=True)
    market = rivals[:3] + [subject] + rivals[3:]     # subject is 4th of five

    out = views.plan_impact(subject, market, market_dict := MARKET)
    assert market_dict is MARKET
    website = next(s for s in out["steps"] if s["key"] == "website")
    assert website["rank_after"] == 4, (
        "after the fix every clinic ties, so a stable sort must keep the subject "
        f"4th; got {website['rank_after']} (variant was appended, not substituted)")
    assert website["rank_after"] < out["now"]["rank"]


def test_step_keys_are_a_subset_of_the_frozen_breakdown_keys():
    """If modules/report.py ever adds a component, this catches the missing recipe."""
    out = views.plan_impact(clinic(), _market(), MARKET)
    known = {c["key"] for c in report.visibility_breakdown(clinic(), MARKET)}
    assert {s["key"] for s in out["steps"]} <= known
