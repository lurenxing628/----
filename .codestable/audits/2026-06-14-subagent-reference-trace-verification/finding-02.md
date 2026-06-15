---
doc_type: audit-finding
audit: 2026-06-14-subagent-reference-trace-verification
finding_id: "performance-02"
nature: performance
severity: P1
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 02：甘特自定义日期跨度缺后端上限

## 速答

`/scheduler/gantt/data` 接收 `start_date/end_date` 后进入 `gantt_range.py`，只校验日期格式和先后顺序，不限制最大天数。

## 关键证据

- `core/services/scheduler/gantt_range.py:69-92`：解析自定义区间后只挡 `end_date < start_date`，没有 `day_count` 上限。
- `core/services/scheduler/resource_dispatch_range.py:52`、`:77-81`：资源派工同类自定义区间已有默认 `max_day_count=62`，超过直接报错。
- `web/routes/domains/scheduler/scheduler_gantt.py:307-341`：`/scheduler/gantt/data` 从请求读取 `start_date/end_date`，传入 `svc.get_gantt_tasks()`。
- 子代理下钻确认：后续甘特任务/日历背景会按 `wr.week_start_date` 到 `wr.week_end_date` 做按天处理，大跨度不是只影响页面文案。

## 影响

单个请求就能构造很长日期跨度，导致后端查很大时间窗、生成很多日历/任务数据，属于和数据量无关的自伤型风险。

## 修复方向

把资源派工的 `max_day_count` 模式推广到甘特范围解析，错误信息走现有 `ValidationError` 用户提示。

## 建议动作

`cs-issue`，因为这是明确可达的单请求范围保护缺失。

