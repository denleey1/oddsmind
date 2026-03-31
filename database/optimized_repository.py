#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Optimized Repository Classes - 数据库专家级优化版本
解决事务管理、并发安全、性能瓶颈等关键问题
"""

from typing import Any, Dict, List, Optional, Tuple
import threading
import time
from abc import ABC

from .connection import get_connection
from .models import CompanyModel, OddsModel, BaseModel
from core.logger import get_logger
from core.exceptions import DatabaseError
from .optimized_repository_ops import (
    atomic_upsert_impl,
    batch_atomic_upsert_impl,
    execute_batch_upsert_impl,
    optimized_find_by_criteria_impl,
    safe_find_or_create_impl,
)
from .optimized_repository_company_ops import (
    create_missing_companies_impl,
    ensure_all_companies_exist_impl,
    get_existing_companies_impl,
    get_match_odds_with_stats_impl,
)


class OptimizedBaseRepository(ABC):
    """优化的基础仓库类 - 解决事务管理和并发问题"""

    def __init__(self, model_class: type, table_name: str):
        self.model_class = model_class
        self.table_name = table_name
        self.db = get_connection()
        self.logger = get_logger(f"optimized_repo.{table_name}")

        # 线程安全锁 - 保护关键操作
        self._operation_lock = threading.RLock()

        # 性能统计
        self._operation_stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "avg_operation_time": 0.0,
        }

    def atomic_upsert(self, model: BaseModel, conflict_columns: List[str]) -> int:
        """
        原子化的插入或更新操作 - 使用数据库事务确保数据一致性
        解决原有upsert方法的竞态条件问题
        """
        with self._operation_lock:
            return atomic_upsert_impl(self, model, conflict_columns)

    def batch_atomic_upsert(
        self,
        models: List[BaseModel],
        conflict_columns: List[str],
        batch_size: int = 100,
    ) -> int:
        """
        批量原子化插入或更新 - 优化的批处理操作
        使用事务确保批量操作的原子性
        """
        with self._operation_lock:
            return batch_atomic_upsert_impl(self, models, conflict_columns, batch_size)

    def _execute_batch_upsert(self, batch: List[BaseModel], conflict_columns: List[str]) -> int:
        """执行单个批次的原子化更新插入"""
        return execute_batch_upsert_impl(self, batch, conflict_columns)

    def safe_find_or_create(self, model: BaseModel, unique_columns: List[str]) -> Tuple[BaseModel, bool]:
        """
        安全的查找或创建操作
        返回: (model_instance, created_flag)
        """
        with self._operation_lock:
            return safe_find_or_create_impl(self, model, unique_columns)

    def optimized_find_by_criteria(
        self,
        criteria: Dict[str, Any],
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        use_index_hint: Optional[str] = None,
    ) -> List[BaseModel]:
        """
        优化的条件查询 - 支持索引提示和查询优化
        """
        return optimized_find_by_criteria_impl(self, criteria, limit, order_by, use_index_hint)

    def _update_operation_stats(self, success: bool, operation_time: float):
        """更新操作统计信息"""
        self._operation_stats["total_operations"] += 1

        if success:
            self._operation_stats["successful_operations"] += 1
        else:
            self._operation_stats["failed_operations"] += 1

        total = self._operation_stats["total_operations"]
        current_avg = self._operation_stats["avg_operation_time"]
        new_avg = ((current_avg * (total - 1)) + operation_time) / total
        self._operation_stats["avg_operation_time"] = new_avg

    def get_operation_stats(self) -> Dict[str, Any]:
        """获取操作统计信息"""
        return self._operation_stats.copy()

    def _get_primary_key_column(self) -> str:
        """获取主键列名"""
        if hasattr(self.model_class, "__dataclass_fields__"):
            fields = list(self.model_class.__dataclass_fields__.keys())
            for field in ["id", f"{self.table_name}_id", f"{self.table_name.rstrip('s')}_id"]:
                if field in fields:
                    return field
        return "id"


class OptimizedOddsRepository(OptimizedBaseRepository):
    """优化的赔率仓库 - 专门处理赔率数据的高性能操作"""

    def __init__(self):
        super().__init__(OddsModel, "european_odds")

        # 赔率特定的性能配置
        self._batch_size = 200
        self._company_cache = {}
        self._cache_lock = threading.Lock()

    def bulk_upsert_odds_with_company_validation(
        self,
        odds_list: List[OddsModel],
        ensure_companies: bool = True,
    ) -> int:
        """
        批量插入赔率数据，并确保相关公司存在
        这是针对你的外键约束问题的专门解决方案
        """
        if not odds_list:
            return 0

        start_time = time.time()

        try:
            if ensure_companies:
                self._ensure_all_companies_exist(odds_list)

            total_affected = self.batch_atomic_upsert(
                odds_list,
                ["match_id", "company_id"],
                batch_size=self._batch_size,
            )

            execution_time = time.time() - start_time
            self.logger.info(
                "Bulk odds upsert completed: %s records in %.2fs (%.1f records/sec)",
                total_affected,
                execution_time,
                total_affected / execution_time if execution_time else 0.0,
            )

            return total_affected
        except Exception as exc:
            self.logger.error(f"Bulk odds upsert failed: {exc}")
            raise DatabaseError(f"Bulk odds upsert failed: {str(exc)}")

    def _ensure_all_companies_exist(self, odds_list: List[OddsModel]):
        """
        确保所有赔率数据中引用的公司都存在于数据库中
        解决外键约束违反的问题
        """
        ensure_all_companies_exist_impl(self, odds_list)

    def _get_existing_companies(self, company_ids: List[int]) -> set:
        """查询数据库中已存在的公司ID"""
        return get_existing_companies_impl(self, company_ids)

    def _create_missing_companies(self, company_ids: set):
        """创建缺失的公司记录"""
        create_missing_companies_impl(self, company_ids)

    def get_match_odds_with_stats(self, match_id: int) -> Dict[str, Any]:
        """获取比赛赔率及统计信息"""
        return get_match_odds_with_stats_impl(self, match_id)


class OptimizedCompanyRepository(OptimizedBaseRepository):
    """优化的公司仓库 - 处理公司数据的并发安全操作"""

    def __init__(self):
        super().__init__(CompanyModel, "companies")

        # 公司名称唯一性缓存
        self._name_cache = set()
        self._cache_lock = threading.Lock()

    def safe_create_company(self, company: CompanyModel) -> Tuple[CompanyModel, bool]:
        """
        安全创建公司 - 解决重复名称的问题
        返回: (company_model, created_flag)
        """
        with self._cache_lock:
            try:
                if company.name_en in self._name_cache:
                    existing = self.optimized_find_by_criteria({"name_en": company.name_en}, limit=1)
                    if existing:
                        return existing[0], False

                result, created = self.safe_find_or_create(company, ["company_id"])
                if created:
                    self._name_cache.add(company.name_en)

                return result, created
            except Exception as exc:
                self.logger.error(f"Safe create company failed: {exc}")
                raise DatabaseError(f"Safe create company failed: {str(exc)}")

    def create_many(self, companies: List[CompanyModel]) -> int:
        """
        批量创建公司记录

        Args:
            companies: 要创建的公司模型列表

        Returns:
            成功创建的记录数
        """
        if not companies:
            return 0

        try:
            return self.batch_atomic_upsert(companies, ["company_id"], batch_size=50)
        except Exception as exc:
            self.logger.error(f"Batch create companies failed: {exc}")
            raise DatabaseError(f"Batch create companies failed: {str(exc)}")


def create_optimized_repositories() -> Dict[str, OptimizedBaseRepository]:
    """创建所有优化的仓库实例"""
    return {
        "odds": OptimizedOddsRepository(),
        "companies": OptimizedCompanyRepository(),
    }
