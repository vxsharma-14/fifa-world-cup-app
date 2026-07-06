"""Pure data-access layer handling all Firebase Realtime Database interactions."""

import hashlib
import zoneinfo
from datetime import datetime, timedelta, timezone

import streamlit as st
from firebase_admin import db
from src.pre_tournament import (
    normalize_player_pick,
    normalize_pre_tournament_picks,
    normalize_team_pick,
)

# US Pacific Time (PDT) is UTC-7
PT_OFFSET = timedelta(hours=-7)
PT = zoneinfo.ZoneInfo("US/Pacific")


def _clear_cached_reads() -> None:
    """Clears cached read helpers after a write."""
    for fn in (
        get_scheduled_matches,
        get_matches_by_date,
        get_match_results,
        get_rosters,
        get_all_users,
        get_all_roster_players,
    ):
        try:
            fn.clear()
        except Exception:
            pass

def get_match_cutoff_dt(kickoff_iso: str) -> datetime:
    """Calculates the 15-minute cutoff for a match in PT."""
    kickoff_dt = datetime.fromisoformat(kickoff_iso).astimezone(PT)
    return kickoff_dt - timedelta(minutes=15)

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
        "name": name.strip().title(),
        "password_hash": hash_password(password_raw),
        "is_active": True
    })
    get_all_users.clear()

def reset_user_password(email: str, generic_password: str = "123456") -> None:
    """Admin tool to override a user's password."""
    db.reference(f"users/{clean_email_key(email)}/password_hash").set(hash_password(generic_password))

@st.cache_data(show_spinner=False)
def get_scheduled_matches() -> dict:
    """Fetches all scheduled matches across all dates, returns a flat dict of all matches."""
    all_dates_ref = db.reference("metadata").get() or {}
    all_matches = {}
    for date, matches in all_dates_ref.items():
        if isinstance(matches, dict):
            all_matches.update(matches)
    return all_matches

@st.cache_data(show_spinner=False)
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

def save_structured_match(
    match_id: str,
    home: str,
    away: str,
    kickoff_iso: str,
    display_str: str,
    scoring_stage: str = "league",
) -> None:
    """Saves a match node with the date-indexed structure: metadata/{date}/{match_id}."""
    kickoff_dt = datetime.fromisoformat(kickoff_iso)
    date_key = get_pt_date_key(kickoff_dt)
    
    db.reference(f"metadata/{date_key}/{match_id}").set({
        "id": match_id,
        "home_team": home,
        "away_team": away,
        "kickoff_time": kickoff_iso,
        "display_string": display_str,
        "scoring_stage": scoring_stage,
        "status": "scheduled"
    })
    _clear_cached_reads()

def update_matches(matches_list: list) -> None:
    """Pushes an updated list of raw match strings to metadata storage."""
    db.reference("metadata/matches").set(matches_list)

def get_pre_tournament_picks(email: str) -> dict:
    """Fetches locked pre-tournament selections for a specific profile."""
    data = db.reference(f"pre_tournament/{clean_email_key(email)}").get() or {}
    return normalize_pre_tournament_picks(data)

def save_pre_tournament_picks(email: str, teams: list, players: list) -> None:
    """Saves locked pre-tournament choices to database tracking."""
    normalized_teams = []
    for team in teams:
        normalized_team = normalize_team_pick(team)
        if normalized_team["name"]:
            normalized_teams.append(normalized_team)

    normalized_players = []
    for player in players:
        normalized_player = normalize_player_pick(player)
        if normalized_player["name"]:
            normalized_players.append(normalized_player)

    db.reference(f"pre_tournament/{clean_email_key(email)}").set({
        "teams": normalized_teams,
        "players": normalized_players,
        "submitted_at": get_pt_timestamp()
    })

def get_daily_predictions(email: str, date: str) -> dict:
    """Retrieves matchday choices for a specific user and date."""
    return db.reference(f"daily_predictions/{clean_email_key(email)}/{date}").get() or {}

def save_daily_predictions(email: str, date: str, match_winners_map: dict, daily_players: list) -> None:
    """Locks user selections for a specific date's match winners and target dynamic players."""
    
    # Normalize players
    normalized_players = []
    for p in daily_players:
        if isinstance(p, dict):
            p['name'] = p.get('name', '').strip().title()
            p['team'] = p.get('team', '').strip().title()
            normalized_players.append(p)
        else:
            normalized_players.append(str(p).strip().title())

    db.reference(f"daily_predictions/{clean_email_key(email)}/{date}").set({
        "teams": {k: v.strip() for k, v in match_winners_map.items()},
        "players": normalized_players,
        "submitted_at": get_pt_timestamp()
    })

def delete_all_matches() -> None:
    """Clears out the entire match schedule metadata node."""
    db.reference("metadata/matches").delete()
    _clear_cached_reads()

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

    scoring_stage = result_data.get("scoring_stage") or target_match.get("scoring_stage", "league")

    # Update match metadata with results and status
    match_ref = db.reference(f"metadata/{target_date}/{match_id}")
    match_ref.update({
        "results": result_data,
        "scoring_stage": scoring_stage,
        "status": "completed"
    })

    # Trigger entity-level point update
    update_match_points_node(
        match_id,
        result_data,
        target_date,
        target_match.get("home_team"),
        target_match.get("away_team"),
        scoring_stage,
    )
    _clear_cached_reads()

@st.cache_data(show_spinner=False)
def get_match_results() -> dict:
    """Fetches all submitted match results from the database."""
    return db.reference("results").get() or {}

def get_user_match_breakdown(email: str, date: str, match_id: str) -> dict:
    """Retrieves a user's points breakdown for a specific match."""
    return db.reference(f"user_points/{clean_email_key(email)}/daily_breakdown/{date}/matches/{match_id}").get() or {}

def get_match_points_breakdown(match_id: str) -> dict:
    """Retrieves granular points breakdown (player/team) for a specific match."""
    return db.reference(f"match_points/{match_id}").get() or {}

@st.cache_data(show_spinner=False)
def get_all_users() -> dict:
    """Fetches all registered users from the system."""
    return db.reference("users").get() or {}


def set_user_active(email: str, is_active: bool) -> None:
    """Enables or disables a user without deleting their data."""
    db.reference(f"users/{clean_email_key(email)}").update({
        "is_active": is_active
    })
    get_all_users.clear()


@st.cache_data(show_spinner=False)
def get_rosters() -> dict[str, list[str]]:
    """Fetches all country rosters from the system.

    Returns:
        Mapping of country team names to roster player names.
    """
    rosters = db.reference("rosters").get() or {}
    normalized_rosters = {}
    for team, players in rosters.items():
        team_name = str(team).strip()
        if not team_name or not isinstance(players, list):
            continue

        normalized_rosters[team_name] = [
            str(player).strip()
            for player in players
            if str(player).strip()
        ]

    return normalized_rosters


def get_favorite_players(email: str) -> list[dict[str, str]]:
    """Fetches a user's favorite player watchlist.

    Args:
        email: User email address.

    Returns:
        List of favorite player dictionaries with name and team values.
    """
    favorites = db.reference(f"favorite_players/{clean_email_key(email)}").get() or []
    if not isinstance(favorites, list):
        return []

    normalized_favorites = []
    for player in favorites:
        if not isinstance(player, dict):
            continue

        name = str(player.get("name", "")).strip()
        team = str(player.get("team", "")).strip()
        if name and team:
            normalized_favorites.append({"name": name, "team": team})

    return normalized_favorites


def save_favorite_players(email: str, favorite_players: list[dict[str, str]]) -> None:
    """Saves a user's favorite player watchlist.

    Args:
        email: User email address.
        favorite_players: Favorite player dictionaries with name and team values.
    """
    normalized_players = []
    seen_players = set()

    for player in favorite_players:
        name = str(player.get("name", "")).strip()
        team = str(player.get("team", "")).strip()
        player_key = (name.lower(), team.lower())

        if not name or not team or player_key in seen_players:
            continue

        seen_players.add(player_key)
        normalized_players.append({"name": name, "team": team})

    db.reference(f"favorite_players/{clean_email_key(email)}").set(normalized_players)

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

@st.cache_data(show_spinner=False)
def get_all_roster_players() -> list:
    """Fetches all player names across all teams from the rosters node."""
    all_players = []
    for players in get_rosters().values():
        all_players.extend(players)
    return sorted(list(set(all_players)))  # Unique and sorted


def get_roster_player_team_map() -> dict[str, str]:
    """Fetches a lookup map from roster player name to country team name.

    Returns:
        Mapping of player names to their associated country team names.
    """
    player_team_map = {}

    for team, players in get_rosters().items():
        for player in players:
            player_name = str(player).strip()
            if player_name and player_name not in player_team_map:
                player_team_map[player_name] = str(team).strip()

    return player_team_map
