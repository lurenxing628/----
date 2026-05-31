---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-layout-gap
finding_id: "arch-drift-03"
nature: arch-drift
severity: P1
confidence: high
suggested_action: cs-roadmap
status: open
---

# Finding 03：工作台 roadmap 已承接横向骨架，但页面仍未落地

## 速答

用户点名的两份调研都指向成熟 APS/MES 的“工作台化布局”。三差距 roadmap 只承接了多方案对比、延期诊断、车间反馈三条数据闭环；同日新增的 `aps-frontend-workbench` roadmap 已经把“首页待处理、甘特详情抽屉、资源负荷贴近甘特、跨页联动”列成路线，但 8 个条目仍是 `planned` / `feature: null`，真实页面还没有落地。

## 关键证据

- `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md:19-24` — 文档已标记 `superseded`，后续实现以三差距 roadmap 为准。
- `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md:52-62` — 调研明确成熟 APS 前端是工作台，重点是甘特、表格、资源负荷、异常、方案对比和车间反馈的组织。
- `.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md:33-39` — roadmap 自己声明只覆盖多方案对比、延期原因诊断、车间反馈三个局部方向。
- `.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md:45-54` — roadmap 范围主要是计划身份、延期解释、方案对比、派工护栏、执行事件、车间反馈和重排事实。
- `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-roadmap.md:27-39` — 新 roadmap 明确承接前端布局调研，目标是把“一堆页面”变成“一条做事路线”。
- `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-items.yaml:5-260` — 8 个工作台条目均已拆出，但当前仍为 `status: planned`、`feature: null`，说明还没有进入单个 feature 实施。
- `docs/aps_frontend_workbench_mockup.html:1585-1586` — mockup 明确提出把首页、甘特、方案对比、延期说明、车间反馈和报表中心做成连贯工作台，但它只是示例，不是真实页面入口。

## 影响

现在功能是在各自页面上纵向增强，横向路线虽已进入 roadmap，但还没有变成真实页面。继续只做局部功能，会让每个局部都越来越完整，但用户仍然要靠自己在多个页面之间拼流程。

## 修复方向

先不要直接改模板大翻修。建议按已存在的 `aps-frontend-workbench` roadmap 推进，第一步从 `dashboard-workbench-risk-todos` 这种最小闭环开始，用保守 viewmodel 做首页值班台，再逐步落跨页上下文、甘特详情区、资源负荷摘要和资源派工执行分层。

## 建议动作

继续走 `cs-roadmap` 下拆出的子 feature；具体实现前再进入 `cs-feat-design`。
