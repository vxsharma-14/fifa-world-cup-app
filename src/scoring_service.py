"""Service for computing match points and updating user points/leaderboard manually."""

from firebase_admin import db
from src.db_service import (
    get_all_users,
    get_scheduled_matches,
    get_pre_tournament_history,
    get_pre_tournament_picks,
    get_daily_predictions,
    clean_email_key,
)
from typing import Dict, Any

from src.scoring_engine import calculate_match_points_for_db, calculate_user_match_breakdown

def update_match_points_node(
    match_id: str,
    match_result: Dict[str, Any],
    date: str,
    home_team: str,
    away_team: str,
    scoring_stage: str = "league",
) -> None:
    """Calculates and stores points for players/teams for a specific match with normalized names."""
    
    points = calculate_match_points_for_db(match_result, home_team, away_team, scoring_stage)
    points["et_date"] = date
    
    db.reference(f"match_points/{match_id}").set(points)

def refresh_leaderboard() -> None:
    """Manually triggers point calculation for all users based on match_points."""
    # 1. Fetch data
    users = get_all_users()
    all_match_points = db.reference("match_points").get() or {}
    user_points_root = db.reference("user_points")
    
    # 2. Iterate through each match in match_points
    for match_id, m_points in all_match_points.items():
        date = m_points.get("et_date")
        
        # 3. For each user, calculate points for this match
        for email, user_info in users.items():
            if "admin" in user_info.get("name", "").lower(): continue
            
            # Fetch predictions and pre-t picks
            daily = get_daily_predictions(email, date)
            pre_t = get_pre_tournament_picks(email)
            pre_t_history = get_pre_tournament_history(email)
            
            # Calculate user points using new engine
            breakdown = calculate_user_match_breakdown(
                email,
                date,
                match_id,
                m_points,
                pre_t,
                daily,
                pre_t_history,
            )
            
            # 4. Save granular audit for this match
            user_points_root.child(f"{clean_email_key(email)}/daily_breakdown/{date}/matches/{match_id}").set(breakdown)
    
    # 5. Aggregate totals
    for email, user_info in users.items():
        if "admin" in user_info.get("name", "").lower(): continue

        user_ref = user_points_root.child(clean_email_key(email))
        breakdown = user_ref.child("daily_breakdown").get() or {}

        grand_total = 0
        for date, date_data in breakdown.items():
            day_total = 0
            if "matches" in date_data:
                for match_id, match_pts in date_data["matches"].items():
                    day_total += match_pts.get("team_points", 0) + match_pts.get("player_points", 0)

            user_ref.child(f"daily_breakdown/{date}").update({"total_for_day": day_total})
            grand_total += day_total

        # Update user total and Sync leaderboard node
        user_ref.update({"total_score": grand_total})
        db.reference(f"leaderboard/{clean_email_key(email)}").set({
            "total_score": grand_total,
            "name": user_info.get("name", "Unknown")
        })

    print("Leaderboard refreshed successfully.")

