"""UI component rendering the landing dashboard summary for logged-in users."""

import streamlit as st
from src.db_service import (get_pre_tournament_picks, get_daily_predictions, get_scheduled_matches, get_pt_date_key,
                            get_user_match_breakdown, get_match_points_breakdown, clean_email_key)
from src.ui.leaderboard import render_leaderboard_table
from firebase_admin import db
from datetime import datetime, timedelta
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
        
        # Get active time context
        current_time = datetime.now(zoneinfo.ZoneInfo("US/Pacific"))
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
            
            # Group matches by date
            matches_by_date = {}
            for match in completed_list:
                kickoff_dt = datetime.fromisoformat(match.get("kickoff_time", ""))
                date_key = get_pt_date_key(kickoff_dt)
                if date_key not in matches_by_date:
                    matches_by_date[date_key] = []
                matches_by_date[date_key].append(match)
            
            sorted_dates = sorted(matches_by_date.keys(), reverse=True)
            
            # Date Selector
            if "selected_date" not in st.session_state:
                st.session_state["selected_date"] = sorted_dates[0]
            
            selected_date = st.selectbox(
                "Filter by Date:",
                options=sorted_dates,
                index=sorted_dates.index(st.session_state["selected_date"]),
                key="date_selector"
            )
            st.session_state["selected_date"] = selected_date
            
            # Render cards for selected date
            day_matches = sorted(matches_by_date[selected_date], key=lambda x: x.get("kickoff_time", ""), reverse=True)
            
            # Using columns to create a grid: 2 columns on wide screens, stacks automatically on small screens
            cols = st.columns(2)
            
            for i, match in enumerate(day_matches):
                with cols[i % 2]:
                    kickoff_dt = datetime.fromisoformat(match.get("kickoff_time", ""))
                    display_time = kickoff_dt.strftime("%I:%M %p")
                    
                    # Fetch result data
                    match_id = match.get("id")
                    results = match.get("results", {})
                    
                    # Format Match display
                    match_name = match.get("display_string", "").split(" | ")[-1]
                    match_display = f"{match.get('home_team')} {results.get('home_score', '-')} - {results.get('away_score', '-')} {match.get('away_team')}" if results else match_name

                    # Fetch prediction
                    match_preds = get_daily_predictions(email, selected_date)
                    prediction = match_preds.get("teams", {}).get(match_id, "None")
                    
                    # Determine winner
                    actual_winner = results.get("winning_team")
                    is_correct = (prediction != "None" and actual_winner and str(prediction).strip() == str(actual_winner).strip())
                    status_icon = " ✅" if is_correct else " ❌" if str(actual_winner) != "None" else ""

                    # Card Layout
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 1])
                        c1.caption(f"{display_time} (PT)")
                        with c2.popover("View"):
                            st.write(f"Match: {match_display}")
                            st.write(f"Your Pick: {prediction}")
                            
                            user_breakdown = get_user_match_breakdown(email, selected_date, match_id)
                            global_breakdown = get_match_points_breakdown(match_id)
                            match_daily_preds = get_daily_predictions(email, selected_date)
                            match_daily_players = match_daily_preds.get('players', [])

                            if user_breakdown and global_breakdown:
                                st.markdown("**Points Breakdown:**")
                                t_pts = user_breakdown.get('team_points', 0)
                                st.write(f"**Team Points: {t_pts}**")
                                team_details = global_breakdown.get('team_points', {})
                                if prediction in team_details:
                                    td = team_details[prediction]
                                    st.write(f"- Win: {td.get('win', 0)} GD: {td.get('goaldiff', 0)}")
                                p_pts = user_breakdown.get('player_points', 0)
                                st.write(f"**Player Points: {p_pts}**")
                                player_details = global_breakdown.get('player_points', {})
                                for p_entry in match_daily_players:
                                     p_name = p_entry.get('name', p_entry) if isinstance(p_entry, dict) else p_entry
                                     if p_name in player_details:
                                         pd = player_details[p_name]
                                         st.write(f"- {p_name}: Goals {pd.get('goals',0)} MotM{pd.get('motm',0)}")
                                st.divider()
                                st.write(f"**Total Points: {user_breakdown.get('team_points', 0) + user_breakdown.get('player_points', 0)}**")
                                if user_breakdown.get('multiplier_applied'):
                                    st.caption("✅ Multiplier applied.")
                            else:
                                st.write("Breakdown not available.")
                                
                        st.markdown(f"**{match_display}**")
                        st.markdown(f"Prediction: {prediction}{status_icon}")
            st.markdown("---")

        # 2. Render Upcoming Submissions Section
        # Calculate time to next match cutoff (kickoff - 15 mins)
        if upcoming_list:
            next_match = min(upcoming_list, key=lambda x: x.get("kickoff_time", ""))
            kickoff_dt = datetime.fromisoformat(next_match.get("kickoff_time", ""))
            cutoff_dt = kickoff_dt - timedelta(minutes=15)
            time_remaining = cutoff_dt - current_time
            
            if time_remaining.total_seconds() > 0:
                hours, remainder = divmod(int(time_remaining.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
            else:
                st.error("⚠️ Match prediction locked!", icon="🔒")

        st.markdown("##### ⏳ Upcoming Submissions")
        
        if not upcoming_list:
            st.info("No upcoming matches scheduled.")
        else:
            # Group upcoming matches by date
            upcoming_by_date = {}
            for match in upcoming_list:
                kickoff_dt = datetime.fromisoformat(match.get("kickoff_time", ""))
                date_key = get_pt_date_key(kickoff_dt)
                if date_key not in upcoming_by_date:
                    upcoming_by_date[date_key] = []
                upcoming_by_date[date_key].append(match)
            
            sorted_upcoming_dates = sorted(upcoming_by_date.keys())
            
            # Date Selector for upcoming
            selected_up_date = st.selectbox(
                "Filter Upcoming by Date:",
                options=sorted_upcoming_dates,
                key="upcoming_date_selector"
            )
            st.warning(f"Predictions for {selected_up_date} locks in **{hours}h {minutes}m**", icon="⏰")
            day_upcoming = sorted(upcoming_by_date[selected_up_date], key=lambda x: x.get("kickoff_time", ""))
            
            # Fetch predictions for the SELECTED upcoming date dynamically
            match_preds = get_daily_predictions(email, selected_up_date)
            upcoming_teams_map = match_preds.get("teams", {})
            upcoming_daily_players = match_preds.get("players", [])
            
            # Display Daily Impact Players
            if upcoming_daily_players:
                # Handle both string names and dictionary objects
                player_names = [p.get('name', 'Unknown') if isinstance(p, dict) else p for p in upcoming_daily_players]
                st.info(f"**Daily Impact Players:** {', '.join(player_names)}")
            
            # Card Grid
            cols = st.columns(2)
            for i, match in enumerate(day_upcoming):
                with cols[i % 2]:
                    kickoff_dt = datetime.fromisoformat(match.get("kickoff_time", ""))
                    display_time = kickoff_dt.strftime("%I:%M %p")
                    match_id = match.get("id")
                    
                    match_name = match.get("display_string", "").split(" | ")[-1]
                    prediction = upcoming_teams_map.get(match_id, "Not Selected")

                    with st.container(border=True):
                        st.caption(f"{display_time} (PT)")
                        st.markdown(f"**{match_name}**")
                        st.markdown(f"Prediction: `{prediction}`")

            if not upcoming_teams_map:
                st.warning("🚨 You haven't locked in predictions for some upcoming games!")
                st.markdown(" ")
                if st.button("📝 Click Here to Enter Predictions Now", use_container_width=True, type="primary"):
                    st.session_state["current_page"] = "📝 Daily Predictions"
                    st.rerun()