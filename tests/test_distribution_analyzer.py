import unittest

from fundamental_analysis.confidence_parser import (
    ConfidenceParseResult,
    HeadToHeadStats,
    RecentMatchInfo,
    TeamStats,
)
from fundamental_analysis.distribution_analyzer import (
    DistributionAnalyzer,
    DistributionNode,
    TeamPower,
)


def make_match(is_home, gf, ga, opp_rank=10, league_size=20):
    match = RecentMatchInfo()
    match.is_home = is_home
    match.goals_for = gf
    match.goals_against = ga
    match.goal_diff = gf - ga
    match.result = 1 if match.goal_diff > 0 else (-1 if match.goal_diff < 0 else 0)
    match.opponent_rank = opp_rank
    match.opponent_league_size = league_size
    return match


class DistributionAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = DistributionAnalyzer()

    def test_handicap_offset_runs_before_reverse_noop(self):
        reason, node = self.analyzer._apply_handicap(
            DistributionNode.NI_RUO_GAO_PING,
            hs=-2,
            as_=1,
            handicap_line=0.5,
        )
        self.assertEqual(node, DistributionNode.GAO_PING)
        self.assertIn("抵冲成高平权重", reason)

    def test_ke_hui_zhu_home_win_can_override_recent_away_loss(self):
        parsed = ConfidenceParseResult()
        parsed.home_stats = TeamStats(league_position=8, league_total_teams=20, home_win_rate=60)
        parsed.away_stats = TeamStats(league_position=14, league_total_teams=20, away_win_rate=30)
        parsed.home_recent_matches = [
            make_match(False, 0, 1, opp_rank=7),
            make_match(True, 2, 0, opp_rank=9),
        ]
        parsed.away_recent_matches = [make_match(False, 0, 2, opp_rank=8)]

        result = self.analyzer.analyze(parsed, handicap_line=0.25)
        self.assertEqual(result.home_power.power_label, TeamPower.WIN_STRONG)
        self.assertIn("按主场胜为主", result.home_power.reasoning)
        self.assertIn("主场大胜", result.home_power.same_venue_reference)

    def test_ke_hui_zhu_strong_away_draw_stays_primary_when_home_win_is_low_quality(self):
        parsed = ConfidenceParseResult()
        parsed.home_stats = TeamStats(league_position=9, league_total_teams=20, home_win_rate=58)
        parsed.away_stats = TeamStats(league_position=11, league_total_teams=20, away_win_rate=28)
        parsed.home_recent_matches = [
            make_match(False, 2, 2, opp_rank=3),
            make_match(True, 1, 0, opp_rank=16),
        ]
        parsed.away_recent_matches = [make_match(False, 0, 1, opp_rank=10)]

        result = self.analyzer.analyze(parsed, handicap_line=0.25)
        self.assertEqual(result.home_power.power_label, TeamPower.WIN_MODERATE)
        self.assertIn("仍以客场平为主", result.home_power.reasoning)

    def test_zhu_hui_ke_home_loss_stays_losing_even_with_recent_away_win(self):
        parsed = ConfidenceParseResult()
        parsed.home_stats = TeamStats(league_position=7, league_total_teams=20, home_win_rate=52)
        parsed.away_stats = TeamStats(league_position=10, league_total_teams=20, away_win_rate=42)
        parsed.home_recent_matches = [make_match(True, 2, 0, opp_rank=11)]
        parsed.away_recent_matches = [
            make_match(True, 0, 1, opp_rank=9),
            make_match(False, 1, 0, opp_rank=12),
        ]

        result = self.analyzer.analyze(parsed, handicap_line=0.0)
        self.assertEqual(result.away_power.power_label, TeamPower.LOSS_SOFT)
        self.assertIn("输球本质不变", result.away_power.reasoning)

    def test_h2h_uses_real_recent_streak_instead_of_win_rate_estimate(self):
        parsed = ConfidenceParseResult()
        parsed.home_stats = TeamStats(league_position=10, league_total_teams=20, home_win_rate=40)
        parsed.away_stats = TeamStats(league_position=10, league_total_teams=20, away_win_rate=30)
        parsed.home_recent_matches = [make_match(True, 1, 1, opp_rank=10)]
        parsed.away_recent_matches = [make_match(False, 0, 0, opp_rank=10)]
        parsed.h2h = HeadToHeadStats(
            total_matches=4,
            home_wins=2,
            draws=2,
            away_wins=0,
            home_win_rate=50.0,
            draw_rate=50.0,
            away_win_rate=0.0,
            recent_results=[1, 1, 0, -1],
            venue_results=[(True, 1), (False, 1), (True, 0), (False, -1)],
        )

        result = self.analyzer.analyze(parsed, handicap_line=0.0)
        self.assertEqual(result.distribution_node, DistributionNode.SHUN_RUO)
        self.assertIn("近2场连续占优", result.h2h_adjustment)


if __name__ == "__main__":
    unittest.main()
