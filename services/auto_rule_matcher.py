#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动规则匹配服务 — 竞争区间规则引擎 v3.1
==========================================
持续监控比赛，在开赛前自动进行多公司规则匹配。

引擎特点:
  - 支持三种公司组合: 威廉+澳门+立博 / 威廉+澳门 / 威廉+立博
  - 68条经回测验证规则 (D-/T-/WL-/V1- 四大类)
  - 信号分级: 重仓 > 强烈 > 参考
  - 冲突检测 + 共振确认
  - 实时更新: 赔率变化后自动清理过期信号，保证显示最新状态

使用方式:
  1. 前台运行: python services/auto_rule_matcher.py
  2. 后台运行: python services/auto_rule_matcher.py --daemon
  3. 单次检查: python services/auto_rule_matcher.py --once

集成日期: 2026-02-12
"""

import sys
import time
import argparse
import signal
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

# 日志目录（与 check30 脚本共用，便于回测）
VALIDATION_LOG_DIR = PROJECT_ROOT / 'validation_test' / 'logs' / 'monitor'

from database.connection import get_connection

from services.auto_rule_matcher_db_ops import (
    ensure_alert_table as _ensure_alert_table,
    get_all_scheduled_match_ids as _get_all_scheduled_match_ids,
    get_upcoming_match_ids as _get_upcoming_match_ids,
    save_signal_summary as _save_signal_summary,
    _cleanup_stale_rules,
)
from services.auto_rule_matcher_logic_ops import (
    RULES,
    SIGNAL_ICON,
    evaluate_match as _evaluate_match,
)

# ==================== 配置 ====================
CHECK_INTERVAL = 120  # 检查间隔（秒）— 每2分钟检测一次
MATCH_WINDOW_MINUTES = 30  # 检查未来多少分钟内的比赛（赛前30分钟开始）

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==================== 日志保存（用于回测） ====================

def save_match_log(all_hits: List[Dict], check_time: datetime) -> int:
    """保存匹配结果到日志文件（便于回测验证）"""
    os.makedirs(VALIDATION_LOG_DIR, exist_ok=True)

    today = check_time.strftime('%Y-%m-%d')
    log_txt = VALIDATION_LOG_DIR / f'{today}.log'
    log_json = VALIDATION_LOG_DIR / f'{today}.json'

    # 读取已有JSON记录
    existing = []
    if log_json.exists():
        try:
            with open(log_json, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []

    # 已记录的match_id+rule组合（去重）
    seen = set()
    for rec in existing:
        seen.add((rec.get('match_id'), rec.get('rule_id')))

    new_records = []
    for hit in all_hits:
        key = (hit['match_id'], hit['rule_id'])
        if key in seen:
            continue
        seen.add(key)

        rec = {
            'check_time': check_time.strftime('%Y-%m-%d %H:%M:%S'),
            'match_id': hit['match_id'],
            'match_time': str(hit.get('match_time', '')),
            'league': hit.get('league', ''),
            'home_team': hit.get('home_team', ''),
            'away_team': hit.get('away_team', ''),
            'handicap_team': hit.get('handicap_team', ''),
            'receiver_team': hit.get('receiver_team', ''),
            'signal_level': hit.get('signal_level', ''),
            'mode': hit.get('mode', ''),
            'rule_id': hit.get('rule_id', ''),
            'rule_grade': hit.get('rule_grade', ''),
            'rule_desc': hit.get('rule_desc', ''),
            'prediction': hit.get('prediction', ''),
            'result': None,  # 待回测填入
        }
        new_records.append(rec)
        existing.append(rec)

    # 写入JSON
    with open(log_json, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    # 追加写入文本日志
    if new_records:
        with open(log_txt, 'a', encoding='utf-8') as f:
            for rec in new_records:
                f.write(
                    f"[{rec['check_time']}] {rec['match_time']} "
                    f"[{rec['league']}] {rec['home_team']} vs {rec['away_team']} | "
                    f"{rec['signal_level']} [{rec['mode']}] "
                    f">>> {rec['prediction']} | "
                    f"{rec['rule_grade']}-{rec['rule_id']} {rec['rule_desc']}\n"
                )

    return len(new_records)


# ==================== 核心服务 ====================

class AutoRuleMatcher:
    """自动规则匹配服务 — 竞争区间规则引擎 v3.1"""

    def __init__(self):
        self.running = False
        self.total_checked = 0
        self.total_matched = 0
        self.db = None

    def _get_db(self):
        """获取数据库连接"""
        if self.db is None:
            self.db = get_connection()
        return self.db

    def check_matches(self, matches: List[Dict]) -> int:
        """
        检查比赛列表。
        matches: 含 match_id, home_team_name, away_team_name, league_name 等字段的列表
        """
        matched_count = 0
        all_hits = []
        check_time = datetime.now()
        db = self._get_db()

        for match in matches:
            match_id = match['match_id']

            # 使用新引擎评估
            result = _evaluate_match(match_id, db)
            self.total_checked += 1

            signal = result.get('signal', '无信号')
            if signal in ('无信号', '无数据'):
                # 清理该比赛可能存在的旧规则记录（赔率变化后不再触发）
                _cleanup_stale_rules(match_id, [], logger)
                continue

            matched_count += 1
            self.total_matched += 1

            # ---- 日志输出 ----
            feat = result.get('features', {})
            side_cn = result.get('side_cn', '')
            mode = result.get('mode', '')
            mode_cn = {'wml': '三公司', 'wm': '威廉+澳门', 'wl': '威廉+立博'}.get(mode, '')
            triggered = result.get('triggered', [])
            home_is_h = feat.get('home_is_h', True)
            home_name = match.get('home_team_name', str(feat.get('home_team_id', '')))
            away_name = match.get('away_team_name', str(feat.get('away_team_id', '')))

            if home_is_h:
                handicap_team = home_name
                receiver_team = away_name
            else:
                handicap_team = away_name
                receiver_team = home_name

            icon = SIGNAL_ICON.get(signal, '⬜')
            n_s = sum(1 for r in triggered if r['grade'] == 'S')
            n_a = sum(1 for r in triggered if r['grade'] == 'A')
            cross_tag = ' ★共振' if result.get('cross_confirm') else ''
            conflict_tag = ' ⚡冲突' if result.get('conflict') else ''

            logger.info("=" * 70)
            logger.info(
                "%s 【%s】 %s %s",
                icon, signal, side_cn, mode_cn
            )
            logger.info(
                "  [%s] %s vs %s | 开赛: %s",
                match.get('league_name', ''),
                home_name, away_name,
                match.get('match_time', '')
            )
            logger.info(
                "  让方=%s(%.2f)  受让方=%s(%.2f)  赔率差=%.2f",
                handicap_team, feat.get('w_h', 0),
                receiver_team, feat.get('w_r', 0),
                feat.get('w_spread', 0) or 0
            )
            if feat.get('m_h') is not None:
                logger.info(
                    "  澳门: 让方=%.2f 受让方=%.2f 差=%.2f",
                    feat.get('m_h', 0), feat.get('m_r', 0),
                    feat.get('m_spread', 0) or 0
                )
            if feat.get('l_h') is not None:
                logger.info(
                    "  立博: 让方=%.2f 受让方=%.2f 差=%.2f",
                    feat.get('l_h', 0), feat.get('l_r', 0),
                    feat.get('l_spread', 0) or 0
                )
            logger.info(
                "  触发 %d 条规则 (%dS+%dA)%s%s | 分数=%d",
                len(triggered), n_s, n_a,
                cross_tag, conflict_tag,
                result.get('score', 0)
            )

            for t in triggered:
                g = {'S': '★★★', 'A': '★★', 'B': '★'}.get(t['grade'], '')
                logger.info("  %s [%s] %s", g, t['id'], t['desc'])

            # 冲突时也显示另一方向
            if result.get('conflict'):
                other = result.get('triggered_r') if result['side'] == 'H' else result.get('triggered_h')
                other_name = '受让方不输' if result['side'] == 'H' else '让方不输'
                if other:
                    logger.info("  ⚡ 同时触发 %s:", other_name)
                    for t in other:
                        g = {'S': '★★★', 'A': '★★', 'B': '★'}.get(t['grade'], '')
                        logger.info("    %s [%s] %s", g, t['id'], t['desc'])

            # ---- 保存到数据库 ----
            match_info = {
                'home_name': home_name,
                'away_name': away_name,
                'league_name': match.get('league_name', ''),
            }
            saved = _save_signal_summary(match_id, result, match_info, logger)
            logger.info("  已保存 %d 条规则到数据库", saved)

            # ---- 收集日志记录 ----
            for t in triggered:
                all_hits.append({
                    'match_id': match_id,
                    'match_time': match.get('match_time', ''),
                    'league': match.get('league_name', ''),
                    'home_team': home_name,
                    'away_team': away_name,
                    'handicap_team': handicap_team,
                    'receiver_team': receiver_team,
                    'signal_level': signal,
                    'mode': mode,
                    'rule_id': t['id'],
                    'rule_grade': t['grade'],
                    'rule_desc': t['desc'],
                    'prediction': side_cn,
                })

        # ---- 保存回测日志 ----
        if all_hits:
            try:
                saved_count = save_match_log(all_hits, check_time)
                logger.debug(f"已保存 {saved_count} 条匹配记录到回测日志")
            except Exception as e:
                logger.warning(f"保存回测日志失败: {e}")

        return matched_count

    def run_once(self):
        """单次检查所有未开始的比赛"""
        logger.info("=" * 70)
        logger.info("🎯 竞争区间规则引擎 v3.1 — 单次检查")
        logger.info("  规则数量: %d 条 (D-%d T-%d WL-%d)",
                     len(RULES),
                     sum(1 for r in RULES if r['requires'] == 'wm'),
                     sum(1 for r in RULES if r['requires'] == 'wml'),
                     sum(1 for r in RULES if r['requires'] == 'wl'))
        logger.info("=" * 70)

        _ensure_alert_table(logger)

        matches = _get_all_scheduled_match_ids()
        logger.info(f"获取到 {len(matches)} 场待检查比赛")

        matched = self.check_matches(matches)

        logger.info("=" * 70)
        logger.info(
            "✅ 检查完成: 共 %d 场, 有信号 %d 场",
            self.total_checked, matched
        )
        logger.info("=" * 70)

    def run_daemon(self):
        """守护进程模式运行"""
        logger.info("=" * 70)
        logger.info("🚀 竞争区间规则引擎 v3.1 — 自动匹配服务启动")
        logger.info("  检查间隔: %d 秒", CHECK_INTERVAL)
        logger.info("  监控窗口: 未来 %d 分钟内的比赛", MATCH_WINDOW_MINUTES)
        logger.info("  规则数量: %d 条 (D-%d T-%d WL-%d)",
                     len(RULES),
                     sum(1 for r in RULES if r['requires'] == 'wm'),
                     sum(1 for r in RULES if r['requires'] == 'wml'),
                     sum(1 for r in RULES if r['requires'] == 'wl'))
        logger.info("  支持模式: 三公司(wml) / 威廉+澳门(wm) / 威廉+立博(wl)")
        logger.info("=" * 70)

        _ensure_alert_table(logger)
        self.running = True

        # 注册信号处理
        def signal_handler(signum, frame):
            logger.info("收到停止信号，正在退出...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        while self.running:
            try:
                matches = _get_upcoming_match_ids(MATCH_WINDOW_MINUTES)

                if matches:
                    scheduled_count = sum(
                        1 for m in matches if m.get('match_status') == 'scheduled'
                    )
                    live_count = sum(
                        1 for m in matches if m.get('match_status') == 'live'
                    )
                    status_info = f"未开始={scheduled_count}场"
                    if live_count > 0:
                        status_info += f", 已开赛={live_count}场（分析延迟补偿）"
                    logger.info(f"检查 {len(matches)} 场比赛 ({status_info})...")
                    self.check_matches(matches)

                # 等待下一次检查
                time.sleep(CHECK_INTERVAL)

            except Exception as e:
                logger.error(f"检查出错: {e}", exc_info=True)
                time.sleep(CHECK_INTERVAL)

        logger.info("=" * 70)
        logger.info(
            "服务已停止。总计检查: %d 场, 有信号: %d 场",
            self.total_checked, self.total_matched
        )
        logger.info("=" * 70)


def main():
    global CHECK_INTERVAL, MATCH_WINDOW_MINUTES

    parser = argparse.ArgumentParser(description='竞争区间规则引擎 v3.1 — 自动匹配服务')
    parser.add_argument('--daemon', '-d', action='store_true', help='后台守护进程模式')
    parser.add_argument('--once', '-o', action='store_true', help='单次检查所有比赛')
    parser.add_argument('--interval', '-i', type=int, default=120, help='检查间隔（秒），默认120秒(2分钟)')
    parser.add_argument('--window', '-w', type=int, default=30, help='监控窗口（分钟）')
    args = parser.parse_args()

    CHECK_INTERVAL = args.interval
    MATCH_WINDOW_MINUTES = args.window

    matcher = AutoRuleMatcher()

    if args.once:
        matcher.run_once()
    else:
        matcher.run_daemon()


if __name__ == '__main__':
    main()
