"""Explicit retained regression inventory, grouped by the behavior each group owns."""

from __future__ import annotations

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Gate meta selftests are retired; the compatibility constant names no test.
QUALITY_GATE_SELFTEST_PATH = ""

QUALITY_GATE_STARTUP_REGRESSION_ARGS = (
    'tests/app_runtime/test_app_new_ui_create_app_smoke.py',
    'tests/app_runtime/test_frontend_offline_static_assets.py',
    'tests/app_runtime/test_launcher_startup.py',
    'tests/app_runtime/test_portable_runtime_paths.py',
    'tests/app_runtime/test_runtime_db_scope_lock.py',
    'tests/app_runtime/test_runtime_server_binding.py',
)

_SCHEDULER_TESTS = (
    'tests/algorithm/test_auto_assign_fixed_operator_respects_op_type.py',
    'tests/algorithm/test_decode_checkpoint_content_evidence.py',
    'tests/algorithm/test_dispatch_blocking_consistency.py',
    'tests/algorithm/test_due_exclusive_consistency.py',
    'tests/algorithm/test_efficiency_greater_than_one_shortens_hours.py',
    'tests/algorithm/test_graph_repair_real_decode.py',
    'tests/algorithm/test_greedy_scheduler_base_date.py',
    'tests/algorithm/test_incomplete_batch_objective_completed_subset_contract.py',
    'tests/algorithm/test_optimizer_end_to_end_matrix_contract.py',
    'tests/algorithm/test_optional_ready_constraint.py',
    'tests/algorithm/test_operation_effort.py',
    'tests/algorithm/test_schedule_persistence_auto_assign_contract.py',
    'tests/algorithm/test_scheduler_reject_nonfinite_and_invalid_status.py',
    'tests/algorithm/test_sgs_internal_scoring_matches_execution.py',
    'tests/algorithm/test_sgs_priority_pruning.py',
    'tests/algorithm/test_sgs_working_hour_slack_dispatch.py',
    'tests/algorithm/test_weighted_tardiness_objective.py',
    'tests/candidate/test_graph_ready_capacity_facts.py',
    'tests/candidate/test_optimizer_process_evidence.py',
    'tests/candidate/test_scheduler_candidate_rule_pool_end_to_end.py',
    'tests/candidate/test_scheduler_selection_evidence.py',
    'tests/candidate/test_shared_schedule_archive.py',
    'tests/gantt/test_gantt_adapter_contract.py',
    'tests/gantt/test_gantt_explicit_dependencies.py',
    'tests/gantt/test_gantt_graph_rendering.py',
    'tests/schedule/route_view/test_scheduler_plan_identity_evidence_contract.py',
    'tests/schedule/service/test_frozen_external_seed_metadata_integration.py',
    'tests/schedule/service/test_operation_effort_input.py',
    'tests/schedule/service/test_schedule_service_reschedulable_contract.py',
    'tests/scheduler_analysis/test_plan_vs_actual_review.py',
    'tests/scheduler_analysis/test_scheduler_delay_diagnosis_contract.py',
    'tests/scheduler_graph/test_scheduler_graph_cycle_policy_contract.py',
    'tests/scheduler_graph/test_scheduler_graph_report_mode_service_contract.py',
)

_WORKBENCH_TESTS = (
    'tests/workbench/test_archived_calendar.py',
    'tests/workbench/test_batch_actions.py',
    'tests/workbench/test_batch_material_row_keys.py',
    'tests/workbench/test_bulk_copy_allocation.py',
    'tests/workbench/test_calendar_file_api.py',
    'tests/workbench/test_calendar_period_defaults.py',
    'tests/workbench/test_candidate_comparison_baseline.py',
    'tests/workbench/test_changeover_projection.py',
    'tests/workbench/test_calibration_adoption_transactions.py',
    'tests/workbench/test_calibration_adoption_reuse.py',
    'tests/workbench/test_quota_continuous_revision.py',
    'tests/workbench/test_commands.py',
    'tests/workbench/test_completion_scope.py',
    'tests/workbench/test_dashboard_api.py',
    'tests/workbench/test_dashboard_external_handling_atomic.py',
    'tests/workbench/test_decision_baseline.py',
    'tests/workbench/test_decision_export_budget.py',
    'tests/workbench/test_decision_export_process.py',
    'tests/workbench/test_decision_history_api.py',
    'tests/workbench/test_decision_read_models.py',
    'tests/workbench/test_delivery_projection.py',
    'tests/workbench/test_display_keys.py',
    'tests/workbench/test_delivery_trial_projection.py',
    'tests/workbench/test_direct_page_snapshot.py',
    'tests/workbench/test_execution_ledger_commands.py',
    'tests/workbench/test_execution_dependency_prefetch.py',
    'tests/workbench/test_execution_plan_read_scope.py',
    'tests/workbench/test_field_report_void_api.py',
    'tests/workbench/test_field_workspace_api.py',
    'tests/workbench/test_gantt_graph.py',
    'tests/workbench/test_import_source_content.py',
    'tests/workbench/test_legacy_plan_range.py',
    'tests/workbench/test_legacy_resource_projection.py',
    'tests/workbench/test_master_material_readiness.py',
    'tests/workbench/test_material_api.py',
    'tests/workbench/test_material_stage_release.py',
    'tests/workbench/test_operator_calendar_api.py',
    'tests/workbench/test_operator_calendar_bulk_reads.py',
    'tests/workbench/test_operator_machine_changes.py',
    'tests/workbench/test_official_scope_coverage.py',
    'tests/workbench/test_outsourcing_atomic.py',
    'tests/workbench/test_outsourcing_command_capture.py',
    'tests/workbench/test_piece_chain_boundaries.py',
    'tests/workbench/test_piece_chain_end_to_end.py',
    'tests/workbench/test_piece_downstream_api.py',
    'tests/workbench/test_plan_adoption_baseline_api.py',
    'tests/workbench/test_plan_metadata_reads.py',
    'tests/workbench/test_plan_query_api.py',
    'tests/workbench/test_point_downstream_api.py',
    'tests/workbench/test_preflight_api.py',
    'tests/workbench/test_process_collection_api.py',
    'tests/workbench/test_process_default_group_reads.py',
    'tests/workbench/test_process_file_api_transactions.py',
    'tests/workbench/test_process_group_api.py',
    'tests/workbench/test_process_route_confirm.py',
    'tests/workbench/test_read_projection_cpu_equivalence.py',
    'tests/workbench/test_relation_import_grouping.py',
    'tests/workbench/test_request_lifecycle_http.py',
    'tests/workbench/test_report_downtime_index.py',
    'tests/workbench/test_resource_api.py',
    'tests/workbench/test_resource_file_api.py',
    'tests/workbench/test_resource_file_captured_projection.py',
    'tests/workbench/test_resource_projection.py',
    'tests/workbench/test_resource_summary.py',
    'tests/workbench/test_resource_write_capture.py',
    'tests/workbench/test_run_candidate_adoption_atomic.py',
    'tests/workbench/test_run_candidate_api.py',
    'tests/workbench/test_run_compute_integration.py',
    'tests/workbench/test_run_decision_api.py',
    'tests/workbench/test_run_decision_completion_api.py',
    'tests/workbench/test_run_decision_impact_api.py',
    'tests/workbench/test_run_decision_metrics.py',
    'tests/workbench/test_run_decision_preparation_api.py',
    'tests/workbench/test_run_decision_process_api.py',
    'tests/workbench/test_run_decision_resource_api.py',
    'tests/workbench/test_run_decision_recommendation.py',
    'tests/workbench/test_run_history_api.py',
    'tests/workbench/test_run_jobs_atomic.py',
    'tests/workbench/test_run_runtime.py',
    'tests/workbench/test_scheduler_execution_ledger_guards.py',
    'tests/workbench/test_subsecond_candidate_flow.py',
    'tests/workbench/test_system_maintenance_restore.py',
    'tests/workbench/test_transport.py',
    'tests/workbench/test_trial_adoption_api.py',
    'tests/workbench/test_trial_adoption_atomic.py',
    'tests/workbench/test_trial_effort_projection.py',
    'tests/workbench/test_trial_history_receipts.py',
    'tests/workbench/test_trial_lifecycle.py',
    'tests/workbench/test_trial_resource_overlap.py',
    'tests/workbench/test_trial_validation.py',
    'tests/workbench/test_ui_refinement_node_contracts.py',
)

_RUNTIME_TESTS = (
    *QUALITY_GATE_STARTUP_REGRESSION_ARGS,
    'tests/app_runtime/test_codex_hook_authorization.py',
    'tests/web_pages/test_system_health_route.py',
    'tests/web_pages/test_system_runtime_logs_page.py',
)

_DATA_IO_TESTS = (
    'tests/config/test_config_field_spec_contract.py',
    'tests/config/test_config_snapshot_strict_numeric.py',
    'tests/config/test_schedule_config_startup.py',
    'tests/excel_data_io/test_excel_import_hardening.py',
    'tests/excel_data_io/test_operator_machine_exception_paths.py',
)

_DOMAIN_TESTS = (
    'tests/material/test_material_finite_quantity_contract.py',
    'tests/migration_db/test_efficiency_indexes_v44.py',
    'tests/migration_db/test_schema_parity.py',
    'tests/migration_db/test_single_pass_v43.py',
    'tests/migration_db/test_transaction_savepoint_nested.py',
    'tests/models_domain/test_query_services.py',
    'tests/operation_execution/test_operation_execution_state_flow.py',
)

_CALENDAR_TESTS = (
    'tests/calendar_maintenance/test_calendar_effective_segments.py',
    'tests/calendar_maintenance/test_calendar_periods.py',
    'tests/calendar_maintenance/test_exit_backup_maintenance.py',
    'tests/calendar_maintenance/test_freeze_window_bounds.py',
)

QUALITY_GATE_GUARD_TESTS = (
    *_SCHEDULER_TESTS,
    *_WORKBENCH_TESTS,
    *_RUNTIME_TESTS,
    *_DATA_IO_TESTS,
    *_DOMAIN_TESTS,
    *_CALENDAR_TESTS,
)
QUALITY_GATE_REQUIRED_TESTS = QUALITY_GATE_GUARD_TESTS

_TEST_ENV_KEYS = ("APS_ENV", "APS_DB_PATH", "APS_LOG_DIR", "APS_BACKUP_DIR", "APS_EXCEL_TEMPLATE_DIR", "SECRET_KEY")


def _group(group_id, label, targets, scopes, env_keys=()):
    return {
        "group_id": group_id,
        "label": label,
        "target_paths": targets,
        "input_file_scopes": (*targets, *scopes),
        "env_keys": (*_TEST_ENV_KEYS, *env_keys),
    }


REQUIRED_REGRESSION_GROUPS = (
    _group(
        'scheduler', 'Scheduling, candidates, dispatch, and analysis', _SCHEDULER_TESTS,
        (
            'tests/algorithm/**/*.py',
            'tests/candidate/**/*.py',
            'tests/gantt/**/*.py',
            'tests/schedule/**/*.py',
            'tests/scheduler_analysis/**/*.py',
            'tests/scheduler_graph/**/*.py',
            'core/algorithm_contracts/**/*.py',
            'core/algorithm_runtime/**/*.py',
            'core/algorithms/**/*.py',
            'core/shared/local_datetime.py',
            'core/services/scheduler/**/*.py',
            'core/services/batch/**/*.py',
            'web/routes/scheduler*.py',
            'web/viewmodels/scheduler*.py',
        ),
    ),
    _group(
        'workbench', 'Workbench API, commands, adoption, and UI Node contracts', _WORKBENCH_TESTS,
        (
            'tests/workbench/**/*.py',
            'tests/**/*.cjs',
            'core/services/workbench/**/*.py',
            'core/shared/local_datetime.py',
            'web/routes/workbench/**/*.py',
            'web/viewmodels/workbench/**/*.py',
            'frontend/workbench/**/*',
            'templates/workbench/**/*.html',
            'static/workbench/**/*',
        ),
        env_keys=('WORKBENCH_NODE', 'NODE_PATH', 'NODE_OPTIONS'),
    ),
    _group(
        'runtime', 'Application startup, runtime identity, system pages, and host hooks', _RUNTIME_TESTS,
        (
            'tests/app_runtime/**/*.py',
            '.codex/hooks/**/*.py',
            '.codex/hooks.json',
            'tests/web_pages/**/*.py',
            'web/**/*.py',
            'plugins/**/*.py',
            'desktop/**/*.py',
            'assets/**/*',
            'installer/**/*',
            'build_win7*.bat',
            'templates/**/*.html',
            'static/**/*',
        ),
        env_keys=('APS_HOST', 'APS_PORT', 'APS_SHARED_DATA_ROOT', 'APS_STATIC_VERSION', 'WERKZEUG_RUN_MAIN'),
    ),
    _group(
        'data_io', 'Configuration and atomic Excel imports', _DATA_IO_TESTS,
        (
            'tests/config/**/*.py',
            'tests/excel_data_io/**/*.py',
            'config.py',
            'core/services/config/**/*.py',
            'core/services/excel/**/*.py',
            'core/services/imports/**/*.py',
            'data/**/*.py',
            'web/routes/**/*.py',
        ),
    ),
    _group(
        'domain', 'Models, migration, and execution transactions', _DOMAIN_TESTS,
        (
            'tests/material/**/*.py',
            'tests/migration_db/**/*.py',
            'tests/models_domain/**/*.py',
            'tests/operation_execution/**/*.py',
            'core/services/**/*.py',
            'core/models/**/*.py',
            'core/infrastructure/**/*.py',
            'data/**/*.py',
            'web/routes/**/*.py',
        ),
    ),
    _group(
        'calendar', 'Calendar, freeze windows, and exit backup', _CALENDAR_TESTS,
        (
            'tests/calendar_maintenance/**/*.py',
            'core/services/scheduler/calendar/**/*.py',
            'core/services/maintenance/**/*.py',
            'core/services/common/**/*.py',
            'core/infrastructure/**/*.py',
            'data/**/*.py',
        ),
    ),
)

# Browser and supplemental test lanes were retired with their test files.
SUPPLEMENTAL_REGRESSION_GROUPS = ()

# Shared support changes select all retained groups; no second helper target inventory.
TEST_ONLY_HELPER_IMPACT = {}

REQUIRED_REGRESSION_COMMON_SCOPES = {
    "input_file_scopes": (
        "tests/conftest.py", "conftest.py", "tests/_support/**/*.py",
        "schema.sql", "app.py", "app_new_ui.py", "core/errors.py",
        "core/infrastructure/**/*.py", "core/services/common/**/*.py", "core/shared/**/*.py",
        "web/bootstrap/**/*.py",
    ),
    "config_file_scopes": (
        "pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini", ".gitignore",
        "pyrightconfig*.json", ".pre-commit-config.yaml", ".github/workflows/*.yml",
        ".codestable/checkup/import_cycles_production_baseline.json",
        ".codestable/checkup/import_cycles_with_tests_baseline.json",
    ),
    "tool_file_scopes": ("tools/**/*.py", "scripts/**/*.py", ".codestable/tools/**/*.py"),
    "dependency_file_scopes": ("requirements*.txt", "poetry.lock", "uv.lock", "Pipfile.lock"),
    "env_keys": (
        "python_executable_realpath", "python_version", "pytest_version",
        "pytest_plugin_distribution_versions", "platform", "git_executable_realpath", "git_version",
        "PYTHONPATH", "PYTHONUTF8", "PYTHONIOENCODING",
        "PYTEST_ADDOPTS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PYTEST_PLUGINS",
    ),
}
