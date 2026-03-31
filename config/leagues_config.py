#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Leagues configuration - Updated from urls.txt
包含所有188个联赛的最新配置
"""

from typing import Dict, List, NamedTuple
import re

from config.monitoring_config import MONITORED_LEAGUES


class LeagueInfo(NamedTuple):
    """League information structure."""
    league_filename: str  # The league's unique filename, e.g., 's36.js' or 's34_2948.js'
    name_cn: str
    name_en: str
    country: str
    level: int
    season: str = "2024-2025"
    total_rounds: int = 38
    is_active: bool = True
    division: str = ""  # 分区标识: 'east', 'west' 等, 空字符串表示无分区

# 从urls.txt导入的所有联赛配置（188个联赛）
LEAGUES_CONFIG: Dict[str, LeagueInfo] = {
    
    # ========== 欧洲联赛 ==========
    # 英格兰
    "ENG_PREMIER": LeagueInfo("s36.js", "英超", "Premier League", "England", 1, "2025-2026", 38),
    "ENG_CHAMPIONSHIP": LeagueInfo("s37_87.js", "英冠", "Championship", "England", 2, "2025-2026", 46),
    "ENG_LEAGUE1": LeagueInfo("s39_135.js", "英甲", "League One", "England", 3, "2025-2026", 46),
    
    # 西班牙  
    "ESP_LALIGA": LeagueInfo("s31.js", "西甲", "La Liga", "Spain", 1, "2025-2026", 38),
    "ESP_SEGUNDA": LeagueInfo("s33_546.js", "西乙", "Segunda Division", "Spain", 2, "2025-2026", 42),
    
    # 意大利
    "ITA_SERIEA": LeagueInfo("s34_2948.js", "意甲", "Serie A", "Italy", 1, "2025-2026", 38),
    "ITA_SERIEB": LeagueInfo("s40_261.js", "意乙", "Serie B", "Italy", 2, "2025-2026", 38),
    
    # 德国
    "GER_BUNDESLIGA": LeagueInfo("s8.js", "德甲", "Bundesliga", "Germany", 1, "2025-2026", 34),
    "GER_2BUNDESLIGA": LeagueInfo("s9_132.js", "德乙", "2. Bundesliga", "Germany", 2, "2025-2026", 34),
    
    # 法国
    "FRA_LIGUE1": LeagueInfo("s11.js", "法甲", "Ligue 1", "France", 1, "2025-2026", 38),
    "FRA_LIGUE2": LeagueInfo("s12_1778.js", "法乙", "Ligue 2", "France", 2, "2025-2026", 38),
    
    # 葡萄牙
    "POR_PRIMEIRA": LeagueInfo("s23_1123.js", "葡超", "Primeira Liga", "Portugal", 1, "2025-2026", 34),
    "POR_SEGUNDA": LeagueInfo("s157_1787.js", "葡甲", "Segunda Liga", "Portugal", 2, "2025-2026", 34),
    
    # 苏格兰
    "SCO_PREMIERSHIP": LeagueInfo("s29_2498.js", "苏超", "Scottish Premiership", "Scotland", 1, "2025-2026", 38),
    "SCO_CHAMPIONSHIP": LeagueInfo("s150_1115.js", "苏冠", "Scottish Championship", "Scotland", 2, "2025-2026", 36),
    
    # 荷兰
    "NED_EREDIVISIE": LeagueInfo("s16_98.js", "荷甲", "Eredivisie", "Netherlands", 1, "2025-2026", 34),
    "NED_EERSTE": LeagueInfo("s17_94.js", "荷乙", "Eerste Divisie", "Netherlands", 2, "2025-2026", 38),
    
    # 比利时
    "BEL_PRO": LeagueInfo("s5_114.js", "比甲", "Belgian Pro League", "Belgium", 1, "2025-2026", 30),
    "BEL_FIRST": LeagueInfo("s138_129.js", "比乙", "First Division B", "Belgium", 2, "2025-2026", 28),
    
    # 瑞典
    "SWE_ALLSVENSKAN": LeagueInfo("s26_431.js", "瑞典超", "Allsvenskan", "Sweden", 1, "2025", 30),
    "SWE_SUPERETTAN": LeagueInfo("s122_415.js", "瑞典甲", "Superettan", "Sweden", 2, "2025", 30),
    
    # 芬兰
    "FIN_VEIKKAUSLIIGA": LeagueInfo("s13_2082.js", "芬超", "Veikkausliiga", "Finland", 1, "2025", 22),
    "FIN_YKKONEN": LeagueInfo("s212_413.js", "芬甲", "Ykkonen", "Finland", 2, "2025", 27),
    
    # 挪威
    "NOR_ELITESERIEN": LeagueInfo("s22_3219.js", "挪超", "Eliteserien", "Norway", 1, "2025", 30),
    "NOR_FIRST": LeagueInfo("s123_437.js", "挪甲", "OBOS-ligaen", "Norway", 2, "2025", 30),
    
    # 丹麦
    "DEN_SUPERLIGA": LeagueInfo("s7_1722.js", "丹麦超", "Superliga", "Denmark", 1, "2025-2026", 32),
    "DEN_FIRST": LeagueInfo("s127_1792.js", "丹麦甲", "1st Division", "Denmark", 2, "2025-2026", 28),
    
    # 奥地利
    "AUT_BUNDESLIGA": LeagueInfo("s3_2021.js", "奥甲", "Bundesliga", "Austria", 1, "2025-2026", 32),
    "AUT_ZWEITE": LeagueInfo("s128_1926.js", "奥乙", "2. Liga", "Austria", 2, "2025-2026", 30),
    
    # 瑞士
    "SUI_SUPER": LeagueInfo("s27_2507.js", "瑞士超", "Super League", "Switzerland", 1, "2025-2026", 36),
    "SUI_CHALLENGE": LeagueInfo("s121_297.js", "瑞士甲", "Challenge League", "Switzerland", 2, "2025-2026", 36),
    
    # 爱尔兰
    "IRE_PREMIER": LeagueInfo("s1_418.js", "爱超", "Premier Division", "Ireland", 1, "2025", 36),
    "IRE_FIRST": LeagueInfo("s139_419.js", "爱甲", "First Division", "Ireland", 2, "2025", 27),
    
    # 北爱尔兰
    "NIR_PREMIERSHIP": LeagueInfo("s165_91.js", "北爱超", "Premiership", "Northern Ireland", 1, "2025-2026", 38),
    "NIR_CHAMPIONSHIP": LeagueInfo("s748_919.js", "北爱冠", "Championship", "Northern Ireland", 2, "2025-2026", 26),
    
    # 俄罗斯
    "RUS_PREMIER": LeagueInfo("s10_591.js", "俄超", "Premier League", "Russia", 1, "2025-2026", 30),
    "RUS_FIRST": LeagueInfo("s235_674.js", "俄甲", "First League", "Russia", 2, "2025-2026", 38),
    
    # 波兰
    "POL_EKSTRAKLASA": LeagueInfo("s6_1103.js", "波兰超", "Ekstraklasa", "Poland", 1, "2025-2026", 30),
    "POL_FIRST": LeagueInfo("s221_1298.js", "波兰甲", "I liga", "Poland", 2, "2025-2026", 34),
    
    # 乌克兰
    "UKR_PREMIER": LeagueInfo("s119_1104.js", "乌克超", "Premier League", "Ukraine", 1, "2025-2026", 30),
    "UKR_FIRST": LeagueInfo("s872_948.js", "乌克甲", "Persha Liga", "Ukraine", 2, "2025-2026", 32),
    
    # 捷克
    "CZE_FIRST": LeagueInfo("s137_2002.js", "捷甲", "First League", "Czech Republic", 1, "2025-2026", 30),
    "CZE_SECOND": LeagueInfo("s290.js", "捷乙", "FNL", "Czech Republic", 2, "2025-2026", 30),
    
    # 希腊
    "GRE_SUPER": LeagueInfo("s32_102.js", "希腊超", "Super League", "Greece", 1, "2025-2026", 26),
    "GRE_FIRST": LeagueInfo("s170_1010.js", "希腊甲", "Super League 2", "Greece", 2, "2025-2026", 30),
    
    # 罗马尼亚
    "ROU_FIRST": LeagueInfo("s124_1573.js", "罗甲", "Liga I", "Romania", 1, "2025-2026", 30),
    "ROU_SECOND": LeagueInfo("s1423_1399.js", "罗乙", "Liga II", "Romania", 2, "2025-2026", 38),
    
    # 斯洛伐克
    "SVK_SUPER": LeagueInfo("s132_1843.js", "斯伐超", "Fortuna Liga", "Slovakia", 1, "2025-2026", 30),
    "SVK_SECOND": LeagueInfo("s351_1308.js", "斯伐甲", "2. Liga", "Slovakia", 2, "2025-2026", 30),
    
    # 冰岛
    "ICE_PREMIER": LeagueInfo("s166_1192.js", "冰岛超", "Urvalsdeild", "Iceland", 1, "2025", 22),
    "ICE_FIRST": LeagueInfo("s381_2993.js", "冰岛甲", "1. deild", "Iceland", 2, "2025", 22),
    
    # 拉脱维亚
    "LAT_HIGHER": LeagueInfo("s214_2866.js", "拉脱超", "Virsliga", "Latvia", 1, "2025", 32),
    "LAT_FIRST": LeagueInfo("s1070_587.js", "拉脱甲", "Pirmā līga", "Latvia", 2, "2025", 28),
    
    # 以色列
    "ISR_PREMIER": LeagueInfo("s118_104.js", "以超", "Ligat Ha'Al", "Israel", 1, "2025-2026", 26),
    "ISR_NATIONAL": LeagueInfo("s160_108.js", "以甲", "Liga Leumit", "Israel", 2, "2025-2026", 30),
    
    # 白俄罗斯
    "BLR_PREMIER": LeagueInfo("s230_1007.js", "白俄超", "Premier League", "Belarus", 1, "2025", 30),
    "BLR_FIRST": LeagueInfo("s1046_616.js", "白俄甲", "First League", "Belarus", 2, "2025", 28),
    
    # 立陶宛
    "LTU_ALYGA": LeagueInfo("s217_1684.js", "立陶甲", "A Lyga", "Lithuania", 1, "2025", 33),
    "LTU_FIRST": LeagueInfo("s897_1012.js", "立陶乙", "Pirma lyga", "Lithuania", 2, "2025", 28),
    
    # 土耳其
    "TUR_SUPER": LeagueInfo("s30_690.js", "土超", "Super Lig", "Turkey", 1, "2025-2026", 38),
    "TUR_FIRST": LeagueInfo("s130_264.js", "土甲", "TFF 1. Lig", "Turkey", 2, "2025-2026", 36),
    
    # 威尔士
    "WAL_PREMIER": LeagueInfo("s135_475.js", "威超", "Cymru Premier", "Wales", 1, "2025-2026", 32),
    "WAL_LEAGUE": LeagueInfo("s1104_1048.js", "威联", "Cymru North/South", "Wales", 2, "2025-2026", 30, False),  # URL需用batch工具验证
    
    # 匈牙利
    "HUN_NB1": LeagueInfo("s136.js", "匈甲", "NB I", "Hungary", 1, "2025-2026", 33),
    "HUN_NB2": LeagueInfo("s703_981.js", "匈乙", "NB II", "Hungary", 2, "2025-2026", 38),
    
    # 克罗地亚
    "CRO_HNL": LeagueInfo("s133_1131.js", "克亚甲", "Prva HNL", "Croatia", 1, "2025-2026", 36),
    "CRO_DRUGA": LeagueInfo("s1612_2059.js", "克亚乙", "Druga HNL", "Croatia", 2, "2025-2026", 30),
    
    # 保加利亚
    "BUL_FIRST": LeagueInfo("s131_1093.js", "保超", "First League", "Bulgaria", 1, "2025-2026", 30),
    "BUL_SECOND": LeagueInfo("s1262_1259.js", "保乙", "Second League", "Bulgaria", 2, "2025-2026", 32),
    
    # 斯洛文尼亚
    "SVN_PRVA": LeagueInfo("s247_307.js", "斯亚甲", "PrvaLiga", "Slovenia", 1, "2025-2026", 36),
    "SVN_DRUGA": LeagueInfo("s120_2453.js", "斯亚乙", "2. SNL", "Slovenia", 2, "2025-2026", 30),
    
    # 塞浦路斯
    "CYP_FIRST": LeagueInfo("s159_110.js", "塞浦甲", "First Division", "Cyprus", 1, "2025-2026", 26),
    "CYP_SECOND": LeagueInfo("s915_169.js", "塞浦乙", "Second Division", "Cyprus", 2, "2025-2026", 30),
    
    # 塞尔维亚
    "SRB_SUPER": LeagueInfo("s129_1167.js", "塞尔超", "SuperLiga", "Serbia", 1, "2025-2026", 37),
    "SRB_FIRST": LeagueInfo("s1061_1147.js", "塞尔甲", "Prva Liga", "Serbia", 2, "2025-2026", 30),
    
    # 阿尔巴尼亚
    "ALB_SUPER": LeagueInfo("s315_326.js", "阿尔巴超", "Kategoria Superiore", "Albania", 1, "2025-2026", 36),
    "ALB_FIRST": LeagueInfo("s348_3280.js", "阿尔巴甲", "Kategoria e Parë", "Albania", 2, "2025-2026", 30),
    
    # 其他欧洲国家
    "KAZ_PREMIER": LeagueInfo("s466_400.js", "哈萨克超", "Premier League", "Kazakhstan", 1, "2025", 22),
    "KAZ_FIRST": LeagueInfo("s1077_1661.js", "哈萨克甲", "First Division", "Kazakhstan", 2, "2025", 20),
    "BIH_PREMIER": LeagueInfo("s352_1730.js", "波斯甲", "Premijer Liga", "Bosnia", 1, "2025-2026", 33),
    "EST_PREMIUM": LeagueInfo("s353_2107.js", "爱沙甲", "Premium Liiga", "Estonia", 1, "2025", 36),
    "EST_ESILIIGA": LeagueInfo("s1043_566.js", "爱沙乙", "Esiliiga", "Estonia", 2, "2025", 36),
    "MDA_NATIONAL": LeagueInfo("s389_2105.js", "摩尔甲", "Divizia Națională", "Moldova", 1, "2025-2026", 28),
    "MDA_FIRST": LeagueInfo("s1014_2803.js", "摩尔乙", "Divizia A", "Moldova", 2, "2025-2026", 26),
    "ARM_PREMIER": LeagueInfo("s469_2169.js", "阿美超", "Premier League", "Armenia", 1, "2025-2026", 28),
    "ARM_FIRST": LeagueInfo("s1062.js", "阿美甲", "First League", "Armenia", 2, "2025-2026", 20),
    "MNE_FIRST": LeagueInfo("s562_541.js", "黑山甲", "Prva CFL", "Montenegro", 1, "2025-2026", 36),
    "MNE_SECOND": LeagueInfo("s1520.js", "黑山乙", "Druga Liga", "Montenegro", 2, "2025-2026", 30),
    "MLT_PREMIER": LeagueInfo("s533_760.js", "马耳甲", "Premier League", "Malta", 1, "2025-2026", 26),
    "LUX_NATIONAL": LeagueInfo("s514.js", "卢森甲", "National Division", "Luxembourg", 1, "2025-2026", 30),
    "FRO_PREMIER": LeagueInfo("s576_1938.js", "法罗甲", "Premier League", "Faroe Islands", 1, "2025", 27),
    "GEO_EROVNULI": LeagueInfo("s563_536.js", "格鲁甲", "Erovnuli Liga", "Georgia", 1, "2025", 36),
    "GEO_FIRST": LeagueInfo("s1116_1312.js", "格鲁乙", "Liga 2", "Georgia", 2, "2025", 30),
    "AZE_PREMIER": LeagueInfo("s613_259.js", "阿塞超", "Premier League", "Azerbaijan", 1, "2025-2026", 28),
    "MKD_FIRST": LeagueInfo("s392_842.js", "北马其甲", "First League", "North Macedonia", 1, "2025-2026", 33),
    "MKD_SECOND": LeagueInfo("s1242_1145.js", "北马其乙", "Second League", "North Macedonia", 2, "2025-2026", 30),
    "SMR_CHAMPIONSHIP": LeagueInfo("s1662_1665.js", "圣马甲", "Campionato", "San Marino", 1, "2025-2026", 30),
    "AND_PRIMERA": LeagueInfo("s880_459.js", "安道超", "Primera Divisió", "Andorra", 1, "2025-2026", 27),
    "KOS_SUPER": LeagueInfo("s1750_1819.js", "科索沃超", "Superliga", "Kosovo", 1, "2025-2026", 33),
    
    # ========== 美洲联赛 ==========
    # 北美洲
    "USA_MLS": LeagueInfo("s21_165.js", "美职业", "MLS", "United States", 1, "2026", 34),
    "USA_USL": LeagueInfo("s448_239.js", "美冠联", "USL Championship", "United States", 2, "2025", 34),
    "MEX_LIGAMX": LeagueInfo("s140_44.js", "墨西联", "Liga MX", "Mexico", 1, "2025-2026", 17),
    "MEX_EXPANSION": LeagueInfo("s847_2967.js", "墨西甲", "Liga de Expansión", "Mexico", 2, "2025-2026", 32),
    "CAN_PREMIER": LeagueInfo("s460_161.js", "加拿超", "Canadian Premier League", "Canada", 1, "2025", 28),
    "CAN_CHAMPIONSHIP": LeagueInfo("s2028_2031.js", "加拿职", "Canadian Championship", "Canada", 1, "2025", 10),
    
    # 中美洲
    "CRC_PRIMERA": LeagueInfo("s504_73.js", "哥斯甲", "Primera División", "Costa Rica", 1, "2025-2026", 22),
    "HON_NACIONAL": LeagueInfo("s577_12.js", "洪都甲", "Liga Nacional", "Honduras", 1, "2025-2026", 18),
    "GUA_NACIONAL": LeagueInfo("s579_65.js", "危地甲", "Liga Nacional", "Guatemala", 1, "2025-2026", 22),
    "SLV_PRIMERA": LeagueInfo("s511_82.js", "萨尔超", "Primera División", "El Salvador", 1, "2025-2026", 22),
    "JAM_PREMIER": LeagueInfo("s1409_2533.js", "牙买超", "Premier League", "Jamaica", 1, "2025-2026", 33),
    "TTO_PRO": LeagueInfo("s1684_1678.js", "千里甲", "TT Pro League", "Trinidad and Tobago", 1, "2025-2026", 18),
    "NCA_PRIMERA": LeagueInfo("s1586_2207.js", "尼拉甲", "Primera División", "Nicaragua", 1, "2025", 22),
    "PAN_PRIMERA": LeagueInfo("s1494_1850.js", "巴马甲", "Liga Panameña", "Panama", 1, "2025", 20),
    
    # 南美洲
    "BRA_SERIEA": LeagueInfo("s4.js", "巴西甲", "Série A", "Brazil", 1, "2026", 38),
    "BRA_SERIEB": LeagueInfo("s358.js", "巴西乙", "Série B", "Brazil", 2, "2026", 38),
    "ARG_PRIMERA": LeagueInfo("s2_1232.js", "阿甲", "Primera División", "Argentina", 1, "2026", 27),
    "ARG_NACIONAL": LeagueInfo("s423_1174.js", "阿乙", "Primera Nacional", "Argentina", 2, "2025", 37),
    "CHI_PRIMERA": LeagueInfo("s415_395.js", "智利甲", "Primera División", "Chile", 1, "2025", 30),
    "CHI_PRIMERA_B": LeagueInfo("s611_896.js", "智利乙", "Primera B", "Chile", 2, "2025", 32),
    "PAR_PRIMERA": LeagueInfo("s354_57.js", "巴拉甲", "Primera División", "Paraguay", 1, "2025", 22),
    "PAR_SEGUNDA": LeagueInfo("s1076_568.js", "巴拉乙", "División Intermedia", "Paraguay", 2, "2025", 32),
    "PER_LIGA1": LeagueInfo("s242_19.js", "秘鲁甲", "Liga 1", "Peru", 1, "2025", 34),
    "URU_PRIMERA": LeagueInfo("s240_22.js", "乌拉甲", "Primera División", "Uruguay", 1, "2025", 30),
    "COL_PRIMERA": LeagueInfo("s250_364.js", "哥伦甲", "Categoría Primera A", "Colombia", 1, "2025", 38),
    "COL_PRIMERA_B": LeagueInfo("s1169_741.js", "哥伦乙", "Categoría Primera B", "Colombia", 2, "2025", 32),
    "ECU_SERIE_A": LeagueInfo("s596_3361.js", "厄瓜甲", "Serie A", "Ecuador", 1, "2025", 30),
    "ECU_SERIE_B": LeagueInfo("s1398_3415.js", "厄瓜乙", "Serie B", "Ecuador", 2, "2025", 30),
    "VEN_PRIMERA": LeagueInfo("s391_63.js", "委内超", "Primera División", "Venezuela", 1, "2025", 38),
    "BOL_PRIMERA": LeagueInfo("s593_58.js", "玻利甲", "División Profesional", "Bolivia", 1, "2025", 30),
    
    # ========== 亚洲联赛 ==========
    # 东亚
    "CHN_SUPER": LeagueInfo("s60_2187.js", "中超", "Chinese Super League", "China", 1, "2025", 30),
    "CHN_LEAGUE1": LeagueInfo("s61_2224.js", "中甲", "China League One", "China", 2, "2025", 30),
    "JPN_J1_EAST": LeagueInfo("s25_3540.js", "日职联(东)", "J1 League East", "Japan", 1, "2026", 18, True, "east"),
    "JPN_J1_WEST": LeagueInfo("s25_3541.js", "日职联(西)", "J1 League West", "Japan", 1, "2026", 18, True, "west"),
    "JPN_J2": LeagueInfo("s284_808.js", "日职乙", "J2 League", "Japan", 2, "2026", 42),
    "KOR_K1": LeagueInfo("s15_313.js", "韩K联", "K League 1", "South Korea", 1, "2026", 33),
    "KOR_K2": LeagueInfo("s1292_1212.js", "韩K2联", "K League 2", "South Korea", 2, "2026", 36),
    
    # 西亚
    "SAU_PRO": LeagueInfo("s292_1079.js", "沙特联", "Saudi Pro League", "Saudi Arabia", 1, "2025-2026", 30),
    "SAU_FIRST": LeagueInfo("s745_918.js", "沙地甲", "First Division", "Saudi Arabia", 2, "2025-2026", 30),
    "IRN_PRO": LeagueInfo("s279_1055.js", "伊朗超", "Persian Gulf Pro League", "Iran", 1, "2025-2026", 30),
    "IRN_AZADEGAN": LeagueInfo("s898_1310.js", "伊朗甲", "Azadegan League", "Iran", 2, "2025-2026", 28),
    "UAE_PRO": LeagueInfo("s301_1082.js", "阿联酋超", "UAE Pro League", "UAE", 1, "2025-2026", 26),
    "UAE_FIRST": LeagueInfo("s740_799.js", "阿联酋甲", "First Division", "UAE", 2, "2025-2026", 22),
    "QAT_STARS": LeagueInfo("s313_334.js", "卡塔尔联", "Stars League", "Qatar", 1, "2025-2026", 22),
    "BHR_PREMIER": LeagueInfo("s318_271.js", "巴林超", "Premier League", "Bahrain", 1, "2025-2026", 22),
    "BHR_SECOND": LeagueInfo("s896_2216.js", "巴林甲", "Second Division", "Bahrain", 2, "2025-2026", 20),
    "JOR_PRO": LeagueInfo("s309_1139.js", "约超联", "Pro League", "Jordan", 1, "2025-2026", 22),
    "JOR_FIRST": LeagueInfo("s1078_1717.js", "约旦甲", "Division 1", "Jordan", 2, "2025-2026", 20),
    "KUW_PREMIER": LeagueInfo("s322_2382.js", "科威特联", "Premier League", "Kuwait", 1, "2025-2026", 20),
    "KUW_FIRST": LeagueInfo("s923_2383.js", "科威甲", "Division One", "Kuwait", 2, "2025-2026", 18),
    "OMA_PRO": LeagueInfo("s332_634.js", "阿曼联", "Professional League", "Oman", 1, "2025-2026", 26),
    "LBN_PREMIER": LeagueInfo("s325_2404.js", "黎巴嫩", "Lebanese Premier League", "Lebanon", 1, "2025-2026", 22),
    "IRQ_PREMIER": LeagueInfo("s1054_580.js", "伊拉联", "Iraqi Premier League", "Iraq", 1, "2025-2026", 38),
    "YEM_LEAGUE": LeagueInfo("s465_3042.js", "也门甲", "Yemeni League", "Yemen", 1, "2023-2024", 26, False),  # 数据源可能已停止
    "YEM_SECOND": LeagueInfo("s976_732.js", "也门乙", "Second Division", "Yemen", 2, "2014", 20, False),       # 数据源已停止
    
    # 南亚
    "IND_SUPER": LeagueInfo("s1367_1230.js", "印度超", "Indian Super League", "India", 1, "2025-2026", 22),
    "IND_ILEAGUE": LeagueInfo("s763_2399.js", "印度甲", "I-League", "India", 2, "2025-2026", 22),
    "BGD_PREMIER": LeagueInfo("s1527_2385.js", "孟加拉联", "Premier League", "Bangladesh", 1, "2025-2026", 24),
    
    # 东南亚
    "SGP_PREMIER": LeagueInfo("s194_1004.js", "新加坡联", "Premier League", "Singapore", 1, "2025-2026", 28),
    "MAS_SUPER": LeagueInfo("s316_739.js", "马来超", "Super League", "Malaysia", 1, "2025-2026", 26),
    "MAS_PREMIER": LeagueInfo("s317_744.js", "马来甲", "Premier League", "Malaysia", 2, "2025-2026", 22, False),  # URL需用batch工具验证
    "THA_LEAGUE1": LeagueInfo("s700_442.js", "泰超", "Thai League 1", "Thailand", 1, "2025-2026", 30),
    "THA_LEAGUE2": LeagueInfo("s1048_2430.js", "泰甲", "Thai League 2", "Thailand", 2, "2025-2026", 34),
    "VIE_VLEAGUE": LeagueInfo("s766_2096.js", "越南联", "V.League 1", "Vietnam", 1, "2025-2026", 26),
    "VIE_FIRST": LeagueInfo("s1248_3133.js", "越南甲", "V.League 2", "Vietnam", 2, "2024-2025", 26),
    "IDN_LIGA1": LeagueInfo("s1122_955.js", "印尼超", "Liga 1", "Indonesia", 1, "2025-2026", 34),
    "MYA_NATIONAL": LeagueInfo("s1443_1709.js", "缅甸联", "National League", "Myanmar", 1, "2025-2026", 22),
    "CAM_PREMIER": LeagueInfo("s1538_3046.js", "柬埔超", "Cambodian Premier League", "Cambodia", 1, "2025-2026", 22),
    
    # 中亚
    "UZB_SUPER": LeagueInfo("s772_1958.js", "乌兹超", "Super League", "Uzbekistan", 1, "2025", 26),
    "UZB_FIRST": LeagueInfo("s1160_3121.js", "乌兹甲", "First League", "Uzbekistan", 2, "2025", 24),
    "TKM_YOKARY": LeagueInfo("s2107_2141.js", "土库曼超", "Yokary Liga", "Turkmenistan", 1, "2025", 24),
    "TJK_HIGHER": LeagueInfo("s1889_2133.js", "塔吉克联", "Higher League", "Tajikistan", 1, "2025", 20),
    "MNG_PREMIER": LeagueInfo("s1909_2779.js", "蒙古超", "Premier League", "Mongolia", 1, "2025-2026", 16),
    
    # ========== 大洋洲联赛 ==========
    "AUS_ALEAGUE": LeagueInfo("s273_462.js", "澳超", "A-League", "Australia", 1, "2025-2026", 26),
    "AUS_NSW": LeagueInfo("s616_376.js", "澳威超", "NSW Premier League", "Australia", 1, "2025", 22),
    "NZL_CHAMPIONSHIP": LeagueInfo("s341_586.js", "新西兰联", "National League", "New Zealand", 1, "2025", 22),
    
    # ========== 非洲联赛 ==========
    "RSA_PREMIER": LeagueInfo("s308_607.js", "南非超", "Premier Division", "South Africa", 1, "2025-2026", 30),
    "RSA_FIRST": LeagueInfo("s907_563.js", "南非甲", "National First Division", "South Africa", 2, "2025-2026", 30),
    "NGA_PREMIER": LeagueInfo("s949_1984.js", "尼日超", "Premier League", "Nigeria", 1, "2025-2026", 38),
    "MAR_BOTOLA": LeagueInfo("s321.js", "摩洛超", "Botola Pro", "Morocco", 1, "2025-2026", 30),
    "MAR_SECOND": LeagueInfo("s953_3348.js", "摩洛乙", "Botola 2", "Morocco", 2, "2025-2026", 32),
    "TUN_LIGUE1": LeagueInfo("s326_3161.js", "突尼甲", "Ligue 1", "Tunisia", 1, "2025-2026", 30),
    "TUN_LIGUE2": LeagueInfo("s1222_2586.js", "突尼乙", "Ligue 2", "Tunisia", 2, "2025-2026", 28),
    "ALG_LIGUE1": LeagueInfo("s193.js", "阿尔甲", "Ligue 1", "Algeria", 1, "2025-2026", 32),
    "ALG_LIGUE2": LeagueInfo("s863_2393.js", "阿尔乙", "Ligue 2", "Algeria", 2, "2025-2026", 32),
    "EGY_PREMIER": LeagueInfo("s303_847.js", "埃及超", "Premier League", "Egypt", 1, "2025-2026", 34),
    "LBY_PREMIER": LeagueInfo("s324_3372.js", "利比亚甲", "Premier League", "Libya", 1, "2025-2026", 38),
    "ZIM_PREMIER": LeagueInfo("s1451_2602.js", "津巴超", "Premier League", "Zimbabwe", 1, "2025", 34),
    "ANG_GIRABOLA": LeagueInfo("s1471_1636.js", "安哥甲", "Girabola", "Angola", 1, "2025-2026", 30),
    "GHA_PREMIER": LeagueInfo("s1393_2552.js", "加纳超", "Premier League", "Ghana", 1, "2025-2026", 34),
    "SDN_PREMIER": LeagueInfo("s1487_3352.js", "苏丹超", "Premier League", "Sudan", 1, "2025", 26),
    "BDI_PREMIER": LeagueInfo("s1741_2134.js", "布隆迪超", "Premier League", "Burundi", 1, "2025-2026", 30),
}

# ========== 分区赛制配置 ==========
# 一个 league_id 下分为多个分区的联赛
# key = league_id, value = 各分区 config_key 列表
# 用于广义实力计算时自动按分区分别计算 + 合并计算
DIVISIONAL_LEAGUES: Dict[int, Dict[str, object]] = {
    25: {  # 日职联 J1 (2026赛季起东西分区)
        'divisions': {
            'east': {'config_key': 'JPN_J1_EAST', 'name_cn': '东区', 'teams_count': 10},
            'west': {'config_key': 'JPN_J1_WEST', 'name_cn': '西区', 'teams_count': 10},
        },
        'global_name_cn': '日职联(全局)',
        'season': '2026',
    },
}


def get_division_for_league_code(league_code: str) -> str:
    """根据 league_code 获取其 division 值（空字符串表示非分区联赛）"""
    info = LEAGUES_CONFIG.get(league_code)
    if info and info.division:
        return info.division
    return ""


def get_divisional_league_codes(league_id: int) -> Dict[str, str]:
    """
    根据 league_id 获取其所有分区的 league_code 映射。
    返回 {'east': 'JPN_J1_EAST', 'west': 'JPN_J1_WEST'} 这样的字典。
    如果不是分区联赛，返回空字典。
    """
    dl = DIVISIONAL_LEAGUES.get(league_id)
    if not dl:
        return {}
    return {
        div_key: div_info['config_key']
        for div_key, div_info in dl['divisions'].items()
    }


# 辅助函数
def get_leagues_by_country(country: str) -> Dict[str, LeagueInfo]:
    """Get all leagues from a specific country."""
    return {
        code: info for code, info in LEAGUES_CONFIG.items() 
        if info.country == country
    }

def get_leagues_by_level(level: int) -> Dict[str, LeagueInfo]:
    """Get all leagues of a specific level (1=top tier, 2=second tier, etc.)."""
    return {
        code: info for code, info in LEAGUES_CONFIG.items()
        if info.level == level
    }

def get_top_leagues() -> Dict[str, LeagueInfo]:
    """Get top tier leagues only.""" 
    return get_leagues_by_level(1)

def get_active_leagues() -> Dict[str, LeagueInfo]:
    """Get only active leagues."""
    return {
        code: info for code, info in LEAGUES_CONFIG.items()
        if info.is_active
    }

# League groupings for different scraping strategies
LEAGUE_GROUPS = {
    "big5": ["ENG_PREMIER", "ESP_LALIGA", "ITA_SERIEA", "GER_BUNDESLIGA", "FRA_LIGUE1"],  
    "big5_second": ["ENG_CHAMPIONSHIP", "ESP_SEGUNDA", "ITA_SERIEB", "GER_2BUNDESLIGA", "FRA_LIGUE2"],
    "europe_top": ["ENG_PREMIER", "ESP_LALIGA", "ITA_SERIEA", "GER_BUNDESLIGA", "FRA_LIGUE1", 
                   "NED_EREDIVISIE", "POR_PRIMEIRA", "RUS_PREMIER", "TUR_SUPER"],
    "asia_major": ["CHN_SUPER", "JPN_J1_EAST", "JPN_J1_WEST", "KOR_K1", "SAU_PRO"],
    "americas_major": ["BRA_SERIEA", "ARG_PRIMERA", "USA_MLS", "MEX_LIGAMX"],
    "all": list(LEAGUES_CONFIG.keys())
}

# Helper function to get league codes from monitored league IDs
def get_monitored_league_codes() -> List[str]:
    """Get league codes for all monitored leagues.

    For divisional leagues (e.g. J1 East/West sharing league_id=25),
    all division codes are returned so that every division is scraped.
    """
    monitored_codes = []

    # Build a reverse mapping: league_id -> list of config codes
    # (divisional leagues produce multiple codes for one league_id)
    from collections import defaultdict
    id_to_codes_map: Dict[int, List[str]] = defaultdict(list)
    for code, info in LEAGUES_CONFIG.items():
        match = re.match(r's(\d+)', info.league_filename)
        if match:
            league_id = int(match.group(1))
            id_to_codes_map[league_id].append(code)

    # Map monitored IDs to codes (all of them for divisional leagues)
    for monitored_id in MONITORED_LEAGUES:
        codes_for_id = id_to_codes_map.get(monitored_id, [])
        if codes_for_id:
            monitored_codes.extend(codes_for_id)

    return monitored_codes


def get_dynamic_league_groups() -> Dict[str, List[str]]:
    """Return league groups including the up-to-date monitored list."""
    groups = dict(LEAGUE_GROUPS)
    groups["monitored"] = get_monitored_league_codes()
    return groups


def list_league_group_names() -> List[str]:
    """List available league group names."""
    return sorted(get_dynamic_league_groups().keys())


def get_league_group_codes(group_name: str) -> List[str]:
    """Fetch league codes for a specific group name."""
    return get_dynamic_league_groups().get(group_name, [])


# Maintain backward compatibility: populate monitored group at import time
LEAGUE_GROUPS["monitored"] = get_monitored_league_codes()


# Quick lookup from league_id to league code for validation utilities
LEAGUE_ID_TO_CODE: Dict[int, str] = {
    int(match.group(1)): code
    for code, info in LEAGUES_CONFIG.items()
    if (match := re.match(r's(\d+)', info.league_filename))
}
