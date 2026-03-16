# Phase2（Models + Repositories）冒烟测试报告

- 测试时间：2026-03-16 10:58:02
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录（自动识别）：`D:\Github\APS Test`

## 0. 测试环境
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase2_p0r3du4w`
- 测试 DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase2_p0r3du4w\aps_phase2_test.db`

## 1. Schema 检查（Phase2 相关表）
- 表数量：26
- 是否存在 Operators：True
- 是否存在 Machines：True
- 是否存在 OperatorMachine：True
- 是否存在 OpTypes：True
- 是否存在 WorkCalendar：True
- 是否存在 ScheduleConfig：True
- 是否存在 OperationLogs：True
- 是否存在 ScheduleHistory：True

## 2. Operators 仓库：CRUD + UNIQUE 异常（中文）
- UNIQUE 异常捕获：code=1003 message=数据已存在，不能重复添加（唯一性约束冲突）。

## 3. Machines 仓库：CRUD + FK 异常（中文）
- FK 异常捕获：code=2004 message=数据关联校验失败：引用的记录不存在或已被删除。

## 4. OperatorMachine 仓库：联动 + UNIQUE/FK 异常（中文）
- OperatorMachine UNIQUE：code=1003 message=数据已存在，不能重复添加（唯一性约束冲突）。
- OperatorMachine FK：code=2004 message=数据关联校验失败：引用的记录不存在或已被删除。

## 5. WorkCalendar 仓库：upsert + range 查询
- range 查询行数：2（期望 2）

## 6. ScheduleConfig 仓库：set/get
- 配置条数：2（期望 >= 2）

## 7. OperationLogs / ScheduleHistory 仓库：基本写入与查询
- OperationLogs（module=smoke_phase2）记录数：1（期望 >= 1）
- ScheduleHistory 记录数：1（期望 >= 1）

## 8. 关键 SQL 输出（用于验收留痕）
- Operators 行数：1
- Machines 行数：1
- OperatorMachine 行数：1

## 结论
- 通过：Phase2（Models + Repositories）冒烟测试通过（CRUD/UNIQUE/FK/日历/配置/留痕）。
- 总耗时：290 ms
