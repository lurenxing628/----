---
doc_type: refactor-apply-notes
refactor: 2026-04-30-techdebt-phase4-ledger-complexity
status: in-progress
tags: [techdebt, oversize, complexity, quality-gate]
---

# techdebt phase4 ledger complexity apply notes

## 步骤 1：记录阶段 4/5 开工基线

- 完成时间：2026-04-30
- 改动文件：
  - `audit/2026-05/phase4_phase5_baseline.txt`
  - `codestable/refactors/2026-04-30-techdebt-phase4-ledger-complexity/*`
- 验证结果：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：passed，active_xfail_count=0，fixed_count=5，collected_count=841。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，oversize_count=8，complexity_count=29，silent_fallback_count=153，test_debt_count=5，accepted_risk_count=5。
- 偏离：无。

## 步骤 2：拆分 scheduler summary 与配置字段校验

- 完成时间：2026-04-30
- 改动文件：
  - `core/services/scheduler/summary/schedule_summary.py`
  - `core/services/scheduler/summary/summary_size_guard.py`
  - `core/services/scheduler/summary/summary_runtime_state.py`
  - `core/services/scheduler/config/config_field_spec.py`
  - `core/services/scheduler/config/config_field_coercion.py`
  - `开发文档/技术债务治理台账.md`
- 改动内容：
  - `schedule_summary.py` 保留原导入路径和 `__all__`，把摘要大小保护、运行状态、告警和冻结状态拼装拆到新模块。
  - `config_field_spec.py` 保留字段注册表和旧入口，把字段值兼容读取、选择项校验、数字/布尔/时间清洗拆到 `config_field_coercion.py`。
  - 台账通过受控刷新移除两个已达标的超长文件登记，`oversize_count` 从 8 降到 6；同步更新的 fallback 行号来自本批修改的 `schedule_summary.py::serialize_end_date`，不是无关启动链漂移。
- 已完成验证：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check ...`：通过。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_sp05_path_topology_contract.py ... tests/regression_config_service_component_contract.py`：53 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`：0 errors，6 个既有 warning。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：passed，active_xfail_count=0，fixed_count=5，collected_count=841。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，oversize_count=6，complexity_count=29，silent_fallback_count=153。
- 偏离：无业务语义偏离；本批只拆文件和刷新已达标台账项。

## 步骤 3：拆分数据库迁移备份与事务基础设施

- 完成时间：2026-04-30
- 改动文件：
  - `core/infrastructure/database.py`
  - `core/infrastructure/database_bootstrap.py`
  - `core/infrastructure/migration_backup.py`
  - `core/infrastructure/migration_runner.py`
  - `core/infrastructure/migration_state.py`
  - `core/infrastructure/backup.py`
  - `core/infrastructure/transaction.py`
  - `core/infrastructure/migrations/v4.py`
  - `core/infrastructure/migrations/v4_sanitizers.py`
  - `tests/test_migration_v4_sanitizers.py`
  - `开发文档/技术债务治理台账.md`
- 改动内容：
  - `database.py` 降到 410 行，保留 `CURRENT_SCHEMA_VERSION`、`MigrationContractError`、`get_connection()`、`ensure_schema()` 和旧私有测试钩子；schema 读取、补缺整表、迁移状态、备份回滚等逻辑拆到小模块。
  - `backup.py` 把维护锁读取、维护窗口嵌套、锁文件读写等逻辑拆成小函数；为了阶段 4 不改静默回退台账，`maintenance_window()` 下既有历史 fallback 扫描点保留在原函数名下。
  - `v4.py` 保留 `_sanitize_field()` 薄包装，真实清洗逻辑拆到 `v4_sanitizers.py`，并新增直接刻画测试。
  - `transaction.py` 保留旧 `transaction()` 异常处理位置，避免阶段 4 把历史 fallback 移位；已拆出的 helper 暂不改变 public 行为。
  - 台账通过受控刷新：`oversize_count` 从 6 降到 5，`complexity_count` 从 29 降到 26，`silent_fallback_count` 保持 153。
- 已完成验证：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_transaction_savepoint_nested.py ... tests/test_migration_v4_sanitizers.py`：26 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/infrastructure tests/test_migration_v4_sanitizers.py`：通过。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`：0 errors，6 个既有 warning。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：passed，active_xfail_count=0，fixed_count=5，collected_count=847。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，oversize_count=5，complexity_count=26，silent_fallback_count=153。
- 偏离：`database.py::_migrate_with_backup`、`database.py::ensure_schema` 和 `transaction.py::transaction` 的复杂度仍在台账内；为避免阶段 4 提前移动历史 fallback，先保留这些旧入口体，后续阶段继续收口。

## 步骤 4：拆分业务服务和相关路由复杂逻辑

- 完成时间：2026-04-30
- 改动文件：
  - `core/services/report/calculations.py`
  - `core/services/report/calculation_helpers.py`
  - `core/services/report/downtime_impact.py`
  - `core/services/report/utilization.py`
  - `core/services/process/unit_excel/template_builder.py`
  - `core/services/process/unit_excel/template_validation.py`
  - `core/services/process/unit_excel/part_sheet_builder.py`
  - `core/services/process/unit_excel/resource_sheet_builder.py`
  - `core/services/process/unit_excel/route_sheet_builder.py`
  - `core/services/process/route_parser.py`
  - `core/services/process/route_parser_tokens.py`
  - `core/services/process/route_parser_segments.py`
  - `core/services/process/route_parser_constraints.py`
  - `core/services/process/route_parser_errors.py`
  - `core/services/process/part_service.py`
  - `core/services/process/part_delete_guard.py`
  - `core/services/process/part_route_validation.py`
  - `core/services/process/part_excel_adapter.py`
  - `web/routes/personnel_pages.py`
  - `web/routes/personnel_detail_context.py`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py`
  - `web/routes/domains/scheduler/scheduler_excel_calendar_rows.py`
  - `web/routes/system_backup.py`
  - `web/routes/system_backup_actions.py`
  - `开发文档/技术债务治理台账.md`
- 改动内容：
  - `report/calculations.py` 保留原 public 入口，把停机影响、利用率统计和共用时间计算拆到独立模块；报表字段名、日期边界和停机重叠口径不变。
  - `unit_excel/template_builder.py` 保留 `UnitTemplateBuilder.build()`，把模板校验、零件/资源/路线 sheet 构建拆开；外协默认周期、状态、备注的诊断文字保持不变。
  - `route_parser.py` 保留 `RouteParser.parse()`，把 token、工序段、约束解析和错误构造拆开；严格模式仍拒绝供应商缺失自动兜底。
  - `part_service.py` 保留服务入口，把删除保护、路线校验、Excel 适配拆到小模块；事务边界和保留旧内部工时规则不变。
  - 人员详情上下文拆到 route 辅助模块，避免 `web/viewmodels` 直接导入服务层；同时保留旧测试依赖的 `skill_level_options` 模块导出。
  - 排产 Excel 日历把 preview/confirm 共用的行清洗、数字校验和空设备效率校验拆到 `scheduler_excel_calendar_rows.py`；错误文案保持不变。
  - 系统备份把 action 执行拆到 `system_backup_actions.py`，同时保留历史 cleanup fallback 扫描点，避免阶段 4 误改启动链台账，并把 `backup_restore()` 降到复杂度阈值内。
  - 台账通过受控刷新：`oversize_count` 从 5 降到 2，`complexity_count` 从 26 降到 20，`silent_fallback_count` 保持 153，`accepted_risk_count` 保持 5。
- 已完成验证：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/report core/services/process core/services/process/unit_excel web/routes/personnel_pages.py web/routes/personnel_detail_context.py web/routes/domains/scheduler/scheduler_excel_calendar.py web/routes/domains/scheduler/scheduler_excel_calendar_rows.py web/routes/system_backup.py web/routes/system_backup_actions.py tests`：通过。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider ...`：4C 定向和架构回归共 38 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`：0 errors，6 个既有 warning。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：passed，active_xfail_count=0，fixed_count=5，collected_count=847。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，oversize_count=2，complexity_count=20，silent_fallback_count=153。
- 偏离：原计划中人员详情建议放到 `web/viewmodels`，但仓库架构测试禁止 viewmodel 直接导服务和 route helper；实际改为 `web/routes/personnel_detail_context.py`，避免分层越界。
