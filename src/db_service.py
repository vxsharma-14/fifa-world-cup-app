"""Pure data-access layer handling all Firebase Realtime Database interactions."""

import hashlib
from datetime import datetime, timedelta, timezone
from firebase_admin import db

# US Pacific Time (PDT) is UTC-7
PT_OFFSET = timedelta(hours=-7)

def hash_password(password: str) -> str:
    """Hashes passwords using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def clean_email_key(email: str) -> str:
    """Replaces invalid '.' characters with '_' for Firebase keys."""
    return email.replace(".", "_")

def get_pt_timestamp() -> str:
    """Generates current timestamp formatted in Pacific Time (PT)."""
    utc_now = datetime.now(timezone.utc)
    pt_now = utc_now + PT_OFFSET
    return pt_now.strftime("%Y-%m-%d %I:%M:%S %p PT")

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
    """Fetches all scheduled matches across all dates, returns a flat dict of all matches."""
    all_dates_ref = db.reference("metadata").get() or {}
    all_matches = {}
    for date, matches in all_dates_ref.items():
        if isinstance(matches, dict):
            all_matches.update(matches)
    return all_matches

def get_matches_by_date() -> dict:
    """Fetches the nested metadata structure: {date: {match_id: {...}}}."""
    return db.reference("metadata").get() or {}

def get_pt_date_key(dt: datetime = None) -> str:
    """Generates a YYYY-MM-DD key for a given datetime in PT."""
    if dt is None:
        dt = datetime.now(timezone(PT_OFFSET))
    else:
        dt = dt.astimezone(timezone(PT_OFFSET))
    return dt.strftime("%Y-%m-%d")

def save_structured_match(match_id: str, home: str, away: str, kickoff_iso: str, display_str: str) -> None:
    """Saves a match node with the date-indexed structure: metadata/{date}/{match_id}."""
    kickoff_dt = datetime.fromisoformat(kickoff_iso)
    date_key = get_pt_date_key(kickoff_dt)
    
    db.reference(f"metadata/{date_key}/{match_id}").set({
        "id": match_id,
        "home_team": home,
        "away_team": away,
        "kickoff_time": kickoff_iso,
        "display_string": display_str,
        "status": "scheduled"
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
        "submitted_at": get_pt_timestamp()
    })

def get_daily_predictions(email: str, date: str) -> dict:
    """Retrieves matchday choices for a specific user and date."""
    return db.reference(f"daily_predictions/{clean_email_key(email)}/{date}").get() or {}

def save_daily_predictions(email: str, date: str, match_winners_map: dict, daily_players: list) -> None:
    """Locks user selections for a specific date's match winners and target dynamic players."""
    db.reference(f"daily_predictions/{clean_email_key(email)}/{date}").set({
        "teams": match_winners_map,
        "players": daily_players,
        "submitted_at": get_pt_timestamp()
    })

def delete_all_matches() -> None:
    """Clears out the entire match schedule metadata node."""
    db.reference("metadata/matches").delete()

def save_match_result(match_id: str, result_data: dict) -> None:
    """Saves finalized results directly into the match metadata node and triggers entity scoring."""
    from src.scoring_service import update_match_points_node
    result_data["updated_at"] = get_pt_timestamp()

    # Need to find the match metadata to get the date
    all_dates = db.reference("metadata").get() or {}
    target_match = None
    target_date = None
    for date, matches in all_dates.items():
        if isinstance(matches, dict) and match_id in matches:
            target_match = matches[match_id]
            target_date = date
            break

    if not target_match:
        raise ValueError(f"Match {match_id} not found in metadata.")

    # Update match metadata with results and status
    match_ref = db.reference(f"metadata/{target_date}/{match_id}")
    match_ref.update({
        "results": result_data,
        "status": "completed"
    })

    # Trigger entity-level point update
    update_match_points_node(match_id, result_data, target_date, target_match.get("home_team"), target_match.get("away_team"))


def recalculate_and_save_user_points(match_id: str, result_data: dict) -> None:
    """Incrementally updates participant points and leaderboard, excluding admins."""
    from src.scoring_engine import calculate_match_points
    all_users = get_all_users()
    
    # Locate match in date-indexed metadata
    all_dates = db.reference("metadata").get() or {}
    match_metadata = None
    match_date = None
    for date, matches in all_dates.items():
        if isinstance(matches, dict) and match_id in matches:
            match_metadata = matches[match_id]
            match_date = date
            break
            
    if not match_metadata:
        raise ValueError(f"Match {match_id} not found in metadata.")
    
    for email, user_info in all_users.items():
        # Filter out admins
        if "admin" in user_info.get("name", "").lower():
            continue
            
        # Get existing data
        pre_t_picks = get_pre_tournament_picks(email)
        daily_picks = get_daily_predictions(email, match_date)
        
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
            "updated_at": get_pt_timestamp()
        })
        
        # Update leaderboard node
        leaderboard_ref = db.reference(f"leaderboard/{email}")
        user_leaderboard = leaderboard_ref.get() or {"total_score": 0, "name": user_info["name"]}
        
        # Delta = new_points - old_points
        delta = new_total_match - old_total_match
        user_leaderboard["total_score"] = user_leaderboard.get("total_score", 0) + delta
        
        leaderboard_ref.update(user_leaderboard)

def get_match_results() -> dict:
    """Fetches all submitted match results from the database."""
    return db.reference("results").get() or {}


def get_user_match_breakdown(email: str, date: str, match_id: str) -> dict:
    """Retrieves a user's points breakdown for a specific match."""
    return db.reference(f"user_points/{clean_email_key(email)}/daily_breakdown/{date}/matches/{match_id}").get() or {}

def get_match_points_breakdown(match_id: str) -> dict:
    """Retrieves granular points breakdown (player/team) for a specific match."""
    return db.reference(f"match_points/{match_id}").get() or {}

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
        "submitted_at": f"{get_pt_timestamp()} (Admin WhatsApp Override)"
    })