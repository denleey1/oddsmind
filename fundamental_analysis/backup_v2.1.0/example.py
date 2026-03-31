#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基本面分析模块使用示例
演示完整的数据获取、解析和分析流程
"""
import sys
from pathlib import Path

# 将项目根目录添加到sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from fundamental_analysis import (
    FundamentalDataFetcher,
    FundamentalCalculator,
    get_league_name
)
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def analyze_match(match_id: str):
    """
    分析一场比赛的基本面
    
    Args:
        match_id: 比赛ID
    """
    print(f"\n{'='*60}")
    print(f"开始分析比赛 ID: {match_id}")
    print('='*60)
    
    # 步骤1: 获取数据
    print("\n[1] 获取比赛数据...")
    fetcher = FundamentalDataFetcher()
    parsed_data = fetcher.fetch_and_parse(match_id)
    
    if not parsed_data:
        print("   ✗ 无法获取比赛数据")
        return None
    
    # 显示基本信息
    basic_info = parsed_data.get('basic_info', {})
    print(f"   ✓ 成功获取数据")
    print(f"   - 主队: {basic_info.get('home_team', '未知')}")
    print(f"   - 客队: {basic_info.get('away_team', '未知')}")
    print(f"   - 联赛: {basic_info.get('league', '未知')}")
    
    # 显示数据量
    analysis_data = parsed_data.get('analysis_data', {})
    print(f"   - 历史交锋: {len(analysis_data.get('history', []))} 场")
    print(f"   - 主队历史: {len(analysis_data.get('home_team_history', []))} 场")
    print(f"   - 客队历史: {len(analysis_data.get('away_team_history', []))} 场")
    
    # 步骤2: 检测联赛
    print("\n[2] 检测联赛信息...")
    league_name = get_league_name(
        match_id=match_id,
        league_input=basic_info.get('league'),
        match_data=parsed_data
    )
    print(f"   ✓ 检测到联赛: {league_name if league_name else '未知（将使用全部数据）'}")
    
    # 步骤3: 计算基本面评分
    print("\n[3] 计算基本面评分...")
    calculator = FundamentalCalculator()
    result = calculator.calculate_analysis_scores(parsed_data)
    
    if not result:
        print("   ✗ 计算失败")
        return None
    
    # 显示结果
    scores = result.get('final_scores', {})
    print(f"   ✓ 计算完成")
    print(f"\n[结果]")
    print(f"   主胜评分: {scores.get('home_win', 0):.1f}")
    print(f"   平局评分: {scores.get('draw', 0):.1f}")
    print(f"   客胜评分: {scores.get('away_win', 0):.1f}")
    print(f"   信心等级: {result.get('confidence_level', '未知')}")
    print(f"   推荐结果: {result.get('recommended_outcome', '未知')}")
    
    # 显示权重信息
    weights = result.get('weights', {})
    if weights:
        print(f"\n[权重分配]")
        print(f"   近期表现权重: {weights.get('recent', 0):.1%}")
        print(f"   主客场权重: {weights.get('home_away', 0):.1%}")
        print(f"   历史交锋权重: {weights.get('h2h', 0):.1%}")
        print(f"   有历史交锋: {'是' if weights.get('has_h2h_data') else '否'}")
    
    # 显示赔率规律
    odds_patterns = result.get('odds_patterns', [])
    if odds_patterns:
        print(f"\n[赔率规律建议]")
        for pattern in odds_patterns[:3]:  # 只显示前3个
            print(f"   - {pattern}")
    
    print(f"\n{'='*60}")
    return result


def main():
    """主函数"""
    print("\n" + "="*60)
    print("基本面分析模块 - 完整工作流示例")
    print("="*60)
    
    # 测试多个比赛
    test_matches = [
        "2703385",  # 日职联赛：柏太阳神 vs 町田泽维亚
        # "2804346",  # 可以添加更多比赛ID
    ]
    
    results = []
    for match_id in test_matches:
        result = analyze_match(match_id)
        if result:
            results.append(result)
    
    # 汇总
    print("\n" + "="*60)
    print(f"分析完成！成功分析 {len(results)}/{len(test_matches)} 场比赛")
    print("="*60)


if __name__ == "__main__":
    main()