---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-workbench-design-gap
finding_id: "design-gap-03"
classification: NEEDS_FEATURE
nature: maintainability
severity: P1
confidence: high
status: open
suggested_action: cs-feat-design
---

# Finding 03：首页工作台需要新聚合层

## 结论

首页现在是统计卡和常用入口，不是计划员值班台。只改模板可以换骨架，但“今日待处理”“资源高负荷”“现场情况待确认”“方案待确认”需要新增首页聚合规则。

## 证据

- 当前首页首屏是待排、已排、超期、最近排产版本四张卡：`templates/dashboard.html:4-21`。
- 当前“常用工作区”是静态入口：`templates/dashboard.html:54-86`。
- 首页路由只算待排、已排、超期、最近版本：`web/routes/dashboard.py:18`、`:35`、`:46`。
- 最近历史和 summary 已有版本、范围、计数、超期等基础数据：`core/services/scheduler/summary/schedule_summary_assembly.py:435`。
- 资源负荷报表服务存在：`core/services/report/report_engine.py:226`。
- 计划和现场实际服务能看到现场状态，但首页没有统一“现场情况待确认”统计：`core/services/report/execution_review.py:94`、`:241`。

## 当前能直接做

- 改首屏布局：标题、上下文条、风险卡、左右两栏、交接摘要。
- 基础卡片先用已有待排、已排、超期、最近版本数据。
- 最近排产从“指标卡”改成“交接摘要”，先复用 `latest_summary` 和已有候选方案 helper。

## 必须新增的功能

- `dashboard_workbench` 聚合层。
- 今日待处理 Top6：类型、标题、影响、证据、动作、处理状态。
- 资源高负荷阈值和排序规则。
- 现场情况待确认统计。
- 工作台链接生成，保证点出去不丢版本和日期。

## 建议

首页优先做，因为它决定用户每天从哪里开始。第一版可以不落库，明确写成“实时生成的工作台摘要”。
