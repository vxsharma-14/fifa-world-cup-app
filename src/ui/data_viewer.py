"""Reusable module for secure, filtered, and cutoff-aware data access."""

import streamlit as st
from datetime import datetime, timedelta
import zoneinfo
from src.db_service import get_all_users, get_daily_predictions, get_scheduled_matches, get_pre_tournament_picks, clean_email_key, get_user_match_breakdown, get_match_points_breakdown

PT = zoneinfo.ZoneInfo("US/Pacific")

def is_cutoff_passed(match_kickoff_iso: str) -> bool:
    """Checks if the match prediction cutoff (kickoff - 15m) has passed."""
    kickoff_dt = datetime.fromisoformat(match_kickoff_iso).astimezone(PT)
    cutoff_dt = kickoff_dt - timedelta(minutes=15)
    return datetime.now(PT) >= cutoff_dt

def get_authorized_predictions(target_email: str, target_date: str, viewer_email: str, is_admin: bool) -> dict:
    """
    Retrieves authorized predictions for a specific date.
    Admin sees all.
    Users see their own, or others' ONLY after the cutoff for the first match of that date has passed.
    """
    if is_admin or target_email == viewer_email:
        return get_daily_predictions(target_email, target_date)
    
    # Check if cutoff passed for the first match on this date
    all_matches = get_scheduled_matches()
    date_matches = [m for m in all_matches.values() 
                    if datetime.fromisoformat(m.get("kickoff_time", "")).astimezone(PT).strftime("%Y-%m-%d") == target_date]
    
    if not date_matches: return {}
    
    # Find the earliest match of the day
    earliest_match = min(date_matches, key=lambda x: x.get("kickoff_time", ""))
    
    # Check only the earliest match cutoff
    if not is_cutoff_passed(earliest_match.get("kickoff_time", "")):
        return {} # Still locked
            
    return get_daily_predictions(target_email, target_date)

def render_daily_prediction_card(email, date, match_id, match_data, prediction, daily_players, performance_view="Both"):
    """Renders a structured insight card for a single match."""
    # 1. Fetch breakdown and metadata
    breakdown = get_user_match_breakdown(email, date, match_id)
    match_points = get_match_points_breakdown(match_id)
    results = match_data.get("results", {})
    is_completed = match_data.get("status") == "completed"

    # 2. Card Layout
    with st.container(border=True):
        # Header: Match Summary
        score = f"{results.get('home_score', '-')} - {results.get('away_score', '-')}" if results else "VS"
        st.markdown(f"#### {match_data['home_team']} {score} {match_data['away_team']}")

        # 4. Granular Performance
        # Team Performance
        if performance_view in ["Both", "Team"]:
                # Point Breakup from match_points node
                team_metrics = match_points.get('team_points', {}).get(prediction, {})
                win_pts = team_metrics.get('win', 0)
                gd_pts = team_metrics.get('goaldiff', 0)
                total_pts = team_metrics.get('total', 0)
                mult = "Yes" if breakdown.get('multiplier_applied') else "No"

                with st.container(border=True):
                    if is_completed:
                        st.metric(label=prediction, value=total_pts)
                        st.caption(f"Win: {win_pts} | GD: {gd_pts} | Mult: {mult}")
                    else:
                        st.metric(label=prediction, value=None)
                        st.caption("To be calculated")

def render_player_performance_view(email, date, preds):
    """Renders structured player performance view using match_points data."""
    players = preds.get("players", [])
    if not players:
        st.info("No players selected for this date.")
        return

    st.markdown("#### Player Performance")

    # We need to map matches on this date to their match_points
    all_matches = get_scheduled_matches()
    matches_on_date = [m for m in all_matches.values()
                       if datetime.fromisoformat(m.get("kickoff_time", "")).astimezone(PT).strftime("%Y-%m-%d") == date]

    # 1. Aggregate stats for all selected players on this date
    def _get_name(p):
        return p.get('name', p) if isinstance(p, dict) else p

    player_names = [_get_name(p) for p in players]

    # Structure: {player_name: {'goals': 0, 'motm': 0, 'total': 0, 'is_completed': False}}
    aggregated_stats = {name: {'goals': 0, 'motm': 0, 'total': 0, 'is_completed': False} for name in player_names}

    for match in matches_on_date:
        is_completed = match.get('status') == "completed"
        match_points = get_match_points_breakdown(match.get('id'))
        player_points_map = match_points.get('player_points', {})

        for name in player_names:
            stats = player_points_map.get(name, {})
            aggregated_stats[name]['goals'] += stats.get('goals', 0)
            aggregated_stats[name]['motm'] += stats.get('motm', 0)
            aggregated_stats[name]['total'] += stats.get('total', 0)
            if is_completed: aggregated_stats[name]['is_completed'] = True


    # 2. Render Metric Cards
    cols = st.columns(len(player_names))
    for j, col in enumerate(cols):
        name = player_names[j]
        stats = aggregated_stats.get(name, {})
        with col.container(border=True):
            if stats['is_completed']:
                st.metric(label=name, value=stats.get('total', 0))
                st.caption(f"Goals: {stats.get('goals', 0)} | MOTM: {stats.get('motm', 0)}")
            else:
                st.metric(label=name, value=None)
                st.caption("To be calculated1")

def render_filtered_participant_view(viewer_email: str, is_admin: bool):
    """Reusable UI for filtered participant data viewing."""

    # 1. User Selection (Pills)
    all_users = get_all_users()
    user_options = {
        "All": "All",
        **{email: u.get("name", email)
        for email, u in all_users.items()
        if "admin" not in u.get("name", "").lower()}
    }
    selected_key = st.pills(
        "Select Participant:",
        options=list(user_options.keys()),
        format_func=lambda x: user_options[x],
        selection_mode="single"
    )

    if not selected_key:
        st.info("Please select a participant to view their data.")
        return

    selected_email = selected_key
    view_type = st.pills(
        "Select Data View:",
        options=["Pre-Tournament", "Daily Predictions"],
        selection_mode="single"
    )

    if not view_type:
        return

    if view_type == "Pre-Tournament":
        st.subheader(f"🛡️ Pre-Tournament Picks: {user_options[selected_email]}")
        if selected_key == "All":
            rows = []
            for email, u in all_users.items():
                # Skip admin
                if "admin" in u.get("name", "").lower(): continue
                pre_t = get_pre_tournament_picks(email)
                teams = pre_t.get("teams", [])
                # Extract names if player is a dict, otherwise use string
                players = [p.get('name', p) if isinstance(p, dict) else p for p in pre_t.get("players", [])]

                # Pad lists to ensure columns exist even if user picked fewer
                teams_padded = (teams + [""] * 2)[:2]
                players_padded = (players + [""] * 5)[:5]
                row = {"User": u.get("name", email)}
                for i in range(2): row[f"Team {i + 1}"] = teams_padded[i]
                for i in range(5): row[f"Player {i + 1}"] = players_padded[i]
                rows.append(row)

            st.table(rows)
        else:
            pre_t = get_pre_tournament_picks(selected_email)
            if not pre_t:
                st.info("No picks found for this user.")
            else:
                # Vertical Stacking of Categories
                st.markdown("#### 🛡️ Pre-t Teams")
                # Grouping teams into rows of 3
                teams = pre_t.get("teams", [])
                for i in range(0, len(teams), 3):
                    cols = st.columns(3)
                    for j, col in enumerate(cols):
                        if i + j < len(teams):
                            # Display Name as metric, Points as label with border
                            with col.container(border=True):
                                st.metric(label=teams[i+j], value=None)
                                st.caption(f"Not played yet")

                st.markdown("#### 👤 Pre-t Players")
                # Grouping players into rows of 5
                players = pre_t.get("players", [])
                if players:
                    cols = st.columns(len(players))
                    for j, col in enumerate(cols):
                        if j < len(players):
                            name = players[j].get('name', players[j]) if isinstance(players[j], dict) else players[j]
                            # Display Name as metric, Points as label with border
                            with col.container(border=True):
                                st.metric(label=name, value=None)
                                st.caption(f"Not played yet")

    elif view_type == "Daily Predictions":
        # 3. Date Selection (Multiple)
        all_matches = get_scheduled_matches()
        available_dates = sorted(list(set([datetime.fromisoformat(m.get("kickoff_time", "")).astimezone(PT).strftime("%Y-%m-%d") for m in all_matches.values()])))
        
        selected_dates = st.multiselect("Select Dates:", options=available_dates, placeholder="Select dates ...",)

        if not selected_dates:
            return

        if selected_key == "All":
            st.subheader("📊 Aggregated Daily Predictions")
            all_users = get_all_users()
            
            rows = []
            for email, u in all_users.items():
                if "admin" in u.get("name", "").lower(): continue
                
                row = {"User": u.get("name", email)}
                
                # Fetch data for selected dates
                for date in selected_dates:
                    preds = get_authorized_predictions(email, date, viewer_email, is_admin)
                    teams_map = preds.get("teams", {})
                    players = preds.get("players", [])
                    
                    # Matches for this date
                    date_matches = [m for m in all_matches.values() 
                                    if datetime.fromisoformat(m.get("kickoff_time", "")).astimezone(PT).strftime("%Y-%m-%d") == date]
                    
                    for match in date_matches:
                        match_id = match.get('id')
                        match_name = f"{match.get('home_team')} vs {match.get('away_team')}"
                        row[f"{match_name}"] = teams_map.get(match_id, "-")
                    
                    # Players
                    for i in range(2):
                        p_name = players[i].get('name', players[i]) if i < len(players) and isinstance(players[i], dict) else (players[i] if i < len(players) else "-")
                        row[f"Player {i+1}"] = p_name
                
                rows.append(row)
            
            if rows: st.table(rows)
            return

        else:
            # 4. Performance Category Selection
            perf_category = st.pills("Select View:", options=["Team", "Player"], selection_mode="single")

            if not perf_category:
                return

            # Pre-calculate available matches/players for the selected dates
            matches_in_range = []
            for match_id, match in all_matches.items():
                dt_str = datetime.fromisoformat(match.get("kickoff_time", "")).astimezone(PT).strftime("%Y-%m-%d")
                if dt_str in selected_dates:
                    matches_in_range.append((match_id, match, dt_str))

            if perf_category == "Team":
                # 5. Match Filter
                match_options = {m_id: f"{m.get('home_team')} vs {m.get('away_team')} ({d})" for m_id, m, d in matches_in_range}
                selected_match_ids = st.multiselect("Select Matches:", options=list(match_options.keys()), format_func=lambda x: match_options[x])

                # Rendering Team Performance Cards
                for date in selected_dates:
                    st.markdown(f"### Predictions for {date}")
                    preds = get_authorized_predictions(selected_email, date, viewer_email, is_admin)
                    if not preds:
                        st.warning(f"Data for {date} is locked or not available.")
                        continue

                    teams_map = preds.get("teams", {})
                    daily_players = preds.get("players", [])

                    # Prepare matches to be rendered
                    matches_to_render = []
                    for match_id, prediction in teams_map.items():
                        if selected_match_ids and match_id not in selected_match_ids:
                            continue
                        match_data = next((m for m_id, m, d in matches_in_range if m_id == match_id and d == date), None)
                        if match_data:
                            matches_to_render.append((match_id, match_data, prediction))

                    # Render in grid of 2
                    for i in range(0, len(matches_to_render), 2):
                        cols = st.columns(2)
                        for j, col in enumerate(cols):
                            if i + j < len(matches_to_render):
                                m_id, m_data, pred = matches_to_render[i+j]
                                with col:
                                    render_daily_prediction_card(selected_email, date, m_id, m_data, pred, daily_players, performance_view="Team")

            elif perf_category == "Player":
                # Rendering Player Performance Cards (Both players automatically)
                for date in selected_dates:
                    st.markdown(f"### Predictions for {date}")
                    preds = get_authorized_predictions(selected_email, date, viewer_email, is_admin)
                    if not preds:
                        st.warning(f"Data for {date} is locked or not available.")
                        continue

                    # Render player performance component
                    render_player_performance_view(selected_email, date, preds)
