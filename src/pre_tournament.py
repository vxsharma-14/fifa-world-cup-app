"""Helpers for phase-aware pre-tournament pick data."""

from datetime import datetime
from typing import Any, Dict, List
import zoneinfo

DEFAULT_PRE_T_PHASE = "Phase1"
PRE_T_PHASE_MULTIPLIERS: Dict[str, float] = {
    "Phase1": 2.0,
    "Phase2": 1.5,
    "Phase3": 1.5,
}

PT = zoneinfo.ZoneInfo("US/Pacific")

PRE_T_BASELINE_CUTOFF = datetime(2026, 6, 14, 0, 15, tzinfo=PT)

PRE_T_CHANGE_WINDOWS: Dict[str, Dict[str, Any]] = {
    "Phase2": {
        "opens_at": datetime(2000, 1, 1, 0, 0, tzinfo=PT),
        "closes_at": datetime(2026, 7, 4, 9, 30, tzinfo=PT),
        "max_team_changes": 2,
        "max_player_changes": 2,
    },
}


def get_pick_name(pick: Any) -> str:
    """Returns the display/comparison name from a pick record."""
    if isinstance(pick, dict):
        return str(pick.get("name", "")).strip()
    return str(pick).strip()


def normalize_team_key(team_name: Any) -> str:
    """Builds a stable comparison key for team names by removing spaces."""
    return "".join(str(team_name).split()).lower()


def format_team_name(team_name: Any) -> str:
    """Formats a team name for storage/display."""
    return " ".join(str(team_name).split()).title()


def normalize_team_pick(pick: Any, default_phase: str = DEFAULT_PRE_T_PHASE) -> Dict[str, str]:
    """Normalizes a team pick into the phase-aware storage shape."""
    if isinstance(pick, dict):
        name = get_pick_name(pick).title()
        phase = str(pick.get("phase") or default_phase).strip()
    else:
        name = get_pick_name(pick).title()
        phase = default_phase

    return {"name": name, "phase": phase or default_phase}


def normalize_player_pick(pick: Any, default_phase: str = DEFAULT_PRE_T_PHASE) -> Dict[str, str]:
    """Normalizes a player pick into the phase-aware storage shape."""
    if isinstance(pick, dict):
        name = get_pick_name(pick)
        team = str(pick.get("team", "")).strip().title()
        phase = str(pick.get("phase") or default_phase).strip()
    else:
        name = get_pick_name(pick)
        team = ""
        phase = default_phase

    return {"name": name, "team": team, "phase": phase or default_phase}


def normalize_pre_tournament_picks(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes pre-tournament data while preserving non-pick metadata."""
    if not data:
        return {}

    normalized = dict(data)
    normalized["teams"] = [
        normalize_team_pick(team)
        for team in data.get("teams", [])
        if get_pick_name(team)
    ]
    normalized["players"] = [
        normalize_player_pick(player)
        for player in data.get("players", [])
        if get_pick_name(player)
    ]
    return normalized


def pick_names(picks: List[Any]) -> List[str]:
    """Returns non-empty names from a list of pick records."""
    return [name for name in (get_pick_name(pick) for pick in picks) if name]


def get_pick_phase(pick: Any) -> str:
    """Returns the phase assigned to a pick record."""
    if isinstance(pick, dict):
        phase = str(pick.get("phase") or DEFAULT_PRE_T_PHASE).strip()
        return phase or DEFAULT_PRE_T_PHASE
    return DEFAULT_PRE_T_PHASE


def get_phase_multiplier(phase: str) -> float:
    """Returns the configured multiplier for a pre-tournament pick phase."""
    return PRE_T_PHASE_MULTIPLIERS.get(phase, PRE_T_PHASE_MULTIPLIERS[DEFAULT_PRE_T_PHASE])


def get_pre_t_change_window(phase: str) -> Dict[str, Any]:
    """Returns the configured change window for a phase, if one exists."""
    return PRE_T_CHANGE_WINDOWS.get(phase, {})


def is_pre_t_change_window_open(
    phase: str,
    current_time: datetime | None = None,
) -> bool:
    """Checks whether a phase change window is open at the given time."""
    window = get_pre_t_change_window(phase)
    if not window:
        return False

    now = current_time or datetime.now(PT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=PT)
    else:
        now = now.astimezone(PT)

    return window["opens_at"] <= now < window["closes_at"]


def get_active_pre_t_phase(current_time: datetime | None = None) -> str:
    """Returns the active pre-tournament phase for the current PT time."""
    now = current_time or datetime.now(PT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=PT)
    else:
        now = now.astimezone(PT)

    phase2_window = PRE_T_CHANGE_WINDOWS.get("Phase2")
    if phase2_window and phase2_window["opens_at"] <= now < phase2_window["closes_at"]:
        return "Phase2"

    return DEFAULT_PRE_T_PHASE


def apply_phase_multiplier(points: int | float, multiplier: float) -> int | float:
    """Applies a phase multiplier while preserving whole-number point totals."""
    multiplied_points = points * multiplier
    if isinstance(multiplied_points, float) and multiplied_points.is_integer():
        return int(multiplied_points)
    return multiplied_points


def pick_multiplier_map(picks: List[Any]) -> Dict[str, float]:
    """Builds a normalized pick-name to multiplier lookup."""
    multipliers = {}
    for pick in picks:
        name = get_pick_name(pick).strip().lower()
        if name:
            multipliers[name] = get_phase_multiplier(get_pick_phase(pick))
    return multipliers
