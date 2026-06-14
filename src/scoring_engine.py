"""
Core business logic for calculating FIFA Fantasy APSJ points.

This module is designed to be a pure, functional service, decoupled from 
UI components and database interactions for maximum testability.
"""

from typing import Dict, List, Any

def calculate_match_points(
    match_id: str,
    pre_t_picks: Dict[str, Any],
    daily_picks: Dict[str, Any],
    match_result: Dict[str, Any],
    match_metadata: Dict[str, Any]
) -> Dict[str, int]:
    """
    Calculates granular points breakdown for a single match for a specific user.

    Returns:
        Dict[str, int]: Breakdown of points by rule category.
    """
    def normalize(name: Any) -> str:
        """Normalizes player names on-the-fly for robust comparison."""
        if isinstance(name, dict):
            name = name.get('name', '')
        return str(name).strip().lower()

    breakdown = {
        "match_winner": 0,
        "goal_difference": 0,
        "player_performance": 0,
        "discipline": 0
    }
    
    # Extract data
    home_team = match_metadata.get("home_team")
    away_team = match_metadata.get("away_team")
    winning_team = match_result.get("winning_team")
    
    pre_t_teams = pre_t_picks.get("teams", [])
    user_daily_teams_map = daily_picks.get("teams", {})
    user_prediction = user_daily_teams_map.get(match_id)

    # --- RULE: Match Winner Points ---
    is_home_pre_t = home_team in pre_t_teams
    is_away_pre_t = away_team in pre_t_teams
    
    if is_home_pre_t:
        predicted_winner = home_team
    elif is_away_pre_t:
        predicted_winner = away_team
    else:
        predicted_winner = user_prediction
        
    if predicted_winner == winning_team:
        if is_home_pre_t or is_away_pre_t:
            breakdown["match_winner"] = 20
        else:
            breakdown["match_winner"] = 10

    # --- RULE: Player Performance Points ---
    # Normalize lookup lists
    pre_t_players = [normalize(p) for p in pre_t_picks.get("players", [])]
    user_daily_players = daily_picks.get("players", [])
    
    all_scorers = [normalize(p) for p in (match_result.get("home_scorers", []) + match_result.get("away_scorers", []))]
    motm = normalize(match_result.get("player_of_the_match"))
    
    for player_entry in user_daily_players:
        if not player_entry: continue
        
        # Normalize the player being evaluated
        norm_player = normalize(player_entry)
        
        # DEBUG: Log normalization
        print(f"DEBUG: Comparing user player: '{norm_player}' against scorers: {[s for s in all_scorers]} and MOTM: '{motm}'")
        
        is_pre_t = norm_player in pre_t_players
        multiplier = 2 if is_pre_t else 1
        
        if norm_player in all_scorers:
            print(f"DEBUG: Match found in scorers for {norm_player}")
            breakdown["player_performance"] += 10 * multiplier
        if norm_player == motm:
            print(f"DEBUG: Match found in MOTM for {norm_player}")
            breakdown["player_performance"] += 20 * multiplier
            
    # --- RULE: Disciplinary Penalties ---
    yellow_cards = [normalize(p) for p in match_result.get("yellow_cards", [])]
    red_cards = [normalize(p) for p in match_result.get("red_cards", [])]
    
    for player_entry in user_daily_players:
        if not player_entry: continue
        norm_player = normalize(player_entry)
        
        is_pre_t = norm_player in pre_t_players
        multiplier = 2 if is_pre_t else 1
        
        if norm_player in yellow_cards:
            breakdown["discipline"] -= 5 * multiplier
        if norm_player in red_cards:
            breakdown["discipline"] -= 10 * multiplier
            
    # --- RULE: Goal Difference Bonus/Penalty ---
    if predicted_winner and predicted_winner != "Draw":
        goal_diff = abs(match_result.get("home_score", 0) - match_result.get("away_score", 0))
        
        if predicted_winner == winning_team:
            gd_points = goal_diff * 10
        else:
            gd_points = -(goal_diff * 10)
            
        if predicted_winner in pre_t_teams:
            gd_points *= 2
            
        breakdown["goal_difference"] = gd_points
            
    # Add multiplier flags
    breakdown["team_multiplier"] = (predicted_winner in pre_t_teams)
    breakdown["player_multiplier"] = any(normalize(p) in pre_t_players for p in user_daily_players)
            
    return breakdown
