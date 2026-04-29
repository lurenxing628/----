# 引用链追踪报告（深度 Review 辅助）

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/infrastructure/database.py（Infrastructure 层）

### `_is_windows_lock_error()` [私有]
- 位置：第 26-35 行
- 参数：e
- 返回类型：Name(id='bool', ctx=Load())

### `_cleanup_sqlite_sidecars()` [私有]
- 位置：第 38-47 行
- 参数：db_path, logger
- 返回类型：Constant(value=None)

### `_restore_db_file_from_backup()` [私有]
- 位置：第 50-93 行
- 参数：backup_path, db_path, logger, retries, base_delay_s
- 返回类型：Constant(value=None)

### `get_connection()` [公开]
- 位置：第 96-113 行
- 参数：db_path
- 返回类型：Attribute(value=Name(id='sqlite3', ctx=Load()), attr='Connec
- **调用者**（3 处）：
  - `web/bootstrap/plugins.py:210` [Bootstrap] `conn0 = get_connection(database_path)`
  - `web/bootstrap/factory.py:106` [Bootstrap] `conn = get_connection(bm.db_path)`
  - `web/bootstrap/factory.py:346` [Bootstrap] `conn = get_connection(app.config["DATABASE_PATH"])`
- **被调用者**（4 个）：`dirname`, `sqlite3.connect`, `conn.execute`, `os.makedirs`

### `_load_schema_sql()` [私有]
- 位置：第 116-118 行
- 参数：schema_path
- 返回类型：Name(id='str', ctx=Load())

### `_build_schema_exec_script()` [私有]
- 位置：第 121-131 行
- 参数：sql
- 返回类型：Name(id='str', ctx=Load())

### `_declared_schema_tables()` [私有]
- 位置：第 134-141 行
- 参数：schema_sql
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_schema_create_table_statements()` [私有]
- 位置：第 144-152 行
- 参数：schema_sql
- 返回类型：Name(id='dict', ctx=Load())

### `_schema_index_statements()` [私有]
- 位置：第 155-163 行
- 参数：schema_sql
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_build_statement_script()` [私有]
- 位置：第 166-170 行
- 参数：statements
- 返回类型：Name(id='str', ctx=Load())

### `_missing_schema_tables()` [私有]
- 位置：第 173-175 行
- 参数：conn, schema_sql
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_bootstrap_missing_tables_from_schema()` [私有]
- 位置：第 178-204 行
- 参数：conn, schema_sql, logger
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_cleanup_probe_db()` [私有]
- 位置：第 207-214 行
- 参数：db_path
- 返回类型：Constant(value=None)

### `_build_contract_error()` [私有]
- 位置：第 217-232 行
- 参数：无
- 返回类型：Name(id='MigrationContractError', ctx=Load())

### `_preflight_migration_contract()` [私有]
- 位置：第 235-292 行
- 参数：db_path
- 返回类型：Constant(value=None)

### `ensure_schema()` [公开]
- 位置：第 295-383 行
- 参数：db_path, logger, schema_path, backup_dir
- 返回类型：Constant(value=None)
- **调用者**（2 处）：
  - `web/routes/system_backup.py:258` [Route] `ensure_schema(`
  - `web/bootstrap/factory.py:274` [Bootstrap] `ensure_schema(`
- **被调用者**（22 个）：`abspath`, `get_connection`, `candidates.append`, `FileNotFoundError`, `exists`, `_migrate_with_backup`, `join`, `getattr`, `_load_schema_sql`, `_build_schema_exec_script`, `_has_no_user_tables`, `_ensure_schema_version`, `_get_schema_version`, `conn.commit`, `conn.close`

### `_ensure_schema_version()` [私有]
- 位置：第 386-411 行
- 参数：conn, logger
- 返回类型：Constant(value=None)

### `_is_truly_empty_db()` [私有]
- 位置：第 414-420 行
- 参数：conn
- 返回类型：Name(id='bool', ctx=Load())

### `_list_user_tables()` [私有]
- 位置：第 423-434 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_has_no_user_tables()` [私有]
- 位置：第 437-438 行
- 参数：conn
- 返回类型：Name(id='bool', ctx=Load())

### `_detect_schema_is_current()` [私有]
- 位置：第 441-491 行
- 参数：conn
- 返回类型：Name(id='bool', ctx=Load())

### `_get_schema_version()` [私有]
- 位置：第 494-505 行
- 参数：conn
- 返回类型：Name(id='int', ctx=Load())

### `_set_schema_version()` [私有]
- 位置：第 508-509 行
- 参数：conn, version
- 返回类型：Constant(value=None)

### `_migrate_with_backup()` [私有]
- 位置：第 512-625 行
- 参数：db_path, from_version, to_version, backup_dir
- 返回类型：Constant(value=None)

### `_run_migration()` [私有]
- 位置：第 628-632 行
- 参数：conn, target_version, logger
- 返回类型：Name(id='MigrationOutcome', ctx=Load())

## core/infrastructure/migrations/__init__.py（Infrastructure 层）

### `run_migration()` [公开]
- 位置：第 27-31 行
- 参数：conn, target_version, logger
- 返回类型：Name(id='MigrationOutcome', ctx=Load())
- **调用者**（1 处）：
  - `core/infrastructure/database.py:632` [Infrastructure] `return run_migration(conn, target_version=int(target_version), logger=logger)`
- **被调用者**（4 个）：`MIGRATIONS.get`, `fn`, `int`, `RuntimeError`

## core/infrastructure/migrations/v7.py（Infrastructure 层）

### `_duplicate_schedule_rows()` [私有]
- 位置：第 8-18 行
- 参数：conn
- 返回类型：无注解

### `run()` [公开]
- 位置：第 21-38 行
- 参数：conn, logger
- 返回类型：Name(id='MigrationOutcome', ctx=Load())
- **调用者**（19 处）：
  - `web/bootstrap/entrypoint.py:260` [Bootstrap] `app.run(host=host, port=port, debug=debug, use_reloader=True)`
  - `web/bootstrap/launcher_processes.py:17` [Bootstrap] `result = subprocess.run(`
  - `web/bootstrap/launcher_processes.py:48` [Bootstrap] `result = subprocess.run(`
  - `web/bootstrap/launcher_processes.py:133` [Bootstrap] `result = subprocess.run(`
  - `scripts/sync_debt_ledger.py:39` [Script] `proc = subprocess.run(`
  - `scripts/sync_debt_ledger.py:53` [Script] `proc = subprocess.run(`
  - `scripts/run_quality_gate.py:71` [Script] `completed = subprocess.run(`
  - `scripts/run_quality_gate.py:161` [Script] `completed = subprocess.run(`
  - `scripts/run_quality_gate.py:173` [Script] `completed = subprocess.run(`
  - `scripts/run_quality_gate.py:463` [Script] `completed = subprocess.run(`
  - `scripts/run_quality_gate.py:477` [Script] `completed = subprocess.run(`
  - `tools/test_registry.py:153` [Tool] `tracked = subprocess.run(`
  - `tools/collect_full_test_debt.py:43` [Tool] `completed = subprocess.run(`
  - `tools/collect_full_test_debt.py:58` [Tool] `completed = subprocess.run(`
  - `tools/quality_gate_shared.py:453` [Tool] `proc = subprocess.run(`
  - `tools/quality_gate_shared.py:514` [Tool] `proc = subprocess.run(`
  - `tools/quality_gate_shared.py:778` [Tool] `proc = subprocess.run(`
  - `tools/quality_gate_shared.py:1138` [Tool] `completed = subprocess.run(`
  - `tools/check_full_test_debt.py:347` [Tool] `completed = subprocess.run(`
- **被调用者**（8 个）：`_duplicate_schedule_rows`, `conn.execute`, `table_exists`, `RuntimeError`, `fallback_log`, `samples.append`, `isinstance`, `join`

## core/models/scheduler_degradation_messages.py（Model 层）

### `public_degradation_event_message()` [公开]
- 位置：第 57-59 行
- 参数：code
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（5 处）：
  - `web/viewmodels/scheduler_degradation_presenter.py:44` [ViewModel] `return public_degradation_event_message(code) if code else ""`
  - `web/viewmodels/scheduler_summary_display.py:85` [ViewModel] `if message == public_degradation_event_message(item.get("code")):`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:202` [Service] `message=public_degradation_event_message(code),`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:220` [Service] `message=public_degradation_event_message(code),`
  - `core/algorithms/greedy/schedule_params.py:38` [Algorithm] `message = public_degradation_event_message(code)`
- **被调用者**（3 个）：`strip`, `_PUBLIC_EVENT_MESSAGES.get`, `str`

### `_public_degradation_event_code()` [私有]
- 位置：第 62-66 行
- 参数：code
- 返回类型：Name(id='str', ctx=Load())

### `is_public_freeze_degradation_message()` [公开]
- 位置：第 69-73 行
- 参数：message
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `web/viewmodels/scheduler_degradation_presenter.py:42` [ViewModel] `if code == "freeze_window_degraded" and is_public_freeze_degradation_message(nor`
  - `web/viewmodels/scheduler_summary_display.py:83` [ViewModel] `if not is_public_freeze_degradation_message(message):`
- **被调用者**（2 个）：`strip`, `str`

### `public_summary_warning_messages()` [公开]
- 位置：第 76-94 行
- 参数：value
- 返回类型：Subscript(value=Name(id='list', ctx=Load()), slice=Name(id='
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_summary_display.py:311` [ViewModel] `public_warning_messages = public_summary_warning_messages(summary_dict.get("warn`
- **被调用者**（7 个）：`set`, `isinstance`, `strip`, `seen.add`, `out.append`, `list`, `str`

### `public_summary_merge_error_code()` [公开]
- 位置：第 97-103 行
- 参数：value
- 返回类型：BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Con
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_summary_display.py:213` [ViewModel] `"summary_merge_error": public_summary_merge_error_code(warning_pipeline.get("sum`
- **被调用者**（2 个）：`strip`, `str`

### `_event_value()` [私有]
- 位置：第 106-109 行
- 参数：event, key
- 返回类型：Name(id='Any', ctx=Load())

### `public_degradation_events()` [公开]
- 位置：第 112-132 行
- 参数：events
- 返回类型：Subscript(value=Name(id='list', ctx=Load()), slice=Subscript
- **调用者**（5 处）：
  - `web/bootstrap/plugins.py:46` [Bootstrap] `base["degradation_events"] = public_degradation_events(merged.to_list())`
  - `core/services/scheduler/resource_dispatch_support.py:155` [Service] `"degradation_events": public_degradation_events(collector.to_list()),`
  - `core/services/scheduler/gantt_contract.py:82` [Service] `"degradation_events": public_degradation_events(self.degradation_events or []),`
  - `core/services/scheduler/config/config_page_outcome.py:130` [Service] `for event in public_degradation_events(events)`
  - `core/services/scheduler/config/config_page_outcome.py:242` [Service] `"degradation_events": public_degradation_events(raw_events),`
- **被调用者**（10 个）：`list`, `strip`, `_public_degradation_event_code`, `max`, `order.append`, `int`, `str`, `public_degradation_event_message`, `get`, `_event_value`

## core/plugins/manager.py（Other 层）

### `_normalize_yes_no()` [私有]
- 位置：第 19-20 行
- 参数：value, default
- 返回类型：Name(id='str', ctx=Load())

### `PluginStatus.to_dict()` [公开]
- 位置：第 35-46 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（87 处）：
  - `web/routes/material.py:26` [Route] `items = [m.to_dict() for m in material_svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/system_logs.py:63` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/system_backup.py:51` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_utils.py:172` [Route] `d = it.to_dict()`
  - `web/routes/personnel_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:46` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:165` [Route] `operator=op.to_dict(),`
  - `web/routes/equipment_pages.py:221` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:234` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/system_history.py:37` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:54` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/process_parts.py:116` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:117` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:118` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:147` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:437` [Route] `result = stats.to_dict()`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:52` [Route] `selected_history = selected_history_item.to_dict() if hasattr(selected_history_i`
  - `web/routes/domains/scheduler/scheduler_batches.py:51` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/domains/scheduler/scheduler_batches.py:139` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:22` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_gantt.py:42` [Route] `selected = item.to_dict() if item and hasattr(item, "to_dict") else None`
  - `web/routes/domains/scheduler/scheduler_gantt.py:100` [Route] `version_resolution=version_resolution.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_analysis.py:22` [Route] `return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})`
  - `web/routes/domains/scheduler/scheduler_analysis.py:209` [Route] `version_resolution=version_resolution.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:196` [Route] `d = op.to_dict()`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:247` [Route] `batch=b.to_dict(),`
  - `web/bootstrap/plugins.py:55` [Bootstrap] `registry = PluginRegistry().to_dict()`
  - `web/viewmodels/scheduler_batches_page.py:119` [ViewModel] `**batch.to_dict(),`
  - `web/viewmodels/system_logs_vm.py:117` [ViewModel] `d = it.to_dict() if hasattr(it, "to_dict") else (it if isinstance(it, dict) else`
  - `web/viewmodels/scheduler_analysis_trends.py:107` [ViewModel] `d = h.to_dict() if hasattr(h, "to_dict") else (h if isinstance(h, dict) else {})`
  - `web/viewmodels/scheduler_analysis_trends.py:153` [ViewModel] `return selected_item.to_dict() if hasattr(selected_item, "to_dict") else (select`
  - `core/services/scheduler/calendar_admin.py:306` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:373` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:378` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/schedule_service.py:301` [Service] `"summary": orchestration.summary_contract.to_dict(),`
  - `core/services/scheduler/gantt_contract.py:133` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/batch_service.py:198` [Service] `self.batch_repo.create(batch.to_dict())`
  - `core/services/scheduler/gantt_service.py:271` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:363` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/batch_excel_import.py:104` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config/config_page_save_policy.py:79` [Service] `values = snapshot.to_dict()`
  - `core/services/scheduler/config/config_page_save_policy.py:91` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_page_save_policy.py:105` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_page_save_policy.py:118` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_page_save_policy.py:144` [Service] `values = normalized_snapshot.to_dict()`
  - `core/services/scheduler/config/config_presets.py:53` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:62` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:70` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:95` [Service] `left = a.to_dict()`
  - `core/services/scheduler/config/config_presets.py:96` [Service] `right = b.to_dict()`
  - `core/services/scheduler/config/config_presets.py:134` [Service] `canonical = snapshot.to_dict()`
  - `core/services/scheduler/config/config_presets.py:159` [Service] `return json.dumps(snapshot.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/config/config_page_outcome.py:121` [Service] `data = snapshot.to_dict()`
  - `core/services/scheduler/config/config_page_outcome.py:192` [Service] `return self.snapshot.to_dict()`
  - `core/services/scheduler/config/config_page_outcome.py:195` [Service] `effective = self.snapshot.to_dict()`
  - `core/services/scheduler/config/config_page_outcome.py:216` [Service] `"effective_snapshot": self.snapshot.to_dict(),`
  - `core/services/scheduler/config/config_page_outcome.py:217` [Service] `"normalized_snapshot": self.normalized_snapshot.to_dict() if self.normalized_sna`
  - `core/services/scheduler/config/config_preset_service.py:108` [Service] `return dict(snapshot.to_dict())`
  - `core/services/scheduler/config/config_preset_service.py:239` [Service] `config_updates = [(key, str(value), None) for key, value in snapshot.to_dict().i`
  - `core/services/scheduler/config/config_page_save_service.py:57` [Service] `payload = current_snapshot.to_dict()`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:169` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:195` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:474` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:489` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/optimizer_local_search.py:140` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/optimizer_local_search.py:154` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/summary/schedule_summary.py:83` [Service] `return snapshot.to_dict().get(str(key or "").strip())`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:32` [Service] `).to_dict()`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:237` [Service] `"metrics": ctx.best_metrics.to_dict() if ctx.best_metrics is not None else None,`
  - `core/services/common/pandas_backend.py:106` [Service] `raw_rows = df.to_dict(orient="records")`
  - `core/services/equipment/machine_excel_import_service.py:106` [Service] `out = stats.to_dict()`
  - `core/services/personnel/resource_team_service.py:74` [Service] `return [team.to_dict() for team in self.list(status=status)]`
  - `core/services/personnel/operator_excel_import_service.py:90` [Service] `out = stats.to_dict()`
  - `core/services/material/material_service.py:82` [Service] `self.op_logger.info(module="material", action="create", target_type="material", `
  - `core/services/process/part_operation_hours_excel_import_service.py:70` [Service] `return stats.to_dict(total_rows=len(preview_rows))`
  - `core/services/process/op_type_excel_import_service.py:79` [Service] `out = stats.to_dict()`
  - `core/services/process/supplier_excel_import_service.py:108` [Service] `out = stats.to_dict()`
  - `core/services/process/route_parser.py:60` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:80` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:81` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`

### `get_plugin_status()` [公开]
- 位置：第 61-72 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`_STATE.get`, `PluginRegistry`, `hasattr`, `registry.to_dict`, `to_dict`, `list`, `registry_dict.get`, `s.to_dict`

### `reset_plugin_state()` [公开]
- 位置：第 75-91 行
- 参数：base_dir
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（1 处）：
  - `web/bootstrap/plugins.py:242` [Bootstrap] `plugin_status = reset_plugin_state(base_dir)`
- **被调用者**（5 个）：`PluginRegistry`, `join`, `_STATE.update`, `get_plugin_status`, `abspath`

### `get_plugin_registry()` [公开]
- 位置：第 94-96 行
- 参数：无
- 返回类型：Name(id='PluginRegistry', ctx=Load())
- **调用者**（1 处）：
  - `core/services/common/excel_backend_factory.py:40` [Service] `reg = get_plugin_registry()`
- **被调用者**（3 个）：`_STATE.get`, `isinstance`, `PluginRegistry`

### `PluginManager.load_from_base_dir()` [公开]
- 位置：第 117-295 行
- 参数：base_dir
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（1 处）：
  - `web/bootstrap/plugins.py:232` [Bootstrap] `plugin_status = PluginManager.load_from_base_dir(base_dir, config_reader=config_`
- **被调用者**（42 个）：`abspath`, `bootstrap_vendor_paths`, `join`, `normcase`, `PluginRegistry`, `str`, `sorted`, `_STATE.update`, `get_plugin_status`, `realpath`, `callable`, `getattr`, `isinstance`, `isdir`, `os.listdir`

## core/services/scheduler/run/freeze_window.py（Service 层）

### `_init_freeze_meta()` [私有]
- 位置：第 44-55 行
- 参数：meta
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_freeze_config_degraded()` [私有]
- 位置：第 58-66 行
- 参数：cfg
- 返回类型：Name(id='bool', ctx=Load())

### `_set_freeze_disabled()` [私有]
- 位置：第 69-71 行
- 参数：meta, reason
- 返回类型：Constant(value=None)

### `_freeze_window_days()` [私有]
- 位置：第 74-102 行
- 参数：cfg, prev_version
- 返回类型：Name(id='int', ctx=Load())

### `_record_freeze_degradation()` [私有]
- 位置：第 105-123 行
- 参数：meta, warnings, message
- 返回类型：Constant(value=None)

### `_finalize_freeze_application_status()` [私有]
- 位置：第 126-142 行
- 参数：meta
- 返回类型：Constant(value=None)

### `_invalid_schedule_row_sample()` [私有]
- 位置：第 145-156 行
- 参数：row
- 返回类型：Name(id='str', ctx=Load())

### `_load_schedule_map()` [私有]
- 位置：第 159-199 行
- 参数：svc
- 返回类型：Name(id='_LoadedScheduleMapOutcome', ctx=Load())

### `_max_seq_by_batch()` [私有]
- 位置：第 202-213 行
- 参数：schedule_map, op_by_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_prefix_op_ids_for_batch()` [私有]
- 位置：第 216-217 行
- 参数：operations, bid, max_seq
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_cache_seed_for_prefix()` [私有]
- 位置：第 220-234 行
- 参数：svc
- 返回类型：Name(id='int', ctx=Load())

### `_discard_seed_cache()` [私有]
- 位置：第 237-239 行
- 参数：prefix, seed_tmp
- 返回类型：Constant(value=None)

### `_build_seed_results()` [私有]
- 位置：第 242-273 行
- 参数：frozen_op_ids
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `_empty_freeze_seed_result()` [私有]
- 位置：第 276-282 行
- 参数：freeze_meta, warnings
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_prepare_freeze_seed_scope()` [私有]
- 位置：第 285-322 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_load_previous_schedule_for_freeze()` [私有]
- 位置：第 325-370 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_apply_freeze_prefixes()` [私有]
- 位置：第 373-415 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Name(id='i

### `_finish_freeze_seed_result()` [私有]
- 位置：第 418-433 行
- 参数：frozen_op_ids
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `build_freeze_window_seed()` [公开]
- 位置：第 436-491 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`_init_freeze_meta`, `_prepare_freeze_seed_scope`, `_load_previous_schedule_for_freeze`, `_apply_freeze_prefixes`, `_finish_freeze_seed_result`, `_empty_freeze_seed_result`, `int`, `bool`

## core/services/scheduler/run/schedule_persistence.py（Service 层）

### `ValidatedSchedulePayload.to_repo_rows()` [公开]
- 位置：第 30-44 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`rows.append`, `int`, `svc._format_dt`

### `_normalized_status_text()` [私有]
- 位置：第 47-49 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_iter_actionable_results()` [私有]
- 位置：第 52-78 行
- 参数：results
- 返回类型：Subscript(value=Name(id='Iterator', ctx=Load()), slice=Subsc

### `count_actionable_schedule_rows()` [公开]
- 位置：第 81-82 行
- 参数：results
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`sum`, `_iter_actionable_results`

### `has_actionable_schedule_rows()` [公开]
- 位置：第 85-86 行
- 参数：results
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`count_actionable_schedule_rows`

### `_raise_no_actionable_schedule_error()` [私有]
- 位置：第 89-95 行
- 参数：validation_errors
- 返回类型：Constant(value=None)

### `_raise_invalid_schedule_rows_error()` [私有]
- 位置：第 98-104 行
- 参数：validation_errors
- 返回类型：Constant(value=None)

### `_raise_out_of_scope_schedule_rows_error()` [私有]
- 位置：第 107-115 行
- 参数：out_of_scope_op_ids
- 返回类型：Constant(value=None)

### `_raise_duplicate_schedule_rows_error()` [私有]
- 位置：第 118-125 行
- 参数：duplicate_op_ids
- 返回类型：Constant(value=None)

### `_result_identity()` [私有]
- 位置：第 128-140 行
- 参数：result
- 返回类型：Name(id='str', ctx=Load())

### `_build_validated_schedule_row()` [私有]
- 位置：第 143-184 行
- 参数：result
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `build_validated_schedule_payload()` [公开]
- 位置：第 187-238 行
- 参数：results
- 返回类型：Name(id='ValidatedSchedulePayload', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_orchestrator.py:247` [Service] `validated_schedule_payload = build_validated_schedule_payload(`
- **被调用者**（16 个）：`set`, `enumerate`, `ValidatedSchedulePayload`, `list`, `_build_validated_schedule_row`, `cast`, `schedule_rows.append`, `scheduled_op_ids.add`, `_raise_out_of_scope_schedule_rows_error`, `_raise_duplicate_schedule_rows_error`, `_raise_invalid_schedule_rows_error`, `_raise_no_actionable_schedule_error`, `out_of_scope_op_ids.append`, `validation_errors.append`, `int`

### `_maybe_persist_auto_assign_resources()` [私有]
- 位置：第 241-261 行
- 参数：svc
- 返回类型：Constant(value=None)

### `_persist_operation_statuses()` [私有]
- 位置：第 264-292 行
- 参数：svc
- 返回类型：Constant(value=None)

### `_persist_batch_statuses()` [私有]
- 位置：第 295-317 行
- 参数：svc
- 返回类型：Constant(value=None)

### `_persist_schedule_history()` [私有]
- 位置：第 320-341 行
- 参数：svc
- 返回类型：Constant(value=None)

### `_log_schedule_operation()` [私有]
- 位置：第 344-383 行
- 参数：svc
- 返回类型：Constant(value=None)

### `persist_schedule()` [公开]
- 位置：第 386-466 行
- 参数：svc
- 返回类型：Constant(value=None)
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:273` [Service] `persist_schedule(`
- **被调用者**（14 个）：`validated_schedule_payload.to_repo_rows`, `_log_schedule_operation`, `_raise_no_actionable_schedule_error`, `transaction`, `_persist_schedule_history`, `int`, `bulk_create`, `set`, `dict`, `_persist_operation_statuses`, `_persist_batch_statuses`, `lower`, `strip`, `str`

## core/services/scheduler/summary/schedule_summary_assembly.py（Service 层）

### `_config_snapshot_dict()` [私有]
- 位置：第 27-32 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_comparison_metric()` [私有]
- 位置：第 35-36 行
- 参数：objective_name
- 返回类型：Name(id='str', ctx=Load())

### `_best_score_schema()` [私有]
- 位置：第 39-40 行
- 参数：objective_name
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `_finish_time_by_batch()` [私有]
- 位置：第 43-55 行
- 参数：results
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_record_invalid_due()` [私有]
- 位置：第 58-68 行
- 参数：无
- 返回类型：Constant(value=None)

### `_build_overdue_items()` [私有]
- 位置：第 71-128 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_algo_downtime_dict()` [私有]
- 位置：第 131-145 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_algo_input_contract_dict()` [私有]
- 位置：第 148-154 行
- 参数：input_state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_algo_freeze_window_dict()` [私有]
- 位置：第 157-188 行
- 参数：state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_algo_resource_pool_dict()` [私有]
- 位置：第 191-203 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_algo_warning_pipeline_dict()` [私有]
- 位置：第 206-221 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_algo_dict()` [私有]
- 位置：第 224-268 行
- 参数：state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_build_result_summary_obj()` [私有]
- 位置：第 271-323 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

## core/shared/degradation.py（Other 层）

### `DegradationCollector.__init__()` [私有]
- 位置：第 50-54 行
- 参数：events
- 返回类型：无注解

### `DegradationCollector.__bool__()` [私有]
- 位置：第 56-57 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `DegradationCollector.__len__()` [私有]
- 位置：第 59-60 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())

### `DegradationCollector.add()` [公开]
- 位置：第 62-116 行
- 参数：event
- 返回类型：Name(id='DegradationEvent', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/gantt_service.py:282` [Service] `degradation_collector.add(`
- **被调用者**（8 个）：`get`, `DegradationEvent`, `len`, `append`, `ValueError`, `str`, `max`, `int`

### `DegradationCollector.extend()` [公开]
- 位置：第 118-124 行
- 参数：events
- 返回类型：Constant(value=None)
- **调用者**（56 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:42` [Route] `normalized.extend(str(item).strip() for item in (hidden_warnings or []) if str(i`
  - `web/bootstrap/plugins.py:44` [Bootstrap] `merged.extend(collector.to_list())`
  - `web/bootstrap/launcher_contracts.py:410` [Bootstrap] `paths.extend(`
  - `web/viewmodels/page_manuals_common.py:205` [ViewModel] `lines.extend([f"### {section['title']}", "", section["body_md"], ""])`
  - `web/viewmodels/page_manuals_common.py:207` [ViewModel] `lines.extend(["## 相关模块说明", ""])`
  - `web/viewmodels/page_manuals_common.py:209` [ViewModel] `lines.extend([f"### {item['title']}", "", item.get("summary") or "", ""])`
  - `web/viewmodels/page_manuals_common.py:211` [ViewModel] `lines.extend([f"#### {section['title']}", "", section["body_md"], ""])`
  - `core/services/scheduler/resource_dispatch_rows.py:249` [Service] `collector.extend(item.events)`
  - `core/services/scheduler/resource_dispatch_rows.py:339` [Service] `collector.extend(parsed.events)`
  - `core/services/scheduler/resource_dispatch_rows.py:450` [Service] `collector.extend(parsed.events)`
  - `core/services/scheduler/resource_dispatch_support.py:194` [Service] `collector.extend(normalized.events)`
  - `core/services/scheduler/resource_dispatch_support.py:247` [Service] `collector.extend(detail_rows_outcome.events)`
  - `core/services/scheduler/resource_dispatch_support.py:248` [Service] `collector.extend(tasks_outcome.events)`
  - `core/services/scheduler/resource_dispatch_support.py:249` [Service] `collector.extend(calendar_outcome.events)`
  - `core/services/scheduler/resource_dispatch_support.py:351` [Service] `summary_collector.extend(prepared_rows.events)`
  - `core/services/scheduler/resource_dispatch_support.py:352` [Service] `summary_collector.extend(operator_scope.events)`
  - `core/services/scheduler/resource_dispatch_support.py:353` [Service] `summary_collector.extend(machine_scope.events)`
  - `core/services/scheduler/resource_dispatch_support.py:354` [Service] `summary_collector.extend(cross_team_rows.events)`
  - `core/services/scheduler/resource_dispatch_support.py:404` [Service] `summary_collector.extend(prepared_rows.events)`
  - `core/services/scheduler/resource_dispatch_support.py:405` [Service] `summary_collector.extend(scope_result.events)`
  - `core/services/scheduler/gantt_tasks.py:254` [Service] `collector.extend(outcome.events)`
  - `core/services/scheduler/gantt_service.py:275` [Service] `degradation_collector.extend(calendar_days_outcome.events)`
  - `core/services/scheduler/gantt_service.py:276` [Service] `degradation_collector.extend(tasks_outcome.events)`
  - `core/services/scheduler/config/config_page_save_service.py:128` [Service] `plan.updates.extend(`
  - `core/services/scheduler/config/config_page_save_service.py:145` [Service] `plan.updates.extend(`
  - `core/services/scheduler/config/config_page_save_service.py:194` [Service] `plan.updates.extend(`
  - `core/services/scheduler/config/config_page_save_service.py:264` [Service] `keys.extend([ACTIVE_PRESET_KEY, ACTIVE_PRESET_REASON_KEY, ACTIVE_PRESET_META_KEY`
  - `core/services/scheduler/config/config_write_service.py:44` [Service] `rows.extend(self._mark_custom_updates())`
  - `core/services/scheduler/config/config_write_service.py:50` [Service] `updates.extend(self.active_service.active_preset_updates(BUILTIN_PRESET_DEFAULT)`
  - `core/services/scheduler/run/schedule_orchestrator.py:209` [Service] `summary_warnings.extend(algo_warnings)`
  - `core/services/scheduler/run/schedule_input_builder.py:131` [Service] `merge_event_collector.extend(lookup.events)`
  - `core/services/scheduler/run/schedule_input_builder.py:132` [Service] `collector.extend(lookup.events)`
  - `core/services/scheduler/run/schedule_input_builder.py:150` [Service] `collector.extend(merge_event_collector.to_list()[merge_event_count_before:])`
  - `core/services/scheduler/run/schedule_input_collector.py:123` [Service] `operations.extend(list(svc.op_repo.list_by_batch(batch_id) or []))`
  - `core/services/scheduler/run/schedule_input_runtime_support.py:74` [Service] `algo_warnings.extend(list(pool_warnings or []))`
  - `core/services/process/route_parser.py:240` [Service] `errors.extend(_strict_supplier_issue_messages(issue_messages, op_type_name=op_ty`
  - `core/services/process/route_parser.py:245` [Service] `warnings.extend([msg for msg in issue_messages if msg])`
  - `core/services/process/unit_excel/parser.py:158` [Service] `operator_names.extend(self._extract_names(ln))`
  - `core/services/process/unit_excel/parser.py:165` [Service] `operator_names.extend(self._extract_names(" ".join(tokens[1:])))`
  - `data/repositories/part_operation_repo.py:147` [Repository] `params.extend([part_no, int(seq)])`
  - `data/repositories/schedule_repo.py:109` [Repository] `out.extend(self.fetchall(sql, tuple(params)))`
  - `data/repositories/schedule_repo.py:226` [Repository] `params.extend([scope_id, scope_id])`
  - `core/algorithms/greedy/algo_stats.py:120` [Algorithm] `existing_list.extend(deepcopy(value))`
  - `core/algorithms/greedy/seed.py:56` [Algorithm] `warnings.extend(_seed_warnings(counters, dup_samples))`
  - `core/algorithms/greedy/scheduler.py:131` [Algorithm] `warnings.extend(params.warnings)`
  - `core/algorithms/greedy/scheduler.py:257` [Algorithm] `override_order.extend([batch.batch_id for batch in sorted_batches if batch.batch`
  - `core/algorithms/greedy/scheduler.py:265` [Algorithm] `warnings.extend(seed_warnings)`
  - `core/algorithms/greedy/scheduler.py:303` [Algorithm] `warnings.extend(state.seed_resource_warnings())`
  - `tools/test_debt_registry.py:322` [Tool] `blockers.extend(["xfail_signal"] * (require_importable and bool(_xfail_signal_no`
  - `tools/collect_full_test_debt.py:399` [Tool] `blockers.extend(["xfail_signal"] * bool(_xfail_signal_nodeids(payload)))`
  - `tools/check_full_test_debt.py:298` [Tool] `errors.extend(_classification_errors(payload))`
  - `tools/check_full_test_debt.py:299` [Tool] `errors.extend(_validate_no_unregistered_xfails(reports, active_entries=active_en`
  - `tools/check_full_test_debt.py:300` [Tool] `errors.extend(`
  - `tools/check_full_test_debt.py:310` [Tool] `errors.extend(`
  - `tools/quality_gate_scan.py:543` [Tool] `assignments_by_scope[scope].extend(_collect_name_bindings([node]))`
  - `tools/quality_gate_scan.py:545` [Tool] `assignments_by_scope[scope].extend(_collect_name_bindings([node]))`
- **被调用者**（3 个）：`isinstance`, `events.to_list`, `self.add`

### `DegradationCollector.to_list()` [公开]
- 位置：第 126-127 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（22 处）：
  - `web/bootstrap/plugins.py:44` [Bootstrap] `merged.extend(collector.to_list())`
  - `web/bootstrap/plugins.py:46` [Bootstrap] `base["degradation_events"] = public_degradation_events(merged.to_list())`
  - `core/services/scheduler/resource_dispatch_support.py:155` [Service] `"degradation_events": public_degradation_events(collector.to_list()),`
  - `core/services/scheduler/gantt_service.py:301` [Service] `degradation_events=degradation_events_to_dicts(degradation_collector.to_list()),`
  - `core/services/scheduler/config/config_validator.py:239` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/config/config_snapshot.py:264` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/config/config_snapshot.py:406` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/run/schedule_input_builder.py:150` [Service] `collector.extend(merge_event_collector.to_list()[merge_event_count_before:])`
  - `core/services/scheduler/run/schedule_input_builder.py:177` [Service] `merge_context_events=degradation_events_to_dicts(merge_event_collector.to_list()`
  - `core/services/scheduler/run/schedule_template_lookup.py:150` [Service] `return TemplateGroupLookupOutcome(None, None, True, collector.to_list())`
  - `core/services/scheduler/run/schedule_template_lookup.py:184` [Service] `return TemplateGroupLookupOutcome(None, None, True, collector.to_list())`
  - `core/services/scheduler/run/schedule_template_lookup.py:219` [Service] `return TemplateGroupLookupOutcome(tmpl, None, True, collector.to_list())`
  - `core/services/scheduler/run/schedule_template_lookup.py:243` [Service] `return TemplateGroupLookupOutcome(tmpl, None, True, collector.to_list())`
  - `core/services/scheduler/run/schedule_template_lookup.py:269` [Service] `return TemplateGroupLookupOutcome(tmpl, None, False, collector.to_list())`
  - `core/services/scheduler/run/schedule_template_lookup.py:313` [Service] `return TemplateGroupLookupOutcome(tmpl, None, False, collector.to_list())`
  - `core/services/scheduler/run/schedule_template_lookup.py:337` [Service] `return TemplateGroupLookupOutcome(tmpl, grp, False, collector.to_list())`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:363` [Service] `return {"events": degradation_events_to_dicts(collector.to_list()), "counters": `
  - `core/services/common/build_outcome.py:33` [Service] `self.events = collector.to_list()`
  - `core/services/common/build_outcome.py:62` [Service] `events=collector.to_list() if collector is not None else [],`
  - `core/services/process/unit_excel/template_builder.py:72` [Service] `"events": degradation_events_to_dicts(collector.to_list()),`
  - `core/models/schedule_config_runtime_coercion.py:366` [Model] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/algorithms/greedy/schedule_params.py:168` [Algorithm] `for event in collector.to_list():`
- **被调用者**（1 个）：`list`

### `DegradationCollector.to_counters()` [公开]
- 位置：第 129-133 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（19 处）：
  - `web/bootstrap/plugins.py:47` [Bootstrap] `base["degradation_counters"] = merged.to_counters()`
  - `web/bootstrap/plugins.py:224` [Bootstrap] `if int(collector.to_counters().get("plugin_bootstrap_config_reader_failed") or 0`
  - `core/services/scheduler/resource_dispatch_rows.py:151` [Service] `if not prepared_rows and collector.to_counters().get("bad_time_row_skipped", 0) `
  - `core/services/scheduler/resource_dispatch_rows.py:254` [Service] `if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/resource_dispatch_rows.py:348` [Service] `if not tasks and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/resource_dispatch_rows.py:477` [Service] `if not out_rows and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/resource_dispatch_support.py:156` [Service] `"degradation_counters": collector.to_counters(),`
  - `core/services/scheduler/resource_dispatch_support.py:213` [Service] `if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/gantt_tasks.py:261` [Service] `if not tasks and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/gantt_service.py:302` [Service] `degradation_counters=degradation_collector.to_counters(),`
  - `core/services/scheduler/gantt_week_plan.py:82` [Service] `if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/config/config_validator.py:240` [Service] `degradation_counters=collector.to_counters(),`
  - `core/services/scheduler/config/config_snapshot.py:267` [Service] `collector.to_counters(),`
  - `core/services/scheduler/config/config_snapshot.py:407` [Service] `degradation_counters=collector.to_counters(),`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:363` [Service] `return {"events": degradation_events_to_dicts(collector.to_list()), "counters": `
  - `core/services/common/build_outcome.py:35` [Service] `merged_counters = collector.to_counters()`
  - `core/services/process/unit_excel/template_builder.py:73` [Service] `"counters": collector.to_counters(),`
  - `core/models/schedule_config_runtime_coercion.py:369` [Model] `collector.to_counters(),`
  - `core/algorithms/greedy/external_groups.py:29` [Algorithm] `counters = collector.to_counters()`
- **被调用者**（2 个）：`counters.get`, `int`

### `degradation_event_to_dict()` [公开]
- 位置：第 136-144 行
- 参数：event
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`str`, `int`

### `degradation_events_to_dicts()` [公开]
- 位置：第 147-148 行
- 参数：events
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript
- **调用者**（11 处）：
  - `core/services/scheduler/gantt_service.py:81` [Service] `degradation_events=degradation_events_to_dicts(calendar_days_outcome.events),`
  - `core/services/scheduler/gantt_service.py:301` [Service] `degradation_events=degradation_events_to_dicts(degradation_collector.to_list()),`
  - `core/services/scheduler/gantt_service.py:360` [Service] `"degradation_events": degradation_events_to_dicts(outcome.events),`
  - `core/services/scheduler/config/config_validator.py:239` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/config/config_snapshot.py:264` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/config/config_snapshot.py:406` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/run/schedule_input_builder.py:177` [Service] `merge_context_events=degradation_events_to_dicts(merge_event_collector.to_list()`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:97` [Service] `event_dicts = degradation_events_to_dicts(input_build_outcome.events)`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:363` [Service] `return {"events": degradation_events_to_dicts(collector.to_list()), "counters": `
  - `core/services/process/unit_excel/template_builder.py:72` [Service] `"events": degradation_events_to_dicts(collector.to_list()),`
  - `core/models/schedule_config_runtime_coercion.py:366` [Model] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
- **被调用者**（1 个）：`degradation_event_to_dict`

## tools/quality_gate_shared.py（Tool 层）

### `now_shanghai_iso()` [公开]
- 位置：第 269-270 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（10 处）：
  - `scripts/sync_debt_ledger.py:147` [Script] `"checked_at": now_shanghai_iso(),`
  - `scripts/sync_debt_ledger.py:257` [Script] `last_verified_at=now_shanghai_iso(),`
  - `scripts/sync_debt_ledger.py:269` [Script] `fixed_at=now_shanghai_iso(),`
  - `tools/quality_gate_entries.py:35` [Tool] `"last_verified_at": now_shanghai_iso(),`
  - `tools/quality_gate_entries.py:54` [Tool] `merged["last_verified_at"] = now_shanghai_iso()`
  - `tools/quality_gate_entries.py:64` [Tool] `merged["last_verified_at"] = now_shanghai_iso()`
  - `tools/test_debt_registry.py:429` [Tool] `verified_at = last_verified_at or now_shanghai_iso()`
  - `tools/quality_gate_ledger.py:40` [Tool] `"updated_at": now_shanghai_iso(),`
  - `tools/quality_gate_ledger.py:588` [Tool] `"updated_at": ledger.get("updated_at") or now_shanghai_iso(),`
  - `tools/quality_gate_ledger.py:622` [Tool] `next_ledger["updated_at"] = now_shanghai_iso()`
- **被调用者**（3 个）：`isoformat`, `replace`, `datetime.now`

### `repo_rel()` [公开]
- 位置：第 273-274 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`replace`, `relpath`

### `repo_abs()` [公开]
- 位置：第 277-278 行
- 参数：rel_path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`join`, `replace`, `str`

### `read_text_file()` [公开]
- 位置：第 281-283 行
- 参数：rel_path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（11 处）：
  - `tools/quality_gate_operations.py:63` [Tool] `current_value = len(read_text_file(path).splitlines())`
  - `tools/quality_gate_operations.py:226` [Tool] `current_value = len(read_text_file(path).splitlines())`
  - `tools/quality_gate_operations.py:348` [Tool] `current_value = len(read_text_file(str(entry.get("path"))).splitlines())`
  - `tools/quality_gate_ledger.py:54` [Tool] `text = read_text_file("开发文档/技术债务治理台账.md")`
  - `tools/quality_gate_ledger.py:86` [Tool] `text = read_text_file("开发文档/技术债务治理台账.md")`
  - `tools/quality_gate_ledger.py:176` [Tool] `text = read_text_file("开发文档/阶段留痕与验收记录.md")`
  - `tools/quality_gate_scan.py:34` [Tool] `source = read_text_file(rel_path)`
  - `tools/quality_gate_scan.py:573` [Tool] `source_lines = read_text_file(rel_path).splitlines()`
  - `tools/quality_gate_scan.py:698` [Tool] `source_lines = read_text_file(rel_path).splitlines()`
  - `tools/quality_gate_scan.py:745` [Tool] `source = read_text_file(rel_path)`
  - `tools/quality_gate_scan.py:776` [Tool] `line_count = len(read_text_file(rel_path).splitlines())`
- **被调用者**（3 个）：`open`, `f.read`, `repo_abs`

### `write_text_file()` [公开]
- 位置：第 286-292 行
- 参数：rel_path, content
- 返回类型：Constant(value=None)
- **调用者**（1 处）：
  - `tools/quality_gate_ledger.py:170` [Tool] `write_text_file("开发文档/技术债务治理台账.md", render_ledger_markdown(sorted_ledger))`
- **被调用者**（5 个）：`repo_abs`, `dirname`, `os.makedirs`, `open`, `f.write`

### `slugify()` [公开]
- 位置：第 295-304 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（11 处）：
  - `tools/quality_gate_entries.py:71` [Tool] `"id": f"oversize:{slugify(path)}",`
  - `tools/quality_gate_entries.py:86` [Tool] `"id": f"complexity:{slugify(path)}-{slugify(symbol)}",`
  - `tools/quality_gate_operations.py:64` [Tool] `existing = find_existing_by_id(oversize_existing, f"oversize:{slugify(path)}")`
  - `tools/quality_gate_operations.py:77` [Tool] `"complexity:{}-{}".format(slugify(item["path"]), slugify(item["symbol"])),`
  - `tools/quality_gate_operations.py:138` [Tool] `existing = find_existing_by_id(oversize_existing, "oversize:{}".format(slugify(i`
  - `tools/quality_gate_operations.py:147` [Tool] `"complexity:{}-{}".format(slugify(item["path"]), slugify(item["symbol"])),`
  - `tools/quality_gate_scan.py:138` [Tool] `return slugify(slice_node.value)`
  - `tools/quality_gate_scan.py:142` [Tool] `return slugify(inner.value)`
  - `tools/quality_gate_scan.py:150` [Tool] `return f"attr:{slugify(target.attr)}"`
  - `tools/quality_gate_scan.py:371` [Tool] `slugify(entry.get("path")),`
  - `tools/quality_gate_scan.py:372` [Tool] `slugify(entry.get("symbol") or "module"),`
- **被调用者**（6 个）：`strip`, `text.replace`, `text.endswith`, `re.sub`, `lower`, `str`

### `collect_py_files()` [公开]
- 位置：第 307-320 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`sorted`, `repo_abs`, `os.walk`, `set`, `isdir`, `files.append`, `name.endswith`, `name.startswith`, `repo_rel`, `join`

### `collect_globbed_files()` [公开]
- 位置：第 323-330 行
- 参数：patterns
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（4 处）：
  - `tools/quality_gate_operations.py:425` [Tool] `entries = scan_request_service_direct_assembly_entries(collect_globbed_files(REQ`
  - `tools/quality_gate_operations.py:441` [Tool] `return scan_repository_bundle_drift_entries(collect_globbed_files(REPOSITORY_BUN`
  - `tools/quality_gate_scan.py:569` [Tool] `paths = collect_globbed_files(REQUEST_SERVICE_SCAN_SCOPE_PATTERNS)`
  - `tools/quality_gate_scan.py:694` [Tool] `paths = collect_globbed_files(REPOSITORY_BUNDLE_DRIFT_SCOPE_PATTERNS)`
- **被调用者**（8 个）：`sorted`, `join`, `glob.glob`, `set`, `pattern.replace`, `isfile`, `files.append`, `repo_rel`

### `collect_startup_scope_files()` [公开]
- 位置：第 333-334 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（2 处）：
  - `tools/quality_gate_operations.py:130` [Tool] `startup_files = collect_startup_scope_files()`
  - `tools/quality_gate_scan.py:384` [Tool] `entries = scan_silent_fallback_entries(collect_startup_scope_files())`
- **被调用者**（1 个）：`collect_globbed_files`

### `_stable_json_hash()` [私有]
- 位置：第 337-339 行
- 参数：payload
- 返回类型：Name(id='str', ctx=Load())

### `_sha256_text()` [私有]
- 位置：第 342-343 行
- 参数：text
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_command_rows()` [私有]
- 位置：第 346-361 行
- 参数：commands
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `_normalize_source_rows()` [私有]
- 位置：第 364-375 行
- 参数：gate_sources
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `_normalize_required_tests()` [私有]
- 位置：第 378-379 行
- 参数：required_tests
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_normalize_collection_proof()` [私有]
- 位置：第 382-404 行
- 参数：collection_proof
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_normalize_command_receipt_payload()` [私有]
- 位置：第 407-420 行
- 参数：payload
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_normalize_command_receipt_index()` [私有]
- 位置：第 423-432 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `parse_pytest_collect_nodeids()` [公开]
- 位置：第 435-449 行
- 参数：output
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:525` [Script] `return parse_pytest_collect_nodeids(output)`
- **被调用者**（9 个）：`set`, `splitlines`, `raw_line.strip`, `seen.add`, `nodeids.append`, `str`, `line.startswith`, `line.split`, `token.startswith`

### `collect_current_pytest_nodeids()` [公开]
- 位置：第 452-466 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Tuple(el
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`subprocess.run`, `str`, `int`, `parse_pytest_collect_nodeids`, `os.fspath`

### `_resolve_quality_gate_command_args()` [私有]
- 位置：第 469-474 行
- 参数：command
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_command_output_policy()` [私有]
- 位置：第 477-479 行
- 参数：command
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_command_output_for_policy()` [私有]
- 位置：第 482-498 行
- 参数：text
- 返回类型：Name(id='str', ctx=Load())

### `_hash_command_output()` [私有]
- 位置：第 501-502 行
- 参数：text
- 返回类型：Name(id='str', ctx=Load())

### `replay_quality_gate_command_plan()` [公开]
- 位置：第 505-540 行
- 参数：repo_root, commands
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`enumerate`, `_normalize_command_rows`, `strip`, `subprocess.run`, `_resolve_quality_gate_command_args`, `int`, `build_quality_gate_receipt_rel_path`, `join`, `_normalize_command_receipt_payload`, `_command_output_policy`, `str`, `os.fspath`, `receipt_rel.replace`, `isfile`, `json.loads`

### `iter_quality_gate_required_tests()` [公开]
- 位置：第 543-544 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（2 处）：
  - `scripts/run_quality_gate.py:38` [Script] `REQUIRED_TEST_ARGS = list(iter_quality_gate_required_tests())`
  - `tools/collect_full_test_debt.py:464` [Tool] `required_paths = iter_quality_gate_required_tests()`
- **被调用者**（1 个）：`_registry_required_tests`

### `quality_gate_required_test_nodeid_matches()` [公开]
- 位置：第 547-551 行
- 参数：nodeid, required_tests
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（3 处）：
  - `tools/collect_full_test_debt.py:203` [Tool] `return quality_gate_required_test_nodeid_matches(nodeid, tuple(required_paths))`
  - `tools/quality_gate_ledger.py:395` [Tool] `if quality_gate_required_test_nodeid_matches(nodeid):`
  - `tools/check_full_test_debt.py:210` [Tool] `if quality_gate_required_test_nodeid_matches(nodeid):`
- **被调用者**（1 个）：`_registry_required_test_nodeid_matches`

### `iter_non_regression_guard_tests()` [公开]
- 位置：第 554-555 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`_registry_non_regression_guard_tests`

### `build_quality_gate_command_plan()` [公开]
- 位置：第 558-640 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:623` [Script] `command_plan = build_quality_gate_command_plan()`
- **被调用者**（4 个）：`iter_quality_gate_required_tests`, `_registry_startup_regressions`, `join`, `list`

### `build_quality_gate_receipt_rel_path()` [公开]
- 位置：第 643-647 行
- 参数：index, display
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:127` [Script] `receipt_rel = build_quality_gate_receipt_rel_path(index, str(command.get("displa`
- **被调用者**（9 个）：`replace`, `slugify`, `rstrip`, `hexdigest`, `join`, `int`, `hashlib.sha256`, `encode`, `str`

### `build_quality_gate_command_receipt()` [公开]
- 位置：第 650-675 行
- 参数：command
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:130` [Script] `receipt_payload = build_quality_gate_command_receipt(`
- **被调用者**（10 个）：`_command_output_policy`, `_normalize_command_receipt_payload`, `_normalize_command_rows`, `strip`, `int`, `_stable_json_hash`, `list`, `bool`, `_hash_command_output`, `str`

### `build_quality_gate_collection_proof()` [公开]
- 位置：第 678-698 行
- 参数：default_collect_nodeids
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:529` [Script] `return build_quality_gate_collection_proof(default_collect_nodeids, required_tes`
- **被调用者**（9 个）：`_normalize_required_tests`, `_normalize_collection_proof`, `strip`, `any`, `key_test_rows.append`, `list`, `iter_quality_gate_required_tests`, `str`, `nodeid.startswith`

### `_sha256_file()` [私有]
- 位置：第 701-709 行
- 参数：abs_path
- 返回类型：Name(id='str', ctx=Load())

### `build_quality_gate_source_proof()` [公开]
- 位置：第 712-725 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`abspath`, `_normalize_source_rows`, `join`, `isfile`, `rows.append`, `os.fspath`, `rel_path.replace`, `replace`, `bool`, `_sha256_file`, `str`

### `hash_required_tests_registry()` [公开]
- 位置：第 728-729 行
- 参数：required_tests
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`_registry_required_tests_hash`

### `hash_quality_gate_commands()` [公开]
- 位置：第 732-733 行
- 参数：commands
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_command_rows`

### `hash_quality_gate_collection_proof()` [公开]
- 位置：第 736-737 行
- 参数：collection_proof
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_collection_proof`

### `hash_quality_gate_source_proof()` [公开]
- 位置：第 740-741 行
- 参数：gate_sources
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_source_rows`

### `hash_quality_gate_command_receipts()` [公开]
- 位置：第 744-745 行
- 参数：command_receipts
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_command_receipt_index`

### `apply_quality_gate_manifest_proof_fields()` [公开]
- 位置：第 748-774 行
- 参数：manifest
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（3 处）：
  - `scripts/run_quality_gate.py:601` [Script] `apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)`
  - `scripts/run_quality_gate.py:708` [Script] `apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)`
  - `scripts/run_quality_gate.py:740` [Script] `apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)`
- **被调用者**（14 个）：`dict`, `_normalize_required_tests`, `hash_required_tests_registry`, `_normalize_command_rows`, `hash_quality_gate_commands`, `_normalize_collection_proof`, `hash_quality_gate_collection_proof`, `_normalize_command_receipt_index`, `hash_quality_gate_command_receipts`, `_normalize_source_rows`, `hash_quality_gate_source_proof`, `manifest.get`, `iter_quality_gate_required_tests`, `build_quality_gate_source_proof`

### `_git_rev_parse_path()` [私有]
- 位置：第 777-792 行
- 参数：repo_root
- 返回类型：Name(id='str', ctx=Load())

### `repo_identity()` [公开]
- 位置：第 795-800 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`abspath`, `_git_rev_parse_path`, `os.fspath`, `join`

### `_verify_quality_gate_collection_proof()` [私有]
- 位置：第 803-818 行
- 参数：manifest
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_load_verified_quality_gate_receipt()` [私有]
- 位置：第 821-842 行
- 参数：repo_root, receipt_entry, command
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Tuple(el

### `_verify_receipt_header()` [私有]
- 位置：第 845-860 行
- 参数：receipt, normalized_command
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_receipt_command_fields()` [私有]
- 位置：第 863-873 行
- 参数：receipt, command, normalized_command
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_receipt_output_hashes()` [私有]
- 位置：第 876-894 行
- 参数：receipt, normalized_command
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_quality_gate_receipt_payload()` [私有]
- 位置：第 897-921 行
- 参数：receipt_payload, command
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_quality_gate_command_receipts()` [私有]
- 位置：第 924-958 行
- 参数：repo_root, manifest
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_manifest_header()` [私有]
- 位置：第 961-982 行
- 参数：repo_root, manifest, head_sha
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Tuple(el

### `_verify_manifest_git_status()` [私有]
- 位置：第 985-995 行
- 参数：manifest, git_status_lines
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_manifest_clean_finish()` [私有]
- 位置：第 998-1009 行
- 参数：manifest, manifest_git_status_after, current_git_status
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_manifest_static_proof()` [私有]
- 位置：第 1012-1029 行
- 参数：manifest
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Tuple(el

### `_verify_manifest_collection_and_receipts()` [私有]
- 位置：第 1032-1064 行
- 参数：repo_root, manifest
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_manifest_gate_sources()` [私有]
- 位置：第 1067-1076 行
- 参数：repo_root, manifest
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_manifest_replay()` [私有]
- 位置：第 1079-1096 行
- 参数：repo_root, expected_commands
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `verify_quality_gate_manifest()` [公开]
- 位置：第 1099-1134 行
- 参数：无
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Tuple(el
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`_verify_manifest_header`, `_verify_manifest_git_status`, `_verify_manifest_static_proof`, `_verify_manifest_collection_and_receipts`, `_verify_manifest_gate_sources`, `_verify_manifest_replay`, `isinstance`

### `git_status_short_lines()` [公开]
- 位置：第 1137-1148 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`subprocess.run`, `rstrip`, `str`, `splitlines`, `strip`

### `collect_quality_rule_files()` [公开]
- 位置：第 1151-1152 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（3 处）：
  - `tools/quality_gate_operations.py:399` [Tool] `for entry in scan_silent_fallback_entries(collect_quality_rule_files()):`
  - `tools/quality_gate_operations.py:412` [Tool] `return {str(entry.get("path")): entry for entry in scan_oversize_entries(collect`
  - `tools/quality_gate_operations.py:416` [Tool] `return complexity_scan_map(collect_quality_rule_files())`
- **被调用者**（4 个）：`sorted`, `set`, `collect_py_files`, `collect_startup_scope_files`

### `is_startup_scope_path()` [公开]
- 位置：第 1155-1157 行
- 参数：path
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `tools/quality_gate_operations.py:168` [Tool] `"entries": remove_entries_by_predicate(silent_existing, lambda entry: is_startup`
  - `tools/quality_gate_operations.py:400` [Tool] `if is_startup_scope_path(str(entry.get("path"))):`
- **被调用者**（3 个）：`replace`, `rel_path.startswith`, `str`

### `ensure_single_marker()` [公开]
- 位置：第 1160-1163 行
- 参数：text, marker, label
- 返回类型：Constant(value=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`text.count`, `QualityGateError`

### `extract_marked_block()` [公开]
- 位置：第 1166-1173 行
- 参数：text, begin_marker, end_marker, label
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`ensure_single_marker`, `text.index`, `strip`, `len`, `QualityGateError`

### `extract_json_code_block()` [公开]
- 位置：第 1176-1188 行
- 参数：text, begin_marker, end_marker, label
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（4 处）：
  - `tools/test_debt_registry.py:330` [Tool] `payload = extract_json_code_block(`
  - `tools/quality_gate_ledger.py:55` [Tool] `ledger = extract_json_code_block(text, LEDGER_BEGIN, LEDGER_END, "治理台账")`
  - `tools/quality_gate_ledger.py:87` [Tool] `ledger = extract_json_code_block(text, LEDGER_BEGIN, LEDGER_END, "治理台账")`
  - `tools/quality_gate_ledger.py:177` [Tool] `payload = extract_json_code_block(text, SP02_FACT_BEGIN, SP02_FACT_END, "SP02 事实`
- **被调用者**（7 个）：`extract_marked_block`, `re.search`, `strip`, `QualityGateError`, `json.loads`, `isinstance`, `match.group`

### `render_marked_json_block()` [公开]
- 位置：第 1191-1193 行
- 参数：begin_marker, end_marker, payload
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `tools/quality_gate_ledger.py:106` [Tool] `payload_block = render_marked_json_block(LEDGER_BEGIN, LEDGER_END, ledger)`
- **被调用者**（1 个）：`json.dumps`

## web/bootstrap/plugins.py（Bootstrap 层）

### `_status_degradation_collector()` [私有]
- 位置：第 16-38 行
- 参数：status
- 返回类型：Name(id='DegradationCollector', ctx=Load())

### `_merge_plugin_degradation()` [私有]
- 位置：第 41-48 行
- 参数：status, collector
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_ensure_plugin_status_shape()` [私有]
- 位置：第 51-64 行
- 参数：status
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_record_plugin_status_failures()` [私有]
- 位置：第 67-79 行
- 参数：status, collector
- 返回类型：Constant(value=None)

### `_resolve_enabled_source()` [私有]
- 位置：第 82-95 行
- 参数：plugin_id, row_source
- 返回类型：Name(id='str', ctx=Load())

### `_public_plugin_status_row()` [私有]
- 位置：第 98-103 行
- 参数：row, source
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_config_source_summary()` [私有]
- 位置：第 106-118 行
- 参数：sources, default_source
- 返回类型：Name(id='str', ctx=Load())

### `_apply_enabled_sources()` [私有]
- 位置：第 121-146 行
- 参数：status
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_build_plugin_config_reader()` [私有]
- 位置：第 149-195 行
- 参数：conn
- 返回类型：无注解

### `bootstrap_plugins()` [公开]
- 位置：第 198-286 行
- 参数：base_dir, database_path
- 返回类型：无注解
- **调用者**（1 处）：
  - `web/bootstrap/factory.py:281` [Bootstrap] `plugin_status = bootstrap_plugins(`
- **被调用者**（21 个）：`DegradationCollector`, `_build_plugin_config_reader`, `_apply_enabled_sources`, `_ensure_plugin_status_shape`, `_record_plugin_status_failures`, `_merge_plugin_degradation`, `get_connection`, `callable`, `getattr`, `isinstance`, `PluginManager.load_from_base_dir`, `collector.add`, `safe_log`, `int`, `reset_plugin_state`

---
- 分析函数/方法数：173
- 找到调用关系：303 处
- 跨层边界风险：0 项
