#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
信心值数据解析器 (v2.0)

从 titan007.com 分析页 HTML 提取文档《欧赔基本面信心值_技术实现方案》所需的全部字段：
  A. 联赛积分排名 → 胜率（总/主场/客场）
  B. 联赛盘路走势 → 赢盘率（总/主场/客场）
  C. 本赛季数据统计比较 → 进失球统计 + 净胜球分布
  D. 对赛往绩 → 历史交锋胜率/赢盘率
  E. 未来五场 → 赛程间隔天数
  F. 阵容情况 → 缺阵球员（仅展示）
  G. 近期战绩 → 近况记录（用于 S7 主客场转换判断）
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from bs4 import BeautifulSoup, Tag
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class TeamStats:
    """单支球队的统计数据"""
    team_name: str = ""

    # 联赛积分排名
    league_position: int = 0       # 排名（如 2 = 第2名）
    league_total_teams: int = 0    # 联赛总队数（如 20）
    league_points: int = 0         # 积分
    league_played: int = 0         # 已踢场次

    # 联赛积分排名 → 胜率
    total_win_rate: float = 0.0
    total_draw_rate: float = 0.0
    total_lose_rate: float = 0.0
    home_win_rate: float = 0.0     # 主队取主场，客队取客场
    home_draw_rate: float = 0.0
    away_win_rate: float = 0.0
    away_draw_rate: float = 0.0

    # 联赛盘路走势 → 赢盘率
    total_win_pan_rate: float = 0.0
    home_win_pan_rate: float = 0.0  # 主队取主场赢盘率
    away_win_pan_rate: float = 0.0  # 客队取客场赢盘率

    # 进失球统计
    total_avg_goal: float = 0.0
    total_avg_concede: float = 0.0
    venue_avg_goal: float = 0.0     # 主队→主场平均进球，客队→客场平均进球
    venue_avg_concede: float = 0.0  # 主队→主场平均失球，客队→客场平均失球

    # 净胜球分布
    win_2plus_rate: float = 0.0
    win_1_rate: float = 0.0
    draw_rate_goals: float = 0.0
    lose_1_rate: float = 0.0
    lose_2plus_rate: float = 0.0

    # 近6场盘路走势序列
    recent6_pan_sequence: str = ""

    # 赛程间隔
    days_since_last: int = 6  # 默认正常间隔

    # 缺阵
    absent_players: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class HeadToHeadStats:
    """历史交锋统计"""
    total_matches: int = 0
    home_wins: int = 0
    draws: int = 0
    away_wins: int = 0
    home_win_rate: float = 0.0
    draw_rate: float = 0.0
    away_win_rate: float = 0.0
    home_win_pan_rate: float = 0.0  # 主队赢盘率
    recent_results: List[int] = field(default_factory=list)  # 最近往绩，主队视角: 1/0/-1
    venue_results: List[Tuple[bool, int]] = field(default_factory=list)  # (主队是否主场, 结果)


@dataclass
class RecentMatchInfo:
    """近期单场比赛信息"""
    date: str = ""
    league: str = ""
    is_home: bool = True
    opponent: str = ""
    goals_for: int = 0
    goals_against: int = 0
    result: int = 0  # 1=胜, 0=平, -1=负
    goal_diff: int = 0
    opponent_rank: int = 0         # 对手联赛排名（0=未知）
    opponent_league_size: int = 0  # 对手所在联赛队数


@dataclass
class ConfidenceParseResult:
    """解析结果汇总"""
    match_id: str = ""
    home_team: str = ""
    away_team: str = ""
    league: str = ""
    match_datetime: str = ""

    home_stats: TeamStats = field(default_factory=TeamStats)
    away_stats: TeamStats = field(default_factory=TeamStats)
    h2h: HeadToHeadStats = field(default_factory=HeadToHeadStats)

    # 近况记录（用于 S7 判断）
    home_recent_matches: List[RecentMatchInfo] = field(default_factory=list)
    away_recent_matches: List[RecentMatchInfo] = field(default_factory=list)

    # 赛前简报（titan007 AI 生成的文字分析）
    briefing: str = ""

    # 未来赛程（含所有赛事：联赛/杯赛/欧冠）
    home_upcoming: List[Dict[str, str]] = field(default_factory=list)
    away_upcoming: List[Dict[str, str]] = field(default_factory=list)

    parse_errors: List[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        return bool(self.home_team and self.away_team)


class ConfidenceDataParser:
    """
    从 titan007 分析页 HTML 提取信心值计算所需全部字段。

    页面关键区块（通过 h2 标签定位）：
      - "联赛积分排名"      → inner tables 0/1 (home/away)
      - "联赛盘路走势" id=006 → inner tables 0-4 (全场/半场 × home/away)
      - "本赛季数据统计比较" id=017 → inner tables 0-11
      - "对赛往绩" id=003
      - "近期战绩" id=004
      - "未来五场" id=012
      - "阵容情况" id=013
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def parse(self, html_content: str, match_id: str = "") -> ConfidenceParseResult:
        result = ConfidenceParseResult(match_id=match_id)
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            if not soup.body:
                result.parse_errors.append("HTML 内容无效")
                return result

            self._extract_basic_info(soup, result)
            self._extract_league_standings(soup, result)
            self._extract_handicap_road(soup, result)
            self._extract_season_stats(soup, result)
            self._extract_h2h(soup, html_content, result)
            self._extract_schedule(soup, result)
            self._extract_lineup(soup, result)
            self._extract_recent_form(soup, html_content, result)
            self._extract_briefing(soup, result)
            self._extract_upcoming_full(soup, result)

            # 「未来五场」只列联赛，会漏掉杯赛/欧冠
            # 用近况最新比赛日期修正 days_since_last
            self._fix_days_since_last_from_recent(soup, result)

        except Exception as e:
            self.logger.error(f"解析失败: {e}", exc_info=True)
            result.parse_errors.append(str(e))

        return result

    # ------------------------------------------------------------------ #
    #  基本信息
    # ------------------------------------------------------------------ #
    def _extract_basic_info(self, soup: BeautifulSoup, result: ConfidenceParseResult):
        try:
            home_link = soup.select_one('.analyhead .home a')
            guest_link = soup.select_one('.analyhead .guest a')
            league_link = soup.select_one('.analyhead .vs .row a.LName')

            if home_link:
                result.home_team = self._clean(home_link.get_text(strip=True))
                result.home_stats.team_name = result.home_team
            if guest_link:
                result.away_team = self._clean(guest_link.get_text(strip=True))
                result.away_stats.team_name = result.away_team
            if league_link:
                raw = league_link.get_text(strip=True).replace('\xa0', ' ')
                result.league = raw.split()[0] if raw else raw

            # JS fallback
            for script in soup.find_all('script'):
                text = script.string or ""
                if not text:
                    continue
                ht = self._js_var(text, 'hometeam')
                if ht:
                    result.home_team = ht
                    result.home_stats.team_name = ht
                at = self._js_var(text, 'guestteam')
                if at:
                    result.away_team = at
                    result.away_stats.team_name = at
                ln = self._js_var(text, 'leagueName') or self._js_var(text, 'leagueNameCn')
                if ln and not result.league:
                    result.league = ln

        except Exception as e:
            self._log_error(result, "basic_info", e)

    # ------------------------------------------------------------------ #
    #  联赛积分排名 → 胜率
    # ------------------------------------------------------------------ #
    def _extract_league_standings(self, soup: BeautifulSoup, result: ConfidenceParseResult):
        try:
            h2 = self._find_h2(soup, '联赛积分排名')
            if not h2:
                result.parse_errors.append("未找到联赛积分排名区块")
                return

            table = h2.find_next('table')
            if not table:
                return

            inner_tables = table.find_all('table')
            # inner_tables[0] = home team, inner_tables[1] = away team
            # 每个 inner table 结构：Row0=队名, Row1=header, Row2=总, Row3=主, Row4=客, Row5=近6

            if len(inner_tables) >= 1:
                self._parse_standings_table(inner_tables[0], result.home_stats, is_home_team=True)
            if len(inner_tables) >= 2:
                self._parse_standings_table(inner_tables[1], result.away_stats, is_home_team=False)

        except Exception as e:
            self._log_error(result, "league_standings", e)

    def _parse_standings_table(self, table: Tag, stats: TeamStats, is_home_team: bool):
        rows = table.find_all('tr')

        # Row0 队名行：提取排名和联赛队数，格式如 "[西甲-2]皇家马德里"
        if rows:
            header_text = rows[0].get_text(strip=True)
            rank_match = re.search(r'\[.*?-(\d+)\]', header_text)
            if rank_match:
                stats.league_position = int(rank_match.group(1))
                # 联赛总队数从排名标记的联赛名推断（后面会用积分榜数据修正）
                league_match = re.search(r'\[([^-\]]+)', header_text)
                if league_match:
                    stats.league_total_teams = self._estimate_league_size(league_match.group(1))

        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            if len(cells) < 11:
                continue

            label = cells[0]
            try:
                matches = int(cells[1])
                wins = int(cells[2])
                draws = int(cells[3])
                losses = int(cells[4])
                win_rate_str = cells[10]
            except (ValueError, IndexError):
                continue

            win_rate = self._parse_pct(win_rate_str)
            draw_rate = (draws / matches * 100) if matches > 0 else 0.0

            if label == '总':
                stats.total_win_rate = win_rate
                stats.total_draw_rate = draw_rate
                stats.league_played = matches
                try:
                    stats.league_points = int(cells[8])
                except (ValueError, IndexError):
                    pass
                stats.total_lose_rate = (losses / matches * 100) if matches > 0 else 0.0
            elif label == '主':
                if is_home_team:
                    stats.home_win_rate = win_rate
                    stats.home_draw_rate = draw_rate
                else:
                    pass  # 客队的主场数据不需要
            elif label == '客':
                if not is_home_team:
                    stats.away_win_rate = win_rate
                    stats.away_draw_rate = draw_rate
                else:
                    pass  # 主队的客场数据不需要

    # ------------------------------------------------------------------ #
    #  联赛盘路走势 → 赢盘率
    # ------------------------------------------------------------------ #
    def _extract_handicap_road(self, soup: BeautifulSoup, result: ConfidenceParseResult):
        try:
            h2 = soup.find('h2', id='006') or self._find_h2(soup, '联赛盘路走势')
            if not h2:
                result.parse_errors.append("未找到联赛盘路走势区块")
                return

            table = h2.find_next('table')
            if not table:
                return

            inner_tables = table.find_all('table')
            # 全场内表: inner[0]=home(outer), inner[1]=home(detail), inner[2]=away(detail)
            # 半场内表: inner[3]=home, inner[4]=away
            # 我们只需要全场的赢盘率

            if len(inner_tables) >= 2:
                self._parse_handicap_table(inner_tables[1], result.home_stats, is_home_team=True)
            if len(inner_tables) >= 3:
                self._parse_handicap_table(inner_tables[2], result.away_stats, is_home_team=False)

        except Exception as e:
            self._log_error(result, "handicap_road", e)

    def _parse_handicap_table(self, table: Tag, stats: TeamStats, is_home_team: bool):
        """解析盘路走势表

        12列行结构（常规行）：
          [0]标签 [1]赛 [2]赢盘 [3]走水 [4]输盘 [5]赢盘率 [6]详细 [7]大球 ...
        7列行结构（近6场）：
          [0]近6场 [1]场数 [2]盘路序列 [3]赢盘率 [4]查看 [5]大小序列 [6]查看
        """
        rows = table.find_all('tr')
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            if len(cells) < 7:
                continue

            label = cells[0]

            # 近6场行（7列）
            if '近6场' in label:
                stats.recent6_pan_sequence = cells[2] if len(cells) > 2 else ""
                continue

            # 常规数据行至少12列
            if len(cells) < 12:
                continue

            # 赢盘率在 cells[5]
            rate = self._parse_pct(cells[5])

            if label == '总':
                stats.total_win_pan_rate = rate
            elif label == '主场':
                if is_home_team:
                    stats.home_win_pan_rate = rate
            elif label == '客场':
                if not is_home_team:
                    stats.away_win_pan_rate = rate

    # ------------------------------------------------------------------ #
    #  本赛季数据统计比较 → 进失球 + 净胜球
    # ------------------------------------------------------------------ #
    def _extract_season_stats(self, soup: BeautifulSoup, result: ConfidenceParseResult):
        try:
            h2 = soup.find('h2', id='017') or self._find_h2(soup, '本赛季数据统计比较')
            if not h2:
                result.parse_errors.append("未找到本赛季数据统计比较区块")
                return

            table = h2.find_next('table')
            if not table:
                return

            inner = table.find_all('table')
            # inner[0-1]: 主队战绩统计
            # inner[2-3]: 主队得失球统计
            # inner[4-5]: 主队净胜球统计
            # inner[6-7]: 客队战绩统计
            # inner[8-9]: 客队得失球统计
            # inner[10-11]: 客队净胜球统计

            # 主队得失球 (inner[3] is the detail table)
            if len(inner) > 3:
                self._parse_goals_stats(inner[3], result.home_stats, is_home_team=True)
            # 主队净胜球 (inner[5])
            if len(inner) > 5:
                self._parse_goal_diff_stats(inner[5], result.home_stats)

            # 客队得失球 (inner[9])
            if len(inner) > 9:
                self._parse_goals_stats(inner[9], result.away_stats, is_home_team=False)
            # 客队净胜球 (inner[11])
            if len(inner) > 11:
                self._parse_goal_diff_stats(inner[11], result.away_stats)

        except Exception as e:
            self._log_error(result, "season_stats", e)

    def _parse_goals_stats(self, table: Tag, stats: TeamStats, is_home_team: bool):
        """解析得失球统计表

        结构示例：
          Row 0: ['总', '进球总数', '', '[2]']
          Row 1: ['失球总数', '', '[3]']
          Row 2: ['平均进球', '', '[0.50]']
          Row 3: ['平均失球', '', '[0.75]']
          Row 4: ['主场', '进球总数', '', '[1]']  (or '客场' for away team)
          ...
        """
        rows = table.find_all('tr')
        current_section = ""  # "总" / "主场" / "客场" / "近六场"

        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            if not cells:
                continue

            # 检测分区标签
            for cell in cells:
                if cell in ('总', '主场', '客场', '近六场'):
                    current_section = cell
                    break

            # 提取数值
            value = self._extract_bracket_number(cells)
            if value is None:
                continue

            field_name = self._find_field_in_cells(cells, ['平均进球', '平均失球', '进球总数', '失球总数'])
            if not field_name:
                continue

            venue_label = '主场' if is_home_team else '客场'

            if current_section == '总' and field_name == '平均进球':
                stats.total_avg_goal = value
            elif current_section == '总' and field_name == '平均失球':
                stats.total_avg_concede = value
            elif current_section == venue_label and field_name == '平均进球':
                stats.venue_avg_goal = value
            elif current_section == venue_label and field_name == '平均失球':
                stats.venue_avg_concede = value

    def _parse_goal_diff_stats(self, table: Tag, stats: TeamStats):
        """解析净胜球分布表

        结构示例：
          Row 0: ['净胜2球或以上', '', '0.00%[0场]']
          Row 1: ['净胜1球', '', '0.00%[0场]']
          Row 2: ['平局', '', '75.00%[3场]']
          Row 3: ['净输1球', '', '25.00%[1场]']
          Row 4: ['净输2球或以上', '', '0.00%[0场]']
        """
        rows = table.find_all('tr')
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            if not cells:
                continue

            text = ' '.join(cells)
            pct = self._extract_pct_from_text(text)
            if pct is None:
                continue

            if '净胜2球或以上' in text:
                stats.win_2plus_rate = pct
            elif '净胜1球' in text:
                stats.win_1_rate = pct
            elif '平局' in text:
                stats.draw_rate_goals = pct
            elif '净输1球' in text:
                stats.lose_1_rate = pct
            elif '净输2球或以上' in text:
                stats.lose_2plus_rate = pct

    # ------------------------------------------------------------------ #
    #  对赛往绩 → 历史交锋
    # ------------------------------------------------------------------ #
    def _extract_h2h(self, soup: BeautifulSoup, html_content: str, result: ConfidenceParseResult):
        """从 JS 变量或 HTML 表格提取历史交锋数据"""
        try:
            h2h_records = self._extract_js_array(html_content, 'v_data')
            if not h2h_records:
                h2h_records = self._extract_js_array(html_content, 'vdata')

            if not h2h_records:
                self.logger.info("JS 中无历史交锋数据，尝试从 HTML 表格提取")
                h2h_records = self._extract_h2h_from_html(soup, result)

            if not h2h_records:
                result.parse_errors.append("未找到历史交锋数据")
                return

            total = len(h2h_records)
            home_wins = 0
            draws = 0
            away_wins = 0
            home_pan_wins = 0
            recent_results: List[int] = []
            venue_results: List[Tuple[bool, int]] = []

            for match in h2h_records[:10]:
                if not isinstance(match, list) or len(match) < 13:
                    continue
                try:
                    home_name = self._clean_html_tag(str(match[5]))
                    home_score = int(match[8])
                    away_score = int(match[9])
                    handicap = float(match[11]) if match[11] else 0.0
                except (ValueError, IndexError):
                    continue

                if home_name == result.home_team:
                    home_perspective_result = 1 if home_score > away_score else (0 if home_score == away_score else -1)
                    if home_score > away_score:
                        home_wins += 1
                    elif home_score == away_score:
                        draws += 1
                    else:
                        away_wins += 1
                    # 盘口赢盘判断
                    adjusted = home_score - away_score + handicap
                    if adjusted > 0:
                        home_pan_wins += 1
                    venue_results.append((True, home_perspective_result))
                else:
                    home_perspective_result = -1 if home_score > away_score else (0 if home_score == away_score else 1)
                    if home_score > away_score:
                        away_wins += 1
                    elif home_score == away_score:
                        draws += 1
                    else:
                        home_wins += 1
                    venue_results.append((False, home_perspective_result))

                recent_results.append(home_perspective_result)

            counted = home_wins + draws + away_wins
            result.h2h.total_matches = counted
            result.h2h.home_wins = home_wins
            result.h2h.draws = draws
            result.h2h.away_wins = away_wins
            result.h2h.home_win_rate = (home_wins / counted * 100) if counted > 0 else 0.0
            result.h2h.draw_rate = (draws / counted * 100) if counted > 0 else 0.0
            result.h2h.away_win_rate = (away_wins / counted * 100) if counted > 0 else 0.0
            result.h2h.home_win_pan_rate = (home_pan_wins / counted * 100) if counted > 0 else 0.0
            result.h2h.recent_results = recent_results
            result.h2h.venue_results = venue_results

        except Exception as e:
            self._log_error(result, "h2h", e)

    def _extract_h2h_from_html(self, soup: BeautifulSoup, result: ConfidenceParseResult) -> List[List]:
        """从 HTML 表格提取交锋记录（备用）"""
        h2 = soup.find('h2', id='003') or self._find_h2(soup, '对赛往绩')
        if not h2:
            return []

        records = []
        el = h2.find_next_sibling()
        while el and el.name != 'h2':
            if el.name == 'table':
                for row in el.find_all('tr')[1:]:
                    cols = row.find_all('td')
                    if len(cols) >= 7:
                        try:
                            date = cols[0].get_text(strip=True)
                            league = cols[1].get_text(strip=True)
                            home = cols[2].get_text(strip=True)
                            score = cols[3].get_text(strip=True)
                            away = cols[4].get_text(strip=True)
                            half = cols[5].get_text(strip=True)
                            handicap_text = cols[6].get_text(strip=True) if len(cols) > 6 else "0"
                            scores = re.findall(r'\d+', score)
                            hs = int(scores[0]) if scores else 0
                            aws = int(scores[1]) if len(scores) > 1 else 0
                            try:
                                hc = float(handicap_text)
                            except ValueError:
                                hc = 0.0
                            records.append([date, "", league, "", 0, home, "", away, hs, aws, half, hc, hs - aws])
                        except Exception:
                            continue
            el = el.find_next_sibling()
        return records

    # ------------------------------------------------------------------ #
    #  近期战绩 → 用于 S7 主客场转换判断
    # ------------------------------------------------------------------ #
    def _extract_recent_form(self, soup: BeautifulSoup, html_content: str, result: ConfidenceParseResult):
        try:
            # 从 JS 变量提取
            home_data = self._extract_js_array(html_content, 'h_data') or \
                        self._extract_js_array(html_content, 'home_data')
            away_data = self._extract_js_array(html_content, 'a_data') or \
                        self._extract_js_array(html_content, 'guest_data')

            if home_data:
                result.home_recent_matches = self._convert_recent_matches(
                    home_data, result.home_team, is_team_home=True
                )
            if away_data:
                result.away_recent_matches = self._convert_recent_matches(
                    away_data, result.away_team, is_team_home=False
                )

        except Exception as e:
            self._log_error(result, "recent_form", e)

    def _convert_recent_matches(self, data: List[List], team_name: str, is_team_home: bool) -> List[RecentMatchInfo]:
        matches = []
        for row in data[:10]:
            if not isinstance(row, list) or len(row) < 13:
                continue
            try:
                info = RecentMatchInfo()
                info.date = str(row[0])
                info.league = str(row[2])

                raw_home = str(row[5])
                raw_away = str(row[7])
                home_name = self._clean_html_tag(raw_home)
                away_name = self._clean_html_tag(raw_away)
                home_score = int(row[8])
                away_score = int(row[9])

                if home_name == team_name:
                    info.is_home = True
                    info.opponent = away_name
                    info.goals_for = home_score
                    info.goals_against = away_score
                    opp_rank, opp_league = self._extract_rank_from_span(raw_away)
                else:
                    info.is_home = False
                    info.opponent = home_name
                    info.goals_for = away_score
                    info.goals_against = home_score
                    opp_rank, opp_league = self._extract_rank_from_span(raw_home)

                info.opponent_rank = opp_rank
                if opp_league:
                    info.opponent_league_size = self._estimate_league_size(opp_league)

                info.goal_diff = info.goals_for - info.goals_against
                info.result = 1 if info.goal_diff > 0 else (-1 if info.goal_diff < 0 else 0)
                matches.append(info)
            except (ValueError, IndexError):
                continue
        return matches

    # ------------------------------------------------------------------ #
    #  赛前简报
    # ------------------------------------------------------------------ #
    def _extract_briefing(self, soup: BeautifulSoup, result: ConfidenceParseResult):
        """提取赛前简报文字（id=016）"""
        try:
            h2 = soup.find('h2', id='016') or self._find_h2(soup, '赛前简报')
            if not h2:
                return

            parts = []
            el = h2.find_next_sibling()
            while el and el.name != 'h2':
                text = el.get_text(strip=True)
                if text and len(text) > 5:
                    parts.append(text)
                el = el.find_next_sibling()

            result.briefing = '\n'.join(parts).strip()

        except Exception as e:
            self._log_error(result, "briefing", e)

    # ------------------------------------------------------------------ #
    #  未来赛程（完整，含杯赛/欧冠）
    # ------------------------------------------------------------------ #
    def _extract_upcoming_full(self, soup: BeautifulSoup, result: ConfidenceParseResult):
        """从「未来五场」提取完整赛程列表（含赛事类型）"""
        try:
            h2 = soup.find('h2', id='012') or self._find_h2(soup, '未来五场')
            if not h2:
                return

            table = h2.find_next('table')
            if not table:
                return

            inner = table.find_all('table')
            if len(inner) >= 1:
                result.home_upcoming = self._parse_upcoming_table(inner[0])
            if len(inner) >= 2:
                result.away_upcoming = self._parse_upcoming_table(inner[1])

        except Exception as e:
            self._log_error(result, "upcoming", e)

    def _parse_upcoming_table(self, table: Tag) -> List[Dict[str, str]]:
        """解析单支球队的未来赛程表"""
        matches = []
        rows = table.find_all('tr')
        for row in rows[1:]:  # 跳过队名行
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            # 标准行：[日期, 赛事, 对阵, 分析, 直播, 相隔]
            if len(cells) >= 3 and re.search(r'\d{2}-\d{2}', cells[0]):
                match_info = {
                    'date': cells[0],
                    'competition': cells[1] if len(cells) > 1 else '',
                    'fixture': cells[2] if len(cells) > 2 else '',
                }
                # 提取间隔天数
                for c in cells:
                    m = re.search(r'(\d+)\s*天', c)
                    if m:
                        match_info['days_gap'] = m.group(1)
                        break
                matches.append(match_info)
        return matches

    # ------------------------------------------------------------------ #
    #  未来五场 → 赛程间隔
    # ------------------------------------------------------------------ #
    def _extract_schedule(self, soup: BeautifulSoup, result: ConfidenceParseResult):
        try:
            h2 = soup.find('h2', id='012') or self._find_h2(soup, '未来五场')
            if not h2:
                return

            table = h2.find_next('table')
            if not table:
                return

            inner = table.find_all('table')
            # inner[0] = home team, inner[1] = away team

            if len(inner) >= 1:
                result.home_stats.days_since_last = self._parse_schedule_days(inner[0])
            if len(inner) >= 2:
                result.away_stats.days_since_last = self._parse_schedule_days(inner[1])

        except Exception as e:
            self._log_error(result, "schedule", e)

    def _parse_schedule_days(self, table: Tag) -> int:
        """从未来五场表格中提取最近下一场的间隔天数（仅联赛，作为后备值）"""
        rows = table.find_all('tr')
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            for cell in cells:
                m = re.search(r'(\d+)\s*天', cell)
                if m:
                    return int(m.group(1))
        return 6

    def _fix_days_since_last_from_recent(self, soup: BeautifulSoup, result: ConfidenceParseResult):
        """用近期战绩的最新日期修正赛程间隔。

        「未来五场」只列联赛比赛，会漏掉欧冠/杯赛，导致间隔虚高。
        近期战绩（h_data/a_data）包含所有赛事，用其中最新一场的日期
        与本场比赛日期算差值，取较小的那个作为真实间隔。
        """
        try:
            # 获取本场比赛日期
            match_date = self._extract_match_date(soup)
            if not match_date:
                return

            if result.home_recent_matches:
                days = self._calc_days_from_recent(match_date, result.home_recent_matches[0].date)
                if days is not None and days < result.home_stats.days_since_last:
                    self.logger.info(
                        f"主队赛程间隔修正: {result.home_stats.days_since_last}天 → {days}天"
                        f"（近况含 {result.home_recent_matches[0].league}）"
                    )
                    result.home_stats.days_since_last = days

            if result.away_recent_matches:
                days = self._calc_days_from_recent(match_date, result.away_recent_matches[0].date)
                if days is not None and days < result.away_stats.days_since_last:
                    self.logger.info(
                        f"客队赛程间隔修正: {result.away_stats.days_since_last}天 → {days}天"
                        f"（近况含 {result.away_recent_matches[0].league}）"
                    )
                    result.away_stats.days_since_last = days

        except Exception as e:
            self.logger.debug(f"赛程间隔修正失败（不影响主流程）: {e}")

    def _extract_match_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """从页面头部提取本场比赛日期"""
        try:
            # 方法1：从 .analyhead 的日期文本提取
            vs_div = soup.select_one('.analyhead .vs')
            if vs_div:
                text = vs_div.get_text()
                m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
                if m:
                    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))

            # 方法2：从 JS 变量提取
            for script in soup.find_all('script'):
                st = script.string or ""
                m = re.search(r'matchDate\s*=\s*["\'](\d{4}-\d{2}-\d{2})', st)
                if m:
                    parts = m.group(1).split('-')
                    return datetime(int(parts[0]), int(parts[1]), int(parts[2]))

            # 方法3：从 title 提取
            title = soup.find('title')
            if title:
                m = re.search(r'(\d{4})-(\d{2})-(\d{2})', title.get_text())
                if m:
                    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            pass
        return None

    def _calc_days_from_recent(self, match_date: datetime, recent_date_str: str) -> Optional[int]:
        """计算本场比赛与最近一场的天数差"""
        try:
            # 近况日期格式通常为 "26-03-18" 或 "2026-03-18"
            clean = recent_date_str.strip()
            for fmt in ('%y-%m-%d', '%Y-%m-%d', '%y/%m/%d', '%Y/%m/%d'):
                try:
                    recent_date = datetime.strptime(clean, fmt)
                    diff = (match_date - recent_date).days
                    return max(0, diff)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------ #
    #  阵容情况 → 缺阵
    # ------------------------------------------------------------------ #
    def _extract_lineup(self, soup: BeautifulSoup, result: ConfidenceParseResult):
        try:
            h2 = soup.find('h2', id='013') or self._find_h2(soup, '阵容情况')
            if not h2:
                return

            table = h2.find_next('table')
            if not table:
                return

            inner = table.find_all('table')
            # inner[1] = home absent, inner[2] = away absent

            if len(inner) >= 2:
                result.home_stats.absent_players = self._parse_absent_table(inner[1])
            if len(inner) >= 3:
                result.away_stats.absent_players = self._parse_absent_table(inner[2])

        except Exception as e:
            self._log_error(result, "lineup", e)

    def _parse_absent_table(self, table: Tag) -> List[Dict[str, str]]:
        players = []
        rows = table.find_all('tr')
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            if len(cells) >= 2 and cells[0] not in ('球员', '缺阵原因', '暂无数据', ''):
                player_text = cells[0]
                reason = cells[1] if len(cells) > 1 else ""
                # 提取位置信息（如果有）
                pos_match = re.search(r'\(([^)]+)\)', player_text)
                position = pos_match.group(1) if pos_match else ""
                name = re.sub(r'\([^)]+\)', '', player_text).strip()
                # 提取球衣号码
                num_match = re.match(r'^(\d+)\s+', name)
                number = num_match.group(1) if num_match else ""
                if num_match:
                    name = name[num_match.end():].strip()

                players.append({
                    'name': name,
                    'position': position,
                    'number': number,
                    'reason': reason,
                })
        return players

    # ------------------------------------------------------------------ #
    #  工具方法
    # ------------------------------------------------------------------ #
    def _extract_rank_from_span(self, raw_html: str) -> Tuple[int, str]:
        """从 '<span title="曼彻斯特城  排名:英超2">...' 中提取排名和联赛"""
        try:
            m = re.search(r'排名[：:]?\s*([^\d]*)(\d+)', raw_html)
            if m:
                league = m.group(1).strip()
                rank = int(m.group(2))
                return rank, league
        except Exception:
            pass
        return 0, ""

    def _estimate_league_size(self, league_name: str) -> int:
        """根据联赛名估算队数（用于保级判断）"""
        big_leagues = {
            '英超': 20, '西甲': 20, '德甲': 18, '意甲': 20, '法甲': 18,
            '英冠': 24, '英甲': 24, '英乙': 24,
            '西乙': 22, '德乙': 18, '意乙': 20, '法乙': 20,
            '葡超': 18, '荷甲': 18, '比甲': 16, '土超': 19,
            '巴西甲': 20, '阿甲': 28, '美职': 29,
            '中超': 18, '韩K联': 12, '日J联': 20, '日J2': 22,
            '韩K2联': 13, '澳超': 12,
            '瑞典超': 16, '挪超': 16, '丹超': 12,
            '苏超': 12, '瑞士超': 12,
        }
        for name, size in big_leagues.items():
            if name in league_name:
                return size
        return 20  # 默认按20队算

    def _find_h2(self, soup: BeautifulSoup, text: str) -> Optional[Tag]:
        for h2 in soup.find_all('h2'):
            if text in h2.get_text(strip=True):
                return h2
        return None

    def _clean(self, text: str) -> str:
        text = text.strip().replace('\xa0', ' ')
        text = re.sub(r'[（(][^()（）]*[)）]', '', text)
        return text.strip()

    def _clean_html_tag(self, text: str) -> str:
        if '<' in text:
            m = re.search(r'>([^<]+)<', text)
            if m:
                return m.group(1).strip()
        return text.strip()

    def _parse_pct(self, text: str) -> float:
        m = re.search(r'([\d.]+)%', text)
        return float(m.group(1)) if m else 0.0

    def _extract_pct_from_text(self, text: str) -> Optional[float]:
        m = re.search(r'([\d.]+)%', text)
        return float(m.group(1)) if m else None

    def _extract_bracket_number(self, cells: List[str]) -> Optional[float]:
        for cell in cells:
            m = re.search(r'\[([\d.]+)\]', cell)
            if m:
                return float(m.group(1))
        return None

    def _find_field_in_cells(self, cells: List[str], field_names: List[str]) -> Optional[str]:
        text = ' '.join(cells)
        for name in field_names:
            if name in text:
                return name
        return None

    def _js_var(self, script_text: str, var_name: str) -> Optional[str]:
        pattern = rf"var\s+{re.escape(var_name)}\s*=\s*(?P<value>'[^']*'|\"[^\"]*\"|[^;]+);"
        m = re.search(pattern, script_text)
        if not m:
            return None
        raw = m.group('value').strip()
        if raw.startswith(("'", '"')) and raw.endswith(("'", '"')):
            raw = raw[1:-1]
        return raw

    def _extract_js_array(self, html_content: str, var_name: str) -> List[List]:
        """从 JS 中提取数组变量"""
        import ast

        try:
            pattern = rf"var\s+{re.escape(var_name)}\s*=\s*(\[[\s\S]*?\]);"
            m = re.search(pattern, html_content)
            if not m:
                return []

            data_str = m.group(1).strip()
            if data_str == '[]':
                return []

            safe = data_str.replace('null', 'None').replace('true', 'True').replace('false', 'False')
            try:
                return ast.literal_eval(safe)
            except Exception:
                items = re.findall(r'\[(.*?)\]', data_str)
                result = []
                for item in items:
                    values = []
                    for val in item.split(','):
                        val = val.strip()
                        if not val:
                            values.append('')
                            continue
                        if (val.startswith("'") and val.endswith("'")) or \
                           (val.startswith('"') and val.endswith('"')):
                            values.append(val[1:-1])
                            continue
                        try:
                            values.append(int(val))
                        except ValueError:
                            try:
                                values.append(float(val))
                            except ValueError:
                                values.append(val)
                    result.append(values)
                return result
        except Exception:
            return []

    def _log_error(self, result: ConfidenceParseResult, section: str, error: Exception):
        msg = f"解析 {section} 失败: {error}"
        self.logger.error(msg, exc_info=True)
        result.parse_errors.append(msg)
