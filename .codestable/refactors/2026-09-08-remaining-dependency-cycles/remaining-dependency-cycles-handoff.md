---
doc_type: refactor-apply-notes
refactor: 2026-09-08-remaining-dependency-cycles
status: completed
scope: A4 backend helpers, A5 plugins, A6 report values and tests support
---

# 剩余依赖治理后端交接

## 结论

- 四个独立切片已实施。每片各有 scan/design/checklist/apply 记录；没有合成一次不透明的大搬迁。
- 产品和测试共 78 个本轮写入路径，其中多数现有路由只调整 import。模板、样式、前端接入和用户指定禁写产品文件未动；已有 dirty 代码保留。
- 全程没有 git add/commit/push；不修改全局 import/deadcode 基线、roadmap、测试 registry 或治理台账。
- 例外必须如实交接：起步 symbol_locator 自动刷新了默认 callgraph 目录，发生非预期快照写入。未拿 HEAD 覆盖共享 dirty 快照；之后一律使用 CHECKUP_CALLGRAPH=/tmp/...。主代理必须重新封存最终证据，不能直接信任这份默认快照。

## 实际切片

| 切片 | 实施 | 专项验证 |
| --- | --- | --- |
| A4 | 七个 helper 放入 web.routes.helpers；42 个直接后端调用方直连 canonical；旧路径同对象转出 | 起步 81 passed；最终纳入 1072 项集成回归 |
| A5 | manager 复用已有 core.shared.boolean_normalize；保留注册回滚；等价 Optional[str] 注解适配 Python 3.8 | 最终 40 passed |
| A6 | 数字解析原实现搬入 report.values.number_parsing；五个调用方直连；旧函数/__all__/ReportEngine identity 保留 | 47 passed；普通/write-only XLSX 单元格和真实 patch 通过 |
| tests | 共用资源脚本 helper 和场景 seed/app fixture 移入 tests._support；原测试函数/SQL/断言不改 | 178 passed |

- 最终源码集成命令：`.venv/bin/python -m pytest -q -p no:cacheprovider tests/web_pages tests/excel_data_io tests/schedule/route_view tests/app_runtime/test_safe_next_url_observability.py tests/schedule/summary/test_scheduler_bp_result_summary_guard.py tests/config/test_plugins_a5_dependency_boundary.py tests/scheduler_analysis/test_report_a6_dependency_boundary.py tests/gate_meta/test_test_support_dependency_boundary.py`；结果 **1072 passed in 93.84s**。
- 最终源码日志：`/tmp/remaining-cycles-integration-sealed-20260908.log`、`/tmp/remaining-cycles-a5-tests-sealed-20260908.log`；A6/tests 切片日志见各自 apply-notes。
- 78 文件 Python 3.8 扫描 **0 findings**，读取失败 0、解析拒绝 0；Ruff 通过；`git diff --check` 通过。两个继承注解改为等价 typing 写法，未改参数默认值/函数体。
- 对开工时 dirty 文件 tar 做了 **60 项源码/AST 对比，全部通过**。manager 已有回滚修复逐字保留；七个 helper 除私有 List[str] 注解外函数体原样，报表解析逐字一致，场景测试及迁移 helper 的全部函数 AST 保持一致。两处文件尾多余空行归一化已在 JSON 单独记出。

## 双 Scope

| scope | 起点模块 / hard 目录圈 | 本轮封存模块 / hard 目录圈 | 父包感知 hard 文件圈 | 显式 hard 文件圈 | unresolved |
| --- | --- | --- | --- | --- | --- |
| production | 786 / 3 | 802 / 1 | 9 | 0 | 6 |
| production-and-tests | 1522 / 4 | 1555 / 1 | 9 | 0 | 45 |

- 来源：`/tmp/remaining-cycles-before-{production,tests}-20260908.json` 与 `/tmp/remaining-cycles-sealed-{production,tests}-20260908.json`。parse errors 均为 0；相对开工现场，无新 hard SCC/圈内边、无 unresolved 新增或删除。模块总数包含其他代理并行新增，不能全部归功于本轮。
- A4 的 routes/scheduler helper 返回边、A5、A6 和 tests 圈均已移除。保留的 13 边圈为 `.` / `web/bootstrap` / `web/routes`，不是 scheduler/helper 返回圈。
- 这个剩余圈有具体目录折叠来源：`app_new_ui.py:5` 依赖 bootstrap，`web/bootstrap/factory.py:31` 起装配路由，`web/bootstrap/startup_config.py:12` 和 `web/routes/system_runtime_logs.py:18` 依赖根目录 config；但 `config.py:1` 只有标准库 import，并不回调 app/路由。因此不能把目录聚合圈当文件加载死循环，也不为数字零重写启动配置语义。它在开工扫描中已经存在，主代理可结合当前启动配置工作统一决策。
- 插件/报表父包圈源于保留的 eager 公共导出；正逆序独立 Python 3.8 导入及 identity 测试通过。没有为消除父包数字改成 lazy import 或删公开 API。

## 调用图

- 起点临时图：`/tmp/remaining-cycles-locator-20260908`。最终独立双跑：`/tmp/remaining-cycles-sealed-callgraph-1-20260908`、`/tmp/remaining-cycles-sealed-callgraph-2-20260908`。
- 10 个 JSON 文件集合及逐文件 SHA256 完全相同；哈希见同目录 evidence JSON。
- 56 个搬移 callable 无丢失；相关 278 条旧确信边在路径映射后全部保留。只对本轮搬移表面作此证明，不将其他代理造成的全仓 callable 差异算成本轮。
- 第一候选曾因根路由仍借兼容入口隐藏 161 条旧确信边，已将 28 个根路由 import 直连 canonical 修正并重测。这正是 A3 要求核对的“运行能用但图被遮住”问题。

## 主代理受控更新

- 新测试登记候选：四个 `test_*_dependency_boundary.py`，精确文件名见末尾 boundary_tests 表；本轮未改 registry。
- 治理台账只需精确迁移同函数体身份：`fallback:web-routes-excel_utils-read_uploaded_xlsx-fef185cd8db6` -> `fallback:web-routes-helpers-excel_utils-read_uploaded_xlsx-fef185cd8db6`。不能新增豁免或删掉原清理异常语义来过门禁。
- deadcode/调用图身份映射共八个模块路径，见 evidence JSON 的 callable_path_map；不要全量 refresh 掩盖其他变化。
- 两个正式 `--fail-on-new-cycle --quiet-when-clean` 命令均退出 1：已有 process/unit_excel 父包文件圈、`web.bootstrap.startup_config -> config` 边；含 tests 另有既有 `test_frozen_bundle_contract.py:198` 的 `_ANCHOR_MODULE` unresolved。这些均能在开工扫描找到，不是本轮新增。日志 `/tmp/remaining-cycles-formal-direct-{production,tests}-20260908.log`。
- 架构专项当次结果 19 passed / 2 failed：本轮上述精确台账身份迁移，以及其他写集 scheduler/run 三个复杂度超限。Pyright gate 当次 3 errors / 15 warnings：错误在 algorithm_runtime/downtime.py:62、64 与 scheduler/run/optimizer_graph_ready_repair.py:159，未越界修改。详细日志 `/tmp/remaining-cycles-architecture-20260908.log`、`/tmp/remaining-cycles-pyright-20260908.log`。
- 完整 `scripts/run_quality_gate.py` 留给主代理在代码/基线/台账统一冻结后执行；本轮共享 dirty 工作区的局部测试与上述分项检查 **不是 clean-worktree proof**。

## 本轮路径与行号

以下是本轮精确写集，不是整仓 git status 中所有已有改动。行号指向实际变更或新实现入口。

### a4

- `web/routes/form_values.py:1`
- `web/routes/helpers/form_values.py:9`
- `web/routes/history_summary_logging.py:1`
- `web/routes/helpers/history_summary_logging.py:10`
- `web/routes/navigation_utils.py:1`
- `web/routes/helpers/navigation_utils.py:11`
- `web/routes/pagination.py:1`
- `web/routes/helpers/pagination.py:10`
- `web/routes/enum_display.py:1`
- `web/routes/helpers/enum_display.py:20`
- `web/routes/excel_utils.py:1`
- `web/routes/helpers/excel_utils.py:30`
- `web/routes/normalizers.py:1`
- `web/routes/helpers/normalizers.py:15`
- `web/routes/helpers/__init__.py:1`
- `web/routes/equipment_excel_machines.py:24`
- `web/routes/material.py:11`
- `web/routes/process_op_types.py:9`
- `web/routes/system_logs.py:8`
- `web/routes/process_excel_part_operation_hours.py:23`
- `web/routes/reports_page_support.py:11`
- `web/routes/system_plugins.py:8`
- `web/routes/process_excel_routes.py:16`
- `web/routes/personnel_excel_operator_calendar.py:22`
- `web/routes/process_bp.py:11`
- `web/routes/process_suppliers.py:9`
- `web/routes/personnel_excel_links.py:19`
- `web/routes/personnel_excel_operators.py:21`
- `web/routes/personnel_bp.py:9`
- `web/routes/equipment_bp.py:9`
- `web/routes/personnel_teams.py:8`
- `web/routes/system_backup.py:14`
- `web/routes/dashboard.py:14`
- `web/routes/personnel_calendar_pages.py:10`
- `web/routes/process_excel_op_types.py:21`
- `web/routes/process_excel_route_apply.py:15`
- `web/routes/process_excel_suppliers.py:22`
- `web/routes/equipment_excel_links.py:20`
- `web/routes/personnel_pages.py:15`
- `web/routes/equipment_pages.py:19`
- `web/routes/system_history.py:5`
- `web/routes/process_parts.py:11`
- `web/routes/excel_demo.py:21`
- `web/routes/domains/scheduler/scheduler_excel_calendar.py:16`
- `web/routes/domains/scheduler/scheduler_week_plan.py:19`
- `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:23`
- `web/routes/domains/scheduler/scheduler_batches.py:11`
- `web/routes/domains/scheduler/scheduler_config.py:18`
- `web/routes/domains/scheduler/scheduler_utils.py:9`
- `web/routes/domains/scheduler/scheduler_run.py:8`
- `web/routes/domains/scheduler/scheduler_analysis_read.py:7`
- `web/routes/domains/scheduler/scheduler_gantt.py:12`
- `web/routes/domains/scheduler/scheduler_bp.py:9`
- `web/routes/domains/scheduler/scheduler_resource_dispatch.py:13`
- `web/routes/domains/scheduler/scheduler_excel_batches.py:16`
- `web/routes/domains/scheduler/scheduler_batch_detail.py:19`
- `web/routes/domains/scheduler/scheduler_ops.py:9`

### a5

- `core/plugins/manager.py:11`

### a6

- `core/services/report/values/__init__.py:1`
- `core/services/report/values/number_parsing.py:9`
- `core/services/report/report_number_parsing.py:1`
- `core/services/report/exporters/xlsx.py:14`
- `core/services/report/delay_diagnosis_presentation.py:7`
- `web/routes/reports_export_support.py:10`
- `core/services/report/report_engine.py:32`
- `core/services/report/execution_review.py:16`

### tests

- `tests/_support/resource_dispatch_frontend_support.py:29`
- `tests/resource_dispatch/resource_dispatch_frontend_support.py:1`
- `tests/_support/gantt_scenario.py:18`
- `tests/gantt/test_gantt_draft_save_and_preview.py:5`
- `tests/operation_execution/operation_execution_feedback_test_support.py:14`
- `tests/web_pages/test_scenario_preview_secondary_outputs.py:27`
- `tests/web_pages/test_frontend_ui_language_polish.py:16`

### boundary_tests

- `tests/_support/dependency_boundaries.py:13`
- `tests/web_pages/test_routes_a4_dependency_boundary.py:35`
- `tests/config/test_plugins_a5_dependency_boundary.py:17`
- `tests/scheduler_analysis/test_report_a6_dependency_boundary.py:20`
- `tests/gate_meta/test_test_support_dependency_boundary.py:17`
