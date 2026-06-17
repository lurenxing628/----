# Finding 03：SQL 时间判断和 Python 时间解析口径不一致

- 优先级：P1 阻塞
- 结论：坏时间行可能在 SQL 层被当成有效行，导致上层坏时间提示链漏报。

## 根因

`data/repositories/schedule_time_sql.py` 注释写着 SQL 侧和 core 层 `parse_dt` 对齐，但实现使用 SQLite `datetime(...)`。SQLite 对部分异常时间比较宽松，Python `datetime.strptime("%Y-%m-%d %H:%M:%S")` 更严格。

大白话说：SQL 和 Python 用了两把尺，同一条脏数据，一个地方说“能用”，另一个地方说“坏了”。

## 调用链

- 报表、Gantt、资源派工从 `schedule_plan_query_repo.py` 取计划明细。
- SQL 侧用 `valid_time_range_sql()` 和 `overlap_or_bad_time_sql()` 决定“有效区间”或“坏时间兜回”。
- 服务层再用 Python 解析时间并生成降级提示。

## 证据

- `data/repositories/schedule_time_sql.py:14-18`：`time_dt()` 使用 SQLite `datetime(...)`。
- `data/repositories/schedule_time_sql.py:21-31`：`valid_time_range_sql()` 用 `datetime(...) IS NOT NULL` 判断有效。
- `core/services/report/calculation_helpers.py:9-20`：Python 严格 `strptime`。
- `core/services/scheduler/_sched_display_utils.py:11`：调度展示侧也用 Python 严格解析。
- 主线程只读复现：
  - `2026-02-30 08:00:00`：Python 解析失败，SQLite 返回 `2026-02-30 08:00:00`。
  - `2026-01-01 24:00:00`：Python 解析失败，SQLite 返回 `2026-01-01 24:00:00`。
  - `2026-01-01 08:00:00.123`：Python 解析失败，SQLite 返回 `2026-01-01 08:00:00`。
  - `2026-01-01 99:00:00`：两边都判坏。

## 影响

- 部分坏时间不会进入 `OR NOT(valid)` 兜回分支。
- 用户可能看不到“有坏时间被跳过”的提示。
- 报表、Gantt、资源派工可能对同一批脏数据给出不同表现。

## 建议

- 只保留一套时间准绳：要么 SQL 严格模拟 Python `strptime`，要么 SQL 只做粗筛，最终用 Python 判定并保证坏行能进入提示链。
- 增加覆盖：非法日期、24 点、毫秒、全角冒号、`T`、斜杠。
