# Finding 16：报表默认日期范围用 raw 文本 MIN/MAX，可能算出反向跨度

- 优先级：P1 阻塞
- 结论：报表默认日期范围会先用 SQL `MIN(start_time)` / `MAX(end_time)` 取计划跨度，但取的是原始文本，不是规范化后的时间。混用 `T`、斜杠等格式时，可能算出开始日期晚于结束日期。

## 根因

SQL 的 `WHERE` 用 `valid_time_range_sql()` 判断“看起来是有效时间”，但 `SELECT` 取最早/最晚时没有对同一套表达式求 `MIN(datetime(start_time))` / `MAX(datetime(end_time))`，而是直接对文本做 MIN/MAX。

大白话说：筛选时按时间看，排序取最小最大时却按字符串看。字符串的大小顺序和真实日期顺序不是一回事。

## 调用链

- `web/routes/report_plan_preview.py::default_date_range_for_version()`
- `ReportPlanHelpers.version_date_range()`
- `SchedulePlanQueryRepo.get_plan_time_span()`
- SQL 返回 raw `min_start_time` / `max_end_time`
- Python 再把这两个 raw 字符串解析成日期

## 证据

- `data/repositories/schedule_plan_query_repo.py:267-296`：`Schedule`、候选方案、模拟方案都用 `SELECT MIN(start_time), MAX(end_time)`。
- `core/services/report/report_plan_helpers.py:187-195`：拿 span 后用 Python parse，再生成日期范围。
- `web/routes/report_plan_preview.py:77-82`：span 有数据就作为 `version_span` 默认日期，否则才回退 7 天。
- 主线程只读复现：两条有效时间里放入 `2026-05-03T08:00:00` 和 `2026/05/01 12:00:00`，当前查询返回 `('2026-05-03T08:00:00', '2026/05/01 12:00:00')`；按规范化时间应是 `('2026-05-01 08:00:00', '2026-05-03 12:00:00')`。

## 影响

- 报表预览可能拿到反向日期范围。
- 用户会看到默认筛选不符合排产版本真实跨度。
- 下游导出、页面跳转和工作台链接可能继续传播错误日期。

## 建议

- SQL span 要么直接返回规范化后的 `MIN(datetime(...))` / `MAX(datetime(...))`，要么把所有候选时间带到 Python，用同一套严格解析规则计算跨度。
- 增加覆盖：空格、`T`、斜杠、毫秒、非法日期混排时，默认日期范围必须稳定且不反向。
