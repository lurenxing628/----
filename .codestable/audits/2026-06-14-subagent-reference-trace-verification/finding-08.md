---
doc_type: audit-finding
audit: 2026-06-14-subagent-reference-trace-verification
finding_id: "bug-08"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 08：批次详情 op_count 与 span 口径不一致

## 速答

批次详情“已排 N 道”按全量排程行计算，但“时间跨度”只按能解析的开始/结束时间计算，坏时间行会被静默排除。

## 关键证据

- `web/routes/domains/scheduler/scheduler_batch_detail.py:280-286`：按最新 adopted 方案和 `batch_id` 取本批次全量排程明细。
- `web/routes/domains/scheduler/scheduler_batch_detail.py:307`：调用 `_placement_span(rows)`。
- `web/routes/domains/scheduler/scheduler_batch_detail.py:250-257`：`_placement_span()` 只把可解析的 start/end 放入候选。
- `web/routes/domains/scheduler/scheduler_batch_detail.py:258-263`：只要至少有一个 start 和 end 可解析，就给出正常 span。
- `web/routes/domains/scheduler/scheduler_batch_detail.py:312`：`op_count=len(rows)`，不排除坏时间行。
- 子代理补充：现有 `tests/schedule/route_view/test_batch_schedule_placement_helpers.py:110` 已钉住“混合坏时间继续给 span”的行为。

## 影响

页面可能同时显示“已排 N 道”和一个看似完整的时间跨度，但这个跨度只覆盖可解析子集；如果最早开始那行时间坏了，甘特定位链接的左边界可能偏晚。

## 修复方向

给 `_placement_span()` 返回坏时间计数/是否部分计算，并在视图模型或模板中明示“时间跨度只按可解析行计算”。

## 建议动作

`cs-issue`，因为这是页面正确性和用户理解问题。
