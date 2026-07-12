import streamlit as st
from datetime import datetime
from src.db_service import (
    get_all_roster_players,
    get_pre_tournament_picks,
    get_roster_player_team_map,
    save_pre_tournament_picks,
)
from src.pre_tournament import (
    DEFAULT_PRE_T_PHASE,
    format_team_name,
    PRE_T_BASELINE_CUTOFF,
    get_pre_t_change_window,
    is_pre_t_change_window_open,
    normalize_player_pick,
    normalize_team_key,
    normalize_team_pick,
)


def _resolve_phase(existing_phase: str, has_changed: bool, updated_phase: str) -> str:
    """Keeps the original phase unless the pick actually changed in the current window."""
    existing_phase = str(existing_phase).strip() or DEFAULT_PRE_T_PHASE
    return updated_phase if has_changed else existing_phase

def render_tournament_setup(email: str) -> None:
    """Renders Pre-T entries, hiding the form after the IST cutoff."""
    edit_phase = "Phase3"
    edit_window_open = is_pre_t_change_window_open(edit_phase)
    edit_window = get_pre_t_change_window(edit_phase)
    max_team_changes = int(edit_window.get("max_team_changes", 1))
    max_player_changes = int(edit_window.get("max_player_changes", 1))

    st.subheader("🏆 Pre-Tournament Lock-Ins")

    existing = get_pre_tournament_picks(email)
    existing_teams = [normalize_team_pick(team) for team in existing.get("teams", [])]
    existing_players = [normalize_player_pick(player) for player in existing.get("players", [])]

    while len(existing_teams) < 2:
        existing_teams.append(normalize_team_pick(""))
    while len(existing_players) < 5:
        existing_players.append(normalize_player_pick(""))

    now_pt = datetime.now(PRE_T_BASELINE_CUTOFF.tzinfo)

    if now_pt <= PRE_T_BASELINE_CUTOFF:
        st.caption("Select your baseline 2 Teams and 5 Players (with their team) for the entire tournament.")

        with st.form("pre_tournament_form"):
            col_teams, col_players = st.columns([1, 3])

            with col_teams:
                st.markdown("**Predict 2 Teams:**")
                team_inputs = [
                    st.text_input(
                        f"Team {i+1}",
                        value=existing_teams[i].get("name", ""),
                        key=f"pre_team_{i}",
                    )
                    for i in range(2)
                ]
            with col_players:
                st.markdown("**Predict 5 Players (and their team):**")
                player_inputs = []
                all_roster_players = get_all_roster_players()
                roster_player_team_map = get_roster_player_team_map()
                for i in range(5):
                    c_p1, c_p2 = st.columns([2, 1])
                    options = [""] + all_roster_players
                    current_name = existing_players[i].get("name", "")
                    idx = options.index(current_name) if current_name in options else 0
                    p_name = c_p1.selectbox(
                        f"Player {i+1} Name",
                        options=options,
                        index=idx,
                        key=f"pre_p_name_{i}",
                    )
                    p_team = roster_player_team_map.get(p_name, "")
                    c_p2.markdown(f"**{p_team or '-'}**")
                    player_inputs.append({'name': p_name, 'team': p_team})

            if st.form_submit_button("Lock Pre-Tournament Entries", type="primary"):
                team_list = [format_team_name(t) for t in team_inputs if t.strip()]
                player_list = [p for p in player_inputs if p["name"].strip()]

                if len(team_list) != 2 or len(player_list) != 5:
                    st.error("Validation Error: Please fill out all fields.")
                    return

                save_pre_tournament_picks(
                    email,
                    team_list,
                    player_list,
                    history_phase_key="phase1",
                    history_changed=False,
                    history_source="streamlit",
                )
                st.success("Pre-tournament selections updated!")
        return

    if not edit_window_open:
        st.error("The deadline for Pre-Tournament entries has passed.")
        return

    st.caption(
        f"{edit_phase} change window is open. You can update up to {max_team_changes} teams "
        f"and {max_player_changes} players."
    )
    st.caption("Players are selected from the roster and their team updates automatically.")

    with st.form(f"pre_tournament_{edit_phase.lower()}_form"):
        col_teams, col_players = st.columns([1, 3])

        with col_teams:
            st.markdown("**Update 2 Teams:**")
            team_inputs = [
                st.text_input(
                    f"Team {i+1}",
                    value=existing_teams[i].get("name", ""),
                    key=f"{edit_phase.lower()}_team_{i}",
                )
                for i in range(2)
            ]

        with col_players:
            st.markdown("**Update 5 Players:**")
            player_inputs = []
            all_roster_players = get_all_roster_players()
            roster_player_team_map = get_roster_player_team_map()
            for i in range(5):
                c_p1, c_p2 = st.columns([2, 1])
                options = [""] + all_roster_players
                current_name = existing_players[i].get("name", "")
                idx = options.index(current_name) if current_name in options else 0
                p_name = c_p1.selectbox(
                    f"Player {i+1} Name",
                    options=options,
                    index=idx,
                    key=f"{edit_phase.lower()}_p_name_{i}",
                )
                p_team = roster_player_team_map.get(p_name, "")
                c_p2.empty()
                player_inputs.append({'name': p_name, 'team': p_team})

        if st.form_submit_button(f"Save {edit_phase} Changes", type="primary"):
            normalized_team_inputs = [format_team_name(t) for t in team_inputs]
            if any(not team.strip() for team in normalized_team_inputs) or len([t for t in normalized_team_inputs if t.strip()]) != 2:
                st.error("Validation Error: Please provide both teams.")
                return

            selected_player_names = [p["name"].strip() for p in player_inputs]
            if any(not name for name in selected_player_names) or len([name for name in selected_player_names if name]) != 5:
                st.error("Validation Error: Please select all 5 players.")
                return

            team_changes = sum(
                normalize_team_key(existing_team.get("name", "")) != normalize_team_key(updated_team)
                for existing_team, updated_team in zip(existing_teams, normalized_team_inputs)
            )
            player_changes = sum(
                str(existing_players[i].get("name", "")).strip() != selected_player_names[i]
                for i in range(5)
            )

            if team_changes > max_team_changes or player_changes > max_player_changes:
                st.error(
                    f"Validation Error: You can change at most {max_team_changes} teams "
                    f"and {max_player_changes} players."
                )
                return

            updated_teams = []
            for existing_team, updated_team in zip(existing_teams, normalized_team_inputs):
                changed = normalize_team_key(existing_team.get("name", "")) != normalize_team_key(updated_team)
                phase = _resolve_phase(existing_team.get("phase", DEFAULT_PRE_T_PHASE), changed, edit_phase)
                updated_teams.append({
                    "name": updated_team,
                    "phase": phase,
                })

            updated_players = []
            for i, player in enumerate(player_inputs):
                existing_player = existing_players[i]
                existing_name = str(existing_player.get("name", "")).strip()
                updated_name = player["name"].strip()
                changed = existing_name != updated_name
                phase = _resolve_phase(existing_player.get("phase", DEFAULT_PRE_T_PHASE), changed, edit_phase)
                updated_players.append({
                    "name": updated_name,
                    "team": (
                        player["team"].strip().title()
                        if changed
                        else str(existing_player.get("team", "")).strip().title()
                    ),
                    "phase": phase,
                })

            save_pre_tournament_picks(
                email,
                updated_teams,
                updated_players,
                history_phase_key=edit_phase,
                history_changed=bool(team_changes or player_changes),
                history_source="streamlit",
            )
            st.success(f"{edit_phase} pre-tournament selections updated!")
