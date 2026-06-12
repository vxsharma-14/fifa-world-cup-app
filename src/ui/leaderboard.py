import streamlit as st
from firebase_admin import db

def render_leaderboard_table() -> None:
    """Displays the live group rankings."""
    leaderboard_data = db.reference("leaderboard").get() or {}

    if not leaderboard_data:
        st.info("No data available yet.")
        return

    table_data = []
    for k, v in leaderboard_data.items():
        table_data.append({
            "Friend": v.get("name", k),
            "Total": int(v.get("total_score", 0))
        })
    
    # Sort by total points
    sorted_data = sorted(table_data, key=lambda x: x["Total"], reverse=True)
    
    # Add Rank
    for idx, item in enumerate(sorted_data, 1):
        item["Rank"] = idx
        
    # Reorder for display
    display_data = [{"Rank": item["Rank"], "Friend": item["Friend"], "Total": item["Total"]} for item in sorted_data]
    
    st.table(display_data)
