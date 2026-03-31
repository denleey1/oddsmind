#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
欧赔特征计算引擎
计算：Δodds、Z-score、隐含概率p、Δp、Δmove、返还率RTP等
"""

from typing import Dict, Tuple, Optional, Literal

Outcome = Literal["H", "D", "A"]


def skeleton_point_and_width(skeleton: Dict) -> Tuple[Dict[str, float], Optional[Dict[str, float]]]:
    """
    从骨架区间或标准点计算骨架点和宽度
    
    Args:
        skeleton: {"type": "range", "H": [1.69, 1.88], ...} 或 {"type": "point", "H": 1.785, ...}
    
    Returns:
        (M, W): M是骨架点字典，W是宽度字典（如果是点则为None）
    """
    if skeleton.get("type") == "range":
        M = {
            k: (skeleton[k][0] + skeleton[k][1]) / 2.0
            for k in ["H", "D", "A"]
        }
        W = {
            k: (skeleton[k][1] - skeleton[k][0])
            for k in ["H", "D", "A"]
        }
        return M, W
    else:
        # 标准点
        M = {
            k: float(skeleton[k])
            for k in ["H", "D", "A"]
        }
        return M, None


def delta_odds(odds: Dict[str, float], M: Dict[str, float]) -> Dict[str, float]:
    """
    计算赔率偏移（Δodds）
    
    Args:
        odds: {"H": 2.20, "D": 3.00, "A": 3.30}
        M: 骨架点 {"H": 1.785, "D": 3.66, "A": 4.31}
    
    Returns:
        {"H": 0.233, "D": -0.180, "A": -0.234}  # 相对偏移百分比
    """
    return {
        k: (odds[k] - M[k]) / M[k] if M[k] != 0 else 0.0
        for k in ["H", "D", "A"]
    }


def z_score(odds: Dict[str, float], M: Dict[str, float], W: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
    """
    计算区间标准化偏移（Z-score）
    用于统一量纲，判断"越界程度"
    
    Args:
        odds: 当前赔率
        M: 骨架点
        W: 骨架宽度（如果是点则为None）
    
    Returns:
        Z-score字典，如果W为None则返回None
    """
    if not W:
        return None
    
    return {
        k: (odds[k] - M[k]) / (W[k] if W[k] != 0 else 1e-9)
        for k in ["H", "D", "A"]
    }


def implied_probs(odds: Dict[str, float]) -> Dict[str, float]:
    """
    计算去水隐含概率（p）
    
    Args:
        odds: {"H": 2.20, "D": 3.00, "A": 3.30}
    
    Returns:
        {"H": 0.4167, "D": 0.3056, "A": 0.2778}  # 归一化后的概率
    """
    q = {
        k: 1.0 / odds[k] if odds[k] != 0 else 0.0
        for k in ["H", "D", "A"]
    }
    s = q["H"] + q["D"] + q["A"]
    
    if s == 0:
        return {"H": 0.3333, "D": 0.3333, "A": 0.3333}
    
    return {
        k: q[k] / s
        for k in ["H", "D", "A"]
    }


def delta_move(open_odds: Dict[str, float], live_odds: Dict[str, float]) -> Dict[str, float]:
    """
    计算变盘幅度（Δmove）
    初赔 → 即时赔的变化百分比
    
    Args:
        open_odds: 初赔
        live_odds: 即时赔
    
    Returns:
        {"H": 0.048, "D": -0.032, "A": -0.029}
    """
    return {
        k: (live_odds[k] - open_odds[k]) / open_odds[k] if open_odds[k] != 0 else 0.0
        for k in ["H", "D", "A"]
    }


def rtp(odds: Dict[str, float]) -> float:
    """
    计算返还率（RTP - Return To Player）
    
    Args:
        odds: 赔率字典
    
    Returns:
        返还率，例如 0.9167 表示 91.67%
    """
    s = (1.0 / odds["H"] if odds["H"] != 0 else 0.0) + \
        (1.0 / odds["D"] if odds["D"] != 0 else 0.0) + \
        (1.0 / odds["A"] if odds["A"] != 0 else 0.0)
    
    if s == 0:
        return 1.0
    
    return 1.0 / s


def pick_fav_dog(M: Dict[str, float]) -> Dict[str, str]:
    """
    自动识别热门方向（fav）和冷门方向（dog）
    基于骨架点：低赔方向天然更热
    
    Args:
        M: 骨架点 {"H": 1.785, "D": 3.66, "A": 4.31}
    
    Returns:
        {"fav": "H", "dog": "A"} 或 {"fav": "A", "dog": "H"}
    """
    # 排除平局，只看胜负项
    if M["H"] <= M["A"]:
        fav = "H"
        dog = "A"
    else:
        fav = "A"
        dog = "H"
    
    return {"fav": fav, "dog": dog}


def compute_all_features(
    skeleton: Dict,
    odds_open: Dict[str, float],
    odds_live: Dict[str, float]
) -> Dict:
    """
    计算所有特征值
    
    Returns:
        包含所有计算结果的字典
    """
    # 1. 骨架点和宽度
    M, W = skeleton_point_and_width(skeleton)
    
    # 2. 赔率偏移
    d_open = delta_odds(odds_open, M)
    d_live = delta_odds(odds_live, M)
    
    # 3. Z-score
    z_live = z_score(odds_live, M, W)
    
    # 4. 隐含概率
    p_skeleton = implied_probs(M)
    p_open = implied_probs(odds_open)
    p_live = implied_probs(odds_live)
    
    # 5. 概率偏移
    dp_open = {k: p_open[k] - p_skeleton[k] for k in ["H", "D", "A"]}
    dp_live = {k: p_live[k] - p_skeleton[k] for k in ["H", "D", "A"]}
    
    # 6. 变盘幅度
    dmove = delta_move(odds_open, odds_live)
    
    # 7. 返还率
    rtp_open = rtp(odds_open)
    rtp_live = rtp(odds_live)
    
    # 8. 热/冷方向
    fd = pick_fav_dog(M)
    
    return {
        "skeleton_point": M,
        "skeleton_width": W,
        "delta_odds_open": d_open,
        "delta_odds_live": d_live,
        "z_live": z_live,
        "p_skeleton": p_skeleton,
        "p_open": p_open,
        "p_live": p_live,
        "delta_p_open": dp_open,
        "delta_p_live": dp_live,
        "delta_move": dmove,
        "rtp_open": rtp_open,
        "rtp_live": rtp_live,
        "fav": fd["fav"],
        "dog": fd["dog"]
    }


