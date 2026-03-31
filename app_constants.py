#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
应用常量配置模块
从app.py中提取的常量和配置项，提高代码可维护性
"""

# 线程池配置
EXECUTOR_MAX_WORKERS = 20  # 通用任务线程池大小
SCRAPER_EXECUTOR_MAX_WORKERS = 10  # 爬虫专用线程池大小

# 服务配置
AUTO_START_MONITORING = True  # 设置为True，则启动时自动开启监控
DEFAULT_PORT = 8889  # 默认服务端口

# 公司优先级排序 (按重要性排序)
# 优先显示的9个公司（按优先级顺序）：
# 432-香港马会, 80-澳门, 115-威廉希尔, 82-立博, 177-平博(Pinna), 104-Interwetten, 110-SNAI, 545-皇冠(Crown), 1129-竞彩
# 注意：bet365在数据库中未找到
PERSONAL_COMPANY_ORDER = [432, 80, 115, 82, 177, 104, 110, 545, 1129]

# 公司中文名称映射
COMPANY_NAME_MAPPING = {
    '791': 'Sisa*(意大利)',
    '16': '10*(英国)',
    '680': 'Stanley*(马尔他)', 
    '649': 'IBC*(哥斯达黎加)',
    '104': 'Interwet*(塞浦路斯)',
    'bet365': 'Bet365',
    'william': '威廉希尔',
    'ladbrokes': '立博',
    'coral': 'Coral',
    'bwin': 'Bwin',
    'unibet': 'Unibet'
}

# 特殊队名处理映射
SPECIAL_TEAM_NAMES = {
    '曼城': 'MC',
    '阿森纳': 'ARS',
    '皇家马德里': 'RM',
    '巴塞罗那': 'FCB',
    '拜仁慕尼黑': 'BAY',
    '多特蒙德': 'BVB',
    '利物浦': 'LFC',
    '切尔西': 'CHE',
    '曼联': 'MU',
    '热刺': 'TOT'
}

# 规则值颜色分类阈值
RULE_VALUE_THRESHOLDS = {
    'RED': 5.0,      # >= 5.0 红色
    'ORANGE': 4.0,   # >= 4.0 橙色  
    'YELLOW': 2.5,   # >= 2.5 黄色
    'GREEN': 1.0     # >= 1.0 绿色
}

# HTTP缓存控制头
CACHE_CONTROL_HEADERS = {
    'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
    'Pragma': 'no-cache',
    'Expires': '0'
}

# Flask会话配置
SESSION_CONFIG = {
    'SESSION_TYPE': 'filesystem'  # 使用文件系统存储session数据
}

# 数据库批量操作配置
BATCH_LIMITS = {
    'MATCHES_TO_MONITOR': 50,      # 最大监控比赛数量
    'FUNDAMENTAL_ANALYSIS': 50,    # 基本面分析批次大小
    'ODDS_UPDATE_LIMIT': 50        # 赔率更新批次大小
}