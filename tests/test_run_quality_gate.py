from __future__ import annotations

import importlib
import re
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
    return importlib.import_module("tools.quality_gate_shared")


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
        "display": "python tools/check_full_test_debt.py",
        "args": ["python", "tools/check_full_test_debt.py"],
        "capture_output": False,
        "output_policy": "normalized",
    }
    original_plan = module.build_quality_gate_command_plan()
    patched_plan = [original_plan[0], sentinel_command, *original_plan[1:]]

    calls = []
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
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
    assert command_displays.count("python tools/check_full_test_debt.py") == 1
    assert command_displays.count("python -m pyright --version") == 1

    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest = module.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [str(command["display"]) for command in manifest["commands"]] == expected_displays
    assert len(manifest["command_receipts"]) == len(patched_plan)


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

    assert tuple(module.REQUIRED_TEST_ARGS) == tuple(shared.iter_quality_gate_required_tests())
    assert module.QUALITY_GATE_SELFTEST == shared.QUALITY_GATE_SELFTEST_PATH
    assert len(module.REQUIRED_TEST_ARGS) == len(set(module.REQUIRED_TEST_ARGS))
    assert "tests/regression_scheduler_analysis_observability.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_system_history_route_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_schedule_summary_input_fallback_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_error_boundary_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_critical_outline_sync.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_route_version_normalizers_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_page_version_default_latest.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_reports_page_version_default_latest.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_reports_export_version_default_latest.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_calendar_load_failed_degraded.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_bad_time_rows_surface_degraded.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_contract_snapshot.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_gantt_critical_chain_unavailable.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_quality_gate_scan_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_request_services_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_request_services_lazy_construction.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_request_services_failure_propagation.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_optimizer_outcome_type_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_optimizer_public_summary_projection_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_optimizer_runtime_seam_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_optimizer_seed_boundary_contract.py" in module.REQUIRED_TEST_ARGS
    assert "tests/regression_schedule_summary_size_guard_large_lists.py" in module.REQUIRED_TEST_ARGS


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
    ]
    assert len(manifest["command_receipts"]) == len(manifest["commands"])


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
    assert len(manifest["command_receipts"]) == len(manifest["commands"])
    for receipt in manifest["command_receipts"]:
        receipt_path = repo_root / receipt["path"]
        assert receipt_path.exists()
        receipt_payload = module.json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt_payload["schema_version"] == shared.QUALITY_GATE_PROOF_SCHEMA_VERSION
        assert receipt_payload["run_id"] == manifest["run_id"]
        assert receipt_payload["command_hash"]
        assert receipt_payload["output_policy"] in {"exact", "normalized"}
    assert "scripts/run_quality_gate.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/quality_gate_entries.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/quality_gate_ledger.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/quality_gate_scan.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/quality_gate_operations.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "scripts/sync_debt_ledger.py" in {item["path"] for item in manifest["gate_sources"]}
    assert ".github/workflows/quality.yml" in {item["path"] for item in manifest["gate_sources"]}
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


def test_main_writes_running_then_passed_manifest(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    manifests = []
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))

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
    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest = module.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["failure_kind"] == "dirty_before_gate"


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
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    monkeypatch.setattr(
        module,
        "_git_status_lines",
        lambda: ["?? core/services/scheduler/version_resolution.py"],
    )
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
