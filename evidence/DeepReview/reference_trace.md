# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ DegradationCollector.extend() 在 Service 层，但被 Repository 层调用（反向依赖）
- ⚠ DegradationCollector.extend() 在 Service 层，但被 Repository 层调用（反向依赖）
- ⚠ DegradationCollector.extend() 在 Service 层，但被 Repository 层调用（反向依赖）
- ⚠ try_load_preset_snapshot_for_baseline() 返回 Optional，但 core/services/scheduler/config/config_service.py:574 的调用者未做 None 检查
- ⚠ ConfigService.get_holiday_default_efficiency_display_state() 返回 Optional，但 web/routes/personnel_calendar_pages.py:37 的调用者未做 None 检查
- ⚠ ConfigService.get_holiday_default_efficiency_display_state() 返回 Optional，但 web/routes/domains/scheduler/scheduler_calendar_pages.py:18 的调用者未做 None 检查
- ⚠ build_primary_degradation() 返回 Optional，但 web/viewmodels/scheduler_summary_display.py:262 的调用者未做 None 检查
- ⚠ build_primary_degradation() 返回 Optional，但 web/viewmodels/scheduler_analysis_vm.py:207 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/algorithms/greedy/dispatch/batch_order.py（Algorithm 层）

### `dispatch_batch_order()` [公开]
- 位置：第 14-126 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:370` [Algorithm] `scheduled_count, failed_count = dispatch_batch_order(`
- **被调用者**（15 个）：`strip`, `errors.append`, `lower`, `scheduler._schedule_external`, `scheduler._schedule_internal`, `results.append`, `max`, `blocked_batches.add`, `str`, `accumulate_busy_hours`, `update_machine_last_state`, `batch_progress.get`, `getattr`, `exception`, `bool`

## core/algorithms/greedy/dispatch/sgs.py（Algorithm 层）

### `_parse_due_date()` [私有]
- 位置：第 24-27 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_safe_seq()` [私有]
- 位置：第 30-37 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_raise_strict_internal_hours_validation()` [私有]
- 位置：第 40-61 行
- 参数：op, batch, exc
- 返回类型：Constant(value=None, kind=None)

### `_dispatch_key()` [私有]
- 位置：第 64-96 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_unscorable_dispatch_key()` [私有]
- 位置：第 99-148 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_collect_sgs_candidates()` [私有]
- 位置：第 151-167 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_record_external_compat_counters()` [私有]
- 位置：第 170-174 行
- 参数：scheduler, collector
- 返回类型：Constant(value=None, kind=None)

### `_score_external_candidate()` [私有]
- 位置：第 177-324 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_score_internal_candidate()` [私有]
- 位置：第 327-449 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_pick_best_candidate()` [私有]
- 位置：第 452-457 行
- 参数：scored_candidates
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `dispatch_sgs()` [公开]
- 位置：第 460-656 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:343` [Algorithm] `scheduled_count, failed_count = dispatch_sgs(`
- **被调用者**（41 个）：`ops_by_batch.values`, `sorted`, `ops_by_batch.items`, `strip`, `append`, `operations.sort`, `list`, `batches.get`, `increment_counter`, `_collect_sgs_candidates`, `_pick_best_candidate`, `errors.append`, `ops_by_batch.keys`, `sum`, `float`

## core/algorithms/greedy/schedule_params.py（Algorithm 层）

### `_field_label()` [私有]
- 位置：第 32-33 行
- 参数：field
- 返回类型：Name(id='str', ctx=Load())

### `_public_field_degradation_message()` [私有]
- 位置：第 36-43 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_snapshot_attr()` [私有]
- 位置：第 58-67 行
- 参数：snapshot, key
- 返回类型：Name(id='Any', ctx=Load())

### `_require_choice()` [私有]
- 位置：第 70-77 行
- 参数：raw_value
- 返回类型：Name(id='str', ctx=Load())

### `_require_weight()` [私有]
- 位置：第 80-81 行
- 参数：raw_value, key
- 返回类型：Name(id='float', ctx=Load())

### `_require_strategy_params_dict()` [私有]
- 位置：第 84-87 行
- 参数：strategy_params
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_config_default_for()` [私有]
- 位置：第 90-93 行
- 参数：key
- 返回类型：Name(id='Any', ctx=Load())

### `_build_runtime_snapshot()` [私有]
- 位置：第 96-103 行
- 参数：config
- 返回类型：Name(id='Any', ctx=Load())

### `_validate_runtime_field()` [私有]
- 位置：第 106-117 行
- 参数：config, field
- 返回类型：Constant(value=None, kind=None)

### `_weighted_override_value()` [私有]
- 位置：第 120-150 行
- 参数：raw_value, key
- 返回类型：Name(id='float', ctx=Load())

### `_weighted_strategy_params()` [私有]
- 位置：第 153-179 行
- 参数：source
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_require_yes_no()` [私有]
- 位置：第 182-187 行
- 参数：raw_value
- 返回类型：Name(id='str', ctx=Load())

### `resolve_schedule_params()` [公开]
- 位置：第 190-350 行
- 参数：无
- 返回类型：Name(id='ScheduleParams', ctx=Load())
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:145` [Algorithm] `params = resolve_schedule_params(`
- **被调用者**（34 个）：`set`, `parse_date`, `_require_choice`, `DispatchRule`, `ScheduleParams`, `_runtime_snapshot`, `_snapshot_attr`, `_record_snapshot_degradations`, `datetime.now`, `parse_datetime`, `strip`, `SortStrategy`, `dict`, `_snapshot_value`, `_require_yes_no`

## core/models/scheduler_degradation_messages.py（Model 层）

### `public_degradation_event_message()` [公开]
- 位置：第 56-58 行
- 参数：code
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（5 处）：
  - `web/viewmodels/scheduler_degradation_presenter.py:44` [ViewModel] `return public_degradation_event_message(code) if code else ""`
  - `web/viewmodels/scheduler_summary_display.py:76` [ViewModel] `if message == public_degradation_event_message(item.get("code")):`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:202` [Service] `message=public_degradation_event_message(code),`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:220` [Service] `message=public_degradation_event_message(code),`
  - `core/algorithms/greedy/schedule_params.py:37` [Algorithm] `message = public_degradation_event_message(code)`
- **被调用者**（3 个）：`strip`, `_PUBLIC_EVENT_MESSAGES.get`, `str`

### `is_public_freeze_degradation_message()` [公开]
- 位置：第 61-65 行
- 参数：message
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `web/viewmodels/scheduler_degradation_presenter.py:42` [ViewModel] `if code == "freeze_window_degraded" and is_public_freeze_degradation_message(nor`
  - `web/viewmodels/scheduler_summary_display.py:74` [ViewModel] `if not is_public_freeze_degradation_message(message):`
- **被调用者**（2 个）：`strip`, `str`

### `public_summary_warning_messages()` [公开]
- 位置：第 68-86 行
- 参数：value
- 返回类型：Subscript(value=Name(id='list', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_summary_display.py:271` [ViewModel] `public_warning_messages = public_summary_warning_messages(summary_dict.get("warn`
- **被调用者**（7 个）：`set`, `isinstance`, `strip`, `seen.add`, `out.append`, `list`, `str`

### `public_summary_merge_error_code()` [公开]
- 位置：第 89-95 行
- 参数：value
- 返回类型：BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Con
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_summary_display.py:204` [ViewModel] `"summary_merge_error": public_summary_merge_error_code(warning_pipeline.get("sum`
- **被调用者**（2 个）：`strip`, `str`

### `_event_value()` [私有]
- 位置：第 98-101 行
- 参数：event, key
- 返回类型：Name(id='Any', ctx=Load())

### `public_degradation_events()` [公开]
- 位置：第 104-126 行
- 参数：events
- 返回类型：Subscript(value=Name(id='list', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/bootstrap/plugins.py:46` [Bootstrap] `base["degradation_events"] = public_degradation_events(merged.to_list())`
  - `core/services/scheduler/resource_dispatch_support.py:155` [Service] `"degradation_events": public_degradation_events(collector.to_list()),`
  - `core/services/scheduler/gantt_contract.py:70` [Service] `"degradation_events": public_degradation_events(self.degradation_events or []),`
- **被调用者**（8 个）：`list`, `strip`, `out.append`, `max`, `public_degradation_event_message`, `str`, `int`, `_event_value`

## core/services/common/degradation.py（Service 层）

### `DegradationCollector.__init__()` [私有]
- 位置：第 49-53 行
- 参数：events
- 返回类型：无注解

### `DegradationCollector.__bool__()` [私有]
- 位置：第 55-56 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `DegradationCollector.__len__()` [私有]
- 位置：第 58-59 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())

### `DegradationCollector.add()` [公开]
- 位置：第 61-108 行
- 参数：event
- 返回类型：Name(id='DegradationEvent', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/gantt_service.py:282` [Service] `degradation_collector.add(`
- **被调用者**（8 个）：`get`, `DegradationEvent`, `len`, `append`, `ValueError`, `str`, `max`, `int`

### `DegradationCollector.extend()` [公开]
- 位置：第 110-116 行
- 参数：events
- 返回类型：Constant(value=None, kind=None)
- **调用者**（46 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:42` [Route] `normalized.extend(str(item).strip() for item in (hidden_warnings or []) if str(i`
  - `web/bootstrap/plugins.py:44` [Bootstrap] `merged.extend(collector.to_list())`
  - `web/bootstrap/launcher.py:721` [Bootstrap] `paths.extend(`
  - `web/viewmodels/page_manuals_common.py:204` [ViewModel] `lines.extend([f"### {section['title']}", "", section["body_md"], ""])`
  - `web/viewmodels/page_manuals_common.py:206` [ViewModel] `lines.extend(["## 相关模块说明", ""])`
  - `web/viewmodels/page_manuals_common.py:208` [ViewModel] `lines.extend([f"### {item['title']}", "", item.get("summary") or "", ""])`
  - `web/viewmodels/page_manuals_common.py:210` [ViewModel] `lines.extend([f"#### {section['title']}", "", section["body_md"], ""])`
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
  - `core/services/scheduler/config/config_service.py:1364` [Service] `plan.updates.extend(`
  - `core/services/scheduler/config/config_service.py:1386` [Service] `plan.updates.extend(`
  - `core/services/scheduler/config/config_service.py:1435` [Service] `plan.updates.extend(`
  - `core/services/scheduler/config/config_service.py:1545` [Service] `keys.extend([self.ACTIVE_PRESET_KEY, self.ACTIVE_PRESET_REASON_KEY, self.ACTIVE_`
  - `core/services/scheduler/config/config_service.py:1664` [Service] `updates.extend(self._active_preset_updates(self.BUILTIN_PRESET_DEFAULT))`
  - `core/services/scheduler/run/schedule_orchestrator.py:205` [Service] `summary_warnings.extend(algo_warnings)`
  - `core/services/scheduler/run/schedule_input_builder.py:137` [Service] `merge_event_collector.extend(lookup.events)`
  - `core/services/scheduler/run/schedule_input_builder.py:138` [Service] `collector.extend(lookup.events)`
  - `core/services/scheduler/run/schedule_input_builder.py:158` [Service] `collector.extend(merge_event_collector.to_list()[merge_event_count_before:])`
  - `core/services/scheduler/run/schedule_input_collector.py:123` [Service] `operations.extend(list(svc.op_repo.list_by_batch(batch_id) or []))`
  - `core/services/scheduler/run/schedule_input_runtime_support.py:74` [Service] `algo_warnings.extend(list(pool_warnings or []))`
  - `core/services/process/route_parser.py:239` [Service] `errors.extend(_strict_supplier_issue_messages(issue_messages, op_type_name=op_ty`
  - `core/services/process/route_parser.py:244` [Service] `warnings.extend([msg for msg in issue_messages if msg])`
  - `core/services/process/unit_excel/parser.py:158` [Service] `operator_names.extend(self._extract_names(ln))`
  - `core/services/process/unit_excel/parser.py:165` [Service] `operator_names.extend(self._extract_names(" ".join(tokens[1:])))`
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
- 位置：第 118-119 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（18 处）：
  - `web/bootstrap/plugins.py:44` [Bootstrap] `merged.extend(collector.to_list())`
  - `web/bootstrap/plugins.py:46` [Bootstrap] `base["degradation_events"] = public_degradation_events(merged.to_list())`
  - `core/services/scheduler/resource_dispatch_support.py:155` [Service] `"degradation_events": public_degradation_events(collector.to_list()),`
  - `core/services/scheduler/gantt_service.py:301` [Service] `degradation_events=degradation_events_to_dicts(degradation_collector.to_list()),`
  - `core/services/scheduler/config/config_validator.py:232` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/config/config_snapshot.py:257` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/config/config_snapshot.py:389` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/run/schedule_input_builder.py:158` [Service] `collector.extend(merge_event_collector.to_list()[merge_event_count_before:])`
  - `core/services/scheduler/run/schedule_input_builder.py:196` [Service] `merge_context_events=degradation_events_to_dicts(merge_event_collector.to_list()`
  - `core/services/scheduler/run/schedule_template_lookup.py:118` [Service] `return TemplateGroupLookupOutcome(None, None, True, collector.to_list())`
  - `core/services/scheduler/run/schedule_template_lookup.py:122` [Service] `return TemplateGroupLookupOutcome(tmpl, None, False, collector.to_list())`
  - `core/services/scheduler/run/schedule_template_lookup.py:136` [Service] `return TemplateGroupLookupOutcome(tmpl, None, True, collector.to_list())`
  - `core/services/scheduler/run/schedule_template_lookup.py:138` [Service] `return TemplateGroupLookupOutcome(tmpl, grp, False, collector.to_list())`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:363` [Service] `return {"events": degradation_events_to_dicts(collector.to_list()), "counters": `
  - `core/services/common/build_outcome.py:33` [Service] `self.events = collector.to_list()`
  - `core/services/common/build_outcome.py:62` [Service] `events=collector.to_list() if collector is not None else [],`
  - `core/services/process/unit_excel/template_builder.py:72` [Service] `"events": degradation_events_to_dicts(collector.to_list()),`
  - `core/algorithms/greedy/schedule_params.py:139` [Algorithm] `for event in collector.to_list():`
- **被调用者**（1 个）：`list`

### `DegradationCollector.to_counters()` [公开]
- 位置：第 121-125 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（19 处）：
  - `web/bootstrap/plugins.py:47` [Bootstrap] `base["degradation_counters"] = merged.to_counters()`
  - `web/bootstrap/plugins.py:175` [Bootstrap] `if int(collector.to_counters().get("plugin_bootstrap_config_reader_failed") or 0`
  - `core/services/scheduler/resource_dispatch_rows.py:151` [Service] `if not prepared_rows and collector.to_counters().get("bad_time_row_skipped", 0) `
  - `core/services/scheduler/resource_dispatch_rows.py:254` [Service] `if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/resource_dispatch_rows.py:348` [Service] `if not tasks and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/resource_dispatch_rows.py:477` [Service] `if not out_rows and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/resource_dispatch_support.py:156` [Service] `"degradation_counters": collector.to_counters(),`
  - `core/services/scheduler/resource_dispatch_support.py:213` [Service] `if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/gantt_tasks.py:261` [Service] `if not tasks and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/gantt_service.py:302` [Service] `degradation_counters=degradation_collector.to_counters(),`
  - `core/services/scheduler/gantt_week_plan.py:82` [Service] `if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:`
  - `core/services/scheduler/config/config_validator.py:233` [Service] `degradation_counters=collector.to_counters(),`
  - `core/services/scheduler/config/config_snapshot.py:260` [Service] `collector.to_counters(),`
  - `core/services/scheduler/config/config_snapshot.py:390` [Service] `degradation_counters=collector.to_counters(),`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:363` [Service] `return {"events": degradation_events_to_dicts(collector.to_list()), "counters": `
  - `core/services/common/build_outcome.py:35` [Service] `merged_counters = collector.to_counters()`
  - `core/services/process/unit_excel/template_builder.py:73` [Service] `"counters": collector.to_counters(),`
  - `core/algorithms/greedy/external_groups.py:29` [Algorithm] `counters = collector.to_counters()`
  - `core/algorithms/greedy/dispatch/sgs.py:171` [Algorithm] `counters = collector.to_counters()`
- **被调用者**（2 个）：`counters.get`, `int`

### `degradation_event_to_dict()` [公开]
- 位置：第 128-136 行
- 参数：event
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`str`, `int`

### `degradation_events_to_dicts()` [公开]
- 位置：第 139-140 行
- 参数：events
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（10 处）：
  - `core/services/scheduler/gantt_service.py:81` [Service] `degradation_events=degradation_events_to_dicts(calendar_days_outcome.events),`
  - `core/services/scheduler/gantt_service.py:301` [Service] `degradation_events=degradation_events_to_dicts(degradation_collector.to_list()),`
  - `core/services/scheduler/gantt_service.py:360` [Service] `"degradation_events": degradation_events_to_dicts(outcome.events),`
  - `core/services/scheduler/config/config_validator.py:232` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/config/config_snapshot.py:257` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/config/config_snapshot.py:389` [Service] `degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),`
  - `core/services/scheduler/run/schedule_input_builder.py:196` [Service] `merge_context_events=degradation_events_to_dicts(merge_event_collector.to_list()`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:97` [Service] `event_dicts = degradation_events_to_dicts(input_build_outcome.events)`
  - `core/services/scheduler/summary/schedule_summary_degradation.py:363` [Service] `return {"events": degradation_events_to_dicts(collector.to_list()), "counters": `
  - `core/services/process/unit_excel/template_builder.py:72` [Service] `"events": degradation_events_to_dicts(collector.to_list()),`
- **被调用者**（1 个）：`degradation_event_to_dict`

## core/services/scheduler/__init__.py（Service 层）

### `__getattr__()` [私有]
- 位置：第 28-34 行
- 参数：name
- 返回类型：无注解

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
  - `core/services/scheduler/config/config_service.py:361` [Service] `return preset_ops.builtin_presets(self)`
- **被调用者**（3 个）：`svc._default_snapshot`, `ScheduleConfigSnapshot`, `base.to_dict`

### `snapshot_close()` [公开]
- 位置：第 78-79 行
- 参数：a, b
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:365` [Service] `return preset_ops.snapshot_close(a, b)`
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
  - `core/services/scheduler/config/config_service.py:596` [Service] `"baseline_diff_fields": preset_ops.snapshot_diff_fields(current_snapshot, baseli`
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
  - `core/services/scheduler/config/config_service.py:371` [Service] `return preset_ops.get_snapshot_from_repo(self, strict_mode=bool(strict_mode))`
- **被调用者**（2 个）：`build_schedule_config_snapshot`, `bool`

### `ensure_builtin_presets()` [公开]
- 位置：第 162-185 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:368` [Service] `preset_ops.ensure_builtin_presets(self, existing_keys=existing_keys)`
- **被调用者**（8 个）：`builtin_presets`, `svc._preset_key`, `presets_to_create.append`, `transaction`, `set`, `list_all`, `json.dumps`, `snap.to_dict`

### `bootstrap_active_provenance_if_pristine()` [公开]
- 位置：第 188-212 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:307` [Service] `preset_ops.bootstrap_active_provenance_if_pristine(self)`
- **被调用者**（12 个）：`bool`, `get`, `get_snapshot_from_repo`, `svc._default_snapshot`, `getattr`, `transaction`, `set_batch`, `snapshot_close`, `safe_warning`, `svc._active_preset_updates`, `svc.get_preset_display_state`, `type`

### `list_presets()` [公开]
- 位置：第 215-217 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:976` [Service] `return preset_ops.list_presets(self)`
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

### `try_load_preset_snapshot_for_baseline()` [公开]
- 位置：第 256-271 行
- 参数：svc, name
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:574` [Service] `return preset_ops.try_load_preset_snapshot_for_baseline(self, active_text)`
- **被调用者**（7 个）：`strip`, `_missing_required_preset_fields`, `_load_preset_payload`, `str`, `preset_name.lower`, `lower`, `normalize_preset_snapshot`

### `save_preset()` [公开]
- 位置：第 274-307 行
- 参数：svc, name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:381` [Route] `saved = cfg_svc.save_preset(name)`
  - `core/services/scheduler/config/config_service.py:979` [Service] `return preset_ops.save_preset(self, name)`
- **被调用者**（17 个）：`svc._normalize_text`, `svc._is_builtin_preset`, `json.dumps`, `_preset_result`, `ValidationError`, `len`, `svc.get_snapshot`, `snap.to_dict`, `transaction`, `set`, `set_batch`, `_readonly_active_preset_state`, `svc._preset_key`, `svc._active_preset_updates`, `str`

### `delete_preset()` [公开]
- 位置：第 310-321 行
- 参数：svc, name
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:408` [Route] `cfg_svc.delete_preset(name)`
  - `core/services/scheduler/config/config_service.py:982` [Service] `preset_ops.delete_preset(self, name)`
- **被调用者**（9 个）：`svc._normalize_text`, `svc._is_builtin_preset`, `svc.get_active_preset`, `ValidationError`, `transaction`, `delete`, `svc._preset_key`, `set_batch`, `svc._active_preset_updates`

### `normalize_preset_snapshot()` [公开]
- 位置：第 324-334 行
- 参数：svc, data
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_service.py:985` [Service] `return preset_ops.normalize_preset_snapshot(self, data)`
- **被调用者**（2 个）：`svc._default_snapshot`, `normalize_preset_snapshot_dict`

### `apply_preset()` [公开]
- 位置：第 337-403 行
- 参数：svc, name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:363` [Route] `applied = cfg_svc.apply_preset(name)`
  - `core/services/scheduler/config/config_service.py:988` [Service] `return preset_ops.apply_preset(self, name)`
- **被调用者**（21 个）：`svc._normalize_text`, `_load_preset_payload`, `_missing_required_preset_fields`, `normalize_preset_snapshot`, `snapshot_payload_projection_diff_fields`, `_preset_result`, `ValidationError`, `_readonly_active_preset_state`, `join`, `transaction`, `set_batch`, `get_snapshot_from_repo`, `snapshot_diff_fields`, `str`, `items`

## core/services/scheduler/config/config_service.py（Service 层）

### `ConfigPageSaveOutcome.effective_snapshot()` [公开]
- 位置：第 47-48 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）

### `ConfigPageSaveOutcome.__getattr__()` [私有]
- 位置：第 50-51 行
- 参数：item
- 返回类型：Name(id='Any', ctx=Load())

### `ConfigPageSaveOutcome.to_dict()` [公开]
- 位置：第 53-54 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（75 处）：
  - `web/routes/material.py:26` [Route] `items = [m.to_dict() for m in material_svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/system_logs.py:57` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/system_backup.py:51` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_utils.py:172` [Route] `d = it.to_dict()`
  - `web/routes/personnel_calendar_pages.py:24` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:45` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:165` [Route] `operator=op.to_dict(),`
  - `web/routes/equipment_pages.py:221` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:234` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/system_history.py:30` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:44` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/process_parts.py:116` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:117` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:118` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:147` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:412` [Route] `result = stats.to_dict()`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:52` [Route] `selected_history = selected_history_item.to_dict() if hasattr(selected_history_i`
  - `web/routes/domains/scheduler/scheduler_batches.py:59` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batches.py:97` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/domains/scheduler/scheduler_batches.py:192` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:22` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_gantt.py:73` [Route] `version_resolution=version_resolution.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_analysis.py:17` [Route] `return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})`
  - `web/routes/domains/scheduler/scheduler_analysis.py:147` [Route] `version_resolution=version_resolution.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:196` [Route] `d = op.to_dict()`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:247` [Route] `batch=b.to_dict(),`
  - `web/viewmodels/system_logs_vm.py:29` [ViewModel] `d = it.to_dict() if hasattr(it, "to_dict") else (it if isinstance(it, dict) else`
  - `web/viewmodels/scheduler_analysis_trends.py:107` [ViewModel] `d = h.to_dict() if hasattr(h, "to_dict") else (h if isinstance(h, dict) else {})`
  - `web/viewmodels/scheduler_analysis_trends.py:153` [ViewModel] `return selected_item.to_dict() if hasattr(selected_item, "to_dict") else (select`
  - `core/services/scheduler/calendar_admin.py:306` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:373` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:378` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/schedule_service.py:301` [Service] `"summary": orchestration.summary_contract.to_dict(),`
  - `core/services/scheduler/gantt_contract.py:121` [Service] `return dto.to_dict(include_history=bool(include_history))`
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
  - `core/services/scheduler/config/config_presets.py:297` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/config/config_presets.py:361` [Service] `config_updates = [(key, str(value), None) for key, value in snap.to_dict().items`
  - `core/services/scheduler/run/schedule_optimizer.py:320` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer.py:334` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:183` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:210` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:399` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:414` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/summary/schedule_summary.py:82` [Service] `return snapshot.to_dict().get(str(key or "").strip())`
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
  - `core/services/process/route_parser.py:59` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:79` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:80` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
- **被调用者**（1 个）：`self.to_effective_snapshot_dict`

### `ConfigPageSaveOutcome.to_snapshot_dict()` [公开]
- 位置：第 56-57 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`self.to_effective_snapshot_dict`

### `ConfigPageSaveOutcome.to_effective_snapshot_dict()` [公开]
- 位置：第 59-60 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`to_dict`

### `ConfigPageSaveOutcome.raw_effective_mismatches()` [公开]
- 位置：第 62-78 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`to_dict`, `sorted`, `items`, `effective.get`, `mismatches.append`, `str`, `dict`

### `ConfigPageSaveOutcome.to_outcome_dict()` [公开]
- 位置：第 80-98 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`to_dict`, `dict`, `self.raw_effective_mismatches`, `list`, `getattr`

### `ConfigService.__init__()` [私有]
- 位置：第 192-197 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ConfigService._normalize_text()` [私有]
- 位置：第 203-204 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ConfigService._normalize_weight()` [私有]
- 位置：第 207-222 行
- 参数：value, field
- 返回类型：Name(id='float', ctx=Load())

### `ConfigService.normalize_weight()` [公开]
- 位置：第 225-226 行
- 参数：value, field
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`ConfigService._normalize_weight`

### `ConfigService._normalize_weights_triplet()` [私有]
- 位置：第 229-270 行
- 参数：priority_weight, due_weight, ready_weight
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._field_description()` [私有]
- 位置：第 272-273 行
- 参数：key
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._registered_updates()` [私有]
- 位置：第 275-279 行
- 参数：values
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._get_raw_value()` [私有]
- 位置：第 281-282 行
- 参数：config_key, default
- 返回类型：Name(id='Any', ctx=Load())

### `ConfigService._bootstrap_registered_defaults()` [私有]
- 位置：第 284-298 行
- 参数：无
- 返回类型：Name(id='set', ctx=Load())

### `ConfigService.ensure_defaults()` [公开]
- 位置：第 300-310 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/system/system_config_service.py:172` [Service] `self.ensure_defaults(backup_keep_days_default=backup_keep_days_default)`
- **被调用者**（5 个）：`self._is_pristine_store`, `self._bootstrap_registered_defaults`, `self._ensure_builtin_presets`, `preset_ops.bootstrap_active_provenance_if_pristine`, `set`

### `ConfigService._is_pristine_store()` [私有]
- 位置：第 312-313 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._ensure_defaults_if_pristine()` [私有]
- 位置：第 315-319 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._preset_key()` [私有]
- 位置：第 325-326 行
- 参数：name
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._is_builtin_preset()` [私有]
- 位置：第 329-335 行
- 参数：name
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._default_snapshot()` [私有]
- 位置：第 337-358 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService._builtin_presets()` [私有]
- 位置：第 360-361 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._snapshot_close()` [私有]
- 位置：第 364-365 行
- 参数：a, b
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._ensure_builtin_presets()` [私有]
- 位置：第 367-368 行
- 参数：existing_keys
- 返回类型：Constant(value=None, kind=None)

### `ConfigService._get_snapshot_from_repo()` [私有]
- 位置：第 370-371 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService._list_config_rows()` [私有]
- 位置：第 373-376 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._extract_repair_fields()` [私有]
- 位置：第 379-393 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._repair_notice_from_reason()` [私有]
- 位置：第 396-409 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._normalize_repair_notice()` [私有]
- 位置：第 412-430 行
- 参数：notice
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ConfigService._active_preset_meta_payload()` [私有]
- 位置：第 433-454 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._legacy_active_preset_meta_from_reason()` [私有]
- 位置：第 457-476 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._active_preset_meta_from_value()` [私有]
- 位置：第 479-505 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._active_preset_meta_parse_warning()` [私有]
- 位置：第 508-521 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ConfigService._serialize_active_preset_meta()` [私有]
- 位置：第 524-531 行
- 参数：meta
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._compat_repair_notice()` [私有]
- 位置：第 534-549 行
- 参数：repair_notices
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._reason_in()` [私有]
- 位置：第 552-553 行
- 参数：reason
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._builtin_preset_names()` [私有]
- 位置：第 555-560 行
- 参数：无
- 返回类型：Subscript(value=Name(id='set', ctx=Load()), slice=Index(valu

### `ConfigService._row_config_text()` [私有]
- 位置：第 563-565 行
- 参数：row
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ConfigService._config_page_values_equal()` [私有]
- 位置：第 568-571 行
- 参数：left, right
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._try_load_preset_baseline_snapshot()` [私有]
- 位置：第 573-574 行
- 参数：active_text
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._active_preset_baseline_probe_state()` [私有]
- 位置：第 576-597 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._resolve_current_config_baseline()` [私有]
- 位置：第 599-634 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._current_config_missing_provenance_descriptor()` [私有]
- 位置：第 637-648 行
- 参数：baseline_label
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._current_config_manual_reason()` [私有]
- 位置：第 651-660 行
- 参数：reason
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._resolve_current_config_descriptor()` [私有]
- 位置：第 662-715 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._collect_preset_rows()` [私有]
- 位置：第 717-727 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._build_preset_entries()` [私有]
- 位置：第 729-752 行
- 参数：preset_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._active_preset_display_state_from_rows()` [私有]
- 位置：第 754-770 行
- 参数：by_key
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._active_preset_provenance_state()` [私有]
- 位置：第 773-802 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._build_current_config_state()` [私有]
- 位置：第 804-861 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService.get_active_preset()` [公开]
- 位置：第 863-866 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/config/config_presets.py:317` [Service] `active = svc.get_active_preset()`
- **被调用者**（3 个）：`get_value`, `strip`, `str`

### `ConfigService.get_active_preset_reason()` [公开]
- 位置：第 868-871 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`get_value`, `strip`, `str`

### `ConfigService.get_active_preset_meta()` [公开]
- 位置：第 873-875 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`get_value`, `self._active_preset_meta_from_value`, `self.get_active_preset_reason`

### `ConfigService.get_preset_display_state()` [公开]
- 位置：第 877-924 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（5 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:78` [Route] `preset_display_state = cfg_svc.get_preset_display_state(readonly=True, current_s`
  - `web/routes/domains/scheduler/scheduler_config.py:314` [Route] `preset_display_state = cfg_svc.get_preset_display_state(readonly=True, current_s`
  - `core/services/scheduler/config/config_presets.py:189` [Service] `if bool((svc.get_preset_display_state(readonly=True) or {}).get("can_preserve_ba`
  - `core/services/scheduler/config/config_presets.py:216` [Service] `state = svc.get_preset_display_state(readonly=True)`
  - `core/services/scheduler/config/config_presets.py:221` [Service] `state = svc.get_preset_display_state(readonly=True)`
- **被调用者**（14 个）：`self._list_config_rows`, `self._collect_preset_rows`, `self._active_preset_display_state_from_rows`, `self._active_preset_baseline_probe_state`, `bool`, `list`, `strip`, `self._build_current_config_state`, `self._get_snapshot_from_repo`, `baseline_probe_state.get`, `self._build_preset_entries`, `str`, `preset_state.get`, `self._reason_in`

### `ConfigService._active_preset_update()` [私有]
- 位置：第 926-932 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._active_preset_reason_update()` [私有]
- 位置：第 934-940 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._active_preset_meta_update()` [私有]
- 位置：第 942-947 行
- 参数：meta
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._active_preset_updates()` [私有]
- 位置：第 949-963 行
- 参数：name, reason
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._set_active_preset()` [私有]
- 位置：第 965-967 行
- 参数：name
- 返回类型：Constant(value=None, kind=None)

### `ConfigService.mark_active_preset_custom()` [公开]
- 位置：第 969-973 行
- 参数：reason
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:360` [Route] `cfg_svc.mark_active_preset_custom()`
- **被调用者**（1 个）：`self._set_active_preset`

### `ConfigService.list_presets()` [公开]
- 位置：第 975-976 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`preset_ops.list_presets`

### `ConfigService.save_preset()` [公开]
- 位置：第 978-979 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:381` [Route] `saved = cfg_svc.save_preset(name)`
- **被调用者**（1 个）：`preset_ops.save_preset`

### `ConfigService.delete_preset()` [公开]
- 位置：第 981-982 行
- 参数：name
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:408` [Route] `cfg_svc.delete_preset(name)`
- **被调用者**（1 个）：`preset_ops.delete_preset`

### `ConfigService._normalize_preset_snapshot()` [私有]
- 位置：第 984-985 行
- 参数：data
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService.apply_preset()` [公开]
- 位置：第 987-988 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:363` [Route] `applied = cfg_svc.apply_preset(name)`
- **被调用者**（1 个）：`preset_ops.apply_preset`

### `ConfigService.get()` [公开]
- 位置：第 990-991 行
- 参数：config_key
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`get_value`, `str`

### `ConfigService._get_registered_field_value()` [私有]
- 位置：第 993-1006 行
- 参数：key
- 返回类型：Name(id='Any', ctx=Load())

### `ConfigService.get_holiday_default_efficiency()` [公开]
- 位置：第 1008-1015 行
- 参数：无
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（3 处）：
  - `web/routes/personnel_excel_operator_calendar.py:130` [Route] `return float(cfg_svc.get_holiday_default_efficiency()), None`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:118` [Route] `return float(cfg_svc.get_holiday_default_efficiency()), None`
  - `core/services/scheduler/calendar_admin.py:46` [Service] `return float(cfg_svc.get_holiday_default_efficiency(strict_mode=True))`
- **被调用者**（3 个）：`float`, `self._get_registered_field_value`, `bool`

### `ConfigService.get_holiday_default_efficiency_display_state()` [公开]
- 位置：第 1017-1032 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（2 处）：
  - `web/routes/personnel_calendar_pages.py:37` [Route] `hde, hde_degraded, hde_warning = cfg_svc.get_holiday_default_efficiency_display_`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:18` [Route] `hde, hde_degraded, hde_warning = cfg_svc.get_holiday_default_efficiency_display_`
- **被调用者**（9 个）：`self.get_snapshot`, `float`, `any`, `safe_warning`, `format`, `isinstance`, `strip`, `str`, `get`

### `ConfigService.get_available_strategies()` [公开]
- 位置：第 1037-1039 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:68` [Route] `strategies = cfg_svc.get_available_strategies()`
  - `web/routes/domains/scheduler/scheduler_config.py:303` [Route] `strategies = cfg_svc.get_available_strategies()`
- **被调用者**（3 个）：`choice_label_map_for`, `labels.get`, `choices_for`

### `ConfigService.get_snapshot()` [公开]
- 位置：第 1041-1044 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（7 处）：
  - `web/routes/system_utils.py:162` [Route] `return svc.get_snapshot(backup_keep_days_default=int(current_app.config.get("BAC`
  - `web/routes/domains/scheduler/scheduler_batches.py:67` [Route] `cfg = cfg_svc.get_snapshot()`
  - `web/routes/domains/scheduler/scheduler_config.py:302` [Route] `cfg = cfg_svc.get_snapshot(strict_mode=False)`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:231` [Route] `prefer_primary_skill = services.config_service.get_snapshot().prefer_primary_ski`
  - `core/services/scheduler/schedule_service.py:38` [Service] `return cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`
  - `core/services/scheduler/config/config_presets.py:284` [Service] `snap = svc.get_snapshot(strict_mode=True)`
  - `core/services/system/system_maintenance_service.py:92` [Service] `cfg = cfg_svc.get_snapshot(backup_keep_days_default=int(backup_keep_days_default`
- **被调用者**（3 个）：`self._get_snapshot_from_repo`, `bool`, `self._ensure_defaults_if_pristine`

### `ConfigService.get_page_metadata()` [公开]
- 位置：第 1047-1048 行
- 参数：keys
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`page_metadata_for`

### `ConfigService.get_field_label()` [公开]
- 位置：第 1051-1052 行
- 参数：key
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`field_label_for`

### `ConfigService.get_choice_labels()` [公开]
- 位置：第 1055-1056 行
- 参数：key
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`choice_label_map_for`

### `ConfigService._config_page_value()` [私有]
- 位置：第 1062-1068 行
- 参数：form_values, key
- 返回类型：Name(id='Any', ctx=Load())

### `ConfigService._config_page_submitted_fields()` [私有]
- 位置：第 1071-1089 行
- 参数：form_values
- 返回类型：Subscript(value=Name(id='set', ctx=Load()), slice=Index(valu

### `ConfigService._normalize_config_page_weights()` [私有]
- 位置：第 1091-1133 行
- 参数：priority_raw, due_raw, current_snapshot
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._normalize_config_page_payload()` [私有]
- 位置：第 1135-1164 行
- 参数：form_values
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService._config_page_write_values()` [私有]
- 位置：第 1166-1176 行
- 参数：snapshot
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_materialized_write_values()` [私有]
- 位置：第 1179-1191 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_visible_changed_fields()` [私有]
- 位置：第 1193-1204 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._snapshot_degraded_fields()` [私有]
- 位置：第 1207-1218 行
- 参数：snapshot
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._config_page_visible_repair_fields()` [私有]
- 位置：第 1221-1248 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._config_page_hidden_repair_values()` [私有]
- 位置：第 1251-1263 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_hidden_repair_reason()` [私有]
- 位置：第 1266-1280 行
- 参数：hidden_repaired_fields
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._config_page_visible_repair_notice()` [私有]
- 位置：第 1283-1288 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_hidden_repair_notice()` [私有]
- 位置：第 1291-1296 行
- 参数：hidden_repaired_fields
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_blocked_hidden_repair_notice()` [私有]
- 位置：第 1299-1310 行
- 参数：blocked_hidden_fields
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_current_provenance_state()` [私有]
- 位置：第 1312-1326 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ConfigService._config_page_notices()` [私有]
- 位置：第 1329-1334 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ConfigService._config_page_initial_write_plan()` [私有]
- 位置：第 1336-1355 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._config_page_apply_visible_change_plan()` [私有]
- 位置：第 1357-1375 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ConfigService._config_page_apply_visible_repair_plan()` [私有]
- 位置：第 1377-1397 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ConfigService._config_page_apply_hidden_repair_plan()` [私有]
- 位置：第 1399-1443 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ConfigService._config_page_blocked_hidden_write_plan()` [私有]
- 位置：第 1445-1465 行
- 参数：无
- 返回类型：Name(id='_ConfigPageWritePlan', ctx=Load())

### `ConfigService._config_page_build_write_plan()` [私有]
- 位置：第 1467-1529 行
- 参数：无
- 返回类型：Name(id='_ConfigPageWritePlan', ctx=Load())

### `ConfigService._config_page_save_status()` [私有]
- 位置：第 1532-1539 行
- 参数：plan
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._config_page_raw_persisted_state()` [私有]
- 位置：第 1541-1558 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService.save_page_config()` [公开]
- 位置：第 1560-1629 行
- 参数：form_values
- 返回类型：Name(id='ConfigPageSaveOutcome', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:457` [Route] `outcome = cfg_svc.save_page_config(payload)`
- **被调用者**（26 个）：`self._ensure_defaults_if_pristine`, `get_value`, `self._active_preset_meta_parse_warning`, `self.get_snapshot`, `self._config_page_current_provenance_state`, `provenance_state.get`, `self._config_page_submitted_fields`, `self._normalize_config_page_payload`, `self._config_page_write_values`, `self._config_page_visible_changed_fields`, `self._config_page_visible_repair_fields`, `self._config_page_hidden_repair_values`, `list`, `write_values.update`, `self._config_page_materialized_write_values`

### `ConfigService.set_strategy()` [公开]
- 位置：第 1631-1644 行
- 参数：sort_strategy
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_weights()` [公开]
- 位置：第 1646-1660 行
- 参数：priority_weight, due_weight, ready_weight, require_sum_1
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`self._normalize_weights_triplet`, `transaction`, `set`, `set_batch`, `str`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.restore_default()` [公开]
- 位置：第 1662-1666 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config.py:468` [Route] `cfg_svc.restore_default()`
- **被调用者**（6 个）：`self._registered_updates`, `updates.extend`, `default_snapshot_values`, `self._active_preset_updates`, `transaction`, `set_batch`

### `ConfigService.set_dispatch()` [公开]
- 位置：第 1668-1691 行
- 参数：dispatch_mode, dispatch_rule
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_auto_assign_enabled()` [公开]
- 位置：第 1693-1706 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_ortools()` [公开]
- 位置：第 1708-1730 行
- 参数：enabled, time_limit_seconds
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`str`, `int`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_prefer_primary_skill()` [公开]
- 位置：第 1732-1745 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_enforce_ready_default()` [公开]
- 位置：第 1747-1760 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_holiday_default_efficiency()` [公开]
- 位置：第 1762-1781 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`float`, `ValidationError`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `strip`, `str`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_algo_mode()` [公开]
- 位置：第 1783-1796 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_time_budget_seconds()` [公开]
- 位置：第 1798-1813 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`int`, `ValidationError`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `strip`, `str`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_objective()` [公开]
- 位置：第 1815-1828 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`str`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

### `ConfigService.set_freeze_window()` [公开]
- 位置：第 1830-1852 行
- 参数：enabled, days
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`str`, `int`, `coerce_config_field`, `transaction`, `set`, `set_batch`, `self._active_preset_updates`, `self._field_description`

## core/services/scheduler/gantt_contract.py（Service 层）

### `_public_critical_chain()` [私有]
- 位置：第 9-19 行
- 参数：chain
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_public_history()` [私有]
- 位置：第 22-27 行
- 参数：history
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `GanttContractDTO.to_dict()` [公开]
- 位置：第 58-79 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（84 处）：
  - `web/routes/material.py:26` [Route] `items = [m.to_dict() for m in material_svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/system_logs.py:57` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/system_backup.py:51` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_utils.py:172` [Route] `d = it.to_dict()`
  - `web/routes/personnel_calendar_pages.py:24` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:45` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:165` [Route] `operator=op.to_dict(),`
  - `web/routes/equipment_pages.py:221` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:234` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/system_history.py:30` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:44` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/process_parts.py:116` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:117` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:118` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:147` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:412` [Route] `result = stats.to_dict()`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:52` [Route] `selected_history = selected_history_item.to_dict() if hasattr(selected_history_i`
  - `web/routes/domains/scheduler/scheduler_batches.py:59` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batches.py:97` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/domains/scheduler/scheduler_batches.py:192` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:22` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_gantt.py:73` [Route] `version_resolution=version_resolution.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_analysis.py:17` [Route] `return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})`
  - `web/routes/domains/scheduler/scheduler_analysis.py:147` [Route] `version_resolution=version_resolution.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:196` [Route] `d = op.to_dict()`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:247` [Route] `batch=b.to_dict(),`
  - `web/viewmodels/system_logs_vm.py:29` [ViewModel] `d = it.to_dict() if hasattr(it, "to_dict") else (it if isinstance(it, dict) else`
  - `web/viewmodels/scheduler_analysis_trends.py:107` [ViewModel] `d = h.to_dict() if hasattr(h, "to_dict") else (h if isinstance(h, dict) else {})`
  - `web/viewmodels/scheduler_analysis_trends.py:153` [ViewModel] `return selected_item.to_dict() if hasattr(selected_item, "to_dict") else (select`
  - `core/services/scheduler/calendar_admin.py:306` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:373` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:378` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/schedule_service.py:301` [Service] `"summary": orchestration.summary_contract.to_dict(),`
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
  - `core/services/scheduler/config/config_presets.py:297` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/config/config_presets.py:361` [Service] `config_updates = [(key, str(value), None) for key, value in snap.to_dict().items`
  - `core/services/scheduler/config/config_service.py:60` [Service] `return self.snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:63` [Service] `effective = self.snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:83` [Service] `"effective_snapshot": self.snapshot.to_dict(),`
  - `core/services/scheduler/config/config_service.py:84` [Service] `"normalized_snapshot": self.normalized_snapshot.to_dict() if self.normalized_sna`
  - `core/services/scheduler/config/config_service.py:1142` [Service] `payload = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1172` [Service] `values = snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1185` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1199` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1227` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1258` [Service] `values = normalized_snapshot.to_dict()`
  - `core/services/scheduler/run/schedule_optimizer.py:320` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer.py:334` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:183` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:210` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:399` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:414` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/summary/schedule_summary.py:82` [Service] `return snapshot.to_dict().get(str(key or "").strip())`
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
  - `core/services/process/route_parser.py:59` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:79` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:80` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
- **被调用者**（8 个）：`int`, `str`, `list`, `_public_critical_chain`, `bool`, `public_degradation_events`, `dict`, `_public_history`

### `build_gantt_contract()` [公开]
- 位置：第 82-121 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/gantt_service.py:71` [Service] `out = build_gantt_contract(`
  - `core/services/scheduler/gantt_service.py:291` [Service] `data = build_gantt_contract(`
- **被调用者**（9 个）：`GanttContractDTO`, `dto.to_dict`, `int`, `str`, `len`, `list`, `dict`, `bool`, `isinstance`

## core/services/scheduler/gantt_service.py（Service 层）

### `GanttService.__init__()` [私有]
- 位置：第 34-39 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `GanttService.get_latest_version_or_1()` [公开]
- 位置：第 41-43 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`int`, `get_latest_version`

### `GanttService.resolve_version()` [公开]
- 位置：第 45-51 行
- 参数：value
- 返回类型：Name(id='VersionResolution', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_gantt.py:48` [Route] `version_resolution = svc.resolve_version(request.args.get("version"))`
- **被调用者**（4 个）：`int`, `resolve_version_or_latest`, `get_latest_version`, `get_by_version`

### `GanttService._empty_gantt_contract()` [私有]
- 位置：第 53-90 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `GanttService.resolve_week_range()` [公开]
- 位置：第 92-99 行
- 参数：week_start, offset_weeks, start_date, end_date
- 返回类型：Name(id='WeekRange', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_week_plan.py:129` [Route] `wr = svc.resolve_week_range(week_start=week_start, offset_weeks=offset, start_da`
  - `web/routes/domains/scheduler/scheduler_gantt.py:59` [Route] `wr = svc.resolve_week_range(week_start=week_start, offset_weeks=offset, start_da`

### `GanttService._log_overdue_marker_degraded()` [私有]
- 位置：第 101-109 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `GanttService._log_overdue_marker_partial()` [私有]
- 位置：第 111-119 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `GanttService._overdue_batch_ids_from_history()` [私有]
- 位置：第 121-143 行
- 参数：version
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `GanttService._critical_chain_cache_key()` [私有]
- 位置：第 145-162 行
- 参数：version
- 返回类型：Name(id='tuple', ctx=Load())

### `GanttService._normalize_critical_chain_result()` [私有]
- 位置：第 165-186 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `GanttService._critical_chain_cacheable()` [私有]
- 位置：第 189-190 行
- 参数：result
- 返回类型：Name(id='bool', ctx=Load())

### `GanttService._get_critical_chain()` [私有]
- 位置：第 192-228 行
- 参数：version
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `GanttService.get_gantt_tasks()` [公开]
- 位置：第 230-313 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_gantt.py:95` [Route] `data: Dict[str, Any] = svc.get_gantt_tasks(`
- **被调用者**（27 个）：`self.resolve_week_range`, `self.resolve_version`, `require_selected_version`, `build_calendar_days`, `list_overlapping_with_details`, `self._overdue_batch_ids_from_history`, `set`, `build_tasks`, `DegradationCollector`, `degradation_collector.extend`, `self._get_critical_chain`, `build_gantt_contract`, `strip`, `ValidationError`, `self._empty_gantt_contract`

### `GanttService.get_week_plan_rows()` [公开]
- 位置：第 315-364 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_week_plan.py:132` [Route] `data = svc.get_week_plan_rows(`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:193` [Route] `data = svc.get_week_plan_rows(`
- **被调用者**（9 个）：`self.resolve_week_range`, `self.resolve_version`, `require_selected_version`, `list_overlapping_with_details`, `build_week_plan_rows`, `get_by_version`, `isoformat`, `degradation_events_to_dicts`, `hist.to_dict`

## core/services/scheduler/resource_dispatch_service.py（Service 层）

### `ResourceDispatchService.__init__()` [私有]
- 位置：第 28-36 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ResourceDispatchService._text()` [私有]
- 位置：第 39-43 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ResourceDispatchService._normalize_scope_type()` [私有]
- 位置：第 45-49 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `ResourceDispatchService._normalize_team_axis()` [私有]
- 位置：第 51-55 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `ResourceDispatchService._resolve_scope_id()` [私有]
- 位置：第 57-73 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ResourceDispatchService._period_preset_label()` [私有]
- 位置：第 75-76 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `ResourceDispatchService._scope_type_label()` [私有]
- 位置：第 78-79 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `ResourceDispatchService._team_axis_label()` [私有]
- 位置：第 81-82 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `ResourceDispatchService._latest_version()` [私有]
- 位置：第 84-85 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())

### `ResourceDispatchService._list_versions()` [私有]
- 位置：第 87-88 行
- 参数：limit
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ResourceDispatchService._normalize_strict_positive_version()` [私有]
- 位置：第 90-104 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ResourceDispatchService._resolve_version()` [私有]
- 位置：第 106-112 行
- 参数：value
- 返回类型：Name(id='VersionResolution', ctx=Load())

### `ResourceDispatchService._scope_record()` [私有]
- 位置：第 114-119 行
- 参数：scope_type, scope_id
- 返回类型：无注解

### `ResourceDispatchService._scope_name()` [私有]
- 位置：第 121-126 行
- 参数：scope_type, scope_id
- 返回类型：Name(id='str', ctx=Load())

### `ResourceDispatchService._build_scope_options()` [私有]
- 位置：第 128-158 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ResourceDispatchService._log_overdue_marker_degraded()` [私有]
- 位置：第 160-168 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ResourceDispatchService._log_overdue_marker_partial()` [私有]
- 位置：第 170-178 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `ResourceDispatchService._load_overdue_meta()` [私有]
- 位置：第 180-201 行
- 参数：version
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `ResourceDispatchService.build_page_context()` [公开]
- 位置：第 203-266 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:181` [Route] `context = svc.build_page_context(**_request_kwargs())`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:192` [Route] `context = svc.build_page_context()`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:199` [Route] `context = svc.build_page_context()`
- **被调用者**（19 个）：`self._normalize_scope_type`, `self._normalize_team_axis`, `self._list_versions`, `resolve_dispatch_range`, `self._resolve_scope_id`, `self._build_scope_options`, `self._resolve_version`, `int`, `self._latest_version`, `self._scope_name`, `require_selected_version`, `bool`, `self._scope_type_label`, `strip`, `self._team_axis_label`

### `ResourceDispatchService.get_dispatch_payload()` [公开]
- 位置：第 268-368 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:218` [Route] `payload = _svc().get_dispatch_payload(**_request_kwargs())`
- **被调用者**（22 个）：`self._normalize_scope_type`, `self._normalize_team_axis`, `self._latest_version`, `self._resolve_version`, `require_selected_version`, `self._resolve_scope_id`, `self._scope_name`, `resolve_dispatch_range`, `self._load_overdue_meta`, `set`, `list_dispatch_rows_with_resource_context`, `build_dispatch_filters`, `bool`, `str`, `build_empty_dispatch_message`

### `ResourceDispatchService.build_export()` [公开]
- 位置：第 370-387 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:232` [Route] `buf, filename, payload = svc.build_export(**_request_kwargs())`
- **被调用者**（5 个）：`self.get_dispatch_payload`, `build_resource_dispatch_workbook`, `filters.get`, `payload.get`, `BusinessError`

## core/services/scheduler/resource_dispatch_support.py（Service 层）

### `_text()` [私有]
- 位置：第 22-23 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `extract_overdue_batch_ids_with_meta()` [公开]
- 位置：第 26-87 行
- 参数：result_summary
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/resource_dispatch_service.py:192` [Service] `meta = extract_overdue_batch_ids_with_meta(hist.result_summary)`
  - `core/services/scheduler/gantt_service.py:134` [Service] `meta = extract_overdue_batch_ids_with_meta(hist.result_summary)`
- **被调用者**（9 个）：`payload.get`, `isinstance`, `set`, `overdue.get`, `json.loads`, `_text`, `seen.add`, `result.append`, `item.get`

### `extract_overdue_batch_ids()` [公开]
- 位置：第 90-97 行
- 参数：result_summary
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Index(valu
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`extract_overdue_batch_ids_with_meta`, `set`, `meta.get`, `_text`, `result.add`

### `filter_team_rows_by_axis()` [公开]
- 位置：第 100-106 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`_text`, `out.append`, `get`, `dict`

### `build_dispatch_summary()` [公开]
- 位置：第 109-158 行
- 参数：detail_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`set`, `item.get`, `seen.add`, `int`, `_text`, `len`, `round`, `bool`, `public_degradation_events`, `collector.to_counters`, `counterpart_label.startswith`, `collector.to_list`

### `count_unique_schedule_ids()` [公开]
- 位置：第 161-162 行
- 参数：rows
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`len`, `row.get`

### `build_team_cross_rows()` [公开]
- 位置：第 165-215 行
- 参数：无
- 返回类型：Subscript(value=Name(id='BuildOutcome', ctx=Load()), slice=I
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`DegradationCollector`, `set`, `out.sort`, `BuildOutcome.from_collector`, `_text`, `build_dispatch_detail_rows`, `collector.extend`, `item.get`, `seen.add`, `out.append`, `get`, `collector.to_counters`

### `build_scope_result()` [公开]
- 位置：第 218-261 行
- 参数：无
- 返回类型：Subscript(value=Name(id='BuildOutcome', ctx=Load()), slice=I
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`build_dispatch_detail_rows`, `build_dispatch_tasks`, `build_dispatch_calendar_matrix`, `DegradationCollector`, `collector.extend`, `BuildOutcome.from_collector`

### `empty_dispatch_payload()` [公开]
- 位置：第 264-308 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/resource_dispatch_service.py:288` [Service] `payload = empty_dispatch_payload(`

### `build_team_scope_payload()` [公开]
- 位置：第 311-381 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/resource_dispatch_service.py:327` [Service] `payload = build_team_scope_payload(`
- **被调用者**（10 个）：`prepare_dispatch_rows`, `build_scope_result`, `build_team_cross_rows`, `DegradationCollector`, `summary_collector.extend`, `build_dispatch_summary`, `count_unique_schedule_ids`, `len`, `filter_team_rows_by_axis`, `list`

### `build_single_scope_payload()` [公开]
- 位置：第 384-423 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/resource_dispatch_service.py:336` [Service] `payload = build_single_scope_payload(`
- **被调用者**（5 个）：`prepare_dispatch_rows`, `build_scope_result`, `DegradationCollector`, `summary_collector.extend`, `build_dispatch_summary`

### `build_dispatch_filters()` [公开]
- 位置：第 426-458 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/resource_dispatch_service.py:344` [Service] `payload["filters"] = build_dispatch_filters(`
- **被调用者**（3 个）：`strip`, `get`, `isoformat`

### `build_empty_dispatch_message()` [公开]
- 位置：第 461-479 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/resource_dispatch_service.py:360` [Service] `payload["empty_message"] = build_empty_dispatch_message(`
- **被调用者**（3 个）：`_text`, `get`, `isoformat`

## core/services/scheduler/resource_pool_builder.py（Service 层）

### `_skill_rank()` [私有]
- 位置：第 19-28 行
- 参数：v
- 返回类型：Name(id='int', ctx=Load())

### `_active_machine_ids()` [私有]
- 位置：第 31-32 行
- 参数：machines
- 返回类型：Name(id='set', ctx=Load())

### `_op_type_ids_for_ops()` [私有]
- 位置：第 35-41 行
- 参数：algo_ops
- 返回类型：Name(id='set', ctx=Load())

### `_machines_by_op_type()` [私有]
- 位置：第 44-59 行
- 参数：machines
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_active_operator_ids()` [私有]
- 位置：第 62-67 行
- 参数：svc
- 返回类型：Name(id='set', ctx=Load())

### `_build_operator_machine_maps()` [私有]
- 位置：第 70-96 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_sort_operators_by_machine()` [私有]
- 位置：第 99-105 行
- 参数：operators_by_machine
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_append_warning()` [私有]
- 位置：第 108-110 行
- 参数：warnings, message
- 返回类型：Constant(value=None, kind=None)

### `_warn_service_logger()` [私有]
- 位置：第 113-114 行
- 参数：svc, message
- 返回类型：Constant(value=None, kind=None)

### `load_machine_downtimes()` [公开]
- 位置：第 118-191 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（17 个）：`MachineDowntimeRepository`, `svc._format_dt`, `sorted`, `join`, `_append_warning`, `_warn_service_logger`, `dt_repo.list_active_after`, `int`, `list`, `strip`, `svc._normalize_datetime`, `intervals.sort`, `partial_fail_mids.append`, `len`, `intervals.append`

### `build_resource_pool()` [公开]
- 位置：第 194-258 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`to_yes_no`, `list`, `_active_machine_ids`, `_op_type_ids_for_ops`, `_machines_by_op_type`, `_active_operator_ids`, `list_simple_rows`, `_build_operator_machine_maps`, `_sort_operators_by_machine`, `warnings.append`, `_warn_service_logger`

### `extend_downtime_map_for_resource_pool()` [公开]
- 位置：第 261-334 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`to_yes_no`, `MachineDowntimeRepository`, `svc._format_dt`, `sorted`, `join`, `_append_warning`, `isinstance`, `_warn_service_logger`, `dt_repo.list_active_after`, `int`, `list`, `resource_pool.get`, `strip`, `svc._normalize_datetime`, `intervals.sort`

## core/services/scheduler/run/freeze_window.py（Service 层）

### `_init_freeze_meta()` [私有]
- 位置：第 27-37 行
- 参数：meta
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_freeze_window_days()` [私有]
- 位置：第 40-71 行
- 参数：cfg, prev_version
- 返回类型：Name(id='int', ctx=Load())

### `_record_freeze_degradation()` [私有]
- 位置：第 74-90 行
- 参数：meta, warnings, message
- 返回类型：Constant(value=None, kind=None)

### `_finalize_freeze_application_status()` [私有]
- 位置：第 93-109 行
- 参数：meta
- 返回类型：Constant(value=None, kind=None)

### `_invalid_schedule_row_sample()` [私有]
- 位置：第 112-123 行
- 参数：row
- 返回类型：Name(id='str', ctx=Load())

### `_load_schedule_map()` [私有]
- 位置：第 126-158 行
- 参数：svc
- 返回类型：Name(id='_LoadedScheduleMapOutcome', ctx=Load())

### `_max_seq_by_batch()` [私有]
- 位置：第 161-172 行
- 参数：schedule_map, op_by_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_prefix_op_ids_for_batch()` [私有]
- 位置：第 175-176 行
- 参数：operations, bid, max_seq
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_cache_seed_for_prefix()` [私有]
- 位置：第 179-193 行
- 参数：svc
- 返回类型：Name(id='int', ctx=Load())

### `_discard_seed_cache()` [私有]
- 位置：第 196-198 行
- 参数：prefix, seed_tmp
- 返回类型：Constant(value=None, kind=None)

### `_build_seed_results()` [私有]
- 位置：第 201-232 行
- 参数：frozen_op_ids
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `build_freeze_window_seed()` [公开]
- 位置：第 235-356 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（29 个）：`set`, `_init_freeze_meta`, `_freeze_window_days`, `svc._format_dt`, `sorted`, `_max_seq_by_batch`, `max_seq_by_batch.items`, `_build_seed_results`, `seed_results.sort`, `bool`, `_finalize_freeze_application_status`, `timedelta`, `int`, `list`, `_load_schedule_map`

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
- 位置：第 151-175 行
- 参数：state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_resource_pool_dict()` [私有]
- 位置：第 178-190 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_warning_pipeline_dict()` [私有]
- 位置：第 193-208 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_dict()` [私有]
- 位置：第 211-253 行
- 参数：state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_result_summary_obj()` [私有]
- 位置：第 256-302 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

## core/services/scheduler/summary/schedule_summary_degradation.py（Service 层）

### `_event_identity()` [私有]
- 位置：第 19-27 行
- 参数：event
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_dedupe_event_dicts()` [私有]
- 位置：第 30-41 行
- 参数：events
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_iter_build_outcome_values()` [私有]
- 位置：第 44-54 行
- 参数：value
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_value_flag()` [私有]
- 位置：第 57-60 行
- 参数：item, key
- 返回类型：Name(id='Any', ctx=Load())

### `_builder_merge_context_state()` [私有]
- 位置：第 63-74 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_legacy_merge_context_events()` [私有]
- 位置：第 77-82 行
- 参数：event_dicts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_input_build_state()` [私有]
- 位置：第 85-120 行
- 参数：input_build_outcome
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_meta_int()` [私有]
- 位置：第 123-127 行
- 参数：meta, key
- 返回类型：Name(id='int', ctx=Load())

### `_meta_sample()` [私有]
- 位置：第 130-145 行
- 参数：meta, key
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_metric_int()` [私有]
- 位置：第 148-154 行
- 参数：metrics, key
- 返回类型：Name(id='int', ctx=Load())

### `_metric_sample()` [私有]
- 位置：第 157-174 行
- 参数：metrics, key
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_optional_text()` [私有]
- 位置：第 177-181 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_event_count()` [私有]
- 位置：第 184-188 行
- 参数：event
- 返回类型：Name(id='int', ctx=Load())

### `_add_input_events()` [私有]
- 位置：第 191-205 行
- 参数：collector, input_state
- 返回类型：Constant(value=None, kind=None)

### `_add_existing_degradation_events()` [私有]
- 位置：第 208-223 行
- 参数：collector, raw_events
- 返回类型：Constant(value=None, kind=None)

### `_add_counted_event()` [私有]
- 位置：第 226-238 行
- 参数：collector
- 返回类型：Constant(value=None, kind=None)

### `_add_state_event()` [私有]
- 位置：第 241-253 行
- 参数：collector
- 返回类型：Constant(value=None, kind=None)

### `_summary_degradation_state()` [私有]
- 位置：第 256-363 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_partial_fail_reason()` [私有]
- 位置：第 366-371 行
- 参数：prefix, count, sample, suffix
- 返回类型：Name(id='str', ctx=Load())

### `_downtime_reason()` [私有]
- 位置：第 374-399 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_compute_downtime_degradation()` [私有]
- 位置：第 402-441 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_compute_resource_pool_degradation()` [私有]
- 位置：第 444-457 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_hard_constraints()` [私有]
- 位置：第 460-466 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

## core/services/scheduler/summary/schedule_summary_freeze.py（Service 层）

### `_freeze_window_config_state()` [私有]
- 位置：第 14-21 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_freeze_degradation_codes()` [私有]
- 位置：第 24-25 行
- 参数：meta
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_freeze_applied()` [私有]
- 位置：第 28-31 行
- 参数：meta
- 返回类型：Name(id='bool', ctx=Load())

### `_freeze_state_name()` [私有]
- 位置：第 34-39 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_freeze_application_status()` [私有]
- 位置：第 42-50 行
- 参数：meta
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_freeze_degradation_reason()` [私有]
- 位置：第 53-58 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_freeze_degradation_public_code()` [私有]
- 位置：第 61-69 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_compute_result_status()` [私有]
- 位置：第 72-81 行
- 参数：summary
- 返回类型：Name(id='str', ctx=Load())

### `_frozen_batch_ids()` [私有]
- 位置：第 84-91 行
- 参数：operations
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_extract_freeze_warnings()` [私有]
- 位置：第 94-104 行
- 参数：all_warnings
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_freeze_meta_dict()` [私有]
- 位置：第 107-142 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

## core/services/scheduler/summary/schedule_summary_types.py（Service 层）

### `FreezeState.status()` [公开]
- 位置：第 76-77 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`str`, `get`

## core/services/scheduler/version_resolution.py（Service 层）

### `VersionResolution.to_dict()` [公开]
- 位置：第 19-26 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（85 处）：
  - `web/routes/material.py:26` [Route] `items = [m.to_dict() for m in material_svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/system_logs.py:57` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:86` [Route] `supplier=s.to_dict(),`
  - `web/routes/system_backup.py:51` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_utils.py:172` [Route] `d = it.to_dict()`
  - `web/routes/personnel_calendar_pages.py:24` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:45` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:165` [Route] `operator=op.to_dict(),`
  - `web/routes/equipment_pages.py:221` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:234` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/system_history.py:30` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:44` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/process_parts.py:116` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:117` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:118` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:147` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:412` [Route] `result = stats.to_dict()`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:52` [Route] `selected_history = selected_history_item.to_dict() if hasattr(selected_history_i`
  - `web/routes/domains/scheduler/scheduler_batches.py:59` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batches.py:97` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/domains/scheduler/scheduler_batches.py:192` [Route] `**b.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:22` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/domains/scheduler/scheduler_gantt.py:73` [Route] `version_resolution=version_resolution.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_analysis.py:17` [Route] `return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})`
  - `web/routes/domains/scheduler/scheduler_analysis.py:147` [Route] `version_resolution=version_resolution.to_dict(),`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:196` [Route] `d = op.to_dict()`
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:247` [Route] `batch=b.to_dict(),`
  - `web/viewmodels/system_logs_vm.py:29` [ViewModel] `d = it.to_dict() if hasattr(it, "to_dict") else (it if isinstance(it, dict) else`
  - `web/viewmodels/scheduler_analysis_trends.py:107` [ViewModel] `d = h.to_dict() if hasattr(h, "to_dict") else (h if isinstance(h, dict) else {})`
  - `web/viewmodels/scheduler_analysis_trends.py:153` [ViewModel] `return selected_item.to_dict() if hasattr(selected_item, "to_dict") else (select`
  - `core/services/scheduler/calendar_admin.py:306` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:373` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:378` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/schedule_service.py:301` [Service] `"summary": orchestration.summary_contract.to_dict(),`
  - `core/services/scheduler/gantt_contract.py:121` [Service] `return dto.to_dict(include_history=bool(include_history))`
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
  - `core/services/scheduler/config/config_presets.py:297` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/config/config_presets.py:361` [Service] `config_updates = [(key, str(value), None) for key, value in snap.to_dict().items`
  - `core/services/scheduler/config/config_service.py:60` [Service] `return self.snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:63` [Service] `effective = self.snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:83` [Service] `"effective_snapshot": self.snapshot.to_dict(),`
  - `core/services/scheduler/config/config_service.py:84` [Service] `"normalized_snapshot": self.normalized_snapshot.to_dict() if self.normalized_sna`
  - `core/services/scheduler/config/config_service.py:1142` [Service] `payload = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1172` [Service] `values = snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1185` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1199` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1227` [Service] `current_values = current_snapshot.to_dict()`
  - `core/services/scheduler/config/config_service.py:1258` [Service] `values = normalized_snapshot.to_dict()`
  - `core/services/scheduler/run/schedule_optimizer.py:320` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer.py:334` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:183` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:210` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:399` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:414` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/summary/schedule_summary.py:82` [Service] `return snapshot.to_dict().get(str(key or "").strip())`
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
  - `core/services/process/route_parser.py:59` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:79` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:80` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
- **被调用者**（1 个）：`bool`

### `_parse_explicit_version()` [私有]
- 位置：第 29-36 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `resolve_version_or_latest()` [公开]
- 位置：第 39-85 行
- 参数：value
- 返回类型：Name(id='VersionResolution', ctx=Load())
- **调用者**（4 处）：
  - `web/routes/normalizers.py:125` [Route] `return resolve_version_or_latest(value, latest_version=latest_version, version_e`
  - `web/routes/reports.py:53` [Route] `return resolve_version_or_latest(`
  - `core/services/scheduler/resource_dispatch_service.py:108` [Service] `return resolve_version_or_latest(`
  - `core/services/scheduler/gantt_service.py:47` [Service] `return resolve_version_or_latest(`
- **被调用者**（8 个）：`int`, `_parse_explicit_version`, `VersionResolution`, `strip`, `raw_text.lower`, `bool`, `version_exists`, `str`

### `require_selected_version()` [公开]
- 位置：第 88-99 行
- 参数：resolution
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（6 处）：
  - `web/routes/reports.py:47` [Route] `return require_selected_version(resolution)`
  - `web/routes/reports.py:48` [Route] `return require_selected_version(resolution, message="暂无排产历史，无法导出报表。")`
  - `core/services/scheduler/resource_dispatch_service.py:239` [Service] `require_selected_version(version_resolution)`
  - `core/services/scheduler/resource_dispatch_service.py:298` [Service] `selected_version = require_selected_version(version_resolution)`
  - `core/services/scheduler/gantt_service.py:261` [Service] `ver = require_selected_version(resolution)`
  - `core/services/scheduler/gantt_service.py:345` [Service] `ver = require_selected_version(resolution)`
- **被调用者**（2 个）：`BusinessError`, `int`

## scripts/run_quality_gate.py（Script 层）

### `_coerce_runtime_probe_state()` [私有]
- 位置：第 58-65 行
- 参数：value
- 返回类型：Name(id='RuntimeProbeState', ctx=Load())

### `_run_command()` [私有]
- 位置：第 68-92 行
- 参数：display, args, capture_output
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_coerce_command_result()` [私有]
- 位置：第 95-106 行
- 参数：result
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_assert_command_succeeded()` [私有]
- 位置：第 109-111 行
- 参数：display, result
- 返回类型：Constant(value=None, kind=None)

### `_sha256_file()` [私有]
- 位置：第 114-122 行
- 参数：abs_path
- 返回类型：Name(id='str', ctx=Load())

### `_write_command_receipt()` [私有]
- 位置：第 125-142 行
- 参数：command
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_clear_quality_gate_receipts()` [私有]
- 位置：第 145-148 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_guard_test_abs_path()` [私有]
- 位置：第 151-152 行
- 参数：rel_path
- 返回类型：Name(id='str', ctx=Load())

### `_guard_test_exists()` [私有]
- 位置：第 155-156 行
- 参数：rel_path
- 返回类型：Name(id='bool', ctx=Load())

### `_guard_test_tracked()` [私有]
- 位置：第 159-168 行
- 参数：rel_path
- 返回类型：Name(id='bool', ctx=Load())

### `_git_rev_parse_path()` [私有]
- 位置：第 171-186 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_repo_identity()` [私有]
- 位置：第 189-193 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_assert_guard_tests_ready()` [私有]
- 位置：第 196-207 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_parse_ruff_version()` [私有]
- 位置：第 210-217 行
- 参数：text
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_assert_ruff_version()` [私有]
- 位置：第 220-227 行
- 参数：output
- 返回类型：Name(id='str', ctx=Load())

### `_parse_pyright_version()` [私有]
- 位置：第 230-234 行
- 参数：text
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_assert_pyright_version()` [私有]
- 位置：第 237-245 行
- 参数：output
- 返回类型：Name(id='str', ctx=Load())

### `_state_paths()` [私有]
- 位置：第 248-249 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_load_runtime_state()` [私有]
- 位置：第 252-262 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_coerce_int()` [私有]
- 位置：第 265-268 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_describe_runtime_endpoint()` [私有]
- 位置：第 271-274 行
- 参数：host, port
- 返回类型：Name(id='str', ctx=Load())

### `_describe_cleanup_hint()` [私有]
- 位置：第 277-281 行
- 参数：paths
- 返回类型：Name(id='str', ctx=Load())

### `_describe_uncertain_reason()` [私有]
- 位置：第 284-294 行
- 参数：pid_state, health_state, exe_path, port
- 返回类型：Name(id='str', ctx=Load())

### `_pid_signal()` [私有]
- 位置：第 297-317 行
- 参数：payload
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_health_signal()` [私有]
- 位置：第 320-331 行
- 参数：contract
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_runtime_state_snapshot()` [私有]
- 位置：第 334-352 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_assert_no_active_runtime()` [私有]
- 位置：第 355-397 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_git_head_sha()` [私有]
- 位置：第 400-411 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_git_status_lines()` [私有]
- 位置：第 414-425 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_tracked_status_lines()` [私有]
- 位置：第 428-430 行
- 参数：lines
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_status_untracked_path()` [私有]
- 位置：第 433-437 行
- 参数：line
- 返回类型：Name(id='str', ctx=Load())

### `_high_risk_untracked_source_paths()` [私有]
- 位置：第 440-451 行
- 参数：lines
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_dirty_worktree_message()` [私有]
- 位置：第 454-459 行
- 参数：lines
- 返回类型：Name(id='str', ctx=Load())

### `_parse_collect_nodeids()` [私有]
- 位置：第 462-463 行
- 参数：output
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_build_collection_proof()` [私有]
- 位置：第 466-467 行
- 参数：default_collect_nodeids
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_resolve_command_args()` [私有]
- 位置：第 470-478 行
- 参数：command
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_write_quality_gate_manifest()` [私有]
- 位置：第 481-486 行
- 参数：manifest
- 返回类型：Constant(value=None, kind=None)

### `_apply_worktree_proof()` [私有]
- 位置：第 489-507 行
- 参数：manifest
- 返回类型：Constant(value=None, kind=None)

### `_base_quality_gate_manifest()` [私有]
- 位置：第 510-540 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_parse_args_legacy()` [私有]
- 位置：第 543-546 行
- 参数：argv
- 返回类型：Attribute(value=Name(id='argparse', ctx=Load()), attr='Names

### `_parse_args()` [私有]
- 位置：第 549-556 行
- 参数：argv
- 返回类型：Attribute(value=Name(id='argparse', ctx=Load()), attr='Names

### `main()` [公开]
- 位置：第 559-693 行
- 参数：argv
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（2 处）：
  - `scripts/sync_debt_ledger.py:186` [Script] `raise SystemExit(main())`
  - `scripts/convert_rotary_shell_unit_excel.py:124` [Script] `raise SystemExit(main())`
- **被调用者**（38 个）：`_parse_args`, `build_quality_gate_command_plan`, `isoformat`, `_clear_quality_gate_receipts`, `_git_head_sha`, `_git_status_lines`, `_runtime_state_snapshot`, `bool`, `_base_quality_gate_manifest`, `_write_quality_gate_manifest`, `str`, `dict`, `_assert_guard_tests_ready`, `_resolve_command_args`, `_coerce_command_result`

## tools/quality_gate_operations.py（Tool 层）

### `refresh_migrate_inline_facts()` [公开]
- 位置：第 47-122 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:95` [Script] `next_ledger = refresh_migrate_inline_facts(current)`
- **被调用者**（35 个）：`load_sp02_facts_snapshot`, `cast`, `sorted`, `complexity_scan_map`, `scan_silent_fallback_entries`, `finalize_ledger_update`, `load_ledger`, `get`, `set`, `len`, `find_existing_by_id`, `new_oversize_entries.append`, `new_complexity_entries.append`, `silent_counter.items`, `key.split`

### `refresh_scan_startup_baseline()` [公开]
- 位置：第 125-169 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:97` [Script] `next_ledger = refresh_scan_startup_baseline(current)`
- **被调用者**（30 个）：`validate_startup_samples`, `collect_startup_scope_files`, `cast`, `set`, `scan_oversize_entries`, `scan_complexity_entries`, `scan_silent_fallback_entries`, `finalize_ledger_update`, `load_ledger`, `get`, `find_existing_by_id`, `build_oversize_entry`, `entry.setdefault`, `startup_oversize.append`, `build_complexity_entry`

### `_silent_scan_index()` [私有]
- 位置：第 172-182 行
- 参数：entries
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_resolve_silent_refresh_entry()` [私有]
- 位置：第 185-207 行
- 参数：entry, silent_scan
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `refresh_auto_fields()` [公开]
- 位置：第 210-247 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:100` [Script] `next_ledger = refresh_auto_fields(current)`
- **被调用者**（25 个）：`cast`, `sorted`, `complexity_scan_map`, `_silent_scan_index`, `finalize_ledger_update`, `load_ledger`, `get`, `str`, `len`, `refreshed_oversize.append`, `format`, `refreshed_complexity.append`, `scan_silent_fallback_entries`, `_resolve_silent_refresh_entry`, `refreshed_silent.append`

### `set_entry_fields()` [公开]
- 位置：第 250-272 行
- 参数：ledger, entry_id, updates
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:127` [Script] `next_ledger = set_entry_fields(ledger, args.id, updates)`
- **被调用者**（8 个）：`finalize_ledger_update`, `cast`, `get`, `updates.items`, `QualityGateError`, `str`, `ledger.get`, `entry.get`

### `upsert_risk()` [公开]
- 位置：第 275-310 行
- 参数：ledger, risk_id, entry_ids, owner, reason, review_after, exit_condition, notes
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:142` [Script] `next_ledger = upsert_risk(`
- **被调用者**（10 个）：`collect_main_entry_ids`, `cast`, `finalize_ledger_update`, `list`, `accepted_risks.append`, `QualityGateError`, `ledger.get`, `str`, `current.get`, `dict`

### `delete_risk()` [公开]
- 位置：第 313-319 行
- 参数：ledger, risk_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:166` [Script] `next_ledger = delete_risk(ledger, args.id)`
- **被调用者**（8 个）：`cast`, `finalize_ledger_update`, `dict`, `len`, `QualityGateError`, `ledger.get`, `str`, `risk.get`

### `validate_ledger_against_current_scan()` [公开]
- 位置：第 322-354 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:77` [Script] `summary = validate_ledger_against_current_scan(ledger)`
- **被调用者**（16 个）：`validate_ledger`, `validate_startup_samples`, `str`, `cast`, `complexity_scan_map`, `_silent_scan_index`, `entry.get`, `len`, `format`, `scan_silent_fallback_entries`, `get`, `ledger.get`, `splitlines`, `int`, `QualityGateError`

### `architecture_oversize_allowlist_map()` [公开]
- 位置：第 357-358 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`str`, `dict`, `entry.get`, `cast`, `ledger.get`

### `architecture_complexity_allowlist_map()` [公开]
- 位置：第 361-365 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`format`, `dict`, `entry.get`, `cast`, `ledger.get`

### `architecture_silent_allowlist_map()` [公开]
- 位置：第 368-372 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`str`, `dict`, `entry.get`, `get`, `cast`, `ledger.get`

### `architecture_silent_scan_entries()` [公开]
- 位置：第 375-392 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`scan_silent_fallback_entries`, `sorted`, `collect_quality_rule_files`, `is_startup_scope_path`, `bool`, `str`, `entries.append`, `entry.get`, `dict`, `normalized.pop`

### `architecture_oversize_scan_map()` [公开]
- 位置：第 395-396 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`str`, `entry.get`, `scan_oversize_entries`, `collect_quality_rule_files`

### `architecture_complexity_scan_map()` [公开]
- 位置：第 399-400 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`complexity_scan_map`, `collect_quality_rule_files`

### `architecture_request_service_direct_assembly_entries()` [公开]
- 位置：第 403-421 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`set`, `scan_request_service_direct_assembly_entries`, `str`, `collect_globbed_files`, `REQUEST_SERVICE_TARGET_SYMBOLS.items`, `target_symbols.get`, `entry.get`

### `architecture_repository_bundle_drift_entries()` [公开]
- 位置：第 424-425 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`scan_repository_bundle_drift_entries`, `collect_globbed_files`

## tools/quality_gate_shared.py（Tool 层）

### `now_shanghai_iso()` [公开]
- 位置：第 298-299 行
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
- 位置：第 302-303 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`replace`, `relpath`

### `repo_abs()` [公开]
- 位置：第 306-307 行
- 参数：rel_path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`join`, `replace`, `str`

### `read_text_file()` [公开]
- 位置：第 310-312 行
- 参数：rel_path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（10 处）：
  - `tools/quality_gate_operations.py:62` [Tool] `current_value = len(read_text_file(path).splitlines())`
  - `tools/quality_gate_operations.py:220` [Tool] `current_value = len(read_text_file(path).splitlines())`
  - `tools/quality_gate_operations.py:332` [Tool] `current_value = len(read_text_file(str(entry.get("path"))).splitlines())`
  - `tools/quality_gate_ledger.py:50` [Tool] `text = read_text_file("开发文档/技术债务治理台账.md")`
  - `tools/quality_gate_ledger.py:129` [Tool] `text = read_text_file("开发文档/阶段留痕与验收记录.md")`
  - `tools/quality_gate_scan.py:34` [Tool] `source = read_text_file(rel_path)`
  - `tools/quality_gate_scan.py:573` [Tool] `source_lines = read_text_file(rel_path).splitlines()`
  - `tools/quality_gate_scan.py:698` [Tool] `source_lines = read_text_file(rel_path).splitlines()`
  - `tools/quality_gate_scan.py:745` [Tool] `source = read_text_file(rel_path)`
  - `tools/quality_gate_scan.py:776` [Tool] `line_count = len(read_text_file(rel_path).splitlines())`
- **被调用者**（3 个）：`open`, `f.read`, `repo_abs`

### `write_text_file()` [公开]
- 位置：第 315-321 行
- 参数：rel_path, content
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `tools/quality_gate_ledger.py:123` [Tool] `write_text_file("开发文档/技术债务治理台账.md", render_ledger_markdown(sorted_ledger))`
- **被调用者**（5 个）：`repo_abs`, `dirname`, `os.makedirs`, `open`, `f.write`

### `slugify()` [公开]
- 位置：第 324-333 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（11 处）：
  - `tools/quality_gate_entries.py:71` [Tool] `"id": f"oversize:{slugify(path)}",`
  - `tools/quality_gate_entries.py:86` [Tool] `"id": f"complexity:{slugify(path)}-{slugify(symbol)}",`
  - `tools/quality_gate_operations.py:63` [Tool] `existing = find_existing_by_id(oversize_existing, f"oversize:{slugify(path)}")`
  - `tools/quality_gate_operations.py:76` [Tool] `"complexity:{}-{}".format(slugify(item["path"]), slugify(item["symbol"])),`
  - `tools/quality_gate_operations.py:137` [Tool] `existing = find_existing_by_id(oversize_existing, "oversize:{}".format(slugify(i`
  - `tools/quality_gate_operations.py:146` [Tool] `"complexity:{}-{}".format(slugify(item["path"]), slugify(item["symbol"])),`
  - `tools/quality_gate_scan.py:138` [Tool] `return slugify(slice_node.value)`
  - `tools/quality_gate_scan.py:142` [Tool] `return slugify(inner.value)`
  - `tools/quality_gate_scan.py:150` [Tool] `return f"attr:{slugify(target.attr)}"`
  - `tools/quality_gate_scan.py:371` [Tool] `slugify(entry.get("path")),`
  - `tools/quality_gate_scan.py:372` [Tool] `slugify(entry.get("symbol") or "module"),`
- **被调用者**（6 个）：`strip`, `text.replace`, `text.endswith`, `re.sub`, `lower`, `str`

### `collect_py_files()` [公开]
- 位置：第 336-349 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`sorted`, `repo_abs`, `os.walk`, `set`, `isdir`, `files.append`, `name.endswith`, `name.startswith`, `repo_rel`, `join`

### `collect_globbed_files()` [公开]
- 位置：第 352-359 行
- 参数：patterns
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `tools/quality_gate_operations.py:409` [Tool] `entries = scan_request_service_direct_assembly_entries(collect_globbed_files(REQ`
  - `tools/quality_gate_operations.py:425` [Tool] `return scan_repository_bundle_drift_entries(collect_globbed_files(REPOSITORY_BUN`
  - `tools/quality_gate_scan.py:569` [Tool] `paths = collect_globbed_files(REQUEST_SERVICE_SCAN_SCOPE_PATTERNS)`
  - `tools/quality_gate_scan.py:694` [Tool] `paths = collect_globbed_files(REPOSITORY_BUNDLE_DRIFT_SCOPE_PATTERNS)`
- **被调用者**（8 个）：`sorted`, `join`, `glob.glob`, `set`, `pattern.replace`, `isfile`, `files.append`, `repo_rel`

### `collect_startup_scope_files()` [公开]
- 位置：第 362-363 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `tools/quality_gate_operations.py:129` [Tool] `startup_files = collect_startup_scope_files()`
  - `tools/quality_gate_scan.py:384` [Tool] `entries = scan_silent_fallback_entries(collect_startup_scope_files())`
- **被调用者**（1 个）：`collect_globbed_files`

### `_stable_json_hash()` [私有]
- 位置：第 366-368 行
- 参数：payload
- 返回类型：Name(id='str', ctx=Load())

### `_sha256_text()` [私有]
- 位置：第 371-372 行
- 参数：text
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_command_rows()` [私有]
- 位置：第 375-390 行
- 参数：commands
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_normalize_source_rows()` [私有]
- 位置：第 393-404 行
- 参数：gate_sources
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_normalize_required_tests()` [私有]
- 位置：第 407-416 行
- 参数：required_tests
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_normalize_collection_proof()` [私有]
- 位置：第 419-441 行
- 参数：collection_proof
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_normalize_command_receipt_payload()` [私有]
- 位置：第 444-457 行
- 参数：payload
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_normalize_command_receipt_index()` [私有]
- 位置：第 460-469 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `parse_pytest_collect_nodeids()` [公开]
- 位置：第 472-486 行
- 参数：output
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:463` [Script] `return parse_pytest_collect_nodeids(output)`
- **被调用者**（9 个）：`set`, `splitlines`, `raw_line.strip`, `seen.add`, `nodeids.append`, `str`, `line.startswith`, `line.split`, `token.startswith`

### `collect_current_pytest_nodeids()` [公开]
- 位置：第 489-503 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`subprocess.run`, `str`, `int`, `parse_pytest_collect_nodeids`, `os.fspath`

### `_resolve_quality_gate_command_args()` [私有]
- 位置：第 506-511 行
- 参数：command
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_command_output_policy()` [私有]
- 位置：第 514-516 行
- 参数：command
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_command_output_for_policy()` [私有]
- 位置：第 519-526 行
- 参数：text
- 返回类型：Name(id='str', ctx=Load())

### `_hash_command_output()` [私有]
- 位置：第 529-530 行
- 参数：text
- 返回类型：Name(id='str', ctx=Load())

### `replay_quality_gate_command_plan()` [公开]
- 位置：第 533-568 行
- 参数：repo_root, commands
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`enumerate`, `_normalize_command_rows`, `strip`, `subprocess.run`, `_resolve_quality_gate_command_args`, `int`, `build_quality_gate_receipt_rel_path`, `join`, `_normalize_command_receipt_payload`, `_command_output_policy`, `str`, `os.fspath`, `receipt_rel.replace`, `isfile`, `json.loads`

### `iter_quality_gate_required_tests()` [公开]
- 位置：第 571-572 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:37` [Script] `REQUIRED_TEST_ARGS = list(iter_quality_gate_required_tests())`
- **被调用者**（2 个）：`list`, `_normalize_required_tests`

### `iter_non_regression_guard_tests()` [公开]
- 位置：第 575-582 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`basename`, `name.startswith`, `out.append`, `str`

### `build_quality_gate_command_plan()` [公开]
- 位置：第 585-660 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:561` [Script] `command_plan = build_quality_gate_command_plan()`
- **被调用者**（3 个）：`iter_quality_gate_required_tests`, `join`, `list`

### `build_quality_gate_receipt_rel_path()` [公开]
- 位置：第 663-667 行
- 参数：index, display
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:126` [Script] `receipt_rel = build_quality_gate_receipt_rel_path(index, str(command.get("displa`
- **被调用者**（9 个）：`replace`, `slugify`, `rstrip`, `hexdigest`, `join`, `int`, `hashlib.sha256`, `encode`, `str`

### `build_quality_gate_command_receipt()` [公开]
- 位置：第 670-695 行
- 参数：command
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:129` [Script] `receipt_payload = build_quality_gate_command_receipt(`
- **被调用者**（10 个）：`_command_output_policy`, `_normalize_command_receipt_payload`, `_normalize_command_rows`, `strip`, `int`, `_stable_json_hash`, `list`, `bool`, `_hash_command_output`, `str`

### `build_quality_gate_collection_proof()` [公开]
- 位置：第 698-718 行
- 参数：default_collect_nodeids
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:467` [Script] `return build_quality_gate_collection_proof(default_collect_nodeids, required_tes`
- **被调用者**（9 个）：`_normalize_required_tests`, `_normalize_collection_proof`, `strip`, `any`, `key_test_rows.append`, `list`, `iter_quality_gate_required_tests`, `str`, `nodeid.startswith`

### `_sha256_file()` [私有]
- 位置：第 721-729 行
- 参数：abs_path
- 返回类型：Name(id='str', ctx=Load())

### `build_quality_gate_source_proof()` [公开]
- 位置：第 732-745 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`abspath`, `_normalize_source_rows`, `join`, `isfile`, `rows.append`, `os.fspath`, `rel_path.replace`, `replace`, `bool`, `_sha256_file`, `str`

### `hash_required_tests_registry()` [公开]
- 位置：第 748-749 行
- 参数：required_tests
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_required_tests`

### `hash_quality_gate_commands()` [公开]
- 位置：第 752-753 行
- 参数：commands
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_command_rows`

### `hash_quality_gate_collection_proof()` [公开]
- 位置：第 756-757 行
- 参数：collection_proof
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_collection_proof`

### `hash_quality_gate_source_proof()` [公开]
- 位置：第 760-761 行
- 参数：gate_sources
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_source_rows`

### `hash_quality_gate_command_receipts()` [公开]
- 位置：第 764-765 行
- 参数：command_receipts
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_command_receipt_index`

### `apply_quality_gate_manifest_proof_fields()` [公开]
- 位置：第 768-794 行
- 参数：manifest
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `scripts/run_quality_gate.py:539` [Script] `apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)`
  - `scripts/run_quality_gate.py:662` [Script] `apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)`
  - `scripts/run_quality_gate.py:691` [Script] `apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)`
- **被调用者**（14 个）：`dict`, `_normalize_required_tests`, `hash_required_tests_registry`, `_normalize_command_rows`, `hash_quality_gate_commands`, `_normalize_collection_proof`, `hash_quality_gate_collection_proof`, `_normalize_command_receipt_index`, `hash_quality_gate_command_receipts`, `_normalize_source_rows`, `hash_quality_gate_source_proof`, `manifest.get`, `iter_quality_gate_required_tests`, `build_quality_gate_source_proof`

### `_git_rev_parse_path()` [私有]
- 位置：第 797-812 行
- 参数：repo_root
- 返回类型：Name(id='str', ctx=Load())

### `repo_identity()` [公开]
- 位置：第 815-820 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`abspath`, `_git_rev_parse_path`, `os.fspath`, `join`

### `_verify_quality_gate_collection_proof()` [私有]
- 位置：第 823-838 行
- 参数：manifest
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_load_verified_quality_gate_receipt()` [私有]
- 位置：第 841-862 行
- 参数：repo_root, receipt_entry, command
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_verify_quality_gate_receipt_payload()` [私有]
- 位置：第 865-903 行
- 参数：receipt_payload, command
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_verify_quality_gate_command_receipts()` [私有]
- 位置：第 906-940 行
- 参数：repo_root, manifest
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `verify_quality_gate_manifest()` [公开]
- 位置：第 943-1050 行
- 参数：无
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（30 个）：`repo_identity`, `realpath`, `strip`, `bool`, `_normalize_required_tests`, `iter_quality_gate_required_tests`, `_normalize_command_rows`, `build_quality_gate_command_plan`, `collect_current_pytest_nodeids`, `_verify_quality_gate_collection_proof`, `_verify_quality_gate_command_receipts`, `_normalize_source_rows`, `build_quality_gate_source_proof`, `replay_quality_gate_command_plan`, `git_status_short_lines`

### `git_status_short_lines()` [公开]
- 位置：第 1053-1064 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`subprocess.run`, `rstrip`, `str`, `splitlines`, `strip`

### `collect_quality_rule_files()` [公开]
- 位置：第 1067-1068 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `tools/quality_gate_operations.py:383` [Tool] `for entry in scan_silent_fallback_entries(collect_quality_rule_files()):`
  - `tools/quality_gate_operations.py:396` [Tool] `return {str(entry.get("path")): entry for entry in scan_oversize_entries(collect`
  - `tools/quality_gate_operations.py:400` [Tool] `return complexity_scan_map(collect_quality_rule_files())`
- **被调用者**（4 个）：`sorted`, `set`, `collect_py_files`, `collect_startup_scope_files`

### `is_startup_scope_path()` [公开]
- 位置：第 1071-1073 行
- 参数：path
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `tools/quality_gate_operations.py:167` [Tool] `"entries": remove_entries_by_predicate(silent_existing, lambda entry: is_startup`
  - `tools/quality_gate_operations.py:384` [Tool] `if is_startup_scope_path(str(entry.get("path"))):`
- **被调用者**（3 个）：`replace`, `rel_path.startswith`, `str`

### `ensure_single_marker()` [公开]
- 位置：第 1076-1079 行
- 参数：text, marker, label
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`text.count`, `QualityGateError`

### `extract_marked_block()` [公开]
- 位置：第 1082-1089 行
- 参数：text, begin_marker, end_marker, label
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`ensure_single_marker`, `text.index`, `strip`, `len`, `QualityGateError`

### `extract_json_code_block()` [公开]
- 位置：第 1092-1104 行
- 参数：text, begin_marker, end_marker, label
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `tools/quality_gate_ledger.py:51` [Tool] `ledger = extract_json_code_block(text, LEDGER_BEGIN, LEDGER_END, "治理台账")`
  - `tools/quality_gate_ledger.py:130` [Tool] `payload = extract_json_code_block(text, SP02_FACT_BEGIN, SP02_FACT_END, "SP02 事实`
- **被调用者**（7 个）：`extract_marked_block`, `re.search`, `strip`, `QualityGateError`, `json.loads`, `isinstance`, `match.group`

### `render_marked_json_block()` [公开]
- 位置：第 1107-1109 行
- 参数：begin_marker, end_marker, payload
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `tools/quality_gate_ledger.py:61` [Tool] `payload_block = render_marked_json_block(LEDGER_BEGIN, LEDGER_END, ledger)`
- **被调用者**（1 个）：`json.dumps`

## web/bootstrap/factory.py（Bootstrap 层）

### `_app_log_once()` [私有]
- 位置：第 57-65 行
- 参数：app, key, level, message
- 返回类型：Constant(value=None, kind=None)

### `_apply_runtime_config()` [私有]
- 位置：第 71-79 行
- 参数：app
- 返回类型：Constant(value=None, kind=None)

### `should_use_runtime_reloader()` [公开]
- 位置：第 82-84 行
- 参数：debug, frozen
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:197` [Bootstrap] `use_reloader = deps.should_use_runtime_reloader(debug)`
- **被调用者**（2 个）：`bool`, `getattr`

### `_should_register_exit_backup()` [私有]
- 位置：第 87-92 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `should_own_runtime_resources()` [公开]
- 位置：第 95-100 行
- 参数：debug, frozen, run_main
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:198` [Bootstrap] `owns_runtime_resources = deps.should_own_runtime_resources(debug)`
- **被调用者**（2 个）：`_should_register_exit_backup`, `bool`

### `_is_exit_backup_enabled()` [私有]
- 位置：第 103-121 行
- 参数：bm
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_run_exit_backup()` [私有]
- 位置：第 124-143 行
- 参数：manager
- 返回类型：Name(id='bool', ctx=Load())

### `_maintenance_gate_response()` [私有]
- 位置：第 146-153 行
- 参数：无
- 返回类型：无注解

### `_maintenance_detection_failure_response()` [私有]
- 位置：第 156-163 行
- 参数：无
- 返回类型：无注解

### `_default_anchor_file()` [私有]
- 位置：第 166-168 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `should_register_runtime_lifecycle_handlers()` [公开]
- 位置：第 171-172 行
- 参数：debug
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:254` [Bootstrap] `if deps.should_register_runtime_lifecycle_handlers(debug):`
- **被调用者**（2 个）：`should_own_runtime_resources`, `bool`

### `serve_runtime_app()` [公开]
- 位置：第 175-186 行
- 参数：app, host, port
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:262` [Bootstrap] `deps.serve_runtime_app(app, host, port)`
- **被调用者**（3 个）：`make_server`, `int`, `server.serve_forever`

### `request_runtime_server_shutdown()` [公开]
- 位置：第 189-207 行
- 参数：logger
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/system_health.py:53` [Route] `if not request_runtime_server_shutdown(logger=current_app.logger):`
- **被调用者**（5 个）：`start`, `time.sleep`, `server.shutdown`, `threading.Thread`, `safe_log`

### `create_app_core()` [公开]
- 位置：第 210-466 行
- 参数：无
- 返回类型：Name(id='Flask', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:63` [Bootstrap] `return create_app_core(`
- **被调用者**（59 个）：`lower`, `runtime_base_dir`, `join`, `Flask`, `from_object`, `_apply_runtime_config`, `int`, `install_versioned_url_for`, `AppLogger`, `setLevel`, `init_ui_mode`, `dirname`, `os.makedirs`, `abspath`, `ensure_schema`

## web/bootstrap/plugins.py（Bootstrap 层）

### `_status_degradation_collector()` [私有]
- 位置：第 14-38 行
- 参数：status
- 返回类型：Name(id='DegradationCollector', ctx=Load())

### `_merge_plugin_degradation()` [私有]
- 位置：第 41-48 行
- 参数：status, collector
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_apply_enabled_sources()` [私有]
- 位置：第 51-97 行
- 参数：status
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_plugin_config_reader()` [私有]
- 位置：第 100-146 行
- 参数：conn
- 返回类型：无注解

### `bootstrap_plugins()` [公开]
- 位置：第 149-238 行
- 参数：base_dir, database_path
- 返回类型：无注解
- **调用者**（1 处）：
  - `web/bootstrap/factory.py:281` [Bootstrap] `plugin_status = bootstrap_plugins(`
- **被调用者**（19 个）：`DegradationCollector`, `_build_plugin_config_reader`, `_apply_enabled_sources`, `_merge_plugin_degradation`, `get_connection`, `callable`, `getattr`, `isinstance`, `PluginManager.load_from_base_dir`, `collector.add`, `safe_log`, `int`, `info`, `bool`, `get_plugin_status`

## web/bootstrap/request_services.py（Bootstrap 层）

### `RequestServices.__init__()` [私有]
- 位置：第 49-60 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `RequestServices._construct()` [私有]
- 位置：第 62-66 行
- 参数：attr_name, factory
- 返回类型：Name(id='Any', ctx=Load())

### `RequestServices.schedule_service()` [公开]
- 位置：第 69-73 行
- 参数：无
- 返回类型：Name(id='ScheduleService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `ScheduleService`

### `RequestServices.batch_service()` [公开]
- 位置：第 76-80 行
- 参数：无
- 返回类型：Name(id='BatchService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `BatchService`

### `RequestServices.config_service()` [公开]
- 位置：第 83-87 行
- 参数：无
- 返回类型：Name(id='ConfigService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `ConfigService`

### `RequestServices.calendar_service()` [公开]
- 位置：第 90-94 行
- 参数：无
- 返回类型：Name(id='CalendarService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `CalendarService`

### `RequestServices.schedule_history_query_service()` [公开]
- 位置：第 97-101 行
- 参数：无
- 返回类型：Name(id='ScheduleHistoryQueryService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `ScheduleHistoryQueryService`

### `RequestServices.machine_service()` [公开]
- 位置：第 104-108 行
- 参数：无
- 返回类型：Name(id='MachineService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `MachineService`

### `RequestServices.operator_service()` [公开]
- 位置：第 111-115 行
- 参数：无
- 返回类型：Name(id='OperatorService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `OperatorService`

### `RequestServices.supplier_service()` [公开]
- 位置：第 118-122 行
- 参数：无
- 返回类型：Name(id='SupplierService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `SupplierService`

### `RequestServices.operator_machine_query_service()` [公开]
- 位置：第 125-129 行
- 参数：无
- 返回类型：Name(id='OperatorMachineQueryService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `OperatorMachineQueryService`

### `RequestServices.material_service()` [公开]
- 位置：第 132-136 行
- 参数：无
- 返回类型：Name(id='MaterialService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `MaterialService`

### `RequestServices.batch_material_service()` [公开]
- 位置：第 139-143 行
- 参数：无
- 返回类型：Name(id='BatchMaterialService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `BatchMaterialService`

### `RequestServices.gantt_service()` [公开]
- 位置：第 146-150 行
- 参数：无
- 返回类型：Name(id='GanttService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `GanttService`

### `RequestServices.resource_dispatch_service()` [公开]
- 位置：第 153-157 行
- 参数：无
- 返回类型：Name(id='ResourceDispatchService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `ResourceDispatchService`

### `RequestServices.part_service()` [公开]
- 位置：第 160-164 行
- 参数：无
- 返回类型：Name(id='PartService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `PartService`

### `RequestServices.part_operation_query_service()` [公开]
- 位置：第 167-171 行
- 参数：无
- 返回类型：Name(id='PartOperationQueryService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `PartOperationQueryService`

### `RequestServices.excel_service()` [公开]
- 位置：第 174-182 行
- 参数：无
- 返回类型：Name(id='ExcelService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self._construct`, `ExcelService`, `self._get_excel_backend`

### `RequestServices.system_config_service()` [公开]
- 位置：第 185-189 行
- 参数：无
- 返回类型：Name(id='SystemConfigService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `SystemConfigService`

### `RequestServices.system_job_state_query_service()` [公开]
- 位置：第 192-196 行
- 参数：无
- 返回类型：Name(id='SystemJobStateQueryService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `SystemJobStateQueryService`

### `RequestServices.operation_log_service()` [公开]
- 位置：第 199-203 行
- 参数：无
- 返回类型：Name(id='OperationLogService', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`self._construct`, `OperationLogService`

### `RequestServices.execute_preview_rows_transactional()` [公开]
- 位置：第 205-206 行
- 参数：无
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（8 处）：
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:82` [Route] `return services.execute_preview_rows_transactional(**kwargs)`
  - `web/routes/domains/scheduler/scheduler_excel_calendar.py:400` [Route] `stats = execute_preview_rows_transactional(`
  - `core/services/scheduler/calendar_service.py:199` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/scheduler/batch_excel_import.py:93` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/equipment/machine_excel_import_service.py:94` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/personnel/operator_excel_import_service.py:77` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/process/op_type_excel_import_service.py:65` [Service] `stats = execute_preview_rows_transactional(`
  - `core/services/process/supplier_excel_import_service.py:94` [Service] `stats = execute_preview_rows_transactional(`

## web/error_boundary.py（Other 层）

### `_normalized_reason()` [私有]
- 位置：第 41-44 行
- 参数：details
- 返回类型：Name(id='str', ctx=Load())

### `_field_only_details()` [私有]
- 位置：第 47-51 行
- 参数：exc
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_looks_internal_message()` [私有]
- 位置：第 54-56 行
- 参数：message
- 返回类型：Name(id='bool', ctx=Load())

### `get_user_visible_field_label()` [公开]
- 位置：第 59-71 行
- 参数：field
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:163` [Route] `labels = [get_user_visible_field_label(key) or str(key).strip() for key in clean`
- **被调用者**（4 个）：`strip`, `str`, `_KNOWN_FIELD_LABELS.get`, `field_label_for`

### `_message_mentions_internal_field()` [私有]
- 位置：第 74-83 行
- 参数：message, field
- 返回类型：Name(id='bool', ctx=Load())

### `_message_mentions_machine_key()` [私有]
- 位置：第 86-87 行
- 参数：message
- 返回类型：Name(id='bool', ctx=Load())

### `_public_invalid_query_details()` [私有]
- 位置：第 90-108 行
- 参数：details
- 返回类型：Name(id='dict', ctx=Load())

### `_public_report_details()` [私有]
- 位置：第 111-123 行
- 参数：details
- 返回类型：Name(id='dict', ctx=Load())

### `_replace_field_details()` [私有]
- 位置：第 126-135 行
- 参数：details
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_validation_error_message()` [私有]
- 位置：第 138-155 行
- 参数：exc, details
- 返回类型：Name(id='str', ctx=Load())

### `user_visible_app_error_message()` [公开]
- 位置：第 158-162 行
- 参数：exc
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（20 处）：
  - `web/routes/domains/scheduler/scheduler_week_plan.py:239` [Route] `return user_visible_app_error_message(e), 404`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:240` [Route] `flash(user_visible_app_error_message(e), "error")`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:289` [Route] `flash(user_visible_app_error_message(e), "error")`
  - `web/routes/domains/scheduler/scheduler_batches.py:246` [Route] `flash(user_visible_app_error_message(e), "error")`
  - `web/routes/domains/scheduler/scheduler_batches.py:262` [Route] `flash(user_visible_app_error_message(e), "error")`
  - `web/routes/domains/scheduler/scheduler_batches.py:285` [Route] `failed_details.append(f"{bid}: {user_visible_app_error_message(e)}")`
  - `web/routes/domains/scheduler/scheduler_batches.py:342` [Route] `return f"{bid}（{user_visible_app_error_message(e)}）"`
  - `web/routes/domains/scheduler/scheduler_batches.py:367` [Route] `failed.append(f"{bid}（{user_visible_app_error_message(e)}）")`
  - `web/routes/domains/scheduler/scheduler_batches.py:436` [Route] `flash(user_visible_app_error_message(e), "error")`
  - `web/routes/domains/scheduler/scheduler_config.py:366` [Route] `flash(user_visible_app_error_message(e), "error")`
  - `web/routes/domains/scheduler/scheduler_config.py:396` [Route] `flash(user_visible_app_error_message(e), "error")`
  - `web/routes/domains/scheduler/scheduler_config.py:411` [Route] `flash(user_visible_app_error_message(e), "error")`
  - `web/routes/domains/scheduler/scheduler_config.py:460` [Route] `flash(user_visible_app_error_message(e), "error")`
  - `web/routes/domains/scheduler/scheduler_run.py:105` [Route] `flash(user_visible_app_error_message(e), "error")`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:71` [Route] `f"系统配置项 holiday_default_efficiency 非法，无法保存日历，请先在排产参数中修复。{user_visible_app_error_`
  - `web/routes/domains/scheduler/scheduler_calendar_pages.py:75` [Route] `flash(user_visible_app_error_message(exc), "error")`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:189` [Route] `flash(user_visible_app_error_message(exc), "error")`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:191` [Route] `flash(user_visible_app_error_message(exc), "error")`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:259` [Route] `return user_visible_app_error_message(exc), 404`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:260` [Route] `flash(user_visible_app_error_message(exc), "error")`
- **被调用者**（2 个）：`isinstance`, `_validation_error_message`

### `user_visible_app_error_details()` [公开]
- 位置：第 165-183 行
- 参数：exc
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`_normalized_reason`, `_replace_field_details`, `isinstance`, `details.get`, `_field_only_details`, `strip`, `_looks_internal_message`, `_message_mentions_internal_field`, `_message_mentions_machine_key`, `str`

### `user_visible_app_error_diagnostics()` [公开]
- 位置：第 186-203 行
- 参数：exc
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`_normalized_reason`, `isinstance`, `details.get`

### `build_user_visible_app_error_payload()` [公开]
- 位置：第 206-215 行
- 参数：exc
- 返回类型：Name(id='dict', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:155` [Route] `payload = build_user_visible_app_error_payload(exc)`
- **被调用者**（5 个）：`error_response`, `user_visible_app_error_diagnostics`, `user_visible_app_error_message`, `user_visible_app_error_details`, `payload.setdefault`

### `wants_json_error_response()` [公开]
- 位置：第 218-226 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`startswith`

### `wants_json_error_response_or_default()` [公开]
- 位置：第 229-241 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `web/bootstrap/factory.py:148` [Bootstrap] `if wants_json_error_response_or_default(`
  - `web/bootstrap/factory.py:158` [Bootstrap] `if wants_json_error_response_or_default(`
- **被调用者**（4 个）：`wants_json_error_response`, `bool`, `getattr`, `logger.warning`

### `json_error_response()` [公开]
- 位置：第 244-245 行
- 参数：exc
- 返回类型：无注解
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_gantt.py:106` [Route] `return json_error_response(exc)`
  - `web/routes/domains/scheduler/scheduler_resource_dispatch.py:221` [Route] `return json_error_response(exc, payload=_error_payload_with_invalid_query_keys(e`
- **被调用者**（3 个）：`jsonify`, `app_error_http_status`, `build_user_visible_app_error_payload`

### `_details_text()` [私有]
- 位置：第 248-256 行
- 参数：details
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `render_minimal_error_page()` [公开]
- 位置：第 259-302 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/bootstrap/factory.py:319` [Bootstrap] `render_minimal_error_page(`
  - `web/bootstrap/factory.py:332` [Bootstrap] `render_minimal_error_page(`
- **被调用者**（5 个）：`html.escape`, `_details_text`, `join`, `str`, `extra_parts.append`

### `render_error_template()` [公开]
- 位置：第 305-333 行
- 参数：template_name
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/bootstrap/factory.py:153` [Bootstrap] `return render_error_template(title="系统维护中", code="503", message=message), 503`
  - `web/bootstrap/factory.py:163` [Bootstrap] `return render_error_template(title="系统状态检测失败", code="500", message=message), 500`
- **被调用者**（4 个）：`render_template`, `getattr`, `render_minimal_error_page`, `logger.error`

## web/error_handlers.py（Other 层）

### `_resolve_field_label()` [私有]
- 位置：第 19-25 行
- 参数：details
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `register_error_handlers()` [公开]
- 位置：第 28-94 行
- 参数：app
- 返回类型：无注解
- **调用者**（1 处）：
  - `web/bootstrap/factory.py:433` [Bootstrap] `register_error_handlers(app)`
- **被调用者**（12 个）：`app.errorhandler`, `warning`, `app_error_http_status`, `user_visible_app_error_message`, `user_visible_app_error_details`, `wants_json_error_response_or_default`, `error_response`, `error`, `render_error_template`, `build_user_visible_app_error_payload`, `_resolve_field_label`, `traceback.format_exc`

## web/routes/_scheduler_compat.py（Route 层）

### `load_scheduler_route_module()` [公开]
- 位置：第 7-13 行
- 参数：domain_module
- 返回类型：Name(id='ModuleType', ctx=Load())
- **调用者**（9 处）：
  - `web/routes/scheduler_excel_calendar.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_excel_calendar`
  - `web/routes/scheduler_week_plan.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_week_plan")`
  - `web/routes/scheduler_batches.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_batches")`
  - `web/routes/scheduler_config.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_config")`
  - `web/routes/scheduler_run.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_run")`
  - `web/routes/scheduler_excel_batches.py:6` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_excel_batches"`
  - `web/routes/scheduler_analysis.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_analysis")`
  - `web/routes/scheduler_batch_detail.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_batch_detail")`
  - `web/routes/scheduler_ops.py:7` [Route] `_impl = load_scheduler_route_module(".domains.scheduler.scheduler_ops")`
- **被调用者**（4 个）：`importlib.import_module`, `getattr`, `callable`, `register_routes`

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

### `_resolve_analysis_version()` [私有]
- 位置：第 50-59 行
- 参数：versions
- 返回类型：无注解

### `_selected_analysis_version()` [私有]
- 位置：第 62-65 行
- 参数：version_resolution
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_missing_history_message()` [私有]
- 位置：第 68-71 行
- 参数：selected_ver
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_selected_history_placeholder()` [私有]
- 位置：第 74-87 行
- 参数：selected_ver
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_ensure_selected_analysis_context()` [私有]
- 位置：第 90-100 行
- 参数：ctx
- 返回类型：Constant(value=None, kind=None)

### `_trend_summary_state()` [私有]
- 位置：第 103-110 行
- 参数：raw_hist
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `analysis_page()` [公开]
- 位置：第 114-149 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（16 个）：`bp.get`, `q.list_versions`, `_resolve_analysis_version`, `_selected_analysis_version`, `_load_recent_analysis_history`, `_load_selected_analysis_item`, `build_analysis_context`, `build_requested_history_resolution`, `_ensure_selected_analysis_context`, `build_summary_display_state`, `render_template`, `ctx.get`, `_missing_history_message`, `get`, `_trend_summary_state`

## web/routes/domains/scheduler/scheduler_batches.py（Route 层）

### `batches_page()` [公开]
- 位置：第 39-163 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（44 个）：`bp.get`, `strip`, `parse_page_args`, `batch_svc.list`, `paginate_rows`, `cfg_svc.get_snapshot`, `cfg_svc.get_available_strategies`, `get_scheduler_visible_config_field_metadata`, `build_config_degraded_display_state`, `cfg_svc.get_preset_display_state`, `list`, `preset_display_state.get`, `dict`, `build_auto_assign_persist_display_state`, `build_summary_display_state`

### `batches_manage_page()` [公开]
- 位置：第 167-212 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `strip`, `parse_page_args`, `batch_svc.list`, `paginate_rows`, `part_svc.list`, `render_template`, `view_rows.append`, `get`, `b.to_dict`, `_priority_zh`, `_ready_zh`, `_batch_status_zh`

### `create_batch()` [公开]
- 位置：第 216-247 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `get`, `_strict_mode_enabled`, `batch_svc.create_batch_from_template`, `flash`, `_surface_schedule_warnings`, `redirect`, `batch_svc.consume_user_visible_warnings`, `url_for`, `user_visible_app_error_message`, `len`, `batch_svc.list_operations`

### `delete_batch()` [公开]
- 位置：第 251-265 行
- 参数：batch_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`bp.post`, `strip`, `_safe_next_url`, `batch_svc.delete`, `flash`, `redirect`, `url_for`, `get`, `user_visible_app_error_message`

### `bulk_delete_batches()` [公开]
- 位置：第 269-297 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.post`, `getlist`, `flash`, `redirect`, `join`, `url_for`, `batch_svc.delete`, `failed.append`, `failed_details.append`, `exception`, `len`, `str`, `user_visible_app_error_message`

### `_next_batch_id_like()` [私有]
- 位置：第 300-320 行
- 参数：src, exists_fn
- 返回类型：Name(id='str', ctx=Load())

### `_bulk_update_one_batch()` [私有]
- 位置：第 323-345 行
- 参数：batch_svc, bid
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `bulk_copy_batches()` [公开]
- 位置：第 350-379 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.post`, `getlist`, `flash`, `redirect`, `url_for`, `_next_batch_id_like`, `batch_svc.copy_batch`, `mappings.append`, `str`, `failed.append`, `exception`, `len`, `join`, `get`, `user_visible_app_error_message`

### `bulk_update_batches()` [公开]
- 位置：第 383-411 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.post`, `getlist`, `get`, `flash`, `redirect`, `strip`, `_bulk_update_one_batch`, `url_for`, `remark.strip`, `str`, `failed.append`, `len`, `join`

### `generate_ops()` [公开]
- 位置：第 415-437 行
- 参数：batch_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.post`, `_strict_mode_enabled`, `batch_svc.get`, `redirect`, `get`, `batch_svc.create_batch_from_template`, `len`, `flash`, `_surface_schedule_warnings`, `url_for`, `batch_svc.list_operations`, `batch_svc.consume_user_visible_warnings`, `user_visible_app_error_message`

## web/routes/domains/scheduler/scheduler_calendar_pages.py（Route 层）

### `calendar_page()` [公开]
- 位置：第 14-40 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`bp.get`, `cfg_svc.get_holiday_default_efficiency_display_state`, `render_template`, `c.to_dict`, `_normalize_day_type`, `_normalize_yesno`, `_day_type_zh`, `cal_svc.list_all`, `r.get`

### `calendar_upsert()` [公开]
- 位置：第 44-78 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`bp.post`, `get`, `flash`, `redirect`, `cal_svc.upsert`, `url_for`, `strip`, `user_visible_app_error_message`, `str`

## web/routes/domains/scheduler/scheduler_config.py（Route 层）

### `_warn_scheduler_config_degraded_once()` [私有]
- 位置：第 40-46 行
- 参数：fields
- 返回类型：Constant(value=None, kind=None)

### `_resolve_scheduler_manual_md_path()` [私有]
- 位置：第 49-74 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_resolve_manual_back_url()` [私有]
- 位置：第 77-85 行
- 参数：raw_src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_build_manual_page_url()` [私有]
- 位置：第 88-94 行
- 参数：raw_src, raw_page
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_scheduler_manual_args()` [私有]
- 位置：第 97-104 行
- 参数：raw_src, raw_page
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_resolve_manual_entry_endpoint()` [私有]
- 位置：第 107-111 行
- 参数：manual_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_format_manual_mtime()` [私有]
- 位置：第 114-118 行
- 参数：manual_path
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_load_manual_text_and_mtime()` [私有]
- 位置：第 121-145 行
- 参数：manual_path, candidates
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_manual_download_url()` [私有]
- 位置：第 148-157 行
- 参数：manual_path, safe_src, safe_page
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_build_related_manual_links()` [私有]
- 位置：第 160-172 行
- 参数：related_manuals, link_src
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_resolve_page_back_action()` [私有]
- 位置：第 175-180 行
- 参数：raw_page, back_url
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_manual_page_view_state()` [私有]
- 位置：第 183-220 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `config_manual_page()` [公开]
- 位置：第 224-265 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `strip`, `_normalize_scheduler_manual_args`, `_resolve_manual_back_url`, `_resolve_scheduler_manual_md_path`, `_load_manual_text_and_mtime`, `_build_manual_download_url`, `_build_manual_page_view_state`, `render_template`, `flash`, `back_url.startswith`, `get`

### `config_manual_download()` [公开]
- 位置：第 269-293 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.get`, `strip`, `_normalize_scheduler_manual_args`, `_resolve_scheduler_manual_md_path`, `flash`, `redirect`, `send_file`, `_build_manual_page_url`, `exception`, `get`

### `config_page()` [公开]
- 位置：第 295-343 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.get`, `cfg_svc.get_snapshot`, `cfg_svc.get_available_strategies`, `get_scheduler_visible_config_field_metadata`, `build_config_degraded_display_state`, `_warn_scheduler_config_degraded_once`, `float`, `config_field_warnings.get`, `cfg_svc.get_preset_display_state`, `list`, `preset_display_state.get`, `dict`, `build_auto_assign_persist_display_state`, `render_template`, `getattr`

### `preset_apply()` [公开]
- 位置：第 347-370 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.post`, `redirect`, `get`, `_safe_next_url`, `url_for`, `_normalize_requested_preset_name`, `_is_custom_preset_name`, `cfg_svc.apply_preset`, `_flash_preset_apply_feedback`, `cfg_svc.mark_active_preset_custom`, `flash`, `exception`, `user_visible_app_error_message`

### `preset_save()` [公开]
- 位置：第 374-400 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.post`, `redirect`, `get`, `cfg_svc.save_preset`, `url_for`, `strip`, `list`, `flash`, `exception`, `_format_preset_error_flash`, `user_visible_app_error_message`, `str`, `saved.get`

### `preset_delete()` [公开]
- 位置：第 404-415 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `redirect`, `get`, `cfg_svc.delete_preset`, `flash`, `url_for`, `exception`, `user_visible_app_error_message`

### `_collect_scheduler_config_form_payload()` [私有]
- 位置：第 418-441 行
- 参数：form
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_normalize_requested_preset_name()` [私有]
- 位置：第 444-445 行
- 参数：name
- 返回类型：Name(id='str', ctx=Load())

### `_is_custom_preset_name()` [私有]
- 位置：第 448-449 行
- 参数：name_text
- 返回类型：Name(id='bool', ctx=Load())

### `update_config()` [公开]
- 位置：第 453-464 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`bp.post`, `redirect`, `_collect_scheduler_config_form_payload`, `cfg_svc.save_page_config`, `_flash_config_save_outcome`, `url_for`, `flash`, `exception`, `user_visible_app_error_message`

### `restore_config_default()` [公开]
- 位置：第 466-470 行
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
  - `web/routes/domains/scheduler/scheduler_batches.py:69` [Route] `config_field_metadata = get_scheduler_visible_config_field_metadata()`
  - `web/routes/domains/scheduler/scheduler_config.py:304` [Route] `config_field_metadata = get_scheduler_visible_config_field_metadata()`
- **被调用者**（2 个）：`page_metadata_for`, `list`

### `_format_config_display_value()` [私有]
- 位置：第 31-39 行
- 参数：field, value
- 返回类型：Name(id='str', ctx=Load())

### `public_config_field_label()` [公开]
- 位置：第 48-55 行
- 参数：field
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`strip`, `str`, `_CONFIG_PUBLIC_FIELD_LABELS.get`, `field_label_for`

### `public_config_field_labels()` [公开]
- 位置：第 58-64 行
- 参数：fields
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`public_config_field_label`, `strip`, `labels.append`, `str`

### `public_hidden_config_warning()` [公开]
- 位置：第 67-69 行
- 参数：field
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`public_config_field_label`

### `public_hidden_repair_notice()` [公开]
- 位置：第 72-77 行
- 参数：fields
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config_feedback.py:105` [Route] `messages.append(public_hidden_repair_notice(fields, blocked=kind == "blocked_hid`
- **被调用者**（2 个）：`join`, `public_config_field_labels`

### `public_meta_parse_warning()` [公开]
- 位置：第 80-81 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_config_feedback.py:109` [Route] `messages.append(public_meta_parse_warning())`

### `build_config_degraded_display_state()` [公开]
- 位置：第 84-114 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:70` [Route] `config_field_warnings, config_degraded_fields, config_hidden_warnings = build_co`
  - `web/routes/domains/scheduler/scheduler_config.py:305` [Route] `config_field_warnings, config_degraded_fields, config_hidden_warnings = build_co`
- **被调用者**（10 个）：`getattr`, `strip`, `hidden_warnings.append`, `isinstance`, `config_field_metadata.get`, `str`, `_format_config_display_value`, `degraded_fields.append`, `public_hidden_config_warning`, `get`

### `build_auto_assign_persist_display_state()` [公开]
- 位置：第 117-138 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/domains/scheduler/scheduler_batches.py:88` [Route] `current_auto_assign_persist_state = build_auto_assign_persist_display_state(geta`
  - `web/routes/domains/scheduler/scheduler_batches.py:130` [Route] `latest_auto_assign_persist_state = build_auto_assign_persist_display_state(`
  - `web/routes/domains/scheduler/scheduler_config.py:324` [Route] `auto_assign_persist_state = build_auto_assign_persist_display_state(getattr(cfg,`
- **被调用者**（3 个）：`lower`, `strip`, `str`

## web/routes/domains/scheduler/scheduler_config_feedback.py（Route 层）

### `_normalized_error_fields()` [私有]
- 位置：第 12-17 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_format_single_field_preset_error()` [私有]
- 位置：第 20-28 行
- 参数：detail, field_key
- 返回类型：Name(id='str', ctx=Load())

### `_format_preset_error_flash()` [私有]
- 位置：第 31-46 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_flash_preset_apply_feedback()` [私有]
- 位置：第 49-74 行
- 参数：applied
- 返回类型：Constant(value=None, kind=None)

### `_config_save_outcome_fields()` [私有]
- 位置：第 77-78 行
- 参数：outcome, field_name
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_config_save_primary_flash()` [私有]
- 位置：第 81-93 行
- 参数：outcome
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_iter_config_save_notice_messages()` [私有]
- 位置：第 96-110 行
- 参数：outcome
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_flash_config_save_outcome()` [私有]
- 位置：第 113-119 行
- 参数：outcome
- 返回类型：Constant(value=None, kind=None)

## web/routes/domains/scheduler/scheduler_excel_calendar.py（Route 层）

### `_canonicalize_calendar_date()` [私有]
- 位置：第 45-49 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_build_existing_preview_data()` [私有]
- 位置：第 52-68 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_calendar_baseline_extra_state()` [私有]
- 位置：第 71-72 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_require_holiday_default_efficiency()` [私有]
- 位置：第 75-78 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())

### `execute_preview_rows_transactional()` [公开]
- 位置：第 81-82 行
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
- 位置：第 85-107 行
- 参数：无
- 返回类型：无注解

### `_load_holiday_default_efficiency_for_excel()` [私有]
- 位置：第 110-132 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `excel_calendar_page()` [公开]
- 位置：第 136-145 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`bp.get`, `_build_existing_preview_data`, `_render_excel_calendar_page`

### `excel_calendar_preview()` [公开]
- 位置：第 149-261 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（30 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `_build_existing_preview_data`, `_load_holiday_default_efficiency_for_excel`, `_require_holiday_default_efficiency`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_calendar_page`, `ValidationError`

### `excel_calendar_confirm()` [公开]
- 位置：第 265-434 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（44 个）：`bp.post`, `time.time`, `_parse_mode`, `load_confirm_payload`, `_build_existing_preview_data`, `_load_holiday_default_efficiency_for_excel`, `_require_holiday_default_efficiency`, `preview_baseline_is_stale`, `_ensure_unique_ids`, `excel_svc.preview_import`, `collect_error_rows`, `set`, `execute_preview_rows_transactional`, `stats.to_dict`, `extract_import_stats`

### `excel_calendar_template()` [公开]
- 位置：第 438-479 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_calendar_export()` [公开]
- 位置：第 483-523 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `cal_svc.list_all`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`, `_normalize_day_type`, `_normalize_yesno`

## web/routes/domains/scheduler/scheduler_gantt.py（Route 层）

### `_get_int_arg()` [私有]
- 位置：第 14-21 行
- 参数：name, default
- 返回类型：Name(id='int', ctx=Load())

### `_get_bool_arg()` [私有]
- 位置：第 24-33 行
- 参数：name, default
- 返回类型：Name(id='bool', ctx=Load())

### `gantt_page()` [公开]
- 位置：第 37-77 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `strip`, `_get_int_arg`, `svc.resolve_version`, `svc.resolve_week_range`, `list_versions`, `render_template`, `get`, `BusinessError`, `isoformat`, `version_resolution.to_dict`, `bool`, `url_for`

### `gantt_data()` [公开]
- 位置：第 81-109 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.get`, `strip`, `_get_int_arg`, `_get_bool_arg`, `svc.get_gantt_tasks`, `jsonify`, `json_error_response`, `exception`, `get`, `error_response`

## web/routes/domains/scheduler/scheduler_resource_dispatch.py（Route 层）

### `_svc()` [私有]
- 位置：第 53-54 行
- 参数：无
- 返回类型：Name(id='Any', ctx=Load())

### `_arg_text()` [私有]
- 位置：第 57-62 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_request_kwargs()` [私有]
- 位置：第 65-78 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_current_request_args()` [私有]
- 位置：第 81-88 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_url_with_query()` [私有]
- 位置：第 91-96 行
- 参数：endpoint, query
- 返回类型：Name(id='str', ctx=Load())

### `_page_url()` [私有]
- 位置：第 99-100 行
- 参数：query
- 返回类型：Name(id='str', ctx=Load())

### `_export_url()` [私有]
- 位置：第 103-110 行
- 参数：filters
- 返回类型：Name(id='str', ctx=Load())

### `_drop_keys()` [私有]
- 位置：第 113-115 行
- 参数：values
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_error_field()` [私有]
- 位置：第 118-124 行
- 参数：exc
- 返回类型：Name(id='str', ctx=Load())

### `_is_missing_history_version_error()` [私有]
- 位置：第 127-131 行
- 参数：exc
- 返回类型：Name(id='bool', ctx=Load())

### `_sanitize_dispatch_args_from_error()` [私有]
- 位置：第 134-144 行
- 参数：exc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_cleanup_query_keys_from_error()` [私有]
- 位置：第 147-151 行
- 参数：exc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_error_payload_with_invalid_query_keys()` [私有]
- 位置：第 154-174 行
- 参数：exc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `resource_dispatch_page()` [公开]
- 位置：第 178-212 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（16 个）：`bp.get`, `_svc`, `render_template`, `svc.build_page_context`, `context.get`, `_export_url`, `_is_missing_history_version_error`, `_current_request_args`, `flash`, `exception`, `url_for`, `_request_kwargs`, `_sanitize_dispatch_args_from_error`, `user_visible_app_error_message`, `redirect`

### `resource_dispatch_data()` [公开]
- 位置：第 216-224 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`bp.get`, `get_dispatch_payload`, `jsonify`, `json_error_response`, `exception`, `_svc`, `_request_kwargs`, `_error_payload_with_invalid_query_keys`, `error_response`

### `resource_dispatch_export()` [公开]
- 位置：第 228-265 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（21 个）：`bp.get`, `time.time`, `_svc`, `redirect`, `svc.build_export`, `int`, `log_excel_export`, `send_file`, `_page_url`, `payload.get`, `flash`, `exception`, `_current_request_args`, `_request_kwargs`, `summary.get`

## web/routes/domains/scheduler/scheduler_route_registrar.py（Route 层）

### `register_scheduler_routes()` [公开]
- 位置：第 23-29 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/scheduler.py:9` [Route] `register_scheduler_routes()`
  - `web/bootstrap/factory.py:440` [Bootstrap] `register_scheduler_routes()`
- **被调用者**（1 个）：`importlib.import_module`

## web/routes/domains/scheduler/scheduler_run.py（Route 层）

### `_parse_optional_checkbox_flag()` [私有]
- 位置：第 19-29 行
- 参数：name
- 返回类型：无注解

### `_run_result_flash()` [私有]
- 位置：第 32-52 行
- 参数：result
- 返回类型：Constant(value=None, kind=None)

### `run_schedule()` [公开]
- 位置：第 56-110 行
- 参数：无
- 返回类型：无注解
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_week_plan.py:266` [Route] `result = sch_svc.run_schedule(`
  - `core/services/scheduler/run/schedule_optimizer.py:378` [Service] `说明：为保证兼容，本函数尽量保持与原 `ScheduleService.run_schedule()` 相同的口径与留痕结构。`
- **被调用者**（26 个）：`bp.post`, `getlist`, `_parse_optional_checkbox_flag`, `_strict_mode_enabled`, `redirect`, `get`, `sch_svc.run_schedule`, `build_summary_display_state`, `_run_result_flash`, `summary_display.get`, `isinstance`, `_surface_secondary_degradation_messages`, `_surface_schedule_warnings`, `_surface_schedule_errors`, `url_for`

## web/routes/domains/scheduler/scheduler_week_plan.py（Route 层）

### `_get_int_arg()` [私有]
- 位置：第 27-34 行
- 参数：name, default
- 返回类型：Name(id='int', ctx=Load())

### `_parse_optional_checkbox_flag()` [私有]
- 位置：第 37-47 行
- 参数：name
- 返回类型：无注解

### `_load_selected_week_plan_summary()` [私有]
- 位置：第 50-68 行
- 参数：services, version
- 返回类型：无注解

### `_build_week_plan_preview_state()` [私有]
- 位置：第 71-86 行
- 参数：data
- 返回类型：无注解

### `_flash_summary_primary_degradation()` [私有]
- 位置：第 89-95 行
- 参数：summary_display
- 返回类型：无注解

### `_flash_simulate_completion()` [私有]
- 位置：第 98-105 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_flash_simulate_summary()` [私有]
- 位置：第 108-118 行
- 参数：summary, summary_display
- 返回类型：Constant(value=None, kind=None)

### `week_plan_page()` [公开]
- 位置：第 122-180 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（18 个）：`bp.get`, `_get_int_arg`, `svc.resolve_week_range`, `list_versions`, `svc.get_week_plan_rows`, `data.get`, `build_requested_history_resolution`, `_build_week_plan_preview_state`, `render_template`, `strip`, `_load_selected_week_plan_summary`, `isoformat`, `get`, `int`, `build_summary_display_state`

### `week_plan_export()` [公开]
- 位置：第 184-245 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（21 个）：`bp.get`, `time.time`, `_get_int_arg`, `strip`, `svc.get_week_plan_rows`, `int`, `data.get`, `build_xlsx_bytes`, `log_excel_export`, `send_file`, `BusinessError`, `flash`, `redirect`, `exception`, `get`

### `simulate_schedule()` [公开]
- 位置：第 249-294 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（21 个）：`bp.post`, `getlist`, `_parse_optional_checkbox_flag`, `_strict_mode_enabled`, `get`, `flash`, `redirect`, `sch_svc.run_schedule`, `int`, `build_summary_display_state`, `str`, `_flash_simulate_completion`, `_flash_simulate_summary`, `isoformat`, `url_for`

## web/routes/normalizers.py（Route 层）

### `_normalize_batch_priority()` [私有]
- 位置：第 24-32 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_ready_status()` [私有]
- 位置：第 35-47 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_day_type()` [私有]
- 位置：第 50-60 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_operator_calendar_day_type()` [私有]
- 位置：第 63-67 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_yesno()` [私有]
- 位置：第 70-82 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `default_version_to_latest()` [公开]
- 位置：第 85-86 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`int`

### `parse_explicit_version_or_latest()` [公开]
- 位置：第 89-101 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`strip`, `ValidationError`, `text.lower`, `default_version_to_latest`, `int`, `str`

### `normalize_version_or_latest_fallback()` [公开]
- 位置：第 104-117 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`default_version_to_latest`, `strip`, `parse_explicit_version_or_latest`, `str`

### `normalize_version_or_latest()` [公开]
- 位置：第 120-121 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`normalize_version_or_latest_fallback`

### `resolve_route_version_or_latest()` [公开]
- 位置：第 124-125 行
- 参数：value
- 返回类型：无注解
- **调用者**（2 处）：
  - `web/routes/domains/scheduler/scheduler_analysis.py:54` [Route] `return resolve_route_version_or_latest(`
  - `web/routes/domains/scheduler/scheduler_analysis.py:59` [Route] `return resolve_route_version_or_latest(None, latest_version=latest_version)`
- **被调用者**（1 个）：`resolve_version_or_latest`

### `parse_optional_version_int()` [公开]
- 位置：第 128-141 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `web/routes/system_history.py:26` [Route] `ver = parse_optional_version_int(request.args.get("version"), field="version")`
- **被调用者**（4 个）：`strip`, `int`, `str`, `ValidationError`

### `_log_result_summary_warning()` [私有]
- 位置：第 144-148 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_parse_result_summary_payload_with_meta()` [私有]
- 位置：第 151-201 行
- 参数：raw_summary
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_parse_result_summary_payload()` [私有]
- 位置：第 204-212 行
- 参数：raw_summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

## web/routes/reports.py（Route 层）

### `_default_date_range()` [私有]
- 位置：第 19-22 行
- 参数：days
- 返回类型：无注解

### `_validate_ymd_date()` [私有]
- 位置：第 25-35 行
- 参数：raw, field
- 返回类型：Name(id='str', ctx=Load())

### `_export_version_or_latest()` [私有]
- 位置：第 38-48 行
- 参数：engine
- 返回类型：Name(id='int', ctx=Load())

### `_resolve_report_version()` [私有]
- 位置：第 51-57 行
- 参数：engine, raw_version
- 返回类型：Name(id='VersionResolution', ctx=Load())

### `_page_version_or_latest()` [私有]
- 位置：第 60-68 行
- 参数：engine
- 返回类型：Name(id='VersionResolution', ctx=Load())

### `_page_date_range_or_version_span()` [私有]
- 位置：第 71-82 行
- 参数：engine, version, start_raw, end_raw
- 返回类型：无注解

### `_send_report_export_file()` [私有]
- 位置：第 85-99 行
- 参数：report_export
- 返回类型：无注解

### `index()` [公开]
- 位置：第 103-119 行
- 参数：无
- 返回类型：无注解
- **调用者**（2 处）：
  - `tools/quality_gate_shared.py:1085` [Tool] `start = text.index(begin_marker) + len(begin_marker)`
  - `tools/quality_gate_shared.py:1086` [Tool] `end = text.index(end_marker)`
- **被调用者**（9 个）：`bp.get`, `ReportEngine`, `engine.list_versions`, `bool`, `render_template`, `int`, `engine.overdue_batches`, `get`, `rep.get`

### `overdue_page()` [公开]
- 位置：第 123-149 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`bp.get`, `ReportEngine`, `engine.list_versions`, `_page_version_or_latest`, `bool`, `render_template`, `engine.overdue_batches`, `int`, `rep.get`

### `overdue_export()` [公开]
- 位置：第 153-157 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `ReportEngine`, `_export_version_or_latest`, `engine.export_overdue_xlsx`, `_send_report_export_file`

### `utilization_page()` [公开]
- 位置：第 161-202 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`bp.get`, `ReportEngine`, `engine.list_versions`, `_page_version_or_latest`, `_page_date_range_or_version_span`, `bool`, `render_template`, `int`, `engine.utilization`, `get`, `rep.get`

### `utilization_export()` [公开]
- 位置：第 206-217 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`bp.get`, `strip`, `ReportEngine`, `_export_version_or_latest`, `engine.export_utilization_xlsx`, `_send_report_export_file`, `_default_date_range`, `_validate_ymd_date`, `get`

### `downtime_page()` [公开]
- 位置：第 221-260 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`bp.get`, `ReportEngine`, `engine.list_versions`, `_page_version_or_latest`, `_page_date_range_or_version_span`, `bool`, `render_template`, `int`, `engine.downtime_impact`, `rep.get`, `get`

### `downtime_export()` [公开]
- 位置：第 264-275 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`bp.get`, `strip`, `ReportEngine`, `_export_version_or_latest`, `engine.export_downtime_impact_xlsx`, `_send_report_export_file`, `_default_date_range`, `_validate_ymd_date`, `get`

## web/viewmodels/scheduler_degradation_presenter.py（ViewModel 层）

### `_safe_int()` [私有]
- 位置：第 26-30 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_degradation_label_for()` [私有]
- 位置：第 33-37 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_public_message_for_event()` [私有]
- 位置：第 40-44 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `format_degradation_detail()` [公开]
- 位置：第 47-52 行
- 参数：label, count
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_summary_display.py:55` [ViewModel] `return format_degradation_detail(item.get("label"), item.get("count"))`
- **被调用者**（4 个）：`strip`, `max`, `_safe_int`, `str`

### `degradation_reason_key()` [公开]
- 位置：第 55-60 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_summary_display.py:93` [ViewModel] `reason_key = degradation_reason_key(code=item.get("code"), label=label, count=it`
- **被调用者**（4 个）：`strip`, `max`, `_safe_int`, `str`

### `degradation_display_key()` [公开]
- 位置：第 63-67 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_summary_display.py:94` [ViewModel] `item_display_key = degradation_display_key(`
- **被调用者**（3 个）：`degradation_reason_key`, `strip`, `str`

### `_normalize_result_state()` [私有]
- 位置：第 70-88 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_primary_degradation_message()` [私有]
- 位置：第 91-103 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_summary_degradation_events()` [私有]
- 位置：第 106-139 行
- 参数：selected_summary
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `build_summary_degradation_messages()` [公开]
- 位置：第 142-143 行
- 参数：selected_summary
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/viewmodels/scheduler_summary_display.py:263` [ViewModel] `secondary_degradation_messages = build_summary_degradation_messages(summary_dict`
  - `web/viewmodels/scheduler_analysis_vm.py:202` [ViewModel] `summary_degradation_messages = build_summary_degradation_messages(selected_summa`
- **被调用者**（1 个）：`_normalize_summary_degradation_events`

### `build_primary_degradation()` [公开]
- 位置：第 146-179 行
- 参数：selected_summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/viewmodels/scheduler_summary_display.py:262` [ViewModel] `primary_degradation = build_primary_degradation(summary_dict, result_state=resul`
  - `web/viewmodels/scheduler_analysis_vm.py:207` [ViewModel] `primary_degradation = build_primary_degradation(`
- **被调用者**（10 个）：`_normalize_summary_degradation_events`, `_normalize_result_state`, `_primary_degradation_message`, `strip`, `format_degradation_detail`, `degradation_reason_key`, `item.get`, `details.append`, `detail_keys.append`, `str`

## web/viewmodels/scheduler_summary_display.py（ViewModel 层）

### `_normalize_text_list()` [私有]
- 位置：第 21-39 行
- 参数：value
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_public_error_messages()` [私有]
- 位置：第 42-51 行
- 参数：value
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_secondary_display_label()` [私有]
- 位置：第 54-55 行
- 参数：item
- 返回类型：Name(id='str', ctx=Load())

### `_primary_detail_keys()` [私有]
- 位置：第 58-68 行
- 参数：primary_degradation
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Index(valu

### `_safe_freeze_secondary_message()` [私有]
- 位置：第 71-78 行
- 参数：item, message
- 返回类型：Name(id='bool', ctx=Load())

### `_normalize_secondary_display_item()` [私有]
- 位置：第 81-118 行
- 参数：item
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `build_display_secondary_degradation_messages()` [公开]
- 位置：第 121-145 行
- 参数：primary_degradation, secondary_degradation_messages
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_analysis_vm.py:212` [ViewModel] `display_summary_degradation_messages = build_display_secondary_degradation_messa`
- **被调用者**（10 个）：`set`, `_primary_detail_keys`, `list`, `_normalize_text_list`, `_normalize_secondary_display_item`, `display_item.pop`, `seen.add`, `filtered.append`, `isinstance`, `get`

### `_counts_from_summary()` [私有]
- 位置：第 148-163 行
- 参数：summary
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_safe_int_or_none()` [私有]
- 位置：第 166-172 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_has_degraded_cause()` [私有]
- 位置：第 175-187 行
- 参数：summary, code
- 返回类型：Name(id='bool', ctx=Load())

### `_build_warning_pipeline_display()` [私有]
- 位置：第 190-220 行
- 参数：summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `derive_completion_status()` [公开]
- 位置：第 223-240 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`lower`, `_counts_from_summary`, `int`, `isinstance`, `strip`, `counts.get`, `str`

### `build_result_state()` [公开]
- 位置：第 243-250 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/viewmodels/scheduler_analysis_vm.py:203` [ViewModel] `result_state = build_result_state(`
- **被调用者**（4 个）：`lower`, `derive_completion_status`, `strip`, `str`

### `build_summary_display_state()` [公开]
- 位置：第 253-303 行
- 参数：summary
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（9 处）：
  - `web/routes/system_history.py:25` [Route] `selected_summary_display = build_summary_display_state(None, result_status=None)`
  - `web/routes/system_history.py:38` [Route] `selected_summary_display = build_summary_display_state(`
  - `web/routes/system_history.py:55` [Route] `it["result_summary_display"] = build_summary_display_state(`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:63` [Route] `summary_display = build_summary_display_state(`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:141` [Route] `else (None, None, build_summary_display_state(None, result_status=None))`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:277` [Route] `summary_display = build_summary_display_state(`
  - `web/routes/domains/scheduler/scheduler_batches.py:109` [Route] `latest_summary_display = build_summary_display_state(`
  - `web/routes/domains/scheduler/scheduler_run.py:76` [Route] `summary_display = build_summary_display_state(`
  - `web/routes/domains/scheduler/scheduler_analysis.py:134` [Route] `selected_summary_display = build_summary_display_state(`
- **被调用者**（16 个）：`build_result_state`, `str`, `build_primary_degradation`, `build_summary_degradation_messages`, `build_display_secondary_degradation_messages`, `_build_warning_pipeline_display`, `_normalize_text_list`, `public_summary_warning_messages`, `_public_error_messages`, `max`, `len`, `isinstance`, `summary_dict.get`, `int`, `parse_state_dict.update`

---
- 分析函数/方法数：642
- 找到调用关系：584 处
- 跨层边界风险：8 项
