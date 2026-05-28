---
doc_type: issue-fix
issue: 2026-05-28-resource-dispatch-feedback-reason-copy
path: fast-track
fix_date: 2026-05-28
status: completed
severity: P3
tags:
  - scheduler
  - resource-dispatch
  - frontend-copy
---

# 资源排班现场反馈禁用原因文案修复记录

## 问题

资源排班页进入“现场反馈”后，待开工任务卡会显示多条不可操作原因。

原页面把多条完整句子直接用分号拼在一起，例如：

`当前状态是待开工，不能完工。；当前状态是待开工，不能暂停。`

句号和分号连在一起，用户看起来像是页面文案坏了。

## 根因

`static/js/resource_dispatch.js` 的 `executionUnavailableReasonText()` 直接把后端返回的每条禁用原因用 `；` 拼接。

后端返回的每条原因本身已经带句号，所以前端再加分号时就出现了 `。；`。同时，同一个状态下的多条原因没有合并，读起来重复。

## 修复

- 前端先把每条原因末尾的句号、分号等收尾标点去掉。
- 对“当前状态是 X，不能 Y”这一类原因做合并，显示成一句大白话。
- 卡片正文按按钮顺序展示禁用动作，避免“完工、暂停、报异常、继续生产”这种不自然顺序。
- 每个按钮自身的禁用原因仍保留在按钮 `title` 上，不改变后端接口和提交逻辑。

修复后示例：

`当前状态是待开工，不能暂停、继续生产、完工、报异常。`

## 改动文件

- `static/js/resource_dispatch.js`
- `tests/regression_operation_execution_feedback_routes.py`

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_operation_execution_feedback_routes.py::test_resource_dispatch_frontend_posts_execution_button_clicks -q`
- `git diff --check -- static/js/resource_dispatch.js tests/regression_operation_execution_feedback_routes.py`
- 浏览器刷新 `http://127.0.0.1:61731/scheduler/resource-dispatch?version=8&start_date=2026-06-01&end_date=2026-06-30&plan_role=adopted&period_preset=custom`，进入“现场反馈”，确认首张任务卡文案为 `当前状态是待开工，不能暂停、继续生产、完工、报异常。`，不再包含 `。；`。

## 遗留说明

当前工作区在本次修复前已有设备 Excel 导入相关未提交改动和一份未跟踪探索记录。本次只处理资源排班现场反馈文案问题，未清理、回退或覆盖那些已有改动。
