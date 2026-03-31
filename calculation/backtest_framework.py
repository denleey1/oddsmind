"""
回测评估框架
提供滚动样本外回测、性能指标计算和可视化评估
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import json

logger = logging.getLogger(__name__)


class BacktestFramework:
    """回测评估框架"""
    
    def __init__(self, start_date: str = None, end_date: str = None):
        self.start_date = start_date
        self.end_date = end_date
        self.results = []
        self.predictions = []
        self.actuals = []
    
    def add_prediction(self, match_id: str, match_date: datetime, 
                       predictions: Dict, actual_result: Dict, odds: Dict = None):
        """
        添加单场预测结果
        
        Args:
            match_id: 比赛ID
            match_date: 比赛日期
            predictions: 预测概率 {'p_over25': x, 'p_ge3': y, ...}
            actual_result: 实际结果 {'total_goals': n, ...}
            odds: 实际赔率 {'over25': x, 'under25': y, ...}
        """
        record = {
            'match_id': match_id,
            'match_date': match_date,
            'predictions': predictions,
            'actual': actual_result,
            'odds': odds or {}
        }
        self.results.append(record)
    
    def calculate_log_loss(self, predictions: List[float], actuals: List[int]) -> float:
        """
        计算对数损失
        
        Args:
            predictions: 预测概率列表
            actuals: 实际结果(0/1)列表
        """
        if len(predictions) != len(actuals):
            raise ValueError("预测和实际结果长度不匹配")
        
        epsilon = 1e-15
        predictions = np.clip(predictions, epsilon, 1 - epsilon)
        
        log_loss = -np.mean(actuals * np.log(predictions) + 
                            (1 - actuals) * np.log(1 - predictions))
        return log_loss
    
    def calculate_brier_score(self, predictions: List[float], actuals: List[int]) -> float:
        """
        计算Brier分数
        
        Args:
            predictions: 预测概率列表
            actuals: 实际结果(0/1)列表
        """
        predictions = np.array(predictions)
        actuals = np.array(actuals)
        return np.mean((predictions - actuals) ** 2)
    
    def calculate_rps(self, pred_probs: np.ndarray, actual_class: int, n_classes: int = 3) -> float:
        """
        计算Ranked Probability Score (用于有序多分类，如≤2, =3, ≥4)
        
        Args:
            pred_probs: 预测概率分布 [P(≤2), P(=3), P(≥4)]
            actual_class: 实际类别(0, 1, or 2)
            n_classes: 类别数
        """
        actual_dist = np.zeros(n_classes)
        actual_dist[actual_class] = 1.0
        
        # 累积概率
        pred_cum = np.cumsum(pred_probs)
        actual_cum = np.cumsum(actual_dist)
        
        rps = np.sum((pred_cum - actual_cum) ** 2)
        return rps
    
    def reliability_diagram(self, predictions: List[float], actuals: List[int], 
                           n_bins: int = 10) -> Dict:
        """
        计算可靠性曲线数据
        
        Returns:
            包含bin数据和ECE的字典
        """
        predictions = np.array(predictions)
        actuals = np.array(actuals)
        
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        bin_data = []
        
        ece = 0.0  # Expected Calibration Error
        mce = 0.0  # Maximum Calibration Error
        
        for i in range(n_bins):
            bin_lower = bin_boundaries[i]
            bin_upper = bin_boundaries[i + 1]
            
            in_bin = (predictions > bin_lower) & (predictions <= bin_upper)
            
            if np.sum(in_bin) > 0:
                bin_acc = np.mean(actuals[in_bin])
                bin_conf = np.mean(predictions[in_bin])
                bin_count = np.sum(in_bin)
                bin_prop = bin_count / len(predictions)
                
                calibration_error = abs(bin_conf - bin_acc)
                ece += calibration_error * bin_prop
                mce = max(mce, calibration_error)
                
                bin_data.append({
                    'bin_lower': bin_lower,
                    'bin_upper': bin_upper,
                    'confidence': bin_conf,
                    'accuracy': bin_acc,
                    'count': int(bin_count),
                    'calibration_error': calibration_error
                })
        
        return {
            'bins': bin_data,
            'ece': ece,
            'mce': mce
        }
    
    def calculate_betting_performance(self, threshold: float = 0.05, 
                                     kelly_fraction: float = 0.25) -> Dict:
        """
        计算下注策略表现
        
        Args:
            threshold: 概率差异阈值
            kelly_fraction: 凯利分数
        """
        total_bets = 0
        wins = 0
        total_stake = 0.0
        total_return = 0.0
        bet_records = []
        
        for record in self.results:
            preds = record['predictions']
            actual = record['actual']
            odds_data = record['odds']
            
            # 检查大2.5
            if 'p_over25' in preds and 'over25' in odds_data:
                p_model = preds['p_over25']
                odds_over = odds_data['over25']
                p_market = 1 / odds_over if odds_over > 0 else 0
                
                diff = p_model - p_market
                
                if abs(diff) >= threshold:
                    # 下注
                    total_bets += 1
                    
                    # 凯利准则
                    if diff > 0:  # 看好大球
                        ev = p_model * (odds_over - 1) - (1 - p_model)
                        if ev > 0:
                            stake = kelly_fraction * ev / (odds_over - 1)
                            stake = min(stake, 0.05)  # 最大5%
                            
                            actual_over = 1 if actual.get('total_goals', 0) > 2.5 else 0
                            
                            if actual_over:
                                profit = stake * (odds_over - 1)
                                wins += 1
                            else:
                                profit = -stake
                            
                            total_stake += stake
                            total_return += stake + profit
                            
                            bet_records.append({
                                'match_id': record['match_id'],
                                'date': record['match_date'],
                                'type': 'over2.5',
                                'stake': stake,
                                'profit': profit,
                                'p_model': p_model,
                                'p_market': p_market,
                                'odds': odds_over
                            })
        
        if total_bets == 0:
            return {'total_bets': 0, 'roi': 0, 'win_rate': 0}
        
        roi = (total_return - total_stake) / total_stake if total_stake > 0 else 0
        win_rate = wins / total_bets
        
        # 计算夏普比率(假设独立)
        if bet_records:
            returns = [b['profit'] / b['stake'] for b in bet_records]
            sharpe = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
        else:
            sharpe = 0
        
        return {
            'total_bets': total_bets,
            'wins': wins,
            'win_rate': win_rate,
            'total_stake': total_stake,
            'total_return': total_return,
            'net_profit': total_return - total_stake,
            'roi': roi,
            'sharpe_ratio': sharpe,
            'bet_records': bet_records
        }
    
    def rolling_window_backtest(self, train_window_days: int = 90, 
                                test_window_days: int = 14) -> List[Dict]:
        """
        滚动窗口回测
        
        Args:
            train_window_days: 训练窗口天数
            test_window_days: 测试窗口天数
        
        Returns:
            每个窗口的评估结果列表
        """
        if not self.results:
            return []
        
        # 按日期排序
        sorted_results = sorted(self.results, key=lambda x: x['match_date'])
        
        # 确定日期范围
        start_date = sorted_results[0]['match_date']
        end_date = sorted_results[-1]['match_date']
        
        windows = []
        current_date = start_date + timedelta(days=train_window_days)
        
        while current_date + timedelta(days=test_window_days) <= end_date:
            train_start = current_date - timedelta(days=train_window_days)
            train_end = current_date
            test_start = current_date
            test_end = current_date + timedelta(days=test_window_days)
            
            # 划分训练集和测试集
            train_set = [r for r in sorted_results 
                        if train_start <= r['match_date'] < train_end]
            test_set = [r for r in sorted_results 
                       if test_start <= r['match_date'] < test_end]
            
            if len(test_set) < 5:  # 测试集太小，跳过
                current_date += timedelta(days=test_window_days)
                continue
            
            # 评估测试集
            window_result = self._evaluate_window(train_set, test_set)
            window_result['train_start'] = train_start
            window_result['train_end'] = train_end
            window_result['test_start'] = test_start
            window_result['test_end'] = test_end
            
            windows.append(window_result)
            
            # 移动窗口
            current_date += timedelta(days=test_window_days)
        
        return windows
    
    def _evaluate_window(self, train_set: List[Dict], test_set: List[Dict]) -> Dict:
        """评估单个窗口"""
        # 提取测试集预测和实际
        predictions_over25 = []
        actuals_over25 = []
        
        for record in test_set:
            if 'p_over25' in record['predictions']:
                predictions_over25.append(record['predictions']['p_over25'])
                actual = 1 if record['actual'].get('total_goals', 0) > 2.5 else 0
                actuals_over25.append(actual)
        
        if not predictions_over25:
            return {'error': 'No valid predictions'}
        
        # 计算指标
        log_loss = self.calculate_log_loss(predictions_over25, actuals_over25)
        brier = self.calculate_brier_score(predictions_over25, actuals_over25)
        reliability = self.reliability_diagram(predictions_over25, actuals_over25, n_bins=5)
        
        return {
            'n_test': len(test_set),
            'log_loss': round(log_loss, 6),
            'brier_score': round(brier, 6),
            'ece': round(reliability['ece'], 6),
            'mce': round(reliability['mce'], 6)
        }
    
    def generate_report(self, output_path: str = None) -> Dict:
        """生成完整评估报告"""
        if not self.results:
            return {'error': 'No results to evaluate'}
        
        # 提取所有预测
        preds_over25 = []
        actuals_over25 = []
        preds_3class = []  # [P(≤2), P(=3), P(≥4)]
        actuals_3class = []
        
        for record in self.results:
            total_goals = record['actual'].get('total_goals', 0)
            
            # 大2.5
            if 'p_over25' in record['predictions']:
                preds_over25.append(record['predictions']['p_over25'])
                actuals_over25.append(1 if total_goals > 2.5 else 0)
            
            # 三分类
            if all(k in record['predictions'] for k in ['p_le2', 'p_eq3', 'p_ge4']):
                preds_3class.append([
                    record['predictions']['p_le2'],
                    record['predictions']['p_eq3'],
                    record['predictions']['p_ge4']
                ])
                
                if total_goals <= 2:
                    actuals_3class.append(0)
                elif total_goals == 3:
                    actuals_3class.append(1)
                else:
                    actuals_3class.append(2)
        
        report = {
            'summary': {
                'total_matches': len(self.results),
                'date_range': {
                    'start': str(min(r['match_date'] for r in self.results)),
                    'end': str(max(r['match_date'] for r in self.results))
                }
            }
        }
        
        # 大2.5评估
        if preds_over25:
            log_loss_25 = self.calculate_log_loss(preds_over25, actuals_over25)
            brier_25 = self.calculate_brier_score(preds_over25, actuals_over25)
            reliability_25 = self.reliability_diagram(preds_over25, actuals_over25)
            
            report['over25_metrics'] = {
                'log_loss': round(log_loss_25, 6),
                'brier_score': round(brier_25, 6),
                'ece': round(reliability_25['ece'], 6),
                'mce': round(reliability_25['mce'], 6),
                'reliability_bins': reliability_25['bins']
            }
        
        # 三分类评估
        if preds_3class:
            rps_scores = [self.calculate_rps(np.array(p), a) 
                         for p, a in zip(preds_3class, actuals_3class)]
            
            report['three_class_metrics'] = {
                'mean_rps': round(np.mean(rps_scores), 6),
                'std_rps': round(np.std(rps_scores), 6)
            }
        
        # 下注表现
        betting_perf = self.calculate_betting_performance()
        report['betting_performance'] = betting_perf
        
        # 输出到文件
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"报告已保存到: {output_path}")
        
        return report


def run_backtest_example():
    """运行示例回测"""
    print("=== 回测框架示例 ===\n")
    
    # 创建模拟数据
    np.random.seed(42)
    bt = BacktestFramework()
    
    for i in range(200):
        match_date = datetime.now() - timedelta(days=200-i)
        true_prob = 0.5
        
        # 模拟预测(略有偏差)
        p_model = np.clip(true_prob + np.random.normal(0, 0.15), 0.1, 0.9)
        
        # 实际结果
        actual_over = np.random.binomial(1, true_prob)
        total_goals = 3 if actual_over else 2
        
        # 市场赔率
        p_market = true_prob + np.random.normal(0, 0.05)
        odds_over = 1 / np.clip(p_market, 0.1, 0.9)
        
        bt.add_prediction(
            match_id=f"match_{i}",
            match_date=match_date,
            predictions={'p_over25': p_model},
            actual_result={'total_goals': total_goals},
            odds={'over25': odds_over}
        )
    
    # 生成报告
    report = bt.generate_report()
    
    print("整体评估:")
    print(f"  样本数: {report['summary']['total_matches']}")
    if 'over25_metrics' in report:
        print(f"  Log Loss: {report['over25_metrics']['log_loss']:.4f}")
        print(f"  Brier Score: {report['over25_metrics']['brier_score']:.4f}")
        print(f"  ECE: {report['over25_metrics']['ece']:.4f}")
    
    print(f"\n下注表现:")
    perf = report['betting_performance']
    print(f"  总下注数: {perf['total_bets']}")
    print(f"  胜率: {perf['win_rate']:.2%}")
    print(f"  ROI: {perf['roi']:.2%}")
    if 'sharpe_ratio' in perf:
        print(f"  夏普比率: {perf['sharpe_ratio']:.3f}")
    
    # 滚动窗口回测
    print(f"\n滚动窗口回测:")
    windows = bt.rolling_window_backtest(train_window_days=60, test_window_days=14)
    
    if windows:
        avg_log_loss = np.mean([w['log_loss'] for w in windows if 'log_loss' in w])
        avg_brier = np.mean([w['brier_score'] for w in windows if 'brier_score' in w])
        print(f"  窗口数: {len(windows)}")
        print(f"  平均Log Loss: {avg_log_loss:.4f}")
        print(f"  平均Brier: {avg_brier:.4f}")


if __name__ == "__main__":
    run_backtest_example()







