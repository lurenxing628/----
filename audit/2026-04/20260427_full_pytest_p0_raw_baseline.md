# Full pytest P0 raw baseline

本文件记录 main-style 子进程隔离前的 full pytest 现场，只用于排查和对比。

- baseline_kind: `raw_before_isolation`
- importable: `false`
- exitstatus: `1`
- collected_count: `578`
- failed_nodeid_count: `36`

<!-- APS-FULL-PYTEST-BASELINE:BEGIN -->
```json
{
  "baseline_kind": "raw_before_isolation",
  "classifications": {
    "candidate_test_debt": [
      "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows"
    ],
    "main_style_isolation_candidate": [
      "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke"
    ],
    "required_or_quality_gate_self_failure": [
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects"
    ]
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
  "generated_at": "2026-04-27T01:07:17+08:00",
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
      "duration": 0.0001842919999999748,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021891699999998515,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.808399999999379e-05,
      "longrepr": "",
      "nodeid": "tests/regression/regression_collection_contract.py::regression_collection_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6666999999990235e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.37129504099999994,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.3917000000014426e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_db_path_no_dirname.py::regression_app_db_path_no_dirname",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.16250000000451e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.349848209,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.9374999999972644e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_secret_key_runtime_ensure.py::regression_app_new_ui_secret_key_runtime_ensure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.458400000006968e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3984741249999999,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.579199999994344e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_security_hardening_enabled.py::regression_app_new_ui_security_hardening_enabled",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.262499999985181e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3671699580000001,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.97090000000744e-05,
      "longrepr": "",
      "nodeid": "tests/regression_app_new_ui_session_contract.py::regression_app_new_ui_session_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.22919999998328e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001884541999999989,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.979199999992744e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_empty_resource_pool.py::regression_auto_assign_empty_resource_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0124999999946453e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005945830000000374,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6249999999959925e-05,
      "longrepr": "",
      "nodeid": "tests/regression_auto_assign_fixed_operator_respects_op_type.py::regression_auto_assign_fixed_operator_respects_op_type",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.958299999995418e-05,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002928291999999999,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.345900000002345e-05,
      "longrepr": "",
      "nodeid": "tests/regression_backup_restore_pending_verify_code.py::regression_backup_restore_pending_verify_code",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.083299999990686e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.262240625,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.3749999999741505e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_detail_linkage.py::regression_batch_detail_linkage",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2792000000346775e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002182166999999957,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.183300000004664e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py::regression_batch_excel_import_strict_mode_hardfail_atomic",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.312500000036579e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26802575000000006,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.366699999997948e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py::regression_batch_excel_preview_confirm_strict_mode_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.495900000023312e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00032466700000011173,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.662499999990132e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_import_unchanged_no_rebuild.py::regression_batch_import_unchanged_no_rebuild",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.82080000003171e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006032089999998824,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.55839999999219e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_bid_unboundlocal.py::regression_batch_order_bid_unboundlocal",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7292000000022085e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004023749999997328,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.508299999976927e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_order_override_dedup.py::regression_batch_order_override_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.929099999977481e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013357080000000465,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.604200000006941e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_service_strict_mode_template_autoparse.py::regression_batch_service_strict_mode_template_autoparse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.658299999997894e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0014379589999999887,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.612500000027552e-05,
      "longrepr": "",
      "nodeid": "tests/regression_batch_template_autobuild_same_tx.py::regression_batch_template_autobuild_same_tx",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6750000000029814e-05,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00023312499999983416,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.354199999971996e-05,
      "longrepr": "",
      "nodeid": "tests/regression_build_outcome_contract.py::regression_build_outcome_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8624999999736787e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.30981279100000014,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.0040999999788625e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_export_normalization.py::regression_calendar_export_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6959000000068585e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004062958000000005,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.81250000001765e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_no_tx_hardening.py::regression_calendar_no_tx_hardening",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.237500000003891e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26620979200000017,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.174999999990604e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_pages_readside_normalization.py::regression_calendar_pages_readside_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1750000000284615e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004165167000000025,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.6457999999915955e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_hours_roundtrip.py::regression_calendar_shift_hours_roundtrip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.312500000036579e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0016873340000000958,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.900000000018778e-05,
      "longrepr": "",
      "nodeid": "tests/regression_calendar_shift_start_rollover.py::regression_calendar_shift_start_rollover",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4291999999668263e-05,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.0211346669999997,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0002482499999998389,
      "longrepr": "",
      "nodeid": "tests/regression_check_manual_layout_runtime_resolution.py::regression_check_manual_layout_runtime_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003994579999999637,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0017153749999998524,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00019087499999992374,
      "longrepr": "",
      "nodeid": "tests/regression_common_broad_false_fixed.py::regression_common_broad_false_fixed",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001976670000001235,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0016042080000002734,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00012662500000004684,
      "longrepr": "",
      "nodeid": "tests/regression_compat_parse_emits_degradation.py::regression_compat_parse_emits_degradation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011925000000001518,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.49772166699999953,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.5041999999616564e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_manual_markdown.py::regression_config_manual_markdown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2500000000167404e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006907920000003287,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.712499999952712e-05,
      "longrepr": "",
      "nodeid": "tests/regression_config_snapshot_strict_numeric.py::regression_config_snapshot_strict_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.691700000008069e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.25796341599999995,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.879199999991869e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dashboard_overdue_count_tolerance.py::regression_dashboard_overdue_count_tolerance",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.483300000046597e-05,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00029308300000074894,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.579199999936833e-05,
      "longrepr": "",
      "nodeid": "tests/regression_degradation_collector_merge_counts.py::regression_degradation_collector_merge_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.954200000055863e-05,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002314580000000177,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.475000000019435e-05,
      "longrepr": "",
      "nodeid": "tests/regression_deletion_validator_source_case_insensitive.py::regression_deletion_validator_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6458999999489095e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0025595840000001147,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.825000000023948e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dict_cfg_contract.py::regression_dict_cfg_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8625000000180876e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006577920000001569,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5957999999780554e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_blocking_consistency.py::regression_dispatch_blocking_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9666000000160295e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00020383400000056895,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.424999999968037e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rule_case_insensitive.py::regression_dispatch_rule_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6209000000120284e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021370799999953505,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4165999999835606e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py::regression_dispatch_rules_nonfinite_proc_hours_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6041000000430756e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021704200000005613,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.375000000005457e-05,
      "longrepr": "",
      "nodeid": "tests/regression_dispatch_rules_priority_case_insensitive.py::regression_dispatch_rules_priority_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.795800000006011e-05,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00019487500000003877,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.28749999995992e-05,
      "longrepr": "",
      "nodeid": "tests/regression_downtime_overlap_skips_invalid_segments.py::regression_downtime_overlap_skips_invalid_segments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.56670000005721e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011005420000005373,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.524999999982015e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_consistency.py::regression_due_exclusive_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.720900000026006e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00019995800000049968,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3375000000113175e-05,
      "longrepr": "",
      "nodeid": "tests/regression_due_exclusive_guard_contract.py::regression_due_exclusive_guard_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8125000000555076e-05,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00048170800000058023,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.483299999995637e-05,
      "longrepr": "",
      "nodeid": "tests/regression_efficiency_greater_than_one_shortens_hours.py::regression_efficiency_greater_than_one_shortens_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.612499999938734e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.035847666000000444,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.304199999933701e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ensure_schema_fastforward_empty_only.py::regression_ensure_schema_fastforward_empty_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.275000000042439e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2679310829999997,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.279099999988546e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_demo_upload_guard.py::regression_excel_demo_upload_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.7792000000157486e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005183959000000016,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5959000000372896e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_failure_semantics_contracts.py::regression_excel_failure_semantics_contracts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2541000000007045e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00042100000000022675,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.591599999985817e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_executor_status_gate.py::regression_excel_import_executor_status_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9332999999253104e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5668144159999997,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.979199999917029e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_result_semantics.py::regression_excel_import_result_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2749999999536215e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004219582999999361,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.6959000000512674e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_import_strict_reference_apply.py::regression_excel_import_strict_reference_apply",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.241600000032264e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004973750000001331,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.24169999995172e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_normalizers_mixed_case.py::regression_excel_normalizers_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.104199999943603e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0014277910000002336,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.641700000045489e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_operator_calendar_cross_midnight.py::regression_excel_operator_calendar_cross_midnight",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.745800000043431e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.31469116699999944,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.5875000000149555e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_baseline_guard.py::regression_excel_preview_confirm_baseline_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4625000000131365e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.331771625,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.470800000040299e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_preview_confirm_extra_state_guard.py::regression_excel_preview_confirm_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1208999999930995e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003913339999996879,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.658400000006168e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_routes_no_tx_surface_hidden.py::regression_excel_routes_no_tx_surface_hidden",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.520899999960193e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003020840000003133,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.541700000031511e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_service_calc_changes_row.py::regression_excel_service_calc_changes_row",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8082999999744516e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0025839580000006634,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.245800000024502e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_source_row_num_preserved.py::regression_excel_source_row_num_preserved",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0165999999786095e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002521249999993813,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.433300000033057e-05,
      "longrepr": "",
      "nodeid": "tests/regression_excel_validators_yesno_mixed_case.py::regression_excel_validators_yesno_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.670799999966334e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0036040829999999247,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.058300000015947e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_maintenance.py::regression_exit_backup_maintenance",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.391700000017096e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002678749999995844,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.583300000009615e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_reloader_parent_skip.py::regression_exit_backup_reloader_parent_skip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.645800000029453e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00447529199999952,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.0166999999868835e-05,
      "longrepr": "",
      "nodeid": "tests/regression_exit_backup_respects_config.py::regression_exit_backup_respects_config",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.950000000063625e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0018038329999994218,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.845799999968591e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_compatible_mode_logs_fallback.py::regression_external_group_service_compatible_mode_logs_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.874999999986528e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012072920000001375,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.641699999956671e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_merge_mode_case_insensitive.py::regression_external_group_service_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.691700000008069e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011778329999998505,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.579199999936833e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_group_service_strict_mode_blank_days.py::regression_external_group_service_strict_mode_blank_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.662499999990132e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00038229200000028385,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.562500000064972e-05,
      "longrepr": "",
      "nodeid": "tests/regression_external_merge_mode_case_insensitive.py::regression_external_merge_mode_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2249999999910415e-05,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.01123508399999995,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.925000000000068e-05,
      "longrepr": "",
      "nodeid": "tests/regression_freeze_window_bounds.py::regression_freeze_window_bounds",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.216700000014839e-05,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006920829999996769,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5750000000334126e-05,
      "longrepr": "",
      "nodeid": "tests/regression_frontend_common_interactions.py::regression_frontend_common_interactions",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.645900000037727e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.40474049999999995,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.316699999990959e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_calendar_load_failed_degraded.py::regression_gantt_calendar_load_failed_degraded",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.245800000024502e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.235846542,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.816599999963756e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_contract_snapshot.py::regression_gantt_contract_snapshot",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.450000000044696e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.11155458300000021,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.858300000001094e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_critical_chain_cache_thread_safe.py::regression_gantt_critical_chain_cache_thread_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.424999999994242e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27151841699999935,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.079199999968864e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_offset_range_consistency.py::regression_gantt_offset_range_consistency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.166699999963441e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.023220999999999492,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.641700000071694e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_status_mode_semantics.py::regression_gantt_status_mode_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.612499999989694e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26649491700000016,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.995800000047069e-05,
      "longrepr": "",
      "nodeid": "tests/regression_gantt_url_persistence.py::regression_gantt_url_persistence",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5375000000014154e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003367919999996971,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5459000000237495e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_date_parsers.py::regression_greedy_date_parsers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.775000000061368e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005654170000006786,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9124999999806676e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_auto_assign.py::regression_greedy_scheduler_algo_stats_auto_assign",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1416999999377424e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000524083000000175,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7290999999939345e-05,
      "longrepr": "",
      "nodeid": "tests/regression_greedy_scheduler_algo_stats_seed_counts.py::regression_greedy_scheduler_algo_stats_seed_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.629199999988231e-05,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003060420000000619,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.462500000050994e-05,
      "longrepr": "",
      "nodeid": "tests/regression_import_execution_stats_source_row_num.py::regression_import_execution_stats_source_row_num",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.245800000024502e-05,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0014823330000002244,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.795799999917193e-05,
      "longrepr": "",
      "nodeid": "tests/regression_improve_dispatch_modes.py::regression_improve_dispatch_modes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.820900000039984e-05,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2807310000000003,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.7958000000191134e-05,
      "longrepr": "",
      "nodeid": "tests/regression_lazy_select_orphan_option.py::regression_lazy_select_orphan_option",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2791000000264034e-05,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009670000000001622,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.766699999996348e-05,
      "longrepr": "",
      "nodeid": "tests/regression_legacy_external_days_defaulted_visible.py::regression_legacy_external_days_defaulted_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.854100000033611e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004797791999999745,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.45410000002866e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_jobstate_retry_signal.py::regression_maintenance_jobstate_retry_signal",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.379100000040381e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004640458999999986,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.150000000053723e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_real_oplog_visibility.py::regression_maintenance_real_oplog_visibility",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3875000000248576e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005318916000000229,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.4625000000131365e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_telemetry_isolation.py::regression_maintenance_telemetry_isolation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.054099999972749e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.022778125000000315,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.204200000008541e-05,
      "longrepr": "",
      "nodeid": "tests/regression_maintenance_window_mutex.py::regression_maintenance_window_mutex",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.295799999987082e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00030729199999957046,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.645900000037727e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_horizon_semantics.py::regression_metrics_horizon_semantics",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.691599999999795e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000224250000000481,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7834000000458445e-05,
      "longrepr": "",
      "nodeid": "tests/regression_metrics_to_dict_nonfinite_safe.py::regression_metrics_to_dict_nonfinite_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.766699999996348e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02023520800000078,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.529100000016939e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_backup_dir_none_creates_backup.py::regression_migrate_backup_dir_none_creates_backup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.87079999999429e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02831291700000005,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0667000000004236e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v2_unify_workcalendar_day_type.py::regression_migrate_v2_unify_workcalendar_day_type",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.187499999908084e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03089541699999998,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5417000000824714e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v4_sanitize_enum_text_fields.py::regression_migrate_v4_sanitize_enum_text_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0250000001407216e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.028674917000000022,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.3041000001030625e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migrate_v5_normalize_operator_machine_legacy_values.py::regression_migrate_v5_normalize_operator_machine_legacy_values",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.308299999955523e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0074408339999987305,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.579199999987793e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_failfast_no_backup_storm.py::regression_migration_failfast_no_backup_storm",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5457999998888e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004628792000000104,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.754200000003152e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_partial_no_upgrade.py::regression_migration_outcome_partial_no_upgrade",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2583000000817606e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03066708399999918,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.7542000000788676e-05,
      "longrepr": "",
      "nodeid": "tests/regression_migration_outcome_skip_no_upgrade.py::regression_migration_outcome_skip_no_upgrade",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.054199999892205e-05,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003584159999991954,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.608299999946496e-05,
      "longrepr": "",
      "nodeid": "tests/regression_model_enums_case_insensitive.py::regression_model_enums_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.762499999915292e-05,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003610829999995957,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9041999999156474e-05,
      "longrepr": "",
      "nodeid": "tests/regression_models_numeric_parse_hybrid_safe.py::regression_models_numeric_parse_hybrid_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7084000000575656e-05,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000267499999999643,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.420799999886981e-05,
      "longrepr": "",
      "nodeid": "tests/regression_normalization_matrix_single_source.py::regression_normalization_matrix_single_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5458999999349317e-05,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021229199999872606,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.445800000001498e-05,
      "longrepr": "",
      "nodeid": "tests/regression_number_utils_facade_delegates_strict_parse.py::regression_number_utils_facade_delegates_strict_parse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.504199999859736e-05,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0018178330000004905,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.308299999955523e-05,
      "longrepr": "",
      "nodeid": "tests/regression_objective_case_normalization.py::regression_objective_case_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.891699999947207e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003949290999999633,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.320799999923963e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_calendar_override_allows_work_on_global_holiday.py::regression_operator_calendar_override_allows_work_on_global_holiday",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3249999999162014e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27582612500000003,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.245800000075462e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_detail_readside_normalization.py::regression_operator_machine_detail_readside_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.162499999971203e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2611413339999995,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.316600000071503e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_dirty_flags_visible.py::regression_operator_machine_dirty_flags_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2041000000381246e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.024388708000000037,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.0125000000965656e-05,
      "longrepr": "",
      "nodeid": "tests/regression_operator_machine_missing_columns.py::regression_operator_machine_missing_columns",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.533400000106269e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000781124999999605,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.762499999915292e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_choice_case_normalization.py::regression_optimizer_choice_case_normalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8083999999827256e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003067458999998607,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.679200000090589e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_ortools_logging_exc_info_safe.py::regression_optimizer_ortools_logging_exc_info_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.250000000105558e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006914589999986731,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.799999999998249e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_outcome_algo_stats.py::regression_optimizer_outcome_algo_stats",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.554099999865002e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007664580000010801,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5500000000965315e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optimizer_zero_weight_cfg_preserved.py::regression_optimizer_zero_weight_cfg_preserved",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6292000000770486e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.008104624999999643,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.7999999999603915e-05,
      "longrepr": "",
      "nodeid": "tests/regression_optional_ready_constraint.py::regression_optional_ready_constraint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.079099999998448e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008578749999994528,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.72500000000997e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_budget_guard_skip_when_no_time.py::regression_ortools_budget_guard_skip_when_no_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.775000000061368e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00023791699999975435,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.716700000033768e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_priority_weight_contract.py::regression_ortools_priority_weight_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.787500000029809e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000303582999999108,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3666000000209806e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ortools_warmstart_skip_nonfinite.py::regression_ortools_warmstart_skip_nonfinite",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.533300000135853e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00025579199999903324,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.324999999954059e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_operation_hours_service_stats_gate.py::regression_part_operation_hours_service_stats_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5207999999897766e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011615830000000216,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.766700000085166e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_create_strict_mode_atomic.py::regression_part_service_create_strict_mode_atomic",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.958300000128645e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001077374999999492,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.391699999966136e-05,
      "longrepr": "",
      "nodeid": "tests/regression_part_service_external_default_days_fallback.py::regression_part_service_external_default_days_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5750000000334126e-05,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27817416699999953,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.3541999999850987e-05,
      "longrepr": "",
      "nodeid": "tests/regression_personnel_excel_links_header_aliases.py::regression_personnel_excel_links_header_aliases",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.208300000030363e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009674159999999432,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7499999999468514e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_injects_config_reader.py::regression_plugin_bootstrap_injects_config_reader",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.891699999947207e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003425916999999501,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.3917000001059137e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_bootstrap_telemetry_failure_visible.py::regression_plugin_bootstrap_telemetry_failure_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.22919999998328e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006670839999998179,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5500000000965315e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_capability_conflict_visible.py::regression_plugin_capability_conflict_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.850000000049647e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006091250000004322,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.558399999903372e-05,
      "longrepr": "",
      "nodeid": "tests/regression_plugin_manager_error_trace_visible.py::regression_plugin_manager_error_trace_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5416999999426935e-05,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00023383300000112683,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.46670000013205e-05,
      "longrepr": "",
      "nodeid": "tests/regression_priority_weight_case_insensitive.py::regression_priority_weight_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.662499999990132e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2987012500000006,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.183300000055624e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py::regression_process_excel_part_operation_hours_append_fill_empty_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.133399999872722e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3084714589999997,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.7667000000094504e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_import.py::regression_process_excel_part_operation_hours_import",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.329100000077801e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28601712500000076,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.7209000001279264e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_part_operation_hours_source_row_num.py::regression_process_excel_part_operation_hours_source_row_num",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.24580000011332e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29619474999999973,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.895900000041365e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_excel_routes_extra_state_guard.py::regression_process_excel_routes_extra_state_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.308299999955523e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.29949154200000017,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.783399999970129e-05,
      "longrepr": "",
      "nodeid": "tests/regression_process_reparse_preserve_internal_hours.py::regression_process_reparse_preserve_internal_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2499999999279225e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.22864491699999867,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.283299999980784e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_large_scope_rejects_need_async.py::regression_report_export_large_scope_rejects_need_async",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.154199999995001e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.234822458,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.837500000005491e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_export_size_mode_selection.py::regression_report_export_size_mode_selection",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.354100000014682e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00036029199999987327,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.720800000017732e-05,
      "longrepr": "",
      "nodeid": "tests/regression_report_source_case_insensitive.py::regression_report_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00017599999999973193,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.28039345799999893,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.304199999933701e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_default_range_from_version_span.py::regression_reports_default_range_from_version_span",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3542000000229564e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26063691600000105,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.96249999990539e-05,
      "longrepr": "",
      "nodeid": "tests/regression_reports_export_version_default_latest.py::regression_reports_export_version_default_latest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.341600000046242e-05,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27627966699999895,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.841699999997729e-05,
      "longrepr": "",
      "nodeid": "tests/regression_restore_success_condition.py::regression_restore_success_condition",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4083000000583183e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006925829999993027,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.775000000061368e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_missing_supplier_warning.py::regression_route_parser_missing_supplier_warning",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.979099999895652e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00040033299999997496,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.624999999907175e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_op_type_category_case_insensitive.py::regression_route_parser_op_type_category_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.70839999987993e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00038499999999963563,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.479100000092217e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_preserve_errors_when_no_matches.py::regression_route_parser_preserve_errors_when_no_matches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.633300000061013e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006062500000005855,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.46670000013205e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py::regression_route_parser_strict_mode_rejects_supplier_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.895799999931171e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006921660000003271,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.512500000013574e-05,
      "longrepr": "",
      "nodeid": "tests/regression_route_parser_supplier_default_days_zero_trace.py::regression_route_parser_supplier_default_days_zero_trace",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.154099999986727e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0016112919999997644,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8083999999827256e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_contract_launcher.py::regression_runtime_contract_launcher",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.874999999986528e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.371274915999999,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.0249999998873704e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_lock_reloader_parent_skip.py::regression_runtime_lock_reloader_parent_skip",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2499999999279225e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.0200636250000006,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0003077499999992739,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_probe_resolution.py::regression_runtime_probe_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0006224589999987984,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 1.5987414169999994,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.425000000045202e-05,
      "longrepr": "",
      "nodeid": "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.949999999936949e-05,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3733597090000007,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.3541999999850987e-05,
      "longrepr": "",
      "nodeid": "tests/regression_safe_next_url_hardening.py::regression_safe_next_url_hardening",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2707999998725654e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.021000499999999533,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.3250000000559794e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sanitize_batch_dates_single_digit.py::regression_sanitize_batch_dates_single_digit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4499999997782425e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002250333999999299,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.545800000244071e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_history_not_created_for_empty_schedule.py::regression_schedule_history_not_created_for_empty_schedule",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0915999999668884e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005265829999991922,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.054200000031983e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_builder_safe_float_parse.py::regression_schedule_input_builder_safe_float_parse",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9290999999840324e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001156874999999502,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.695799999865358e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_input_collector_contract.py::regression_schedule_input_collector_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.075000000014484e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000878792000001738,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9959000002198763e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_orchestrator_contract.py::regression_schedule_orchestrator_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.979199999903926e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00042862499999785086,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.704200000242963e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_params_read_failure_visible.py::regression_schedule_params_read_failure_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.883300000140366e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0016776669999991611,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5792000002032864e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py::regression_schedule_persistence_reject_empty_actionable_schedule",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.716700000211404e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001539708000002804,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7792000000536063e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_persistence_reschedulable_contract.py::regression_schedule_persistence_reschedulable_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.86669999983269e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00288416700000127,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.529199999974253e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_all_frozen_short_circuit.py::regression_schedule_service_all_frozen_short_circuit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.858299999848214e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004301707999999849,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.304099999785649e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_empty_reschedulable_rejected.py::regression_schedule_service_empty_reschedulable_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1416999998489246e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00048512500000086334,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.0957999999591266e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_facade_delegation.py::regression_schedule_service_facade_delegation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.837499999903571e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0020352499999987117,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.2458999999439584e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py::regression_schedule_service_missing_resource_source_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.141700000204196e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001895167000000697,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.641700000045489e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_passes_algo_stats_to_summary.py::regression_schedule_service_passes_algo_stats_to_summary",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.683299999934775e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0022267500000019425,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.712499999863894e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_service_reschedulable_contract.py::regression_schedule_service_reschedulable_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.766700000085166e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0015278750000007335,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.61250000011637e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_end_date_type_guard.py::regression_schedule_summary_end_date_type_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.054200000069841e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008959160000010513,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9750000002669594e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_fallback_counts_output.py::regression_schedule_summary_fallback_counts_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.879200000156402e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009885829999980444,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.574999999855777e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py::regression_schedule_summary_invalid_due_and_unscheduled_counts",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6250000000848104e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00037370899999800145,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.462499999784541e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_overdue_warning_append_fallback.py::regression_schedule_summary_overdue_warning_append_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.81249999996669e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.15284233299999883,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.983399999858307e-05,
      "longrepr": "",
      "nodeid": "tests/regression_schedule_summary_size_guard_large_lists.py::regression_schedule_summary_size_guard_large_lists",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.087499999982924e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009917919999971048,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.195800000061922e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py::regression_scheduler_accepts_start_dt_string_and_safe_weights",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1165999999037695e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27941195800000074,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.320800000063741e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.237499999959482e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00846066599999773,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.729099999778441e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py::regression_scheduler_apply_preset_reject_invalid_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.14580000018816e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005650207999998713,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.3790999999515634e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_enforce_ready_default_from_config.py::regression_scheduler_enforce_ready_default_from_config",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0667000000382814e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2707477499999982,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.570899999796097e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_strict_numeric.py::regression_scheduler_excel_calendar_strict_numeric",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.216600000006565e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27306104199999837,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.0583999999863636e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_excel_calendar_uses_executor.py::regression_scheduler_excel_calendar_uses_executor",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.191700000077958e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008276249999994434,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.4249999998413614e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_nonfinite_efficiency_fallback.py::regression_scheduler_nonfinite_efficiency_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.733299999770679e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004812291000000357,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.370899999983635e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py::regression_scheduler_reject_nonfinite_and_invalid_status",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.983300000243162e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.008253624999998266,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.358299999969063e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_route_enforce_ready_tristate.py::regression_scheduler_route_enforce_ready_tristate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2000000000541604e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4179410840000024,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.779099999969617e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_run_no_reschedulable_flash.py::regression_scheduler_run_no_reschedulable_flash",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.254100000267158e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002223250000000121,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.374999999967599e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_strict_mode_dispatch_flags.py::regression_scheduler_strict_mode_dispatch_flags",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.129199999880484e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.41760054099999877,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.812499999890974e-05,
      "longrepr": "",
      "nodeid": "tests/regression_scheduler_week_plan_no_reschedulable_flash.py::regression_scheduler_week_plan_no_reschedulable_flash",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4875000000388354e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011519169999978374,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.299999999801685e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_dedup.py::regression_seed_results_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.108299999927567e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000656833000000745,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.875000000126306e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py::regression_seed_results_drop_duplicate_op_id_and_bad_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0291999997776884e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011559999999981585,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7207999998400965e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_freeze_missing_resource.py::regression_seed_results_freeze_missing_resource",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7625000000929276e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001174791000000397,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.441600000186895e-05,
      "longrepr": "",
      "nodeid": "tests/regression_seed_results_invalid_op_id_dedup.py::regression_seed_results_invalid_op_id_dedup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.637500000053251e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007234579999995105,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.470800000078157e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_atc_penalize_missing_resources.py::regression_sgs_atc_penalize_missing_resources",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.149999999825127e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006228330000013216,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.250000000283194e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_penalize_nonfinite_proc_hours.py::regression_sgs_penalize_nonfinite_proc_hours",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0500000000776026e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008814590000021383,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.925000000037926e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py::regression_sgs_scoring_machine_operator_id_type_safe",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9416999999986047e-05,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0019923750000003793,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7665999997216204e-05,
      "longrepr": "",
      "nodeid": "tests/regression_shared_runtime_state.py::regression_shared_runtime_state",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6082999997310026e-05,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0058285419999997146,
      "longrepr": ".venv/lib/python3.8/site-packages/_pytest/runner.py:341: in from_call\n    result: TResult | None = func()\n.venv/lib/python3.8/site-packages/_pytest/runner.py:242: in <lambda>\n    lambda: runtest_hook(item=item, **kwds), when=when, reraise=reraise\n.venv/lib/python3.8/site-packages/pluggy/_hooks.py:513: in __call__\n    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)\n.venv/lib/python3.8/site-packages/pluggy/_manager.py:120: in _hookexec\n    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:139: in _multicall\n    raise exception.with_traceback(exception.__traceback__)\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/threadexception.py:92: in pytest_runtest_call\n    yield from thread_exception_runtest_hook()\n.venv/lib/python3.8/site-packages/_pytest/threadexception.py:68: in thread_exception_runtest_hook\n    yield\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/unraisableexception.py:95: in pytest_runtest_call\n    yield from unraisable_exception_runtest_hook()\n.venv/lib/python3.8/site-packages/_pytest/unraisableexception.py:70: in unraisable_exception_runtest_hook\n    yield\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/logging.py:846: in pytest_runtest_call\n    yield from self._runtest_for(item, \"call\")\n.venv/lib/python3.8/site-packages/_pytest/logging.py:829: in _runtest_for\n    yield\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/capture.py:898: in pytest_runtest_call\n    return (yield)\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/skipping.py:257: in pytest_runtest_call\n    return (yield)\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:103: in _multicall\n    res = hook_impl.function(*args)\n.venv/lib/python3.8/site-packages/_pytest/runner.py:174: in pytest_runtest_call\n    item.runtest()\ntests/conftest.py:82: in runtest\n    rc = main()\ntests/regression_skill_rank_mapping.py:95: in main\n    assert len(rows) == 1, f\"预期 1 条 Schedule 记录，实际 {len(rows)}\"\nE   AssertionError: 预期 1 条 Schedule 记录，实际 0",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 8.991600000030076e-05,
      "longrepr": "",
      "nodeid": "tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5709000001892264e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005051670000000286,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.887500000132604e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategies_priority_case_insensitive.py::regression_sort_strategies_priority_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6708999999746084e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003410000000023672,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7707999997138586e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sort_strategy_case_insensitive.py::regression_sort_strategy_case_insensitive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.787500000029809e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004838330000005442,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5415999999344194e-05,
      "longrepr": "",
      "nodeid": "tests/regression_sqlite_detect_types_enabled.py::regression_sqlite_detect_types_enabled",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.691599999910977e-05,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002202708999998748,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.645800000029453e-05,
      "longrepr": "",
      "nodeid": "tests/regression_start_and_rerun_route_resolution.py::regression_start_and_rerun_route_resolution",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7207999998400965e-05,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007342920000006359,
      "longrepr": "tests/regression_startup_host_portfile.py:229: in _run_case\n    expected_pid=p.pid,\nE   AttributeError: '_DummyProc' object has no attribute 'pid'\n\nDuring handling of the above exception, another exception occurred:\ntests/runtime_cleanup_helper.py:185: in cleanup_runtime_process\n    if process.poll() is None:\nE   AttributeError: '_DummyProc' object has no attribute 'poll'\n\nDuring handling of the above exception, another exception occurred:\n.venv/lib/python3.8/site-packages/_pytest/runner.py:341: in from_call\n    result: TResult | None = func()\n.venv/lib/python3.8/site-packages/_pytest/runner.py:242: in <lambda>\n    lambda: runtest_hook(item=item, **kwds), when=when, reraise=reraise\n.venv/lib/python3.8/site-packages/pluggy/_hooks.py:513: in __call__\n    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)\n.venv/lib/python3.8/site-packages/pluggy/_manager.py:120: in _hookexec\n    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:139: in _multicall\n    raise exception.with_traceback(exception.__traceback__)\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/threadexception.py:92: in pytest_runtest_call\n    yield from thread_exception_runtest_hook()\n.venv/lib/python3.8/site-packages/_pytest/threadexception.py:68: in thread_exception_runtest_hook\n    yield\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/unraisableexception.py:95: in pytest_runtest_call\n    yield from unraisable_exception_runtest_hook()\n.venv/lib/python3.8/site-packages/_pytest/unraisableexception.py:70: in unraisable_exception_runtest_hook\n    yield\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/logging.py:846: in pytest_runtest_call\n    yield from self._runtest_for(item, \"call\")\n.venv/lib/python3.8/site-packages/_pytest/logging.py:829: in _runtest_for\n    yield\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/capture.py:898: in pytest_runtest_call\n    return (yield)\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/skipping.py:257: in pytest_runtest_call\n    return (yield)\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:103: in _multicall\n    res = hook_impl.function(*args)\n.venv/lib/python3.8/site-packages/_pytest/runner.py:174: in pytest_runtest_call\n    item.runtest()\ntests/conftest.py:82: in runtest\n    rc = main()\ntests/regression_startup_host_portfile.py:282: in main\n    _run_case(repo_root, h)\ntests/regression_startup_host_portfile.py:270: in _run_case\n    cleanup_runtime_process(repo_root, \"app.py\", p, env=env)\ntests/runtime_cleanup_helper.py:220: in cleanup_runtime_process\n    if process.poll() is None:\nE   AttributeError: '_DummyProc' object has no attribute 'poll'",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00014645899999976564,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile.py::regression_startup_host_portfile",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.854199999788534e-05,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008765000000003909,
      "longrepr": "tests/regression_startup_host_portfile_new_ui.py:222: in _run_case\n    expected_pid=p.pid,\nE   AttributeError: '_DummyProc' object has no attribute 'pid'\n\nDuring handling of the above exception, another exception occurred:\ntests/runtime_cleanup_helper.py:185: in cleanup_runtime_process\n    if process.poll() is None:\nE   AttributeError: '_DummyProc' object has no attribute 'poll'\n\nDuring handling of the above exception, another exception occurred:\n.venv/lib/python3.8/site-packages/_pytest/runner.py:341: in from_call\n    result: TResult | None = func()\n.venv/lib/python3.8/site-packages/_pytest/runner.py:242: in <lambda>\n    lambda: runtest_hook(item=item, **kwds), when=when, reraise=reraise\n.venv/lib/python3.8/site-packages/pluggy/_hooks.py:513: in __call__\n    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)\n.venv/lib/python3.8/site-packages/pluggy/_manager.py:120: in _hookexec\n    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:139: in _multicall\n    raise exception.with_traceback(exception.__traceback__)\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/threadexception.py:92: in pytest_runtest_call\n    yield from thread_exception_runtest_hook()\n.venv/lib/python3.8/site-packages/_pytest/threadexception.py:68: in thread_exception_runtest_hook\n    yield\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/unraisableexception.py:95: in pytest_runtest_call\n    yield from unraisable_exception_runtest_hook()\n.venv/lib/python3.8/site-packages/_pytest/unraisableexception.py:70: in unraisable_exception_runtest_hook\n    yield\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/logging.py:846: in pytest_runtest_call\n    yield from self._runtest_for(item, \"call\")\n.venv/lib/python3.8/site-packages/_pytest/logging.py:829: in _runtest_for\n    yield\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/capture.py:898: in pytest_runtest_call\n    return (yield)\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:122: in _multicall\n    teardown.throw(exception)  # type: ignore[union-attr]\n.venv/lib/python3.8/site-packages/_pytest/skipping.py:257: in pytest_runtest_call\n    return (yield)\n.venv/lib/python3.8/site-packages/pluggy/_callers.py:103: in _multicall\n    res = hook_impl.function(*args)\n.venv/lib/python3.8/site-packages/_pytest/runner.py:174: in pytest_runtest_call\n    item.runtest()\ntests/conftest.py:82: in runtest\n    rc = main()\ntests/regression_startup_host_portfile_new_ui.py:274: in main\n    _run_case(repo_root, h)\ntests/regression_startup_host_portfile_new_ui.py:262: in _run_case\n    cleanup_runtime_process(repo_root, \"app_new_ui.py\", p, env=env)\ntests/runtime_cleanup_helper.py:220: in cleanup_runtime_process\n    if process.poll() is None:\nE   AttributeError: '_DummyProc' object has no attribute 'poll'",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00010658400000096435,
      "longrepr": "",
      "nodeid": "tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.1583999997717456e-05,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0034250419999999338,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.366699999991397e-05,
      "longrepr": "",
      "nodeid": "tests/regression_status_category_mixed_case.py::regression_status_category_mixed_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0709000000305195e-05,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004101670000018487,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6124999997610985e-05,
      "longrepr": "",
      "nodeid": "tests/regression_strict_parse_blank_required.py::regression_strict_parse_blank_required",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7584000001089635e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0036358749999969575,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.166699999747948e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_config_dirty_fields_contract.py::regression_system_config_dirty_fields_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.779100000045332e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.9016343750000004,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.30000000008124e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_health_route.py::regression_system_health_route",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00012970799999934002,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27371537500000187,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.33750000002442e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_logs_delete_no_clamp.py::regression_system_logs_delete_no_clamp",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.24169999995172e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2669018329999986,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.941699999922889e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_invalid_last_run_visible.py::regression_system_maintenance_invalid_last_run_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.279199999857042e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02169829099999987,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.879199999763273e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_jobstate_commit.py::regression_system_maintenance_jobstate_commit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1666999997858056e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002955458000002409,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.3375000000622776e-05,
      "longrepr": "",
      "nodeid": "tests/regression_system_maintenance_throttle_short_circuit.py::regression_system_maintenance_throttle_short_circuit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2666000002355986e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02839462499999712,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0833000003081e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_no_inline_event_jinja.py::regression_template_no_inline_event_jinja",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2041000000381246e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.23544925000000205,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.5916000000877375e-05,
      "longrepr": "",
      "nodeid": "tests/regression_template_urlfor_endpoints.py::regression_template_urlfor_endpoints",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.320800000101599e-05,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.248614749999998,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.17920000007166e-05,
      "longrepr": "",
      "nodeid": "tests/regression_tojson_zh_autoescape.py::regression_tojson_zh_autoescape",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.24169999995172e-05,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002970208000000696,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.637500000015393e-05,
      "longrepr": "",
      "nodeid": "tests/regression_transaction_savepoint_nested.py::regression_transaction_savepoint_nested",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0708000000222455e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012387089999990053,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.224999999953184e-05,
      "longrepr": "",
      "nodeid": "tests/regression_ui_contract_table_overflow_guard.py::regression_ui_contract_table_overflow_guard",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.366699999991397e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.1121469580000003,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.9458000002999825e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_diagnostics_visible.py::regression_unit_excel_converter_diagnostics_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.329199999730804e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00738308400000065,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.558400000220786e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py::regression_unit_excel_converter_duplicate_part_rows_no_override",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.370799999975361e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009842500000019072,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.220799999998803e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_facade_binding.py::regression_unit_excel_converter_facade_binding",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1416999998489246e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13487979199999955,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.704200000167248e-05,
      "longrepr": "",
      "nodeid": "tests/regression_unit_excel_converter_merge_steps_and_classify.py::regression_unit_excel_converter_merge_steps_and_classify",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5583999998655145e-05,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000544708999999699,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.97079999991945e-05,
      "longrepr": "",
      "nodeid": "tests/regression_v2_strategy_zh_contract.py::regression_v2_strategy_zh_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.86669999983269e-05,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.43034833399999783,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001641250000012917,
      "longrepr": "",
      "nodeid": "tests/regression_validate_dist_runtime_identity.py::regression_validate_dist_runtime_identity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011129099999962477,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0016695419999983585,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011466699999829189,
      "longrepr": "",
      "nodeid": "tests/regression_value_policies_matrix_contract.py::regression_value_policies_matrix_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.854199999992375e-05,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0047914999999996155,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013045800000099916,
      "longrepr": "",
      "nodeid": "tests/regression_warmstart_failure_surfaces_degradation.py::regression_warmstart_failure_surfaces_degradation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00013441599999808318,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009492920000013783,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011412499999963188,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00016445800000042254,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000575374999996825,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015162500000087675,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_override_full_cover_still_validates_ready_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00018837500000046248,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010509590000005176,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0002454579999984219,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_schedule_created_at_strict_only_applies_to_fifo",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004269579999984785,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004582499999976619,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.858399999984613e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00013104199999958155,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003491249999996171,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.724999999998317e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_ready_date_adjust_errors_bubble_without_silent_fallback[True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001655830000011349,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013162910000019679,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.641699999818343e-05,
      "longrepr": "",
      "nodeid": "tests/test_algorithm_date_boundary_split.py::test_optimize_schedule_created_at_strict_only_for_current_strategy",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0014279589999972586,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7697420830000006,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.691600000039102e-05,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002998749999996164,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.7368349579999993,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.774999999834222e-05,
      "longrepr": "",
      "nodeid": "tests/test_app_factory_runtime_env_refresh.py::test_app_new_ui_create_app_uses_current_environment_each_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.758300000062832e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.017084333999999757,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.670900000216307e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0416000000552685e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.02993954200000104,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.779100000249173e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_import_flask_request",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5500000002363095e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004506417000001761,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.2666999998507436e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_routes_do_not_import_repository",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.291700000180754e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008462079999986827,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5791999998101574e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_web_helpers_do_not_import_repository",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.725000000149748e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.017841374999999715,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0167000001266615e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3542000000229564e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.013187208000001505,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.466700000056335e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_circular_service_dependencies",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2375000003147534e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03121233299999915,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.129199999804769e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_wildcard_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6000000001100716e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.24035533300000012,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.5291999998985375e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_new_local_parse_helpers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.591700000133869e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2424842500000004,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.474999999918964e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_stable_degradation_codes_cover_actual_usages",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.137500000060527e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.15564424999999815,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.600000000072214e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2916999997876246e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.6101766670000011,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00015100000000245473,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_no_silent_exception_swallow",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.683400000071174e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.06331658299999887,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.3707999999375033e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_startup_silent_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.38749999993604e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2800970410000012,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.108400000215397e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.654199999976072e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 2.3418192500000004,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.637499999939678e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.850000000189425e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.015846333000002488,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.2208999999692196e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_size_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.1541000001643624e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.015625790999997946,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.854199999788534e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.483300000046597e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.020656750000000557,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.733400000058509e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.291599999817208e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3808912080000013,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.4707999996850276e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.391699999928278e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3937579999999983,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.7916999999463314e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4625000001019544e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0031293330000004005,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.699999999819738e-05,
      "longrepr": "",
      "nodeid": "tests/test_architecture_fitness.py::test_file_naming_snake_case",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003040419999997823,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2675305829999992,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001049999999978013,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00041116699999932393,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2669467919999988,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.649999999832403e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_equipment_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00029274999999984175,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2658190420000004,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.495799999825749e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_personnel_bulk_routes_show_reasons_and_log_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00031495800000058694,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.285705458999999,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.145799999998871e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_process_bulk_delete_shows_reason_and_logs_unexpected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00030004099999914047,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2709537080000004,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.987500000083969e-05,
      "longrepr": "",
      "nodeid": "tests/test_bulk_route_error_visibility.py::test_system_backup_batch_delete_shows_specific_failure_reasons",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4541999997704806e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006320419999994442,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.524999999982015e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_render_report_uses_repo_relative_path_and_stable_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.687499999927013e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002070409999994638,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.82920000028264e-05,
      "longrepr": "",
      "nodeid": "tests/test_check_quickref_vs_routes.py::test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.837499999903571e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.554199999873276e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.154199999855223e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_occupy_resource_keeps_segments_sorted",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.437500000202931e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.5332999999203594e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.999999999886427e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_runtime_state_helpers_handle_seed_and_dispatch_modes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4582999997923025e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.816599999912796e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2583999999502566e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_update_machine_last_state_rejects_non_datetime_end_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.487500000076693e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.56250000020475e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0041000002256624e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_accumulate_busy_hours_rejects_non_datetime",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.370900000021493e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002743750000000489,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.345800000076338e-05,
      "longrepr": "",
      "nodeid": "tests/test_downtime_timeline_ordered_insert.py::test_schedule_normalizes_unordered_machine_downtimes_once",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.624999999729539e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.349999999955003e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2958000002025756e-05,
      "longrepr": "",
      "nodeid": "tests/test_enum_display_consistency.py::test_enum_display_wrappers_expected_outputs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002709169999981498,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26681812500000035,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.42920000003744e-05,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_shows_planned_downtime_when_overlay_available",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00029541700000024207,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2693749580000002,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.416700000069e-05,
      "longrepr": "",
      "nodeid": "tests/test_equipment_page_downtime_overlay_degraded.py::test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003124999999997158,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0023207499999990944,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.291700000142896e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_quantity_float_is_rejected_without_truncation",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.191700000077958e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.404099999850587e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.387500000329169e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_accepts_parts_cache_without_conn",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6541000000056556e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.266600000084168e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4374999998476596e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_batch_validator_requires_conn_when_parts_cache_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.658400000006168e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.858400000211759e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.175000000155137e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_blank_helper_does_not_treat_zero_as_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002153749999997956,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002582166999999913,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.1124999998819476e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_import_service_does_not_treat_zero_id_as_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2834000002045514e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.350000000234559e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.600000000147929e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_ensure_unique_ids_detects_integer_like_float_duplicates",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00023558300000203758,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2406178340000018,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00013675000000290538,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_fallback_trims_time_suffix",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00031504100000034896,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0028181659999972908,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.9083000000393895e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_validator_rejects_bool_and_nonfinite_numeric_inputs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002779159999981573,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3018251670000005,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.925000000166051e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_operator_calendar_preview_and_confirm_reject_bool_numeric_cells",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00027962499999745205,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.24182291600000028,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.866599999952541e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_upload_over_limit_returns_413",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00030016599999882487,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2736262079999996,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010970800000009717,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_exact_file_limit_is_not_rejected_by_multipart_overhead",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003602080000000285,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27415108399999966,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.17500000032112e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_op_type_preview_and_confirm_reject_duplicate_name_conflict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0005788749999986464,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.23880970800000156,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011345800000128747,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_file_body_over_limit_returns_file_too_large_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003304170000006934,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2640194170000001,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.30409999998949e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_scheduler_calendar_preview_rejects_duplicate_dates_after_canonicalization",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3083000001331584e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.003286833000000655,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.612500000078512e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_import_hardening.py::test_build_xlsx_bytes_sanitizes_formula_like_strings",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5124999999757165e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001031249999989825,
      "longrepr": "tests/test_excel_normalizers_contract.py:17: in test_regression_excel_normalizers_mixed_case_script_smoke\n    result = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 6.629099999955201e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.495800000015038e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00034462500000032037,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.662499999990132e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_true_for_equal_token",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6250000000848104e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002516659999969306,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.954099999958771e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_for_different_token",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0001685840000007488,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00034370799999905444,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.1250000002056595e-05,
      "longrepr": "",
      "nodeid": "tests/test_excel_utils_compare_digest_guard.py::test_preview_baseline_matches_returns_false_when_compare_digest_raises",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000301916999998042,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.17788175000000095,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0001155409999995527,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004409589999987418,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.16569949999999878,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00011716699999908542,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_records_collection_errors_and_exitstatus",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004129589999983807,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.13171008300000153,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010954100000049038,
      "longrepr": "",
      "nodeid": "tests/test_full_test_debt_registry_contract.py::test_collect_full_test_debt_writes_raw_baseline_machine_block",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.429199999795742e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.333299999956466e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3375000001001354e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_safe_int_parses_integer_float_forms",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.662499999990132e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.054200000031983e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.09170000001302e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4333999998636955e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011754199999813864,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6042000001401675e-05,
      "longrepr": "",
      "nodeid": "tests/test_gantt_safe_int_parsing.py::test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.887499999777333e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.400000000221894e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.129199999918342e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_make_algo_stats_can_be_used_as_explicit_counter_sink",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.462499999784541e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.358299999969063e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1375000002498155e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_legacy_scheduler_stats_snapshot_still_works",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.416599999894743e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.679099999866821e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.375000000005457e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_legacy_scheduler_repairs_bad_stats_sink",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8040999999822134e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.9541999999291875e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0791000000363056e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_run_context_external_fallback_writes_legacy_scheduler_stats",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3416000000840995e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.895800000033091e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2791999998948995e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_merge_algo_stats_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010550000000009163,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.254199999844445e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016966699999798607,
      "longrepr": "",
      "nodeid": "tests/test_greedy_algo_stats_contract.py::test_snapshot_algo_stats_fallback_deep_copies_fallback_samples",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.783299999923997e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011345900000137021,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8417000002510804e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_duplicate_batch_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.141700000204196e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.6583999999304524e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9624999999432475e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_normalized_batches_reject_empty_batch_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.533299999958217e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.2249999999910415e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2333000000051015e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_keeps_valid_batch_ids_in_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.825000000176829e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.2416999999138625e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.0291999997776884e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override0]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002209579999998823,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.737500000118189e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.57080000021881e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override1]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.229199999945422e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.920900000016104e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.883299999785095e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_override_rejects_invalid_batch_order_items[override2]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.524999999982015e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.100000000117348e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1625000001866965e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_strict_ready_date_error_is_not_hidden_by_full_override",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.566600000226572e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.695800000144914e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.262499999934221e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_bad_str_conversion_is_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.491600000060657e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.858399999780772e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.46670000013205e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_ordering_contract.py::test_operation_sort_key_uses_shared_integer_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.787500000029809e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012154099999861501,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0165999998388315e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3874999999738975e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.820799999942892e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9417000000364624e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_keeps_legacy_ordering_helper_export",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.416699999903017e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013799999999974943,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.337499999744864e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_modules_do_not_call_scheduler_private_callbacks",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.537499999950455e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.006899541999999315,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.81249999996669e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5833000001872506e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.017990040999997348,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.445900000111692e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_refactored_algorithm_files_stay_under_complexity_threshold",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4166000002121564e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003527080000012006,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.949999999974807e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_scheduler_schedule_still_uses_legacy_internal_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.316700000117635e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00018087499999808188,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5624999998873363e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_legacy_direct_dispatch_keeps_empty_state_containers_in_place",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.816699999958928e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.712500000105592e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.220800000036661e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_identity_fields_reject_fractional_text_without_crashing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.512500000013574e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.783299999999713e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.104199999981461e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4124999999107786e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.874999999771035e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9916999999102245e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_backfill_preserves_original_object_source_and_dynamic_attributes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.666599999974096e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.887500000056889e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.154200000210494e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_seed_bad_time_reasons_are_separated",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3957999999501e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.2499999999279225e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9874999999179863e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_empty_machine_pool_records_single_root_cause",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.379099999989421e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.22919999998328e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9208000000835455e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_operator_requires_declared_op_type_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.666599999974096e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.066699999924708e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.13339999991058e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8708000001719256e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.295900000172992e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.083300000028544e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_fixed_machine_respects_declared_op_type_pool",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4750000001082526e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.983300000091731e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2999999998395424e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_auto_assign_existing_pair_rank_must_be_integer",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.258300000259396e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002588330000001804,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6333999997140154e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_scoring_hook_sync_does_not_leak_monkeypatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.454100000155336e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001582079999984387,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.408300000273812e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.370900000021493e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.65000000026339e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.108299999965425e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_enforces_strict_internal_input_before_legacy_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.595800000155691e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.570899999796097e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.983399999934022e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.295899999855578e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011883299999837504,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1416000002337796e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_external_scoring_does_not_double_count_defaulted_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.420899999895255e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.93750000032378e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.058400000099937e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.904200000093283e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.200000000016303e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.112499999957663e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_external_scoring_rejects_blank_merged_total_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.41250000026605e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.25410000007787e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.6957999999032154e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.420800000242252e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.16249999975571e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.054099999872278e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_sequence_identity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.862500000195723e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.420900000061238e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.279100000090466e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00012079100000050857,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003465409999989788,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0833999999611024e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_rejects_malformed_auto_assign_probe_result",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.099999999951365e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014374999999944293,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3625000000370164e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.879099999996697e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00020491700000135893,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.904100000085009e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[batch_order]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3707999999375033e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002197919999993303,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.433399999825838e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_refactor_contracts.py::test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes[sgs]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2042000000463986e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.3707999999375033e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.187499999768306e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_seed_result_missing_resources_records_warning_counts_without_blocking",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.208300000030363e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.724999999794477e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.191700000115816e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_run_state_contract.py::test_dispatch_success_advances_progress_and_records_internal_usage",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.983299999812175e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00018562500000030013,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.149999999825127e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_passes_start_dt_date_to_sorter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.141699999811067e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00017633400000249821,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.979099999895652e-05,
      "longrepr": "",
      "nodeid": "tests/test_greedy_scheduler_base_date.py::test_greedy_scheduler_weighted_order_uses_start_dt_base_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00033683400000228403,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26870137499999913,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.983300000053873e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003663749999986976,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2781215409999973,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.929199999840876e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035049999999614556,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.30698612500000166,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.416600000060726e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037845800000013696,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2857669999999999,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.862500000361706e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/config-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00033766699999659977,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2779167500000028,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.379100000155404e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035791600000578683,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.267562875000003,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.766599999887603e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/calendar-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003505829999994603,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3013493750000009,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010345899999464336,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config[/scheduler/batches/B001-True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003471670000010363,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2802376670000015,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.179199999602815e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00029475000000189766,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2662004170000003,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.504200000596484e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003014999999990664,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.26793587499999916,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.995899999713174e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.529199999581124e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004763339999982463,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5124999999757165e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_calendar_picker_js_does_not_rebuild_local_0_8_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003171669999986193,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27240583399999707,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.883299999951078e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00033462500000069895,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2960377089999966,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.016700000013088e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003338750000025925,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.27502941699999894,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.78340000017397e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034812499999503643,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.2744132089999951,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.116699999760613e-05,
      "longrepr": "",
      "nodeid": "tests/test_holiday_default_efficiency_read_guard.py::test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5374999999125976e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013641599999658638,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4958000000528955e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_matches_schedule_internal_and_is_read_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.662500000700675e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.158299999725614e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.495799999342353e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_uses_adjusted_max_of_prev_end_and_base_time",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.687499999927013e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0017727919999970254,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.491699999993216e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_estimator_handles_more_than_two_hundred_fragments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.308399999786161e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.529100000487233e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.279200000605442e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.474999999752981e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011037499999844158,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5249999996267434e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.61250000011637e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.733399999982794e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1915999997522704e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_fallback_only_updates_formal_schedule_counter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4166000006052855e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00024562499999802867,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.399999999942338e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_auto_assign_passes_best_end_to_estimator_abort_after",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.529199999974253e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.887500000056889e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.804199999597358e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_returns_start_equals_end",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.604199999784896e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.404200000531546e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2500000003210516e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_still_avoids_occupied_segments",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4499999998161e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.7458000000565335e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.162500000541968e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_zero_hours_at_segment_start_does_not_shift",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5207999999897766e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021033300000539157,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.0916999999751624e-05,
      "longrepr": "",
      "nodeid": "tests/test_internal_slot_estimator_consistency.py::test_efficiency_edge_cases_none_invalid_values_and_exception",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9125000000694854e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0011558749999949214,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.458300000147574e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.587500000179489e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009192080000062219,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.395899999958374e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_name_raises_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.454199999453067e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000895874999997659,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.591700000526998e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_missing_status_raises_specific_message",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.61250000011637e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008618749999982356,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3542000004160855e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_valid_rows_commit_and_trim_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4083999999268144e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009420829999982061,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.450000000526643e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.433300000210693e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009353330000010374,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.420899999895255e-05,
      "longrepr": "",
      "nodeid": "tests/test_machine_excel_import_apply_defense.py::test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00013395799999926794,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001029416999998034,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.0500000003571586e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v1-\\u5df2\\u6e05\\u6d17 Batches \\u7684\\u65e5\\u671f\\u5b57\\u6bb5]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.933399999795256e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008718340000015701,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.6707999995353475e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v2-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v2\\uff1a\\u5df2\\u5c06 WorkCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.983400000379561e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010313750000037203,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.51670000024751e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v3-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v3\\uff1a\\u5df2\\u5c06 OperatorCalendar.day_type \\u7684 weekend \\u7edf\\u4e00\\u4e3a holiday]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010624999999464535,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0016439169999955539,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.087499999869351e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v4-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v4\\uff1a\\u5df2\\u6e05\\u6d17 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00010287499999606098,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0015403750000047012,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010083300000474082,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_each_migration_falls_back_to_stderr_when_logger_is_broken[run-_prep_v5-\\u6570\\u636e\\u5e93\\u8fc1\\u79fb v5\\uff1a\\u5df2\\u4fee\\u6b63 OperatorMachine.skill_level]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.300000000119098e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001127791999998351,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8124999996114184e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v5_run_does_not_log_changed_rows_for_canonical_values",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.983400000062147e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.03880837499999501,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.566700000045557e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_ensure_schema_migration_entry_path_survives_broken_logger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.79999999980896e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002875000000059913,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.166700000103219e-05,
      "longrepr": "",
      "nodeid": "tests/test_migration_logging_fallback.py::test_v6_run_falls_back_to_stderr_when_logger_is_broken",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.0625000004013145e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.083299999990686e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.004199999878665e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_none_and_blank",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.479200000100491e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.716599999847858e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0541000000994245e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_normalize_text_str_and_non_str",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3666000000209806e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.637500000053251e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1833000001313394e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_none_buffer",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.679199999595539e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.9542000003223166e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.954200000004903e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_single_value_and_dedup_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3375000001001354e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.5584000002586436e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.966599999609798e-05,
      "longrepr": "",
      "nodeid": "tests/test_normalize_text.py::test_append_unique_text_messages_accepts_set_input",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.495900000416441e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000990584000000183,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.10839999958057e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.804100000337485e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008955409999984454,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.874999999453621e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_create",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4708000001160144e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009047080000001984,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.645799999674182e-05,
      "longrepr": "",
      "nodeid": "tests/test_op_type_excel_import_apply_defense.py::test_apply_preview_rows_rejects_duplicate_name_on_update",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.758399999753692e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008627089999961868,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.295899999500307e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_strips_name_and_normalizes_remark",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6417000004007605e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008435419999983651,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.304200000542323e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_update_without_team_column_preserves_existing_team_id",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3625000000370164e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013205839999983482,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.92080000000783e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_excel_import_normalization.py::test_operator_excel_import_team_accepts_id_or_name_and_blank_clears",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.383400000155916e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.241024000000003,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.079199999855291e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_excel_route_error_handling.py::test_personnel_excel_preview_hides_internal_runtime_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.737500000118189e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.87089999963564e-05,
      "longrepr": "tests/test_operator_machine_exception_paths.py:45: in test_normalize_skill_level_optional_only_converts_value_error\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/Users/lurenxing/Documents/GitHub/----/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 9.812500000094815e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.416699999865159e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.804199999521643e-05,
      "longrepr": "tests/test_operator_machine_exception_paths.py:54: in test_normalize_skill_level_stored_only_falls_back_for_value_error\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/Users/lurenxing/Documents/GitHub/----/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 9.595800000283816e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.320800000101599e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001500999999997532,
      "longrepr": "tests/test_operator_machine_exception_paths.py:72: in test_list_by_operator_propagates_unexpected_readside_normalization_errors\n    with patch(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1393: in __enter__\n    original, local = self.get_original()\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/unittest/mock.py:1366: in get_original\n    raise AttributeError(\nE   AttributeError: <module 'core.services.personnel.operator_machine_normalizers' from '/Users/lurenxing/Documents/GitHub/----/core/services/personnel/operator_machine_normalizers.py'> does not have the attribute 'normalize_skill_level'",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 9.90829999949483e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5165999999596806e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0014370829999990065,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.9125000000694854e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_preview_skill_and_primary_only_convert_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.7708999997221326e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.001018541000000539,
      "longrepr": "tests/test_operator_machine_exception_paths.py:128: in test_resolve_write_values_only_converts_validation_error\n    assert new_skill is None\nE   AssertionError: assert 'normal' is None",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 4.449999999422971e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8000000003535206e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021449999999845204,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.779099999690061e-05,
      "longrepr": "",
      "nodeid": "tests/test_operator_machine_exception_paths.py::test_query_service_only_falls_back_for_value_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8291999999273685e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011974999999608826,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1417000002420536e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4833999997374576e-05,
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
      "duration": 2.908300000115105e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostics_without_fake_score",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3915999999578617e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.766699999933735e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5167000000058124e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.450000000526643e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.1416999998489246e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.058299999736391e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_attempt_compaction_contract.py::test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.575000000211048e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004523749999947313,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.399999999942338e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_build_order_is_cached_per_strategy_within_single_multi_start_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.474999999752981e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00024204200000355058,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5457999995335285e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.875000000164164e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021575000000240152,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5457999999266576e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_strict_mode_raises_non_primary_sgs_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.61250000011637e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001443750000049704,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.420899999895255e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.991700000227638e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00022733299999799783,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.562500000242608e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_multi_start_partial_object_cfg_is_normalized_before_weighted_params",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4958000000528955e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.82080000018459e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.120800000289137e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.283300000437976e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00016204199999947377,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.2750000005753463e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3999999998666226e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010716599999938126,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.241699999596449e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_dedups_duplicate_neighbors_when_order_large",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.250000000245336e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011641599999734353,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.983300000243162e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_retrying_duplicates_when_order_small",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.074999999976626e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.766699999933735e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8082999999744516e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_and_keeps_existing_best",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.074999999976626e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.458400000042275e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.8541999998642495e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_strict_mode_raises_rejected_neighbor_validation_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.091599999929031e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013054099999720847,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.866700000543233e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_records_rejected_neighbor_after_existing_attempt_cap",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.941600000307744e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.174999999648435e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7750000004166395e-05,
      "longrepr": "",
      "nodeid": "tests/test_optimizer_local_search_neighbor_dedup.py::test_local_search_keeps_distinct_rejected_neighbor_origins",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.579199999848015e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.133300000181862e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4708000001160144e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_parse_write_row_accepts_integer_float_string_forms",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3707999996579474e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011608399999829544,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4875000004319645e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_defense.py::test_apply_preview_rows_turns_nan_inf_into_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.670800000321606e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010834169999967003,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.341700000447645e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.741700000072569e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0014678329999995299,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.379200000277251e-05,
      "longrepr": "",
      "nodeid": "tests/test_part_operation_hours_import_apply_mixed_rows.py::test_apply_preview_rows_unexpected_exception_rolls_back_all_changes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.708399999411085e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0030743750000041814,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.9374999996132374e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_changed_files_preserve_first_git_status_columns",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.987499999804413e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015454199999709317,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.020900000512029e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_changed_file_exceeds_complexity",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.170799999376641e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012504200000051924,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.925000000037926e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_complexity_tool_is_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.120800000213421e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011950000000382488,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.1334000002279936e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_architecture_scan_skips_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2249999995979124e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011624999999781949,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.966700000290757e-05,
      "longrepr": "",
      "nodeid": "tests/test_post_change_check_contract.py::test_post_change_check_fails_when_code_quality_scan_skips_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.654199999658658e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001108749999971792,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.279100000241897e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_batch_query_service_has_any",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3792000003529665e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002192500000006703,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.4625000001019544e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_part_operation_query_service_lists_hours_and_details",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.662499999990132e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012083300000398367,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.21250000041573e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.554199999911134e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00029404100000363087,
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
      "duration": 3.604199999784896e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001715000000004352,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.974999999911688e-05,
      "longrepr": "",
      "nodeid": "tests/test_query_services.py::test_schedule_history_query_service_versions_and_latest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.812500000321961e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.0707999996291164e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.095900000005258e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_legacy_full_selftest_root_report_is_not_current_artifact",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.424999999879219e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006562079999952175,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.2499999999279225e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002978340000012736,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000510750000003668,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.099999999520378e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_tracked_regression_discovery_ignores_untracked_files",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002476250000000846,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007047499999970341,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.7750000000235104e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002176249999976676,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0061375839999939785,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:199: in test_quality_gate_binding_status_accepts_clean_proof_manifest\n    _write_verified_manifest(repo_root)\ntests/test_run_full_selftest_report_metadata.py:62: in _write_verified_manifest\n    collect_proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00012920799999704968,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035024999999677675,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005296292000004144,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:219: in test_quality_gate_manifest_replay_rechecks_clean_worktree\n    manifest_path = _write_verified_manifest(repo_root)\ntests/test_run_full_selftest_report_metadata.py:62: in _write_verified_manifest\n    collect_proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00015979199999804905,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003996669999963842,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0062779590000019425,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:244: in test_quality_gate_binding_status_rejects_command_replay_failure\n    _write_verified_manifest(repo_root)\ntests/test_run_full_selftest_report_metadata.py:62: in _write_verified_manifest\n    collect_proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00013983299999864585,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032733400000495294,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005818374999996934,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:260: in test_quality_gate_binding_status_replay_disabled_is_structural_only\n    _write_verified_manifest(repo_root)\ntests/test_run_full_selftest_report_metadata.py:62: in _write_verified_manifest\n    collect_proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00012133399999925132,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003037090000006515,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003390409999965982,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:297: in test_quality_gate_replay_rejects_forged_non_collect_receipt_output\n    note = shared.replay_quality_gate_command_plan(repo_root, [command], timeout_s=30, compare_receipts=True)\ntools/quality_gate_shared.py:569: in replay_quality_gate_command_plan\n    proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.0001939160000006268,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00014170800000101735,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00042204100000020617,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.145900000196434e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_volatile_iso_timestamp",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8709000001801996e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.620800000372128e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.1458999998790205e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_normalized_output_ignores_pyright_update_notice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003609999999980573,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005808416999997235,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:332: in test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest\n    _write_verified_manifest(\ntests/test_run_full_selftest_report_metadata.py:62: in _write_verified_manifest\n    collect_proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00014895800000402915,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003627500000007444,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.006510833000000105,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:364: in test_quality_gate_binding_status_reports_failed_manifest_reason\n    _write_verified_manifest(\ntests/test_run_full_selftest_report_metadata.py:62: in _write_verified_manifest\n    collect_proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00013812499999943384,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00037137500000028467,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005568624999995109,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:384: in test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch\n    _write_verified_manifest(repo_root, head_sha=\"not-deadbeef\")\ntests/test_run_full_selftest_report_metadata.py:62: in _write_verified_manifest\n    collect_proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00010950000000065074,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003813329999999837,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.006688000000004024,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:404: in test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope\n    _write_verified_manifest(repo_root, overrides={\"proof_scope\": None})\ntests/test_run_full_selftest_report_metadata.py:62: in _write_verified_manifest\n    collect_proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 9.708299999999781e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003250410000035231,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.006558958999995923,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:424: in test_quality_gate_binding_status_rejects_hash_mismatch\n    manifest_path = _write_verified_manifest(repo_root)\ntests/test_run_full_selftest_report_metadata.py:62: in _write_verified_manifest\n    collect_proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00010887500000222872,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003258750000014743,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.006436499999999512,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:478: in test_quality_gate_binding_status_rejects_missing_command_receipt_file\n    manifest_path = _write_verified_manifest(repo_root)\ntests/test_run_full_selftest_report_metadata.py:62: in _write_verified_manifest\n    collect_proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00011795799999703149,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00038545800000377994,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00582358300000152,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:492: in test_quality_gate_binding_status_rejects_fabricated_collection_proof\n    manifest_path = _write_verified_manifest(repo_root)\ntests/test_run_full_selftest_report_metadata.py:62: in _write_verified_manifest\n    collect_proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00012729200000194396,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003531670000000986,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.005767875000003642,
      "longrepr": "tests/test_run_full_selftest_report_metadata.py:511: in test_quality_gate_binding_status_rejects_fabricated_collect_receipt\n    manifest_path = _write_verified_manifest(repo_root)\ntests/test_run_full_selftest_report_metadata.py:62: in _write_verified_manifest\n    collect_proc = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00011800000000050659,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.641599999644086e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005251669999992714,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.129199999880484e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_full_selftest_report_metadata.py::test_full_selftest_explicit_guard_subset_comes_from_shared_registry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.087499999869351e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005786250000028303,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.61670000007075e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.841700000379205e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00033587500000464843,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.100000000230921e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_assert_no_active_runtime_allows_stale_trace_and_prints_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002913329999998382,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00048562500000315367,
      "longrepr": "tests/test_run_quality_gate.py:110: in test_main_runs_guard_preflight_before_static_and_startup_checks\n    assert module.main([]) == 0\nscripts/run_quality_gate.py:578: in main\n    manifest = _base_quality_gate_manifest(\nscripts/run_quality_gate.py:523: in _base_quality_gate_manifest\n    **_repo_identity(),\nscripts/run_quality_gate.py:192: in _repo_identity\n    \"checkout_root_realpath\": _git_rev_parse_path(\"--show-toplevel\", fallback=REPO_ROOT),\nscripts/run_quality_gate.py:173: in _git_rev_parse_path\n    completed = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00011887499999829743,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.425000000196633e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009828749999982733,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.070899999675248e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.804100000337485e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000512000000000512,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.866599999469145e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_quality_workflow_uploads_quality_gate_manifest_artifact",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002905420000018921,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005209159999992607,
      "longrepr": "tests/test_run_quality_gate.py:205: in test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree\n    subprocess.run([\"git\", \"init\", \"-q\"], cwd=repo_root, check=True)\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00013358300000021472,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.499999999538431e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003775829999952407,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.529099999928121e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_missing_guard_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.537500000230011e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00025991599999741766,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.770799999841984e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_preflight_rejects_untracked_guard_file",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002942499999960546,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.004437750000001017,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.654199999582943e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.88340000014864e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.62499999993338e-05,
      "longrepr": "tests/test_run_quality_gate.py:368: in test_guard_collect_only_keeps_analysis_and_history_in_default_collect\n    result = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00012008400000240727,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035229199999520233,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005925000000033265,
      "longrepr": "tests/test_run_quality_gate.py:415: in test_main_allow_dirty_worktree_marks_manifest_unbound\n    assert module.main([\"--allow-dirty-worktree\"]) == 0\nscripts/run_quality_gate.py:578: in main\n    manifest = _base_quality_gate_manifest(\nscripts/run_quality_gate.py:523: in _base_quality_gate_manifest\n    **_repo_identity(),\nscripts/run_quality_gate.py:192: in _repo_identity\n    \"checkout_root_realpath\": _git_rev_parse_path(\"--show-toplevel\", fallback=REPO_ROOT),\nscripts/run_quality_gate.py:173: in _git_rev_parse_path\n    completed = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00011400000000350019,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00032483300000052395,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006190000000003693,
      "longrepr": "tests/test_run_quality_gate.py:453: in test_main_writes_running_then_passed_manifest\n    assert module.main([]) == 0\nscripts/run_quality_gate.py:578: in main\n    manifest = _base_quality_gate_manifest(\nscripts/run_quality_gate.py:523: in _base_quality_gate_manifest\n    **_repo_identity(),\nscripts/run_quality_gate.py:192: in _repo_identity\n    \"checkout_root_realpath\": _git_rev_parse_path(\"--show-toplevel\", fallback=REPO_ROOT),\nscripts/run_quality_gate.py:173: in _git_rev_parse_path\n    completed = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.0001254579999994121,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00033299999999769625,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006555840000004309,
      "longrepr": "tests/test_run_quality_gate.py:489: in test_main_updates_manifest_to_failed_on_command_error\n    module.main([])\nscripts/run_quality_gate.py:578: in main\n    manifest = _base_quality_gate_manifest(\nscripts/run_quality_gate.py:523: in _base_quality_gate_manifest\n    **_repo_identity(),\nscripts/run_quality_gate.py:192: in _repo_identity\n    \"checkout_root_realpath\": _git_rev_parse_path(\"--show-toplevel\", fallback=REPO_ROOT),\nscripts/run_quality_gate.py:173: in _git_rev_parse_path\n    completed = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00011645800000081863,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003289160000008451,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005642919999999663,
      "longrepr": "tests/test_run_quality_gate.py:512: in test_main_rejects_dirty_worktree_by_default\n    module.main([])\nscripts/run_quality_gate.py:578: in main\n    manifest = _base_quality_gate_manifest(\nscripts/run_quality_gate.py:523: in _base_quality_gate_manifest\n    **_repo_identity(),\nscripts/run_quality_gate.py:192: in _repo_identity\n    \"checkout_root_realpath\": _git_rev_parse_path(\"--show-toplevel\", fallback=REPO_ROOT),\nscripts/run_quality_gate.py:173: in _git_rev_parse_path\n    completed = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00011587499999876627,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0004007920000006493,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006838750000000005,
      "longrepr": "tests/test_run_quality_gate.py:535: in test_main_rejects_dirty_worktree_when_require_clean_worktree\n    module.main([\"--require-clean-worktree\"])\nscripts/run_quality_gate.py:578: in main\n    manifest = _base_quality_gate_manifest(\nscripts/run_quality_gate.py:523: in _base_quality_gate_manifest\n    **_repo_identity(),\nscripts/run_quality_gate.py:192: in _repo_identity\n    \"checkout_root_realpath\": _git_rev_parse_path(\"--show-toplevel\", fallback=REPO_ROOT),\nscripts/run_quality_gate.py:173: in _git_rev_parse_path\n    completed = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00011737499999497913,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.58749999978636e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003662499999990132,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.695800000258487e-05,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_high_risk_untracked_source_diagnostic_covers_production_imported_py",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003357079999943835,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005548749999988445,
      "longrepr": "tests/test_run_quality_gate.py:576: in test_main_dirty_worktree_message_names_untracked_source\n    module.main([\"--require-clean-worktree\"])\nscripts/run_quality_gate.py:578: in main\n    manifest = _base_quality_gate_manifest(\nscripts/run_quality_gate.py:523: in _base_quality_gate_manifest\n    **_repo_identity(),\nscripts/run_quality_gate.py:192: in _repo_identity\n    \"checkout_root_realpath\": _git_rev_parse_path(\"--show-toplevel\", fallback=REPO_ROOT),\nscripts/run_quality_gate.py:173: in _git_rev_parse_path\n    completed = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00015629199999978027,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003931250000022146,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005554580000008968,
      "longrepr": "tests/test_run_quality_gate.py:611: in test_main_fails_when_tracked_status_changes_during_gate\n    module.main([])\nscripts/run_quality_gate.py:578: in main\n    manifest = _base_quality_gate_manifest(\nscripts/run_quality_gate.py:523: in _base_quality_gate_manifest\n    **_repo_identity(),\nscripts/run_quality_gate.py:192: in _repo_identity\n    \"checkout_root_realpath\": _git_rev_parse_path(\"--show-toplevel\", fallback=REPO_ROOT),\nscripts/run_quality_gate.py:173: in _git_rev_parse_path\n    completed = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00011958300000003419,
      "longrepr": "",
      "nodeid": "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.712500000181308e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.96660000016891e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.183399999784342e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_setup_hours_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.529199999974253e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.445900000073834e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.091699999657749e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_strict_blank_ext_days_rejected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.391699999610864e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.17499999972415e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2791999998948995e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_input_builder_strict_hours_and_ext_days.py::test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.562499999532065e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001669160000048464,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2250000003841706e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.266699999926459e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011904200000145693,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.112499999957663e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.316699999800221e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014083300000322652,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.358299999689507e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.312500000163254e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001142079999993939,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.266699999926459e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4875000004319645e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013470799999737437,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.241699999989578e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.770900000205529e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00018550000000061573,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7583000001006894e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8250000002904017e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00030141599999922164,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.741699999437742e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.4499999998161e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.899999999707916e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0375000001470198e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.429200000226729e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011604200000192577,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.570799999863539e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_inconsistent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.320799999784185e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013991600000196058,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.237500000352611e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_normalizes_percent_runtime_weight_triplet",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.299999999484271e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.612499999647525e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0207999998310697e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_start_dt",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.845800000590316e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.258299999866267e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2250000003841706e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_params_direct_call_contract.py::test_schedule_params_strict_mode_rejects_invalid_end_date",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003287090000014814,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.41848554100000257,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.912499999918055e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_logs_warning_when_latest_result_summary_is_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.000336499999995965,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4152499160000005,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.074999999825195e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_keeps_latest_history_when_summary_is_invalid",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00036620899999917356,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.43835004099999964,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.912499999918055e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_logs_warning_for_selected_and_list_summary_parse_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00035150000000072623,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.4238122090000047,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.837500000107411e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003421660000029192,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3911027500000017,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.704200000408946e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00031658399999656694,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3948277500000046,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.041600000296967e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00030941600000033986,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.3738404160000002,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.924999999886495e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003325419999953283,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.39640683300000035,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.98750000043924e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_system_history_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.4209000002126686e-05,
      "longrepr": "",
      "nodeid": "tests/test_schedule_summary_observability.py::test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 7.687499999775582e-05,
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
      "duration": 3.791700000022047e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.462499999708825e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.19580000009978e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_field_spec_registry_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0025603750000016134,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0016134580000013443,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.720900000331767e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_service_snapshot_includes_hidden_field_and_get_stays_single_arg",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.2000000000541604e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.3500000003859896e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.283299999878864e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__schedule_config_snapshot_hidden_field_defaults_to_yes",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.687500000637556e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.966699999504499e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.179200000147375e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5207999999897766e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.366699999598268e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.112499999957663e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8833999994380974e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.050000000039745e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.0500000001154604e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_config_field_spec_contract__config_helpers_reject_removed_valid_override_kwargs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.9417000002781606e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00823908400000306,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.416699999789444e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_uses_request_services",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.424999999727788e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.007390374999999949,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.120899999473295e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_marks_parse_failure_and_incomplete_trend",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.700000000137152e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0077459580000009964,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.837499999396869e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_route_surfaces_missing_requested_history",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.920799999932115e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.007064624999998159,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.0625000000081855e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_default_latest_does_not_synthesize_missing_selected",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.220899999931362e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00812183400000066,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.404199999821003e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_scheduler_analysis_route_contract__scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.416699999865159e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002215419999984647,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.4499999998161e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__calendar_pages_use_shared_holiday_default_efficiency_helper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.637500000053251e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.749999999935199e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.083399999326275e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__error_handlers_prefer_config_service_field_labels",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.908299999721976e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00022483400000083975,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.2541999999580185e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_page_requests_and_uses_visible_field_metadata",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.474999999752981e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 8.287499999681813e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.108399999973699e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_shows_shared_preset_degradation_notice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.399999999942338e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00013012500000542104,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.108399999973699e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_template_surfaces_shared_degraded_field_warning_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.654199999658658e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00011645899999734866,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.087500000020782e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_config_v2_template_matches_shared_metadata_and_warning_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.416700000258288e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.04589999990435e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.137499999894544e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_followup_root_collect.py::test_regression_sp05_followup_contracts__scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00038612499999857164,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5285662089999974,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.133300000030431e-05,
      "longrepr": "",
      "nodeid": "tests/test_scheduler_resource_dispatch_smoke.py::test_scheduler_resource_dispatch_page_data_export_and_dashboard_entry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.654199999976072e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007454160000008869,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.7541999994061825e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.837500000258842e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00028749999999888587,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5749999995005055e-05,
      "longrepr": "",
      "nodeid": "tests/test_sgs_internal_scoring_matches_execution.py::test_sgs_probe_none_efficiency_default_does_not_pollute_formal_counter",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.754200000116725e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.437500000089358e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.19580000009978e-05,
      "longrepr": "",
      "nodeid": "tests/test_skill_level_normalization_contract.py::test_normalize_skill_level_canonical3_and_legacy_aliases",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.870799999816654e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.40830000051551e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.237500000352611e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_utilization_only_counts_internal_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.3457999997210663e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.42089999942641e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.120800000289137e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_compute_downtime_impact_only_counts_internal_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.270800000620966e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004268750000022692,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.333400000116171e-05,
      "longrepr": "",
      "nodeid": "tests/test_source_merge_mode_constants.py::test_target_files_have_no_source_merge_mode_quoted_literals",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8624999994851805e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008346250000030864,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.570899999833955e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.9166000000534495e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.266699999699313e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.441700000195169e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_package_init_relative_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.620799999737301e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00014133300000196414,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.300000000194814e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_legacy_import_scan_catches_dynamic_import_strings",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.34580000003848e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.42162170799999643,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.804199999914772e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_production_code_does_not_grow_legacy_wrapper_imports",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.579100000512426e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.008121166000002233,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.133400000152278e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_topology_and_compatibility_matrix",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.6707999999284766e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021100000000018326,
      "longrepr": "tests/test_sp05_path_topology_contract.py:527: in test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint\n    payload = _import_module_isolation_probe(old_name)\ntests/test_sp05_path_topology_contract.py:289: in _import_module_isolation_probe\n    completed = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.00011845800000287454,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.9332999999762706e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00019383400000094753,
      "longrepr": "tests/test_sp05_path_topology_contract.py:536: in test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint\n    payload = _import_module_isolation_probe(\"web.routes.scheduler_excel_batches\")\ntests/test_sp05_path_topology_contract.py:289: in _import_module_isolation_probe\n    completed = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 0.0001336670000000595,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.93750000032378e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 6.095799999883411e-05,
      "longrepr": "tests/test_sp05_path_topology_contract.py:544: in test_sp05_scheduler_domain_package_import_stays_passive\n    payload = _import_module_isolation_probe(\"web.routes.domains.scheduler\")\ntests/test_sp05_path_topology_contract.py:289: in _import_module_isolation_probe\n    completed = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 9.900000000584441e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.766600000039034e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.691599999835262e-05,
      "longrepr": "tests/test_sp05_path_topology_contract.py:559: in test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects\n    payload = _import_module_isolation_probe(module_name)\ntests/test_sp05_path_topology_contract.py:289: in _import_module_isolation_probe\n    completed = subprocess.run(\n/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/subprocess.py:493: in run\n    with Popen(*popenargs, **kwargs) as process:\nE   AttributeError: __enter__",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "failed",
      "when": "call"
    },
    {
      "duration": 9.024999999951433e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3542000000229564e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00020100000000411455,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.45420000016361e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_safe_next_url_has_one_policy_module",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00031574999999861575,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010732920000009472,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.766699999692037e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00028079100000155677,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00033625000000370164,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.416700000575702e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.670800000321606e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0021996669999992946,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.591700000375567e-05,
      "longrepr": "",
      "nodeid": "tests/test_sp05_path_topology_contract.py::test_sp05_documentation_uses_migrated_scheduler_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.67910000025995e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0012590419999938263,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.687499999927013e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_normalizes_remark_text",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.837500000258842e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009662920000010899,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.729099999816299e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.662499999990132e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009232910000065431,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.566700000590117e-05,
      "longrepr": "",
      "nodeid": "tests/test_supplier_excel_import_remark_normalization.py::test_supplier_excel_import_rejects_blank_default_days",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011216600000096832,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0010407499999942615,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.108300000169265e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00013058300000068357,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007678750000010837,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.8250000005321e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[migrate-inline-facts-refresh_migrate_inline_facts-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011458300000555255,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006520000000023174,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.504100000626067e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[scan-startup-baseline-refresh_scan_startup_baseline-False]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00011095899999702397,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006894160000001648,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.429199999757884e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode[refresh-auto-fields-refresh_auto_fields-True]",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.362499999492456e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006278339999994387,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.7749999996303814e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.3250000000559794e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00021491700000098035,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.129199999880484e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.245900000261372e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015366699999930233,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.891599999406026e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_refresh_auto_fields_prunes_resolved_complexity_entry",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.208300000234203e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007609580000007554,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.583400000119809e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_command_updates_manual_fields",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.554199999911134e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0008906250000038085,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5916999998164556e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_set_entry_fields_rejects_invalid_status_choice",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.949999999823376e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007210829999948487,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.537500000230011e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_upsert_risk_command_dispatches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 8.429200000392711e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0006122500000032005,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.6083000004036876e-05,
      "longrepr": "",
      "nodeid": "tests/test_sync_debt_ledger.py::test_delete_risk_command_dispatches",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.6832999995795035e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.000253332999996303,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_operation_log_service_list_and_delete",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.38750000068444e-05,
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
      "duration": 0.00013479200000432456,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.716700000211404e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_job_state_query_service_get_and_map",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.395799999912242e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0001277499999972065,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.320899999437188e-05,
      "longrepr": "",
      "nodeid": "tests/test_system_services.py::test_system_config_service_get_value",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00034737499999693,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.5540148340000002,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 8.520900000519305e-05,
      "longrepr": "",
      "nodeid": "tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.679199999912953e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007505410000021584,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.6084000004498193e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_prefers_cookie_over_db",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.01249999981701e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003441669999943997,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.595900000163965e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.741699999437742e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004055409999992321,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.075000000369755e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_reads_db_when_cookie_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 6.587499999710644e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005427920000045106,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.3333000000700395e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_falls_back_to_default_for_invalid_db_value",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.5082999999456206e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003739169999974479,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.016700000164519e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.204199999297998e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003833749999984093,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.979099999895652e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_invalid_db_value_once_per_request",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.454200000087894e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00036858300000375266,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.004099999832533e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_cookie_read_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.525000000337286e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 3.883299999785095e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 2.9707999999573076e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_without_request_context",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.395899999958374e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00036366700000201035,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.383300000336931e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.450000000133514e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004180419999997298,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.46670000013205e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_db_exists_but_services_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.5916999998164556e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003182500000065147,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.5167000000058124e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.416700000258288e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003879169999976284,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.349999999358033e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_raises_when_system_config_service_access_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.916699999630737e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004517500000034147,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.983299999532619e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_get_ui_mode_logs_warning_when_db_read_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.554200000621677e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003036250000008067,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.312500000163254e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.504200000037372e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002756660000002853,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.262500000289492e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.51250000029313e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002854589999969903,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.900000000101045e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_safe_url_for_logs_warning_on_non_build_error",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.0916999995820333e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007600409999994895,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_warns_once_when_v2_env_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.687499999533884e-05,
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
      "duration": 0.0006210000000024252,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.399999999942338e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_sets_degraded_context_when_v2_env_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003585420000007389,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0013084590000005392,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.387499999898182e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_marks_base_loader_resolution_as_degraded",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.929199999599177e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0005990829999973357,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.570800000180952e-05,
      "longrepr": "",
      "nodeid": "tests/test_ui_mode.py::test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 3.8291999999273685e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 4.429100000180597e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.3457999997210663e-05,
      "longrepr": "",
      "nodeid": "tests/test_value_domains_consistency.py::test_value_domains_consistent_with_model_enums",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 9.816699999731782e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00028829099999683194,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.520799999914061e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_runtime_base_dir_fallback_logs_to_stderr",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0003012920000031727,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002838750000009327,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.4957999996597664e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_prefers_explicit_env",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002842499999999859,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00022200000000083264,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.4165999995016136e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_shared_data_root_uses_registry_only_when_frozen",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00023933300000322788,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002813340000002995,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.7416999997551557e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_prelaunch_log_dir_uses_shared_root",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00024874999999724423,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.002377166999998792,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.783300000354984e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_apply_runtime_config_uses_shared_root_for_all_data_dirs",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.2499999995347935e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0002492909999958215,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.166600000132803e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_current_runtime_owner_uses_computername_when_userdomain_missing",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002482920000019817,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00022708400000226447,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.5292000002916666e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_default_chrome_profile_dir_prefers_localappdata_profile_name",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00024179200000418177,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0007238749999984861,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.3542000000229564e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0002498749999944039,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 12.12251475,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0006227079999945317,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.001516958999999929,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0021592920000017557,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00016391699999473985,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.0008806250000006344,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.05103641700000594,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.00010079199999779576,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00044883300000009285,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0009312500000007162,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 7.025000000027148e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_runtime_from_dir_waits_for_pid_exit_before_success",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 7.779199999902175e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00033016599999768914,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 5.733300000088093e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.908400000402935e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00041158399999829953,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.07079999994653e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.4750000003878085e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00033833300000196687,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.508299999628207e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_bat_contains_json_health_probe_and_owner_fallback",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.475000000070395e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00024183400000055144,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.287499999833244e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.020799999755354e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003191249999972001,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.0667000000382814e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.358400000370466e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012058299999750943,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.925000000037926e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_package_script_exposes_explicit_best_effort_cleanup_wrapper",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.066600000385279e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003995419999966998,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 6.10420000057843e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installer_uninstall_stop_checks_multiple_runtime_roots",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 5.358300000324334e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00017400000000122873,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.470900000086431e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_main_installer_contains_precleanup_and_skip_legacy_migration",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5583999998655145e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00036520799999806286,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.02499999978545e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_legacy_installer_uses_runtime_root_stop_contract",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.308400000496704e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0004290420000003792,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.241699999596449e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_installers_fail_closed_on_silent_uninstall_and_retry_delete",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3415999996909704e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012479200000115043,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.991700000227638e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.137500000211958e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010525000000427553,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 3.850000000227283e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_stop_helper_uses_current_user_profile_path_marker",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.258400000622942e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.0003623750000016912,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.26669999953333e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_build_scripts_guard_vendor_and_launcher_path",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.475000000070395e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00012258300000667077,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.608299999375731e-05,
      "longrepr": "",
      "nodeid": "tests/test_win7_launcher_runtime_paths.py::test_chrome_installer_remains_non_target_for_precleanup",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 0.00015904099999630716,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00019391699999715684,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.3333000000700395e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_to_yes_no_wide_truthy_and_falsy_and_default",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.862499999802594e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 9.10830000009355e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 4.049999999722331e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_system_config_yes_no_unknown_is_no",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.3665999996278515e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_plugin_yes_no_unknown_follows_default_param",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 5.3417000003719295e-05,
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
      "duration": 8.208300000234203e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00015604100000388144,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 9.099999999762076e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough",
      "outcome": "passed",
      "when": "teardown"
    },
    {
      "duration": 4.5042000003547855e-05,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises",
      "outcome": "passed",
      "when": "setup"
    },
    {
      "duration": 0.00010487499999811689,
      "longrepr": "",
      "nodeid": "tests/test_yesno_normalization_contract.py::test_calendar_admin_yesno_is_narrow_unknown_raises",
      "outcome": "passed",
      "when": "call"
    },
    {
      "duration": 0.0003747910000058141,
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
      "main_style_isolation_candidate": 4,
      "required_or_quality_gate_self_failure": 27
    },
    "collected_count": 578,
    "collection_error_count": 0,
    "failed_nodeid_count": 36,
    "outcome_counts": {
      "call:failed": 36,
      "call:passed": 542,
      "setup:passed": 578,
      "teardown:passed": 578
    }
  }
}
```
<!-- APS-FULL-PYTEST-BASELINE:END -->
