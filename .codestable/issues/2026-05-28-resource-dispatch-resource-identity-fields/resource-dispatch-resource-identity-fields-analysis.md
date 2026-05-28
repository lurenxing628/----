---
doc_type: issue-analysis
issue: 2026-05-28-resource-dispatch-resource-identity-fields
status: confirmed
title: "资源排班资源身份字段根因下钻与修复计划"
date: 2026-05-28
recommended_plan: "后端统一资源身份字段，前端和导出按干净字段展示"
tags:
  - scheduler
  - resource-dispatch
  - execution-feedback
  - report
  - frontend
---

# 资源排班资源身份字段根因下钻与修复计划

## 历史资料检索

本轮开始前已读取 CodeStable 起步资料，并补查相关现状文档：

- `.codestable/attention.md`
- `.codestable/reference/system-overview.md`
- `.codestable/architecture/ARCHITECTURE.md`
- `.codestable/architecture/ui-gantt.md`
- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md`
- `.codestable/compound/2026-05-28-explore-shop-floor-feedback-usage.md`

结论：

- APS 仍要兼容 Win7 x64、Python 3.8、Chrome 109 和离线静态资源。
- 用户可见页面和导出不能暴露内部字段名、内部枚举或调试字段。
- 现场反馈记录的是现场实际事实，计划资源只用于对照。
- 计划和现场实际复盘里，实际资源必须来自执行事件或执行状态读模型，不能拿计划资源冒充。

## 根因

根因不是某一个页面样式写坏了，而是字段契约本身太粗：

- `data/repositories/operation_execution_event_repo.py` 读取执行事件状态时，只给上层传一个 `actual_machine_label` / `actual_operator_label`。
- `core/services/scheduler/operation_execution_feedback_actions.py` 给事件列表补资源名时，也只返回一个拼好的 label。
- `web/viewmodels/scheduler_resource_dispatch_execution.py` 构造现场反馈卡片和事件详情时，把计划资源、实际资源、影响资源都当成一个 label。
- `core/services/scheduler/resource_dispatch_rows.py`、`web/viewmodels/scheduler_resource_dispatch.py`、`static/js/resource_dispatch.js` 在任务明细、日历、甘特弹窗里继续沿用这个 label。
- `core/services/scheduler/resource_dispatch_excel.py` 和 `core/services/report/execution_review.py` 也直接消费这个 label，导致导出和复盘页面一起难读。

结果就是：编号、名称、用户主显示文本、完整身份文本混在一个字段里。前端如果再去拆字符串，会变成新的不稳定规则。

## 字段语义

本轮统一使用这套语义：

- `id`：资源编号，例如 `MC-01`。
- `name`：资源名称，例如 `一号设备`。
- `display_label`：用户主视图优先看的文本；有名称时优先显示名称，没有名称时显示编号。
- `identity_label`：完整身份文本；编号和名称都存在且不相同时显示 `编号 名称`。
- `label`：兼容旧调用，等同于 `identity_label`，避免旧链路突然丢信息。

特殊情况：

- 只有编号：`display_label`、`identity_label`、`label` 都是编号。
- 只有名称：`display_label`、`identity_label`、`label` 都是名称。
- 编号和名称相同：不重复显示，三个字段都是同一个文本。
- 外协供应商：用户可见文本为 `外协供应商：供应商名称`。
- 外协未分配：用户可见文本为 `外协未分配`。

## 方案选择

### 方案 A：只在前端拆字符串

做法：前端看到空格后切成两段。

问题：

- 编号和名称里都可能有空格或短横线，拆错后会更乱。
- Excel、报表、后端事件详情仍然不统一。

结论：不采用。

### 方案 B：只修现场反馈卡片

做法：只给卡片补字段，其他表格和导出先不动。

问题：

- 用户在同一个资源排班页会继续看到两套口径。
- Excel 和计划实际复盘仍会把长身份挤在一个单元格里。

结论：不采用。

### 方案 C：后端统一干净字段，前端和导出一起消费（采用）

做法：

- 新增统一资源身份模型。
- 执行状态读模型、事件列表、资源排班行、日历、甘特、Excel、计划和现场实际复盘一起消费这套字段。
- 旧 `label` 保留为完整身份，避免已有测试和兼容调用丢信息。

优点：

- 展示口径统一。
- 前端不需要猜字符串结构。
- 导出和报表能一起变清楚。

结论：采用。

## 实现边界

本轮预计只触碰资源身份展示链路：

- `.codestable/issues/2026-05-28-resource-dispatch-resource-identity-fields/`
- `core/models/resource_identity.py`
- `core/models/operation_execution_state.py`
- `data/repositories/operation_execution_event_repo.py`
- `data/repositories/operation_execution_state_builder.py`
- `core/services/scheduler/operation_execution_feedback_actions.py`
- `core/services/scheduler/resource_dispatch_execution_enrichment.py`
- `core/services/scheduler/resource_dispatch_rows.py`
- `web/viewmodels/scheduler_resource_dispatch.py`
- `web/viewmodels/scheduler_resource_dispatch_execution.py`
- `core/services/scheduler/resource_dispatch_excel.py`
- `core/services/report/execution_review.py`
- `core/services/report/exporters/xlsx.py`
- `templates/scheduler/resource_dispatch.html`
- `templates/reports/execution_review.html`
- `static/js/resource_dispatch.js`
- `static/css/ui_contract.css`
- 相关精准回归测试。

本轮不做：

- 不改排产算法。
- 不改现场反馈写入规则。
- 不改数据库 schema。
- 不升级依赖。
- 不引入外部静态资源。

## 验证计划

精准测试：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_resource_dispatch_viewmodel.py tests/test_scheduler_resource_dispatch_smoke.py tests/regression_scheduler_candidate_resource_dispatch_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_table_layout_readability_contract.py`

收口检查：

- CodeStable 文档 frontmatter 校验。
- Python 3.8 语法扫描。
- `git diff --check`。
- 浏览器打开资源排班页，确认现场反馈卡片、任务明细、日历和甘特弹窗都能清楚区分名称与完整身份。
