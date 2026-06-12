"""Manages the layout inside the persistent left sidebar configuration panel."""

import streamlit as st
from src.config import CONFIG
from src.scoring_service import refresh_leaderboard

@st.dialog("📋 Tournament Rules & Scoring")
def show_rules_popup() -> None:
    """Displays the tournament rules overlay popup pulled from rules.md."""
    try:
        with open("rules.md", "r", encoding="utf-8") as file:
            st.markdown(file.read())
    except FileNotFoundError:
        st.error("Error: 'rules.md' file missing from project root folder.")

    st.markdown("---")
    if st.button("Close Rules", use_container_width=True, key="close_rules_btn"):
        st.rerun()

def render_sidebar_elements(active_email: str) -> None:
    """Renders persistent sidebar elements like Rules."""
    if active_email == CONFIG.ADMIN_EMAIL:
        st.sidebar.markdown("### 🛠️ Admin Tools")
        if st.sidebar.button("🔄 Refresh Leaderboard", use_container_width=True):
            with st.spinner("Recalculating scores..."):
                refresh_leaderboard()
                st.success("Leaderboard refreshed!")
    
    st.sidebar.markdown("---")
    if st.sidebar.button("📋 View Tournament Rules", use_container_width=True, key="view_rules_sidebar_btn"):
        show_rules_popup()
