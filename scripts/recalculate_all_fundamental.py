#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量重算所有基本面数据（新信心值引擎 v3.0）

用法：
  python scripts/recalculate_all_fundamental.py           # 全量重算
  python scripts/recalculate_all_fundamental.py --pending  # 只算未更新的
  python scripts/recalculate_all_fundamental.py --limit 100 # 最多算100场
"""

import sys
import time
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.logger import get_logger
from app_database import execute_query
from fundamental_analysis.confidence_engine import ConfidenceEngine
from application.services.fundamental_analysis_service import FundamentalAnalysisService

logger = get_logger('recalculate_fundamental')


def main():
    parser = argparse.ArgumentParser(description='批量重算基本面数据')
    parser.add_argument('--pending', action='store_true', help='只处理未更新的记录')
    parser.add_argument('--limit', type=int, default=0, help='最大处理数量（0=不限）')
    parser.add_argument('--delay', type=float, default=3.0, help='每次抓取间隔秒数（默认3秒）')
    args = parser.parse_args()

    # 获取待处理的 match_id
    if args.pending:
        sql = "SELECT DISTINCT match_id FROM fundamental_analysis WHERE pull_direction IS NULL ORDER BY match_id DESC"
    else:
        sql = "SELECT DISTINCT match_id FROM fundamental_analysis ORDER BY match_id DESC"

    rows = execute_query(sql)
    if not rows:
        print("没有需要处理的记录")
        return

    match_ids = [str(r['match_id']) for r in rows]
    if args.limit > 0:
        match_ids = match_ids[:args.limit]

    total = len(match_ids)
    print(f"准备处理 {total} 场比赛，间隔 {args.delay}秒/场")
    print(f"预计耗时: {total * args.delay / 60:.0f} 分钟")
    print()

    engine = ConfidenceEngine()
    svc = FundamentalAnalysisService()

    # 优先用本地快照
    snapshot_dir = PROJECT_ROOT / 'logs' / 'html_snapshots'
    snapshot_map = {}
    if snapshot_dir.exists():
        for f in snapshot_dir.glob('analysis_*.html'):
            if f.stat().st_size > 50000:
                mid = f.stem.replace('analysis_', '')
                snapshot_map[mid] = f

    success = 0
    fail = 0
    skip = 0

    for i, match_id in enumerate(match_ids):
        try:
            # 优先本地快照
            if match_id in snapshot_map:
                html = snapshot_map[match_id].read_text(encoding='utf-8', errors='ignore')
                result = engine.analyze_html(html, match_id)
            else:
                result = engine.analyze(match_id, save_html=True)
                time.sleep(args.delay)

            if result:
                svc._persist_analysis(match_id, result)
                success += 1
                if (i + 1) % 50 == 0:
                    print(f"[{i+1}/{total}] 已完成 {success} 场，失败 {fail} 场")
            else:
                fail += 1
                logger.warning(f"比赛 {match_id} 分析失败")

        except Exception as e:
            fail += 1
            logger.error(f"比赛 {match_id} 出错: {e}")

    print(f"\n完成！成功: {success}, 失败: {fail}, 总计: {total}")


if __name__ == '__main__':
    main()
