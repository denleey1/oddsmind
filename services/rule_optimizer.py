#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规则优化服务
============
基于回测结果持续优化规则，发现更优质的规则

功能：
1. 分析回测日志，统计每个规则的实际表现
2. 对比理论准确率 vs 实际准确率
3. 从历史数据中挖掘新的优质规则
4. 生成规则优化建议报告
5. 识别需要淘汰的低效规则

使用方式：
1. 分析回测结果: python services/rule_optimizer.py --analyze
2. 挖掘新规则: python services/rule_optimizer.py --mine
3. 生成优化报告: python services/rule_optimizer.py --report
4. 完整流程: python services/rule_optimizer.py --full
"""
import sys
import json
import os
import glob
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import argparse

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger
import pymysql
import pymysql.cursors

# 日志目录
VALIDATION_LOG_DIR = PROJECT_ROOT / 'validation_test' / 'logs' / 'monitor'
# 报告输出目录
REPORTS_DIR = PROJECT_ROOT / 'validation_test' / 'reports' / 'rule_optimization'
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

logger = get_logger(__name__)


class RuleOptimizer:
    """规则优化器"""
    
    def __init__(self):
        try:
            self.db = get_connection()
        except Exception as e:
            # 如果连接失败，尝试直接连接
            self.logger = get_logger(self.__class__.__name__)
            self.logger.warning(f"使用get_connection失败: {e}，尝试直接连接数据库")
            try:
                self.db = pymysql.connect(
                    host='localhost', port=3306,
                    user='root', password=os.environ.get('MYSQL_PASSWORD', ''),
                    database='oddsmind', charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor
                )
            except Exception as e2:
                self.logger.error(f"直接连接数据库也失败: {e2}")
                raise
        else:
            self.logger = get_logger(self.__class__.__name__)
        
    def load_backtest_logs(self, days: int = 30) -> List[Dict]:
        """加载回测日志"""
        records = []
        log_dir = VALIDATION_LOG_DIR
        
        if not log_dir.exists():
            self.logger.warning(f"日志目录不存在: {log_dir}")
            return records
        
        # 加载最近N天的日志
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for log_file in sorted(glob.glob(str(log_dir / '*.json'))):
            try:
                file_date = datetime.fromtimestamp(os.path.getmtime(log_file))
                if file_date < cutoff_date:
                    continue
                    
                with open(log_file, 'r', encoding='utf-8') as f:
                    day_records = json.load(f)
                    records.extend(day_records)
            except Exception as e:
                self.logger.warning(f"加载日志文件失败 {log_file}: {e}")
        
        self.logger.info(f"加载了 {len(records)} 条回测记录")
        return records
    
    def fetch_match_results(self, match_ids: List[int]) -> Dict[int, Dict]:
        """从数据库查询比赛结果"""
        if not match_ids:
            return {}
        
        placeholders = ','.join(['%s'] * len(match_ids))
        query = f"""
            SELECT match_id, home_score, away_score, match_status,
                   home_team_name, away_team_name
            FROM matches
            WHERE match_id IN ({placeholders})
        """
        
        try:
            if hasattr(self.db, 'execute_query'):
                results = self.db.execute_query(query, params=list(match_ids), fetch='all')
            else:
                # 直接使用pymysql连接
                with self.db.cursor() as cursor:
                    cursor.execute(query, list(match_ids))
                    results = cursor.fetchall()
            return {r['match_id']: r for r in results}
        except Exception as e:
            self.logger.error(f"查询比赛结果失败: {e}")
            return {}
    
    def determine_result(self, rec: Dict, match_info: Dict) -> Tuple[Optional[bool], str]:
        """判断预测是否命中"""
        if match_info['match_status'] != 'finished':
            return None, '未完成'
        
        hs = match_info['home_score']
        as_ = match_info['away_score']
        if hs is None or as_ is None:
            return None, '无比分'
        
        score_str = f"{hs}-{as_}"
        
        # 判断让方是主队还是客队
        h_team = rec.get('h_team', '')
        home_team = match_info.get('home_team_name', '')
        
        if h_team == home_team:
            h_score, r_score = hs, as_
        else:
            h_score, r_score = as_, hs
        
        target = rec.get('target', '')
        if target == '让方必赢':
            hit = h_score > r_score
        elif target == '让方不输':
            hit = h_score >= r_score
        elif target == '受让方不输':
            hit = r_score >= h_score
        else:
            hit = None
        
        return hit, score_str
    
    def analyze_rule_performance(self, days: int = 30) -> Dict[str, Dict]:
        """分析规则表现"""
        self.logger.info("=" * 80)
        self.logger.info("开始分析规则表现...")
        self.logger.info("=" * 80)
        
        # 加载回测日志
        records = self.load_backtest_logs(days)
        if not records:
            self.logger.warning("没有找到回测记录")
            return {}
        
        # 去重（同一场比赛同一规则只算一次）
        seen = set()
        unique_records = []
        for rec in records:
            key = (rec.get('match_id'), rec.get('rule'))
            if key not in seen:
                seen.add(key)
                unique_records.append(rec)
        
        self.logger.info(f"去重后: {len(unique_records)} 条记录")
        
        # 查询比赛结果
        match_ids = list(set(r.get('match_id') for r in unique_records if r.get('match_id')))
        results = self.fetch_match_results(match_ids)
        
        # 按规则统计
        rule_stats = defaultdict(lambda: {
            'total': 0,
            'hit': 0,
            'miss': 0,
            'pending': 0,
            'theoretical_accuracy': 0,
            'actual_accuracy': 0,
            'sample_size': 0,
            'target': '',
            'details': []
        })
        
        for rec in unique_records:
            rule_name = rec.get('rule', '未知规则')
            target = rec.get('target', '')
            theoretical_acc = rec.get('accuracy', 0)  # 理论准确率（百分比）
            sample = rec.get('sample', 0)
            
            stats = rule_stats[rule_name]
            stats['target'] = target
            stats['theoretical_accuracy'] = theoretical_acc
            stats['sample_size'] = sample
            
            match_id = rec.get('match_id')
            match_info = results.get(match_id) if match_id else None
            
            if not match_info:
                hit, score = None, '未知'
            else:
                hit, score = self.determine_result(rec, match_info)
            
            stats['total'] += 1
            
            detail = {
                'match_id': match_id,
                'match_time': rec.get('match_time', ''),
                'league': rec.get('league', ''),
                'home': rec.get('home_team', ''),
                'away': rec.get('away_team', ''),
                'score': score,
                'hit': hit,
            }
            
            if hit is None:
                stats['pending'] += 1
            elif hit:
                stats['hit'] += 1
            else:
                stats['miss'] += 1
            
            stats['details'].append(detail)
        
        # 计算实际准确率
        for rule_name, stats in rule_stats.items():
            decided = stats['hit'] + stats['miss']
            if decided > 0:
                stats['actual_accuracy'] = (stats['hit'] / decided) * 100
            else:
                stats['actual_accuracy'] = 0
        
        self.logger.info(f"分析了 {len(rule_stats)} 个规则")
        return dict(rule_stats)
    
    def generate_performance_report(self, rule_stats: Dict[str, Dict], output_file: Optional[Path] = None) -> str:
        """生成规则表现报告"""
        if not rule_stats:
            return "没有规则统计数据"
        
        # 按实际准确率排序
        sorted_rules = sorted(
            rule_stats.items(),
            key=lambda x: (x[1]['actual_accuracy'], x[1]['total']),
            reverse=True
        )
        
        report_lines = []
        report_lines.append("=" * 100)
        report_lines.append("规则表现分析报告")
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 100)
        report_lines.append("")
        
        # 优质规则（实际准确率 >= 理论准确率，且样本数 >= 5）
        excellent_rules = []
        # 表现不佳的规则（实际准确率 < 理论准确率 - 10%，且样本数 >= 5）
        poor_rules = []
        # 需要更多样本的规则
        need_more_samples = []
        
        for rule_name, stats in sorted_rules:
            decided = stats['hit'] + stats['miss']
            actual_acc = stats['actual_accuracy']
            theoretical_acc = stats['theoretical_accuracy']
            diff = actual_acc - theoretical_acc
            
            if decided >= 5:
                if actual_acc >= theoretical_acc - 5:  # 实际准确率接近或超过理论值
                    excellent_rules.append((rule_name, stats))
                elif actual_acc < theoretical_acc - 15:  # 实际准确率明显低于理论值
                    poor_rules.append((rule_name, stats))
            else:
                need_more_samples.append((rule_name, stats))
        
        # 优质规则
        report_lines.append("🌟 优质规则（表现良好，建议保留）")
        report_lines.append("-" * 100)
        if excellent_rules:
            report_lines.append(f"{'规则名称':<40} {'目标':<12} {'理论准确率':<12} {'实际准确率':<12} {'样本数':<8} {'命中/总数':<12}")
            report_lines.append("-" * 100)
            for rule_name, stats in excellent_rules[:20]:  # 显示前20个
                report_lines.append(
                    f"{rule_name:<40} {stats['target']:<12} "
                    f"{stats['theoretical_accuracy']:>6.1f}%     {stats['actual_accuracy']:>6.1f}%     "
                    f"{stats['total']:>6}     {stats['hit']}/{stats['total']}"
                )
        else:
            report_lines.append("暂无")
        report_lines.append("")
        
        # 表现不佳的规则
        report_lines.append("⚠️  表现不佳的规则（建议淘汰或调整）")
        report_lines.append("-" * 100)
        if poor_rules:
            report_lines.append(f"{'规则名称':<40} {'目标':<12} {'理论准确率':<12} {'实际准确率':<12} {'样本数':<8} {'命中/总数':<12}")
            report_lines.append("-" * 100)
            for rule_name, stats in poor_rules:
                report_lines.append(
                    f"{rule_name:<40} {stats['target']:<12} "
                    f"{stats['theoretical_accuracy']:>6.1f}%     {stats['actual_accuracy']:>6.1f}%     "
                    f"{stats['total']:>6}     {stats['hit']}/{stats['total']}"
                )
        else:
            report_lines.append("暂无")
        report_lines.append("")
        
        # 需要更多样本
        report_lines.append("📊 需要更多样本的规则（样本数 < 5）")
        report_lines.append("-" * 100)
        if need_more_samples:
            report_lines.append(f"{'规则名称':<40} {'目标':<12} {'理论准确率':<12} {'实际准确率':<12} {'样本数':<8}")
            report_lines.append("-" * 100)
            for rule_name, stats in need_more_samples[:10]:  # 显示前10个
                report_lines.append(
                    f"{rule_name:<40} {stats['target']:<12} "
                    f"{stats['theoretical_accuracy']:>6.1f}%     {stats['actual_accuracy']:>6.1f}%     "
                    f"{stats['total']:>6}"
                )
        else:
            report_lines.append("暂无")
        report_lines.append("")
        
        # 总体统计
        total_rules = len(rule_stats)
        total_matches = sum(s['total'] for s in rule_stats.values())
        total_hit = sum(s['hit'] for s in rule_stats.values())
        total_miss = sum(s['miss'] for s in rule_stats.values())
        total_decided = total_hit + total_miss
        overall_accuracy = (total_hit / total_decided * 100) if total_decided > 0 else 0
        
        report_lines.append("=" * 100)
        report_lines.append("总体统计")
        report_lines.append("-" * 100)
        report_lines.append(f"规则总数: {total_rules}")
        report_lines.append(f"匹配记录总数: {total_matches}")
        report_lines.append(f"已决出结果: {total_decided} (命中: {total_hit}, 未中: {total_miss})")
        report_lines.append(f"总体准确率: {overall_accuracy:.1f}%")
        report_lines.append(f"优质规则数: {len(excellent_rules)}")
        report_lines.append(f"表现不佳规则数: {len(poor_rules)}")
        report_lines.append("=" * 100)
        
        report_text = "\n".join(report_lines)
        
        # 保存到文件
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = REPORTS_DIR / f'rule_performance_{timestamp}.txt'
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        self.logger.info(f"报告已保存到: {output_file}")
        return report_text
    
    def mine_new_rules_from_database(self, min_accuracy: float = 0.85, min_samples: int = 10,
                                     use_time_split: bool = True, train_ratio: float = 0.7) -> List[Dict]:
        """从数据库历史数据中挖掘新的优质规则模式（带防过拟合机制）
        
        Args:
            min_accuracy: 最小准确率阈值
            min_samples: 最小样本数（训练集）
            use_time_split: 是否使用时间序列分割（防止过拟合）
            train_ratio: 训练集比例（用于时间序列分割）
        """
        self.logger.info("=" * 80)
        self.logger.info("开始从数据库挖掘新规则（防过拟合模式）...")
        self.logger.info("=" * 80)
        
        # 查询已完成且有赔率分析结果的比赛
        query = """
            SELECT 
                m.match_id,
                m.home_team_name,
                m.away_team_name,
                m.home_score,
                m.away_score,
                m.match_status,
                m.match_time,
                l.name_cn as league_name,
                oar.current_home_fullwater as curr_home_odds,
                oar.current_draw_fullwater as curr_draw_odds,
                oar.current_away_fullwater as curr_away_odds,
                oar.initial_home_fullwater as init_home_odds,
                oar.initial_draw_fullwater as init_draw_odds,
                oar.initial_away_fullwater as init_away_odds,
                oar.current_home_range as curr_h_range_full,
                oar.current_away_range as curr_r_range_full,
                oar.current_draw_range as curr_draw_full,
                oar.initial_home_range as init_h_range_full,
                oar.initial_away_range as init_r_range_full,
                oar.initial_draw_range as init_draw_full,
                oar.power_diff
            FROM matches m
            INNER JOIN leagues l ON m.league_id = l.league_id
            INNER JOIN odds_analysis_results oar ON m.match_id = oar.match_id
            WHERE m.match_status = 'finished'
              AND m.home_score IS NOT NULL
              AND m.away_score IS NOT NULL
              AND oar.company_id = '115'  -- 威廉公司
              AND m.match_time >= DATE_SUB(NOW(), INTERVAL 180 DAY)  -- 最近180天
            ORDER BY m.match_time ASC  -- 按时间升序，便于分割
            LIMIT 2000
        """
        
        try:
            if hasattr(self.db, 'execute_query'):
                matches = self.db.execute_query(query, fetch='all')
            else:
                # 直接使用pymysql连接
                with self.db.cursor() as cursor:
                    cursor.execute(query)
                    matches = cursor.fetchall()
        except Exception as e:
            self.logger.error(f"查询比赛数据失败: {e}")
            return []
        self.logger.info(f"从数据库加载了 {len(matches)} 场已完成比赛")
        
        if not matches:
            return []
        
        # 时间序列分割：防止过拟合
        if use_time_split and len(matches) > min_samples * 2:
            split_idx = int(len(matches) * train_ratio)
            train_matches = matches[:split_idx]
            test_matches = matches[split_idx:]
            
            self.logger.info(f"时间序列分割: 训练集 {len(train_matches)} 场, 测试集 {len(test_matches)} 场")
            self.logger.info(f"训练集时间范围: {train_matches[0]['match_time']} ~ {train_matches[-1]['match_time']}")
            self.logger.info(f"测试集时间范围: {test_matches[0]['match_time']} ~ {test_matches[-1]['match_time']}")
        else:
            train_matches = matches
            test_matches = []
            self.logger.info("未使用时间序列分割（数据量不足或已禁用）")
        
        # 在训练集上挖掘规则模式
        pattern_stats_train = defaultdict(lambda: {
            'total': 0,
            'hit': 0,
            'miss': 0,
            'target': '',
            'matches': []
        })
        
        for match in train_matches:
            # 计算让方和受让方（基于赔率）
            init_home = float(match.get('init_home_odds', 0) or 0)
            init_away = float(match.get('init_away_odds', 0) or 0)
            
            if init_home <= 0 or init_away <= 0:
                continue
            
            # 让方是赔率较低的一方
            if init_home <= init_away:
                handicap_team = match['home_team_name']
                receiver_team = match['away_team_name']
            else:
                handicap_team = match['away_team_name']
                receiver_team = match['home_team_name']
            
            handicap_value = 0  # 简化处理，不计算具体让球值
            
            # 判断让方是主队还是客队
            if handicap_team == match['home_team_name']:
                h_score, r_score = match['home_score'], match['away_score']
            else:
                h_score, r_score = match['away_score'], match['home_score']
            
            # 提取特征
            curr_h = self._get_range_type(match.get('curr_h_range_full', ''))
            curr_r = self._get_range_type(match.get('curr_r_range_full', ''))
            curr_draw = self._get_range_type(match.get('curr_draw_full', ''))
            init_h = self._get_range_type(match.get('init_h_range_full', ''))
            init_r = self._get_range_type(match.get('init_r_range_full', ''))
            
            # 计算赔率变化
            init_home = float(match.get('init_home_odds', 0) or 0)
            curr_home = float(match.get('curr_home_odds', 0) or 0)
            init_draw = float(match.get('init_draw_odds', 0) or 0)
            curr_draw_odds = float(match.get('curr_draw_odds', 0) or 0)
            
            h_change = self._classify_odds_change(init_home, curr_home) if init_home > 0 else '未知'
            d_change = self._classify_odds_change(init_draw, curr_draw_odds) if init_draw > 0 else '未知'
            
            # 计算力量差
            power_diff = match.get('power_diff', 0)
            power_type = self._classify_power(power_diff)
            
            # 生成规则模式组合（测试不同的特征组合）
            patterns = self._generate_rule_patterns(
                curr_h, curr_r, curr_draw, init_h, init_r,
                h_change, d_change, power_type, handicap_value
            )
            
            # 测试每个模式
            for pattern, target in patterns:
                stats = pattern_stats_train[pattern]
                stats['target'] = target
                
                # 判断是否命中
                hit = False
                if target == '让方必赢':
                    hit = h_score > r_score
                elif target == '让方不输':
                    hit = h_score >= r_score
                elif target == '受让方不输':
                    hit = r_score >= h_score
                
                stats['total'] += 1
                if hit:
                    stats['hit'] += 1
                else:
                    stats['miss'] += 1
                
                stats['matches'].append({
                    'match_id': match['match_id'],
                    'score': f"{match['home_score']}-{match['away_score']}",
                    'hit': hit,
                })
        
        # 在训练集上筛选候选规则（提高阈值，防止过拟合）
        candidate_patterns = []
        for pattern, stats in pattern_stats_train.items():
            decided = stats['hit'] + stats['miss']
            if decided < min_samples:
                continue
            
            train_accuracy = (stats['hit'] / decided) if decided > 0 else 0
            # 训练集准确率要求更高（+5%），以应对测试集可能的下降
            if train_accuracy >= min_accuracy + 0.05:
                candidate_patterns.append({
                    'pattern': pattern,
                    'target': stats['target'],
                    'train_accuracy': train_accuracy,
                    'train_sample': decided,
                    'train_hit': stats['hit'],
                    'train_miss': stats['miss'],
                })
        
        self.logger.info(f"训练集上发现 {len(candidate_patterns)} 个候选规则（准确率 >= {min_accuracy + 0.05:.1%}）")
        
        # 在测试集上验证候选规则（样本外验证）
        if test_matches:
            pattern_stats_test = defaultdict(lambda: {
                'total': 0,
                'hit': 0,
                'miss': 0,
            })
            
            for match in test_matches:
                # 重新计算特征（与训练集相同逻辑）
                handicap_team = match.get('handicap_team_name', '')
                receiver_team = match.get('receiver_team_name', '')
                
                if not handicap_team or not receiver_team:
                    continue
                
                if handicap_team == match['home_team_name']:
                    h_score, r_score = match['home_score'], match['away_score']
                else:
                    h_score, r_score = match['away_score'], match['home_score']
                
                curr_h = self._get_range_type(match.get('curr_h_range_full', ''))
                curr_r = self._get_range_type(match.get('curr_r_range_full', ''))
                curr_draw = self._get_range_type(match.get('curr_draw_full', ''))
                init_h = self._get_range_type(match.get('init_h_range_full', ''))
                
                init_home = match.get('init_home_odds', 0)
                curr_home = match.get('curr_home_odds', 0)
                init_draw = match.get('init_draw_odds', 0)
                curr_draw_odds = match.get('curr_draw_odds', 0)
                
                h_change = self._classify_odds_change(init_home, curr_home) if init_home > 0 else '未知'
                d_change = self._classify_odds_change(init_draw, curr_draw_odds) if init_draw > 0 else '未知'
                
                power_diff = match.get('power_diff', 0)
                power_type = self._classify_power(power_diff)
                handicap_value = match.get('handicap_value', 0)
                
                patterns = self._generate_rule_patterns(
                    curr_h, curr_r, curr_draw, init_h, init_r,
                    h_change, d_change, power_type, handicap_value
                )
                
                for pattern, target in patterns:
                    # 只验证候选规则
                    if not any(c['pattern'] == pattern for c in candidate_patterns):
                        continue
                    
                    stats = pattern_stats_test[pattern]
                    
                    hit = False
                    if target == '让方必赢':
                        hit = h_score > r_score
                    elif target == '让方不输':
                        hit = h_score >= r_score
                    elif target == '受让方不输':
                        hit = r_score >= h_score
                    
                    stats['total'] += 1
                    if hit:
                        stats['hit'] += 1
                    else:
                        stats['miss'] += 1
            
            # 合并训练集和测试集结果
            validated_patterns = []
            for candidate in candidate_patterns:
                pattern = candidate['pattern']
                test_stats = pattern_stats_test.get(pattern, {'total': 0, 'hit': 0, 'miss': 0})
                
                test_total = test_stats['total']
                test_hit = test_stats['hit']
                test_miss = test_stats['miss']
                
                if test_total > 0:
                    test_accuracy = (test_hit / test_total) if test_total > 0 else 0
                    # 测试集准确率必须 >= 最小阈值
                    if test_accuracy >= min_accuracy:
                        # 计算训练集和测试集的准确率差异（过拟合指标）
                        accuracy_diff = candidate['train_accuracy'] - test_accuracy
                        
                        validated_patterns.append({
                            'pattern': pattern,
                            'target': candidate['target'],
                            'train_accuracy': candidate['train_accuracy'],
                            'test_accuracy': test_accuracy,
                            'accuracy_diff': accuracy_diff,  # 过拟合指标：差异越小越好
                            'train_sample': candidate['train_sample'],
                            'test_sample': test_total,
                            'total_sample': candidate['train_sample'] + test_total,
                            'train_hit': candidate['train_hit'],
                            'test_hit': test_hit,
                            'total_hit': candidate['train_hit'] + test_hit,
                        })
                    else:
                        self.logger.debug(f"规则 {pattern} 在测试集上准确率 {test_accuracy:.1%} < {min_accuracy:.1%}，已淘汰")
                else:
                    # 测试集没有样本，标记为需要更多数据
                    self.logger.debug(f"规则 {pattern} 在测试集上无样本，需要更多数据")
            
            # 按测试集准确率和样本数排序（优先考虑测试集表现）
            validated_patterns.sort(
                key=lambda x: (x['test_accuracy'], x['test_sample'], -x['accuracy_diff']),
                reverse=True
            )
            
            self.logger.info(f"经过样本外验证，最终保留 {len(validated_patterns)} 个优质规则")
            return validated_patterns
        else:
            # 没有测试集，直接返回训练集结果（但标记为未验证）
            good_patterns = []
            for candidate in candidate_patterns:
                good_patterns.append({
                    'pattern': candidate['pattern'],
                    'target': candidate['target'],
                    'train_accuracy': candidate['train_accuracy'],
                    'test_accuracy': None,
                    'accuracy_diff': None,
                    'train_sample': candidate['train_sample'],
                    'test_sample': 0,
                    'total_sample': candidate['train_sample'],
                    'train_hit': candidate['train_hit'],
                    'test_hit': 0,
                    'total_hit': candidate['train_hit'],
                    'warning': '未经过样本外验证，建议谨慎使用'
                })
            
            good_patterns.sort(key=lambda x: (x['train_accuracy'], x['train_sample']), reverse=True)
            self.logger.warning(f"未使用测试集验证，返回 {len(good_patterns)} 个候选规则（建议谨慎使用）")
            return good_patterns
    
    def _get_range_type(self, range_str: str) -> str:
        """提取盘面类型"""
        if not range_str:
            return '未知'
        prefixes = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']
        for p in prefixes:
            if range_str.startswith(p):
                return p
        return '其他'
    
    def _classify_odds_change(self, init: float, curr: float) -> str:
        """分类赔率变化"""
        if init <= 0:
            return '未知'
        if curr > init * 1.05:
            return '升'
        elif curr < init * 0.95:
            return '降'
        return '稳'
    
    def _classify_power(self, power_diff: float) -> str:
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
        else:
            return '强受'
    
    def _generate_rule_patterns(self, curr_h, curr_r, curr_draw, init_h, init_r,
                                h_change, d_change, power_type, handicap_value) -> List[Tuple[str, str]]:
        """生成规则模式组合"""
        patterns = []
        
        # 模式1: 即时让方 + 即时受让方 + 平赔变化
        if curr_h and curr_r and d_change:
            patterns.append((f"即时让方={curr_h}+即时受让方={curr_r}+平赔变化={d_change}", '受让方不输'))
            patterns.append((f"即时让方={curr_h}+即时受让方={curr_r}+平赔变化={d_change}", '让方不输'))
        
        # 模式2: 力量差 + 即时让方
        if power_type and curr_h:
            if power_type in ['强让', '微让']:
                patterns.append((f"强让+即时让方={curr_h}", '让方不输'))
            elif power_type in ['强受', '微受']:
                patterns.append((f"强受+即时受让方={curr_r}", '受让方不输'))
        
        # 模式3: 即时让方 + 让方赔率变化
        if curr_h and h_change:
            patterns.append((f"即时让方={curr_h}+让方赔率{h_change}", '受让方不输'))
        
        # 模式4: 初盘即时盘一致性
        if init_h and curr_h:
            if init_h == curr_h:
                patterns.append((f"初盘即时盘一致={curr_h}", '让方不输'))
        
        return patterns
    
    def mine_new_rules_from_backtest(self, min_accuracy: float = 0.85, min_samples: int = 5) -> List[Dict]:
        """从回测数据中挖掘新的优质规则模式（保留原方法作为备用）"""
        return self.mine_new_rules_from_database(min_accuracy, min_samples)
    
    def run_full_optimization(self):
        """运行完整的优化流程"""
        self.logger.info("=" * 80)
        self.logger.info("开始完整规则优化流程")
        self.logger.info("=" * 80)
        
        # 1. 分析规则表现
        rule_stats = self.analyze_rule_performance(days=30)
        
        # 2. 生成表现报告
        report = self.generate_performance_report(rule_stats)
        print("\n" + report)
        
        # 3. 挖掘新规则（使用防过拟合机制）
        new_rules = self.mine_new_rules_from_database(
            min_accuracy=0.85,
            min_samples=15,  # 提高最小样本数要求
            use_time_split=True,  # 启用时间序列分割
            train_ratio=0.7  # 70%训练，30%测试
        )
        if new_rules:
            self.logger.info(f"\n发现 {len(new_rules)} 个经过样本外验证的优质规则:")
            for rule in new_rules[:20]:  # 显示前20个
                if rule.get('test_accuracy') is not None:
                    self.logger.info(
                        f"  {rule['pattern']}: {rule['target']} "
                        f"[训练准确率: {rule['train_accuracy']*100:.1f}%, "
                        f"测试准确率: {rule['test_accuracy']*100:.1f}%, "
                        f"差异: {rule['accuracy_diff']*100:+.1f}%, "
                        f"总样本: {rule['total_sample']}]"
                    )
                else:
                    self.logger.warning(
                        f"  {rule['pattern']}: {rule['target']} "
                        f"[训练准确率: {rule['train_accuracy']*100:.1f}%, "
                        f"样本: {rule['train_sample']}] ⚠️ 未经过样本外验证"
                    )
            
            # 保存新规则到文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_rules_file = REPORTS_DIR / f'new_rules_{timestamp}.json'
            with open(new_rules_file, 'w', encoding='utf-8') as f:
                json.dump(new_rules, f, ensure_ascii=False, indent=2)
            self.logger.info(f"新规则已保存到: {new_rules_file}")
        
        self.logger.info("=" * 80)
        self.logger.info("规则优化流程完成")
        self.logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='规则优化服务')
    parser.add_argument('--analyze', action='store_true', help='分析规则表现')
    parser.add_argument('--mine', action='store_true', help='挖掘新规则')
    parser.add_argument('--report', action='store_true', help='生成优化报告')
    parser.add_argument('--full', action='store_true', help='运行完整优化流程')
    parser.add_argument('--days', type=int, default=30, help='分析最近N天的数据（默认30）')
    parser.add_argument('--min-accuracy', type=float, default=0.85, help='最小准确率阈值（默认0.85）')
    parser.add_argument('--min-samples', type=int, default=15, help='最小样本数（默认15）')
    parser.add_argument('--no-time-split', action='store_true', help='禁用时间序列分割（不推荐）')
    
    args = parser.parse_args()
    
    optimizer = RuleOptimizer()
    
    if args.full:
        optimizer.run_full_optimization()
    elif args.analyze:
        rule_stats = optimizer.analyze_rule_performance(days=args.days)
        print(f"\n分析了 {len(rule_stats)} 个规则")
    elif args.mine:
        new_rules = optimizer.mine_new_rules_from_database(
            min_accuracy=args.min_accuracy,
            min_samples=args.min_samples,
            use_time_split=not args.no_time_split
        )
        print(f"\n挖掘到 {len(new_rules)} 个潜在优质规则")
        if new_rules:
            validated_count = sum(1 for r in new_rules if r.get('test_accuracy') is not None)
            print(f"其中 {validated_count} 个经过样本外验证")
    elif args.report:
        rule_stats = optimizer.analyze_rule_performance(days=args.days)
        report = optimizer.generate_performance_report(rule_stats)
        print("\n" + report)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
