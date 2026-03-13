# Phase4（设备管理模块）冒烟测试报告

- 测试时间：2026-03-13 12:26:41
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录（自动识别）：`D:\Github\APS Test`

## 0. 测试环境
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase4_bhs2rzyz`
- 测试 DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase4_bhs2rzyz\aps_phase4_test.db`

## 1. Schema 检查（Phase4 相关表）
- 是否存在 Machines：True
- 是否存在 MachineDowntimes：True
- 是否存在 OperatorMachine：True
- 是否存在 OpTypes：True
- 是否存在 BatchOperations：True
- 是否存在 Batches：True
- 是否存在 Parts：True
- 是否存在 Operators：True

## 2. 设备服务：创建/更新/清空字段（中文校验）
- 清空后：remark=None op_type_id=None（期望均为 None）
- 非法状态异常：code=1001 message=状态不正确，请选择：可用 / 维修 / 停用。

## 3. 设备-人员关联：新增/查询（双向一致底层表）
- MC001 关联数量：1（期望 1）

## 4. 设备 Excel 预览：NEW/UPDATE/ERROR（含工种识别）
- 预览状态序列：['update', 'new', 'error', 'error', 'error']

## 5. REPLACE 保护：存在批次引用时禁止清空设备
- 保护异常：code=4003 message=已有批次工序引用了设备，不能执行替换（清空后导入）。请先解除引用或改用覆盖/追加。

## 6. 设备停机计划：新增/重叠校验/取消
- 新增停机：id=1 machine=MC001 2026-01-22 08:00:00~2026-01-22 12:00:00 reason=maintenance
- 重叠校验：code=6003 message=该设备在该时间段已存在停机计划（时间段重叠）。请调整时间。
- 取消后重建停机：id=2（期望成功）

## 结论
- 通过：Phase4（设备管理模块）冒烟测试通过（CRUD/字段清空/关联/Excel 预览/REPLACE 保护/停机计划）。
- 总耗时：874 ms
