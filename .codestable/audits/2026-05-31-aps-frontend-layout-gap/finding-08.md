---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-layout-gap
finding_id: "maintainability-08"
nature: maintainability
severity: P1
confidence: high
suggested_action: cs-roadmap
status: open
---

# Finding 08：顶层导航缺核心作业入口，工作台动线断在最外层

## 速答

当前全局导航只有“首页、排产、工艺、人员、设备、物料、报表、系统”这类大类入口，甘特图、排产优化分析、资源排班、周计划这些计划员每天会反复看的作业页没有成为一跳可达的核心入口。

## 关键证据

- `templates/base.html:56-63` — 顶层导航只有 8 个大类入口，没有甘特图、排产优化分析、资源排班或周计划。
- `templates/scheduler/analysis.html:10-15` — 排产优化分析页只能在进入排产相关页面后通过 `scheduler_nav('analysis')` 这类二级导航进入。
- `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md:159-189` — 调研明确成熟 APS 首页和导航应直接回答“今天有哪些问题、下一步要处理什么”。
- `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-roadmap.md:96-107` — 工作台概设已经把首页值班台、上下文协议、甘特工作台、分析行动层和资源派工执行层拆成一条路线。

## 影响

用户每天要看的核心页面藏在二级入口里，最直接的后果不是“找不到”，而是每次都要多绕几步。对计划员来说，这种小摩擦会每天重复发生：先点排产，再找甘特、分析、资源派工，最后还要自己记住当前版本和方案。

## 修复方向

不要急着把顶层导航塞满。建议作为 `aps-frontend-workbench` 的导航输入处理：先确定首页值班台和跨页上下文，再决定是否新增“计划工作台”一级入口、是否把甘特/分析/资源派工收成二级作业菜单，以及如何避免普通用户看到内部字段。

## 建议动作

走 `cs-roadmap` 下的工作台路线。它不是 `workbench-context-link-contract` 的子集；上下文合同解决“跳过去别丢版本”，本发现解决“核心作业页能不能快速进入”。
