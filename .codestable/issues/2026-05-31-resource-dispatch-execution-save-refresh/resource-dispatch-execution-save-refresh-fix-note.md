---
doc_type: issue-fix
issue: 2026-05-31-resource-dispatch-execution-save-refresh
status: done
path: fast-track
fix_date: 2026-05-31
tags: [frontend, resource-dispatch, execution-feedback]
---

# 现场记录手填保存后主表和甘特不同步修复记录

## 1. 问题描述

资源派工页在手动填写实际情况后，只立刻更新“现场记录”任务卡。任务明细表和页内甘特图里的现场状态、最近异常、影响资源仍可能停在旧数据。

## 2. 根因

`static/js/resource_execution.js` 的手填保存成功路径只调用 `replaceExecutionTask()`，它只替换 `state.execution.tasks` 并重画现场记录卡。资源派工主表和甘特使用的是 `state.data.detail_rows` / `state.data.tasks`，只有 `ns.core.loadData()` 才会重新拉取并渲染这两块数据。

## 3. 修复方案

手填保存成功后，先用后端返回的 `task_card` 立即刷新现场记录卡，再调用 `loadData()` 拉取资源派工主数据。这样和 Excel 导入成功后的刷新口径保持一致，同页几个视图最终会看到同一份现场状态。

## 4. 改动文件清单

- `static/js/resource_execution.js`
- `tests/regression_resource_dispatch_site_records_frontend_contract.py`

## 5. 验证结果

- `node --check static/js/resource_execution.js`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_resource_dispatch_actual_import.py -q`：41 passed。
- 浏览器验证：打开资源排班页，切到“现场记录”，填写实际开工并保存；保存后切回“任务明细”，任务明细能看到现场状态已更新，页面没有保存失败或加载失败提示。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/viewmodels/scheduler_resource_dispatch.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_resource_dispatch_site_records_frontend_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --fast-precheck`：通过。注意这只是快速静态预检，不是完整质量门禁证明。

## 6. 遗留事项

当前工作区已有其它未提交改动，因此本轮没有 clean-worktree proof。
