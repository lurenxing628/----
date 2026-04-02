# Phase0~Phase6 Web + Excel 端到端冒烟测试报告

- 测试时间：2026-04-02 16:55:18
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录（自动识别）：`D:\Github\APS Test`

## 1. 基础页面可用性（含 Scheduler）
- GET /：200
- GET /personnel/：200
- GET /equipment/：200
- GET /process/：200
- GET /scheduler/：200
- GET /scheduler/calendar：200

## 1.X 设备管理：停机计划（设备详情页展示 + 提交新增）
- GET /equipment/MC_D1：200
- POST /equipment/MC_D1/downtimes/create：200

## 2. 排产调度：批次信息 Excel（上传→预览→确认→导出）
- GET /scheduler/excel/batches/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /scheduler/excel/batches/preview：200
- POST /scheduler/excel/batches/confirm：200
- 严格拒绝校验：B001 batch_cnt=0 ops_cnt=0（期望 batch_cnt=0 ops_cnt=0）
- POST /scheduler/excel/batches/preview（valid）：200
- POST /scheduler/excel/batches/confirm（valid）：200
- Batches/BatchOperations 写入校验：B001 batch_cnt=1 ops_cnt=2（期望 batch_cnt=1 ops_cnt>=1）
- OperationLogs 校验（scheduler/import/batch）：3 条（期望 >= 1）
- GET /scheduler/excel/batches/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- OperationLogs 校验（scheduler/export/batch）：2 条（期望 >= 1）

## 2.X 排产调度：批次工序补充（人机匹配约束）
- 目标内部工序：id=1 op_code=B001_05
- GET /scheduler/batches/B001：200
- POST /scheduler/ops/1/update（不匹配应拒绝）：400
- POST /scheduler/ops/1/update（匹配应成功）：200

## 3. 排产调度：工作日历 Excel（上传→预览→确认→导出）
- GET /scheduler/excel/calendar/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /scheduler/excel/calendar/preview：200
- POST /scheduler/excel/calendar/confirm：200
- 严格拒绝校验：2026-01-21 行数=0（期望 0）
- POST /scheduler/excel/calendar/preview（valid）：200
- POST /scheduler/excel/calendar/confirm（valid）：200
- WorkCalendar 写入校验：2026-01-21 行数=1（期望 1）
- OperationLogs 校验（scheduler/import/calendar）：3 条（期望 >= 1）
- GET /scheduler/excel/calendar/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- OperationLogs 校验（scheduler/export/calendar）：2 条（期望 >= 1）

## 结论
- 通过：Phase0~Phase6 Web+Excel 关键链路端到端冒烟测试通过（含 Scheduler）。
- 总耗时：2675 ms
