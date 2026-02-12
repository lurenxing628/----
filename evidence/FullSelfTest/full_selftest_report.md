# APS 全量自测汇总报告（不打包）

- 生成时间：2026-02-13 03:01:34
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- Python 可执行：`D:\py3.8\python.exe`
- 仓库根目录：`D:/Github/APS Test`
- fail_fast：false
- complex_repeat：1

## 总结

- 结论：**PASS**
- 记录数：78

## 明细

| # | 脚本 | 结果 | exit | 耗时(s) | 证据(evidence) | runner日志 | 备注 |
|---:|---|---|---:|---:|---|---|---|
| 1 | `smoke_phase0_phase1.py` | PASS | 0 | 2.62 | evidence/Phase0_Phase1/smoke_test_report.md | evidence/FullSelfTest/logs/01_smoke_phase0_phase1.py.log.txt | - |
| 2 | `smoke_phase2.py` | PASS | 0 | 0.52 | evidence/Phase2/smoke_phase2_report.md | evidence/FullSelfTest/logs/02_smoke_phase2.py.log.txt | - |
| 3 | `smoke_phase3.py` | PASS | 0 | 1.17 | evidence/Phase3/smoke_phase3_report.md | evidence/FullSelfTest/logs/03_smoke_phase3.py.log.txt | - |
| 4 | `smoke_phase4.py` | PASS | 0 | 1.41 | evidence/Phase4/smoke_phase4_report.md | evidence/FullSelfTest/logs/04_smoke_phase4.py.log.txt | - |
| 5 | `smoke_phase5.py` | PASS | 0 | 1.34 | evidence/Phase5/smoke_phase5_report.md | evidence/FullSelfTest/logs/05_smoke_phase5.py.log.txt | - |
| 6 | `smoke_phase6.py` | PASS | 0 | 1.40 | evidence/Phase6/smoke_phase6_report.md | evidence/FullSelfTest/logs/06_smoke_phase6.py.log.txt | - |
| 7 | `smoke_phase7.py` | PASS | 0 | 3.03 | evidence/Phase7/smoke_phase7_report.md | evidence/FullSelfTest/logs/07_smoke_phase7.py.log.txt | - |
| 8 | `smoke_phase8.py` | PASS | 0 | 2.54 | evidence/Phase8/smoke_phase8_report.md | evidence/FullSelfTest/logs/08_smoke_phase8.py.log.txt | - |
| 9 | `smoke_phase9.py` | PASS | 0 | 27.41 | evidence/Phase9/smoke_phase9_report.md | evidence/FullSelfTest/logs/09_smoke_phase9.py.log.txt | - |
| 10 | `smoke_phase10_sgs_auto_assign.py` | PASS | 0 | 1.89 | evidence/Phase10/smoke_phase10_report.md | evidence/FullSelfTest/logs/10_smoke_phase10_sgs_auto_assign.py.log.txt | Phase10 报告显示 PASS：D:/Github/APS Test/evidence/Phase10/smoke_phase10_report.md |
| 11 | `smoke_web_phase0_5.py` | PASS | 0 | 3.22 | evidence/Phase0_to_Phase5/web_smoke_report.md | evidence/FullSelfTest/logs/11_smoke_web_phase0_5.py.log.txt | - |
| 12 | `smoke_web_phase0_6.py` | PASS | 0 | 3.09 | evidence/Phase0_to_Phase6/web_smoke_report.md | evidence/FullSelfTest/logs/12_smoke_web_phase0_6.py.log.txt | - |
| 13 | `smoke_e2e_excel_to_schedule.py` | PASS | 0 | 3.67 | evidence/FullE2E/excel_to_schedule_report.md | evidence/FullSelfTest/logs/13_smoke_e2e_excel_to_schedule.py.log.txt | - |
| 14 | `regression_app_db_path_no_dirname.py` | PASS | 0 | 2.38 | - | evidence/FullSelfTest/logs/14_regression_app_db_path_no_dirname.py.log.txt | - |
| 15 | `regression_auto_assign_empty_resource_pool.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/15_regression_auto_assign_empty_resource_pool.py.log.txt | - |
| 16 | `regression_auto_assign_fixed_operator_respects_op_type.py` | PASS | 0 | 0.27 | - | evidence/FullSelfTest/logs/16_regression_auto_assign_fixed_operator_respects_op_type.py.log.txt | - |
| 17 | `regression_batch_order_bid_unboundlocal.py` | PASS | 0 | 0.24 | - | evidence/FullSelfTest/logs/17_regression_batch_order_bid_unboundlocal.py.log.txt | - |
| 18 | `regression_batch_order_override_dedup.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/18_regression_batch_order_override_dedup.py.log.txt | - |
| 19 | `regression_calendar_shift_start_rollover.py` | PASS | 0 | 0.47 | - | evidence/FullSelfTest/logs/19_regression_calendar_shift_start_rollover.py.log.txt | - |
| 20 | `regression_deletion_validator_source_case_insensitive.py` | PASS | 0 | 1.05 | - | evidence/FullSelfTest/logs/20_regression_deletion_validator_source_case_insensitive.py.log.txt | - |
| 21 | `regression_dispatch_blocking_consistency.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/21_regression_dispatch_blocking_consistency.py.log.txt | - |
| 22 | `regression_dispatch_rule_case_insensitive.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/22_regression_dispatch_rule_case_insensitive.py.log.txt | - |
| 23 | `regression_dispatch_rules_nonfinite_proc_hours_safe.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/23_regression_dispatch_rules_nonfinite_proc_hours_safe.py.log.txt | - |
| 24 | `regression_dispatch_rules_priority_case_insensitive.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/24_regression_dispatch_rules_priority_case_insensitive.py.log.txt | - |
| 25 | `regression_downtime_overlap_skips_invalid_segments.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/25_regression_downtime_overlap_skips_invalid_segments.py.log.txt | - |
| 26 | `regression_efficiency_greater_than_one_shortens_hours.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/26_regression_efficiency_greater_than_one_shortens_hours.py.log.txt | - |
| 27 | `regression_excel_service_calc_changes_row.py` | PASS | 0 | 0.21 | - | evidence/FullSelfTest/logs/27_regression_excel_service_calc_changes_row.py.log.txt | - |
| 28 | `regression_external_group_service_merge_mode_case_insensitive.py` | PASS | 0 | 1.06 | - | evidence/FullSelfTest/logs/28_regression_external_group_service_merge_mode_case_insensitive.py.log.txt | - |
| 29 | `regression_external_merge_mode_case_insensitive.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/29_regression_external_merge_mode_case_insensitive.py.log.txt | - |
| 30 | `regression_freeze_window_bounds.py` | PASS | 0 | 0.77 | - | evidence/FullSelfTest/logs/30_regression_freeze_window_bounds.py.log.txt | - |
| 31 | `regression_lazy_select_orphan_option.py` | PASS | 0 | 2.37 | - | evidence/FullSelfTest/logs/31_regression_lazy_select_orphan_option.py.log.txt | - |
| 32 | `regression_metrics_horizon_semantics.py` | PASS | 0 | 0.26 | - | evidence/FullSelfTest/logs/32_regression_metrics_horizon_semantics.py.log.txt | - |
| 33 | `regression_metrics_to_dict_nonfinite_safe.py` | PASS | 0 | 0.26 | - | evidence/FullSelfTest/logs/33_regression_metrics_to_dict_nonfinite_safe.py.log.txt | - |
| 34 | `regression_migrate_backup_dir_none_creates_backup.py` | PASS | 0 | 0.36 | - | evidence/FullSelfTest/logs/34_regression_migrate_backup_dir_none_creates_backup.py.log.txt | - |
| 35 | `regression_migrate_v2_unify_workcalendar_day_type.py` | PASS | 0 | 0.87 | - | evidence/FullSelfTest/logs/35_regression_migrate_v2_unify_workcalendar_day_type.py.log.txt | - |
| 36 | `regression_migrate_v4_sanitize_enum_text_fields.py` | PASS | 0 | 0.84 | - | evidence/FullSelfTest/logs/36_regression_migrate_v4_sanitize_enum_text_fields.py.log.txt | - |
| 37 | `regression_model_enums_case_insensitive.py` | PASS | 0 | 0.31 | - | evidence/FullSelfTest/logs/37_regression_model_enums_case_insensitive.py.log.txt | - |
| 38 | `regression_models_numeric_parse_hybrid_safe.py` | PASS | 0 | 0.30 | - | evidence/FullSelfTest/logs/38_regression_models_numeric_parse_hybrid_safe.py.log.txt | - |
| 39 | `regression_operator_calendar_override_allows_work_on_global_holiday.py` | PASS | 0 | 0.60 | - | evidence/FullSelfTest/logs/39_regression_operator_calendar_override_allows_work_on_global_holiday.py.log.txt | - |
| 40 | `regression_operator_machine_missing_columns.py` | PASS | 0 | 0.33 | - | evidence/FullSelfTest/logs/40_regression_operator_machine_missing_columns.py.log.txt | - |
| 41 | `regression_optimizer_ortools_logging_exc_info_safe.py` | PASS | 0 | 0.45 | - | evidence/FullSelfTest/logs/41_regression_optimizer_ortools_logging_exc_info_safe.py.log.txt | - |
| 42 | `regression_optional_ready_constraint.py` | PASS | 0 | 0.65 | - | evidence/FullSelfTest/logs/42_regression_optional_ready_constraint.py.log.txt | - |
| 43 | `regression_ortools_budget_guard_skip_when_no_time.py` | PASS | 0 | 0.47 | - | evidence/FullSelfTest/logs/43_regression_ortools_budget_guard_skip_when_no_time.py.log.txt | - |
| 44 | `regression_ortools_warmstart_skip_nonfinite.py` | PASS | 0 | 0.10 | - | evidence/FullSelfTest/logs/44_regression_ortools_warmstart_skip_nonfinite.py.log.txt | - |
| 45 | `regression_plugin_manager_error_trace_visible.py` | PASS | 0 | 0.40 | - | evidence/FullSelfTest/logs/45_regression_plugin_manager_error_trace_visible.py.log.txt | - |
| 46 | `regression_priority_weight_case_insensitive.py` | PASS | 0 | 0.27 | - | evidence/FullSelfTest/logs/46_regression_priority_weight_case_insensitive.py.log.txt | - |
| 47 | `regression_process_excel_part_operation_hours_import.py` | PASS | 0 | 2.65 | - | evidence/FullSelfTest/logs/47_regression_process_excel_part_operation_hours_import.py.log.txt | - |
| 48 | `regression_reports_export_version_default_latest.py` | PASS | 0 | 2.55 | - | evidence/FullSelfTest/logs/48_regression_reports_export_version_default_latest.py.log.txt | - |
| 49 | `regression_route_parser_op_type_category_case_insensitive.py` | PASS | 0 | 1.05 | - | evidence/FullSelfTest/logs/49_regression_route_parser_op_type_category_case_insensitive.py.log.txt | - |
| 50 | `regression_route_parser_preserve_errors_when_no_matches.py` | PASS | 0 | 7.71 | - | evidence/FullSelfTest/logs/50_regression_route_parser_preserve_errors_when_no_matches.py.log.txt | - |
| 51 | `regression_sanitize_batch_dates_single_digit.py` | PASS | 0 | 0.32 | - | evidence/FullSelfTest/logs/51_regression_sanitize_batch_dates_single_digit.py.log.txt | - |
| 52 | `regression_schedule_input_builder_safe_float_parse.py` | PASS | 0 | 0.47 | - | evidence/FullSelfTest/logs/52_regression_schedule_input_builder_safe_float_parse.py.log.txt | - |
| 53 | `regression_schedule_service_missing_resource_source_case_insensitive.py` | PASS | 0 | 0.48 | - | evidence/FullSelfTest/logs/53_regression_schedule_service_missing_resource_source_case_insensitive.py.log.txt | - |
| 54 | `regression_scheduler_accepts_start_dt_string_and_safe_weights.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/54_regression_scheduler_accepts_start_dt_string_and_safe_weights.py.log.txt | - |
| 55 | `regression_scheduler_enforce_ready_default_from_config.py` | PASS | 0 | 0.67 | - | evidence/FullSelfTest/logs/55_regression_scheduler_enforce_ready_default_from_config.py.log.txt | - |
| 56 | `regression_scheduler_nonfinite_efficiency_fallback.py` | PASS | 0 | 0.26 | - | evidence/FullSelfTest/logs/56_regression_scheduler_nonfinite_efficiency_fallback.py.log.txt | - |
| 57 | `regression_scheduler_reject_nonfinite_and_invalid_status.py` | PASS | 0 | 0.60 | - | evidence/FullSelfTest/logs/57_regression_scheduler_reject_nonfinite_and_invalid_status.py.log.txt | - |
| 58 | `regression_seed_results_dedup.py` | PASS | 0 | 0.24 | - | evidence/FullSelfTest/logs/58_regression_seed_results_dedup.py.log.txt | - |
| 59 | `regression_seed_results_drop_duplicate_op_id_and_bad_time.py` | PASS | 0 | 0.24 | - | evidence/FullSelfTest/logs/59_regression_seed_results_drop_duplicate_op_id_and_bad_time.py.log.txt | - |
| 60 | `regression_seed_results_freeze_missing_resource.py` | PASS | 0 | 0.27 | - | evidence/FullSelfTest/logs/60_regression_seed_results_freeze_missing_resource.py.log.txt | - |
| 61 | `regression_seed_results_invalid_op_id_dedup.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/61_regression_seed_results_invalid_op_id_dedup.py.log.txt | - |
| 62 | `regression_sgs_atc_penalize_missing_resources.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/62_regression_sgs_atc_penalize_missing_resources.py.log.txt | - |
| 63 | `regression_sgs_penalize_nonfinite_proc_hours.py` | PASS | 0 | 0.27 | - | evidence/FullSelfTest/logs/63_regression_sgs_penalize_nonfinite_proc_hours.py.log.txt | - |
| 64 | `regression_sgs_scoring_fallback_unscorable.py` | PASS | 0 | 0.29 | - | evidence/FullSelfTest/logs/64_regression_sgs_scoring_fallback_unscorable.py.log.txt | - |
| 65 | `regression_sgs_scoring_machine_operator_id_type_safe.py` | PASS | 0 | 0.26 | - | evidence/FullSelfTest/logs/65_regression_sgs_scoring_machine_operator_id_type_safe.py.log.txt | - |
| 66 | `regression_skill_rank_mapping.py` | PASS | 0 | 0.67 | - | evidence/FullSelfTest/logs/66_regression_skill_rank_mapping.py.log.txt | - |
| 67 | `regression_sort_strategies_priority_case_insensitive.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/67_regression_sort_strategies_priority_case_insensitive.py.log.txt | - |
| 68 | `regression_sort_strategy_case_insensitive.py` | PASS | 0 | 0.25 | - | evidence/FullSelfTest/logs/68_regression_sort_strategy_case_insensitive.py.log.txt | - |
| 69 | `regression_sqlite_detect_types_enabled.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/69_regression_sqlite_detect_types_enabled.py.log.txt | - |
| 70 | `regression_startup_host_portfile.py` | PASS | 0 | 9.48 | - | evidence/FullSelfTest/logs/70_regression_startup_host_portfile.py.log.txt | - |
| 71 | `regression_system_logs_delete_no_clamp.py` | PASS | 0 | 2.44 | - | evidence/FullSelfTest/logs/71_regression_system_logs_delete_no_clamp.py.log.txt | - |
| 72 | `regression_system_maintenance_jobstate_commit.py` | PASS | 0 | 1.04 | - | evidence/FullSelfTest/logs/72_regression_system_maintenance_jobstate_commit.py.log.txt | - |
| 73 | `regression_template_no_inline_event_jinja.py` | PASS | 0 | 0.18 | - | evidence/FullSelfTest/logs/73_regression_template_no_inline_event_jinja.py.log.txt | - |
| 74 | `regression_template_urlfor_endpoints.py` | PASS | 0 | 2.38 | - | evidence/FullSelfTest/logs/74_regression_template_urlfor_endpoints.py.log.txt | - |
| 75 | `regression_tojson_zh_autoescape.py` | PASS | 0 | 2.31 | - | evidence/FullSelfTest/logs/75_regression_tojson_zh_autoescape.py.log.txt | - |
| 76 | `regression_transaction_savepoint_nested.py` | PASS | 0 | 0.27 | - | evidence/FullSelfTest/logs/76_regression_transaction_savepoint_nested.py.log.txt | - |
| 77 | `regression_unit_excel_converter_merge_steps_and_classify.py` | PASS | 0 | 1.22 | - | evidence/FullSelfTest/logs/77_regression_unit_excel_converter_merge_steps_and_classify.py.log.txt | - |
| 78 | `run_complex_excel_cases_e2e.py` | PASS | 0 | 1774.09 | evidence/ComplexExcelCases/complex_cases_report.md<br/>evidence/ComplexExcelCases/complex_cases_summary.json | evidence/FullSelfTest/logs/78_run_complex_excel_cases_e2e.py.log.txt | - |

## 说明

- 本 runner **不会**执行 PyInstaller / dist / validate_dist_exe 等打包流程。
- 复杂 Excel 用例的重产物目录默认会被 `.gitignore` 忽略，仅保留报告与 summary JSON。

