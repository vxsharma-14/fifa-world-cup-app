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

            """if st.button("🗑️ Clear Entire Match Schedule", type="primary"):
                delete_all_matches()
                st.success("All matches wiped out from the database configuration node.")
                st.rerun()"""

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
                score_str = f"{m_data.get('home_score', '-')} - {m_data.get('away_score', '-')}" if m_id in existing_results else " - "
                
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 3, 1])
                    c1.markdown(f"**{date_str}** {time_str}")
                    c2.markdown(f"**{home}** {score_str} **{away}**")
                    
                    with c3.popover("Edit"):
                        st.markdown(f"### Grade: {home} vs {away}")
                        
                        s_key = f'scorer_rows_{m_id}'
                        c_key = f'card_rows_{m_id}'
                        if s_key not in st.session_state: st.session_state[s_key] = [{'team': home, 'name': '', 'goals': 1}]
                        if c_key not in st.session_state: st.session_state[c_key] = [{'team': home, 'name': '', 'type': 'Yellow'}]

                        # Add buttons (outside form)
                        c_a1, c_a2 = st.columns(2)
                        if c_a1.button("➕ Add Scorer", key=f"as_{m_id}"): 
                            st.session_state[s_key].append({'team': home, 'name': '', 'goals': 1})
                            st.rerun()
                        if c_a2.button("➕ Add Card", key=f"ac_{m_id}"): 
                            st.session_state[c_key].append({'team': home, 'name': '', 'type': 'Yellow'})
                            st.rerun()
                        
                        with st.form(f"form_{m_id}"):
                            # 1. Score
                            with st.expander("1. Final Score", expanded=True):
                                c_s1, c_s2 = st.columns(2)
                                h_score = c_s1.number_input("Home Goals", min_value=0, value=int(m_data.get("home_score", 0)), step=1)
                                a_score = c_s2.number_input("Away Goals", min_value=0, value=int(m_data.get("away_score", 0)), step=1)
                                winner = home if h_score > a_score else (away if a_score > h_score else "Draw")
                                st.info(f"Outcome: **{winner}**")

                            # 2. Metrics
                            with st.expander("2. Match Metrics", expanded=False):
                                st.markdown("##### Goal Scorers")
                                for i, row in enumerate(st.session_state[s_key]):
                                    c1, c2, c3 = st.columns([2, 2, 1])
                                    row['team'] = c1.selectbox("Team", [home, away], index=[home, away].index(row['team']) if row['team'] in [home, away] else 0, key=f"st_{m_id}_{i}")
                                    row['name'] = c2.text_input("Player", value=row['name'], key=f"sn_{m_id}_{i}")
                                    row['goals'] = c3.number_input("Goals", min_value=1, value=row['goals'], key=f"sg_{m_id}_{i}")
                                
                                st.markdown("##### Discipline (Cards)")
                                for i, row in enumerate(st.session_state[c_key]):
                                    c1, c2, c3 = st.columns([2, 2, 1])
                                    row['team'] = c1.selectbox("Team", [home, away], index=[home, away].index(row['team']) if row['team'] in [home, away] else 0, key=f"ct_{m_id}_{i}")
                                    row['name'] = c2.text_input("Player", value=row['name'], key=f"cn_{m_id}_{i}")
                                    row['type'] = c3.selectbox("Type", ["Yellow", "Red"], index=["Yellow", "Red"].index(row['type']) if row['type'] in ["Yellow", "Red"] else 0, key=f"cty_{m_id}_{i}")

                            # 3. Highlights
                            with st.expander("3. Highlights", expanded=False):
                                motm = st.text_input("Man of the Match:", value=m_data.get("player_of_the_match", ""), key=f"motm_{m_id}").strip()

                            # Save
                            if st.form_submit_button("Save Results", type="primary"):
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
                                    "match_id": m_id, "home_score": h_score, "away_score": a_score,
                                    "winning_team": winner, "home_scorers": h_scorers,
                                    "away_scorers": a_scorers, "yellow_cards": yellow,
                                    "red_cards": red, "player_of_the_match": motm
                                })
                                st.success("Saved!")
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
            for email, user_info in all_users.items():
                if "admin" in user_info.get("name", "").lower(): continue
                pre_t, daily = get_pre_tournament_picks(email), get_daily_predictions(email)
                participant_data.append({
                    "Name": user_info.get("name"),
                    "Pre-T Teams": ", ".join(pre_t.get("teams", [])),
                    "Pre-T Players": ", ".join(pre_t.get("players", [])),
                    "Daily Players": ", ".join(daily.get("players", [])),
                    "Daily Match Picks": ", ".join([f"{v}" for v in daily.get("teams", {}).values()])
                })
            import pandas as pd
            if participant_data: st.table(pd.DataFrame(participant_data))

    # -------------------------------------------------------------
    # TAB 5: LEADERBOARD
    # -------------------------------------------------------------
    with tab_leaderboard:
        st.subheader("🏆 Global Leaderboard")
        render_leaderboard_table()