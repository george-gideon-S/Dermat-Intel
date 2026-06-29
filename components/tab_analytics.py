"""Tab 3 — Market intelligence dashboard (14 charts)."""
from __future__ import annotations

import streamlit as st

from modules import analytics


@st.cache_data(show_spinner="Building charts…")
def _cached(query_rows, result_rows):
    """Build all figures + KPIs once per dataset (reused across reruns)."""
    return analytics.build_all(query_rows, result_rows), analytics.kpis(result_rows)


def _chart(container, fig, insight: str, key: str):
    container.plotly_chart(fig, use_container_width=True, key=key)
    container.caption(f"💡 Insight: {insight}")


def render():
    st.header("📊 Market Intelligence Dashboard")
    rows = st.session_state.get("result_rows")
    if not rows:
        st.info("No data yet — run the pipeline from the sidebar.")
        return
    qrows = st.session_state.get("query_rows") or []
    figs, k = _cached(qrows, rows)
    st.caption("Tip: hover any chart and use its 📷 toolbar icon to download a PNG.")

    st.subheader("Market Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unique clinics", k["unique_clinics"])
    c2.metric("Avg rating", k["avg_rating"])
    c3.metric("Average reviews", k["avg_reviews"])
    c4.metric("% with website", f'{k["pct_with_website"]}%')
    cL, cR = st.columns(2)
    _chart(cL, figs["donut"], "Where local search demand concentrates.", "an_donut")
    _chart(cR, figs["top_clinics"], "Clinics that dominate local visibility.", "an_top")

    st.subheader("Ratings & Reviews")
    _chart(st, figs["rating_reviews"], "Top-right = trusted leaders; lower = reputation gaps.", "an_rr")
    cL, cR = st.columns(2)
    _chart(cL, figs["ratings_hist"], "Most clinics cluster here on rating.", "an_hist")
    _chart(cR, figs["reviews_box"], "Review depth varies by search intent.", "an_box")
    st.altair_chart(figs["heatmap"], use_container_width=True, key="an_heatmap")

    st.subheader("Presence & Visibility")
    cL, cR = st.columns(2)
    _chart(cL, figs["ranked_appearances"], "Full visibility ranking.", "an_ranked")
    _chart(cR, figs["website_stacked"], "Website coverage by search intent.", "an_web")
    _chart(st, figs["treemap"], "Bigger = more reviews; red = weak rating.", "an_tree")
    _chart(st, figs["map"], "Geographic spread, coloured by rating tier.", "an_map")

    st.subheader("Competitive Gaps")
    _chart(st, figs["quadrant"], "‘Vulnerable’ = popular but poorly rated → your opportunity.", "an_quad")
    cL, cR = st.columns(2)
    _chart(cL, figs["no_website"], "High-demand clinics with no website = prime targets.", "an_noweb")
    _chart(cR, figs["funnel"], "Very few clinics have a complete online presence.", "an_funnel")
