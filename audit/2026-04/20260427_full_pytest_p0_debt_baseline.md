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
  "generated_at": "2026-04-27T14:29:53+08:00",
  "git_status_short_after_write": [
    " M audit/2026-04/20260427_full_pytest_p0_debt_baseline.md"
  ],
  "git_status_short_before": [],
  "head_sha": "75b0c77cceddf5fa2c887fd281767c93e745b282",
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
      "duration": 0.00023304200000007214,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.021529750000000014,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.71660000000729e-05,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.599999999999049e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.664389458,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.812499999999446e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8000000000048004e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6688153340000003,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.825000000005744e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6207999999658966e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7054800000000001,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.704200000002714e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.27919999999682e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6668776250000001,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.012499999976441e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.895899999990405e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06223429199999986,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.766699999991246e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.208299999992505e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06068920799999988,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010016700000026191,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.179200000033802e-05,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03670699999999982,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.475000000007782e-05,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9084000000032546e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7027810420000002,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.883300000002038e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.620800000016857e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11153729099999943,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.608400000069793e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3249999999671616e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6998539159999995,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011637500000016843,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.866599999926336e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.046506292000000116,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.5166999999432e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.945799999995671e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.061115832999999675,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.649999999959078e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6417000000076314e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.062098999999999904,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.954099999998078e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.204100000000267e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11282566599999999,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012370799999938953,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.7208000000308346e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11037766699999985,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.983399999922369e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.174999999990604e-05,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.024706874999999684,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.49169999996846e-05,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.366600000034083e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7425385000000002,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.53750000002762e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.741600000013335e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07782504199999973,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016520800000030533,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.937500000032571e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7010576250000007,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.883400000086027e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7958999999764274e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13139187499999938,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001335000000004527,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.737499999991513e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06798270800000061,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.258299999968187e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.75419999999005e-05,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.0811159999999997,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0003324169999991966,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00012662500000004684,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04072366699999996,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.000118708000000467,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.083300000054749e-05,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.035064625000000404,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001051670000009608,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.749999999871136e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.8509328329999999,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.854199999890454e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.741600000064295e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.045249332999999226,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.408300000046665e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.037499999893669e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7018737909999988,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.187500000111925e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.887499999917111e-05,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02519054100000062,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.987500000083969e-05,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.941599999952473e-05,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10426879200000094,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010104200000071728,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.14170000012848e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08173941699999965,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.387500000000102e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.85419999996617e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06101787499999922,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001240410000011849,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1665999999173096e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05724866599999956,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.83329999989968e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1166000000435474e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.058434625000000295,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.175000000143484e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.61670000007075e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.058015499999999776,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.437499999975785e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.129100000011988e-05,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.057930332999999834,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.404100000054427e-05,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7792000000157486e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1440231669999985,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001398330000004222,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.345900000072959e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.14165562500000028,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.587499999952342e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3791000000913414e-05,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.061349040999999715,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.52500000011014e-05,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.608299999908638e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06122287500000034,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013891600000093263,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.295800000051145e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7078100420000002,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.395799999976305e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.900000000063187e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.163798667,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.445799999989845e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.016599999940752e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03169145799999917,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.691599999899324e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.416700000144715e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.9987219589999992,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.799999999948739e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.433299999957342e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12205837499999994,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.850000000000136e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.341700000016658e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.19579887499999948,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.51669999999416e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.249999999890065e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04408737500000015,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.024999999951433e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9666000000669897e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7686290420000006,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001208329999986546,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9291999999923064e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7718690830000003,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.949999999963154e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8249999998972726e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.019960917000000578,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.991600000067933e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6000000001100716e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02836083299999892,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.545900000063057e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.970900000029644e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05671683299999941,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011204099999950756,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.4541999999102586e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04152670899999933,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.449999999982083e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.812500000106468e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3168177919999984,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.562500000053319e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9083000000393895e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.30847987499999974,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.420799999913186e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.891700000086985e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3134624579999983,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00038995799999952396,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.458400000004417e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11704645899999733,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.712500000029877e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.850000000189425e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1051620419999999,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010437499999937927,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2542000002375744e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10361679100000032,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011416699999955426,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.608300000010559e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05791170800000245,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.579100000005724e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.820800000260306e-05,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13720891699999882,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.179199999958087e-05,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.054200000031983e-05,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02146529100000194,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.662499999838701e-05,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.579200000165429e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7186912079999992,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.062499999856755e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.008300000142185e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6747833750000005,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.8540999999841e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3875000002534534e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.16896587500000138,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.924999999848637e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.616699999677621e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7103421250000004,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012662500000004684,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.962499999867532e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05364954199999872,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.387499999784609e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7750000000235104e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.712090332999999,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.566700000083415e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.766600000039034e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05873762499999913,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.987499999728698e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7374999997629175e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.060873833000002264,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.525000000185855e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.879200000118544e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06056812499999964,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.5667000000077e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.4958000003324514e-05,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.031022166999999712,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.733400000020652e-05,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.949999999936949e-05,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0719947079999983,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.374999999816168e-05,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9791999998660685e-05,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7007680839999999,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.350000000234559e-05,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.895800000070949e-05,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0741254999999974,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.816600000116637e-05,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.025000000102864e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07643758300000059,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.920799999856399e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.749999999731358e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0649599589999994,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.583400000006236e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.987499999842271e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06434970900000181,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.716600000013841e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.574999999817919e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06479262499999905,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.425000000045202e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.770800000031272e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05972241599999961,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011533400000018901,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.4125000001903345e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.060415708000000734,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.312499999973966e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7416999997551557e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04845225000000042,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010054100000189692,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.404199999858861e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05709004200000223,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010199999999827014,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1708000000871834e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06010512499999976,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.337499999910847e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.01669999977139e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.056017666999998994,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.516699999816524e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9999999998107114e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03978541700000093,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.975000000115529e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5958000001178334e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03600866700000083,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.379100000155404e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.649999999983834e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05859983300000238,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.962500000147088e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.649999999983834e-05,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.036776917000000964,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.63340000023527e-05,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.845800000197187e-05,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.036148000000000735,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.754199999965294e-05,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7041000001968314e-05,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.173780292,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.300000000005525e-05,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1750000000794216e-05,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0266405419999991,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.208400000242477e-05,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.891700000086985e-05,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06628750000000139,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.137499999667398e-05,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.308299999740029e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09619675000000072,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.125000000054229e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9333999999845446e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7165912080000005,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.52500000011014e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.754100000032736e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6972087499999979,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.020799999997053e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.912500000031628e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.047712624999999065,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.045799999896076e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.004100000149947e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06993133300000309,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.300000000043383e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.054100000023709e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07500941700000041,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.020799999959195e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.841599999849677e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0701407500000002,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.520800000117902e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.283399999811422e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06948058400000079,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.708299999999781e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.833299999873475e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13345449999999914,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.779199999864318e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.054200000031983e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0740052079999991,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010370899999756489,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.225000000270597e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05735279199999965,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012362499999696297,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.6874999998512976e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.020517042000001595,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014508400000323718,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.308300000095301e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10434150000000031,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.712499999992019e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.912500000031628e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10377016600000033,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.000114792000001529,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.283300000120562e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10447233300000036,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.141700000052765e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.070799999984388e-05,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7187842909999986,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001205420000012225,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1832999997003526e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07279120800000172,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.091699999823732e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.945799999944711e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07567229200000014,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012100000000003774,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.74579999994296e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.044279583999998096,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.749999999973056e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.633400000031429e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.044581790999998816,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.966700000139326e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.383299999905944e-05,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.059848374999997844,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.141700000052765e-05,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.608300000048416e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7365937080000009,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.64999999987026e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.61670000007075e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7513600419999982,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.062500000212026e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.104199999905745e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.696704583999999,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.841700000061792e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.654199999976072e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7321921249999974,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.587499999952342e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2916999997876246e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7341965409999993,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.737500000004616e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.916700000023866e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6662274169999982,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.691600000114818e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.716700000173546e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6747975410000002,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.98329999973646e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.637500000015393e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1194880420000004,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.508399999802464e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.787499999991951e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7032429580000006,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001202499999983786,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.7000000001750095e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6970018329999981,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.008399999999028e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2916999997876246e-05,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7352010419999999,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.23750000020118e-05,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6666999999445125e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10351037499999904,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010333400000206439,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.6833999998673335e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10220308299999914,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.620900000659958e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.758300000418103e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10247704099999311,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.833400000123447e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.970799999881592e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10498008400000458,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014608400000071242,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.262499999503234e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.10552316600000466,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.50409999944668e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9000000004184585e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04775495900000237,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.324999999904549e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.525000000261571e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.6916030000000006,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.733300000329791e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8750000004815774e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.084960959,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001642499999974234,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010175000000600676,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.8750515830000012,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.38750000013988e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.887499999739475e-05,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6682547499999956,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.724999999998317e-05,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8499999998341536e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04733362500000027,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.474999999918964e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.133299999788733e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11944075000000254,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012379200000367518,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.7957999999302956e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.042776667000005375,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.166600000374501e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7750000000235104e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09680883299999721,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.283399999697849e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7999999999603915e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09643691699999835,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.808299999823021e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8332999995182035e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.059805374999996275,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.612499999964939e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.733300000481222e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09978570899999539,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.491600000264498e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.687500000244427e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0971067500000018,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.599999999996498e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6916999998813935e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11592449999999843,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.974999999760257e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.76250000005507e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11658570800000234,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.512500000217415e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.954099999565642e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11238999999999777,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.129200000046467e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0583000003712186e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11382650000000183,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.170799999618339e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.883299999391966e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11247700000000549,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.579199999696584e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.433299999741848e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11603883400000115,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.170799999935753e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.404200000214132e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07230670799999928,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001242499999989377,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.333299999994324e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07235787500000157,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013608300000100826,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.608299999693145e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07407837499999914,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.991599999319533e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.283299999803148e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0730628330000016,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.100000000155205e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.77920000037102e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.19947595800000073,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.874999999937017e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3208000004190126e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06326641600000471,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.30839999963473e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9374999996132374e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7627222079999996,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.508400000157735e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2999999994085556e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.07747583300000116,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.579200000407127e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2749999994716745e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13455054099999586,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.733300000329791e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8458999998501895e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7074700410000005,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.012500000376122e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.754200000434139e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7364860409999991,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.779200000219589e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.758400000071106e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0631643749999995,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.070799999870815e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.050000000039745e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12986825000000124,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013170799999784322,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.441700000119454e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.20233108300000424,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.954199999777757e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.412500000545606e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7568586249999996,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.958300000472263e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8833000001025084e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08596641700000163,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.837500000107411e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0625000000081855e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7251099580000044,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.837500000424825e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.8040999995512266e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06165379200000132,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.825000000138971e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.141700000166338e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06162979199999796,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.258300000107965e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.149999999787269e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06300295800000555,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.412499999759348e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.699999999819738e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06291379099999972,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.9415999998389e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.92080000000783e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05959479199999862,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.162499999997408e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.74579999973912e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.061020167000002346,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.770800000235113e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.837500000576256e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06382758400000199,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011495799999750034,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.629199999646062e-05,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.047974666999998306,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.029199999981529e-05,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7750000000235104e-05,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13540520800000166,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.541699999715547e-05,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0833000003081e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05782779199999766,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011945800000034978,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.537500000230011e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05826774999999884,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.21249999987117e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.687500000244427e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.030874834000002238,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.891599999965138e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2040999996449955e-05,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04974195900000211,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.308399999952144e-05,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.7416000004195666e-05,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.094929499999999,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00034916599999945674,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032270799999878363,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.198056832999995,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001555409999980384,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.279200000136598e-05,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13260458299999556,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.816699999807497e-05,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.000000000165983e-05,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03390158299999513,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.208399999887206e-05,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.77920000037102e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.060931208999996045,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.920800000642657e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.904200000055425e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.1836488749999958,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001300420000021063,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.616599999948903e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.713657542,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.012499999665579e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.19590000038761e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7119183749999962,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.516600000518793e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.250000000245336e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.09937195799999898,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.016700000013088e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.72909999942317e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.056142250000000615,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012120800000303689,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.5875000001037733e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.036924000000006174,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.108299999776136e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.412499999835063e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6924977079999977,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.062499999856755e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.262499999503234e-05,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.680282708,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010262499999669217,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.320800000025883e-05,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.04859645799999868,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.216600000565677e-05,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.575000000135333e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02074079100000148,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.516600000201379e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.924999999644797e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2324762920000012,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.237499999808051e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.149999999787269e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11453004099999475,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010120900000032407,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010724999999922602,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11544591699999529,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.595899999619405e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.6750000005934e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2600536670000011,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.779200000219589e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.108300000244981e-05,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02104041700000181,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.808300000533563e-05,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.316600000071503e-05,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4602473330000052,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0002537079999953562,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010195800000190047,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03724887499999596,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012458300000162126,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.708400000514757e-05,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13859304200000366,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011383399999687072,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.733400000375923e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005322833000001026,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.07079999994653e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.479100000054359e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00028887499999541433,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7959000003695564e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.400000000259752e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007029580000050828,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.850000000227283e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010220799999416386,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001792920000056597,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.412500000228192e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.6166000000246186e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001616250000040509,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.104200000654146e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.458299999603014e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008002920000009794,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.3999999998666226e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0019184169999988399,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.8386084170000103,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010179200000948185,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032983399999864105,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7509124170000092,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.879099999920982e-05,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7791999989499345e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.009522875000001818,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.6042000008128525e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.999999999848569e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01608837499999538,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.295800001192674e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.358300000717463e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004810583999997675,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.24160000026086e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.154200000527908e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003683329999972784,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.466700000842593e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.879100000858671e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.034177749999997786,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.0000000004833964e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7041000001968314e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.012091542000007394,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.8500000005446964e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.070900000385791e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02507691600000328,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.1542000008453215e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.320799999391056e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2330566669999996,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.033300000751751e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.483400000765414e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.24668504199999575,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.73749999972506e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.662499999597003e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.17003541700000824,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.141699999773209e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7667000004025795e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6482056669999992,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.470900000010715e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.570800000180952e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0378927079999869,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.766600000673861e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.370799999582232e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.32933116700000653,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.8791000000724125e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6999999995023245e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 2.5307747079999956,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.0750000002940396e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.804199999204229e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01842183400000863,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.208400000673464e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.041699999708271e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01717458299999919,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.7542000007515526e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7958000010339674e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02103504100000464,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.212499999629472e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.341700000054516e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.39524462499998947,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.320800000025883e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.308299999740029e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.41471654200000785,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.016700000088804e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.416699999865159e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0022381250000051978,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.437500000165073e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00030225000000427826,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2772859580000073,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.962499999791817e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00030166599999859045,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28051912499999787,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.854200000347646e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00029345900000521397,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27789612499999805,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.404099999381742e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00028354200000535457,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2969914579999937,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.041600000296967e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00029129100001057395,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2899191249999973,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.620800000220697e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.916700000023866e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008538340000114886,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.1375000009225005e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.079100000353719e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008785419999952637,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.183400000101756e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.391600000985818e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.01669999977139e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3375000001001354e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8000000003535206e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.833399999881749e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.316699999800221e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.716700000211404e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.1458000001503024e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.399999999942338e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.791700000022047e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.0249999986817784e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3291999997686617e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.637499999342708e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003477089999961436,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.558399998837558e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9375000000063665e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.612500000358068e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6332999997057414e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00031900000000462114,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28809412500000064,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.533400000487745e-05,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00031416699999908815,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27824320800000635,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.599999999920783e-05,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003173750000087239,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0025370000000037862,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.858400000136044e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.370799999264818e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.5791999997722996e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4958000000528955e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0416000004483976e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.729099999982282e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5999999994373866e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8124999989008757e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.0082999987589574e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.204200000084256e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00023745800000085637,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0026705420000041613,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.408300000908639e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.554100000575545e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.22090000017306e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.645799999674182e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002575840000105245,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.25707633300000055,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.137499999349984e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002813330000037695,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0029937499999874717,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.879200000435958e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002904170000022077,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.31533625000000143,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.762500000614182e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00031116699999245157,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.25445333399999015,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.937499999854936e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00029616599999826576,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29589229100000125,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.816699999807497e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00029195899999479025,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2927042499999999,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010037500000237287,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003698750000040718,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.25351037500000473,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.699999999668307e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003026250000033315,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2849341250000066,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.162499999286865e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4833000004018686e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0032433340000039834,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.9583000006236944e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.616700000781293e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.22040966699999842,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.675000001152512e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.645799999205337e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007809159999965232,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.32909999972253e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.391699999928278e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002970840000102726,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.900000000101045e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010845900000333586,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003047080000015967,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.291699999077082e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037574999998923886,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.18671562500000505,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016229199999884258,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00043141599999785285,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.17380995800000676,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015316699999345929,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004903339999913214,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1370524169999925,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010595900000964775,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034487499999613647,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13818633299999306,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010616699999843604,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003765419999979258,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.17253720900001213,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001443750000049704,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040258300001028147,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_importable_debt_baseline",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.20926337500000614,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_importable_debt_baseline",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011945900000398524,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_importable_debt_baseline",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034058299999628616,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_zero_candidate_importable_baseline_is_current_proof",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1992787920000012,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_zero_candidate_importable_baseline_is_current_proof",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011341599999070695,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_zero_candidate_importable_baseline_is_current_proof",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00033849999999802094,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_after_isolation_and_output_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.08087041599999623,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_after_isolation_and_output_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011220799999023257,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_after_isolation_and_output_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003907500000082109,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.135445500000003,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015424999999424927,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_requires_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000398083000007432,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6314547910000101,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.000134458000005111,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039770799999416795,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_bad_pytest_invocation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.19325645799999336,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_bad_pytest_invocation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010500000000490672,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_importable_rejects_bad_pytest_invocation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.316699999013963e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_requires_nodeid_owner_root_and_exit_condition",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005945840000123326,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_requires_nodeid_owner_root_and_exit_condition",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.24999999921738e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_requires_nodeid_owner_root_and_exit_condition",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9375000000063665e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_rejects_duplicates_and_negative_ratchet",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014854100000150083,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_rejects_duplicates_and_negative_ratchet",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3375000001001354e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_test_debt_registry_rejects_duplicates_and_negative_ratchet",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.716699998790318e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_sort_ledger_preserves_test_debt_and_active_xfail_reads_ledger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.495800000218878e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_sort_ledger_preserves_test_debt_and_active_xfail_reads_ledger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3874999999738975e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_sort_ledger_preserves_test_debt_and_active_xfail_reads_ledger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003876669999982596,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_marks_registered_exact_nodeids_xfail",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13644737500000303,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_marks_registered_exact_nodeids_xfail",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013891700000101537,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_marks_registered_exact_nodeids_xfail",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004062499999974989,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_keeps_unregistered_failures_failed",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13174029099999984,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_keeps_unregistered_failures_failed",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010683300000380314,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_keeps_unregistered_failures_failed",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004989580000085425,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_does_not_require_uncollected_registered_nodeids",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12315649999999323,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_does_not_require_uncollected_registered_nodeids",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012012499999514148,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_does_not_require_uncollected_registered_nodeids",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00043187500000385626,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_strict_xpass_fails_when_registered_debt_is_fixed",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12342329199999824,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_strict_xpass_fails_when_registered_debt_is_fixed",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010591699999906723,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_strict_xpass_fails_when_registered_debt_is_fixed",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004130840000016178,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_propagates_debt_registry_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12591391699999122,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_propagates_debt_registry_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013950000000306773,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_pytest_collection_propagates_debt_registry_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011687500000334694,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_save_ledger_writes_test_debt_snapshot_and_machine_block",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00027241699999080993,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_save_ledger_writes_test_debt_snapshot_and_machine_block",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.379099999596292e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_save_ledger_writes_test_debt_snapshot_and_machine_block",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.525000000261571e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_finalize_ledger_update_preserves_test_debt_and_stable_updated_at",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00017966599999397204,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_finalize_ledger_update_preserves_test_debt_and_stable_updated_at",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.929199999674893e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_finalize_ledger_update_preserves_test_debt_and_stable_updated_at",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.808299999898736e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_refresh_auto_fields_preserves_test_debt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001599589999869977,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_refresh_auto_fields_preserves_test_debt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.908400000796064e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_refresh_auto_fields_preserves_test_debt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.054199999676712e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_ordinary_sort_and_save_reject_missing_test_debt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013045900000463462,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_ordinary_sort_and_save_reject_missing_test_debt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.3500000003859896e-05,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_ordinary_sort_and_save_reject_missing_test_debt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8250000002904017e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.962500000260661e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.21250000041573e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5416999995495644e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.066699999645152e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.087499999310239e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.579199999137472e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012091700000382843,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.424999999879219e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.929200001095978e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.4750000003878085e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2583000006525253e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.645799999674182e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.933300000686813e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.166700000178935e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6667000003376415e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.61659999963149e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.462500001205626e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.39170000103195e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.7625000007656126e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9334000004155314e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.537499999595184e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.554099999471873e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.233299999294559e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.233399998871846e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.595800000435247e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6708999999746084e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5207999999897766e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.033300000751751e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0042000005892078e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.641699998979675e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012050000000840555,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.350000000068576e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.499999999689862e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.9667000010013e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.050000000826003e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.479099999978644e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.787500000702494e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4958000000528955e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.629199999646062e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.849999999123611e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.479199999389948e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.237499999566353e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.812500000639375e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.662499999279589e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4834000004480004e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.874999999695319e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9999999995311555e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6249999993742676e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.841700000530636e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0333999987419702e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.354099999341997e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.787500000702494e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1374999991840014e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.625000000795353e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013058399999010817,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2500000003210516e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.620800001158386e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.237499999248939e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9707999999573076e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.37089999931095e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013670900000306574,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1082999996101535e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3625000000370164e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.007980834000008485,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.370799999899646e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.391699999928278e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0175290419999925,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.0707999992359873e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.570899999123412e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003243750000052614,
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
      "duration": 3.62920000043232e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000170791999991593,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.558399998837558e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.129199999169941e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.533299999806786e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.129200000273613e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.737500000511318e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.0874999999450665e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.299999998773728e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.429199999516186e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.93750000032378e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.983399998868208e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7624999990271135e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.920799999614701e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.237500000352611e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.68749999921647e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.387500000291311e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.933300000051986e-05,
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
      "duration": 4.279099999848768e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9290999989939337e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.604200000495439e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.141599999727077e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.09999999927868e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.333400000826714e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.225000000701584e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9875000009838004e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.424999999879219e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.270799999365863e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1750000005104084e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5791000001950124e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00027000000000043656,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.479100000447488e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.399999999942338e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014395799999533665,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2833000005894064e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4458000001791333e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.591700000058154e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.050000000826003e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3208999997546016e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.7458999989989934e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0791999989787655e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.408300000273812e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001447500000040236,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.224999998963085e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.420800000242252e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.929099999628761e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9916999991996818e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.59579999980042e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.9250000003553396e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4708000001160144e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.391599999247319e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013970899999549147,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.541700000653236e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6541000000056556e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.1416999994557955e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0541000000994245e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6541000000056556e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.429199999682169e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1208999999421394e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3291999997686617e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014412500000560158,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.187500000478849e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.2707999991998804e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010629100000869585,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.254099999594473e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.887499999981173e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00018612499999903775,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.041599999027312e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.291699999077082e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015520900001320115,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.845900000953861e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.737500000511318e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.874999999060492e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.945900000383972e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.612499999405827e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.4583000004649875e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.016600000194103e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.683399999156791e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00023849999999470128,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.129199999169941e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1416999994557955e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00017070799999885367,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.1665999987117175e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00033408299999848623,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29720395900000085,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.620900000266829e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032099999999957163,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3109058750000031,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.404099999381742e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037183299998844177,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2980066249999993,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.404099999381742e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003624579999979005,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.30364987499999074,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010283400000332676,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004062499999974989,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2963365419999917,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010941600000080598,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003854170000039403,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2809292079999892,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.345899999857465e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037637500000187174,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.316897124999997,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.170799999935753e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000326541999996266,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2948066659999995,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014287500000875752,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003488330000038786,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2791413750000089,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.133400000393976e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003338329999991174,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27816691600000354,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.966699999428783e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.337500000417549e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004136670000036702,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.354199998601871e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003109590000036633,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.31997908299999267,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.825000000138971e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003307080000070073,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28899308299999404,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.741599999950722e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003717080000029682,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29339866600000164,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.949999999823376e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003627080000114802,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29673808299999394,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.266700000092442e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.879200000118544e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014333299999691462,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.625000000795353e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6582999996426224e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.525000000578984e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.695799999547944e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8791999998011306e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0014737500000023829,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.570799999863539e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.774999998995554e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.716700000059973e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.383400000700476e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.633400000069287e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011475000000871205,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5834000001955246e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.695799999547944e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.754200000282708e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.37080000036849e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.616600000100334e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002576669999996284,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.645900000037727e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.654200000369201e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.05409999963058e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.091700000685705e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.758299999390147e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.570799999394694e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4124999999107786e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.583299999831979e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.008299999393785e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2915999994997946e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.62920000043232e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021399999999971442,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.862500000195723e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.999999999848569e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0015727079999976468,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.8500000005446964e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.420900000923211e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010941249999945057,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.766700000085166e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0458000000853644e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010143749999969032,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.979199999548655e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0957999999591266e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010647910000045613,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.812500000321961e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.845899999532776e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010024169999951482,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6541000000056556e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.687500000637556e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001050374999991277,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.704200000242963e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00015358400000309302,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001245000000011487,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.329200001038316e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001182499999998754,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010993340000027274,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.65420000021777e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011933300000066538,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011067909999979975,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.56249999906322e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011345899999071207,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0017794169999945098,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.4375000007999e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001074169999952801,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011325419999934638,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.449999999664669e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.904200001159097e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001393290999999408,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.1749999994067366e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.70419999898786e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0399505419999997,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.249999999383363e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.950000000458203e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00034629200000324545,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.837499999472584e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.374999999219199e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.495799998949224e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4458000001791333e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.86669999983269e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.175000000827822e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.40420000100039e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9624999999432475e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.958300000306281e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.358299998978964e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.287500000543787e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.387500000291311e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.424999999879219e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7250000005428774e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.94580000033784e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.462500001205626e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9333000003693996e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001158458000006135,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6041999990743534e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.070900000385791e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010354590000076769,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7332999994532656e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.716700000211404e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000994333000008396,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6249999993742676e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9375000000063665e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009930840000009766,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.637499999342708e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.049999999722331e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009840830000058531,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.729200000179844e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0082999987589574e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013528329999985544,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.7917000003394605e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.725000000391447e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.25590333400000986,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.720799999968222e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.045899999662652e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.195800001293719e-05,
      "longrepr": "tests/test_operator_machine_exception_paths.py:45: in test_normalize_skill_level_optional_only_converts_value_error\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/private/tmp/full-pytest-baseline.0ncjIa/wt/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "skipped",
      "when": "call"
    },
    {
      "duration": 0.00011537499999292322,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0916999995820333e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.520799999838346e-05,
      "longrepr": "tests/test_operator_machine_exception_paths.py:54: in test_normalize_skill_level_stored_only_falls_back_for_value_error\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/private/tmp/full-pytest-baseline.0ncjIa/wt/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "skipped",
      "when": "call"
    },
    {
      "duration": 0.00016812500000185082,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.5957999990141616e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001177041999994799,
      "longrepr": "tests/test_operator_machine_exception_paths.py:72: in test_list_by_operator_propagates_unexpected_readside_normalization_errors\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/private/tmp/full-pytest-baseline.0ncjIa/wt/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "skipped",
      "when": "call"
    },
    {
      "duration": 0.00010637500000143518,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.770799999676001e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001532541000003107,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5374999999125976e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000179709000008188,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0015846250000066675,
      "longrepr": "tests/test_operator_machine_exception_paths.py:128: in test_resolve_write_values_only_converts_validation_error\n    assert new_skill is None\nE   AssertionError: assert 'normal' is None",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "skipped",
      "when": "call"
    },
    {
      "duration": 8.462499999950523e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.720799999802239e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00032999999999105967,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.4083000005912254e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3250000004491085e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013370899999642916,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.55000000098471e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7124999991533514e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.416600000922699e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.258399999594985e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7458999997852516e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.312499999225565e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4499999998161e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.591699999105913e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.2458000010014985e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.395799998884286e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8583999995012164e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000519415999988837,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.591699999105913e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.766700000085166e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00020295899999211997,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6041000001318935e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7334000012378965e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002254579999885209,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.454199999453067e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.729200000179844e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015045899999677204,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.037499999919874e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.758299999390147e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00019550000000378986,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.724999999121792e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.620800001158386e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.275000000106502e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6791999988849966e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.824999998717885e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009342909999929816,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.816699998855256e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.39169999914202e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.812500000487944e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.141699999138382e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.341600000008384e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012000000000966793,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.162499999438296e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2834000001666936e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.995900000423717e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.304200000149194e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.537500000230011e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.545800000561485e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9874999998801286e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.595800000435247e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001291659999935746,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.058399998996265e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.270900000198253e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.549999999412194e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.366600001048937e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.954199999611774e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.279200000529727e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.245800000684085e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.637499999342708e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012174999999103875,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.433400000574238e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.812500000321961e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011947079999998778,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.654100000323069e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.49170000031063e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011960829999964062,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.662499999597003e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.741700000783112e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004302249999994956,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.058299999267547e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.154099999695518e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001196332999995775,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.895799999360406e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.129199999804769e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010964589999957752,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5999999997548e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.7042000008777904e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010490840000016988,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5290999992175784e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.950000000609634e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010375829999986763,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5916000004808666e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.058300000053805e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00016758399999616813,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3833999992793906e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.716700000211404e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00026870800000722284,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6332999997057414e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.195799999706651e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014612500000055206,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.424999999879219e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.200000000764703e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003190830000079359,
      "longrepr": "tests/test_query_services.py:163: in test_operator_machine_query_service_lists_with_names_and_linkage_rows\n    assert simple == [\nE   assert [{'dirty_fiel...': 'M2', ...}] == [{'is_primary...: 'beginner'}]\nE     \nE     At index 0 diff: {'operator_id': 'O1', 'machine_id': 'M1', 'skill_level': 'expert', 'is_primary': 'yes', 'dirty_fields': ['skill_level'], 'dirty_reasons': {'skill_level': \"历史技能等级 'high' 已兼容归一为 expert。\"}} != {'operator_id': 'O1', 'machine_id': 'M1', 'skill_level': 'expert', 'is_primary': 'yes'}\nE     Use -v to get more diff",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "skipped",
      "when": "call"
    },
    {
      "duration": 4.795799999612882e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9874999998801286e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00019091599999399023,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.62920000043232e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003260000000011587,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.12902716700000383,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012587499999483498,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_nodeid_and_runner_file_are_not_collected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00041766699999357115,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.0909737079999928,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00018041699999571392,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_exit_contract_and_failure_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005202499999938937,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.16213208299998882,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001226669999994101,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_main_style_subprocess_pollution_is_isolated",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2875000008612005e-05,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.8638416249999921,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.300000000360797e-05,
      "longrepr": "",
      "nodeid": "tests/test_regression_main_isolation_contract.py::test_runner_script_exists_and_is_not_main_style_collected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.9290999999461746e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.954199999777757e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.424999999879219e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.958400000669826e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005454709000005664,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.458299999361316e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00041008300000555664,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0019962500000048067,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.950000000609634e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002727909999862277,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0020743329999959315,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.212500001050557e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002475409999931344,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2712300409999955,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012279100000966992,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00041949999999246756,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27041437500000143,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015000000000497948,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005919999999974834,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2727369159999995,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001498330000089254,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005339589999948657,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27776779100000226,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001352499999995871,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00045508400000926486,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.018734125000008817,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010066699999811135,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.533299999489373e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014224999999612464,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.170900000133315e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.24999999921738e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.56249999906322e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.487499999721422e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004826250000036225,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2945072499999952,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012720799999499377,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00045687499999758074,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1481024590000004,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013837499999169722,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00041995899999847097,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2969988330000035,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012158400001283098,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004407499999956599,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.296106457999997,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001271659999986241,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00043779199999960383,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5984179579999989,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012300000000209366,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040675000001044737,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28151250000000516,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001435839999999189,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004409999999950287,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26925812500000745,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010054100000900235,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004951669999968544,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2689955000000026,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011933300000066538,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.5165999995665516e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002430000000003929,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.916700000023866e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5124999999757165e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_shared_quality_registry_does_not_split_quality_gate_error_identity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001379589999999098,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_shared_quality_registry_does_not_split_quality_gate_error_identity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.320800000494728e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_shared_quality_registry_does_not_split_quality_gate_error_identity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.0166000006775e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0029254170000001523,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.912500000704313e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001216250000055652,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.022710291000009875,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.529099999383561e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039612499999464035,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.025060666000001675,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014050000000054297,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6042000008128525e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002593250000003877,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.145799999832889e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9666999995802144e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000519124999996734,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.6166999993602076e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00033924999999612737,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.17828837500000816,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0002355830000055903,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00015191600000719063,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0030219169999980977,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.53340000095659e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.42500000083146e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002696999999997729,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.512500000610544e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00041716699999483353,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.009643207999999959,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.15000000073951e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.904200000055425e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3152412080000033,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.470899999541871e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005037499999929196,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.026582083999997508,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012599999999451938,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004234999999965794,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.024417958000000795,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001221670000006725,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004448749999994561,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.053032833000003166,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00017679200000486617,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000538125000005607,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.029580540999987193,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016616700000327,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004823340000115195,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.033877375000002985,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00014554200001271056,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.7834000003254005e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0029909590000016806,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015966700000547007,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0010454170000002705,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03101216700000009,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001550830000098813,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0009446669999988444,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1087031670000016,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001732500000031223,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.895799999995234e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00016616699998905915,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00019000000000346517,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001052920000006452,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000969707999999514,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001587499999970987,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00020941600000412564,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010387500000774708,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.412500000228192e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2541000002293003e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006785420000028353,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.7749999996303814e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7665999986179486e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00017016600000374638,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.01249999981701e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.333299999359497e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001902909999955682,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.916599999342907e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.074999999659212e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014399999999170632,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.920800000400959e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.366699999991397e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015412499999456486,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00017187500000659384,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00043233299999201336,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0024114170000046897,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00031195799999750307,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00027283400000044367,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0029894579999876214,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00020270900000696201,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00027916599999855407,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021387500000003,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00018962500000441196,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.599999999920783e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007728749999955653,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.283300000120562e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00021866699999861794,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007951249999962329,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001817090000031385,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011816700001077152,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004036833000000684,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.083400001306472e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.875000000798991e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.891699999935554e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.574999999817919e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.011146874999994338,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6831865419999872,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.079099999098617e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003913749999924221,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.49945679100000007,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.558300000061081e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039520800000047984,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.45150816700000007,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.820899999761878e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005638330000010683,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.48170837499999664,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.366699999839966e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037129199999696993,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.43405120799999963,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00017037499999617012,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039137500000663294,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.41173599999999055,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.887499998877502e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003614590000040607,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4339387499999958,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.191700000281799e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003817919999988817,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4108222499999954,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.237499999414922e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9000000004184585e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.945899999446283e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8833000004956375e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2082999996750914e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.341600000325798e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.47090000047956e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0027664160000000493,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0016522499999922502,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010749999999859483,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.545900000607617e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.7667000004025795e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.741700000148285e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.279200000212313e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.845800000121471e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7374999990902324e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.229200000338551e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.249999999852207e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6249999993742676e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1749999994067366e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.791700000656874e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.83329999920079e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.58330000078422e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.020592500000006453,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.799999999884676e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.449999999664669e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01841054199999803,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.116599999790196e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.858300000407326e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01833337499999743,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.654200000535184e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.145800001102543e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01770333400000368,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.02499999963402e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.854200000030232e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.018810624999986203,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.016700000406217e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.000000000165983e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004686165999999048,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5374999999125976e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.433299999107021e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.570800000346935e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.612499999405827e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.216600000641392e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010238750000013397,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.7582999997075603e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.516699999612683e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001067500000004884,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6917000002745226e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.01249999981701e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015900000001067838,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7082999995163846e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.366600001048937e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00031387500000334967,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.770799999676001e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.54170000097065e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010354200000506353,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.78750000038508e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040212499999370266,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5673578330000026,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.92909999947733e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9415999995972015e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008386669999964624,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.925000000037926e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.941599999279788e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003028750000027003,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.6958999988078176e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.262500000606906e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.687500000168711e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2415999996260325e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.662499999279589e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.495799999584051e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2000000004472895e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.579199999137472e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.587500000421187e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2500000003210516e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.562499999532065e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010205829999989646,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.358300000717463e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.425000000196633e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0016159170000094036,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.529199999581124e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.304200000149194e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.37500000017144e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4834000004480004e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.970800000274721e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012850000000241835,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.262499998868407e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.562499999532065e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.474653124999989,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.912500000704313e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6292000007497336e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.013935333000006267,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.337500000734963e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.624999999691681e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.6529511250000013,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.216699999115008e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.520800000942018e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.19427670799998964,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.958400000835809e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.283400000484107e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0189330830000074,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011270800000318104,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.6792000009409094e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7208151250000014,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.670799999777046e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.033300000751751e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003335000000106447,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.395800000622785e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0006331249999931288,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004143457999987277,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.6792000009409094e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003077920000009726,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004024999999927559,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5624999998494786e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.758399999753692e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002386749999999438,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.991699999834509e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.549999999881038e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013748329999998532,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00048508399999036556,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.6790999991562785e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013733330000036403,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.704200000560377e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.420800000559666e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000993833999999083,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.783299999327028e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00014025000000117416,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005225916000000552,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.541700000501805e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00013433299999121573,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0038984579999947755,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.862500000044292e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00012483400000462552,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0044730839999971295,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010058300000537201,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00014154199999438788,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004347291999991398,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.504200000596484e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.458299999209885e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004005792000000952,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.004100000074232e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.108300000562394e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003229590000017879,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.420800000559666e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.583299999045721e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00024233300000275904,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.8500000005446964e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.804099999792925e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004089833999998405,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.395900000200072e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.86669999983269e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00461083300000098,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.6292000007497336e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011929100000429571,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004164083000006258,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.97089999906575e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.770900000205529e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003754834000005758,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.120800000530835e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00036629199999538287,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_imports_seed_entries",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005549292000011974,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_imports_seed_entries",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.570800000029521e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_imports_seed_entries",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004169169999954647,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update0-schema_version]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004636500000003707,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update0-schema_version]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.654099999854225e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update0-schema_version]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003531670000000986,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update1-schema_version]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004172334000003275,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update1-schema_version]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.679200000154651e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update1-schema_version]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003816250000028276,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update2-baseline_kind]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004950875000005794,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update2-baseline_kind]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.620800000220697e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update2-baseline_kind]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00043204199999991033,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update3-importable]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0044057920000000195,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update3-importable]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.445800000027702e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update3-importable]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003832499999987249,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update4-importable]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004489250000005995,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update4-importable]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.920800000249528e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update4-importable]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039658400000064375,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update5-importable]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004400791999998432,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update5-importable]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.400000001211993e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update5-importable]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005626250000005939,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update6-pytest_exitstatus]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02379658300000642,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update6-pytest_exitstatus]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.129199999335924e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_invalid_baseline[payload_update6-pytest_exitstatus]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004385000000013406,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-schema_version]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0045949590000020635,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-schema_version]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.862500000361706e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-schema_version]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040329200000144283,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-classifications]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004848166999991577,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-classifications]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.970799999019619e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-classifications]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040504200001123536,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt0]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004387207999997145,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt0]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.349999998813473e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt0]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003557090000043672,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt1]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004464000000012902,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt1]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.895799998891562e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-candidate_test_debt1]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003785419999928763,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-failed_nodeid_count]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.007408999999995558,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-failed_nodeid_count]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.608399999194717e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-failed_nodeid_count]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00044499999999914053,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collected_nodeids]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0051896249999998645,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collected_nodeids]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.070800000188228e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collected_nodeids]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00041020800000524105,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collection_errors]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004384917000010091,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collection_errors]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.445800000027702e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-collection_errors]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003682920000045442,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-reports]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.006230083000005493,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-reports]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.304199998894092e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-reports]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004254579999951602,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-worktree_clean_before]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0044727499999908105,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-worktree_clean_before]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.312500000011823e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_malformed_machine_contract[<lambda>-worktree_clean_before]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000337707999989334,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004611624999995456,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.170799999618339e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_blocked_classifications",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000423709000003214,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-required_or_quality_gate_self_failure]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005389082999997186,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-required_or_quality_gate_self_failure]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.925000000203909e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-required_or_quality_gate_self_failure]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004288749999972197,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-main_style_isolation_candidate]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004599791000003961,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-main_style_isolation_candidate]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.670900000140591e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-main_style_isolation_candidate]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00039445799998816256,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-collection_error_count]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004418041999997513,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-collection_error_count]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.737500000359887e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero[<lambda>-collection_error_count]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004157500000019354,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_unknown_candidate_nodeid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005511999999995965,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_unknown_candidate_nodeid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.566700001073514e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_unknown_candidate_nodeid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004919999999941638,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_empty_candidate_nodeid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004652832999994416,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_empty_candidate_nodeid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.625000000643922e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_empty_candidate_nodeid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035150000000783166,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_current_dry_run_candidate_drift",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0042825840000091375,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_current_dry_run_candidate_drift",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.070799999553401e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_rejects_current_dry_run_candidate_drift",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003872500000028367,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_does_not_overwrite_existing_test_debt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.006079166000006353,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_does_not_overwrite_existing_test_debt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.516699999461252e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_test_debt_baseline_command_does_not_overwrite_existing_test_debt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001126249999998663,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[owner--owner]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0027990420000065797,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[owner--owner]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.379200000277251e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[owner--owner]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.241700000472974e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[style-untriaged-untriaged]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002410041000004526,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[style-untriaged-untriaged]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.4584000011459466e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_empty_and_untriaged_fields[style-untriaged-untriaged]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.812499999535703e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_duplicate_debt_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0027760420000078057,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_duplicate_debt_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.766600000039034e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_import_seed_metadata_rejects_duplicate_debt_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.02499999978545e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003235830000107853,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.429199999516186e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.529099998900165e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014449999999044394,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.633400000069287e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.408299998852726e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012562500000967702,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2541999999580185e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003378749999995989,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.652510250000006,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012087499999324791,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00021579200000587662,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008232499999962783,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.279200000529727e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3708000010033174e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00038437499999588454,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.999999999848569e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.037499999753891e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004711250000042355,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.916699999706452e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.70419999898786e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005902919999982714,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.870799999423525e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.141699999773209e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000415625000002251,
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
      "duration": 5.804199999204229e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004085839999987684,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.504199999644243e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.0541999999941254e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00040404199999954926,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.524999999944157e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.941699999643333e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.195799999706651e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.399999999942338e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.891600000827111e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00040458399999465655,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7082999995163846e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1584000001648747e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004250420000033728,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.758299999390147e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.916600000763992e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00033849999999802094,
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
      "duration": 3.7792000000536063e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00041533299999230167,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.737500000511318e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.458400000042275e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004691670000056547,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.4207999991385805e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.891599999406026e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00033675000000243926,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.70839999987993e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.783399999690573e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00030304199999875436,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.654200000369201e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.937500000641194e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003086250000023938,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.304099999785649e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.65830000027745e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008517920000059576,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.6208000000547145e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8291999999273685e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007008339999998725,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.929199999674893e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00040041600000506605,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012416249999915863,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.2999999994085556e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.870799999740939e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004412090000016633,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.495799998949224e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.141700000559467e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.004199998699278e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.570799999863539e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003315830000047981,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004994159999966996,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.10410000013917e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00043558299999801875,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0038643329999956677,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.53749999912634e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037283300000012787,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0034068750000102455,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.9624999991569894e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034183399999676567,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003514584000001264,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.8125000009567884e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003379169999959686,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01206287499999803,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.491700000628043e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.020900000360598e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0037376249999994116,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.6333000003405687e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003822089999943046,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003728917000003662,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.387499999822467e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00038837499999999636,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003618541999998115,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.537500000230011e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003355420000019649,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 12.212004000000007,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0003703340000100752,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0010943749999938746,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.008344665999999279,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013995800000543568,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0006865839999932177,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.010052916999995887,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.441699999968023e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004975419999908581,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005402000000003682,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.066700000914807e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000103165999988164,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.006208125000000564,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010670900000775418,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.9874999990938704e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005017499999979691,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.8625000008305506e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.362500000671844e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000213540999993711,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.4707999990123426e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9959000008925614e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00022450000000162618,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.250000000638465e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.899999998997373e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00039950000000033015,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.262500000606906e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.645900000355141e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001255829999990965,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.108299999927567e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.716699999107732e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003417079999934458,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.137499999501415e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.458299999043902e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014558299999123392,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.187499999375177e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.504100000701783e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000358125000005316,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.10419999923306e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.8167000002763416e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003850829999976213,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.233399999975518e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.533299998854545e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012970800000289273,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.087499999627653e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.333299999359497e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010737499999891043,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.100000001017179e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7125000008918505e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003663749999986976,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.349999998964904e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.787500000702494e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011150000000270666,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.270900000515667e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9165999996603205e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.654100000171638e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.066599998964193e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.812499999218289e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.820899999444464e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.925000000037926e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3915999995647326e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.704199999456705e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.591700000526998e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9375000000063665e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.629199999177217e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.679200000306082e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.320799999391056e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.720799999968222e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0006007909999965477,
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
