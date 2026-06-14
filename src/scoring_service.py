"""Service for computing match points and updating user points/leaderboard manually."""

from firebase_admin import db
from src.db_service import get_all_users, get_scheduled_matches, get_pre_tournament_picks, get_daily_predictions, clean_email_key
from typing import Dict, Any

def update_match_points_node(match_id: str, match_result: Dict[str, Any], date: str, home_team: str, away_team: str) -> None:
    """Calculates and stores points for players/teams for a specific match with normalized names."""
    
    def normalize_name(name: str) -> str:
        """Standardizes name formatting for DB storage."""
        return name.strip().title()

    points = {
        "et_date": date,
        "scoring_stage": "league",
        "team_points": {},
        "player_points": {}
    }
    
    # Calculate Team points
    h_score = match_result.get("home_score", 0)
    a_score = match_result.get("away_score", 0)
    diff = h_score - a_score
    
    if diff > 0: # Home win
        points["team_points"][home_team] = {"win": 10, "goaldiff": (diff * 10), "total": (diff * 10) + 10}
        points["team_points"][away_team] = {"win": 0, "goaldiff": (diff * 10) * -1, "total": (diff * 10) * -1}
    elif diff < 0: # Away win
        points["team_points"][home_team] = {"win": 0, "goaldiff": (diff * 10), "total": (diff * 10)}
        points["team_points"][away_team] = {"win": 10, "goaldiff": (abs(diff) * 10), "total": (abs(diff) * 10) + 10}
    else: # Draw
        points["team_points"][home_team] = {"win": 0, "goaldiff": 0, "total": 0}
        points["team_points"][away_team] = {"win": 0, "goaldiff": 0, "total": 0}
        points["team_points"]["Draw"] = {"win": 0, "goaldiff": 0, "total": 10}
    
    # Calculate Player points (proactively normalized)
    home_scorers = [normalize_name(p) for p in match_result.get("home_scorers", [])]
    away_scorers = [normalize_name(p) for p in match_result.get("away_scorers", [])]
    all_scorers = home_scorers + away_scorers
    
    motm = normalize_name(match_result.get("player_of_the_match", ""))
    
    # Identify all unique players involved
    all_involved = set(all_scorers)
    if motm:
        all_involved.add(motm)
        
    for player in all_involved:
        goals = all_scorers.count(player)
        motm_bonus = 20 if player == motm else 0
        p_pts = (goals * 10) + motm_bonus
        points["player_points"][player] = {"goals": goals * 10, "motm": motm_bonus, "total": p_pts}
        
    db.reference(f"match_points/{match_id}").set(points)

def refresh_leaderboard() -> None:
    """Manually triggers point calculation for all users based on match_points."""
    # 1. Fetch data
    users = get_all_users()
    all_match_points = db.reference("match_points").get() or {}
    user_points_root = db.reference("user_points")
    
    # Helper for points extraction
    def get_total(d: Any) -> int:
        if isinstance(d, dict): return d.get("total", 0)
        return d if isinstance(d, int) else 0

    # 2. Iterate through each match in match_points
    for match_id, m_points in all_match_points.items():
        date = m_points.get("et_date")
        
        # 3. For each user, calculate points for this match
        for email, user_info in users.items():
            if "admin" in user_info.get("name", "").lower(): continue
            
            # Fetch predictions and pre-t picks
            daily = get_daily_predictions(email, date)
            pre_t = get_pre_tournament_picks(email)
            pre_t_teams = pre_t.get("teams", [])
            pre_t_players = pre_t.get("players", [])
            
            # Calculate user points
            team_pick = daily.get('teams', {}).get(match_id)
            raw_player_picks = daily.get('players', [])

            def get_name(p):
                return p.get('name', p) if isinstance(p, dict) else p

            player_picks = [get_name(p) for p in raw_player_picks]
            
            team_pts = get_total(m_points.get('team_points', {}).get(team_pick, 0))
            player_pts = sum(get_total(m_points.get('player_points', {}).get(p, 0)) for p in player_picks)
            
            # Check for multiplier
            team_multiplier = (team_pick in pre_t_teams)
            player_multiplier = any(get_name(p) in pre_t_players for p in player_picks)

            # 4. Save granular audit for this match
            user_points_root.child(f"{clean_email_key(email)}/daily_breakdown/{date}/matches/{match_id}").set({
                "team_points": team_pts,
                "player_points": player_pts,
                "team_multiplier": team_multiplier,
                "player_multiplier": player_multiplier,
            })
    
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

