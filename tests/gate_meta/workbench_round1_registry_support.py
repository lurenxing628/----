"""Reviewed R1 target expectations, independent of the production registry."""

# Keep this review record independent of the production tuple: future additions
# must not silently disappear from the historical owner/order assertions.
REVIEWED_ALGORITHM_REQUIRED_TESTS = (
    "tests/algorithm/test_busy_union_closure.py",
    "tests/algorithm/test_gap_resource_quality.py",
    "tests/algorithm/test_graph_repair_deadline.py",
    "tests/algorithm/test_graph_repair_decisions.py",
    "tests/algorithm/test_graph_repair_multiround.py",
    "tests/algorithm/test_graph_repair_operation_neighbors.py",
    "tests/algorithm/test_graph_repair_real_decode.py",
    "tests/algorithm/test_native_snapshot_callback_boundaries.py",
    "tests/algorithm/test_optimizer_benchmark_timing_contract.py",
    "tests/algorithm/test_optimizer_budget_public_projection.py",
    "tests/algorithm/test_optimizer_comparison_baseline_lifecycle.py",
    "tests/algorithm/test_optimizer_deadline_boundary.py",
    "tests/algorithm/test_optimizer_end_to_end_matrix_contract.py",
    "tests/algorithm/test_optimizer_end_to_end_snapshot_contract.py",
    "tests/algorithm/test_optimizer_exact_oracle.py",
    "tests/algorithm/test_optimizer_multi_start_budget_integration.py",
    "tests/algorithm/test_optimizer_multi_start_decision_dedup.py",
    "tests/algorithm/test_optimizer_objective_aware_graph_features.py",
    "tests/algorithm/test_optimizer_quality_matrix_quality_contract.py",
    "tests/algorithm/test_optimizer_shared_budget.py",
    "tests/algorithm/test_owned_sgs_timeline.py",
    "tests/algorithm/test_resource_demand_contract.py",
    "tests/algorithm/test_resource_demand_neutral_comparison.py",
    "tests/algorithm/test_resource_demand_total_blocking.py",
    "tests/algorithm/test_sgs_native_score_reuse.py",
    "tests/algorithm/test_sgs_plain_auto_timelines.py",
    "tests/scheduler_graph/test_graph_preparation_efficiency.py",
    "tests/scheduler_graph/test_metrics_impact_components.py",
)
REVIEWED_ALGORITHM_TARGET_OWNERS = {
    **{path: "scheduler_run_core" for path in REVIEWED_ALGORITHM_REQUIRED_TESTS},
    "tests/workbench/test_run_snapshot_reuse.py": "workbench_run_compute",
    "tests/gate_meta/test_quality_gate_output_normalization.py": "quality_gate",
}


def assert_reviewed_algorithm_registration():
    from tools import test_registry
    from tools.test_registry_algorithm_efficiency import ALGORITHM_EFFICIENCY_REQUIRED_TESTS
    from tools.test_registry_groups_workbench import WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS

    assert ALGORITHM_EFFICIENCY_REQUIRED_TESTS == REVIEWED_ALGORITHM_REQUIRED_TESTS
    groups = test_registry.REQUIRED_REGRESSION_GROUPS
    for path, owner in REVIEWED_ALGORITHM_TARGET_OWNERS.items():
        assert [group["group_id"] for group in groups for target in group["target_paths"]
                if target == path] == [owner]
        assert test_registry.QUALITY_GATE_REQUIRED_TESTS.count(path) == 1
        assert all(path not in group["target_paths"] for group in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    for owner in dict.fromkeys(REVIEWED_ALGORITHM_TARGET_OWNERS.values()):
        expected = [path for path, group_id in REVIEWED_ALGORITHM_TARGET_OWNERS.items() if group_id == owner]
        group = next(group for group in groups if group["group_id"] == owner)
        assert [path for path in group["target_paths"] if path in REVIEWED_ALGORITHM_TARGET_OWNERS] == expected


# Expected additions are literal review records, never derived from registry implementation.
UI_REQUIRED_TARGETS = (
    "tests/workbench/test_style_build_sources.py",
    "tests/workbench/test_ui_refinement_style_gate.py",
    "tests/workbench/test_ui_refinement_node_contracts.py",
    "tests/workbench/test_ui_refinement_evidence_contract.py",
    "tests/workbench/test_ui_refinement_browser_dependencies.py",
    "tests/gate_meta/test_daily_ui_refinement_opt_in.py",
    "tests/gate_meta/test_workbench_ui_registry.py",
    # 2026-09-13 reviewed addition: user-visible copy glossary guard (tools/scan_ui_copy.py must report zero hits).
    "tests/workbench/test_ui_copy_glossary.py",
    # 2026-09-13 reviewed additions (UI audit remediation): handler prefill memory contract (pure Node) and the
    # run progress ledger that feeds the run-job progress bar (pure Python).
    "tests/workbench/test_handler_memory.py",
    "tests/workbench/test_run_progress_ledger.py",
    "tests/workbench/test_workbench_delete_icons.py",
)
UI_SUPPLEMENTAL_TARGETS = (
    "tests/workbench/test_ui_refinement_geometry.py",
    "tests/workbench/test_ui_navigation_guard.py",
    "tests/workbench/test_shared_controls_widgets.py",
    "tests/workbench/test_dashboard_ui_refinement.py",
    "tests/workbench/test_dirty_guard_widgets.py",
    "tests/workbench/test_ui_refinement_reports_review.py",
    "tests/workbench/test_wbui_actual_keyboard.py",
    "tests/workbench/test_wbui_plan_first_screen.py",
    "tests/workbench/test_wbui_plan_gantt_models.py",
    # 2026-09-14 reviewed addition: short-screen application layout (only the table scrolls) on a real Flask + Chromium 109 loop.
    "tests/workbench/test_short_screen_layout.py",
    "tests/workbench/test_workbench_visual_controls.py",
    "tests/workbench/test_operator_machine_permissions_widgets.py",
)
UI_GROUP_IDS = ("workbench_ui_refinement", "workbench_ui_refinement_browser")

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
        "test_final_operations_navigation.py",
        "test_final_operations_system_recovery.py",
        "test_final_operations_system_restart.py",
        "test_final_planning_process_order.py",
        "test_final_planning_task_origin.py",
        "test_final_planning_required.py",
        "test_batch_dashboard_return_context.py",
        "test_final_planning_l5_contract.py",
        "test_final_execution_read_contract.py",
        "test_final_execution_read_reentry.py",
        "test_final_execution_rejections.py",
        "test_final_execution_report_contract.py",
        "test_final_execution_report_reentry.py",
        "test_final_master_typed_lineage.py",
        "test_final_operations_context_contract.py",
        "test_final_planning_candidate_source.py",
        "test_final_master_domain_ledger.py",
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

FINAL_CANDIDATE_READONLY_FILES = (
    "test_final_planning_analysis.py", "test_final_planning_analysis_history.py",
    "test_final_planning_analysis_contract.py",
)


FINAL_CANDIDATE_READONLY_INPUTS = (
    "tests/workbench/final_planning_analysis_contract.cjs",
    "frontend/workbench/app/RunCandidateAPI.js",
    "frontend/workbench/app/RunCandidateAnalysisAPI.js",
)


MANUAL_REMEDIATION_TARGET_OWNERS = {
    "tests/workbench/test_manual_remediation_schema_migration.py": "workbench_mainmigration",
    "tests/workbench/test_batch_template_updates.py": "workbench_batches",
    "tests/workbench/test_operator_machine_permissions.py": "workbench_resources",
    "tests/workbench/test_outsourcing_legacy_source.py": "workbench_outsourcing",
    "tests/workbench/test_resource_utilization_shared.py": "workbench_reports",
    "tests/workbench/test_run_data_context.py": "workbench_run_jobs",
    "tests/workbench/test_execution_report_void.py": "workbench_execution_ledger",
    "tests/workbench/test_field_report_void_api.py": "workbench_field",
    "tests/workbench/test_report_void_projections.py": "workbench_reports",
    "tests/workbench/test_trial_source_presentation.py": "workbench_trial",
    "tests/workbench/test_resource_feedback.py": "workbench_resources",
    "tests/workbench/test_file_reference_roundtrip.py": "workbench_resources",
    "tests/workbench/test_trial_adoption_execution_anchors.py": "workbench_trial_adoption",
}


def before_manual_remediation_targets(group):
    return [path for path in group["target_paths"] if path not in MANUAL_REMEDIATION_TARGET_OWNERS]


POST_ROUND1_TARGETS = frozenset((
    *MANUAL_REMEDIATION_TARGET_OWNERS,
    "tests/workbench/test_field_report_void_browser.py",
    "tests/workbench/test_field_scope_navigation_browser.py",
    "tests/workbench/test_resource_context_refresh.py",
    *UI_REQUIRED_TARGETS,
    *UI_SUPPLEMENTAL_TARGETS,
    "tests/gate_meta/test_quality_gate_output_normalization.py",
    "tests/gate_meta/test_scheduler_lazy_exports_final.py",
    "tests/workbench/test_final_capacity_cli_loading.py",
    "tests/workbench/test_final_foundation_navigation.py",
    "tests/workbench/test_final_foundation_live.py",
    "tests/workbench/test_final_navigation_host.py",
    "tests/workbench/test_final_navigation_boot.py",
    "tests/workbench/test_final_legacy_navigation.py",
    *("tests/workbench/" + name for names in FINAL_INTEGRATION_SUPPLEMENTAL_FILES.values() for name in names),
    *("tests/workbench/" + name for name in FINAL_CANDIDATE_READONLY_FILES),
))


def round1_targets(group):
    return [path for path in group["target_paths"]
            if path not in POST_ROUND1_TARGETS and path not in REVIEWED_ALGORITHM_TARGET_OWNERS]


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
    "scheduler_batches_material_resource",
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
    ("tests/workbench/round1_field_piece_files_support.py", "workbench_field"),
    ("tests/workbench/round1_piece_point_support.py", "workbench_piece_adoption"),
    ("tests/gate_meta/workbench_round1_registry_support.py", "workbench_registry"),
)

ROUND1_BROWSER_INPUTS = (
    "tests/workbench/test_round1_field_piece_files_browser.cjs",
    "tests/workbench/round1_field_piece_files_probe.py",
    "tests/workbench/round1_field_piece_files_support.py",
    "tests/workbench/field_workspace_probe_harness.cjs",
)
