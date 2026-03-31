#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主分析器：整合所有引擎
"""

from typing import Dict, Optional, List
from core.logger import get_logger
from application.services.odds_intent_v2.schemas import (
    AnalyzeRequest, AnalyzeResponse, PrimaryOutput, IntentOutput,
    ComputedFeatures, BooksOutput, DebugInfo, Solution
)
from application.services.odds_intent_v2.engine.feature_engine import FeatureEngine
from application.services.odds_intent_v2.engine.draw_engine import DrawEngine
from application.services.odds_intent_v2.engine.intent_engine import IntentEngine
from application.services.odds_intent_v2.engine.rule_engine import RuleEngine
from application.services.odds_intent_v2.engine.postprocess import PostProcessor
from application.services.odds_intent_v2.engine.explain import ExplainEngine
from application.services.odds_intent_v2.engine.books_engine import BooksEngine
from application.services.odds_intent_v2.config import config

logger = get_logger(__name__)


class OddsIntentAnalyzer:
    """欧赔意图分析器"""
    
    def __init__(self):
        self.feature_engine = FeatureEngine()
        self.draw_engine = DrawEngine()
        self.intent_engine = IntentEngine()
        self.rule_engine = RuleEngine()
        self.postprocessor = PostProcessor()
        self.explain_engine = ExplainEngine()
        self.books_engine = BooksEngine()
        self.config = config
    
    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """
        执行完整分析流程
        
        Args:
            request: 分析请求
        
        Returns:
            分析响应
        """
        try:
            # 单公司模式
            if not request.is_multi_book():
                return self._analyze_single_book(request)
            else:
                # 多公司模式
                return self._analyze_multi_books(request)
        except Exception as e:
            logger.error(f"分析失败: {e}", exc_info=True)
            return self._create_error_response(request.match_id, str(e))
    
    def _analyze_single_book(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """单公司分析"""
        # L0-L2: 数据校验和特征计算
        features, error = self.feature_engine.validate_and_compute(
            request.skeleton,
            request.odds_open.dict() if request.odds_open else None,
            request.odds_live.dict() if request.odds_live else None
        )
        
        if error:
            return self._create_nobet_response(request.match_id, error)
        
        # L3: 平赔桥梁与分散结构
        draw_structure = self.draw_engine.analyze_draw_structure(features)
        
        # L4: 更优解与庄家意图
        intent_result = self.intent_engine.analyze_intent(features, draw_structure)
        
        # 规则引擎
        rule_result = self.rule_engine.execute(features, draw_structure, intent_result)
        
        # 后处理
        # 先计算基础置信度（优先使用规则输出的confidence_base，否则基于solutions的分数）
        base_confidence = rule_result.get("confidence_base")
        if base_confidence is None:
            base_confidence = 50
            solutions = intent_result.get("solutions", [])
            if solutions:
                best_solution = max(solutions, key=lambda s: s.score)
                base_confidence = int(best_solution.score * 100)
        
        # 确定使用的solution（用于确认分计算）
        solution_name = None
        final_pick = rule_result.get("final_pick")
        if final_pick:
            solutions = intent_result.get("solutions", [])
            for sol in solutions:
                if sol.target == final_pick:
                    solution_name = sol.name
                    break
        
        postprocess_result = self.postprocessor.process(
            features,
            intent_result,
            final_pick,
            base_confidence,
            solution_name
        )
        
        # 检查NoBet条件
        nobet_reason = self.postprocessor.check_nobet_conditions(
            features, intent_result, draw_structure
        )
        if nobet_reason:
            return self._create_nobet_response(request.match_id, nobet_reason)
        
        # 解释生成（优先使用规则输出的explain，否则使用引擎生成）
        explain_list = rule_result.get("explain")
        if not explain_list:
            explain_list = self.explain_engine.generate(
                features, draw_structure, intent_result, rule_result, postprocess_result
            )
        
        # 组装响应
        return self._build_response(
            request.match_id,
            features,
            draw_structure,
            intent_result,
            rule_result,
            postprocess_result,
            explain_list
        )
    
    def _analyze_multi_books(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """多公司分析"""
        book_results = []
        all_features = []
        
        # 对每个公司独立分析
        for book_input in request.books:
            features, error = self.feature_engine.validate_and_compute(
                request.skeleton,
                book_input.odds_open.dict(),
                book_input.odds_live.dict(),
                book_input.book
            )
            
            if error:
                logger.warning(f"公司 {book_input.book} 分析失败: {error}")
                continue
            
            all_features.append(features)
            
            # 快速分析（简化版）
            draw_structure = self.draw_engine.analyze_draw_structure(features)
            intent_result = self.intent_engine.analyze_intent(features, draw_structure)
            rule_result = self.rule_engine.execute(features, draw_structure, intent_result)
            
            book_results.append({
                "book": book_input.book,
                "pick": rule_result.get("final_pick"),
                "pattern": rule_result.get("structure"),
                "confidence": 50  # 简化
            })
        
        if not book_results:
            return self._create_nobet_response(request.match_id, "所有公司数据校验失败")
        
        # 多公司一致性分析
        books_output = self.books_engine.analyze_consensus(book_results)
        
        # 使用第一个有效公司的详细分析作为主结果
        main_features = all_features[0]
        draw_structure = self.draw_engine.analyze_draw_structure(main_features)
        intent_result = self.intent_engine.analyze_intent(main_features, draw_structure)
        rule_result = self.rule_engine.execute(main_features, draw_structure, intent_result)
        
        # 结合多公司共识调整
        consensus_score = books_output.consensus_score
        if consensus_score < 0.5 and intent_result.get("two_solutions", False):
            return self._create_nobet_response(
                request.match_id,
                "多公司不一致且双更优解"
            )
        
        postprocess_result = self.postprocessor.process(
            main_features,
            intent_result,
            rule_result.get("final_pick"),
            50
        )
        
        explain_list = self.explain_engine.generate(
            main_features, draw_structure, intent_result, rule_result, postprocess_result
        )
        
        # 组装响应（包含多公司信息）
        response = self._build_response(
            request.match_id,
            main_features,
            draw_structure,
            intent_result,
            rule_result,
            postprocess_result,
            explain_list
        )
        response.books = books_output
        
        return response
    
    def _build_response(
        self,
        match_id: str,
        features: Dict,
        draw_structure: Dict,
        intent_result: Dict,
        rule_result: Dict,
        postprocess_result: Dict,
        explain_list: List[str]
    ) -> AnalyzeResponse:
        """组装响应"""
        final_pick = rule_result.get("final_pick")
        status = postprocess_result.get("status", "ok")
        
        # Primary输出
        pick_market = self._determine_market_pick(final_pick, draw_structure, intent_result, rule_result)
        hedge = self._determine_hedge(final_pick, draw_structure, intent_result)
        
        primary = PrimaryOutput(
            pick_1x2=final_pick,
            pick_market=pick_market,
            hedge=hedge,
            confidence=postprocess_result.get("confidence", 50)
        )
        
        # Intent输出（优先使用规则输出的intent，否则使用structure）
        solutions = intent_result.get("solutions", [])
        intent_summary = rule_result.get("intent")
        if not intent_summary:
            intent_summary = rule_result.get("structure", "未识别明确结构")
        
        intent = IntentOutput(
            summary=intent_summary,
            tags=rule_result.get("tags", []),
            solutions=solutions,
            two_solutions=intent_result.get("two_solutions", False),
            draw_role=draw_structure.get("draw_role", "neutral"),
            structure=draw_structure.get("structure")
        )
        
        # Computed特征
        tail_penalty = postprocess_result.get("tail_penalty", {})
        computed = ComputedFeatures(
            skeleton_point=features.get("skeleton_point", {}),
            delta_odds_live=features.get("delta_odds_live", {}),
            delta_p_live=features.get("delta_p_live", {}),
            delta_move=features.get("delta_move"),
            z_live=features.get("z_live"),
            rtp_live=features.get("rtp_live", 0.9),
            tail_penalty=tail_penalty if tail_penalty else None
        )
        
        # Debug信息
        debug = DebugInfo(
            matched_rule=rule_result.get("matched_rules", [""])[0] if rule_result.get("matched_rules") else None,
            rule_trace=rule_result.get("matched_rules", [])
        )
        
        return AnalyzeResponse(
            match_id=match_id,
            ruleset_version=config.get_ruleset().get("version", "v2.0"),
            status=status,
            primary=primary,
            intent=intent,
            computed=computed,
            explain=explain_list,
            debug=debug
        )
    
    def _determine_market_pick(
        self,
        pick: Optional[str],
        draw_structure: Dict,
        intent_result: Dict,
        rule_result: Optional[Dict] = None
    ) -> str:
        """确定市场推荐"""
        # 优先使用规则输出的market_pick
        if rule_result and rule_result.get("market_pick"):
            return rule_result.get("market_pick")
        
        if not pick:
            return "1X2"
        
        exclude = intent_result.get("exclude", [])
        
        if "D" in exclude:
            return "12"  # 排除平局
        elif pick == "D":
            return "1X2"
        elif pick == "H":
            return "1X"  # 主胜或平
        elif pick == "A":
            return "X2"  # 平或客胜
        else:
            return "1X2"
    
    def _determine_hedge(
        self,
        pick: Optional[str],
        draw_structure: Dict,
        intent_result: Dict
    ) -> str:
        """确定防守建议"""
        if not pick:
            return "none"
        
        exclude = intent_result.get("exclude", [])
        if "D" in exclude:
            return "none"
        
        draw_role = draw_structure.get("draw_role", "neutral")
        
        if draw_role == "spill":
            return "D"  # 平分洪，防守平
        elif pick == "H":
            return "1X"
        elif pick == "A":
            return "X2"
        else:
            return "none"
    
    def _create_nobet_response(self, match_id: str, reason: str) -> AnalyzeResponse:
        """创建NoBet响应"""
        return AnalyzeResponse(
            match_id=match_id,
            ruleset_version=config.get_ruleset().get("version", "v2.0"),
            status="nobet",
            primary=PrimaryOutput(),
            intent=IntentOutput(summary=f"NoBet: {reason}"),
            computed=ComputedFeatures(
                skeleton_point={},
                delta_odds_live={},
                delta_p_live={},
                rtp_live=0.9
            ),
            explain=[f"无法判定：{reason}"]
        )
    
    def _create_error_response(self, match_id: str, error: str) -> AnalyzeResponse:
        """创建错误响应"""
        return AnalyzeResponse(
            match_id=match_id,
            ruleset_version=config.get_ruleset().get("version", "v2.0"),
            status="nobet",
            primary=PrimaryOutput(),
            intent=IntentOutput(summary=f"分析失败：{error}"),
            computed=ComputedFeatures(
                skeleton_point={},
                delta_odds_live={},
                delta_p_live={},
                rtp_live=0.9
            ),
            explain=[f"错误：{error}"]
        )

