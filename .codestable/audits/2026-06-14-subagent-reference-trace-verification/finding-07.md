---
doc_type: audit-finding
audit: 2026-06-14-subagent-reference-trace-verification
finding_id: "bug-07"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 07：报表坏时间静默跳过导致指标偏小

## 速答

利用率和停机影响报表遇到坏 `start_time/end_time` 会直接 `continue`，指标变小但页面/导出没有提示坏行被跳过。

## 关键证据

- `core/services/report/utilization.py:20-22`：`_row_hours_in_window()` 返回 `None` 时直接跳过。
- `core/services/report/utilization.py:34-37`：开始/结束时间解析失败返回 `None`。
- `core/services/report/downtime_impact.py:57-60`：排产行坏时间直接跳过。
- `core/services/report/downtime_impact.py:39-42`：停机行本身坏时间也会被跳过。
- `core/services/report/report_engine.py:306-321`、`:421`：报表返回值没有 `degradation_events/degradation_counters`。
- `core/services/scheduler/_sched_display_utils.py:84-97`：scheduler 侧已有 `record_bad_time_row()` 对照。
- `core/services/scheduler/resource_dispatch_rows.py:123-130`：资源派工遇到坏时间会记录降级事件。

## 影响

利用率的小时数、任务数、利用率可能偏小；停机影响的重叠小时数、重叠次数可能偏小。用户看到的是正常数字，不知道有数据被过滤。

## 修复方向

把报表计算改成能区分“正常不计”和“坏数据跳过”，并返回 bad-time counter/sample 给页面和导出摘要。

## 建议动作

`cs-issue`，因为这是数据正确性和用户提示问题。

