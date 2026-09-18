"""Browser acceptance lane: test files that need the real Chromium 109 / Node probe runtime.

Rule (how this list was derived on 2026-09-17 and how ``--check`` recomputes it):

* a test file belongs here when the file itself, or a ``tests.*`` support module it
  imports (two levels deep), references ``WORKBENCH_BROWSER`` or calls
  ``runtime_tools(`` -- both mean "start Node and the Chromium 109 build";
* files registered as gate-required (``tools.test_registry.iter_required_tests``)
  never belong here, so the required-regression proof of the full gate stays whole.

``tools.full_test_debt_shards.is_perf_nodeid`` treats every file below as ``perf``:
the daily gate and the formal full gate deselect them with ``-m "not perf"``, and
``scripts/run_browser_test_lane.py`` runs them on purpose with the browser runtime.

Refresh: ``python -m tools.browser_lane_files --check`` prints files that the rule
would add or drop; edit the tuple by hand after reviewing the diff.
"""
from __future__ import annotations

import os
import re
import sys
from typing import List, Optional, Sequence, Set, Tuple

BROWSER_LANE_FILES: Tuple[str, ...] = (
    "tests/web_pages/test_aps_workbench_first_round_flow_contract.py",
    "tests/web_pages/test_frontend_ui_language_polish.py",
    "tests/web_pages/test_lazy_select_orphan_option.py",
    "tests/workbench/test_actual_gantt_ui.py",
    "tests/workbench/test_asset_browser_globals.py",
    "tests/workbench/test_assets_build.py",
    "tests/workbench/test_az_contrast_modal_scroll.py",
    "tests/workbench/test_batch_dashboard_return_context.py",
    "tests/workbench/test_batch_transport.py",
    "tests/workbench/test_batch_widgets.py",
    "tests/workbench/test_be_preflight_actual_surfaces.py",
    "tests/workbench/test_calibration_adoption_widgets.py",
    "tests/workbench/test_calibration_lineage_ui.py",
    "tests/workbench/test_calibration_widgets.py",
    "tests/workbench/test_dashboard_external_handling_widgets.py",
    "tests/workbench/test_dashboard_ui_refinement.py",
    "tests/workbench/test_dashboard_widgets.py",
    "tests/workbench/test_dirty_guard_widgets.py",
    "tests/workbench/test_du_system_restore_browser.py",
    "tests/workbench/test_du_system_restore_contract.py",
    "tests/workbench/test_ed_material_process_browser.py",
    "tests/workbench/test_el_material_browser.py",
    "tests/workbench/test_el_material_contracts.py",
    "tests/workbench/test_ev_piece_fixture_contracts.py",
    "tests/workbench/test_fg_plan_workspace_actions.py",
    "tests/workbench/test_field_report_void_browser.py",
    "tests/workbench/test_field_scope_navigation_browser.py",
    "tests/workbench/test_final_execution_analytics.py",
    "tests/workbench/test_final_execution_backend.py",
    "tests/workbench/test_final_execution_browser.py",
    "tests/workbench/test_final_execution_calibration.py",
    "tests/workbench/test_final_execution_chain.py",
    "tests/workbench/test_final_execution_controls.py",
    "tests/workbench/test_final_execution_history.py",
    "tests/workbench/test_final_execution_read_contract.py",
    "tests/workbench/test_final_execution_read_reentry.py",
    "tests/workbench/test_final_execution_rejections.py",
    "tests/workbench/test_final_execution_report_contract.py",
    "tests/workbench/test_final_execution_report_reentry.py",
    "tests/workbench/test_final_execution_reports.py",
    "tests/workbench/test_final_execution_resources.py",
    "tests/workbench/test_final_execution_search.py",
    "tests/workbench/test_final_foundation_live.py",
    "tests/workbench/test_final_master_context.py",
    "tests/workbench/test_final_operations_browser.py",
    "tests/workbench/test_final_operations_context_contract.py",
    "tests/workbench/test_final_operations_download.py",
    "tests/workbench/test_final_operations_download_contract.py",
    "tests/workbench/test_final_operations_edges.py",
    "tests/workbench/test_final_operations_host.py",
    "tests/workbench/test_final_operations_inflight.py",
    "tests/workbench/test_final_operations_navigation.py",
    "tests/workbench/test_final_operations_projection_api.py",
    "tests/workbench/test_final_operations_read_controls.py",
    "tests/workbench/test_final_operations_restore.py",
    "tests/workbench/test_final_operations_system_recovery.py",
    "tests/workbench/test_final_operations_system_restart.py",
    "tests/workbench/test_final_planning_browser.py",
    "tests/workbench/test_final_planning_candidate_source.py",
    "tests/workbench/test_final_planning_delivery.py",
    "tests/workbench/test_final_planning_gantt.py",
    "tests/workbench/test_final_planning_l5_contract.py",
    "tests/workbench/test_final_planning_preflight_return.py",
    "tests/workbench/test_final_planning_readonly.py",
    "tests/workbench/test_final_planning_required.py",
    "tests/workbench/test_final_planning_task_origin.py",
    "tests/workbench/test_live_browser.py",
    "tests/workbench/test_master_overview_browser.py",
    "tests/workbench/test_merged_cycle_ui.py",
    "tests/workbench/test_migrated_process_batch_browser.py",
    "tests/workbench/test_modal_focus_browser.py",
    "tests/workbench/test_operator_machine_permissions_widgets.py",
    "tests/workbench/test_outsourcing_widgets.py",
    "tests/workbench/test_piece_downstream_api.py",
    "tests/workbench/test_piece_downstream_browser.py",
    "tests/workbench/test_piece_main_browser.py",
    "tests/workbench/test_piece_presentation_browser.py",
    "tests/workbench/test_plan_adoption_baseline_browser.py",
    "tests/workbench/test_plan_scope_caption.py",
    "tests/workbench/test_plan_ui.py",
    "tests/workbench/test_point_dense_canvas.py",
    "tests/workbench/test_point_downstream_browser.py",
    "tests/workbench/test_point_frontend.py",
    "tests/workbench/test_preflight_browser.py",
    "tests/workbench/test_process_actions_widgets.py",
    "tests/workbench/test_process_detail_files.py",
    "tests/workbench/test_process_live_browser.py",
    "tests/workbench/test_process_quota_widgets.py",
    "tests/workbench/test_process_readiness_browser.py",
    "tests/workbench/test_process_stage_live_browser.py",
    "tests/workbench/test_process_stage_widgets.py",
    "tests/workbench/test_process_widgets.py",
    "tests/workbench/test_report_ledger_widgets.py",
    "tests/workbench/test_report_widgets.py",
    "tests/workbench/test_reports_review_browser.py",
    "tests/workbench/test_resource_context_refresh.py",
    "tests/workbench/test_resource_detail_layout.py",
    "tests/workbench/test_resource_details_widgets.py",
    "tests/workbench/test_resource_file_widgets.py",
    "tests/workbench/test_resource_live_browser.py",
    "tests/workbench/test_resource_navigation_context.py",
    "tests/workbench/test_resource_readiness.py",
    "tests/workbench/test_resource_table_header_widgets.py",
    "tests/workbench/test_round1_field_piece_files_browser.py",
    "tests/workbench/test_run_adoption_widgets.py",
    "tests/workbench/test_run_baseline_widgets.py",
    "tests/workbench/test_run_candidate_widgets.py",
    "tests/workbench/test_run_history_widgets.py",
    "tests/workbench/test_run_job_widgets.py",
    "tests/workbench/test_run_presentation.py",
    "tests/workbench/test_secondary_copy_contrast.py",
    "tests/workbench/test_shared_controls_widgets.py",
    "tests/workbench/test_system_config_saved.py",
    "tests/workbench/test_system_maintenance_widgets.py",
    "tests/workbench/test_trial_adoption_history_widgets.py",
    "tests/workbench/test_trial_adoption_widgets.py",
    "tests/workbench/test_trial_export_widgets.py",
    "tests/workbench/test_trial_widgets.py",
    "tests/workbench/test_ui_navigation_guard.py",
    "tests/workbench/test_ui_refinement_geometry.py",
    "tests/workbench/test_ui_refinement_reports_review.py",
    "tests/workbench/test_wbui_actual_keyboard.py",
    "tests/workbench/test_wbui_plan_first_screen.py",
    "tests/workbench/test_wbui_plan_gantt_models.py",
    "tests/workbench/test_workbench_plain_language.py",
    "tests/workbench/test_workbench_visual_controls.py",
    "tests/workbench/test_workspace_primitive_styles.py",
)

_LANE_SET = frozenset(BROWSER_LANE_FILES)
_BROWSER_RUNTIME_PATTERN = re.compile(r"WORKBENCH_BROWSER|runtime_tools\(")
_TEST_IMPORT_PATTERN = re.compile(r"^\s*from\s+(tests\.[\w.]+)\s+import|^\s*import\s+(tests\.[\w.]+)", re.M)


def is_browser_lane_file(path: str) -> bool:
    return str(path or "").replace("\\", "/") in _LANE_SET


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def _module_file(module: str) -> str:
    base = module.replace(".", "/")
    if os.path.isfile(base + ".py"):
        return base + ".py"
    package = base + "/__init__.py"
    return package if os.path.isfile(package) else ""


def _needs_browser_runtime(path: str, depth: int = 0, seen: Optional[Set[str]] = None) -> bool:
    if seen is None:
        seen = set()
    if path in seen or depth > 2:
        return False
    seen.add(path)
    text = _read(path)
    if _BROWSER_RUNTIME_PATTERN.search(text):
        return True
    for match in _TEST_IMPORT_PATTERN.finditer(text):
        target = _module_file(match.group(1) or match.group(2))
        if target and _needs_browser_runtime(target, depth + 1, seen):
            return True
    return False


def iter_test_files(root: str = "tests") -> List[str]:
    found = []  # type: List[str]
    for directory, _dirs, files in os.walk(root):
        for name in files:
            if name.startswith("test_") and name.endswith(".py"):
                found.append(os.path.join(directory, name).replace("\\", "/"))
    return sorted(found)


def compute_browser_lane(required_paths: Sequence[str]) -> List[str]:
    required = {str(path).replace("\\", "/") for path in required_paths}
    return [path for path in iter_test_files() if path not in required and _needs_browser_runtime(path)]


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args not in (["--check"], ["--print"]):
        print("usage: python -m tools.browser_lane_files --check | --print", file=sys.stderr)
        return 2
    from tools.test_registry import iter_required_tests

    expected = compute_browser_lane(iter_required_tests())
    if args == ["--print"]:
        print("\n".join(expected))
        return 0
    current = set(BROWSER_LANE_FILES)
    missing_on_disk = sorted(path for path in current if not os.path.isfile(path))
    to_add = sorted(set(expected) - current)
    to_drop = sorted(current - set(expected))
    for label, rows in (("add", to_add), ("drop", to_drop), ("missing file", missing_on_disk)):
        for row in rows:
            print(label + ": " + row)
    if to_add or to_drop or missing_on_disk:
        print(f"browser lane drift: {len(to_add)} to add, {len(to_drop)} to drop, {len(missing_on_disk)} missing")
        return 1
    print(f"browser lane up to date: {len(current)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
