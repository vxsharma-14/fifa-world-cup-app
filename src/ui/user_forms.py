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
    st.caption("Select your baseline 2 Teams and 5 Players for the entire tournament.")

    existing = get_pre_tournament_picks(email)
    existing_teams = existing.get("teams", ["", ""])
    existing_players = existing.get("players", ["", "", "", "", ""])

    while len(existing_teams) < 2: existing_teams.append("")
    while len(existing_players) < 5: existing_players.append("")

    with st.form("pre_tournament_form"):
        st.markdown("**Predict 2 Teams:**")
        team_inputs = [st.text_input(f"Team {i+1}", value=existing_teams[i], key=f"pre_team_{i}") for i in range(2)]

        st.markdown("**Predict 5 Players:**")
        player_inputs = [st.text_input(f"Player {i+1}", value=existing_players[i], key=f"pre_player_{i}") for i in range(5)]

        if st.form_submit_button("Lock Pre-Tournament Entries"):
            team_list = [t.strip() for t in team_inputs if t.strip()]
            player_list = [p.strip() for p in player_inputs if p.strip()]

            if len(team_list) != 2 or len(player_list) != 5:
                st.error("Validation Error: Please fill out all fields.")
                return

            save_pre_tournament_picks(email, team_list, player_list)
            st.success("Pre-tournament selections updated!")

def render_daily_predictions_section(email: str, raw_matches: dict) -> None:
    """Processes match predictions with automated 15-minute chronological locks."""
    st.subheader("📅 2. Today's Predictions Dashboard")

    if not raw_matches:
        st.info("Awaiting today's match configurations from the administrator.")
        return

    existing = get_daily_predictions(email)
    existing_teams_map = existing.get("teams", {})
    existing_players = existing.get("players", ["", ""])

    while len(existing_players) < 2: existing_players.append("")

    # Get current time in Indian Standard Time (IST)
    current_time = datetime.now(zoneinfo.ZoneInfo("Asia/Kolkata"))

    with st.form("daily_prediction_form"):
        st.markdown("#### ⚽ Match Winner Selection Matrix")
        st.caption("Picks lock automatically 15 minutes prior to each match's scheduled kickoff.")

        selected_winners = {}
        all_matches_locked = True  # Tracks if we should disable the main submit button

        # Sort incoming structured dict matches chronologically
        sorted_matches = sorted(raw_matches.values(), key=lambda x: x.get("kickoff_time", ""))

        for idx, match in enumerate(sorted_matches):
            match_id = match.get("id", f"match_{idx+1}")
            home = match.get("home_team", "Home")
            away = match.get("away_team", "Away")
            kickoff_iso = match.get("kickoff_time", "")

            options = [home, away, "Draw"]

            # Match specific default indexing
            default_idx = 0
            saved_pick = existing_teams_map.get(match_id)
            if saved_pick in options:
                default_idx = options.index(saved_pick)

            # --- Automated Cutoff Calculation ---
            is_locked = False
            lock_reason = ""
            if kickoff_iso:
                kickoff_dt = datetime.fromisoformat(kickoff_iso)
                cutoff_dt = kickoff_dt - timedelta(minutes=15)

                if current_time >= cutoff_dt:
                    is_locked = True
                    lock_reason = " 🔒 (Locked - Cutoff Passed)"
                else:
                    all_matches_locked = False # At least one match is still open

            # Label displays cleanly with dynamic lock status
            label_text = f"🏆 {match.get('display_string', f'{home} vs {away}')}{lock_reason}"

            chosen_winner = st.selectbox(
                label_text,
                options=options,
                index=default_idx,
                key=f"match_drop_{match_id}",
                disabled=is_locked  # Freezes the input box if past cutoff time
            )

            # If it's locked, retain the previously saved pick (or default to fallback)
            if is_locked and saved_pick:
                selected_winners[match_id] = saved_pick
            else:
                selected_winners[match_id] = chosen_winner

        st.markdown("---")
        st.markdown("#### 🏃‍♂️ Daily Player Picks")

        daily_player_inputs = []
        for i in range(2):
            player_in = st.text_input(
                f"Daily Player {i+1}",
                value=existing_players[i],
                key=f"daily_player_{i}",
                disabled=all_matches_locked # Locks player entries if all matches for the day have started
            )
            daily_player_inputs.append(player_in)

        # Form submit configuration
        submit_btn = st.form_submit_button(
            "Submit Dashboard Predictions",
            disabled=all_matches_locked
        )

        if submit_btn:
            player_list = [p.strip() for p in daily_player_inputs if p.strip()]

            if len(player_list) != 2:
                st.error("Validation Error: Please make sure both Daily Player text boxes are filled out.")
                return

            save_daily_predictions(email, selected_winners, player_list)
            st.success("Your predictions have been securely synced to the database!")