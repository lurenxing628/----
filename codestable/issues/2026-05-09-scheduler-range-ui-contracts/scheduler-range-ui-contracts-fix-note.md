---
doc_type: issue-fix
issue: 2026-05-09-scheduler-range-ui-contracts
status: pending-clean-proof
clean_proof_status: blocked_by_dirty_worktree
path: fast-track
fix_date: 2026-05-09
tags: [scheduler, gantt, week-plan, ui-contract, python38]
---

# 排产范围和界面反馈修复记录

## 1. 问题描述

这次处理的是两类用户能直接感知的问题：

- 周计划页明明选了某个指定周，但页面、表格和导出还停在旧周。
- 正式排产已经生成版本，但跳回页面后甘特图默认周看不到刚排出来的任务。

后续顺手收敛了几块页面体验：批次详情工序表列宽、资源排班视角切换、排产方案切换提示、甘特图筛选开关、人员详情导航、主操开关、关键表单中文校验和宽表长文本展示。

## 2. 根因

核心根因不是数据没有生成，而是页面和接口取范围的来源不一致：

- 周计划页同时提交 `week_start`、`start_date`、`end_date`。底层范围解析看到 `start_date/end_date` 就优先走自定义区间，所以用户新选的 `week_start` 被旧起止日期盖住。
- 甘特图在没有手动选范围时默认显示“明天所在周”，没有用所选版本实际排程的最早开始时间和最晚结束时间。新版本任务如果不在默认周，接口就按版本和时间区间过滤成空结果。

## 3. 修复方案

- 周计划只保留一个真实范围来源：`week_start + offset + version`。页面、预览、导出链接和 Excel 导出都从同一个规范化周范围出发。
- 甘特图新增版本实际跨度读取：复用 `ScheduleRepository.get_version_time_span(version)`，只把已落库的最早开始和最晚结束转成日期，不新增 SQL。
- 甘特图页面和 `/scheduler/gantt/data` 共用同一套范围判断：用户没显式选范围时用版本实际跨度；用户填了起止日期、指定周或 offset 时按请求范围走。起止日期和 offset 同时出现时，以起止日期为准，不再二次偏移。
- 正式排产成功或部分完成后跳到甘特图，并带上新版本和实际排程日期范围；失败和业务错误仍留在批次页。
- 页面体验修复只放在展示层和页面级脚本里，不改导入合同，不碰 `raw_rows_json`、preview/confirm 数据流。

## 4. 改动范围

- 周计划：`web/routes/domains/scheduler/scheduler_week_plan.py`、`templates/scheduler/week_plan.html`
- 甘特图：`core/services/scheduler/gantt_service.py`、`web/routes/domains/scheduler/scheduler_gantt.py`、`templates/scheduler/gantt.html`、`static/js/gantt_boot.js`、`static/js/gantt_render.js`、`static/css/aps_gantt.css`
- 正式排产跳转：`web/routes/domains/scheduler/scheduler_run.py`
- 页面稳定：`templates/scheduler/batch_detail.html`、`templates/scheduler/resource_dispatch.html`、`templates/scheduler/batches.html`、`static/js/resource_dispatch.js`、`static/js/scheduler_run.js`
- 表单反馈和长文本：`static/js/scheduler_form_feedback.js`、`static/css/ui_contract.css`、批次、人员、设备、工艺、报表相关模板
- 路由错误反馈：`web/routes/domains/scheduler/scheduler_ops.py`、`web/routes/personnel_pages.py`、`web/routes/equipment_pages.py`
- 镜像和说明书：`web_new_test/templates/scheduler/batches.html`、`web_new_test/templates/scheduler/gantt.html`、`static/docs/scheduler_manual.md`、`web_new_test/static/docs/scheduler_manual.md`
- 回归测试：周计划、甘特默认范围、正式排产跳转、UI 合同、资源排班、批次详情、人员设备异常路径和说明书相关测试

## 5. 验证结果

已通过：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_week_plan_summary_observability.py tests/regression_week_plan_filename_uses_normalized_version.py tests/regression_gantt_default_version_span.py tests/test_scheduler_run_view_result_contract.py tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_frontend_common_interactions.py
```

结果：`38 passed`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_run_entry_layout_contract.py tests/regression_form_run_option_checkbox_layout_contract.py tests/regression_mirror_template_sync.py
```

结果：`14 passed`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_*.py tests/regression_week_plan_*.py tests/regression_scheduler_week_plan_*.py tests/test_gantt_safe_int_parsing.py
```

结果：`59 passed`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py
```

结果：`24 passed`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_scheduler_resource_dispatch_smoke.py tests/test_resource_dispatch_viewmodel.py tests/test_resource_dispatch_labels_boundary.py tests/regression_resource_dispatch_*.py tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py tests/regression_batch_detail_linkage.py tests/regression_scheduler_batch_detail_route_contract.py tests/regression_calendar_layout_contract.py
```

结果：`45 passed`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_operator_machine_exception_paths.py tests/test_operator_machine_excel_route_error_handling.py tests/regression_operator_machine_detail_readside_normalization.py tests/regression_operator_machine_dirty_flags_visible.py tests/regression_manual_entry_scope.py tests/regression_page_manual_registry.py tests/regression_config_manual_markdown.py tests/regression_frontend_manual_blueprint_contract.py
```

结果：`29 passed`。

```bash
git diff --check
```

结果：通过。

最终 clean proof 尚未形成。原因是本轮开始前工作区已有大量未提交改动，执行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

结果被干净工作区检查拦截：`ERROR: dirty worktree: clean proof requires an empty worktree before the gate runs`。

## 6. 收口说明

本轮已经完成代码和局部回归测试层面的修复闭环，但还不能标成最终完成。原因有两个：

- 还没有做浏览器手工复验。
- 还没有在干净工作区拿到最终总门禁。

后续要形成最终验收，需要先把本轮改动和既有未提交改动按边界整理清楚，再在干净工作区跑 `scripts/run_quality_gate.py --require-clean-worktree`，并按 `docs/dev/aps-browser-scheduler-qa-replay.md` 补周计划导出和正式排产后甘特图可见性的页面记录。
