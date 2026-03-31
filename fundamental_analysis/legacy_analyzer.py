import logging
import traceback
import re

class MatchAnalyzer:
    """比赛数据分析类"""
    
    def __init__(self, home_team="", away_team="", league_name=""):
        """
        初始化分析器
        
        Args:
            home_team: 主队名
            away_team: 客队名
            league_name: 联赛名称，默认为空字符串
        """
        self.home_team = home_team
        self.away_team = away_team
        self.league_name = league_name
        
    def set_teams(self, home_team, away_team, league_name=None):
        """
        设置比赛队伍
        
        Args:
            home_team: 主队名
            away_team: 客队名
            league_name: 联赛名称（可选）
        """
        self.home_team = home_team
        self.away_team = away_team
        if league_name:
            self.league_name = league_name
        
    def calculate_ratings(self, data):
        """
        计算比赛胜平负评分
        
        Args:
            data: 比赛数据
            
        Returns:
            dict: 评分结果
        """
        try:
            logging.info("使用新的评分规则计算：胜3分、平1分、负0分，近10场比赛，历史交锋6场")
            return self._calculate_new_rating_system(data)
        except Exception as e:
            logging.error(f"计算评分出错: {e}")
            logging.error(traceback.format_exc())
            # 返回默认评分
            return {
                'home_win_score': 0,
                'draw_score': 0,
                'away_win_score': 0,
                'confidence_level': '欠缺信心'
            }
            
    def _extract_team_name(self, html_text):
        """
        从带有HTML标签的文本中提取纯文本队名
        
        Args:
            html_text: 带HTML标签的文本，如 '<span title="斯蒂文尼奇  排名:14">斯蒂文尼奇</span>'
            
        Returns:
            str: 提取的纯文本队名，如 '斯蒂文尼奇'
        """
        # 如果输入不是字符串，直接返回原值
        if not isinstance(html_text, str):
            return html_text
            
        # 尝试提取 <span> 标签内的文本
        tag_content = re.search(r'>([^<]+)<', html_text)
        if tag_content:
            return tag_content.group(1).strip()
            
        # 如果没有找到标签，返回原文本
        return html_text
        
    def _calculate_team_recent_form(self, history_data, match_count, is_home=None):
        """
        计算球队近期表现得分
        
        Args:
            history_data: 历史数据列表
            match_count: 要考虑的比赛场数
            is_home: 是否筛选主场/客场 (True=主场, False=客场, None=不筛选)
            
        Returns:
            dict: 包含胜平负场次和得分的字典
        """
        wins = 0
        draws = 0
        losses = 0
        
        try:
            # 日志记录筛选开始
            if is_home is not None:
                logging.info(f"开始筛选{'主场' if is_home else '客场'}比赛，总计{len(history_data)}条记录")
            
            # 记录当前分析的联赛名称
            logging.info(f"当前分析的联赛: {self.league_name}")
            
            # 第一步：过滤掉杯赛和友谊赛，仅保留指定联赛比赛（所有比赛，不区分主客场）
            valid_league_matches = []
            filtered_matches = []
            for idx, match in enumerate(history_data):
                if isinstance(match, list) and len(match) > 12:
                    league = str(match[2])
                    
                    # 记录前三条数据格式供调试
                    if idx < 3 and is_home is not None:
                        logging.info(f"比赛数据调试 #{idx}: {match}")
                    
                    # 严格筛选：只保留指定联赛
                    if self.league_name and league != self.league_name:
                        logging.info(f"{'主队' if is_home else '客队'}历史中过滤掉非{self.league_name}比赛: {league}")
                        filtered_matches.append(match)
                        continue
                        
                    # 额外检查确保不包含任何杯赛
                    if "锦" in league or self._is_cup_or_friendly(league):
                        logging.info(f"{'主队' if is_home else '客队'}历史中过滤掉杯赛: {league}")
                        filtered_matches.append(match)
                        continue
                    
                    # 记录处理的联赛比赛
                    if idx < 10:
                        logging.info(f"保留{self.league_name}联赛比赛 #{idx}: {league}")
                    
                    # 添加有效的联赛比赛（不区分主客场）
                    valid_league_matches.append(match)
            
            # 第二步：取最近N场联赛比赛
            recent_league_matches = valid_league_matches[:match_count] if len(valid_league_matches) >= match_count else valid_league_matches
            logging.info(f"从{len(valid_league_matches)}场联赛比赛中选取最近{len(recent_league_matches)}场")
            
            # 第三步：从最近N场联赛比赛中筛选主场/客场比赛
            valid_matches = []
            if is_home is None:
                # 不区分主客场，直接使用所有联赛比赛
                valid_matches = recent_league_matches
            else:
                # 从最近N场联赛比赛中筛选主场或客场比赛
                for match in recent_league_matches:
                    if is_home:  # 筛选主场比赛
                        if len(match) > 5:
                            team_name = self._extract_team_name(match[5])
                            if team_name == self.home_team:
                                valid_matches.append(match)
                                logging.info(f"从最近{len(recent_league_matches)}场联赛比赛中筛选出主场比赛: {team_name}")
                    else:  # 筛选客场比赛
                        if len(match) > 7:
                            team_name = self._extract_team_name(match[7])
                            if team_name == self.away_team:
                                valid_matches.append(match)
                                date = match[0] if len(match) > 0 else "未知"
                                home_team = self._extract_team_name(match[5]) if len(match) > 5 else "未知"
                                away_team = self._extract_team_name(match[7]) if len(match) > 7 else "未知"
                                score = f"{match[8]}-{match[9]}" if len(match) > 9 else "未知"
                                logging.info(f"从最近{len(recent_league_matches)}场联赛比赛中筛选出客场比赛: {date} {self.league_name} {home_team} vs {away_team} {score}")
            
            # 记录最终使用的比赛数据
            if is_home is not None:
                logging.info(f"从最近{len(recent_league_matches)}场联赛比赛中筛选出{'主场' if is_home else '客场'}比赛: {len(valid_matches)}条")
                
                # 记录最终使用的比赛详情
                if not is_home:  # 仅对客场比赛进行详细记录
                    logging.info(f"最终使用的客场比赛列表:")
                    for i, match in enumerate(valid_matches):
                        date = match[0] if len(match) > 0 else "未知"
                        home_team = self._extract_team_name(match[5]) if len(match) > 5 else "未知"
                        away_team = self._extract_team_name(match[7]) if len(match) > 7 else "未知"
                        score = f"{match[8]}-{match[9]}" if len(match) > 9 else "未知"
                        result = "胜" if match[12] > 0 else ("平" if match[12] == 0 else "负")
                        logging.info(f"客场比赛 #{i+1}: {date} {self.league_name} {home_team} vs {away_team} {score} ({result})")
            
            # 计算胜平负场次
            for match in valid_matches:
                if match[12] > 0:  # 胜
                    wins += 1
                elif match[12] == 0:  # 平
                    draws += 1
                else:  # 负
                    losses += 1
            
            # 按照新规则计算总分：胜3分、平1分、负0分
            score = wins * 3 + draws * 1 + losses * 0
                    
        except Exception as e:
            logging.error(f"计算球队近期表现得分出错: {e}")
            logging.error(traceback.format_exc())
            score = 0
        
        return {
            'wins': wins,
            'draws': draws, 
            'losses': losses,
            'total_matches': wins + draws + losses,
            'score': score
        }
        
    def _calculate_new_rating_system(self, data):
        """
        实现新的基本面拉力评分系统
        
        Args:
            data: 数据字典
            
        Returns:
            dict: 评分结果
        """
        results = {
            'home_win_score': 0,
            'draw_score': 0,
            'away_win_score': 0,
            'confidence_level': ''
        }
        
        try:
            logging.info("开始计算评分，使用新规则：主近10场，客近10场，交锋近6场，胜3平1负0")
            
            # 1. 计算联赛近况最多10场比赛（不分主客场）
            home_recent_data = self._calculate_team_recent_form(data.get('home_team_history', []), 10)
            away_recent_data = self._calculate_team_recent_form(data.get('away_team_history', []), 10)
            
            # 获取主队在近10场比赛中的主场比赛数据
            home_home_data = self._calculate_team_recent_form(data.get('home_team_history', []), 10, True)
            
            # 获取客队在近10场比赛中的客场比赛数据
            away_away_data = self._calculate_team_recent_form(data.get('away_team_history', []), 10, False)
            
            # 输出原始数据，便于调试
            logging.info(f"主队总数据：{home_recent_data}")
            logging.info(f"客队总数据：{away_recent_data}")
            logging.info(f"主队主场数据：{home_home_data}")
            logging.info(f"客队客场数据：{away_away_data}")
            
            # 如果主队主场数据为空，使用总数据代替
            if home_home_data['total_matches'] == 0:
                logging.info("主队主场数据为空，使用总数据替代")
                home_home_data = home_recent_data
            
            # 如果客队客场数据为空，使用总数据代替
            if away_away_data['total_matches'] == 0:
                logging.info("客队客场数据为空，使用总数据替代")
                away_away_data = away_recent_data
            
            # 计算主队近况最高分、最低分和评分等距
            home_recent_max_score = home_recent_data['total_matches'] * 3
            home_recent_min_score = 0  # 最低分始终为0
            home_recent_score_interval = (home_recent_max_score - home_recent_min_score) / 10
            home_recent_score_interval = max(home_recent_score_interval, 0.1)  # 防止除以零
            
            # 计算客队近况最高分、最低分和评分等距
            away_recent_max_score = away_recent_data['total_matches'] * 3
            away_recent_min_score = 0  # 最低分始终为0
            away_recent_score_interval = (away_recent_max_score - away_recent_min_score) / 10
            away_recent_score_interval = max(away_recent_score_interval, 0.1)  # 防止除以零
            
            # 计算主队主场近况最高分、最低分和评分等距
            home_home_max_score = home_home_data['total_matches'] * 3
            home_home_min_score = 0  # 最低分始终为0
            home_home_score_interval = (home_home_max_score - home_home_min_score) / 10
            home_home_score_interval = max(home_home_score_interval, 0.1)  # 防止除以零
            
            # 计算客队客场近况最高分、最低分和评分等距
            away_away_max_score = away_away_data['total_matches'] * 3
            away_away_min_score = 0  # 最低分始终为0
            away_away_score_interval = (away_away_max_score - away_away_min_score) / 10
            away_away_score_interval = max(away_away_score_interval, 0.1)  # 防止除以零
            
            # 根据主客双方实际场次打分
            home_recent_rating = (home_recent_data['score'] - home_recent_min_score) / home_recent_score_interval
            away_recent_rating = (away_recent_data['score'] - away_recent_min_score) / away_recent_score_interval
            home_home_rating = (home_home_data['score'] - home_home_min_score) / home_home_score_interval
            away_away_rating = (away_away_data['score'] - away_away_min_score) / away_away_score_interval
            
            # 3. 计算历史交锋近况最多6场 - 包含杯赛，但不包含友谊赛
            history_data = data.get('history', [])
            if not history_data and 'head_to_head' in data:
                logging.info("使用head_to_head作为历史交锋数据")
                history_data = data.get('head_to_head', [])
            
            # 记录历史交锋数据
            if len(history_data) > 0:
                logging.info(f"历史交锋数据第一条: {history_data[0]}")
            else:
                logging.info("没有历史交锋数据")
            
            # 过滤有效的交锋记录（包括杯赛，但不包括友谊赛）
            valid_h2h = []
            for match in history_data:
                if isinstance(match, list) and len(match) > 12:
                    league = str(match[2])
                    if not self._is_friendly_match(league):  # 只过滤友谊赛
                        valid_h2h.append(match)
                        
            # 取最近6场
            recent_h2h = valid_h2h[:6] if len(valid_h2h) >= 6 else valid_h2h
            
            # 计算交战记录得分 - 记录胜平负场次
            home_h2h_wins = 0
            h2h_draws = 0
            away_h2h_wins = 0
            
            for match in recent_h2h:
                if match[12] > 0:  # 主队胜
                    home_h2h_wins += 1
                elif match[12] == 0:  # 平
                    h2h_draws += 1
                else:  # 客队胜
                    away_h2h_wins += 1
            
            # 计算历史交锋双方得分
            h2h_total_matches = len(recent_h2h)
            home_h2h_score = home_h2h_wins * 3 + h2h_draws * 1
            away_h2h_score = away_h2h_wins * 3 + h2h_draws * 1
            
            # 计算历史交锋最高分、最低分和评分等距
            h2h_max_score = h2h_total_matches * 3
            h2h_min_score = 0  # 最低分始终为0
            h2h_score_interval = (h2h_max_score - h2h_min_score) / 10
            h2h_score_interval = max(h2h_score_interval, 0.1)  # 防止除以零
            
            # 计算历史交锋评分
            home_h2h_rating = (home_h2h_score - h2h_min_score) / h2h_score_interval if h2h_total_matches > 0 else 0
            away_h2h_rating = (away_h2h_score - h2h_min_score) / h2h_score_interval if h2h_total_matches > 0 else 0
            
            # 计算平局评分 - 10减去主客双方评分差值绝对值
            recent_diff = abs(home_recent_rating - away_recent_rating)
            recent_draw_rating = 10 - recent_diff
            
            home_away_diff = abs(home_home_rating - away_away_rating)
            home_away_draw_rating = 10 - home_away_diff
            
            h2h_diff = abs(home_h2h_rating - away_h2h_rating)
            h2h_draw_rating = 10 - h2h_diff
            
            # 限制评分在0-10之间
            home_recent_rating = max(0, min(10, home_recent_rating))
            away_recent_rating = max(0, min(10, away_recent_rating))
            home_home_rating = max(0, min(10, home_home_rating))
            away_away_rating = max(0, min(10, away_away_rating))
            home_h2h_rating = max(0, min(10, home_h2h_rating))
            away_h2h_rating = max(0, min(10, away_h2h_rating))
            recent_draw_rating = max(0, min(10, recent_draw_rating))
            home_away_draw_rating = max(0, min(10, home_away_draw_rating))
            h2h_draw_rating = max(0, min(10, h2h_draw_rating))
            
            # 记录各项场次和得分情况（调试用）
            logging.info(f"主队近{home_recent_data['total_matches']}场：{home_recent_data['wins']}胜{home_recent_data['draws']}平{home_recent_data['losses']}负，得分：{home_recent_data['score']}，评分：{home_recent_rating:.2f}")
            logging.info(f"客队近{away_recent_data['total_matches']}场：{away_recent_data['wins']}胜{away_recent_data['draws']}平{away_recent_data['losses']}负，得分：{away_recent_data['score']}，评分：{away_recent_rating:.2f}")
            logging.info(f"主队主场近况{home_home_data['total_matches']}场：{home_home_data['wins']}胜{home_home_data['draws']}平{home_home_data['losses']}负，得分：{home_home_data['score']}，评分：{home_home_rating:.2f}")
            logging.info(f"客队客场近况{away_away_data['total_matches']}场：{away_away_data['wins']}胜{away_away_data['draws']}平{away_away_data['losses']}负，得分：{away_away_data['score']}，评分：{away_away_rating:.2f}")
            logging.info(f"历史交锋{h2h_total_matches}场：主胜{home_h2h_wins}场，平{h2h_draws}场，客胜{away_h2h_wins}场，主队得分：{home_h2h_score}，客队得分：{away_h2h_score}")
            logging.info(f"历史交锋评分：主队{home_h2h_rating:.2f}，客队{away_h2h_rating:.2f}")
            logging.info(f"平局评分 - 近况：{recent_draw_rating:.2f}，主客场：{home_away_draw_rating:.2f}，历史交锋：{h2h_draw_rating:.2f}")
            
            # 应用权重系数计算最终得分
            # 当没有历史交锋记录时，将权重重新分配
            if h2h_total_matches == 0:
                logging.info("没有历史交锋记录，将历史交锋的0.3权重按比例分配：近期表现+0.15，主客场表现+0.15")
                home_win_calc = 0.45 * home_recent_rating + 0.55 * home_home_rating
                away_win_calc = 0.45 * away_recent_rating + 0.55 * away_away_rating
                draw_calc = 0.45 * recent_draw_rating + 0.55 * home_away_draw_rating
                
                # 输出详细计算过程
                logging.info(f"主胜计算(无历史交锋): 0.45 * {home_recent_rating:.2f} + 0.55 * {home_home_rating:.2f} = {home_win_calc:.2f}")
                logging.info(f"平局计算(无历史交锋): 0.45 * {recent_draw_rating:.2f} + 0.55 * {home_away_draw_rating:.2f} = {draw_calc:.2f}")
                logging.info(f"客胜计算(无历史交锋): 0.45 * {away_recent_rating:.2f} + 0.55 * {away_away_rating:.2f} = {away_win_calc:.2f}")
            else:
                home_win_calc = 0.3 * home_recent_rating + 0.4 * home_home_rating + 0.3 * home_h2h_rating
                away_win_calc = 0.3 * away_recent_rating + 0.4 * away_away_rating + 0.3 * away_h2h_rating
                draw_calc = 0.3 * recent_draw_rating + 0.4 * home_away_draw_rating + 0.3 * h2h_draw_rating
                
                # 输出详细计算过程
                logging.info(f"主胜计算: 0.3 * {home_recent_rating:.2f} + 0.4 * {home_home_rating:.2f} + 0.3 * {home_h2h_rating:.2f} = {home_win_calc:.2f}")
                logging.info(f"平局计算: 0.3 * {recent_draw_rating:.2f} + 0.4 * {home_away_draw_rating:.2f} + 0.3 * {h2h_draw_rating:.2f} = {draw_calc:.2f}")
                logging.info(f"客胜计算: 0.3 * {away_recent_rating:.2f} + 0.4 * {away_away_rating:.2f} + 0.3 * {away_h2h_rating:.2f} = {away_win_calc:.2f}")
            
            # 对平局评分额外乘以0.8的系数，降低平局的权重
            draw_calc = draw_calc * 0.8
            
            # 保留一位小数
            results['home_win_score'] = round(home_win_calc, 1)
            results['away_win_score'] = round(away_win_calc, 1)
            results['draw_score'] = round(draw_calc, 1)
            
            # 确定信心级别
            max_score = max(results['home_win_score'], results['draw_score'], results['away_win_score'])
            
            if max_score >= 9.0:
                results['confidence_level'] = "极致信心"
            elif max_score >= 7.9:
                results['confidence_level'] = "信心充足"
            elif max_score >= 6.8:
                results['confidence_level'] = "信心中上"
            elif max_score >= 4.2:
                results['confidence_level'] = "信心中庸"
            elif max_score >= 2.8:
                results['confidence_level'] = "信心中下"
            elif max_score >= 1.4:
                results['confidence_level'] = "信心不足"
            else:
                results['confidence_level'] = "欠缺信心"
                
            # 记录评分结果
            logging.info(f"基本面拉力评分 - 主胜: {results['home_win_score']:.1f}, 平局: {results['draw_score']:.1f}, 客胜: {results['away_win_score']:.1f}")
            logging.info(f"最高评分: {max_score:.1f}, 信心级别: {results['confidence_level']}")
            
        except Exception as e:
            logging.error(f"计算新评分系统时出错: {e}")
            logging.error(traceback.format_exc())
            
        return results
        
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
                       "挑战杯", "淘汰赛", "英锦赛", "锦赛", "championship", "cup", "trophy"]
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
