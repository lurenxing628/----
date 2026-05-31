---
doc_type: issue-fix
issue: 2026-05-31-resource-dispatch-view-records-action-contract
status: done
path: fast-track
fix_date: 2026-05-31
tags: [frontend, resource-dispatch, available-actions]
---

# 查看计划和实际按钮动作合同修复记录

## 1. 问题描述

现场记录卡片里的“填写实际情况”按钮已经按后端 `available_actions` 判断是否可点，但“查看计划和实际”按钮只看 `op_id` 是否存在。这会让前端绕过服务端动作合同。

## 2. 根因

`static/js/resource_execution.js` 的 `renderExecutionActions()` 只从 `available_actions` 里找 `fill_actual`，没有找 `view_records`。因此后端如果未来禁用 `view_records`，前端仍可能把按钮画成可点击。

## 3. 修复方案

新增统一的 `executionAction()` 查找函数，让 `fill_actual` 和 `view_records` 都从 `available_actions` 获取：

- 按 `enabled` 决定按钮是否禁用。
- 按 `disabled_reason` 设置禁用提示。
- 按 `label` 渲染按钮文案。
- `op_id` 缺失只作为无法发请求时的本地保护，不再作为按钮可用性的主要来源。

## 4. 改动文件清单

- `static/js/resource_execution.js`
- `tests/regression_resource_dispatch_site_records_frontend_contract.py`

## 5. 验证结果

- `node --check static/js/resource_execution.js`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_resource_dispatch_actual_import.py -q`：41 passed。
- 浏览器验证：打开资源排班页，切到“现场记录”，页面正常显示“填写实际情况”“查看计划和实际”“导入实际情况 Excel”和反馈人输入框，没有脚本加载失败或现场记录加载失败提示。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/viewmodels/scheduler_resource_dispatch.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_resource_dispatch_site_records_frontend_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --fast-precheck`：通过。注意这只是快速静态预检，不是完整质量门禁证明。

## 6. 遗留事项

当前工作区已有其它未提交改动，因此本轮没有 clean-worktree proof。
