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
) -> int:
    """
    Calculates total points for a single match for a specific user.

    Args:
        match_id: Unique identifier for the match.
        pre_t_picks: User's pre-tournament selections.
        daily_picks: User's daily predictions.
        match_result: Final stats for the match.
        match_metadata: Match details (teams, kickoff).

    Returns:
        int: Total points earned for this match.
    """
    points = 0
    
    # Extract data
    home_team = match_metadata.get("home_team")
    away_team = match_metadata.get("away_team")
    winning_team = match_result.get("winning_team")
    
    pre_t_teams = pre_t_picks.get("teams", [])
    user_daily_teams_map = daily_picks.get("teams", {})
    user_prediction = user_daily_teams_map.get(match_id)

    # --- RULE: Match Winner Points ---
    
    # 1. Check if Pre-T team is playing
    is_home_pre_t = home_team in pre_t_teams
    is_away_pre_t = away_team in pre_t_teams
    
    # 2. Determine predicted winner (with Pre-T override)
    if is_home_pre_t:
        predicted_winner = home_team
    elif is_away_pre_t:
        predicted_winner = away_team
    else:
        predicted_winner = user_prediction
        
    # 3. Calculate points
    if predicted_winner == winning_team:
        if is_home_pre_t or is_away_pre_t:
            points += 20  # Pre-T Override Double Points
        else:
            points += 10  # Standard Points

    # --- RULE: Player Performance Points ---
    pre_t_players = pre_t_picks.get("players", [])
    user_daily_players = daily_picks.get("players", [])
    
    # Collect all scorers
    all_scorers = match_result.get("home_scorers", []) + match_result.get("away_scorers", [])
    motm = match_result.get("player_of_the_match")
    
    # Check player performance picks
    for player in user_daily_players:
        if not player: continue
        
        is_pre_t = player in pre_t_players
        multiplier = 2 if is_pre_t else 1
        
        # Points: Goal (+10/20), MotM (+20/40)
        if player in all_scorers:
            points += 10 * multiplier
        if player == motm:
            points += 20 * multiplier
            
    # --- RULE: Disciplinary Penalties ---
    yellow_cards = match_result.get("yellow_cards", [])
    red_cards = match_result.get("red_cards", [])
    
    for player in user_daily_players:
        if not player: continue
        
        is_pre_t = player in pre_t_players
        multiplier = 2 if is_pre_t else 1
        
        # Penalties: Yellow (-5/10), Red (-10/20)
        if player in yellow_cards:
            points -= 5 * multiplier
        if player in red_cards:
            points -= 10 * multiplier
            
    # --- RULE: Goal Difference Bonus/Penalty ---
    if predicted_winner and predicted_winner != "Draw":
        goal_diff = abs(match_result.get("home_score", 0) - match_result.get("away_score", 0))
        
        # Determine if predicted winner won or lost
        if predicted_winner == winning_team:
            gd_points = goal_diff * 10
        else:
            gd_points = -(goal_diff * 10)
            
        # Apply Pre-T multiplier if the predicted team is a Pre-T team
        if predicted_winner in pre_t_teams:
            gd_points *= 2
            
        points += gd_points
            
    return points
