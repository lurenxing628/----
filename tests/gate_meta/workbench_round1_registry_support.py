"""Reviewed R1 target expectations, independent of the production registry."""

# Only explicitly reviewed additions are outside the historical 582/85 snapshot.
FINAL_INTEGRATION_SUPPLEMENTAL_FILES = {
    "workbench_browser": (
        "test_final_execution_analytics.py",
        "test_final_execution_backend.py",
        "test_final_execution_browser.py",
        "test_final_execution_calibration.py",
        "test_final_execution_chain.py",
        "test_final_execution_controls.py",
        "test_final_execution_history.py",
        "test_final_execution_reports.py",
        "test_final_execution_search.py",
        "test_final_master_config_trace.py",
        "test_final_master_context.py",
        "test_final_master_guards.py",
        "test_final_master_manifest.py",
        "test_final_master_metadata_guard.py",
        "test_final_operations_analysis.py",
        "test_final_operations_browser.py",
        "test_final_operations_candidates.py",
        "test_final_operations_download.py",
        "test_final_operations_download_contract.py",
        "test_final_operations_host.py",
        "test_final_operations_pressure.py",
        "test_final_operations_projection_api.py",
        "test_final_operations_records.py",
        "test_final_operations_restore.py",
        "test_final_planning_browser.py",
        "test_final_planning_contracts.py",
        "test_final_planning_delivery.py",
        "test_final_planning_preflight_return.py",
        "test_final_planning_readonly.py",
        "test_final_legacy_navigation_layering.py", "test_final_planning_gantt.py",
        "test_final_operations_read_controls.py",
        "test_final_execution_calibration_table.py", "test_final_execution_resources.py",
        "test_final_legacy_report_dates.py",
        "test_final_operations_edges.py", "test_final_operations_inflight.py",
        "test_final_master_action_ledger.py", "test_final_master_config_preservation.py",
        "test_final_master_resource_revisions.py",
    ),
    "workbench_run_compute_capacity": (
        "test_final_capacity_contract.py",
        "test_final_capacity_inputs.py",
        "test_final_capacity_source_binding.py",
    ),
    "workbench_run_jobs_capacity": (
        "test_final_capacity_managed.py",
    ),
}

CAPACITY_SOURCE_BINDING_INPUTS = (
    "tests/workbench/final_capacity_binding.py",
    "tests/workbench/final_foundation_live_source_guard.py",
    ".codestable/roadmap/workbench-prototype-migration/legacy-retirement/factory-tests/source_guard.py",
    ".codestable/roadmap/workbench-prototype-migration/legacy-retirement/factory-tests/source_binding.py",
    ".codestable/roadmap/workbench-prototype-migration/legacy-retirement/factory-tests/source_inventory.py",
)
CAPACITY_SOURCE_BINDING_ENV_KEYS = (
    "FACTORY_SOURCE_MANIFEST", "WORKBENCH_CAPACITY_EXPECTED_SOURCE_ROOT",
    "WORKBENCH_CAPACITY_FORBIDDEN_ORIGIN", "WORKBENCH_CAPACITY_MANIFEST_SHA256",
)

POST_ROUND1_TARGETS = frozenset((
    "tests/gate_meta/test_scheduler_lazy_exports_final.py",
    "tests/workbench/test_final_capacity_cli_loading.py",
    "tests/workbench/test_final_foundation_navigation.py",
    "tests/workbench/test_final_foundation_live.py",
    "tests/workbench/test_final_navigation_host.py",
    "tests/workbench/test_final_navigation_boot.py",
    "tests/workbench/test_final_legacy_navigation.py",
    *("tests/workbench/" + name for names in FINAL_INTEGRATION_SUPPLEMENTAL_FILES.values() for name in names),
))


def round1_targets(group):
    return [path for path in group["target_paths"] if path not in POST_ROUND1_TARGETS]


ROUND1_REQUIRED_FILES = {
    "workbench_registry": (
        "test_round1_execution_dependency_contract.py", "test_round1_plan_query_dependency_contract.py",
    ),
    "workbench_process": (
        "test_round1_process_contract.py", "test_round1_process_boundaries.py",
    ),
    "workbench_batches": ("test_batch_round1_boundaries.py",),
    "workbench_plans": (
        "test_round1_plan_contract_boundaries.py", "test_round1_plan_contract_projections.py",
    ),
    "workbench_reports": (
        "test_round1_analytics_contract.py", "test_round1_report_export_contract.py",
    ),
    "workbench_system": ("test_round1_host_boundaries.py", "test_round1_runtime_observation.py"),
    "workbench_execution_ledger": (
        "test_round1_execution_contract.py",
    ),
    "workbench_field": (
        "test_round1_field_piece_files.py", "test_round1_field_piece_files_codec.py",
        "test_round1_field_piece_files_contract.py",
    ),
    "workbench_run_compute": (
        "test_round1_run_boundaries_input.py", "test_round1_run_boundaries_compute.py",
    ),
    "workbench_run_jobs": (
        "test_round1_run_boundaries_models.py", "test_round1_run_boundaries_candidates.py",
    ),
    "workbench_trial": ("test_round1_trial_boundaries.py",),
    "workbench_outsourcing": ("test_round1_outsourcing_contract.py",),
    "workbench_piece_adoption": (
        "test_round1_piece_point_chain.py", "test_round1_piece_point_constraints.py",
        "test_round1_piece_point_evidence.py", "test_round1_piece_point_protection.py",
    ),
}

ROUND1_SUPPLEMENTAL_FILES = {
    "workbench_browser": ("test_round1_field_piece_files_browser.py",),
}

ROUND1_GATE_TESTS = ("tests/gate_meta/test_workbench_round1_registry_contract.py",)
ROUND1_ALGORITHM_TESTS = ("tests/algorithm/test_sgs_explicit_piece_scope.py",)
ROUND1_CANDIDATE_SCHEMA_TESTS = ("tests/candidate/test_scheduler_candidate_schema_contract.py",)
CANDIDATE_V9_FIXTURE = "tests/migration_db/fixtures/schema-v9.sql"
ROUND1_SCANNER_TESTS = ("tests/gate_meta/test_round1_import_resolver.py",)
ROUND1_SCANNER_SOURCES = (
    "tools/import_cycle_analysis.py", "tools/import_cycle_graph.py", "tools/scan_import_cycles.py",
)

SNAPSHOT_REQUIRED_GROUPS = (
    "workbench_registry", "workbench_foundation", "workbench_resources", "workbench_process", "workbench_batches",
    "workbench_plans", "workbench_system", "workbench_field", "workbench_preflight", "workbench_mainmigration",
    "workbench_run_compute", "workbench_run_jobs", "workbench_trial", "workbench_template_lineage",
    "workbench_request_lifecycle", "workbench_calibration_adoption", "workbench_trial_adoption",
    "workbench_dashboard", "workbench_zero_duration", "workbench_piece_adoption",
)
SNAPSHOT_SUPPLEMENTAL_GROUPS = (
    "workbench_browser", "workbench_browser_opt_in", "workbench_run_compute_capacity", "workbench_run_jobs_capacity",
    "workbench_run_history_capacity", "workbench_run_candidate_capacity", "workbench_run_baseline_capacity",
    "workbench_run_adoption_capacity", "workbench_identity_diagnostics", "workbench_trial_capacity",
)

ROUND1_SERIAL_FILES = ("test_round1_piece_point_evidence.py", "test_round1_runtime_observation.py")

NEUTRAL_EXECUTION_FILES = (
    "__init__.py", "ledger_reader.py", "legacy.py", "projection.py", "quality.py", "totals.py",
)

NEUTRAL_PLAN_READ_FILES = (
    "plan_identity.py", "plan_query.py", "bounded_plan_query.py",
)

ROUND1_INPUT_OWNERS = (
    ("core/algorithms/greedy/dispatch/sgs.py", "scheduler_run_core"),
    ("core/services/system/backup_restore.py", "workbench_system"),
    ("core/services/system/backup_restore.py", "request_services_runtime_error_boundary"),
    ("core/services/system/backup_restore.py", "ui_layout_presenters_system"),
    ("web/routes/system_backup_actions.py", "workbench_system"),
    ("web/routes/workbench/system_actions.py", "workbench_system"),
    ("web/bootstrap/workbench_system_restore.py", "workbench_system"),
    ("web/bootstrap/entrypoint.py", "workbench_system"),
    ("web/bootstrap/launcher_shutdown.py", "workbench_system"),
    ("web/bootstrap/workbench_run_runtime.py", "workbench_system"),
    ("core/services/process/unit_excel/__init__.py", "workbench_system"),
    ("core/services/process/unit_excel/builder_diagnostics.py", "workbench_system"),
    ("core/services/workbench/system_journal.py", "workbench_system"),
    ("core/models/workbench_master_overview.py", "workbench_process"),
    ("core/services/workbench/master_overview.py", "workbench_process"),
    ("core/services/workbench/resource_readiness.py", "workbench_process"),
    ("web/routes/process_parts.py", "workbench_process"),
    ("core/models/workbench_run_adoption.py", "workbench_plans"),
    ("core/services/workbench/run_candidate_adoption.py", "workbench_plans"),
    ("core/services/workbench/report_exports.py", "workbench_reports"),
    ("core/services/workbench/report_catalog.py", "workbench_reports"),
    ("core/services/common/plan_query.py", "workbench_reports"),
    ("core/services/common/plan_query.py", "scheduler_analysis_gantt_reports_week_plan"),
    ("core/services/common/plan_query.py", "scheduler_batches_material_resource"),
    ("core/services/workbench/field_report_files_identity.py", "workbench_field"),
    ("core/services/workbench/field_report_files_xml.py", "workbench_field"),
    ("core/services/workbench/field_report_files_codec.py", "workbench_field"),
    ("core/services/workbench/actual_gantt_export.py", "workbench_field"),
    ("core/services/scheduler/execution/execution_plan_identity.py", "workbench_execution_scheduler"),
    ("core/services/workbench/dashboard_commands.py", "workbench_outsourcing"),
    ("tests/workbench/test_batch_files.py", "workbench_batches"),
    ("tests/workbench/test_round1_field_piece_files_support.py", "workbench_field"),
    ("tests/workbench/test_round1_piece_point_support.py", "workbench_piece_adoption"),
    ("tests/gate_meta/workbench_round1_registry_support.py", "workbench_registry"),
)

ROUND1_BROWSER_INPUTS = (
    "tests/workbench/test_round1_field_piece_files_browser.cjs",
    "tests/workbench/test_round1_field_piece_files_probe.py",
    "tests/workbench/test_round1_field_piece_files_support.py",
    "tests/workbench/field_workspace_probe_harness.cjs",
)
