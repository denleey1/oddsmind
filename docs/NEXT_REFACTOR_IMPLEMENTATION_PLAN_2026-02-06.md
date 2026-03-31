# 下一阶段重构实施方案（不改功能版）

日期：2026-02-06  
状态：待执行（你回来后可直接按此推进）

## 1. 总目标
- 继续深度治理代码负债，进一步拆解大文件和混合职责模块。
- 严格保持功能 100% 一致，不新增/删除业务能力。
- 保持数据库结构不变（不做 DDL、不做迁移）。
- 保持现有 API 路由契约不变（含小程序既有接口）。

## 2. 硬约束（必须全程满足）
- 不改数据库 schema。
- 不改路由路径、方法、入参/出参字段语义。
- 仅做“结构重组 + 代码下沉 + 依赖解耦”。
- 每个子阶段必须通过三道闸门后才能进入下一阶段：
  1. `python -m unittest discover -s tests\architecture -p "test_*.py"`
  2. `python scripts/check_module_size_budget.py`
  3. `python scripts/check_route_contract.py`

## 3. 当前基线（用于验收对比）
- 已完成多轮治理：`manager`、`monitoring_coordinator`、`web_*`、`auto_rule_matcher`、`rule_match_api` 等已拆分。
- 关键校验当前全绿：
  - 架构测试：52/52 通过
  - 模块预算：通过（41 文件）
  - 路由契约：通过（23 routes）

## 4. 下一轮优先级与范围

### P0（先做）
- `database/optimized_repository.py`（588 行）
- `database/enhanced_manager.py`（477 行）
- `database/batch_writer.py`（453 行）

### P1（随后）
- `database/models.py`（530 行，按领域拆分但保留向后兼容导出）
- `application/services/task_health_tracker.py`（479 行）
- `services/league_status_monitor.py`（421 行）

### P2（可选收尾）
- `application/services/match_detail_optimized.py`（421 行）
- `application/services/odds_intent_v2/engine/rule_engine.py`（380 行）

## 5. 执行策略（统一模板）

每个目标模块按同一模板执行，避免失控：

1. **职责切片**  
将“查询/写入/编排/格式化/统计/重试”拆到独立 `*_ops.py` 或 `*_helpers.py`。

2. **兼容外壳保留**  
原模块保留原函数/类/方法签名，内部改为委派新模块。

3. **防回退测试**  
新增 `tests/architecture/test_*_extraction*.py`，用 AST 锁定：
- helper 模块 import 存在；
- 关键方法已委派到 helper。

4. **预算与文档同步**  
更新：
- `tests/architecture/baselines/module_size_budget_v1.json`
- `docs/ARCHITECTURE_GUARDRAILS.md`

5. **强制闸门校验**  
三道闸门全部通过才算完成该模块。

## 6. 分阶段实施清单

### 阶段 A：数据库执行链路解耦（P0）
- A1：`optimized_repository` 拆成 CRUD helper + SQL builder helper + 批处理 helper。
- A2：`enhanced_manager` 拆成健康诊断/修复动作/统计输出三层。
- A3：`batch_writer` 拆成队列协议、flush 执行器、容错重试器。
- A4：给 A1~A3 分别补 extraction guard。

完成标准：
- 以上 3 文件总行数下降 >= 25%。
- 对外类与方法签名不变。

### 阶段 B：模型与状态管理清晰化（P1）
- B1：`models.py` 按领域拆分为 `models_core.py / models_odds.py / models_analysis.py`。
- B2：保留 `database/models.py` 作为兼容导出 façade（`from ... import *` 或显式 `__all__`）。
- B3：补模型导出兼容测试（确保旧 import 不失效）。

完成标准：
- 旧代码 `from database.models import X` 无需改动即可运行。
- 路由契约与架构测试全绿。

### 阶段 C：服务层监控治理（P1）
- C1：`task_health_tracker` 下沉 Redis 读写、状态聚合、健康判定。
- C2：`league_status_monitor` 下沉扫描策略、联赛状态转换、日志统计。
- C3：补 extraction guard 和最小行为回归测试。

完成标准：
- 模块职责单一，可读性提升，且无接口漂移。

## 7. 风险点与控制
- 风险：委派遗漏导致分支逻辑变更。  
控制：每次切片后先补 guard 再跑全量架构测试。

- 风险：模型拆分导致导入路径失效。  
控制：先做兼容导出层，再替换内部 import。

- 风险：批处理/重试链路重构引入时序差异。  
控制：仅重构结构，不改阈值和重试策略参数。

## 8. 验收标准（最终）
- 无数据库 schema 变更。
- 路由契约 100% 一致（23 routes 无差异）。
- 架构测试与预算检查全通过。
- 新增 guard 覆盖所有本轮新拆模块。

## 9. 你回来后的第一步
- 直接从 **阶段 A / A1 (`database/optimized_repository.py`)** 开始。
- 先做最小切片（1 个 helper + 1 个 guard + 三道闸门），确认节奏后再扩大到 A2/A3。

