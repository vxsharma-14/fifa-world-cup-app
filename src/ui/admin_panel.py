"""Administrative panels handling internal settings, match scheduling, and results scoring."""

import streamlit as st
from datetime import datetime, time
import zoneinfo
from src.db_service import (
    get_scheduled_matches, save_structured_match,
    delete_all_matches, save_match_result, get_match_results
)

def render_admin_dashboard() -> None:
    """Renders structured scheduling calendars, match grading forms, and support tools."""
    st.header("👑 Admin Command Center")

    # -------------------------------------------------------------
    # 1. MATCH SCHEDULER
    # -------------------------------------------------------------
    st.subheader("📅 Master Calendar Match Scheduler")
    with st.form("match_scheduler_form", clear_on_submit=True):
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            home_team = st.text_input("Home Team Name (e.g., Mexico)").strip()
        with col_t2:
            away_team = st.text_input("Away Team Name (e.g., South Africa)").strip()

        col_d, col_t = st.columns(2)
        with col_d:
            match_date = st.date_input("Match Date", datetime.now().date())
        with col_t:
            match_time = st.time_input("Kickoff Time (IST)", time(12, 00))

        if st.form_submit_button("➕ Add Match to Master Calendar"):
            if not home_team or not away_team:
                st.error("Please provide both team names.")
            else:
                combined_dt = datetime.combine(match_date, match_time)
                ist_dt = combined_dt.replace(tzinfo=zoneinfo.ZoneInfo("Asia/Kolkata"))
                kickoff_iso = ist_dt.isoformat()

                timestamp_str = ist_dt.strftime("%I:%M %p")
                display_str = f"{timestamp_str} | {home_team} vs {away_team}"
                match_id = f"match_{int(datetime.now().timestamp())}"

                save_structured_match(match_id, home_team, away_team, kickoff_iso, display_str)
                st.success(f"Successfully scheduled: {display_str}")
                st.rerun()

    st.markdown("---")

    # Fetch active data states
    current_time = datetime.now(zoneinfo.ZoneInfo("Asia/Kolkata"))
    current_matches = get_scheduled_matches()
    existing_results = get_match_results()

    upcoming_admin_list = []
    completed_admin_list = []

    if isinstance(current_matches, dict):
        for match in current_matches.values():
            kickoff_iso = match.get("kickoff_time", "")
            if kickoff_iso:
                kickoff_dt = datetime.fromisoformat(kickoff_iso)
                if current_time >= kickoff_dt:
                    completed_admin_list.append(match)
                else:
                    upcoming_admin_list.append(match)
            else:
                upcoming_admin_list.append(match)

    # -------------------------------------------------------------
    # 2. UPCOMING MATCHES VIEW
    # -------------------------------------------------------------
    st.markdown("#### ⏳ Upcoming Scheduled Matches")
    if not upcoming_admin_list:
        st.info("No upcoming matches on the calendar.")
    else:
        sorted_upcoming = sorted(upcoming_admin_list, key=lambda x: x.get("kickoff_time", ""))
        for m in sorted_upcoming:
            dt_obj = datetime.fromisoformat(m["kickoff_time"])
            formatted_date = dt_obj.strftime("%A, %b %d")
            st.text(f"• [{formatted_date}] {m.get('display_string')}")

        if st.button("🗑️ Clear Entire Match Schedule", type="primary"):
            delete_all_matches()
            st.success("All matches wiped out from the database configuration node.")
            st.rerun()

    st.markdown("---")

    # -------------------------------------------------------------
    # 3. RESULTS & GRADING ENGINE (New Feature)
    # -------------------------------------------------------------
    st.subheader("⚽ Match Results & Grading Center")
    st.caption("Submit stats for completed matches to log data points for leaderboard score distribution.")

    if not completed_admin_list:
        st.info("No completed matches found on the timeline to grade.")
    else:
        # Build a selection dropdown dictionary for completed matches
        sorted_completed = sorted(completed_admin_list, key=lambda x: x.get("kickoff_time", ""))
        match_options = {m["id"]: m["display_string"] for m in sorted_completed}

        selected_match_id = st.selectbox(
            "Select completed match to submit/update results:",
            options=list(match_options.keys()),
            format_func=lambda x: match_options[x]
        )

        # Pull selected match details
        selected_match = next(m for m in sorted_completed if m["id"] == selected_match_id)
        home = selected_match.get("home_team")
        away = selected_match.get("away_team")

        # Visual indicator if the match has already been graded previously
        if selected_match_id in existing_results:
            st.warning("⚠️ This match has already been graded. Submitting again will overwrite historical stats.")
            match_data = existing_results[selected_match_id]
        else:
            match_data = {}

        # Render explicit statistical entry form fields
        with st.form("results_entry_form"):
            st.markdown(f"### Scoreboard: **{home}** vs **{away}**")

            c_sc1, c_sc2 = st.columns(2)
            with c_sc1:
                home_score = st.number_input(f"{home} Goals", min_value=0, value=int(match_data.get("home_score", 0)), step=1)
            with c_sc2:
                away_score = st.number_input(f"{away} Goals", min_value=0, value=int(match_data.get("away_score", 0)), step=1)

            # Automatically evaluate the winning team node
            if home_score > away_score:
                winner_prediction_value = home
            elif away_score > home_score:
                winner_prediction_value = away
            else:
                winner_prediction_value = "Draw"

            st.info(f"👉 **Determined Outcome:** {winner_prediction_value}")

            st.markdown("---")
            st.markdown("##### 🏃‍♂️ Match Metrics & Event Logs")
            st.caption("Separate multiple player names using commas (e.g., Messi, Neymar). Leave empty if none.")

            # Set up list string fields comma-separated string formatting text fallbacks
            def join_list(l): return ", ".join(l) if l else ""

            home_scorers_raw = st.text_input(f"Goal Scorers for {home}:", value=join_list(match_data.get("home_scorers", [])))
            away_scorers_raw = st.text_input(f"Goal Scorers for {away}:", value=join_list(match_data.get("away_scorers", [])))

            st.markdown(" ")
            yellow_cards_raw = st.text_input("Players Booked (Yellow Cards):", value=join_list(match_data.get("yellow_cards", [])))
            red_cards_raw = st.text_input("Players Sent Off (Red Cards):", value=join_list(match_data.get("red_cards", [])))

            st.markdown(" ")
            motm_player = st.text_input("FIFA Official Man of the Match:", value=match_data.get("player_of_the_match", "")).strip()

            if st.form_submit_button("💾 Finalize & Save Match Results"):
                # Clean and parse text strings into structured lists
                def parse_input(raw_str): return [p.strip() for p in raw_str.split(",") if p.strip()]

                final_results = {
                    "match_id": selected_match_id,
                    "home_score": home_score,
                    "away_score": away_score,
                    "winning_team": winner_prediction_value,
                    "home_scorers": parse_input(home_scorers_raw),
                    "away_scorers": parse_input(away_scorers_raw),
                    "yellow_cards": parse_input(yellow_cards_raw),
                    "red_cards": parse_input(red_cards_raw),
                    "player_of_the_match": motm_player
                }

                save_match_result(selected_match_id, final_results)
                st.success(f"Results for match locked in successfully!")
                st.rerun()

    # -------------------------------------------------------------
    # 5. PARTICIPANTS OVERVIEW
    # -------------------------------------------------------------
    st.markdown("---")
    st.subheader("👥 Participants Overview")
    
    from src.db_service import get_all_users, get_pre_tournament_picks, get_daily_predictions
    
    all_users = get_all_users()
    
    if not all_users:
        st.info("No participants found.")
    else:
        # Create a dataframe or list of data to display
        participant_data = []
        for email, user_info in all_users.items():
            # Filter out admins
            if "admin" in user_info.get("name", "").lower():
                continue
                
            pre_t = get_pre_tournament_picks(email)
            daily = get_daily_predictions(email)
            
            # Format daily match picks
            match_picks = daily.get("teams", {})
            # Extract just the team name
            match_picks_str = ", ".join([f"{v}" for v in match_picks.values()])
            
            participant_data.append({
                "Name": user_info.get("name"),
                "Pre-T Teams": ", ".join(pre_t.get("teams", [])),
                "Pre-T Players": ", ".join(pre_t.get("players", [])),
                "Daily Players": ", ".join(daily.get("players", [])),
                "Daily Match Picks": match_picks_str
            })
            
        import pandas as pd
        if participant_data:
            st.table(pd.DataFrame(participant_data))
        else:
            st.info("No non-admin participants found.")

    # -------------------------------------------------------------
    # 4. COMPLETED ARCHIVE REFERENCE
    # -------------------------------------------------------------
    if completed_admin_list:
        st.markdown(" ")
        with st.expander("✅ View Completed Matches Timeline Reference", expanded=False):
            for m in sorted_completed:
                dt_obj = datetime.fromisoformat(m["kickoff_time"])
                formatted_date = dt_obj.strftime("%b %d")
                status = "📝 Graded" if m["id"] in existing_results else "⏳ Missing Results"
                st.markdown(f"🏁 **[{formatted_date}] {m.get('display_string')}** — `{status}`")

    st.markdown("---")
    st.subheader("💬 User Prediction Overrides (WhatsApp Backdoor)")
    st.caption("Manually adjust or insert entries for friends who submitted via WhatsApp due to platform delays.")

    from src.db_service import get_all_users, save_user_daily_override, get_daily_predictions
    import firebase_admin.db as fdb

    all_users = get_all_users()

    if not all_users:
        st.info("No registered users found to override.")
    elif not current_matches:
        st.info("No matches scheduled to map predictions against.")
    else:
        # 1. Global User Picker
        user_options = {u["email"]: f"{u['name']} ({u['email']})" for u in all_users.values()}
        selected_user_email = st.selectbox(
            "👉 Select the Friend to Modify:",
            options=list(user_options.keys()),
            format_func=lambda x: user_options[x],
            key="override_user_select"
        )

        # Pull all current daily data for this specific user up front to use as safe states
        user_existing_daily = get_daily_predictions(selected_user_email)
        user_existing_teams = user_existing_daily.get("teams", {})
        user_existing_players = user_existing_daily.get("players", ["", ""])
        while len(user_existing_players) < 2: user_existing_players.append("")

        # Create two separate workspace columns to isolate match choices from player lists
        col_match, col_player = st.columns(2, gap="large")

        # -----------------------------------------------------------------
        # COLUMN 1: ISOLATED MATCH-WINNER OVERRIDE FORM
        # -----------------------------------------------------------------
        with col_match:
            st.markdown("##### ⚽ Part A: Override Specific Match Pick")
            st.caption("This updates ONE specific match winner without touching player data.")

            all_matches_sorted = sorted(current_matches.values(), key=lambda x: x.get("kickoff_time", ""))
            match_options_map = {m["id"]: m["display_string"] for m in all_matches_sorted}

            selected_match_override_id = st.selectbox(
                "Select the Target Match:",
                options=list(match_options_map.keys()),
                format_func=lambda x: match_options_map[x],
                key="override_match_select"
            )

            target_match = next(m for m in all_matches_sorted if m["id"] == selected_match_override_id)
            home = target_match.get("home_team", "Home")
            away = target_match.get("away_team", "Away")

            saved_override_pick = user_existing_teams.get(selected_match_override_id)
            team_options = [home, away, "Draw"]
            default_team_idx = team_options.index(saved_override_pick) if saved_override_pick in team_options else 0

            with st.form("whatsapp_match_override_form"):
                chosen_winner = st.selectbox(
                    f"Predicted Outcome for {home} vs {away}:",
                    options=team_options,
                    index=default_team_idx
                )

                if st.form_submit_button("💾 Force Update This Match Selection"):
                    # Safe update: Fetch current, insert single winner key, push back
                    cleaned_email = selected_user_email.replace(".", "_")
                    ref = fdb.reference(f"daily_predictions/{cleaned_email}")

                    user_existing_teams[selected_match_override_id] = chosen_winner

                    ref.update({
                        "teams": user_existing_teams,
                        "submitted_at": f"{datetime.now().strftime('%Y-%m-%d %I:%M %p')} (Admin Match Override)"
                    })
                    st.success(f"Match selection updated safely for {selected_user_email}!")
                    st.rerun()

        # -----------------------------------------------------------------
        # COLUMN 2: ISOLATED GLOBAL DAILY PLAYER OVERRIDE FORM
        # -----------------------------------------------------------------
        with col_player:
            st.markdown("##### 🏃‍♂️ Part B: Override Daily Player Lock-Ins")
            st.caption("This modifies the user's 2 global player picks for the entire matchday.")

            with st.form("whatsapp_player_override_form"):
                p1 = st.text_input("Daily Player Pick 1:", value=user_existing_players[0])
                p2 = st.text_input("Daily Player Pick 2:", value=user_existing_players[1])

                if st.form_submit_button("🚀 Force Update Daily Players"):
                    cleaned_players = [p.strip() for p in [p1, p2] if p.strip()]
                    if len(cleaned_players) != 2:
                        st.error("Validation Error: Both text boxes must contain a valid player name.")
                        return

                    cleaned_email = selected_user_email.replace(".", "_")
                    ref = fdb.reference(f"daily_predictions/{cleaned_email}")

                    ref.update({
                        "players": cleaned_players,
                        "submitted_at": f"{datetime.now().strftime('%Y-%m-%d %I:%M %p')} (Admin Player Override)"
                    })
                    st.success(f"Daily player choices successfully locked for {selected_user_email}!")
                    st.rerun()