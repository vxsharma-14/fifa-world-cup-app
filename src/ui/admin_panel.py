"""Administrative panels handling internal settings, match scheduling, and results scoring."""

import streamlit as st
from datetime import datetime, time
import zoneinfo
from src.db_service import (
    get_scheduled_matches, save_structured_match,
    delete_all_matches, save_match_result, get_match_results
)
from src.ui.leaderboard import render_leaderboard_table

def render_admin_dashboard() -> None:
    """Renders structured scheduling calendars, match grading forms, and support tools."""
    st.header("👑 Admin Command Center")

    # Fetch active data states
    current_time = datetime.now(zoneinfo.ZoneInfo("Asia/Kolkata"))
    current_matches = get_scheduled_matches()
    
    # Re-map results from the metadata for UI backward compatibility
    existing_results = {
        m_id: m.get("results", {}) 
        for m_id, m in current_matches.items() 
        if m.get("status") == "completed"
    }

    upcoming_admin_list = []
    completed_admin_list = []

    if isinstance(current_matches, dict):
        for match in current_matches.values():
            kickoff_iso = match.get("kickoff_time", "")
            # Determine if completed based on status flag or kickoff time
            is_completed = match.get("status") == "completed"
            
            if is_completed or (kickoff_iso and current_time >= datetime.fromisoformat(kickoff_iso)):
                completed_admin_list.append(match)
            else:
                upcoming_admin_list.append(match)

    tab_sched, tab_grade, tab_part, tab_override, tab_leaderboard = st.tabs([
        "📅 Matches & Scheduling", 
        "⚽ Results & Grading", 
        "👥 Participants", 
        "💬 Overrides",
        "🏆 Leaderboard"
    ])

    # -------------------------------------------------------------
    # TAB 1: MATCH SCHEDULER
    # -------------------------------------------------------------
    with tab_sched:
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
        st.markdown("#### ⏳ Upcoming Scheduled Matches")
        if not upcoming_admin_list:
            st.info("No upcoming matches on the calendar.")
        else:
            sorted_upcoming = sorted(upcoming_admin_list, key=lambda x: x.get("kickoff_time", ""))
            for m in sorted_upcoming:
                dt_obj = datetime.fromisoformat(m["kickoff_time"])
                formatted_date = dt_obj.strftime("%A, %b %d")
                st.text(f"• [{formatted_date}] {m.get('display_string')}")

        if completed_admin_list:
            st.markdown("---")
            with st.expander("✅ View Completed Matches Timeline Reference", expanded=False):
                sorted_completed = sorted(completed_admin_list, key=lambda x: x.get("kickoff_time", ""))
                for m in sorted_completed:
                    dt_obj = datetime.fromisoformat(m["kickoff_time"])
                    formatted_date = dt_obj.strftime("%b %d")
                    status = "📝 Graded" if m["id"] in existing_results else "⏳ Missing Results"
                    st.markdown(f"🏁 **[{formatted_date}] {m.get('display_string')}** — `{status}`")

    # -------------------------------------------------------------
    # TAB 2: RESULTS & GRADING ENGINE
    # -------------------------------------------------------------
    with tab_grade:
        st.subheader("⚽ Match Results & Grading Center")
        if not completed_admin_list:
            st.info("No completed matches found to grade.")
        else:
            sorted_completed = sorted(completed_admin_list, key=lambda x: x.get("kickoff_time", ""))
            for m in sorted_completed:
                m_id = m["id"]
                m_data = existing_results.get(m_id, {})
                home, away = m["home_team"], m["away_team"]
                
                # Summary display
                dt = datetime.fromisoformat(m["kickoff_time"])
                date_str = dt.strftime("%d/%m")
                time_str = dt.strftime("%I:%M %p")
                
                # Determine button label and status
                has_results = m_id in existing_results
                btn_label = "Edit Results" if has_results else "Add Results"
                
                with st.expander(f"{date_str} {time_str} | {home} vs {away} {'✅' if has_results else '⏳'}"):
                    with st.form(f"form_{m_id}"):
                        # 1. Score
                        c_s1, c_s2 = st.columns(2)
                        h_score = c_s1.number_input("Home Goals", min_value=0, value=int(m_data.get("home_score", 0)), step=1)
                        a_score = c_s2.number_input("Away Goals", min_value=0, value=int(m_data.get("away_score", 0)), step=1)

                        # 2. Metrics (Dynamic Rows)
                        s_key = f'scorer_rows_{m_id}'
                        c_key = f'card_rows_{m_id}'
                        if s_key not in st.session_state: 
                            st.session_state[s_key] = [{'team': home, 'name': n, 'goals': 1} for n in m_data.get('home_scorers', [])] + [{'team': away, 'name': n, 'goals': 1} for n in m_data.get('away_scorers', [])] or [{'team': home, 'name': '', 'goals': 1}]
                        if c_key not in st.session_state: 
                            st.session_state[c_key] = [{'team': home, 'name': n, 'type': 'Yellow'} for n in m_data.get('yellow_cards', [])] + [{'team': home, 'name': n, 'type': 'Red'} for n in m_data.get('red_cards', [])] or [{'team': home, 'name': '', 'type': 'Yellow'}]

                        st.markdown("##### Goal Scorers")
                        for i, row in enumerate(st.session_state[s_key]):
                            c1, c2, c3 = st.columns([2, 2, 1])
                            row['team'] = c1.selectbox("Team", [home, away], index=[home, away].index(row['team']) if row['team'] in [home, away] else 0, key=f"st_{m_id}_{i}")
                            row['name'] = c2.text_input("Player", value=row['name'], key=f"sn_{m_id}_{i}")
                            row['goals'] = c3.number_input("Goals", min_value=1, value=row.get('goals', 1), key=f"sg_{m_id}_{i}")
                        if st.form_submit_button("➕ Add Scorer"): 
                            st.session_state[s_key].append({'team': home, 'name': '', 'goals': 1})
                            st.rerun()

                        st.markdown("##### Discipline (Cards)")
                        for i, row in enumerate(st.session_state[c_key]):
                            c1, c2, c3 = st.columns([2, 2, 1])
                            row['team'] = c1.selectbox("Team", [home, away], index=[home, away].index(row['team']) if row['team'] in [home, away] else 0, key=f"ct_{m_id}_{i}")
                            row['name'] = c2.text_input("Player", value=row['name'], key=f"cn_{m_id}_{i}")
                            row['type'] = c3.selectbox("Type", ["Yellow", "Red"], index=["Yellow", "Red"].index(row['type']) if row['type'] in ["Yellow", "Red"] else 0, key=f"cty_{m_id}_{i}")
                        if st.form_submit_button("➕ Add Card"): 
                            st.session_state[c_key].append({'team': home, 'name': '', 'type': 'Yellow'})
                            st.rerun()

                        motm = st.text_input("Man of the Match:", value=m_data.get("player_of_the_match", "")).strip()

                        if st.form_submit_button(btn_label, type="primary"):
                            h_scorers, a_scorers, yellow, red = [], [], [], []
                            for r in st.session_state[s_key]:
                                if r['name']:
                                    if r['team'] == home: h_scorers.extend([r['name']] * r['goals'])
                                    else: a_scorers.extend([r['name']] * r['goals'])
                            for r in st.session_state[c_key]:
                                if r['name']:
                                    if r['type'] == "Yellow": yellow.append(r['name'])
                                    else: red.append(r['name'])

                            save_match_result(m_id, {
                                "match_id": m_id, 
                                "home_score": h_score, 
                                "away_score": a_score,
                                "winning_team": home if h_score > a_score else (away if a_score > h_score else "Draw"), 
                                "home_scorers": h_scorers,
                                "away_scorers": a_scorers,
                                "yellow_cards": yellow,
                                "red_cards": red, 
                                "player_of_the_match": motm
                            })
                            # Clear session state for next edit
                            del st.session_state[s_key]
                            del st.session_state[c_key]
                            st.success(f"Results for {home} vs {away} saved!")
                            st.rerun()

    # -------------------------------------------------------------
    # TAB 3: PARTICIPANTS
    # -------------------------------------------------------------
    with tab_part:
        st.subheader("👥 Participants Overview")
        from src.db_service import get_all_users, get_pre_tournament_picks, get_daily_predictions
        all_users = get_all_users()
        if not all_users:
            st.info("No participants found.")
        else:
            participant_data = []
            def _extract_name(p):
                if isinstance(p, dict):
                    return str(p.get('name', ''))
                return str(p)

            for email, user_info in all_users.items():
                # Ensure user_info is a dict
                if not isinstance(user_info, dict): continue
                
                # Safely extract name
                name = user_info.get("name", "")
                if not isinstance(name, str): name = str(name)
                
                if "admin" in name.lower(): continue
                
                # Use today's date for participant overview
                today_str = datetime.now().strftime("%Y-%m-%d")
                pre_t, daily = get_pre_tournament_picks(email), get_daily_predictions(email, today_str)
                
                participant_data.append({
                    "Name": name,
                    "Pre-T Teams": ", ".join([str(t) for t in pre_t.get("teams", [])]),
                    "Pre-T Players": ", ".join([_extract_name(p) for p in pre_t.get("players", [])]),
                    "Daily Players": ", ".join([_extract_name(p) for p in daily.get("players", [])]),
                    "Daily Match Picks": ", ".join([f"{v}" for v in daily.get("teams", {}).values()])
                })
            import pandas as pd
            if participant_data: st.table(pd.DataFrame(participant_data))

    # -------------------------------------------------------------
    # TAB 4: OVERRIDES
    # -------------------------------------------------------------
    with tab_override:
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

            # Pull all current daily data for this specific user
            # We need to decide which date to override. Let's add a date picker.
            override_date = st.date_input("Select Date for Override", datetime.now().date()).strftime("%Y-%m-%d")
            
            user_existing_daily = get_daily_predictions(selected_user_email, override_date)
            user_existing_teams = user_existing_daily.get("teams", {})
            user_existing_players = user_existing_daily.get("players", ["", ""])
            while len(user_existing_players) < 2: user_existing_players.append("")

            # Create two separate workspace columns
            col_match, col_player = st.columns(2, gap="large")

            # COLUMN 1: ISOLATED MATCH-WINNER OVERRIDE FORM
            with col_match:
                st.markdown("##### ⚽ Part A: Override Specific Match Pick")
                # Filter matches for the selected date
                date_matches = [m for m in current_matches.values() if datetime.fromisoformat(m.get("kickoff_time", "")).strftime("%Y-%m-%d") == override_date]
                
                if not date_matches:
                    st.info(f"No matches scheduled for {override_date}")
                else:
                    all_matches_sorted = sorted(date_matches, key=lambda x: x.get("kickoff_time", ""))
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
                        chosen_winner = st.selectbox(f"Predicted Outcome for {home} vs {away}:", options=team_options, index=default_team_idx)

                        if st.form_submit_button("💾 Force Update This Match Selection"):
                            user_existing_teams[selected_match_override_id] = chosen_winner
                            fdb.reference(f"daily_predictions/{selected_user_email.replace('.', '_')}/{override_date}").update({
                                "teams": user_existing_teams,
                                "submitted_at": f"{datetime.now().strftime('%Y-%m-%d %I:%M %p')} (Admin Match Override)"
                            })
                            st.success(f"Match selection updated safely for {override_date}!")
                            st.rerun()

            # COLUMN 2: ISOLATED GLOBAL DAILY PLAYER OVERRIDE FORM
            with col_player:
                st.markdown("##### 🏃‍♂️ Part B: Override Daily Player Lock-Ins")
                with st.form("whatsapp_player_override_form"):
                    p1 = st.text_input("Daily Player Pick 1:", value=user_existing_players[0])
                    p2 = st.text_input("Daily Player Pick 2:", value=user_existing_players[1])

                    if st.form_submit_button("🚀 Force Update Daily Players"):
                        cleaned_players = [p.strip() for p in [p1, p2] if p.strip()]
                        if len(cleaned_players) != 2:
                            st.error("Validation Error: Both text boxes must contain a valid player name.")
                        else:
                            fdb.reference(f"daily_predictions/{selected_user_email.replace('.', '_')}/{override_date}").update({
                                "players": cleaned_players,
                                "submitted_at": f"{datetime.now().strftime('%Y-%m-%d %I:%M %p')} (Admin Player Override)"
                            })
                            st.success(f"Daily player choices successfully locked for {override_date}!")
                            st.rerun()

    # -------------------------------------------------------------
    # TAB 5: LEADERBOARD
    # -------------------------------------------------------------
    with tab_leaderboard:
        st.subheader("🏆 Global Leaderboard")
        render_leaderboard_table()