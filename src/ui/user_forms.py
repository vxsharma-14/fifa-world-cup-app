"""Views collecting structured prediction data records with automated cutoff locks."""

from datetime import datetime, timedelta, timezone
import zoneinfo
import streamlit as st
from src.db_service import (
    get_pre_tournament_picks, save_pre_tournament_picks,
    get_daily_predictions, save_daily_predictions
)

def render_daily_predictions_section(email: str, raw_matches: dict) -> None:
    """Processes upcoming match predictions, filtering out graded matches and locking by IST."""
    IST = zoneinfo.ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(IST)
    
    st.subheader("📅 Predictions Dashboard")

    if not raw_matches:
        st.info("No matches scheduled.")
        return

    # Filter for active/incomplete matches
    from src.db_service import get_match_results
    existing_results = get_match_results()
    
    active_matches = []
    for m in raw_matches.values():
        if m['id'] not in existing_results:
            active_matches.append(m)

    if not active_matches:
        st.info("No active matches to predict.")
        return

    # Sort matches chronologically
    active_matches = sorted(active_matches, key=lambda x: x.get("kickoff_time", ""))

    # 1. Handle clearing (generic reset)
    existing = get_daily_predictions(email)
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

    # Identify Pre-T players involved in active matches
    active_pre_t_players = []
    playing_teams_active = set()
    for match in active_matches:
        playing_teams_active.add(match['home_team'])
        playing_teams_active.add(match['away_team'])

    for p in pre_t_players:
        if p.get('team') in playing_teams_active:
            active_pre_t_players.append(p)

    with st.form("daily_prediction_form"):
        col_m, col_p = st.columns([1, 3])
        
        with col_m:
            st.markdown("#### ⚽ Match Predictions")
            selected_winners = {}
            for match in active_matches:
                match_id = match['id']
                home, away = match['home_team'], match['away_team']
                
                # Compact display string
                kickoff_dt = datetime.fromisoformat(match.get("kickoff_time", "")).astimezone(IST)
                display_label = f"{kickoff_dt.strftime('%b %d, %I:%M %p')} | {home} vs {away}"
                
                # Logic: If Pre-T team is playing, auto-lock
                is_pre_t_match = home in pre_t_teams or away in pre_t_teams
                
                # Automated Cutoff (15 mins prior to kickoff in IST)
                is_locked = now_ist >= (kickoff_dt - timedelta(minutes=15))
                
                # Determine winner
                if is_pre_t_match:
                    winner = home if home in pre_t_teams else away
                    st.selectbox(f"🏆 {display_label} (Pre-T Locked)", 
                                 options=[winner], disabled=True, key=f"match_drop_{match_id}", label_visibility="collapsed")
                    selected_winners[match_id] = winner
                else:
                    options = [home, away, "Draw"]
                    current_pick = existing_teams_map.get(match_id, "Draw")
                    if current_pick not in options: current_pick = "Draw"
                    
                    default_idx = options.index(current_pick)
                    selected_winners[match_id] = st.selectbox(
                        display_label,
                        options=options,
                        index=default_idx,
                        key=f"match_drop_{match_id}",
                        disabled=is_locked,
                        label_visibility="visible"
                    )
        with col_p:
            st.markdown("#### 🏃‍♂️ Daily Player Picks")
            daily_player_inputs = []
            for i in range(2):
                # If an active Pre-T player is available, auto-fill and lock
                pre_t_player = active_pre_t_players[i] if i < len(active_pre_t_players) else None
                
                c1, c2 = st.columns([2, 1])
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
