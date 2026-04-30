from __future__ import annotations

import hashlib
import json
import os
import subprocess
from typing import Any, Dict, List, Optional, Sequence

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

QUALITY_GATE_SELFTEST_PATH = "tests/test_run_quality_gate.py"

QUALITY_GATE_STARTUP_REGRESSION_ARGS = (
    "tests/regression_runtime_probe_resolution.py",
    "tests/test_win7_launcher_runtime_paths.py",
    "tests/regression_runtime_contract_launcher.py",
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
    "tests/regression_schedule_orchestrator_contract.py",
    "tests/test_schedule_summary_observability.py",
    "tests/regression_sp06_no_duplicate_defs.py",
    "tests/test_schedule_params_direct_call_contract.py",
    "tests/regression_config_field_metadata_shape.py",
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
    "tests/regression_reports_page_version_default_latest.py",
    "tests/regression_reports_export_version_default_latest.py",
    "tests/regression_week_plan_filename_uses_normalized_version.py",
    "tests/regression_gantt_calendar_load_failed_degraded.py",
    "tests/regression_gantt_bad_time_rows_surface_degraded.py",
    "tests/regression_gantt_contract_snapshot.py",
    "tests/regression_gantt_critical_chain_unavailable.py",
    "tests/regression_quality_gate_scan_contract.py",
    "tests/regression_request_services_contract.py",
    "tests/regression_request_services_lazy_construction.py",
    "tests/regression_request_services_failure_propagation.py",
    "tests/regression_factory_request_lifecycle_observability.py",
    "tests/regression_optimizer_seed_results_contract.py",
    "tests/regression_optimizer_seed_boundary_contract.py",
    "tests/regression_optimizer_runtime_seam_contract.py",
    "tests/regression_optimizer_outcome_type_contract.py",
    "tests/regression_optimizer_public_summary_projection_contract.py",
    "tests/regression_schedule_input_collector_contract.py",
    "tests/regression_schedule_params_read_failure_visible.py",
    "tests/regression_schedule_service_strict_snapshot_guard.py",
    "tests/regression_schedule_service_facade_delegation.py",
    "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py",
    "tests/regression_schedule_persistence_reschedulable_contract.py",
    "tests/regression_schedule_optimizer_cfg_snapshot_contract.py",
    "tests/regression_schedule_summary_cfg_snapshot_contract.py",
    "tests/regression_schedule_summary_algo_warnings_union.py",
    "tests/regression_schedule_summary_v11_contract.py",
    "tests/regression_schedule_summary_size_guard_large_lists.py",
    "tests/regression_schedule_summary_merge_context_degraded_code.py",
    "tests/regression_schedule_summary_input_fallback_contract.py",
    "tests/regression_scheduler_run_surfaces_resource_pool_warning.py",
    "tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py",
    "tests/regression_error_field_label_source.py",
    "tests/test_run_full_selftest_report_metadata.py",
    "tests/test_ui_mode.py",
    "tests/regression_safe_next_url_hardening.py",
    "tests/regression_safe_next_url_observability.py",
    "tests/test_holiday_default_efficiency_read_guard.py",
    "tests/regression_error_boundary_contract.py",
    "tests/regression_gantt_critical_outline_sync.py",
)

QUALITY_GATE_REQUIRED_TESTS = (QUALITY_GATE_SELFTEST_PATH, *QUALITY_GATE_GUARD_TESTS)


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
    "build_test_path_status",
    "hash_required_tests_registry",
    "hash_test_registry",
    "iter_non_regression_guard_tests",
    "iter_required_tests",
    "iter_startup_regressions",
    "normalize_test_paths",
    "required_test_nodeid_matches",
    "stable_registry_hash",
]
