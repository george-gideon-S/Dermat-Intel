"""Tab 4 — Top 10 vulnerable clinics + Excel / PDF export."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import config
from components import _format as fmt
from modules import vulnerability as vuln


def _ascii(s: str) -> str:
    """fpdf core fonts are latin-1 only; replace anything outside it."""
    return str(s).encode("latin-1", "replace").decode("latin-1")


def build_pdf_brief(top_df) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Derma Intel - Guntur: Top 10 Vulnerable Clinics",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, "Clinics with the weakest online presence (highest opportunity).",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    for i, (_, r) in enumerate(top_df.iterrows(), start=1):
        pdf.set_font("Helvetica", "B", 11)
        head = f"{i}. {_ascii(r.get('name', ''))}  [{int(r.get('vulnerability_score', 0))} / {_ascii(r.get('vulnerability_label', ''))}]"
        pdf.cell(0, 7, head, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)
        line = f"{_ascii(fmt.text(r.get('formatted_address')))} | {_ascii(fmt.text(r.get('formatted_phone_number'), 'No phone'))} | {_ascii(fmt.text(r.get('website'), 'No website'))}"
        pdf.multi_cell(0, 5, line)
        pdf.multi_cell(0, 5, _ascii(r.get("opportunity_notes", "")))
        pdf.ln(1)
    return bytes(pdf.output())


def render():
    st.header("🚨 Top 10 Clinics That Need Your Help Most")
    top = st.session_state.get("top_df")
    scored = st.session_state.get("scored_df")
    if top is None or len(top) == 0:
        st.info("No vulnerability data yet — run the pipeline from the sidebar.")
        return

    st.write(vuln.build_overview(scored))
    st.divider()

    for i, (_, r) in enumerate(top.iterrows(), start=1):
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"### {i}. {r.get('name', '')}")
            color = r.get("vulnerability_color", "#CA8A04")
            score = int(r.get("vulnerability_score", 0))
            label = r.get("vulnerability_label", "")
            c2.markdown(
                f"<div style='background:{color};color:white;padding:8px;border-radius:10px;"
                f"text-align:center;font-weight:700'>{score} · {label}</div>",
                unsafe_allow_html=True,
            )
            st.write(f"📍 {fmt.text(r.get('formatted_address'))}  |  📞 {fmt.text(r.get('formatted_phone_number'), 'No phone')}")
            st.write(
                f"★ {fmt.rating(r.get('rating'))} ({fmt.reviews(r.get('user_ratings_total'))} reviews)"
                f"  |  🌐 {fmt.text(r.get('website'), 'No website')}"
            )
            st.progress(score / 100)
            st.markdown(f"*💡 {r.get('opportunity_notes', '')}*")
            if r.get("place_url"):
                st.link_button("🔗 View on Google Maps", r["place_url"])

    st.divider()
    c1, c2 = st.columns(2)
    p = Path(config.VULNERABLE_XLSX)
    if p.exists():
        c1.download_button("📥 Download Excel", p.read_bytes(),
                           file_name="vulnerable_10.xlsx", use_container_width=True)
    try:
        pdf_bytes = build_pdf_brief(top)
        c2.download_button("📄 Export PDF Brief", pdf_bytes, file_name="vulnerable_brief.pdf",
                           mime="application/pdf", use_container_width=True)
    except Exception as exc:
        c2.caption(f"PDF export unavailable: {exc}")
