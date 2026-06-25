# 引用链追踪报告（深度 Review 辅助）

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/services/scheduler/schedule_service.py（Service 层）

### `_normalized_status_text()` [私有]
- 位置：第 38-39 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_get_snapshot_with_strict_mode()` [私有]
- 位置：第 42-43 行
- 参数：cfg_svc
- 返回类型：Name(id='Any', ctx=Load())

### `ScheduleService.__init__()` [私有]
- 位置：第 54-71 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ScheduleService._normalize_text()` [私有]
- 位置：第 77-78 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `ScheduleService._is_reschedulable_operation()` [私有]
- 位置：第 81-83 行
- 参数：op
- 返回类型：Name(id='bool', ctx=Load())

### `ScheduleService._normalize_float()` [私有]
- 位置：第 86-87 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `ScheduleService._get_batch_or_raise()` [私有]
- 位置：第 89-93 行
- 参数：batch_id
- 返回类型：Name(id='Batch', ctx=Load())

### `ScheduleService._get_op_or_raise()` [私有]
- 位置：第 95-107 行
- 参数：op_id
- 返回类型：Name(id='BatchOperation', ctx=Load())

### `ScheduleService._get_template_and_group_for_op()` [私有]
- 位置：第 109-110 行
- 参数：op
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `ScheduleService._format_dt()` [私有]
- 位置：第 113-114 行
- 参数：dt
- 返回类型：Name(id='str', ctx=Load())

### `ScheduleService._normalize_datetime()` [私有]
- 位置：第 117-131 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `ScheduleService.list_batch_operations()` [公开]
- 位置：第 136-137 行
- 参数：batch_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_batch_detail.py:390` [Route] `ops = sch_svc.list_batch_operations(batch_id=b.batch_id)`
- **被调用者**（1 个）：`op_edit.list_batch_operations`

### `ScheduleService.get_operation()` [公开]
- 位置：第 139-140 行
- 参数：op_id
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（4 处）：
  - `web/routes/domains/scheduler/scheduler_ops.py:60` [Route] `op = sch_svc.get_operation(op_id)`
  - `core/services/scheduler/operation_edit_service.py:48` [Service] `op = get_operation(svc, op_id)`
  - `core/services/scheduler/operation_edit_service.py:211` [Service] `op = get_operation(svc, op_id)`
  - `core/services/scheduler/operation_edit_service.py:262` [Service] `op = get_operation(svc, op_id)`
- **被调用者**（1 个）：`op_edit.get_operation`

### `ScheduleService.get_external_merge_hint_for_op()` [公开]
- 位置：第 142-146 行
- 参数：op
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（1 处）：
  - `core/services/scheduler/operation_edit_service.py:49` [Service] `return get_external_merge_hint_for_op(svc, op)`
- **被调用者**（1 个）：`op_edit.get_external_merge_hint_for_op`

### `ScheduleService.get_external_merge_hint()` [公开]
- 位置：第 148-152 行
- 参数：op_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`op_edit.get_external_merge_hint`

### `ScheduleService.update_internal_operation()` [公开]
- 位置：第 157-174 行
- 参数：op_id, machine_id, operator_id, setup_hours, unit_hours, status
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_ops.py:67` [Route] `sch_svc.update_internal_operation(`
- **被调用者**（1 个）：`op_edit.update_internal_operation`

### `ScheduleService.update_external_operation()` [公开]
- 位置：第 179-192 行
- 参数：op_id, supplier_id, ext_days, status
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/domains/scheduler/scheduler_ops.py:79` [Route] `sch_svc.update_external_operation(op_id=op_id, supplier_id=supplier_id, ext_days`
- **被调用者**（1 个）：`op_edit.update_external_operation`

### `ScheduleService.run_schedule()` [公开]
- 位置：第 197-224 行
- 参数：batch_ids, start_dt, end_date, created_by, simulate, enforce_ready, strict_mode, run_time_budget_seconds
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（3 处）：
  - `web/routes/domains/scheduler/scheduler_week_plan.py:452` [Route] `result = sch_svc.run_schedule(`
  - `web/routes/domains/scheduler/scheduler_run.py:51` [Route] `result = sch_svc.run_schedule(`
  - `tools/capture_networkx_phase0_baseline.py:165` [Tool] `ret = svc.run_schedule(`
- **被调用者**（4 个）：`_RUN_SCHEDULE_LOCK.acquire`, `ValidationError`, `self._run_schedule_impl`, `_RUN_SCHEDULE_LOCK.release`

### `ScheduleService._run_schedule_impl()` [私有]
- 位置：第 226-359 行
- 参数：batch_ids, start_dt, end_date, created_by, simulate, enforce_ready, strict_mode, run_time_budget_seconds
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

## core/services/scheduler/run/schedule_orchestrator.py（Service 层）

### `_normalize_summary_merge_error()` [私有]
- 位置：第 24-30 行
- 参数：reason
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_normalize_optimizer_outcome()` [私有]
- 位置：第 78-97 行
- 参数：optimizer_outcome
- 返回类型：Name(id='_NormalizedOptimizerOutcome', ctx=Load())

### `_normalize_candidate_plan()` [私有]
- 位置：第 100-115 行
- 参数：candidate_plan
- 返回类型：Name(id='_NormalizedOptimizerOutcome', ctx=Load())

### `_candidate_comparison_enabled()` [私有]
- 位置：第 118-119 行
- 参数：cfg
- 返回类型：Name(id='bool', ctx=Load())

### `_candidate_weight_count()` [私有]
- 位置：第 122-124 行
- 参数：cfg
- 返回类型：Name(id='int', ctx=Load())

### `_candidate_selection_policy()` [私有]
- 位置：第 127-128 行
- 参数：cfg
- 返回类型：Name(id='str', ctx=Load())

### `_candidate_overdue_tolerance_count()` [私有]
- 位置：第 131-133 行
- 参数：cfg
- 返回类型：Name(id='int', ctx=Load())

### `_candidate_tardiness_tolerance_ratio()` [私有]
- 位置：第 136-138 行
- 参数：cfg
- 返回类型：Name(id='float', ctx=Load())

### `_run_optimizer_once()` [私有]
- 位置：第 141-175 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_graph_analysis_for_summary()` [私有]
- 位置：第 178-191 行
- 参数：candidate_comparison, adopted_plan
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_merge_summary_warnings()` [私有]
- 位置：第 194-225 行
- 参数：summary, algo_warnings
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_run_plan_selection()` [私有]
- 位置：第 228-256 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_allowed_schedule_output_op_ids()` [私有]
- 位置：第 259-263 行
- 参数：schedule_input
- 返回类型：无注解

### `_payload_validation_operations()` [私有]
- 位置：第 266-272 行
- 参数：schedule_input
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `orchestrate_schedule_run()` [公开]
- 位置：第 275-406 行
- 参数：svc
- 返回类型：Name(id='ScheduleOrchestrationOutcome', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:319` [Service] `orchestration = orchestrate_schedule_run(`
- **被调用者**（21 个）：`_run_plan_selection`, `_allowed_schedule_output_op_ids`, `build_validated_schedule_payload`, `_merge_summary_warnings`, `callable`, `_build_outcome`, `list`, `SummaryBuildContext`, `build_result_summary_fn`, `ScheduleOrchestrationOutcome`, `before_version_allocate_fn`, `int`, `bool`, `_payload_validation_operations`, `set`

## core/services/scheduler/run/schedule_optimizer.py（Service 层）

### `_run_local_search()` [私有]
- 位置：第 52-57 行
- 参数：无
- 返回类型：无注解

### `_default_runtime()` [私有]
- 位置：第 60-68 行
- 参数：无
- 返回类型：Name(id='OptimizerRuntime', ctx=Load())

### `optimize_schedule()` [公开]
- 位置：第 71-278 行
- 参数：无
- 返回类型：Name(id='OptimizationOutcome', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（32 个）：`ensure_optimizer_config_snapshot`, `_coerce_seed_results`, `runtime.scheduler_factory`, `resolve_optimizer_config`, `build_normalized_batches_map`, `OptimizerSearchState`, `runtime.clock`, `runtime.run_ortools_warmstart`, `runtime.run_multi_start`, `runtime.run_local_search`, `OptimizationOutcome`, `_default_runtime`, `ValidationError`, `optimizer_cfg.dispatch_modes`, `build_batch_sort_inputs`

## core/algorithms/greedy/scheduler.py（Algorithm 层）

### `GreedyScheduler.__init__()` [私有]
- 位置：第 64-68 行
- 参数：calendar_service, config_service, logger
- 返回类型：无注解

### `GreedyScheduler.schedule()` [公开]
- 位置：第 70-142 行
- 参数：operations, batches, strategy, strategy_params, start_dt, end_date, machine_downtimes, batch_order_override, seed_results, dispatch_mode, dispatch_rule, resource_pool, readiness_gate_enabled, strict_mode, graph_ready_context
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el
- **调用者**（5 处）：
  - `core/services/scheduler/run/schedule_signature_support.py:121` [Service] `return scheduler.schedule(**kwargs)`
  - `core/services/scheduler/run/schedule_signature_support.py:128` [Service] `return scheduler.schedule(**retry_kwargs)`
  - `core/services/scheduler/run/schedule_signature_support.py:160` [Service] `return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))`
  - `core/services/scheduler/run/schedule_signature_support.py:162` [Service] `return scheduler.schedule(**kwargs)`
  - `core/services/scheduler/run/schedule_signature_support.py:165` [Service] `return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))`
- **被调用者**（16 个）：`datetime.now`, `self._reset_algo_stats`, `self._resolve_params`, `build_normalized_batches_map`, `_normalize_machine_downtimes`, `_build_batch_order`, `_normalize_seed_inputs`, `_sorted_unseeded_operations`, `_prepare_run_state`, `ScheduleRunContext.from_legacy_scheduler`, `self._log_start`, `_run_dispatch`, `_build_summary`, `info`, `bool`

### `GreedyScheduler._reset_algo_stats()` [私有]
- 位置：第 144-146 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `GreedyScheduler._resolve_params()` [私有]
- 位置：第 148-151 行
- 参数：无
- 返回类型：无注解

### `GreedyScheduler._log_start()` [私有]
- 位置：第 153-156 行
- 参数：无
- 返回类型：Constant(value=None)

### `GreedyScheduler._schedule_external()` [私有]
- 位置：第 158-179 行
- 参数：op, batch, batch_progress, external_group_cache, base_time, errors, end_dt_exclusive, strict_mode
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `GreedyScheduler._schedule_internal()` [私有]
- 位置：第 181-219 行
- 参数：op, batch, batch_progress, machine_timeline, operator_timeline, base_time, errors, end_dt_exclusive, machine_downtimes
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `GreedyScheduler._auto_assign_internal_resources()` [私有]
- 位置：第 221-254 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Subsc

### `GreedyScheduler._auto_assign_internal_resources_attempt()` [私有]
- 位置：第 256-289 行
- 参数：无
- 返回类型：无注解

### `_normalize_machine_downtimes()` [私有]
- 位置：第 292-299 行
- 参数：machine_downtimes
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Subsc

### `_build_batch_order()` [私有]
- 位置：第 302-324 行
- 参数：batches, params
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_normalize_seed_inputs()` [私有]
- 位置：第 327-332 行
- 参数：seed_results, operations
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_sorted_unseeded_operations()` [私有]
- 位置：第 335-342 行
- 参数：operations
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_drop_seeded_operations()` [私有]
- 位置：第 345-354 行
- 参数：operations, seed_op_ids
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_operation_op_id()` [私有]
- 位置：第 357-362 行
- 参数：op
- 返回类型：Name(id='int', ctx=Load())

### `_prepare_run_state()` [私有]
- 位置：第 365-384 行
- 参数：calendar
- 返回类型：Name(id='ScheduleRunState', ctx=Load())

### `_initialize_ready_progress()` [私有]
- 位置：第 387-392 行
- 参数：calendar
- 返回类型：Constant(value=None)

### `_apply_seed_results()` [私有]
- 位置：第 395-399 行
- 参数：无
- 返回类型：Constant(value=None)

### `_validate_seed_result()` [私有]
- 位置：第 402-411 行
- 参数：result
- 返回类型：Constant(value=None)

### `_freeze_seed_resources()` [私有]
- 位置：第 414-424 行
- 参数：state, result
- 返回类型：Constant(value=None)

### `_run_dispatch()` [私有]
- 位置：第 427-458 行
- 参数：ctx
- 返回类型：Constant(value=None)

### `_build_summary()` [私有]
- 位置：第 461-471 行
- 参数：无
- 返回类型：Name(id='ScheduleSummary', ctx=Load())

## core/algorithms/greedy/dispatch/sgs_graph.py（Algorithm 层）

### `_op_id()` [私有]
- 位置：第 12-13 行
- 参数：op
- 返回类型：Name(id='int', ctx=Load())

### `_is_graph_like()` [私有]
- 位置：第 16-17 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())

### `_graph_ready_op_id_set()` [私有]
- 位置：第 20-30 行
- 参数：value
- 返回类型：Name(id='set', ctx=Load())

### `_prepare_graph_ready_state()` [私有]
- 位置：第 33-101 行
- 参数：graph_ready_context
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Subsc

### `_graph_score_enabled()` [私有]
- 位置：第 104-107 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())

### `_graph_priority_key_number()` [私有]
- 位置：第 110-116 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())

### `_graph_priority_key_map()` [私有]
- 位置：第 119-136 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_graph_sort_key_map()` [私有]
- 位置：第 139-161 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_normalize_link_map()` [私有]
- 位置：第 164-178 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_validate_graph_ready_links()` [私有]
- 位置：第 181-211 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_validate_link_scope()` [私有]
- 位置：第 214-223 行
- 参数：无
- 返回类型：Constant(value=None)

### `_initialize_graph_ready_frontier()` [私有]
- 位置：第 226-241 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_collect_candidates()` [私有]
- 位置：第 244-268 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `_ensure_graph_ready_complete()` [私有]
- 位置：第 271-280 行
- 参数：无
- 返回类型：Constant(value=None)

### `_block_graph_operation()` [私有]
- 位置：第 283-302 行
- 参数：graph_state, op_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_mark_graph_operation_completed()` [私有]
- 位置：第 305-320 行
- 参数：graph_state, op_id
- 返回类型：Constant(value=None)

### `_batch_failed_op_ids()` [私有]
- 位置：第 323-326 行
- 参数：batch_id, next_idx, ops_by_batch
- 返回类型：Name(id='set', ctx=Load())

### `_graph_op_label()` [私有]
- 位置：第 329-334 行
- 参数：graph_state, op_id
- 返回类型：Name(id='str', ctx=Load())

### `_record_graph_blocked_operations()` [私有]
- 位置：第 337-354 行
- 参数：state
- 返回类型：Name(id='int', ctx=Load())

## core/services/scheduler/run/schedule_graph_report.py（Service 层）

### `_elapsed_ms()` [私有]
- 位置：第 70-71 行
- 参数：started
- 返回类型：Name(id='int', ctx=Load())

### `_graph_analysis_mode()` [私有]
- 位置：第 74-78 行
- 参数：cfg
- 返回类型：Name(id='str', ctx=Load())

### `_graph_block_on_cycle()` [私有]
- 位置：第 81-85 行
- 参数：cfg
- 返回类型：Name(id='str', ctx=Load())

### `maybe_analyze_schedule_graph()` [公开]
- 位置：第 88-92 行
- 参数：schedule_input
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`prepare_schedule_graph_for_dispatch`

### `make_cached_graph_preparation_fn()` [公开]
- 位置：第 95-107 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Callable', ctx=Load()), slice=Tuple
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_candidate_runner.py:126` [Service] `prepare_graph = prepare_graph_fn if prepare_graph_fn is not None else make_cache`
- **被调用者**（1 个）：`prepare_schedule_graph_for_dispatch`

### `prepare_schedule_graph_for_dispatch()` [公开]
- 位置：第 110-148 行
- 参数：schedule_input
- 返回类型：Name(id='ScheduleGraphDispatchPreparation', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_orchestrator.py:150` [Service] `graph_preparation = prepare_schedule_graph_for_dispatch(schedule_input)`
- **被调用者**（5 个）：`_graph_analysis_mode`, `_graph_block_on_cycle`, `_build_schedule_graph_analysis_projection`, `_enforce_graph_dispatch_policy`, `ScheduleGraphDispatchPreparation`

### `_build_schedule_graph_analysis_projection()` [私有]
- 位置：第 151-260 行
- 参数：schedule_input
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_format_cycle_error_message()` [私有]
- 位置：第 263-269 行
- 参数：diagnostics
- 返回类型：Name(id='str', ctx=Load())

### `_cycle_error_details()` [私有]
- 位置：第 272-282 行
- 参数：diagnostics
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_enforce_graph_dispatch_policy()` [私有]
- 位置：第 285-310 行
- 参数：无
- 返回类型：Constant(value=None)

### `_graph_unavailable_projection()` [私有]
- 位置：第 313-337 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_graph_contract_error_projection()` [私有]
- 位置：第 340-366 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_truncated()` [私有]
- 位置：第 369-370 行
- 参数：values, limit
- 返回类型：Name(id='bool', ctx=Load())

### `_sample()` [私有]
- 位置：第 373-374 行
- 参数：values, limit
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_project_graph_analysis_payload()` [私有]
- 位置：第 377-447 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

---
- 分析函数/方法数：93
- 找到调用关系：19 处
- 跨层边界风险：0 项
