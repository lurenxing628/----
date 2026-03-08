# Phase7（排产算法 / M3）冒烟测试报告

- 测试时间：2026-03-08 17:36:38
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录（自动识别）：`D:\Github\APS Test`

## 0. 测试环境
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase7_4ufo4na8`
- 测试 DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase7_4ufo4na8\aps_phase7_test.db`

## 1. 基础数据准备（工种/供应商/资源）

## 2. 工艺模板准备（含 merged 外部组）

## 3. 批次创建（从模板复制生成工序）
- 已创建批次：B_CAL/B001/B002/B_EXT

## 4. 工序补充（内部工序设备/人员/工时）
- 内部工序资源已补全（设备/人员均为 active 且符合 OperatorMachine）

## 5. 工作日历约束：短班次 + 停工（用于验证跨天）
- 已配置：2026-01-21 2h，2026-01-22 停工

## 6. 排产执行：策略切换 + 落库 + 留痕
- priority_first（B_CAL）：version=1 result_status=success scheduled_ops=1
- 日历跨天校验：B_CAL end_time=2026-01-23 09:00:00（期望 2026-01-23 09:00:00）
- due_date_first：version=2 result_status=success overdue=1
- 人员冲突校验：B001_05 [2026-02-02 09:00:00~2026-02-02 13:00:00]  B002_05 [2026-02-02 13:00:00~2026-02-03 09:00:00]（期望不重叠）
- merged 外部组校验：start=2026-02-02 09:00:00 end=2026-02-05 09:00:00 span_days=3.0（期望 3.0）
- 超期预警校验：B_EXT 已出现在 overdue_batches
- result_summary.algo 留痕：mode=improve objective=min_overdue metrics={'overdue_count': 1, 'total_tardiness_hours': 57.0003, 'makespan_hours': 73.0, 'changeover_count': 0, 'weighted_tardiness_hours': 114.0006, 'makespan_internal_hours': 25.0, 'machine_used_count': 2, 'operator_used_count': 1, 'machine_busy_hours_total': 25.0, 'operator_busy_hours_total': 25.0, 'machine_util_avg': 0.5, 'operator_util_avg': 1.0, 'machine_load_cv': 0.6, 'operator_load_cv': 0.0, 'internal_horizon_hours': 25.0, 'util_defined': True}
- 冻结窗口校验：version=3 locked_cnt=5 frozen_op_count=5
- weighted：version=4 strategy_params={'priority_weight': 0.4, 'due_weight': 0.5, 'dispatch_mode': 'batch_order', 'dispatch_rule': 'slack', 'auto_assign_enabled': 'no'}
- fifo：version=5

## 7. 留痕核对（ScheduleHistory / OperationLogs）
- ScheduleHistory 最近 6 条：[(5, 'fifo', 'success'), (4, 'weighted', 'success'), (3, 'due_date_first', 'success'), (2, 'due_date_first', 'success'), (1, 'priority_first', 'success')]
- ScheduleHistory.result_summary 字段校验：包含 overdue_batches/strategy_params
- OperationLogs(schedule) 最近 4 条：[(5, '5'), (4, '4'), (3, '3'), (2, '2')]

## 结论
- 通过：Phase7（排产算法 / M3）冒烟测试通过（策略切换/双资源冲突/日历/外部合并周期/落库/留痕）。
- 总耗时：810 ms
