---
doc_type: audit-finding
audit: 2026-06-14-subagent-reference-trace-verification
finding_id: "bug-09"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 09：超期清单日期参数传播但查询不生效

## 速答

超期清单链接、隐藏字段和导出 URL 会传播日期参数，但 `overdue_batches()` 没有日期形参，实际查询不按用户选择日期过滤。

## 关键证据

- `web/routes/reports_page_support.py:195-197`：超期页上下文读取 `start_date/date_from`、`end_date/date_to`。
- `web/viewmodels/scheduler_workbench_link_specs.py:100-105`：`overdue_report` 配置为 `date_style=date_from_to`。
- `web/viewmodels/scheduler_workbench_link_query.py:199-207`：按规格把日期追加到目标链接。
- `web/routes/reports_export_support.py:16-31`：导出链接也会保留 `date_from/date_to/start_date/end_date/query_date`。
- `web/routes/reports_page_support.py:183-190`：实际调用 `engine.overdue_batches()` 时只传版本、方案、资源、批次。
- `core/services/report/report_engine.py:157-165`：`overdue_batches()` 函数签名没有日期。
- `data/repositories/schedule_plan_query_repo.py:422-424`：SQL 只要求有交期并按批次/资源过滤，没有日期范围条件。

## 影响

用户可能以为当前超期清单被某段日期约束了，实际看到的是当前版本/方案下的全部超期。导出也同样保留了空转日期参数。

## 修复方向

二选一：要么超期清单明确不接受日期，链接规格和表单不再传播日期；要么给超期定义一个明确日期口径并下推查询。

## 建议动作

`cs-issue`，因为这是用户筛选语义和实际查询不一致。

