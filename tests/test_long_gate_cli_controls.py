from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import pytest


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def _import_run_quality_gate():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("scripts.run_quality_gate", None)
    return importlib.import_module("scripts.run_quality_gate")


def _small_plan(*, include_planned: bool = True):
    plan = [
        {
            "display": "python -m pytest --collect-only -q tests",
            "args": ["python", "-m", "pytest", "--collect-only", "-q", "tests"],
            "capture_output": True,
            "output_policy": "normalized",
        },
    ]
    if include_planned:
        plan.append(
            {
                "display": "python -m ruff check",
                "args": ["python", "-m", "ruff", "check"],
                "capture_output": False,
                "output_policy": "normalized",
            }
        )
    plan.extend(
        [
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
        ]
    )
    return plan


def _patch_gate_environment(monkeypatch, module, repo_root: Path, *, statuses: Sequence[Sequence[str]]) -> None:
    if not (repo_root / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(
        module,
        "_repo_identity",
        lambda: {
            "checkout_root_realpath": str(repo_root.resolve()),
            "git_common_dir_realpath": str((repo_root / ".git").resolve()),
        },
    )
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    status_iter = iter([list(item) for item in statuses])
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(status_iter))
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})


def _successful_result(display: str) -> dict:
    if display == "python -m pytest --collect-only -q tests":
        return {
            "stdout": "tests/test_long_gate_cli_controls.py::test_collect\n",
            "stderr": "",
            "returncode": 0,
        }
    if display == "python -m ruff --version":
        return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
    if display == "python -m pyright --version":
        return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
    return {"stdout": "", "stderr": "", "returncode": 0}


def _summary_path(repo_root: Path) -> Path:
    return repo_root / "evidence" / "QualityGate" / "long_gate" / "summary.json"


def _load_summary(repo_root: Path) -> dict:
    return json.loads(_summary_path(repo_root).read_text(encoding="utf-8"))


def _manifest_path(repo_root: Path) -> Path:
    return repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"


def _load_manifest(repo_root: Path) -> dict:
    return json.loads(_manifest_path(repo_root).read_text(encoding="utf-8"))


def _entry_by_id(summary: dict, entry_id: str) -> dict:
    for entry in summary["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError(f"missing summary entry: {entry_id}")


def _success_cache_path(repo_root: Path, *, cache_dir: str, entry_id: str = "pytest_collect_all") -> Path:
    return repo_root / cache_dir / "results" / f"{entry_id}.success.json"


def _write_collect_input(repo_root: Path) -> None:
    test_path = repo_root / "tests" / "test_cached_collect.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_cached_collect():\n    assert True\n", encoding="utf-8")


def _seed_collect_success(module, command_plan, repo_root: Path, *, cache_dir: str = "evidence/QualityGate/long_gate") -> None:
    _write_collect_input(repo_root)
    manifest = module.build_manifest_from_quality_gate_plan(command_plan, repo_root=str(repo_root))
    entry = next(row for row in manifest["entries"] if row["entry_id"] == module.ENTRY_PYTEST_COLLECT_ALL)
    fingerprint = module.fingerprint_entry(entry, str(repo_root))
    stdout = "tests/test_cached_collect.py::test_cached_collect\n"
    collect_payload = module.build_collect_nodeids_payload(
        stdout,
        pytest_version=module.pytest_distribution_version(),
        collect_stdout_log_path="evidence/QualityGate/logs/seed-collect.stdout.log",
    )
    collect_rel_path = module.write_collect_nodeids(collect_payload, repo_root=str(repo_root))
    module.write_long_gate_success(
        entry,
        fingerprint,
        {"stdout": stdout, "stderr": "", "returncode": 0, "duration_s": 8.0},
        [str(repo_root / collect_rel_path)],
        repo_root=str(repo_root),
        cache_dir=cache_dir,
    )


def test_custom_cache_dir_reads_writes_success_cache_and_summary(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cache_dir = "evidence/QualityGate/long_gate/manual"
    command_plan = _small_plan(include_planned=False)
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    _seed_collect_success(module, command_plan, repo_root)
    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result(display)

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--long-gate-cache", "--long-gate-cache-dir", cache_dir]) == 0

    summary = _load_summary(repo_root)
    collect = _entry_by_id(summary, "pytest_collect_all")
    assert summary["cache_dir"] == cache_dir
    assert collect["execution_mode"] == "executed"
    assert "python -m pytest --collect-only -q tests" in calls
    success_cache_path = _success_cache_path(repo_root, cache_dir=cache_dir)
    default_success_cache_path = _success_cache_path(repo_root, cache_dir="evidence/QualityGate/long_gate")
    assert success_cache_path.exists()
    success_cache = json.loads(success_cache_path.read_text(encoding="utf-8"))
    assert success_cache["stdout_log_path"].startswith(cache_dir + "/logs/")
    assert default_success_cache_path.exists()
    assert success_cache_path != default_success_cache_path


@pytest.mark.parametrize(
    "cache_dir",
    [
        "../outside-long-gate",
        "evidence/QualityGate/not_long_gate",
    ],
)
def test_unsafe_cache_dir_fails_without_running_commands(monkeypatch, tmp_path, cache_dir):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_plan(include_planned=False))

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("unsafe cache-dir must fail before commands run")

    monkeypatch.setattr(module, "_run_command", fail_if_called)

    with pytest.raises(module.QualityGateError, match="long gate cache dir"):
        module.main(["--long-gate-cache", "--long-gate-cache-dir", cache_dir])

    assert not _summary_path(repo_root).exists()


def test_force_rerun_entry_executes_instead_of_reusing_and_refreshes_cache(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_plan(include_planned=False)
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    _seed_collect_success(module, command_plan, repo_root)
    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result(display)

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--long-gate-cache", "--long-gate-force-rerun", "pytest_collect_all"]) == 0

    manifest = _load_manifest(repo_root)
    summary = _load_summary(repo_root)
    collect = _entry_by_id(summary, "pytest_collect_all")
    assert "python -m pytest --collect-only -q tests" in calls
    assert manifest["planned_commands"] == [module._command_identity(command) for command in command_plan]
    assert manifest["planned_commands_hash"] == module.hash_quality_gate_commands(command_plan)
    assert [str(command["display"]) for command in manifest["commands"]] == [
        str(command["display"]) for command in command_plan
    ]
    assert collect["decision"] == "run"
    assert collect["execution_mode"] == "executed"
    assert collect["reason"] == "forced by --long-gate-force-rerun pytest_collect_all"
    assert "forced by --long-gate-force-rerun pytest_collect_all" in collect["invalidated_by"]
    assert _success_cache_path(repo_root, cache_dir="evidence/QualityGate/long_gate").exists()


def test_force_all_only_invalidates_enabled_entries_and_keeps_planned_entries(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _small_plan(include_planned=True)
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    _seed_collect_success(module, command_plan, repo_root)
    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result(display)

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--long-gate-cache", "--long-gate-force-rerun-all"]) == 0

    summary = _load_summary(repo_root)
    collect = _entry_by_id(summary, "pytest_collect_all")
    planned = _entry_by_id(summary, "ruff_check_full")
    assert "python -m pytest --collect-only -q tests" in calls
    assert collect["reason"] == "forced by --long-gate-force-rerun-all"
    assert planned["cache_status"] == "planned"
    assert planned["decision"] == "planned_only"
    assert planned["execution_mode"] == "planned_only"
    assert not _success_cache_path(repo_root, cache_dir="evidence/QualityGate/long_gate", entry_id="ruff_check_full").exists()


def test_force_planned_entry_is_reported_but_does_not_enable_cache(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_plan(include_planned=True))
    calls = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        return _successful_result(display)

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--long-gate-cache", "--long-gate-force-rerun", "ruff_check_full"]) == 0

    planned = _entry_by_id(_load_summary(repo_root), "ruff_check_full")
    assert "python -m ruff check" in calls
    assert planned["cache_status"] == "planned"
    assert planned["decision"] == "planned_only"
    assert planned["reason"].endswith("force rerun ignored because planned entries are not enabled")
    assert planned["invalidated_by"] == ["force rerun ignored for planned entry"]
    assert not _success_cache_path(repo_root, cache_dir="evidence/QualityGate/long_gate", entry_id="ruff_check_full").exists()


def test_explain_prints_cache_dir_and_force_decision_without_writing_proof(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    cache_dir = "evidence/QualityGate/long_gate/manual"
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_plan(include_planned=True))

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("explain must not execute quality gate commands")

    monkeypatch.setattr(module, "_run_command", fail_if_called)

    assert (
        module.main(
            [
                "--long-gate-cache-explain",
                "--long-gate-cache-dir",
                cache_dir,
                "--long-gate-force-rerun",
                "pytest_collect_all",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "Long gate cache decisions" in output
    assert f"cache_dir: {cache_dir}" in output
    assert "- pytest_collect_all: RUN" in output
    assert "forced by --long-gate-force-rerun pytest_collect_all" in output
    assert "- ruff_check_full: PLANNED_ONLY" in output
    assert not _summary_path(repo_root).exists()
    assert not _manifest_path(repo_root).exists()
    assert not (repo_root / "evidence" / "QualityGate" / "receipts").exists()
    assert not _success_cache_path(repo_root, cache_dir=cache_dir).exists()


def test_unknown_force_rerun_entry_fails_before_running(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_plan(include_planned=False))

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("unknown force entry must fail before commands run")

    monkeypatch.setattr(module, "_run_command", fail_if_called)

    with pytest.raises(module.QualityGateError, match="未知的 long gate entry_id"):
        module.main(["--long-gate-cache", "--long-gate-force-rerun", "missing_entry"])
