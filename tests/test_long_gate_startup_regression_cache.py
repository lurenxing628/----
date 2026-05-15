from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Sequence

import pytest

from tests.long_gate_cache_helpers import (
    _entry_by_id,
    _entry_display,
    _fingerprint_for,
    _load_summary,
    _manifest_for,
    _prepare_gate_run_context,
    _proof_path_for_entry,
    _real_quality_gate_plan,
    _reuse_decision_for,
    _run_gate_with_fake_commands,
    _seed_required_or_startup_success_cache,
    _success_log_path_for_entry,
    _success_path,
    _summary_entry,
    _write_file,
)
from tools import quality_gate_shared
from tools.long_gate_manifest import (
    ENTRY_REQUIRED_REGRESSIONS,
    ENTRY_STARTUP_RUNTIME_REGRESSIONS,
)
from tools.test_registry import iter_startup_regressions


def _seed_startup_success(module, monkeypatch, repo_root: Path, command_plan: Sequence[dict]) -> None:
    _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    assert _proof_path_for_entry(repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS).exists()
    assert _success_path(repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS).exists()


def _call_displays(calls: Sequence[dict]) -> list[str]:
    return [str(call["display"]) for call in calls]


def _call_by_display(calls: Sequence[dict], display: str) -> dict:
    return next(call for call in calls if str(call["display"]) == display)


def test_startup_entry_comes_from_real_command_plan_and_enables_only_next6(tmp_path):
    command_plan = _real_quality_gate_plan()
    manifest = _manifest_for(command_plan, tmp_path)
    startup_entry = _entry_by_id(manifest, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    startup_command = next(command for command in command_plan if command["display"] == startup_entry["display"])
    enabled = [entry["entry_id"] for entry in manifest["entries"] if entry["reuse_allowed"]]

    assert startup_entry["args"] == [str(arg) for arg in startup_command["args"]]
    assert startup_entry["args"][4:] == iter_startup_regressions()
    assert enabled == [
        "pytest_collect_all",
        "full_test_debt",
        "ruff_check_full",
        "pyright_gate_full",
        "pyright_tools_full",
        "required_regressions",
        "startup_runtime_regressions",
    ]
    assert _entry_by_id(manifest, ENTRY_REQUIRED_REGRESSIONS)["cache_status"] == "enabled"


def test_startup_classification_does_not_depend_on_command_position(tmp_path):
    command_plan = _real_quality_gate_plan()
    manifest = _manifest_for(command_plan, tmp_path)
    startup_command = next(
        command
        for command, entry in zip(command_plan, manifest["entries"])
        if entry["entry_id"] == ENTRY_STARTUP_RUNTIME_REGRESSIONS
    )
    reordered_plan = [startup_command, *[command for command in command_plan if command is not startup_command]]

    startup_entry = _entry_by_id(_manifest_for(reordered_plan, tmp_path), ENTRY_STARTUP_RUNTIME_REGRESSIONS)

    assert startup_entry["args"] == [str(arg) for arg in startup_command["args"]]
    assert startup_entry["cache_status"] == "enabled"


def test_startup_scope_tracks_runtime_inputs_without_unrelated_markdown(tmp_path):
    startup = _entry_by_id(_manifest_for(_real_quality_gate_plan(), tmp_path), ENTRY_STARTUP_RUNTIME_REGRESSIONS)

    for path in [
        "web/bootstrap/**/*.py",
        "app.py",
        "app_new_ui.py",
        "config.py",
        "schema.sql",
        "templates/**/*.html",
        "static/**/*",
        "tools/long_gate_manifest.py",
        "tools/long_gate_fingerprint.py",
        "tools/long_gate_cache.py",
        "tools/long_gate_schema.py",
        "tools/test_registry.py",
        "scripts/run_quality_gate.py",
    ]:
        assert path in (
            startup["input_file_scopes"]
            + startup["config_file_scopes"]
            + startup["tool_file_scopes"]
            + startup["dependency_file_scopes"]
        )
    assert "docs/**/*.md" not in startup["input_file_scopes"]
    assert "audit/**/*.md" not in startup["input_file_scopes"]
    assert "开发文档/**/*.md" not in startup["input_file_scopes"]


def test_startup_success_writes_proof_and_reuses_next_run(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)

    first_calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    proof = json.loads(_proof_path_for_entry(repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS).read_text(encoding="utf-8"))
    success_cache = json.loads(
        _success_path(repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS).read_text(encoding="utf-8")
    )
    manifest = _manifest_for(command_plan, repo_root)
    startup_entry = _entry_by_id(manifest, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    startup_index = next(
        index
        for index, entry in enumerate(manifest["entries"], start=1)
        if entry["entry_id"] == ENTRY_STARTUP_RUNTIME_REGRESSIONS
    )

    startup_call = _call_by_display(first_calls, startup_display)
    first_displays = _call_displays(first_calls)
    assert startup_display in first_displays
    assert startup_call["args"] == [str(arg) for arg in module._resolve_command_args(startup_entry)]
    assert startup_call["args"][-len(startup_entry["args"][4:]) :] == startup_entry["args"][4:]
    assert startup_call["capture_output"] == bool(startup_entry["capture_output"])
    assert proof["schema_version"] == module.STARTUP_RUNTIME_REGRESSIONS_PROOF_SCHEMA_VERSION
    assert proof["status"] == "passed"
    assert proof["entry_id"] == ENTRY_STARTUP_RUNTIME_REGRESSIONS
    assert proof["quality_gate_plan_hash"] == quality_gate_shared.hash_quality_gate_commands(command_plan)
    assert proof["command_index"] == startup_index
    assert proof["display"] == startup_entry["display"]
    assert proof["args"] == startup_entry["args"]
    assert proof["command_hash"] == startup_entry["command_hash"]
    assert proof["fingerprint_schema_version"] == startup_entry["fingerprint_schema_version"]
    assert proof["fingerprint_hash"] == success_cache["fingerprint_hash"]
    assert proof["returncode"] == 0
    assert proof["pytest_exit_code"] == 0
    assert proof["execution_mode"] == "executed"
    assert proof["test_count"] == len(iter_startup_regressions())
    assert proof["startup_target_count"] == len(iter_startup_regressions())
    assert proof["startup_target_paths"] == iter_startup_regressions()
    assert proof["stdout_log_path"] == "evidence/QualityGate/long_gate/logs/startup_runtime_regressions.stdout.log"
    assert proof["stderr_log_path"] == "evidence/QualityGate/long_gate/logs/startup_runtime_regressions.stderr.log"
    assert proof["logs"]["stdout"]["path"] == (
        "evidence/QualityGate/long_gate/logs/startup_runtime_regressions.stdout.log"
    )
    assert proof["logs"]["stderr"]["path"] == (
        "evidence/QualityGate/long_gate/logs/startup_runtime_regressions.stderr.log"
    )
    stdout_log = repo_root / proof["logs"]["stdout"]["path"]
    stderr_log = repo_root / proof["logs"]["stderr"]["path"]
    assert stdout_log.exists()
    assert stderr_log.exists()
    assert proof["logs"]["stdout"]["sha256"] == hashlib.sha256(stdout_log.read_bytes()).hexdigest()
    assert proof["logs"]["stderr"]["sha256"] == hashlib.sha256(stderr_log.read_bytes()).hexdigest()
    assert proof["stdout_sha256"] == proof["logs"]["stdout"]["sha256"]
    assert proof["stderr_sha256"] == proof["logs"]["stderr"]["sha256"]

    second_calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary = _load_summary(repo_root)

    second_displays = _call_displays(second_calls)
    assert startup_display not in second_displays
    assert required_display not in second_displays
    assert _summary_entry(summary, ENTRY_STARTUP_RUNTIME_REGRESSIONS)["execution_mode"] == "reused_success_cache"
    assert _summary_entry(summary, ENTRY_REQUIRED_REGRESSIONS)["execution_mode"] == "reused_success_cache"
    assert _success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda repo_root: _success_log_path_for_entry(
            repo_root,
            ENTRY_STARTUP_RUNTIME_REGRESSIONS,
            "stdout",
        ).write_text("changed stdout\n", encoding="utf-8"),
    ],
)
def test_startup_bad_stdout_log_forces_parent_rerun(monkeypatch, tmp_path, mutate):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    _seed_required_or_startup_success_cache(
        module,
        repo_root,
        command_plan,
        ENTRY_STARTUP_RUNTIME_REGRESSIONS,
    )

    mutate(repo_root)
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])

    assert startup_display in [str(call["display"]) for call in calls]
    assert _summary_entry(_load_summary(repo_root), ENTRY_STARTUP_RUNTIME_REGRESSIONS)["execution_mode"] == "executed"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda repo_root: _proof_path_for_entry(repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS).unlink(),
        lambda repo_root: _proof_path_for_entry(repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS).write_text(
            "{bad json",
            encoding="utf-8",
        ),
    ],
)
def test_startup_bad_proof_file_invalidates_success_cache_without_runner(monkeypatch, tmp_path, mutate):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    _seed_required_or_startup_success_cache(
        module,
        repo_root,
        command_plan,
        ENTRY_STARTUP_RUNTIME_REGRESSIONS,
    )
    success_cache = json.loads(_success_path(repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS).read_text(encoding="utf-8"))
    assert "evidence/QualityGate/startup_runtime_regressions.json" in {
        str(row["path"]) for row in success_cache["output_files"]
    }

    mutate(repo_root)
    decision = _reuse_decision_for(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)

    assert decision["decision"] == "run"
    assert decision["reason"] == "previous output files missing or hash mismatch"


@pytest.mark.parametrize(
    "changed_path",
    [
        "tests/regression_runtime_probe_resolution.py",
        "web/bootstrap/runtime.py",
        "app.py",
        "app_new_ui.py",
        "config.py",
        "schema.sql",
        "templates/base.html",
        "static/app.css",
        "pyproject.toml",
        "requirements.txt",
        "scripts/run_quality_gate.py",
        "tools/long_gate_cache.py",
        "tools/long_gate_fingerprint.py",
        "tools/long_gate_manifest.py",
        "tools/long_gate_schema.py",
        "tools/test_registry.py",
    ],
)
def test_startup_tracked_scope_changes_update_fingerprint(tmp_path, changed_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    before = _fingerprint_for(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)

    _write_file(repo_root, changed_path)
    after = _fingerprint_for(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)

    assert before["hash"] != after["hash"]


@pytest.mark.parametrize(
    "env_key",
    [
        "APS_ENV",
        "APS_DB_PATH",
        "APS_LOG_DIR",
        "APS_BACKUP_DIR",
        "APS_EXCEL_TEMPLATE_DIR",
        "APS_CHROME_PATH",
        "PYTHONPATH",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
    ],
)
def test_startup_environment_changes_update_fingerprint(monkeypatch, tmp_path, env_key):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    monkeypatch.delenv(env_key, raising=False)
    before = _fingerprint_for(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)

    monkeypatch.setenv(env_key, f"next6-{env_key.lower()}")
    after = _fingerprint_for(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)

    assert before["hash"] != after["hash"]
    assert after["components"]["environment"]["values"][env_key] == os.environ.get(env_key)


def test_unrelated_markdown_change_does_not_invalidate_startup(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    _seed_required_or_startup_success_cache(
        module,
        repo_root,
        command_plan,
        ENTRY_STARTUP_RUNTIME_REGRESSIONS,
    )

    _write_file(repo_root, "notes/unrelated.md", "# unrelated\n")
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])

    assert startup_display not in [str(call["display"]) for call in calls]
    assert _summary_entry(_load_summary(repo_root), ENTRY_STARTUP_RUNTIME_REGRESSIONS)["execution_mode"] == (
        "reused_success_cache"
    )


def test_startup_invalidation_keeps_full_test_debt_success_cache_reuse(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    monkeypatch.delenv("APS_ENV", raising=False)
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    _seed_startup_success(module, monkeypatch, repo_root, command_plan)

    monkeypatch.setenv("APS_ENV", "next6-startup-only")
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary = _load_summary(repo_root)

    displays = [str(call["display"]) for call in calls]
    assert "python tools/check_full_test_debt.py" not in displays
    assert startup_display in displays
    assert _summary_entry(summary, "full_test_debt")["execution_mode"] == "reused_success_cache"
    assert _summary_entry(summary, ENTRY_STARTUP_RUNTIME_REGRESSIONS)["execution_mode"] == "executed"
    assert _success_path(repo_root, "full_test_debt").exists()
    assert (repo_root / "evidence" / "QualityGate" / "current_full_test_debt.json").exists()
    assert (repo_root / "evidence" / "QualityGate" / "full_test_debt_summary.json").exists()
    assert (repo_root / "evidence" / "QualityGate" / "full_test_debt_node_cache.json").exists()


def test_explain_does_not_write_startup_proof(monkeypatch, tmp_path, capsys):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root

    assert module.main(["--long-gate-cache-explain"]) == 0

    assert "startup_runtime_regressions" in capsys.readouterr().out
    assert not _proof_path_for_entry(repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS).exists()


def test_no_cache_ignores_existing_startup_cache_and_does_not_write_proof(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    _seed_required_or_startup_success_cache(
        module,
        repo_root,
        command_plan,
        ENTRY_STARTUP_RUNTIME_REGRESSIONS,
    )
    _proof_path_for_entry(repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS).unlink()

    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--no-long-gate-cache"])

    assert startup_display in [str(call["display"]) for call in calls]
    assert not _proof_path_for_entry(repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS).exists()


def test_force_rerun_startup_executes_parent_instead_of_reusing(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    _seed_startup_success(module, monkeypatch, repo_root, command_plan)

    calls = _run_gate_with_fake_commands(
        module,
        monkeypatch,
        repo_root,
        command_plan,
        ["--long-gate-cache", "--long-gate-force-rerun", ENTRY_STARTUP_RUNTIME_REGRESSIONS],
    )
    startup_summary = _summary_entry(_load_summary(repo_root), ENTRY_STARTUP_RUNTIME_REGRESSIONS)

    assert startup_display in [str(call["display"]) for call in calls]
    assert startup_summary["execution_mode"] == "executed"
    assert startup_summary["reason"] == (
        "forced by --long-gate-force-rerun startup_runtime_regressions"
    )


def test_force_rerun_all_executes_startup_and_required(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    _seed_startup_success(module, monkeypatch, repo_root, command_plan)

    calls = _run_gate_with_fake_commands(
        module,
        monkeypatch,
        repo_root,
        command_plan,
        ["--long-gate-cache", "--long-gate-force-rerun-all"],
    )
    summary = _load_summary(repo_root)

    displays = [str(call["display"]) for call in calls]
    assert "python -m pytest --collect-only -q tests" in displays
    assert "python tools/check_full_test_debt.py" in displays
    assert required_display in displays
    assert startup_display in displays
    assert _summary_entry(summary, ENTRY_REQUIRED_REGRESSIONS)["reason"] == "forced by --long-gate-force-rerun-all"
    assert _summary_entry(summary, ENTRY_STARTUP_RUNTIME_REGRESSIONS)["reason"] == (
        "forced by --long-gate-force-rerun-all"
    )
    assert _success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).exists()
