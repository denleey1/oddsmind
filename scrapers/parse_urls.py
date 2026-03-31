#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parse urls.txt and generate league configurations.
"""

import re
from typing import Dict, Tuple

def parse_urls_file(filepath: str) -> Dict[str, Tuple[str, str, str]]:
    """
    Parse urls.txt file and extract league information.
    Returns dict: {league_name: (filename, season, url)}
    """
    leagues = {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or not ':' in line:
                continue
                
            # Parse each line: "联赛名: URL"
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
                
            league_name = parts[0].strip()
            url = parts[1].strip()
            
            # Extract filename and season from URL
            # Example: https://zq.titan007.com/jsData/matchResult/2025-2026/s36.js?version=2025090516
            match = re.search(r'/matchResult/([^/]+)/([^?]+)', url)
            if match:
                season = match.group(1)
                filename = match.group(2)
                leagues[league_name] = (filename, season, url)
    
    return leagues

def generate_league_config(leagues: Dict[str, Tuple[str, str, str]]) -> str:
    """Generate Python configuration code for leagues."""
    
    # Country mapping based on league names
    country_map = {
        '英': 'England', '意': 'Italy', '西': 'Spain', '德': 'Germany', '法': 'France',
        '葡': 'Portugal', '荷': 'Netherlands', '苏': 'Scotland', '俄': 'Russia', '土': 'Turkey',
        '瑞典': 'Sweden', '瑞士': 'Switzerland', '挪': 'Norway', '丹': 'Denmark', '芬': 'Finland',
        '奥': 'Austria', '比': 'Belgium', '爱超': 'Ireland', '爱甲': 'Ireland',
        '北爱': 'Northern Ireland', '威': 'Wales',
        '波兰': 'Poland', '乌克': 'Ukraine', '捷': 'Czech Republic', '希': 'Greece',
        '罗': 'Romania', '斯伐': 'Slovakia', '冰': 'Iceland', '拉脱': 'Latvia',
        '以': 'Israel', '白俄': 'Belarus', '立陶': 'Lithuania',
        '匈': 'Hungary', '克亚': 'Croatia', '保': 'Bulgaria', '斯亚': 'Slovenia',
        '塞浦': 'Cyprus', '塞尔': 'Serbia', '阿尔巴': 'Albania',
        '哈萨': 'Kazakhstan', '波斯': 'Bosnia', '爱沙': 'Estonia', '摩尔': 'Moldova',
        '阿美': 'Armenia', '黑山': 'Montenegro', '马耳': 'Malta', '卢森': 'Luxembourg',
        '法罗': 'Faroe Islands', '格鲁': 'Georgia', '阿塞': 'Azerbaijan',
        '北马': 'North Macedonia', '圣马': 'San Marino', '安道': 'Andorra', '科索': 'Kosovo',
        '美': 'United States', '巴西': 'Brazil', '阿甲': 'Argentina', '阿乙': 'Argentina',
        '智利': 'Chile', '墨西': 'Mexico', '巴拉': 'Paraguay', '秘鲁': 'Peru',
        '乌拉': 'Uruguay', '哥伦': 'Colombia', '厄瓜': 'Ecuador', '委内': 'Venezuela',
        '玻利': 'Bolivia', '哥斯': 'Costa Rica', '洪都': 'Honduras', '加拿': 'Canada',
        '危地': 'Guatemala', '萨尔': 'El Salvador', '牙买': 'Jamaica', '千里': 'Trinidad and Tobago',
        '尼拉': 'Nicaragua', '巴马': 'Panama',
        '中': 'China', '日': 'Japan', '韩': 'South Korea', '澳': 'Australia',
        '沙': 'Saudi Arabia', '伊朗': 'Iran', '阿联': 'UAE', '新加坡': 'Singapore',
        '马来': 'Malaysia', '巴林': 'Bahrain', '卡塔': 'Qatar', '也门': 'Yemen',
        '约': 'Jordan', '泰': 'Thailand', '科威': 'Kuwait', '阿曼': 'Oman',
        '乌兹': 'Uzbekistan', '黎巴': 'Lebanon', '伊拉': 'Iraq', '印度': 'India',
        '越南': 'Vietnam', '印尼': 'Indonesia', '缅甸': 'Myanmar', '孟加': 'Bangladesh',
        '土库': 'Turkmenistan', '柬埔': 'Cambodia', '塔吉': 'Tajikistan', '蒙古': 'Mongolia',
        '新西兰': 'New Zealand',
        '南非': 'South Africa', '尼日': 'Nigeria', '摩洛': 'Morocco', '突尼': 'Tunisia',
        '阿尔及': 'Algeria', '埃及': 'Egypt', '利比': 'Libya', '津巴': 'Zimbabwe',
        '安哥': 'Angola', '加纳': 'Ghana', '苏丹': 'Sudan', '布隆': 'Burundi'
    }
    
    def get_country(league_name: str) -> str:
        """Get country from league name."""
        for key, country in country_map.items():
            if key in league_name:
                return country
        return 'Unknown'
    
    def get_level(league_name: str) -> int:
        """Determine league level based on name."""
        if any(x in league_name for x in ['超', '甲', 'K联', '职联', '职业']):
            return 1
        elif any(x in league_name for x in ['冠', '乙', 'K2']):
            return 2
        elif '丙' in league_name:
            return 3
        else:
            return 1  # Default to level 1
    
    def get_total_rounds(league_name: str) -> int:
        """Estimate total rounds based on league."""
        # Common round numbers
        if any(x in league_name for x in ['英超', '意甲', '西甲', '法甲']):
            return 38
        elif '德甲' in league_name:
            return 34
        elif any(x in league_name for x in ['英冠']):
            return 46
        elif any(x in league_name for x in ['中超']):
            return 30
        else:
            return 38  # Default
    
    config_lines = []
    config_lines.append('# Generated league configurations from urls.txt\n')
    config_lines.append('ADDITIONAL_LEAGUES = {\n')
    
    # Generate league codes
    code_counter = {}
    
    for league_name, (filename, season, url) in sorted(leagues.items()):
        # Generate a unique code for the league
        country = get_country(league_name)
        country_abbr = country[:3].upper()
        level = get_level(league_name)
        
        # Create unique code
        if country_abbr not in code_counter:
            code_counter[country_abbr] = {}
        if level not in code_counter[country_abbr]:
            code_counter[country_abbr][level] = 0
        
        code_counter[country_abbr][level] += 1
        code = f"{country_abbr}{level}_{code_counter[country_abbr][level]:02d}"
        
        # Generate the configuration
        config_lines.append(f'    "{code}": LeagueInfo(\n')
        config_lines.append(f'        league_filename="{filename}",\n')
        config_lines.append(f'        name_cn="{league_name}",\n')
        config_lines.append(f'        name_en="{league_name}_en",  # TODO: Add English name\n')
        config_lines.append(f'        country="{country}",\n')
        config_lines.append(f'        level={level},\n')
        config_lines.append(f'        season="{season}",\n')
        config_lines.append(f'        total_rounds={get_total_rounds(league_name)},\n')
        config_lines.append(f'        is_active=True\n')
        config_lines.append(f'    ),\n')
    
    config_lines.append('}\n')
    
    return ''.join(config_lines)

if __name__ == '__main__':
    # Parse urls.txt
    leagues = parse_urls_file('urls.txt')
    
    print(f"Parsed {len(leagues)} leagues from urls.txt")
    
    # Generate configuration
    config = generate_league_config(leagues)
    
    # Save to file
    with open('generated_leagues_config.py', 'w', encoding='utf-8') as f:
        f.write(config)
    
    print("Generated configuration saved to generated_leagues_config.py")
    
    # Also print summary
    print("\nSummary:")
    for name, (filename, season, url) in sorted(leagues.items()):
        print(f"  {name}: {filename} ({season})")