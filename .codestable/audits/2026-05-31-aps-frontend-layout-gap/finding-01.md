---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-layout-gap
finding_id: "bug-01"
nature: bug
severity: P0
confidence: high
suggested_action: cs-issue
status: resolved
resolved_by: 2026-05-31-resource-dispatch-execution-save-refresh
resolved_date: 2026-05-31
---

# Finding 01：现场记录手填成功后明细和甘特仍显示旧状态

## 速答

资源派工页手动填写实际情况后，只刷新“现场记录”任务卡，不同步刷新任务明细表和页内甘特图；用户可能刚保存了开工、完工或异常，却在同页其它视图继续看到旧的现场状态。

复核结论：这条问题已经由 fast-track issue `2026-05-31-resource-dispatch-execution-save-refresh` 修复，当前审计保留它作为历史发现和回归依据，不再作为 open bug 重复立项。

## 关键证据

- `static/js/resource_execution.js:396-414` — `replaceExecutionTask()` 只更新 `state.execution.tasks` 并调用 `renderExecutionCards(state.execution)`，没有调用资源排班主数据刷新。
- `static/js/resource_execution.js:416-442` — 手填保存成功后调用 `replaceExecutionTask(responsePayload.data && responsePayload.data.task_card)`，随后清理内联表单并提示已保存。
- `static/js/resource_dispatch_core.js:117-120` — 任务明细表显示 `execution_status_label`、最近异常和影响资源，这些内容依赖 `state.data.detail_rows`。
- `static/js/resource_dispatch_core.js:421-424` — 只有 `loadData()` 路径会在甘特 tab 重新渲染甘特并重新加载现场记录数据。
- `static/js/resource_execution.js:456-458` — 当前代码已经在 `replaceExecutionTask(responsePayload.data && responsePayload.data.task_card)` 后调用 `loadData()`，修复手填成功后的主表和甘特刷新。
- `tests/regression_resource_dispatch_site_records_frontend_contract.py:172-178` — 回归测试断言手填成功路径里 `replaceExecutionTask()` 之后必须调用 `loadData()`。
- `.codestable/issues/2026-05-31-resource-dispatch-execution-save-refresh/resource-dispatch-execution-save-refresh-fix-note.md:1-8` — fix-note 标记 `status: done`，修复日期为 2026-05-31。

## 影响

这不是单纯美观问题。用户保存现场实际后，如果切回“任务明细”或“甘特图”，仍可能看到旧现场状态、旧异常摘要或旧影响资源。现场记录本来是当前项目补 APS/MES 闭环的重要能力；同页视图不同步，会让用户怀疑到底有没有保存成功。

## 修复方向

把手填保存成功后的刷新路径和 Excel 导入成功后的刷新路径拉齐：成功写入后至少刷新资源排班数据，或定点更新 `state.data.detail_rows` / 甘特任务 / 当前任务卡，保证四个视图看到同一份现场状态。

## 建议动作

已走 `cs-issue` fast-track 并完成修复；后续只需要保留回归测试，不要重复开同名修复任务。
