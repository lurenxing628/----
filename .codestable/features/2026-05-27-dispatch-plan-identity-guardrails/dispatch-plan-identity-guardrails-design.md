---
doc_type: feature-design
feature: 2026-05-27-dispatch-plan-identity-guardrails
status: approved
roadmap: aps-three-gap-directions
roadmap_item: dispatch-plan-identity-guardrails
created: 2026-05-27
retrospective_backfill: true
---

# 资源派工计划身份护栏设计

## 背景

资源派工页可以查看正式采用方案、历史正式方案、对比参考方案和模拟预览。用户必须知道当前看到的是哪套计划，并且只有当前最新正式采用方案能进入派工和现场反馈。

这份设计是回溯补档，用来补齐 CodeStable 事实源。它记录的边界和后续 checklist、acceptance 保持一致。

## 目标

- 页面和导出用中文说明当前计划身份。
- 当前最新正式采用方案显示可以用于派工和现场反馈。
- 历史正式方案、对比参考方案、模拟预览都只能查看，不能写现场事实。
- 普通 `/resource-dispatch/data` 和 Excel 不泄露 `source_table / candidate_id / scenario_id` 等内部字段。

## 不做

- 不新增确认派工写入。
- 不新增确认派工表或确认派工 route。
- 不开放开工、完工、暂停、继续生产或报异常。
- 不改 schema、算法、安装包或第三方资源。

## 实现范围

- `core/services/scheduler/resource_dispatch_service.py`：把公共 PlanIdentity 转成资源派工上下文。
- `web/viewmodels/scheduler_resource_dispatch.py`：整理用户可见计划身份和护栏提示。
- `core/services/scheduler/resource_dispatch_excel.py`：导出查询摘要增加中文身份说明。
- `templates/scheduler/resource_dispatch.html`：页面摘要显示计划身份和派工反馈说明。
- `tests/regression_scheduler_dispatch_plan_identity_guardrails.py`、`tests/regression_scheduler_candidate_resource_dispatch_contract.py`：覆盖身份展示、导出脱敏和只读副作用。

## 验收口径

- 只有当前最新正式 adopted 方案 `can_dispatch/can_write_feedback=true`。
- 候选、模拟、历史正式方案均不能写现场反馈。
- 页面和导出只有中文说明，不直接显示内部字段。
- 没有确认派工副作用。
