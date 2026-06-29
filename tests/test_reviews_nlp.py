"""Pure-function tests for reviews_nlp (no live scraping, no network, no browser)."""
from modules import reviews_nlp as nlp


# ---------------------------------------------------------------- sentiment
def test_sentiment_positive():
    s = nlp.score_sentiment("Excellent doctor, amazing staff, highly recommend!")
    assert s["label"] == "positive"
    assert s["compound"] > 0.05


def test_sentiment_negative():
    s = nlp.score_sentiment("Terrible experience, rude staff and the treatment did not work.")
    assert s["label"] == "negative"
    assert s["compound"] < -0.05


def test_sentiment_neutral_empty():
    s = nlp.score_sentiment("")
    assert s["label"] == "neutral"
    assert s["compound"] == 0.0


# ---------------------------------------------------------------- themes
def test_theme_bucketing_doctor_and_wait():
    themes = nlp.detect_themes("The doctor was friendly but the waiting time was very long.")
    assert "doctor/staff behaviour" in themes
    assert "wait time" in themes


def test_theme_bucketing_cost_and_results():
    themes = nlp.detect_themes("Treatment gave great results for my acne but it was expensive.")
    assert "treatment results/effectiveness" in themes
    assert "cost/value" in themes


def test_theme_bucketing_cleanliness_and_booking():
    themes = nlp.detect_themes("Very clean and hygienic; easy to book an appointment online.")
    assert "cleanliness" in themes
    assert "booking/appointment" in themes


def test_theme_empty():
    assert nlp.detect_themes("") == []


# ---------------------------------------------------------------- referral
def test_referral_detection_recommend():
    assert nlp.has_referral_signal("I highly recommend this clinic to everyone.")


def test_referral_detection_family():
    assert nlp.has_referral_signal("My friend told me about this place, so I came here.")


def test_referral_detection_referred():
    assert nlp.has_referral_signal("I was referred here by my colleague.")


def test_referral_negative():
    assert not nlp.has_referral_signal("The clinic was clean and the doctor was on time.")


# ---------------------------------------------------------------- n-grams
def test_top_ngrams_counts():
    # note: "doctor"/"good"/"place" are domain stopwords, so use content words
    texts = ["friendly helpful staff friendly", "friendly helpful service"]
    grams = dict(nlp.top_ngrams(texts, n=2, top_k=5))
    # "friendly helpful" appears in both reviews -> count 2
    assert grams.get("friendly helpful") == 2


def test_top_ngrams_filters_stopwords_unigram():
    grams = dict(nlp.top_ngrams(["the the the wonderful wonderful"], n=1, top_k=5))
    assert "the" not in grams           # stopword removed
    assert grams.get("wonderful") == 2


# ---------------------------------------------------------------- recency
def test_relative_date_to_days_months():
    assert nlp.relative_date_to_days("2 months ago") == 60.0


def test_relative_date_to_days_a_year():
    assert nlp.relative_date_to_days("a year ago") == 365.0


def test_relative_date_to_days_unparseable():
    assert nlp.relative_date_to_days("recently") is None


def test_summarize_recency_buckets():
    reviews = [
        {"relative_date": "2 weeks ago"},
        {"relative_date": "5 months ago"},
        {"relative_date": "2 years ago"},
        {"relative_date": "unknown"},
    ]
    s = nlp.summarize_recency(reviews)
    assert s["reviews_with_date"] == 3
    assert s["last_6mo"] == 2      # 2 weeks + 5 months
    assert s["last_12mo"] == 2
    assert s["newest_days"] == 14.0


# ---------------------------------------------------------------- analyze_clinic
def _sample_reviews():
    return [
        {"author": "A", "rating": 5, "relative_date": "1 week ago", "owner_response": "Thanks!",
         "text": "Excellent doctor and very friendly staff. Highly recommend this clinic!"},
        {"author": "B", "rating": 4, "relative_date": "2 months ago", "owner_response": None,
         "text": "Good treatment results for my acne, a bit expensive though."},
        {"author": "C", "rating": 1, "relative_date": "6 months ago", "owner_response": None,
         "text": "Waited over an hour, rude staff, treatment did not work."},
        {"author": "D", "rating": 2, "relative_date": "8 months ago", "owner_response": None,
         "text": "Too costly and the appointment booking was a mess."},
    ]


def test_analyze_clinic_shape_and_contract():
    a = nlp.analyze_clinic(_sample_reviews())
    expected_keys = {
        "n_reviews", "avg_sentiment", "pos_pct", "neu_pct", "neg_pct",
        "top_positive_themes", "top_negative_themes", "referral_mention_rate",
        "recency_summary",
    }
    assert expected_keys.issubset(a.keys())
    assert a["n_reviews"] == 4
    # percentages sum to ~100
    assert abs(a["pos_pct"] + a["neu_pct"] + a["neg_pct"] - 100.0) < 0.2


def test_analyze_clinic_polarity_split():
    a = nlp.analyze_clinic(_sample_reviews())
    # 2 reviews are 4-5 star (positive), 2 are 1-2 star (negative)
    assert a["pos_pct"] == 50.0
    assert a["neg_pct"] == 50.0


def test_analyze_clinic_themes_routed_by_polarity():
    a = nlp.analyze_clinic(_sample_reviews())
    pos_themes = {t[0] for t in a["top_positive_themes"]}
    neg_themes = {t[0] for t in a["top_negative_themes"]}
    assert "doctor/staff behaviour" in pos_themes        # from the 5-star review
    assert "wait time" in neg_themes or "cost/value" in neg_themes


def test_analyze_clinic_referral_rate():
    a = nlp.analyze_clinic(_sample_reviews())
    # exactly one review says "Highly recommend" -> 1/4
    assert a["referral_mention_rate"] == 0.25


def test_analyze_clinic_empty():
    a = nlp.analyze_clinic([])
    assert a["n_reviews"] == 0
    assert a["referral_mention_rate"] == 0.0
    assert a["top_positive_themes"] == []


# ---------------------------------------------------------------- analyze_all
def test_analyze_all_skips_meta_and_keys_by_clinic():
    data = {
        "clinic_1": _sample_reviews(),
        "clinic_2": [],
        "_meta": {"collected_at": "x"},
    }
    out = nlp.analyze_all(data, write=False)
    assert set(out.keys()) == {"clinic_1", "clinic_2"}   # _meta skipped
    assert out["clinic_1"]["n_reviews"] == 4
    assert out["clinic_2"]["n_reviews"] == 0
