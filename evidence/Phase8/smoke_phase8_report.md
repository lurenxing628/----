# Phase8（甘特图与周计划 / M4）冒烟测试报告

- 测试时间：2026-03-13 12:26:46
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录（自动识别）：`D:\Github\APS Test`

## 0. 测试环境
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase8_d7e8lrrf`
- 测试 DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase8_d7e8lrrf\aps_phase8_test.db`

## 1. 基础数据准备（资源 + 工艺模板）

## 2. 批次创建与工序补全
- 已创建批次：B_CAL / B_SIM
- 内部工序已补全：B_CAL_05 / B_SIM_05

## 3. 工作日历约束（用于跨天）
- 已配置：2026-01-21 2h；2026-01-22 停工

## 4. 正式排产（生成版本，用于甘特图/周计划）
- 排产完成：version=1 result_status=success overdue_count=1

## 5. Web 页面与接口（甘特图/周计划）
- GET /scheduler/gantt：200
- GET /scheduler/gantt/data：200
- GET /scheduler/gantt/data (2nd)：200
- 甘特图 tasks 校验：1 条（契约字段齐全，含 overdue 标记，关键链缓存命中）
- 甘特图数据耗时：首次 4 ms，二次 3 ms
- GET /scheduler/week-plan：200
- GET /scheduler/week-plan/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- 周计划表.xlsx 表头校验：通过
- 周计划导出留痕：通过（log_id=4）

## 6. 插单模拟：新版本 + 不更新状态
- 模拟排产校验：通过（version=2；状态未变化；simulate 留痕存在）

## 结论
- 通过：Phase8（甘特图与周计划 / M4）冒烟测试通过（甘特图数据/周计划导出与留痕/插单模拟可追溯）。
- 总耗时：1919 ms
