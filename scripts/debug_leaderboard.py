import sys
import os
import json
import firebase_admin
from firebase_admin import db, credentials

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import existing services
from src.db_service import get_all_users, get_pre_tournament_picks, get_daily_predictions
from src.config import CONFIG

def init_firebase():
    """Initializes Firebase if not already initialized."""
    if not firebase_admin._apps:
        # For local running, look for a local firebase-service-account.json or similar
        # Alternatively, prompt the user to set environment variable
        try:
            # Assumes a local service account file in project root
            cred_path = os.path.join(os.path.dirname(__file__), '..', 'firebase_creds.json')
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {
                'databaseURL': CONFIG.DATABASE_URL
            })
        except Exception as e:
            print(f"Error initializing Firebase: {e}")
            print("Ensure 'firebase-service-account.json' exists in project root.")
            sys.exit(1)

init_firebase()

from src.db_service import get_all_users, get_pre_tournament_picks, get_daily_predictions

def debug_user_points_calc(email: str):
    print(f"--- DEBUGGING CALCULATION FOR: {email} ---")
    
    # 1. Fetch data
    users = get_all_users()
    if email not in users:
        print(f"User {email} not found.")
        return
    
    # Fetch picks
    pre_t = get_pre_tournament_picks(email)
    pre_t_teams = pre_t.get("teams", [])

    # Correctly extract names from the list of objects
    raw_pre_t_players = pre_t.get("players", [])
    pre_t_players = []
    for p in raw_pre_t_players:
        if isinstance(p, dict):
            pre_t_players.append(str(p.get('name', '')).strip().lower())
        else:
            pre_t_players.append(str(p).strip().lower())

    print(f"Pre-T Teams: {pre_t_teams}")
    print(f"Pre-T Players: {pre_t_players}")
    
    # Fetch all matches and points
    all_match_points = db.reference("match_points").get() or {}
    
    grand_total = 0
    
    for match_id, m_points in all_match_points.items():
        date = m_points.get("et_date")
        daily = get_daily_predictions(email, date)
        
        team_pick = daily.get('teams', {}).get(match_id)
        player_picks = daily.get('players', [])
        
        print(f"\n--- Match: {match_id} (Date: {date}) ---")
        print(f"User Picks - Team: {team_pick}, Players: {player_picks}")
        
        # Team points
        team_data = m_points.get('team_points', {}).get(team_pick, {})
        win_pts = team_data.get("win", 0)
        gd_pts = team_data.get("goaldiff", 0)
        base_team_total = team_data.get("total", 0)
        
        team_multiplier = (team_pick in pre_t_teams)
        final_team_pts = base_team_total * 2 if team_multiplier else base_team_total
        
        print(f"Team: {team_pick}")
        print(f"  Win Pts: {win_pts}, GD Pts: {gd_pts}, Base Total: {base_team_total}")
        print(f"  Multiplier: {team_multiplier}, Final Team Pts: {final_team_pts}")
        
        # Player points
        player_pts_total = 0
        print("Player Breakdown:")
        for p in player_picks:
            # Normalize for DB lookup
            p_name = p.get('name', p) if isinstance(p, dict) else p
            norm_p_name = str(p_name).strip().lower()
            
            # Need to find base points in DB by normalized name
            # Assuming match_points/player_points keys are already somewhat normalized
            # This logic might need refinement based on how player_points are stored
            p_data = m_points.get('player_points', {}).get(p_name, {})
            goals_pts = p_data.get("goals", 0)
            motm_pts = p_data.get("motm", 0)
            base_p_total = p_data.get("total", 0)
            
            p_multiplier = (norm_p_name in pre_t_players)
            final_p_pts = base_p_total * 2 if p_multiplier else base_p_total
            
            player_pts_total += final_p_pts
            print(f"  - {p_name}: Goals Pts: {goals_pts}, MOTM Pts: {motm_pts}, Base Total: {base_p_total}")
            print(f"    Multiplier: {p_multiplier}, Final: {final_p_pts}")
            
        match_total = final_team_pts + player_pts_total
        print(f"Total Match Pts: {match_total}")
        grand_total += match_total
        
    print(f"\n--- GRAND TOTAL: {grand_total} ---")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_leaderboard.py <user_email>")
    else:
        # Assuming app is initialized elsewhere if imported, 
        # or initialize here if needed based on project structure
        debug_user_points_calc(sys.argv[1])
