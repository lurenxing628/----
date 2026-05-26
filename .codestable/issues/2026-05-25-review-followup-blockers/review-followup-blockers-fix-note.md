---
doc_type: issue-fix
issue: 2026-05-25-review-followup-blockers
path: fast-track
fix_date: 2026-05-25
status: completed
tags: [review, scheduler, excel-template, codestable, manual]
---

# Review 后续阻塞问题修复记录

## 背景

用户要求把当前 review 后仍需要修的问题全部修掉，并且对大量读取和最终复审使用 Sub Agent。

本轮实际处理的是这些可落地问题：

- 工种、供应商 Excel 模板表头新旧不一致。
- 零件工序工时导入模板说明和真实表头不一致。
- 候选方案标签可能把“最终采用方案”显示成“正式采用方案方案”。
- 甘特图、周计划在“想看对比方案但明细不存在，页面回退到正式采用方案”时，会同时显示两种互相打架的提示。
- CodeStable compound 文档使用了下划线字段名，和项目约定的 `superseded-by` 不一致。

## 已修内容

- Excel 默认模板登记了旧表头，只允许把已知旧表头自动刷新成新表头。
- 顶层模板和 `templates_excel/转换输出/` 下的工种、供应商实体 Excel 表头已统一为“工种编号 / 供应商编号”。
- 零件工序工时导入模板相关说明统一使用 `换型时间(h)` 和 `单件工时(h)`。
- 候选方案标签先替换完整的“最终采用方案”，再替换短的“最终采用”，避免重复“方案”。
- 甘特图、周计划只有真的在看对比方案时才显示“对比参考方案”提示；如果已经回退到正式采用方案，只显示回退提示。
- 两份被新 roadmap 覆盖的 compound 文档改用 `superseded-by`。

## 当前验证

已通过：

- `.venv/bin/python -m pytest -q tests/regression_scheduler_candidate_plan_query_contract.py::test_plan_candidate_label_does_not_duplicate_adopted_plan_suffix tests/regression_scheduler_candidate_analysis_contract.py::test_candidate_display_does_not_duplicate_adopted_plan_suffix tests/test_codestable_tools_contract.py::test_compound_superseded_documents_use_hyphenated_field tests/regression_scheduler_candidate_gantt_plan_role_contract.py::test_gantt_missing_valid_plan_role_page_only_shows_fallback_notice tests/regression_scheduler_candidate_week_plan_contract.py::test_week_plan_missing_valid_plan_role_page_only_shows_fallback_notice tests/regression_frontend_ui_language_polish.py::test_ensure_excel_templates_refreshes_known_legacy_id_headers`
- `.venv/bin/python -m pytest -q tests/regression_excel_template_contracts.py tests/regression_excel_hidden_payload_contract.py tests/regression_unit_excel_template_headers.py tests/test_excel_template_download_validation.py tests/regression_process_excel_part_operation_hours_import.py tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py tests/regression_scheduler_candidate_week_plan_contract.py tests/test_codestable_tools_contract.py`
- `.venv/bin/python -m pytest -q tests/regression_config_manual_markdown.py tests/regression_page_manual_registry.py tests/regression_frontend_ui_language_polish.py`
- `.venv/bin/python -m pytest -q tests/regression_excel_template_contracts.py tests/regression_excel_hidden_payload_contract.py tests/regression_unit_excel_template_headers.py tests/test_excel_template_download_validation.py tests/regression_process_excel_part_operation_hours_import.py tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py tests/regression_scheduler_candidate_week_plan_contract.py tests/test_codestable_tools_contract.py tests/regression_config_manual_markdown.py tests/regression_page_manual_registry.py tests/regression_frontend_ui_language_polish.py`
- `git diff --check`

## 复审状态

已完成对抗性 Sub Agent 复审。第一轮发现 `templates_excel/转换输出/工种配置.xlsx` 仍残留 `internal/external` 样例值且缺少下拉，已修复后复审通过。后续小复审发现下拉清理逻辑可能误删非目标列下拉，已改成只移除目标列范围，并补了内存工作簿回归；最后一轮复审未发现阻塞问题。

## 2026-05-25 补充修复

后续 review 又发现几类残留问题，本轮继续按“主 Agent 统筹 + Sub Agent 分方向只读 + 修复后对抗复审”的方式处理。

### 补充处理范围

- 报表预览、周计划页的无历史/缺方案兜底结果仍有旧 `selected` 状态或缺少 `status/source_table/candidate_id/candidate_key`。
- 旧分析兼容提示测试仍期望旧字段文案，和当前用户文案“系统比较顺序”不一致。
- 资源排班任务 id 生成里出现忽略式编码参数，会静默吞掉坏 Unicode；同时公开任务 id 需要既不暴露内部 `schedule_id/op_id`，又不能丢掉唯一性。
- 前端离线资源扫描漏掉远程图片、`srcset`、CSS `url(...)`、不带引号的属性和 `object data`。
- 周计划说明把按钮名“导出周计划表.xlsx”和真实下载文件名混在一起；审计文档仍有旧 `_to_` 文件名示例。
- CodeStable roadmap 账本正文仍有下划线字段名旧写法。
- Excel 检查结果状态日志仍保留“预览基线”旧口径。
- 若干本轮相关测试里仍有忽略式解码参数，会吞掉响应解码错误。

### 补充已修内容

- `web/routes/report_plan_preview.py` 和 `web/routes/domains/scheduler/scheduler_week_plan.py` 改为复用 `default_plan_resolution_dict()`，统一 `resolved_adopted / fallback_to_adopted` 等字段口径，并保留调用侧 `version`。
- 补报表默认兜底、周计划兜底和“已有 plan_role_resolution 不被覆盖”的回归测试。
- 资源排班任务 id 改为严格 UTF-8 编码；公开 id 的可读前缀做安全字符收敛，内部唯一信息只进入 hash，不直接暴露到前端 id。
- 补资源排班 id 的坏 Unicode、隐藏身份参与 hash、逗号/斜杠不破坏依赖串的回归测试。
- 前端离线扫描改成严格 UTF-8 读取，补远程图片、`srcset`、CSS `url(...)`、不带引号属性、`object data` 的检测和测试。
- 周计划页面帮助手册、完整手册、web_new_test 手册改成“点击按钮后下载的 Excel 为准，真实文件名按版本和周范围自动生成”。
- `docs/manual_audit_report.md` 的周计划示例改为中文“至”格式。
- CodeStable roadmap 账本正文的下划线字段名改为 `superseded-by`。
- Excel 检查结果状态日志改为“检查结果状态比较失败”，测试同步更新。
- 本轮相关测试中的响应解码去掉忽略式参数。
- `tests/regression_gantt_critical_chain_provider.py` 的计划身份夹具不再使用旧 `status: "selected"`。

### 补充验证

已通过：

- `PYTHONDONTWRITEBYTECODE=1 python3.8 -m pytest -q -p no:cacheprovider tests/regression_resource_dispatch_task_id_encoding.py tests/regression_frontend_offline_static_assets.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py tests/test_scheduler_resource_dispatch_smoke.py tests/regression_report_export_size_mode_selection.py tests/regression_reports_export_version_default_latest.py tests/regression_gantt_critical_chain_provider.py`
- `PYTHONDONTWRITEBYTECODE=1 python3.8 -m pytest -q -p no:cacheprovider tests/regression_schedule_result_view_context.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_candidate_week_plan_contract.py tests/regression_frontend_offline_static_assets.py tests/regression_resource_dispatch_task_id_encoding.py tests/regression_page_manual_registry.py tests/regression_config_manual_markdown.py tests/test_excel_utils_compare_digest_guard.py tests/test_codestable_tools_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 python3.8 -m pytest -q -p no:cacheprovider tests/regression_resource_dispatch_task_id_encoding.py tests/regression_frontend_offline_static_assets.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py tests/test_scheduler_resource_dispatch_smoke.py tests/regression_report_export_size_mode_selection.py tests/regression_reports_export_version_default_latest.py tests/regression_gantt_critical_chain_provider.py tests/regression_schedule_result_view_context.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_candidate_week_plan_contract.py tests/regression_page_manual_registry.py tests/regression_config_manual_markdown.py tests/test_excel_utils_compare_digest_guard.py tests/test_codestable_tools_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/ruff check core/services/scheduler/resource_dispatch_rows.py tests/regression_resource_dispatch_task_id_encoding.py tests/regression_frontend_offline_static_assets.py web/routes/report_plan_preview.py web/routes/domains/scheduler/scheduler_week_plan.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_candidate_week_plan_contract.py web/routes/excel_utils.py tests/test_excel_utils_compare_digest_guard.py`
- `PYTHONDONTWRITEBYTECODE=1 python3.8 -m pytest -q -p no:cacheprovider tests/test_excel_utils_compare_digest_guard.py tests/regression_frontend_offline_static_assets.py tests/regression_resource_dispatch_task_id_encoding.py`
- `git diff --check`

### 补充复审状态

- 第一轮补充对抗复审发现资源排班任务 id 唯一性、依赖字符串安全、离线资源未加引号属性、`object data`、测试断言粒度等问题；已修复并补测试。
- 第二轮补充对抗复审发现 `ruff I001` import 顺序问题；已用 ruff 整理相关 import 并复验通过。
- 最后一轮补充对抗复审未发现本轮交付阻塞问题。

## 2026-05-25 再复审补修

本轮继续处理 review 后残留的阻塞点，重点是 Python 3.8 兼容、测试合同稳定性、甘特模拟方案发布护栏，以及工种/供应商 Excel 导入把数字 `0` 当空值的问题。

### 再补修范围

- `tests/regression_scheduler_missing_resource_message.py` 与 `tests/regression_excel_template_contracts.py` 清理 Python 3.8 不支持或扫描器会判为风险的泛型注解写法。
- `tests/test_codestable_tools_contract.py` 不再把 `search-yaml.py` 的过滤行为绑定到真实 compound 文件名，改用临时文档验证 `superseded-by` 过滤。
- `tests/regression_scheduler_candidate_week_plan_contract.py` 不再要求复用同一个字典对象，只要求页面真正依赖的字段保持不变。
- `core/services/process/op_type_excel_import_service.py` 和 `core/services/process/supplier_excel_import_service.py` 同时识别新列和旧列，并保留数字 `0` 转成的 `"0"` 编号。
- `tests/regression_gantt_scenario_publish.py` 补充真实服务链路回归：基于对比方案保存出来的模拟方案不能被发布为正式方案，失败后正式表和发布字段都不能被改写。

### 再补修验证

已通过：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_gantt_scenario_publish.py tests/test_excel_import_hardening.py tests/test_supplier_excel_import_remark_normalization.py tests/test_codestable_tools_contract.py tests/regression_scheduler_candidate_week_plan_contract.py tests/regression_scheduler_missing_resource_message.py`
- `.venv/bin/python tools/scan_py38plus_syntax.py tests/regression_scheduler_missing_resource_message.py tests/regression_excel_template_contracts.py --json --fail-on-hit`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/ruff check core/services/process/op_type_excel_import_service.py core/services/process/supplier_excel_import_service.py tests/regression_scheduler_missing_resource_message.py tests/regression_excel_template_contracts.py tests/test_codestable_tools_contract.py tests/regression_scheduler_candidate_week_plan_contract.py tests/test_excel_import_hardening.py tests/test_supplier_excel_import_remark_normalization.py tests/regression_gantt_scenario_publish.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile core/services/process/op_type_excel_import_service.py core/services/process/supplier_excel_import_service.py tests/regression_scheduler_missing_resource_message.py tests/regression_excel_template_contracts.py tests/test_codestable_tools_contract.py tests/regression_scheduler_candidate_week_plan_contract.py tests/test_excel_import_hardening.py tests/test_supplier_excel_import_remark_normalization.py tests/regression_gantt_scenario_publish.py`
- `git diff --check -- core/services/process/op_type_excel_import_service.py core/services/process/supplier_excel_import_service.py tests/regression_scheduler_missing_resource_message.py tests/regression_excel_template_contracts.py tests/test_codestable_tools_contract.py tests/regression_scheduler_candidate_week_plan_contract.py tests/test_excel_import_hardening.py tests/test_supplier_excel_import_remark_normalization.py tests/regression_gantt_scenario_publish.py`

### 再补修复审状态

- 第一轮分方向只读 Sub Agent 发现 Python 3.8 注解、甘特对比方案发布测试缺口、测试脆弱断言、数字 `0` 编号被当空值四类问题。
- 修复后按方向派出 3 个对抗复审 Sub Agent，均未发现阻塞问题。
- 其中供应商旧列 `供应商ID=0` 与模拟方案发布字段回滚属于非阻塞补强，已一并补入测试。
- 最终整体对抗复审发现 `schedule_result_view_context.py` 仍从 `schedule_plan_query_service.py` 间接导入 `is_comparison_source`，测试收集阶段会断链；已改为从真正定义处 `core.models.schedule_plan_role` 直接导入。
- 最终门禁复验发现 `resource_dispatch_rows.py` 和 `schedule_plan_query_service.py` 超过 500 行；已把资源排班公开任务 id 生成拆到 `resource_dispatch_task_ids.py`，并整理方案查询服务 import，核心文件重新低于 500 行。
- 复修后已补跑资源排班、方案查询、周计划、视图上下文相关回归：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_resource_dispatch_task_id_encoding.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/test_scheduler_resource_dispatch_smoke.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_schedule_result_view_context.py tests/regression_scheduler_candidate_week_plan_contract.py`，结果 `40 passed`。
- 最终一揽子本地验证通过：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_gantt_scenario_publish.py tests/test_excel_import_hardening.py tests/test_supplier_excel_import_remark_normalization.py tests/test_codestable_tools_contract.py tests/regression_scheduler_candidate_week_plan_contract.py tests/regression_scheduler_missing_resource_message.py tests/regression_resource_dispatch_task_id_encoding.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/test_scheduler_resource_dispatch_smoke.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_schedule_result_view_context.py`，结果 `94 passed`。
  - `.venv/bin/python tools/scan_py38plus_syntax.py tests/regression_scheduler_missing_resource_message.py tests/regression_excel_template_contracts.py core/services/scheduler/resource_dispatch_task_ids.py --json --fail-on-hit`，结果 `total_findings: 0`。
  - 本轮涉及文件的 `ruff check`、`py_compile`、`git diff --check` 均通过。
  - `tests/test_architecture_fitness.py::test_file_size_limit` 通过，核心相关文件行数为：`resource_dispatch_rows.py` 462 行、`resource_dispatch_task_ids.py` 63 行、`schedule_plan_query_service.py` 498 行、`schedule_result_view_context.py` 403 行。
- 最终整体复验 Sub Agent 两个方向均返回 OK，无阻塞；当前工作区仍有大量既有未提交改动，因此这不是 clean-worktree proof。

## 2026-05-26 Review finding 补修

本轮处理当前工作区 review 后确认的两条问题：资源派工无 `schedule_id` 行摘要少算任务，以及“导出工序清单”页面说明写了不存在的导出列。

### 修复范围

- `core/services/scheduler/resource_dispatch_task_ids.py`：只修无 `schedule_id`、有 `op_id` 时的内部行身份。
- `tests/regression_resource_dispatch_task_id_encoding.py`：补同工序同时间但不同资源的摘要计数回归。
- `web/viewmodels/page_manuals_process_excel.py`：把“导出工序清单”说明改回真实 6 列。
- `tests/regression_page_manual_registry.py`：锁住页面说明中的真实列名，并禁止旧错误列名回流。

### 根因

- 资源派工原本把有 `op_id` 的无 `schedule_id` 行识别为 `op_id + 开始时间 + 结束时间`，没有包含原始设备和人员，所以不同资源上的两条派工行会在摘要里被当作一条。
- “导出工序清单”的真实导出列是 `图号 / 工序 / 工种 / 归属 / 供应商 / 周期`，页面说明却写成包含零件名称、换型时间、单件工时等更多列。

### 修复方式

- 在 `row_identity()` 的 `op_id` 分支加入 `machine_id` 和 `operator_id`，让身份源头和真实资源派工行保持一致。
- 不改真实导出格式，只修正页面说明，避免把文档错误扩大成用户可见导出契约变更。

### 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_resource_dispatch_task_id_encoding.py tests/regression_page_manual_registry.py`：`19 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py core/services/scheduler/resource_dispatch_task_ids.py tests/regression_resource_dispatch_task_id_encoding.py web/viewmodels/page_manuals_process_excel.py tests/regression_page_manual_registry.py --json --fail-on-hit`：`total_findings: 0`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold`：`2 passed`。
- `.venv/bin/ruff check core/services/scheduler/resource_dispatch_task_ids.py tests/regression_resource_dispatch_task_id_encoding.py web/viewmodels/page_manuals_process_excel.py tests/regression_page_manual_registry.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile core/services/scheduler/resource_dispatch_task_ids.py tests/regression_resource_dispatch_task_id_encoding.py web/viewmodels/page_manuals_process_excel.py tests/regression_page_manual_registry.py`：通过。
- `git diff --check -- core/services/scheduler/resource_dispatch_task_ids.py tests/regression_resource_dispatch_task_id_encoding.py web/viewmodels/page_manuals_process_excel.py tests/regression_page_manual_registry.py .codestable/issues/2026-05-25-review-followup-blockers/review-followup-blockers-fix-note.md`：通过。

### 本轮对抗复审

- 资源派工方向复审未发现阻塞问题；按建议补充了“只换设备 / 只换人员也应区分”和“同一真实任务同时落在班组人员轴、设备轴时不应双算”的测试。
- 手册方向复审发现“工种名称 / 工时数据 / 换型时间或单件工时”旧口径残留；已清理并补强 forbidden phrases。
- 整体复审提醒暂存区不是最新修复。当前未执行 stage / commit，本轮交付以工作区文件为准。

## 2026-05-26 当前工作区 review 补修

本轮处理当前 review 明确指出的 3 类问题：

- 资源派工公开 `task.id` 会随查询区间变化。
- 缺资源即时提示缺少图号 / 零件 / 件号上下文，并且脏业务字段可能直接进 flash。
- `tests/test_codestable_tools_contract.py` 依赖的 3 份 issue fix-note 仍是未跟踪文件。

### 修复内容

- `core/services/scheduler/resource_dispatch_task_ids.py` 收窄 `public_task_id()` 入参，只按原始排班行身份生成公开 id。
- `core/services/scheduler/resource_dispatch_rows.py` 不再把查询区间裁剪后的可见开始 / 结束时间传入 id 生成函数。
- `core/algorithms/greedy/dispatch/sgs_scoring.py` 复用 `public_safe_identifier()` / `public_safe_label()` 生成缺资源用户提示，提示中补入图号、零件和件号；脏值被清掉但错误仍正常抛出。
- `core/services/scheduler/run/schedule_input_builder.py` 将 `BatchOperation.piece_id` 透传到 `OpForScheduleAlgo`，让算法深处能拿到件号上下文。
- 将 `quality-gate-timeout`、`route-parser-supplier-global-scope`、`review-followup-blockers` 三份 fix-note 纳入 Git 索引，避免干净环境缺文档导致合同测试失败。

### 验证结果

已通过：

- `python3.8 -m pytest -q tests/regression_resource_dispatch_task_id_encoding.py tests/regression_scheduler_missing_resource_message.py tests/test_schedule_input_builder_strict_hours_and_ext_days.py tests/test_codestable_tools_contract.py`：`40 passed`。
- `python3.8 -m pytest -q tests/regression_resource_dispatch_task_id_encoding.py tests/regression_resource_dispatch_public_output_contract.py tests/regression_resource_dispatch_viewmodel_public_output_contract.py tests/test_resource_dispatch_viewmodel.py tests/regression_scheduler_missing_resource_message.py tests/test_schedule_input_builder_strict_hours_and_ext_days.py tests/regression_scheduler_user_visible_messages.py tests/test_codestable_tools_contract.py`：`108 passed`。
- `python3.8 -m py_compile` 覆盖本轮生产代码和测试文件：通过。
- `git diff --check` 与 `git diff --cached --check`：通过。

### 对抗复审

- 资源派工方向复审 OK，无阻塞；按建议补了不同资源下 `task.id` 不重复的直接断言。
- 缺资源提示方向复审 OK，无阻塞；确认脏字段不会直接进入页面 flash。
- CodeStable 文档方向复审发现 3 份 fix-note 仍未被 Git 跟踪；已用 `git add` 将这 3 份文件纳入索引，并用 `git ls-files --stage` 确认有输出。
- 最终整体复审发现 `schedule_input_builder.py` 存量返回注解仍使用 Python 3.8 不支持的 `A | B` 写法；已改为 `Union[...]`，并用 `tools/scan_py38plus_syntax.py` 复验 `total_findings: 0`。

当前工作区仍有大量既有未提交改动，因此这不是 clean-worktree proof。

## 2026-05-26 自动派工错误链路补修

本轮继续处理当前工作区 review 后暴露的自动派工错误链路问题，目标是让用户看到真实可处理的原因，同时避免把内部诊断、脏字段或误导性的“去补设备/人员”提示暴露到页面。

### 修复范围

- `core/algorithms/greedy/auto_assign.py`：把自动派工从只返回设备/人员，扩展为返回“成功或失败原因”的结果对象。
- `core/algorithms/greedy/internal_operation.py`、`core/algorithms/greedy/dispatch/sgs_scoring.py`：按失败原因生成用户能看懂的提示，不再把自动派工失败误说成普通缺资源。
- `core/algorithms/greedy/dispatch/resource_validation.py`：集中生成 SGS 缺资源和自动派工失败提示，避免算法评分文件继续变大。
- `core/services/scheduler/run/auto_assign_resource_errors.py`：集中识别自动派工资源错误，供空结果提示和结果摘要共同复用。
- `core/services/scheduler/run/schedule_payload_contract.py`、`core/services/scheduler/run/schedule_orchestrator.py`、`core/services/scheduler/run/schedule_persistence_errors.py`：空结果时保留算法真实错误，并优先展示自动派工根因。
- `core/services/scheduler/summary/schedule_summary_assembly.py`：部分成功时过滤自动派工失败工序，避免继续显示在“缺设备/人员”面板里。
- `core/models/scheduler_public_errors.py`：把普通派工和 SGS 自动派工的安全文案加入公开错误白名单，敏感内容仍降级为通用提示。
- `core/infrastructure/errors.py`、`core/services/scheduler/schedule_service.py`、`web/error_handlers.py`：增加仅日志可见的 `internal_details`，页面响应不带内部工序 id 和诊断原因。
- `.codestable/tools/validate-yaml.py`：新增 `--require-yaml`，避免纯 YAML 扫描和 Markdown frontmatter 扫描互相影响。
- `core/services/scheduler/resource_dispatch_task_ids.py`：让资源派工任务 id 在人员视角和设备视角保持稳定。

### 关键根因

- 自动派工深处原来只把“找到/没找到”传出来，到了外层就分不清是缺工种、资料不完整、没有可用组合，还是工时不合法。
- 空结果保存链路原来只看普通校验错误，`batch_order` 全失败时可能丢掉算法摘要里的真实错误。
- 部分成功摘要先记录了“原始工序缺设备/人员”，但没有扣掉“其实是自动派工失败”的工序，所以页面会给出错误补救方向。
- 公开错误白名单只认普通派工短句，不认 SGS 评分阶段生成的长句，安全文案会被误降级成“联系管理员”。
- `schedule_summary_assembly.py` 在补逻辑后触碰 500 行门禁，需要把自动派工错误识别收进独立小模块。

### 验证结果

已通过：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_error_boundary_contract.py tests/regression_schedule_persistence_reject_empty_actionable_schedule.py tests/regression_scheduler_summary_result_summary_contract.py tests/regression_scheduler_user_visible_messages.py tests/regression_scheduler_missing_resource_message.py tests/regression_resource_dispatch_task_id_encoding.py tests/test_codestable_tools_contract.py tests/test_greedy_refactor_contracts.py -p no:cacheprovider`：`156 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py tests/test_run_quality_gate.py tests/regression_quality_gate_scan_contract.py -p no:cacheprovider`：`157 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --fast-precheck`：通过；这是快速预检，不是 clean-worktree 完整门禁证明。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py $( { git diff --name-only -- '*.py'; git diff --cached --name-only -- '*.py'; git ls-files --others --exclude-standard -- '*.py'; } | sort -u ) --fail-on-hit`：扫描 123 个文件，`总发现数: 0`。
- `git diff --check`：通过。
- 重点文件行数：`schedule_summary_assembly.py` 476 行、`auto_assign_resource_errors.py` 77 行、`scheduler_public_errors.py` 315 行、`resource_validation.py` 154 行。

### 对抗复审

- 第一轮复审发现：普通派工全失败时会回到缺资源提示、部分成功摘要仍显示缺资源面板、公开错误文案会降级、资源派工测试未进门禁、`resource_validation.py` 未跟踪。
- 修复后第二轮复审发现：`工时不合法` 分支没有被摘要过滤，`schedule_summary_assembly.py` 超过 500 行，SGS 详细文案白名单缺失。
- 已把 `工时不合法：工序 ...` 纳入公共自动派工错误识别，把摘要文件降到 476 行，并补了 SGS 自动派工详细文案不会降级、敏感文案仍隐藏的测试。

### 提交注意

- 当前仍未执行本轮统一 `git add` / `commit`。
- 本轮新增且必须随修复提交的文件包括：
  - `core/algorithms/greedy/dispatch/resource_validation.py`
  - `core/services/scheduler/run/auto_assign_resource_errors.py`
- 当前工作区还有大量既有未提交改动，因此这不是 clean-worktree proof。

### 末轮对抗复审补修

- 对抗复审发现 `core/models/scheduler_public_errors.py` 的公开错误分类函数复杂度超过门禁阈值；已改成前缀表和标记表驱动，避免继续堆 `if`。
- 对抗复审提醒摘要侧只覆盖了部分自动派工错误；已把缺工种、资料不完整、无可用组合、工时不合法 4 类都纳入回归。
- 对抗复审提醒工序号解析不应靠空格截断；已改为按当前工序清单里的完整 `op_code` 匹配，并补了带空格工序号的摘要过滤测试。
- 补修后验证：
  - `.venv/bin/python -m pytest -q tests/test_architecture_fitness.py`：`21 passed`。
  - `.venv/bin/python -m pytest -q tests/regression_scheduler_summary_result_summary_contract.py::test_auto_assign_failure_does_not_render_as_missing_resource_panel tests/regression_scheduler_summary_result_summary_contract.py::test_auto_assign_failure_filter_matches_full_op_code_with_spaces tests/regression_scheduler_user_visible_messages.py::test_sgs_auto_assign_errors_keep_public_details tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold`：`7 passed`。
  - `.venv/bin/python -m ruff check --no-cache -- core/models/scheduler_public_errors.py core/services/scheduler/run/auto_assign_resource_errors.py tests/regression_scheduler_summary_result_summary_contract.py tests/regression_scheduler_user_visible_messages.py`：通过。

## 2026-05-26 手册方案尝试表列名补修

当前工作区 review 发现完整手册和 web_new_test 手册把“方案尝试表”写成包含单独“整体表现”列，但真实页面模板只渲染“条形”列，整体表现只体现在条形进度条里。

本轮只修正文档，不改页面模板：

- `static/docs/scheduler_manual.md`：删除不存在的“整体表现”表格行，把说明合并到“条形”行。
- `web_new_test/static/docs/scheduler_manual.md`：同步同一处说明。

验证结果：

- `.venv/bin/python -m pytest -q tests/regression_config_manual_markdown.py tests/regression_page_manual_registry.py -p no:cacheprovider`：`12 passed`。
- `rg -n "\\| 整体表现 \\|" static/docs/scheduler_manual.md web_new_test/static/docs/scheduler_manual.md templates/scheduler/analysis_parts/_optimization_process.html`：无匹配，确认手册不再声明页面没有的独立列。

## 2026-05-26 Review 后阻塞问题补修

本轮处理当前工作区 review 发现的两个 P1 问题，并同步收敛暂存区和工作区不自洽风险。

### 修复范围

- `core/models/scheduler_public_errors.py`：把 SGS 普通缺设备、缺人员、缺设备和人员的安全长句加入公开错误白名单，并把这类句子归类为 `missing_internal_resource`。
- `core/services/scheduler/run/auto_assign_resource_errors.py`：识别 `工时不合法：工序 ...` 时不再按空格截断工序号，改为把前缀后的完整内容交给真实工序号匹配，支持 `OP SPACE 001` 这类带空格工序号。
- `tests/regression_scheduler_user_visible_messages.py`：补 SGS 普通缺资源长句保留原文、脏内容仍转通用错误的回归。
- `tests/regression_scheduler_summary_result_summary_contract.py`：补带空格工序号自动派工失败过滤，以及“带诊断细节的工时错误不能被误扣成自动派工失败”的回归。

### 关键根因

- 公开错误白名单之前只覆盖自动派工失败长句，没有覆盖 SGS 普通缺资源长句，导致本来安全、用户能处理的提示被降级成“联系管理员”。
- 摘要过滤自动派工失败时，旧逻辑对 `工时不合法：工序 ...` 的尾部依赖空格边界，遇到带空格的工序号会匹配失败；如果继续宽松按空格匹配，又会把 `OP10 工时字段不合法...` 这种内部诊断误扣掉。

### 验证结果

已通过：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_summary_result_summary_contract.py::test_auto_assign_failure_filter_matches_full_op_code_with_spaces tests/regression_scheduler_summary_result_summary_contract.py::test_invalid_hours_detail_does_not_get_deducted_as_auto_assign_failure tests/regression_scheduler_user_visible_messages.py::test_sgs_missing_resource_error_keeps_public_details`：`3 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_user_visible_messages.py tests/regression_scheduler_missing_resource_message.py tests/regression_scheduler_summary_result_summary_contract.py tests/regression_schedule_persistence_reject_empty_actionable_schedule.py tests/regression_error_boundary_contract.py`：`117 passed`。

### 对抗复审结论

- 公开错误链路复审确认最小修复点在 `scheduler_public_errors.py`，不需要放宽全局白名单，也不应该让带敏感路径、Traceback 的句子进入页面。
- 自动派工摘要链路复审确认要按当前工序清单里的完整 `op_code` 匹配，不能把公开错误白名单当作内部工序号解析器。
- 暂存区复审发现多组已暂存测试依赖未暂存生产代码，后续通过精确 `git add` 同步配套文件，不使用 `git add .`。

### 对抗复审补修

- 复审发现 `工时不合法：工序 OP SPACE 001` 在摘要过滤里已经能识别完整工序号，但公开错误清洗仍会显示成 `工时不合法：工序 OP`。
- 已把普通工时/外协周期错误改为按真实诊断标记截断：遇到 `工时字段不合法`、`工时总量不合法`、`ext_days=` 时去掉内部诊断；没有这些诊断标记时保留完整安全工序号。
- 补了公开错误测试和摘要错误列表断言，确认 `OP SPACE 001` 不再被截断，同时 `setup_hours='abc'` 仍不会出现在用户可见错误里。
