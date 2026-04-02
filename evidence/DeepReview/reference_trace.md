# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ auto_assign_internal_resources() 返回 Optional，但 core/algorithms/greedy/scheduler.py:573 的调用者未做 None 检查
- ⚠ ConfigService.get_active_preset() 返回 Optional，但 web/routes/scheduler_config.py:286 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## check_manual_layout.py（Other 层）

### `_has_manual_related_min_width()` [私有]
- 位置：第 56-61 行
- 参数：css_content
- 返回类型：Name(id='bool', ctx=Load())

### `_normalize_base_url()` [私有]
- 位置：第 64-66 行
- 参数：base_url
- 返回类型：Name(id='str', ctx=Load())

### `_resolve_base_url()` [私有]
- 位置：第 69-75 行
- 参数：explicit_base_url, runtime_dir
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_server_is_reachable()` [私有]
- 位置：第 78-79 行
- 参数：base_url
- 返回类型：Name(id='bool', ctx=Load())

### `_parse_args()` [私有]
- 位置：第 82-89 行
- 参数：argv
- 返回类型：无注解

### `check_layout_via_styles()` [公开]
- 位置：第 92-119 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`print`, `css_file.read_text`, `checks.items`, `css_file.exists`, `_has_manual_related_min_width`

### `check_layout_via_browser()` [公开]
- 位置：第 122-282 行
- 参数：base_url
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（22 个）：`_normalize_base_url`, `print`, `Options`, `options.add_argument`, `_server_is_reachable`, `webdriver.Chrome`, `driver.quit`, `driver.get`, `time.sleep`, `driver.add_cookie`, `driver.refresh`, `until`, `driver.find_element`, `driver.execute_script`, `results.append`

### `main()` [公开]
- 位置：第 285-337 行
- 参数：argv
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`_parse_args`, `_resolve_base_url`, `print`, `check_layout_via_styles`, `check_layout_via_browser`, `sys.exit`, `sum`, `len`, `mkdir`, `report_file.write_text`, `all`, `json.dumps`

## core/algorithms/greedy/algo_stats.py（Algorithm 层）

### `ensure_algo_stats()` [公开]
- 位置：第 10-26 行
- 参数：target
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:81` [Algorithm] `ensure_algo_stats(self)`
- **被调用者**（4 个）：`isinstance`, `getattr`, `stats.get`, `setattr`

### `snapshot_algo_stats()` [公开]
- 位置：第 29-38 行
- 参数：target
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `core/services/scheduler/schedule_optimizer.py:169` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/schedule_optimizer.py:540` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/schedule_optimizer_steps.py:154` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/schedule_optimizer_steps.py:275` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
- **被调用者**（5 个）：`ensure_algo_stats`, `deepcopy`, `stats.get`, `isinstance`, `dict`

### `increment_counter()` [公开]
- 位置：第 41-58 行
- 参数：target, key, amount
- 返回类型：Constant(value=None, kind=None)
- **调用者**（51 处）：
  - `core/services/scheduler/schedule_optimizer.py:274` [Service] `increment_counter(optimizer_algo_stats, f"optimizer_{key}_defaulted_count", buck`
  - `core/services/scheduler/schedule_optimizer.py:279` [Service] `increment_counter(optimizer_algo_stats, f"optimizer_{key}_defaulted_count", buck`
  - `core/services/scheduler/schedule_optimizer.py:282` [Service] `increment_counter(optimizer_algo_stats, f"optimizer_{key}_defaulted_count", buck`
  - `core/services/scheduler/schedule_optimizer.py:428` [Service] `increment_counter(optimizer_algo_stats, "optimizer_seed_result_invalid_count", i`
  - `core/services/scheduler/schedule_optimizer_steps.py:31` [Service] `increment_counter(algo_stats, counter_key or f"optimizer_{key}_defaulted_count",`
  - `core/services/scheduler/schedule_optimizer_steps.py:36` [Service] `increment_counter(algo_stats, counter_key or f"optimizer_{key}_defaulted_count",`
  - `core/services/scheduler/schedule_optimizer_steps.py:39` [Service] `increment_counter(algo_stats, counter_key or f"optimizer_{key}_defaulted_count",`
  - `core/algorithms/greedy/auto_assign.py:47` [Algorithm] `increment_counter(scheduler, "auto_assign_missing_op_type_id_count")`
  - `core/algorithms/greedy/auto_assign.py:81` [Algorithm] `increment_counter(scheduler, "auto_assign_missing_machine_pool_count")`
  - `core/algorithms/greedy/auto_assign.py:88` [Algorithm] `increment_counter(scheduler, "auto_assign_missing_machine_pool_count")`
  - `core/algorithms/greedy/auto_assign.py:95` [Algorithm] `increment_counter(scheduler, "auto_assign_no_machine_candidate_count")`
  - `core/algorithms/greedy/auto_assign.py:105` [Algorithm] `increment_counter(scheduler, "auto_assign_invalid_total_hours_count")`
  - `core/algorithms/greedy/auto_assign.py:108` [Algorithm] `increment_counter(scheduler, "auto_assign_invalid_total_hours_count")`
  - `core/algorithms/greedy/auto_assign.py:223` [Algorithm] `increment_counter(scheduler, "auto_assign_no_operator_candidate_count")`
  - `core/algorithms/greedy/auto_assign.py:225` [Algorithm] `increment_counter(scheduler, "auto_assign_no_feasible_pair_count")`
  - `core/algorithms/greedy/scheduler.py:201` [Algorithm] `increment_counter(self, "seed_overlap_filtered_count", dropped)`
  - `core/algorithms/greedy/scheduler.py:310` [Algorithm] `increment_counter(self, "seed_missing_machine_id_count", missing_seed_machine)`
  - `core/algorithms/greedy/scheduler.py:317` [Algorithm] `increment_counter(self, "seed_missing_operator_id_count", missing_seed_operator)`
  - `core/algorithms/greedy/scheduler.py:433` [Algorithm] `increment_counter(self, "internal_auto_assign_attempt_count")`
  - `core/algorithms/greedy/scheduler.py:449` [Algorithm] `increment_counter(self, "internal_auto_assign_success_count")`
  - `core/algorithms/greedy/scheduler.py:452` [Algorithm] `increment_counter(self, "internal_auto_assign_failed_count")`
  - `core/algorithms/greedy/scheduler.py:457` [Algorithm] `increment_counter(self, "internal_missing_resource_without_auto_assign_count")`
  - `core/algorithms/greedy/scheduler.py:491` [Algorithm] `increment_counter(self, "internal_efficiency_fallback_count")`
  - `core/algorithms/greedy/schedule_params.py:49` [Algorithm] `increment_counter(algo_stats, "start_dt_parsed_count", bucket="param_fallbacks")`
  - `core/algorithms/greedy/schedule_params.py:53` [Algorithm] `increment_counter(algo_stats, "start_dt_default_now_count", bucket="param_fallba`
  - `core/algorithms/greedy/schedule_params.py:61` [Algorithm] `increment_counter(algo_stats, "end_date_ignored_count", bucket="param_fallbacks"`
  - `core/algorithms/greedy/schedule_params.py:79` [Algorithm] `increment_counter(algo_stats, "sort_strategy_defaulted_count", bucket="param_fal`
  - `core/algorithms/greedy/schedule_params.py:97` [Algorithm] `increment_counter(algo_stats, f"weighted_{key}_defaulted_count", bucket="param_f`
  - `core/algorithms/greedy/schedule_params.py:117` [Algorithm] `increment_counter(algo_stats, f"weighted_{key}_defaulted_count", bucket="param_f`
  - `core/algorithms/greedy/schedule_params.py:146` [Algorithm] `increment_counter(algo_stats, "dispatch_mode_defaulted_count", bucket="param_fal`
  - `core/algorithms/greedy/schedule_params.py:172` [Algorithm] `increment_counter(algo_stats, "dispatch_rule_defaulted_count", bucket="param_fal`
  - `core/algorithms/greedy/schedule_params.py:191` [Algorithm] `increment_counter(algo_stats, "auto_assign_enabled_defaulted_count", bucket="par`
  - `core/algorithms/greedy/seed.py:142` [Algorithm] `increment_counter(algo_stats, "seed_normalize_outer_exception_count")`
  - `core/algorithms/greedy/seed.py:145` [Algorithm] `increment_counter(algo_stats, "seed_op_id_backfilled_count", backfilled)`
  - `core/algorithms/greedy/seed.py:146` [Algorithm] `increment_counter(algo_stats, "seed_invalid_dropped_count", dropped_invalid)`
  - `core/algorithms/greedy/seed.py:147` [Algorithm] `increment_counter(algo_stats, "seed_bad_time_dropped_count", dropped_bad_time)`
  - `core/algorithms/greedy/seed.py:148` [Algorithm] `increment_counter(algo_stats, "seed_duplicate_dropped_count", dropped_dup)`
  - `core/algorithms/greedy/dispatch/sgs.py:107` [Algorithm] `increment_counter(scheduler, "dispatch_key_avg_proc_hours_fallback_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:156` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_external_duration_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:173` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_external_duration_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:185` [Algorithm] `increment_counter(scheduler, "dispatch_key_proc_hours_fallback_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:222` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_auto_assign_probe_exception_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:225` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_auto_assign_probe_exception_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:229` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_missing_resource_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:236` [Algorithm] `increment_counter(scheduler, "dispatch_key_proc_hours_fallback_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:255` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_total_hours_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:258` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_total_hours_unscorable_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:263` [Algorithm] `increment_counter(scheduler, "dispatch_key_proc_hours_fallback_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:320` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_scoring_exception_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:321` [Algorithm] `increment_counter(scheduler, "dispatch_key_proc_hours_fallback_count")`
  - `core/algorithms/greedy/dispatch/sgs.py:425` [Algorithm] `increment_counter(scheduler, "dispatch_sgs_runtime_busy_hours_update_exception_c`
- **被调用者**（5 个）：`ensure_algo_stats`, `stats.get`, `isinstance`, `int`, `current_bucket.get`

### `merge_algo_stats()` [公开]
- 位置：第 61-82 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（5 处）：
  - `core/services/scheduler/schedule_optimizer.py:169` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/schedule_optimizer.py:540` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/schedule_optimizer.py:566` [Service] `merge_algo_stats(best_algo_stats) if isinstance(best_algo_stats, dict) else merg`
  - `core/services/scheduler/schedule_optimizer_steps.py:154` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
  - `core/services/scheduler/schedule_optimizer_steps.py:275` [Service] `algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(schedule`
- **被调用者**（6 个）：`isinstance`, `src.get`, `merged.get`, `part.items`, `int`, `bucket_out.get`

## core/algorithms/greedy/auto_assign.py（Algorithm 层）

### `auto_assign_internal_resources()` [公开]
- 位置：第 11-227 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:573` [Algorithm] `return auto_assign_internal_resources(`
- **被调用者**（32 个）：`strip`, `batch_progress.get`, `getattr`, `list`, `sorted`, `increment_counter`, `isinstance`, `resource_pool.get`, `dict.fromkeys`, `str`, `float`, `math.isfinite`, `max`, `adjust_to_working_time`, `_scaled_hours`

## core/algorithms/greedy/dispatch/sgs.py（Algorithm 层）

### `_parse_date()` [私有]
- 位置：第 15-30 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `dispatch_sgs()` [公开]
- 位置：第 33-460 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:320` [Algorithm] `scheduled_count, failed_count = dispatch_sgs(`
- **被调用者**（53 个）：`ops_by_batch.items`, `sorted`, `strip`, `append`, `lst.sort`, `list`, `batches.get`, `increment_counter`, `errors.append`, `ops_by_batch.keys`, `getattr`, `sum`, `float`, `int`, `candidates.append`

## core/algorithms/greedy/schedule_params.py（Algorithm 层）

### `resolve_schedule_params()` [公开]
- 位置：第 29-208 行
- 参数：无
- 返回类型：Name(id='ScheduleParams', ctx=Load())
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:83` [Algorithm] `params = resolve_schedule_params(`
- **被调用者**（23 个）：`parse_date`, `lower`, `parse_dispatch_rule`, `ScheduleParams`, `datetime.now`, `parse_datetime`, `strip`, `parse_strategy`, `dict`, `isinstance`, `ValidationError`, `warnings.append`, `increment_counter`, `datetime`, `timedelta`

## core/algorithms/greedy/scheduler.py（Algorithm 层）

### `GreedyScheduler.__init__()` [私有]
- 位置：第 38-42 行
- 参数：calendar_service, config_service, logger
- 返回类型：无注解

### `GreedyScheduler._cfg_get()` [私有]
- 位置：第 44-53 行
- 参数：key, default
- 返回类型：Name(id='Any', ctx=Load())

### `GreedyScheduler.schedule()` [公开]
- 位置：第 55-383 行
- 参数：operations, batches, strategy, strategy_params, start_dt, end_date, machine_downtimes, batch_order_override, seed_results, dispatch_mode, dispatch_rule, resource_pool, strict_mode
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（4 处）：
  - `core/services/scheduler/schedule_optimizer_steps.py:61` [Service] `return scheduler.schedule(**kwargs)`
  - `core/services/scheduler/schedule_optimizer_steps.py:63` [Service] `return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))`
  - `core/services/scheduler/schedule_optimizer_steps.py:66` [Service] `return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))`
  - `core/services/scheduler/schedule_optimizer_steps.py:73` [Service] `return scheduler.schedule(**kwargs)`
- **被调用者**（54 个）：`datetime.now`, `ensure_algo_stats`, `resolve_schedule_params`, `warnings.extend`, `items`, `StrategyFactory.create`, `batches.items`, `sorter.sort`, `set`, `sorted`, `info`, `total_seconds`, `int`, `ScheduleSummary`, `_norm_id`

### `GreedyScheduler._schedule_external()` [私有]
- 位置：第 385-404 行
- 参数：op, batch, batch_progress, external_group_cache, base_time, errors, end_dt_exclusive
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `GreedyScheduler._schedule_internal()` [私有]
- 位置：第 406-555 行
- 参数：op, batch, batch_progress, machine_timeline, operator_timeline, base_time, errors, end_dt_exclusive, machine_downtimes
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `GreedyScheduler._auto_assign_internal_resources()` [私有]
- 位置：第 557-587 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

## core/algorithms/greedy/seed.py（Algorithm 层）

### `normalize_seed_results()` [公开]
- 位置：第 10-163 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/algorithms/greedy/scheduler.py:181` [Algorithm] `normalized_seed, seed_op_ids, seed_warnings = normalize_seed_results(seed_result`
- **被调用者**（18 个）：`set`, `increment_counter`, `strip`, `bs_seen.pop`, `warnings.append`, `join`, `int`, `bs_seen.get`, `getattr`, `str`, `bs_dups.add`, `seed_op_ids.add`, `normalized.append`, `len`, `dup_samples.append`

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
  - `web/routes/process_parts.py:90` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:91` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:92` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:121` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:85` [Route] `supplier=s.to_dict(),`
  - `web/routes/scheduler_batches.py:45` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:68` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:117` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:186` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:230` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/scheduler_resource_dispatch.py:51` [Route] `for key, value in request.args.to_dict(flat=True).items():`
  - `web/routes/scheduler_resource_dispatch.py:188` [Route] `return redirect(url_for("scheduler.resource_dispatch_page", **request.args.to_di`
  - `web/routes/system_backup.py:45` [Route] `settings=cfg.to_dict(),`
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
  - `core/services/process/route_parser.py:58` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:78` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:79` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
  - `core/services/process/supplier_excel_import_service.py:114` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:104` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:276` [Service] `self.batch_repo.create(b.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:328` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:384` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:389` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config_presets.py:20` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:29` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:37` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:129` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config_presets.py:181` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/gantt_contract.py:70` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:164` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:206` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_optimizer.py:195` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:209` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:257` [Service] `cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(`
  - `core/services/scheduler/schedule_optimizer_steps.py:163` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:190` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:284` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:311` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_summary.py:46` [Service] `obj = to_dict()`
  - `core/services/scheduler/schedule_summary.py:581` [Service] `"metrics": best_metrics.to_dict() if best_metrics is not None else None,`

### `ValidationError.__init__()` [私有]
- 位置：第 107-110 行
- 参数：message, field
- 返回类型：无注解

### `NotFoundError.__init__()` [私有]
- 位置：第 114-119 行
- 参数：resource_type, resource_id
- 返回类型：无注解

### `success_response()` [公开]
- 位置：第 126-132 行
- 参数：data, meta
- 返回类型：Name(id='dict', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）

### `error_response()` [公开]
- 位置：第 135-139 行
- 参数：code, message, details
- 返回类型：Name(id='dict', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）

## core/services/process/external_group_service.py（Service 层）

### `ExternalGroupService.__init__()` [私有]
- 位置：第 16-22 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ExternalGroupService._normalize_text()` [私有]
- 位置：第 25-26 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ExternalGroupService._normalize_float()` [私有]
- 位置：第 29-35 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ExternalGroupService._get_group_or_raise()` [私有]
- 位置：第 37-41 行
- 参数：group_id
- 返回类型：无注解

### `ExternalGroupService.list_by_part()` [公开]
- 位置：第 43-44 行
- 参数：part_no
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（9 处）：
  - `core/services/process/part_operation_query_service.py:30` [Service] `for op in self.repo.list_by_part(part_no, include_deleted=False):`
  - `core/services/process/part_service.py:70` [Service] `ops = self.op_repo.list_by_part(part_no, include_deleted=False)`
  - `core/services/process/part_service.py:387` [Service] `ops = self.op_repo.list_by_part(p.part_no, include_deleted=True)`
  - `core/services/process/part_service.py:388` [Service] `groups = self.group_repo.list_by_part(p.part_no)`
  - `core/services/process/part_service.py:439` [Service] `ops = self.op_repo.list_by_part(pn, include_deleted=False)`
  - `core/services/process/part_service.py:479` [Service] `ops = self.op_repo.list_by_part(pn, include_deleted=False)`
  - `core/services/process/part_service.py:491` [Service] `for group in self.group_repo.list_by_part(pn):`
  - `core/services/scheduler/batch_service.py:143` [Service] `template_ops = self.part_op_repo.list_by_part(part_no, include_deleted=False)`
  - `core/services/scheduler/batch_service.py:157` [Service] `template_ops = self.part_op_repo.list_by_part(part_no, include_deleted=False)`

### `ExternalGroupService._list_external_ops_in_group()` [私有]
- 位置：第 46-55 行
- 参数：part_no, group_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `ExternalGroupService._update_group_common_fields()` [私有]
- 位置：第 57-73 行
- 参数：group_id
- 返回类型：Constant(value=None, kind=None)

### `ExternalGroupService._apply_merged_mode()` [私有]
- 位置：第 75-101 行
- 参数：group_id
- 返回类型：Constant(value=None, kind=None)

### `ExternalGroupService._apply_separate_mode()` [私有]
- 位置：第 103-146 行
- 参数：group_id
- 返回类型：Constant(value=None, kind=None)

### `ExternalGroupService.set_merge_mode()` [公开]
- 位置：第 148-204 行
- 参数：group_id, merge_mode, total_days, per_op_days, supplier_id, remark, strict_mode
- 返回类型：Name(id='ExternalGroup', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/process_parts.py:225` [Route] `svc.set_merge_mode(`
- **被调用者**（11 个）：`self._normalize_text`, `lower`, `self._get_group_or_raise`, `self._list_external_ops_in_group`, `ValidationError`, `int`, `transaction`, `strip`, `self._apply_merged_mode`, `self._apply_separate_mode`, `bool`

## core/services/process/part_service.py（Service 层）

### `PartService.__init__()` [私有]
- 位置：第 27-40 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `PartService._normalize_text()` [私有]
- 位置：第 46-47 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `PartService._normalize_float()` [私有]
- 位置：第 50-56 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `PartService._get_or_raise()` [私有]
- 位置：第 58-62 行
- 参数：part_no
- 返回类型：Name(id='Part', ctx=Load())

### `PartService._build_internal_hours_snapshot()` [私有]
- 位置：第 64-79 行
- 参数：part_no
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `PartService._coerce_external_default_days()` [私有]
- 位置：第 81-118 行
- 参数：op
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `PartService.list()` [公开]
- 位置：第 124-127 行
- 参数：route_parsed
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`ValidationError`

### `PartService.get()` [公开]
- 位置：第 129-133 行
- 参数：part_no
- 返回类型：Name(id='Part', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self._normalize_text`, `self._get_or_raise`, `ValidationError`

### `PartService.create()` [公开]
- 位置：第 135-173 行
- 参数：part_no, part_name, route_raw, remark
- 返回类型：Name(id='Part', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`self._normalize_text`, `get`, `self._get_or_raise`, `str`, `ValidationError`, `BusinessError`, `strip`, `self._parse_route_or_raise`, `transaction`, `self._save_template_no_tx`, `self.reparse_and_save`

### `PartService.update()` [公开]
- 位置：第 175-195 行
- 参数：part_no, part_name, route_raw, remark
- 返回类型：Name(id='Part', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`self._normalize_text`, `self._get_or_raise`, `ValidationError`, `str`, `transaction`

### `PartService.delete()` [公开]
- 位置：第 197-209 行
- 参数：part_no
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`self._normalize_text`, `self._get_or_raise`, `fetchone`, `ValidationError`, `BusinessError`, `transaction`, `execute`

### `PartService.delete_all_no_tx()` [公开]
- 位置：第 211-212 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `web/routes/process_excel_routes.py:225` [Route] `part_svc.delete_all_no_tx()`
  - `web/routes/scheduler_excel_calendar.py:355` [Route] `cal_svc.delete_all_no_tx()`
  - `core/services/scheduler/batch_excel_import.py:31` [Service] `svc.delete_all_no_tx()`
  - `core/services/scheduler/calendar_service.py:101` [Service] `self._admin.delete_all_no_tx()`
- **被调用者**（1 个）：`delete_all`

### `PartService.validate_route_format()` [公开]
- 位置：第 217-218 行
- 参数：route_raw
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `web/routes/process_excel_routes.py:41` [Route] `ok, msg = part_svc.validate_route_format(route_raw)`
- **被调用者**（2 个）：`validate_format`, `str`

### `PartService._parse_route_or_raise()` [私有]
- 位置：第 220-233 行
- 参数：无
- 返回类型：Name(id='ParseResult', ctx=Load())

### `PartService.parse()` [公开]
- 位置：第 235-238 行
- 参数：route_raw, part_no
- 返回类型：Name(id='ParseResult', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/process_excel_routes.py:46` [Route] `result = part_svc.parse(route_raw, part_no=part_no, strict_mode=True)`
  - `core/services/process/unit_excel_converter.py:27` [Service] `parts, stations = self._parser.parse(input_path=input_path, sheet_name=sheet_nam`
- **被调用者**（2 个）：`str`, `bool`

### `PartService.reparse_and_save()` [公开]
- 位置：第 240-272 行
- 参数：part_no, route_raw
- 返回类型：Name(id='ParseResult', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/process_parts.py:183` [Route] `result = svc.reparse_and_save(part_no=part_no, route_raw=route_raw, strict_mode=`
  - `core/services/scheduler/batch_service.py:125` [Service] `svc.reparse_and_save(part_no=part_no, route_raw=route_raw, strict_mode=strict_mo`
- **被调用者**（11 个）：`self._normalize_text`, `self._get_or_raise`, `self._parse_route_or_raise`, `ValidationError`, `str`, `transaction`, `update`, `self._build_internal_hours_snapshot`, `delete_by_part`, `self._save_template_no_tx`, `bool`

### `PartService.upsert_and_parse_no_tx()` [公开]
- 位置：第 274-306 行
- 参数：part_no, part_name, route_raw
- 返回类型：Name(id='ParseResult', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/process_excel_routes.py:251` [Route] `part_svc.upsert_and_parse_no_tx(part_no=pn, part_name=name, route_raw=route_raw,`
  - `core/services/scheduler/batch_service.py:123` [Service] `svc.upsert_and_parse_no_tx(part_no=part_no, part_name=part_name, route_raw=route`
- **被调用者**（11 个）：`self._normalize_text`, `self._parse_route_or_raise`, `get`, `self._build_internal_hours_snapshot`, `delete_by_part`, `self._save_template_no_tx`, `str`, `ValidationError`, `update`, `create`, `bool`

### `PartService._save_template_no_tx()` [私有]
- 位置：第 308-380 行
- 参数：part_no, parse_result, preserved_internal_hours
- 返回类型：Constant(value=None, kind=None)

### `PartService.get_template_detail()` [公开]
- 位置：第 385-395 行
- 参数：part_no
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/process_parts.py:89` [Route] `detail = p_svc.get_template_detail(part_no)`
- **被调用者**（2 个）：`self.get`, `list_by_part`

### `PartService.update_internal_hours()` [公开]
- 位置：第 397-424 行
- 参数：part_no, seq, setup_hours, unit_hours
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/process_parts.py:202` [Route] `svc.update_internal_hours(part_no=part_no, seq=seq, setup_hours=setup_hours, uni`
  - `core/services/process/part_operation_hours_excel_import_service.py:76` [Service] `self.part_svc.update_internal_hours(part_no=part_no, seq=seq, setup_hours=sh, un`
- **被调用者**（12 个）：`self._normalize_text`, `self._get_or_raise`, `self._normalize_float`, `get`, `ValidationError`, `int`, `BusinessError`, `lower`, `transaction`, `update`, `strip`, `float`

### `PartService.delete_external_group()` [公开]
- 位置：第 426-469 行
- 参数：part_no, group_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/process_parts.py:241` [Route] `result = svc.delete_external_group(part_no=part_no, group_id=group_id)`
- **被调用者**（17 个）：`self._normalize_text`, `self._get_or_raise`, `get`, `list_by_part`, `get_deletion_groups`, `can_delete`, `ValidationError`, `BusinessError`, `int`, `DeleteOp`, `any`, `transaction`, `delete`, `mark_deleted`, `lower`

### `PartService.calc_deletable_external_group_ids()` [公开]
- 位置：第 471-502 行
- 参数：part_no
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/process_parts.py:101` [Route] `deletable_group_ids = set(p_svc.calc_deletable_external_group_ids(part_no))`
- **被调用者**（11 个）：`self._normalize_text`, `list_by_part`, `get_deletion_groups`, `set`, `DeleteOp`, `deletable_seqs.add`, `int`, `all`, `group_ids.append`, `lower`, `strip`

### `PartService.build_existing_for_excel_routes()` [公开]
- 位置：第 507-511 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/process_excel_routes.py:89` [Route] `existing = svc.build_existing_for_excel_routes()`
  - `web/routes/process_excel_routes.py:114` [Route] `existing = part_svc.build_existing_for_excel_routes()`
  - `web/routes/process_excel_routes.py:173` [Route] `existing = part_svc.build_existing_for_excel_routes()`
- **被调用者**（1 个）：`list`

## core/services/process/route_parser.py（Service 层）

### `ParsedOperation.to_dict()` [公开]
- 位置：第 31-41 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（60 处）：
  - `web/routes/equipment_pages.py:216` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:229` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:27` [Route] `items = [m.to_dict() for m in svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:23` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:48` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:144` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:90` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:91` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:92` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:121` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:85` [Route] `supplier=s.to_dict(),`
  - `web/routes/scheduler_batches.py:45` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:68` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:117` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:186` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:230` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/scheduler_resource_dispatch.py:51` [Route] `for key, value in request.args.to_dict(flat=True).items():`
  - `web/routes/scheduler_resource_dispatch.py:188` [Route] `return redirect(url_for("scheduler.resource_dispatch_page", **request.args.to_di`
  - `web/routes/system_backup.py:45` [Route] `settings=cfg.to_dict(),`
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
  - `core/services/process/supplier_excel_import_service.py:114` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:104` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:276` [Service] `self.batch_repo.create(b.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:328` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:384` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:389` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config_presets.py:20` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:29` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:37` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:129` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config_presets.py:181` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/gantt_contract.py:70` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:164` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:206` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_optimizer.py:195` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:209` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:257` [Service] `cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(`
  - `core/services/scheduler/schedule_optimizer_steps.py:163` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:190` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:284` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:311` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_summary.py:46` [Service] `obj = to_dict()`
  - `core/services/scheduler/schedule_summary.py:581` [Service] `"metrics": best_metrics.to_dict() if best_metrics is not None else None,`

### `ExternalGroup.to_dict()` [公开]
- 位置：第 53-59 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（60 处）：
  - `web/routes/equipment_pages.py:216` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:229` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:27` [Route] `items = [m.to_dict() for m in svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:23` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:48` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:144` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:90` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:91` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:92` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:121` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:85` [Route] `supplier=s.to_dict(),`
  - `web/routes/scheduler_batches.py:45` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:68` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:117` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:186` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:230` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/scheduler_resource_dispatch.py:51` [Route] `for key, value in request.args.to_dict(flat=True).items():`
  - `web/routes/scheduler_resource_dispatch.py:188` [Route] `return redirect(url_for("scheduler.resource_dispatch_page", **request.args.to_di`
  - `web/routes/system_backup.py:45` [Route] `settings=cfg.to_dict(),`
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
  - `core/services/process/supplier_excel_import_service.py:114` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:104` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:276` [Service] `self.batch_repo.create(b.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:328` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:384` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:389` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config_presets.py:20` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:29` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:37` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:129` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config_presets.py:181` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/gantt_contract.py:70` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:164` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:206` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_optimizer.py:195` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:209` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:257` [Service] `cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(`
  - `core/services/scheduler/schedule_optimizer_steps.py:163` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:190` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:284` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:311` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_summary.py:46` [Service] `obj = to_dict()`
  - `core/services/scheduler/schedule_summary.py:581` [Service] `"metrics": best_metrics.to_dict() if best_metrics is not None else None,`

### `ParseResult.to_dict()` [公开]
- 位置：第 75-85 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（60 处）：
  - `web/routes/equipment_pages.py:216` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:229` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:27` [Route] `items = [m.to_dict() for m in svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:23` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:48` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:144` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:90` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:91` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:92` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:121` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:85` [Route] `supplier=s.to_dict(),`
  - `web/routes/scheduler_batches.py:45` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:68` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:117` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:186` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:230` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/scheduler_resource_dispatch.py:51` [Route] `for key, value in request.args.to_dict(flat=True).items():`
  - `web/routes/scheduler_resource_dispatch.py:188` [Route] `return redirect(url_for("scheduler.resource_dispatch_page", **request.args.to_di`
  - `web/routes/system_backup.py:45` [Route] `settings=cfg.to_dict(),`
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
  - `core/services/process/supplier_excel_import_service.py:114` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:104` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:276` [Service] `self.batch_repo.create(b.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:328` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:384` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:389` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config_presets.py:20` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:29` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:37` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:129` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config_presets.py:181` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/gantt_contract.py:70` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:164` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:206` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_optimizer.py:195` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:209` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:257` [Service] `cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(`
  - `core/services/scheduler/schedule_optimizer_steps.py:163` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:190` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:284` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:311` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_summary.py:46` [Service] `obj = to_dict()`
  - `core/services/scheduler/schedule_summary.py:581` [Service] `"metrics": best_metrics.to_dict() if best_metrics is not None else None,`

### `RouteParser.__init__()` [私有]
- 位置：第 103-106 行
- 参数：op_types_repo, suppliers_repo, logger
- 返回类型：无注解

### `RouteParser.parse()` [公开]
- 位置：第 108-291 行
- 参数：route_string, part_no
- 返回类型：Name(id='ParseResult', ctx=Load())
- **调用者**（4 处）：
  - `web/routes/process_excel_routes.py:46` [Route] `result = part_svc.parse(route_raw, part_no=part_no, strict_mode=True)`
  - `core/services/process/part_service.py:226` [Service] `result = self.route_parser.parse(rr, part_no=part_no, strict_mode=bool(strict_mo`
  - `core/services/process/part_service.py:236` [Service] `return self.route_parser.parse(`
  - `core/services/process/unit_excel_converter.py:27` [Service] `parts, stations = self._parser.parse(input_path=input_path, sheet_name=sheet_nam`
- **被调用者**（32 个）：`self._preprocess`, `re.search`, `self._build_supplier_map`, `re.findall`, `set`, `operations.sort`, `self._identify_external_groups`, `ParseResult`, `re.match`, `errors.append`, `list`, `strip`, `seen_seqs.add`, `op_types.get`, `ParsedOperation`

### `RouteParser._preprocess()` [私有]
- 位置：第 293-310 行
- 参数：route_string
- 返回类型：Name(id='str', ctx=Load())

### `RouteParser._build_supplier_map()` [私有]
- 位置：第 312-367 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `RouteParser._identify_external_groups()` [私有]
- 位置：第 369-399 行
- 参数：operations, part_no
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `RouteParser.validate_format()` [公开]
- 位置：第 401-427 行
- 参数：route_string
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（2 处）：
  - `core/services/process/part_service.py:218` [Service] `return self.route_parser.validate_format(str(route_raw) if route_raw is not None`
  - `core/services/process/part_service.py:222` [Service] `ok, msg = self.route_parser.validate_format(rr)`
- **被调用者**（8 个）：`self._preprocess`, `re.search`, `re.findall`, `re.match`, `strip`, `len`, `str`, `tail_m.group`

## core/services/process/supplier_service.py（Service 层）

### `SupplierService.__init__()` [私有]
- 位置：第 16-22 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `SupplierService._normalize_text()` [私有]
- 位置：第 25-26 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `SupplierService._normalize_default_days()` [私有]
- 位置：第 29-39 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `SupplierService._log_default_days_fallback()` [私有]
- 位置：第 41-50 行
- 参数：raw_value
- 返回类型：Constant(value=None, kind=None)

### `SupplierService._resolve_op_type_id()` [私有]
- 位置：第 52-66 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `SupplierService._validate_fields()` [私有]
- 位置：第 68-98 行
- 参数：supplier_id, name, default_days, status, allow_partial
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `SupplierService._get_or_raise()` [私有]
- 位置：第 100-104 行
- 参数：supplier_id
- 返回类型：Name(id='Supplier', ctx=Load())

### `SupplierService.list()` [公开]
- 位置：第 106-116 行
- 参数：status, op_type_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/process_parts.py:98` [Route] `suppliers = {s.supplier_id: s for s in SupplierService(g.db).list()}  # type: ig`
  - `web/routes/scheduler_batch_detail.py:106` [Route] `suppliers_active = supplier_svc.list(status=SupplierStatus.ACTIVE.value)`
- **被调用者**（4 个）：`self._validate_fields`, `get`, `ValidationError`, `BusinessError`

### `SupplierService.get()` [公开]
- 位置：第 118-122 行
- 参数：supplier_id
- 返回类型：Name(id='Supplier', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self._validate_fields`, `self._get_or_raise`, `ValidationError`

### `SupplierService.get_optional()` [公开]
- 位置：第 124-131 行
- 参数：supplier_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（11 处）：
  - `web/routes/equipment_excel_machines.py:69` [Route] `ot = op_type_svc.get_optional(v)`
  - `web/routes/process_excel_suppliers.py:63` [Route] `ot = op_type_svc.get_optional(v)`
  - `web/routes/scheduler_batch_detail.py:54` [Route] `extra = machine_svc.get_optional(mid)`
  - `web/routes/scheduler_batch_detail.py:83` [Route] `extra = operator_svc.get_optional(oid)`
  - `web/routes/scheduler_batch_detail.py:112` [Route] `extra = supplier_svc.get_optional(sid)`
  - `core/services/personnel/resource_team_service.py:98` [Service] `team = self.get_optional(v)`
  - `core/services/personnel/resource_team_service.py:109` [Service] `team = self.get_optional(team_id)`
  - `core/services/process/op_type_service.py:92` [Service] `ot = self.get_optional(v)`
  - `core/services/scheduler/resource_dispatch_service.py:100` [Service] `return self.operator_service.get_optional(scope_id)`
  - `core/services/scheduler/resource_dispatch_service.py:102` [Service] `return self.machine_service.get_optional(scope_id)`
  - `core/services/scheduler/resource_dispatch_service.py:103` [Service] `return self.team_service.get_optional(scope_id)`
- **被调用者**（2 个）：`self._validate_fields`, `get`

### `SupplierService.create()` [公开]
- 位置：第 133-162 行
- 参数：supplier_id, name, op_type_value, default_days, status, remark
- 返回类型：Name(id='Supplier', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`self._validate_fields`, `self._normalize_text`, `get`, `self._get_or_raise`, `ValidationError`, `self._resolve_op_type_id`, `BusinessError`, `transaction`, `float`

### `SupplierService.update()` [公开]
- 位置：第 164-195 行
- 参数：supplier_id, name, op_type_value, default_days, status, remark
- 返回类型：Name(id='Supplier', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`self._validate_fields`, `self._get_or_raise`, `ValidationError`, `float`, `self._resolve_op_type_id`, `self._normalize_text`, `transaction`

### `SupplierService.delete()` [公开]
- 位置：第 197-212 行
- 参数：supplier_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`self._validate_fields`, `self._get_or_raise`, `has_part_operation_reference`, `has_batch_operation_reference`, `has_external_group_reference`, `ValidationError`, `BusinessError`, `transaction`

### `SupplierService.build_existing_for_excel()` [公开]
- 位置：第 217-230 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（14 处）：
  - `web/routes/equipment_excel_machines.py:145` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/equipment_excel_machines.py:189` [Route] `existing = m_svc.build_existing_for_excel()`
  - `web/routes/equipment_excel_machines.py:265` [Route] `existing = m_svc.build_existing_for_excel()`
  - `web/routes/excel_demo.py:30` [Route] `return OperatorService(conn, op_logger=None).build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:87` [Route] `existing = op_svc.build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:113` [Route] `existing = op_svc.build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:199` [Route] `existing = op_svc.build_existing_for_excel()`
  - `web/routes/personnel_excel_operators.py:345` [Route] `existing = OperatorService(g.db, op_logger=getattr(g, "op_logger", None)).build_`
  - `web/routes/process_excel_op_types.py:114` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_op_types.py:137` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_op_types.py:194` [Route] `existing = op_type_svc.build_existing_for_excel()`
  - `web/routes/process_excel_suppliers.py:87` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_suppliers.py:110` [Route] `existing = svc.build_existing_for_excel()`
  - `web/routes/process_excel_suppliers.py:204` [Route] `existing = supplier_svc.build_existing_for_excel()`
- **被调用者**（2 个）：`list`, `op_types.get`

### `SupplierService.list_for_export_rows()` [公开]
- 位置：第 232-239 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/process_excel_suppliers.py:358` [Route] `rows = SupplierService(g.db, op_logger=getattr(g, "op_logger", None)).list_for_e`
- **被调用者**（1 个）：`list_for_export`

### `SupplierService.ensure_replace_allowed()` [公开]
- 位置：第 241-251 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `core/services/equipment/machine_excel_import_service.py:60` [Service] `self.machine_svc.ensure_replace_allowed()`
  - `core/services/personnel/operator_excel_import_service.py:44` [Service] `self.svc.ensure_replace_allowed()`
  - `core/services/process/op_type_excel_import_service.py:42` [Service] `self.svc.ensure_replace_allowed()`
  - `core/services/process/supplier_excel_import_service.py:57` [Service] `self.svc.ensure_replace_allowed()`
- **被调用者**（4 个）：`has_any_part_operation_reference`, `has_any_batch_operation_reference`, `has_any_external_group_reference`, `BusinessError`

## core/services/scheduler/batch_excel_import.py（Service 层）

### `import_batches_from_preview_rows()` [公开]
- 位置：第 10-107 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/batch_service.py:399` [Service] `return batch_excel_import.import_batches_from_preview_rows(`
- **被调用者**（17 个）：`list`, `execute_preview_rows_transactional`, `stats.to_dict`, `len`, `bool`, `set`, `svc.delete_all_no_tx`, `strip`, `int`, `get`, `parts_cache.get`, `svc.update_no_tx`, `svc.create_no_tx`, `svc.create_batch_from_template_no_tx`, `svc.list`

## core/services/scheduler/batch_service.py（Service 层）

### `BatchService.__init__()` [私有]
- 位置：第 21-37 行
- 参数：conn, logger, op_logger, template_resolver
- 返回类型：无注解

### `BatchService._normalize_text()` [私有]
- 位置：第 43-44 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `BatchService._normalize_int()` [私有]
- 位置：第 47-48 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `BatchService._safe_float()` [私有]
- 位置：第 51-59 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `BatchService._normalize_date()` [私有]
- 位置：第 62-91 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `BatchService._validate_enum()` [私有]
- 位置：第 94-107 行
- 参数：value, allowed, field
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `BatchService._get_or_raise()` [私有]
- 位置：第 109-113 行
- 参数：batch_id
- 返回类型：Name(id='Batch', ctx=Load())

### `BatchService._default_template_resolver()` [私有]
- 位置：第 115-125 行
- 参数：part_no, part_name, route_raw, no_tx
- 返回类型：Constant(value=None, kind=None)

### `BatchService._invoke_template_resolver()` [私有]
- 位置：第 127-140 行
- 参数：part_no, part_name, route_raw, no_tx
- 返回类型：Constant(value=None, kind=None)

### `BatchService._load_template_ops_with_fallback()` [私有]
- 位置：第 142-164 行
- 参数：part_no, part
- 返回类型：无注解

### `BatchService.list()` [公开]
- 位置：第 169-188 行
- 参数：status, priority, part_no
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `web/routes/dashboard.py:23` [Route] `pending_count = len(batch_svc.list(status="pending"))`
  - `web/routes/dashboard.py:24` [Route] `scheduled_count = len(batch_svc.list(status="scheduled"))`
  - `web/routes/material.py:106` [Route] `batches = batch_svc.list()`
  - `web/routes/scheduler_batches.py:38` [Route] `batches = batch_svc.list(status=status if status else None)`
  - `web/routes/scheduler_batches.py:110` [Route] `batches = batch_svc.list(status=status if status else None)`
  - `web/routes/scheduler_excel_batches.py:62` [Route] `existing = {b.batch_id: b for b in batch_svc.list()}`
- **被调用者**（1 个）：`self._validate_enum`

### `BatchService.get()` [公开]
- 位置：第 190-194 行
- 参数：batch_id
- 返回类型：Name(id='Batch', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_batches.py:332` [Route] `b = batch_svc.get(batch_id)`
  - `web/routes/scheduler_batch_detail.py:198` [Route] `b = batch_svc.get(batch_id)`
- **被调用者**（3 个）：`self._normalize_text`, `self._get_or_raise`, `ValidationError`

### `BatchService.create()` [公开]
- 位置：第 196-266 行
- 参数：batch_id, part_no, quantity, due_date, priority, ready_status, ready_date, status, remark, part_name
- 返回类型：Name(id='Batch', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`self._normalize_text`, `self._normalize_int`, `self._normalize_date`, `self._validate_enum`, `get`, `self._get_or_raise`, `ValidationError`, `BusinessError`, `transaction`, `self.create_no_tx`, `int`

### `BatchService.create_no_tx()` [公开]
- 位置：第 268-277 行
- 参数：payload
- 返回类型：Name(id='Batch', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/batch_excel_import.py:64` [Service] `svc.create_no_tx(`
- **被调用者**（4 个）：`create`, `isinstance`, `Batch.from_row`, `b.to_dict`

### `BatchService.update()` [公开]
- 位置：第 279-358 行
- 参数：batch_id, part_no, quantity, due_date, priority, ready_status, ready_date, status, remark, part_name
- 返回类型：Name(id='Batch', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_batches.py:249` [Route] `batch_svc.update(`
- **被调用者**（11 个）：`self._normalize_text`, `self._get_or_raise`, `ValidationError`, `get`, `self._normalize_int`, `int`, `self._normalize_date`, `self._validate_enum`, `BusinessError`, `transaction`, `self.update_no_tx`

### `BatchService.update_no_tx()` [公开]
- 位置：第 360-367 行
- 参数：batch_id, updates
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/batch_excel_import.py:50` [Service] `svc.update_no_tx(`
- **被调用者**（1 个）：`update`

### `BatchService.delete()` [公开]
- 位置：第 369-377 行
- 参数：batch_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/scheduler_batches.py:180` [Route] `batch_svc.delete(batch_id)`
  - `web/routes/scheduler_batches.py:204` [Route] `batch_svc.delete(bid)`
- **被调用者**（4 个）：`self._normalize_text`, `self._get_or_raise`, `ValidationError`, `transaction`

### `BatchService.delete_all_no_tx()` [公开]
- 位置：第 379-387 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `web/routes/process_excel_routes.py:225` [Route] `part_svc.delete_all_no_tx()`
  - `web/routes/scheduler_excel_calendar.py:355` [Route] `cal_svc.delete_all_no_tx()`
  - `core/services/scheduler/batch_excel_import.py:31` [Service] `svc.delete_all_no_tx()`
  - `core/services/scheduler/calendar_service.py:101` [Service] `self._admin.delete_all_no_tx()`
- **被调用者**（1 个）：`delete_all`

### `BatchService.import_from_preview_rows()` [公开]
- 位置：第 389-407 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/scheduler_excel_batches.py:349` [Route] `import_stats = svc.import_from_preview_rows(`
- **被调用者**（2 个）：`batch_excel_import.import_batches_from_preview_rows`, `bool`

### `BatchService.copy_batch()` [公开]
- 位置：第 409-410 行
- 参数：source_batch_id, new_batch_id
- 返回类型：Name(id='Batch', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_batches.py:277` [Route] `b2 = batch_svc.copy_batch(bid, new_id)`
- **被调用者**（1 个）：`batch_copy.copy_batch`

### `BatchService.create_batch_from_template()` [公开]
- 位置：第 415-473 行
- 参数：batch_id, part_no, quantity, due_date, priority, ready_status, ready_date, remark, rebuild_ops, strict_mode
- 返回类型：Name(id='Batch', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_batches.py:155` [Route] `b = batch_svc.create_batch_from_template(`
  - `web/routes/scheduler_batches.py:335` [Route] `batch_svc.create_batch_from_template(`
- **被调用者**（13 个）：`self._normalize_text`, `self._normalize_int`, `self._normalize_date`, `self._validate_enum`, `get`, `self._load_template_ops_with_fallback`, `self._get_or_raise`, `ValidationError`, `BusinessError`, `transaction`, `self.create_batch_from_template_no_tx`, `bool`, `int`

### `BatchService.create_batch_from_template_no_tx()` [公开]
- 位置：第 475-500 行
- 参数：batch_id, part_no, quantity, due_date, priority, ready_status, ready_date, remark, rebuild_ops, strict_mode
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/batch_excel_import.py:80` [Service] `svc.create_batch_from_template_no_tx(`
- **被调用者**（2 个）：`batch_template_ops.create_batch_from_template_no_tx`, `bool`

### `BatchService.list_operations()` [公开]
- 位置：第 502-507 行
- 参数：batch_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/scheduler_batches.py:167` [Route] `flash(f"已创建批次并生成工序：{b.batch_id}（共 {len(batch_svc.list_operations(b.batch_id))} 道`
  - `web/routes/scheduler_batches.py:346` [Route] `cnt = len(batch_svc.list_operations(b.batch_id))`
- **被调用者**（4 个）：`self._normalize_text`, `self._get_or_raise`, `list_by_batch`, `ValidationError`

## core/services/scheduler/batch_template_ops.py（Service 层）

### `_normalize_source()` [私有]
- 位置：第 9-15 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_ensure_batch_exists_for_template_ops()` [私有]
- 位置：第 18-52 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)

### `_build_batch_op_payload()` [私有]
- 位置：第 55-72 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `create_batch_from_template_no_tx()` [公开]
- 位置：第 75-132 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)
- **调用者**（3 处）：
  - `core/services/scheduler/batch_excel_import.py:80` [Service] `svc.create_batch_from_template_no_tx(`
  - `core/services/scheduler/batch_service.py:460` [Service] `self.create_batch_from_template_no_tx(`
  - `core/services/scheduler/batch_service.py:488` [Service] `batch_template_ops.create_batch_from_template_no_tx(`
- **被调用者**（13 个）：`svc._normalize_text`, `svc._validate_enum`, `get`, `svc._load_template_ops_with_fallback`, `_ensure_batch_exists_for_template_ops`, `ValidationError`, `BusinessError`, `int`, `_normalize_source`, `create`, `bool`, `getattr`, `_build_batch_op_payload`

## core/services/scheduler/config_presets.py（Service 层）

### `builtin_presets()` [公开]
- 位置：第 12-48 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/config_service.py:255` [Service] `return preset_ops.builtin_presets(self)`
- **被调用者**（3 个）：`svc._default_snapshot`, `ScheduleConfigSnapshot`, `base.to_dict`

### `snapshot_close()` [公开]
- 位置：第 51-77 行
- 参数：a, b
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/config_service.py:259` [Service] `return preset_ops.snapshot_close(a, b)`
- **被调用者**（5 个）：`all`, `_eq_float`, `int`, `abs`, `float`

### `get_snapshot_from_repo()` [公开]
- 位置：第 80-113 行
- 参数：svc
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/config_service.py:265` [Service] `return preset_ops.get_snapshot_from_repo(self, strict_mode=bool(strict_mode))`
- **被调用者**（5 个）：`build_schedule_config_snapshot`, `float`, `str`, `int`, `bool`

### `ensure_builtin_presets()` [公开]
- 位置：第 116-153 行
- 参数：svc
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `core/services/scheduler/config_service.py:262` [Service] `preset_ops.ensure_builtin_presets(self, existing_keys=existing_keys)`
- **被调用者**（12 个）：`builtin_presets`, `svc._preset_key`, `presets_to_create.append`, `transaction`, `get_snapshot_from_repo`, `svc._default_snapshot`, `set`, `svc._active_preset_update`, `list_all`, `json.dumps`, `snapshot_close`, `snap.to_dict`

### `list_presets()` [公开]
- 位置：第 156-168 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/scheduler_batches.py:55` [Route] `presets = cfg_svc.list_presets()`
  - `web/routes/scheduler_config.py:285` [Route] `presets = cfg_svc.list_presets()`
  - `core/services/scheduler/config_service.py:290` [Service] `return preset_ops.list_presets(self)`
- **被调用者**（8 个）：`svc.ensure_defaults`, `list_all`, `out.sort`, `out.append`, `startswith`, `str`, `len`, `x.get`

### `save_preset()` [公开]
- 位置：第 171-186 行
- 参数：svc, name
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_config.py:340` [Route] `saved = cfg_svc.save_preset(name)`
  - `core/services/scheduler/config_service.py:293` [Service] `return preset_ops.save_preset(self, name)`
- **被调用者**（11 个）：`svc._normalize_text`, `svc._is_builtin_preset`, `svc.get_snapshot`, `json.dumps`, `ValidationError`, `len`, `snap.to_dict`, `transaction`, `set`, `svc._active_preset_update`, `svc._preset_key`

### `delete_preset()` [公开]
- 位置：第 189-201 行
- 参数：svc, name
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/scheduler_config.py:355` [Route] `cfg_svc.delete_preset(name)`
  - `core/services/scheduler/config_service.py:296` [Service] `preset_ops.delete_preset(self, name)`
- **被调用者**（9 个）：`svc._normalize_text`, `svc._is_builtin_preset`, `svc.get_active_preset`, `ValidationError`, `transaction`, `delete`, `svc._preset_key`, `svc._active_preset_update`, `set`

### `normalize_preset_snapshot()` [公开]
- 位置：第 204-218 行
- 参数：svc, data
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/config_service.py:299` [Service] `return preset_ops.normalize_preset_snapshot(self, data)`
- **被调用者**（2 个）：`svc._default_snapshot`, `normalize_preset_snapshot_dict`

### `apply_preset()` [公开]
- 位置：第 221-264 行
- 参数：svc, name
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_config.py:322` [Route] `applied = cfg_svc.apply_preset(name)`
  - `core/services/scheduler/config_service.py:302` [Service] `return preset_ops.apply_preset(self, name)`
- **被调用者**（17 个）：`svc._normalize_text`, `svc.ensure_defaults`, `get_value`, `normalize_preset_snapshot`, `ValidationError`, `svc._preset_key`, `BusinessError`, `json.loads`, `svc._active_preset_update`, `transaction`, `set_batch`, `strip`, `str`, `isinstance`, `ValueError`

## core/services/scheduler/config_service.py（Service 层）

### `ConfigService.__init__()` [私有]
- 位置：第 64-69 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ConfigService._normalize_text()` [私有]
- 位置：第 75-76 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ConfigService._normalize_weight()` [私有]
- 位置：第 79-95 行
- 参数：value, field
- 返回类型：Name(id='float', ctx=Load())

### `ConfigService.normalize_weight()` [公开]
- 位置：第 98-104 行
- 参数：value, field
- 返回类型：Name(id='float', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/scheduler_config.py:398` [Route] `pw_f = cfg_svc.normalize_weight(pw_v, field="优先级权重")`
  - `web/routes/scheduler_config.py:399` [Route] `dw_f = cfg_svc.normalize_weight(dw_v, field="交期权重")`
- **被调用者**（1 个）：`ConfigService._normalize_weight`

### `ConfigService._normalize_weights_triplet()` [私有]
- 位置：第 107-157 行
- 参数：priority_weight, due_weight, ready_weight
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService.ensure_defaults()` [公开]
- 位置：第 159-215 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（3 处）：
  - `core/services/scheduler/config_presets.py:157` [Service] `svc.ensure_defaults()`
  - `core/services/scheduler/config_presets.py:226` [Service] `svc.ensure_defaults()`
  - `core/services/system/system_config_service.py:138` [Service] `self.ensure_defaults(backup_keep_days_default=backup_keep_days_default)`
- **被调用者**（6 个）：`self._ensure_builtin_presets`, `to_set.append`, `transaction`, `list_all`, `set`, `str`

### `ConfigService._preset_key()` [私有]
- 位置：第 221-222 行
- 参数：name
- 返回类型：Name(id='str', ctx=Load())

### `ConfigService._is_builtin_preset()` [私有]
- 位置：第 225-231 行
- 参数：name
- 返回类型：Name(id='bool', ctx=Load())

### `ConfigService._default_snapshot()` [私有]
- 位置：第 233-252 行
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

### `ConfigService.get_active_preset()` [公开]
- 位置：第 267-271 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（3 处）：
  - `web/routes/scheduler_batches.py:56` [Route] `active_preset = cfg_svc.get_active_preset()`
  - `web/routes/scheduler_config.py:286` [Route] `active_preset = cfg_svc.get_active_preset()`
  - `core/services/scheduler/config_presets.py:196` [Service] `active = svc.get_active_preset()`
- **被调用者**（4 个）：`self.ensure_defaults`, `get_value`, `strip`, `str`

### `ConfigService._active_preset_update()` [私有]
- 位置：第 273-279 行
- 参数：name
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ConfigService._set_active_preset()` [私有]
- 位置：第 281-284 行
- 参数：name
- 返回类型：Constant(value=None, kind=None)

### `ConfigService.mark_active_preset_custom()` [公开]
- 位置：第 286-287 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/scheduler_config.py:319` [Route] `cfg_svc.mark_active_preset_custom()`
  - `web/routes/scheduler_config.py:408` [Route] `cfg_svc.mark_active_preset_custom()`
- **被调用者**（1 个）：`self._set_active_preset`

### `ConfigService.list_presets()` [公开]
- 位置：第 289-290 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/scheduler_batches.py:55` [Route] `presets = cfg_svc.list_presets()`
  - `web/routes/scheduler_config.py:285` [Route] `presets = cfg_svc.list_presets()`
- **被调用者**（1 个）：`preset_ops.list_presets`

### `ConfigService.save_preset()` [公开]
- 位置：第 292-293 行
- 参数：name
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:340` [Route] `saved = cfg_svc.save_preset(name)`
- **被调用者**（1 个）：`preset_ops.save_preset`

### `ConfigService.delete_preset()` [公开]
- 位置：第 295-296 行
- 参数：name
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:355` [Route] `cfg_svc.delete_preset(name)`
- **被调用者**（1 个）：`preset_ops.delete_preset`

### `ConfigService._normalize_preset_snapshot()` [私有]
- 位置：第 298-299 行
- 参数：data
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())

### `ConfigService.apply_preset()` [公开]
- 位置：第 301-302 行
- 参数：name
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:322` [Route] `applied = cfg_svc.apply_preset(name)`
- **被调用者**（1 个）：`preset_ops.apply_preset`

### `ConfigService.get()` [公开]
- 位置：第 305-314 行
- 参数：config_key, default
- 返回类型：Name(id='Any', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`self.ensure_defaults`, `get_value`, `str`

### `ConfigService.get_available_strategies()` [公开]
- 位置：第 319-320 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/scheduler_batches.py:54` [Route] `strategies = cfg_svc.get_available_strategies()`
  - `web/routes/scheduler_config.py:283` [Route] `strategies = cfg_svc.get_available_strategies()`
- **被调用者**（1 个）：`get`

### `ConfigService.get_snapshot()` [公开]
- 位置：第 322-324 行
- 参数：无
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（8 处）：
  - `web/routes/scheduler_batches.py:53` [Route] `cfg = cfg_svc.get_snapshot()`
  - `web/routes/scheduler_batch_detail.py:214` [Route] `prefer_primary_skill = ConfigService(g.db, logger=getattr(g, "app_logger", None)`
  - `web/routes/scheduler_config.py:282` [Route] `cfg = cfg_svc.get_snapshot()`
  - `web/routes/scheduler_config.py:395` [Route] `cur = cfg_svc.get_snapshot()`
  - `web/routes/system_utils.py:135` [Route] `return svc.get_snapshot(backup_keep_days_default=int(current_app.config.get("BAC`
  - `core/services/scheduler/config_presets.py:180` [Service] `snap = svc.get_snapshot()`
  - `core/services/scheduler/schedule_service.py:284` [Service] `cfg = cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`
  - `core/services/system/system_maintenance_service.py:85` [Service] `cfg = cfg_svc.get_snapshot(backup_keep_days_default=int(backup_keep_days_default`
- **被调用者**（3 个）：`self.ensure_defaults`, `self._get_snapshot_from_repo`, `bool`

### `ConfigService.set_strategy()` [公开]
- 位置：第 329-336 行
- 参数：sort_strategy
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:366` [Route] `cfg_svc.set_strategy(form.get("sort_strategy"))`
- **被调用者**（4 个）：`self._normalize_text`, `ValidationError`, `transaction`, `set`

### `ConfigService.set_weights()` [公开]
- 位置：第 338-349 行
- 参数：priority_weight, due_weight, ready_weight, require_sum_1
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:403` [Route] `cfg_svc.set_weights(pw_f, dw_f, max(0.0, float(rw_f)), require_sum_1=True)`
- **被调用者**（4 个）：`self._normalize_weights_triplet`, `transaction`, `set`, `str`

### `ConfigService.restore_default()` [公开]
- 位置：第 351-381 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:433` [Route] `cfg_svc.restore_default()`
- **被调用者**（4 个）：`self._active_preset_update`, `transaction`, `set_batch`, `str`

### `ConfigService.set_dispatch()` [公开]
- 位置：第 383-401 行
- 参数：dispatch_mode, dispatch_rule
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:370` [Route] `cfg_svc.set_dispatch(form.get("dispatch_mode"), form.get("dispatch_rule"))`
- **被调用者**（6 个）：`lower`, `ValidationError`, `transaction`, `set`, `strip`, `str`

### `ConfigService.set_auto_assign_enabled()` [公开]
- 位置：第 403-407 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:371` [Route] `cfg_svc.set_auto_assign_enabled(form.get("auto_assign_enabled"))`
- **被调用者**（5 个）：`lower`, `transaction`, `set`, `strip`, `str`

### `ConfigService.set_ortools()` [公开]
- 位置：第 409-419 行
- 参数：enabled, time_limit_seconds
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:372` [Route] `cfg_svc.set_ortools(form.get("ortools_enabled"), form.get("ortools_time_limit_se`
- **被调用者**（8 个）：`lower`, `max`, `int`, `transaction`, `set`, `strip`, `str`, `parse_finite_int`

### `ConfigService.set_prefer_primary_skill()` [公开]
- 位置：第 421-430 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:368` [Route] `cfg_svc.set_prefer_primary_skill(form.get("prefer_primary_skill"))`
- **被调用者**（5 个）：`lower`, `transaction`, `set`, `strip`, `str`

### `ConfigService.set_enforce_ready_default()` [公开]
- 位置：第 432-441 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:369` [Route] `cfg_svc.set_enforce_ready_default(form.get("enforce_ready_default"))`
- **被调用者**（5 个）：`lower`, `transaction`, `set`, `strip`, `str`

### `ConfigService.set_holiday_default_efficiency()` [公开]
- 位置：第 443-460 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:367` [Route] `cfg_svc.set_holiday_default_efficiency(form.get("holiday_default_efficiency"))`
- **被调用者**（7 个）：`float`, `ValidationError`, `transaction`, `set`, `strip`, `str`, `parse_finite_float`

### `ConfigService.set_algo_mode()` [公开]
- 位置：第 462-467 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:376` [Route] `cfg_svc.set_algo_mode(algo_mode)`
- **被调用者**（6 个）：`lower`, `ValidationError`, `transaction`, `set`, `strip`, `str`

### `ConfigService.set_time_budget_seconds()` [公开]
- 位置：第 469-475 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:384` [Route] `cfg_svc.set_time_budget_seconds(tb)`
- **被调用者**（8 个）：`int`, `max`, `ValidationError`, `transaction`, `set`, `strip`, `parse_finite_int`, `str`

### `ConfigService.set_objective()` [公开]
- 位置：第 477-482 行
- 参数：value
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:380` [Route] `cfg_svc.set_objective(objective)`
- **被调用者**（6 个）：`lower`, `ValidationError`, `transaction`, `set`, `strip`, `str`

### `ConfigService.set_freeze_window()` [公开]
- 位置：第 484-494 行
- 参数：enabled, days
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:386` [Route] `cfg_svc.set_freeze_window(form.get("freeze_window_enabled"), form.get("freeze_wi`
- **被调用者**（8 个）：`lower`, `max`, `int`, `transaction`, `set`, `strip`, `str`, `parse_finite_int`

## core/services/scheduler/config_snapshot.py（Service 层）

### `ScheduleConfigSnapshot.to_dict()` [公开]
- 位置：第 32-51 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
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
  - `web/routes/process_parts.py:90` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:91` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:92` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:121` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:85` [Route] `supplier=s.to_dict(),`
  - `web/routes/scheduler_batches.py:45` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:68` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:117` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:186` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:230` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/scheduler_resource_dispatch.py:51` [Route] `for key, value in request.args.to_dict(flat=True).items():`
  - `web/routes/scheduler_resource_dispatch.py:188` [Route] `return redirect(url_for("scheduler.resource_dispatch_page", **request.args.to_di`
  - `web/routes/system_backup.py:45` [Route] `settings=cfg.to_dict(),`
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
  - `core/services/process/route_parser.py:58` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:78` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:79` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
  - `core/services/process/supplier_excel_import_service.py:114` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:104` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:276` [Service] `self.batch_repo.create(b.to_dict())`
  - `core/services/scheduler/calendar_admin.py:317` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:328` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:384` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:389` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:210` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config_presets.py:20` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:29` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:37` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:129` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config_presets.py:181` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/gantt_contract.py:70` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:164` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:206` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_optimizer.py:195` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:209` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:257` [Service] `cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(`
  - `core/services/scheduler/schedule_optimizer_steps.py:163` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:190` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:284` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:311` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_summary.py:46` [Service] `obj = to_dict()`
  - `core/services/scheduler/schedule_summary.py:581` [Service] `"metrics": best_metrics.to_dict() if best_metrics is not None else None,`
- **被调用者**（2 个）：`float`, `int`

### `build_schedule_config_snapshot()` [公开]
- 位置：第 54-160 行
- 参数：repo
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/config_presets.py:104` [Service] `return build_schedule_config_snapshot(`
- **被调用者**（18 个）：`_choice`, `_get_float`, `repo.get_value`, `to_yes_no`, `_yes_no`, `_get_int`, `max`, `ScheduleConfigSnapshot`, `tuple`, `lower`, `float`, `str`, `int`, `ValidationError`, `bool`

## core/services/scheduler/config_validator.py（Service 层）

### `normalize_preset_snapshot()` [公开]
- 位置：第 11-154 行
- 参数：data
- 返回类型：Name(id='ScheduleConfigSnapshot', ctx=Load())
- **调用者**（2 处）：
  - `core/services/scheduler/config_presets.py:238` [Service] `snap = normalize_preset_snapshot(svc, data)`
  - `core/services/scheduler/config_service.py:299` [Service] `return preset_ops.normalize_preset_snapshot(self, data)`
- **被调用者**（23 个）：`_valid_norm`, `lower`, `_get_float`, `max`, `_yesno`, `data.get`, `_get_int`, `ScheduleConfigSnapshot`, `set`, `tuple`, `parse_finite_float`, `float`, `ValidationError`, `to_yes_no`, `int`

## core/services/scheduler/resource_pool_builder.py（Service 层）

### `_skill_rank()` [私有]
- 位置：第 13-22 行
- 参数：v
- 返回类型：Name(id='int', ctx=Load())

### `_active_machine_ids()` [私有]
- 位置：第 25-26 行
- 参数：machines
- 返回类型：Name(id='set', ctx=Load())

### `_op_type_ids_for_ops()` [私有]
- 位置：第 29-35 行
- 参数：algo_ops
- 返回类型：Name(id='set', ctx=Load())

### `_machines_by_op_type()` [私有]
- 位置：第 38-53 行
- 参数：machines
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_active_operator_ids()` [私有]
- 位置：第 56-61 行
- 参数：svc
- 返回类型：Name(id='set', ctx=Load())

### `_build_operator_machine_maps()` [私有]
- 位置：第 64-90 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_sort_operators_by_machine()` [私有]
- 位置：第 93-99 行
- 参数：operators_by_machine
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `load_machine_downtimes()` [公开]
- 位置：第 102-197 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:366` [Service] `downtime_map = load_machine_downtimes(`
- **被调用者**（18 个）：`MachineDowntimeRepository`, `svc._format_dt`, `sorted`, `join`, `getattr`, `dt_repo.list_active_after`, `int`, `list`, `strip`, `str`, `svc._normalize_datetime`, `intervals.sort`, `partial_fail_mids.append`, `len`, `warnings.append`

### `build_resource_pool()` [公开]
- 位置：第 200-268 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:375` [Service] `resource_pool, pool_warnings = build_resource_pool(self, cfg=cfg, algo_ops=algo_`
- **被调用者**（13 个）：`to_yes_no`, `list`, `_active_machine_ids`, `_op_type_ids_for_ops`, `_machines_by_op_type`, `_active_operator_ids`, `list_simple_rows`, `_build_operator_machine_maps`, `_sort_operators_by_machine`, `getattr`, `warnings.append`, `str`, `warning`

### `extend_downtime_map_for_resource_pool()` [公开]
- 位置：第 271-366 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:388` [Service] `downtime_map = extend_downtime_map_for_resource_pool(`
- **被调用者**（21 个）：`to_yes_no`, `MachineDowntimeRepository`, `svc._format_dt`, `sorted`, `join`, `getattr`, `isinstance`, `dt_repo.list_active_after`, `int`, `list`, `resource_pool.get`, `strip`, `str`, `svc._normalize_datetime`, `intervals.sort`

## core/services/scheduler/schedule_optimizer.py（Service 层）

### `_score_tuple()` [私有]
- 位置：第 36-45 行
- 参数：score
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_compact_attempts()` [私有]
- 位置：第 48-71 行
- 参数：attempts
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_run_local_search()` [私有]
- 位置：第 74-232 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `optimize_schedule()` [公开]
- 位置：第 235-583 行
- 参数：无
- 返回类型：Name(id='OptimizationOutcome', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:401` [Service] `outcome = optimize_schedule(`
- **被调用者**（61 个）：`GreedyScheduler`, `parse_strategy`, `_norm_text`, `int`, `max`, `batches.values`, `_cfg_choices`, `str`, `time.time`, `_run_ortools_warmstart`, `_run_multi_start`, `_run_local_search`, `OptimizationOutcome`, `hasattr`, `cfg.to_dict`

## core/services/scheduler/schedule_optimizer_steps.py（Service 层）

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

### `_cfg_float()` [私有]
- 位置：第 28-41 行
- 参数：_cfg_value, key, default
- 返回类型：Name(id='float', ctx=Load())

### `_scheduler_accepts_strict_mode()` [私有]
- 位置：第 44-55 行
- 参数：scheduler
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_schedule_with_optional_strict_mode()` [私有]
- 位置：第 58-74 行
- 参数：scheduler
- 返回类型：无注解

### `_run_ortools_warmstart()` [私有]
- 位置：第 77-202 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_run_multi_start()` [私有]
- 位置：第 205-314 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

## core/services/scheduler/schedule_service.py（Service 层）

### `_normalized_status_text()` [私有]
- 位置：第 43-44 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `ScheduleService.__init__()` [私有]
- 位置：第 56-74 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `ScheduleService._normalize_text()` [私有]
- 位置：第 80-81 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleService._is_reschedulable_operation()` [私有]
- 位置：第 84-86 行
- 参数：op
- 返回类型：Name(id='bool', ctx=Load())

### `ScheduleService._normalize_float()` [私有]
- 位置：第 89-90 行
- 参数：value, field, allow_none
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleService._get_batch_or_raise()` [私有]
- 位置：第 92-96 行
- 参数：batch_id
- 返回类型：Name(id='Batch', ctx=Load())

### `ScheduleService._get_op_or_raise()` [私有]
- 位置：第 98-102 行
- 参数：op_id
- 返回类型：Name(id='BatchOperation', ctx=Load())

### `ScheduleService._get_template_and_group_for_op()` [私有]
- 位置：第 104-105 行
- 参数：op
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `ScheduleService._format_dt()` [私有]
- 位置：第 108-109 行
- 参数：dt
- 返回类型：Name(id='str', ctx=Load())

### `ScheduleService._normalize_datetime()` [私有]
- 位置：第 112-126 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `ScheduleService.list_batch_operations()` [公开]
- 位置：第 131-132 行
- 参数：batch_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/scheduler_batch_detail.py:199` [Route] `ops = sch_svc.list_batch_operations(batch_id=b.batch_id)`
- **被调用者**（1 个）：`op_edit.list_batch_operations`

### `ScheduleService.get_operation()` [公开]
- 位置：第 134-135 行
- 参数：op_id
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（4 处）：
  - `web/routes/scheduler_ops.py:14` [Route] `op = sch_svc.get_operation(op_id)`
  - `core/services/scheduler/operation_edit_service.py:30` [Service] `op = get_operation(svc, op_id)`
  - `core/services/scheduler/operation_edit_service.py:126` [Service] `op = get_operation(svc, op_id)`
  - `core/services/scheduler/operation_edit_service.py:172` [Service] `op = get_operation(svc, op_id)`
- **被调用者**（1 个）：`op_edit.get_operation`

### `ScheduleService.get_external_merge_hint()` [公开]
- 位置：第 137-141 行
- 参数：op_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/scheduler_batch_detail.py:188` [Route] `d["merge_hint"] = sch_svc.get_external_merge_hint(op.id)`
- **被调用者**（1 个）：`op_edit.get_external_merge_hint`

### `ScheduleService.update_internal_operation()` [公开]
- 位置：第 146-163 行
- 参数：op_id, machine_id, operator_id, setup_hours, unit_hours, status
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_ops.py:22` [Route] `sch_svc.update_internal_operation(`
- **被调用者**（1 个）：`op_edit.update_internal_operation`

### `ScheduleService.update_external_operation()` [公开]
- 位置：第 168-181 行
- 参数：op_id, supplier_id, ext_days, status
- 返回类型：Name(id='BatchOperation', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_ops.py:34` [Route] `sch_svc.update_external_operation(op_id=op_id, supplier_id=supplier_id, ext_days`
- **被调用者**（1 个）：`op_edit.update_external_operation`

### `ScheduleService.run_schedule()` [公开]
- 位置：第 186-211 行
- 参数：batch_ids, start_dt, end_date, created_by, simulate, enforce_ready, strict_mode
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/scheduler_run.py:40` [Route] `result = sch_svc.run_schedule(`
  - `web/routes/scheduler_week_plan.py:179` [Route] `result = sch_svc.run_schedule(`
  - `core/services/scheduler/schedule_optimizer.py:254` [Service] `说明：为保证兼容，本函数尽量保持与原 `ScheduleService.run_schedule()` 相同的口径与留痕结构。`
- **被调用者**（4 个）：`_RUN_SCHEDULE_LOCK.acquire`, `ValidationError`, `self._run_schedule_impl`, `_RUN_SCHEDULE_LOCK.release`

### `ScheduleService._run_schedule_impl()` [私有]
- 位置：第 213-531 行
- 参数：batch_ids, start_dt, end_date, created_by, simulate, enforce_ready, strict_mode
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

## core/services/scheduler/schedule_summary.py（Service 层）

### `_serialize_end_date()` [私有]
- 位置：第 15-28 行
- 参数：end_date
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_due_exclusive()` [私有]
- 位置：第 31-34 行
- 参数：due_date
- 返回类型：Name(id='datetime', ctx=Load())

### `_config_snapshot_dict()` [私有]
- 位置：第 37-85 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_cfg_value()` [私有]
- 位置：第 88-91 行
- 参数：cfg, key, default
- 返回类型：Name(id='Any', ctx=Load())

### `_warning_list()` [私有]
- 位置：第 94-119 行
- 参数：value
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_merge_warning_lists()` [私有]
- 位置：第 122-130 行
- 参数：primary, extra
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_append_summary_warning()` [私有]
- 位置：第 133-151 行
- 参数：summary, message
- 返回类型：Name(id='bool', ctx=Load())

### `_counter_dict()` [私有]
- 位置：第 154-165 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_comparison_metric()` [私有]
- 位置：第 168-176 行
- 参数：objective_name
- 返回类型：Name(id='str', ctx=Load())

### `_best_score_schema()` [私有]
- 位置：第 179-215 行
- 参数：objective_name
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_summary_size_bytes()` [私有]
- 位置：第 218-219 行
- 参数：obj
- 返回类型：Name(id='int', ctx=Load())

### `_apply_summary_size_guard()` [私有]
- 位置：第 222-286 行
- 参数：result_summary_obj
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_finish_time_by_batch()` [私有]
- 位置：第 289-298 行
- 参数：results
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_overdue_items()` [私有]
- 位置：第 301-348 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_compute_result_status()` [私有]
- 位置：第 351-360 行
- 参数：summary
- 返回类型：Name(id='str', ctx=Load())

### `_frozen_batch_ids()` [私有]
- 位置：第 363-370 行
- 参数：operations
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_extract_freeze_warnings()` [私有]
- 位置：第 373-380 行
- 参数：summary
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_compute_downtime_degradation()` [私有]
- 位置：第 383-457 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_compute_resource_pool_degradation()` [私有]
- 位置：第 460-473 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_hard_constraints()` [私有]
- 位置：第 476-486 行
- 参数：cfg
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `build_result_summary()` [公开]
- 位置：第 489-647 行
- 参数：svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `core/services/scheduler/schedule_service.py:459` [Service] `overdue_items, result_status, result_summary_obj, result_summary_json, time_cost`
- **被调用者**（34 个）：`_finish_time_by_batch`, `_build_overdue_items`, `_compute_result_status`, `int`, `_frozen_batch_ids`, `_warning_list`, `_merge_warning_lists`, `_extract_freeze_warnings`, `_compute_downtime_degradation`, `bool`, `downtime_state.get`, `list`, `_compute_resource_pool_degradation`, `_hard_constraints`, `_counter_dict`

## verify_manual_styles.py（Other 层）

### `_prepare_env()` [私有]
- 位置：第 18-24 行
- 参数：tmpdir
- 返回类型：Constant(value=None, kind=None)

### `_load_app()` [私有]
- 位置：第 27-33 行
- 参数：repo_root
- 返回类型：无注解

### `_mode_headers()` [私有]
- 位置：第 36-37 行
- 参数：ui_mode
- 返回类型：Name(id='dict', ctx=Load())

### `_build_url()` [私有]
- 位置：第 40-42 行
- 参数：app, endpoint
- 返回类型：Name(id='str', ctx=Load())

### `_check()` [私有]
- 位置：第 45-50 行
- 参数：condition, message, failures
- 返回类型：Constant(value=None, kind=None)

### `_has_css_rule()` [私有]
- 位置：第 53-54 行
- 参数：css_content, pattern
- 返回类型：Name(id='bool', ctx=Load())

### `main()` [公开]
- 位置：第 57-125 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`print`, `_check`, `css_file.read_text`, `Path`, `_prepare_env`, `_load_app`, `app.test_client`, `css_file.exists`, `sys.exit`, `tempfile.mkdtemp`, `_has_css_rule`, `_build_url`, `client.get`, `resp.get_data`, `_mode_headers`

## web/routes/process_excel_routes.py（Route 层）

### `_strict_mode_enabled()` [私有]
- 位置：第 29-30 行
- 参数：raw_value
- 返回类型：Name(id='bool', ctx=Load())

### `_validate_route_row()` [私有]
- 位置：第 33-53 行
- 参数：part_svc, row
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_render_excel_routes_page()` [私有]
- 位置：第 56-83 行
- 参数：无
- 返回类型：无注解

### `excel_routes_page()` [公开]
- 位置：第 87-98 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`bp.get`, `PartService`, `svc.build_existing_for_excel_routes`, `_render_excel_routes_page`, `getattr`

### `excel_routes_preview()` [公开]
- 位置：第 102-147 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`bp.post`, `time.time`, `_parse_mode`, `_strict_mode_enabled`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `PartService`, `part_svc.build_existing_for_excel_routes`, `ExcelService`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`, `_render_excel_routes_page`

### `excel_routes_confirm()` [公开]
- 位置：第 151-287 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（37 个）：`bp.post`, `time.time`, `_parse_mode`, `_strict_mode_enabled`, `get`, `strip`, `_ensure_unique_ids`, `PartService`, `part_svc.build_existing_for_excel_routes`, `ExcelService`, `excel_svc.preview_import`, `TransactionManager`, `int`, `log_excel_import`, `flash_import_result`

### `excel_routes_template()` [公开]
- 位置：第 291-338 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_routes_export()` [公开]
- 位置：第 342-372 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `PartService`, `svc.list`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`

## web/routes/process_parts.py（Route 层）

### `_strict_mode_enabled()` [私有]
- 位置：第 17-18 行
- 参数：raw_value
- 返回类型：Name(id='bool', ctx=Load())

### `_summarize_active_ops()` [私有]
- 位置：第 21-26 行
- 参数：ops
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_ops_by_group()` [私有]
- 位置：第 29-38 行
- 参数：active_ops
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `list_parts()` [公开]
- 位置：第 42-64 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.get`, `PartService`, `parse_page_args`, `svc.list`, `paginate_rows`, `render_template`, `strip`, `view_rows.append`, `getattr`, `len`

### `create_part()` [公开]
- 位置：第 68-82 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`bp.post`, `get`, `_strict_mode_enabled`, `PartService`, `svc.create`, `flash`, `redirect`, `getattr`, `url_for`

### `part_detail()` [公开]
- 位置：第 86-125 行
- 参数：part_no
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（17 个）：`bp.get`, `PartService`, `p_svc.get_template_detail`, `to_dict`, `_summarize_active_ops`, `set`, `_build_ops_by_group`, `render_template`, `o.to_dict`, `gr.to_dict`, `p_svc.calc_deletable_external_group_ids`, `getattr`, `list`, `v.to_dict`, `SupplierService`

### `update_part()` [公开]
- 位置：第 129-136 行
- 参数：part_no
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `get`, `PartService`, `svc.update`, `flash`, `redirect`, `url_for`, `getattr`

### `delete_part()` [公开]
- 位置：第 140-147 行
- 参数：part_no
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.post`, `PartService`, `redirect`, `svc.delete`, `flash`, `url_for`, `getattr`

### `bulk_delete_parts()` [公开]
- 位置：第 151-172 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `getlist`, `PartService`, `flash`, `redirect`, `join`, `url_for`, `getattr`, `svc.delete`, `failed.append`, `len`, `str`

### `reparse_part()` [公开]
- 位置：第 176-194 行
- 参数：part_no
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `get`, `_strict_mode_enabled`, `PartService`, `time.time`, `int`, `flash`, `redirect`, `svc.reparse_and_save`, `url_for`, `getattr`, `len`

### `update_internal_hours()` [公开]
- 位置：第 198-204 行
- 参数：part_no, seq
- 返回类型：无注解
- **调用者**（1 处）：
  - `core/services/process/part_operation_hours_excel_import_service.py:76` [Service] `self.part_svc.update_internal_hours(part_no=part_no, seq=seq, setup_hours=sh, un`
- **被调用者**（8 个）：`bp.post`, `get`, `PartService`, `svc.update_internal_hours`, `flash`, `redirect`, `url_for`, `getattr`

### `set_group_mode()` [公开]
- 位置：第 208-235 行
- 参数：part_no, group_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`bp.post`, `get`, `_strict_mode_enabled`, `items`, `ExternalGroupService`, `redirect`, `svc.set_merge_mode`, `flash`, `url_for`, `k.startswith`, `int`, `getattr`, `k.replace`, `_merge_mode_zh`

### `delete_group()` [公开]
- 位置：第 239-243 行
- 参数：part_no, group_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `PartService`, `svc.delete_external_group`, `flash`, `redirect`, `url_for`, `getattr`, `result.get`

## web/routes/scheduler_batches.py（Route 层）

### `_strict_mode_enabled()` [私有]
- 位置：第 21-22 行
- 参数：raw_value
- 返回类型：Name(id='bool', ctx=Load())

### `batches_page()` [公开]
- 位置：第 26-89 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（27 个）：`bp.get`, `BatchService`, `ConfigService`, `strip`, `parse_page_args`, `batch_svc.list`, `paginate_rows`, `cfg_svc.get_snapshot`, `cfg_svc.get_available_strategies`, `cfg_svc.list_presets`, `cfg_svc.get_active_preset`, `render_template`, `view_rows.append`, `ScheduleHistoryQueryService`, `hist_q.list_recent`

### `batches_manage_page()` [公开]
- 位置：第 93-137 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（16 个）：`bp.get`, `BatchService`, `strip`, `parse_page_args`, `batch_svc.list`, `paginate_rows`, `PartService`, `p_svc.list`, `render_template`, `view_rows.append`, `getattr`, `get`, `b.to_dict`, `_priority_zh`, `_ready_zh`

### `create_batch()` [公开]
- 位置：第 141-171 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`bp.post`, `get`, `_strict_mode_enabled`, `BatchService`, `batch_svc.create_batch_from_template`, `flash`, `redirect`, `getattr`, `url_for`, `len`, `batch_svc.list_operations`

### `delete_batch()` [公开]
- 位置：第 175-189 行
- 参数：batch_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.post`, `BatchService`, `strip`, `_safe_next_url`, `batch_svc.delete`, `flash`, `redirect`, `getattr`, `url_for`, `get`

### `bulk_delete_batches()` [公开]
- 位置：第 193-214 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `getlist`, `BatchService`, `flash`, `redirect`, `join`, `url_for`, `getattr`, `batch_svc.delete`, `failed.append`, `len`, `str`

### `_next_batch_id_like()` [私有]
- 位置：第 217-237 行
- 参数：src, exists_fn
- 返回类型：Name(id='str', ctx=Load())

### `_bulk_update_one_batch()` [私有]
- 位置：第 240-260 行
- 参数：batch_svc, bid
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `bulk_copy_batches()` [公开]
- 位置：第 264-293 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（16 个）：`bp.post`, `getlist`, `BatchService`, `flash`, `redirect`, `url_for`, `getattr`, `_next_batch_id_like`, `batch_svc.copy_batch`, `mappings.append`, `str`, `failed.append`, `exception`, `len`, `join`

### `bulk_update_batches()` [公开]
- 位置：第 297-325 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.post`, `getlist`, `get`, `BatchService`, `flash`, `redirect`, `strip`, `_bulk_update_one_batch`, `url_for`, `remark.strip`, `getattr`, `str`, `failed.append`, `len`, `join`

### `generate_ops()` [公开]
- 位置：第 329-350 行
- 参数：batch_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `BatchService`, `_strict_mode_enabled`, `batch_svc.get`, `redirect`, `get`, `batch_svc.create_batch_from_template`, `len`, `flash`, `url_for`, `getattr`, `batch_svc.list_operations`

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

### `_strict_mode_enabled()` [私有]
- 位置：第 57-58 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())

### `_build_existing_preview_data()` [私有]
- 位置：第 61-76 行
- 参数：batch_svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_parts_cache()` [私有]
- 位置：第 79-81 行
- 参数：conn
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_template_ops_snapshot()` [私有]
- 位置：第 84-89 行
- 参数：conn, rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_batch_baseline_extra_state()` [私有]
- 位置：第 92-115 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_render_excel_batches_page()` [私有]
- 位置：第 118-147 行
- 参数：无
- 返回类型：无注解

### `_extract_error_rows()` [私有]
- 位置：第 150-151 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_format_error_sample()` [私有]
- 位置：第 154-156 行
- 参数：error_rows
- 返回类型：Name(id='str', ctx=Load())

### `excel_batches_page()` [公开]
- 位置：第 160-184 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.get`, `BatchService`, `_render_excel_batches_page`, `getattr`, `svc.list`, `list`, `existing.values`

### `excel_batches_preview()` [公开]
- 位置：第 188-274 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（31 个）：`bp.post`, `time.time`, `_parse_mode`, `_parse_auto_generate_ops`, `_strict_mode_enabled`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `BatchService`, `_build_parts_cache`, `get_batch_row_validate_and_normalize`, `ExcelService`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`

### `excel_batches_confirm()` [公开]
- 位置：第 278-381 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（37 个）：`bp.post`, `time.time`, `_parse_mode`, `get`, `strip`, `_strict_mode_enabled`, `_parse_auto_generate_ops`, `_parse_preview_rows_json`, `_ensure_unique_ids`, `BatchService`, `_build_existing_preview_data`, `_build_parts_cache`, `get_batch_row_validate_and_normalize`, `ExcelService`, `excel_svc.preview_import`

### `excel_batches_template()` [公开]
- 位置：第 385-431 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

### `excel_batches_export()` [公开]
- 位置：第 435-467 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `time.time`, `BatchService`, `svc.list`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `getattr`, `template_def.get`, `len`

## web/routes/scheduler_run.py（Route 层）

### `_strict_mode_enabled()` [私有]
- 位置：第 11-12 行
- 参数：raw_value
- 返回类型：Name(id='bool', ctx=Load())

### `_parse_optional_checkbox_flag()` [私有]
- 位置：第 15-25 行
- 参数：name
- 返回类型：无注解

### `run_schedule()` [公开]
- 位置：第 29-87 行
- 参数：无
- 返回类型：无注解
- **调用者**（2 处）：
  - `web/routes/scheduler_week_plan.py:179` [Route] `result = sch_svc.run_schedule(`
  - `core/services/scheduler/schedule_optimizer.py:254` [Service] `说明：为保证兼容，本函数尽量保持与原 `ScheduleService.run_schedule()` 相同的口径与留痕结构。`
- **被调用者**（19 个）：`bp.post`, `getlist`, `_parse_optional_checkbox_flag`, `_strict_mode_enabled`, `ScheduleService`, `redirect`, `get`, `sch_svc.run_schedule`, `result.get`, `flash`, `url_for`, `getattr`, `join`, `summary.get`, `exception`

## web/routes/scheduler_week_plan.py（Route 层）

### `_get_int_arg()` [私有]
- 位置：第 19-26 行
- 参数：name, default
- 返回类型：Name(id='int', ctx=Load())

### `_strict_mode_enabled()` [私有]
- 位置：第 29-30 行
- 参数：raw_value
- 返回类型：Name(id='bool', ctx=Load())

### `_parse_optional_checkbox_flag()` [私有]
- 位置：第 33-43 行
- 参数：name
- 返回类型：无注解

### `week_plan_page()` [公开]
- 位置：第 47-89 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（18 个）：`bp.get`, `_get_int_arg`, `strip`, `GanttService`, `svc.resolve_week_range`, `list_versions`, `svc.get_week_plan_rows`, `render_template`, `svc.get_latest_version_or_1`, `data.get`, `int`, `getattr`, `ScheduleHistoryQueryService`, `isoformat`, `len`

### `week_plan_export()` [公开]
- 位置：第 93-158 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（21 个）：`bp.get`, `time.time`, `_get_int_arg`, `strip`, `GanttService`, `svc.get_week_plan_rows`, `int`, `data.get`, `build_xlsx_bytes`, `log_excel_export`, `send_file`, `getattr`, `flash`, `redirect`, `exception`

### `simulate_schedule()` [公开]
- 位置：第 162-213 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（19 个）：`bp.post`, `getlist`, `_parse_optional_checkbox_flag`, `_strict_mode_enabled`, `ScheduleService`, `get`, `flash`, `redirect`, `sch_svc.run_schedule`, `int`, `isoformat`, `url_for`, `getattr`, `result.get`, `summary.get`

---
- 分析函数/方法数：289
- 找到调用关系：544 处
- 跨层边界风险：2 项
