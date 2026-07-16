"""Administrative panels handling internal settings, match scheduling, and results scoring."""

import streamlit as st
from datetime import datetime, time
import zoneinfo
from firebase_admin import db
from src.config import CONFIG
from src.db_service import (
    get_scheduled_matches, save_structured_match,
    delete_all_matches, save_match_result, get_match_results, get_pt_timestamp,
    get_rosters, get_all_users, set_user_active, get_all_roster_players
)
from src.ui.leaderboard import render_leaderboard_table

SCORING_STAGE_OPTIONS = {
    "league": "League",
    "R32": "Round of 32",
    "R16": "Round of 16",
    "QF": "Quarter Final",
    "SF": "Semi Final",
    "TP": "Bronze Final",
    "F": "Final",
}


def render_admin_dashboard() -> None:
    """Renders structured scheduling calendars, match grading forms, and support tools."""
    st.header("👑 Admin Command Center")

    # Fetch active data states
    current_time = datetime.now(zoneinfo.ZoneInfo("US/Pacific"))
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

    tab_sched, tab_grade, tab_part, tab_override, tab_leaderboard, tab_users, tab_rosters = st.tabs([
        "📅 Matches & Scheduling", 
        "⚽ Results & Grading", 
        "👥 Participants", 
        "💬 Overrides",
        "🏆 Leaderboard",
        "👥 User Control",
        "👥 Rosters"
    ])

    # ... (Keep existing code for tabs 1-5, add Tab 6 below)

    # -------------------------------------------------------------
    # TAB 6: ROSTER MANAGEMENT
    # -------------------------------------------------------------
    with tab_rosters:
        st.subheader("👥 Manage Team Rosters")
        
        # 1. Fetch Rosters
        rosters = get_rosters()
        
        # 2. Add/Edit Form
        with st.form("roster_update_form"):
            team = st.text_input("Team Name").strip()
            players_str = st.text_area("Player Names (comma-separated)").strip()
            
            if st.form_submit_button("💾 Save/Update Roster"):
                if not team or not players_str:
                    st.error("Team name and players are required.")
                else:
                    player_list = [p.strip() for p in players_str.split(",")]
                    db.reference(f"rosters/{team}").set(player_list)
                    get_rosters.clear()
                    get_all_roster_players.clear()
                    st.success(f"Roster for {team} updated!")
                    st.rerun()
        
        st.markdown("---")
        # 3. View Existing
        for team, players in rosters.items():
            with st.expander(f"{team} ({len(players)} players)"):
                st.write(", ".join(players))
                if st.button(f"🗑️ Delete Roster: {team}", key=f"del_{team}"):
                    db.reference(f"rosters/{team}").delete()
                    get_rosters.clear()
                    get_all_roster_players.clear()
                    st.rerun()
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
                match_time = st.time_input("Kickoff Time (PT)", time(12, 00))

            scoring_stage = st.selectbox(
                "Scoring Stage",
                options=list(SCORING_STAGE_OPTIONS.keys()),
                format_func=lambda stage: SCORING_STAGE_OPTIONS[stage],
                index=0,
            )

            if st.form_submit_button("➕ Add Match to Master Calendar"):
                if not home_team or not away_team:
                    st.error("Please provide both team names.")
                else:
                    combined_dt = datetime.combine(match_date, match_time)
                    pt_dt = combined_dt.replace(tzinfo=zoneinfo.ZoneInfo("US/Pacific"))
                    kickoff_iso = pt_dt.isoformat()

                    timestamp_str = pt_dt.strftime("%I:%M %p")
                    display_str = f"{timestamp_str} | {home_team} vs {away_team}"
                    match_id = f"match_{int(datetime.now().timestamp())}"

                    save_structured_match(
                        match_id,
                        home_team,
                        away_team,
                        kickoff_iso,
                        display_str,
                        scoring_stage,
                    )
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
            match_options = {}
            for match in sorted_completed:
                match_id = match["id"]
                dt = datetime.fromisoformat(match["kickoff_time"])
                date_str = dt.strftime("%d/%m")
                time_str = dt.strftime("%I:%M %p")
                home, away = match["home_team"], match["away_team"]
                has_results = match_id in existing_results
                match_options[match_id] = f"{date_str} {time_str} | {home} vs {away} {'✅' if has_results else '⏳'}"

            if "grade_selected_match_id" not in st.session_state or st.session_state["grade_selected_match_id"] not in match_options:
                st.session_state["grade_selected_match_id"] = next(
                    (match["id"] for match in sorted_completed if match["id"] not in existing_results),
                    sorted_completed[0]["id"],
                )

            selected_match_id = st.selectbox(
                "Select a match to edit",
                options=list(match_options.keys()),
                format_func=lambda x: match_options[x],
                key="grade_selected_match_id",
            )

            selected_match = next(match for match in sorted_completed if match["id"] == selected_match_id)
            m_id = selected_match["id"]
            m_data = existing_results.get(m_id, {})
            home, away = selected_match["home_team"], selected_match["away_team"]
            has_results = m_id in existing_results
            btn_label = "Edit Results" if has_results else "Add Results"
            all_roster_players = get_all_roster_players()
            player_options = [""] + all_roster_players

            st.caption("Only one match editor is rendered at a time to keep Add Scorer responsive.")

            with st.expander(match_options[m_id], expanded=True):
                with st.form(f"form_{m_id}"):
                    current_stage = m_data.get("scoring_stage") or selected_match.get("scoring_stage", "league")
                    stage_options = list(SCORING_STAGE_OPTIONS.keys())
                    stage_index = stage_options.index(current_stage) if current_stage in stage_options else 0
                    scoring_stage = st.selectbox(
                        "Scoring Stage",
                        options=stage_options,
                        format_func=lambda stage: SCORING_STAGE_OPTIONS[stage],
                        index=stage_index,
                        key=f"scoring_stage_{m_id}",
                    )

                    c_s1, c_s2 = st.columns(2)
                    h_score = c_s1.number_input("Home Goals", min_value=0, value=int(m_data.get("home_score", 0)), step=1)
                    a_score = c_s2.number_input("Away Goals", min_value=0, value=int(m_data.get("away_score", 0)), step=1)

                    s_key = f"scorer_rows_{m_id}"
                    c_key = f"card_rows_{m_id}"
                    if s_key not in st.session_state:
                        st.session_state[s_key] = (
                            [{"team": home, "name": n, "goals": 1} for n in m_data.get("home_scorers", [])]
                            + [{"team": away, "name": n, "goals": 1} for n in m_data.get("away_scorers", [])]
                            or [{"team": home, "name": "", "goals": 1}]
                        )
                    if c_key not in st.session_state:
                        st.session_state[c_key] = (
                            [{"team": home, "name": n, "type": "Yellow"} for n in m_data.get("yellow_cards", [])]
                            + [{"team": home, "name": n, "type": "Red"} for n in m_data.get("red_cards", [])]
                            or [{"team": home, "name": "", "type": "Yellow"}]
                        )

                    st.markdown("##### Goal Scorers")
                    for i, row in enumerate(st.session_state[s_key]):
                        c1, c2, c3 = st.columns([2, 2, 1])
                        row["team"] = c1.selectbox(
                            "Team",
                            [home, away],
                            index=[home, away].index(row["team"]) if row["team"] in [home, away] else 0,
                            key=f"st_{m_id}_{i}",
                        )
                        idx = player_options.index(row["name"]) if row["name"] in player_options else 0
                        row["name"] = c2.selectbox(
                            "Player",
                            options=player_options,
                            index=idx,
                            key=f"sn_{m_id}_{i}",
                        )
                        row["goals"] = c3.number_input(
                            "Goals",
                            min_value=1,
                            value=row.get("goals", 1),
                            key=f"sg_{m_id}_{i}",
                        )
                    if st.form_submit_button("➕ Add Scorer"):
                        st.session_state[s_key].append({"team": home, "name": "", "goals": 1})
                        st.rerun()

                    st.markdown("##### Discipline (Cards)")
                    for i, row in enumerate(st.session_state[c_key]):
                        c1, c2, c3 = st.columns([2, 2, 1])
                        row["team"] = c1.selectbox(
                            "Team",
                            [home, away],
                            index=[home, away].index(row["team"]) if row["team"] in [home, away] else 0,
                            key=f"ct_{m_id}_{i}",
                        )
                        row["name"] = c2.text_input("Player", value=row["name"], key=f"cn_{m_id}_{i}")
                        row["type"] = c3.selectbox(
                            "Type",
                            ["Yellow", "Red"],
                            index=["Yellow", "Red"].index(row["type"]) if row["type"] in ["Yellow", "Red"] else 0,
                            key=f"cty_{m_id}_{i}",
                        )
                    if st.form_submit_button("➕ Add Card"):
                        st.session_state[c_key].append({"team": home, "name": "", "type": "Yellow"})
                        st.rerun()

                    motm_current = m_data.get("player_of_the_match", "")
                    motm_idx = player_options.index(motm_current) if motm_current in player_options else 0
                    motm = st.selectbox("Man of the Match:", options=player_options, index=motm_idx, key=f"motm_{m_id}")

                    if st.form_submit_button(btn_label, type="primary"):
                        def norm(name):
                            return name.strip().title()

                        h_scorers, a_scorers, yellow, red = [], [], [], []
                        for r in st.session_state[s_key]:
                            if r["name"]:
                                if r["team"] == home:
                                    h_scorers.extend([norm(r["name"])] * r["goals"])
                                else:
                                    a_scorers.extend([norm(r["name"])] * r["goals"])
                        for r in st.session_state[c_key]:
                            if r["name"]:
                                if r["type"] == "Yellow":
                                    yellow.append(norm(r["name"]))
                                else:
                                    red.append(norm(r["name"]))

                        save_match_result(m_id, {
                            "match_id": m_id,
                            "home_score": h_score,
                            "away_score": a_score,
                            "winning_team": home if h_score > a_score else (away if a_score > h_score else "Draw"),
                            "home_scorers": h_scorers,
                            "away_scorers": a_scorers,
                            "yellow_cards": yellow,
                            "red_cards": red,
                            "player_of_the_match": norm(motm) if motm else "",
                            "scoring_stage": scoring_stage,
                        })
                        del st.session_state[s_key]
                        del st.session_state[c_key]
                        st.success(f"Results for {home} vs {away} saved!")
                        st.rerun()
            for m in []:
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
                        current_stage = m_data.get("scoring_stage") or m.get("scoring_stage", "league")
                        stage_options = list(SCORING_STAGE_OPTIONS.keys())
                        stage_index = stage_options.index(current_stage) if current_stage in stage_options else 0
                        scoring_stage = st.selectbox(
                            "Scoring Stage",
                            options=stage_options,
                            format_func=lambda stage: SCORING_STAGE_OPTIONS[stage],
                            index=stage_index,
                            key=f"scoring_stage_{m_id}",
                        )

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
                            
                            # Replace text_input with searchable selectbox
                            options = [""] + all_roster_players
                            idx = options.index(row['name']) if row['name'] in options else 0
                            row['name'] = c2.selectbox("Player", options=options, index=idx, key=f"sn_{m_id}_{i}")
                            
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

                        # Man of the Match
                        options = [""] + all_roster_players
                        motm_current = m_data.get("player_of_the_match", "")
                        motm_idx = options.index(motm_current) if motm_current in options else 0
                        motm = st.selectbox("Man of the Match:", options=options, index=motm_idx, key=f"motm_{m_id}")

                        if st.form_submit_button(btn_label, type="primary"):
                            def norm(name): return name.strip().title()
                            h_scorers, a_scorers, yellow, red = [], [], [], []
                            for r in st.session_state[s_key]:
                                if r['name']:
                                    if r['team'] == home: h_scorers.extend([norm(r['name'])] * r['goals'])
                                    else: a_scorers.extend([norm(r['name'])] * r['goals'])
                            for r in st.session_state[c_key]:
                                if r['name']:
                                    if r['type'] == "Yellow": yellow.append(norm(r['name']))
                                    else: red.append(norm(r['name']))

                            save_match_result(m_id, {
                                "match_id": m_id, 
                                "home_score": h_score, 
                                "away_score": a_score,
                                "winning_team": home if h_score > a_score else (away if a_score > h_score else "Draw"), 
                                "home_scorers": h_scorers,
                                "away_scorers": a_scorers,
                                "yellow_cards": yellow,
                                "red_cards": red, 
                                "player_of_the_match": norm(motm) if motm else "",
                                "scoring_stage": scoring_stage,
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
        from src.ui.data_viewer import render_filtered_participant_view
        # Assuming admin is always viewing, is_admin=True
        render_filtered_participant_view("admin@fifafantasy.com", True)

    # -------------------------------------------------------------
    # TAB 4: OVERRIDES
    # -------------------------------------------------------------
    with tab_override:
        st.subheader("💬 User Prediction Overrides (WhatsApp Backdoor)")
        st.caption("Manually adjust or insert entries for friends who submitted via WhatsApp due to platform delays.")

        from src.db_service import get_all_users, save_user_daily_override, get_daily_predictions, get_pt_timestamp
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
                                "submitted_at": f"{get_pt_timestamp()} (Admin Match Override)"
                            })
                            st.success(f"Match selection updated safely for {override_date}!")
                            st.rerun()

            # COLUMN 2: ISOLATED GLOBAL DAILY PLAYER OVERRIDE FORM
            with col_player:
                st.markdown("##### 🏃‍♂️ Part B: Override Daily Player Lock-Ins")
                with st.form("whatsapp_player_override_form"):
                    options = [""] + all_roster_players
                    
                    # Pick 1
                    p1_idx = options.index(user_existing_players[0]) if user_existing_players[0] in options else 0
                    p1 = st.selectbox("Daily Player Pick 1:", options=options, index=p1_idx)
                    
                    # Pick 2
                    p2_idx = options.index(user_existing_players[1]) if user_existing_players[1] in options else 0
                    p2 = st.selectbox("Daily Player Pick 2:", options=options, index=p2_idx)

                    if st.form_submit_button("🚀 Force Update Daily Players"):
                        cleaned_players = [p.strip() for p in [p1, p2] if p.strip()]
                        if len(cleaned_players) != 2:
                            st.error("Validation Error: Both dropdowns must contain a valid player name.")
                        else:
                            fdb.reference(f"daily_predictions/{selected_user_email.replace('.', '_')}/{override_date}").update({
                                "players": cleaned_players,
                                "submitted_at": f"{get_pt_timestamp()} (Admin Player Override)"
                            })
                            st.success(f"Daily player choices successfully locked for {override_date}!")
                            st.rerun()

    # -------------------------------------------------------------
    # TAB 5: LEADERBOARD
    # -------------------------------------------------------------
    with tab_leaderboard:
        st.subheader("🏆 Global Leaderboard")
        render_leaderboard_table()

    # -------------------------------------------------------------
    # TAB 6: USER CONTROL
    # -------------------------------------------------------------
    with tab_users:
        st.subheader("👥 Enable / Disable Users")
        st.caption("Disabled users keep their data, but cannot sign in.")

        all_users = get_all_users()
        managed_users = [
            user
            for user in all_users.values()
            if user.get("email") and user.get("email") != CONFIG.ADMIN_EMAIL
        ]

        if not managed_users:
            st.info("No users found to manage.")
        else:
            for user in sorted(managed_users, key=lambda u: u.get("name", "").lower()):
                user_email = user.get("email", "")
                user_name = user.get("name", user_email)
                current_active = bool(user.get("is_active", True))

                with st.expander(f"{user_name} ({user_email})", expanded=False):
                    st.write(f"Status: {'Enabled' if current_active else 'Disabled'}")
                    new_active = st.toggle(
                        "Account Enabled",
                        value=current_active,
                        key=f"user_active_toggle_{user_email}",
                    )

                    if st.button("Save Status", key=f"save_user_status_{user_email}"):
                        set_user_active(user_email, new_active)
                        st.success(f"Updated {user_email}.")
                        st.rerun()
