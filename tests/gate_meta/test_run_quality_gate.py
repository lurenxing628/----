"""回归测试：scripts/run_quality_gate.py 质量门——校验共享命令计划与 tools.quality_gate_shared 一致(QualityGateError 身份不分裂、必跑命令顺序 guard_preflight→collect→ruff→pyright→…、全 collect/ruff/pyright 命令回执齐全)、活动运行时探测的不确定/陈旧判定与提示、缺命令证据时 main 失败并写 failed manifest、REQUIRED/STARTUP 测试集来自 test_debt_registry 且覆盖高风险回归、env_overlay(APS_BROWSER_SMOKE_REQUIRED 等)透传、--require-clean-worktree 重建被忽略回执不弄脏干净工作区、pyright tools 覆盖与 config include 一致性、long_gate 静态证据落盘。"""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest

from tests._support.paths import REPO_ROOT, REPO_ROOT_STR


def _repo_root() -> str:
    return REPO_ROOT_STR


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
    if not (repo_root / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: head_sha)
    status_iter = iter(statuses if statuses is not None else [[], []])
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(status_iter))
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    monkeypatch.setattr(module, "_assert_pyright_tools_coverage", lambda: None)


def _successful_result_for_display(display: str, nodeid_suffix: str = "test_quality_gate") -> dict:
    if display == "python -m ruff --version":
        return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
    if display == "python -m pyright --version":
        return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
    if display == "python -m pytest --collect-only -q tests":
        return {"stdout": f"tests/gate_meta/test_run_quality_gate.py::{nodeid_suffix}\n", "stderr": "", "returncode": 0}
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


def _write_long_gate_collect_input(repo_root: Path, text: str = "def test_cached_collect():\n    assert True\n") -> Path:
    test_path = repo_root / "tests" / "test_cached_collect.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(text, encoding="utf-8")
    return test_path


def _collect_long_gate_entry(module, command_plan, repo_root: Path) -> dict:
    manifest = module.build_manifest_from_quality_gate_plan(command_plan, repo_root=str(repo_root))
    return next(
        entry for entry in manifest["entries"] if str(entry.get("entry_id") or "") == module.ENTRY_PYTEST_COLLECT_ALL
    )


def _seed_collect_long_gate_success(
    module,
    command_plan,
    repo_root: Path,
    *,
    stdout: str = "tests/test_cached_collect.py::test_cached_collect\n",
) -> dict:
    if not (repo_root / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    entry = _collect_long_gate_entry(module, command_plan, repo_root)
    fingerprint = module.fingerprint_entry(entry, str(repo_root))
    collect_payload = module.build_collect_nodeids_payload(
        stdout,
        pytest_version=module.pytest_distribution_version(),
        collect_stdout_log_path="evidence/QualityGate/logs/seed-collect.stdout.log",
    )
    collect_rel_path = module.write_collect_nodeids(collect_payload, repo_root=str(repo_root))
    module.write_long_gate_success(
        entry,
        fingerprint,
        {"stdout": stdout, "stderr": "", "returncode": 0, "duration_s": 12.5},
        [str(repo_root / collect_rel_path)],
        repo_root=str(repo_root),
    )
    return entry


def _load_receipt_payload(module, repo_root: Path, manifest: dict, index: int) -> dict:
    receipt_entry = manifest["command_receipts"][index]
    return module.json.loads((repo_root / receipt_entry["path"]).read_text(encoding="utf-8"))


def _load_long_gate_summary(module, repo_root: Path) -> dict:
    summary_path = repo_root / "evidence" / "QualityGate" / "long_gate" / "summary.json"
    return module.json.loads(summary_path.read_text(encoding="utf-8"))


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


def test_pid_signal_keeps_unknown_pid_probe_visible(monkeypatch):
    module = _import_run_quality_gate()

    monkeypatch.setattr(module.launcher, "runtime_pid_state", lambda pid: None)

    state, pid, pid_match, exe_path = module._pid_signal(
        {"pid": 321, "exe_path": sys.executable}
    )

    assert state == module.RuntimeProbeState.UNKNOWN
    assert pid == 321
    assert pid_match is None
    assert exe_path == sys.executable


def test_main_runs_guard_preflight_before_static_and_startup_checks(monkeypatch, tmp_path):
    module = _import_run_quality_gate()

    calls = []
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    _patch_repo_identity(monkeypatch, module, repo_root)

    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: calls.append(("guard_preflight", [], False)))

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append((display, list(args), bool(capture_output)))
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/gate_meta/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks\n"
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "abc123")
    monkeypatch.setattr(module, "_git_status_lines", lambda: [])
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    monkeypatch.setattr(module, "_assert_pyright_tools_coverage", lambda: None)
    monkeypatch.setattr(module, "_write_quality_gate_manifest", lambda manifest: None)

    assert module.main([]) == 0

    displays = [display for display, _args, _capture_output in calls]
    tool_pyright_display = f"python -m pyright -p {module.PYRIGHT_TOOLS_CONFIG}"
    assert "python -m pytest --collect-only -q tests" in displays
    assert "python -m pyright --version" in displays
    assert "python -m pyright -p pyrightconfig.gate.json" in displays
    assert tool_pyright_display in displays
    tool_pyright_call = next((row for row in calls if row[0] == tool_pyright_display), None)
    assert tool_pyright_call is not None
    assert tool_pyright_call[1][1:] == ["-m", "pyright", "-p", module.PYRIGHT_TOOLS_CONFIG]
    assert "scripts/run_daily_quality_gate.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/fast_static_precheck.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/architecture_scan_cache.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/quality_gate_entries.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/quality_gate_ledger.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/quality_gate_scan.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/quality_gate_operations.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/quality_gate_support.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/git_hook_checks.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/test_registry.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/long_gate_cache.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/long_gate_collect.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/long_gate_fingerprint.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/full_test_debt_shards.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/long_gate_manifest.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/long_gate_paths.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/long_gate_schema.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "tools/long_gate_summary.py" in module.QUALITY_GATE_TOOL_PATHS
    assert "scripts/sync_debt_ledger.py" in module.QUALITY_GATE_TOOL_PATHS
    required_display = "python tools/verify_required_regressions_from_full_test_debt.py"
    assert required_display in displays
    assert "python scripts/sync_debt_ledger.py check" in displays
    assert displays.index("guard_preflight") < displays.index("python -m pytest --collect-only -q tests")
    assert displays.index("python -m pytest --collect-only -q tests") < displays.index("python -m ruff --version")
    assert displays.index("guard_preflight") < displays.index("python -m ruff --version")
    assert displays.index("python -m ruff --version") < displays.index("python -m pyright --version")
    assert displays.index("python -m pyright --version") < displays.index('python -c "import radon"')
    assert displays.index("python -m ruff check") < displays.index("python -m pyright -p pyrightconfig.gate.json")
    assert displays.index("python -m pyright -p pyrightconfig.gate.json") < displays.index(tool_pyright_display)
    assert displays.index(tool_pyright_display) < displays.index(
        "python -m pytest -q tests/gate_meta/test_architecture_fitness.py"
    )
    assert displays.index("guard_preflight") < displays.index(
        "python -m pytest -q tests/gate_meta/test_architecture_fitness.py"
    )
    assert displays.index("python -m pytest -q tests/gate_meta/test_architecture_fitness.py") < displays.index(
        "python scripts/sync_debt_ledger.py check"
    )
    assert displays.index(required_display) < displays.index(
        "python scripts/sync_debt_ledger.py check"
    )
    assert displays.index("guard_preflight") < displays.index(required_display)
    assert displays.index(required_display) < displays.index(
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
    monkeypatch.setattr(module, "_assert_pyright_tools_coverage", lambda: None)

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append((display, list(args), bool(capture_output)))
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/gate_meta/test_run_quality_gate.py::test_main_executes_every_shared_command_when_plan_inserts_preflight\n"
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
    full_debt_display = "python tools/check_full_test_debt.py --sharded --shard-count 3"
    full_debt_command = command_plan[displays.index(full_debt_display)]

    assert displays.index("python -m pytest --collect-only -q tests") < displays.index(full_debt_display)
    assert displays.index(full_debt_display) < displays.index("python -m ruff --version")
    assert full_debt_command["args"] == ["python", "tools/check_full_test_debt.py", "--sharded", "--shard-count", "3"]
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
        "scripts/run_daily_quality_gate.py",
        "tools/fast_static_precheck.py",
        "tools/git_hook_blocked_paths.py",
        "tools/git_hook_cache.py",
        "tools/check_full_test_debt.py",
        "tools/collect_full_test_debt.py",
        "tools/verify_required_regressions_from_full_test_debt.py",
        "tools/git_hook_checks.py",
        "tools/test_debt_registry.py",
        "tools/test_registry.py",
        "tools/long_gate_cache.py",
        "tools/long_gate_collect.py",
        "tools/long_gate_fingerprint.py",
        "tools/long_gate_manifest.py",
        "tools/long_gate_paths.py",
        "tools/long_gate_schema.py",
        "tools/long_gate_summary.py",
        "tests/conftest.py",
        "tests/gate_meta/test_check_full_test_debt.py",
        "tests/gate_meta/test_full_test_debt_registry_contract.py",
        "tests/gate_meta/test_architecture_fitness.py",
        "tests/gate_meta/check_quickref_vs_routes.py",
        "pyproject.toml",
        "开发文档/技术债务治理台账.md",
    ]:
        assert rel_path in source_paths

    tool_paths = set(shared.QUALITY_GATE_TOOL_PATHS)
    for rel_path in [
        "scripts/run_daily_quality_gate.py",
        "tools/fast_static_precheck.py",
        "tools/git_hook_blocked_paths.py",
        "tools/git_hook_cache.py",
        "tools/check_full_test_debt.py",
        "tools/collect_full_test_debt.py",
        "tools/verify_required_regressions_from_full_test_debt.py",
        "tools/git_hook_checks.py",
        "tools/test_debt_registry.py",
        "tools/test_registry.py",
        "tools/long_gate_cache.py",
        "tools/long_gate_collect.py",
        "tools/long_gate_fingerprint.py",
        "tools/long_gate_manifest.py",
        "tools/long_gate_paths.py",
        "tools/long_gate_schema.py",
        "tools/long_gate_summary.py",
        "tests/conftest.py",
    ]:
        assert rel_path in tool_paths

    assert "tools/check_full_test_debt.py" in " ".join(displays)
    assert tuple(module.REQUIRED_TEST_ARGS) == tuple(shared.iter_quality_gate_required_tests())


def test_quality_gate_receipt_proof_requires_execution_mode_fields() -> None:
    shared = _shared_quality_registry()
    command = _small_quality_gate_plan()[0]
    stdout = "tests/gate_meta/test_run_quality_gate.py::test_quality_gate_receipt_proof_requires_execution_mode_fields\n"
    payload = shared.build_quality_gate_command_receipt(
        command,
        run_id="run-1",
        command_index=1,
        returncode=0,
        stdout=stdout,
        stderr="",
        stdout_log_path="evidence/QualityGate/logs/collect.stdout.log",
        stderr_log_path="evidence/QualityGate/logs/collect.stderr.log",
    )
    payload.update({"execution_mode": "executed", "timed_out": False, "interrupted": False, "partial_write": False})

    assert (
        shared._verify_quality_gate_receipt_payload(
            payload,
            command,
            index=1,
            run_id="run-1",
            current_collect_stdout=stdout,
            current_collect_stderr="",
        )
        is None
    )

    missing_mode = dict(payload)
    missing_mode.pop("execution_mode")
    assert (
        shared._verify_quality_gate_receipt_payload(
            missing_mode,
            command,
            index=1,
            run_id="run-1",
            current_collect_stdout=stdout,
            current_collect_stderr="",
        )
        == "UNBOUND: quality gate command receipt execution_mode mismatch"
    )

    bad_reuse = dict(payload)
    bad_reuse["execution_mode"] = "reused_success_cache"
    bad_reuse["reused_from"] = {}
    assert (
        shared._verify_quality_gate_receipt_payload(
            bad_reuse,
            command,
            index=1,
            run_id="run-1",
            current_collect_stdout=stdout,
            current_collect_stderr="",
        )
        == "UNBOUND: quality gate command receipt reused_from result_path missing"
    )


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
    monkeypatch.setattr(module, "_assert_pyright_tools_coverage", lambda: None)

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/gate_meta/test_run_quality_gate.py::test_main_fails_when_required_command_proof_is_missing\n"
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
    assert "tests/app_runtime/test_entrypoint_meta_failure_visible.py" in module.STARTUP_REGRESSION_ARGS
    assert "tests/app_runtime/test_launcher_observability.py" in module.STARTUP_REGRESSION_ARGS
    for high_value_path in (
        "tests/scheduler_analysis/test_scheduler_analysis_observability.py",
        "tests/web_pages/test_system_history_route_contract.py",
        "tests/resource_dispatch/test_scheduler_resource_dispatch_invalid_query_cleanup.py",
        "tests/schedule/summary/test_schedule_summary_input_fallback_contract.py",
        "tests/web_pages/test_error_boundary_contract.py",
        "tests/schedule/route_view/test_route_version_normalizers_contract.py",
        "tests/gantt/test_gantt_page_version_default_latest.py",
        "tests/gantt/test_gantt_default_version_span.py",
        "tests/gantt/test_gantt_adjustment_draft_model.py",
        "tests/gantt/test_gantt_adjustment_validate_simulate.py",
        "tests/gantt/test_gantt_draft_save_and_preview.py",
        "tests/gantt/test_gantt_scenario_publish.py",
        "tests/web_pages/test_scenario_preview_secondary_outputs.py",
        "tests/web_pages/test_reports_page_version_default_latest.py",
        "tests/gantt/test_gantt_degradation_surface.py",
        "tests/gantt/test_gantt_frontend_error_boundary.py",
        "tests/schedule/route_view/test_scheduler_result_navigation_contract.py",
        "tests/gantt/test_gantt_contract_snapshot.py",
        "tests/gantt/test_gantt_critical_chain_unavailable.py",
        "tests/gantt/test_gantt_critical_chain_provider.py",
        "tests/gantt/test_scheduler_candidate_gantt_plan_role_contract.py",
        "tests/gate_meta/test_quality_gate_scan_contract.py",
        "tests/gate_meta/test_codestable_architecture_contract.py",
        "tests/schedule/route_view/test_scheduler_batch_template_warning_surface.py",
        "tests/schedule/route_view/test_scheduler_run_view_result_contract.py",
        "tests/resource_dispatch/test_resource_dispatch_bad_time_rows_surface_degraded.py",
        "tests/resource_dispatch/test_resource_dispatch_export_surfaces_degraded.py",
        "tests/resource_dispatch/test_resource_dispatch_public_output_contract.py",
        "tests/resource_dispatch/test_resource_dispatch_viewmodel_public_output_contract.py",
        "tests/resource_dispatch/test_resource_dispatch_overdue_summary_formats.py",
        "tests/resource_dispatch/test_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py",
        "tests/app_runtime/test_ui_browser_geometry_env.py",
        "tests/app_runtime/test_ui_geometry_html_contract.py",
        "tests/schedule/route_view/test_scheduler_route_enforce_ready_tristate.py",
        "tests/gate_meta/test_run_full_selftest_report_metadata.py",
        "tests/calendar_maintenance/test_holiday_default_efficiency_read_guard.py",
        "tests/excel_data_io/test_excel_import_hardening.py",
        "tests/excel_data_io/test_excel_utils_compare_digest_guard.py",
        "tests/excel_data_io/test_excel_conversion_output_contract.py",
        "tests/excel_data_io/test_excel_hidden_payload_contract.py",
        "tests/app_runtime/test_frontend_offline_static_assets.py",
        "tests/excel_data_io/test_excel_renamed_column_conflicts.py",
        "tests/excel_data_io/test_scheduler_excel_batches_preview_baseline_precision.py",
        "tests/gate_meta/test_check_full_test_debt.py",
        "tests/gate_meta/test_full_test_debt_registry_contract.py",
        "tests/web_pages/test_request_services_contract.py",
        "tests/web_pages/test_factory_request_lifecycle_observability.py",
        "tests/calendar_maintenance/test_maintenance_window_mutex.py",
        "tests/migration_db/test_database_high_version_failfast.py",
        "tests/algorithm/test_optimizer_outcome_type_contract.py",
        "tests/algorithm/test_optimizer_public_summary_projection_contract.py",
        "tests/algorithm/test_optimizer_runtime_seam_contract.py",
        "tests/algorithm/test_optimizer_seed_boundary_contract.py",
        "tests/schedule/summary/test_schedule_summary_invalid_due_and_unscheduled_counts.py",
        "tests/schedule/summary/test_schedule_summary_overdue_warning_append_fallback.py",
        "tests/config/test_schedule_config_snapshot_optional_guard.py",
        "tests/schedule/summary/test_schedule_summary_freeze_state_contract.py",
        "tests/gate_meta/test_git_hook_checks.py",
        "tests/gate_meta/test_long_gate_cli_controls.py",
        "tests/gate_meta/test_long_gate_quickref_cache.py",
        "tests/schedule/service/test_schedule_template_lookup_contract.py",
    ):
        assert high_value_path in module.REQUIRED_TEST_ARGS

    for lower_frequency_path in (
        "tests/gantt/test_gantt_critical_outline_sync.py",
        "tests/app_runtime/test_ui_browser_geometry_smoke.py",
        "tests/gate_meta/test_long_gate_required_regression_cache.py",
        "tests/gate_meta/test_sync_debt_ledger.py",
        "tests/schedule/route_view/test_scheduler_batches_page_viewmodel.py",
        "tests/config/test_config_manual_markdown.py",
        "tests/web_pages/test_frontend_ui_language_polish.py",
        "tests/web_pages/test_manual_entry_scope.py",
        "tests/web_pages/test_page_manual_registry.py",
        "tests/excel_data_io/test_excel_template_contract.py",
        "tests/web_pages/test_reports_export_version_default_latest.py",
    ):
        assert lower_frequency_path not in module.REQUIRED_TEST_ARGS

    command_plan = shared.build_quality_gate_command_plan()
    displays = [str(command["display"]) for command in command_plan]
    required_display = "python tools/verify_required_regressions_from_full_test_debt.py"
    startup_display = "python -m pytest -q " + " ".join(startup_from_registry)
    assert required_display in displays
    assert startup_display in displays
    assert displays.index(required_display) < displays.index("python scripts/sync_debt_ledger.py check")
    assert displays.index("python scripts/sync_debt_ledger.py check") < displays.index(startup_display)


def test_browser_required_env_overlay_is_in_shared_quality_gate_plan() -> None:
    shared = _shared_quality_registry()
    command_plan = shared.build_quality_gate_command_plan()
    displays = [str(command["display"]) for command in command_plan]
    full_debt = command_plan[displays.index("python tools/check_full_test_debt.py --sharded --shard-count 3")]
    required_display = "python tools/verify_required_regressions_from_full_test_debt.py"
    required = command_plan[displays.index(required_display)]

    for command in (full_debt, required):
        assert command["env_overlay"]["APS_BROWSER_SMOKE_REQUIRED"] == "1"
        assert command["env_overlay"]["PYTHONDONTWRITEBYTECODE"] == "1"
        assert command["env_overlay"]["PYTHONUTF8"] == "1"
        assert command["env_overlay"]["PYTHONIOENCODING"] == "utf-8"

    changed_required = dict(required)
    changed_required["env_overlay"] = dict(required["env_overlay"], APS_BROWSER_SMOKE_REQUIRED="0")
    assert shared.hash_quality_gate_commands([required]) != shared.hash_quality_gate_commands([changed_required])


def test_run_quality_gate_passes_env_overlay_to_required_commands(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])

    seen_env = {}

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        seen_env[str(display)] = dict(env_overlay or {})
        return _successful_result_for_display(str(display))

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main([]) == 0

    full_debt_display = "python tools/check_full_test_debt.py --sharded --shard-count 3"
    required_display = "python tools/verify_required_regressions_from_full_test_debt.py"
    assert seen_env[full_debt_display]["APS_BROWSER_SMOKE_REQUIRED"] == "1"
    assert seen_env[required_display]["APS_BROWSER_SMOKE_REQUIRED"] == "1"
    assert seen_env["python -m ruff --version"] == {}


def test_quality_workflow_uploads_quality_gate_manifest_artifact():
    workflow = Path(_repo_root()) / ".github" / "workflows" / "quality.yml"
    content = workflow.read_text(encoding="utf-8")

    assert "actions/upload-artifact" in content
    assert "evidence/QualityGate/" in content
    assert "--require-clean-worktree" in content
    assert "--long-gate-cache" in content
    quality_gate_job = re.search(r"(?ms)^  quality-gate:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", content)
    assert quality_gate_job is not None
    assert re.search(r"(?m)^    env:\s*$", quality_gate_job.group("body"))
    assert re.search(r"(?m)^      PYTHONDONTWRITEBYTECODE:\s*['\"]?1['\"]?\s*$", quality_gate_job.group("body"))
    assert re.search(r"(?m)^      PYTHONUTF8:\s*['\"]?1['\"]?\s*$", quality_gate_job.group("body"))
    assert re.search(r"(?m)^      PYTHONIOENCODING:\s*['\"]?utf-8['\"]?\s*$", quality_gate_job.group("body"))
    assert "安装 Node.js 24" in quality_gate_job.group("body")
    chrome_check_index = quality_gate_job.group("body").index("Test-Path $env:APS_CHROME_PATH")
    chrome_version_index = quality_gate_job.group("body").index("& $env:APS_CHROME_PATH --version")
    gate_run = "run: python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache"
    gate_run_index = quality_gate_job.group("body").index(gate_run)
    assert chrome_check_index < chrome_version_index < gate_run_index
    assert "node-version: '24'" in quality_gate_job.group("body")


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
    monkeypatch.setattr(module, "_assert_pyright_tools_coverage", lambda: None)

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/gate_meta/test_run_quality_gate.py::test_quality_gate_receipts\n"
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
        "evidence/QualityGate/collect_nodeids.json",
        "evidence/QualityGate/current_full_test_debt.json",
        "evidence/QualityGate/full_test_debt_summary.json",
        "evidence/QualityGate/architecture_scan_cache.json",
        "evidence/QualityGate/startup_runtime_regressions.json",
        "evidence/QualityGate/required_regressions.json",
        "evidence/QualityGate/required_regressions/",
        "evidence/QualityGate/debt_ledger_sync.json",
        "evidence/QualityGate/ruff_check_full.json",
        "evidence/QualityGate/pyright_gate_full.json",
        "evidence/QualityGate/pyright_tools_full.json",
        "evidence/QualityGate/quickref_vs_routes.md",
    ]
    assert len(manifest["command_receipts"]) == len(manifest["commands"])


@pytest.mark.parametrize(
    ("entry_id", "display", "args", "proof_rel"),
    [
        (
            "ruff_check_full",
            "python -m ruff check",
            ["python", "-m", "ruff", "check"],
            "evidence/QualityGate/ruff_check_full.json",
        ),
        (
            "pyright_gate_full",
            "python -m pyright -p pyrightconfig.gate.json",
            ["python", "-m", "pyright", "-p", "pyrightconfig.gate.json"],
            "evidence/QualityGate/pyright_gate_full.json",
        ),
        (
            "pyright_tools_full",
            "python -m pyright -p pyrightconfig.tools.json",
            ["python", "-m", "pyright", "-p", "pyrightconfig.tools.json"],
            "evidence/QualityGate/pyright_tools_full.json",
        ),
    ],
)
def test_prepare_long_gate_success_output_files_writes_static_proof(monkeypatch, tmp_path, entry_id, display, args, proof_rel):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    entry = {
        "entry_id": entry_id,
        "display": display,
        "args": args,
        "command_hash": "command-hash",
        "capture_output": False,
        "output_policy": "normalized",
        "fingerprint_schema_version": 1,
    }
    result = {
        "stdout": "ok\n",
        "stderr": "",
        "returncode": 0,
        "execution_mode": "executed",
        "duration_s": 1.25,
    }
    command_plan = [
        {
            "display": display,
            "args": args,
            "capture_output": False,
            "output_policy": "normalized",
        }
    ]

    output_files = module._prepare_long_gate_success_output_files(
        entry,
        result,
        cache_dir="evidence/QualityGate/long_gate",
        run_id="run-static",
        command_index=4,
        command_plan=command_plan,
        fingerprint={"hash": "fingerprint-hash"},
    )

    assert output_files == [proof_rel]
    proof = module.json.loads((repo_root / proof_rel).read_text(encoding="utf-8"))
    assert proof["status"] == "passed"
    assert proof["entry_id"] == entry_id
    assert proof["head_sha"] == "deadbeef"
    assert proof["run_id"] == "run-static"
    assert proof["fingerprint_hash"] == "fingerprint-hash"
    assert proof["command_hash"] == "command-hash"
    assert proof["returncode"] == 0
    assert proof["does_not_claim"] == "clean_worktree_proof"
    assert proof["stdout_log_path"] == f"evidence/QualityGate/long_gate/logs/{entry_id}.stdout.log"
    assert proof["stderr_log_path"] == f"evidence/QualityGate/long_gate/logs/{entry_id}.stderr.log"
    assert proof["logs"]["stdout"]["sha256"] == proof["stdout_sha256"]
    assert proof["logs"]["stderr"]["sha256"] == proof["stderr_sha256"]
    if entry_id == "pyright_gate_full":
        assert proof["config_path"] == "pyrightconfig.gate.json"
    if entry_id == "pyright_tools_full":
        assert proof["config_path"] == "pyrightconfig.tools.json"
        assert proof["tool_paths"] == list(_shared_quality_registry().QUALITY_GATE_TOOL_PATHS)
        assert proof["tool_path_count"] == len(_shared_quality_registry().QUALITY_GATE_TOOL_PATHS)
        assert proof["tool_paths_hash"] == module.stable_json_hash(list(_shared_quality_registry().QUALITY_GATE_TOOL_PATHS))


def test_pyright_tools_coverage_requires_all_tool_paths(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / module.PYRIGHT_TOOLS_CONFIG).write_text(
        module.json.dumps({"include": module.QUALITY_GATE_TOOL_PATHS}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = list(args)
        seen["cwd"] = kwargs.get("cwd")
        return SimpleNamespace(
            returncode=0,
            stdout=module.json.dumps(
                {
                    "summary": {
                        "filesAnalyzed": len(module.QUALITY_GATE_TOOL_PATHS),
                        "errorCount": 0,
                        "warningCount": 0,
                    }
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module._assert_pyright_tools_coverage()

    assert seen["cwd"] == str(repo_root)
    assert seen["args"][-3:] == ["-p", module.PYRIGHT_TOOLS_CONFIG, "--outputjson"]


def test_pyright_tools_coverage_rejects_empty_coverage(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / module.PYRIGHT_TOOLS_CONFIG).write_text(
        module.json.dumps({"include": module.QUALITY_GATE_TOOL_PATHS}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))

    def fake_run(_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=module.json.dumps({"summary": {"filesAnalyzed": 2, "errorCount": 0, "warningCount": 0}}),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(module.QualityGateError, match="pyright tools 覆盖不足"):
        module._assert_pyright_tools_coverage()


def test_pyright_tools_coverage_rejects_config_that_does_not_match_tool_paths(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / module.PYRIGHT_TOOLS_CONFIG).write_text(
        module.json.dumps({"include": ["tools/long_gate_manifest.py"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))

    def fake_run(_args, **_kwargs):
        raise AssertionError("pyright should not run when config include is stale")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(module.QualityGateError, match="include 与 QUALITY_GATE_TOOL_PATHS 不一致"):
        module._assert_pyright_tools_coverage()


def test_repository_pyright_tools_config_matches_quality_gate_tool_paths():
    module = _import_run_quality_gate()

    module._assert_pyright_tools_config_matches_tool_paths()


def test_pyright_tools_reused_cache_validates_config_without_rerunning_pyright(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / module.PYRIGHT_TOOLS_CONFIG).write_text(
        module.json.dumps({"include": module.QUALITY_GATE_TOOL_PATHS}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(
        module,
        "_assert_pyright_tools_coverage",
        lambda: (_ for _ in ()).throw(AssertionError("reused cache should not rerun pyright coverage")),
    )

    assert module._handle_pyright_tools_quality_gate_command(
        f"python -m pyright -p {module.PYRIGHT_TOOLS_CONFIG}",
        {"stdout": "", "stderr": "", "returncode": 0, "execution_mode": "reused_success_cache"},
    ) == {}


@pytest.mark.parametrize(
    ("entry_id", "display", "args", "proof_rel"),
    [
        (
            "ruff_check_full",
            "python -m ruff check",
            ["python", "-m", "ruff", "check"],
            "evidence/QualityGate/ruff_check_full.json",
        ),
        (
            "pyright_tools_full",
            "python -m pyright -p pyrightconfig.tools.json",
            ["python", "-m", "pyright", "-p", "pyrightconfig.tools.json"],
            "evidence/QualityGate/pyright_tools_full.json",
        ),
    ],
)
def test_run_quality_gate_command_plan_prepares_enabled_static_proof_before_pending_success(
    monkeypatch, tmp_path, entry_id, display, args, proof_rel
):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    command = {
        "display": display,
        "args": args,
        "capture_output": False,
        "output_policy": "normalized",
    }
    manifest = module.build_manifest_from_quality_gate_plan([command], repo_root=str(repo_root))
    entry = next(item for item in manifest["entries"] if item["entry_id"] == entry_id)
    entry = dict(entry)
    entry["reuse_allowed"] = True
    entry["cache_status"] = "enabled"
    pending_successes = []
    runtime_entries = {
        display: {
            "entry": entry,
            "fingerprint": {"hash": "fingerprint-hash"},
            "evaluation": {},
            "decision": {"decision": "run", "reason": "no previous success cache"},
            "summary_entry": {},
        }
    }
    monkeypatch.setattr(
        module,
        "_run_command_with_env_overlay",
        lambda *args, **kwargs: {"stdout": "static ok\n", "stderr": "", "returncode": 0},
    )
    monkeypatch.setattr(module, "_assert_pyright_tools_coverage", lambda: None)

    module._run_quality_gate_command_plan(
        [command],
        run_id="run-static",
        commands=[],
        command_receipts=[],
        parsed_command_results={},
        long_gate_cache=True,
        long_gate_cache_write_success=True,
        long_gate_cache_dir="evidence/QualityGate/long_gate",
        long_gate_runtime_entries=runtime_entries,
        long_gate_failure={},
        pending_long_gate_successes=pending_successes,
    )

    proof_path = repo_root / proof_rel
    assert proof_path.is_file()
    proof = module.json.loads(proof_path.read_text(encoding="utf-8"))
    assert proof["entry_id"] == entry_id
    assert proof["does_not_claim"] == "clean_worktree_proof"
    assert pending_successes[0]["output_files"] == [str(proof_path)]


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

    monkeypatch.setattr(module, "_guard_test_exists", lambda path: path != "tests/gate_meta/test_sp05_path_topology_contract.py")
    monkeypatch.setattr(module, "_guard_test_tracked", lambda _path: True)

    with pytest.raises(module.QualityGateError) as exc_info:
        module._assert_guard_tests_ready()

    assert "missing=tests/gate_meta/test_sp05_path_topology_contract.py" in str(exc_info.value)


def test_guard_preflight_rejects_untracked_guard_file(monkeypatch):
    module = _import_run_quality_gate()

    monkeypatch.setattr(module, "_guard_test_exists", lambda _path: True)
    monkeypatch.setattr(
        module,
        "_guard_test_tracked",
        lambda path: path != "tests/schedule/service/test_schedule_input_builder_strict_hours_and_ext_days.py",
    )

    with pytest.raises(module.QualityGateError) as exc_info:
        module._assert_guard_tests_ready()

    assert "untracked=tests/schedule/service/test_schedule_input_builder_strict_hours_and_ext_days.py" in str(exc_info.value)


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
    monkeypatch.setattr(module, "_assert_pyright_tools_coverage", lambda: None)
    monkeypatch.setattr(
        module,
        "_repo_identity",
        lambda: {
            "checkout_root_realpath": str((repo_root / "checkout").resolve()),
            "git_common_dir_realpath": str((repo_root / ".git").resolve()),
        },
    )

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "\n".join(
                [
                    "tests/gate_meta/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks",
                    "tests/gate_meta/test_sp05_path_topology_contract.py::test_scheduler_route_topology",
                    "tests/web_pages/test_system_history_route_contract.py::test_system_history_route_uses_request_services",
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
        assert receipt_payload["execution_mode"] == "executed"
        assert receipt_payload["reused_from"] == {}
        assert receipt_payload["started_at"]
        assert receipt_payload["ended_at"]
        assert receipt_payload["duration_s"] >= 0
        assert receipt_payload["duration_kind"] == "executed"
    assert "scripts/run_quality_gate.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/quality_gate_entries.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/quality_gate_ledger.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/quality_gate_scan.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/quality_gate_operations.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "scripts/sync_debt_ledger.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/test_registry.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/git_hook_blocked_paths.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/long_gate_cache.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/long_gate_collect.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/long_gate_fingerprint.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/long_gate_manifest.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/long_gate_paths.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/long_gate_schema.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/long_gate_summary.py" in {item["path"] for item in manifest["gate_sources"]}
    assert "tools/long_gate_full_test_debt.py" in {item["path"] for item in manifest["gate_sources"]}
    assert ".github/workflows/quality.yml" in {item["path"] for item in manifest["gate_sources"]}
    assert "pyproject.toml" in {item["path"] for item in manifest["gate_sources"]}
    assert manifest["collection_proof"]["default_collect_nodeids"]
    assert manifest["collection_proof"]["collected_count"] == 3
    quality_gate_entry = next(
        item for item in manifest["collection_proof"]["key_tests"] if item["path"] == "tests/gate_meta/test_run_quality_gate.py"
    )
    assert quality_gate_entry["execution_mode"] == "default_collect"
    regression_entry = next(
        item
        for item in manifest["collection_proof"]["key_tests"]
        if item["path"] == "tests/web_pages/test_system_history_route_contract.py"
    )
    assert regression_entry["execution_mode"] == "default_collect"


def test_collect_only_success_prints_count_without_nodeids(capsys):
    module = _import_run_quality_gate()

    result = module._run_command(
        module.PYTEST_COLLECT_ALL_DISPLAY,
        [sys.executable, "-c", "print('tests/test_sample.py::test_a')"],
        capture_output=True,
    )

    captured = capsys.readouterr()
    assert result["returncode"] == 0
    assert result["stdout"] == "tests/test_sample.py::test_a\n"
    assert captured.out.strip() == "collected_count=1"
    assert "tests/test_sample.py::test_a" not in captured.out


def test_collect_only_handler_rejects_empty_stdout() -> None:
    module = _import_run_quality_gate()

    with pytest.raises(module.QualityGateError, match="没有任何 test nodeid"):
        module._handle_collect_quality_gate_command(
            module.PYTEST_COLLECT_ALL_DISPLAY,
            {"stdout": "", "stderr": "", "returncode": 0},
        )


def test_collect_only_handler_rejects_summary_without_nodeids() -> None:
    module = _import_run_quality_gate()

    with pytest.raises(module.QualityGateError, match="没有任何 test nodeid"):
        module._handle_collect_quality_gate_command(
            module.PYTEST_COLLECT_ALL_DISPLAY,
            {"stdout": "2592 tests collected in 0.67s\n", "stderr": "", "returncode": 0},
        )


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
    assert "tests/scheduler_analysis/test_scheduler_analysis_observability.py::test_scheduler_analysis_observability" in output
    assert "tests/web_pages/test_system_history_route_contract.py::test_system_history_route_uses_request_services" in output
    assert (
        "tests/algorithm/test_auto_assign_persist_truthy_variants.py::"
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
    monkeypatch.setattr(module, "_assert_pyright_tools_coverage", lambda: None)

    calls = []

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append((display, list(args), bool(capture_output)))
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/gate_meta/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound\n"
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree"]) == 2
    output = capsys.readouterr().out
    assert "passed_but_unbound" in output
    assert "质量门禁通过" not in output
    full_debt_call = next(call for call in calls if call[0].startswith("python tools/check_full_test_debt.py"))
    assert full_debt_call[0].endswith(" --allow-dirty-worktree-proof")
    assert "--allow-dirty-worktree-proof" in full_debt_call[1]

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
    monkeypatch.setattr(module, "_assert_pyright_tools_coverage", lambda: None)

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/gate_meta/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest\n"
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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
    for receipt_index in range(manifest["resume"]["skip_count"]):
        receipt_payload = _load_receipt_payload(module, repo_root, manifest, receipt_index)
        assert receipt_payload["execution_mode"] == "resumed_success_prefix"
        assert receipt_payload["reused_from"]["run_id"] == "old-run"
        assert receipt_payload["duration_kind"] == "resume_overhead"
        assert receipt_payload["original_duration_s"] >= 0


def test_main_long_gate_cache_explain_prints_decision_without_running(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    command_plan = _small_quality_gate_plan()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("quality gate command should not run in explain mode")

    monkeypatch.setattr(module, "_run_command", fail_if_called)

    assert module.main(["--long-gate-cache-explain"]) == 0

    output = capsys.readouterr().out
    assert "Long gate cache decisions" in output
    assert "explain mode prints decisions only; it is not a quality gate proof" in output
    assert "- pytest_collect_all: RUN" in output
    assert "no previous success cache" in output
    assert not (repo_root / "evidence" / "QualityGate" / "long_gate" / "summary.json").exists()
    assert not (repo_root / "evidence" / "QualityGate" / "receipts").exists()


def test_long_gate_cache_explain_and_no_cache_are_mutually_exclusive():
    module = _import_run_quality_gate()

    with pytest.raises(SystemExit):
        module._parse_args(["--long-gate-cache-explain", "--no-long-gate-cache"])


def test_main_long_gate_impact_explain_prints_json_without_writing_proof(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("impact explain must not execute quality gate commands")

    monkeypatch.setattr(module, "_run_command", fail_if_called)

    assert module.main(["--long-gate-impact-explain", "--long-gate-impact-path", "tools/git_hook_checks.py"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "long_gate_impact_explain"
    assert payload["changed_paths"] == ["tools/git_hook_checks.py"]
    assert "entries" in payload
    assert not (repo_root / "evidence" / "QualityGate" / "long_gate" / "summary.json").exists()
    assert not (repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json").exists()
    assert not (repo_root / "evidence" / "QualityGate" / "receipts").exists()


def test_long_gate_impact_explain_rejects_cache_flags():
    module = _import_run_quality_gate()

    with pytest.raises(SystemExit):
        module._parse_args(["--long-gate-impact-explain", "--long-gate-cache"])


def test_main_fast_precheck_returns_before_full_quality_gate_plan(monkeypatch):
    module = _import_run_quality_gate()
    from tools import fast_static_precheck

    calls = []
    monkeypatch.setattr(fast_static_precheck, "main", lambda argv: calls.append(list(argv)) or 7)
    monkeypatch.setattr(
        module,
        "build_quality_gate_command_plan",
        lambda: (_ for _ in ()).throw(AssertionError("full quality gate plan should not be built")),
    )
    monkeypatch.setattr(
        module,
        "write_long_gate_success",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("success cache should not be written")),
    )
    monkeypatch.setattr(
        module,
        "_write_quality_gate_manifest",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("manifest should not be written")),
    )
    monkeypatch.setattr(
        module,
        "_write_command_receipt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("receipt should not be written")),
    )
    monkeypatch.setattr(
        module,
        "_write_and_print_long_gate_summary",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("long gate summary should not be written")),
    )

    assert module.main(["--fast-precheck"]) == 7

    assert calls == [[]]


@pytest.mark.parametrize(
    "extra_args",
    [
        ["--require-clean-worktree"],
        ["--allow-dirty-worktree"],
        ["--long-gate-cache"],
        ["--no-long-gate-cache"],
        ["--long-gate-cache-dir", "evidence/QualityGate/long_gate/manual"],
        ["--long-gate-force-rerun", "pytest_collect_all"],
        ["--long-gate-force-rerun-all"],
        ["--long-gate-cache-explain"],
        ["--long-gate-impact-explain"],
        ["--long-gate-impact-explain", "--long-gate-impact-path", "tools/git_hook_checks.py"],
        ["--no-resume"],
    ],
)
def test_fast_precheck_rejects_full_gate_and_long_gate_arguments(extra_args):
    module = _import_run_quality_gate()

    with pytest.raises(SystemExit):
        module._parse_args(["--fast-precheck", *extra_args])


def test_long_gate_cache_explain_uses_strict_fingerprint(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_quality_gate_plan())
    calls = []

    def spy_fingerprint_entry(entry, repo_root_arg, *, strict=False):
        calls.append(strict)
        return {
            "schema_version": 1,
            "hash": "sha256:test",
            "components": {"files": {"files": []}},
        }

    monkeypatch.setattr(module, "fingerprint_entry", spy_fingerprint_entry)
    monkeypatch.setattr(
        module,
        "evaluate_reuse",
        lambda entry, fingerprint, repo_root=None, cache_dir=None: {
            "decision": {
                "entry_id": "pytest_collect_all",
                "decision": "run",
                "reuse_allowed": False,
                "reason": "no previous success cache",
                "invalidated_by": [],
                "previous_completed_at": None,
                "previous_result_path": None,
                "current_fingerprint_hash": fingerprint["hash"],
            },
            "validated_success": None,
            "stdout": "",
            "stderr": "",
        },
    )

    assert module.main(["--long-gate-cache-explain"]) == 0
    assert calls == [True]


def test_long_gate_cache_explain_marks_fingerprint_error_cache_unavailable(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_quality_gate_plan())

    def fail_fingerprint(entry, repo_root_arg, *, strict=False):
        del entry, repo_root_arg
        assert strict is True
        raise module.LongGateFingerprintError(
            "Chrome headless preflight failed",
            details={
                "runtime_key": "chrome_headless_preflight",
                "failure_kind": "chrome_exited_before_devtools",
                "chrome_path": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "chrome_source": "APS_CHROME_PATH",
                "chrome_exit_code": 7,
                "stderr_tail": "profile permission denied",
            },
        )

    monkeypatch.setattr(module, "fingerprint_entry", fail_fingerprint)
    monkeypatch.setattr(
        module,
        "evaluate_reuse",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("reuse must not be evaluated")),
    )

    assert module.main(["--long-gate-cache-explain"]) == 0

    output = capsys.readouterr().out
    assert "- pytest_collect_all: RUN" in output
    assert "cache: cache_unavailable" in output
    assert "runtime_key: chrome_headless_preflight" in output
    assert "failure_kind: chrome_exited_before_devtools" in output
    assert "cache unavailable for this entry" in output
    assert "profile permission denied" in output


def test_final_gate_fingerprint_error_runs_command_without_success_cache(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_quality_gate_plan())

    def fail_fingerprint(entry, repo_root_arg, *, strict=False):
        del entry, repo_root_arg
        assert strict is True
        raise module.LongGateFingerprintError(
            "Chrome headless preflight failed",
            details={
                "runtime_key": "chrome_headless_preflight",
                "failure_kind": "chrome_exited_before_devtools",
            },
        )

    calls = []

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        del args, capture_output, env_overlay
        calls.append(display)
        return _successful_result_for_display(display)

    monkeypatch.setattr(module, "fingerprint_entry", fail_fingerprint)
    monkeypatch.setattr(
        module,
        "evaluate_reuse",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("reuse must not be evaluated")),
    )
    monkeypatch.setattr(
        module,
        "write_long_gate_success",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("success cache must not be written")),
    )
    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--require-clean-worktree", "--long-gate-cache"]) == 0

    output = capsys.readouterr().out
    assert "strict fingerprint 失败，该 entry 当前 cache unavailable" in output
    assert calls == [
        "python -m pytest --collect-only -q tests",
        "python -m ruff --version",
        "python -m pyright --version",
        "python tools/failing_command.py",
    ]
    summary = _load_long_gate_summary(module, repo_root)
    collect = next(entry for entry in summary["entries"] if entry["entry_id"] == module.ENTRY_PYTEST_COLLECT_ALL)
    assert collect["cache_status"] == "cache_unavailable"
    assert collect["decision"] == "run"
    assert collect["cache_unavailable"] is True
    assert collect["fingerprint_error"]["runtime_key"] == "chrome_headless_preflight"
    assert collect["execution_mode"] == "executed"
    assert not (repo_root / "evidence" / "QualityGate" / "long_gate" / "results").exists()


def test_main_long_gate_cache_reuses_collect_only_success(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    original_plan_hash = module.hash_quality_gate_commands(command_plan)
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    calls = []

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append(display)
        if display == "python -m ruff --version":
            return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
        if display == "python -m pyright --version":
            return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
        if display == "python -m pytest --collect-only -q tests":
            return {
                "stdout": "tests/gate_meta/test_run_quality_gate.py::test_main_long_gate_cache_reuses_collect_only_success\n",
                "stderr": "",
                "returncode": 0,
            }
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--long-gate-cache"]) == 0
    first_run_calls = list(calls)
    assert "python -m pytest --collect-only -q tests" in first_run_calls
    collect_payload = module.json.loads(
        (repo_root / "evidence" / "QualityGate" / "collect_nodeids.json").read_text(encoding="utf-8")
    )
    assert collect_payload["nodeids"] == [
        "tests/gate_meta/test_run_quality_gate.py::test_main_long_gate_cache_reuses_collect_only_success"
    ]
    assert collect_payload["nodeid_hash"]
    assert collect_payload["collect_stdout_log_path"].startswith("evidence/QualityGate/logs/")
    success_cache = module.json.loads(
        (
            repo_root
            / "evidence"
            / "QualityGate"
            / "long_gate"
            / "results"
            / "pytest_collect_all.success.json"
        ).read_text(encoding="utf-8")
    )
    assert success_cache["output_files"] == [
        {
            "path": "evidence/QualityGate/collect_nodeids.json",
            "sha256": module._sha256_file(str(repo_root / "evidence" / "QualityGate" / "collect_nodeids.json")),
        }
    ]
    first_summary = _load_long_gate_summary(module, repo_root)
    first_collect_summary = next(entry for entry in first_summary["entries"] if entry["entry_id"] == "pytest_collect_all")
    assert first_collect_summary["execution_mode"] == "executed"
    assert first_collect_summary["receipt_path"] == _load_manifest(module, repo_root)["command_receipts"][0]["path"]
    assert first_collect_summary["current_fingerprint_hash"]
    assert first_collect_summary["output_files"][0]["path"] == "evidence/QualityGate/collect_nodeids.json"

    calls.clear()
    assert module.main(["--long-gate-cache"]) == 0
    assert "python -m pytest --collect-only -q tests" not in calls
    assert calls == ["python -m ruff --version", "python -m pyright --version", "python tools/failing_command.py"]

    output = capsys.readouterr().out
    assert "- pytest_collect_all: RUN" in output
    assert "- pytest_collect_all: REUSE" in output
    assert "[long-gate-reuse]" in output
    manifest = _load_manifest(module, repo_root)
    assert manifest["planned_commands_hash"] == original_plan_hash
    assert manifest["commands_hash"] == original_plan_hash
    assert [str(command["display"]) for command in manifest["commands"]] == [
        str(command["display"]) for command in command_plan
    ]
    receipt_payload = _load_receipt_payload(module, repo_root, manifest, 0)
    assert receipt_payload["execution_mode"] == "reused_success_cache"
    assert receipt_payload["reused_from"]["result_path"].endswith("pytest_collect_all.success.json")
    assert receipt_payload["reused_from"]["fingerprint_hash"]
    assert receipt_payload["duration_kind"] == "reuse_overhead"
    assert receipt_payload["original_duration_s"] >= 0
    assert receipt_payload["started_at"]
    assert receipt_payload["ended_at"]
    assert receipt_payload["duration_s"] >= 0
    assert receipt_payload["timed_out"] is False
    assert receipt_payload["interrupted"] is False
    assert receipt_payload["partial_write"] is False
    second_summary = _load_long_gate_summary(module, repo_root)
    second_collect_summary = next(entry for entry in second_summary["entries"] if entry["entry_id"] == "pytest_collect_all")
    assert second_collect_summary["execution_mode"] == "reused_success_cache"
    assert second_collect_summary["receipt_path"] == manifest["command_receipts"][0]["path"]
    assert second_collect_summary["previous_result_path"].endswith("pytest_collect_all.success.json")


def test_long_gate_reuse_uses_validated_payload_without_second_cache_read(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _write_long_gate_collect_input(repo_root)
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    _seed_collect_long_gate_success(module, command_plan, repo_root)

    def forbidden_load_previous_success(*_args, **_kwargs):
        raise AssertionError("runner must not re-read success cache after evaluate_reuse")

    monkeypatch.setattr(module, "load_previous_success", forbidden_load_previous_success, raising=False)
    calls = []

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append(display)
        if display == "python -m pytest --collect-only -q tests":
            raise AssertionError("collect-only command should be reused")
        return _successful_result_for_display(display)

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--long-gate-cache"]) == 0
    assert "python -m pytest --collect-only -q tests" not in calls


def test_main_long_gate_cache_reruns_collect_when_input_changes(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    test_path = _write_long_gate_collect_input(repo_root)
    _seed_collect_long_gate_success(module, command_plan, repo_root)
    test_path.write_text("def test_cached_collect():\n    assert 1 == 1\n", encoding="utf-8")

    calls = []

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append(display)
        if display == "python -m ruff --version":
            return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
        if display == "python -m pyright --version":
            return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
        if display == "python -m pytest --collect-only -q tests":
            return {
                "stdout": "tests/test_cached_collect.py::test_cached_collect\n",
                "stderr": "",
                "returncode": 0,
            }
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--long-gate-cache"]) == 0

    assert "python -m pytest --collect-only -q tests" in calls
    output = capsys.readouterr().out
    assert "- pytest_collect_all: RUN" in output
    assert "modified input file: tests/test_cached_collect.py" in output
    summary = _load_long_gate_summary(module, repo_root)
    collect_summary = next(entry for entry in summary["entries"] if entry["entry_id"] == "pytest_collect_all")
    assert collect_summary["decision"] == "run"
    assert "modified input file: tests/test_cached_collect.py" in collect_summary["invalidated_by"]


def test_dirty_long_gate_cache_does_not_write_success_cache(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        if display == "python -m ruff --version":
            return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
        if display == "python -m pyright --version":
            return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
        if display == "python -m pytest --collect-only -q tests":
            return {
                "stdout": "tests/test_cached_collect.py::test_cached_collect\n",
                "stderr": "",
                "returncode": 0,
            }
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree", "--long-gate-cache"]) == 2

    output = capsys.readouterr().out
    assert "跳过 long-gate success cache 写入" in output
    assert not (
        repo_root / "evidence" / "QualityGate" / "long_gate" / "results" / "pytest_collect_all.success.json"
    ).exists()
    summary = _load_long_gate_summary(module, repo_root)
    assert summary["worktree_clean"] is False
    assert summary["counts"]["executed"] == 1


def test_resume_success_prefix_wins_before_long_gate_cache(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()
    _write_long_gate_collect_input(repo_root)
    _seed_collect_long_gate_success(module, command_plan, repo_root)
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    _seed_failed_manifest_with_receipts(module, repo_root, command_plan, failed_index=4)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    calls = []

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append(display)
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--allow-dirty-worktree", "--long-gate-cache"]) == 2

    output = capsys.readouterr().out
    assert "[resume-skip]" in output
    assert "[long-gate-reuse]" not in output
    assert calls == ["python tools/failing_command.py"]
    manifest = _load_manifest(module, repo_root)
    for receipt_index in range(manifest["resume"]["skip_count"]):
        receipt_payload = _load_receipt_payload(module, repo_root, manifest, receipt_index)
        assert receipt_payload["execution_mode"] == "resumed_success_prefix"
        assert receipt_payload["duration_kind"] == "resume_overhead"
        assert receipt_payload["original_duration_s"] >= 0
        assert receipt_payload["reused_from"]["run_id"] == "old-run"
    summary = _load_long_gate_summary(module, repo_root)
    collect_summary = next(entry for entry in summary["entries"] if entry["entry_id"] == "pytest_collect_all")
    assert collect_summary["decision"] == "disabled"
    assert collect_summary["execution_mode"] == "disabled"
    assert summary["counts"]["reused"] == 0


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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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


def test_clear_stale_long_gate_output_files_keeps_reused_outputs_and_removes_run_outputs(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    run_output = repo_root / "evidence" / "QualityGate" / "quickref_vs_routes.md"
    reuse_output = repo_root / "evidence" / "QualityGate" / "debt_ledger_sync.json"
    required_parent = repo_root / "evidence" / "QualityGate" / "required_regressions.json"
    required_child = repo_root / "evidence" / "QualityGate" / "required_regressions" / "core.json"
    full_debt_output = repo_root / "evidence" / "QualityGate" / "current_full_test_debt.json"
    for path in (run_output, reuse_output, required_parent, required_child, full_debt_output):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale\n", encoding="utf-8")

    module._clear_stale_long_gate_output_files(
        {
            "quickref": {
                "entry": {
                    "entry_id": "quickref_vs_routes",
                    "output_result_files": ["evidence/QualityGate/quickref_vs_routes.md"],
                },
                "decision": {"decision": "run"},
            },
            "required": {
                "entry": {
                    "entry_id": "required_regressions",
                    "output_result_files": ["evidence/QualityGate/required_regressions.json"],
                },
                "decision": {"decision": "run"},
            },
            "debt": {
                "entry": {
                    "entry_id": "debt_ledger_sync",
                    "output_result_files": ["evidence/QualityGate/debt_ledger_sync.json"],
                },
                "decision": {"decision": "reuse"},
            },
            "full": {
                "entry": {
                    "entry_id": "full_test_debt",
                    "output_result_files": ["evidence/QualityGate/current_full_test_debt.json"],
                },
                "decision": {"decision": "run"},
            },
        },
        preserve_full_test_debt_outputs=True,
    )

    assert not run_output.exists()
    assert not required_parent.exists()
    assert not required_child.exists()
    assert reuse_output.exists()
    assert full_debt_output.exists()


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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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


@pytest.mark.skipif(
    os.name == "nt",
    reason="文件名含换行符 \\n 在 Windows 上非法（OSError [Errno 22]）；本用例验证 POSIX 下 git 引号路径指纹",
)
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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


def test_collect_only_failure_prints_stdout_and_stderr_tail(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()[:1]
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        assert display == "python -m pytest --collect-only -q tests"
        stdout = "\n".join(f"out line {index}" for index in range(1, 101))
        stderr = "\n".join(f"err line {index}" for index in range(1, 101))
        return {"stdout": stdout, "stderr": stderr, "returncode": 1}

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    with pytest.raises(module.QualityGateError) as exc_info:
        module.main(["--require-clean-worktree"])

    captured = capsys.readouterr()
    message = str(exc_info.value)
    combined = captured.out + captured.err + message
    combined_lines = set(combined.splitlines())
    assert "第 1/1 步失败" in combined
    assert "python -m pytest --collect-only -q tests" in combined
    assert "out line 100" in combined_lines
    assert "err line 100" in combined_lines
    assert "out line 1" not in combined_lines
    assert "err line 1" not in combined_lines


def test_main_preserves_failed_manifest_when_worktree_fingerprint_fails_after_command_error(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_quality_gate_plan()[:2]
    _patch_basic_gate_environment(monkeypatch, module, repo_root, statuses=[[], [" M app.py"]])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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
    monkeypatch.setattr(module, "_assert_pyright_tools_coverage", lambda: None)
    monkeypatch.setattr(module, "_run_command", lambda display, args, capture_output=False, env_overlay=None: "")

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
    monkeypatch.setattr(module, "_run_command", lambda display, args, capture_output=False, env_overlay=None: "")

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
    monkeypatch.setattr(module, "_run_command", lambda display, args, capture_output=False, env_overlay=None: "")

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
    monkeypatch.setattr(module, "_assert_pyright_tools_coverage", lambda: None)

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        if display == "python -m pyright --version":
            return "pyright 1.1.406"
        if display == "python -m pytest --collect-only -q tests":
            return "tests/gate_meta/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate\n"
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
