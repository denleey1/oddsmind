#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pydantic 数据模型定义
"""

from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field, validator


class SkeletonRange(BaseModel):
    """骨架区间"""
    type: Literal["range"] = "range"
    H: List[float] = Field(..., min_items=2, max_items=2)
    D: List[float] = Field(..., min_items=2, max_items=2)
    A: List[float] = Field(..., min_items=2, max_items=2)
    
    @validator('H', 'D', 'A')
    def validate_range(cls, v):
        if len(v) != 2:
            raise ValueError('区间必须包含两个值 [low, high]')
        if v[0] >= v[1]:
            raise ValueError('区间下限必须小于上限')
        return v


class SkeletonPoint(BaseModel):
    """骨架点"""
    type: Literal["point"] = "point"
    H: float = Field(..., gt=1.0)
    D: float = Field(..., gt=1.0)
    A: float = Field(..., gt=1.0)


class OddsDict(BaseModel):
    """赔率字典"""
    H: float = Field(..., gt=1.01)
    D: float = Field(..., gt=1.01)
    A: float = Field(..., gt=1.01)


class BookInput(BaseModel):
    """单公司输入"""
    book: str
    odds_open: OddsDict
    odds_live: OddsDict


class MetaInfo(BaseModel):
    """元信息"""
    league: Optional[str] = None
    zone: Optional[str] = None
    match_time: Optional[str] = None


class AnalyzeRequest(BaseModel):
    """分析请求"""
    match_id: str
    skeleton: Dict[str, Any]  # SkeletonRange 或 SkeletonPoint
    odds_open: Optional[OddsDict] = None  # 单公司模式
    odds_live: Optional[OddsDict] = None  # 单公司模式
    books: Optional[List[BookInput]] = None  # 多公司模式
    meta: Optional[MetaInfo] = None
    
    @validator('skeleton')
    def validate_skeleton(cls, v):
        if not isinstance(v, dict):
            raise ValueError('skeleton必须是字典')
        if 'type' not in v:
            raise ValueError('skeleton必须包含type字段')
        if v['type'] not in ['range', 'point']:
            raise ValueError('skeleton type必须是range或point')
        return v
    
    def is_multi_book(self) -> bool:
        """判断是否多公司模式"""
        return self.books is not None and len(self.books) > 0


class Solution(BaseModel):
    """更优解"""
    name: str  # "REAL_solution" 或 "TAO_solution"
    target: str  # "H" | "D" | "A"
    score: float = Field(..., ge=0.0, le=1.0)
    why: List[str] = []


class PrimaryOutput(BaseModel):
    """主要输出"""
    pick_1x2: Optional[str] = None  # "H" | "D" | "A" | None
    pick_market: str = "1X2"  # "1X" | "X2" | "12" | "1X2"
    hedge: str = "none"  # "D" | "none" | "1X" | "X2" | ...
    confidence: int = Field(0, ge=0, le=100)


class IntentOutput(BaseModel):
    """意图输出"""
    summary: str
    tags: List[str] = []
    solutions: List[Solution] = []
    two_solutions: bool = False
    draw_role: str = "neutral"  # "spill" | "block" | "valley" | "neutral"
    structure: Optional[str] = None  # "PullWinSplitDraw" | "DoubleSplitDraw" | ...


class ComputedFeatures(BaseModel):
    """计算特征"""
    skeleton_point: Dict[str, float]
    delta_odds_live: Dict[str, float]
    delta_p_live: Dict[str, float]
    delta_move: Optional[Dict[str, float]] = None
    z_live: Optional[Dict[str, float]] = None
    rtp_live: float
    tail_penalty: Optional[Dict[str, float]] = None


class BookResult(BaseModel):
    """单公司分析结果"""
    book: str
    pick: Optional[str] = None
    pattern: Optional[str] = None
    confidence: int = 0


class BooksOutput(BaseModel):
    """多公司输出"""
    consensus_score: float = Field(0.0, ge=0.0, le=1.0)
    divergence_score: float = Field(0.0, ge=0.0, le=1.0)
    per_book: List[BookResult] = []


class DebugInfo(BaseModel):
    """调试信息"""
    matched_rule: Optional[str] = None
    rule_trace: List[str] = []


class AnalyzeResponse(BaseModel):
    """分析响应"""
    match_id: str
    ruleset_version: str
    status: Literal["ok", "nobet", "low_confidence"]
    primary: PrimaryOutput
    intent: IntentOutput
    computed: ComputedFeatures
    books: Optional[BooksOutput] = None
    explain: List[str] = []
    debug: DebugInfo = DebugInfo()

