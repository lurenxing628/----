# 附录 C：路径迁移完整映射

> 本附录承接原总 plan 中与目录重组、根层保留清单、延后迁移批次与测试路径切换相关的长清单。执行时以 `SP05`、`SP07`、`SP08`、`SP09`、`SP10` 正文为准；本附录只做完整映射和交叉参考。

## 一、总体原则

1. `SP05` 完成前，后续子 plan 不得按迁移后路径实施。
2. `SP05` 完成后，已迁组（`core/services/scheduler/config/`、`run/`、`summary/` 与 `web/routes/domains/scheduler/`）统一只认迁移后真实实现路径；延后组（`batch/dispatch/gantt/calendar`）在 `SP08/SP09` 触达前仍以根层稳定入口为准。
3. 根层保留文件只能承担薄门面、兼容导出或共享工具，不得继续承载真实实现。
4. 延后迁移组必须在本附录中写死归属批次，不得留无主残项。
5. `SP05` 只为延后组创建空包骨架；`core/services/scheduler/{batch,dispatch,gantt,calendar}/__init__.py` 不得包含 `Import` / `ImportFrom`，不得导入真实实现、不得导出根层旧模块、不得提前接管业务路径。
6. 根层兼容薄门面按 `SP05` 正文三档矩阵处理：强兼容档必须通过 `sys.modules` alias 或等效实现保证 `old is new`；推荐旧路径直接别名到新模块对象（如 `sys.modules[__name__] = importlib.import_module("新真实模块")`），禁止用 `from 新路径 import *` 冒充同一模块对象。行为兼容档不得强制 `old is new`，无兼容档不得创建根层薄门面。
7. 上述兼容薄门面不得被新真实实现反向依赖，也不得继续承接新改动；模块级替换 / 注入合同必须作为 `SP05` 的显式验证项，并至少补一组服务侧、一组 route 侧“旧路径 monkeypatch 后命中新真实链”的代表性回归；`old is new` 是强兼容必要前置，不得作为唯一行为证明。
8. `web/routes/domains/{process,personnel,equipment,system}/` 在 `SP05` 只创建空包骨架；对应 `__init__.py` 不得包含 `Import` / `ImportFrom`，根层 `process.py`、`personnel.py`、`equipment.py`、`system.py` 不得提前指向空包。

## 二、调度服务目标目录

### 目标子包
- `core/services/scheduler/config/`
- `core/services/scheduler/run/`
- `core/services/scheduler/batch/`
- `core/services/scheduler/dispatch/`
- `core/services/scheduler/gantt/`
- `core/services/scheduler/summary/`
- `core/services/scheduler/calendar/`

### 批次 1 热点先迁（`SP05`）
#### `config/`
- `config_presets.py`
- `config_service.py`
- `config_snapshot.py`
- `config_validator.py`

#### `run/`
- `schedule_input_collector.py`
- `schedule_input_contracts.py`
- `schedule_input_runtime_support.py`
- `schedule_input_builder.py`
- `schedule_orchestrator.py`
- `schedule_optimizer.py`
- `schedule_optimizer_steps.py`
- `schedule_persistence.py`
- `schedule_template_lookup.py`
- `freeze_window.py`
- `run_command.py`（默认不创建；只有确认现有 `ScheduleRunInput` / `ScheduleOrchestrationOutcome` / `SummaryBuildContext` 无法吸收明确重复消费证据时，才允许新增）
- `run_context.py`（默认不创建；只有确认现有 `ScheduleRunInput` / `ScheduleOrchestrationOutcome` / `SummaryBuildContext` 无法吸收明确重复消费证据时，才允许新增）
- `run_status_rules.py`（`SP07` 必须先完成状态 / reason 语义重基线；只有确认现有模块无法吸收重复语义时，才允许在 `run/` 下落位，且只承载统一状态 / reason 语义）

#### `summary/`
- `schedule_summary.py`
- `schedule_summary_assembly.py`
- `schedule_summary_degradation.py`
- `schedule_summary_freeze.py`
- `schedule_summary_types.py`

### 延后迁移组
#### `SP08` 负责
##### `gantt/`
- `gantt_contract.py`
- `gantt_critical_chain.py`
- `gantt_range.py`
- `gantt_service.py`
- `gantt_tasks.py`
- `gantt_week_plan.py`

#### `SP09` 负责
##### `batch/`
- `batch_copy.py`
- `batch_excel_import.py`
- `batch_query_service.py`
- `batch_service.py`
- `batch_template_ops.py`
- `batch_write_rules.py`

##### `dispatch/`
- `resource_dispatch_excel.py`
- `resource_dispatch_range.py`
- `resource_dispatch_rows.py`
- `resource_dispatch_service.py`
- `resource_dispatch_support.py`
- `resource_pool_builder.py`

##### `calendar/`
- `calendar_admin.py`
- `calendar_engine.py`
- `calendar_service.py`

### 调度服务根层长期保留清单
- `schedule_service.py`
- `repository_bundle.py`
- `number_utils.py`
- `operation_edit_service.py`
- `schedule_history_query_service.py`
- `_sched_display_utils.py`
- `_sched_utils.py`
- `__init__.py`

### `SP05` 兼容薄门面（真实实现迁入新子包后暂留根层）
- `config_service.py`
- `config_snapshot.py`
- `config_validator.py`
- `schedule_input_collector.py`
- `schedule_input_builder.py`
- `schedule_orchestrator.py`
- `schedule_optimizer.py`
- `schedule_optimizer_steps.py`
- `schedule_persistence.py`
- `freeze_window.py`
- `schedule_summary.py`
- `schedule_summary_types.py`

说明：`config_presets.py`、`schedule_summary_assembly.py`、`schedule_summary_degradation.py`、`schedule_summary_freeze.py`、`schedule_template_lookup.py`、`schedule_input_contracts.py`、`schedule_input_runtime_support.py` 作为新子包内部支撑模块，默认不创建根层兼容薄门面；只有执行前全仓搜索确认存在旧模块精确路径导入方时，才允许在本附录补登记兼容入口。当前主链稳定对象以 `ScheduleRunInput`、`ScheduleOrchestrationOutcome`、`SummaryBuildContext` 为准；`run/schedule_orchestrator.py::_normalize_optimizer_outcome`、`run/schedule_orchestrator.py::_merge_summary_warnings` 仍属内部兼容面，`summary/schedule_summary.py::build_result_summary(ctx|**kwargs)` 仍属兼容公开面。根层 wrapper 若仍存在，一律视为 compat-only，不得新增新引用。相关 input contract / runtime support / template lookup 的 owner 不得再回写到根层 facade 或 `schedule_input_collector.py`、`schedule_input_builder.py` 这类消费者。

### 服务层导入改写规则
1. `config/run/summary` 子包内部继续使用同子包相对导入。
2. 子包之间跨组引用统一使用 `from ..目标子包.模块 import ...` 的两级相对导入，禁止绕回根层兼容薄门面。
3. 子包引用根层共享工具统一用 `from ..number_utils import ...`、`from ..repository_bundle import ...` 等单层向上导入。
4. 根层 `schedule_service.py` 统一改为 `.config/.run/.summary` 导入新真实实现。
5. `core/services/scheduler/__init__.py` 对已迁出的 `config/run/summary` 真实实现必须直接导出新路径；对延后迁移组仍暂沿用根层唯一稳定入口，不得经由兼容薄门面绕回。
6. 上述兼容薄门面只供旧模块精确路径导入方与脚本 / 回归过渡，并按强兼容 / 行为兼容 / 无兼容三档处理；强兼容档必须保证 `old is new`，行为兼容档不得为了整齐额外制造 `old is new` 约束。
7. `config_service.py`、`config_snapshot.py`、`config_validator.py`、`schedule_input_builder.py`、`freeze_window.py` 旧精确路径兼容必须至少覆盖旧路径 import、关键符号存在与代表性调用 smoke；`schedule_summary.py` 保持行为兼容档，覆盖旧路径 import / call；`schedule_summary_types.py` 单列旧路径 import smoke；二者均不要求 `old is new`。
8. `tests/regression_schedule_service_facade_delegation.py`、`tests/regression_dict_cfg_contract.py`、`tests/regression_optimizer_zero_weight_cfg_preserved.py` 这类模块级替换 / 注入合同在回收前必须保持有效；`schedule_optimizer_steps.py` 必须与 `schedule_optimizer.py` 一并纳入强兼容验证。
9. 若施工中短暂采用“新路径回指旧路径”，必须在 `SP05` 完成前按对应档位回收；强兼容档回收为“旧路径别名到新模块对象并满足 `old is new`”，行为兼容档不得遗留反向依赖。

### `SP05` 服务兼容薄门面回收矩阵（首批高风险项）

> 规则：任何兼容薄门面在删除前，必须先补齐“旧模块精确路径导入方清单 + 回收归属批次 + 验证命令”。下表先登记已确认的高频入口；未列出的其他薄门面，回收前也必须按同一格式补齐。

| 薄门面 | 档位 | 已知旧精确路径导入方 | 回收归属 | 验收方式 / 额外联动 |
| --- | --- | --- | --- | --- |
| `config_service.py` | 行为兼容 | `tests/run_synthetic_case.py`、`tests/run_real_db_replay_e2e.py`、`tests/run_complex_excel_cases_e2e.py`；`tests/regression_config_service_active_preset_custom_sync.py` 等配置 / Excel / 目标函数相关回归 | `SP10` 统一收口；`calendar_admin.py` 已按现状迁净，不再视为旧路径依赖 | 旧路径 import + `ConfigService` 存在 + 代表性调用 smoke；不得再把 `calendar_admin.py` 计入回收阻塞项 |
| `config_snapshot.py` | 行为兼容 | `tests/regression_config_snapshot_strict_numeric.py`、`tests/regression_objective_case_normalization.py`、`tests/regression_scheduler_strict_mode_dispatch_flags.py` 等 | `SP06` / `SP10` | 旧路径 import + 快照关键符号存在 + 代表性调用 smoke |
| `config_validator.py` | 行为兼容 | `tests/regression_config_validator_preset_degradation.py`、`tests/regression_objective_case_normalization.py`、`tests/regression_scheduler_strict_mode_dispatch_flags.py` 等 | `SP06` / `SP10` | 旧路径 import + 校验关键符号存在 + 代表性调用 smoke |
| `schedule_input_collector.py` | 行为兼容 | `tests/regression_schedule_input_collector_contract.py`、`tests/regression_schedule_input_collector_legacy_compat.py` | `SP07` / `SP10` | 删除前统一改到 `run/` 新路径；旧路径 import + `collect_schedule_run_input` 存在 + 代表性调用 smoke |
| `schedule_input_builder.py` | 行为兼容 | `tests/regression_schedule_input_builder_*.py` | `SP07` / `SP10` | 删除前统一改到 `run/` 新路径；旧路径 import + 关键 builder 符号存在 + 代表性调用 smoke |
| `schedule_orchestrator.py` | 行为兼容 | `tests/regression_schedule_orchestrator_contract.py` | `SP07` / `SP10` | 删除前统一改到 `run/` 新路径；旧路径 import + `orchestrate_schedule_run` 存在 |
| `schedule_persistence.py` | 行为兼容 | `tests/regression_schedule_persistence_*.py` | `SP07` / `SP10` | 删除前统一改到 `run/` 新路径；旧路径 import + `persist_schedule` 存在 + 持久化合同回归 |
| `freeze_window.py` | 行为兼容 | `tests/run_complex_excel_cases_e2e.py`、`tests/regression_freeze_window_fail_closed_contract.py` | `SP07` / `SP10` | 删除前统一改到 `run/` 新路径；旧路径 import + 关键 freeze 符号存在 + 代表性调用 smoke |
| `schedule_summary.py` | 行为兼容 | `tests/regression_schedule_summary_*.py`、`tests/regression_due_exclusive_*.py`、`audit/2026-03/20260316_schedule_audit_probes.py` | `SP07` / `SP10` | 删除前完成主链回归与审计探针切换；普通最小验证若不跑审计探针，必须用 summary 行为兼容代表测试替代覆盖 |
| `schedule_summary_types.py` | 行为兼容 | `tests/regression_schedule_summary_v11_contract.py`、`tests/regression_schedule_orchestrator_contract.py`、`tests/regression_dict_cfg_contract.py`、`tests/regression_due_exclusive_consistency.py` | `SP07` / `SP10` | 旧路径 import smoke；不得要求 `old is new` |
| `schedule_optimizer.py` | 强兼容 | `tests/regression_dict_cfg_contract.py`、`tests/regression_optimizer_zero_weight_cfg_preserved.py`、`tests/test_algorithm_date_boundary_split.py`、`tests/test_optimizer_local_search_neighbor_dedup.py` 等 | `SP07` / `SP10` | 删除前统一改到 `run/` 新路径；必须通过 `old is new` 验证并保持优化链模块级替换合同 |
| `schedule_optimizer_steps.py` | 强兼容 | `tests/regression_dict_cfg_contract.py`、`tests/regression_optimizer_zero_weight_cfg_preserved.py`、`tests/test_optimizer_build_order_once_per_strategy.py`、`tests/regression_warmstart_failure_surfaces_degradation.py` 等 | `SP07` / `SP10` | 删除前统一改到 `run/` 新路径；必须通过 `old is new` 验证并保持 `time` / helper 模块级替换合同 |

## 三、路由目标目录

### 域目录
- `web/routes/domains/scheduler/`
- `web/routes/domains/process/`
- `web/routes/domains/personnel/`
- `web/routes/domains/equipment/`
- `web/routes/domains/system/`

### `SP05` 先迁 scheduler 域
- `scheduler_bp.py`
- `scheduler_pages.py`
- `scheduler_config.py`
- `scheduler_run.py`
- `scheduler_batches.py`
- `scheduler_batch_detail.py`
- `scheduler_ops.py`
- `scheduler_analysis.py`
- `scheduler_resource_dispatch.py`
- `scheduler_calendar_pages.py`
- `scheduler_gantt.py`
- `scheduler_week_plan.py`
- `scheduler_excel_batches.py`
- `scheduler_excel_batches_baseline.py`
- `scheduler_excel_calendar.py`
- `scheduler_utils.py`

说明：`scheduler_gantt.py`、`scheduler_week_plan.py`、`scheduler_excel_batches.py`、`scheduler_excel_batches_baseline.py`、`scheduler_excel_calendar.py` 的 route / 同域 helper 物理位置在 `SP05` 统一收口到 `domains/scheduler/`，但其依赖的 `gantt/`、`batch/`、`calendar/` 服务分组仍分别由 `SP08` / `SP09` 负责后续业务收口。

### `SP09` 触达时同步迁移
#### process 域
- `process_bp.py`
- `process_excel_op_types.py`
- `process_excel_part_operation_hours.py`
- `process_excel_part_operations.py`
- `process_excel_routes.py`
- `process_excel_suppliers.py`
- `process_op_types.py`
- `process_parts.py`
- `process_suppliers.py`

#### personnel 域
- `personnel_bp.py`
- `personnel_calendar_pages.py`
- `personnel_excel_links.py`
- `personnel_excel_operator_calendar.py`
- `personnel_excel_operators.py`
- `personnel_pages.py`
- `personnel_teams.py`

#### equipment 域
- `equipment_bp.py`
- `equipment_downtimes.py`
- `equipment_excel_links.py`
- `equipment_excel_machines.py`
- `equipment_pages.py`

#### system 域
- `system_bp.py`
- `system_backup.py`
- `system_health.py`
- `system_history.py`
- `system_logs.py`
- `system_plugins.py`
- `system_ui_mode.py`
- `system_utils.py`

### 路由根层长期保留清单
- `dashboard.py`
- `excel_demo.py`
- `excel_utils.py`
- `material.py`
- `navigation_utils.py`
- `normalizers.py`
- `pagination.py`
- `reports.py`
- `enum_display.py`
- `scheduler.py`
- `process.py`
- `personnel.py`
- `equipment.py`
- `system.py`
- `team_view_helpers.py`
- `__init__.py`

说明：`navigation_utils.py`、`normalizers.py` 属于 `SP05` 明确保留的根层共享 helper，不是执行者可自由搬动的候选；后续子 plan 只能消费它们，不能把真实实现回退到域内文件或兼容薄门面。

### scheduler 域旧根层同名文件盘点（仅 inventory）
- `scheduler_bp.py`
- `scheduler_pages.py`
- `scheduler_config.py`
- `scheduler_run.py`
- `scheduler_batches.py`
- `scheduler_batch_detail.py`
- `scheduler_ops.py`
- `scheduler_analysis.py`
- `scheduler_resource_dispatch.py`
- `scheduler_calendar_pages.py`
- `scheduler_gantt.py`
- `scheduler_week_plan.py`
- `scheduler_excel_batches.py`
- `scheduler_excel_calendar.py`
- `scheduler_utils.py`

说明：上表只表示迁移前存在的旧根层同名文件，不等于 `SP05` 必须全部创建或保留兼容薄门面。是否保留 facade 必须按旧精确路径 import / monkeypatch / 注入合同证据进入三档矩阵；没有证据的文件默认不建根层 facade，避免过度兜底和第二事实源。该矩阵在补齐完整旧精确路径导入方清单与验证命令前，只能当作 compat 回收跟踪表，不得当作完成态 checklist。

### `SP05` 实际保留兼容薄门面（scheduler 域旧根层同名文件）
#### 强兼容档（必须 `old is new`）
- `scheduler_config.py`
- `scheduler_run.py`
- `scheduler_week_plan.py`
- `scheduler_excel_calendar.py`
- `scheduler_batches.py`
- `scheduler_analysis.py`
- `scheduler_batch_detail.py`
- `scheduler_ops.py`

#### 行为兼容档（不要求 `old is new`）
- `scheduler_excel_batches.py`
  - 旧路径必须能访问 `_build_parts_cache`、`_batch_baseline_extra_state`、`_build_template_ops_snapshot`。
  - 不得因普通 `from 新路径 import *` 丢失上述下划线 helper。

#### 无兼容档（默认不创建根层 facade）
- `scheduler_bp.py`
- `scheduler_pages.py`
- `scheduler_resource_dispatch.py`
- `scheduler_calendar_pages.py`
- `scheduler_gantt.py`
- `scheduler_utils.py`

说明：无兼容档文件只有在执行前发现新的旧精确路径 import / monkeypatch / 注入合同证据，并先回填本附录后，才允许调整档位。

### 根层门面切换规则
1. `scheduler.py` 在 `SP05` 中切到 `domains/scheduler/scheduler_pages.py` 这条二级聚合链，一级门面不得混导根层兼容薄门面。
2. `domains/scheduler/scheduler_pages.py` 负责导入 scheduler 域全部 route 实现（含 `gantt/week_plan/excel` 页面）；`SP05` 需显式补入对 `scheduler_excel_batches.py`、`scheduler_excel_calendar.py`、`scheduler_gantt.py`、`scheduler_week_plan.py` 的副作用导入。
3. `process.py`、`personnel.py`、`equipment.py`、`system.py` 在 `SP09` 对应域文件完成物理迁移前，禁止切到空子包。
4. `web/routes/domains/__init__.py` 仅作空包标记，不定义限制性 `__all__`。
5. scheduler 域旧根层同名文件如仍保留，只能给旧模块精确路径导入方与定向回归过渡使用，并按 `SP05` 三档兼容矩阵处理；强兼容档必须通过 `sys.modules` alias 或等效实现保证 `old is new`，行为兼容档只保证 import / 调用 / 可观测行为稳定，不得作为新门面继续扩散；无兼容档默认不创建根层 facade。
6. `tests/regression_scheduler_config_route_contract.py`、`tests/regression_scheduler_config_manual_url_normalization.py`、`tests/regression_manual_entry_scope.py`、`tests/regression_scheduler_run_surfaces_resource_pool_warning.py`、`tests/regression_scheduler_route_enforce_ready_tristate.py`、`tests/regression_scheduler_excel_calendar_uses_executor.py`、`tests/regression_scheduler_analysis_route_contract.py`、`tests/regression_scheduler_batch_detail_route_contract.py`、`tests/regression_scheduler_ops_update_route_contract.py`、`tests/regression_request_scope_app_logger_binding.py`、`tests/test_schedule_summary_observability.py` 的模块级替换 / 注入合同在 `SP05` 回收前必须保持有效；当前强兼容路由至少覆盖 `scheduler_config.py`、`scheduler_run.py`、`scheduler_week_plan.py`、`scheduler_excel_calendar.py`、`scheduler_batches.py`、`scheduler_analysis.py`、`scheduler_batch_detail.py`、`scheduler_ops.py`。`scheduler_excel_batches.py` 当前保持行为兼容，除非执行前新增 monkeypatch 证据；`scheduler_bp.py`、`scheduler_pages.py`、`scheduler_resource_dispatch.py`、`scheduler_calendar_pages.py`、`scheduler_gantt.py`、`scheduler_utils.py` 默认不创建根层 facade。

说明：`scheduler_excel_batches_baseline.py` 作为 `scheduler_excel_batches.py` 的同域伴随 helper，同批迁入 `web/routes/domains/scheduler/`；默认不保留根层兼容薄门面，现有合同继续通过 `web.routes.scheduler_excel_batches` 暴露的 `_build_parts_cache`、`_batch_baseline_extra_state` / `_build_template_ops_snapshot` 维持。

## 四、共享导入与兼容导出规则

1. 迁入 `web/routes/domains/**` 的文件统一改成从 `web.routes...` 绝对导入根层共享工具。
2. 同一 domain 内部文件继续使用相对导入（如 `from .scheduler_bp import bp`），避免跨层相对导入猜路径。
3. `_safe_next_url` 统一落到 `web/routes/navigation_utils.py` 作为唯一真实实现；`_warn_invalid_next_url_once` 随策略迁入该真实策略模块的私有 helper；scheduler 域与 `system_ui_mode.py` 统一改走新入口。若 `system_utils.py` 暂保留 `_safe_next_url`，只能调用 `_safe_next_url_core(raw, url_for)` 做旧路径薄包装，并通过行为回归与观测回归验证，不把函数对象同一性写成完成判定；`navigation_utils.py` 禁止反向导入 `system_utils.py`。
4. `_parse_result_summary_payload` 的共享归属继续稳定落在 `web/routes/normalizers.py`；`dashboard.py`、`system_history.py` 必须继续直接从该根层共享 helper 导入，不得回退依赖 `scheduler_bp.py`、`domains/scheduler/**` 或兼容薄门面。
5. `core/services/scheduler/__init__.py` 与各子包 `__init__.py` 负责建立稳定导出路径。
6. 对延后迁移组，在物理迁移完成前，根层兼容导出仍视为唯一稳定入口；对已迁出的 `config/run/summary` 与 scheduler 域 route，根层同名文件只作兼容薄门面并按强兼容 / 行为兼容 / 无兼容三档矩阵处理，不再是新改动入口。
7. `SP05` 的 scheduler 域共享工具导入改写至少覆盖：
   - `scheduler_bp.py` → `web.routes.enum_display`
   - `scheduler_batches.py` → `web.routes.excel_utils`、`web.routes.pagination`、`web.routes.navigation_utils`
   - `scheduler_analysis.py`、`scheduler_gantt.py`、`scheduler_week_plan.py`、`scheduler_utils.py` → `web.routes.normalizers`
   - `scheduler_excel_calendar.py`、`scheduler_excel_batches.py`、`scheduler_run.py`、`scheduler_week_plan.py`、`scheduler_utils.py`、`scheduler_batches.py` → `web.routes.excel_utils`
   - `scheduler_config.py`、`scheduler_batches.py` 中的 `_safe_next_url` → `web.routes.navigation_utils`
8. `tests/regression_excel_routes_no_tx_surface_hidden.py`、`tests/generate_conformance_report.py`、`tests/test_source_merge_mode_constants.py` 这类按文件路径读源码的测试 / 脚本，`SP05` 必须同步切到新真实实现路径；若阶段性保留旧路径检查，必须明确登记为兼容层检查。
9. `tests/generate_conformance_report.py::_check_architecture_layers(...)` 必须改为递归扫描 `web/routes/**`，不能继续停留在 `os.listdir(web/routes)` 顶层枚举；脚本内硬编码真实实现路径与 evidence 文案也必须同步迁移，至少包括 `core/services/scheduler/config/config_service.py` 与 `core/services/scheduler/run/schedule_persistence.py`；否则 scheduler 域 route 迁入 `domains/**` 后会从报告中消失，服务侧 evidence 也会继续误指旧根层薄门面。
10. `开发文档/技术债务治理台账.md` 中受 `SP05` 影响的 `oversize_allowlist`、`complexity_allowlist`、`silent_fallback` 必须与迁移后路径同步更新；否则不得把新路径视为稳定口径。

## 五、测试与支撑脚本路径映射

### `SP10` 目标目录
- `tests/architecture/`
- `tests/regression/`
- `tests/smoke/`
- `tests/e2e/`
- `tests/support/`

### 首批迁移文件
#### 架构与路径敏感
- `tests/test_architecture_fitness.py` → `tests/architecture/test_architecture_fitness.py`
- `tests/regression_safe_next_url_hardening.py` → `tests/regression/regression_safe_next_url_hardening.py`
- `tests/regression_safe_next_url_observability.py` → `tests/regression/regression_safe_next_url_observability.py`
- `tests/regression_quality_gate_scan_contract.py` → `tests/regression/regression_quality_gate_scan_contract.py`
- `tests/test_source_merge_mode_constants.py` → `tests/regression/test_source_merge_mode_constants.py`
  - `SP05` 只同步改其中 `schedule_optimizer.py`、`freeze_window.py` 两个目标到 `core/services/scheduler/run/` 新真实路径；`process_parts.py`、`process_excel_op_types.py` 留待 `SP09` 切换，不把 source_merge 目标与 no_tx 路由扫描混写。
- `tests/regression_excel_routes_no_tx_surface_hidden.py` → `tests/regression/regression_excel_routes_no_tx_surface_hidden.py`
  - `SP05` 只同步改其中 `scheduler_excel_batches.py` 到 `web/routes/domains/scheduler/` 新真实路径；`personnel_excel_operator_calendar.py` 留待 `SP09` 切换，不把 no_tx 路由扫描与 source_merge 常量检查混写。

#### 配置与主链
- `regression_config_snapshot_strict_numeric.py`
- `regression_config_service_active_preset_custom_sync.py`
- `regression_schedule_optimizer_cfg_float_strict_blank.py`
- `regression_scheduler_apply_preset_reject_invalid_numeric.py`
- `regression_schedule_input_collector_contract.py`
- `regression_schedule_orchestrator_contract.py`
- `regression_build_outcome_contract.py`
- `regression_schedule_service_facade_delegation.py`
- `regression_system_request_services_contract.py`
- `regression_dict_cfg_contract.py`
- `regression_optimizer_zero_weight_cfg_preserved.py`

#### 界面与试点页
- `regression_excel_import_strict_reference_apply.py`
- `regression_excel_preview_confirm_baseline_guard.py`
- `regression_scheduler_excel_calendar_uses_executor.py`
- `regression_scheduler_excel_calendar_strict_numeric.py`
- `regression_process_excel_part_operation_hours_import.py`
- `regression_process_excel_part_operation_hours_source_row_num.py`
- `regression_process_excel_part_operation_hours_append_fill_empty_only.py`
- `regression_frontend_common_interactions.py`
- `test_ui_mode.py`
- `regression_template_no_inline_event_jinja.py`

#### `SP09` 直接新增的专项回归（不属于迁移，但路径口径需固定）
- `tests/regression/page_boot_dom_contract.py`
- `tests/regression/template_inline_script_targets.py`
- `tests/regression/static_versioning_manifest_contract.py`
- `tests/regression/static_versioning_ui_v2_static.py`
- 说明：以上专项回归自创建起直接落位于 `tests/regression/`，用于承接 `SP09` 的 DOM 协议、模板脚本外置与静态资源版本化校验；`SP10` 只负责统一目录入口与命令切换，不再把它们回落到 `tests/` 根层。

### 支撑脚本迁移目标
- `tests/check_quickref_vs_routes.py` → `tests/support/check_quickref_vs_routes.py`
- `tests/generate_conformance_report.py` → `tests/support/generate_conformance_report.py`
- `tests/excel_preview_confirm_helpers.py` → `tests/support/excel_preview_confirm_helpers.py`
- 新建 `tests/support/repo_root.py`
- `SP05` 如迁移 `config_service.py`、`schedule_persistence.py` 等真实实现，`generate_conformance_report.py` 的默认扫描目标与 evidence 文案必须同步切到新真实实现，至少指向 `core/services/scheduler/config/config_service.py`、`core/services/scheduler/run/schedule_persistence.py`；若阶段性保留旧路径检查，需在治理台账登记“兼容层检查”用途。

## 六、路径敏感门禁联动清单

以下文件在 `SP05`、`SP08`、`SP09`、`SP10` 中都可能被修改，视为串行修改文件：
- `tests/test_architecture_fitness.py`（迁移后对应 `tests/architecture/test_architecture_fitness.py`；含 `LOCAL_PARSE_HELPER_ALLOWLIST`）
- `tools/quality_gate_shared.py`（含 `REQUEST_SERVICE_TARGET_FILES`、`REQUEST_SERVICE_TARGET_ALLOWED_HELPERS`）
- `tools/quality_gate_operations.py`
- `tools/quality_gate_scan.py`
- `tools/quality_gate_support.py`
- `tests/test_source_merge_mode_constants.py`
- `tests/regression_safe_next_url_hardening.py`
- `tests/regression_safe_next_url_observability.py`
- `tests/regression_template_urlfor_endpoints.py`
- `tests/regression_page_manual_registry.py`
- `tests/regression_scheduler_config_route_contract.py`
- `tests/regression_scheduler_config_manual_url_normalization.py`
- `tests/regression_scheduler_analysis_route_contract.py`
- `tests/regression_scheduler_batch_detail_route_contract.py`
- `tests/regression_scheduler_ops_update_route_contract.py`
- `tests/regression_scheduler_route_enforce_ready_tristate.py`
- `tests/regression_scheduler_run_surfaces_resource_pool_warning.py`
- `tests/regression_scheduler_excel_batches_helper_injection_contract.py`
- `tests/regression_scheduler_excel_calendar_uses_executor.py`
- `tests/regression_request_scope_app_logger_binding.py`
- `tests/test_schedule_summary_observability.py`
- `tests/regression_manual_entry_scope.py`
- `tests/regression_system_request_services_contract.py`
- `tests/regression_schedule_service_facade_delegation.py`
- `tests/regression_dict_cfg_contract.py`
- `tests/regression_optimizer_zero_weight_cfg_preserved.py`
- `tests/regression_quality_gate_scan_contract.py`
- `tests/regression_excel_routes_no_tx_surface_hidden.py`
- `tests/generate_conformance_report.py`
- `开发文档/技术债务治理台账.md`
- 本附录 `C_路径迁移完整映射.md`

说明：`tests/regression_excel_routes_no_tx_surface_hidden.py`、`tests/generate_conformance_report.py`、`tests/test_source_merge_mode_constants.py` 属于按文件路径读源码的检查；`SP05` 必须把默认扫描目标切到新真实实现，或明确登记为兼容层检查。其中 `test_source_merge_mode_constants.py` 只承接 `schedule_optimizer.py`、`freeze_window.py` 的 SP05 切换，`regression_excel_routes_no_tx_surface_hidden.py` 只承接 `scheduler_excel_batches.py` 的 SP05 切换，`generate_conformance_report.py` 同步承接 route 递归扫描与服务侧 evidence 路径切换。

## 七、使用方式

1. 需要知道“某文件最终要迁到哪里”时，先查本附录。
2. 真正执行时，仍以对应子 plan 的范围和步骤为准。
3. 若附录与子 plan 正文冲突，以子 plan 正文为准，并在完成后反向更新本附录，保持索引稳定。
