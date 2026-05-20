from __future__ import annotations

import hashlib
import json
import os
import subprocess
from typing import Any, Dict, List, Mapping, Optional, Sequence

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

QUALITY_GATE_SELFTEST_PATH = "tests/test_run_quality_gate.py"

QUALITY_GATE_STARTUP_REGRESSION_ARGS = (
    "tests/regression_runtime_probe_resolution.py",
    "tests/test_win7_launcher_runtime_paths.py",
    "tests/regression_runtime_contract_launcher.py",
    "tests/regression_entrypoint_meta_failure_visible.py",
    "tests/test_launcher_observability.py",
    "tests/regression_runtime_lock_reloader_parent_skip.py",
    "tests/regression_startup_host_portfile.py",
    "tests/regression_startup_host_portfile_new_ui.py",
    "tests/regression_plugin_bootstrap_config_failure_visible.py",
    "tests/regression_plugin_bootstrap_injects_config_reader.py",
    "tests/regression_plugin_bootstrap_telemetry_failure_visible.py",
    "tests/regression_app_new_ui_secret_key_runtime_ensure.py",
    "tests/regression_app_new_ui_session_contract.py",
    "tests/regression_app_new_ui_security_hardening_enabled.py",
    "tests/test_app_factory_runtime_env_refresh.py",
    "tests/regression_runtime_stop_cli.py",
)

QUALITY_GATE_GUARD_TESTS = (
    "tests/test_sp05_path_topology_contract.py",
    "tests/test_schedule_input_builder_strict_hours_and_ext_days.py",
    "tests/regression_scheduler_wrapper_import_order_contract.py",
    "tests/test_scheduler_route_registration_contract.py",
    "tests/test_scheduler_routes_still_registered_by_factory.py",
    "tests/test_history_summary_parser.py",
    "tests/test_phase6_no_result_summary_route_parser.py",
    "tests/regression_scheduler_bp_result_summary_guard.py",
    "tests/test_version_resolution_contract.py",
    "tests/test_phase6_no_route_version_parser.py",
    "tests/test_evidence_audit_entrypoints.py",
    "tests/regression_schedule_orchestrator_contract.py",
    "tests/test_schedule_summary_observability.py",
    "tests/regression_sp06_no_duplicate_defs.py",
    "tests/test_schedule_params_direct_call_contract.py",
    "tests/regression_scheduler_config_route_contract.py",
    "tests/regression_config_field_spec_contract.py",
    "tests/regression_scheduler_config_manual_url_normalization.py",
    "tests/regression_config_service_active_preset_custom_sync.py",
    "tests/regression_config_snapshot_strict_numeric.py",
    "tests/regression_config_snapshot_projection_sync.py",
    "tests/regression_config_service_component_contract.py",
    "tests/regression_config_service_relaxed_missing_visibility.py",
    "tests/regression_apply_preset_adjusted_marks_custom.py",
    "tests/regression_scheduler_batches_degraded_visibility.py",
    "tests/regression_scheduler_batch_template_warning_surface.py",
    "tests/regression_scheduler_objective_labels.py",
    "tests/regression_objective_projection_contract.py",
    "tests/regression_scheduler_analysis_route_contract.py",
    "tests/regression_scheduler_analysis_observability.py",
    "tests/regression_analysis_page_version_default_latest.py",
    "tests/regression_scheduler_analysis_vm_legacy_summary_bridge.py",
    "tests/regression_scheduler_week_plan_summary_observability.py",
    "tests/regression_system_history_route_contract.py",
    "tests/regression_sp05_followup_contracts.py",
    "tests/regression_scheduler_user_visible_messages.py",
    "tests/regression_route_version_normalizers_contract.py",
    "tests/regression_gantt_page_version_default_latest.py",
    "tests/regression_gantt_default_version_span.py",
    "tests/regression_reports_page_version_default_latest.py",
    "tests/regression_week_plan_filename_uses_normalized_version.py",
    "tests/regression_gantt_calendar_load_failed_degraded.py",
    "tests/regression_gantt_bad_time_rows_surface_degraded.py",
    "tests/regression_scheduler_result_navigation_contract.py",
    "tests/regression_gantt_contract_snapshot.py",
    "tests/regression_gantt_critical_chain_unavailable.py",
    "tests/regression_gantt_critical_chain_provider.py",
    "tests/regression_scheduler_candidate_gantt_plan_role_contract.py",
    "tests/regression_quality_gate_scan_contract.py",
    "tests/regression_request_services_contract.py",
    "tests/regression_request_services_lazy_construction.py",
    "tests/regression_request_services_failure_propagation.py",
    "tests/regression_factory_request_lifecycle_observability.py",
    "tests/regression_system_request_services_contract.py",
    "tests/regression_maintenance_window_mutex.py",
    "tests/regression_optimizer_seed_results_contract.py",
    "tests/regression_optimizer_seed_boundary_contract.py",
    "tests/regression_optimizer_runtime_seam_contract.py",
    "tests/regression_optimizer_outcome_type_contract.py",
    "tests/regression_optimizer_public_summary_projection_contract.py",
    "tests/regression_schedule_input_collector_contract.py",
    "tests/regression_schedule_params_read_failure_visible.py",
    "tests/regression_schedule_service_strict_snapshot_guard.py",
    "tests/regression_schedule_config_snapshot_optional_guard.py",
    "tests/regression_schedule_service_facade_delegation.py",
    "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py",
    "tests/regression_schedule_persistence_reschedulable_contract.py",
    "tests/regression_schedule_optimizer_cfg_snapshot_contract.py",
    "tests/regression_schedule_summary_cfg_snapshot_contract.py",
    "tests/regression_schedule_summary_algo_warnings_union.py",
    "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py",
    "tests/regression_schedule_summary_freeze_state_contract.py",
    "tests/regression_schedule_summary_overdue_warning_append_fallback.py",
    "tests/regression_schedule_summary_v11_contract.py",
    "tests/regression_schedule_summary_merge_context_degraded_code.py",
    "tests/regression_schedule_summary_input_fallback_contract.py",
    "tests/regression_scheduler_run_surfaces_resource_pool_warning.py",
    "tests/test_scheduler_run_view_result_contract.py",
    "tests/test_schedule_template_lookup_contract.py",
    "tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py",
    "tests/regression_resource_dispatch_bad_time_rows_surface_degraded.py",
    "tests/regression_resource_dispatch_export_surfaces_degraded.py",
    "tests/regression_error_field_label_source.py",
    "tests/test_run_full_selftest_report_metadata.py",
    "tests/test_check_full_test_debt.py",
    "tests/test_full_test_debt_registry_contract.py",
    "tests/test_fast_static_precheck.py",
    "tests/test_git_hook_checks.py",
    "tests/test_benchmark_full_test_debt_shards.py",
    "tests/test_quality_workflow_cache.py",
    "tests/test_long_gate_cli_controls.py",
    "tests/test_long_gate_quickref_cache.py",
    "tests/test_ui_mode.py",
    "tests/regression_safe_next_url_hardening.py",
    "tests/regression_safe_next_url_observability.py",
    "tests/test_holiday_default_efficiency_read_guard.py",
    "tests/test_excel_import_hardening.py",
    "tests/test_excel_utils_compare_digest_guard.py",
    "tests/regression_excel_hidden_payload_contract.py",
    "tests/regression_scheduler_excel_batches_preview_baseline_precision.py",
    "tests/regression_error_boundary_contract.py",
    "tests/regression_mirror_template_sync.py",
    "tests/regression_scheduler_ui_range_feedback_contract.py",
    "tests/regression_scheduler_route_enforce_ready_tristate.py",
    "tests/test_ui_browser_geometry_env.py",
    "tests/test_ui_geometry_html_contract.py",
)

QUALITY_GATE_REQUIRED_TESTS = (QUALITY_GATE_SELFTEST_PATH, *QUALITY_GATE_GUARD_TESTS)

TEST_ONLY_HELPER_IMPACT = {
    "tests/long_gate_cache_helpers.py": (
        "tests/test_long_gate_debt_ledger_cache.py",
        "tests/test_long_gate_required_regression_cache.py",
        "tests/test_long_gate_startup_regression_cache.py",
    ),
}

REQUIRED_REGRESSION_COMMON_SCOPES = {
    "input_file_scopes": (
        "tests/conftest.py",
        "conftest.py",
        "tests/main_style_regression_runner.py",
        "tests/runtime_cleanup_helper.py",
    ),
    "config_file_scopes": (
        "pytest.ini",
        "pyproject.toml",
        "setup.cfg",
        "tox.ini",
        ".gitignore",
        "tools/test_registry.py",
        "tools/quality_gate_shared.py",
        "tools/quality_gate_support.py",
        "scripts/run_quality_gate.py",
    ),
    "tool_file_scopes": (
        "scripts/run_quality_gate.py",
        "tools/fast_static_precheck.py",
        "tools/long_gate_cache.py",
        "tools/long_gate_collect.py",
        "tools/long_gate_fingerprint.py",
        "tools/long_gate_full_test_debt.py",
        "tools/long_gate_manifest.py",
        "tools/long_gate_paths.py",
        "tools/long_gate_schema.py",
        "tools/long_gate_summary.py",
        "tools/verify_required_regressions_from_full_test_debt.py",
        "tools/test_registry.py",
        "tools/quality_gate_shared.py",
        "tools/quality_gate_support.py",
    ),
    "dependency_file_scopes": (
        "requirements*.txt",
        "requirements-dev*.txt",
        "poetry.lock",
        "uv.lock",
        "Pipfile.lock",
    ),
    "env_keys": (
        "python_executable_realpath",
        "python_version",
        "pytest_version",
        "pytest_plugin_distribution_versions",
        "platform",
        "git_executable_realpath",
        "git_version",
        "PYTHONPATH",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
        "PYTEST_ADDOPTS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTEST_PLUGINS",
    ),
}

REQUIRED_REGRESSION_GROUPS = (
    {
        "group_id": "quality_gate",
        "label": "Quality gate and long gate contracts",
        "target_paths": (
            "tests/test_run_quality_gate.py",
            "tests/test_sp05_path_topology_contract.py",
            "tests/test_evidence_audit_entrypoints.py",
            "tests/regression_sp06_no_duplicate_defs.py",
            "tests/regression_quality_gate_scan_contract.py",
            "tests/test_run_full_selftest_report_metadata.py",
            "tests/test_check_full_test_debt.py",
            "tests/test_full_test_debt_registry_contract.py",
            "tests/test_fast_static_precheck.py",
            "tests/test_git_hook_checks.py",
            "tests/test_benchmark_full_test_debt_shards.py",
            "tests/test_quality_workflow_cache.py",
            "tests/test_long_gate_cli_controls.py",
            "tests/test_long_gate_quickref_cache.py",
        ),
        "input_file_scopes": (
            ".github/workflows/quality.yml",
            ".pre-commit-config.yaml",
            "scripts/run_quality_gate.py",
            "scripts/run_daily_quality_gate.py",
            "scripts/sync_debt_ledger.py",
            "tools/check_full_test_debt.py",
            "tools/collect_full_test_debt.py",
            "tools/verify_required_regressions_from_full_test_debt.py",
            "tools/fast_static_precheck.py",
            "tools/git_hook_checks.py",
            "tools/test_debt_registry.py",
            "tools/test_registry.py",
            "tools/quality_gate_*.py",
            "tools/long_gate_*.py",
            ".codestable/tools/**/*.py",
            "tests/long_gate_cache_helpers.py",
            "开发文档/技术债务治理台账.md",
            "evidence/README.md",
            "evidence/current/README.md",
            "audit/**/README.md",
            ".limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md",
            ".limcode/skills/aps-full-selftest/scripts/run_full_selftest.py",
            "开发文档/开发文档.md",
            "开发文档/阶段留痕与验收记录.md",
        ),
        "config_file_scopes": (
            ".pre-commit-config.yaml",
            ".github/workflows/quality.yml",
        ),
        "tool_file_scopes": (
            "scripts/run_quality_gate.py",
            "scripts/sync_debt_ledger.py",
            "tools/check_full_test_debt.py",
            "tools/collect_full_test_debt.py",
            "tools/verify_required_regressions_from_full_test_debt.py",
            "tools/git_hook_checks.py",
            "tools/test_debt_registry.py",
            "tools/quality_gate_*.py",
            "tools/long_gate_*.py",
        ),
        "env_keys": (
            "git_executable_realpath",
            "git_version",
            "CI",
        ),
    },
    {
        "group_id": "scheduler_config",
        "label": "Scheduler config contracts",
        "target_paths": (
            "tests/regression_scheduler_config_route_contract.py",
            "tests/regression_config_field_spec_contract.py",
            "tests/regression_scheduler_config_manual_url_normalization.py",
            "tests/regression_config_service_active_preset_custom_sync.py",
            "tests/regression_config_snapshot_strict_numeric.py",
            "tests/regression_config_snapshot_projection_sync.py",
            "tests/regression_config_service_component_contract.py",
            "tests/regression_config_service_relaxed_missing_visibility.py",
            "tests/regression_apply_preset_adjusted_marks_custom.py",
            "tests/test_holiday_default_efficiency_read_guard.py",
        ),
        "input_file_scopes": (
            "core/services/scheduler/config*.py",
            "core/services/scheduler/config/*.py",
            "core/services/scheduler/config/**/*.py",
            "core/services/scheduler/calendar*.py",
            "core/services/scheduler/degradation_messages.py",
            "core/algorithms/*.py",
            "core/algorithms/**/*.py",
            "core/models/schedule_config_runtime*.py",
            "core/shared/*.py",
            "core/shared/**/*.py",
            "web/routes/domains/scheduler/scheduler_config*.py",
            "web/routes/domains/scheduler/scheduler_bp.py",
            "web/routes/domains/scheduler/scheduler_route_registrar.py",
            "web/routes/scheduler_config.py",
            "web/routes/scheduler.py",
            "web/viewmodels/**/*.py",
            "data/**/*.py",
            "templates/**/*.html",
            "web_new_test/templates/**/*.html",
            "static/**/*",
            "web_new_test/static/**/*",
            "docs/*manual*.md",
            "static/docs/**/*.md",
            "web_new_test/static/docs/**/*.md",
            "app.py",
            "app_new_ui.py",
            "config.py",
            "schema.sql",
        ),
        "env_keys": (
            "APS_ENV",
            "APS_DB_PATH",
            "APS_EXCEL_TEMPLATE_DIR",
            "SECRET_KEY",
            "node_executable_realpath",
            "node_version",
        ),
    },
    {
        "group_id": "scheduler_run_core",
        "label": "Scheduler run core contracts",
        "target_paths": (
            "tests/test_schedule_input_builder_strict_hours_and_ext_days.py",
            "tests/regression_scheduler_wrapper_import_order_contract.py",
            "tests/test_scheduler_route_registration_contract.py",
            "tests/test_scheduler_routes_still_registered_by_factory.py",
            "tests/test_history_summary_parser.py",
            "tests/test_phase6_no_result_summary_route_parser.py",
            "tests/regression_scheduler_bp_result_summary_guard.py",
            "tests/test_version_resolution_contract.py",
            "tests/test_phase6_no_route_version_parser.py",
            "tests/regression_schedule_orchestrator_contract.py",
            "tests/test_schedule_summary_observability.py",
            "tests/test_schedule_params_direct_call_contract.py",
            "tests/regression_scheduler_objective_labels.py",
            "tests/regression_objective_projection_contract.py",
            "tests/regression_sp05_followup_contracts.py",
            "tests/regression_scheduler_user_visible_messages.py",
            "tests/regression_route_version_normalizers_contract.py",
            "tests/regression_optimizer_seed_results_contract.py",
            "tests/regression_optimizer_seed_boundary_contract.py",
            "tests/regression_optimizer_runtime_seam_contract.py",
            "tests/regression_optimizer_outcome_type_contract.py",
            "tests/regression_optimizer_public_summary_projection_contract.py",
            "tests/regression_schedule_input_collector_contract.py",
            "tests/regression_schedule_params_read_failure_visible.py",
            "tests/regression_schedule_service_strict_snapshot_guard.py",
            "tests/regression_schedule_config_snapshot_optional_guard.py",
            "tests/regression_schedule_service_facade_delegation.py",
            "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py",
            "tests/regression_schedule_persistence_reschedulable_contract.py",
            "tests/regression_schedule_optimizer_cfg_snapshot_contract.py",
            "tests/regression_schedule_summary_cfg_snapshot_contract.py",
            "tests/regression_schedule_summary_algo_warnings_union.py",
            "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py",
            "tests/regression_schedule_summary_freeze_state_contract.py",
            "tests/regression_schedule_summary_overdue_warning_append_fallback.py",
            "tests/regression_schedule_summary_v11_contract.py",
            "tests/regression_schedule_summary_merge_context_degraded_code.py",
            "tests/regression_schedule_summary_input_fallback_contract.py",
            "tests/regression_scheduler_run_surfaces_resource_pool_warning.py",
            "tests/test_scheduler_run_view_result_contract.py",
            "tests/test_schedule_template_lookup_contract.py",
            "tests/regression_scheduler_ui_range_feedback_contract.py",
            "tests/regression_scheduler_route_enforce_ready_tristate.py",
        ),
        "input_file_scopes": (
            "core/services/scheduler/**/*.py",
            "core/**/*.py",
            "web/routes/domains/scheduler/scheduler_run.py",
            "web/routes/domains/scheduler/scheduler_ops.py",
            "web/routes/domains/scheduler/scheduler_batches.py",
            "web/routes/domains/scheduler/scheduler_batch_detail.py",
            "web/routes/domains/scheduler/scheduler_history_resolution.py",
            "web/routes/domains/scheduler/scheduler_user_messages.py",
            "web/routes/domains/scheduler/scheduler_utils.py",
            "web/routes/domains/scheduler/scheduler_bp.py",
            "web/routes/domains/scheduler/scheduler_route_registrar.py",
            "web/routes/scheduler_run.py",
            "web/routes/scheduler_ops.py",
            "web/routes/scheduler_batches.py",
            "web/routes/scheduler_batch_detail.py",
            "web/routes/scheduler.py",
            "web/viewmodels/**/*.py",
            "data/**/*.py",
            "templates/**/*.html",
            "static/**/*",
            "templates_excel/**/*",
            "app.py",
            "app_new_ui.py",
            "config.py",
            "schema.sql",
        ),
        "env_keys": (
            "APS_ENV",
            "APS_DB_PATH",
            "APS_LOG_DIR",
            "APS_BACKUP_DIR",
            "APS_EXCEL_TEMPLATE_DIR",
            "SECRET_KEY",
        ),
    },
    {
        "group_id": "scheduler_analysis_gantt_reports_week_plan",
        "label": "Scheduler analysis, gantt, reports, and week plan contracts",
        "target_paths": (
            "tests/regression_scheduler_analysis_route_contract.py",
            "tests/regression_scheduler_analysis_observability.py",
            "tests/regression_analysis_page_version_default_latest.py",
            "tests/regression_scheduler_analysis_vm_legacy_summary_bridge.py",
            "tests/regression_scheduler_week_plan_summary_observability.py",
            "tests/regression_gantt_page_version_default_latest.py",
            "tests/regression_gantt_default_version_span.py",
            "tests/regression_reports_page_version_default_latest.py",
            "tests/regression_week_plan_filename_uses_normalized_version.py",
            "tests/regression_gantt_calendar_load_failed_degraded.py",
            "tests/regression_gantt_bad_time_rows_surface_degraded.py",
            "tests/regression_scheduler_result_navigation_contract.py",
            "tests/regression_gantt_contract_snapshot.py",
            "tests/regression_gantt_critical_chain_unavailable.py",
            "tests/regression_gantt_critical_chain_provider.py",
            "tests/regression_scheduler_candidate_gantt_plan_role_contract.py",
        ),
        "input_file_scopes": (
            "core/services/scheduler/**/*.py",
            "web/routes/domains/scheduler/scheduler_analysis.py",
            "web/routes/domains/scheduler/scheduler_gantt.py",
            "web/routes/domains/scheduler/scheduler_gantt_redirect.py",
            "web/routes/domains/scheduler/scheduler_week_plan.py",
            "web/routes/domains/scheduler/scheduler_calendar_pages.py",
            "web/routes/domains/scheduler/scheduler_history_resolution.py",
            "web/routes/domains/scheduler/scheduler_pages.py",
            "web/routes/domains/scheduler/scheduler_utils.py",
            "web/routes/scheduler_analysis.py",
            "web/routes/scheduler_week_plan.py",
            "web/routes/reports.py",
            "web/routes/scheduler.py",
            "web/viewmodels/**/*.py",
            "templates/**/*.html",
            "static/**/*",
            "data/**/*.py",
            "app.py",
            "app_new_ui.py",
            "config.py",
            "schema.sql",
        ),
        "env_keys": (
            "APS_ENV",
            "APS_DB_PATH",
            "node_executable_realpath",
            "node_version",
            "node_browser_runtime_capability",
            "SECRET_KEY",
        ),
    },
    {
        "group_id": "scheduler_batches_material_resource",
        "label": "Scheduler batches, material, and resource contracts",
        "target_paths": (
            "tests/regression_scheduler_batches_degraded_visibility.py",
            "tests/regression_scheduler_batch_template_warning_surface.py",
            "tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py",
            "tests/regression_resource_dispatch_bad_time_rows_surface_degraded.py",
            "tests/regression_resource_dispatch_export_surfaces_degraded.py",
            "tests/regression_scheduler_excel_batches_preview_baseline_precision.py",
        ),
        "input_file_scopes": (
            "web/routes/domains/scheduler/scheduler_batches.py",
            "web/routes/domains/scheduler/scheduler_batch_detail.py",
            "web/routes/domains/scheduler/scheduler_excel_batches*.py",
            "web/routes/domains/scheduler/scheduler_resource_dispatch.py",
            "web/routes/domains/scheduler/scheduler_resource_dispatch_query.py",
            "web/routes/material.py",
            "web/routes/scheduler_batches.py",
            "web/routes/scheduler_batch_detail.py",
            "web/routes/scheduler_excel_batches.py",
            "web/routes/scheduler.py",
            "core/services/scheduler/**/*.py",
            "data/**/*.py",
            "templates/**/*.html",
            "static/**/*",
            "templates_excel/**/*",
            "app.py",
            "app_new_ui.py",
            "config.py",
            "schema.sql",
        ),
        "env_keys": (
            "APS_ENV",
            "APS_DB_PATH",
            "APS_EXCEL_TEMPLATE_DIR",
            "SECRET_KEY",
        ),
    },
    {
        "group_id": "request_services_runtime_error_boundary",
        "label": "Request services, runtime, and error boundary contracts",
        "target_paths": (
            "tests/regression_request_services_contract.py",
            "tests/regression_request_services_lazy_construction.py",
            "tests/regression_request_services_failure_propagation.py",
            "tests/regression_factory_request_lifecycle_observability.py",
            "tests/regression_system_request_services_contract.py",
            "tests/regression_maintenance_window_mutex.py",
            "tests/regression_error_field_label_source.py",
            "tests/test_ui_mode.py",
            "tests/regression_safe_next_url_hardening.py",
            "tests/regression_safe_next_url_observability.py",
            "tests/regression_error_boundary_contract.py",
        ),
        "input_file_scopes": (
            "web/bootstrap/**/*.py",
            "web/error_boundary.py",
            "web/error_handlers.py",
            "web/ui_mode.py",
            "web/ui_mode_request.py",
            "web/ui_mode_store.py",
            "web/render_bridge.py",
            "web/manual_src_security.py",
            "web/bootstrap/*.py",
            "web/routes/__init__.py",
            "web/routes/navigation_utils.py",
            "web/routes/normalizers.py",
            "web/routes/system_utils.py",
            "web/routes/system_backup.py",
            "web/routes/system_history.py",
            "web/routes/system_logs.py",
            "web/routes/system_plugins.py",
            "web/routes/system_ui_mode.py",
            "web/routes/domains/scheduler/scheduler_config.py",
            "web/routes/domains/scheduler/scheduler_batches.py",
            "core/**/*.py",
            "data/**/*.py",
            "plugins/**/*.py",
            "templates/**/*.html",
            "static/**/*",
            "app.py",
            "app_new_ui.py",
            "config.py",
            "schema.sql",
        ),
        "env_keys": (
            "APS_ENV",
            "APS_DB_PATH",
            "APS_LOG_DIR",
            "APS_BACKUP_DIR",
            "APS_EXCEL_TEMPLATE_DIR",
            "APS_CHROME_PATH",
            "SECRET_KEY",
            "chrome_executable_resolution",
            "chrome_version",
            "chrome_executable_identity",
        ),
    },
    {
        "group_id": "frontend_manual_excel",
        "label": "Frontend manual and Excel contracts",
        "target_paths": (
            "tests/test_excel_import_hardening.py",
            "tests/test_excel_utils_compare_digest_guard.py",
            "tests/regression_excel_hidden_payload_contract.py",
            "tests/regression_mirror_template_sync.py",
        ),
        "input_file_scopes": (
            "templates_excel/**/*",
            "docs/**/*.md",
            "static/docs/**/*.md",
            "web_new_test/static/docs/**/*.md",
            "templates/**/*.html",
            "web_new_test/templates/**/*.html",
            "static/**/*",
            "web_new_test/static/**/*",
            "web/routes/excel_*.py",
            "web/routes/process_excel_*.py",
            "web/routes/personnel_excel_*.py",
            "web/routes/equipment_excel_*.py",
            "web/routes/domains/scheduler/scheduler_excel*.py",
            "web/routes/domains/scheduler/scheduler_config_display_state.py",
            "web/routes/scheduler_excel*.py",
            "web/manual_src_security.py",
            "web/render_bridge.py",
            "web/viewmodels/**/*.py",
            "core/**/*.py",
            "data/**/*.py",
            "app.py",
            "app_new_ui.py",
            "config.py",
            "schema.sql",
        ),
        "env_keys": (
            "APS_ENV",
            "APS_DB_PATH",
            "APS_EXCEL_TEMPLATE_DIR",
            "APS_CHROME_PATH",
            "APS_STATIC_VERSION",
            "node_executable_realpath",
            "node_version",
            "chrome_executable_resolution",
            "chrome_version",
            "chrome_executable_identity",
        ),
    },
    {
        "group_id": "ui_layout_presenters_system",
        "label": "UI layout, presenters, and system contracts",
        "target_paths": (
            "tests/regression_system_history_route_contract.py",
            "tests/test_ui_browser_geometry_env.py",
            "tests/test_ui_geometry_html_contract.py",
        ),
        "input_file_scopes": (
            "tests/ui_geometry_contract_data.py",
            "templates/**/*.html",
            "web_new_test/templates/**/*.html",
            "static/**/*",
            "web_new_test/static/**/*",
            "web/viewmodels/**/*.py",
            "web/routes/system_*.py",
            "web/routes/system_backup.py",
            "web/routes/system_history.py",
            "web/routes/system_logs.py",
            "web/routes/system.py",
            "web/routes/system_bp.py",
            "web/routes/system_health.py",
            "web/routes/system_plugins.py",
            "web/routes/system_ui_mode.py",
            "web/routes/excel_utils.py",
            "web/routes/process_parts.py",
            "web/routes/process_excel_routes.py",
            "web/routes/domains/scheduler/scheduler_run.py",
            "web/routes/domains/scheduler/scheduler_batches.py",
            "web/routes/domains/scheduler/scheduler_batch_detail.py",
            "web/routes/domains/scheduler/scheduler_excel_batches.py",
            "web/routes/domains/scheduler/scheduler_week_plan.py",
            "core/**/*.py",
            "data/**/*.py",
            "app.py",
            "app_new_ui.py",
            "config.py",
            "schema.sql",
        ),
        "env_keys": (
            "APS_BROWSER_SMOKE_REQUIRED",
            "APS_CHROME_PATH",
            "APS_STATIC_VERSION",
            "CI",
            "chrome_executable_resolution",
            "chrome_version",
            "chrome_executable_identity",
            "chrome_headless_preflight",
            "node_executable_realpath",
            "node_version",
            "node_browser_runtime_capability",
            "NODE_OPTIONS",
        ),
    },
)


def _normalize_registry_path(path: str) -> str:
    return str(path or "").strip().replace("\\", "/")


def _normalize_scope_paths(paths: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw_path in list(paths or []):
        normalized = _normalize_registry_path(str(raw_path))
        if not normalized or normalized in seen:
            continue
        if os.path.isabs(normalized):
            raise ValueError("required regression scope path must be repo-relative: " + normalized)
        if "\0" in normalized:
            raise ValueError("required regression scope path contains NUL: " + normalized)
        seen.add(normalized)
        out.append(normalized)
    return out


def _normalize_env_keys(keys: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw_key in list(keys or []):
        key = str(raw_key or "").strip()
        if not key or key in seen:
            continue
        if "\0" in key:
            raise ValueError("required regression env key contains NUL: " + key)
        seen.add(key)
        out.append(key)
    return out


def _is_top_level_test_only_helper_path(path: str) -> bool:
    normalized = _normalize_registry_path(path)
    name = os.path.basename(normalized)
    return (
        normalized.startswith("tests/")
        and normalized.count("/") == 1
        and normalized.endswith(".py")
        and name.endswith("_helpers.py")
        and name != "conftest.py"
    )


def _is_regular_helper_impact_target(path: str) -> bool:
    normalized = _normalize_registry_path(path)
    name = os.path.basename(normalized)
    if normalized == "conftest.py" or normalized.endswith("/conftest.py"):
        return False
    if not normalized.startswith("tests/") or normalized.count("/") != 1 or not normalized.endswith(".py"):
        return False
    if name.endswith("_helpers.py"):
        return False
    return name.startswith("test_") or name.startswith("regression_")


def iter_test_only_helper_impacts(
    helper_impacts: Optional[Mapping[str, Sequence[str]]] = None,
) -> Dict[str, List[str]]:
    impacts = helper_impacts if helper_impacts is not None else TEST_ONLY_HELPER_IMPACT
    rows: Dict[str, List[str]] = {}
    for helper_path, target_paths in sorted(impacts.items()):
        helper = _normalize_registry_path(helper_path)
        if not _is_top_level_test_only_helper_path(helper):
            raise ValueError("test-only helper impact helper must be top-level tests/*_helpers.py: " + helper)
        targets = normalize_test_paths(list(target_paths or []))
        if not targets:
            raise ValueError("test-only helper impact targets are empty: " + helper)
        for target in targets:
            if not _is_regular_helper_impact_target(target):
                raise ValueError("test-only helper impact target must be a top-level test file: " + target)
        rows[helper] = targets
    return rows


def test_only_helper_impacts_for_path(
    path: str,
    helper_impacts: Optional[Mapping[str, Sequence[str]]] = None,
) -> List[str]:
    normalized = _normalize_registry_path(path)
    return list(iter_test_only_helper_impacts(helper_impacts).get(normalized) or [])


def normalize_test_paths(paths: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for rel_path in list(paths or []):
        normalized = str(rel_path or "").strip().replace("\\", "/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def iter_required_tests(required_tests: Sequence[str] = QUALITY_GATE_REQUIRED_TESTS) -> List[str]:
    return normalize_test_paths(required_tests)


def iter_startup_regressions(
    startup_regressions: Sequence[str] = QUALITY_GATE_STARTUP_REGRESSION_ARGS,
) -> List[str]:
    return normalize_test_paths(startup_regressions)


def iter_non_regression_guard_tests(required_tests: Sequence[str] = QUALITY_GATE_REQUIRED_TESTS) -> List[str]:
    out: List[str] = []
    for rel_path in iter_required_tests(required_tests):
        if os.path.basename(rel_path).startswith("regression_"):
            continue
        out.append(rel_path)
    return out


def required_test_nodeid_matches(nodeid: str, required_tests: Sequence[str] = QUALITY_GATE_REQUIRED_TESTS) -> bool:
    normalized_nodeid = str(nodeid or "").strip().replace("\\", "/")
    node_path = normalized_nodeid.split("::", 1)[0]
    return any(
        node_path == required_path or normalized_nodeid.startswith(required_path + "::")
        for required_path in iter_required_tests(required_tests)
    )


def build_test_path_status(
    paths: Sequence[str],
    *,
    repo_root: Optional[str] = None,
) -> List[Dict[str, Any]]:
    root = os.path.abspath(repo_root or REPO_ROOT)
    rows: List[Dict[str, Any]] = []
    for rel_path in normalize_test_paths(paths):
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel_path],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        rows.append(
            {
                "path": rel_path,
                "exists": os.path.exists(os.path.join(root, rel_path)),
                "tracked": tracked.returncode == 0,
            }
        )
    return rows


def stable_registry_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def hash_required_tests_registry(required_tests: Sequence[str]) -> str:
    return stable_registry_hash(iter_required_tests(required_tests))


def iter_required_regression_groups(
    groups: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    source = REQUIRED_REGRESSION_GROUPS if groups is None else groups
    rows: List[Dict[str, Any]] = []
    seen_group_ids = set()
    for raw_group in list(source or []):
        group_id = str(raw_group.get("group_id") or "").strip()
        if not group_id:
            raise ValueError("required regression group_id is empty")
        if group_id in seen_group_ids:
            raise ValueError("required regression group_id is duplicated: " + group_id)
        seen_group_ids.add(group_id)
        target_paths = normalize_test_paths(list(raw_group.get("target_paths") or []))
        if not target_paths:
            raise ValueError("required regression group targets are empty: " + group_id)
        rows.append(
            {
                "group_id": group_id,
                "label": str(raw_group.get("label") or group_id).strip() or group_id,
                "target_paths": target_paths,
                "input_file_scopes": _normalize_scope_paths(raw_group.get("input_file_scopes") or ()),
                "config_file_scopes": _normalize_scope_paths(raw_group.get("config_file_scopes") or ()),
                "tool_file_scopes": _normalize_scope_paths(raw_group.get("tool_file_scopes") or ()),
                "dependency_file_scopes": _normalize_scope_paths(raw_group.get("dependency_file_scopes") or ()),
                "env_keys": _normalize_env_keys(raw_group.get("env_keys") or ()),
            }
        )
    return rows


def iter_required_regression_common_scope_policy(
    scopes: Optional[Mapping[str, Sequence[str]]] = None,
) -> Dict[str, List[str]]:
    source = REQUIRED_REGRESSION_COMMON_SCOPES if scopes is None else scopes
    return {
        "input_file_scopes": _normalize_scope_paths(source.get("input_file_scopes") or ()),
        "config_file_scopes": _normalize_scope_paths(source.get("config_file_scopes") or ()),
        "tool_file_scopes": _normalize_scope_paths(source.get("tool_file_scopes") or ()),
        "dependency_file_scopes": _normalize_scope_paths(source.get("dependency_file_scopes") or ()),
        "env_keys": _normalize_env_keys(source.get("env_keys") or ()),
    }


def hash_required_regression_groups(
    groups: Optional[Sequence[Mapping[str, Any]]] = None,
) -> str:
    return stable_registry_hash(iter_required_regression_groups(groups))


def validate_required_regression_group_coverage(
    required_tests: Sequence[str],
    groups: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    required_paths = iter_required_tests(required_tests)
    required_set = set(required_paths)
    group_rows = iter_required_regression_groups(groups)
    flat_targets: List[str] = []
    target_to_groups: Dict[str, List[str]] = {}
    for group in group_rows:
        group_id = str(group.get("group_id") or "")
        for target in list(group.get("target_paths") or []):
            normalized = _normalize_registry_path(str(target))
            flat_targets.append(normalized)
            target_to_groups.setdefault(normalized, []).append(group_id)

    duplicates = []
    for target, owning_groups in sorted(target_to_groups.items()):
        if len(owning_groups) > 1 or flat_targets.count(target) > 1:
            duplicates.append(
                {
                    "path": target,
                    "groups": list(owning_groups),
                }
            )

    missing = [path for path in required_paths if path not in target_to_groups]
    unknown = [path for path in flat_targets if path not in required_set]
    return {
        "missing": missing,
        "duplicates": duplicates,
        "unknown": sorted(dict.fromkeys(unknown)),
        "required_target_count": len(required_paths),
        "group_target_count": len(flat_targets),
        "group_count": len(group_rows),
        "required_registry_hash": hash_required_tests_registry(required_paths),
        "group_registry_hash": hash_required_regression_groups(group_rows),
    }


def hash_test_registry(
    *,
    required_tests: Optional[Sequence[str]] = None,
    startup_regressions: Optional[Sequence[str]] = None,
    active_xfail_entries: Optional[Sequence[Dict[str, Any]]] = None,
) -> str:
    active_entries = []
    for entry in list(active_xfail_entries or []):
        active_entries.append(
            {
                "debt_id": str(entry.get("debt_id") or ""),
                "nodeid": str(entry.get("nodeid") or ""),
                "reason": str(entry.get("reason") or ""),
            }
        )
    active_entries.sort(key=lambda item: (item["nodeid"], item["debt_id"]))
    required_source = QUALITY_GATE_REQUIRED_TESTS if required_tests is None else required_tests
    startup_source = QUALITY_GATE_STARTUP_REGRESSION_ARGS if startup_regressions is None else startup_regressions
    return stable_registry_hash(
        {
            "required_tests": iter_required_tests(required_source),
            "startup_regressions": iter_startup_regressions(startup_source),
            "active_xfail_entries": active_entries,
        }
    )


__all__ = [
    "QUALITY_GATE_GUARD_TESTS",
    "QUALITY_GATE_REQUIRED_TESTS",
    "QUALITY_GATE_SELFTEST_PATH",
    "QUALITY_GATE_STARTUP_REGRESSION_ARGS",
    "REQUIRED_REGRESSION_COMMON_SCOPES",
    "REQUIRED_REGRESSION_GROUPS",
    "TEST_ONLY_HELPER_IMPACT",
    "build_test_path_status",
    "hash_required_regression_groups",
    "hash_required_tests_registry",
    "hash_test_registry",
    "iter_non_regression_guard_tests",
    "iter_required_regression_common_scope_policy",
    "iter_required_regression_groups",
    "iter_required_tests",
    "iter_startup_regressions",
    "iter_test_only_helper_impacts",
    "normalize_test_paths",
    "required_test_nodeid_matches",
    "stable_registry_hash",
    "test_only_helper_impacts_for_path",
    "validate_required_regression_group_coverage",
]
