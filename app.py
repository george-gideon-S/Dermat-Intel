"""Derma Intel — Guntur dermatologist search-intelligence dashboard.

Free / no API keys. Run with:  streamlit run app.py
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st

import config
from modules import maps_collector, storage, vulnerability
from components import tab_analytics, tab_queries, tab_results, tab_vulnerable

st.set_page_config(page_title="Derma Intel — Guntur", layout="wide", page_icon="🔬",
                   initial_sidebar_state="expanded")


def _init_state():
    ss = st.session_state
    for key, default in {
        "query_rows": None, "result_rows": None, "scored_df": None, "top_df": None,
        "use_mock": False, "selected_query": None, "selected_clinic": None,
        "queries_ready": False, "maps_ready": False, "vuln_ready": False,
        "last_run": None,
    }.items():
        ss.setdefault(key, default)


def _recompute_vulnerability():
    rows = st.session_state.get("result_rows") or []
    scored = vulnerability.score_clinics(vulnerability.aggregate_clinics(rows))
    st.session_state["scored_df"] = scored
    st.session_state["top_df"] = vulnerability.top_n(scored, 10)
    st.session_state["vuln_ready"] = scored is not None and not scored.empty


def _load_from_disk_once():
    if st.session_state.get("_loaded"):
        return
    qr = storage.load_rows(storage.QUERIES_JSON)
    if qr:
        st.session_state["query_rows"] = qr
        st.session_state["queries_ready"] = True
    rr = storage.load_rows(storage.RESULTS_JSON)
    if rr:
        st.session_state["result_rows"] = rr
        st.session_state["maps_ready"] = True
        _recompute_vulnerability()
    st.session_state["last_run"] = storage.load_meta().get("last_run")
    st.session_state["_loaded"] = True


def _run_pipeline():
    queries = st.session_state.get("query_rows") or []
    if not queries:
        st.toast("Add queries first (Tab 1).", icon="⚠️")
        return
    use_mock = st.session_state.get("use_mock", False)
    progress = st.progress(0.0, text="Starting…")

    def cb(i, n, q):
        progress.progress(i / n, text=f"Scraping {i}/{n}: {q[:38]}…")

    try:
        with st.status("Collecting maps data…", expanded=False):
            rows = maps_collector.collect(queries, mock=use_mock, progress_cb=cb)
        progress.empty()
        st.session_state["result_rows"] = rows
        storage.save_rows(storage.RESULTS_JSON, rows)
        try:
            maps_collector.save_results_xlsx(rows)
        except Exception as exc:
            st.warning(f"Results saved in app, but Excel export failed: {exc}")
        _recompute_vulnerability()
        try:
            vulnerability.save_vulnerable_xlsx(st.session_state["top_df"])
        except Exception as exc:
            st.warning(f"Vulnerable export failed: {exc}")
        st.session_state["maps_ready"] = True
        st.session_state["last_run"] = datetime.now().isoformat(timespec="seconds")
        storage.save_meta({"last_run": st.session_state["last_run"]})
        n_vuln = 0 if st.session_state["top_df"] is None else len(st.session_state["top_df"])
        st.toast(f"Done — {len(rows)} rows, {n_vuln} vulnerable clinics.", icon="✅")
    except Exception as exc:
        progress.empty()
        st.error(f"Pipeline failed: {exc}")


def _sidebar():
    with st.sidebar:
        st.title("🔬 Derma Intel")
        st.caption("Guntur dermatologist market intelligence · free / no API keys")

        st.subheader("Data status")
        def dot(ok):
            return "🟢" if ok else "🔴"
        st.write(f"{dot(st.session_state['queries_ready'])} Queries loaded")
        st.write(f"{dot(st.session_state['maps_ready'])} Maps data collected")
        st.write(f"{dot(st.session_state['vuln_ready'])} Vulnerability scored")
        st.divider()

        st.session_state["use_mock"] = st.toggle(
            "Use mock data (no scraping)", value=st.session_state["use_mock"],
            help="Demo the whole dashboard instantly — no browser, no network.")
        if st.session_state["maps_ready"] and not st.session_state["use_mock"]:
            st.caption("⚠️ Running again overwrites the current data.")
        st.button("▶ Run Pipeline", type="primary", use_container_width=True,
                  disabled=not st.session_state["queries_ready"], on_click=_run_pipeline)
        if st.session_state["last_run"]:
            st.caption(f"Last run: {st.session_state['last_run']}")

        st.divider()
        rr = st.session_state.get("result_rows") or []
        qr = st.session_state.get("query_rows") or []
        top = st.session_state.get("top_df")
        st.metric("Queries", len(qr))
        st.metric("Appearance rows", len(rr))
        st.metric("Vulnerable identified", 0 if top is None else len(top))


def main():
    _init_state()
    _load_from_disk_once()
    _sidebar()
    t1, t2, t3, t4 = st.tabs(["📝 Queries", "🗺️ Results", "📊 Analytics", "🚨 Vulnerable 10"])
    with t1:
        tab_queries.render()
    with t2:
        tab_results.render()
    with t3:
        tab_analytics.render()
    with t4:
        tab_vulnerable.render()


main()
