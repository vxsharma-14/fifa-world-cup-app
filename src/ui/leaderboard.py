import streamlit as st
from firebase_admin import db

def render_leaderboard_table() -> None:
    """Displays the live group rankings with granular points breakdown."""
    leaderboard_data = db.reference("leaderboard").get() or {}
    audit_data = db.reference("points_audit").get() or {}

    if not leaderboard_data:
        st.info("No data available yet.")
        return

    table_data = []
    for k, v in leaderboard_data.items():
        # Get granular audit data for this user
        user_audit = audit_data.get(k, {}).get("match_results", {})
        
        # Initialize breakdown counters
        # Note: The scoring engine categorizes as: match_winner, goal_difference, player_performance, discipline
        # We need to map these to: Pre-T Team, Pre-T Player, Daily Team, Daily Player
        # This requires additional mapping logic based on picks which might be complex here.
        # As a first step, let's just display the categories from the scoring engine.
        
        # Aggregating categories from all match results
        mw_pts = sum(m.get("match_winner", 0) for m in user_audit.values())
        gd_pts = sum(m.get("goal_difference", 0) for m in user_audit.values())
        pp_pts = sum(m.get("player_performance", 0) for m in user_audit.values())
        dis_pts = sum(m.get("discipline", 0) for m in user_audit.values())
        
        table_data.append({
            "Friend": v.get("name", k),
            "Total": int(v.get("total_score", 0)),
            "Match Winner": mw_pts,
            "Goal Diff": gd_pts,
            "Player Perf": pp_pts,
            "Discipline": dis_pts
        })
    
    # Sort by total points
    sorted_data = sorted(table_data, key=lambda x: x["Total"], reverse=True)
    
    # Add Rank
    for idx, item in enumerate(sorted_data, 1):
        item["Rank"] = idx
        
    st.table(sorted_data)
