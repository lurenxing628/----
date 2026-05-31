---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-layout-gap
finding_id: "maintainability-04"
nature: maintainability
severity: P1
confidence: high
suggested_action: cs-roadmap
status: open
---

# Finding 04：首页缺少“今日待处理”动态工作台

## 速答

当前首页有统计卡和常用工作区，但更像入口页，不像计划员每天打开先处理风险的工作台。

## 关键证据

- `templates/dashboard.html:4-21` — 首页首屏是待排批次、已排批次、超期批次、最近排产版本四张统计卡。
- `templates/dashboard.html:54-86` — “常用工作区”按排产作业、基础资料、分析复盘分组，主要是静态入口按钮。
- `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md:159-189` — 调研指出成熟 APS 首页应直接回答今天有哪些问题、哪些会晚、哪些资源排满、下一步处理什么。
- `docs/aps_frontend_workbench_mockup.html:1722-1769` — mockup 给出了“今日待处理”风险列表示例，但真实 `dashboard.html` 没有对应动态区域。

## 影响

用户能看到数字，但不能从首页直接知道“现在最该点哪里”。超期、方案待确认、资源过载、停机影响、现场异常这些风险仍散在分析页、报表页、资源派工页里。

## 修复方向

在新工作台 roadmap 里把首页改造成风险入口：四张统计卡保留，但补“今日待处理”列表，把超期、方案待确认、高负荷资源、现场异常和基础资料缺口按优先级拉出来。

## 建议动作

走 `cs-roadmap` 或后续 `cs-feat-design`，因为这会改变首页信息组织和入口优先级。
