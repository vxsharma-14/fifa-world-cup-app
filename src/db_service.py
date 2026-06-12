"""Pure data-access layer handling all Firebase Realtime Database interactions."""

import hashlib
from datetime import datetime, timedelta, timezone
from firebase_admin import db

def hash_password(password: str) -> str:
    """Hashes passwords using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def clean_email_key(email: str) -> str:
    """Replaces invalid '.' characters with '_' for Firebase keys."""
    return email.replace(".", "_")

def get_ist_timestamp() -> str:
    """Generates current timestamp formatted in Indian Standard Time (IST)."""
    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    return ist_now.strftime("%Y-%m-%d %I:%M:%S %p IST")

def get_user_data(email: str) -> dict | None:
    """Fetches user record by email."""
    return db.reference(f"users/{clean_email_key(email)}").get()

def create_user(email: str, name: str, password_raw: str) -> None:
    """Registers a new user inside the database nodes."""
    db.reference(f"users/{clean_email_key(email)}").set({
        "email": email,
        "name": name,
        "password_hash": hash_password(password_raw)
    })

def reset_user_password(email: str, generic_password: str = "123456") -> None:
    """Admin tool to override a user's password."""
    db.reference(f"users/{clean_email_key(email)}/password_hash").set(hash_password(generic_password))

def get_scheduled_matches() -> dict:
    """Fetches all scheduled match objects organized by their unique IDs."""
    return db.reference("metadata/matches").get() or {}

def save_structured_match(match_id: str, home: str, away: str, kickoff_iso: str, display_str: str) -> None:
    """Saves or updates a standardized match node with an explicit timeline validation string."""
    db.reference(f"metadata/matches/{match_id}").set({
        "id": match_id,
        "home_team": home,
        "away_team": away,
        "kickoff_time": kickoff_iso,
        "display_string": display_str
    })

def update_matches(matches_list: list) -> None:
    """Pushes an updated list of raw match strings to metadata storage."""
    db.reference("metadata/matches").set(matches_list)

def get_pre_tournament_picks(email: str) -> dict:
    """Fetches locked pre-tournament selections for a specific profile."""
    return db.reference(f"pre_tournament/{clean_email_key(email)}").get() or {}

def save_pre_tournament_picks(email: str, teams: list, players: list) -> None:
    """Saves locked pre-tournament choices to database tracking."""
    db.reference(f"pre_tournament/{clean_email_key(email)}").set({
        "teams": teams,
        "players": players,
        "submitted_at": get_ist_timestamp()
    })

def get_daily_predictions(email: str) -> dict:
    """Retrieves current matchday choices mapped to an email user."""
    return db.reference(f"daily_predictions/{clean_email_key(email)}").get() or {}

def save_daily_predictions(email: str, match_winners_map: dict, daily_players: list) -> None:
    """Locks user selections for today's match winners and target dynamic players."""
    db.reference(f"daily_predictions/{clean_email_key(email)}").set({
        "teams": match_winners_map,
        "players": daily_players,
        "submitted_at": get_ist_timestamp()
    })

def delete_all_matches() -> None:
    """Clears out the entire match schedule metadata node."""
    db.reference("metadata/matches").delete()


from src.scoring_engine import calculate_match_points

# ... (rest of imports)

def save_match_result(match_id: str, result_data: dict) -> None:
    """Saves finalized results and triggers incremental leaderboard update."""
    result_data["updated_at"] = get_ist_timestamp()
    db.reference(f"results/{match_id}").set(result_data)
    
    # Trigger incremental recalculation
    recalculate_and_save_user_points(match_id, result_data)

def recalculate_and_save_user_points(match_id: str, result_data: dict) -> None:
    """Incrementally updates participant points and leaderboard, excluding admins."""
    all_users = get_all_users()
    match_metadata = db.reference(f"metadata/matches/{match_id}").get()
    
    for email, user_info in all_users.items():
        # Filter out admins
        if "admin" in user_info.get("name", "").lower():
            continue
            
        # Get existing data
        pre_t_picks = get_pre_tournament_picks(email)
        daily_picks = get_daily_predictions(email)
        
        # Calculate new points
        new_breakdown = calculate_match_points(match_id, pre_t_picks, daily_picks, result_data, match_metadata)
        new_total_match = sum(new_breakdown.values())
        
        # Get old points from audit node to calculate delta
        old_audit = db.reference(f"points_audit/{email}/match_results/{match_id}").get() or {}
        old_total_match = old_audit.get("total_points", 0)
        
        # Update audit node
        db.reference(f"points_audit/{email}/match_results/{match_id}").set({
            **new_breakdown,
            "total_points": new_total_match,
            "updated_at": get_ist_timestamp()
        })
        
        # Update leaderboard node
        leaderboard_ref = db.reference(f"leaderboard/{email}")
        user_leaderboard = leaderboard_ref.get() or {"total_score": 0, "name": user_info["name"]}
        
        # Delta = new_points - old_points
        delta = new_total_match - old_total_match
        user_leaderboard["total_score"] = user_leaderboard.get("total_score", 0) + delta
        # Removed 'last_daily_score' as requested
        
        leaderboard_ref.update(user_leaderboard)
        
        # Track granular player and team stats
        track_player_and_team_stats(email, match_id, pre_t_picks, daily_picks, result_data)

def track_player_and_team_stats(email: str, match_id: str, pre_t_picks: dict, daily_picks: dict, result_data: dict) -> None:
    """Tracks granular stats for all player and team picks (as previously planned) and global stats."""
    
    # 1. Update Global Player Stats (regardless of user selection)
    all_scorers = result_data.get("home_scorers", []) + result_data.get("away_scorers", [])
    yellow_cards = result_data.get("yellow_cards", [])
    red_cards = result_data.get("red_cards", [])
    motm = result_data.get("player_of_the_match")
    
    # Get all unique players involved in the match results
    all_involved_players = set(all_scorers + yellow_cards + red_cards + ([motm] if motm else []))
    
    for player in all_involved_players:
        if not player: continue
        
        player_ref = db.reference(f"global_player_stats/{player}")
        stats = player_ref.get() or {"goals": 0, "yellow_cards": 0, "red_cards": 0, "motm": 0}
        
        stats["goals"] += all_scorers.count(player)
        stats["yellow_cards"] += yellow_cards.count(player)
        stats["red_cards"] += red_cards.count(player)
        if player == motm:
            stats["motm"] += 1
            
        player_ref.set(stats)

    # 2. Update Global Team Stats
    home_team = result_data.get("home_team") # Note: This data is not directly in result_data passed, 
                                            # we need metadata here, but simplifying for now.
    # Actually, we should pull team names from metadata
    match_meta = db.reference(f"metadata/matches/{match_id}").get()
    home = match_meta.get("home_team")
    away = match_meta.get("away_team")
    h_score = result_data.get("home_score", 0)
    a_score = result_data.get("away_score", 0)

    for team, goals, opponent_goals in [(home, h_score, a_score), (away, a_score, h_score)]:
        team_ref = db.reference(f"global_team_stats/{team}")
        stats = team_ref.get() or {"wins": 0, "draws": 0, "losses": 0, "goals_for": 0, "goals_against": 0}
        
        if goals > opponent_goals: stats["wins"] += 1
        elif goals < opponent_goals: stats["losses"] += 1
        else: stats["draws"] += 1
        
        stats["goals_for"] += goals
        stats["goals_against"] += opponent_goals
        
        team_ref.set(stats)

    # 3. (Optional) Keep existing user-specific tracking logic if needed, 
    # but based on requirements, the global stats seem to be the primary need.

def get_match_results() -> dict:
    """Fetches all submitted match results from the database."""
    return db.reference("results").get() or {}


def get_all_users() -> dict:
    """Fetches all registered users from the system."""
    return db.reference("users").get() or {}


def save_user_daily_override(email: str, match_id: str, team_pick: str, daily_players: list) -> None:
    """Admin tool to explicitly insert or override a specific match prediction for a user."""
    cleaned_email = clean_email_key(email)
    ref = db.reference(f"daily_predictions/{cleaned_email}")

    # Fetch current data to preserve other match predictions already made by the user
    current_data = ref.get() or {}
    teams_map = current_data.get("teams", {})

    # Update only the target match slot
    teams_map[match_id] = team_pick

    ref.set({
        "teams": teams_map,
        "players": daily_players,
        "submitted_at": f"{get_ist_timestamp()} (Admin WhatsApp Override)"
    })