# APS 全量自测汇总报告（不打包）

- 生成时间：2026-03-02 12:37:01
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- Python 可执行：`D:\py3.8\python.exe`
- 仓库根目录：`D:/Github/APS Test`
- fail_fast：true
- complex_repeat：1
- step_timeout_s：900

## 总结

- 结论：**PASS**
- 记录数：112

## 明细

| # | 脚本 | 结果 | exit | 耗时(s) | 证据(evidence) | runner日志 | 备注 |
|---:|---|---|---:|---:|---|---|---|
| 1 | `smoke_phase0_phase1.py` | PASS | 0 | 2.70 | evidence/Phase0_Phase1/smoke_test_report.md | evidence/FullSelfTest/logs/01_smoke_phase0_phase1.py.log.txt | - |
| 2 | `smoke_phase2.py` | PASS | 0 | 0.46 | evidence/Phase2/smoke_phase2_report.md | evidence/FullSelfTest/logs/02_smoke_phase2.py.log.txt | - |
| 3 | `smoke_phase3.py` | PASS | 0 | 1.35 | evidence/Phase3/smoke_phase3_report.md | evidence/FullSelfTest/logs/03_smoke_phase3.py.log.txt | - |
| 4 | `smoke_phase4.py` | PASS | 0 | 1.38 | evidence/Phase4/smoke_phase4_report.md | evidence/FullSelfTest/logs/04_smoke_phase4.py.log.txt | - |
| 5 | `smoke_phase5.py` | PASS | 0 | 1.77 | evidence/Phase5/smoke_phase5_report.md | evidence/FullSelfTest/logs/05_smoke_phase5.py.log.txt | - |
| 6 | `smoke_phase6.py` | PASS | 0 | 1.61 | evidence/Phase6/smoke_phase6_report.md | evidence/FullSelfTest/logs/06_smoke_phase6.py.log.txt | - |
| 7 | `smoke_phase7.py` | PASS | 0 | 1.06 | evidence/Phase7/smoke_phase7_report.md | evidence/FullSelfTest/logs/07_smoke_phase7.py.log.txt | - |
| 8 | `smoke_phase8.py` | PASS | 0 | 3.01 | evidence/Phase8/smoke_phase8_report.md | evidence/FullSelfTest/logs/08_smoke_phase8.py.log.txt | - |
| 9 | `smoke_phase9.py` | PASS | 0 | 27.36 | evidence/Phase9/smoke_phase9_report.md | evidence/FullSelfTest/logs/09_smoke_phase9.py.log.txt | - |
| 10 | `smoke_phase10_sgs_auto_assign.py` | PASS | 0 | 1.05 | evidence/Phase10/smoke_phase10_report.md | evidence/FullSelfTest/logs/10_smoke_phase10_sgs_auto_assign.py.log.txt | Phase10 报告显示 PASS：D:/Github/APS Test/evidence/Phase10/smoke_phase10_report.md |
| 11 | `smoke_web_phase0_5.py` | PASS | 0 | 3.64 | evidence/Phase0_to_Phase5/web_smoke_report.md | evidence/FullSelfTest/logs/11_smoke_web_phase0_5.py.log.txt | - |
| 12 | `smoke_web_phase0_6.py` | PASS | 0 | 3.18 | evidence/Phase0_to_Phase6/web_smoke_report.md | evidence/FullSelfTest/logs/12_smoke_web_phase0_6.py.log.txt | - |
| 13 | `smoke_e2e_excel_to_schedule.py` | PASS | 0 | 4.36 | evidence/FullE2E/excel_to_schedule_report.md | evidence/FullSelfTest/logs/13_smoke_e2e_excel_to_schedule.py.log.txt | - |
| 14 | `regression_app_db_path_no_dirname.py` | PASS | 0 | 2.60 | - | evidence/FullSelfTest/logs/14_regression_app_db_path_no_dirname.py.log.txt | - |
| 15 | `regression_app_new_ui_secret_key_runtime_ensure.py` | PASS | 0 | 2.37 | - | evidence/FullSelfTest/logs/15_regression_app_new_ui_secret_key_runtime_ensure.py.log.txt | - |
| 16 | `regression_app_new_ui_security_hardening_enabled.py` | PASS | 0 | 2.41 | - | evidence/FullSelfTest/logs/16_regression_app_new_ui_security_hardening_enabled.py.log.txt | - |
| 17 | `regression_app_new_ui_session_contract.py` | PASS | 0 | 2.36 | - | evidence/FullSelfTest/logs/17_regression_app_new_ui_session_contract.py.log.txt | - |
| 18 | `regression_auto_assign_empty_resource_pool.py` | PASS | 0 | 0.21 | - | evidence/FullSelfTest/logs/18_regression_auto_assign_empty_resource_pool.py.log.txt | - |
| 19 | `regression_auto_assign_fixed_operator_respects_op_type.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/19_regression_auto_assign_fixed_operator_respects_op_type.py.log.txt | - |
| 20 | `regression_auto_assign_persist_truthy_variants.py` | PASS | 0 | 0.57 | - | evidence/FullSelfTest/logs/20_regression_auto_assign_persist_truthy_variants.py.log.txt | - |
| 21 | `regression_batch_detail_linkage.py` | PASS | 0 | 2.46 | - | evidence/FullSelfTest/logs/21_regression_batch_detail_linkage.py.log.txt | - |
| 22 | `regression_batch_import_unchanged_no_rebuild.py` | PASS | 0 | 0.42 | - | evidence/FullSelfTest/logs/22_regression_batch_import_unchanged_no_rebuild.py.log.txt | - |
| 23 | `regression_batch_order_bid_unboundlocal.py` | PASS | 0 | 0.21 | - | evidence/FullSelfTest/logs/23_regression_batch_order_bid_unboundlocal.py.log.txt | - |
| 24 | `regression_batch_order_override_dedup.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/24_regression_batch_order_override_dedup.py.log.txt | - |
| 25 | `regression_calendar_shift_start_rollover.py` | PASS | 0 | 0.43 | - | evidence/FullSelfTest/logs/25_regression_calendar_shift_start_rollover.py.log.txt | - |
| 26 | `regression_config_manual_markdown.py` | PASS | 0 | 0.22 | - | evidence/FullSelfTest/logs/26_regression_config_manual_markdown.py.log.txt | - |
| 27 | `regression_dashboard_overdue_count_tolerance.py` | PASS | 0 | 2.48 | - | evidence/FullSelfTest/logs/27_regression_dashboard_overdue_count_tolerance.py.log.txt | - |
| 28 | `regression_deletion_validator_source_case_insensitive.py` | PASS | 0 | 1.09 | - | evidence/FullSelfTest/logs/28_regression_deletion_validator_source_case_insensitive.py.log.txt | - |
| 29 | `regression_dispatch_blocking_consistency.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/29_regression_dispatch_blocking_consistency.py.log.txt | - |
| 30 | `regression_dispatch_rule_case_insensitive.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/30_regression_dispatch_rule_case_insensitive.py.log.txt | - |
| 31 | `regression_dispatch_rules_nonfinite_proc_hours_safe.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/31_regression_dispatch_rules_nonfinite_proc_hours_safe.py.log.txt | - |
| 32 | `regression_dispatch_rules_priority_case_insensitive.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/32_regression_dispatch_rules_priority_case_insensitive.py.log.txt | - |
| 33 | `regression_downtime_overlap_skips_invalid_segments.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/33_regression_downtime_overlap_skips_invalid_segments.py.log.txt | - |
| 34 | `regression_efficiency_greater_than_one_shortens_hours.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/34_regression_efficiency_greater_than_one_shortens_hours.py.log.txt | - |
| 35 | `regression_excel_import_executor_status_gate.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/35_regression_excel_import_executor_status_gate.py.log.txt | - |
| 36 | `regression_excel_normalizers_mixed_case.py` | PASS | 0 | 1.46 | - | evidence/FullSelfTest/logs/36_regression_excel_normalizers_mixed_case.py.log.txt | - |
| 37 | `regression_excel_operator_calendar_cross_midnight.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/37_regression_excel_operator_calendar_cross_midnight.py.log.txt | - |
| 38 | `regression_excel_preview_confirm_baseline_guard.py` | PASS | 0 | 1.99 | - | evidence/FullSelfTest/logs/38_regression_excel_preview_confirm_baseline_guard.py.log.txt | - |
| 39 | `regression_excel_routes_no_tx_surface_hidden.py` | PASS | 0 | 0.10 | - | evidence/FullSelfTest/logs/39_regression_excel_routes_no_tx_surface_hidden.py.log.txt | - |
| 40 | `regression_excel_service_calc_changes_row.py` | PASS | 0 | 0.16 | - | evidence/FullSelfTest/logs/40_regression_excel_service_calc_changes_row.py.log.txt | - |
| 41 | `regression_excel_validators_yesno_mixed_case.py` | PASS | 0 | 0.22 | - | evidence/FullSelfTest/logs/41_regression_excel_validators_yesno_mixed_case.py.log.txt | - |
| 42 | `regression_external_group_service_merge_mode_case_insensitive.py` | PASS | 0 | 1.00 | - | evidence/FullSelfTest/logs/42_regression_external_group_service_merge_mode_case_insensitive.py.log.txt | - |
| 43 | `regression_external_merge_mode_case_insensitive.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/43_regression_external_merge_mode_case_insensitive.py.log.txt | - |
| 44 | `regression_freeze_window_bounds.py` | PASS | 0 | 0.53 | - | evidence/FullSelfTest/logs/44_regression_freeze_window_bounds.py.log.txt | - |
| 45 | `regression_frontend_common_interactions.py` | PASS | 0 | 0.10 | - | evidence/FullSelfTest/logs/45_regression_frontend_common_interactions.py.log.txt | - |
| 46 | `regression_gantt_contract_snapshot.py` | PASS | 0 | 1.92 | - | evidence/FullSelfTest/logs/46_regression_gantt_contract_snapshot.py.log.txt | - |
| 47 | `regression_gantt_critical_chain_cache_thread_safe.py` | PASS | 0 | 1.37 | - | evidence/FullSelfTest/logs/47_regression_gantt_critical_chain_cache_thread_safe.py.log.txt | - |
| 48 | `regression_gantt_offset_range_consistency.py` | PASS | 0 | 1.95 | - | evidence/FullSelfTest/logs/48_regression_gantt_offset_range_consistency.py.log.txt | - |
| 49 | `regression_gantt_status_mode_semantics.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/49_regression_gantt_status_mode_semantics.py.log.txt | - |
| 50 | `regression_gantt_url_persistence.py` | PASS | 0 | 1.90 | - | evidence/FullSelfTest/logs/50_regression_gantt_url_persistence.py.log.txt | - |
| 51 | `regression_greedy_date_parsers.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/51_regression_greedy_date_parsers.py.log.txt | - |
| 52 | `regression_lazy_select_orphan_option.py` | PASS | 0 | 1.87 | - | evidence/FullSelfTest/logs/52_regression_lazy_select_orphan_option.py.log.txt | - |
| 53 | `regression_metrics_horizon_semantics.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/53_regression_metrics_horizon_semantics.py.log.txt | - |
| 54 | `regression_metrics_to_dict_nonfinite_safe.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/54_regression_metrics_to_dict_nonfinite_safe.py.log.txt | - |
| 55 | `regression_migrate_backup_dir_none_creates_backup.py` | PASS | 0 | 0.24 | - | evidence/FullSelfTest/logs/55_regression_migrate_backup_dir_none_creates_backup.py.log.txt | - |
| 56 | `regression_migrate_v2_unify_workcalendar_day_type.py` | PASS | 0 | 0.63 | - | evidence/FullSelfTest/logs/56_regression_migrate_v2_unify_workcalendar_day_type.py.log.txt | - |
| 57 | `regression_migrate_v4_sanitize_enum_text_fields.py` | PASS | 0 | 0.69 | - | evidence/FullSelfTest/logs/57_regression_migrate_v4_sanitize_enum_text_fields.py.log.txt | - |
| 58 | `regression_model_enums_case_insensitive.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/58_regression_model_enums_case_insensitive.py.log.txt | - |
| 59 | `regression_models_numeric_parse_hybrid_safe.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/59_regression_models_numeric_parse_hybrid_safe.py.log.txt | - |
| 60 | `regression_operator_calendar_override_allows_work_on_global_holiday.py` | PASS | 0 | 0.43 | - | evidence/FullSelfTest/logs/60_regression_operator_calendar_override_allows_work_on_global_holiday.py.log.txt | - |
| 61 | `regression_operator_machine_missing_columns.py` | PASS | 0 | 0.24 | - | evidence/FullSelfTest/logs/61_regression_operator_machine_missing_columns.py.log.txt | - |
| 62 | `regression_optimizer_ortools_logging_exc_info_safe.py` | PASS | 0 | 0.32 | - | evidence/FullSelfTest/logs/62_regression_optimizer_ortools_logging_exc_info_safe.py.log.txt | - |
| 63 | `regression_optional_ready_constraint.py` | PASS | 0 | 0.46 | - | evidence/FullSelfTest/logs/63_regression_optional_ready_constraint.py.log.txt | - |
| 64 | `regression_ortools_budget_guard_skip_when_no_time.py` | PASS | 0 | 0.33 | - | evidence/FullSelfTest/logs/64_regression_ortools_budget_guard_skip_when_no_time.py.log.txt | - |
| 65 | `regression_ortools_warmstart_skip_nonfinite.py` | PASS | 0 | 0.07 | - | evidence/FullSelfTest/logs/65_regression_ortools_warmstart_skip_nonfinite.py.log.txt | - |
| 66 | `regression_part_operation_hours_service_stats_gate.py` | PASS | 0 | 1.01 | - | evidence/FullSelfTest/logs/66_regression_part_operation_hours_service_stats_gate.py.log.txt | - |
| 67 | `regression_plugin_manager_error_trace_visible.py` | PASS | 0 | 0.27 | - | evidence/FullSelfTest/logs/67_regression_plugin_manager_error_trace_visible.py.log.txt | - |
| 68 | `regression_priority_weight_case_insensitive.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/68_regression_priority_weight_case_insensitive.py.log.txt | - |
| 69 | `regression_process_excel_part_operation_hours_append_fill_empty_only.py` | PASS | 0 | 2.16 | - | evidence/FullSelfTest/logs/69_regression_process_excel_part_operation_hours_append_fill_empty_only.py.log.txt | - |
| 70 | `regression_process_excel_part_operation_hours_import.py` | PASS | 0 | 2.17 | - | evidence/FullSelfTest/logs/70_regression_process_excel_part_operation_hours_import.py.log.txt | - |
| 71 | `regression_process_reparse_preserve_internal_hours.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/71_regression_process_reparse_preserve_internal_hours.py.log.txt | - |
| 72 | `regression_reports_default_range_from_version_span.py` | PASS | 0 | 1.92 | - | evidence/FullSelfTest/logs/72_regression_reports_default_range_from_version_span.py.log.txt | - |
| 73 | `regression_reports_export_version_default_latest.py` | PASS | 0 | 1.96 | - | evidence/FullSelfTest/logs/73_regression_reports_export_version_default_latest.py.log.txt | - |
| 74 | `regression_route_parser_op_type_category_case_insensitive.py` | PASS | 0 | 1.01 | - | evidence/FullSelfTest/logs/74_regression_route_parser_op_type_category_case_insensitive.py.log.txt | - |
| 75 | `regression_route_parser_preserve_errors_when_no_matches.py` | PASS | 0 | 0.98 | - | evidence/FullSelfTest/logs/75_regression_route_parser_preserve_errors_when_no_matches.py.log.txt | - |
| 76 | `regression_sanitize_batch_dates_single_digit.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/76_regression_sanitize_batch_dates_single_digit.py.log.txt | - |
| 77 | `regression_schedule_input_builder_safe_float_parse.py` | PASS | 0 | 0.32 | - | evidence/FullSelfTest/logs/77_regression_schedule_input_builder_safe_float_parse.py.log.txt | - |
| 78 | `regression_schedule_service_missing_resource_source_case_insensitive.py` | PASS | 0 | 0.33 | - | evidence/FullSelfTest/logs/78_regression_schedule_service_missing_resource_source_case_insensitive.py.log.txt | - |
| 79 | `regression_schedule_summary_end_date_type_guard.py` | PASS | 0 | 0.32 | - | evidence/FullSelfTest/logs/79_regression_schedule_summary_end_date_type_guard.py.log.txt | - |
| 80 | `regression_scheduler_accepts_start_dt_string_and_safe_weights.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/80_regression_scheduler_accepts_start_dt_string_and_safe_weights.py.log.txt | - |
| 81 | `regression_scheduler_apply_preset_reject_invalid_numeric.py` | PASS | 0 | 0.47 | - | evidence/FullSelfTest/logs/81_regression_scheduler_apply_preset_reject_invalid_numeric.py.log.txt | - |
| 82 | `regression_scheduler_enforce_ready_default_from_config.py` | PASS | 0 | 0.48 | - | evidence/FullSelfTest/logs/82_regression_scheduler_enforce_ready_default_from_config.py.log.txt | - |
| 83 | `regression_scheduler_nonfinite_efficiency_fallback.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/83_regression_scheduler_nonfinite_efficiency_fallback.py.log.txt | - |
| 84 | `regression_scheduler_reject_nonfinite_and_invalid_status.py` | PASS | 0 | 0.46 | - | evidence/FullSelfTest/logs/84_regression_scheduler_reject_nonfinite_and_invalid_status.py.log.txt | - |
| 85 | `regression_scheduler_route_enforce_ready_tristate.py` | PASS | 0 | 0.90 | - | evidence/FullSelfTest/logs/85_regression_scheduler_route_enforce_ready_tristate.py.log.txt | - |
| 86 | `regression_seed_results_dedup.py` | PASS | 0 | 0.17 | - | evidence/FullSelfTest/logs/86_regression_seed_results_dedup.py.log.txt | - |
| 87 | `regression_seed_results_drop_duplicate_op_id_and_bad_time.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/87_regression_seed_results_drop_duplicate_op_id_and_bad_time.py.log.txt | - |
| 88 | `regression_seed_results_freeze_missing_resource.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/88_regression_seed_results_freeze_missing_resource.py.log.txt | - |
| 89 | `regression_seed_results_invalid_op_id_dedup.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/89_regression_seed_results_invalid_op_id_dedup.py.log.txt | - |
| 90 | `regression_sgs_atc_penalize_missing_resources.py` | PASS | 0 | 0.17 | - | evidence/FullSelfTest/logs/90_regression_sgs_atc_penalize_missing_resources.py.log.txt | - |
| 91 | `regression_sgs_penalize_nonfinite_proc_hours.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/91_regression_sgs_penalize_nonfinite_proc_hours.py.log.txt | - |
| 92 | `regression_sgs_scoring_fallback_unscorable.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/92_regression_sgs_scoring_fallback_unscorable.py.log.txt | - |
| 93 | `regression_sgs_scoring_machine_operator_id_type_safe.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/93_regression_sgs_scoring_machine_operator_id_type_safe.py.log.txt | - |
| 94 | `regression_skill_rank_mapping.py` | PASS | 0 | 0.47 | - | evidence/FullSelfTest/logs/94_regression_skill_rank_mapping.py.log.txt | - |
| 95 | `regression_sort_strategies_priority_case_insensitive.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/95_regression_sort_strategies_priority_case_insensitive.py.log.txt | - |
| 96 | `regression_sort_strategy_case_insensitive.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/96_regression_sort_strategy_case_insensitive.py.log.txt | - |
| 97 | `regression_sqlite_detect_types_enabled.py` | PASS | 0 | 0.14 | - | evidence/FullSelfTest/logs/97_regression_sqlite_detect_types_enabled.py.log.txt | - |
| 98 | `regression_startup_host_portfile.py` | PASS | 0 | 8.24 | - | evidence/FullSelfTest/logs/98_regression_startup_host_portfile.py.log.txt | - |
| 99 | `regression_startup_host_portfile_new_ui.py` | PASS | 0 | 7.64 | - | evidence/FullSelfTest/logs/99_regression_startup_host_portfile_new_ui.py.log.txt | - |
| 100 | `regression_status_category_mixed_case.py` | PASS | 0 | 1.11 | - | evidence/FullSelfTest/logs/100_regression_status_category_mixed_case.py.log.txt | - |
| 101 | `regression_system_logs_delete_no_clamp.py` | PASS | 0 | 1.95 | - | evidence/FullSelfTest/logs/101_regression_system_logs_delete_no_clamp.py.log.txt | - |
| 102 | `regression_system_maintenance_jobstate_commit.py` | PASS | 0 | 0.76 | - | evidence/FullSelfTest/logs/102_regression_system_maintenance_jobstate_commit.py.log.txt | - |
| 103 | `regression_system_maintenance_throttle_short_circuit.py` | PASS | 0 | 0.28 | - | evidence/FullSelfTest/logs/103_regression_system_maintenance_throttle_short_circuit.py.log.txt | - |
| 104 | `regression_template_no_inline_event_jinja.py` | PASS | 0 | 0.14 | - | evidence/FullSelfTest/logs/104_regression_template_no_inline_event_jinja.py.log.txt | - |
| 105 | `regression_template_urlfor_endpoints.py` | PASS | 0 | 1.83 | - | evidence/FullSelfTest/logs/105_regression_template_urlfor_endpoints.py.log.txt | - |
| 106 | `regression_tojson_zh_autoescape.py` | PASS | 0 | 1.81 | - | evidence/FullSelfTest/logs/106_regression_tojson_zh_autoescape.py.log.txt | - |
| 107 | `regression_transaction_savepoint_nested.py` | PASS | 0 | 0.20 | - | evidence/FullSelfTest/logs/107_regression_transaction_savepoint_nested.py.log.txt | - |
| 108 | `regression_ui_contract_table_overflow_guard.py` | PASS | 0 | 0.10 | - | evidence/FullSelfTest/logs/108_regression_ui_contract_table_overflow_guard.py.log.txt | - |
| 109 | `regression_unit_excel_converter_duplicate_part_rows_no_override.py` | PASS | 0 | 1.05 | - | evidence/FullSelfTest/logs/109_regression_unit_excel_converter_duplicate_part_rows_no_override.py.log.txt | - |
| 110 | `regression_unit_excel_converter_facade_binding.py` | PASS | 0 | 1.00 | - | evidence/FullSelfTest/logs/110_regression_unit_excel_converter_facade_binding.py.log.txt | - |
| 111 | `regression_unit_excel_converter_merge_steps_and_classify.py` | PASS | 0 | 1.12 | - | evidence/FullSelfTest/logs/111_regression_unit_excel_converter_merge_steps_and_classify.py.log.txt | - |
| 112 | `run_complex_excel_cases_e2e.py` | PASS | 0 | 67.09 | evidence/ComplexExcelCases/complex_cases_report.md<br/>evidence/ComplexExcelCases/complex_cases_summary.json | evidence/FullSelfTest/logs/112_run_complex_excel_cases_e2e.py.log.txt | - |

## 说明

- 本 runner **不会**执行 PyInstaller / dist / validate_dist_exe 等打包流程。
- 复杂 Excel 用例的重产物目录默认会被 `.gitignore` 忽略，仅保留报告与 summary JSON。

