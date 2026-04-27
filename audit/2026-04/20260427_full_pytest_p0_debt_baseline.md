# Full pytest P0 debt baseline

本文件记录 main-style 子进程隔离后的正式 full pytest 债务基线，可作为任务 5 导入测试债务台账的正式输入。

- baseline_kind: `after_main_style_isolation`
- importable: `true`
- exitstatus: `1`
- collected_count: `588`
- failed_nodeid_count: `5`

<!-- APS-FULL-PYTEST-BASELINE:BEGIN -->
```json
{
  "baseline_kind": "after_main_style_isolation",
  "classifications": {
    "candidate_test_debt": [
      "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows"
    ],
    "main_style_isolation_candidate": [],
    "required_or_quality_gate_self_failure": []
  },
  "collected_nodeids": [
    "tests/regression/regression_collection_contract.py::regression_collection_contract",
    "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
    "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
    "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
    "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
    "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
    "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
    "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
    "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
    "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
    "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
    "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
    "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
    "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
    "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
    "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
    "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
    "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
    "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
    "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
    "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
    "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
    "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
    "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
    "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
    "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
    "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
    "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
    "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
    "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
    "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
    "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
    "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
    "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
    "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
    "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
    "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
    "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
    "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
    "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
    "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
    "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
    "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
    "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
    "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
    "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
    "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
    "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
    "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
    "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
    "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
    "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
    "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
    "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
    "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
    "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
    "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
    "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
    "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
    "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
    "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
    "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
    "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
    "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
    "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
    "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
    "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
    "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
    "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
    "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
    "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
    "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
    "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
    "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
    "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
    "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
    "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
    "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
    "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
    "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
    "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
    "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
    "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
    "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
    "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
    "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
    "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
    "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
    "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
    "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
    "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
    "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
    "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
    "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
    "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
    "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
    "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
    "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
    "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
    "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
    "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
    "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
    "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
    "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
    "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
    "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
    "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
    "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
    "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
    "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
    "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
    "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
    "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
    "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
    "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
    "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
    "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
    "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
    "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
    "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
    "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
    "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
    "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
    "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
    "tests/regression_restore_success_condition.py::regression_restore_success_condition",
    "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
    "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
    "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
    "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
    "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
    "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
    "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
    "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
    "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
    "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
    "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
    "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
    "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
    "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
    "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
    "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
    "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
    "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
    "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
    "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
    "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
    "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
    "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
    "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
    "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
    "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
    "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
    "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
    "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
    "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
    "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
    "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
    "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
    "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
    "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
    "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
    "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
    "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
    "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
    "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
    "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
    "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
    "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
    "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
    "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
    "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
    "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
    "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
    "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
    "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
    "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
    "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
    "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
    "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
    "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
    "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
    "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
    "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
    "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
    "tests/regression_system_health_route.py::regression_system_health_route",
    "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
    "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
    "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
    "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
    "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
    "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
    "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
    "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
    "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
    "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
    "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
    "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
    "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
    "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
    "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
    "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
    "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
    "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
    "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
    "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
    "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
    "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
    "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
    "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
    "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
    "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
    "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
    "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
    "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
    "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
    "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
    "tests/test_architecture_fitness.py::test_no_wildcard_imports",
    "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
    "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
    "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
    "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
    "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
    "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
    "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
    "tests/test_architecture_fitness.py::test_file_size_limit",
    "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
    "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
    "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
    "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
    "tests/test_architecture_fitness.py::test_file_naming_snake_case",
    "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
    "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
    "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
    "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
    "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
    "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
    "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
    "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
    "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
    "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
    "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
    "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
    "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
    "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
    "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
    "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
    "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
    "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
    "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
    "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
    "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
    "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
    "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
    "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
    "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
    "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
    "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
    "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
    "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
    "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
    "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
    "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
    "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
    "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_importable_debt_baseline",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_after_isolation_and_output_file",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_blocked_classifications",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_bad_pytest_invocation",
    "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
    "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
    "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
    "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
    "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
    "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
    "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
    "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
    "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
    "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
    "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
    "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
    "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
    "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
    "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
    "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
    "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
    "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
    "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
    "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
    "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
    "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
    "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
    "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
    "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
    "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
    "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
    "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
    "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
    "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
    "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
    "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
    "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
    "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
    "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
    "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
    "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
    "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
    "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
    "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
    "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
    "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
    "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
    "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
    "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
    "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
    "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
    "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
    "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
    "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
    "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
    "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
    "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
    "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
    "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
    "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
    "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
    "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
    "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
    "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
    "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
    "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
    "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
    "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
    "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
    "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
    "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
    "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
    "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
    "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
    "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
    "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
    "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
    "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
    "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
    "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
    "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
    "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
    "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
    "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
    "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
    "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
    "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
    "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
    "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
    "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
    "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
    "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
    "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
    "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
    "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
    "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
    "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
    "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
    "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
    "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
    "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
    "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
    "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
    "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
    "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
    "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
    "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
    "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
    "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
    "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
    "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
    "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
    "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
    "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
    "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
    "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
    "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
    "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
    "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
    "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
    "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
    "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
    "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
    "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
    "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
    "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
    "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
    "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
    "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
    "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
    "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
    "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
    "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
    "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
    "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
    "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
    "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
    "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
    "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
    "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
    "tests/test_query_services.py::test_batch_query_service_has_any",
    "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
    "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
    "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
    "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
    "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
    "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
    "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
    "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
    "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
    "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
    "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
    "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
    "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
    "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
    "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
    "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
    "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
    "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
    "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
    "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
    "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
    "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
    "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
    "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
    "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
    "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
    "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
    "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
    "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
    "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
    "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
    "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
    "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
    "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
    "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
    "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
    "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
    "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
    "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
    "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
    "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
    "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
    "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
    "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
    "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
    "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
    "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
    "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
    "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
    "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
    "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
    "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
    "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
    "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
    "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
    "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
    "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
    "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
    "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
    "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
    "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
    "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
    "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
    "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
    "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
    "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
    "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
    "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
    "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
    "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
    "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
    "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
    "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
    "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
    "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
    "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
    "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
    "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
    "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
    "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
    "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
    "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
    "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
    "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
    "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
    "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
    "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
    "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
    "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
    "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
    "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
    "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
    "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
    "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
    "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
    "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
    "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
    "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
    "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
    "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
    "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
    "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
    "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
    "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
    "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
    "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
    "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
    "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
    "tests/test_system_services.py::test_operation_log_service_list_and_delete",
    "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
    "tests/test_system_services.py::test_system_config_service_get_value",
    "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
    "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
    "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
    "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
    "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
    "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
    "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
    "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
    "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
    "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
    "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
    "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
    "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
    "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
    "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
    "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
    "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
    "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
    "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
    "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
    "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
    "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
    "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
    "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
    "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
    "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
    "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
    "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
    "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
    "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
    "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
    "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
    "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
    "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
    "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
    "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
    "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
    "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
    "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
    "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
    "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
    "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
    "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
    "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
    "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
    "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
    "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
    "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
    "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
    "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
    "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
    "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
    "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises"
  ],
  "collection_errors": [],
  "exitstatus": 1,
  "generated_at": "2026-04-27T07:56:23+08:00",
  "head_sha": "ee96b3248a2bdf8abf48a5c5eba8d152379c8fdf",
  "importable": true,
  "pytest_args": [
    "tests",
    "-q",
    "--tb=short",
    "-ra",
    "-p",
    "no:cacheprovider"
  ],
  "pytest_version": "8.3.5",
  "python_executable": "/Users/lurenxing/Documents/GitHub/----/.venv/bin/python",
  "python_version": "3.8.10 (v3.8.10:3d8993a744, May  3 2021, 09:09:08) ",
  "reports": [
    {
      "duration": 0.0031645829999999986,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.020485124999999993,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.262499999999283e-05,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.545799999999822e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5312964170000001,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.624999999999993e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.90409999999164e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5308968750000002,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011220800000000253,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.825000000008295e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5667615420000001,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.650000000003487e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.162499999977754e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.537881542,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.437500000020194e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.10840000003121e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.043242375000000166,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.374999999987253e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.758299999980565e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04723912499999994,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.112499999983868e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.629199999994782e-05,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03411029199999982,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.575000000015208e-05,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6750000000095326e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5739177500000001,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.891700000024372e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9082999999949806e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09243808399999986,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.379100000015626e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.679199999970464e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5860236250000002,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.437500000013642e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.333299999994324e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.037622500000000336,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.420800000002004e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.816700000009888e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.043058416000000044,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.983300000040771e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.71669999999591e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.042099125000000015,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.054200000045086e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.820799999993852e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09049454200000007,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.733400000020652e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.158299999941107e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09375633400000005,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.950000000014114e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.104199999994563e-05,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.026983415999999316,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.591599999961062e-05,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.766600000039034e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6103708750000001,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.754100000045838e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.850000000011789e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05492737500000011,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.541600000049442e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.820799999993852e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5772133329999996,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.920799999983075e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0875000000338844e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09932245900000058,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.19999999995369e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.858299999987992e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04723987499999982,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.366700000017602e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.370800000026321e-05,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.5791342499999992,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0018371659999996126,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001722499999994298,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.039659333999999546,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010300000000018628,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.570800000016419e-05,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03333025000000056,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.26660000004631e-05,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.108300000067345e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6507783329999999,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.033400000011625e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8249999999860904e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03602929200000027,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.399999999968543e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8042000000414475e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5722480829999999,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.424999999905424e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8999999998855515e-05,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.023398792000000057,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.579200000089713e-05,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.708300000011434e-05,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08638374999999954,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.120800000099848e-05,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.970800000047575e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05575483299999995,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.816699999985133e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9583999999214257e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.046234250000001254,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.100000000155205e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.791699999984189e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.041480041999999884,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.329199999934644e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.895900000079223e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04244883399999999,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.183400000165818e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.71669999999591e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.041185374999999524,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.674999999845e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7208999999881485e-05,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.042913709000000466,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.216600000070628e-05,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7500000000866294e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10616079200000073,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.487499999925262e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.850000000011789e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10575933299999996,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.991700000114065e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7750000000235104e-05,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04518333300000066,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.966699999999548e-05,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.391600000059782e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06294974999999958,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.037499999995589e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.81669999992107e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5790841250000014,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.679200000154651e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.029200000095102e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12099295900000051,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.287500000074942e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.93340000016218e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.029216207999999355,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.508300000047541e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7500000000866294e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.8714384580000001,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.179199999958087e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7792000000157486e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09562895800000071,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.216600000070628e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.816700000098706e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1478791250000011,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.779199999902175e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8334000000593846e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03668866699999995,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.208400000064842e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.304199999933701e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6179584589999987,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.562499999913541e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.945799999944711e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6405429999999992,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.579200000013998e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.816599999912796e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.019713208999998955,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.770899999925973e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6417000000076314e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.027805458000001337,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.966700000101469e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0917000001149404e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04302337500000064,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.899999999949614e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8249999998972726e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0339555830000009,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.374999999955946e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001293330000002868,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1924689999999991,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.258299999968187e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8333000000511106e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.18815587499999964,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.245799999999747e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.754099999892958e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.19584091599999986,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.387499999924387e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1624999999333454e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10201325000000061,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.854200000030232e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.254100000051665e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08976224999999971,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.833299999937537e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.141699999950845e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08996512499999909,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.187499999934289e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.183300000055624e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04427454200000014,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.429099999991308e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3583000001466985e-05,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08055874999999979,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.979200000107767e-05,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.883399999933147e-05,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.021464458999998826,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.587500000065916e-05,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.537500000090233e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5812638329999995,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.058299999902374e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9291999999923064e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5526999999999997,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.516700000032017e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.866599999964194e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.15786675000000017,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.962499999931595e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.895800000033091e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5804958330000005,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.200000000118223e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.837499999865713e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04388783300000121,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.133300000106146e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.762499999877434e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.581031458,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.64999999987026e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.912500000031628e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04381612499999932,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.737500000004616e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.037500000033447e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04386291699999845,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001656250000010573,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.191700000002243e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04270970800000029,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.57079999967425e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.829200000169067e-05,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02869833299999769,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.66670000018621e-05,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.962499999867532e-05,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04788066599999752,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.487500000280534e-05,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.795799999968153e-05,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5757888749999971,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.708300000075496e-05,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.054100000023709e-05,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05088512500000064,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.883300000026793e-05,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.491699999841785e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06617029099999883,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.33339999996474e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.229099999823575e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05169404200000116,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.324999999942406e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.5708000001430946e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04931133299999857,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.079100000202288e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.250000000245336e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.059221000000000856,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.833300000115173e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.941699999960747e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.043616790999998045,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010283299999969131,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.124999999850388e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04285491699999966,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.820799999829319e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9749999998738303e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.042432166000001104,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.695900000077472e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.458299999716587e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05395012500000007,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.37909999983799e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.5041999999616564e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.057599583000001786,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.766699999971593e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7999999999603915e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.057420125000000155,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.287500000074942e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9291999999923064e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03629416600000113,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0002177920000008271,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.508300000187319e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.032036208000000954,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.175000000003706e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.345799999887049e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06032549999999759,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.258299999790552e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8875000000947466e-05,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.033021334000000735,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.937500000210207e-05,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.854199999826392e-05,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.031696207999999615,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.345799999887049e-05,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.149999999787269e-05,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13804512499999788,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.758299999949259e-05,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7500000000866294e-05,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02714595800000197,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.416600000060726e-05,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.104099999897471e-05,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04548525000000225,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.708300000037639e-05,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.76250000005507e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06046058300000112,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.320799999950168e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001698750000009852,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5871772499999999,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.64170000024933e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.362499999923443e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5681801670000013,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.670800000170175e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0667000000004236e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.042171791999997765,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.991700000114065e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.083299999952828e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04667204200000086,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.700000000137152e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7333000001259506e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.049412000000000234,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.312500000011823e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.875000000126306e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04649429200000199,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.795800000209852e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.366599999945265e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04720287499999998,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.366700000233095e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.92080000000783e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07539645900000025,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010779199999788602,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.8333000001908886e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05480658400000138,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.970799999768019e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.941699999960747e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.051492416999998625,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.174999999965848e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.116599999865912e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.020362875000000003,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.670799999852761e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.570899999833955e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.19154479100000188,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00026945800000177655,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010195800000190047,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09598937499999849,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.249999999776492e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.837500000183127e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09022775000000038,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.466599999972345e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.116699999874186e-05,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5879322080000016,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.349999999917145e-05,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.37919999992198e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06012854200000106,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.57500000002176e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.937499999968509e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06380270800000076,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.57500000002176e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.958399999883568e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.038125332999999983,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.391700000169976e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.012500000134423e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0377905829999996,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013825000000267096,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.229199999831849e-05,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.043707042000001195,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.04999999996403e-05,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.733400000134225e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6107715419999984,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.474999999956822e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9333999999845446e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6154674170000014,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.308300000019585e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.875000000126306e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5760865419999988,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.899999999987472e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.76250000005507e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5974398329999993,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.379200000201536e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.816599999912796e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6067024580000009,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.49160000022664e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.508400000309166e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5421950419999995,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.987499999728698e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.937499999968509e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5507732499999989,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.45000000001994e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.745800000094391e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09580770799999883,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.324999999942406e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8875000000947466e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6234898340000008,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.950000000216505e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.729099999778441e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5685016249999997,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.762499999979354e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.716600000165272e-05,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5992216249999984,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.487499999925262e-05,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.875000000126306e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08853300000000175,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001019589999984305,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3499999999928605e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08907704099999947,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012891700000139394,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00013225000000005593,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08842512500000055,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.379199999846264e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8833000001025084e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08967129200000201,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.11669999979847e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7999999999603915e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09085895799999832,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.762499999979354e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.724999999794477e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04520049999999998,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001031670000024576,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011254200000010428,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.5035848340000015,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.512499999862143e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.854199999826392e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.5792313339999993,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0003185420000022532,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040512500000033924,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.422556250000003,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011316699999852631,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.441700000119454e-05,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5367956250000034,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.008299999711198e-05,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.058400000024221e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.041855875000003095,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.3208999999963e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.816600000623339e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06873258299999918,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.983400000062147e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2999999994085556e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03679183300000233,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.775000000658338e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.570800000180952e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.057970333000000096,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.36659999986955e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8167000002763416e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.059274291999997786,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.149999999711554e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.874999999771035e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04581604199999845,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.720799999333394e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.862500000513137e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06212520900000129,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.291700000029323e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.200000000371574e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06007295799999923,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.583299999997962e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.329199999692946e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0686068750000004,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.454200000329593e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.212499999553756e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06924862500000017,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.675000000124555e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.84169999950268e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06457020899999577,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.216699999901266e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.725000000149748e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06814349999999791,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.54580000009264e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2541000002293003e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06636466700000199,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010874999999543888,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.845799999804058e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06829791700000243,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.570799999712108e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8582999994550846e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05120687499999832,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.779200000219589e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.262500000213777e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04922841700000191,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.05419999991841e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.737500000118189e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05090462500000115,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.637500000294949e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.566700000196988e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04947791699999726,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.245800000532654e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.008400000150459e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1800784580000041,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.333300000311738e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.812499999928832e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04779308300000196,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.366600000186963e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.216600000323979e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.588266124999997,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.604200000344008e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.449999999740385e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05730620799999997,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.154200000059063e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.758399999677977e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07547812500000362,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.587500000028058e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.76250000005507e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5776218749999984,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.800000000519503e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.491600000340213e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5899816659999999,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.88749999966376e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.062499999539341e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04531958300000127,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.816600000154494e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8708999997870706e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07156133299999823,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010287499999606098,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.991699999834509e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.15123291599999789,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.154200000059063e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.862499999802594e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5843830419999989,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.754099999919163e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.345900000008896e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05383091699999909,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.991700000076207e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.899999999707916e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6214294580000015,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.362499999885586e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.029199999739831e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.046412625000002095,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.954199999853472e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.920899999660833e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04416583300000099,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010516600000443077,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.366699999598268e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04588412500000061,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.179200000313358e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9959000001820186e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04969804200000283,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001239999999995689,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.395800000229656e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.049170166999999765,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.220800000202644e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.379099999913706e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.046060624999995525,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010466699999511775,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3332999996769104e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04890795800000092,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.966700000139326e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.237499999566353e-05,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.054878540999993675,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0002667500000015366,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00018479199999887896,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12466916700000041,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.745800000298232e-05,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.437499999771944e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0459118750000016,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.775000000265209e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.208299999992505e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04466845900000038,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.224999999522197e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.916700000023866e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.027097957999998812,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00028820800000062263,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010070799999795099,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04254783299999332,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.270799999758992e-05,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.912499999676356e-05,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.078003125000002,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016620899999963967,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.62499999993338e-05,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.834272999999996,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001195409999965591,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.204200000250239e-05,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10345404200000274,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00019162499999936244,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.941699999567618e-05,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03020233400000194,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.37500000017144e-05,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.92080000000783e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04957820799999979,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010808399999717722,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.620900000025131e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.0503017079999992,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.40000000050145e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.125000000167802e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5841912090000037,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.599999999996498e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8499999998341536e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5679819579999972,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.641699999538787e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.783299999961855e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07784908299999671,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.650000000187674e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.92080000000783e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04358925000000369,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010141700000332321,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8499999998341536e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03586737499999515,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010620900000191114,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.0541999999941254e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5393567079999997,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.370900000187476e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.704099999803702e-05,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5367217080000017,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013370799999989913,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.837500000183127e-05,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04576237499999536,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.120799999744577e-05,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.837499999865713e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.020024249999998744,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.724999999680904e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.679199999912953e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.20614675000000204,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.862500000044292e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8833000001025084e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09652816700000244,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010420799999621977,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.741700000072569e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08863529199999931,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.258299999397423e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.874999999771035e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.21185612499999706,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.704100000362814e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.59590000008825e-05,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.019969166000002758,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.154200000376477e-05,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.316699999724506e-05,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.46152587499999953,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00017879199999981665,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001584170000015206,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04275341700000013,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00018120800000076542,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.508300000187319e-05,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0785060000000044,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.508399999840321e-05,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.674999999489728e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003180749999998511,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00024499999999960664,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.887499999588044e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004019579999976486,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.20420000040167e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010487499999811689,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000643166000003248,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.61250000011637e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.341599999856953e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001676250000031132,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0625000000081855e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.5875000001037733e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014904199999676848,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.829200000637911e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.908299999887959e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006612079999968046,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.425000000196633e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0017605829999993716,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7411211249999994,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.820800000108875e-05,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000328249999995478,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7208783330000017,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.683299999745486e-05,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.520899999960193e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01677008299999727,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.63329999994744e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.34580000003848e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.027703666999997267,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.8249999995041435e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2082999996750914e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004482250000002352,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.641699999614502e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.195799999706651e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008916670000047588,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5624999998494786e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7541000000705935e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01885491699999875,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.825000000607815e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9833999998961644e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.012711625000001447,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.008400000150459e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.083299999990686e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02995183400000201,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.829200000244782e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.908400000085521e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.23004945799999632,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.062500000325599e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.504199999644243e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.23544545800000094,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.429200000151013e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.212500000022601e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1512010410000002,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0003152920000033532,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.995900000106303e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.594363708000003,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.808300000609279e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.433299999817564e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.035106292000001815,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.962500000260661e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.258300000259396e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.30484370899999647,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.949999999505962e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.020799999755354e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 2.338078875000001,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.520800000231475e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.295800000164718e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.017156042000003424,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.520800000624604e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.070899999675248e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.016100790999999504,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.387500000608725e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.079200000006722e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.021186749999998256,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.429200000151013e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.229199999628008e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.39055287500000446,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.7584000003885194e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.345899999691483e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3694640840000005,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.566700000121273e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6666999999445125e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002773458000000062,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.549999999881038e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003150000000005093,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2627906670000044,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.312499999936108e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003182499999994093,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2867920830000017,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.237499999808051e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00027495799999854853,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26706595799999633,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.695800000107056e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00027174999999601823,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26174199999999814,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.041599999586424e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003199580000057267,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26825066699999667,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.12080000045512e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.470800000433428e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005496660000048337,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.162500000148839e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.754200000116725e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00022066600000414383,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.024999999392321e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.841699999895809e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.554099999865002e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.029199999815546e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.466599999768505e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.4624999993914116e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1249999999261036e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3957999995948285e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.787499999991951e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.275000000257933e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4958000000528955e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.583400000512938e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0375000001470198e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3291999997686617e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00026820900000501524,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.812500000321961e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5584000002586436e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.241699999520733e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.287500000226373e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002678339999988566,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26437474999999466,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.991700000076207e-05,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003077910000044426,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2839248339999969,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.59999999960337e-05,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00029645800000110967,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0023818750000046407,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0166000001183875e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.787499999674537e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.920899999660833e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.133300000257577e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4666999994215075e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.80000000020209e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3041999998317806e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4042000002898476e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.670800000321606e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1082999996101535e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00023254199999911407,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002978374999997868,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.6957999994722286e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.266599999880327e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011712500000271575,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.375000000005457e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00025137499999772217,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.23887112500000285,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.458299999996143e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002502500000005625,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0028053330000048504,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.741600000102153e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00025312500000040927,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.276231082999999,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.495800000218878e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002797089999972968,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.24016412499999973,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.549999999412194e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00027154099999648906,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2713770000000011,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.004099999681102e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00030412499999954434,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2921357499999999,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.974999999760257e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002880420000010986,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.23578766600000023,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.004099999681102e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002932080000022097,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.23975950000000523,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.508400000157735e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.545800000244071e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0031131670000021927,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.012500000134423e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.258300000259396e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1801027499999961,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.554199999683988e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.141699999773209e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007783330000066258,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.191600000069684e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.920800000400959e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003020410000047491,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5167000000058124e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011012499999907277,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00030345800000475265,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.9583000006236944e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003738750000010782,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.17585995800000376,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00023254100000258404,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004459580000002461,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.16685695799999678,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014087499999959618,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004290420000003792,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13417129199999778,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015287500000482623,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034808299999866676,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1350576669999981,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001542079999978796,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004157079999984603,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1685868330000062,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001207919999970386,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00048037499999509237,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_importable_debt_baseline",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13306416700000057,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_importable_debt_baseline",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014708300000165764,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_importable_debt_baseline",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039587500000237696,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_after_isolation_and_output_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06666883300000137,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_after_isolation_and_output_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001085000000031755,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_after_isolation_and_output_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003709169999979167,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.430296833000007,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011295800000254985,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00048029199999177763,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_bad_pytest_invocation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12322541700000045,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_bad_pytest_invocation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001273750000052587,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_bad_pytest_invocation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.35420000034037e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.837499999789998e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.733300000874351e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6708999999746084e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.1166999995189144e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0499999994049176e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8333000006218754e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012020900000209167,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2292000000211374e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.508300000021336e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.67919999920241e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9999999995311555e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3291999997686617e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.458300000782401e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0082999998626292e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.579200000558558e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.095799999490282e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2124999989946446e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.354200001126628e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.041600000765811e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9625000010469194e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.325000000131695e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.237499999566353e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0499999994049176e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.22920000018712e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.791600000293329e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.745799999421706e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4374999998476596e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.77909999953863e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.25829999923144e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4916999993583886e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.624999999691681e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.025000000889122e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.579200000558558e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.304100001206734e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.933300000051986e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.704199999774119e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.5124999999757165e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3874999999738975e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.154100000481776e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.387500000291311e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.566699999169032e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.116599999155369e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.1124999998819476e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4374999998476596e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.312500000163254e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.175000000041564e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0417000004945294e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4708000001160144e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001239999999995689,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.154099999846949e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.579099998773927e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.812500000639375e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.987499999562715e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4666999994215075e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011675000000366254,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.029200000526089e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.220799999326118e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.783300000748113e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.933399998994446e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.487499999721422e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012762499999041665,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.558399998837558e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3417000011581877e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.007204125000001227,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.1416999994557955e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.058300000053805e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.016952958000004514,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.9500000002922206e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.970899999217181e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003067909999998619,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6165999986792485e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4958000000528955e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000159500000009416,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3625000000370164e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.208400000038637e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010974999999291413,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012395800000319923,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7291000001337125e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.7499999996935e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.858299999621067e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.650000000732234e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.73749999972506e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1374999991840014e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.649999999311149e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.666699999868797e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.433300000210693e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.52910000032125e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.9500000002922206e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9334000004155314e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.341699999737102e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.379099999596292e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.962499999625834e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.504099998963284e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.379199999490993e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.245800000684085e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3833999992793906e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.304200000149194e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9791999992312412e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7750000004166395e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.012499999665579e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.129200000273613e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.691599999910977e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002468330000056085,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.266699999926459e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.454199999453067e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00016483400000311121,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.204200000084256e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4666999994215075e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.224999999915326e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.058299999736391e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4958000000528955e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.879200000435958e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.983299999925748e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.266699999926459e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001362910000040074,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.183299999420797e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2541999999580185e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.741600000102153e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.104200000336732e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.591700000526998e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.2334000002929315e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.958299999988867e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.308400000889833e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013583300000163945,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.149999999152442e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3459000007951545e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.070800000339659e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9499999996573933e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5207999999897766e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.212500000581713e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1082999996101535e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3041999998317806e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001617500000037353,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.170799999452356e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2541999999580185e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010212499999795455,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.204099999720711e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.816699999807497e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001848750000021937,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8041000010480275e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.908399999692392e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015029100001129336,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.479199999707362e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.512499999658303e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.720800001223324e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9542000007154456e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5457999999266576e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.3750000003228706e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0042000005892078e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.375000000640284e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00022733299999799783,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.17079999976977e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8708000008446106e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00017266599999743448,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8833999994380974e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037549999998987005,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2889975829999969,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.279200000060882e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032737499999768715,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2709642079999952,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.949999999823376e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003478330000064034,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2720461669999992,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.949999999823376e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034345800000323834,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27212300000000766,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.383300000502913e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003409579999953394,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2953084170000011,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.412499998655676e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034441700000797937,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.264015332999989,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011845899999229914,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035966699999789853,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2777415420000011,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011687500000334694,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034729099999708524,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27204891699999223,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.500000000959517e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002921669999977894,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2621751660000058,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.12910000007605e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00031291599999860864,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2852134580000012,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.891700001039226e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4291999998335996e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004528749999934689,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.0957999999591266e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00036066699999537377,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2707764160000039,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.804200001260142e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00030904200001202753,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2728810419999945,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.883299999557948e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003505829999994603,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27088366700000677,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.933299998796883e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003200000000020964,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2705424579999942,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.116599999003938e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.52080000030719e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001390000000043301,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.512499999658303e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5749999995005055e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.0750000002940396e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5584000002586436e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.812500000321961e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013702500000078999,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.237500000352611e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.383299998915845e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.029200000374658e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.125000000636646e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.308299999105202e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001051660000115362,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3417000011581877e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.40420000100039e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.920800000249528e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.191600001173356e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2665999995629136e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002386249999943857,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6667000003376415e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.424999999879219e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00025579100000072685,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.233299999929386e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.887499999346346e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.295900001087375e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.841699999895809e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.758300000811232e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.079099999567461e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.366699999673983e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.529200000684796e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002193750000003547,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.845800000590316e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.008300000180043e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011971670000008316,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4374999998476596e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.491600000415929e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009258340000002363,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.399999999942338e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.487499999721422e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008850419999930637,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.520900000353322e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.554200000621677e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011374589999917362,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.424999999879219e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.487499999721422e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009062499999998863,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.350000000068576e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.454199999453067e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009402090000065755,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.529200000684796e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000129959000005897,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010680829999927255,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.8375000008936695e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001980830000007927,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010814160000052198,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.504099998811853e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001123750000004975,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000947957999997584,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.991700000151923e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.925000000521322e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0015614579999976286,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.045899999662652e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.99999999891088e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010021249999994097,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.704100000514245e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.458400000511119e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013187910000027614,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.420800000559666e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011129199999970751,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.040845915999994986,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.637500000929776e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.658299999808605e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00029433299999936935,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.1374999998188287e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0666999993277386e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.2041000000381246e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0332999997995103e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.40420000100039e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.7792000000536063e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9374999996889528e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.341600000794642e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.375000000005457e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.041699999073444e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.625000000795353e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.870899999469657e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9249999997205123e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.275000000257933e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.604200000495439e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9458999989628865e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.420799998821167e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00103120799998635,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.395800000305371e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.633300001126827e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009250420000057602,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3083000005262875e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.266699999926459e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000900584000007143,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.37080000036849e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.55000000098471e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008952499999992369,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2957999991367615e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5834000001955246e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008895410000064885,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.366699999673983e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.308299999105202e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012692920000034746,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.387500000291311e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.362500000202999e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.23976845800000035,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.883299999557948e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5999999997548e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.612500001310309e-05,
      "longrepr": "tests/test_operator_machine_exception_paths.py:45: in test_normalize_skill_level_optional_only_converts_value_error\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/Users/lurenxing/Documents/GitHub/----/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00010625000000175078,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5916999994233265e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.30419999968035e-05,
      "longrepr": "tests/test_operator_machine_exception_paths.py:54: in test_normalize_skill_level_stored_only_falls_back_for_value_error\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/Users/lurenxing/Documents/GitHub/----/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.0001027080000000069,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3417000003719295e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001162457999996036,
      "longrepr": "tests/test_operator_machine_exception_paths.py:72: in test_list_by_operator_propagates_unexpected_readside_normalization_errors\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/Users/lurenxing/Documents/GitHub/----/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00014533300000607596,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.6916999994882644e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001453584000003616,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8957999990429926e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.645799999674182e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009517909999914309,
      "longrepr": "tests/test_operator_machine_exception_paths.py:128: in test_resolve_write_values_only_converts_validation_error\n    assert new_skill is None\nE   AssertionError: assert 'normal' is None",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 4.199999999343618e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.591700000526998e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00019454099999904884,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.62920000043232e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6041000001318935e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011966700000698438,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.11249999924712e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.399999999942338e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.158299999801329e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9458000000204265e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.758299999390147e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001273750000052587,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.074999999659212e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011187500000175987,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.833300000939289e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3333000004631685e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1125000009856194e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005583749999971133,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6375000007637937e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.695799999547944e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001931249999955753,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5249999996267434e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4124999999107786e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002259169999945243,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.29169999986334e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.404199999579305e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014187499999707143,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.433399999636549e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.479100000447488e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00016687500000500677,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3583999993425095e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4166999995477454e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.770800000310828e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.070800001125917e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.220899999220819e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00042029199998694367,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.437500000165073e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.4208999998195395e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.774999999161537e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.02499999978545e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.962500000260661e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011087499999007377,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.850000000227283e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.862500000513137e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.454199999301636e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.770799999358587e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.85839999981863e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.3917000002456916e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.008300000180043e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.841700000213223e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013220799999658084,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8291999999273685e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.754200000434139e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.137500000453656e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.783299999327028e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.595900000163965e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.487499999569991e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.195800000810323e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.424999999879219e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001272919999877331,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2500000003210516e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.604099998710808e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001254542000012293,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.66669999923397e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.962499999474403e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011305829999912476,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.67919999920241e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.800000000988348e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000751208000011161,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.400000000259752e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.674999999882857e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013391599999579284,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.0999999995960934e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.016599999407845e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011933300000066538,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.3542000000229564e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0833000003081e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013687499999548436,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.949999999974807e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.7082999987301264e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011912499999766624,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9333000003693996e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.562499999532065e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001105829999943353,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.124999999215561e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.341600000794642e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002274999999940519,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3375000001001354e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.570900000227084e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012087499999324791,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.179200000147375e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.424999999879219e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00029183300000568124,
      "longrepr": "tests/test_query_services.py:163: in test_operator_machine_query_service_lists_with_names_and_linkage_rows\n    assert simple == [\nE   assert [{'dirty_fiel...': 'M2', ...}] == [{'is_primary...: 'beginner'}]\nE     \nE     At index 0 diff: {'operator_id': 'O1', 'machine_id': 'M1', 'skill_level': 'expert', 'is_primary': 'yes', 'dirty_fields': ['skill_level'], 'dirty_reasons': {'skill_level': \"历史技能等级 'high' 已兼容归一为 expert。\"}} != {'operator_id': 'O1', 'machine_id': 'M1', 'skill_level': 'expert', 'is_primary': 'yes'}\nE     Use -v to get more diff",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 4.50830000033875e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0416999993908576e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00016875000000027285,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.345800000431609e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002917910000093116,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11636883299999567,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011737500000208456,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004261249999899519,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.0171071249999954,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0003450829999991356,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0006214590000013231,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.15398570799999334,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016599999999300508,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.475000000705222e-05,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3706145409999948,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.46669999958749e-05,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.495800000687723e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.029200000692072e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.350000000068576e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6582999996426224e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010553329999964944,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.712500000574437e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037941600000124254,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005547500000062655,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.187499999692591e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00023312500000827185,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000712042000003521,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.891700000086985e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00024725000000103137,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27044341699999563,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011529100000018389,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003567920000051572,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26795758400000125,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001276250000046275,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040408399999591893,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2663712909999987,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014937500000655746,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005248330000000578,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26963916700000823,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012516700000730907,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003675420000064378,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.016783875000001558,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011599999999134525,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.191600000387098e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.462500000267937e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4374999998476596e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6332999997057414e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.358300001034877e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1208999999421394e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040070900000444,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28999687499999993,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001190419999943515,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039925000000096134,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14546962500000404,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010966600000017479,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003982909999962203,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2938782079999953,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001067500000004884,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003936660000078973,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29533987499999625,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011929100000429571,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004903330000018968,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5801183750000121,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.812500000805358e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003954169999929036,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2655722500000053,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010195800000190047,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005209170000028962,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2662535830000081,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001347080000044798,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0006996250000099735,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2700644999999895,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.987500000363525e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.891700000086985e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005967079999891212,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.845899999532776e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.199999999192187e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008609580000040751,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.725000001177705e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00013454199999785033,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000333083000001011,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.695800000500185e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00030241700000033234,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04150958400001059,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012362500000051568,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.804200000307901e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012147499999883848,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.6042000008128525e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.912500000386899e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005734589999946138,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.6084000004498193e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003852499999936754,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12430054200000029,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014662499999928968,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011500000000808086,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000623707999992007,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.8041999988868156e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.9750000005465154e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004725830000040787,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015154199999756202,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004171670000090444,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004924250000001962,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.712500000423006e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.36250000035443e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.23363212499999975,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.820800000819418e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005681250000009186,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02391308400000014,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010224999999763895,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003209169999962569,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.021582666999989897,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010879200000601941,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032866700000511173,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.019623250000009307,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014504200001397294,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000376291999998557,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02009287500000312,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001158750000058717,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003737499999942884,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01952820900000063,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.437500000331056e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.720799999802239e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000511833000004458,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001922089999908394,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004805000000089876,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.019293958000005773,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011454199999150205,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003463750000065602,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.022013624999999593,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011095799999338851,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3167000004350484e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000106959000007123,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.704199998821878e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1749999994067366e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.13750000077107e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.487500001142507e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7665999997216204e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.620800000372128e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4708999990584744e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.999999999848569e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002930830000025253,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.625000000795353e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.620900000100846e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012616600000114886,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.195799999389237e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2915999994997946e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014904100000023845,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2415999996260325e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.29169999986334e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011645800000792406,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3333000004631685e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.52910000032125e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012033299999814062,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.162500000541968e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.283400000952952e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001189169999946671,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.195800000810323e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.287500000226373e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002703749999994898,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5499999995636244e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.533399998900677e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.849999999123611e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1500000005735274e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.295800000557847e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000113291999994658,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.300000000194814e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.29169999986334e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012775000000431191,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.350000000068576e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5207999999897766e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.329199999617231e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.041600000130984e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3291999997686617e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.804200000473884e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2292000000211374e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032512500000336786,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4038429579999985,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.208399999887206e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00033966699999155026,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.43411420900000053,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.275000000423915e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003390830000000733,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.404957875000008,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.383399999762787e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00042991600000164,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4383452910000045,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.891599999254595e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034641700000292985,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3918510000000026,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.887500000616001e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037299999999618194,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3673105000000021,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.512499999824286e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00033650000000307045,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3916636249999925,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001451669999994465,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004013749999955962,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3690607500000027,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.887499999981173e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3000000005122274e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.579199998986041e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.579099998773927e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8667000012537756e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.7499999996935e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1458000009365605e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0027253330000007736,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0015766249999984439,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.233299999777955e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.112499999564534e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.4207999991385805e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.166700000178935e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.491600000415929e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.779199999267348e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1374999991840014e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5499999995636244e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.325000000766522e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.074999999341799e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.741599999784739e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.7541999990130535e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9999999995311555e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.6125000000406544e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.008465041999997425,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.275000001210174e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.88749999966376e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.007202625000005014,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.720800000437066e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.933299999900555e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00769187499999191,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.179199999995944e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.387500001243552e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.007108375000001388,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.858300000089912e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.13749999903257e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.008126832999991507,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.804199999839057e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.366699998887725e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002539999999982001,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.566699999169032e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5084000003848814e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.99170000078675e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.258399999594985e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.725000000860291e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00018337500000598084,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3625000000370164e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.454199999453067e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.420800000408235e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.154200000210494e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4458000001791333e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001290830000044707,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1750000005104084e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4666999994215075e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001019169999949554,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0417000004945294e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2707999991998804e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.912499999918055e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.100000000699765e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003402499999936026,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5243990419999989,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.329099999571099e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.508299998917664e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007981669999992391,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5124999999757165e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9624999999432475e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00031554099999198115,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.649999999311149e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.783299999327028e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.362499999568172e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.137500000605087e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8291999999273685e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.262499999820648e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1374999991840014e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.458300000147574e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.49170000031063e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.170799999452356e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.274999998836847e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003749999999911324,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.354199999705543e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.795800000716554e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0014291250000013633,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.420800000242252e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6041999990743534e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011433299999907831,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012195800000824875,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.637500001081207e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015045899999677204,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.32919999866499e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.541600001241932e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.43272420800001044,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.462500000419368e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2082999996750914e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0068238340000021935,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.0999999995960934e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8207999992323494e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.1822061249999933,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.683400000109032e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.370799999899646e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14670399999999972,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.733299999301835e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.100000000230921e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.018235333999996328,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.020799999997053e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.54590000092503e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5962897080000005,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.400000000108321e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.07920000024842e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003997919999960686,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.812500000321961e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004342500000120708,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001712834000002772,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.1124999998819476e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00028450000000646014,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004022500000075979,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.420899999502126e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.554199999200591e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001792999999992162,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.812499999218289e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.187499999375177e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012913330000117185,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6417000004007605e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.833399999564335e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010050830000096767,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.591700000526998e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.474999999752981e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009275000000030786,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8041999999904874e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001347089999939044,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011595830000032947,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.645799999205337e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00012370800000383042,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006873749999982692,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.550000000515865e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010929200000475703,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006983749999989186,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.608299999300016e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010950000000775617,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011110840000014832,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010495899999796166,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010762499999827924,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008144590000114249,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.070900001020618e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.5957999990141616e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00027799999999444935,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.0999999995960934e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2457999998978266e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015774999999962347,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.2417000003069916e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.258299999397423e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006651249999976017,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.550000000198452e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.408300000273812e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001062165999996978,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6041999990743534e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.670900000140591e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006557919999892192,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.883299999709379e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.054199999207867e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009137079999987918,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.00839999975733e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7124999991533514e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000334791000000223,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.441599999121081e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.312500000163254e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001505000000037171,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4374999998476596e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5499999995636244e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013725000000874843,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.125000000636646e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003397079999984953,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5429688749999997,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.241700000472974e-05,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.808300001002408e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006992080000003398,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.7249999994392056e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.029199999422417e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00034370800000260715,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.479199999389948e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4958000000528955e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004049590000079206,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.37080000036849e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.799999999884676e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005323750000059135,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.637500001081207e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.51250000029313e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003645000000034315,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9624999999432475e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.295800001192674e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003616250000106902,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.0542000007803836e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0207999990448116e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00036479199999917,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.979199999548655e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.491599998994843e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.7250000005428774e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2041000011417964e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4416999994846265e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003509999999948832,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.262500000289492e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3333000004631685e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00037800000001197986,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2833999995318663e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.404100000636845e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00030220799999369774,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.55000000098471e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7665999997216204e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003717090000066037,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.275000000257933e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0083000004974565e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00041416699998819695,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8957999990429926e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.379199999642424e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000298708999991959,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.458300000147574e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5499999995636244e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002700419999968062,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.233299999294559e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.054199999676712e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00027245900000139045,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9874999998801286e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.73749999972506e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007917499999905431,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.479199999707362e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.499999999689862e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006178330000068399,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.433399999153153e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003365830000063852,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010705830000006245,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.58749999978636e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.141700000876881e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003937079999900561,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.1125000009856194e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.729200000179844e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.500000000007276e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1458000009365605e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.104200000820128e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00025816700001257686,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.39999999915608e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00029274999999984175,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010262499999953434,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00021833299999229894,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004550409999950489,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00036475000000280033,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.237499999566353e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00026808299999458995,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003642920000004324,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.85839999981863e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00028783400000520487,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0024744580000088945,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.7708000010970864e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3540999999768246e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00026058400000295023,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.141699999138382e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002637919999983751,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00022670900000321126,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.579199999454886e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002378750000104901,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00034579100000087237,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.112499999564534e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002639580000050046,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 12.125540415999993,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0005233339999932696,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0018037499999934425,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00471287499999562,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0002386670000049662,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000980124999998111,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0015192500000011933,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001279590000109465,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0006965829999927564,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0015040420000076438,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012879199999815683,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00025170899999693575,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000954958999997757,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013170799999784322,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010845900000333586,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007717920000089862,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.370799999430801e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.30839999963473e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003833330000020396,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011033399999860194,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.541699999715547e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004446250000000873,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.71249999900192e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.549999999412194e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006800000000026785,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001276250000046275,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.37920000012582e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00028162499999950796,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.141600000044491e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.254200000124001e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006029169999948181,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.574999999983902e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.104100000456583e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002993749999973261,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.52919999911228e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.816699999807497e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005193329999997331,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.704200000091532e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.075000000928867e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005752910000040856,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.175000000358978e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.787500000233649e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002202919999945152,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.158299999332485e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.316599999285245e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00018770799999856536,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.337499999948704e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.704099999727987e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005437500000056161,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.054199998890454e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.574999999349075e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00018062500001292392,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.087499999158808e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.816700001228583e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012346249999950487,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.795800000247709e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.837499999789998e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011166600000933613,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.804200000625315e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.620799999268456e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.404199999745288e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.858400000136044e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000207208000006176,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00016962499999806369,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.258300000501094e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.30410000073789e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00016224999998826206,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0007580829999938032,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises",
      "outcome": "passed",
      "when": "teardown"
    }
  ],
  "schema_version": 1,
  "summary": {
    "classification_counts": {
      "candidate_test_debt": 5,
      "main_style_isolation_candidate": 0,
      "required_or_quality_gate_self_failure": 0
    },
    "collected_count": 588,
    "collection_error_count": 0,
    "failed_nodeid_count": 5,
    "outcome_counts": {
      "call:failed": 5,
      "call:passed": 583,
      "setup:passed": 588,
      "teardown:passed": 588
    }
  }
}
```
<!-- APS-FULL-PYTEST-BASELINE:END -->
