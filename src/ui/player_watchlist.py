"""Player watchlist view for browsing rosters and saving favorites."""

import streamlit as st

from src.db_service import get_favorite_players, get_rosters, save_favorite_players


def _get_player_key(player: dict[str, str]) -> tuple[str, str]:
    """Builds a stable player identity key.

    Args:
        player: Player dictionary with name and team values.

    Returns:
        Normalized tuple identifying the player within a country roster.
    """
    return (
        str(player.get("name", "")).strip().lower(),
        str(player.get("team", "")).strip().lower(),
    )


def _toggle_favorite(
    email: str,
    player: dict[str, str],
    favorite_players: list[dict[str, str]],
) -> None:
    """Adds or removes a player from the user's favorite watchlist.

    Args:
        email: User email address.
        player: Player dictionary with name and team values.
        favorite_players: Current favorite player dictionaries.
    """
    target_key = _get_player_key(player)
    updated_favorites = [
        favorite
        for favorite in favorite_players
        if _get_player_key(favorite) != target_key
    ]

    if len(updated_favorites) == len(favorite_players):
        updated_favorites.append(player)

    save_favorite_players(email, updated_favorites)
    st.rerun()


def render_player_watchlist(email: str) -> None:
    """Renders country roster cards with user-specific favorite toggles.

    Args:
        email: Active user's email address.
    """
    rosters = get_rosters()

    st.subheader("Player Watchlist")

    if not rosters:
        st.info("No rosters have been added yet.")
        return

    country_options = sorted(rosters.keys())
    selected_country = st.selectbox(
        "Select Country",
        options=country_options,
        key="watchlist_country_select",
    )

    favorite_players = get_favorite_players(email)
    favorite_keys = {_get_player_key(player) for player in favorite_players}

    view_filter = st.radio(
        "Show",
        options=["All Players", "Favorites Only"],
        horizontal=True,
        key="watchlist_view_filter",
    )

    country_players = [
        {"name": str(player).strip(), "team": selected_country}
        for player in rosters.get(selected_country, [])
        if str(player).strip()
    ]

    if view_filter == "Favorites Only":
        country_players = [
            player
            for player in country_players
            if _get_player_key(player) in favorite_keys
        ]

    favorite_count = sum(
        1 for player in country_players if _get_player_key(player) in favorite_keys
    )
    st.caption(
        f"{len(country_players)} players shown"
        f" | {favorite_count} favorites in this view"
    )

    if not country_players:
        st.info("No favorite players found for this country.")
        return

    card_columns = st.columns(3)
    for index, player in enumerate(country_players):
        player_key = _get_player_key(player)
        is_favorite = player_key in favorite_keys
        button_label = "★ Favorited" if is_favorite else "☆ Favorite"
        button_type = "primary" if is_favorite else "secondary"

        with card_columns[index % 3]:
            with st.container(border=True):
                st.markdown(f"**{player['name']}**")
                st.caption(player["team"])
                if st.button(
                    button_label,
                    key=f"fav_{index}_{player_key[0]}_{player_key[1]}",
                    type=button_type,
                    use_container_width=True,
                ):
                    _toggle_favorite(email, player, favorite_players)
