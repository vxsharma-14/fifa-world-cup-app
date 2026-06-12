"""UI module rendering granular points calculations and ledger audit analysis."""

import streamlit as st
from src.db_service import (
    get_pre_tournament_picks, get_daily_predictions, 
    get_scheduled_matches, get_match_results
)
from src.scoring_engine import calculate_match_points

def render_granular_points_analysis(email: str) -> None:
    """Renders an interactive audit log detailing calculated points based on DB data."""
    st.markdown("### 🔍 Granular Score Calculation Audit")
    st.caption("Real-time points calculation based on current match results.")

    # Fetch data
    pre_t_picks = get_pre_tournament_picks(email)
    daily_picks = get_daily_predictions(email)
    all_matches = get_scheduled_matches()
    all_results = get_match_results()

    if not daily_picks or not all_results:
        st.info("📊 Match results or predictions are missing. Points will be calculated once data is available.")
        return

    # Calculate total points and breakdown per match
    total_points = 0
    match_breakdowns = []

    for match_id, match_data in all_matches.items():
        if match_id in all_results:
            match_result = all_results[match_id]
            points = calculate_match_points(match_id, pre_t_picks, daily_picks, match_result, match_data)
            total_points += points
            match_breakdowns.append({
                "display_string": match_data.get("display_string"),
                "points": points
            })

    # Display Total
    st.metric("Total Tournament Points", f"{total_points} pts")

    # Display Breakdown
    st.markdown("---")
    st.markdown("#### 📅 Match Breakdown")
    for b in match_breakdowns:
        st.markdown(f"**{b['display_string']}**: `{b['points']} pts`")