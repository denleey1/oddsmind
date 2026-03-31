#!/usr/bin/env python3
"""
阈值敏感性分析
测试不同的赔率变化阈值对规则命中率的影响
"""

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection

# 威廉公司ID
WILLIAM_ID = 115

# 五大联赛ID
BIG5_LEAGUE_IDS = [36, 31, 34, 8, 11]

# 测试的阈值列表
THRESHOLDS = [0.02, 0.03, 0.05, 0.07, 0.10, 0.15]


def classify_odds_change_with_threshold(init: float, curr: float, threshold: float) -> str:
    """根据给定阈值分类赔率变化"""
    if curr > init * (1 + threshold):
        return '升'
    elif curr < init * (1 - threshold):
        return '降'
    return '稳'


def get_range_type(range_type: str) -> str:
    """简化盘型名称"""
    if not range_type:
        return '未知'
    return range_type


def classify_power_diff(power_diff: float) -> str:
    """分类力量差"""
    if power_diff is None:
        return '未知'
    if power_diff > 2:
        return '强让'
    elif power_diff > 0.5:
        return '微让'
    elif power_diff > -0.5:
        return '平手'
    elif power_diff > -2:
        return '微受'
    return '强受'


def get_all_finished_matches():
    """获取所有已完成比赛的数据"""
    query = '''
        SELECT 
            m.match_id, m.league_id, m.home_score, m.away_score,
            eo.initial_home, eo.initial_away, eo.initial_draw,
            eo.current_home, eo.current_away, eo.current_draw,
            oar.initial_home_range, oar.initial_away_range,
            oar.current_home_range, oar.current_away_range,
            oar.power_diff
        FROM matches m
        JOIN odds_analysis_results oar ON m.match_id = oar.match_id
        JOIN european_odds eo ON m.match_id = eo.match_id AND oar.company_id = eo.company_id
        WHERE m.match_status = 'finished'
          AND m.home_score IS NOT NULL
          AND m.away_score IS NOT NULL
          AND oar.company_id = %s
    '''
    
    db = get_connection()
    return db.execute_query(query, (WILLIAM_ID,), fetch='all')


def process_matches_with_threshold(matches, threshold):
    """用指定阈值处理比赛数据"""
    processed = []
    
    for row in matches:
        is_big5 = row['league_id'] in BIG5_LEAGUE_IDS
        
        init_home = float(row['initial_home'])
        init_away = float(row['initial_away'])
        curr_home = float(row['current_home'])
        curr_away = float(row['current_away'])
        
        # 判断让球方
        if init_home <= init_away:
            handicap = 'home'
            h_score = row['home_score']
            r_score = row['away_score']
            init_h, init_r = init_home, init_away
            curr_h, curr_r = curr_home, curr_away
            curr_h_range = row['current_home_range']
            curr_r_range = row['current_away_range']
        else:
            handicap = 'away'
            h_score = row['away_score']
            r_score = row['home_score']
            init_h, init_r = init_away, init_home
            curr_h, curr_r = curr_away, curr_home
            curr_h_range = row['current_away_range']
            curr_r_range = row['current_home_range']
        
        processed.append({
            'is_big5': is_big5,
            'h_score': h_score,
            'r_score': r_score,
            'power': classify_power_diff(float(row['power_diff']) if row['power_diff'] else None),
            'curr_h': get_range_type(curr_h_range),
            'curr_r': get_range_type(curr_r_range),
            'h_change': classify_odds_change_with_threshold(init_h, curr_h, threshold),
            'r_change': classify_odds_change_with_threshold(init_r, curr_r, threshold),
        })
    
    return processed


def test_rule_with_threshold(matches, rule_name, condition, check_result, threshold):
    """测试单个规则在指定阈值下的表现"""
    processed = process_matches_with_threshold(matches, threshold)
    
    # 分别统计五大和其他联赛
    big5_total = 0
    big5_correct = 0
    other_total = 0
    other_correct = 0
    
    for m in processed:
        if condition(m):
            if m['is_big5']:
                big5_total += 1
                if check_result(m):
                    big5_correct += 1
            else:
                other_total += 1
                if check_result(m):
                    other_correct += 1
    
    big5_acc = big5_correct / big5_total if big5_total > 0 else 0
    other_acc = other_correct / other_total if other_total > 0 else 0
    all_total = big5_total + other_total
    all_correct = big5_correct + other_correct
    all_acc = all_correct / all_total if all_total > 0 else 0
    
    return {
        'big5_total': big5_total,
        'big5_correct': big5_correct,
        'big5_acc': big5_acc,
        'other_total': other_total,
        'other_correct': other_correct,
        'other_acc': other_acc,
        'all_total': all_total,
        'all_acc': all_acc
    }


def main():
    print("=" * 80)
    print("阈值敏感性分析")
    print("=" * 80)
    print()
    
    # 获取数据
    print("加载数据...")
    matches = get_all_finished_matches()
    print(f"共 {len(matches)} 场已完成比赛")
    print()
    
    # 定义要测试的规则
    rules = [
        # 让方必赢类 - 测试升降阈值影响
        (
            '强让+让方赔率降',
            lambda m: m['power'] == '强让' and m['h_change'] == '降',
            lambda m: m['h_score'] > m['r_score'],
            '让方必赢'
        ),
        (
            '强让+让方降+受让方升',
            lambda m: m['power'] == '强让' and m['h_change'] == '降' and m['r_change'] == '升',
            lambda m: m['h_score'] > m['r_score'],
            '让方必赢'
        ),
        (
            '微让+让方赔率降',
            lambda m: m['power'] == '微让' and m['h_change'] == '降',
            lambda m: m['h_score'] > m['r_score'],
            '让方必赢'
        ),
        (
            '仅让方赔率降',
            lambda m: m['h_change'] == '降',
            lambda m: m['h_score'] > m['r_score'],
            '让方必赢'
        ),
        
        # 受让方不输类 - 测试升降阈值影响  
        (
            '仅让方赔率升',
            lambda m: m['h_change'] == '升',
            lambda m: m['h_score'] <= m['r_score'],
            '受让方不输'
        ),
        (
            '让方赔率升+受让方赔率降',
            lambda m: m['h_change'] == '升' and m['r_change'] == '降',
            lambda m: m['h_score'] <= m['r_score'],
            '受让方不输'
        ),
        (
            '强让+让方赔率升',
            lambda m: m['power'] == '强让' and m['h_change'] == '升',
            lambda m: m['h_score'] <= m['r_score'],
            '受让方不输'
        ),
        (
            '仅受让方赔率降',
            lambda m: m['r_change'] == '降',
            lambda m: m['h_score'] <= m['r_score'],
            '受让方不输'
        ),
    ]
    
    # 测试每个规则在不同阈值下的表现
    for rule_name, condition, check_result, predict in rules:
        print(f"\n{'='*80}")
        print(f"规则: {rule_name}")
        print(f"预测: {predict}")
        print(f"{'='*80}")
        print()
        print(f"{'阈值':^8} | {'五大样本':^10} | {'五大命中率':^12} | {'普通样本':^10} | {'普通命中率':^12} | {'总样本':^8} | {'总命中率':^10}")
        print("-" * 90)
        
        for threshold in THRESHOLDS:
            result = test_rule_with_threshold(matches, rule_name, condition, check_result, threshold)
            
            big5_str = f"{result['big5_correct']}/{result['big5_total']}"
            other_str = f"{result['other_correct']}/{result['other_total']}"
            
            # 标记最佳阈值
            big5_mark = "★" if result['big5_acc'] == 1.0 and result['big5_total'] >= 3 else ""
            other_mark = "★" if result['other_acc'] >= 0.9 and result['other_total'] >= 5 else ""
            
            print(f"{threshold*100:>5.0f}%   | {big5_str:^10} | {result['big5_acc']*100:>6.1f}% {big5_mark:<3} | "
                  f"{other_str:^10} | {result['other_acc']*100:>6.1f}% {other_mark:<3} | "
                  f"{result['all_total']:^8} | {result['all_acc']*100:>6.1f}%")
        
        print()
        print("★ = 五大100%且样本>=3，或普通90%+且样本>=5")
    
    # 结论分析
    print("\n" + "=" * 80)
    print("结论分析")
    print("=" * 80)
    print("""
1. 阈值越小（如2%），"升"和"降"的判定越敏感
   - 优点：样本量更大，规则触发更频繁
   - 缺点：可能把轻微波动也算进去，噪音更大

2. 阈值越大（如10%、15%），只有大幅变动才算"升/降"
   - 优点：信号更强，只捕捉显著变化
   - 缺点：样本量大幅减少，可能统计意义不足

3. 当前使用5%阈值是一个平衡选择

建议：
- 如果规则命中率随阈值增大而提高，说明"显著变化"更有预测价值
- 如果规则命中率随阈值变化不大，说明变化幅度不是关键因素
- 可以针对不同规则使用不同阈值，追求最优
""")


if __name__ == '__main__':
    main()
