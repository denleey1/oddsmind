#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基本面数据爬取模块
从 titan007 获取比赛的基本面分析数据
"""

import re
import ast
import logging
import requests
from typing import Dict, List, Optional, Any, Iterable
from bs4 import BeautifulSoup
from pathlib import Path
import sys
import json
import traceback

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from core.logger import get_logger
from fundamental_analysis.league_manager import get_league_name

class FundamentalScraper:
    """
    基本面数据爬取器
    *** 此部分代码完全从 fundamental_analysis_fetcher.py 移植而来，以确保与原始标准100%一致 ***
    """
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Referer': 'https://zq.titan007.com/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Accept-Encoding': 'gzip, deflate, br',
            'sec-ch-ua': '"Chromium";v="122", "Google Chrome";v="122", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
        self.session = requests.Session()
        try:
            from scrapers.proxy_config import apply_proxy_to_session
            apply_proxy_to_session(self.session)
        except ImportError:
            pass

    def fetch_match_analysis(self, match_id: str) -> Optional[str]:
        """获取比赛分析页面HTML"""
        url = f"https://zq.titan007.com/analysis/{match_id}cn.htm"
        try:
            # 先访问主页获取cookies
            try:
                self.logger.info("访问主页获取cookies")
                self.session.get('https://zq.titan007.com/', headers=self.headers, timeout=10)
            except Exception as e:
                self.logger.warning(f"访问主页获取cookies失败: {e}")

            self.logger.info(f"正在获取比赛 {match_id} 的基本面数据...")
            response = self.session.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            html_content = self._decode_response(response)

            if html_content:
                self._save_html_snapshot(match_id, html_content)
                return html_content
            else:
                self.logger.error("无法正确解码HTML内容")
                return None
            
        except requests.RequestException as e:
            self.logger.error(f"获取数据失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"未知错误: {e}")
            return None

    def _save_html_snapshot(self, match_id: str, html_content: str) -> None:
        """保存原始HTML，便于后续排查解析问题。"""
        try:
            logs_dir = Path('logs/html_snapshots')
            logs_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path = logs_dir / f"analysis_{match_id}.html"
            snapshot_path.write_text(html_content, encoding='utf-8', errors='ignore')
        except Exception as exc:
            self.logger.debug(f"保存比赛 {match_id} HTML 快照失败: {exc}")

    def _decode_response(self, response):
        """
        尝试多种编码方式解码响应内容
        """
        raw = response.content

        def _normalize_encoding_name(name: str) -> str:
            return name.strip().strip('"\'').lower()

        def _evaluate_text_quality(text: str) -> float:
            if not text:
                return 0.0
            total = len(text)
            cjk = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
            kana = sum(1 for ch in text if '\u3040' <= ch <= '\u30ff')
            latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
            replacement = text.count('\ufffd')
            markup = text.count('<') + text.count('>')

            score = (cjk * 2 + kana * 1.5 + latin * 0.2) / max(total, 1)
            score -= replacement * 0.05

            if markup < 10 or '<html' not in text.lower():
                score -= 0.5
            return score

        encodings_to_try = []

        if response.encoding:
            encodings_to_try.append(response.encoding)

        # 在响应体中查找 charset 声明
        try:
            meta_match = re.search(b'charset=([a-zA-Z0-9_-]+)', raw[:2000])
            if meta_match:
                declared = meta_match.group(1).decode('ascii', errors='ignore')
                if declared:
                    encodings_to_try.append(declared)
        except Exception:
            pass

        encodings_to_try.extend(['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'utf-16', 'utf-16le', 'utf-16be'])

        results = []
        tried = set()
        for encoding in encodings_to_try:
            if not encoding:
                continue
            encoding = _normalize_encoding_name(encoding)
            if not encoding or encoding in tried:
                continue
            tried.add(encoding)
            try:
                content = raw.decode(encoding)
            except UnicodeDecodeError:
                continue
            score = _evaluate_text_quality(content)
            results.append((score, encoding, content))

        # 使用 requests 检测的编码再尝试一次
        try:
            apparent = response.apparent_encoding
            if apparent:
                apparent = _normalize_encoding_name(apparent)
                if apparent and apparent not in tried:
                    content = raw.decode(apparent, errors='ignore')
                    results.append((_evaluate_text_quality(content), apparent, content))
        except Exception:
            pass

        if results:
            best_score, best_encoding, best_content = max(results, key=lambda item: item[0])
            if best_score > 0:
                self.logger.info(f"成功使用 {best_encoding} 解码响应 (score={best_score:.3f})")
                return best_content.lstrip('\ufeff')

        # 最后使用替换模式
        try:
            content = raw.decode('utf-8', errors='replace')
            self.logger.warning("使用替换错误的方式解码响应")
            return content
        except Exception as e:
            self.logger.error(f"所有解码尝试均失败: {e}")
            return None

class FundamentalParser:
    """
    基本面数据解析器
    *** 此部分代码完全从 fundamental_analysis_parser.py 移植而来，以确保与原始标准100%一致 ***
    """
    def __init__(self, home_team="", away_team="", league_name=""):
        self.home_team = home_team
        self.away_team = away_team
        self.league_name = league_name
        self.logger = get_logger(self.__class__.__name__)
        self._table_title_aliases: Dict[str, List[str]] = {
            'history': ['交战历史', '历史交锋', '历史战绩', '双方交战', '交锋记录'],
            'home_team_history': ['主队近期赛事', '主队近期战绩', '主队近况', '主队近10场', '主队战绩'],
            'away_team_history': ['客队近期赛事', '客队近期战绩', '客队近况', '客队近10场', '客队战绩'],
            'home_team_home_history': ['主队主场赛事', '主队主场战绩', '主队主场近况', '主队主场近10场'],
            'away_team_away_history': ['客队客场赛事', '客队客场战绩', '客队客场近况', '客队客场近10场'],
        }
        self._js_variable_aliases: Dict[str, List[str]] = {
            'history': ['v_data', 'vdata'],
            'home_team_history': ['h_data', 'home_data'],
            'away_team_history': ['a_data', 'guest_data'],
            'home_team_home_history': ['h2_data', 'home_home_data'],
            'away_team_away_history': ['a2_data', 'guest_away_data'],
        }

    def parse_match_data(self, html_content: str, match_id: str = None):
        result = {
            'match_id': match_id,
            'basic_info': {},
            'analysis_data': {}
        }
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            if not soup.body:
                self.logger.error("HTML内容无效，没有body元素")
                result['parse_error'] = "收到的HTML内容无效或为空"
                return result
                
            self._extract_basic_info(soup, result['basic_info'])
            
            # 更新内部变量，这对于_determine_result至关重要
            self.home_team = result['basic_info'].get('home_team', self.home_team)
            self.away_team = result['basic_info'].get('away_team', self.away_team)
            self.league_name = result['basic_info'].get('league', self.league_name)

            analysis_data = result['analysis_data']
            for key, aliases in self._table_title_aliases.items():
                analysis_data[key] = self._extract_match_history(soup, aliases)

            js_data = self._extract_from_javascript(html_content)
            for key, js_values in js_data.items():
                if not analysis_data.get(key) and js_values:
                    analysis_data[key] = js_values
                    self.logger.info(f"使用从JavaScript提取的 {key} 数据")

        except Exception as e:
            self.logger.error(f"解析数据错误: {e}")
            result['parse_error'] = str(e)
            self.logger.error(traceback.format_exc())
            
        return result
        
    def _extract_basic_info(self, soup, result):
        try:
            home_link = soup.select_one('.analyhead .home a')
            guest_link = soup.select_one('.analyhead .guest a')
            league_link = soup.select_one('.analyhead .vs .row a.LName')

            if home_link and home_link.text:
                result['home_team'] = self._clean_team_name(home_link.text)
            if guest_link and guest_link.text:
                result['away_team'] = self._clean_team_name(guest_link.text)
            if league_link and league_link.text:
                league_text = league_link.get_text(strip=True).replace('\xa0', ' ')
                result['league'] = league_text.split()[0] if league_text else league_text

            title = soup.find('title')
            if title and 'vs' in title.text.lower():
                title_text = title.text.replace('\xa0', ' ')
                title_match = re.search(r'(.*?)\s+vs\s+(.*?)(?:\(|（)', title_text, re.IGNORECASE)
                if title_match:
                    result.setdefault('home_team', title_match.group(1).strip())
                    result.setdefault('away_team', title_match.group(2).strip())
                league_match = re.search(r'\(([^)（）]+)\)', title_text)
                if league_match and league_match.group(1):
                    result.setdefault('league', league_match.group(1).strip())

            script_tags = soup.find_all('script')
            for script in script_tags:
                script_text = script.string or ""
                if not script_text:
                    continue

                home_team_js = self._extract_js_string(script_text, 'hometeam')
                if home_team_js:
                    result['home_team'] = home_team_js

                away_team_js = self._extract_js_string(script_text, 'guestteam')
                if away_team_js:
                    result['away_team'] = away_team_js

                # leagueName 在部分页面使用单引号或双引号，统一处理
                league_name_js = self._extract_js_string(script_text, 'leagueName')
                if league_name_js:
                    result.setdefault('league', league_name_js)

                # 某些页面额外提供 leagueNameCn，作为补充
                league_name_cn_js = self._extract_js_string(script_text, 'leagueNameCn')
                if league_name_cn_js and not result.get('league'):
                    result['league'] = league_name_cn_js

        except Exception as e:
            self.logger.error(f"提取基本信息出错: {e}")

    def _extract_js_string(self, script_text: str, var_name: str) -> Optional[str]:
        """解析<script>文本中的简单字符串变量，兼容单双引号并处理转义。"""
        try:
            pattern = rf"var\s+{re.escape(var_name)}\s*=\s*(?P<value>'[^']*'|\"[^\"]*\"|[^;]+);"
            match = re.search(pattern, script_text)
            if not match:
                return None

            raw_value = match.group('value').strip()
            if raw_value.startswith(("'", '"')) and raw_value.endswith(("'", '"')):
                raw_value = raw_value[1:-1]

            try:
                if '\\u' in raw_value or '\\x' in raw_value:
                    return bytes(raw_value, 'utf-8').decode('unicode_escape')
                return raw_value
            except Exception:
                return raw_value
        except Exception as exc:  # pragma: no cover - 防御性兜底
            self.logger.debug(f"解析 JavaScript 变量 {var_name} 失败: {exc}")
            return None

    def _extract_match_history(self, soup, table_titles: Iterable[str]) -> List[List[Any]]:
        matches: List[List[Any]] = []
        try:
            if isinstance(table_titles, str):
                table_titles = [table_titles]

            target_table = None
            target_heading = None

            title_divs = soup.find_all(['div', 'h2', 'h3'], class_=['M_title', 'title'])
            for div in title_divs:
                span = div.find('span') or div
                text = span.get_text(strip=True) if span else ''
                if any(title in text for title in table_titles):
                    target_heading = text
                    target_table = div.find_next('table')
                    break

            if target_table is None:
                self.logger.debug(f"未找到标题匹配{list(table_titles)}的表格")
                return matches

            rows = target_table.find_all('tr')
            for row in rows[1:]:
                cols = row.find_all('td')
                if len(cols) < 7:
                    continue
                try:
                    date = self._get_text(cols[0])
                    league = self._get_text(cols[1])
                    home_team_name = self._get_text(cols[2])
                    score_text = self._get_text(cols[3])
                    score_parts = re.findall(r'\d+', score_text)
                    home_score = int(score_parts[0]) if len(score_parts) > 0 else 0
                    away_score = int(score_parts[1]) if len(score_parts) > 1 else 0
                    away_team_name = self._get_text(cols[4])
                    half_time = self._get_text(cols[5])
                    handicap_text = self._get_text(cols[6]) if len(cols) > 6 else "0"
                    try:
                        handicap = float(handicap_text) if handicap_text and handicap_text != "-" else 0.0
                    except ValueError:
                        handicap = 0.0
                    result_value = self._determine_result(target_heading or '', home_team_name, away_team_name, home_score, away_score)
                    match_row = [date, "", league, "", 0, home_team_name, "", away_team_name, home_score, away_score, half_time, handicap, result_value]
                    matches.append(match_row)
                except Exception as exc:
                    self.logger.error(f"处理表格行时出错: {exc}")

            if target_heading:
                self.logger.debug(f"从表格'{target_heading}'提取了{len(matches)}条记录")

        except Exception as e:
            self.logger.error(f"提取'{table_titles}'数据出错: {e}")

        return matches

    def _extract_from_javascript(self, html_content) -> Dict[str, List[Any]]:
        js_data: Dict[str, List[Any]] = {}
        try:
            for key, aliases in self._js_variable_aliases.items():
                for var_name in aliases:
                    data = self._extract_js_data(html_content, var_name)
                    if data:
                        js_data[key] = data
                        break
                if key not in js_data:
                    self.logger.debug(f"未能从JavaScript变量提取{key}记录")

            for key, value in js_data.items():
                self.logger.info(f"从JavaScript变量提取了{len(value)}条{key}记录")

        except Exception as e:
            self.logger.error(f"从JavaScript变量提取数据出错: {e}")

        return js_data

    def _extract_js_data(self, html_content, var_name):
        try:
            pattern = rf"var\s+{re.escape(var_name)}\s*=\s*(\[[\s\S]*?\]);"
            match = re.search(pattern, html_content)
            data_str = None

            if match:
                data_str = match.group(1).strip()
                if data_str == '[]':
                    constructed = self._extract_array_construction(html_content, var_name)
                    if constructed != '[]':
                        data_str = constructed
            else:
                init_pattern = rf"var\s+{re.escape(var_name)}\s*=\s*new\s+Array\s*\(\s*\);"
                if re.search(init_pattern, html_content):
                    data_str = self._extract_array_construction(html_content, var_name)

            if not data_str or data_str == '[]':
                return []

            safe_str = data_str.replace('null', 'None').replace('true', 'True').replace('false', 'False')
            try:
                return ast.literal_eval(safe_str)
            except Exception:
                self.logger.debug(f"literal_eval 解析 {var_name} 失败，尝试备用解析方案")
                items = re.findall(r'\[(.*?)\]', data_str)
                result: List[List[Any]] = []
                for item in items:
                    values: List[Any] = []
                    for val in item.split(','):
                        val = val.strip()
                        if not val:
                            values.append('')
                            continue
                        if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
                            values.append(val[1:-1])
                            continue
                        try:
                            values.append(int(val))
                            continue
                        except ValueError:
                            pass
                        try:
                            values.append(float(val))
                            continue
                        except ValueError:
                            values.append(val)
                    result.append(values)
                return result
        except Exception as e:
            self.logger.error(f"提取JavaScript变量{var_name}时出错: {e}")
        return []

    def _extract_array_construction(self, html_content: str, var_name: str) -> str:
        """处理 new Array() + push 风格的脚本结构，构造标准列表文本。"""
        entries: List[str] = []

        push_pattern = rf"{re.escape(var_name)}\.push\(([^;]+)\);"
        for match in re.finditer(push_pattern, html_content):
            entries.append(match.group(1).strip())

        if not entries:
            assign_pattern = rf"{re.escape(var_name)}\s*\[\s*{re.escape(var_name)}\.length\s*\]\s*=\s*(?:new\s+Array\(([^;]+)\)|\[(.*?)\]);"
            for match in re.finditer(assign_pattern, html_content):
                content = match.group(1) if match.group(1) is not None else match.group(2)
                if not content:
                    continue
                content = content.strip()
                if not content.startswith('['):
                    content = f"[{content}]"
                entries.append(content)

        if not entries:
            return '[]'

        normalized = []
        for entry in entries:
            entry = entry.strip()
            if entry.startswith('new Array(') and entry.endswith(')'):
                entry = entry[len('new Array('):-1]
            entry = entry.strip()
            if not entry.startswith('['):
                entry = f"[{entry}]"
            normalized.append(entry)

        return f"[{','.join(normalized)}]"
        
    def _get_text(self, element):
        try:
            text = element.get_text(strip=True)
            text = re.sub(r'#{2,}', '', text)
            return text
        except:
            return ""
            
    def _clean_team_name(self, text: str) -> str:
        cleaned = text.strip().replace('\xa0', ' ')
        cleaned = re.sub(r'[（(][^()（）]*[)）]', '', cleaned)
        return cleaned.strip()

    def _determine_result(self, table_title, home_team, away_team, home_score, away_score):
        # This logic is critical and must be exactly as in the original file
        if "交战历史" in table_title:
            if home_team == self.home_team:
                return 1 if home_score > away_score else (-1 if home_score < away_score else 0)
            else:
                return -1 if home_score > away_score else (1 if home_score < away_score else 0)
        elif "主队" in table_title:
            if home_team == self.home_team:
                return 1 if home_score > away_score else (-1 if home_score < away_score else 0)
            else:
                return -1 if home_score > away_score else (1 if home_score < away_score else 0)
        elif "客队" in table_title:
            if home_team == self.away_team:
                return 1 if home_score > away_score else (-1 if home_score < away_score else 0)
            else:
                return -1 if home_score > away_score else (1 if home_score < away_score else 0)
        return 0

class FundamentalDataFetcher:
    """基本面数据获取器 - 整合爬取和解析"""
    
    def __init__(self):
        self.scraper = FundamentalScraper()
        self.parser = FundamentalParser()
        self.logger = get_logger(self.__class__.__name__)
    
    def fetch_and_parse(self, match_id: str) -> Optional[Dict[str, Any]]:
        html_content = self.scraper.fetch_match_analysis(match_id)
        if not html_content:
            self.logger.error(f"无法获取比赛 {match_id} 的数据")
            return None
        
        # 解析器现在是自包含的，不再需要手动传递上下文
        parsed_data = self.parser.parse_match_data(html_content, match_id)

        if not parsed_data or 'parse_error' in parsed_data:
            self.logger.error(f"无法解析比赛 {match_id} 的数据")
            return None

        basic_info = parsed_data.get('basic_info', {})
        if not basic_info.get('league'):
            fallback_league = get_league_name(match_id=str(match_id), match_data=parsed_data)
            if fallback_league:
                basic_info['league'] = fallback_league
                parsed_data['basic_info'] = basic_info
                self.logger.info(f"补充比赛 {match_id} 的联赛信息: {fallback_league}")

        self.logger.info(f"成功获取比赛 {match_id} 的基本面数据")
        return parsed_data

if __name__ == "__main__":
    # Test
    fetcher = FundamentalDataFetcher()
    test_match_id = "2702229"
    print(f"测试获取比赛 {test_match_id} 的基本面数据...")
    data = fetcher.fetch_and_parse(test_match_id)
    
    if data:
        print(f"基本信息: {data.get('basic_info')}")
        print(f"历史交锋: {len(data.get('analysis_data', {}).get('history', []))} 条")
        print(f"主队历史: {len(data.get('analysis_data', {}).get('home_team_history', []))} 条")
        print(f"客队历史: {len(data.get('analysis_data', {}).get('away_team_history', []))} 条")
    else:
        print("获取失败")
