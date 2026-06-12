"""Tournament Prediction Web Application Entry Point Routing Context."""

import streamlit as st
from src.config import CONFIG, initialize_db
from src.db_service import get_scheduled_matches
from src.ui.auth import render_auth_panel
from src.ui.home import render_home_summary_dashboard
from src.ui.user_forms import render_pre_tournament_section, render_daily_predictions_section
from src.ui.admin_panel import render_admin_dashboard
from src.ui.points_analysis import render_granular_points_analysis

def main() -> None:
    st.set_page_config(page_title="Fifa Fantasy APSJ", layout="wide", initial_sidebar_state="auto")
    st.title("🏆 FIFA Fantasy APSJ Dashboard")

    # Initialize connection endpoints
    initialize_db()

    # Render left tray entry points
    active_email = render_auth_panel()

    if not active_email:
        st.info("👈 Use the Access Portal in the sidebar to create an account or sign in.")
        return

    if active_email == CONFIG.ADMIN_EMAIL:
        render_admin_dashboard()
        return

    # Initialize navigation state if not present
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "🏠 Dashboard Home"

    # --- PAGE NAVIGATION MENU ---
    st.sidebar.markdown("### 🧭 Main Navigation")

    # We use index calculation so the sidebar radio syncs up when redirected programmatically
    page_options = ["🏠 Dashboard Home", "📝 Prediction Entry Forms", "🔍 Detailed Points Audit"]
    default_index = page_options.index(st.session_state["current_page"])

    chosen_page = st.sidebar.radio(
        "Go to page:",
        page_options,
        index=default_index,
        key="nav_radio",
        label_visibility="collapsed"
    )

    # Sync state if user manually clicks sidebar
    if chosen_page != st.session_state["current_page"]:
        st.session_state["current_page"] = chosen_page
        st.rerun()

    # --- PAGE ROUTING CONTROLLER ---
    if st.session_state["current_page"] == "🏠 Dashboard Home":
        render_home_summary_dashboard(active_email)

    elif st.session_state["current_page"] == "📝 Prediction Entry Forms":
        raw_matches = get_scheduled_matches()
        col1, col2 = st.columns(2, gap="large")
        with col1:
            render_pre_tournament_section(active_email)
        with col2:
            render_daily_predictions_section(active_email, raw_matches)

    elif st.session_state["current_page"] == "🔍 Detailed Points Audit":
        # Call the new analytical ledger layout view safely
        render_granular_points_analysis(active_email)

if __name__ == "__main__":
    main()