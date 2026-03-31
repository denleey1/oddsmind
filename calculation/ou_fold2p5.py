
import math
import sqlite3
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, List, Optional, Dict, Any
from scipy.stats import nbinom
from scipy.optimize import minimize
import numpy as np
import logging

logger = logging.getLogger(__name__)

# ------------------ Core math helpers ------------------

def poisson_pmf(mu: float, k: int) -> float:
    return math.exp(-mu) * mu**k / math.factorial(k)

def poisson_cdf(mu: float, k: int) -> float:
    return sum(poisson_pmf(mu, i) for i in range(k+1))

def p_over25_from_mu(mu: float) -> float:
    # P(G >= 3)
    return 1.0 - poisson_cdf(mu, 2)

def parse_line_str(s: str) -> Optional[float]:
    """
    Convert Asian total string into float midpoint:
      "2/2.5" -> 2.25
      "2.5/3" -> 2.75
      "3"     -> 3.0
      "3.5"   -> 3.5
    Return None if cannot parse.
    """
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
    """
    Convert stored odds (which may be "water" like 0.93 or decimal like 1.93) to decimal odds.
    Heuristic: if x < 1.2 -> treat as "water" and add 1.0. If already >= 1.2 -> assume decimal.
    Return None if cannot parse.
    """
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
    """Return no-vig probability for Over from two decimal odds."""
    pO_star = 1.0 / over_dec
    pU_star = 1.0 / under_dec
    s = pO_star + pU_star
    return pO_star / s

def P_eq(mu: float, k: int) -> float:
    return poisson_pmf(mu, k)

def ev_components_over(mu: float, line: float) -> Tuple[float, float]:
    """
    For an Asian line (can be integer x.0, half x.5, or quarter x.25/x.75),
    compute (W, L): the probabilities that determine Over's EV when odds are "fair".

    EV_over = (odds_fair - 1) * W - L
    We will set EV_over = 0 and solve for mu with odds_fair = 1 / p_over_no_vig.

    Consistent with standard Asian O/U settlement:
      - integer x.0: over wins on >= x+1, loses on <= x-1, push at x (ignored in W/L as EV uses net win/loss)
      - half    x.5: over wins on >= x+1, loses on <= x
      - quarter x.25 (= x/x.5): half on x.0, half on x.5
      - quarter x.75 (= x.5/x+1.0): half on x.5, half on x+1.0
    """
    base = int(math.floor(line))
    frac = line - base
    P_ge = lambda n: 1.0 - poisson_cdf(mu, n-1)
    P_le = lambda n: poisson_cdf(mu, n)
    if abs(frac - 0.0) < 1e-12:   # integer (e.g., 2.0, 3.0, ...)
        W = P_ge(base+1)
        L = P_le(base-1)
    elif abs(frac - 0.5) < 1e-12: # half (e.g., 2.5, 3.5, ...)
        W = P_ge(base+1)
        L = P_le(base)
    elif abs(frac - 0.25) < 1e-12: # quarter up (x.25 = x/x.5) e.g., 2.25
        # half on over x.0 and half on over x.5
        # net win prob component:
        #  - >= x+1 => full win both halves
        #  - == x   => half loss on x.5 leg, push on x.0 leg -> net half loss
        #  - <= x-1 => full loss
        W = P_ge(base+1)
        L = P_le(base-1) + 0.5 * P_eq(mu, base)
    elif abs(frac - 0.75) < 1e-12: # quarter down (x.75 = x.5/x+1.0) e.g., 2.75
        # half on over x.5 and half on over x+1.0
        #  - >= x+2 => full win
        #  - == x+1 => half win
        #  - <= x   => full loss
        W = P_ge(base+2) + 0.5 * P_eq(mu, base+1)
        L = P_le(base)
    else:
        # Some exotic lines (like 0.5/1, 1/1.5) also map to x.25 and x.75 midpoints; above covers them.
        # If a very unusual format sneaks in, fallback:
        # treat as pure midpoint half-line for safety.
        W = P_ge(math.floor(line)+1)
        L = P_le(math.floor(line))
    return W, L

def implied_mu_from_row(line_mid: float, over_dec: float, under_dec: float) -> Tuple[float, float]:
    """
    Solve EV_over(mu) = 0 using no-vig odds for Over derived from both sides.
    Return (mu, p_over_no_vig).
    """
    p_over = no_vig_over_prob(over_dec, under_dec)
    if p_over <= 0 or p_over >= 1:
        raise ValueError("Invalid p_over after no-vig normalization")
    odds_fair = 1.0 / p_over

    def f(mu: float) -> float:
        W, L = ev_components_over(mu, line_mid)
        return (odds_fair - 1.0) * W - L

    # Bisection on [0.01, 10]
    lo, hi = 0.01, 10.0
    flo, fhi = f(lo), f(hi)
    # Expand hi if needed
    expand = 0
    while flo * fhi > 0 and expand < 12:
        hi *= 1.5
        fhi = f(hi)
        expand += 1
    for _ in range(120):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if abs(fm) < 1e-12:
            return mid, p_over
        # pick side
        if flo * fm <= 0:
            hi = mid
            fhi = fm
        else:
            lo = mid
            flo = fm
    return 0.5 * (lo + hi), p_over

def top_two_goals_from_mu(mu: float) -> Tuple[int, int]:
    # Compute pmf on 0..7 and return argmax two (ties resolved by lower k first)
    pmf = [poisson_pmf(mu, k) for k in range(8)]
    idx = sorted(range(8), key=lambda k: (-pmf[k], k))
    return idx[0], idx[1]

# ------------------ Enhanced: Negative Binomial & Robust Consensus ------------------

def infer_nb_from_two_lines(p_over25: float, p_over35: float) -> Dict:
    """
    从2.5和3.5两条盘口联合反演负二项分布参数(μ, k)
    关键提升: 精确估计P(S=3)，解决3.0盘走水问题
    """
    mu0 = 2.6 + 0.8 * (p_over25 - 0.5)
    mu0 = max(0.5, min(6.0, mu0))
    k0 = 5.0
    
    def loss(theta):
        mu, k = theta
        if mu <= 0 or k <= 0:
            return 1e10
        try:
            p = k / (k + mu)
            pge3 = 1 - nbinom.cdf(2, k, p)
            pge4 = 1 - nbinom.cdf(3, k, p)
            return (pge3 - p_over25)**2 + (pge4 - p_over35)**2
        except:
            return 1e10
    
    best_result = None
    best_loss = float('inf')
    
    for mu_init in [mu0, 2.0, 2.5, 3.0]:
        for k_init in [k0, 2.0, 10.0]:
            try:
                result = minimize(loss, x0=(mu_init, k_init), 
                                bounds=[(0.5, 6.0), (0.2, 50.0)], method='L-BFGS-B')
                if result.fun < best_loss:
                    best_loss = result.fun
                    best_result = result
            except:
                continue
    
    if best_result is None or best_loss > 0.01:
        # 降级到泊松
        logger.warning(f"NB拟合失败(loss={best_loss:.6f})，降级到泊松")
        return {'mu': None, 'k': None, 'use_nb': False}
    
    mu, k = best_result.x
    p = k / (k + mu)
    
    p_ge3 = 1 - nbinom.cdf(2, k, p)
    p_ge4 = 1 - nbinom.cdf(3, k, p)
    p_eq3 = p_ge3 - p_ge4  # 关键: P(S=3)
    
    probs_0_7 = [nbinom.pmf(i, k, p) for i in range(8)]
    
    return {
        'mu': round(mu, 4),
        'k': round(k, 4),
        'p_ge3': round(p_ge3, 6),
        'p_eq3': round(p_eq3, 6),  # 3.0盘关键概率
        'p_ge4': round(p_ge4, 6),
        'use_nb': True,
        'P0': round(probs_0_7[0], 6),
        'P1': round(probs_0_7[1], 6),
        'P2': round(probs_0_7[2], 6),
        'P3': round(probs_0_7[3], 6),
        'P4': round(probs_0_7[4], 6),
        'P5': round(probs_0_7[5], 6),
        'P6': round(probs_0_7[6], 6),
        'P7': round(probs_0_7[7], 6),
    }


def robust_consensus_odds(records: List[Dict], trim_pct: float = 0.15) -> Optional[Tuple[float, float]]:
    """
    鲁棒赔率共识: 截尾均值 + 水位加权
    抗异常值，提高稳定性
    """
    if not records:
        return None, None
    
    processed = []
    for rec in records:
        over_odds = rec.get('over_odds')
        under_odds = rec.get('under_odds')
        
        if over_odds and under_odds and over_odds > 1.0 and under_odds > 1.0:
            margin = (1/over_odds + 1/under_odds - 1)
            p_over_raw = 1 / over_odds
            p_under_raw = 1 / under_odds
            p_over = p_over_raw / (p_over_raw + p_under_raw)  # 去水
            
            processed.append({
                'p_over': p_over,
                'margin': margin,
                'weight': 1/(margin + 0.01)  # 水位倒数加权
            })
    
    if not processed:
        return None, None
    
    # 按p_over排序并截尾
    processed.sort(key=lambda x: x['p_over'])
    n = len(processed)
    trim_count = int(n * trim_pct)
    
    if n > 4:
        trimmed = processed[trim_count:n-trim_count]
    else:
        trimmed = processed
    
    # 加权平均
    total_weight = sum(r['weight'] for r in trimmed)
    p_over_consensus = sum(r['p_over'] * r['weight'] for r in trimmed) / total_weight
    margin_avg = sum(r['margin'] for r in processed) / len(processed)
    
    return p_over_consensus, margin_avg


# ------------------ Pipeline ------------------

def compute_from_db(sqlite_path: str, match_filter: Optional[str]=None, workers: int = 1, 
                    use_nb: bool = True, trim_pct: float = 0.15) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    增强版: 支持负二项分布和鲁棒聚合
    
    Args:
        sqlite_path: 数据库路径
        match_filter: 可选match_id过滤
        workers: 并发数
        use_nb: 是否使用负二项分布(从2.5&3.5联合拟合)
        trim_pct: 鲁棒聚合截尾比例
    
    新增功能:
    - 如果有2.5和3.5盘口，自动使用NB联合拟合
    - 鲁棒赔率共识(截尾+水位加权)
    - 精确的P(S=3)估计
    """
    conn = sqlite3.connect(sqlite_path)
    df = pd.read_sql_query("SELECT * FROM ou_odds", conn)
    conn.close()

    if match_filter is not None:
        df = df[df["match_id"] == str(match_filter)].copy()

    # 按比赛分组，尝试NB联合拟合
    match_groups = df.groupby(['match_id', 'match_time', 'home', 'away'])
    
    enhanced_results = []
    
    for (match_id, match_time, home, away), group_df in match_groups:
        # 为每个阶段(open/close)收集不同盘口的赔率
        for phase in ['open', 'close']:
            line_col = f'line_{phase}'
            over_col = f'over_odds_{phase}'
            under_col = f'under_odds_{phase}'
            time_col = f'time_{phase}'
            
            # 收集该阶段所有bookmaker的赔率，按盘口分组
            lines_data = {}  # {line_mid: [odds_records]}
            
            for _, row in group_df.iterrows():
                line_str = row.get(line_col)
                line_mid = parse_line_str(line_str)
                over_odds = to_decimal_odds(row.get(over_col))
                under_odds = to_decimal_odds(row.get(under_col))
                
                if line_mid and over_odds and under_odds:
                    if line_mid not in lines_data:
                        lines_data[line_mid] = []
                    lines_data[line_mid].append({
                        'over_odds': over_odds,
                        'under_odds': under_odds,
                        'bookmaker': row.get('bookmaker'),
                        'row': row
                    })
            
            # 尝试NB联合拟合
            nb_result = None
            if use_nb and 2.5 in lines_data and 3.5 in lines_data:
                # 计算2.5和3.5的鲁棒共识
                p_over25, margin25 = robust_consensus_odds(lines_data[2.5], trim_pct)
                p_over35, margin35 = robust_consensus_odds(lines_data[3.5], trim_pct)
                
                if p_over25 and p_over35:
                    nb_result = infer_nb_from_two_lines(p_over25, p_over35)
                    if nb_result.get('use_nb'):
                        logger.info(f"[NB] {match_id} {phase}: μ={nb_result['mu']}, k={nb_result['k']}, P(S=3)={nb_result['p_eq3']}")
                        enhanced_results.append({
                            'site': group_df.iloc[0].get('site'),
                            'league': group_df.iloc[0].get('league'),
                            'match_id': match_id,
                            'match_time': match_time,
                            'home': home,
                            'away': away,
                            'market': 'Full Time',
                            'phase': phase,
                            'method': 'NB_2lines',
                            **nb_result,
                            'n_bookmakers_25': len(lines_data[2.5]),
                            'n_bookmakers_35': len(lines_data[3.5]),
                            'time_phase': group_df.iloc[0].get(time_col)
                        })
                        continue  # 已处理，跳过传统方法
            
            # 如果NB失败或不可用，回退到原有逻辑(但使用鲁棒聚合)
            for line_mid, odds_records in lines_data.items():
                p_over, margin = robust_consensus_odds(odds_records, trim_pct)
                
                if p_over:
                    # 使用鲁棒共识概率计算implied mu
                    try:
                        # 简化: 直接用去水后的概率反推mu
                        if abs(line_mid - 2.5) < 0.01:
                            # 2.5盘
                            mu, _ = implied_mu_from_row(line_mid, 1/p_over, 1/(1-p_over))
                            probs_0_7 = [poisson_pmf(mu, k) for k in range(8)]
                            p_over25 = 1 - poisson_cdf(mu, 2)
                            
                            enhanced_results.append({
                                'site': group_df.iloc[0].get('site'),
                                'league': group_df.iloc[0].get('league'),
                                'match_id': match_id,
                                'match_time': match_time,
                                'home': home,
                                'away': away,
                                'market': 'Full Time',
                                'phase': phase,
                                'method': 'Poisson_robust',
                                'mu': round(mu, 4),
                                'k': None,
                                'use_nb': False,
                                'p_over25': round(p_over25 * 100, 2),
                                'P0': round(probs_0_7[0] * 100, 2),
                                'P1': round(probs_0_7[1] * 100, 2),
                                'P2': round(probs_0_7[2] * 100, 2),
                                'P3': round(probs_0_7[3] * 100, 2),
                                'P4': round(probs_0_7[4] * 100, 2),
                                'P5': round(probs_0_7[5] * 100, 2),
                                'P6': round(probs_0_7[6] * 100, 2),
                                'P7': round(probs_0_7[7] * 100, 2),
                                'n_bookmakers': len(odds_records),
                                'avg_margin': round(margin, 4) if margin else None,
                                'time_phase': group_df.iloc[0].get(time_col)
                            })
                    except:
                        pass
    
    if enhanced_results:
        out = pd.DataFrame(enhanced_results)
        # 共识: 按match+phase聚合
        consensus = out.groupby(['site','league','match_id','match_time','home','away','market','phase'], dropna=False).agg(
            mu_consensus=('mu', 'mean'),
            k_consensus=('k', lambda x: x.dropna().mean() if x.notna().any() else None),
            p_over25_consensus=('p_over25', 'mean') if 'p_over25' in out.columns else ('p_ge3', 'mean')
        ).reset_index()
        
        return out, consensus
    
    # 如果没有增强结果，回退到原有完整逻辑
    # Build tasks for phases (open/close) per row
    tasks: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        # Open
        tasks.append({
            "phase": "open",
            "line_mid": parse_line_str(r.get("line_open")),
            "oO": to_decimal_odds(r.get("over_odds_open")),
            "oU": to_decimal_odds(r.get("under_odds_open")),
            "time_phase": r.get("time_open"),
            "line_original": r.get("line_open"),
            "base": r,
        })
        # Close
        tasks.append({
            "phase": "close",
            "line_mid": parse_line_str(r.get("line_close")),
            "oO": to_decimal_odds(r.get("over_odds_close")),
            "oU": to_decimal_odds(r.get("under_odds_close")),
            "time_phase": r.get("time_close"),
            "line_original": r.get("line_close"),
            "base": r,
        })

    def compute_task(t) -> Optional[Dict[str, Any]]:
        if t["line_mid"] is None or t["oO"] is None or t["oU"] is None:
            return None
        try:
            mu, p_over_no_vig = implied_mu_from_row(t["line_mid"], t["oO"], t["oU"])
        except Exception:
            return None
        p_over25 = p_over25_from_mu(mu)
        probs_0_7 = [poisson_pmf(mu, k) for k in range(8)]
        top1, top2 = top_two_goals_from_mu(mu)
        r = t["base"]
        return {
            "site": r.get("site"),
            "league": r.get("league"),
            "match_id": r.get("match_id"),
            "match_time": r.get("match_time"),
            "home": r.get("home"),
            "away": r.get("away"),
            "bookmaker": r.get("bookmaker"),
            "market": r.get("market"),
            "variant": r.get("variant"),
            "phase": t["phase"],
            "line_original": t["line_original"],
            "mu": mu,
            "p_over25": p_over25,
            "P0": probs_0_7[0],
            "P1": probs_0_7[1],
            "P2": probs_0_7[2],
            "P3": probs_0_7[3],
            "P4": probs_0_7[4],
            "P5": probs_0_7[5],
            "P6": probs_0_7[6],
            "P7": probs_0_7[7],
            "top1_goals": top1,
            "top2_goals": top2,
            "p_over_no_vig_at_line": p_over_no_vig,
            "time_phase": t["time_phase"],
        }

    rows: List[Dict[str, Any]] = []
    if workers and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(compute_task, t) for t in tasks]
            for fut in as_completed(futs):
                res = fut.result()
                if res is not None:
                    rows.append(res)
    else:
        for t in tasks:
            res = compute_task(t)
            if res is not None:
                rows.append(res)

    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    out = pd.DataFrame(rows)

    # Per-match equal-weight consensus per phase
    group_cols = ["site","league","match_id","match_time","home","away","market","phase"]
    # Only average across bookmakers/variants that produced results
    # Keep groups even if some grouping keys are NaN/None (league/match_time often missing in scraped data)
    agg = out.groupby(group_cols, dropna=False).agg(
        mu_consensus=("mu", "mean"),
        p_over25_consensus=("p_over25","mean")
    ).reset_index()

    # Compute consensus 0..7 and top-2 by using the consensus mu
    def attach_probs(df_cons: pd.DataFrame) -> pd.DataFrame:
        recs = []
        for _, r in df_cons.iterrows():
            mu = r["mu_consensus"]
            probs = [poisson_pmf(mu, k) for k in range(8)]
            top = sorted(range(8), key=lambda k: (-probs[k], k))[:2]
            recs.append({
                **r.to_dict(),
                **{f"P{k}": probs[k] for k in range(8)},
                "top1_goals": top[0],
                "top2_goals": top[1]
            })
        return pd.DataFrame(recs)

    consensus = attach_probs(agg)

    # Nicely format percentages for output CSVs
    def fmt_probs(df_in: pd.DataFrame) -> pd.DataFrame:
        df = df_in.copy()
        for c in ["p_over25","p_over25_consensus","P0","P1","P2","P3","P4","P5","P6","P7"]:
            if c in df.columns:
                df[c] = (df[c]*100).round(2)
        df["mu"] = df.get("mu", pd.Series(dtype=float)).round(4)
        df["mu_consensus"] = df.get("mu_consensus", pd.Series(dtype=float)).round(4)
        return df

    out_fmt = fmt_probs(out)
    cons_fmt = fmt_probs(consensus)

    return out_fmt, cons_fmt


def write_rows_to_db(db_path: str, table: str, df: pd.DataFrame):
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            site TEXT, league TEXT, match_id TEXT, match_time TEXT,
            home TEXT, away TEXT, bookmaker TEXT, market TEXT, variant TEXT,
            phase TEXT, line_original TEXT,
            mu REAL, p_over25 REAL,
            P0 REAL, P1 REAL, P2 REAL, P3 REAL, P4 REAL, P5 REAL, P6 REAL, P7 REAL,
            top1_goals INTEGER, top2_goals INTEGER,
            p_over_no_vig_at_line REAL, time_phase TEXT,
            UNIQUE(site, match_id, bookmaker, market, variant, phase)
        )""")
        con.commit()
        rows = [(
            r.get('site'), r.get('league'), str(r.get('match_id') or ''), r.get('match_time'),
            r.get('home'), r.get('away'), r.get('bookmaker'), r.get('market'), r.get('variant'),
            r.get('phase'), r.get('line_original'),
            float(r.get('mu') or 0), float(r.get('p_over25') or 0),
            float(r.get('P0') or 0), float(r.get('P1') or 0), float(r.get('P2') or 0), float(r.get('P3') or 0),
            float(r.get('P4') or 0), float(r.get('P5') or 0), float(r.get('P6') or 0), float(r.get('P7') or 0),
            int(r.get('top1_goals') or 0), int(r.get('top2_goals') or 0),
            float(r.get('p_over_no_vig_at_line') or 0), r.get('time_phase')
        ) for _, r in df.iterrows()]
        cur.executemany(f"""
        INSERT OR REPLACE INTO {table} (
            site, league, match_id, match_time, home, away, bookmaker, market, variant,
            phase, line_original, mu, p_over25, P0, P1, P2, P3, P4, P5, P6, P7,
            top1_goals, top2_goals, p_over_no_vig_at_line, time_phase
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        con.commit()
    finally:
        con.close()


def write_cons_to_db(db_path: str, table: str, df: pd.DataFrame):
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            site TEXT, league TEXT, match_id TEXT, match_time TEXT,
            home TEXT, away TEXT, market TEXT, phase TEXT,
            mu_consensus REAL, p_over25_consensus REAL,
            P0 REAL, P1 REAL, P2 REAL, P3 REAL, P4 REAL, P5 REAL, P6 REAL, P7 REAL,
            top1_goals INTEGER, top2_goals INTEGER,
            UNIQUE(site, match_id, market, phase)
        )""")
        con.commit()
        rows = [(
            r.get('site'), r.get('league'), str(r.get('match_id') or ''), r.get('match_time'),
            r.get('home'), r.get('away'), r.get('market'), r.get('phase'),
            float(r.get('mu_consensus') or 0), float(r.get('p_over25_consensus') or 0),
            float(r.get('P0') or 0), float(r.get('P1') or 0), float(r.get('P2') or 0), float(r.get('P3') or 0),
            float(r.get('P4') or 0), float(r.get('P5') or 0), float(r.get('P6') or 0), float(r.get('P7') or 0),
            int(r.get('top1_goals') or 0), int(r.get('top2_goals') or 0),
        ) for _, r in df.iterrows()]
        cur.executemany(f"""
        INSERT OR REPLACE INTO {table} (
            site, league, match_id, match_time, home, away, market, phase,
            mu_consensus, p_over25_consensus, P0, P1, P2, P3, P4, P5, P6, P7,
            top1_goals, top2_goals
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        con.commit()
    finally:
        con.close()

if __name__ == "__main__":
    import argparse, os
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="Path to your SQLite file (containing ou_odds table).")
    parser.add_argument("--match_id", default=None, help="Optional: filter to a single match_id.")
    parser.add_argument("--out_rows", default="ou_rows.csv", help="Per-bookmaker rows CSV.")
    parser.add_argument("--out_consensus", default="ou_consensus.csv", help="Per-match consensus CSV.")
    parser.add_argument("--sqlite-out", default=None, help="Optional: write results to this SQLite path (defaults to --db if not set).")
    parser.add_argument("--table-rows", default="ou_rows_metrics", help="SQLite table name for rows output.")
    parser.add_argument("--table-cons", default="ou_consensus_metrics", help="SQLite table name for consensus output.")
    parser.add_argument("--workers", type=int, default=4, help="Concurrency for computing rows.")
    args = parser.parse_args()

    rows, consensus = compute_from_db(args.db, args.match_id, workers=args.workers)

    # Optional DB writes
    db_out = args.sqlite_out or args.db
    if db_out:
        if not rows.empty:
            write_rows_to_db(db_out, args.table_rows, rows)
        if not consensus.empty:
            write_cons_to_db(db_out, args.table_cons, consensus)

    # CSVs
    rows.to_csv(args.out_rows, index=False, encoding="utf-8-sig")
    consensus.to_csv(args.out_consensus, index=False, encoding="utf-8-sig")

    print(f"Wrote {len(rows)} row(s) to {args.out_rows}")
    print(f"Wrote {len(consensus)} consensus row(s) to {args.out_consensus}")
