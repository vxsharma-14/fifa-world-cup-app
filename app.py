"""Tournament Prediction Web Application Entry Point Routing Context."""

import streamlit as st
from src.config import CONFIG, initialize_db
from src.db_service import get_scheduled_matches
from src.ui.auth import render_auth_panel
from src.ui.home import render_home_summary_dashboard
from src.ui.user_forms import render_daily_predictions_section
from src.ui.admin_panel import render_admin_dashboard
from src.ui.points_analysis import render_granular_points_analysis
from src.ui.tournament_setup import render_tournament_setup
from src.ui.sidebar import render_sidebar_elements
from streamlit_cookies_controller import CookieController
# ...
def get_cookie_controller():
    if "cookie_controller" not in st.session_state:
        st.session_state["cookie_controller"] = CookieController()
    return st.session_state["cookie_controller"]

def main() -> None:
    st.set_page_config(page_title="Fifa Fantasy APSJ", layout="wide", initial_sidebar_state="auto")
    st.title("🏆 FIFA Fantasy APSJ Dashboard")

    controller = get_cookie_controller()

    # Auto-login from cookie if session is empty
    if "authenticated_user" not in st.session_state:
        saved_email = controller.get("auth_email")
        if saved_email:
            # Re-fetch user data to populate session
            from src.db_service import get_user_data
            user_data = get_user_data(saved_email)
            if user_data:
                st.session_state["authenticated_user"] = saved_email
                st.session_state["user_name"] = user_data["name"]

    # Initialize connection endpoints
    initialize_db()
# ...

    # Render left tray entry points
    active_email = render_auth_panel()

    if not active_email:
        st.info("👈 Use the Access Portal in the sidebar to create an account or sign in.")
        return

    # Render persistent sidebar elements (Only if not admin, as admin panel has its own management)
    if active_email != CONFIG.ADMIN_EMAIL:
        render_sidebar_elements()

    if active_email == CONFIG.ADMIN_EMAIL:
        render_admin_dashboard()
        return

    # --- PAGE NAVIGATION MENU ---
    st.sidebar.markdown("### 🧭 Main Navigation")
    page_options = ["🏠 Dashboard Home", "🏆 Tournament Setup", "📝 Prediction Entry Forms", "🔍 Detailed Points Audit"]

    # Robust session state initialization
    if "current_page" not in st.session_state or st.session_state["current_page"] not in page_options:
        st.session_state["current_page"] = page_options[0]

    # Render buttons
    for page in page_options:
        if st.sidebar.button(
            page, 
            use_container_width=True, 
            key=f"nav_{page}",
            type="primary" if st.session_state["current_page"] == page else "secondary"
        ):
            st.session_state["current_page"] = page
            st.rerun()

    # --- PAGE ROUTING CONTROLLER ---
    if st.session_state["current_page"] == "🏠 Dashboard Home":
        render_home_summary_dashboard(active_email)

    elif st.session_state["current_page"] == "🏆 Tournament Setup":
        render_tournament_setup(active_email)

    elif st.session_state["current_page"] == "📝 Prediction Entry Forms":
        raw_matches = get_scheduled_matches()
        render_daily_predictions_section(active_email, raw_matches)

    elif st.session_state["current_page"] == "🔍 Detailed Points Audit":
        render_granular_points_analysis(active_email)

if __name__ == "__main__":
    main()