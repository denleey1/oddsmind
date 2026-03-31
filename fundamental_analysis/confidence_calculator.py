#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
欧赔基本面信心值计算引擎 (v2.0)

严格按照《欧赔基本面信心值_技术实现方案 v1.0》实现：
  S6  近况基础分  = 胜率×0.40 + 赢盘率×0.60
  S7  主客场转换修正系数（8种情况）
  S8  进球质量修正 = 进攻系数 × 防守系数
  S9  赛程间隔修正
  S10 历史交锋修正 + 最终输出
  S11 等距转换 0~10
  S12 映射信心评级
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field

from fundamental_analysis.confidence_parser import (
    ConfidenceParseResult,
    TeamStats,
    HeadToHeadStats,
    RecentMatchInfo,
)

logger = logging.getLogger(__name__)

# 等距除数：基于实际数据校准（实际强队raw峰值≈80），而非理论最高112
# 除数8.0 → 皇马级别(raw≈65)映射到8分，弱队客场(raw≈25)映射到3分
SCORE_INTERVAL = 8.0

CONFIDENCE_RATINGS = [
    (0.0, 1.0, "欠缺信心", "几乎没有投注信心，大众对该方向极度不信任"),
    (1.0, 2.0, "信心不足", "投注信心很弱，大众普遍不看好"),
    (2.0, 3.0, "信心中低", "信心偏低，大众信任度不高"),
    (3.0, 4.0, "信心中下", "信心略低于中位，有一定支持但不多"),
    (4.0, 5.0, "信心中庸", "信心处于中间水平，胜负均衡"),
    (5.0, 6.0, "信心中上", "信心略高于中位，大众倾向看好"),
    (6.0, 7.0, "信心中高", "信心较强，大众较为看好该方向"),
    (7.0, 8.0, "信心充足", "信心强，大众普遍看好，庄家赔付压力大"),
    (8.0, 10.0, "极致信心", "信心极强，大众高度一致看好，庄家必须降赔应对"),
]


@dataclass
class ConfidenceResult:
    """最终信心值输出"""
    home_score: float = 0.0
    away_score: float = 0.0
    draw_score: float = 0.0
    home_rating: str = "欠缺信心"
    away_rating: str = "欠缺信心"
    draw_rating: str = "欠缺信心"

    # 拉力方向
    pull_direction: str = ""  # "home" / "away" / "draw" / "balanced"
    pull_description: str = ""

    # 中间过程（调试用）
    details: Dict[str, Any] = field(default_factory=dict)

    # 人工提示
    prompts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "home_score": round(self.home_score, 2),
            "away_score": round(self.away_score, 2),
            "draw_score": round(self.draw_score, 2),
            "home_rating": self.home_rating,
            "away_rating": self.away_rating,
            "draw_rating": self.draw_rating,
            "pull_direction": self.pull_direction,
            "pull_description": self.pull_description,
            "details": self.details,
            "prompts": self.prompts,
        }


class ConfidenceCalculator:
    """
    信心值计算器

    输入：ConfidenceParseResult（由 ConfidenceDataParser 产出）
    输出：ConfidenceResult（三个方向的 0~10 评分 + 信心评级 + 拉力方向）
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def calculate(self, parsed: ConfidenceParseResult) -> ConfidenceResult:
        result = ConfidenceResult()
        details = {}

        try:
            # ---- S6: 近况基础分 ----
            home_base = self._s6_base_score(parsed.home_stats, is_home=True)
            away_base = self._s6_base_score(parsed.away_stats, is_home=False)
            details['S6'] = {'home_base': home_base, 'away_base': away_base}
            self.logger.info(f"S6 基础分 → 主队: {home_base:.2f}, 客队: {away_base:.2f}")

            # ---- S7: 主客场转换修正 ----
            home_coeff_s7 = self._s7_venue_transition(parsed.home_recent_matches, is_home=True)
            away_coeff_s7 = self._s7_venue_transition(parsed.away_recent_matches, is_home=False)
            home_s7 = home_base * home_coeff_s7
            away_s7 = away_base * away_coeff_s7
            details['S7'] = {
                'home_coeff': home_coeff_s7, 'away_coeff': away_coeff_s7,
                'home_score': home_s7, 'away_score': away_s7,
            }
            self.logger.info(f"S7 修正 → 主队系数: {home_coeff_s7}, 得分: {home_s7:.2f}; "
                           f"客队系数: {away_coeff_s7}, 得分: {away_s7:.2f}")

            # ---- S8: 进球质量修正 ----
            home_atk = self._s8_attack_coeff(parsed.home_stats)
            home_def = self._s8_defense_coeff(parsed.home_stats, is_home=True)
            away_atk = self._s8_attack_coeff(parsed.away_stats)
            away_def = self._s8_defense_coeff(parsed.away_stats, is_home=False)
            home_s8 = home_s7 * home_atk * home_def
            away_s8 = away_s7 * away_atk * away_def
            details['S8'] = {
                'home_atk': home_atk, 'home_def': home_def,
                'away_atk': away_atk, 'away_def': away_def,
                'home_score': home_s8, 'away_score': away_s8,
            }
            self.logger.info(f"S8 质量修正 → 主队(攻{home_atk}×防{home_def})={home_s8:.2f}; "
                           f"客队(攻{away_atk}×防{away_def})={away_s8:.2f}")

            # ---- S9: 赛程间隔修正 ----
            home_sched = self._s9_schedule_coeff(parsed.home_stats.days_since_last)
            away_sched = self._s9_schedule_coeff(parsed.away_stats.days_since_last)
            home_s9 = home_s8 * home_sched
            away_s9 = away_s8 * away_sched
            details['S9'] = {
                'home_days': parsed.home_stats.days_since_last, 'home_coeff': home_sched,
                'away_days': parsed.away_stats.days_since_last, 'away_coeff': away_sched,
                'home_score': home_s9, 'away_score': away_s9,
            }
            self.logger.info(f"S9 赛程修正 → 主队({parsed.home_stats.days_since_last}天×{home_sched})={home_s9:.2f}; "
                           f"客队({parsed.away_stats.days_since_last}天×{away_sched})={away_s9:.2f}")

            # ---- S10: 历史交锋修正 + 最终输出 ----
            # ---- S10: 历史交锋修正（含 v1.2 动态权重熔断）----
            h2h = parsed.h2h
            h2h_weight = 0.20
            circuit_breaker = None  # 熔断状态

            if h2h.total_matches < 5:
                h2h_weight = 0.10
                self.logger.info(f"历史交锋仅{h2h.total_matches}场(<5)，权重降为0.10")
            elif h2h.total_matches >= 5:
                # v1.2 熔断检测
                home_extreme = h2h.home_win_rate >= 80 or h2h.home_win_rate <= 20
                away_extreme = h2h.away_win_rate >= 80 or h2h.away_win_rate <= 20
                home_ultra = h2h.home_win_rate >= 90 or h2h.home_win_rate <= 10
                away_ultra = h2h.away_win_rate >= 90 or h2h.away_win_rate <= 10

                if home_ultra or away_ultra:
                    h2h_weight = 0.50
                    circuit_breaker = "二级"
                    self.logger.info(f"交锋熔断(二级): 权重提升至0.50")
                elif home_extreme or away_extreme:
                    h2h_weight = 0.40
                    circuit_breaker = "一级"
                    self.logger.info(f"交锋熔断(一级): 权重提升至0.40")

            s9_weight = 1.0 - h2h_weight

            h2h_base_home = h2h.home_win_rate * 0.40 + h2h.home_win_pan_rate * 0.60
            away_pan_rate = (100 - h2h.home_win_pan_rate) if h2h.total_matches > 0 else 0.0
            h2h_base_away = h2h.away_win_rate * 0.40 + away_pan_rate * 0.60

            home_confidence = home_s9 * s9_weight + h2h_base_home * h2h_weight
            away_confidence = away_s9 * s9_weight + h2h_base_away * h2h_weight

            # ---- v1.1: 含金量系数（S10之后、S11之前）----
            home_qf = self._calc_quality_factor(parsed.home_recent_matches)
            away_qf = self._calc_quality_factor(parsed.away_recent_matches)

            home_confidence = home_confidence * home_qf
            away_confidence = away_confidence * away_qf

            home_confidence = max(0, min(112, home_confidence))
            away_confidence = max(0, min(112, away_confidence))

            details['quality_factor'] = {
                'home': home_qf, 'away': away_qf,
            }

            # ---- 定和分配法：三项总分=15，此消彼长 ----
            #
            # 核心思想：主/客/平共享固定预算(15分)，根据均衡度和不确定性分配
            #   均衡度高 → 平局权重大；不均衡 → 平局被 balance^0.5 大幅压低
            #   两弱均衡(20,18) → 主4.0 平7.3 客3.6（平局突出）
            #   碾压局(80,10)   → 主9.5 平1.6 客1.5（一边倒）
            #   两强均衡(50,45) → 主4.9 平5.7 客4.4（三项接近）
            #
            import math
            BUDGET = 15.0

            draw_freq = (h2h.draws / h2h.total_matches) if h2h.total_matches > 0 else 0.20

            home_confidence = max(0, min(100, home_confidence))
            away_confidence = max(0, min(100, away_confidence))

            h_conf = max(home_confidence, 1.0)
            a_conf = max(away_confidence, 1.0)

            draw_geo_mean = math.sqrt(h_conf * a_conf)
            balance = min(h_conf, a_conf) / max(h_conf, a_conf)
            avg_side = (home_confidence + away_confidence) / 2
            weakness = max(0, (50 - avg_side) / 50)

            draw_base = draw_geo_mean * (1 + balance * 0.3) + weakness * balance * 25
            # 不均衡时 balance^0.5 大幅衰减平局（碾压局 balance≈0.1 → 衰减70%）
            draw_raw = draw_base * (balance ** 0.5)

            draw_h2h_boost = 1 + (draw_freq - 0.20) * 0.8
            draw_h2h_boost = max(0.8, draw_h2h_boost)
            draw_raw *= draw_h2h_boost

            # 归一化到 BUDGET
            total_raw = home_confidence + away_confidence + draw_raw
            factor = BUDGET / max(total_raw, 1)

            details['S10'] = {
                'h2h_weight': h2h_weight,
                'circuit_breaker': circuit_breaker,
                'h2h_base_home': h2h_base_home,
                'h2h_base_away': h2h_base_away,
                'home_quality_factor': home_qf,
                'away_quality_factor': away_qf,
                'home_confidence_raw': home_confidence,
                'away_confidence_raw': away_confidence,
                'draw_geo_mean': draw_geo_mean,
                'draw_raw': draw_raw,
                'draw_balance': balance,
                'draw_weakness': weakness,
                'draw_freq': draw_freq,
                'draw_h2h_boost': draw_h2h_boost,
                'budget': BUDGET,
                'total_raw': total_raw,
            }
            self.logger.info(f"S10 定和分配 → 主raw:{home_confidence:.1f} 客raw:{away_confidence:.1f} "
                           f"平raw:{draw_raw:.1f} 均衡度:{balance:.2f} "
                           f"总:{total_raw:.1f} 系数:{factor:.3f}")

            # 熔断标签
            if circuit_breaker and h2h.total_matches >= 5:
                dominant = parsed.home_team if h2h.home_win_rate >= 80 else parsed.away_team
                weak = parsed.away_team if h2h.home_win_rate >= 80 else parsed.home_team
                weak_rate = min(h2h.home_win_rate, h2h.away_win_rate)
                result.prompts.append(f"🔴 历史血脉压制（{weak}近{h2h.total_matches}场交锋胜率仅{weak_rate:.0f}%）")

            # ---- S11: 定和分配 → 0~9.5 ----
            result.home_score = round(max(0.5, min(9.5, home_confidence * factor)), 2)
            result.away_score = round(max(0.5, min(9.5, away_confidence * factor)), 2)
            result.draw_score = round(max(0.5, min(9.5, draw_raw * factor)), 2)

            details['S11'] = {
                'interval': SCORE_INTERVAL,
                'home_score': result.home_score,
                'away_score': result.away_score,
                'draw_score': result.draw_score,
            }

            # ---- S12: 映射信心评级 ----
            result.home_rating = self._get_rating(result.home_score)
            result.away_rating = self._get_rating(result.away_score)
            result.draw_rating = self._get_rating(result.draw_score)

            # 拉力方向 = 三者中最高分的方向
            scores = {
                'home': result.home_score,
                'away': result.away_score,
                'draw': result.draw_score,
            }
            top_key = max(scores, key=scores.get)
            result.pull_direction = top_key
            direction_map = {'home': '主队拉力', 'away': '客队拉力', 'draw': '平局拉力'}
            result.pull_description = direction_map[top_key]

            details['S12'] = {
                'home_rating': result.home_rating,
                'away_rating': result.away_rating,
                'draw_rating': result.draw_rating,
                'pull_direction': result.pull_direction,
            }

            # 人工提示
            result.prompts = self._generate_prompts(parsed)

            result.details = details

            self.logger.info(
                f"最终评分 → 主队: {result.home_score}({result.home_rating}), "
                f"平局: {result.draw_score}({result.draw_rating}), "
                f"客队: {result.away_score}({result.away_rating}), "
                f"拉力: {result.pull_description}"
            )

        except Exception as e:
            self.logger.error(f"信心值计算失败: {e}", exc_info=True)

        return result

    # ================================================================= #
    #  S6 ~ S9 实现
    # ================================================================= #

    def _s6_base_score(self, stats: TeamStats, is_home: bool) -> float:
        """S6 近况基础分 = 胜率×0.40 + 赢盘率×0.60
        主队取主场数据，客队取客场数据。"""
        if is_home:
            win_rate = stats.home_win_rate
            pan_rate = stats.home_win_pan_rate
        else:
            win_rate = stats.away_win_rate
            pan_rate = stats.away_win_pan_rate
        return win_rate * 0.40 + pan_rate * 0.60

    def _s7_venue_transition(self, recent_matches: List[RecentMatchInfo], is_home: bool) -> float:
        """S7 主客场心理矩阵（4×4=16种情况）

        融合欧赔专家心理模型：
          纵轴 = 本场场地(主/客) × 上次同场地结果(胜/负)
          横轴 = 最近一场结果: 主场胜/主场负/客场胜/客场负

        ─────────────────────────────────────────────────────
        到主场：
          上个主场胜 + 上场主场胜 → 1.10  (连续主场赢，惯性)
          上个主场胜 + 上场主场负 → 1.00  (按最近一场，主场底气还在)
          上个主场胜 + 上场客场胜 → 1.15  (信心加成：主客都赢，双保险)
          上个主场胜 + 上场客场负 → 1.05  (按上个主场：客场输了但主场还行)

          上个主场负 + 上场主场胜 → 1.00  (按最近一场：刚赢了)
          上个主场负 + 上场主场负 → 0.85  (按最近一场：连续输)
          上个主场负 + 上场客场胜 → 1.05  (信心加强：客场赢修复主场伤疤)
          上个主场负 + 上场客场负 → 0.80  (只看最近一场：主客都不行)

        到客场：
          上个客场胜 + 上场主场胜 → 0.85  (主场胜→客场需转化，打折)
          上个客场胜 + 上场主场负 → 0.70  (信心受挫：主场都输了)
          上个客场胜 + 上场客场胜 → 0.90  (连续客场赢，客场信心好)
          上个客场胜 + 上场客场负 → 0.75  (最近客场输了，上个客场赢被冲淡)

          上个客场负 + 上场主场胜 → 0.75  (信心受挫：客场阴影+主场胜打折)
          上个客场负 + 上场主场负 → 0.55  (没有信心：主客都输了)
          上个客场负 + 上场客场胜 → 0.80  (按最近一场：客场刚赢了)
          上个客场负 + 上场客场负 → 0.60  (按最近一场：连续客场输)
        ─────────────────────────────────────────────────────
        """
        if not recent_matches:
            return 1.0

        last_match = recent_matches[0]
        last_was_home = last_match.is_home
        last_won = last_match.result > 0
        last_lost = last_match.result < 0

        if is_home:
            # 本场主场
            prev_home = self._find_last_venue_match(recent_matches, is_home_venue=True)
            prev_home_won = prev_home.result > 0 if prev_home else False

            if prev_home_won:
                # 上个主场赢
                if last_was_home:
                    return 1.10 if last_won else 1.00
                else:
                    return 1.15 if last_won else 1.05
            else:
                # 上个主场负（或无记录）
                if last_was_home:
                    return 1.00 if last_won else 0.85
                else:
                    return 1.05 if last_won else 0.80
        else:
            # 本场客场
            prev_away = self._find_last_venue_match(recent_matches, is_home_venue=False)
            prev_away_won = prev_away.result > 0 if prev_away else False

            if prev_away_won:
                # 上个客场赢
                if last_was_home:
                    return 0.85 if last_won else 0.70
                else:
                    return 0.90 if last_won else 0.75
            else:
                # 上个客场负（或无记录）
                if last_was_home:
                    return 0.75 if last_won else 0.55
                else:
                    return 0.80 if last_won else 0.60

    def _find_last_venue_match(self, matches: List[RecentMatchInfo], is_home_venue: bool) -> Optional[RecentMatchInfo]:
        for m in matches:
            if m.is_home == is_home_venue:
                return m
        return None

    def _calc_quality_factor(self, recent_matches: List[RecentMatchInfo]) -> float:
        """v1.1 含金量系数：近3场对手排名决定胜负含金量

        赢了前25%对手 → 1.20
        赢了前50%对手 → 1.10
        赢了后50%对手 → 1.00
        输给后25%对手 → 0.85
        输给后50%对手 → 0.92
        平局 → 1.00
        杯赛/无排名 → 1.00
        """
        if not recent_matches:
            return 1.0

        coeffs = []
        for m in recent_matches[:3]:
            rank = m.opponent_rank
            league_size = m.opponent_league_size

            if rank <= 0 or league_size <= 0:
                coeffs.append(1.0)
                continue

            pct = rank / league_size  # 排名百分位（越小越强）

            if m.result > 0:  # 赢了
                if pct <= 0.25:
                    coeffs.append(1.20)
                elif pct <= 0.50:
                    coeffs.append(1.10)
                else:
                    coeffs.append(1.00)
            elif m.result < 0:  # 输了
                if pct > 0.75:
                    coeffs.append(0.85)
                elif pct > 0.50:
                    coeffs.append(0.92)
                else:
                    coeffs.append(1.00)
            else:  # 平局
                coeffs.append(1.00)

        return sum(coeffs) / len(coeffs) if coeffs else 1.0

    def _s8_attack_coeff(self, stats: TeamStats) -> float:
        """S8 进攻质量系数（净胜球分布）"""
        rate = stats.win_2plus_rate
        if rate >= 30:
            return 1.15
        elif rate >= 10:
            return 1.00
        else:
            return 0.90

    def _s8_defense_coeff(self, stats: TeamStats, is_home: bool) -> float:
        """S8 防守质量系数（平均失球）"""
        avg_concede = stats.venue_avg_concede
        if avg_concede <= 0.70:
            return 1.10
        elif avg_concede <= 1.20:
            return 1.00
        else:
            return 0.90

    def _s9_schedule_coeff(self, days: int) -> float:
        """S9 赛程间隔修正系数"""
        if days <= 3:
            return 0.85
        elif days <= 6:
            return 1.00
        else:
            return 1.05

    # ================================================================= #
    #  S12 评级映射
    # ================================================================= #

    def _get_rating(self, score: float) -> str:
        for lo, hi, label, _ in CONFIDENCE_RATINGS:
            if lo <= score < hi:
                return label
        if score >= 8.0:
            return "极致信心"
        return "欠缺信心"

    # ================================================================= #
    #  人工提示模块
    # ================================================================= #

    def _generate_prompts(self, parsed: ConfidenceParseResult) -> List[str]:
        """生成人工提示标签（文档第四章）"""
        prompts = []

        # 缺阵提示
        for player in parsed.home_stats.absent_players:
            prompts.append(f"⚠ {parsed.home_team} 缺阵: {player['name']}"
                         f"{'(' + player['position'] + ')' if player['position'] else ''}"
                         f" - {player['reason']}")
        for player in parsed.away_stats.absent_players:
            prompts.append(f"⚠ {parsed.away_team} 缺阵: {player['name']}"
                         f"{'(' + player['position'] + ')' if player['position'] else ''}"
                         f" - {player['reason']}")

        # 赛程密集
        if parsed.home_stats.days_since_last <= 3:
            prompts.append(f"⚡ {parsed.home_team} 赛程密集（{parsed.home_stats.days_since_last}天前有比赛）")
        if parsed.away_stats.days_since_last <= 3:
            prompts.append(f"⚡ {parsed.away_team} 赛程密集（{parsed.away_stats.days_since_last}天前有比赛）")

        # 长休息
        if parsed.home_stats.days_since_last >= 10:
            prompts.append(f"😴 {parsed.home_team} 长休息（{parsed.home_stats.days_since_last}天未踢球）")
        if parsed.away_stats.days_since_last >= 10:
            prompts.append(f"😴 {parsed.away_team} 长休息（{parsed.away_stats.days_since_last}天未踢球）")

        # 历史碾压
        if parsed.h2h.total_matches >= 5:
            if parsed.h2h.home_win_rate >= 70:
                prompts.append(f"💪 {parsed.home_team} 历史强势方（胜率{parsed.h2h.home_win_rate:.0f}%）")
            if parsed.h2h.away_win_rate >= 70:
                prompts.append(f"💪 {parsed.away_team} 历史强势方（胜率{parsed.h2h.away_win_rate:.0f}%）")

        # 历史交锋平多
        if parsed.h2h.total_matches >= 5 and parsed.h2h.draw_rate >= 40:
            prompts.append(f"🤝 历史交锋平局频繁（平局率{parsed.h2h.draw_rate:.0f}%）")

        # 近期连胜/连败
        self._check_streak(parsed.home_recent_matches, parsed.home_team, prompts)
        self._check_streak(parsed.away_recent_matches, parsed.away_team, prompts)

        return prompts

    def _check_streak(self, matches: List[RecentMatchInfo], team_name: str, prompts: List[str]):
        if len(matches) < 3:
            return
        last3 = matches[:3]
        if all(m.result > 0 for m in last3):
            prompts.append(f"🔥 {team_name} 近3场连胜")
        if all(m.result < 0 for m in last3):
            prompts.append(f"❄ {team_name} 近3场连败")


# ================================================================= #
#  兼容层：适配现有 calculator.py 的输出格式
# ================================================================= #

def format_as_legacy_result(
    parsed: ConfidenceParseResult,
    conf_result: ConfidenceResult,
) -> Dict[str, Any]:
    """将新版信心值结果转为与旧版 FundamentalCalculator 兼容的字典格式。
    供 calculator.py 或下游系统直接消费。"""

    ODDS_PATTERNS = {
        "欠缺信心": ["实开盘高水", "实开盘中高水", "实开盘中水", "实开盘中低水", "实开盘低水"],
        "信心不足": ["实开盘超高水", "实开盘高水", "实开盘中高水", "实开盘中水", "实开盘中低水", "实开盘低水"],
        "信心中低": ["韬光盘低水", "韬光盘超低水", "实开盘超高水", "实开盘高水", "实开盘中高水", "实开盘中水", "实开盘中低水"],
        "信心中下": ["韬光盘中低水", "韬光盘低水", "韬光盘超低水", "实开盘超高水", "实开盘高水", "实开盘中高水", "实开盘中水"],
        "信心中庸": ["实开盘超高水", "实开盘高水", "实开盘中低水", "实开盘低水", "超实盘高水", "超实盘中高水", "韬光盘中低水", "韬光盘低水"],
        "信心中上": ["实开盘中水", "实开盘中低水", "实开盘低水", "实开盘超低水", "超实盘超高水", "超实盘高水", "超实盘中高水", "超实盘中水"],
        "信心中高": ["实开盘低水", "实开盘超低水", "超实盘高水", "超实盘中高水", "超实盘中水", "超实盘中低水", "超实盘低水", "超实盘超低水"],
        "信心充足": ["超实盘中低水", "超实盘低水", "超实盘超低水", "超散盘中高水", "超深盘中上水", "超深盘中下水"],
        "极致信心": ["超实盘低水", "超实盘超低水", "超散盘中高水", "超深诱盘"],
    }

    def _interval(score: float) -> str:
        if score >= 8.0: return "[8.0-10.0]"
        if score >= 7.0: return "[7.0-8.0]"
        if score >= 6.0: return "[6.0-7.0]"
        if score >= 5.0: return "[5.0-6.0]"
        if score >= 4.0: return "[4.0-5.0]"
        if score >= 3.0: return "[3.0-4.0]"
        if score >= 2.0: return "[2.0-3.0]"
        if score >= 1.0: return "[1.0-2.0]"
        return "[0.0-1.0]"

    direction_map = {'home': 'home_win', 'away': 'away_win', 'draw': 'draw', 'balanced': 'draw'}
    recommended = direction_map.get(conf_result.pull_direction, 'draw')

    return {
        "match_id": parsed.match_id,
        "basic_info": {
            "home_team": parsed.home_team,
            "away_team": parsed.away_team,
            "league": parsed.league,
        },
        "final_scores": {
            "home_win": conf_result.home_score,
            "draw": conf_result.draw_score,
            "away_win": conf_result.away_score,
        },
        "confidence_levels": {
            "home_win": conf_result.home_rating,
            "draw": conf_result.draw_rating,
            "away_win": conf_result.away_rating,
        },
        "confidence_level": conf_result.draw_rating if conf_result.pull_direction == "draw"
                           else (conf_result.home_rating if conf_result.pull_direction == "home"
                                 else conf_result.away_rating),
        "recommended_outcome": recommended,
        "max_score": max(conf_result.home_score, conf_result.draw_score, conf_result.away_score),
        "pull_direction": conf_result.pull_direction,
        "pull_description": conf_result.pull_description,
        "weights": {
            "S9_weight": conf_result.details.get('S10', {}).get('h2h_weight', 0.20),
            "h2h_weight": 1.0 - conf_result.details.get('S10', {}).get('h2h_weight', 0.20),
            "has_h2h_data": parsed.h2h.total_matches > 0,
        },
        "odds_patterns": ODDS_PATTERNS.get(
            conf_result.home_rating if recommended == 'home_win'
            else (conf_result.away_rating if recommended == 'away_win'
                  else conf_result.draw_rating),
            ["实开盘中水", "实开盘中低水", "实开盘低水"]
        ),
        "confidence_analysis": {
            "home_win": {
                "level": conf_result.home_rating,
                "interval": _interval(conf_result.home_score),
                "odds_suggestions": ODDS_PATTERNS.get(conf_result.home_rating, []),
            },
            "draw": {
                "level": conf_result.draw_rating,
                "interval": _interval(conf_result.draw_score),
                "odds_suggestions": ODDS_PATTERNS.get(conf_result.draw_rating, []),
            },
            "away_win": {
                "level": conf_result.away_rating,
                "interval": _interval(conf_result.away_score),
                "odds_suggestions": ODDS_PATTERNS.get(conf_result.away_rating, []),
            },
        },
        "prompts": conf_result.prompts,
        "briefing": parsed.briefing,
        "upcoming": {
            "home": parsed.home_upcoming,
            "away": parsed.away_upcoming,
        },
        "calculation_details": conf_result.details,
    }
