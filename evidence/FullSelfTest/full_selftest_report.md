# APS 全量自测汇总报告（不打包）

- 生成时间：2026-04-02 17:02:01
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- Python 可执行：`D:\py3.8\python.exe`
- 仓库根目录：`D:/Github/APS Test`
- fail_fast：false
- complex_repeat：1
- step_timeout_s：900

## 总结

- 结论：**PASS**
- 记录数：189

## 明细

| # | 脚本 | 结果 | exit | 耗时(s) | 证据(evidence) | runner日志 | 备注 |
|---:|---|---|---:|---:|---|---|---|
| 1 | `smoke_phase0_phase1.py` | PASS | 0 | 2.49 | evidence/Phase0_Phase1/smoke_test_report.md | evidence/FullSelfTest/logs/01_smoke_phase0_phase1.py.log.txt | - |
| 2 | `smoke_phase2.py` | PASS | 0 | 0.39 | evidence/Phase2/smoke_phase2_report.md | evidence/FullSelfTest/logs/02_smoke_phase2.py.log.txt | - |
| 3 | `smoke_phase3.py` | PASS | 0 | 1.09 | evidence/Phase3/smoke_phase3_report.md | evidence/FullSelfTest/logs/03_smoke_phase3.py.log.txt | - |
| 4 | `smoke_phase4.py` | PASS | 0 | 1.13 | evidence/Phase4/smoke_phase4_report.md | evidence/FullSelfTest/logs/04_smoke_phase4.py.log.txt | - |
| 5 | `smoke_phase5.py` | PASS | 0 | 1.20 | evidence/Phase5/smoke_phase5_report.md | evidence/FullSelfTest/logs/05_smoke_phase5.py.log.txt | - |
| 6 | `smoke_phase6.py` | PASS | 0 | 1.31 | evidence/Phase6/smoke_phase6_report.md | evidence/FullSelfTest/logs/06_smoke_phase6.py.log.txt | - |
| 7 | `smoke_phase7.py` | PASS | 0 | 1.64 | evidence/Phase7/smoke_phase7_report.md | evidence/FullSelfTest/logs/07_smoke_phase7.py.log.txt | - |
| 8 | `smoke_phase8.py` | PASS | 0 | 2.53 | evidence/Phase8/smoke_phase8_report.md | evidence/FullSelfTest/logs/08_smoke_phase8.py.log.txt | - |
| 9 | `smoke_phase9.py` | PASS | 0 | 27.01 | evidence/Phase9/smoke_phase9_report.md | evidence/FullSelfTest/logs/09_smoke_phase9.py.log.txt | - |
| 10 | `smoke_phase10_sgs_auto_assign.py` | PASS | 0 | 1.60 | evidence/Phase10/smoke_phase10_report.md | evidence/FullSelfTest/logs/10_smoke_phase10_sgs_auto_assign.py.log.txt | Phase10 报告显示 PASS：D:/Github/APS Test/evidence/Phase10/smoke_phase10_report.md |
| 11 | `smoke_web_phase0_5.py` | PASS | 0 | 3.07 | evidence/Phase0_to_Phase5/web_smoke_report.md | evidence/FullSelfTest/logs/11_smoke_web_phase0_5.py.log.txt | - |
| 12 | `smoke_web_phase0_6.py` | PASS | 0 | 2.85 | evidence/Phase0_to_Phase6/web_smoke_report.md | evidence/FullSelfTest/logs/12_smoke_web_phase0_6.py.log.txt | - |
| 13 | `smoke_e2e_excel_to_schedule.py` | PASS | 0 | 3.88 | evidence/FullE2E/excel_to_schedule_report.md | evidence/FullSelfTest/logs/13_smoke_e2e_excel_to_schedule.py.log.txt | - |
| 14 | `regression_app_db_path_no_dirname.py` | PASS | 0 | 2.77 | - | evidence/FullSelfTest/logs/14_regression_app_db_path_no_dirname.py.log.txt | - |
| 15 | `regression_app_new_ui_secret_key_runtime_ensure.py` | PASS | 0 | 2.77 | - | evidence/FullSelfTest/logs/15_regression_app_new_ui_secret_key_runtime_ensure.py.log.txt | - |
| 16 | `regression_app_new_ui_security_hardening_enabled.py` | PASS | 0 | 2.86 | - | evidence/FullSelfTest/logs/16_regression_app_new_ui_security_hardening_enabled.py.log.txt | - |
| 17 | `regression_app_new_ui_session_contract.py` | PASS | 0 | 2.76 | - | evidence/FullSelfTest/logs/17_regression_app_new_ui_session_contract.py.log.txt | - |
| 18 | `regression_auto_assign_empty_resource_pool.py` | PASS | 0 | 0.94 | - | evidence/FullSelfTest/logs/18_regression_auto_assign_empty_resource_pool.py.log.txt | - |
| 19 | `regression_auto_assign_fixed_operator_respects_op_type.py` | PASS | 0 | 0.94 | - | evidence/FullSelfTest/logs/19_regression_auto_assign_fixed_operator_respects_op_type.py.log.txt | - |
| 20 | `regression_auto_assign_persist_truthy_variants.py` | PASS | 0 | 1.92 | - | evidence/FullSelfTest/logs/20_regression_auto_assign_persist_truthy_variants.py.log.txt | - |
| 21 | `regression_batch_detail_linkage.py` | PASS | 0 | 2.87 | - | evidence/FullSelfTest/logs/21_regression_batch_detail_linkage.py.log.txt | - |
| 22 | `regression_batch_excel_import_strict_mode_hardfail_atomic.py` | PASS | 0 | 1.82 | - | evidence/FullSelfTest/logs/22_regression_batch_excel_import_strict_mode_hardfail_atomic.py.log.txt | - |
| 23 | `regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py` | PASS | 0 | 2.95 | - | evidence/FullSelfTest/logs/23_regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py.log.txt | - |
| 24 | `regression_batch_import_unchanged_no_rebuild.py` | PASS | 0 | 1.77 | - | evidence/FullSelfTest/logs/24_regression_batch_import_unchanged_no_rebuild.py.log.txt | - |
| 25 | `regression_batch_order_bid_unboundlocal.py` | PASS | 0 | 0.94 | - | evidence/FullSelfTest/logs/25_regression_batch_order_bid_unboundlocal.py.log.txt | - |
| 26 | `regression_batch_order_override_dedup.py` | PASS | 0 | 0.92 | - | evidence/FullSelfTest/logs/26_regression_batch_order_override_dedup.py.log.txt | - |
| 27 | `regression_batch_service_strict_mode_template_autoparse.py` | PASS | 0 | 1.82 | - | evidence/FullSelfTest/logs/27_regression_batch_service_strict_mode_template_autoparse.py.log.txt | - |
| 28 | `regression_calendar_export_normalization.py` | PASS | 0 | 2.95 | - | evidence/FullSelfTest/logs/28_regression_calendar_export_normalization.py.log.txt | - |
| 29 | `regression_calendar_no_tx_hardening.py` | PASS | 0 | 1.87 | - | evidence/FullSelfTest/logs/29_regression_calendar_no_tx_hardening.py.log.txt | - |
| 30 | `regression_calendar_pages_readside_normalization.py` | PASS | 0 | 2.96 | - | evidence/FullSelfTest/logs/30_regression_calendar_pages_readside_normalization.py.log.txt | - |
| 31 | `regression_calendar_shift_hours_roundtrip.py` | PASS | 0 | 1.93 | - | evidence/FullSelfTest/logs/31_regression_calendar_shift_hours_roundtrip.py.log.txt | - |
| 32 | `regression_calendar_shift_start_rollover.py` | PASS | 0 | 1.79 | - | evidence/FullSelfTest/logs/32_regression_calendar_shift_start_rollover.py.log.txt | - |
| 33 | `regression_check_manual_layout_runtime_resolution.py` | PASS | 0 | 2.80 | - | evidence/FullSelfTest/logs/33_regression_check_manual_layout_runtime_resolution.py.log.txt | - |
| 34 | `regression_common_broad_false_fixed.py` | PASS | 0 | 0.93 | - | evidence/FullSelfTest/logs/34_regression_common_broad_false_fixed.py.log.txt | - |
| 35 | `regression_config_manual_markdown.py` | PASS | 0 | 3.03 | - | evidence/FullSelfTest/logs/35_regression_config_manual_markdown.py.log.txt | - |
| 36 | `regression_config_snapshot_strict_numeric.py` | PASS | 0 | 1.79 | - | evidence/FullSelfTest/logs/36_regression_config_snapshot_strict_numeric.py.log.txt | - |
| 37 | `regression_dashboard_overdue_count_tolerance.py` | PASS | 0 | 2.89 | - | evidence/FullSelfTest/logs/37_regression_dashboard_overdue_count_tolerance.py.log.txt | - |
| 38 | `regression_deletion_validator_source_case_insensitive.py` | PASS | 0 | 1.70 | - | evidence/FullSelfTest/logs/38_regression_deletion_validator_source_case_insensitive.py.log.txt | - |
| 39 | `regression_dict_cfg_contract.py` | PASS | 0 | 1.77 | - | evidence/FullSelfTest/logs/39_regression_dict_cfg_contract.py.log.txt | - |
| 40 | `regression_dispatch_blocking_consistency.py` | PASS | 0 | 0.94 | - | evidence/FullSelfTest/logs/40_regression_dispatch_blocking_consistency.py.log.txt | - |
| 41 | `regression_dispatch_rule_case_insensitive.py` | PASS | 0 | 0.95 | - | evidence/FullSelfTest/logs/41_regression_dispatch_rule_case_insensitive.py.log.txt | - |
| 42 | `regression_dispatch_rules_nonfinite_proc_hours_safe.py` | PASS | 0 | 0.95 | - | evidence/FullSelfTest/logs/42_regression_dispatch_rules_nonfinite_proc_hours_safe.py.log.txt | - |
| 43 | `regression_dispatch_rules_priority_case_insensitive.py` | PASS | 0 | 0.95 | - | evidence/FullSelfTest/logs/43_regression_dispatch_rules_priority_case_insensitive.py.log.txt | - |
| 44 | `regression_downtime_overlap_skips_invalid_segments.py` | PASS | 0 | 0.96 | - | evidence/FullSelfTest/logs/44_regression_downtime_overlap_skips_invalid_segments.py.log.txt | - |
| 45 | `regression_due_exclusive_consistency.py` | PASS | 0 | 1.76 | - | evidence/FullSelfTest/logs/45_regression_due_exclusive_consistency.py.log.txt | - |
| 46 | `regression_due_exclusive_guard_contract.py` | PASS | 0 | 1.80 | - | evidence/FullSelfTest/logs/46_regression_due_exclusive_guard_contract.py.log.txt | - |
| 47 | `regression_efficiency_greater_than_one_shortens_hours.py` | PASS | 0 | 0.95 | - | evidence/FullSelfTest/logs/47_regression_efficiency_greater_than_one_shortens_hours.py.log.txt | - |
| 48 | `regression_ensure_schema_fastforward_empty_only.py` | PASS | 0 | 1.53 | - | evidence/FullSelfTest/logs/48_regression_ensure_schema_fastforward_empty_only.py.log.txt | - |
| 49 | `regression_excel_failure_semantics_contracts.py` | PASS | 0 | 1.87 | - | evidence/FullSelfTest/logs/49_regression_excel_failure_semantics_contracts.py.log.txt | - |
| 50 | `regression_excel_import_executor_status_gate.py` | PASS | 0 | 0.96 | - | evidence/FullSelfTest/logs/50_regression_excel_import_executor_status_gate.py.log.txt | - |
| 51 | `regression_excel_import_result_semantics.py` | PASS | 0 | 3.92 | - | evidence/FullSelfTest/logs/51_regression_excel_import_result_semantics.py.log.txt | - |
| 52 | `regression_excel_import_strict_reference_apply.py` | PASS | 0 | 1.83 | - | evidence/FullSelfTest/logs/52_regression_excel_import_strict_reference_apply.py.log.txt | - |
| 53 | `regression_excel_normalizers_mixed_case.py` | PASS | 0 | 2.08 | - | evidence/FullSelfTest/logs/53_regression_excel_normalizers_mixed_case.py.log.txt | - |
| 54 | `regression_excel_operator_calendar_cross_midnight.py` | PASS | 0 | 1.01 | - | evidence/FullSelfTest/logs/54_regression_excel_operator_calendar_cross_midnight.py.log.txt | - |
| 55 | `regression_excel_preview_confirm_baseline_guard.py` | PASS | 0 | 3.24 | - | evidence/FullSelfTest/logs/55_regression_excel_preview_confirm_baseline_guard.py.log.txt | - |
| 56 | `regression_excel_preview_confirm_extra_state_guard.py` | PASS | 0 | 3.38 | - | evidence/FullSelfTest/logs/56_regression_excel_preview_confirm_extra_state_guard.py.log.txt | - |
| 57 | `regression_excel_routes_no_tx_surface_hidden.py` | PASS | 0 | 0.94 | - | evidence/FullSelfTest/logs/57_regression_excel_routes_no_tx_surface_hidden.py.log.txt | - |
| 58 | `regression_excel_service_calc_changes_row.py` | PASS | 0 | 0.92 | - | evidence/FullSelfTest/logs/58_regression_excel_service_calc_changes_row.py.log.txt | - |
| 59 | `regression_excel_validators_yesno_mixed_case.py` | PASS | 0 | 1.02 | - | evidence/FullSelfTest/logs/59_regression_excel_validators_yesno_mixed_case.py.log.txt | - |
| 60 | `regression_exit_backup_maintenance.py` | PASS | 0 | 2.28 | - | evidence/FullSelfTest/logs/60_regression_exit_backup_maintenance.py.log.txt | - |
| 61 | `regression_exit_backup_reloader_parent_skip.py` | PASS | 0 | 2.25 | - | evidence/FullSelfTest/logs/61_regression_exit_backup_reloader_parent_skip.py.log.txt | - |
| 62 | `regression_exit_backup_respects_config.py` | PASS | 0 | 2.33 | - | evidence/FullSelfTest/logs/62_regression_exit_backup_respects_config.py.log.txt | - |
| 63 | `regression_external_group_service_compatible_mode_logs_fallback.py` | PASS | 0 | 1.77 | - | evidence/FullSelfTest/logs/63_regression_external_group_service_compatible_mode_logs_fallback.py.log.txt | - |
| 64 | `regression_external_group_service_merge_mode_case_insensitive.py` | PASS | 0 | 1.70 | - | evidence/FullSelfTest/logs/64_regression_external_group_service_merge_mode_case_insensitive.py.log.txt | - |
| 65 | `regression_external_group_service_strict_mode_blank_days.py` | PASS | 0 | 1.74 | - | evidence/FullSelfTest/logs/65_regression_external_group_service_strict_mode_blank_days.py.log.txt | - |
| 66 | `regression_external_merge_mode_case_insensitive.py` | PASS | 0 | 0.92 | - | evidence/FullSelfTest/logs/66_regression_external_merge_mode_case_insensitive.py.log.txt | - |
| 67 | `regression_freeze_window_bounds.py` | PASS | 0 | 2.03 | - | evidence/FullSelfTest/logs/67_regression_freeze_window_bounds.py.log.txt | - |
| 68 | `regression_frontend_common_interactions.py` | PASS | 0 | 0.92 | - | evidence/FullSelfTest/logs/68_regression_frontend_common_interactions.py.log.txt | - |
| 69 | `regression_gantt_contract_snapshot.py` | PASS | 0 | 2.97 | - | evidence/FullSelfTest/logs/69_regression_gantt_contract_snapshot.py.log.txt | - |
| 70 | `regression_gantt_critical_chain_cache_thread_safe.py` | PASS | 0 | 2.80 | - | evidence/FullSelfTest/logs/70_regression_gantt_critical_chain_cache_thread_safe.py.log.txt | - |
| 71 | `regression_gantt_offset_range_consistency.py` | PASS | 0 | 2.92 | - | evidence/FullSelfTest/logs/71_regression_gantt_offset_range_consistency.py.log.txt | - |
| 72 | `regression_gantt_status_mode_semantics.py` | PASS | 0 | 0.97 | - | evidence/FullSelfTest/logs/72_regression_gantt_status_mode_semantics.py.log.txt | - |
| 73 | `regression_gantt_url_persistence.py` | PASS | 0 | 2.89 | - | evidence/FullSelfTest/logs/73_regression_gantt_url_persistence.py.log.txt | - |
| 74 | `regression_greedy_date_parsers.py` | PASS | 0 | 1.00 | - | evidence/FullSelfTest/logs/74_regression_greedy_date_parsers.py.log.txt | - |
| 75 | `regression_greedy_scheduler_algo_stats_auto_assign.py` | PASS | 0 | 0.92 | - | evidence/FullSelfTest/logs/75_regression_greedy_scheduler_algo_stats_auto_assign.py.log.txt | - |
| 76 | `regression_greedy_scheduler_algo_stats_seed_counts.py` | PASS | 0 | 0.98 | - | evidence/FullSelfTest/logs/76_regression_greedy_scheduler_algo_stats_seed_counts.py.log.txt | - |
| 77 | `regression_improve_dispatch_modes.py` | PASS | 0 | 1.80 | - | evidence/FullSelfTest/logs/77_regression_improve_dispatch_modes.py.log.txt | - |
| 78 | `regression_lazy_select_orphan_option.py` | PASS | 0 | 2.91 | - | evidence/FullSelfTest/logs/78_regression_lazy_select_orphan_option.py.log.txt | - |
| 79 | `regression_maintenance_jobstate_retry_signal.py` | PASS | 0 | 1.13 | - | evidence/FullSelfTest/logs/79_regression_maintenance_jobstate_retry_signal.py.log.txt | - |
| 80 | `regression_maintenance_real_oplog_visibility.py` | PASS | 0 | 1.14 | - | evidence/FullSelfTest/logs/80_regression_maintenance_real_oplog_visibility.py.log.txt | - |
| 81 | `regression_maintenance_telemetry_isolation.py` | PASS | 0 | 1.17 | - | evidence/FullSelfTest/logs/81_regression_maintenance_telemetry_isolation.py.log.txt | - |
| 82 | `regression_maintenance_window_mutex.py` | PASS | 0 | 1.18 | - | evidence/FullSelfTest/logs/82_regression_maintenance_window_mutex.py.log.txt | - |
| 83 | `regression_manual_entry_scope.py` | PASS | 0 | 4.11 | - | evidence/FullSelfTest/logs/83_regression_manual_entry_scope.py.log.txt | - |
| 84 | `regression_metrics_horizon_semantics.py` | PASS | 0 | 0.98 | - | evidence/FullSelfTest/logs/84_regression_metrics_horizon_semantics.py.log.txt | - |
| 85 | `regression_metrics_to_dict_nonfinite_safe.py` | PASS | 0 | 0.93 | - | evidence/FullSelfTest/logs/85_regression_metrics_to_dict_nonfinite_safe.py.log.txt | - |
| 86 | `regression_migrate_backup_dir_none_creates_backup.py` | PASS | 0 | 1.09 | - | evidence/FullSelfTest/logs/86_regression_migrate_backup_dir_none_creates_backup.py.log.txt | - |
| 87 | `regression_migrate_v2_unify_workcalendar_day_type.py` | PASS | 0 | 1.52 | - | evidence/FullSelfTest/logs/87_regression_migrate_v2_unify_workcalendar_day_type.py.log.txt | - |
| 88 | `regression_migrate_v4_sanitize_enum_text_fields.py` | PASS | 0 | 1.57 | - | evidence/FullSelfTest/logs/88_regression_migrate_v4_sanitize_enum_text_fields.py.log.txt | - |
| 89 | `regression_migrate_v5_normalize_operator_machine_legacy_values.py` | PASS | 0 | 1.57 | - | evidence/FullSelfTest/logs/89_regression_migrate_v5_normalize_operator_machine_legacy_values.py.log.txt | - |
| 90 | `regression_migration_failfast_no_backup_storm.py` | PASS | 0 | 1.06 | - | evidence/FullSelfTest/logs/90_regression_migration_failfast_no_backup_storm.py.log.txt | - |
| 91 | `regression_migration_outcome_partial_no_upgrade.py` | PASS | 0 | 1.05 | - | evidence/FullSelfTest/logs/91_regression_migration_outcome_partial_no_upgrade.py.log.txt | - |
| 92 | `regression_migration_outcome_skip_no_upgrade.py` | PASS | 0 | 1.56 | - | evidence/FullSelfTest/logs/92_regression_migration_outcome_skip_no_upgrade.py.log.txt | - |
| 93 | `regression_model_enums_case_insensitive.py` | PASS | 0 | 0.97 | - | evidence/FullSelfTest/logs/93_regression_model_enums_case_insensitive.py.log.txt | - |
| 94 | `regression_models_numeric_parse_hybrid_safe.py` | PASS | 0 | 0.95 | - | evidence/FullSelfTest/logs/94_regression_models_numeric_parse_hybrid_safe.py.log.txt | - |
| 95 | `regression_objective_case_normalization.py` | PASS | 0 | 1.82 | - | evidence/FullSelfTest/logs/95_regression_objective_case_normalization.py.log.txt | - |
| 96 | `regression_operator_calendar_override_allows_work_on_global_holiday.py` | PASS | 0 | 1.86 | - | evidence/FullSelfTest/logs/96_regression_operator_calendar_override_allows_work_on_global_holiday.py.log.txt | - |
| 97 | `regression_operator_machine_detail_readside_normalization.py` | PASS | 0 | 3.10 | - | evidence/FullSelfTest/logs/97_regression_operator_machine_detail_readside_normalization.py.log.txt | - |
| 98 | `regression_operator_machine_missing_columns.py` | PASS | 0 | 1.16 | - | evidence/FullSelfTest/logs/98_regression_operator_machine_missing_columns.py.log.txt | - |
| 99 | `regression_optimizer_choice_case_normalization.py` | PASS | 0 | 6.82 | - | evidence/FullSelfTest/logs/99_regression_optimizer_choice_case_normalization.py.log.txt | - |
| 100 | `regression_optimizer_ortools_logging_exc_info_safe.py` | PASS | 0 | 1.81 | - | evidence/FullSelfTest/logs/100_regression_optimizer_ortools_logging_exc_info_safe.py.log.txt | - |
| 101 | `regression_optimizer_outcome_algo_stats.py` | PASS | 0 | 1.87 | - | evidence/FullSelfTest/logs/101_regression_optimizer_outcome_algo_stats.py.log.txt | - |
| 102 | `regression_optimizer_zero_weight_cfg_preserved.py` | PASS | 0 | 1.81 | - | evidence/FullSelfTest/logs/102_regression_optimizer_zero_weight_cfg_preserved.py.log.txt | - |
| 103 | `regression_optional_ready_constraint.py` | PASS | 0 | 1.92 | - | evidence/FullSelfTest/logs/103_regression_optional_ready_constraint.py.log.txt | - |
| 104 | `regression_ortools_budget_guard_skip_when_no_time.py` | PASS | 0 | 1.81 | - | evidence/FullSelfTest/logs/104_regression_ortools_budget_guard_skip_when_no_time.py.log.txt | - |
| 105 | `regression_ortools_priority_weight_contract.py` | PASS | 0 | 0.94 | - | evidence/FullSelfTest/logs/105_regression_ortools_priority_weight_contract.py.log.txt | - |
| 106 | `regression_ortools_warmstart_skip_nonfinite.py` | PASS | 0 | 0.90 | - | evidence/FullSelfTest/logs/106_regression_ortools_warmstart_skip_nonfinite.py.log.txt | - |
| 107 | `regression_page_manual_registry.py` | PASS | 0 | 2.86 | - | evidence/FullSelfTest/logs/107_regression_page_manual_registry.py.log.txt | - |
| 108 | `regression_part_operation_hours_service_stats_gate.py` | PASS | 0 | 1.71 | - | evidence/FullSelfTest/logs/108_regression_part_operation_hours_service_stats_gate.py.log.txt | - |
| 109 | `regression_part_service_create_strict_mode_atomic.py` | PASS | 0 | 1.70 | - | evidence/FullSelfTest/logs/109_regression_part_service_create_strict_mode_atomic.py.log.txt | - |
| 110 | `regression_part_service_external_default_days_fallback.py` | PASS | 0 | 1.70 | - | evidence/FullSelfTest/logs/110_regression_part_service_external_default_days_fallback.py.log.txt | - |
| 111 | `regression_personnel_excel_links_header_aliases.py` | PASS | 0 | 3.06 | - | evidence/FullSelfTest/logs/111_regression_personnel_excel_links_header_aliases.py.log.txt | - |
| 112 | `regression_plugin_manager_error_trace_visible.py` | PASS | 0 | 1.01 | - | evidence/FullSelfTest/logs/112_regression_plugin_manager_error_trace_visible.py.log.txt | - |
| 113 | `regression_priority_weight_case_insensitive.py` | PASS | 0 | 0.98 | - | evidence/FullSelfTest/logs/113_regression_priority_weight_case_insensitive.py.log.txt | - |
| 114 | `regression_process_excel_part_operation_hours_append_fill_empty_only.py` | PASS | 0 | 3.18 | - | evidence/FullSelfTest/logs/114_regression_process_excel_part_operation_hours_append_fill_empty_only.py.log.txt | - |
| 115 | `regression_process_excel_part_operation_hours_import.py` | PASS | 0 | 3.28 | - | evidence/FullSelfTest/logs/115_regression_process_excel_part_operation_hours_import.py.log.txt | - |
| 116 | `regression_process_reparse_preserve_internal_hours.py` | PASS | 0 | 3.12 | - | evidence/FullSelfTest/logs/116_regression_process_reparse_preserve_internal_hours.py.log.txt | - |
| 117 | `regression_report_source_case_insensitive.py` | PASS | 0 | 1.83 | - | evidence/FullSelfTest/logs/117_regression_report_source_case_insensitive.py.log.txt | - |
| 118 | `regression_reports_default_range_from_version_span.py` | PASS | 0 | 2.90 | - | evidence/FullSelfTest/logs/118_regression_reports_default_range_from_version_span.py.log.txt | - |
| 119 | `regression_reports_export_version_default_latest.py` | PASS | 0 | 2.98 | - | evidence/FullSelfTest/logs/119_regression_reports_export_version_default_latest.py.log.txt | - |
| 120 | `regression_resource_dispatch_overdue_summary_formats.py` | PASS | 0 | 1.82 | - | evidence/FullSelfTest/logs/120_regression_resource_dispatch_overdue_summary_formats.py.log.txt | - |
| 121 | `regression_resource_reference_guard_schedule.py` | PASS | 0 | 1.19 | - | evidence/FullSelfTest/logs/121_regression_resource_reference_guard_schedule.py.log.txt | - |
| 122 | `regression_restore_success_condition.py` | PASS | 0 | 2.94 | - | evidence/FullSelfTest/logs/122_regression_restore_success_condition.py.log.txt | - |
| 123 | `regression_route_parser_missing_supplier_warning.py` | PASS | 0 | 1.70 | - | evidence/FullSelfTest/logs/123_regression_route_parser_missing_supplier_warning.py.log.txt | - |
| 124 | `regression_route_parser_op_type_category_case_insensitive.py` | PASS | 0 | 1.70 | - | evidence/FullSelfTest/logs/124_regression_route_parser_op_type_category_case_insensitive.py.log.txt | - |
| 125 | `regression_route_parser_preserve_errors_when_no_matches.py` | PASS | 0 | 1.68 | - | evidence/FullSelfTest/logs/125_regression_route_parser_preserve_errors_when_no_matches.py.log.txt | - |
| 126 | `regression_route_parser_strict_mode_rejects_supplier_fallback.py` | PASS | 0 | 1.71 | - | evidence/FullSelfTest/logs/126_regression_route_parser_strict_mode_rejects_supplier_fallback.py.log.txt | - |
| 127 | `regression_route_parser_supplier_default_days_zero_trace.py` | PASS | 0 | 1.72 | - | evidence/FullSelfTest/logs/127_regression_route_parser_supplier_default_days_zero_trace.py.log.txt | - |
| 128 | `regression_runtime_contract_launcher.py` | PASS | 0 | 1.01 | - | evidence/FullSelfTest/logs/128_regression_runtime_contract_launcher.py.log.txt | - |
| 129 | `regression_runtime_lock_reloader_parent_skip.py` | PASS | 0 | 5.05 | - | evidence/FullSelfTest/logs/129_regression_runtime_lock_reloader_parent_skip.py.log.txt | - |
| 130 | `regression_runtime_probe_resolution.py` | PASS | 0 | 3.13 | - | evidence/FullSelfTest/logs/130_regression_runtime_probe_resolution.py.log.txt | - |
| 131 | `regression_runtime_stop_cli.py` | PASS | 0 | 7.62 | - | evidence/FullSelfTest/logs/131_regression_runtime_stop_cli.py.log.txt | - |
| 132 | `regression_safe_next_url_hardening.py` | PASS | 0 | 2.77 | - | evidence/FullSelfTest/logs/132_regression_safe_next_url_hardening.py.log.txt | - |
| 133 | `regression_sanitize_batch_dates_single_digit.py` | PASS | 0 | 1.11 | - | evidence/FullSelfTest/logs/133_regression_sanitize_batch_dates_single_digit.py.log.txt | - |
| 134 | `regression_schedule_input_builder_safe_float_parse.py` | PASS | 0 | 1.77 | - | evidence/FullSelfTest/logs/134_regression_schedule_input_builder_safe_float_parse.py.log.txt | - |
| 135 | `regression_schedule_persistence_reschedulable_contract.py` | PASS | 0 | 1.80 | - | evidence/FullSelfTest/logs/135_regression_schedule_persistence_reschedulable_contract.py.log.txt | - |
| 136 | `regression_schedule_service_missing_resource_source_case_insensitive.py` | PASS | 0 | 1.86 | - | evidence/FullSelfTest/logs/136_regression_schedule_service_missing_resource_source_case_insensitive.py.log.txt | - |
| 137 | `regression_schedule_service_passes_algo_stats_to_summary.py` | PASS | 0 | 1.78 | - | evidence/FullSelfTest/logs/137_regression_schedule_service_passes_algo_stats_to_summary.py.log.txt | - |
| 138 | `regression_schedule_service_reschedulable_contract.py` | PASS | 0 | 1.82 | - | evidence/FullSelfTest/logs/138_regression_schedule_service_reschedulable_contract.py.log.txt | - |
| 139 | `regression_schedule_summary_algo_warnings_union.py` | PASS | 0 | 1.79 | - | evidence/FullSelfTest/logs/139_regression_schedule_summary_algo_warnings_union.py.log.txt | - |
| 140 | `regression_schedule_summary_end_date_type_guard.py` | PASS | 0 | 1.77 | - | evidence/FullSelfTest/logs/140_regression_schedule_summary_end_date_type_guard.py.log.txt | - |
| 141 | `regression_schedule_summary_fallback_counts_output.py` | PASS | 0 | 1.79 | - | evidence/FullSelfTest/logs/141_regression_schedule_summary_fallback_counts_output.py.log.txt | - |
| 142 | `regression_schedule_summary_overdue_warning_append_fallback.py` | PASS | 0 | 1.80 | - | evidence/FullSelfTest/logs/142_regression_schedule_summary_overdue_warning_append_fallback.py.log.txt | - |
| 143 | `regression_schedule_summary_size_guard_large_lists.py` | PASS | 0 | 1.88 | - | evidence/FullSelfTest/logs/143_regression_schedule_summary_size_guard_large_lists.py.log.txt | - |
| 144 | `regression_schedule_summary_v11_contract.py` | PASS | 0 | 1.81 | - | evidence/FullSelfTest/logs/144_regression_schedule_summary_v11_contract.py.log.txt | - |
| 145 | `regression_scheduler_accepts_start_dt_string_and_safe_weights.py` | PASS | 0 | 0.96 | - | evidence/FullSelfTest/logs/145_regression_scheduler_accepts_start_dt_string_and_safe_weights.py.log.txt | - |
| 146 | `regression_scheduler_analysis_observability.py` | PASS | 0 | 3.03 | - | evidence/FullSelfTest/logs/146_regression_scheduler_analysis_observability.py.log.txt | - |
| 147 | `regression_scheduler_apply_preset_reject_invalid_numeric.py` | PASS | 0 | 1.88 | - | evidence/FullSelfTest/logs/147_regression_scheduler_apply_preset_reject_invalid_numeric.py.log.txt | - |
| 148 | `regression_scheduler_enforce_ready_default_from_config.py` | PASS | 0 | 1.93 | - | evidence/FullSelfTest/logs/148_regression_scheduler_enforce_ready_default_from_config.py.log.txt | - |
| 149 | `regression_scheduler_nonfinite_efficiency_fallback.py` | PASS | 0 | 0.96 | - | evidence/FullSelfTest/logs/149_regression_scheduler_nonfinite_efficiency_fallback.py.log.txt | - |
| 150 | `regression_scheduler_objective_labels.py` | PASS | 0 | 0.89 | - | evidence/FullSelfTest/logs/150_regression_scheduler_objective_labels.py.log.txt | - |
| 151 | `regression_scheduler_reject_nonfinite_and_invalid_status.py` | PASS | 0 | 1.91 | - | evidence/FullSelfTest/logs/151_regression_scheduler_reject_nonfinite_and_invalid_status.py.log.txt | - |
| 152 | `regression_scheduler_resource_dispatch_invalid_query_cleanup.py` | PASS | 0 | 4.67 | - | evidence/FullSelfTest/logs/152_regression_scheduler_resource_dispatch_invalid_query_cleanup.py.log.txt | - |
| 153 | `regression_scheduler_route_enforce_ready_tristate.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/153_regression_scheduler_route_enforce_ready_tristate.py.log.txt | - |
| 154 | `regression_scheduler_strict_mode_dispatch_flags.py` | PASS | 0 | 1.79 | - | evidence/FullSelfTest/logs/154_regression_scheduler_strict_mode_dispatch_flags.py.log.txt | - |
| 155 | `regression_seed_results_dedup.py` | PASS | 0 | 0.95 | - | evidence/FullSelfTest/logs/155_regression_seed_results_dedup.py.log.txt | - |
| 156 | `regression_seed_results_drop_duplicate_op_id_and_bad_time.py` | PASS | 0 | 0.96 | - | evidence/FullSelfTest/logs/156_regression_seed_results_drop_duplicate_op_id_and_bad_time.py.log.txt | - |
| 157 | `regression_seed_results_freeze_missing_resource.py` | PASS | 0 | 0.97 | - | evidence/FullSelfTest/logs/157_regression_seed_results_freeze_missing_resource.py.log.txt | - |
| 158 | `regression_seed_results_invalid_op_id_dedup.py` | PASS | 0 | 0.94 | - | evidence/FullSelfTest/logs/158_regression_seed_results_invalid_op_id_dedup.py.log.txt | - |
| 159 | `regression_sgs_atc_penalize_missing_resources.py` | PASS | 0 | 0.96 | - | evidence/FullSelfTest/logs/159_regression_sgs_atc_penalize_missing_resources.py.log.txt | - |
| 160 | `regression_sgs_penalize_nonfinite_proc_hours.py` | PASS | 0 | 0.93 | - | evidence/FullSelfTest/logs/160_regression_sgs_penalize_nonfinite_proc_hours.py.log.txt | - |
| 161 | `regression_sgs_scoring_fallback_unscorable.py` | PASS | 0 | 0.95 | - | evidence/FullSelfTest/logs/161_regression_sgs_scoring_fallback_unscorable.py.log.txt | - |
| 162 | `regression_sgs_scoring_machine_operator_id_type_safe.py` | PASS | 0 | 0.97 | - | evidence/FullSelfTest/logs/162_regression_sgs_scoring_machine_operator_id_type_safe.py.log.txt | - |
| 163 | `regression_shared_runtime_state.py` | PASS | 0 | 1.21 | - | evidence/FullSelfTest/logs/163_regression_shared_runtime_state.py.log.txt | - |
| 164 | `regression_skill_rank_mapping.py` | PASS | 0 | 1.95 | - | evidence/FullSelfTest/logs/164_regression_skill_rank_mapping.py.log.txt | - |
| 165 | `regression_sort_strategies_priority_case_insensitive.py` | PASS | 0 | 0.93 | - | evidence/FullSelfTest/logs/165_regression_sort_strategies_priority_case_insensitive.py.log.txt | - |
| 166 | `regression_sort_strategy_case_insensitive.py` | PASS | 0 | 0.95 | - | evidence/FullSelfTest/logs/166_regression_sort_strategy_case_insensitive.py.log.txt | - |
| 167 | `regression_sqlite_detect_types_enabled.py` | PASS | 0 | 0.93 | - | evidence/FullSelfTest/logs/167_regression_sqlite_detect_types_enabled.py.log.txt | - |
| 168 | `regression_start_and_rerun_route_resolution.py` | PASS | 0 | 0.95 | - | evidence/FullSelfTest/logs/168_regression_start_and_rerun_route_resolution.py.log.txt | - |
| 169 | `regression_startup_host_portfile.py` | PASS | 0 | 9.31 | - | evidence/FullSelfTest/logs/169_regression_startup_host_portfile.py.log.txt | - |
| 170 | `regression_startup_host_portfile_new_ui.py` | PASS | 0 | 9.30 | - | evidence/FullSelfTest/logs/170_regression_startup_host_portfile_new_ui.py.log.txt | - |
| 171 | `regression_status_category_mixed_case.py` | PASS | 0 | 1.79 | - | evidence/FullSelfTest/logs/171_regression_status_category_mixed_case.py.log.txt | - |
| 172 | `regression_supplier_service_invalid_default_days_not_silent.py` | PASS | 0 | 1.69 | - | evidence/FullSelfTest/logs/172_regression_supplier_service_invalid_default_days_not_silent.py.log.txt | - |
| 173 | `regression_system_health_route.py` | PASS | 0 | 3.27 | - | evidence/FullSelfTest/logs/173_regression_system_health_route.py.log.txt | - |
| 174 | `regression_system_logs_delete_no_clamp.py` | PASS | 0 | 3.08 | - | evidence/FullSelfTest/logs/174_regression_system_logs_delete_no_clamp.py.log.txt | - |
| 175 | `regression_system_maintenance_jobstate_commit.py` | PASS | 0 | 1.75 | - | evidence/FullSelfTest/logs/175_regression_system_maintenance_jobstate_commit.py.log.txt | - |
| 176 | `regression_system_maintenance_throttle_short_circuit.py` | PASS | 0 | 1.03 | - | evidence/FullSelfTest/logs/176_regression_system_maintenance_throttle_short_circuit.py.log.txt | - |
| 177 | `regression_template_no_inline_event_jinja.py` | PASS | 0 | 0.91 | - | evidence/FullSelfTest/logs/177_regression_template_no_inline_event_jinja.py.log.txt | - |
| 178 | `regression_template_urlfor_endpoints.py` | PASS | 0 | 2.83 | - | evidence/FullSelfTest/logs/178_regression_template_urlfor_endpoints.py.log.txt | - |
| 179 | `regression_tojson_zh_autoescape.py` | PASS | 0 | 2.82 | - | evidence/FullSelfTest/logs/179_regression_tojson_zh_autoescape.py.log.txt | - |
| 180 | `regression_transaction_savepoint_nested.py` | PASS | 0 | 1.00 | - | evidence/FullSelfTest/logs/180_regression_transaction_savepoint_nested.py.log.txt | - |
| 181 | `regression_ui_contract_table_overflow_guard.py` | PASS | 0 | 0.91 | - | evidence/FullSelfTest/logs/181_regression_ui_contract_table_overflow_guard.py.log.txt | - |
| 182 | `regression_unit_excel_converter_duplicate_part_rows_no_override.py` | PASS | 0 | 1.75 | - | evidence/FullSelfTest/logs/182_regression_unit_excel_converter_duplicate_part_rows_no_override.py.log.txt | - |
| 183 | `regression_unit_excel_converter_facade_binding.py` | PASS | 0 | 1.71 | - | evidence/FullSelfTest/logs/183_regression_unit_excel_converter_facade_binding.py.log.txt | - |
| 184 | `regression_unit_excel_converter_merge_steps_and_classify.py` | PASS | 0 | 2.02 | - | evidence/FullSelfTest/logs/184_regression_unit_excel_converter_merge_steps_and_classify.py.log.txt | - |
| 185 | `regression_unit_excel_template_headers.py` | PASS | 0 | 1.70 | - | evidence/FullSelfTest/logs/185_regression_unit_excel_template_headers.py.log.txt | - |
| 186 | `regression_v2_strategy_zh_contract.py` | PASS | 0 | 0.90 | - | evidence/FullSelfTest/logs/186_regression_v2_strategy_zh_contract.py.log.txt | - |
| 187 | `regression_validate_dist_runtime_identity.py` | PASS | 0 | 1.37 | - | evidence/FullSelfTest/logs/187_regression_validate_dist_runtime_identity.py.log.txt | - |
| 188 | `regression_weighted_tardiness_objective.py` | PASS | 0 | 1.80 | - | evidence/FullSelfTest/logs/188_regression_weighted_tardiness_objective.py.log.txt | - |
| 189 | `run_complex_excel_cases_e2e.py` | PASS | 0 | 55.60 | evidence/ComplexExcelCases/complex_cases_report.md<br/>evidence/ComplexExcelCases/complex_cases_summary.json | evidence/FullSelfTest/logs/189_run_complex_excel_cases_e2e.py.log.txt | - |

## 说明

- 本 runner **不会**执行 PyInstaller / dist / validate_dist_exe 等打包流程。
- 复杂 Excel 用例的重产物目录默认会被 `.gitignore` 忽略，仅保留报告与 summary JSON。

