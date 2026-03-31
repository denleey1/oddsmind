"""
增强版大小球反演模块
集成负二项分布反演、鲁棒聚合和多盘口联合拟合
"""

import math
import sqlite3
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, List, Optional, Dict, Any
import logging

# 导入新模块
from calculation.nb_inverter import (
    infer_nb_from_two_lines,
    infer_nb_from_single_line,
    robust_consensus,
    negative_binomial_pmf
)

logger = logging.getLogger(__name__)


# ------------------ 原有核心函数(保留兼容性) ------------------

def poisson_pmf(mu: float, k: int) -> float:
    return math.exp(-mu) * mu**k / math.factorial(k)


def parse_line_str(s: str) -> Optional[float]:
    """解析亚洲盘口字符串"""
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    if "/" in s:
        a, b = s.split("/")
        try:
            return (float(a) + float(b)) / 2.0
        except:
            return None
    try:
        return float(s)
    except:
        return None


def to_decimal_odds(x: Optional[str]) -> Optional[float]:
    """转换赔率格式"""
    if x is None:
        return None
    xs = str(x).strip()
    if not xs:
        return None
    try:
        v = float(xs)
    except:
        return None
    if v <= 0:
        return None
    if v < 1.2:
        return 1.0 + v
    return v


def no_vig_over_prob(over_dec: float, under_dec: float) -> float:
    """去水计算Over概率"""
    pO_star = 1.0 / over_dec
    pU_star = 1.0 / under_dec
    s = pO_star + pU_star
    return pO_star / s


# ------------------ 增强功能: 多盘口聚合与NB反演 ------------------

def extract_line_odds_groups(rows: List[Dict]) -> Dict[str, List[Dict]]:
    """
    按盘口线分组赔率数据
    
    Returns:
        {line: [records]} 例如 {'2.5': [...], '3.5': [...], '3.0': [...]}
    """
    groups = {}
    
    for row in rows:
        line_str = row.get('line_original', '')
        line_mid = parse_line_str(line_str)
        
        if line_mid is None:
            continue
        
        # 规范化为标准盘口
        if abs(line_mid - 2.5) < 0.01:
            key = '2.5'
        elif abs(line_mid - 3.5) < 0.01:
            key = '3.5'
        elif abs(line_mid - 3.0) < 0.01:
            key = '3.0'
        elif abs(line_mid - 2.25) < 0.01:
            key = '2.25'
        elif abs(line_mid - 2.75) < 0.01:
            key = '2.75'
        else:
            key = str(line_mid)
        
        if key not in groups:
            groups[key] = []
        
        groups[key].append(row)
    
    return groups


def compute_robust_consensus_for_line(records: List[Dict], trim_pct: float = 0.15) -> Optional[Dict]:
    """
    对单条盘口的多家赔率进行鲁棒聚合
    
    Returns:
        {'p_over_consensus': x, 'margin_avg': y, 'n_bookmakers': z}
    """
    odds_records = []
    
    for rec in records:
        over_odds = rec.get('over_odds')
        under_odds = rec.get('under_odds')
        
        if over_odds and under_odds:
            odds_records.append({
                'over_odds': over_odds,
                'under_odds': under_odds
            })
    
    if not odds_records:
        return None
    
    p_consensus, margin = robust_consensus(odds_records, trim_pct=trim_pct, margin_weight=True)
    
    if p_consensus is None:
        return None
    
    return {
        'p_over_consensus': p_consensus,
        'margin_avg': margin,
        'n_bookmakers': len(odds_records)
    }


def infer_nb_from_match_lines(
    line_groups: Dict[str, List[Dict]],
    phase: str,
    league_k_prior: float = 5.0
) -> Dict:
    """
    从一场比赛的多条盘口联合反演NB参数
    
    优先级:
    1. 如果有2.5和3.5，联合拟合(μ, k)
    2. 如果只有一条，使用联赛k先验
    3. 降级到泊松
    
    Args:
        line_groups: 按盘口分组的数据 {'2.5': [...], '3.5': [...]}
        phase: 'open' 或 'close'
        league_k_prior: 联赛k先验
    
    Returns:
        NB参数和概率字典
    """
    # 提取关键盘口的共识概率
    consensus_25 = None
    consensus_35 = None
    consensus_30 = None
    
    if '2.5' in line_groups:
        c = compute_robust_consensus_for_line(line_groups['2.5'])
        if c:
            consensus_25 = c['p_over_consensus']
    
    if '3.5' in line_groups:
        c = compute_robust_consensus_for_line(line_groups['3.5'])
        if c:
            consensus_35 = c['p_over_consensus']
    
    if '3.0' in line_groups:
        c = compute_robust_consensus_for_line(line_groups['3.0'])
        if c:
            consensus_30 = c['p_over_consensus']
    
    # 策略1: 如果有2.5和3.5，联合拟合
    if consensus_25 is not None and consensus_35 is not None:
        result = infer_nb_from_two_lines(consensus_25, consensus_35)
        result['inference_method'] = 'two_lines_nb'
        result['lines_used'] = ['2.5', '3.5']
        
        # 如果还有3.0，可以验证P(S=3)
        if consensus_30 is not None:
            p_eq3_market = consensus_25 - consensus_35  # 近似
            p_eq3_model = result['p_eq3']
            result['p_eq3_market_check'] = round(p_eq3_market, 6)
            result['p_eq3_deviation'] = round(abs(p_eq3_model - p_eq3_market), 6)
        
        return result
    
    # 策略2: 只有一条盘口
    elif consensus_25 is not None:
        result = infer_nb_from_single_line(2.5, consensus_25, league_k_prior)
        result['inference_method'] = 'single_line_nb'
        result['lines_used'] = ['2.5']
        return result
    
    elif consensus_35 is not None:
        result = infer_nb_from_single_line(3.5, consensus_35, league_k_prior)
        result['inference_method'] = 'single_line_nb'
        result['lines_used'] = ['3.5']
        return result
    
    # 策略3: 无可用数据
    else:
        return {
            'mu': None,
            'k': None,
            'inference_method': 'failed',
            'error': 'No valid lines available'
        }


def compute_from_db_enhanced(
    sqlite_path: str,
    match_filter: Optional[str] = None,
    workers: int = 1,
    league_k_prior: float = 5.0,
    trim_pct: float = 0.15
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    增强版计算: 集成NB反演和鲁棒聚合
    
    Args:
        sqlite_path: 数据库路径
        match_filter: 可选的match_id过滤
        workers: 并发数
        league_k_prior: 联赛k先验(用于单盘口反演)
        trim_pct: 截尾比例
    """
    conn = sqlite3.connect(sqlite_path)
    df = pd.read_sql_query("SELECT * FROM ou_odds", conn)
    conn.close()
    
    if match_filter is not None:
        df = df[df["match_id"] == str(match_filter)].copy()
    
    # 按比赛和阶段分组
    match_phase_groups = df.groupby(['match_id', 'match_time', 'home', 'away'])
    
    all_results = []
    
    for (match_id, match_time, home, away), group_df in match_phase_groups:
        # 准备开盘和收盘数据
        open_rows = []
        close_rows = []
        
        for _, row in group_df.iterrows():
            # 开盘
            if row.get('line_open') and row.get('over_odds_open') and row.get('under_odds_open'):
                open_rows.append({
                    'line_original': row['line_open'],
                    'over_odds': to_decimal_odds(row['over_odds_open']),
                    'under_odds': to_decimal_odds(row['under_odds_open']),
                    'bookmaker': row.get('bookmaker'),
                    'row': row
                })
            
            # 收盘
            if row.get('line_close') and row.get('over_odds_close') and row.get('under_odds_close'):
                close_rows.append({
                    'line_original': row['line_close'],
                    'over_odds': to_decimal_odds(row['over_odds_close']),
                    'under_odds': to_decimal_odds(row['under_odds_close']),
                    'bookmaker': row.get('bookmaker'),
                    'row': row
                })
        
        # 处理开盘
        if open_rows:
            open_groups = extract_line_odds_groups(open_rows)
            nb_result_open = infer_nb_from_match_lines(open_groups, 'open', league_k_prior)
            
            if nb_result_open.get('mu') is not None:
                all_results.append({
                    'match_id': match_id,
                    'match_time': match_time,
                    'home': home,
                    'away': away,
                    'phase': 'open',
                    **nb_result_open,
                    'n_bookmakers': sum(len(v) for v in open_groups.values())
                })
        
        # 处理收盘
        if close_rows:
            close_groups = extract_line_odds_groups(close_rows)
            nb_result_close = infer_nb_from_match_lines(close_groups, 'close', league_k_prior)
            
            if nb_result_close.get('mu') is not None:
                all_results.append({
                    'match_id': match_id,
                    'match_time': match_time,
                    'home': home,
                    'away': away,
                    'phase': 'close',
                    **nb_result_close,
                    'n_bookmakers': sum(len(v) for v in close_groups.values())
                })
    
    if not all_results:
        return pd.DataFrame(), pd.DataFrame()
    
    # 转换为DataFrame
    results_df = pd.DataFrame(all_results)
    
    # 格式化百分比
    for col in ['p_ge3', 'p_eq3', 'p_ge4', 'p_le2', 'P0', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7']:
        if col in results_df.columns:
            results_df[col] = (results_df[col] * 100).round(2)
    
    # 生成共识表(每场比赛的平均)
    consensus_cols = ['match_id', 'match_time', 'home', 'away', 'phase']
    consensus_df = results_df.groupby(consensus_cols, dropna=False).agg({
        'mu': 'mean',
        'k': 'mean',
        'p_ge3': 'mean',
        'p_eq3': 'mean',
        'p_ge4': 'mean'
    }).reset_index()
    
    return results_df, consensus_df


# ------------------ 数据库写入 (扩展支持NB参数) ------------------

def write_enhanced_to_db(db_path: str, table: str, df: pd.DataFrame):
    """写入增强结果到数据库"""
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            match_id TEXT, match_time TEXT, home TEXT, away TEXT, phase TEXT,
            mu REAL, k REAL, distribution_type TEXT, inference_method TEXT,
            p_ge3 REAL, p_eq3 REAL, p_ge4 REAL, p_le2 REAL,
            P0 REAL, P1 REAL, P2 REAL, P3 REAL, P4 REAL, P5 REAL, P6 REAL, P7 REAL,
            n_bookmakers INTEGER, lines_used TEXT,
            UNIQUE(match_id, phase)
        )""")
        con.commit()
        
        rows = [(
            r.get('match_id'), r.get('match_time'), r.get('home'), r.get('away'), r.get('phase'),
            float(r.get('mu') or 0), float(r.get('k') or 0),
            r.get('distribution_type'), r.get('inference_method'),
            float(r.get('p_ge3') or 0), float(r.get('p_eq3') or 0),
            float(r.get('p_ge4') or 0), float(r.get('p_le2') or 0),
            float(r.get('P0') or 0), float(r.get('P1') or 0), float(r.get('P2') or 0),
            float(r.get('P3') or 0), float(r.get('P4') or 0), float(r.get('P5') or 0),
            float(r.get('P6') or 0), float(r.get('P7') or 0),
            int(r.get('n_bookmakers') or 0),
            str(r.get('lines_used') or '')
        ) for _, r in df.iterrows()]
        
        cur.executemany(f"""
        INSERT OR REPLACE INTO {table} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        con.commit()
    finally:
        con.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="增强版大小球反演(NB+鲁棒聚合)")
    parser.add_argument("--db", required=True, help="SQLite数据库路径")
    parser.add_argument("--match_id", default=None, help="可选: 过滤match_id")
    parser.add_argument("--out_csv", default="ou_enhanced.csv", help="输出CSV")
    parser.add_argument("--out_consensus", default="ou_consensus_enhanced.csv", help="共识CSV")
    parser.add_argument("--sqlite-out", default=None, help="可选: 输出SQLite路径")
    parser.add_argument("--table", default="ou_enhanced_metrics", help="输出表名")
    parser.add_argument("--league-k", type=float, default=5.0, help="联赛k先验")
    parser.add_argument("--trim-pct", type=float, default=0.15, help="截尾比例")
    parser.add_argument("--workers", type=int, default=4, help="并发数")
    
    args = parser.parse_args()
    
    print(f"[增强版反演] 开始处理 {args.db}")
    print(f"  - 联赛k先验: {args.league_k}")
    print(f"  - 截尾比例: {args.trim_pct}")
    
    results, consensus = compute_from_db_enhanced(
        args.db,
        match_filter=args.match_id,
        workers=args.workers,
        league_k_prior=args.league_k,
        trim_pct=args.trim_pct
    )
    
    # 输出CSV
    results.to_csv(args.out_csv, index=False, encoding='utf-8-sig')
    consensus.to_csv(args.out_consensus, index=False, encoding='utf-8-sig')
    
    # 可选: 写入数据库
    db_out = args.sqlite_out or args.db
    if db_out and not results.empty:
        write_enhanced_to_db(db_out, args.table, results)
    
    print(f"\n[完成] 处理 {len(results)} 行结果")
    print(f"  - 已保存到: {args.out_csv}")
    print(f"  - 共识文件: {args.out_consensus}")
    
    # 显示统计
    if not results.empty:
        print(f"\n[统计]")
        print(f"  - 使用NB双盘口: {len(results[results['inference_method']=='two_lines_nb'])}")
        print(f"  - 使用NB单盘口: {len(results[results['inference_method']=='single_line_nb'])}")
        print(f"  - 平均μ: {results['mu'].mean():.3f}")
        print(f"  - 平均k: {results['k'].mean():.3f}")
        print(f"  - 平均P(S=3): {results['p_eq3'].mean():.2f}%")







