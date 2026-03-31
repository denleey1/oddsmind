#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
信心值计算引擎测试

使用已保存的 HTML 快照验证 ConfidenceDataParser + ConfidenceCalculator 完整流程。
"""

import sys
import json
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fundamental_analysis.confidence_parser import ConfidenceDataParser
from fundamental_analysis.confidence_calculator import ConfidenceCalculator, format_as_legacy_result

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
)
logger = logging.getLogger('TestConfidence')


def test_with_snapshot(html_path: str, match_id: str = ""):
    """用单个 HTML 快照运行完整测试"""
    path = Path(html_path)
    if not path.exists():
        logger.error(f"文件不存在: {path}")
        return None

    html = path.read_text(encoding='utf-8', errors='ignore')
    if not match_id:
        match_id = path.stem.replace('analysis_', '')

    print(f"\n{'='*70}")
    print(f"  测试比赛 ID: {match_id}")
    print(f"  文件: {path.name}")
    print(f"{'='*70}")

    # 第一步：解析
    parser = ConfidenceDataParser()
    parsed = parser.parse(html, match_id)

    print(f"\n📋 基本信息:")
    print(f"   主队: {parsed.home_team}")
    print(f"   客队: {parsed.away_team}")
    print(f"   联赛: {parsed.league}")

    print(f"\n📊 主队统计 ({parsed.home_team}):")
    hs = parsed.home_stats
    print(f"   总胜率: {hs.total_win_rate:.1f}%  |  主场胜率: {hs.home_win_rate:.1f}%")
    print(f"   总赢盘率: {hs.total_win_pan_rate:.1f}%  |  主场赢盘率: {hs.home_win_pan_rate:.1f}%")
    print(f"   主场平均进球: {hs.venue_avg_goal:.2f}  |  主场平均失球: {hs.venue_avg_concede:.2f}")
    print(f"   净胜2球+占比: {hs.win_2plus_rate:.1f}%")
    print(f"   赛程间隔: {hs.days_since_last}天")
    print(f"   缺阵球员: {len(hs.absent_players)}人")
    for p in hs.absent_players:
        print(f"     - {p['name']} ({p['position']}) {p['reason']}")

    print(f"\n📊 客队统计 ({parsed.away_team}):")
    aws = parsed.away_stats
    print(f"   总胜率: {aws.total_win_rate:.1f}%  |  客场胜率: {aws.away_win_rate:.1f}%")
    print(f"   总赢盘率: {aws.total_win_pan_rate:.1f}%  |  客场赢盘率: {aws.away_win_pan_rate:.1f}%")
    print(f"   客场平均进球: {aws.venue_avg_goal:.2f}  |  客场平均失球: {aws.venue_avg_concede:.2f}")
    print(f"   净胜2球+占比: {aws.win_2plus_rate:.1f}%")
    print(f"   赛程间隔: {aws.days_since_last}天")
    print(f"   缺阵球员: {len(aws.absent_players)}人")
    for p in aws.absent_players:
        print(f"     - {p['name']} ({p['position']}) {p['reason']}")

    print(f"\n🤝 历史交锋 ({parsed.h2h.total_matches}场):")
    print(f"   主队胜率: {parsed.h2h.home_win_rate:.1f}%  |  平局率: {parsed.h2h.draw_rate:.1f}%  |  客队胜率: {parsed.h2h.away_win_rate:.1f}%")
    print(f"   主队赢盘率: {parsed.h2h.home_win_pan_rate:.1f}%")

    print(f"\n📅 近况记录:")
    print(f"   主队近况: {len(parsed.home_recent_matches)}场")
    for i, m in enumerate(parsed.home_recent_matches[:3]):
        venue = "主" if m.is_home else "客"
        res = "胜" if m.result > 0 else ("平" if m.result == 0 else "负")
        print(f"     {i+1}. [{venue}] vs {m.opponent} {m.goals_for}-{m.goals_against} ({res})")
    print(f"   客队近况: {len(parsed.away_recent_matches)}场")
    for i, m in enumerate(parsed.away_recent_matches[:3]):
        venue = "主" if m.is_home else "客"
        res = "胜" if m.result > 0 else ("平" if m.result == 0 else "负")
        print(f"     {i+1}. [{venue}] vs {m.opponent} {m.goals_for}-{m.goals_against} ({res})")

    if parsed.parse_errors:
        print(f"\n⚠️  解析警告: {parsed.parse_errors}")

    # 第二步：计算
    calc = ConfidenceCalculator()
    conf = calc.calculate(parsed)

    print(f"\n{'─'*50}")
    print(f"  🎯 信心值计算结果")
    print(f"{'─'*50}")
    print(f"  主队 ({parsed.home_team}): {conf.home_score:.2f} → {conf.home_rating}")
    print(f"  客队 ({parsed.away_team}): {conf.away_score:.2f} → {conf.away_rating}")
    print(f"  平局:                      {conf.draw_score:.2f} → {conf.draw_rating}")
    print(f"  拉力方向: {conf.pull_description}")

    if conf.prompts:
        print(f"\n  📌 人工提示:")
        for p in conf.prompts:
            print(f"    {p}")

    # 计算中间过程
    d = conf.details
    if 'S6' in d:
        print(f"\n  S6 基础分: 主={d['S6']['home_base']:.2f}, 客={d['S6']['away_base']:.2f}")
    if 'S7' in d:
        print(f"  S7 修正系数: 主={d['S7']['home_coeff']}, 客={d['S7']['away_coeff']}")
    if 'S8' in d:
        print(f"  S8 进球质量: 主(攻{d['S8']['home_atk']}×防{d['S8']['home_def']}), 客(攻{d['S8']['away_atk']}×防{d['S8']['away_def']})")
    if 'S9' in d:
        print(f"  S9 赛程修正: 主={d['S9']['home_coeff']}, 客={d['S9']['away_coeff']}")
    if 'S10' in d:
        print(f"  S10 原始信心值: 主={d['S10']['home_confidence_raw']:.2f}, "
              f"客={d['S10']['away_confidence_raw']:.2f}, 平={d['S10']['draw_confidence_raw']:.2f}")

    # 兼容层测试
    legacy = format_as_legacy_result(parsed, conf)
    print(f"\n  ✅ 兼容格式输出: final_scores={legacy['final_scores']}")
    print(f"     推荐结果: {legacy['recommended_outcome']}")
    print(f"     赔率规律: {legacy['odds_patterns'][:3]}...")

    return conf


def run_batch_test(snapshot_dir: str, max_files: int = 5):
    """批量测试多个快照"""
    snap_path = Path(snapshot_dir)
    if not snap_path.exists():
        logger.error(f"快照目录不存在: {snap_path}")
        return

    files = sorted(snap_path.glob('analysis_*.html'))[:max_files]
    print(f"\n📂 批量测试: {len(files)} 个文件")

    results = []
    for f in files:
        try:
            conf = test_with_snapshot(str(f))
            if conf:
                results.append((f.stem, conf))
        except Exception as e:
            logger.error(f"测试 {f.name} 失败: {e}", exc_info=True)

    print(f"\n\n{'='*70}")
    print(f"  📊 批量测试总结 ({len(results)}/{len(files)})")
    print(f"{'='*70}")
    for name, c in results:
        mid = name.replace('analysis_', '')
        print(f"  {mid}: 主={c.home_score:.2f}({c.home_rating}) "
              f"平={c.draw_score:.2f}({c.draw_rating}) "
              f"客={c.away_score:.2f}({c.away_rating}) → {c.pull_description}")


if __name__ == '__main__':
    snapshot_dir = PROJECT_ROOT / 'logs' / 'html_snapshots'

    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            test_with_snapshot(arg)
    else:
        run_batch_test(str(snapshot_dir), max_files=5)
