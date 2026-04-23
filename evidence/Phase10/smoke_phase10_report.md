# Phase10（SGS/自动分配/OR-Tools/冻结窗口）冒烟测试报告

- 测试时间：2026-04-19 01:22:24
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录：`D:\Github\APS Test`
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase10_aau4n902`
- 测试 DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase10_aau4n902\aps_phase10_test.db`

## 1. 基础数据准备

## 2. 工艺模板准备（含 merged 外协组）

## 3. 批次创建（内部工序缺省资源）
- 已创建批次：B10_1/B10_2（内部工序未补全 machine/operator）

## 4. auto-assign 关闭：缺省资源应导致失败
- auto-assign 关闭命中空结果契约：[1001] 优化结果未生成有效可落库排程行

## 5. auto-assign 开启：应成功排产且不与停机重叠
- result_status=simulated failed_ops=0 scheduled_ops=8
- downtime_avoid 校验通过（MC_A1 无重叠）

## 6. SGS 派工：应可跑且无资源重叠
- SGS：version=2 failed_ops=0 scheduled_ops=8
- SGS 资源重叠校验通过（machine/operator）

## 7. merged 外协组：同组同起止
- 外协组起止一致：2026-02-03 09:18:00 ~ 2026-02-05 09:18:00

## 8. 冻结窗口：第二次排产应出现 locked
- freeze_window：v3 -> v4 locked_count=3

## 9. OR-Tools 开关：可选项不应阻断排产
- ortools_enabled=yes：version=5 failed_ops=0（无论环境是否安装 ortools，都应可继续）

## 结论
- PASS：SGS/自动分配/冻结窗口/外协合并周期/停机避让 基本链路可用。
- 总耗时：1.706s
