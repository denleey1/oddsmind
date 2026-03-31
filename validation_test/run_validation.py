#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
样本外验证命令行工具
用于导入策略规则并运行验证
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime, date
from typing import List, Optional

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from validation_test.strategy_rule_service import StrategyRuleService
from validation_test.out_of_sample_validator import OutOfSampleValidator
from core.logger import get_logger

logger = get_logger(__name__)


def import_golden_rules():
    """导入黄金定式规则"""
    print("正在导入黄金定式规则...")
    service = StrategyRuleService()
    count = service.import_golden_rules()
    print(f"✅ 成功导入 {count} 条规则")
    return count


def list_rules(validation_status: Optional[str] = None):
    """列出所有策略规则"""
    service = StrategyRuleService()
    rules = service.get_all_rules(validation_status=validation_status)
    
    print(f"\n共找到 {len(rules)} 条策略规则:\n")
    print(f"{'ID':<6} {'规则描述':<60} {'训练胜率':<12} {'验证状态':<12} {'评级':<8}")
    print("-" * 100)
    
    for rule in rules:
        rule_desc = f"{rule['home_range_cond']} VS {rule['away_range_cond']} | 平:{rule['draw_range_cond']}"
        training_rate = f"{rule['training_win_rate']}% ({rule['training_sample_size']})"
        validation_status = rule.get('validation_status', 'PENDING')
        rating = rule.get('rating', 'N/A')
        
        print(f"{rule['rule_id']:<6} {rule_desc:<60} {training_rate:<12} {validation_status:<12} {rating:<8}")
    
    print()


def validate_rules(rule_ids: Optional[List[int]] = None,
                  start_date: Optional[str] = None,
                  end_date: Optional[str] = None,
                  validation_table: str = 'odds_analysis_results',
                  match_table: str = 'matches',
                  company_id: Optional[int] = None):
    """运行验证"""
    validator = OutOfSampleValidator(
        validation_table=validation_table,
        match_table=match_table,
        company_id=company_id
    )
    
    # 解析日期
    start = None
    end = None
    if start_date:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    print(f"\n开始验证策略规则...")
    if start or end:
        print(f"日期范围: {start or '不限'} 至 {end or '不限'}")
    print()
    
    results = validator.validate_all_rules(
        rule_ids=rule_ids,
        start_date=start,
        end_date=end
    )
    
    # 显示结果
    print("\n" + "="*100)
    print("验证结果汇总")
    print("="*100)
    
    passed = [r for r in results if r.get('validation_status') == 'PASSED']
    weakened = [r for r in results if r.get('validation_status') == 'WEAKENED']
    failed = [r for r in results if r.get('validation_status') == 'FAILED']
    no_sample = [r for r in results if r.get('validation_status') == 'NO_SAMPLE']
    
    print(f"\n验证通过 (✅): {len(passed)} 条")
    print(f"效力减弱 (⚠️): {len(weakened)} 条")
    print(f"验证失败 (❌): {len(failed)} 条")
    print(f"样本不足 (⏳): {len(no_sample)} 条")
    
    if passed:
        print(f"\n✅ 验证通过的规则 ({len(passed)} 条):")
        print(f"{'规则ID':<8} {'样本数':<8} {'胜率':<10} {'不败率':<10} {'状态':<20}")
        print("-" * 60)
        for r in passed:
            rule = validator.rule_service.get_rule_by_id(r['rule_id'])
            rule_desc = f"{rule['home_range_cond']} VS {rule['away_range_cond']}"
            print(f"{r['rule_id']:<8} {r['total_matches']:<8} {r['win_rate']:<10.1f}% {r['unbeaten_rate']:<10.1f}% {r['validation_comment']:<20}")
    
    if weakened:
        print(f"\n⚠️ 效力减弱的规则 ({len(weakened)} 条):")
        print(f"{'规则ID':<8} {'样本数':<8} {'胜率':<10} {'状态':<20}")
        print("-" * 60)
        for r in weakened:
            print(f"{r['rule_id']:<8} {r['total_matches']:<8} {r['win_rate']:<10.1f}% {r['validation_comment']:<20}")
    
    if failed:
        print(f"\n❌ 验证失败的规则 ({len(failed)} 条):")
        print(f"{'规则ID':<8} {'样本数':<8} {'胜率':<10} {'状态':<20}")
        print("-" * 60)
        for r in failed:
            print(f"{r['rule_id']:<8} {r['total_matches']:<8} {r['win_rate']:<10.1f}% {r['validation_comment']:<20}")
    
    print()


def generate_report(output_file: Optional[str] = None):
    """生成验证报告"""
    validator = OutOfSampleValidator()
    report = validator.get_validation_report()
    
    # 生成报告文本
    report_text = f"""
{'='*100}
样本外验证报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*100}

汇总统计:
  总规则数: {report['summary']['total_rules']}
  验证通过 (✅): {report['summary']['passed']}
  效力减弱 (⚠️): {report['summary']['weakened']}
  验证失败 (❌): {report['summary']['failed']}
  待验证 (⏳): {report['summary']['pending']}

{'='*100}
详细规则列表
{'='*100}

"""
    
    for rule in report['rules']:
        status_icon = {
            'PASSED': '✅',
            'WEAKENED': '⚠️',
            'FAILED': '❌',
            'PENDING': '⏳'
        }.get(rule.get('validation_status'), '❓')
        
        report_text += f"""
{status_icon} 规则 #{rule['rule_id']}: {rule.get('rule_name', '未命名')}
   规则描述: {rule['rule_desc']}
   期望结果: {rule['expected_result']}
   训练数据: 胜率 {rule['training_win_rate']}% (样本: {rule['training_sample_size']})
"""
        
        if rule.get('validation_win_rate'):
            report_text += f"""   验证数据: 胜率 {rule['validation_win_rate']}% (样本: {rule['validation_sample_size']})
   验证状态: {rule['validation_status']}
   最后验证: {rule.get('last_validated_at', '从未验证')}
"""
        else:
            report_text += f"""   验证状态: 待验证
"""
        
        report_text += f"""   评级: {rule['rating']}
   验证次数: {rule['validation_count']}
   
"""
    
    # 输出到控制台
    print(report_text)
    
    # 保存到文件
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"\n✅ 报告已保存到: {output_path}")
    else:
        # 默认保存到 reports 目录
        reports_dir = Path(__file__).parent / 'reports'
        reports_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = reports_dir / f'validation_report_{timestamp}.txt'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"\n✅ 报告已保存到: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='样本外验证工具')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 导入规则命令
    import_parser = subparsers.add_parser('import', help='导入黄金定式规则')
    
    # 列出规则命令
    list_parser = subparsers.add_parser('list', help='列出所有策略规则')
    list_parser.add_argument('--status', choices=['PENDING', 'PASSED', 'WEAKENED', 'FAILED'], 
                           help='按验证状态过滤')
    
    # 验证命令
    validate_parser = subparsers.add_parser('validate', help='运行验证')
    validate_parser.add_argument('--rule-ids', type=str, help='要验证的规则ID列表（逗号分隔）')
    validate_parser.add_argument('--start-date', type=str, help='验证开始日期 (YYYY-MM-DD)')
    validate_parser.add_argument('--end-date', type=str, help='验证结束日期 (YYYY-MM-DD)')
    validate_parser.add_argument('--validation-table', type=str, default='odds_analysis_results',
                                help='验证数据表名（默认: odds_analysis_results）')
    validate_parser.add_argument('--match-table', type=str, default='matches',
                                help='比赛表名（默认: matches）')
    validate_parser.add_argument('--company-id', type=int, help='公司ID（可选，如果指定则只验证该公司的数据）')
    
    # 生成报告命令
    report_parser = subparsers.add_parser('report', help='生成验证报告')
    report_parser.add_argument('--output', type=str, help='输出文件路径（可选）')
    
    args = parser.parse_args()
    
    if args.command == 'import':
        import_golden_rules()
    elif args.command == 'list':
        list_rules(validation_status=args.status)
    elif args.command == 'validate':
        rule_ids = None
        if args.rule_ids:
            rule_ids = [int(x.strip()) for x in args.rule_ids.split(',')]
        validate_rules(
            rule_ids=rule_ids,
            start_date=args.start_date,
            end_date=args.end_date,
            validation_table=args.validation_table,
            match_table=args.match_table,
            company_id=args.company_id
        )
    elif args.command == 'report':
        generate_report(output_file=args.output)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
