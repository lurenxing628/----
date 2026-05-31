---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-workbench-design-gap
finding_id: "design-gap-02"
classification: CONFLICT_OR_RISK
nature: arch-drift
severity: P0
confidence: high
status: open
suggested_action: cs-feat-design
---

# Finding 02：跨页上下文参数没有统一合同

## 结论

目标页面路由大多已经存在，但“从哪里跳到哪里时带什么参数”还没有统一合同。现在各页面手写链接，日期、资源、方案身份的参数名不一致，容易出现“点过去了，但版本/日期/资源丢了”。

## 证据

- 设计稿要求首页、分析、甘特、资源派工、报表之间保留 `version`、`plan_role`、`scenario_id`、日期、批次、资源对象。
- roadmap 已经规划 `WorkbenchPlanContext` / `WorkbenchLink`，但 items 仍是 planned。
- 当前首页常用入口多为裸 `url_for`：`templates/dashboard.html:60`。
- 报表中心卡片也是裸链接：`templates/reports/index.html:36`、`:40`、`:44`、`:48`。
- 资源派工解析 `start_date/end_date`：`web/routes/domains/scheduler/scheduler_resource_dispatch_query.py:11`、`:53`；计划和现场实际解析 `date_from/date_to`：`web/routes/reports.py:329`。
- 设计稿写 `resource_id`，但资源派工实际用 `scope_type/scope_id/operator_id/machine_id/team_id`。
- 甘特前端识别 `gantt_batch/gantt_resource/gantt_overdue`：`static/js/gantt_ui.js:128`，和设计稿里的 `batch_id/resource_id/view` 需要翻译。
- `scheduler_nav` 读取了 `scenario_id`，但分析页入口使用的上下文没有带它：`templates/components/ui_macros.html:327`、`:342`、`:353`。

## 影响

工作台最怕的不是少一个按钮，而是用户点来点去以后上下文丢了。比如从候选方案跳到甘特，可能掉回默认方案；从报表跳资源派工，可能日期或资源没带上；从资源派工跳计划和现场实际，可能没有明确说明为什么非正式方案不可复盘。

## 建议

- 新增统一链接生成器，例如 `web/viewmodels/scheduler_workbench_links.py`。
- 明确三组翻译：`date_from/date_to` 对 `start_date/end_date`，`resource_id` 对 `operator_id/machine_id/team_id`，`resource_type` 对 `scope_type`。
- `required_params` 必须按页面设计稿第 3.4 节逐路线矩阵写进 feature design；资源派工和报表类跳转要覆盖 `query_date`、`period_preset`、`scope_type`，不能只测 `version/date_from/date_to`。
- `plan_role`、`guardrail_reason_type`、`resource_type/scope_type`、`period_preset`、`view` 要有内部值到中文展示值映射。
- 所有首页、分析、甘特、资源派工、报表链接都消费同一个 `WorkbenchLink`。
- 新增 `tests/regression_scheduler_workbench_links_contract.py` 覆盖设计稿第 15.4 的主流程。
