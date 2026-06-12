import unittest
from src.scoring_engine import calculate_match_points

class TestScoringEngine(unittest.TestCase):
    def setUp(self):
        self.match_metadata = {"home_team": "Team A", "away_team": "Team B"}
        self.pre_t_picks = {"teams": ["Team A"]}

    def test_standard_win(self):
        # Setup: No Pre-T teams involved in this specific match
        match_metadata = {"home_team": "Team C", "away_team": "Team D"}
        pre_t_picks = {"teams": ["Team A"]} # Different Pre-T team
        daily_picks = {"teams": {"match_1": "Team D"}, "players": []}
        match_result = {"winning_team": "Team D"}
        
        breakdown = calculate_match_points("match_1", pre_t_picks, daily_picks, match_result, match_metadata)
        self.assertEqual(sum(breakdown.values()), 10)
        self.assertEqual(breakdown["match_winner"], 10)

    def test_pre_t_win_override(self):
        # Setup: Pre-T team A is playing
        match_metadata = {"home_team": "Team A", "away_team": "Team B"}
        pre_t_picks = {"teams": ["Team A"], "players": []}
        daily_picks = {"teams": {"match_1": "Team B"}, "players": []} # User predicts B
        match_result = {"winning_team": "Team A"} # A wins
        
        # Override A wins, points 20
        breakdown = calculate_match_points("match_1", pre_t_picks, daily_picks, match_result, match_metadata)
        self.assertEqual(sum(breakdown.values()), 20)
        self.assertEqual(breakdown["match_winner"], 20)

    def test_pre_t_team_loses(self):
        daily_picks = {"teams": {"match_1": "Team B"}, "players": []}
        match_result = {"winning_team": "Team B"}
        
        # User predicted Team B (or would have, but Pre-T locked it to A), A lost. 
        # Points should be 0.
        breakdown = calculate_match_points("match_1", self.pre_t_picks, daily_picks, match_result, self.match_metadata)
        self.assertEqual(sum(breakdown.values()), 0)

    def test_player_performance_standard(self):
        # Setup: Player scores and gets MotM
        match_metadata = {"home_team": "Team C", "away_team": "Team D"}
        pre_t_picks = {"teams": [], "players": []}
        daily_picks = {"teams": {}, "players": ["Player1"]}
        match_result = {
            "winning_team": "Team C",
            "home_scorers": ["Player1"],
            "player_of_the_match": "Player1"
        }
        
        # Goal (10) + MotM (20) = 30
        breakdown = calculate_match_points("match_1", pre_t_picks, daily_picks, match_result, match_metadata)
        self.assertEqual(sum(breakdown.values()), 30)
        self.assertEqual(breakdown["player_performance"], 30)

    def test_disciplinary_penalties(self):
        # Setup: Player gets yellow and red card
        match_metadata = {"home_team": "Team C", "away_team": "Team D"}
        pre_t_picks = {"teams": [], "players": []}
        daily_picks = {"teams": {}, "players": ["Player1"]}
        match_result = {
            "winning_team": "Team C",
            "yellow_cards": ["Player1"],
            "red_cards": ["Player1"]
        }
        
        # Yellow (-5) + Red (-10) = -15
        breakdown = calculate_match_points("match_1", pre_t_picks, daily_picks, match_result, match_metadata)
        self.assertEqual(sum(breakdown.values()), -15)
        self.assertEqual(breakdown["discipline"], -15)

    def test_goal_difference_bonus(self):
        # Setup: Predicted winner wins by 2 goals
        match_metadata = {"home_team": "Team C", "away_team": "Team D"}
        pre_t_picks = {"teams": [], "players": []}
        daily_picks = {"teams": {"match_1": "Team C"}, "players": []}
        match_result = {
            "winning_team": "Team C",
            "home_score": 3,
            "away_score": 1
        }
        
        # Winner pts(10) + GD pts(2*10=20) = 30
        breakdown = calculate_match_points("match_1", pre_t_picks, daily_picks, match_result, match_metadata)
        self.assertEqual(sum(breakdown.values()), 30)
        self.assertEqual(breakdown["goal_difference"], 20)
        self.assertEqual(breakdown["match_winner"], 10)

    def test_goal_difference_penalty_pre_t(self):
        # Setup: Pre-T Team C predicted to win but loses by 2 goals
        match_metadata = {"home_team": "Team C", "away_team": "Team D"}
        pre_t_picks = {"teams": ["Team C"], "players": []}
        daily_picks = {"teams": {"match_1": "Team C"}, "players": []}
        match_result = {
            "winning_team": "Team D",
            "home_score": 1,
            "away_score": 3
        }
        
        # Lose(0) - GD penalty(2*10*2=40) = -40
        breakdown = calculate_match_points("match_1", pre_t_picks, daily_picks, match_result, match_metadata)
        self.assertEqual(sum(breakdown.values()), -40)
        self.assertEqual(breakdown["goal_difference"], -40)

if __name__ == '__main__':
    unittest.main()
