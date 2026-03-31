import logging
import traceback
from football_analysis_system.config import COLOR_BG, COLOR_HOME, COLOR_AWAY, COLOR_PRIMARY, COLOR_ACCENT, COLOR_TEXT, COLOR_TEXT_LIGHT

class ResultFormatter:
    """分析结果格式化类"""
    
    def __init__(self, ui_component=None):
        """
        初始化结果格式化器
        
        Args:
            ui_component: UI组件，用于展示结果
        """
        self.ui = ui_component
        self.home_team = ""
        self.away_team = ""
        self.league_name = ""
        
    def set_teams(self, home_team, away_team, league_name):
        """
        设置比赛队伍和联赛
        
        Args:
            home_team: 主队名称
            away_team: 客队名称
            league_name: 联赛名称
        """
        self.home_team = home_team
        self.away_team = away_team
        self.league_name = league_name
        
    def format_and_display_result(self, data, ratings=None):
        """
        格式化并显示分析结果
        
        Args:
            data: 解析后的数据
            ratings: 评分结果，如果为None则使用默认评分
        """
        try:
            logging.info("开始格式化分析结果...")
            
            # 检查是否有解析错误
            if 'parse_error' in data:
                logging.warning("检测到解析错误，显示错误信息")
                self._display_parse_error(data)
                return
                
            # 检查基本数据是否存在
            if not data.get('home_team') or not data.get('away_team'):
                logging.warning("基本数据不完整，显示数据不完整提示")
                self.ui.append_result("# 数据不完整\n\n")
                self.ui.append_result("抱歉，无法获取完整的比赛数据。可能是因为该比赛信息尚未在球探网上更新。\n\n")
                self.ui.append_result("请稍后再试。\n")
                return
                
            # 更新队伍信息
            self.home_team = data.get('home_team', self.home_team)
            self.away_team = data.get('away_team', self.away_team)
            
            logging.info(f"开始显示分析结果: {self.home_team} vs {self.away_team}")
            
            # 显示标题和基本信息
            logging.info("显示比赛标题和基本信息...")
            self._display_match_header(data)
            
            # 显示历史交锋记录
            logging.info("显示历史交锋记录...")
            self._display_history(data)
            
            # 显示球队近期战绩
            logging.info("显示球队近期战绩...")
            self._display_team_recent_form(data)
            
            # 显示统计分析
            logging.info("显示统计分析...")
            self._display_statistics_analysis(data)
            
            # 显示胜平负倾向分析
            logging.info("显示胜平负倾向分析...")
            self._display_result_tendency(data, ratings)
            
            # 数据来源
            logging.info("添加数据来源信息...")
            self.ui.append_result("\n\n*数据来源：球探网，分析仅供参考*")
            
            logging.info("基本面分析结果格式化完成！")
            
        except Exception as e:
            logging.error(f"格式化分析结果错误: {e}")
            logging.error(traceback.format_exc())
            self.ui.append_result(f"\n\n格式化分析结果出错: {e}\n")
            
            # 显示基本比赛信息作为备份
            self._display_basic_match_info()
            
    def _display_parse_error(self, data):
        """
        显示解析错误信息
        
        Args:
            data: 数据字典
        """
        error_msg = data.get('parse_error')
        self.ui.append_result("# 数据解析错误\n\n")
        self.ui.append_result(f"抱歉，在解析比赛数据时遇到问题: {error_msg}\n\n")
        self.ui.append_result("请尝试以下解决方法:\n")
        self.ui.append_result("1. 刷新页面后重试\n")
        self.ui.append_result("2. 确认比赛ID是否正确\n")
        self.ui.append_result("3. 检查网络连接\n")
        
        # 添加错误详情
        self.ui.append_result("\n## 技术信息\n")
        self.ui.append_result(f"- 主队: {self.home_team}\n")
        self.ui.append_result(f"- 客队: {self.away_team}\n")
        self.ui.append_result(f"- 联赛: {self.league_name}\n")
        
    def _display_match_header(self, data):
        """
        显示比赛标题和基本信息
        
        Args:
            data: 数据字典
        """
        try:
            logging.info("开始显示比赛标题...")
            # 标题
            self.ui.append_result(f"# ")
            self.ui.append_colored_result(f"{self.home_team}", COLOR_HOME)
            self.ui.append_result(" VS ")
            self.ui.append_colored_result(f"{self.away_team}", COLOR_AWAY)
            self.ui.append_result(f" - {self.league_name} 分析\n\n")
            
            logging.info("开始显示基本信息...")
            # 基本信息
            self.ui.append_result("## 基本信息\n")
            home_rank = data.get('home_rank', '未知')
            away_rank = data.get('away_rank', '未知')
            self.ui.append_result(f"- 主队: ")
            self.ui.append_colored_result(f"{self.home_team}", COLOR_HOME)
            self.ui.append_result(f" [联赛排名: {home_rank}]\n")
            self.ui.append_result(f"- 客队: ")
            self.ui.append_colored_result(f"{self.away_team}", COLOR_AWAY)
            self.ui.append_result(f" [联赛排名: {away_rank}]\n\n")
            
            logging.info("比赛标题和基本信息显示完成")
            
        except Exception as e:
            logging.error(f"显示比赛标题出错: {e}")
            logging.error(traceback.format_exc())
        
    def _display_history(self, data):
        """
        显示历史交锋记录
        
        Args:
            data: 数据字典
        """
        history_data = data.get('history', [])
        self.ui.append_result("## 历史交锋记录\n")
        
        if history_data:
            # 过滤掉友谊赛（但保留杯赛）
            filtered_history = []
            for match in history_data:
                try:
                    if len(match) >= 13:
                        league = str(match[2])
                        if not self._is_friendly_match(league):
                            filtered_history.append(match)
                        else:
                            logging.info(f"历史交锋中过滤掉友谊赛: {league}")
                except (IndexError, TypeError) as e:
                    logging.error(f"过滤历史交锋记录出错: {e}")
                    continue
                    
            if filtered_history:
                self.ui.append_result("| 日期 | 赛事 | 主队 | 比分 | 客队 | 半场 | 让球 | 赛果 |\n")
                self.ui.append_result("|------|------|------|------|------|------|------|------|\n")
                
                # 限制展示5场历史交锋 - 与评分系统保持一致
                recent_history = filtered_history[:6] if len(filtered_history) > 6 else filtered_history
                
                # 添加安全处理
                display_count = 0
                for match in recent_history:
                    try:
                        if len(match) < 13:  # 确保数据完整
                            continue
                            
                        date = str(match[0])
                        league = str(match[2])
                        home_team_name = self._clean_text(str(match[5]))
                        away_team_name = self._clean_text(str(match[7]))
                        score = f"{match[8]}-{match[9]}"
                        half_time = str(match[10])
                        handicap = str(match[11]) if match[11] else "0"
                        
                        # 结果使用不同颜色标记
                        if match[12] > 0:  # 主胜
                            result = "主胜"
                            result_color = COLOR_HOME
                        elif match[12] < 0:  # 客胜
                            result = "客胜"
                            result_color = COLOR_AWAY
                        else:  # 平局
                            result = "平局"
                            result_color = COLOR_TEXT
                            
                        # 构建行内容
                        self.ui.append_result(f"| {date} | {league} | ")
                        
                        # 标记主队
                        if home_team_name == self.home_team:
                            self.ui.append_colored_result(home_team_name, COLOR_HOME)
                        elif home_team_name == self.away_team:
                            self.ui.append_colored_result(home_team_name, COLOR_AWAY)
                        else:
                            self.ui.append_result(home_team_name)
                            
                        self.ui.append_result(f" | {score} | ")
                        
                        # 标记客队
                        if away_team_name == self.home_team:
                            self.ui.append_colored_result(away_team_name, COLOR_HOME)
                        elif away_team_name == self.away_team:
                            self.ui.append_colored_result(away_team_name, COLOR_AWAY)
                        else:
                            self.ui.append_result(away_team_name)
                            
                        self.ui.append_result(f" | {half_time} | {handicap} | ")
                        
                        # 标记结果
                        self.ui.append_colored_result(result, result_color)
                        self.ui.append_result(" |\n")
                        
                        display_count += 1
                    except (IndexError, TypeError) as e:
                        logging.error(f"处理历史交锋记录出错: {e}")
                        continue
                        
                if display_count == 0:
                    self.ui.append_result("*过滤后未找到有效的历史交锋记录*\n")
            else:
                self.ui.append_result("*没有符合条件的历史交锋记录*\n")
        else:
            self.ui.append_result("*没有历史交锋记录*\n")
            
        self.ui.append_result("\n")
     
    def _clean_text(self, text):
        """
        清理文本中的特殊字符
        
        Args:
            text: 输入文本
            
        Returns:
            str: 清理后的文本
        """
        # 移除HTML标签
        import re
        text = re.sub(r'<[^>]+>', '', text)
        # 移除特殊字符如##
        text = re.sub(r'#{2,}', '', text)
        # 移除多余空白字符
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
        
    def _display_team_recent_form(self, data):
        """
        显示球队近期战绩
        
        Args:
            data: 数据字典
        """
        # 主队最近战绩 - 修改为显示10场比赛
        home_history = data.get('home_team_history', [])
        self.ui.append_result("## ")
        self.ui.append_colored_result(f"{self.home_team}", COLOR_HOME)
        self.ui.append_result(" 最近战绩（近10场联赛比赛）\n")
        
        if home_history:
            # 过滤掉杯赛和友谊赛，只保留当前联赛比赛
            filtered_history = []
            for match in home_history:
                try:
                    if len(match) >= 13:
                        league = str(match[2])
                        # 检查是否为当前联赛（而不是杯赛或其他联赛）
                        if league == self.league_name and not "锦" in league and not self._is_cup_or_friendly(league):
                            filtered_history.append(match)
                        else:
                            logging.info(f"主队历史中过滤掉非{self.league_name}比赛或杯赛: {league}")
                except (IndexError, TypeError) as e:
                    logging.error(f"过滤主队历史记录出错: {e}")
                    continue
                    
            if filtered_history:
                self.ui.append_result("| 日期 | 赛事 | 对阵 | 比分 | 半场 | 让球 | 赛果 |\n")
                self.ui.append_result("|------|------|------|------|------|------|------|\n")
                
                # 修改：展示最近10场联赛比赛
                recent_home = filtered_history[:10] if len(filtered_history) > 10 else filtered_history
                
                # 添加安全处理
                display_count = 0
                for match in recent_home:
                    try:
                        if len(match) < 13:  # 确保数据完整
                            continue
                            
                        date = str(match[0])
                        league = str(match[2])
                        home_team_name = self._clean_text(str(match[5]))
                        away_team_name = self._clean_text(str(match[7]))
                        score = f"{match[8]}-{match[9]}"
                        half_time = str(match[10])
                        handicap = str(match[11]) if match[11] else "0"
                        
                        # 结果使用不同颜色标记
                        if match[12] > 0:  # 胜
                            result = "胜"
                            result_color = COLOR_HOME  # 主队用主队颜色
                        elif match[12] < 0:  # 负
                            result = "负"
                            result_color = COLOR_AWAY  # 败方用客队颜色
                        else:  # 平
                            result = "平"
                            result_color = COLOR_TEXT  # 平局用默认颜色
                            
                        # 构建对阵字符串
                        self.ui.append_result(f"| {date} | {league} | ")
                        
                        # 标记主队和客队
                        if home_team_name == self.home_team:
                            self.ui.append_colored_result(home_team_name, COLOR_HOME)
                            self.ui.append_result(" vs ")
                            self.ui.append_result(away_team_name)
                        elif away_team_name == self.home_team:
                            self.ui.append_result(home_team_name)
                            self.ui.append_result(" vs ")
                            self.ui.append_colored_result(away_team_name, COLOR_HOME)
                        else:
                            if home_team_name == self.away_team:
                                self.ui.append_colored_result(home_team_name, COLOR_AWAY)
                            else:
                                self.ui.append_result(home_team_name)
                            self.ui.append_result(" vs ")
                            if away_team_name == self.away_team:
                                self.ui.append_colored_result(away_team_name, COLOR_AWAY)
                            else:
                                self.ui.append_result(away_team_name)
                                
                        self.ui.append_result(f" | {score} | {half_time} | {handicap} | ")
                        self.ui.append_colored_result(result, result_color)
                        self.ui.append_result(" |\n")
                        
                        display_count += 1
                    except (IndexError, TypeError) as e:
                        logging.error(f"处理主队历史记录出错: {e}")
                        continue
                        
                if display_count == 0:
                    self.ui.append_result("*过滤后未找到有效的主队历史记录*\n")
            else:
                self.ui.append_result("*没有符合条件的主队历史战绩记录*\n")
        else:
            self.ui.append_result("*没有主队历史战绩记录*\n")
            
        self.ui.append_result("\n")
        
        # 客队最近战绩 - 修改为显示10场比赛
        away_history = data.get('away_team_history', [])
        self.ui.append_result("## ")
        self.ui.append_colored_result(f"{self.away_team}", COLOR_AWAY)
        self.ui.append_result(" 最近战绩（近10场联赛比赛）\n")
        
        if away_history:
            # 过滤掉杯赛和友谊赛，只保留当前联赛比赛
            filtered_history = []
            for match in away_history:
                try:
                    if len(match) >= 13:
                        league = str(match[2])
                        # 检查是否为当前联赛（而不是杯赛或其他联赛）
                        if league == self.league_name and not "锦" in league and not self._is_cup_or_friendly(league):
                            filtered_history.append(match)
                        else:
                            logging.info(f"客队历史中过滤掉非{self.league_name}比赛或杯赛: {league}")
                except (IndexError, TypeError) as e:
                    logging.error(f"过滤客队历史记录出错: {e}")
                    continue
                    
            if filtered_history:
                self.ui.append_result("| 日期 | 赛事 | 对阵 | 比分 | 半场 | 让球 | 赛果 |\n")
                self.ui.append_result("|------|------|------|------|------|------|------|\n")
                
                # 修改：展示最近10场联赛比赛
                recent_away = filtered_history[:10] if len(filtered_history) > 10 else filtered_history
                
                # 添加安全处理
                display_count = 0
                for match in recent_away:
                    try:
                        if len(match) < 13:  # 确保数据完整
                            continue
                            
                        date = str(match[0])
                        league = str(match[2])
                        home_team_name = self._clean_text(str(match[5]))
                        away_team_name = self._clean_text(str(match[7]))
                        score = f"{match[8]}-{match[9]}"
                        half_time = str(match[10])
                        handicap = str(match[11]) if match[11] else "0"
                        
                        # 结果使用不同颜色标记
                        if match[12] > 0:  # 胜
                            result = "胜"
                            result_color = COLOR_HOME  # 胜方用主队颜色
                        elif match[12] < 0:  # 负
                            result = "负"
                            result_color = COLOR_AWAY  # 负方用客队颜色
                        else:  # 平
                            result = "平"
                            result_color = COLOR_TEXT  # 平局用默认颜色
                            
                        # 构建对阵字符串
                        self.ui.append_result(f"| {date} | {league} | ")
                        
                        # 标记主队和客队
                        if home_team_name == self.away_team:
                            self.ui.append_colored_result(home_team_name, COLOR_AWAY)
                            self.ui.append_result(" vs ")
                            self.ui.append_result(away_team_name)
                        elif away_team_name == self.away_team:
                            self.ui.append_result(home_team_name)
                            self.ui.append_result(" vs ")
                            self.ui.append_colored_result(away_team_name, COLOR_AWAY)
                        else:
                            if home_team_name == self.home_team:
                                self.ui.append_colored_result(home_team_name, COLOR_HOME)
                            else:
                                self.ui.append_result(home_team_name)
                            self.ui.append_result(" vs ")
                            if away_team_name == self.home_team:
                                self.ui.append_colored_result(away_team_name, COLOR_HOME)
                            else:
                                self.ui.append_result(away_team_name)
                                
                        self.ui.append_result(f" | {score} | {half_time} | {handicap} | ")
                        self.ui.append_colored_result(result, result_color)
                        self.ui.append_result(" |\n")
                        
                        display_count += 1
                    except (IndexError, TypeError) as e:
                        logging.error(f"处理客队历史记录出错: {e}")
                        continue
                        
                if display_count == 0:
                    self.ui.append_result("*过滤后未找到有效的客队历史记录*\n")
            else:
                self.ui.append_result("*没有符合条件的客队历史记录*\n")
                
        self.ui.append_result("\n")
        
    def _is_cup_or_friendly(self, league_name):
        """
        判断比赛是否为杯赛或友谊赛
        
        Args:
            league_name: 赛事名称
            
        Returns:
            bool: 如果是杯赛或友谊赛返回True，否则返回False
        """
        # 转换为小写，便于大小写不敏感的匹配
        league_lower = league_name.lower()
        
        # 检查是否包含"杯"、"友谊赛"、"友谊"、"杯赛"等关键词
        cup_keywords = ["杯", "杯赛", "锦标赛", "联赛杯", "足总杯", "欧洲杯", "世界杯", "冠军杯",
                       "挑战杯", "淘汰赛", "championship", "cup", "trophy"]
        friendly_keywords = ["友谊赛", "友谊", "友谊联赛", "表演赛", "热身赛", "friendly"]
        
        # 检查杯赛关键词
        for keyword in cup_keywords:
            if keyword in league_lower:
                return True
                
        # 检查友谊赛关键词
        for keyword in friendly_keywords:
            if keyword in league_lower:
                return True
                
        return False
        
    def _is_friendly_match(self, league_name):
        """
        判断比赛是否为友谊赛
        
        Args:
            league_name: 赛事名称
            
        Returns:
            bool: 如果是友谊赛返回True，否则返回False
        """
        league_lower = league_name.lower()
        friendly_keywords = ["友谊赛", "友谊", "友谊联赛", "表演赛", "热身赛", "friendly"]
        
        for keyword in friendly_keywords:
            if keyword in league_lower:
                return True
                
        return False
        
    def _display_statistics_analysis(self, data):
        """
        显示统计分析结果
        
        Args:
            data: 数据字典
        """
        # 如果数据极少，可能无法进行后续分析
        if not data.get('history') and not data.get('home_team_history') and not data.get('away_team_history'):
            self.ui.append_result("## 数据不足提示\n\n")
            self.ui.append_result("当前数据不足以进行全面分析。以下结果仅基于有限数据进行预测，请谨慎参考。\n\n")
            
        # 战绩统计分析
        self.ui.append_result("## 战绩统计分析\n\n")
        
        # 历史交锋统计（包含杯赛，但不包含友谊赛）
        history_data = data.get('history', [])
        if history_data:
            try:
                # 过滤掉友谊赛，保留杯赛
                valid_matches = []
                for match in history_data:
                    if isinstance(match, list) and len(match) > 12:
                        league = str(match[2])
                        if not self._is_friendly_match(league):
                            valid_matches.append(match)
                            
                home_wins = sum(1 for match in valid_matches if match[12] > 0)
                draws = sum(1 for match in valid_matches if match[12] == 0)
                away_wins = sum(1 for match in valid_matches if match[12] < 0)
                total_matches = len(valid_matches)
                
                self.ui.append_result("### 历史交锋\n")
                self.ui.append_result(f"- 总交锋: {total_matches}场\n")
                self.ui.append_result(f"- ")
                self.ui.append_colored_result(f"{self.home_team}", COLOR_HOME)
                self.ui.append_result(" ")
                self.ui.append_colored_result(f"{home_wins}胜", COLOR_HOME)
                self.ui.append_result(f"{draws}平")
                self.ui.append_colored_result(f"{away_wins}负", COLOR_AWAY)
                self.ui.append_result("\n")
                
                try:
                    home_goals = sum(match[8] for match in valid_matches if isinstance(match[8], (int, float)))
                    away_goals = sum(match[9] for match in valid_matches if isinstance(match[9], (int, float)))
                    self.ui.append_result(f"- 进球: ")
                    self.ui.append_colored_result(f"{self.home_team}", COLOR_HOME)
                    self.ui.append_result(f"进{home_goals}球，")
                    self.ui.append_colored_result(f"{self.away_team}", COLOR_AWAY)
                    self.ui.append_result(f"进{away_goals}球\n\n")
                except (TypeError, IndexError) as e:
                    logging.error(f"计算进球数据出错: {e}")
                    self.ui.append_result("- 进球数据计算失败\n\n")
            except Exception as e:
                logging.error(f"历史交锋统计出错: {e}")
                self.ui.append_result("*历史交锋数据处理出错*\n\n")
                
        # 主队近况
        home_history = data.get('home_team_history', [])
        if home_history:
            self._display_team_recent_stats(self.home_team, home_history, "主队")
            
        # 客队近况
        away_history = data.get('away_team_history', [])
        if away_history:
            self._display_team_recent_stats(self.away_team, away_history, "客队")
            
    def _display_team_recent_stats(self, team_name, history_data, team_type):
        """
        显示球队近期统计
        
        Args:
            team_name: 球队名称
            history_data: 历史数据
            team_type: 球队类型（主队/客队）
        """
        try:
            # 过滤掉杯赛和友谊赛
            valid_matches = []
            for match in history_data:
                if isinstance(match, list) and len(match) > 12:
                    league = str(match[2])
                    if not self._is_cup_or_friendly(league):
                        valid_matches.append(match)
                        
            # 使用10场比赛统计数据，与评分系统保持一致
            recent_matches = valid_matches[:10] if len(valid_matches) >= 10 else valid_matches
            
            if recent_matches:
                wins = sum(1 for match in recent_matches if match[12] > 0)
                draws = sum(1 for match in recent_matches if match[12] == 0)
                losses = sum(1 for match in recent_matches if match[12] < 0)
                
                # 计算进失球
                team_goals = 0
                opponent_goals = 0
                
                for match in recent_matches:
                    try:
                        # 判断球队是主场还是客场
                        if team_type == "主队":
                            is_home = self._clean_text(str(match[5])) == self.home_team
                        else:
                            is_home = self._clean_text(str(match[5])) == self.away_team
                            
                        if is_home:
                            team_goals += match[8] if isinstance(match[8], (int, float)) else 0
                            opponent_goals += match[9] if isinstance(match[9], (int, float)) else 0
                        else:
                            team_goals += match[9] if isinstance(match[9], (int, float)) else 0
                            opponent_goals += match[8] if isinstance(match[8], (int, float)) else 0
                    except (IndexError, TypeError) as e:
                        logging.error(f"计算{team_type}进球数据出错: {e}")
                        
                self.ui.append_result(f"### ")
                # 根据球队类型使用不同颜色
                color = COLOR_HOME if team_type == "主队" else COLOR_AWAY
                self.ui.append_colored_result(f"{team_name}", color)
                self.ui.append_result(" 近况\n")
                self.ui.append_result(f"- 近{len(recent_matches)}场: ")
                self.ui.append_colored_result(f"{wins}胜", COLOR_HOME)
                self.ui.append_result(f"{draws}平")
                self.ui.append_colored_result(f"{losses}负", COLOR_AWAY)
                self.ui.append_result("\n")
                self.ui.append_result(f"- 进球: {team_goals}球，失球: {opponent_goals}球\n\n")
            else:
                self.ui.append_result(f"### ")
                color = COLOR_HOME if team_type == "主队" else COLOR_AWAY
                self.ui.append_colored_result(f"{team_name}", color)
                self.ui.append_result(" 近况\n")
                self.ui.append_result("*没有有效的近期比赛数据*\n\n")
        except Exception as e:
            logging.error(f"{team_type}近况统计出错: {e}")
            self.ui.append_result(f"### ")
            color = COLOR_HOME if team_type == "主队" else COLOR_AWAY
            self.ui.append_colored_result(f"{team_name}", color)
            self.ui.append_result(" 近况\n")
            self.ui.append_result("*数据处理出错*\n\n")
            
    def _display_result_tendency(self, data, ratings=None):
        """
        显示胜平负倾向分析

        Args:
            data: 数据字典
            ratings: 评分结果，如果为None则使用默认评分
        """
        # 分析结论
        self.ui.append_result("## 数据分析结论\n\n")

        # 使用传入的评分或默认生成评分
        if not ratings:
            ratings = {
                'home_win_score': 0,
                'draw_score': 0,
                'away_win_score': 0,
                'confidence_level': '欠缺信心'
            }

        home_score = ratings['home_win_score']
        draw_score = ratings['draw_score']
        away_score = ratings['away_win_score']
        confidence = ratings['confidence_level']

        # 保存分析结果供其他模块使用
        self._save_analysis_results(ratings)
        
        # 将得分转换为星级显示（保留一位小数）
        home_stars = min(round(home_score), 10)
        draw_stars = min(round(draw_score), 10)
        away_stars = min(round(away_score), 10)
        
        # 输出胜平负倾向
        self.ui.append_result(f"**主胜（")
        self.ui.append_colored_result(f"{self.home_team}", COLOR_HOME)
        self.ui.append_result(f"）**：{home_score:.1f}分 ")
        self.ui.append_colored_result('★' * home_stars, COLOR_HOME)
        self.ui.append_result('☆' * (10-home_stars) + "\n")
        
        self.ui.append_result(f"**平局**：{draw_score:.1f}分 " + '★' * draw_stars + '☆' * (10-draw_stars) + "\n")
        
        self.ui.append_result(f"**客胜（")
        self.ui.append_colored_result(f"{self.away_team}", COLOR_AWAY)
        self.ui.append_result(f"）**：{away_score:.1f}分 ")
        self.ui.append_colored_result('★' * away_stars, COLOR_AWAY)
        self.ui.append_result('☆' * (10-away_stars) + "\n\n")
        
        # 确定各结果的信心级别
        def get_confidence_level(score):
            if score >= 9.0:
                return "极致信心"
            elif score >= 7.9:
                return "信心充足"
            elif score >= 6.8:
                return "信心中上"
            elif score >= 4.2:
                return "信心中庸"
            elif score >= 2.8:
                return "信心中下"
            elif score >= 1.4:
                return "信心不足"
            else:
                return "欠缺信心"
                
        home_confidence = get_confidence_level(home_score)
        draw_confidence = get_confidence_level(draw_score)
        away_confidence = get_confidence_level(away_score)
        
        # 获取各信心级别对应的赔率规则
        home_rules = self.get_confidence_odds_rules(home_confidence)
        draw_rules = self.get_confidence_odds_rules(draw_confidence)
        away_rules = self.get_confidence_odds_rules(away_confidence)
        
        # 展示各结果的信心等级及对应赔率规则
        self.ui.append_result(f"**主胜信心**：{home_confidence}\n")
        if home_rules:
            self.ui.append_result("合理赔率区间：\n")
            for rule in home_rules:
                self.ui.append_result(f"- {rule}\n")
        self.ui.append_result("\n")
        
        self.ui.append_result(f"**平局信心**：{draw_confidence}\n")
        if draw_rules:
            self.ui.append_result("合理赔率区间：\n")
            for rule in draw_rules:
                self.ui.append_result(f"- {rule}\n")
        self.ui.append_result("\n")
        
        self.ui.append_result(f"**客胜信心**：{away_confidence}\n")
        if away_rules:
            self.ui.append_result("合理赔率区间：\n")
            for rule in away_rules:
                self.ui.append_result(f"- {rule}\n")
        self.ui.append_result("\n")
        
        # 只显示最高分结果，不重复展示信心级别和赔率区间
        max_score = max(home_score, draw_score, away_score)
        max_result = "主胜" if max_score == home_score else ("平局" if max_score == draw_score else "客胜")
        
        self.ui.append_result(f"**基本面拉力评分**：{max_result}（最高分：{max_score:.1f}）\n\n")
        
        # 添加说明
        if home_score > away_score and home_score > draw_score:
            self.ui.append_result("根据历史交锋和近期战绩分析，")
            self.ui.append_colored_result(f"{self.home_team}", COLOR_HOME)
            self.ui.append_result("主场作战优势明显，获胜概率较高。\n")
        elif away_score > home_score and away_score > draw_score:
            self.ui.append_result("尽管")
            self.ui.append_colored_result(f"{self.home_team}", COLOR_HOME)
            self.ui.append_result("拥有主场优势，但")
            self.ui.append_colored_result(f"{self.away_team}", COLOR_AWAY)
            self.ui.append_result("近期状态更佳，客胜可能性较大。\n")
        else:
            self.ui.append_result("双方实力相当，比赛可能会以平局收场。\n")
            
    def get_confidence_odds_rules(self, confidence_level):
        """根据信心级别获取对应的赔率规则
        
        Args:
            confidence_level: 信心级别
            
        Returns:
            list: 赔率规则列表
        """
        rules_map = {
            "欠缺信心": ["1.实开盘高水", "2.实开盘中高水", "3.实开盘中水", "4.实开盘中低水", "5实开盘低水"],
            "信心不足": ["1.韬光盘低水", "2.韬光盘中低水", "3.实开盘低水", "4.实开盘中低水", "5.实开盘中水"],
            "信心中下": ["1.韬光盘低水", "2.韬光盘中低水", "3.实开盘超高水", "4.实开盘高水", 
                     "5.实开盘中高水", "6.实开盘中水", "7.实开盘中低水", "8.实开盘低水"],
            "信心中庸": ["1.实开盘中低水", "2.实开盘低水", "3.实开盘超高水", "4.实开盘高水", 
                     "5.超实盘高水", "6.韬光盘低水", "7.超实盘中高水", "8.韬光盘超低水", "9.韬光盘中高水"],
            "信心中上": ["1.超实盘高水", "2.超实盘中高水", "3.实开盘超低水", "4.实开盘低水", 
                     "5.实开盘中低水", "6.超实盘超高水", "7.超实盘中水", "8.超实盘中低水"],
            "信心充足": ["1.超实盘高水", "2.超实盘中高水", "3.超实盘中水", "4.超实盘中低水", 
                     "5.超实盘低水", "6.超实盘超低水"],
            "极致信心": ["1.超实盘低水", "2.超实盘中低水", "3.超实盘超低水", "4.超深盘中上水", 
                     "5.超散盘中高水", "6.超深盘中下水"]
        }
        return rules_map.get(confidence_level, [])

    def _save_analysis_results(self, ratings):
        """
        保存分析结果供其他模块使用

        Args:
            ratings: 评分结果字典
        """
        try:
            logging.info("开始保存基本面分析结果...")

            home_score = ratings.get('home_win_score', 0)
            draw_score = ratings.get('draw_score', 0)
            away_score = ratings.get('away_win_score', 0)

            logging.info(f"评分: 主胜{home_score}, 平局{draw_score}, 客胜{away_score}")

            # 确定各结果的信心级别
            def get_confidence_level(score):
                if score >= 9.0:
                    return "极致信心"
                elif score >= 7.9:
                    return "信心充足"
                elif score >= 6.8:
                    return "信心中上"
                elif score >= 4.2:
                    return "信心中庸"
                elif score >= 2.8:
                    return "信心中下"
                elif score >= 1.4:
                    return "信心不足"
                else:
                    return "欠缺信心"

            home_confidence = get_confidence_level(home_score)
            draw_confidence = get_confidence_level(draw_score)
            away_confidence = get_confidence_level(away_score)

            logging.info(f"信心级别: 主胜{home_confidence}, 平局{draw_confidence}, 客胜{away_confidence}")

            # 获取各信心级别对应的赔率规则
            logging.info("获取赔率规则...")
            home_rules = self.get_confidence_odds_rules(home_confidence)
            draw_rules = self.get_confidence_odds_rules(draw_confidence)
            away_rules = self.get_confidence_odds_rules(away_confidence)

            logging.info(f"规则数量: 主胜{len(home_rules)}, 平局{len(draw_rules)}, 客胜{len(away_rules)}")

            # 构建分析结果数据
            analysis_results = {
                'home_win': {
                    'score': home_score,
                    'confidence': home_confidence,
                    'odds_rules': home_rules
                },
                'draw': {
                    'score': draw_score,
                    'confidence': draw_confidence,
                    'odds_rules': draw_rules
                },
                'away_win': {
                    'score': away_score,
                    'confidence': away_confidence,
                    'odds_rules': away_rules
                },
                'teams': {
                    'home_team': getattr(self, 'home_team', '主队'),
                    'away_team': getattr(self, 'away_team', '客队'),
                    'league_name': getattr(self, 'league_name', '未知联赛')
                }
            }

            # 保存到类属性中
            self.latest_analysis_results = analysis_results

            logging.info(f"基本面分析结果已保存: 主胜{home_confidence}, 平局{draw_confidence}, 客胜{away_confidence}")

        except Exception as e:
            logging.error(f"保存分析结果时出错: {e}")
            import traceback
            logging.error(f"错误详情: {traceback.format_exc()}")
            self.latest_analysis_results = None

    def get_latest_analysis_results(self):
        """
        获取最新的分析结果

        Returns:
            dict: 分析结果字典，如果没有则返回None
        """
        results = getattr(self, 'latest_analysis_results', None)
        logging.info(f"获取分析结果: {results is not None}")
        if results:
            logging.info(f"结果包含队伍: {results.get('teams', {})}")
        return results

    def _display_basic_match_info(self):
        """显示基本比赛信息（当格式化失败时使用）"""
        self.ui.append_result("\n## 基本比赛信息\n")
        self.ui.append_result(f"- 联赛: {self.league_name}\n")
        self.ui.append_result(f"- 主队: ")
        self.ui.append_colored_result(f"{self.home_team}", COLOR_HOME)
        self.ui.append_result("\n")
        self.ui.append_result(f"- 客队: ")
        self.ui.append_colored_result(f"{self.away_team}", COLOR_AWAY)
        self.ui.append_result("\n")