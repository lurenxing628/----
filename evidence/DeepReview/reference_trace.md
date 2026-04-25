# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ run_local_search() 返回 Optional，但 core/services/scheduler/run/schedule_optimizer.py:172 的调用者未做 None 检查
- ⚠ init_seen_hashes() 返回 Optional，但 core/services/scheduler/run/optimizer_local_search.py:270 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/services/scheduler/run/optimizer_config.py（Service 层）

### `OptimizerConfig.strategy_keys()` [公开]
- 位置：第 42-46 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:147` [Service] `keys=optimizer_cfg.strategy_keys(),`
- **被调用者**（1 个）：`str`

### `OptimizerConfig.dispatch_modes()` [公开]
- 位置：第 48-51 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:148` [Service] `dispatch_modes=optimizer_cfg.dispatch_modes(),`

### `field_label()` [公开]
- 位置：第 54-55 行
- 参数：field
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`_FIELD_LABELS.get`, `strip`, `str`

### `require_choice()` [公开]
- 位置：第 58-63 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`field_label`, `lower`, `set`, `ValidationError`, `strip`, `str`

### `require_float()` [公开]
- 位置：第 66-67 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`float`, `parse_required_float`

### `require_int()` [公开]
- 位置：第 70-71 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`int`, `parse_required_int`

### `normalized_choice_values()` [公开]
- 位置：第 74-85 行
- 参数：values
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`set`, `tuple`, `isinstance`, `lower`, `seen.add`, `out.append`, `strip`, `str`

### `effective_choice_values()` [公开]
- 位置：第 88-96 行
- 参数：field
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`tuple`, `normalized_choice_values`, `set`, `getattr`, `lower`, `choices_for`, `strip`, `str`

### `record_optimizer_cfg_degradations()` [公开]
- 位置：第 99-113 行
- 参数：snapshot, optimizer_algo_stats
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`mapping.items`, `getattr`, `strip`, `isinstance`, `increment_counter`, `str`, `get`

### `ensure_optimizer_config_snapshot()` [公开]
- 位置：第 116-121 行
- 参数：cfg
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:93` [Service] `cfg = ensure_optimizer_config_snapshot(cfg, strict_mode=bool(strict_mode))`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:29` [Service] `return ensure_optimizer_config_snapshot(cfg, strict_mode=bool(strict_mode))`
- **被调用者**（2 个）：`ensure_schedule_config_snapshot`, `bool`

### `weighted_strategy_params()` [公开]
- 位置：第 124-128 行
- 参数：snapshot
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/run/schedule_optimizer_steps.py:100` [Service] `return weighted_strategy_params(snapshot, strict_mode=bool(strict_mode))`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:300` [Service] `return weighted_strategy_params(cfg, strict_mode=bool(strict_mode))`
- **被调用者**（1 个）：`require_float`

### `is_ortools_enabled()` [公开]
- 位置：第 131-132 行
- 参数：snapshot
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_optimizer_steps.py:241` [Service] `if algo_mode != "improve" or not is_ortools_enabled(snapshot):`
- **被调用者**（2 个）：`to_yes_no`, `getattr`

### `ortools_time_limit_seconds()` [公开]
- 位置：第 135-136 行
- 参数：snapshot
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_optimizer_steps.py:86` [Service] `tl_cfg = ortools_time_limit_seconds(snapshot)`
- **被调用者**（1 个）：`require_int`

### `resolve_optimizer_config()` [公开]
- 位置：第 139-181 行
- 参数：无
- 返回类型：Name(id='OptimizerConfig', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:98` [Service] `optimizer_cfg = resolve_optimizer_config(`
- **被调用者**（8 个）：`effective_choice_values`, `SortStrategy`, `OptimizerConfig`, `require_choice`, `record_optimizer_cfg_degradations`, `weighted_strategy_params`, `require_int`, `bool`

## core/services/scheduler/run/optimizer_local_search.py（Service 层）

### `_swap_neighbor()` [私有]
- 位置：第 13-17 行
- 参数：order, rnd
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_insert_neighbor()` [私有]
- 位置：第 20-26 行
- 参数：order, rnd
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_block_neighbor()` [私有]
- 位置：第 29-44 行
- 参数：order, rnd
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_choose_neighbor()` [私有]
- 位置：第 47-59 行
- 参数：order, rnd
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_evaluate_candidate()` [私有]
- 位置：第 62-111 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_record_improvement()` [私有]
- 位置：第 114-154 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_shake_order()` [私有]
- 位置：第 157-171 行
- 参数：order, rnd
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_should_skip_seen()` [私有]
- 位置：第 174-181 行
- 参数：cand_order, seen_hashes
- 返回类型：Name(id='bool', ctx=Load())

### `run_local_search()` [公开]
- 位置：第 184-271 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:172` [Service] `state.best = runtime.run_local_search(`
- **被调用者**（17 个）：`rng_factory`, `list`, `dict`, `str`, `max`, `init_seen_hashes`, `int`, `min`, `_choose_neighbor`, `_should_skip_seen`, `_evaluate_candidate`, `len`, `best.get`, `clock`, `_record_improvement`

## core/services/scheduler/run/optimizer_search_state.py（Service 层）

### `score_tuple()` [公开]
- 位置：第 7-16 行
- 参数：score
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`tuple`, `isinstance`, `float`, `out.append`

### `_attempt_dispatch_mode()` [私有]
- 位置：第 19-20 行
- 参数：item
- 返回类型：Name(id='str', ctx=Load())

### `_attempt_tag()` [私有]
- 位置：第 23-24 行
- 参数：item
- 返回类型：Name(id='str', ctx=Load())

### `_sorted_attempts_by_score()` [私有]
- 位置：第 27-28 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_best_attempts_by_dispatch_mode()` [私有]
- 位置：第 31-38 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_append_unique_best_attempts()` [私有]
- 位置：第 41-56 行
- 参数：selected, attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `compact_attempts()` [公开]
- 位置：第 59-65 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:225` [Service] `attempts=state.compact_attempts(limit=12),`
  - `core/services/scheduler/run/schedule_optimizer.py:252` [Service] `attempts=state.compact_attempts(limit=12),`
- **被调用者**（7 个）：`_best_attempts_by_dispatch_mode`, `_append_unique_best_attempts`, `selected.sort`, `len`, `list`, `score_tuple`, `item.get`

### `init_seen_hashes()` [公开]
- 位置：第 68-76 行
- 参数：cur_order, best
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `core/services/scheduler/run/optimizer_local_search.py:224` [Service] `seen_hashes = init_seen_hashes(cur_order, best)`
  - `core/services/scheduler/run/optimizer_local_search.py:270` [Service] `seen_hashes = init_seen_hashes(cur_order, best)`
- **被调用者**（5 个）：`isinstance`, `len`, `tuple`, `seen_hashes.add`, `best.get`

### `OptimizerSearchState.compact_attempts()` [公开]
- 位置：第 85-86 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:225` [Service] `attempts=state.compact_attempts(limit=12),`
  - `core/services/scheduler/run/schedule_optimizer.py:252` [Service] `attempts=state.compact_attempts(limit=12),`
- **被调用者**（7 个）：`_best_attempts_by_dispatch_mode`, `_append_unique_best_attempts`, `selected.sort`, `len`, `list`, `score_tuple`, `item.get`

### `OptimizerSearchState.compact_trace()` [公开]
- 位置：第 88-89 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:226` [Service] `improvement_trace=state.compact_trace(limit=200),`
  - `core/services/scheduler/run/schedule_optimizer.py:253` [Service] `improvement_trace=state.compact_trace(limit=200),`
- **被调用者**（1 个）：`list`

## core/services/scheduler/run/schedule_optimizer.py（Service 层）

### `_run_local_search()` [私有]
- 位置：第 51-55 行
- 参数：无
- 返回类型：无注解

### `_default_runtime()` [私有]
- 位置：第 58-66 行
- 参数：无
- 返回类型：Name(id='OptimizerRuntime', ctx=Load())

### `optimize_schedule()` [公开]
- 位置：第 69-258 行
- 参数：无
- 返回类型：Name(id='OptimizationOutcome', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（31 个）：`ensure_optimizer_config_snapshot`, `_coerce_seed_results`, `runtime.scheduler_factory`, `resolve_optimizer_config`, `build_normalized_batches_map`, `OptimizerSearchState`, `runtime.clock`, `runtime.run_ortools_warmstart`, `runtime.run_multi_start`, `runtime.run_local_search`, `OptimizationOutcome`, `_default_runtime`, `build_batch_sort_inputs`, `StrategyFactory.create`, `float`

## core/services/scheduler/run/schedule_optimizer_steps.py（Service 层）

### `SchedulerLike.schedule()` [公开]
- 位置：第 22-23 行
- 参数：无
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）

### `_step_config_snapshot()` [私有]
- 位置：第 26-29 行
- 参数：cfg
- 返回类型：Name(id='Any', ctx=Load())

### `_schedule_supports_strict_mode()` [私有]
- 位置：第 32-44 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_is_unexpected_strict_mode_type_error()` [私有]
- 位置：第 47-49 行
- 参数：exc
- 返回类型：Name(id='bool', ctx=Load())

### `_schedule_with_optional_strict_mode()` [私有]
- 位置：第 52-64 行
- 参数：scheduler
- 返回类型：无注解

### `_solve_ortools_order()` [私有]
- 位置：第 67-94 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_ortools_strategy_params()` [私有]
- 位置：第 97-100 行
- 参数：snapshot
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_evaluate_ortools_candidate()` [私有]
- 位置：第 103-152 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_append_ortools_attempt()` [私有]
- 位置：第 155-171 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_append_ortools_trace()` [私有]
- 位置：第 174-196 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_record_ortools_failure()` [私有]
- 位置：第 199-208 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_run_ortools_warmstart()` [私有]
- 位置：第 211-282 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_dispatch_rules_for_mode()` [私有]
- 位置：第 285-288 行
- 参数：dispatch_mode, dispatch_rule_cfg, valid_dispatch_rules
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_resolve_multi_start_strategy_params()` [私有]
- 位置：第 291-300 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_get_cached_multi_start_order()` [私有]
- 位置：第 303-313 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_evaluate_multi_start_candidate()` [私有]
- 位置：第 316-365 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_run_multi_start()` [私有]
- 位置：第 368-471 行
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
- **调用者**（86 处）：
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
  - `core/services/scheduler/run/schedule_optimizer_steps.py:168` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:194` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:453` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:468` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/optimizer_local_search.py:138` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/run/optimizer_local_search.py:152` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/summary/schedule_summary.py:83` [Service] `return snapshot.to_dict().get(str(key or "").strip())`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:31` [Service] `).to_dict()`
  - `core/services/scheduler/summary/schedule_summary_assembly.py:225` [Service] `"metrics": ctx.best_metrics.to_dict() if ctx.best_metrics is not None else None,`
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
- 位置：第 164-183 行
- 参数：optimizer_outcome
- 返回类型：Name(id='_NormalizedOptimizerOutcome', ctx=Load())

### `_merge_summary_warnings()` [私有]
- 位置：第 186-217 行
- 参数：summary, algo_warnings
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `orchestrate_schedule_run()` [公开]
- 位置：第 220-324 行
- 参数：svc
- 返回类型：Name(id='ScheduleOrchestrationOutcome', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:264` [Service] `orchestration = orchestrate_schedule_run(`
- **被调用者**（14 个）：`_normalize_optimizer_outcome`, `build_validated_schedule_payload`, `_merge_summary_warnings`, `SummaryBuildContext`, `build_result_summary_fn`, `ScheduleOrchestrationOutcome`, `optimize_schedule_fn`, `list`, `transaction`, `int`, `set`, `allocate_next_version`, `_build_summary_contract`, `bool`

## core/services/scheduler/run/schedule_seed_contracts.py（Service 层）

### `_raise_invalid_seed_results_error()` [私有]
- 位置：第 11-17 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_seed_result_sample()` [私有]
- 位置：第 20-30 行
- 参数：item
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_coerce_seed_time_range()` [私有]
- 位置：第 33-44 行
- 参数：item
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `coerce_seed_result_item()` [公开]
- 位置：第 47-62 行
- 参数：item
- 返回类型：Name(id='ScheduleResult', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`_coerce_seed_time_range`, `ScheduleResult`, `isinstance`, `TypeError`, `int`, `str`, `item.get`, `type`

### `coerce_seed_results()` [公开]
- 位置：第 65-89 行
- 参数：seed_results
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`enumerate`, `increment_counter`, `optimizer_algo_stats.setdefault`, `list`, `_raise_invalid_seed_results_error`, `seed_sr_list.append`, `coerce_seed_result_item`, `len`, `invalid_seed_samples.append`, `int`, `str`, `_seed_result_sample`

## core/services/scheduler/summary/optimizer_public_summary.py（Service 层）

### `_project_attempts()` [私有]
- 位置：第 21-34 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `project_public_algo_summary()` [公开]
- 位置：第 37-46 行
- 参数：algo
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/services/scheduler/summary/schedule_summary_assembly.py:273` [Service] `public_algo, optimizer_diagnostics = project_public_algo_summary(_algo_dict(algo`
- **被调用者**（4 个）：`dict`, `_project_attempts`, `isinstance`, `public_algo.get`

## core/services/scheduler/summary/schedule_summary_assembly.py（Service 层）

### `_config_snapshot_dict()` [私有]
- 位置：第 26-31 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_comparison_metric()` [私有]
- 位置：第 34-35 行
- 参数：objective_name
- 返回类型：Name(id='str', ctx=Load())

### `_best_score_schema()` [私有]
- 位置：第 38-39 行
- 参数：objective_name
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_finish_time_by_batch()` [私有]
- 位置：第 42-54 行
- 参数：results
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_record_invalid_due()` [私有]
- 位置：第 57-67 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_build_overdue_items()` [私有]
- 位置：第 70-127 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_algo_downtime_dict()` [私有]
- 位置：第 130-140 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_input_contract_dict()` [私有]
- 位置：第 143-149 行
- 参数：input_state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_freeze_window_dict()` [私有]
- 位置：第 152-176 行
- 参数：state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_resource_pool_dict()` [私有]
- 位置：第 179-191 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_warning_pipeline_dict()` [私有]
- 位置：第 194-209 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_algo_dict()` [私有]
- 位置：第 212-254 行
- 参数：state
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_result_summary_obj()` [私有]
- 位置：第 257-310 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

---
- 分析函数/方法数：83
- 找到调用关系：106 处
- 跨层边界风险：2 项
