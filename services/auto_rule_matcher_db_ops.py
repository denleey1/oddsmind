#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库操作 — 竞争区间规则引擎 v2.0 集成
=========================================
支持三公司(威廉+澳门+立博)规则匹配结果的存储和查询。

更新日期: 2026-02-11
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from database.connection import get_connection


def ensure_alert_table(logger) -> None:
    """确保规则匹配结果表存在(含新字段: signal_level, mode, rule_grade)"""
    db = get_connection()

    create_sql = '''
        CREATE TABLE IF NOT EXISTS rule_match_alerts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            match_id INT NOT NULL,
            rule_id VARCHAR(20) NOT NULL,
            rule_name VARCHAR(200) NOT NULL,
            prediction VARCHAR(50) NOT NULL,
            handicap_team VARCHAR(100),
            receiver_team VARCHAR(100),
            bet_suggestion VARCHAR(200),
            rule_accuracy DECIMAL(5,3),
            signal_level VARCHAR(20) DEFAULT NULL COMMENT '信号等级: 重仓/强烈/标准',
            mode VARCHAR(20) DEFAULT NULL COMMENT '公司组合: wml/wm/wl',
            rule_grade VARCHAR(5) DEFAULT NULL COMMENT '规则等级: S/A/B',
            features JSON,
            checked_at DATETIME NOT NULL,
            match_time DATETIME,
            match_result VARCHAR(20) DEFAULT NULL,
            is_correct TINYINT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_match_rule (match_id, rule_id),
            INDEX idx_match_time (match_time),
            INDEX idx_checked_at (checked_at),
            INDEX idx_signal_level (signal_level)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    '''

    try:
        db.execute_query(create_sql)
        logger.info("规则匹配结果表已就绪")

        # 迁移：确保新字段存在
        _migrate_add_columns(db, logger)

    except Exception as e:
        logger.warning(f"创建表时出错（可能已存在）: {e}")


def _migrate_add_columns(db, logger) -> None:
    """迁移: 为旧表添加新字段"""
    new_columns = [
        ('signal_level', "VARCHAR(20) DEFAULT NULL COMMENT '信号等级: 重仓/强烈/标准'"),
        ('mode', "VARCHAR(20) DEFAULT NULL COMMENT '公司组合: wml/wm/wl'"),
        ('rule_grade', "VARCHAR(5) DEFAULT NULL COMMENT '规则等级: S/A/B'"),
        ('updated_at', "DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    ]

    for col_name, col_def in new_columns:
        try:
            check_sql = '''
                SELECT COUNT(*) as cnt
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'rule_match_alerts'
                  AND COLUMN_NAME = %s
            '''
            result = db.execute_query(check_sql, (col_name,), fetch='one')
            if result and result.get('cnt', 0) == 0:
                alter_sql = f'ALTER TABLE rule_match_alerts ADD COLUMN {col_name} {col_def}'
                db.execute_query(alter_sql)
                logger.info(f"已为 rule_match_alerts 表添加 {col_name} 字段")
        except Exception as e:
            logger.debug(f"迁移字段 {col_name} 时出错(可能已存在): {e}")

    # 确保 rule_name 字段足够长
    try:
        db.execute_query(
            "ALTER TABLE rule_match_alerts MODIFY COLUMN rule_name VARCHAR(200) NOT NULL"
        )
    except Exception:
        pass

    # 确保 UNIQUE KEY 存在
    try:
        check_uk_sql = '''
            SELECT COUNT(*) as cnt
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'rule_match_alerts'
              AND INDEX_NAME = 'uk_match_rule'
        '''
        uk_result = db.execute_query(check_uk_sql, fetch='one')
        if uk_result and uk_result.get('cnt', 0) == 0:
            db.execute_query('''
                ALTER TABLE rule_match_alerts
                ADD UNIQUE KEY uk_match_rule (match_id, rule_id)
            ''')
            logger.info("已为 rule_match_alerts 表添加 UNIQUE KEY uk_match_rule")
    except Exception:
        pass


def save_alert(
    match_id: int,
    rule_id: str,
    rule_desc: str,
    rule_grade: str,
    prediction: str,
    signal_level: str,
    mode: str,
    handicap_team: str,
    receiver_team: str,
    match_time: Optional[datetime],
    features: Dict[str, Any],
    logger,
) -> bool:
    """保存规则匹配结果（新版: 支持信号等级和公司组合模式）"""
    db = get_connection()

    # 根据预测方向生成建议
    if prediction == '让方不输':
        bet_suggestion = f"买 {handicap_team} 不输（{handicap_team}赢或平局）"
    elif prediction.startswith('排除'):
        bet_suggestion = f"⚠️ 剪刀差预警: {prediction}（三庄降赔诱导+平博不认可）"
    else:
        bet_suggestion = f"买 {receiver_team} 不输（{receiver_team}赢或平局）"

    # 使用 ON DUPLICATE KEY UPDATE 来更新最后一次匹配结果
    sql = '''
        INSERT INTO rule_match_alerts
        (match_id, rule_id, rule_name, prediction, handicap_team, receiver_team,
         bet_suggestion, rule_accuracy, signal_level, mode, rule_grade,
         features, checked_at, match_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            rule_name = VALUES(rule_name),
            prediction = VALUES(prediction),
            handicap_team = VALUES(handicap_team),
            receiver_team = VALUES(receiver_team),
            bet_suggestion = VALUES(bet_suggestion),
            rule_accuracy = VALUES(rule_accuracy),
            signal_level = VALUES(signal_level),
            mode = VALUES(mode),
            rule_grade = VALUES(rule_grade),
            features = VALUES(features),
            checked_at = VALUES(checked_at),
            match_time = VALUES(match_time)
    '''

    # 从规则描述解析准确率 (格式: "→ OOS 90.7%(n=43)")
    import re as _re
    _acc_match = _re.search(r'(\d+\.?\d*)%\(n=(\d+)\)', rule_desc)
    rule_accuracy_val = float(_acc_match.group(1)) / 100.0 if _acc_match else None

    try:
        db.execute_query(sql, (
            match_id, rule_id, rule_desc, prediction,
            handicap_team, receiver_team, bet_suggestion,
            rule_accuracy_val,
            signal_level, mode, rule_grade,
            json.dumps(features, ensure_ascii=False, default=str),
            datetime.now(), match_time,
        ))
        return True
    except Exception as e:
        logger.error(f"保存匹配结果失败: {e}")
        return False


def _cleanup_stale_rules(match_id: int, keep_rule_ids: List[str], logger) -> int:
    """
    清理过期的规则记录。
    当赔率变化导致某些规则不再触发时，删除这些旧记录，
    避免显示过时的信号等级（如"重仓"已降级为"标准"或"无信号"）。

    返回删除的记录数。
    """
    db = get_connection()

    if not keep_rule_ids:
        # 全部规则都不再触发 → 删除该比赛所有记录
        sql = 'DELETE FROM rule_match_alerts WHERE match_id = %s'
        try:
            result = db.execute_query(sql, (match_id,))
            deleted = result if isinstance(result, int) else 0
            if deleted:
                logger.info("  🧹 比赛 %s 已无信号，清理 %d 条过期记录", match_id, deleted)
            return deleted
        except Exception as e:
            logger.warning("清理过期规则失败(match_id=%s): %s", match_id, e)
            return 0
    else:
        # 部分规则不再触发 → 只删除不在 keep_rule_ids 里的记录
        placeholders = ','.join(['%s'] * len(keep_rule_ids))
        sql = f'DELETE FROM rule_match_alerts WHERE match_id = %s AND rule_id NOT IN ({placeholders})'
        try:
            params = [match_id] + list(keep_rule_ids)
            result = db.execute_query(sql, tuple(params))
            deleted = result if isinstance(result, int) else 0
            if deleted:
                logger.info("  🧹 清理 %d 条不再触发的规则 (保留 %d 条)",
                            deleted, len(keep_rule_ids))
            return deleted
        except Exception as e:
            logger.warning("清理过期规则失败(match_id=%s): %s", match_id, e)
            return 0


def save_signal_summary(
    match_id: int,
    eval_result: Dict[str, Any],
    match_info: Dict[str, Any],
    logger,
) -> int:
    """
    保存一场比赛的完整信号结果。
    为每条触发规则保存一行记录。
    同时清理不再触发的旧规则记录，确保信号等级实时准确。

    返回保存的规则数量。
    """
    signal = eval_result.get('signal', '无信号')
    triggered_sc = eval_result.get('triggered_sc', [])
    if signal in ('无信号', '无数据') and not triggered_sc:
        _cleanup_stale_rules(match_id, [], logger)
        return 0

    side_cn = eval_result.get('side_cn', '')
    mode = eval_result.get('mode', '')
    triggered = eval_result.get('triggered', [])

    # 先清理不再触发的旧规则记录
    current_rule_ids = [r['id'] for r in triggered]
    _cleanup_stale_rules(match_id, current_rule_ids, logger)
    feat = eval_result.get('features', {})

    # 导入显示辅助函数
    from services.auto_rule_matcher_logic_ops import classify_odds_change_detailed, classify_power

    # 计算显示用字段
    w_h = feat.get('w_h') or 0
    w_r = feat.get('w_r') or 0
    w_d = feat.get('w_d') or 0
    w_ih = feat.get('w_ih') or 0
    w_ir = feat.get('w_ir') or 0
    w_id = feat.get('w_id') or 0

    # 赔率字符串
    odds_str = f"{w_h:.2f} / {w_d:.2f} / {w_r:.2f}" if w_h else ''

    # 变化分类 (使用变化百分比)
    h_change_pct = feat.get('w_hc', 0) or 0
    r_change_pct = feat.get('w_rc', 0) or 0
    d_change_pct = feat.get('w_dc', 0) or 0
    h_change_simple = classify_odds_change_detailed(w_ih, w_h) if w_ih else ''
    r_change_simple = classify_odds_change_detailed(w_ir, w_r) if w_ir else ''
    d_change_simple = classify_odds_change_detailed(w_id, w_d) if w_id else ''

    # 力量差
    power_diff_val = feat.get('w_power_diff')
    power_v2 = classify_power(power_diff_val) if power_diff_val is not None else ''

    # 盘型 (区间类型, 来自OAR分析)
    curr_h_full = feat.get('w_curr_h_range', '') or ''
    curr_r_full = feat.get('w_curr_r_range', '') or ''
    curr_draw_full = feat.get('w_curr_d_range', '') or ''
    init_h_full = feat.get('w_init_h_range', '') or ''
    init_r_full = feat.get('w_init_r_range', '') or ''

    # 构建保存用的特征信息
    features_to_save = {
        'signal_level': signal,
        'mode': mode,
        'mode_cn': {'wml': '三公司', 'wm': '威廉+澳门', 'wl': '威廉+立博'}.get(mode, ''),
        'side': eval_result.get('side', ''),
        'side_cn': side_cn,
        'score': eval_result.get('score', 0),
        'h_score': eval_result.get('h_score', 0),
        'r_score': eval_result.get('r_score', 0),
        'cross_confirm': eval_result.get('cross_confirm', False),
        'conflict': eval_result.get('conflict', False),
        'home_is_h': feat.get('home_is_h', True),
        'triggered_count': len(triggered),
        'triggered_h_count': len(eval_result.get('triggered_h', [])),
        'triggered_r_count': len(eval_result.get('triggered_r', [])),
        # 核心赔率特征
        'w_h': feat.get('w_h'),
        'w_r': feat.get('w_r'),
        'w_d': feat.get('w_d'),
        'w_spread': feat.get('w_spread'),
        'w_ih': feat.get('w_ih'),
        'w_ir': feat.get('w_ir'),
        'w_id': feat.get('w_id'),
        'm_h': feat.get('m_h'),
        'm_r': feat.get('m_r'),
        'm_d': feat.get('m_d'),
        'm_spread': feat.get('m_spread'),
        'l_h': feat.get('l_h'),
        'l_r': feat.get('l_r'),
        'l_d': feat.get('l_d'),
        'l_spread': feat.get('l_spread'),
        # 变化百分比 (原始值)
        'w_hc': feat.get('w_hc'),
        'w_rc': feat.get('w_rc'),
        'w_dc': feat.get('w_dc'),
        # 力量差原始值
        'w_power_diff': power_diff_val,
        # ---- 小程序显示用字段 (向后兼容旧版) ----
        'odds_str': odds_str,
        'h_odds': w_h,
        'r_odds': w_r,
        'curr_draw_odds': w_d,
        'h_change_simple': h_change_simple,
        'r_change_simple': r_change_simple,
        'd_change_simple': d_change_simple,
        'curr_h_full': curr_h_full,
        'curr_r_full': curr_r_full,
        'curr_draw_full': curr_draw_full,
        'init_h_full': init_h_full,
        'init_r_full': init_r_full,
        'power': power_v2,
        'power_v2': power_v2,
        # 比赛信息
        'home_team': match_info.get('home_name', ''),
        'away_team': match_info.get('away_name', ''),
        'league_name': match_info.get('league_name', ''),
    }

    # 确定让方/受让方队名
    home_is_h = feat.get('home_is_h', True)
    home_name = match_info.get('home_name', str(feat.get('home_team_id', '')))
    away_name = match_info.get('away_name', str(feat.get('away_team_id', '')))
    if home_is_h:
        handicap_team = home_name
        receiver_team = away_name
    else:
        handicap_team = away_name
        receiver_team = home_name

    saved = 0
    for r in triggered:
        ok = save_alert(
            match_id=match_id,
            rule_id=r['id'],
            rule_desc=r['desc'],
            rule_grade=r['grade'],
            prediction=side_cn,
            signal_level=signal,
            mode=mode,
            handicap_team=handicap_team,
            receiver_team=receiver_team,
            match_time=feat.get('match_time'),
            features=features_to_save,
            logger=logger,
        )
        if ok:
            saved += 1

    # ---- 剪刀差信号保存 (独立于H/R体系) ----
    triggered_sc = eval_result.get('triggered_sc', [])
    if triggered_sc:
        _sc_labels = {'XH': '排除主胜', 'XA': '排除客胜', 'XD': '排除平局'}
        _sc_grade_to_level = {'S': '重仓', 'A': '重仓', 'B': '强烈'}
        # 把剪刀差规则ID也加入保留列表，避免被清理
        current_rule_ids.extend([r['id'] for r in triggered_sc])
        _cleanup_stale_rules(match_id, current_rule_ids, logger)

        for r in triggered_sc:
            sc_prediction = _sc_labels.get(r.get('side', ''), '剪刀差')
            sc_level = _sc_grade_to_level.get(r['grade'], '参考')
            sc_features = {
                **features_to_save,
                'scissor_type': r.get('side', ''),
                'b3_raw_ih': feat.get('b3_raw_ih'), 'b3_raw_ch': feat.get('b3_raw_ch'),
                'pb_raw_ih': feat.get('pb_raw_ih'), 'pb_raw_ch': feat.get('pb_raw_ch'),
                'w_raw_ih': feat.get('w_raw_ih'), 'w_raw_ch': feat.get('w_raw_ch'),
                'l_raw_ih': feat.get('l_raw_ih'), 'l_raw_ch': feat.get('l_raw_ch'),
            }
            ok = save_alert(
                match_id=match_id,
                rule_id=r['id'],
                rule_desc=r['desc'],
                rule_grade=r['grade'],
                prediction=sc_prediction,
                signal_level=sc_level,
                mode='sc',
                handicap_team=home_name,
                receiver_team=away_name,
                match_time=feat.get('match_time'),
                features=sc_features,
                logger=logger,
            )
            if ok:
                saved += 1

    # 统一该比赛所有规则的 signal_level，避免不同评估周期导致的不一致
    # 注意: 剪刀差规则有独立的 signal_level，不参与统一
    if saved > 0 and signal not in ('剪刀差',):
        _normalize_signal_level(match_id, signal, logger)

    return saved


def _normalize_signal_level(match_id: int, signal_level: str, logger) -> None:
    """确保同一比赛的所有规则记录使用相同的 signal_level。
    当信号等级在两次评估间发生变化时（如从"参考"升级为"重仓"），
    旧规则记录可能保留过期的 signal_level，导致同一比赛在不同分组中重复出现。
    """
    db = get_connection()
    try:
        sql = '''
            UPDATE rule_match_alerts
            SET signal_level = %s
            WHERE match_id = %s AND (signal_level != %s OR signal_level IS NULL)
        '''
        db.execute_query(sql, (signal_level, match_id, signal_level))
    except Exception as e:
        logger.warning("统一 signal_level 失败(match_id=%s): %s", match_id, e)


def get_upcoming_match_ids(minutes: int = 30) -> List[Dict[str, Any]]:
    """
    获取即将开始的比赛列表(含基本信息)。
    新引擎的特征加载由 evaluate_match 内部完成。
    """
    db = get_connection()

    now = datetime.now()
    future = now + timedelta(minutes=minutes)
    live_window_start = now - timedelta(minutes=30)

    query = '''
        SELECT m.match_id, m.match_time,
               m.home_team_name, m.away_team_name,
               m.match_status,
               l.league_id, l.name_cn as league_name
        FROM matches m
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE (
            (m.match_status = 'scheduled' AND m.match_time BETWEEN %s AND %s)
            OR
            (m.match_status = 'live' AND m.match_time >= %s AND m.match_time <= %s)
        )
        ORDER BY m.match_time
    '''

    return db.execute_query(
        query, (now, future, live_window_start, now), fetch='all'
    ) or []


def get_all_scheduled_match_ids() -> List[Dict[str, Any]]:
    """
    获取所有未开始的比赛列表(含基本信息)。
    用于 --once 模式。
    """
    db = get_connection()

    now = datetime.now()
    live_window_start = now - timedelta(minutes=30)

    query = '''
        SELECT m.match_id, m.match_time,
               m.home_team_name, m.away_team_name,
               m.match_status,
               l.league_id, l.name_cn as league_name
        FROM matches m
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE (
            (m.match_status = 'scheduled' AND m.match_time > NOW())
            OR
            (m.match_status = 'live' AND m.match_time >= %s AND m.match_time <= %s)
        )
        ORDER BY m.match_time
    '''

    return db.execute_query(
        query, (live_window_start, now), fetch='all'
    ) or []


# ==================== 向后兼容导出 ====================
# 以下函数保留签名，供旧代码 import 时不报错

def get_upcoming_matches(company_id: str, minutes: int) -> List[Dict]:
    """向后兼容: 旧版获取比赛(已不再使用 company_id 参数)"""
    return get_upcoming_match_ids(minutes)


def get_all_scheduled_matches(company_id: str) -> List[Dict]:
    """向后兼容: 旧版获取比赛(已不再使用 company_id 参数)"""
    return get_all_scheduled_match_ids()


__all__ = [
    "ensure_alert_table",
    "get_all_scheduled_match_ids",
    "get_all_scheduled_matches",
    "get_upcoming_match_ids",
    "get_upcoming_matches",
    "save_alert",
    "save_signal_summary",
]
