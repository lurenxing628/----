"""Host-only source, receipt and hook-cache contracts; not a product gate run."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import run_daily_quality_gate as daily
from scripts import run_quality_gate as runner
from tools import git_hook_cache as hooks
from tools.long_gate_schema import content_equal


def test_runner_binds_dirty_source_and_resume_receipt_to_original_content(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(runner, "_run_git_bytes", lambda _args: b"actual diff\n")
    source = tmp_path / "input.bin"
    source.write_bytes(b"\x00same\xff")
    status = ["?? input.bin"]
    original = runner._dirty_worktree_content(status)
    source.write_bytes(b"\x00SAME\xff")
    assert not content_equal(original, runner._dirty_worktree_content(status))
    source.write_bytes(b"\x00same\xff")
    assert content_equal(original, runner._dirty_worktree_content(status))
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", ["input.bin"])
    monkeypatch.setattr(runner, "_guard_test_tracked", lambda _path: False)
    runner._assert_guard_tests_ready(require_tracked=False)
    with pytest.raises(runner.QualityGateError, match="untracked"):
        runner._assert_guard_tests_ready()
    source.unlink()
    with pytest.raises(runner.QualityGateError, match="missing"):
        runner._assert_guard_tests_ready(require_tracked=False)
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", ["tests/test_a.py", "tests/test_b.py"])
    collect = {"stdout": "tests/test_a.py::test_a\n", "stderr": "", "returncode": 0}
    with pytest.raises(runner.QualityGateError, match="actual collect|实际 collect"):
        runner._handle_collect_quality_gate_command("", collect)
    collect["stdout"] += "tests/test_b.py::test_b\n"
    proof = runner._handle_collect_quality_gate_command("", collect)
    assert proof["collection_proof"]["default_collect_nodeids"] == [
        "tests/test_a.py::test_a", "tests/test_b.py::test_b",
    ]

    command = {"display": "host contract", "args": ["python", "host_check.py"], "capture_output": True}
    monkeypatch.setenv("SECRET_KEY", "fixture-private-only")
    result = {"stdout": "fixture-private-only\r\nchecked\n", "stderr": "", "returncode": 0}
    entry = runner._write_command_receipt(command, run_id="saved-run", index=1, result=result)
    assert {key: result[key] for key in ("receipt_path", "run_id", "command_index")} == {
        "receipt_path": entry["path"], "run_id": "saved-run", "command_index": 1,
    }
    assert entry["content"]["stdout_content"] == "[REDACTED]\r\nchecked\n"
    assert "fixture-private-only" not in (tmp_path / result["stdout_log_path"]).read_text()
    accepted, error = runner._load_resume_receipt_payload(entry, command, index=1, previous_run_id="saved-run")
    assert accepted is not None and not error
    assert runner._load_resume_receipt_payload(entry, command, index=1, previous_run_id="other-run")[1]
    changed = copy.deepcopy(entry)
    changed["content"]["returncode"] = 1
    assert runner._load_resume_receipt_payload(changed, command, index=1, previous_run_id="saved-run")[1]
    stderr = tmp_path / result["stderr_log_path"]
    stderr.write_text("different output")
    assert runner._load_resume_receipt_payload(entry, command, index=1, previous_run_id="saved-run")[1]
    legacy = {"path": "evidence/QualityGate/receipts/original.json", "sha256": "historical"}
    assert runner._load_resume_receipt_payload(legacy, command, index=1, previous_run_id="saved-run")[1]


def test_hook_cache_and_daily_scope_compare_full_content_and_preserve_old_record(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks, "REPO_ROOT", tmp_path)
    source = tmp_path / "config.bin"
    source.write_bytes(b"\x00first\xff")
    key = {"files": hooks._file_contents(["config.bin"]), "enabled": True}
    path = tmp_path / "cache.v2.json"
    hooks._write_pass_cache(path, key_payload=key, extra={})
    assert hooks._cache_matches(path, key)
    assert not hooks._cache_matches(path, {**key, "enabled": 1})
    source.write_bytes(b"\x00FIRST\xff")
    assert not hooks._cache_matches(path, {**key, "files": hooks._file_contents(["config.bin"])})
    old = tmp_path / "cache.json"
    historical = b'{"schema_version":1,"status":"passed","key_hash":"old","key_payload":{}}\n'
    old.write_bytes(historical)
    assert not hooks._cache_matches(old, {})
    assert old.read_bytes() == historical
    assert "key_hash" not in json.loads(path.read_text())

    scope = daily.DailyGateScope(
        daily.ChangedPathSet(["core/a.py"], True, "actual paths"),
        daily.ImpactPlan(["tests/test_a.py"], ["domain"], False, "actual targets"),
        daily.RuffPlan(["core/a.py"], False, "actual ruff targets"),
    )
    content = daily.daily_gate_scope_payload(scope)
    extra = hooks._daily_scope_cache_extra(content)
    assert extra["changed_paths"] == ["core/a.py"]
    assert extra["impact_pytest_target_paths"] == ["tests/test_a.py"]
    assert extra["ruff_target_paths"] == ["core/a.py"]
    assert not any("hash" in key for key in extra)


def test_git_hook_cli_help_imports_from_outside_repository(tmp_path):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    script = Path(__file__).resolve().parents[1] / "git_hook_checks.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "check-staged-artifacts" in result.stdout
    assert "run-quality-gate" in result.stdout
