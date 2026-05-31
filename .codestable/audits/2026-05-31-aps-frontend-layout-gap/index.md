---
doc_type: audit-index
audit: 2026-05-31-aps-frontend-layout-gap
scope: 当前 APS 前端布局、工作台串联、甘特/资源派工/报表/方案对比/延期解释页面组织
created: 2026-05-31
status: active
total_findings: 9
open_findings: 7
resolved_findings: 2
---

# APS 前端布局对抗审计

## 范围

本轮只审查当前项目前端布局和工作流组织，不改业务代码。重点读取：

- `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md`
- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md`
- `.codestable/roadmap/aps-three-gap-directions/`
- `docs/aps_frontend_workbench_mockup.html`
- `templates/base.html`、`templates/dashboard.html`、`templates/scheduler/gantt.html`、`templates/scheduler/resource_dispatch.html`
- `templates/scheduler/analysis_parts/`、`templates/reports/`
- `static/js/resource_dispatch_core.js`、`static/js/resource_execution.js`
- 前端布局合同、说明蓝本和相关回归测试

## 协作记录

- Codex 本轮启动 6 个 SubAgent，覆盖调研文档、三差距路线图、工作台路线图、当前页面结构、布局测试和现有审计复核。
- Claude Code 使用 fresh delegate 会话做两轮对抗讨论。Round 1 启动 3 个 Claude 子代理；Claude 报告传入 `model: "opus"`，覆盖模板布局、前端 JS 闭环、布局契约/蓝图。Round 2 未再启动新子代理，只做定点反驳复核。
- 本轮没有修改前端实现，也没有回退工作区已有改动。
- 按“零阻塞复审”口径，本轮不是完成态：已发现需要修复/立项的问题，但用户尚未确认是否进入修复或新 roadmap，因此状态应视为 `blocked_not_complete`，不能说“当前布局无阻塞”。

## 总评

当前项目不是“没有 APS 前端地基”。方案对比推荐卡、延期解释、现场记录任务卡、资源派工、甘特、报表和说明文档都已经有不少扎实实现。真正的问题是：三差距 roadmap 主要承接了“多方案对比、延期诊断、车间反馈”三条数据闭环；同日新增的 `aps-frontend-workbench` roadmap 已经承接“成熟 APS 工作台怎么把这些页面串起来”的横向布局骨架，但 8 个条目仍是 `planned` / `feature: null`，真实页面还没落地。

大白话说，就是纵向功能做了不少，但横向还不像计划员每天打开就能顺着做事的工作台。用户仍然需要在首页、甘特、分析、报表、资源派工之间来回跳，自己把“哪里晚、为什么晚、资源哪里满、哪个方案更合适、现场出了什么事”拼起来。

本轮复核发现两个更具体的前端闭环问题曾经存在：现场记录手填成功后只刷新任务卡，不同步刷新任务明细和资源派工甘特；“查看计划和实际”按钮没有完全按后端 `available_actions` 驱动。它们已经在当前工作区通过两个 fast-track issue 修复并有回归测试锁住，审计里保留为历史发现，但不应继续作为 open bug 重复立项。

## 发现清单

| # | 性质 | 严重度 | 状态 | 置信度 | 标题 | 文件 |
|---|---|---|---|---|---|---|
| 1 | bug | P0 | resolved | high | 现场记录手填成功后，任务明细和资源派工甘特仍显示旧现场状态 | [finding-01.md](finding-01.md) |
| 2 | bug | P1 | resolved | high | “查看计划和实际”按钮没有完全按后端 `available_actions` 驱动 | [finding-02.md](finding-02.md) |
| 3 | arch-drift | P1 | open | high | 工作台 roadmap 已承接横向骨架，但页面仍未落地 | [finding-03.md](finding-03.md) |
| 4 | maintainability | P1 | open | high | 首页仍偏统计和入口宫格，缺少“今日待处理”动态工作台 | [finding-04.md](finding-04.md) |
| 5 | maintainability | P1 | open | high | 甘特页仍偏只读查看，缺少任务详情抽屉和资源负荷摘要 | [finding-05.md](finding-05.md) |
| 6 | maintainability | P1 | open | high | 资源派工仍是超级页面，现场执行动作没有独立成清晰工作流 | [finding-06.md](finding-06.md) |
| 7 | arch-drift | P2 | open | medium | 现有布局测试能防可读性倒退，但不能证明成熟 APS 主流程完整 | [finding-07.md](finding-07.md) |
| 8 | maintainability | P1 | open | high | 顶层导航缺核心作业入口，工作台动线断在最外层 | [finding-08.md](finding-08.md) |
| 9 | maintainability | P2 | open | high | 报表中心缺少回跳入口，资源过载无法一键定位到甘特或派工 | [finding-09.md](finding-09.md) |

## 按维度分布

本表只统计当前仍 open 的布局缺口；Finding 01/02 已修复，保留在发现清单里作为历史和回归依据。

| 性质 | P0 | P1 | P2 | 合计 |
|---|---:|---:|---:|---:|
| bug | 0 | 0 | 0 | 0 |
| security | 0 | 0 | 0 | 0 |
| performance | 0 | 0 | 0 | 0 |
| maintainability | 0 | 4 | 1 | 5 |
| arch-drift | 0 | 1 | 1 | 2 |
| **合计** | **0** | **5** | **2** | **7** |

## 下一步建议

- **不要重复修已修问题**：Finding 01 和 Finding 02 已由 `resource-dispatch-execution-save-refresh`、`resource-dispatch-view-records-action-contract` 两个 fast-track issue 修复，本审计不再建议重复开 `cs-issue`。
- **先落最小工作台**：Finding 03-06、08 建议继续按 `aps-frontend-workbench` roadmap 推进。第一锤建议是 `dashboard-workbench-risk-todos`，用保守 viewmodel 把首页变成“今天先处理什么”的值班台；顶层导航缺口要作为后续导航/上下文设计输入，不要被跨页上下文协议吞掉。
- **打通报表回路**：Finding 09 可以排在工作台主线后补，重点是让资源负荷、计划实际、超期清单这些报表不再是死胡同，至少能带版本和日期跳回甘特或资源派工。
- **补保护网**：Finding 07 不建议直接删测试。现有测试仍然能防表格撑破、按钮丢失、说明误导；后续大布局重构时，应新增“工作台流程可断言”的测试，并把首页、甘特、分析、资源派工纳入浏览器几何覆盖。
