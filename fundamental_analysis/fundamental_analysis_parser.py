import logging
import re
import json
import traceback
from bs4 import BeautifulSoup

class MatchDataParser:
    """比赛数据解析类"""
    
    def __init__(self, home_team="", away_team="", league_name=""):
        """
        初始化数据解析器
        
        Args:
            home_team: 主队名
            away_team: 客队名
            league_name: 联赛名
        """
        self.home_team = home_team
        self.away_team = away_team
        self.league_name = league_name
        
    def parse_match_data(self, html_content):
        """
        解析球探网页面数据
        
        Args:
            html_content: HTML页面内容
            
        Returns:
            dict: 解析后的数据
        """
        result = {}
        
        # 使用BeautifulSoup解析HTML
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 检查HTML内容是否有效
            if not soup.body:
                logging.error("HTML内容无效，没有body元素")
                result['parse_error'] = "收到的HTML内容无效或为空"
                return result
                
            # 提取比赛基本信息
            self._extract_basic_info(soup, result)
            
            # 提取历史交锋记录
            result['history'] = self._extract_match_history(soup, '交战历史')
            
            # 提取主队历史记录
            result['home_team_history'] = self._extract_match_history(soup, '主队近期赛事')
            
            # 提取客队历史记录
            result['away_team_history'] = self._extract_match_history(soup, '客队近期赛事')
            
            # 提取主队主场历史
            result['home_team_home_history'] = self._extract_match_history(soup, '主队主场赛事')
            
            # 提取客队客场历史
            result['away_team_away_history'] = self._extract_match_history(soup, '客队客场赛事')
            
            # 提取排名信息
            self._extract_rankings(soup, result)
            
            # 尝试从JS变量中提取数据作为备份
            if not result.get('history') or not result.get('home_team_history') or not result.get('away_team_history'):
                logging.info("从HTML表格提取数据不完整，尝试从JavaScript变量中提取")
                js_data = self._extract_from_javascript(html_content, result)
                
                # 合并JS变量提取的数据
                if js_data:
                    for key, value in js_data.items():
                        if not result.get(key) and value:
                            result[key] = value
                            logging.info(f"使用从JavaScript提取的 {key} 数据")
            
        except Exception as e:
            logging.error(f"解析数据错误: {e}")
            result['parse_error'] = str(e)
            logging.error(traceback.format_exc())
            
        # 数据检查
        if 'home_team' not in result or not result['home_team']:
            # 尝试使用初始化时的队伍信息
            result['home_team'] = self.home_team
            result['away_team'] = self.away_team
            result['league_name'] = self.league_name
            logging.warning("使用初始化时的队伍信息作为备份")
            
        # 记录解析结果
        logging.info(f"提取的比赛数据: 主队={result.get('home_team')}, 客队={result.get('away_team')}")
        logging.info(f"历史交锋记录: {len(result.get('history', []))}条")
        logging.info(f"主队历史记录: {len(result.get('home_team_history', []))}条")
        logging.info(f"客队历史记录: {len(result.get('away_team_history', []))}条")
        logging.info(f"主队主场记录: {len(result.get('home_team_home_history', []))}条")
        logging.info(f"客队客场记录: {len(result.get('away_team_away_history', []))}条")
        
        # 记录主队主场和客队客场数据的详细信息
        if result.get('home_team_home_history'):
            logging.info(f"主队主场数据有效性检查: {self._validate_history_data(result['home_team_home_history'])}")
            if len(result['home_team_home_history']) > 0:
                first_match = result['home_team_home_history'][0]
                if len(first_match) >= 13:
                    logging.info(f"主队主场首场比赛: {first_match[0]} {first_match[2]} {first_match[5]} vs {first_match[7]} {first_match[8]}-{first_match[9]}")
                
        if result.get('away_team_away_history'):
            logging.info(f"客队客场数据有效性检查: {self._validate_history_data(result['away_team_away_history'])}")
            if len(result['away_team_away_history']) > 0:
                first_match = result['away_team_away_history'][0]
                if len(first_match) >= 13:
                    logging.info(f"客队客场首场比赛: {first_match[0]} {first_match[2]} {first_match[5]} vs {first_match[7]} {first_match[8]}-{first_match[9]}")
        
        return result
        
    def _extract_basic_info(self, soup, result):
        """
        从页面提取基本比赛信息
        
        Args:
            soup: BeautifulSoup对象
            result: 结果字典
        """
        try:
            # 从标题提取
            title = soup.find('title')
            if title and 'vs' in title.text:
                title_text = title.text
                title_match = re.search(r'(.*?)vs(.*?)\s*-\s*(.*?)比赛分析', title_text)
                if title_match:
                    result['home_team'] = title_match.group(1).strip()
                    result['away_team'] = title_match.group(2).strip()
                    result['league_name'] = title_match.group(3).strip()
                    logging.info(f"从标题提取: {result['home_team']} vs {result['away_team']} - {result['league_name']}")
                    
            # 尝试从JavaScript变量中提取
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string:
                    # 提取比赛ID
                    schedule_id_match = re.search(r'var scheduleID = (\d+);', script.string)
                    if schedule_id_match:
                        result['schedule_id'] = schedule_id_match.group(1)
                        
                    # 提取队伍名称
                    home_team_match = re.search(r'var hometeam = "([^"]+)";', script.string)
                    if home_team_match:
                        result['home_team'] = home_team_match.group(1)
                        
                    away_team_match = re.search(r'var guestteam = "([^"]+)";', script.string)
                    if away_team_match:
                        result['away_team'] = away_team_match.group(1)
                        
            # 如果JavaScript变量中没有找到，尝试从URL提取
            if 'schedule_id' not in result and soup.base:
                base_href = soup.base.get('href', '')
                match_id_match = re.search(r'analysis/(\d+)cn\.htm', base_href)
                if match_id_match:
                    result['schedule_id'] = match_id_match.group(1)
                    
            # 记录提取结果
            logging.info(f"提取的比赛ID: {result.get('schedule_id')}")
            logging.info(f"提取的主队: {result.get('home_team')}")
            logging.info(f"提取的客队: {result.get('away_team')}")
            
        except Exception as e:
            logging.error(f"提取基本信息出错: {e}")
            
    def _extract_match_history(self, soup, table_title):
        """
        提取比赛历史记录
        
        Args:
            soup: BeautifulSoup对象
            table_title: 表格标题（如"交战历史"、"主队近期赛事"等）
            
        Returns:
            list: 比赛记录列表
        """
        matches = []
        try:
            # 查找包含表格标题的div
            title_divs = soup.find_all('div', class_='M_title')
            target_div = None
            
            for div in title_divs:
                span = div.find('span')
                if span and table_title in span.text:
                    target_div = div
                    break
                    
            if target_div:
                # 找到对应的表格
                table = target_div.find_next('table')
                if table:
                    # 提取表格行
                    rows = table.find_all('tr')
                    
                    # 跳过表头
                    for row in rows[1:]:
                        cols = row.find_all('td')
                        if len(cols) >= 7:
                            try:
                                # 处理每列数据
                                date = self._get_text(cols[0])
                                league = self._get_text(cols[1])
                                home_team = self._get_text(cols[2])
                                
                                # 处理比分
                                score_text = self._get_text(cols[3])
                                score_parts = re.findall(r'\d+', score_text)
                                home_score = int(score_parts[0]) if len(score_parts) > 0 else 0
                                away_score = int(score_parts[1]) if len(score_parts) > 1 else 0
                                
                                away_team = self._get_text(cols[4])
                                half_time = self._get_text(cols[5])
                                
                                # 尝试提取让球
                                handicap_text = self._get_text(cols[6]) if len(cols) > 6 else "0"
                                handicap = 0
                                try:
                                    handicap = float(handicap_text) if handicap_text and handicap_text != "-" else 0
                                except ValueError:
                                    handicap = 0
                                    
                                # 确定输赢
                                result_value = self._determine_result(table_title, home_team, away_team, home_score, away_score)
                                
                                # 构建匹配标准格式的数据行
                                match_row = [date, "", league, "", 0, home_team, "", away_team, home_score, away_score, half_time, handicap, result_value]
                                matches.append(match_row)
                            except Exception as e:
                                logging.error(f"处理表格行时出错: {e}")
                                
                    logging.info(f"从表格'{table_title}'提取了{len(matches)}条记录")
                else:
                    logging.warning(f"未找到'{table_title}'对应的表格")
            else:
                logging.warning(f"未找到标题为'{table_title}'的表格")
                
        except Exception as e:
            logging.error(f"提取'{table_title}'数据出错: {e}")
            
        return matches
        
    def _extract_rankings(self, soup, result):
        """
        从页面提取排名信息
        
        Args:
            soup: BeautifulSoup对象
            result: 结果字典
        """
        try:
            # 查找包含排名信息的元素
            rank_elements = soup.find_all('div', string=lambda text: text and '联赛排名' in text)
            if rank_elements:
                rank_text = rank_elements[0].text
                rank_match = re.search(r'联赛排名：主\s*(\d+)\s*客\s*(\d+)', rank_text)
                if rank_match:
                    result['home_rank'] = rank_match.group(1)
                    result['away_rank'] = rank_match.group(2)
                    logging.info(f"从排名文本提取: 主 {result['home_rank']}, 客 {result['away_rank']}")
            else:
                # 备用方法：从队名旁边的排名提取
                team_elements = soup.find_all(string=lambda text: text and self.home_team in text)
                for elem in team_elements:
                    rank_match = re.search(fr'{re.escape(self.home_team)}\s*\[(\d+)\]', elem)
                    if rank_match:
                        result['home_rank'] = rank_match.group(1)
                        logging.info(f"从队名提取主队排名: {result['home_rank']}")
                        break
                        
                team_elements = soup.find_all(string=lambda text: text and self.away_team in text)
                for elem in team_elements:
                    rank_match = re.search(fr'{re.escape(self.away_team)}\s*\[(\d+)\]', elem)
                    if rank_match:
                        result['away_rank'] = rank_match.group(1)
                        logging.info(f"从队名提取客队排名: {result['away_rank']}")
                        break
        except Exception as e:
            logging.error(f"提取排名信息出错: {e}")
            
    def _extract_from_javascript(self, html_content, result):
        """
        从JavaScript变量中提取数据
        
        Args:
            html_content: HTML内容
            result: 当前结果字典
            
        Returns:
            dict: 提取的数据
        """
        js_data = {}
        
        try:
            # 提取交战历史数据
            js_data['history'] = self._extract_js_data(html_content, 'v_data')
            
            # 提取主队历史数据
            js_data['home_team_history'] = self._extract_js_data(html_content, 'h_data')
            
            # 提取客队历史数据
            js_data['away_team_history'] = self._extract_js_data(html_content, 'a_data')
            
            # 提取主队主场历史数据
            js_data['home_team_home_history'] = self._extract_js_data(html_content, 'h2_data')
            
            # 提取客队客场历史数据
            js_data['away_team_away_history'] = self._extract_js_data(html_content, 'a2_data')
            
            # 记录提取结果
            for key, value in js_data.items():
                if value:
                    logging.info(f"从JavaScript变量提取了{len(value)}条{key}记录")
                else:
                    logging.warning(f"未能从JavaScript变量提取{key}记录")
                    
        except Exception as e:
            logging.error(f"从JavaScript变量提取数据出错: {e}")
            
        return js_data
        
    def _extract_js_data(self, html_content, var_name):
        """
        从JavaScript变量中提取数据
        
        Args:
            html_content: HTML内容
            var_name: 变量名
            
        Returns:
            list: 提取的数据列表
        """
        try:
            pattern = f'var {var_name} = (.*?);\r?\n'
            match = re.search(pattern, html_content, re.DOTALL)
            
            if match:
                data_str = match.group(1).strip()
                if data_str and data_str != "[]":
                    # 简单处理JS数组格式，转为Python列表
                    try:
                        # 使用json模块解析，要先将JS数组转换为标准JSON格式
                        # 替换JS中的单引号为双引号
                        data_str = data_str.replace("'", '"')
                        # 尝试解析JSON
                        data = json.loads(data_str)
                        return data
                    except json.JSONDecodeError:
                        # 如果JSON解析失败，尝试直接处理字符串
                        logging.warning(f"JSON解析{var_name}失败，尝试替代方法")
                        
                        # 移除字符串前后的方括号
                        if data_str.startswith('[') and data_str.endswith(']'):
                            data_str = data_str[1:-1].strip()
                            
                        # 按逗号分隔每个数组项
                        items = re.findall(r'\[(.*?)\]', data_str)
                        result = []
                        
                        for item in items:
                            try:
                                # 处理每个数组项
                                values = item.split(',')
                                processed_values = []
                                
                                for val in values:
                                    val = val.strip()
                                    # 处理字符串、数字和空值
                                    if val.startswith('"') or val.startswith("'"):
                                        # 字符串
                                        processed_values.append(val.strip('"\''))
                                    elif val == '':
                                        # 空值
                                        processed_values.append('')
                                    else:
                                        # 尝试转换为数字
                                        try:
                                            if '.' in val:
                                                processed_values.append(float(val))
                                            else:
                                                processed_values.append(int(val))
                                        except ValueError:
                                            processed_values.append(val)
                                            
                                result.append(processed_values)
                            except Exception as e:
                                logging.error(f"处理{var_name}数组项时出错: {e}")
                                
                        return result
            else:
                logging.warning(f"未找到JavaScript变量: {var_name}")
        except Exception as e:
            logging.error(f"提取JavaScript变量{var_name}时出错: {e}")
            
        return []
        
    def _get_text(self, element):
        """
        安全地从元素中提取文本并清理
        
        Args:
            element: BeautifulSoup元素
            
        Returns:
            str: 提取的文本
        """
        try:
            text = element.get_text(strip=True)
            # 清理特殊字符
            text = re.sub(r'#{2,}', '', text)
            return text
        except:
            return ""
            
    def _clean_text(self, text):
        """
        清理文本中的HTML标签和特殊字符
        
        Args:
            text: 输入文本
            
        Returns:
            str: 清理后的文本
        """
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除特殊字符如##
        text = re.sub(r'#{2,}', '', text)
        # 移除多余空白字符
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
        
    def _determine_result(self, table_title, home_team, away_team, home_score, away_score):
        """
        确定比赛结果
        
        Args:
            table_title: 表格标题
            home_team: 主队名称
            away_team: 客队名称
            home_score: 主队进球
            away_score: 客队进球
            
        Returns:
            int: 结果值（1=胜，0=平，-1=负）
        """
        result_value = 0
        
        # 交战历史的结果根据当前比赛的主队判断
        if "交战历史" in table_title:
            if home_team == self.home_team:
                # 主队是主场
                result_value = 1 if home_score > away_score else (-1 if home_score < away_score else 0)
            else:
                # 主队是客场
                result_value = -1 if home_score > away_score else (1 if home_score < away_score else 0)
                
        # 主队记录
        elif "主队" in table_title:
            if home_team == self.home_team:
                # 主队是主场
                result_value = 1 if home_score > away_score else (-1 if home_score < away_score else 0)
            else:
                # 主队是客场
                result_value = -1 if home_score > away_score else (1 if home_score < away_score else 0)
                
        # 客队记录
        elif "客队" in table_title:
            if home_team == self.away_team:
                # 客队是主场
                result_value = 1 if home_score > away_score else (-1 if home_score < away_score else 0)
            else:
                # 客队是客场
                result_value = -1 if home_score > away_score else (1 if home_score < away_score else 0)
                
        return result_value
        
    def validate_match_data(self, data):
        """
        验证解析后的数据是否完整有效
        
        Args:
            data: 解析后的数据
            
        Returns:
            bool: 数据是否有效
        """
        # 检查是否有解析错误
        if 'parse_error' in data:
            logging.error(f"数据解析错误: {data['parse_error']}")
            return False
            
        # 检查必要的字段是否存在
        required_fields = ['home_team', 'away_team']
        for field in required_fields:
            if field not in data or not data[field]:
                logging.error(f"缺少必要字段: {field}")
                return False
                
        # 检查至少有一种比赛历史数据
        data_sources = ['history', 'home_team_history', 'away_team_history']
        has_data = False
        for source in data_sources:
            if source in data and isinstance(data[source], list) and len(data[source]) > 0:
                has_data = True
                logging.info(f"找到有效数据源: {source} ({len(data[source])}条记录)")
                break
                
        if not has_data:
            logging.error("没有找到任何有效的比赛历史数据")
            
        return has_data
        
    def _validate_history_data(self, history_data):
        """
        验证历史数据的有效性
        
        Args:
            history_data: 历史数据列表
            
        Returns:
            str: 验证结果描述
        """
        if not history_data or not isinstance(history_data, list):
            return "数据不存在或格式错误"
            
        if len(history_data) == 0:
            return "数据列表为空"
            
        # 检查数据结构
        valid_items = 0
        invalid_items = 0
        
        for item in history_data:
            if isinstance(item, list) and len(item) >= 13:
                valid_items += 1
            else:
                invalid_items += 1
                
        if valid_items == 0:
            return f"所有{len(history_data)}项数据结构无效"
        elif invalid_items > 0:
            return f"部分数据有效: {valid_items}有效/{invalid_items}无效"
        else:
            return f"全部{valid_items}项数据有效" 