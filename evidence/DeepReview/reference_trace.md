# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ OperatorMachineRepository.list_by_operator() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ OperatorMachineRepository.list_by_machine() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ OperatorMachineRepository.list_simple_rows() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ OperatorMachineRepository.list_with_names_by_machine() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ OperatorMachineRepository.list_with_names_by_operator() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ OperatorMachineRepository.list_links_with_operator_info() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ OperatorMachineRepository.list_simple_rows_for_machine_operator_sets() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/infrastructure/backup.py（Infrastructure 层）

### `BackupManager.__init__()` [私有]
- 位置：第 18-30 行
- 参数：db_path, backup_dir, keep_days, logger
- 返回类型：无注解

### `BackupManager.backup()` [公开]
- 位置：第 32-72 行
- 参数：suffix
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（3 处）：
  - `web/routes/system_backup.py:52` [Route] `path = mgr.backup(suffix="manual")`
  - `core/services/system/maintenance/backup_task.py:35` [Service] `path = mgr.backup(suffix="auto")`
  - `core/infrastructure/database.py:317` [Infrastructure] `backup_path = bm.backup(suffix=f"before_migrate_v{from_version}_to_v{to_version}`
- **被调用者**（18 个）：`strftime`, `join`, `os.replace`, `info`, `datetime.now`, `exists`, `closing`, `os.remove`, `sqlite3.connect`, `source.backup`, `lower`, `fetchall`, `warning`, `error`, `RuntimeError`

### `BackupManager.restore()` [公开]
- 位置：第 74-168 行
- 参数：backup_path
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/system_backup.py:196` [Route] `- 恢复前自动备份 before_restore（由 BackupManager.restore() 内部保证）`
  - `web/routes/system_backup.py:217` [Route] `ok = mgr.restore(backup_path)`
- **被调用者**（27 个）：`exists`, `error`, `_MAINT_MUTEX.acquire`, `abspath`, `self.backup`, `range`, `os.open`, `exception`, `_MAINT_MUTEX.release`, `os.write`, `warning`, `info`, `os.close`, `os.remove`, `encode`

### `BackupManager.cleanup_old_backups()` [公开]
- 位置：第 170-186 行
- 参数：无
- 返回类型：无注解
- **调用者**（1 处）：
  - `web/routes/system_backup.py:175` [Route] `mgr.cleanup_old_backups()`
- **被调用者**（11 个）：`os.listdir`, `datetime.now`, `timedelta`, `exists`, `join`, `filename.startswith`, `datetime.fromtimestamp`, `getmtime`, `os.remove`, `info`, `warning`

### `BackupManager.list_backups()` [公开]
- 位置：第 188-207 行
- 参数：无
- 返回类型：Name(id='list', ctx=Load())
- **调用者**（3 处）：
  - `web/routes/system_backup.py:30` [Route] `backups = mgr.list_backups()`
  - `web/routes/system_backup.py:174` [Route] `before = mgr.list_backups()`
  - `web/routes/system_backup.py:176` [Route] `after = mgr.list_backups()`
- **被调用者**（10 个）：`sorted`, `exists`, `os.listdir`, `join`, `os.stat`, `backups.append`, `filename.startswith`, `round`, `isoformat`, `datetime.fromtimestamp`

## core/infrastructure/database.py（Infrastructure 层）

### `_is_windows_lock_error()` [私有]
- 位置：第 15-24 行
- 参数：e
- 返回类型：Name(id='bool', ctx=Load())

### `_cleanup_sqlite_sidecars()` [私有]
- 位置：第 27-39 行
- 参数：db_path, logger
- 返回类型：Constant(value=None, kind=None)

### `_restore_db_file_from_backup()` [私有]
- 位置：第 42-88 行
- 参数：backup_path, db_path, logger, retries, base_delay_s
- 返回类型：Constant(value=None, kind=None)

### `get_connection()` [公开]
- 位置：第 91-108 行
- 参数：db_path
- 返回类型：Attribute(value=Name(id='sqlite3', ctx=Load()), attr='Connec
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`dirname`, `sqlite3.connect`, `conn.execute`, `os.makedirs`

### `ensure_schema()` [公开]
- 位置：第 111-193 行
- 参数：db_path, logger, schema_path, backup_dir
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/system_backup.py:223` [Route] `ensure_schema(`
- **被调用者**（22 个）：`abspath`, `get_connection`, `candidates.append`, `FileNotFoundError`, `exists`, `_migrate_with_backup`, `join`, `getattr`, `conn.executescript`, `_ensure_schema_version`, `_get_schema_version`, `conn.commit`, `conn.close`, `dirname`, `os.getcwd`

### `_ensure_schema_version()` [私有]
- 位置：第 196-222 行
- 参数：conn, logger
- 返回类型：Constant(value=None, kind=None)

### `_detect_schema_is_current()` [私有]
- 位置：第 225-255 行
- 参数：conn
- 返回类型：Name(id='bool', ctx=Load())

### `_get_schema_version()` [私有]
- 位置：第 258-269 行
- 参数：conn
- 返回类型：Name(id='int', ctx=Load())

### `_set_schema_version()` [私有]
- 位置：第 272-273 行
- 参数：conn, version
- 返回类型：Constant(value=None, kind=None)

### `_migrate_with_backup()` [私有]
- 位置：第 276-383 行
- 参数：db_path, from_version, to_version, backup_dir, logger
- 返回类型：Constant(value=None, kind=None)

### `_run_migration()` [私有]
- 位置：第 386-390 行
- 参数：conn, target_version, logger
- 返回类型：Constant(value=None, kind=None)

## core/infrastructure/logging.py（Infrastructure 层）

### `AppLogger.__init__()` [私有]
- 位置：第 15-38 行
- 参数：app_name, log_dir, log_level, max_bytes, backup_count
- 返回类型：无注解

### `AppLogger._add_console_handler()` [私有]
- 位置：第 40-48 行
- 参数：无
- 返回类型：无注解

### `AppLogger._add_file_handler()` [私有]
- 位置：第 50-64 行
- 参数：无
- 返回类型：无注解

### `AppLogger._add_error_file_handler()` [私有]
- 位置：第 66-81 行
- 参数：无
- 返回类型：无注解

### `AppLogger.get_logger()` [公开]
- 位置：第 83-86 行
- 参数：name
- 返回类型：Attribute(value=Name(id='logging', ctx=Load()), attr='Logger
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`logging.getLogger`

### `OperationLogger.__init__()` [私有]
- 位置：第 92-94 行
- 参数：db_connection, logger
- 返回类型：无注解

### `OperationLogger.log()` [公开]
- 位置：第 96-154 行
- 参数：level, module, action, target_type, target_id, operator, detail, error_code, error_message
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`execute`, `bool`, `error`, `getattr`, `in_transaction_context`, `commit`, `json.dumps`, `rollback`

### `OperationLogger.info()` [公开]
- 位置：第 156-159 行
- 参数：module, action
- 返回类型：无注解
- **调用者**（30 处）：
  - `web/routes/system_backup.py:61` [Route] `g.op_logger.info(`
  - `web/routes/system_backup.py:105` [Route] `g.op_logger.info(`
  - `web/routes/system_backup.py:149` [Route] `g.op_logger.info(`
  - `web/routes/system_backup.py:180` [Route] `g.op_logger.info(`
  - `web/routes/system_backup.py:236` [Route] `op_logger.info(`
  - `web/routes/system_plugins.py:33` [Route] `g.op_logger.info(`
  - `core/services/common/excel_audit.py:85` [Service] `op_logger.info(`
  - `core/services/common/excel_audit.py:119` [Service] `op_logger.info(`
  - `core/services/material/batch_material_service.py:71` [Service] `self.op_logger.info(`
  - `core/services/material/batch_material_service.py:100` [Service] `self.op_logger.info(`
  - `core/services/material/batch_material_service.py:120` [Service] `self.op_logger.info(`
  - `core/services/material/material_service.py:81` [Service] `self.op_logger.info(module="material", action="create", target_type="material", `
  - `core/services/material/material_service.py:114` [Service] `self.op_logger.info(`
  - `core/services/material/material_service.py:131` [Service] `self.op_logger.info(module="material", action="delete", target_type="material", `
  - `core/services/process/route_parser.py:245` [Service] `self.logger.info(`
  - `core/services/scheduler/schedule_persistence.py:178` [Service] `svc.op_logger.info(`
  - `core/services/system/operation_log_service.py:45` [Service] `self.op_logger.info(`
  - `core/services/system/operation_log_service.py:60` [Service] `self.op_logger.info(`
  - `core/services/system/maintenance/backup_task.py:46` [Service] `op_logger.info(`
  - `core/services/system/maintenance/cleanup_task.py:120` [Service] `op_logger.info(`
  - `core/services/system/maintenance/cleanup_task.py:203` [Service] `op_logger.info(`
  - `core/infrastructure/backup.py:64` [Infrastructure] `self.logger.info(f"数据库已备份：{backup_path}")`
  - `core/infrastructure/backup.py:116` [Infrastructure] `self.logger.info(f"数据库已恢复：{backup_path}")`
  - `core/infrastructure/backup.py:184` [Infrastructure] `self.logger.info(f"已清理过期备份：{filename}")`
  - `core/infrastructure/database.py:167` [Infrastructure] `logger.info("数据库结构检查完成（已确保所有表存在）。")`
  - `core/infrastructure/database.py:220` [Infrastructure] `logger.info(f"检测到新库结构已满足当前版本，SchemaVersion 已设为 {CURRENT_SCHEMA_VERSION}。")`
  - `core/infrastructure/database.py:345` [Infrastructure] `logger.info(f"数据库迁移完成：SchemaVersion {current} -> {to_version}")`
  - `core/algorithms/ortools_bottleneck.py:202` [Algorithm] `logger.info(`
  - `core/algorithms/greedy/scheduler.py:199` [Algorithm] `self.logger.info(f"排产开始：批次数={len(batches)} 工序数={len(sorted_ops)} 策略={sorter.get_`
  - `core/algorithms/greedy/scheduler.py:370` [Algorithm] `self.logger.info(f"排产结束：成功={scheduled_count}/{total_ops} 失败={failed_count} 耗时={d`
- **被调用者**（2 个）：`self.log`, `kwargs.get`

### `OperationLogger.warn()` [公开]
- 位置：第 161-163 行
- 参数：module, action
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self.log`, `warning`

### `OperationLogger.error()` [公开]
- 位置：第 165-174 行
- 参数：module, action, error_code, error_message
- 返回类型：无注解
- **调用者**（26 处）：
  - `core/services/system/maintenance/backup_task.py:71` [Service] `logger.error(f"自动备份失败：{e}")`
  - `core/services/system/maintenance/backup_task.py:76` [Service] `op_logger.error(`
  - `core/services/system/maintenance/cleanup_task.py:145` [Service] `logger.error(f"自动清理备份失败：{e}")`
  - `core/services/system/maintenance/cleanup_task.py:150` [Service] `op_logger.error(`
  - `core/services/system/maintenance/cleanup_task.py:229` [Service] `logger.error(f"自动清理操作日志失败：{e}")`
  - `core/services/system/maintenance/cleanup_task.py:234` [Service] `op_logger.error(`
  - `data/repositories/base_repo.py:165` [Repository] `self.logger.error("数据库错误：%s；SQL=%s；params=%s", e, sql, _safe_params(params))`
  - `data/repositories/schedule_history_repo.py:90` [Repository] `self.logger.error(f"分配排产版本号失败：{e}", exc_info=True)`
  - `core/infrastructure/backup.py:61` [Infrastructure] `self.logger.error(f"备份 integrity_check 未通过：{rows}")`
  - `core/infrastructure/backup.py:76` [Infrastructure] `self.logger.error(f"备份文件不存在：{backup_path}")`
  - `core/infrastructure/backup.py:81` [Infrastructure] `self.logger.error("数据库正在维护/恢复中，请稍后重试。")`
  - `core/infrastructure/backup.py:96` [Infrastructure] `self.logger.error(f"检测到维护锁文件，可能已有恢复任务在进行：{lock_path}")`
  - `core/infrastructure/backup.py:141` [Infrastructure] `self.logger.error(f"数据库恢复失败，已自动回滚到恢复前备份：{before_restore_path}")`
  - `core/infrastructure/database.py:306` [Infrastructure] `logger.error(f"数据库迁移前无法创建备份目录，已阻断迁移：{e}（dir={effective_backup_dir}）")`
  - `core/infrastructure/database.py:321` [Infrastructure] `logger.error(f"数据库迁移前备份失败，已阻断迁移：{e}（dir={effective_backup_dir}）")`
  - `core/infrastructure/database.py:374` [Infrastructure] `logger.error(f"数据库迁移失败，已从备份回滚：{backup_path}")`
  - `core/infrastructure/database.py:380` [Infrastructure] `logger.error(f"数据库迁移失败且回滚失败：{e}（backup={backup_path}）")`
  - `core/infrastructure/transaction.py:95` [Infrastructure] `logger.error(f"SAVEPOINT 回滚失败：{e2}")`
  - `core/infrastructure/transaction.py:99` [Infrastructure] `logger.error(f"SAVEPOINT 释放失败（回滚路径）：{e2}")`
  - `core/infrastructure/transaction.py:108` [Infrastructure] `logger.error(f"事务已回滚：{e}")`
  - `core/infrastructure/transaction.py:119` [Infrastructure] `logger.error(f"SAVEPOINT 回滚失败（提交路径）：{e2}")`
  - `core/infrastructure/transaction.py:123` [Infrastructure] `logger.error(f"SAVEPOINT 释放失败（提交路径-回滚后）：{e2}")`
  - `core/infrastructure/transaction.py:129` [Infrastructure] `logger.error(f"SAVEPOINT 释放失败（提交路径）：{e}")`
  - `core/infrastructure/transaction.py:140` [Infrastructure] `logger.error(f"事务提交失败：{e}")`
  - `core/infrastructure/migrations/v4.py:61` [Infrastructure] `logger.error(f"数据库迁移 v4：非法标识符，已跳过清洗（table={table!r} field={field!r}）")`
  - `core/infrastructure/migrations/v4.py:79` [Infrastructure] `logger.error(f"数据库迁移 v4：非法 pk_expr，已跳过清洗（table={table!r} field={field!r} pk_expr`
- **被调用者**（1 个）：`self.log`

## core/infrastructure/transaction.py（Infrastructure 层）

### `_depth_map()` [私有]
- 位置：第 15-20 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_inc_depth()` [私有]
- 位置：第 23-26 行
- 参数：conn
- 返回类型：Constant(value=None, kind=None)

### `_dec_depth()` [私有]
- 位置：第 29-36 行
- 参数：conn
- 返回类型：Constant(value=None, kind=None)

### `in_transaction_context()` [公开]
- 位置：第 39-48 行
- 参数：conn
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `core/infrastructure/logging.py:118` [Infrastructure] `auto_commit = (not pre_in_tx) and (not in_transaction_context(self.conn))`
- **被调用者**（4 个）：`int`, `get`, `id`, `_depth_map`

### `TransactionManager.__init__()` [私有]
- 位置：第 54-55 行
- 参数：db_connection
- 返回类型：无注解

### `TransactionManager.transaction()` [公开]
- 位置：第 58-144 行
- 参数：无
- 返回类型：无注解
- **调用者**（80 处）：
  - `web/routes/process_excel_routes.py:177` [Route] `with tx.transaction():`
  - `web/routes/scheduler_excel_calendar.py:310` [Route] `with tx.transaction():`
  - `core/services/common/excel_import_executor.py:129` [Service] `with tx.transaction():`
  - `core/services/equipment/machine_downtime_service.py:121` [Service] `with self.tx_manager.transaction():`
  - `core/services/equipment/machine_downtime_service.py:198` [Service] `with self.tx_manager.transaction():`
  - `core/services/equipment/machine_downtime_service.py:239` [Service] `with self.tx_manager.transaction():`
  - `core/services/equipment/machine_service.py:143` [Service] `with self.tx_manager.transaction():`
  - `core/services/equipment/machine_service.py:192` [Service] `with self.tx_manager.transaction():`
  - `core/services/equipment/machine_service.py:212` [Service] `with self.tx_manager.transaction():`
  - `core/services/material/batch_material_service.py:67` [Service] `with self.tx.transaction():`
  - `core/services/material/batch_material_service.py:96` [Service] `with self.tx.transaction():`
  - `core/services/material/batch_material_service.py:116` [Service] `with self.tx.transaction():`
  - `core/services/material/material_service.py:78` [Service] `with self.tx.transaction():`
  - `core/services/material/material_service.py:111` [Service] `with self.tx.transaction():`
  - `core/services/material/material_service.py:128` [Service] `with self.tx.transaction():`
  - `core/services/personnel/operator_machine_service.py:326` [Service] `with self.tx_manager.transaction():`
  - `core/services/personnel/operator_machine_service.py:339` [Service] `with self.tx_manager.transaction():`
  - `core/services/personnel/operator_machine_service.py:370` [Service] `with self.tx_manager.transaction():`
  - `core/services/personnel/operator_machine_service.py:422` [Service] `with self.tx_manager.transaction():`
  - `core/services/personnel/operator_service.py:91` [Service] `with self.tx_manager.transaction():`
  - `core/services/personnel/operator_service.py:124` [Service] `with self.tx_manager.transaction():`
  - `core/services/personnel/operator_service.py:158` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/external_group_service.py:164` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/op_type_service.py:102` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/op_type_service.py:126` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/op_type_service.py:146` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/part_operation_hours_excel_import_service.py:53` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/part_service.py:107` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/part_service.py:145` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/part_service.py:161` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/part_service.py:200` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/part_service.py:376` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/part_service.py:417` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/supplier_service.py:128` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/supplier_service.py:170` [Service] `with self.tx_manager.transaction():`
  - `core/services/process/supplier_service.py:188` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/batch_copy.py:33` [Service] `with svc.tx_manager.transaction():`
  - `core/services/scheduler/batch_service.py:229` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/batch_service.py:334` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/batch_service.py:355` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/batch_service.py:435` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/calendar_admin.py:168` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/calendar_admin.py:185` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/calendar_admin.py:274` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/calendar_admin.py:292` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_presets.py:147` [Service] `with svc.tx_manager.transaction():`
  - `core/services/scheduler/config_presets.py:184` [Service] `with svc.tx_manager.transaction():`
  - `core/services/scheduler/config_presets.py:198` [Service] `with svc.tx_manager.transaction():`
  - `core/services/scheduler/config_presets.py:261` [Service] `with svc.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:210` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:275` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:327` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:338` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:372` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:388` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:395` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:406` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:418` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:429` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:444` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:455` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:463` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:470` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/config_service.py:481` [Service] `with self.tx_manager.transaction():`
  - `core/services/scheduler/operation_edit_service.py:155` [Service] `with svc.tx_manager.transaction():`
  - `core/services/scheduler/operation_edit_service.py:214` [Service] `with svc.tx_manager.transaction():`
  - `core/services/scheduler/schedule_persistence.py:215` [Service] `with svc.tx_manager.transaction():`
  - `core/services/scheduler/schedule_service.py:316` [Service] `with self.tx_manager.transaction():`
  - `core/services/system/operation_log_service.py:42` [Service] `with self.tx.transaction():`
  - `core/services/system/operation_log_service.py:57` [Service] `with self.tx.transaction():`
  - `core/services/system/system_config_service.py:107` [Service] `with self.tx.transaction():`
  - `core/services/system/system_config_service.py:151` [Service] `with self.tx.transaction():`
  - `core/services/system/system_config_service.py:172` [Service] `with self.tx.transaction():`
  - `core/services/system/system_config_service.py:188` [Service] `with self.tx.transaction():`
  - `core/services/system/maintenance/backup_task.py:44` [Service] `with TransactionManager(conn).transaction():`
  - `core/services/system/maintenance/backup_task.py:74` [Service] `with TransactionManager(conn).transaction():`
  - `core/services/system/maintenance/cleanup_task.py:118` [Service] `with TransactionManager(conn).transaction():`
  - `core/services/system/maintenance/cleanup_task.py:148` [Service] `with TransactionManager(conn).transaction():`
  - `core/services/system/maintenance/cleanup_task.py:193` [Service] `with TransactionManager(conn).transaction():`
  - `core/services/system/maintenance/cleanup_task.py:232` [Service] `with TransactionManager(conn).transaction():`
- **被调用者**（13 个）：`_inc_depth`, `int`, `conn.execute`, `_dec_depth`, `logger.debug`, `get`, `id`, `logger.error`, `bool`, `conn.commit`, `_depth_map`, `getattr`, `conn.rollback`

### `transactional()` [公开]
- 位置：第 147-155 行
- 参数：func
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`wraps`, `transaction`, `func`

## core/models/machine_downtime.py（Model 层）

### `MachineDowntime.from_row()` [公开]
- 位置：第 33-51 行
- 参数：row
- 返回类型：Constant(value='MachineDowntime', kind=None)
- **调用者**（70 处）：
  - `core/services/scheduler/batch_service.py:254` [Service] `b = payload if isinstance(payload, Batch) else Batch.from_row(payload)`
  - `core/services/scheduler/calendar_admin.py:179` [Service] `c = calendar_payload if isinstance(calendar_payload, WorkCalendar) else WorkCale`
  - `core/services/scheduler/calendar_admin.py:282` [Service] `else OperatorCalendar.from_row(calendar_payload)`
  - `data/repositories/batch_material_repo.py:25` [Repository] `return BatchMaterial.from_row(row) if row else None`
  - `data/repositories/batch_material_repo.py:40` [Repository] `return [BatchMaterial.from_row(r) for r in rows]`
  - `data/repositories/batch_operation_repo.py:23` [Repository] `return BatchOperation.from_row(row) if row else None`
  - `data/repositories/batch_operation_repo.py:35` [Repository] `return BatchOperation.from_row(row) if row else None`
  - `data/repositories/batch_operation_repo.py:48` [Repository] `return [BatchOperation.from_row(r) for r in rows]`
  - `data/repositories/batch_operation_repo.py:61` [Repository] `return [BatchOperation.from_row(r) for r in rows]`
  - `data/repositories/batch_operation_repo.py:64` [Repository] `bo = op if isinstance(op, BatchOperation) else BatchOperation.from_row(op)`
  - `data/repositories/batch_repo.py:18` [Repository] `return Batch.from_row(row) if row else None`
  - `data/repositories/batch_repo.py:42` [Repository] `return [Batch.from_row(r) for r in rows]`
  - `data/repositories/batch_repo.py:48` [Repository] `b = batch if isinstance(batch, Batch) else Batch.from_row(batch)`
  - `data/repositories/calendar_repo.py:18` [Repository] `return WorkCalendar.from_row(row) if row else None`
  - `data/repositories/calendar_repo.py:24` [Repository] `return [WorkCalendar.from_row(r) for r in rows]`
  - `data/repositories/calendar_repo.py:31` [Repository] `return [WorkCalendar.from_row(r) for r in rows]`
  - `data/repositories/calendar_repo.py:34` [Repository] `c = calendar if isinstance(calendar, WorkCalendar) else WorkCalendar.from_row(ca`
  - `data/repositories/config_repo.py:18` [Repository] `return ScheduleConfig.from_row(row) if row else None`
  - `data/repositories/config_repo.py:32` [Repository] `return [ScheduleConfig.from_row(r) for r in rows]`
  - `data/repositories/external_group_repo.py:18` [Repository] `return ExternalGroup.from_row(row) if row else None`
  - `data/repositories/external_group_repo.py:25` [Repository] `return [ExternalGroup.from_row(r) for r in rows]`
  - `data/repositories/external_group_repo.py:28` [Repository] `g = group if isinstance(group, ExternalGroup) else ExternalGroup.from_row(group)`
  - `data/repositories/machine_downtime_repo.py:23` [Repository] `return MachineDowntime.from_row(row) if row else None`
  - `data/repositories/machine_downtime_repo.py:37` [Repository] `return [MachineDowntime.from_row(r) for r in rows]`
  - `data/repositories/machine_downtime_repo.py:55` [Repository] `return [MachineDowntime.from_row(r) for r in rows]`
  - `data/repositories/machine_downtime_repo.py:99` [Repository] `d = payload if isinstance(payload, MachineDowntime) else MachineDowntime.from_ro`
  - `data/repositories/machine_repo.py:18` [Repository] `return Machine.from_row(row) if row else None`
  - `data/repositories/machine_repo.py:42` [Repository] `return [Machine.from_row(r) for r in rows]`
  - `data/repositories/machine_repo.py:48` [Repository] `m = machine if isinstance(machine, Machine) else Machine.from_row(machine)`
  - `data/repositories/material_repo.py:18` [Repository] `return Material.from_row(row) if row else None`
  - `data/repositories/material_repo.py:33` [Repository] `return [Material.from_row(r) for r in rows]`
  - `data/repositories/material_repo.py:36` [Repository] `m = material if isinstance(material, Material) else Material.from_row(material)`
  - `data/repositories/operation_log_repo.py:18` [Repository] `return OperationLog.from_row(row) if row else None`
  - `data/repositories/operation_log_repo.py:52` [Repository] `return [OperationLog.from_row(r) for r in rows]`
  - `data/repositories/operator_calendar_repo.py:22` [Repository] `return OperatorCalendar.from_row(row) if row else None`
  - `data/repositories/operator_calendar_repo.py:34` [Repository] `return [OperatorCalendar.from_row(r) for r in rows]`
  - `data/repositories/operator_calendar_repo.py:44` [Repository] `return [OperatorCalendar.from_row(r) for r in rows]`
  - `data/repositories/operator_calendar_repo.py:47` [Repository] `c = calendar if isinstance(calendar, OperatorCalendar) else OperatorCalendar.fro`
  - `data/repositories/operator_machine_repo.py:18` [Repository] `return OperatorMachine.from_row(row) if row else None`
  - `data/repositories/operator_machine_repo.py:33` [Repository] `return [OperatorMachine.from_row(r) for r in rows]`
  - `data/repositories/operator_machine_repo.py:40` [Repository] `return [OperatorMachine.from_row(r) for r in rows]`
  - `data/repositories/operator_repo.py:18` [Repository] `return Operator.from_row(row) if row else None`
  - `data/repositories/operator_repo.py:30` [Repository] `return [Operator.from_row(r) for r in rows]`
  - `data/repositories/operator_repo.py:36` [Repository] `op = operator if isinstance(operator, Operator) else Operator.from_row(operator)`
  - `data/repositories/op_type_repo.py:18` [Repository] `return OpType.from_row(row) if row else None`
  - `data/repositories/op_type_repo.py:25` [Repository] `return OpType.from_row(row) if row else None`
  - `data/repositories/op_type_repo.py:37` [Repository] `return [OpType.from_row(r) for r in rows]`
  - `data/repositories/op_type_repo.py:40` [Repository] `ot = op_type if isinstance(op_type, OpType) else OpType.from_row(op_type)`
  - `data/repositories/part_operation_repo.py:18` [Repository] `return PartOperation.from_row(row) if row else None`
  - `data/repositories/part_operation_repo.py:31` [Repository] `return [PartOperation.from_row(r) for r in rows]`
  - `data/repositories/part_operation_repo.py:77` [Repository] `po = op if isinstance(op, PartOperation) else PartOperation.from_row(op)`
  - `data/repositories/part_repo.py:18` [Repository] `return Part.from_row(row) if row else None`
  - `data/repositories/part_repo.py:30` [Repository] `return [Part.from_row(r) for r in rows]`
  - `data/repositories/part_repo.py:36` [Repository] `p = part if isinstance(part, Part) else Part.from_row(part)`
  - `data/repositories/schedule_history_repo.py:20` [Repository] `return ScheduleHistory.from_row(row) if row else None`
  - `data/repositories/schedule_history_repo.py:27` [Repository] `return [ScheduleHistory.from_row(r) for r in rows]`
  - `data/repositories/schedule_history_repo.py:34` [Repository] `return ScheduleHistory.from_row(row) if row else None`
  - `data/repositories/schedule_repo.py:18` [Repository] `return Schedule.from_row(row) if row else None`
  - `data/repositories/schedule_repo.py:25` [Repository] `return [Schedule.from_row(r) for r in rows]`
  - `data/repositories/schedule_repo.py:60` [Repository] `return [Schedule.from_row(r) for r in rows]`
  - `data/repositories/schedule_repo.py:212` [Repository] `return [Schedule.from_row(r) for r in rows]`
  - `data/repositories/schedule_repo.py:215` [Repository] `s = schedule if isinstance(schedule, Schedule) else Schedule.from_row(schedule)`
  - `data/repositories/schedule_repo.py:229` [Repository] `s = item if isinstance(item, Schedule) else Schedule.from_row(item)`
  - `data/repositories/supplier_repo.py:18` [Repository] `return Supplier.from_row(row) if row else None`
  - `data/repositories/supplier_repo.py:34` [Repository] `return [Supplier.from_row(r) for r in rows]`
  - `data/repositories/supplier_repo.py:37` [Repository] `s = supplier if isinstance(supplier, Supplier) else Supplier.from_row(supplier)`
  - `data/repositories/system_config_repo.py:18` [Repository] `return SystemConfig.from_row(row) if row else None`
  - `data/repositories/system_config_repo.py:30` [Repository] `return [SystemConfig.from_row(r) for r in rows]`
  - `data/repositories/system_job_state_repo.py:18` [Repository] `return SystemJobState.from_row(row) if row else None`
  - `data/repositories/system_job_state_repo.py:22` [Repository] `return [SystemJobState.from_row(r) for r in rows]`
- **被调用者**（6 个）：`get`, `parse_int`, `cls`, `str`, `lower`, `strip`

### `MachineDowntime.to_dict()` [公开]
- 位置：第 53-68 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（59 处）：
  - `web/routes/equipment_pages.py:155` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:162` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:26` [Route] `items = [m.to_dict() for m in svc.list()]`
  - `web/routes/material.py:130` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:23` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:40` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:128` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:22` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:43` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:80` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:81` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:82` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:111` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:28` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/scheduler_batches.py:41` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:64` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:113` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:177` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:221` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/system_backup.py:39` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:35` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:42` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:52` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:142` [Route] `d = it.to_dict()`
  - `core/services/common/pandas_backend.py:64` [Service] `raw_rows = df.to_dict(orient="records")`
  - `core/services/equipment/machine_excel_import_service.py:95` [Service] `out = stats.to_dict()`
  - `core/services/material/material_service.py:81` [Service] `self.op_logger.info(module="material", action="create", target_type="material", `
  - `core/services/personnel/operator_excel_import_service.py:79` [Service] `out = stats.to_dict()`
  - `core/services/process/op_type_excel_import_service.py:85` [Service] `out = stats.to_dict()`
  - `core/services/process/part_operation_hours_excel_import_service.py:57` [Service] `return stats.to_dict(total_rows=len(preview_rows))`
  - `core/services/process/route_parser.py:55` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:75` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:76` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
  - `core/services/process/supplier_excel_import_service.py:108` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:101` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:255` [Service] `self.batch_repo.create(b.to_dict())`
  - `core/services/scheduler/calendar_admin.py:169` [Service] `self.upsert_no_tx(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:180` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:275` [Service] `self.upsert_operator_calendar_no_tx(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:284` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:209` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config_presets.py:20` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:29` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:37` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:128` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config_presets.py:183` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/gantt_contract.py:70` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:164` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:206` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_optimizer.py:147` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:160` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:207` [Service] `cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(`
  - `core/services/scheduler/schedule_optimizer_steps.py:96` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:121` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:198` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:223` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_summary.py:233` [Service] `"metrics": best_metrics.to_dict() if best_metrics is not None else None,`
- **被调用者**（1 个）：`as_dict`

## core/services/common/excel_audit.py（Service 层）

### `_calc_stats_from_preview()` [私有]
- 位置：第 8-28 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `log_excel_import()` [公开]
- 位置：第 31-91 行
- 参数：op_logger, module, target_type, filename, mode, preview_or_result, time_cost_ms, errors_sample, file_hash, target_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（24 处）：
  - `web/routes/equipment_excel_links.py:84` [Route] `log_excel_import(`
  - `web/routes/equipment_excel_links.py:184` [Route] `log_excel_import(`
  - `web/routes/equipment_excel_machines.py:205` [Route] `log_excel_import(`
  - `web/routes/equipment_excel_machines.py:294` [Route] `log_excel_import(`
  - `web/routes/excel_demo.py:128` [Route] `log_excel_import(`
  - `web/routes/excel_demo.py:213` [Route] `log_excel_import(`
  - `web/routes/personnel_excel_links.py:71` [Route] `log_excel_import(`
  - `web/routes/personnel_excel_links.py:172` [Route] `log_excel_import(`
  - `web/routes/personnel_excel_operators.py:88` [Route] `log_excel_import(`
  - `web/routes/personnel_excel_operators.py:178` [Route] `log_excel_import(`
  - `web/routes/personnel_excel_operator_calendar.py:146` [Route] `log_excel_import(`
  - `web/routes/personnel_excel_operator_calendar.py:288` [Route] `log_excel_import(`
  - `web/routes/process_excel_op_types.py:91` [Route] `log_excel_import(`
  - `web/routes/process_excel_op_types.py:193` [Route] `log_excel_import(`
  - `web/routes/process_excel_part_operation_hours.py:225` [Route] `log_excel_import(`
  - `web/routes/process_excel_part_operation_hours.py:319` [Route] `log_excel_import(`
  - `web/routes/process_excel_routes.py:83` [Route] `log_excel_import(`
  - `web/routes/process_excel_routes.py:214` [Route] `log_excel_import(`
  - `web/routes/process_excel_suppliers.py:125` [Route] `log_excel_import(`
  - `web/routes/process_excel_suppliers.py:239` [Route] `log_excel_import(`
  - `web/routes/scheduler_excel_batches.py:196` [Route] `log_excel_import(`
  - `web/routes/scheduler_excel_batches.py:296` [Route] `log_excel_import(`
  - `web/routes/scheduler_excel_calendar.py:167` [Route] `log_excel_import(`
  - `web/routes/scheduler_excel_calendar.py:346` [Route] `log_excel_import(`
- **被调用者**（6 个）：`isinstance`, `op_logger.info`, `str`, `detail.update`, `int`, `_calc_stats_from_preview`

### `log_excel_export()` [公开]
- 位置：第 94-125 行
- 参数：op_logger, module, target_type, template_or_export_type, filters, row_count, time_range, time_cost_ms, target_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（37 处）：
  - `web/routes/equipment_excel_links.py:207` [Route] `log_excel_export(`
  - `web/routes/equipment_excel_links.py:237` [Route] `log_excel_export(`
  - `web/routes/equipment_excel_links.py:277` [Route] `log_excel_export(`
  - `web/routes/equipment_excel_machines.py:317` [Route] `log_excel_export(`
  - `web/routes/equipment_excel_machines.py:347` [Route] `log_excel_export(`
  - `web/routes/equipment_excel_machines.py:386` [Route] `log_excel_export(`
  - `web/routes/excel_demo.py:239` [Route] `log_excel_export(`
  - `web/routes/excel_demo.py:269` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_links.py:195` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_links.py:225` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_links.py:265` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_operators.py:202` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_operators.py:232` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_operators.py:274` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_operator_calendar.py:308` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_operator_calendar.py:338` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_operator_calendar.py:389` [Route] `log_excel_export(`
  - `web/routes/process_excel_op_types.py:213` [Route] `log_excel_export(`
  - `web/routes/process_excel_op_types.py:244` [Route] `log_excel_export(`
  - `web/routes/process_excel_op_types.py:283` [Route] `log_excel_export(`
  - `web/routes/process_excel_part_operations.py:64` [Route] `log_excel_export(`
  - `web/routes/process_excel_part_operation_hours.py:339` [Route] `log_excel_export(`
  - `web/routes/process_excel_part_operation_hours.py:370` [Route] `log_excel_export(`
  - `web/routes/process_excel_part_operation_hours.py:409` [Route] `log_excel_export(`
  - `web/routes/process_excel_routes.py:241` [Route] `log_excel_export(`
  - `web/routes/process_excel_routes.py:271` [Route] `log_excel_export(`
  - `web/routes/process_excel_routes.py:311` [Route] `log_excel_export(`
  - `web/routes/process_excel_suppliers.py:259` [Route] `log_excel_export(`
  - `web/routes/process_excel_suppliers.py:289` [Route] `log_excel_export(`
  - `web/routes/process_excel_suppliers.py:327` [Route] `log_excel_export(`
  - `web/routes/scheduler_excel_batches.py:317` [Route] `log_excel_export(`
  - `web/routes/scheduler_excel_batches.py:347` [Route] `log_excel_export(`
  - `web/routes/scheduler_excel_batches.py:385` [Route] `log_excel_export(`
  - `web/routes/scheduler_excel_calendar.py:373` [Route] `log_excel_export(`
  - `web/routes/scheduler_excel_calendar.py:402` [Route] `log_excel_export(`
  - `web/routes/scheduler_excel_calendar.py:440` [Route] `log_excel_export(`
  - `web/routes/scheduler_week_plan.py:129` [Route] `log_excel_export(`
- **被调用者**（2 个）：`op_logger.info`, `int`

## core/services/common/excel_import_executor.py（Service 层）

### `ImportExecutionStats.to_dict()` [公开]
- 位置：第 20-27 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（59 处）：
  - `web/routes/equipment_pages.py:155` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:162` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:26` [Route] `items = [m.to_dict() for m in svc.list()]`
  - `web/routes/material.py:130` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:23` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:40` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:128` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:22` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:43` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:80` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:81` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:82` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:111` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:28` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/scheduler_batches.py:41` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:64` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:113` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:177` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:221` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/system_backup.py:39` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:35` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:42` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:52` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:142` [Route] `d = it.to_dict()`
  - `core/services/common/pandas_backend.py:64` [Service] `raw_rows = df.to_dict(orient="records")`
  - `core/services/equipment/machine_excel_import_service.py:95` [Service] `out = stats.to_dict()`
  - `core/services/material/material_service.py:81` [Service] `self.op_logger.info(module="material", action="create", target_type="material", `
  - `core/services/personnel/operator_excel_import_service.py:79` [Service] `out = stats.to_dict()`
  - `core/services/process/op_type_excel_import_service.py:85` [Service] `out = stats.to_dict()`
  - `core/services/process/part_operation_hours_excel_import_service.py:57` [Service] `return stats.to_dict(total_rows=len(preview_rows))`
  - `core/services/process/route_parser.py:55` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:75` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:76` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
  - `core/services/process/supplier_excel_import_service.py:108` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:101` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:255` [Service] `self.batch_repo.create(b.to_dict())`
  - `core/services/scheduler/calendar_admin.py:169` [Service] `self.upsert_no_tx(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:180` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:275` [Service] `self.upsert_operator_calendar_no_tx(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:284` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:209` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config_presets.py:20` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:29` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:37` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:128` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config_presets.py:183` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/gantt_contract.py:70` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:164` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:206` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_optimizer.py:147` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:160` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:207` [Service] `cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(`
  - `core/services/scheduler/schedule_optimizer_steps.py:96` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:121` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:198` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:223` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_summary.py:233` [Service] `"metrics": best_metrics.to_dict() if best_metrics is not None else None,`
- **被调用者**（2 个）：`int`, `list`

### `_append_error_sample()` [私有]
- 位置：第 30-41 行
- 参数：stats
- 返回类型：Constant(value=None, kind=None)

### `_should_skip_before_row_id()` [私有]
- 位置：第 44-63 行
- 参数：stats
- 返回类型：Name(id='bool', ctx=Load())

### `_should_skip_after_row_id()` [私有]
- 位置：第 66-76 行
- 参数：stats
- 返回类型：Name(id='bool', ctx=Load())

### `_apply_one_row()` [私有]
- 位置：第 79-104 行
- 参数：stats
- 返回类型：Constant(value=None, kind=None)

### `execute_preview_rows_transactional()` [公开]
- 位置：第 107-164 行
- 参数：conn
- 返回类型：Name(id='ImportExecutionStats', ctx=Load())
- **调用者**（6 处）：
  - `core/services/equipment/machine_excel_import_service.py:81` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/personnel/operator_excel_import_service.py:65` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/process/op_type_excel_import_service.py:70` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/process/supplier_excel_import_service.py:93` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/scheduler/batch_excel_import.py:90` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/scheduler/calendar_service.py:198` [Service] `stats = execute_preview_rows_transactional(`
- **被调用者**（12 个）：`ImportExecutionStats`, `TransactionManager`, `tx.transaction`, `replace_existing_no_tx`, `existing_row_ids.clear`, `_should_skip_before_row_id`, `strip`, `_should_skip_after_row_id`, `_apply_one_row`, `_append_error_sample`, `str`, `row_id_getter`

## core/services/common/excel_service.py（Service 层）

### `ExcelService.__init__()` [私有]
- 位置：第 55-59 行
- 参数：backend, logger, op_logger, template_dir
- 返回类型：无注解

### `ExcelService.read_rows()` [公开]
- 位置：第 61-62 行
- 参数：file_path, sheet
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`read`

### `ExcelService.write_rows()` [公开]
- 位置：第 64-66 行
- 参数：rows, file_path, sheet
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`write`

### `ExcelService.preview_import()` [公开]
- 位置：第 68-161 行
- 参数：rows, id_column, existing_data, validators, mode
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（20 处）：
  - `web/routes/equipment_excel_machines.py:196` [Route] `preview_rows = svc.preview_import(`
  - `web/routes/equipment_excel_machines.py:258` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/excel_demo.py:119` [Route] `preview_rows = svc.preview_import(`
  - `web/routes/excel_demo.py:172` [Route] `preview_rows = svc.preview_import(`
  - `web/routes/personnel_excel_operators.py:79` [Route] `preview_rows = svc.preview_import(`
  - `web/routes/personnel_excel_operators.py:136` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/personnel_excel_operator_calendar.py:136` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/personnel_excel_operator_calendar.py:247` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/process_excel_op_types.py:82` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/process_excel_op_types.py:151` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/process_excel_part_operation_hours.py:215` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/process_excel_part_operation_hours.py:276` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/process_excel_routes.py:74` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/process_excel_routes.py:143` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/process_excel_suppliers.py:116` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/process_excel_suppliers.py:197` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/scheduler_excel_batches.py:186` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/scheduler_excel_batches.py:261` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/scheduler_excel_calendar.py:158` [Route] `preview_rows = excel_svc.preview_import(`
  - `web/routes/scheduler_excel_calendar.py:276` [Route] `preview_rows = excel_svc.preview_import(`
- **被调用者**（9 个）：`enumerate`, `ValidationError`, `row_dict.get`, `strip`, `preview.append`, `ImportPreviewRow`, `str`, `validator`, `self._calc_changes`

### `ExcelService._normalize_for_compare()` [私有]
- 位置：第 164-192 行
- 参数：value
- 返回类型：Name(id='Any', ctx=Load())

### `ExcelService._calc_changes()` [私有]
- 位置：第 194-224 行
- 参数：existing, new_data
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

## core/services/common/excel_templates.py（Service 层）

### `_write_xlsx()` [私有]
- 位置：第 11-25 行
- 参数：path, headers, sample_rows
- 返回类型：Constant(value=None, kind=None)

### `get_default_templates()` [公开]
- 位置：第 28-95 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）

### `ensure_excel_templates()` [公开]
- 位置：第 98-119 行
- 参数：template_dir
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`abspath`, `os.makedirs`, `get_default_templates`, `join`, `exists`, `_write_xlsx`, `created.append`, `skipped.append`, `t.get`

## core/services/common/excel_validators.py（Service 层）

### `_normalize_batch_priority()` [私有]
- 位置：第 13-21 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_ready_status()` [私有]
- 位置：第 24-32 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_operator_calendar_day_type()` [私有]
- 位置：第 35-43 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_yesno()` [私有]
- 位置：第 46-53 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_batch_date_cell()` [私有]
- 位置：第 56-82 行
- 参数：value, field_label
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `get_batch_row_validate_and_normalize()` [公开]
- 位置：第 85-134 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='Callable', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/routes/scheduler_excel_batches.py:183` [Route] `validate_row = get_batch_row_validate_and_normalize(g.db, parts_cache=parts, inp`
  - `web/routes/scheduler_excel_batches.py:258` [Route] `validate_row = get_batch_row_validate_and_normalize(g.db, parts_cache=parts, inp`
- **被调用者**（13 个）：`isinstance`, `strip`, `target.get`, `_normalize_batch_priority`, `_normalize_ready_status`, `_normalize_batch_date_cell`, `ready_res.get`, `due_res.get`, `dict`, `int`, `str`, `list`, `PartRepository`

### `get_operator_calendar_row_validate_and_normalize()` [公开]
- 位置：第 137-229 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='Callable', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/routes/personnel_excel_operator_calendar.py:129` [Route] `validate_row = get_operator_calendar_row_validate_and_normalize(`
  - `web/routes/personnel_excel_operator_calendar.py:240` [Route] `validate_row = get_operator_calendar_row_validate_and_normalize(`
- **被调用者**（14 个）：`OperatorRepository`, `float`, `strip`, `_normalize_operator_calendar_day_type`, `target.get`, `_normalize_yesno`, `dict`, `repo.exists`, `normalize_date`, `normalize_hhmm`, `str`, `datetime.strptime`, `total_seconds`, `timedelta`

## core/services/common/openpyxl_backend.py（Service 层）

### `_normalize_header_cell()` [私有]
- 位置：第 12-15 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_cell_value()` [私有]
- 位置：第 18-22 行
- 参数：value
- 返回类型：Name(id='Any', ctx=Load())

### `_is_blank_cell()` [私有]
- 位置：第 25-31 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())

### `_is_blank_row()` [私有]
- 位置：第 34-37 行
- 参数：raw
- 返回类型：Name(id='bool', ctx=Load())

### `_row_to_item()` [私有]
- 位置：第 40-47 行
- 参数：headers, raw
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_convert_worksheet_rows()` [私有]
- 位置：第 50-63 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `OpenpyxlBackend.read()` [公开]
- 位置：第 69-91 行
- 参数：file_path, sheet
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（7 处）：
  - `web/routes/excel_demo.py:76` [Route] `data = file.read()`
  - `web/routes/excel_utils.py:94` [Route] `- 统一走 backend.read(file_path)，以支持可选 pandas 后端`
  - `web/routes/excel_utils.py:96` [Route] `data = file_storage.read()`
  - `web/routes/excel_utils.py:105` [Route] `return backend.read(tmp_path)`
  - `web/routes/scheduler_config.py:81` [Route] `manual_text = f.read()`
  - `core/services/common/excel_service.py:62` [Service] `return self.backend.read(file_path, sheet=sheet)`
  - `core/infrastructure/database.py:150` [Infrastructure] `sql = f.read()`
- **被调用者**（6 个）：`openpyxl.load_workbook`, `list`, `_convert_worksheet_rows`, `ws.iter_rows`, `AppError`, `wb.close`

### `OpenpyxlBackend.write()` [公开]
- 位置：第 93-126 行
- 参数：rows, file_path, sheet
- 返回类型：Constant(value=None, kind=None)
- **调用者**（3 处）：
  - `web/routes/excel_utils.py:103` [Route] `f.write(data)`
  - `core/services/common/excel_service.py:65` [Service] `self.backend.write(rows, file_path, sheet=sheet)`
  - `core/infrastructure/backup.py:92` [Infrastructure] `os.write(lock_fd, f"pid={os.getpid()} ts={datetime.now().isoformat()}".encode("u`
- **被调用者**（10 个）：`os.makedirs`, `openpyxl.Workbook`, `list`, `ws.append`, `wb.save`, `keys`, `AppError`, `dirname`, `wb.close`, `r.get`

## core/services/common/pandas_backend.py（Service 层）

### `_normalize_header_key()` [私有]
- 位置：第 11-14 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_cell_value()` [私有]
- 位置：第 17-21 行
- 参数：value
- 返回类型：Name(id='Any', ctx=Load())

### `_is_blank_value()` [私有]
- 位置：第 24-29 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())

### `_normalize_record()` [私有]
- 位置：第 32-41 行
- 参数：record
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_is_blank_item()` [私有]
- 位置：第 44-47 行
- 参数：item
- 返回类型：Name(id='bool', ctx=Load())

### `PandasBackend.read()` [公开]
- 位置：第 57-82 行
- 参数：file_path, sheet
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（7 处）：
  - `web/routes/excel_demo.py:76` [Route] `data = file.read()`
  - `web/routes/excel_utils.py:94` [Route] `- 统一走 backend.read(file_path)，以支持可选 pandas 后端`
  - `web/routes/excel_utils.py:96` [Route] `data = file_storage.read()`
  - `web/routes/excel_utils.py:105` [Route] `return backend.read(tmp_path)`
  - `web/routes/scheduler_config.py:81` [Route] `manual_text = f.read()`
  - `core/services/common/excel_service.py:62` [Service] `return self.backend.read(file_path, sheet=sheet)`
  - `core/infrastructure/database.py:150` [Infrastructure] `sql = f.read()`
- **被调用者**（8 个）：`pd.read_excel`, `df.where`, `df.to_dict`, `pd.notnull`, `_normalize_record`, `_is_blank_item`, `result.append`, `AppError`

### `PandasBackend.write()` [公开]
- 位置：第 84-114 行
- 参数：rows, file_path, sheet
- 返回类型：Constant(value=None, kind=None)
- **调用者**（3 处）：
  - `web/routes/excel_utils.py:103` [Route] `f.write(data)`
  - `core/services/common/excel_service.py:65` [Service] `self.backend.write(rows, file_path, sheet=sheet)`
  - `core/infrastructure/backup.py:92` [Infrastructure] `os.write(lock_fd, f"pid={os.getpid()} ts={datetime.now().isoformat()}".encode("u`
- **被调用者**（9 个）：`os.makedirs`, `list`, `pd.DataFrame`, `keys`, `pd.ExcelWriter`, `df.to_excel`, `AppError`, `dirname`, `to_excel`

## core/services/common/tabular_backend.py（Service 层）

### `TabularBackend.read()` [公开]
- 位置：第 15-16 行
- 参数：file_path, sheet
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（7 处）：
  - `web/routes/excel_demo.py:76` [Route] `data = file.read()`
  - `web/routes/excel_utils.py:94` [Route] `- 统一走 backend.read(file_path)，以支持可选 pandas 后端`
  - `web/routes/excel_utils.py:96` [Route] `data = file_storage.read()`
  - `web/routes/excel_utils.py:105` [Route] `return backend.read(tmp_path)`
  - `web/routes/scheduler_config.py:81` [Route] `manual_text = f.read()`
  - `core/services/common/excel_service.py:62` [Service] `return self.backend.read(file_path, sheet=sheet)`
  - `core/infrastructure/database.py:150` [Infrastructure] `sql = f.read()`

### `TabularBackend.write()` [公开]
- 位置：第 19-20 行
- 参数：rows, file_path, sheet
- 返回类型：Constant(value=None, kind=None)
- **调用者**（3 处）：
  - `web/routes/excel_utils.py:103` [Route] `f.write(data)`
  - `core/services/common/excel_service.py:65` [Service] `self.backend.write(rows, file_path, sheet=sheet)`
  - `core/infrastructure/backup.py:92` [Infrastructure] `os.write(lock_fd, f"pid={os.getpid()} ts={datetime.now().isoformat()}".encode("u`

## core/services/equipment/machine_downtime_service.py（Service 层）

### `MachineDowntimeService.__init__()` [私有]
- 位置：第 27-33 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `MachineDowntimeService._normalize_text()` [私有]
- 位置：第 39-40 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `MachineDowntimeService._parse_datetime()` [私有]
- 位置：第 43-58 行
- 参数：value, field
- 返回类型：Name(id='datetime', ctx=Load())

### `MachineDowntimeService._to_db_datetime()` [私有]
- 位置：第 61-62 行
- 参数：dt
- 返回类型：Name(id='str', ctx=Load())

### `MachineDowntimeService._ensure_machine_exists()` [私有]
- 位置：第 64-66 行
- 参数：machine_id
- 返回类型：Constant(value=None, kind=None)

### `MachineDowntimeService.list_by_machine()` [公开]
- 位置：第 71-76 行
- 参数：machine_id, include_cancelled
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/equipment_pages.py:114` [Route] `links = link_svc.list_by_machine(machine_id)`
  - `web/routes/equipment_pages.py:115` [Route] `downtimes = dt_svc.list_by_machine(machine_id, include_cancelled=False)`
  - `core/services/personnel/operator_machine_service.py:300` [Service] `return self.repo.list_by_machine(mc_id)`
- **被调用者**（3 个）：`self._normalize_text`, `self._ensure_machine_exists`, `ValidationError`

### `MachineDowntimeService.get()` [公开]
- 位置：第 78-86 行
- 参数：downtime_id
- 返回类型：Name(id='MachineDowntime', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`int`, `BusinessError`, `ValidationError`

### `MachineDowntimeService.create()` [公开]
- 位置：第 91-134 行
- 参数：machine_id, start_time, end_time, reason_code, reason_detail
- 返回类型：Name(id='MachineDowntime', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`self._normalize_text`, `self._ensure_machine_exists`, `self._parse_datetime`, `self._to_db_datetime`, `has_overlap`, `ValidationError`, `BusinessError`, `transaction`

### `MachineDowntimeService.create_by_scope()` [公开]
- 位置：第 136-226 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/equipment_downtimes.py:47` [Route] `res = svc.create_by_scope(`
- **被调用者**（15 个）：`self._parse_datetime`, `self._to_db_datetime`, `self._normalize_text`, `strip`, `ValidationError`, `self._ensure_machine_exists`, `BusinessError`, `transaction`, `len`, `list`, `has_overlap`, `create`, `skipped_overlap.append`, `created_ids.append`, `int`

### `MachineDowntimeService.cancel()` [公开]
- 位置：第 228-240 行
- 参数：downtime_id, machine_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/equipment_downtimes.py:90` [Route] `svc.cancel(downtime_id=downtime_id, machine_id=machine_id)`
- **被调用者**（6 个）：`self.get`, `self._normalize_text`, `strip`, `transaction`, `BusinessError`, `int`

## core/services/material/batch_material_service.py（Service 层）

### `BatchMaterialService.__init__()` [私有]
- 位置：第 14-21 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `BatchMaterialService._norm_text()` [私有]
- 位置：第 24-28 行
- 参数：v
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `BatchMaterialService._norm_float_required()` [私有]
- 位置：第 31-41 行
- 参数：v, field
- 返回类型：Name(id='float', ctx=Load())

### `BatchMaterialService.list_for_batch()` [公开]
- 位置：第 43-47 行
- 参数：batch_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/material.py:120` [Route] `req_rows = BatchMaterialService(g.db, op_logger=getattr(g, "op_logger", None)).l`
- **被调用者**（3 个）：`self._norm_text`, `list_with_material_details_by_batch`, `ValidationError`

### `BatchMaterialService.add_requirement()` [公开]
- 位置：第 49-77 行
- 参数：batch_id, material_id, required_qty, available_qty
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/material.py:141` [Route] `svc.add_requirement(`
- **被调用者**（10 个）：`self._norm_text`, `exists`, `self._norm_float_required`, `ValidationError`, `get`, `BusinessError`, `transaction`, `add`, `self._recalc_and_sync_batch_ready`, `info`

### `BatchMaterialService.update_requirement()` [公开]
- 位置：第 79-106 行
- 参数：bm_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/material.py:163` [Route] `svc.update_requirement(`
- **被调用者**（11 个）：`get`, `int`, `BusinessError`, `self._norm_float_required`, `transaction`, `update_qty`, `self._recalc_and_sync_batch_ready`, `strip`, `ValidationError`, `info`, `str`

### `BatchMaterialService.delete_requirement()` [公开]
- 位置：第 108-126 行
- 参数：bm_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/material.py:184` [Route] `svc.delete_requirement(bm_id)`
- **被调用者**（9 个）：`get`, `int`, `transaction`, `delete`, `self._recalc_and_sync_batch_ready`, `strip`, `ValidationError`, `info`, `str`

### `BatchMaterialService._calc_batch_ready()` [私有]
- 位置：第 131-154 行
- 参数：batch_id
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `BatchMaterialService._recalc_and_sync_batch_ready()` [私有]
- 位置：第 156-163 行
- 参数：batch_id
- 返回类型：Constant(value=None, kind=None)

## core/services/personnel/operator_excel_import_service.py（Service 层）

### `OperatorExcelImportService.__init__()` [私有]
- 位置：第 22-27 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `OperatorExcelImportService.apply_preview_rows()` [公开]
- 位置：第 29-81 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `web/routes/equipment_excel_machines.py:287` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/excel_demo.py:206` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/personnel_excel_operators.py:171` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_op_types.py:186` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_part_operation_hours.py:312` [Route] `stats = import_svc.apply_preview_rows(preview_rows)`
  - `web/routes/process_excel_suppliers.py:232` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
- **被调用者**（15 个）：`list`, `set`, `execute_preview_rows_transactional`, `stats.to_dict`, `len`, `ensure_replace_allowed`, `delete_all`, `strip`, `data.get`, `getattr`, `ValidationError`, `update`, `create`, `str`, `get`

## core/services/personnel/operator_machine_service.py（Service 层）

### `OperatorMachineService.__init__()` [私有]
- 位置：第 20-28 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `OperatorMachineService._normalize_text()` [私有]
- 位置：第 32-33 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._normalize_skill_level_optional()` [私有]
- 位置：第 36-58 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._normalize_yes_no_optional()` [私有]
- 位置：第 61-73 行
- 参数：value, field
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._ensure_operator_exists()` [私有]
- 位置：第 75-77 行
- 参数：operator_id
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._ensure_machine_exists()` [私有]
- 位置：第 79-81 行
- 参数：machine_id
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._detect_optional_columns()` [私有]
- 位置：第 84-87 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._detect_optional_columns_from_preview()` [私有]
- 位置：第 90-93 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._build_existing_link_map()` [私有]
- 位置：第 95-107 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `OperatorMachineService._validate_required_ids_for_preview_row()` [私有]
- 位置：第 109-120 行
- 参数：row, row_num
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._check_duplicate_key_in_file()` [私有]
- 位置：第 123-132 行
- 参数：key
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._check_fk_exists()` [私有]
- 位置：第 134-149 行
- 参数：op_id, mc_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._parse_skill_optional_for_preview()` [私有]
- 位置：第 151-162 行
- 参数：row, row_num
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._parse_primary_optional_for_preview()` [私有]
- 位置：第 164-175 行
- 参数：row, row_num
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._build_overwrite_preview_for_existing()` [私有]
- 位置：第 177-189 行
- 参数：无
- 返回类型：Name(id='ImportPreviewRow', ctx=Load())

### `OperatorMachineService._decide_preview_row()` [私有]
- 位置：第 191-201 行
- 参数：无
- 返回类型：Name(id='ImportPreviewRow', ctx=Load())

### `OperatorMachineService._preview_one_row()` [私有]
- 位置：第 203-225 行
- 参数：无
- 返回类型：Name(id='ImportPreviewRow', ctx=Load())

### `OperatorMachineService._is_primary_yes()` [私有]
- 位置：第 228-230 行
- 参数：data
- 返回类型：Name(id='bool', ctx=Load())

### `OperatorMachineService._collect_dup_primary_yes_operators()` [私有]
- 位置：第 232-242 行
- 参数：preview
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Index(valu

### `OperatorMachineService._mark_dup_primary_yes()` [私有]
- 位置：第 245-255 行
- 参数：preview, dup_ops
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._enforce_primary_unique_in_file()` [私有]
- 位置：第 257-260 行
- 参数：preview
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._resolve_write_values()` [私有]
- 位置：第 262-285 行
- 参数：pr
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService.list_by_operator()` [公开]
- 位置：第 290-294 行
- 参数：operator_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/personnel_pages.py:92` [Route] `links = link_svc.list_by_operator(operator_id)`
  - `core/services/scheduler/calendar_admin.py:205` [Service] `return self.operator_calendar_repo.list_by_operator(op_id)`
- **被调用者**（2 个）：`self._normalize_text`, `ValidationError`

### `OperatorMachineService.list_by_machine()` [公开]
- 位置：第 296-300 行
- 参数：machine_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/equipment_pages.py:114` [Route] `links = link_svc.list_by_machine(machine_id)`
  - `web/routes/equipment_pages.py:115` [Route] `downtimes = dt_svc.list_by_machine(machine_id, include_cancelled=False)`
  - `core/services/equipment/machine_downtime_service.py:76` [Service] `return self.repo.list_by_machine(mc_id, include_cancelled=include_cancelled)`
- **被调用者**（2 个）：`self._normalize_text`, `ValidationError`

### `OperatorMachineService.add_link()` [公开]
- 位置：第 302-330 行
- 参数：operator_id, machine_id, skill_level, is_primary
- 返回类型：Name(id='OperatorMachine', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:267` [Route] `svc.add_link(operator_id=operator_id, machine_id=machine_id)`
  - `web/routes/personnel_pages.py:234` [Route] `svc.add_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（11 个）：`self._normalize_text`, `self._ensure_operator_exists`, `self._ensure_machine_exists`, `exists`, `ValidationError`, `BusinessError`, `self._normalize_skill_level_optional`, `self._normalize_yes_no_optional`, `transaction`, `add`, `clear_primary_for_operator`

### `OperatorMachineService.remove_link()` [公开]
- 位置：第 332-340 行
- 参数：operator_id, machine_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:287` [Route] `svc.remove_link(operator_id=operator_id, machine_id=machine_id)`
  - `web/routes/personnel_pages.py:255` [Route] `svc.remove_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（4 个）：`self._normalize_text`, `ValidationError`, `transaction`, `remove`

### `OperatorMachineService.update_link_fields()` [公开]
- 位置：第 342-373 行
- 参数：operator_id, machine_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:278` [Route] `svc.update_link_fields(operator_id=operator_id, machine_id=machine_id, skill_lev`
  - `web/routes/personnel_pages.py:246` [Route] `svc.update_link_fields(operator_id=operator_id, machine_id=machine_id, skill_lev`
- **被调用者**（9 个）：`self._normalize_text`, `ValidationError`, `exists`, `BusinessError`, `self._normalize_skill_level_optional`, `self._normalize_yes_no_optional`, `transaction`, `update_fields`, `clear_primary_for_operator`

### `OperatorMachineService.preview_import_links()` [公开]
- 位置：第 378-410 行
- 参数：rows, mode
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/equipment_excel_links.py:81` [Route] `preview_rows = link_svc.preview_import_links(rows=normalized_rows, mode=mode)`
  - `web/routes/equipment_excel_links.py:141` [Route] `preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)`
  - `web/routes/personnel_excel_links.py:68` [Route] `preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)`
  - `web/routes/personnel_excel_links.py:129` [Route] `preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)`
- **被调用者**（7 个）：`self._detect_optional_columns`, `self._build_existing_link_map`, `set`, `enumerate`, `self._preview_one_row`, `preview.append`, `self._enforce_primary_unique_in_file`

### `OperatorMachineService.apply_import_links()` [公开]
- 位置：第 412-487 行
- 参数：preview_rows, mode
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/equipment_excel_links.py:181` [Route] `stats = link_svc.apply_import_links(preview_rows=preview_rows, mode=mode)`
  - `web/routes/personnel_excel_links.py:169` [Route] `stats = link_svc.apply_import_links(preview_rows=preview_rows, mode=mode)`
- **被调用者**（15 个）：`self._detect_optional_columns_from_preview`, `self._build_existing_link_map`, `transaction`, `len`, `delete_all`, `strip`, `existing_map.get`, `self._resolve_write_values`, `exists`, `update_fields`, `add`, `errors_sample.append`, `str`, `clear_primary_for_operator`, `get`

## core/services/process/deletion_validator.py（Service 层）

### `DeletionValidator._norm_source()` [私有]
- 位置：第 44-51 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `DeletionValidator._norm_status()` [私有]
- 位置：第 54-65 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `DeletionValidator.can_delete()` [公开]
- 位置：第 67-105 行
- 参数：operations, to_delete
- 返回类型：Name(id='DeletionCheckResult', ctx=Load())
- **调用者**（1 处）：
  - `core/services/process/part_service.py:413` [Service] `check = self.deletion_validator.can_delete(del_ops, to_delete=to_delete)`
- **被调用者**（11 个）：`set`, `self._filter_active_ops`, `self._build_op_map`, `self._validate_delete_targets`, `self._check_remaining_sanity`, `internal_ops.sort`, `self._find_external_gap`, `DeletionCheckResult`, `len`, `int`, `self._norm_source`

### `DeletionValidator._filter_active_ops()` [私有]
- 位置：第 107-112 行
- 参数：operations
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `DeletionValidator._build_op_map()` [私有]
- 位置：第 115-122 行
- 参数：active_ops
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `DeletionValidator._validate_delete_targets()` [私有]
- 位置：第 124-141 行
- 参数：op_map, to_delete_set
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `DeletionValidator._check_remaining_sanity()` [私有]
- 位置：第 144-151 行
- 参数：remaining
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `DeletionValidator._find_external_gap()` [私有]
- 位置：第 153-165 行
- 参数：remaining, internal_ops
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `DeletionValidator._find_op()` [私有]
- 位置：第 167-171 行
- 参数：operations, seq
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `DeletionValidator.get_deletable_external_ops()` [公开]
- 位置：第 173-182 行
- 参数：operations
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`self._filter_active_ops`, `self.can_delete`, `deletable.append`, `self._norm_source`

### `DeletionValidator.get_deletion_groups()` [公开]
- 位置：第 184-217 行
- 参数：operations
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `core/services/process/part_service.py:404` [Service] `deletable_groups = self.deletion_validator.get_deletion_groups(del_ops)  # List[`
  - `core/services/process/part_service.py:427` [Service] `规则：根据 DeletionValidator.get_deletion_groups() 返回的首/尾外部工序组匹配 group_id。`
  - `core/services/process/part_service.py:437` [Service] `deletable_groups = self.deletion_validator.get_deletion_groups(del_ops)  # List[`
- **被调用者**（7 个）：`sorted`, `reversed`, `groups.append`, `self._norm_source`, `head_group.append`, `tail_group.insert`, `self._norm_status`

## core/services/process/external_group_service.py（Service 层）

### `ExternalGroupService.__init__()` [私有]
- 位置：第 16-22 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ExternalGroupService._normalize_text()` [私有]
- 位置：第 25-26 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ExternalGroupService._normalize_float()` [私有]
- 位置：第 29-35 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ExternalGroupService._get_group_or_raise()` [私有]
- 位置：第 37-41 行
- 参数：group_id
- 返回类型：无注解

### `ExternalGroupService.list_by_part()` [公开]
- 位置：第 43-44 行
- 参数：part_no
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（8 处）：
  - `core/services/process/part_service.py:69` [Service] `ops = self.op_repo.list_by_part(part_no, include_deleted=False)`
  - `core/services/process/part_service.py:340` [Service] `ops = self.op_repo.list_by_part(p.part_no, include_deleted=True)`
  - `core/services/process/part_service.py:341` [Service] `groups = self.group_repo.list_by_part(p.part_no)`
  - `core/services/process/part_service.py:392` [Service] `ops = self.op_repo.list_by_part(pn, include_deleted=False)`
  - `core/services/process/part_service.py:432` [Service] `ops = self.op_repo.list_by_part(pn, include_deleted=False)`
  - `core/services/process/part_service.py:444` [Service] `for group in self.group_repo.list_by_part(pn):`
  - `core/services/scheduler/batch_service.py:122` [Service] `template_ops = self.part_op_repo.list_by_part(part_no, include_deleted=False)`
  - `core/services/scheduler/batch_service.py:136` [Service] `template_ops = self.part_op_repo.list_by_part(part_no, include_deleted=False)`

### `ExternalGroupService._list_external_ops_in_group()` [私有]
- 位置：第 46-55 行
- 参数：part_no, group_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ExternalGroupService._update_group_common_fields()` [私有]
- 位置：第 57-73 行
- 参数：group_id
- 返回类型：Constant(value=None, kind=None)

### `ExternalGroupService._apply_merged_mode()` [私有]
- 位置：第 75-101 行
- 参数：group_id
- 返回类型：Constant(value=None, kind=None)

### `ExternalGroupService._apply_separate_mode()` [私有]
- 位置：第 103-132 行
- 参数：group_id
- 返回类型：Constant(value=None, kind=None)

### `ExternalGroupService.set_merge_mode()` [公开]
- 位置：第 134-188 行
- 参数：group_id, merge_mode, total_days, per_op_days, supplier_id, remark
- 返回类型：Name(id='ExternalGroup', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/process_parts.py:208` [Route] `svc.set_merge_mode(`
- **被调用者**（10 个）：`self._normalize_text`, `lower`, `self._get_group_or_raise`, `self._list_external_ops_in_group`, `ValidationError`, `int`, `transaction`, `strip`, `self._apply_merged_mode`, `self._apply_separate_mode`

## core/services/process/part_operation_hours_excel_import_service.py（Service 层）

### `_ImportStats.add_error()` [公开]
- 位置：第 21-24 行
- 参数：row_num, message
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`append`, `len`

### `_ImportStats.to_dict()` [公开]
- 位置：第 26-34 行
- 参数：total_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（58 处）：
  - `web/routes/equipment_pages.py:155` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:162` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:26` [Route] `items = [m.to_dict() for m in svc.list()]`
  - `web/routes/material.py:130` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:23` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:40` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:128` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:22` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:43` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:80` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:81` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:82` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:111` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:28` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/scheduler_batches.py:41` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:64` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:113` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:177` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:221` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/system_backup.py:39` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:35` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:42` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:52` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:142` [Route] `d = it.to_dict()`
  - `core/services/common/pandas_backend.py:64` [Service] `raw_rows = df.to_dict(orient="records")`
  - `core/services/equipment/machine_excel_import_service.py:95` [Service] `out = stats.to_dict()`
  - `core/services/material/material_service.py:81` [Service] `self.op_logger.info(module="material", action="create", target_type="material", `
  - `core/services/personnel/operator_excel_import_service.py:79` [Service] `out = stats.to_dict()`
  - `core/services/process/op_type_excel_import_service.py:85` [Service] `out = stats.to_dict()`
  - `core/services/process/route_parser.py:55` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:75` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:76` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
  - `core/services/process/supplier_excel_import_service.py:108` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:101` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:255` [Service] `self.batch_repo.create(b.to_dict())`
  - `core/services/scheduler/calendar_admin.py:169` [Service] `self.upsert_no_tx(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:180` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:275` [Service] `self.upsert_operator_calendar_no_tx(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:284` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:209` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config_presets.py:20` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:29` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:37` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:128` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config_presets.py:183` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/gantt_contract.py:70` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:164` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:206` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_optimizer.py:147` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:160` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:207` [Service] `cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(`
  - `core/services/scheduler/schedule_optimizer_steps.py:96` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:121` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:198` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:223` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_summary.py:233` [Service] `"metrics": best_metrics.to_dict() if best_metrics is not None else None,`
- **被调用者**（1 个）：`list`

### `PartOperationHoursExcelImportService.__init__()` [私有]
- 位置：第 40-45 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `PartOperationHoursExcelImportService.apply_preview_rows()` [公开]
- 位置：第 47-57 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `web/routes/equipment_excel_machines.py:287` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/excel_demo.py:206` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/personnel_excel_operators.py:171` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_op_types.py:186` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_part_operation_hours.py:312` [Route] `stats = import_svc.apply_preview_rows(preview_rows)`
  - `web/routes/process_excel_suppliers.py:232` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
- **被调用者**（5 个）：`_ImportStats`, `stats.to_dict`, `transaction`, `self._apply_one`, `len`

### `PartOperationHoursExcelImportService._apply_one()` [私有]
- 位置：第 59-79 行
- 参数：pr, stats
- 返回类型：Constant(value=None, kind=None)

### `PartOperationHoursExcelImportService._apply_non_write_row()` [私有]
- 位置：第 82-92 行
- 参数：pr, stats
- 返回类型：Constant(value=None, kind=None)

### `PartOperationHoursExcelImportService._parse_write_row()` [私有]
- 位置：第 95-105 行
- 参数：pr
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

## core/services/process/part_service.py（Service 层）

### `PartService.__init__()` [私有]
- 位置：第 26-39 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `PartService._normalize_text()` [私有]
- 位置：第 45-46 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `PartService._normalize_float()` [私有]
- 位置：第 49-55 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `PartService._get_or_raise()` [私有]
- 位置：第 57-61 行
- 参数：part_no
- 返回类型：Name(id='Part', ctx=Load())

### `PartService._build_internal_hours_snapshot()` [私有]
- 位置：第 63-78 行
- 参数：part_no
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `PartService.list()` [公开]
- 位置：第 83-86 行
- 参数：route_parsed
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`ValidationError`

### `PartService.get()` [公开]
- 位置：第 88-92 行
- 参数：part_no
- 返回类型：Name(id='Part', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self._normalize_text`, `self._get_or_raise`, `ValidationError`

### `PartService.create()` [公开]
- 位置：第 94-126 行
- 参数：part_no, part_name, route_raw, remark
- 返回类型：Name(id='Part', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`self._normalize_text`, `get`, `self._get_or_raise`, `str`, `ValidationError`, `BusinessError`, `transaction`, `strip`, `self.reparse_and_save`

### `PartService.update()` [公开]
- 位置：第 128-148 行
- 参数：part_no, part_name, route_raw, remark
- 返回类型：Name(id='Part', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`self._normalize_text`, `self._get_or_raise`, `ValidationError`, `str`, `transaction`

### `PartService.delete()` [公开]
- 位置：第 150-162 行
- 参数：part_no
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`self._normalize_text`, `self._get_or_raise`, `fetchone`, `ValidationError`, `BusinessError`, `transaction`, `execute`

### `PartService.delete_all_no_tx()` [公开]
- 位置：第 164-165 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `web/routes/process_excel_routes.py:183` [Route] `part_svc.delete_all_no_tx()`
  - `web/routes/scheduler_excel_calendar.py:312` [Route] `cal_svc.delete_all_no_tx()`
  - `core/services/scheduler/batch_excel_import.py:30` [Service] `svc.delete_all_no_tx()`
  - `core/services/scheduler/calendar_service.py:100` [Service] `self._admin.delete_all_no_tx()`
- **被调用者**（1 个）：`delete_all`

### `PartService.validate_route_format()` [公开]
- 位置：第 170-171 行
- 参数：route_raw
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（2 处）：
  - `web/routes/process_excel_routes.py:68` [Route] `ok, msg = part_svc.validate_route_format(route_raw)`
  - `web/routes/process_excel_routes.py:137` [Route] `ok, msg = part_svc.validate_route_format(route_raw)`
- **被调用者**（2 个）：`validate_format`, `str`

### `PartService.parse()` [公开]
- 位置：第 173-174 行
- 参数：route_raw, part_no
- 返回类型：Name(id='ParseResult', ctx=Load())
- **调用者**（1 处）：
  - `core/services/process/unit_excel_converter.py:27` [Service] `parts, stations = self._parser.parse(input_path=input_path, sheet_name=sheet_nam`
- **被调用者**（1 个）：`str`

### `PartService.reparse_and_save()` [公开]
- 位置：第 176-218 行
- 参数：part_no, route_raw
- 返回类型：Name(id='ParseResult', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/process_parts.py:171` [Route] `result = svc.reparse_and_save(part_no=part_no, route_raw=route_raw)`
  - `core/services/scheduler/batch_service.py:119` [Service] `svc.reparse_and_save(part_no=part_no, route_raw=route_raw)`
- **被调用者**（12 个）：`self._normalize_text`, `self._get_or_raise`, `validate_format`, `parse`, `ValidationError`, `str`, `BusinessError`, `transaction`, `update`, `self._build_internal_hours_snapshot`, `delete_by_part`, `self._save_template_no_tx`

### `PartService.upsert_and_parse_no_tx()` [公开]
- 位置：第 220-262 行
- 参数：part_no, part_name, route_raw
- 返回类型：Name(id='ParseResult', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/process_excel_routes.py:202` [Route] `part_svc.upsert_and_parse_no_tx(part_no=pn, part_name=name, route_raw=route_raw)`
  - `core/services/scheduler/batch_service.py:117` [Service] `svc.upsert_and_parse_no_tx(part_no=part_no, part_name=part_name, route_raw=route`
- **被调用者**（12 个）：`self._normalize_text`, `validate_format`, `parse`, `get`, `self._build_internal_hours_snapshot`, `delete_by_part`, `self._save_template_no_tx`, `str`, `ValidationError`, `BusinessError`, `update`, `create`

### `PartService._save_template_no_tx()` [私有]
- 位置：第 264-333 行
- 参数：part_no, parse_result, preserved_internal_hours
- 返回类型：Constant(value=None, kind=None)

### `PartService.get_template_detail()` [公开]
- 位置：第 338-348 行
- 参数：part_no
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/process_parts.py:79` [Route] `detail = p_svc.get_template_detail(part_no)`
- **被调用者**（2 个）：`self.get`, `list_by_part`

### `PartService.update_internal_hours()` [公开]
- 位置：第 350-377 行
- 参数：part_no, seq, setup_hours, unit_hours
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/process_parts.py:187` [Route] `svc.update_internal_hours(part_no=part_no, seq=seq, setup_hours=setup_hours, uni`
  - `core/services/process/part_operation_hours_excel_import_service.py:71` [Service] `self.part_svc.update_internal_hours(part_no=part_no, seq=seq, setup_hours=sh, un`
- **被调用者**（12 个）：`self._normalize_text`, `self._get_or_raise`, `self._normalize_float`, `get`, `ValidationError`, `int`, `BusinessError`, `lower`, `transaction`, `update`, `strip`, `float`

### `PartService.delete_external_group()` [公开]
- 位置：第 379-422 行
- 参数：part_no, group_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/process_parts.py:221` [Route] `result = svc.delete_external_group(part_no=part_no, group_id=group_id)`
- **被调用者**（17 个）：`self._normalize_text`, `self._get_or_raise`, `get`, `list_by_part`, `get_deletion_groups`, `can_delete`, `ValidationError`, `BusinessError`, `int`, `DeleteOp`, `any`, `transaction`, `delete`, `mark_deleted`, `lower`

### `PartService.calc_deletable_external_group_ids()` [公开]
- 位置：第 424-455 行
- 参数：part_no
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/process_parts.py:91` [Route] `deletable_group_ids = set(p_svc.calc_deletable_external_group_ids(part_no))`
- **被调用者**（11 个）：`self._normalize_text`, `list_by_part`, `get_deletion_groups`, `set`, `DeleteOp`, `deletable_seqs.add`, `int`, `all`, `group_ids.append`, `lower`, `strip`

### `PartService.build_existing_for_excel_routes()` [公开]
- 位置：第 460-464 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/process_excel_routes.py:30` [Route] `existing = svc.build_existing_for_excel_routes()`
  - `web/routes/process_excel_routes.py:58` [Route] `existing = part_svc.build_existing_for_excel_routes()`
  - `web/routes/process_excel_routes.py:127` [Route] `existing = part_svc.build_existing_for_excel_routes()`
- **被调用者**（1 个）：`list`

## core/services/process/unit_excel/parser.py（Service 层）

### `UnitExcelParser.parse()` [公开]
- 位置：第 44-70 行
- 参数：input_path, sheet_name
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（4 处）：
  - `core/services/process/part_service.py:174` [Service] `return self.route_parser.parse(str(route_raw) if route_raw is not None else "", `
  - `core/services/process/part_service.py:192` [Service] `result = self.route_parser.parse(rr, part_no=pn)`
  - `core/services/process/part_service.py:237` [Service] `result = self.route_parser.parse(rr, part_no=pn)`
  - `core/services/process/unit_excel_converter.py:27` [Service] `parts, stations = self._parser.parse(input_path=input_path, sheet_name=sheet_nam`
- **被调用者**（9 个）：`openpyxl.load_workbook`, `self._build_station_columns`, `ws.iter_rows`, `self._to_text`, `list`, `self._maybe_update_part_context`, `self._append_station_step_records`, `wb.close`, `next`

### `UnitExcelParser._maybe_update_part_context()` [私有]
- 位置：第 72-99 行
- 参数：parts
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `UnitExcelParser._append_station_step_records()` [私有]
- 位置：第 101-119 行
- 参数：ctx
- 返回类型：Constant(value=None, kind=None)

### `UnitExcelParser._build_station_columns()` [私有]
- 位置：第 121-138 行
- 参数：headers
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `UnitExcelParser._parse_station_header()` [私有]
- 位置：第 140-162 行
- 参数：raw_header
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `UnitExcelParser._extract_machine_id()` [私有]
- 位置：第 165-173 行
- 参数：text
- 返回类型：Name(id='str', ctx=Load())

### `UnitExcelParser._extract_names()` [私有]
- 位置：第 175-186 行
- 参数：text
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `UnitExcelParser._parse_step_seq()` [私有]
- 位置：第 189-205 行
- 参数：step_text
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `UnitExcelParser._parse_route_map()` [私有]
- 位置：第 207-221 行
- 参数：route_raw
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `UnitExcelParser._to_text()` [私有]
- 位置：第 224-229 行
- 参数：v
- 返回类型：Name(id='str', ctx=Load())

### `UnitExcelParser._to_float()` [私有]
- 位置：第 232-249 行
- 参数：v
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `UnitExcelParser._pick_cell()` [私有]
- 位置：第 252-253 行
- 参数：row_values, idx
- 返回类型：Name(id='Any', ctx=Load())

### `UnitExcelParser._dedupe_keep_order()` [私有]
- 位置：第 256-265 行
- 参数：items
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `UnitExcelParser._normalize_route()` [私有]
- 位置：第 267-273 行
- 参数：route_raw
- 返回类型：Name(id='str', ctx=Load())

## core/services/process/unit_excel/template_builder.py（Service 层）

### `ConvertedTemplates.output_specs()` [公开]
- 位置：第 24-33 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/process/unit_excel/exporter.py:15` [Service] `for filename, headers, field_name in ConvertedTemplates.output_specs():`

### `ConvertedTemplates.rows_by_filename()` [公开]
- 位置：第 35-39 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self.output_specs`, `list`, `getattr`

### `UnitTemplateBuilder.build()` [公开]
- 位置：第 43-77 行
- 参数：parts, stations
- 返回类型：Name(id='ConvertedTemplates', ctx=Load())
- **调用者**（1 处）：
  - `core/services/process/unit_excel_converter.py:28` [Service] `return self._builder.build(parts=parts, stations=stations)`
- **被调用者**（13 个）：`self._build_machine_op_hint`, `self._collect_op_records`, `self._conflict_names`, `self._apply_final_names`, `self._group_op_records_by_part`, `self._build_route_rows`, `self._build_part_operation_hours_rows`, `self._build_operator_rows`, `self._build_machines_rows`, `self._build_operator_machine_rows`, `self._build_op_types_rows`, `self._build_suppliers_rows`, `ConvertedTemplates`

### `UnitTemplateBuilder._build_machine_op_hint()` [私有]
- 位置：第 80-89 行
- 参数：parts
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `UnitTemplateBuilder._build_seq_maps()` [私有]
- 位置：第 92-102 行
- 参数：ctx
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `UnitTemplateBuilder._infer_missing_name_map()` [私有]
- 位置：第 104-121 行
- 参数：ctx
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `UnitTemplateBuilder._all_seqs()` [私有]
- 位置：第 124-125 行
- 参数：ctx, internal_seq_set
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `UnitTemplateBuilder._collect_op_records()` [私有]
- 位置：第 127-177 行
- 参数：parts, machine_op_hint
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `UnitTemplateBuilder._append_internal_links_and_counters()` [私有]
- 位置：第 180-196 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `UnitTemplateBuilder._conflict_names()` [私有]
- 位置：第 199-204 行
- 参数：op_records
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Index(valu

### `UnitTemplateBuilder._apply_final_names()` [私有]
- 位置：第 206-213 行
- 参数：op_records, conflict_names
- 返回类型：Constant(value=None, kind=None)

### `UnitTemplateBuilder._group_op_records_by_part()` [私有]
- 位置：第 216-220 行
- 参数：op_records
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `UnitTemplateBuilder._build_route_rows()` [私有]
- 位置：第 223-230 行
- 参数：by_part
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `UnitTemplateBuilder._build_part_operation_hours_rows()` [私有]
- 位置：第 233-248 行
- 参数：by_part
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `UnitTemplateBuilder._build_operator_rows()` [私有]
- 位置：第 251-264 行
- 参数：operator_names
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `UnitTemplateBuilder._build_machines_rows()` [私有]
- 位置：第 266-286 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `UnitTemplateBuilder._build_operator_machine_rows()` [私有]
- 位置：第 289-296 行
- 参数：links, operator_id_map
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `UnitTemplateBuilder._build_op_types_rows()` [私有]
- 位置：第 299-310 行
- 参数：op_records
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `UnitTemplateBuilder._build_suppliers_rows()` [私有]
- 位置：第 313-340 行
- 参数：op_records, op_types_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `UnitTemplateBuilder._infer_op_name_for_missing_seq()` [私有]
- 位置：第 342-364 行
- 参数：seq, records, machine_op_hint
- 返回类型：Name(id='str', ctx=Load())

### `UnitTemplateBuilder._aggregate_internal_hours()` [私有]
- 位置：第 366-383 行
- 参数：records
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `UnitTemplateBuilder._extract_step_key()` [私有]
- 位置：第 386-391 行
- 参数：step_text
- 返回类型：Name(id='str', ctx=Load())

### `UnitTemplateBuilder._estimate_external_days()` [私有]
- 位置：第 394-411 行
- 参数：records
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `UnitTemplateBuilder._external_alias()` [私有]
- 位置：第 414-418 行
- 参数：name
- 返回类型：Name(id='str', ctx=Load())

### `UnitTemplateBuilder._most_common_key()` [私有]
- 位置：第 421-427 行
- 参数：counter
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `UnitTemplateBuilder._build_machine_name()` [私有]
- 位置：第 430-436 行
- 参数：machine_id, machine_label
- 返回类型：Name(id='str', ctx=Load())

## core/services/scheduler/batch_excel_import.py（Service 层）

### `import_batches_from_preview_rows()` [公开]
- 位置：第 10-104 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/batch_service.py:377` [Service] `return batch_excel_import.import_batches_from_preview_rows(`
- **被调用者**（17 个）：`list`, `execute_preview_rows_transactional`, `stats.to_dict`, `len`, `bool`, `set`, `svc.delete_all_no_tx`, `strip`, `int`, `get`, `parts_cache.get`, `svc.update_no_tx`, `svc.create_no_tx`, `svc.create_batch_from_template_no_tx`, `svc.list`

## core/services/scheduler/calendar_engine.py（Service 层）

### `DayPolicy.is_priority_allowed()` [公开]
- 位置：第 34-42 行
- 参数：priority
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`lower`, `strip`, `str`

### `DayPolicy.work_window()` [公开]
- 位置：第 44-48 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`date`, `datetime.combine`, `timedelta`, `datetime.strptime`, `float`

### `CalendarEngine.__init__()` [私有]
- 位置：第 60-67 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `CalendarEngine.clear_policy_cache()` [公开]
- 位置：第 69-76 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（9 处）：
  - `core/services/scheduler/calendar_service.py:87` [Service] `self._engine.clear_policy_cache()`
  - `core/services/scheduler/calendar_service.py:92` [Service] `self._engine.clear_policy_cache()`
  - `core/services/scheduler/calendar_service.py:97` [Service] `self._engine.clear_policy_cache()`
  - `core/services/scheduler/calendar_service.py:101` [Service] `self._engine.clear_policy_cache()`
  - `core/services/scheduler/calendar_service.py:140` [Service] `self._engine.clear_policy_cache()`
  - `core/services/scheduler/calendar_service.py:145` [Service] `self._engine.clear_policy_cache()`
  - `core/services/scheduler/calendar_service.py:150` [Service] `self._engine.clear_policy_cache()`
  - `core/services/scheduler/calendar_service.py:154` [Service] `self._engine.clear_policy_cache()`
  - `core/services/scheduler/calendar_service.py:211` [Service] `self._engine.clear_policy_cache()`
- **被调用者**（1 个）：`clear`

### `CalendarEngine._normalize_text()` [私有]
- 位置：第 79-80 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `CalendarEngine._default_for_date()` [私有]
- 位置：第 82-103 行
- 参数：date_str
- 返回类型：Name(id='WorkCalendar', ctx=Load())

### `CalendarEngine._resolve_calendar_row()` [私有]
- 位置：第 105-111 行
- 参数：date_str, op_id
- 返回类型：Name(id='Any', ctx=Load())

### `CalendarEngine._normalize_efficiency()` [私有]
- 位置：第 114-116 行
- 参数：cal
- 返回类型：Name(id='float', ctx=Load())

### `CalendarEngine._parse_shift_start()` [私有]
- 位置：第 119-127 行
- 参数：cal
- 返回类型：Name(id='time', ctx=Load())

### `CalendarEngine._override_shift_hours_by_shift_end()` [私有]
- 位置：第 130-146 行
- 参数：cal
- 返回类型：Name(id='float', ctx=Load())

### `CalendarEngine._policy_for_date()` [私有]
- 位置：第 148-176 行
- 参数：date_str, operator_id
- 返回类型：Name(id='DayPolicy', ctx=Load())

### `CalendarEngine._policy_for_datetime()` [私有]
- 位置：第 178-201 行
- 参数：dt, operator_id
- 返回类型：Name(id='DayPolicy', ctx=Load())

### `CalendarEngine.policy_for_datetime()` [公开]
- 位置：第 203-207 行
- 参数：dt, operator_id
- 返回类型：Name(id='DayPolicy', ctx=Load())
- **调用者**（2 处）：
  - `core/services/report/calculations.py:50` [Service] `p = calendar.policy_for_datetime(datetime.combine(cur, datetime.min.time()))`
  - `core/services/scheduler/calendar_service.py:215` [Service] `return self._engine.policy_for_datetime(dt, operator_id=operator_id)`
- **被调用者**（1 个）：`self._policy_for_datetime`

### `CalendarEngine.get_efficiency()` [公开]
- 位置：第 209-210 行
- 参数：dt, machine_id, operator_id
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（4 处）：
  - `core/services/scheduler/calendar_service.py:218` [Service] `return self._engine.get_efficiency(dt, machine_id=machine_id, operator_id=operat`
  - `core/algorithms/greedy/auto_assign.py:136` [Algorithm] `raw_eff = scheduler.calendar.get_efficiency(start, operator_id=oid)`
  - `core/algorithms/greedy/scheduler.py:471` [Algorithm] `eff = float(self.calendar.get_efficiency(start, operator_id=operator_id) or 1.0)`
  - `core/algorithms/greedy/dispatch/sgs.py:248` [Algorithm] `eff = float(scheduler.calendar.get_efficiency(est_start, operator_id=operator_id`
- **被调用者**（2 个）：`float`, `self._policy_for_datetime`

### `CalendarEngine.adjust_to_working_time()` [公开]
- 位置：第 212-243 行
- 参数：dt, priority, machine_id, operator_id
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（7 处）：
  - `core/services/scheduler/calendar_service.py:227` [Service] `return self._engine.adjust_to_working_time(dt, priority=priority, machine_id=mac`
  - `core/algorithms/greedy/auto_assign.py:130` [Algorithm] `earliest = scheduler.calendar.adjust_to_working_time(earliest, priority=priority`
  - `core/algorithms/greedy/auto_assign.py:169` [Algorithm] `earliest = scheduler.calendar.adjust_to_working_time(earliest, priority=priority`
  - `core/algorithms/greedy/scheduler.py:221` [Algorithm] `dt_ready = self.calendar.adjust_to_working_time(dt0, priority=p)`
  - `core/algorithms/greedy/scheduler.py:451` [Algorithm] `earliest = self.calendar.adjust_to_working_time(earliest, priority=priority, ope`
  - `core/algorithms/greedy/scheduler.py:506` [Algorithm] `earliest = self.calendar.adjust_to_working_time(earliest, priority=priority, ope`
  - `core/algorithms/greedy/dispatch/sgs.py:234` [Algorithm] `est_start = scheduler.calendar.adjust_to_working_time(est_start, priority=priori`
- **被调用者**（8 个）：`self._policy_for_datetime`, `p.work_window`, `BusinessError`, `datetime.combine`, `p.is_priority_allowed`, `cur.date`, `timedelta`, `time`

### `CalendarEngine.add_working_hours()` [公开]
- 位置：第 245-307 行
- 参数：start, hours, priority, machine_id, operator_id
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（6 处）：
  - `core/services/scheduler/calendar_service.py:237` [Service] `return self._engine.add_working_hours(start, hours, priority=priority, machine_i`
  - `core/algorithms/greedy/auto_assign.py:154` [Algorithm] `end = scheduler.calendar.add_working_hours(earliest, total_hours, priority=prior`
  - `core/algorithms/greedy/auto_assign.py:171` [Algorithm] `end = scheduler.calendar.add_working_hours(earliest, total_hours, priority=prior`
  - `core/algorithms/greedy/scheduler.py:488` [Algorithm] `end = self.calendar.add_working_hours(earliest, total_hours, priority=priority, `
  - `core/algorithms/greedy/scheduler.py:508` [Algorithm] `end = self.calendar.add_working_hours(earliest, total_hours, priority=priority, `
  - `core/algorithms/greedy/dispatch/sgs.py:265` [Algorithm] `est_end = scheduler.calendar.add_working_hours(`
- **被调用者**（12 个）：`self.adjust_to_working_time`, `ValidationError`, `float`, `self._policy_for_datetime`, `p.work_window`, `BusinessError`, `datetime.combine`, `total_seconds`, `p.is_priority_allowed`, `time`, `timedelta`, `cur.date`

### `CalendarEngine.add_calendar_days()` [公开]
- 位置：第 309-322 行
- 参数：start, days, machine_id, operator_id
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（5 处）：
  - `core/services/scheduler/calendar_service.py:240` [Service] `return self._engine.add_calendar_days(start, days, machine_id=machine_id, operat`
  - `core/algorithms/greedy/external_groups.py:45` [Algorithm] `end = scheduler.calendar.add_calendar_days(start, total_days_f)`
  - `core/algorithms/greedy/external_groups.py:84` [Algorithm] `end = scheduler.calendar.add_calendar_days(start, ext_days_f)`
  - `core/algorithms/greedy/dispatch/sgs.py:158` [Algorithm] `est_end = scheduler.calendar.add_calendar_days(est_start, total_days_f)`
  - `core/algorithms/greedy/dispatch/sgs.py:174` [Algorithm] `est_end = scheduler.calendar.add_calendar_days(est_start, ext_days_f)`
- **被调用者**（3 个）：`ValidationError`, `float`, `timedelta`

## core/services/scheduler/calendar_service.py（Service 层）

### `CalendarService.__init__()` [私有]
- 位置：第 23-28 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `CalendarService._normalize_date()` [私有]
- 位置：第 34-41 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `CalendarService._normalize_hhmm()` [私有]
- 位置：第 44-48 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `CalendarService.get()` [公开]
- 位置：第 53-56 行
- 参数：date_value
- 返回类型：Name(id='WorkCalendar', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_normalize_date`, `_default_for_date`

### `CalendarService.list_all()` [公开]
- 位置：第 58-59 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（11 处）：
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/scheduler_excel_calendar.py:38` [Route] `for c in cal_svc.list_all():`
  - `web/routes/scheduler_excel_calendar.py:97` [Route] `for c in cal_svc.list_all():`
  - `web/routes/scheduler_excel_calendar.py:220` [Route] `for c in cal_svc.list_all():`
  - `web/routes/scheduler_excel_calendar.py:424` [Route] `rows = cal_svc.list_all()`
  - `core/services/scheduler/calendar_admin.py:100` [Service] `return self.repo.list_all()`
  - `core/services/scheduler/calendar_admin.py:208` [Service] `return self.operator_calendar_repo.list_all()`
  - `core/services/scheduler/config_presets.py:119` [Service] `keys = existing_keys if existing_keys is not None else {c.config_key for c in sv`
  - `core/services/scheduler/config_presets.py:160` [Service] `items = svc.repo.list_all()`
  - `core/services/scheduler/config_service.py:163` [Service] `existing = {c.config_key for c in self.repo.list_all()}`
  - `core/services/system/system_config_service.py:90` [Service] `existing = {c.config_key for c in self.repo.list_all()}`

### `CalendarService.list_range()` [公开]
- 位置：第 61-62 行
- 参数：start_date, end_date
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/calendar_admin.py:105` [Service] `return self.repo.list_range(s, e)`

### `CalendarService.upsert()` [公开]
- 位置：第 64-88 行
- 参数：date_value, day_type, shift_hours, shift_start, shift_end, efficiency, allow_normal, allow_urgent, remark
- 返回类型：Name(id='WorkCalendar', ctx=Load())
- **调用者**（3 处）：
  - `web/routes/scheduler_calendar_pages.py:44` [Route] `cal_svc.upsert(`
  - `core/services/scheduler/calendar_admin.py:180` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:284` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.upsert_no_tx()` [公开]
- 位置：第 90-93 行
- 参数：calendar_payload
- 返回类型：Name(id='WorkCalendar', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_excel_calendar.py:329` [Route] `cal_svc.upsert_no_tx(`
  - `core/services/scheduler/calendar_admin.py:169` [Service] `self.upsert_no_tx(cal.to_dict())`
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.delete()` [公开]
- 位置：第 95-97 行
- 参数：date_value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.delete_all_no_tx()` [公开]
- 位置：第 99-101 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（3 处）：
  - `web/routes/process_excel_routes.py:183` [Route] `part_svc.delete_all_no_tx()`
  - `web/routes/scheduler_excel_calendar.py:312` [Route] `cal_svc.delete_all_no_tx()`
  - `core/services/scheduler/batch_excel_import.py:30` [Service] `svc.delete_all_no_tx()`
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.get_operator_calendar()` [公开]
- 位置：第 106-107 行
- 参数：operator_id, date_value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）

### `CalendarService.list_operator_calendar()` [公开]
- 位置：第 109-110 行
- 参数：operator_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/personnel_calendar_pages.py:23` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`

### `CalendarService.list_operator_calendar_all()` [公开]
- 位置：第 112-113 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/personnel_excel_operator_calendar.py:39` [Route] `for c in cal_svc.list_operator_calendar_all():`
  - `web/routes/personnel_excel_operator_calendar.py:112` [Route] `for c in cal_svc.list_operator_calendar_all():`
  - `web/routes/personnel_excel_operator_calendar.py:204` [Route] `for c in cal_svc.list_operator_calendar_all():`
  - `web/routes/personnel_excel_operator_calendar.py:360` [Route] `rows = cal_svc.list_operator_calendar_all()`

### `CalendarService.upsert_operator_calendar()` [公开]
- 位置：第 115-141 行
- 参数：operator_id, date_value, day_type, shift_hours, shift_start, shift_end, efficiency, allow_normal, allow_urgent, remark
- 返回类型：Name(id='OperatorCalendar', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/personnel_calendar_pages.py:63` [Route] `cal_svc.upsert_operator_calendar(`
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.upsert_operator_calendar_no_tx()` [公开]
- 位置：第 143-146 行
- 参数：calendar_payload
- 返回类型：Name(id='OperatorCalendar', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/calendar_admin.py:275` [Service] `self.upsert_operator_calendar_no_tx(cal.to_dict())`
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.delete_operator_calendar()` [公开]
- 位置：第 148-150 行
- 参数：operator_id, date_value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.delete_operator_calendar_all_no_tx()` [公开]
- 位置：第 152-154 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.import_operator_calendar_from_preview_rows()` [公开]
- 位置：第 156-212 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/personnel_excel_operator_calendar.py:277` [Route] `import_stats = cal_svc.import_operator_calendar_from_preview_rows(`
- **被调用者**（12 个）：`list`, `execute_preview_rows_transactional`, `stats.to_dict`, `len`, `clear_policy_cache`, `set`, `self.delete_operator_calendar_all_no_tx`, `strip`, `self.upsert_operator_calendar_no_tx`, `self.list_operator_calendar_all`, `str`, `get`

### `CalendarService.policy_for_datetime()` [公开]
- 位置：第 214-215 行
- 参数：dt, operator_id
- 返回类型：Name(id='DayPolicy', ctx=Load())
- **调用者**（1 处）：
  - `core/services/report/calculations.py:50` [Service] `p = calendar.policy_for_datetime(datetime.combine(cur, datetime.min.time()))`

### `CalendarService.get_efficiency()` [公开]
- 位置：第 217-218 行
- 参数：dt, machine_id, operator_id
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（3 处）：
  - `core/algorithms/greedy/auto_assign.py:136` [Algorithm] `raw_eff = scheduler.calendar.get_efficiency(start, operator_id=oid)`
  - `core/algorithms/greedy/scheduler.py:471` [Algorithm] `eff = float(self.calendar.get_efficiency(start, operator_id=operator_id) or 1.0)`
  - `core/algorithms/greedy/dispatch/sgs.py:248` [Algorithm] `eff = float(scheduler.calendar.get_efficiency(est_start, operator_id=operator_id`

### `CalendarService.adjust_to_working_time()` [公开]
- 位置：第 220-227 行
- 参数：dt, priority, machine_id, operator_id
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（12 处）：
  - `core/services/scheduler/calendar_engine.py:267` [Service] `return self.adjust_to_working_time(start, priority=priority, operator_id=operato`
  - `core/services/scheduler/calendar_engine.py:269` [Service] `cur = self.adjust_to_working_time(start, priority=priority, operator_id=operator`
  - `core/services/scheduler/calendar_engine.py:280` [Service] `cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_i`
  - `core/services/scheduler/calendar_engine.py:289` [Service] `cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_i`
  - `core/services/scheduler/calendar_engine.py:296` [Service] `cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_i`
  - `core/services/scheduler/calendar_engine.py:305` [Service] `cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_i`
  - `core/algorithms/greedy/auto_assign.py:130` [Algorithm] `earliest = scheduler.calendar.adjust_to_working_time(earliest, priority=priority`
  - `core/algorithms/greedy/auto_assign.py:169` [Algorithm] `earliest = scheduler.calendar.adjust_to_working_time(earliest, priority=priority`
  - `core/algorithms/greedy/scheduler.py:221` [Algorithm] `dt_ready = self.calendar.adjust_to_working_time(dt0, priority=p)`
  - `core/algorithms/greedy/scheduler.py:451` [Algorithm] `earliest = self.calendar.adjust_to_working_time(earliest, priority=priority, ope`
  - `core/algorithms/greedy/scheduler.py:506` [Algorithm] `earliest = self.calendar.adjust_to_working_time(earliest, priority=priority, ope`
  - `core/algorithms/greedy/dispatch/sgs.py:234` [Algorithm] `est_start = scheduler.calendar.adjust_to_working_time(est_start, priority=priori`

### `CalendarService.add_working_hours()` [公开]
- 位置：第 229-237 行
- 参数：start, hours, priority, machine_id, operator_id
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（5 处）：
  - `core/algorithms/greedy/auto_assign.py:154` [Algorithm] `end = scheduler.calendar.add_working_hours(earliest, total_hours, priority=prior`
  - `core/algorithms/greedy/auto_assign.py:171` [Algorithm] `end = scheduler.calendar.add_working_hours(earliest, total_hours, priority=prior`
  - `core/algorithms/greedy/scheduler.py:488` [Algorithm] `end = self.calendar.add_working_hours(earliest, total_hours, priority=priority, `
  - `core/algorithms/greedy/scheduler.py:508` [Algorithm] `end = self.calendar.add_working_hours(earliest, total_hours, priority=priority, `
  - `core/algorithms/greedy/dispatch/sgs.py:265` [Algorithm] `est_end = scheduler.calendar.add_working_hours(`

### `CalendarService.add_calendar_days()` [公开]
- 位置：第 239-240 行
- 参数：start, days, machine_id, operator_id
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（4 处）：
  - `core/algorithms/greedy/external_groups.py:45` [Algorithm] `end = scheduler.calendar.add_calendar_days(start, total_days_f)`
  - `core/algorithms/greedy/external_groups.py:84` [Algorithm] `end = scheduler.calendar.add_calendar_days(start, ext_days_f)`
  - `core/algorithms/greedy/dispatch/sgs.py:158` [Algorithm] `est_end = scheduler.calendar.add_calendar_days(est_start, total_days_f)`
  - `core/algorithms/greedy/dispatch/sgs.py:174` [Algorithm] `est_end = scheduler.calendar.add_calendar_days(est_start, ext_days_f)`

## core/services/scheduler/freeze_window.py（Service 层）

### `_freeze_window_days()` [私有]
- 位置：第 11-23 行
- 参数：cfg, prev_version
- 返回类型：Name(id='int', ctx=Load())

### `_safe_load_schedule_map()` [私有]
- 位置：第 26-55 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_max_seq_by_batch()` [私有]
- 位置：第 58-69 行
- 参数：schedule_map, op_by_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_prefix_op_ids_for_batch()` [私有]
- 位置：第 72-73 行
- 参数：operations, bid, max_seq
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_cache_seed_for_prefix()` [私有]
- 位置：第 76-90 行
- 参数：svc
- 返回类型：Name(id='int', ctx=Load())

### `_discard_seed_cache()` [私有]
- 位置：第 93-95 行
- 参数：prefix, seed_tmp
- 返回类型：Constant(value=None, kind=None)

### `_build_seed_results()` [私有]
- 位置：第 98-129 行
- 参数：frozen_op_ids
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `build_freeze_window_seed()` [公开]
- 位置：第 132-205 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:320` [Service] `frozen_op_ids, seed_results, algo_warnings = build_freeze_window_seed(`
- **被调用者**（21 个）：`set`, `_freeze_window_days`, `svc._format_dt`, `sorted`, `_safe_load_schedule_map`, `_max_seq_by_batch`, `max_seq_by_batch.items`, `_build_seed_results`, `seed_results.sort`, `timedelta`, `int`, `list`, `_prefix_op_ids_for_batch`, `_cache_seed_for_prefix`, `op_by_id.keys`

## core/services/scheduler/gantt_critical_chain.py（Service 层）

### `_parse_dt()` [私有]
- 位置：第 7-21 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_fmt_dt()` [私有]
- 位置：第 24-25 行
- 参数：dt
- 返回类型：Name(id='str', ctx=Load())

### `_minutes_between()` [私有]
- 位置：第 28-34 行
- 参数：a, b
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_safe_int()` [私有]
- 位置：第 37-46 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_empty_result()` [私有]
- 位置：第 49-56 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_load_rows()` [私有]
- 位置：第 59-63 行
- 参数：schedule_repo, version
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_build_nodes()` [私有]
- 位置：第 66-86 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_process_prev()` [私有]
- 位置：第 89-107 行
- 参数：nodes
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_prev_by_resource()` [私有]
- 位置：第 110-127 行
- 参数：nodes
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_eligible_process_edge()` [私有]
- 位置：第 130-135 行
- 参数：pn, n
- 返回类型：Name(id='bool', ctx=Load())

### `_eligible_resource_edge()` [私有]
- 位置：第 138-143 行
- 参数：pn, n
- 返回类型：Name(id='bool', ctx=Load())

### `_process_prev_candidate()` [私有]
- 位置：第 146-161 行
- 参数：nodes, tid, n
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_resource_prev_candidate()` [私有]
- 位置：第 164-184 行
- 参数：nodes, tid, n
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_pick_latest_candidate()` [私有]
- 位置：第 187-195 行
- 参数：cands
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_choose_control_prev()` [私有]
- 位置：第 198-234 行
- 参数：nodes
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_sink_id()` [私有]
- 位置：第 237-239 行
- 参数：nodes
- 返回类型：Name(id='str', ctx=Load())

### `_backtrace_chain()` [私有]
- 位置：第 242-273 行
- 参数：sink_id
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_edge_type_stats()` [私有]
- 位置：第 276-283 行
- 参数：edges
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `compute_critical_chain()` [公开]
- 位置：第 286-315 行
- 参数：schedule_repo, version
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/gantt_service.py:103` [Service] `computed = compute_critical_chain(self.schedule_repo, int(version))`
- **被调用者**（13 个）：`_load_rows`, `_build_nodes`, `_build_process_prev`, `_build_prev_by_resource`, `_choose_control_prev`, `_sink_id`, `_backtrace_chain`, `_empty_result`, `_fmt_dt`, `_edge_type_stats`, `len`, `int`, `get`

## core/services/scheduler/gantt_tasks.py（Service 层）

### `_parse_dt()` [私有]
- 位置：第 12-26 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_fmt_dt()` [私有]
- 位置：第 29-30 行
- 参数：dt
- 返回类型：Name(id='str', ctx=Load())

### `_duration_minutes()` [私有]
- 位置：第 33-37 行
- 参数：st, et
- 返回类型：Name(id='int', ctx=Load())

### `_priority_class()` [私有]
- 位置：第 40-44 行
- 参数：priority
- 返回类型：Name(id='str', ctx=Load())

### `_display_machine()` [私有]
- 位置：第 47-53 行
- 参数：machine_id, machine_name, supplier_name
- 返回类型：Name(id='str', ctx=Load())

### `_display_operator()` [私有]
- 位置：第 56-61 行
- 参数：operator_id, operator_name
- 返回类型：Name(id='str', ctx=Load())

### `build_calendar_days()` [公开]
- 位置：第 64-107 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/gantt_service.py:155` [Service] `calendar_days = build_calendar_days(self.conn, wr=wr, logger=self.logger, op_log`
- **被调用者**（9 个）：`CalendarService`, `cal_svc.get`, `str`, `getattr`, `bool`, `calendar_days.append`, `d0.isoformat`, `float`, `timedelta`

### `_clamp_to_week()` [私有]
- 位置：第 110-116 行
- 参数：st, et
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_task_name_and_group()` [私有]
- 位置：第 119-134 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_safe_int()` [私有]
- 位置：第 137-146 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_build_one_task()` [私有]
- 位置：第 149-221 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_attach_process_dependencies()` [私有]
- 位置：第 224-251 行
- 参数：tasks
- 返回类型：Constant(value=None, kind=None)

### `_sort_tasks()` [私有]
- 位置：第 254-260 行
- 参数：tasks
- 返回类型：Constant(value=None, kind=None)

### `build_tasks()` [公开]
- 位置：第 263-281 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/gantt_service.py:159` [Service] `tasks = build_tasks(view=view, wr=wr, rows=rows, overdue_set=overdue_set)`
- **被调用者**（5 个）：`_attach_process_dependencies`, `_sort_tasks`, `_build_one_task`, `tasks.append`, `dict`

## core/services/scheduler/operation_edit_service.py（Service 层）

### `list_batch_operations()` [公开]
- 位置：第 10-15 行
- 参数：svc, batch_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/scheduler_batch_detail.py:190` [Route] `ops = sch_svc.list_batch_operations(batch_id=b.batch_id)`
  - `core/services/scheduler/schedule_service.py:119` [Service] `return op_edit.list_batch_operations(self, batch_id)`
- **被调用者**（4 个）：`svc._normalize_text`, `svc._get_batch_or_raise`, `list_by_batch`, `ValidationError`

### `get_operation()` [公开]
- 位置：第 18-23 行
- 参数：svc, op_id
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_ops.py:14` [Route] `op = sch_svc.get_operation(op_id)`
  - `core/services/scheduler/schedule_service.py:122` [Service] `return op_edit.get_operation(self, op_id)`
- **被调用者**（3 个）：`svc._get_op_or_raise`, `int`, `ValidationError`

### `get_external_merge_hint()` [公开]
- 位置：第 26-42 行
- 参数：svc, op_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/scheduler_batch_detail.py:179` [Route] `d["merge_hint"] = sch_svc.get_external_merge_hint(op.id)`
  - `core/services/scheduler/schedule_service.py:128` [Service] `return op_edit.get_external_merge_hint(self, op_id)`
- **被调用者**（4 个）：`get_operation`, `svc._get_template_and_group_for_op`, `lower`, `strip`

### `_normalize_batch_op_status()` [私有]
- 位置：第 45-60 行
- 参数：svc, value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_ensure_internal_operation_editable()` [私有]
- 位置：第 63-67 行
- 参数：op
- 返回类型：Constant(value=None, kind=None)

### `_validate_machine_available()` [私有]
- 位置：第 70-77 行
- 参数：svc, mc_id
- 返回类型：Constant(value=None, kind=None)

### `_validate_operator_available()` [私有]
- 位置：第 80-87 行
- 参数：svc, operator_id_text
- 返回类型：Constant(value=None, kind=None)

### `_validate_operator_machine_match()` [私有]
- 位置：第 90-100 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)

### `_normalize_hours()` [私有]
- 位置：第 103-110 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `update_internal_operation()` [公开]
- 位置：第 113-158 行
- 参数：svc, op_id, machine_id, operator_id, setup_hours, unit_hours, status
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_ops.py:22` [Route] `sch_svc.update_internal_operation(`
  - `core/services/scheduler/schedule_service.py:142` [Service] `return op_edit.update_internal_operation(`
- **被调用者**（13 个）：`get_operation`, `_ensure_internal_operation_editable`, `svc._normalize_text`, `_validate_machine_available`, `_validate_operator_available`, `_validate_operator_machine_match`, `_normalize_hours`, `svc._get_op_or_raise`, `float`, `_normalize_batch_op_status`, `transaction`, `update`, `int`

### `update_external_operation()` [公开]
- 位置：第 161-217 行
- 参数：svc, op_id, supplier_id, ext_days, status
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_ops.py:34` [Route] `sch_svc.update_external_operation(op_id=op_id, supplier_id=supplier_id, ext_days`
  - `core/services/scheduler/schedule_service.py:162` [Service] `return op_edit.update_external_operation(`
- **被调用者**（17 个）：`get_operation`, `svc._normalize_text`, `svc._get_template_and_group_for_op`, `svc._get_op_or_raise`, `BusinessError`, `lower`, `ValidationError`, `get`, `svc._normalize_float`, `float`, `_normalize_batch_op_status`, `transaction`, `update`, `int`, `strip`

## core/services/scheduler/resource_pool_builder.py（Service 层）

### `_skill_rank()` [私有]
- 位置：第 12-37 行
- 参数：v
- 返回类型：Name(id='int', ctx=Load())

### `_active_machine_ids()` [私有]
- 位置：第 40-41 行
- 参数：machines
- 返回类型：Name(id='set', ctx=Load())

### `_op_type_ids_for_ops()` [私有]
- 位置：第 44-50 行
- 参数：algo_ops
- 返回类型：Name(id='set', ctx=Load())

### `_machines_by_op_type()` [私有]
- 位置：第 53-68 行
- 参数：machines
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_active_operator_ids()` [私有]
- 位置：第 71-72 行
- 参数：svc
- 返回类型：Name(id='set', ctx=Load())

### `_build_operator_machine_maps()` [私有]
- 位置：第 75-101 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_sort_operators_by_machine()` [私有]
- 位置：第 104-110 行
- 参数：operators_by_machine
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `load_machine_downtimes()` [公开]
- 位置：第 113-171 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:330` [Service] `downtime_map = load_machine_downtimes(`
- **被调用者**（13 个）：`MachineDowntimeRepository`, `svc._format_dt`, `sorted`, `dt_repo.list_active_after`, `getattr`, `strip`, `svc._normalize_datetime`, `intervals.sort`, `str`, `intervals.append`, `warnings.append`, `warning`, `lower`

### `build_resource_pool()` [公开]
- 位置：第 174-229 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:339` [Service] `resource_pool, pool_warnings = build_resource_pool(self, cfg=cfg, algo_ops=algo_`
- **被调用者**（12 个）：`to_yes_no`, `list`, `_active_machine_ids`, `_op_type_ids_for_ops`, `_machines_by_op_type`, `_active_operator_ids`, `list_simple_rows`, `_build_operator_machine_maps`, `_sort_operators_by_machine`, `getattr`, `warnings.append`, `warning`

### `extend_downtime_map_for_resource_pool()` [公开]
- 位置：第 232-293 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:352` [Service] `downtime_map = extend_downtime_map_for_resource_pool(`
- **被调用者**（16 个）：`to_yes_no`, `MachineDowntimeRepository`, `svc._format_dt`, `sorted`, `getattr`, `isinstance`, `dt_repo.list_active_after`, `resource_pool.get`, `strip`, `svc._normalize_datetime`, `intervals.sort`, `str`, `keys`, `intervals.append`, `warnings.append`

## core/services/scheduler/schedule_persistence.py（Service 层）

### `_build_schedule_rows()` [私有]
- 位置：第 10-33 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_scheduled_op_ids()` [私有]
- 位置：第 36-37 行
- 参数：results
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Index(valu

### `_assigned_by_op_id()` [私有]
- 位置：第 40-47 行
- 参数：results
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_maybe_persist_auto_assign_resources()` [私有]
- 位置：第 50-71 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)

### `_persist_operation_statuses()` [私有]
- 位置：第 74-97 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)

### `_persist_batch_statuses()` [私有]
- 位置：第 100-118 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)

### `_persist_schedule_history()` [私有]
- 位置：第 121-142 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)

### `_log_schedule_operation()` [私有]
- 位置：第 145-184 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)

### `persist_schedule()` [公开]
- 位置：第 187-265 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:440` [Service] `persist_schedule(`
- **被调用者**（12 个）：`_build_schedule_rows`, `_log_schedule_operation`, `transaction`, `_persist_schedule_history`, `int`, `bulk_create`, `_scheduled_op_ids`, `_assigned_by_op_id`, `_persist_operation_statuses`, `_persist_batch_statuses`, `to_yes_no`, `getattr`

## core/services/scheduler/schedule_summary.py（Service 层）

### `_serialize_end_date()` [私有]
- 位置：第 13-26 行
- 参数：end_date
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_finish_time_by_batch()` [私有]
- 位置：第 29-38 行
- 参数：results
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_overdue_items()` [私有]
- 位置：第 41-88 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_compute_result_status()` [私有]
- 位置：第 91-100 行
- 参数：summary
- 返回类型：Name(id='str', ctx=Load())

### `_frozen_batch_ids()` [私有]
- 位置：第 103-110 行
- 参数：operations
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_extract_freeze_warnings()` [私有]
- 位置：第 113-123 行
- 参数：summary
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_compute_downtime_degradation()` [私有]
- 位置：第 126-150 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_hard_constraints()` [私有]
- 位置：第 153-163 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `build_result_summary()` [公开]
- 位置：第 166-270 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:413` [Service] `overdue_items, result_status, result_summary_obj, result_summary_json, time_cost`
- **被调用者**（18 个）：`_finish_time_by_batch`, `_build_overdue_items`, `_compute_result_status`, `int`, `_frozen_batch_ids`, `_extract_freeze_warnings`, `_compute_downtime_degradation`, `_hard_constraints`, `json.dumps`, `getattr`, `bool`, `list`, `svc._format_dt`, `_serialize_end_date`, `len`

## data/repositories/batch_material_repo.py（Repository 层）

### `BatchMaterialRepository.get()` [公开]
- 位置：第 20-25 行
- 参数：bm_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self.fetchone`, `BatchMaterial.from_row`, `int`

### `BatchMaterialRepository.exists()` [公开]
- 位置：第 27-33 行
- 参数：batch_id, material_id
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bool`, `self.fetchvalue`, `str`

### `BatchMaterialRepository.list_by_batch()` [公开]
- 位置：第 35-40 行
- 参数：batch_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（5 处）：
  - `core/services/material/batch_material_service.py:141` [Service] `rows = self.repo.list_by_batch(batch_id)`
  - `core/services/scheduler/batch_copy.py:32` [Service] `ops = svc.batch_op_repo.list_by_batch(src)`
  - `core/services/scheduler/batch_service.py:480` [Service] `return self.batch_op_repo.list_by_batch(bid)`
  - `core/services/scheduler/operation_edit_service.py:15` [Service] `return svc.op_repo.list_by_batch(bid)`
  - `core/services/scheduler/schedule_service.py:284` [Service] `operations.extend(self.op_repo.list_by_batch(bid))`
- **被调用者**（3 个）：`self.fetchall`, `BatchMaterial.from_row`, `str`

### `BatchMaterialRepository.list_with_material_details_by_batch()` [公开]
- 位置：第 42-53 行
- 参数：batch_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/material/batch_material_service.py:47` [Service] `return self.repo.list_with_material_details_by_batch(bid)`
- **被调用者**（2 个）：`self.fetchall`, `str`

### `BatchMaterialRepository.add()` [公开]
- 位置：第 55-70 行
- 参数：batch_id, material_id
- 返回类型：Name(id='BatchMaterial', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`self.execute`, `BatchMaterial`, `str`, `float`, `int`

### `BatchMaterialRepository.update_qty()` [公开]
- 位置：第 72-102 行
- 参数：bm_id
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（1 处）：
  - `core/services/material/batch_material_service.py:97` [Service] `self.repo.update_qty(bid_int, required_qty=req, available_qty=avail, ready_statu`
- **被调用者**（8 个）：`params.append`, `self.execute`, `int`, `tuple`, `set_parts.append`, `join`, `getattr`, `updates.get`

### `BatchMaterialRepository.delete()` [公开]
- 位置：第 104-105 行
- 参数：bm_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self.execute`, `int`

### `BatchMaterialRepository.delete_by_batch()` [公开]
- 位置：第 107-109 行
- 参数：batch_id
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/batch_template_ops.py:35` [Service] `svc.batch_op_repo.delete_by_batch(batch_id)`
- **被调用者**（4 个）：`self.execute`, `int`, `str`, `getattr`

## data/repositories/operator_machine_repo.py（Repository 层）

### `OperatorMachineRepository.get()` [公开]
- 位置：第 13-18 行
- 参数：link_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self.fetchone`, `OperatorMachine.from_row`

### `OperatorMachineRepository.exists()` [公开]
- 位置：第 20-26 行
- 参数：operator_id, machine_id
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/operation_edit_service.py:93` [Service] `if svc.operator_machine_repo.exists(operator_id_text, mc_id):`
- **被调用者**（2 个）：`bool`, `self.fetchvalue`

### `OperatorMachineRepository.list_by_operator()` [公开]
- 位置：第 28-33 行
- 参数：operator_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/personnel_pages.py:92` [Route] `links = link_svc.list_by_operator(operator_id)`
  - `core/services/personnel/operator_machine_service.py:294` [Service] `return self.repo.list_by_operator(op_id)`
  - `core/services/scheduler/calendar_admin.py:205` [Service] `return self.operator_calendar_repo.list_by_operator(op_id)`
- **被调用者**（2 个）：`self.fetchall`, `OperatorMachine.from_row`

### `OperatorMachineRepository.list_by_machine()` [公开]
- 位置：第 35-40 行
- 参数：machine_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/equipment_pages.py:114` [Route] `links = link_svc.list_by_machine(machine_id)`
  - `web/routes/equipment_pages.py:115` [Route] `downtimes = dt_svc.list_by_machine(machine_id, include_cancelled=False)`
  - `core/services/equipment/machine_downtime_service.py:76` [Service] `return self.repo.list_by_machine(mc_id, include_cancelled=include_cancelled)`
  - `core/services/personnel/operator_machine_service.py:300` [Service] `return self.repo.list_by_machine(mc_id)`
- **被调用者**（2 个）：`self.fetchall`, `OperatorMachine.from_row`

### `OperatorMachineRepository.list_simple_rows()` [公开]
- 位置：第 42-46 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `web/routes/equipment_excel_links.py:260` [Route] `rows = q.list_simple_rows()`
  - `web/routes/personnel_excel_links.py:248` [Route] `rows = q.list_simple_rows()`
  - `web/routes/personnel_pages.py:28` [Route] `link_rows = OperatorMachineQueryService(g.db, op_logger=getattr(g, "op_logger", `
  - `core/services/personnel/operator_machine_query_service.py:24` [Service] `return self.repo.list_simple_rows()`
  - `core/services/personnel/operator_machine_service.py:96` [Service] `existing_links = self.repo.list_simple_rows()`
  - `core/services/scheduler/resource_pool_builder.py:205` [Service] `rows = svc.operator_machine_repo.list_simple_rows()`
- **被调用者**（1 个）：`self.fetchall`

### `OperatorMachineRepository.list_with_names_by_machine()` [公开]
- 位置：第 48-63 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/equipment_excel_links.py:28` [Route] `rows = q.list_with_names_by_machine()`
  - `web/routes/equipment_excel_links.py:96` [Route] `existing_rows = q.list_with_names_by_machine()`
  - `web/routes/equipment_excel_links.py:154` [Route] `existing_rows = q.list_with_names_by_machine()`
  - `core/services/personnel/operator_machine_query_service.py:27` [Service] `return self.repo.list_with_names_by_machine()`
- **被调用者**（1 个）：`self.fetchall`

### `OperatorMachineRepository.list_with_names_by_operator()` [公开]
- 位置：第 65-80 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/personnel_excel_links.py:29` [Route] `rows = q.list_with_names_by_operator()`
  - `web/routes/personnel_excel_links.py:83` [Route] `existing_rows = q.list_with_names_by_operator()`
  - `web/routes/personnel_excel_links.py:142` [Route] `existing_rows = q.list_with_names_by_operator()`
  - `core/services/personnel/operator_machine_query_service.py:30` [Service] `return self.repo.list_with_names_by_operator()`
- **被调用者**（1 个）：`self.fetchall`

### `OperatorMachineRepository.list_links_with_machine_names()` [公开]
- 位置：第 82-90 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`self.fetchall`

### `OperatorMachineRepository.list_links_with_operator_info()` [公开]
- 位置：第 92-100 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:40` [Route] `link_rows = om_q.list_links_with_operator_info()`
  - `core/services/personnel/operator_machine_query_service.py:33` [Service] `return self.repo.list_links_with_operator_info()`
- **被调用者**（1 个）：`self.fetchall`

### `OperatorMachineRepository.list_simple_rows_for_machine_operator_sets()` [公开]
- 位置：第 102-118 行
- 参数：machine_ids, operator_ids
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/scheduler_batch_detail.py:159` [Route] `link_rows = om_q.list_simple_rows_for_machine_operator_sets(m_list, o_list)`
  - `core/services/personnel/operator_machine_query_service.py:40` [Service] `return self.repo.list_simple_rows_for_machine_operator_sets(machine_ids, operato`
- **被调用者**（6 个）：`join`, `self.fetchall`, `strip`, `tuple`, `len`, `str`

### `OperatorMachineRepository.add()` [公开]
- 位置：第 120-137 行
- 参数：operator_id, machine_id, skill_level, is_primary
- 返回类型：Name(id='OperatorMachine', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self.execute`, `OperatorMachine`, `int`

### `OperatorMachineRepository.remove()` [公开]
- 位置：第 139-143 行
- 参数：operator_id, machine_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`self.execute`

### `OperatorMachineRepository.delete_all()` [公开]
- 位置：第 145-148 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（9 处）：
  - `core/services/equipment/machine_excel_import_service.py:56` [Service] `self.repo.delete_all()`
  - `core/services/personnel/operator_excel_import_service.py:41` [Service] `self.repo.delete_all()`
  - `core/services/personnel/operator_machine_service.py:424` [Service] `self.repo.delete_all()`
  - `core/services/process/op_type_excel_import_service.py:40` [Service] `self.repo.delete_all()`
  - `core/services/process/part_service.py:165` [Service] `self.part_repo.delete_all()`
  - `core/services/process/supplier_excel_import_service.py:51` [Service] `self.repo.delete_all()`
  - `core/services/scheduler/batch_service.py:366` [Service] `self.batch_repo.delete_all()`
  - `core/services/scheduler/calendar_admin.py:189` [Service] `self.repo.delete_all()`
  - `core/services/scheduler/calendar_admin.py:296` [Service] `self.operator_calendar_repo.delete_all()`
- **被调用者**（3 个）：`self.execute`, `int`, `getattr`

### `OperatorMachineRepository.delete()` [公开]
- 位置：第 150-151 行
- 参数：link_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`self.execute`

### `OperatorMachineRepository.update_fields()` [公开]
- 位置：第 153-162 行
- 参数：operator_id, machine_id
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（2 处）：
  - `core/services/personnel/operator_machine_service.py:373` [Service] `self.repo.update_fields(op_id, mc_id, skill_level=skill_norm, is_primary=primary`
  - `core/services/personnel/operator_machine_service.py:470` [Service] `self.repo.update_fields(op_id, mc_id, skill_level=new_skill, is_primary=new_prim`
- **被调用者**（3 个）：`self.execute`, `int`, `getattr`

### `OperatorMachineRepository.clear_primary_for_operator()` [公开]
- 位置：第 164-166 行
- 参数：operator_id
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（4 处）：
  - `core/services/personnel/operator_machine_service.py:329` [Service] `self.repo.clear_primary_for_operator(op_id)`
  - `core/services/personnel/operator_machine_service.py:372` [Service] `self.repo.clear_primary_for_operator(op_id)`
  - `core/services/personnel/operator_machine_service.py:469` [Service] `self.repo.clear_primary_for_operator(op_id)`
  - `core/services/personnel/operator_machine_service.py:475` [Service] `self.repo.clear_primary_for_operator(op_id)`
- **被调用者**（3 个）：`self.execute`, `int`, `getattr`

## web/routes/dashboard.py（Route 层）

### `index()` [公开]
- 位置：第 15-59 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `BatchService`, `ScheduleHistoryQueryService`, `len`, `history_q.list_recent`, `isinstance`, `render_template`, `batch_svc.list`, `latest_summary.get`, `getattr`, `overdue_payload.get`, `json.loads`, `int`

## web/routes/excel_demo.py（Route 层）

### `_fetch_existing_operators()` [私有]
- 位置：第 24-26 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_parse_mode()` [私有]
- 位置：第 29-30 行
- 参数：value
- 返回类型：Name(id='ImportMode', ctx=Load())

### `_validate_operator_row()` [私有]
- 位置：第 33-46 行
- 参数：row
- 返回类型：Name(id='str', ctx=Load())

### `index()` [公开]
- 位置：第 50-63 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`bp.get`, `_fetch_existing_operators`, `render_template`, `list`, `url_for`, `existing.values`

### `preview()` [公开]
- 位置：第 67-149 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（30 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `file.read`, `io.BytesIO`, `tmp.seek`, `OpenpyxlBackend`, `_fetch_existing_operators`, `ExcelService`, `svc.preview_import`, `int`, `log_excel_import`, `render_template`, `ValidationError`

### `confirm()` [公开]
- 位置：第 153-227 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（29 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_fetch_existing_operators`, `OpenpyxlBackend`, `ExcelService`, `svc.preview_import`, `OperatorExcelImportService`, `import_svc.apply_preview_rows`, `int`, `log_excel_import`, `flash`, `redirect`, `ValidationError`

### `download_template()` [公开]
- 位置：第 231-285 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `openpyxl.Workbook`, `ws.append`, `io.BytesIO`, `wb.save`, `output.seek`, `int`, `log_excel_export`, `send_file`

## web/routes/personnel_excel_operators.py（Route 层）

### `_validate_operator_excel_row()` [私有]
- 位置：第 23-35 行
- 参数：row
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `excel_operator_page()` [公开]
- 位置：第 44-60 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.get`, `OperatorService`, `op_svc.build_existing_for_excel`, `render_template`, `getattr`, `list`, `url_for`, `existing.values`

### `excel_operator_preview()` [公开]
- 位置：第 64-110 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `OperatorService`, `op_svc.build_existing_for_excel`, `ExcelService`, `svc.preview_import`, `int`, `log_excel_import`, `render_template`, `ValidationError`, `getattr`

### `excel_operator_confirm()` [公开]
- 位置：第 114-192 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（31 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_ensure_unique_ids`, `OperatorService`, `op_svc.build_existing_for_excel`, `ExcelService`, `excel_svc.preview_import`, `OperatorExcelImportService`, `import_svc.apply_preview_rows`, `int`, `log_excel_import`, `flash`, `redirect`

### `excel_operator_template()` [公开]
- 位置：第 196-248 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `openpyxl.Workbook`, `ws.append`, `io.BytesIO`, `wb.save`, `output.seek`, `int`, `log_excel_export`, `send_file`, `getattr`

### `excel_operator_export()` [公开]
- 位置：第 252-290 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（17 个）：`bp.get`, `time.time`, `build_existing_for_excel`, `list`, `openpyxl.Workbook`, `ws.append`, `io.BytesIO`, `wb.save`, `output.seek`, `int`, `log_excel_export`, `send_file`, `existing.values`, `OperatorService`, `getattr`

## web/routes/process_excel_part_operation_hours.py（Route 层）

### `_part_op_hours_mode_options()` [私有]
- 位置：第 34-35 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_parse_seq()` [私有]
- 位置：第 38-58 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_build_existing_internal()` [私有]
- 位置：第 61-93 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_normalize_rows()` [私有]
- 位置：第 96-110 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_build_validator()` [私有]
- 位置：第 113-145 行
- 参数：meta_all
- 返回类型：无注解

### `_build_existing_for_append()` [私有]
- 位置：第 148-160 行
- 参数：existing_internal
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_rewrite_append_preview_rows()` [私有]
- 位置：第 163-173 行
- 参数：preview_rows, mode
- 返回类型：Constant(value=None, kind=None)

### `excel_part_op_hours_page()` [公开]
- 位置：第 177-192 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `_build_existing_internal`, `render_template`, `url_for`, `_part_op_hours_mode_options`

### `excel_part_op_hours_preview()` [公开]
- 位置：第 196-248 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（22 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_normalize_rows`, `_ensure_unique_ids`, `_build_existing_internal`, `_build_validator`, `ExcelService`, `excel_svc.preview_import`, `_rewrite_append_preview_rows`, `int`, `log_excel_import`, `render_template`

### `excel_part_op_hours_confirm()` [公开]
- 位置：第 252-330 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（30 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_ensure_unique_ids`, `_build_existing_internal`, `_build_validator`, `ExcelService`, `excel_svc.preview_import`, `_rewrite_append_preview_rows`, `PartOperationHoursExcelImportService`, `import_svc.apply_preview_rows`, `int`, `log_excel_import`, `flash`

### `excel_part_op_hours_template()` [公开]
- 位置：第 334-386 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `openpyxl.Workbook`, `ws.append`, `io.BytesIO`, `wb.save`, `output.seek`, `int`, `log_excel_export`, `send_file`, `getattr`

### `excel_part_op_hours_export()` [公开]
- 位置：第 390-425 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.get`, `time.time`, `PartOperationQueryService`, `q.list_internal_active_hours`, `openpyxl.Workbook`, `ws.append`, `io.BytesIO`, `wb.save`, `output.seek`, `int`, `log_excel_export`, `send_file`, `getattr`, `len`, `float`

## web/routes/scheduler_analysis.py（Route 层）

### `analysis_page()` [公开]
- 位置：第 16-45 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `ScheduleHistoryQueryService`, `q.list_versions`, `strip`, `q.list_recent`, `build_analysis_context`, `render_template`, `q.get_by_version`, `getattr`, `int`, `get`, `ValidationError`, `safe_int`

## web/routes/system_logs.py（Route 层）

### `logs_page()` [公开]
- 位置：第 18-67 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（17 个）：`bp.get`, `get`, `parse_page_args`, `_safe_int`, `_normalize_time_range`, `OperationLogService`, `svc.list_recent`, `build_operation_log_view_rows`, `paginate_rows`, `render_template`, `strip`, `getattr`, `to_dict`, `_get_job_state_map`, `int`

### `logs_settings()` [公开]
- 位置：第 71-79 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.post`, `SystemConfigService`, `svc.update_logs_settings`, `flash`, `redirect`, `url_for`, `get`

### `logs_delete()` [公开]
- 位置：第 83-106 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.post`, `strip`, `delete_by_id`, `flash`, `redirect`, `int`, `url_for`, `OperationLogService`, `get`, `getattr`

### `logs_delete_batch()` [公开]
- 位置：第 110-130 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `getlist`, `delete_by_ids`, `flash`, `redirect`, `url_for`, `ids.append`, `OperationLogService`, `int`, `strip`, `getattr`, `str`

## web/viewmodels/scheduler_analysis_vm.py（Other 层）

### `safe_float()` [公开]
- 位置：第 7-13 行
- 参数：v, default
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`float`, `strip`, `str`

### `safe_int()` [公开]
- 位置：第 16-22 行
- 参数：v, default
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_analysis.py:34` [Route] `selected_ver = safe_int((versions[0] or {}).get("version"), default=0) or None`
- **被调用者**（4 个）：`int`, `float`, `strip`, `str`

### `extract_metrics_from_summary()` [公开]
- 位置：第 25-31 行
- 参数：summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`isinstance`, `summary.get`, `algo.get`

### `build_svg_polyline()` [公开]
- 位置：第 34-76 行
- 参数：values
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`min`, `max`, `float`, `join`, `len`, `pts.append`, `int`, `round`

### `score_key()` [公开]
- 位置：第 79-92 行
- 参数：score
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`tuple`, `isinstance`, `float`, `out.append`

### `_safe_load_json()` [私有]
- 位置：第 95-105 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_objective_key_from_algo_objective()` [私有]
- 位置：第 108-114 行
- 参数：obj
- 返回类型：Name(id='str', ctx=Load())

### `_metric_value()` [私有]
- 位置：第 117-121 行
- 参数：row, key
- 返回类型：Name(id='float', ctx=Load())

### `build_trend_rows()` [公开]
- 位置：第 124-158 行
- 参数：raw_hist
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`sorted`, `safe_int`, `_safe_load_json`, `by_ver.values`, `d.get`, `extract_metrics_from_summary`, `isinstance`, `summary.get`, `int`, `algo.get`, `len`, `hasattr`, `h.to_dict`, `x.get`

### `build_trend_charts()` [公开]
- 位置：第 161-175 行
- 参数：trend_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`build_svg_polyline`, `_metric_value`

### `build_selected_details()` [公开]
- 位置：第 178-258 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（25 个）：`_safe_load_json`, `_objective_key_from_algo_objective`, `isinstance`, `extract_metrics_from_summary`, `selected_summary.get`, `algo.get`, `len`, `trace_values.sort`, `build_svg_polyline`, `reversed`, `hasattr`, `selected_item.to_dict`, `selected.get`, `attempts_rows.append`, `safe_int`

### `sort_and_enrich_attempts()` [公开]
- 位置：第 261-278 行
- 参数：attempts_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`sorted`, `max`, `isinstance`, `safe_float`, `r.get`, `float`, `score_key`, `selected_metrics.get`, `round`

### `build_analysis_context()` [公开]
- 位置：第 281-309 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/scheduler_analysis.py:38` [Route] `ctx = build_analysis_context(selected_ver=selected_ver, raw_hist=raw_hist, selec`
- **被调用者**（4 个）：`build_trend_rows`, `build_trend_charts`, `build_selected_details`, `sort_and_enrich_attempts`

## web/viewmodels/system_logs_vm.py（Other 层）

### `_safe_load_detail_obj()` [私有]
- 位置：第 7-17 行
- 参数：detail_raw
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `build_operation_log_view_rows()` [公开]
- 位置：第 20-34 行
- 参数：items
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/system_logs.py:39` [Route] `view_rows = build_operation_log_view_rows(items)`
- **被调用者**（6 个）：`_safe_load_detail_obj`, `out.append`, `d.get`, `hasattr`, `it.to_dict`, `isinstance`

---
- 分析函数/方法数：407
- 找到调用关系：748 处
- 跨层边界风险：7 项
