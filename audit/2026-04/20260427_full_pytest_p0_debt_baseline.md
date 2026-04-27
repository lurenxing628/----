# Full pytest P0 current debt proof baseline

本文件记录当前 full pytest 债务证明；当前没有未登记 full pytest 失败，不作为任务 5 的导入种子。

- baseline_kind: `after_main_style_isolation`
- importable: `true`
- exitstatus: `0`
- collected_count: `631`
- failed_nodeid_count: `0`

<!-- APS-FULL-PYTEST-BASELINE:BEGIN -->
```json
{
  "baseline_kind": "after_main_style_isolation",
  "classifications": {
    "candidate_test_debt": [],
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
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_zero_candidate_importable_baseline_is_current_proof",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_after_isolation_and_output_file",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_clean_worktree",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_blocked_classifications",
    "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_bad_pytest_invocation",
    "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_requires_nodeid_owner_root_and_exit_condition",
    "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_rejects_duplicates_and_negative_ratchet",
    "tests/test_full_test_debt_registry_contract.py::test_sort_ledger_preserves_test_debt_and_active_xfail_reads_ledger",
    "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_marks_registered_exact_nodeids_xfail",
    "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_keeps_unregistered_failures_failed",
    "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_does_not_require_uncollected_registered_nodeids",
    "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_strict_xpass_fails_when_registered_debt_is_fixed",
    "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_propagates_debt_registry_failures",
    "tests/test_full_test_debt_registry_contract.py::test_save_ledger_writes_test_debt_snapshot_and_machine_block",
    "tests/test_full_test_debt_registry_contract.py::test_finalize_ledger_update_preserves_test_debt_and_stable_updated_at",
    "tests/test_full_test_debt_registry_contract.py::test_refresh_auto_fields_preserves_test_debt",
    "tests/test_full_test_debt_registry_contract.py::test_ordinary_sort_and_save_reject_missing_test_debt",
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
    "tests/test_run_quality_gate.py::test_shared_quality_registry_does_not_split_quality_gate_error_identity",
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
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_imports_seed_entries",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update0-schema_version]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update1-schema_version]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update2-baseline_kind]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update3-importable]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update4-importable]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update5-importable]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update6-pytest_exitstatus]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-schema_version]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-classifications]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt0]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt1]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-failed_nodeid_count]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collected_nodeids]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collection_errors]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-reports]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-worktree_clean_before]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_blocked_classifications",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-required_or_quality_gate_self_failure]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-main_style_isolation_candidate]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-collection_error_count]",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_unknown_candidate_nodeid",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_empty_candidate_nodeid",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_current_dry_run_candidate_drift",
    "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_does_not_overwrite_existing_test_debt",
    "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[owner--owner]",
    "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[style-untriaged-untriaged]",
    "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_duplicate_debt_id",
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
  "collector_argv": [
    "--baseline-kind",
    "after_main_style_isolation",
    "--importable-debt-baseline",
    "--write-baseline",
    "audit/2026-04/20260427_full_pytest_p0_debt_baseline.md",
    "--",
    "tests",
    "-q",
    "--tb=short",
    "-ra",
    "-p",
    "no:cacheprovider"
  ],
  "exitstatus": 0,
  "generated_at": "2026-04-27T14:21:22+08:00",
  "git_status_short_after_write": [
    " M audit/2026-04/20260427_full_pytest_p0_debt_baseline.md"
  ],
  "git_status_short_before": [],
  "head_sha": "a40175738f93c2b713ce7f0dd05847eab1883a6b",
  "importable": true,
  "importable_blockers": [],
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
      "duration": 0.0002099160000000877,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02149687499999997,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.137500000005016e-05,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.587499999997302e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6632340840000001,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013129099999997784,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.712499999988019e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6580179589999999,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.062499999989981e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.833300000006702e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6917373339999999,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.274999999986377e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3999999999998494e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6594429580000001,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.045800000029303e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.024999999969637e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06183533299999988,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011404199999986986,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.416700000004937e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06201762500000019,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.262500000011386e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.820799999993852e-05,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03695466699999983,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010370800000014668,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7249999999721126e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6973596670000002,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.004100000036374e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.866700000061286e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11276337499999922,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.279199999934207e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.33750000002442e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7045672500000002,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011895899999991855,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.945800000033529e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04726545800000004,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.300000000043383e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7249999999721126e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06143233299999995,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011916700000025315,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.083300000041646e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06071749999999998,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.958299999977214e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8833000000136906e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11196300000000026,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.200000000080365e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.712500000003672e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11110083300000007,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011175000000029911,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7291000000448946e-05,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.024668375000000076,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.629200000014436e-05,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.579199999987793e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7388527910000002,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.862500000006435e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0625000000081855e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07786079200000007,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.066699999975668e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.795800000056971e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7003185420000007,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.225000000017246e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.129199999931444e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12863670800000016,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.141600000006633e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.054100000023709e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06766979200000023,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.38339999997828e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6417000000076314e-05,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.5838368750000011,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00018425000000021896,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011016600000068877,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.037931250000001526,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014491700000007768,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.383400000053996e-05,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03452200000000083,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.000207415999998517,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.758299999987116e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7774555419999984,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.499999999855845e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0082999999645494e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04457291599999991,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.770800000057477e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.774999999947795e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6868107499999994,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.600000000136276e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.712500000003672e-05,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.024858333000000954,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.895800000097154e-05,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9875000000199066e-05,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10131066599999983,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010816700000049195,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.787499999991951e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0805532909999993,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010462500000052444,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.825000000074908e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06103725000000004,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.133300000030431e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.591700000133869e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.057178957999999724,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.866699999960815e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.183300000055624e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05717787500000071,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.287499999999227e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.666600000113874e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05834658300000051,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010720799999930364,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.995799999996109e-05,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05972508300000001,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.920900000080167e-05,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.97910000003543e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14693737500000026,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.350000000019065e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.883299999924873e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13971333399999963,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.47920000005098e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9625000000830255e-05,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05982350000000025,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.537500000116438e-05,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7750000000235104e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06065337499999934,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011595900000038739,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9625000000830255e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.704940624999999,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.762499999903639e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.637500000015393e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.16288650000000082,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.166699999989646e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6916999998813935e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.031230041999998903,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.083299999979033e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7750000000235104e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.0099557919999995,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.912500000057832e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.833299999873475e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12231420799999881,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.412499999861268e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.795799999968153e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.20194408400000086,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016812500000007446,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.383299999905944e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04277229199999866,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.108400000139682e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7000000000352316e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.750954333000001,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.958299999939356e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.083299999952828e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7693949159999995,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.400000000108321e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.80419999995263e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.020176041999999228,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.42920000003744e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.733299999948315e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.027311708000000934,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.037499999919874e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9584000000990613e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.056274292000001225,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010479100000004848,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.366699999953539e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04047850000000075,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.51669999999416e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6750000000983505e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3100967920000013,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.683399999931396e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9833000000276684e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3080786250000003,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.058300000219788e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8207999999050344e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.31538895899999986,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.916600000219432e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.366599999945265e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11932524999999927,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00018774999999848774,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.487500000000978e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10311679200000157,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001237500000002001,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6291999996839195e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10487195800000038,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.054099999872278e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.662499999952274e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05759649999999894,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.10830000009355e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.912500000031628e-05,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13876774999999952,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.566599999999426e-05,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.079199999968864e-05,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02166033299999981,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.912499999918055e-05,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.491599999667528e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7062409580000022,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.279200000060882e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.699999999857596e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6710974579999984,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010762499999827924,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1375000001741e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1950179169999977,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012925000000052478,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.087499999869351e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6973997920000023,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.154199999983348e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7291000001337125e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.049201083999999895,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.879099999920982e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.812499999928832e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6948269170000003,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.208300000196346e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1750000000794216e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06015999999999977,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.225000000157024e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.87910000011027e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06014133400000077,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.812499999815259e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.629200000039191e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06127441599999983,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.758399999919675e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.808399999944868e-05,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.031030416000000116,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.300000000005525e-05,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.637500000015393e-05,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07161829100000006,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.024999999951433e-05,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7333000001259506e-05,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6960873749999976,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.429199999999582e-05,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5582999998572404e-05,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07612879199999867,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.416699999713728e-05,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.054100000023709e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07571508299999863,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.029099999935397e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6666999999445125e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06621579200000127,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010329100000205926,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.116599999865912e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06127795799999802,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.391599999768573e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6666999999445125e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06506245799999988,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011150000000270666,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1124999998819476e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05971845800000253,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.137500000022669e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.829099999881237e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06075833399999908,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015683300000191025,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.604200000064452e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.046089333999997706,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.237500000163323e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.987499999842271e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.056702624999999784,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010025000000268847,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.249999999890065e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05726795800000062,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.670800000132317e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.937499999968509e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.059581458000000254,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001190839999978266,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1958000000240645e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03909612500000037,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.67089999978532e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.891700000086985e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03512783300000066,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.262499999707074e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.154200000134779e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05797870800000027,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.675000000124555e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9291999999923064e-05,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03558849999999936,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011687499999979423,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.366699999953539e-05,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03573745799999983,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.22920000018712e-05,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.099999999913507e-05,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.17238233299999806,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.533300000086342e-05,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.820800000260306e-05,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02641837499999866,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.508299999832047e-05,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.674999999920715e-05,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06641974999999789,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.79579999985458e-05,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.654199999976072e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09786412500000097,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010995799999946598,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.679199999912953e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7072312079999996,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010208400000166762,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.295900000135134e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6955339999999985,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011404099999978712,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.945799999944711e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04767949999999743,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.979200000032051e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.904200000055425e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07000566700000022,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010554200000001401,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3250000000559794e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07540887499999727,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010062500000174168,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.133300000144004e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0695089160000002,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.42499999968993e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.554199999873276e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06977941699999946,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014012500000148975,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.091700000292576e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1327177500000012,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.833300000039458e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0625000000081855e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07404062499999853,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.395900000086499e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.679199999912953e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.057996165999998794,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.912499999842339e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.637500000015393e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02174349999999947,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.99170000003835e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.591699999778598e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1045846250000011,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.241599999792015e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5958000001178334e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10311554200000117,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.920900000219945e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.829099999881237e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10356333299999676,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.754200000282708e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.76250000005507e-05,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7136643330000005,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0006926669999991475,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.7707999999934145e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07104920800000158,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.962499999791817e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.4792000000247754e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07355224999999876,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.258299999752694e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.695899999873632e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.043413541999999694,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010008400000316442,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.900000000063187e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04283345800000049,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.508300000187319e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.291600000134622e-05,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06043541700000077,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.491700000272772e-05,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.61670000007075e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7362165830000009,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.008300000028612e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.449999999740385e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7327179170000022,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.758399999919675e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8249999998972726e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7040629999999979,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012733399999831363,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.537500000267869e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7264937089999997,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.349999999879287e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7500000000866294e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7434892919999996,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001245419999982289,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3707999999375033e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6724208750000003,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.245800000101667e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.208299999992505e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6759804580000015,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.245900000147799e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.674999999920715e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11833758299999886,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.95000000014079e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.687500000244427e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6935790829999995,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.366699999839966e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9083000000393895e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6995326669999962,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.070799999870815e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8583000001656274e-05,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7230654170000008,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011241700000397259,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.616700000388164e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10497958399999874,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013424999999500642,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.270899999411995e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10507120799999825,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.083299999839255e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1042000002610166e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10438987500000252,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.56250000040859e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.862499999802594e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10382325000000492,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.295800000013287e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.658299999960036e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10419716600000584,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.779199999902175e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.733299999770679e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04770979100000261,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.833400000440861e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0041999998029496e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.6397926670000018,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.379100000155404e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9959000001820186e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.5894320829999984,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0004023750000001769,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00012612500000130922,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.8763674590000008,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.991600000030076e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.933400000339816e-05,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6663870419999967,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010199999999827014,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.129200000197898e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04806887499999846,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.966700000139326e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.899999999707916e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1211556250000001,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.279200000060882e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.654199999976072e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04174420799999723,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.920799999538986e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.58749999978636e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09716325000000126,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.04169999994997e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6417000000076314e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09386549999999971,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0002218749999940428,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.162500000073123e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06204595799999879,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.020799999997053e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.816599999912796e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0997305420000032,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.80420000015647e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1708000000871834e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09575949999999978,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.38750000013988e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.641600000354629e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1158144589999992,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.44160000031502e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.604100000449307e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11601970800000316,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010633299999796009,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.029100000086828e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1103262909999998,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.599999999920783e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.56660000046827e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1134991669999934,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.129200000046467e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.741600000102153e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11180258300000645,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.304199999997763e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.812499999928832e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11505224999999797,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.937500000565478e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.558300000212512e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07309183299999944,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.012499999665579e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.862499999802594e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07267804099999609,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.833400000440861e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7500000000866294e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07295158299999827,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014166599999754226,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.374999999854026e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07242929200000248,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012899999999405054,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.129100000151766e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2099223329999944,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001452499999956558,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.504099999915525e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.062431583999995155,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.916599999902019e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.812499999928832e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.8996455830000016,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.25410000007787e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3749999999297415e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08363741599999486,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010041700000584797,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2125000003400146e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.144079167000001,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.066700000204264e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.812499999928832e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7096720000000047,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.779199999902175e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7416999997551557e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7439690419999963,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.858399999349786e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.695799999865358e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06350470800000352,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.212500000581713e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9083000000393895e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12742879200000345,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.39590000044177e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.704100000514245e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.19886295900000306,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.241700000155561e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6749999995654434e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7130236249999982,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.845800000438885e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.67910000025995e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08411404099999942,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.100000000155205e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.041699999708271e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7040194159999942,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010825000000380669,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.445800000103418e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06109449999999583,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.454200000012179e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.049999999329202e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06541412500000376,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.987499999728698e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.691599999517848e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06111383299999318,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015766699999630873,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.870799999982637e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06359979199999799,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.554200000077117e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7750000000235104e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06048629200000022,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.954100000517883e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.600000000465343e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06216533300000293,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.945899999839412e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6417000000076314e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06584325000000035,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.841599999380833e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.579199999454886e-05,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.046389542000000006,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00023291600000163726,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.837500000107411e-05,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13312570800000145,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010345799999811334,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.795800000323425e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05729866699999775,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.183400000267739e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.812499999928832e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.059022375000004956,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.366599999793834e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7500000000866294e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03225791700000258,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.362499999492456e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6666999999445125e-05,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05040341700000539,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.620799999903284e-05,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.341600000008384e-05,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.155694375000003,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012054100000113976,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.758300000342388e-05,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.144240249999996,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012054199999766979,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.06669999988685e-05,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12502087500000414,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.400000000108321e-05,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.879200000118544e-05,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.031752916000002074,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014237499999580905,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.4208999998195395e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06158212500000104,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.874999999937017e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1083999998979834e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.1801501659999971,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010079200000490118,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.287500000150658e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6967380829999996,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.337500000583532e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.912500000386899e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7028170000000031,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.754200000282708e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.412499999835063e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09058754099999788,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.495800000218878e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.941600000307744e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.056330124999995235,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.879099999996697e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.629200000039191e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03606445800000557,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.591699999982438e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6375000003706646e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6693059160000061,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.754200000282708e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.854200000181663e-05,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6562784170000029,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016312500000026375,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.5875000001037733e-05,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04692679200000072,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.883300000344207e-05,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.058300000612917e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02031412499999874,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010091700000458559,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.041599999344726e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2241193329999973,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.870799999665223e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5999999997548e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11066704200000288,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.916700000189849e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0874999999450665e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10362183300000538,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.658299999491192e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.962500000260661e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.24533766700000115,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.808300000140434e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.020800000465897e-05,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.021237040999999124,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010729099999906566,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.070899999992662e-05,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4730398749999978,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0004962080000012747,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00022654100000352173,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04252858299999218,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011008299999559767,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.112500000199361e-05,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10904899999999884,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.912500000552882e-05,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.425000000045202e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005079417000004582,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.041699999708271e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.058300000053805e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002517920000002505,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5625000009531504e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.974999999911688e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00067754200000536,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5749999995005055e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010012500000300406,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00016941699999506454,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.008300000180043e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9707999991710494e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014216700000702076,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.729200000179844e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.537499999443753e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000646458000005623,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.466699999738921e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.002311082999995051,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7760326660000061,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.395899999731228e-05,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00030412499999954434,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7194886249999968,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.049999999888314e-05,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.574999999817919e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.009365875000000301,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.404200000214132e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4875000000388354e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.015752292000001944,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.149999999787269e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1667000004963484e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004184499999993818,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.983300000243162e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.60829999976886e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003545840000072076,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.325000000131695e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7332999994532656e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03355616600001099,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.179199999361117e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.158299999801329e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01250241599998958,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.124999999850388e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.058300000053805e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.023215333999999643,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.6042000008128525e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.791700000022047e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.21961487499999066,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.3917000002456916e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2958999998177205e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.23948966600001143,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.525000000261571e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.533300000275631e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1673683340000025,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.470800000750842e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3000000005122274e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6136039590000024,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.366700000626224e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4333999994705664e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.035326707999999485,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.566699999803859e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3165999997540894e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3077895829999875,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.499999998903604e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3582999996137914e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 2.436206833,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.008299999711198e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.800000000670934e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01721762500000068,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.266600000197741e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.379099999596292e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.015799749999999335,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.008399998971072e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.50830000033875e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.021321499999999105,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.9291000010498465e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2624999991858203e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3842800420000003,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.495899999630183e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.85839999981863e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3760101249999934,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.2749999994716745e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.279099999848768e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002229666999994606,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.049999999722331e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000352667000001361,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2832000000000079,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.766600000205017e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035258300000862164,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27000745800000914,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.691700000123092e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00027695800000060444,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26422666700000264,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.570800000029521e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002996249999966949,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2747279999999961,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.204099998783022e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000350166999993462,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28599583400000483,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.520900000519305e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.720799999802239e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008539580000075375,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.183400000101756e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.44169999980204e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008029579999941916,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.391699999928278e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.158399998743789e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.133400000545407e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.350000000068576e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.695799999547944e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.891700000086985e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3625000000370164e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.633400000069287e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.2999999994085556e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.529200000684796e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7332999994532656e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.975000000229102e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.204199998663171e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.562499999532065e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002933330000018941,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.68749999921647e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.795800000716554e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.9334000002641e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6249999993742676e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002867919999971491,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2920220830000062,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012658299999657174,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00033633400001065183,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26814274999999554,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.05830000132346e-05,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003124170000035065,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0024241659999972853,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.349999999282318e-05,
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
      "duration": 5.074999999976626e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3375000001001354e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.316700000117635e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.220899999855646e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9792000009697404e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.52919999926371e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.9125000000694854e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.091600000004746e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00024020899999754874,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002960874999999419,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0959000006400856e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.195799999706651e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.708399998624827e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4458000001791333e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00024083299999233532,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.23836158299999965,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.754100001022834e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002457919999869773,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003284042000004206,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.4834000010828277e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00027749999999571173,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2781899579999987,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.604199998922923e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002837920000047234,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26638141600000154,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.558299999743667e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002844999999922493,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29495045900000605,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.208299999841074e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003164580000003525,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28053974999998843,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.962499999791817e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00028391600000077233,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.31293600000000765,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014245799999912379,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004093750000038199,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2909238339999973,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.275000000423915e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5666999994864454e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003801417000005358,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.879200000753372e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.887500000450018e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.25375008399998933,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.720799999968222e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.600000000389628e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008477920000018457,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.500000000007276e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.170900000133315e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00030345899999417725,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9416000007008734e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00013012499999831562,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003548340000065764,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.6125000000406544e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004487920000002532,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.19887670800000024,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012562499999546617,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004851669999936803,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.18648354200000483,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015004200000134915,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004217919999973674,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14633891600000482,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012370800000383042,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003397909999875992,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14080375000000345,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013824999999201282,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004640830000113283,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.17291008299999078,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011783300000445251,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00044625000001019544,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_importable_debt_baseline",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.21356929200000252,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_importable_debt_baseline",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001311250000100017,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_importable_debt_baseline",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034283400000845177,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_zero_candidate_importable_baseline_is_current_proof",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.19966741599999693,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_zero_candidate_importable_baseline_is_current_proof",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014820800001302814,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_zero_candidate_importable_baseline_is_current_proof",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004037080000074411,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_after_isolation_and_output_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07758925000000261,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_after_isolation_and_output_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010566699999969842,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_after_isolation_and_output_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003729579999998123,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12793712500000254,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015166699999724642,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00043924999999944703,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6330995419999965,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010645899999417452,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0006003750000047603,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_bad_pytest_invocation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.18985283300000333,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_bad_pytest_invocation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001356249999986403,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_bad_pytest_invocation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.254200000592846e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_requires_nodeid_owner_root_and_exit_condition",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005564169999985324,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_requires_nodeid_owner_root_and_exit_condition",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7708999997221326e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_requires_nodeid_owner_root_and_exit_condition",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5791000001950124e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_rejects_duplicates_and_negative_ratchet",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001341669999987971,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_rejects_duplicates_and_negative_ratchet",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3083000005262875e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_rejects_duplicates_and_negative_ratchet",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.808299999263909e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_sort_ledger_preserves_test_debt_and_active_xfail_reads_ledger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002642080000043734,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_sort_ledger_preserves_test_debt_and_active_xfail_reads_ledger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3291999997686617e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_sort_ledger_preserves_test_debt_and_active_xfail_reads_ledger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003232090000011567,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_marks_registered_exact_nodeids_xfail",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13353466700000638,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_marks_registered_exact_nodeids_xfail",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001164579999937132,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_marks_registered_exact_nodeids_xfail",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004224579999885236,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_keeps_unregistered_failures_failed",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12811620799999446,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_keeps_unregistered_failures_failed",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00017779099999870596,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_keeps_unregistered_failures_failed",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004054580000030228,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_does_not_require_uncollected_registered_nodeids",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12051700000000665,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_does_not_require_uncollected_registered_nodeids",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012370899999325502,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_does_not_require_uncollected_registered_nodeids",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040250000000696673,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_strict_xpass_fails_when_registered_debt_is_fixed",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12435554200000354,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_strict_xpass_fails_when_registered_debt_is_fixed",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011958300000003419,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_strict_xpass_fails_when_registered_debt_is_fixed",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003705829999915977,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_propagates_debt_registry_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12030937499999084,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_propagates_debt_registry_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014808299999913288,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_propagates_debt_registry_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00013095899998916138,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_save_ledger_writes_test_debt_snapshot_and_machine_block",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00030608299999812516,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_save_ledger_writes_test_debt_snapshot_and_machine_block",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.991699999834509e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_save_ledger_writes_test_debt_snapshot_and_machine_block",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.9208000010357864e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_finalize_ledger_update_preserves_test_debt_and_stable_updated_at",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00018254200000455967,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_finalize_ledger_update_preserves_test_debt_and_stable_updated_at",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.1499999994698555e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_finalize_ledger_update_preserves_test_debt_and_stable_updated_at",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.170800000404597e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_refresh_auto_fields_preserves_test_debt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001678329999919015,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_refresh_auto_fields_preserves_test_debt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.037499999753891e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_refresh_auto_fields_preserves_test_debt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.237499999566353e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_ordinary_sort_and_save_reject_missing_test_debt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001708750000091186,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_ordinary_sort_and_save_reject_missing_test_debt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.345800000749023e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_ordinary_sort_and_save_reject_missing_test_debt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9207999989798736e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.250000000955879e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.066699999645152e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.908299999011433e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.47919999860369e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.291599999817208e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.487499999721422e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001280829999927846,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.350000000068576e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.695799999547944e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.6208000000547145e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.070799999704832e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.000000000165983e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.379200000277251e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.241699999989578e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3583000004000496e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.899999999314787e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.070900000068377e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.454199999453067e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.52080000030719e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.958299999988867e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.837500000258842e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.604199999709181e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1332999995470345e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1166999995189144e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.187499999692591e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7374999990902324e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5457999999266576e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.0500000003571586e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.112500000668206e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.616699999042794e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.316600000071503e-05,
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
      "duration": 3.424999999879219e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.94580000033784e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0917000003682915e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.8499999994410246e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.612499999723241e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.474999999752981e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.208299999992505e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.0457999989816926e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4040999992157595e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.908300000749932e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001089999999948077,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6417000004007605e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4458000001791333e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.2458999991577e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0084000002261746e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.587499999468946e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.129199999804769e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9541000003519002e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.300000000194814e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.629199999328648e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0332999997995103e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6417000004007605e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014245799999912379,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1750000005104084e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.591699999105913e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.991700000938181e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.029200000526089e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.325000000131695e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013662499999611555,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.058400000099937e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.262499998868407e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.029563082999999324,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.037500000388718e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.420800000559666e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01700266699999986,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.233299999929386e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0542000007803836e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00023774999999659485,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6667000003376415e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.474999999752981e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014999999999076863,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3249999987106094e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.67910000025995e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.7584000003885194e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0125000009206815e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.366699999673983e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.7375000008287316e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.041600000130984e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.300000000194814e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.845799999486644e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.958299999988867e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.541699999232151e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.949999999188549e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.958299999988867e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2833000005894064e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.3082999994226157e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.95419999929436e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2667000013475445e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.199999999343618e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9249999997205123e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.51660000035281e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.770800000310828e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0208000012521552e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2165999996891514e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.066600000385279e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.041699999073444e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.275000000257933e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.529200000533365e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.058299999736391e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4540999990895216e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000191958000002046,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3375000001001354e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2791999998948995e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014108400000623078,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.233399999658104e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.254099999594473e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.633299999236897e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.620799999737301e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7250000005428774e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.5583000005299255e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.929100000415019e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2959000009213923e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010650000000111959,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0291999991050034e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.300000000194814e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.216600000323979e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.183400000736583e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0008294590000019753,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00017870800000707732,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.641600000037215e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.954199999611774e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012129200000288165,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2791999998948995e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.445799998758048e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.529099999534992e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.608399999028734e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.729099999816299e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.141600000361905e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.183399999784342e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.233399999658104e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014637499999992087,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1417000002420536e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.287500000226373e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010733300000254076,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.308299999105202e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.487499999252577e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001864580000017213,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7915999996585015e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9457999992341684e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015295800000103554,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8000000003535206e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.51669999929527e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010954200000412584,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.366699999673983e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.350000000068576e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.241699998885906e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9957999998941887e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.483299999298197e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001792500000021846,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.037499999753891e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.820799999549763e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00017462499999965075,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.1249999995329745e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003099580000025526,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2756915410000005,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.8791999996497e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00028675000000077944,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28624104200000033,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.966699999746197e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003824169999973037,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28914249999999697,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.908299998860002e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00036016600000721155,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.30507049999999936,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.587499999634929e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003500830000007227,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2861845000000045,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010816700000759738,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004402080000005526,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2778689999999955,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.720900000331767e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040108299999985775,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29478387499999315,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.658399999068479e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003401249999939182,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.30435195799999804,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.404100000485414e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003578750000059472,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2716731249999924,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.666700000503624e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003338340000027529,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28143199999999524,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010991700000317906,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3417000003719295e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00034033299999691735,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.800000000670934e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003705419999988635,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3224976250000111,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.899999998845942e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003779160000050297,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.30479808300000855,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.879200001070785e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035141699999030607,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3093899169999901,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010720800000285635,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004255829999948446,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2964195419999953,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.649999999477131e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.820799999549763e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001502500000043483,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.62920000043232e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.900000000101045e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.633300000657982e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7250000005428774e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.754200000116725e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0014976669999953174,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.462499999784541e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.679200000306082e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.674999999096599e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.379100000699964e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5249999996267434e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012275000000272485,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.650000000732234e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.791700000022047e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.750000000645741e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3709000007320356e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5207999999897766e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002538749999985157,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5749999995005055e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6291999990112345e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.004200000120363e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.533299999958217e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9375000000063665e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.529200000215951e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3375000001001354e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.51669999929527e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.883299999709379e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.258399999594985e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.591600000163453e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00020979199999260345,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.837500000258842e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.99159999915355e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012312090000108356,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.679200000306082e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.733300000874351e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010303749999991396,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5334000003217625e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.62920000043232e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010075419999964197,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9375000000063665e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.779099999690061e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010562500000048658,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6667000003376415e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7374999990902324e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010120000000028995,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.083299999990686e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.666599999974096e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011777499999965357,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.716700000528817e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00022370799999293922,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0014772499999935462,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.437499999696229e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00012179099999798382,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011071670000006861,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010316600000237486,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011041700000191668,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010063330000065207,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.366699999205139e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001107079999940197,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001747665999999981,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.354099998873153e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000108667000006335,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011228749999929732,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.070899999599533e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.737500000511318e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011163750000093842,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.787499999281408e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.687499999382453e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03729345800000772,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.258400000078382e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010762499999827924,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00033675000000243926,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.833299999835617e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4625000001019544e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.4625000001019544e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2915999994997946e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7250000005428774e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.12500000095406e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.220800000747204e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.887500000132604e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.799999998932435e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.404100000636845e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2834000001666936e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.137499999501415e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.166700000178935e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.575000000921591e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.8041999999904874e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3625000000370164e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8250000002904017e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0016584579999943116,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.833300000939289e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3791999999598374e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010415829999885773,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.941699999643333e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8250000002904017e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009806249999968486,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.887500000132604e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4333000005281065e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009518749999983811,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.604200000495439e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9624999999432475e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009348749999986694,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5084000003848814e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.774999998995554e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009926669999913429,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6582999996426224e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.379199999490993e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2572650420000002,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.875000000012733e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.0791999999310065e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.495800000218878e-05,
      "longrepr": "tests/test_operator_machine_exception_paths.py:45: in test_normalize_skill_level_optional_only_converts_value_error\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/private/tmp/full-pytest-baseline.132b1M/wt/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "skipped",
      "when": "call"
    },
    {
      "duration": 9.004199999651519e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5999999997548e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.645899999568883e-05,
      "longrepr": "tests/test_operator_machine_exception_paths.py:54: in test_normalize_skill_level_stored_only_falls_back_for_value_error\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/private/tmp/full-pytest-baseline.132b1M/wt/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "skipped",
      "when": "call"
    },
    {
      "duration": 9.962500000426644e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5999999997548e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011241250000040282,
      "longrepr": "tests/test_operator_machine_exception_paths.py:72: in test_list_by_operator_propagates_unexpected_readside_normalization_errors\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/private/tmp/full-pytest-baseline.132b1M/wt/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "skipped",
      "when": "call"
    },
    {
      "duration": 9.041700000977926e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.85839999981863e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001471457999997483,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9709000006382666e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.949999999974807e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010200420000074928,
      "longrepr": "tests/test_operator_machine_exception_paths.py:128: in test_resolve_write_values_only_converts_validation_error\n    assert new_skill is None\nE   AssertionError: assert 'normal' is None",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "skipped",
      "when": "call"
    },
    {
      "duration": 4.258300000969939e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6375000007637937e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002085419999957594,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.612499999405827e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.554200000621677e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011991600000271774,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.124999999215561e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.424999999879219e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.18329999973821e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9334000004155314e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.675000000669115e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.508399999129779e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2665999995629136e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3333000004631685e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.133299999864448e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9958999988366486e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.483300000084455e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005187919999940505,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.483300000084455e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.537499999595184e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00020008399999937865,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.429199999516186e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4374999998476596e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00022179200000493893,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7624999990271135e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.675000000669115e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014904100000023845,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.72920000066324e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.791700000022047e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001723339999983864,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.616600000100334e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3041000008893207e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.729200001132085e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6167000004638794e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.404100000168e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008676249999979291,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.2832999994857346e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.487500000356249e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.67910000010852e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8000000003535206e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.866700000150104e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011208399999418361,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.770799999358587e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9291999999923064e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.441699999333196e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.679099999942537e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7708000010970864e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.2375000009874384e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7458000008427916e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.733299999770679e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012308299999119754,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.845800000590316e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3167000004350484e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.991599999002119e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7792000000536063e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.462499999784541e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.1666999993926765e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.116699998884087e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.341699999737102e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010879100000238395,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1708999998159015e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4458000001791333e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001068374999988464,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.312500000163254e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.154199999424236e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0014165000000048167,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.566699999803859e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.591699999271896e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004066499999993312,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.675000000986529e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.9582999995200225e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010421249999978954,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.3957999992016994e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.0541999999941254e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010066669999986289,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.36250000035443e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.320900000072015e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009998750000050904,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.387500000291311e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.5291000009560776e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009725409999958856,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.254200000275432e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7082999995163846e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00017645800001275802,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.120799999578594e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3874999999738975e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00023558400000922575,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.300000000194814e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.579199999137472e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012562499999546617,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.141600001299594e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.816699999958928e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003043330000025435,
      "longrepr": "tests/test_query_services.py:163: in test_operator_machine_query_service_lists_with_names_and_linkage_rows\n    assert simple == [\nE   assert [{'dirty_fiel...': 'M2', ...}] == [{'is_primary...: 'beginner'}]\nE     \nE     At index 0 diff: {'operator_id': 'O1', 'machine_id': 'M1', 'skill_level': 'expert', 'is_primary': 'yes', 'dirty_fields': ['skill_level'], 'dirty_reasons': {'skill_level': \"历史技能等级 'high' 已兼容归一为 expert。\"}} != {'operator_id': 'O1', 'machine_id': 'M1', 'skill_level': 'expert', 'is_primary': 'yes'}\nE     Use -v to get more diff",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "skipped",
      "when": "call"
    },
    {
      "duration": 4.583300000149393e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6167000004638794e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00024075000000323143,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.933299998948314e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002979579999902171,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12455441699999881,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00017608299999949395,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00041712499999846386,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.085369166999996,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016912499999932606,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004330419999973856,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.162991458999997,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013383399999611356,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.84170000084805e-05,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.8547948340000033,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013679200000638048,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.720800000437066e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010666699999717366,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.958300000306281e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5958000001178334e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005657709000004729,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.316699999013963e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00045820799999773953,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002036291999999662,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.679199999837238e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002861250000023574,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0021810840000000553,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.7999999995672624e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002725000000083355,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2855637080000122,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001319170000044778,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040949999998929343,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26584437500000035,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011950000001093031,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00046116699999743105,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2681487920000052,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015412499999456486,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004472090000007256,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2638786670000002,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012312500000177806,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003819579999913003,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.017125958999997692,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001306660000039983,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.4500000004509275e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010904199999117736,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.462499999784541e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7500000004797585e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.695800000182771e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.395800000305371e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039962500000001455,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2939962500000064,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012854199999878801,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00048562499999604825,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1486189170000074,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011829099999260961,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003948749999977963,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2930824169999937,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001197079999997186,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00041412500000603814,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2937953329999914,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011283299998865459,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040308299999480823,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.585765374999994,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00027866699998924105,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005140840000024127,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2693762910000004,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010729200000980654,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005052500000033433,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26925583300000255,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011433299999907831,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004671250000001237,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.267866166999994,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011295800000254985,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.67089999918835e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0024036659999921994,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.583400000512938e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1917000004332294e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_shared_quality_registry_does_not_split_quality_gate_error_identity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011091599999701884,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_shared_quality_registry_does_not_split_quality_gate_error_identity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.379199999642424e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_shared_quality_registry_does_not_split_quality_gate_error_identity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.008300000028612e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0026916249999970887,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.970800000592135e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00012254099999609025,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02319220799999755,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.970800000440704e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039712500000632645,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.024150458000008257,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001314170000057402,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.912500000386899e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0030082910000004404,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.575000000135333e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2417000003069916e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005830000000059954,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.829099999881237e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003471670000010363,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12590816699999152,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012404099999230311,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010254200000758829,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002745833999995284,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.933399999629273e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.129199999804769e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002558125000007294,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.891699999300727e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003753750000043965,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005849624999996195,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.525000000578984e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2624999991858203e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2752926670000022,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012474999999767533,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000496958000013592,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02511466699999687,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001173330000057149,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003882919999966816,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02519041699999036,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014695800000197323,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040654100000381277,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.022730209000002333,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013695900000243455,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035937500000216005,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02490329199999053,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012904199999752564,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004132079999976668,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02374316599998849,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001670409999974254,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.7875000010199074e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0028029159999931608,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.7667000004025795e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035533300000167856,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.022151292000003764,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013537500001348235,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035325000000341333,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.025641417000002775,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013145900000210986,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8374999991551704e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012787499998978547,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.808299999263909e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0208000001484834e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.599999999920783e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.366699999673983e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.820800000653435e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.73749999972506e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.287500000226373e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.566699999169032e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002524169999986725,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.37080000036849e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6708000010321484e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013212500000747696,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.187500000478849e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.466700000842593e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015108399999519406,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.275000000257933e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3417000011581877e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012145800000951112,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.570799999863539e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.55000000098471e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012675000000683667,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1500000005735274e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.245799999262999e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012745800000857344,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3583000004000496e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3625000000370164e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008864169999895921,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.97920000081831e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.787500000702494e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.670799999777046e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.233300000715644e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.958300000306281e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021887500000161708,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.37080000036849e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.600000000072214e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001443750000049704,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9624999999432475e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.716599999847858e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.5459000007736e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.125000000636646e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7374999990902324e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.595899999377707e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.079200000399851e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040145799999891096,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4155808750000034,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.445899999287576e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003706669999985479,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.47349924999998905,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.374999998750354e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003676669999919113,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4313111660000004,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.95000000014079e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039616699999101,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.464679916999998,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.779200000537003e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040879099999813207,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.41757945800000584,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.000000000014552e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034920800000293184,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.39673808300000246,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.966699999746197e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003398749999945494,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.43517795900000067,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.870900000739312e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003373330000044916,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.38784708299999693,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.287500000392356e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5124999999757165e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.333300000629151e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.499999999689862e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9375000000063665e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.9667000002150417e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.204200000084256e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0029037080000051674,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0016604589999928976,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001261249999942038,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.387499998870226e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.633300000023155e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4542000008741525e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.758399999753692e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.208400000673464e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2583000006525253e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.591700000526998e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.766700000719993e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.204099999720711e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.720799999484825e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.266700000561286e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3499999986474904e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.016700000723631e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01711054199999751,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.533299999489373e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.949999999505962e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.016616458000001444,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.01250000076925e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.029200000374658e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01658320899998955,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.224999999915326e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.900000001053286e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01601241699999889,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.291600000452036e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.88749999966376e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.016824208999992152,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.887500001084845e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.600000001175886e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00025033299999677183,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.891699999769571e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9125000000694854e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.879200000284527e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2791999998948995e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7667000004025795e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00022195799999735755,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.300000000194814e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4540999990895216e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.637499999508691e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0332999997995103e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3375000001001354e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013583300000163945,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.17919999872629e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7082999995163846e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010679199999685807,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.025000000889122e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.366700001095069e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.120799999744577e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.270900000984511e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035787499999173633,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5717889590000027,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001025830000003225,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.891699998983313e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000876000000005206,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.725000000860291e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3500000003859896e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003231249999942065,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.954200001032859e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.887500000450018e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.495799999901465e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4124999999107786e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8207999992323494e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.862499999726879e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3959000006689166e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.608400000132406e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.975000000863929e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4666999994215075e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.741700000148285e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00042670799999200426,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.091599998901074e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001874580000134074,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012264169999980368,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.225000000701584e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.941699999643333e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.604100000297876e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.375000000005457e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0000000012696546e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001331250000049522,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.479100000447488e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5249999996267434e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.45366275000000655,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.5000000003246896e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.116599999155369e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.013188166999995588,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.65830000027745e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5665999991229e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.5483500410000062,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.629199999494631e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.429200000151013e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.19656879199999366,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.29589999966629e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.4874999989351636e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.019392624999994723,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00021787499998993098,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.774999999947795e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7027301250000022,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.316700000283618e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.558399999789799e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00035649999999520787,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.02499999978545e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00045087499999851843,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004428209000010952,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.004199998699278e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032712499999831834,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004005840000047556,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5124999999757165e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6332999997057414e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002335083000005511,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.28339999984928e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.425000000196633e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00180004199999928,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.2874999991227014e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.779099999690061e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010055839999978389,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5499999995636244e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.562499999532065e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009038750000058826,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.716700000211404e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00013320800000826694,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005355999999991923,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.858399999984613e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00014525000000276123,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0040489169999915475,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.300000000043383e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011970900000335405,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004470333000000437,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.216700000536093e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00013295800000889813,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004228166999993732,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.445800000027702e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010391700000411674,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004204416000007427,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.46249999963311e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.029099999693699e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00029029099999888786,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.162499999438296e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.287499999440115e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002242089999953123,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.574999999817919e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.425000000045202e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003906667000009634,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.9208000010357864e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.670799999611063e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004839333999996143,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.837499999789998e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00012787499998978547,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004116667000005236,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.329100000674771e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.291599999983191e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003788749999998231,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.137500000136242e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003551660000056245,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_imports_seed_entries",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004933917000002452,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_imports_seed_entries",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.09580000012511e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_imports_seed_entries",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00042670900000985057,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update0-schema_version]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004697958999997809,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update0-schema_version]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.033399998907953e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update0-schema_version]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037620899999524227,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update1-schema_version]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004242333000007648,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update1-schema_version]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.879100000389826e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update1-schema_version]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034712499999045576,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update2-baseline_kind]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004988707999999065,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update2-baseline_kind]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010504099999764094,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update2-baseline_kind]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004726250000004484,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update3-importable]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004626874999999586,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update3-importable]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.270899999729409e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update3-importable]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037920900000187885,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update4-importable]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004278833999990184,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update4-importable]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.90840000032722e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update4-importable]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003595839999945838,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update5-importable]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005073875000007888,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update5-importable]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00023070800000368763,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update5-importable]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004892919999974765,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update6-pytest_exitstatus]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02308579200000338,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update6-pytest_exitstatus]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.087499999793636e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update6-pytest_exitstatus]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003992079999903808,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-schema_version]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004749541999998996,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-schema_version]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.89169999961814e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-schema_version]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003775839999917707,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-classifications]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004679417000005515,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-classifications]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.812500000487944e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-classifications]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040141700000617675,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt0]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004369332999999642,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt0]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.191699999964385e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt0]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037120799999001974,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt1]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004470666999992545,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt1]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.820899999444464e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt1]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037966699999003595,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-failed_nodeid_count]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004522124999994048,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-failed_nodeid_count]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011125000000333785,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-failed_nodeid_count]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004367500000057589,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collected_nodeids]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004581625000000145,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collected_nodeids]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.120799999427163e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collected_nodeids]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037458299999570954,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collection_errors]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004808167000007302,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collection_errors]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.304099999951632e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collection_errors]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00041220800000019153,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-reports]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004404041000000802,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-reports]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.416599999032769e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-reports]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005818329999982552,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-worktree_clean_before]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0045004589999990685,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-worktree_clean_before]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.979100000454764e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-worktree_clean_before]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003742079999966563,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004424709000005578,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.995800001163843e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003712080000042306,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-required_or_quality_gate_self_failure]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004237291000009691,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-required_or_quality_gate_self_failure]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.941699999174489e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-required_or_quality_gate_self_failure]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035412500000120417,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-main_style_isolation_candidate]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0055791249999970205,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-main_style_isolation_candidate]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010266700000727269,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-main_style_isolation_candidate]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004154580000061969,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-collection_error_count]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004462625000002163,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-collection_error_count]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.304099999316804e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-collection_error_count]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003345410000008542,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_unknown_candidate_nodeid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004296000000010736,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_unknown_candidate_nodeid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.795800000565123e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_unknown_candidate_nodeid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003617079999997941,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_empty_candidate_nodeid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005044583000000102,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_empty_candidate_nodeid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.075000000928867e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_empty_candidate_nodeid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003784169999931919,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_current_dry_run_candidate_drift",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004345958000001815,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_current_dry_run_candidate_drift",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.725000000074033e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_current_dry_run_candidate_drift",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034966599999108894,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_does_not_overwrite_existing_test_debt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004342790999999124,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_does_not_overwrite_existing_test_debt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.02499999963402e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_does_not_overwrite_existing_test_debt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.970799999337032e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[owner--owner]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002714040999990175,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[owner--owner]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.166599999029131e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[owner--owner]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00012366600000746075,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[style-untriaged-untriaged]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0028279999999938354,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[style-untriaged-untriaged]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.454100000041763e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[style-untriaged-untriaged]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.458300001099815e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_duplicate_debt_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002810083999989388,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_duplicate_debt_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.658299999960036e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_duplicate_debt_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.475000000070395e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00032254199999215416,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4124999999107786e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.858400000922302e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001517080000041915,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.316699999800221e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.429199999516186e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012833300000636427,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.220800000747204e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035595900000373604,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.58930645800001,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.799999999098418e-05,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.908299999328847e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006524169999977403,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.241700000624405e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.395800000622785e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003809580000080359,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.995800000211602e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.958400000669826e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00045320799999615247,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.804099999626942e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.337499999948704e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006647919999949181,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.183399999632911e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.549999999412194e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005754169999931946,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.92920000030972e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.700000000137152e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005406669999956648,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0583999993136786e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.275000000106502e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004550409999950489,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.654199999265529e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0208000001484834e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.3208999997546016e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4124999999107786e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7500000004797585e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004417090000004009,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.94580000033784e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.141600000195922e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004410840000019789,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.808399999627454e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8791999998011306e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00034604200000387664,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7082999995163846e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.754200000116725e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004264580000068463,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.724999999121792e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.133399999441735e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00047404200000755736,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.758400000071106e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.770799999358587e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00034004100000117887,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.662499999279589e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.833399999564335e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00029966699999306456,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.587499999468946e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.033300000751751e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00030908399999418634,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.36250000035443e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.616699999677621e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008701249999916172,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.4875000000388354e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.845800000590316e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006910000000033278,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9125000000694854e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00044929199999899083,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013647500000075752,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.33340000035787e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.629199999963475e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005080000000106111,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.020800000465897e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.36250000035443e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.099999999913507e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.508300000021336e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010937500000807177,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00037379199999065804,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.450000000768341e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032941700000321816,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004496375000002217,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.125000000485215e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00046387500000832915,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003495208000003913,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.620800000372128e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003473329999934549,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0034677080000022897,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.0415999996621395e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00036891700000296623,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.011770374999997557,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.341600000643211e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.633399999917856e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004043207999998799,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.208300000309919e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000417458999990572,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003275165999994556,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.9208999999782463e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003277920000073209,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004954917000006276,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.883299999709379e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003635000000059563,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 12.081411583000005,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0005274589999970658,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0011775419999935366,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.009731541999997262,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00018416599999682148,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0009959170000115591,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.010392792000004647,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00018441699999982575,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0008216660000073261,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.008144000000001483,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001212919999886708,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001206249999938791,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00536099999999351,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.633399999917856e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.9624999991569894e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005481249999945703,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.849999999289594e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.558299999426254e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002652909999909525,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.566699999803859e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.833299999835617e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00026720900000043457,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.183300000055624e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.295900000135134e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003999159999921176,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.2791999991086414e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.341699998950844e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001475410000040256,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.841700000213223e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.566699999803859e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00041187500001171884,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.183300000373038e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.8791999990148724e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00019925000000853288,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.012499998713338e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.050000000039745e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003603330000032656,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.025000000102864e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.595800000435247e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00043320800000401505,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.9250000003553396e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9791999998660685e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001425000000097043,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.516599999249138e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.52080000030719e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011708299999213523,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.266699998822787e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.012500000134423e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00037637500000187174,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.4459000008600924e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.791699998918375e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011391599998944457,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016524999999489864,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.808299999898736e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001089999999948077,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0333000004343376e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.370900001366863e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.245800001167481e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.3500000003859896e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.287499999757529e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.183299999269366e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5999999997548e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9415999995972015e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010958299999686005,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.287500000543787e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.17499999972415e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012045900000146048,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0005634160000056454,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises",
      "outcome": "passed",
      "when": "teardown"
    }
  ],
  "schema_version": 2,
  "summary": {
    "classification_counts": {
      "candidate_test_debt": 0,
      "main_style_isolation_candidate": 0,
      "required_or_quality_gate_self_failure": 0
    },
    "collected_count": 631,
    "collection_error_count": 0,
    "failed_nodeid_count": 0,
    "outcome_counts": {
      "call:passed": 626,
      "call:skipped": 5,
      "setup:passed": 631,
      "teardown:passed": 631
    }
  },
  "worktree_clean_before": true
}
```
<!-- APS-FULL-PYTEST-BASELINE:END -->
