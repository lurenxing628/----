---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-workbench-design-gap
finding_id: "design-gap-01"
classification: CONFLICT_OR_RISK
nature: arch-drift
severity: P1
confidence: high
status: open
suggested_action: cs-feat-design
---

# Finding 01：现场记录短期不做反馈人必填和 Excel 预览，保留非正式方案入口风险

## 结论

现场记录这块不是简单改布局。后端已经有“只有当前正式采用方案能写”的主护栏。用户已确认短期内系统仍是计划员一个人操作，其他人把现场情况汇报给计划员，所以“反馈人必填”和“Excel 预览确认”短期不做，不再作为阻塞项。

剩下需要保留的风险是：非正式方案下，前端是否还应该下发可用的 Excel 写入 URL，以及页面是否要给计划员更清楚的不可写提示。

## 证据

- 设计稿要求非正式方案下，手填、Excel 模板、Excel 导入、导入预览和页面 `data-*` 写入 URL 都不可用。
- 当前写入服务会拒绝非当前正式方案：`core/services/scheduler/resource_dispatch_actual_record_service.py:129-142`。
- 当前资源派工路由只按 `has_history and can_query` 下发 Excel 模板/导入 URL：`web/routes/domains/scheduler/scheduler_resource_dispatch.py:77-89`。
- 当前模板把这些 URL 写入页面 `data-*`：`templates/scheduler/resource_dispatch.html:20-29`、`:291-305`。
- 用户已明确反馈人短期不必填；当前 placeholder 是“可不填”：`templates/scheduler/resource_dispatch.html:282-287`。
- 当前服务会把空反馈人落成“未填写反馈人”：`core/services/scheduler/resource_dispatch_actual_records.py:11-13`、`:106-107`。在计划员单人操作口径下，这不是短期问题。
- 用户已明确 Excel 预览短期不做；当前前端测试禁止 `data-actual-import-preview-url` / `data-actual-import-confirm-url`，这可以继续保留。

## 影响

如果用户在非正式方案里看到页面仍有导入入口，会以为可以导入；后端虽然会挡住，但页面体验和“只有正式采用方案能写现场事实”的规则不一致。反馈人必填和 Excel 预览不再算短期风险。

## 建议

- 继续保留反馈人可空，不做多人权限/反馈人模型。
- 继续保留 Excel 直接导入，不做预览/确认流程。
- 非正式方案下，建议前端不要下发导入 URL，或至少禁用入口并给中文原因。
- 写入护栏测试仍要覆盖按钮、手填、Excel、API 和页面 `data-*` URL。
