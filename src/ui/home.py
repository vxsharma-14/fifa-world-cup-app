"""UI component rendering the landing dashboard summary for logged-in users."""

import streamlit as st
from src.db_service import (get_pre_tournament_picks, get_daily_predictions, get_scheduled_matches, get_ist_date_key,
                            get_user_match_breakdown, get_match_points_breakdown)
from src.ui.leaderboard import render_leaderboard_table
from firebase_admin import db
from datetime import datetime
import zoneinfo

@st.dialog("📊 Global Tournament Leaderboard")
def show_leaderboard_popup() -> None:
    """Displays the live group rankings inside a clean modal popup wrapper."""
    st.markdown("### 🏆 Friend Standings")
    render_leaderboard_table()

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

    col1, col2 = st.columns([1, 2], gap="large")

    with col1:
        st.markdown("### 🎯 Your Active Lock-Ins")
        pre_t = get_pre_tournament_picks(email)
        teams = pre_t.get("teams", [])
        players = pre_t.get("players", [])

        with st.container(border=True):
            st.markdown("### 🛡️ Locked Teams")
            if teams:
                for team in teams:
                    st.markdown(f"• **{team}**")
            else:
                st.caption("No teams locked.")
        
        with st.container(border=True):
            st.markdown("### 👤 Locked Players")
            if players:
                for player in players:
                    # Handle both string names and dictionary objects
                    if isinstance(player, dict):
                        display_text = f"{player.get('name', 'Unknown')} ({player.get('team', '?')})"
                    else:
                        display_text = player
                    st.markdown(f"• **{display_text}**")
            else:
                st.caption("No players locked.")

    with col2:
        st.markdown("### 📅 Match Status Tracking")
        daily_t = get_daily_predictions(email, get_ist_date_key())
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
            
            # Table Header
            c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
            c1.caption("Date/Time")
            c2.caption("Match")
            c3.caption("Prediction")
            c4.caption("Action")
            
            for match in sorted(completed_list, key=lambda x: x.get("kickoff_time", ""), reverse=True):
                kickoff_dt = datetime.fromisoformat(match.get("kickoff_time", ""))
                display_time = kickoff_dt.strftime("%b %d, %I:%M %p")
                
                # Fetch result data
                match_id = match.get("id")
                results = match.get("results", {})
                
                # Format Match display (TeamA Score - Score TeamB)
                match_name = match.get("display_string", "").split(" | ")[-1]
                if results:
                    score_str = f"{results.get('home_score', '-')} - {results.get('away_score', '-')}"
                    match_display = f"{match.get('home_team')} {score_str} {match.get('away_team')}"
                else:
                    match_display = match_name

                # Fetch prediction
                match_date_key = get_ist_date_key(kickoff_dt)
                match_preds = get_daily_predictions(email, match_date_key)
                prediction = match_preds.get("teams", {}).get(match_id, "None")
                
                # Determine winner from results for status icon
                # Explicitly accessing 'winning_team' field from results node
                actual_winner = results.get("winning_team")

                # Status icon logic
                if prediction != "None" and actual_winner:
                    is_correct = (str(prediction).strip() == str(actual_winner).strip())
                    status_icon = " ✅" if is_correct else " ❌"
                else:
                    status_icon = "" 

                c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
                c1.text(display_time)
                c2.text(match_display)
                c3.text(f"{prediction} {status_icon}")
                
                # Popover for View Picks
                with c4.popover("View"):
                    st.write(f"Match: {match_display}")
                    st.write(f"Your Pick: {prediction}")
                    
                    # 1. Fetch user breakdown (totals)
                    user_breakdown = get_user_match_breakdown(email, match_date_key, match_id)
                    # 2. Fetch global granular breakdown
                    global_breakdown = get_match_points_breakdown(match_id)
                    # 3. Re-fetch daily predictions to get specific players picked for this match
                    match_daily_preds = get_daily_predictions(email, match_date_key)
                    match_daily_players = match_daily_preds.get('players', [])

                    if user_breakdown and global_breakdown:
                        st.markdown("**Points Breakdown:**")
                        
                        # Display Team breakdown
                        t_pts = user_breakdown.get('team_points', 0)
                        st.write(f"**Team Points: {t_pts}**")
                        # Drill down into global match data for the specific team breakdown
                        team_details = global_breakdown.get('team_points', {})
                        if prediction in team_details:
                            td = team_details[prediction]
                            st.write(f"- Win: {td.get('win', 0)} Goal Diff: {td.get('goaldiff', 0)}")

                        # Display Player breakdown
                        p_pts = user_breakdown.get('player_points', 0)
                        st.write(f"**Player Points: {p_pts}**")

                        # Drill down into global match data for the specific player breakdown
                        player_details = global_breakdown.get('player_points', {})
                        for p_name in match_daily_players:
                             if p_name in player_details:
                                 pd = player_details[p_name]
                                 st.write(f"- {p_name}: Goals {pd.get('goals',0)} MotM{pd.get('motm',0)}")

                        total = t_pts + p_pts
                        st.divider()
                        st.write(f"**Total Points: {total}**")
                        
                        if user_breakdown.get('multiplier_applied'):
                            st.caption("✅ Multiplier applied to this match.")
                    else:
                        st.write("Breakdown not available.")
            st.markdown("---")

        # 2. Render Upcoming Submissions Section
        st.markdown("##### ⏳ Tonight's Submissions")
        
        if not upcoming_list:
            st.info("No further matches scheduled for today.")
        else:
            # Table Header
            c1, c2, c3 = st.columns([2, 3, 2])
            c1.caption("Date/Time")
            c2.caption("Match")
            c3.caption("Your Prediction")
            
            for match in sorted(upcoming_list, key=lambda x: x.get("kickoff_time", "")):
                match_id = match.get("id")
                kickoff_dt = datetime.fromisoformat(match.get("kickoff_time", ""))
                display_time = kickoff_dt.strftime("%I:%M %p")
                
                # Match display
                match_name = match.get("display_string", "").split(" | ")[-1]
                
                # Get current prediction
                prediction = upcoming_teams_map.get(match_id, "Not Selected")
                
                c1, c2, c3 = st.columns([2, 3, 2])
                c1.text(display_time)
                c2.text(match_name)
                c3.text(prediction)
            
            if not upcoming_teams_map:
                st.warning("🚨 You haven't locked in predictions for tonight's upcoming games!")
                st.markdown(" ")
                if st.button("📝 Click Here to Enter Predictions Now", use_container_width=True, type="primary"):
                    st.session_state["current_page"] = "📝 Prediction Entry Forms"
                    st.rerun()