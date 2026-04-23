from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

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
    sys.modules.pop("tools.quality_gate_shared", None)
    return importlib.import_module("tools.quality_gate_shared")


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


def test_main_runs_guard_preflight_before_static_and_startup_checks(monkeypatch):
    module = _import_run_quality_gate()

    calls = []

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
    assert "python -m pytest --collect-only -q tests" in displays
    assert "python -m pyright --version" in displays
    assert "python -m pyright -p pyrightconfig.gate.json" in displays
    assert "python -m pyright scripts/run_quality_gate.py tools/quality_gate_shared.py" in displays
    assert "python -m pytest -q tests/test_run_quality_gate.py" in displays
    assert "python scripts/sync_debt_ledger.py check" in displays
    assert displays.index("guard_preflight") < displays.index("python -m pytest --collect-only -q tests")
    assert displays.index("python -m pytest --collect-only -q tests") < displays.index("python -m ruff --version")
    assert displays.index("guard_preflight") < displays.index("python -m ruff --version")
    assert displays.index("python -m ruff --version") < displays.index("python -m pyright --version")
    assert displays.index("python -m pyright --version") < displays.index('python -c "import radon"')
    assert displays.index("python -m ruff check") < displays.index("python -m pyright -p pyrightconfig.gate.json")
    assert displays.index("python -m pyright -p pyrightconfig.gate.json") < displays.index(
        "python -m pyright scripts/run_quality_gate.py tools/quality_gate_shared.py"
    )
    assert displays.index("python -m pyright scripts/run_quality_gate.py tools/quality_gate_shared.py") < displays.index(
        "python -m pytest -q tests/test_architecture_fitness.py"
    )
    assert displays.index("guard_preflight") < displays.index(
        "python -m pytest -q tests/test_architecture_fitness.py"
    )
    assert displays.index("python -m pytest -q tests/test_architecture_fitness.py") < displays.index(
        "python scripts/sync_debt_ledger.py check"
    )
    assert displays.index("python -m pytest -q " + " ".join(module.GUARD_TEST_ARGS)) < displays.index(
        "python scripts/sync_debt_ledger.py check"
    )
    assert displays.index("guard_preflight") < displays.index("python -m pytest -q " + " ".join(module.GUARD_TEST_ARGS))
    assert displays.index("python -m pytest -q tests/test_run_quality_gate.py") < displays.index(
        "python scripts/sync_debt_ledger.py check"
    )
    assert displays.index("python scripts/sync_debt_ledger.py check") < displays.index(
        "python -m pytest -q " + " ".join(module.STARTUP_REGRESSION_ARGS)
    )


def test_guard_suite_includes_scheduler_followup_regressions():
    module = _import_run_quality_gate()
    shared = _shared_quality_registry()

    assert tuple(module.GUARD_TEST_ARGS) == tuple(shared.QUALITY_GATE_GUARD_TESTS)
    assert module.QUALITY_GATE_SELFTEST == shared.QUALITY_GATE_SELFTEST_PATH
    assert len(module.GUARD_TEST_ARGS) == len(set(module.GUARD_TEST_ARGS))
    assert "tests/regression_scheduler_analysis_observability.py" in module.GUARD_TEST_ARGS
    assert "tests/regression_system_history_route_contract.py" in module.GUARD_TEST_ARGS
    assert "tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py" in module.GUARD_TEST_ARGS
    assert "tests/regression_schedule_summary_input_fallback_contract.py" in module.GUARD_TEST_ARGS


def test_quality_workflow_uploads_quality_gate_manifest_artifact():
    workflow = Path(_repo_root()) / ".github" / "workflows" / "quality.yml"
    content = workflow.read_text(encoding="utf-8")

    assert "actions/upload-artifact" in content
    assert "evidence/QualityGate/quality_gate_manifest.json" in content
    assert "--require-clean-worktree" in content


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
                ]
            )
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main([]) == 0

    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    assert manifest_path.exists()
    manifest = module.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "passed"
    assert manifest["head_sha"] == "deadbeef"
    assert manifest["checkout_root_realpath"] == str((repo_root / "checkout").resolve())
    assert manifest["git_common_dir_realpath"] == str((repo_root / ".git").resolve())
    assert manifest["is_dirty_before"] is False
    assert manifest["git_status_short_before"] == []
    assert manifest["is_dirty_after"] is False
    assert manifest["git_status_short_after"] == []
    assert manifest["tracked_drift_detected"] is False
    assert manifest["collection_proof"]["default_collect_nodeids"]
    quality_gate_entry = next(
        item for item in manifest["collection_proof"]["key_tests"] if item["path"] == "tests/test_run_quality_gate.py"
    )
    assert quality_gate_entry["execution_mode"] == "default_collect"


def test_guard_collect_only_keeps_analysis_and_history_in_default_collect() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "tests/regression_scheduler_analysis_observability.py",
            "tests/regression_system_history_route_contract.py",
        ],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=True,
    )

    output = result.stdout
    assert "tests/regression_scheduler_analysis_observability.py::regression_scheduler_analysis_observability" in output
    assert "tests/regression_system_history_route_contract.py::test_system_history_route_uses_request_services" in output


def test_main_allow_dirty_worktree_marks_manifest_unbound(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    dirty_status = [" M web/routes/domains/scheduler/scheduler_config.py"]
    git_status_calls = iter([list(dirty_status), list(dirty_status)])

    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(git_status_calls))
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound\n"
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 0

    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest = module.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "passed_but_unbound"
    assert manifest["is_dirty_before"] is True
    assert manifest["git_status_short_before"] == dirty_status
    assert manifest["is_dirty_after"] is True
    assert manifest["git_status_short_after"] == dirty_status
    assert manifest["tracked_drift_detected"] is False


def test_main_writes_running_then_passed_manifest(monkeypatch):
    module = _import_run_quality_gate()
    manifests = []

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


def test_main_updates_manifest_to_failed_on_command_error(monkeypatch):
    module = _import_run_quality_gate()
    manifests = []

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


def test_main_rejects_dirty_worktree_by_default(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    monkeypatch.setattr(module, "_git_status_lines", lambda: [" M scripts/run_quality_gate.py"])
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    monkeypatch.setattr(module, "_run_command", lambda display, args, capture_output=False: "")

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main([])

    assert "dirty worktree" in str(exc_info.value)


def test_main_rejects_dirty_worktree_when_require_clean_worktree(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    monkeypatch.setattr(module, "_git_status_lines", lambda: [" M scripts/run_quality_gate.py"])
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    monkeypatch.setattr(module, "_run_command", lambda display, args, capture_output=False: "")

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main(["--require-clean-worktree"])

    assert "dirty worktree" in str(exc_info.value)


def test_main_fails_when_tracked_status_changes_during_gate(monkeypatch):
    module = _import_run_quality_gate()
    manifests = []

    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    git_status_calls = iter([[], [" M scripts/run_quality_gate.py"]])
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(git_status_calls))
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
