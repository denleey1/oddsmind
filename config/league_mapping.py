#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
League ID mapping extracted from filenames.
Maps league_id from titan007 to league names and filenames.
"""

import re
from typing import Dict, Optional

def extract_league_id_from_filename(filename: str) -> Optional[int]:
    """
    Extract league ID from filename like 's36.js' or 's34_2948.js'
    Returns the first number after 's'
    """
    match = re.match(r's(\d+)', filename)
    if match:
        return int(match.group(1))
    return None

# Mapping from league_id to league information
# Extracted from urls.txt
LEAGUE_ID_MAPPING = {
    # 英格兰
    36: {"name_cn": "英超", "name_en": "Premier League", "filename": "s36.js", "season": "2025-2026"},
    37: {"name_cn": "英冠", "name_en": "Championship", "filename": "s37_87.js", "season": "2025-2026"},
    39: {"name_cn": "英甲", "name_en": "League One", "filename": "s39_135.js", "season": "2025-2026"},
    
    # 西班牙
    31: {"name_cn": "西甲", "name_en": "La Liga", "filename": "s31.js", "season": "2025-2026"},
    33: {"name_cn": "西乙", "name_en": "Segunda Division", "filename": "s33_546.js", "season": "2025-2026"},
    
    # 意大利
    34: {"name_cn": "意甲", "name_en": "Serie A", "filename": "s34_2948.js", "season": "2025-2026"},
    40: {"name_cn": "意乙", "name_en": "Serie B", "filename": "s40_261.js", "season": "2025-2026"},
    
    # 德国
    8: {"name_cn": "德甲", "name_en": "Bundesliga", "filename": "s8.js", "season": "2025-2026"},
    9: {"name_cn": "德乙", "name_en": "2. Bundesliga", "filename": "s9_132.js", "season": "2025-2026"},
    
    # 法国
    11: {"name_cn": "法甲", "name_en": "Ligue 1", "filename": "s11.js", "season": "2025-2026"},
    12: {"name_cn": "法乙", "name_en": "Ligue 2", "filename": "s12_1778.js", "season": "2025-2026"},
    
    # 葡萄牙
    23: {"name_cn": "葡超", "name_en": "Primeira Liga", "filename": "s23_1123.js", "season": "2025-2026"},
    157: {"name_cn": "葡甲", "name_en": "Segunda Liga", "filename": "s157_1787.js", "season": "2025-2026"},
    
    # 苏格兰
    29: {"name_cn": "苏超", "name_en": "Scottish Premiership", "filename": "s29_2498.js", "season": "2025-2026"},
    150: {"name_cn": "苏冠", "name_en": "Scottish Championship", "filename": "s150_1115.js", "season": "2025-2026"},
    
    # 荷兰
    16: {"name_cn": "荷甲", "name_en": "Eredivisie", "filename": "s16_98.js", "season": "2025-2026"},
    17: {"name_cn": "荷乙", "name_en": "Eerste Divisie", "filename": "s17_94.js", "season": "2025-2026"},
    
    # 比利时
    5: {"name_cn": "比甲", "name_en": "Belgian Pro League", "filename": "s5_114.js", "season": "2025-2026"},
    138: {"name_cn": "比乙", "name_en": "First Division B", "filename": "s138_129.js", "season": "2025-2026"},
    
    # 瑞典
    26: {"name_cn": "瑞典超", "name_en": "Allsvenskan", "filename": "s26_431.js", "season": "2025"},
    122: {"name_cn": "瑞典甲", "name_en": "Superettan", "filename": "s122_415.js", "season": "2025"},
    
    # 芬兰
    13: {"name_cn": "芬超", "name_en": "Veikkausliiga", "filename": "s13_2082.js", "season": "2025"},
    212: {"name_cn": "芬甲", "name_en": "Ykkonen", "filename": "s212_413.js", "season": "2025"},
    
    # 挪威
    22: {"name_cn": "挪超", "name_en": "Eliteserien", "filename": "s22_3219.js", "season": "2025"},
    123: {"name_cn": "挪甲", "name_en": "OBOS-ligaen", "filename": "s123_437.js", "season": "2025"},
    
    # 丹麦
    7: {"name_cn": "丹麦超", "name_en": "Superliga", "filename": "s7_1722.js", "season": "2025-2026"},
    127: {"name_cn": "丹麦甲", "name_en": "1st Division", "filename": "s127_1792.js", "season": "2025-2026"},
    
    # 奥地利
    3: {"name_cn": "奥甲", "name_en": "Bundesliga", "filename": "s3_2021.js", "season": "2025-2026"},
    128: {"name_cn": "奥乙", "name_en": "2. Liga", "filename": "s128_1926.js", "season": "2025-2026"},
    
    # 瑞士
    27: {"name_cn": "瑞士超", "name_en": "Super League", "filename": "s27_2507.js", "season": "2025-2026"},
    121: {"name_cn": "瑞士甲", "name_en": "Challenge League", "filename": "s121_297.js", "season": "2025-2026"},
    
    # 爱尔兰
    1: {"name_cn": "爱超", "name_en": "Premier Division", "filename": "s1_418.js", "season": "2025"},
    139: {"name_cn": "爱甲", "name_en": "First Division", "filename": "s139_419.js", "season": "2025"},
    
    # 北爱尔兰
    165: {"name_cn": "北爱超", "name_en": "Premiership", "filename": "s165_91.js", "season": "2025-2026"},
    748: {"name_cn": "北爱冠", "name_en": "Championship", "filename": "s748_919.js", "season": "2025-2026"},
    
    # 俄罗斯
    10: {"name_cn": "俄超", "name_en": "Premier League", "filename": "s10_591.js", "season": "2025-2026"},
    235: {"name_cn": "俄甲", "name_en": "First League", "filename": "s235_674.js", "season": "2025-2026"},
    
    # 波兰
    6: {"name_cn": "波兰超", "name_en": "Ekstraklasa", "filename": "s6_1103.js", "season": "2025-2026"},
    221: {"name_cn": "波兰甲", "name_en": "I liga", "filename": "s221_1298.js", "season": "2025-2026"},
    
    # 乌克兰
    119: {"name_cn": "乌克超", "name_en": "Premier League", "filename": "s119_1104.js", "season": "2025-2026"},
    872: {"name_cn": "乌克甲", "name_en": "Persha Liga", "filename": "s872_948.js", "season": "2025-2026"},
    
    # 捷克
    137: {"name_cn": "捷甲", "name_en": "First League", "filename": "s137_2002.js", "season": "2025-2026"},
    290: {"name_cn": "捷乙", "name_en": "FNL", "filename": "s290.js", "season": "2025-2026"},
    
    # 罗马尼亚
    124: {"name_cn": "罗甲", "name_en": "Liga I", "filename": "s124_1573.js", "season": "2025-2026"},
    
    # 土耳其
    30: {"name_cn": "土超", "name_en": "Super Lig", "filename": "s30_690.js", "season": "2025-2026"},
    130: {"name_cn": "土甲", "name_en": "TFF 1. Lig", "filename": "s130_264.js", "season": "2025-2026"},
    
    # 亚洲联赛
    # 中国
    60: {"name_cn": "中超", "name_en": "Chinese Super League", "filename": "s60_2187.js", "season": "2025"},
    61: {"name_cn": "中甲", "name_en": "China League One", "filename": "s61_2224.js", "season": "2025"},
    
    # 日本
    25: {"name_cn": "日职联", "name_en": "J1 League", "filename": "s25_943.js", "season": "2025"},
    284: {"name_cn": "日职乙", "name_en": "J2 League", "filename": "s284_808.js", "season": "2025"},
    
    # 韩国
    15: {"name_cn": "韩K联", "name_en": "K League 1", "filename": "s15_313.js", "season": "2025"},
    1292: {"name_cn": "韩K2联", "name_en": "K League 2", "filename": "s1292_1212.js", "season": "2025"},
    
    # 沙特 & 卡塔尔
    292: {"name_cn": "沙特联", "name_en": "Saudi Pro League", "filename": "s292_1079.js", "season": "2025-2026"},
    745: {"name_cn": "沙地甲", "name_en": "First Division", "filename": "s745_918.js", "season": "2025-2026"},
    313: {"name_cn": "卡塔尔联", "name_en": "Stars League", "filename": "s313_334.js", "season": "2025-2026"},
    
    # 澳大利亚
    273: {"name_cn": "澳超", "name_en": "A-League", "filename": "s273_462.js", "season": "2025-2026"},
    616: {"name_cn": "澳威超", "name_en": "NSW Premier League", "filename": "s616_376.js", "season": "2025"},
    
    # 美洲联赛
    # 美国
    21: {"name_cn": "美职业", "name_en": "MLS", "filename": "s21_165.js", "season": "2025"},
    448: {"name_cn": "美冠联", "name_en": "USL Championship", "filename": "s448_239.js", "season": "2025"},
    
    # 巴西
    4: {"name_cn": "巴西甲", "name_en": "Série A", "filename": "s4.js", "season": "2026"},
    358: {"name_cn": "巴西乙", "name_en": "Série B", "filename": "s358.js", "season": "2025"},
    
    # 阿根廷
    2: {"name_cn": "阿甲", "name_en": "Primera División", "filename": "s2_2761.js", "season": "2025"},
    423: {"name_cn": "阿乙", "name_en": "Primera Nacional", "filename": "s423_1174.js", "season": "2025"},
    
    # 墨西哥
    140: {"name_cn": "墨西联", "name_en": "Liga MX", "filename": "s140_44.js", "season": "2025-2026"},
    847: {"name_cn": "墨西甲", "name_en": "Liga de Expansión", "filename": "s847_2967.js", "season": "2025-2026"},
}

def get_league_by_id(league_id: int) -> Optional[Dict]:
    """Get league information by league_id"""
    return LEAGUE_ID_MAPPING.get(league_id)

def get_league_by_filename(filename: str) -> Optional[Dict]:
    """Get league information by filename"""
    for league_id, info in LEAGUE_ID_MAPPING.items():
        if info['filename'] == filename:
            return {'league_id': league_id, **info}
    return None

def get_league_by_name(name_cn: str) -> Optional[Dict]:
    """Get league information by Chinese name"""
    for league_id, info in LEAGUE_ID_MAPPING.items():
        if info['name_cn'] == name_cn:
            return {'league_id': league_id, **info}
    return None
