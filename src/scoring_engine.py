"""
New scoring engine providing centralized, source-of-truth logic for points calculation.
"""
from typing import Dict, Any

def calculate_match_points_for_db(match_result: Dict[str, Any], home_team: str, away_team: str) -> Dict[str, Any]:
    """
    Core logic extracted from update_match_points_node.
    Calculates points for players/teams for a specific match.
    """
    def normalize_name(name: str) -> str:
        return name.strip().title()

    points = {
        "scoring_stage": "league",
        "team_points": {},
        "player_points": {}
    }
    
    # Calculate Team points
    h_score = match_result.get("home_score", 0)
    a_score = match_result.get("away_score", 0)
    diff = h_score - a_score
    
    if diff > 0: # Home win
        points["team_points"][home_team] = {"win": 10, "goaldiff": (diff * 5), "total": (diff * 5) + 10}
        points["team_points"][away_team] = {"win": 0, "goaldiff": (diff * 5) * -1, "total": (diff * 5) * -1}
    elif diff < 0: # Away win
        points["team_points"][home_team] = {"win": 0, "goaldiff": (diff * 5), "total": (diff * 5)}
        points["team_points"][away_team] = {"win": 10, "goaldiff": (abs(diff) * 5), "total": (abs(diff) * 5) + 10}
    else: # Draw
        points["team_points"][home_team] = {"win": 0, "goaldiff": 0, "total": 0}
        points["team_points"][away_team] = {"win": 0, "goaldiff": 0, "total": 0}
        points["team_points"]["Draw"] = {"win": 0, "goaldiff": 0, "total": 10}
    
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
        motm_bonus = 20 if player == motm else 0
        p_pts = (goals * 10) + motm_bonus
        points["player_points"][player] = {"goals": goals * 10, "motm": motm_bonus, "total": p_pts}
        
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

    pre_t_teams = pre_t.get("teams", [])
    raw_pre_t_players = pre_t.get("players", [])
    
    pre_t_players = []
    for p in raw_pre_t_players:
        if isinstance(p, dict):
            pre_t_players.append(str(p.get('name', '')).strip().lower())
        else:
            pre_t_players.append(str(p).strip().lower())
    
    team_pick = daily.get('teams', {}).get(match_id)
    raw_player_picks = daily.get('players', [])

    player_picks = []
    for p in raw_player_picks:
        name = p.get('name', p) if isinstance(p, dict) else p
        player_picks.append(str(name).strip().lower())
    
    team_pts = get_total(m_points.get('team_points', {}).get(team_pick, 0))
    team_multiplier = (team_pick in pre_t_teams)
    final_team_pts = team_pts * 2 if team_multiplier else team_pts
    
    player_pts = 0
    player_points_db = m_points.get('player_points', {})
    db_player_map = {str(k).strip().lower(): v for k, v in player_points_db.items()}

    for p_norm in player_picks:
        p_pts = get_total(db_player_map.get(p_norm, 0))
        if p_norm in pre_t_players:
            p_pts *= 2
        player_pts += p_pts
    
    player_multiplier = any(p_norm in pre_t_players for p_norm in player_picks)

    return {
        "team_points": final_team_pts,
        "player_points": player_pts,
        "team_multiplier": team_multiplier,
        "player_multiplier": player_multiplier,
    }
