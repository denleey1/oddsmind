#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接运行验证并输出结果
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / 'oddsmind.env')

import pymysql
from datetime import datetime

def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE', 'oddsmind'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def ensure_tables_exist(db):
    """确保表存在"""
    with db.cursor() as cursor:
        # 创建 strategy_rules 表
        create_strategy_rules = """
        CREATE TABLE IF NOT EXISTS strategy_rules (
            rule_id INT AUTO_INCREMENT PRIMARY KEY,
            home_range_cond VARCHAR(50) NOT NULL COMMENT '主队盘型条件',
            away_range_cond VARCHAR(50) NOT NULL COMMENT '客队盘型条件',
            draw_range_cond VARCHAR(50) NOT NULL COMMENT '平局盘型条件',
            expected_result VARCHAR(10) NOT NULL COMMENT '期望结果',
            rule_name VARCHAR(200) COMMENT '规则名称',
            priority_order INT DEFAULT 0 COMMENT '优先级',
            training_sample_size INT DEFAULT 0 COMMENT '训练样本数',
            training_win_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '训练集胜率',
            training_unbeaten_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '训练集不败率',
            validation_status VARCHAR(20) DEFAULT 'PENDING' COMMENT '验证状态',
            last_validated_at DATETIME NULL COMMENT '最后验证时间',
            validation_sample_size INT DEFAULT 0 COMMENT '验证样本数',
            validation_win_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '验证集胜率',
            validation_unbeaten_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '验证集不败率',
            rating VARCHAR(10) DEFAULT 'N/A' COMMENT '评级',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            UNIQUE KEY uk_range_combination (home_range_cond, away_range_cond, draw_range_cond, expected_result),
            INDEX idx_validation_status (validation_status),
            INDEX idx_priority (priority_order DESC)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='策略规则表'
        """
        
        # 创建 validation_results 表
        create_validation_results = """
        CREATE TABLE IF NOT EXISTS validation_results (
            validation_id INT AUTO_INCREMENT PRIMARY KEY,
            rule_id INT NOT NULL COMMENT '关联的策略规则ID',
            validation_database VARCHAR(100) COMMENT '验证数据库名称',
            validation_table VARCHAR(100) COMMENT '验证表名称',
            validation_start_date DATE COMMENT '验证开始日期',
            validation_end_date DATE COMMENT '验证结束日期',
            total_matches INT DEFAULT 0 COMMENT '总匹配场次',
            actual_wins INT DEFAULT 0 COMMENT '实际主胜场次',
            actual_draws INT DEFAULT 0 COMMENT '实际平局场次',
            actual_losses INT DEFAULT 0 COMMENT '实际客胜场次',
            win_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '主胜率',
            unbeaten_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '不败率',
            validation_status VARCHAR(20) DEFAULT 'PENDING' COMMENT '验证状态',
            validation_comment TEXT COMMENT '验证备注',
            validated_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '验证时间',
            INDEX idx_rule_id (rule_id),
            INDEX idx_validation_status (validation_status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='验证结果表'
        """
        
        try:
            cursor.execute(create_strategy_rules)
            cursor.execute(create_validation_results)
            db.commit()
            print("✅ 表创建成功")
        except Exception as e:
            print(f"⚠️ 创建表时出错（可能已存在）: {e}")
            db.rollback()

def import_golden_rules(db):
    """导入黄金定式规则"""
    rules = [
        {
            'home_range_cond': '超实盘中水',
            'away_range_cond': '韬光盘中低水',
            'draw_range_cond': '平实高',
            'expected_result': 'HOME_WIN',
            'rule_name': '完美定式 #1',
            'priority_order': 100,
            'training_sample_size': 10,
            'training_win_rate': 100.0,
            'training_unbeaten_rate': 100.0,
            'rating': '★★★★★'
        },
        {
            'home_range_cond': '低开盘中高水',
            'away_range_cond': '高开盘中低水',
            'draw_range_cond': '平中庸上',
            'expected_result': 'HOME_WIN',
            'rule_name': '完美定式 #2',
            'priority_order': 99,
            'training_sample_size': 5,
            'training_win_rate': 100.0,
            'training_unbeaten_rate': 100.0,
            'rating': '★★★★★'
        },
        {
            'home_range_cond': '低开盘中低水',
            'away_range_cond': '韬光盘低水',
            'draw_range_cond': '平实低',
            'expected_result': 'HOME_WIN',
            'rule_name': '高胜定式 #1',
            'priority_order': 80,
            'training_sample_size': 8,
            'training_win_rate': 87.5,
            'training_unbeaten_rate': 100.0,
            'rating': '★★★★'
        },
        {
            'home_range_cond': '实开盘超低水',
            'away_range_cond': '实开盘超高水',
            'draw_range_cond': '平中庸下',
            'expected_result': 'HOME_WIN',
            'rule_name': '高胜定式 #2',
            'priority_order': 79,
            'training_sample_size': 7,
            'training_win_rate': 85.7,
            'training_unbeaten_rate': 100.0,
            'rating': '★★★★'
        },
        {
            'home_range_cond': '实开盘中高水',
            'away_range_cond': '实开盘中水',
            'draw_range_cond': '低开平',
            'expected_result': 'HOME_WIN',
            'rule_name': '高胜定式 #3',
            'priority_order': 78,
            'training_sample_size': 7,
            'training_win_rate': 85.7,
            'training_unbeaten_rate': 85.7,
            'rating': '★★★★'
        },
        {
            'home_range_cond': '实开盘中高水',
            'away_range_cond': '实开盘超低水',
            'draw_range_cond': '高开平',
            'expected_result': 'HOME_WIN',
            'rule_name': '高胜定式 #4',
            'priority_order': 77,
            'training_sample_size': 7,
            'training_win_rate': 85.7,
            'training_unbeaten_rate': 85.7,
            'rating': '★★★★'
        },
        {
            'home_range_cond': '低开盘中低水',
            'away_range_cond': '高开盘中高水',
            'draw_range_cond': '平实高',
            'expected_result': 'HOME_WIN',
            'rule_name': '高胜定式 #5',
            'priority_order': 76,
            'training_sample_size': 7,
            'training_win_rate': 85.7,
            'training_unbeaten_rate': 85.7,
            'rating': '★★★★'
        },
        {
            'home_range_cond': '超实盘中水',
            'away_range_cond': '韬光盘低水',
            'draw_range_cond': '高开平',
            'expected_result': 'HOME_WIN',
            'rule_name': '高胜定式 #6',
            'priority_order': 75,
            'training_sample_size': 6,
            'training_win_rate': 83.3,
            'training_unbeaten_rate': 100.0,
            'rating': '★★★★'
        },
        {
            'home_range_cond': '实开盘高水',
            'away_range_cond': '实开盘低水',
            'draw_range_cond': '平实高',
            'expected_result': 'HOME_WIN',
            'rule_name': '高胜定式 #7',
            'priority_order': 74,
            'training_sample_size': 6,
            'training_win_rate': 83.3,
            'training_unbeaten_rate': 100.0,
            'rating': '★★★★'
        },
        {
            'home_range_cond': '实开盘中高水',
            'away_range_cond': '实开盘超高水',
            'draw_range_cond': '低开平',
            'expected_result': 'HOME_WIN',
            'rule_name': '高胜定式 #8',
            'priority_order': 73,
            'training_sample_size': 10,
            'training_win_rate': 80.0,
            'training_unbeaten_rate': 90.0,
            'rating': '★★★'
        },
    ]
    
    with db.cursor() as cursor:
        sql = """
        INSERT INTO strategy_rules (
            home_range_cond, away_range_cond, draw_range_cond, expected_result,
            rule_name, priority_order, training_sample_size, 
            training_win_rate, training_unbeaten_rate, rating
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            rule_name = VALUES(rule_name),
            priority_order = VALUES(priority_order),
            training_sample_size = VALUES(training_sample_size),
            training_win_rate = VALUES(training_win_rate),
            training_unbeaten_rate = VALUES(training_unbeaten_rate),
            rating = VALUES(rating),
            updated_at = NOW()
        """
        
        for rule in rules:
            cursor.execute(sql, (
                rule['home_range_cond'], rule['away_range_cond'], rule['draw_range_cond'],
                rule['expected_result'], rule['rule_name'], rule['priority_order'],
                rule['training_sample_size'], rule['training_win_rate'],
                rule['training_unbeaten_rate'], rule['rating']
            ))
        
        db.commit()
        print(f"✅ 成功导入/更新 {len(rules)} 条规则")

def validate_rule(db, rule):
    """验证单个规则"""
    sql = """
    SELECT 
        COUNT(*) AS total_matches,
        SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) AS actual_wins,
        SUM(CASE WHEN home_score = away_score THEN 1 ELSE 0 END) AS actual_draws,
        SUM(CASE WHEN home_score < away_score THEN 1 ELSE 0 END) AS actual_losses
    FROM (
        SELECT DISTINCT
            m.match_id,
            m.home_score,
            m.away_score
        FROM matches m
        JOIN odds_analysis_results a ON m.match_id = a.match_id
        WHERE m.match_status = 'finished'
          AND a.current_home_range = %s
          AND a.current_away_range = %s
          AND a.current_draw_range = %s
          AND m.home_score IS NOT NULL
          AND m.away_score IS NOT NULL
    ) AS unique_matches
    """
    
    with db.cursor() as cursor:
        cursor.execute(sql, (
            rule['home_range_cond'],
            rule['away_range_cond'],
            rule['draw_range_cond']
        ))
        result = cursor.fetchone()
        
        if not result or result['total_matches'] == 0:
            return {
                'rule_id': rule['rule_id'],
                'total_matches': 0,
                'validation_status': 'NO_SAMPLE',
                'validation_comment': '样本过少，无法验证'
            }
        
        total = result['total_matches']
        wins = result['actual_wins']
        draws = result['actual_draws']
        losses = result['actual_losses']
        
        win_rate = (wins / total * 100) if total > 0 else 0.0
        unbeaten_rate = ((wins + draws) / total * 100) if total > 0 else 0.0
        
        # 判断验证状态
        if total < 3:
            status = 'NO_SAMPLE'
            comment = '样本过少，无法验证'
        elif win_rate >= 75:
            status = 'PASSED'
            comment = '✅ 验证通过 (真理)'
        elif win_rate >= 60:
            status = 'WEAKENED'
            comment = '⚠️ 效力减弱 (需谨慎)'
        else:
            status = 'FAILED'
            comment = '❌ 验证失败 (这是个巧合)'
        
        return {
            'rule_id': rule['rule_id'],
            'total_matches': total,
            'actual_wins': wins,
            'actual_draws': draws,
            'actual_losses': losses,
            'win_rate': round(win_rate, 2),
            'unbeaten_rate': round(unbeaten_rate, 2),
            'validation_status': status,
            'validation_comment': comment
        }

def main():
    print("="*100)
    print("样本外验证系统 - 运行验证")
    print("="*100)
    print()
    
    db = get_db_connection()
    
    try:
        # 1. 确保表存在
        print("步骤1: 初始化数据库表...")
        ensure_tables_exist(db)
        print("✅ 数据库表已准备就绪")
        print()
        
        # 2. 导入规则
        print("步骤2: 导入黄金定式规则...")
        import_golden_rules(db)
        print()
        
        # 3. 获取所有规则
        print("步骤3: 获取所有规则...")
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM strategy_rules ORDER BY priority_order DESC, rule_id")
            rules = cursor.fetchall()
        print(f"✅ 找到 {len(rules)} 条策略规则")
        print()
        
        # 4. 运行验证
        print("步骤4: 运行验证...")
        print("-"*100)
        results = []
        for rule in rules:
            result = validate_rule(db, rule)
            results.append(result)
            
            # 显示结果
            rule_desc = f"{rule['home_range_cond']} VS {rule['away_range_cond']} | 平:{rule['draw_range_cond']}"
            status_icon = {
                'PASSED': '✅',
                'WEAKENED': '⚠️',
                'FAILED': '❌',
                'NO_SAMPLE': '⏳'
            }.get(result['validation_status'], '❓')
            
            print(f"\n{status_icon} 规则 #{rule['rule_id']}: {rule['rule_name']}")
            print(f"   规则描述: {rule_desc}")
            print(f"   训练数据: 胜率 {rule['training_win_rate']}% (样本: {rule['training_sample_size']})")
            
            if result['total_matches'] > 0:
                print(f"   验证数据: 样本 {result['total_matches']} 场")
                print(f"             主胜: {result['actual_wins']} 场 | 平局: {result['actual_draws']} 场 | 客胜: {result['actual_losses']} 场")
                print(f"             胜率: {result['win_rate']:.1f}% | 不败率: {result['unbeaten_rate']:.1f}%")
                print(f"   验证状态: {result['validation_comment']}")
            else:
                print(f"   验证状态: {result['validation_comment']}")
        
        # 5. 汇总统计
        print("\n" + "="*100)
        print("验证结果汇总")
        print("="*100)
        
        passed = [r for r in results if r['validation_status'] == 'PASSED']
        weakened = [r for r in results if r['validation_status'] == 'WEAKENED']
        failed = [r for r in results if r['validation_status'] == 'FAILED']
        no_sample = [r for r in results if r['validation_status'] == 'NO_SAMPLE']
        
        print(f"\n验证通过 (✅): {len(passed)} 条")
        print(f"效力减弱 (⚠️): {len(weakened)} 条")
        print(f"验证失败 (❌): {len(failed)} 条")
        print(f"样本不足 (⏳): {len(no_sample)} 条")
        
        if passed:
            print(f"\n✅ 验证通过的规则 ({len(passed)} 条):")
            print(f"{'规则ID':<8} {'规则名称':<25} {'样本数':<8} {'胜率':<10} {'不败率':<10} {'状态':<30}")
            print("-"*100)
            for r in passed:
                rule = next((rule for rule in rules if rule['rule_id'] == r['rule_id']), None)
                if rule:
                    print(f"{r['rule_id']:<8} {rule['rule_name']:<25} {r['total_matches']:<8} {r['win_rate']:<10.1f}% {r['unbeaten_rate']:<10.1f}% {r['validation_comment']:<30}")
        
        if weakened:
            print(f"\n⚠️ 效力减弱的规则 ({len(weakened)} 条):")
            print(f"{'规则ID':<8} {'规则名称':<25} {'样本数':<8} {'胜率':<10} {'状态':<30}")
            print("-"*100)
            for r in weakened:
                rule = next((rule for rule in rules if rule['rule_id'] == r['rule_id']), None)
                if rule:
                    print(f"{r['rule_id']:<8} {rule['rule_name']:<25} {r['total_matches']:<8} {r['win_rate']:<10.1f}% {r['validation_comment']:<30}")
        
        if failed:
            print(f"\n❌ 验证失败的规则 ({len(failed)} 条):")
            print(f"{'规则ID':<8} {'规则名称':<25} {'样本数':<8} {'胜率':<10} {'状态':<30}")
            print("-"*100)
            for r in failed:
                rule = next((rule for rule in rules if rule['rule_id'] == r['rule_id']), None)
                if rule:
                    print(f"{r['rule_id']:<8} {rule['rule_name']:<25} {r['total_matches']:<8} {r['win_rate']:<10.1f}% {r['validation_comment']:<30}")
        
        if no_sample:
            print(f"\n⏳ 样本不足的规则 ({len(no_sample)} 条):")
            print(f"{'规则ID':<8} {'规则名称':<25} {'状态':<30}")
            print("-"*100)
            for r in no_sample:
                rule = next((rule for rule in rules if rule['rule_id'] == r['rule_id']), None)
                if rule:
                    print(f"{r['rule_id']:<8} {rule['rule_name']:<25} {r['validation_comment']:<30}")
        
        print("\n" + "="*100)
        print("验证完成！")
        print("="*100)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == '__main__':
    main()
