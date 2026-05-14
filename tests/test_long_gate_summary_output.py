from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import pytest

from tools.long_gate_summary import (
    build_long_gate_summary,
    build_summary_entry,
    extract_copyable_failure,
    render_summary_markdown,
    tail_text,
)


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


def _patch_gate_environment(monkeypatch, module, repo_root: Path, *, statuses: Sequence[Sequence[str]]):
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
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"dirty-diff")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})


def _successful_result(display: str) -> dict:
    if display == "python -m pytest --collect-only -q tests":
        return {
            "stdout": "tests/test_long_gate_summary_output.py::test_collect_summary\n",
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


def _summary_md_path(repo_root: Path) -> Path:
    return repo_root / "evidence" / "QualityGate" / "long_gate" / "summary.md"


def _success_cache_path(repo_root: Path) -> Path:
    return repo_root / "evidence" / "QualityGate" / "long_gate" / "results" / "pytest_collect_all.success.json"


def _load_summary(repo_root: Path) -> dict:
    return json.loads(_summary_path(repo_root).read_text(encoding="utf-8"))


def _entry_by_id(summary: dict, entry_id: str) -> dict:
    for entry in summary["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError(f"missing summary entry: {entry_id}")


def _write_collect_input(repo_root: Path) -> None:
    test_path = repo_root / "tests" / "test_cached_collect.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_cached_collect():\n    assert True\n", encoding="utf-8")


def _seed_collect_success(module, command_plan, repo_root: Path) -> None:
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
    )


def test_explain_mode_prints_full_decision_table_and_writes_no_proof(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_plan())

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("explain must not execute quality gate commands")

    monkeypatch.setattr(module, "_run_command", fail_if_called)

    assert module.main(["--long-gate-cache-explain"]) == 0

    output = capsys.readouterr().out
    assert "Long gate cache decisions" in output
    assert "pytest_collect_all: RUN" in output
    assert "ruff_check_full: PLANNED_ONLY" in output
    assert "cache: enabled" in output
    assert "cache: planned" in output
    assert "explain mode prints decisions only; it is not a quality gate proof" in output
    assert not _summary_path(repo_root).exists()
    assert not _success_cache_path(repo_root).exists()


def test_successful_run_writes_json_md_counts_and_reasons(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_plan())
    monkeypatch.setattr(module, "_run_command", lambda display, args, capture_output=False: _successful_result(display))

    assert module.main(["--long-gate-cache"]) == 0

    summary = _load_summary(repo_root)
    assert _summary_md_path(repo_root).exists()
    assert summary["schema_version"] == 1
    assert summary["mode"] == "run"
    assert summary["cache_enabled"] is True
    assert summary["cache_dir"] == "evidence/QualityGate/long_gate"
    assert summary["counts"] == {"executed": 1, "reused": 0, "failed": 0, "planned_only": 1, "disabled": 0}
    assert summary["duration"]["total_s"] > 0.0
    assert summary["duration"]["executed_total_s"] > 0.0
    assert summary["duration"]["reuse_overhead_total_s"] == 0.0
    assert summary["duration"]["top_entries"][0]["entry_id"] == "pytest_collect_all"
    for entry in summary["entries"]:
        assert entry["reason"]
        assert isinstance(entry["invalidated_by"], list)
    collect = _entry_by_id(summary, "pytest_collect_all")
    assert collect["execution_mode"] == "executed"
    assert collect["duration_kind"] == "executed"
    assert collect["duration_s"] > 0.0
    assert collect["returncode"] == 0
    assert collect["receipt_path"].startswith("evidence/QualityGate/receipts/")
    assert collect["stdout_log_path"].startswith("evidence/QualityGate/logs/")
    assert collect["stderr_log_path"].startswith("evidence/QualityGate/logs/")
    assert collect["output_files"][0]["path"] == "evidence/QualityGate/collect_nodeids.json"
    planned = _entry_by_id(summary, "ruff_check_full")
    assert planned["decision"] == "planned_only"
    assert planned["execution_mode"] == "planned_only"
    markdown = _summary_md_path(repo_root).read_text(encoding="utf-8")
    assert "## Duration" in markdown
    assert "## Slow entries" in markdown
    assert "For local profiling, run the exact final proof command" in markdown


def test_reused_collect_only_is_recorded_as_reused_success_cache(monkeypatch, tmp_path):
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
        if display == "python -m pytest --collect-only -q tests":
            raise AssertionError("collect-only should be reused")
        return _successful_result(display)

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--long-gate-cache"]) == 0

    summary = _load_summary(repo_root)
    collect = _entry_by_id(summary, "pytest_collect_all")
    assert "python -m pytest --collect-only -q tests" not in calls
    assert collect["decision"] == "reuse"
    assert collect["execution_mode"] == "reused_success_cache"
    assert collect["duration_kind"] == "reuse_overhead"
    assert collect["duration_s"] > 0.0
    assert collect["original_duration_s"] == 8.0
    assert collect["previous_result_path"].endswith("pytest_collect_all.success.json")
    assert summary["duration"]["reuse_overhead_total_s"] > 0.0
    assert summary["duration"]["top_entries"][0]["original_duration_s"] == 8.0
    assert summary["counts"]["reused"] == 1


def test_required_regression_groups_are_recorded_in_json_and_markdown():
    entry = {
        "entry_id": "required_regressions",
        "entry_type": "required_regressions",
        "display": "python -m pytest -q tests/test_a.py tests/test_b.py",
        "cache_status": "enabled",
    }
    decision = {
        "entry_id": "required_regressions",
        "decision": "run",
        "reason": "input fingerprint changed",
    }
    result = {
        "stdout": "",
        "stderr": "",
        "returncode": 0,
        "execution_mode": "grouped",
        "duration_s": 3.5,
        "required_regressions_groups": [
            {
                "group_id": "quality_gate",
                "decision": "run",
                "execution_mode": "executed",
                "target_count": 1,
                "duration_s": 1.25,
                "original_duration_s": 0.0,
                "proof_path": "evidence/QualityGate/required_regressions/groups/quality_gate.json",
            },
            {
                "group_id": "scheduler_config",
                "decision": "reuse",
                "execution_mode": "reused_success_cache",
                "target_count": 2,
                "duration_s": 0.05,
                "original_duration_s": 9.5,
                "proof_path": "evidence/QualityGate/required_regressions/groups/scheduler_config.json",
            },
        ],
    }

    summary = build_long_gate_summary(
        run_id="run",
        repo_root="/repo",
        head_sha="deadbeef",
        worktree_clean=True,
        cache_enabled=True,
        mode="run",
        entries=[
            build_summary_entry(
                index=1,
                entry=entry,
                decision=decision,
                result=result,
                receipt_path="evidence/QualityGate/receipts/required.json",
            )
        ],
    )
    markdown = render_summary_markdown(summary)

    required = _entry_by_id(summary, "required_regressions")
    assert summary["counts"]["executed"] == 1
    assert required["execution_mode"] == "grouped"
    assert required["required_regressions_groups"][1]["original_duration_s"] == 9.5
    assert "## Required regression groups" in markdown
    assert "| scheduler_config | reuse | reused_success_cache | 2 | 0.050 | 9.500 |" in markdown


def test_failed_collect_records_failure_and_prints_copyable_command(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_plan(include_planned=False))

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m pytest --collect-only -q tests":
            stdout = "FAILED tests/test_long_gate_summary_output.py::test_bad - nope\n"
            return {"stdout": stdout, "stderr": "collect failed\n", "returncode": 1}
        return _successful_result(display)

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    with pytest.raises(module.QualityGateError):
        module.main(["--long-gate-cache"])

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    summary = _load_summary(repo_root)
    failure = summary["failure"]
    assert summary["counts"]["failed"] == 1
    assert failure["entry_id"] == "pytest_collect_all"
    assert failure["copyable_nodeids"] == ["tests/test_long_gate_summary_output.py::test_bad"]
    assert failure["copyable_command"] == "python -m pytest -q tests/test_long_gate_summary_output.py::test_bad"
    assert failure["receipt_path"].startswith("evidence/QualityGate/receipts/")
    assert failure["stdout_log_path"].startswith("evidence/QualityGate/logs/")
    assert failure["stderr_log_path"].startswith("evidence/QualityGate/logs/")
    assert "FAILED tests/test_long_gate_summary_output.py::test_bad" in failure["stdout_tail"]
    assert "collect failed" in failure["stderr_tail"]
    assert "copyable rerun:" in combined
    assert "python -m pytest -q tests/test_long_gate_summary_output.py::test_bad" in combined


def test_planned_long_entry_failure_records_summary_failure(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_plan(include_planned=True))

    def fake_run_command(display, args, capture_output=False):
        if display == "python -m ruff check":
            return {
                "stdout": "unexpected failure: tests/test_long_gate_summary_output.py::test_debt\n",
                "stderr": "full debt failed\n",
                "returncode": 1,
            }
        return _successful_result(display)

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    with pytest.raises(module.QualityGateError):
        module.main(["--long-gate-cache"])

    summary = _load_summary(repo_root)
    failure = summary["failure"]
    full_debt = _entry_by_id(summary, "ruff_check_full")
    assert summary["counts"]["failed"] == 1
    assert failure["entry_id"] == "ruff_check_full"
    assert failure["copyable_command"] == "python -m ruff check"
    assert failure["copyable_nodeids"] == []
    assert "full debt failed" in failure["stderr_tail"]
    assert full_debt["decision"] == "planned_only"
    assert full_debt["failed"] is True


def test_dirty_worktree_summary_is_unbound_and_does_not_write_success_cache(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[" M app.py"], [" M app.py"]])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_plan(include_planned=False))
    monkeypatch.setattr(module, "_run_command", lambda display, args, capture_output=False: _successful_result(display))

    assert module.main(["--allow-dirty-worktree", "--long-gate-cache"]) == 2

    summary = _load_summary(repo_root)
    assert summary["worktree_clean"] is False
    assert summary["counts"]["executed"] == 1
    assert not _success_cache_path(repo_root).exists()


def test_summary_write_failure_prevents_success_cache(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _small_plan(include_planned=False))
    monkeypatch.setattr(module, "_run_command", lambda display, args, capture_output=False: _successful_result(display))

    def boom_write_summary(*_args, **_kwargs):
        raise OSError("summary disk full")

    monkeypatch.setattr(module, "write_long_gate_summary", boom_write_summary)

    with pytest.raises(OSError, match="summary disk full"):
        module.main(["--long-gate-cache"])

    assert not _success_cache_path(repo_root).exists()


def test_disabled_entry_summary_keeps_reason_and_invalidated_by():
    entry = {"entry_id": "pytest_collect_all", "entry_type": "pytest_collect_all", "cache_status": "enabled"}
    decision = {
        "entry_id": "pytest_collect_all",
        "decision": "disabled",
        "reason": "long gate cache is disabled for this run",
        "invalidated_by": [],
    }

    summary_entry = build_summary_entry(index=1, entry=entry, decision=decision)
    summary = build_long_gate_summary(
        run_id="run",
        repo_root=_repo_root(),
        head_sha="head",
        worktree_clean=True,
        cache_enabled=False,
        mode="run",
        entries=[summary_entry],
    )

    assert summary_entry["decision"] == "disabled"
    assert summary_entry["reason"] == "long gate cache is disabled for this run"
    assert summary_entry["invalidated_by"] == []
    assert summary["counts"]["disabled"] == 1


def test_tail_text_keeps_only_last_lines():
    text = "\n".join(f"line {index}" for index in range(1, 101))

    tailed = tail_text(text, max_lines=80)

    assert "line 100" in tailed
    assert "line 1" not in tailed.splitlines()
    assert len(tailed.splitlines()) == 80


def test_extract_copyable_failure_falls_back_to_display_without_nodeid():
    failure = extract_copyable_failure(
        entry_id="ruff_check_full",
        display="python -m ruff check",
        result={"stdout": "", "stderr": "boom", "returncode": 1},
        receipt_path="evidence/QualityGate/receipts/ruff.json",
    )

    assert failure["copyable_command"] == "python -m ruff check"
    assert failure["copyable_nodeids"] == []
    assert failure["stderr_tail"] == "boom"


def test_extract_copyable_failure_quotes_pytest_nodeids_and_ignores_non_pytest_output():
    pytest_failure = extract_copyable_failure(
        entry_id="pytest_collect_all",
        display="python -m pytest --collect-only -q tests",
        result={
            "stdout": "FAILED tests/test_x.py::test_param[a;b]",
            "stderr": "",
            "returncode": 1,
        },
        receipt_path="evidence/QualityGate/receipts/collect.json",
    )
    non_pytest_failure = extract_copyable_failure(
        entry_id="full_test_debt",
        display="python tools/check_full_test_debt.py",
        result={
            "stdout": "unexpected tests/test_x.py::test_param[a;b]",
            "stderr": "",
            "returncode": 1,
        },
        receipt_path="evidence/QualityGate/receipts/debt.json",
    )

    assert pytest_failure["copyable_nodeids"] == ["tests/test_x.py::test_param[a;b]"]
    assert pytest_failure["copyable_command"] == "python -m pytest -q 'tests/test_x.py::test_param[a;b]'"
    assert non_pytest_failure["copyable_nodeids"] == []
    assert non_pytest_failure["copyable_command"] == "python tools/check_full_test_debt.py"


def test_interrupted_and_partial_write_flags_are_preserved():
    entry = {"entry_id": "pytest_collect_all", "entry_type": "pytest_collect_all", "cache_status": "enabled"}
    decision = {"entry_id": "pytest_collect_all", "decision": "run", "reason": "manual", "invalidated_by": []}

    summary_entry = build_summary_entry(
        index=1,
        entry=entry,
        decision=decision,
        result={
            "stdout": "",
            "stderr": "",
            "returncode": 1,
            "interrupted": True,
            "partial_write": True,
            "timed_out": False,
        },
        failed=True,
    )

    assert summary_entry["interrupted"] is True
    assert summary_entry["partial_write"] is True
    assert summary_entry["timed_out"] is False
    assert summary_entry["failed"] is True


def test_markdown_renders_failure_paths_and_tails():
    entry = {"entry_id": "pytest_collect_all", "entry_type": "pytest_collect_all", "cache_status": "enabled"}
    decision = {"entry_id": "pytest_collect_all", "decision": "run", "reason": "no cache", "invalidated_by": []}
    summary_entry = build_summary_entry(index=1, entry=entry, decision=decision)
    summary = build_long_gate_summary(
        run_id="run",
        repo_root=_repo_root(),
        head_sha="head",
        worktree_clean=True,
        cache_enabled=True,
        mode="run",
        entries=[summary_entry],
        failure={
            "entry_id": "pytest_collect_all",
            "display": "python -m pytest --collect-only -q tests",
            "copyable_command": "python -m pytest -q tests/test_x.py::test_y",
            "copyable_nodeids": ["tests/test_x.py::test_y"],
            "receipt_path": "evidence/QualityGate/receipts/collect.json",
            "stdout_log_path": "evidence/QualityGate/logs/collect.stdout.log",
            "stderr_log_path": "evidence/QualityGate/logs/collect.stderr.log",
            "stdout_tail": "FAILED tests/test_x.py::test_y",
            "stderr_tail": "boom",
        },
    )

    markdown = render_summary_markdown(summary)

    assert "copyable_command" in markdown
    assert "evidence/QualityGate/receipts/collect.json" in markdown
    assert "FAILED tests/test_x.py::test_y" in markdown
    assert "boom" in markdown


def test_summary_counts_incremental_modes_as_executed():
    entry = {"entry_id": "full_test_debt", "entry_type": "full_test_debt", "cache_status": "enabled"}
    decision = {"entry_id": "full_test_debt", "decision": "run", "reason": "input fingerprint changed"}
    nodeid_entry = build_summary_entry(
        index=1,
        entry=entry,
        decision=decision,
        result={"stdout": "", "stderr": "", "returncode": 0, "execution_mode": "nodeid_incremental"},
        receipt_path="evidence/QualityGate/receipts/full.json",
    )
    ledger_entry = build_summary_entry(
        index=2,
        entry=entry,
        decision=decision,
        result={"stdout": "", "stderr": "", "returncode": 0, "execution_mode": "ledger_only"},
        receipt_path="evidence/QualityGate/receipts/full2.json",
    )

    summary = build_long_gate_summary(
        run_id="run",
        repo_root=_repo_root(),
        head_sha="head",
        worktree_clean=True,
        cache_enabled=True,
        mode="run",
        entries=[nodeid_entry, ledger_entry],
    )

    assert summary["counts"]["executed"] == 2


def test_summary_duration_keeps_counts_and_ranks_slow_entries():
    executed = build_summary_entry(
        index=1,
        entry={"entry_id": "full_test_debt", "entry_type": "full_test_debt", "cache_status": "enabled"},
        decision={"entry_id": "full_test_debt", "decision": "run", "reason": "input fingerprint changed"},
        result={
            "stdout": "",
            "stderr": "",
            "returncode": 0,
            "execution_mode": "executed",
            "duration_s": 201.25,
            "duration_kind": "executed",
        },
        receipt_path="evidence/QualityGate/receipts/full.json",
    )
    reused = build_summary_entry(
        index=2,
        entry={"entry_id": "required_regressions", "entry_type": "required_regressions", "cache_status": "enabled"},
        decision={"entry_id": "required_regressions", "decision": "reuse", "reason": "success cache reusable"},
        result={
            "stdout": "",
            "stderr": "",
            "returncode": 0,
            "execution_mode": "reused_success_cache",
            "duration_s": 0.12,
            "duration_kind": "reuse_overhead",
            "original_duration_s": 98.34,
        },
        receipt_path="evidence/QualityGate/receipts/required.json",
    )
    planned = build_summary_entry(
        index=3,
        entry={"entry_id": "ruff_check_full", "entry_type": "ruff", "cache_status": "planned"},
        decision={"entry_id": "ruff_check_full", "decision": "planned_only", "reason": "not cache-enabled"},
    )

    summary = build_long_gate_summary(
        run_id="run",
        repo_root=_repo_root(),
        head_sha="head",
        worktree_clean=True,
        cache_enabled=True,
        mode="run",
        entries=[executed, reused, planned],
    )
    markdown = render_summary_markdown(summary)

    assert summary["counts"] == {"executed": 1, "reused": 1, "failed": 0, "planned_only": 1, "disabled": 0}
    assert summary["duration"]["total_s"] == pytest.approx(201.37)
    assert summary["duration"]["executed_total_s"] == pytest.approx(201.25)
    assert summary["duration"]["reuse_overhead_total_s"] == pytest.approx(0.12)
    assert [row["entry_id"] for row in summary["duration"]["top_entries"]] == [
        "full_test_debt",
        "required_regressions",
    ]
    assert "## Duration" in markdown
    assert "## Slow entries" in markdown
    assert "| 2 | required_regressions | reused_success_cache | 0.120 | 98.340 | success cache reusable |" in markdown


def test_summary_markdown_displays_full_test_debt_helper_incremental_details():
    helper_plan = {
        "available": True,
        "mode": "nodeid_incremental",
        "changed_helpers": ["tests/long_gate_cache_helpers.py"],
        "declared_helper_impacts": {
            "tests/long_gate_cache_helpers.py": [
                "tests/test_long_gate_required_regression_cache.py",
                "tests/test_long_gate_startup_regression_cache.py",
            ]
        },
        "actual_importing_test_files": [
            "tests/test_long_gate_required_regression_cache.py",
            "tests/test_long_gate_startup_regression_cache.py",
        ],
        "affected_test_files": [
            "tests/test_long_gate_required_regression_cache.py",
            "tests/test_long_gate_startup_regression_cache.py",
        ],
        "selected_nodeids": ["tests/test_long_gate_required_regression_cache.py::test_required"],
    }
    entry = build_summary_entry(
        index=1,
        entry={"entry_id": "full_test_debt", "entry_type": "full_test_debt", "cache_status": "enabled"},
        decision={
            "entry_id": "full_test_debt",
            "decision": "run",
            "reason": "input fingerprint changed",
            "full_test_debt_incremental": helper_plan,
        },
        result={"returncode": 0, "execution_mode": "nodeid_incremental", "duration_s": 1.0},
    )

    summary = build_long_gate_summary(
        run_id="run",
        repo_root=_repo_root(),
        head_sha="head",
        worktree_clean=True,
        cache_enabled=True,
        mode="run",
        entries=[entry],
    )
    markdown = render_summary_markdown(summary)

    assert summary["entries"][0]["full_test_debt_incremental"] == helper_plan
    assert "## Full-test-debt incremental" in markdown
    assert "changed_helpers" in markdown
    assert "tests/long_gate_cache_helpers.py" in markdown
    assert "declared_helper_impacts" in markdown
    assert "actual_importing_test_files" in markdown
    assert "affected_test_files" in markdown
