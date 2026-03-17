# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ normalize_text() 返回 Optional，但 web/routes/process_excel_op_types.py:60 的调用者未做 None 检查
- ⚠ normalize_text() 返回 Optional，但 core/services/equipment/machine_downtime_service.py:40 的调用者未做 None 检查
- ⚠ normalize_text() 返回 Optional，但 core/services/equipment/machine_service.py:31 的调用者未做 None 检查
- ⚠ normalize_text() 返回 Optional，但 core/services/personnel/operator_machine_normalizers.py:13 的调用者未做 None 检查
- ⚠ normalize_text() 返回 Optional，但 core/services/personnel/operator_service.py:29 的调用者未做 None 检查
- ⚠ normalize_text() 返回 Optional，但 core/services/personnel/resource_team_service.py:23 的调用者未做 None 检查
- ⚠ normalize_text() 返回 Optional，但 core/services/process/op_type_service.py:25 的调用者未做 None 检查
- ⚠ normalize_text() 返回 Optional，但 core/services/process/supplier_excel_import_service.py:86 的调用者未做 None 检查
- ⚠ normalize_text() 返回 Optional，但 core/services/scheduler/batch_service.py:43 的调用者未做 None 检查
- ⚠ normalize_text() 返回 Optional，但 core/services/scheduler/calendar_admin.py:58 的调用者未做 None 检查
- ⚠ normalize_text() 返回 Optional，但 core/services/scheduler/config_service.py:76 的调用者未做 None 检查
- ⚠ normalize_text() 返回 Optional，但 core/services/scheduler/schedule_service.py:73 的调用者未做 None 检查
- ⚠ normalize_operator_machine_text() 返回 Optional，但 core/services/personnel/operator_machine_service.py:35 的调用者未做 None 检查
- ⚠ normalize_skill_level_optional() 返回 Optional，但 core/services/personnel/operator_machine_service.py:39 的调用者未做 None 检查
- ⚠ normalize_yes_no_optional() 返回 Optional，但 core/services/personnel/operator_machine_service.py:43 的调用者未做 None 检查
- ⚠ CalendarAdmin.get_operator_calendar() 返回 Optional，但 core/services/scheduler/calendar_service.py:108 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## .windsurf/skills/aps-start-and-rerun-route/scripts/run_start_and_rerun_route.py（Other 层）

### `_find_repo_root()` [私有]
- 位置：第 16-35 行
- 参数：无
- 返回类型：Name(id='Path', ctx=Load())

### `_ensure_repo_on_path()` [私有]
- 位置：第 38-41 行
- 参数：repo_root
- 返回类型：Constant(value=None, kind=None)

### `_runtime_probe()` [私有]
- 位置：第 44-48 行
- 参数：repo_root
- 返回类型：无注解

### `_normalize_db_path()` [私有]
- 位置：第 51-55 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())

### `_resolve_target_db_path()` [私有]
- 位置：第 58-67 行
- 参数：repo_root, explicit_db_path
- 返回类型：Name(id='str', ctx=Load())

### `_assert_repo_runtime_matches_endpoint()` [私有]
- 位置：第 70-105 行
- 参数：runtime_probe_mod, repo_root, endpoint, target_db_path
- 返回类型：Constant(value=None, kind=None)

### `_start_server_if_needed()` [私有]
- 位置：第 108-165 行
- 参数：repo_root, host, port, wait_seconds, db_path
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_seed_and_schedule()` [私有]
- 位置：第 168-477 行
- 参数：repo_root, db_path, view
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_verify_route()` [私有]
- 位置：第 480-494 行
- 参数：host, port, view, week_start, version
- 返回类型：Name(id='int', ctx=Load())

### `_open_url()` [私有]
- 位置：第 497-509 行
- 参数：url
- 返回类型：Constant(value=None, kind=None)

### `main()` [公开]
- 位置：第 512-596 行
- 参数：argv
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（18 个）：`argparse.ArgumentParser`, `p.add_argument`, `p.parse_args`, `_find_repo_root`, `_resolve_target_db_path`, `_start_server_if_needed`, `str`, `int`, `rstrip`, `bool`, `_seed_and_schedule`, `_verify_route`, `print`, `endpoint.get`, `_open_url`

## app.py（Other 层）

### `_runtime_base_dir()` [私有]
- 位置：第 11-12 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `create_app()` [公开]
- 位置：第 15-21 行
- 参数：无
- 返回类型：Name(id='Flask', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`create_app_core`

## app_new_ui.py（Other 层）

### `_runtime_base_dir()` [私有]
- 位置：第 11-12 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `create_app()` [公开]
- 位置：第 15-22 行
- 参数：无
- 返回类型：Name(id='Flask', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`create_app_core`

## check_manual_layout.py（Other 层）

### `_has_manual_related_min_width()` [私有]
- 位置：第 41-46 行
- 参数：css_content
- 返回类型：Name(id='bool', ctx=Load())

### `_normalize_base_url()` [私有]
- 位置：第 49-51 行
- 参数：base_url
- 返回类型：Name(id='str', ctx=Load())

### `_resolve_base_url()` [私有]
- 位置：第 54-60 行
- 参数：explicit_base_url, runtime_dir
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_server_is_reachable()` [私有]
- 位置：第 63-64 行
- 参数：base_url
- 返回类型：Name(id='bool', ctx=Load())

### `_parse_args()` [私有]
- 位置：第 67-74 行
- 参数：argv
- 返回类型：无注解

### `check_layout_via_styles()` [公开]
- 位置：第 77-104 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`print`, `css_file.read_text`, `checks.items`, `css_file.exists`, `_has_manual_related_min_width`

### `check_layout_via_browser()` [公开]
- 位置：第 107-267 行
- 参数：base_url
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（22 个）：`_normalize_base_url`, `print`, `Options`, `options.add_argument`, `_server_is_reachable`, `webdriver.Chrome`, `driver.quit`, `driver.get`, `time.sleep`, `driver.add_cookie`, `driver.refresh`, `until`, `driver.find_element`, `driver.execute_script`, `results.append`

### `main()` [公开]
- 位置：第 270-322 行
- 参数：argv
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`_parse_args`, `_resolve_base_url`, `print`, `check_layout_via_styles`, `check_layout_via_browser`, `sys.exit`, `sum`, `len`, `mkdir`, `report_file.write_text`, `all`, `json.dumps`

## core/infrastructure/errors.py（Infrastructure 层）

### `AppError.__post_init__()` [私有]
- 位置：第 71-86 行
- 参数：无
- 返回类型：无注解

### `AppError.__str__()` [私有]
- 位置：第 88-89 行
- 参数：无
- 返回类型：无注解

### `AppError.to_dict()` [公开]
- 位置：第 91-101 行
- 参数：无
- 返回类型：Name(id='dict', ctx=Load())
- **调用者**（63 处）：
  - `web/routes/equipment_pages.py:216` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:229` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:27` [Route] `items = [m.to_dict() for m in svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:23` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:48` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:144` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:81` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:82` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:83` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:112` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:85` [Route] `supplier=s.to_dict(),`
  - `web/routes/scheduler_batches.py:41` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:64` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:113` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:186` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:230` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/scheduler_resource_dispatch.py:51` [Route] `for key, value in request.args.to_dict(flat=True).items():`
  - `web/routes/scheduler_resource_dispatch.py:188` [Route] `return redirect(url_for("scheduler.resource_dispatch_page", **request.args.to_di`
  - `web/routes/system_backup.py:38` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:35` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:42` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:52` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:145` [Route] `d = it.to_dict()`
  - `core/services/common/pandas_backend.py:64` [Service] `raw_rows = df.to_dict(orient="records")`
  - `core/services/equipment/machine_excel_import_service.py:106` [Service] `out = stats.to_dict()`
  - `core/services/material/material_service.py:82` [Service] `self.op_logger.info(module="material", action="create", target_type="material", `
  - `core/services/personnel/operator_excel_import_service.py:90` [Service] `out = stats.to_dict()`
  - `core/services/personnel/resource_team_service.py:74` [Service] `return [team.to_dict() for team in self.list(status=status)]`
  - `core/services/process/op_type_excel_import_service.py:79` [Service] `out = stats.to_dict()`
  - `core/services/process/part_operation_hours_excel_import_service.py:59` [Service] `return stats.to_dict(total_rows=len(preview_rows))`
  - `core/services/process/route_parser.py:57` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:77` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:78` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
  - `core/services/process/supplier_excel_import_service.py:114` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:102` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:258` [Service] `self.batch_repo.create(b.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:328` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:384` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:389` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config_presets.py:20` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:29` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:37` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:128` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config_presets.py:180` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/gantt_contract.py:70` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:164` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:206` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_optimizer.py:186` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:199` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:246` [Service] `cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(`
  - `core/services/scheduler/schedule_optimizer_steps.py:101` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:126` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:215` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:240` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_summary.py:46` [Service] `obj = to_dict()`
  - `core/services/scheduler/schedule_summary.py:423` [Service] `"metrics": best_metrics.to_dict() if best_metrics is not None else None,`

### `ValidationError.__init__()` [私有]
- 位置：第 105-107 行
- 参数：message, field
- 返回类型：无注解

### `NotFoundError.__init__()` [私有]
- 位置：第 111-116 行
- 参数：resource_type, resource_id
- 返回类型：无注解

### `success_response()` [公开]
- 位置：第 123-129 行
- 参数：data, meta
- 返回类型：Name(id='dict', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）

### `error_response()` [公开]
- 位置：第 132-136 行
- 参数：code, message, details
- 返回类型：Name(id='dict', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）

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
  - `web/routes/equipment_excel_machines.py:57` [Route] `return normalize_machine_status(value)`
  - `core/services/equipment/machine_excel_import_service.py:38` [Service] `return normalize_machine_status(value)`
- **被调用者**（2 个）：`_text`, `v.lower`

### `normalize_operator_status()` [公开]
- 位置：第 43-61 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（4 处）：
  - `web/routes/excel_demo.py:68` [Route] `st = normalize_operator_status(row.get("状态"))`
  - `web/routes/personnel_excel_operators.py:32` [Route] `st = normalize_operator_status(row.get("状态"))`
  - `web/routes/personnel_excel_operators.py:119` [Route] `item["状态"] = normalize_operator_status(item.get("状态"))`
  - `core/services/personnel/operator_excel_import_service.py:58` [Service] `status = normalize_operator_status(data.get("状态"))`
- **被调用者**（2 个）：`_text`, `v.lower`

### `normalize_supplier_status()` [公开]
- 位置：第 64-85 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/process_excel_suppliers.py:56` [Route] `return normalize_supplier_status(value)`
  - `core/services/process/supplier_excel_import_service.py:35` [Service] `return normalize_supplier_status(value)`
- **被调用者**（2 个）：`_text`, `v.lower`

### `normalize_op_type_category()` [公开]
- 位置：第 88-109 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/process_excel_op_types.py:56` [Route] `return normalize_op_type_category(value)`
  - `core/services/process/op_type_excel_import_service.py:57` [Service] `cat = normalize_op_type_category(data.get("归属"))`
- **被调用者**（2 个）：`_text`, `v.lower`

### `normalize_yes_no_wide()` [公开]
- 位置：第 116-136 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（3 处）：
  - `core/services/personnel/operator_machine_query_service.py:34` [Service] `out["is_primary"] = normalize_yes_no_wide(out.get("is_primary"), default=YesNo.N`
  - `core/services/scheduler/number_utils.py:59` [Service] `return normalize_yes_no_wide(value, default=default, unknown_policy="no")`
  - `core/services/system/system_config_service.py:18` [Service] `return normalize_yes_no_wide(value, default="no", unknown_policy="no")`
- **被调用者**（3 个）：`lower`, `strip`, `str`

### `normalize_yesno_narrow()` [公开]
- 位置：第 139-160 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（3 处）：
  - `web/routes/normalizers.py:75` [Route] `return normalize_yesno_narrow(value, default=YesNo.YES.value, unknown_policy="pa`
  - `core/services/common/excel_validators.py:62` [Service] `return normalize_yesno_narrow(value, default=YesNo.YES.value, unknown_policy="pa`
  - `core/services/scheduler/calendar_admin.py:96` [Service] `return normalize_yesno_narrow(v, default=YesNo.YES.value, unknown_policy="raise"`
- **被调用者**（5 个）：`v.lower`, `strip`, `ValueError`, `lower`, `str`

### `normalize_skill_level()` [公开]
- 位置：第 163-188 行
- 参数：value
- 返回类型：无注解
- **调用者**（3 处）：
  - `core/services/personnel/operator_machine_normalizers.py:19` [Service] `return normalize_skill_level(value, default="normal", allow_none=True)`
  - `core/services/personnel/operator_machine_normalizers.py:47` [Service] `return normalize_skill_level(value, default="normal", allow_none=False)`
  - `core/services/personnel/operator_machine_query_service.py:30` [Service] `out["skill_level"] = normalize_skill_level(out.get("skill_level"), default="norm`
- **被调用者**（4 个）：`strip`, `s0.lower`, `ValueError`, `str`

### `skill_rank()` [公开]
- 位置：第 191-211 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`normalize_skill_level`

## core/services/common/excel_templates.py（Service 层）

### `_sanitize_export_cell()` [私有]
- 位置：第 23-26 行
- 参数：value
- 返回类型：Name(id='Any', ctx=Load())

### `_iter_column_indices()` [私有]
- 位置：第 29-32 行
- 参数：spec, key
- 返回类型：Subscript(value=Name(id='Iterable', ctx=Load()), slice=Index

### `_apply_number_format()` [私有]
- 位置：第 35-39 行
- 参数：ws, col_indices, fmt, max_row
- 返回类型：Constant(value=None, kind=None)

### `_apply_enum_validations()` [私有]
- 位置：第 42-52 行
- 参数：ws, enum_cols, max_row
- 返回类型：Constant(value=None, kind=None)

### `_auto_width()` [私有]
- 位置：第 55-71 行
- 参数：ws
- 返回类型：Constant(value=None, kind=None)

### `_apply_sheet_layout()` [私有]
- 位置：第 74-96 行
- 参数：ws
- 返回类型：Constant(value=None, kind=None)

### `build_xlsx_bytes()` [公开]
- 位置：第 99-124 行
- 参数：headers, rows
- 返回类型：Attribute(value=Name(id='io', ctx=Load()), attr='BytesIO', c
- **调用者**（25 处）：
  - `web/routes/equipment_excel_links.py:262` [Route] `output = build_xlsx_bytes(`
  - `web/routes/equipment_excel_links.py:295` [Route] `output = build_xlsx_bytes(`
  - `web/routes/equipment_excel_machines.py:387` [Route] `output = build_xlsx_bytes(`
  - `web/routes/equipment_excel_machines.py:418` [Route] `output = build_xlsx_bytes(`
  - `web/routes/excel_demo.py:291` [Route] `output = build_xlsx_bytes(`
  - `web/routes/personnel_excel_links.py:250` [Route] `output = build_xlsx_bytes(`
  - `web/routes/personnel_excel_links.py:283` [Route] `output = build_xlsx_bytes(`
  - `web/routes/personnel_excel_operators.py:315` [Route] `output = build_xlsx_bytes(`
  - `web/routes/personnel_excel_operators.py:348` [Route] `output = build_xlsx_bytes(`
  - `web/routes/personnel_excel_operator_calendar.py:373` [Route] `output = build_xlsx_bytes(`
  - `web/routes/personnel_excel_operator_calendar.py:404` [Route] `output = build_xlsx_bytes(`
  - `web/routes/process_excel_op_types.py:292` [Route] `output = build_xlsx_bytes(`
  - `web/routes/process_excel_op_types.py:324` [Route] `output = build_xlsx_bytes(`
  - `web/routes/process_excel_part_operations.py:34` [Route] `output = build_xlsx_bytes(`
  - `web/routes/process_excel_part_operation_hours.py:412` [Route] `output = build_xlsx_bytes(`
  - `web/routes/process_excel_part_operation_hours.py:444` [Route] `output = build_xlsx_bytes(`
  - `web/routes/process_excel_routes.py:299` [Route] `output = build_xlsx_bytes(`
  - `web/routes/process_excel_routes.py:332` [Route] `output = build_xlsx_bytes(`
  - `web/routes/process_excel_suppliers.py:330` [Route] `output = build_xlsx_bytes(`
  - `web/routes/process_excel_suppliers.py:360` [Route] `output = build_xlsx_bytes(`
  - `web/routes/scheduler_excel_batches.py:383` [Route] `output = build_xlsx_bytes(`
  - `web/routes/scheduler_excel_batches.py:414` [Route] `output = build_xlsx_bytes(`
  - `web/routes/scheduler_excel_calendar.py:447` [Route] `output = build_xlsx_bytes(`
  - `web/routes/scheduler_excel_calendar.py:478` [Route] `output = build_xlsx_bytes(`
  - `web/routes/scheduler_week_plan.py:115` [Route] `output = build_xlsx_bytes(`
- **被调用者**（10 个）：`openpyxl.Workbook`, `ws.append`, `_apply_sheet_layout`, `io.BytesIO`, `wb.save`, `output.seek`, `list`, `wb.close`, `len`, `_sanitize_export_cell`

### `_write_xlsx()` [私有]
- 位置：第 127-137 行
- 参数：path, headers, sample_rows
- 返回类型：Constant(value=None, kind=None)

### `get_template_definition()` [公开]
- 位置：第 140-144 行
- 参数：filename
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（22 处）：
  - `web/routes/equipment_excel_links.py:260` [Route] `template_def = get_template_definition("设备人员关联.xlsx")`
  - `web/routes/equipment_excel_links.py:294` [Route] `template_def = get_template_definition("设备人员关联.xlsx")`
  - `web/routes/equipment_excel_machines.py:385` [Route] `template_def = get_template_definition("设备信息.xlsx")`
  - `web/routes/equipment_excel_machines.py:417` [Route] `template_def = get_template_definition("设备信息.xlsx")`
  - `web/routes/excel_demo.py:289` [Route] `template_def = get_template_definition("人员基本信息.xlsx")`
  - `web/routes/personnel_excel_links.py:248` [Route] `template_def = get_template_definition("人员设备关联.xlsx")`
  - `web/routes/personnel_excel_links.py:282` [Route] `template_def = get_template_definition("人员设备关联.xlsx")`
  - `web/routes/personnel_excel_operators.py:313` [Route] `template_def = get_template_definition("人员基本信息.xlsx")`
  - `web/routes/personnel_excel_operators.py:347` [Route] `template_def = get_template_definition("人员基本信息.xlsx")`
  - `web/routes/personnel_excel_operator_calendar.py:371` [Route] `template_def = get_template_definition("人员专属工作日历.xlsx")`
  - `web/routes/personnel_excel_operator_calendar.py:403` [Route] `template_def = get_template_definition("人员专属工作日历.xlsx")`
  - `web/routes/process_excel_op_types.py:290` [Route] `template_def = get_template_definition("工种配置.xlsx")`
  - `web/routes/process_excel_op_types.py:323` [Route] `template_def = get_template_definition("工种配置.xlsx")`
  - `web/routes/process_excel_part_operation_hours.py:410` [Route] `template_def = get_template_definition("零件工序工时.xlsx")`
  - `web/routes/process_excel_part_operation_hours.py:443` [Route] `template_def = get_template_definition("零件工序工时.xlsx")`
  - `web/routes/process_excel_routes.py:297` [Route] `template_def = get_template_definition("零件工艺路线.xlsx")`
  - `web/routes/process_excel_routes.py:331` [Route] `template_def = get_template_definition("零件工艺路线.xlsx")`
  - `web/routes/process_excel_suppliers.py:328` [Route] `template_def = get_template_definition("供应商配置.xlsx")`
  - `web/routes/scheduler_excel_batches.py:381` [Route] `template_def = get_template_definition("批次信息.xlsx")`
  - `web/routes/scheduler_excel_batches.py:413` [Route] `template_def = get_template_definition("批次信息.xlsx")`
  - `web/routes/scheduler_excel_calendar.py:445` [Route] `template_def = get_template_definition("工作日历.xlsx")`
  - `web/routes/scheduler_excel_calendar.py:477` [Route] `template_def = get_template_definition("工作日历.xlsx")`
- **被调用者**（4 个）：`get_default_templates`, `KeyError`, `str`, `item.get`

### `get_default_templates()` [公开]
- 位置：第 147-287 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）

### `ensure_excel_templates()` [公开]
- 位置：第 290-316 行
- 参数：template_dir
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`abspath`, `os.makedirs`, `get_default_templates`, `join`, `exists`, `_write_xlsx`, `created.append`, `skipped.append`, `t.get`

## core/services/common/excel_validators.py（Service 层）

### `_normalize_batch_priority()` [私有]
- 位置：第 25-34 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_ready_status()` [私有]
- 位置：第 37-46 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_operator_calendar_day_type()` [私有]
- 位置：第 49-58 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_yesno()` [私有]
- 位置：第 61-62 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_batch_date_cell()` [私有]
- 位置：第 65-91 行
- 参数：value, field_label
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `get_batch_row_validate_and_normalize()` [公开]
- 位置：第 94-143 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='Callable', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/routes/scheduler_excel_batches.py:212` [Route] `validate_row = get_batch_row_validate_and_normalize(g.db, parts_cache=parts, inp`
  - `web/routes/scheduler_excel_batches.py:298` [Route] `validate_row = get_batch_row_validate_and_normalize(g.db, parts_cache=parts, inp`
- **被调用者**（15 个）：`isinstance`, `is_blank_value`, `to_str_or_blank`, `target.get`, `_normalize_batch_priority`, `_normalize_ready_status`, `_normalize_batch_date_cell`, `ready_res.get`, `due_res.get`, `dict`, `parse_finite_int`, `str`, `list`, `strip`, `PartRepository`

### `get_operator_calendar_row_validate_and_normalize()` [公开]
- 位置：第 146-238 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='Callable', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/routes/personnel_excel_operator_calendar.py:155` [Route] `validate_row = get_operator_calendar_row_validate_and_normalize(`
  - `web/routes/personnel_excel_operator_calendar.py:280` [Route] `validate_row = get_operator_calendar_row_validate_and_normalize(`
- **被调用者**（16 个）：`OperatorRepository`, `float`, `to_str_or_blank`, `is_blank_value`, `_normalize_operator_calendar_day_type`, `target.get`, `_normalize_yesno`, `dict`, `repo.exists`, `normalize_date`, `normalize_hhmm`, `strip`, `datetime.strptime`, `str`, `total_seconds`

## core/services/common/normalize.py（Service 层）

### `normalize_text()` [公开]
- 位置：第 8-40 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（19 处）：
  - `web/routes/process_excel_op_types.py:60` [Route] `return normalize_text(value) or ""`
  - `web/routes/process_excel_op_types.py:84` [Route] `ot_id = normalize_text(row.get("工种ID")) or ""`
  - `core/services/equipment/machine_downtime_service.py:40` [Service] `return normalize_text(value)`
  - `core/services/equipment/machine_service.py:31` [Service] `return normalize_text(value)`
  - `core/services/personnel/operator_excel_import_service.py:55` [Service] `name = normalize_text(data.get("姓名"))`
  - `core/services/personnel/operator_excel_import_service.py:63` [Service] `remark = normalize_text(data.get("备注"))`
  - `core/services/personnel/operator_machine_normalizers.py:13` [Service] `return normalize_text(value)`
  - `core/services/personnel/operator_service.py:29` [Service] `return normalize_text(value)`
  - `core/services/personnel/resource_team_service.py:23` [Service] `return normalize_text(value)`
  - `core/services/process/external_group_service.py:26` [Service] `return normalize_text(value)`
  - `core/services/process/op_type_service.py:25` [Service] `return normalize_text(value)`
  - `core/services/process/part_service.py:46` [Service] `return normalize_text(value)`
  - `core/services/process/supplier_excel_import_service.py:86` [Service] `remark = normalize_text(data.get("备注"))`
  - `core/services/process/supplier_service.py:26` [Service] `return normalize_text(value)`
  - `core/services/scheduler/batch_service.py:43` [Service] `return normalize_text(value)`
  - `core/services/scheduler/calendar_admin.py:58` [Service] `return normalize_text(value)`
  - `core/services/scheduler/calendar_engine.py:92` [Service] `return normalize_text(value)`
  - `core/services/scheduler/config_service.py:76` [Service] `return normalize_text(value)`
  - `core/services/scheduler/schedule_service.py:73` [Service] `return normalize_text(value)`
- **被调用者**（6 个）：`isinstance`, `strip`, `math.isnan`, `value.strip`, `value.is_nan`, `str`

### `to_str_or_blank()` [公开]
- 位置：第 43-52 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（39 处）：
  - `web/routes/personnel_excel_operator_calendar.py:107` [Route] `op_id = to_str_or_blank(item.get("工号"))`
  - `web/routes/personnel_excel_operator_calendar.py:118` [Route] `item["日期"] = to_str_or_blank(raw_date).replace("/", "-")[:10]`
  - `web/routes/personnel_excel_operator_calendar.py:123` [Route] `item["日期"] = to_str_or_blank(raw_date).replace("/", "-")[:10]`
  - `web/routes/personnel_excel_operator_calendar.py:125` [Route] `item["日期"] = to_str_or_blank(raw_date).replace("/", "-")[:10]`
  - `web/routes/personnel_excel_operator_calendar.py:129` [Route] `item["__id"] = f"{op_id}|{to_str_or_blank(item.get('日期'))}"`
  - `web/routes/process_excel_part_operation_hours.py:73` [Route] `part_no = to_str_or_blank(r["part_no"])`
  - `web/routes/process_excel_part_operation_hours.py:76` [Route] `source = to_str_or_blank(r["source"]).lower() or SourceType.INTERNAL.value`
  - `web/routes/process_excel_part_operation_hours.py:102` [Route] `part_no = to_str_or_blank(r.get("图号"))`
  - `web/routes/process_excel_part_operation_hours.py:118` [Route] `part_no = to_str_or_blank(row.get("图号"))`
  - `web/routes/process_excel_part_operation_hours.py:144` [Route] `if to_str_or_blank(meta.get("归属")).lower() != SourceType.INTERNAL.value:`
  - `web/routes/process_excel_part_operation_hours.py:156` [Route] `"source": to_str_or_blank((meta or {}).get("归属")).lower(),`
  - `core/services/common/excel_validators.py:109` [Service] `pn = to_str_or_blank(target.get("图号"))`
  - `core/services/common/excel_validators.py:159` [Service] `op_id = to_str_or_blank(target.get("工号"))`
  - `core/services/equipment/machine_excel_import_service.py:41` [Service] `raw = to_str_or_blank(value)`
  - `core/services/equipment/machine_excel_import_service.py:64` [Service] `return to_str_or_blank((getattr(pr, "data", None) or {}).get("设备编号"))`
  - `core/services/equipment/machine_excel_import_service.py:68` [Service] `machine_id = to_str_or_blank(data.get("设备编号"))`
  - `core/services/equipment/machine_excel_import_service.py:72` [Service] `name = to_str_or_blank(data.get("设备名称"))`
  - `core/services/personnel/operator_excel_import_service.py:48` [Service] `return to_str_or_blank((getattr(pr, "data", None) or {}).get("工号"))`
  - `core/services/personnel/operator_excel_import_service.py:52` [Service] `op_id = to_str_or_blank(data.get("工号"))`
  - `core/services/personnel/operator_machine_service.py:81` [Service] `op_id = to_str_or_blank(r.get("operator_id"))`
  - `core/services/personnel/operator_machine_service.py:82` [Service] `mc_id = to_str_or_blank(r.get("machine_id"))`
  - `core/services/personnel/operator_machine_service.py:216` [Service] `if primary_raw is None or to_str_or_blank(primary_raw) == "":`
  - `core/services/personnel/operator_machine_service.py:218` [Service] `v = to_str_or_blank(primary_raw).lower()`
  - `core/services/personnel/operator_machine_service.py:238` [Service] `op_id = to_str_or_blank((pr.data or {}).get("工号"))`
  - `core/services/personnel/operator_machine_service.py:430` [Service] `op_id = to_str_or_blank(pr.data.get("工号"))`
  - `core/services/personnel/operator_machine_service.py:431` [Service] `mc_id = to_str_or_blank(pr.data.get("设备编号"))`
  - `core/services/process/op_type_excel_import_service.py:46` [Service] `return to_str_or_blank((getattr(pr, "data", None) or {}).get("工种ID"))`
  - `core/services/process/op_type_excel_import_service.py:50` [Service] `ot_id = to_str_or_blank(data.get("工种ID"))`
  - `core/services/process/op_type_excel_import_service.py:53` [Service] `name = to_str_or_blank(data.get("工种名称"))`
  - `core/services/process/part_operation_hours_excel_import_service.py:146` [Service] `part_no = to_str_or_blank(data.get("图号"))`
  - `core/services/process/supplier_excel_import_service.py:38` [Service] `raw = to_str_or_blank(value)`
  - `core/services/process/supplier_excel_import_service.py:61` [Service] `return to_str_or_blank((getattr(pr, "data", None) or {}).get("供应商ID"))`
  - `core/services/process/supplier_excel_import_service.py:65` [Service] `sid = to_str_or_blank(data.get("供应商ID"))`
  - `core/services/process/supplier_excel_import_service.py:68` [Service] `name = to_str_or_blank(data.get("名称"))`
  - `core/services/scheduler/calendar_service.py:176` [Service] `rid = to_str_or_blank(pr.data.get("__id"))`
  - `core/services/scheduler/calendar_service.py:179` [Service] `op_id = to_str_or_blank(pr.data.get("工号"))`
  - `core/services/scheduler/calendar_service.py:180` [Service] `date_str = to_str_or_blank(pr.data.get("日期"))`
  - `core/services/scheduler/calendar_service.py:186` [Service] `"operator_id": to_str_or_blank(pr.data.get("工号")),`
  - `core/services/scheduler/calendar_service.py:187` [Service] `"date": to_str_or_blank(pr.data.get("日期")),`
- **被调用者**（1 个）：`normalize_text`

### `is_blank_value()` [公开]
- 位置：第 55-57 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（19 处）：
  - `web/routes/equipment_excel_machines.py:34` [Route] `if is_blank_value(row.get("设备编号")):`
  - `web/routes/equipment_excel_machines.py:36` [Route] `if is_blank_value(row.get("设备名称")):`
  - `web/routes/excel_demo.py:63` [Route] `if is_blank_value(row.get("工号")):`
  - `web/routes/excel_demo.py:65` [Route] `if is_blank_value(row.get("姓名")):`
  - `web/routes/personnel_excel_operators.py:27` [Route] `if is_blank_value(row.get("工号")):`
  - `web/routes/personnel_excel_operators.py:29` [Route] `if is_blank_value(row.get("姓名")):`
  - `web/routes/process_excel_routes.py:83` [Route] `if is_blank_value(row.get("图号")):`
  - `web/routes/process_excel_routes.py:85` [Route] `if is_blank_value(row.get("名称")):`
  - `web/routes/process_excel_routes.py:161` [Route] `if is_blank_value(row.get("图号")):`
  - `web/routes/process_excel_routes.py:163` [Route] `if is_blank_value(row.get("名称")):`
  - `web/routes/process_excel_suppliers.py:114` [Route] `if is_blank_value(row.get("供应商ID")):`
  - `web/routes/process_excel_suppliers.py:116` [Route] `if is_blank_value(row.get("名称")):`
  - `web/routes/process_excel_suppliers.py:224` [Route] `if is_blank_value(row.get("供应商ID")):`
  - `web/routes/process_excel_suppliers.py:226` [Route] `if is_blank_value(row.get("名称")):`
  - `web/routes/scheduler_excel_calendar.py:147` [Route] `if is_blank_value(row.get("日期")):`
  - `web/routes/scheduler_excel_calendar.py:279` [Route] `if is_blank_value(row.get("日期")):`
  - `core/services/common/excel_validators.py:105` [Service] `if is_blank_value(target.get("批次号")):`
  - `core/services/common/excel_validators.py:107` [Service] `if is_blank_value(target.get("图号")):`
  - `core/services/common/excel_validators.py:165` [Service] `if is_blank_value(target.get("日期")):`
- **被调用者**（1 个）：`normalize_text`

## core/services/equipment/machine_excel_import_service.py（Service 层）

### `MachineExcelImportService.__init__()` [私有]
- 位置：第 26-34 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `MachineExcelImportService._normalize_machine_status_for_excel()` [私有]
- 位置：第 37-38 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `MachineExcelImportService._resolve_op_type_id_strict_for_excel()` [私有]
- 位置：第 40-47 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `MachineExcelImportService.apply_preview_rows()` [公开]
- 位置：第 49-108 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `web/routes/equipment_excel_machines.py:335` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/excel_demo.py:236` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/personnel_excel_operators.py:262` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_op_types.py:239` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_part_operation_hours.py:360` [Route] `stats = import_svc.apply_preview_rows(preview_rows)`
  - `web/routes/process_excel_suppliers.py:278` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
- **被调用者**（17 个）：`list`, `set`, `execute_preview_rows_transactional`, `stats.to_dict`, `len`, `ensure_replace_allowed`, `delete_all`, `to_str_or_blank`, `self._normalize_machine_status_for_excel`, `get`, `getattr`, `data.get`, `ValidationError`, `self._resolve_op_type_id_strict_for_excel`, `resolve_team_id_optional`

## core/services/personnel/operator_excel_import_service.py（Service 层）

### `OperatorExcelImportService.__init__()` [私有]
- 位置：第 25-31 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `OperatorExcelImportService.apply_preview_rows()` [公开]
- 位置：第 33-92 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `web/routes/equipment_excel_machines.py:335` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/excel_demo.py:236` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/personnel_excel_operators.py:262` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_op_types.py:239` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_part_operation_hours.py:360` [Route] `stats = import_svc.apply_preview_rows(preview_rows)`
  - `web/routes/process_excel_suppliers.py:278` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
- **被调用者**（17 个）：`list`, `set`, `execute_preview_rows_transactional`, `stats.to_dict`, `len`, `ensure_replace_allowed`, `delete_all`, `to_str_or_blank`, `normalize_text`, `normalize_operator_status`, `get`, `getattr`, `data.get`, `ValidationError`, `resolve_team_id_optional`

## core/services/personnel/operator_machine_normalizers.py（Service 层）

### `normalize_operator_machine_text()` [公开]
- 位置：第 12-13 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/personnel/operator_machine_service.py:35` [Service] `return om_normalizers.normalize_operator_machine_text(value)`
- **被调用者**（1 个）：`normalize_text`

### `normalize_skill_level_optional()` [公开]
- 位置：第 16-24 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/personnel/operator_machine_service.py:39` [Service] `return om_normalizers.normalize_skill_level_optional(value)`
- **被调用者**（2 个）：`normalize_skill_level`, `ValidationError`

### `normalize_yes_no_optional()` [公开]
- 位置：第 27-42 行
- 参数：value, field
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/personnel/operator_machine_service.py:43` [Service] `return om_normalizers.normalize_yes_no_optional(value, field)`
- **被调用者**（4 个）：`strip`, `s.lower`, `ValidationError`, `str`

### `normalize_skill_level_stored()` [公开]
- 位置：第 45-49 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `core/services/personnel/operator_machine_service.py:47` [Service] `return om_normalizers.normalize_skill_level_stored(value)`
- **被调用者**（1 个）：`normalize_skill_level`

### `normalize_yes_no_stored()` [公开]
- 位置：第 52-63 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `core/services/personnel/operator_machine_service.py:51` [Service] `return om_normalizers.normalize_yes_no_stored(value)`
- **被调用者**（3 个）：`strip`, `s.lower`, `str`

### `normalize_link_record()` [公开]
- 位置：第 66-69 行
- 参数：link
- 返回类型：Name(id='OperatorMachine', ctx=Load())
- **调用者**（1 处）：
  - `core/services/personnel/operator_machine_service.py:55` [Service] `return om_normalizers.normalize_link_record(link)`
- **被调用者**（3 个）：`normalize_skill_level_stored`, `normalize_yes_no_stored`, `getattr`

## core/services/personnel/operator_machine_service.py（Service 层）

### `OperatorMachineService.__init__()` [私有]
- 位置：第 22-30 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `OperatorMachineService._normalize_text()` [私有]
- 位置：第 34-35 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._normalize_skill_level_optional()` [私有]
- 位置：第 38-39 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._normalize_yes_no_optional()` [私有]
- 位置：第 42-43 行
- 参数：value, field
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._normalize_skill_level_stored()` [私有]
- 位置：第 46-47 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `OperatorMachineService._normalize_yes_no_stored()` [私有]
- 位置：第 50-51 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `OperatorMachineService._normalize_link()` [私有]
- 位置：第 54-55 行
- 参数：link
- 返回类型：Name(id='OperatorMachine', ctx=Load())

### `OperatorMachineService._ensure_operator_exists()` [私有]
- 位置：第 57-59 行
- 参数：operator_id
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._ensure_machine_exists()` [私有]
- 位置：第 61-63 行
- 参数：machine_id
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._detect_optional_columns()` [私有]
- 位置：第 66-69 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._detect_optional_columns_from_preview()` [私有]
- 位置：第 72-75 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._build_existing_link_map()` [私有]
- 位置：第 77-89 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `OperatorMachineService._validate_required_ids_for_preview_row()` [私有]
- 位置：第 91-102 行
- 参数：row, row_num
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._check_duplicate_key_in_file()` [私有]
- 位置：第 105-114 行
- 参数：key
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._check_fk_exists()` [私有]
- 位置：第 116-131 行
- 参数：op_id, mc_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._parse_skill_optional_for_preview()` [私有]
- 位置：第 133-143 行
- 参数：row, row_num
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._parse_primary_optional_for_preview()` [私有]
- 位置：第 145-155 行
- 参数：row, row_num
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._build_overwrite_preview_for_existing()` [私有]
- 位置：第 157-169 行
- 参数：无
- 返回类型：Name(id='ImportPreviewRow', ctx=Load())

### `OperatorMachineService._decide_preview_row()` [私有]
- 位置：第 171-181 行
- 参数：无
- 返回类型：Name(id='ImportPreviewRow', ctx=Load())

### `OperatorMachineService._preview_one_row()` [私有]
- 位置：第 183-211 行
- 参数：无
- 返回类型：Name(id='ImportPreviewRow', ctx=Load())

### `OperatorMachineService._is_primary_yes()` [私有]
- 位置：第 214-219 行
- 参数：data
- 返回类型：Name(id='bool', ctx=Load())

### `OperatorMachineService._collect_dup_primary_yes_operators()` [私有]
- 位置：第 221-231 行
- 参数：preview
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Index(valu

### `OperatorMachineService._mark_dup_primary_yes()` [私有]
- 位置：第 234-244 行
- 参数：preview, dup_ops
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._enforce_primary_unique_in_file()` [私有]
- 位置：第 246-249 行
- 参数：preview
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._resolve_write_values()` [私有]
- 位置：第 251-273 行
- 参数：pr
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService.list_by_operator()` [公开]
- 位置：第 278-282 行
- 参数：operator_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/personnel_pages.py:106` [Route] `links = link_svc.list_by_operator(operator_id)`
  - `core/services/scheduler/calendar_admin.py:353` [Service] `return self.operator_calendar_repo.list_by_operator(op_id)`
- **被调用者**（3 个）：`self._normalize_text`, `ValidationError`, `self._normalize_link`

### `OperatorMachineService.list_by_machine()` [公开]
- 位置：第 284-288 行
- 参数：machine_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/equipment_pages.py:199` [Route] `links = link_svc.list_by_machine(machine_id)`
  - `web/routes/equipment_pages.py:200` [Route] `downtimes = dt_svc.list_by_machine(machine_id, include_cancelled=False)`
  - `core/services/equipment/machine_downtime_service.py:76` [Service] `return self.repo.list_by_machine(mc_id, include_cancelled=include_cancelled)`
- **被调用者**（3 个）：`self._normalize_text`, `ValidationError`, `self._normalize_link`

### `OperatorMachineService.add_link()` [公开]
- 位置：第 290-318 行
- 参数：operator_id, machine_id, skill_level, is_primary
- 返回类型：Name(id='OperatorMachine', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:343` [Route] `svc.add_link(operator_id=operator_id, machine_id=machine_id)`
  - `web/routes/personnel_pages.py:253` [Route] `svc.add_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（11 个）：`self._normalize_text`, `self._ensure_operator_exists`, `self._ensure_machine_exists`, `exists`, `ValidationError`, `BusinessError`, `self._normalize_skill_level_optional`, `self._normalize_yes_no_optional`, `transaction`, `add`, `clear_primary_for_operator`

### `OperatorMachineService.remove_link()` [公开]
- 位置：第 320-328 行
- 参数：operator_id, machine_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:368` [Route] `svc.remove_link(operator_id=operator_id, machine_id=machine_id)`
  - `web/routes/personnel_pages.py:279` [Route] `svc.remove_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（4 个）：`self._normalize_text`, `ValidationError`, `transaction`, `remove`

### `OperatorMachineService.update_link_fields()` [公开]
- 位置：第 330-361 行
- 参数：operator_id, machine_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:354` [Route] `svc.update_link_fields(`
  - `web/routes/personnel_pages.py:265` [Route] `svc.update_link_fields(`
- **被调用者**（9 个）：`self._normalize_text`, `ValidationError`, `exists`, `BusinessError`, `self._normalize_skill_level_optional`, `self._normalize_yes_no_optional`, `transaction`, `update_fields`, `clear_primary_for_operator`

### `OperatorMachineService.preview_import_links()` [公开]
- 位置：第 366-398 行
- 参数：rows, mode
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/equipment_excel_links.py:126` [Route] `preview_rows = link_svc.preview_import_links(rows=normalized_rows, mode=mode)`
  - `web/routes/equipment_excel_links.py:194` [Route] `preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)`
  - `web/routes/personnel_excel_links.py:113` [Route] `preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)`
  - `web/routes/personnel_excel_links.py:182` [Route] `preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)`
- **被调用者**（7 个）：`self._detect_optional_columns`, `self._build_existing_link_map`, `set`, `enumerate`, `self._preview_one_row`, `preview.append`, `self._enforce_primary_unique_in_file`

### `OperatorMachineService.apply_import_links()` [公开]
- 位置：第 400-475 行
- 参数：preview_rows, mode
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/equipment_excel_links.py:214` [Route] `stats = link_svc.apply_import_links(preview_rows=preview_rows, mode=mode)`
  - `web/routes/personnel_excel_links.py:202` [Route] `stats = link_svc.apply_import_links(preview_rows=preview_rows, mode=mode)`
- **被调用者**（14 个）：`self._detect_optional_columns_from_preview`, `self._build_existing_link_map`, `transaction`, `len`, `delete_all`, `to_str_or_blank`, `existing_map.get`, `self._resolve_write_values`, `exists`, `get`, `update_fields`, `add`, `errors_sample.append`, `clear_primary_for_operator`

## core/services/process/op_type_excel_import_service.py（Service 层）

### `OpTypeExcelImportService.__init__()` [私有]
- 位置：第 24-29 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `OpTypeExcelImportService.apply_preview_rows()` [公开]
- 位置：第 31-81 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `web/routes/equipment_excel_machines.py:335` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/excel_demo.py:236` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/personnel_excel_operators.py:262` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_op_types.py:239` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_part_operation_hours.py:360` [Route] `stats = import_svc.apply_preview_rows(preview_rows)`
  - `web/routes/process_excel_suppliers.py:278` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
- **被调用者**（15 个）：`list`, `set`, `execute_preview_rows_transactional`, `stats.to_dict`, `len`, `ensure_replace_allowed`, `delete_all`, `to_str_or_blank`, `normalize_op_type_category`, `get`, `getattr`, `data.get`, `ValidationError`, `update`, `create`

## core/services/process/part_operation_hours_excel_import_service.py（Service 层）

### `_ImportStats.add_error()` [公开]
- 位置：第 23-26 行
- 参数：row_num, message
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`append`, `len`

### `_ImportStats.to_dict()` [公开]
- 位置：第 28-36 行
- 参数：total_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（62 处）：
  - `web/routes/equipment_pages.py:216` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:229` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:27` [Route] `items = [m.to_dict() for m in svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:23` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:48` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:144` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:81` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:82` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:83` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:112` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:85` [Route] `supplier=s.to_dict(),`
  - `web/routes/scheduler_batches.py:41` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:64` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:113` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:186` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:230` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/scheduler_resource_dispatch.py:51` [Route] `for key, value in request.args.to_dict(flat=True).items():`
  - `web/routes/scheduler_resource_dispatch.py:188` [Route] `return redirect(url_for("scheduler.resource_dispatch_page", **request.args.to_di`
  - `web/routes/system_backup.py:38` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:35` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:42` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:52` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:145` [Route] `d = it.to_dict()`
  - `core/services/common/pandas_backend.py:64` [Service] `raw_rows = df.to_dict(orient="records")`
  - `core/services/equipment/machine_excel_import_service.py:106` [Service] `out = stats.to_dict()`
  - `core/services/material/material_service.py:82` [Service] `self.op_logger.info(module="material", action="create", target_type="material", `
  - `core/services/personnel/operator_excel_import_service.py:90` [Service] `out = stats.to_dict()`
  - `core/services/personnel/resource_team_service.py:74` [Service] `return [team.to_dict() for team in self.list(status=status)]`
  - `core/services/process/op_type_excel_import_service.py:79` [Service] `out = stats.to_dict()`
  - `core/services/process/route_parser.py:57` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:77` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:78` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
  - `core/services/process/supplier_excel_import_service.py:114` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:102` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:258` [Service] `self.batch_repo.create(b.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:328` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:384` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:389` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config_presets.py:20` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:29` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:37` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:128` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config_presets.py:180` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/gantt_contract.py:70` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:164` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:206` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_optimizer.py:186` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:199` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:246` [Service] `cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(`
  - `core/services/scheduler/schedule_optimizer_steps.py:101` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:126` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:215` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:240` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_summary.py:46` [Service] `obj = to_dict()`
  - `core/services/scheduler/schedule_summary.py:423` [Service] `"metrics": best_metrics.to_dict() if best_metrics is not None else None,`
- **被调用者**（1 个）：`list`

### `PartOperationHoursExcelImportService.__init__()` [私有]
- 位置：第 42-47 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `PartOperationHoursExcelImportService.apply_preview_rows()` [公开]
- 位置：第 49-59 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `web/routes/equipment_excel_machines.py:335` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/excel_demo.py:236` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/personnel_excel_operators.py:262` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_op_types.py:239` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_part_operation_hours.py:360` [Route] `stats = import_svc.apply_preview_rows(preview_rows)`
  - `web/routes/process_excel_suppliers.py:278` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
- **被调用者**（5 个）：`_ImportStats`, `stats.to_dict`, `transaction`, `self._apply_one`, `len`

### `PartOperationHoursExcelImportService._apply_one()` [私有]
- 位置：第 61-84 行
- 参数：pr, stats
- 返回类型：Constant(value=None, kind=None)

### `PartOperationHoursExcelImportService._apply_non_write_row()` [私有]
- 位置：第 87-97 行
- 参数：pr, stats
- 返回类型：Constant(value=None, kind=None)

### `PartOperationHoursExcelImportService._coerce_int()` [私有]
- 位置：第 100-118 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `PartOperationHoursExcelImportService._coerce_finite_float()` [私有]
- 位置：第 121-141 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `PartOperationHoursExcelImportService._parse_write_row()` [私有]
- 位置：第 144-160 行
- 参数：pr
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

## core/services/process/part_operation_query_service.py（Service 层）

### `PartOperationQueryService.__init__()` [私有]
- 位置：第 11-15 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `PartOperationQueryService.list_all_active_with_details()` [公开]
- 位置：第 17-18 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/process_excel_part_operations.py:33` [Route] `rows = q.list_all_active_with_details()`

### `PartOperationQueryService.list_active_hours()` [公开]
- 位置：第 20-21 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/process_excel_part_operation_hours.py:66` [Route] `rows = q.list_active_hours()`

### `PartOperationQueryService.list_internal_active_hours()` [公开]
- 位置：第 23-24 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/process_excel_part_operation_hours.py:442` [Route] `rows = q.list_internal_active_hours()`

### `PartOperationQueryService.list_template_snapshot_for_parts()` [公开]
- 位置：第 26-44 行
- 参数：part_nos
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/scheduler_excel_batches.py:85` [Route] `return query_svc.list_template_snapshot_for_parts(part_nos)`
- **被调用者**（6 个）：`sorted`, `list_by_part`, `strip`, `snapshot.append`, `str`, `int`

## core/services/process/supplier_excel_import_service.py（Service 层）

### `SupplierExcelImportService.__init__()` [私有]
- 位置：第 25-31 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `SupplierExcelImportService._normalize_supplier_status_for_excel()` [私有]
- 位置：第 34-35 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `SupplierExcelImportService._resolve_op_type_id_strict_for_excel()` [私有]
- 位置：第 37-44 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `SupplierExcelImportService.apply_preview_rows()` [公开]
- 位置：第 46-116 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `web/routes/equipment_excel_machines.py:335` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/excel_demo.py:236` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/personnel_excel_operators.py:262` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_op_types.py:239` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
  - `web/routes/process_excel_part_operation_hours.py:360` [Route] `stats = import_svc.apply_preview_rows(preview_rows)`
  - `web/routes/process_excel_suppliers.py:278` [Route] `import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_i`
- **被调用者**（20 个）：`list`, `set`, `execute_preview_rows_transactional`, `stats.to_dict`, `len`, `ensure_replace_allowed`, `delete_all`, `to_str_or_blank`, `self._resolve_op_type_id_strict_for_excel`, `data.get`, `self._normalize_supplier_status_for_excel`, `normalize_text`, `get`, `getattr`, `ValidationError`

## core/services/report/exporters/xlsx.py（Service 层）

### `_auto_width()` [私有]
- 位置：第 12-19 行
- 参数：ws
- 返回类型：Constant(value=None, kind=None)

### `_append_row()` [私有]
- 位置：第 22-23 行
- 参数：ws, values
- 返回类型：Constant(value=None, kind=None)

### `_format_sheet()` [私有]
- 位置：第 26-34 行
- 参数：ws
- 返回类型：Constant(value=None, kind=None)

### `export_overdue_xlsx()` [公开]
- 位置：第 37-67 行
- 参数：items
- 返回类型：Attribute(value=Name(id='io', ctx=Load()), attr='BytesIO', c
- **调用者**（2 处）：
  - `web/routes/reports.py:132` [Route] `x = engine.export_overdue_xlsx(version)`
  - `core/services/report/report_engine.py:106` [Service] `buf = export_overdue_xlsx(rep["items"])`
- **被调用者**（8 个）：`openpyxl.Workbook`, `_append_row`, `_format_sheet`, `io.BytesIO`, `wb.save`, `buf.seek`, `wb.close`, `it.get`

### `export_utilization_xlsx()` [公开]
- 位置：第 70-114 行
- 参数：machines, operators
- 返回类型：Attribute(value=Name(id='io', ctx=Load()), attr='BytesIO', c
- **调用者**（2 处）：
  - `web/routes/reports.py:187` [Route] `x = engine.export_utilization_xlsx(version, start_date, end_date)`
  - `core/services/report/report_engine.py:152` [Service] `buf = export_utilization_xlsx(rep["machines"], rep["operators"])`
- **被调用者**（9 个）：`openpyxl.Workbook`, `_append_row`, `_format_sheet`, `wb.create_sheet`, `io.BytesIO`, `wb.save`, `buf.seek`, `wb.close`, `r.get`

### `export_downtime_impact_xlsx()` [公开]
- 位置：第 117-144 行
- 参数：machines
- 返回类型：Attribute(value=Name(id='io', ctx=Load()), attr='BytesIO', c
- **调用者**（2 处）：
  - `web/routes/reports.py:240` [Route] `x = engine.export_downtime_impact_xlsx(version, start_date, end_date)`
  - `core/services/report/report_engine.py:193` [Service] `buf = export_downtime_impact_xlsx(rep["machines"])`
- **被调用者**（8 个）：`openpyxl.Workbook`, `_append_row`, `_format_sheet`, `io.BytesIO`, `wb.save`, `buf.seek`, `wb.close`, `r.get`

## core/services/scheduler/batch_excel_import.py（Service 层）

### `import_batches_from_preview_rows()` [公开]
- 位置：第 10-105 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/batch_service.py:380` [Service] `return batch_excel_import.import_batches_from_preview_rows(`
- **被调用者**（17 个）：`list`, `execute_preview_rows_transactional`, `stats.to_dict`, `len`, `bool`, `set`, `svc.delete_all_no_tx`, `strip`, `int`, `get`, `parts_cache.get`, `svc.update_no_tx`, `svc.create_no_tx`, `svc.create_batch_from_template_no_tx`, `svc.list`

## core/services/scheduler/batch_service.py（Service 层）

### `BatchService.__init__()` [私有]
- 位置：第 20-36 行
- 参数：conn, logger, op_logger, template_resolver
- 返回类型：无注解

### `BatchService._normalize_text()` [私有]
- 位置：第 42-43 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `BatchService._normalize_int()` [私有]
- 位置：第 46-47 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `BatchService._safe_float()` [私有]
- 位置：第 50-58 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `BatchService._normalize_date()` [私有]
- 位置：第 61-90 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `BatchService._validate_enum()` [私有]
- 位置：第 93-106 行
- 参数：value, allowed, field
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `BatchService._get_or_raise()` [私有]
- 位置：第 108-112 行
- 参数：batch_id
- 返回类型：Name(id='Batch', ctx=Load())

### `BatchService._default_template_resolver()` [私有]
- 位置：第 114-122 行
- 参数：part_no, part_name, route_raw, no_tx
- 返回类型：Constant(value=None, kind=None)

### `BatchService._load_template_ops_with_fallback()` [私有]
- 位置：第 124-146 行
- 参数：part_no, part
- 返回类型：无注解

### `BatchService.list()` [公开]
- 位置：第 151-170 行
- 参数：status, priority, part_no
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `web/routes/dashboard.py:23` [Route] `pending_count = len(batch_svc.list(status="pending"))`
  - `web/routes/dashboard.py:24` [Route] `scheduled_count = len(batch_svc.list(status="scheduled"))`
  - `web/routes/material.py:106` [Route] `batches = batch_svc.list()`
  - `web/routes/scheduler_batches.py:34` [Route] `batches = batch_svc.list(status=status if status else None)`
  - `web/routes/scheduler_batches.py:106` [Route] `batches = batch_svc.list(status=status if status else None)`
  - `web/routes/scheduler_excel_batches.py:58` [Route] `existing = {b.batch_id: b for b in batch_svc.list()}`
- **被调用者**（1 个）：`self._validate_enum`

### `BatchService.get()` [公开]
- 位置：第 172-176 行
- 参数：batch_id
- 返回类型：Name(id='Batch', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_batches.py:325` [Route] `b = batch_svc.get(batch_id)`
  - `web/routes/scheduler_batch_detail.py:198` [Route] `b = batch_svc.get(batch_id)`
- **被调用者**（3 个）：`self._normalize_text`, `self._get_or_raise`, `ValidationError`

### `BatchService.create()` [公开]
- 位置：第 178-248 行
- 参数：batch_id, part_no, quantity, due_date, priority, ready_status, ready_date, status, remark, part_name
- 返回类型：Name(id='Batch', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`self._normalize_text`, `self._normalize_int`, `self._normalize_date`, `self._validate_enum`, `get`, `self._get_or_raise`, `ValidationError`, `BusinessError`, `transaction`, `self.create_no_tx`, `int`

### `BatchService.create_no_tx()` [公开]
- 位置：第 250-259 行
- 参数：payload
- 返回类型：Name(id='Batch', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/batch_excel_import.py:63` [Service] `svc.create_no_tx(`
- **被调用者**（4 个）：`create`, `isinstance`, `Batch.from_row`, `b.to_dict`

### `BatchService.update()` [公开]
- 位置：第 261-340 行
- 参数：batch_id, part_no, quantity, due_date, priority, ready_status, ready_date, status, remark, part_name
- 返回类型：Name(id='Batch', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_batches.py:243` [Route] `batch_svc.update(`
- **被调用者**（11 个）：`self._normalize_text`, `self._get_or_raise`, `ValidationError`, `get`, `self._normalize_int`, `int`, `self._normalize_date`, `self._validate_enum`, `BusinessError`, `transaction`, `self.update_no_tx`

### `BatchService.update_no_tx()` [公开]
- 位置：第 342-349 行
- 参数：batch_id, updates
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/batch_excel_import.py:49` [Service] `svc.update_no_tx(`
- **被调用者**（1 个）：`update`

### `BatchService.delete()` [公开]
- 位置：第 351-359 行
- 参数：batch_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/scheduler_batches.py:174` [Route] `batch_svc.delete(batch_id)`
  - `web/routes/scheduler_batches.py:198` [Route] `batch_svc.delete(bid)`
- **被调用者**（4 个）：`self._normalize_text`, `self._get_or_raise`, `ValidationError`, `transaction`

### `BatchService.delete_all_no_tx()` [公开]
- 位置：第 361-369 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `web/routes/process_excel_routes.py:209` [Route] `part_svc.delete_all_no_tx()`
  - `web/routes/scheduler_excel_calendar.py:355` [Route] `cal_svc.delete_all_no_tx()`
  - `core/services/scheduler/batch_excel_import.py:30` [Service] `svc.delete_all_no_tx()`
  - `core/services/scheduler/calendar_service.py:101` [Service] `self._admin.delete_all_no_tx()`
- **被调用者**（1 个）：`delete_all`

### `BatchService.import_from_preview_rows()` [公开]
- 位置：第 371-387 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/scheduler_excel_batches.py:324` [Route] `import_stats = svc.import_from_preview_rows(`
- **被调用者**（1 个）：`batch_excel_import.import_batches_from_preview_rows`

### `BatchService.copy_batch()` [公开]
- 位置：第 389-390 行
- 参数：source_batch_id, new_batch_id
- 返回类型：Name(id='Batch', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_batches.py:271` [Route] `b2 = batch_svc.copy_batch(bid, new_id)`
- **被调用者**（1 个）：`batch_copy.copy_batch`

### `BatchService.create_batch_from_template()` [公开]
- 位置：第 395-451 行
- 参数：batch_id, part_no, quantity, due_date, priority, ready_status, ready_date, remark, rebuild_ops
- 返回类型：Name(id='Batch', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_batches.py:150` [Route] `b = batch_svc.create_batch_from_template(`
  - `web/routes/scheduler_batches.py:327` [Route] `batch_svc.create_batch_from_template(`
- **被调用者**（12 个）：`self._normalize_text`, `self._normalize_int`, `self._normalize_date`, `self._validate_enum`, `get`, `self._load_template_ops_with_fallback`, `self._get_or_raise`, `ValidationError`, `BusinessError`, `transaction`, `self.create_batch_from_template_no_tx`, `int`

### `BatchService.create_batch_from_template_no_tx()` [公开]
- 位置：第 453-476 行
- 参数：batch_id, part_no, quantity, due_date, priority, ready_status, ready_date, remark, rebuild_ops
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/batch_excel_import.py:79` [Service] `svc.create_batch_from_template_no_tx(`
- **被调用者**（1 个）：`batch_template_ops.create_batch_from_template_no_tx`

### `BatchService.list_operations()` [公开]
- 位置：第 478-483 行
- 参数：batch_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/scheduler_batches.py:161` [Route] `flash(f"已创建批次并生成工序：{b.batch_id}（共 {len(batch_svc.list_operations(b.batch_id))} 道`
  - `web/routes/scheduler_batches.py:337` [Route] `cnt = len(batch_svc.list_operations(b.batch_id))`
- **被调用者**（4 个）：`self._normalize_text`, `self._get_or_raise`, `list_by_batch`, `ValidationError`

## core/services/scheduler/calendar_admin.py（Service 层）

### `CalendarAdmin.__init__()` [私有]
- 位置：第 28-34 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `CalendarAdmin._get_holiday_default_efficiency()` [私有]
- 位置：第 36-51 行
- 参数：无
- 返回类型：Name(id='float', ctx=Load())

### `CalendarAdmin._normalize_text()` [私有]
- 位置：第 57-58 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `CalendarAdmin._normalize_float()` [私有]
- 位置：第 61-62 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `CalendarAdmin._normalize_hhmm()` [私有]
- 位置：第 65-66 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `CalendarAdmin._normalize_date()` [私有]
- 位置：第 69-70 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `CalendarAdmin._validate_day_type()` [私有]
- 位置：第 73-90 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `CalendarAdmin._normalize_yesno()` [私有]
- 位置：第 93-101 行
- 参数：value, field
- 返回类型：Name(id='str', ctx=Load())

### `CalendarAdmin._normalize_shift_window()` [私有]
- 位置：第 103-127 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `CalendarAdmin._build_work_calendar()` [私有]
- 位置：第 129-174 行
- 参数：无
- 返回类型：Name(id='WorkCalendar', ctx=Load())

### `CalendarAdmin._build_work_calendar_from_payload()` [私有]
- 位置：第 176-200 行
- 参数：calendar_payload
- 返回类型：Name(id='WorkCalendar', ctx=Load())

### `CalendarAdmin._build_operator_calendar()` [私有]
- 位置：第 202-252 行
- 参数：无
- 返回类型：Name(id='OperatorCalendar', ctx=Load())

### `CalendarAdmin._build_operator_calendar_from_payload()` [私有]
- 位置：第 254-280 行
- 参数：calendar_payload
- 返回类型：Name(id='OperatorCalendar', ctx=Load())

### `CalendarAdmin.list_all()` [公开]
- 位置：第 285-286 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（8 处）：
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/scheduler_excel_calendar.py:58` [Route] `for c in cal_svc.list_all():`
  - `web/routes/scheduler_excel_calendar.py:476` [Route] `rows = cal_svc.list_all()`
  - `core/services/scheduler/calendar_service.py:60` [Service] `return self._admin.list_all()`
  - `core/services/scheduler/config_presets.py:119` [Service] `keys = existing_keys if existing_keys is not None else {c.config_key for c in sv`
  - `core/services/scheduler/config_presets.py:157` [Service] `items = svc.repo.list_all()`
  - `core/services/scheduler/config_service.py:163` [Service] `existing = {c.config_key for c in self.repo.list_all()}`
  - `core/services/system/system_config_service.py:116` [Service] `existing = {c.config_key for c in self.repo.list_all()}`

### `CalendarAdmin.list_range()` [公开]
- 位置：第 288-291 行
- 参数：start_date, end_date
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/calendar_service.py:63` [Service] `return self._admin.list_range(start_date, end_date)`
- **被调用者**（1 个）：`self._normalize_date`

### `CalendarAdmin.upsert()` [公开]
- 位置：第 293-318 行
- 参数：date_value, day_type, shift_hours, shift_start, shift_end, efficiency, allow_normal, allow_urgent, remark
- 返回类型：Name(id='WorkCalendar', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_calendar_pages.py:52` [Route] `cal_svc.upsert(`
  - `core/services/scheduler/calendar_service.py:77` [Service] `row = self._admin.upsert(`
- **被调用者**（3 个）：`self._build_work_calendar`, `transaction`, `cal.to_dict`

### `CalendarAdmin.upsert_no_tx()` [公开]
- 位置：第 320-329 行
- 参数：calendar_payload
- 返回类型：Name(id='WorkCalendar', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_excel_calendar.py:378` [Route] `cal_svc.upsert_no_tx(`
  - `core/services/scheduler/calendar_service.py:92` [Service] `row = self._admin.upsert_no_tx(calendar_payload)`
- **被调用者**（3 个）：`self._build_work_calendar_from_payload`, `upsert`, `c.to_dict`

### `CalendarAdmin.delete()` [公开]
- 位置：第 331-334 行
- 参数：date_value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._normalize_date`, `transaction`

### `CalendarAdmin.delete_all_no_tx()` [公开]
- 位置：第 336-337 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `web/routes/process_excel_routes.py:209` [Route] `part_svc.delete_all_no_tx()`
  - `web/routes/scheduler_excel_calendar.py:355` [Route] `cal_svc.delete_all_no_tx()`
  - `core/services/scheduler/batch_excel_import.py:30` [Service] `svc.delete_all_no_tx()`
  - `core/services/scheduler/calendar_service.py:101` [Service] `self._admin.delete_all_no_tx()`
- **被调用者**（1 个）：`delete_all`

### `CalendarAdmin.get_operator_calendar()` [公开]
- 位置：第 342-347 行
- 参数：operator_id, date_value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/calendar_service.py:108` [Service] `return self._admin.get_operator_calendar(operator_id, date_value)`
- **被调用者**（4 个）：`self._normalize_text`, `self._normalize_date`, `get`, `ValidationError`

### `CalendarAdmin.list_operator_calendar()` [公开]
- 位置：第 349-353 行
- 参数：operator_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/personnel_calendar_pages.py:23` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `core/services/scheduler/calendar_service.py:111` [Service] `return self._admin.list_operator_calendar(operator_id)`
- **被调用者**（3 个）：`self._normalize_text`, `list_by_operator`, `ValidationError`

### `CalendarAdmin.list_operator_calendar_all()` [公开]
- 位置：第 355-356 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `web/routes/personnel_excel_operator_calendar.py:53` [Route] `for c in cal_svc.list_operator_calendar_all():`
  - `web/routes/personnel_excel_operator_calendar.py:138` [Route] `for c in cal_svc.list_operator_calendar_all():`
  - `web/routes/personnel_excel_operator_calendar.py:239` [Route] `for c in cal_svc.list_operator_calendar_all():`
  - `web/routes/personnel_excel_operator_calendar.py:402` [Route] `rows = cal_svc.list_operator_calendar_all()`
  - `core/services/scheduler/calendar_service.py:114` [Service] `return self._admin.list_operator_calendar_all()`
  - `core/services/scheduler/calendar_service.py:169` [Service] `set(existing_ids or set()) if existing_ids is not None else {f"{c.operator_id}|{`
- **被调用者**（1 个）：`list_all`

### `CalendarAdmin.upsert_operator_calendar()` [公开]
- 位置：第 358-385 行
- 参数：operator_id, date_value, day_type, shift_hours, shift_start, shift_end, efficiency, allow_normal, allow_urgent, remark
- 返回类型：Name(id='OperatorCalendar', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/personnel_calendar_pages.py:71` [Route] `cal_svc.upsert_operator_calendar(`
  - `core/services/scheduler/calendar_service.py:129` [Service] `row = self._admin.upsert_operator_calendar(`
- **被调用者**（4 个）：`self._build_operator_calendar`, `transaction`, `upsert`, `cal.to_dict`

### `CalendarAdmin.upsert_operator_calendar_no_tx()` [公开]
- 位置：第 387-390 行
- 参数：calendar_payload
- 返回类型：Name(id='OperatorCalendar', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/calendar_service.py:145` [Service] `row = self._admin.upsert_operator_calendar_no_tx(calendar_payload)`
  - `core/services/scheduler/calendar_service.py:184` [Service] `self.upsert_operator_calendar_no_tx(`
- **被调用者**（3 个）：`self._build_operator_calendar_from_payload`, `upsert`, `c.to_dict`

### `CalendarAdmin.delete_operator_calendar()` [公开]
- 位置：第 392-398 行
- 参数：operator_id, date_value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/calendar_service.py:150` [Service] `self._admin.delete_operator_calendar(operator_id, date_value)`
- **被调用者**（5 个）：`self._normalize_text`, `self._normalize_date`, `ValidationError`, `transaction`, `delete`

### `CalendarAdmin.delete_operator_calendar_all_no_tx()` [公开]
- 位置：第 400-401 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `core/services/scheduler/calendar_service.py:154` [Service] `self._admin.delete_operator_calendar_all_no_tx()`
  - `core/services/scheduler/calendar_service.py:173` [Service] `self.delete_operator_calendar_all_no_tx()`
- **被调用者**（1 个）：`delete_all`

## core/services/scheduler/calendar_service.py（Service 层）

### `CalendarService.__init__()` [私有]
- 位置：第 24-29 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `CalendarService._normalize_date()` [私有]
- 位置：第 35-42 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `CalendarService._normalize_hhmm()` [私有]
- 位置：第 45-49 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `CalendarService.get()` [公开]
- 位置：第 54-57 行
- 参数：date_value
- 返回类型：Name(id='WorkCalendar', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_normalize_date`, `_default_for_date`

### `CalendarService.list_all()` [公开]
- 位置：第 59-60 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（9 处）：
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/scheduler_excel_calendar.py:58` [Route] `for c in cal_svc.list_all():`
  - `web/routes/scheduler_excel_calendar.py:476` [Route] `rows = cal_svc.list_all()`
  - `core/services/scheduler/calendar_admin.py:286` [Service] `return self.repo.list_all()`
  - `core/services/scheduler/calendar_admin.py:356` [Service] `return self.operator_calendar_repo.list_all()`
  - `core/services/scheduler/config_presets.py:119` [Service] `keys = existing_keys if existing_keys is not None else {c.config_key for c in sv`
  - `core/services/scheduler/config_presets.py:157` [Service] `items = svc.repo.list_all()`
  - `core/services/scheduler/config_service.py:163` [Service] `existing = {c.config_key for c in self.repo.list_all()}`
  - `core/services/system/system_config_service.py:116` [Service] `existing = {c.config_key for c in self.repo.list_all()}`

### `CalendarService.list_range()` [公开]
- 位置：第 62-63 行
- 参数：start_date, end_date
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/calendar_admin.py:291` [Service] `return self.repo.list_range(s, e)`

### `CalendarService.upsert()` [公开]
- 位置：第 65-89 行
- 参数：date_value, day_type, shift_hours, shift_start, shift_end, efficiency, allow_normal, allow_urgent, remark
- 返回类型：Name(id='WorkCalendar', ctx=Load())
- **调用者**（5 处）：
  - `web/routes/scheduler_calendar_pages.py:52` [Route] `cal_svc.upsert(`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:328` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:384` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:389` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.upsert_no_tx()` [公开]
- 位置：第 91-94 行
- 参数：calendar_payload
- 返回类型：Name(id='WorkCalendar', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_excel_calendar.py:378` [Route] `cal_svc.upsert_no_tx(`
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.delete()` [公开]
- 位置：第 96-98 行
- 参数：date_value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.delete_all_no_tx()` [公开]
- 位置：第 100-102 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（3 处）：
  - `web/routes/process_excel_routes.py:209` [Route] `part_svc.delete_all_no_tx()`
  - `web/routes/scheduler_excel_calendar.py:355` [Route] `cal_svc.delete_all_no_tx()`
  - `core/services/scheduler/batch_excel_import.py:30` [Service] `svc.delete_all_no_tx()`
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.get_operator_calendar()` [公开]
- 位置：第 107-108 行
- 参数：operator_id, date_value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）

### `CalendarService.list_operator_calendar()` [公开]
- 位置：第 110-111 行
- 参数：operator_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/personnel_calendar_pages.py:23` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`

### `CalendarService.list_operator_calendar_all()` [公开]
- 位置：第 113-114 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/personnel_excel_operator_calendar.py:53` [Route] `for c in cal_svc.list_operator_calendar_all():`
  - `web/routes/personnel_excel_operator_calendar.py:138` [Route] `for c in cal_svc.list_operator_calendar_all():`
  - `web/routes/personnel_excel_operator_calendar.py:239` [Route] `for c in cal_svc.list_operator_calendar_all():`
  - `web/routes/personnel_excel_operator_calendar.py:402` [Route] `rows = cal_svc.list_operator_calendar_all()`

### `CalendarService.upsert_operator_calendar()` [公开]
- 位置：第 116-142 行
- 参数：operator_id, date_value, day_type, shift_hours, shift_start, shift_end, efficiency, allow_normal, allow_urgent, remark
- 返回类型：Name(id='OperatorCalendar', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/personnel_calendar_pages.py:71` [Route] `cal_svc.upsert_operator_calendar(`
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.upsert_operator_calendar_no_tx()` [公开]
- 位置：第 144-147 行
- 参数：calendar_payload
- 返回类型：Name(id='OperatorCalendar', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.delete_operator_calendar()` [公开]
- 位置：第 149-151 行
- 参数：operator_id, date_value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.delete_operator_calendar_all_no_tx()` [公开]
- 位置：第 153-155 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`clear_policy_cache`

### `CalendarService.import_operator_calendar_from_preview_rows()` [公开]
- 位置：第 157-213 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/personnel_excel_operator_calendar.py:317` [Route] `import_stats = cal_svc.import_operator_calendar_from_preview_rows(`
- **被调用者**（11 个）：`list`, `execute_preview_rows_transactional`, `stats.to_dict`, `len`, `clear_policy_cache`, `set`, `self.delete_operator_calendar_all_no_tx`, `to_str_or_blank`, `self.upsert_operator_calendar_no_tx`, `get`, `self.list_operator_calendar_all`

### `CalendarService.policy_for_datetime()` [公开]
- 位置：第 215-216 行
- 参数：dt, operator_id
- 返回类型：Name(id='DayPolicy', ctx=Load())
- **调用者**（1 处）：
  - `core/services/report/calculations.py:61` [Service] `p = calendar.policy_for_datetime(datetime.combine(cur, datetime.min.time()))`

### `CalendarService.get_efficiency()` [公开]
- 位置：第 218-219 行
- 参数：dt, machine_id, operator_id
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（3 处）：
  - `core/algorithms/greedy/auto_assign.py:154` [Algorithm] `raw_eff = scheduler.calendar.get_efficiency(start, operator_id=_oid)`
  - `core/algorithms/greedy/scheduler.py:473` [Algorithm] `eff = float(self.calendar.get_efficiency(start, operator_id=operator_id) or 1.0)`
  - `core/algorithms/greedy/dispatch/sgs.py:265` [Algorithm] `eff = float(scheduler.calendar.get_efficiency(est_start, operator_id=operator_id`

### `CalendarService.adjust_to_working_time()` [公开]
- 位置：第 221-228 行
- 参数：dt, priority, machine_id, operator_id
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（13 处）：
  - `core/services/scheduler/calendar_engine.py:279` [Service] `return self.adjust_to_working_time(start, priority=priority, operator_id=operato`
  - `core/services/scheduler/calendar_engine.py:281` [Service] `cur = self.adjust_to_working_time(start, priority=priority, operator_id=operator`
  - `core/services/scheduler/calendar_engine.py:292` [Service] `cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_i`
  - `core/services/scheduler/calendar_engine.py:301` [Service] `cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_i`
  - `core/services/scheduler/calendar_engine.py:308` [Service] `cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_i`
  - `core/services/scheduler/calendar_engine.py:317` [Service] `cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_i`
  - `core/algorithms/greedy/auto_assign.py:146` [Algorithm] `earliest = scheduler.calendar.adjust_to_working_time(earliest, priority=priority`
  - `core/algorithms/greedy/auto_assign.py:187` [Algorithm] `earliest = scheduler.calendar.adjust_to_working_time(earliest, priority=priority`
  - `core/algorithms/greedy/scheduler.py:223` [Algorithm] `dt_ready = self.calendar.adjust_to_working_time(dt0, priority=p)`
  - `core/algorithms/greedy/scheduler.py:453` [Algorithm] `earliest = self.calendar.adjust_to_working_time(earliest, priority=priority, ope`
  - `core/algorithms/greedy/scheduler.py:508` [Algorithm] `earliest = self.calendar.adjust_to_working_time(earliest, priority=priority, ope`
  - `core/algorithms/greedy/dispatch/sgs.py:255` [Algorithm] `est_start = scheduler.calendar.adjust_to_working_time(est_start, priority=priori`
  - `core/algorithms/greedy/dispatch/sgs.py:262` [Algorithm] `est_start = scheduler.calendar.adjust_to_working_time(est_start, priority=priori`

### `CalendarService.add_working_hours()` [公开]
- 位置：第 230-238 行
- 参数：start, hours, priority, machine_id, operator_id
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（5 处）：
  - `core/algorithms/greedy/auto_assign.py:172` [Algorithm] `end = scheduler.calendar.add_working_hours(earliest, total_hours, priority=prior`
  - `core/algorithms/greedy/auto_assign.py:191` [Algorithm] `end = scheduler.calendar.add_working_hours(earliest, total_hours, priority=prior`
  - `core/algorithms/greedy/scheduler.py:490` [Algorithm] `end = self.calendar.add_working_hours(earliest, total_hours, priority=priority, `
  - `core/algorithms/greedy/scheduler.py:510` [Algorithm] `end = self.calendar.add_working_hours(earliest, total_hours, priority=priority, `
  - `core/algorithms/greedy/dispatch/sgs.py:273` [Algorithm] `est_end = scheduler.calendar.add_working_hours(`

### `CalendarService.add_calendar_days()` [公开]
- 位置：第 240-241 行
- 参数：start, days, machine_id, operator_id
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（4 处）：
  - `core/algorithms/greedy/external_groups.py:46` [Algorithm] `end = scheduler.calendar.add_calendar_days(start, total_days_f)`
  - `core/algorithms/greedy/external_groups.py:85` [Algorithm] `end = scheduler.calendar.add_calendar_days(start, ext_days_f)`
  - `core/algorithms/greedy/dispatch/sgs.py:159` [Algorithm] `est_end = scheduler.calendar.add_calendar_days(est_start, total_days_f)`
  - `core/algorithms/greedy/dispatch/sgs.py:175` [Algorithm] `est_end = scheduler.calendar.add_calendar_days(est_start, ext_days_f)`

## core/services/scheduler/resource_dispatch_excel.py（Service 层）

### `_auto_width()` [私有]
- 位置：第 12-23 行
- 参数：ws
- 返回类型：Constant(value=None, kind=None)

### `_append_row()` [私有]
- 位置：第 26-27 行
- 参数：ws, values
- 返回类型：Constant(value=None, kind=None)

### `_write_table()` [私有]
- 位置：第 30-41 行
- 参数：ws, headers, rows
- 返回类型：Constant(value=None, kind=None)

### `_detail_headers()` [私有]
- 位置：第 44-65 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_first_present()` [私有]
- 位置：第 68-73 行
- 参数：row
- 返回类型：Name(id='Any', ctx=Load())

### `_yes_no_label()` [私有]
- 位置：第 76-77 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_build_detail_row()` [私有]
- 位置：第 80-102 行
- 参数：row
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_detail_table_rows()` [私有]
- 位置：第 105-106 行
- 参数：detail_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_calendar_table_rows()` [私有]
- 位置：第 109-117 行
- 参数：calendar_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_summary_pairs()` [私有]
- 位置：第 120-135 行
- 参数：filters, summary
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_write_summary_sheet()` [私有]
- 位置：第 138-147 行
- 参数：wb, filters, summary
- 返回类型：Constant(value=None, kind=None)

### `_write_calendar_sheet()` [私有]
- 位置：第 150-152 行
- 参数：wb, title, headers, rows
- 返回类型：Constant(value=None, kind=None)

### `_write_detail_sheet()` [私有]
- 位置：第 155-157 行
- 参数：wb, title, rows
- 返回类型：Constant(value=None, kind=None)

### `_write_team_scope_sheets()` [私有]
- 位置：第 160-177 行
- 参数：wb, payload
- 返回类型：Constant(value=None, kind=None)

### `_write_resource_scope_sheets()` [私有]
- 位置：第 180-187 行
- 参数：wb, payload
- 返回类型：Constant(value=None, kind=None)

### `build_resource_dispatch_workbook()` [公开]
- 位置：第 190-207 行
- 参数：payload
- 返回类型：Name(id='BytesIO', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/resource_dispatch_service.py:305` [Service] `buf = build_resource_dispatch_workbook(payload)`
- **被调用者**（11 个）：`Workbook`, `wb.remove`, `_write_summary_sheet`, `BytesIO`, `wb.save`, `buf.seek`, `payload.get`, `str`, `_write_team_scope_sheets`, `_write_resource_scope_sheets`, `filters.get`

## validate_dist_exe.py（Other 层）

### `_is_port_open()` [私有]
- 位置：第 33-38 行
- 参数：host, port
- 返回类型：Name(id='bool', ctx=Load())

### `_http_get()` [私有]
- 位置：第 41-47 行
- 参数：url, timeout
- 返回类型：Name(id='int', ctx=Load())

### `_http_get_text()` [私有]
- 位置：第 50-53 行
- 参数：url, timeout
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_db_path()` [私有]
- 位置：第 56-60 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())

### `_runtime_contract_paths()` [私有]
- 位置：第 63-68 行
- 参数：log_dir
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_read_port_file()` [私有]
- 位置：第 71-72 行
- 参数：path
- 返回类型：Name(id='int', ctx=Load())

### `_read_host_file()` [私有]
- 位置：第 75-76 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())

### `_read_db_file()` [私有]
- 位置：第 79-80 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())

### `_read_runtime_contract()` [私有]
- 位置：第 83-95 行
- 参数：log_dir
- 返回类型：BinOp(left=Subscript(value=Name(id='tuple', ctx=Load()), sli

### `_clear_runtime_contract_files()` [私有]
- 位置：第 98-109 行
- 参数：log_dir
- 返回类型：Constant(value=None, kind=None)

### `_assert_process_running()` [私有]
- 位置：第 112-115 行
- 参数：p, context
- 返回类型：Constant(value=None, kind=None)

### `_wait_for_runtime_contract()` [私有]
- 位置：第 118-126 行
- 参数：log_dir, p, timeout_s
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_wait_port_open()` [私有]
- 位置：第 129-136 行
- 参数：host, port, p, timeout_s
- 返回类型：Constant(value=None, kind=None)

### `_assert_health()` [私有]
- 位置：第 139-152 行
- 参数：base_url, timeout
- 返回类型：Name(id='dict', ctx=Load())

### `_assert_runtime_db_path()` [私有]
- 位置：第 155-162 行
- 参数：db_path
- 返回类型：Constant(value=None, kind=None)

### `main()` [公开]
- 位置：第 165-237 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（19 个）：`abspath`, `print`, `dirname`, `join`, `subprocess.Popen`, `len`, `exists`, `_clear_runtime_contract_files`, `_wait_for_runtime_contract`, `_assert_runtime_db_path`, `_wait_port_open`, `_assert_process_running`, `_assert_health`, `getattr`, `_http_get`

## web/bootstrap/factory.py（Other 层）

### `_apply_runtime_config()` [私有]
- 位置：第 42-49 行
- 参数：app
- 返回类型：Constant(value=None, kind=None)

### `_should_register_exit_backup()` [私有]
- 位置：第 52-57 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `_is_exit_backup_enabled()` [私有]
- 位置：第 60-78 行
- 参数：bm
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_run_exit_backup()` [私有]
- 位置：第 81-97 行
- 参数：manager
- 返回类型：Name(id='bool', ctx=Load())

### `_default_anchor_file()` [私有]
- 位置：第 100-102 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `create_app_core()` [公开]
- 位置：第 105-284 行
- 参数：无
- 返回类型：Name(id='Flask', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（49 个）：`lower`, `runtime_base_dir`, `join`, `Flask`, `from_object`, `_apply_runtime_config`, `int`, `install_versioned_url_for`, `AppLogger`, `setLevel`, `init_ui_mode`, `dirname`, `os.makedirs`, `abspath`, `ensure_schema`

## web/bootstrap/launcher.py（Other 层）

### `pick_bind_host()` [公开]
- 位置：第 9-22 行
- 参数：raw_host
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`strip`, `ipaddress.ip_address`, `getattr`, `ValueError`, `logger.warning`

### `_can_bind()` [私有]
- 位置：第 25-40 行
- 参数：host0, port0
- 返回类型：Name(id='bool', ctx=Load())

### `pick_port()` [公开]
- 位置：第 43-81 行
- 参数：host, preferred
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`socket.socket`, `_can_bind`, `int`, `candidates.append`, `s.bind`, `s.getsockname`, `s.close`

### `_normalize_db_path_for_runtime()` [私有]
- 位置：第 84-88 行
- 参数：db_path
- 返回类型：Name(id='str', ctx=Load())

### `write_runtime_host_port_files()` [公开]
- 位置：第 91-146 行
- 参数：runtime_dir, cfg_log_dir, host, port, db_path
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`join`, `os.makedirs`, `_normalize_db_path_for_runtime`, `open`, `f.write`, `strip`, `logger.info`, `str`, `abspath`, `int`, `f2.write`, `f3.write`, `f4.write`

## web/bootstrap/runtime_probe.py（Other 层）

### `_runtime_log_paths()` [私有]
- 位置：第 12-17 行
- 参数：runtime_dir
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_runtime_db_path_file()` [私有]
- 位置：第 20-22 行
- 参数：runtime_dir
- 返回类型：Name(id='str', ctx=Load())

### `_read_text()` [私有]
- 位置：第 25-27 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_db_path()` [私有]
- 位置：第 30-34 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())

### `build_base_url()` [公开]
- 位置：第 37-41 行
- 参数：host, port
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`strip`, `int`, `str`

### `read_runtime_host_port()` [公开]
- 位置：第 44-55 行
- 参数：runtime_dir
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`_runtime_log_paths`, `int`, `exists`, `_read_text`

### `read_runtime_db_path()` [公开]
- 位置：第 58-68 行
- 参数：runtime_dir
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`_runtime_db_path_file`, `exists`, `_normalize_db_path`, `_read_text`

### `delete_stale_runtime_files()` [公开]
- 位置：第 71-80 行
- 参数：runtime_dir
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`_runtime_log_paths`, `_runtime_db_path_file`, `os.remove`

### `probe_health()` [公开]
- 位置：第 83-101 行
- 参数：base_url, timeout
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`Request`, `rstrip`, `int`, `urlopen`, `json.loads`, `payload.get`, `str`, `decode`, `resp.read`

### `_build_endpoint_result()` [私有]
- 位置：第 104-111 行
- 参数：host, port, source, health
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `resolve_healthy_endpoint()` [公开]
- 位置：第 114-139 行
- 参数：runtime_dir, preferred_host, preferred_port, timeout
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`read_runtime_host_port`, `probe_health`, `_build_endpoint_result`, `build_base_url`, `int`, `strip`, `str`

### `wait_for_healthy_runtime_endpoint()` [公开]
- 位置：第 142-161 行
- 参数：runtime_dir, timeout_s, interval_s
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`max`, `TimeoutError`, `time.time`, `float`, `read_runtime_host_port`, `time.sleep`, `int`, `probe_health`, `build_base_url`, `_build_endpoint_result`, `join`, `str`

## web/error_handlers.py（Other 层）

### `_wants_json()` [私有]
- 位置：第 12-21 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `register_error_handlers()` [公开]
- 位置：第 24-63 行
- 参数：app
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`app.errorhandler`, `warning`, `_wants_json`, `error_response`, `error`, `render_template`, `e.to_dict`, `traceback.format_exc`

## web/routes/equipment_excel_links.py（Route 层）

### `_build_existing_machine_link_page_data()` [私有]
- 位置：第 27-51 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_operator_machine_reference_snapshot()` [私有]
- 位置：第 54-60 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_render_excel_link_page()` [私有]
- 位置：第 63-85 行
- 参数：无
- 返回类型：无注解

### `excel_link_page()` [公开]
- 位置：第 89-98 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `_build_existing_machine_link_page_data`, `_render_excel_link_page`

### `excel_link_preview()` [公开]
- 位置：第 102-153 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `OperatorMachineService`, `link_svc.preview_import_links`, `_build_existing_machine_link_page_data`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_link_page`, `ValidationError`, `dict`, `normalized_rows.append`

### `excel_link_confirm()` [公开]
- 位置：第 157-234 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（28 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `_build_existing_machine_link_page_data`, `OperatorMachineService`, `link_svc.preview_import_links`, `link_svc.apply_import_links`, `int`, `log_excel_import`, `flash_import_result`, `redirect`, `ValidationError`, `json.loads`

### `excel_link_template()` [公开]
- 位置：第 238-285 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_link_export()` [公开]
- 位置：第 289-319 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.get`, `time.time`, `OperatorMachineQueryService`, `q.list_simple_rows`, `rows.sort`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`, `str`, `r.get`

## web/routes/equipment_excel_machines.py（Route 层）

### `_validate_machine_excel_row()` [私有]
- 位置：第 33-47 行
- 参数：row
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_normalize_machine_status_for_excel()` [私有]
- 位置：第 50-57 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_resolve_op_type()` [私有]
- 位置：第 60-74 行
- 参数：value, op_type_svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_parse_preview_rows_json()` [私有]
- 位置：第 77-84 行
- 参数：raw_rows_json
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_extract_error_rows()` [私有]
- 位置：第 87-88 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_format_error_sample()` [私有]
- 位置：第 91-93 行
- 参数：error_rows
- 返回类型：Name(id='str', ctx=Load())

### `_machine_reference_snapshot()` [私有]
- 位置：第 96-114 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_render_excel_machine_page()` [私有]
- 位置：第 117-139 行
- 参数：无
- 返回类型：无注解

### `excel_machine_page()` [公开]
- 位置：第 143-153 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `MachineService`, `svc.build_existing_for_excel`, `_render_excel_machine_page`, `getattr`

### `excel_machine_preview()` [公开]
- 位置：第 157-244 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（32 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `OpTypeService`, `ResourceTeamService`, `MachineService`, `m_svc.build_existing_for_excel`, `ExcelService`, `svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`

### `excel_machine_confirm()` [公开]
- 位置：第 248-359 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（41 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `_parse_preview_rows_json`, `_ensure_unique_ids`, `OpTypeService`, `ResourceTeamService`, `MachineService`, `m_svc.build_existing_for_excel`, `ExcelService`, `excel_svc.preview_import`, `_extract_error_rows`, `MachineExcelImportService`

### `excel_machine_template()` [公开]
- 位置：第 363-409 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_machine_export()` [公开]
- 位置：第 413-442 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `MachineService`, `m_svc.list_for_export`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`, `r.get`

## web/routes/excel_demo.py（Route 层）

### `_fetch_existing_operators()` [私有]
- 位置：第 28-30 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_parse_mode()` [私有]
- 位置：第 33-34 行
- 参数：value
- 返回类型：Name(id='ImportMode', ctx=Load())

### `_render_demo_page()` [私有]
- 位置：第 37-58 行
- 参数：无
- 返回类型：无注解

### `_validate_operator_row()` [私有]
- 位置：第 61-74 行
- 参数：row
- 返回类型：Name(id='str', ctx=Load())

### `index()` [公开]
- 位置：第 78-87 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `_fetch_existing_operators`, `_render_demo_page`

### `preview()` [公开]
- 位置：第 91-170 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（29 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `file.read`, `io.BytesIO`, `tmp.seek`, `OpenpyxlBackend`, `_fetch_existing_operators`, `ExcelService`, `svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_demo_page`

### `confirm()` [公开]
- 位置：第 174-260 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（31 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `_fetch_existing_operators`, `OpenpyxlBackend`, `ExcelService`, `svc.preview_import`, `OperatorExcelImportService`, `import_svc.apply_preview_rows`, `int`, `log_excel_import`, `flash_import_result`, `redirect`

### `download_template()` [公开]
- 位置：第 264-314 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `len`

## web/routes/excel_utils.py（Route 层）

### `parse_import_mode()` [公开]
- 位置：第 17-25 行
- 参数：value
- 返回类型：Name(id='ImportMode', ctx=Load())
- **调用者**（5 处）：
  - `web/routes/equipment_bp.py:24` [Route] `return parse_import_mode(value)`
  - `web/routes/excel_demo.py:34` [Route] `return parse_import_mode(value)`
  - `web/routes/personnel_bp.py:29` [Route] `return parse_import_mode(value)`
  - `web/routes/process_bp.py:41` [Route] `return parse_import_mode(value)`
  - `web/routes/scheduler_utils.py:12` [Route] `return parse_import_mode(value)`
- **被调用者**（2 个）：`ImportMode`, `ValidationError`

### `build_preview_baseline_token()` [公开]
- 位置：第 28-47 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（12 处）：
  - `web/routes/equipment_excel_links.py:128` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/equipment_excel_machines.py:219` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/excel_demo.py:150` [Route] `preview_baseline = build_preview_baseline_token(existing_data=existing, mode=mod`
  - `web/routes/personnel_excel_links.py:115` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/personnel_excel_operators.py:147` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/personnel_excel_operator_calendar.py:170` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/process_excel_op_types.py:149` [Route] `preview_baseline = build_preview_baseline_token(existing_data=existing, mode=mod`
  - `web/routes/process_excel_part_operation_hours.py:258` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/process_excel_routes.py:103` [Route] `preview_baseline = build_preview_baseline_token(existing_data=existing, mode=mod`
  - `web/routes/process_excel_suppliers.py:155` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/scheduler_excel_batches.py:222` [Route] `preview_baseline = build_preview_baseline_token(`
  - `web/routes/scheduler_excel_calendar.py:201` [Route] `preview_baseline = build_preview_baseline_token(`
- **被调用者**（7 个）：`json.dumps`, `hexdigest`, `strip`, `hashlib.sha256`, `str`, `raw.encode`, `getattr`

### `preview_baseline_matches()` [公开]
- 位置：第 50-73 行
- 参数：token
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（12 处）：
  - `web/routes/equipment_excel_links.py:176` [Route] `if not preview_baseline_matches(`
  - `web/routes/equipment_excel_machines.py:266` [Route] `if not preview_baseline_matches(`
  - `web/routes/excel_demo.py:194` [Route] `if not preview_baseline_matches(preview_baseline, existing_data=existing, mode=m`
  - `web/routes/personnel_excel_links.py:164` [Route] `if not preview_baseline_matches(`
  - `web/routes/personnel_excel_operators.py:200` [Route] `if not preview_baseline_matches(`
  - `web/routes/personnel_excel_operator_calendar.py:254` [Route] `if not preview_baseline_matches(`
  - `web/routes/process_excel_op_types.py:195` [Route] `if not preview_baseline_matches(preview_baseline, existing_data=existing, mode=m`
  - `web/routes/process_excel_part_operation_hours.py:314` [Route] `if not preview_baseline_matches(`
  - `web/routes/process_excel_routes.py:149` [Route] `if not preview_baseline_matches(preview_baseline, existing_data=existing, mode=m`
  - `web/routes/process_excel_suppliers.py:207` [Route] `if not preview_baseline_matches(`
  - `web/routes/scheduler_excel_batches.py:276` [Route] `if not preview_baseline_matches(`
  - `web/routes/scheduler_excel_calendar.py:251` [Route] `if not preview_baseline_matches(`
- **被调用者**（3 个）：`strip`, `build_preview_baseline_token`, `hmac.compare_digest`

### `flash_import_result()` [公开]
- 位置：第 76-104 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（12 处）：
  - `web/routes/equipment_excel_links.py:227` [Route] `flash_import_result(`
  - `web/routes/equipment_excel_machines.py:352` [Route] `flash_import_result(`
  - `web/routes/excel_demo.py:253` [Route] `flash_import_result(`
  - `web/routes/personnel_excel_links.py:215` [Route] `flash_import_result(`
  - `web/routes/personnel_excel_operators.py:279` [Route] `flash_import_result(`
  - `web/routes/personnel_excel_operator_calendar.py:338` [Route] `flash_import_result(`
  - `web/routes/process_excel_op_types.py:257` [Route] `flash_import_result(`
  - `web/routes/process_excel_part_operation_hours.py:377` [Route] `flash_import_result(`
  - `web/routes/process_excel_routes.py:264` [Route] `flash_import_result(`
  - `web/routes/process_excel_suppliers.py:295` [Route] `flash_import_result(`
  - `web/routes/scheduler_excel_batches.py:347` [Route] `flash_import_result(`
  - `web/routes/scheduler_excel_calendar.py:412` [Route] `flash_import_result(`
- **被调用者**（5 个）：`flash`, `int`, `join`, `item.get`, `list`

### `ensure_unique_ids()` [公开]
- 位置：第 107-130 行
- 参数：rows, id_column
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `web/routes/equipment_bp.py:32` [Route] `ensure_unique_ids(rows, id_column=id_column)`
  - `web/routes/personnel_bp.py:37` [Route] `ensure_unique_ids(rows, id_column=id_column)`
  - `web/routes/process_bp.py:45` [Route] `ensure_unique_ids(rows, id_column=id_column)`
  - `web/routes/scheduler_utils.py:16` [Route] `ensure_unique_ids(rows, id_column=id_column)`
- **被调用者**（13 个）：`set`, `r.get`, `seen.add`, `join`, `ValidationError`, `isinstance`, `v.is_integer`, `strip`, `dup.add`, `list`, `str`, `sorted`, `int`

### `read_uploaded_xlsx()` [公开]
- 位置：第 133-160 行
- 参数：file_storage
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/equipment_bp.py:28` [Route] `return read_uploaded_xlsx(file_storage)`
  - `web/routes/personnel_bp.py:33` [Route] `return read_uploaded_xlsx(file_storage)`
  - `web/routes/process_bp.py:49` [Route] `return read_uploaded_xlsx(file_storage)`
  - `web/routes/scheduler_utils.py:20` [Route] `return read_uploaded_xlsx(file_storage)`
- **被调用者**（11 个）：`file_storage.read`, `int`, `tempfile.mkstemp`, `AppError`, `get_excel_backend`, `backend.read`, `get`, `len`, `os.fdopen`, `f.write`, `os.remove`

## web/routes/personnel_excel_links.py（Route 层）

### `_build_existing_operator_link_page_data()` [私有]
- 位置：第 27-51 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_operator_machine_reference_snapshot()` [私有]
- 位置：第 54-60 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_render_excel_link_page()` [私有]
- 位置：第 63-85 行
- 参数：无
- 返回类型：无注解

### `excel_link_page()` [公开]
- 位置：第 89-99 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `_build_existing_operator_link_page_data`, `_render_excel_link_page`

### `excel_link_preview()` [公开]
- 位置：第 103-140 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（16 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `OperatorMachineService`, `link_svc.preview_import_links`, `_build_existing_operator_link_page_data`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_link_page`, `ValidationError`, `getattr`, `_operator_machine_reference_snapshot`

### `excel_link_confirm()` [公开]
- 位置：第 144-222 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（28 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `_build_existing_operator_link_page_data`, `OperatorMachineService`, `link_svc.preview_import_links`, `link_svc.apply_import_links`, `int`, `log_excel_import`, `flash_import_result`, `redirect`, `ValidationError`, `json.loads`

### `excel_link_template()` [公开]
- 位置：第 226-273 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_link_export()` [公开]
- 位置：第 277-307 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.get`, `time.time`, `OperatorMachineQueryService`, `q.list_simple_rows`, `rows.sort`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`, `str`, `r.get`

## web/routes/personnel_excel_operator_calendar.py（Route 层）

### `_list_operator_ids()` [私有]
- 位置：第 37-39 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_operator_calendar_baseline_extra_state()` [私有]
- 位置：第 42-46 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `excel_operator_calendar_page()` [公开]
- 位置：第 50-81 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.get`, `CalendarService`, `cal_svc.list_operator_calendar_all`, `render_template`, `existing_list.append`, `getattr`, `url_for`, `_normalize_operator_calendar_day_type`

### `excel_operator_calendar_preview()` [公开]
- 位置：第 85-204 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（39 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `ConfigService`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `CalendarService`, `cal_svc.list_operator_calendar_all`, `get_operator_calendar_row_validate_and_normalize`, `ExcelService`, `excel_svc.preview_import`, `_list_operator_ids`, `build_preview_baseline_token`, `int`

### `excel_operator_calendar_confirm()` [公开]
- 位置：第 208-345 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（40 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `ConfigService`, `_ensure_unique_ids`, `CalendarService`, `cal_svc.list_operator_calendar_all`, `_list_operator_ids`, `get_operator_calendar_row_validate_and_normalize`, `ExcelService`, `excel_svc.preview_import`, `cal_svc.import_operator_calendar_from_preview_rows`, `int`

### `excel_operator_calendar_template()` [公开]
- 位置：第 349-395 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_operator_calendar_export()` [公开]
- 位置：第 399-442 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`bp.get`, `time.time`, `CalendarService`, `cal_svc.list_operator_calendar_all`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`, `_normalize_operator_calendar_day_type`, `_normalize_yesno`

## web/routes/personnel_excel_operators.py（Route 层）

### `_validate_operator_excel_row()` [私有]
- 位置：第 26-38 行
- 参数：row
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_render_excel_operator_page()` [私有]
- 位置：第 46-68 行
- 参数：无
- 返回类型：无注解

### `_operator_team_snapshot()` [私有]
- 位置：第 71-81 行
- 参数：team_svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `excel_operator_page()` [公开]
- 位置：第 85-96 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `OperatorService`, `op_svc.build_existing_for_excel`, `_render_excel_operator_page`, `getattr`

### `excel_operator_preview()` [公开]
- 位置：第 100-172 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（27 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `OperatorService`, `ResourceTeamService`, `op_svc.build_existing_for_excel`, `ExcelService`, `svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_operator_page`

### `excel_operator_confirm()` [公开]
- 位置：第 176-286 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（38 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `_ensure_unique_ids`, `OperatorService`, `ResourceTeamService`, `op_svc.build_existing_for_excel`, `ExcelService`, `excel_svc.preview_import`, `OperatorExcelImportService`, `import_svc.apply_preview_rows`, `int`, `log_excel_import`

### `excel_operator_template()` [公开]
- 位置：第 290-338 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_operator_export()` [公开]
- 位置：第 342-372 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.get`, `time.time`, `build_existing_for_excel`, `list`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `existing.values`, `OperatorService`, `template_def.get`, `getattr`, `len`, `r.get`

## web/routes/process_excel_op_types.py（Route 层）

### `_render_excel_op_type_page()` [私有]
- 位置：第 30-52 行
- 参数：无
- 返回类型：无注解

### `_normalize_op_type_category()` [私有]
- 位置：第 55-56 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_op_type_name()` [私有]
- 位置：第 59-60 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_build_op_type_row_validator()` [私有]
- 位置：第 63-108 行
- 参数：无
- 返回类型：无注解

### `excel_op_type_page()` [公开]
- 位置：第 112-122 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `OpTypeService`, `svc.build_existing_for_excel`, `_render_excel_op_type_page`, `getattr`

### `excel_op_type_preview()` [公开]
- 位置：第 126-169 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（19 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `OpTypeService`, `svc.build_existing_for_excel`, `_build_op_type_row_validator`, `ExcelService`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_op_type_page`

### `excel_op_type_confirm()` [公开]
- 位置：第 173-264 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（34 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `_ensure_unique_ids`, `OpTypeService`, `op_type_svc.build_existing_for_excel`, `_build_op_type_row_validator`, `ExcelService`, `excel_svc.preview_import`, `OpTypeExcelImportService`, `import_svc.apply_preview_rows`, `int`, `list`

### `excel_op_type_template()` [公开]
- 位置：第 268-315 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_op_type_export()` [公开]
- 位置：第 319-348 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `OpTypeService`, `svc.list`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`

## web/routes/process_excel_part_operation_hours.py（Route 层）

### `_part_op_hours_mode_options()` [私有]
- 位置：第 37-38 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_parse_seq()` [私有]
- 位置：第 41-61 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_build_existing_internal()` [私有]
- 位置：第 64-96 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_normalize_rows()` [私有]
- 位置：第 99-113 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_build_validator()` [私有]
- 位置：第 116-148 行
- 参数：meta_all
- 返回类型：无注解

### `_build_part_op_hours_extra_state()` [私有]
- 位置：第 151-160 行
- 参数：meta_all
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_existing_for_append()` [私有]
- 位置：第 163-175 行
- 参数：existing_internal
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_rewrite_append_preview_rows()` [私有]
- 位置：第 178-188 行
- 参数：preview_rows, mode
- 返回类型：Constant(value=None, kind=None)

### `_render_excel_part_op_hours_page()` [私有]
- 位置：第 191-214 行
- 参数：无
- 返回类型：无注解

### `excel_part_op_hours_page()` [公开]
- 位置：第 218-227 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `_build_existing_internal`, `_render_excel_part_op_hours_page`

### `excel_part_op_hours_preview()` [公开]
- 位置：第 231-283 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（22 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_normalize_rows`, `_ensure_unique_ids`, `_build_existing_internal`, `_build_validator`, `ExcelService`, `excel_svc.preview_import`, `_rewrite_append_preview_rows`, `build_preview_baseline_token`, `int`, `log_excel_import`

### `excel_part_op_hours_confirm()` [公开]
- 位置：第 287-384 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（34 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `_ensure_unique_ids`, `_build_existing_internal`, `_build_validator`, `ExcelService`, `excel_svc.preview_import`, `_rewrite_append_preview_rows`, `PartOperationHoursExcelImportService`, `import_svc.apply_preview_rows`, `int`, `log_excel_import`

### `excel_part_op_hours_template()` [公开]
- 位置：第 388-435 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_part_op_hours_export()` [公开]
- 位置：第 439-468 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `PartOperationQueryService`, `q.list_internal_active_hours`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`, `float`

## web/routes/process_excel_part_operations.py（Route 层）

### `excel_part_ops_page()` [公开]
- 位置：第 21-26 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `render_template`, `url_for`

### `excel_part_ops_export()` [公开]
- 位置：第 30-73 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.get`, `time.time`, `PartOperationQueryService`, `q.list_all_active_with_details`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `len`

## web/routes/process_excel_routes.py（Route 层）

### `_render_excel_routes_page()` [私有]
- 位置：第 29-51 行
- 参数：无
- 返回类型：无注解

### `excel_routes_page()` [公开]
- 位置：第 55-65 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `PartService`, `svc.build_existing_for_excel_routes`, `_render_excel_routes_page`, `getattr`

### `excel_routes_preview()` [公开]
- 位置：第 69-123 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（23 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `PartService`, `part_svc.build_existing_for_excel_routes`, `ExcelService`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_routes_page`, `ValidationError`

### `excel_routes_confirm()` [公开]
- 位置：第 127-271 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（38 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `_ensure_unique_ids`, `PartService`, `part_svc.build_existing_for_excel_routes`, `ExcelService`, `excel_svc.preview_import`, `TransactionManager`, `int`, `log_excel_import`, `flash_import_result`, `redirect`

### `excel_routes_template()` [公开]
- 位置：第 275-322 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_routes_export()` [公开]
- 位置：第 326-356 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `PartService`, `svc.list`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`

## web/routes/process_excel_suppliers.py（Route 层）

### `_render_excel_supplier_page()` [私有]
- 位置：第 30-52 行
- 参数：无
- 返回类型：无注解

### `_normalize_supplier_status()` [私有]
- 位置：第 55-56 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_resolve_op_type_name()` [私有]
- 位置：第 59-68 行
- 参数：value, op_type_svc
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_supplier_op_type_snapshot()` [私有]
- 位置：第 71-81 行
- 参数：op_type_svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `excel_supplier_page()` [公开]
- 位置：第 85-95 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `SupplierService`, `svc.build_existing_for_excel`, `_render_excel_supplier_page`, `getattr`

### `excel_supplier_preview()` [公开]
- 位置：第 99-180 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（27 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `SupplierService`, `svc.build_existing_for_excel`, `OpTypeService`, `ExcelService`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_supplier_page`

### `excel_supplier_confirm()` [公开]
- 位置：第 184-302 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（41 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `_ensure_unique_ids`, `SupplierService`, `OpTypeService`, `supplier_svc.build_existing_for_excel`, `ExcelService`, `excel_svc.preview_import`, `SupplierExcelImportService`, `import_svc.apply_preview_rows`, `int`, `log_excel_import`

### `excel_supplier_template()` [公开]
- 位置：第 306-353 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_supplier_export()` [公开]
- 位置：第 357-388 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.get`, `time.time`, `list_for_export_rows`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `SupplierService`, `getattr`, `len`

## web/routes/scheduler_excel_batches.py（Route 层）

### `_parse_preview_rows_json()` [私有]
- 位置：第 37-44 行
- 参数：raw_rows_json
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_sorted_existing_list()` [私有]
- 位置：第 47-50 行
- 参数：existing_preview_data
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_parse_auto_generate_ops()` [私有]
- 位置：第 53-54 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())

### `_build_existing_preview_data()` [私有]
- 位置：第 57-72 行
- 参数：batch_svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_parts_cache()` [私有]
- 位置：第 75-77 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_template_ops_snapshot()` [私有]
- 位置：第 80-85 行
- 参数：conn, rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_batch_baseline_extra_state()` [私有]
- 位置：第 88-103 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_render_excel_batches_page()` [私有]
- 位置：第 106-130 行
- 参数：无
- 返回类型：无注解

### `_extract_error_rows()` [私有]
- 位置：第 133-134 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_format_error_sample()` [私有]
- 位置：第 137-139 行
- 参数：error_rows
- 返回类型：Name(id='str', ctx=Load())

### `excel_batches_page()` [公开]
- 位置：第 143-166 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.get`, `BatchService`, `_render_excel_batches_page`, `getattr`, `svc.list`, `list`, `existing.values`

### `excel_batches_preview()` [公开]
- 位置：第 170-253 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（30 个）：`bp.post`, `time.time`, `_parse_mode`, `_parse_auto_generate_ops`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `BatchService`, `_build_parts_cache`, `get_batch_row_validate_and_normalize`, `ExcelService`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`

### `excel_batches_confirm()` [公开]
- 位置：第 257-355 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（36 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `_parse_auto_generate_ops`, `_parse_preview_rows_json`, `_ensure_unique_ids`, `BatchService`, `_build_existing_preview_data`, `_build_parts_cache`, `get_batch_row_validate_and_normalize`, `ExcelService`, `excel_svc.preview_import`, `_extract_error_rows`

### `excel_batches_template()` [公开]
- 位置：第 359-405 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_batches_export()` [公开]
- 位置：第 409-441 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `BatchService`, `svc.list`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`

## web/routes/scheduler_excel_calendar.py（Route 层）

### `_parse_preview_rows_json()` [私有]
- 位置：第 37-44 行
- 参数：raw_rows_json
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

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

### `_render_excel_calendar_page()` [私有]
- 位置：第 77-99 行
- 参数：无
- 返回类型：无注解

### `excel_calendar_page()` [公开]
- 位置：第 103-112 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `_build_existing_preview_data`, `_render_excel_calendar_page`

### `excel_calendar_preview()` [公开]
- 位置：第 116-226 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（32 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `ConfigService`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `_build_existing_preview_data`, `ExcelService`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_calendar_page`, `ValidationError`

### `excel_calendar_confirm()` [公开]
- 位置：第 230-419 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（44 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `ConfigService`, `_parse_preview_rows_json`, `_build_existing_preview_data`, `_ensure_unique_ids`, `ExcelService`, `excel_svc.preview_import`, `CalendarService`, `TransactionManager`, `int`, `log_excel_import`

### `excel_calendar_template()` [公开]
- 位置：第 423-469 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_calendar_export()` [公开]
- 位置：第 473-513 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`bp.get`, `time.time`, `CalendarService`, `cal_svc.list_all`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`, `_normalize_day_type`, `_normalize_yesno`

## web/routes/scheduler_week_plan.py（Route 层）

### `_get_int_arg()` [私有]
- 位置：第 19-26 行
- 参数：name, default
- 返回类型：Name(id='int', ctx=Load())

### `_parse_optional_checkbox_flag()` [私有]
- 位置：第 29-39 行
- 参数：name
- 返回类型：无注解

### `week_plan_page()` [公开]
- 位置：第 43-85 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（18 个）：`bp.get`, `_get_int_arg`, `strip`, `GanttService`, `svc.resolve_week_range`, `list_versions`, `svc.get_week_plan_rows`, `render_template`, `svc.get_latest_version_or_1`, `data.get`, `int`, `getattr`, `ScheduleHistoryQueryService`, `isoformat`, `len`

### `week_plan_export()` [公开]
- 位置：第 89-154 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（21 个）：`bp.get`, `time.time`, `_get_int_arg`, `strip`, `GanttService`, `svc.get_week_plan_rows`, `int`, `data.get`, `build_xlsx_bytes`, `log_excel_export`, `send_file`, `getattr`, `flash`, `redirect`, `exception`

### `simulate_schedule()` [公开]
- 位置：第 158-207 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（18 个）：`bp.post`, `getlist`, `_parse_optional_checkbox_flag`, `ScheduleService`, `get`, `flash`, `redirect`, `sch_svc.run_schedule`, `int`, `isoformat`, `url_for`, `getattr`, `result.get`, `summary.get`, `exception`

## web/routes/system_health.py（Route 层）

### `health()` [公开]
- 位置：第 15-26 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.get`, `current_app.response_class`, `str`, `isoformat`, `json.dumps`, `get`, `datetime.now`

## web/viewmodels/page_manuals_common.py（Other 层）

### `_card()` [私有]
- 位置：第 7-11 行
- 参数：title
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_section()` [私有]
- 位置：第 14-18 行
- 参数：title, body_md
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_topic()` [私有]
- 位置：第 21-38 行
- 参数：title, summary, full_manual_anchor, sections, related_manual_ids, help_card
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_expand_fragments()` [私有]
- 位置：第 111-115 行
- 参数：text
- 返回类型：Name(id='str', ctx=Load())

### `_build_full_manual_label()` [私有]
- 位置：第 118-130 行
- 参数：anchor
- 返回类型：Name(id='str', ctx=Load())

### `_clone_help_card()` [私有]
- 位置：第 133-140 行
- 参数：card
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_clone_sections()` [私有]
- 位置：第 143-150 行
- 参数：sections
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_clean_related_ids()` [私有]
- 位置：第 153-162 行
- 参数：items
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_apply_payload_overrides()` [私有]
- 位置：第 165-173 行
- 参数：payload, overrides
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `build_manual_payload_from_topic()` [公开]
- 位置：第 176-193 行
- 参数：manual_id, topic, overrides, include_sections
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`_apply_payload_overrides`, `strip`, `_build_full_manual_label`, `_clone_help_card`, `_clean_related_ids`, `_clone_sections`, `topic.get`, `list`, `str`

### `build_page_fallback_text_from_bundle()` [公开]
- 位置：第 196-211 行
- 参数：bundle
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`strip`, `current.get`, `lines.extend`, `join`, `item.get`

---
- 分析函数/方法数：399
- 找到调用关系：495 处
- 跨层边界风险：16 项
