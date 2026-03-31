#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分布评估模块 — 基于近一场+主客场转换的力度节点判断

核心权重逻辑（来自基本面方法论文档）：
  - 近一场 + 主客场转换  : ≥ 90%
  - 往绩 + 底层盘口      : ≤ 5%（仅微调，不改变大格局）

基准线：客观权重，不主观臆断。经验节点的本质是：
  让方有没有"赢球的支撑点"——有则顺弱，无则顺弱接近高平。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from fundamental_analysis.confidence_parser import (
    ConfidenceParseResult,
    RecentMatchInfo,
    TeamStats,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  单队权重等级
# ─────────────────────────────────────────────────────────────────────────────

class TeamPower:
    """近况权重等级（经主客场转换后）。数值供内部合并计算，标签供展示。"""

    WIN_STRONG    = "直接赢球权重"     # 5  稳定、明确赢球
    WIN_MODERATE  = "赢球想象"         # 4  有赢球想象，较稳定
    WIN_UNSTABLE  = "不稳定赢球想象"   # 3  赢球想象但容易被颠覆
    DRAW_WIN      = "逼平偏赢"         # 2  逼平带赢球倾向
    DRAW          = "逼平想象"         # 1  直接逼平权重
    DRAW_WEAK     = "弱逼平想象"       # 0  较弱的逼平
    LOSS_SOFT     = "输球想象弱"       # -1 有一点残留缓冲
    LOSS          = "输球想象"         # -2 明确输球方向
    LOSS_COMPLETE = "完全输球"         # -3 无任何赢球缓冲

    _SCORES: dict[str, int] = {
        "直接赢球权重":   5,
        "赢球想象":       4,
        "不稳定赢球想象": 3,
        "逼平偏赢":       2,
        "逼平想象":       1,
        "弱逼平想象":     0,
        "输球想象弱":    -1,
        "输球想象":      -2,
        "完全输球":      -3,
    }

    @classmethod
    def score(cls, power: str) -> int:
        return cls._SCORES.get(power, 0)

    @classmethod
    def from_score(cls, score: int) -> str:
        bounded = max(min(score, max(cls._SCORES.values())), min(cls._SCORES.values()))
        for label, value in cls._SCORES.items():
            if value == bounded:
                return label
        return cls.DRAW

    @classmethod
    def shift(cls, power: str, delta: int) -> str:
        return cls.from_score(cls.score(power) + delta)


# ─────────────────────────────────────────────────────────────────────────────
#  分布节点标签
# ─────────────────────────────────────────────────────────────────────────────

class DistributionNode:
    """力度分布节点（主队=让球方视角，正值=顺分布）"""

    # 顺分布（让球方/主队占优）
    SHUN_STRONG         = "顺强"
    SHUN_PIAN_QIANG     = "顺偏强"
    SHUN_ZHONG          = "顺中"
    SHUN_ZHONG_PIAN_RUO = "顺中偏弱"
    SHUN_RUO            = "顺弱"
    SHUN_RUO_GAO_PING   = "顺弱接近高平"

    # 中间区域
    GAO_PING            = "高平权重"
    CHONG_PIAN_SHUN     = "缓冲偏顺"
    CHONG_JUN_HENG      = "缓冲均衡"
    CHONG_PIAN_NI       = "缓冲偏逆"

    # 逆分布（受让方/客队占优）
    NI_RUO_GAO_PING     = "逆弱接近高平"
    NI_RUO              = "逆弱"
    NI_ZHONG_PIAN_RUO   = "逆中偏弱"
    NI_ZHONG            = "逆中"
    NI_PIAN_QIANG       = "逆偏强"
    NI_STRONG           = "逆强"


# ─────────────────────────────────────────────────────────────────────────────
#  数据结构
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TeamPowerResult:
    """单队分布权重评估结果"""
    power_label: str = ""          # TeamPower 中的标签
    base_result: str = ""          # 近一场原始结果描述
    position_type: str = ""        # 本场位 / 客回主 / 主回客
    distance: int = 0              # 连续在对场位的场次（距离效应）
    opponent_strength: str = ""    # stronger / similar / weaker
    same_venue_reference: str = "" # 本场位最近一次结果（用于客回主 / 主回客对照）
    reasoning: str = ""            # 推理说明（中文）
    goal_diff: int = 0
    goals_for: int = 0
    goals_against: int = 0


@dataclass
class DistributionResult:
    """最终分布评估结果"""
    distribution_node: str = ""
    home_power: TeamPowerResult = field(default_factory=TeamPowerResult)
    away_power: TeamPowerResult = field(default_factory=TeamPowerResult)
    raw_home_score: int = 0
    raw_away_score: int = 0
    handicap_adjustment: str = ""
    h2h_adjustment: str = ""
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "distribution_node": self.distribution_node,
            "home_power": {
                "power_label":        self.home_power.power_label,
                "base_result":        self.home_power.base_result,
                "position_type":      self.home_power.position_type,
                "distance":           self.home_power.distance,
                "opponent_strength":  self.home_power.opponent_strength,
                "same_venue_reference": self.home_power.same_venue_reference,
                "reasoning":          self.home_power.reasoning,
            },
            "away_power": {
                "power_label":        self.away_power.power_label,
                "base_result":        self.away_power.base_result,
                "position_type":      self.away_power.position_type,
                "distance":           self.away_power.distance,
                "opponent_strength":  self.away_power.opponent_strength,
                "same_venue_reference": self.away_power.same_venue_reference,
                "reasoning":          self.away_power.reasoning,
            },
            "raw_home_score":      self.raw_home_score,
            "raw_away_score":      self.raw_away_score,
            "handicap_adjustment": self.handicap_adjustment,
            "h2h_adjustment":      self.h2h_adjustment,
            "summary":             self.summary,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  主分析器
# ─────────────────────────────────────────────────────────────────────────────

class DistributionAnalyzer:
    """
    基本面分布评估器。

    使用方式::

        analyzer = DistributionAnalyzer()
        result = analyzer.analyze(parsed_result, handicap_line=0.75)
        print(result.distribution_node)
        print(result.summary)

    Args:
        handicap_line: 底层盘口让球数（主队视角，正数=主队让球）。
                       0.5=平半, 0.75=半一, 1.0=让一球, 0.0=平手盘。
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    def analyze(
        self,
        parsed: ConfidenceParseResult,
        handicap_line: float = 0.0,
    ) -> DistributionResult:
        result = DistributionResult()

        # 1. 评估主队权重
        home_power = self._evaluate_team(
            recent_matches=parsed.home_recent_matches,
            team_stats=parsed.home_stats,
            is_playing_home=True,
        )
        result.home_power = home_power
        result.raw_home_score = TeamPower.score(home_power.power_label)

        # 2. 评估客队权重
        away_power = self._evaluate_team(
            recent_matches=parsed.away_recent_matches,
            team_stats=parsed.away_stats,
            is_playing_home=False,
        )
        result.away_power = away_power
        result.raw_away_score = TeamPower.score(away_power.power_label)

        # 3. 确定分布节点（主权重 ≥90%）
        node = self._determine_node(
            result.raw_home_score,
            result.raw_away_score,
            home_power,
            away_power,
        )

        # 4. 底层盘口微调（≤5%，不改变大格局）
        handicap_adj, node = self._apply_handicap(
            node, result.raw_home_score, result.raw_away_score, handicap_line
        )
        result.handicap_adjustment = handicap_adj

        # 5. 往绩微调（≤5%，仅在边界条件触发）
        h2h_adj, node = self._apply_h2h(
            node, result.raw_home_score, result.raw_away_score, parsed
        )
        result.h2h_adjustment = h2h_adj

        result.distribution_node = node
        result.summary = self._build_summary(result, parsed.home_team, parsed.away_team)

        self.logger.info(
            "分布评估 [%s vs %s] → %s (主%+d 客%+d)",
            parsed.home_team, parsed.away_team, node,
            result.raw_home_score, result.raw_away_score,
        )
        return result

    # ─────────────────────────────────────────────────────────────────────────
    #  单队评估
    # ─────────────────────────────────────────────────────────────────────────

    def _evaluate_team(
        self,
        recent_matches: List[RecentMatchInfo],
        team_stats: TeamStats,
        is_playing_home: bool,
    ) -> TeamPowerResult:
        pr = TeamPowerResult()

        if not recent_matches:
            pr.power_label = TeamPower.DRAW
            pr.reasoning   = "无近期比赛数据，默认逼平想象"
            pr.position_type = "未知"
            return pr

        last = recent_matches[0]

        # 判断本场位 vs 对场位
        # 主队：上一场也是主场 → 本场位；否则 → 客回主
        # 客队：上一场也是客场 → 本场位；否则 → 主回客
        same_venue = (last.is_home == is_playing_home)
        if same_venue:
            position_type = "本场位"
        elif is_playing_home:
            position_type = "客回主"
        else:
            position_type = "主回客"

        pr.position_type   = position_type
        pr.goal_diff       = last.goal_diff
        pr.goals_for       = last.goals_for
        pr.goals_against   = last.goals_against

        # 对手相对实力
        opp_strength = self._opponent_strength(last, team_stats)
        pr.opponent_strength = opp_strength

        # 近一场文字描述
        pr.base_result = self._describe_match(last, opp_strength)

        # 距离效应（连续在对场位的额外场次）
        distance = 0
        if not same_venue:
            distance = self._count_distance(recent_matches, is_playing_home)
        pr.distance = distance

        # 本场位历史胜率质量
        venue_quality = self._venue_quality(team_stats, is_playing_home)
        venue_ref = None
        venue_ref_opp = "similar"
        if not same_venue:
            venue_ref = self._recent_current_venue_match(recent_matches, is_playing_home)
            if venue_ref:
                venue_ref_opp = self._opponent_strength(venue_ref, team_stats)
                pr.same_venue_reference = self._describe_match(venue_ref, venue_ref_opp)

        # 转换规则
        # 标注：
        # 1. 近一场为主锚点。
        # 2. 若近一场在对场位，则额外取“本场位最近一场”来判断你描述中的“遇胜 / 遇平 / 遇负”。
        # 3. distance 只负责描述连续对场位后的残留衰减。
        if position_type == "本场位":
            label, reason = self._same_venue(last, opp_strength, venue_quality)
        elif position_type == "客回主":
            label, reason = self._ke_hui_zhu(
                last, opp_strength, venue_quality, distance, venue_ref, venue_ref_opp
            )
        else:
            label, reason = self._zhu_hui_ke(
                last, opp_strength, venue_quality, distance, venue_ref, venue_ref_opp
            )

        pr.power_label = label
        pr.reasoning   = reason
        return pr

    # ─────────────────────────────────────────────────────────────────────────
    #  辅助函数
    # ─────────────────────────────────────────────────────────────────────────

    def _opponent_strength(self, match: RecentMatchInfo, stats: TeamStats) -> str:
        """通过排名差距估算对手相对实力（stronger / similar / weaker）"""
        team_rank = stats.league_position
        opp_rank  = match.opponent_rank
        total     = stats.league_total_teams or match.opponent_league_size or 20

        if team_rank <= 0 or opp_rank <= 0:
            return "similar"

        # 阈值约为联赛总队数的 1/6（至少 3）
        threshold = max(3, total // 6)
        diff = opp_rank - team_rank   # 正数 = 对手排名靠后 = 对手更弱

        if diff <= -threshold:
            return "stronger"
        if diff >= threshold:
            return "weaker"
        return "similar"

    def _count_distance(
        self, recent_matches: List[RecentMatchInfo], is_playing_home: bool
    ) -> int:
        """统计连续在对场位的额外场次（第一场对场位不算距离，之后每场+1）"""
        count = 0
        for m in recent_matches:
            if m.is_home != is_playing_home:
                count += 1
            else:
                break
        return max(0, count - 1)

    def _venue_quality(self, stats: TeamStats, is_home: bool) -> str:
        """以本场位历史胜率判断场地环境质量：good / neutral / bad"""
        rate = stats.home_win_rate if is_home else stats.away_win_rate
        if rate >= 50:
            return "good"
        if rate >= 28:
            return "neutral"
        return "bad"

    def _recent_current_venue_match(
        self,
        recent_matches: List[RecentMatchInfo],
        is_playing_home: bool,
    ) -> Optional[RecentMatchInfo]:
        """返回本场位最近一次比赛，用于“客回主/主回客”的遇胜平负对照。"""
        for match in recent_matches:
            if match.is_home == is_playing_home:
                return match
        return None

    @staticmethod
    def _is_high_quality_win(match: RecentMatchInfo, opp: str) -> bool:
        return match.result == 1 and (
            match.goal_diff >= 2 or opp == "stronger" or (opp == "similar" and match.goals_for >= 2)
        )

    @staticmethod
    def _is_low_quality_win(match: RecentMatchInfo, opp: str) -> bool:
        return match.result == 1 and match.goal_diff == 1 and opp == "weaker"

    @staticmethod
    def _is_strong_draw(match: RecentMatchInfo, opp: str) -> bool:
        return match.result == 0 and opp == "stronger" and match.goals_for >= 2

    def _describe_match(self, m: RecentMatchInfo, opp: str) -> str:
        venue = "主场" if m.is_home else "客场"
        score = f"{m.goals_for}-{m.goals_against}"
        opp_s = {"stronger": "强队", "similar": "同级队", "weaker": "弱队"}.get(opp, "对手")

        if m.result == 1:
            qual = "大胜" if m.goal_diff >= 2 else "小胜"
            return f"{venue}{qual}{opp_s}（{score}）"
        if m.result == 0:
            if m.goals_for >= 2:
                return f"{venue}强逼平{opp_s}（{score}，{m.goals_for}进球）"
            if m.goals_for == 1:
                return f"{venue}逼平{opp_s}（{score}）"
            return f"{venue}0-0逼平{opp_s}"
        return f"{venue}输给{opp_s}（{score}）"

    # ─────────────────────────────────────────────────────────────────────────
    #  本场位评估（近一场与本场在同一场地）
    # ─────────────────────────────────────────────────────────────────────────

    def _same_venue(
        self, m: RecentMatchInfo, opp: str, vq: str
    ) -> Tuple[str, str]:
        venue = "主场" if m.is_home else "客场"

        if m.result == 1:
            if m.goal_diff >= 2:
                return TeamPower.WIN_STRONG, f"{venue}大净胜球→直接赢球权重"
            # 小胜
            if opp == "stronger":
                return TeamPower.WIN_MODERATE, f"{venue}小胜强队→稳定赢球想象"
            if opp == "weaker" and vq == "bad":
                return TeamPower.WIN_UNSTABLE, f"{venue}小胜弱队，但本场位环境一般→不稳定赢球想象"
            return TeamPower.WIN_MODERATE, f"{venue}小胜→赢球想象"

        if m.result == 0:
            if opp == "stronger":
                if m.goals_for >= 2:
                    return TeamPower.DRAW_WIN, f"{venue}强逼平（≥2进球）→逼平偏赢"
                return TeamPower.DRAW, f"{venue}逼平强队→对冲赢球权重"
            if opp == "weaker":
                if vq == "good" and m.goals_for >= 2:
                    return TeamPower.DRAW, f"{venue}逼平弱队，但本场位环境较好→仅保留对冲逼平"
                return TeamPower.DRAW_WEAK, f"{venue}逼平弱队→弱逼平权重"
            if vq == "good" and m.goals_for >= 2:
                return TeamPower.DRAW_WIN, f"{venue}高比分逼平同级+本场位环境好→逼平偏赢"
            if vq == "bad":
                return TeamPower.DRAW_WEAK, f"{venue}逼平同级，但本场位环境偏弱→弱逼平"
            return TeamPower.DRAW, f"{venue}逼平同级→逼平想象"

        # 负
        if opp == "stronger" and m.goal_diff == -1 and vq == "good":
            return TeamPower.LOSS_SOFT, f"{venue}惜败强队+本场位环境好→输球想象弱"
        return TeamPower.LOSS, f"{venue}输球→输球想象"

    # ─────────────────────────────────────────────────────────────────────────
    #  客回主评估（近一场客场，本场主场）
    # ─────────────────────────────────────────────────────────────────────────

    def _ke_hui_zhu(
        self,
        m: RecentMatchInfo,
        opp: str,
        vq: str,
        dist: int,
        venue_ref: Optional[RecentMatchInfo] = None,
        venue_ref_opp: str = "similar",
    ) -> Tuple[str, str]:
        """客回主：近客场为主锚点，再对照最近主场的“遇胜 / 遇平 / 遇负”结果。"""
        dn = f"（连续{dist+1}次客场后回主，距离减弱）" if dist >= 1 else ""
        venue_ref_desc = (
            self._describe_match(venue_ref, venue_ref_opp) if venue_ref else "无近主场参照"
        )
        venue_ref_label = ""
        venue_ref_score = None
        if venue_ref:
            venue_ref_label, _ = self._same_venue(venue_ref, venue_ref_opp, vq)
            venue_ref_score = TeamPower.score(venue_ref_label)

        if m.result == 1:
            if m.goal_diff >= 2:
                label = TeamPower.WIN_STRONG if vq == "good" else TeamPower.WIN_MODERATE
                reason = f"客场大胜{dn}+主场环境好→强赢球想象" if vq == "good" else f"客场大胜回主场{dn}→赢球想象为主"
            elif dist >= 2:
                label = TeamPower.WIN_UNSTABLE
                reason = f"客场小胜+距离较远{dn}→不稳定赢球想象"
            elif vq == "good":
                label = TeamPower.WIN_MODERATE
                reason = f"客场小胜+主场环境好{dn}→赢球想象"
            else:
                label = TeamPower.WIN_UNSTABLE
                reason = f"客场小胜回主场{dn}→不稳定赢球想象"

            if venue_ref:
                if venue_ref.result == 1:
                    if self._is_high_quality_win(venue_ref, venue_ref_opp):
                        return (
                            TeamPower.shift(label, 1),
                            f"近客场赢球回主场{dn}，最近主场又有{venue_ref_desc}→主场胜对客胜形成信心加成",
                        )
                    return (
                        label,
                        f"近客场赢球回主场{dn}，最近主场也有{venue_ref_desc}→形成辅助加成，但客场胜仍是主判断",
                    )
                if venue_ref.result == -1:
                    weakened = TeamPower.shift(label, -1 if dist >= 1 or not self._is_high_quality_win(m, opp) else 0)
                    return (
                        weakened,
                        f"近客场赢球回主场{dn}，但最近主场是{venue_ref_desc}→客场胜仍为主，只是被主场负削弱",
                    )
            return label, reason

        if m.result == 0:
            if opp == "stronger":
                if m.goals_for >= 2:
                    base_label = TeamPower.WIN_MODERATE
                    base_reason = f"客场强逼平（{m.goals_for}进球）回主场{dn}→赢球想象"
                else:
                    base_label = TeamPower.DRAW_WIN
                    base_reason = f"客场逼平强队（低分）回主场{dn}→逼平偏赢"
            elif opp == "weaker":
                base_label = TeamPower.DRAW
                base_reason = f"客场逼平弱队回主场{dn}→对冲逼平权重"
            elif dist >= 1:
                base_label = TeamPower.DRAW_WEAK
                base_reason = f"客场逼平同级+距离{dn}→弱逼平"
            else:
                base_label = TeamPower.DRAW
                base_reason = f"客场逼平同级回主场{dn}→五五开"

            if venue_ref:
                if venue_ref.result == 1:
                    if self._is_high_quality_win(venue_ref, venue_ref_opp) and venue_ref_score is not None and venue_ref_score >= TeamPower.score(base_label):
                        chosen = venue_ref_label
                        if dist >= 1 and TeamPower.score(chosen) >= TeamPower.score(TeamPower.WIN_MODERATE):
                            chosen = TeamPower.shift(chosen, -1)
                        return (
                            chosen,
                            f"客场平局回主场{dn}，最近主场是{venue_ref_desc}，且主场胜质量更高→以主场胜为主",
                        )
                    return (
                        base_label,
                        f"客场平局回主场{dn}，最近主场是{venue_ref_desc}，但不足以压过客场平的缓冲→仍以客场平为主",
                    )
                if venue_ref.result == 0 and venue_ref_score is not None:
                    chosen = venue_ref_label if venue_ref_score > TeamPower.score(base_label) else base_label
                    if dist >= 1 and chosen == venue_ref_label and not self._is_strong_draw(venue_ref, venue_ref_opp):
                        chosen = TeamPower.shift(chosen, -1)
                    return (
                        chosen,
                        f"客场平局回主场{dn}，最近主场是{venue_ref_desc}→比较两次平局质量后取权重大头",
                    )
                if venue_ref.result == -1 and dist >= 1 and TeamPower.score(base_label) > 0:
                    return (
                        TeamPower.shift(base_label, -1),
                        f"客场平局回主场{dn}，最近主场是{venue_ref_desc}→客场平缓冲被主场负进一步削弱",
                    )
            return base_label, base_reason

        if venue_ref:
            if venue_ref.result == 1:
                chosen = venue_ref_label
                if not self._is_high_quality_win(venue_ref, venue_ref_opp):
                    chosen = TeamPower.shift(chosen, -1)
                if dist >= 1 and TeamPower.score(chosen) > 0:
                    chosen = TeamPower.shift(chosen, -1)
                if TeamPower.score(chosen) < TeamPower.score(TeamPower.DRAW):
                    chosen = TeamPower.DRAW
                return (
                    chosen,
                    f"客场输球回主场{dn}，最近主场是{venue_ref_desc}→按主场胜为主，客场负只负责削弱力度",
                )
            if venue_ref.result == 0:
                chosen = venue_ref_label
                if dist >= 1 and TeamPower.score(chosen) > 0:
                    chosen = TeamPower.shift(chosen, -1)
                return (
                    chosen,
                    f"客场输球回主场{dn}，最近主场是{venue_ref_desc}→按主场平局为主，客场负仅保留残留削弱",
                )

        if dist >= 2:
            return TeamPower.DRAW_WEAK, f"客场输球+距离较远{dn}→残留缓冲极弱"
        if dist == 1:
            return TeamPower.DRAW, f"客场输球+距离适中{dn}→主场残留缓冲减弱"
        if vq == "good":
            return TeamPower.WIN_UNSTABLE, f"客场输球回主场，主场环境好{dn}→主场残留缓冲为主"
        if vq == "neutral":
            return TeamPower.DRAW, f"客场输球回主场+主场中性{dn}→有限残留缓冲"
        return TeamPower.LOSS_SOFT, f"客场输球回主场+主场偏弱{dn}→残留缓冲有限"

    # ─────────────────────────────────────────────────────────────────────────
    #  主回客评估（近一场主场，本场客场）
    # ─────────────────────────────────────────────────────────────────────────

    def _zhu_hui_ke(
        self,
        m: RecentMatchInfo,
        opp: str,
        vq: str,
        dist: int,
        venue_ref: Optional[RecentMatchInfo] = None,
        venue_ref_opp: str = "similar",
    ) -> Tuple[str, str]:
        """主回客：近主场为主锚点，再对照最近客场的“遇胜 / 遇平 / 遇负”结果。"""
        dn = f"（连续{dist+1}次主场后赴客）" if dist >= 1 else ""
        venue_ref_desc = (
            self._describe_match(venue_ref, venue_ref_opp) if venue_ref else "无近客场参照"
        )

        if m.result == 1:
            if m.goal_diff >= 2:
                label = TeamPower.WIN_UNSTABLE
                reason = f"主场大胜→赴客，主客转化削弱{dn}→赢球想象"
            else:
                label = TeamPower.DRAW_WIN
                reason = f"主场小胜{dn}→赴客折叠为逼平偏赢"

            if venue_ref:
                if venue_ref.result == 1:
                    if self._is_high_quality_win(venue_ref, venue_ref_opp) and TeamPower.score(label) < TeamPower.score(TeamPower.WIN_UNSTABLE):
                        return (
                            TeamPower.WIN_UNSTABLE,
                            f"主场胜回客场{dn}，最近客场又有{venue_ref_desc}→形成连胜缓冲，但仍非直接赢球权重",
                        )
                    return (
                        label,
                        f"主场胜回客场{dn}，最近客场又有{venue_ref_desc}→形成连续缓冲，但仍以主客转化后的缓冲理解",
                    )
                if venue_ref.result == 0:
                    chosen = label if m.goal_diff >= 2 else TeamPower.DRAW
                    return (
                        chosen,
                        f"主场胜回客场{dn}，最近客场是{venue_ref_desc}→客场平局削弱主场胜的缓冲",
                    )
                if venue_ref.result == -1:
                    if m.goal_diff >= 2:
                        chosen = TeamPower.DRAW_WIN if dist >= 1 else TeamPower.WIN_UNSTABLE
                    elif self._is_low_quality_win(m, opp):
                        chosen = TeamPower.LOSS_SOFT
                    else:
                        chosen = TeamPower.DRAW_WEAK
                    return (
                        chosen,
                        f"主场胜回客场{dn}，最近客场是{venue_ref_desc}→客场输球削弱主场胜缓冲",
                    )
            return label, reason

        if m.result == 0:
            if opp == "stronger" and m.goals_for >= 2:
                base_label = TeamPower.DRAW_WIN
                base_reason = f"主场强逼平（{m.goals_for}进球）{dn}→赴客有点赢球想象"
            elif opp == "stronger":
                base_label = TeamPower.DRAW
                base_reason = f"主场逼平强队{dn}→赴客对冲逼平权重"
            elif opp == "weaker":
                base_label = TeamPower.LOSS_SOFT
                base_reason = f"主场逼平弱队{dn}→赴客，输球想象"
            elif dist >= 1:
                base_label = TeamPower.DRAW_WEAK
                base_reason = f"主场逼平+距离{dn}→赴客弱逼平"
            else:
                base_label = TeamPower.DRAW
                base_reason = f"主场逼平{dn}→赴客对冲逼平权重（削弱）"

            if venue_ref:
                if venue_ref.result == 0:
                    chosen = TeamPower.shift(base_label, -1) if TeamPower.score(base_label) > TeamPower.score(TeamPower.LOSS_SOFT) else base_label
                    return (
                        chosen,
                        f"主场逼平回客场{dn}，最近客场是{venue_ref_desc}→进一步削弱主场平局的缓冲",
                    )
                if venue_ref.result == -1:
                    delta = -2 if TeamPower.score(base_label) >= TeamPower.score(TeamPower.DRAW) else -1
                    return (
                        TeamPower.shift(base_label, delta),
                        f"主场逼平回客场{dn}，最近客场是{venue_ref_desc}→主场平回客场被继续削弱",
                    )
                if venue_ref.result == 1:
                    return (
                        base_label,
                        f"主场逼平回客场{dn}，最近客场是{venue_ref_desc}→不改变逼平回客场的本质，仍看原缓冲",
                    )
            return base_label, base_reason

        if venue_ref:
            if venue_ref.result == 1:
                chosen = TeamPower.LOSS_SOFT if dist == 0 else TeamPower.LOSS
                return (
                    chosen,
                    f"主场输球回客场{dn}，最近客场是{venue_ref_desc}→客场胜只能略作正向加持，输球本质不变",
                )
            if venue_ref.result == 0:
                return (
                    TeamPower.LOSS,
                    f"主场输球回客场{dn}，最近客场是{venue_ref_desc}→客场平略作缓冲，但仍以输球权重为主",
                )
            return (
                TeamPower.LOSS_COMPLETE,
                f"主场输球回客场{dn}，最近客场也是{venue_ref_desc}→没有赢球缓冲，完全输球",
            )

        if dist >= 1:
            return TeamPower.LOSS_COMPLETE, f"主场输球+连续主场{dn}→赴客完全输球"
        return TeamPower.LOSS, f"主场输球{dn}→赴客，输球权重"

    # ─────────────────────────────────────────────────────────────────────────
    #  确定分布节点（主权重 ≥ 90%）
    # ─────────────────────────────────────────────────────────────────────────

    def _determine_node(
        self,
        hs: int,
        as_: int,
        home_power: TeamPowerResult,
        away_power: TeamPowerResult,
    ) -> str:
        net = hs - as_  # 正值 → 顺分布

        # ── 特殊情形：双方都有积极缓冲（均有赢球想象）→ 缓冲区 ──
        both_positive = hs >= 3 and as_ >= 3
        if both_positive:
            if net >= 3:
                return DistributionNode.SHUN_ZHONG
            if net == 2:
                return DistributionNode.CHONG_PIAN_SHUN
            if net == 1:
                return DistributionNode.CHONG_PIAN_SHUN
            if net == 0:
                return DistributionNode.CHONG_JUN_HENG
            if net == -1:
                return DistributionNode.CHONG_PIAN_NI
            if net == -2:
                return DistributionNode.CHONG_PIAN_NI
            return DistributionNode.NI_ZHONG

        # ── 特殊情形：双方都只是逼平/弱逼平 → 高平权重 ──
        both_draw_zone = (0 <= hs <= 2) and (0 <= as_ <= 2)
        if both_draw_zone and abs(net) <= 1:
            return DistributionNode.GAO_PING

        # ── 特殊情形：双方都是负面（输球方向）→ 缓冲区（均衡型弱势） ──
        both_negative = hs <= -1 and as_ <= -1
        if both_negative:
            if net >= 1:
                return DistributionNode.CHONG_PIAN_SHUN
            if net <= -1:
                return DistributionNode.CHONG_PIAN_NI
            return DistributionNode.CHONG_JUN_HENG

        # ── 标准映射：基于净分差 + 绝对分值 ──
        if net >= 6:
            return DistributionNode.SHUN_STRONG
        if net == 5:
            return DistributionNode.SHUN_STRONG if as_ <= -2 else DistributionNode.SHUN_PIAN_QIANG
        if net == 4:
            return DistributionNode.SHUN_PIAN_QIANG
        if net == 3:
            return DistributionNode.SHUN_PIAN_QIANG if as_ <= -2 else DistributionNode.SHUN_ZHONG
        if net == 2:
            if as_ <= -2:
                return DistributionNode.SHUN_ZHONG
            if hs >= 4:
                return DistributionNode.SHUN_ZHONG
            return DistributionNode.SHUN_ZHONG_PIAN_RUO
        if net == 1:
            if hs >= 4 and as_ <= 0:
                return DistributionNode.SHUN_ZHONG
            if hs >= 3:
                return DistributionNode.SHUN_RUO
            return DistributionNode.SHUN_RUO_GAO_PING
        if net == 0:
            return DistributionNode.GAO_PING
        if net == -1:
            if as_ >= 4 and hs <= 0:
                return DistributionNode.NI_RUO
            return DistributionNode.NI_RUO_GAO_PING
        if net == -2:
            return DistributionNode.NI_ZHONG_PIAN_RUO if as_ >= 4 else DistributionNode.NI_RUO
        if net == -3:
            return DistributionNode.NI_PIAN_QIANG if (as_ >= 5 and hs <= -2) else DistributionNode.NI_ZHONG
        if net == -4:
            return DistributionNode.NI_PIAN_QIANG
        return DistributionNode.NI_STRONG

    # ─────────────────────────────────────────────────────────────────────────
    #  底层盘口微调（≤5%，不改变大格局）
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_handicap(
        self,
        node: str,
        hs: int,
        as_: int,
        handicap_line: float,
    ) -> Tuple[str, str]:
        """
        底层盘口微调规则：
        1. 让方输球 + 受方逼平 + 半球及内 → 可抵冲成高平权重
        2. 双方势均力敌（净分差≤1）+ 半一及上 → 带来赢球想象加持
        3. 让方已有赢球方向 → 仅锦上添花
        4. 带逆分布 → 底层盘口不起作用
        """
        if handicap_line <= 0:
            return "无主队让球，底层盘口不作加成", node

        net = hs - as_
        home_losing = hs <= -1
        away_only_draw = 0 <= as_ <= 1
        away_winning = as_ >= 3

        # 先处理用户规则里的特例：
        # 让方输球 + 受方只是直接逼平时，底层盘口可以先抵冲逆力度。
        if home_losing and away_only_draw:
            if handicap_line <= 0.5:
                adj_node = DistributionNode.GAO_PING
                return (
                    f"让方输球+受方逼平，盘口让{handicap_line}球（半球及内）"
                    "→抵冲成高平权重",
                    adj_node,
                )
            if handicap_line <= 0.75:
                # 半一，抵冲不完全，带顺倾斜
                if node != DistributionNode.SHUN_RUO_GAO_PING:
                    return (
                        f"让方输球+受方逼平，盘口让{handicap_line}球（半一）"
                        "→带点顺倾斜",
                        DistributionNode.SHUN_RUO_GAO_PING,
                    )
            return f"让方输球+受方逼平，盘口让{handicap_line}球只能部分抵冲，难再往上突破", node

        # 若受方已经是稳定赢球想象，则底层盘口无法抹平逆力度。
        if node.startswith("逆"):
            if home_losing and away_winning:
                return f"让方输球且受方已有赢球想象，盘口让{handicap_line}球仅能部分抵冲，无法改写逆分布", node
            return f"逆分布中底层盘口让{handicap_line}球通常不起作用", node

        # 双方势均力敌（净分差≤1），半一及上带赢球想象
        if abs(net) <= 1:
            if handicap_line >= 0.75:
                # 若当前节点是高平或顺弱接近高平，可升一级
                if node in (DistributionNode.GAO_PING, DistributionNode.SHUN_RUO_GAO_PING):
                    adj_node = DistributionNode.SHUN_RUO
                    return (
                        f"底层盘口让{handicap_line}球（半一及上）+双方势均力敌"
                        "→带来赢球想象加持，升至顺弱",
                        adj_node,
                    )
                if node in (DistributionNode.CHONG_JUN_HENG, DistributionNode.CHONG_PIAN_SHUN) and net >= 0:
                    return (
                        f"底层盘口让{handicap_line}球（半一及上）+原本缓冲均衡/偏顺"
                        "→让方获得额外赢球支撑点，升至顺弱接近高平",
                        DistributionNode.SHUN_RUO_GAO_PING,
                    )
                return (
                    f"底层盘口让{handicap_line}球（半一及上），势均力敌基础上可带来赢球想象加持",
                    node,
                )
            if handicap_line >= 0.5:
                return (
                    f"底层盘口让{handicap_line}球（平半），有一点加持但不突破赢球想象门槛",
                    node,
                )

        # 让方已有优势方向
        if net >= 2:
            if handicap_line >= 0.75:
                return f"让方已占优+让{handicap_line}球，锦上添花，力度微增", node
            return f"让方有优势+让{handicap_line}球，轻微加成", node

        return f"底层盘口让{handicap_line}球，当前格局下微弱影响", node

    # ─────────────────────────────────────────────────────────────────────────
    #  往绩微调（≤5%）
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_h2h(
        self,
        node: str,
        hs: int,
        as_: int,
        parsed: ConfidenceParseResult,
    ) -> Tuple[str, str]:
        """
        往绩规则：
        1. 往绩连胜≥2 + 当前处于顺/逆弱接近高平边界 → 带来赢球想象（升一级）
        2. 往绩完全克制（胜率≥80%）→ 轻微力度加持
        3. 其余情况：仅说明，不调整节点
        """
        h2h = parsed.h2h
        if h2h.total_matches < 2:
            return "往绩场次不足，不作微调", node

        home_streak = self._h2h_streak(h2h.recent_results, 1)
        away_streak = self._h2h_streak(h2h.recent_results, -1)
        home_home_sweep = self._h2h_venue_clean_sweep(h2h.venue_results, True, 1)
        away_away_sweep = self._h2h_venue_clean_sweep(h2h.venue_results, False, -1)

        # 往绩两连胜 + 处于边界节点 → 带来赢球想象
        boundary_shun = node in (
            DistributionNode.SHUN_RUO_GAO_PING,
            DistributionNode.GAO_PING,
        )
        boundary_ni = node in (
            DistributionNode.NI_RUO_GAO_PING,
            DistributionNode.GAO_PING,
        )

        if home_streak >= 2 and boundary_shun:
            adj_node = DistributionNode.SHUN_RUO
            return (
                f"往绩主队近{home_streak}场连续占优，在顺弱接近高平力度下带来赢球想象→升至顺弱",
                adj_node,
            )
        if away_streak >= 2 and boundary_ni:
            adj_node = DistributionNode.NI_RUO
            return (
                f"往绩客队近{away_streak}场连续占优，在逆弱接近高平力度下带来赢球想象→升至逆弱",
                adj_node,
            )

        if home_home_sweep >= 2 and boundary_shun:
            return (
                f"往绩主队在本场位主场已连续{home_home_sweep}次全胜→给顺弱接近高平额外赢球支撑点",
                DistributionNode.SHUN_RUO,
            )
        if away_away_sweep >= 2 and boundary_ni:
            return (
                f"往绩客队在本场位客场已连续{away_away_sweep}次全胜→给逆弱接近高平额外赢球支撑点",
                DistributionNode.NI_RUO,
            )

        # 完全克制
        if h2h.home_win_rate >= 80 and h2h.total_matches >= 4:
            return f"往绩主队完全克制（胜率{h2h.home_win_rate:.0f}%），力度微增", node
        if h2h.away_win_rate >= 80 and h2h.total_matches >= 4:
            return f"往绩客队完全克制（胜率{h2h.away_win_rate:.0f}%），力度微增", node

        # 一般往绩
        if home_streak >= 2:
            return f"往绩主队近{home_streak}场连续占优，锦上添花，力度微增（<5%）", node
        if away_streak >= 2:
            return f"往绩客队近{away_streak}场连续占优，锦上添花，力度微增（<5%）", node
        if home_home_sweep >= 2:
            return f"往绩主队在本场位主场已连续{home_home_sweep}次全胜，力度微增（<5%）", node
        if away_away_sweep >= 2:
            return f"往绩客队在本场位客场已连续{away_away_sweep}次全胜，力度微增（<5%）", node

        return "往绩无显著倾向，仅轻微影响（<5%）", node

    @staticmethod
    def _h2h_streak(results: List[int], target: int) -> int:
        """按真实顺序统计最近连续占优场次。"""
        streak = 0
        for result in results:
            if result == target:
                streak += 1
            else:
                break
        return streak

    @staticmethod
    def _h2h_venue_clean_sweep(
        venue_results: List[Tuple[bool, int]],
        is_home_venue: bool,
        target: int,
    ) -> int:
        """统计本场位往绩是否形成“主场全胜 / 客场全胜”的特征。"""
        filtered = [result for venue_is_home, result in venue_results if venue_is_home == is_home_venue]
        if len(filtered) < 2:
            return 0
        if all(result == target for result in filtered):
            return len(filtered)
        return 0

    # ─────────────────────────────────────────────────────────────────────────
    #  综合说明
    # ─────────────────────────────────────────────────────────────────────────

    def _build_summary(
        self,
        result: DistributionResult,
        home_team: str,
        away_team: str,
    ) -> str:
        hp = result.home_power
        ap = result.away_power
        lines = [
            f"【分布节点】{result.distribution_node}",
            "",
            f"▶ {home_team}（主队）",
            f"  近一场 : {hp.base_result}",
            f"  位置   : {hp.position_type}"
            + (f"  距离效应：连续{hp.distance+1}次对场位" if hp.distance >= 1 else ""),
            f"  权重   : {hp.power_label}",
            f"  推理   : {hp.reasoning}",
            "",
            f"▶ {away_team}（客队）",
            f"  近一场 : {ap.base_result}",
            f"  位置   : {ap.position_type}"
            + (f"  距离效应：连续{ap.distance+1}次对场位" if ap.distance >= 1 else ""),
            f"  权重   : {ap.power_label}",
            f"  推理   : {ap.reasoning}",
            "",
            f"▶ 底层盘口 : {result.handicap_adjustment}",
            f"▶ 往绩微调 : {result.h2h_adjustment}",
        ]
        return "\n".join(lines)
