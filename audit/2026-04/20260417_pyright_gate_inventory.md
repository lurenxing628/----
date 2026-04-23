# 2026-04-17 Pyright 主链门禁盘点

## 范围

- 主链 gate 配置：`pyrightconfig.gate.json`
- 覆盖范围：`app.py`、`app_new_ui.py`、`config.py`、`core/`、`data/`、`web/`
- 全仓盘点配置：`pyrightconfig.json`

## 一、本轮已修并进入 gate 的主链问题

### 1. 配置快照与算法参数

- `core/algorithms/greedy/schedule_params.py`
- 根因：`used_params` 在 weighted 分支被推断成 `Dict[str, float]`，后续再写入 `dispatch_mode`、`dispatch_rule`、`auto_assign_enabled` 时报类型错误。
- 处理：显式声明 `used_params: Dict[str, Any]`，不改当前 `ScheduleConfigSnapshot` 单一事实源语义。

### 2. 宽输入 helper 与强契约边界

- `core/services/equipment/machine_service.py`
- `core/services/personnel/operator_service.py`
- `core/services/personnel/resource_team_service.py`
- `core/services/process/op_type_service.py`
- 根因：同一个 `_validate_*` helper 同时服务 `allow_partial=True` 的局部更新和 `create()` 的必填场景，返回类型被保守成 `Optional[...]`。
- 处理：只在 `create()` 的强契约入口增加显式非空收口，不修改 helper 本身的宽输入职责，也不修改 repo 签名。

### 3. 模型/仓储写库边界

- `core/models/schedule.py`
- `data/repositories/schedule_repo.py`
- `data/repositories/machine_downtime_repo.py`
- `data/repositories/schedule_history_repo.py`
- `core/services/equipment/machine_downtime_service.py`
- 根因：读侧模型允许 `None`，但写库或命令式操作默认这些字段必定存在。
- 处理：
  - `Schedule.version` 在 `from_row()` 出口保证为 `int`
  - `ScheduleRepository.create/bulk_create()` 在写库前对 `op_id` 做本地硬校验
  - `MachineDowntimeService.cancel()` 在执行取消前确认 `d.id` 非空
  - `MachineDowntimeRepository.create()` 与 `ScheduleHistoryRepository.allocate_next_version()` 用局部变量收窄 `lastrowid`

### 4. 关键链计算

- `core/services/scheduler/gantt_critical_chain.py`
- 根因：节点结构是 `Dict[str, Any]`，`.get()` 访问 `start/end` 时退化成 `Any | None`，导致 `<=` 比较和 `_fmt_dt()` 调用报错。
- 处理：新增 route-local 级别的 `_node_dt()` 收窄 helper，仅在比较和格式化点收口，不引入 `TypedDict` 重构。

### 5. 资源排班 route 层 query 契约

- `web/routes/domains/scheduler/scheduler_resource_dispatch.py`
- 根因：`request.args.to_dict(flat=True)` 与 `url_for(**dict)` 不符合当前 Flask 类型桩约束。
- 处理：
  - 显式遍历 `request.args` 归一化为 `Dict[str, str]`
  - 新增 route-local `_url_with_query()`、`_page_url()`、`_export_url()` helper
  - 保持 service 层 `build_page_context/get_dispatch_payload/build_export` 签名不变

### 6. 资源清理契约

- `core/infrastructure/database.py`
- `core/services/process/deletion_validator.py`
- 根因：
  - migration probe 清理阶段 `conn` 可能仍为 `None`
  - `_norm_status()` 调用点允许 `None`
- 处理：
  - `conn.close()` 改为先做空值守卫
  - `_norm_status(value: Any)` 接受真实调用面

## 二、全仓盘点中仍待后续收缩的类型债务

### 当前盘点结果

- `python -m pyright -p pyrightconfig.json`
- 结果：`169 errors`

### 代表性债务簇

- `tests/` 中大量契约测试直接 monkeypatch 模块私有符号、动态属性或 Flask route 导出，类型桩缺少对应声明。
- `tests/` 中多处 `url_for` 动态 kwargs、生成器 fixture 注解、`sqlite3.Connection` stub、伪对象协议不完整导致报错。
- 调度优化器相关测试大量依赖私有函数或模块级符号重绑定，当前公开符号面与类型桩不匹配。
- 少量工具/分析脚本仍存在 AST、可选值、第三方可选依赖未声明的问题。

### 本轮不处理原因

- 这些错误主要集中在 `tests/` 和边缘脚本，不属于当前主链 gate 范围。
- 大部分修复会涉及测试桩、导出面或私有 API 暴露策略，超出“先接入主链 pyright 门禁”的范围。

## 三、明确不纳入主链 gate 的边缘目录/脚本

- `tests/`
- `scripts/`
- `tools/`
- 各类一次性扫描、对账、文档生成脚本

说明：

- 这些目录仍保留在 `pyrightconfig.json` 中做全仓盘点。
- 但不进入 `pyrightconfig.gate.json`，避免把主链门禁和测试/工具层技术债混在一起。

## 验证结果

- `python -m pyright -p pyrightconfig.gate.json`
  - 结果：`0 errors`
- `python -m pytest -q tests/test_run_quality_gate.py`
  - 结果：`4 passed`
- `python -m pytest -q tests/test_schedule_params_direct_call_contract.py`
  - 结果：`8 passed`
- `python -m pytest -q tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py`
  - 结果：`4 passed`
- `python -m pytest -q tests/test_scheduler_resource_dispatch_smoke.py`
  - 结果：`1 passed`
- `python -m pytest -q tests/regression_status_category_mixed_case.py`
  - 结果：`1 passed`
- `python -m pytest -q tests/regression_resource_reference_guard_schedule.py`
  - 结果：`4 passed`
- `python -m pytest -q tests/regression_gantt_critical_chain_cache_thread_safe.py`
  - 结果：`1 passed`
- `python -m pytest -q tests/regression_schedule_orchestrator_contract.py`
  - 结果：`1 passed`
- `python -m pytest -q tests/regression_schedule_persistence_reject_empty_actionable_schedule.py`
  - 结果：`1 passed`
- `python -m pytest --collect-only -q tests`
  - 结果：`453 tests collected`

## 当前剩余阻断

- `python -m pytest -q tests/test_architecture_fitness.py`
- `python scripts/run_quality_gate.py`

当前两者都卡在同一个非本轮 pyright 接入引入的基线问题：

- `web/routes/system_ui_mode.py:13 ui_mode_set complexity=16 (rank F)`

结论：

- 主链 `pyright` gate 已接入并清零。
- 统一质量门禁当前未完全通过，但剩余阻断来自既有架构复杂度基线，而非本轮 `pyright` 接入修改。
