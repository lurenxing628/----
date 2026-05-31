---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-layout-gap
finding_id: "maintainability-06"
nature: maintainability
severity: P1
confidence: high
suggested_action: cs-roadmap
status: open
---

# Finding 06：资源派工超级页面里现场执行工作流不够清楚

## 速答

资源派工页已经有现场记录、任务卡、Excel 导入、日历矩阵和甘特图，但整体仍是“资源排班大页里塞执行能力”，不是给现场人员或计划员清晰分工的执行工作台。

## 关键证据

- `templates/scheduler/resource_dispatch.html:41-46` — 页面主标题仍是“资源排班”，不是现场执行或执行工作台。
- `templates/scheduler/resource_dispatch.html:55-66` — 第一块是查询条件，要求用户选择视角、资源、区间、版本、方案。
- `templates/scheduler/resource_dispatch.html:235-242` — 同一结果卡里并列放任务明细、现场记录、日历矩阵、甘特图。
- `templates/scheduler/resource_dispatch.html:286-317` — 现场记录页签里同时放反馈人、Excel 模板、导入文件、导入按钮和任务卡。
- `static/js/resource_execution.js:267-288` — “填写实际情况”内联表单一次性展示实际开工、实际完工、数量、暂停时间、暂停原因、异常记录、备注等字段。
- `.codestable/features/2026-05-29-resource-dispatch-execution-page-extraction/对抗评审结论与意见汇总.md:41-50` — 既有评审已确认资源排班是一个承载 6 大功能的超级页面。
- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md:1246-1262` — 三差距调研明确车间端应是任务卡、大按钮、少字段，计划员端才适合表格、筛选、异常汇总和跳转。

## 影响

对计划员来说，这页能看很多东西；对现场录入人员来说，路径偏绕，字段偏多。用户只是想补完工时间或报一个异常时，会被计划查询、甘特、日历和 Excel 导入流程包围。长期看，这会放大误填、漏填和培训成本。

## 修复方向

先不要直接拆页面。既有对抗评审已经判断“拆代码”比“拆页面”更稳。建议先在新工作台 roadmap 中确认用户角色和入口：计划员看排班/影响，现场人员看任务卡/实际情况，二者是否保持同页、分 tab、还是未来独立页，需要有真实验收标准。

## 建议动作

走 `cs-roadmap`，必要时接 `cs-refactor` 继续收敛前端文件边界。
