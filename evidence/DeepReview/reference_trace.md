# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ auto_assign_internal_resources() 返回 Optional，但 core/algorithms/greedy/scheduler.py:567 的调用者未做 None 检查
- ⚠ parse_date() 返回 Optional，但 core/algorithms/greedy/dispatch/sgs.py:25 的调用者未做 None 检查
- ⚠ parse_datetime() 返回 Optional，但 core/algorithms/greedy/scheduler.py:80 的调用者未做 None 检查
- ⚠ try_solve_bottleneck_batch_order() 返回 Optional，但 core/services/scheduler/schedule_optimizer_steps.py:169 的调用者未做 None 检查
- ⚠ parse_optional_float() 返回 Optional，但 core/services/common/number_utils.py:26 的调用者未做 None 检查
- ⚠ parse_optional_int() 返回 Optional，但 core/services/common/number_utils.py:43 的调用者未做 None 检查
- ⚠ parse_optional_date() 返回 Optional，但 core/algorithms/greedy/dispatch/sgs.py:24 的调用者未做 None 检查
- ⚠ parse_optional_datetime() 返回 Optional，但 core/algorithms/greedy/scheduler.py:79 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/algorithms/dispatch_rules.py（Algorithm 层）

### `parse_dispatch_rule()` [公开]
- 位置：第 28-35 行
- 参数：value, default
- 返回类型：Name(id='DispatchRule', ctx=Load())
- **调用者**（1 处）：
  - `core/algorithms/greedy/schedule_params.py:203` [Algorithm] `dispatch_rule_enum = parse_dispatch_rule(dispatch_rule, default=DispatchRule.SLA`
- **被调用者**（5 个）：`isinstance`, `DispatchRule`, `lower`, `strip`, `str`

### `build_dispatch_key()` [公开]
- 位置：第 55-109 行
- 参数：inp
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/dispatch/sgs.py:78` [Algorithm] `base_key = build_dispatch_key(`
- **被调用者**（10 个）：`normalize_priority`, `float`, `due_exclusive`, `_safe_positive`, `PRIORITY_RANK.get`, `PRIORITY_WEIGHT.get`, `total_seconds`, `math.isfinite`, `math.exp`, `max`

### `mean_positive()` [公开]
- 位置：第 112-132 行
- 参数：values
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`values.values`, `float`, `statistics.fmean`, `math.isfinite`, `vals.append`

## core/algorithms/evaluation.py（Algorithm 层）

### `_due_text()` [私有]
- 位置：第 15-22 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_parse_due_date_state()` [私有]
- 位置：第 25-36 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ScheduleMetrics.to_dict()` [公开]
- 位置：第 68-99 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（65 处）：
  - `web/routes/equipment_pages.py:221` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:234` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:27` [Route] `items = [m.to_dict() for m in svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:40` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:58` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:165` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:116` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:117` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:118` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:147` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/scheduler_batches.py:49` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:73` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:139` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:183` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:227` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:34` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/scheduler_excel_calendar.py:410` [Route] `result = stats.to_dict()`
  - `web/routes/scheduler_resource_dispatch.py:51` [Route] `for key, value in request.args.to_dict(flat=True).items():`
  - `web/routes/scheduler_resource_dispatch.py:188` [Route] `return redirect(url_for("scheduler.resource_dispatch_page", **request.args.to_di`
  - `web/routes/system_backup.py:51` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:49` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:57` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:52` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:146` [Route] `d = it.to_dict()`
  - `core/services/common/pandas_backend.py:106` [Service] `raw_rows = df.to_dict(orient="records")`
  - `core/services/equipment/machine_excel_import_service.py:106` [Service] `out = stats.to_dict()`
  - `core/services/material/material_service.py:82` [Service] `self.op_logger.info(module="material", action="create", target_type="material", `
  - `core/services/personnel/operator_excel_import_service.py:90` [Service] `out = stats.to_dict()`
  - `core/services/personnel/resource_team_service.py:74` [Service] `return [team.to_dict() for team in self.list(status=status)]`
  - `core/services/process/op_type_excel_import_service.py:79` [Service] `out = stats.to_dict()`
  - `core/services/process/part_operation_hours_excel_import_service.py:70` [Service] `return stats.to_dict(total_rows=len(preview_rows))`
  - `core/services/process/route_parser.py:59` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:79` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:80` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
  - `core/services/process/supplier_excel_import_service.py:108` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:104` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:198` [Service] `self.batch_repo.create(batch.to_dict())`
  - `core/services/scheduler/calendar_admin.py:310` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:321` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:377` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:382` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config_presets.py:20` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:29` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:37` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:81` [Service] `canonical = snap.to_dict()`
  - `core/services/scheduler/config_presets.py:150` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config_presets.py:210` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/gantt_contract.py:98` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:189` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:248` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_optimizer.py:239` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:252` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:298` [Service] `cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(`
  - `core/services/scheduler/schedule_optimizer_steps.py:226` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:253` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:455` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:470` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_summary_assembly.py:89` [Service] `obj = to_dict()`
  - `core/services/scheduler/schedule_summary_assembly.py:292` [Service] `"metrics": ctx.best_metrics.to_dict() if ctx.best_metrics is not None else None,`
- **被调用者**（8 个）：`float`, `int`, `_round_finite`, `bool`, `math.isfinite`, `round`, `str`, `list`

### `compute_metrics()` [公开]
- 位置：第 102-280 行
- 参数：results, batches
- 返回类型：Name(id='ScheduleMetrics', ctx=Load())
- **调用者**（4 处）：
  - `core/services/scheduler/schedule_optimizer.py:212` [Service] `metrics = compute_metrics(res, batches)`
  - `core/services/scheduler/schedule_optimizer.py:538` [Service] `best_metrics = compute_metrics(results, batches)`
  - `core/services/scheduler/schedule_optimizer_steps.py:215` [Service] `metrics = compute_metrics(res, batches)`
  - `core/services/scheduler/schedule_optimizer_steps.py:352` [Service] `metrics = compute_metrics(res, batches)`
- **被调用者**（35 个）：`batches.items`, `by_machine.items`, `_finite_non_negative`, `float`, `bool`, `ScheduleMetrics`, `strip`, `finish_by_batch.get`, `getattr`, `_parse_due_date_state`, `due_exclusive`, `append`, `lst.sort`, `max`, `statistics.fmean`

### `objective_score()` [公开]
- 位置：第 283-314 行
- 参数：objective, metrics
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（4 处）：
  - `core/services/scheduler/schedule_optimizer.py:214` [Service] `score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)`
  - `core/services/scheduler/schedule_optimizer.py:539` [Service] `best_score = (float(summary.failed_ops),) + objective_score(objective_name, best`
  - `core/services/scheduler/schedule_optimizer_steps.py:216` [Service] `score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)`
  - `core/services/scheduler/schedule_optimizer_steps.py:353` [Service] `score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)`
- **被调用者**（4 个）：`lower`, `float`, `strip`, `str`

## core/algorithms/greedy/auto_assign.py（Algorithm 层）

### `auto_assign_internal_resources()` [公开]
- 位置：第 10-177 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:567` [Algorithm] `return auto_assign_internal_resources(`
- **被调用者**（27 个）：`strip`, `batch_progress.get`, `list`, `sorted`, `_count`, `isinstance`, `resource_pool.get`, `dict.fromkeys`, `validate_internal_hours`, `str`, `estimate_internal_slot`, `operators_by_machine.items`, `float`, `int`, `getattr`

## core/algorithms/greedy/date_parsers.py（Algorithm 层）

### `parse_date()` [公开]
- 位置：第 7-21 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（10 处）：
  - `core/services/report/report_engine.py:185` [Service] `sd = calculations.parse_date(start_date, field="start_date")`
  - `core/services/report/report_engine.py:186` [Service] `ed = calculations.parse_date(end_date, field="end_date")`
  - `core/services/report/report_engine.py:234` [Service] `sd = calculations.parse_date(start_date, field="start_date")`
  - `core/services/report/report_engine.py:235` [Service] `ed = calculations.parse_date(end_date, field="end_date")`
  - `core/algorithms/evaluation.py:35` [Algorithm] `parsed = parse_date(s)`
  - `core/algorithms/ortools_bottleneck.py:94` [Algorithm] `due_d = parse_date(getattr(b, "due_date", None))`
  - `core/algorithms/greedy/scheduler.py:70` [Algorithm] `return parse_optional_date(value, field="due_date") if strict_mode else parse_da`
  - `core/algorithms/greedy/scheduler.py:74` [Algorithm] `return parse_optional_date(value, field="ready_date") if strict_mode else parse_`
  - `core/algorithms/greedy/schedule_params.py:68` [Algorithm] `end_d = parse_date(end_date)`
  - `core/algorithms/greedy/dispatch/sgs.py:25` [Algorithm] `return parse_date(value)`
- **被调用者**（7 个）：`isinstance`, `strip`, `s.replace`, `value.date`, `date`, `str`, `datetime.strptime`

### `parse_datetime()` [公开]
- 位置：第 24-43 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `core/algorithms/greedy/scheduler.py:80` [Algorithm] `return parse_datetime(value)`
  - `core/algorithms/greedy/schedule_params.py:58` [Algorithm] `parsed = parse_datetime(base_time)`
- **被调用者**（7 个）：`isinstance`, `strip`, `replace`, `datetime`, `datetime.strptime`, `str`, `s.replace`

### `due_exclusive()` [公开]
- 位置：第 46-49 行
- 参数：d
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（4 处）：
  - `core/services/report/calculations.py:98` [Service] `due_excl = due_exclusive(due_d)`
  - `core/algorithms/dispatch_rules.py:67` [Algorithm] `due_dt_exclusive = due_exclusive(inp.due_date)`
  - `core/algorithms/evaluation.py:151` [Algorithm] `batch_due_exclusive = due_exclusive(due_d)`
  - `core/algorithms/ortools_bottleneck.py:96` [Algorithm] `due_dt_exclusive = due_exclusive(due_d)`
- **被调用者**（2 个）：`datetime`, `timedelta`

## core/algorithms/greedy/dispatch/batch_order.py（Algorithm 层）

### `dispatch_batch_order()` [公开]
- 位置：第 12-124 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:382` [Algorithm] `scheduled_count, failed_count = dispatch_batch_order(`
- **被调用者**（15 个）：`strip`, `errors.append`, `lower`, `scheduler._schedule_external`, `scheduler._schedule_internal`, `results.append`, `max`, `blocked_batches.add`, `str`, `accumulate_busy_hours`, `update_machine_last_state`, `batch_progress.get`, `getattr`, `exception`, `bool`

## core/algorithms/greedy/dispatch/runtime_state.py（Algorithm 层）

### `accumulate_busy_hours()` [公开]
- 位置：第 7-23 行
- 参数：无
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（3 处）：
  - `core/algorithms/greedy/scheduler.py:317` [Algorithm] `accumulate_busy_hours(`
  - `core/algorithms/greedy/dispatch/batch_order.py:90` [Algorithm] `accumulate_busy_hours(`
  - `core/algorithms/greedy/dispatch/sgs.py:610` [Algorithm] `accumulate_busy_hours(`
- **被调用者**（6 个）：`float`, `TypeError`, `total_seconds`, `isinstance`, `machine_busy_hours.get`, `operator_busy_hours.get`

### `update_machine_last_state()` [公开]
- 位置：第 26-54 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（3 处）：
  - `core/algorithms/greedy/scheduler.py:325` [Algorithm] `update_machine_last_state(`
  - `core/algorithms/greedy/dispatch/batch_order.py:98` [Algorithm] `update_machine_last_state(`
  - `core/algorithms/greedy/dispatch/sgs.py:618` [Algorithm] `update_machine_last_state(`
- **被调用者**（5 个）：`strip`, `last_end_by_machine.get`, `isinstance`, `TypeError`, `str`

## core/algorithms/greedy/dispatch/sgs.py（Algorithm 层）

### `_parse_due_date()` [私有]
- 位置：第 22-25 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_safe_seq()` [私有]
- 位置：第 28-35 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_raise_strict_internal_hours_validation()` [私有]
- 位置：第 38-59 行
- 参数：op, batch, exc
- 返回类型：Constant(value=None, kind=None)

### `_dispatch_key()` [私有]
- 位置：第 62-94 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_unscorable_dispatch_key()` [私有]
- 位置：第 97-146 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_collect_sgs_candidates()` [私有]
- 位置：第 149-165 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_record_external_compat_counters()` [私有]
- 位置：第 168-172 行
- 参数：scheduler, collector
- 返回类型：Constant(value=None, kind=None)

### `_score_external_candidate()` [私有]
- 位置：第 175-322 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_score_internal_candidate()` [私有]
- 位置：第 325-447 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_pick_best_candidate()` [私有]
- 位置：第 450-455 行
- 参数：scored_candidates
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `dispatch_sgs()` [公开]
- 位置：第 458-654 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:355` [Algorithm] `scheduled_count, failed_count = dispatch_sgs(`
- **被调用者**（41 个）：`ops_by_batch.values`, `sorted`, `ops_by_batch.items`, `strip`, `append`, `operations.sort`, `list`, `batches.get`, `increment_counter`, `_collect_sgs_candidates`, `_pick_best_candidate`, `errors.append`, `ops_by_batch.keys`, `sum`, `float`

## core/algorithms/greedy/downtime.py（Algorithm 层）

### `get_resource_available()` [公开]
- 位置：第 8-18 行
- 参数：timeline, resource_id, base_time
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`max`, `timeline.get`

### `occupy_resource()` [公开]
- 位置：第 21-30 行
- 参数：timeline, resource_id, start, end
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `core/algorithms/greedy/scheduler.py:306` [Algorithm] `occupy_resource(machine_timeline, machine_id, sr.start_time, sr.end_time)`
  - `core/algorithms/greedy/scheduler.py:312` [Algorithm] `occupy_resource(operator_timeline, operator_id, sr.start_time, sr.end_time)`
  - `core/algorithms/greedy/scheduler.py:529` [Algorithm] `occupy_resource(machine_timeline, machine_id, estimate.start_time, estimate.end_`
  - `core/algorithms/greedy/scheduler.py:530` [Algorithm] `occupy_resource(operator_timeline, operator_id, estimate.start_time, estimate.en`
- **被调用者**（2 个）：`timeline.setdefault`, `bisect.insort`

### `find_earliest_available_start()` [公开]
- 位置：第 33-59 行
- 参数：segments, base_time, duration_hours
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（3 处）：
  - `core/algorithms/greedy/dispatch/sgs.py:123` [Algorithm] `estimate_start = find_earliest_available_start(machine_timeline or [], estimate_`
  - `core/algorithms/greedy/dispatch/sgs.py:124` [Algorithm] `estimate_start = find_earliest_available_start(operator_timeline or [], estimate`
  - `core/algorithms/greedy/dispatch/sgs.py:125` [Algorithm] `estimate_start = find_earliest_available_start(machine_downtimes or [], estimate`
- **被调用者**（4 个）：`timedelta`, `float`, `find_overlap_shift_end`, `len`

### `find_overlap_shift_end()` [公开]
- 位置：第 62-80 行
- 参数：segments, start, end
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（3 处）：
  - `core/algorithms/greedy/internal_slot.py:167` [Algorithm] `find_overlap_shift_end(machine_segments, earliest, end_time),`
  - `core/algorithms/greedy/internal_slot.py:168` [Algorithm] `find_overlap_shift_end(operator_segments, earliest, end_time),`
  - `core/algorithms/greedy/internal_slot.py:169` [Algorithm] `find_overlap_shift_end(downtime_segments, earliest, end_time),`

## core/algorithms/greedy/internal_slot.py（Algorithm 层）

### `_read_legacy_field()` [私有]
- 位置：第 27-32 行
- 参数：obj, field
- 返回类型：Name(id='Any', ctx=Load())

### `_coerce_legacy_hours_value()` [私有]
- 位置：第 35-50 行
- 参数：raw_value
- 返回类型：Name(id='float', ctx=Load())

### `validate_internal_hours()` [公开]
- 位置：第 53-68 行
- 参数：op, batch
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（3 处）：
  - `core/algorithms/greedy/auto_assign.py:89` [Algorithm] `total_hours_base = validate_internal_hours(op, batch)`
  - `core/algorithms/greedy/dispatch/sgs.py:354` [Algorithm] `total_hours_base = validate_internal_hours(op, batch)`
  - `core/algorithms/greedy/dispatch/sgs.py:515` [Algorithm] `proc_samples.append(validate_internal_hours(op, batch))`
- **被调用者**（5 个）：`_read_legacy_field`, `_coerce_legacy_hours_value`, `float`, `ValueError`, `math.isfinite`

### `_resolve_efficiency()` [私有]
- 位置：第 71-83 行
- 参数：calendar
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_changeover_penalty()` [私有]
- 位置：第 86-95 行
- 参数：op, machine_id, last_op_type_by_machine
- 返回类型：Name(id='int', ctx=Load())

### `_abort_result()` [私有]
- 位置：第 98-115 行
- 参数：无
- 返回类型：Name(id='InternalSlotEstimate', ctx=Load())

### `estimate_internal_slot()` [公开]
- 位置：第 118-204 行
- 参数：无
- 返回类型：Name(id='InternalSlotEstimate', ctx=Load())
- **调用者**（3 处）：
  - `core/algorithms/greedy/auto_assign.py:134` [Algorithm] `estimate = estimate_internal_slot(`
  - `core/algorithms/greedy/scheduler.py:500` [Algorithm] `estimate = estimate_internal_slot(`
  - `core/algorithms/greedy/dispatch/sgs.py:414` [Algorithm] `estimate = estimate_internal_slot(`
- **被调用者**（17 个）：`getattr`, `_changeover_penalty`, `list`, `max`, `calendar.adjust_to_working_time`, `InternalSlotEstimate`, `validate_internal_hours`, `float`, `ValueError`, `_abort_result`, `_resolve_efficiency`, `bool`, `calendar.add_working_hours`, `math.isfinite`, `find_overlap_shift_end`

## core/algorithms/greedy/scheduler.py（Algorithm 层）

### `normalize_text_id()` [公开]
- 位置：第 36-43 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`strip`, `str`

### `resolve_batch_sort_batch_id()` [公开]
- 位置：第 46-50 行
- 参数：batch_key, batch
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`normalize_text_id`, `getattr`

### `build_normalized_batches_map()` [公开]
- 位置：第 53-66 行
- 参数：batches
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_optimizer.py:346` [Service] `normalized_batches_for_sort = build_normalized_batches_map(batches)`
- **被调用者**（5 个）：`items`, `resolve_batch_sort_batch_id`, `str`, `warnings.append`, `normalized.get`

### `_parse_due_date_for_sort()` [私有]
- 位置：第 69-70 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_parse_ready_date_for_sort()` [私有]
- 位置：第 73-74 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_parse_created_at_for_sort()` [私有]
- 位置：第 77-80 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `build_batch_sort_inputs()` [公开]
- 位置：第 83-106 行
- 参数：batches
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_optimizer.py:349` [Service] `batch_for_sort = build_batch_sort_inputs(`
- **被调用者**（10 个）：`items`, `resolve_batch_sort_batch_id`, `batch_for_sort.append`, `BatchForSort`, `str`, `_parse_due_date_for_sort`, `_parse_ready_date_for_sort`, `_parse_created_at_for_sort`, `getattr`, `bool`

### `GreedyScheduler.__init__()` [私有]
- 位置：第 112-116 行
- 参数：calendar_service, config_service, logger
- 返回类型：无注解

### `GreedyScheduler._cfg_get()` [私有]
- 位置：第 118-127 行
- 参数：key, default
- 返回类型：Name(id='Any', ctx=Load())

### `GreedyScheduler.schedule()` [公开]
- 位置：第 129-420 行
- 参数：operations, batches, strategy, strategy_params, start_dt, end_date, machine_downtimes, batch_order_override, seed_results, dispatch_mode, dispatch_rule, resource_pool, strict_mode
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（4 处）：
  - `core/services/scheduler/schedule_optimizer_steps.py:102` [Service] `return scheduler.schedule(**kwargs)`
  - `core/services/scheduler/schedule_optimizer_steps.py:104` [Service] `return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))`
  - `core/services/scheduler/schedule_optimizer_steps.py:107` [Service] `return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))`
  - `core/services/scheduler/schedule_optimizer_steps.py:114` [Service] `return scheduler.schedule(**kwargs)`
- **被调用者**（51 个）：`datetime.now`, `ensure_algo_stats`, `resolve_schedule_params`, `warnings.extend`, `build_normalized_batches_map`, `StrategyFactory.create`, `set`, `sorted`, `info`, `batches.items`, `total_seconds`, `int`, `ScheduleSummary`, `build_batch_sort_inputs`, `sorter.sort`

### `GreedyScheduler._schedule_external()` [私有]
- 位置：第 422-443 行
- 参数：op, batch, batch_progress, external_group_cache, base_time, errors, end_dt_exclusive, strict_mode
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `GreedyScheduler._schedule_internal()` [私有]
- 位置：第 445-548 行
- 参数：op, batch, batch_progress, machine_timeline, operator_timeline, base_time, errors, end_dt_exclusive, machine_downtimes
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `GreedyScheduler._auto_assign_internal_resources()` [私有]
- 位置：第 550-582 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

## core/algorithms/ortools_bottleneck.py（Algorithm 层）

### `try_solve_bottleneck_batch_order()` [公开]
- 位置：第 27-197 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_optimizer_steps.py:169` [Service] `ort_order = try_solve_bottleneck_batch_order(`
- **被调用者**（45 个）：`batches.items`, `int`, `cp_model.CpModel`, `enumerate`, `model.AddNoOverlap`, `model.Minimize`, `cp_model.CpSolver`, `float`, `solver.Solve`, `sorted`, `strip`, `batches.get`, `max`, `priority_weight_scaled`, `jobs.append`

## core/services/common/strict_parse.py（Service 层）

### `is_blank_input()` [公开]
- 位置：第 13-14 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `core/services/common/compat_parse.py:48` [Service] `if is_blank_input(raw_value) and policy.blank_reason_code:`
- **被调用者**（2 个）：`isinstance`, `value.strip`

### `_raise_blank_required()` [私有]
- 位置：第 17-18 行
- 参数：field
- 返回类型：Constant(value=None, kind=None)

### `_ensure_min_float()` [私有]
- 位置：第 21-26 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())

### `_ensure_min_int()` [私有]
- 位置：第 29-32 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_parse_finite_float()` [私有]
- 位置：第 35-44 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())

### `_parse_finite_int()` [私有]
- 位置：第 47-59 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_normalize_datetime_text()` [私有]
- 位置：第 62-65 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `parse_required_float()` [公开]
- 位置：第 68-73 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（11 处）：
  - `web/routes/process_excel_suppliers.py:99` [Route] `days = parse_required_float(raw_value, field="默认周期", min_value=0, min_inclusive=`
  - `core/services/common/compat_parse.py:95` [Service] `parsed = parse_required_float(value, field=field, min_value=min_value, min_inclu`
  - `core/services/common/field_parse.py:72` [Service] `parse_required_float(value, field=field, min_value=min_value, min_inclusive=min_`
  - `core/services/common/field_parse.py:76` [Service] `parsed = float(parse_required_float(value, field=field))`
  - `core/services/common/number_utils.py:27` [Service] `return parse_required_float(value, field=field)`
  - `core/services/process/supplier_excel_import_service.py:73` [Service] `default_days = parse_required_float(data.get("默认周期"), field="默认周期")`
  - `core/services/process/supplier_service.py:33` [Service] `parsed = parse_required_float(value, field="默认周期")`
  - `core/services/scheduler/config_validator.py:72` [Service] `return float(parse_required_float(raw, field=key, min_value=min_value, min_inclu`
  - `core/services/scheduler/config_validator.py:74` [Service] `parsed = float(parse_required_float(raw, field=key))`
  - `core/services/scheduler/operation_edit_service.py:210` [Service] `dv = parse_required_float(ext_days, field="外协周期(天)")`
  - `core/services/scheduler/schedule_input_builder.py:65` [Service] `parse_required_float(`
- **被调用者**（4 个）：`is_blank_input`, `_ensure_min_float`, `_raise_blank_required`, `_parse_finite_float`

### `parse_optional_float()` [公开]
- 位置：第 76-79 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/common/number_utils.py:26` [Service] `return parse_optional_float(value, field=field)`
- **被调用者**（2 个）：`is_blank_input`, `parse_required_float`

### `parse_required_int()` [公开]
- 位置：第 82-85 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（6 处）：
  - `core/services/common/compat_parse.py:102` [Service] `parsed = parse_required_int(value, field=field, min_value=min_value)`
  - `core/services/common/field_parse.py:120` [Service] `return int(parse_required_int(value, field=field, min_value=min_value))`
  - `core/services/common/field_parse.py:123` [Service] `parsed = int(parse_required_int(value, field=field))`
  - `core/services/common/number_utils.py:44` [Service] `return parse_required_int(value, field=field)`
  - `core/services/scheduler/config_validator.py:94` [Service] `return int(parse_required_int(raw, field=key, min_value=min_v))`
  - `core/services/scheduler/config_validator.py:96` [Service] `parsed = int(parse_required_int(raw, field=key))`
- **被调用者**（4 个）：`is_blank_input`, `_ensure_min_int`, `_raise_blank_required`, `_parse_finite_int`

### `parse_optional_int()` [公开]
- 位置：第 88-91 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/common/number_utils.py:43` [Service] `return parse_optional_int(value, field=field)`
- **被调用者**（2 个）：`is_blank_input`, `parse_required_int`

### `parse_required_date()` [公开]
- 位置：第 94-105 行
- 参数：value
- 返回类型：Name(id='date', ctx=Load())
- **调用者**（1 处）：
  - `core/services/common/compat_parse.py:113` [Service] `return parse_required_date(value, field=field)`
- **被调用者**（10 个）：`isinstance`, `is_blank_input`, `replace`, `value.date`, `_raise_blank_required`, `date`, `strip`, `ValidationError`, `datetime.strptime`, `str`

### `parse_optional_date()` [公开]
- 位置：第 108-111 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（3 处）：
  - `core/algorithms/greedy/scheduler.py:70` [Algorithm] `return parse_optional_date(value, field="due_date") if strict_mode else parse_da`
  - `core/algorithms/greedy/scheduler.py:74` [Algorithm] `return parse_optional_date(value, field="ready_date") if strict_mode else parse_`
  - `core/algorithms/greedy/dispatch/sgs.py:24` [Algorithm] `return parse_optional_date(value, field="due_date")`
- **被调用者**（2 个）：`is_blank_input`, `parse_required_date`

### `parse_required_datetime()` [公开]
- 位置：第 114-125 行
- 参数：value
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`isinstance`, `_normalize_datetime_text`, `ValidationError`, `datetime`, `datetime.strptime`

### `parse_optional_datetime()` [公开]
- 位置：第 128-131 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:79` [Algorithm] `return parse_optional_datetime(value, field="created_at")`
- **被调用者**（2 个）：`is_blank_input`, `parse_required_datetime`

## core/services/scheduler/schedule_optimizer.py（Service 层）

### `_score_tuple()` [私有]
- 位置：第 42-51 行
- 参数：score
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_attempt_dispatch_mode()` [私有]
- 位置：第 54-55 行
- 参数：item
- 返回类型：Name(id='str', ctx=Load())

### `_attempt_tag()` [私有]
- 位置：第 58-59 行
- 参数：item
- 返回类型：Name(id='str', ctx=Load())

### `_sorted_attempts_by_score()` [私有]
- 位置：第 62-63 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_best_attempts_by_dispatch_mode()` [私有]
- 位置：第 66-73 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_append_unique_best_attempts()` [私有]
- 位置：第 76-91 行
- 参数：selected, attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_compact_attempts()` [私有]
- 位置：第 94-100 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_init_seen_hashes()` [私有]
- 位置：第 103-111 行
- 参数：cur_order, best
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_run_local_search()` [私有]
- 位置：第 114-274 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `optimize_schedule()` [公开]
- 位置：第 277-582 行
- 参数：无
- 返回类型：Name(id='OptimizationOutcome', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（51 个）：`GreedyScheduler`, `parse_strategy`, `_norm_text`, `_cfg_int`, `build_normalized_batches_map`, `_cfg_choices`, `str`, `time.time`, `_run_ortools_warmstart`, `_run_multi_start`, `_run_local_search`, `OptimizationOutcome`, `hasattr`, `cfg.to_dict`, `cfg_get`

## core/services/scheduler/schedule_optimizer_steps.py（Service 层）

### `SchedulerLike.schedule()` [公开]
- 位置：第 21-22 行
- 参数：无
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）

### `_is_yes()` [私有]
- 位置：第 25-26 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())

### `_cfg_float()` [私有]
- 位置：第 29-55 行
- 参数：_cfg_value, key, default
- 返回类型：Name(id='float', ctx=Load())

### `_cfg_int()` [私有]
- 位置：第 58-82 行
- 参数：_cfg_value, key, default
- 返回类型：Name(id='int', ctx=Load())

### `_scheduler_accepts_strict_mode()` [私有]
- 位置：第 85-96 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_schedule_with_optional_strict_mode()` [私有]
- 位置：第 99-115 行
- 参数：scheduler
- 返回类型：无注解

### `_run_ortools_warmstart()` [私有]
- 位置：第 118-266 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_dispatch_rules_for_mode()` [私有]
- 位置：第 269-272 行
- 参数：dispatch_mode, dispatch_rule_cfg, valid_dispatch_rules
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_resolve_multi_start_strategy_params()` [私有]
- 位置：第 275-301 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_get_cached_multi_start_order()` [私有]
- 位置：第 304-314 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_evaluate_multi_start_candidate()` [私有]
- 位置：第 317-366 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_run_multi_start()` [私有]
- 位置：第 369-473 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

---
- 分析函数/方法数：88
- 找到调用关系：148 处
- 跨层边界风险：8 项
