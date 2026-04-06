# 引用链追踪报告（深度 Review 辅助）

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## app.py（Other 层）

### `create_app()` [公开]
- 位置：第 29-30 行
- 参数：无
- 返回类型：Name(id='Flask', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`create_app_with_mode`

### `_module_globals()` [私有]
- 位置：第 33-54 行
- 参数：无
- 返回类型：无注解

### `main()` [公开]
- 位置：第 61-62 行
- 参数：argv
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`app_main`, `_module_globals`

## app_new_ui.py（Other 层）

### `create_app()` [公开]
- 位置：第 29-30 行
- 参数：无
- 返回类型：Name(id='Flask', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`create_app_with_mode`

### `_module_globals()` [私有]
- 位置：第 33-54 行
- 参数：无
- 返回类型：无注解

### `main()` [公开]
- 位置：第 61-62 行
- 参数：argv
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`app_main`, `_module_globals`

## core/services/scheduler/schedule_orchestrator.py（Service 层）

### `_normalize_optimizer_outcome()` [私有]
- 位置：第 53-68 行
- 参数：optimizer_outcome
- 返回类型：Name(id='_NormalizedOptimizerOutcome', ctx=Load())

### `_merge_summary_warnings()` [私有]
- 位置：第 71-100 行
- 参数：summary, algo_warnings
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `orchestrate_schedule_run()` [公开]
- 位置：第 103-208 行
- 参数：svc
- 返回类型：Name(id='ScheduleOrchestrationOutcome', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:344` [Service] `orchestration = orchestrate_schedule_run(`
- **被调用者**（14 个）：`_normalize_optimizer_outcome`, `bool`, `_merge_summary_warnings`, `SummaryBuildContext`, `build_result_summary_fn`, `ScheduleOrchestrationOutcome`, `optimize_schedule_fn`, `has_actionable_schedule_rows_fn`, `_raise_schedule_empty_result`, `list`, `transaction`, `int`, `allocate_next_version`, `set`

## core/services/scheduler/schedule_summary.py（Service 层）

### `serialize_end_date()` [公开]
- 位置：第 75-88 行
- 参数：end_date
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`isinstance`, `strip`, `end_date.strip`, `getattr`, `callable`, `str`, `isoformat`

### `due_exclusive()` [公开]
- 位置：第 91-94 行
- 参数：due_date
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（1 处）：
  - `core/services/report/calculations.py:98` [Service] `due_excl = due_exclusive(due_d)`
- **被调用者**（2 个）：`datetime`, `timedelta`

### `_warning_list()` [私有]
- 位置：第 97-122 行
- 参数：value
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_merge_warning_lists()` [私有]
- 位置：第 125-133 行
- 参数：primary, extra
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_append_summary_warning()` [私有]
- 位置：第 136-154 行
- 参数：summary, message
- 返回类型：Name(id='bool', ctx=Load())

### `_counter_dict()` [私有]
- 位置：第 157-168 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_summary_size_bytes()` [私有]
- 位置：第 171-172 行
- 参数：obj
- 返回类型：Name(id='int', ctx=Load())

### `apply_summary_size_guard()` [公开]
- 位置：第 175-229 行
- 参数：result_summary_obj
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`_summary_size_bytes`, `result_summary_obj.get`, `algo_dict.get`, `isinstance`, `overdue_batches.get`, `_trim_trace`, `_trim_warnings`, `_trim_attempts`, `int`, `_trim_best_batch_order`, `_trim_selected_batch_ids`, `_trim_overdue_items`

### `build_overdue_items()` [公开]
- 位置：第 232-246 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`_build_overdue_items_impl`

### `_build_runtime_state()` [私有]
- 位置：第 249-279 行
- 参数：无
- 返回类型：Name(id='RuntimeState', ctx=Load())

### `_build_warning_state()` [私有]
- 位置：第 282-311 行
- 参数：无
- 返回类型：Name(id='WarningState', ctx=Load())

### `_build_freeze_state()` [私有]
- 位置：第 314-334 行
- 参数：无
- 返回类型：Name(id='FreezeState', ctx=Load())

### `_build_fallback_state()` [私有]
- 位置：第 337-347 行
- 参数：algo_stats
- 返回类型：Name(id='FallbackState', ctx=Load())

### `_merge_fallback_warnings()` [私有]
- 位置：第 350-357 行
- 参数：all_warnings, fallback_state
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `build_result_summary()` [公开]
- 位置：第 360-462 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（28 个）：`dict`, `_build_runtime_state`, `_compute_result_status`, `int`, `_frozen_batch_ids`, `_input_build_state`, `_build_warning_state`, `_build_freeze_state`, `_compute_downtime_degradation`, `_compute_resource_pool_degradation`, `_hard_constraints`, `_build_fallback_state`, `replace`, `_summary_degradation_state`, `AlgorithmSummaryState`

## core/services/scheduler/schedule_summary_assembly.py（Service 层）

### `_cfg_value()` [私有]
- 位置：第 75-78 行
- 参数：cfg, key, default
- 返回类型：Name(id='Any', ctx=Load())

### `_config_snapshot_dict()` [私有]
- 位置：第 81-101 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_comparison_metric()` [私有]
- 位置：第 104-106 行
- 参数：objective_name
- 返回类型：Name(id='str', ctx=Load())

### `_best_score_schema()` [私有]
- 位置：第 109-112 行
- 参数：objective_name
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_finish_time_by_batch()` [私有]
- 位置：第 115-127 行
- 参数：results
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_record_invalid_due()` [私有]
- 位置：第 130-140 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_build_overdue_items()` [私有]
- 位置：第 143-200 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_algo_downtime_dict()` [私有]
- 位置：第 203-213 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_input_contract_dict()` [私有]
- 位置：第 216-222 行
- 参数：input_state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_freeze_window_dict()` [私有]
- 位置：第 225-245 行
- 参数：state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_resource_pool_dict()` [私有]
- 位置：第 248-261 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_warning_pipeline_dict()` [私有]
- 位置：第 264-276 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_dict()` [私有]
- 位置：第 279-320 行
- 参数：state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_result_summary_obj()` [私有]
- 位置：第 323-363 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

## core/services/scheduler/schedule_summary_types.py（Service 层）

### `FreezeState.status()` [公开]
- 位置：第 68-69 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`str`, `get`

## web/bootstrap/entrypoint.py（Other 层）

### `create_app_with_mode()` [公开]
- 位置：第 60-66 行
- 参数：ui_mode
- 返回类型：Name(id='Flask', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`create_app_core`

### `_parse_cli_args()` [私有]
- 位置：第 69-73 行
- 参数：argv
- 返回类型：无注解

### `_default_deps()` [私有]
- 位置：第 76-97 行
- 参数：ui_mode
- 返回类型：Name(id='EntryPointDeps', ctx=Load())

### `deps_from_module_globals()` [公开]
- 位置：第 100-133 行
- 参数：module_globals, ui_mode
- 返回类型：Name(id='EntryPointDeps', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`module_globals.get`, `callable`, `EntryPointDeps`, `cast`, `create_app_with_mode`, `getattr`, `__import__`

### `configure_runtime_contract()` [公开]
- 位置：第 136-173 行
- 参数：app, runtime_dir, host, port, owner
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`secrets.token_urlsafe`, `deps.write_runtime_host_port_files`, `deps.write_runtime_contract_file`, `get`, `str`, `deps.default_chrome_profile_dir`

### `app_main()` [公开]
- 位置：第 176-289 行
- 参数：ui_mode
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（30 个）：`_parse_cli_args`, `strip`, `runtime_base_dir`, `deps.resolve_prelaunch_log_dir`, `deps.current_runtime_owner`, `bool`, `deps.should_use_runtime_reloader`, `deps.should_own_runtime_resources`, `get`, `deps.pick_bind_host`, `deps.pick_port`, `deps.serve_runtime_app`, `int`, `deps.clear_launch_error`, `deps.create_app`

## web/routes/equipment_excel_links.py（Route 层）

### `_build_existing_machine_link_page_data()` [私有]
- 位置：第 36-60 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_operator_machine_reference_snapshot()` [私有]
- 位置：第 63-69 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_render_excel_link_page()` [私有]
- 位置：第 72-94 行
- 参数：无
- 返回类型：无注解

### `excel_link_page()` [公开]
- 位置：第 98-107 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `_build_existing_machine_link_page_data`, `_render_excel_link_page`

### `excel_link_preview()` [公开]
- 位置：第 111-162 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `OperatorMachineService`, `link_svc.preview_import_links`, `_build_existing_machine_link_page_data`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_link_page`, `ValidationError`, `dict`, `normalized_rows.append`

### `excel_link_confirm()` [公开]
- 位置：第 166-228 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（25 个）：`bp.post`, `time.time`, `_parse_mode`, `load_confirm_payload`, `_build_existing_machine_link_page_data`, `preview_baseline_is_stale`, `OperatorMachineService`, `link_svc.preview_import_links`, `collect_error_rows`, `link_svc.apply_import_links`, `extract_import_stats`, `int`, `log_excel_import`, `flash_import_result`, `redirect`

### `excel_link_template()` [公开]
- 位置：第 232-274 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_link_export()` [公开]
- 位置：第 278-308 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.get`, `time.time`, `OperatorMachineQueryService`, `q.list_simple_rows`, `rows.sort`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`, `str`, `r.get`

## web/routes/equipment_excel_machines.py（Route 层）

### `_validate_machine_excel_row()` [私有]
- 位置：第 42-56 行
- 参数：row
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_normalize_machine_status_for_excel()` [私有]
- 位置：第 59-66 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_resolve_op_type()` [私有]
- 位置：第 69-83 行
- 参数：value, op_type_svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_machine_reference_snapshot()` [私有]
- 位置：第 86-104 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_render_excel_machine_page()` [私有]
- 位置：第 107-129 行
- 参数：无
- 返回类型：无注解

### `excel_machine_page()` [公开]
- 位置：第 133-143 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `MachineService`, `svc.build_existing_for_excel`, `_render_excel_machine_page`, `getattr`

### `excel_machine_preview()` [公开]
- 位置：第 147-234 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（32 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `OpTypeService`, `ResourceTeamService`, `MachineService`, `m_svc.build_existing_for_excel`, `ExcelService`, `svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`

### `excel_machine_confirm()` [公开]
- 位置：第 238-334 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（40 个）：`bp.post`, `time.time`, `_parse_mode`, `load_confirm_payload`, `_ensure_unique_ids`, `OpTypeService`, `ResourceTeamService`, `MachineService`, `m_svc.build_existing_for_excel`, `preview_baseline_is_stale`, `ExcelService`, `excel_svc.preview_import`, `collect_error_rows`, `MachineExcelImportService`, `import_svc.apply_preview_rows`

### `excel_machine_template()` [公开]
- 位置：第 338-379 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_machine_export()` [公开]
- 位置：第 383-412 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `MachineService`, `m_svc.list_for_export`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`, `r.get`

## web/routes/excel_demo.py（Route 层）

### `_fetch_existing_operators()` [私有]
- 位置：第 39-41 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_parse_mode()` [私有]
- 位置：第 44-45 行
- 参数：value
- 返回类型：Name(id='ImportMode', ctx=Load())

### `_render_demo_page()` [私有]
- 位置：第 48-69 行
- 参数：无
- 返回类型：无注解

### `_validate_operator_row()` [私有]
- 位置：第 72-85 行
- 参数：row
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `index()` [公开]
- 位置：第 89-98 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `_fetch_existing_operators`, `_render_demo_page`

### `preview()` [公开]
- 位置：第 102-189 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（31 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `file.read`, `io.BytesIO`, `tmp.seek`, `OpenpyxlBackend`, `_fetch_existing_operators`, `ExcelService`, `svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_demo_page`

### `confirm()` [公开]
- 位置：第 193-260 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（28 个）：`bp.post`, `time.time`, `_parse_mode`, `load_confirm_payload`, `_fetch_existing_operators`, `preview_baseline_is_stale`, `OpenpyxlBackend`, `ExcelService`, `svc.preview_import`, `collect_error_rows`, `OperatorExcelImportService`, `import_svc.apply_preview_rows`, `extract_import_stats`, `int`, `log_excel_import`

### `download_template()` [公开]
- 位置：第 264-309 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `len`

## web/routes/excel_utils.py（Route 层）

### `parse_import_mode()` [公开]
- 位置：第 22-30 行
- 参数：value
- 返回类型：Name(id='ImportMode', ctx=Load())
- **调用者**（5 处）：
  - `web/routes/equipment_bp.py:24` [Route] `return parse_import_mode(value)`
  - `web/routes/excel_demo.py:45` [Route] `return parse_import_mode(value)`
  - `web/routes/personnel_bp.py:29` [Route] `return parse_import_mode(value)`
  - `web/routes/process_bp.py:41` [Route] `return parse_import_mode(value)`
  - `web/routes/scheduler_utils.py:12` [Route] `return parse_import_mode(value)`
- **被调用者**（2 个）：`ImportMode`, `ValidationError`

### `build_preview_baseline_token()` [公开]
- 位置：第 33-52 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（12 处）：
  - `web/routes/equipment_excel_links.py:137` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/equipment_excel_machines.py:209` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/excel_demo.py:169` [Route] `preview_baseline = build_preview_baseline_token(existing_data=existing, mode=mod`
  - `web/routes/personnel_excel_links.py:137` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/personnel_excel_operators.py:156` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/personnel_excel_operator_calendar.py:221` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/process_excel_op_types.py:158` [Route] `preview_baseline = build_preview_baseline_token(existing_data=existing, mode=mod`
  - `web/routes/process_excel_part_operation_hours.py:267` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/process_excel_routes.py:134` [Route] `preview_baseline = build_preview_baseline_token(existing_data=existing, mode=mod`
  - `web/routes/process_excel_suppliers.py:169` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/scheduler_excel_batches.py:230` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/scheduler_excel_calendar.py:234` [Route] `preview_baseline = build_preview_baseline_token(`
- **被调用者**（7 个）：`json.dumps`, `hexdigest`, `strip`, `hashlib.sha256`, `str`, `raw.encode`, `getattr`

### `preview_baseline_matches()` [公开]
- 位置：第 55-79 行
- 参数：token
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`strip`, `build_preview_baseline_token`, `hmac.compare_digest`, `exception`

### `parse_preview_rows_json()` [公开]
- 位置：第 88-95 行
- 参数：raw_rows_json
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`json.loads`, `isinstance`, `ValueError`, `ValidationError`

### `extract_error_rows()` [公开]
- 位置：第 98-99 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`getattr`

### `format_error_sample()` [公开]
- 位置：第 102-108 行
- 参数：error_rows
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`join`, `getattr`

### `strict_mode_enabled()` [公开]
- 位置：第 111-112 行
- 参数：raw_value
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`lower`, `strip`, `str`

### `load_confirm_payload()` [公开]
- 位置：第 115-124 行
- 参数：raw_rows_json, preview_baseline
- 返回类型：Name(id='ConfirmPayload', ctx=Load())
- **调用者**（12 处）：
  - `web/routes/equipment_excel_links.py:170` [Route] `payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.g`
  - `web/routes/equipment_excel_machines.py:242` [Route] `payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.g`
  - `web/routes/excel_demo.py:198` [Route] `payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.g`
  - `web/routes/personnel_excel_links.py:171` [Route] `payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.g`
  - `web/routes/personnel_excel_operators.py:190` [Route] `payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.g`
  - `web/routes/personnel_excel_operator_calendar.py:257` [Route] `payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.g`
  - `web/routes/process_excel_op_types.py:186` [Route] `payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.g`
  - `web/routes/process_excel_part_operation_hours.py:303` [Route] `payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.g`
  - `web/routes/process_excel_routes.py:164` [Route] `payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.g`
  - `web/routes/process_excel_suppliers.py:202` [Route] `payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.g`
  - `web/routes/scheduler_excel_batches.py:273` [Route] `payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.g`
  - `web/routes/scheduler_excel_calendar.py:267` [Route] `payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.g`
- **被调用者**（5 个）：`strip`, `ConfirmPayload`, `ValidationError`, `str`, `parse_preview_rows_json`

### `preview_baseline_is_stale()` [公开]
- 位置：第 127-141 行
- 参数：preview_baseline
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（12 处）：
  - `web/routes/equipment_excel_links.py:174` [Route] `if preview_baseline_is_stale(`
  - `web/routes/equipment_excel_machines.py:251` [Route] `if preview_baseline_is_stale(`
  - `web/routes/excel_demo.py:202` [Route] `if preview_baseline_is_stale(payload.preview_baseline, existing_data=existing, m`
  - `web/routes/personnel_excel_links.py:175` [Route] `if preview_baseline_is_stale(`
  - `web/routes/personnel_excel_operators.py:198` [Route] `if preview_baseline_is_stale(`
  - `web/routes/personnel_excel_operator_calendar.py:276` [Route] `if preview_baseline_is_stale(`
  - `web/routes/process_excel_op_types.py:193` [Route] `if preview_baseline_is_stale(payload.preview_baseline, existing_data=existing, m`
  - `web/routes/process_excel_part_operation_hours.py:312` [Route] `if preview_baseline_is_stale(`
  - `web/routes/process_excel_routes.py:171` [Route] `if preview_baseline_is_stale(payload.preview_baseline, existing_data=existing, m`
  - `web/routes/process_excel_suppliers.py:210` [Route] `if preview_baseline_is_stale(`
  - `web/routes/scheduler_excel_batches.py:281` [Route] `if preview_baseline_is_stale(`
  - `web/routes/scheduler_excel_calendar.py:282` [Route] `if preview_baseline_is_stale(`
- **被调用者**（1 个）：`preview_baseline_matches`

### `collect_error_rows()` [公开]
- 位置：第 144-145 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（12 处）：
  - `web/routes/equipment_excel_links.py:194` [Route] `error_rows = collect_error_rows(preview_rows)`
  - `web/routes/equipment_excel_machines.py:296` [Route] `error_rows = collect_error_rows(preview_rows)`
  - `web/routes/excel_demo.py:222` [Route] `error_rows = collect_error_rows(preview_rows)`
  - `web/routes/personnel_excel_links.py:195` [Route] `error_rows = collect_error_rows(preview_rows)`
  - `web/routes/personnel_excel_operators.py:236` [Route] `error_rows = collect_error_rows(preview_rows)`
  - `web/routes/personnel_excel_operator_calendar.py:311` [Route] `error_rows = collect_error_rows(preview_rows)`
  - `web/routes/process_excel_op_types.py:215` [Route] `error_rows = collect_error_rows(preview_rows)`
  - `web/routes/process_excel_part_operation_hours.py:337` [Route] `error_rows = collect_error_rows(preview_rows)`
  - `web/routes/process_excel_routes.py:194` [Route] `error_rows = collect_error_rows(preview_rows)`
  - `web/routes/process_excel_suppliers.py:254` [Route] `error_rows = collect_error_rows(preview_rows)`
  - `web/routes/scheduler_excel_batches.py:316` [Route] `error_rows = collect_error_rows(preview_rows)`
  - `web/routes/scheduler_excel_calendar.py:362` [Route] `error_rows = collect_error_rows(preview_rows)`
- **被调用者**（1 个）：`extract_error_rows`

### `build_error_rows_message()` [公开]
- 位置：第 148-153 行
- 参数：error_rows
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（12 处）：
  - `web/routes/equipment_excel_links.py:196` [Route] `flash(build_error_rows_message(error_rows), "error")`
  - `web/routes/equipment_excel_machines.py:298` [Route] `flash(build_error_rows_message(error_rows), "error")`
  - `web/routes/excel_demo.py:224` [Route] `flash(build_error_rows_message(error_rows), "error")`
  - `web/routes/personnel_excel_links.py:197` [Route] `flash(build_error_rows_message(error_rows), "error")`
  - `web/routes/personnel_excel_operators.py:238` [Route] `flash(build_error_rows_message(error_rows), "error")`
  - `web/routes/personnel_excel_operator_calendar.py:313` [Route] `flash(build_error_rows_message(error_rows), "error")`
  - `web/routes/process_excel_op_types.py:217` [Route] `flash(build_error_rows_message(error_rows), "error")`
  - `web/routes/process_excel_part_operation_hours.py:339` [Route] `flash(build_error_rows_message(error_rows), "error")`
  - `web/routes/process_excel_routes.py:196` [Route] `flash(build_error_rows_message(error_rows), "error")`
  - `web/routes/process_excel_suppliers.py:256` [Route] `flash(build_error_rows_message(error_rows), "error")`
  - `web/routes/scheduler_excel_batches.py:318` [Route] `flash(build_error_rows_message(error_rows), "error")`
  - `web/routes/scheduler_excel_calendar.py:364` [Route] `flash(build_error_rows_message(error_rows), "error")`
- **被调用者**（2 个）：`format_error_sample`, `len`

### `extract_import_stats()` [公开]
- 位置：第 156-162 行
- 参数：import_stats
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（12 处）：
  - `web/routes/equipment_excel_links.py:208` [Route] `new_count, update_count, skip_count, error_count = extract_import_stats(stats)`
  - `web/routes/equipment_excel_machines.py:314` [Route] `new_count, update_count, skip_count, error_count = extract_import_stats(import_s`
  - `web/routes/excel_demo.py:240` [Route] `new_count, update_count, skip_count, error_count = extract_import_stats(import_s`
  - `web/routes/personnel_excel_links.py:209` [Route] `new_count, update_count, skip_count, error_count = extract_import_stats(stats)`
  - `web/routes/personnel_excel_operators.py:254` [Route] `new_count, update_count, skip_count, error_count = extract_import_stats(import_s`
  - `web/routes/personnel_excel_operator_calendar.py:328` [Route] `new_count, update_count, skip_count, error_count = extract_import_stats(import_s`
  - `web/routes/process_excel_op_types.py:233` [Route] `new_count, update_count, skip_count, error_count = extract_import_stats(import_s`
  - `web/routes/process_excel_part_operation_hours.py:355` [Route] `new_count, update_count, skip_count, error_count = extract_import_stats(stats)`
  - `web/routes/process_excel_routes.py:286` [Route] `new_count, update_count, skip_count, error_count = extract_import_stats(result)`
  - `web/routes/process_excel_suppliers.py:272` [Route] `new_count, update_count, skip_count, error_count = extract_import_stats(import_s`
  - `web/routes/scheduler_excel_batches.py:338` [Route] `new_count, update_count, skip_count, error_count = extract_import_stats(import_s`
  - `web/routes/scheduler_excel_calendar.py:411` [Route] `new_count, update_count, skip_count, error_count = extract_import_stats(result)`
- **被调用者**（2 个）：`int`, `import_stats.get`

### `flash_import_result()` [公开]
- 位置：第 171-199 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（12 处）：
  - `web/routes/equipment_excel_links.py:221` [Route] `flash_import_result(`
  - `web/routes/equipment_excel_machines.py:327` [Route] `flash_import_result(`
  - `web/routes/excel_demo.py:253` [Route] `flash_import_result(`
  - `web/routes/personnel_excel_links.py:222` [Route] `flash_import_result(`
  - `web/routes/personnel_excel_operators.py:267` [Route] `flash_import_result(`
  - `web/routes/personnel_excel_operator_calendar.py:341` [Route] `flash_import_result(`
  - `web/routes/process_excel_op_types.py:247` [Route] `flash_import_result(`
  - `web/routes/process_excel_part_operation_hours.py:368` [Route] `flash_import_result(`
  - `web/routes/process_excel_routes.py:288` [Route] `flash_import_result(`
  - `web/routes/process_excel_suppliers.py:285` [Route] `flash_import_result(`
  - `web/routes/scheduler_excel_batches.py:351` [Route] `flash_import_result(`
  - `web/routes/scheduler_excel_calendar.py:425` [Route] `flash_import_result(`
- **被调用者**（5 个）：`flash`, `int`, `join`, `item.get`, `list`

### `ensure_unique_ids()` [公开]
- 位置：第 202-225 行
- 参数：rows, id_column
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `web/routes/equipment_bp.py:32` [Route] `ensure_unique_ids(rows, id_column=id_column)`
  - `web/routes/personnel_bp.py:37` [Route] `ensure_unique_ids(rows, id_column=id_column)`
  - `web/routes/process_bp.py:45` [Route] `ensure_unique_ids(rows, id_column=id_column)`
  - `web/routes/scheduler_utils.py:16` [Route] `ensure_unique_ids(rows, id_column=id_column)`
- **被调用者**（13 个）：`set`, `r.get`, `seen.add`, `join`, `ValidationError`, `isinstance`, `v.is_integer`, `strip`, `dup.add`, `list`, `str`, `sorted`, `int`

### `read_uploaded_xlsx()` [公开]
- 位置：第 228-255 行
- 参数：file_storage
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/equipment_bp.py:28` [Route] `return read_uploaded_xlsx(file_storage)`
  - `web/routes/personnel_bp.py:33` [Route] `return read_uploaded_xlsx(file_storage)`
  - `web/routes/process_bp.py:49` [Route] `return read_uploaded_xlsx(file_storage)`
  - `web/routes/scheduler_utils.py:20` [Route] `return read_uploaded_xlsx(file_storage)`
- **被调用者**（11 个）：`file_storage.read`, `int`, `tempfile.mkstemp`, `AppError`, `get_excel_backend`, `backend.read`, `get`, `len`, `os.fdopen`, `f.write`, `os.remove`

### `send_excel_template_file()` [公开]
- 位置：第 258-269 行
- 参数：template_path
- 返回类型：无注解
- **调用者**（12 处）：
  - `web/routes/equipment_excel_links.py:247` [Route] `return send_excel_template_file(template_path, download_name="设备人员关联.xlsx")`
  - `web/routes/equipment_excel_machines.py:353` [Route] `return send_excel_template_file(template_path, download_name="设备信息.xlsx")`
  - `web/routes/excel_demo.py:282` [Route] `return send_excel_template_file(template_path, download_name="人员基本信息.xlsx")`
  - `web/routes/personnel_excel_links.py:248` [Route] `return send_excel_template_file(template_path, download_name="人员设备关联.xlsx")`
  - `web/routes/personnel_excel_operators.py:294` [Route] `return send_excel_template_file(template_path, download_name="人员基本信息.xlsx")`
  - `web/routes/personnel_excel_operator_calendar.py:367` [Route] `return send_excel_template_file(template_path, download_name="人员专属工作日历.xlsx")`
  - `web/routes/process_excel_op_types.py:273` [Route] `return send_excel_template_file(template_path, download_name="工种配置.xlsx")`
  - `web/routes/process_excel_part_operation_hours.py:394` [Route] `return send_excel_template_file(template_path, download_name="零件工序工时.xlsx")`
  - `web/routes/process_excel_routes.py:314` [Route] `return send_excel_template_file(template_path, download_name="零件工艺路线.xlsx")`
  - `web/routes/process_excel_suppliers.py:311` [Route] `return send_excel_template_file(template_path, download_name="供应商配置.xlsx")`
  - `web/routes/scheduler_excel_batches.py:381` [Route] `return send_excel_template_file(template_path, download_name="批次信息.xlsx")`
  - `web/routes/scheduler_excel_calendar.py:451` [Route] `return send_excel_template_file(template_path, download_name="工作日历.xlsx")`
- **被调用者**（4 个）：`send_file`, `io.BytesIO`, `read_bytes`, `Path`

## web/routes/personnel_excel_links.py（Route 层）

### `_build_existing_operator_link_page_data()` [私有]
- 位置：第 36-60 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_operator_machine_reference_snapshot()` [私有]
- 位置：第 63-69 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_normalize_excel_link_rows()` [私有]
- 位置：第 72-81 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_render_excel_link_page()` [私有]
- 位置：第 84-106 行
- 参数：无
- 返回类型：无注解

### `excel_link_page()` [公开]
- 位置：第 110-120 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `_build_existing_operator_link_page_data`, `_render_excel_link_page`

### `excel_link_preview()` [公开]
- 位置：第 124-162 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（17 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_normalize_excel_link_rows`, `OperatorMachineService`, `link_svc.preview_import_links`, `_build_existing_operator_link_page_data`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_link_page`, `ValidationError`, `getattr`

### `excel_link_confirm()` [公开]
- 位置：第 166-229 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（25 个）：`bp.post`, `time.time`, `_parse_mode`, `load_confirm_payload`, `_build_existing_operator_link_page_data`, `preview_baseline_is_stale`, `OperatorMachineService`, `link_svc.preview_import_links`, `collect_error_rows`, `link_svc.apply_import_links`, `extract_import_stats`, `int`, `log_excel_import`, `flash_import_result`, `redirect`

### `excel_link_template()` [公开]
- 位置：第 233-275 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_link_export()` [公开]
- 位置：第 279-309 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.get`, `time.time`, `OperatorMachineQueryService`, `q.list_simple_rows`, `rows.sort`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`, `str`, `r.get`

## web/routes/personnel_excel_operator_calendar.py（Route 层）

### `_list_operator_ids()` [私有]
- 位置：第 46-48 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_operator_calendar_baseline_extra_state()` [私有]
- 位置：第 51-55 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_fallback_calendar_date_text()` [私有]
- 位置：第 58-65 行
- 参数：raw_date
- 返回类型：Name(id='str', ctx=Load())

### `_require_holiday_default_efficiency()` [私有]
- 位置：第 68-71 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())

### `_build_existing_operator_calendar_preview_data()` [私有]
- 位置：第 74-94 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_render_excel_operator_calendar_page()` [私有]
- 位置：第 97-119 行
- 参数：无
- 返回类型：无注解

### `_load_holiday_default_efficiency_for_excel()` [私有]
- 位置：第 122-147 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `excel_operator_calendar_page()` [公开]
- 位置：第 151-160 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `_build_existing_operator_calendar_preview_data`, `_render_excel_operator_calendar_page`

### `excel_operator_calendar_preview()` [公开]
- 位置：第 164-249 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（31 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_build_existing_operator_calendar_preview_data`, `ConfigService`, `_load_holiday_default_efficiency_for_excel`, `_require_holiday_default_efficiency`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `get_operator_calendar_row_validate_and_normalize`, `ExcelService`, `excel_svc.preview_import`, `_list_operator_ids`, `build_preview_baseline_token`

### `excel_operator_calendar_confirm()` [公开]
- 位置：第 253-348 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（35 个）：`bp.post`, `time.time`, `_parse_mode`, `load_confirm_payload`, `_build_existing_operator_calendar_preview_data`, `ConfigService`, `_load_holiday_default_efficiency_for_excel`, `_require_holiday_default_efficiency`, `_ensure_unique_ids`, `CalendarService`, `_list_operator_ids`, `preview_baseline_is_stale`, `get_operator_calendar_row_validate_and_normalize`, `ExcelService`, `excel_svc.preview_import`

### `excel_operator_calendar_template()` [公开]
- 位置：第 352-393 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_operator_calendar_export()` [公开]
- 位置：第 397-440 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`bp.get`, `time.time`, `CalendarService`, `cal_svc.list_operator_calendar_all`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`, `_normalize_operator_calendar_day_type`, `_normalize_yesno`

## web/routes/personnel_excel_operators.py（Route 层）

### `_validate_operator_excel_row()` [私有]
- 位置：第 35-47 行
- 参数：row
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_render_excel_operator_page()` [私有]
- 位置：第 55-77 行
- 参数：无
- 返回类型：无注解

### `_operator_team_snapshot()` [私有]
- 位置：第 80-90 行
- 参数：team_svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `excel_operator_page()` [公开]
- 位置：第 94-105 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `OperatorService`, `op_svc.build_existing_for_excel`, `_render_excel_operator_page`, `getattr`

### `excel_operator_preview()` [公开]
- 位置：第 109-181 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（27 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `OperatorService`, `ResourceTeamService`, `op_svc.build_existing_for_excel`, `ExcelService`, `svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_operator_page`

### `excel_operator_confirm()` [公开]
- 位置：第 185-274 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（35 个）：`bp.post`, `time.time`, `_parse_mode`, `load_confirm_payload`, `_ensure_unique_ids`, `OperatorService`, `ResourceTeamService`, `op_svc.build_existing_for_excel`, `preview_baseline_is_stale`, `ExcelService`, `excel_svc.preview_import`, `collect_error_rows`, `OperatorExcelImportService`, `import_svc.apply_preview_rows`, `extract_import_stats`

### `excel_operator_template()` [公开]
- 位置：第 278-321 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_operator_export()` [公开]
- 位置：第 325-355 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.get`, `time.time`, `build_existing_for_excel`, `list`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `existing.values`, `OperatorService`, `template_def.get`, `getattr`, `len`, `r.get`

## web/routes/process_excel_op_types.py（Route 层）

### `_render_excel_op_type_page()` [私有]
- 位置：第 39-61 行
- 参数：无
- 返回类型：无注解

### `_normalize_op_type_category()` [私有]
- 位置：第 64-65 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_op_type_name()` [私有]
- 位置：第 68-69 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_build_op_type_row_validator()` [私有]
- 位置：第 72-117 行
- 参数：无
- 返回类型：无注解

### `excel_op_type_page()` [公开]
- 位置：第 121-131 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `OpTypeService`, `svc.build_existing_for_excel`, `_render_excel_op_type_page`, `getattr`

### `excel_op_type_preview()` [公开]
- 位置：第 135-178 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（19 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `OpTypeService`, `svc.build_existing_for_excel`, `_build_op_type_row_validator`, `ExcelService`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_op_type_page`

### `excel_op_type_confirm()` [公开]
- 位置：第 182-254 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（31 个）：`bp.post`, `time.time`, `_parse_mode`, `load_confirm_payload`, `_ensure_unique_ids`, `OpTypeService`, `op_type_svc.build_existing_for_excel`, `preview_baseline_is_stale`, `_build_op_type_row_validator`, `ExcelService`, `excel_svc.preview_import`, `collect_error_rows`, `OpTypeExcelImportService`, `import_svc.apply_preview_rows`, `extract_import_stats`

### `excel_op_type_template()` [公开]
- 位置：第 258-300 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_op_type_export()` [公开]
- 位置：第 304-333 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `OpTypeService`, `svc.list`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`

## web/routes/process_excel_part_operation_hours.py（Route 层）

### `_part_op_hours_mode_options()` [私有]
- 位置：第 46-47 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_parse_seq()` [私有]
- 位置：第 50-72 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_build_existing_internal()` [私有]
- 位置：第 75-107 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_normalize_rows()` [私有]
- 位置：第 110-122 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_build_validator()` [私有]
- 位置：第 125-157 行
- 参数：meta_all
- 返回类型：无注解

### `_build_part_op_hours_extra_state()` [私有]
- 位置：第 160-169 行
- 参数：meta_all
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_existing_for_append()` [私有]
- 位置：第 172-184 行
- 参数：existing_internal
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_rewrite_append_preview_rows()` [私有]
- 位置：第 187-197 行
- 参数：preview_rows, mode
- 返回类型：Constant(value=None, kind=None)

### `_render_excel_part_op_hours_page()` [私有]
- 位置：第 200-223 行
- 参数：无
- 返回类型：无注解

### `excel_part_op_hours_page()` [公开]
- 位置：第 227-236 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `_build_existing_internal`, `_render_excel_part_op_hours_page`

### `excel_part_op_hours_preview()` [公开]
- 位置：第 240-292 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（22 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_normalize_rows`, `_ensure_unique_ids`, `_build_existing_internal`, `_build_validator`, `ExcelService`, `excel_svc.preview_import`, `_rewrite_append_preview_rows`, `build_preview_baseline_token`, `int`, `log_excel_import`

### `excel_part_op_hours_confirm()` [公开]
- 位置：第 296-375 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（32 个）：`bp.post`, `time.time`, `_parse_mode`, `load_confirm_payload`, `_ensure_unique_ids`, `_build_existing_internal`, `_build_validator`, `ExcelService`, `preview_baseline_is_stale`, `excel_svc.preview_import`, `_rewrite_append_preview_rows`, `collect_error_rows`, `PartOperationHoursExcelImportService`, `import_svc.apply_preview_rows`, `extract_import_stats`

### `excel_part_op_hours_template()` [公开]
- 位置：第 379-421 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_part_op_hours_export()` [公开]
- 位置：第 425-454 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `PartOperationQueryService`, `q.list_internal_active_hours`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`, `float`

## web/routes/process_excel_routes.py（Route 层）

### `_validate_route_row()` [私有]
- 位置：第 41-61 行
- 参数：part_svc, row
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_render_excel_routes_page()` [私有]
- 位置：第 64-91 行
- 参数：无
- 返回类型：无注解

### `excel_routes_page()` [公开]
- 位置：第 95-106 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `PartService`, `svc.build_existing_for_excel_routes`, `_render_excel_routes_page`, `getattr`

### `excel_routes_preview()` [公开]
- 位置：第 110-155 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`bp.post`, `time.time`, `_parse_mode`, `_strict_mode_enabled`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `PartService`, `part_svc.build_existing_for_excel_routes`, `ExcelService`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_routes_page`

### `excel_routes_confirm()` [公开]
- 位置：第 159-295 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（37 个）：`bp.post`, `time.time`, `_parse_mode`, `_strict_mode_enabled`, `load_confirm_payload`, `_ensure_unique_ids`, `PartService`, `part_svc.build_existing_for_excel_routes`, `preview_baseline_is_stale`, `ExcelService`, `excel_svc.preview_import`, `collect_error_rows`, `TransactionManager`, `int`, `log_excel_import`

### `excel_routes_template()` [公开]
- 位置：第 299-341 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_routes_export()` [公开]
- 位置：第 345-375 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `PartService`, `svc.list`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`

## web/routes/process_excel_suppliers.py（Route 层）

### `_render_excel_supplier_page()` [私有]
- 位置：第 40-62 行
- 参数：无
- 返回类型：无注解

### `_normalize_supplier_status()` [私有]
- 位置：第 65-66 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_resolve_op_type_name()` [私有]
- 位置：第 69-78 行
- 参数：value, op_type_svc
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_supplier_op_type_snapshot()` [私有]
- 位置：第 81-91 行
- 参数：op_type_svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_normalize_supplier_default_days()` [私有]
- 位置：第 94-104 行
- 参数：row
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `excel_supplier_page()` [公开]
- 位置：第 108-118 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `SupplierService`, `svc.build_existing_for_excel`, `_render_excel_supplier_page`, `getattr`

### `excel_supplier_preview()` [公开]
- 位置：第 122-194 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（25 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `SupplierService`, `svc.build_existing_for_excel`, `OpTypeService`, `ExcelService`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_supplier_page`

### `excel_supplier_confirm()` [公开]
- 位置：第 198-292 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（37 个）：`bp.post`, `time.time`, `_parse_mode`, `load_confirm_payload`, `_ensure_unique_ids`, `SupplierService`, `OpTypeService`, `supplier_svc.build_existing_for_excel`, `preview_baseline_is_stale`, `ExcelService`, `excel_svc.preview_import`, `collect_error_rows`, `SupplierExcelImportService`, `import_svc.apply_preview_rows`, `extract_import_stats`

### `excel_supplier_template()` [公开]
- 位置：第 296-338 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_supplier_export()` [公开]
- 位置：第 342-370 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `list_for_export_rows`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `SupplierService`, `template_def.get`, `getattr`, `len`

## web/routes/process_parts.py（Route 层）

### `_summarize_active_ops()` [私有]
- 位置：第 18-23 行
- 参数：ops
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_surface_route_warnings()` [私有]
- 位置：第 26-43 行
- 参数：messages
- 返回类型：Constant(value=None, kind=None)

### `_build_ops_by_group()` [私有]
- 位置：第 46-55 行
- 参数：active_ops
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `list_parts()` [公开]
- 位置：第 59-81 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.get`, `PartService`, `parse_page_args`, `svc.list`, `paginate_rows`, `render_template`, `strip`, `view_rows.append`, `getattr`, `len`

### `create_part()` [公开]
- 位置：第 85-108 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.post`, `get`, `_strict_mode_enabled`, `PartService`, `svc.create`, `flash`, `_surface_route_warnings`, `redirect`, `getattr`, `url_for`

### `part_detail()` [公开]
- 位置：第 112-151 行
- 参数：part_no
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（17 个）：`bp.get`, `PartService`, `p_svc.get_template_detail`, `to_dict`, `_summarize_active_ops`, `set`, `_build_ops_by_group`, `render_template`, `o.to_dict`, `gr.to_dict`, `p_svc.calc_deletable_external_group_ids`, `getattr`, `list`, `v.to_dict`, `SupplierService`

### `update_part()` [公开]
- 位置：第 155-162 行
- 参数：part_no
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `get`, `PartService`, `svc.update`, `flash`, `redirect`, `url_for`, `getattr`

### `delete_part()` [公开]
- 位置：第 166-173 行
- 参数：part_no
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.post`, `PartService`, `redirect`, `svc.delete`, `flash`, `url_for`, `getattr`

### `bulk_delete_parts()` [公开]
- 位置：第 177-205 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`bp.post`, `getlist`, `PartService`, `flash`, `redirect`, `join`, `url_for`, `getattr`, `svc.delete`, `failed.append`, `failed_details.append`, `exception`, `len`, `str`

### `reparse_part()` [公开]
- 位置：第 209-228 行
- 参数：part_no
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.post`, `get`, `_strict_mode_enabled`, `PartService`, `time.time`, `int`, `flash`, `_surface_route_warnings`, `redirect`, `svc.reparse_and_save`, `url_for`, `getattr`, `len`

### `update_internal_hours()` [公开]
- 位置：第 232-238 行
- 参数：part_no, seq
- 返回类型：无注解
- **调用者**（1 处）：
  - `core/services/process/part_operation_hours_excel_import_service.py:87` [Service] `self.part_svc.update_internal_hours(part_no=part_no, seq=seq, setup_hours=sh, un`
- **被调用者**（8 个）：`bp.post`, `get`, `PartService`, `svc.update_internal_hours`, `flash`, `redirect`, `url_for`, `getattr`

### `set_group_mode()` [公开]
- 位置：第 242-272 行
- 参数：part_no, group_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.post`, `get`, `_strict_mode_enabled`, `items`, `ExternalGroupService`, `redirect`, `svc.set_merge_mode`, `flash`, `_surface_route_warnings`, `url_for`, `k.startswith`, `int`, `getattr`, `k.replace`, `_merge_mode_zh`

### `delete_group()` [公开]
- 位置：第 276-280 行
- 参数：part_no, group_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `PartService`, `svc.delete_external_group`, `flash`, `redirect`, `url_for`, `getattr`, `result.get`

## web/routes/scheduler_batches.py（Route 层）

### `batches_page()` [公开]
- 位置：第 30-111 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（34 个）：`bp.get`, `BatchService`, `ConfigService`, `strip`, `parse_page_args`, `batch_svc.list`, `paginate_rows`, `cfg_svc.get_snapshot`, `cfg_svc.get_available_strategies`, `cfg_svc.list_presets`, `cfg_svc.get_active_preset`, `cfg_svc.get_active_preset_reason`, `ScheduleHistoryQueryService`, `_normalize_warning_texts`, `len`

### `batches_manage_page()` [公开]
- 位置：第 115-159 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（16 个）：`bp.get`, `BatchService`, `strip`, `parse_page_args`, `batch_svc.list`, `paginate_rows`, `PartService`, `p_svc.list`, `render_template`, `view_rows.append`, `getattr`, `get`, `b.to_dict`, `_priority_zh`, `_ready_zh`

### `create_batch()` [公开]
- 位置：第 163-194 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.post`, `get`, `_strict_mode_enabled`, `BatchService`, `batch_svc.create_batch_from_template`, `flash`, `_surface_schedule_warnings`, `redirect`, `getattr`, `batch_svc.consume_user_visible_warnings`, `url_for`, `len`, `batch_svc.list_operations`

### `delete_batch()` [公开]
- 位置：第 198-212 行
- 参数：batch_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.post`, `BatchService`, `strip`, `_safe_next_url`, `batch_svc.delete`, `flash`, `redirect`, `getattr`, `url_for`, `get`

### `bulk_delete_batches()` [公开]
- 位置：第 216-244 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`bp.post`, `getlist`, `BatchService`, `flash`, `redirect`, `join`, `url_for`, `getattr`, `batch_svc.delete`, `failed.append`, `failed_details.append`, `exception`, `len`, `str`

### `_next_batch_id_like()` [私有]
- 位置：第 247-267 行
- 参数：src, exists_fn
- 返回类型：Name(id='str', ctx=Load())

### `_bulk_update_one_batch()` [私有]
- 位置：第 270-292 行
- 参数：batch_svc, bid
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `bulk_copy_batches()` [公开]
- 位置：第 297-326 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（16 个）：`bp.post`, `getlist`, `BatchService`, `flash`, `redirect`, `url_for`, `getattr`, `_next_batch_id_like`, `batch_svc.copy_batch`, `mappings.append`, `str`, `failed.append`, `exception`, `len`, `join`

### `bulk_update_batches()` [公开]
- 位置：第 330-358 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.post`, `getlist`, `get`, `BatchService`, `flash`, `redirect`, `strip`, `_bulk_update_one_batch`, `url_for`, `remark.strip`, `getattr`, `str`, `failed.append`, `len`, `join`

### `generate_ops()` [公开]
- 位置：第 362-384 行
- 参数：batch_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`bp.post`, `BatchService`, `_strict_mode_enabled`, `batch_svc.get`, `redirect`, `get`, `batch_svc.create_batch_from_template`, `len`, `flash`, `_surface_schedule_warnings`, `url_for`, `getattr`, `batch_svc.list_operations`, `batch_svc.consume_user_visible_warnings`

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

## web/routes/scheduler_excel_calendar.py（Route 层）

### `_canonicalize_calendar_date()` [私有]
- 位置：第 47-51 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_build_existing_preview_data()` [私有]
- 位置：第 54-70 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_calendar_baseline_extra_state()` [私有]
- 位置：第 73-74 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_require_holiday_default_efficiency()` [私有]
- 位置：第 77-80 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())

### `_render_excel_calendar_page()` [私有]
- 位置：第 83-105 行
- 参数：无
- 返回类型：无注解

### `_load_holiday_default_efficiency_for_excel()` [私有]
- 位置：第 108-130 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `excel_calendar_page()` [公开]
- 位置：第 134-143 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `_build_existing_preview_data`, `_render_excel_calendar_page`

### `excel_calendar_preview()` [公开]
- 位置：第 147-259 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（33 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_build_existing_preview_data`, `ConfigService`, `_load_holiday_default_efficiency_for_excel`, `_require_holiday_default_efficiency`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `ExcelService`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`

### `excel_calendar_confirm()` [公开]
- 位置：第 263-432 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（48 个）：`bp.post`, `time.time`, `_parse_mode`, `load_confirm_payload`, `_build_existing_preview_data`, `ConfigService`, `_load_holiday_default_efficiency_for_excel`, `_require_holiday_default_efficiency`, `preview_baseline_is_stale`, `_ensure_unique_ids`, `ExcelService`, `excel_svc.preview_import`, `collect_error_rows`, `CalendarService`, `set`

### `excel_calendar_template()` [公开]
- 位置：第 436-477 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_calendar_export()` [公开]
- 位置：第 481-521 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`bp.get`, `time.time`, `CalendarService`, `cal_svc.list_all`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`, `_normalize_day_type`, `_normalize_yesno`

## web/routes/scheduler_run.py（Route 层）

### `_parse_optional_checkbox_flag()` [私有]
- 位置：第 12-22 行
- 参数：name
- 返回类型：无注解

### `run_schedule()` [公开]
- 位置：第 26-74 行
- 参数：无
- 返回类型：无注解
- **调用者**（2 处）：
  - `web/routes/scheduler_week_plan.py:175` [Route] `result = sch_svc.run_schedule(`
  - `core/services/scheduler/schedule_optimizer.py:283` [Service] `说明：为保证兼容，本函数尽量保持与原 `ScheduleService.run_schedule()` 相同的口径与留痕结构。`
- **被调用者**（19 个）：`bp.post`, `getlist`, `_parse_optional_checkbox_flag`, `_strict_mode_enabled`, `ScheduleService`, `redirect`, `get`, `sch_svc.run_schedule`, `result.get`, `flash`, `_surface_schedule_warnings`, `url_for`, `getattr`, `join`, `summary.get`

## web/routes/scheduler_week_plan.py（Route 层）

### `_get_int_arg()` [私有]
- 位置：第 21-28 行
- 参数：name, default
- 返回类型：Name(id='int', ctx=Load())

### `_parse_optional_checkbox_flag()` [私有]
- 位置：第 31-41 行
- 参数：name
- 返回类型：无注解

### `week_plan_page()` [公开]
- 位置：第 45-91 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（21 个）：`bp.get`, `_get_int_arg`, `GanttService`, `svc.get_latest_version_or_1`, `svc.resolve_week_range`, `normalize_version_or_latest`, `list_versions`, `svc.get_week_plan_rows`, `int`, `render_template`, `strip`, `get`, `data.get`, `getattr`, `ScheduleHistoryQueryService`

### `week_plan_export()` [公开]
- 位置：第 95-154 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（22 个）：`bp.get`, `time.time`, `_get_int_arg`, `GanttService`, `strip`, `normalize_version_or_latest`, `svc.get_week_plan_rows`, `int`, `data.get`, `build_xlsx_bytes`, `log_excel_export`, `send_file`, `getattr`, `get`, `flash`

### `simulate_schedule()` [公开]
- 位置：第 158-199 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（18 个）：`bp.post`, `getlist`, `_parse_optional_checkbox_flag`, `_strict_mode_enabled`, `ScheduleService`, `get`, `flash`, `redirect`, `sch_svc.run_schedule`, `int`, `_surface_schedule_warnings`, `isoformat`, `url_for`, `getattr`, `result.get`

---
- 分析函数/方法数：209
- 找到调用关系：114 处
- 跨层边界风险：0 项
