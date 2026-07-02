"""
New scoring engine providing centralized, source-of-truth logic for points calculation.
"""
from typing import Dict, Any
from src.pre_tournament import apply_phase_multiplier, pick_multiplier_map


SCORING_RULES: Dict[str, Dict[str, int]] = {
    "league": {
        "goal": 10,
        "motm": 20,
        "correct_result": 10,
        "goal_difference": 5,
    },
    "R32": {
        "goal": 20,
        "motm": 40,
        "correct_result": 20,
        "goal_difference": 10,
    },
    "R16": {
        "goal": 40,
        "motm": 80,
        "correct_result": 40,
        "goal_difference": 20,
    },
    "QF": {
        "goal": 80,
        "motm": 160,
        "correct_result": 80,
        "goal_difference": 40,
    },
    "SF": {
        "goal": 160,
        "motm": 320,
        "correct_result": 160,
        "goal_difference": 80,
    },
    "F": {
        "goal": 320,
        "motm": 640,
        "correct_result": 320,
        "goal_difference": 160,
    },
}


def get_scoring_rules(scoring_stage: str) -> Dict[str, int]:
    """Returns configured scoring rules for a match stage."""
    return SCORING_RULES.get(scoring_stage, SCORING_RULES["league"])


def calculate_match_points_for_db(
    match_result: Dict[str, Any],
    home_team: str,
    away_team: str,
    scoring_stage: str = "league",
) -> Dict[str, Any]:
    """
    Core logic extracted from update_match_points_node.
    Calculates points for players/teams for a specific match.
    """
    def normalize_name(name: str) -> str:
        return name.strip().title()

    rules = get_scoring_rules(scoring_stage)
    result_points = rules["correct_result"]
    goal_diff_points = rules["goal_difference"]
    goal_points = rules["goal"]
    motm_points = rules["motm"]

    points = {
        "scoring_stage": scoring_stage if scoring_stage in SCORING_RULES else "league",
        "team_points": {},
        "player_points": {}
    }
    
    # Calculate Team points
    h_score = match_result.get("home_score", 0)
    a_score = match_result.get("away_score", 0)
    diff = h_score - a_score
    
    if diff > 0: # Home win
        points["team_points"][home_team] = {"win": result_points, "goaldiff": (diff * goal_diff_points), "total": (diff * goal_diff_points) + result_points}
        points["team_points"][away_team] = {"win": 0, "goaldiff": (diff * goal_diff_points) * -1, "total": (diff * goal_diff_points) * -1}
    elif diff < 0: # Away win
        points["team_points"][home_team] = {"win": 0, "goaldiff": (diff * goal_diff_points), "total": (diff * goal_diff_points)}
        points["team_points"][away_team] = {"win": result_points, "goaldiff": (abs(diff) * goal_diff_points), "total": (abs(diff) * goal_diff_points) + result_points}
    else: # Draw
        points["team_points"][home_team] = {"win": 0, "goaldiff": 0, "total": 0}
        points["team_points"][away_team] = {"win": 0, "goaldiff": 0, "total": 0}
        points["team_points"]["Draw"] = {"win": 0, "goaldiff": 0, "total": result_points}
    
    # Calculate Player points
    home_scorers = [normalize_name(p) for p in match_result.get("home_scorers", [])]
    away_scorers = [normalize_name(p) for p in match_result.get("away_scorers", [])]
    all_scorers = home_scorers + away_scorers
    
    motm = normalize_name(match_result.get("player_of_the_match", ""))
    
    all_involved = set(all_scorers)
    if motm:
        all_involved.add(motm)
        
    for player in all_involved:
        goals = all_scorers.count(player)
        goal_total = goals * goal_points
        motm_bonus = motm_points if player == motm else 0
        p_pts = goal_total + motm_bonus
        points["player_points"][player] = {"goals": goal_total, "motm": motm_bonus, "total": p_pts}
        
    return points

def calculate_user_match_breakdown(
    email: str,
    date: str,
    match_id: str,
    m_points: Dict[str, Any],
    pre_t: Dict[str, Any],
    daily: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Core logic extracted from refresh_leaderboard.
    Calculates points breakdown for a single user for a specific match.
    """
    def get_total(d: Any) -> int:
        if isinstance(d, dict): return d.get("total", 0)
        return d if isinstance(d, int) else 0

    pre_t_team_multipliers = pick_multiplier_map(pre_t.get("teams", []))
    pre_t_player_multipliers = pick_multiplier_map(pre_t.get("players", []))
    
    team_pick = daily.get('teams', {}).get(match_id)
    raw_player_picks = daily.get('players', [])

    player_picks = []
    for p in raw_player_picks:
        name = p.get('name', p) if isinstance(p, dict) else p
        player_picks.append(str(name).strip().lower())
    
    team_pts = get_total(m_points.get('team_points', {}).get(team_pick, 0))
    team_multiplier_value = pre_t_team_multipliers.get(str(team_pick).strip().lower(), 1)
    team_multiplier = team_multiplier_value > 1
    final_team_pts = apply_phase_multiplier(team_pts, team_multiplier_value)
    
    player_pts = 0
    player_multipliers = {}
    player_points_db = m_points.get('player_points', {})
    db_player_map = {str(k).strip().lower(): v for k, v in player_points_db.items()}

    for p_norm in player_picks:
        p_pts = get_total(db_player_map.get(p_norm, 0))
        player_multiplier_value = pre_t_player_multipliers.get(p_norm, 1)
        player_multipliers[p_norm] = player_multiplier_value
        p_pts = apply_phase_multiplier(p_pts, player_multiplier_value)
        player_pts += p_pts
    
    player_multiplier = any(multiplier > 1 for multiplier in player_multipliers.values())
    player_multiplier_value = max(player_multipliers.values(), default=1)

    return {
        "team_points": final_team_pts,
        "player_points": player_pts,
        "team_multiplier": team_multiplier,
        "player_multiplier": player_multiplier,
        "team_multiplier_value": team_multiplier_value,
        "player_multiplier_value": player_multiplier_value,
        "player_multipliers": player_multipliers,
    }
