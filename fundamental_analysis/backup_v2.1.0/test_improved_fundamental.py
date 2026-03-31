#!/usr/bin/env python3
"""
基本面算法改进测试

原始算法核心逻辑:
1. 主队近10场联赛 → 胜3分+平1分+负0分 → 标准化到0-10
2. 客队近10场联赛 → 同上
3. 主队主场(从近10场筛选) → 同上
4. 客队客场(从近10场筛选) → 同上
5. 历史交锋近6场 → 双方得分
6. 平局 = 10 - |主-客|
7. 最终 = 0.3×近况 + 0.4×主客场 + 0.3×交锋

改进点:
1. 时间衰减: 近5场权重1.0，6-10场0.7
2. 平局计算: 基于历史平局率 + 接近度
3. 主客场独立取样: 各取10场
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FundamentalComparison:
    """对比原始算法和改进算法"""
    
    def __init__(self):
        pass
    
    # ========== 原始算法 ==========
    def original_score(self, wins, draws, losses):
        """原始得分计算: 胜3+平1+负0，标准化到0-10"""
        total = wins + draws + losses
        if total == 0:
            return 0
        score = wins * 3 + draws * 1
        max_score = total * 3
        return (score / max_score) * 10
    
    def original_draw(self, home_rating, away_rating):
        """原始平局: 10 - |主-客|"""
        return 10 - abs(home_rating - away_rating)
    
    # ========== 改进算法 ==========
    def improved_score(self, matches_results):
        """
        改进得分: 时间衰减
        matches_results: 按时间倒序的比赛结果列表 ['W','D','L',...]
        """
        if not matches_results:
            return 0
        
        weighted_score = 0
        total_weight = 0
        
        for i, result in enumerate(matches_results):
            weight = 1.0 if i < 5 else 0.7  # 近5场权重1.0，6-10场0.7
            
            if result == 'W':
                base = 3
            elif result == 'D':
                base = 1
            else:
                base = 0
            
            weighted_score += base * weight
            total_weight += weight
        
        max_weighted = total_weight * 3
        return (weighted_score / max_weighted) * 10 if max_weighted > 0 else 0
    
    def improved_draw(self, home_rating, away_rating, home_draw_rate, away_draw_rate, h2h_draw_rate):
        """
        改进平局: 接近度 + 历史平局率
        """
        # 1. 实力接近度
        diff = abs(home_rating - away_rating)
        closeness = max(0, 10 - diff * 1.5)
        
        # 2. 双方平局率
        avg_draw_rate = (home_draw_rate + away_draw_rate) / 2
        draw_tendency = avg_draw_rate * 10
        
        # 3. 历史交锋平局率
        h2h_factor = h2h_draw_rate * 10
        
        # 综合
        return closeness * 0.4 + draw_tendency * 0.3 + h2h_factor * 0.3
    
    def compare(self, home_team, away_team, 
                home_recent, away_recent,
                home_home, away_away,
                h2h_home_wins, h2h_draws, h2h_away_wins):
        """
        对比两种算法
        
        Args:
            home_recent: 主队近况结果列表 ['W','D','L',...]
            away_recent: 客队近况结果列表
            home_home: 主队主场结果列表
            away_away: 客队客场结果列表
            h2h_*: 历史交锋胜平负场次
        """
        print("="*80)
        print(f"【{home_team} vs {away_team}】")
        print("="*80)
        
        # 统计
        home_stats = {'W': home_recent.count('W'), 'D': home_recent.count('D'), 'L': home_recent.count('L')}
        away_stats = {'W': away_recent.count('W'), 'D': away_recent.count('D'), 'L': away_recent.count('L')}
        home_home_stats = {'W': home_home.count('W'), 'D': home_home.count('D'), 'L': home_home.count('L')}
        away_away_stats = {'W': away_away.count('W'), 'D': away_away.count('D'), 'L': away_away.count('L')}
        
        print(f"\n{home_team}近{len(home_recent)}场: {home_stats['W']}胜{home_stats['D']}平{home_stats['L']}负")
        print(f"{away_team}近{len(away_recent)}场: {away_stats['W']}胜{away_stats['D']}平{away_stats['L']}负")
        print(f"{home_team}主场{len(home_home)}场: {home_home_stats['W']}胜{home_home_stats['D']}平{home_home_stats['L']}负")
        print(f"{away_team}客场{len(away_away)}场: {away_away_stats['W']}胜{away_away_stats['D']}平{away_away_stats['L']}负")
        h2h_total = h2h_home_wins + h2h_draws + h2h_away_wins
        print(f"历史交锋{h2h_total}场: {home_team}胜{h2h_home_wins}, 平{h2h_draws}, {away_team}胜{h2h_away_wins}")
        
        # ========== 原始算法 ==========
        print("\n" + "-"*40)
        print("【原始算法】")
        print("-"*40)
        
        home_recent_orig = self.original_score(home_stats['W'], home_stats['D'], home_stats['L'])
        away_recent_orig = self.original_score(away_stats['W'], away_stats['D'], away_stats['L'])
        home_home_orig = self.original_score(home_home_stats['W'], home_home_stats['D'], home_home_stats['L'])
        away_away_orig = self.original_score(away_away_stats['W'], away_away_stats['D'], away_away_stats['L'])
        
        # 历史交锋
        h2h_home_score = h2h_home_wins * 3 + h2h_draws * 1
        h2h_away_score = h2h_away_wins * 3 + h2h_draws * 1
        h2h_max = h2h_total * 3 if h2h_total > 0 else 1
        h2h_home_orig = (h2h_home_score / h2h_max) * 10
        h2h_away_orig = (h2h_away_score / h2h_max) * 10
        
        # 平局
        recent_draw_orig = self.original_draw(home_recent_orig, away_recent_orig)
        ha_draw_orig = self.original_draw(home_home_orig, away_away_orig)
        h2h_draw_orig = self.original_draw(h2h_home_orig, h2h_away_orig)
        
        print(f"近况评分: {home_team}={home_recent_orig:.1f}, {away_team}={away_recent_orig:.1f}")
        print(f"主客场评分: {home_team}主场={home_home_orig:.1f}, {away_team}客场={away_away_orig:.1f}")
        print(f"交锋评分: {home_team}={h2h_home_orig:.1f}, {away_team}={h2h_away_orig:.1f}")
        print(f"平局计算: 近况={recent_draw_orig:.1f}, 主客={ha_draw_orig:.1f}, 交锋={h2h_draw_orig:.1f}")
        
        # 最终
        home_win_orig = 0.3 * home_recent_orig + 0.4 * home_home_orig + 0.3 * h2h_home_orig
        away_win_orig = 0.3 * away_recent_orig + 0.4 * away_away_orig + 0.3 * h2h_away_orig
        draw_orig = (0.3 * recent_draw_orig + 0.4 * ha_draw_orig + 0.3 * h2h_draw_orig) * 0.8
        
        print(f"\n原始结果: 主胜={home_win_orig:.1f}, 平局={draw_orig:.1f}, 客胜={away_win_orig:.1f}")
        
        # ========== 改进算法 ==========
        print("\n" + "-"*40)
        print("【改进算法】")
        print("-"*40)
        
        home_recent_impr = self.improved_score(home_recent)
        away_recent_impr = self.improved_score(away_recent)
        home_home_impr = self.improved_score(home_home)
        away_away_impr = self.improved_score(away_away)
        
        print(f"近况评分(时间衰减): {home_team}={home_recent_impr:.1f}, {away_team}={away_recent_impr:.1f}")
        print(f"主客场评分: {home_team}主场={home_home_impr:.1f}, {away_team}客场={away_away_impr:.1f}")
        
        # 平局率
        home_draw_rate = home_stats['D'] / len(home_recent) if home_recent else 0
        away_draw_rate = away_stats['D'] / len(away_recent) if away_recent else 0
        h2h_draw_rate = h2h_draws / h2h_total if h2h_total > 0 else 0
        
        print(f"历史平局率: {home_team}={home_draw_rate*100:.0f}%, {away_team}={away_draw_rate*100:.0f}%, 交锋={h2h_draw_rate*100:.0f}%")
        
        # 改进平局
        draw_impr = self.improved_draw(home_recent_impr, away_recent_impr, 
                                        home_draw_rate, away_draw_rate, h2h_draw_rate)
        
        # 最终
        home_win_impr = 0.3 * home_recent_impr + 0.4 * home_home_impr + 0.3 * h2h_home_orig
        away_win_impr = 0.3 * away_recent_impr + 0.4 * away_away_impr + 0.3 * h2h_away_orig
        
        print(f"\n改进结果: 主胜={home_win_impr:.1f}, 平局={draw_impr:.1f}, 客胜={away_win_impr:.1f}")
        
        # ========== 对比 ==========
        print("\n" + "="*80)
        print("【对比】")
        print("="*80)
        print(f"{'指标':12} | {'原始':>8} | {'改进':>8} | {'差异':>8}")
        print("-"*45)
        print(f"{'主胜拉力':12} | {home_win_orig:>8.1f} | {home_win_impr:>8.1f} | {home_win_impr-home_win_orig:>+8.1f}")
        print(f"{'平局拉力':12} | {draw_orig:>8.1f} | {draw_impr:>8.1f} | {draw_impr-draw_orig:>+8.1f}")
        print(f"{'客胜拉力':12} | {away_win_orig:>8.1f} | {away_win_impr:>8.1f} | {away_win_impr-away_win_orig:>+8.1f}")
        
        return {
            'original': {'home': home_win_orig, 'draw': draw_orig, 'away': away_win_orig},
            'improved': {'home': home_win_impr, 'draw': draw_impr, 'away': away_win_impr}
        }


if __name__ == "__main__":
    comp = FundamentalComparison()
    
    # 示例：阿森纳 vs 利物浦
    # 根据数据库结果反推近似数据
    # 主胜7.3, 平局5.9, 客胜5.6 → 阿森纳表现更好
    
    print("\n" + "#"*80)
    print("# 示例：模拟阿森纳 vs 利物浦的基本面数据")
    print("#"*80)
    
    comp.compare(
        home_team="阿森纳",
        away_team="利物浦",
        # 阿森纳近10场（假设7胜2平1负）
        home_recent=['W','W','W','W','W','L','W','D','W','D'],
        # 利物浦近10场（假设4胜4平2负）
        away_recent=['D','D','W','W','W','D','D','W','L','L'],
        # 阿森纳主场5场（假设全胜）
        home_home=['W','W','W','W','W'],
        # 利物浦客场5场（假设2胜2平1负）
        away_away=['D','D','W','W','L'],
        # 历史交锋（假设近6场）
        h2h_home_wins=2,
        h2h_draws=2,
        h2h_away_wins=2
    )
    
    print("\n\n" + "#"*80)
    print("# 改进效果分析")
    print("#"*80)
    print("""
改进点1: 时间衰减
- 如果阿森纳近5场全胜，6-10场有输：改进后评分会更高
- 如果利物浦近5场有平局：改进后评分会略低

改进点2: 平局计算
- 原始: 10 - |7.7 - 5.3| = 7.6 → 乘0.8 → 6.1
- 改进: 考虑平局率20%和40%，历史交锋33% → 更合理的4-5分

改进点3: 主客场独立取样
- 如果主客场各取10场，样本量更充足
- 避免从近10场筛选导致样本量只有3-4场
""")
