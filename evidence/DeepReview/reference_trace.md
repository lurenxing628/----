# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ get_full_manual_section_url() 返回 Optional，但 web/routes/scheduler_config.py:194 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/services/scheduler/schedule_service.py（Service 层）

### `_normalized_status_text()` [私有]
- 位置：第 45-46 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_get_snapshot_with_optional_strict_mode()` [私有]
- 位置：第 49-59 行
- 参数：cfg_svc
- 返回类型：Name(id='Any', ctx=Load())

### `_raise_schedule_empty_result()` [私有]
- 位置：第 62-66 行
- 参数：message
- 返回类型：Constant(value=None, kind=None)

### `ScheduleService.__init__()` [私有]
- 位置：第 78-96 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ScheduleService._normalize_text()` [私有]
- 位置：第 102-103 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleService._is_reschedulable_operation()` [私有]
- 位置：第 106-108 行
- 参数：op
- 返回类型：Name(id='bool', ctx=Load())

### `ScheduleService._normalize_float()` [私有]
- 位置：第 111-112 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleService._get_batch_or_raise()` [私有]
- 位置：第 114-118 行
- 参数：batch_id
- 返回类型：Name(id='Batch', ctx=Load())

### `ScheduleService._get_op_or_raise()` [私有]
- 位置：第 120-124 行
- 参数：op_id
- 返回类型：Name(id='BatchOperation', ctx=Load())

### `ScheduleService._get_template_and_group_for_op()` [私有]
- 位置：第 126-127 行
- 参数：op
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ScheduleService._format_dt()` [私有]
- 位置：第 130-131 行
- 参数：dt
- 返回类型：Name(id='str', ctx=Load())

### `ScheduleService._normalize_datetime()` [私有]
- 位置：第 134-148 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleService.list_batch_operations()` [公开]
- 位置：第 153-154 行
- 参数：batch_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/scheduler_batch_detail.py:196` [Route] `ops = sch_svc.list_batch_operations(batch_id=b.batch_id)`
- **被调用者**（1 个）：`op_edit.list_batch_operations`

### `ScheduleService.get_operation()` [公开]
- 位置：第 156-157 行
- 参数：op_id
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（4 处）：
  - `web/routes/scheduler_ops.py:14` [Route] `op = sch_svc.get_operation(op_id)`
  - `core/services/scheduler/operation_edit_service.py:31` [Service] `op = get_operation(svc, op_id)`
  - `core/services/scheduler/operation_edit_service.py:127` [Service] `op = get_operation(svc, op_id)`
  - `core/services/scheduler/operation_edit_service.py:178` [Service] `op = get_operation(svc, op_id)`
- **被调用者**（1 个）：`op_edit.get_operation`

### `ScheduleService.get_external_merge_hint()` [公开]
- 位置：第 159-163 行
- 参数：op_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/scheduler_batch_detail.py:185` [Route] `d["merge_hint"] = sch_svc.get_external_merge_hint(op.id)`
- **被调用者**（1 个）：`op_edit.get_external_merge_hint`

### `ScheduleService.update_internal_operation()` [公开]
- 位置：第 168-185 行
- 参数：op_id, machine_id, operator_id, setup_hours, unit_hours, status
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_ops.py:22` [Route] `sch_svc.update_internal_operation(`
- **被调用者**（1 个）：`op_edit.update_internal_operation`

### `ScheduleService.update_external_operation()` [公开]
- 位置：第 190-203 行
- 参数：op_id, supplier_id, ext_days, status
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_ops.py:34` [Route] `sch_svc.update_external_operation(op_id=op_id, supplier_id=supplier_id, ext_days`
- **被调用者**（1 个）：`op_edit.update_external_operation`

### `ScheduleService.run_schedule()` [公开]
- 位置：第 208-233 行
- 参数：batch_ids, start_dt, end_date, created_by, simulate, enforce_ready, strict_mode
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/scheduler_run.py:37` [Route] `result = sch_svc.run_schedule(`
  - `web/routes/scheduler_week_plan.py:175` [Route] `result = sch_svc.run_schedule(`
  - `core/services/scheduler/schedule_optimizer.py:296` [Service] `说明：为保证兼容，本函数尽量保持与原 `ScheduleService.run_schedule()` 相同的口径与留痕结构。`
- **被调用者**（4 个）：`_RUN_SCHEDULE_LOCK.acquire`, `ValidationError`, `self._run_schedule_impl`, `_RUN_SCHEDULE_LOCK.release`

### `ScheduleService._run_schedule_impl()` [私有]
- 位置：第 235-333 行
- 参数：batch_ids, start_dt, end_date, created_by, simulate, enforce_ready, strict_mode
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

## web/ui_mode.py（Other 层）

### `normalize_ui_mode()` [公开]
- 位置：第 41-43 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `web/routes/system_ui_mode.py:19` [Route] `mode = normalize_ui_mode(request.form.get("mode"))`
- **被调用者**（3 个）：`lower`, `strip`, `str`

### `_log_warning()` [私有]
- 位置：第 46-50 行
- 参数：message
- 返回类型：Constant(value=None, kind=None)

### `_log_startup_warning()` [私有]
- 位置：第 53-54 行
- 参数：app, message
- 返回类型：Constant(value=None, kind=None)

### `_warn_invalid_db_ui_mode_once()` [私有]
- 位置：第 57-63 行
- 参数：raw_value
- 返回类型：Constant(value=None, kind=None)

### `_resolve_manual_endpoint()` [私有]
- 位置：第 66-74 行
- 参数：endpoint
- 返回类型：Name(id='str', ctx=Load())

### `normalize_manual_src()` [公开]
- 位置：第 77-89 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（3 处）：
  - `web/routes/scheduler_config.py:80` [Route] `输入应为已经过 normalize_manual_src() 过滤的站内相对地址。`
  - `web/routes/scheduler_config.py:212` [Route] `safe_src = normalize_manual_src(raw_src)`
  - `web/routes/scheduler_config.py:255` [Route] `safe_src = normalize_manual_src(raw_src)`
- **被调用者**（6 个）：`strip`, `any`, `text.startswith`, `urlsplit`, `startswith`, `str`

### `_resolve_manual_src()` [私有]
- 位置：第 92-106 行
- 参数：src
- 返回类型：Name(id='str', ctx=Load())

### `get_manual_url()` [公开]
- 位置：第 109-114 行
- 参数：endpoint, src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:147` [Route] `enriched["url"] = get_manual_url(endpoint=entry_endpoint, src=link_src) if entry`
- **被调用者**（5 个）：`_resolve_manual_endpoint`, `normalize_manual_src`, `safe_url_for`, `_resolve_manual_src`, `resolve_manual_id`

### `get_full_manual_section_url()` [公开]
- 位置：第 117-129 行
- 参数：endpoint, src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/routes/scheduler_config.py:149` [Route] `get_full_manual_section_url(endpoint=entry_endpoint, src=link_src) if entry_endp`
  - `web/routes/scheduler_config.py:194` [Route] `"full_manual_section_url": get_full_manual_section_url(endpoint=raw_page, src=li`
- **被调用者**（8 个）：`_resolve_manual_endpoint`, `build_manual_for_endpoint`, `normalize_manual_src`, `safe_url_for`, `strip`, `_resolve_manual_src`, `str`, `manual.get`

### `get_help_card()` [公开]
- 位置：第 132-146 行
- 参数：endpoint, src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`_resolve_manual_endpoint`, `build_manual_for_endpoint`, `manual.get`, `strip`, `list`, `get_manual_url`, `str`, `help_card.get`

### `init_ui_mode()` [公开]
- 位置：第 149-206 行
- 参数：app, base_dir
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/bootstrap/factory.py:242` [Bootstrap] `init_ui_mode(app, base_dir)`
- **被调用者**（11 个）：`join`, `setdefault`, `str`, `Blueprint`, `app.register_blueprint`, `FileSystemLoader`, `ChoiceLoader`, `overlay`, `get`, `isdir`, `_log_startup_warning`

### `_read_ui_mode_from_db()` [私有]
- 位置：第 209-240 行
- 参数：无
- 返回类型：Name(id='_UiModeDbReadResult', ctx=Load())

### `get_ui_mode()` [公开]
- 位置：第 243-269 行
- 参数：default
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`_read_ui_mode_from_db`, `normalize_ui_mode`, `has_request_context`, `_warn_invalid_db_ui_mode_once`, `get`, `_log_warning`

### `_get_v2_env()` [私有]
- 位置：第 272-274 行
- 参数：app
- 返回类型：Name(id='Any', ctx=Load())

### `_describe_template_name()` [私有]
- 位置：第 277-283 行
- 参数：template_name_or_list
- 返回类型：Name(id='str', ctx=Load())

### `_warn_v2_render_fallback_once()` [私有]
- 位置：第 286-303 行
- 参数：app
- 返回类型：Constant(value=None, kind=None)

### `safe_url_for()` [公开]
- 位置：第 306-346 行
- 参数：endpoint
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`has_request_context`, `url_for`, `_log_warning`, `getattr`, `set`, `logged.add`

### `_resolve_template_url_for()` [私有]
- 位置：第 349-357 行
- 参数：无
- 返回类型：无注解

### `render_ui_template()` [公开]
- 位置：第 360-422 行
- 参数：template_name_or_list
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`get_ui_mode`, `context.setdefault`, `app.update_template_context`, `_resolve_template_url_for`, `env.get_or_select_template`, `template.render`, `_get_v2_env`, `setdefault`, `_warn_v2_render_fallback_once`

## web/routes/scheduler_excel_batches.py（Route 层）

### `_sorted_existing_list()` [私有]
- 位置：第 49-52 行
- 参数：existing_preview_data
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_parse_auto_generate_ops()` [私有]
- 位置：第 55-56 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())

### `_build_existing_preview_data()` [私有]
- 位置：第 59-74 行
- 参数：batch_svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_parts_cache()` [私有]
- 位置：第 77-79 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_template_ops_snapshot()` [私有]
- 位置：第 82-87 行
- 参数：conn, rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_batch_baseline_extra_state()` [私有]
- 位置：第 90-113 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_render_excel_batches_page()` [私有]
- 位置：第 116-145 行
- 参数：无
- 返回类型：无注解

### `excel_batches_page()` [公开]
- 位置：第 149-173 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.get`, `BatchService`, `_render_excel_batches_page`, `getattr`, `svc.list`, `list`, `existing.values`

### `excel_batches_preview()` [公开]
- 位置：第 177-263 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（31 个）：`bp.post`, `time.time`, `_parse_mode`, `_parse_auto_generate_ops`, `_strict_mode_enabled`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `BatchService`, `_build_parts_cache`, `get_batch_row_validate_and_normalize`, `ExcelService`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`

### `excel_batches_confirm()` [公开]
- 位置：第 267-362 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（37 个）：`bp.post`, `time.time`, `_parse_mode`, `_strict_mode_enabled`, `_parse_auto_generate_ops`, `load_confirm_payload`, `_ensure_unique_ids`, `BatchService`, `_build_existing_preview_data`, `_build_parts_cache`, `preview_baseline_is_stale`, `get_batch_row_validate_and_normalize`, `ExcelService`, `excel_svc.preview_import`, `collect_error_rows`

### `excel_batches_template()` [公开]
- 位置：第 366-407 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_batches_export()` [公开]
- 位置：第 411-443 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `BatchService`, `svc.list`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`

---
- 分析函数/方法数：50
- 找到调用关系：19 处
- 跨层边界风险：1 项
