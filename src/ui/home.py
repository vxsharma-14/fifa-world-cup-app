"""UI component rendering the landing dashboard summary for logged-in users."""

import streamlit as st
from src.db_service import get_pre_tournament_picks, get_daily_predictions, get_scheduled_matches
from firebase_admin import db
from datetime import datetime
import zoneinfo

@st.dialog("📊 Global Tournament Leaderboard")
def show_leaderboard_popup() -> None:
    """Displays the live group rankings inside a clean modal popup wrapper."""
    st.markdown("### 🏆 Friend Standings")
    leaderboard_data = db.reference("leaderboard").get() or {}

    if not leaderboard_data:
        st.info("No data available yet. Rank positions will update once the first match kicks off!")
    else:
        sorted_ranks = sorted(
            [
                {
                    "Rank": 0,
                    "Friend": v.get("name", k),
                    "Total Points": f"{v.get('total_score', 0)} pts",
                    "Last Gain": f"+{v.get('last_daily_score', 0)}"
                }
                for k, v in leaderboard_data.items()
            ],
            key=lambda x: int(x["Total Points"].split()[0]), reverse=True
        )
        for idx, item in enumerate(sorted_ranks, 1):
            item["Rank"] = idx
        st.table(sorted_ranks)

    st.markdown("---")
    if st.button("Close Standings", use_container_width=True):
        st.rerun()

def render_home_summary_dashboard(email: str) -> None:
    """Renders a clean, clutter-free bird's-eye view summary of the user's status."""
    st.subheader("🏠 Welcome back to the Tournament Hub!")
    st.caption("Here is your real-time performance summary and active lock-ins.")

    leaderboard_data = db.reference("leaderboard").get() or {}
    user_node = leaderboard_data.get(email.replace(".", "_"), {})

    user_total_score = user_node.get("total_score", 0)
    user_last_score = user_node.get("last_daily_score", 0)

    sorted_ranks = sorted(
        [(k, v.get("total_score", 0)) for k, v in leaderboard_data.items()],
        key=lambda x: x[1], reverse=True
    )
    user_rank = "N/A"
    for rank, (cleaned_email, _) in enumerate(sorted_ranks, 1):
        if cleaned_email == email.replace(".", "_"):
            user_rank = f"#{rank}"
            break

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric(label="🏆 Your Total Points", value=f"{user_total_score} pts")
    with m2:
        st.metric(label="📈 Current Group Rank", value=user_rank)
    with m3:
        st.metric(label="⚽ Last Matchday Gain", value=f"+{user_last_score} pts")

    if st.button("📊 View Full Leaderboard Table", use_container_width=True, type="secondary"):
        show_leaderboard_popup()

    st.markdown("---")

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("### 🎯 Your Active Lock-Ins")
        pre_t = get_pre_tournament_picks(email)

        sub_c1, sub_c2 = st.columns(2)
        with sub_c1:
            st.markdown("**Pre-T Teams:**")
            teams = pre_t.get("teams", [])
            if teams:
                for team in teams:
                    st.markdown(f"• `{team}`")
            else:
                st.caption("⚠️ No teams locked in yet.")
        with sub_c2:
            st.markdown("**Pre-T Players:**")
            players = pre_t.get("players", [])
            if players:
                for player in players:
                    st.markdown(f"• `{player}`")
            else:
                st.caption("⚠️ No players locked in yet.")

    with col2:
        st.markdown("### 📅 Match Status Tracking")
        daily_t = get_daily_predictions(email)
        upcoming_teams_map = daily_t.get("teams", {})
        upcoming_players = daily_t.get("players", [])

        # Get active time context
        current_time = datetime.now(zoneinfo.ZoneInfo("Asia/Kolkata"))
        raw_matches = get_scheduled_matches()

        upcoming_list = []
        completed_list = []

        # Categorize matches dynamically based on timestamp comparison
        if isinstance(raw_matches, dict):
            for match in raw_matches.values():
                kickoff_iso = match.get("kickoff_time", "")
                if kickoff_iso:
                    kickoff_dt = datetime.fromisoformat(kickoff_iso)
                    if current_time >= kickoff_dt:
                        completed_list.append(match)
                    else:
                        upcoming_list.append(match)
                else:
                    upcoming_list.append(match)

        # 1. Render Completed Matches Section
        if completed_list:
            st.markdown("##### ✅ Completed Matches")
            for match in sorted(completed_list, key=lambda x: x.get("kickoff_time", "")):
                match_id = match.get("id")
                saved_winner = upcoming_teams_map.get(match_id, "None Submitted")
                st.markdown(f"🏁 *{match.get('display_string')}* ➔ **Your Pick:** `{saved_winner}`")
            st.markdown("---")

        # 2. Render Upcoming Submissions Section
        st.markdown("##### ⏳ Tonight's Submissions")
        if not upcoming_teams_map:
            st.warning("🚨 You haven't locked in predictions for tonight's upcoming games!")
            if upcoming_list:
                for match in sorted(upcoming_list, key=lambda x: x.get("kickoff_time", "")):
                    st.markdown(f"⏳ *{match.get('display_string')}*")
            st.markdown(" ")
            if st.button("📝 Click Here to Enter Predictions Now", use_container_width=True, type="primary"):
                st.session_state["current_page"] = "📝 Prediction Entry Forms"
                st.rerun()
        else:
            if not upcoming_list:
                st.info("No further matches scheduled for today.")
            else:
                for match in sorted(upcoming_list, key=lambda x: x.get("kickoff_time", "")):
                    match_id = match.get("id")
                    winner = upcoming_teams_map.get(match_id, "Not Selected")
                    st.markdown(f"• {match.get('display_string')} ➔ **Your Pick:** `{winner}`")

            if upcoming_players:
                st.markdown(f"**Daily Impact Players:** `{', '.join(upcoming_players)}`")