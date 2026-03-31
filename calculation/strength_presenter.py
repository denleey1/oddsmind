#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
展示服务：负责在命令行中以表格形式展示计算结果
"""
import pandas as pd
from typing import Dict, Optional

class StrengthResultPresenter:
    """
    广义实力计算结果的展示服务
    """
    def display(self, team_powers: Dict, league_info: Dict, company_name: str,
                target_round: Optional[int], division: Optional[str] = None):
        """
        在控制台显示计算结果
        """
        if not team_powers:
            print("没有计算结果可显示")
            return

        results_df = self._prepare_dataframe(team_powers)
        
        league_label = league_info['name_cn']
        if division:
            div_names = {'east': '东区', 'west': '西区'}
            league_label += f" ({div_names.get(division, division)})"
        header = f"【{league_label}】| 公司: {company_name}"
        if target_round:
            header += f" | 第{target_round}轮后"
        header += " | 广义实力计算结果"

        print("\n" + "=" * 120)
        print(header)
        print("=" * 120)
        
        print(f"{'排名':<4} {'队伍':<20} {'综合实力':<10} {'相对实力':<10} {'档距':<6} {'档次':<8} {'总场实力':<10} {'近况实力':<10} {'比赛场次':<8}")
        print("-" * 120)
        
        for idx, row in results_df.iterrows():
            rank = idx + 1
            print(f"{rank:<4} {row['team_name']:<20} {row['combined_power']:<10.4f} {row['relative_power']:<10.4f} "
                  f"{row['power_level']:<6.1f} {row['level_class']:<8} {row['total_power']:<10.4f} {row['recent_power']:<10.4f} {row['matches_count']:<8}")
        
        print("=" * 120)
        print(f"计算说明:")
        print(f"- 博彩公司: {company_name}")
        print(f"- 综合实力 = 总场实力 × 0.2 + 近况实力 × 0.8")
        print(f"- 相对实力 = 综合实力 - 最低实力")
        print(f"- 档距 = 相对实力 / 10.5")

    def _prepare_dataframe(self, team_powers: Dict) -> pd.DataFrame:
        """将结果字典转换为用于显示的DataFrame"""
        results_df = pd.DataFrame.from_dict(team_powers, orient='index')
        results_df = results_df.sort_values('combined_power', ascending=False)
        results_df.reset_index(inplace=True)
        results_df.rename(columns={'index': 'team_id'}, inplace=True)
        return results_df