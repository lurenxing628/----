---
doc_type: audit-finding
audit: 2026-05-21-networkx-full-browser-stress
finding_id: resource-dispatch-date-query-ignored
nature: frontend-behavior
severity: P1
confidence: high
status: open
suggested_action: cs-issue
last_deep_trace: 2026-05-21
---

# Finding 06：资源排班页面忽略 start_date/end_date 查询参数

## 现象

同一个 v15 版本，甘特图和周计划能看到 2026-05-04 到 2026-05-11 的任务，但资源排班页面打开同样日期参数后，页面显示的是另一段日期，并且任务数为 0。

## 操作步骤

打开：

```text
http://127.0.0.1:61661/scheduler/resource-dispatch?version=15&scope_type=machine&start_date=2026-05-04&end_date=2026-05-11
```

## 实际表现

页面显示：

```text
区间 2026-05-18 ～ 2026-05-24
任务数 0
未查询到排班任务
```

## 期望表现

页面应按 URL 里的日期显示 `2026-05-04 ～ 2026-05-11`，并能看到和 v15 甘特图/周计划一致的任务。

## 问题类型

数据筛选/交互错误。

## 严重程度

明显影响使用。用户从分析页或手工带日期进入资源排班时，会看到错误时间段和空数据。

## 证据

- 截图：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/resource-dispatch-machine-v15-query-ignored.png`
- 对比页：
  - `/scheduler/gantt?view=machine&version=15`
  - `/scheduler/week-plan?version=15&week_start=2026-05-04`

## 追加根因追踪（2026-05-21）

根因不是版本没有数据。资源排班页面收到了 URL 里的 `start_date/end_date`，但因为 URL 没带 `period_preset=custom`，服务仍按默认 `week` 模式算日期，最终用的是服务器当天加一天所在的周，也就是 `2026-05-18 ～ 2026-05-24`。

调用链：

- [web/routes/domains/scheduler/scheduler_resource_dispatch_query.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_resource_dispatch_query.py:52) 的 `_request_kwargs()` 读取了 `start_date/end_date`。
- 同一个函数在 [web/routes/domains/scheduler/scheduler_resource_dispatch_query.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_resource_dispatch_query.py:60) 把 `period_preset` 默认成 `week`。
- [core/services/scheduler/resource_dispatch_service.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/resource_dispatch_service.py:239) 和 [core/services/scheduler/resource_dispatch_service.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/resource_dispatch_service.py:355) 调 `resolve_dispatch_range()`。
- [core/services/scheduler/resource_dispatch_range.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/resource_dispatch_range.py:68) 只有在 `period_preset == "custom"` 时才解析 `start_date/end_date`。
- `week` 模式下走 `query_date`，未传时 [core/services/scheduler/resource_dispatch_range.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/resource_dispatch_range.py:58) 用 `datetime.now() + 1 天`。
- 页面展示的日期来自服务重新算出来的 `filters.start_date/end_date`，在 [core/services/scheduler/resource_dispatch_service.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/resource_dispatch_service.py:272) 和 [templates/scheduler/resource_dispatch.html](/Users/lurenxing/Documents/GitHub/----/templates/scheduler/resource_dispatch.html:53)。
- 数据接口也走同一套请求解析和服务查询：[web/routes/domains/scheduler/scheduler_resource_dispatch.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_resource_dispatch.py:82)。
- 最终查库用 `dr.start_time/dr.end_time`，在 [core/services/scheduler/resource_dispatch_service.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/resource_dispatch_service.py:367)。
- 仓储 SQL 用时间重叠查询：`s.start_time < end_time` 且 `s.end_time > start_time`，位置在 [data/repositories/schedule_plan_query_repo.py](/Users/lurenxing/Documents/GitHub/----/data/repositories/schedule_plan_query_repo.py:200)。

关键变量：

- URL 原始值：`start_date=2026-05-04`、`end_date=2026-05-11`、`version=15`、`scope_type=machine`。
- 实际 `period_preset=week`。
- `query_date` 未传，因此按当前运行日期 `2026-05-21` 推到锚点 `2026-05-22`。
- 解析后页面范围变成 `2026-05-18 ～ 2026-05-24`。
- 实际查询窗口为 `2026-05-18 00:00:00 ～ 2026-05-25 00:00:00`，临时库查到 `0` 条。
- URL 期望窗口 `2026-05-04 00:00:00 ～ 2026-05-12 00:00:00` 能查到 `21` 条 machine 记录。

和其他结果页的差异：

- 甘特图明确读取并尊重 `start_date/end_date`：[web/routes/domains/scheduler/scheduler_gantt.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_gantt.py:111)、[core/services/scheduler/gantt_range.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/gantt_range.py:46)。
- 周计划只按 `week_start` 查：[web/routes/domains/scheduler/scheduler_week_plan.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_week_plan.py:276)。
- 资源排班当前夹在中间：入口接受 `start_date/end_date`，但默认模式不把它们当有效日期范围。

## 建议修复方向

最小修复点应放在资源排班请求解析边界：当 `period_preset` 没有显式传入，但 URL 带了 `start_date` 或 `end_date` 时，自动按 `custom` 处理。不要简单让所有 `start_date/end_date` 永远压过 `period_preset`，因为资源排班表单在非自定义模式下也可能残留隐藏日期字段。

需要补两条回归：一条是不带 `period_preset` 但带 `start_date/end_date` 时应返回 `filters.period_preset == "custom"` 并查到任务；另一条是显式 `period_preset=week&query_date=...` 时，即使有残留 `start_date/end_date`，仍按周查询。
