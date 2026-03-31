#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard compatibility of split database models facade exports."""

from __future__ import annotations

import unittest

from database import models
from database.models_analysis import ComprehensiveAnalysisModel, TeamPowerRatingHistoryModel
from database.models_core import (
    BaseModel,
    InviteCodeModel,
    LeagueModel,
    MatchModel,
    MatchStatus,
    MiniProgramUserModel,
    ScrapingLogModel,
    StandingModel,
    StandingType,
    TeamModel,
)
from database.models_odds import (
    CompanyModel,
    OddsChangeModel,
    OddsHistoryModel,
    OddsModel,
    OverUnderOddsChangeModel,
)


class ModelsSplitCompatibilityTests(unittest.TestCase):
    def test_facade_exports_match_split_modules(self):
        self.assertIs(models.BaseModel, BaseModel)
        self.assertIs(models.MatchStatus, MatchStatus)
        self.assertIs(models.StandingType, StandingType)
        self.assertIs(models.LeagueModel, LeagueModel)
        self.assertIs(models.TeamModel, TeamModel)
        self.assertIs(models.MatchModel, MatchModel)
        self.assertIs(models.CompanyModel, CompanyModel)
        self.assertIs(models.OddsModel, OddsModel)
        self.assertIs(models.OddsHistoryModel, OddsHistoryModel)
        self.assertIs(models.StandingModel, StandingModel)
        self.assertIs(models.ScrapingLogModel, ScrapingLogModel)
        self.assertIs(models.OddsChangeModel, OddsChangeModel)
        self.assertIs(models.OverUnderOddsChangeModel, OverUnderOddsChangeModel)
        self.assertIs(models.MiniProgramUserModel, MiniProgramUserModel)
        self.assertIs(models.InviteCodeModel, InviteCodeModel)
        self.assertIs(models.ComprehensiveAnalysisModel, ComprehensiveAnalysisModel)
        self.assertIs(models.TeamPowerRatingHistoryModel, TeamPowerRatingHistoryModel)

    def test_registry_and_factory_still_work(self):
        self.assertIs(models.get_model_class("league"), LeagueModel)
        self.assertIs(models.get_model_class("TEAM"), TeamModel)

        league = models.create_model_instance("league", {"league_id": 1, "name_cn": "测试联赛"})
        self.assertIsInstance(league, LeagueModel)
        self.assertEqual(league.league_id, 1)

        self.assertIsNone(models.create_model_instance("unknown_model", {"a": 1}))


if __name__ == "__main__":
    unittest.main()
