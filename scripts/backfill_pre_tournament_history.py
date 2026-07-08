"""Backfills phase-tagged pre-tournament history snapshots for scoring."""

from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import datetime
from typing import Any

import firebase_admin
from firebase_admin import credentials, db

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import CONFIG, initialize_db
from src.db_service import clean_email_key, get_pt_timestamp
from src.pre_tournament import normalize_player_pick, normalize_team_pick

DEFAULT_BACKUP_PATH = "db_backup_02072026.json"
PHASE1_SUBMITTED_AT = "2026-06-10 09:30:00 AM PT"
PHASE2_SUBMITTED_AT = "2026-07-04 09:30:00 AM PT"
FIREBASE_CREDENTIAL_CANDIDATES = (
    "firebase_creds.json",
    "serviceAccountKey.json",
    "firebase-service-account.json",
)


def init_firebase() -> None:
    """Initializes Firebase Admin using the app config or a local credential file."""
    if firebase_admin._apps:
        return

    try:
        initialize_db()
    except Exception:
        pass

    if firebase_admin._apps:
        return

    for candidate in FIREBASE_CREDENTIAL_CANDIDATES:
        if os.path.exists(candidate):
            cred = credentials.Certificate(candidate)
            firebase_admin.initialize_app(cred, {"databaseURL": CONFIG.DATABASE_URL})
            return

    raise RuntimeError(
        "Firebase is not initialized. Provide Streamlit secrets or one of: "
        f"{', '.join(FIREBASE_CREDENTIAL_CANDIDATES)}"
    )


def load_backup(backup_path: str) -> dict[str, Any]:
    """Loads the JSON backup file from disk."""
    with open(backup_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def get_email_keys(backup_data: dict[str, Any], current_data: dict[str, Any]) -> list[str]:
    """Builds the union of users present in the backup and current database."""
    backup_users = set((backup_data.get("pre_tournament") or {}).keys())
    current_users = set(current_data.keys())
    return sorted(backup_users | current_users)


def normalize_phase_one_snapshot(raw_entry: dict[str, Any] | None) -> dict[str, Any]:
    """Normalizes a Phase 1 snapshot using the backup shape."""
    raw_entry = raw_entry or {}

    teams = [
        normalize_team_pick(team, default_phase="Phase1")
        for team in raw_entry.get("teams", [])
        if str(team).strip()
    ]
    players = [
        normalize_player_pick(player, default_phase="Phase1")
        for player in raw_entry.get("players", [])
        if str(player.get("name", "") if isinstance(player, dict) else player).strip()
    ]

    return {
        "phase": "Phase1",
        "changed": False,
        "submitted_at": PHASE1_SUBMITTED_AT,
        "source": "db_backup_02072026.json",
        "teams": teams,
        "players": players,
    }


def _normalized_name(value: Any) -> str:
    """Returns a stable comparison name for team/player records."""
    if isinstance(value, dict):
        value = value.get("name", "")
    return str(value).strip().lower()


def _phase_from_pick(value: Any, default_phase: str, fallback_name: str, reference_name: str) -> str:
    """Returns an explicit phase for a pick, preserving stored values where present."""
    if isinstance(value, dict):
        phase = str(value.get("phase") or "").strip()
        if phase:
            return phase
    if fallback_name and reference_name and fallback_name == reference_name:
        return "Phase1"
    return default_phase


def normalize_phase_two_snapshot(
    phase_one_entry: dict[str, Any] | None,
    current_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Normalizes a Phase 2 snapshot using the current live database state."""
    phase_one_entry = phase_one_entry or {}
    current_entry = current_entry or phase_one_entry

    phase_one_teams = phase_one_entry.get("teams", [])
    current_teams = current_entry.get("teams", [])

    normalized_teams = []
    for index, team in enumerate(current_teams):
        name = str(team.get("name", team) if isinstance(team, dict) else team).strip()
        if not name:
            continue

        reference_name = ""
        if index < len(phase_one_teams):
            reference_name = str(
                phase_one_teams[index].get("name", phase_one_teams[index])
                if isinstance(phase_one_teams[index], dict)
                else phase_one_teams[index]
            ).strip()

        phase = _phase_from_pick(team, "Phase2", _normalized_name(name), _normalized_name(reference_name))
        normalized_teams.append(normalize_team_pick({"name": name, "phase": phase}, default_phase=phase))

    phase_one_players = phase_one_entry.get("players", [])
    current_players = current_entry.get("players", [])

    normalized_players = []
    for index, player in enumerate(current_players):
        name = str(player.get("name", player) if isinstance(player, dict) else player).strip()
        if not name:
            continue

        team = str(player.get("team", "") if isinstance(player, dict) else "").strip()
        reference_name = ""
        if index < len(phase_one_players):
            reference_name = str(
                phase_one_players[index].get("name", phase_one_players[index])
                if isinstance(phase_one_players[index], dict)
                else phase_one_players[index]
            ).strip()

        phase = _phase_from_pick(player, "Phase2", _normalized_name(name), _normalized_name(reference_name))
        normalized_players.append(
            normalize_player_pick({"name": name, "team": team, "phase": phase}, default_phase=phase)
        )

    current_signature = {
        "teams": [_normalized_name(team) for team in current_teams],
        "players": [_normalized_name(player) for player in current_players],
    }
    phase_one_signature = {
        "teams": [_normalized_name(team) for team in phase_one_teams],
        "players": [_normalized_name(player) for player in phase_one_players],
    }

    return {
        "phase": "Phase2",
        "changed": current_signature != phase_one_signature,
        "submitted_at": PHASE2_SUBMITTED_AT,
        "source": "firebase_rtdb",
        "teams": normalized_teams,
        "players": normalized_players,
    }


def build_user_history(
    backup_entry: dict[str, Any] | None,
    current_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Builds the history payload for a single user."""
    phase_one_snapshot = normalize_phase_one_snapshot(backup_entry)
    phase_two_snapshot = normalize_phase_two_snapshot(backup_entry, current_entry)

    return {
        "phase1": phase_one_snapshot,
        "phase2": phase_two_snapshot,
        "backfilled_at": get_pt_timestamp(),
    }


def main() -> None:
    """Backfills pre-tournament history snapshots into Firebase."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backup",
        default=DEFAULT_BACKUP_PATH,
        help="Path to the Phase 1 backup JSON file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the payloads without writing to Firebase.",
    )
    args = parser.parse_args()

    init_firebase()
    backup_data = load_backup(args.backup)
    current_pre_tournament = db.reference("pre_tournament").get() or {}

    backup_pre_tournament = backup_data.get("pre_tournament") or {}
    all_emails = get_email_keys(backup_data, current_pre_tournament)

    if not all_emails:
        print("No pre-tournament users found in backup or current database.")
        return

    for email_key in all_emails:
        backup_entry = deepcopy(backup_pre_tournament.get(email_key))
        current_entry = deepcopy(current_pre_tournament.get(email_key))
        history_payload = build_user_history(backup_entry, current_entry)

        if args.dry_run:
            print(f"[DRY RUN] {email_key}")
            print(json.dumps(history_payload, indent=2, ensure_ascii=False))
            continue

        db.reference(f"pre_tournament_history/{email_key}").set(history_payload)
        print(f"Backfilled pre_tournament_history for {email_key}")


if __name__ == "__main__":
    main()
