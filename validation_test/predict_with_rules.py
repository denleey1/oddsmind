#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于挖掘规则预测未来比赛 v1.0
============================
使用已验证的高准确率规则对未来比赛进行预测
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection

# ==================== 配置 ====================
COMPANY_ID = '115'  # 威廉公司
BIG5_LEAGUE_IDS = {36, 31, 34, 8, 11}
BIG5_NAMES = {36: '英超', 31: '西甲', 34: '意甲', 8: '德甲', 11: '法甲'}

# 盘型前缀
RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']


def get_range_type(range_str: str) -> Optional[str]:
    """提取盘面类型前缀"""
    if not range_str:
        return None
    for p in RANGE_PREFIXES:
        if range_str.startswith(p):
            return p
    return '其他'


def classify_odds_change(init: float, curr: float) -> str:
    """分类赔率变化"""
    if curr > init * 1.05:
        return '升'
    elif curr < init * 0.95:
        return '降'
    return '稳'


def classify_kelly(kelly: float) -> str:
    """分类Kelly系数"""
    if kelly is None:
        return '未知'
    if kelly < 0.85:
        return '低Kelly'
    elif kelly < 0.95:
        return '中Kelly'
    elif kelly < 1.05:
        return '正常Kelly'
    else:
        return '高Kelly'


def classify_power_diff(diff: float) -> str:
    """分类力量差"""
    if diff is None:
        return '未知'
    if diff > 2:
        return '强让'
    elif diff > 0.5:
        return '微让'
    elif diff > -0.5:
        return '平手'
    elif diff > -2:
        return '微受'
    else:
        return '强受'


def classify_rule_diff(diff: float) -> str:
    """分类规则差"""
    if diff is None:
        return '未知'
    if diff < -2:
        return '大负'
    elif diff < -0.5:
        return '小负'
    elif diff < 0.5:
        return '平衡'
    elif diff < 2:
        return '小正'
    else:
        return '大正'


# ==================== 规则定义 ====================

@dataclass
class RuleMatch:
    """规则匹配结果"""
    rule_name: str
    prediction: str  # 让方不输 / 受让方不输 / 让方必赢
    accuracy: float
    sample_size: int
    confidence: str  # high / medium / low
    

class RulePredictor:
    """规则预测器"""
    
    def __init__(self):
        self.db = get_connection()
        
    def load_upcoming_matches(self, days: int = 3) -> List[Dict]:
        """加载未来比赛"""
        query = '''
            SELECT 
                m.match_id, m.home_team_name, m.away_team_name, m.match_time,
                l.league_id, l.name_cn as league_name,
                oar.initial_home_range, oar.initial_away_range, oar.initial_draw_range,
                oar.current_home_range, oar.current_away_range, oar.current_draw_range,
                oar.initial_rule_diff, oar.current_rule_diff, oar.power_diff,
                eo.initial_home, eo.initial_draw, eo.initial_away,
                eo.current_home, eo.current_draw, eo.current_away,
                eo.kelly_home, eo.kelly_draw, eo.kelly_away
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            JOIN odds_analysis_results oar ON m.match_id = oar.match_id AND oar.company_id = %s
            JOIN european_odds eo ON m.match_id = eo.match_id AND eo.company_id = %s
            WHERE m.match_status = 'scheduled'
              AND m.match_time >= NOW()
              AND m.match_time <= DATE_ADD(NOW(), INTERVAL %s DAY)
            ORDER BY m.match_time
        '''
        
        return self.db.execute_query(query, (COMPANY_ID, COMPANY_ID, days), fetch='all')
    
    def process_match(self, row: Dict) -> Dict:
        """处理单场比赛数据"""
        init_home = float(row['initial_home'])
        init_away = float(row['initial_away'])
        curr_home = float(row['current_home'])
        curr_away = float(row['current_away'])
        init_draw = float(row['initial_draw'])
        curr_draw = float(row['current_draw'])
        
        # 判断让球方
        if init_home <= init_away:
            handicap_side = 'home'
            handicap_team = row['home_team_name']
            receiver_team = row['away_team_name']
            init_h_range = row['initial_home_range']
            init_r_range = row['initial_away_range']
            curr_h_range = row['current_home_range']
            curr_r_range = row['current_away_range']
            init_h_odds, init_r_odds = init_home, init_away
            curr_h_odds, curr_r_odds = curr_home, curr_away
            kelly_h = float(row['kelly_home']) if row['kelly_home'] else None
            kelly_r = float(row['kelly_away']) if row['kelly_away'] else None
        else:
            handicap_side = 'away'
            handicap_team = row['away_team_name']
            receiver_team = row['home_team_name']
            init_h_range = row['initial_away_range']
            init_r_range = row['initial_home_range']
            curr_h_range = row['current_away_range']
            curr_r_range = row['current_home_range']
            init_h_odds, init_r_odds = init_away, init_home
            curr_h_odds, curr_r_odds = curr_away, curr_home
            kelly_h = float(row['kelly_away']) if row['kelly_away'] else None
            kelly_r = float(row['kelly_home']) if row['kelly_home'] else None
        
        return {
            'match_id': row['match_id'],
            'match_time': row['match_time'],
            'league_id': row['league_id'],
            'league_name': row['league_name'],
            'home_team': row['home_team_name'],
            'away_team': row['away_team_name'],
            'handicap_team': handicap_team,
            'receiver_team': receiver_team,
            'handicap_side': handicap_side,
            'is_big5': row['league_id'] in BIG5_LEAGUE_IDS,
            
            # 盘型
            'init_h_type': get_range_type(init_h_range),
            'init_r_type': get_range_type(init_r_range),
            'curr_h_type': get_range_type(curr_h_range),
            'curr_r_type': get_range_type(curr_r_range),
            'init_home_type': get_range_type(row['initial_home_range']),
            'init_away_type': get_range_type(row['initial_away_range']),
            'init_draw_range': row['initial_draw_range'],
            
            # 赔率变化
            'h_odds_change': classify_odds_change(init_h_odds, curr_h_odds),
            'r_odds_change': classify_odds_change(init_r_odds, curr_r_odds),
            
            # Kelly
            'kelly_h': classify_kelly(kelly_h),
            'kelly_r': classify_kelly(kelly_r),
            
            # 力量差 & 规则差
            'power_diff': float(row['power_diff']) if row['power_diff'] else None,
            'power_class': classify_power_diff(float(row['power_diff']) if row['power_diff'] else None),
            'init_rule_diff': float(row['initial_rule_diff']) if row['initial_rule_diff'] else None,
            'init_rule_class': classify_rule_diff(float(row['initial_rule_diff']) if row['initial_rule_diff'] else None),
        }
    
    def check_rules(self, m: Dict) -> List[RuleMatch]:
        """检查所有规则"""
        matches = []
        
        # === 金牌规则 ===
        
        # 规则1: 让方赔率降+受让方赔率升 → 让方不输 (82.1%, 805场)
        if m['h_odds_change'] == '降' and m['r_odds_change'] == '升':
            matches.append(RuleMatch(
                rule_name='让方赔率降+受让方赔率升',
                prediction='让方不输',
                accuracy=0.821,
                sample_size=805,
                confidence='high'
            ))
        
        # 规则2: 初双实开→即时让高受低 → 让方不输 (83.3%, 42场)
        if (m['init_h_type'] == '实开' and m['init_r_type'] == '实开' and
            m['curr_h_type'] == '高开' and m['curr_r_type'] == '低开'):
            matches.append(RuleMatch(
                rule_name='初双实开→即时让高受低',
                prediction='让方不输',
                accuracy=0.833,
                sample_size=42,
                confidence='high'
            ))
        
        # 规则3: 初双实开+低开平 → 让方不输 (77.9%, 272场)
        if (m['init_home_type'] == '实开' and m['init_away_type'] == '实开' and
            m['init_draw_range'] and m['init_draw_range'].startswith('低开平')):
            matches.append(RuleMatch(
                rule_name='初双实开+低开平',
                prediction='让方不输',
                accuracy=0.779,
                sample_size=272,
                confidence='high'
            ))
        
        # 规则4: 让方低Kelly → 让方不输 (90.9%, 11场)
        if m['kelly_h'] == '低Kelly':
            matches.append(RuleMatch(
                rule_name='让方低Kelly',
                prediction='让方不输',
                accuracy=0.909,
                sample_size=11,
                confidence='medium'  # 样本较少
            ))
        
        # === 银牌规则 (二维交叉) ===
        
        # 力量差=强让 + 初盘规则差=大负 → 让方不输 (98.0%, 50场)
        if m['power_class'] == '强让' and m['init_rule_class'] == '大负':
            matches.append(RuleMatch(
                rule_name='强让+初盘规则差大负',
                prediction='让方不输',
                accuracy=0.980,
                sample_size=50,
                confidence='high'
            ))
        
        # 即时受让方盘型=韬光 + 力量差=强让 → 让方不输 (94.3%, 175场)
        if m['curr_r_type'] == '韬光' and m['power_class'] == '强让':
            matches.append(RuleMatch(
                rule_name='即时受让方韬光+强让',
                prediction='让方不输',
                accuracy=0.943,
                sample_size=175,
                confidence='high'
            ))
        
        # 即时让方盘型=超实 + 力量差=强让 → 让方不输 (93.5%, 170场)
        if m['curr_h_type'] == '超实' and m['power_class'] == '强让':
            matches.append(RuleMatch(
                rule_name='即时让方超实+强让',
                prediction='让方不输',
                accuracy=0.935,
                sample_size=170,
                confidence='high'
            ))
        
        # 即时让方盘型=超深 + 力量差=强受 → 让方不输 (92.9%, 56场)
        if m['curr_h_type'] == '超深' and m['power_class'] == '强受':
            matches.append(RuleMatch(
                rule_name='即时让方超深+强受',
                prediction='让方不输',
                accuracy=0.929,
                sample_size=56,
                confidence='high'
            ))
        
        # 即时让方盘型=超深 + 即时受让方盘型=超韬 → 让方不输 (91.6%, 107场)
        if m['curr_h_type'] == '超深' and m['curr_r_type'] == '超韬':
            matches.append(RuleMatch(
                rule_name='即时让方超深+受让方超韬',
                prediction='让方不输',
                accuracy=0.916,
                sample_size=107,
                confidence='high'
            ))
        
        # 受让方赔率变化=升 + 力量差=强让 → 让方不输 (91.5%, 246场)
        if m['r_odds_change'] == '升' and m['power_class'] == '强让':
            matches.append(RuleMatch(
                rule_name='受让方赔率升+强让',
                prediction='让方不输',
                accuracy=0.915,
                sample_size=246,
                confidence='high'
            ))
        
        # 力量差=强让 + 初盘规则差=小负 → 让方不输 (91.4%, 221场)
        if m['power_class'] == '强让' and m['init_rule_class'] == '小负':
            matches.append(RuleMatch(
                rule_name='强让+初盘规则差小负',
                prediction='让方不输',
                accuracy=0.914,
                sample_size=221,
                confidence='high'
            ))
        
        # 即时让方盘型=超散 + 让方赔率变化=降 → 让方不输 (90.8%, 98场)
        if m['curr_h_type'] == '超散' and m['h_odds_change'] == '降':
            matches.append(RuleMatch(
                rule_name='即时让方超散+让方赔率降',
                prediction='让方不输',
                accuracy=0.908,
                sample_size=98,
                confidence='high'
            ))
        
        # 力量差=强让 + 五大联赛=True → 让方不输 (89.9%, 189场)
        if m['power_class'] == '强让' and m['is_big5']:
            matches.append(RuleMatch(
                rule_name='强让+五大联赛',
                prediction='让方不输',
                accuracy=0.899,
                sample_size=189,
                confidence='high'
            ))
        
        # === 受让方规则 ===
        
        # 即时让方韬光盘 → 受让方不输 (65.6%, 253场) - 准确率一般但样本大
        if m['curr_h_type'] == '韬光':
            matches.append(RuleMatch(
                rule_name='即时让方韬光盘',
                prediction='受让方不输',
                accuracy=0.656,
                sample_size=253,
                confidence='low'
            ))
        
        # 即时让方超韬盘 → 受让方不输 (70.0%, 70场)
        if m['curr_h_type'] == '超韬':
            matches.append(RuleMatch(
                rule_name='即时让方超韬盘',
                prediction='受让方不输',
                accuracy=0.700,
                sample_size=70,
                confidence='medium'
            ))
        
        return matches
    
    def predict(self, days: int = 3):
        """执行预测"""
        print("=" * 100)
        print("🎯 基于挖掘规则的比赛预测")
        print("=" * 100)
        print(f"预测范围: 未来 {days} 天")
        print(f"数据来源: 威廉公司 (company_id={COMPANY_ID})")
        print()
        
        matches = self.load_upcoming_matches(days)
        print(f"✅ 加载 {len(matches)} 场待预测比赛")
        print()
        
        if not matches:
            print("没有找到待预测的比赛")
            return
        
        # 按命中规则数量排序
        predictions = []
        
        for row in matches:
            m = self.process_match(row)
            rule_matches = self.check_rules(m)
            
            if rule_matches:
                predictions.append({
                    'match': m,
                    'rules': rule_matches,
                })
        
        # 按规则数量和平均准确率排序
        predictions.sort(key=lambda x: (
            -len(x['rules']),
            -sum(r.accuracy for r in x['rules']) / len(x['rules'])
        ))
        
        # 输出结果
        print("=" * 100)
        print("【高置信度预测】命中多条高准确率规则")
        print("=" * 100)
        
        high_conf_count = 0
        for pred in predictions:
            m = pred['match']
            rules = pred['rules']
            
            # 只显示高置信度预测（命中2+规则或有95%+准确率规则）
            high_acc_rules = [r for r in rules if r.accuracy >= 0.90]
            
            if len(rules) >= 2 or high_acc_rules:
                high_conf_count += 1
                tag = '🏆' if m['is_big5'] else '⚽'
                
                # 统计预测方向
                handicap_votes = sum(1 for r in rules if '让方' in r.prediction)
                receiver_votes = sum(1 for r in rules if '受让方' in r.prediction)
                
                if handicap_votes > receiver_votes:
                    final_prediction = f"让方({m['handicap_team']})不输"
                    vote_info = f"让方:{handicap_votes}票 vs 受让方:{receiver_votes}票"
                elif receiver_votes > handicap_votes:
                    final_prediction = f"受让方({m['receiver_team']})不输"
                    vote_info = f"受让方:{receiver_votes}票 vs 让方:{handicap_votes}票"
                else:
                    final_prediction = "规则冲突，建议观望"
                    vote_info = f"让方:{handicap_votes}票 vs 受让方:{receiver_votes}票"
                
                avg_acc = sum(r.accuracy for r in rules) / len(rules)
                
                print()
                print(f"{tag} {m['match_time']} | {m['league_name']}")
                print(f"   {m['home_team']} vs {m['away_team']}")
                print(f"   让球方: {m['handicap_team']}")
                print(f"   盘型: 初[{m['init_h_type']},{m['init_r_type']}] → 即[{m['curr_h_type']},{m['curr_r_type']}]")
                print(f"   赔率变化: 让方{m['h_odds_change']} 受让方{m['r_odds_change']} | 力量差:{m['power_class']} | Kelly:{m['kelly_h']}")
                print(f"   ──────────────────────────────────────────────")
                print(f"   📊 命中 {len(rules)} 条规则 | 平均准确率: {avg_acc*100:.1f}%")
                
                for rule in sorted(rules, key=lambda x: -x.accuracy):
                    conf_icon = '🔥' if rule.confidence == 'high' else ('⚠️' if rule.confidence == 'medium' else '❓')
                    print(f"      {conf_icon} {rule.rule_name} → {rule.prediction} [{rule.accuracy*100:.1f}%, {rule.sample_size}场]")
                
                print(f"   ──────────────────────────────────────────────")
                print(f"   🎯 预测: {final_prediction} ({vote_info})")
        
        print()
        print("=" * 100)
        print(f"共 {high_conf_count} 场高置信度预测")
        print()
        
        # 所有命中规则的比赛
        print("=" * 100)
        print("【所有命中规则的比赛】")
        print("=" * 100)
        
        for pred in predictions:
            m = pred['match']
            rules = pred['rules']
            
            tag = '🏆' if m['is_big5'] else '⚽'
            best_rule = max(rules, key=lambda x: x.accuracy)
            
            print(f"{tag} {m['match_time'].strftime('%m-%d %H:%M')} | {m['league_name']:<15} | {m['home_team']:<12} vs {m['away_team']:<12} | {best_rule.rule_name} → {best_rule.prediction} [{best_rule.accuracy*100:.0f}%]")
        
        print()
        print(f"总计: {len(predictions)} 场比赛命中规则")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='基于挖掘规则预测未来比赛')
    parser.add_argument('--days', type=int, default=3, help='预测未来多少天的比赛（默认3天）')
    args = parser.parse_args()
    
    predictor = RulePredictor()
    predictor.predict(days=args.days)


if __name__ == '__main__':
    main()
