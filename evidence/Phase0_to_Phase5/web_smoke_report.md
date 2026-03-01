# Phase0~Phase5 Web + Excel 端到端冒烟测试报告

- 测试时间：2026-02-28 21:33:52
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录（自动识别）：`D:\Github\APS Test`

## 1. 基础页面可用性
- GET /：200
- GET /personnel/：200
- GET /equipment/：200
- GET /process/：200

## 2. 设备管理：设备信息 Excel（上传→预览→确认→导出）
- GET /equipment/excel/machines/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /equipment/excel/machines/preview：200
- POST /equipment/excel/machines/confirm：200
- 严格拒绝校验：MC001/MC002 行数=0（期望 0）
- OperationLogs 校验（equipment/import/machine）：1 条（期望 >= 1）
- POST /equipment/excel/machines/preview（valid）：200
- POST /equipment/excel/machines/confirm（valid）：200
- Machines 写入校验：MC001/MC002 行数=2（期望 2）
- GET /equipment/excel/machines/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- OperationLogs 校验（equipment/export/machine）：2 条（期望 >= 1）

## 3. 人员管理：人员基本信息 Excel（上传→预览→确认→导出）
- GET /personnel/excel/operators/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /personnel/excel/operators/preview：200
- POST /personnel/excel/operators/confirm：200
- 严格拒绝校验：OP100/OP101 行数=0（期望 0）
- OperationLogs 校验（personnel/import/operator）：1 条（期望 >= 1）
- POST /personnel/excel/operators/preview（valid）：200
- POST /personnel/excel/operators/confirm（valid）：200
- Operators 写入校验：OP100/OP101 行数=2（期望 2）
- GET /personnel/excel/operators/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- OperationLogs 校验（personnel/export/operator）：2 条（期望 >= 1）

## 4. 人员管理：人员设备关联 Excel（上传→预览→确认→导出）
- GET /personnel/excel/links/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /personnel/excel/links/preview：200
- POST /personnel/excel/links/confirm：200
- 严格拒绝校验：OP100-MC001 行数=0（期望 0）
- OperationLogs 校验（personnel/import/operator_machine）：1 条（期望 >= 1）
- POST /personnel/excel/links/preview（valid）：200
- POST /personnel/excel/links/confirm（valid）：200
- OperatorMachine 写入校验：OP100-MC001 行数=1（期望 1）
- GET /personnel/excel/links/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

## 5. 工艺管理：工种/供应商/工艺路线 Excel（上传→预览→确认→导出）
- GET /process/excel/op-types/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /process/excel/op-types/preview：200
- POST /process/excel/op-types/confirm：200
- GET /process/excel/suppliers/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /process/excel/suppliers/preview：200
- POST /process/excel/suppliers/confirm：200
- GET /process/excel/routes/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- POST /process/excel/routes/preview：200
- POST /process/excel/routes/confirm：200
- Parts/PartOperations/ExternalGroups 生成校验：parts=1 ops=5 groups=1（期望 >=1）
- OperationLogs 校验（process/import/part_route）：2 条（期望 >= 1）
- GET /process/excel/part-operations/export：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

## 结论
- 通过：Phase0~Phase5 Web+Excel 关键链路端到端冒烟测试通过。
- 总耗时：2932 ms
