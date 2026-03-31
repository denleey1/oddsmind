#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置管理
"""

import os
from pathlib import Path
from typing import Dict, Any
import yaml


class Config:
    """配置类"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.ruleset_path = self.project_root / "application" / "services" / "odds_intent_v2" / "rulesets" / "ruleset_v2.yaml"
        
        # 默认阈值
        self.default_thresholds = {
            "real": -0.08,
            "real_soft": -0.05,  # 轻实阈值（-5%）
            "tao": 0.08,
            "draw_spill_pp": 0.02,
            "draw_block_pp": -0.02,
            "move_confirm": -0.03,
            "move_reverse": 0.03,
        }
        
        # 默认权重
        self.default_weights = {
            "w_real": 1.0,
            "w_tao": 0.8,
            "w_draw_spill": 0.4,
            "w_move_confirm": 0.6,
            "w_tail_penalty": -0.2,
        }
        
        # RTP范围
        self.rtp_min = float(os.getenv("RTP_MIN", "0.86"))
        self.rtp_max = float(os.getenv("RTP_MAX", "0.98"))
        
        # 加载规则集
        self._ruleset = None
        self._load_ruleset()
    
    def _load_ruleset(self):
        """加载规则集"""
        if self.ruleset_path.exists():
            with open(self.ruleset_path, 'r', encoding='utf-8') as f:
                self._ruleset = yaml.safe_load(f)
        else:
            # 使用默认规则集
            self._ruleset = {
                "version": "v2.0",
                "thresholds": self.default_thresholds,
                "weights": self.default_weights,
                "stageA_structure": [],
                "stageB_solutions": [],
                "stageC_decision": []
            }
    
    def reload_ruleset(self):
        """重新加载规则集（热更新）"""
        self._load_ruleset()
    
    def get_ruleset(self) -> Dict[str, Any]:
        """获取规则集"""
        return self._ruleset
    
    def get_thresholds(self) -> Dict[str, float]:
        """获取阈值"""
        return self._ruleset.get("thresholds", self.default_thresholds)
    
    def get_weights(self) -> Dict[str, float]:
        """获取权重"""
        return self._ruleset.get("weights", self.default_weights)


# 全局配置实例
config = Config()

