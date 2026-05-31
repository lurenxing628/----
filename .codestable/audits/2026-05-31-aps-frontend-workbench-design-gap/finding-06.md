---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-workbench-design-gap
finding_id: "design-gap-06"
classification: CONFLICT_OR_RISK
nature: maintainability
severity: P1
confidence: high
status: open
suggested_action: cs-feat-design
---

# Finding 06：资源派工现场事实车道与当前页面/测试不一致

## 结论

资源派工页功能很多，但现在仍是一个超级页面。设计稿要求拆成“计划员查看”和“现场事实”两个可测试车道；当前页面只是一个 tab 条，现场记录又混着反馈人、Excel、任务卡和大表单。

## 证据

- 当前 tab 混放任务明细、现场记录、日历矩阵、甘特图：`templates/scheduler/resource_dispatch.html:231`。
- JS 只按一个 tab 状态切换，没有车道概念：`static/js/resource_dispatch_core.js:271`。
- 现场记录面板一开始就展示反馈人和 Excel 控件：`templates/scheduler/resource_dispatch.html:282-313`。
- 当前任务卡动作是“填写实际情况 / 查看计划和实际”，不是设计稿的开工、完工、查看记录：`static/js/resource_execution.js:40`。
- 当前内联表单有暂停、异常、数量等字段：`static/js/resource_execution.js:260-309`。
- 后端路由仍有 start、finish、pause、resume、report-exception：`web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:237`。
- 任务卡缺图号和开工/完工偏差字段：`static/js/resource_execution.js:170`、`web/viewmodels/scheduler_resource_dispatch_execution.py:198`。
- 执行事件模型有 `created_at`，但 viewmodel 没传给前端：`core/models/operation_execution_event.py:52`、`web/viewmodels/scheduler_resource_dispatch_execution.py:327`。

## 当前能直接做

- 模板上分出“计划员查看”和“现场事实”两个分组。
- 现场记录 tab 放到“现场事实”分组里。
- Excel 批量维护默认收起。
- 给两个分组加稳定文案，方便测试断言。

## 必须拍板的冲突

- 第一版到底保留“填写实际情况”大表单，还是按设计稿拆成“开工 / 完工 / 查看记录”。
- 暂停、继续、报异常是否从第一版入口里收掉。
- 反馈人短期已确认不必填，因为当前是计划员单人操作，不做多人现场终端。

## 建议

这条不要直接边改边猜。先写一个小 design，明确首版动作白名单、字段白名单、Excel 折叠规则，然后再改模板和测试。反馈人保持可空，不作为短期验收项。
