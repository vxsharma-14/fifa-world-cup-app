"""
Tournament Prediction Web Application.

Integrated with Firebase Realtime Database (RTDB) for persistent storage.
Features a permanent sidebar match schedule, an overlay modal for rules,
dynamic match dropdown prediction matrices, and secure SHA-256 session handling.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import firebase_admin
from firebase_admin import credentials, db
import streamlit as st
import json

# --- Configuration ---
CONFIG = SimpleNamespace(
    # REPLACE THIS URL with your actual Firebase Realtime Database URL
    DATABASE_URL="https://fifa-world-cup-apsj-default-rtdb.firebaseio.com/",
    ADMIN_EMAIL="admin@fifafantasy.com"
)

# --- Initialize Firebase Admin SDK (Idempotent) ---
if not firebase_admin._apps:
    # Read the JSON string from Streamlit secrets
    creds_dict = json.loads(st.secrets["firebase_json"])
    cred = credentials.Certificate(creds_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': CONFIG.DATABASE_URL
    })

# --- Helper Utilities ---
def hash_password(password: str) -> str:
    """Hashes passwords using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def get_ist_timestamp() -> str:
    """Generates current timestamp formatted in Indian Standard Time (IST)."""
    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    return ist_now.strftime("%Y-%m-%d %I:%M:%S %p IST")

def clean_email_key(email: str) -> str:
    """Realtime Database keys cannot contain dots '.'. This cleans the email key."""
    return email.replace(".", "_")

# --- Rules Popup Modal ---
@st.dialog("📋 Tournament Rules & Scoring")
def show_rules_popup() -> None:
    """Displays the tournament rules overlay popup with a manual close button."""
    st.markdown("### 🏆 Prediction Guidelines")
    st.markdown("""
    Welcome to the FIFA Fantasy Prediction Portal! Please review the rules below:
    
    1. **Pre-Tournament Lock-Ins:** You must select exactly 2 teams and 5 players before the main tournament kicks off. These choices are locked for the entire month.
    2. **Daily Predictions:** For each day, select the specific winner for every scheduled match and pick your top 2 performance players.
    3. **Submission Cutoffs:** All daily predictions must be submitted at least **15 minutes before the first match of the day** begins (IST). Timestamps are strictly audited.
    """)

    st.markdown("### 📊 Scoring Matrix")
    st.markdown("""
    - **Correct Match Winner:** +10 Points
    - **Correct Player Performance Pick:** +5 Points
    - *Additional pre-tournament bonus points will be applied at the end of the tournament.*
    """)

    st.markdown("---")
    if st.button("Close Rules", use_container_width=True):
        st.rerun()

# --- UI Components ---
def render_sidebar_schedule() -> list:
    """Fetches and renders today's match schedule permanently inside the sidebar."""
    raw_matches = db.reference("metadata/matches").get() or []

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📅 Today's Matches (IST)")

    if not raw_matches:
        st.sidebar.info("No matches listed for today.")
    else:
        for idx, match in enumerate(raw_matches):
            parts = match.split("|")
            if len(parts) == 3:
                time_val = parts[0].strip()
                team1 = parts[1].strip()
                team2 = parts[2].strip()
                st.sidebar.markdown(f"⚽ **{time_val}**\n{team1} vs {team2}")
            else:
                st.sidebar.markdown(f"• {match}")

    st.sidebar.markdown("---")
    # Trigger the modal popup window when clicked
    if st.sidebar.button("📋 View Tournament Rules", use_container_width=True):
        show_rules_popup()

    return raw_matches

def render_auth_panel() -> str:
    """Renders authentication flows inside the sidebar wrapper."""
    st.sidebar.title("🔐 Access Portal")

    if "authenticated_user" in st.session_state:
        st.sidebar.success(f"Hello, {st.session_state['user_name']}")
        if st.sidebar.button("Log Out", use_container_width=True):
            del st.session_state["authenticated_user"]
            del st.session_state["user_name"]
            st.rerun()

        # Render schedule and rules button directly below Logout button
        if st.session_state["authenticated_user"] != CONFIG.ADMIN_EMAIL:
            render_sidebar_schedule()

        return st.session_state["authenticated_user"]

    auth_mode = st.sidebar.radio("Choose Action:", ["Login", "Sign Up"])

    if auth_mode == "Sign Up":
        with st.sidebar.form("signup_form"):
            st.subheader("Create Account")
            new_name = st.text_input("Full Name").strip()
            new_email = st.text_input("Email Address").strip().lower()
            new_pass = st.text_input("Password", type="password")

            if st.form_submit_button("Register"):
                if not new_name or not new_email or not new_pass:
                    st.sidebar.error("All fields are required.")
                    return ""

                cleaned_email = clean_email_key(new_email)
                user_ref = db.reference(f"users/{cleaned_email}").get()

                if user_ref is not None:
                    st.sidebar.error("Email already registered.")
                    return ""

                db.reference(f"users/{cleaned_email}").set({
                    "email": new_email,
                    "name": new_name,
                    "password_hash": hash_password(new_pass)
                })
                st.sidebar.success("Registration successful! Switch to Login.")

    elif auth_mode == "Login":
        with st.sidebar.form("login_form"):
            st.subheader("Sign In")
            email = st.text_input("Email Address").strip().lower()
            password = st.text_input("Password", type="password")

            if st.form_submit_button("Login"):
                if not email or not password:
                    st.sidebar.error("Please fill in all fields.")
                    return ""

                cleaned_email = clean_email_key(email)
                user_data = db.reference(f"users/{cleaned_email}").get()

                if user_data and user_data["password_hash"] == hash_password(password):
                    st.session_state["authenticated_user"] = email
                    st.session_state["user_name"] = user_data["name"]
                    st.rerun()
                else:
                    st.sidebar.error("Invalid credentials.")

    return ""

def render_pre_tournament_section(email: str) -> None:
    """Handles submission of baseline pre-tournament picks using individual text boxes."""
    st.subheader("🏆 1. Pre-Tournament Lock-Ins")
    st.caption("Select your baseline 2 Teams and 5 Players for the entire tournament.")

    cleaned_email = clean_email_key(email)
    existing = db.reference(f"pre_tournament/{cleaned_email}").get() or {}
    existing_teams = existing.get("teams", ["", ""])
    existing_players = existing.get("players", ["", "", "", "", ""])

    while len(existing_teams) < 2: existing_teams.append("")
    while len(existing_players) < 5: existing_players.append("")

    with st.form("pre_tournament_form"):
        st.markdown("**Predict 2 Teams:**")
        team_inputs = [
            st.text_input(f"Team {i+1}", value=existing_teams[i], key=f"pre_team_{i}")
            for i in range(2)
        ]

        st.markdown("**Predict 5 Players:**")
        player_inputs = [
            st.text_input(f"Player {i+1}", value=existing_players[i], key=f"pre_player_{i}")
            for i in range(5)
        ]

        if st.form_submit_button("Lock Pre-Tournament Entries"):
            team_list = [t.strip() for t in team_inputs if t.strip()]
            player_list = [p.strip() for p in player_inputs if p.strip()]

            if len(team_list) != 2 or len(player_list) != 5:
                st.error("Validation Error: Please fill out all fields.")
                return

            db.reference(f"pre_tournament/{cleaned_email}").set({
                "teams": team_list,
                "players": player_list,
                "submitted_at": get_ist_timestamp()
            })
            st.success("Pre-tournament selections updated!")

def render_daily_predictions_section(email: str, raw_matches: list) -> None:
    """Processes match-by-match unique binary dropdown predictions from global matches array."""
    st.subheader("📅 2. Today's Predictions Dashboard")

    if not raw_matches:
        st.info("Awaiting today's match configurations from the administrator.")
        return

    cleaned_email = clean_email_key(email)
    existing = db.reference(f"daily_predictions/{cleaned_email}").get() or {}
    existing_teams_map = existing.get("teams", {})
    existing_players = existing.get("players", ["", ""])

    while len(existing_players) < 2: existing_players.append("")

    with st.form("daily_prediction_form"):
        st.markdown("#### ⚽ Match Winner Selection Matrix")
        st.caption("Pick your predicted winner for each distinct match:")

        selected_winners = {}

        for idx, match in enumerate(raw_matches):
            parts = match.split("|")
            if len(parts) == 3:
                time_val = parts[0].strip()
                team1 = parts[1].strip()
                team2 = parts[2].strip()

                options = [team1, team2]

                default_idx = 0
                saved_pick = existing_teams_map.get(f"Match_{idx+1}")
                if saved_pick in options:
                    default_idx = options.index(saved_pick)

                chosen_winner = st.selectbox(
                    f"🏆 Match {idx+1} ({time_val}): {team1} vs {team2}",
                    options=options,
                    index=default_idx,
                    key=f"match_drop_{idx}"
                )
                selected_winners[f"Match_{idx+1}"] = chosen_winner
            else:
                st.text(f"Parsing error on line item: {match}")

        st.markdown("---")
        st.markdown("#### 🏃‍♂️ Daily Player Picks")
        st.caption("Provide your top 2 performance players for the whole day:")
        daily_player_inputs = [
            st.text_input(f"Daily Player {i+1}", value=existing_players[i], key=f"daily_player_{i}")
            for i in range(2)
        ]

        if st.form_submit_button("Submit Daily Dashboard Predictions"):
            player_list = [p.strip() for p in daily_player_inputs if p.strip()]

            if len(player_list) != 2:
                st.error("Validation Error: Please make sure both Daily Player text boxes are filled out.")
                return

            db.reference(f"daily_predictions/{cleaned_email}").set({
                "teams": selected_winners,
                "players": player_list,
                "submitted_at": get_ist_timestamp()
            })
            st.success("Your match winner selections and player picks are safely locked in RTDB!")

def render_admin_dashboard() -> None:
    """Dashboard for admin to manage current matches and audit user tools."""
    st.header("👑 Admin Command Center")

    st.subheader("Manage Today's Matches")
    st.caption("CRITICAL: Enter matches strictly using this pipe format: **Time (IST) | Team 1 | Team 2**")

    current_matches = db.reference("metadata/matches").get() or []
    placeholder_example = "12:30 AM | Mexico | South Africa\n03:30 AM | Uruguay | France"

    matches_text = st.text_area(
        "Edit schedule details:",
        value="\n".join(current_matches) if current_matches else placeholder_example,
        height=120
    )

    if st.button("Update Match Schedule & Sync Dropdowns"):
        clean_matches = [m.strip() for m in matches_text.split("\n") if m.strip()]
        db.reference("metadata/matches").set(clean_matches)
        st.success("Matches sync complete across cloud database!")
        st.rerun()

    st.markdown("---")
    st.subheader("🔧 User Account Support Tools")

    with st.form("admin_reset_form"):
        target_email = st.text_input("Enter user's email to reset password:").strip().lower()
        if st.form_submit_button("Reset User Password to '123456'"):
            if not target_email:
                st.error("Please enter a valid email.")
            else:
                cleaned_target = clean_email_key(target_email)
                user_node = db.reference(f"users/{cleaned_target}").get()
                if not user_node:
                    st.error("User email not found in database.")
                else:
                    db.reference(f"users/{cleaned_target}/password_hash").set(hash_password("123456"))
                    st.success(f"Password for {target_email} successfully reset to '123456'!")

    st.markdown("---")
    st.subheader("Realtime Database Registry")
    tab1, tab2 = st.tabs(["Pre-Tournament Data", "Daily Predictions Data"])
    with tab1:
        st.json(db.reference("pre_tournament").get() or {})
    with tab2:
        st.json(db.reference("daily_predictions").get() or {})

# --- Routing Engine ---
def main() -> None:
    st.set_page_config(page_title="Tournament Hub", layout="centered")
    st.title("🏆 FIFA Fantasy Prediction Portal")

    active_email = render_auth_panel()

    if not active_email:
        st.info("👈 Use the Access Portal in the sidebar to create an account or sign in.")
        return

    if active_email == CONFIG.ADMIN_EMAIL:
        render_admin_dashboard()
        return

    raw_matches = db.reference("metadata/matches").get() or []

    render_pre_tournament_section(active_email)
    st.markdown("---")
    render_daily_predictions_section(active_email, raw_matches)

if __name__ == "__main__":
    main()