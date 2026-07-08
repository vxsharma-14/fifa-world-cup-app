"""UI module rendering granular points calculations and ledger audit analysis."""

import streamlit as st
from firebase_admin import db
from src.db_service import (
    get_pre_tournament_history,
    get_pre_tournament_picks,
    get_daily_predictions, 
    get_matches_by_date, get_match_results, get_pt_date_key
)
from src.scoring_engine import calculate_user_match_breakdown

def render_granular_points_analysis(email: str) -> None:
    """Renders an interactive audit log detailing calculated points based on DB data."""
    st.markdown("### 🔍 Granular Score Calculation Audit")
    st.caption("Real-time points calculation based on current match results.")

    # Fetch data
    pre_t_picks = get_pre_tournament_picks(email)
    pre_t_history = get_pre_tournament_history(email)
    all_dates_matches = get_matches_by_date()

    # Calculate total points and breakdown per match
    total_points = 0
    match_breakdowns = []

    for date, matches_on_date in all_dates_matches.items():
        if not isinstance(matches_on_date, dict): continue

        # Fetch predictions for this date once
        daily_picks = get_daily_predictions(email, date)

        for match_id, match_data in matches_on_date.items():
            if match_data.get("status") == "completed":
                # Fetch match points data for this match
                m_points = db.reference(f"match_points/{match_id}").get() or {}
                
                # Calculate breakdown using new engine
                breakdown = calculate_user_match_breakdown(
                    email,
                    date,
                    match_id,
                    m_points,
                    pre_t_picks,
                    daily_picks,
                    pre_t_history,
                )
                
                team_pts = breakdown.get('team_points', 0)
                player_pts = breakdown.get('player_points', 0)
                
                total_pts = team_pts + player_pts
                
                total_points += total_pts
                match_breakdowns.append({
                    "date": date,
                    "teams": f"{match_data.get('home_team')} vs {match_data.get('away_team')}",
                    "team_pts": team_pts,
                    "player_pts": player_pts,
                    "total_pts": total_pts
                })

    # Display Total
    st.metric("Total Tournament Points", f"{total_points} pts")

    # Display Breakdown
    st.markdown("---")
    st.markdown("#### 📅 Match Breakdown")

    # Header row
    c1, c2, c3, c4, c5 = st.columns([1, 2, 1, 1, 1])
    c1.markdown("**Date**")
    c2.markdown("**Match**")
    c3.markdown("**Team Pts**")
    c4.markdown("**Player Pts**")
    c5.markdown("**Total**")
    st.markdown("---")

    for b in match_breakdowns:
        c1, c2, c3, c4, c5 = st.columns([1, 2, 1, 1, 1])
        c1.text(b['date'])
        c2.text(b['teams'])
        c3.text(b['team_pts'])
        c4.text(b['player_pts'])
        c5.markdown(f"**{b['total_pts']} pts**")
