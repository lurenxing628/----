# Phase0+Phase1 冒烟测试报告

- 测试时间：2026-02-28 01:01:57
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录（自动识别）：`D:\Github\APS Test`
- Flask：2.3.3
- openpyxl：3.0.10

## 0. 测试环境与目录
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_h64hvm6t`
- 测试 DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_h64hvm6t\aps_test.db`
- 测试日志目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_h64hvm6t\logs`
- 测试备份目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_h64hvm6t\backups`

## 1. Schema 检查
- 表数量：25
- 是否存在 SchemaVersion：True
- 是否存在 OperationLogs：True
- 是否存在 ResourceLocks：False
- SchemaVersion.version：4

## 1.1 Schema 迁移机制（缺列补齐 + 迁移前备份）
- 迁移前备份文件数（before_migrate_v0_to_v4）：1
- 旧库迁移后 SchemaVersion.version：4

## 2. Excel 读写与预览
- 写入并读取行数：2（期望 2）
- 预览状态统计：{"update": 1, "new": 1}
- OP001 行号(row_num)：2（应为 2）

## 3. 留痕（OperationLogs）检查
- 最近记录数（取 5 条）：2
- id=2 action=export module=smoke_test target_type=operator
  - detail={"template_or_export_type": "人员基本信息模板.xlsx", "filters": {}, "row_count": 1, "time_range": {}, "time_cost_ms": 45}
- id=1 action=import module=smoke_test target_type=operator
  - detail={"filename": "test.xlsx", "mode": "overwrite", "time_cost_ms": 123, "total_rows": 2, "new_count": 1, "update_count": 1, "skip_count": 0, "error_count": 0, "errors_sample": []}

## 4. Web 冒烟（Flask test_client）
- GET /：200
- GET /excel-demo/：200
- GET /__not_found__：404
- GET /excel-demo/template：200 content-type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

### 4.1 端到端：上传→预览→确认导入
- POST /excel-demo/preview：200
- POST /excel-demo/confirm（follow_redirects）：200
- Operators 写入校验：OP100/OP101 行数=2（期望 2）
- OperationLogs 写入校验：excel_demo import 记录数=2（期望 >= 1）

## 5. 备份检查
- 手动触发备份：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_h64hvm6t\backups\aps_backup_20260228_010159_auto_test.db`
- backups 文件数：1

## 6. 文件日志检查（用户排障）
- aps.log 是否存在：True（`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_h64hvm6t\logs\aps.log`）
- aps_error.log 是否存在：True（`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_h64hvm6t\logs\aps_error.log`）

### aps.log 摘录（最后 20 行）
```
2026-02-28 01:01:59 [INFO] web.bootstrap.factory [security.py:54]: 已生成 SECRET_KEY 并写入：C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_h64hvm6t\logs\aps_secret_key.txt
2026-02-28 01:01:59 [INFO] web.bootstrap.factory [factory.py:102]: 已生成 Excel 模板：10 个
2026-02-28 01:01:59 [INFO] web.bootstrap.factory [database.py:165]: 数据库结构检查完成（已确保所有表存在）。
2026-02-28 01:01:59 [INFO] web.bootstrap.factory [logging.py:157]: [plugins] 操作：load（runtime plugins）
2026-02-28 01:01:59 [INFO] web.bootstrap.factory [factory.py:231]: 应用启动完成。
2026-02-28 01:01:59 [INFO] web.bootstrap.factory [database.py:165]: 数据库结构检查完成（已确保所有表存在）。
2026-02-28 01:01:59 [INFO] web.bootstrap.factory [logging.py:157]: [plugins] 操作：load（runtime plugins）
2026-02-28 01:01:59 [INFO] web.bootstrap.factory [factory.py:231]: 应用启动完成。
2026-02-28 01:01:59 [INFO] web.bootstrap.factory [logging.py:157]: [excel_demo] 操作：export（operator ）
2026-02-28 01:01:59 [INFO] web.bootstrap.factory [logging.py:157]: [excel_demo] 操作：import（operator ）
2026-02-28 01:01:59 [INFO] web.bootstrap.factory [logging.py:157]: [excel_demo] 操作：import（operator ）
```

## 结论
- 通过：Phase0+Phase1 核心链路冒烟测试通过（Schema/Excel/留痕/Web/备份）。
- 总耗时：1996 ms
