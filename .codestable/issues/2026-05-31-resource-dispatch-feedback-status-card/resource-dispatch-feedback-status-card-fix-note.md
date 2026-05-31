---
doc_type: issue-fix
slug: resource-dispatch-feedback-status-card
status: done
path: fast-track
created: 2026-05-31
last_reviewed: 2026-05-31
tags:
  - aps
  - frontend
  - resource-dispatch
---

# 资源派工重复状态卡修复记录

## 1. 问题

资源派工页版本摘要里原来有一张“派工反馈 / 可用于派工和现场反馈”的卡片。后来短暂改成“现场记录 / 可以填写现场实际”，但继续复看页面后发现它还是多余。

这张卡片背后确实有业务含义：它表示当前查看的计划是否允许写入现场记录。但是页面下面已经有一段更完整的提示，摘要区再放一张卡会重复。另一个问题是“查看方案”和“计划身份”在当前正式采用方案下内容完全一样，也会让用户疑惑为什么要看两遍。

## 2. 修复

- 版本摘要卡只保留“版本、时间、排产方式、结果、查看方案”。
- 删除页面摘要里的“计划身份”卡，避免和“查看方案”重复。
- 删除页面摘要里的“派工反馈 / 现场记录”卡，避免把“能不能写反馈”塞进一张含义不清的卡片。
- 保留下面的护栏提示，用来解释为什么当前方案能写或不能写现场记录。
- Excel 摘要仍保留计划身份和现场记录说明，因为导出文件离开页面后需要自带上下文。
- 更新资源派工计划身份回归测试，锁住页面不再出现重复卡片，Excel 摘要仍保留必要说明。

## 3. 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py -q`：9 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_resource_dispatch_actual_import.py -q`：41 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/viewmodels/scheduler_resource_dispatch.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_resource_dispatch_site_records_frontend_contract.py`：通过。
- `.venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/issues/2026-05-31-resource-dispatch-feedback-status-card --require doc_type --require status`：通过。
- 浏览器验证：资源派工页版本摘要只保留“查看方案”，不再显示“计划身份”“现场记录”或“派工反馈”摘要卡，页面下方仍显示当前方案能否写现场记录的提示。截图：`/tmp/aps-resource-dispatch-status-card-smoke.png`。

## 4. 遗留

当前工作区在本轮开始前已经有较多未提交改动，所以本记录不声明 clean-worktree proof。
