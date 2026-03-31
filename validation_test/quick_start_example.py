#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
样本外验证系统 - 快速开始示例
演示如何使用验证系统
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from validation_test.strategy_rule_service import StrategyRuleService
from validation_test.out_of_sample_validator import OutOfSampleValidator
from core.logger import get_logger

logger = get_logger(__name__)


def main():
    print("="*80)
    print("样本外验证系统 - 快速开始示例")
    print("="*80)
    
    # 步骤1: 初始化服务
    print("\n步骤1: 初始化服务...")
    rule_service = StrategyRuleService()
    validator = OutOfSampleValidator()
    
    # 步骤2: 导入黄金定式规则
    print("\n步骤2: 导入黄金定式规则...")
    try:
        count = rule_service.import_golden_rules()
        print(f"✅ 成功导入 {count} 条规则")
    except Exception as e:
        print(f"⚠️ 导入规则时出错（可能已存在）: {e}")
    
    # 步骤3: 查看所有规则
    print("\n步骤3: 查看所有规则...")
    rules = rule_service.get_all_rules()
    print(f"共找到 {len(rules)} 条策略规则")
    for rule in rules[:5]:  # 只显示前5条
        rule_desc = f"{rule['home_range_cond']} VS {rule['away_range_cond']} | 平:{rule['draw_range_cond']}"
        print(f"  规则 #{rule['rule_id']}: {rule_desc}")
        print(f"    训练胜率: {rule['training_win_rate']}% (样本: {rule['training_sample_size']})")
        print(f"    评级: {rule['rating']}")
    if len(rules) > 5:
        print(f"  ... 还有 {len(rules) - 5} 条规则")
    
    # 步骤4: 运行验证（示例：验证前3条规则）
    print("\n步骤4: 运行验证（示例：验证前3条规则）...")
    print("注意：这需要数据库中有匹配的比赛数据")
    
    try:
        rule_ids = [r['rule_id'] for r in rules[:3]]
        results = validator.validate_all_rules(rule_ids=rule_ids)
        
        print(f"\n验证完成，共验证 {len(results)} 条规则：")
        for result in results:
            if 'error' in result:
                print(f"  规则 #{result['rule_id']}: ❌ 错误 - {result['error']}")
            else:
                status_icon = {
                    'PASSED': '✅',
                    'WEAKENED': '⚠️',
                    'FAILED': '❌',
                    'NO_SAMPLE': '⏳'
                }.get(result.get('validation_status'), '❓')
                
                print(f"  规则 #{result['rule_id']}: {status_icon} {result.get('validation_status', 'UNKNOWN')}")
                print(f"    样本数: {result.get('total_matches', 0)}")
                print(f"    胜率: {result.get('win_rate', 0):.1f}%")
                print(f"    状态: {result.get('validation_comment', 'N/A')}")
    except Exception as e:
        print(f"⚠️ 验证时出错: {e}")
        print("   这可能是因为数据库中没有匹配的比赛数据，或者表结构不匹配")
        print("   请检查：")
        print("   1. odds_analysis_results 表是否存在且包含 current_home_range, current_away_range, current_draw_range 字段")
        print("   2. matches 表是否存在且包含 match_status, home_score, away_score 字段")
        print("   3. 是否有已完成的比赛数据（match_status = 'finished'）")
    
    # 步骤5: 生成报告
    print("\n步骤5: 生成验证报告...")
    try:
        report = validator.get_validation_report()
        print(f"\n验证报告汇总：")
        print(f"  总规则数: {report['summary']['total_rules']}")
        print(f"  验证通过: {report['summary']['passed']}")
        print(f"  效力减弱: {report['summary']['weakened']}")
        print(f"  验证失败: {report['summary']['failed']}")
        print(f"  待验证: {report['summary']['pending']}")
    except Exception as e:
        print(f"⚠️ 生成报告时出错: {e}")
    
    print("\n" + "="*80)
    print("快速开始示例完成！")
    print("="*80)
    print("\n下一步：")
    print("1. 使用命令行工具运行完整验证：")
    print("   python validation_test/run_validation.py validate")
    print("\n2. 查看详细使用说明：")
    print("   cat validation_test/README_VALIDATION.md")
    print("\n3. 生成完整报告：")
    print("   python validation_test/run_validation.py report")


if __name__ == '__main__':
    main()
