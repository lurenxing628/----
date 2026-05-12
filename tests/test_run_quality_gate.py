from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def _import_run_quality_gate():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("scripts.run_quality_gate", None)
    return importlib.import_module("scripts.run_quality_gate")


def _shared_quality_registry():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    return importlib.import_module("tools.quality_gate_shared")


def _patch_repo_identity(monkeypatch, module, repo_root: Path) -> None:
    monkeypatch.setattr(
        module,
        "_repo_identity",
        lambda: {
            "checkout_root_realpath": str(repo_root.resolve()),
            "git_common_dir_realpath": str((repo_root / ".git").resolve()),
        },
    )


def _patch_basic_gate_environment(monkeypatch, module, repo_root: Path, *, statuses=None, head_sha: str = "deadbeef"):
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: head_sha)
    status_iter = iter(statuses if statuses is not None else [[], []])
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(status_iter))
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})


def _successful_result_for_display(display: str, nodeid_suffix: str = "test_quality_gate") -> dict:
    if display == "python -m ruff --version":
        return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
    if display == "python -m pyright --version":
        return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
    if display == "python -m pytest --collect-only -q tests":
        return {"stdout": f"tests/test_run_quality_gate.py::{nodeid_suffix}\n", "stderr": "", "returncode": 0}
    return {"stdout": "", "stderr": "", "returncode": 0}


def _manifest_path(repo_root: Path) -> Path:
    return repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"


def _load_manifest(module, repo_root: Path) -> dict:
    return module.json.loads(_manifest_path(repo_root).read_text(encoding="utf-8"))


def _seed_failed_manifest_with_receipts(
    module,
    repo_root: Path,
    command_plan,
    *,
    failed_index: int,
    old_run_id: str = "old-run",
    head_sha: str = "deadbeef",
    git_status_short_before=None,
    python_executable: Optional[str] = None,
    python_version: Optional[str] = None,
) -> dict:
    old_receipts = []
    for index, command in enumerate(command_plan, start=1):
        display = str(command["display"])
        result = _successful_result_for_display(display, f"test_resume_{index}")
        if index == failed_index:
            result = {"stdout": "", "stderr": "boom", "returncode": 1}
        old_receipts.append(
            module._write_command_receipt(
                command,
                run_id=old_run_id,
                index=index,
                result=result,
            )
        )
    old_manifest = {
        "status": "failed",
        "run_id": old_run_id,
        "planned_commands": [module._command_identity(command) for command in command_plan],
        "planned_commands_hash": module.hash_quality_gate_commands(command_plan),
        "commands": list(command_plan),
        "head_sha": head_sha,
        "python_executable": sys.executable if python_executable is None else python_executable,
        "python_version": sys.version.splitlines()[0].strip() if python_version is None else python_version,
        **module._repo_identity(),
        "dirty_worktree_fingerprint_before": module._dirty_worktree_fingerprint(
            git_status_short_before if git_status_short_before is not None else [" M app.py"]
        ),
        "command_receipts": old_receipts,
        "failure_message": f"命令失败：{command_plan[failed_index - 1]['display']}",
    }
    manifest_path = _manifest_path(repo_root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(module.json.dumps(old_manifest, ensure_ascii=False), encoding="utf-8")
    return old_manifest


def _small_quality_gate_plan():
    return [
        {
            "display": "python -m pytest --collect-only -q tests",
            "args": ["python", "-m", "pytest", "--collect-only", "-q", "tests"],
            "capture_output": True,
            "output_policy": "normalized",
        },
        {
            "display": "python -m ruff --version",
            "args": ["python", "-m", "ruff", "--version"],
            "capture_output": True,
            "output_policy": "exact",
        },
        {
            "display": "python -m pyright --version",
            "args": ["python", "-m", "pyright", "--version"],
            "capture_output": True,
            "output_policy": "normalized",
        },
        {
            "display": "python tools/failing_command.py",
            "args": ["python", "tools/failing_command.py"],
            "capture_output": False,
            "output_policy": "normalized",
        },
    ]


def test_shared_quality_registry_does_not_split_quality_gate_error_identity():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    shared = importlib.import_module("tools.quality_gate_shared")
    ledger = importlib.import_module("tools.quality_gate_ledger")

    registry = _shared_quality_registry()

    assert registry.QualityGateError is shared.QualityGateError
    assert ledger.QualityGateError is shared.QualityGateError


def test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain(monkeypatch):
    module = _import_run_quality_gate()

    monkeypatch.setattr(
        module,
        "_load_runtime_state",
        lambda: (
            {"pid": 321, "host": "127.0.0.1", "port": 0, "exe_path": ""},
            {"pid": 321, "exe_path": ""},
            {"contract_path": "C:/tmp/aps_runtime.json", "lock_path": "C:/tmp/aps_runtime.lock"},
        ),
    )
    monkeypatch.setattr(module, "_pid_signal", lambda payload: ("unknown", 321, None, ""))
    monkeypatch.setattr(module, "_health_signal", lambda contract: ("absent", None, None))

    with pytest.raises(module.QualityGateError) as exc_info:
        module._assert_no_active_runtime()

    message = str(exc_info.value)
    assert "活动实例判定不确定" in message
    assert "手动删除后重试" in message
    assert "contract=C:/tmp/aps_runtime.json" in message
    assert "lock=C:/tmp/aps_runtime.lock" in message
    assert "缺少 exe_path" in message
    assert "缺少运行时契约" in message
    assert "无法做健康探测" in message


def test_assert_no_active_runtime_allows_stale_trace_and_prints_paths(monkeypatch, capsys):
    module = _import_run_quality_gate()

    monkeypatch.setattr(
        module,
        "_load_runtime_state",
        lambda: (
            {"pid": 0, "host": "127.0.0.1", "port": 5000, "exe_path": sys.executable},
            None,
            {"contract_path": "C:/tmp/aps_runtime.json", "lock_path": "C:/tmp/aps_runtime.lock"},
        ),
    )
    monkeypatch.setattr(module, "_pid_signal", lambda payload: ("stale", 0, False, sys.executable))
    monkeypatch.setattr(module, "_health_signal", lambda contract: ("stale", "127.0.0.1", 5000))

    module._assert_no_active_runtime()

    stdout = capsys.readouterr().out
    assert "陈旧运行时痕迹" in stdout
    assert "contract=C:/tmp/aps_runtime.json" in stdout
    assert "lock=C:/tmp/aps_runtime.lock" in stdout


def test_main_runs_guard_preflight_before_static_and_startup_checks(monkeypatch, tmp_path):
    module = _import_run_quality_gate()

    calls = []
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)

    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: calls.append(("guard_preflight", [], False)))

    def fake_run_command(display, args, capture_output=False):
        calls.append((display, list(args), bool(capture_output)))
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks\n"
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "abc123")
    monkeypatch.setattr(module, "_git_status_lines", lambda: [])
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    monkeypatch.setattr(module, "_write_quality_gate_manifest", lambda manifest: None)

    assert module.main([]) == 0

    displays = [display for display, _args, _capture_output in calls]
    tool_pyright_display = "python -m pyright " + " ".join(module.QUALITY_GATE_TOOL_PATHS)
    assert "python -m pytest --collect-only -q tests" in displays
    assert "python -m pyright --version" in displays
    assert "python -m pyright -p pyrightconfig.gate.json" in displays
    assert tool_pyright_display in displays
    assert "tools/quality_gate_entries.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/quality_gate_ledger.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/quality_gate_scan.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/quality_gate_operations.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/quality_gate_support.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/git_hook_checks.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/test_registry.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "scripts/sync_debt_ledger.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "python -m pytest -q " + " ".join(module.REQUIRED_TEST_ARGS) in displays
    assert "python scripts/sync_debt_ledger.py check" in displays
    assert displays.index("guard_preflight") < displays.index("python -m pytest --collect-only -q tests")
    assert displays.index("python -m pytest --collect-only -q tests") < displays.index("python -m ruff --version")
    assert displays.index("guard_preflight") < displays.index("python -m ruff --version")
    assert displays.index("python -m ruff --version") < displays.index("python -m pyright --version")
    assert displays.index("python -m pyright --version") < displays.index('python -c "import radon"')
    assert displays.index("python -m ruff check") < displays.index("python -m pyright -p pyrightconfig.gate.json")
    assert displays.index("python -m pyright -p pyrightconfig.gate.json") < displays.index(tool_pyright_display)
    assert displays.index(tool_pyright_display) < displays.index(
        "python -m pytest -q tests/test_architecture_fitness.py"
    )
    assert displays.index("guard_preflight") < displays.index(
        "python -m pytest -q tests/test_architecture_fitness.py"
    )
    assert displays.index("python -m pytest -q tests/test_architecture_fitness.py") < displays.index(
        "python scripts/sync_debt_ledger.py check"
    )
    assert displays.index("python -m pytest -q " + " ".join(module.REQUIRED_TEST_ARGS)) < displays.index(
        "python scripts/sync_debt_ledger.py check"
    )
    assert displays.index("guard_preflight") < displays.index("python -m pytest -q " + " ".join(module.REQUIRED_TEST_ARGS))
    assert displays.index("python -m pytest -q " + " ".join(module.REQUIRED_TEST_ARGS)) < displays.index(
        "python scripts/sync_debt_ledger.py check"
    )
    assert displays.index("python scripts/sync_debt_ledger.py check") < displays.index(
        "python -m pytest -q " + " ".join(module.STARTUP_REGRESSION_ARGS)
    )


def test_main_executes_every_shared_command_when_plan_inserts_preflight(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    sentinel_command = {
        "display": "python tools/sentinel_inserted_after_collect.py",
        "args": ["python", "tools/sentinel_inserted_after_collect.py"],
        "capture_output": False,
        "output_policy": "normalized",
    }
    original_plan = module.build_quality_gate_command_plan()
    patched_plan = [original_plan[0], sentinel_command, *original_plan[1:]]

    calls = []
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(patched_plan))
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: calls.append(("guard_preflight", [], False)))
    monkeypatch.setattr(module, "_git_head_sha", lambda: "abc123")
    git_status_calls = iter([[], []])
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(git_status_calls))
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})

    def fake_run_command(display, args, capture_output=False):
        calls.append((display, list(args), bool(capture_output)))
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/test_run_quality_gate.py::test_main_executes_every_shared_command_when_plan_inserts_preflight\n"
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main([]) == 0

    command_displays = [display for display, _args, _capture_output in calls if display != "guard_preflight"]
    expected_displays = [str(command["display"]) for command in patched_plan]
    assert command_displays == expected_displays
    assert command_displays.count("python tools/sentinel_inserted_after_collect.py") == 1
    assert command_displays.count("python -m pyright --version") == 1

    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest = module.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [str(command["display"]) for command in manifest["commands"]] == expected_displays
    assert len(manifest["command_receipts"]) == len(patched_plan)


def test_full_test_debt_proof_is_in_shared_quality_gate_plan() -> None:
    module = _import_run_quality_gate()
    shared = _shared_quality_registry()

    command_plan = shared.build_quality_gate_command_plan()
    displays = [str(command["display"]) for command in command_plan]
    full_debt_display = "python tools/check_full_test_debt.py"
    full_debt_command = command_plan[displays.index(full_debt_display)]

    assert displays.index("python -m pytest --collect-only -q tests") < displays.index(full_debt_display)
    assert displays.index(full_debt_display) < displays.index("python -m ruff --version")
    assert full_debt_command["args"] == ["python", "tools/check_full_test_debt.py"]
    assert full_debt_command["capture_output"] is True
    assert full_debt_command["output_policy"] == "exact"

    source_paths = set(shared.QUALITY_GATE_SOURCE_FILES)
    command_arg_paths = (
        str(arg).replace("\\", "/")
        for command in command_plan
        for arg in command["args"]
    )
    command_python_targets = set(filter(lambda path: path.endswith(".py"), command_arg_paths))
    assert command_python_targets <= source_paths
    for rel_path in [
        ".pre-commit-config.yaml",
        "tools/check_full_test_debt.py",
        "tools/collect_full_test_debt.py",
        "tools/git_hook_checks.py",
        "tools/test_debt_registry.py",
        "tools/test_registry.py",
        "tests/conftest.py",
        "tests/main_style_regression_runner.py",
        "tests/test_check_full_test_debt.py",
        "tests/test_full_test_debt_registry_contract.py",
        "tests/test_architecture_fitness.py",
        "tests/check_quickref_vs_routes.py",
        "pyproject.toml",
        "开发文档/技术债务治理台账.md",
    ]:
        assert rel_path in source_paths

    tool_paths = set(shared.QUALITY_GATE_TOOL_PATHS)
    for rel_path in [
        "tools/check_full_test_debt.py",
        "tools/collect_full_test_debt.py",
        "tools/git_hook_checks.py",
        "tools/test_debt_registry.py",
        "tools/test_registry.py",
        "tests/conftest.py",
        "tests/main_style_regression_runner.py",
    ]:
        assert rel_path in tool_paths

    assert "tools/check_full_test_debt.py" in " ".join(displays)
    assert tuple(module.REQUIRED_TEST_ARGS) == tuple(shared.iter_quality_gate_required_tests())


@pytest.mark.parametrize(
    "removed_display",
    [
        "python -m pytest --collect-only -q tests",
        "python -m ruff --version",
        "python -m pyright --version",
    ],
)
def test_main_fails_when_required_command_proof_is_missing(monkeypatch, tmp_path, removed_display: str):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    patched_plan = [
        command
        for command in module.build_quality_gate_command_plan()
        if str(command["display"]) != removed_display
    ]

    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(patched_plan))
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "abc123")
    git_status_calls = iter([[], []])
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(git_status_calls))
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/test_run_quality_gate.py::test_main_fails_when_required_command_proof_is_missing\n"
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main([])

    assert removed_display in str(exc_info.value)
    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest = module.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert removed_display in manifest["failure_message"]


def test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions():
    module = _import_run_quality_gate()
    shared = _shared_quality_registry()
    from tools.test_debt_registry import iter_required_tests, iter_startup_regressions

    required_from_registry = iter_required_tests()
    startup_from_registry = iter_startup_regressions()

    assert tuple(module.REQUIRED_TEST_ARGS) == tuple(required_from_registry)
    assert tuple(module.REQUIRED_TEST_ARGS) == tuple(shared.iter_quality_gate_required_tests())
    assert tuple(module.STARTUP_REGRESSION_ARGS) == tuple(startup_from_registry)
    assert tuple(shared.QUALITY_GATE_STARTUP_REGRESSION_ARGS) == tuple(startup_from_registry)
    assert module.QUALITY_GATE_SELFTEST == shared.QUALITY_GATE_SELFTEST_PATH
    assert len(module.REQUIRED_TEST_ARGS) == len(set(module.REQUIRED_TEST_ARGS))
    assert "tests/regression_entrypoint_meta_failure_visible.py" in module.STARTUP_REGRESSION_ARGS
    assert "tests/test_launcher_observability.py" in module.STARTUP_REGRESSION_ARGS
    assert "tests/regression_scheduler_analysis_observability.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_system_history_route_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_schedule_summary_input_fallback_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_error_boundary_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_excel_template_contracts.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_critical_outline_sync.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_route_version_normalizers_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_page_version_default_latest.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_default_version_span.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_reports_page_version_default_latest.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_reports_export_version_default_latest.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_week_plan_bad_time_rows_surface_degraded.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_calendar_load_failed_degraded.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_bad_time_rows_surface_degraded.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_contract_snapshot.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_critical_chain_unavailable.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_quality_gate_scan_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_scheduler_run_entry_layout_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/test_scheduler_batches_page_viewmodel.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_scheduler_batch_template_warning_surface.py" in module.REQUIRED_TEST_ARGS
    assert "tests/test_scheduler_run_view_result_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_resource_dispatch_bad_time_rows_surface_degraded.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_resource_dispatch_export_surfaces_degraded.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_action_card_button_layout_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_mirror_template_sync.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_stable_form_layout_allowlist.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_ui_contract_table_overflow_guard.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_ui_contract_component_tokens.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_ui_presenters_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_system_backup_presenter_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_scheduler_batches_presenter_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_system_logs_layout_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_system_logs_presenter_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_form_run_option_checkbox_layout_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_scheduler_ui_range_feedback_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_scheduler_route_enforce_ready_tristate.py" in module.REQUIRED_TEST_ARGS
    assert "tests/test_holiday_default_efficiency_read_guard.py" in module.REQUIRED_TEST_ARGS
    assert "tests/test_excel_import_hardening.py" in module.REQUIRED_TEST_ARGS
    assert "tests/test_excel_utils_compare_digest_guard.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_excel_hidden_payload_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_scheduler_excel_batches_preview_baseline_precision.py" in module.REQUIRED_TEST_ARGS
    assert "tests/test_check_full_test_debt.py" in module.REQUIRED_TEST_ARGS
    assert "tests/test_full_test_debt_registry_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_config_manual_markdown.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_frontend_manual_blueprint_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_frontend_ui_language_polish.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_manual_entry_scope.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_page_manual_registry.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_excel_template_contracts.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_ui_browser_geometry_smoke.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_layout_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_request_services_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_request_services_lazy_construction.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_request_services_failure_propagation.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_factory_request_lifecycle_observability.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_maintenance_window_mutex.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_optimizer_outcome_type_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_optimizer_public_summary_projection_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_optimizer_runtime_seam_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_optimizer_seed_boundary_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_schedule_summary_overdue_warning_append_fallback.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_schedule_config_snapshot_optional_guard.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_schedule_summary_freeze_state_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/test_git_hook_checks.py" in module.REQUIRED_TEST_ARGS
    assert "tests/test_sync_debt_ledger.py" in module.REQUIRED_TEST_ARGS
    assert "tests/test_schedule_template_lookup_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_schedule_summary_size_guard_large_lists.py" in module.REQUIRED_TEST_ARGS

    command_plan = shared.build_quality_gate_command_plan()
    displays = [str(command["display"]) for command in command_plan]
    required_display = "python -m pytest -q " + " ".join(required_from_registry)
    startup_display = "python -m pytest -q " + " ".join(startup_from_registry)
    assert required_display in displays
    assert startup_display in displays
    assert displays.index(required_display) < displays.index("python scripts/sync_debt_ledger.py check")
    assert displays.index("python scripts/sync_debt_ledger.py check") < displays.index(startup_display)


def test_quality_workflow_uploads_quality_gate_manifest_artifact():
    workflow = Path(_repo_root()) / ".github" / "workflows" / "quality.yml"
    content = workflow.read_text(encoding="utf-8")

    assert "actions/upload-artifact" in content
    assert "evidence/QualityGate/" in content
    assert "--require-clean-worktree" in content
    quality_gate_job = re.search(r"(?ms)^  quality-gate:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", content)
    assert quality_gate_job is not None
    assert re.search(r"(?m)^    env:\s*$", quality_gate_job.group("body"))
    assert re.search(r"(?m)^      PYTHONUTF8:\s*['\"]?1['\"]?\s*$", quality_gate_job.group("body"))
    assert re.search(r"(?m)^      PYTHONIOENCODING:\s*['\"]?utf-8['\"]?\s*$", quality_gate_job.group("body"))
    assert re.search(r"(?m)^      APS_CHROME_PATH:\s*C:\\Program Files\\Google\\Chrome\\Application\\chrome\.exe\s*$", quality_gate_job.group("body"))
    assert "安装 Node.js 24" in quality_gate_job.group("body")
    assert "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4" in quality_gate_job.group("body")
    assert "node-version: '24'" in quality_gate_job.group("body")
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4" in quality_gate_job.group("body")


def test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitignore").write_text((Path(_repo_root()) / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "review@example.invalid"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "review"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", ".gitignore"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_root, check=True)

    stale_receipt = repo_root / "evidence" / "QualityGate" / "receipts" / "stale.json"
    stale_receipt.parent.mkdir(parents=True)
    stale_receipt.write_text("{}", encoding="utf-8")
    stale_log = repo_root / "evidence" / "QualityGate" / "logs" / "stale.log"
    stale_log.parent.mkdir(parents=True)
    stale_log.write_text("stale", encoding="utf-8")
    stale_current_debt = repo_root / "evidence" / "QualityGate" / "current_full_test_debt.json"
    stale_current_debt.write_text('{"stale": true}', encoding="utf-8")

    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/test_run_quality_gate.py::test_quality_gate_receipts\n"
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--require-clean-worktree"]) == 0
    assert not stale_receipt.exists()
    assert not stale_log.exists()
    assert not stale_current_debt.exists()

    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert status.stdout.strip() == ""

    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest = module.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "passed"
    assert manifest["git_status_short_after"] == []
    assert manifest["clean_worktree_excluded_paths"] == [
        "evidence/QualityGate/quality_gate_manifest.json",
        "evidence/QualityGate/receipts/",
        "evidence/QualityGate/logs/",
        "evidence/QualityGate/current_full_test_debt.json",
    ]
    assert len(manifest["command_receipts"]) == len(manifest["commands"])


def test_git_status_lines_expands_untracked_dir_and_keeps_readable_paths(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "review@example.invalid"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "review"], cwd=repo_root, check=True)
    (repo_root / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_root, check=True)
    untracked = repo_root / "新目录" / "未跟踪.txt"
    untracked.parent.mkdir()
    untracked.write_text("new content\n", encoding="utf-8")
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))

    assert module._git_status_lines() == ["?? 新目录/未跟踪.txt"]


def test_repo_identity_fails_closed_when_git_identity_is_unavailable(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))

    with pytest.raises(module.QualityGateError, match="无法确认仓库身份"):
        module._repo_identity()


def test_guard_preflight_rejects_missing_guard_file(monkeypatch):
    module = _import_run_quality_gate()

    monkeypatch.setattr(module, "_guard_test_exists", lambda path: path != "tests/test_sp05_path_topology_contract.py")
    monkeypatch.setattr(module, "_guard_test_tracked", lambda _path: True)

    with pytest.raises(module.QualityGateError) as exc_info:
        module._assert_guard_tests_ready()

    assert "missing=tests/test_sp05_path_topology_contract.py" in str(exc_info.value)


def test_guard_preflight_rejects_untracked_guard_file(monkeypatch):
    module = _import_run_quality_gate()

    monkeypatch.setattr(module, "_guard_test_exists", lambda _path: True)
    monkeypatch.setattr(
        module,
        "_guard_test_tracked",
        lambda path: path != "tests/test_schedule_input_builder_strict_hours_and_ext_days.py",
    )

    with pytest.raises(module.QualityGateError) as exc_info:
        module._assert_guard_tests_ready()

    assert "untracked=tests/test_schedule_input_builder_strict_hours_and_ext_days.py" in str(exc_info.value)


def test_main_writes_quality_gate_manifest_with_git_and_collection_proof(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    shared = _shared_quality_registry()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    git_status_calls = iter([[], []])
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(git_status_calls))
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    monkeypatch.setattr(
        module,
        "_repo_identity",
        lambda: {
            "checkout_root_realpath": str((repo_root / "checkout").resolve()),
            "git_common_dir_realpath": str((repo_root / ".git").resolve()),
        },
    )

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "\n".join(
                [
                    "tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
                    "tests/test_sp05_path_topology_contract.py::test_scheduler_route_topology",
                    "tests/regression_system_history_route_contract.py::test_system_history_route_uses_request_services",
                ]
            )
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main([]) == 0

    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    assert manifest_path.exists()
    manifest = module.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "passed"
    assert manifest["schema_version"] == shared.QUALITY_GATE_PROOF_SCHEMA_VERSION
    assert manifest["run_id"]
    assert manifest["head_sha"] == "deadbeef"
    assert manifest["checkout_root_realpath"] == str((repo_root / "checkout").resolve())
    assert manifest["git_common_dir_realpath"] == str((repo_root / ".git").resolve())
    assert manifest["is_dirty_before"] is False
    assert manifest["git_status_short_before"] == []
    assert manifest["is_dirty_after"] is False
    assert manifest["git_status_short_after"] == []
    assert manifest["tracked_drift_detected"] is False
    assert manifest["proof_scope"]["claim"] == "required_registry_bound_to_clean_worktree"
    assert manifest["proof_scope"]["does_not_claim"] == "risk_coverage_complete"
    assert manifest["required_tests"] == shared.iter_quality_gate_required_tests()
    assert manifest["required_tests_hash"] == shared.hash_required_tests_registry(manifest["required_tests"])
    assert manifest["commands_hash"] == shared.hash_quality_gate_commands(manifest["commands"])
    assert manifest["collection_proof_hash"] == shared.hash_quality_gate_collection_proof(manifest["collection_proof"])
    assert manifest["command_receipts_hash"] == shared.hash_quality_gate_command_receipts(manifest["command_receipts"])
    assert manifest["gate_sources_hash"] == shared.hash_quality_gate_source_proof(manifest["gate_sources"])
    assert manifest["planned_commands"] == [module._command_identity(command) for command in manifest["commands"]]
    assert manifest["planned_commands_hash"] == shared.hash_quality_gate_commands(manifest["commands"])
    assert len(manifest["command_receipts"]) == len(manifest["commands"])
    for receipt in manifest["command_receipts"]:
        receipt_path = repo_root / receipt["path"]
        assert receipt_path.exists()
        receipt_payload = module.json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt_payload["schema_version"] == shared.QUALITY_GATE_PROOF_SCHEMA_VERSION
        assert receipt_payload["run_id"] == manifest["run_id"]
        assert receipt_payload["command_hash"]
        assert receipt_payload["output_policy"] in {"exact", "normalized"}
        assert receipt_payload["stdout_log_path"].startswith("evidence/QualityGate/logs/")
        assert receipt_payload["stderr_log_path"].startswith("evidence/QualityGate/logs/")
        assert (repo_root / receipt_payload["stdout_log_path"]).exists()
        assert (repo_root / receipt_payload["stderr_log_path"]).exists()
    assert "scripts/run_quality_gate.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/quality_gate_entries.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/quality_gate_ledger.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/quality_gate_scan.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/quality_gate_operations.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "scripts/sync_debt_ledger.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/test_registry.py" in {item["path"] for item in manifest["gate_sources"]}
    assert ".github/workflows/quality.yml" in {item["path"] for item in manifest["gate_sources"]}
    assert "pyproject.toml" in {item["path"] for item in manifest["gate_sources"]}
    assert manifest["collection_proof"]["default_collect_nodeids"]
    quality_gate_entry = next(
        item for item in manifest["collection_proof"]["key_tests"] if item["path"] == "tests/test_run_quality_gate.py"
    )
    assert quality_gate_entry["execution_mode"] == "default_collect"
    regression_entry = next(
        item
        for item in manifest["collection_proof"]["key_tests"]
        if item["path"] == "tests/regression_system_history_route_contract.py"
    )
    assert regression_entry["execution_mode"] == "default_collect"


def test_guard_collect_only_keeps_analysis_and_history_in_default_collect() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests",
        ],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=True,
    )

    output = result.stdout
    assert "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability" in output
    assert "tests/regression_system_history_route_contract.py::test_system_history_route_uses_request_services" in output
    assert (
        "tests/regression_auto_assign_persist_truthy_variants.py::"
        "test_auto_assign_persist_truthy_variant_is_normalized_before_persistence"
    ) in output


def test_main_allow_dirty_worktree_marks_manifest_unbound(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    dirty_status = [" M web/routes/domains/scheduler/scheduler_config.py"]
    git_status_calls = iter([list(dirty_status), list(dirty_status)])

    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(git_status_calls))
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"dirty-diff")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})

    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append((display, list(args), bool(capture_output)))
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound\n"
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 2
    output = capsys.readouterr().out
    assert "passed_but_unbound" in output
    assert "质量门禁通过" not in output
    full_debt_call = next(call for call in calls if call[0].startswith("python tools/check_full_test_debt.py"))
    assert full_debt_call[0].endswith(" --allow-dirty-worktree-proof")
    assert full_debt_call[1][-1] == "--allow-dirty-worktree-proof"

    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest = module.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "passed_but_unbound"
    assert manifest["is_dirty_before"] is True
    assert manifest["git_status_short_before"] == dirty_status
    assert manifest["is_dirty_after"] is True
    assert manifest["git_status_short_after"] == dirty_status
    assert manifest["tracked_drift_detected"] is False
    assert manifest["resume"]["proof_status"] == "full_command_plan_unbound"
    assert manifest["proof_scope"] == {
        "claim": "diagnostic_run_completed_in_dirty_worktree",
        "does_not_claim": "required_registry_bound_to_clean_worktree",
    }
    assert any(
        str(command["display"]).endswith(" --allow-dirty-worktree-proof")
        for command in manifest["planned_commands"]
    )


def test_main_writes_running_then_passed_manifest(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    manifests = []
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)

    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    git_status_calls = iter([[], []])
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(git_status_calls))
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest\n"
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(module, "_write_quality_gate_manifest", lambda manifest: manifests.append(dict(manifest)))

    assert module.main([]) == 0
    assert [manifest.get("status") for manifest in manifests] == ["running", "passed"]
    assert manifests[0]["finished_at"] is None
    assert manifests[-1]["head_sha"] == "deadbeef"
    assert manifests[-1]["git_status_short_before"] == []
    assert manifests[-1]["git_status_short_after"] == []
    assert manifests[-1]["tracked_drift_detected"] is False


def test_main_updates_manifest_to_failed_on_command_error(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    manifests = []
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)

    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    git_status_calls = iter([[], []])
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(git_status_calls))
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            raise module.QualityGateError("collect failed")
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(module, "_write_quality_gate_manifest", lambda manifest: manifests.append(dict(manifest)))

    with pytest.raises(module.QualityGateError):
        module.main([])

    assert [manifest.get("status") for manifest in manifests] == ["running", "failed"]
    assert manifests[-1]["failure_message"] == "collect failed"
    assert manifests[-1]["git_status_short_before"] == []
    assert manifests[-1]["git_status_short_after"] == []
    assert manifests[-1]["tracked_drift_detected"] is False


def test_main_allow_dirty_resumes_from_previous_failed_command(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    stale_current_debt = repo_root / "evidence" / "QualityGate" / "current_full_test_debt.json"
    stale_current_debt.parent.mkdir(parents=True)
    stale_current_debt.write_text('{"stale": true}', encoding="utf-8")
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    _seed_failed_manifest_with_receipts(module, repo_root, command_plan, failed_index=4)

    calls = []
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 2

    output = capsys.readouterr().out
    assert "从第 4/4 步继续" in output
    assert "resume-skip" in output
    assert calls == ["python tools/failing_command.py"]

    manifest = _load_manifest(module, repo_root)
    assert manifest["status"] == "passed_but_unbound"
    assert manifest["resume"]["enabled"] is True
    assert manifest["resume"]["proof_status"] == "fast_feedback_only"
    assert manifest["resume"]["skip_count"] == 3
    assert manifest["resume"]["start_command_display"] == "python tools/failing_command.py"
    assert len(manifest["commands"]) == 4
    assert len(manifest["command_receipts"]) == 4
    assert not stale_current_debt.exists()


def test_main_does_not_resume_when_previous_manifest_head_sha_differs(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(
        monkeypatch,
        module,
        repo_root,
        statuses=[[" M app.py"], [" M app.py"]],
        head_sha="new-head",
    )
    _seed_failed_manifest_with_receipts(module, repo_root, command_plan, failed_index=4, head_sha="old-head")
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result_for_display(display, "test_resume_head_mismatch")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 2

    assert calls == [str(command["display"]) for command in command_plan]
    output = capsys.readouterr().out
    assert "未使用续跑" in output
    assert "head_sha" in output
    assert "HEAD 不一致" in output
    manifest = _load_manifest(module, repo_root)
    assert manifest["resume"]["enabled"] is False


def test_main_does_not_resume_when_previous_python_executable_differs(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    _seed_failed_manifest_with_receipts(
        module,
        repo_root,
        command_plan,
        failed_index=4,
        python_executable=str(repo_root / ".venv" / "bin" / "other-python"),
    )
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result_for_display(display, "test_resume_python_mismatch")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 2

    assert calls == [str(command["display"]) for command in command_plan]
    output = capsys.readouterr().out
    assert "未使用续跑" in output
    assert "Python 解释器" in output
    manifest = _load_manifest(module, repo_root)
    assert manifest["resume"]["enabled"] is False


def test_main_records_failed_manifest_when_run_output_cleanup_fails(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result_for_display(display, "test_cleanup_failure")

    def _boom_cleanup(**_kwargs):
        raise PermissionError("locked")

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(module, "_clear_quality_gate_run_outputs", _boom_cleanup)

    with pytest.raises(PermissionError, match="locked"):
        module.main(["--require-clean-worktree"])

    assert calls == []
    manifest = _load_manifest(module, repo_root)
    assert manifest["status"] == "failed"
    assert manifest["failure_kind"] == "quality_gate_cleanup_failed"
    assert manifest["failure_message"] == "locked"
    assert manifest["commands"] == []
    assert manifest["resume"]["proof_status"] == "failed"


def test_main_does_not_resume_when_dirty_worktree_content_differs(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "app.py").write_text("old dirty content\n", encoding="utf-8")
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    _seed_failed_manifest_with_receipts(
        module,
        repo_root,
        command_plan,
        failed_index=4,
        git_status_short_before=[" M app.py"],
    )
    (repo_root / "app.py").write_text("new dirty content\n", encoding="utf-8")
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result_for_display(display, "test_resume_dirty_fingerprint_mismatch")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 2

    assert calls == [str(command["display"]) for command in command_plan]
    output = capsys.readouterr().out
    assert "未使用续跑" in output
    assert "脏工作区内容已变化" in output
    manifest = _load_manifest(module, repo_root)
    assert manifest["resume"]["enabled"] is False


def test_main_does_not_resume_when_untracked_file_content_differs(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    untracked = repo_root / "new_dir" / "a.txt"
    untracked.parent.mkdir()
    untracked.write_text("old untracked content\n", encoding="utf-8")
    command_plan = _small_quality_gate_plan()
    status = ["?? new_dir/a.txt"]
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[status, status])
    _seed_failed_manifest_with_receipts(
        module,
        repo_root,
        command_plan,
        failed_index=4,
        git_status_short_before=status,
    )
    untracked.write_text("new untracked content\n", encoding="utf-8")
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result_for_display(display, "test_resume_untracked_fingerprint_mismatch")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 2

    assert calls == [str(command["display"]) for command in command_plan]
    output = capsys.readouterr().out
    assert "未使用续跑" in output
    assert "脏工作区内容已变化" in output
    manifest = _load_manifest(module, repo_root)
    assert manifest["resume"]["enabled"] is False


def test_main_does_not_resume_when_staged_worktree_content_differs(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "review@example.invalid"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "review"], cwd=repo_root, check=True)
    staged_file = repo_root / "app.py"
    staged_file.write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_root, check=True)
    staged_file.write_text("old staged content\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=repo_root, check=True)
    command_plan = _small_quality_gate_plan()
    status = ["M  app.py"]
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[status, status])
    _seed_failed_manifest_with_receipts(
        module,
        repo_root,
        command_plan,
        failed_index=4,
        git_status_short_before=status,
    )
    staged_file.write_text("new staged content\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=repo_root, check=True)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result_for_display(display, "test_resume_staged_fingerprint_mismatch")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 2

    assert calls == [str(command["display"]) for command in command_plan]
    output = capsys.readouterr().out
    assert "未使用续跑" in output
    assert "脏工作区内容已变化" in output
    manifest = _load_manifest(module, repo_root)
    assert manifest["resume"]["enabled"] is False


def test_main_does_not_resume_when_real_dirty_content_changes(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "app.py").write_text("print('clean')\n", encoding="utf-8")
    (repo_root / ".gitignore").write_text("evidence/\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=str(repo_root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "app.py", ".gitignore"], cwd=str(repo_root), check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test Runner", "commit", "-m", "base"],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    command_plan = _small_quality_gate_plan()
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    (repo_root / "app.py").write_text("print('dirty before')\n", encoding="utf-8")
    head_sha = module._git_head_sha()
    _seed_failed_manifest_with_receipts(module, repo_root, command_plan, failed_index=4, head_sha=head_sha)
    (repo_root / "app.py").write_text("print('dirty after')\n", encoding="utf-8")

    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result_for_display(display, "test_real_dirty_content_changed")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 2

    assert calls == [str(command["display"]) for command in command_plan]
    output = capsys.readouterr().out
    assert "脏工作区内容已变化" in output
    manifest = _load_manifest(module, repo_root)
    assert manifest["resume"]["enabled"] is False
    assert manifest["resume"]["proof_status"] == "full_command_plan_unbound"


def test_dirty_worktree_fingerprint_raises_when_git_diff_fails(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))

    class _Result:
        returncode = 128
        stdout = b""
        stderr = b"fatal: external diff died"

    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: _Result())

    with pytest.raises(module.QualityGateError, match="无法生成脏工作区指纹"):
        module._dirty_worktree_fingerprint([" M app.py"])


def test_dirty_fingerprint_detects_quoted_untracked_path_change(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    path = repo_root / "a\nb.txt"
    path.write_text("before", encoding="utf-8")
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"")

    before = module._dirty_worktree_fingerprint(['?? "a\\nb.txt"'])
    path.write_text("after", encoding="utf-8")
    after = module._dirty_worktree_fingerprint(['?? "a\\nb.txt"'])

    assert before != after


def test_dirty_fingerprint_detects_untracked_symlink_target_change(monkeypatch, tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlink is not available on this platform")
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    link_path = repo_root / "missing-link"
    os.symlink("missing-a", link_path)
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"")

    before = module._dirty_worktree_fingerprint(["?? missing-link"])
    link_path.unlink()
    os.symlink("missing-b", link_path)
    after = module._dirty_worktree_fingerprint(["?? missing-link"])

    assert before != after


def test_dirty_fingerprint_preserves_untracked_path_edge_spaces(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    leading_path = repo_root / " leading.txt"
    trailing_path = repo_root / "trailing.txt "
    leading_path.write_text("before", encoding="utf-8")
    trailing_path.write_text("before", encoding="utf-8")
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"")

    before = module._dirty_worktree_fingerprint(["??  leading.txt", "?? trailing.txt "])
    leading_path.write_text("after", encoding="utf-8")
    trailing_path.write_text("after", encoding="utf-8")
    after = module._dirty_worktree_fingerprint(["??  leading.txt", "?? trailing.txt "])

    assert before != after


def test_apply_worktree_proof_detects_same_status_content_drift(monkeypatch):
    module = _import_run_quality_gate()
    fingerprints = iter(
        [
            {"status_lines": [" M app.py"], "content_sha256": "before"},
            {"status_lines": [" M app.py"], "content_sha256": "after"},
        ]
    )
    monkeypatch.setattr(module, "_dirty_worktree_fingerprint", lambda _status_lines: next(fingerprints))
    manifest = {}

    module._apply_worktree_proof(
        manifest,
        git_status_short_before=[" M app.py"],
        git_status_short_after=[" M app.py"],
    )

    assert manifest["dirty_worktree_fingerprint_before"]["content_sha256"] == "before"
    assert manifest["dirty_worktree_fingerprint_after"]["content_sha256"] == "after"
    assert manifest["tracked_drift_detected"] is True


def test_status_line_path_only_treats_rename_or_copy_as_arrow_path() -> None:
    module = _import_run_quality_gate()

    assert module._status_line_path("R  old/path.py -> new/path.py") == "new/path.py"
    assert module._status_line_path("C  old/template.py -> new/template.py") == "new/template.py"
    assert module._status_line_path("?? reports/a -> b.txt") == "reports/a -> b.txt"


def test_main_preserves_stale_manifest_when_resume_fingerprint_fails(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    old_manifest = _seed_failed_manifest_with_receipts(module, repo_root, command_plan, failed_index=4)
    old_receipt_paths = [repo_root / receipt["path"] for receipt in old_manifest["command_receipts"]]
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    def _boom_fingerprint(_status_lines):
        raise module.QualityGateError("fingerprint boom")

    monkeypatch.setattr(module, "_dirty_worktree_fingerprint", _boom_fingerprint)

    with pytest.raises(module.QualityGateError, match="fingerprint boom"):
        module.main(["--allow-dirty-worktree"])

    manifest = _load_manifest(module, repo_root)
    assert manifest["run_id"] == old_manifest["run_id"]
    assert manifest["failure_message"] == old_manifest["failure_message"]
    assert all(path.exists() for path in old_receipt_paths)


def test_main_preserves_stale_manifest_until_new_manifest_can_be_written(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    old_manifest = _seed_failed_manifest_with_receipts(module, repo_root, command_plan, failed_index=4)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    def _changed_fingerprint(_status_lines):
        return {"status_lines": [" M app.py"], "content_sha256": "changed"}

    monkeypatch.setattr(module, "_dirty_worktree_fingerprint", _changed_fingerprint)
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: (_ for _ in ()).throw(module.QualityGateError("runtime snapshot boom")))

    with pytest.raises(module.QualityGateError, match="runtime snapshot boom"):
        module.main(["--allow-dirty-worktree"])

    manifest = _load_manifest(module, repo_root)
    assert manifest["run_id"] == old_manifest["run_id"]
    assert manifest["failure_message"] == old_manifest["failure_message"]


def test_main_no_resume_forces_full_rerun(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    _seed_failed_manifest_with_receipts(module, repo_root, command_plan, failed_index=4)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result_for_display(display, "test_no_resume")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree", "--no-resume"]) == 2

    assert calls == [str(command["display"]) for command in command_plan]
    output = capsys.readouterr().out
    assert "--no-resume" in output
    assert "未使用续跑" in output


@pytest.mark.parametrize("break_kind", ["missing_receipt", "hash_mismatch", "bad_json", "log_path_mismatch"])
def test_main_does_not_resume_when_previous_receipt_invalid(monkeypatch, tmp_path, capsys, break_kind: str):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    old_manifest = _seed_failed_manifest_with_receipts(module, repo_root, command_plan, failed_index=4)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    first_receipt_path = repo_root / old_manifest["command_receipts"][0]["path"]
    if break_kind == "missing_receipt":
        first_receipt_path.unlink()
    elif break_kind == "hash_mismatch":
        first_receipt_path.write_text(first_receipt_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    elif break_kind == "bad_json":
        first_receipt_path.write_text("not json", encoding="utf-8")
        old_manifest["command_receipts"][0]["sha256"] = module._sha256_file(str(first_receipt_path))
        _manifest_path(repo_root).write_text(module.json.dumps(old_manifest, ensure_ascii=False), encoding="utf-8")
    else:
        payload = module.json.loads(first_receipt_path.read_text(encoding="utf-8"))
        payload["stdout_log_path"] = "evidence/QualityGate/logs/not-the-expected.stdout.log"
        first_receipt_path.write_text(module.json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        old_manifest["command_receipts"][0]["sha256"] = module._sha256_file(str(first_receipt_path))
        _manifest_path(repo_root).write_text(module.json.dumps(old_manifest, ensure_ascii=False), encoding="utf-8")

    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result_for_display(display, f"test_invalid_receipt_{break_kind}")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 2

    assert calls == [str(command["display"]) for command in command_plan]
    output = capsys.readouterr().out
    assert "未使用续跑" in output
    assert "完整重跑" in output


def test_main_does_not_resume_when_full_command_plan_changes_after_failure(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    old_plan = _small_quality_gate_plan()
    new_plan = [dict(command) for command in old_plan]
    new_plan[-1] = {
        "display": "python tools/changed_command.py",
        "args": ["python", "tools/changed_command.py"],
        "capture_output": False,
        "output_policy": "normalized",
    }
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    _seed_failed_manifest_with_receipts(module, repo_root, old_plan, failed_index=2)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(new_plan))

    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result_for_display(display, "test_changed_plan")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 2

    assert calls == [str(command["display"]) for command in new_plan]
    assert "命令计划已变化" in capsys.readouterr().out


def test_main_never_skips_previous_failed_command(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    _seed_failed_manifest_with_receipts(module, repo_root, command_plan, failed_index=2)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result_for_display(display, "test_never_skip_failed")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 2

    assert calls[0] == command_plan[1]["display"]
    assert calls == [str(command["display"]) for command in command_plan[1:]]


def test_command_failure_prints_step_receipt_logs_and_last_80_lines(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()[:3]
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m pytest --collect-only -q tests":
            return _successful_result_for_display(display, "test_failure_tail")
        if display == "python -m ruff --version":
            stderr = "\n".join(f"err line {index}" for index in range(1, 101))
            return {"stdout": "", "stderr": stderr, "returncode": 1}
        return _successful_result_for_display(display, "test_failure_tail")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main(["--require-clean-worktree"])

    captured = capsys.readouterr()
    message = str(exc_info.value)
    output = captured.out + captured.err
    combined = output + message
    assert "第 2/3 步失败" in combined
    assert "python -m ruff --version" in combined
    assert "evidence/QualityGate/receipts/" in combined
    assert "evidence/QualityGate/logs/" in combined
    assert "err line 100" in combined
    assert "err line 1" not in combined.splitlines()


def test_main_preserves_failed_manifest_when_worktree_fingerprint_fails_after_command_error(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()[:2]
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[], [" M app.py"]])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m pytest --collect-only -q tests":
            return _successful_result_for_display(display, "test_failed_manifest_when_fingerprint_fails")
        return {"stdout": "", "stderr": "ruff exploded", "returncode": 1}

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: (_ for _ in ()).throw(module.QualityGateError("diff broken")))

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main(["--require-clean-worktree"])

    assert "python -m ruff --version" in str(exc_info.value)
    manifest = _load_manifest(module, repo_root)
    assert manifest["status"] == "failed"
    assert manifest["failure_message"] == str(exc_info.value)
    assert "diff broken" in manifest["worktree_proof_error"]


def test_main_preserves_original_failure_when_failed_manifest_proof_fails(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()[:2]
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m pytest --collect-only -q tests":
            return _successful_result_for_display(display, "test_failed_manifest_proof_fails")
        return {"stdout": "", "stderr": "ruff exploded", "returncode": 1}

    def _boom_manifest_proof(_manifest, *, repo_root):
        if _manifest.get("status") == "failed":
            raise OSError("manifest proof broken")

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(module, "apply_quality_gate_manifest_proof_fields", _boom_manifest_proof)

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main(["--require-clean-worktree"])

    assert "python -m ruff --version" in str(exc_info.value)
    manifest = _load_manifest(module, repo_root)
    assert manifest["status"] == "failed"
    assert manifest["failure_message"] == str(exc_info.value)
    assert manifest["manifest_proof_error"] == "manifest proof broken"


def test_main_preserves_original_failure_when_git_status_after_raises_oserror(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()[:2]
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    status_calls = iter([[], OSError("git missing")])

    def _status_or_boom():
        value = next(status_calls)
        if isinstance(value, OSError):
            raise value
        return value

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m pytest --collect-only -q tests":
            return _successful_result_for_display(display, "test_git_status_after_oserror")
        return {"stdout": "", "stderr": "ruff exploded", "returncode": 1}

    monkeypatch.setattr(module, "_git_status_lines", _status_or_boom)
    monkeypatch.setattr(module, "_run_command", fake_run_command)

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main(["--require-clean-worktree"])

    assert "python -m ruff --version" in str(exc_info.value)
    manifest = _load_manifest(module, repo_root)
    assert manifest["status"] == "failed"
    assert manifest["failure_message"] == str(exc_info.value)
    assert "git missing" in manifest["worktree_proof_error"]


def test_resume_rechecks_dirty_fingerprint_after_decision_before_skip(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    old_manifest = _seed_failed_manifest_with_receipts(module, repo_root, command_plan, failed_index=3)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    old_fingerprint = dict(old_manifest["dirty_worktree_fingerprint_before"])
    changed_fingerprint = {"status_lines": [" M app.py"], "content_sha256": "changed"}
    fingerprint_calls = {"count": 0}

    def fake_dirty_fingerprint(_status_lines):
        fingerprint_calls["count"] += 1
        return old_fingerprint if fingerprint_calls["count"] == 1 else changed_fingerprint

    monkeypatch.setattr(module, "_dirty_worktree_fingerprint", fake_dirty_fingerprint)
    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result_for_display(display, "test_resume_recheck")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main(["--allow-dirty-worktree"])

    assert "续跑判定后又发生变化" in str(exc_info.value)
    assert calls == []
    manifest = _load_manifest(module, repo_root)
    assert manifest["status"] == "failed"
    assert manifest["failure_kind"] == "resume_dirty_fingerprint_changed"



def test_main_rejects_dirty_worktree_by_default(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    monkeypatch.setattr(module, "_git_status_lines", lambda: [" M scripts/run_quality_gate.py"])
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"dirty-diff")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    monkeypatch.setattr(module, "_run_command", lambda display, args, capture_output=False: "")

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main([])

    assert "dirty worktree" in str(exc_info.value)
    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest = module.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["failure_kind"] == "dirty_before_gate"
    assert manifest["resume"]["proof_status"] == "failed"


def test_main_rejects_dirty_worktree_when_require_clean_worktree(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    monkeypatch.setattr(module, "_git_status_lines", lambda: [" M scripts/run_quality_gate.py"])
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"dirty-diff")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    monkeypatch.setattr(module, "_run_command", lambda display, args, capture_output=False: "")

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main(["--require-clean-worktree"])

    assert "dirty worktree" in str(exc_info.value)
    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest = module.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["failure_kind"] == "dirty_before_gate"


def test_high_risk_untracked_source_diagnostic_covers_production_imported_py() -> None:
    module = _import_run_quality_gate()

    status_lines = [
        "?? core/services/scheduler/version_resolution.py",
        "?? docs/scratch.md",
        "?? evidence/QualityGate/quality_gate_manifest.json",
    ]

    assert module._high_risk_untracked_source_paths(status_lines) == [
        "core/services/scheduler/version_resolution.py",
    ]


def test_main_dirty_worktree_message_names_untracked_source(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    monkeypatch.setattr(
        module,
        "_git_status_lines",
        lambda: ["?? core/services/scheduler/version_resolution.py"],
    )
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    monkeypatch.setattr(module, "_run_command", lambda display, args, capture_output=False: "")

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main(["--require-clean-worktree"])

    message = str(exc_info.value)
    assert "dirty worktree" in message
    assert "untracked source files" in message
    assert "core/services/scheduler/version_resolution.py" in message


def test_main_fails_when_tracked_status_changes_during_gate(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    manifests = []
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)

    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    git_status_calls = iter([[], [" M scripts/run_quality_gate.py"]])
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(git_status_calls))
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"dirty-diff")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate\n"
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(module, "_write_quality_gate_manifest", lambda manifest: manifests.append(module.json.loads(module.json.dumps(manifest))))

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main([])

    assert "tracked drift" in str(exc_info.value)
    assert [manifest.get("status") for manifest in manifests] == ["running", "failed"]
    assert manifests[-1]["git_status_short_before"] == []
    assert manifests[-1]["git_status_short_after"] == [" M scripts/run_quality_gate.py"]
    assert manifests[-1]["tracked_drift_detected"] is True
