---
doc_type: issue-fix
issue: 2026-05-09-scheduler-range-ui-contracts
status: completed
clean_proof_status: passed
path: fast-track
fix_date: 2026-05-10
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

本轮先做定点验证，再做干净工作区总门禁。代码修复提交为 `7abd67d0`。

已通过的定点验证：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_page_manual_registry.py tests/regression_frontend_manual_blueprint_contract.py tests/regression_frontend_ui_language_polish.py tests/regression_manual_entry_scope.py
```

结果：`41 passed`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_default_version_span.py tests/test_scheduler_run_view_result_contract.py tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_scheduler_ops_update_route_contract.py
```

结果：`32 passed`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_scheduler_reject_nonfinite_and_invalid_status.py
```

结果：`OK`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_architecture_fitness.py::test_file_size_limit tests/regression_page_manual_registry.py
```

结果：`12 passed`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_check_full_test_debt.py tests/regression_gantt_offset_range_consistency.py
```

结果：`25 passed`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_run_surfaces_resource_pool_warning.py tests/regression_frontend_ui_language_polish.py::test_manuals_keep_backend_supported_english_aliases_but_mark_them_as_compatible tests/regression_scheduler_route_enforce_ready_tristate.py
```

结果：`12 passed`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_default_version_span.py tests/test_scheduler_run_view_result_contract.py tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_scheduler_ops_update_route_contract.py tests/regression_gantt_offset_range_consistency.py tests/test_check_full_test_debt.py tests/test_architecture_fitness.py::test_file_size_limit tests/regression_page_manual_registry.py tests/regression_scheduler_run_surfaces_resource_pool_warning.py tests/regression_frontend_ui_language_polish.py::test_manuals_keep_backend_supported_english_aliases_but_mark_them_as_compatible tests/regression_scheduler_route_enforce_ready_tristate.py
```

结果：`81 passed`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check
```

结果：通过。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json
```

结果：`0 errors, 6 warnings`。6 个 warning 是既有的 `core/services/scheduler/__init__.py` 中 `__all__` 导出提示，本轮没有新增类型错误。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py
```

结果：

```json
{
  "active_xfail_count": 0,
  "collected_count": 1005,
  "collection_error_count": 0,
  "fixed_count": 5,
  "max_registered_xfail": 0,
  "status": "passed",
  "unexpected_failure_count": 0
}
```

最终 clean proof：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

结果：`质量门禁通过`。

对抗性复查：

- 只读子代理确认甘特图正常页面链路不再同时带 `start_date/end_date` 和 `week_start/offset` 两套范围。
- 只读子代理确认 `/scheduler/run` 不再把坏版本号当成 `0`、`None` 或最新版本静默放过去。
- 只读子代理确认批次详情自制工序允许设备、人员、工时留空保存；空工时落成 0；非法数字仍会被拦；外协规则未被误伤。
- 子代理指出旧 `regression_gantt_offset_range_consistency.py` 仍按旧字符串查 `gantt_boot.js`，本轮已把测试改成检查真实的“起止日期”和“周入口”二选一行为。

## 6. 收口说明

本轮收口后，三条小尾巴都已处理：

- 甘特图主查询不再提交 `week_start` 输入；视图切换只保留后端算好的起止日期；周切换按钮仍只走 `week_start/offset`。
- 正式排产成功或部分成功后，跳甘特图前必须有合法版本号；坏版本号直接显示中文错误并留在批次页，不再静默跳到别的版本。
- 批次详情自制工序保存口径统一为“可以先留空保存，正式排产前建议补齐或开启自动分配”；前端只拦填了但明显非法的工时值。

另外，总门禁一度被两个质量问题挡住，本轮也一起修掉：

- `tools/check_full_test_debt.py` 以前只吐一句“候选集合不一致”，定位非常费时间；现在会直接列出多出的或缺少的 nodeid。
- 页面帮助文字变多后，几个 viewmodel 文件超过 500 行；本轮没有加白名单，而是按主题拆成小文件，内容不变、入口不变。

浏览器手工复验说明：本轮没有重新按 `docs/dev/aps-browser-scheduler-qa-replay.md` 跑完整浏览器压测造数；本记录的完成依据是定点回归、只读对抗审查和干净工作区质量门禁。后续如果要补真实浏览器截图和导出核对，应继续按该手册复跑。
