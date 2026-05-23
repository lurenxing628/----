---
doc_type: issue-analysis
issue: 2026-05-23-review-report-dedupe-fix-plan
status: confirmed
title: "Review 报告剩余问题根因下钻与修复计划"
date: 2026-05-23
source_audit: "../../audits/2026-05-23-review-report-dedupe/index.md"
scope:
  - "F-01..F-07 P1 剩余问题"
  - "F-08..F-11 P2 后续收口项"
subagents_created_for_root_cause: 9
subagents_created_for_adversarial_review: 4
adversarial_review_status: completed
recommended_plan: "按批次小步修复，先 P1，再 P2"
implementation_status: "implemented_pending_clean_proof"
actual_scope_note: "本轮实际实现已包含 P1、P2-1、P2-2、P2-3、P2-4 的一部分文档同步；最终 clean proof 仍需提交后跑"
tags: [review, scheduler, gantt, resource-dispatch, quality-gate, database, codestable]
---

# Review 报告剩余问题根因下钻与修复计划

## 当前结论

本文件接在 `.codestable/audits/2026-05-23-review-report-dedupe/index.md` 后面，用来把已经去重后的问题继续下钻到引用链和根因，并整理成可以后续执行的修复计划。

本轮不是直接改业务代码，而是先把修复边界定清楚。原因很简单：这批问题跨页面、后端、前端脚本、数据库迁移、质量门禁和文档。如果直接一锅改，后面很难判断是哪个修复带来了新问题。

本轮第一批真实创建了 9 个只读子代理做下钻：

- F-01：分析页诊断状态和坏数字。
- F-02：报表页单边日期。
- F-03：Gantt 前端错误边界。
- F-04：质量门禁漏纳入超期摘要回归。
- F-05：周计划模拟方案提示重复。
- F-06：资源排班展示、导出文件名、Excel 输出。
- F-07：数据库高版本库没有 fail-fast。
- P2：关键链异常折叠、Week/Month 假期宽度、`gantt_render.js` 拆分、文档同步。
- 跨问题分批：确认哪些问题可以合批，哪些必须拆开修。

计划初稿完成后，又真实创建了 4 个全新的只读子代理做对抗性审核，分别检查后端根因、Gantt 前端、质量门禁、资源排班和文档边界。对抗性审核指出的问题已经回填到本文：

- F-07 要在 `migrate_with_backup()` 创建备份前就失败，不能等备份已经生成后才报错。
- F-01 的测试不能只证明“不炸页”，还要证明坏数字没有被静默显示成 `0` 或正常状态。
- F-02 不能只测单边日期，还要测两边都有但格式坏的日期。
- F-03 的前端测试必须走真实 boot -> render -> adapter 链，不能用假函数绕过真实断点。
- F-06 的 Excel 是用户下载看的公开输出，中文标签应纳入 P1 子批，不再作为“待确认才做”的可选项。
- 新增的 P1 回归必须写清楚进哪个注册表、跑哪个命令，不能只散落在普通测试里。

总判断：

- P1 问题都成立，但不适合一次性混改。
- P2 里面，关键链异常折叠和 Week/Month 假期宽度测试可以排在第一批 P2；`gantt_render.js` 拆分和完整文档同步应放到 P1 修完以后。
- 最推荐的执行方式是：先补质量门禁，再补数据库 fail-fast，再修页面和前端可见错误，再收口资源排班公开输出，最后做 P2 维护收口。

2026-05-23 实际执行更新：

- 本轮后续实现已经按用户要求继续推进，不再停留在计划阶段。
- P1 批次已进入实现；P2-1、P2-2、P2-3 也已实际纳入当前工作区。
- `gantt_render.js` 拆分没有另开新重构文档，而是在本轮同步补了脚本顺序、前端回归和架构文档。
- 本文作为根因与计划依据保留，最终是否可合并以 `review-report-dedupe-fix-plan-fix-note.md` 和实际门禁证明为准。

## 修复策略选择

### 方案 A：按批次小步修复（推荐）

做法：

- 每批只解决一组根因相近、文件范围相对集中的问题。
- 每批都补对应回归测试。
- 每批结束后跑该批相关测试，最后再跑完整质量门禁。

优点：

- 每个问题修完后都能单独证明。
- 出现失败时容易定位。
- 不会把用户可见修复和大文件拆分混在一起。

缺点：

- 批次数量多一点。

结论：推荐采用。

### 方案 B：P1 一次性全修

做法：

- 一次提交内同时改所有 P1。

优点：

- 表面上快。

缺点：

- 涉及后端、前端、数据库、测试门禁，互相影响很大。
- 一旦测试红了，不容易判断是哪条链路坏了。
- Gantt 前端和资源排班导出都属于用户可见输出，混改风险高。

结论：不推荐。

### 方案 C：只修页面能看到的问题，门禁和数据库以后再说

做法：

- 先修 F-02、F-03、F-05、F-06，暂缓 F-04、F-07。

优点：

- 用户界面变化更快。

缺点：

- F-04 会继续让历史回归漏过质量门禁。
- F-07 会继续让未来高版本数据库被静默接受。
- 这两个问题虽然不一定每天都触发，但一旦触发，影响会比较深。

结论：不推荐作为主线。

## 推荐批次

### Batch 0：先补质量门禁缺口（F-04）

目标：

- 让已经存在的资源排班超期摘要解析回归进入必跑门禁，避免以后解析器退化却没人发现。

根因：

- 测试已经存在，但没有同时进入质量门禁注册表、必需回归分组和质量门禁自测。

引用链：

- `tools/test_registry.py` 里的 `QUALITY_GATE_GUARD_TESTS` 决定质量门禁守护测试。
- `tools/test_registry.py` 里的 `REQUIRED_REGRESSION_GROUPS["scheduler_batches_material_resource"]` 决定完整测试债检查时哪些测试必须存在。
- `scripts/run_quality_gate.py` 和 `tools/quality_gate_shared.py` 从共享注册表取测试清单。
- `tests/test_run_quality_gate.py` 用高价值断言防止清单再次被删。

最小修复：

- 把下面 3 个测试加入 `QUALITY_GATE_GUARD_TESTS`：
  - `tests/regression_resource_dispatch_overdue_summary_formats.py`
  - `tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py`
  - `tests/regression_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py`
- 把同样 3 个测试加入 `REQUIRED_REGRESSION_GROUPS["scheduler_batches_material_resource"]["target_paths"]`。
- 在 `tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions` 加对应断言。

验证：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_resource_dispatch_overdue_summary_formats.py tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py tests/regression_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py -k "required_suite_comes_from_shared_registry_and_covers_high_risk_regressions"`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_manifest.py::test_required_groups_cover_required_registry tests/test_long_gate_manifest.py::test_required_and_startup_regression_args_come_from_dynamic_plan tests/test_full_test_debt_registry_contract.py::test_quality_gate_required_startup_and_full_debt_share_registry`

不要做：

- 不要用自动 glob 把一堆测试都塞进门禁。
- 不要只改一个注册点；三个注册点要一起补。

### Batch 1：数据库高版本库 fail-fast（F-07）

目标：

- 当数据库版本比当前代码认识的版本还高时，启动、预检、迁移都要直接报错，不能假装没事。

根因：

- 当前 `ensure_schema()` 只处理“数据库版本小于当前代码版本”的情况。
- 如果数据库版本大于当前代码版本，它会跳过迁移并继续运行。
- 迁移预检和正式迁移也有类似的 `current >= to_version` 直接返回逻辑。

引用链：

- `app.py` 启动应用。
- `web/bootstrap/entrypoint.py` 创建应用。
- `web/bootstrap/factory.py` 调 `ensure_schema()`。
- `core/infrastructure/database.py` 读取 `SchemaVersion`。
- `core/infrastructure/migration_runner.py` 做迁移预检和正式迁移。

最小修复：

- 在迁移状态相关位置加一个共享检查：数据库版本大于 `CURRENT_SCHEMA_VERSION` 时抛 `MigrationContractError`。
- 调用点至少包含：
  - `core/infrastructure/database.py` 的 `ensure_schema()`。
  - `core/infrastructure/migration_runner.py` 的 `_run_preflight_on_probe()`。
  - `core/infrastructure/migration_runner.py` 的 `migrate_with_backup()`，而且必须在创建 `before_migrate` 备份之前判断 `from_version > to_version` 并抛错。
  - `core/infrastructure/migration_runner.py` 的 `_apply_migrations()`。
- `_apply_migrations()` 仍要保留数据库实读后的二次保护，避免绕过 `migrate_with_backup()` 的调用路径漏网。

验证：

- 新增或扩展 `tests/regression_database_high_version_failfast.py`：
  - 先建到当前版本，再手动把 `SchemaVersion` 改成更高版本，断言 `ensure_schema()` 抛 `MigrationContractError`。
  - 高版本库调用 `preflight_migration_contract()` 抛 `MigrationContractError`。
  - 高版本库调用 `migrate_with_backup()` 抛 `MigrationContractError`。
  - `migrate_with_backup()` 的测试还要断言没有生成 `before_migrate` 备份，并且 `BackupManager.backup()` 没有被调用。
- 把 `tests/regression_database_high_version_failfast.py` 加入 `QUALITY_GATE_GUARD_TESTS`。
- 把 `tests/regression_database_high_version_failfast.py` 加入 `REQUIRED_REGRESSION_GROUPS["request_services_runtime_error_boundary"]["target_paths"]`。
- 在 `tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions` 加高价值断言。
- 跑现有迁移回归：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_database_high_version_failfast.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_ensure_schema_fastforward_empty_only.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_migration_failfast_no_backup_storm.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_database_migration_runner_delegation.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py -k "required_suite_comes_from_shared_registry_and_covers_high_risk_regressions"`

不要做：

- 不要自动降级数据库版本。
- 不要吞掉异常继续启动。
- 不要破坏空库从 0 升到当前版本的正常路径。

### Batch 2：分析页诊断状态和坏数字（F-01）

目标：

- 分析页不能把未知状态显示成“正常”。
- `NaN`、`Infinity`、`-Infinity` 不能把诊断构建炸掉，也不能被当成正常数字。

根因：

- `graph_status` 缺失时会变成 `unknown`，但总健康状态函数没有处理 `unknown` 或陌生状态，最后落到 `ok`。
- `safe_float()`、`safe_int()`、`format_hours()` 没有统一拒绝非有限数字。
- 历史摘要解析使用默认 `json.loads()`，会接受非标准 JSON 里的 `NaN`、`Infinity`。

引用链：

- `web/routes/domains/scheduler/scheduler_analysis.py` 进入分析页。
- `web/routes/domains/scheduler/scheduler_analysis_read.py` 构造读取上下文。
- `core/models/scheduler_history_parser.py` 解析历史摘要。
- `web/viewmodels/scheduler_analysis_vm.py` 把摘要交给诊断模块。
- `web/viewmodels/scheduler_analysis_diagnostic_health.py` 计算总状态。
- `web/viewmodels/scheduler_analysis_diagnostic_helpers.py` 格式化数值和文案。
- `templates/scheduler/analysis_parts/_diagnostic_sections.html` 展示诊断。

最小修复：

- `scheduler_analysis_diagnostic_health.py`：只有 `graph_status == "available"` 且无循环、无错误、无提醒时才返回 `ok`。
- `scheduler_analysis_diagnostic_health.py`：缺失、`unknown`、陌生状态都返回“未知”或“需要关注”，不能返回 `ok`。
- `scheduler_analysis_diagnostic_helpers.py`：`safe_float()`、`safe_int()`、`format_hours()` 统一用 `math.isfinite()` 拒绝非有限值，并接住 `OverflowError`。
- `core/models/scheduler_history_parser.py`：用 `parse_constant` 拒绝 `NaN`、`Infinity`、`-Infinity`，并把 `parse_constant` 抛出的异常收口成 `ResultSummaryParseResult(parse_failed=True, reason="json_decode_error" 或更明确 reason)`，不能让异常冒泡炸页面。

验证：

- 更新 `tests/regression_scheduler_analysis_diagnostic_contract.py`：
  - 缺少 `graph_status` 时不能是正常。
  - `graph_status == "unknown"` 时不能是正常。
  - 陌生状态不能是正常。
  - `time_cost_ms=inf`、`critical_path_minutes=inf`、`warning_count=nan/inf`、`total_tardiness_hours=nan/inf` 不炸页。
  - 非有限数字不能显示成 `0`、`0 小时`、`0 分钟`，也不能让总状态继续是 `ok`；应该显示未知、需要关注、解析失败这类明确异常口径。
  - 最终诊断对象能被 `json.dumps(..., allow_nan=False)` 接受。
- 更新 `tests/test_history_summary_parser.py`：
  - 含 `NaN`、`Infinity`、`-Infinity` 的 JSON 摘要进入解析失败分支。
- 保留正常可用状态的正向测试：`graph_status == "available"` 且没有异常时仍可显示正常。
- 定向验证命令：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_analysis_diagnostic_contract.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_history_summary_parser.py`

不要做：

- 不要把坏数字静默改成 0，因为 0 会让用户误以为真的没有延误。
- 不要只修模板文案；根因在状态计算和数值入口。

### Batch 3：报表日期和周计划提示一起修（F-02 + F-05）

目标：

- 报表页只填开始或只填结束时，要清楚报错。
- 周计划模拟方案预览时，只显示“模拟方案预览”，不要同时显示“对比方案”。

为什么可以合批：

- 两个问题都是页面上下文提示不准确。
- 修改点较小。
- 都是用户会直接看到的“你现在到底在看什么”的问题。

#### F-02 报表页单边日期

根因：

- 页面端的 `page_date_range_or_version_span()` 只有开始和结束都填了，才认为用户要按日期查。
- 只填一边时，它会退回版本排程范围，甚至再退到最近 7 天。
- 导出端已经用“任意一边有值就校验两边”的规则，所以页面端和导出端口径不一致。

引用链：

- `templates/reports/utilization.html` 和 `templates/reports/downtime.html` 提供日期输入。
- `web/routes/reports.py` 从 URL 取 `start_date` 和 `end_date`。
- `web/routes/report_plan_preview.py` 的 `page_date_range_or_version_span()` 决定使用用户日期、版本范围还是默认 7 天。
- `core/services/report/report_engine.py` 根据最终日期查数据。

最小修复：

- 修改 `web/routes/report_plan_preview.py` 的 `page_date_range_or_version_span()`：
  - 只要 `start_date` 或 `end_date` 任意一个有值，就调用 `validate_ymd_date()` 校验两边。
  - 只有两边都空时，才允许自动用版本排程范围或最近 7 天。

验证：

- 在 `tests/regression_reports_page_version_default_latest.py` 加页面端回归：
  - `/reports/utilization?start_date=2026-01-01` 返回 400，页面包含“缺少开始日期或结束日期”。
  - `/reports/utilization?end_date=2026-01-07` 返回 400。
  - `/reports/utilization?start_date=bad-date&end_date=2026-01-07` 返回 400，页面包含日期格式错误。
  - `/reports/utilization?start_date=2026-01-01&end_date=bad-date` 返回 400，页面包含日期格式错误。
  - `/reports/downtime?start_date=2026-01-01` 返回 400。
  - `/reports/downtime?end_date=2026-01-07` 返回 400。
  - `/reports/downtime?start_date=bad-date&end_date=2026-01-07` 返回 400，页面包含日期格式错误。
  - `/reports/downtime?start_date=2026-01-01&end_date=bad-date` 返回 400，页面包含日期格式错误。
  - 两边都空时仍能自动选择版本范围或默认范围。
- 保持导出端现有单边日期报错测试不变。
- 定向验证命令：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_reports_page_version_default_latest.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_reports_export_version_default_latest.py`

不要做：

- 不要只改 HTML 输入框，因为用户可以直接改 URL。
- 不要丢掉页面端 `scenario_id` 默认范围计算。

#### F-05 周计划模拟方案提示重复

根因：

- `adjustment_scenario_rows` 被 `is_comparison_source()` 归为 comparison 来源。
- 周计划模板分别显示“模拟方案预览”和“对比方案提示”，第二个提示只看 `is_comparison`，没有排除 `is_scenario_preview`。

引用链：

- `/scheduler/week-plan?...&plan_role=adopted&scenario_id=...` 进入周计划页。
- `web/routes/domains/scheduler/scheduler_week_plan.py` 解析 `plan_role` 和 `scenario_id`。
- `core/services/scheduler/schedule_plan_query_service.py` 解析计划来源。
- `core/models/schedule_plan_role.py` 判断来源是否 comparison。
- `templates/scheduler/week_plan.html` 展示提示。

最小修复：

- 在 `templates/scheduler/week_plan.html` 的 comparison 提示上增加 `and not plan_resolution.is_scenario_preview`。
- 暂时不要改 `is_comparison_source()`，因为它是更宽的语义，别影响别的页面。

验证：

- 扩展 `tests/regression_scenario_preview_secondary_outputs.py`：
  - scenario preview 的周计划页面出现“模拟方案预览”。
  - scenario preview 的周计划页面不出现普通“当前正在查看……对比方案”提示。
- 保留普通候选方案周计划回归，确认普通 comparison 仍显示 comparison 提示。
- 定向验证命令：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scenario_preview_secondary_outputs.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_week_plan_contract.py`

不要做：

- 不要全局把 `adjustment_scenario_rows` 从 comparison 来源里删掉。
- 不要在路由里硬删字段；这个问题更适合模板或 viewmodel 展示层处理。

### Batch 4：资源排班公开输出收口（F-06）

目标：

- 资源排班页面和导出文件名不要泄漏内部值或非法文件名字符。
- Excel 是业务用户下载查看、沟通和留档的公开输出，“来源”“锁定状态”这类列也要显示成人话。

根因：

- 文件名已有安全清洗函数，但只用在模拟方案字段和方案标签，没有用在 `scope_id`。
- 页面已经构造了 `schedule_time_display`，但模板仍显示原始 `schedule_time`。
- Excel 导出直接写 `source`、`lock_status` 原始值，而页面 JS 另有一套中文标签，导致页面和下载文件口径不一致。

引用链：

- `web/routes/domains/scheduler/scheduler_resource_dispatch.py` 进入页面和导出。
- `web/viewmodels/scheduler_history_summary.py` 构造 `schedule_time_display`。
- `templates/scheduler/resource_dispatch.html` 展示版本摘要。
- `web/viewmodels/scheduler_resource_dispatch.py` 生成导出文件名。
- `core/services/scheduler/resource_dispatch_excel.py` 写 Excel。
- `static/js/resource_dispatch.js` 已经有页面端中文标签。

最小修复：

- F-06a：页面摘要和导出文件名。
  - `web/viewmodels/scheduler_resource_dispatch.py`：`scope_id` 拼进文件名前也走安全清洗。
  - `templates/scheduler/resource_dispatch.html`：优先显示 `schedule_time_display`，没有再退到 `schedule_time`。
- F-06b：Excel 公开标签。
  - 在 Python 侧产出 `source_label`、`lock_status_label` 这类公开标签，页面和 Excel 尽量复用同一套标签，避免 JS 和 Python 两套翻译继续漂。
  - Excel 写入中文标签，同时保留未知值的明确兜底。
  - 只改单元格显示值，不改列名，不改列顺序。

验证：

- `tests/test_resource_dispatch_viewmodel.py`：
  - 危险 `scope_id` 不能让文件名出现 `/ \ : * ? " < > |`。
  - 文件名其他动态片段仍可读。
- 新增并注册回归 `tests/regression_resource_dispatch_public_output_contract.py`：
  - 版本摘要优先出现格式化后的 `schedule_time_display`。
  - 读取导出的 workbook，断言“来源”和“锁定状态”列是中文标签，不再出现 `internal`、`external`、`locked`、`urgent` 这类内部值。
  - 未知值要显示成明确未知口径，不能假装正常。
- 把 `tests/regression_resource_dispatch_public_output_contract.py` 加入 `QUALITY_GATE_GUARD_TESTS`。
- 把 `tests/regression_resource_dispatch_public_output_contract.py` 加入 `REQUIRED_REGRESSION_GROUPS["scheduler_batches_material_resource"]["target_paths"]`。
- 在 `tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions` 加断言。
- 定向验证命令：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_resource_dispatch_viewmodel.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_resource_dispatch_public_output_contract.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_resource_dispatch_export_surfaces_degraded.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scenario_preview_secondary_outputs.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_resource_dispatch_contract.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py -k "required_suite_comes_from_shared_registry_and_covers_high_risk_regressions"`

不要做：

- 不要随手改 Excel 列名或列顺序。
- 不要把所有未知内部值都翻译成“正常”，未知就应该明确显示未知。
- 不要把 Excel 标签和页面 JS 标签做成两套以后继续漂移；这批要优先把公开标签收敛到 Python 侧，再让页面和 Excel 共用或对齐。

### Batch 5：Gantt 前端错误边界（F-03）

目标：

- Gantt 数据接口返回错误、返回错误数据形状、前端缺少 Gantt 库时，页面要把真实可理解的错误显示出来，不能显示成“暂无数据”或只在控制台报错。

根因：

- `gantt_boot.js` 的错误处理主要包住请求过程，没有完整覆盖 HTTP 错误正文读取、成功响应数据形状校验、render/adapter 抛错。
- HTTP 非 2xx 时先抛固定 HTTP 错误，没有优先读取后端 JSON 里的 `error.message`。
- `tasks` 不是数组时被转成空数组，页面显示“暂无排程数据”。
- `gantt_adapter.js` 抛出 `Frappe Gantt 未加载。`，但 boot 层没有保证写入 `#ganttError`。

引用链：

- `templates/scheduler/gantt.html` 提供 `#ganttError`、`#ganttEmpty`、`#gantt`。
- `web/routes/domains/scheduler/scheduler_gantt.py` 返回 `/scheduler/gantt/data` 数据或错误 JSON。
- `static/js/gantt_boot.js` 请求接口、读取 payload、调用 render。
- `static/js/gantt_render.js` 处理空任务和渲染。
- `static/js/gantt_adapter.js` 创建 Frappe Gantt 实例。

最小修复：

- `static/js/gantt_boot.js`：
  - HTTP 非 2xx 时，先尝试读取 JSON 错误正文，优先显示 `error.message`。
  - 成功响应后校验 `payload.data` 是对象、`payload.data.tasks` 是数组。
  - `tasks` 形状不对时，显示“甘特图数据格式不对，请刷新后重试或联系维护人员”之类可见错误。
  - 包住 render 调用，把 adapter 抛出的 `Frappe Gantt 未加载。` 写到 `#ganttError`。
- 保持 `gantt_adapter.js` 不直接操作 DOM。

验证：

- 新增或扩展前端回归，例如 `tests/regression_gantt_frontend_error_boundary.py`：
  - HTTP 400 JSON 的后端错误正文展示到页面。
  - `payload.data` 缺失、是数组、是字符串等坏形状时显示数据格式错误。
  - `tasks` 是对象时显示数据格式错误，不显示空状态。
  - 缺少 `window.Gantt` 时显示 `Frappe Gantt 未加载。`，并且测试必须加载真实 `gantt_boot.js + gantt_render.js + gantt_adapter.js`，走 boot -> render -> adapter 链，不能用假 `ns.render` 直接抛错代替。
  - 合法的 `tasks: []` 仍显示空状态。
- 把 `tests/regression_gantt_frontend_error_boundary.py` 加入 `QUALITY_GATE_GUARD_TESTS`。
- 把 `tests/regression_gantt_frontend_error_boundary.py` 加入 `REQUIRED_REGRESSION_GROUPS["scheduler_analysis_gantt_reports_week_plan"]["target_paths"]`。
- 在 `tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions` 加高价值断言。
- 定向验证命令：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_frontend_error_boundary.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_page_version_default_latest.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_calendar_load_failed_degraded.py tests/regression_gantt_bad_time_rows_surface_degraded.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py -k "required_suite_comes_from_shared_registry_and_covers_high_risk_regressions"`

不要做：

- 不要把所有异常都吞成“暂无排程数据”。
- 不要在这一批拆 `gantt_render.js`，拆文件属于 P2 维护，不是 F-03 根因。
- 不要改 vendor 文件，除非后续证明必须改。

## P2 收口计划

### P2-1：关键链异常原因折叠（F-09）

目标：

- 关键链不可用时，前端仍然 fail-closed，不展示不可信关键链。
- 但后端公开合同要给维护者一个脱敏原因码，能区分读取失败、计算失败、候选行读取失败等。

根因：

- `GanttService.get_gantt_tasks()` 拿关键链失败后，只记录 `critical_chain_unavailable`。
- provider 内部能区分 `repo_exception`、`calc_exception`、`rows_exception`，但公开合同层会把一部分原因压成 `unknown`。

最小修复：

- 在关键链公开合同中保留 `available=false` 时清空 `ids/edges` 的安全规则。
- 增加或放宽脱敏 `reason_code` 白名单，至少区分：
  - `repo_exception`
  - `calc_exception`
  - `rows_exception` 或 `rows_load_exception`
  - `unknown`
- 不暴露真实异常字符串。

验证：

- 增加公开合同测试：`rows_exception` 走过 `build_gantt_contract()` 或 `GanttService.get_gantt_tasks()` 后，`reason_code` 不能被折成 `unknown`，同时 `ids/edges` 仍然清空。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_critical_chain_provider.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_critical_chain_unavailable.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_gantt_plan_role_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_critical_outline_sync.py`

### P2-2：Week/Month 假期宽度测试缺口（F-10）

目标：

- 当前代码看起来不是 bug，但缺回归。要用测试锁住：Week/Month 视图下，一个假期仍然只占一天宽度，不应该画满一整周或一整月。

根因：

- `gantt_zoom.js` 的 `dayWidth = 1440 / stepMinutes * columnWidth` 逻辑是对的。
- `gantt_render.js` 使用 `scale.dayWidth` 渲染假期块。
- 现有测试主要覆盖小时/分钟级，没有覆盖 Week/Month。

最小修复：

- 扩展 `tests/regression_gantt_zoom_decoration_sync.py`，把 `week` 和 `month` 纳入参数化测试。
- 断言 `.aps-holiday-rect` 宽度等于一天宽度，而不是整列宽度。
- 测试要跑真实 DOM 渲染链，断言假期块宽度小于整列宽度，避免以后又退回“整周/整月都涂满”。

验证：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_zoom_decoration_sync.py`

### P2-3：`gantt_render.js` 拆分（F-08）

目标：

- 降低长期维护难度。

原始判断：

- 计划阶段建议不和 P1 同批做，因为文件约 1116 行，混有筛选、图例、假期背景、缩放校验、装饰、弹窗、主渲染，拆分会影响脚本加载顺序、全局命名空间和镜像模板。

2026-05-23 实际执行更新：

- 用户后续要求继续完成整体工作后，P2-3 已实际纳入本轮实现。
- `gantt_render.js` 已按职责拆出 `gantt_popup.js`、`gantt_legend.js`、`gantt_holidays.js`、`gantt_decorations.js`、`gantt_help.js` 等前端文件。
- 两份模板已经同步新脚本顺序。
- `tests/regression_gantt_critical_outline_sync.py` 已更新脚本顺序和独立预览 HTML 断言。
- 对抗性审核又补出独立预览页缺 `gantt_help.js` 的问题，已在生成器和 tracked 证据 HTML 里同步。
- 拆分后的生产 JS 文件均控制在 500 行以内，最终证明以修复记录中的测试和门禁为准。

### P2-4：文档同步（F-11）

目标：

- 代码和测试最终完成后，再把架构文档、用户说明、vendor patch 文档同步到真实状态。

边界：

- 计划阶段只记录“待同步清单”，不要提前把文档写成“已完成”。
- 如果没有改 vendor 文件，就不要改 vendor patch 文档说 vendor 变了。

实际同步情况：

- `.codestable/architecture/ui-gantt.md` 已同步 Gantt 前端职责拆分、`gantt_help.js`、脚本加载顺序和当前“模拟调整”灰色占位事实。
- `web/viewmodels/page_manuals_scheduler_outputs.py`、`static/docs/scheduler_manual.md`、`web_new_test/static/docs/scheduler_manual.md` 已同步资源排班导出文件名清理、公开中文来源/锁定标签、模拟调整开放条件。
- `docs/frontend_manual_audit_and_rewrite_blueprint.md` 已同步资源排班说明蓝本。
- 未修改 vendor 文件，因此不更新 `.codestable/vendor/frappe-gantt-local-patches.md`。

## 总体验证顺序

每批完成后先跑该批测试。所有 P1 完成后，再跑：

- `git diff --check`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_manifest.py tests/test_full_test_debt_registry_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_resource_dispatch_overdue_summary_formats.py tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py tests/regression_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_database_high_version_failfast.py tests/regression_ensure_schema_fastforward_empty_only.py tests/regression_migration_failfast_no_backup_storm.py tests/test_database_migration_runner_delegation.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_analysis_diagnostic_contract.py tests/test_history_summary_parser.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_reports_page_version_default_latest.py tests/regression_reports_export_version_default_latest.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_scheduler_candidate_week_plan_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_resource_dispatch_viewmodel.py tests/regression_resource_dispatch_public_output_contract.py tests/regression_resource_dispatch_export_surfaces_degraded.py tests/regression_scheduler_candidate_resource_dispatch_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_frontend_error_boundary.py tests/regression_gantt_page_version_default_latest.py tests/regression_gantt_calendar_load_failed_degraded.py tests/regression_gantt_bad_time_rows_surface_degraded.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache`

如果最终要宣称“可合并”，还需要在干净工作区跑：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`

说明：

- `.codestable/audits/2026-05-23-review-report-dedupe/index.md` 里的旧验收命令是去重报告阶段的初版建议。
- 后续真正执行和验收时，以本文的批次和命令为准。

## 原计划阶段不要做的事

- 以下约束是计划阶段写给后续执行者的护栏；本轮后续已按用户要求进入实现阶段，并且 P2-3 已实际纳入当前工作区。
- 不要把坏数据静默改成正常值。
- 不要只补页面文案，不补服务端校验。
- 不要只修测试不进门禁。
- 不要大幅调整 Excel 列名或列顺序；本计划只要求把用户可见单元格值转成人话。
- 不要提前把文档写成最终状态，文档要等代码和测试落地后同步。

## 对抗性审核已回填的问题

本计划初稿完成后，已经用 4 个全新的只读子代理做过对抗性审核。审核意见已经回填，主要修订如下：

- Batch 0 补上注册表覆盖验证，防止只改一半门禁清单。
- Batch 1 补上 `migrate_with_backup()` 备份前 fail-fast，防止“先备份再失败”的副作用。
- Batch 2 补上坏数字不能显示成 `0` 或正常状态的证明。
- Batch 3 补上坏日期格式和周计划普通对比提示消失的证明。
- Batch 4 把 Excel 中文标签纳入 P1 子批，同时明确不改列名和列顺序。
- Batch 5 补上真实 boot -> render -> adapter 链路测试和 `payload.data` 坏形状测试。
- P2 补上关键链公开合同、Week/Month 真实 DOM 渲染链、`gantt_render.js` 拆分时两个模板和脚本顺序的约束。
- 所有命令统一改成 `.venv/bin/python`，符合本仓库 Python 3.8 和 Win7 兼容口径。
