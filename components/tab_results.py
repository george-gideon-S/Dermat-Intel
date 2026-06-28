"""Tab 2 — Maps results browser: query list | clinic cards | clinic detail."""
from __future__ import annotations

from collections import Counter

import streamlit as st

from components import _format as fmt
from modules import vulnerability as vuln


def render():
    st.header("🗺️ Maps Results")
    rows = st.session_state.get("result_rows")
    if not rows:
        st.info("No maps data yet — load queries (Tab 1) and click **Run Pipeline** in the sidebar.")
        return

    ok_rows = [r for r in rows if r.get("status") != "FETCH_FAILED" and str(r.get("name") or "").strip()]
    queries = list(dict.fromkeys(r["source_query"] for r in rows))
    counts = Counter(r["source_query"] for r in ok_rows)

    left, center, right = st.columns([1, 2, 1.5])

    with left:
        st.subheader("Queries")
        for q in queries:
            if st.button(f"{q}  ·  {counts.get(q, 0)}", key=f"q_{q}", use_container_width=True):
                st.session_state["selected_query"] = q

    sel_q = st.session_state.get("selected_query") or (queries[0] if queries else None)
    q_rows = sorted(
        [r for r in ok_rows if r["source_query"] == sel_q],
        key=lambda r: r.get("result_position") or 999,
    )

    with center:
        st.subheader(f"Clinics · {fmt.text(sel_q)}")
        term = st.text_input("Search clinics", key="clinic_search")
        cards = [r for r in q_rows if term.lower() in r["name"].lower()] if term else q_rows
        for r in cards:
            with st.container(border=True):
                pos = r.get("result_position")
                badge = "🟢" if (pos and pos <= 3) else ("⚪" if (pos and pos >= 10) else "🔵")
                st.markdown(f"{badge} **{r['name']}**  ·  #{int(pos) if pos else '?'}")
                st.caption(f"★ {fmt.rating(r.get('rating'))} ({fmt.reviews(r.get('user_ratings_total'))} reviews)")
                web = "🌐 " + (r["website"] if r.get("website") else "No website")
                phone = "📞 " + (r["formatted_phone_number"] if r.get("formatted_phone_number") else "No phone")
                st.caption(f"{web}  |  {phone}")
                if st.button("View details →", key=f"c_{sel_q}_{r['name']}_{pos}"):
                    st.session_state["selected_clinic"] = r["name"]

    with right:
        st.subheader("Clinic detail")
        name = st.session_state.get("selected_clinic")
        if not name and cards:
            name = cards[0]["name"]
        if not name:
            st.caption("Select a clinic to see details.")
            return
        appearances = [r for r in ok_rows if r["name"] == name]
        if not appearances:
            st.caption("Select a clinic to see details.")
            return
        d = appearances[0]
        st.markdown(f"### {name}")
        st.write(f"📍 {fmt.text(d.get('formatted_address'))}")
        st.write(f"📞 {fmt.text(d.get('formatted_phone_number'), 'No phone')}")
        st.write(f"★ {fmt.rating(d.get('rating'))} ({fmt.reviews(d.get('user_ratings_total'))} reviews)")
        st.write(f"🕑 {fmt.text(d.get('opening_hours'))}  ·  {fmt.text(d.get('business_status'))}")
        if d.get("website"):
            st.markdown(f"🌐 [{d['website']}]({d['website']})")
        # vulnerability pre-score for this clinic (aggregated across its appearances)
        agg = {
            "name": name,
            "website": next((a["website"] for a in appearances if a.get("website")), ""),
            "rating": max([a["rating"] for a in appearances if a.get("rating") is not None], default=None),
            "user_ratings_total": max(
                [a["user_ratings_total"] for a in appearances if a.get("user_ratings_total") is not None],
                default=None),
            "result_position_avg": sum(a.get("result_position") or 0 for a in appearances) / len(appearances),
            "appearances": len({a["source_query"] for a in appearances}),
            "formatted_phone_number": next(
                (a["formatted_phone_number"] for a in appearances if a.get("formatted_phone_number")), None),
            "business_status": d.get("business_status", "OPERATIONAL"),
        }
        score = vuln.compute_score(agg)
        label, color = vuln.label_for(score)
        st.markdown(
            f"<span style='background:{color};color:white;padding:3px 10px;border-radius:10px;"
            f"font-weight:700'>Vulnerability {score} · {label}</span>",
            unsafe_allow_html=True,
        )
        nq = len({a["source_query"] for a in appearances})
        with st.expander(f"Appeared in {nq} queries"):
            for q in sorted({a["source_query"] for a in appearances}):
                st.write(f"• {q}")
        if d.get("place_url"):
            st.link_button("🔗 View on Google Maps", d["place_url"])
