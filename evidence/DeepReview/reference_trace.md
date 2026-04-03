# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ get_full_manual_section_url() 返回 Optional，但 web/routes/scheduler_config.py:194 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## web/bootstrap/factory.py（Other 层）

### `_apply_runtime_config()` [私有]
- 位置：第 49-57 行
- 参数：app
- 返回类型：Constant(value=None, kind=None)

### `should_use_runtime_reloader()` [公开]
- 位置：第 60-62 行
- 参数：debug, frozen
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`bool`, `getattr`

### `_should_register_exit_backup()` [私有]
- 位置：第 65-70 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `should_own_runtime_resources()` [公开]
- 位置：第 73-78 行
- 参数：debug, frozen, run_main
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_should_register_exit_backup`, `bool`

### `_is_exit_backup_enabled()` [私有]
- 位置：第 81-99 行
- 参数：bm
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_run_exit_backup()` [私有]
- 位置：第 102-121 行
- 参数：manager
- 返回类型：Name(id='bool', ctx=Load())

### `_maintenance_gate_response()` [私有]
- 位置：第 124-133 行
- 参数：无
- 返回类型：无注解

### `_default_anchor_file()` [私有]
- 位置：第 136-138 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `should_register_runtime_lifecycle_handlers()` [公开]
- 位置：第 141-142 行
- 参数：debug
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`should_own_runtime_resources`, `bool`

### `serve_runtime_app()` [公开]
- 位置：第 145-156 行
- 参数：app, host, port
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`make_server`, `int`, `server.serve_forever`

### `request_runtime_server_shutdown()` [公开]
- 位置：第 159-181 行
- 参数：logger
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/system_health.py:53` [Route] `if not request_runtime_server_shutdown(logger=current_app.logger):`
- **被调用者**（5 个）：`start`, `time.sleep`, `server.shutdown`, `threading.Thread`, `logger.warning`

### `create_app_core()` [公开]
- 位置：第 184-368 行
- 参数：无
- 返回类型：Name(id='Flask', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（51 个）：`lower`, `runtime_base_dir`, `join`, `Flask`, `from_object`, `_apply_runtime_config`, `int`, `install_versioned_url_for`, `AppLogger`, `setLevel`, `init_ui_mode`, `dirname`, `os.makedirs`, `abspath`, `ensure_schema`

## core/services/scheduler/schedule_service.py（Service 层）

### `_normalized_status_text()` [私有]
- 位置：第 43-44 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_get_snapshot_with_optional_strict_mode()` [私有]
- 位置：第 47-57 行
- 参数：cfg_svc
- 返回类型：Name(id='Any', ctx=Load())

### `ScheduleService.__init__()` [私有]
- 位置：第 69-87 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ScheduleService._normalize_text()` [私有]
- 位置：第 93-94 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleService._is_reschedulable_operation()` [私有]
- 位置：第 97-99 行
- 参数：op
- 返回类型：Name(id='bool', ctx=Load())

### `ScheduleService._normalize_float()` [私有]
- 位置：第 102-103 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleService._get_batch_or_raise()` [私有]
- 位置：第 105-109 行
- 参数：batch_id
- 返回类型：Name(id='Batch', ctx=Load())

### `ScheduleService._get_op_or_raise()` [私有]
- 位置：第 111-115 行
- 参数：op_id
- 返回类型：Name(id='BatchOperation', ctx=Load())

### `ScheduleService._get_template_and_group_for_op()` [私有]
- 位置：第 117-118 行
- 参数：op
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ScheduleService._format_dt()` [私有]
- 位置：第 121-122 行
- 参数：dt
- 返回类型：Name(id='str', ctx=Load())

### `ScheduleService._normalize_datetime()` [私有]
- 位置：第 125-139 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleService.list_batch_operations()` [公开]
- 位置：第 144-145 行
- 参数：batch_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/scheduler_batch_detail.py:199` [Route] `ops = sch_svc.list_batch_operations(batch_id=b.batch_id)`
- **被调用者**（1 个）：`op_edit.list_batch_operations`

### `ScheduleService.get_operation()` [公开]
- 位置：第 147-148 行
- 参数：op_id
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（4 处）：
  - `web/routes/scheduler_ops.py:14` [Route] `op = sch_svc.get_operation(op_id)`
  - `core/services/scheduler/operation_edit_service.py:30` [Service] `op = get_operation(svc, op_id)`
  - `core/services/scheduler/operation_edit_service.py:126` [Service] `op = get_operation(svc, op_id)`
  - `core/services/scheduler/operation_edit_service.py:172` [Service] `op = get_operation(svc, op_id)`
- **被调用者**（1 个）：`op_edit.get_operation`

### `ScheduleService.get_external_merge_hint()` [公开]
- 位置：第 150-154 行
- 参数：op_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/scheduler_batch_detail.py:188` [Route] `d["merge_hint"] = sch_svc.get_external_merge_hint(op.id)`
- **被调用者**（1 个）：`op_edit.get_external_merge_hint`

### `ScheduleService.update_internal_operation()` [公开]
- 位置：第 159-176 行
- 参数：op_id, machine_id, operator_id, setup_hours, unit_hours, status
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_ops.py:22` [Route] `sch_svc.update_internal_operation(`
- **被调用者**（1 个）：`op_edit.update_internal_operation`

### `ScheduleService.update_external_operation()` [公开]
- 位置：第 181-194 行
- 参数：op_id, supplier_id, ext_days, status
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_ops.py:34` [Route] `sch_svc.update_external_operation(op_id=op_id, supplier_id=supplier_id, ext_days`
- **被调用者**（1 个）：`op_edit.update_external_operation`

### `ScheduleService.run_schedule()` [公开]
- 位置：第 199-224 行
- 参数：batch_ids, start_dt, end_date, created_by, simulate, enforce_ready, strict_mode
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/scheduler_run.py:40` [Route] `result = sch_svc.run_schedule(`
  - `web/routes/scheduler_week_plan.py:179` [Route] `result = sch_svc.run_schedule(`
  - `core/services/scheduler/schedule_optimizer.py:277` [Service] `说明：为保证兼容，本函数尽量保持与原 `ScheduleService.run_schedule()` 相同的口径与留痕结构。`
- **被调用者**（4 个）：`_RUN_SCHEDULE_LOCK.acquire`, `ValidationError`, `self._run_schedule_impl`, `_RUN_SCHEDULE_LOCK.release`

### `ScheduleService._run_schedule_impl()` [私有]
- 位置：第 226-549 行
- 参数：batch_ids, start_dt, end_date, created_by, simulate, enforce_ready, strict_mode
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

## web/routes/scheduler_batch_detail.py（Route 层）

### `_count_internal_ops()` [私有]
- 位置：第 18-27 行
- 参数：ops
- 返回类型：Name(id='int', ctx=Load())

### `_collect_selected_resource_ids()` [私有]
- 位置：第 30-44 行
- 参数：ops
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_machine_options()` [私有]
- 位置：第 47-73 行
- 参数：machine_svc, selected_machine_ids
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_build_operator_options()` [私有]
- 位置：第 76-102 行
- 参数：operator_svc, selected_operator_ids
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_build_supplier_options()` [私有]
- 位置：第 105-131 行
- 参数：supplier_svc, selected_supplier_ids
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_resolve_lazy_select_enabled()` [私有]
- 位置：第 134-144 行
- 参数：internal_op_count, machine_options, operator_options
- 返回类型：Name(id='bool', ctx=Load())

### `_build_machine_operator_maps()` [私有]
- 位置：第 147-180 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_view_ops()` [私有]
- 位置：第 183-190 行
- 参数：ops, sch_svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `batch_detail()` [公开]
- 位置：第 194-244 行
- 参数：batch_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（25 个）：`bp.get`, `BatchService`, `ScheduleService`, `batch_svc.get`, `sch_svc.list_batch_operations`, `_count_internal_ops`, `_collect_selected_resource_ids`, `MachineService`, `OperatorService`, `SupplierService`, `_build_machine_options`, `_build_operator_options`, `_build_supplier_options`, `_resolve_lazy_select_enabled`, `OperatorMachineQueryService`

## web/ui_mode.py（Other 层）

### `normalize_ui_mode()` [公开]
- 位置：第 30-32 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `web/routes/system_ui_mode.py:19` [Route] `mode = normalize_ui_mode(request.form.get("mode"))`
- **被调用者**（3 个）：`lower`, `strip`, `str`

### `_resolve_manual_endpoint()` [私有]
- 位置：第 35-43 行
- 参数：endpoint
- 返回类型：Name(id='str', ctx=Load())

### `normalize_manual_src()` [公开]
- 位置：第 46-58 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（3 处）：
  - `web/routes/scheduler_config.py:80` [Route] `输入应为已经过 normalize_manual_src() 过滤的站内相对地址。`
  - `web/routes/scheduler_config.py:212` [Route] `safe_src = normalize_manual_src(raw_src)`
  - `web/routes/scheduler_config.py:255` [Route] `safe_src = normalize_manual_src(raw_src)`
- **被调用者**（6 个）：`strip`, `any`, `text.startswith`, `urlsplit`, `startswith`, `str`

### `_resolve_manual_src()` [私有]
- 位置：第 61-75 行
- 参数：src
- 返回类型：Name(id='str', ctx=Load())

### `get_manual_url()` [公开]
- 位置：第 78-83 行
- 参数：endpoint, src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:147` [Route] `enriched["url"] = get_manual_url(endpoint=entry_endpoint, src=link_src) if entry`
- **被调用者**（5 个）：`_resolve_manual_endpoint`, `normalize_manual_src`, `safe_url_for`, `_resolve_manual_src`, `resolve_manual_id`

### `get_full_manual_section_url()` [公开]
- 位置：第 86-98 行
- 参数：endpoint, src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/routes/scheduler_config.py:149` [Route] `get_full_manual_section_url(endpoint=entry_endpoint, src=link_src) if entry_endp`
  - `web/routes/scheduler_config.py:194` [Route] `"full_manual_section_url": get_full_manual_section_url(endpoint=raw_page, src=li`
- **被调用者**（8 个）：`_resolve_manual_endpoint`, `build_manual_for_endpoint`, `normalize_manual_src`, `safe_url_for`, `strip`, `_resolve_manual_src`, `str`, `manual.get`

### `get_help_card()` [公开]
- 位置：第 101-115 行
- 参数：endpoint, src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`_resolve_manual_endpoint`, `build_manual_for_endpoint`, `manual.get`, `strip`, `list`, `get_manual_url`, `str`, `help_card.get`

### `init_ui_mode()` [公开]
- 位置：第 118-179 行
- 参数：app, base_dir
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`join`, `setdefault`, `str`, `Blueprint`, `app.register_blueprint`, `FileSystemLoader`, `ChoiceLoader`, `overlay`, `get`, `isdir`, `warning`

### `_read_ui_mode_from_db()` [私有]
- 位置：第 182-195 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `get_ui_mode()` [公开]
- 位置：第 198-222 行
- 参数：default
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`_read_ui_mode_from_db`, `normalize_ui_mode`, `has_request_context`, `get`

### `_get_v2_env()` [私有]
- 位置：第 225-227 行
- 参数：app
- 返回类型：Name(id='Any', ctx=Load())

### `_describe_template_name()` [私有]
- 位置：第 230-236 行
- 参数：template_name_or_list
- 返回类型：Name(id='str', ctx=Load())

### `_warn_v2_render_fallback_once()` [私有]
- 位置：第 239-256 行
- 参数：app
- 返回类型：Constant(value=None, kind=None)

### `safe_url_for()` [公开]
- 位置：第 259-295 行
- 参数：endpoint
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`has_request_context`, `url_for`, `getattr`, `set`, `logged.add`, `warning`

### `_resolve_template_url_for()` [私有]
- 位置：第 298-306 行
- 参数：无
- 返回类型：无注解

### `render_ui_template()` [公开]
- 位置：第 309-371 行
- 参数：template_name_or_list
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`get_ui_mode`, `context.setdefault`, `app.update_template_context`, `_resolve_template_url_for`, `env.get_or_select_template`, `template.render`, `_get_v2_env`, `setdefault`, `_warn_v2_render_fallback_once`

---
- 分析函数/方法数：55
- 找到调用关系：19 处
- 跨层边界风险：1 项
