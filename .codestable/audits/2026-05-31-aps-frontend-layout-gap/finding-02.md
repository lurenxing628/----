---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-layout-gap
finding_id: "bug-02"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
resolved_by: 2026-05-31-resource-dispatch-view-records-action-contract
resolved_date: 2026-05-31
---

# Finding 02：“查看计划和实际”按钮没有完全按后端动作合同驱动

## 速答

现场记录卡片里的“填写实际情况”按钮读取了后端 `available_actions`，但“查看计划和实际”按钮只按 `op_id` 是否存在决定可用，和 roadmap 里“按钮能不能点必须由服务端返回”的口径不一致。

复核结论：这条问题已经由 fast-track issue `2026-05-31-resource-dispatch-view-records-action-contract` 修复，当前审计保留它作为历史发现和回归依据，不再作为 open bug 重复立项。

## 关键证据

- `static/js/resource_execution.js:20-29` — `fill_actual` 会从 `available_actions` 中查找动作并读取 `enabled / disabled_reason`，但 records 按钮只计算 `recordsDisabledAttr = opId ? "" : " disabled"`。
- `static/js/resource_execution.js:31-40` — “查看计划和实际”按钮没有读取 `available_actions` 里的 `view_records`。
- `.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md:1110` — 任务卡合同包含 `available_actions`。
- `.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md:1131` — 明确 `available_actions` 是前端画按钮的唯一数据源。
- `tests/regression_operation_execution_feedback_routes.py:47-52` — 回归测试已经断言后端返回 `fill_actual` 和 `view_records` 两个动作及其中文标签。
- `static/js/resource_execution.js:23-40` — 当前代码已经同时读取 `fill_actual` 和 `view_records`，并用 `viewAction.enabled / disabled_reason / label` 渲染“查看计划和实际”按钮。
- `tests/regression_resource_dispatch_site_records_frontend_contract.py:157-169` — 回归测试断言 `renderExecutionActions()` 必须读取 `view_records`，且不能回到只按 `op_id` 判断可用的旧写法。
- `.codestable/issues/2026-05-31-resource-dispatch-view-records-action-contract/resource-dispatch-view-records-action-contract-fix-note.md:1-8` — fix-note 标记 `status: done`，修复日期为 2026-05-31。

## 影响

目前“查看计划和实际”多半仍能正常用，但它绕过了后端动作合同。后续如果服务端因为计划身份、权限、状态或数据异常禁用 `view_records`，前端仍可能让用户点，造成页面行为和后端规则不一致。

## 修复方向

让 `renderExecutionActions()` 同时读取 `fill_actual` 和 `view_records` 两个动作；按钮可用、禁用原因、标题提示都从 `available_actions` 来。

## 建议动作

已走 `cs-issue` fast-track 并完成修复；后续只需要保留回归测试，不要重复开同名修复任务。
