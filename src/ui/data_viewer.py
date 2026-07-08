"""Reusable module for secure, filtered, and cutoff-aware data access."""

from __future__ import annotations

from datetime import datetime, timedelta
import zoneinfo

import streamlit as st

from src.db_service import (
    get_all_users,
    get_daily_predictions,
    get_matches_by_date,
    get_match_points_breakdown,
    get_pre_tournament_history,
    get_pre_tournament_picks,
    get_scheduled_matches,
    get_user_match_breakdown,
)
from src.pre_tournament import apply_phase_multiplier, pick_multiplier_map, pick_names
from src.scoring_engine import get_active_pre_tournament_snapshot

PT = zoneinfo.ZoneInfo("US/Pacific")


def is_cutoff_passed(match_kickoff_iso: str) -> bool:
    """Checks if the match prediction cutoff (kickoff - 15m) has passed."""
    kickoff_dt = datetime.fromisoformat(match_kickoff_iso).astimezone(PT)
    cutoff_dt = kickoff_dt - timedelta(minutes=15)
    return datetime.now(PT) >= cutoff_dt


def get_authorized_predictions(
    target_email: str,
    target_date: str,
    viewer_email: str,
    is_admin: bool,
) -> dict:
    """Returns a user's daily predictions when access rules allow it."""
    if is_admin or target_email == viewer_email:
        return get_daily_predictions(target_email, target_date)

    all_matches = get_scheduled_matches()
    date_matches = [
        match
        for match in all_matches.values()
        if datetime.fromisoformat(match.get("kickoff_time", "")).astimezone(PT).strftime("%Y-%m-%d")
        == target_date
    ]
    if not date_matches:
        return {}

    earliest_match = min(date_matches, key=lambda x: x.get("kickoff_time", ""))
    if not is_cutoff_passed(earliest_match.get("kickoff_time", "")):
        return {}
    return get_daily_predictions(target_email, target_date)


def render_daily_prediction_card(
    email: str,
    date: str,
    match_id: str,
    match_data: dict,
    prediction: str,
    daily_players: list,
    performance_view: str = "Both",
) -> None:
    """Renders a structured insight card for a single match."""
    breakdown = get_user_match_breakdown(email, date, match_id)
    match_points = get_match_points_breakdown(match_id)
    results = match_data.get("results", {})
    is_completed = match_data.get("status") == "completed"

    with st.container(border=True):
        score = f"{results.get('home_score', '-')}" + f" - {results.get('away_score', '-')}" if results else "VS"
        st.markdown(f"#### {match_data['home_team']} {score} {match_data['away_team']}")

        if performance_view in ["Both", "Team"]:
            team_metrics = match_points.get("team_points", {}).get(prediction, {})
            is_mult = breakdown.get("team_multiplier", False)
            mult_factor = breakdown.get("team_multiplier_value", 2 if is_mult else 1)
            win_pts = apply_phase_multiplier(team_metrics.get("win", 0), mult_factor)
            gd_pts = apply_phase_multiplier(team_metrics.get("goaldiff", 0), mult_factor)
            total_pts = breakdown.get("team_points", 0)
            mult = f"{mult_factor}x" if is_mult else "No"

            with st.container(border=True):
                if is_completed:
                    st.metric(label=prediction, value=total_pts)
                    st.caption(f"Win: {win_pts} | GD: {gd_pts} | Mult: {mult}")
                else:
                    st.metric(label=prediction, value=None)
                    st.caption("To be calculated")


def render_player_performance_view(email: str, date: str, preds: dict) -> None:
    """Renders player performance using the phase-aware pre-tournament snapshot."""
    players = preds.get("players", [])
    if not players:
        st.info("No players selected for this date.")
        return

    st.markdown("#### Player Performance")
    pre_t = get_pre_tournament_picks(email)
    pre_t_history = get_pre_tournament_history(email)
    all_matches = get_scheduled_matches()
    matches_on_date = [
        match
        for match in all_matches.values()
        if datetime.fromisoformat(match.get("kickoff_time", "")).astimezone(PT).strftime("%Y-%m-%d")
        == date
    ]

    def _get_name(value: object) -> str:
        if isinstance(value, dict):
            return str(value.get("name", "")).strip()
        return str(value).strip()

    player_names = [_get_name(player) for player in players if _get_name(player)]
    aggregated_stats = {
        name: {
            "goals": 0,
            "motm": 0,
            "total": 0,
            "is_completed": False,
            "multipliers": set(),
        }
        for name in player_names
    }

    for match in matches_on_date:
        is_completed = match.get("status") == "completed"
        match_id = match.get("id")
        match_points = get_match_points_breakdown(match_id)
        player_points_map = match_points.get("player_points", {})
        active_pre_t = get_active_pre_tournament_snapshot(
            pre_t,
            pre_t_history,
            str(match_points.get("scoring_stage") or "league"),
        )
        match_multiplier_lookup = pick_multiplier_map(active_pre_t.get("players", []))

        for name in player_names:
            stats = player_points_map.get(name, {})
            mult_factor = match_multiplier_lookup.get(name.strip().lower(), 1)
            aggregated_stats[name]["multipliers"].add(mult_factor)
            aggregated_stats[name]["goals"] += apply_phase_multiplier(stats.get("goals", 0), mult_factor)
            aggregated_stats[name]["motm"] += apply_phase_multiplier(stats.get("motm", 0), mult_factor)
            aggregated_stats[name]["total"] += apply_phase_multiplier(stats.get("total", 0), mult_factor)
            if is_completed:
                aggregated_stats[name]["is_completed"] = True

    cols = st.columns(len(player_names))
    for index, col in enumerate(cols):
        name = player_names[index]
        stats = aggregated_stats.get(name, {})
        multipliers = sorted(stats.get("multipliers", {1}))
        if len(multipliers) == 1:
            mult_label = f"{multipliers[0]}x" if multipliers[0] > 1 else "No"
        else:
            mult_label = "Varies"

        with col.container(border=True):
            if stats["is_completed"]:
                st.metric(label=name, value=stats.get("total", 0))
                st.caption(
                    f"Goals: {stats.get('goals', 0)} | MOTM: {stats.get('motm', 0)} | Mult: {mult_label}"
                )
            else:
                st.metric(label=name, value=None)
                st.caption("To be calculated")


def render_filtered_participant_view(viewer_email: str, is_admin: bool) -> None:
    """Reusable UI for filtered participant data viewing."""
    all_users = get_all_users()
    user_options = {
        "All": "All",
        **{
            email: user.get("name", email)
            for email, user in all_users.items()
            if "admin" not in user.get("name", "").lower()
        },
    }

    selected_key = st.pills(
        "Select Participant:",
        options=list(user_options.keys()),
        format_func=lambda key: user_options[key],
        selection_mode="single",
    )
    if not selected_key:
        st.info("Please select a participant to view their data.")
        return

    selected_email = selected_key
    view_type = st.pills(
        "Select Data View:",
        options=["Pre-Tournament", "Daily Predictions"],
        selection_mode="single",
    )
    if not view_type:
        return

    if view_type == "Pre-Tournament":
        st.subheader(f"🛡️ Pre-Tournament Picks: {user_options[selected_email]}")
        if selected_key == "All":
            rows = []
            for email, user in all_users.items():
                if "admin" in user.get("name", "").lower():
                    continue

                pre_t = get_pre_tournament_picks(email)
                teams = pick_names(pre_t.get("teams", []))
                players = [p.get("name", p) if isinstance(p, dict) else p for p in pre_t.get("players", [])]
                row = {"User": user.get("name", email)}
                for i in range(2):
                    row[f"Team {i + 1}"] = teams[i] if i < len(teams) else ""
                for i in range(5):
                    row[f"Player {i + 1}"] = players[i] if i < len(players) else ""
                rows.append(row)

            st.table(rows)
            return

        pre_t = get_pre_tournament_picks(selected_email)
        pre_t_history = get_pre_tournament_history(selected_email)
        if not pre_t:
            st.info("No picks found for this user.")
            return

        teams = pick_names(pre_t.get("teams", []))
        players_raw = pre_t.get("players", [])
        players = [p.get("name", p) if isinstance(p, dict) else p for p in players_raw]

        team_points_map = {t: 0 for t in teams}
        team_played_map = {t: False for t in teams}
        team_wins = {t: 0 for t in teams}
        team_losses = {t: 0 for t in teams}
        team_draws = {t: 0 for t in teams}
        team_gd = {t: 0 for t in teams}

        player_points_map_total = {p: 0 for p in players}
        player_goals_map = {p: 0 for p in players}
        player_motm_map = {p: 0 for p in players}
        player_played_map = {p: False for p in players}

        all_dates_matches = get_matches_by_date()
        for date, matches_on_date in all_dates_matches.items():
            if not isinstance(matches_on_date, dict):
                continue

            daily_picks = get_daily_predictions(selected_email, date)
            daily_players = [
                str(p.get("name", p) if isinstance(p, dict) else p).strip().lower()
                for p in daily_picks.get("players", [])
            ]

            for match_id, match_data in matches_on_date.items():
                if match_data.get("status") != "completed":
                    continue

                m_points = get_match_points_breakdown(match_id)
                breakdown = get_user_match_breakdown(selected_email, date, match_id)
                active_pre_t = get_active_pre_tournament_snapshot(
                    pre_t,
                    pre_t_history,
                    str(m_points.get("scoring_stage") or "league"),
                )
                multiplier_lookup = pick_multiplier_map(active_pre_t.get("players", []))

                for team in teams:
                    t_metrics = m_points.get("team_points", {}).get(team)
                    if t_metrics is None:
                        continue
                    team_points_map[team] += breakdown.get("team_points", 0)
                    team_played_map[team] = True
                    win_val = t_metrics.get("win", 0)
                    gd_val = t_metrics.get("goaldiff", 0)
                    team_gd[team] += int(gd_val / 5)
                    if win_val == 10:
                        team_wins[team] += 1
                    elif gd_val == 0:
                        team_draws[team] += 1
                    else:
                        team_losses[team] += 1

                player_points_map = m_points.get("player_points", {})
                normalized_player_map = {
                    str(key).strip().lower(): value for key, value in player_points_map.items()
                }
                for player in players:
                    player_key = str(player).strip().lower()
                    if player_key not in daily_players:
                        continue
                    player_stats = normalized_player_map.get(player_key, {})
                    if not player_stats:
                        continue
                    multiplier = multiplier_lookup.get(player_key, 1)
                    player_points_map_total[player] += apply_phase_multiplier(
                        player_stats.get("total", 0),
                        multiplier,
                    )
                    player_goals_map[player] += player_stats.get("goals", 0)
                    player_motm_map[player] += player_stats.get("motm", 0)
                    player_played_map[player] = True

        st.markdown("#### 🛡️ Pre-t Teams")
        for index in range(0, len(teams), 3):
            cols = st.columns(3)
            for offset, col in enumerate(cols):
                if index + offset >= len(teams):
                    continue
                team_name = teams[index + offset]
                with col.container(border=True):
                    if team_played_map.get(team_name, False):
                        st.metric(label=team_name, value=f"{team_points_map.get(team_name, 0)} pts")
                        st.caption(
                            f"W: {team_wins.get(team_name, 0)} | "
                            f"L: {team_losses.get(team_name, 0)} | "
                            f"D: {team_draws.get(team_name, 0)} | "
                            f"GD: {team_gd.get(team_name, 0)}"
                        )
                    else:
                        st.metric(label=team_name, value="-")
                        st.caption("Not played yet")

        st.markdown("#### 👤 Pre-t Players")
        if players:
            cols = st.columns(len(players))
            for index, col in enumerate(cols):
                if index >= len(players):
                    continue
                player_name = players[index]
                with col.container(border=True):
                    if player_played_map.get(player_name, False):
                        st.metric(label=player_name, value=f"{player_points_map_total.get(player_name, 0)} pts")
                        st.caption(
                            f"G: {int(player_goals_map.get(player_name, 0) / 10)} | "
                            f"MOTM: {int(player_motm_map.get(player_name, 0) / 20)}"
                        )
                    else:
                        st.metric(label=player_name, value="-")
                        st.caption("Not played yet")
        return

    all_matches = get_scheduled_matches()
    available_dates = sorted(
        {
            datetime.fromisoformat(match.get("kickoff_time", "")).astimezone(PT).strftime("%Y-%m-%d")
            for match in all_matches.values()
        }
    )

    selected_dates = st.multiselect(
        "Select Dates:",
        options=available_dates,
        placeholder="Select dates ...",
    )
    if not selected_dates:
        return

    if selected_key == "All":
        st.subheader("📊 Aggregated Daily Predictions")
        rows = []
        for email, user in all_users.items():
            if "admin" in user.get("name", "").lower():
                continue

            row = {"User": user.get("name", email)}
            for date in selected_dates:
                preds = get_authorized_predictions(email, date, viewer_email, is_admin)
                teams_map = preds.get("teams", {})
                players = preds.get("players", [])

                date_matches = [
                    match
                    for match in all_matches.values()
                    if datetime.fromisoformat(match.get("kickoff_time", "")).astimezone(PT).strftime("%Y-%m-%d")
                    == date
                ]
                for match in date_matches:
                    match_id = match.get("id")
                    match_name = f"{match.get('home_team')} vs {match.get('away_team')}"
                    row[match_name] = teams_map.get(match_id, "-")

                for index in range(2):
                    if index < len(players) and isinstance(players[index], dict):
                        row[f"Player {index + 1}"] = players[index].get("name", players[index])
                    elif index < len(players):
                        row[f"Player {index + 1}"] = players[index]
                    else:
                        row[f"Player {index + 1}"] = "-"

            rows.append(row)

        if rows:
            st.table(rows)
        return

    perf_category = st.pills("Select View:", options=["Team", "Player"], selection_mode="single")
    if not perf_category:
        return

    matches_in_range = []
    for match_id, match in all_matches.items():
        dt_str = datetime.fromisoformat(match.get("kickoff_time", "")).astimezone(PT).strftime("%Y-%m-%d")
        if dt_str in selected_dates:
            matches_in_range.append((match_id, match, dt_str))

    if perf_category == "Team":
        match_options = {
            match_id: f"{match.get('home_team')} vs {match.get('away_team')} ({date})"
            for match_id, match, date in matches_in_range
        }
        selected_match_ids = st.multiselect(
            "Select Matches:",
            options=list(match_options.keys()),
            format_func=lambda key: match_options[key],
        )

        for date in selected_dates:
            st.markdown(f"### Predictions for {date}")
            preds = get_authorized_predictions(selected_email, date, viewer_email, is_admin)
            if not preds:
                st.warning(f"Data for {date} is locked or not available.")
                continue

            teams_map = preds.get("teams", {})
            daily_players = preds.get("players", [])
            matches_to_render = []
            for match_id, prediction in teams_map.items():
                if selected_match_ids and match_id not in selected_match_ids:
                    continue
                match_data = next(
                    (match for m_id, match, match_date in matches_in_range if m_id == match_id and match_date == date),
                    None,
                )
                if match_data:
                    matches_to_render.append((match_id, match_data, prediction))

            for index in range(0, len(matches_to_render), 2):
                cols = st.columns(2)
                for offset, col in enumerate(cols):
                    if index + offset >= len(matches_to_render):
                        continue
                    match_id, match_data, prediction = matches_to_render[index + offset]
                    with col:
                        render_daily_prediction_card(
                            selected_email,
                            date,
                            match_id,
                            match_data,
                            prediction,
                            daily_players,
                            performance_view="Team",
                        )

    elif perf_category == "Player":
        for date in selected_dates:
            st.markdown(f"### Predictions for {date}")
            preds = get_authorized_predictions(selected_email, date, viewer_email, is_admin)
            if not preds:
                st.warning(f"Data for {date} is locked or not available.")
                continue
            render_player_performance_view(selected_email, date, preds)
