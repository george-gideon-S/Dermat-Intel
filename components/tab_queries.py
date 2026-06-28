"""Tab 1 — Query setup (paste workflow) + the Top-50 table."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import config
from modules import analytics, query_generator as qg, storage


def render():
    st.header("📝 Step 1 — Top 50 Search Queries")
    rows = st.session_state.get("query_rows")
    if not rows:
        _render_setup(prefix="main")
    else:
        _render_table(rows)


def _render_setup(prefix: str):
    st.info(
        "Generate your 50 queries for **free** — no API key. Copy the prompt below, paste it into "
        "any AI tool (ChatGPT, Claude, Gemini, Perplexity), then paste its answer back here."
    )
    st.markdown("**1. Copy this prompt**")
    st.code(qg.build_ai_prompt(), language="text")
    st.markdown("**2. Paste the AI's answer** (format: `'abc', 'xyz', ...`)")
    pasted = st.text_area("Paste the 50 queries here", height=150, key=f"paste_{prefix}",
                          label_visibility="collapsed")
    if st.button("Parse & Save Queries", type="primary", key=f"parse_{prefix}"):
        parsed = qg.parse_pasted_queries(pasted or "")
        if not parsed:
            st.error("Couldn't find any queries. Paste a list like: 'best dermatologist in Guntur', ...")
            return
        try:
            qg.save_queries_xlsx(parsed)
        except Exception as exc:  # keep going even if the Excel write fails
            st.warning(f"Loaded, but the Excel export failed: {exc}")
        storage.save_rows(storage.QUERIES_JSON, parsed)
        st.session_state["query_rows"] = parsed
        st.session_state["queries_ready"] = True
        bd = qg.category_breakdown(parsed)
        st.success(f"Parsed {len(parsed)} queries — " + ", ".join(f"{k}: {v}" for k, v in bd.items()))
        if len(parsed) != 50:
            st.warning(f"Expected 50, found {len(parsed)}. You can re-paste or continue anyway.")
        st.rerun()


def _render_table(rows: list[dict]):
    df = pd.DataFrame(rows)
    left, right = st.columns([3, 1])
    with right:
        st.plotly_chart(analytics.donut_categories(rows), use_container_width=True, key="q_donut")
    with left:
        cats = st.multiselect("Filter category", sorted(df["category"].unique()), key="q_cat")
        c1, c2 = st.columns(2)
        search = c1.text_input("Search query text", key="q_search")
        sort_by = c2.selectbox("Sort by", ["rank", "search_strength_score"], key="q_sort")

    view = df.copy()
    if cats:
        view = view[view["category"].isin(cats)]
    if search:
        view = view[view["search_query"].str.contains(search, case=False, na=False)]
    view = view.sort_values(sort_by, ascending=(sort_by == "rank"))

    st.dataframe(
        view, use_container_width=True, hide_index=True,
        column_config={
            "rank": st.column_config.NumberColumn("Rank", width="small"),
            "search_query": st.column_config.TextColumn("Search Query", width="large"),
            "category": st.column_config.TextColumn("Category"),
            "user_intent": st.column_config.TextColumn("User Intent"),
            "search_strength_score": st.column_config.ProgressColumn(
                "Strength", min_value=0, max_value=10, format="%d"),
        },
    )

    p = Path(config.QUERIES_XLSX)
    if p.exists():
        st.download_button("⬇ Download queries (.xlsx)", p.read_bytes(),
                           file_name="search_queries_50.xlsx", key="dl_queries")

    with st.expander("↻ Replace queries"):
        _render_setup(prefix="replace")
