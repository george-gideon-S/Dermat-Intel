"""Third-party roundups ("best dermatologists in Guntur") -> per-clinic mention signal.

No network: SERP blocks come from a fixture, and the page fetcher is injected.

The point of this stage is the clinics a Maps-only view can't see: a roundup that recommends a
practitioner who never appeared in the scrape is real market intelligence, so unmatched names
are surfaced rather than dropped. Per the plan, listicle mentions are context in v1 and do NOT
enter scoring, which keeps snapshot #2 comparable with a June snapshot that has no such signal.
"""
import pytest

from modules import listicles, packs


@pytest.fixture
def ctx():
    return packs.load("guntur-ap", "dermatology")


SCREENS = {
    "queries": [
        {"search_query": "best dermatologist in Guntur", "blocks": [
            {"block_type": "organic", "platform": "practo",
             "title": "10 Best Dermatologists in Guntur - Practo",
             "domain": "practo.com", "url": "https://practo.com/guntur/dermatologist"},
            {"block_type": "organic", "platform": "clinic_site",
             "title": "Dr Sowmya Skin Clinic", "domain": "drsowmya.example",
             "url": "https://drsowmya.example"},
            {"block_type": "organic", "platform": "other",
             "title": "Top 7 Skin Doctors in Guntur (2026) - HealthBlog",
             "domain": "healthblog.example",
             "url": "https://healthblog.example/best-skin-doctors-guntur"},
        ]},
    ]
}


# --- candidate selection -------------------------------------------------------

def test_identifies_roundup_urls_from_serp_blocks(ctx):
    cands = listicles.find_candidates(SCREENS, ctx)
    urls = {c["url"] for c in cands}
    assert "https://practo.com/guntur/dermatologist" in urls
    assert "https://healthblog.example/best-skin-doctors-guntur" in urls


def test_a_clinics_own_site_is_not_a_listicle(ctx):
    cands = listicles.find_candidates(SCREENS, ctx)
    assert all(c["platform"] != "clinic_site" for c in cands)
    assert "https://drsowmya.example" not in {c["url"] for c in cands}


def test_roundup_titles_are_recognised_by_pattern(ctx):
    assert listicles.is_roundup("10 Best Dermatologists in Guntur")
    assert listicles.is_roundup("Top 7 Skin Doctors in Guntur (2026)")
    assert not listicles.is_roundup("Dr Sowmya Skin Clinic - Home")


# --- extraction ----------------------------------------------------------------

PAGE = """
<html><body>
<h1>10 Best Dermatologists in Guntur</h1>
<ol>
  <li><h3>Dr. Sowmya Skin Clinic</h3> great for acne</li>
  <li><h3>VCare Hair &amp; Skin Clinic</h3></li>
  <li><h3>Rejuve Skin &amp; Laser Centre</h3></li>
</ol>
</body></html>
"""


def test_extracts_practitioner_names_from_a_page():
    names = listicles.extract_names(PAGE)
    assert "Dr. Sowmya Skin Clinic" in names
    assert "VCare Hair & Skin Clinic" in names
    assert "Rejuve Skin & Laser Centre" in names


def test_matches_names_against_the_run_clinics_and_surfaces_the_rest(ctx):
    clinics = [{"key": "k1", "name": "Dr Sowmya Skin Clinic"},
               {"key": "k2", "name": "VCare Hair & Skin Clinic"}]
    fetch = lambda url: PAGE
    result = listicles.collect(SCREENS, clinics, ctx, fetch=fetch)
    # matched clinics get a mention attached
    assert result["mentions"].get("k1")
    assert result["mentions"].get("k2")
    # Rejuve is recommended by others but absent from the scrape -> surfaced, not lost
    unmatched = {u["name"] for u in result["unmatched"]}
    assert any("Rejuve" in n for n in unmatched)


def test_mention_records_its_source(ctx):
    clinics = [{"key": "k1", "name": "Dr Sowmya Skin Clinic"}]
    result = listicles.collect(SCREENS, clinics, ctx, fetch=lambda url: PAGE)
    m = result["mentions"]["k1"][0]
    assert m["source_domain"] and m["source_url"]


# --- resilience ----------------------------------------------------------------

def test_a_failing_fetch_does_not_sink_the_stage(ctx):
    def boom(url):
        raise RuntimeError("timeout")
    clinics = [{"key": "k1", "name": "Dr Sowmya Skin Clinic"}]
    result = listicles.collect(SCREENS, clinics, ctx, fetch=boom)
    assert result["mentions"] == {} or all(v == [] for v in result["mentions"].values())
    assert result["errors"]


def test_no_candidates_is_a_clean_empty_result(ctx):
    result = listicles.collect({"queries": []}, [], ctx, fetch=lambda url: "")
    assert result["n_mentions"] == 0 and result["n_unmatched"] == 0


def test_listicles_are_not_fed_into_scoring(ctx):
    """Guard the v1 decision: the signal is context, comparable-snapshot-safe, not a score input."""
    import inspect
    from modules import vulnerability, report
    for mod in (vulnerability, report):
        src = inspect.getsource(mod)
        assert "listicle" not in src.lower()
