#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
赛事题材检测模块

从解析数据中提取赛事题材标签，补充 confidence_calculator 未覆盖的维度：
  - 同城德比 / 国家德比（内置映射表）
  - 保级战 / 争冠战（基于精确排名 + 联赛队数）
  - 未来重要赛事（欧冠/杯赛/关键对手）
  - 复仇战（历史交锋极端不平衡）
"""

import re
import logging
from typing import List, FrozenSet

from fundamental_analysis.confidence_parser import ConfidenceParseResult, TeamStats

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  德比映射表
# ------------------------------------------------------------------ #

DERBY_MAP: dict[FrozenSet[str], str] = {
    # 西班牙
    frozenset({"皇家马德里", "马德里竞技"}): "马德里德比",
    frozenset({"皇家马德里", "巴塞罗那"}): "西班牙国家德比",
    frozenset({"巴塞罗那", "西班牙人"}): "巴塞罗那德比",
    frozenset({"皇家贝蒂斯", "塞维利亚"}): "塞维利亚德比",
    frozenset({"毕尔巴鄂竞技", "皇家社会"}): "巴斯克德比",
    frozenset({"瓦伦西亚", "比利亚雷亚尔"}): "瓦伦西亚社区德比",
    # 英格兰
    frozenset({"曼彻斯特联", "曼彻斯特城"}): "曼彻斯特德比",
    frozenset({"阿森纳", "托特纳姆热刺"}): "北伦敦德比",
    frozenset({"利物浦", "埃弗顿"}): "默西塞德德比",
    frozenset({"切尔西", "阿森纳"}): "伦敦德比",
    frozenset({"切尔西", "托特纳姆热刺"}): "伦敦德比",
    frozenset({"纽卡斯尔联", "桑德兰"}): "东北德比",
    frozenset({"阿斯顿维拉", "伯明翰"}): "伯明翰德比",
    frozenset({"利物浦", "曼彻斯特联"}): "英格兰国家德比",
    # 意大利
    frozenset({"AC米兰", "国际米兰"}): "米兰德比",
    frozenset({"罗马", "拉齐奥"}): "罗马德比",
    frozenset({"尤文图斯", "都灵"}): "都灵德比",
    frozenset({"尤文图斯", "国际米兰"}): "意大利国家德比",
    frozenset({"热那亚", "桑普多利亚"}): "热那亚德比",
    frozenset({"那不勒斯", "罗马"}): "太阳德比",
    # 德国
    frozenset({"多特蒙德", "沙尔克04"}): "鲁尔区德比",
    frozenset({"拜仁慕尼黑", "多特蒙德"}): "德国国家德比",
    frozenset({"汉堡", "云达不莱梅"}): "北方德比",
    frozenset({"科隆", "门兴格拉德巴赫"}): "莱茵德比",
    # 法国
    frozenset({"巴黎圣日耳曼", "马赛"}): "法国国家德比",
    frozenset({"里昂", "圣埃蒂安"}): "罗纳德比",
    # 荷兰 / 葡萄牙
    frozenset({"阿贾克斯", "费耶诺德"}): "荷兰国家德比",
    frozenset({"本菲卡", "波尔图"}): "葡萄牙国家德比",
    frozenset({"本菲卡", "里斯本竞技"}): "里斯本德比",
    # 土耳其
    frozenset({"加拉塔萨雷", "费内巴切"}): "洲际德比",
    frozenset({"加拉塔萨雷", "贝西克塔斯"}): "伊斯坦布尔德比",
    frozenset({"费内巴切", "贝西克塔斯"}): "伊斯坦布尔德比",
    # 南美
    frozenset({"博卡青年", "河床"}): "阿根廷超级德比",
    frozenset({"弗拉门戈", "弗鲁米嫩塞"}): "里约德比",
    frozenset({"科林蒂安", "帕尔梅拉斯"}): "圣保罗德比",
    # 日韩中
    frozenset({"浦和红钻", "大宫松鼠"}): "埼玉德比",
    frozenset({"FC首尔", "水原三星"}): "超级比赛",
    frozenset({"上海海港", "上海申花"}): "上海德比",
}

TEAM_ALIASES: dict[str, str] = {
    "皇马": "皇家马德里", "马竞": "马德里竞技", "巴萨": "巴塞罗那",
    "曼联": "曼彻斯特联", "曼城": "曼彻斯特城", "热刺": "托特纳姆热刺",
    "国米": "国际米兰", "大巴黎": "巴黎圣日耳曼", "拜仁": "拜仁慕尼黑",
    "多特": "多特蒙德",
}

# 重要赛事关键词
MAJOR_COMPETITIONS = ['欧冠', '欧联', '欧协联', '欧洲杯', '世界杯', '杯决赛',
                      '亚冠', '解放者杯', '南美杯', '足总杯', '国王杯', '德国杯',
                      '意大利杯', '联赛杯', '超级杯', '西杯']


def detect_themes(parsed: ConfidenceParseResult) -> List[str]:
    """检测赛事题材，返回提示标签列表（不含缺阵/连胜连败等已由calculator处理的项）"""
    prompts: List[str] = []

    _detect_derby(parsed, prompts)
    _detect_relegation(parsed, prompts)
    _detect_title_race(parsed, prompts)
    _detect_upcoming_major(parsed, prompts)
    _detect_revenge(parsed, prompts)

    return prompts


def _detect_derby(parsed: ConfidenceParseResult, prompts: List[str]):
    home = parsed.home_team
    away = parsed.away_team
    if not home or not away:
        return

    key = frozenset({home, away})
    derby_name = DERBY_MAP.get(key)

    if not derby_name:
        h_canon = TEAM_ALIASES.get(home, home)
        a_canon = TEAM_ALIASES.get(away, away)
        derby_name = DERBY_MAP.get(frozenset({h_canon, a_canon}))

    if not derby_name:
        for pair, name in DERBY_MAP.items():
            t1, t2 = tuple(pair)
            if ((t1 in home or home in t1) and (t2 in away or away in t2)) or \
               ((t1 in away or away in t1) and (t2 in home or home in t2)):
                derby_name = name
                break

    if derby_name:
        prompts.append(f"🔥 {derby_name}")


def _detect_relegation(parsed: ConfidenceParseResult, prompts: List[str]):
    """基于精确排名判断保级。

    保级区定义：
      - 联赛队数 >= 18：倒数3名（如20队联赛→18/19/20名）
      - 联赛队数 12-17：倒数2名
      - 联赛队数 < 12：倒数1名
    赛季进度越深判断越可靠，但垫底位置即使赛季初也值得关注。
    """
    for team_name, stats in [(parsed.home_team, parsed.home_stats),
                              (parsed.away_team, parsed.away_stats)]:
        pos = stats.league_position
        total = stats.league_total_teams
        played = stats.league_played

        if pos <= 0 or total <= 0 or played < 3:
            continue

        # 保级区大小取决于联赛规模
        if total >= 18:
            relegation_zone = total - 2  # 倒数3名
        elif total >= 12:
            relegation_zone = total - 1  # 倒数2名
        else:
            relegation_zone = total      # 倒数1名

        total_rounds = (total - 1) * 2 if total > 1 else 30
        season_progress = played / total_rounds if total_rounds > 0 else 0

        if pos >= relegation_zone:
            if season_progress >= 0.4:
                prompts.append(f"⚠ {team_name} 保级压力（排名第{pos}/{total}）")
            else:
                prompts.append(f"⚠ {team_name} 排名靠后（第{pos}/{total}，赛季初期）")


def _detect_title_race(parsed: ConfidenceParseResult, prompts: List[str]):
    """基于排名判断争冠。前3名且赛季进行超过一半。"""
    for team_name, stats in [(parsed.home_team, parsed.home_stats),
                              (parsed.away_team, parsed.away_stats)]:
        pos = stats.league_position
        total = stats.league_total_teams
        played = stats.league_played

        if pos <= 0 or total <= 0:
            continue

        total_rounds = (total - 1) * 2 if total > 1 else 30
        if played < total_rounds * 0.5:
            continue

        if pos <= 3:
            prompts.append(f"🏆 {team_name} 争冠热门（排名第{pos}）")


def _detect_upcoming_major(parsed: ConfidenceParseResult, prompts: List[str]):
    """检测未来赛程中的重要赛事（欧冠/杯赛等），生成标签提示"""
    for team_name, upcoming in [(parsed.home_team, parsed.home_upcoming),
                                 (parsed.away_team, parsed.away_upcoming)]:
        if not upcoming:
            continue

        for match in upcoming[:3]:  # 只看最近3场
            comp = match.get('competition', '')
            fixture = match.get('fixture', '')
            days = match.get('days_gap', '')

            for keyword in MAJOR_COMPETITIONS:
                if keyword in comp:
                    opponent = fixture.replace(team_name, '').replace(' - ', '').strip()
                    if opponent:
                        prompts.append(f"📅 {team_name} {comp}在即（vs {opponent}）")
                    else:
                        prompts.append(f"📅 {team_name} {comp}在即")
                    break


def _detect_revenge(parsed: ConfidenceParseResult, prompts: List[str]):
    """历史交锋一方胜率极高（>=80%），弱势方有复仇动力"""
    h2h = parsed.h2h
    if h2h.total_matches < 3:
        return

    if h2h.home_win_rate >= 80:
        prompts.append(f"⚔ {parsed.away_team} 复仇动力（历史交锋仅{h2h.away_win_rate:.0f}%胜率）")
    elif h2h.away_win_rate >= 80:
        prompts.append(f"⚔ {parsed.home_team} 复仇动力（历史交锋仅{h2h.home_win_rate:.0f}%胜率）")
