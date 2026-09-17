"""回归测试：tools.long_gate_manifest 从真实质量门命令计划构建 long-gate manifest 的契约——entry 顺序/哈希与 build_quality_gate_command_plan 一致、含 pytest_collect_all/full_test_debt/ruff/pyright/required_regressions 等条目并带 fingerprint 槽与共享 schema 版本，required/startup 参数取自动态计划且 fingerprint 跟踪 scope 并集，required 分组不进入正式 manifest 契约，version-probe 条目不可复用，并校验 reuse_allowed/cache_status/input_file_scopes/env_keys 及本地 receipt 解析与异常容错。"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from tests.gate_meta.workbench_round1_registry_support import (
    POST_ROUND1_TARGETS,
    UI_REQUIRED_TARGETS,
    assert_reviewed_algorithm_registration,
)
from tools import long_gate_fingerprint as fingerprint_mod
from tools import long_gate_manifest as manifest_mod
from tools import quality_gate_shared
from tools.long_gate_fingerprint import fingerprint_entry
from tools.long_gate_schema import (
    LONG_GATE_CACHE_SCHEMA_VERSION,
    LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
    LONG_GATE_MANIFEST_SCHEMA_VERSION,
)
from tools.test_registry import (
    iter_required_regression_groups,
    iter_required_tests,
    iter_startup_regressions,
    validate_required_regression_group_coverage,
)
from tools.test_registry_algorithm_efficiency import ALGORITHM_EFFICIENCY_REQUIRED_TESTS
from tools.test_registry_groups_workbench import WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS


def _entry_by_id(manifest, entry_id):
    entries = list(manifest["entries"])
    for entry in entries:
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError(f"missing entry_id: {entry_id}")


def test_build_long_gate_manifest_uses_real_quality_gate_plan(monkeypatch, tmp_path):
    real_plan_builder = quality_gate_shared.build_quality_gate_command_plan
    real_plan = real_plan_builder()
    calls = []

    def spy_plan():
        calls.append("called")
        return real_plan_builder()

    monkeypatch.setattr(manifest_mod.quality_gate_shared, "build_quality_gate_command_plan", spy_plan)

    manifest = manifest_mod.build_long_gate_manifest(str(tmp_path))

    assert calls == ["called"]
    assert [entry["display"] for entry in manifest["entries"]] == [command["display"] for command in real_plan]
    assert manifest["quality_gate_plan_hash"] == quality_gate_shared.hash_quality_gate_commands(real_plan)


def test_manifest_contains_current_quality_gate_long_entries():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    entry_ids = {entry["entry_id"] for entry in manifest["entries"]}

    assert "pytest_collect_all" in entry_ids
    assert "full_test_debt" in entry_ids
    assert "ruff_check_full" in entry_ids
    assert "pyright_gate_full" in entry_ids
    assert "pyright_tools_full" in entry_ids
    assert "architecture_fitness" in entry_ids
    assert "required_regressions" in entry_ids
    assert "debt_ledger_sync" in entry_ids
    assert "startup_runtime_regressions" in entry_ids
    assert "quickref_vs_routes" in entry_ids
    assert "import_cycles_production" in entry_ids
    assert "import_cycles_with_tests" in entry_ids


def test_manifest_entry_keeps_current_and_previous_fingerprint_slots():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    collect_entry = _entry_by_id(manifest, "pytest_collect_all")

    assert "fingerprint" in collect_entry
    assert "previous_success" in collect_entry
    assert "last_success_fingerprint" in collect_entry
    assert collect_entry["fingerprint"] is None
    assert collect_entry["previous_success"] is None
    assert collect_entry["last_success_fingerprint"] is None


def test_manifest_uses_shared_long_gate_schema_versions():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    collect_entry = _entry_by_id(manifest, "pytest_collect_all")
    planned_entry = _entry_by_id(manifest, "full_test_debt")

    assert manifest["schema_version"] == LONG_GATE_MANIFEST_SCHEMA_VERSION
    assert collect_entry["schema_version"] == LONG_GATE_MANIFEST_SCHEMA_VERSION
    assert collect_entry["cache_schema_version"] == LONG_GATE_CACHE_SCHEMA_VERSION
    assert collect_entry["fingerprint_schema_version"] == LONG_GATE_FINGERPRINT_SCHEMA_VERSION
    assert planned_entry["schema_version"] == LONG_GATE_MANIFEST_SCHEMA_VERSION
    assert planned_entry["cache_schema_version"] == LONG_GATE_CACHE_SCHEMA_VERSION
    assert planned_entry["fingerprint_schema_version"] == LONG_GATE_FINGERPRINT_SCHEMA_VERSION


def test_required_and_startup_regression_args_come_from_dynamic_plan():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)

    required_entry = _entry_by_id(manifest, "required_regressions")
    startup_entry = _entry_by_id(manifest, "startup_runtime_regressions")

    assert required_entry["args"] == ["python", "tools/verify_required_regressions_from_full_test_debt.py"]
    for required_path in quality_gate_shared.iter_quality_gate_required_tests():
        assert required_path in required_entry["input_file_scopes"]
    assert startup_entry["args"][4:] == iter_startup_regressions()
    assert startup_entry["args"][-2:] == [
        "tests/app_runtime/test_runtime_stop_cli.py", "tests/app_runtime/test_runtime_stop_draining.py",
    ]
    assert "tests/app_runtime/test_runtime_stop_draining.py" in startup_entry["input_file_scopes"]
    assert "tests/app_runtime/test_runtime_stop_draining.py" not in iter_required_tests()


def test_full_test_debt_manifest_tracks_runtime_and_shard_inputs():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)

    full_debt_entry = _entry_by_id(manifest, "full_test_debt")
    required_entry = _entry_by_id(manifest, "required_regressions")

    assert "tools/full_test_debt_shards.py" in full_debt_entry["config_file_scopes"]
    for env_key in (
        "chrome_executable_resolution",
        "chrome_version",
        "chrome_executable_identity",
        "chrome_headless_preflight",
    ):
        assert env_key in full_debt_entry["env_keys"]
    assert "evidence/QualityGate/current_full_test_debt.json" in required_entry["input_file_scopes"]


def test_required_groups_cover_required_registry():
    assert_reviewed_algorithm_registration()
    required = iter_required_tests()
    groups = iter_required_regression_groups()
    coverage = validate_required_regression_group_coverage(required)

    assert coverage["missing"] == []
    assert coverage["duplicates"] == []
    assert coverage["unknown"] == []
    assert coverage["required_target_count"] == len(required)
    assert coverage["group_target_count"] == len(required)
    # Preserve the historical 582 and explicitly account for reviewed additions.
    # Registration coverage is not execution proof.
    assert coverage["group_count"] == 34
    final_required = (
        ("tests/gate_meta/test_scheduler_lazy_exports_final.py", "scheduler_run_core"),
        ("tests/workbench/test_final_planning_analysis.py", "workbench_run_jobs"),
        ("tests/workbench/test_final_planning_analysis_history.py", "workbench_run_jobs"),
        ("tests/workbench/test_final_planning_analysis_contract.py", "workbench_run_jobs"),
    )
    ui_required = tuple((path, "workbench_ui_refinement") for path in UI_REQUIRED_TARGETS)
    # 2026-09-16 manual remediation batch: reviewed additions, each owned by the workbench group it exercises.
    manual_remediation_required = (
        ("tests/workbench/test_file_reference_roundtrip.py", "workbench_resources"),
        ("tests/workbench/test_operator_machine_permissions.py", "workbench_resources"),
        ("tests/workbench/test_resource_feedback.py", "workbench_resources"),
        ("tests/workbench/test_batch_template_updates.py", "workbench_batches"),
        ("tests/workbench/test_resource_utilization_shared.py", "workbench_reports"),
        ("tests/workbench/test_report_void_projections.py", "workbench_reports"),
        ("tests/workbench/test_execution_report_void.py", "workbench_execution_ledger"),
        ("tests/workbench/test_field_report_void_api.py", "workbench_field"),
        ("tests/workbench/test_manual_remediation_schema_migration.py", "workbench_mainmigration"),
        ("tests/workbench/test_run_data_context.py", "workbench_run_jobs"),
        ("tests/workbench/test_trial_source_presentation.py", "workbench_trial"),
        ("tests/workbench/test_trial_adoption_execution_anchors.py", "workbench_trial_adoption"),
        ("tests/workbench/test_outsourcing_legacy_source.py", "workbench_outsourcing"),
    )
    reviewed_post_round1 = (
        ("tests/gate_meta/test_quality_gate_output_normalization.py", "quality_gate"),
        *final_required, *manual_remediation_required, *ui_required,
    )
    algorithm_required = dict.fromkeys(ALGORITHM_EFFICIENCY_REQUIRED_TESTS, "scheduler_run_core")
    algorithm_required.update({
        "tests/workbench/test_run_snapshot_reuse.py": "workbench_run_compute",
        "tests/gate_meta/test_quality_gate_output_normalization.py": "quality_gate",
    })
    # The registry yields targets in group order, so compare membership; owners are asserted per path below.
    assert sorted(path for path in required if path in POST_ROUND1_TARGETS) == sorted(path for path, _owner in reviewed_post_round1)
    assert set(algorithm_required).issubset(required)
    # Count structure, not a frozen total: every required path is owned exactly once across the partitions.
    base_required = [path for path in required if path not in POST_ROUND1_TARGETS and path not in algorithm_required]
    assert coverage["required_target_count"] == (len(base_required) + len(final_required) + len(algorithm_required)
                                                 + len(ui_required) + len(manual_remediation_required))
    for path, owner in (*final_required, *algorithm_required.items(), *ui_required, *manual_remediation_required):
        assert [group["group_id"] for group in groups if path in group["target_paths"]] == [owner]
    domain_ledger = "tests/workbench/test_final_master_domain_ledger.py"
    assert domain_ledger not in required
    assert [group["group_id"] for group in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
            for path in group["target_paths"] if path == domain_ledger] == ["workbench_browser"]
    assert [group["group_id"] for group in groups][-10:-1] == [
        "workbench_trial", "workbench_template_lineage", "workbench_request_lifecycle",
        "workbench_calibration_adoption", "workbench_trial_adoption", "workbench_dashboard",
        "workbench_outsourcing", "workbench_zero_duration", "workbench_piece_adoption",
    ]
    assert groups[-1]["group_id"] == "workbench_ui_refinement"
    assert coverage["required_registry_hash"]
    assert coverage["group_registry_hash"]


def test_required_group_registry_reports_missing_target():
    required = iter_required_tests()
    groups = [
        {
            "group_id": "almost_all",
            "target_paths": required[1:],
        }
    ]

    coverage = validate_required_regression_group_coverage(required, groups)

    assert coverage["missing"] == [required[0]]


def test_required_group_registry_reports_duplicate_target():
    required = iter_required_tests()
    groups = [
        {
            "group_id": "first",
            "target_paths": [required[0]],
        },
        {
            "group_id": "second",
            "target_paths": [required[0], *required[1:]],
        },
    ]

    coverage = validate_required_regression_group_coverage(required, groups)

    assert coverage["duplicates"] == [{"path": required[0], "groups": ["first", "second"]}]


def test_required_group_registry_reports_unknown_target():
    required = iter_required_tests()
    unknown = "tests/test_not_in_required_registry.py"
    groups = [
        {
            "group_id": "with_extra",
            "target_paths": [*required, unknown],
        }
    ]

    coverage = validate_required_regression_group_coverage(required, groups)

    assert coverage["unknown"] == [unknown]


def test_required_parent_entry_still_matches_real_command_plan():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    required_entry = _entry_by_id(manifest, "required_regressions")
    command_by_display = {command["display"]: command for command in command_plan}

    assert required_entry["display"] in command_by_display
    assert required_entry["args"] == command_by_display[required_entry["display"]]["args"]
    for required_path in iter_required_tests():
        assert required_path in required_entry["input_file_scopes"]


def test_required_parent_scope_includes_group_specific_scope_union():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    required_entry = _entry_by_id(manifest, "required_regressions")

    assert "web/routes/domains/scheduler/scheduler_config*.py" in required_entry["input_file_scopes"]
    assert "tools/long_gate_cache.py" in required_entry["tool_file_scopes"]
    assert "node_version" in required_entry["env_keys"]
    assert "node_browser_runtime_capability" in required_entry["env_keys"]
    assert "NODE_OPTIONS" in required_entry["env_keys"]
    assert "git_executable_realpath" in required_entry["env_keys"]
    assert "git_version" in required_entry["env_keys"]
    assert "APS_BROWSER_SMOKE_REQUIRED" in required_entry["env_keys"]
    assert "chrome_version" not in required_entry["env_keys"]
    assert "chrome_executable_identity" not in required_entry["env_keys"]
    assert "chrome_headless_preflight" not in required_entry["env_keys"]
    assert "tests/app_runtime/ui_geometry_contract_data.py" in required_entry["input_file_scopes"]
    assert ".gitignore" in required_entry["config_file_scopes"]
    assert required_entry["output_result_files"] == ["evidence/QualityGate/required_regressions.json"]


def test_required_parent_fingerprint_tracks_group_specific_scope_union(tmp_path):
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=str(tmp_path))
    required_entry = _entry_by_id(manifest, "required_regressions")

    before_parent = fingerprint_entry(required_entry, str(tmp_path))
    changed = tmp_path / "web" / "routes" / "domains" / "scheduler" / "scheduler_config_feedback.py"
    changed.parent.mkdir(parents=True)
    changed.write_text("CONFIG_MARKER = True\n", encoding="utf-8")
    after_parent = fingerprint_entry(required_entry, str(tmp_path))

    assert before_parent["hash"] != after_parent["hash"]


@pytest.mark.parametrize("source", (
    "schema.sql", "core/infrastructure/migrations/v31.py",
    "web/bootstrap/__init__.py", "web/bootstrap/factory.py", "web/routes/workbench/registration.py",
    "web/routes/workbench/pages.py", "tests/workbench/fe03_route_manifest.json",
    "core/services/process/quota_protection.py", "core/services/scheduler/template_lineage.py",
    "core/services/scheduler/template_lineage_query.py", "tests/_support/dependency_boundaries.py",
    "tests/workbench/test_fe04_shared_service_dependency_contract.py",
    "tools/long_gate_manifest_environment.py", "tools/long_gate_fingerprint.py",
    "tests/gate_meta/workbench_cache_environment_support.py",
    "core/algorithm_contracts/schedule_point_evidence.py",
    "core/services/workbench/zero_duration_evidence.py", "core/services/workbench/plan_point_evidence.py",
    "core/services/workbench/piece_adoption_scope.py", "core/models/workbench_piece_adoption.py",
    "core/algorithms/greedy/piece_input.py", "core/algorithm_runtime/busy_block_skip.py",
    "core/services/scheduler/calendar_engine.py", "core/services/scheduler/calendar_service.py",
    "tests/_support/busy_block_case.py", "tests/workbench/ea_zero_duration_support.py",
    "tests/workbench/piece_adoption_support.py",
    "tests/workbench/test_eu_process_fixture_contracts.py", "tests/workbench/process_detail_files_probe.cjs",
    "tests/workbench/process_stage_widgets_probe.cjs", "tests/workbench/process_widgets_probe.cjs",
    "tests/workbench/test_point_adoption_host.py", "tests/workbench/test_run_adoption_host.py",
    "tests/workbench/run_entrypoint_support.py",
    "tests/workbench/test_piece_presentation.py", "tests/workbench/test_piece_production_connection.py",
    "tests/workbench/test_preflight_run_status.py", "tests/workbench/preflight_support.py",
    "tests/workbench/request_lifecycle_support.py", "core/services/workbench/preflight_result.py",
    "core/services/workbench/run_jobs.py", "web/routes/workbench/scheduling_jobs.py",
    "web/bootstrap/factory.py", "web/bootstrap/launcher_runtime_lock.py",
    "web/bootstrap/workbench_request_lifecycle.py", "web/bootstrap/workbench_run_runtime.py",
    "tests/workbench/test_trial_predecessor_labels.py", "tests/workbench/test_piece_chain_end_to_end.py",
    "tests/workbench/piece_production_connection_support.py", "tests/workbench/trial_predecessor_labels_probe.cjs",
    "core/infrastructure/database.py", "core/services/workbench/plan_projection.py",
    "core/services/workbench/run_candidate_tasks.py", "core/services/workbench/trial_adoption_validation.py",
    "frontend/workbench/app/PointContract.js", "frontend/workbench/app/ResourceControls.jsx",
    "frontend/workbench/app/TrialControls.jsx", "frontend/workbench/app/TrialGantt.jsx",
    "frontend/workbench/app/TrialDetails.jsx", "scripts/workbench/compile.cjs",
    "frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js",
    "frontend/workbench/prototype/ui_kits/workbench/assets/vendor/react-18.3.1.js",
))
def test_completed_ea_ec_eg_source_edit_invalidates_required_parent_fingerprint(tmp_path, source):
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(
        quality_gate_shared.build_quality_gate_command_plan(), repo_root=str(tmp_path))
    required = _entry_by_id(manifest, "required_regressions")
    path = tmp_path / source
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# before\n", encoding="utf-8")
    before = fingerprint_entry(required, str(tmp_path))
    path.write_text("# after\n", encoding="utf-8")
    assert fingerprint_entry(required, str(tmp_path))["hash"] != before["hash"]


@pytest.mark.parametrize("source", (
    "tests/workbench/piece_main_build.cjs", "tests/workbench/piece_main_seed.py",
    "tests/workbench/piece_main_oracle.py", "tests/workbench/piece_main_dependencies.cjs",
    "tests/workbench/piece_presentation_build.cjs", "tests/workbench/piece_presentation_host.jsx",
    "tests/workbench/piece_presentation_contract.cjs", "tests/workbench/test_piece_presentation.py",
    "tests/workbench/plan_ui_fixtures.cjs", "frontend/workbench/app/main.jsx",
    "scripts/workbench/build-order.json", "static/workbench/asset-manifest.json",
    "tests/workbench/plan_scope_caption_probe.cjs", "tests/workbench/ea_zero_duration_support.py",
    "tests/workbench/piece_downstream_contract.cjs", "tests/workbench/piece_downstream_browser.cjs",
    "tests/workbench/piece_downstream_browser_support.cjs", "tests/workbench/test_piece_main_browser.py",
    "frontend/workbench/app/FieldContract.js", "frontend/workbench/app/FieldTable.jsx",
    "frontend/workbench/app/FieldDetail.jsx", "frontend/workbench/app/ActualGanttContract.js",
    "frontend/workbench/app/ActualGanttModel.js", "frontend/workbench/app/ActualGanttRows.jsx",
    "core/services/workbench/field_workspace.py", "core/services/workbench/field_workspace_scope.py",
    "core/services/workbench/actual_gantt_scope.py", "core/services/workbench/actual_gantt_export.py",
    "tests/workbench/fg_plan_workspace_actions_probe.cjs", "tests/workbench/plan_adoption_baseline_support.py",
    "tests/workbench/plan_ui_browser_probe.cjs", "tests/workbench/plan_ui_browser_harness.cjs",
    "tests/workbench/point_downstream_browser_build_support.cjs", "tests/workbench/point_downstream_support.py",
    "tests/workbench/run_candidate_support.py", "tests/workbench/trial_support.py",
    "web/routes/workbench/plan_reads.py", "core/services/workbench/plan_projection.py",
    "frontend/workbench/app/PlanWorkspace.jsx", "frontend/workbench/app/PlanLayout.jsx",
    "frontend/workbench/app/PlanContract.js", "frontend/workbench/app/PlanAPI.js",
    "frontend/workbench/app/PointContract.js", "scripts/workbench/compile.cjs",
    "frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js",
))
def test_final_piece_browser_inventory_fingerprint_tracks_actual_source_inputs(tmp_path, source):
    browser = next(group for group in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
                   if group["group_id"] == "workbench_browser")
    assert source in browser["input_file_scopes"]
    path = tmp_path / source
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("before\n", encoding="utf-8")
    before = fingerprint_entry(browser, str(tmp_path))
    path.write_text("after\n", encoding="utf-8")
    assert fingerprint_entry(browser, str(tmp_path))["hash"] != before["hash"]


@pytest.mark.parametrize("env_key", (
    "APS_ET_EVIDENCE_ROOT", "PIECE_MAIN_ALL_THEMES", "PIECE_MAIN_LONG_IDS", "WORKBENCH_EV_SOURCE_ROOT",
))
def test_final_piece_environment_fingerprints_keep_required_and_browser_separate(tmp_path, monkeypatch, env_key):
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(
        quality_gate_shared.build_quality_gate_command_plan(), repo_root=str(tmp_path))
    required = _entry_by_id(manifest, "required_regressions")
    browser = next(group for group in WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
                   if group["group_id"] == "workbench_browser")
    entry = required if env_key == "APS_ET_EVIDENCE_ROOT" else browser
    assert env_key in entry["env_keys"]
    monkeypatch.setenv(env_key, "before")
    before = fingerprint_entry(entry, str(tmp_path))
    monkeypatch.setenv(env_key, "after")
    assert fingerprint_entry(entry, str(tmp_path))["hash"] != before["hash"]
    if env_key != "APS_ET_EVIDENCE_ROOT":
        assert env_key not in required["env_keys"]


@pytest.fixture
def stable_registry_runtime(monkeypatch):
    original = fingerprint_mod._runtime_fingerprint_value

    def stable_value(key, **kwargs):
        if key in fingerprint_mod.RUNTIME_FINGERPRINT_KEYS:
            return "stable-runtime"
        return original(key, **kwargs)

    monkeypatch.setattr(fingerprint_mod, "_runtime_fingerprint_value", stable_value)


@pytest.mark.parametrize("env_key", (
    "AN_SCOPE", "AY_REACT_DEV", "WORKBENCH_EXPECT_BUILD", "SYSTEM_CONFIG_SAVED_REPLAY_OLD_EFFECT",
    "TRIAL_WIDGET_TARGET_ONLY", "OUTSOURCING_UI_SCHEMA",
))
def test_browser_behavior_inputs_invalidate_full_consumers_but_not_required_or_startup(
    tmp_path, monkeypatch, stable_registry_runtime, env_key,
):
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(
        quality_gate_shared.build_quality_gate_command_plan(), repo_root=str(tmp_path))
    for entry_id in ("pytest_collect_all", "full_test_debt", "required_regressions", "startup_runtime_regressions"):
        entry = _entry_by_id(manifest, entry_id)
        observes_browser = entry_id in ("pytest_collect_all", "full_test_debt")
        assert (env_key in entry["env_keys"]) is observes_browser
        monkeypatch.setenv(env_key, "fd-before")
        before = fingerprint_entry(entry, str(tmp_path))
        monkeypatch.setenv(env_key, "fd-after")
        after = fingerprint_entry(entry, str(tmp_path))
        assert (after["hash"] != before["hash"]) is observes_browser
        if observes_browser:
            assert after["components"]["environment"]["values"][env_key] == "fd-after"


@pytest.mark.parametrize("env_key", ("AY_SMOKE", "AY_BASELINE", "AY_UNSUSPENDED", "FD_UNDECLARED_SECRET"))
def test_cleared_or_undeclared_environment_is_not_captured_by_any_test_consumer(
    tmp_path, monkeypatch, stable_registry_runtime, env_key,
):
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(
        quality_gate_shared.build_quality_gate_command_plan(), repo_root=str(tmp_path))
    for entry_id in ("pytest_collect_all", "full_test_debt", "required_regressions", "startup_runtime_regressions"):
        entry = _entry_by_id(manifest, entry_id)
        assert env_key not in entry["env_keys"]
        monkeypatch.setenv(env_key, "fd-private-before")
        before = fingerprint_entry(entry, str(tmp_path))
        monkeypatch.setenv(env_key, "fd-private-after")
        after = fingerprint_entry(entry, str(tmp_path))
        assert after["hash"] == before["hash"]
        assert "fd-private" not in json.dumps(after)


def test_required_groups_do_not_enter_formal_manifest_contract():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    entry_ids = [entry["entry_id"] for entry in manifest["entries"]]
    required = _entry_by_id(manifest, "required_regressions")

    assert len(manifest["entries"]) == len(command_plan)
    assert "required_regressions" in entry_ids
    assert all(not entry_id.startswith("required_regressions.") for entry_id in entry_ids)
    assert "groups" not in required
    assert "required_regression_group_coverage" not in required
    assert "required_regression_group_scope_policy" not in required




def test_import_cycle_entries_have_stable_ids_hash_and_scope(tmp_path):
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=str(tmp_path))
    production = _entry_by_id(manifest, "import_cycles_production")
    with_tests = _entry_by_id(manifest, "import_cycles_with_tests")

    assert production["display"] == quality_gate_shared.IMPORT_CYCLE_PRODUCTION_DISPLAY
    assert with_tests["display"] == quality_gate_shared.IMPORT_CYCLE_WITH_TESTS_DISPLAY
    assert production["reuse_allowed"] is True
    assert with_tests["reuse_allowed"] is True
    assert "core/**/*.py" in production["input_file_scopes"]
    assert "tests/**/*.py" not in production["input_file_scopes"]
    assert "tests/**/*.py" in with_tests["input_file_scopes"]
    assert ".codestable/checkup/import_cycles_production_baseline.json" in production["config_file_scopes"]
    assert ".codestable/checkup/import_cycles_with_tests_baseline.json" in with_tests["config_file_scopes"]
    for entry in (production, with_tests):
        assert "tools/scan_import_cycles.py" in entry["tool_file_scopes"]
        assert "tools/import_cycle_analysis.py" in entry["tool_file_scopes"]
        assert "tools/import_cycle_graph.py" in entry["tool_file_scopes"]
        assert "python_version" in entry["env_keys"]

    full_hash = quality_gate_shared.hash_quality_gate_commands(command_plan)
    for display in (
        quality_gate_shared.IMPORT_CYCLE_PRODUCTION_DISPLAY,
        quality_gate_shared.IMPORT_CYCLE_WITH_TESTS_DISPLAY,
    ):
        without_command = [command for command in command_plan if command["display"] != display]
        assert quality_gate_shared.hash_quality_gate_commands(without_command) != full_hash


def test_pyright_tools_entry_tracks_quality_gate_tool_paths():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)

    pyright_tools = _entry_by_id(manifest, "pyright_tools_full")

    assert pyright_tools["input_file_scopes"][: len(quality_gate_shared.QUALITY_GATE_TOOL_PATHS)] == (
        quality_gate_shared.QUALITY_GATE_TOOL_PATHS
    )
    assert set(quality_gate_shared.QUALITY_GATE_TOOL_PATHS) <= set(pyright_tools["tool_file_scopes"])


def test_long_gate_impact_explain_does_not_mark_every_entry_for_hook_only_change():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    impact = manifest_mod.explain_long_gate_impact(
        command_plan,
        ["tools/git_hook_checks.py"],
        repo_root=quality_gate_shared.REPO_ROOT,
    )
    entries = {entry["entry_id"]: entry for entry in impact["entries"]}

    assert impact["global_runner_tooling_affected"] is False
    assert entries["pyright_tools_full"]["affected"] is True
    assert "input" in entries["pyright_tools_full"]["matched_categories"]
    assert entries["startup_runtime_regressions"]["affected"] is False
    assert entries["quickref_vs_routes"]["affected"] is False
    assert entries["pyright_gate_full"]["affected"] is False


def test_long_gate_impact_explain_marks_global_runner_tooling_change_for_all_entries():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    impact = manifest_mod.explain_long_gate_impact(
        command_plan,
        ["scripts/run_quality_gate.py"],
        repo_root=quality_gate_shared.REPO_ROOT,
    )

    assert impact["global_runner_tooling_affected"] is True
    assert impact["global_matches"] == [{"path": "scripts/run_quality_gate.py", "scope": "scripts/run_quality_gate.py"}]
    assert impact["entries"]
    assert all(entry["affected"] for entry in impact["entries"])
    assert all(entry["global_runner_tooling_affected"] for entry in impact["entries"])


def test_pyright_tools_config_include_matches_quality_gate_tool_paths():
    config_path = os.path.join(
        quality_gate_shared.REPO_ROOT,
        quality_gate_shared.QUALITY_GATE_PYRIGHT_TOOLS_CONFIG,
    )
    with open(config_path, encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["include"] == list(quality_gate_shared.QUALITY_GATE_TOOL_PATHS)


def test_include_local_receipts_reports_missing_history(tmp_path, capsys):
    assert manifest_mod.main(["--print", "--include-local-receipts", "--repo-root", str(tmp_path)]) == 0

    stdout = capsys.readouterr().out

    assert "No local QualityGate receipts found." in stdout
    assert "using command-plan based long-gate candidates" in stdout
    assert "pytest_collect_all" in stdout


def test_long_gate_manifest_can_run_as_script():
    result = subprocess.run(
        [sys.executable, "tools/long_gate_manifest.py", "--print"],
        cwd=quality_gate_shared.REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )

    assert "Long gate manifest" in result.stdout
    assert "pytest_collect_all" in result.stdout


def test_unknown_local_receipt_emits_warning(tmp_path):
    receipts_dir = tmp_path / "evidence" / "QualityGate" / "receipts"
    receipts_dir.mkdir(parents=True)
    receipt_path = receipts_dir / "01_unknown.json"
    receipt_path.write_text(
        json.dumps(
            {
                "display": "python tools/unknown_slow_command.py",
                "command_index": 1,
                "returncode": 0,
                "duration_s": 12.5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    receipts = manifest_mod.load_local_quality_gate_receipts(str(tmp_path))
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(
        [
            {
                "display": "python -m pytest --collect-only -q tests",
                "args": ["python", "-m", "pytest", "--collect-only", "-q", "tests"],
                "capture_output": True,
                "output_policy": "normalized",
            }
        ],
        receipts=receipts,
        repo_root=str(tmp_path),
    )

    assert manifest["warnings"] == [
        "local receipt command is not in current plan: python tools/unknown_slow_command.py"
    ]


def test_load_local_receipts_tolerates_bad_numeric_fields(tmp_path):
    receipts_dir = tmp_path / "evidence" / "QualityGate" / "receipts"
    receipts_dir.mkdir(parents=True)
    receipt_path = receipts_dir / "bad_numeric.json"
    receipt_path.write_text(
        json.dumps(
            {
                "display": "python -m pytest --collect-only -q tests",
                "command_index": "bad",
                "returncode": "bad",
                "duration_s": "bad",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    receipts = manifest_mod.load_local_quality_gate_receipts(str(tmp_path))

    assert receipts[0]["command_index"] == 0
    assert receipts[0]["returncode"] == 0
    assert receipts[0]["duration_unknown"] is True
    assert "invalid numeric field: command_index='bad'" in receipts[0]["warnings"]
    assert "invalid numeric field: returncode='bad'" in receipts[0]["warnings"]
    assert "invalid numeric field: duration_s='bad'" in receipts[0]["warnings"]


def test_local_receipts_report_reuse_overhead_and_original_duration(tmp_path):
    receipts_dir = tmp_path / "evidence" / "QualityGate" / "receipts"
    receipts_dir.mkdir(parents=True)
    receipt_path = receipts_dir / "reuse.json"
    receipt_path.write_text(
        json.dumps(
            {
                "display": "python -m pytest --collect-only -q tests",
                "command_index": 1,
                "returncode": 0,
                "duration_s": 0.12,
                "duration_kind": "reuse_overhead",
                "original_duration_s": 8.5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    receipts = manifest_mod.load_local_quality_gate_receipts(str(tmp_path))
    line = manifest_mod._format_receipt_line(receipts[0])

    assert "0.120s" in line
    assert "kind=reuse_overhead" in line
    assert "original=8.500s" in line


def test_local_receipts_without_duration_display_duration_unknown(tmp_path):
    receipts_dir = tmp_path / "evidence" / "QualityGate" / "receipts"
    receipts_dir.mkdir(parents=True)
    receipt_path = receipts_dir / "missing_duration.json"
    receipt_path.write_text(
        json.dumps(
            {
                "display": "python -m pytest --collect-only -q tests",
                "command_index": 1,
                "returncode": 0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    receipts = manifest_mod.load_local_quality_gate_receipts(str(tmp_path))
    line = manifest_mod._format_receipt_line(receipts[0])

    assert receipts[0]["duration_unknown"] is True
    assert "duration_unknown" in line


def test_unrecognized_pytest_command_is_not_positionally_classified_as_required_or_startup():
    plan = [
        {
            "display": "python -m pytest --collect-only -q tests",
            "args": ["python", "-m", "pytest", "--collect-only", "-q", "tests"],
            "capture_output": True,
            "output_policy": "normalized",
        },
        {
            "display": "python -m pytest -q tests/test_sentinel_before_debt.py",
            "args": ["python", "-m", "pytest", "-q", "tests/test_sentinel_before_debt.py"],
            "capture_output": True,
            "output_policy": "normalized",
        },
        {
            "display": "python scripts/sync_debt_ledger.py check",
            "args": ["python", "scripts/sync_debt_ledger.py", "check"],
            "capture_output": True,
            "output_policy": "normalized",
        },
        {
            "display": "python -m pytest -q tests/test_sentinel_after_debt.py",
            "args": ["python", "-m", "pytest", "-q", "tests/test_sentinel_after_debt.py"],
            "capture_output": True,
            "output_policy": "normalized",
        },
    ]

    manifest = manifest_mod.build_manifest_from_quality_gate_plan(plan, repo_root=quality_gate_shared.REPO_ROOT)

    assert manifest["entries"][1]["entry_id"] == "unknown_02"
    assert manifest["entries"][1]["entry_type"] == "unknown"
    assert manifest["entries"][3]["entry_id"] == "unknown_04"
    assert manifest["entries"][3]["entry_type"] == "unknown"


def test_version_probe_entries_are_not_marked_as_reusable_long_gate_items():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)

    ruff_probe = _entry_by_id(manifest, "ruff_version_probe")
    pyright_probe = _entry_by_id(manifest, "pyright_version_probe")
    radon_probe = _entry_by_id(manifest, "radon_import_probe")

    assert ruff_probe["entry_type"] == "version_or_env_probe"
    assert pyright_probe["entry_type"] == "version_or_env_probe"
    assert radon_probe["entry_type"] == "version_or_env_probe"
    assert ruff_probe["reuse_allowed"] is False
    assert pyright_probe["reuse_allowed"] is False
    assert radon_probe["reuse_allowed"] is False
