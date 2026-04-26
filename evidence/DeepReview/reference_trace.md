# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ auto_assign_internal_resources() 返回 Optional，但 core/algorithms/greedy/scheduler.py:219 的调用者未做 None 检查
- ⚠ auto_assign_internal_resources() 返回 Optional，但 core/algorithms/greedy/dispatch/sgs_scoring.py:234 的调用者未做 None 检查
- ⚠ evaluate_optional_start_candidate() 返回 Optional，但 core/services/scheduler/run/schedule_optimizer_steps.py:428 的调用者未做 None 检查
- ⚠ evaluate_optional_local_candidate() 返回 Optional，但 core/services/scheduler/run/optimizer_local_search.py:262 的调用者未做 None 检查
- ⚠ run_local_search() 返回 Optional，但 core/services/scheduler/run/schedule_optimizer.py:172 的调用者未做 None 检查
- ⚠ init_seen_hashes() 返回 Optional，但 core/services/scheduler/run/optimizer_local_search.py:304 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/algorithms/greedy/auto_assign.py（Algorithm 层）

### `auto_assign_internal_resources()` [公开]
- 位置：第 13-80 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（3 处）：
  - `core/algorithms/greedy/run_context.py:70` [Algorithm] `return auto_assign_internal_resources(*args, **call_kwargs)`
  - `core/algorithms/greedy/scheduler.py:219` [Algorithm] `return auto_assign_internal_resources(`
  - `core/algorithms/greedy/dispatch/sgs_scoring.py:234` [Algorithm] `chosen = ctx.auto_assign_internal_resources(`
- **被调用者**（11 个）：`_fixed_resource_inputs`, `_coerce_resource_pool`, `_resolve_machine_candidates`, `_validated_total_hours`, `_sort_machine_candidates`, `_choose_best_pair`, `getattr`, `count`, `increment_counter`, `strip`, `str`

### `_fixed_resource_inputs()` [私有]
- 位置：第 83-88 行
- 参数：op
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_coerce_resource_pool()` [私有]
- 位置：第 91-99 行
- 参数：resource_pool
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_dict_part()` [私有]
- 位置：第 102-104 行
- 参数：source, key
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_resolve_machine_candidates()` [私有]
- 位置：第 107-127 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_machines_for_fixed_operator()` [私有]
- 位置：第 130-138 行
- 参数：fixed_operator
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_needs_op_type_machine_filter()` [私有]
- 位置：第 141-142 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `_filter_machines_by_op_type()` [私有]
- 位置：第 145-152 行
- 参数：candidates
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_validated_total_hours()` [私有]
- 位置：第 155-160 行
- 参数：op, batch
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_sort_machine_candidates()` [私有]
- 位置：第 163-177 行
- 参数：candidates
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_choose_best_pair()` [私有]
- 位置：第 180-234 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_operator_candidates_for_machine()` [私有]
- 位置：第 237-241 行
- 参数：machine_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_sort_operator_candidates()` [私有]
- 位置：第 244-251 行
- 参数：candidates
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_pair_score()` [私有]
- 位置：第 254-293 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_pair_rank()` [私有]
- 位置：第 296-303 行
- 参数：pool, operator_id, machine_id
- 返回类型：Name(id='int', ctx=Load())

## core/algorithms/greedy/dispatch/sgs_scoring.py（Algorithm 层）

### `_parse_due_date()` [私有]
- 位置：第 20-21 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_dispatch_key()` [私有]
- 位置：第 24-57 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_collect_sgs_candidates()` [私有]
- 位置：第 60-73 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_score_external_candidate()` [私有]
- 位置：第 76-109 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_score_internal_candidate()` [私有]
- 位置：第 112-160 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_candidate_meta()` [私有]
- 位置：第 163-171 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_external_candidate_window()` [私有]
- 位置：第 174-201 行
- 参数：ctx, state
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_parse_external_days()` [私有]
- 位置：第 204-207 行
- 参数：value
- 返回类型：Name(id='float', ctx=Load())

### `_scoring_total_hours()` [私有]
- 位置：第 210-214 行
- 参数：ctx
- 返回类型：Name(id='float', ctx=Load())

### `_scoring_resources()` [私有]
- 位置：第 217-253 行
- 参数：ctx
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_estimate_scoring_slot()` [私有]
- 位置：第 256-287 行
- 参数：ctx, state, op, batch, meta, machine_id, operator_id, end_dt_exclusive, machine_downtimes, total_hours, estimate_slot
- 返回类型：无注解

## core/algorithms/greedy/internal_slot.py（Algorithm 层）

### `_read_legacy_field()` [私有]
- 位置：第 37-42 行
- 参数：obj, field
- 返回类型：Name(id='Any', ctx=Load())

### `_coerce_legacy_hours_value()` [私有]
- 位置：第 45-60 行
- 参数：raw_value
- 返回类型：Name(id='float', ctx=Load())

### `validate_internal_hours()` [公开]
- 位置：第 63-78 行
- 参数：op, batch
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（1 处）：
  - `core/algorithms/greedy/auto_assign.py:157` [Algorithm] `return validate_internal_hours(op, batch)`
- **被调用者**（5 个）：`_read_legacy_field`, `_coerce_legacy_hours_value`, `float`, `ValueError`, `math.isfinite`

### `validate_internal_hours_for_mode()` [公开]
- 位置：第 81-87 行
- 参数：op, batch
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（3 处）：
  - `core/algorithms/greedy/run_context.py:82` [Algorithm] `validate_internal_hours_for_mode(call_kwargs["op"], call_kwargs["batch"], strict`
  - `core/algorithms/greedy/dispatch/sgs_scoring.py:212` [Algorithm] `return validate_internal_hours_for_mode(op, batch, strict_mode=strict_mode)`
  - `core/algorithms/greedy/dispatch/sgs.py:146` [Algorithm] `samples.append(validate_internal_hours_for_mode(op, batch, strict_mode=strict_mo`
- **被调用者**（2 个）：`validate_internal_hours`, `raise_strict_internal_hours_validation`

### `raise_strict_internal_hours_validation()` [公开]
- 位置：第 90-100 行
- 参数：op, batch, exc
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `core/algorithms/greedy/internal_operation.py:175` [Algorithm] `raise_strict_internal_hours_validation(op, batch, exc)`
  - `core/algorithms/greedy/dispatch/sgs_scoring.py:214` [Algorithm] `raise_strict_internal_hours_validation(op, batch, exc)`
- **被调用者**（4 个）：`_internal_hour_fields`, `ValidationError`, `_raise_if_invalid_strict_number`, `str`

### `_internal_hour_fields()` [私有]
- 位置：第 103-108 行
- 参数：op, batch
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_raise_if_invalid_strict_number()` [私有]
- 位置：第 111-119 行
- 参数：field, raw_value
- 返回类型：Constant(value=None, kind=None)

### `_resolve_efficiency()` [私有]
- 位置：第 122-139 行
- 参数：calendar
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_changeover_penalty()` [私有]
- 位置：第 142-151 行
- 参数：op, machine_id, last_op_type_by_machine
- 返回类型：Name(id='int', ctx=Load())

### `_abort_result()` [私有]
- 位置：第 154-171 行
- 参数：无
- 返回类型：Name(id='InternalSlotEstimate', ctx=Load())

### `_resolve_total_base()` [私有]
- 位置：第 174-178 行
- 参数：op, batch, total_hours_base
- 返回类型：Name(id='float', ctx=Load())

### `_slot_segments()` [私有]
- 位置：第 181-187 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_max_shift_count()` [私有]
- 位置：第 190-191 行
- 参数：segment_groups
- 返回类型：Name(id='int', ctx=Load())

### `_adjust_slot_start()` [私有]
- 位置：第 194-195 行
- 参数：calendar, start_time
- 返回类型：Name(id='datetime', ctx=Load())

### `_abort_after_result()` [私有]
- 位置：第 198-215 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_estimate_attempt()` [私有]
- 位置：第 218-226 行
- 参数：calendar
- 返回类型：Name(id='_SlotAttempt', ctx=Load())

### `_latest_overlap_shift_end()` [私有]
- 位置：第 229-236 行
- 参数：segment_groups, earliest, end_time
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_shifted_start()` [私有]
- 位置：第 239-240 行
- 参数：calendar
- 返回类型：Name(id='datetime', ctx=Load())

### `_build_slot_estimate()` [私有]
- 位置：第 243-262 行
- 参数：无
- 返回类型：Name(id='InternalSlotEstimate', ctx=Load())

### `estimate_internal_slot()` [公开]
- 位置：第 265-336 行
- 参数：无
- 返回类型：Name(id='InternalSlotEstimate', ctx=Load())
- **调用者**（2 处）：
  - `core/algorithms/greedy/internal_operation.py:158` [Algorithm] `estimate = estimate_internal_slot(`
  - `core/algorithms/greedy/auto_assign.py:274` [Algorithm] `estimate = estimate_internal_slot(`
- **被调用者**（14 个）：`_resolve_total_base`, `getattr`, `_changeover_penalty`, `_slot_segments`, `_max_shift_count`, `max`, `_adjust_slot_start`, `_abort_after_result`, `_estimate_attempt`, `bool`, `_latest_overlap_shift_end`, `_shifted_start`, `_build_slot_estimate`, `RuntimeError`

## core/algorithms/greedy/run_context.py（Algorithm 层）

### `ScheduleRunContext.from_legacy_scheduler()` [公开]
- 位置：第 23-32 行
- 参数：scheduler
- 返回类型：Name(id='ScheduleRunContext', ctx=Load())
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:106` [Algorithm] `ctx = ScheduleRunContext.from_legacy_scheduler(self)`
- **被调用者**（3 个）：`ensure_algo_stats`, `cls`, `getattr`

### `ScheduleRunContext.increment()` [公开]
- 位置：第 34-35 行
- 参数：key, amount
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/algorithms/greedy/dispatch/sgs.py:140` [Algorithm] `ctx.increment("dispatch_key_avg_proc_hours_fallback_count")`
- **被调用者**（1 个）：`increment_counter`

### `ScheduleRunContext.log_exception()` [公开]
- 位置：第 37-41 行
- 参数：message
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `core/algorithms/greedy/dispatch/sgs.py:332` [Algorithm] `ctx.log_exception(f"工序 {getattr(op, 'op_code', '-') or '-'} 排产异常")`
  - `core/algorithms/greedy/dispatch/batch_order.py:214` [Algorithm] `ctx.log_exception(f"工序 {op_code} 排产异常")`
- **被调用者**（2 个）：`exception`, `self.increment`

### `ScheduleRunContext.schedule_external()` [公开]
- 位置：第 43-47 行
- 参数：无
- 返回类型：无注解
- **调用者**（2 处）：
  - `core/algorithms/greedy/scheduler.py:150` [Algorithm] `return schedule_external(`
  - `core/algorithms/greedy/dispatch/batch_order.py:181` [Algorithm] `return ctx.schedule_external(`
- **被调用者**（4 个）：`callable`, `dict`, `self.external_callback`, `_ScheduleFacade`

### `ScheduleRunContext.schedule_internal()` [公开]
- 位置：第 49-62 行
- 参数：无
- 返回类型：无注解
- **调用者**（1 处）：
  - `core/algorithms/greedy/dispatch/batch_order.py:191` [Algorithm] `return ctx.schedule_internal(`
- **被调用者**（8 个）：`dict`, `bool`, `_validate_strict_internal_input`, `callable`, `call_kwargs.setdefault`, `schedule_internal_operation`, `call_kwargs.pop`, `self.internal_callback`

### `ScheduleRunContext.auto_assign_internal_resources()` [公开]
- 位置：第 64-70 行
- 参数：无
- 返回类型：无注解
- **调用者**（2 处）：
  - `core/algorithms/greedy/scheduler.py:219` [Algorithm] `return auto_assign_internal_resources(`
  - `core/algorithms/greedy/dispatch/sgs_scoring.py:234` [Algorithm] `chosen = ctx.auto_assign_internal_resources(`
- **被调用者**（4 个）：`callable`, `dict`, `call_kwargs.setdefault`, `self.auto_assign_callback`

### `ensure_run_context()` [公开]
- 位置：第 73-76 行
- 参数：candidate
- 返回类型：Name(id='ScheduleRunContext', ctx=Load())
- **调用者**（2 处）：
  - `core/algorithms/greedy/dispatch/sgs.py:70` [Algorithm] `ctx = ensure_run_context(context)`
  - `core/algorithms/greedy/dispatch/batch_order.py:43` [Algorithm] `ctx = ensure_run_context(context)`
- **被调用者**（2 个）：`isinstance`, `ScheduleRunContext.from_legacy_scheduler`

### `_validate_strict_internal_input()` [私有]
- 位置：第 79-82 行
- 参数：call_kwargs
- 返回类型：Constant(value=None, kind=None)

### `_ScheduleFacade.__init__()` [私有]
- 位置：第 86-88 行
- 参数：calendar, algo_stats
- 返回类型：Constant(value=None, kind=None)

## core/algorithms/greedy/seed.py（Algorithm 层）

### `normalize_seed_results()` [公开]
- 位置：第 11-57 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:264` [Algorithm] `normalized_seed, seed_op_ids, seed_warnings = normalize_seed_results(seed_result`
- **被调用者**（13 个）：`set`, `_build_operation_lookup`, `_record_seed_counters`, `warnings.extend`, `_identity_int`, `_normalize_one_seed_result`, `seed_op_ids.add`, `normalized.append`, `_seed_warnings`, `getattr`, `len`, `dup_samples.append`, `str`

### `_build_operation_lookup()` [私有]
- 位置：第 60-81 行
- 参数：operations
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_normalize_one_seed_result()` [私有]
- 位置：第 84-100 行
- 参数：seed_result
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_invalid_time_window_reason()` [私有]
- 位置：第 103-109 行
- 参数：seed_result
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_resolve_seed_op_id()` [私有]
- 位置：第 112-119 行
- 参数：seed_result
- 返回类型：Name(id='int', ctx=Load())

### `_backfill_seed_op_id()` [私有]
- 位置：第 122-124 行
- 参数：seed_result, op_id
- 返回类型：Name(id='ScheduleResult', ctx=Load())

### `_batch_seq_key()` [私有]
- 位置：第 127-130 行
- 参数：obj
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_identity_int()` [私有]
- 位置：第 133-146 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_invalid_identity_supplied()` [私有]
- 位置：第 149-162 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())

### `_record_seed_counters()` [私有]
- 位置：第 165-172 行
- 参数：algo_stats, counters
- 返回类型：Constant(value=None, kind=None)

### `_seed_warnings()` [私有]
- 位置：第 175-191 行
- 参数：counters, dup_samples
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

## core/algorithms/ordering.py（Algorithm 层）

### `normalize_text_id()` [公开]
- 位置：第 13-19 行
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
  - `core/algorithms/greedy/dispatch/batch_order.py:131` [Algorithm] `batch_id = normalize_text_id(getattr(op, "batch_id", ""))`
- **被调用者**（3 个）：`strip`, `ValidationError`, `str`

### `resolve_batch_sort_batch_id()` [公开]
- 位置：第 22-26 行
- 参数：batch_key, batch
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`normalize_text_id`, `getattr`

### `build_normalized_batches_map()` [公开]
- 位置：第 29-38 行
- 参数：batches
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:105` [Service] `normalized_batches_for_sort = build_normalized_batches_map(batches)`
  - `core/algorithms/greedy/scheduler.py:100` [Algorithm] `batches = build_normalized_batches_map(batches, warnings=warnings)`
- **被调用者**（3 个）：`items`, `resolve_batch_sort_batch_id`, `ValidationError`

### `normalize_batch_order_override()` [公开]
- 位置：第 41-56 行
- 参数：batch_order_override, batches
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:249` [Algorithm] `override_order = normalize_batch_order_override(batch_order_override, batches)`
- **被调用者**（5 个）：`set`, `normalize_text_id`, `seen.add`, `override_order.append`, `ValidationError`

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
- **被调用者**（11 个）：`items`, `resolve_batch_sort_batch_id`, `batch_for_sort.append`, `ValidationError`, `BatchForSort`, `str`, `_parse_due_date_for_sort`, `_parse_ready_date_for_sort`, `_parse_created_at_for_sort`, `getattr`, `bool`

### `operation_sort_key()` [公开]
- 位置：第 103-110 行
- 参数：op, batch_order
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:276` [Algorithm] `return sorted(ops_for_sort, key=lambda op: operation_sort_key(op, batch_order))`
- **被调用者**（5 个）：`normalize_text_id`, `getattr`, `int`, `parse_required_int`, `batch_order.get`

## core/services/scheduler/run/optimizer_attempt_records.py（Service 层）

### `validation_error_origin()` [公开]
- 位置：第 10-11 行
- 参数：exc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`getattr`, `str`

### `candidate_tag()` [公开]
- 位置：第 14-15 行
- 参数：strategy_key, dispatch_mode, dispatch_rule
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/run/schedule_optimizer_steps.py:461` [Service] `"tag": candidate_tag(k, dm, dr),`
  - `core/services/scheduler/run/schedule_optimizer_steps.py:478` [Service] `"tag": candidate_tag(k, dm, dr),`

### `append_rejected_start_attempt()` [公开]
- 位置：第 18-35 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`attempts.append`, `candidate_tag`, `validation_error_origin`

### `append_rejected_local_attempt()` [公开]
- 位置：第 38-57 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`append_unique_rejected_attempt`, `validation_error_origin`

### `evaluate_optional_start_candidate()` [公开]
- 位置：第 60-81 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_optimizer_steps.py:428` [Service] `cand = evaluate_optional_start_candidate(`
- **被调用者**（2 个）：`evaluate`, `append_rejected_start_attempt`

### `evaluate_optional_local_candidate()` [公开]
- 位置：第 84-104 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/run/optimizer_local_search.py:262` [Service] `candidate = evaluate_optional_local_candidate(`
- **被调用者**（2 个）：`evaluate`, `append_rejected_local_attempt`

## core/services/scheduler/run/optimizer_local_search.py（Service 层）

### `_swap_neighbor()` [私有]
- 位置：第 15-19 行
- 参数：order, rnd
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_insert_neighbor()` [私有]
- 位置：第 22-28 行
- 参数：order, rnd
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_block_neighbor()` [私有]
- 位置：第 31-46 行
- 参数：order, rnd
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_choose_neighbor()` [私有]
- 位置：第 49-61 行
- 参数：order, rnd
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_evaluate_candidate()` [私有]
- 位置：第 64-113 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_record_improvement()` [私有]
- 位置：第 116-156 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_shake_order()` [私有]
- 位置：第 159-173 行
- 参数：order, rnd
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_should_skip_seen()` [私有]
- 位置：第 176-183 行
- 参数：cand_order, seen_hashes
- 返回类型：Name(id='bool', ctx=Load())

### `_apply_candidate_result()` [私有]
- 位置：第 186-210 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `run_local_search()` [公开]
- 位置：第 213-305 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:172` [Service] `state.best = runtime.run_local_search(`
- **被调用者**（18 个）：`rng_factory`, `list`, `dict`, `str`, `max`, `init_seen_hashes`, `int`, `min`, `_choose_neighbor`, `_should_skip_seen`, `evaluate_optional_local_candidate`, `_apply_candidate_result`, `len`, `best.get`, `clock`

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

### `is_candidate_rejected_attempt()` [公开]
- 位置：第 27-28 行
- 参数：item
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`item.get`

### `attempt_identity()` [公开]
- 位置：第 31-44 行
- 参数：item
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`is_candidate_rejected_attempt`, `_attempt_tag`, `item.get`, `str`, `origin.get`

### `append_unique_rejected_attempt()` [公开]
- 位置：第 47-51 行
- 参数：attempts, attempt
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/run/optimizer_attempt_records.py:47` [Service] `append_unique_rejected_attempt(`
- **被调用者**（3 个）：`attempt_identity`, `any`, `attempts.append`

### `_sorted_attempts_by_score()` [私有]
- 位置：第 54-55 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_best_attempts_by_dispatch_mode()` [私有]
- 位置：第 58-65 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_append_unique_best_attempts()` [私有]
- 位置：第 68-83 行
- 参数：selected, attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_unique_rejected_attempts()` [私有]
- 位置：第 86-91 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_compact_scored_attempts()` [私有]
- 位置：第 94-98 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `compact_attempts()` [公开]
- 位置：第 101-109 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:225` [Service] `attempts=state.compact_attempts(limit=12),`
  - `core/services/scheduler/run/schedule_optimizer.py:252` [Service] `attempts=state.compact_attempts(limit=12),`
- **被调用者**（5 个）：`list`, `_compact_scored_attempts`, `len`, `_unique_rejected_attempts`, `is_candidate_rejected_attempt`

### `init_seen_hashes()` [公开]
- 位置：第 112-120 行
- 参数：cur_order, best
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `core/services/scheduler/run/optimizer_local_search.py:253` [Service] `seen_hashes = init_seen_hashes(cur_order, best)`
  - `core/services/scheduler/run/optimizer_local_search.py:304` [Service] `seen_hashes = init_seen_hashes(cur_order, best)`
- **被调用者**（5 个）：`isinstance`, `len`, `tuple`, `seen_hashes.add`, `best.get`

### `OptimizerSearchState.compact_attempts()` [公开]
- 位置：第 129-130 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:225` [Service] `attempts=state.compact_attempts(limit=12),`
  - `core/services/scheduler/run/schedule_optimizer.py:252` [Service] `attempts=state.compact_attempts(limit=12),`
- **被调用者**（5 个）：`list`, `_compact_scored_attempts`, `len`, `_unique_rejected_attempts`, `is_candidate_rejected_attempt`

### `OptimizerSearchState.compact_trace()` [公开]
- 位置：第 132-133 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `core/services/scheduler/run/schedule_optimizer.py:226` [Service] `improvement_trace=state.compact_trace(limit=200),`
  - `core/services/scheduler/run/schedule_optimizer.py:253` [Service] `improvement_trace=state.compact_trace(limit=200),`
- **被调用者**（1 个）：`list`

## core/services/scheduler/run/schedule_optimizer_steps.py（Service 层）

### `SchedulerLike.schedule()` [公开]
- 位置：第 24-25 行
- 参数：无
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）

### `_step_config_snapshot()` [私有]
- 位置：第 28-29 行
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
- 位置：第 368-486 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

## core/services/scheduler/summary/optimizer_public_summary.py（Service 层）

### `_is_candidate_rejected_attempt()` [私有]
- 位置：第 23-24 行
- 参数：attempt
- 返回类型：Name(id='bool', ctx=Load())

### `_source_label()` [私有]
- 位置：第 27-35 行
- 参数：attempt
- 返回类型：Name(id='str', ctx=Load())

### `_project_attempts()` [私有]
- 位置：第 38-56 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `project_public_algo_summary()` [公开]
- 位置：第 59-68 行
- 参数：algo
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/services/scheduler/summary/schedule_summary_assembly.py:273` [Service] `public_algo, optimizer_diagnostics = project_public_algo_summary(_algo_dict(algo`
- **被调用者**（4 个）：`dict`, `_project_attempts`, `isinstance`, `public_algo.get`

---
- 分析函数/方法数：128
- 找到调用关系：61 处
- 跨层边界风险：6 项
