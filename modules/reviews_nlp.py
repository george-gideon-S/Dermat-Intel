"""Step 3b — Deep, FREE, OFFLINE NLP on scraped Google Maps reviews.

No API keys, no paid services, no model downloads, no nltk data (which hits TLS
cert issues on this machine). Everything here is local:

  * Sentiment   -> vaderSentiment (rule/lexicon based, ships with its lexicon).
  * Themes      -> keyword buckets + top n-grams via collections.Counter.
  * Word-of-mouth / referral signal -> regex over recommend/referred/family/...
  * Recency / velocity -> parsed from Google's "2 months ago" relative dates.

All functions are pure (text in, dict out) so tests need no network or browser.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_ANALYZER = SentimentIntensityAnalyzer()

# VADER's standard thresholds for labelling a compound score.
POS_THRESHOLD = 0.05
NEG_THRESHOLD = -0.05


def nlp_cache_path() -> str:
    return str(Path(config.CACHE_DIR) / "reviews_nlp.json")


# --------------------------------------------------------------------------- sentiment
def score_sentiment(text: str) -> dict:
    """One review -> {compound, label} where label in {positive, neutral, negative}."""
    text = (text or "").strip()
    if not text:
        return {"compound": 0.0, "label": "neutral"}
    compound = _ANALYZER.polarity_scores(text)["compound"]
    if compound >= POS_THRESHOLD:
        label = "positive"
    elif compound <= NEG_THRESHOLD:
        label = "negative"
    else:
        label = "neutral"
    return {"compound": round(compound, 4), "label": label}


# --------------------------------------------------------------------------- themes
# Aspect buckets — each maps a theme to the keywords/phrases that signal it.
THEME_KEYWORDS: dict[str, list[str]] = {
    "doctor/staff behaviour": [
        "doctor", "dr ", "dr.", "staff", "nurse", "receptionist", "rude", "polite",
        "friendly", "caring", "behaviour", "behavior", "attentive", "patient", "kind",
        "professional", "arrogant", "humble", "listened", "attitude", "courteous",
    ],
    "wait time": [
        "wait", "waiting", "queue", "long time", "hours", "delay", "delayed", "on time",
        "appointment time", "waited", "slow", "quick", "prompt", "punctual",
    ],
    "cleanliness": [
        "clean", "hygiene", "hygienic", "neat", "tidy", "sanitiz", "sanitis", "dirty",
        "spotless", "well maintained", "sterile", "ambience", "ambiance",
    ],
    "cost/value": [
        "cost", "costly", "price", "pricey", "expensive", "cheap", "affordable", "fee",
        "fees", "charges", "charged", "money", "worth", "value", "overpriced", "budget",
        "reasonable", "rupees", "rs ", "amount",
    ],
    "treatment results/effectiveness": [
        "treatment", "result", "results", "effective", "cured", "cure", "improved",
        "improvement", "skin", "hair", "acne", "pimple", "scar", "laser", "medicine",
        "prescribed", "worked", "didn't work", "did not work", "no improvement",
        "satisfied", "recovery", "healed",
    ],
    "booking/appointment": [
        "appointment", "booking", "book", "schedule", "scheduled", "online", "call",
        "phone", "reschedule", "slot", "walk in", "walk-in", "reception desk",
    ],
}

# Words too common to be informative as n-grams (kept tiny on purpose — no nltk).
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be", "been",
    "being", "to", "of", "in", "on", "at", "for", "with", "by", "from", "as", "it",
    "this", "that", "these", "those", "i", "you", "he", "she", "we", "they", "my",
    "me", "our", "us", "your", "his", "her", "their", "them", "him", "so", "very",
    "too", "have", "has", "had", "do", "did", "does", "not", "no", "can", "will",
    "would", "should", "could", "there", "here", "all", "any", "if", "then", "than",
    "out", "up", "down", "about", "into", "over", "after", "before", "just", "also",
    "got", "get", "am", "more", "most", "such", "only", "own", "same", "s", "t",
    "who", "what", "which", "when", "where", "why", "how", "one", "two", "much",
    "really", "good", "place", "clinic", "doctor",  # generic high-freq for this domain
}

_WORD_RE = re.compile(r"[a-z][a-z'\-]+")

# Referral / word-of-mouth signal phrases.
_REFERRAL_RE = re.compile(
    r"\b(recommend(?:ed|s|ing)?|referr?(?:ed|al|s)?|word of mouth|told me|"
    r"suggested by|came (?:here )?because|my (?:friend|family|sister|brother|mother|"
    r"father|cousin|neighbou?r|colleague)|friends? and family)\b",
    re.I,
)


def detect_themes(text: str) -> list[str]:
    """Return the list of theme buckets a single review touches (substring match)."""
    if not text:
        return []
    low = text.lower()
    hits = []
    for theme, kws in THEME_KEYWORDS.items():
        if any(kw in low for kw in kws):
            hits.append(theme)
    return hits


def has_referral_signal(text: str) -> bool:
    """True if the review mentions recommending / referral / word-of-mouth / family-told."""
    if not text:
        return False
    return bool(_REFERRAL_RE.search(text))


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall((text or "").lower())
            if w not in _STOPWORDS and len(w) > 2]


def top_ngrams(texts: list[str], n: int = 2, top_k: int = 8) -> list[tuple[str, int]]:
    """Top `top_k` n-grams across `texts` via a plain Counter (no nltk)."""
    counter: Counter = Counter()
    for t in texts:
        toks = _tokens(t)
        if n == 1:
            counter.update(toks)
        else:
            for i in range(len(toks) - n + 1):
                counter.update([" ".join(toks[i:i + n])])
    return counter.most_common(top_k)


# --------------------------------------------------------------------------- recency
_REL_UNIT_DAYS = {
    "second": 1 / 86400, "minute": 1 / 1440, "hour": 1 / 24,
    "day": 1.0, "week": 7.0, "month": 30.0, "year": 365.0,
}
_REL_RE = re.compile(r"(a|an|\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", re.I)


def relative_date_to_days(rel: str):
    """Convert 'a month ago' / '3 weeks ago' to an approximate age in days. None if unparseable."""
    if not rel:
        return None
    m = _REL_RE.search(rel)
    if not m:
        return None
    qty_raw, unit = m.group(1).lower(), m.group(2).lower()
    qty = 1.0 if qty_raw in ("a", "an") else float(qty_raw)
    return qty * _REL_UNIT_DAYS.get(unit, 0.0)


def summarize_recency(reviews: list[dict]) -> dict:
    """Velocity signal from relative dates: how fresh / active the review stream is."""
    ages = [d for d in (relative_date_to_days(r.get("relative_date")) for r in reviews)
            if d is not None]
    if not ages:
        return {"reviews_with_date": 0, "newest_days": None, "median_age_days": None,
                "last_6mo": 0, "last_12mo": 0}
    ages.sort()
    mid = len(ages) // 2
    median = ages[mid] if len(ages) % 2 else (ages[mid - 1] + ages[mid]) / 2
    return {
        "reviews_with_date": len(ages),
        "newest_days": round(min(ages), 1),
        "median_age_days": round(median, 1),
        "last_6mo": sum(1 for a in ages if a <= 182),
        "last_12mo": sum(1 for a in ages if a <= 365),
    }


# --------------------------------------------------------------------------- per-clinic
def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def analyze_clinic(reviews: list[dict]) -> dict:
    """Deep NLP rollup for one clinic's reviews.

    Returns:
        {
          n_reviews, avg_sentiment, pos_pct, neu_pct, neg_pct,
          top_positive_themes, top_negative_themes,   # [[theme, count], ...]
          referral_mention_rate,                        # 0..1
          recency_summary,                              # dict (see summarize_recency)
          # extras (useful for the dashboard, additive):
          avg_star_rating, top_positive_phrases, top_negative_phrases, n_owner_responses,
        }
    """
    reviews = reviews or []
    n = len(reviews)
    if n == 0:
        return {
            "n_reviews": 0, "avg_sentiment": 0.0,
            "pos_pct": 0.0, "neu_pct": 0.0, "neg_pct": 0.0,
            "top_positive_themes": [], "top_negative_themes": [],
            "referral_mention_rate": 0.0,
            "recency_summary": summarize_recency([]),
            "avg_star_rating": None, "top_positive_phrases": [],
            "top_negative_phrases": [], "n_owner_responses": 0,
        }

    compounds = []
    pos = neu = neg = 0
    pos_theme_counter: Counter = Counter()
    neg_theme_counter: Counter = Counter()
    pos_texts, neg_texts = [], []
    referrals = 0
    stars = []
    owner_responses = 0

    for r in reviews:
        text = r.get("text") or ""
        sent = score_sentiment(text)
        compounds.append(sent["compound"])
        themes = detect_themes(text)

        # classify the review as pos/neu/neg using BOTH the star rating (authoritative
        # when present) and sentiment — themes are then credited to the right bucket.
        star = r.get("rating")
        if isinstance(star, (int, float)):
            stars.append(float(star))
            polarity = "positive" if star >= 4 else ("negative" if star <= 2 else "neutral")
        else:
            polarity = sent["label"]

        if polarity == "positive":
            pos += 1
            pos_theme_counter.update(themes)
            if text:
                pos_texts.append(text)
        elif polarity == "negative":
            neg += 1
            neg_theme_counter.update(themes)
            if text:
                neg_texts.append(text)
        else:
            neu += 1

        if has_referral_signal(text):
            referrals += 1
        if r.get("owner_response"):
            owner_responses += 1

    avg_sent = round(sum(compounds) / n, 4) if compounds else 0.0
    avg_star = round(sum(stars) / len(stars), 2) if stars else None

    return {
        "n_reviews": n,
        "avg_sentiment": avg_sent,
        "pos_pct": _pct(pos, n),
        "neu_pct": _pct(neu, n),
        "neg_pct": _pct(neg, n),
        "top_positive_themes": [list(t) for t in pos_theme_counter.most_common(6)],
        "top_negative_themes": [list(t) for t in neg_theme_counter.most_common(6)],
        "referral_mention_rate": round(referrals / n, 3),
        "recency_summary": summarize_recency(reviews),
        "avg_star_rating": avg_star,
        "top_positive_phrases": [list(t) for t in top_ngrams(pos_texts, n=2, top_k=8)],
        "top_negative_phrases": [list(t) for t in top_ngrams(neg_texts, n=2, top_k=8)],
        "n_owner_responses": owner_responses,
    }


def analyze_all(reviews_by_clinic: dict, write: bool = True) -> dict:
    """Analyze every clinic; returns {clinic_key: analyze_clinic(...)}.

    Skips the `_meta` bookkeeping key written by collect_reviews. When `write` is
    True, persists the result to .cache/reviews_nlp.json.
    """
    out: dict = {}
    for key, reviews in (reviews_by_clinic or {}).items():
        if key == "_meta":
            continue
        out[key] = analyze_clinic(reviews)
    if write:
        Path(config.CACHE_DIR).mkdir(parents=True, exist_ok=True)
        with open(nlp_cache_path(), "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
    return out
