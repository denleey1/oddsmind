"""
大小球爬虫模块 - 专门用于爬取titan007.com的大小球赔率数据
"""
import requests
import time
import re
import logging
import os
import sys
import sqlite3
from datetime import datetime
from html.parser import HTMLParser
from typing import List, Optional, Dict, Tuple

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

try:
    from scrapers.config import logger
except ImportError:
    # 设置基本日志
    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

# 导入性能优化器
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from performance_optimizer import PerformanceMonitor, OptimizedRequestPool
except ImportError:
    PerformanceMonitor = None
    OptimizedRequestPool = None

try:
    from models.overunder_odds import OverUnderOdds
except ImportError:
    # 尝试从不同路径导入
    sys.path.append(os.path.join(project_root, 'models'))
    from overunder_odds import OverUnderOdds

class SimpleHTMLParser(HTMLParser):
    """简单的HTML解析器，用于解析大小球赔率表格"""
    
    def __init__(self):
        super().__init__()
        self.in_odds_table = False
        self.in_odds_row = False
        self.in_cell = False
        self.current_row = []
        self.current_cell_content = ""
        self.odds_rows = []
        self.current_row_attrs = {}
        self.current_row_html = ""
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag == 'table' and attrs_dict.get('id') == 'odds':
            self.in_odds_table = True
            
        elif self.in_odds_table and tag == 'tr' and 'bgcolor' in attrs_dict:
            self.in_odds_row = True
            self.current_row = []
            self.current_row_attrs = attrs_dict
            self.current_row_html = ""
            
        elif self.in_odds_row and tag == 'td':
            self.in_cell = True
            self.current_cell_content = ""
        
        # 记录原始HTML用于解析公司ID
        if self.in_odds_row:
            self.current_row_html += f"<{tag}"
            for name, value in attrs:
                self.current_row_html += f' {name}="{value}"'
            self.current_row_html += ">"
    
    def handle_endtag(self, tag):
        if self.in_odds_row:
            self.current_row_html += f"</{tag}>"
            
        if tag == 'table' and self.in_odds_table:
            self.in_odds_table = False
            
        elif tag == 'tr' and self.in_odds_row:
            if self.current_row and len(self.current_row) >= 10:  # 确保有足够的列
                row_info = {
                    'cells': self.current_row.copy(),
                    'attrs': self.current_row_attrs.copy(),
                    'html': self.current_row_html
                }
                self.odds_rows.append(row_info)
            self.in_odds_row = False
            self.current_row = []
            self.current_row_attrs = {}
            self.current_row_html = ""
            
        elif tag == 'td' and self.in_cell:
            self.current_row.append(self.current_cell_content.strip())
            self.in_cell = False
            self.current_cell_content = ""
    
    def handle_data(self, data):
        if self.in_cell:
            self.current_cell_content += data
        if self.in_odds_row:
            self.current_row_html += data
    
    def get_odds_rows(self):
        return self.odds_rows

class OverUnderScraper:
    """大小球爬虫类，负责从titan007.com爬取大小球赔率数据"""
    
    def __init__(self, headers=None):
        """
        初始化爬虫
        
        Args:
            headers: 请求头信息
        """
        self.session = requests.Session()
        
        # 设置默认请求头
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        if headers:
            default_headers.update(headers)
        
        self.session.headers.update(default_headers)
        
        # Apply tunnel proxy (if configured via env vars)
        try:
            from scrapers.proxy_config import apply_proxy_to_session
            apply_proxy_to_session(self.session)
        except ImportError:
            pass
        
        # 统计信息
        self._stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_odds_parsed': 0,
            'errors': 0
        }
        
        # 添加性能监控
        self._performance_monitor = PerformanceMonitor() if PerformanceMonitor else None
    
    def _parse_company_id(self, html_snippet: str) -> Optional[str]:
        """
        从HTML片段中解析公司ID
        
        Args:
            html_snippet: HTML片段
            
        Returns:
            str: 公司ID，如果未找到返回None
        """
        # 查找companyID='数字'模式
        company_id_match = re.search(r"companyID=['\"](\d+)['\"]", html_snippet)
        if company_id_match:
            return company_id_match.group(1)
        return None
    
    def _parse_company_id_from_row(self, html_content: str, company_name: str) -> Optional[str]:
        """
        从HTML内容中根据公司名称解析公司ID
        
        Args:
            html_content: 完整HTML内容
            company_name: 公司名称
            
        Returns:
            str: 公司ID，如果未找到返回None
        """
        # 查找包含公司名称的行中的companyID
        pattern = rf'<tr[^>]*>.*?{re.escape(company_name)}.*?companyID=[\'"](\d+)[\'"].*?</tr>'
        match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
        
        # 如果没找到，尝试更简单的匹配
        pattern = rf'companyID=[\'"](\d+)[\'"].*?{re.escape(company_name)}'
        match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
            
        return None
    
    def _parse_odds_value(self, text: str) -> Optional[float]:
        """
        解析赔率值，处理各种格式
        
        Args:
            text: 赔率文本
            
        Returns:
            float: 赔率值，如果解析失败返回None
        """
        if not text:
            return None
            
        text = str(text).strip()
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        try:
            return float(text)
        except (ValueError, TypeError):
            return None
    
    def _parse_line_value(self, text: str) -> Tuple[Optional[str], Optional[float]]:
        """
        解析盘口值，返回字符串和数值两种格式
        
        Args:
            text: 盘口文本
            
        Returns:
            tuple: (盘口字符串, 盘口数值)
        """
        if not text:
            return None, None
            
        text = str(text).strip()
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 转换为数值
        numeric_value = OverUnderOdds.convert_line_to_numeric(text)
        
        return text, numeric_value
    
    def parse_overunder_odds(self, html_content: str) -> List[OverUnderOdds]:
        """
        解析大小球赔率HTML内容
        
        Args:
            html_content: HTML页面内容
            
        Returns:
            List[OverUnderOdds]: 大小球赔率列表
        """
        odds_list = []
        last_company_name = ""  # 用于记录上一个主盘口的公司名称
        last_company_id = None  # 用于记录上一个主盘口的公司ID
        
        try:
            # 使用自定义HTML解析器
            parser = SimpleHTMLParser()
            parser.feed(html_content)
            odds_rows = parser.get_odds_rows()
            
            if not odds_rows:
                logger.warning("未找到大小球赔率表格数据")
                return odds_list
            
            for row_info in odds_rows:
                try:
                    cells = row_info['cells']
                    row_attrs = row_info['attrs']
                    row_html = row_info.get('html', '')
                    
                    # 跳过隐藏行
                    if 'style' in row_attrs and 'display: none' in row_attrs.get('style', ''):
                        continue
                    
                    # 检查基本结构 - 根据实际数据调整
                    if len(cells) < 10:
                        continue
                    
                    # 获取公司名称（索引1，不是0）
                    company_name = cells[1].strip()
                    
                    # 处理多盘口逻辑
                    if company_name:
                        # 主盘口：有公司名称，去掉末尾的*号
                        company_name = re.sub(r'[*\s]+$', '', company_name)
                        last_company_name = company_name  # 记录主盘口公司名
                        
                        # 获取公司ID - 从行HTML中解析
                        company_id = self._parse_company_id(row_html)
                        last_company_id = company_id
                        
                        current_company_name = company_name
                        current_company_id = company_id
                    else:
                        # 子盘口：空白公司名称，继承上一个主盘口的信息
                        if not last_company_name:
                            logger.warning("发现子盘口但没有上级主盘口，跳过")
                            continue
                        
                        current_company_name = last_company_name
                        current_company_id = last_company_id
                    
                    # 根据实际HTML结构调整索引：
                    # TD3: 初始大球赔率, TD4: 初始盘口, TD5: 初始小球赔率
                    # TD6: 即时大球赔率, TD7: 即时盘口, TD8: 即时小球赔率
                    initial_over = self._parse_odds_value(cells[3])
                    initial_line_str, initial_line_numeric = self._parse_line_value(cells[4])
                    initial_under = self._parse_odds_value(cells[5])
                    
                    # 解析即时赔率
                    instant_over = self._parse_odds_value(cells[6])
                    instant_line_str, instant_line_numeric = self._parse_line_value(cells[7])
                    instant_under = self._parse_odds_value(cells[8])
                    
                    # 创建大小球赔率对象
                    odds = OverUnderOdds(
                        bookmaker=current_company_name,
                        initial_over=initial_over,
                        initial_line=initial_line_str,
                        initial_under=initial_under,
                        instant_over=instant_over,
                        instant_line=instant_line_str,
                        instant_under=instant_under,
                        line_numeric=instant_line_numeric or initial_line_numeric,
                        company_id=current_company_id,
                        update_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    )
                    
                    odds_list.append(odds)
                    
                    self._stats['total_odds_parsed'] += 1
                    
                    # 记录详细日志
                    盘口类型 = "主盘口" if company_name else "子盘口"
                    logger.debug(f"解析大小球赔率({盘口类型}): {current_company_name} - {instant_line_str} - 上:{instant_over} 下:{instant_under}")
                    
                except Exception as e:
                    logger.error(f"解析单行大小球赔率失败: {e}")
                    self._stats['errors'] += 1
                    continue
            
            logger.info(f"成功解析 {len(odds_list)} 个大小球赔率")
            
        except Exception as e:
            logger.error(f"解析大小球赔率失败: {e}")
            self._stats['errors'] += 1
        
        return odds_list
    
    def fetch_overunder_odds(self, match_id: str, max_retries: int = 2) -> Optional[List[OverUnderOdds]]:
        """
        获取指定比赛的大小球赔率
        
        Args:
            match_id: 比赛ID
            max_retries: 最大重试次数
            
        Returns:
            List[OverUnderOdds]: 大小球赔率列表，失败返回None
        """
        url = f"https://vip.titan007.com/OverDown_n.aspx?id={match_id}&l=1"
        
        for attempt in range(max_retries):
            try:
                self._stats['total_requests'] += 1
                
                logger.info(f"获取大小球赔率 (第 {attempt + 1}/{max_retries} 次): {url}")
                
                # 记录性能
                start_time = time.time()
                response = self.session.get(url, timeout=15)  # 减少超时时间
                
                if self._performance_monitor:
                    self._performance_monitor.record('fetch_overunder', time.time() - start_time, response.status_code == 200)
                
                if response.status_code == 200:
                    content = response.text
                    
                    if content and len(content) > 1000:  # 基本内容验证
                        self._stats['successful_requests'] += 1
                        
                        # 解析大小球赔率
                        odds_list = self.parse_overunder_odds(content)
                        
                        if odds_list:
                            logger.info(f"成功获取 {len(odds_list)} 个大小球赔率")
                            return odds_list
                        else:
                            logger.warning("未能解析到大小球赔率数据")
                    else:
                        logger.warning(f"响应内容过短: {len(content) if content else 0}")
                else:
                    logger.warning(f"HTTP响应状态码: {response.status_code}")
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"第 {attempt + 1} 次请求超时: {e}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"第 {attempt + 1} 次连接错误: {e}")
            except Exception as e:
                logger.error(f"第 {attempt + 1} 次获取大小球赔率失败: {e}")
            
            # 重试前等待 - 减少等待时间
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 0.3  # 减少基础等待时间
                logger.info(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
        
        # 所有尝试都失败
        self._stats['failed_requests'] += 1
        
        logger.error(f"在 {max_retries} 次尝试后仍无法获取大小球赔率: {url}")
        return None
    
    def get_stats(self) -> Dict:
        """获取爬虫统计信息"""
        stats = dict(self._stats)
        
        # 计算成功率
        if stats['total_requests'] > 0:
            stats['success_rate'] = stats['successful_requests'] / stats['total_requests']
        else:
            stats['success_rate'] = 0
        
        return stats
    
    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_odds_parsed': 0,
            'errors': 0
        }
    
    def close(self):
        """关闭爬虫，清理资源"""
        if hasattr(self, 'session') and self.session:
            self.session.close()
        logger.info("大小球爬虫已关闭")

    def clear_database(self):
        """
        清空大小球赔率数据库
        
        Returns:
            bool: 是否清空成功
        """
        try:
            # 获取数据库路径
            try:
                from football_analysis_system.config import DB_MATCHES
            except ImportError:
                from config import DB_MATCHES
            
            # 连接数据库
            conn = sqlite3.connect(DB_MATCHES)
            cursor = conn.cursor()
            
            # 清空大小球赔率表
            cursor.execute("DELETE FROM overunder_odds")
            
            # 获取删除的行数
            deleted_rows = cursor.rowcount
            
            # 提交更改
            conn.commit()
            conn.close()
            
            logger.info(f"✅ 成功清空大小球赔率数据库，删除了 {deleted_rows} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"❌ 清空大小球赔率数据库失败: {e}")
            if 'conn' in locals():
                conn.close()
            return False
    
    def clear_database_for_match(self, match_id: str):
        """
        清空指定比赛的大小球赔率数据
        
        Args:
            match_id: 比赛ID
            
        Returns:
            bool: 是否清空成功
        """
        try:
            # 获取数据库路径
            try:
                from football_analysis_system.config import DB_MATCHES
            except ImportError:
                from config import DB_MATCHES
            
            # 连接数据库
            conn = sqlite3.connect(DB_MATCHES)
            cursor = conn.cursor()
            
            # 清空指定比赛的大小球赔率
            cursor.execute("DELETE FROM overunder_odds WHERE match_id = ?", (match_id,))
            
            # 获取删除的行数
            deleted_rows = cursor.rowcount
            
            # 提交更改
            conn.commit()
            conn.close()
            
            logger.info(f"✅ 成功清空比赛 {match_id} 的大小球赔率数据，删除了 {deleted_rows} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"❌ 清空比赛 {match_id} 的大小球赔率数据失败: {e}")
            if 'conn' in locals():
                conn.close()
            return False 