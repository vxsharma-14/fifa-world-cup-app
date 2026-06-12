import streamlit as st
from datetime import datetime
import zoneinfo
from src.db_service import get_pre_tournament_picks, save_pre_tournament_picks

def render_tournament_setup(email: str) -> None:
    """Renders Pre-T entries, hiding the form after the IST cutoff."""
    IST = zoneinfo.ZoneInfo("Asia/Kolkata")
    CUTOFF = datetime(2026, 6, 14, 0, 15, tzinfo=IST)
    now_ist = datetime.now(IST)

    st.subheader("🏆 Pre-Tournament Lock-Ins")
    
    if now_ist > CUTOFF:
        st.error("The deadline for Pre-Tournament entries has passed.")
        return

    st.caption("Select your baseline 2 Teams and 5 Players (with their team) for the entire tournament.")

    existing = get_pre_tournament_picks(email)
    existing_teams = existing.get("teams", ["", ""])
    existing_players = existing.get("players", [{'name': '', 'team': ''} for _ in range(5)])

    # Ensure existing_players is a list of dictionaries
    processed_players = []
    for p in existing_players:
        if isinstance(p, dict):
            processed_players.append(p)
        else:
            processed_players.append({'name': str(p) if p else '', 'team': ''})
    existing_players = processed_players

    while len(existing_teams) < 2: existing_teams.append("")
    while len(existing_players) < 5: existing_players.append({'name': '', 'team': ''})

    with st.form("pre_tournament_form"):
        col_teams, col_players = st.columns([1, 3])
        
        with col_teams:
            st.markdown("**Predict 2 Teams:**")
            team_inputs = [st.text_input(f"Team {i+1}", value=existing_teams[i], key=f"pre_team_{i}") for i in range(2)]
        with col_players:
            st.markdown("**Predict 5 Players (and their team):**")
            player_inputs = []
            for i in range(5):
                # Compact player/team row with 2:1 ratio
                c_p1, c_p2 = st.columns([2, 1])
                p_name = c_p1.text_input(f"Player {i+1} Name", value=existing_players[i].get('name', ''), key=f"pre_p_name_{i}")
                p_team = c_p2.text_input(f"Player {i+1} Team", value=existing_players[i].get('team', ''), key=f"pre_p_team_{i}")
                player_inputs.append({'name': p_name, 'team': p_team})

        if st.form_submit_button("Lock Pre-Tournament Entries", type="primary"):
            team_list = [t.strip() for t in team_inputs if t.strip()]
            player_list = [p for p in player_inputs if p['name'].strip()]

            if len(team_list) != 2 or len(player_list) != 5:
                st.error("Validation Error: Please fill out all fields.")
                return

            save_pre_tournament_picks(email, team_list, player_list)
            st.success("Pre-tournament selections updated!")
