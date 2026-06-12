"""Views collecting structured prediction data records with automated cutoff locks."""

from datetime import datetime, timedelta
import zoneinfo
import streamlit as st
from src.db_service import (
    get_pre_tournament_picks, save_pre_tournament_picks,
    get_daily_predictions, save_daily_predictions
)

def render_pre_tournament_section(email: str) -> None:
    """Collects permanent multi-input forms for tournament baseline selections."""
    st.subheader("🏆 1. Pre-Tournament Lock-Ins")
    st.caption("Select your baseline 2 Teams and 5 Players (with their team) for the entire tournament.")

    existing = get_pre_tournament_picks(email)
    existing_teams = existing.get("teams", ["", ""])
    # New format: [{'name': ..., 'team': ...}, ...]
    existing_players = existing.get("players", [{'name': '', 'team': ''} for _ in range(5)])

    # Ensure existing_players is a list of dictionaries even if fetched as strings from an old version
    processed_players = []
    for p in existing_players:
        if isinstance(p, dict):
            processed_players.append(p)
        else:
            # Handle potential legacy string data
            processed_players.append({'name': str(p) if p else '', 'team': ''})
    existing_players = processed_players

    while len(existing_teams) < 2: existing_teams.append("")
    while len(existing_players) < 5: existing_players.append({'name': '', 'team': ''})

    with st.form("pre_tournament_form"):
        st.markdown("**Predict 2 Teams:**")
        team_inputs = [st.text_input(f"Team {i+1}", value=existing_teams[i], key=f"pre_team_{i}") for i in range(2)]

        st.markdown("**Predict 5 Players (and their team):**")
        player_inputs = []
        for i in range(5):
            c1, c2 = st.columns(2)
            p_name = c1.text_input(f"Player {i+1} Name", value=existing_players[i].get('name', ''), key=f"pre_p_name_{i}")
            p_team = c2.text_input(f"Player {i+1} Team", value=existing_players[i].get('team', ''), key=f"pre_p_team_{i}")
            player_inputs.append({'name': p_name, 'team': p_team})

        if st.form_submit_button("Lock Pre-Tournament Entries"):
            team_list = [t.strip() for t in team_inputs if t.strip()]
            player_list = [p for p in player_inputs if p['name'].strip()]

            if len(team_list) != 2 or len(player_list) != 5:
                st.error("Validation Error: Please fill out all fields.")
                return

            save_pre_tournament_picks(email, team_list, player_list)
            st.success("Pre-tournament selections updated!")

from datetime import datetime, timedelta, timezone

def render_daily_predictions_section(email: str, raw_matches: dict) -> None:
    """Processes match predictions, filtering and locking by IST."""
    IST = zoneinfo.ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    st.subheader(f"📅 Daily Predictions - {today_ist.strftime('%A, %b %d')} (IST)")

    if not raw_matches:
        st.info("No matches scheduled.")
        return

    # Filter for today's matches (based on IST date)
    today_matches = []
    for m in raw_matches.values():
        kickoff_str = m.get("kickoff_time", "")
        if not kickoff_str: continue
        # Assume kickoff_time is in ISO format
        kickoff_dt = datetime.fromisoformat(kickoff_str).astimezone(IST)
        if kickoff_dt.date() == today_ist:
            today_matches.append(m)

    if not today_matches:
        st.info("No matches scheduled for today (IST).")
        return

    # 1. Handle date-based clearing
    existing = get_daily_predictions(email)
    submitted_at_str = existing.get("submitted_at", "")
    today_str = today_ist.strftime("%Y-%m-%d")

    if today_str not in submitted_at_str:
        existing_teams_map = {}
        existing_players = [{'name': '', 'team': ''} for _ in range(2)]
    else:
        existing_teams_map = existing.get("teams", {})
        existing_players = existing.get("players", [{'name': '', 'team': ''} for _ in range(2)])

    # Process existing_players to ensure they are dictionaries
    processed_players = []
    for p in existing_players:
        if isinstance(p, dict):
            processed_players.append(p)
        else:
            processed_players.append({'name': str(p) if p else '', 'team': ''})
    existing_players = processed_players

    # Fetch Pre-T picks
    pre_t_picks = get_pre_tournament_picks(email)
    pre_t_teams = pre_t_picks.get("teams", [])
    raw_pre_t_players = pre_t_picks.get("players", [])

    # Ensure pre_t_players are dictionaries
    pre_t_players = []
    for p in raw_pre_t_players:
        if isinstance(p, dict):
            pre_t_players.append(p)
        else:
            pre_t_players.append({'name': str(p) if p else '', 'team': ''})

    # Identify Pre-T players playing today
    active_pre_t_players = []
    playing_teams_today = set()
    for match in today_matches:
        playing_teams_today.add(match['home_team'])
        playing_teams_today.add(match['away_team'])

    for p in pre_t_players:
        if p.get('team') in playing_teams_today:
            active_pre_t_players.append(p)

    with st.form("daily_prediction_form"):
        st.markdown("#### ⚽ Match Predictions")

        selected_winners = {}

        for match in today_matches:
            match_id = match['id']
            home, away = match['home_team'], match['away_team']

            # Logic: If Pre-T team is playing, auto-lock
            is_pre_t_match = home in pre_t_teams or away in pre_t_teams

            # Automated Cutoff (15 mins prior to kickoff in IST)
            kickoff_dt = datetime.fromisoformat(match.get("kickoff_time", "")).astimezone(IST)
            is_locked = now_ist >= (kickoff_dt - timedelta(minutes=15))

            # Determine winner
            if is_pre_t_match:
                winner = home if home in pre_t_teams else away
                st.selectbox(f"🏆 {match.get('display_string')} (Pre-T Locked)", 
                             options=[winner], disabled=True, key=f"match_drop_{match_id}")
                selected_winners[match_id] = winner
            else:
                options = [home, away, "Draw"]
                current_pick = existing_teams_map.get(match_id, "Draw")
                if current_pick not in options: current_pick = "Draw"

                default_idx = options.index(current_pick)
                selected_winners[match_id] = st.selectbox(
                    f"🏆 {match.get('display_string')}",
                    options=options,
                    index=default_idx,
                    key=f"match_drop_{match_id}",
                    disabled=is_locked
                )

        st.markdown("---")
        st.markdown("#### 🏃‍♂️ Daily Player Picks")
        daily_player_inputs = []
        for i in range(2):
            # If an active Pre-T player is available, auto-fill and lock
            pre_t_player = active_pre_t_players[i] if i < len(active_pre_t_players) else None

            c1, c2 = st.columns(2)
            if pre_t_player:
                p_name = c1.text_input(f"Player {i+1} Name", value=pre_t_player.get('name', ''), disabled=True)
                p_team = c2.text_input(f"Player {i+1} Team", value=pre_t_player.get('team', ''), disabled=True)
                daily_player_inputs.append(pre_t_player)
            else:
                p_name = c1.text_input(f"Player {i+1} Name", value=existing_players[i].get('name', ''), key=f"daily_p_name_{i}")
                p_team = c2.text_input(f"Player {i+1} Team", value=existing_players[i].get('team', ''), key=f"daily_p_team_{i}")
                daily_player_inputs.append({'name': p_name, 'team': p_team})

        if st.form_submit_button("Submit Predictions", type="primary"):
            player_list = [p for p in daily_player_inputs if p['name'].strip()]
            save_daily_predictions(email, selected_winners, player_list)
            st.success("Predictions saved!")
            st.rerun()