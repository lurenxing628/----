# Phase3（人员管理模块）冒烟测试报告

- 测试时间：2026-01-28 00:43:29
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录（自动识别）：`D:\Github\APS Test`

## 0. 测试环境
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase3_q2fh6_xu`
- 测试 DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase3_q2fh6_xu\aps_phase3_test.db`

## 1. Schema 检查（Phase3 相关表）
- 是否存在 Operators：True
- 是否存在 Machines：True
- 是否存在 OperatorMachine：True
- 是否存在 OpTypes：True
- 是否存在 BatchOperations：True
- 是否存在 Batches：True
- 是否存在 Parts：True

## 2. 人员服务：创建/更新/清空备注（中文校验）
- 清空备注后 remark=None（期望 None）
- 非法状态异常：code=1001 message=“状态”不合法（允许：active / inactive）

## 3. 人员-设备关联服务：新增/预览/导入（复合键）
- OP001 关联数量：1（期望 1）
- 预览状态序列：['unchanged', 'new', 'error', 'error']
- 导入统计：{'total_rows': 4, 'new_count': 1, 'update_count': 0, 'skip_count': 0, 'error_count': 2, 'errors_sample': [{'row': 4, 'message': '人员“OP_NOT_EXIST”不存在，请先在人员管理中新增该人员。'}, {'row': 5, 'message': 'Excel 中存在重复的“工号+设备编号”行，请去重后再导入。'}]}

## 4. 人员 Excel 预览：NEW/UPDATE/ERROR
- 预览状态序列：['update', 'new', 'error']

## 5. REPLACE 保护：存在批次引用时禁止清空人员
- 保护异常：code=3003 message=已有批次工序引用了人员，不能执行“替换（清空后导入）”。请先解除引用或改用“覆盖/追加”。

## 结论
- 通过：Phase3（人员管理模块）冒烟测试通过（CRUD/备注清空/关联预览与导入/Excel 预览/REPLACE 保护）。
- 总耗时：1691 ms
