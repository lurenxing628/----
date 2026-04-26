# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ auto_assign_internal_resources() 返回 Optional，但 core/algorithms/greedy/scheduler.py:219 的调用者未做 None 检查
- ⚠ auto_assign_internal_resources() 返回 Optional，但 core/algorithms/greedy/dispatch/sgs_scoring.py:255 的调用者未做 None 检查
- ⚠ schedule_internal_operation() 返回 Optional，但 core/algorithms/greedy/run_context.py:55 的调用者未做 None 检查
- ⚠ schedule_internal_operation() 返回 Optional，但 core/algorithms/greedy/scheduler.py:181 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/algorithms/greedy/algo_stats.py（Algorithm 层）

### `_empty_stats()` [私有]
- 位置：第 11-12 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `make_algo_stats()` [公开]
- 位置：第 15-16 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/algorithms/greedy/scheduler.py:67` [Algorithm] `self._last_algo_stats = make_algo_stats()`
  - `core/algorithms/greedy/scheduler.py:126` [Algorithm] `self._last_algo_stats = make_algo_stats()`
- **被调用者**（1 个）：`_empty_stats`

### `ensure_algo_stats()` [公开]
- 位置：第 19-35 行
- 参数：target
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/algorithms/greedy/run_context.py:23` [Algorithm] `algo_stats = ensure_algo_stats(scheduler)`
  - `core/algorithms/greedy/scheduler.py:127` [Algorithm] `return ensure_algo_stats(self._last_algo_stats)`
- **被调用者**（4 个）：`isinstance`, `getattr`, `stats.get`, `_empty_stats`

### `snapshot_algo_stats()` [公开]
- 位置：第 38-54 行
- 参数：target
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:216` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:138` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:351` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/run/optimizer_local_search.py:99` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
- **被调用者**（8 个）：`ensure_algo_stats`, `deepcopy`, `_empty_stats`, `stats.get`, `isinstance`, `dict`, `part.items`, `str`

### `increment_counter()` [公开]
- 位置：第 57-74 行
- 参数：target, key, amount
- 返回类型：Constant(value=None, kind=None)
- **调用者**（23 处）：
  - `core/services/scheduler/run/schedule_optimizer_steps.py:198` [Service] `increment_counter(optimizer_algo_stats if isinstance(optimizer_algo_stats, dict)`
  - `core/services/scheduler/run/optimizer_config.py:113` [Service] `increment_counter(optimizer_algo_stats, counter_key, bucket="param_fallbacks")`
  - `core/services/scheduler/run/schedule_seed_contracts.py:81` [Service] `increment_counter(optimizer_algo_stats, "optimizer_seed_result_invalid_count", i`
  - `core/algorithms/greedy/internal_operation.py:84` [Algorithm] `increment_counter(algo_stats, "internal_efficiency_fallback_count")`
  - `core/algorithms/greedy/internal_operation.py:112` [Algorithm] `increment_counter(algo_stats, "internal_missing_resource_without_auto_assign_cou`
  - `core/algorithms/greedy/internal_operation.py:116` [Algorithm] `increment_counter(algo_stats, "internal_auto_assign_attempt_count")`
  - `core/algorithms/greedy/internal_operation.py:132` [Algorithm] `increment_counter(algo_stats, "internal_auto_assign_success_count")`
  - `core/algorithms/greedy/internal_operation.py:134` [Algorithm] `increment_counter(algo_stats, "internal_auto_assign_failed_count")`
  - `core/algorithms/greedy/external_groups.py:32` [Algorithm] `increment_counter(scheduler, "legacy_external_days_defaulted_count", legacy_defa`
  - `core/algorithms/greedy/seed.py:171` [Algorithm] `increment_counter(algo_stats, "seed_op_id_backfilled_count", counters["backfille`
  - `core/algorithms/greedy/seed.py:172` [Algorithm] `increment_counter(algo_stats, "seed_invalid_dropped_count", counters["dropped_in`
  - `core/algorithms/greedy/seed.py:173` [Algorithm] `increment_counter(algo_stats, "seed_bad_time_dropped_count", counters["dropped_b`
  - `core/algorithms/greedy/seed.py:174` [Algorithm] `increment_counter(algo_stats, "seed_duplicate_dropped_count", counters["dropped_`
  - `core/algorithms/greedy/run_context.py:34` [Algorithm] `increment_counter(self.algo_stats, key, amount, bucket=bucket)`
  - `core/algorithms/greedy/auto_assign.py:31` [Algorithm] `count = (lambda key: None) if probe_only else (lambda key: increment_counter(sta`
  - `core/algorithms/greedy/schedule_params.py:173` [Algorithm] `increment_counter(`
  - `core/algorithms/greedy/schedule_params.py:234` [Algorithm] `increment_counter(algo_stats, "start_dt_parsed_count", bucket="param_fallbacks")`
  - `core/algorithms/greedy/schedule_params.py:240` [Algorithm] `increment_counter(algo_stats, "start_dt_default_now_count", bucket="param_fallba`
  - `core/algorithms/greedy/schedule_params.py:258` [Algorithm] `increment_counter(algo_stats, "end_date_ignored_count", bucket="param_fallbacks"`
  - `core/algorithms/greedy/schedule_params.py:407` [Algorithm] `increment_counter(`
  - `core/algorithms/greedy/scheduler.py:275` [Algorithm] `increment_counter(algo_stats, "seed_overlap_filtered_count", dropped)`
  - `core/algorithms/greedy/scheduler.py:304` [Algorithm] `increment_counter(algo_stats, "seed_missing_machine_id_count", state.missing_see`
  - `core/algorithms/greedy/scheduler.py:305` [Algorithm] `increment_counter(algo_stats, "seed_missing_operator_id_count", state.missing_se`
- **被调用者**（5 个）：`ensure_algo_stats`, `stats.get`, `isinstance`, `int`, `current_bucket.get`

### `merge_algo_stats()` [公开]
- 位置：第 77-84 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（5 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:216` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/run/schedule_optimizer.py:242` [Service] `algo_stats = merge_algo_stats(best_algo_stats) if isinstance(best_algo_stats, di`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:138` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:351` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/run/optimizer_local_search.py:99` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
- **被调用者**（4 个）：`_empty_stats`, `_merge_counter_buckets`, `_merge_sample_buckets`, `isinstance`

### `_merge_counter_buckets()` [私有]
- 位置：第 87-103 行
- 参数：merged, src
- 返回类型：Constant(value=None, kind=None)

### `_merge_sample_buckets()` [私有]
- 位置：第 106-121 行
- 参数：merged, src
- 返回类型：Constant(value=None, kind=None)

## core/algorithms/greedy/auto_assign.py（Algorithm 层）

### `auto_assign_internal_resources()` [公开]
- 位置：第 10-77 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（3 处）：
  - `core/algorithms/greedy/run_context.py:66` [Algorithm] `return auto_assign_internal_resources(*args, **call_kwargs)`
  - `core/algorithms/greedy/scheduler.py:219` [Algorithm] `return auto_assign_internal_resources(`
  - `core/algorithms/greedy/dispatch/sgs_scoring.py:255` [Algorithm] `chosen = ctx.auto_assign_internal_resources(`
- **被调用者**（11 个）：`_fixed_resource_inputs`, `_coerce_resource_pool`, `_resolve_machine_candidates`, `_validated_total_hours`, `_sort_machine_candidates`, `_choose_best_pair`, `getattr`, `count`, `increment_counter`, `strip`, `str`

### `_fixed_resource_inputs()` [私有]
- 位置：第 80-85 行
- 参数：op
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_coerce_resource_pool()` [私有]
- 位置：第 88-96 行
- 参数：resource_pool
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_dict_part()` [私有]
- 位置：第 99-101 行
- 参数：source, key
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_resolve_machine_candidates()` [私有]
- 位置：第 104-123 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_machines_for_fixed_operator()` [私有]
- 位置：第 126-134 行
- 参数：fixed_operator
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_filter_machines_by_op_type()` [私有]
- 位置：第 137-144 行
- 参数：candidates
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_validated_total_hours()` [私有]
- 位置：第 147-152 行
- 参数：op, batch
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_sort_machine_candidates()` [私有]
- 位置：第 155-169 行
- 参数：candidates
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_choose_best_pair()` [私有]
- 位置：第 172-226 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_operator_candidates_for_machine()` [私有]
- 位置：第 229-233 行
- 参数：machine_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_sort_operator_candidates()` [私有]
- 位置：第 236-243 行
- 参数：candidates
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_pair_score()` [私有]
- 位置：第 246-285 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_pair_rank()` [私有]
- 位置：第 288-292 行
- 参数：pool, operator_id, machine_id
- 返回类型：Name(id='int', ctx=Load())

## core/algorithms/greedy/dispatch/batch_order.py（Algorithm 层）

### `dispatch_batch_order()` [公开]
- 位置：第 18-76 行
- 参数：context
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:348` [Algorithm] `dispatch_batch_order(`
- **被调用者**（4 个）：`ensure_run_context`, `_coerce_state`, `_dispatch_one`, `bool`

### `_coerce_state()` [私有]
- 位置：第 79-114 行
- 参数：无
- 返回类型：Name(id='ScheduleRunState', ctx=Load())

### `_dispatch_one()` [私有]
- 位置：第 117-153 行
- 参数：ctx
- 返回类型：Constant(value=None, kind=None)

### `_validate_batch()` [私有]
- 位置：第 156-164 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `_schedule_op()` [私有]
- 位置：第 167-207 行
- 参数：ctx
- 返回类型：无注解

### `_validate_strict_internal_input()` [私有]
- 位置：第 210-216 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_record_dispatch_exception()` [私有]
- 位置：第 219-225 行
- 参数：ctx
- 返回类型：Constant(value=None, kind=None)

## core/algorithms/greedy/dispatch/sgs.py（Algorithm 层）

### `_score_internal_candidate()` [私有]
- 位置：第 27-32 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_pick_best_candidate()` [私有]
- 位置：第 35-39 行
- 参数：scored_candidates
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `dispatch_sgs()` [公开]
- 位置：第 42-109 行
- 参数：context
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:361` [Algorithm] `dispatch_sgs(`
- **被调用者**（10 个）：`ensure_run_context`, `_coerce_state`, `_group_sgs_ops`, `sorted`, `_average_proc_hours`, `_run_sgs_loop`, `list`, `bool`, `ops_by_batch.keys`, `batch_order.get`

### `_group_sgs_ops()` [私有]
- 位置：第 112-128 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_average_proc_hours()` [私有]
- 位置：第 131-141 行
- 参数：ctx
- 返回类型：Name(id='float', ctx=Load())

### `_append_proc_sample()` [私有]
- 位置：第 144-149 行
- 参数：samples
- 返回类型：Constant(value=None, kind=None)

### `_run_sgs_loop()` [私有]
- 位置：第 152-206 行
- 参数：ctx, state, ops_by_batch, batch_ids, next_idx, batches, batch_order, dispatch_rule, end_dt_exclusive, machine_downtimes, auto_assign_enabled, resource_pool, strict_mode, avg_proc_hours
- 返回类型：Constant(value=None, kind=None)

### `_score_candidates()` [私有]
- 位置：第 209-244 行
- 参数：ctx, state, candidates, batches, batch_order, dispatch_rule, end_dt_exclusive, machine_downtimes, auto_assign_enabled, resource_pool, strict_mode, avg_proc_hours
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_score_candidate()` [私有]
- 位置：第 247-293 行
- 参数：ctx, state, op, batch, batch_id, batch_order, dispatch_rule, end_dt_exclusive, machine_downtimes, auto_assign_enabled, resource_pool, strict_mode, avg_proc_hours
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_dispatch_selected()` [私有]
- 位置：第 296-332 行
- 参数：ctx, state, op, batch_id, batches, next_idx, ops_by_batch, end_dt_exclusive, machine_downtimes, auto_assign_enabled, resource_pool, strict_mode
- 返回类型：Constant(value=None, kind=None)

### `_remaining_failed()` [私有]
- 位置：第 335-337 行
- 参数：batch_id, next_idx, ops_by_batch
- 返回类型：Name(id='int', ctx=Load())

## core/algorithms/greedy/dispatch/sgs_scoring.py（Algorithm 层）

### `_parse_due_date()` [私有]
- 位置：第 24-25 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_dispatch_key()` [私有]
- 位置：第 28-61 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_collect_sgs_candidates()` [私有]
- 位置：第 64-77 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_score_external_candidate()` [私有]
- 位置：第 80-116 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_score_internal_candidate()` [私有]
- 位置：第 119-170 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_candidate_meta()` [私有]
- 位置：第 173-181 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_external_candidate_window()` [私有]
- 位置：第 184-202 行
- 参数：ctx, state
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_parse_external_days()` [私有]
- 位置：第 205-225 行
- 参数：ctx, value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_scoring_total_hours()` [私有]
- 位置：第 228-235 行
- 参数：ctx
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_scoring_resources()` [私有]
- 位置：第 238-274 行
- 参数：ctx
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_estimate_scoring_slot()` [私有]
- 位置：第 277-308 行
- 参数：ctx, state, op, batch, meta, machine_id, operator_id, end_dt_exclusive, machine_downtimes, total_hours, estimate_slot
- 返回类型：无注解

### `_unscorable_key()` [私有]
- 位置：第 311-334 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_unscorable_dispatch_key()` [私有]
- 位置：第 337-373 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_fallback_proc_hours()` [私有]
- 位置：第 376-380 行
- 参数：avg_proc_hours
- 返回类型：Name(id='float', ctx=Load())

### `_fallback_estimate_start()` [私有]
- 位置：第 383-398 行
- 参数：ctx, state, est_start, proc_hours, priority, machine_id, operator_id, machine_downtimes
- 返回类型：Name(id='datetime', ctx=Load())

## core/algorithms/greedy/internal_operation.py（Algorithm 层）

### `schedule_internal_operation()` [公开]
- 位置：第 15-85 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（2 处）：
  - `core/algorithms/greedy/run_context.py:55` [Algorithm] `return schedule_internal_operation(`
  - `core/algorithms/greedy/scheduler.py:181` [Algorithm] `return schedule_internal_operation(`
- **被调用者**（10 个）：`normalize_text_id`, `_resolve_internal_resources`, `_estimate_internal`, `occupy_resource`, `getattr`, `errors.append`, `increment_counter`, `_build_internal_result`, `bool`, `_window_blocked_error`

### `_resolve_internal_resources()` [私有]
- 位置：第 88-136 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_estimate_internal()` [私有]
- 位置：第 139-180 行
- 参数：无
- 返回类型：无注解

### `_window_blocked_error()` [私有]
- 位置：第 183-188 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_build_internal_result()` [私有]
- 位置：第 191-203 行
- 参数：无
- 返回类型：Name(id='ScheduleResult', ctx=Load())

## core/algorithms/greedy/internal_slot.py（Algorithm 层）

### `_read_legacy_field()` [私有]
- 位置：第 29-34 行
- 参数：obj, field
- 返回类型：Name(id='Any', ctx=Load())

### `_coerce_legacy_hours_value()` [私有]
- 位置：第 37-52 行
- 参数：raw_value
- 返回类型：Name(id='float', ctx=Load())

### `validate_internal_hours()` [公开]
- 位置：第 55-70 行
- 参数：op, batch
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（4 处）：
  - `core/algorithms/greedy/auto_assign.py:149` [Algorithm] `return validate_internal_hours(op, batch)`
  - `core/algorithms/greedy/dispatch/sgs_scoring.py:230` [Algorithm] `return validate_internal_hours(op, batch)`
  - `core/algorithms/greedy/dispatch/sgs.py:146` [Algorithm] `samples.append(validate_internal_hours(op, batch))`
  - `core/algorithms/greedy/dispatch/batch_order.py:214` [Algorithm] `validate_internal_hours(op, batch)`
- **被调用者**（5 个）：`_read_legacy_field`, `_coerce_legacy_hours_value`, `float`, `ValueError`, `math.isfinite`

### `raise_strict_internal_hours_validation()` [公开]
- 位置：第 73-83 行
- 参数：op, batch, exc
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `core/algorithms/greedy/internal_operation.py:175` [Algorithm] `raise_strict_internal_hours_validation(op, batch, exc)`
  - `core/algorithms/greedy/dispatch/batch_order.py:216` [Algorithm] `raise_strict_internal_hours_validation(op, batch, exc)`
- **被调用者**（4 个）：`_internal_hour_fields`, `ValidationError`, `_raise_if_invalid_strict_number`, `str`

### `_internal_hour_fields()` [私有]
- 位置：第 86-91 行
- 参数：op, batch
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_raise_if_invalid_strict_number()` [私有]
- 位置：第 94-102 行
- 参数：field, raw_value
- 返回类型：Constant(value=None, kind=None)

### `_resolve_efficiency()` [私有]
- 位置：第 105-117 行
- 参数：calendar
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_changeover_penalty()` [私有]
- 位置：第 120-129 行
- 参数：op, machine_id, last_op_type_by_machine
- 返回类型：Name(id='int', ctx=Load())

### `_abort_result()` [私有]
- 位置：第 132-149 行
- 参数：无
- 返回类型：Name(id='InternalSlotEstimate', ctx=Load())

### `estimate_internal_slot()` [公开]
- 位置：第 152-238 行
- 参数：无
- 返回类型：Name(id='InternalSlotEstimate', ctx=Load())
- **调用者**（2 处）：
  - `core/algorithms/greedy/internal_operation.py:158` [Algorithm] `estimate = estimate_internal_slot(`
  - `core/algorithms/greedy/auto_assign.py:266` [Algorithm] `estimate = estimate_internal_slot(`
- **被调用者**（17 个）：`getattr`, `_changeover_penalty`, `list`, `max`, `calendar.adjust_to_working_time`, `InternalSlotEstimate`, `validate_internal_hours`, `float`, `ValueError`, `_abort_result`, `_resolve_efficiency`, `bool`, `calendar.add_working_hours`, `math.isfinite`, `find_overlap_shift_end`

## core/algorithms/greedy/run_context.py（Algorithm 层）

### `ScheduleRunContext.from_legacy_scheduler()` [公开]
- 位置：第 22-31 行
- 参数：scheduler
- 返回类型：Name(id='ScheduleRunContext', ctx=Load())
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:106` [Algorithm] `ctx = ScheduleRunContext.from_legacy_scheduler(self)`
- **被调用者**（3 个）：`ensure_algo_stats`, `cls`, `getattr`

### `ScheduleRunContext.increment()` [公开]
- 位置：第 33-34 行
- 参数：key, amount
- 返回类型：Constant(value=None, kind=None)
- **调用者**（5 处）：
  - `core/algorithms/greedy/dispatch/sgs_scoring.py:97` [Algorithm] `ctx.increment("dispatch_sgs_external_duration_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs_scoring.py:152` [Algorithm] `ctx.increment("dispatch_sgs_missing_resource_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs_scoring.py:234` [Algorithm] `ctx.increment("dispatch_sgs_total_hours_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs_scoring.py:355` [Algorithm] `ctx.increment("dispatch_key_proc_hours_fallback_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:140` [Algorithm] `ctx.increment("dispatch_key_avg_proc_hours_fallback_count")`
- **被调用者**（1 个）：`increment_counter`

### `ScheduleRunContext.log_exception()` [公开]
- 位置：第 36-40 行
- 参数：message
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `core/algorithms/greedy/dispatch/sgs.py:331` [Algorithm] `ctx.log_exception(f"工序 {getattr(op, 'op_code', '-') or '-'} 排产异常")`
  - `core/algorithms/greedy/dispatch/batch_order.py:223` [Algorithm] `ctx.log_exception(f"工序 {op_code} 排产异常")`
- **被调用者**（1 个）：`exception`

### `ScheduleRunContext.schedule_external()` [公开]
- 位置：第 42-46 行
- 参数：无
- 返回类型：无注解
- **调用者**（2 处）：
  - `core/algorithms/greedy/scheduler.py:150` [Algorithm] `return schedule_external(`
  - `core/algorithms/greedy/dispatch/batch_order.py:181` [Algorithm] `return ctx.schedule_external(`
- **被调用者**（4 个）：`callable`, `dict`, `self.external_callback`, `_ScheduleFacade`

### `ScheduleRunContext.schedule_internal()` [公开]
- 位置：第 48-58 行
- 参数：无
- 返回类型：无注解
- **调用者**（1 处）：
  - `core/algorithms/greedy/dispatch/batch_order.py:192` [Algorithm] `return ctx.schedule_internal(`
- **被调用者**（5 个）：`callable`, `dict`, `call_kwargs.setdefault`, `schedule_internal_operation`, `self.internal_callback`

### `ScheduleRunContext.auto_assign_internal_resources()` [公开]
- 位置：第 60-66 行
- 参数：无
- 返回类型：无注解
- **调用者**（2 处）：
  - `core/algorithms/greedy/scheduler.py:219` [Algorithm] `return auto_assign_internal_resources(`
  - `core/algorithms/greedy/dispatch/sgs_scoring.py:255` [Algorithm] `chosen = ctx.auto_assign_internal_resources(`
- **被调用者**（4 个）：`callable`, `dict`, `call_kwargs.setdefault`, `self.auto_assign_callback`

### `ensure_run_context()` [公开]
- 位置：第 69-72 行
- 参数：candidate
- 返回类型：Name(id='ScheduleRunContext', ctx=Load())
- **调用者**（2 处）：
  - `core/algorithms/greedy/dispatch/sgs.py:70` [Algorithm] `ctx = ensure_run_context(context)`
  - `core/algorithms/greedy/dispatch/batch_order.py:44` [Algorithm] `ctx = ensure_run_context(context)`
- **被调用者**（2 个）：`isinstance`, `ScheduleRunContext.from_legacy_scheduler`

### `_ScheduleFacade.__init__()` [私有]
- 位置：第 76-78 行
- 参数：calendar, algo_stats
- 返回类型：Constant(value=None, kind=None)

## core/algorithms/greedy/run_state.py（Algorithm 层）

### `ScheduleRunState.from_legacy()` [公开]
- 位置：第 37-71 行
- 参数：无
- 返回类型：Name(id='ScheduleRunState', ctx=Load())
- **调用者**（1 处）：
  - `core/algorithms/greedy/dispatch/batch_order.py:99` [Algorithm] `return ScheduleRunState.from_legacy(`
- **被调用者**（4 个）：`max`, `cls`, `int`, `len`

### `ScheduleRunState.scheduled_count()` [公开]
- 位置：第 74-75 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`int`, `len`

### `ScheduleRunState.prev_end()` [公开]
- 位置：第 77-78 行
- 参数：batch_id
- 返回类型：Name(id='datetime', ctx=Load())
- **调用者**（1 处）：
  - `core/algorithms/greedy/dispatch/sgs_scoring.py:180` [Algorithm] `"prev_end": state.prev_end(batch_id),`
- **被调用者**（1 个）：`get`

### `ScheduleRunState.advance_batch()` [公开]
- 位置：第 80-83 行
- 参数：batch_id, end_time
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:314` [Algorithm] `state.advance_batch(batch_id, calendar.adjust_to_working_time(ready_start, prior`
- **被调用者**（3 个）：`max`, `get`, `isinstance`

### `ScheduleRunState.record_seed_result()` [公开]
- 位置：第 85-91 行
- 参数：result
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:321` [Algorithm] `state.record_seed_result(result)`
- **被调用者**（7 个）：`append`, `self.advance_batch`, `self._record_internal_usage`, `normalize_text_id`, `lower`, `self._record_missing_seed_resources`, `strip`

### `ScheduleRunState.record_dispatch_success()` [公开]
- 位置：第 93-96 行
- 参数：result
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `core/algorithms/greedy/dispatch/sgs.py:324` [Algorithm] `state.record_dispatch_success(result)`
  - `core/algorithms/greedy/dispatch/batch_order.py:147` [Algorithm] `state.record_dispatch_success(result)`
- **被调用者**（4 个）：`append`, `self.advance_batch`, `self._record_internal_usage`, `normalize_text_id`

### `ScheduleRunState.record_dispatch_failure()` [公开]
- 位置：第 98-101 行
- 参数：batch_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `core/algorithms/greedy/dispatch/sgs.py:327` [Algorithm] `state.record_dispatch_failure(batch_id, block=True, remaining_failed=_remaining_`
  - `core/algorithms/greedy/dispatch/batch_order.py:149` [Algorithm] `state.record_dispatch_failure(batch_id, block=True)`
- **被调用者**（3 个）：`max`, `add`, `int`

### `ScheduleRunState.seed_resource_warnings()` [公开]
- 位置：第 103-117 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:303` [Algorithm] `warnings.extend(state.seed_resource_warnings())`
- **被调用者**（2 个）：`join`, `warnings.append`

### `ScheduleRunState._record_internal_usage()` [私有]
- 位置：第 119-141 行
- 参数：result
- 返回类型：Constant(value=None, kind=None)

### `ScheduleRunState._record_missing_seed_resources()` [私有]
- 位置：第 143-152 行
- 参数：result
- 返回类型：Constant(value=None, kind=None)

## core/algorithms/greedy/scheduler.py（Algorithm 层）

### `GreedyScheduler.__init__()` [私有]
- 位置：第 63-67 行
- 参数：calendar_service, config_service, logger
- 返回类型：无注解

### `GreedyScheduler.schedule()` [公开]
- 位置：第 69-123 行
- 参数：operations, batches, strategy, strategy_params, start_dt, end_date, machine_downtimes, batch_order_override, seed_results, dispatch_mode, dispatch_rule, resource_pool, strict_mode
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（4 处）：
  - `core/services/scheduler/run/schedule_optimizer_steps.py:53` [Service] `return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:55` [Service] `return scheduler.schedule(**kwargs)`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:58` [Service] `return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:62` [Service] `return scheduler.schedule(**kwargs)`
- **被调用者**（16 个）：`datetime.now`, `self._reset_algo_stats`, `self._resolve_params`, `build_normalized_batches_map`, `_normalize_machine_downtimes`, `_build_batch_order`, `_normalize_seed_inputs`, `_sorted_unseeded_operations`, `_prepare_run_state`, `ScheduleRunContext.from_legacy_scheduler`, `self._log_start`, `_run_dispatch`, `_build_summary`, `info`, `bool`

### `GreedyScheduler._reset_algo_stats()` [私有]
- 位置：第 125-127 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `GreedyScheduler._resolve_params()` [私有]
- 位置：第 129-132 行
- 参数：无
- 返回类型：无注解

### `GreedyScheduler._log_start()` [私有]
- 位置：第 134-137 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `GreedyScheduler._schedule_external()` [私有]
- 位置：第 139-160 行
- 参数：op, batch, batch_progress, external_group_cache, base_time, errors, end_dt_exclusive, strict_mode
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `GreedyScheduler._schedule_internal()` [私有]
- 位置：第 162-200 行
- 参数：op, batch, batch_progress, machine_timeline, operator_timeline, base_time, errors, end_dt_exclusive, machine_downtimes
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `GreedyScheduler._auto_assign_internal_resources()` [私有]
- 位置：第 202-235 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_normalize_machine_downtimes()` [私有]
- 位置：第 238-245 行
- 参数：machine_downtimes
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_build_batch_order()` [私有]
- 位置：第 248-258 行
- 参数：batches, params
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_normalize_seed_inputs()` [私有]
- 位置：第 261-266 行
- 参数：seed_results, operations
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_sorted_unseeded_operations()` [私有]
- 位置：第 269-276 行
- 参数：operations
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_drop_seeded_operations()` [私有]
- 位置：第 279-288 行
- 参数：operations, seed_op_ids
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_safe_op_id()` [私有]
- 位置：第 291-295 行
- 参数：op
- 返回类型：Name(id='int', ctx=Load())

### `_prepare_run_state()` [私有]
- 位置：第 298-306 行
- 参数：calendar
- 返回类型：Name(id='ScheduleRunState', ctx=Load())

### `_initialize_ready_progress()` [私有]
- 位置：第 309-314 行
- 参数：calendar
- 返回类型：Constant(value=None, kind=None)

### `_apply_seed_results()` [私有]
- 位置：第 317-321 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_valid_seed_result()` [私有]
- 位置：第 324-330 行
- 参数：result
- 返回类型：Name(id='bool', ctx=Load())

### `_freeze_seed_resources()` [私有]
- 位置：第 333-343 行
- 参数：state, result
- 返回类型：Constant(value=None, kind=None)

### `_run_dispatch()` [私有]
- 位置：第 346-374 行
- 参数：ctx
- 返回类型：Constant(value=None, kind=None)

### `_build_summary()` [私有]
- 位置：第 377-387 行
- 参数：无
- 返回类型：Name(id='ScheduleSummary', ctx=Load())

## core/algorithms/greedy/seed.py（Algorithm 层）

### `normalize_seed_results()` [公开]
- 位置：第 11-51 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:264` [Algorithm] `normalized_seed, seed_op_ids, seed_warnings = normalize_seed_results(seed_result`
- **被调用者**（13 个）：`set`, `_build_operation_lookup`, `_record_seed_counters`, `warnings.extend`, `_identity_int`, `_normalize_one_seed_result`, `seed_op_ids.add`, `normalized.append`, `_seed_warnings`, `getattr`, `len`, `dup_samples.append`, `str`

### `_build_operation_lookup()` [私有]
- 位置：第 54-75 行
- 参数：operations
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_normalize_one_seed_result()` [私有]
- 位置：第 78-93 行
- 参数：seed_result
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_has_valid_time_window()` [私有]
- 位置：第 96-100 行
- 参数：seed_result
- 返回类型：Name(id='bool', ctx=Load())

### `_resolve_seed_op_id()` [私有]
- 位置：第 103-110 行
- 参数：seed_result
- 返回类型：Name(id='int', ctx=Load())

### `_with_seed_op_id()` [私有]
- 位置：第 113-129 行
- 参数：seed_result, op_id
- 返回类型：Name(id='ScheduleResult', ctx=Load())

### `_batch_seq_key()` [私有]
- 位置：第 132-135 行
- 参数：obj
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_identity_int()` [私有]
- 位置：第 138-151 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_invalid_identity_supplied()` [私有]
- 位置：第 154-167 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())

### `_record_seed_counters()` [私有]
- 位置：第 170-174 行
- 参数：algo_stats, counters
- 返回类型：Constant(value=None, kind=None)

### `_seed_warnings()` [私有]
- 位置：第 177-191 行
- 参数：counters, dup_samples
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

## core/algorithms/ordering.py（Algorithm 层）

### `normalize_text_id()` [公开]
- 位置：第 12-19 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（16 处）：
  - `core/algorithms/greedy/run_state.py:88` [Algorithm] `self.advance_batch(normalize_text_id(result.batch_id), result.end_time)`
  - `core/algorithms/greedy/run_state.py:95` [Algorithm] `self.advance_batch(normalize_text_id(result.batch_id), result.end_time)`
  - `core/algorithms/greedy/run_state.py:124` [Algorithm] `machine_id = normalize_text_id(result.machine_id)`
  - `core/algorithms/greedy/run_state.py:125` [Algorithm] `operator_id = normalize_text_id(result.operator_id)`
  - `core/algorithms/greedy/run_state.py:144` [Algorithm] `op_id = normalize_text_id(getattr(result, "op_id", "") or "?") or "?"`
  - `core/algorithms/greedy/run_state.py:145` [Algorithm] `if not normalize_text_id(result.machine_id):`
  - `core/algorithms/greedy/run_state.py:149` [Algorithm] `if not normalize_text_id(result.operator_id):`
  - `core/algorithms/greedy/internal_operation.py:36` [Algorithm] `bid = normalize_text_id(getattr(op, "batch_id", ""))`
  - `core/algorithms/greedy/internal_operation.py:107` [Algorithm] `machine_id = normalize_text_id(getattr(op, "machine_id", None))`
  - `core/algorithms/greedy/internal_operation.py:108` [Algorithm] `operator_id = normalize_text_id(getattr(op, "operator_id", None))`
  - `core/algorithms/greedy/internal_operation.py:133` [Algorithm] `return normalize_text_id(chosen[0]), normalize_text_id(chosen[1])`
  - `core/algorithms/greedy/scheduler.py:242` [Algorithm] `normalize_text_id(resource_id): sorted(list(segments or []), key=lambda segment:`
  - `core/algorithms/greedy/scheduler.py:244` [Algorithm] `if normalize_text_id(resource_id)`
  - `core/algorithms/greedy/scheduler.py:338` [Algorithm] `machine_id = normalize_text_id(result.machine_id)`
  - `core/algorithms/greedy/scheduler.py:339` [Algorithm] `operator_id = normalize_text_id(result.operator_id)`
  - `core/algorithms/greedy/dispatch/batch_order.py:130` [Algorithm] `batch_id = normalize_text_id(getattr(op, "batch_id", ""))`
- **被调用者**（2 个）：`strip`, `str`

### `resolve_batch_sort_batch_id()` [公开]
- 位置：第 22-26 行
- 参数：batch_key, batch
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`normalize_text_id`, `getattr`

### `build_normalized_batches_map()` [公开]
- 位置：第 29-42 行
- 参数：batches
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:105` [Service] `normalized_batches_for_sort = build_normalized_batches_map(batches)`
  - `core/algorithms/greedy/scheduler.py:100` [Algorithm] `batches = build_normalized_batches_map(batches, warnings=warnings)`
- **被调用者**（5 个）：`items`, `resolve_batch_sort_batch_id`, `str`, `warnings.append`, `normalized.get`

### `normalize_batch_order_override()` [公开]
- 位置：第 45-56 行
- 参数：batch_order_override, batches
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:249` [Algorithm] `override_order = normalize_batch_order_override(batch_order_override, batches)`
- **被调用者**（4 个）：`set`, `normalize_text_id`, `seen.add`, `override_order.append`

### `_parse_due_date_for_sort()` [私有]
- 位置：第 59-60 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_parse_ready_date_for_sort()` [私有]
- 位置：第 63-64 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `parse_ready_date_for_sort()` [公开]
- 位置：第 67-68 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:311` [Algorithm] `ready_date = parse_ready_date_for_sort(getattr(batch, "ready_date", None), stric`
- **被调用者**（2 个）：`_parse_ready_date_for_sort`, `bool`

### `_parse_created_at_for_sort()` [私有]
- 位置：第 71-74 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `build_batch_sort_inputs()` [公开]
- 位置：第 77-100 行
- 参数：batches
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:108` [Service] `batch_for_sort = build_batch_sort_inputs(`
  - `core/algorithms/greedy/scheduler.py:252` [Algorithm] `batch_for_sort = build_batch_sort_inputs(batches, strict_mode=bool(strict_mode),`
- **被调用者**（10 个）：`items`, `resolve_batch_sort_batch_id`, `batch_for_sort.append`, `BatchForSort`, `str`, `_parse_due_date_for_sort`, `_parse_ready_date_for_sort`, `_parse_created_at_for_sort`, `getattr`, `bool`

### `operation_sort_key()` [公开]
- 位置：第 103-110 行
- 参数：op, batch_order
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:276` [Algorithm] `return sorted(ops_for_sort, key=lambda op: operation_sort_key(op, batch_order))`
- **被调用者**（5 个）：`normalize_text_id`, `getattr`, `int`, `parse_required_int`, `batch_order.get`

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

---
- 分析函数/方法数：133
- 找到调用关系：103 处
- 跨层边界风险：4 项
