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


def save_match_result(match_id: str, result_data: dict) -> None:
    """Saves or updates the finalized results and stats for a completed match."""
    result_data["updated_at"] = get_ist_timestamp()
    db.reference(f"results/{match_id}").set(result_data)

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