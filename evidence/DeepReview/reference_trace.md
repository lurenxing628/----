# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ normalize_repair_notice() 返回 Optional，但 core/services/scheduler/config/config_service.py:286 的调用者未做 None 检查
- ⚠ active_preset_meta_parse_warning() 返回 Optional，但 core/services/scheduler/config/config_service.py:347 的调用者未做 None 检查
- ⚠ public_active_preset_reason() 返回 Optional，但 core/services/scheduler/config/config_service.py:685 的调用者未做 None 检查
- ⚠ ConfigPresetService.try_load_preset_snapshot_for_baseline() 返回 Optional，但 core/services/scheduler/config/config_service.py:400 的调用者未做 None 检查
- ⚠ try_load_preset_snapshot_for_baseline() 返回 Optional，但 core/services/scheduler/config/config_service.py:400 的调用者未做 None 检查
- ⚠ try_load_preset_snapshot_for_baseline() 返回 Optional，但 core/services/scheduler/config/config_preset_service.py:34 的调用者未做 None 检查
- ⚠ ConfigService.get_holiday_default_efficiency_display_state() 返回 Optional，但 web/routes/personnel_calendar_pages.py:38 的调用者未做 None 检查
- ⚠ ConfigService.get_holiday_default_efficiency_display_state() 返回 Optional，但 web/routes/domains/scheduler/scheduler_excel_calendar.py:156 的调用者未做 None 检查
- ⚠ ConfigService.get_holiday_default_efficiency_display_state() 返回 Optional，但 web/routes/domains/scheduler/scheduler_calendar_pages.py:18 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/services/scheduler/config/active_preset_provenance.py（Service 层）

### `extract_repair_fields()` [公开]
- 位置：第 7-21 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:274` [Service] `return active_preset_provenance.extract_repair_fields(reason)`
- **被调用者**（8 个）：`rstrip`, `suffix.split`, `raw_field.strip`, `strip`, `fields.append`, `str`, `field.split`, `reason.split`

### `repair_notice_from_reason()` [公开]
- 位置：第 24-42 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:278` [Service] `return active_preset_provenance.repair_notice_from_reason(`
- **被调用者**（1 个）：`extract_repair_fields`

### `normalize_repair_notice()` [公开]
- 位置：第 45-63 行
- 参数：notice
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:286` [Service] `return active_preset_provenance.normalize_repair_notice(notice)`
- **被调用者**（6 个）：`lower`, `notice.get`, `isinstance`, `strip`, `str`, `fields.append`

### `active_preset_meta_payload()` [公开]
- 位置：第 66-83 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:303` [Service] `return active_preset_provenance.active_preset_meta_payload(`
- **被调用者**（6 个）：`lower`, `set`, `normalize_repair_notice`, `notices.append`, `strip`, `str`

### `active_preset_meta_parse_warning()` [公开]
- 位置：第 86-99 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:347` [Service] `return active_preset_provenance.active_preset_meta_parse_warning(`
- **被调用者**（4 个）：`strip`, `isinstance`, `json.loads`, `str`

### `parse_active_preset_meta()` [公开]
- 位置：第 102-130 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:338` [Service] `return active_preset_provenance.parse_active_preset_meta(`
- **被调用者**（7 个）：`isinstance`, `active_preset_meta_payload`, `strip`, `legacy_meta_from_reason`, `data.get`, `str`, `json.loads`

### `serialize_active_preset_meta()` [公开]
- 位置：第 133-145 行
- 参数：meta
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:354` [Service] `return active_preset_provenance.serialize_active_preset_meta(`
- **被调用者**（3 个）：`active_preset_meta_payload`, `json.dumps`, `get`

## core/services/scheduler/config/config_page_outcome.py（Service 层）

### `public_config_field_label()` [公开]
- 位置：第 18-25 行
- 参数：field
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config_display_state.py:44` [Route] `label = public_config_field_label(field)`
- **被调用者**（4 个）：`strip`, `PUBLIC_FIELD_LABEL_OVERRIDES.get`, `str`, `field_label_for`

### `public_config_field_labels()` [公开]
- 位置：第 28-34 行
- 参数：fields
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config_display_state.py:49` [Route] `labels = public_config_field_labels(fields) or ["隐藏配置"]`
  - `web/routes/domains/scheduler/scheduler_config_feedback.py:78` [Route] `sample = "、".join(public_config_field_labels([str(field) for field in adjusted_f`
- **被调用者**（5 个）：`list`, `public_config_field_label`, `strip`, `labels.append`, `str`

### `public_config_notice()` [公开]
- 位置：第 37-55 行
- 参数：notice
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:660` [Service] `repair_notice = public_config_notice(raw_repair_notice)`
- **被调用者**（6 个）：`strip`, `public_config_field_labels`, `join`, `str`, `list`, `notice.get`

### `public_config_notices()` [公开]
- 位置：第 58-59 行
- 参数：notices
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:659` [Service] `repair_notices = public_config_notices(raw_repair_notices)`
- **被调用者**（4 个）：`public_config_notice`, `dict`, `list`, `isinstance`

### `public_active_preset_reason()` [公开]
- 位置：第 62-70 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:685` [Service] `"reason": public_active_preset_reason(reason),`
- **被调用者**（2 个）：`strip`, `str`

### `public_adjusted_reason_label()` [公开]
- 位置：第 73-85 行
- 参数：reason
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_service.py:512` [Service] `public_adjusted_reason_label(reason) or f"当前运行配置与“{baseline_label}”存在差异。",`
  - `core/services/scheduler/config/config_service.py:518` [Service] `public_adjusted_reason_label(reason) or f"当前运行配置与“{baseline_label}”存在差异。",`
- **被调用者**（10 个）：`strip`, `text.split`, `rstrip`, `public_config_field_labels`, `str`, `public_active_preset_reason`, `field.strip`, `raw_fields.split`, `prefix.strip`, `join`

### `public_config_snapshot_dict()` [公开]
- 位置：第 88-94 行
- 参数：snapshot
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`snapshot.to_dict`, `data.pop`

### `public_degradation_counters()` [公开]
- 位置：第 97-102 行
- 参数：events
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`str`, `int`, `event.get`, `public_degradation_events`, `isinstance`, `strip`

### `ConfigPageSaveOutcome.effective_snapshot()` [公开]
- 位置：第 122-123 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）

### `ConfigPageSaveOutcome.__getattr__()` [私有]
- 位置：第 125-126 行
- 参数：item
- 返回类型：Name(id='Any', ctx=Load())

### `ConfigPageSaveOutcome.to_dict()` [公开]
- 位置：第 128-129 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（82 处）：
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
  - `web/routes/domains/scheduler/scheduler_batches.py:59` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batches.py:97` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/domains/scheduler/scheduler_batches.py:192` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:22` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_gantt.py:42` [Route] `selected = item.to_dict() if item and hasattr(item, "to_dict") else None`
  - `web/routes/domains/scheduler/scheduler_gantt.py:100` [Route] `version_resolution=version_resolution.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_analysis.py:22` [Route] `return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})`
  - `web/routes/domains/scheduler/scheduler_analysis.py:209` [Route] `version_resolution=version_resolution.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:196` [Route] `d = op.to_dict()`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:247` [Route] `batch=b.to_dict(),`
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
  - `core/services/scheduler/config/config_presets.py:47` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:56` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:64` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:89` [Service] `left = a.to_dict()`
  - `core/services/scheduler/config/config_presets.py:90` [Service] `right = b.to_dict()`
  - `core/services/scheduler/config/config_presets.py:138` [Service] `canonical = snapshot.to_dict()`
  - `core/services/scheduler/config/config_presets.py:175` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config/config_presets.py:234` [Service] `return dict(snapshot.to_dict())`
  - `core/services/scheduler/config/config_presets.py:311` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/config/config_presets.py:371` [Service] `config_updates = [(key, str(value), None) for key, value in snap.to_dict().items`
  - `core/services/scheduler/config/config_service.py:951` [Service] `payload = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:981` [Service] `values = snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:994` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1008` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1036` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1067` [Service] `values = normalized_snapshot.to_dict()`
  - `core/services/scheduler/run/schedule_optimizer.py:392` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer.py:406` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:183` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:210` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:399` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:414` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/summary/schedule_summary.py:83` [Service] `return snapshot.to_dict().get(str(key or "").strip())`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:30` [Service] `).to_dict()`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:224` [Service] `"metrics": ctx.best_metrics.to_dict() if ctx.best_metrics is not None else None,`
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
- **被调用者**（1 个）：`self.to_effective_snapshot_dict`

### `ConfigPageSaveOutcome.to_snapshot_dict()` [公开]
- 位置：第 131-132 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`self.to_effective_snapshot_dict`

### `ConfigPageSaveOutcome.to_effective_snapshot_dict()` [公开]
- 位置：第 134-135 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`to_dict`

### `ConfigPageSaveOutcome.raw_effective_mismatches()` [公开]
- 位置：第 137-153 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`to_dict`, `sorted`, `items`, `effective.get`, `mismatches.append`, `str`, `dict`

### `ConfigPageSaveOutcome.to_outcome_dict()` [公开]
- 位置：第 155-174 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`to_dict`, `dict`, `self.raw_effective_mismatches`, `list`, `getattr`

### `ConfigPageSaveOutcome.to_public_outcome_dict()` [公开]
- 位置：第 176-191 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`list`, `public_config_snapshot_dict`, `public_degradation_events`, `public_degradation_counters`, `public_config_field_labels`, `public_config_notices`, `public_active_preset_reason`, `getattr`

## core/services/scheduler/config/config_preset_service.py（Service 层）

### `ConfigPresetService.__init__()` [私有]
- 位置：第 12-13 行
- 参数：owner
- 返回类型：Constant(value=None, kind=None)

### `ConfigPresetService.builtin_presets()` [公开]
- 位置：第 15-16 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `core/services/scheduler/config/config_presets.py:168` [Service] `for name, snap, desc in builtin_presets(svc):`
  - `core/services/scheduler/config/config_presets.py:231` [Service] `for preset_name, snapshot, _description in builtin_presets(svc):`
  - `core/services/scheduler/config/config_service.py:255` [Service] `return self.preset_service.builtin_presets()`
- **被调用者**（1 个）：`config_presets.builtin_presets`

### `ConfigPresetService.snapshot_close()` [公开]
- 位置：第 18-19 行
- 参数：left, right
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_presets.py:200` [Service] `elif snapshot_close(cur, default_snap):`
  - `core/services/scheduler/config/config_service.py:259` [Service] `return preset_ops.snapshot_close(a, b)`
- **被调用者**（1 个）：`config_presets.snapshot_close`

### `ConfigPresetService.ensure_builtin_presets()` [公开]
- 位置：第 21-22 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:262` [Service] `self.preset_service.ensure_builtin_presets(existing_keys=existing_keys)`
- **被调用者**（1 个）：`config_presets.ensure_builtin_presets`

### `ConfigPresetService.bootstrap_active_provenance_if_pristine()` [公开]
- 位置：第 24-25 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:201` [Service] `self.preset_service.bootstrap_active_provenance_if_pristine()`
- **被调用者**（1 个）：`config_presets.bootstrap_active_provenance_if_pristine`

### `ConfigPresetService.list_presets()` [公开]
- 位置：第 27-28 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:805` [Service] `return self.preset_service.list_presets()`
- **被调用者**（1 个）：`config_presets.list_presets`

### `ConfigPresetService.get_snapshot_from_repo()` [公开]
- 位置：第 30-31 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（3 处）：
  - `core/services/scheduler/config/config_presets.py:195` [Service] `cur = get_snapshot_from_repo(svc)`
  - `core/services/scheduler/config/config_presets.py:375` [Service] `final_snap = get_snapshot_from_repo(svc, strict_mode=True)`
  - `core/services/scheduler/config/config_service.py:265` [Service] `return self.preset_service.get_snapshot_from_repo(strict_mode=bool(strict_mode))`
- **被调用者**（2 个）：`config_presets.get_snapshot_from_repo`, `bool`

### `ConfigPresetService.try_load_preset_snapshot_for_baseline()` [公开]
- 位置：第 33-34 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:400` [Service] `return self.preset_service.try_load_preset_snapshot_for_baseline(active_text)`
- **被调用者**（1 个）：`config_presets.try_load_preset_snapshot_for_baseline`

### `ConfigPresetService.save_preset()` [公开]
- 位置：第 36-37 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:381` [Route] `saved = cfg_svc.save_preset(name)`
  - `core/services/scheduler/config/config_service.py:808` [Service] `return self.preset_service.save_preset(name)`
- **被调用者**（1 个）：`config_presets.save_preset`

### `ConfigPresetService.delete_preset()` [公开]
- 位置：第 39-40 行
- 参数：name
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:408` [Route] `cfg_svc.delete_preset(name)`
  - `core/services/scheduler/config/config_service.py:811` [Service] `self.preset_service.delete_preset(name)`
- **被调用者**（1 个）：`config_presets.delete_preset`

### `ConfigPresetService.normalize_preset_snapshot()` [公开]
- 位置：第 42-43 行
- 参数：data
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（3 处）：
  - `core/services/scheduler/config/config_presets.py:288` [Service] `return normalize_preset_snapshot(svc, data), False`
  - `core/services/scheduler/config/config_presets.py:369` [Service] `snap = normalize_preset_snapshot(svc, data)`
  - `core/services/scheduler/config/config_service.py:814` [Service] `return self.preset_service.normalize_preset_snapshot(data)`
- **被调用者**（1 个）：`config_presets.normalize_preset_snapshot`

### `ConfigPresetService.apply_preset()` [公开]
- 位置：第 45-46 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:363` [Route] `applied = cfg_svc.apply_preset(name)`
  - `core/services/scheduler/config/config_service.py:817` [Service] `return self.preset_service.apply_preset(name)`
- **被调用者**（1 个）：`config_presets.apply_preset`

## core/services/scheduler/config/config_presets.py（Service 层）

### `_preset_result()` [私有]
- 位置：第 16-36 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `builtin_presets()` [公开]
- 位置：第 39-75 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_service.py:255` [Service] `return self.preset_service.builtin_presets()`
  - `core/services/scheduler/config/config_preset_service.py:16` [Service] `return config_presets.builtin_presets(self._owner)`
- **被调用者**（3 个）：`svc._default_snapshot`, `ScheduleConfigSnapshot`, `base.to_dict`

### `snapshot_close()` [公开]
- 位置：第 78-79 行
- 参数：a, b
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_service.py:259` [Service] `return preset_ops.snapshot_close(a, b)`
  - `core/services/scheduler/config/config_preset_service.py:19` [Service] `return config_presets.snapshot_close(left, right)`
- **被调用者**（1 个）：`snapshot_diff_fields`

### `_values_close()` [私有]
- 位置：第 82-85 行
- 参数：left, right
- 返回类型：Name(id='bool', ctx=Load())

### `snapshot_diff_fields()` [公开]
- 位置：第 88-98 行
- 参数：a, b
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:422` [Service] `"baseline_diff_fields": preset_ops.snapshot_diff_fields(current_snapshot, baseli`
- **被调用者**（10 个）：`a.to_dict`, `b.to_dict`, `left.items`, `right.keys`, `list`, `dict.fromkeys`, `diff_fields.append`, `_values_close`, `str`, `right.get`

### `_preset_mismatch_reason()` [私有]
- 位置：第 101-103 行
- 参数：svc, fields
- 返回类型：Name(id='str', ctx=Load())

### `_preset_adjusted_reason()` [私有]
- 位置：第 106-108 行
- 参数：svc, fields
- 返回类型：Name(id='str', ctx=Load())

### `_registered_preset_keys()` [私有]
- 位置：第 111-112 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_missing_required_preset_fields()` [私有]
- 位置：第 115-117 行
- 参数：data
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_raw_value_matches_canonical()` [私有]
- 位置：第 120-133 行
- 参数：key, raw_value, canonical_value
- 返回类型：Name(id='bool', ctx=Load())

### `snapshot_payload_projection_diff_fields()` [公开]
- 位置：第 136-152 行
- 参数：data, snapshot
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`dict`, `snapshot.to_dict`, `set`, `_registered_preset_keys`, `payload.keys`, `list`, `dict.fromkeys`, `diff_fields.append`, `_raw_value_matches_canonical`, `payload.get`, `str`

### `get_snapshot_from_repo()` [公开]
- 位置：第 155-159 行
- 参数：svc
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_service.py:265` [Service] `return self.preset_service.get_snapshot_from_repo(strict_mode=bool(strict_mode))`
  - `core/services/scheduler/config/config_preset_service.py:31` [Service] `return config_presets.get_snapshot_from_repo(self._owner, strict_mode=bool(stric`
- **被调用者**（2 个）：`build_schedule_config_snapshot`, `bool`

### `ensure_builtin_presets()` [公开]
- 位置：第 162-185 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_service.py:262` [Service] `self.preset_service.ensure_builtin_presets(existing_keys=existing_keys)`
  - `core/services/scheduler/config/config_preset_service.py:22` [Service] `config_presets.ensure_builtin_presets(self._owner, existing_keys=existing_keys)`
- **被调用者**（8 个）：`builtin_presets`, `svc._preset_key`, `presets_to_create.append`, `transaction`, `set`, `list_all`, `json.dumps`, `snap.to_dict`

### `bootstrap_active_provenance_if_pristine()` [公开]
- 位置：第 188-212 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_service.py:201` [Service] `self.preset_service.bootstrap_active_provenance_if_pristine()`
  - `core/services/scheduler/config/config_preset_service.py:25` [Service] `config_presets.bootstrap_active_provenance_if_pristine(self._owner)`
- **被调用者**（12 个）：`bool`, `get_snapshot_from_repo`, `svc._default_snapshot`, `getattr`, `transaction`, `set_batch`, `get`, `snapshot_close`, `safe_warning`, `svc._active_preset_updates`, `svc.get_preset_display_state`, `type`

### `list_presets()` [公开]
- 位置：第 215-217 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_service.py:805` [Service] `return self.preset_service.list_presets()`
  - `core/services/scheduler/config/config_preset_service.py:28` [Service] `return config_presets.list_presets(self._owner)`
- **被调用者**（3 个）：`svc.get_preset_display_state`, `list`, `state.get`

### `_readonly_active_preset_state()` [私有]
- 位置：第 220-227 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_builtin_preset_payload()` [私有]
- 位置：第 230-235 行
- 参数：svc, name
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_is_reserved_custom_preset_name()` [私有]
- 位置：第 238-239 行
- 参数：svc, name
- 返回类型：Name(id='bool', ctx=Load())

### `_validate_preset_name()` [私有]
- 位置：第 242-254 行
- 参数：svc, name
- 返回类型：Name(id='str', ctx=Load())

### `_load_preset_payload()` [私有]
- 位置：第 257-272 行
- 参数：svc, name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `try_load_preset_snapshot_for_baseline()` [公开]
- 位置：第 275-290 行
- 参数：svc, name
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_service.py:400` [Service] `return self.preset_service.try_load_preset_snapshot_for_baseline(active_text)`
  - `core/services/scheduler/config/config_preset_service.py:34` [Service] `return config_presets.try_load_preset_snapshot_for_baseline(self._owner, name)`
- **被调用者**（7 个）：`strip`, `_missing_required_preset_fields`, `_load_preset_payload`, `str`, `preset_name.lower`, `lower`, `normalize_preset_snapshot`

### `save_preset()` [公开]
- 位置：第 293-321 行
- 参数：svc, name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:381` [Route] `saved = cfg_svc.save_preset(name)`
  - `core/services/scheduler/config/config_service.py:808` [Service] `return self.preset_service.save_preset(name)`
  - `core/services/scheduler/config/config_preset_service.py:37` [Service] `return config_presets.save_preset(self._owner, name)`
- **被调用者**（15 个）：`_validate_preset_name`, `svc._ensure_defaults_if_pristine`, `json.dumps`, `_preset_result`, `svc.get_snapshot`, `snap.to_dict`, `transaction`, `set`, `set_batch`, `_readonly_active_preset_state`, `svc._preset_key`, `svc._active_preset_updates`, `str`, `strip`, `getattr`

### `delete_preset()` [公开]
- 位置：第 324-333 行
- 参数：svc, name
- 返回类型：Constant(value=None, kind=None)
- **调用者**（3 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:408` [Route] `cfg_svc.delete_preset(name)`
  - `core/services/scheduler/config/config_service.py:811` [Service] `self.preset_service.delete_preset(name)`
  - `core/services/scheduler/config/config_preset_service.py:40` [Service] `config_presets.delete_preset(self._owner, name)`
- **被调用者**（9 个）：`_validate_preset_name`, `svc.get_active_preset`, `get_value`, `BusinessError`, `transaction`, `delete`, `svc._preset_key`, `set_batch`, `svc._active_preset_updates`

### `normalize_preset_snapshot()` [公开]
- 位置：第 336-346 行
- 参数：svc, data
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_service.py:814` [Service] `return self.preset_service.normalize_preset_snapshot(data)`
  - `core/services/scheduler/config/config_preset_service.py:43` [Service] `return config_presets.normalize_preset_snapshot(self._owner, data)`
- **被调用者**（2 个）：`svc._default_snapshot`, `normalize_preset_snapshot_dict`

### `apply_preset()` [公开]
- 位置：第 349-413 行
- 参数：svc, name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:363` [Route] `applied = cfg_svc.apply_preset(name)`
  - `core/services/scheduler/config/config_service.py:817` [Service] `return self.preset_service.apply_preset(name)`
  - `core/services/scheduler/config/config_preset_service.py:46` [Service] `return config_presets.apply_preset(self._owner, name)`
- **被调用者**（20 个）：`_validate_preset_name`, `_load_preset_payload`, `_missing_required_preset_fields`, `normalize_preset_snapshot`, `snapshot_payload_projection_diff_fields`, `_preset_result`, `_readonly_active_preset_state`, `join`, `transaction`, `set_batch`, `get_snapshot_from_repo`, `snapshot_diff_fields`, `str`, `items`, `list`

## core/services/scheduler/config/config_service.py（Service 层）

### `ConfigService.__init__()` [私有]
- 位置：第 123-129 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ConfigService._normalize_text()` [私有]
- 位置：第 135-136 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ConfigService._normalize_weight()` [私有]
- 位置：第 139-145 行
- 参数：value, field
- 返回类型：Name(id='float', ctx=Load())

### `ConfigService.normalize_weight()` [公开]
- 位置：第 148-149 行
- 参数：value, field
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`ConfigService._normalize_weight`

### `ConfigService._normalize_weights_triplet()` [私有]
- 位置：第 152-164 行
- 参数：priority_weight, due_weight, ready_weight
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._field_description()` [私有]
- 位置：第 166-167 行
- 参数：key
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._registered_updates()` [私有]
- 位置：第 169-173 行
- 参数：values
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._get_raw_value()` [私有]
- 位置：第 175-176 行
- 参数：config_key, default
- 返回类型：Name(id='Any', ctx=Load())

### `ConfigService._bootstrap_registered_defaults()` [私有]
- 位置：第 178-192 行
- 参数：无
- 返回类型：Name(id='set', ctx=Load())

### `ConfigService.ensure_defaults()` [公开]
- 位置：第 194-204 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/system/system_config_service.py:172` [Service] `self.ensure_defaults(backup_keep_days_default=backup_keep_days_default)`
- **被调用者**（5 个）：`self._is_pristine_store`, `self._bootstrap_registered_defaults`, `self._ensure_builtin_presets`, `bootstrap_active_provenance_if_pristine`, `set`

### `ConfigService._is_pristine_store()` [私有]
- 位置：第 206-207 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._ensure_defaults_if_pristine()` [私有]
- 位置：第 209-213 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._preset_key()` [私有]
- 位置：第 219-220 行
- 参数：name
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._is_builtin_preset()` [私有]
- 位置：第 223-229 行
- 参数：name
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._default_snapshot()` [私有]
- 位置：第 231-252 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService._builtin_presets()` [私有]
- 位置：第 254-255 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._snapshot_close()` [私有]
- 位置：第 258-259 行
- 参数：a, b
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._ensure_builtin_presets()` [私有]
- 位置：第 261-262 行
- 参数：existing_keys
- 返回类型：Constant(value=None, kind=None)

### `ConfigService._get_snapshot_from_repo()` [私有]
- 位置：第 264-265 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService._list_config_rows()` [私有]
- 位置：第 267-270 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._extract_repair_fields()` [私有]
- 位置：第 273-274 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._repair_notice_from_reason()` [私有]
- 位置：第 277-282 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._normalize_repair_notice()` [私有]
- 位置：第 285-286 行
- 参数：notice
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ConfigService._active_preset_meta_reason_codes()` [私有]
- 位置：第 289-294 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._active_preset_meta_payload()` [私有]
- 位置：第 297-307 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._legacy_active_preset_meta_from_reason()` [私有]
- 位置：第 310-329 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._active_preset_meta_from_value()` [私有]
- 位置：第 332-343 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._active_preset_meta_parse_warning()` [私有]
- 位置：第 346-350 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ConfigService._serialize_active_preset_meta()` [私有]
- 位置：第 353-357 行
- 参数：meta
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._compat_repair_notice()` [私有]
- 位置：第 360-375 行
- 参数：repair_notices
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._reason_in()` [私有]
- 位置：第 378-379 行
- 参数：reason
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._builtin_preset_names()` [私有]
- 位置：第 381-386 行
- 参数：无
- 返回类型：Subscript(value=Name(id='set', ctx=Load()), slice=Index(valu

### `ConfigService._row_config_text()` [私有]
- 位置：第 389-391 行
- 参数：row
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ConfigService._config_page_values_equal()` [私有]
- 位置：第 394-397 行
- 参数：left, right
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._try_load_preset_baseline_snapshot()` [私有]
- 位置：第 399-400 行
- 参数：active_text
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._active_preset_baseline_probe_state()` [私有]
- 位置：第 402-423 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._resolve_current_config_baseline()` [私有]
- 位置：第 425-460 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._current_config_missing_provenance_descriptor()` [私有]
- 位置：第 463-474 行
- 参数：baseline_label
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._current_config_manual_reason()` [私有]
- 位置：第 477-486 行
- 参数：reason
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._resolve_current_config_descriptor()` [私有]
- 位置：第 488-542 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._collect_preset_rows()` [私有]
- 位置：第 544-554 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._build_preset_entries()` [私有]
- 位置：第 556-579 行
- 参数：preset_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._active_preset_display_state_from_rows()` [私有]
- 位置：第 581-597 行
- 参数：by_key
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._active_preset_provenance_state()` [私有]
- 位置：第 600-629 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._build_current_config_state()` [私有]
- 位置：第 631-690 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService.get_active_preset()` [公开]
- 位置：第 692-695 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_presets.py:329` [Service] `active = svc.get_active_preset()`
- **被调用者**（3 个）：`get_value`, `strip`, `str`

### `ConfigService.get_active_preset_reason()` [公开]
- 位置：第 697-700 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`get_value`, `strip`, `str`

### `ConfigService.get_active_preset_meta()` [公开]
- 位置：第 702-704 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`get_value`, `self._active_preset_meta_from_value`, `self.get_active_preset_reason`

### `ConfigService.get_preset_display_state()` [公开]
- 位置：第 706-753 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（5 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:78` [Route] `preset_display_state = cfg_svc.get_preset_display_state(readonly=True, current_s`
  - `web/routes/domains/scheduler/scheduler_config.py:314` [Route] `preset_display_state = cfg_svc.get_preset_display_state(readonly=True, current_s`
  - `core/services/scheduler/config/config_presets.py:192` [Service] `if bool((svc.get_preset_display_state(readonly=True) or {}).get("can_preserve_ba`
  - `core/services/scheduler/config/config_presets.py:216` [Service] `state = svc.get_preset_display_state(readonly=True)`
  - `core/services/scheduler/config/config_presets.py:221` [Service] `state = svc.get_preset_display_state(readonly=True)`
- **被调用者**（14 个）：`self._list_config_rows`, `self._collect_preset_rows`, `self._active_preset_display_state_from_rows`, `self._active_preset_baseline_probe_state`, `bool`, `list`, `strip`, `self._build_current_config_state`, `self._get_snapshot_from_repo`, `baseline_probe_state.get`, `self._build_preset_entries`, `str`, `preset_state.get`, `self._reason_in`

### `ConfigService._active_preset_update()` [私有]
- 位置：第 755-761 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._active_preset_reason_update()` [私有]
- 位置：第 763-769 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._active_preset_meta_update()` [私有]
- 位置：第 771-776 行
- 参数：meta
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._active_preset_updates()` [私有]
- 位置：第 778-792 行
- 参数：name, reason
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._set_active_preset()` [私有]
- 位置：第 794-796 行
- 参数：name
- 返回类型：Constant(value=None, kind=None)

### `ConfigService.mark_active_preset_custom()` [公开]
- 位置：第 798-802 行
- 参数：reason
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:360` [Route] `cfg_svc.mark_active_preset_custom()`
- **被调用者**（1 个）：`self._set_active_preset`

### `ConfigService.list_presets()` [公开]
- 位置：第 804-805 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_preset_service.py:28` [Service] `return config_presets.list_presets(self._owner)`

### `ConfigService.save_preset()` [公开]
- 位置：第 807-808 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:381` [Route] `saved = cfg_svc.save_preset(name)`
  - `core/services/scheduler/config/config_preset_service.py:37` [Service] `return config_presets.save_preset(self._owner, name)`

### `ConfigService.delete_preset()` [公开]
- 位置：第 810-811 行
- 参数：name
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:408` [Route] `cfg_svc.delete_preset(name)`
  - `core/services/scheduler/config/config_preset_service.py:40` [Service] `config_presets.delete_preset(self._owner, name)`

### `ConfigService._normalize_preset_snapshot()` [私有]
- 位置：第 813-814 行
- 参数：data
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService.apply_preset()` [公开]
- 位置：第 816-817 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:363` [Route] `applied = cfg_svc.apply_preset(name)`
  - `core/services/scheduler/config/config_preset_service.py:46` [Service] `return config_presets.apply_preset(self._owner, name)`

### `ConfigService.get()` [公开]
- 位置：第 819-820 行
- 参数：config_key
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`get_value`, `str`

### `ConfigService._get_registered_field_value()` [私有]
- 位置：第 822-835 行
- 参数：key
- 返回类型：Name(id='Any', ctx=Load())

### `ConfigService.get_holiday_default_efficiency()` [公开]
- 位置：第 837-844 行
- 参数：无
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（3 处）：
  - `web/routes/personnel_excel_operator_calendar.py:138` [Route] `return float(cfg_svc.get_holiday_default_efficiency()), None`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:132` [Route] `return float(cfg_svc.get_holiday_default_efficiency()), None`
  - `core/services/scheduler/calendar_admin.py:46` [Service] `return float(cfg_svc.get_holiday_default_efficiency(strict_mode=True))`
- **被调用者**（3 个）：`float`, `self._get_registered_field_value`, `bool`

### `ConfigService.get_holiday_default_efficiency_display_state()` [公开]
- 位置：第 846-861 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（3 处）：
  - `web/routes/personnel_calendar_pages.py:38` [Route] `hde, hde_degraded, hde_warning = cfg_svc.get_holiday_default_efficiency_display_`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:156` [Route] `hde, hde_degraded, hde_warning = cfg_svc.get_holiday_default_efficiency_display_`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:18` [Route] `hde, hde_degraded, hde_warning = cfg_svc.get_holiday_default_efficiency_display_`
- **被调用者**（9 个）：`self.get_snapshot`, `float`, `any`, `safe_warning`, `format`, `isinstance`, `strip`, `str`, `get`

### `ConfigService.get_available_strategies()` [公开]
- 位置：第 866-868 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:68` [Route] `strategies = cfg_svc.get_available_strategies()`
  - `web/routes/domains/scheduler/scheduler_config.py:303` [Route] `strategies = cfg_svc.get_available_strategies()`
- **被调用者**（3 个）：`choice_label_map_for`, `labels.get`, `choices_for`

### `ConfigService.get_snapshot()` [公开]
- 位置：第 870-873 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（7 处）：
  - `web/routes/system_utils.py:162` [Route] `return svc.get_snapshot(backup_keep_days_default=int(current_app.config.get("BAC`
  - `web/routes/domains/scheduler/scheduler_batches.py:67` [Route] `cfg = cfg_svc.get_snapshot()`
  - `web/routes/domains/scheduler/scheduler_config.py:302` [Route] `cfg = cfg_svc.get_snapshot(strict_mode=False)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:231` [Route] `prefer_primary_skill = services.config_service.get_snapshot().prefer_primary_ski`
  - `core/services/scheduler/schedule_service.py:38` [Service] `return cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`
  - `core/services/scheduler/config/config_presets.py:298` [Service] `snap = svc.get_snapshot(strict_mode=True)`
  - `core/services/system/system_maintenance_service.py:92` [Service] `cfg = cfg_svc.get_snapshot(backup_keep_days_default=int(backup_keep_days_default`
- **被调用者**（3 个）：`self._get_snapshot_from_repo`, `bool`, `self._ensure_defaults_if_pristine`

### `ConfigService.get_page_metadata()` [公开]
- 位置：第 876-877 行
- 参数：keys
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`page_metadata_for`

### `ConfigService.get_field_label()` [公开]
- 位置：第 880-881 行
- 参数：key
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`field_label_for`

### `ConfigService.get_choice_labels()` [公开]
- 位置：第 884-885 行
- 参数：key
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`choice_label_map_for`

### `ConfigService._config_page_value()` [私有]
- 位置：第 891-897 行
- 参数：form_values, key
- 返回类型：Name(id='Any', ctx=Load())

### `ConfigService._config_page_submitted_fields()` [私有]
- 位置：第 900-918 行
- 参数：form_values
- 返回类型：Subscript(value=Name(id='set', ctx=Load()), slice=Index(valu

### `ConfigService._normalize_config_page_weights()` [私有]
- 位置：第 920-942 行
- 参数：priority_raw, due_raw, current_snapshot
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._normalize_config_page_payload()` [私有]
- 位置：第 944-973 行
- 参数：form_values
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService._config_page_write_values()` [私有]
- 位置：第 975-985 行
- 参数：snapshot
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_materialized_write_values()` [私有]
- 位置：第 988-1000 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_visible_changed_fields()` [私有]
- 位置：第 1002-1013 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._snapshot_degraded_fields()` [私有]
- 位置：第 1016-1027 行
- 参数：snapshot
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._config_page_visible_repair_fields()` [私有]
- 位置：第 1030-1057 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._config_page_hidden_repair_values()` [私有]
- 位置：第 1060-1072 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_hidden_repair_reason()` [私有]
- 位置：第 1075-1089 行
- 参数：hidden_repaired_fields
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._config_page_visible_repair_notice()` [私有]
- 位置：第 1092-1097 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_hidden_repair_notice()` [私有]
- 位置：第 1100-1105 行
- 参数：hidden_repaired_fields
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_blocked_hidden_repair_notice()` [私有]
- 位置：第 1108-1119 行
- 参数：blocked_hidden_fields
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_current_provenance_state()` [私有]
- 位置：第 1121-1135 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_notices()` [私有]
- 位置：第 1138-1143 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._config_page_initial_write_plan()` [私有]
- 位置：第 1145-1164 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._config_page_apply_visible_change_plan()` [私有]
- 位置：第 1166-1184 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ConfigService._config_page_apply_visible_repair_plan()` [私有]
- 位置：第 1186-1206 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ConfigService._config_page_apply_hidden_repair_plan()` [私有]
- 位置：第 1208-1252 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ConfigService._config_page_build_write_plan()` [私有]
- 位置：第 1254-1311 行
- 参数：无
- 返回类型：Name(id='ConfigPageWritePlan', ctx=Load())

### `ConfigService._config_page_save_status()` [私有]
- 位置：第 1314-1321 行
- 参数：plan
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._config_page_raw_persisted_state()` [私有]
- 位置：第 1323-1340 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService.save_page_config()` [公开]
- 位置：第 1342-1411 行
- 参数：form_values
- 返回类型：Name(id='ConfigPageSaveOutcome', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:457` [Route] `outcome = cfg_svc.save_page_config(payload)`
- **被调用者**（26 个）：`self._ensure_defaults_if_pristine`, `get_value`, `self._active_preset_meta_parse_warning`, `self.get_snapshot`, `self._config_page_current_provenance_state`, `provenance_state.get`, `self._config_page_submitted_fields`, `self._normalize_config_page_payload`, `self._config_page_write_values`, `self._config_page_visible_changed_fields`, `self._config_page_visible_repair_fields`, `self._config_page_hidden_repair_values`, `list`, `write_values.update`, `self._config_page_materialized_write_values`

### `ConfigService.set_strategy()` [公开]
- 位置：第 1413-1426 行
- 参数：sort_strategy
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_weights()` [公开]
- 位置：第 1428-1442 行
- 参数：priority_weight, due_weight, ready_weight, require_sum_1
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`self._normalize_weights_triplet`, `transaction`, `set`, `set_batch`, `str`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.restore_default()` [公开]
- 位置：第 1444-1448 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:468` [Route] `cfg_svc.restore_default()`
- **被调用者**（6 个）：`self._registered_updates`, `updates.extend`, `default_snapshot_values`, `self._active_preset_updates`, `transaction`, `set_batch`

### `ConfigService.set_dispatch()` [公开]
- 位置：第 1450-1473 行
- 参数：dispatch_mode, dispatch_rule
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_auto_assign_enabled()` [公开]
- 位置：第 1475-1488 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_ortools()` [公开]
- 位置：第 1490-1512 行
- 参数：enabled, time_limit_seconds
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`str`, `int`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_prefer_primary_skill()` [公开]
- 位置：第 1514-1527 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_enforce_ready_default()` [公开]
- 位置：第 1529-1542 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_holiday_default_efficiency()` [公开]
- 位置：第 1544-1563 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`float`, `ValidationError`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `strip`, `str`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_algo_mode()` [公开]
- 位置：第 1565-1578 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_time_budget_seconds()` [公开]
- 位置：第 1580-1595 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`int`, `ValidationError`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `strip`, `str`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_objective()` [公开]
- 位置：第 1597-1610 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_freeze_window()` [公开]
- 位置：第 1612-1634 行
- 参数：enabled, days
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`str`, `int`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

## core/services/scheduler/config/config_snapshot.py（Service 层）

### `ScheduleConfigSnapshot.to_dict()` [公开]
- 位置：第 46-66 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
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
  - `web/routes/domains/scheduler/scheduler_batches.py:59` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batches.py:97` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/domains/scheduler/scheduler_batches.py:192` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:22` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_gantt.py:42` [Route] `selected = item.to_dict() if item and hasattr(item, "to_dict") else None`
  - `web/routes/domains/scheduler/scheduler_gantt.py:100` [Route] `version_resolution=version_resolution.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_analysis.py:22` [Route] `return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})`
  - `web/routes/domains/scheduler/scheduler_analysis.py:209` [Route] `version_resolution=version_resolution.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:196` [Route] `d = op.to_dict()`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:247` [Route] `batch=b.to_dict(),`
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
  - `core/services/scheduler/config/config_presets.py:47` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:56` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:64` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:89` [Service] `left = a.to_dict()`
  - `core/services/scheduler/config/config_presets.py:90` [Service] `right = b.to_dict()`
  - `core/services/scheduler/config/config_presets.py:138` [Service] `canonical = snapshot.to_dict()`
  - `core/services/scheduler/config/config_presets.py:175` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config/config_presets.py:234` [Service] `return dict(snapshot.to_dict())`
  - `core/services/scheduler/config/config_presets.py:311` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/config/config_presets.py:371` [Service] `config_updates = [(key, str(value), None) for key, value in snap.to_dict().items`
  - `core/services/scheduler/config/config_page_outcome.py:91` [Service] `data = snapshot.to_dict()`
  - `core/services/scheduler/config/config_page_outcome.py:135` [Service] `return self.snapshot.to_dict()`
  - `core/services/scheduler/config/config_page_outcome.py:138` [Service] `effective = self.snapshot.to_dict()`
  - `core/services/scheduler/config/config_page_outcome.py:159` [Service] `"effective_snapshot": self.snapshot.to_dict(),`
  - `core/services/scheduler/config/config_page_outcome.py:160` [Service] `"normalized_snapshot": self.normalized_snapshot.to_dict() if self.normalized_sna`
  - `core/services/scheduler/config/config_service.py:951` [Service] `payload = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:981` [Service] `values = snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:994` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1008` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1036` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1067` [Service] `values = normalized_snapshot.to_dict()`
  - `core/services/scheduler/run/schedule_optimizer.py:392` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer.py:406` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:183` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:210` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:399` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:414` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/summary/schedule_summary.py:83` [Service] `return snapshot.to_dict().get(str(key or "").strip())`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:30` [Service] `).to_dict()`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:224` [Service] `"metrics": ctx.best_metrics.to_dict() if ctx.best_metrics is not None else None,`
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
- **被调用者**（2 个）：`float`, `int`

### `_read_runtime_cfg_raw_value()` [私有]
- 位置：第 69-89 行
- 参数：cfg, key
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_runtime_cfg_read_error()` [私有]
- 位置：第 92-93 行
- 参数：key, exc
- 返回类型：Name(id='ValidationError', ctx=Load())

### `_read_runtime_cfg_mapping_like_value()` [私有]
- 位置：第 96-112 行
- 参数：cfg, key, raw_missing
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_read_runtime_cfg_mapping_like_value_without_default()` [私有]
- 位置：第 115-123 行
- 参数：getter, key, raw_missing
- 返回类型：Name(id='Any', ctx=Load())

### `_coerce_degradation_event()` [私有]
- 位置：第 126-152 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_seed_snapshot_degradation_collector()` [私有]
- 位置：第 155-161 行
- 参数：snapshot
- 返回类型：Name(id='DegradationCollector', ctx=Load())

### `_merge_degradation_counters()` [私有]
- 位置：第 164-180 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_validate_present_runtime_cfg_fields()` [私有]
- 位置：第 183-202 行
- 参数：cfg
- 返回类型：Constant(value=None, kind=None)

### `_build_schedule_config_snapshot_from_runtime_cfg()` [私有]
- 位置：第 205-273 行
- 参数：cfg
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `coerce_runtime_config_field()` [公开]
- 位置：第 276-297 行
- 参数：cfg, key
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（1 处）：
  - `core/algorithms/greedy/schedule_params.py:110` [Algorithm] `coerce_runtime_config_field(`
- **被调用者**（5 个）：`default_snapshot_values`, `_read_runtime_cfg_raw_value`, `coerce_config_field`, `DegradationCollector`, `bool`

### `ensure_schedule_config_snapshot()` [公开]
- 位置：第 300-310 行
- 参数：cfg
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（14 处）：
  - `core/services/scheduler/config/config_service.py:969` [Service] `return ensure_schedule_config_snapshot(`
  - `core/services/scheduler/run/schedule_optimizer.py:454` [Service] `cfg = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:36` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:52` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:121` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:338` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:403` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:445` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/summary/schedule_summary_freeze.py:15` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/summary/schedule_summary.py:78` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/summary/schedule_summary.py:456` [Service] `cfg=ensure_schedule_config_snapshot(`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:26` [Service] `return ensure_schedule_config_snapshot(`
  - `core/algorithms/greedy/config_adapter.py:17` [Algorithm] `snapshot = ensure_schedule_config_snapshot(config)`
  - `core/algorithms/greedy/schedule_params.py:99` [Algorithm] `return ensure_schedule_config_snapshot(`
- **被调用者**（2 个）：`_build_schedule_config_snapshot_from_runtime_cfg`, `bool`

### `build_schedule_config_snapshot()` [公开]
- 位置：第 313-412 行
- 参数：repo
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_presets.py:156` [Service] `return build_schedule_config_snapshot(`
- **被调用者**（26 个）：`DegradationCollector`, `object`, `default_snapshot_values`, `isinstance`, `bool`, `list_config_fields`, `ScheduleConfigSnapshot`, `default_map.update`, `TypeError`, `getattr`, `callable`, `repo.get_value`, `_read_repo_raw_value`, `coerce_config_field`, `normalize_weight_triplet`

## core/services/scheduler/config/config_validator.py（Service 层）

### `_emit_number_below_minimum()` [私有]
- 位置：第 13-26 行
- 参数：collector
- 返回类型：Constant(value=None, kind=None)

### `_preset_float()` [私有]
- 位置：第 29-49 行
- 参数：key, raw_value
- 返回类型：Name(id='float', ctx=Load())

### `_preset_int()` [私有]
- 位置：第 52-72 行
- 参数：key, raw_value
- 返回类型：Name(id='int', ctx=Load())

### `normalize_preset_snapshot()` [公开]
- 位置：第 75-241 行
- 参数：data
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（4 处）：
  - `core/services/scheduler/config/config_presets.py:288` [Service] `return normalize_preset_snapshot(svc, data), False`
  - `core/services/scheduler/config/config_presets.py:369` [Service] `snap = normalize_preset_snapshot(svc, data)`
  - `core/services/scheduler/config/config_service.py:814` [Service] `return self.preset_service.normalize_preset_snapshot(data)`
  - `core/services/scheduler/config/config_preset_service.py:43` [Service] `return config_presets.normalize_preset_snapshot(self._owner, data)`
- **被调用者**（22 个）：`dict`, `DegradationCollector`, `_read`, `coerce_config_field`, `_preset_float`, `derive_ready_weight_from_priority_due`, `_yes_no`, `_choice`, `_preset_int`, `ScheduleConfigSnapshot`, `normalize_single_weight`, `str`, `payload.get`, `bool`, `float`

## core/services/scheduler/config/config_weight_policy.py（Service 层）

### `_parse_weight()` [私有]
- 位置：第 10-16 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())

### `normalize_single_weight()` [公开]
- 位置：第 19-24 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_validator.py:133` [Service] `explicit_ready_weight = normalize_single_weight(rw, field="ready_weight")`
  - `core/services/scheduler/config/config_service.py:145` [Service] `return normalize_single_weight(value, field=field)`
- **被调用者**（3 个）：`_parse_weight`, `float`, `ValidationError`

### `normalize_weight_triplet()` [公开]
- 位置：第 27-62 行
- 参数：priority_weight, due_weight, ready_weight
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（3 处）：
  - `core/services/scheduler/config/config_snapshot.py:239` [Service] `values["priority_weight"], values["due_weight"], values["ready_weight"] = normal`
  - `core/services/scheduler/config/config_snapshot.py:381` [Service] `values["priority_weight"], values["due_weight"], values["ready_weight"] = normal`
  - `core/services/scheduler/config/config_service.py:159` [Service] `return normalize_weight_triplet(`
- **被调用者**（4 个）：`_parse_weight`, `float`, `ValidationError`, `abs`

### `derive_ready_weight_from_priority_due()` [公开]
- 位置：第 65-86 行
- 参数：priority_weight, due_weight
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_validator.py:126` [Service] `derived_pw, derived_dw, derived_rw = derive_ready_weight_from_priority_due(`
  - `core/services/scheduler/config/config_service.py:939` [Service] `return derive_ready_weight_from_priority_due(`
- **被调用者**（5 个）：`_parse_weight`, `normalize_weight_triplet`, `float`, `ValidationError`, `max`

## core/services/scheduler/run/schedule_optimizer.py（Service 层）

### `_field_label()` [私有]
- 位置：第 35-36 行
- 参数：field
- 返回类型：Name(id='str', ctx=Load())

### `_score_tuple()` [私有]
- 位置：第 56-65 行
- 参数：score
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_attempt_dispatch_mode()` [私有]
- 位置：第 68-69 行
- 参数：item
- 返回类型：Name(id='str', ctx=Load())

### `_attempt_tag()` [私有]
- 位置：第 72-73 行
- 参数：item
- 返回类型：Name(id='str', ctx=Load())

### `_sorted_attempts_by_score()` [私有]
- 位置：第 76-77 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_best_attempts_by_dispatch_mode()` [私有]
- 位置：第 80-87 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_append_unique_best_attempts()` [私有]
- 位置：第 90-105 行
- 参数：selected, attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_compact_attempts()` [私有]
- 位置：第 108-114 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_require_choice()` [私有]
- 位置：第 117-122 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_require_float()` [私有]
- 位置：第 125-126 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())

### `_require_int()` [私有]
- 位置：第 129-130 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_normalized_choice_values()` [私有]
- 位置：第 133-144 行
- 参数：values
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_effective_choice_values()` [私有]
- 位置：第 147-155 行
- 参数：field
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_record_optimizer_cfg_degradations()` [私有]
- 位置：第 158-172 行
- 参数：snapshot, optimizer_algo_stats
- 返回类型：Constant(value=None, kind=None)

### `_init_seen_hashes()` [私有]
- 位置：第 175-183 行
- 参数：cur_order, best
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_raise_invalid_seed_results_error()` [私有]
- 位置：第 186-192 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_seed_result_sample()` [私有]
- 位置：第 195-205 行
- 参数：item
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_coerce_seed_result_item()` [私有]
- 位置：第 208-223 行
- 参数：item
- 返回类型：Name(id='ScheduleResult', ctx=Load())

### `_coerce_seed_time_range()` [私有]
- 位置：第 226-237 行
- 参数：item
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_coerce_seed_results()` [私有]
- 位置：第 240-264 行
- 参数：seed_results
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_run_local_search()` [私有]
- 位置：第 267-428 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `optimize_schedule()` [公开]
- 位置：第 431-651 行
- 参数：无
- 返回类型：Name(id='OptimizationOutcome', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（32 个）：`_coerce_seed_results`, `ensure_schedule_config_snapshot`, `GreedyScheduler`, `_effective_choice_values`, `SortStrategy`, `_require_choice`, `_require_int`, `build_normalized_batches_map`, `str`, `time.time`, `_run_ortools_warmstart`, `_run_multi_start`, `_run_local_search`, `OptimizationOutcome`, `_record_optimizer_cfg_degradations`

## web/routes/domains/scheduler/scheduler_config_display_state.py（Route 层）

### `get_scheduler_visible_config_field_metadata()` [公开]
- 位置：第 28-29 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:69` [Route] `config_field_metadata = get_scheduler_visible_config_field_metadata()`
  - `web/routes/domains/scheduler/scheduler_config.py:304` [Route] `config_field_metadata = get_scheduler_visible_config_field_metadata()`
- **被调用者**（2 个）：`page_metadata_for`, `list`

### `_format_config_display_value()` [私有]
- 位置：第 32-40 行
- 参数：field, value
- 返回类型：Name(id='str', ctx=Load())

### `public_hidden_config_warning()` [公开]
- 位置：第 43-45 行
- 参数：field
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`public_config_field_label`

### `public_hidden_repair_notice()` [公开]
- 位置：第 48-53 行
- 参数：fields
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config_feedback.py:118` [Route] `messages.append(public_hidden_repair_notice(fields, blocked=kind == "blocked_hid`
- **被调用者**（2 个）：`join`, `public_config_field_labels`

### `public_meta_parse_warning()` [公开]
- 位置：第 56-57 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config_feedback.py:122` [Route] `messages.append(public_meta_parse_warning())`

### `build_config_degraded_display_state()` [公开]
- 位置：第 60-89 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:70` [Route] `config_field_warnings, config_degraded_fields, config_hidden_warnings = build_co`
  - `web/routes/domains/scheduler/scheduler_config.py:305` [Route] `config_field_warnings, config_degraded_fields, config_hidden_warnings = build_co`
- **被调用者**（10 个）：`getattr`, `strip`, `hidden_warnings.append`, `isinstance`, `config_field_metadata.get`, `str`, `_format_config_display_value`, `degraded_fields.append`, `public_hidden_config_warning`, `get`

### `build_auto_assign_persist_display_state()` [公开]
- 位置：第 92-113 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:88` [Route] `current_auto_assign_persist_state = build_auto_assign_persist_display_state(geta`
  - `web/routes/domains/scheduler/scheduler_batches.py:130` [Route] `latest_auto_assign_persist_state = build_auto_assign_persist_display_state(`
  - `web/routes/domains/scheduler/scheduler_config.py:324` [Route] `auto_assign_persist_state = build_auto_assign_persist_display_state(getattr(cfg,`
- **被调用者**（3 个）：`lower`, `strip`, `str`

## web/routes/domains/scheduler/scheduler_config_feedback.py（Route 层）

### `_normalized_error_fields()` [私有]
- 位置：第 13-18 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_format_single_field_preset_error()` [私有]
- 位置：第 21-29 行
- 参数：detail, field_key
- 返回类型：Name(id='str', ctx=Load())

### `_replace_field_keys_with_labels()` [私有]
- 位置：第 32-38 行
- 参数：detail, field_keys
- 返回类型：Name(id='str', ctx=Load())

### `_format_preset_error_flash()` [私有]
- 位置：第 41-57 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_flash_preset_apply_feedback()` [私有]
- 位置：第 60-85 行
- 参数：applied
- 返回类型：Constant(value=None, kind=None)

### `_config_save_outcome_fields()` [私有]
- 位置：第 88-89 行
- 参数：outcome, field_name
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_config_save_primary_flash()` [私有]
- 位置：第 92-106 行
- 参数：outcome
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_iter_config_save_notice_messages()` [私有]
- 位置：第 109-123 行
- 参数：outcome
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_flash_config_save_outcome()` [私有]
- 位置：第 126-132 行
- 参数：outcome
- 返回类型：Constant(value=None, kind=None)

## web/routes/domains/scheduler/scheduler_excel_calendar.py（Route 层）

### `_canonicalize_calendar_date()` [私有]
- 位置：第 47-51 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_build_existing_preview_data()` [私有]
- 位置：第 54-73 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_calendar_baseline_extra_state()` [私有]
- 位置：第 76-77 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_require_holiday_default_efficiency()` [私有]
- 位置：第 80-83 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())

### `execute_preview_rows_transactional()` [公开]
- 位置：第 86-87 行
- 参数：services
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（7 处）：
  - `web/bootstrap/request_services.py:206` [Bootstrap] `return execute_preview_rows_transactional(self._db, **kwargs)`
  - `core/services/scheduler/calendar_service.py:199` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/scheduler/batch_excel_import.py:93` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/equipment/machine_excel_import_service.py:94` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/personnel/operator_excel_import_service.py:77` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/process/op_type_excel_import_service.py:65` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/process/supplier_excel_import_service.py:94` [Service] `stats = execute_preview_rows_transactional(`
- **被调用者**（1 个）：`services.execute_preview_rows_transactional`

### `_render_excel_calendar_page()` [私有]
- 位置：第 90-121 行
- 参数：无
- 返回类型：无注解

### `_load_holiday_default_efficiency_for_excel()` [私有]
- 位置：第 124-149 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `excel_calendar_page()` [公开]
- 位置：第 153-170 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`bp.get`, `_build_existing_preview_data`, `cfg_svc.get_holiday_default_efficiency_display_state`, `_render_excel_calendar_page`

### `excel_calendar_preview()` [公开]
- 位置：第 174-286 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（30 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_build_existing_preview_data`, `_load_holiday_default_efficiency_for_excel`, `_require_holiday_default_efficiency`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_calendar_page`, `ValidationError`

### `excel_calendar_confirm()` [公开]
- 位置：第 290-459 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（44 个）：`bp.post`, `time.time`, `_parse_mode`, `load_confirm_payload`, `_build_existing_preview_data`, `_load_holiday_default_efficiency_for_excel`, `_require_holiday_default_efficiency`, `preview_baseline_is_stale`, `_ensure_unique_ids`, `excel_svc.preview_import`, `collect_error_rows`, `set`, `execute_preview_rows_transactional`, `stats.to_dict`, `extract_import_stats`

### `excel_calendar_template()` [公开]
- 位置：第 463-504 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_calendar_export()` [公开]
- 位置：第 508-548 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `cal_svc.list_all`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`, `calendar_day_type_label`, `yes_no_label`

---
- 分析函数/方法数：237
- 找到调用关系：306 处
- 跨层边界风险：9 项
