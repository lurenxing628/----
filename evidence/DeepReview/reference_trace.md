# 引用链追踪报告（深度 Review 辅助）

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/infrastructure/database.py（Infrastructure 层）

### `_is_windows_lock_error()` [私有]
- 位置：第 14-23 行
- 参数：e
- 返回类型：Name(id='bool', ctx=Load())

### `_cleanup_sqlite_sidecars()` [私有]
- 位置：第 26-38 行
- 参数：db_path, logger
- 返回类型：Constant(value=None, kind=None)

### `_restore_db_file_from_backup()` [私有]
- 位置：第 41-87 行
- 参数：backup_path, db_path, logger, retries, base_delay_s
- 返回类型：Constant(value=None, kind=None)

### `get_connection()` [公开]
- 位置：第 90-107 行
- 参数：db_path
- 返回类型：Attribute(value=Name(id='sqlite3', ctx=Load()), attr='Connec
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`dirname`, `sqlite3.connect`, `conn.execute`, `os.makedirs`

### `ensure_schema()` [公开]
- 位置：第 110-192 行
- 参数：db_path, logger, schema_path, backup_dir
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/system_backup.py:222` [Route] `ensure_schema(`
- **被调用者**（22 个）：`abspath`, `get_connection`, `candidates.append`, `FileNotFoundError`, `exists`, `_migrate_with_backup`, `join`, `getattr`, `conn.executescript`, `_ensure_schema_version`, `_get_schema_version`, `conn.commit`, `conn.close`, `dirname`, `os.getcwd`

### `_ensure_schema_version()` [私有]
- 位置：第 195-221 行
- 参数：conn, logger
- 返回类型：Constant(value=None, kind=None)

### `_detect_schema_is_current()` [私有]
- 位置：第 224-254 行
- 参数：conn
- 返回类型：Name(id='bool', ctx=Load())

### `_get_schema_version()` [私有]
- 位置：第 257-268 行
- 参数：conn
- 返回类型：Name(id='int', ctx=Load())

### `_set_schema_version()` [私有]
- 位置：第 271-272 行
- 参数：conn, version
- 返回类型：Constant(value=None, kind=None)

### `_migrate_with_backup()` [私有]
- 位置：第 275-382 行
- 参数：db_path, from_version, to_version, backup_dir, logger
- 返回类型：Constant(value=None, kind=None)

### `_run_migration()` [私有]
- 位置：第 385-389 行
- 参数：conn, target_version, logger
- 返回类型：Constant(value=None, kind=None)

## core/infrastructure/migrations/__init__.py（Infrastructure 层）

### `run_migration()` [公开]
- 位置：第 22-26 行
- 参数：conn, target_version, logger
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/infrastructure/database.py:389` [Infrastructure] `run_migration(conn, target_version=int(target_version), logger=logger)`
- **被调用者**（4 个）：`MIGRATIONS.get`, `fn`, `int`, `RuntimeError`

## core/infrastructure/migrations/v5.py（Infrastructure 层）

### `_run_update()` [私有]
- 位置：第 6-24 行
- 参数：conn, sql
- 返回类型：Constant(value=None, kind=None)

### `run()` [公开]
- 位置：第 27-58 行
- 参数：conn, logger
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`_run_update`

## core/services/common/enum_normalizers.py（Service 层）

### `_text()` [私有]
- 位置：第 8-9 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `normalize_machine_status()` [公开]
- 位置：第 12-40 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/equipment_excel_machines.py:55` [Route] `return normalize_machine_status(value)`
  - `core/services/equipment/machine_excel_import_service.py:35` [Service] `return normalize_machine_status(value)`
- **被调用者**（2 个）：`_text`, `v.lower`

### `normalize_operator_status()` [公开]
- 位置：第 43-56 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（3 处）：
  - `web/routes/excel_demo.py:42` [Route] `st = normalize_operator_status(row.get("状态"))`
  - `web/routes/personnel_excel_operators.py:30` [Route] `st = normalize_operator_status(row.get("状态"))`
  - `core/services/personnel/operator_excel_import_service.py:56` [Service] `status = normalize_operator_status(data.get("状态"))`
- **被调用者**（2 个）：`_text`, `v.lower`

### `normalize_supplier_status()` [公开]
- 位置：第 59-80 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/process_excel_suppliers.py:29` [Route] `return normalize_supplier_status(value)`
  - `core/services/process/supplier_excel_import_service.py:35` [Service] `return normalize_supplier_status(value)`
- **被调用者**（2 个）：`_text`, `v.lower`

### `normalize_op_type_category()` [公开]
- 位置：第 83-104 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/process_excel_op_types.py:29` [Route] `return normalize_op_type_category(value)`
  - `core/services/process/op_type_excel_import_service.py:56` [Service] `cat = normalize_op_type_category(data.get("归属"))`
- **被调用者**（2 个）：`_text`, `v.lower`

### `normalize_yes_no_wide()` [公开]
- 位置：第 111-131 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（3 处）：
  - `core/services/personnel/operator_machine_query_service.py:34` [Service] `out["is_primary"] = normalize_yes_no_wide(out.get("is_primary"), default=YesNo.N`
  - `core/services/scheduler/number_utils.py:59` [Service] `return normalize_yes_no_wide(value, default=default, unknown_policy="no")`
  - `core/services/system/system_config_service.py:18` [Service] `return normalize_yes_no_wide(value, default="no", unknown_policy="no")`
- **被调用者**（3 个）：`lower`, `strip`, `str`

### `normalize_yesno_narrow()` [公开]
- 位置：第 134-155 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（3 处）：
  - `web/routes/normalizers.py:75` [Route] `return normalize_yesno_narrow(value, default=YesNo.YES.value, unknown_policy="pa`
  - `core/services/common/excel_validators.py:60` [Service] `return normalize_yesno_narrow(value, default=YesNo.YES.value, unknown_policy="pa`
  - `core/services/scheduler/calendar_admin.py:96` [Service] `return normalize_yesno_narrow(v, default=YesNo.YES.value, unknown_policy="raise"`
- **被调用者**（5 个）：`v.lower`, `strip`, `ValueError`, `lower`, `str`

### `normalize_skill_level()` [公开]
- 位置：第 158-183 行
- 参数：value
- 返回类型：无注解
- **调用者**（3 处）：
  - `core/services/personnel/operator_machine_query_service.py:30` [Service] `out["skill_level"] = normalize_skill_level(out.get("skill_level"), default="norm`
  - `core/services/personnel/operator_machine_service.py:40` [Service] `return normalize_skill_level(value, default="normal", allow_none=True)`
  - `core/services/personnel/operator_machine_service.py:63` [Service] `return normalize_skill_level(value, default="normal", allow_none=False)`
- **被调用者**（4 个）：`strip`, `s0.lower`, `ValueError`, `str`

### `skill_rank()` [公开]
- 位置：第 186-206 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`normalize_skill_level`

## core/services/personnel/operator_machine_service.py（Service 层）

### `OperatorMachineService.__init__()` [私有]
- 位置：第 21-29 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `OperatorMachineService._normalize_text()` [私有]
- 位置：第 33-34 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._normalize_skill_level_optional()` [私有]
- 位置：第 37-42 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._normalize_yes_no_optional()` [私有]
- 位置：第 45-57 行
- 参数：value, field
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._normalize_skill_level_stored()` [私有]
- 位置：第 61-65 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `OperatorMachineService._normalize_yes_no_stored()` [私有]
- 位置：第 68-79 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `OperatorMachineService._normalize_link()` [私有]
- 位置：第 82-85 行
- 参数：link
- 返回类型：Name(id='OperatorMachine', ctx=Load())

### `OperatorMachineService._ensure_operator_exists()` [私有]
- 位置：第 87-89 行
- 参数：operator_id
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._ensure_machine_exists()` [私有]
- 位置：第 91-93 行
- 参数：machine_id
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._detect_optional_columns()` [私有]
- 位置：第 96-99 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._detect_optional_columns_from_preview()` [私有]
- 位置：第 102-105 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._build_existing_link_map()` [私有]
- 位置：第 107-119 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `OperatorMachineService._validate_required_ids_for_preview_row()` [私有]
- 位置：第 121-132 行
- 参数：row, row_num
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._check_duplicate_key_in_file()` [私有]
- 位置：第 135-144 行
- 参数：key
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._check_fk_exists()` [私有]
- 位置：第 146-161 行
- 参数：op_id, mc_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._parse_skill_optional_for_preview()` [私有]
- 位置：第 163-174 行
- 参数：row, row_num
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._parse_primary_optional_for_preview()` [私有]
- 位置：第 176-187 行
- 参数：row, row_num
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._build_overwrite_preview_for_existing()` [私有]
- 位置：第 189-201 行
- 参数：无
- 返回类型：Name(id='ImportPreviewRow', ctx=Load())

### `OperatorMachineService._decide_preview_row()` [私有]
- 位置：第 203-213 行
- 参数：无
- 返回类型：Name(id='ImportPreviewRow', ctx=Load())

### `OperatorMachineService._preview_one_row()` [私有]
- 位置：第 215-243 行
- 参数：无
- 返回类型：Name(id='ImportPreviewRow', ctx=Load())

### `OperatorMachineService._is_primary_yes()` [私有]
- 位置：第 246-248 行
- 参数：data
- 返回类型：Name(id='bool', ctx=Load())

### `OperatorMachineService._collect_dup_primary_yes_operators()` [私有]
- 位置：第 250-260 行
- 参数：preview
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Index(valu

### `OperatorMachineService._mark_dup_primary_yes()` [私有]
- 位置：第 263-273 行
- 参数：preview, dup_ops
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._enforce_primary_unique_in_file()` [私有]
- 位置：第 275-278 行
- 参数：preview
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._resolve_write_values()` [私有]
- 位置：第 280-303 行
- 参数：pr
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService.list_by_operator()` [公开]
- 位置：第 308-312 行
- 参数：operator_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/personnel_pages.py:93` [Route] `links = link_svc.list_by_operator(operator_id)`
  - `core/services/scheduler/calendar_admin.py:209` [Service] `return self.operator_calendar_repo.list_by_operator(op_id)`
- **被调用者**（3 个）：`self._normalize_text`, `ValidationError`, `self._normalize_link`

### `OperatorMachineService.list_by_machine()` [公开]
- 位置：第 314-318 行
- 参数：machine_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/equipment_pages.py:119` [Route] `links = link_svc.list_by_machine(machine_id)`
  - `web/routes/equipment_pages.py:120` [Route] `downtimes = dt_svc.list_by_machine(machine_id, include_cancelled=False)`
  - `core/services/equipment/machine_downtime_service.py:76` [Service] `return self.repo.list_by_machine(mc_id, include_cancelled=include_cancelled)`
- **被调用者**（3 个）：`self._normalize_text`, `ValidationError`, `self._normalize_link`

### `OperatorMachineService.add_link()` [公开]
- 位置：第 320-348 行
- 参数：operator_id, machine_id, skill_level, is_primary
- 返回类型：Name(id='OperatorMachine', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:276` [Route] `svc.add_link(operator_id=operator_id, machine_id=machine_id)`
  - `web/routes/personnel_pages.py:235` [Route] `svc.add_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（11 个）：`self._normalize_text`, `self._ensure_operator_exists`, `self._ensure_machine_exists`, `exists`, `ValidationError`, `BusinessError`, `self._normalize_skill_level_optional`, `self._normalize_yes_no_optional`, `transaction`, `add`, `clear_primary_for_operator`

### `OperatorMachineService.remove_link()` [公开]
- 位置：第 350-358 行
- 参数：operator_id, machine_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:296` [Route] `svc.remove_link(operator_id=operator_id, machine_id=machine_id)`
  - `web/routes/personnel_pages.py:256` [Route] `svc.remove_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（4 个）：`self._normalize_text`, `ValidationError`, `transaction`, `remove`

### `OperatorMachineService.update_link_fields()` [公开]
- 位置：第 360-391 行
- 参数：operator_id, machine_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:287` [Route] `svc.update_link_fields(operator_id=operator_id, machine_id=machine_id, skill_lev`
  - `web/routes/personnel_pages.py:247` [Route] `svc.update_link_fields(operator_id=operator_id, machine_id=machine_id, skill_lev`
- **被调用者**（9 个）：`self._normalize_text`, `ValidationError`, `exists`, `BusinessError`, `self._normalize_skill_level_optional`, `self._normalize_yes_no_optional`, `transaction`, `update_fields`, `clear_primary_for_operator`

### `OperatorMachineService.preview_import_links()` [公开]
- 位置：第 396-428 行
- 参数：rows, mode
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/equipment_excel_links.py:81` [Route] `preview_rows = link_svc.preview_import_links(rows=normalized_rows, mode=mode)`
  - `web/routes/equipment_excel_links.py:141` [Route] `preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)`
  - `web/routes/personnel_excel_links.py:68` [Route] `preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)`
  - `web/routes/personnel_excel_links.py:129` [Route] `preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)`
- **被调用者**（7 个）：`self._detect_optional_columns`, `self._build_existing_link_map`, `set`, `enumerate`, `self._preview_one_row`, `preview.append`, `self._enforce_primary_unique_in_file`

### `OperatorMachineService.apply_import_links()` [公开]
- 位置：第 430-505 行
- 参数：preview_rows, mode
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/equipment_excel_links.py:181` [Route] `stats = link_svc.apply_import_links(preview_rows=preview_rows, mode=mode)`
  - `web/routes/personnel_excel_links.py:169` [Route] `stats = link_svc.apply_import_links(preview_rows=preview_rows, mode=mode)`
- **被调用者**（15 个）：`self._detect_optional_columns_from_preview`, `self._build_existing_link_map`, `transaction`, `len`, `delete_all`, `strip`, `existing_map.get`, `self._resolve_write_values`, `exists`, `update_fields`, `add`, `errors_sample.append`, `str`, `clear_primary_for_operator`, `get`

## web/routes/personnel_calendar_pages.py（Route 层）

### `operator_calendar_page()` [公开]
- 位置：第 14-51 行
- 参数：operator_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（16 个）：`bp.get`, `OperatorService`, `op_svc.get`, `CalendarService`, `ConfigService`, `render_template`, `c.to_dict`, `_normalize_operator_calendar_day_type`, `_normalize_yesno`, `_day_type_zh`, `cfg_svc.get`, `getattr`, `cal_svc.list_operator_calendar`, `r.get`, `float`

### `operator_calendar_upsert()` [公开]
- 位置：第 55-84 行
- 参数：operator_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.post`, `OperatorService`, `op_svc.get`, `get`, `CalendarService`, `cal_svc.upsert_operator_calendar`, `flash`, `redirect`, `url_for`, `getattr`

## web/routes/scheduler_calendar_pages.py（Route 层）

### `calendar_page()` [公开]
- 位置：第 13-36 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `CalendarService`, `ConfigService`, `render_template`, `cfg_svc.get`, `c.to_dict`, `_normalize_day_type`, `_normalize_yesno`, `_day_type_zh`, `getattr`, `float`, `cal_svc.list_all`, `r.get`

### `calendar_upsert()` [公开]
- 位置：第 40-64 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `get`, `CalendarService`, `cal_svc.upsert`, `flash`, `redirect`, `url_for`, `getattr`

## web/routes/scheduler_excel_calendar.py（Route 层）

### `excel_calendar_page()` [公开]
- 位置：第 36-63 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.get`, `CalendarService`, `cal_svc.list_all`, `render_template`, `existing_list.append`, `getattr`, `url_for`, `_normalize_day_type`

### `excel_calendar_preview()` [公开]
- 位置：第 67-190 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（32 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `ConfigService`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `CalendarService`, `cal_svc.list_all`, `ExcelService`, `excel_svc.preview_import`, `int`, `log_excel_import`, `render_template`, `ValidationError`

### `excel_calendar_confirm()` [公开]
- 位置：第 194-365 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（40 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `ConfigService`, `_ensure_unique_ids`, `CalendarService`, `cal_svc.list_all`, `ExcelService`, `excel_svc.preview_import`, `TransactionManager`, `int`, `log_excel_import`, `flash`, `redirect`

### `excel_calendar_template()` [公开]
- 位置：第 369-418 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `openpyxl.Workbook`, `ws.append`, `io.BytesIO`, `wb.save`, `output.seek`, `int`, `log_excel_export`, `send_file`, `getattr`

### `excel_calendar_export()` [公开]
- 位置：第 422-457 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.get`, `time.time`, `CalendarService`, `cal_svc.list_all`, `openpyxl.Workbook`, `ws.append`, `io.BytesIO`, `wb.save`, `output.seek`, `int`, `log_excel_export`, `send_file`, `getattr`, `len`, `_normalize_day_type`

---
- 分析函数/方法数：64
- 找到调用关系：37 处
- 跨层边界风险：0 项
