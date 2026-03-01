# 引用链追踪报告（深度 Review 辅助）

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/services/common/excel_import_executor.py（Service 层）

### `ImportExecutionStats.to_dict()` [公开]
- 位置：第 20-27 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（61 处）：
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
  - `web/routes/scheduler_analysis.py:50` [Route] `d = h.to_dict()`
  - `web/routes/scheduler_analysis.py:104` [Route] `selected = item.to_dict()`
  - `web/routes/scheduler_batches.py:41` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:64` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:113` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:177` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:221` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/system_backup.py:39` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:35` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:42` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:41` [Route] `d = it.to_dict()`
  - `web/routes/system_logs.py:65` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:142` [Route] `d = it.to_dict()`
  - `core/services/common/pandas_backend.py:25` [Service] `raw_rows = df.to_dict(orient="records")`
  - `core/services/equipment/machine_excel_import_service.py:95` [Service] `out = stats.to_dict()`
  - `core/services/material/material_service.py:81` [Service] `self.op_logger.info(module="material", action="create", target_type="material", `
  - `core/services/personnel/operator_excel_import_service.py:78` [Service] `out = stats.to_dict()`
  - `core/services/process/op_type_excel_import_service.py:85` [Service] `out = stats.to_dict()`
  - `core/services/process/route_parser.py:55` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:75` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:76` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
  - `core/services/process/supplier_excel_import_service.py:108` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:100` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:255` [Service] `self.batch_repo.create(b.to_dict())`
  - `core/services/scheduler/calendar_admin.py:169` [Service] `self.upsert_no_tx(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:180` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:275` [Service] `self.upsert_operator_calendar_no_tx(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:284` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:208` [Service] `result = stats.to_dict()`
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
  - `core/services/scheduler/schedule_summary.py:196` [Service] `"metrics": best_metrics.to_dict() if best_metrics is not None else None,`
- **被调用者**（2 个）：`int`, `list`

### `_append_error_sample()` [私有]
- 位置：第 30-41 行
- 参数：stats
- 返回类型：Constant(value=None, kind=None)

### `_should_skip_before_row_id()` [私有]
- 位置：第 44-62 行
- 参数：stats
- 返回类型：Name(id='bool', ctx=Load())

### `_should_skip_after_row_id()` [私有]
- 位置：第 65-75 行
- 参数：stats
- 返回类型：Name(id='bool', ctx=Load())

### `_apply_one_row()` [私有]
- 位置：第 78-103 行
- 参数：stats
- 返回类型：Constant(value=None, kind=None)

### `execute_preview_rows_transactional()` [公开]
- 位置：第 106-163 行
- 参数：conn
- 返回类型：Name(id='ImportExecutionStats', ctx=Load())
- **调用者**（6 处）：
  - `core/services/equipment/machine_excel_import_service.py:81` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/personnel/operator_excel_import_service.py:64` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/process/op_type_excel_import_service.py:70` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/process/supplier_excel_import_service.py:93` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/scheduler/batch_excel_import.py:90` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/scheduler/calendar_service.py:198` [Service] `stats = execute_preview_rows_transactional(`
- **被调用者**（12 个）：`ImportExecutionStats`, `TransactionManager`, `tx.transaction`, `replace_existing_no_tx`, `existing_row_ids.clear`, `_should_skip_before_row_id`, `strip`, `_should_skip_after_row_id`, `_apply_one_row`, `_append_error_sample`, `str`, `row_id_getter`

## core/services/common/excel_validators.py（Service 层）

### `_normalize_batch_priority()` [私有]
- 位置：第 12-20 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_ready_status()` [私有]
- 位置：第 23-31 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_operator_calendar_day_type()` [私有]
- 位置：第 34-42 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_yesno()` [私有]
- 位置：第 45-52 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_batch_date_cell()` [私有]
- 位置：第 55-81 行
- 参数：value, field_label
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `get_batch_row_validate_and_normalize()` [公开]
- 位置：第 84-133 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='Callable', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/routes/scheduler_excel_batches.py:183` [Route] `validate_row = get_batch_row_validate_and_normalize(g.db, parts_cache=parts, inp`
  - `web/routes/scheduler_excel_batches.py:258` [Route] `validate_row = get_batch_row_validate_and_normalize(g.db, parts_cache=parts, inp`
- **被调用者**（13 个）：`isinstance`, `strip`, `target.get`, `_normalize_batch_priority`, `_normalize_ready_status`, `_normalize_batch_date_cell`, `ready_res.get`, `due_res.get`, `dict`, `int`, `str`, `list`, `PartRepository`

### `get_operator_calendar_row_validate_and_normalize()` [公开]
- 位置：第 136-228 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='Callable', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/routes/personnel_excel_operator_calendar.py:129` [Route] `validate_row = get_operator_calendar_row_validate_and_normalize(`
  - `web/routes/personnel_excel_operator_calendar.py:240` [Route] `validate_row = get_operator_calendar_row_validate_and_normalize(`
- **被调用者**（14 个）：`OperatorRepository`, `float`, `strip`, `_normalize_operator_calendar_day_type`, `target.get`, `_normalize_yesno`, `dict`, `repo.exists`, `normalize_date`, `normalize_hhmm`, `str`, `datetime.strptime`, `total_seconds`, `timedelta`

## core/services/common/excel_audit.py（Service 层）

### `_calc_stats_from_preview()` [私有]
- 位置：第 8-28 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `log_excel_import()` [公开]
- 位置：第 31-91 行
- 参数：op_logger, module, target_type, filename, mode, preview_or_result, time_cost_ms, errors_sample, file_hash, target_id
- 返回类型：无注解
- **调用者**（24 处）：
  - `web/routes/equipment_excel_links.py:84` [Route] `log_excel_import(`
  - `web/routes/equipment_excel_links.py:184` [Route] `log_excel_import(`
  - `web/routes/equipment_excel_machines.py:205` [Route] `log_excel_import(`
  - `web/routes/equipment_excel_machines.py:294` [Route] `log_excel_import(`
  - `web/routes/excel_demo.py:126` [Route] `log_excel_import(`
  - `web/routes/excel_demo.py:211` [Route] `log_excel_import(`
  - `web/routes/personnel_excel_links.py:71` [Route] `log_excel_import(`
  - `web/routes/personnel_excel_links.py:172` [Route] `log_excel_import(`
  - `web/routes/personnel_excel_operators.py:87` [Route] `log_excel_import(`
  - `web/routes/personnel_excel_operators.py:177` [Route] `log_excel_import(`
  - `web/routes/personnel_excel_operator_calendar.py:146` [Route] `log_excel_import(`
  - `web/routes/personnel_excel_operator_calendar.py:288` [Route] `log_excel_import(`
  - `web/routes/process_excel_op_types.py:91` [Route] `log_excel_import(`
  - `web/routes/process_excel_op_types.py:193` [Route] `log_excel_import(`
  - `web/routes/process_excel_part_operation_hours.py:225` [Route] `log_excel_import(`
  - `web/routes/process_excel_part_operation_hours.py:360` [Route] `log_excel_import(`
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
- 返回类型：无注解
- **调用者**（37 处）：
  - `web/routes/equipment_excel_links.py:207` [Route] `log_excel_export(`
  - `web/routes/equipment_excel_links.py:237` [Route] `log_excel_export(`
  - `web/routes/equipment_excel_links.py:277` [Route] `log_excel_export(`
  - `web/routes/equipment_excel_machines.py:317` [Route] `log_excel_export(`
  - `web/routes/equipment_excel_machines.py:347` [Route] `log_excel_export(`
  - `web/routes/equipment_excel_machines.py:386` [Route] `log_excel_export(`
  - `web/routes/excel_demo.py:237` [Route] `log_excel_export(`
  - `web/routes/excel_demo.py:267` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_links.py:195` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_links.py:225` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_links.py:265` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_operators.py:201` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_operators.py:231` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_operators.py:273` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_operator_calendar.py:308` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_operator_calendar.py:338` [Route] `log_excel_export(`
  - `web/routes/personnel_excel_operator_calendar.py:389` [Route] `log_excel_export(`
  - `web/routes/process_excel_op_types.py:213` [Route] `log_excel_export(`
  - `web/routes/process_excel_op_types.py:244` [Route] `log_excel_export(`
  - `web/routes/process_excel_op_types.py:283` [Route] `log_excel_export(`
  - `web/routes/process_excel_part_operations.py:64` [Route] `log_excel_export(`
  - `web/routes/process_excel_part_operation_hours.py:387` [Route] `log_excel_export(`
  - `web/routes/process_excel_part_operation_hours.py:418` [Route] `log_excel_export(`
  - `web/routes/process_excel_part_operation_hours.py:457` [Route] `log_excel_export(`
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

---
- 分析函数/方法数：16
- 找到调用关系：132 处
- 跨层边界风险：0 项

