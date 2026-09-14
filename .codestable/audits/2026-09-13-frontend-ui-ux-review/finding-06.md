---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-06"
nature: usability
severity: P2
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 06：「选择排产方案」入口承载三态，候选态缺显式页签、侧栏高亮只看 view

## 速答

侧栏项「选择排产方案」（view=analysis）承载正式计划版本、某次排产的候选方案、排产记录列表三种内容。页内顶部一直有「计划版本 / 排产记录」两个带 pressed 态的页签，所以三态并非不可见；真实缺口是候选态只有一个徽章没有 pressed 页签，且侧栏高亮只按 view 不按 context，排产记录态下标题变成「排产记录」而侧栏仍高亮「选择排产方案」。

## 关键证据

- 三态分发：`frontend/workbench/app/SchedulingWorkspace.jsx:57-58,73-76` — 有 run_ref / candidate_ref 走 RunCandidateWorkspace，`context.source === 'run_history'` 走 RunHistoryWorkspace，否则 PlanWorkspace。
- 页内页签一直存在：`SchedulingWorkspace.jsx:69-72` 的 `.scheduling-navigation` 在三态全部渲染「计划版本」（`aria-pressed={!candidate && !history}`）与「排产记录」（`aria-pressed={history}`）；候选态只有 `:72` 的「候选方案 · 不是正式计划」徽章。
- 排产记录态：`main.jsx:45` `showPlanTabs` 为 false，计划 tab 条整块不渲染；`WorkbenchNavigation.js:42-49` `historyView` 时页头标题为「排产记录」（词表裁决第 56 行的统一叫法）。
- 侧栏高亮：`main.jsx:43` `active` 只看 view，三态下都停在「选择排产方案」（`web/routes/workbench/navigation_metadata.py:5`）。
- 这一「入口 + 页内页签」结构是路线图 `wbui-view-tabs-merge`（done）的既定产物，侧栏减到 12 项是该条已批准目标。

## 影响

候选态下用户只能靠徽章知道自己不在正式计划里；排产记录态下标题与侧栏高亮不一致。三个信号里两个是一致的，位置感有损但不至于迷路。

## 修复方向

在 `.scheduling-navigation` 补第三个 pressed 页签「候选方案」，让三态显式可切换；侧栏高亮可按 context 加二级提示。不新增侧栏项，不改 12 项目标。

## 建议动作

`cs-issue`，局部改造 SchedulingWorkspace 的导航条。

## 复核记录（2026-09-13）

- 原「三态间进入/退出全靠页内按钮，无稳定二级导航」不成立，撤销；原修复方向①「排产记录升为侧栏第 4 项」与 `wbui-view-tabs-merge` 冲突，撤销。
- 原标题「计划中心一名三态」中「计划中心」不是任何侧栏项或页面标题，改为「选择排产方案」。
- 原「刷新后入口路径无法复现」过强：`WorkbenchNavigation.js:92-119` 把 context 落进 history.state，reload 可保持；不可复现的只是「把 URL 分享给别人」。
- 由 P1 降为 P2；JSX 坐标改为源码。

## 实施记录（2026-09-13）

- 状态：resolved。`SchedulingWorkspace.jsx` 有候选时渲染 `aria-pressed` 的「候选方案」页签与「不是正式计划」说明。
- 详见 [remediation-record.md](remediation-record.md)。
