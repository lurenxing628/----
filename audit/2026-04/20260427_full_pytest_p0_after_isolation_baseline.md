# Full pytest P0 after isolation baseline

本文件记录 main-style 子进程隔离后的 full pytest 对比现场，只用于任务 3 承接，不允许导入债务台账。

- baseline_kind: `after_main_style_isolation`
- importable: `false`
- exitstatus: `1`
- collected_count: `583`
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
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
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
  "generated_at": "2026-04-27T01:45:22+08:00",
  "head_sha": "11836bd4022bfe9f4b475880e3ed240224befe92",
  "importable": false,
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
      "duration": 0.0031003749999999886,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.019821250000000012,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.466699999998273e-05,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2957999999981844e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.525771167,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.2333e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.620799999999203e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5410967500000001,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.558300000010121e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.258400000007768e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.564829042,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.366699999988846e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.862500000002434e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5194025,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.995799999977905e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9624999999942077e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04188187500000007,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.487499999982774e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.550000000020816e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04175420900000004,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010304200000010866,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.016699999993435e-05,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03146791700000007,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.00000000000145e-05,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3833999999964846e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5557373750000001,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.379200000037002e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.6916000000128975e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08869875000000027,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.787500000011605e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8499999999673804e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5695348329999996,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.958300000028174e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.941700000005156e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.035771792000000247,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.675000000029186e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.491699999986665e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04120100000000004,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.675000000029186e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.666600000025056e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04202824999999999,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.741700000034712e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.450000000000287e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08746329100000017,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.53749999997666e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7792000000157486e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09164154200000052,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.162499999997408e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.762499999966252e-05,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02755358299999955,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.337500000037522e-05,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.654199999976072e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5938245000000002,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.791699999997292e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.612499999989694e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05492587499999946,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.333300000007426e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.733299999948315e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5861203330000002,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.858300000052054e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5916000000367774e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10065833400000024,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.737499999915798e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.583299999971757e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.046722500000000444,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.225000000017246e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5916999999562336e-05,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.0789515409999995,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00019633299999988196,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010666700000072638,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04318487499999968,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.316700000017164e-05,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.549999999931998e-05,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03151866700000028,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001340000000000785,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.75839999994443e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6210014170000004,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.679099999968741e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.76250000005507e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03557475000000032,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.620899999949415e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.60840000000573e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5574390000000005,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.991600000030076e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.737500000029371e-05,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02243133299999922,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001055839999999364,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.333300000032182e-05,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08371599999999901,
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
      "duration": 4.71669999999591e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05342341600000111,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.533399999954838e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7750000000235104e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04220008300000089,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.420799999951043e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.370899999983635e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04031208299999989,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.970799999907797e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.791599999975915e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04186966700000028,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.204199999932825e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1167000000518215e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03987249999999953,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.870900000028769e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.570900000011591e-05,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04026195800000032,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.695899999975552e-05,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.441699999979676e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10110245899999981,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.374999999854026e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8542000000040275e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10018879100000078,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.716699999882337e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6916999998813935e-05,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0425244590000009,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.670800000132317e-05,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.90420000008163e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.053742792000001316,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.458400000004417e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5874999999639954e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.585010917,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.487500000027183e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.937499999968509e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12101604200000082,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.6458000000178e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3707999999375033e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.030065500000000966,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.608299999896985e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.024999999925228e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.8843629170000007,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.7041000000454e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.791699999984189e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09503320800000026,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.979099999959715e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.475000000070395e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14482591600000028,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.829099999945299e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.391699999928278e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03690308299999856,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.141699999912987e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.383400000129711e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6013502909999993,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.333299999956466e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.737499999940553e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6253674169999996,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.904100000035498e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.587500000141631e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01889145899999889,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.320900000034158e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.262499999896363e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.025416749999999766,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.683299999998837e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.4833000000087395e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.042194916999999776,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.241700000015783e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.483300000046597e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.032459459000000024,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.570900000113511e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3791999999598374e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.18281162500000114,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.229100000039068e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7542000000788676e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.18229616600000043,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.024999999989291e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.624999999869317e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1897847499999994,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.51669999999416e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8333000000511106e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09878554099999981,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.566599999897505e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5332999999203594e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08847691699999949,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.929200000158289e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.649999999983834e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08922550000000129,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.016700000050946e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6333999998537934e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04344808400000133,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.16660000001923e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.312499999947761e-05,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07907383299999893,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.225000000017246e-05,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.783299999999713e-05,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.022577249999999438,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.808299999924941e-05,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3584000000151946e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5895774160000009,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.154200000021206e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7708999998619106e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5454120830000004,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.195799999948349e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.516699999967955e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14044104200000085,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.037499999919874e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.175000000041564e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5681874999999987,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00020654199999903256,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.891599999965138e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04516820899999985,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.187500000111925e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.483300000046597e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5548704170000001,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.729199999990556e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.958300000090787e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04065933299999891,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.295900000021561e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7750000000235104e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04231695800000068,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.599999999996498e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8999999998855515e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04105658300000137,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.070900000094582e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.208300000030363e-05,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.027921333000000104,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.708300000113354e-05,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.65839999996831e-05,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04584120800000058,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.141700000090623e-05,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.504199999999514e-05,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5546695840000009,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.445800000027702e-05,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.541699999904836e-05,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05130620799999974,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.049999999926172e-05,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.541699999904836e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06008812500000005,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.829199999813795e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.412500000228192e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05147737500000105,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.412499999759348e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.625000000046953e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04758762500000202,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.783299999923997e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6458999999998696e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05773699999999948,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.54580000009264e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.91249999999377e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04053833400000073,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.929200000271862e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4625000001019544e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.040951499999998475,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.204199999932825e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.304199999793923e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04062066699999889,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.508299999869905e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.58749999978636e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05035554200000192,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.86250000008215e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.429200000188871e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.054774500000000614,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.950000000178647e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.82090000026858e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05203112500000273,
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
      "duration": 4.5333999999286334e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03503083300000043,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.754099999994878e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.720799999802239e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03142049999999941,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.733300000012377e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.520899999960193e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0559958339999973,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.279200000023025e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.529099999928121e-05,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03329208400000283,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.058399999948506e-05,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6000000001100716e-05,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.031415833000000504,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.03339999993591e-05,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.524999999944157e-05,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14132070799999852,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.875000000012733e-05,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.629200000001333e-05,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.027874125000000305,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.358399999901621e-05,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.433300000172835e-05,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04485558400000045,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011558299999947508,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.03340000008734e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06164216599999861,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.754199999965294e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.616599999707205e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5954482910000003,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.624999999895522e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.76250000005507e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.570718166999999,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.558300000098939e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5832999997941215e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04115175000000093,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.666699999868797e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.374999999967599e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.045263957999999604,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.600000000034356e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.558300000212512e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04764191699999998,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013237499999974034,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.162500000314822e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04413650000000047,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.920899999864673e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5959000001261074e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04518124999999884,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.462499999988381e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.658299999960036e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07379229100000018,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.733400000020652e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.649999999983834e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04867825000000181,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.508400000195593e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.204100000000267e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.040507583000000125,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.533400000170332e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5250000002994284e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02002329100000111,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.45000000001994e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.658299999960036e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08660849999999698,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.929199999878733e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6792000002682244e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08713383399999941,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.86250000008215e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.912500000031628e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0910445409999987,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012995900000234428,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.583300000111535e-05,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6011920840000009,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.370799999861788e-05,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.483300000046597e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05875858399999956,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.604100000335734e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4875000000388354e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06205479200000141,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010862499999930719,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.674999999920715e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03707929099999774,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.908400000251504e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.329100000077801e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.037837208999999206,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.570800000067379e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.687499999889155e-05,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04160404099999937,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.454200000050037e-05,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.437500000165073e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5936646250000024,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.604199999950879e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.608300000086274e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.617281166999998,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.195899999918765e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8040999999443557e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5862598329999997,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012120900000311963,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2624999998585054e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5986881249999989,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.333299999880751e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.679099999904679e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5907188750000003,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.733300000012377e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9083000000393895e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5214680839999986,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.320799999950168e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.745800000094391e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5259754580000013,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.708300000075496e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.341600000046242e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09163250000000289,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.174999999965848e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.22499999983961e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5629674579999993,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.370800000217059e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.487499999683564e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5626029169999995,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.975000000115529e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.737500000118189e-05,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6066624589999989,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001431249999974682,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.50420000027907e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08852420900000268,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.429200000075298e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.587500000141631e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09060408399999886,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.579200000051856e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.795799999968153e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09179624999999803,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.587500000028058e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9332999999762706e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08803612500000213,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.387499999784609e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6082999997310026e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08633883299999923,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.029199999981529e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.816599999912796e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.043777250000001544,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.612499999964939e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0792000003241355e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.513874458,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.112500000085788e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.300000000119098e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.5790261249999986,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001604170000000238,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00023470799999714131,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.4199269589999979,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.316600000275344e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.808399999944868e-05,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5237070829999979,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010954200000057313,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.975000000115529e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04117670800000184,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.987500000083969e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7292000001419865e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06679829200000142,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.95830000015485e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.500000000007276e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03662683299999969,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.324999999980264e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.374999999967599e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05568545899999933,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.06670000027998e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.516700000323226e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05636391700000232,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.47919999994906e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.508299999983478e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04342904199999964,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.854100000097674e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6040999997387644e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.058982415999999205,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.550000000047021e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.083299999952828e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.057320874999998495,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.766599999963319e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.608300000086274e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06607045799999867,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.154100000050789e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.766700000047308e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06889325000000213,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.908400000289362e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.97920000022134e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06200679200000181,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.804200000232186e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.695899999873632e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06351733300000006,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.758299999987116e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.34580000003848e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06237575000000106,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.966700000139326e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5292000002916666e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06437729199999964,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.958299999837436e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.341700000054516e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0499137499999982,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.950000000533919e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.687500000244427e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04713495800000089,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.150000000028967e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.483299999691326e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.048784417000000246,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.89589999996565e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.712500000181308e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04770854199999519,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.662499999838701e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.737500000118189e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.18903087499999316,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.249999999776492e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9332999999762706e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0451647080000015,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.62499999993338e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3500000003859896e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.579564665999996,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.154099999695518e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.8708000004514815e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05619087499999864,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.558399999714084e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.654199999976072e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07812520899999953,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010512500000459113,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3167000004350484e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5840376250000006,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.995800000060171e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9083000000393895e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5994680000000017,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.275000000030786e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0292000004503734e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04293979199999853,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.287500000074942e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.524999999944157e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06840516599999802,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.912500000311184e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3874999995807684e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14802079199999696,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.595800000359532e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7541000000705935e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5675880410000005,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.833300000077315e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.158300000118743e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05149408300000147,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.587499999952342e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.791599999975915e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5718284579999988,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.333299999918609e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.616599999707205e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04164279100000101,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.183299999979909e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8500000005446964e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.042003207999997016,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.624999999615966e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.44590000014955e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04191329200000382,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.129200000046467e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.154199999424236e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04203233399999817,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.887499999981173e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6125000004337835e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04050979200000171,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.483299999933024e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.591599999770324e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04031987500000156,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.379099999444861e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.262500000213777e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04301941599999992,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.491599999871369e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9791999998660685e-05,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04181583299999403,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.858300000089912e-05,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3542000000229564e-05,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0739614999999958,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.441700000361152e-05,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.387499999898182e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.042089416999999685,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.312500000011823e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7708000003865436e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.041135167000000195,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.187500000251703e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.8917000004043985e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02681383299999851,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.075000000611453e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.258399999912399e-05,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03971762499999443,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.816699999807497e-05,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.520799999914061e-05,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.778924875000001,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013024999999800002,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.308299999664314e-05,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.748383625000002,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016450000000389764,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.404200000138417e-05,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1009360840000042,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.687500000092996e-05,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.920899999660833e-05,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.029543666000002133,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011304200000239462,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.93750000032378e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04753287499999459,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.679200000154651e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.120800000213421e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.0143299170000049,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.816699999490083e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.629200000039191e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5659230420000014,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.441599999680193e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7041000001968314e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.552245083999999,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.195799999948349e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.870800000134068e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0767208330000031,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011079200000096989,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.754199999723596e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.043354958000001886,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.087499999869351e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2082999996750914e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.028617625000002533,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.437499999696229e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.895800000070949e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5257887500000038,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010562500000332875,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.133300000106146e-05,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5406504170000019,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.850000000075852e-05,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1124999998819476e-05,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04720766699999501,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.445900000391248e-05,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.366699999991397e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.020166958000004342,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.379100000548533e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.416699999865159e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2186626669999967,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.679200000154651e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9500000002922206e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09704329099999853,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.945799999475867e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4209000002126686e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08600641700000011,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.579100000043582e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.766699999692037e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2087426249999993,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.237499999808051e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.629200000039191e-05,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01956149999999468,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.595800000359532e-05,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.683299999896917e-05,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.45959245800000303,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00023737499999754164,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00016150000000436648,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04086391699999581,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.012499999982992e-05,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.99160000049892e-05,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07361591599999429,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.541699999715547e-05,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.22500000023274e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00294654200000366,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.708299999833798e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.845799999879773e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002524590000021476,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5249999996267434e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.100000000472619e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006390830000029268,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.591700000526998e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010070900000158645,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00016783400000264237,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.337499999707006e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.283300000513691e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014633299999644578,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.729099999816299e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.22920000018712e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006646670000023391,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.2458999999439584e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0016528749999977776,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7189544579999989,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.816599999761365e-05,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00029483299999810697,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6957107500000035,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.062500000567297e-05,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4666000000859185e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.008540625000001967,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.308300000450572e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.074999999659212e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.013975458000004437,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.4541999997704806e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9207999996904164e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004115167000001918,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.391699999928278e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.958300000306281e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003427910000013412,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.370900000021493e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.766700000085166e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.015536875000002226,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.470800000040299e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.112499999564534e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0128728339999995,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.720799999802239e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.02920000013296e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.023010499999998046,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.51250000029313e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.191699999722687e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.22180916700000353,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.316699999724506e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.258300000259396e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.22468866700000234,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.270799999834708e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2499999999279225e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14907029200000466,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.3499999999928605e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2499999999279225e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6077699159999952,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.020799999679639e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.233300000639929e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03539125000000354,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.5332999998825017e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.279200000212313e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3103143339999974,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.262499999820648e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.666700000655055e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 2.2806032080000023,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.404200000214132e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3291000004330726e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.015484417000003248,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.437499999771944e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.341700000054516e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.015731916000000012,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0792000003241355e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.004200000196079e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.021900625000000673,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.287500000150658e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.179200000464789e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.37868208300000106,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.3167000004350484e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.150000000180398e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.36958954199999994,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.9667000002150417e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5124999999757165e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0029682090000022754,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.2249999999910415e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00031937500000367436,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2698777919999955,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.150000000028967e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004558750000001055,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2883267500000031,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.691600000394374e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002708750000053328,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27386970799999943,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.724999999998317e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003102080000019214,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.275991458,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.754199999965294e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002896250000006262,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26254366700000276,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.508300000187319e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5707999994704096e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002347499999970637,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.554199999911134e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.720800000195368e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00022570800000210056,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.004200000196079e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.037499999753891e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.820800000260306e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.170800000162899e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4499999998161e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.6708000006390193e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.058299999736391e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3375000001001354e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.808399999944868e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3625000000370164e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.508300000021336e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.6625000003075456e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0416999997839866e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3375000001001354e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00027845900000045276,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.395800000305371e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.583299999831979e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.31670000004192e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.341699999737102e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002687080000001174,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.269218292000005,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010295899999590574,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003679999999945949,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29144066599999974,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.920800000249528e-05,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002834589999949344,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002273875000000203,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.358399999977337e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.02499999978545e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.962500000260661e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2209000004002064e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.562499999532065e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.954200000170886e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.400000000652881e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.554100000258131e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.866599999469145e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.104199999626189e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000229249999996739,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0026089999999996394,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.675000000275986e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.883299999785095e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.270800000076406e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.287500000226373e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00022574999999847023,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2314215829999995,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.120900000108122e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002625000000051614,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002603332999996155,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0542000003872545e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002545839999967825,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2754280830000013,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.295900000376832e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002891659999946228,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.24511804200000142,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.12910000007605e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00030854199999907905,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26977112500000544,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.81250000017053e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002877499999982547,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28175925000000035,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.916700000189849e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002938329999935263,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2312536250000008,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.21249999987117e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00030091699999701405,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.23262041599999606,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.458299999996143e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.158300000511872e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0031442920000017693,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.74579999973912e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.20420000040167e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14402158299999712,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.758299999873543e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.545800000561485e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007030419999978221,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.0417000001014e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.845799999879773e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002723329999980706,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4875000004319645e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.441699999968023e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00029316700000237006,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.991699999834509e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032908299999689916,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.17471487499999938,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012341700000462197,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004612500000007458,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1696036250000006,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013962500000275213,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004939170000000104,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.135445500000003,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012066600000082417,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035241699999488674,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1718253750000045,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015129200000529863,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.912500000386899e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.537500000547425e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.408300000273812e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.558299999895098e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.295799999771589e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2874999995158305e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9457999996272974e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000133040999998002,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.45420000016361e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.525000000337286e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003355409999983294,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2582999999419826e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3166000001472185e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.1540999997712333e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.187499999768306e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.587499999468946e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.0500000003571586e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9875000002732577e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.266699999926459e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.416699999865159e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.170800000162899e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.18329999973821e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.654199999582943e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0375000001470198e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.037500000313003e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.345800000673307e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9833999998961644e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.145799999832889e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.441699999968023e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.129200000273613e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4166999995477454e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.687500000244427e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0500000001154604e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7208999998483705e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.18750000008572e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0250000001785793e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.57919999937917e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.320800000101599e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8583000005587564e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.033299999723795e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.558300000212512e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4708000001160144e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.091599999929031e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.5624999998494786e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.362499999326474e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3375000001001354e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.049999999646616e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.962499999625834e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.1915999997522704e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.458400000435404e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.8792000001942597e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.320800000101599e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.8458999998501895e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.529199999974253e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5167000000058124e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001415420000014933,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.245899999626545e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.554100000424114e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.287499999833244e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1958999997527826e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6832999995795035e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012674999999973124,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2083000000682205e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.262500000289492e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0074797500000016726,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.175000000041564e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.533299999565088e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.017355332999997586,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.674999999882857e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5999999997548e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004357080000048086,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.058300000053805e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.641600000037215e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00016791699999885168,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.408300000273812e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.683399999943049e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.300000000436512e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2624999995789494e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.475000000463524e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.6290999996756454e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0207999998310697e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.375000000005457e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.091599999929031e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0999999999892225e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.575000000211048e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.074999999583497e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.079200000399851e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.320799999784185e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.9582999999131516e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9374999996889528e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.345800000431609e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.216600000006565e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.950000000367936e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.558299999895098e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.820799999474048e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.058299999736391e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.19580000009978e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.0916999999751624e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9957999998941887e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.37080000036849e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.90839999993409e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.070900000068377e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5125000003688456e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002649580000024798,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.366699999673983e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.333299999752626e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015629199999978027,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.37080000036849e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6041000001318935e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.254200000199717e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.104200000336732e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.520900000353322e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.825000000214686e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0999999999892225e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4834000004480004e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011258299999639121,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.354199999705543e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3583000004000496e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.929100000339304e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.929200000068022e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4625000004950834e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.0665999999921496e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9458000000204265e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.383300000336931e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013441699999816592,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.316699999800221e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.275000000257933e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.0707999996291164e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.095800000352256e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.337499999707006e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.470800000281997e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.13339999991058e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.27499999954739e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00017154199999680486,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.245799999973542e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2292000000211374e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010295799999937572,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.087500000020782e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.216699999901266e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00018233400000156053,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.925000000037926e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.004100000149947e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001507499999959805,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6541000000056556e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5249999996267434e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.8040999999443557e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9167000000995813e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9374999996132374e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.229100000292419e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9666999999733434e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.604100000056178e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002394159999994372,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.154199999817365e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.000000000165983e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001685419999972737,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9792000002591976e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003167500000031964,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29628179200000204,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.987500000046111e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003129170000022441,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2833351249999936,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.733399999982794e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003743339999999762,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2819796249999982,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.312499999618694e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035737500000010414,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27473404200000573,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012016699999861657,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003993330000042761,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3010872500000019,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.03339999993591e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035466699999631146,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26394229200000296,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001068750000001728,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035029200000025185,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28709154100000234,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.945900000156826e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003118330000049241,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27072333399999593,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.295800000013287e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003388750000041796,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26305795900000106,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.924999999886495e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00029970899999653966,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2760532499999968,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.699999999350894e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00017183299999601331,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001175207999992267,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.1708000000871834e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003250420000000531,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2697997089999973,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.450000001085755e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002866669999974647,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27129783399999496,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.687500000803539e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00042720800000495274,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28738400000000297,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.558400000424626e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00038187500000219643,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29210741600000745,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.299999999257125e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9707999991710494e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000156375000003095,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.875000000164164e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.01249999981701e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.774999999947795e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.841699999895809e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9249999986168405e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001556458999999677,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.70839999987993e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.816699999958928e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.21660000127622e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.687500000637556e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.841600000953349e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001269159999992553,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9416000007008734e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.837500000258842e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.154100000330345e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.541700000653236e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7208999998483705e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002568750000051523,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7082999995163846e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.741700000148285e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.199999999978445e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.129200000591027e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1084000002911125e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.916700000658693e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.70830000093747e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.78750000038508e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.212499999946886e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4166999995477454e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.679200000306082e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021887499998740623,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9624999999432475e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4333000005281065e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012567089999890868,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8250000002904017e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.933299999900555e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012198750000038672,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.77920000037102e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4625000001019544e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0020543339999932186,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.975000000229102e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.425000000196633e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0014305410000048369,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.58749999978636e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2082999996750914e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010533749999979136,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.025000001206536e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3124999990595825e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010828340000017533,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.862499998774638e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00015125000000182354,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012528329999952348,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.054099999947994e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011220800000444342,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009929170000049226,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.558299999426254e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011220899999386802,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001002332999988198,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.445799999710289e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010925000000838736,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0017689590000031785,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.766599999252776e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011287499999923511,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011840829999982816,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.354200000657784e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.933400000732945e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010917919999968717,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.729099999816299e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.762500000296768e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.046491958000004274,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010179099999163554,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011216699999749835,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003742090000002918,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.925000000672753e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.183300000055624e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.758400000071106e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.383300000336931e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.808299999263909e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.158299999801329e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.312500000163254e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7500000004797585e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.8541000009217896e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.395799998884286e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.054199999359298e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.366600001048937e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4124999999107786e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7500000004797585e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.079199999296179e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.341699999737102e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.887500000132604e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011690830000077312,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.716700000211404e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.129199999169941e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00125945800000693,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.745899999633821e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6042000008128525e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00127558299999464,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.349999998964904e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.387499998870226e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010734579999933658,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8291999999273685e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.100000001017179e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001056791999999973,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7915999996585015e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.191600000069684e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010645830000015621,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.737500000511318e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.587499999317515e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.25972091600000624,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.624999999222837e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.11670000094e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.250000000804448e-05,
      "longrepr": "tests/test_operator_machine_exception_paths.py:45: in test_normalize_skill_level_optional_only_converts_value_error\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/Users/lurenxing/Documents/GitHub/----/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00011941599998976926,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.949999998871135e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.98750000083237e-05,
      "longrepr": "tests/test_operator_machine_exception_paths.py:54: in test_normalize_skill_level_stored_only_falls_back_for_value_error\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/Users/lurenxing/Documents/GitHub/----/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.0001029170000066415,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.58749999978636e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011066670000019485,
      "longrepr": "tests/test_operator_machine_exception_paths.py:72: in test_list_by_operator_propagates_unexpected_readside_normalization_errors\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/Users/lurenxing/Documents/GitHub/----/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 8.991699999683078e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.266599999880327e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001453249999997297,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.1917000004332294e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.083299999990686e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009652080000108754,
      "longrepr": "tests/test_operator_machine_exception_paths.py:128: in test_resolve_write_values_only_converts_validation_error\n    assert new_skill is None\nE   AssertionError: assert 'normal' is None",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 4.383299999233259e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.649999999311149e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002125839999962409,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.658300001063708e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.654200000369201e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011791600000776725,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1167000003051726e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.370799998947405e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.0957999999591266e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.012499999499596e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.316599999436676e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.779199999902175e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.341600000794642e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.270800000620966e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.854099999500704e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0041999991681223e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4499999998161e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00048604100000204653,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3874999999738975e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.416700000968831e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00019324999999525971,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4540999990895216e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.375000000005457e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021608299999797964,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2541999999580185e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.350000000068576e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014050000000054297,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.195899999918765e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4374999998476596e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00016324999999994816,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.404199999579305e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.262500000289492e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.66250000023183e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.825000000607815e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.062499999221927e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00036724999999648844,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.2167000003701105e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.329200000403489e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.483399999192898e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.979199999548655e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.970899999534595e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011129099999607206,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8041999999904874e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8458000009077296e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.366599999159007e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6832999995795035e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.804200000307901e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.337499999313877e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6958000009690295e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.766600000039034e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012179099999798382,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7374999990902324e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.708299999833798e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.179199999995944e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.666599999974096e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4708000001160144e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.795800000247709e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1750000005104084e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9083000004325186e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011095899999702397,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.245799999262999e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.499999999689862e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00102275000000418,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.325000000131695e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.970800000592135e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013539999999920838,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.595799999966403e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.291700000346736e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006557079999964799,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.7375000008287316e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.525000000261571e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001403330000044889,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9333999993118596e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0083000004974565e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011854199999561388,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9083999993749785e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.975000000229102e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011908300000129657,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.929199999674893e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.041700001129357e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011558300001013322,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.82499999918673e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.504100000384369e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001250410000039892,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.166700000178935e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.233299999294559e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002093330000008109,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.375000000005457e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.25829999923144e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012641700000415312,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.112500000668206e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.329099999405116e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003466659999986632,
      "longrepr": "tests/test_query_services.py:163: in test_operator_machine_query_service_lists_with_names_and_linkage_rows\n    assert simple == [\nE   assert [{'dirty_fiel...': 'M2', ...}] == [{'is_primary...: 'beginner'}]\nE     \nE     At index 0 diff: {'operator_id': 'O1', 'machine_id': 'M1', 'skill_level': 'expert', 'is_primary': 'yes', 'dirty_fields': ['skill_level'], 'dirty_reasons': {'skill_level': \"历史技能等级 'high' 已兼容归一为 expert。\"}} != {'operator_id': 'O1', 'machine_id': 'M1', 'skill_level': 'expert', 'is_primary': 'yes'}\nE     Use -v to get more diff",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 4.1334000002279936e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5084000003848814e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00017250000000501586,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.454100000510607e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002808340000086673,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11341912499999296,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010316700000601031,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00036787499999491047,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.9935557499999987,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001180409999932408,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00041450000000509135,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14614795800000024,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016850000000090404,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.712499999788179e-05,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.34042050000000756,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.0499999995709e-05,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.729199999393586e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.074999999825195e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.799999998932435e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.962500001364333e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007512499999933198,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.075000001080298e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003621670000057975,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005608750000050122,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.220900000324491e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00023283299999832252,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000743874999997729,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.099999999913507e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002360839999937525,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.25780420799999604,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010833400000365145,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000416708000003041,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.25950895799999785,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011941700000761557,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040683299999955125,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2575439999999958,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010333299999842893,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037308300001370753,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.25900975000000415,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012562499999546617,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003628749999933234,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.016321208000007914,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012204200000098808,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.854099999818118e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.891700000252968e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4124999999107786e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.862500000195723e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.550000000198452e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.287500000226373e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00036370799999474457,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2866583750000018,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015191699999661523,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00042316699999389584,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14752329200000247,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010608299999148585,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004631250000102227,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29873054099999763,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013233299999626524,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004472499999934598,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29897966699999756,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010362499999416741,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040749999999434294,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5808452079999995,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001155419999889773,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039520800000047984,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2599527500000107,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010750000001280569,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004389169999967635,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2559664589999926,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.000129624999999578,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004504999999994652,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2611628330000002,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001030409999884796,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4875000000388354e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006273750000076461,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.450000000133514e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.004199999651519e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006277499999924885,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.870799999423525e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011658299999339761,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002819170000094573,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.4750000003878085e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002907909999976255,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03866454200000646,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001125000000001819,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.437500000165073e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011502079999985426,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.066700000748824e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.091599998901074e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005970419999954402,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.470800000433428e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034120800000891904,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11804999999999666,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015650000000277942,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010874999999543888,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005832080000089945,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.67919999920241e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.908400000009806e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00042654199999958564,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.8167000002763416e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003071250000061809,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004611500000009983,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.058300000688632e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.887500000132604e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.22797850000000608,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.391699998673175e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000472500000000764,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.023976540999996132,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012699999999199463,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034358399999234734,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.022506667000001812,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013579199999469438,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003535419999991518,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.018378832999999872,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013112499999579086,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003361249999898064,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.019312999999996805,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014316699999028515,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003895840000041062,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.019661041999995632,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010500000000490672,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5209000006707356e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004875409999982594,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.049999999722331e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00031375000000366526,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.018097541000003048,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010704199999622688,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034504100000276594,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.021345832999998038,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.979200000032051e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.608399999028734e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010241599999005757,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.399999999942338e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7874999989639946e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.062499999539341e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.237500000352611e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.462499999784541e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.308400000103575e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1167000003051726e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.566700000590117e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00027116700000817673,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5625000009531504e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.658300001063708e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013270800000952931,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2791999998948995e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.429199999516186e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001548749999926713,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.416700000968831e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.399999999942338e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011958300000003419,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.395799998884286e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.416700000968831e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012370800000383042,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.21250000041573e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3083000005262875e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001207499999935635,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2583000006525253e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.308400000889833e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00028095800000471627,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5207999999897766e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.591700000526998e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.9000000004184585e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.020900000194615e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.441700000905712e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011866699999529828,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.179200000147375e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.258399999594985e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013016600000526068,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.399999999942338e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.520900000353322e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.904200000690253e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.083400000036818e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3583000004000496e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.933399999795256e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3291999997686617e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00033558300000890995,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3934924170000045,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.016699999619959e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000382542000011199,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.43268583299999364,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.983299998988059e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003792079999982434,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4092842919999953,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.275000000423915e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035679199999094635,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.46006024999999795,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.612499999889224e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003904160000018919,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4105725000000007,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.095799999807696e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032674999999926513,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3869176250000095,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.816600000865037e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039495800000111103,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.40870366599999386,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.583299999997962e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003552919999947335,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3713594580000006,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.541700000819219e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.695800001286443e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.408299999018709e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.741700000148285e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1917000004332294e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.045899999662652e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.583399998774439e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0028764999999992824,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001652957999993987,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.770799999841984e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2082999996750914e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.470800000433428e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.662500000700675e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9416000007008734e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.341600000325798e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.454199999453067e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.833399999564335e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.954200000246601e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.433300000210693e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.916599999342907e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.533299999171959e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3625000000370164e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.695799999396513e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00838779199999351,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.674999998779185e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.516599998780293e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00786266600000829,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.299999999725969e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.875000000012733e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.007883500000005483,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.870900000421898e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.441700000754281e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.007590124999993009,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.191699999646971e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.762499999979354e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.009114541999991843,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.575000000452746e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5665999991229e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021133399999939684,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.816699999958928e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.033300000116924e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.570899998971981e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.504199999326829e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.308399999786161e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001864580000017213,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.600000000858472e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7708999997221326e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.237500000836008e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4374999998476596e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.758399999753692e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001430829999975458,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5875000008900315e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.887499998711519e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011412499999607917,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5208999989322365e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7332999994532656e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.97090000080425e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.487500001142507e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035833399999773974,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5238231669999891,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.641700000566743e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6749999995654434e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007846670000049016,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.3750000003228706e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.116699999201501e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003312500000021146,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.754200000116725e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1125000009856194e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.779200001005847e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2583000006525253e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.620800001158386e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.412499999441934e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.316600000857761e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.408300000273812e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.599999998968542e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.770799999358587e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.662499999279589e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004527919999901542,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.483300000084455e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.62920000043232e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011291250000056152,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.558399998837558e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.616699999042794e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.216599999855134e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2957999991367615e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.650000000732234e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012737499999104784,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.249999998899966e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.379200001063509e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.432352999999992,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.375000000640284e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.133299999864448e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003400042000009762,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.262500000606906e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.824999998869316e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.1924617499999925,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.362499998781914e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.654199999900356e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.15137850000000697,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.825000000138971e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1416000005133355e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.018249208000000294,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.916699999872435e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.32079999970847e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6156578750000108,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.71250000074042e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.412500000545606e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003293330000104788,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9667000010013e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005073749999979782,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0017481250000059845,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0083000004974565e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002803750000026639,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00039566700000648325,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.420900000923211e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.541700000653236e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0017898750000000518,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.09160000032216e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.841699999895809e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013308329999972557,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.474999999752981e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5334000003217625e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00101508299999864,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6791999988849966e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5499999995636244e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0017763749999915035,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.35420000034037e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00015237499999898318,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012136670000018057,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.791699999553202e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00013687499999548436,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007399999999933016,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.583299999363135e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011433400000271376,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007254580000051192,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.249999999852207e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010933299999749124,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006118749999899364,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.133300000499275e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.808299999112478e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006741250000033006,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.387500000608725e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.35420000034037e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002702909999925396,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.979199999548655e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.045800000402778e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014799999999581814,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.895800000464078e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.133400000076563e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000632625000008602,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.387500000608725e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7124999991533514e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009701669999913065,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.487499999721422e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.825000000138971e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000766082999987816,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.133399999759149e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.391699998673175e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010197919999939131,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.679199999837238e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.18329999973821e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00030474999999796637,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.529200000684796e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4708000001160144e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014629199999660614,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.237500000352611e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2833000005894064e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012987500001315766,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6332999997057414e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000337916000006544,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5651741249999986,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.954199999777757e-05,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.887500000450018e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006225000000057435,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.3000000005122274e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1749999994067366e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00035874999998952717,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.958400000669826e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.887500000132604e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004315829999939069,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.808299999263909e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.112500001151602e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000567166999999813,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.695799999865358e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.008299999393785e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00040250000000696673,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.495800000370309e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.5875000001037733e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004991250000045966,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001912919999966789,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00024412499999471038,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007389169999925116,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.8541000001355314e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1291000002274814e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.3250000004491085e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.462499999784541e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.008400000543588e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005865840000041089,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.500000000007276e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.112499999564534e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004977499999938573,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.029199999422417e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8041999999904874e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003697090000116532,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6832999995795035e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8291999999273685e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00042287499999815736,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.645799999674182e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.720900000800611e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004933749999906922,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.6042000008128525e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.720799999484825e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003327919999946971,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6167000004638794e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.587499999468946e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002934999999979482,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.037500001174976e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.7834000003254005e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003083749999888141,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5374999999125976e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.541699999866978e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000894041000009338,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.50830000033875e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7208999998483705e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006712079999999787,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7374999990902324e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003663749999986976,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013019169999921587,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.070800000657073e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.524999999157899e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005039999999922884,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.104100000608014e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.179200000464789e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.733399998713139e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.383299998915845e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010591699999906723,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002845420000028298,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.15419999974165e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00030533300000001873,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003500419999937776,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.941699999960747e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032491599999673326,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00027054199999554385,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.8624999990920514e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002762499999988677,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00031791700000383116,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.2334000002929315e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002714999999966494,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0028025409999941076,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.537500000547425e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.774999999947795e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003416670000007116,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.4875000000388354e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000315666999995301,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002465840000098751,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.1792000007822026e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002576250000032587,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003684579999969628,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.441599999438495e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002763749999985521,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 12.176627291999992,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00040087500001106946,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0028700000000014825,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0031310840000031703,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0002039170000074364,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0010266249999943966,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0029645829999935813,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.000208291000006966,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.001026791000001026,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002658750000009036,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016154100001131155,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001713329999972757,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000939083999995205,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013516699999627235,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010008300000663439,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00039400000000000546,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.5875000007386e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.029200001009485e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006775000000089904,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012033299999814062,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010658400000806978,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00048375000000078217,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.099999999762076e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.12920000075701e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00027837499999350257,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.183300000690451e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.783300000596682e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00020779100000822837,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.954100000517883e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.587499999317515e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00024491700000339733,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.929199999206048e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.574999999349075e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002479999999991378,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.995799999742758e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.454099998938091e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00028566699999998946,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.445899998970162e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.358299999144947e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003834590000053595,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.037500000706132e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.66670000018621e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00022179100000130347,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.974999999442844e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.27079999904845e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00018450000000314049,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.750000000328328e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.362499999885586e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006130830000046217,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.029200000374658e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.566700000438686e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00017983400000787242,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.12499999906413e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.999999999697138e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009596669999893948,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.945799999868996e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.59589999969512e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011658300000760846,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.487499999252577e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.420799999773408e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.5333000001242e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.7499999996935e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.441700000436867e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001315409999875783,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.258300000183681e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.545800000878899e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001435839999999189,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0005281659999951671,
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
    "collected_count": 583,
    "collection_error_count": 0,
    "failed_nodeid_count": 5,
    "outcome_counts": {
      "call:failed": 5,
      "call:passed": 578,
      "setup:passed": 583,
      "teardown:passed": 583
    }
  }
}
```
<!-- APS-FULL-PYTEST-BASELINE:END -->
