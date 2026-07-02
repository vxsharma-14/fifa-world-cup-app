import unittest

from src.scoring_engine import calculate_match_points_for_db


class TestMatchPointsScoringRules(unittest.TestCase):
    """Validates stage-based match_points calculation rules."""

    def test_league_stage_uses_league_scoring_rules(self) -> None:
        """League matches use the configured league values."""
        result = {
            "home_score": 2,
            "away_score": 0,
            "home_scorers": ["Player One", "Player One"],
            "away_scorers": [],
            "player_of_the_match": "Player One",
        }

        points = calculate_match_points_for_db(result, "Team A", "Team B")

        self.assertEqual(points["scoring_stage"], "league")
        self.assertEqual(points["team_points"]["Team A"]["win"], 10)
        self.assertEqual(points["team_points"]["Team A"]["goaldiff"], 10)
        self.assertEqual(points["player_points"]["Player One"]["goals"], 20)
        self.assertEqual(points["player_points"]["Player One"]["motm"], 20)

    def test_round_of_32_uses_stage_scoring_rules(self) -> None:
        """Round of 32 matches use the configured knockout values."""
        result = {
            "home_score": 3,
            "away_score": 1,
            "home_scorers": ["Player One", "Player Two", "Player Two"],
            "away_scorers": ["Player Three"],
            "player_of_the_match": "Player Two",
        }

        points = calculate_match_points_for_db(result, "Team A", "Team B", "R32")

        self.assertEqual(points["scoring_stage"], "R32")
        self.assertEqual(points["team_points"]["Team A"]["win"], 20)
        self.assertEqual(points["team_points"]["Team A"]["goaldiff"], 20)
        self.assertEqual(points["team_points"]["Team B"]["goaldiff"], -20)
        self.assertEqual(points["player_points"]["Player Two"]["goals"], 40)
        self.assertEqual(points["player_points"]["Player Two"]["motm"], 40)

    def test_unknown_stage_falls_back_to_league_rules(self) -> None:
        """Unknown stages are saved and calculated as league stage."""
        result = {
            "home_score": 0,
            "away_score": 0,
            "home_scorers": [],
            "away_scorers": [],
            "player_of_the_match": "",
        }

        points = calculate_match_points_for_db(result, "Team A", "Team B", "unknown")

        self.assertEqual(points["scoring_stage"], "league")
        self.assertEqual(points["team_points"]["Draw"]["total"], 10)


if __name__ == "__main__":
    unittest.main()
