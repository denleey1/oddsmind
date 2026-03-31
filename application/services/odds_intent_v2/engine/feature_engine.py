#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L0-L1-L2: 数据校验、骨架建模、特征计算引擎
"""

from typing import Dict, Tuple, Optional, List
from decimal import Decimal
import math

from core.logger import get_logger
from application.services.odds_intent_v2.config import config

logger = get_logger(__name__)


class FeatureEngine:
    """特征计算引擎"""
    
    def __init__(self):
        self.config = config
        self.rtp_min = config.rtp_min
        self.rtp_max = config.rtp_max
    
    def validate_and_compute(
        self,
        skeleton: Dict,
        odds_open: Optional[Dict[str, float]],
        odds_live: Dict[str, float],
        book_name: str = "default"
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        L0: 数据校验 + L1: 骨架建模 + L2: 特征计算
        
        Returns:
            (features_dict, error_message)
            如果校验失败，返回 (None, error_message)
        """
        # L0: 数据校验
        error = self._validate_input(skeleton, odds_live, odds_open)
        if error:
            return None, error
        
        # L1: 骨架建模
        M, W = self._skeleton_modeling(skeleton)
        
        # L2: 特征计算
        features = self._compute_features(M, W, odds_open, odds_live)
        
        return features, None
    
    def _validate_input(
        self,
        skeleton: Dict,
        odds_live: Dict[str, float],
        odds_open: Optional[Dict[str, float]]
    ) -> Optional[str]:
        """L0: 数据校验"""
        # 1. 校验骨架
        if skeleton.get("type") == "range":
            for key in ["H", "D", "A"]:
                if key not in skeleton:
                    return f"骨架缺少{key}字段"
                if not isinstance(skeleton[key], list) or len(skeleton[key]) != 2:
                    return f"骨架{key}必须是包含两个值的列表"
                if skeleton[key][0] >= skeleton[key][1]:
                    return f"骨架{key}区间下限必须小于上限"
                if skeleton[key][0] <= 1.01:
                    return f"骨架{key}下限必须大于1.01"
        elif skeleton.get("type") == "point":
            for key in ["H", "D", "A"]:
                if key not in skeleton:
                    return f"骨架缺少{key}字段"
                if skeleton[key] <= 1.01:
                    return f"骨架{key}必须大于1.01"
        else:
            return f"骨架type必须是range或point，当前为{skeleton.get('type')}"
        
        # 2. 校验即时赔率
        for key in ["H", "D", "A"]:
            if key not in odds_live:
                return f"即时赔率缺少{key}字段"
            if odds_live[key] <= 1.01:
                return f"即时赔率{key}必须大于1.01"
        
        # 3. 校验初赔（如果提供）
        if odds_open:
            for key in ["H", "D", "A"]:
                if key not in odds_open:
                    return f"初赔缺少{key}字段"
                if odds_open[key] <= 1.01:
                    return f"初赔{key}必须大于1.01"
        
        # 4. 校验RTP
        rtp_live = self._calculate_rtp(odds_live)
        if rtp_live < self.rtp_min or rtp_live > self.rtp_max:
            return f"即时赔率RTP({rtp_live:.4f})超出合理范围[{self.rtp_min}, {self.rtp_max}]"
        
        if odds_open:
            rtp_open = self._calculate_rtp(odds_open)
            if rtp_open < self.rtp_min or rtp_open > self.rtp_max:
                return f"初赔RTP({rtp_open:.4f})超出合理范围[{self.rtp_min}, {self.rtp_max}]"
        
        return None
    
    def _skeleton_modeling(self, skeleton: Dict) -> Tuple[Dict[str, float], Optional[Dict[str, float]]]:
        """
        L1: 骨架建模
        将骨架区间或点转换为可计算的参照系
        
        Returns:
            (M, W): M是骨架点字典，W是宽度字典（如果是点则为None）
        """
        if skeleton.get("type") == "range":
            M = {
                k: (skeleton[k][0] + skeleton[k][1]) / 2.0
                for k in ["H", "D", "A"]
            }
            W = {
                k: skeleton[k][1] - skeleton[k][0]
                for k in ["H", "D", "A"]
            }
            return M, W
        else:  # point
            M = {
                k: float(skeleton[k])
                for k in ["H", "D", "A"]
            }
            return M, None
    
    def _compute_features(
        self,
        M: Dict[str, float],
        W: Optional[Dict[str, float]],
        odds_open: Optional[Dict[str, float]],
        odds_live: Dict[str, float]
    ) -> Dict:
        """
        L2: 特征计算
        计算所有特征值
        """
        # 5.1 Δodds（赔率偏移）
        delta_odds_live = self._delta_odds(odds_live, M)
        delta_odds_open = self._delta_odds(odds_open, M) if odds_open else None
        
        # 5.2 Z（区间标准化偏移）
        z_live = self._z_score(odds_live, M, W)
        
        # 5.3 去水概率 p 与 Δp
        p_skeleton = self._implied_probs(M)
        p_live = self._implied_probs(odds_live)
        p_open = self._implied_probs(odds_open) if odds_open else None
        
        delta_p_live = {
            k: p_live[k] - p_skeleton[k]
            for k in ["H", "D", "A"]
        }
        delta_p_open = {
            k: p_open[k] - p_skeleton[k]
            for k in ["H", "D", "A"]
        } if p_open else None
        
        # 5.4 变盘 Δmove
        delta_move = self._delta_move(odds_open, odds_live) if odds_open else None
        
        # RTP
        rtp_live = self._calculate_rtp(odds_live)
        rtp_open = self._calculate_rtp(odds_open) if odds_open else None
        
        # 识别fav/dog（热门/冷门方向）
        fav, dog = self._pick_fav_dog(M)
        
        return {
            "skeleton_point": M,
            "skeleton_width": W,
            "odds_live": odds_live,  # 保存原始赔率用于尾巴阻尼计算
            "odds_open": odds_open if odds_open else None,
            "delta_odds_open": delta_odds_open,
            "delta_odds_live": delta_odds_live,
            "z_live": z_live,
            "p_skeleton": p_skeleton,
            "p_open": p_open,
            "p_live": p_live,
            "delta_p_open": delta_p_open,
            "delta_p_live": delta_p_live,
            "delta_move": delta_move,
            "rtp_open": rtp_open,
            "rtp_live": rtp_live,
            "fav": fav,
            "dog": dog
        }
    
    def _delta_odds(self, odds: Dict[str, float], M: Dict[str, float]) -> Dict[str, float]:
        """计算赔率偏移（Δodds）"""
        return {
            k: (odds[k] - M[k]) / M[k] if M[k] != 0 else 0.0
            for k in ["H", "D", "A"]
        }
    
    def _z_score(
        self,
        odds: Dict[str, float],
        M: Dict[str, float],
        W: Optional[Dict[str, float]]
    ) -> Optional[Dict[str, float]]:
        """计算区间标准化偏移（Z-score）"""
        if W is None:
            return None
        
        eps = 1e-9
        return {
            k: (odds[k] - M[k]) / max(W[k], eps)
            for k in ["H", "D", "A"]
        }
    
    def _implied_probs(self, odds: Dict[str, float]) -> Dict[str, float]:
        """计算去水隐含概率（p）"""
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
    
    def _delta_move(
        self,
        odds_open: Optional[Dict[str, float]],
        odds_live: Dict[str, float]
    ) -> Optional[Dict[str, float]]:
        """计算变盘幅度（Δmove）"""
        if not odds_open:
            return None
        
        return {
            k: (odds_live[k] - odds_open[k]) / odds_open[k] if odds_open[k] != 0 else 0.0
            for k in ["H", "D", "A"]
        }
    
    def _calculate_rtp(self, odds: Dict[str, float]) -> float:
        """计算返还率（RTP）"""
        s = (1.0 / odds["H"] if odds["H"] != 0 else 0.0) + \
            (1.0 / odds["D"] if odds["D"] != 0 else 0.0) + \
            (1.0 / odds["A"] if odds["A"] != 0 else 0.0)
        
        if s == 0:
            return 1.0
        
        return 1.0 / s
    
    def _pick_fav_dog(self, M: Dict[str, float]) -> Tuple[str, str]:
        """自动识别热门方向（fav）和冷门方向（dog）"""
        # 排除平局，只看胜负项
        if M["H"] <= M["A"]:
            fav = "H"
            dog = "A"
        else:
            fav = "A"
            dog = "H"
        
        return fav, dog

