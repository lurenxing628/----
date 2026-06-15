---
doc_type: audit-finding
audit: 2026-06-14-subagent-reference-trace-verification
finding_id: "performance-04"
nature: performance
severity: P2
confidence: medium
suggested_action: cs-issue
status: open
---

# Finding 04：计划和现场实际导出无日期时全量装配当前版本

## 速答

`/reports/execution-review/export` 不带日期时会把“没填日期”解释成“全部日期”，读取当前版本 adopted/Schedule 的全部计划行，再逐行装配现场状态。

## 关键证据

- `core/services/report/execution_review.py:124-134`：空日期返回 `start_time=None/end_time=None/date_range_label=全部日期`。
- `core/services/report/execution_review.py:173-182`：无日期分支调用 `_list_plan_rows_all()`。
- `core/services/report/execution_review.py:219`：结果被 `list(plan_rows or [])` 后逐行装配。
- `web/routes/reports_export_routes.py:95-112`：导出路由直接把空 `date_from/date_to` 传给 `export_execution_review_xlsx()`。
- 子代理限定：普通页面通常会通过页面上下文补日期范围，主要可达入口是导出路由。

## 影响

影响取决于单个排产版本的 `Schedule` 行数。行数大时，导出大小检查发生在全量取数和现场状态装配之后，只能挡最终 Excel，挡不住前面的内存和计算开销。

## 修复方向

导出入口和页面入口统一日期策略：不带日期时补版本范围或要求显式确认；如果保留“全部日期”，也应有查询上限或流式分批。

## 建议动作

`cs-issue`，因为这是导出入口的边界条件问题。

