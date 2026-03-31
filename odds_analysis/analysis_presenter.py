#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
赔率分析结果展示器
负责将分析结果以用户友好的格式呈现
"""
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from core.logger import get_logger

class AnalysisPresenter:
    """
    格式化并展示赔率分析结果
    """
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    def display_match_analysis(self, match_id: int, results: List[Dict]):
        """
        在控制台打印一场比赛的分析结果摘要
        """
        if not results:
            print(f"\n比赛 {match_id} 没有生成有效的分析结果。")
            return

        print("\n" + "="*120)
        print(f"比赛ID: {match_id} - 赔率分析摘要 ({len(results)} 家公司)")
        print("="*120)
        print(f"{'公司名称':<20} | {'初盘推荐':<12} | {'即时推荐':<12} | {'实力差':<8} | {'初盘规则差':<10} | {'即时规则差':<10}")
        print("-"*120)

        for res in results:
            ia = res['initial_analysis']
            ca = res['current_analysis']
            
            initial_rec = f"{ia['recommendation']['outcome']} ({ia['recommendation']['confidence']})"
            current_rec = f"{ca['recommendation']['outcome']} ({ca['recommendation']['confidence']})"

            print(f"{res['company_name']:<20.20s} | {initial_rec:<12} | {current_rec:<12} | {res['power_diff']:<8.2f} | {ia['rule_diff']:<10} | {ca['rule_diff']:<10}")
        
        print("="*120 + "\n")
 