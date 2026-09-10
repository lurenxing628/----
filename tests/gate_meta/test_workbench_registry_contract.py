"""Fixed workbench registration, real gate consumers and execution boundaries."""

from __future__ import annotations

import ast
import hashlib
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import run_daily_quality_gate as daily
from tests.gate_meta.workbench_round1_registry_support import (
    FINAL_INTEGRATION_SUPPLEMENTAL_FILES,
    POST_ROUND1_TARGETS,
    ROUND1_ALGORITHM_TESTS,
    ROUND1_CANDIDATE_SCHEMA_TESTS,
    ROUND1_GATE_TESTS,
    ROUND1_REQUIRED_FILES,
    ROUND1_SERIAL_FILES,
    ROUND1_SUPPLEMENTAL_FILES,
    round1_targets,
)
from tools import quality_gate_shared, test_registry
from tools.full_test_debt_shards import PERF_FILE_PATTERNS, classify_nodeid, is_perf_nodeid
from tools.long_gate_fingerprint import fingerprint_files
from tools.test_registry_data import REQUIRED_REGRESSION_COMMON_SCOPES
from tools.test_registry_groups_misc import MISC_REQUIRED_REGRESSION_GROUPS
from tools.test_registry_groups_scheduler import SCHEDULER_REQUIRED_REGRESSION_GROUPS
from tools.test_registry_groups_workbench import (
    WORKBENCH_REQUIRED_REGRESSION_GROUPS,
    WORKBENCH_REQUIRED_TESTS,
    WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS,
)

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "tests/workbench/"
REGISTRY_PATH = "tools/test_registry_groups_workbench.py"
CONTRACT_PATH = "tests/gate_meta/test_workbench_registry_contract.py"
LEDGER_FILES = (
    "test_execution_ledger.py",
    "test_execution_ledger_contracts.py",
    "test_execution_ledger_commands.py",
    "test_execution_ledger_constraints.py",
    "test_execution_ledger_legacy.py",
    "test_execution_ledger_scope.py",
    "test_execution_ledger_source_integrity.py",
    "test_execution_ledger_scale.py",
    *ROUND1_REQUIRED_FILES["workbench_execution_ledger"],
)
COMPLETED_BROWSER_FILES = (
    "test_trial_widgets.py", "test_calibration_adoption_widgets.py",
    "test_trial_adoption_widgets.py", "test_trial_export_widgets.py",
    "test_dashboard_widgets.py", "test_plan_adoption_baseline_browser.py",
    "test_trial_adoption_history_widgets.py",
    "test_process_quota_widgets.py",
    "test_outsourcing_widgets.py",
    "test_dashboard_external_handling_widgets.py",
    "test_du_system_restore_browser.py", "test_du_system_restore_contract.py",
    "test_point_frontend.py", "test_point_downstream_browser.py",
    "test_el_material_contracts.py", "test_point_dense_canvas.py",
    "test_piece_main_browser.py", "test_piece_presentation_browser.py",
    "test_ev_piece_fixture_contracts.py",
    "test_plan_scope_caption.py",
    "test_fg_plan_workspace_actions.py",
    "test_piece_downstream_api.py", "test_piece_downstream_browser.py",
    *ROUND1_SUPPLEMENTAL_FILES["workbench_browser"],
)
DASHBOARD_EXTERNAL_BROWSER_INPUTS = (
    *("frontend/workbench/app/" + name for name in (
        "ResourceControls.jsx", "WorkbenchControlStyles.jsx", "WorkbenchControlBridge.js",
        "WorkbenchSelectMenu.jsx", "WorkbenchDatePickerModel.js", "WorkbenchDatePicker.jsx",
        "WorkbenchControls.jsx", "WorkbenchNumberControls.jsx", "OutsourcingContract.js",
        "OutsourcingSession.js", "OutsourcingControls.jsx", "OutsourcingStyles.jsx", "OutsourcingWorkspace.jsx",
        "DashboardContract.js", "DashboardSession.js", "DashboardStyles.jsx", "DashboardPanels.jsx",
        "DashboardHistory.jsx", "DashboardHandling.jsx", "DashboardWorkspace.jsx",
    )),
    "tests/workbench/dashboard_external_handling_widgets_support.py",
    "tests/workbench/dashboard_external_handling_widgets_probe.cjs",
    "tests/workbench/outsourcing_widgets_support.py",
    "tests/workbench/outsourcing_support.py",
    "tests/workbench/test_live_browser.py",
    "tests/workbench/live_environment.py",
    "scripts/workbench/compile.cjs",
    "static/workbench/asset-manifest.json",
    "frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js",
    "tests/workbench/fixtures/schema-v29.sql",
)
SYSTEM_RESTORE_VIEW_INPUTS = (
    "web/bootstrap/workbench_system_restore_status.py",
    "web/bootstrap/workbench_system_restore_view.py",
    "templates/workbench/recovery.html",
    "tests/workbench/test_system_restore_entrypoint_support.py",
    "tests/workbench/test_system_restore_entrypoint_process_support.py",
    "tests/workbench/test_system_restore_host_support.py",
)
SYSTEM_RESTORE_BROWSER_INPUTS = (
    *SYSTEM_RESTORE_VIEW_INPUTS,
    *("frontend/workbench/app/" + name for name in (
        "SystemRestoreStatus.js", "SystemMaintenanceAPI.js", "SystemMaintenanceControls.jsx",
        "SystemRestorePanel.jsx", "SystemMaintenanceRecords.jsx", "SystemMaintenanceConfig.jsx",
        "SystemMaintenanceWorkspace.jsx", "SystemLive.jsx", "ResourceControls.jsx",
    )),
    "tests/workbench/du_system_restore_browser.cjs",
    "tests/workbench/system_maintenance_widgets_probe.cjs",
    "tests/workbench/system_config_saved_probe.cjs",
    "tests/workbench/test_live_browser.py", "tests/workbench/live_environment.py",
    "scripts/workbench/build-order.json", "scripts/workbench/compile.cjs",
    "static/workbench/asset-manifest.json",
    "frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js",
)
COMPLETED_REQUIRED_EXTENSIONS = {
    "workbench_resources": ("test_resource_table_domain_pairing.py", "test_fe01_resource_static_contract.py"),
    "workbench_process": (
        "test_process_quota_protection.py", "test_process_quota_protection_excel.py",
        "test_process_quota_protection_routes.py", "test_process_quota_protection_transactions.py",
        "test_process_quota_protection_stage_regressions.py",
        "test_process_quota_protection_file_receipts.py", "test_process_quota_protection_file_receipt_failures.py",
        "test_merged_cycle_projection.py", "test_merged_cycle_projection_api.py",
        "test_eu_process_fixture_contracts.py",
        *ROUND1_REQUIRED_FILES["workbench_process"],
    ),
    "workbench_plans": (
        "test_plan_adoption_baseline.py", "test_plan_adoption_baseline_api.py",
        "test_plan_adoption_baseline_integrity.py",
        *ROUND1_REQUIRED_FILES["workbench_plans"],
    ),
    "workbench_trial_adoption": (
        "test_trial_adoption_history.py", "test_trial_adoption_history_api.py",
        "test_trial_adoption_history_boundaries.py",
    ),
    "workbench_system": (
        "test_system_restore_host.py", "test_system_restore_host_drain.py", "test_system_restore_host_recovery.py",
        "test_system_restore_entrypoint.py", "test_system_restore_entrypoint_fail_closed.py",
        "test_system_restore_entrypoint_recovery.py",
        "test_du_system_restore_view.py",
        *ROUND1_REQUIRED_FILES["workbench_system"],
    ),
    "workbench_calibration_adoption": ("test_calibration_adoption_host.py",),
}
RUN_REQUIRED_FILES = {
    "workbench_run_jobs": (
        "test_run_runtime.py", "test_run_runtime_lock.py", "test_run_runtime_recovery.py",
        "test_run_runtime_lifecycle.py", "test_run_entrypoint.py",
        "test_run_history_queries.py", "test_run_history_snapshots.py",
        "test_run_history_integrity.py", "test_run_history_api.py",
        "test_run_candidate_queries.py", "test_run_candidate_boundaries.py",
        "test_run_candidate_exports.py", "test_run_candidate_api.py",
        "test_run_candidate_baseline_api.py", "test_run_candidate_baseline_queries.py",
        "test_run_candidate_baseline_integrity.py",
        "test_run_candidate_adoption.py", "test_run_candidate_adoption_resources.py",
        "test_run_candidate_adoption_atomic.py", "test_run_candidate_adoption_boundaries.py",
        "test_run_candidate_adoption_api.py",
        "test_run_adoption_host.py",
        *ROUND1_REQUIRED_FILES["workbench_run_jobs"],
    ),
}
RUN_SUPPLEMENTAL_FILES = {
    "workbench_browser": ("test_run_job_widgets.py", "test_run_candidate_widgets.py", "test_run_history_widgets.py", "test_run_live_server.py", "test_run_presentation.py", "test_run_baseline_widgets.py", "test_calibration_widgets.py", "test_run_adoption_widgets.py", "test_calibration_lineage_ui.py", *COMPLETED_BROWSER_FILES),
    "workbench_run_history_capacity": ("test_run_history_capacity.py",),
    "workbench_run_candidate_capacity": ("test_run_candidate_capacity.py",),
}
NEW_REQUIRED_FILES = {
    "workbench_preflight": (
        "test_preflight_api.py", "test_preflight_ledger.py", "test_preflight_capacity.py",
        "test_preflight_run_status.py",
    ),
    "workbench_trial": (
        "test_trial_lifecycle.py", "test_trial_validation.py", "test_trial_atomic.py",
        "test_trial_api_schema.py", "test_trial_edges.py", "test_trial_catalog.py",
        "test_ep_trial_fixture_contracts.py",
        "test_trial_predecessor_labels.py",
        "test_fe02_trial_static_contract.py",
        *ROUND1_REQUIRED_FILES["workbench_trial"],
    ),
    "workbench_template_lineage": (
        "test_template_lineage_schema.py", "test_template_lineage_writes.py",
        "test_template_lineage_integrity.py", "test_template_lineage_calibration.py",
        "test_legacy_batch_lineage_copy.py",
    ),
    "workbench_request_lifecycle": (
        "test_request_lifecycle_registration.py", "test_request_lifecycle_http.py",
        "test_request_lifecycle_errors.py", "test_request_lifecycle_maintenance.py",
        "test_request_lifecycle_runtime.py", "test_request_lifecycle_factory.py",
        "test_fe03_request_ticket_contract.py", "test_fe03_request_package_contract.py",
    ),
    "workbench_calibration_adoption": (
        "test_calibration_adoption.py", "test_calibration_adoption_schema.py",
        "test_calibration_adoption_drift.py", "test_calibration_adoption_transactions.py",
        "test_calibration_adoption_routes.py",
        "test_calibration_adoption_host.py",
    ),
    "workbench_trial_adoption": (
        "test_trial_adoption.py", "test_trial_adoption_validation.py",
        "test_trial_adoption_boundaries.py", "test_trial_adoption_atomic.py",
        "test_trial_adoption_raw.py", "test_trial_adoption_restart.py",
        "test_trial_adoption_api.py", "test_trial_adoption_host.py",
        *COMPLETED_REQUIRED_EXTENSIONS["workbench_trial_adoption"],
    ),
    "workbench_dashboard": (
        "test_dashboard_schema.py", "test_dashboard_reads.py", "test_dashboard_candidates.py",
        "test_dashboard_commands.py", "test_dashboard_atomic.py", "test_dashboard_api.py",
        "test_dashboard_host_connection.py", "test_dashboard_legacy.py",
        "test_dashboard_external_reads.py", "test_dashboard_external_identity.py", "test_dashboard_external_snapshot.py",
        "test_dashboard_external_handling_schema.py", "test_dashboard_external_handling_commands.py",
        "test_dashboard_external_handling_atomic.py", "test_dashboard_external_handling_identity.py",
        "test_dashboard_external_handling_api.py",
    ),
    "workbench_outsourcing": (
        "test_outsourcing_facts.py", "test_outsourcing_identity.py", "test_outsourcing_schema.py",
        "test_outsourcing_atomic.py", "test_outsourcing_api.py",
        "test_outsourcing_targets_labels.py",
        *ROUND1_REQUIRED_FILES["workbench_outsourcing"],
    ),
    "workbench_zero_duration": (
        "test_zero_duration_contract.py", "test_zero_duration_calendar.py", "test_zero_duration_boundaries.py",
        "test_ea_zero_duration_chain.py", "test_ea_zero_duration_boundaries.py", "test_ea_zero_duration_constraints.py",
        "test_point_public_contract.py",
        "test_point_adoption_host.py",
    ),
    "workbench_piece_adoption": (
        "test_piece_adoption.py", "test_piece_adoption_boundaries.py",
        "test_piece_adoption_execution.py", "test_piece_adoption_persistence.py",
        "test_piece_chain_input.py", "test_piece_chain_end_to_end.py",
        "test_piece_chain_execution.py", "test_piece_chain_external.py", "test_piece_chain_boundaries.py",
        "test_piece_presentation.py", "test_piece_production_connection.py",
        *ROUND1_REQUIRED_FILES["workbench_piece_adoption"],
    ),
    "workbench_field": (
        "test_field_workspace_api.py", "test_field_files_api.py", "test_field_files_codec.py",
        "test_actual_gantt_api.py", "test_point_downstream_api.py",
        *ROUND1_REQUIRED_FILES["workbench_field"],
    ),
}
NEW_SUPPLEMENTAL_FILES = {
    "workbench_browser": ("test_run_adoption_widgets.py", "test_calibration_lineage_ui.py", *COMPLETED_BROWSER_FILES),
    "workbench_trial_capacity": ("test_trial_scale.py",),
    "workbench_lineage_lookup_capacity": ("test_lineage_lookup_budget.py",),
    "workbench_dashboard_capacity": ("test_dashboard_capacity.py",),
}
BUSY_BLOCK_FILES = (
    "tests/algorithm/test_busy_block_native_equivalence.py",
    "tests/algorithm/test_busy_block_boundaries.py",
)
POINT_PIECE_INPUTS = (
    "core/errors.py", "web/routes/workbench/materials.py",
    "core/models/workbench_piece_adoption.py", "core/models/workbench_execution.py",
    "core/models/workbench_plan_scope.py", "core/models/workbench_run_compute.py",
    "core/models/workbench_trial_codec.py", "core/services/workbench/zero_duration.py",
    "core/services/workbench/zero_duration_evidence.py", "core/services/workbench/plan_point_evidence.py",
    "core/services/workbench/point_plan_query.py", "core/services/workbench/plan_baseline.py",
    "core/services/workbench/piece_adoption.py", "core/services/workbench/piece_adoption_scope.py",
    "core/services/workbench/piece_adoption_facts.py", "core/services/workbench/piece_adoption_execution.py",
    "core/services/workbench/run_input.py", "core/services/workbench/run_compute.py",
    "core/services/workbench/run_worker.py", "core/services/workbench/run_candidate_adoption.py",
    "core/services/workbench/trial_adoption.py", "core/services/workbench/trial_validation.py",
    "core/services/workbench/official_plan_persistence.py", "core/services/workbench/production_report.py",
    "core/services/workbench/execution_ledger.py", "data/repositories/workbench_plan_identity_repo.py",
    "tests/workbench/ea_zero_duration_support.py", "tests/workbench/test_piece_adoption_support.py",
    "tests/workbench/test_run_candidate_support.py", "tests/workbench/trial_support.py",
)
ALGORITHM_CALENDAR_INPUTS = (
    "schema.sql", "core/infrastructure/migrations/v31.py",
    "core/algorithm_contracts/schedule_point_evidence.py", "core/algorithm_runtime/busy_block_skip.py",
    "core/algorithm_runtime/internal_slot.py", "core/algorithm_runtime/downtime.py",
    "core/algorithm_runtime/piece_input.py", "core/algorithms/greedy/scheduler.py",
    "core/services/scheduler/calendar_engine.py", "core/services/scheduler/calendar_service.py",
    "core/services/scheduler/operator_shift_calendar.py",
    "core/services/scheduler/run/schedule_payload_contract.py",
    "core/services/scheduler/run/schedule_execution_persistence_guard.py",
    "core/services/scheduler/run/schedule_execution_reservations.py",
)
DELIVERED_REQUIRED_INPUTS = (
    ("web/bootstrap/__init__.py", "workbench_request_lifecycle"),
    ("web/bootstrap/factory.py", "workbench_request_lifecycle"),
    ("web/routes/workbench/registration.py", "workbench_request_lifecycle"),
    ("web/routes/workbench/pages.py", "workbench_request_lifecycle"),
    ("tests/workbench/fe03_route_manifest.json", "workbench_request_lifecycle"),
    ("core/models/workbench_trial_codec.py", "workbench_trial"),
    ("core/services/workbench/trial_base.py", "workbench_trial"),
    ("core/services/workbench/trial_capacity.py", "workbench_trial"),
    ("core/services/workbench/trial_adoption_history_evidence.py", "workbench_trial"),
    ("data/repositories/workbench_trial_raw_repo.py", "workbench_trial"),
    ("data/repositories/workbench_trial_repo.py", "workbench_trial"),
    ("core/services/workbench/preflight_result.py", "workbench_preflight"),
    ("core/services/workbench/run_jobs.py", "workbench_preflight"),
    ("tests/workbench/test_preflight_support.py", "workbench_preflight"),
    ("tests/workbench/test_request_lifecycle_support.py", "workbench_preflight"),
    ("web/routes/workbench/scheduling_jobs.py", "workbench_preflight"),
    ("web/bootstrap/factory.py", "workbench_preflight"),
    ("web/bootstrap/launcher_runtime_lock.py", "workbench_preflight"),
    ("web/bootstrap/workbench_request_lifecycle.py", "workbench_preflight"),
    ("web/bootstrap/workbench_run_runtime.py", "workbench_preflight"),
    ("tests/workbench/test_piece_chain_support.py", "workbench_piece_adoption"),
    ("core/services/workbench/piece_adoption_trial.py", "workbench_piece_adoption"),
    ("core/algorithm_runtime/piece_input.py", "workbench_piece_adoption"),
    ("tests/workbench/merged_cycle_projection_support.py", "workbench_process"),
    ("core/services/process/workflow_state.py", "workbench_process"),
    ("core/services/workbench/process_queries.py", "workbench_process"),
    ("frontend/workbench/app/resource-contract.js", "workbench_process"),
    ("frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js", "workbench_process"),
    ("tests/workbench/process_detail_files_probe.cjs", "workbench_process"),
    ("tests/workbench/process_stage_widgets_probe.cjs", "workbench_process"),
    ("tests/workbench/process_widgets_probe.cjs", "workbench_process"),
    ("tests/workbench/run_entrypoint_support.py", "workbench_zero_duration"),
    ("tests/workbench/trial_adoption_support.py", "workbench_zero_duration"),
    ("web/routes/workbench/actual_gantt.py", "workbench_zero_duration"),
    ("web/routes/workbench/execution.py", "workbench_zero_duration"),
    ("tests/workbench/point_public_contract_probe.cjs", "workbench_zero_duration"),
    ("frontend/workbench/app/PointContract.js", "workbench_zero_duration"),
    ("frontend/workbench/app/RunCandidateAPI.js", "workbench_zero_duration"),
    ("frontend/workbench/app/RunBaselineAPI.js", "workbench_zero_duration"),
    ("tests/workbench/run_baseline_widgets_support.py", "workbench_trial"),
    ("tests/workbench/trial_widgets_support.py", "workbench_trial"),
    ("tests/workbench/point_downstream_support.py", "workbench_field"),
    ("core/services/workbench/actual_gantt.py", "workbench_field"),
    ("core/services/workbench/field_workspace.py", "workbench_field"),
    ("core/services/workbench/point_plan_query.py", "workbench_field"),
    ("web/routes/workbench/reports.py", "workbench_field"),
    ("tests/workbench/piece_production_connection_support.py", "workbench_piece_adoption"),
    ("core/infrastructure/database.py", "workbench_piece_adoption"),
    ("core/services/workbench/plan_projection.py", "workbench_piece_adoption"),
    ("core/services/workbench/run_candidate_facts.py", "workbench_piece_adoption"),
    ("core/services/workbench/run_candidate_tasks.py", "workbench_piece_adoption"),
    ("core/services/workbench/trial_adoption_validation.py", "workbench_piece_adoption"),
    ("tests/workbench/trial_predecessor_labels_probe.cjs", "workbench_trial"),
    ("frontend/workbench/app/PointContract.js", "workbench_trial"),
    ("frontend/workbench/app/ResourceControls.jsx", "workbench_trial"),
    ("frontend/workbench/app/TrialControls.jsx", "workbench_trial"),
    ("frontend/workbench/app/TrialGantt.jsx", "workbench_trial"),
    ("frontend/workbench/app/TrialDetails.jsx", "workbench_trial"),
    ("scripts/workbench/compile.cjs", "workbench_trial"),
    ("frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js", "workbench_trial"),
    ("frontend/workbench/prototype/ui_kits/workbench/assets/vendor/react-18.3.1.js", "workbench_trial"),
)
DELIVERED_BROWSER_INPUTS = (
    "tests/workbench/piece_downstream_contract.cjs", "tests/workbench/piece_downstream_browser.cjs",
    "tests/workbench/piece_downstream_browser_support.cjs",
    "frontend/workbench/app/FieldContract.js", "frontend/workbench/app/FieldTable.jsx",
    "frontend/workbench/app/FieldDetail.jsx", "frontend/workbench/app/ActualGanttContract.js",
    "frontend/workbench/app/ActualGanttModel.js", "frontend/workbench/app/ActualGanttRows.jsx",
    "core/services/workbench/field_workspace.py", "core/services/workbench/field_workspace_scope.py",
    "core/services/workbench/actual_gantt_scope.py", "core/services/workbench/actual_gantt_export.py",
    "tests/workbench/fg_plan_workspace_actions_probe.cjs", "tests/workbench/test_plan_adoption_baseline_support.py",
    "tests/workbench/plan_ui_browser_probe.cjs", "tests/workbench/plan_ui_browser_harness.cjs",
    "tests/workbench/plan_scope_caption_probe.cjs", "tests/workbench/ea_zero_duration_support.py",
    "web/routes/workbench/plan_reads.py", "core/services/workbench/plan_projection.py",
    "frontend/workbench/app/PlanWorkspace.jsx", "frontend/workbench/app/PlanLayout.jsx",
    "frontend/workbench/app/PlanAPI.js",
    "tests/workbench/point_frontend_support.py", "tests/workbench/point_frontend_probe.cjs",
    "tests/workbench/point_browser_build.cjs", "tests/workbench/point_browser_host.jsx",
    "tests/workbench/point_browser_probe.cjs", "tests/workbench/point_dense_canvas_probe.cjs",
    "tests/workbench/point_downstream_support.py", "tests/workbench/point_downstream_browser.cjs",
    "tests/workbench/point_downstream_browser_build_support.cjs",
    "tests/workbench/el_material_contracts.cjs", "tests/workbench/el_material_paging.cjs",
    "frontend/workbench/app/PointContract.js", "frontend/workbench/app/PointGanttModel.js",
    "frontend/workbench/app/PointGantt.jsx", "frontend/workbench/app/PlanGanttCanvas.jsx",
    "frontend/workbench/app/PlanGantt.jsx", "frontend/workbench/app/PlanContract.js",
    "frontend/workbench/app/resource-contract.js", "frontend/workbench/app/ResourceWorkspace.jsx",
    "tests/workbench/piece_main_server.py", "tests/workbench/piece_main_seed.py",
    "tests/workbench/piece_main_oracle.py", "tests/workbench/piece_main_build.cjs",
    "tests/workbench/piece_main_browser.cjs", "tests/workbench/piece_main_actions.cjs",
    "tests/workbench/piece_main_dependencies.cjs", "tests/workbench/piece_main_recovery.cjs",
    "tests/workbench/piece_main_visuals.cjs",
    "tests/workbench/piece_presentation_build.cjs", "tests/workbench/piece_presentation_host.jsx",
    "tests/workbench/piece_presentation_browser.cjs", "tests/workbench/piece_presentation_contract.cjs",
    "tests/workbench/test_piece_chain_support.py", "tests/workbench/test_run_candidate_baseline_support.py",
    "tests/workbench/test_run_candidate_support.py", "tests/workbench/plan_catalog_support.py",
    "tests/workbench/trial_support.py", "tests/workbench/plan_ui_fixtures.cjs",
    "tests/workbench/live_environment.py", "tests/workbench/run_live_server.py",
    "tests/workbench/run_live_server_support.py",
    "frontend/workbench/app/main.jsx", "frontend/workbench/app/PlanGanttModel.js",
    "frontend/workbench/app/RunCandidateAPI.js", "frontend/workbench/app/RunCandidateModel.js",
    "frontend/workbench/app/RunBaselineAPI.js", "frontend/workbench/app/RunBaselineModel.js",
    "frontend/workbench/app/TrialDetails.jsx", "frontend/workbench/app/TrialGantt.jsx",
    "scripts/workbench/build-order.json", "scripts/workbench/compile.cjs",
    "static/workbench/asset-manifest.json",
    "frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js",
)
DELIVERED_OPT_IN_FILES = (
    "test_ed_material_process_browser.py", "test_el_material_browser.py", "test_reports_review_browser.py",
    "test_merged_cycle_ui.py", "test_secondary_copy_contrast.py",
)
DELIVERED_OPT_IN_INPUTS = (
    "tests/workbench/merged_cycle_ui_contract.cjs", "tests/workbench/merged_cycle_projection_support.py",
    "tests/workbench/merged_cycle_ui_runner.py", "tests/workbench/merged_cycle_ui_server.py",
    "tests/workbench/merged_cycle_ui_assets.py", "tests/workbench/merged_cycle_ui_seed.py",
    "tests/workbench/merged_cycle_ui_probe.cjs", "tests/workbench/merged_cycle_ui_steps.cjs",
    "tests/workbench/secondary_copy_assets.py", "tests/workbench/secondary_copy_server.py",
    "tests/workbench/secondary_copy_component_probe.cjs", "tests/workbench/secondary_copy_live_probe.cjs",
    "tests/workbench/secondary_copy_metrics.cjs", "tests/workbench/az_contrast_modal_harness.cjs",
    "tests/workbench/az_contrast_modal_fixture.jsx", "frontend/workbench/app/WorkbenchControlStyles.jsx",
    "tests/workbench/ed_material_process_server.py", "tests/workbench/ed_material_process_seed.py",
    "tests/workbench/ed_material_process_assets.py", "tests/workbench/ed_material_process_probe.cjs",
    "tests/workbench/ed_material_process_material.cjs", "tests/workbench/ed_material_process_filters.cjs",
    "tests/workbench/ed_material_process_stages.cjs", "tests/workbench/ed_material_process_states.cjs",
    "tests/workbench/ed_material_process_visual.cjs", "tests/workbench/migrated_process_batch_support.cjs",
    "tests/workbench/el_material_server.py", "tests/workbench/el_material_assets.py",
    "tests/workbench/el_material_probe.cjs", "tests/workbench/el_material_actions.cjs",
    "tests/workbench/reports_review_browser_server.py", "tests/workbench/reports_review_browser_seed.py",
    "tests/workbench/reports_review_browser_oracle.py", "tests/workbench/reports_review_browser_probe.cjs",
    "tests/workbench/reports_review_browser_actions.cjs", "tests/workbench/reports_review_browser_details.cjs",
    "tests/workbench/reports_review_browser_support.cjs",
    "tests/workbench/run_live_server.py", "tests/workbench/run_live_server_support.py",
)


def _targets(groups):
    return [path for group in groups for path in group["target_paths"]]


def _groups():
    return {row["group_id"]: row for row in test_registry.iter_required_regression_groups()}


def _has_test_definition(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
               for node in ast.walk(tree))


def test_existing_groups_remain_an_unchanged_prefix_and_all_targets_stay_required():
    legacy = (*SCHEDULER_REQUIRED_REGRESSION_GROUPS, *MISC_REQUIRED_REGRESSION_GROUPS)
    assert test_registry.REQUIRED_REGRESSION_GROUPS == (*legacy, *WORKBENCH_REQUIRED_REGRESSION_GROUPS)
    required = test_registry.iter_required_tests()
    assert required == quality_gate_shared.iter_quality_gate_required_tests()
    assert required == list(test_registry.QUALITY_GATE_REQUIRED_TESTS)
    assert required[-len(WORKBENCH_REQUIRED_TESTS):] == list(WORKBENCH_REQUIRED_TESTS)
    assert set(required[:-len(WORKBENCH_REQUIRED_TESTS)]) == set(_targets(legacy))
    assert required[0] == test_registry.QUALITY_GATE_SELFTEST_PATH
    assert set(required).isdisjoint(test_registry.iter_startup_regressions())


def test_raw_targets_and_group_ids_are_unique_before_normalization():
    groups = (*test_registry.REQUIRED_REGRESSION_GROUPS, *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    assert len(groups) == len({group["group_id"] for group in groups})
    assert all(count == 1 for count in Counter(_targets(groups)).values())
    assert len(test_registry.QUALITY_GATE_REQUIRED_TESTS) == len(set(test_registry.QUALITY_GATE_REQUIRED_TESTS))
    coverage = test_registry.validate_required_regression_group_coverage(test_registry.QUALITY_GATE_REQUIRED_TESTS)
    assert coverage["missing"] == coverage["unknown"] == coverage["duplicates"] == []
    assert coverage["required_target_count"] == coverage["group_target_count"]
    assert test_registry.iter_required_regression_groups() == test_registry.iter_required_regression_groups()
    assert test_registry.hash_required_regression_groups() == test_registry.hash_required_regression_groups()


def test_every_workbench_target_is_an_explicit_existing_test_not_support_or_server():
    groups = (*WORKBENCH_REQUIRED_REGRESSION_GROUPS, *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    for target in _targets(groups):
        path = ROOT / target
        assert not any(char in target for char in "*?[]:"), target
        assert path.is_file() and path.suffix == ".py", target
        assert not path.name.endswith("_support.py"), target
        assert _has_test_definition(path), target


def test_discovery_reports_unregistered_real_tests_without_expanding_targets():
    groups = (*WORKBENCH_REQUIRED_REGRESSION_GROUPS, *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    # Discovery is an audit only, never a source for the fixed target registry.
    discovered = {str(path.relative_to(ROOT)) for path in (ROOT / "tests/workbench").glob("test_*.py")
                  if _has_test_definition(path) and not path.name.endswith("_support.py")}
    missing = sorted(discovered - set(_targets(groups)))
    assert not missing, "Unregistered real tests (review and register explicitly):\n" + "\n".join(missing)


def test_all_eight_ledger_domains_are_required_and_main_migration_is_separate():
    groups = _groups()
    assert groups["workbench_execution_ledger"]["target_paths"] == [PREFIX + name for name in LEDGER_FILES]
    migration = PREFIX + "test_execution_ledger_migration.py"
    assert migration in groups["workbench_mainmigration"]["target_paths"]
    assert migration not in groups["workbench_execution_ledger"]["target_paths"]
    assert "core/infrastructure/migrations/v25.py" in groups["workbench_mainmigration"]["input_file_scopes"]
    assert "tests/workbench/fixtures/schema-v24.sql" in groups["workbench_mainmigration"]["input_file_scopes"]
    assert PREFIX + "test_run_schema_migration.py" in groups["workbench_mainmigration"]["target_paths"]
    assert "core/infrastructure/migrations/v26.py" in groups["workbench_mainmigration"]["input_file_scopes"]
    assert "tests/workbench/fixtures/schema-v25.sql" in groups["workbench_mainmigration"]["input_file_scopes"]


@pytest.mark.parametrize("group_id,filenames,required", (
    *[(group_id, filenames, True) for group_id, filenames in RUN_REQUIRED_FILES.items()],
    *[(group_id, filenames, False) for group_id, filenames in RUN_SUPPLEMENTAL_FILES.items()],
))
def test_run_targets_keep_fixed_owners_order_and_gate_classification(group_id, filenames, required):
    inventory = WORKBENCH_REQUIRED_REGRESSION_GROUPS if required else WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
    groups = {row["group_id"]: row for row in inventory}
    expected = tuple(PREFIX + name for name in filenames)
    assert tuple(round1_targets(groups[group_id])[-len(expected):]) == expected
    for path in expected:
        assert quality_gate_shared.quality_gate_required_test_nodeid_matches(path + "::test_contract") is required


def test_run_job_extension_preserves_all_previous_targets_in_order():
    original = ("test_run_jobs.py", "test_run_jobs_schema.py", "test_run_jobs_api.py", "test_run_jobs_atomic.py",
                "test_run_jobs_concurrency.py", "test_run_jobs_recovery.py", "test_run_jobs_restart.py")
    assert _groups()["workbench_run_jobs"]["target_paths"] == [
        PREFIX + name for name in (*original, *RUN_REQUIRED_FILES["workbench_run_jobs"])]


@pytest.mark.parametrize("group_id,filenames", NEW_REQUIRED_FILES.items())
def test_trial_lineage_and_request_groups_have_fixed_order_and_required_owners(group_id, filenames):
    expected = [PREFIX + name for name in filenames]
    assert _groups()[group_id]["target_paths"] == expected
    for path in expected:
        assert [row["group_id"] for row in WORKBENCH_REQUIRED_REGRESSION_GROUPS
                if path in row["target_paths"]] == [group_id]
        assert quality_gate_shared.quality_gate_required_test_nodeid_matches(path + "::test_contract")
        serial = "runtime" in path or Path(path).name in ROUND1_SERIAL_FILES
        assert classify_nodeid(path + "::test_contract") == ("serial" if serial else "parallel")
        assert not is_perf_nodeid(path + "::test_contract")
        plan = daily._build_impact_plan(daily.ChangedPathSet([path], True, "contract"))
        assert not plan.all_required_groups, plan.reason
        assert group_id in plan.selected_group_ids
        assert set(expected) <= set(plan.target_paths)


@pytest.mark.parametrize("path", BUSY_BLOCK_FILES)
def test_completed_busy_block_files_are_fixed_required_scheduler_targets(path):
    assert _has_test_definition(ROOT / path)
    assert [row["group_id"] for row in test_registry.REQUIRED_REGRESSION_GROUPS
            if path in row["target_paths"]] == ["scheduler_run_core"]
    expected_tail = (*BUSY_BLOCK_FILES, *ROUND1_ALGORITHM_TESTS, *ROUND1_CANDIDATE_SCHEMA_TESTS)
    assert tuple(round1_targets(_groups()["scheduler_run_core"])[-len(expected_tail):]) == expected_tail
    assert quality_gate_shared.quality_gate_required_test_nodeid_matches(path + "::test_contract")
    assert classify_nodeid(path + "::test_contract") == "parallel"
    assert not is_perf_nodeid(path + "::test_contract")
    plan = daily._build_impact_plan(daily.ChangedPathSet([path], True, "contract"))
    assert not plan.all_required_groups, plan.reason
    assert "scheduler_run_core" in plan.selected_group_ids
    assert set(BUSY_BLOCK_FILES) <= set(plan.target_paths)


@pytest.mark.parametrize("source,group_id", (
    *((source, group) for source in (*POINT_PIECE_INPUTS, *ALGORITHM_CALENDAR_INPUTS)
      for group in ("workbench_zero_duration", "workbench_piece_adoption")),
    *((source, "scheduler_run_core") for source in (*ALGORITHM_CALENDAR_INPUTS, "tests/_support/busy_block_case.py")),
))
def test_completed_ea_ec_eg_sources_select_their_required_tests(source, group_id):
    assert (ROOT / source).is_file()
    plan = daily._build_impact_plan(daily.ChangedPathSet([source], True, "contract"))
    assert not plan.all_required_groups, plan.reason
    assert group_id in plan.selected_group_ids
    assert set(_groups()[group_id]["target_paths"]) <= set(plan.target_paths)
    if source.endswith("_support.py") or source == "tests/_support/busy_block_case.py":
        assert source in _groups()[group_id]["input_file_scopes"] or any(
            daily._path_matches_pattern(source, scope) for scope in _groups()[group_id]["input_file_scopes"])
        assert source not in plan.target_paths
        assert not test_registry.required_test_nodeid_matches(source + "::test_placeholder")


def test_mainmigration_extension_preserves_previous_owners_and_order():
    expected = (
        "test_execution_ledger_migration.py", "test_run_schema_migration.py",
        "test_plan_migration_integration.py", "test_migration_pages_fixture.py",
        "test_trial_lineage_migration.py",
        "test_lineage_lookup_migration.py",
        "test_calibration_dashboard_migration.py",
        "test_outsourcing_identity_migration.py",
        "test_dashboard_external_migration.py",
    )
    assert _groups()["workbench_mainmigration"]["target_paths"] == [PREFIX + name for name in expected]
    assert hashlib.sha256((ROOT / "tests/workbench/fixtures/schema-v28.sql").read_bytes()).hexdigest() == (
        "2520295cebbe708270f93ed0aa5a6b18ea9b93ad3a1c77dd6c7a857fea44ad52")
    assert PREFIX + "calibration_dashboard_migration_support.py" not in test_registry.iter_required_tests()
    assert hashlib.sha256((ROOT / "tests/workbench/fixtures/schema-v29.sql").read_bytes()).hexdigest() == (
        "d303a3b004546845c214d3907e1dc27c8c630132da2096feaaa15ed374333648")
    assert PREFIX + "outsourcing_identity_migration_support.py" not in test_registry.iter_required_tests()
    assert hashlib.sha256((ROOT / "tests/workbench/fixtures/schema-v30.sql").read_bytes()).hexdigest() == (
        "16460ac6d0f95373eca466b101cfcc46097187760e2438fb3a8c292c28761b2e")
    assert PREFIX + "dashboard_external_migration_support.py" not in test_registry.iter_required_tests()


@pytest.mark.parametrize("group_id,filenames", COMPLETED_REQUIRED_EXTENSIONS.items())
def test_completed_extensions_keep_exact_required_owner_and_append_order(group_id, filenames):
    expected = [PREFIX + name for name in filenames]
    assert _groups()[group_id]["target_paths"][-len(expected):] == expected
    for path in expected:
        assert [row["group_id"] for row in WORKBENCH_REQUIRED_REGRESSION_GROUPS
                if path in row["target_paths"]] == [group_id]
        assert quality_gate_shared.quality_gate_required_test_nodeid_matches(path + "::test_contract")
        plan = daily._build_impact_plan(daily.ChangedPathSet([path], True, "contract"))
        assert not plan.all_required_groups, plan.reason
        assert group_id in plan.selected_group_ids
        assert set(expected) <= set(plan.target_paths)


@pytest.mark.parametrize("source,group_id", (
    *((source, "workbench_system") for source in SYSTEM_RESTORE_VIEW_INPUTS),
    ("web/bootstrap/workbench_system_restore.py", "workbench_system"),
    ("web/bootstrap/workbench_system_restore_recovery.py", "workbench_system"),
    ("tests/workbench/test_system_restore_host_support.py", "workbench_system"),
    ("tests/workbench/calibration_adoption_host_support.py", "workbench_calibration_adoption"),
    ("core/services/workbench/outsourcing_commands.py", "workbench_outsourcing"),
    ("data/repositories/workbench_outsourcing_source_repo.py", "workbench_outsourcing"),
    ("web/routes/workbench/outsourcing.py", "workbench_outsourcing"),
    ("tests/workbench/outsourcing_support.py", "workbench_outsourcing"),
    ("tests/workbench/outsourcing_targets_labels_support.py", "workbench_outsourcing"),
    ("tests/workbench/fixtures/schema-v29.sql", "workbench_outsourcing"),
    ("core/services/workbench/dashboard_external.py", "workbench_dashboard"),
    ("core/services/workbench/dashboard_external_sources.py", "workbench_dashboard"),
    ("core/services/workbench/outsourcing.py", "workbench_dashboard"),
    ("core/services/workbench/outsourcing_projection.py", "workbench_dashboard"),
    ("data/repositories/workbench_outsourcing_source_repo.py", "workbench_dashboard"),
    ("tests/workbench/dashboard_external_support.py", "workbench_dashboard"),
    ("core/infrastructure/migrations/v30.py", "workbench_mainmigration"),
    ("core/infrastructure/workbench_outsourcing_schema.py", "workbench_mainmigration"),
    ("core/infrastructure/workbench_plan_identity_write_guard.py", "workbench_mainmigration"),
    ("tests/workbench/outsourcing_identity_migration_support.py", "workbench_mainmigration"),
    ("tests/workbench/fixtures/schema-v29.sql", "workbench_mainmigration"),
    ("core/infrastructure/migrations/v31.py", "workbench_mainmigration"),
    ("core/infrastructure/workbench_dashboard_external_schema.py", "workbench_mainmigration"),
    ("tests/workbench/dashboard_external_migration_support.py", "workbench_mainmigration"),
    ("tests/workbench/fixtures/schema-v30.sql", "workbench_mainmigration"),
    ("core/infrastructure/workbench_dashboard_external_schema.py", "workbench_dashboard"),
    ("data/repositories/workbench_dashboard_external_repo.py", "workbench_dashboard"),
    ("tests/workbench/dashboard_external_handling_support.py", "workbench_dashboard"),
    ("tests/workbench/dashboard_external_migration_support.py", "workbench_dashboard"),
    ("web/bootstrap/entrypoint.py", "workbench_system"),
    ("web/bootstrap/launcher_shutdown.py", "workbench_system"),
    ("web/bootstrap/launcher_stop.py", "workbench_system"),
    ("web/bootstrap/workbench_system_restore_status.py", "workbench_system"),
    ("tests/workbench/test_system_restore_entrypoint_support.py", "workbench_system"),
    ("tests/workbench/test_system_restore_entrypoint_process_support.py", "workbench_system"),
    ("tests/workbench/test_system_restore_entrypoint_legacy_support.py", "workbench_system"),
    ("core/services/workbench/zero_duration.py", "workbench_zero_duration"),
    ("core/algorithm_runtime/internal_slot.py", "workbench_zero_duration"),
    ("core/services/workbench/trial_validation.py", "workbench_zero_duration"),
    ("core/services/workbench/run_compute.py", "workbench_zero_duration"),
    ("tests/workbench/zero_duration_support.py", "workbench_zero_duration"),
))
def test_dq_completed_groups_follow_actual_changed_sources(source, group_id):
    assert (ROOT / source).is_file()
    plan = daily._build_impact_plan(daily.ChangedPathSet([source], True, "contract"))
    assert not plan.all_required_groups, plan.reason
    assert group_id in plan.selected_group_ids
    assert set(_groups()[group_id]["target_paths"]) <= set(plan.target_paths)


@pytest.mark.parametrize("group_id,filenames", NEW_SUPPLEMENTAL_FILES.items())
def test_new_browser_and_capacity_inventory_never_enters_daily_required_targets(group_id, filenames):
    groups = {row["group_id"]: row for row in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS}
    expected = tuple(PREFIX + name for name in filenames)
    assert tuple(round1_targets(groups[group_id])[-len(expected):]) == expected
    supplemental = set(_targets(WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS))
    for path in expected:
        assert [row["group_id"] for row in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
                if path in row["target_paths"]] == [group_id]
        assert not quality_gate_shared.quality_gate_required_test_nodeid_matches(path + "::test_contract")
        assert classify_nodeid(path + "::test_contract") == "parallel"
        assert not is_perf_nodeid(path + "::test_contract")
        plan = daily._build_impact_plan(daily.ChangedPathSet([path], True, "contract"))
        assert not plan.all_required_groups, plan.reason
        assert plan.target_paths and CONTRACT_PATH in plan.target_paths
        assert group_id not in plan.selected_group_ids
        assert supplemental.isdisjoint(plan.target_paths)


@pytest.mark.parametrize("group_id,filename", (
    ("workbench_foundation", "test_entry.py"),
    ("workbench_resources", "test_resource_api.py"),
    ("workbench_resources", "test_material_actions_api.py"),
    ("workbench_process", "test_process_collection_api_transactions.py"),
    ("workbench_process", "test_process_stage_api.py"),
    ("workbench_process", "test_process_file_api_transactions.py"),
    ("workbench_batches", "test_batch_execution_ledger_atomic.py"),
    ("workbench_plans", "test_plan_query_api.py"),
    ("workbench_plans", "test_plan_export_api.py"),
    ("workbench_plans", "test_official_plan_persistence.py"),
    ("workbench_reports", "test_report_execution_ledger_export.py"),
    ("workbench_system", "test_system_maintenance_api.py"),
    ("workbench_system", "test_master_overview_reads.py"),
    ("workbench_execution_scheduler", "test_scheduler_execution_ledger_snapshot.py"),
    ("workbench_field", "test_field_workspace_api.py"),
    ("workbench_field", "test_actual_gantt_api.py"),
    ("workbench_preflight", "test_preflight_api.py"),
    ("workbench_mainmigration", "test_migration_pages_fixture.py"),
    ("workbench_mainmigration", "test_trial_lineage_migration.py"),
    ("workbench_mainmigration", "test_lineage_lookup_migration.py"),
    ("workbench_mainmigration", "test_calibration_dashboard_migration.py"),
    ("workbench_mainmigration", "test_outsourcing_identity_migration.py"),
    ("workbench_mainmigration", "test_dashboard_external_migration.py"),
    ("workbench_system", "test_system_restore_entrypoint.py"),
    ("workbench_system", "test_system_restore_entrypoint_fail_closed.py"),
    ("workbench_system", "test_system_restore_entrypoint_recovery.py"),
    ("workbench_run_compute", "test_run_compute_integration.py"),
    ("workbench_run_jobs", "test_run_jobs_api.py"),
    ("workbench_run_jobs", "test_run_adoption_host.py"),
    ("workbench_calibration", "test_calibration_routes.py"),
))
def test_critical_api_contract_has_exact_owner_and_required_nodeid(group_id, filename):
    path = PREFIX + filename
    assert path in _groups()[group_id]["target_paths"]
    assert quality_gate_shared.quality_gate_required_test_nodeid_matches(path + "::test_contract")


@pytest.mark.parametrize("source,group_id", (
    ("web/routes/workbench/pages.py", "workbench_foundation"),
    ("core/services/workbench/resource_entities.py", "workbench_resources"),
    ("core/services/workbench/resource_table_facts.py", "workbench_resources"),
    ("core/services/workbench/material_files.py", "workbench_resources"),
    ("web/routes/workbench/calendars.py", "workbench_resources"),
    ("core/services/workbench/process_stage_apply.py", "workbench_process"),
    ("web/routes/workbench/process_file_exports.py", "workbench_process"),
    ("core/services/workbench/batch_execution.py", "workbench_batches"),
    ("core/services/workbench/plan_delivery.py", "workbench_plans"),
    ("core/services/workbench/plan_adoption_baseline.py", "workbench_plans"),
    ("core/services/workbench/plan_adoption_baseline_identity.py", "workbench_plans"),
    ("core/services/workbench/plan_adoption_baseline_sources.py", "workbench_plans"),
    ("core/services/workbench/plan_adoption_baseline_values.py", "workbench_plans"),
    ("core/services/workbench/run_candidate_adoption_storage.py", "workbench_plans"),
    ("core/services/workbench/run_candidate_baseline.py", "workbench_plans"),
    ("core/services/workbench/run_candidate_facts.py", "workbench_plans"),
    ("core/services/workbench/run_candidate_storage.py", "workbench_plans"),
    ("core/services/workbench/trial_adoption_storage.py", "workbench_plans"),
    ("core/models/workbench_trial_codec.py", "workbench_plans"),
    ("tests/workbench/test_plan_adoption_baseline_support.py", "workbench_plans"),
    ("core/services/workbench/process_quota_protection.py", "workbench_process"),
    ("core/services/process/part_service.py", "workbench_process"),
    ("core/services/process/part_operation_hours_excel_import_service.py", "workbench_process"),
    ("data/repositories/workbench_calibration_adoption_repo.py", "workbench_process"),
    ("tests/workbench/process_quota_protection_support.py", "workbench_process"),
    ("tests/workbench/process_quota_protection_file_receipt_support.py", "workbench_process"),
    ("core/services/scheduler/workbench_plan_catalog.py", "workbench_plans"),
    ("web/routes/workbench/plan_reads.py", "workbench_plans"),
    ("core/services/workbench/review_projection.py", "workbench_reports"),
    ("web/routes/workbench/reports.py", "workbench_reports"),
    ("core/services/workbench/system_journal.py", "workbench_system"),
    ("core/services/system/workbench_overview.py", "workbench_system"),
    ("core/services/workbench/master_overview.py", "workbench_system"),
    ("core/services/workbench/execution_ledger.py", "workbench_execution_ledger"),
    ("core/services/workbench/production_report.py", "workbench_execution_ledger"),
    ("data/repositories/workbench_execution_source_repo.py", "workbench_execution_ledger"),
    ("core/services/scheduler/execution/execution_ledger_adapter.py", "workbench_execution_scheduler"),
    ("core/services/workbench/field_report_files.py", "workbench_field"),
    ("core/services/workbench/actual_gantt_scope.py", "workbench_field"),
    ("core/services/workbench/preflight_execution.py", "workbench_preflight"),
    ("core/infrastructure/migrations/v25.py", "workbench_mainmigration"),
    ("tests/workbench/execution_ledger_migration_support.py", "workbench_mainmigration"),
    ("tests/workbench/fixtures/schema-v24.sql", "workbench_mainmigration"),
    ("core/infrastructure/migrations/v26.py", "workbench_mainmigration"),
    ("core/infrastructure/workbench_run_schema.py", "workbench_mainmigration"),
    ("tests/workbench/fixtures/schema-v25.sql", "workbench_mainmigration"),
    ("core/services/workbench/run_input_projection_codec.py", "workbench_run_compute"),
    ("core/services/workbench/run_worker_recovery.py", "workbench_run_jobs"),
    ("web/routes/workbench/scheduling_jobs.py", "workbench_run_jobs"),
    ("web/bootstrap/entrypoint.py", "workbench_run_jobs"),
    ("web/bootstrap/factory.py", "workbench_run_jobs"),
    ("web/bootstrap/workbench_run_runtime.py", "workbench_run_jobs"),
    ("web/bootstrap/workbench_run_runtime_lock.py", "workbench_run_jobs"),
    ("web/bootstrap/workbench_run_lifecycle.py", "workbench_run_jobs"),
    ("core/services/workbench/run_worker.py", "workbench_run_jobs"),
    ("core/infrastructure/migrations/v26.py", "workbench_run_jobs"),
    ("core/models/workbench_run_history.py", "workbench_run_jobs"),
    ("core/services/workbench/run_history.py", "workbench_run_jobs"),
    ("core/services/workbench/run_history_storage.py", "workbench_run_jobs"),
    ("core/services/workbench/run_history_projection.py", "workbench_run_jobs"),
    ("web/routes/workbench/run_history.py", "workbench_run_jobs"),
    ("core/infrastructure/workbench_run_schema.py", "workbench_run_jobs"),
    ("core/models/workbench_run_candidate.py", "workbench_run_jobs"),
    ("core/services/workbench/run_candidates.py", "workbench_run_jobs"),
    ("core/services/workbench/run_candidate_storage.py", "workbench_run_jobs"),
    ("core/services/workbench/run_candidate_export.py", "workbench_run_jobs"),
    ("web/routes/workbench/run_candidates.py", "workbench_run_jobs"),
    ("web/routes/workbench/run_candidate_baseline.py", "workbench_run_jobs"),
    ("core/services/workbench/calibration.py", "workbench_calibration"),
    ("core/services/workbench/template_lineage.py", "workbench_batches"),
    ("core/services/workbench/template_lineage_calibration.py", "workbench_calibration"),
    ("core/services/workbench/template_lineage_query.py", "workbench_calibration"),
    ("core/services/workbench/template_lineage.py", "workbench_template_lineage"),
    ("core/services/workbench/template_lineage_calibration.py", "workbench_template_lineage"),
    ("core/services/workbench/template_lineage_query.py", "workbench_template_lineage"),
    ("core/services/scheduler/batch_copy.py", "workbench_template_lineage"),
    ("core/infrastructure/workbench_lineage_lookup_schema.py", "workbench_template_lineage"),
    ("core/infrastructure/migrations/v28.py", "workbench_template_lineage"),
    ("core/infrastructure/workbench_lineage_lookup_schema.py", "workbench_mainmigration"),
    ("core/infrastructure/migrations/v27.py", "workbench_mainmigration"),
    ("core/infrastructure/migrations/v28.py", "workbench_mainmigration"),
    ("core/infrastructure/migrations/v29.py", "workbench_mainmigration"),
    ("core/infrastructure/workbench_calibration_adoption_schema.py", "workbench_mainmigration"),
    ("core/infrastructure/workbench_dashboard_schema.py", "workbench_mainmigration"),
    ("tests/workbench/calibration_dashboard_migration_support.py", "workbench_mainmigration"),
    ("tests/workbench/fixtures/schema-v28.sql", "workbench_mainmigration"),
    ("tests/workbench/fixtures/schema-v26.sql", "workbench_mainmigration"),
    ("tests/workbench/fixtures/schema-v27.sql", "workbench_mainmigration"),
    ("tests/workbench/trial_lineage_migration_support.py", "workbench_mainmigration"),
    ("core/services/workbench/official_plan_persistence.py", "workbench_run_jobs"),
    ("core/services/workbench/official_plan_persistence.py", "workbench_plans"),
    ("core/services/workbench/official_plan_persistence.py", "workbench_trial"),
    ("core/services/workbench/official_plan_persistence.py", "workbench_mainmigration"),
    ("core/models/workbench_trial.py", "workbench_trial"),
    ("core/services/workbench/trial.py", "workbench_trial"),
    ("core/services/workbench/trial_catalog.py", "workbench_trial"),
    ("web/routes/workbench/trial.py", "workbench_trial"),
    ("tests/workbench/trial_support.py", "workbench_trial"),
    ("web/bootstrap/workbench_request_lifecycle.py", "workbench_request_lifecycle"),
    ("web/bootstrap/workbench_request_lifecycle_server.py", "workbench_request_lifecycle"),
    ("web/bootstrap/workbench_request_lifecycle_state.py", "workbench_request_lifecycle"),
    ("web/bootstrap/workbench_request_lifecycle_wsgi.py", "workbench_request_lifecycle"),
    ("web/bootstrap/entrypoint.py", "workbench_request_lifecycle"),
    ("web/bootstrap/factory.py", "workbench_request_lifecycle"),
    ("core/services/system/maintenance/backup_task.py", "workbench_request_lifecycle"),
    ("core/services/workbench/system_restore.py", "workbench_request_lifecycle"),
    ("tests/workbench/test_request_lifecycle_support.py", "workbench_request_lifecycle"),
    ("tests/workbench/test_run_runtime_support.py", "workbench_run_jobs"),
    ("tests/workbench/run_entrypoint_support.py", "workbench_run_jobs"),
    ("tests/workbench/test_run_history_support.py", "workbench_run_jobs"),
    ("tests/workbench/test_run_candidate_support.py", "workbench_run_jobs"),
    ("frontend/workbench/app/ResourceFileContract.js", "workbench_resources"),
    ("frontend/workbench/app/PlanContract.js", "workbench_plans"),
    ("tests/workbench/test_execution_ledger_support.py", "workbench_execution_ledger"),
    ("core/models/workbench_calibration_adoption.py", "workbench_calibration_adoption"),
    ("core/infrastructure/workbench_calibration_adoption_schema.py", "workbench_calibration_adoption"),
    ("core/services/workbench/calibration_adoption.py", "workbench_calibration_adoption"),
    ("core/services/workbench/calibration_adoption_evidence.py", "workbench_calibration_adoption"),
    ("data/repositories/workbench_calibration_adoption_repo.py", "workbench_calibration_adoption"),
    ("web/routes/workbench/calibration_adoption.py", "workbench_calibration_adoption"),
    ("frontend/workbench/app/CalibrationAdoptionAPI.js", "workbench_calibration_adoption"),
    ("frontend/workbench/app/CalibrationAdoptionState.js", "workbench_calibration_adoption"),
    ("frontend/workbench/app/CalibrationAdoptionControls.jsx", "workbench_calibration_adoption"),
    ("frontend/workbench/app/CalibrationAdoptionAction.jsx", "workbench_calibration_adoption"),
    ("tests/workbench/calibration_adoption_support.py", "workbench_calibration_adoption"),
    ("core/models/workbench_trial_adoption.py", "workbench_trial_adoption"),
    ("core/services/workbench/trial_adoption.py", "workbench_trial_adoption"),
    ("core/services/workbench/trial_adoption_input.py", "workbench_trial_adoption"),
    ("core/services/workbench/trial_adoption_storage.py", "workbench_trial_adoption"),
    ("core/services/workbench/trial_adoption_validation.py", "workbench_trial_adoption"),
    ("core/services/workbench/trial_adoption_persistence.py", "workbench_trial_adoption"),
    ("core/services/workbench/trial_adoption_history.py", "workbench_trial_adoption"),
    ("core/services/workbench/trial_adoption_history_evidence.py", "workbench_trial_adoption"),
    ("core/services/workbench/plan_queries.py", "workbench_trial_adoption"),
    ("data/repositories/workbench_trial_adoption_history.py", "workbench_trial_adoption"),
    ("web/routes/workbench/trial_adoption_history.py", "workbench_trial_adoption"),
    ("tests/workbench/trial_adoption_history_support.py", "workbench_trial_adoption"),
    ("data/repositories/workbench_trial_raw_repo.py", "workbench_trial_adoption"),
    ("web/routes/workbench/trial_adoption.py", "workbench_trial_adoption"),
    ("frontend/workbench/app/TrialAdoptionAPI.js", "workbench_trial_adoption"),
    ("frontend/workbench/app/TrialAdoptionState.js", "workbench_trial_adoption"),
    ("frontend/workbench/app/TrialAdoptionControls.jsx", "workbench_trial_adoption"),
    ("frontend/workbench/app/TrialAdoptionAction.jsx", "workbench_trial_adoption"),
    ("core/services/workbench/official_plan_persistence.py", "workbench_trial_adoption"),
    ("tests/workbench/trial_adoption_support.py", "workbench_trial_adoption"),
    ("tests/workbench/trial_adoption_restart_support.py", "workbench_trial_adoption"),
    ("core/models/workbench_dashboard.py", "workbench_dashboard"),
    ("core/models/workbench_dashboard_input.py", "workbench_dashboard"),
    ("core/infrastructure/workbench_dashboard_schema.py", "workbench_dashboard"),
    ("core/services/workbench/dashboard.py", "workbench_dashboard"),
    ("core/services/workbench/dashboard_commands.py", "workbench_dashboard"),
    ("core/services/workbench/dashboard_facts.py", "workbench_dashboard"),
    ("core/services/workbench/dashboard_execution.py", "workbench_dashboard"),
    ("core/services/workbench/dashboard_downtime.py", "workbench_dashboard"),
    ("core/services/workbench/dashboard_projection.py", "workbench_dashboard"),
    ("core/services/workbench/dashboard_catalogs.py", "workbench_dashboard"),
    ("data/repositories/workbench_dashboard_repo.py", "workbench_dashboard"),
    ("data/repositories/workbench_dashboard_source_repo.py", "workbench_dashboard"),
    ("web/routes/workbench/dashboard.py", "workbench_dashboard"),
    ("tests/workbench/dashboard_support.py", "workbench_dashboard"),
    ("frontend/workbench/app/TrialContract.js", "workbench_trial"),
    ("frontend/workbench/app/TrialExport.js", "workbench_trial"),
    ("frontend/workbench/app/TrialControls.jsx", "workbench_trial"),
))
def test_actual_daily_changed_source_selection_hits_owner_without_unknown_fallback(source, group_id):
    assert (ROOT / source).is_file()
    plan = daily._build_impact_plan(daily.ChangedPathSet([source], True, "contract"))
    assert not plan.all_required_groups, plan.reason
    assert group_id in plan.selected_group_ids
    assert set(_groups()[group_id]["target_paths"]) <= set(plan.target_paths)
    assert len(plan.target_paths) == len(set(plan.target_paths))


def test_registry_split_invalidates_common_cache_and_selects_its_own_contract():
    for scope_key in ("config_file_scopes", "tool_file_scopes"):
        assert REGISTRY_PATH in REQUIRED_REGRESSION_COMMON_SCOPES[scope_key]
    plan = daily._build_impact_plan(daily.ChangedPathSet([REGISTRY_PATH], True, "contract"))
    assert plan.all_required_groups and plan.reason.startswith("common quality gate scope changed:")
    assert CONTRACT_PATH in plan.target_paths
    assert set(plan.target_paths) == set(test_registry.iter_required_tests())


def test_registered_scopes_exist_and_test_helpers_are_inputs_only():
    groups = (*WORKBENCH_REQUIRED_REGRESSION_GROUPS, *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    for group in groups:
        for scope in group["input_file_scopes"]:
            assert not Path(scope).is_absolute(), scope
            assert any(ROOT.glob(scope)), (group["group_id"], scope)
    for helper in ("test_execution_ledger_support.py", "test_run_runtime_support.py", "run_entrypoint_support.py",
                   "test_run_history_support.py", "test_run_candidate_support.py", "run_job_widgets_support.py",
                   "test_run_candidate_widgets_support.py"):
        assert not test_registry.required_test_nodeid_matches(PREFIX + helper + "::test_placeholder")


def test_heavy_browser_opt_in_platform_and_build_targets_are_not_must_pass_by_registration():
    supplemental = _targets(WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    assert set(supplemental).isdisjoint(test_registry.iter_required_tests())
    coverage = test_registry.validate_required_regression_group_coverage(
        supplemental, groups=WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    assert coverage["missing"] == coverage["unknown"] == coverage["duplicates"] == []
    groups = {group["group_id"]: group for group in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS}
    assert round1_targets(groups["workbench_run_compute_capacity"]) == [PREFIX + "test_run_compute_capacity.py"]
    assert round1_targets(groups["workbench_run_jobs_capacity"]) == [PREFIX + "test_run_jobs_capacity.py"]
    assert {"AN_RUN_BROWSER", "AZ_RUN_BROWSER", "AY_RUN_MODAL_FOCUS", "WORKBENCH_PROCESS_STAGE_BUILD_READY"} <= set(
        groups["workbench_browser_opt_in"]["env_keys"])
    # Existing perf classification remains the authority, independent of inventory.
    assert "tests/scheduler_graph/test_graph_performance.py" in PERF_FILE_PATTERNS
    assert is_perf_nodeid("tests/scheduler_graph/test_graph_performance.py::test_existing")


def test_completed_dx_browser_keeps_exact_inputs_and_inventory_counts():
    groups = {group["group_id"]: group for group in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS}
    browser = groups["workbench_browser"]
    assert tuple(round1_targets(browser)[-15:]) == tuple(PREFIX + name for name in (
        "test_dashboard_external_handling_widgets.py",
        "test_du_system_restore_browser.py", "test_du_system_restore_contract.py",
        "test_point_frontend.py", "test_point_downstream_browser.py",
        "test_el_material_contracts.py", "test_point_dense_canvas.py",
        "test_piece_main_browser.py", "test_piece_presentation_browser.py",
        "test_ev_piece_fixture_contracts.py",
        "test_plan_scope_caption.py",
        "test_fg_plan_workspace_actions.py",
        "test_piece_downstream_api.py", "test_piece_downstream_browser.py",
        *ROUND1_SUPPLEMENTAL_FILES["workbench_browser"],
    ))
    assert set(DASHBOARD_EXTERNAL_BROWSER_INPUTS) <= set(browser["input_file_scopes"])
    assert len([path for path in test_registry.iter_required_tests() if path not in POST_ROUND1_TARGETS]) == 582
    assert len([path for path in _targets(WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
                if path not in POST_ROUND1_TARGETS]) == 85
    targets = set(_targets((*WORKBENCH_REQUIRED_REGRESSION_GROUPS, *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)))
    assert all(source not in targets for source in DASHBOARD_EXTERNAL_BROWSER_INPUTS
               if not Path(source).name.startswith("test_"))


@pytest.mark.parametrize("source,group_id", DELIVERED_REQUIRED_INPUTS)
def test_delivered_point_piece_material_and_fixture_inputs_select_required_targets(source, group_id):
    assert (ROOT / source).is_file()
    plan = daily._build_impact_plan(daily.ChangedPathSet([source], True, "contract"))
    assert not plan.all_required_groups, plan.reason
    assert group_id in plan.selected_group_ids
    assert set(_groups()[group_id]["target_paths"]) <= set(plan.target_paths)
    assert source not in plan.target_paths


@pytest.mark.parametrize("source,group_id", (
    *((source, "workbench_browser") for source in DELIVERED_BROWSER_INPUTS),
    *((source, "workbench_browser_opt_in") for source in DELIVERED_OPT_IN_INPUTS),
))
def test_delivered_browser_dependencies_are_explicit_inputs_not_pytest_targets(source, group_id):
    group = next(row for row in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS if row["group_id"] == group_id)
    assert (ROOT / source).is_file()
    assert source in group["input_file_scopes"]
    groups = test_registry.iter_required_regression_groups(WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    assert group_id in [row["group_id"] for row in groups
                        if daily._path_matches_any(source, daily._group_scope_patterns(row))]
    assert source not in _targets((*WORKBENCH_REQUIRED_REGRESSION_GROUPS, *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS))


def test_delivered_opt_in_and_node_only_contracts_keep_real_runtime_boundaries():
    group = next(row for row in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS if row["group_id"] == "workbench_browser_opt_in")
    assert group["target_paths"][-len(DELIVERED_OPT_IN_FILES):] == tuple(PREFIX + name for name in DELIVERED_OPT_IN_FILES)
    assert {"ED_RUN_BROWSER", "ED_CANDIDATE", "ED_STATES", "ED_SCOPE", "EL_RUN_BROWSER",
            "EL_CANDIDATE", "EL_STATES", "EI_RUN_BROWSER", "AN_PYTHON", "ER_RUN_BROWSER",
            "SECONDARY_COPY_RUN_BROWSER", "SECONDARY_COPY_BASELINE"} <= set(group["env_keys"])
    switches = ("ED_RUN_BROWSER", "EL_RUN_BROWSER", "EI_RUN_BROWSER", "ER_RUN_BROWSER", "SECONDARY_COPY_RUN_BROWSER")
    for filename, switch in zip(DELIVERED_OPT_IN_FILES, switches):
        tree = ast.parse((ROOT / PREFIX / filename).read_text(encoding="utf-8"))
        decorators = [decorator for node in ast.walk(tree) if isinstance(node, (ast.ClassDef, ast.FunctionDef))
                      for decorator in node.decorator_list]
        expected_decorator = "skipif" if switch == "ER_RUN_BROWSER" else "skipUnless"
        assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == expected_decorator
                   and any(isinstance(value, ast.Constant) and value.value == switch for value in ast.walk(node))
                   for node in decorators)
        assert not test_registry.required_test_nodeid_matches(PREFIX + filename + "::test_contract")
    public = PREFIX + "test_point_public_contract.py"
    assert test_registry.required_test_nodeid_matches(public + "::test_contract")
    el = PREFIX + "test_el_material_contracts.py"
    assert not test_registry.required_test_nodeid_matches(el + "::test_contract")
    tree = ast.parse((ROOT / el).read_text(encoding="utf-8"))
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "runtime_tools"
               for node in ast.walk(tree))


def test_point_adoption_host_tracks_imported_test_helper_without_reassigning_its_owner():
    helper = PREFIX + "test_run_adoption_host.py"
    group = _groups()["workbench_zero_duration"]
    assert group["target_paths"][-1] == PREFIX + "test_point_adoption_host.py"
    assert helper in group["input_file_scopes"] and helper not in group["target_paths"]
    assert helper in _groups()["workbench_run_jobs"]["target_paths"]
    plan = daily._build_impact_plan(daily.ChangedPathSet([helper], True, "contract"))
    assert not plan.all_required_groups, plan.reason
    assert {"workbench_run_jobs", "workbench_zero_duration"} <= set(plan.selected_group_ids)
    assert set(group["target_paths"]) <= set(plan.target_paths)


def test_final_piece_delivery_keeps_real_runtime_and_imported_target_boundaries():
    browser = next(group for group in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
                   if group["group_id"] == "workbench_browser")
    assert {"PIECE_MAIN_ALL_THEMES", "PIECE_MAIN_LONG_IDS", "WORKBENCH_EV_SOURCE_ROOT"} <= set(browser["env_keys"])
    assert "APS_ET_EVIDENCE_ROOT" in _groups()["workbench_piece_adoption"]["env_keys"]
    for filename in ("test_piece_presentation.py", "test_piece_production_connection.py", "test_trial_predecessor_labels.py",
                     "test_preflight_run_status.py"):
        tree = ast.parse((ROOT / PREFIX / filename).read_text(encoding="utf-8"))
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not any("browser" in module or "playwright" in module for module in imports), filename
        assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "runtime_tools"
                       for node in ast.walk(tree)), filename
    for filename in ("test_piece_main_browser.py", "test_piece_presentation_browser.py", "test_ev_piece_fixture_contracts.py",
                     "test_fg_plan_workspace_actions.py", "test_piece_downstream_api.py", "test_piece_downstream_browser.py"):
        tree = ast.parse((ROOT / PREFIX / filename).read_text(encoding="utf-8"))
        assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "runtime_tools"
                   for node in ast.walk(tree)), filename
        assert PREFIX + filename in browser["target_paths"]
    for filename in ("test_piece_presentation.py", "test_piece_chain_end_to_end.py"):
        path = PREFIX + filename
        assert path in browser["input_file_scopes"] and path not in browser["target_paths"]
        assert [group["group_id"] for group in WORKBENCH_REQUIRED_REGRESSION_GROUPS
                if path in group["target_paths"]] == ["workbench_piece_adoption"]


def test_plan_caption_browser_keeps_its_actual_runtime_out_of_required_commands():
    path = PREFIX + "test_plan_scope_caption.py"
    browser = next(group for group in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
                   if group["group_id"] == "workbench_browser")
    assert path in browser["target_paths"]
    assert not test_registry.required_test_nodeid_matches(path + "::test_plan_scope_caption_real_adoption")
    assert {"NODE_PATH", "WORKBENCH_BROWSER", "NODE_OPTIONS"} <= set(browser["env_keys"])
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    literals = {node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert {"plan_scope_caption_probe.cjs", "point_downstream_browser_build_support.cjs"} <= literals
    assert any("chromium109" in value for value in literals)
    assert any("node_modules" in value for value in literals)
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"
               and node.func.attr == "run" for node in ast.walk(tree))
    for command in quality_gate_shared.build_quality_gate_command_plan():
        assert path not in command["args"]


@pytest.mark.parametrize("env_key,group_id,source", (
    ("AN_SCOPE", "workbench_browser_opt_in", "migrated_process_batch_probe.cjs"),
    ("AY_REACT_DEV", "workbench_browser_opt_in", "modal_focus_probe.cjs"),
    ("WORKBENCH_EXPECT_BUILD", "workbench_browser", "resource_detail_layout_probe.cjs"),
    ("SYSTEM_CONFIG_SAVED_REPLAY_OLD_EFFECT", "workbench_browser", "system_config_saved_probe.cjs"),
    ("TRIAL_WIDGET_TARGET_ONLY", "workbench_browser", "trial_widgets_probe.cjs"),
    ("OUTSOURCING_UI_SCHEMA", "workbench_browser", "outsourcing_widgets_support.py"),
    ("FINAL_E_PARENT", "workbench_browser", "final_execution_cases.py"),
    ("FINAL_E_SHARED_BUILD", "workbench_browser", "final_execution_support.py"),
    ("FINAL_E_SHARED_BUILD_ID", "workbench_browser", "final_execution_support.py"),
    ("FINAL_OPERATIONS_BUILD", "workbench_browser", "final_operations_support.py"),
    ("FINAL_PLANNING_BUILD", "workbench_browser", "final_planning_build.cjs"),
    ("FINAL_PLANNING_TEMP_PARENT", "workbench_browser", "test_final_planning_browser.py"),
))
def test_behavior_environment_has_only_its_real_supplemental_owner(env_key, group_id, source):
    groups = test_registry.iter_required_regression_groups(WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    assert [group["group_id"] for group in groups if env_key in group["env_keys"]] == [group_id]
    assert all(env_key not in group["env_keys"] for group in test_registry.iter_required_regression_groups())
    assert env_key in (ROOT / PREFIX / source).read_text(encoding="utf-8")
    owner = next(group for group in groups if group["group_id"] == group_id)
    assert daily._path_matches_any(PREFIX + source, daily._group_scope_patterns(owner))


def test_modal_focus_entry_strips_direct_probe_overrides_before_launch(tmp_path, monkeypatch):
    from tests.workbench import test_modal_focus_browser as modal

    executable = tmp_path / "runtime-placeholder"
    executable.touch()
    monkeypatch.setenv("WORKBENCH_NODE", str(executable))
    monkeypatch.setenv("WORKBENCH_BROWSER", str(executable))
    cleared = ("AY_SMOKE", "AY_BASELINE", "AY_UNSUSPENDED")
    for name in (*cleared, "AY_REACT_DEV"):
        monkeypatch.setenv(name, "fd-probe-value")
    monkeypatch.setattr(modal.tempfile, "mkdtemp", lambda **kwargs: str(tmp_path))
    captured = []

    def intercept(args, **kwargs):
        captured.append(kwargs["env"])
        raise RuntimeError("FD browser launch intercepted")

    monkeypatch.setattr(modal.subprocess, "run", intercept)
    with pytest.raises(RuntimeError, match="FD browser launch intercepted"):
        modal.ModalFocusBrowserTest().test_nested_resource_modal_focus_contract()
    assert len(captured) == 1
    assert all(name not in captured[0] for name in cleared)
    assert captured[0]["AY_REACT_DEV"] == "fd-probe-value"
    groups = test_registry.iter_required_regression_groups(WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    assert all(set(cleared).isdisjoint(group["env_keys"]) for group in groups)


def test_cache_environment_contract_is_required_without_promoting_browser_inventory():
    path = "tests/gate_meta/test_workbench_cache_environment.py"
    helper = "tests/gate_meta/workbench_cache_environment_support.py"
    group = _groups()["workbench_registry"]
    assert group["target_paths"] == [
        CONTRACT_PATH, path, PREFIX + "test_fe04_shared_service_dependency_contract.py",
        *ROUND1_GATE_TESTS, *(PREFIX + name for name in ROUND1_REQUIRED_FILES["workbench_registry"]),
    ]
    assert group["env_keys"] == []
    assert [row["group_id"] for row in WORKBENCH_REQUIRED_REGRESSION_GROUPS
            if path in row["target_paths"]] == ["workbench_registry"]
    assert test_registry.required_test_nodeid_matches(path + "::test_browser_skip_to_run_invalidates_cached_success")
    for source in (path, helper, "tools/long_gate_manifest_environment.py", "tools/long_gate_fingerprint.py"):
        plan = daily._build_impact_plan(daily.ChangedPathSet([source], True, "contract"))
        assert "workbench_registry" in plan.selected_group_ids
        assert path in plan.target_paths and helper not in plan.target_paths
        assert set(_targets(WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)).isdisjoint(plan.target_paths)


def test_shared_service_scanner_contract_tracks_all_real_roots_without_browser_runtime():
    from tools.scan_import_cycles import PROD_ROOTS

    path = PREFIX + "test_fe04_shared_service_dependency_contract.py"
    group = _groups()["workbench_registry"]
    assert path in group["target_paths"] and group["env_keys"] == []
    expected = {root if root == "*.py" else root + "/**/*.py" for root in PROD_ROOTS}
    assert expected | {"tests/**/*.py"} <= set(group["input_file_scopes"])
    for source in ("core/services/process/quota_protection.py", "core/services/scheduler/template_lineage.py",
                   "core/services/scheduler/template_lineage_query.py", "tests/_support/dependency_boundaries.py"):
        assert (ROOT / source).is_file()
        plan = daily._build_impact_plan(daily.ChangedPathSet([source], True, "contract"))
        assert path in plan.target_paths and "workbench_registry" in plan.selected_group_ids


@pytest.mark.parametrize("source", (
    "core/services/scheduler/template_lineage.py", "core/services/scheduler/template_lineage_query.py",
))
def test_canonical_lineage_sources_select_every_existing_facade_owner(source):
    facade = "core/services/workbench/template_lineage*.py"
    canonical = "core/services/scheduler/template_lineage*.py"
    plan = daily._build_impact_plan(daily.ChangedPathSet([source], True, "contract"))
    groups = (*WORKBENCH_REQUIRED_REGRESSION_GROUPS, *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    for group in groups:
        if facade in group["input_file_scopes"]:
            assert canonical in group["input_file_scopes"], group["group_id"]
            if group in WORKBENCH_REQUIRED_REGRESSION_GROUPS:
                assert group["group_id"] in plan.selected_group_ids
                assert set(group["target_paths"]) <= set(plan.target_paths)


def test_completed_du_restore_keeps_explicit_scopes_and_required_browser_boundary():
    system = _groups()["workbench_system"]
    browser = next(group for group in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
                   if group["group_id"] == "workbench_browser")
    expected_tail = ("test_du_system_restore_view.py", *ROUND1_REQUIRED_FILES["workbench_system"])
    assert system["target_paths"][-len(expected_tail):] == [PREFIX + name for name in expected_tail]
    assert set(SYSTEM_RESTORE_VIEW_INPUTS) <= set(system["input_file_scopes"])
    assert set(SYSTEM_RESTORE_BROWSER_INPUTS) <= set(browser["input_file_scopes"])
    assert set(SYSTEM_RESTORE_VIEW_INPUTS).isdisjoint(_targets(WORKBENCH_REQUIRED_REGRESSION_GROUPS))
    for filename in ("test_du_system_restore_view.py", "test_system_restore_entrypoint_support.py",
                     "test_system_restore_entrypoint_process_support.py", "test_system_restore_host_support.py"):
        tree = ast.parse((ROOT / PREFIX / filename).read_text(encoding="utf-8"))
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        assert not any("browser" in name or "playwright" in name for name in imports), filename


@pytest.mark.parametrize("source,group_id", (
    *((source, "workbench_browser") for source in DASHBOARD_EXTERNAL_BROWSER_INPUTS),
    *((source, "workbench_browser") for source in SYSTEM_RESTORE_BROWSER_INPUTS),
    ("frontend/workbench/app/ActualGanttCanvas.jsx", "workbench_browser"),
    ("tests/workbench/test_process_stage_live_browser.py", "workbench_browser_opt_in"),
    ("core/services/workbench/run_compute.py", "workbench_run_compute_capacity"),
    ("core/services/workbench/run_worker.py", "workbench_run_jobs_capacity"),
    ("core/services/system/workbench_overview.py", "workbench_system_platform"),
    ("scripts/workbench/build.py", "workbench_asset_build"),
    ("core/services/workbench/run_history_storage.py", "workbench_run_history_capacity"),
    ("core/services/workbench/run_candidate_export.py", "workbench_run_candidate_capacity"),
    ("frontend/workbench/app/RunJobAPI.js", "workbench_browser"),
    ("frontend/workbench/app/RunJobControls.jsx", "workbench_browser"),
    ("frontend/workbench/app/RunJobPanel.jsx", "workbench_browser"),
    ("frontend/workbench/app/RunCandidateAPI.js", "workbench_browser"),
    ("frontend/workbench/app/RunCandidateControls.jsx", "workbench_browser"),
    ("frontend/workbench/app/RunCandidateGantt.jsx", "workbench_browser"),
    ("frontend/workbench/app/RunCandidateModel.js", "workbench_browser"),
    ("frontend/workbench/app/RunCandidateWorkspace.jsx", "workbench_browser"),
    ("tests/workbench/run_job_widgets_support.py", "workbench_browser"),
    ("tests/workbench/run_job_widgets_probe.cjs", "workbench_browser"),
    ("tests/workbench/test_run_candidate_widgets_support.py", "workbench_browser"),
    ("tests/workbench/test_run_candidate_widgets.cjs", "workbench_browser"),
    ("tests/workbench/run_adoption_widgets_probe.cjs", "workbench_browser"),
    ("tests/workbench/calibration_lineage_ui_probe.cjs", "workbench_browser"),
    ("core/services/workbench/trial.py", "workbench_trial_capacity"),
    ("tests/workbench/trial_support.py", "workbench_trial_capacity"),
    ("core/infrastructure/workbench_lineage_lookup_schema.py", "workbench_lineage_lookup_capacity"),
    ("core/infrastructure/migrations/v28.py", "workbench_lineage_lookup_capacity"),
    ("core/services/workbench/template_lineage_query.py", "workbench_lineage_lookup_capacity"),
    ("core/services/workbench/template_lineage_calibration.py", "workbench_lineage_lookup_capacity"),
    ("tests/workbench/lineage_lookup_budget_support.py", "workbench_lineage_lookup_capacity"),
    ("tests/workbench/fixtures/schema-v27.sql", "workbench_lineage_lookup_capacity"),
    ("tests/workbench/test_plan_persistent_identity.py", "workbench_lineage_lookup_capacity"),
    ("frontend/workbench/app/CalibrationAdoptionAPI.js", "workbench_browser"),
    ("frontend/workbench/app/CalibrationAdoptionState.js", "workbench_browser"),
    ("frontend/workbench/app/CalibrationAdoptionControls.jsx", "workbench_browser"),
    ("frontend/workbench/app/CalibrationAdoptionAction.jsx", "workbench_browser"),
    ("frontend/workbench/app/TrialAdoptionAPI.js", "workbench_browser"),
    ("frontend/workbench/app/TrialAdoptionState.js", "workbench_browser"),
    ("frontend/workbench/app/TrialAdoptionControls.jsx", "workbench_browser"),
    ("frontend/workbench/app/TrialAdoptionAction.jsx", "workbench_browser"),
    ("frontend/workbench/app/TrialContract.js", "workbench_browser"),
    ("frontend/workbench/app/DashboardContract.js", "workbench_browser"),
    ("frontend/workbench/app/DashboardWorkspace.jsx", "workbench_browser"),
    ("frontend/workbench/app/PlanContract.js", "workbench_browser"),
    ("frontend/workbench/app/PlanDetailsUI.jsx", "workbench_browser"),
    ("tests/workbench/dashboard_widgets_support.py", "workbench_browser"),
    ("tests/workbench/dashboard_widgets_probe.cjs", "workbench_browser"),
    ("tests/workbench/test_plan_adoption_baseline_probe.cjs", "workbench_browser"),
    ("tests/workbench/trial_adoption_history_widgets_support.py", "workbench_browser"),
    ("tests/workbench/trial_adoption_history_widgets_probe.cjs", "workbench_browser"),
    ("frontend/workbench/app/TrialExport.js", "workbench_browser"),
    ("frontend/workbench/app/TrialControls.jsx", "workbench_browser"),
    ("tests/workbench/trial_widgets_probe.cjs", "workbench_browser"),
    ("tests/workbench/trial_widgets_support.py", "workbench_browser"),
    ("tests/workbench/calibration_adoption_widgets_probe.cjs", "workbench_browser"),
    ("tests/workbench/calibration_adoption_widgets_support.py", "workbench_browser"),
    ("tests/workbench/trial_adoption_widgets_probe.cjs", "workbench_browser"),
    ("tests/workbench/trial_adoption_widgets_support.py", "workbench_browser"),
    ("tests/workbench/trial_export_widgets_probe.cjs", "workbench_browser"),
    ("tests/workbench/trial_export_widgets_support.py", "workbench_browser"),
    ("core/infrastructure/workbench_dashboard_schema.py", "workbench_dashboard_capacity"),
    ("core/models/workbench_dashboard.py", "workbench_dashboard_capacity"),
    ("core/models/workbench_dashboard_input.py", "workbench_dashboard_capacity"),
    ("core/services/workbench/dashboard.py", "workbench_dashboard_capacity"),
    ("core/services/workbench/dashboard_projection.py", "workbench_dashboard_capacity"),
    ("core/services/workbench/dashboard_facts.py", "workbench_dashboard_capacity"),
    ("core/services/workbench/dashboard_commands.py", "workbench_dashboard_capacity"),
    ("core/services/workbench/dashboard_execution.py", "workbench_dashboard_capacity"),
    ("core/services/workbench/dashboard_downtime.py", "workbench_dashboard_capacity"),
    ("core/services/workbench/dashboard_catalogs.py", "workbench_dashboard_capacity"),
    ("data/repositories/workbench_dashboard_repo.py", "workbench_dashboard_capacity"),
    ("data/repositories/workbench_dashboard_source_repo.py", "workbench_dashboard_capacity"),
    ("web/routes/workbench/dashboard.py", "workbench_dashboard_capacity"),
    ("tests/workbench/dashboard_support.py", "workbench_dashboard_capacity"),
    ("tests/workbench/outsourcing_widgets_support.py", "workbench_browser"),
    ("tests/workbench/outsourcing_widgets_probe.cjs", "workbench_browser"),
))
def test_explicit_supplemental_selection_uses_existing_scope_schema(source, group_id):
    assert (ROOT / source).is_file()
    groups = test_registry.iter_required_regression_groups(WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    selected = [group["group_id"] for group in groups
                if daily._path_matches_any(source, daily._group_scope_patterns(group))]
    assert group_id in selected


def test_registry_and_contract_keep_python38_syntax():
    for relative in (REGISTRY_PATH, CONTRACT_PATH, "tools/test_registry.py", "tools/test_registry_data.py",
                     "tools/test_registry_groups_scheduler.py", "tests/gate_meta/test_long_gate_manifest.py",
                     "tests/workbench/test_plan_delivery.py", "tests/workbench/test_plan_baseline.py"):
        ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative, feature_version=(3, 8))


def test_stop_draining_is_startup_only_serial_and_support_remains_input_only():
    path = "tests/app_runtime/test_runtime_stop_draining.py"
    assert test_registry.iter_startup_regressions()[-2:] == [
        "tests/app_runtime/test_runtime_stop_cli.py", path,
    ]
    assert test_registry.iter_startup_regressions().count(path) == 1
    assert _has_test_definition(ROOT / path)
    assert not test_registry.required_test_nodeid_matches(path + "::test_contract")
    assert classify_nodeid(path + "::test_contract") == "serial"
    assert not is_perf_nodeid(path + "::test_contract")
    assert "tests/app_runtime/test_runtime_stop_draining_support.py" not in test_registry.iter_startup_regressions()


def _dashboard_retention_snapshots():
    def row(*values):
        return tuple((type(value).__name__, value) for value in values)
    before = {
        "WorkbenchTaskRefs": [row(1, "1" * 48, "a" * 48, "b" * 48)],
        "WorkbenchDashboardItems": [row(1, "c" * 48, "actual", None, "1" * 48),
                                    row(2, "d" * 48, "downtime", None, "1" * 48)],
        "Schedule": [row(1, b"raw\x00\xff", None, 1, 1.5, "original")],
        "WorkbenchDashboardStates": [row(1, "unchanged handling")],
        "WorkbenchDashboardHistory": [row(1, "unchanged history")],
        "WorkbenchDashboardDowntimeRefs": [row(1, "unchanged downtime")],
        "LegacyRaw": [row(1, b"raw", None, 1, 1.5, "original")],
    }
    after = deepcopy(before)
    after["WorkbenchTaskRefs"].append(row(2, "2" * 48, "e" * 48, "f" * 48))
    after["WorkbenchDashboardItems"].extend([
        row(3, "e" * 48, "actual", None, "2" * 48), row(4, "f" * 48, "downtime", None, "2" * 48)])
    return before, after


@pytest.fixture(params=("trial", "candidate"))
def retention_assertion(request):
    from tests.workbench.test_run_candidate_adoption_support import assert_retained as candidate_retained
    from tests.workbench.trial_adoption_support import assert_retained as trial_retained
    return {"trial": trial_retained, "candidate": candidate_retained}[request.param]


def test_v29_support_accepts_only_exact_new_task_mapping_pairs(retention_assertion):
    before, after = _dashboard_retention_snapshots()
    retention_assertion(before, deepcopy(before))
    retention_assertion(before, after)
    assert before == _dashboard_retention_snapshots()[0]


def test_dashboard_missing_schema_support_uses_frozen_v28(tmp_path):
    from core.infrastructure.workbench_dashboard_schema import workbench_dashboard_contract_issues
    from tests.workbench.dashboard_widgets_support import connect, missing_dashboard_database
    from tests.workbench.trial_support import snapshot
    with connect(missing_dashboard_database(tmp_path / "missing.sqlite")) as conn:
        before = snapshot(conn)
        assert "WorkbenchTaskRefs" in before and "WorkbenchCommandReceipts" in before
        assert "WorkbenchDashboardItems" not in before
        assert "missing_dashboard_schema:WorkbenchDashboardItems" in workbench_dashboard_contract_issues(conn)
        assert snapshot(conn) == before


@pytest.mark.parametrize("damage", (
    "old_mapping_change", "old_mapping_delete", "missing_pair", "duplicate_category",
    "old_task", "unknown_task", "batch_mapping", "wrong_category", "invalid_ref",
    "extra_column", "duplicate_ref", "old_task_change", "old_task_delete",
))
def test_v29_support_rejects_non_source_mapping_changes(damage, retention_assertion):
    before, after = _dashboard_retention_snapshots()
    items, tasks = after["WorkbenchDashboardItems"], after["WorkbenchTaskRefs"]
    if damage in ("old_mapping_delete", "missing_pair", "old_task_delete"):
        (tasks if damage == "old_task_delete" else items).pop(-1 if damage == "missing_pair" else 0)
    elif damage == "old_task_change":
        tasks[0] = (*tasks[0][:-1], ("str", "0" * 48))
    else:
        index = 0 if damage == "old_mapping_change" else -1
        changed = list(items[index])
        if damage == "extra_column":
            changed.append(("NoneType", None))
        else:
            column, value = {
                "old_mapping_change": (1, ("str", "0" * 48)),
                "duplicate_category": (2, ("str", "actual")),
                "old_task": (4, ("str", "1" * 48)), "unknown_task": (4, ("str", "0" * 48)),
                "batch_mapping": (3, ("str", "a" * 48)), "wrong_category": (2, ("str", "delivery")),
                "invalid_ref": (1, ("str", "not-a-ref")), "duplicate_ref": (1, items[0][1]),
            }[damage]
            changed[column] = value
        items[index] = tuple(changed)
    with pytest.raises(AssertionError):
        retention_assertion(before, after)


@pytest.mark.parametrize("table", (
    "Schedule", "WorkbenchDashboardStates", "WorkbenchDashboardHistory",
    "WorkbenchDashboardDowntimeRefs", "LegacyRaw",
))
@pytest.mark.parametrize("damage", ("delete", "value", "type"))
def test_v29_support_still_rejects_each_old_raw_row_or_type_change(table, damage, retention_assertion):
    before, after = _dashboard_retention_snapshots()
    old = after[table][0]
    after[table] = [] if damage == "delete" else [
        (*old[:-1], ("bytes", old[-1][1]) if damage == "type" else (old[-1][0], "changed"))]
    with pytest.raises(AssertionError):
        retention_assertion(before, after)


FINAL_CAPACITY_STABLE_INPUTS = (
    "tests/workbench/final_capacity_assets.py",
    "tests/workbench/final_capacity_observation.py",
    "tests/workbench/final_capacity_probe.py",
    "tests/workbench/final_capacity_server.py",
    "tests/workbench/final_capacity_sources.py",
    "tests/workbench/final_capacity_support.py",
    "scripts/workbench/verify_final_capacity.py",
    "tests/workbench/live_environment.py",
    "tests/workbench/run_live_server.py",
    "tests/workbench/run_live_server_support.py",
)
FINAL_CAPACITY_GROUPS = ("workbench_run_compute_capacity", "workbench_run_jobs_capacity")


@pytest.mark.parametrize("group_id", FINAL_CAPACITY_GROUPS)
def test_stable_final_capacity_helpers_remain_inputs_not_test_targets(group_id):
    group = next(row for row in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS if row["group_id"] == group_id)
    targets = {path for row in (*test_registry.REQUIRED_REGRESSION_GROUPS,
                               *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS) for path in row["target_paths"]}
    for source in FINAL_CAPACITY_STABLE_INPUTS:
        assert (ROOT / source).is_file()
        assert source in group["input_file_scopes"]
        assert source not in targets
        assert any(daily._path_matches_pattern(source, scope) for scope in group["input_file_scopes"])


@pytest.mark.parametrize("group_id", FINAL_CAPACITY_GROUPS)
@pytest.mark.parametrize("source", FINAL_CAPACITY_STABLE_INPUTS)
def test_stable_final_capacity_helper_change_invalidates_group_files(tmp_path, group_id, source):
    group = next(row for row in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS if row["group_id"] == group_id)
    helper = tmp_path / source
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text("# stable helper before\n", encoding="utf-8")
    before = fingerprint_files(group["input_file_scopes"], str(tmp_path))["content_hash"]
    helper.write_text("# stable helper after\n", encoding="utf-8")
    assert fingerprint_files(group["input_file_scopes"], str(tmp_path))["content_hash"] != before


def test_final_capacity_cli_loading_has_one_supplemental_capacity_owner():
    target = "tests/workbench/test_final_capacity_cli_loading.py"
    groups = (*test_registry.REQUIRED_REGRESSION_GROUPS, *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    assert [row["group_id"] for row in groups if target in row["target_paths"]] == ["workbench_run_compute_capacity"]
    owner = next(row for row in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
                 if row["group_id"] == "workbench_run_compute_capacity")
    assert owner["target_paths"].count(target) == 1
    assert (ROOT / target).is_file() and _has_test_definition(ROOT / target)
    assert not quality_gate_shared.quality_gate_required_test_nodeid_matches(target + "::test_contract")
    assert "scripts/workbench/verify_final_capacity.py" in owner["input_file_scopes"]
    assert "tests/workbench/final_capacity_probe.py" in owner["input_file_scopes"]
    plan = daily._build_impact_plan(daily.ChangedPathSet([target], True, "final-capacity-cli"))
    assert not plan.all_required_groups and target not in plan.target_paths


FINAL_FOUNDATION_FILES = (
    "test_final_foundation_navigation.py",
    "test_final_foundation_live.py",
    "test_final_navigation_host.py",
    "test_final_navigation_boot.py",
    "test_final_legacy_navigation.py",
)
FINAL_FOUNDATION_INPUTS = (
    "tests/workbench/final_foundation_navigation.cjs",
    "tests/workbench/final_foundation_live.py",
    "tests/workbench/final_foundation_live_support.py",
    "tests/workbench/final_foundation_host.py",
    "tests/workbench/final_foundation_live.cjs",
    "tests/workbench/final_foundation_live_probe.cjs",
    "tests/workbench/final_foundation_live_actions.cjs",
    "tests/workbench/final_foundation_live_faults.cjs",
    "tests/workbench/final_navigation_support.py",
    "tests/workbench/final_legacy_navigation_support.py",
    "tests/workbench/live_environment.py",
    "tests/workbench/run_live_server.py",
    "tests/workbench/run_live_server_support.py",
    "tests/workbench/plan_read_support.py",
    "tests/workbench/plan_catalog_support.py",
    "frontend/workbench/app/WorkbenchNavigation.js",
    "frontend/workbench/app/main.jsx",
    "frontend/workbench/app/theme.js",
    "web/routes/workbench/navigation_boot.py",
    "web/routes/workbench/pages.py",
    "web/routes/workbench/legacy_navigation.py",
    "web/routes/workbench/legacy_navigation_plan.py",
    "web/routes/workbench/legacy_page_contract.py",
    "scripts/workbench/build-order.json",
    "scripts/workbench/build.py",
    "scripts/workbench/compile.cjs",
)


@pytest.mark.parametrize("filename", FINAL_FOUNDATION_FILES)
def test_final_foundation_targets_have_one_supplemental_owner(filename):
    target = PREFIX + filename
    groups = (*test_registry.REQUIRED_REGRESSION_GROUPS, *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    assert [row["group_id"] for row in groups if target in row["target_paths"]] == ["workbench_browser"]
    owner = next(row for row in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
                 if row["group_id"] == "workbench_browser")
    assert owner["target_paths"].count(target) == 1
    assert (ROOT / target).is_file() and _has_test_definition(ROOT / target)
    assert target in POST_ROUND1_TARGETS
    assert not quality_gate_shared.quality_gate_required_test_nodeid_matches(target + "::test_contract")
    plan = daily._build_impact_plan(daily.ChangedPathSet([target], True, "final-foundation"))
    assert not plan.all_required_groups and target not in plan.target_paths
    assert "workbench_browser" not in plan.selected_group_ids


@pytest.mark.parametrize("source", FINAL_FOUNDATION_INPUTS)
def test_final_foundation_helpers_and_sources_invalidate_owner_without_becoming_targets(tmp_path, source):
    owner = next(row for row in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
                 if row["group_id"] == "workbench_browser")
    groups = (*test_registry.REQUIRED_REGRESSION_GROUPS, *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    assert (ROOT / source).is_file()
    assert all(source not in row["target_paths"] for row in groups)
    assert any(daily._path_matches_pattern(source, scope) for scope in owner["input_file_scopes"])
    file = tmp_path / source
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("before\n", encoding="utf-8")
    before = fingerprint_files(owner["input_file_scopes"], str(tmp_path))["content_hash"]
    file.write_text("after\n", encoding="utf-8")
    assert fingerprint_files(owner["input_file_scopes"], str(tmp_path))["content_hash"] != before


def test_final_foundation_historical_filter_never_hides_unreviewed_tests():
    retained = (PREFIX + "test_final_unreviewed_contract.py", PREFIX + "test_transport.py")
    targets = [retained[0], *sorted(POST_ROUND1_TARGETS), retained[1], retained[0]]
    assert round1_targets({"target_paths": targets}) == [retained[0], retained[1], retained[0]]


@pytest.mark.parametrize("owner_id,filename", (
    *((owner_id, name) for owner_id, names in FINAL_INTEGRATION_SUPPLEMENTAL_FILES.items() for name in names),
))
def test_final_integration_targets_keep_one_explicit_supplemental_owner(owner_id, filename):
    target = PREFIX + filename
    groups = (*test_registry.REQUIRED_REGRESSION_GROUPS, *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)
    assert [row["group_id"] for row in groups if target in row["target_paths"]] == [owner_id]
    owner = next(row for row in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS if row["group_id"] == owner_id)
    assert owner["target_paths"].count(target) == 1
    assert (ROOT / target).is_file() and _has_test_definition(ROOT / target)
    assert target in POST_ROUND1_TARGETS
    assert not quality_gate_shared.quality_gate_required_test_nodeid_matches(target + "::test_contract")
    plan = daily._build_impact_plan(daily.ChangedPathSet([target], True, "final-integration"))
    assert not plan.all_required_groups and target not in plan.target_paths
    assert owner_id not in plan.selected_group_ids


@pytest.mark.parametrize("source", (
    ".codestable/roadmap/workbench-prototype-migration/workbench-capabilities.json",
    ".codestable/roadmap/workbench-prototype-migration/acceptance-master/actions.json",
    ".codestable/roadmap/workbench-prototype-migration/acceptance-planning/action-inventory.json",
))
def test_final_integration_action_manifests_invalidate_browser_owner(tmp_path, source):
    owner = next(row for row in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
                 if row["group_id"] == "workbench_browser")
    assert (ROOT / source).is_file() and source in owner["input_file_scopes"]
    assert all(source not in row["target_paths"] for row in
               (*test_registry.REQUIRED_REGRESSION_GROUPS, *WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS))
    path = tmp_path / source
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"action": "before"}\n', encoding="utf-8")
    before = fingerprint_files(owner["input_file_scopes"], str(tmp_path))["content_hash"]
    path.write_text('{"action": "after"}\n', encoding="utf-8")
    assert fingerprint_files(owner["input_file_scopes"], str(tmp_path))["content_hash"] != before


@pytest.mark.parametrize("group_id", FINAL_CAPACITY_GROUPS)
def test_final_capacity_owner_covers_every_actual_frozen_product_input(group_id):
    from tests.workbench.final_capacity_sources import product_paths

    owner = next(row for row in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS if row["group_id"] == group_id)
    missing = [str(path.relative_to(ROOT)) for path in product_paths()
               if not any(daily._path_matches_pattern(str(path.relative_to(ROOT)), scope)
                          for scope in owner["input_file_scopes"])]
    assert not missing, missing
