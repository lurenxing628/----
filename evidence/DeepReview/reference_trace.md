# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ DegradationCollector.extend() 在 Service 层，但被 Repository 层调用（反向依赖）
- ⚠ DegradationCollector.extend() 在 Service 层，但被 Repository 层调用（反向依赖）
- ⚠ DegradationCollector.extend() 在 Service 层，但被 Repository 层调用（反向依赖）
- ⚠ ResourceTeamService.resolve_team_name_optional() 返回 Optional，但 web/routes/equipment_excel_machines.py:173 的调用者未做 None 检查
- ⚠ ResourceTeamService.resolve_team_name_optional() 返回 Optional，但 web/routes/equipment_excel_machines.py:196 的调用者未做 None 检查
- ⚠ ResourceTeamService.resolve_team_name_optional() 返回 Optional，但 web/routes/equipment_excel_machines.py:282 的调用者未做 None 检查
- ⚠ ResourceTeamService.resolve_team_name_optional() 返回 Optional，但 web/routes/personnel_excel_operators.py:131 的调用者未做 None 检查
- ⚠ ResourceTeamService.resolve_team_name_optional() 返回 Optional，但 web/routes/personnel_excel_operators.py:143 的调用者未做 None 检查
- ⚠ ResourceTeamService.resolve_team_name_optional() 返回 Optional，但 web/routes/personnel_excel_operators.py:222 的调用者未做 None 检查
- ⚠ CalendarAdmin.get_operator_calendar() 返回 Optional，但 core/services/scheduler/calendar_service.py:108 的调用者未做 None 检查
- ⚠ ConfigService.get_holiday_default_efficiency_display_state() 返回 Optional，但 web/routes/personnel_calendar_pages.py:37 的调用者未做 None 检查
- ⚠ ConfigService.get_holiday_default_efficiency_display_state() 返回 Optional，但 web/routes/domains/scheduler/scheduler_calendar_pages.py:17 的调用者未做 None 检查
- ⚠ ConfigRepository.get_value() 返回 Optional，但 core/services/system/system_config_service.py:179 的调用者未做 None 检查
- ⚠ ConfigRepository.list_all() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ MachineDowntimeRepository.list_by_machine() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ MachineDowntimeRepository.list_active_machine_ids_at() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ MachineDowntimeRepository.cancel() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ ScheduleHistoryRepository.list_recent() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ ScheduleHistoryRepository.get_by_version() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ ScheduleHistoryRepository.get_by_version() 返回 Optional，但 core/services/scheduler/gantt_service.py:271 的调用者未做 None 检查
- ⚠ ScheduleHistoryRepository.get_by_version() 返回 Optional，但 core/services/scheduler/schedule_history_query_service.py:25 的调用者未做 None 检查
- ⚠ ScheduleHistoryRepository.list_versions() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ ScheduleRepository.list_by_machine() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）
- ⚠ build_trend_charts() 返回 Optional，但 web/viewmodels/scheduler_analysis_vm.py:184 的调用者未做 None 检查
- ⚠ build_selected_details() 返回 Optional，但 web/viewmodels/scheduler_analysis_vm.py:193 的调用者未做 None 检查
- ⚠ build_primary_degradation() 返回 Optional，但 web/viewmodels/scheduler_analysis_vm.py:207 的调用者未做 None 检查
- ⚠ build_primary_degradation() 返回 Optional，但 web/viewmodels/scheduler_summary_display.py:173 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/algorithms/evaluation.py（Algorithm 层）

### `_due_text()` [私有]
- 位置：第 16-23 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_parse_due_date_state()` [私有]
- 位置：第 26-37 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ScheduleMetrics.to_dict()` [公开]
- 位置：第 69-100 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（81 处）：
  - `web/routes/equipment_pages.py:221` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:234` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:26` [Route] `items = [m.to_dict() for m in material_svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:24` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:45` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:165` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:116` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:117` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:118` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:147` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/system_backup.py:51` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:34` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:48` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:57` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:172` [Route] `d = it.to_dict()`
  - `web/routes/domains/scheduler/scheduler_analysis.py:17` [Route] `return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})`
  - `web/routes/domains/scheduler/scheduler_batches.py:58` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batches.py:96` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/domains/scheduler/scheduler_batches.py:189` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:196` [Route] `d = op.to_dict()`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:247` [Route] `batch=b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:21` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:410` [Route] `result = stats.to_dict()`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:139` [Route] `payload = exc.to_dict()`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:50` [Route] `selected_history = selected_history_item.to_dict() if hasattr(selected_history_i`
  - `web/viewmodels/scheduler_analysis_trends.py:107` [ViewModel] `d = h.to_dict() if hasattr(h, "to_dict") else (h if isinstance(h, dict) else {})`
  - `web/viewmodels/scheduler_analysis_trends.py:153` [ViewModel] `return selected_item.to_dict() if hasattr(selected_item, "to_dict") else (select`
  - `web/viewmodels/system_logs_vm.py:29` [ViewModel] `d = it.to_dict() if hasattr(it, "to_dict") else (it if isinstance(it, dict) else`
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
  - `core/services/scheduler/calendar_admin.py:306` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:373` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:378` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/gantt_contract.py:98` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:212` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:281` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_service.py:301` [Service] `"summary": orchestration.summary_contract.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:47` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:56` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:64` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:89` [Service] `left = a.to_dict()`
  - `core/services/scheduler/config/config_presets.py:90` [Service] `right = b.to_dict()`
  - `core/services/scheduler/config/config_presets.py:138` [Service] `canonical = snapshot.to_dict()`
  - `core/services/scheduler/config/config_presets.py:175` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config/config_presets.py:234` [Service] `return dict(snapshot.to_dict())`
  - `core/services/scheduler/config/config_presets.py:279` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/config/config_presets.py:343` [Service] `config_updates = [(key, str(value), None) for key, value in snap.to_dict().items`
  - `core/services/scheduler/config/config_service.py:45` [Service] `return self.snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:968` [Service] `payload = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:998` [Service] `values = snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1011` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1025` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1053` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1084` [Service] `values = normalized_snapshot.to_dict()`
  - `core/services/scheduler/run/schedule_optimizer.py:320` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer.py:334` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:183` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:210` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:399` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:414` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/summary/schedule_summary.py:82` [Service] `return snapshot.to_dict().get(str(key or "").strip())`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:30` [Service] `).to_dict()`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:220` [Service] `"metrics": ctx.best_metrics.to_dict() if ctx.best_metrics is not None else None,`
- **被调用者**（8 个）：`float`, `int`, `_round_finite`, `bool`, `math.isfinite`, `round`, `str`, `list`

### `compute_metrics()` [公开]
- 位置：第 103-281 行
- 参数：results, batches
- 返回类型：Name(id='ScheduleMetrics', ctx=Load())
- **调用者**（4 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:293` [Service] `metrics = compute_metrics(res, batches)`
  - `core/services/scheduler/run/schedule_optimizer.py:601` [Service] `best_metrics = compute_metrics(results, batches)`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:171` [Service] `metrics = compute_metrics(res, batches)`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:295` [Service] `metrics = compute_metrics(res, batches)`
- **被调用者**（35 个）：`batches.items`, `by_machine.items`, `_finite_non_negative`, `float`, `bool`, `ScheduleMetrics`, `strip`, `finish_by_batch.get`, `getattr`, `_parse_due_date_state`, `due_exclusive`, `append`, `lst.sort`, `max`, `statistics.fmean`

### `objective_score()` [公开]
- 位置：第 284-285 行
- 参数：objective, metrics
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（4 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:295` [Service] `score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)`
  - `core/services/scheduler/run/schedule_optimizer.py:602` [Service] `best_score = (float(summary.failed_ops),) + objective_score(objective_name, best`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:172` [Service] `score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:296` [Service] `score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)`
- **被调用者**（4 个）：`tuple`, `float`, `getattr`, `objective_metric_keys`

## core/algorithms/greedy/algo_stats.py（Algorithm 层）

### `_empty_stats()` [私有]
- 位置：第 11-12 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ensure_algo_stats()` [公开]
- 位置：第 15-31 行
- 参数：target
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:143` [Algorithm] `ensure_algo_stats(self)`
- **被调用者**（4 个）：`isinstance`, `getattr`, `stats.get`, `_empty_stats`

### `snapshot_algo_stats()` [公开]
- 位置：第 34-50 行
- 参数：target
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:294` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/run/schedule_optimizer.py:604` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:173` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:297` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
- **被调用者**（9 个）：`ensure_algo_stats`, `deepcopy`, `_empty_stats`, `stats.get`, `isinstance`, `dict`, `part.items`, `list`, `str`

### `increment_counter()` [公开]
- 位置：第 53-70 行
- 参数：target, key, amount
- 返回类型：Constant(value=None, kind=None)
- **调用者**（31 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:172` [Service] `increment_counter(optimizer_algo_stats, counter_key, bucket="param_fallbacks")`
  - `core/services/scheduler/run/schedule_optimizer.py:496` [Service] `increment_counter(optimizer_algo_stats, "optimizer_seed_result_invalid_count", i`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:215` [Service] `increment_counter(optimizer_algo_stats if isinstance(optimizer_algo_stats, dict)`
  - `core/algorithms/greedy/external_groups.py:32` [Algorithm] `increment_counter(scheduler, "legacy_external_days_defaulted_count", legacy_defa`
  - `core/algorithms/greedy/scheduler.py:239` [Algorithm] `increment_counter(self, "seed_overlap_filtered_count", dropped)`
  - `core/algorithms/greedy/scheduler.py:333` [Algorithm] `increment_counter(self, "seed_missing_machine_id_count", missing_seed_machine)`
  - `core/algorithms/greedy/scheduler.py:340` [Algorithm] `increment_counter(self, "seed_missing_operator_id_count", missing_seed_operator)`
  - `core/algorithms/greedy/scheduler.py:457` [Algorithm] `increment_counter(self, "internal_auto_assign_attempt_count")`
  - `core/algorithms/greedy/scheduler.py:473` [Algorithm] `increment_counter(self, "internal_auto_assign_success_count")`
  - `core/algorithms/greedy/scheduler.py:476` [Algorithm] `increment_counter(self, "internal_auto_assign_failed_count")`
  - `core/algorithms/greedy/scheduler.py:481` [Algorithm] `increment_counter(self, "internal_missing_resource_without_auto_assign_count")`
  - `core/algorithms/greedy/scheduler.py:520` [Algorithm] `increment_counter(self, "internal_efficiency_fallback_count")`
  - `core/algorithms/greedy/schedule_params.py:132` [Algorithm] `increment_counter(`
  - `core/algorithms/greedy/schedule_params.py:227` [Algorithm] `increment_counter(`
  - `core/algorithms/greedy/schedule_params.py:247` [Algorithm] `increment_counter(algo_stats, "start_dt_parsed_count", bucket="param_fallbacks")`
  - `core/algorithms/greedy/schedule_params.py:253` [Algorithm] `increment_counter(algo_stats, "start_dt_default_now_count", bucket="param_fallba`
  - `core/algorithms/greedy/schedule_params.py:263` [Algorithm] `increment_counter(algo_stats, "end_date_ignored_count", bucket="param_fallbacks"`
  - `core/algorithms/greedy/seed.py:143` [Algorithm] `increment_counter(algo_stats, "seed_normalize_outer_exception_count")`
  - `core/algorithms/greedy/seed.py:146` [Algorithm] `increment_counter(algo_stats, "seed_op_id_backfilled_count", backfilled)`
  - `core/algorithms/greedy/seed.py:147` [Algorithm] `increment_counter(algo_stats, "seed_invalid_dropped_count", dropped_invalid)`
  - `core/algorithms/greedy/seed.py:148` [Algorithm] `increment_counter(algo_stats, "seed_bad_time_dropped_count", dropped_bad_time)`
  - `core/algorithms/greedy/seed.py:149` [Algorithm] `increment_counter(algo_stats, "seed_duplicate_dropped_count", dropped_dup)`
  - `core/algorithms/greedy/dispatch/sgs.py:115` [Algorithm] `increment_counter(scheduler, "dispatch_key_proc_hours_fallback_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:172` [Algorithm] `increment_counter(scheduler, "legacy_external_days_defaulted_count", legacy_defa`
  - `core/algorithms/greedy/dispatch/sgs.py:222` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_external_duration_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:237` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_external_duration_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:272` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_external_duration_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:287` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_external_duration_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:358` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_total_hours_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:400` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_missing_resource_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:522` [Algorithm] `increment_counter(scheduler, "dispatch_key_avg_proc_hours_fallback_count")`
- **被调用者**（5 个）：`ensure_algo_stats`, `stats.get`, `isinstance`, `int`, `current_bucket.get`

### `merge_algo_stats()` [公开]
- 位置：第 73-109 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（5 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:294` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/run/schedule_optimizer.py:604` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/run/schedule_optimizer.py:629` [Service] `algo_stats = merge_algo_stats(best_algo_stats) if isinstance(best_algo_stats, di`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:173` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:297` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
- **被调用者**（10 个）：`_empty_stats`, `isinstance`, `src.get`, `merged.get`, `part.items`, `bucket_out.get`, `existing_list.extend`, `int`, `list`, `str`

## core/algorithms/greedy/config_adapter.py（Algorithm 层）

### `read_schedule_config_value()` [公开]
- 位置：第 16-23 行
- 参数：config, key
- 返回类型：Name(id='CriticalConfigReadResult', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`ensure_schedule_config_snapshot`, `hasattr`, `CriticalConfigReadResult`, `getattr`

### `read_critical_schedule_config()` [公开]
- 位置：第 26-27 行
- 参数：config, key
- 返回类型：Name(id='CriticalConfigReadResult', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`read_schedule_config_value`

## core/algorithms/greedy/schedule_params.py（Algorithm 层）

### `_field_label()` [私有]
- 位置：第 31-32 行
- 参数：field
- 返回类型：Name(id='str', ctx=Load())

### `_snapshot_attr()` [私有]
- 位置：第 47-56 行
- 参数：snapshot, key
- 返回类型：Name(id='Any', ctx=Load())

### `_require_choice()` [私有]
- 位置：第 59-66 行
- 参数：raw_value
- 返回类型：Name(id='str', ctx=Load())

### `_require_weight()` [私有]
- 位置：第 69-70 行
- 参数：raw_value, key
- 返回类型：Name(id='float', ctx=Load())

### `_require_strategy_params_dict()` [私有]
- 位置：第 73-76 行
- 参数：strategy_params
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_config_default_for()` [私有]
- 位置：第 79-82 行
- 参数：key
- 返回类型：Name(id='Any', ctx=Load())

### `_build_runtime_snapshot()` [私有]
- 位置：第 85-92 行
- 参数：config
- 返回类型：Name(id='Any', ctx=Load())

### `_validate_runtime_field()` [私有]
- 位置：第 95-106 行
- 参数：config, field
- 返回类型：Constant(value=None, kind=None)

### `_weighted_override_value()` [私有]
- 位置：第 109-138 行
- 参数：raw_value, key
- 返回类型：Name(id='float', ctx=Load())

### `_weighted_strategy_params()` [私有]
- 位置：第 141-167 行
- 参数：source
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_require_yes_no()` [私有]
- 位置：第 170-175 行
- 参数：raw_value
- 返回类型：Name(id='str', ctx=Load())

### `resolve_schedule_params()` [公开]
- 位置：第 178-338 行
- 参数：无
- 返回类型：Name(id='ScheduleParams', ctx=Load())
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:145` [Algorithm] `params = resolve_schedule_params(`
- **被调用者**（33 个）：`set`, `parse_date`, `_require_choice`, `DispatchRule`, `ScheduleParams`, `_runtime_snapshot`, `_snapshot_attr`, `_record_snapshot_degradations`, `datetime.now`, `parse_datetime`, `strip`, `SortStrategy`, `dict`, `_snapshot_value`, `_require_yes_no`

## core/algorithms/greedy/scheduler.py（Algorithm 层）

### `normalize_text_id()` [公开]
- 位置：第 35-42 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`strip`, `str`

### `resolve_batch_sort_batch_id()` [公开]
- 位置：第 45-49 行
- 参数：batch_key, batch
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`normalize_text_id`, `getattr`

### `build_normalized_batches_map()` [公开]
- 位置：第 52-65 行
- 参数：batches
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:416` [Service] `normalized_batches_for_sort = build_normalized_batches_map(batches)`
- **被调用者**（5 个）：`items`, `resolve_batch_sort_batch_id`, `str`, `warnings.append`, `normalized.get`

### `_parse_due_date_for_sort()` [私有]
- 位置：第 68-69 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_parse_ready_date_for_sort()` [私有]
- 位置：第 72-73 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_parse_created_at_for_sort()` [私有]
- 位置：第 76-79 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `build_batch_sort_inputs()` [公开]
- 位置：第 82-105 行
- 参数：batches
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:419` [Service] `batch_for_sort = build_batch_sort_inputs(`
- **被调用者**（10 个）：`items`, `resolve_batch_sort_batch_id`, `batch_for_sort.append`, `BatchForSort`, `str`, `_parse_due_date_for_sort`, `_parse_ready_date_for_sort`, `_parse_created_at_for_sort`, `getattr`, `bool`

### `GreedyScheduler.__init__()` [私有]
- 位置：第 111-115 行
- 参数：calendar_service, config_service, logger
- 返回类型：无注解

### `GreedyScheduler.schedule()` [公开]
- 位置：第 117-408 行
- 参数：operations, batches, strategy, strategy_params, start_dt, end_date, machine_downtimes, batch_order_override, seed_results, dispatch_mode, dispatch_rule, resource_pool, strict_mode
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（4 处）：
  - `core/services/scheduler/run/schedule_optimizer_steps.py:83` [Service] `return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:85` [Service] `return scheduler.schedule(**kwargs)`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:88` [Service] `return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:92` [Service] `return scheduler.schedule(**kwargs)`
- **被调用者**（51 个）：`datetime.now`, `ensure_algo_stats`, `resolve_schedule_params`, `warnings.extend`, `build_normalized_batches_map`, `StrategyFactory.create`, `set`, `sorted`, `info`, `batches.items`, `total_seconds`, `int`, `ScheduleSummary`, `build_batch_sort_inputs`, `sorter.sort`

### `GreedyScheduler._schedule_external()` [私有]
- 位置：第 410-431 行
- 参数：op, batch, batch_progress, external_group_cache, base_time, errors, end_dt_exclusive, strict_mode
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `GreedyScheduler._schedule_internal()` [私有]
- 位置：第 433-536 行
- 参数：op, batch, batch_progress, machine_timeline, operator_timeline, base_time, errors, end_dt_exclusive, machine_downtimes
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `GreedyScheduler._auto_assign_internal_resources()` [私有]
- 位置：第 538-570 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

## core/algorithms/objective_specs.py（Algorithm 层）

### `normalize_objective_name()` [公开]
- 位置：第 54-56 行
- 参数：objective
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`lower`, `strip`, `str`

### `objective_metric_keys()` [公开]
- 位置：第 59-60 行
- 参数：objective
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/evaluation.py:285` [Algorithm] `return tuple(float(getattr(metrics, key)) for key in objective_metric_keys(objec`
- **被调用者**（1 个）：`normalize_objective_name`

### `comparison_metric_key()` [公开]
- 位置：第 63-64 行
- 参数：objective
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/viewmodels/scheduler_analysis_labels.py:19` [ViewModel] `return comparison_metric_key(value)`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:34` [Service] `return comparison_metric_key(objective_name)`
- **被调用者**（1 个）：`objective_metric_keys`

### `metric_label_for()` [公开]
- 位置：第 67-69 行
- 参数：metric_key
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_analysis_labels.py:43` [ViewModel] `return metric_label_for(key)`
- **被调用者**（4 个）：`lower`, `_METRIC_LABELS.get`, `strip`, `str`

### `best_score_schema_parts()` [公开]
- 位置：第 72-76 行
- 参数：objective
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`objective_metric_keys`, `tuple`, `metric_label_for`

### `best_score_schema()` [公开]
- 位置：第 79-83 行
- 参数：objective
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/summary/schedule_summary_assembly.py:38` [Service] `return best_score_schema(objective_name)`
- **被调用者**（3 个）：`int`, `enumerate`, `best_score_schema_parts`

### `objective_choice_labels()` [公开]
- 位置：第 86-87 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/viewmodels/scheduler_analysis_labels.py:27` [ViewModel] `choice_labels = objective_choice_labels()`
  - `web/viewmodels/scheduler_analysis_vm.py:247` [ViewModel] `"objective_choice_labels": objective_choice_labels(),`
- **被调用者**（1 个）：`dict`

## core/infrastructure/database.py（Infrastructure 层）

### `_is_windows_lock_error()` [私有]
- 位置：第 26-35 行
- 参数：e
- 返回类型：Name(id='bool', ctx=Load())

### `_cleanup_sqlite_sidecars()` [私有]
- 位置：第 38-47 行
- 参数：db_path, logger
- 返回类型：Constant(value=None, kind=None)

### `_restore_db_file_from_backup()` [私有]
- 位置：第 50-93 行
- 参数：backup_path, db_path, logger, retries, base_delay_s
- 返回类型：Constant(value=None, kind=None)

### `get_connection()` [公开]
- 位置：第 96-113 行
- 参数：db_path
- 返回类型：Attribute(value=Name(id='sqlite3', ctx=Load()), attr='Connec
- **调用者**（3 处）：
  - `web/bootstrap/factory.py:105` [Bootstrap] `conn = get_connection(bm.db_path)`
  - `web/bootstrap/factory.py:345` [Bootstrap] `conn = get_connection(app.config["DATABASE_PATH"])`
  - `web/bootstrap/plugins.py:158` [Bootstrap] `conn0 = get_connection(database_path)`
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
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_schema_create_table_statements()` [私有]
- 位置：第 144-152 行
- 参数：schema_sql
- 返回类型：Name(id='dict', ctx=Load())

### `_schema_index_statements()` [私有]
- 位置：第 155-163 行
- 参数：schema_sql
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_build_statement_script()` [私有]
- 位置：第 166-170 行
- 参数：statements
- 返回类型：Name(id='str', ctx=Load())

### `_missing_schema_tables()` [私有]
- 位置：第 173-175 行
- 参数：conn, schema_sql
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_bootstrap_missing_tables_from_schema()` [私有]
- 位置：第 178-202 行
- 参数：conn, schema_sql, logger
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_cleanup_probe_db()` [私有]
- 位置：第 205-212 行
- 参数：db_path
- 返回类型：Constant(value=None, kind=None)

### `_build_contract_error()` [私有]
- 位置：第 215-230 行
- 参数：无
- 返回类型：Name(id='MigrationContractError', ctx=Load())

### `_preflight_migration_contract()` [私有]
- 位置：第 233-290 行
- 参数：db_path
- 返回类型：Constant(value=None, kind=None)

### `ensure_schema()` [公开]
- 位置：第 293-379 行
- 参数：db_path, logger, schema_path, backup_dir
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/system_backup.py:258` [Route] `ensure_schema(`
  - `web/bootstrap/factory.py:273` [Bootstrap] `ensure_schema(`
- **被调用者**（22 个）：`abspath`, `get_connection`, `candidates.append`, `FileNotFoundError`, `exists`, `_migrate_with_backup`, `join`, `getattr`, `_load_schema_sql`, `_build_schema_exec_script`, `_has_no_user_tables`, `_ensure_schema_version`, `_get_schema_version`, `conn.commit`, `conn.close`

### `_ensure_schema_version()` [私有]
- 位置：第 382-405 行
- 参数：conn, logger
- 返回类型：Constant(value=None, kind=None)

### `_is_truly_empty_db()` [私有]
- 位置：第 408-414 行
- 参数：conn
- 返回类型：Name(id='bool', ctx=Load())

### `_list_user_tables()` [私有]
- 位置：第 417-428 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_has_no_user_tables()` [私有]
- 位置：第 431-432 行
- 参数：conn
- 返回类型：Name(id='bool', ctx=Load())

### `_detect_schema_is_current()` [私有]
- 位置：第 435-473 行
- 参数：conn
- 返回类型：Name(id='bool', ctx=Load())

### `_get_schema_version()` [私有]
- 位置：第 476-487 行
- 参数：conn
- 返回类型：Name(id='int', ctx=Load())

### `_set_schema_version()` [私有]
- 位置：第 490-491 行
- 参数：conn, version
- 返回类型：Constant(value=None, kind=None)

### `_migrate_with_backup()` [私有]
- 位置：第 494-605 行
- 参数：db_path, from_version, to_version, backup_dir
- 返回类型：Constant(value=None, kind=None)

### `_run_migration()` [私有]
- 位置：第 608-612 行
- 参数：conn, target_version, logger
- 返回类型：Name(id='MigrationOutcome', ctx=Load())

## core/models/schedule.py（Model 层）

### `Schedule.from_row()` [公开]
- 位置：第 23-41 行
- 参数：row
- 返回类型：Name(id='Schedule', ctx=Load())
- **调用者**（72 处）：
  - `core/services/scheduler/batch_service.py:197` [Service] `batch = payload if isinstance(payload, Batch) else Batch.from_row(payload)`
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
  - `data/repositories/machine_repo.py:46` [Repository] `return [Machine.from_row(r) for r in rows]`
  - `data/repositories/machine_repo.py:52` [Repository] `m = machine if isinstance(machine, Machine) else Machine.from_row(machine)`
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
  - `data/repositories/operator_repo.py:34` [Repository] `return [Operator.from_row(r) for r in rows]`
  - `data/repositories/operator_repo.py:40` [Repository] `op = operator if isinstance(operator, Operator) else Operator.from_row(operator)`
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
  - `data/repositories/resource_team_repo.py:16` [Repository] `return ResourceTeam.from_row(row) if row else None`
  - `data/repositories/resource_team_repo.py:23` [Repository] `return ResourceTeam.from_row(row) if row else None`
  - `data/repositories/resource_team_repo.py:35` [Repository] `return [ResourceTeam.from_row(r) for r in rows]`
  - `data/repositories/resource_team_repo.py:73` [Repository] `item = team if isinstance(team, ResourceTeam) else ResourceTeam.from_row(team)`
  - `data/repositories/schedule_history_repo.py:20` [Repository] `return ScheduleHistory.from_row(row) if row else None`
  - `data/repositories/schedule_history_repo.py:27` [Repository] `return [ScheduleHistory.from_row(r) for r in rows]`
  - `data/repositories/schedule_history_repo.py:34` [Repository] `return ScheduleHistory.from_row(row) if row else None`
  - `data/repositories/schedule_repo.py:25` [Repository] `return Schedule.from_row(row) if row else None`
  - `data/repositories/schedule_repo.py:32` [Repository] `return [Schedule.from_row(r) for r in rows]`
  - `data/repositories/schedule_repo.py:67` [Repository] `return [Schedule.from_row(r) for r in rows]`
  - `data/repositories/schedule_repo.py:287` [Repository] `return [Schedule.from_row(r) for r in rows]`
  - `data/repositories/schedule_repo.py:290` [Repository] `s = schedule if isinstance(schedule, Schedule) else Schedule.from_row(schedule)`
  - `data/repositories/schedule_repo.py:305` [Repository] `s = item if isinstance(item, Schedule) else Schedule.from_row(item)`
  - `data/repositories/supplier_repo.py:18` [Repository] `return Supplier.from_row(row) if row else None`
  - `data/repositories/supplier_repo.py:34` [Repository] `return [Supplier.from_row(r) for r in rows]`
  - `data/repositories/supplier_repo.py:37` [Repository] `s = supplier if isinstance(supplier, Supplier) else Supplier.from_row(supplier)`
  - `data/repositories/system_config_repo.py:18` [Repository] `return SystemConfig.from_row(row) if row else None`
  - `data/repositories/system_config_repo.py:40` [Repository] `return [SystemConfig.from_row(r) for r in rows]`
  - `data/repositories/system_job_state_repo.py:18` [Repository] `return SystemJobState.from_row(row) if row else None`
  - `data/repositories/system_job_state_repo.py:22` [Repository] `return [SystemJobState.from_row(r) for r in rows]`
- **被调用者**（6 个）：`get`, `cls`, `parse_int`, `str`, `lower`, `strip`

### `Schedule.to_dict()` [公开]
- 位置：第 43-56 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（81 处）：
  - `web/routes/equipment_pages.py:221` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:234` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:26` [Route] `items = [m.to_dict() for m in material_svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:24` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:45` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:165` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:116` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:117` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:118` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:147` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/system_backup.py:51` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:34` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:48` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:57` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:172` [Route] `d = it.to_dict()`
  - `web/routes/domains/scheduler/scheduler_analysis.py:17` [Route] `return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})`
  - `web/routes/domains/scheduler/scheduler_batches.py:58` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batches.py:96` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/domains/scheduler/scheduler_batches.py:189` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:196` [Route] `d = op.to_dict()`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:247` [Route] `batch=b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:21` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:410` [Route] `result = stats.to_dict()`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:139` [Route] `payload = exc.to_dict()`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:50` [Route] `selected_history = selected_history_item.to_dict() if hasattr(selected_history_i`
  - `web/viewmodels/scheduler_analysis_trends.py:107` [ViewModel] `d = h.to_dict() if hasattr(h, "to_dict") else (h if isinstance(h, dict) else {})`
  - `web/viewmodels/scheduler_analysis_trends.py:153` [ViewModel] `return selected_item.to_dict() if hasattr(selected_item, "to_dict") else (select`
  - `web/viewmodels/system_logs_vm.py:29` [ViewModel] `d = it.to_dict() if hasattr(it, "to_dict") else (it if isinstance(it, dict) else`
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
  - `core/services/scheduler/calendar_admin.py:306` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:373` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:378` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/gantt_contract.py:98` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:212` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:281` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_service.py:301` [Service] `"summary": orchestration.summary_contract.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:47` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:56` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:64` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:89` [Service] `left = a.to_dict()`
  - `core/services/scheduler/config/config_presets.py:90` [Service] `right = b.to_dict()`
  - `core/services/scheduler/config/config_presets.py:138` [Service] `canonical = snapshot.to_dict()`
  - `core/services/scheduler/config/config_presets.py:175` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config/config_presets.py:234` [Service] `return dict(snapshot.to_dict())`
  - `core/services/scheduler/config/config_presets.py:279` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/config/config_presets.py:343` [Service] `config_updates = [(key, str(value), None) for key, value in snap.to_dict().items`
  - `core/services/scheduler/config/config_service.py:45` [Service] `return self.snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:968` [Service] `payload = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:998` [Service] `values = snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1011` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1025` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1053` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1084` [Service] `values = normalized_snapshot.to_dict()`
  - `core/services/scheduler/run/schedule_optimizer.py:320` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer.py:334` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:183` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:210` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:399` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:414` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/summary/schedule_summary.py:82` [Service] `return snapshot.to_dict().get(str(key or "").strip())`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:30` [Service] `).to_dict()`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:220` [Service] `"metrics": ctx.best_metrics.to_dict() if ctx.best_metrics is not None else None,`
- **被调用者**（1 个）：`as_dict`

## core/services/common/degradation.py（Service 层）

### `DegradationCollector.__init__()` [私有]
- 位置：第 44-48 行
- 参数：events
- 返回类型：无注解

### `DegradationCollector.__bool__()` [私有]
- 位置：第 50-51 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `DegradationCollector.__len__()` [私有]
- 位置：第 53-54 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())

### `DegradationCollector.add()` [公开]
- 位置：第 56-103 行
- 参数：event
- 返回类型：Name(id='DegradationEvent', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/gantt_service.py:223` [Service] `degradation_collector.add(`
- **被调用者**（8 个）：`get`, `DegradationEvent`, `len`, `append`, `ValueError`, `str`, `max`, `int`

### `DegradationCollector.extend()` [公开]
- 位置：第 105-111 行
- 参数：events
- 返回类型：Constant(value=None, kind=None)
- **调用者**（45 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:41` [Route] `normalized.extend(str(item).strip() for item in (hidden_warnings or []) if str(i`
  - `web/bootstrap/launcher.py:721` [Bootstrap] `paths.extend(`
  - `web/bootstrap/plugins.py:43` [Bootstrap] `merged.extend(collector.to_list())`
  - `web/viewmodels/page_manuals_common.py:204` [ViewModel] `lines.extend([f"### {section['title']}", "", section["body_md"], ""])`
  - `web/viewmodels/page_manuals_common.py:206` [ViewModel] `lines.extend(["## 相关模块说明", ""])`
  - `web/viewmodels/page_manuals_common.py:208` [ViewModel] `lines.extend([f"### {item['title']}", "", item.get("summary") or "", ""])`
  - `web/viewmodels/page_manuals_common.py:210` [ViewModel] `lines.extend([f"#### {section['title']}", "", section["body_md"], ""])`
  - `core/services/process/route_parser.py:239` [Service] `errors.extend(_strict_supplier_issue_messages(issue_messages, op_type_name=op_ty`
  - `core/services/process/route_parser.py:244` [Service] `warnings.extend([msg for msg in issue_messages if msg])`
  - `core/services/process/unit_excel/parser.py:158` [Service] `operator_names.extend(self._extract_names(ln))`
  - `core/services/process/unit_excel/parser.py:165` [Service] `operator_names.extend(self._extract_names(" ".join(tokens[1:])))`
  - `core/services/scheduler/gantt_service.py:216` [Service] `degradation_collector.extend(calendar_days_outcome.events)`
  - `core/services/scheduler/gantt_service.py:217` [Service] `degradation_collector.extend(tasks_outcome.events)`
  - `core/services/scheduler/gantt_tasks.py:254` [Service] `collector.extend(outcome.events)`
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
  - `core/services/scheduler/config/config_service.py:1177` [Service] `plan.updates.extend(`
  - `core/services/scheduler/config/config_service.py:1199` [Service] `plan.updates.extend(`
  - `core/services/scheduler/config/config_service.py:1246` [Service] `plan.updates.extend(`
  - `core/services/scheduler/config/config_service.py:1418` [Service] `updates.extend(self._active_preset_updates(self.BUILTIN_PRESET_DEFAULT))`
  - `core/services/scheduler/run/schedule_input_builder.py:137` [Service] `merge_event_collector.extend(lookup.events)`
  - `core/services/scheduler/run/schedule_input_builder.py:138` [Service] `collector.extend(lookup.events)`
  - `core/services/scheduler/run/schedule_input_builder.py:158` [Service] `collector.extend(merge_event_collector.to_list()[merge_event_count_before:])`
  - `core/services/scheduler/run/schedule_input_collector.py:123` [Service] `operations.extend(list(svc.op_repo.list_by_batch(batch_id) or []))`
  - `core/services/scheduler/run/schedule_input_runtime_support.py:74` [Service] `algo_warnings.extend(list(pool_warnings or []))`
  - `core/services/scheduler/run/schedule_orchestrator.py:205` [Service] `summary_warnings.extend(algo_warnings)`
  - `data/repositories/part_operation_repo.py:147` [Repository] `params.extend([part_no, int(seq)])`
  - `data/repositories/schedule_repo.py:109` [Repository] `out.extend(self.fetchall(sql, tuple(params)))`
  - `data/repositories/schedule_repo.py:226` [Repository] `params.extend([scope_id, scope_id])`
  - `core/algorithms/greedy/algo_stats.py:107` [Algorithm] `existing_list.extend(value)`
  - `core/algorithms/greedy/scheduler.py:157` [Algorithm] `warnings.extend(params.warnings)`
  - `core/algorithms/greedy/scheduler.py:222` [Algorithm] `warnings.extend(seed_warnings)`
  - `tools/quality_gate_scan.py:543` [Tool] `assignments_by_scope[scope].extend(_collect_name_bindings([node]))`
  - `tools/quality_gate_scan.py:545` [Tool] `assignments_by_scope[scope].extend(_collect_name_bindings([node]))`
- **被调用者**（3 个）：`isinstance`, `events.to_list`, `self.add`

### `DegradationCollector.to_list()` [公开]
- 位置：第 113-114 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（18 处）：
  - `web/bootstrap/plugins.py:43` [Bootstrap] `merged.extend(collector.to_list())`
  - `web/bootstrap/plugins.py:45` [Bootstrap] `base["degradation_events"] = degradation_events_to_dicts(merged.to_list())`
  - `core/services/common/build_outcome.py:33` [Service] `self.events = collector.to_list()`
  - `core/services/common/build_outcome.py:62` [Service] `events=collector.to_list() if collector is not None else [],`
  - `core/services/process/unit_excel/template_builder.py:72` [Service] `"events": degradation_events_to_dicts(collector.to_list()),`
  - `core/services/scheduler/gantt_service.py:242` [Service] `degradation_events=degradation_events_to_dicts(degradation_collector.to_list()),`
  - `core/services/scheduler/resource_dispatch_support.py:155` [Service] `"degradation_events": degradation_events_to_dicts(collector.to_list()),`
  - `core/services/scheduler/config/config_snapshot.py:257` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/config/config_snapshot.py:389` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/config/config_validator.py:232` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/run/schedule_input_builder.py:158` [Service] `collector.extend(merge_event_collector.to_list()[merge_event_count_before:])`
  - `core/services/scheduler/run/schedule_input_builder.py:196` [Service] `merge_context_events=degradation_events_to_dicts(merge_event_collector.to_list()`
  - `core/services/scheduler/run/schedule_template_lookup.py:118` [Service] `return TemplateGroupLookupOutcome(None, None, True, collector.to_list())`
  - `core/services/scheduler/run/schedule_template_lookup.py:122` [Service] `return TemplateGroupLookupOutcome(tmpl, None, False, collector.to_list())`
  - `core/services/scheduler/run/schedule_template_lookup.py:136` [Service] `return TemplateGroupLookupOutcome(tmpl, None, True, collector.to_list())`
  - `core/services/scheduler/run/schedule_template_lookup.py:138` [Service] `return TemplateGroupLookupOutcome(tmpl, grp, False, collector.to_list())`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:357` [Service] `return {"events": degradation_events_to_dicts(collector.to_list()), "counters": `
  - `core/algorithms/greedy/schedule_params.py:128` [Algorithm] `for event in collector.to_list():`
- **被调用者**（1 个）：`list`

### `DegradationCollector.to_counters()` [公开]
- 位置：第 116-120 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（19 处）：
  - `web/bootstrap/plugins.py:46` [Bootstrap] `base["degradation_counters"] = merged.to_counters()`
  - `web/bootstrap/plugins.py:172` [Bootstrap] `if int(collector.to_counters().get("plugin_bootstrap_config_reader_failed") or 0`
  - `core/services/common/build_outcome.py:35` [Service] `merged_counters = collector.to_counters()`
  - `core/services/process/unit_excel/template_builder.py:73` [Service] `"counters": collector.to_counters(),`
  - `core/services/scheduler/gantt_service.py:243` [Service] `degradation_counters=degradation_collector.to_counters(),`
  - `core/services/scheduler/gantt_tasks.py:261` [Service] `if not tasks and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/gantt_week_plan.py:82` [Service] `if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/resource_dispatch_rows.py:151` [Service] `if not prepared_rows and collector.to_counters().get("bad_time_row_skipped", 0) `
  - `core/services/scheduler/resource_dispatch_rows.py:254` [Service] `if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/resource_dispatch_rows.py:348` [Service] `if not tasks and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/resource_dispatch_rows.py:477` [Service] `if not out_rows and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/resource_dispatch_support.py:156` [Service] `"degradation_counters": collector.to_counters(),`
  - `core/services/scheduler/resource_dispatch_support.py:213` [Service] `if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/config/config_snapshot.py:260` [Service] `collector.to_counters(),`
  - `core/services/scheduler/config/config_snapshot.py:390` [Service] `degradation_counters=collector.to_counters(),`
  - `core/services/scheduler/config/config_validator.py:233` [Service] `degradation_counters=collector.to_counters(),`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:357` [Service] `return {"events": degradation_events_to_dicts(collector.to_list()), "counters": `
  - `core/algorithms/greedy/external_groups.py:29` [Algorithm] `counters = collector.to_counters()`
  - `core/algorithms/greedy/dispatch/sgs.py:169` [Algorithm] `counters = collector.to_counters()`
- **被调用者**（2 个）：`counters.get`, `int`

### `degradation_event_to_dict()` [公开]
- 位置：第 123-131 行
- 参数：event
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`str`, `int`

### `degradation_events_to_dicts()` [公开]
- 位置：第 134-135 行
- 参数：events
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（11 处）：
  - `web/bootstrap/plugins.py:45` [Bootstrap] `base["degradation_events"] = degradation_events_to_dicts(merged.to_list())`
  - `core/services/process/unit_excel/template_builder.py:72` [Service] `"events": degradation_events_to_dicts(collector.to_list()),`
  - `core/services/scheduler/gantt_service.py:242` [Service] `degradation_events=degradation_events_to_dicts(degradation_collector.to_list()),`
  - `core/services/scheduler/gantt_service.py:278` [Service] `"degradation_events": degradation_events_to_dicts(outcome.events),`
  - `core/services/scheduler/resource_dispatch_support.py:155` [Service] `"degradation_events": degradation_events_to_dicts(collector.to_list()),`
  - `core/services/scheduler/config/config_snapshot.py:257` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/config/config_snapshot.py:389` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/config/config_validator.py:232` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/run/schedule_input_builder.py:196` [Service] `merge_context_events=degradation_events_to_dicts(merge_event_collector.to_list()`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:91` [Service] `event_dicts = degradation_events_to_dicts(input_build_outcome.events)`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:357` [Service] `return {"events": degradation_events_to_dicts(collector.to_list()), "counters": `
- **被调用者**（1 个）：`degradation_event_to_dict`

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
  - `web/routes/equipment_pages.py:204` [Route] `links = link_svc.list_by_machine(machine_id)`
  - `web/routes/equipment_pages.py:205` [Route] `downtimes = dt_svc.list_by_machine(machine_id, include_cancelled=False)`
  - `core/services/personnel/operator_machine_service.py:292` [Service] `return [self._normalize_link(link) for link in self.repo.list_by_machine(mc_id)]`
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
- 位置：第 228-243 行
- 参数：downtime_id, machine_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/equipment_downtimes.py:90` [Route] `svc.cancel(downtime_id=downtime_id, machine_id=machine_id)`
- **被调用者**（6 个）：`self.get`, `self._normalize_text`, `strip`, `BusinessError`, `transaction`, `int`

## core/services/equipment/machine_service.py（Service 层）

### `MachineService.__init__()` [私有]
- 位置：第 16-24 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `MachineService._normalize_text()` [私有]
- 位置：第 30-31 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `MachineService._normalize_status()` [私有]
- 位置：第 34-61 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `MachineService._validate_machine_fields()` [私有]
- 位置：第 63-94 行
- 参数：machine_id, name, status, op_type_id, team_id, allow_partial
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `MachineService._get_or_raise()` [私有]
- 位置：第 96-100 行
- 参数：machine_id
- 返回类型：Name(id='Machine', ctx=Load())

### `MachineService.list()` [公开]
- 位置：第 105-131 行
- 参数：status, op_type_id, team_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/equipment_excel_links.py:68` [Route] `"machine_ids": sorted([str(machine.machine_id) for machine in machine_svc.list(s`
  - `web/routes/personnel_excel_links.py:68` [Route] `"machine_ids": sorted([str(machine.machine_id) for machine in machine_svc.list(s`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:52` [Route] `machines_active = machine_svc.list(status=MachineStatus.ACTIVE.value)`
  - `core/services/scheduler/resource_dispatch_service.py:131` [Service] `for item in self.machine_service.list()`
- **被调用者**（5 个）：`self._normalize_status`, `get`, `self._validate_machine_fields`, `ValidationError`, `BusinessError`

### `MachineService.get()` [公开]
- 位置：第 133-137 行
- 参数：machine_id
- 返回类型：Name(id='Machine', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self._normalize_text`, `self._get_or_raise`, `ValidationError`

### `MachineService.get_optional()` [公开]
- 位置：第 139-146 行
- 参数：machine_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（11 处）：
  - `web/routes/equipment_excel_machines.py:78` [Route] `ot = op_type_svc.get_optional(v)`
  - `web/routes/process_excel_suppliers.py:73` [Route] `ot = op_type_svc.get_optional(v)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:58` [Route] `extra = machine_svc.get_optional(mid)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:87` [Route] `extra = operator_svc.get_optional(oid)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:116` [Route] `extra = supplier_svc.get_optional(sid)`
  - `core/services/personnel/resource_team_service.py:98` [Service] `team = self.get_optional(v)`
  - `core/services/personnel/resource_team_service.py:109` [Service] `team = self.get_optional(team_id)`
  - `core/services/process/op_type_service.py:92` [Service] `ot = self.get_optional(v)`
  - `core/services/scheduler/resource_dispatch_service.py:100` [Service] `return self.operator_service.get_optional(scope_id)`
  - `core/services/scheduler/resource_dispatch_service.py:102` [Service] `return self.machine_service.get_optional(scope_id)`
  - `core/services/scheduler/resource_dispatch_service.py:103` [Service] `return self.team_service.get_optional(scope_id)`
- **被调用者**（2 个）：`self._normalize_text`, `get`

### `MachineService.create()` [公开]
- 位置：第 148-187 行
- 参数：machine_id, name, op_type_id, category, status, remark, team_id
- 返回类型：Name(id='Machine', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`self._validate_machine_fields`, `self._normalize_text`, `exists`, `self._get_or_raise`, `ValidationError`, `BusinessError`, `transaction`

### `MachineService.update()` [公开]
- 位置：第 189-238 行
- 参数：machine_id, name, op_type_id, category, status, remark, team_id
- 返回类型：Name(id='Machine', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`self._normalize_text`, `self._get_or_raise`, `ValidationError`, `self._normalize_status`, `self._validate_machine_fields`, `transaction`, `get`, `BusinessError`

### `MachineService.set_status()` [公开]
- 位置：第 240-241 行
- 参数：machine_id, status
- 返回类型：Name(id='Machine', ctx=Load())
- **调用者**（4 处）：
  - `web/routes/equipment_pages.py:269` [Route] `m = svc.set_status(machine_id=machine_id, status=status)`
  - `web/routes/equipment_pages.py:304` [Route] `svc.set_status(mid, status=status)`
  - `web/routes/personnel_pages.py:200` [Route] `op = svc.set_status(operator_id=operator_id, status=status)`
  - `web/routes/personnel_pages.py:235` [Route] `svc.set_status(oid, status=status)`
- **被调用者**（1 个）：`self.update`

### `MachineService.delete()` [公开]
- 位置：第 243-256 行
- 参数：machine_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`self._normalize_text`, `self._get_or_raise`, `is_referenced_by_batch_operations`, `is_referenced_by_schedule`, `ValidationError`, `BusinessError`, `transaction`

### `MachineService.build_existing_for_excel()` [公开]
- 位置：第 261-279 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（14 处）：
  - `web/routes/equipment_excel_machines.py:135` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/equipment_excel_machines.py:179` [Route] `existing = m_svc.build_existing_for_excel()`
  - `web/routes/equipment_excel_machines.py:250` [Route] `existing = m_svc.build_existing_for_excel()`
  - `web/routes/excel_demo.py:40` [Route] `return OperatorService(conn, op_logger=None).build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:96` [Route] `existing = op_svc.build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:122` [Route] `existing = op_svc.build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:197` [Route] `existing = op_svc.build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:328` [Route] `existing = OperatorService(g.db, op_logger=getattr(g, "op_logger", None)).build_`
  - `web/routes/process_excel_op_types.py:123` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_op_types.py:146` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_op_types.py:192` [Route] `existing = op_type_svc.build_existing_for_excel()`
  - `web/routes/process_excel_suppliers.py:110` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_suppliers.py:133` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_suppliers.py:209` [Route] `existing = supplier_svc.build_existing_for_excel()`
- **被调用者**（3 个）：`list`, `op_types.get`, `team_names.get`

### `MachineService.list_for_export()` [公开]
- 位置：第 281-285 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/equipment_excel_machines.py:386` [Route] `rows = m_svc.list_for_export()`
  - `core/services/process/supplier_service.py:222` [Service] `返回字段由 SupplierRepository.list_for_export() 定义：`
  - `core/services/process/supplier_service.py:225` [Service] `return self.repo.list_for_export()`

### `MachineService.ensure_replace_allowed()` [公开]
- 位置：第 287-301 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `core/services/equipment/machine_excel_import_service.py:60` [Service] `self.machine_svc.ensure_replace_allowed()`
  - `core/services/personnel/operator_excel_import_service.py:44` [Service] `self.svc.ensure_replace_allowed()`
  - `core/services/process/op_type_excel_import_service.py:42` [Service] `self.svc.ensure_replace_allowed()`
  - `core/services/process/supplier_excel_import_service.py:58` [Service] `self.svc.ensure_replace_allowed()`
- **被调用者**（3 个）：`has_any_batch_operations_machine_reference`, `has_any_schedule_machine_reference`, `BusinessError`

## core/services/personnel/operator_service.py（Service 层）

### `OperatorService.__init__()` [私有]
- 位置：第 16-22 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `OperatorService._normalize_text()` [私有]
- 位置：第 28-29 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorService._validate_operator_fields()` [私有]
- 位置：第 31-59 行
- 参数：operator_id, name, status, team_id, allow_partial
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorService._get_or_raise()` [私有]
- 位置：第 61-65 行
- 参数：operator_id
- 返回类型：Name(id='Operator', ctx=Load())

### `OperatorService.list()` [公开]
- 位置：第 70-83 行
- 参数：status, team_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（5 处）：
  - `web/routes/equipment_excel_links.py:67` [Route] `"operator_ids": sorted([str(op.operator_id) for op in operator_svc.list(status=N`
  - `web/routes/equipment_pages.py:210` [Route] `operators = {o.operator_id: o for o in operator_svc.list()}`
  - `web/routes/personnel_excel_links.py:67` [Route] `"operator_ids": sorted([str(op.operator_id) for op in operator_svc.list(status=N`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:81` [Route] `operators_active = operator_svc.list(status=OperatorStatus.ACTIVE.value)`
  - `core/services/scheduler/resource_dispatch_service.py:121` [Service] `for item in self.operator_service.list()`
- **被调用者**（2 个）：`self._validate_operator_fields`, `ValidationError`

### `OperatorService.get()` [公开]
- 位置：第 85-94 行
- 参数：operator_id
- 返回类型：Name(id='Operator', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self._validate_operator_fields`, `self._get_or_raise`, `ValidationError`

### `OperatorService.get_optional()` [公开]
- 位置：第 96-108 行
- 参数：operator_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（11 处）：
  - `web/routes/equipment_excel_machines.py:78` [Route] `ot = op_type_svc.get_optional(v)`
  - `web/routes/process_excel_suppliers.py:73` [Route] `ot = op_type_svc.get_optional(v)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:58` [Route] `extra = machine_svc.get_optional(mid)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:87` [Route] `extra = operator_svc.get_optional(oid)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:116` [Route] `extra = supplier_svc.get_optional(sid)`
  - `core/services/personnel/resource_team_service.py:98` [Service] `team = self.get_optional(v)`
  - `core/services/personnel/resource_team_service.py:109` [Service] `team = self.get_optional(team_id)`
  - `core/services/process/op_type_service.py:92` [Service] `ot = self.get_optional(v)`
  - `core/services/scheduler/resource_dispatch_service.py:100` [Service] `return self.operator_service.get_optional(scope_id)`
  - `core/services/scheduler/resource_dispatch_service.py:102` [Service] `return self.machine_service.get_optional(scope_id)`
  - `core/services/scheduler/resource_dispatch_service.py:103` [Service] `return self.team_service.get_optional(scope_id)`
- **被调用者**（2 个）：`self._validate_operator_fields`, `get`

### `OperatorService.create()` [公开]
- 位置：第 110-143 行
- 参数：operator_id, name, status, remark, team_id
- 返回类型：Name(id='Operator', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`self._validate_operator_fields`, `self._normalize_text`, `exists`, `self._get_or_raise`, `ValidationError`, `BusinessError`, `transaction`

### `OperatorService.update()` [公开]
- 位置：第 145-176 行
- 参数：operator_id, name, status, remark, team_id
- 返回类型：Name(id='Operator', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`self._validate_operator_fields`, `self._get_or_raise`, `ValidationError`, `self._normalize_text`, `transaction`

### `OperatorService.set_status()` [公开]
- 位置：第 178-179 行
- 参数：operator_id, status
- 返回类型：Name(id='Operator', ctx=Load())
- **调用者**（4 处）：
  - `web/routes/equipment_pages.py:269` [Route] `m = svc.set_status(machine_id=machine_id, status=status)`
  - `web/routes/equipment_pages.py:304` [Route] `svc.set_status(mid, status=status)`
  - `web/routes/personnel_pages.py:200` [Route] `op = svc.set_status(operator_id=operator_id, status=status)`
  - `web/routes/personnel_pages.py:235` [Route] `svc.set_status(oid, status=status)`
- **被调用者**（1 个）：`self.update`

### `OperatorService.delete()` [公开]
- 位置：第 181-214 行
- 参数：operator_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`self._validate_operator_fields`, `self._get_or_raise`, `is_referenced_by_batch_operations`, `is_referenced_by_schedule`, `ValidationError`, `BusinessError`, `transaction`

### `OperatorService.build_existing_for_excel()` [公开]
- 位置：第 219-235 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（14 处）：
  - `web/routes/equipment_excel_machines.py:135` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/equipment_excel_machines.py:179` [Route] `existing = m_svc.build_existing_for_excel()`
  - `web/routes/equipment_excel_machines.py:250` [Route] `existing = m_svc.build_existing_for_excel()`
  - `web/routes/excel_demo.py:40` [Route] `return OperatorService(conn, op_logger=None).build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:96` [Route] `existing = op_svc.build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:122` [Route] `existing = op_svc.build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:197` [Route] `existing = op_svc.build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:328` [Route] `existing = OperatorService(g.db, op_logger=getattr(g, "op_logger", None)).build_`
  - `web/routes/process_excel_op_types.py:123` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_op_types.py:146` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_op_types.py:192` [Route] `existing = op_type_svc.build_existing_for_excel()`
  - `web/routes/process_excel_suppliers.py:110` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_suppliers.py:133` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_suppliers.py:209` [Route] `existing = supplier_svc.build_existing_for_excel()`
- **被调用者**（2 个）：`list`, `team_names.get`

### `OperatorService.ensure_replace_allowed()` [公开]
- 位置：第 237-251 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `core/services/equipment/machine_excel_import_service.py:60` [Service] `self.machine_svc.ensure_replace_allowed()`
  - `core/services/personnel/operator_excel_import_service.py:44` [Service] `self.svc.ensure_replace_allowed()`
  - `core/services/process/op_type_excel_import_service.py:42` [Service] `self.svc.ensure_replace_allowed()`
  - `core/services/process/supplier_excel_import_service.py:58` [Service] `self.svc.ensure_replace_allowed()`
- **被调用者**（3 个）：`has_any_batch_operations_operator_reference`, `has_any_schedule_operator_reference`, `BusinessError`

## core/services/personnel/resource_team_service.py（Service 层）

### `ResourceTeamService.__init__()` [私有]
- 位置：第 14-19 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ResourceTeamService._normalize_text()` [私有]
- 位置：第 22-23 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ResourceTeamService._validate_fields()` [私有]
- 位置：第 25-49 行
- 参数：team_id, name, status, allow_partial
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ResourceTeamService._get_or_raise()` [私有]
- 位置：第 51-55 行
- 参数：team_id
- 返回类型：Name(id='ResourceTeam', ctx=Load())

### `ResourceTeamService.list()` [公开]
- 位置：第 57-63 行
- 参数：status
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._validate_fields`, `ValidationError`

### `ResourceTeamService.list_with_counts()` [公开]
- 位置：第 65-71 行
- 参数：status
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/personnel_teams.py:23` [Route] `rows = svc.list_with_counts()`
- **被调用者**（2 个）：`self._validate_fields`, `ValidationError`

### `ResourceTeamService.list_options()` [公开]
- 位置：第 73-74 行
- 参数：status
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/team_view_helpers.py:11` [Route] `return ResourceTeamService(g.db, op_logger=getattr(g, "op_logger", None)).list_o`
- **被调用者**（2 个）：`team.to_dict`, `self.list`

### `ResourceTeamService.get()` [公开]
- 位置：第 76-80 行
- 参数：team_id
- 返回类型：Name(id='ResourceTeam', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self._validate_fields`, `self._get_or_raise`, `ValidationError`

### `ResourceTeamService.get_optional()` [公开]
- 位置：第 82-86 行
- 参数：team_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（9 处）：
  - `web/routes/equipment_excel_machines.py:78` [Route] `ot = op_type_svc.get_optional(v)`
  - `web/routes/process_excel_suppliers.py:73` [Route] `ot = op_type_svc.get_optional(v)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:58` [Route] `extra = machine_svc.get_optional(mid)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:87` [Route] `extra = operator_svc.get_optional(oid)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:116` [Route] `extra = supplier_svc.get_optional(sid)`
  - `core/services/process/op_type_service.py:92` [Service] `ot = self.get_optional(v)`
  - `core/services/scheduler/resource_dispatch_service.py:100` [Service] `return self.operator_service.get_optional(scope_id)`
  - `core/services/scheduler/resource_dispatch_service.py:102` [Service] `return self.machine_service.get_optional(scope_id)`
  - `core/services/scheduler/resource_dispatch_service.py:103` [Service] `return self.team_service.get_optional(scope_id)`
- **被调用者**（2 个）：`self._validate_fields`, `get`

### `ResourceTeamService.get_by_name_optional()` [公开]
- 位置：第 88-92 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（3 处）：
  - `web/routes/equipment_excel_machines.py:80` [Route] `ot = op_type_svc.get_by_name_optional(v)`
  - `web/routes/process_excel_suppliers.py:75` [Route] `ot = op_type_svc.get_by_name_optional(v)`
  - `core/services/process/op_type_service.py:94` [Service] `ot = self.get_by_name_optional(v)`
- **被调用者**（2 个）：`self._normalize_text`, `get_by_name`

### `ResourceTeamService.resolve_team_id_optional()` [公开]
- 位置：第 94-103 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `core/services/equipment/machine_excel_import_service.py:88` [Service] `payload["team_id"] = self.team_svc.resolve_team_id_optional(data.get("班组"))`
  - `core/services/personnel/operator_excel_import_service.py:65` [Service] `team_id = self.team_svc.resolve_team_id_optional(data.get("班组")) if team_in_payl`
- **被调用者**（4 个）：`self._normalize_text`, `self.get_optional`, `self.get_by_name_optional`, `ValidationError`

### `ResourceTeamService.resolve_team_name_optional()` [公开]
- 位置：第 105-110 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（6 处）：
  - `web/routes/equipment_excel_machines.py:173` [Route] `item["班组"] = team_svc.resolve_team_name_optional(item.get("班组"))`
  - `web/routes/equipment_excel_machines.py:196` [Route] `row["班组"] = team_svc.resolve_team_name_optional(row.get("班组"))`
  - `web/routes/equipment_excel_machines.py:282` [Route] `row["班组"] = team_svc.resolve_team_name_optional(row.get("班组"))`
  - `web/routes/personnel_excel_operators.py:131` [Route] `item["班组"] = team_svc.resolve_team_name_optional(item.get("班组"))`
  - `web/routes/personnel_excel_operators.py:143` [Route] `row["班组"] = team_svc.resolve_team_name_optional(row.get("班组"))`
  - `web/routes/personnel_excel_operators.py:222` [Route] `row["班组"] = team_svc.resolve_team_name_optional(row.get("班组"))`
- **被调用者**（2 个）：`self.resolve_team_id_optional`, `self.get_optional`

### `ResourceTeamService.get_usage_counts()` [公开]
- 位置：第 112-119 行
- 参数：team_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`self._validate_fields`, `ValidationError`, `count_operator_refs`, `count_machine_refs`

### `ResourceTeamService.create()` [公开]
- 位置：第 121-150 行
- 参数：team_id, name, status, remark
- 返回类型：Name(id='ResourceTeam', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`self._validate_fields`, `self._normalize_text`, `exists`, `get_by_name`, `self._get_or_raise`, `ValidationError`, `BusinessError`, `transaction`

### `ResourceTeamService.update()` [公开]
- 位置：第 152-179 行
- 参数：team_id, name, status, remark
- 返回类型：Name(id='ResourceTeam', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`self._validate_fields`, `self._get_or_raise`, `ValidationError`, `get_by_name`, `self._normalize_text`, `transaction`, `BusinessError`

### `ResourceTeamService.delete()` [公开]
- 位置：第 181-197 行
- 参数：team_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`self._validate_fields`, `self._get_or_raise`, `self.get_usage_counts`, `int`, `ValidationError`, `BusinessError`, `transaction`, `counts.get`

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
  - `core/services/process/part_service.py:547` [Service] `check = self.deletion_validator.can_delete(del_ops, to_delete=to_delete)`
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

### `DeletionValidator.get_deletion_groups()` [公开]
- 位置：第 167-200 行
- 参数：operations
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `core/services/process/part_service.py:538` [Service] `deletable_groups = self.deletion_validator.get_deletion_groups(del_ops)  # List[`
  - `core/services/process/part_service.py:561` [Service] `规则：根据 DeletionValidator.get_deletion_groups() 返回的首/尾外部工序组匹配 group_id。`
  - `core/services/process/part_service.py:571` [Service] `deletable_groups = self.deletion_validator.get_deletion_groups(del_ops)  # List[`
- **被调用者**（7 个）：`sorted`, `reversed`, `groups.append`, `self._norm_source`, `head_group.append`, `tail_group.insert`, `self._norm_status`

## core/services/process/op_type_service.py（Service 层）

### `OpTypeService.__init__()` [私有]
- 位置：第 16-21 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `OpTypeService._normalize_text()` [私有]
- 位置：第 24-25 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OpTypeService._validate_fields()` [私有]
- 位置：第 27-51 行
- 参数：op_type_id, name, category, allow_partial
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OpTypeService._get_or_raise()` [私有]
- 位置：第 53-57 行
- 参数：op_type_id
- 返回类型：Name(id='OpType', ctx=Load())

### `OpTypeService.list()` [公开]
- 位置：第 59-65 行
- 参数：category
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `web/routes/equipment_excel_machines.py:94` [Route] `for ot in sorted(op_type_svc.list(), key=lambda item: str(item.op_type_id))`
  - `web/routes/equipment_pages.py:135` [Route] `op_types = {ot.op_type_id: ot for ot in op_type_svc.list()}`
  - `web/routes/equipment_pages.py:209` [Route] `op_types = {ot.op_type_id: ot for ot in op_type_svc.list()}`
  - `web/routes/process_excel_suppliers.py:89` [Route] `for ot in sorted(op_type_svc.list(), key=lambda item: str(item.op_type_id))`
  - `web/routes/process_suppliers.py:29` [Route] `op_types = {ot.op_type_id: ot for ot in OpTypeService(g.db).list()}  # type: ign`
  - `web/routes/process_suppliers.py:79` [Route] `op_types = {ot.op_type_id: ot for ot in OpTypeService(g.db).list()}  # type: ign`
- **被调用者**（2 个）：`self._validate_fields`, `ValidationError`

### `OpTypeService.get()` [公开]
- 位置：第 67-71 行
- 参数：op_type_id
- 返回类型：Name(id='OpType', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self._validate_fields`, `self._get_or_raise`, `ValidationError`

### `OpTypeService.get_optional()` [公开]
- 位置：第 73-77 行
- 参数：op_type_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（10 处）：
  - `web/routes/equipment_excel_machines.py:78` [Route] `ot = op_type_svc.get_optional(v)`
  - `web/routes/process_excel_suppliers.py:73` [Route] `ot = op_type_svc.get_optional(v)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:58` [Route] `extra = machine_svc.get_optional(mid)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:87` [Route] `extra = operator_svc.get_optional(oid)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:116` [Route] `extra = supplier_svc.get_optional(sid)`
  - `core/services/personnel/resource_team_service.py:98` [Service] `team = self.get_optional(v)`
  - `core/services/personnel/resource_team_service.py:109` [Service] `team = self.get_optional(team_id)`
  - `core/services/scheduler/resource_dispatch_service.py:100` [Service] `return self.operator_service.get_optional(scope_id)`
  - `core/services/scheduler/resource_dispatch_service.py:102` [Service] `return self.machine_service.get_optional(scope_id)`
  - `core/services/scheduler/resource_dispatch_service.py:103` [Service] `return self.team_service.get_optional(scope_id)`
- **被调用者**（2 个）：`self._validate_fields`, `get`

### `OpTypeService.get_by_name_optional()` [公开]
- 位置：第 79-83 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（3 处）：
  - `web/routes/equipment_excel_machines.py:80` [Route] `ot = op_type_svc.get_by_name_optional(v)`
  - `web/routes/process_excel_suppliers.py:75` [Route] `ot = op_type_svc.get_by_name_optional(v)`
  - `core/services/personnel/resource_team_service.py:100` [Service] `team = self.get_by_name_optional(v)`
- **被调用者**（2 个）：`self._normalize_text`, `get_by_name`

### `OpTypeService.resolve_op_type_id_optional()` [公开]
- 位置：第 85-95 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `core/services/equipment/machine_excel_import_service.py:44` [Service] `op_type_id = self.op_type_svc.resolve_op_type_id_optional(raw)`
  - `core/services/process/supplier_excel_import_service.py:42` [Service] `op_type_id = self.op_type_svc.resolve_op_type_id_optional(raw)`
- **被调用者**（3 个）：`self._normalize_text`, `self.get_optional`, `self.get_by_name_optional`

### `OpTypeService.create()` [公开]
- 位置：第 97-112 行
- 参数：op_type_id, name, category, remark
- 返回类型：Name(id='OpType', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`self._validate_fields`, `self._normalize_text`, `get`, `get_by_name`, `self._get_or_raise`, `ValidationError`, `BusinessError`, `transaction`

### `OpTypeService.update()` [公开]
- 位置：第 114-136 行
- 参数：op_type_id, name, category, remark
- 返回类型：Name(id='OpType', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`self._validate_fields`, `self._get_or_raise`, `ValidationError`, `get_by_name`, `self._normalize_text`, `transaction`, `BusinessError`

### `OpTypeService.delete()` [公开]
- 位置：第 138-155 行
- 参数：op_type_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`self._validate_fields`, `self._get_or_raise`, `has_machine_reference`, `has_supplier_reference`, `has_part_operation_reference`, `has_batch_operation_reference`, `ValidationError`, `BusinessError`, `transaction`

### `OpTypeService.build_existing_for_excel()` [公开]
- 位置：第 160-164 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（14 处）：
  - `web/routes/equipment_excel_machines.py:135` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/equipment_excel_machines.py:179` [Route] `existing = m_svc.build_existing_for_excel()`
  - `web/routes/equipment_excel_machines.py:250` [Route] `existing = m_svc.build_existing_for_excel()`
  - `web/routes/excel_demo.py:40` [Route] `return OperatorService(conn, op_logger=None).build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:96` [Route] `existing = op_svc.build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:122` [Route] `existing = op_svc.build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:197` [Route] `existing = op_svc.build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:328` [Route] `existing = OperatorService(g.db, op_logger=getattr(g, "op_logger", None)).build_`
  - `web/routes/process_excel_op_types.py:123` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_op_types.py:146` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_op_types.py:192` [Route] `existing = op_type_svc.build_existing_for_excel()`
  - `web/routes/process_excel_suppliers.py:110` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_suppliers.py:133` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_suppliers.py:209` [Route] `existing = supplier_svc.build_existing_for_excel()`
- **被调用者**（1 个）：`list`

### `OpTypeService.ensure_replace_allowed()` [公开]
- 位置：第 166-178 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `core/services/equipment/machine_excel_import_service.py:60` [Service] `self.machine_svc.ensure_replace_allowed()`
  - `core/services/personnel/operator_excel_import_service.py:44` [Service] `self.svc.ensure_replace_allowed()`
  - `core/services/process/op_type_excel_import_service.py:42` [Service] `self.svc.ensure_replace_allowed()`
  - `core/services/process/supplier_excel_import_service.py:58` [Service] `self.svc.ensure_replace_allowed()`
- **被调用者**（5 个）：`has_any_machine_reference`, `has_any_supplier_reference`, `has_any_part_operation_reference`, `has_any_batch_operation_reference`, `BusinessError`

## core/services/scheduler/calendar_admin.py（Service 层）

### `CalendarAdmin.__init__()` [私有]
- 位置：第 31-37 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `CalendarAdmin._get_holiday_default_efficiency()` [私有]
- 位置：第 39-46 行
- 参数：无
- 返回类型：Name(id='float', ctx=Load())

### `CalendarAdmin._normalize_text()` [私有]
- 位置：第 53-54 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `CalendarAdmin._normalize_float()` [私有]
- 位置：第 57-58 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `CalendarAdmin._normalize_hhmm()` [私有]
- 位置：第 61-62 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `CalendarAdmin._normalize_date()` [私有]
- 位置：第 65-66 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `CalendarAdmin._validate_day_type()` [私有]
- 位置：第 69-80 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `CalendarAdmin._normalize_yesno()` [私有]
- 位置：第 83-90 行
- 参数：value, field
- 返回类型：Name(id='str', ctx=Load())

### `CalendarAdmin._normalize_shift_window()` [私有]
- 位置：第 92-116 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `CalendarAdmin._build_work_calendar()` [私有]
- 位置：第 118-163 行
- 参数：无
- 返回类型：Name(id='WorkCalendar', ctx=Load())

### `CalendarAdmin._build_work_calendar_from_payload()` [私有]
- 位置：第 165-189 行
- 参数：calendar_payload
- 返回类型：Name(id='WorkCalendar', ctx=Load())

### `CalendarAdmin._build_operator_calendar()` [私有]
- 位置：第 191-241 行
- 参数：无
- 返回类型：Name(id='OperatorCalendar', ctx=Load())

### `CalendarAdmin._build_operator_calendar_from_payload()` [私有]
- 位置：第 243-269 行
- 参数：calendar_payload
- 返回类型：Name(id='OperatorCalendar', ctx=Load())

### `CalendarAdmin.list_all()` [公开]
- 位置：第 274-275 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（8 处）：
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:21` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:58` [Route] `for c in cal_svc.list_all():`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:484` [Route] `rows = cal_svc.list_all()`
  - `core/services/scheduler/calendar_service.py:60` [Service] `return self._admin.list_all()`
  - `core/services/scheduler/config/config_presets.py:166` [Service] `keys = existing_keys if existing_keys is not None else {c.config_key for c in sv`
  - `core/services/scheduler/config/config_service.py:232` [Service] `existing = set(existing_keys) if existing_keys is not None else {c.config_key fo`
  - `core/services/scheduler/config/config_service.py:323` [Service] `return list(self.repo.list_all())`
  - `core/services/system/system_config_service.py:150` [Service] `existing = {c.config_key for c in self.repo.list_all()}`

### `CalendarAdmin.list_range()` [公开]
- 位置：第 277-280 行
- 参数：start_date, end_date
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/calendar_service.py:63` [Service] `return self._admin.list_range(start_date, end_date)`
- **被调用者**（1 个）：`self._normalize_date`

### `CalendarAdmin.upsert()` [公开]
- 位置：第 282-307 行
- 参数：date_value, day_type, shift_hours, shift_start, shift_end, efficiency, allow_normal, allow_urgent, remark
- 返回类型：Name(id='WorkCalendar', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:56` [Route] `cal_svc.upsert(`
  - `core/services/scheduler/calendar_service.py:77` [Service] `row = self._admin.upsert(`
- **被调用者**（3 个）：`self._build_work_calendar`, `transaction`, `cal.to_dict`

### `CalendarAdmin.upsert_no_tx()` [公开]
- 位置：第 309-318 行
- 参数：calendar_payload
- 返回类型：Name(id='WorkCalendar', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:386` [Route] `cal_svc.upsert_no_tx(`
  - `core/services/scheduler/calendar_service.py:92` [Service] `row = self._admin.upsert_no_tx(calendar_payload)`
- **被调用者**（3 个）：`self._build_work_calendar_from_payload`, `upsert`, `c.to_dict`

### `CalendarAdmin.delete()` [公开]
- 位置：第 320-323 行
- 参数：date_value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._normalize_date`, `transaction`

### `CalendarAdmin.delete_all_no_tx()` [公开]
- 位置：第 325-326 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `web/routes/process_excel_routes.py:261` [Route] `part_svc.delete_all_no_tx()`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:379` [Route] `cal_svc.delete_all_no_tx()`
  - `core/services/scheduler/batch_excel_import.py:33` [Service] `svc.delete_all_no_tx()`
  - `core/services/scheduler/calendar_service.py:101` [Service] `self._admin.delete_all_no_tx()`
- **被调用者**（1 个）：`delete_all`

### `CalendarAdmin.get_operator_calendar()` [公开]
- 位置：第 331-336 行
- 参数：operator_id, date_value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/calendar_service.py:108` [Service] `return self._admin.get_operator_calendar(operator_id, date_value)`
- **被调用者**（4 个）：`self._normalize_text`, `self._normalize_date`, `get`, `ValidationError`

### `CalendarAdmin.list_operator_calendar()` [公开]
- 位置：第 338-342 行
- 参数：operator_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/personnel_calendar_pages.py:24` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `core/services/scheduler/calendar_service.py:111` [Service] `return self._admin.list_operator_calendar(operator_id)`
- **被调用者**（3 个）：`self._normalize_text`, `list_by_operator`, `ValidationError`

### `CalendarAdmin.list_operator_calendar_all()` [公开]
- 位置：第 344-345 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/personnel_excel_operator_calendar.py:78` [Route] `for c in cal_svc.list_operator_calendar_all():`
  - `web/routes/personnel_excel_operator_calendar.py:400` [Route] `rows = cal_svc.list_operator_calendar_all()`
  - `core/services/scheduler/calendar_service.py:114` [Service] `return self._admin.list_operator_calendar_all()`
  - `core/services/scheduler/calendar_service.py:169` [Service] `set(existing_ids or set()) if existing_ids is not None else {f"{c.operator_id}|{`
- **被调用者**（1 个）：`list_all`

### `CalendarAdmin.upsert_operator_calendar()` [公开]
- 位置：第 347-374 行
- 参数：operator_id, date_value, day_type, shift_hours, shift_start, shift_end, efficiency, allow_normal, allow_urgent, remark
- 返回类型：Name(id='OperatorCalendar', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/personnel_calendar_pages.py:71` [Route] `cal_svc.upsert_operator_calendar(`
  - `core/services/scheduler/calendar_service.py:129` [Service] `row = self._admin.upsert_operator_calendar(`
- **被调用者**（4 个）：`self._build_operator_calendar`, `transaction`, `upsert`, `cal.to_dict`

### `CalendarAdmin.upsert_operator_calendar_no_tx()` [公开]
- 位置：第 376-379 行
- 参数：calendar_payload
- 返回类型：Name(id='OperatorCalendar', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/calendar_service.py:145` [Service] `row = self._admin.upsert_operator_calendar_no_tx(calendar_payload)`
  - `core/services/scheduler/calendar_service.py:184` [Service] `self.upsert_operator_calendar_no_tx(`
- **被调用者**（3 个）：`self._build_operator_calendar_from_payload`, `upsert`, `c.to_dict`

### `CalendarAdmin.delete_operator_calendar()` [公开]
- 位置：第 381-387 行
- 参数：operator_id, date_value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/calendar_service.py:150` [Service] `self._admin.delete_operator_calendar(operator_id, date_value)`
- **被调用者**（5 个）：`self._normalize_text`, `self._normalize_date`, `ValidationError`, `transaction`, `delete`

### `CalendarAdmin.delete_operator_calendar_all_no_tx()` [公开]
- 位置：第 389-390 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `core/services/scheduler/calendar_service.py:154` [Service] `self._admin.delete_operator_calendar_all_no_tx()`
  - `core/services/scheduler/calendar_service.py:173` [Service] `self.delete_operator_calendar_all_no_tx()`
- **被调用者**（1 个）：`delete_all`

## core/services/scheduler/config/config_field_spec.py（Service 层）

### `_choice_pairs()` [私有]
- 位置：第 57-58 行
- 参数：choice_labels
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `list_config_fields()` [公开]
- 位置：第 282-283 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（6 处）：
  - `core/services/scheduler/config/config_presets.py:112` [Service] `return tuple(spec.key for spec in list_config_fields())`
  - `core/services/scheduler/config/config_service.py:234` [Service] `for spec in list_config_fields():`
  - `core/services/scheduler/config/config_snapshot.py:188` [Service] `for spec in list_config_fields():`
  - `core/services/scheduler/config/config_snapshot.py:225` [Service] `for spec in list_config_fields():`
  - `core/services/scheduler/config/config_snapshot.py:341` [Service] `for spec in list_config_fields():`
  - `core/services/scheduler/config/config_snapshot.py:357` [Service] `for spec in list_config_fields():`
- **被调用者**（1 个）：`tuple`

### `has_config_field()` [公开]
- 位置：第 286-287 行
- 参数：key
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`strip`, `str`

### `get_field_spec()` [公开]
- 位置：第 290-294 行
- 参数：key
- 返回类型：Name(id='ConfigFieldSpec', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_presets.py:121` [Service] `spec = get_field_spec(key)`
  - `core/services/scheduler/config/config_service.py:220` [Service] `return get_field_spec(key).description`
- **被调用者**（3 个）：`strip`, `KeyError`, `str`

### `default_for()` [公开]
- 位置：第 297-298 行
- 参数：key
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（18 处）：
  - `core/services/scheduler/config/config_service.py:83` [Service] `DEFAULT_SORT_STRATEGY = str(default_for("sort_strategy"))`
  - `core/services/scheduler/config/config_service.py:84` [Service] `DEFAULT_PRIORITY_WEIGHT = float(default_for("priority_weight"))`
  - `core/services/scheduler/config/config_service.py:85` [Service] `DEFAULT_DUE_WEIGHT = float(default_for("due_weight"))`
  - `core/services/scheduler/config/config_service.py:86` [Service] `DEFAULT_READY_WEIGHT = float(default_for("ready_weight"))`
  - `core/services/scheduler/config/config_service.py:87` [Service] `DEFAULT_ENFORCE_READY_DEFAULT = str(default_for("enforce_ready_default"))`
  - `core/services/scheduler/config/config_service.py:88` [Service] `DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY = float(default_for("holiday_default_efficien`
  - `core/services/scheduler/config/config_service.py:89` [Service] `DEFAULT_DISPATCH_MODE = str(default_for("dispatch_mode"))`
  - `core/services/scheduler/config/config_service.py:90` [Service] `DEFAULT_DISPATCH_RULE = str(default_for("dispatch_rule"))`
  - `core/services/scheduler/config/config_service.py:91` [Service] `DEFAULT_AUTO_ASSIGN_ENABLED = str(default_for("auto_assign_enabled"))`
  - `core/services/scheduler/config/config_service.py:92` [Service] `DEFAULT_AUTO_ASSIGN_PERSIST = str(default_for("auto_assign_persist"))`
  - `core/services/scheduler/config/config_service.py:93` [Service] `DEFAULT_ORTOOLS_ENABLED = str(default_for("ortools_enabled"))`
  - `core/services/scheduler/config/config_service.py:94` [Service] `DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS = int(default_for("ortools_time_limit_seconds`
  - `core/services/scheduler/config/config_service.py:95` [Service] `DEFAULT_ALGO_MODE = str(default_for("algo_mode"))`
  - `core/services/scheduler/config/config_service.py:96` [Service] `DEFAULT_TIME_BUDGET_SECONDS = int(default_for("time_budget_seconds"))`
  - `core/services/scheduler/config/config_service.py:97` [Service] `DEFAULT_OBJECTIVE = str(default_for("objective"))`
  - `core/services/scheduler/config/config_service.py:98` [Service] `DEFAULT_FREEZE_WINDOW_ENABLED = str(default_for("freeze_window_enabled"))`
  - `core/services/scheduler/config/config_service.py:99` [Service] `DEFAULT_FREEZE_WINDOW_DAYS = int(default_for("freeze_window_days"))`
  - `core/algorithms/greedy/schedule_params.py:82` [Algorithm] `return default_for(key)`
- **被调用者**（1 个）：`get_field_spec`

### `choices_for()` [公开]
- 位置：第 301-303 行
- 参数：key
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（7 处）：
  - `core/services/scheduler/config/config_service.py:105` [Service] `VALID_STRATEGIES = choices_for("sort_strategy")`
  - `core/services/scheduler/config/config_service.py:106` [Service] `VALID_ALGO_MODES = choices_for("algo_mode")`
  - `core/services/scheduler/config/config_service.py:107` [Service] `VALID_OBJECTIVES = choices_for("objective")`
  - `core/services/scheduler/config/config_service.py:108` [Service] `VALID_DISPATCH_MODES = choices_for("dispatch_mode")`
  - `core/services/scheduler/config/config_service.py:109` [Service] `VALID_DISPATCH_RULES = choices_for("dispatch_rule")`
  - `core/services/scheduler/config/config_service.py:865` [Service] `return [{"key": key, "name": labels.get(key, key)} for key in choices_for("sort_`
  - `core/services/scheduler/run/schedule_optimizer.py:148` [Service] `registry_values = tuple(str(item).strip().lower() for item in choices_for(field)`
- **被调用者**（2 个）：`get_field_spec`, `tuple`

### `field_label_for()` [公开]
- 位置：第 306-310 行
- 参数：key
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（3 处）：
  - `web/routes/domains/scheduler/scheduler_config_feedback.py:19` [Route] `label = field_label_for(field_key)`
  - `web/routes/domains/scheduler/scheduler_config_feedback.py:40` [Route] `label_text = "、".join(dict.fromkeys(field_label_for(key) for key in normalized_f`
  - `core/services/scheduler/config/config_service.py:878` [Service] `return field_label_for(key)`
- **被调用者**（3 个）：`strip`, `_FIELD_LABEL_ALIASES.get`, `str`

### `choice_label_map_for()` [公开]
- 位置：第 313-317 行
- 参数：key
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `core/services/scheduler/config/config_service.py:111` [Service] `STRATEGY_NAME_ZH = choice_label_map_for("sort_strategy")`
  - `core/services/scheduler/config/config_service.py:864` [Service] `labels = choice_label_map_for("sort_strategy")`
  - `core/services/scheduler/config/config_service.py:882` [Service] `return choice_label_map_for(key)`
- **被调用者**（3 个）：`get_field_spec`, `dict`, `choices_for`

### `page_metadata_for()` [公开]
- 位置：第 320-332 行
- 参数：keys
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config_display_state.py:28` [Route] `return page_metadata_for(list(SCHEDULER_VISIBLE_CONFIG_FIELDS))`
  - `core/services/scheduler/config/config_service.py:874` [Service] `return page_metadata_for(keys)`
- **被调用者**（5 个）：`list`, `get_field_spec`, `ConfigFieldPageMetadata`, `_choice_pairs`, `choice_label_map_for`

### `normalize_text_field()` [公开]
- 位置：第 335-340 行
- 参数：key, value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`get_field_spec`, `lower`, `to_yes_no`, `strip`, `str`

### `_normalize_valid_texts()` [私有]
- 位置：第 343-352 行
- 参数：values
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_format_choice_allow_text()` [私有]
- 位置：第 355-356 行
- 参数：valid_values
- 返回类型：Name(id='str', ctx=Load())

### `_record_blank_choice_degradation()` [私有]
- 位置：第 359-373 行
- 参数：collector
- 返回类型：Constant(value=None, kind=None)

### `_record_invalid_choice_degradation()` [私有]
- 位置：第 376-394 行
- 参数：collector
- 返回类型：Constant(value=None, kind=None)

### `_handle_missing_value()` [私有]
- 位置：第 397-417 行
- 参数：collector
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_choice_with_degradation()` [私有]
- 位置：第 420-467 行
- 参数：raw_value
- 返回类型：Name(id='str', ctx=Load())

### `_yes_no_with_degradation()` [私有]
- 位置：第 470-518 行
- 参数：raw_value
- 返回类型：Name(id='str', ctx=Load())

### `coerce_config_field()` [公开]
- 位置：第 521-597 行
- 参数：key, value
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（25 处）：
  - `core/services/scheduler/config/config_service.py:825` [Service] `return coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1387` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1424` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1432` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1449` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1464` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1472` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1488` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1503` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1520` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1539` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1556` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1571` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1586` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_service.py:1594` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_snapshot.py:192` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_snapshot.py:227` [Service] `values[spec.key] = coerce_config_field(`
  - `core/services/scheduler/config/config_snapshot.py:277` [Service] `return coerce_config_field(`
  - `core/services/scheduler/config/config_snapshot.py:345` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_snapshot.py:359` [Service] `values[spec.key] = coerce_config_field(`
  - `core/services/scheduler/config/config_validator.py:38` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_validator.py:61` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_validator.py:87` [Service] `st = coerce_config_field(`
  - `core/services/scheduler/config/config_validator.py:146` [Service] `coerce_config_field(`
  - `core/services/scheduler/config/config_validator.py:168` [Service] `coerce_config_field(`
- **被调用者**（15 个）：`get_field_spec`, `TypeError`, `DegradationCollector`, `_choice_with_degradation`, `_yes_no_with_degradation`, `_handle_missing_value`, `float`, `int`, `parse_field_float`, `parse_field_int`, `lower`, `choices_for`, `bool`, `strip`, `str`

### `default_snapshot_values()` [公开]
- 位置：第 600-601 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `core/services/scheduler/config/config_service.py:285` [Service] `defaults = default_snapshot_values()`
  - `core/services/scheduler/config/config_service.py:1417` [Service] `updates = self._registered_updates(default_snapshot_values())`
  - `core/services/scheduler/config/config_snapshot.py:187` [Service] `default_map = default_snapshot_values()`
  - `core/services/scheduler/config/config_snapshot.py:222` [Service] `default_map = default_snapshot_values()`
  - `core/services/scheduler/config/config_snapshot.py:274` [Service] `default_map = default_snapshot_values()`
  - `core/services/scheduler/config/config_snapshot.py:310` [Service] `default_map = default_snapshot_values()`
- **被调用者**（1 个）：`list_config_fields`

## core/services/scheduler/config/config_presets.py（Service 层）

### `_preset_result()` [私有]
- 位置：第 16-36 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `builtin_presets()` [公开]
- 位置：第 39-75 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:308` [Service] `return preset_ops.builtin_presets(self)`
- **被调用者**（3 个）：`svc._default_snapshot`, `ScheduleConfigSnapshot`, `base.to_dict`

### `snapshot_close()` [公开]
- 位置：第 78-79 行
- 参数：a, b
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:312` [Service] `return preset_ops.snapshot_close(a, b)`
- **被调用者**（1 个）：`snapshot_diff_fields`

### `_values_close()` [私有]
- 位置：第 82-85 行
- 参数：left, right
- 返回类型：Name(id='bool', ctx=Load())

### `snapshot_diff_fields()` [公开]
- 位置：第 88-98 行
- 参数：a, b
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
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
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:318` [Service] `return preset_ops.get_snapshot_from_repo(self, strict_mode=bool(strict_mode))`
- **被调用者**（2 个）：`build_schedule_config_snapshot`, `bool`

### `ensure_builtin_presets()` [公开]
- 位置：第 162-185 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:315` [Service] `preset_ops.ensure_builtin_presets(self, existing_keys=existing_keys)`
- **被调用者**（8 个）：`builtin_presets`, `svc._preset_key`, `presets_to_create.append`, `transaction`, `set`, `list_all`, `json.dumps`, `snap.to_dict`

### `bootstrap_active_provenance_if_pristine()` [公开]
- 位置：第 188-212 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:254` [Service] `preset_ops.bootstrap_active_provenance_if_pristine(self)`
- **被调用者**（12 个）：`bool`, `get`, `get_snapshot_from_repo`, `svc._default_snapshot`, `getattr`, `transaction`, `set_batch`, `snapshot_close`, `safe_warning`, `svc._active_preset_updates`, `svc.get_preset_display_state`, `type`

### `list_presets()` [公开]
- 位置：第 215-217 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:802` [Service] `return preset_ops.list_presets(self)`
- **被调用者**（3 个）：`svc.get_preset_display_state`, `list`, `state.get`

### `_readonly_active_preset_state()` [私有]
- 位置：第 220-227 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_builtin_preset_payload()` [私有]
- 位置：第 230-235 行
- 参数：svc, name
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_load_preset_payload()` [私有]
- 位置：第 238-253 行
- 参数：svc, name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `save_preset()` [公开]
- 位置：第 256-289 行
- 参数：svc, name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:380` [Route] `saved = cfg_svc.save_preset(name)`
  - `core/services/scheduler/config/config_service.py:805` [Service] `return preset_ops.save_preset(self, name)`
- **被调用者**（17 个）：`svc._normalize_text`, `svc._is_builtin_preset`, `json.dumps`, `_preset_result`, `ValidationError`, `len`, `svc.get_snapshot`, `snap.to_dict`, `transaction`, `set`, `set_batch`, `_readonly_active_preset_state`, `svc._preset_key`, `svc._active_preset_updates`, `str`

### `delete_preset()` [公开]
- 位置：第 292-303 行
- 参数：svc, name
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:407` [Route] `cfg_svc.delete_preset(name)`
  - `core/services/scheduler/config/config_service.py:808` [Service] `preset_ops.delete_preset(self, name)`
- **被调用者**（9 个）：`svc._normalize_text`, `svc._is_builtin_preset`, `svc.get_active_preset`, `ValidationError`, `transaction`, `delete`, `svc._preset_key`, `set_batch`, `svc._active_preset_updates`

### `normalize_preset_snapshot()` [公开]
- 位置：第 306-316 行
- 参数：svc, data
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:811` [Service] `return preset_ops.normalize_preset_snapshot(self, data)`
- **被调用者**（2 个）：`svc._default_snapshot`, `normalize_preset_snapshot_dict`

### `apply_preset()` [公开]
- 位置：第 319-385 行
- 参数：svc, name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:362` [Route] `applied = cfg_svc.apply_preset(name)`
  - `core/services/scheduler/config/config_service.py:814` [Service] `return preset_ops.apply_preset(self, name)`
- **被调用者**（21 个）：`svc._normalize_text`, `_load_preset_payload`, `_missing_required_preset_fields`, `normalize_preset_snapshot`, `snapshot_payload_projection_diff_fields`, `_preset_result`, `ValidationError`, `_readonly_active_preset_state`, `join`, `transaction`, `set_batch`, `get_snapshot_from_repo`, `snapshot_diff_fields`, `str`, `items`

## core/services/scheduler/config/config_service.py（Service 层）

### `ConfigPageSaveOutcome.__getattr__()` [私有]
- 位置：第 41-42 行
- 参数：item
- 返回类型：Name(id='Any', ctx=Load())

### `ConfigPageSaveOutcome.to_dict()` [公开]
- 位置：第 44-45 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（74 处）：
  - `web/routes/equipment_pages.py:221` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:234` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:26` [Route] `items = [m.to_dict() for m in material_svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:24` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:45` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:165` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:116` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:117` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:118` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:147` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/system_backup.py:51` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:34` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:48` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:57` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:172` [Route] `d = it.to_dict()`
  - `web/routes/domains/scheduler/scheduler_analysis.py:17` [Route] `return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})`
  - `web/routes/domains/scheduler/scheduler_batches.py:58` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batches.py:96` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/domains/scheduler/scheduler_batches.py:189` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:196` [Route] `d = op.to_dict()`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:247` [Route] `batch=b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:21` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:410` [Route] `result = stats.to_dict()`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:139` [Route] `payload = exc.to_dict()`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:50` [Route] `selected_history = selected_history_item.to_dict() if hasattr(selected_history_i`
  - `web/viewmodels/scheduler_analysis_trends.py:107` [ViewModel] `d = h.to_dict() if hasattr(h, "to_dict") else (h if isinstance(h, dict) else {})`
  - `web/viewmodels/scheduler_analysis_trends.py:153` [ViewModel] `return selected_item.to_dict() if hasattr(selected_item, "to_dict") else (select`
  - `web/viewmodels/system_logs_vm.py:29` [ViewModel] `d = it.to_dict() if hasattr(it, "to_dict") else (it if isinstance(it, dict) else`
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
  - `core/services/scheduler/calendar_admin.py:306` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:373` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:378` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/gantt_contract.py:98` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:212` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:281` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_service.py:301` [Service] `"summary": orchestration.summary_contract.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:47` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:56` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:64` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:89` [Service] `left = a.to_dict()`
  - `core/services/scheduler/config/config_presets.py:90` [Service] `right = b.to_dict()`
  - `core/services/scheduler/config/config_presets.py:138` [Service] `canonical = snapshot.to_dict()`
  - `core/services/scheduler/config/config_presets.py:175` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config/config_presets.py:234` [Service] `return dict(snapshot.to_dict())`
  - `core/services/scheduler/config/config_presets.py:279` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/config/config_presets.py:343` [Service] `config_updates = [(key, str(value), None) for key, value in snap.to_dict().items`
  - `core/services/scheduler/run/schedule_optimizer.py:320` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer.py:334` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:183` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:210` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:399` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:414` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/summary/schedule_summary.py:82` [Service] `return snapshot.to_dict().get(str(key or "").strip())`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:30` [Service] `).to_dict()`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:220` [Service] `"metrics": ctx.best_metrics.to_dict() if ctx.best_metrics is not None else None,`

### `ConfigService.__init__()` [私有]
- 位置：第 139-144 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ConfigService._normalize_text()` [私有]
- 位置：第 150-151 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ConfigService._normalize_weight()` [私有]
- 位置：第 154-169 行
- 参数：value, field
- 返回类型：Name(id='float', ctx=Load())

### `ConfigService.normalize_weight()` [公开]
- 位置：第 172-173 行
- 参数：value, field
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`ConfigService._normalize_weight`

### `ConfigService._normalize_weights_triplet()` [私有]
- 位置：第 176-217 行
- 参数：priority_weight, due_weight, ready_weight
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._field_description()` [私有]
- 位置：第 219-220 行
- 参数：key
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._registered_updates()` [私有]
- 位置：第 222-226 行
- 参数：values
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._get_raw_value()` [私有]
- 位置：第 228-229 行
- 参数：config_key, default
- 返回类型：Name(id='Any', ctx=Load())

### `ConfigService._bootstrap_registered_defaults()` [私有]
- 位置：第 231-245 行
- 参数：无
- 返回类型：Name(id='set', ctx=Load())

### `ConfigService.ensure_defaults()` [公开]
- 位置：第 247-257 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/system/system_config_service.py:172` [Service] `self.ensure_defaults(backup_keep_days_default=backup_keep_days_default)`
- **被调用者**（5 个）：`self._is_pristine_store`, `self._bootstrap_registered_defaults`, `self._ensure_builtin_presets`, `preset_ops.bootstrap_active_provenance_if_pristine`, `set`

### `ConfigService._is_pristine_store()` [私有]
- 位置：第 259-260 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._ensure_defaults_if_pristine()` [私有]
- 位置：第 262-266 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._preset_key()` [私有]
- 位置：第 272-273 行
- 参数：name
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._is_builtin_preset()` [私有]
- 位置：第 276-282 行
- 参数：name
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._default_snapshot()` [私有]
- 位置：第 284-305 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService._builtin_presets()` [私有]
- 位置：第 307-308 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._snapshot_close()` [私有]
- 位置：第 311-312 行
- 参数：a, b
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._ensure_builtin_presets()` [私有]
- 位置：第 314-315 行
- 参数：existing_keys
- 返回类型：Constant(value=None, kind=None)

### `ConfigService._get_snapshot_from_repo()` [私有]
- 位置：第 317-318 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService._list_config_rows()` [私有]
- 位置：第 320-323 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._extract_repair_fields()` [私有]
- 位置：第 326-331 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._repair_notice_from_reason()` [私有]
- 位置：第 334-347 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._normalize_repair_notice()` [私有]
- 位置：第 350-368 行
- 参数：notice
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ConfigService._active_preset_meta_payload()` [私有]
- 位置：第 371-392 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._legacy_active_preset_meta_from_reason()` [私有]
- 位置：第 395-414 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._active_preset_meta_from_value()` [私有]
- 位置：第 417-443 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._serialize_active_preset_meta()` [私有]
- 位置：第 446-453 行
- 参数：meta
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._compat_repair_notice()` [私有]
- 位置：第 456-471 行
- 参数：repair_notices
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._reason_in()` [私有]
- 位置：第 474-475 行
- 参数：reason
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._builtin_preset_names()` [私有]
- 位置：第 477-482 行
- 参数：无
- 返回类型：Subscript(value=Name(id='set', ctx=Load()), slice=Index(valu

### `ConfigService._row_config_text()` [私有]
- 位置：第 485-487 行
- 参数：row
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ConfigService._config_page_values_equal()` [私有]
- 位置：第 490-493 行
- 参数：left, right
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._resolve_current_config_baseline()` [私有]
- 位置：第 495-523 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._resolve_current_config_descriptor()` [私有]
- 位置：第 525-582 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._collect_preset_rows()` [私有]
- 位置：第 584-594 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._build_preset_entries()` [私有]
- 位置：第 596-619 行
- 参数：preset_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._active_preset_display_state_from_rows()` [私有]
- 位置：第 621-637 行
- 参数：by_key
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._active_preset_provenance_state()` [私有]
- 位置：第 640-661 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._build_current_config_state()` [私有]
- 位置：第 663-711 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService.get_active_preset()` [公开]
- 位置：第 713-716 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_presets.py:299` [Service] `active = svc.get_active_preset()`
- **被调用者**（3 个）：`get_value`, `strip`, `str`

### `ConfigService.get_active_preset_reason()` [公开]
- 位置：第 718-721 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`get_value`, `strip`, `str`

### `ConfigService.get_active_preset_meta()` [公开]
- 位置：第 723-725 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`get_value`, `self._active_preset_meta_from_value`, `self.get_active_preset_reason`

### `ConfigService.get_preset_display_state()` [公开]
- 位置：第 727-750 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（5 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:77` [Route] `preset_display_state = cfg_svc.get_preset_display_state(readonly=True, current_s`
  - `web/routes/domains/scheduler/scheduler_config.py:313` [Route] `preset_display_state = cfg_svc.get_preset_display_state(readonly=True, current_s`
  - `core/services/scheduler/config/config_presets.py:189` [Service] `if bool((svc.get_preset_display_state(readonly=True) or {}).get("can_preserve_ba`
  - `core/services/scheduler/config/config_presets.py:216` [Service] `state = svc.get_preset_display_state(readonly=True)`
  - `core/services/scheduler/config/config_presets.py:221` [Service] `state = svc.get_preset_display_state(readonly=True)`
- **被调用者**（8 个）：`self._list_config_rows`, `self._collect_preset_rows`, `self._active_preset_display_state_from_rows`, `self._get_snapshot_from_repo`, `self._build_preset_entries`, `self._build_current_config_state`, `bool`, `preset_state.get`

### `ConfigService._active_preset_update()` [私有]
- 位置：第 752-758 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._active_preset_reason_update()` [私有]
- 位置：第 760-766 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._active_preset_meta_update()` [私有]
- 位置：第 768-773 行
- 参数：meta
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._active_preset_updates()` [私有]
- 位置：第 775-789 行
- 参数：name, reason
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._set_active_preset()` [私有]
- 位置：第 791-793 行
- 参数：name
- 返回类型：Constant(value=None, kind=None)

### `ConfigService.mark_active_preset_custom()` [公开]
- 位置：第 795-799 行
- 参数：reason
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:359` [Route] `cfg_svc.mark_active_preset_custom()`
- **被调用者**（1 个）：`self._set_active_preset`

### `ConfigService.list_presets()` [公开]
- 位置：第 801-802 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`preset_ops.list_presets`

### `ConfigService.save_preset()` [公开]
- 位置：第 804-805 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:380` [Route] `saved = cfg_svc.save_preset(name)`
- **被调用者**（1 个）：`preset_ops.save_preset`

### `ConfigService.delete_preset()` [公开]
- 位置：第 807-808 行
- 参数：name
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:407` [Route] `cfg_svc.delete_preset(name)`
- **被调用者**（1 个）：`preset_ops.delete_preset`

### `ConfigService._normalize_preset_snapshot()` [私有]
- 位置：第 810-811 行
- 参数：data
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService.apply_preset()` [公开]
- 位置：第 813-814 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:362` [Route] `applied = cfg_svc.apply_preset(name)`
- **被调用者**（1 个）：`preset_ops.apply_preset`

### `ConfigService.get()` [公开]
- 位置：第 816-817 行
- 参数：config_key
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`get_value`, `str`

### `ConfigService._get_registered_field_value()` [私有]
- 位置：第 819-832 行
- 参数：key
- 返回类型：Name(id='Any', ctx=Load())

### `ConfigService.get_holiday_default_efficiency()` [公开]
- 位置：第 834-841 行
- 参数：无
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（3 处）：
  - `web/routes/personnel_excel_operator_calendar.py:130` [Route] `return float(cfg_svc.get_holiday_default_efficiency()), None`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:116` [Route] `return float(cfg_svc.get_holiday_default_efficiency()), None`
  - `core/services/scheduler/calendar_admin.py:46` [Service] `return float(cfg_svc.get_holiday_default_efficiency(strict_mode=True))`
- **被调用者**（3 个）：`float`, `self._get_registered_field_value`, `bool`

### `ConfigService.get_holiday_default_efficiency_display_state()` [公开]
- 位置：第 843-858 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（2 处）：
  - `web/routes/personnel_calendar_pages.py:37` [Route] `hde, hde_degraded, hde_warning = cfg_svc.get_holiday_default_efficiency_display_`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:17` [Route] `hde, hde_degraded, hde_warning = cfg_svc.get_holiday_default_efficiency_display_`
- **被调用者**（9 个）：`self.get_snapshot`, `float`, `any`, `safe_warning`, `format`, `isinstance`, `strip`, `str`, `get`

### `ConfigService.get_available_strategies()` [公开]
- 位置：第 863-865 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:67` [Route] `strategies = cfg_svc.get_available_strategies()`
  - `web/routes/domains/scheduler/scheduler_config.py:302` [Route] `strategies = cfg_svc.get_available_strategies()`
- **被调用者**（3 个）：`choice_label_map_for`, `labels.get`, `choices_for`

### `ConfigService.get_snapshot()` [公开]
- 位置：第 867-870 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（7 处）：
  - `web/routes/system_utils.py:162` [Route] `return svc.get_snapshot(backup_keep_days_default=int(current_app.config.get("BAC`
  - `web/routes/domains/scheduler/scheduler_batches.py:66` [Route] `cfg = cfg_svc.get_snapshot()`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:231` [Route] `prefer_primary_skill = services.config_service.get_snapshot().prefer_primary_ski`
  - `web/routes/domains/scheduler/scheduler_config.py:301` [Route] `cfg = cfg_svc.get_snapshot(strict_mode=False)`
  - `core/services/scheduler/schedule_service.py:38` [Service] `return cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`
  - `core/services/scheduler/config/config_presets.py:266` [Service] `snap = svc.get_snapshot(strict_mode=True)`
  - `core/services/system/system_maintenance_service.py:92` [Service] `cfg = cfg_svc.get_snapshot(backup_keep_days_default=int(backup_keep_days_default`
- **被调用者**（3 个）：`self._get_snapshot_from_repo`, `bool`, `self._ensure_defaults_if_pristine`

### `ConfigService.get_page_metadata()` [公开]
- 位置：第 873-874 行
- 参数：keys
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`page_metadata_for`

### `ConfigService.get_field_label()` [公开]
- 位置：第 877-878 行
- 参数：key
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`field_label_for`

### `ConfigService.get_choice_labels()` [公开]
- 位置：第 881-882 行
- 参数：key
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`choice_label_map_for`

### `ConfigService._config_page_value()` [私有]
- 位置：第 888-894 行
- 参数：form_values, key
- 返回类型：Name(id='Any', ctx=Load())

### `ConfigService._config_page_submitted_fields()` [私有]
- 位置：第 897-915 行
- 参数：form_values
- 返回类型：Subscript(value=Name(id='set', ctx=Load()), slice=Index(valu

### `ConfigService._normalize_config_page_weights()` [私有]
- 位置：第 917-959 行
- 参数：priority_raw, due_raw, current_snapshot
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._normalize_config_page_payload()` [私有]
- 位置：第 961-990 行
- 参数：form_values
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService._config_page_write_values()` [私有]
- 位置：第 992-1002 行
- 参数：snapshot
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_materialized_write_values()` [私有]
- 位置：第 1005-1017 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_visible_changed_fields()` [私有]
- 位置：第 1019-1030 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._snapshot_degraded_fields()` [私有]
- 位置：第 1033-1044 行
- 参数：snapshot
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._config_page_visible_repair_fields()` [私有]
- 位置：第 1047-1074 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._config_page_hidden_repair_values()` [私有]
- 位置：第 1077-1089 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_hidden_repair_reason()` [私有]
- 位置：第 1092-1096 行
- 参数：hidden_repaired_fields
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._config_page_visible_repair_notice()` [私有]
- 位置：第 1099-1104 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_hidden_repair_notice()` [私有]
- 位置：第 1107-1112 行
- 参数：hidden_repaired_fields
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_blocked_hidden_repair_notice()` [私有]
- 位置：第 1115-1126 行
- 参数：blocked_hidden_fields
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_current_provenance_state()` [私有]
- 位置：第 1128-1139 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_notices()` [私有]
- 位置：第 1142-1147 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._config_page_initial_write_plan()` [私有]
- 位置：第 1149-1168 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._config_page_apply_visible_change_plan()` [私有]
- 位置：第 1170-1188 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ConfigService._config_page_apply_visible_repair_plan()` [私有]
- 位置：第 1190-1210 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ConfigService._config_page_apply_hidden_repair_plan()` [私有]
- 位置：第 1212-1254 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ConfigService._config_page_blocked_hidden_write_plan()` [私有]
- 位置：第 1256-1276 行
- 参数：无
- 返回类型：Name(id='_ConfigPageWritePlan', ctx=Load())

### `ConfigService._config_page_build_write_plan()` [私有]
- 位置：第 1278-1325 行
- 参数：无
- 返回类型：Name(id='_ConfigPageWritePlan', ctx=Load())

### `ConfigService.save_page_config()` [公开]
- 位置：第 1327-1383 行
- 参数：form_values
- 返回类型：Name(id='ConfigPageSaveOutcome', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:456` [Route] `outcome = cfg_svc.save_page_config(payload)`
- **被调用者**（21 个）：`self._ensure_defaults_if_pristine`, `self.get_snapshot`, `self._config_page_current_provenance_state`, `provenance_state.get`, `self._config_page_submitted_fields`, `self._normalize_config_page_payload`, `self._config_page_write_values`, `self._config_page_visible_changed_fields`, `self._config_page_visible_repair_fields`, `self._config_page_hidden_repair_values`, `list`, `write_values.update`, `self._config_page_materialized_write_values`, `self._config_page_build_write_plan`, `ConfigPageSaveOutcome`

### `ConfigService.set_strategy()` [公开]
- 位置：第 1385-1398 行
- 参数：sort_strategy
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_weights()` [公开]
- 位置：第 1400-1414 行
- 参数：priority_weight, due_weight, ready_weight, require_sum_1
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`self._normalize_weights_triplet`, `transaction`, `set`, `set_batch`, `str`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.restore_default()` [公开]
- 位置：第 1416-1420 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:467` [Route] `cfg_svc.restore_default()`
- **被调用者**（6 个）：`self._registered_updates`, `updates.extend`, `default_snapshot_values`, `self._active_preset_updates`, `transaction`, `set_batch`

### `ConfigService.set_dispatch()` [公开]
- 位置：第 1422-1445 行
- 参数：dispatch_mode, dispatch_rule
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_auto_assign_enabled()` [公开]
- 位置：第 1447-1460 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_ortools()` [公开]
- 位置：第 1462-1484 行
- 参数：enabled, time_limit_seconds
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`str`, `int`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_prefer_primary_skill()` [公开]
- 位置：第 1486-1499 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_enforce_ready_default()` [公开]
- 位置：第 1501-1514 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_holiday_default_efficiency()` [公开]
- 位置：第 1516-1535 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`float`, `ValidationError`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `strip`, `str`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_algo_mode()` [公开]
- 位置：第 1537-1550 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_time_budget_seconds()` [公开]
- 位置：第 1552-1567 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`int`, `ValidationError`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `strip`, `str`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_objective()` [公开]
- 位置：第 1569-1582 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_freeze_window()` [公开]
- 位置：第 1584-1606 行
- 参数：enabled, days
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`str`, `int`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

## core/services/scheduler/config/config_snapshot.py（Service 层）

### `ScheduleConfigSnapshot.to_dict()` [公开]
- 位置：第 45-65 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（81 处）：
  - `web/routes/equipment_pages.py:221` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:234` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:26` [Route] `items = [m.to_dict() for m in material_svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:24` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:45` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:165` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:116` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:117` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:118` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:147` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/system_backup.py:51` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:34` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:48` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:57` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:172` [Route] `d = it.to_dict()`
  - `web/routes/domains/scheduler/scheduler_analysis.py:17` [Route] `return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})`
  - `web/routes/domains/scheduler/scheduler_batches.py:58` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batches.py:96` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/domains/scheduler/scheduler_batches.py:189` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:196` [Route] `d = op.to_dict()`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:247` [Route] `batch=b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:21` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:410` [Route] `result = stats.to_dict()`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:139` [Route] `payload = exc.to_dict()`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:50` [Route] `selected_history = selected_history_item.to_dict() if hasattr(selected_history_i`
  - `web/viewmodels/scheduler_analysis_trends.py:107` [ViewModel] `d = h.to_dict() if hasattr(h, "to_dict") else (h if isinstance(h, dict) else {})`
  - `web/viewmodels/scheduler_analysis_trends.py:153` [ViewModel] `return selected_item.to_dict() if hasattr(selected_item, "to_dict") else (select`
  - `web/viewmodels/system_logs_vm.py:29` [ViewModel] `d = it.to_dict() if hasattr(it, "to_dict") else (it if isinstance(it, dict) else`
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
  - `core/services/scheduler/calendar_admin.py:306` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:373` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:378` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/gantt_contract.py:98` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:212` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:281` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_service.py:301` [Service] `"summary": orchestration.summary_contract.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:47` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:56` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:64` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:89` [Service] `left = a.to_dict()`
  - `core/services/scheduler/config/config_presets.py:90` [Service] `right = b.to_dict()`
  - `core/services/scheduler/config/config_presets.py:138` [Service] `canonical = snapshot.to_dict()`
  - `core/services/scheduler/config/config_presets.py:175` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config/config_presets.py:234` [Service] `return dict(snapshot.to_dict())`
  - `core/services/scheduler/config/config_presets.py:279` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/config/config_presets.py:343` [Service] `config_updates = [(key, str(value), None) for key, value in snap.to_dict().items`
  - `core/services/scheduler/config/config_service.py:45` [Service] `return self.snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:968` [Service] `payload = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:998` [Service] `values = snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1011` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1025` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1053` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1084` [Service] `values = normalized_snapshot.to_dict()`
  - `core/services/scheduler/run/schedule_optimizer.py:320` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer.py:334` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:183` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:210` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:399` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:414` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/summary/schedule_summary.py:82` [Service] `return snapshot.to_dict().get(str(key or "").strip())`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:30` [Service] `).to_dict()`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:220` [Service] `"metrics": ctx.best_metrics.to_dict() if ctx.best_metrics is not None else None,`
- **被调用者**（2 个）：`float`, `int`

### `_read_runtime_cfg_raw_value()` [私有]
- 位置：第 68-88 行
- 参数：cfg, key
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_runtime_cfg_read_error()` [私有]
- 位置：第 91-92 行
- 参数：key, exc
- 返回类型：Name(id='ValidationError', ctx=Load())

### `_read_runtime_cfg_mapping_like_value()` [私有]
- 位置：第 95-111 行
- 参数：cfg, key, raw_missing
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_read_runtime_cfg_mapping_like_value_without_default()` [私有]
- 位置：第 114-122 行
- 参数：getter, key, raw_missing
- 返回类型：Name(id='Any', ctx=Load())

### `_coerce_degradation_event()` [私有]
- 位置：第 125-151 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_seed_snapshot_degradation_collector()` [私有]
- 位置：第 154-160 行
- 参数：snapshot
- 返回类型：Name(id='DegradationCollector', ctx=Load())

### `_merge_degradation_counters()` [私有]
- 位置：第 163-179 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_validate_present_runtime_cfg_fields()` [私有]
- 位置：第 182-201 行
- 参数：cfg
- 返回类型：Constant(value=None, kind=None)

### `_build_schedule_config_snapshot_from_runtime_cfg()` [私有]
- 位置：第 204-262 行
- 参数：cfg
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `coerce_runtime_config_field()` [公开]
- 位置：第 265-286 行
- 参数：cfg, key
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（1 处）：
  - `core/algorithms/greedy/schedule_params.py:99` [Algorithm] `coerce_runtime_config_field(`
- **被调用者**（5 个）：`default_snapshot_values`, `_read_runtime_cfg_raw_value`, `coerce_config_field`, `DegradationCollector`, `bool`

### `ensure_schedule_config_snapshot()` [公开]
- 位置：第 289-299 行
- 参数：cfg
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（14 处）：
  - `core/services/scheduler/config/config_service.py:986` [Service] `return ensure_schedule_config_snapshot(`
  - `core/services/scheduler/run/schedule_optimizer.py:380` [Service] `cfg = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:36` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:52` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:121` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:338` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/summary/schedule_summary.py:77` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/summary/schedule_summary.py:455` [Service] `cfg=ensure_schedule_config_snapshot(`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:26` [Service] `return ensure_schedule_config_snapshot(`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:397` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:439` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/services/scheduler/summary/schedule_summary_freeze.py:10` [Service] `snapshot = ensure_schedule_config_snapshot(`
  - `core/algorithms/greedy/config_adapter.py:17` [Algorithm] `snapshot = ensure_schedule_config_snapshot(config)`
  - `core/algorithms/greedy/schedule_params.py:88` [Algorithm] `return ensure_schedule_config_snapshot(`
- **被调用者**（2 个）：`_build_schedule_config_snapshot_from_runtime_cfg`, `bool`

### `build_schedule_config_snapshot()` [公开]
- 位置：第 302-391 行
- 参数：repo
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_presets.py:156` [Service] `return build_schedule_config_snapshot(`
- **被调用者**（25 个）：`DegradationCollector`, `object`, `default_snapshot_values`, `isinstance`, `bool`, `list_config_fields`, `ScheduleConfigSnapshot`, `default_map.update`, `TypeError`, `getattr`, `callable`, `repo.get_value`, `_read_repo_raw_value`, `coerce_config_field`, `repo_get`

## core/services/scheduler/config/config_validator.py（Service 层）

### `_emit_number_below_minimum()` [私有]
- 位置：第 12-25 行
- 参数：collector
- 返回类型：Constant(value=None, kind=None)

### `_preset_float()` [私有]
- 位置：第 28-48 行
- 参数：key, raw_value
- 返回类型：Name(id='float', ctx=Load())

### `_preset_int()` [私有]
- 位置：第 51-71 行
- 参数：key, raw_value
- 返回类型：Name(id='int', ctx=Load())

### `normalize_preset_snapshot()` [公开]
- 位置：第 74-234 行
- 参数：data
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/config/config_presets.py:341` [Service] `snap = normalize_preset_snapshot(svc, data)`
  - `core/services/scheduler/config/config_service.py:811` [Service] `return preset_ops.normalize_preset_snapshot(self, data)`
- **被调用者**（20 个）：`dict`, `DegradationCollector`, `_read`, `coerce_config_field`, `_preset_float`, `max`, `_yes_no`, `_choice`, `_preset_int`, `ScheduleConfigSnapshot`, `ValidationError`, `float`, `str`, `payload.get`, `bool`

## core/services/scheduler/gantt_critical_chain.py（Service 层）

### `_parse_dt()` [私有]
- 位置：第 9-23 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_fmt_dt()` [私有]
- 位置：第 26-27 行
- 参数：dt
- 返回类型：Name(id='str', ctx=Load())

### `_node_dt()` [私有]
- 位置：第 30-32 行
- 参数：node, key
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_minutes_between()` [私有]
- 位置：第 35-41 行
- 参数：a, b
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_empty_result()` [私有]
- 位置：第 44-53 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_load_rows()` [私有]
- 位置：第 56-57 行
- 参数：schedule_repo, version
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_unavailable_result()` [私有]
- 位置：第 60-64 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_nodes()` [私有]
- 位置：第 67-87 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_process_prev()` [私有]
- 位置：第 90-108 行
- 参数：nodes
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_prev_by_resource()` [私有]
- 位置：第 111-128 行
- 参数：nodes
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_eligible_process_edge()` [私有]
- 位置：第 131-142 行
- 参数：pn, n
- 返回类型：Name(id='bool', ctx=Load())

### `_eligible_resource_edge()` [私有]
- 位置：第 145-154 行
- 参数：pn, n
- 返回类型：Name(id='bool', ctx=Load())

### `_process_prev_candidate()` [私有]
- 位置：第 157-172 行
- 参数：nodes, tid, n
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_resource_prev_candidate()` [私有]
- 位置：第 175-195 行
- 参数：nodes, tid, n
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_pick_latest_candidate()` [私有]
- 位置：第 198-206 行
- 参数：cands
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_choose_control_prev()` [私有]
- 位置：第 209-245 行
- 参数：nodes
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_sink_id()` [私有]
- 位置：第 248-250 行
- 参数：nodes
- 返回类型：Name(id='str', ctx=Load())

### `_backtrace_chain()` [私有]
- 位置：第 253-284 行
- 参数：sink_id
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_edge_type_stats()` [私有]
- 位置：第 287-294 行
- 参数：edges
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `compute_critical_chain()` [公开]
- 位置：第 297-330 行
- 参数：schedule_repo, version
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/gantt_service.py:157` [Service] `computed = self._normalize_critical_chain_result(compute_critical_chain(self.sch`
- **被调用者**（14 个）：`_build_nodes`, `_build_process_prev`, `_build_prev_by_resource`, `_choose_control_prev`, `_sink_id`, `_backtrace_chain`, `_load_rows`, `_empty_result`, `_node_dt`, `_fmt_dt`, `_edge_type_stats`, `len`, `_unavailable_result`, `int`

## core/services/scheduler/gantt_service.py（Service 层）

### `GanttService.__init__()` [私有]
- 位置：第 33-38 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `GanttService.get_latest_version_or_1()` [公开]
- 位置：第 40-42 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（4 处）：
  - `web/routes/domains/scheduler/scheduler_gantt.py:48` [Route] `latest_version = svc.get_latest_version_or_1()`
  - `web/routes/domains/scheduler/scheduler_gantt.py:84` [Route] `version = normalize_version_or_latest(request.args.get("version"), latest_versio`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:127` [Route] `latest_version = svc.get_latest_version_or_1()`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:176` [Route] `version = normalize_version_or_latest(request.args.get("version"), latest_versio`
- **被调用者**（2 个）：`int`, `get_latest_version`

### `GanttService.resolve_week_range()` [公开]
- 位置：第 44-51 行
- 参数：week_start, offset_weeks, start_date, end_date
- 返回类型：Name(id='WeekRange', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_gantt.py:49` [Route] `wr = svc.resolve_week_range(week_start=week_start, offset_weeks=offset, start_da`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:128` [Route] `wr = svc.resolve_week_range(week_start=week_start, offset_weeks=offset, start_da`

### `GanttService._log_overdue_marker_degraded()` [私有]
- 位置：第 53-61 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `GanttService._log_overdue_marker_partial()` [私有]
- 位置：第 63-71 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `GanttService._overdue_batch_ids_from_history()` [私有]
- 位置：第 73-95 行
- 参数：version
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `GanttService._critical_chain_cache_key()` [私有]
- 位置：第 97-114 行
- 参数：version
- 返回类型：Name(id='tuple', ctx=Load())

### `GanttService._normalize_critical_chain_result()` [私有]
- 位置：第 117-138 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `GanttService._critical_chain_cacheable()` [私有]
- 位置：第 141-142 行
- 参数：result
- 返回类型：Name(id='bool', ctx=Load())

### `GanttService._get_critical_chain()` [私有]
- 位置：第 144-180 行
- 参数：version
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `GanttService.get_gantt_tasks()` [公开]
- 位置：第 182-250 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_gantt.py:86` [Route] `data: Dict[str, Any] = svc.get_gantt_tasks(`
- **被调用者**（26 个）：`self.resolve_week_range`, `build_calendar_days`, `list_overlapping_with_details`, `self._overdue_batch_ids_from_history`, `set`, `build_tasks`, `DegradationCollector`, `degradation_collector.extend`, `self._get_critical_chain`, `build_gantt_contract`, `strip`, `ValidationError`, `int`, `self.get_latest_version_or_1`, `get_by_version`

### `GanttService.get_week_plan_rows()` [公开]
- 位置：第 252-282 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_week_plan.py:132` [Route] `data = svc.get_week_plan_rows(start_date=wr.week_start_date.isoformat(), end_dat`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:178` [Route] `data = svc.get_week_plan_rows(`
- **被调用者**（11 个）：`self.resolve_week_range`, `list_overlapping_with_details`, `build_week_plan_rows`, `get_by_version`, `int`, `self.get_latest_version_or_1`, `isoformat`, `degradation_events_to_dicts`, `hist.to_dict`, `strip`, `str`

## core/services/scheduler/resource_dispatch_excel.py（Service 层）

### `_auto_width()` [私有]
- 位置：第 15-30 行
- 参数：ws
- 返回类型：Constant(value=None, kind=None)

### `_append_row()` [私有]
- 位置：第 33-34 行
- 参数：ws, values
- 返回类型：Constant(value=None, kind=None)

### `_write_table()` [私有]
- 位置：第 37-50 行
- 参数：ws, headers, rows
- 返回类型：Constant(value=None, kind=None)

### `_detail_headers()` [私有]
- 位置：第 53-74 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_first_present()` [私有]
- 位置：第 77-82 行
- 参数：row
- 返回类型：Name(id='Any', ctx=Load())

### `_yes_no_label()` [私有]
- 位置：第 85-86 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_build_detail_row()` [私有]
- 位置：第 89-111 行
- 参数：row
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_detail_table_rows()` [私有]
- 位置：第 114-115 行
- 参数：detail_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_calendar_table_rows()` [私有]
- 位置：第 118-126 行
- 参数：calendar_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_empty_reason_text()` [私有]
- 位置：第 129-135 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_degradation_message_text()` [私有]
- 位置：第 138-154 行
- 参数：summary
- 返回类型：Name(id='str', ctx=Load())

### `_summary_pairs()` [私有]
- 位置：第 157-182 行
- 参数：payload
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_write_summary_sheet()` [私有]
- 位置：第 185-194 行
- 参数：wb, payload
- 返回类型：Constant(value=None, kind=None)

### `_write_calendar_sheet()` [私有]
- 位置：第 197-199 行
- 参数：wb, title, headers, rows
- 返回类型：Constant(value=None, kind=None)

### `_write_detail_sheet()` [私有]
- 位置：第 202-204 行
- 参数：wb, title, rows
- 返回类型：Constant(value=None, kind=None)

### `_write_team_scope_sheets()` [私有]
- 位置：第 207-224 行
- 参数：wb, payload
- 返回类型：Constant(value=None, kind=None)

### `_write_resource_scope_sheets()` [私有]
- 位置：第 227-234 行
- 参数：wb, payload
- 返回类型：Constant(value=None, kind=None)

### `build_resource_dispatch_workbook()` [公开]
- 位置：第 237-256 行
- 参数：payload
- 返回类型：Name(id='BytesIO', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/resource_dispatch_service.py:347` [Service] `buf = build_resource_dispatch_workbook(payload)`
- **被调用者**（12 个）：`Workbook`, `wb.remove`, `_write_summary_sheet`, `BytesIO`, `wb.save`, `buf.seek`, `ValueError`, `payload.get`, `str`, `_write_team_scope_sheets`, `_write_resource_scope_sheets`, `filters.get`

## core/services/scheduler/resource_dispatch_range.py（Service 层）

### `DispatchRange.start_time()` [公开]
- 位置：第 22-23 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`strftime`

### `DispatchRange.end_time()` [公开]
- 位置：第 26-27 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`strftime`

### `_parse_date()` [私有]
- 位置：第 30-43 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `resolve_dispatch_range()` [公开]
- 位置：第 46-93 行
- 参数：无
- 返回类型：Name(id='DispatchRange', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/resource_dispatch_service.py:206` [Service] `dr = resolve_dispatch_range(`
  - `core/services/scheduler/resource_dispatch_service.py:287` [Service] `dr = resolve_dispatch_range(`
- **被调用者**（14 个）：`_parse_date`, `datetime`, `DispatchRange`, `lower`, `ValidationError`, `date`, `int`, `timedelta`, `anchor.replace`, `strip`, `datetime.now`, `anchor.weekday`, `str`, `calendar.monthrange`

## core/services/scheduler/resource_dispatch_service.py（Service 层）

### `ResourceDispatchService.__init__()` [私有]
- 位置：第 25-33 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ResourceDispatchService._text()` [私有]
- 位置：第 36-40 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ResourceDispatchService._normalize_scope_type()` [私有]
- 位置：第 42-46 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `ResourceDispatchService._normalize_team_axis()` [私有]
- 位置：第 48-52 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `ResourceDispatchService._resolve_scope_id()` [私有]
- 位置：第 54-70 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ResourceDispatchService._period_preset_label()` [私有]
- 位置：第 72-73 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `ResourceDispatchService._scope_type_label()` [私有]
- 位置：第 75-76 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `ResourceDispatchService._team_axis_label()` [私有]
- 位置：第 78-79 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `ResourceDispatchService._latest_version()` [私有]
- 位置：第 81-82 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())

### `ResourceDispatchService._list_versions()` [私有]
- 位置：第 84-85 行
- 参数：limit
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ResourceDispatchService._normalize_version()` [私有]
- 位置：第 87-96 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `ResourceDispatchService._scope_record()` [私有]
- 位置：第 98-103 行
- 参数：scope_type, scope_id
- 返回类型：无注解

### `ResourceDispatchService._scope_name()` [私有]
- 位置：第 105-110 行
- 参数：scope_type, scope_id
- 返回类型：Name(id='str', ctx=Load())

### `ResourceDispatchService._build_scope_options()` [私有]
- 位置：第 112-142 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ResourceDispatchService._log_overdue_marker_degraded()` [私有]
- 位置：第 144-152 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ResourceDispatchService._log_overdue_marker_partial()` [私有]
- 位置：第 154-162 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ResourceDispatchService._load_overdue_meta()` [私有]
- 位置：第 164-185 行
- 参数：version
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ResourceDispatchService.build_page_context()` [公开]
- 位置：第 187-247 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:156` [Route] `context = svc.build_page_context(**_request_kwargs())`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:165` [Route] `context = svc.build_page_context()`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:172` [Route] `context = svc.build_page_context()`
- **被调用者**（18 个）：`self._normalize_scope_type`, `self._normalize_team_axis`, `self._list_versions`, `resolve_dispatch_range`, `self._resolve_scope_id`, `self._build_scope_options`, `self._normalize_version`, `int`, `self._latest_version`, `self._scope_name`, `bool`, `self._scope_type_label`, `strip`, `self._team_axis_label`, `self._period_preset_label`

### `ResourceDispatchService.get_dispatch_payload()` [公开]
- 位置：第 249-343 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:191` [Route] `payload = _svc().get_dispatch_payload(**_request_kwargs())`
- **被调用者**（21 个）：`self._normalize_scope_type`, `self._normalize_team_axis`, `self._latest_version`, `self._normalize_version`, `self._resolve_scope_id`, `self._scope_name`, `resolve_dispatch_range`, `self._load_overdue_meta`, `set`, `list_dispatch_rows_with_resource_context`, `build_dispatch_filters`, `bool`, `str`, `build_empty_dispatch_message`, `empty_dispatch_payload`

### `ResourceDispatchService.build_export()` [公开]
- 位置：第 345-360 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:207` [Route] `buf, filename, payload = svc.build_export(**_request_kwargs())`
- **被调用者**（4 个）：`self.get_dispatch_payload`, `build_resource_dispatch_workbook`, `filters.get`, `payload.get`

## core/services/scheduler/resource_pool_builder.py（Service 层）

### `_skill_rank()` [私有]
- 位置：第 14-23 行
- 参数：v
- 返回类型：Name(id='int', ctx=Load())

### `_active_machine_ids()` [私有]
- 位置：第 26-27 行
- 参数：machines
- 返回类型：Name(id='set', ctx=Load())

### `_op_type_ids_for_ops()` [私有]
- 位置：第 30-36 行
- 参数：algo_ops
- 返回类型：Name(id='set', ctx=Load())

### `_machines_by_op_type()` [私有]
- 位置：第 39-54 行
- 参数：machines
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_active_operator_ids()` [私有]
- 位置：第 57-62 行
- 参数：svc
- 返回类型：Name(id='set', ctx=Load())

### `_build_operator_machine_maps()` [私有]
- 位置：第 65-91 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_sort_operators_by_machine()` [私有]
- 位置：第 94-100 行
- 参数：operators_by_machine
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_append_warning()` [私有]
- 位置：第 103-105 行
- 参数：warnings, message
- 返回类型：Constant(value=None, kind=None)

### `_warn_service_logger()` [私有]
- 位置：第 108-109 行
- 参数：svc, message
- 返回类型：Constant(value=None, kind=None)

### `load_machine_downtimes()` [公开]
- 位置：第 113-186 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（17 个）：`MachineDowntimeRepository`, `svc._format_dt`, `sorted`, `join`, `_append_warning`, `_warn_service_logger`, `dt_repo.list_active_after`, `int`, `list`, `strip`, `str`, `svc._normalize_datetime`, `intervals.sort`, `partial_fail_mids.append`, `len`

### `build_resource_pool()` [公开]
- 位置：第 189-253 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`to_yes_no`, `list`, `_active_machine_ids`, `_op_type_ids_for_ops`, `_machines_by_op_type`, `_active_operator_ids`, `list_simple_rows`, `_build_operator_machine_maps`, `_sort_operators_by_machine`, `warnings.append`, `_warn_service_logger`, `str`

### `extend_downtime_map_for_resource_pool()` [公开]
- 位置：第 256-329 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`to_yes_no`, `MachineDowntimeRepository`, `svc._format_dt`, `sorted`, `join`, `_append_warning`, `isinstance`, `_warn_service_logger`, `dt_repo.list_active_after`, `int`, `list`, `resource_pool.get`, `strip`, `str`, `svc._normalize_datetime`

## core/services/scheduler/run/freeze_window.py（Service 层）

### `_init_freeze_meta()` [私有]
- 位置：第 23-31 行
- 参数：meta
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_freeze_window_days()` [私有]
- 位置：第 34-65 行
- 参数：cfg, prev_version
- 返回类型：Name(id='int', ctx=Load())

### `_record_freeze_degradation()` [私有]
- 位置：第 68-83 行
- 参数：meta, warnings, message
- 返回类型：Constant(value=None, kind=None)

### `_invalid_schedule_row_sample()` [私有]
- 位置：第 86-97 行
- 参数：row
- 返回类型：Name(id='str', ctx=Load())

### `_load_schedule_map()` [私有]
- 位置：第 100-132 行
- 参数：svc
- 返回类型：Name(id='_LoadedScheduleMapOutcome', ctx=Load())

### `_max_seq_by_batch()` [私有]
- 位置：第 135-146 行
- 参数：schedule_map, op_by_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_prefix_op_ids_for_batch()` [私有]
- 位置：第 149-150 行
- 参数：operations, bid, max_seq
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_cache_seed_for_prefix()` [私有]
- 位置：第 153-167 行
- 参数：svc
- 返回类型：Name(id='int', ctx=Load())

### `_discard_seed_cache()` [私有]
- 位置：第 170-172 行
- 参数：prefix, seed_tmp
- 返回类型：Constant(value=None, kind=None)

### `_build_seed_results()` [私有]
- 位置：第 175-206 行
- 参数：frozen_op_ids
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `build_freeze_window_seed()` [公开]
- 位置：第 209-321 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（26 个）：`set`, `_init_freeze_meta`, `_freeze_window_days`, `svc._format_dt`, `sorted`, `_max_seq_by_batch`, `max_seq_by_batch.items`, `_build_seed_results`, `seed_results.sort`, `bool`, `timedelta`, `int`, `list`, `_load_schedule_map`, `join`

## core/services/scheduler/run/schedule_input_builder.py（Service 层）

### `_build_scope()` [私有]
- 位置：第 46-52 行
- 参数：op
- 返回类型：Name(id='str', ctx=Load())

### `_merged_total_days()` [私有]
- 位置：第 55-82 行
- 参数：raw_value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_lookup_template_group_context()` [私有]
- 位置：第 85-86 行
- 参数：svc, op
- 返回类型：Name(id='TemplateGroupLookupOutcome', ctx=Load())

### `_build_algo_operations_outcome()` [私有]
- 位置：第 89-199 行
- 参数：svc, reschedulable_operations
- 返回类型：Subscript(value=Name(id='BuildOutcome', ctx=Load()), slice=I

### `build_algo_operations()` [公开]
- 位置：第 203-210 行
- 参数：svc, reschedulable_operations
- 返回类型：Subscript(value=Name(id='BuildOutcome', ctx=Load()), slice=I
- **调用者**（0 处）：
  - （无外部调用者）

### `build_algo_operations()` [公开]
- 位置：第 214-221 行
- 参数：svc, reschedulable_operations
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）

### `build_algo_operations()` [公开]
- 位置：第 224-234 行
- 参数：svc, reschedulable_operations
- 返回类型：BinOp(left=Subscript(value=Name(id='BuildOutcome', ctx=Load(
- **调用者**（0 处）：
  - （无外部调用者）

## core/services/scheduler/run/schedule_input_collector.py（Service 层）

### `_normalized_status_text()` [私有]
- 位置：第 51-52 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_raise_schedule_empty_result()` [私有]
- 位置：第 55-59 行
- 参数：message
- 返回类型：Constant(value=None, kind=None)

### `_normalize_batch_ids_or_raise()` [私有]
- 位置：第 62-77 行
- 参数：svc, batch_ids
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_normalize_schedule_window()` [私有]
- 位置：第 80-101 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_resolve_enforce_ready_effective()` [私有]
- 位置：第 104-109 行
- 参数：cfg, enforce_ready
- 返回类型：Name(id='bool', ctx=Load())

### `_load_batches_and_operations()` [私有]
- 位置：第 112-129 行
- 参数：svc, normalized_batch_ids
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_build_reschedulable_state()` [私有]
- 位置：第 132-155 行
- 参数：svc, operations
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_is_missing_internal_resource()` [私有]
- 位置：第 158-165 行
- 参数：op
- 返回类型：Name(id='bool', ctx=Load())

### `_ensure_ready_batches()` [私有]
- 位置：第 168-176 行
- 参数：svc, batches
- 返回类型：Constant(value=None, kind=None)

### `collect_schedule_run_input()` [公开]
- 位置：第 179-290 行
- 参数：svc
- 返回类型：Name(id='ScheduleRunInput', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:245` [Service] `schedule_input = collect_schedule_run_input(`
- **被调用者**（23 个）：`_normalize_batch_ids_or_raise`, `time.time`, `_normalize_schedule_window`, `calendar_service_cls`, `config_service_cls`, `get_snapshot_with_strict_mode`, `_resolve_enforce_ready_effective`, `_load_batches_and_operations`, `_build_reschedulable_state`, `_build_algo_operations_outcome`, `list`, `int`, `_build_runtime_support_inputs`, `ScheduleRunInput`, `svc._normalize_text`

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

### `_run_local_search()` [私有]
- 位置：第 195-356 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `optimize_schedule()` [公开]
- 位置：第 359-645 行
- 参数：无
- 返回类型：Name(id='OptimizationOutcome', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（44 个）：`ensure_schedule_config_snapshot`, `GreedyScheduler`, `_effective_choice_values`, `SortStrategy`, `_require_choice`, `_require_int`, `build_normalized_batches_map`, `str`, `time.time`, `_run_ortools_warmstart`, `_run_multi_start`, `_run_local_search`, `OptimizationOutcome`, `_record_optimizer_cfg_degradations`, `build_batch_sort_inputs`

## core/services/scheduler/run/schedule_optimizer_steps.py（Service 层）

### `SchedulerLike.schedule()` [公开]
- 位置：第 20-21 行
- 参数：无
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）

### `_is_yes()` [私有]
- 位置：第 24-25 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())

### `_snapshot_float()` [私有]
- 位置：第 28-48 行
- 参数：cfg, key
- 返回类型：Name(id='float', ctx=Load())

### `_snapshot_int()` [私有]
- 位置：第 51-57 行
- 参数：cfg, key
- 返回类型：Name(id='int', ctx=Load())

### `_schedule_supports_strict_mode()` [私有]
- 位置：第 60-72 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_is_unexpected_strict_mode_type_error()` [私有]
- 位置：第 75-77 行
- 参数：exc
- 返回类型：Name(id='bool', ctx=Load())

### `_schedule_with_optional_strict_mode()` [私有]
- 位置：第 80-92 行
- 参数：scheduler
- 返回类型：无注解

### `_run_ortools_warmstart()` [私有]
- 位置：第 95-223 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_dispatch_rules_for_mode()` [私有]
- 位置：第 226-229 行
- 参数：dispatch_mode, dispatch_rule_cfg, valid_dispatch_rules
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_resolve_multi_start_strategy_params()` [私有]
- 位置：第 232-244 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_get_cached_multi_start_order()` [私有]
- 位置：第 247-257 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_evaluate_multi_start_candidate()` [私有]
- 位置：第 260-309 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_run_multi_start()` [私有]
- 位置：第 312-417 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

## core/services/scheduler/run/schedule_orchestrator.py（Service 层）

### `_normalize_summary_merge_error()` [私有]
- 位置：第 19-25 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleSummaryContract.to_dict()` [公开]
- 位置：第 32-33 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（81 处）：
  - `web/routes/equipment_pages.py:221` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:234` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:26` [Route] `items = [m.to_dict() for m in material_svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:24` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:45` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:165` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:116` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:117` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:118` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:147` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/system_backup.py:51` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:34` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:48` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:57` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:172` [Route] `d = it.to_dict()`
  - `web/routes/domains/scheduler/scheduler_analysis.py:17` [Route] `return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})`
  - `web/routes/domains/scheduler/scheduler_batches.py:58` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batches.py:96` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/domains/scheduler/scheduler_batches.py:189` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:196` [Route] `d = op.to_dict()`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:247` [Route] `batch=b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:21` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:410` [Route] `result = stats.to_dict()`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:139` [Route] `payload = exc.to_dict()`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:50` [Route] `selected_history = selected_history_item.to_dict() if hasattr(selected_history_i`
  - `web/viewmodels/scheduler_analysis_trends.py:107` [ViewModel] `d = h.to_dict() if hasattr(h, "to_dict") else (h if isinstance(h, dict) else {})`
  - `web/viewmodels/scheduler_analysis_trends.py:153` [ViewModel] `return selected_item.to_dict() if hasattr(selected_item, "to_dict") else (select`
  - `web/viewmodels/system_logs_vm.py:29` [ViewModel] `d = it.to_dict() if hasattr(it, "to_dict") else (it if isinstance(it, dict) else`
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
  - `core/services/scheduler/calendar_admin.py:306` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:373` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:378` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/gantt_contract.py:98` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:212` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:281` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_service.py:301` [Service] `"summary": orchestration.summary_contract.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:47` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:56` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:64` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config/config_presets.py:89` [Service] `left = a.to_dict()`
  - `core/services/scheduler/config/config_presets.py:90` [Service] `right = b.to_dict()`
  - `core/services/scheduler/config/config_presets.py:138` [Service] `canonical = snapshot.to_dict()`
  - `core/services/scheduler/config/config_presets.py:175` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config/config_presets.py:234` [Service] `return dict(snapshot.to_dict())`
  - `core/services/scheduler/config/config_presets.py:279` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/config/config_presets.py:343` [Service] `config_updates = [(key, str(value), None) for key, value in snap.to_dict().items`
  - `core/services/scheduler/config/config_service.py:45` [Service] `return self.snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:968` [Service] `payload = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:998` [Service] `values = snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1011` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1025` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1053` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1084` [Service] `values = normalized_snapshot.to_dict()`
  - `core/services/scheduler/run/schedule_optimizer.py:320` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer.py:334` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:183` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:210` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:399` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:414` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/summary/schedule_summary.py:82` [Service] `return snapshot.to_dict().get(str(key or "").strip())`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:30` [Service] `).to_dict()`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:220` [Service] `"metrics": ctx.best_metrics.to_dict() if ctx.best_metrics is not None else None,`
- **被调用者**（1 个）：`dict`

### `_summary_field()` [私有]
- 位置：第 80-83 行
- 参数：summary, field, default
- 返回类型：Name(id='Any', ctx=Load())

### `_summary_warnings()` [私有]
- 位置：第 86-98 行
- 参数：result_summary_obj, summary
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_summary_errors()` [私有]
- 位置：第 101-114 行
- 参数：result_summary_obj, summary
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_summary_counts()` [私有]
- 位置：第 117-134 行
- 参数：result_summary_obj, summary
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_summary_contract()` [私有]
- 位置：第 137-161 行
- 参数：summary
- 返回类型：Name(id='ScheduleSummaryContract', ctx=Load())

### `_normalize_optimizer_outcome()` [私有]
- 位置：第 164-179 行
- 参数：optimizer_outcome
- 返回类型：Name(id='_NormalizedOptimizerOutcome', ctx=Load())

### `_merge_summary_warnings()` [私有]
- 位置：第 182-213 行
- 参数：summary, algo_warnings
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `orchestrate_schedule_run()` [公开]
- 位置：第 216-320 行
- 参数：svc
- 返回类型：Name(id='ScheduleOrchestrationOutcome', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:264` [Service] `orchestration = orchestrate_schedule_run(`
- **被调用者**（14 个）：`_normalize_optimizer_outcome`, `build_validated_schedule_payload`, `_merge_summary_warnings`, `SummaryBuildContext`, `build_result_summary_fn`, `ScheduleOrchestrationOutcome`, `optimize_schedule_fn`, `list`, `transaction`, `int`, `set`, `allocate_next_version`, `_build_summary_contract`, `bool`

## core/services/scheduler/run/schedule_persistence.py（Service 层）

### `ValidatedSchedulePayload.to_repo_rows()` [公开]
- 位置：第 32-46 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`rows.append`, `int`, `svc._format_dt`

### `_normalized_status_text()` [私有]
- 位置：第 49-51 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_iter_actionable_results()` [私有]
- 位置：第 54-80 行
- 参数：results
- 返回类型：Subscript(value=Name(id='Iterator', ctx=Load()), slice=Index

### `count_actionable_schedule_rows()` [公开]
- 位置：第 83-84 行
- 参数：results
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`sum`, `_iter_actionable_results`

### `has_actionable_schedule_rows()` [公开]
- 位置：第 87-88 行
- 参数：results
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`count_actionable_schedule_rows`

### `_raise_no_actionable_schedule_error()` [私有]
- 位置：第 91-97 行
- 参数：validation_errors
- 返回类型：Constant(value=None, kind=None)

### `_raise_invalid_schedule_rows_error()` [私有]
- 位置：第 100-106 行
- 参数：validation_errors
- 返回类型：Constant(value=None, kind=None)

### `_raise_out_of_scope_schedule_rows_error()` [私有]
- 位置：第 109-117 行
- 参数：out_of_scope_op_ids
- 返回类型：Constant(value=None, kind=None)

### `_result_identity()` [私有]
- 位置：第 120-132 行
- 参数：result
- 返回类型：Name(id='str', ctx=Load())

### `build_validated_schedule_payload()` [公开]
- 位置：第 135-208 行
- 参数：results
- 返回类型：Name(id='ValidatedSchedulePayload', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_orchestrator.py:243` [Service] `validated_schedule_payload = build_validated_schedule_payload(`
- **被调用者**（18 个）：`set`, `enumerate`, `ValidatedSchedulePayload`, `list`, `_result_identity`, `getattr`, `lower`, `schedule_rows.append`, `scheduled_op_ids.add`, `_raise_out_of_scope_schedule_rows_error`, `_raise_invalid_schedule_rows_error`, `_raise_no_actionable_schedule_error`, `validation_errors.append`, `int`, `out_of_scope_op_ids.append`

### `_maybe_persist_auto_assign_resources()` [私有]
- 位置：第 211-231 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)

### `_persist_operation_statuses()` [私有]
- 位置：第 234-259 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)

### `_persist_batch_statuses()` [私有]
- 位置：第 262-284 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)

### `_persist_schedule_history()` [私有]
- 位置：第 287-308 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)

### `_log_schedule_operation()` [私有]
- 位置：第 311-350 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)

### `persist_schedule()` [公开]
- 位置：第 353-433 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:273` [Service] `persist_schedule(`
- **被调用者**（14 个）：`validated_schedule_payload.to_repo_rows`, `_log_schedule_operation`, `_raise_no_actionable_schedule_error`, `transaction`, `_persist_schedule_history`, `int`, `bulk_create`, `set`, `dict`, `_persist_operation_statuses`, `_persist_batch_statuses`, `lower`, `strip`, `str`

## core/services/scheduler/schedule_service.py（Service 层）

### `_normalized_status_text()` [私有]
- 位置：第 33-34 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_get_snapshot_with_strict_mode()` [私有]
- 位置：第 37-38 行
- 参数：cfg_svc
- 返回类型：Name(id='Any', ctx=Load())

### `_raise_schedule_empty_result()` [私有]
- 位置：第 41-45 行
- 参数：message
- 返回类型：Constant(value=None, kind=None)

### `ScheduleService.__init__()` [私有]
- 位置：第 57-73 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ScheduleService._normalize_text()` [私有]
- 位置：第 79-80 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleService._is_reschedulable_operation()` [私有]
- 位置：第 83-85 行
- 参数：op
- 返回类型：Name(id='bool', ctx=Load())

### `ScheduleService._normalize_float()` [私有]
- 位置：第 88-89 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleService._get_batch_or_raise()` [私有]
- 位置：第 91-95 行
- 参数：batch_id
- 返回类型：Name(id='Batch', ctx=Load())

### `ScheduleService._get_op_or_raise()` [私有]
- 位置：第 97-101 行
- 参数：op_id
- 返回类型：Name(id='BatchOperation', ctx=Load())

### `ScheduleService._get_template_and_group_for_op()` [私有]
- 位置：第 103-104 行
- 参数：op
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ScheduleService._format_dt()` [私有]
- 位置：第 107-108 行
- 参数：dt
- 返回类型：Name(id='str', ctx=Load())

### `ScheduleService._normalize_datetime()` [私有]
- 位置：第 111-125 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleService.list_batch_operations()` [公开]
- 位置：第 130-131 行
- 参数：batch_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:216` [Route] `ops = sch_svc.list_batch_operations(batch_id=b.batch_id)`
- **被调用者**（1 个）：`op_edit.list_batch_operations`

### `ScheduleService.get_operation()` [公开]
- 位置：第 133-134 行
- 参数：op_id
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（4 处）：
  - `web/routes/domains/scheduler/scheduler_ops.py:13` [Route] `op = sch_svc.get_operation(op_id)`
  - `core/services/scheduler/operation_edit_service.py:46` [Service] `op = get_operation(svc, op_id)`
  - `core/services/scheduler/operation_edit_service.py:131` [Service] `op = get_operation(svc, op_id)`
  - `core/services/scheduler/operation_edit_service.py:182` [Service] `op = get_operation(svc, op_id)`
- **被调用者**（1 个）：`op_edit.get_operation`

### `ScheduleService.get_external_merge_hint_for_op()` [公开]
- 位置：第 136-140 行
- 参数：op
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/operation_edit_service.py:47` [Service] `return get_external_merge_hint_for_op(svc, op)`
- **被调用者**（1 个）：`op_edit.get_external_merge_hint_for_op`

### `ScheduleService.get_external_merge_hint()` [公开]
- 位置：第 142-146 行
- 参数：op_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`op_edit.get_external_merge_hint`

### `ScheduleService.update_internal_operation()` [公开]
- 位置：第 151-168 行
- 参数：op_id, machine_id, operator_id, setup_hours, unit_hours, status
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_ops.py:21` [Route] `sch_svc.update_internal_operation(`
- **被调用者**（1 个）：`op_edit.update_internal_operation`

### `ScheduleService.update_external_operation()` [公开]
- 位置：第 173-186 行
- 参数：op_id, supplier_id, ext_days, status
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_ops.py:33` [Route] `sch_svc.update_external_operation(op_id=op_id, supplier_id=supplier_id, ext_days`
- **被调用者**（1 个）：`op_edit.update_external_operation`

### `ScheduleService.run_schedule()` [公开]
- 位置：第 191-216 行
- 参数：batch_ids, start_dt, end_date, created_by, simulate, enforce_ready, strict_mode
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/domains/scheduler/scheduler_run.py:65` [Route] `result = sch_svc.run_schedule(`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:247` [Route] `result = sch_svc.run_schedule(`
  - `core/services/scheduler/run/schedule_optimizer.py:378` [Service] `说明：为保证兼容，本函数尽量保持与原 `ScheduleService.run_schedule()` 相同的口径与留痕结构。`
- **被调用者**（4 个）：`_RUN_SCHEDULE_LOCK.acquire`, `ValidationError`, `self._run_schedule_impl`, `_RUN_SCHEDULE_LOCK.release`

### `ScheduleService._run_schedule_impl()` [私有]
- 位置：第 218-304 行
- 参数：batch_ids, start_dt, end_date, created_by, simulate, enforce_ready, strict_mode
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

## core/services/scheduler/summary/schedule_summary.py（Service 层）

### `cfg_value()` [公开]
- 位置：第 71-73 行
- 参数：cfg, key, default
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`_config_snapshot_value`

### `_config_snapshot_value()` [私有]
- 位置：第 76-82 行
- 参数：cfg, key
- 返回类型：Name(id='Any', ctx=Load())

### `serialize_end_date()` [公开]
- 位置：第 86-99 行
- 参数：end_date
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`isinstance`, `strip`, `end_date.strip`, `getattr`, `callable`, `str`, `isoformat`

### `due_exclusive()` [公开]
- 位置：第 102-105 行
- 参数：due_date
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（4 处）：
  - `core/services/report/calculations.py:98` [Service] `due_excl = due_exclusive(due_d)`
  - `core/algorithms/dispatch_rules.py:67` [Algorithm] `due_dt_exclusive = due_exclusive(inp.due_date)`
  - `core/algorithms/evaluation.py:152` [Algorithm] `batch_due_exclusive = due_exclusive(due_d)`
  - `core/algorithms/ortools_bottleneck.py:96` [Algorithm] `due_dt_exclusive = due_exclusive(due_d)`
- **被调用者**（2 个）：`datetime`, `timedelta`

### `_warning_list()` [私有]
- 位置：第 108-133 行
- 参数：value
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_merge_warning_lists()` [私有]
- 位置：第 136-144 行
- 参数：primary, extra
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_dedupe_text_list()` [私有]
- 位置：第 147-156 行
- 参数：values
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_append_summary_warning()` [私有]
- 位置：第 159-177 行
- 参数：summary, message
- 返回类型：Name(id='bool', ctx=Load())

### `_counter_dict()` [私有]
- 位置：第 180-191 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_fallback_samples_dict()` [私有]
- 位置：第 194-207 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_summary_size_bytes()` [私有]
- 位置：第 210-211 行
- 参数：obj
- 返回类型：Name(id='int', ctx=Load())

### `apply_summary_size_guard()` [公开]
- 位置：第 214-268 行
- 参数：result_summary_obj
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`_summary_size_bytes`, `result_summary_obj.get`, `algo_dict.get`, `isinstance`, `overdue_batches.get`, `_trim_trace`, `_trim_warnings`, `_trim_attempts`, `int`, `_trim_best_batch_order`, `_trim_selected_batch_ids`, `_trim_overdue_items`

### `build_overdue_items()` [公开]
- 位置：第 271-285 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`_build_overdue_items_impl`

### `_build_runtime_state()` [私有]
- 位置：第 288-318 行
- 参数：无
- 返回类型：Name(id='RuntimeState', ctx=Load())

### `_build_warning_state()` [私有]
- 位置：第 321-345 行
- 参数：无
- 返回类型：Name(id='WarningState', ctx=Load())

### `_build_freeze_state()` [私有]
- 位置：第 348-373 行
- 参数：无
- 返回类型：Name(id='FreezeState', ctx=Load())

### `_build_fallback_state()` [私有]
- 位置：第 376-388 行
- 参数：algo_stats
- 返回类型：Name(id='FallbackState', ctx=Load())

### `_merge_fallback_warnings()` [私有]
- 位置：第 391-398 行
- 参数：all_warnings, fallback_state
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_degraded_cause_codes()` [私有]
- 位置：第 401-421 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_degraded_success_state()` [私有]
- 位置：第 424-432 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `build_result_summary()` [公开]
- 位置：第 435-550 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（31 个）：`dict`, `replace`, `_build_runtime_state`, `_compute_result_status`, `int`, `_frozen_batch_ids`, `_input_build_state`, `_build_warning_state`, `_build_freeze_state`, `_compute_downtime_degradation`, `_compute_resource_pool_degradation`, `_hard_constraints`, `_build_fallback_state`, `_summary_degradation_state`, `_degraded_success_state`

## core/services/scheduler/summary/schedule_summary_assembly.py（Service 层）

### `_config_snapshot_dict()` [私有]
- 位置：第 25-30 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_comparison_metric()` [私有]
- 位置：第 33-34 行
- 参数：objective_name
- 返回类型：Name(id='str', ctx=Load())

### `_best_score_schema()` [私有]
- 位置：第 37-38 行
- 参数：objective_name
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_finish_time_by_batch()` [私有]
- 位置：第 41-53 行
- 参数：results
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_record_invalid_due()` [私有]
- 位置：第 56-66 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_build_overdue_items()` [私有]
- 位置：第 69-126 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_algo_downtime_dict()` [私有]
- 位置：第 129-139 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_input_contract_dict()` [私有]
- 位置：第 142-148 行
- 参数：input_state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_freeze_window_dict()` [私有]
- 位置：第 151-171 行
- 参数：state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_resource_pool_dict()` [私有]
- 位置：第 174-186 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_warning_pipeline_dict()` [私有]
- 位置：第 189-204 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_dict()` [私有]
- 位置：第 207-249 行
- 参数：state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_result_summary_obj()` [私有]
- 位置：第 252-298 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

## core/services/scheduler/summary/schedule_summary_degradation.py（Service 层）

### `_event_identity()` [私有]
- 位置：第 13-21 行
- 参数：event
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_dedupe_event_dicts()` [私有]
- 位置：第 24-35 行
- 参数：events
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_iter_build_outcome_values()` [私有]
- 位置：第 38-48 行
- 参数：value
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_value_flag()` [私有]
- 位置：第 51-54 行
- 参数：item, key
- 返回类型：Name(id='Any', ctx=Load())

### `_builder_merge_context_state()` [私有]
- 位置：第 57-68 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_legacy_merge_context_events()` [私有]
- 位置：第 71-76 行
- 参数：event_dicts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_input_build_state()` [私有]
- 位置：第 79-114 行
- 参数：input_build_outcome
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_meta_int()` [私有]
- 位置：第 117-121 行
- 参数：meta, key
- 返回类型：Name(id='int', ctx=Load())

### `_meta_sample()` [私有]
- 位置：第 124-139 行
- 参数：meta, key
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_metric_int()` [私有]
- 位置：第 142-148 行
- 参数：metrics, key
- 返回类型：Name(id='int', ctx=Load())

### `_metric_sample()` [私有]
- 位置：第 151-168 行
- 参数：metrics, key
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_optional_text()` [私有]
- 位置：第 171-175 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_event_count()` [私有]
- 位置：第 178-182 行
- 参数：event
- 返回类型：Name(id='int', ctx=Load())

### `_add_input_events()` [私有]
- 位置：第 185-199 行
- 参数：collector, input_state
- 返回类型：Constant(value=None, kind=None)

### `_add_existing_degradation_events()` [私有]
- 位置：第 202-217 行
- 参数：collector, raw_events
- 返回类型：Constant(value=None, kind=None)

### `_add_counted_event()` [私有]
- 位置：第 220-232 行
- 参数：collector
- 返回类型：Constant(value=None, kind=None)

### `_add_state_event()` [私有]
- 位置：第 235-247 行
- 参数：collector
- 返回类型：Constant(value=None, kind=None)

### `_summary_degradation_state()` [私有]
- 位置：第 250-357 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_partial_fail_reason()` [私有]
- 位置：第 360-365 行
- 参数：prefix, count, sample, suffix
- 返回类型：Name(id='str', ctx=Load())

### `_downtime_reason()` [私有]
- 位置：第 368-393 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_compute_downtime_degradation()` [私有]
- 位置：第 396-435 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_compute_resource_pool_degradation()` [私有]
- 位置：第 438-451 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_hard_constraints()` [私有]
- 位置：第 454-460 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

## core/services/scheduler/summary/schedule_summary_freeze.py（Service 层）

### `_freeze_window_config_state()` [私有]
- 位置：第 9-16 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_freeze_degradation_codes()` [私有]
- 位置：第 19-20 行
- 参数：meta
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_freeze_applied()` [私有]
- 位置：第 23-26 行
- 参数：meta
- 返回类型：Name(id='bool', ctx=Load())

### `_freeze_state_name()` [私有]
- 位置：第 29-34 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_compute_result_status()` [私有]
- 位置：第 37-46 行
- 参数：summary
- 返回类型：Name(id='str', ctx=Load())

### `_frozen_batch_ids()` [私有]
- 位置：第 49-56 行
- 参数：operations
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_extract_freeze_warnings()` [私有]
- 位置：第 59-69 行
- 参数：all_warnings
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_freeze_meta_dict()` [私有]
- 位置：第 72-95 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

## core/services/scheduler/summary/schedule_summary_types.py（Service 层）

### `FreezeState.status()` [公开]
- 位置：第 68-69 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`str`, `get`

## data/repositories/config_repo.py（Repository 层）

### `ConfigRepository.get()` [公开]
- 位置：第 13-18 行
- 参数：config_key
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self.fetchone`, `ScheduleConfig.from_row`

### `ConfigRepository.get_value()` [公开]
- 位置：第 20-26 行
- 参数：config_key, default
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（11 处）：
  - `web/bootstrap/plugins.py:125` [Bootstrap] `value = repo.get_value(key, default=None)`
  - `core/services/scheduler/config/config_presets.py:243` [Service] `raw = svc.repo.get_value(svc._preset_key(name), default=None)`
  - `core/services/scheduler/config/config_service.py:229` [Service] `return self.repo.get_value(str(config_key), default=None if default is None else`
  - `core/services/scheduler/config/config_service.py:714` [Service] `raw = self.repo.get_value(self.ACTIVE_PRESET_KEY, default=None)`
  - `core/services/scheduler/config/config_service.py:719` [Service] `raw = self.repo.get_value(self.ACTIVE_PRESET_REASON_KEY, default=None)`
  - `core/services/scheduler/config/config_service.py:724` [Service] `raw = self.repo.get_value(self.ACTIVE_PRESET_META_KEY, default=None)`
  - `core/services/scheduler/config/config_service.py:817` [Service] `return self.repo.get_value(str(config_key), default=None)`
  - `core/services/scheduler/config/config_snapshot.py:335` [Service] `raw = repo.get_value(key, default=raw_missing)`
  - `core/services/system/system_config_service.py:97` [Service] `raw = self.repo.get_value(key, default=default)`
  - `core/services/system/system_config_service.py:107` [Service] `raw = self.repo.get_value(key, default=None)`
  - `core/services/system/system_config_service.py:179` [Service] `return self.repo.get_value(config_key, default=default)`
- **被调用者**（2 个）：`self.fetchvalue`, `str`

### `ConfigRepository.list_all()` [公开]
- 位置：第 28-32 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（10 处）：
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:21` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:58` [Route] `for c in cal_svc.list_all():`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:484` [Route] `rows = cal_svc.list_all()`
  - `core/services/scheduler/calendar_admin.py:275` [Service] `return self.repo.list_all()`
  - `core/services/scheduler/calendar_admin.py:345` [Service] `return self.operator_calendar_repo.list_all()`
  - `core/services/scheduler/calendar_service.py:60` [Service] `return self._admin.list_all()`
  - `core/services/scheduler/config/config_presets.py:166` [Service] `keys = existing_keys if existing_keys is not None else {c.config_key for c in sv`
  - `core/services/scheduler/config/config_service.py:232` [Service] `existing = set(existing_keys) if existing_keys is not None else {c.config_key fo`
  - `core/services/scheduler/config/config_service.py:323` [Service] `return list(self.repo.list_all())`
  - `core/services/system/system_config_service.py:150` [Service] `existing = {c.config_key for c in self.repo.list_all()}`
- **被调用者**（2 个）：`self.fetchall`, `ScheduleConfig.from_row`

### `ConfigRepository.count_all()` [公开]
- 位置：第 34-39 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:260` [Service] `return int(self.repo.count_all() or 0) == 0`
- **被调用者**（2 个）：`self.fetchvalue`, `int`

### `ConfigRepository.set()` [公开]
- 位置：第 41-52 行
- 参数：config_key, config_value, description
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self.execute`, `str`

### `ConfigRepository.set_batch()` [公开]
- 位置：第 54-68 行
- 参数：items
- 返回类型：Constant(value=None, kind=None)
- **调用者**（22 处）：
  - `core/services/scheduler/config/config_presets.py:212` [Service] `svc.repo.set_batch(svc._active_preset_updates(active_value, reason=active_reason`
  - `core/services/scheduler/config/config_presets.py:282` [Service] `svc.repo.set_batch(svc._active_preset_updates(n))`
  - `core/services/scheduler/config/config_presets.py:303` [Service] `svc.repo.set_batch(svc._active_preset_updates(svc.ACTIVE_PRESET_CUSTOM, reason=s`
  - `core/services/scheduler/config/config_presets.py:346` [Service] `svc.repo.set_batch(config_updates)`
  - `core/services/scheduler/config/config_presets.py:352` [Service] `svc.repo.set_batch(`
  - `core/services/scheduler/config/config_presets.py:363` [Service] `svc.repo.set_batch(`
  - `core/services/scheduler/config/config_presets.py:373` [Service] `svc.repo.set_batch(svc._active_preset_updates(n))`
  - `core/services/scheduler/config/config_service.py:793` [Service] `self.repo.set_batch(self._active_preset_updates(name, reason=reason))`
  - `core/services/scheduler/config/config_service.py:1373` [Service] `self.repo.set_batch(plan.updates)`
  - `core/services/scheduler/config/config_service.py:1396` [Service] `self.repo.set_batch(`
  - `core/services/scheduler/config/config_service.py:1412` [Service] `self.repo.set_batch(`
  - `core/services/scheduler/config/config_service.py:1420` [Service] `self.repo.set_batch(updates)`
  - `core/services/scheduler/config/config_service.py:1443` [Service] `self.repo.set_batch(`
  - `core/services/scheduler/config/config_service.py:1458` [Service] `self.repo.set_batch(`
  - `core/services/scheduler/config/config_service.py:1482` [Service] `self.repo.set_batch(`
  - `core/services/scheduler/config/config_service.py:1497` [Service] `self.repo.set_batch(`
  - `core/services/scheduler/config/config_service.py:1512` [Service] `self.repo.set_batch(`
  - `core/services/scheduler/config/config_service.py:1533` [Service] `self.repo.set_batch(`
  - `core/services/scheduler/config/config_service.py:1548` [Service] `self.repo.set_batch(`
  - `core/services/scheduler/config/config_service.py:1565` [Service] `self.repo.set_batch(`
  - `core/services/scheduler/config/config_service.py:1580` [Service] `self.repo.set_batch(`
  - `core/services/scheduler/config/config_service.py:1604` [Service] `self.repo.set_batch(`
- **被调用者**（2 个）：`self.executemany`, `str`

### `ConfigRepository.delete()` [公开]
- 位置：第 70-71 行
- 参数：config_key
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`self.execute`

## data/repositories/machine_downtime_repo.py（Repository 层）

### `MachineDowntimeRepository.get()` [公开]
- 位置：第 13-23 行
- 参数：downtime_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self.fetchone`, `MachineDowntime.from_row`, `int`

### `MachineDowntimeRepository.list_by_machine()` [公开]
- 位置：第 25-37 行
- 参数：machine_id, include_cancelled
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/equipment_pages.py:204` [Route] `links = link_svc.list_by_machine(machine_id)`
  - `web/routes/equipment_pages.py:205` [Route] `downtimes = dt_svc.list_by_machine(machine_id, include_cancelled=False)`
  - `core/services/equipment/machine_downtime_service.py:76` [Service] `return self.repo.list_by_machine(mc_id, include_cancelled=include_cancelled)`
  - `core/services/personnel/operator_machine_service.py:292` [Service] `return [self._normalize_link(link) for link in self.repo.list_by_machine(mc_id)]`
- **被调用者**（3 个）：`self.fetchall`, `tuple`, `MachineDowntime.from_row`

### `MachineDowntimeRepository.list_active_after()` [公开]
- 位置：第 39-55 行
- 参数：machine_id, start_time
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/resource_pool_builder.py:154` [Service] `rows = dt_repo.list_active_after(mid, start_str)`
  - `core/services/scheduler/resource_pool_builder.py:301` [Service] `rows = dt_repo.list_active_after(mid, start_str)`
- **被调用者**（2 个）：`self.fetchall`, `MachineDowntime.from_row`

### `MachineDowntimeRepository.has_overlap()` [公开]
- 位置：第 57-80 行
- 参数：machine_id, start_time, end_time, exclude_id
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `core/services/equipment/machine_downtime_service.py:118` [Service] `if self.repo.has_overlap(mc_id, start_time=st_db, end_time=et_db, exclude_id=Non`
  - `core/services/equipment/machine_downtime_service.py:200` [Service] `if self.repo.has_overlap(mid, start_time=st_db, end_time=et_db, exclude_id=None)`
- **被调用者**（5 个）：`bool`, `params.append`, `self.fetchvalue`, `int`, `tuple`

### `MachineDowntimeRepository.list_active_machine_ids_at()` [公开]
- 位置：第 82-96 行
- 参数：now_str
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Index(valu
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:66` [Route] `return {"machine_ids": dt_q.list_active_machine_ids_at(now_str), "degraded": Fal`
  - `core/services/equipment/machine_downtime_query_service.py:18` [Service] `return self.repo.list_active_machine_ids_at(now_str)`
- **被调用者**（6 个）：`self.fetchall`, `set`, `strip`, `out.add`, `str`, `get`

### `MachineDowntimeRepository.create()` [公开]
- 位置：第 98-119 行
- 参数：payload
- 返回类型：Name(id='MachineDowntime', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`self.execute`, `getattr`, `isinstance`, `MachineDowntime.from_row`, `int`

### `MachineDowntimeRepository.update()` [公开]
- 位置：第 121-136 行
- 参数：downtime_id, updates
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`set_parts.append`, `params.append`, `self.execute`, `int`, `tuple`, `join`, `updates.get`

### `MachineDowntimeRepository.cancel()` [公开]
- 位置：第 138-142 行
- 参数：downtime_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/equipment_downtimes.py:90` [Route] `svc.cancel(downtime_id=downtime_id, machine_id=machine_id)`
  - `core/services/equipment/machine_downtime_service.py:243` [Service] `self.repo.cancel(int(d.id))`
- **被调用者**（2 个）：`self.execute`, `int`

## data/repositories/schedule_history_repo.py（Repository 层）

### `ScheduleHistoryRepository.get()` [公开]
- 位置：第 15-20 行
- 参数：history_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self.fetchone`, `ScheduleHistory.from_row`, `int`

### `ScheduleHistoryRepository.list_recent()` [公开]
- 位置：第 22-27 行
- 参数：limit
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（7 处）：
  - `web/routes/dashboard.py:22` [Route] `recent = history_q.list_recent(limit=1)`
  - `web/routes/system_history.py:48` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:35` [Route] `items = svc.list_recent(`
  - `web/routes/domains/scheduler/scheduler_analysis.py:40` [Route] `return [_parse_analysis_summary(_history_item_to_dict(item), source="trend") for`
  - `web/routes/domains/scheduler/scheduler_batches.py:95` [Route] `items = hist_q.list_recent(limit=1)`
  - `core/services/scheduler/schedule_history_query_service.py:19` [Service] `return self.repo.list_recent(limit=int(limit))`
  - `core/services/system/operation_log_service.py:30` [Service] `return self.repo.list_recent(`
- **被调用者**（3 个）：`self.fetchall`, `ScheduleHistory.from_row`, `int`

### `ScheduleHistoryRepository.get_by_version()` [公开]
- 位置：第 29-34 行
- 参数：version
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（8 处）：
  - `web/routes/system_history.py:32` [Route] `item = q.get_by_version(ver)`
  - `web/routes/domains/scheduler/scheduler_analysis.py:46` [Route] `item = history_query_service.get_by_version(int(selected_ver))`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:49` [Route] `selected_history_item = services.schedule_history_query_service.get_by_version(v`
  - `core/services/scheduler/gantt_service.py:74` [Service] `hist = self.history_repo.get_by_version(int(version))`
  - `core/services/scheduler/gantt_service.py:211` [Service] `hist = self.history_repo.get_by_version(ver)`
  - `core/services/scheduler/gantt_service.py:271` [Service] `hist = self.history_repo.get_by_version(ver)`
  - `core/services/scheduler/resource_dispatch_service.py:165` [Service] `hist = self.history_service.get_by_version(int(version))`
  - `core/services/scheduler/schedule_history_query_service.py:25` [Service] `return self.repo.get_by_version(int(version))`
- **被调用者**（3 个）：`self.fetchone`, `ScheduleHistory.from_row`, `int`

### `ScheduleHistoryRepository.get_latest_version()` [公开]
- 位置：第 36-41 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（5 处）：
  - `core/services/report/report_engine.py:112` [Service] `return int(self.history_repo.get_latest_version() or 0)`
  - `core/services/scheduler/gantt_service.py:41` [Service] `v = int(self.history_repo.get_latest_version() or 0)`
  - `core/services/scheduler/resource_dispatch_service.py:82` [Service] `return int(self.history_service.get_latest_version() or 0)`
  - `core/services/scheduler/schedule_history_query_service.py:28` [Service] `return int(self.repo.get_latest_version() or 0)`
  - `core/services/scheduler/run/schedule_input_collector.py:232` [Service] `prev_version = int(svc.history_repo.get_latest_version() or 0)`
- **被调用者**（2 个）：`self.fetchvalue`, `int`

### `ScheduleHistoryRepository.allocate_next_version()` [公开]
- 位置：第 43-94 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_orchestrator.py:254` [Service] `version = int(svc.history_repo.allocate_next_version())`
- **被调用者**（8 个）：`conn.execute`, `fetchone`, `int`, `getattr`, `max`, `RuntimeError`, `AppError`, `error`

### `ScheduleHistoryRepository.list_versions()` [公开]
- 位置：第 96-117 行
- 参数：limit
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（11 处）：
  - `web/routes/reports.py:84` [Route] `versions = engine.list_versions(limit=1)`
  - `web/routes/reports.py:104` [Route] `versions = engine.list_versions(limit=30)`
  - `web/routes/reports.py:137` [Route] `versions = engine.list_versions(limit=30)`
  - `web/routes/reports.py:192` [Route] `versions = engine.list_versions(limit=30)`
  - `web/routes/system_history.py:22` [Route] `versions = q.list_versions(limit=30)`
  - `web/routes/domains/scheduler/scheduler_analysis.py:107` [Route] `versions = q.list_versions(limit=50)`
  - `web/routes/domains/scheduler/scheduler_gantt.py:52` [Route] `versions = services.schedule_history_query_service.list_versions(limit=30)`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:131` [Route] `versions = services.schedule_history_query_service.list_versions(limit=30)`
  - `core/services/report/report_engine.py:109` [Service] `return list(self.history_repo.list_versions(limit=int(limit)))`
  - `core/services/scheduler/resource_dispatch_service.py:85` [Service] `return list(self.history_service.list_versions(limit=limit) or [])`
  - `core/services/scheduler/schedule_history_query_service.py:22` [Service] `return self.repo.list_versions(limit=int(limit))`
- **被调用者**（2 个）：`self.fetchall`, `int`

### `ScheduleHistoryRepository.create()` [公开]
- 位置：第 119-135 行
- 参数：payload
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self.execute`, `int`, `payload.get`

## data/repositories/schedule_repo.py（Repository 层）

### `_require_schedule_op_id()` [私有]
- 位置：第 10-14 行
- 参数：schedule
- 返回类型：Name(id='int', ctx=Load())

### `ScheduleRepository.get()` [公开]
- 位置：第 20-25 行
- 参数：schedule_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self.fetchone`, `Schedule.from_row`, `int`

### `ScheduleRepository.list_by_version()` [公开]
- 位置：第 27-32 行
- 参数：version
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self.fetchall`, `Schedule.from_row`, `int`

### `ScheduleRepository.get_version_time_span()` [公开]
- 位置：第 34-57 行
- 参数：version
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/report/report_engine.py:130` [Service] `span = self.schedule_repo.get_version_time_span(v)`
- **被调用者**（4 个）：`self.fetchone`, `row.get`, `int`, `str`

### `ScheduleRepository.list_between()` [公开]
- 位置：第 59-67 行
- 参数：start_time, end_time, version
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`self.fetchall`, `params.append`, `tuple`, `Schedule.from_row`, `int`

### `ScheduleRepository.list_version_rows_by_op_ids_start_range()` [公开]
- 位置：第 69-110 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/run/freeze_window.py:111` [Service] `rows = svc.schedule_repo.list_version_rows_by_op_ids_start_range(`
- **被调用者**（9 个）：`range`, `len`, `int`, `join`, `out.extend`, `ids.append`, `self.fetchall`, `list`, `tuple`

### `ScheduleRepository.list_overlapping_with_details()` [公开]
- 位置：第 112-160 行
- 参数：start_time, end_time, version
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `core/services/report/report_engine.py:195` [Service] `schedule_rows = self.schedule_repo.list_overlapping_with_details(start_s, end_s,`
  - `core/services/report/report_engine.py:245` [Service] `sch_rows = self.schedule_repo.list_overlapping_with_details(start_s, end_s, v)`
  - `core/services/scheduler/gantt_service.py:205` [Service] `rows = self.schedule_repo.list_overlapping_with_details(wr.start_str, wr.end_exc`
  - `core/services/scheduler/gantt_service.py:268` [Service] `rows = self.schedule_repo.list_overlapping_with_details(wr.start_str, wr.end_exc`
- **被调用者**（2 个）：`self.fetchall`, `int`

### `ScheduleRepository.list_dispatch_rows_with_resource_context()` [公开]
- 位置：第 162-228 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/resource_dispatch_service.py:295` [Service] `rows = self.schedule_repo.list_dispatch_rows_with_resource_context(`
- **被调用者**（5 个）：`self.fetchall`, `int`, `params.append`, `tuple`, `params.extend`

### `ScheduleRepository.list_by_version_with_details()` [公开]
- 位置：第 230-274 行
- 参数：version
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/gantt_critical_chain.py:57` [Service] `return schedule_repo.list_by_version_with_details(int(version))`
- **被调用者**（2 个）：`self.fetchall`, `int`

### `ScheduleRepository.list_by_machine()` [公开]
- 位置：第 276-287 行
- 参数：machine_id, version
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/equipment_pages.py:204` [Route] `links = link_svc.list_by_machine(machine_id)`
  - `web/routes/equipment_pages.py:205` [Route] `downtimes = dt_svc.list_by_machine(machine_id, include_cancelled=False)`
  - `core/services/equipment/machine_downtime_service.py:76` [Service] `return self.repo.list_by_machine(mc_id, include_cancelled=include_cancelled)`
  - `core/services/personnel/operator_machine_service.py:292` [Service] `return [self._normalize_link(link) for link in self.repo.list_by_machine(mc_id)]`
- **被调用者**（3 个）：`self.fetchall`, `Schedule.from_row`, `int`

### `ScheduleRepository.create()` [公开]
- 位置：第 289-300 行
- 参数：schedule
- 返回类型：Name(id='Schedule', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`_require_schedule_op_id`, `self.execute`, `isinstance`, `Schedule.from_row`, `int`

### `ScheduleRepository.bulk_create()` [公开]
- 位置：第 302-321 行
- 参数：schedules
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_persistence.py:386` [Service] `svc.schedule_repo.bulk_create(schedule_rows)`
- **被调用者**（6 个）：`self.executemany`, `params.append`, `isinstance`, `Schedule.from_row`, `_require_schedule_op_id`, `int`

### `ScheduleRepository.delete()` [公开]
- 位置：第 323-324 行
- 参数：schedule_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self.execute`, `int`

### `ScheduleRepository.delete_by_version()` [公开]
- 位置：第 326-327 行
- 参数：version
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self.execute`, `int`

### `ScheduleRepository.delete_by_op()` [公开]
- 位置：第 329-330 行
- 参数：op_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self.execute`, `int`

## scripts/run_quality_gate.py（Script 层）

### `_run_command()` [私有]
- 位置：第 52-69 行
- 参数：display, args, capture_output
- 返回类型：Name(id='str', ctx=Load())

### `_guard_test_abs_path()` [私有]
- 位置：第 72-73 行
- 参数：rel_path
- 返回类型：Name(id='str', ctx=Load())

### `_guard_test_exists()` [私有]
- 位置：第 76-77 行
- 参数：rel_path
- 返回类型：Name(id='bool', ctx=Load())

### `_guard_test_tracked()` [私有]
- 位置：第 80-89 行
- 参数：rel_path
- 返回类型：Name(id='bool', ctx=Load())

### `_git_rev_parse_path()` [私有]
- 位置：第 92-107 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_repo_identity()` [私有]
- 位置：第 110-114 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_assert_guard_tests_ready()` [私有]
- 位置：第 117-128 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_parse_ruff_version()` [私有]
- 位置：第 131-138 行
- 参数：text
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_assert_ruff_version()` [私有]
- 位置：第 141-146 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_parse_pyright_version()` [私有]
- 位置：第 149-153 行
- 参数：text
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_assert_pyright_version()` [私有]
- 位置：第 156-162 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_state_paths()` [私有]
- 位置：第 165-166 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_load_runtime_state()` [私有]
- 位置：第 169-179 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_coerce_int()` [私有]
- 位置：第 182-185 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_describe_runtime_endpoint()` [私有]
- 位置：第 188-191 行
- 参数：host, port
- 返回类型：Name(id='str', ctx=Load())

### `_describe_cleanup_hint()` [私有]
- 位置：第 194-198 行
- 参数：paths
- 返回类型：Name(id='str', ctx=Load())

### `_describe_uncertain_reason()` [私有]
- 位置：第 201-211 行
- 参数：pid_state, health_state, exe_path, port
- 返回类型：Name(id='str', ctx=Load())

### `_pid_signal()` [私有]
- 位置：第 214-234 行
- 参数：payload
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_health_signal()` [私有]
- 位置：第 237-248 行
- 参数：contract
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_runtime_state_snapshot()` [私有]
- 位置：第 251-267 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_assert_no_active_runtime()` [私有]
- 位置：第 270-302 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_git_head_sha()` [私有]
- 位置：第 305-316 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_git_status_lines()` [私有]
- 位置：第 319-330 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_tracked_status_lines()` [私有]
- 位置：第 333-335 行
- 参数：lines
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_parse_collect_nodeids()` [私有]
- 位置：第 338-354 行
- 参数：output
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_build_collection_proof()` [私有]
- 位置：第 357-372 行
- 参数：default_collect_nodeids
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_write_quality_gate_manifest()` [私有]
- 位置：第 375-380 行
- 参数：manifest
- 返回类型：Constant(value=None, kind=None)

### `_apply_worktree_proof()` [私有]
- 位置：第 383-401 行
- 参数：manifest
- 返回类型：Constant(value=None, kind=None)

### `_base_quality_gate_manifest()` [私有]
- 位置：第 404-429 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_parse_args_legacy()` [私有]
- 位置：第 432-435 行
- 参数：argv
- 返回类型：Attribute(value=Name(id='argparse', ctx=Load()), attr='Names

### `_parse_args()` [私有]
- 位置：第 438-445 行
- 参数：argv
- 返回类型：Attribute(value=Name(id='argparse', ctx=Load()), attr='Names

### `main()` [公开]
- 位置：第 448-605 行
- 参数：argv
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（2 处）：
  - `scripts/convert_rotary_shell_unit_excel.py:124` [Script] `raise SystemExit(main())`
  - `scripts/sync_debt_ledger.py:186` [Script] `raise SystemExit(main())`
- **被调用者**（25 个）：`_parse_args`, `isoformat`, `_git_head_sha`, `_git_status_lines`, `_runtime_state_snapshot`, `bool`, `_base_quality_gate_manifest`, `_write_quality_gate_manifest`, `_assert_guard_tests_ready`, `_run_command`, `commands.append`, `_build_collection_proof`, `_assert_ruff_version`, `_assert_pyright_version`, `_apply_worktree_proof`

## scripts/sync_debt_ledger.py（Script 层）

### `_build_parser()` [私有]
- 位置：第 29-67 行
- 参数：无
- 返回类型：Attribute(value=Name(id='argparse', ctx=Load()), attr='Argum

### `_print_summary()` [私有]
- 位置：第 70-72 行
- 参数：title, payload
- 返回类型：Constant(value=None, kind=None)

### `_handle_check()` [私有]
- 位置：第 75-88 行
- 参数：_args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_refresh()` [私有]
- 位置：第 91-113 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_set_entry_fields()` [私有]
- 位置：第 116-137 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_upsert_risk()` [私有]
- 位置：第 140-161 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_delete_risk()` [私有]
- 位置：第 164-172 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `main()` [公开]
- 位置：第 175-182 行
- 参数：argv
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（2 处）：
  - `scripts/convert_rotary_shell_unit_excel.py:124` [Script] `raise SystemExit(main())`
  - `scripts/run_quality_gate.py:610` [Script] `raise SystemExit(main())`
- **被调用者**（5 个）：`_build_parser`, `parser.parse_args`, `int`, `args.handler`, `print`

## tools/quality_gate_operations.py（Tool 层）

### `refresh_migrate_inline_facts()` [公开]
- 位置：第 48-123 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:95` [Script] `next_ledger = refresh_migrate_inline_facts(current)`
- **被调用者**（35 个）：`load_sp02_facts_snapshot`, `cast`, `sorted`, `complexity_scan_map`, `scan_silent_fallback_entries`, `finalize_ledger_update`, `load_ledger`, `get`, `set`, `len`, `find_existing_by_id`, `new_oversize_entries.append`, `new_complexity_entries.append`, `silent_counter.items`, `key.split`

### `refresh_scan_startup_baseline()` [公开]
- 位置：第 126-170 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:97` [Script] `next_ledger = refresh_scan_startup_baseline(current)`
- **被调用者**（30 个）：`validate_startup_samples`, `collect_startup_scope_files`, `cast`, `set`, `scan_oversize_entries`, `scan_complexity_entries`, `scan_silent_fallback_entries`, `finalize_ledger_update`, `load_ledger`, `get`, `find_existing_by_id`, `build_oversize_entry`, `entry.setdefault`, `startup_oversize.append`, `build_complexity_entry`

### `_silent_scan_index()` [私有]
- 位置：第 173-183 行
- 参数：entries
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_resolve_silent_refresh_entry()` [私有]
- 位置：第 186-208 行
- 参数：entry, silent_scan
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `refresh_auto_fields()` [公开]
- 位置：第 211-248 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:100` [Script] `next_ledger = refresh_auto_fields(current)`
- **被调用者**（25 个）：`cast`, `sorted`, `complexity_scan_map`, `_silent_scan_index`, `finalize_ledger_update`, `load_ledger`, `get`, `str`, `len`, `refreshed_oversize.append`, `format`, `refreshed_complexity.append`, `scan_silent_fallback_entries`, `_resolve_silent_refresh_entry`, `refreshed_silent.append`

### `set_entry_fields()` [公开]
- 位置：第 251-273 行
- 参数：ledger, entry_id, updates
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:127` [Script] `next_ledger = set_entry_fields(ledger, args.id, updates)`
- **被调用者**（8 个）：`finalize_ledger_update`, `cast`, `get`, `updates.items`, `QualityGateError`, `str`, `ledger.get`, `entry.get`

### `upsert_risk()` [公开]
- 位置：第 276-311 行
- 参数：ledger, risk_id, entry_ids, owner, reason, review_after, exit_condition, notes
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:142` [Script] `next_ledger = upsert_risk(`
- **被调用者**（10 个）：`collect_main_entry_ids`, `cast`, `finalize_ledger_update`, `list`, `accepted_risks.append`, `QualityGateError`, `ledger.get`, `str`, `current.get`, `dict`

### `delete_risk()` [公开]
- 位置：第 314-320 行
- 参数：ledger, risk_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:166` [Script] `next_ledger = delete_risk(ledger, args.id)`
- **被调用者**（8 个）：`cast`, `finalize_ledger_update`, `dict`, `len`, `QualityGateError`, `ledger.get`, `str`, `risk.get`

### `validate_ledger_against_current_scan()` [公开]
- 位置：第 323-355 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:77` [Script] `summary = validate_ledger_against_current_scan(ledger)`
- **被调用者**（16 个）：`validate_ledger`, `validate_startup_samples`, `str`, `cast`, `complexity_scan_map`, `_silent_scan_index`, `entry.get`, `len`, `format`, `scan_silent_fallback_entries`, `get`, `ledger.get`, `splitlines`, `int`, `QualityGateError`

### `architecture_oversize_allowlist_map()` [公开]
- 位置：第 358-359 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`str`, `dict`, `entry.get`, `cast`, `ledger.get`

### `architecture_complexity_allowlist_map()` [公开]
- 位置：第 362-366 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`format`, `dict`, `entry.get`, `cast`, `ledger.get`

### `architecture_silent_allowlist_map()` [公开]
- 位置：第 369-373 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`str`, `dict`, `entry.get`, `get`, `cast`, `ledger.get`

### `architecture_silent_scan_entries()` [公开]
- 位置：第 376-393 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`scan_silent_fallback_entries`, `sorted`, `collect_quality_rule_files`, `is_startup_scope_path`, `bool`, `str`, `entries.append`, `entry.get`, `dict`, `normalized.pop`

### `architecture_oversize_scan_map()` [公开]
- 位置：第 396-397 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`str`, `entry.get`, `scan_oversize_entries`, `collect_quality_rule_files`

### `architecture_complexity_scan_map()` [公开]
- 位置：第 400-401 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`complexity_scan_map`, `collect_quality_rule_files`

### `_matches_allowed_request_service_helper()` [私有]
- 位置：第 404-411 行
- 参数：entry, helper
- 返回类型：Name(id='bool', ctx=Load())

### `architecture_request_service_direct_assembly_entries()` [公开]
- 位置：第 414-437 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`set`, `scan_request_service_direct_assembly_entries`, `str`, `dict`, `collect_globbed_files`, `REQUEST_SERVICE_TARGET_SYMBOLS.items`, `target_symbols.get`, `any`, `entry.get`, `_matches_allowed_request_service_helper`

### `architecture_repository_bundle_drift_entries()` [公开]
- 位置：第 440-441 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`scan_repository_bundle_drift_entries`, `collect_globbed_files`

## tools/quality_gate_shared.py（Tool 层）

### `now_shanghai_iso()` [公开]
- 位置：第 245-246 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（7 处）：
  - `scripts/sync_debt_ledger.py:79` [Script] `"checked_at": now_shanghai_iso(),`
  - `tools/quality_gate_entries.py:35` [Tool] `"last_verified_at": now_shanghai_iso(),`
  - `tools/quality_gate_entries.py:54` [Tool] `merged["last_verified_at"] = now_shanghai_iso()`
  - `tools/quality_gate_entries.py:64` [Tool] `merged["last_verified_at"] = now_shanghai_iso()`
  - `tools/quality_gate_ledger.py:37` [Tool] `"updated_at": now_shanghai_iso(),`
  - `tools/quality_gate_ledger.py:321` [Tool] `"updated_at": ledger.get("updated_at") or now_shanghai_iso(),`
  - `tools/quality_gate_ledger.py:398` [Tool] `next_ledger["updated_at"] = now_shanghai_iso()`
- **被调用者**（3 个）：`isoformat`, `replace`, `datetime.now`

### `repo_rel()` [公开]
- 位置：第 249-250 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`replace`, `relpath`

### `repo_abs()` [公开]
- 位置：第 253-254 行
- 参数：rel_path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`join`, `replace`, `str`

### `read_text_file()` [公开]
- 位置：第 257-259 行
- 参数：rel_path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（10 处）：
  - `tools/quality_gate_ledger.py:50` [Tool] `text = read_text_file("开发文档/技术债务治理台账.md")`
  - `tools/quality_gate_ledger.py:129` [Tool] `text = read_text_file("开发文档/阶段留痕与验收记录.md")`
  - `tools/quality_gate_operations.py:63` [Tool] `current_value = len(read_text_file(path).splitlines())`
  - `tools/quality_gate_operations.py:221` [Tool] `current_value = len(read_text_file(path).splitlines())`
  - `tools/quality_gate_operations.py:333` [Tool] `current_value = len(read_text_file(str(entry.get("path"))).splitlines())`
  - `tools/quality_gate_scan.py:34` [Tool] `source = read_text_file(rel_path)`
  - `tools/quality_gate_scan.py:573` [Tool] `source_lines = read_text_file(rel_path).splitlines()`
  - `tools/quality_gate_scan.py:698` [Tool] `source_lines = read_text_file(rel_path).splitlines()`
  - `tools/quality_gate_scan.py:745` [Tool] `source = read_text_file(rel_path)`
  - `tools/quality_gate_scan.py:776` [Tool] `line_count = len(read_text_file(rel_path).splitlines())`
- **被调用者**（3 个）：`open`, `f.read`, `repo_abs`

### `write_text_file()` [公开]
- 位置：第 262-268 行
- 参数：rel_path, content
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `tools/quality_gate_ledger.py:123` [Tool] `write_text_file("开发文档/技术债务治理台账.md", render_ledger_markdown(sorted_ledger))`
- **被调用者**（5 个）：`repo_abs`, `dirname`, `os.makedirs`, `open`, `f.write`

### `slugify()` [公开]
- 位置：第 271-280 行
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
- 位置：第 283-296 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`sorted`, `repo_abs`, `os.walk`, `set`, `isdir`, `files.append`, `name.endswith`, `name.startswith`, `repo_rel`, `join`

### `collect_globbed_files()` [公开]
- 位置：第 299-306 行
- 参数：patterns
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `tools/quality_gate_operations.py:421` [Tool] `entries = scan_request_service_direct_assembly_entries(collect_globbed_files(REQ`
  - `tools/quality_gate_operations.py:441` [Tool] `return scan_repository_bundle_drift_entries(collect_globbed_files(REPOSITORY_BUN`
  - `tools/quality_gate_scan.py:569` [Tool] `paths = collect_globbed_files(REQUEST_SERVICE_SCAN_SCOPE_PATTERNS)`
  - `tools/quality_gate_scan.py:694` [Tool] `paths = collect_globbed_files(REPOSITORY_BUNDLE_DRIFT_SCOPE_PATTERNS)`
- **被调用者**（8 个）：`sorted`, `join`, `glob.glob`, `set`, `pattern.replace`, `isfile`, `files.append`, `repo_rel`

### `collect_startup_scope_files()` [公开]
- 位置：第 309-310 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `tools/quality_gate_operations.py:130` [Tool] `startup_files = collect_startup_scope_files()`
  - `tools/quality_gate_scan.py:384` [Tool] `entries = scan_silent_fallback_entries(collect_startup_scope_files())`
- **被调用者**（1 个）：`collect_globbed_files`

### `iter_non_regression_guard_tests()` [公开]
- 位置：第 313-320 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`basename`, `name.startswith`, `out.append`, `str`

### `collect_quality_rule_files()` [公开]
- 位置：第 323-324 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `tools/quality_gate_operations.py:384` [Tool] `for entry in scan_silent_fallback_entries(collect_quality_rule_files()):`
  - `tools/quality_gate_operations.py:397` [Tool] `return {str(entry.get("path")): entry for entry in scan_oversize_entries(collect`
  - `tools/quality_gate_operations.py:401` [Tool] `return complexity_scan_map(collect_quality_rule_files())`
- **被调用者**（4 个）：`sorted`, `set`, `collect_py_files`, `collect_startup_scope_files`

### `is_startup_scope_path()` [公开]
- 位置：第 327-329 行
- 参数：path
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `tools/quality_gate_operations.py:168` [Tool] `"entries": remove_entries_by_predicate(silent_existing, lambda entry: is_startup`
  - `tools/quality_gate_operations.py:385` [Tool] `if is_startup_scope_path(str(entry.get("path"))):`
- **被调用者**（3 个）：`replace`, `rel_path.startswith`, `str`

### `ensure_single_marker()` [公开]
- 位置：第 332-335 行
- 参数：text, marker, label
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`text.count`, `QualityGateError`

### `extract_marked_block()` [公开]
- 位置：第 338-345 行
- 参数：text, begin_marker, end_marker, label
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`ensure_single_marker`, `text.index`, `strip`, `len`, `QualityGateError`

### `extract_json_code_block()` [公开]
- 位置：第 348-360 行
- 参数：text, begin_marker, end_marker, label
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `tools/quality_gate_ledger.py:51` [Tool] `ledger = extract_json_code_block(text, LEDGER_BEGIN, LEDGER_END, "治理台账")`
  - `tools/quality_gate_ledger.py:130` [Tool] `payload = extract_json_code_block(text, SP02_FACT_BEGIN, SP02_FACT_END, "SP02 事实`
- **被调用者**（7 个）：`extract_marked_block`, `re.search`, `strip`, `QualityGateError`, `json.loads`, `isinstance`, `match.group`

### `render_marked_json_block()` [公开]
- 位置：第 363-365 行
- 参数：begin_marker, end_marker, payload
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `tools/quality_gate_ledger.py:61` [Tool] `payload_block = render_marked_json_block(LEDGER_BEGIN, LEDGER_END, ledger)`
- **被调用者**（1 个）：`json.dumps`

## web/bootstrap/entrypoint.py（Bootstrap 层）

### `create_app_with_mode()` [公开]
- 位置：第 62-68 行
- 参数：ui_mode
- 返回类型：Name(id='Flask', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`create_app_core`

### `_parse_cli_args()` [私有]
- 位置：第 71-75 行
- 参数：argv
- 返回类型：无注解

### `_default_deps()` [私有]
- 位置：第 78-99 行
- 参数：ui_mode
- 返回类型：Name(id='EntryPointDeps', ctx=Load())

### `_write_launch_error_with_observability()` [私有]
- 位置：第 102-114 行
- 参数：deps, runtime_dir, message, log_dir
- 返回类型：Constant(value=None, kind=None)

### `configure_runtime_contract()` [公开]
- 位置：第 117-154 行
- 参数：app, runtime_dir, host, port, owner
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`secrets.token_urlsafe`, `deps.write_runtime_host_port_files`, `deps.write_runtime_contract_file`, `get`, `str`, `deps.default_chrome_profile_dir`

### `app_main()` [公开]
- 位置：第 157-263 行
- 参数：ui_mode
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（27 个）：`_parse_cli_args`, `strip`, `runtime_base_dir`, `deps.resolve_prelaunch_log_dir`, `bool`, `deps.current_runtime_owner`, `deps.should_use_runtime_reloader`, `deps.should_own_runtime_resources`, `get`, `deps.pick_bind_host`, `deps.pick_port`, `deps.serve_runtime_app`, `_default_deps`, `int`, `getattr`

## web/bootstrap/factory.py（Bootstrap 层）

### `_app_log_once()` [私有]
- 位置：第 56-64 行
- 参数：app, key, level, message
- 返回类型：Constant(value=None, kind=None)

### `_apply_runtime_config()` [私有]
- 位置：第 70-78 行
- 参数：app
- 返回类型：Constant(value=None, kind=None)

### `should_use_runtime_reloader()` [公开]
- 位置：第 81-83 行
- 参数：debug, frozen
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:197` [Bootstrap] `use_reloader = deps.should_use_runtime_reloader(debug)`
- **被调用者**（2 个）：`bool`, `getattr`

### `_should_register_exit_backup()` [私有]
- 位置：第 86-91 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `should_own_runtime_resources()` [公开]
- 位置：第 94-99 行
- 参数：debug, frozen, run_main
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:198` [Bootstrap] `owns_runtime_resources = deps.should_own_runtime_resources(debug)`
- **被调用者**（2 个）：`_should_register_exit_backup`, `bool`

### `_is_exit_backup_enabled()` [私有]
- 位置：第 102-120 行
- 参数：bm
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_run_exit_backup()` [私有]
- 位置：第 123-142 行
- 参数：manager
- 返回类型：Name(id='bool', ctx=Load())

### `_maintenance_gate_response()` [私有]
- 位置：第 145-152 行
- 参数：无
- 返回类型：无注解

### `_maintenance_detection_failure_response()` [私有]
- 位置：第 155-162 行
- 参数：无
- 返回类型：无注解

### `_default_anchor_file()` [私有]
- 位置：第 165-167 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `should_register_runtime_lifecycle_handlers()` [公开]
- 位置：第 170-171 行
- 参数：debug
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:254` [Bootstrap] `if deps.should_register_runtime_lifecycle_handlers(debug):`
- **被调用者**（2 个）：`should_own_runtime_resources`, `bool`

### `serve_runtime_app()` [公开]
- 位置：第 174-185 行
- 参数：app, host, port
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:262` [Bootstrap] `deps.serve_runtime_app(app, host, port)`
- **被调用者**（3 个）：`make_server`, `int`, `server.serve_forever`

### `request_runtime_server_shutdown()` [公开]
- 位置：第 188-206 行
- 参数：logger
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/system_health.py:53` [Route] `if not request_runtime_server_shutdown(logger=current_app.logger):`
- **被调用者**（5 个）：`start`, `time.sleep`, `server.shutdown`, `threading.Thread`, `safe_log`

### `create_app_core()` [公开]
- 位置：第 209-464 行
- 参数：无
- 返回类型：Name(id='Flask', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:63` [Bootstrap] `return create_app_core(`
- **被调用者**（58 个）：`lower`, `runtime_base_dir`, `join`, `Flask`, `from_object`, `_apply_runtime_config`, `int`, `install_versioned_url_for`, `AppLogger`, `setLevel`, `init_ui_mode`, `dirname`, `os.makedirs`, `abspath`, `ensure_schema`

## web/bootstrap/launcher.py（Bootstrap 层）

### `pick_bind_host()` [公开]
- 位置：第 22-35 行
- 参数：raw_host
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:201` [Bootstrap] `host = deps.pick_bind_host(raw_host, logger=app.logger)`
- **被调用者**（5 个）：`strip`, `ipaddress.ip_address`, `getattr`, `ValueError`, `logger.warning`

### `_can_bind()` [私有]
- 位置：第 38-53 行
- 参数：host0, port0
- 返回类型：Name(id='bool', ctx=Load())

### `pick_port()` [公开]
- 位置：第 56-94 行
- 参数：host, preferred
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:213` [Bootstrap] `host, port = deps.pick_port(host, preferred_port, logger=app.logger)`
- **被调用者**（7 个）：`socket.socket`, `_can_bind`, `int`, `candidates.append`, `s.bind`, `s.getsockname`, `s.close`

### `_normalize_db_path_for_runtime()` [私有]
- 位置：第 97-101 行
- 参数：db_path
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_abs_dir()` [私有]
- 位置：第 104-108 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())

### `_compose_runtime_owner()` [私有]
- 位置：第 111-116 行
- 参数：user, domain
- 返回类型：Name(id='str', ctx=Load())

### `current_runtime_owner()` [公开]
- 位置：第 119-127 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:183` [Bootstrap] `runtime_owner = deps.current_runtime_owner()`
- **被调用者**（5 个）：`strip`, `_compose_runtime_owner`, `str`, `get`, `getpass.getuser`

### `read_shared_data_root_from_registry()` [公开]
- 位置：第 130-154 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`int`, `getattr`, `_normalize_abs_dir`, `winreg.OpenKey`, `winreg.QueryValueEx`, `winreg.CloseKey`

### `resolve_shared_data_root()` [公开]
- 位置：第 157-173 行
- 参数：base_dir
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/factory.py:72` [Bootstrap] `data_root = resolve_shared_data_root(base_dir)`
- **被调用者**（9 个）：`_normalize_abs_dir`, `read_shared_data_root_from_registry`, `get`, `abspath`, `bool`, `join`, `isdir`, `str`, `getattr`

### `resolve_prelaunch_log_dir()` [公开]
- 位置：第 176-180 行
- 参数：runtime_dir
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:177` [Bootstrap] `prelaunch_log_dir = deps.resolve_prelaunch_log_dir(runtime_dir)`
- **被调用者**（4 个）：`_normalize_abs_dir`, `join`, `get`, `resolve_shared_data_root`

### `_runtime_log_dir()` [私有]
- 位置：第 183-184 行
- 参数：runtime_dir
- 返回类型：Name(id='str', ctx=Load())

### `resolve_runtime_state_dir()` [公开]
- 位置：第 187-195 行
- 参数：runtime_dir, cfg_log_dir
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`abspath`, `_runtime_log_dir`, `strip`, `str`

### `_resolve_runtime_state_dir_for_read()` [私有]
- 位置：第 198-212 行
- 参数：runtime_dir_or_state_dir
- 返回类型：Name(id='str', ctx=Load())

### `_runtime_dir_from_state_dir()` [私有]
- 位置：第 215-221 行
- 参数：state_dir
- 返回类型：Name(id='str', ctx=Load())

### `_resolve_runtime_stop_context()` [私有]
- 位置：第 224-231 行
- 参数：runtime_dir_or_state_dir
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_runtime_log_mirror_dir()` [私有]
- 位置：第 234-239 行
- 参数：runtime_dir, cfg_log_dir
- 返回类型：Name(id='str', ctx=Load())

### `_state_contract_paths()` [私有]
- 位置：第 242-248 行
- 参数：state_dir
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_runtime_lock_path()` [私有]
- 位置：第 251-252 行
- 参数：state_dir
- 返回类型：Name(id='str', ctx=Load())

### `_launch_error_path()` [私有]
- 位置：第 255-256 行
- 参数：state_dir
- 返回类型：Name(id='str', ctx=Load())

### `resolve_runtime_state_paths()` [公开]
- 位置：第 259-278 行
- 参数：runtime_dir_or_state_dir
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:166` [Script] `return launcher.resolve_runtime_state_paths(REPO_ROOT)`
- **被调用者**（5 个）：`_resolve_runtime_state_dir_for_read`, `_runtime_dir_from_state_dir`, `_state_contract_paths`, `_runtime_lock_path`, `_launch_error_path`

### `_write_runtime_state_triplet()` [私有]
- 位置：第 281-291 行
- 参数：state_dir, host, port, db_for_runtime
- 返回类型：Constant(value=None, kind=None)

### `_write_key_value_file()` [私有]
- 位置：第 294-303 行
- 参数：path, data
- 返回类型：Constant(value=None, kind=None)

### `_read_key_value_file()` [私有]
- 位置：第 306-324 行
- 参数：path
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_pid_exists()` [私有]
- 位置：第 327-354 行
- 参数：pid
- 返回类型：Name(id='bool', ctx=Load())

### `runtime_pid_exists()` [公开]
- 位置：第 357-360 行
- 参数：pid
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:224` [Script] `pid_exists = bool(launcher.runtime_pid_exists(pid))`
- **被调用者**（1 个）：`_pid_exists`

### `runtime_pid_matches_executable()` [公开]
- 位置：第 363-369 行
- 参数：pid, expected_exe_path
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:229` [Script] `pid_match = launcher.runtime_pid_matches_executable(pid, exe_path)`
- **被调用者**（1 个）：`_pid_matches_contract`

### `probe_runtime_health()` [公开]
- 位置：第 372-375 行
- 参数：host, port, timeout_s
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:247` [Script] `healthy = bool(launcher.probe_runtime_health(host, port, timeout_s=1.0))`
- **被调用者**（1 个）：`_probe_runtime_health`

### `RuntimeLockError.__init__()` [私有]
- 位置：第 379-385 行
- 参数：message
- 返回类型：无注解

### `read_runtime_lock()` [公开]
- 位置：第 388-403 行
- 参数：runtime_dir_or_state_dir
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:174` [Script] `lock = launcher.read_runtime_lock(REPO_ROOT)`
- **被调用者**（7 个）：`_resolve_runtime_state_dir_for_read`, `_runtime_lock_path`, `_read_key_value_file`, `dict`, `exists`, `int`, `payload.get`

### `_is_runtime_lock_active()` [私有]
- 位置：第 406-420 行
- 参数：lock_payload, expected_exe_path
- 返回类型：Name(id='bool', ctx=Load())

### `acquire_runtime_lock()` [公开]
- 位置：第 423-483 行
- 参数：runtime_dir, cfg_log_dir
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:225` [Bootstrap] `deps.acquire_runtime_lock(`
- **被调用者**（22 个）：`resolve_runtime_state_dir`, `os.makedirs`, `_runtime_lock_path`, `strip`, `range`, `RuntimeLockError`, `int`, `time.strftime`, `abspath`, `os.getpid`, `time.gmtime`, `os.open`, `str`, `_is_runtime_lock_active`, `os.fdopen`

### `release_runtime_lock()` [公开]
- 位置：第 486-503 行
- 参数：runtime_dir_or_state_dir, expected_pid
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`read_runtime_lock`, `int`, `os.remove`, `existing.get`, `str`, `os.getpid`

### `write_launch_error()` [公开]
- 位置：第 506-512 行
- 参数：runtime_dir, message, cfg_log_dir
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:112` [Bootstrap] `deps.write_launch_error(runtime_dir, message, log_dir)`
- **被调用者**（7 个）：`resolve_runtime_state_dir`, `os.makedirs`, `_launch_error_path`, `open`, `f.write`, `strip`, `str`

### `clear_launch_error()` [公开]
- 位置：第 515-523 行
- 参数：runtime_dir_or_state_dir
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:185` [Bootstrap] `deps.clear_launch_error(prelaunch_log_dir)`
- **被调用者**（3 个）：`_resolve_runtime_state_dir_for_read`, `_launch_error_path`, `os.remove`

### `write_runtime_host_port_files()` [公开]
- 位置：第 526-554 行
- 参数：runtime_dir, cfg_log_dir, host, port, db_path
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:132` [Bootstrap] `deps.write_runtime_host_port_files(`
- **被调用者**（8 个）：`_normalize_db_path_for_runtime`, `resolve_runtime_state_dir`, `os.makedirs`, `_write_runtime_state_triplet`, `_runtime_log_mirror_dir`, `_state_contract_paths`, `logger.info`, `int`

### `default_chrome_profile_dir()` [公开]
- 位置：第 557-561 行
- 参数：runtime_dir
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:151` [Bootstrap] `chrome_profile_dir=deps.default_chrome_profile_dir(runtime_dir),`
- **被调用者**（4 个）：`strip`, `join`, `str`, `get`

### `_runtime_contract_path()` [私有]
- 位置：第 564-565 行
- 参数：state_dir
- 返回类型：Name(id='str', ctx=Load())

### `_runtime_contract_payload()` [私有]
- 位置：第 568-610 行
- 参数：runtime_dir, host, port
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `write_runtime_contract_file()` [公开]
- 位置：第 613-664 行
- 参数：runtime_dir, host, port
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:140` [Bootstrap] `deps.write_runtime_contract_file(`
- **被调用者**（10 个）：`_runtime_contract_payload`, `resolve_runtime_state_dir`, `os.makedirs`, `_runtime_contract_path`, `_runtime_log_mirror_dir`, `open`, `json.dump`, `f.write`, `logger.info`, `f2.write`

### `read_runtime_contract()` [公开]
- 位置：第 667-693 行
- 参数：runtime_dir
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:173` [Script] `contract = launcher.read_runtime_contract(REPO_ROOT)`
- **被调用者**（8 个）：`_resolve_runtime_state_dir_for_read`, `_runtime_contract_path`, `exists`, `isinstance`, `int`, `open`, `json.load`, `payload.get`

### `delete_runtime_contract_files()` [公开]
- 位置：第 696-737 行
- 参数：runtime_dir
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（16 个）：`_resolve_runtime_state_dir_for_read`, `_runtime_contract_path`, `isinstance`, `paths.extend`, `open`, `json.load`, `strip`, `os.remove`, `abspath`, `payload.get`, `join`, `str`, `_runtime_log_dir`, `normcase`, `log_dirs.append`

### `_build_shutdown_url()` [私有]
- 位置：第 740-751 行
- 参数：contract
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_request_runtime_shutdown()` [私有]
- 位置：第 754-768 行
- 参数：contract, timeout_s
- 返回类型：Name(id='bool', ctx=Load())

### `_probe_runtime_health()` [私有]
- 位置：第 771-783 行
- 参数：host, port, timeout_s
- 返回类型：Name(id='bool', ctx=Load())

### `_run_powershell_text()` [私有]
- 位置：第 786-805 行
- 参数：script, timeout_s
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_query_process_executable_path()` [私有]
- 位置：第 808-838 行
- 参数：pid
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_pid_matches_contract()` [私有]
- 位置：第 841-850 行
- 参数：pid, expected_exe_path
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_kill_runtime_pid()` [私有]
- 位置：第 853-872 行
- 参数：pid
- 返回类型：Name(id='bool', ctx=Load())

### `_list_aps_chrome_pids()` [私有]
- 位置：第 875-925 行
- 参数：profile_dir
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `stop_aps_chrome_processes()` [公开]
- 位置：第 928-949 行
- 参数：profile_dir, logger
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`strip`, `_list_aps_chrome_pids`, `str`, `_kill_runtime_pid`, `logger.warning`

### `_stop_aps_chrome_if_requested()` [私有]
- 位置：第 952-960 行
- 参数：stop_aps_chrome, profile_dir
- 返回类型：Name(id='bool', ctx=Load())

### `_read_runtime_endpoint_files()` [私有]
- 位置：第 963-986 行
- 参数：state_dir
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_classify_runtime_state()` [私有]
- 位置：第 989-1063 行
- 参数：runtime_dir_or_state_dir
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_runtime_stop_is_complete()` [私有]
- 位置：第 1066-1070 行
- 参数：status
- 返回类型：Name(id='bool', ctx=Load())

### `_can_force_kill_runtime()` [私有]
- 位置：第 1073-1095 行
- 参数：status
- 返回类型：Name(id='bool', ctx=Load())

### `_runtime_stop_failure_reason()` [私有]
- 位置：第 1098-1107 行
- 参数：status
- 返回类型：Name(id='str', ctx=Load())

### `_runtime_process_inactive()` [私有]
- 位置：第 1110-1127 行
- 参数：pid, pid_match_hint
- 返回类型：Name(id='bool', ctx=Load())

### `stop_runtime_from_dir()` [公开]
- 位置：第 1130-1194 行
- 参数：runtime_dir
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:170` [Bootstrap] `deps.stop_runtime_from_dir(`
- **被调用者**（21 个）：`_resolve_runtime_stop_context`, `_classify_runtime_state`, `_runtime_stop_is_complete`, `isinstance`, `_can_force_kill_runtime`, `_runtime_stop_failure_reason`, `delete_runtime_contract_files`, `time.time`, `max`, `status.get`, `_request_runtime_shutdown`, `time.sleep`, `_kill_runtime_pid`, `strip`, `default_chrome_profile_dir`

## web/error_boundary.py（Other 层）

### `wants_json_error_response()` [公开]
- 位置：第 10-18 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`startswith`

### `wants_json_error_response_or_default()` [公开]
- 位置：第 21-33 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `web/bootstrap/factory.py:147` [Bootstrap] `if wants_json_error_response_or_default(`
  - `web/bootstrap/factory.py:157` [Bootstrap] `if wants_json_error_response_or_default(`
- **被调用者**（4 个）：`wants_json_error_response`, `bool`, `getattr`, `logger.warning`

### `_details_text()` [私有]
- 位置：第 36-44 行
- 参数：details
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `render_minimal_error_page()` [公开]
- 位置：第 47-90 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/bootstrap/factory.py:318` [Bootstrap] `render_minimal_error_page(`
  - `web/bootstrap/factory.py:331` [Bootstrap] `render_minimal_error_page(`
- **被调用者**（5 个）：`html.escape`, `_details_text`, `join`, `str`, `extra_parts.append`

### `render_error_template()` [公开]
- 位置：第 93-121 行
- 参数：template_name
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/bootstrap/factory.py:152` [Bootstrap] `return render_error_template(title="系统维护中", code="503", message=message), 503`
  - `web/bootstrap/factory.py:162` [Bootstrap] `return render_error_template(title="系统状态检测失败", code="500", message=message), 500`
- **被调用者**（4 个）：`render_template`, `getattr`, `render_minimal_error_page`, `logger.error`

## web/error_handlers.py（Other 层）

### `_resolve_field_label()` [私有]
- 位置：第 13-17 行
- 参数：details
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `register_error_handlers()` [公开]
- 位置：第 20-84 行
- 参数：app
- 返回类型：无注解
- **调用者**（1 处）：
  - `web/bootstrap/factory.py:432` [Bootstrap] `register_error_handlers(app)`
- **被调用者**（9 个）：`app.errorhandler`, `warning`, `wants_json_error_response_or_default`, `error_response`, `error`, `render_error_template`, `e.to_dict`, `_resolve_field_label`, `traceback.format_exc`

## web/routes/_scheduler_compat.py（Route 层）

### `load_scheduler_route_module()` [公开]
- 位置：第 7-10 行
- 参数：domain_module
- 返回类型：Name(id='ModuleType', ctx=Load())
- **调用者**（9 处）：
  - `web/routes/scheduler_analysis.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_analysis")`
  - `web/routes/scheduler_batches.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_batches")`
  - `web/routes/scheduler_batch_detail.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_batch_detail")`
  - `web/routes/scheduler_config.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_config")`
  - `web/routes/scheduler_excel_batches.py:6` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_excel_batches"`
  - `web/routes/scheduler_excel_calendar.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_excel_calendar`
  - `web/routes/scheduler_ops.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_ops")`
  - `web/routes/scheduler_run.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_run")`
  - `web/routes/scheduler_week_plan.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_week_plan")`
- **被调用者**（1 个）：`importlib.import_module`

## web/routes/domains/scheduler/scheduler_analysis.py（Route 层）

### `_history_item_to_dict()` [私有]
- 位置：第 16-17 行
- 参数：item
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_parse_analysis_summary()` [私有]
- 位置：第 20-36 行
- 参数：row
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_load_recent_analysis_history()` [私有]
- 位置：第 39-40 行
- 参数：history_query_service
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_load_selected_analysis_item()` [私有]
- 位置：第 43-47 行
- 参数：history_query_service, selected_ver
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_selected_analysis_version()` [私有]
- 位置：第 50-56 行
- 参数：versions
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_missing_history_message()` [私有]
- 位置：第 59-62 行
- 参数：selected_ver
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_selected_history_placeholder()` [私有]
- 位置：第 65-78 行
- 参数：selected_ver
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_ensure_selected_analysis_context()` [私有]
- 位置：第 81-91 行
- 参数：ctx
- 返回类型：Constant(value=None, kind=None)

### `_trend_summary_state()` [私有]
- 位置：第 94-101 行
- 参数：raw_hist
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `analysis_page()` [公开]
- 位置：第 105-138 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`bp.get`, `q.list_versions`, `_selected_analysis_version`, `_load_recent_analysis_history`, `_load_selected_analysis_item`, `build_analysis_context`, `build_requested_history_resolution`, `_ensure_selected_analysis_context`, `build_summary_display_state`, `render_template`, `ctx.get`, `_missing_history_message`, `get`, `_trend_summary_state`

## web/routes/domains/scheduler/scheduler_batches.py（Route 层）

### `batches_page()` [公开]
- 位置：第 38-160 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（44 个）：`bp.get`, `strip`, `parse_page_args`, `batch_svc.list`, `paginate_rows`, `cfg_svc.get_snapshot`, `cfg_svc.get_available_strategies`, `get_scheduler_visible_config_field_metadata`, `build_config_degraded_display_state`, `cfg_svc.get_preset_display_state`, `list`, `preset_display_state.get`, `dict`, `build_auto_assign_persist_display_state`, `build_summary_display_state`

### `batches_manage_page()` [公开]
- 位置：第 164-209 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `strip`, `parse_page_args`, `batch_svc.list`, `paginate_rows`, `part_svc.list`, `render_template`, `view_rows.append`, `get`, `b.to_dict`, `_priority_zh`, `_ready_zh`, `_batch_status_zh`

### `create_batch()` [公开]
- 位置：第 213-244 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`bp.post`, `get`, `_strict_mode_enabled`, `batch_svc.create_batch_from_template`, `flash`, `_surface_schedule_warnings`, `redirect`, `batch_svc.consume_user_visible_warnings`, `url_for`, `len`, `batch_svc.list_operations`

### `delete_batch()` [公开]
- 位置：第 248-262 行
- 参数：batch_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `strip`, `_safe_next_url`, `batch_svc.delete`, `flash`, `redirect`, `url_for`, `get`

### `bulk_delete_batches()` [公开]
- 位置：第 266-294 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `getlist`, `flash`, `redirect`, `join`, `url_for`, `batch_svc.delete`, `failed.append`, `failed_details.append`, `exception`, `len`, `str`

### `_next_batch_id_like()` [私有]
- 位置：第 297-317 行
- 参数：src, exists_fn
- 返回类型：Name(id='str', ctx=Load())

### `_bulk_update_one_batch()` [私有]
- 位置：第 320-342 行
- 参数：batch_svc, bid
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `bulk_copy_batches()` [公开]
- 位置：第 347-376 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`bp.post`, `getlist`, `flash`, `redirect`, `url_for`, `_next_batch_id_like`, `batch_svc.copy_batch`, `mappings.append`, `str`, `failed.append`, `exception`, `len`, `join`, `get`

### `bulk_update_batches()` [公开]
- 位置：第 380-408 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.post`, `getlist`, `get`, `flash`, `redirect`, `strip`, `_bulk_update_one_batch`, `url_for`, `remark.strip`, `str`, `failed.append`, `len`, `join`

### `generate_ops()` [公开]
- 位置：第 412-434 行
- 参数：batch_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `_strict_mode_enabled`, `batch_svc.get`, `redirect`, `get`, `batch_svc.create_batch_from_template`, `len`, `flash`, `_surface_schedule_warnings`, `url_for`, `batch_svc.list_operations`, `batch_svc.consume_user_visible_warnings`

## web/routes/domains/scheduler/scheduler_bp.py（Route 层）

### `_priority_zh()` [私有]
- 位置：第 13-14 行
- 参数：v
- 返回类型：Name(id='str', ctx=Load())

### `_ready_zh()` [私有]
- 位置：第 17-18 行
- 参数：v
- 返回类型：Name(id='str', ctx=Load())

### `_batch_status_zh()` [私有]
- 位置：第 21-22 行
- 参数：v
- 返回类型：Name(id='str', ctx=Load())

### `_day_type_zh()` [私有]
- 位置：第 25-26 行
- 参数：v
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_warning_texts()` [私有]
- 位置：第 29-40 行
- 参数：values
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_surface_schedule_warnings()` [私有]
- 位置：第 43-52 行
- 参数：messages
- 返回类型：Constant(value=None, kind=None)

### `_surface_schedule_errors()` [私有]
- 位置：第 55-66 行
- 参数：messages
- 返回类型：Constant(value=None, kind=None)

### `_surface_secondary_degradation_messages()` [私有]
- 位置：第 69-98 行
- 参数：messages
- 返回类型：Constant(value=None, kind=None)

## web/routes/domains/scheduler/scheduler_calendar_pages.py（Route 层）

### `calendar_page()` [公开]
- 位置：第 14-39 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `CalendarService`, `ConfigService`, `cfg_svc.get_holiday_default_efficiency_display_state`, `render_template`, `c.to_dict`, `_normalize_day_type`, `_normalize_yesno`, `_day_type_zh`, `getattr`, `cal_svc.list_all`, `r.get`

### `calendar_upsert()` [公开]
- 位置：第 43-74 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.post`, `get`, `CalendarService`, `flash`, `redirect`, `cal_svc.upsert`, `url_for`, `getattr`, `strip`, `str`

## web/routes/domains/scheduler/scheduler_config.py（Route 层）

### `_warn_scheduler_config_degraded_once()` [私有]
- 位置：第 39-45 行
- 参数：fields
- 返回类型：Constant(value=None, kind=None)

### `_resolve_scheduler_manual_md_path()` [私有]
- 位置：第 48-73 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_resolve_manual_back_url()` [私有]
- 位置：第 76-84 行
- 参数：raw_src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_build_manual_page_url()` [私有]
- 位置：第 87-93 行
- 参数：raw_src, raw_page
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_scheduler_manual_args()` [私有]
- 位置：第 96-103 行
- 参数：raw_src, raw_page
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_resolve_manual_entry_endpoint()` [私有]
- 位置：第 106-110 行
- 参数：manual_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_format_manual_mtime()` [私有]
- 位置：第 113-117 行
- 参数：manual_path
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_load_manual_text_and_mtime()` [私有]
- 位置：第 120-144 行
- 参数：manual_path, candidates
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_manual_download_url()` [私有]
- 位置：第 147-156 行
- 参数：manual_path, safe_src, safe_page
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_build_related_manual_links()` [私有]
- 位置：第 159-171 行
- 参数：related_manuals, link_src
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_resolve_page_back_action()` [私有]
- 位置：第 174-179 行
- 参数：raw_page, back_url
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_manual_page_view_state()` [私有]
- 位置：第 182-219 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `config_manual_page()` [公开]
- 位置：第 223-264 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `strip`, `_normalize_scheduler_manual_args`, `_resolve_manual_back_url`, `_resolve_scheduler_manual_md_path`, `_load_manual_text_and_mtime`, `_build_manual_download_url`, `_build_manual_page_view_state`, `render_template`, `flash`, `back_url.startswith`, `get`

### `config_manual_download()` [公开]
- 位置：第 268-292 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.get`, `strip`, `_normalize_scheduler_manual_args`, `_resolve_scheduler_manual_md_path`, `flash`, `redirect`, `send_file`, `_build_manual_page_url`, `exception`, `get`

### `config_page()` [公开]
- 位置：第 294-342 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.get`, `cfg_svc.get_snapshot`, `cfg_svc.get_available_strategies`, `get_scheduler_visible_config_field_metadata`, `build_config_degraded_display_state`, `_warn_scheduler_config_degraded_once`, `float`, `config_field_warnings.get`, `cfg_svc.get_preset_display_state`, `list`, `preset_display_state.get`, `dict`, `build_auto_assign_persist_display_state`, `render_template`, `getattr`

### `preset_apply()` [公开]
- 位置：第 346-369 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `redirect`, `get`, `_safe_next_url`, `url_for`, `_normalize_requested_preset_name`, `_is_custom_preset_name`, `cfg_svc.apply_preset`, `_flash_preset_apply_feedback`, `cfg_svc.mark_active_preset_custom`, `flash`, `exception`

### `preset_save()` [公开]
- 位置：第 373-399 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `redirect`, `get`, `cfg_svc.save_preset`, `url_for`, `strip`, `list`, `flash`, `exception`, `_format_preset_error_flash`, `str`, `saved.get`

### `preset_delete()` [公开]
- 位置：第 403-414 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.post`, `redirect`, `get`, `cfg_svc.delete_preset`, `flash`, `url_for`, `exception`

### `_collect_scheduler_config_form_payload()` [私有]
- 位置：第 417-440 行
- 参数：form
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_normalize_requested_preset_name()` [私有]
- 位置：第 443-444 行
- 参数：name
- 返回类型：Name(id='str', ctx=Load())

### `_is_custom_preset_name()` [私有]
- 位置：第 447-448 行
- 参数：name_text
- 返回类型：Name(id='bool', ctx=Load())

### `update_config()` [公开]
- 位置：第 452-463 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `redirect`, `_collect_scheduler_config_form_payload`, `cfg_svc.save_page_config`, `_flash_config_save_outcome`, `url_for`, `flash`, `exception`

### `restore_config_default()` [公开]
- 位置：第 465-469 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.post`, `cfg_svc.restore_default`, `flash`, `redirect`, `url_for`

## web/routes/domains/scheduler/scheduler_config_display_state.py（Route 层）

### `get_scheduler_visible_config_field_metadata()` [公开]
- 位置：第 27-28 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:68` [Route] `config_field_metadata = get_scheduler_visible_config_field_metadata()`
  - `web/routes/domains/scheduler/scheduler_config.py:303` [Route] `config_field_metadata = get_scheduler_visible_config_field_metadata()`
- **被调用者**（2 个）：`page_metadata_for`, `list`

### `_format_config_display_value()` [私有]
- 位置：第 31-39 行
- 参数：field, value
- 返回类型：Name(id='str', ctx=Load())

### `build_config_degraded_display_state()` [公开]
- 位置：第 42-75 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:69` [Route] `config_field_warnings, config_degraded_fields, config_hidden_warnings = build_co`
  - `web/routes/domains/scheduler/scheduler_config.py:304` [Route] `config_field_warnings, config_degraded_fields, config_hidden_warnings = build_co`
- **被调用者**（9 个）：`getattr`, `strip`, `hidden_warnings.append`, `isinstance`, `config_field_metadata.get`, `str`, `_format_config_display_value`, `degraded_fields.append`, `get`

### `build_auto_assign_persist_display_state()` [公开]
- 位置：第 78-99 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:87` [Route] `current_auto_assign_persist_state = build_auto_assign_persist_display_state(geta`
  - `web/routes/domains/scheduler/scheduler_batches.py:127` [Route] `latest_auto_assign_persist_state = build_auto_assign_persist_display_state(`
  - `web/routes/domains/scheduler/scheduler_config.py:323` [Route] `auto_assign_persist_state = build_auto_assign_persist_display_state(getattr(cfg,`
- **被调用者**（3 个）：`lower`, `strip`, `str`

## web/routes/domains/scheduler/scheduler_config_feedback.py（Route 层）

### `_normalized_error_fields()` [私有]
- 位置：第 10-15 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_format_single_field_preset_error()` [私有]
- 位置：第 18-26 行
- 参数：detail, field_key
- 返回类型：Name(id='str', ctx=Load())

### `_format_preset_error_flash()` [私有]
- 位置：第 29-44 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_flash_preset_apply_feedback()` [私有]
- 位置：第 47-72 行
- 参数：applied
- 返回类型：Constant(value=None, kind=None)

### `_config_save_outcome_fields()` [私有]
- 位置：第 75-76 行
- 参数：outcome, field_name
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_config_save_primary_flash()` [私有]
- 位置：第 79-91 行
- 参数：outcome
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_iter_config_save_notice_messages()` [私有]
- 位置：第 94-105 行
- 参数：outcome
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_flash_config_save_outcome()` [私有]
- 位置：第 108-114 行
- 参数：outcome
- 返回类型：Constant(value=None, kind=None)

## web/routes/domains/scheduler/scheduler_history_resolution.py（Route 层）

### `build_requested_history_resolution()` [公开]
- 位置：第 6-24 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_analysis.py:113` [Route] `selected_history_resolution = build_requested_history_resolution(`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:134` [Route] `selected_history_resolution = build_requested_history_resolution(`
- **被调用者**（4 个）：`int`, `bool`, `strip`, `str`

## web/routes/domains/scheduler/scheduler_resource_dispatch.py（Route 层）

### `_svc()` [私有]
- 位置：第 48-49 行
- 参数：无
- 返回类型：Name(id='ResourceDispatchService', ctx=Load())

### `_arg_text()` [私有]
- 位置：第 52-57 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_request_kwargs()` [私有]
- 位置：第 60-73 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_current_request_args()` [私有]
- 位置：第 76-83 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_url_with_query()` [私有]
- 位置：第 86-91 行
- 参数：endpoint, query
- 返回类型：Name(id='str', ctx=Load())

### `_page_url()` [私有]
- 位置：第 94-95 行
- 参数：query
- 返回类型：Name(id='str', ctx=Load())

### `_export_url()` [私有]
- 位置：第 98-105 行
- 参数：filters
- 返回类型：Name(id='str', ctx=Load())

### `_drop_keys()` [私有]
- 位置：第 108-110 行
- 参数：values
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_error_field()` [私有]
- 位置：第 113-119 行
- 参数：exc
- 返回类型：Name(id='str', ctx=Load())

### `_sanitize_dispatch_args_from_error()` [私有]
- 位置：第 122-130 行
- 参数：exc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_invalid_query_keys_from_error()` [私有]
- 位置：第 133-135 行
- 参数：exc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_error_payload_with_invalid_query_keys()` [私有]
- 位置：第 138-149 行
- 参数：exc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `resource_dispatch_page()` [公开]
- 位置：第 153-185 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`bp.get`, `_svc`, `render_template`, `svc.build_page_context`, `context.get`, `_export_url`, `_current_request_args`, `flash`, `exception`, `url_for`, `_request_kwargs`, `_sanitize_dispatch_args_from_error`, `redirect`, `_page_url`

### `resource_dispatch_data()` [公开]
- 位置：第 189-199 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.get`, `get_dispatch_payload`, `jsonify`, `exception`, `_svc`, `_request_kwargs`, `_error_payload_with_invalid_query_keys`

### `resource_dispatch_export()` [公开]
- 位置：第 203-238 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`bp.get`, `time.time`, `_svc`, `redirect`, `svc.build_export`, `int`, `log_excel_export`, `send_file`, `_page_url`, `payload.get`, `flash`, `exception`, `_current_request_args`, `_request_kwargs`, `summary.get`

## web/routes/domains/scheduler/scheduler_run.py（Route 层）

### `_parse_optional_checkbox_flag()` [私有]
- 位置：第 17-27 行
- 参数：name
- 返回类型：无注解

### `_run_result_flash()` [私有]
- 位置：第 30-50 行
- 参数：result
- 返回类型：Constant(value=None, kind=None)

### `run_schedule()` [公开]
- 位置：第 54-108 行
- 参数：无
- 返回类型：无注解
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_week_plan.py:247` [Route] `result = sch_svc.run_schedule(`
  - `core/services/scheduler/run/schedule_optimizer.py:378` [Service] `说明：为保证兼容，本函数尽量保持与原 `ScheduleService.run_schedule()` 相同的口径与留痕结构。`
- **被调用者**（25 个）：`bp.post`, `getlist`, `_parse_optional_checkbox_flag`, `_strict_mode_enabled`, `redirect`, `get`, `sch_svc.run_schedule`, `build_summary_display_state`, `_run_result_flash`, `summary_display.get`, `isinstance`, `_surface_secondary_degradation_messages`, `_surface_schedule_warnings`, `_surface_schedule_errors`, `url_for`

## web/routes/domains/scheduler/scheduler_week_plan.py（Route 层）

### `_get_int_arg()` [私有]
- 位置：第 25-32 行
- 参数：name, default
- 返回类型：Name(id='int', ctx=Load())

### `_parse_optional_checkbox_flag()` [私有]
- 位置：第 35-45 行
- 参数：name
- 返回类型：无注解

### `_load_selected_week_plan_summary()` [私有]
- 位置：第 48-66 行
- 参数：services, version
- 返回类型：无注解

### `_build_week_plan_preview_state()` [私有]
- 位置：第 69-84 行
- 参数：data
- 返回类型：无注解

### `_flash_summary_primary_degradation()` [私有]
- 位置：第 87-93 行
- 参数：summary_display
- 返回类型：无注解

### `_flash_simulate_completion()` [私有]
- 位置：第 96-103 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_flash_simulate_summary()` [私有]
- 位置：第 106-116 行
- 参数：summary, summary_display
- 返回类型：Constant(value=None, kind=None)

### `week_plan_page()` [公开]
- 位置：第 120-163 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（18 个）：`bp.get`, `_get_int_arg`, `svc.get_latest_version_or_1`, `svc.resolve_week_range`, `normalize_version_or_latest`, `list_versions`, `svc.get_week_plan_rows`, `_load_selected_week_plan_summary`, `build_requested_history_resolution`, `_build_week_plan_preview_state`, `render_template`, `strip`, `get`, `isoformat`, `bool`

### `week_plan_export()` [公开]
- 位置：第 167-226 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（21 个）：`bp.get`, `time.time`, `_get_int_arg`, `strip`, `normalize_version_or_latest`, `svc.get_week_plan_rows`, `int`, `data.get`, `build_xlsx_bytes`, `log_excel_export`, `send_file`, `get`, `flash`, `redirect`, `exception`

### `simulate_schedule()` [公开]
- 位置：第 230-275 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`bp.post`, `getlist`, `_parse_optional_checkbox_flag`, `_strict_mode_enabled`, `get`, `flash`, `redirect`, `sch_svc.run_schedule`, `int`, `build_summary_display_state`, `str`, `_flash_simulate_completion`, `_flash_simulate_summary`, `isoformat`, `url_for`

## web/routes/navigation_utils.py（Route 层）

### `_warn_invalid_next_url_once()` [私有]
- 位置：第 11-24 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_safe_next_url_core()` [私有]
- 位置：第 27-56 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_safe_next_url()` [私有]
- 位置：第 59-60 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_same_origin_absolute_to_relative()` [私有]
- 位置：第 63-87 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

## web/routes/normalizers.py（Route 层）

### `_normalize_batch_priority()` [私有]
- 位置：第 17-25 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_ready_status()` [私有]
- 位置：第 28-40 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_day_type()` [私有]
- 位置：第 43-53 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_operator_calendar_day_type()` [私有]
- 位置：第 56-60 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_yesno()` [私有]
- 位置：第 63-75 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `normalize_version_or_latest()` [公开]
- 位置：第 78-92 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（7 处）：
  - `web/routes/reports.py:42` [Route] `return normalize_version_or_latest(request.args.get("version"), latest_version=l`
  - `web/routes/reports.py:47` [Route] `return normalize_version_or_latest(request.args.get("version"), latest_version=l`
  - `web/routes/domains/scheduler/scheduler_analysis.py:53` [Route] `return normalize_version_or_latest(request.args.get("version"), latest_version=l`
  - `web/routes/domains/scheduler/scheduler_gantt.py:50` [Route] `ver = normalize_version_or_latest(request.args.get("version"), latest_version=la`
  - `web/routes/domains/scheduler/scheduler_gantt.py:84` [Route] `version = normalize_version_or_latest(request.args.get("version"), latest_versio`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:129` [Route] `ver = normalize_version_or_latest(request.args.get("version"), latest_version=la`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:176` [Route] `version = normalize_version_or_latest(request.args.get("version"), latest_versio`
- **被调用者**（3 个）：`int`, `strip`, `str`

### `_log_result_summary_warning()` [私有]
- 位置：第 95-99 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_parse_result_summary_payload_with_meta()` [私有]
- 位置：第 102-152 行
- 参数：raw_summary
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_parse_result_summary_payload()` [私有]
- 位置：第 155-163 行
- 参数：raw_summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

## web/routes/personnel_calendar_pages.py（Route 层）

### `operator_calendar_page()` [公开]
- 位置：第 15-50 行
- 参数：operator_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.get`, `OperatorService`, `op_svc.get`, `CalendarService`, `ConfigService`, `cfg_svc.get_holiday_default_efficiency_display_state`, `render_template`, `c.to_dict`, `_normalize_operator_calendar_day_type`, `_normalize_yesno`, `_day_type_zh`, `getattr`, `cal_svc.list_operator_calendar`, `r.get`, `op.to_dict`

### `operator_calendar_upsert()` [公开]
- 位置：第 54-90 行
- 参数：operator_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `OperatorService`, `op_svc.get`, `get`, `CalendarService`, `flash`, `redirect`, `cal_svc.upsert_operator_calendar`, `url_for`, `getattr`, `strip`, `str`

## web/routes/system_history.py（Route 层）

### `history_page()` [公开]
- 位置：第 16-79 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（22 个）：`bp.get`, `strip`, `parse_page_args`, `_safe_int`, `_get_schedule_history_query_service`, `q.list_versions`, `build_summary_display_state`, `paginate_rows`, `render_template`, `get`, `q.get_by_version`, `x.to_dict`, `_parse_result_summary_payload_with_meta`, `parse_state.get`, `int`

## web/routes/system_ui_mode.py（Route 层）

### `_resolve_ui_mode_next_url()` [私有]
- 位置：第 15-23 行
- 参数：raw_next, raw_referrer
- 返回类型：Name(id='str', ctx=Load())

### `_persist_ui_mode_db()` [私有]
- 位置：第 26-37 行
- 参数：svc, mode
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_persist_ui_mode_cookie()` [私有]
- 位置：第 40-53 行
- 参数：resp, mode
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_flash_ui_mode_result()` [私有]
- 位置：第 56-72 行
- 参数：mode, db_ok, cookie_ok, db_error_text, cookie_error_text
- 返回类型：Constant(value=None, kind=None)

### `ui_mode_set()` [公开]
- 位置：第 76-93 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.post`, `normalize_ui_mode`, `_resolve_ui_mode_next_url`, `_get_system_config_service`, `redirect`, `_persist_ui_mode_db`, `_persist_ui_mode_cookie`, `_flash_ui_mode_result`, `get`, `flash`

## web/routes/system_utils.py（Route 层）

### `_safe_next_url()` [私有]
- 位置：第 18-19 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_parse_dt()` [私有]
- 位置：第 22-48 行
- 参数：value, field
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_normalize_time_range()` [私有]
- 位置：第 51-85 行
- 参数：start_raw, end_raw
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_safe_int()` [私有]
- 位置：第 88-100 行
- 参数：value, field, default, min_v, max_v
- 返回类型：Name(id='int', ctx=Load())

### `_get_request_service()` [私有]
- 位置：第 106-123 行
- 参数：service_attr
- 返回类型：Name(id='Any', ctx=Load())

### `_get_system_config_service()` [私有]
- 位置：第 126-127 行
- 参数：无
- 返回类型：无注解

### `_get_schedule_history_query_service()` [私有]
- 位置：第 130-131 行
- 参数：无
- 返回类型：无注解

### `_get_system_job_state_query_service()` [私有]
- 位置：第 134-135 行
- 参数：无
- 返回类型：无注解

### `_get_operation_log_service()` [私有]
- 位置：第 138-139 行
- 参数：无
- 返回类型：无注解

### `_get_backup_manager()` [私有]
- 位置：第 151-157 行
- 参数：keep_days
- 返回类型：Name(id='BackupManager', ctx=Load())

### `_get_system_cfg_snapshot()` [私有]
- 位置：第 160-162 行
- 参数：无
- 返回类型：无注解

### `_get_job_state_map()` [私有]
- 位置：第 165-187 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_validate_backup_filename()` [私有]
- 位置：第 190-202 行
- 参数：filename
- 返回类型：Name(id='str', ctx=Load())

## web/ui_mode.py（Other 层）

### `normalize_ui_mode()` [公开]
- 位置：第 41-43 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `web/routes/system_ui_mode.py:82` [Route] `mode = normalize_ui_mode(request.form.get("mode"))`
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

### `_normalize_relative_manual_src()` [私有]
- 位置：第 77-88 行
- 参数：text
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_same_origin_absolute_manual_src()` [私有]
- 位置：第 91-114 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `normalize_manual_src()` [公开]
- 位置：第 117-119 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:78` [Route] `输入应为已经过 normalize_manual_src() 过滤的站内相对地址。`
  - `web/routes/domains/scheduler/scheduler_config.py:97` [Route] `safe_src = normalize_manual_src(raw_src)`
- **被调用者**（4 个）：`strip`, `_normalize_relative_manual_src`, `_same_origin_absolute_manual_src`, `str`

### `_resolve_manual_src()` [私有]
- 位置：第 122-136 行
- 参数：src
- 返回类型：Name(id='str', ctx=Load())

### `get_manual_url()` [公开]
- 位置：第 139-144 行
- 参数：endpoint, src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:165` [Route] `enriched["url"] = get_manual_url(endpoint=entry_endpoint, src=link_src) if entry`
- **被调用者**（5 个）：`_resolve_manual_endpoint`, `normalize_manual_src`, `safe_url_for`, `_resolve_manual_src`, `resolve_manual_id`

### `get_full_manual_section_url()` [公开]
- 位置：第 147-159 行
- 参数：endpoint, src
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:167` [Route] `get_full_manual_section_url(endpoint=entry_endpoint, src=link_src) if entry_endp`
  - `web/routes/domains/scheduler/scheduler_config.py:213` [Route] `"full_manual_section_url": get_full_manual_section_url(endpoint=raw_page, src=li`
- **被调用者**（8 个）：`_resolve_manual_endpoint`, `build_manual_for_endpoint`, `normalize_manual_src`, `safe_url_for`, `strip`, `_resolve_manual_src`, `str`, `manual.get`

### `get_help_card()` [公开]
- 位置：第 162-176 行
- 参数：endpoint, src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`_resolve_manual_endpoint`, `build_manual_for_endpoint`, `manual.get`, `strip`, `list`, `get_manual_url`, `str`, `help_card.get`

### `init_ui_mode()` [公开]
- 位置：第 179-237 行
- 参数：app, base_dir
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/bootstrap/factory.py:256` [Bootstrap] `init_ui_mode(app, base_dir)`
- **被调用者**（13 个）：`join`, `normcase`, `setdefault`, `str`, `Blueprint`, `app.register_blueprint`, `abspath`, `FileSystemLoader`, `ChoiceLoader`, `overlay`, `get`, `isdir`, `_log_startup_warning`

### `_read_ui_mode_from_db()` [私有]
- 位置：第 240-281 行
- 参数：无
- 返回类型：Name(id='_UiModeDbReadResult', ctx=Load())

### `get_ui_mode()` [公开]
- 位置：第 284-310 行
- 参数：default
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`_read_ui_mode_from_db`, `normalize_ui_mode`, `has_request_context`, `_warn_invalid_db_ui_mode_once`, `get`, `_log_warning`

### `_get_v2_env()` [私有]
- 位置：第 313-315 行
- 参数：app
- 返回类型：Name(id='Any', ctx=Load())

### `_describe_template_name()` [私有]
- 位置：第 318-324 行
- 参数：template_name_or_list
- 返回类型：Name(id='str', ctx=Load())

### `_warn_v2_render_fallback_once()` [私有]
- 位置：第 327-345 行
- 参数：app
- 返回类型：Constant(value=None, kind=None)

### `_resolve_template_source()` [私有]
- 位置：第 348-366 行
- 参数：app
- 返回类型：Name(id='str', ctx=Load())

### `safe_url_for()` [公开]
- 位置：第 369-409 行
- 参数：endpoint
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`has_request_context`, `url_for`, `_log_warning`, `getattr`, `set`, `logged.add`

### `_resolve_template_url_for()` [私有]
- 位置：第 412-420 行
- 参数：无
- 返回类型：无注解

### `render_ui_template()` [公开]
- 位置：第 423-510 行
- 参数：template_name_or_list
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（17 个）：`get_ui_mode`, `context.setdefault`, `app.update_template_context`, `_resolve_template_url_for`, `env.get_or_select_template`, `_resolve_template_source`, `template.render`, `_get_v2_env`, `setdefault`, `_warn_v2_render_fallback_once`, `context.get`, `bool`, `_log_warning`, `has_request_context`, `str`

## web/viewmodels/scheduler_analysis_labels.py（ViewModel 层）

### `objective_choice_labels()` [公开]
- 位置：第 14-15 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_analysis_vm.py:247` [ViewModel] `"objective_choice_labels": objective_choice_labels(),`
- **被调用者**（1 个）：`_objective_choice_labels`

### `objective_key_from_objective()` [公开]
- 位置：第 18-19 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/viewmodels/scheduler_analysis_vm.py:136` [ViewModel] `return objective_key_from_objective(obj)`
  - `web/viewmodels/scheduler_analysis_vm.py:140` [ViewModel] `return objective_key_from_objective(value)`
- **被调用者**（1 个）：`comparison_metric_key`

### `objective_label_for()` [公开]
- 位置：第 22-43 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（5 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:124` [Route] `latest_objective_label = objective_label_for(latest_algo.get("objective"), algo=`
  - `web/viewmodels/scheduler_analysis_vm.py:153` [ViewModel] `row["display_label"] = str(row.get("label") or "").strip() or objective_label_fo`
  - `web/viewmodels/scheduler_analysis_vm.py:224` [ViewModel] `algo_config_snapshot_objective_label = objective_label_for(`
  - `web/viewmodels/scheduler_analysis_vm.py:228` [ViewModel] `algo_objective_label = objective_label_for(`
  - `web/viewmodels/scheduler_analysis_vm.py:232` [ViewModel] `objective_key_label = objective_label_for(`
- **被调用者**（8 个）：`lower`, `objective_choice_labels`, `isinstance`, `metric_label_for`, `algo.get`, `strip`, `str`, `item.get`

## web/viewmodels/scheduler_analysis_trends.py（ViewModel 层）

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
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_analysis.py:51` [Route] `latest_version = safe_int((versions[0] or {}).get("version"), default=0) if vers`
  - `web/routes/domains/scheduler/scheduler_analysis.py:56` [Route] `return safe_int((versions[0] or {}).get("version"), default=0) or None`
- **被调用者**（4 个）：`int`, `float`, `strip`, `str`

### `build_svg_polyline()` [公开]
- 位置：第 25-62 行
- 参数：values
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`min`, `max`, `float`, `join`, `len`, `pts.append`, `int`, `round`

### `score_key()` [公开]
- 位置：第 65-74 行
- 参数：score
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`tuple`, `isinstance`, `float`, `out.append`

### `safe_load_json()` [公开]
- 位置：第 77-89 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`isinstance`, `strip`, `dict`, `json.loads`, `str`

### `metric_value()` [公开]
- 位置：第 92-96 行
- 参数：row, key
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`safe_float`, `row.get`, `isinstance`, `metrics.get`

### `build_trend_rows()` [公开]
- 位置：第 99-131 行
- 参数：raw_hist
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_analysis_vm.py:183` [ViewModel] `trend_all, trend_rows = build_trend_rows(raw_hist, extract_metrics_from_summary=`
- **被调用者**（14 个）：`sorted`, `safe_int`, `safe_load_json`, `by_ver.values`, `d.get`, `extract_metrics_from_summary`, `isinstance`, `summary.get`, `int`, `algo.get`, `len`, `hasattr`, `h.to_dict`, `x.get`

### `build_trend_charts()` [公开]
- 位置：第 134-148 行
- 参数：trend_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_analysis_vm.py:184` [ViewModel] `trend_charts = build_trend_charts(trend_rows)`
- **被调用者**（2 个）：`build_svg_polyline`, `metric_value`

### `_selected_dict()` [私有]
- 位置：第 151-155 行
- 参数：selected_item
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_selected_summary_context()` [私有]
- 位置：第 158-162 行
- 参数：selected
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_attempt_rows()` [私有]
- 位置：第 165-186 行
- 参数：algo
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_build_trace_chart()` [私有]
- 位置：第 189-207 行
- 参数：algo
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_previous_metrics()` [私有]
- 位置：第 210-215 行
- 参数：trend_all
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `build_selected_details()` [公开]
- 位置：第 218-251 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_analysis_vm.py:193` [ViewModel] `) = build_selected_details(`
- **被调用者**（7 个）：`_selected_dict`, `_selected_summary_context`, `comparison_metric_from_algo`, `_build_attempt_rows`, `_build_trace_chart`, `_previous_metrics`, `int`

### `sort_and_enrich_attempts()` [公开]
- 位置：第 254-271 行
- 参数：attempts_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_analysis_vm.py:216` [ViewModel] `attempts = sort_and_enrich_attempts(attempts_rows, selected_metrics=selected_met`
- **被调用者**（9 个）：`sorted`, `max`, `isinstance`, `safe_float`, `r.get`, `float`, `score_key`, `selected_metrics.get`, `round`

## web/viewmodels/scheduler_analysis_vm.py（ViewModel 层）

### `safe_float()` [公开]
- 位置：第 21-24 行
- 参数：v, default
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（6 处）：
  - `web/viewmodels/scheduler_analysis_trends.py:96` [ViewModel] `return safe_float(metrics.get(key), default=0.0)`
  - `web/viewmodels/scheduler_analysis_trends.py:183` [ViewModel] `"primary_value": safe_float(metrics.get(objective_key), default=0.0) if isinstan`
  - `web/viewmodels/scheduler_analysis_trends.py:201` [ViewModel] `float(safe_float(metrics.get(objective_key), default=0.0) if isinstance(metrics,`
  - `web/viewmodels/scheduler_analysis_trends.py:263` [ViewModel] `max_primary = max([safe_float(r.get("primary_value"), default=0.0) for r in atte`
  - `web/viewmodels/scheduler_analysis_trends.py:265` [ViewModel] `max_primary = max(max_primary, safe_float(selected_metrics.get(objective_key), d`
  - `web/viewmodels/scheduler_analysis_trends.py:269` [ViewModel] `v = safe_float(r.get("primary_value"), default=0.0)`
- **被调用者**（1 个）：`_safe_float`

### `extract_metrics_from_summary()` [公开]
- 位置：第 27-33 行
- 参数：summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/viewmodels/scheduler_analysis_trends.py:114` [ViewModel] `metrics = extract_metrics_from_summary(summary) or None`
  - `web/viewmodels/scheduler_analysis_trends.py:160` [ViewModel] `selected_metrics = extract_metrics_from_summary(selected_summary) if isinstance(`
- **被调用者**（3 个）：`isinstance`, `summary.get`, `algo.get`

### `_summary_metric_value()` [私有]
- 位置：第 48-57 行
- 参数：selected_summary, selected_metrics, key
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `build_extra_cards()` [公开]
- 位置：第 60-80 行
- 参数：selected_summary, selected_metrics, prev_metrics
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`_summary_metric_value`, `cards.append`, `int`

### `build_freeze_display()` [公开]
- 位置：第 83-119 行
- 参数：selected_summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`algo.get`, `bool`, `lower`, `int`, `selected_summary.get`, `freeze_window.get`, `list`, `max`, `strip`, `len`, `str`

### `_comparison_metric_from_algo()` [私有]
- 位置：第 122-136 行
- 参数：algo
- 返回类型：Name(id='str', ctx=Load())

### `_objective_key_from_algo_objective()` [私有]
- 位置：第 139-140 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_best_score_schema_display()` [私有]
- 位置：第 143-155 行
- 参数：selected_summary
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_compat_fallback_state()` [私有]
- 位置：第 158-174 行
- 参数：selected_summary
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `build_analysis_context()` [公开]
- 位置：第 177-256 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_analysis.py:112` [Route] `ctx = build_analysis_context(selected_ver=selected_ver, raw_hist=raw_hist, selec`
- **被调用者**（21 个）：`build_trend_rows`, `build_trend_charts`, `build_selected_details`, `build_extra_cards`, `build_freeze_display`, `build_summary_degradation_messages`, `build_result_state`, `build_primary_degradation`, `build_display_secondary_degradation_messages`, `sort_and_enrich_attempts`, `_best_score_schema_display`, `_compat_fallback_state`, `isinstance`, `objective_label_for`, `selected_summary.get`

## web/viewmodels/scheduler_degradation_presenter.py（ViewModel 层）

### `_safe_int()` [私有]
- 位置：第 21-25 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_degradation_label_for()` [私有]
- 位置：第 28-34 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `format_degradation_detail()` [公开]
- 位置：第 37-42 行
- 参数：label, count
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_summary_display.py:36` [ViewModel] `return format_degradation_detail(item.get("label"), item.get("count"))`
- **被调用者**（4 个）：`strip`, `max`, `_safe_int`, `str`

### `degradation_reason_key()` [公开]
- 位置：第 45-50 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_summary_display.py:64` [ViewModel] `reason_key = degradation_reason_key(code=item.get("code"), label=label, count=it`
- **被调用者**（4 个）：`strip`, `max`, `_safe_int`, `str`

### `degradation_display_key()` [公开]
- 位置：第 53-57 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_summary_display.py:65` [ViewModel] `item_display_key = degradation_display_key(`
- **被调用者**（3 个）：`degradation_reason_key`, `strip`, `str`

### `_normalize_result_state()` [私有]
- 位置：第 60-78 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_primary_degradation_message()` [私有]
- 位置：第 81-93 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_summary_degradation_events()` [私有]
- 位置：第 96-128 行
- 参数：selected_summary
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `build_summary_degradation_messages()` [公开]
- 位置：第 131-132 行
- 参数：selected_summary
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/viewmodels/scheduler_analysis_vm.py:202` [ViewModel] `summary_degradation_messages = build_summary_degradation_messages(selected_summa`
  - `web/viewmodels/scheduler_summary_display.py:174` [ViewModel] `secondary_degradation_messages = build_summary_degradation_messages(summary_dict`
- **被调用者**（1 个）：`_normalize_summary_degradation_events`

### `build_primary_degradation()` [公开]
- 位置：第 135-168 行
- 参数：selected_summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/viewmodels/scheduler_analysis_vm.py:207` [ViewModel] `primary_degradation = build_primary_degradation(`
  - `web/viewmodels/scheduler_summary_display.py:173` [ViewModel] `primary_degradation = build_primary_degradation(summary_dict, result_state=resul`
- **被调用者**（10 个）：`_normalize_summary_degradation_events`, `_normalize_result_state`, `_primary_degradation_message`, `strip`, `format_degradation_detail`, `degradation_reason_key`, `item.get`, `details.append`, `detail_keys.append`, `str`

## web/viewmodels/scheduler_summary_display.py（ViewModel 层）

### `_normalize_text_list()` [私有]
- 位置：第 14-32 行
- 参数：value
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_secondary_display_label()` [私有]
- 位置：第 35-36 行
- 参数：item
- 返回类型：Name(id='str', ctx=Load())

### `_primary_detail_keys()` [私有]
- 位置：第 39-49 行
- 参数：primary_degradation
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Index(valu

### `_normalize_secondary_display_item()` [私有]
- 位置：第 52-86 行
- 参数：item
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `build_display_secondary_degradation_messages()` [公开]
- 位置：第 89-113 行
- 参数：primary_degradation, secondary_degradation_messages
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_analysis_vm.py:212` [ViewModel] `display_summary_degradation_messages = build_display_secondary_degradation_messa`
- **被调用者**（10 个）：`set`, `_primary_detail_keys`, `list`, `_normalize_text_list`, `_normalize_secondary_display_item`, `display_item.pop`, `seen.add`, `filtered.append`, `isinstance`, `get`

### `_counts_from_summary()` [私有]
- 位置：第 116-131 行
- 参数：summary
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `derive_completion_status()` [公开]
- 位置：第 134-151 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`lower`, `_counts_from_summary`, `int`, `isinstance`, `strip`, `counts.get`, `str`

### `build_result_state()` [公开]
- 位置：第 154-161 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_analysis_vm.py:203` [ViewModel] `result_state = build_result_state(`
- **被调用者**（4 个）：`lower`, `derive_completion_status`, `strip`, `str`

### `build_summary_display_state()` [公开]
- 位置：第 164-210 行
- 参数：summary
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（8 处）：
  - `web/routes/system_history.py:26` [Route] `selected_summary_display = build_summary_display_state(None, result_status=None)`
  - `web/routes/system_history.py:42` [Route] `selected_summary_display = build_summary_display_state(`
  - `web/routes/system_history.py:59` [Route] `it["result_summary_display"] = build_summary_display_state(`
  - `web/routes/domains/scheduler/scheduler_analysis.py:124` [Route] `selected_summary_display = build_summary_display_state(`
  - `web/routes/domains/scheduler/scheduler_batches.py:108` [Route] `latest_summary_display = build_summary_display_state(`
  - `web/routes/domains/scheduler/scheduler_run.py:74` [Route] `summary_display = build_summary_display_state(`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:61` [Route] `summary_display = build_summary_display_state(`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:258` [Route] `summary_display = build_summary_display_state(`
- **被调用者**（13 个）：`build_result_state`, `str`, `build_primary_degradation`, `build_summary_degradation_messages`, `build_display_secondary_degradation_messages`, `_normalize_text_list`, `max`, `len`, `isinstance`, `summary_dict.get`, `int`, `parse_state_dict.update`, `result_state.get`

---
- 分析函数/方法数：992
- 找到调用关系：1238 处
- 跨层边界风险：27 项
