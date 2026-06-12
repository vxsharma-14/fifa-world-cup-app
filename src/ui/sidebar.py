"""Manages the layout inside the persistent left sidebar configuration panel."""

import streamlit as st
from src.db_service import get_scheduled_matches


@st.dialog("📋 Tournament Rules & Scoring")
def show_rules_popup() -> None:
    """Displays the tournament rules overlay popup pulled from rules.md."""
    try:
        with open("rules.md", "r", encoding="utf-8") as file:
            st.markdown(file.read())
    except FileNotFoundError:
        st.error("Error: 'rules.md' file missing from project root folder.")

    st.markdown("---")
    if st.button("Close Rules", use_container_width=True):
        st.rerun()


def render_sidebar_schedule() -> list:
    """Renders the match reference list and overlay trigger components in the sidebar."""
    raw_matches = get_scheduled_matches()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📅 Today's Matches (IST)")

    if not raw_matches:
        st.sidebar.info("No matches listed for today.")
    else:
        for match in raw_matches:
            parts = match.split("|")
            if len(parts) == 3:
                st.sidebar.markdown(f"⚽ **{parts[0].strip()}**\n{parts[1].strip()} vs {parts[2].strip()}")
            else:
                st.sidebar.markdown(f"• {match}")

    st.sidebar.markdown("---")
    if st.sidebar.button("📋 View Tournament Rules", use_container_width=True):
        show_rules_popup()

    return raw_matches