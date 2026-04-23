# 附录 D：验证命令全集

> 本附录仅为汇总导航，不替代各子 plan 的“最小验证命令”。真正执行时，先看对应子 plan 正文，再按需要来本附录拷长命令块。**如本附录与子 plan 正文存在差异，一律以子 plan 正文为准。** 本轮已按 `SP06~SP10` 的细化稿同步刷新；若后续子 plan 更新了最小验证命令，本附录也必须同步更新。

## SP01：入口文档与开发依赖

```bash
python -m ruff --version
python -m pytest --collect-only tests -q
python -c "from pathlib import Path; assert Path('README.md').exists(); assert Path('开发文档/README.md').exists(); assert Path('audit/README.md').exists(); assert Path('tests/regression/__init__.py').exists()"
```

## SP02：质量门禁与治理台账

```bash
python -m pytest tests/test_architecture_fitness.py -q
python -m pytest tests/regression_runtime_probe_resolution.py -q
python -m pytest tests/test_win7_launcher_runtime_paths.py -q
python -m pytest tests/regression_plugin_bootstrap_config_failure_visible.py -q
python scripts/run_quality_gate.py
```

## SP03：启动链静默回退专项

```bash
python -m pytest tests/regression_runtime_probe_resolution.py -q
python -m pytest tests/test_win7_launcher_runtime_paths.py -q
python -m pytest tests/regression_startup_host_portfile.py -q
python -m pytest tests/regression_plugin_bootstrap_config_failure_visible.py -q
python -m pytest tests/regression_runtime_stop_cli.py -q
python -m pytest tests/test_architecture_fitness.py -q
python scripts/run_quality_gate.py
```

## SP04：请求级容器与仓储束

```bash
python tests/regression_schedule_service_passes_algo_stats_to_summary.py
python tests/regression_schedule_service_reschedulable_contract.py
python tests/regression_schedule_input_collector_contract.py
python tests/regression_schedule_service_empty_reschedulable_rejected.py
python tests/regression_schedule_service_all_frozen_short_circuit.py
python tests/regression_schedule_orchestrator_contract.py
python -m pytest tests/regression_schedule_service_facade_delegation.py -q
python -m pytest tests/regression_request_scope_app_logger_binding.py -q
# 本批新建：请求级容器惰性构造 / 失败传播回归
python -m pytest tests/regression_request_services_lazy_construction.py -q
python -m pytest tests/regression_request_services_failure_propagation.py -q
python -m pytest tests/regression_scheduler_run_no_reschedulable_flash.py -q
python -m pytest tests/regression_dashboard_overdue_count_tolerance.py -q
python -m pytest tests/regression_gantt_contract_snapshot.py -q
python -m pytest tests/regression_scheduler_week_plan_no_reschedulable_flash.py -q
python -m pytest tests/regression_config_service_active_preset_custom_sync.py -q
python -m pytest tests/regression_scheduler_strict_mode_dispatch_flags.py -q
python -m pytest tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py -q
python -m pytest tests/test_ui_mode.py -q
python -m pytest tests/test_architecture_fitness.py -q
# 残余直接装配搜索口径：需显式看到 scheduler_analysis.py / system_history.py 等命中
python -c "import re; from pathlib import Path; pats={'g.db': re.compile(r'(?:Service|Repository)\(g\.db\b'), 'conn': re.compile(r'(?:Service|Repository)\(conn\b')}; hits=[]; [hits.append(f'{name}:{p}:{i+1}') for name,pat in pats.items() for p in Path('web/routes').rglob('*.py') for i,l in enumerate(p.read_text(encoding='utf-8').splitlines()) if pat.search(l)]; print('\n'.join(hits)); print(f'TOTAL={len(hits)}')"
# 非 Service / Repository 口径补充：scheduler_excel_batches.py 中仍显式把 g.db 传给校验函数
python -c "from pathlib import Path; p=Path('web/routes/scheduler_excel_batches.py'); hits=[f'{i+1}:{l.strip()}' for i,l in enumerate(p.read_text(encoding='utf-8').splitlines()) if 'get_batch_row_validate_and_normalize(g.db' in l]; print('\n'.join(hits) or 'NO_HITS')"
# web/ui_mode.py 直接构造残余核对
python -c "from pathlib import Path; hits=[i+1 for i,l in enumerate(Path('web/ui_mode.py').read_text(encoding='utf-8').splitlines()) if 'SystemConfigService(conn' in l]; print(f'web/ui_mode.py:SystemConfigService(conn lines={hits})')"
```

## SP05：目录骨架与路径门禁

```bash
python -m ruff check --select F401 core/services/scheduler/config/ core/services/scheduler/run/ core/services/scheduler/summary/ core/services/scheduler/batch/ core/services/scheduler/dispatch/ core/services/scheduler/gantt/ core/services/scheduler/calendar/ core/services/scheduler/config_service.py core/services/scheduler/config_snapshot.py core/services/scheduler/config_validator.py core/services/scheduler/freeze_window.py core/services/scheduler/schedule_input_builder.py core/services/scheduler/schedule_input_collector.py core/services/scheduler/schedule_orchestrator.py core/services/scheduler/schedule_optimizer.py core/services/scheduler/schedule_optimizer_steps.py core/services/scheduler/schedule_persistence.py core/services/scheduler/schedule_service.py core/services/scheduler/schedule_summary.py core/services/scheduler/schedule_summary_types.py core/services/scheduler/__init__.py
python -m ruff check --select F401 web/routes/domains/scheduler/ web/routes/navigation_utils.py web/routes/scheduler.py web/routes/scheduler_config.py web/routes/scheduler_run.py web/routes/scheduler_batches.py web/routes/scheduler_batch_detail.py web/routes/scheduler_ops.py web/routes/scheduler_analysis.py web/routes/scheduler_week_plan.py web/routes/scheduler_excel_batches.py web/routes/scheduler_excel_calendar.py web/routes/system_utils.py
python -c 'from pathlib import Path; import ast; forbidden=[Path(p) for p in ("web/routes/scheduler_bp.py","web/routes/scheduler_pages.py","web/routes/scheduler_resource_dispatch.py","web/routes/scheduler_calendar_pages.py","web/routes/scheduler_gantt.py","web/routes/scheduler_utils.py")]; existing=[p.as_posix() for p in forbidden if p.exists()]; assert not existing, existing; expected=[Path(p) for p in ("web/routes/domains/scheduler/scheduler_bp.py","web/routes/domains/scheduler/scheduler_pages.py","web/routes/domains/scheduler/scheduler_resource_dispatch.py","web/routes/domains/scheduler/scheduler_calendar_pages.py","web/routes/domains/scheduler/scheduler_gantt.py","web/routes/domains/scheduler/scheduler_utils.py")]; missing=[p.as_posix() for p in expected if not p.exists()]; assert not missing, missing; empty_domains=[Path(f"web/routes/domains/{name}/__init__.py") for name in ("process","personnel","equipment","system")]; missing_empty=[p.as_posix() for p in empty_domains if not p.exists()]; assert not missing_empty, missing_empty; importing=[p.as_posix() for p in empty_domains if any(isinstance(n,(ast.Import,ast.ImportFrom)) for n in ast.parse(p.read_text(encoding="utf-8")).body)]; assert not importing, importing; root_hits=[]; [root_hits.append(f"{p}:{needle}") for p in (Path("web/routes/process.py"),Path("web/routes/personnel.py"),Path("web/routes/equipment.py"),Path("web/routes/system.py")) if p.exists() for needle in (".domains.process",".domains.personnel",".domains.equipment",".domains.system") if needle in p.read_text(encoding="utf-8")]; assert not root_hits, root_hits; print("OK SP05 topology empty domains and no-compat roots")'
python -c 'import importlib; pairs=[("core.services.scheduler.schedule_optimizer","core.services.scheduler.run.schedule_optimizer"),("core.services.scheduler.schedule_optimizer_steps","core.services.scheduler.run.schedule_optimizer_steps"),("web.routes.scheduler_config","web.routes.domains.scheduler.scheduler_config"),("web.routes.scheduler_run","web.routes.domains.scheduler.scheduler_run"),("web.routes.scheduler_week_plan","web.routes.domains.scheduler.scheduler_week_plan"),("web.routes.scheduler_excel_calendar","web.routes.domains.scheduler.scheduler_excel_calendar"),("web.routes.scheduler_batches","web.routes.domains.scheduler.scheduler_batches"),("web.routes.scheduler_analysis","web.routes.domains.scheduler.scheduler_analysis"),("web.routes.scheduler_batch_detail","web.routes.domains.scheduler.scheduler_batch_detail"),("web.routes.scheduler_ops","web.routes.domains.scheduler.scheduler_ops")]; exec("for old_name, new_name in pairs:\n old = importlib.import_module(old_name)\n new = importlib.import_module(new_name)\n assert old is new, f\"{old_name} != {new_name}\"\n print(f\"OK strong compat {old_name} == {new_name}\")")'
python -c 'import importlib; svc = importlib.import_module("core.services.scheduler.schedule_service"); assert hasattr(svc.ScheduleService, "_run_schedule_impl"); required=["collect_schedule_run_input","orchestrate_schedule_run","persist_schedule","optimize_schedule"]; missing=[name for name in required if not hasattr(svc, name)]; assert not missing, missing; print("OK schedule_service root patch surface retained")'
python -m pytest tests/regression_sp05_path_topology_contract.py -q
python -c 'from pathlib import Path; text = Path("tools/quality_gate_ledger.py").read_text(encoding="utf-8"); blocked = ["web/routes/scheduler_batches.py", "web/routes/scheduler_analysis.py", "web/routes/scheduler_excel_batches.py"]; assert not any(item in text for item in blocked), blocked; print("OK ledger template paths updated")'
python -m pytest tests/regression_template_urlfor_endpoints.py tests/regression_page_manual_registry.py -q
python -m pytest tests/regression_safe_next_url_hardening.py tests/regression_safe_next_url_observability.py tests/regression_system_request_services_contract.py tests/regression_request_scope_app_logger_binding.py tests/regression_manual_entry_scope.py tests/regression_dashboard_overdue_count_tolerance.py tests/test_schedule_summary_observability.py -q
python -m pytest tests/regression_scheduler_config_route_contract.py tests/regression_scheduler_config_manual_url_normalization.py tests/regression_scheduler_analysis_route_contract.py tests/regression_scheduler_batch_detail_route_contract.py tests/regression_scheduler_ops_update_route_contract.py tests/regression_scheduler_route_enforce_ready_tristate.py tests/regression_scheduler_run_surfaces_resource_pool_warning.py tests/regression_scheduler_excel_batches_helper_injection_contract.py tests/regression_scheduler_excel_calendar_uses_executor.py tests/regression_scheduler_excel_calendar_strict_numeric.py -q
python -m pytest tests/regression_config_service_active_preset_custom_sync.py tests/regression_config_snapshot_strict_numeric.py tests/regression_config_validator_preset_degradation.py tests/regression_freeze_window_fail_closed_contract.py tests/regression_schedule_input_builder_safe_float_parse.py tests/test_schedule_input_builder_strict_hours_and_ext_days.py tests/regression_schedule_input_builder_template_missing_surfaces_event.py -q
python -m pytest tests/regression_schedule_input_collector_contract.py tests/regression_schedule_orchestrator_contract.py tests/regression_schedule_persistence_reschedulable_contract.py tests/regression_schedule_summary_v11_contract.py tests/regression_schedule_summary_algo_warnings_union.py tests/regression_schedule_summary_fallback_counts_output.py tests/regression_due_exclusive_consistency.py tests/regression_schedule_summary_size_guard_large_lists.py tests/regression_schedule_service_facade_delegation.py tests/regression_dict_cfg_contract.py tests/regression_optimizer_zero_weight_cfg_preserved.py -q
python tests/regression_excel_routes_no_tx_surface_hidden.py
python tests/generate_conformance_report.py
python -m pytest tests/regression_quality_gate_scan_contract.py tests/test_source_merge_mode_constants.py tests/test_architecture_fitness.py tests/test_sync_debt_ledger.py -q
```

## SP06：配置单一事实源

```bash
python -m pytest tests/regression_config_snapshot_strict_numeric.py -q
python -m pytest tests/regression_config_service_active_preset_custom_sync.py -q
python -m pytest tests/regression_config_validator_preset_degradation.py -q
python -m pytest tests/regression_schedule_optimizer_cfg_float_strict_blank.py -q
python -m pytest tests/regression_optimizer_choice_case_normalization.py -q
python -m pytest tests/regression_objective_case_normalization.py -q
python -m pytest tests/regression_scheduler_apply_preset_reject_invalid_numeric.py -q
python -m pytest tests/regression_scheduler_objective_labels.py -q
python -c "from pathlib import Path; s1 = Path(r'core/services/scheduler/run/schedule_optimizer.py').read_text(encoding='utf-8'); s2 = Path(r'core/services/scheduler/run/schedule_optimizer_steps.py').read_text(encoding='utf-8'); s3 = Path(r'core/services/scheduler/summary/schedule_summary_freeze.py').read_text(encoding='utf-8'); assert '_cfg_value(' not in s1 and '_norm_text(' not in s1 and '_cfg_choices(' not in s1; assert 'VALID_STRATEGIES' not in s1 and 'VALID_DISPATCH_MODES' not in s1 and 'VALID_DISPATCH_RULES' not in s1; assert 'def _cfg_value' not in s2 and '_cfg_value(' not in s2; assert 'cfg_get(cfg, \"freeze_window_enabled\"' not in s3 and 'cfg_get(cfg, \"freeze_window_days\"' not in s3"
```

## SP07：排产主链边界收口

```bash
python -m pytest tests/regression_schedule_input_builder_safe_float_parse.py -q
python -m pytest tests/test_schedule_input_builder_strict_hours_and_ext_days.py -q
python -m pytest tests/regression_schedule_input_builder_template_missing_surfaces_event.py -q
python -m pytest tests/regression_schedule_service_strict_snapshot_guard.py -q
python -m pytest tests/regression_schedule_input_collector_contract.py -q
python tests/regression_schedule_service_passes_algo_stats_to_summary.py
python tests/regression_schedule_service_reschedulable_contract.py
python tests/regression_schedule_service_empty_reschedulable_rejected.py
python tests/regression_schedule_service_all_frozen_short_circuit.py
python -m pytest tests/regression_schedule_orchestrator_contract.py -q
python -m pytest tests/regression_build_outcome_contract.py -q
python -m pytest tests/regression_schedule_persistence_reject_empty_actionable_schedule.py -q
python -m pytest tests/regression_schedule_persistence_reschedulable_contract.py -q
python -m pytest tests/regression_schedule_summary_v11_contract.py -q
python -m pytest tests/regression_schedule_summary_cfg_snapshot_contract.py -q
python -m pytest tests/regression_schedule_summary_fallback_counts_output.py -q
python -m pytest tests/regression_schedule_summary_freeze_state_contract.py -q
python -m pytest tests/regression_schedule_summary_algo_warnings_union.py -q
python -m pytest tests/regression_scheduler_strict_mode_dispatch_flags.py -q
python -c "import re; from pathlib import Path; s1 = Path(r'core/services/scheduler/run/schedule_optimizer.py').read_text(encoding='utf-8'); s2 = Path(r'core/services/scheduler/run/schedule_optimizer_steps.py').read_text(encoding='utf-8'); s3 = Path(r'core/services/scheduler/schedule_service.py').read_text(encoding='utf-8'); s4 = Path(r'core/services/scheduler/run/schedule_orchestrator.py').read_text(encoding='utf-8'); s5 = Path(r'core/services/scheduler/run/schedule_input_contracts.py').read_text(encoding='utf-8'); s6 = Path(r'core/services/scheduler/run/schedule_persistence.py').read_text(encoding='utf-8'); s7 = Path(r'core/services/scheduler/run/schedule_template_lookup.py').read_text(encoding='utf-8'); s8 = Path(r'core/services/scheduler/summary/schedule_summary.py').read_text(encoding='utf-8'); s9 = Path(r'core/services/scheduler/run/schedule_input_builder.py').read_text(encoding='utf-8'); assert '_schedule_with_optional_strict_mode' not in (s1 + s2); assert '_scheduler_accepts_strict_mode' not in s2; assert '_normalize_optimizer_outcome' not in s4; assert re.search(r'best_metrics\s*=\s*.*metrics', s4); assert '_build_algo_operations_with_optional_outcome' not in s5 and '_build_freeze_window_seed_with_optional_meta' not in s5; assert '_get_template_and_group_for_op' not in (s7 + s9); assert '_aps_schedule_input_cache' not in (s3 + s7); assert (s3.count('def _normalized_status_text') + s6.count('def _normalized_status_text')) <= 1; assert s3.count('def _raise_schedule_empty_result') <= 1; assert 'getattr(orchestration.summary' not in s3; assert 'set(schedule_input.reschedulable_op_ids)' not in s3 and 'set(schedule_input.frozen_op_ids)' not in s3; assert 'except Exception:\n        return False' not in s8"
```

## SP08：算法拆分与数据基础设施

```bash
python -m pytest tests/test_greedy_scheduler_base_date.py -q
python -m pytest tests/regression_greedy_date_parsers.py -q
python -m pytest tests/regression_greedy_scheduler_algo_stats_auto_assign.py -q
python -m pytest tests/regression_greedy_scheduler_algo_stats_seed_counts.py -q
python -m pytest tests/regression_sgs_pre_sort_strict_nonfinite_rejected.py -q
python -m pytest tests/regression_weighted_tardiness_objective.py -q
python -m pytest tests/regression_ensure_schema_fastforward_empty_only.py -q
python -m pytest tests/regression_backup_restore_pending_verify_code.py -q
python -m pytest tests/regression_transaction_savepoint_nested.py -q
python -m pytest tests/test_query_services.py -q
python -m pytest tests/regression_models_numeric_parse_hybrid_safe.py -q
python -m pytest tests/regression_calendar_shift_start_invalid_visible.py -q
python -m pytest tests/regression_migrate_v4_sanitize_enum_text_fields.py -q
python -m pytest tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py -q
python -m pytest tests/regression_gantt_critical_chain_parse_contract.py -q
python tests/regression_gantt_critical_chain_cache_thread_safe.py
python -m pytest tests/test_architecture_fitness.py -q
python -c "from pathlib import Path; s = Path(r'core/services/scheduler/run/schedule_optimizer.py').read_text(encoding='utf-8'); assert 'def _parse_date(' not in s and 'def _parse_datetime(' not in s"
python -c "from pathlib import Path; s = Path(r'core/services/scheduler/gantt/gantt_critical_chain.py').read_text(encoding='utf-8'); assert 'def _parse_dt(' not in s"
```

## SP09：页面流程与前端协议

```bash
python scripts/build_static_assets.py
python tests/regression_scheduler_excel_calendar_uses_executor.py
python tests/regression_scheduler_excel_calendar_strict_numeric.py
python tests/regression_process_excel_part_operation_hours_import.py
python tests/regression_process_excel_part_operation_hours_source_row_num.py
python tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py
python tests/regression_excel_import_strict_reference_apply.py
python tests/regression_excel_preview_confirm_baseline_guard.py
python tests/regression_frontend_common_interactions.py
python tests/regression_gantt_url_persistence.py
python tests/regression_template_no_inline_event_jinja.py
python -m pytest tests/test_ui_mode.py -q
python tests/regression/page_boot_dom_contract.py
python tests/regression/template_inline_script_targets.py
python tests/regression/static_versioning_manifest_contract.py
python tests/regression/static_versioning_ui_v2_static.py
python -m pytest tests/test_architecture_fitness.py -q
```

## SP10：测试分层与文档收口

```bash
python -m pytest --collect-only
python -m pytest tests/architecture tests/regression -q
python tests/regression/regression_excel_import_strict_reference_apply.py
python tests/regression/regression_excel_preview_confirm_baseline_guard.py
python tests/regression/regression_scheduler_excel_calendar_uses_executor.py
python tests/regression/regression_scheduler_excel_calendar_strict_numeric.py
python tests/regression/regression_process_excel_part_operation_hours_import.py
python tests/regression/regression_process_excel_part_operation_hours_source_row_num.py
python tests/regression/regression_process_excel_part_operation_hours_append_fill_empty_only.py
python tests/regression/regression_frontend_common_interactions.py
python tests/regression/regression_template_no_inline_event_jinja.py
python -m pytest tests/regression/test_ui_mode.py -q
python tests/support/check_quickref_vs_routes.py
python -m pytest tests/architecture/test_architecture_fitness.py -q
python -m pytest --cov=core --cov=web --cov-report=term-missing
python -c "from pathlib import Path; root = Path('README.md').read_text(encoding='utf-8'); dev = Path('开发文档/README.md').read_text(encoding='utf-8'); assert Path('evidence/README.md').exists() and Path('audit/README.md').exists(); assert '开发文档/README.md' in root and 'evidence/README.md' in root and 'audit/README.md' in root and 'installer/README_WIN7_INSTALLER.md' in root; assert '系统速查表.md' in dev and '阶段留痕与验收记录.md' in dev"
```
