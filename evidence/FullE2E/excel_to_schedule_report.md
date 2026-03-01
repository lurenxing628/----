# Full E2E（从 Excel 导入开始→排产→甘特/周计划→系统管理）验收报告

- 测试时间：2026-02-28 21:33:58
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录（自动识别）：`D:\Github\APS Test`

## 0. 测试环境（隔离目录）
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_full_e2e_d5p983z8`
- 测试 DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_full_e2e_d5p983z8\aps_full_e2e.db`
- logs：`C:\Users\LURENX~1\AppData\Local\Temp\aps_full_e2e_d5p983z8\logs`
- backups：`C:\Users\LURENX~1\AppData\Local\Temp\aps_full_e2e_d5p983z8\backups`
- templates_excel：`C:\Users\LURENX~1\AppData\Local\Temp\aps_full_e2e_d5p983z8\templates_excel`

## 1. 基础页面可访问性（用于确认路由装配）
- GET /：200
- GET /personnel/：200
- GET /equipment/：200
- GET /process/：200
- GET /scheduler/：200
- GET /system/backup：200

## 2. Excel：设备信息（导入→导出→留痕）
- GET /equipment/excel/machines/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /equipment/excel/machines/preview：200
- POST /equipment/excel/machines/confirm：200
- GET /equipment/excel/machines/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

## 3. Excel：人员基本信息 + 人员设备关联（导入→导出→留痕）
- GET /personnel/excel/operators/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /personnel/excel/operators/preview：200
- POST /personnel/excel/operators/confirm：200
- GET /personnel/excel/operators/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- GET /personnel/excel/links/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /personnel/excel/links/preview：200
- POST /personnel/excel/links/confirm：200
- GET /personnel/excel/links/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

## 4. Excel：工种/供应商/零件工艺路线（导入→生成模板→留痕）
- GET /process/excel/op-types/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /process/excel/op-types/preview：200
- POST /process/excel/op-types/confirm：200
- GET /process/excel/suppliers/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /process/excel/suppliers/preview：200
- POST /process/excel/suppliers/confirm：200
- GET /process/excel/routes/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /process/excel/routes/preview：200
- POST /process/excel/routes/confirm：200
- GET /process/excel/part-operations/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

## 5. Excel：批次信息（导入→自动生成工序→留痕）
- GET /scheduler/excel/batches/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /scheduler/excel/batches/preview：200
- POST /scheduler/excel/batches/confirm：200

## 6. Excel：工作日历（导入→导出→留痕）
- GET /scheduler/excel/calendar/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /scheduler/excel/calendar/preview：200
- POST /scheduler/excel/calendar/confirm：200
- GET /scheduler/excel/calendar/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

## 7. 批次工序补齐（确保排产可跑：内部人机匹配 + 外部周期）
- GET /scheduler/batches/B001：200
- POST /scheduler/ops/1/update（B001_05）：200
- POST /scheduler/ops/2/update（B001_35 外部）：200

## 8. 执行排产（/scheduler/run）→ 查询 Schedule/ScheduleHistory/OperationLogs
- POST /scheduler/run (follow redirects)：200
- ScheduleHistory：version=1 strategy=priority_first result_status=success
- Schedule 行数：2（version=1，期望 >=1）
- 甘特周起点（按排程起始时间）：2026-03-02
- Batches.status：scheduled（期望 scheduled）
- OperationLogs（schedule）：log_id=32 keys_ok

## 9. 甘特图与周计划（/scheduler/gantt/data + /scheduler/week-plan/export）
- GET /scheduler/gantt?version=abc：400
- GET /scheduler/gantt/data?version=abc：400
- GET /scheduler/week-plan?version=abc：400
- GET /scheduler/week-plan/export?version=abc：302
- week-plan/export invalid version redirect：/scheduler/week-plan
- GET /scheduler/gantt：200
- GET /scheduler/gantt/data：200
- 甘特图 tasks：2 条（字段齐全）
- GET /scheduler/week-plan/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

## 10. 系统管理抽检（logs/history/backup 页面可访问）
- GET /system/logs：200
- GET /system/history?version=1：200
- GET /system/backup：200

## 10.A 报表中心抽检（页面可访问）
- GET /reports/：200
- GET /reports/overdue：200
- GET /reports/utilization：200
- GET /reports/downtime：200

## 10.X 物料模块 MVP（物料→批次需求→齐套回写）
- GET /material/materials：200
- 选取批次：B001
- POST /material/materials/create (follow redirects)：200
- POST /material/batches/<bid>/requirements/add (follow redirects)：200
- 加入物料需求后批次齐套：no ready_date=None
- POST /material/requirements/<id>/update (follow redirects)：200
- 齐套后批次齐套：yes ready_date=2026-02-28

## 11. 留痕抽检（OperationLogs.detail 键名对齐开发文档）
- OperationLogs 抽检：通过（import/export/schedule 关键键名齐全）

## 结论
- 通过：Full E2E（从 Excel 导入开始→排产→甘特/周计划→系统管理）链路跑通。
- 总耗时：3315 ms
