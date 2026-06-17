# Finding 17：超期/延期统计遇到坏 due_date 会静默跳过整批

- 优先级：P1 阻塞
- 结论：超期和延期诊断已经努力把坏排程时间放进“排程时间异常”，但如果批次 `due_date` 本身坏了，整批会被 `continue` 掉，没有进入 scheduled、unscheduled、invalid_time，也没有提示。

## 根因

`compute_overdue_bucket_groups()` 对每个批次先解析 `due_date`。解析失败时直接 `continue`，没有把它计入坏数据桶，也没有记录降级事件。

大白话说：截止日期写坏了，系统不是告诉用户“这条截止日期坏了”，而是把这批从超期统计里拿掉了。

## 调用链

- `ReportEngine.overdue_report()`
- `compute_overdue_bucket_groups(rows)`
- `ScheduleDelayDiagnosisService` 也复用同一个分桶函数
- 页面和 Excel 摘要消费这些分桶结果

## 证据

- `data/repositories/schedule_plan_query_repo.py:415-416`：查询把 `due_date` 和计划 `finish_time` 一起交给上层。
- `core/services/common/overdue_calculations.py:75-82`：`due_d = parse_dt(due_s)` 后，解析失败直接 `continue`。
- `core/services/report/report_engine.py:179`：超期报表使用 `compute_overdue_bucket_groups()`。
- `core/services/scheduler/schedule_delay_diagnosis_service.py:66`：延期诊断也使用同一个分桶函数。
- 主线程只读复现：输入 `due_date='2026-02-31'` 且有晚于截止日的完成时间，输出为 `{'scheduled': [], 'unscheduled': [], 'invalid_time': []}`。

## 影响

- 坏 `due_date` 的批次会从超期清单和延期诊断里消失。
- 用户看不到“截止日期坏了”的提示，容易误以为没有风险。
- 这和本分支“不静默吞坏时间”的方向不一致。

## 建议

- 把坏 `due_date` 单独计入数据异常桶，至少在页面和导出摘要中提示。
- 如果业务上截止日期坏了无法判断超期，也要显示为“无法判断”，不能直接消失。
- 增加回归：坏 due_date、有排程、无排程、混合坏时间，都要有可见提示。
