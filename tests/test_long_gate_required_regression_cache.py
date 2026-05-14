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
    _fake_successful_command,
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


def _seed_required_success(module, monkeypatch, repo_root: Path, command_plan: Sequence[dict]) -> None:
    _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    assert _proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).exists()
    assert _success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).exists()


def test_required_entry_comes_from_real_command_plan_and_enables_only_next7(tmp_path):
    command_plan = _real_quality_gate_plan()
    manifest = _manifest_for(command_plan, tmp_path)
    required_entry = _entry_by_id(manifest, ENTRY_REQUIRED_REGRESSIONS)
    required_command = next(command for command in command_plan if command["display"] == required_entry["display"])
    enabled = [entry["entry_id"] for entry in manifest["entries"] if entry["reuse_allowed"]]

    assert required_entry["args"] == [str(arg) for arg in required_command["args"]]
    assert required_entry["input_file_scopes"][: len(required_entry["args"][4:])] == required_entry["args"][4:]
    assert enabled == [
        "pytest_collect_all",
        "full_test_debt",
        "required_regressions",
        "startup_runtime_regressions",
    ]
    for entry_id in [
        "ruff_check_full",
        "pyright_gate_full",
        "pyright_tools_full",
        "architecture_fitness",
        "debt_ledger_sync",
        "quickref_vs_routes",
    ]:
        assert _entry_by_id(manifest, entry_id)["cache_status"] == "planned"


def test_required_classification_does_not_depend_on_command_position(tmp_path):
    command_plan = _real_quality_gate_plan()
    manifest = _manifest_for(command_plan, tmp_path)
    required_command = next(
        command
        for command, entry in zip(command_plan, manifest["entries"])
        if entry["entry_id"] == ENTRY_REQUIRED_REGRESSIONS
    )
    reordered_plan = [required_command, *[command for command in command_plan if command is not required_command]]

    required_entry = _entry_by_id(_manifest_for(reordered_plan, tmp_path), ENTRY_REQUIRED_REGRESSIONS)

    assert required_entry["args"] == [str(arg) for arg in required_command["args"]]
    assert required_entry["cache_status"] == "enabled"


def test_required_scope_tracks_real_inputs_without_unrelated_markdown(tmp_path):
    required = _entry_by_id(_manifest_for(_real_quality_gate_plan(), tmp_path), ENTRY_REQUIRED_REGRESSIONS)
    all_scopes = (
        required["input_file_scopes"]
        + required["config_file_scopes"]
        + required["tool_file_scopes"]
        + required["dependency_file_scopes"]
    )

    for path in [
        "core/**/*.py",
        "web/**/*.py",
        "data/**/*.py",
        "plugins/**/*.py",
        "app.py",
        "app_new_ui.py",
        "config.py",
        "schema.sql",
        "templates/**/*.html",
        "web_new_test/templates/**/*.html",
        "static/**/*",
        "web_new_test/static/**/*",
        "templates_excel/**/*",
        "static/docs/**/*.md",
        "web_new_test/static/docs/**/*.md",
        "docs/frontend_manual_audit_and_rewrite_blueprint.md",
        ".limcode/skills/aps-full-selftest/scripts/run_full_selftest.py",
        ".limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md",
        "evidence/README.md",
        "evidence/current/README.md",
        "audit/**/README.md",
        "开发文档/开发文档.md",
        "开发文档/阶段留痕与验收记录.md",
        "tools/test_registry.py",
        "tools/long_gate_manifest.py",
        "tools/long_gate_fingerprint.py",
        "scripts/run_quality_gate.py",
    ]:
        assert path in all_scopes
    assert set(quality_gate_shared.QUALITY_GATE_TOOL_PATHS) <= set(all_scopes)
    for env_key in [
        "python_executable_realpath",
        "python_version",
        "pytest_version",
        "pytest_plugin_distribution_versions",
        "platform",
        "PYTHONPATH",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
        "PYTEST_ADDOPTS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTEST_PLUGINS",
        "APS_CHROME_PATH",
        "chrome_executable_resolution",
        "node_executable_realpath",
        "node_version",
        "PATH",
    ]:
        assert env_key in required["env_keys"]
    assert "docs/**/*.md" not in required["input_file_scopes"]
    assert "audit/**/*.md" not in required["input_file_scopes"]
    assert "开发文档/**/*.md" not in required["input_file_scopes"]
    assert required["output_result_files"] == ["evidence/QualityGate/required_regressions.json"]


def test_required_success_writes_proof_and_reuses_next_run(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)

    first_calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    proof = json.loads(_proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8"))
    success_cache = json.loads(_success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8"))
    manifest = _manifest_for(command_plan, repo_root)
    required_entry = _entry_by_id(manifest, ENTRY_REQUIRED_REGRESSIONS)
    required_index = next(
        index
        for index, entry in enumerate(manifest["entries"], start=1)
        if entry["entry_id"] == ENTRY_REQUIRED_REGRESSIONS
    )

    assert required_display in first_calls
    assert proof["schema_version"] == module.REQUIRED_REGRESSIONS_PROOF_SCHEMA_VERSION
    assert proof["status"] == "passed"
    assert proof["entry_id"] == ENTRY_REQUIRED_REGRESSIONS
    assert proof["quality_gate_plan_hash"] == quality_gate_shared.hash_quality_gate_commands(command_plan)
    assert proof["command_index"] == required_index
    assert proof["display"] == required_entry["display"]
    assert proof["args"] == required_entry["args"]
    assert proof["command_hash"] == required_entry["command_hash"]
    assert proof["fingerprint_schema_version"] == required_entry["fingerprint_schema_version"]
    assert proof["fingerprint_hash"] == success_cache["fingerprint_hash"]
    assert proof["returncode"] == 0
    assert proof["pytest_exit_code"] == 0
    assert proof["execution_mode"] == "executed"
    assert proof["test_count"] == len(required_entry["args"][4:])
    assert proof["required_target_count"] == len(required_entry["args"][4:])
    assert proof["required_target_paths"] == required_entry["args"][4:]
    assert proof["stdout_log_path"] == "evidence/QualityGate/long_gate/logs/required_regressions.stdout.log"
    assert proof["stderr_log_path"] == "evidence/QualityGate/long_gate/logs/required_regressions.stderr.log"
    stdout_log = repo_root / proof["logs"]["stdout"]["path"]
    stderr_log = repo_root / proof["logs"]["stderr"]["path"]
    assert stdout_log.exists()
    assert stderr_log.exists()
    assert proof["stdout_sha256"] == hashlib.sha256(stdout_log.read_bytes()).hexdigest()
    assert proof["stderr_sha256"] == hashlib.sha256(stderr_log.read_bytes()).hexdigest()

    second_calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary = _load_summary(repo_root)

    assert required_display not in second_calls
    assert _summary_entry(summary, ENTRY_REQUIRED_REGRESSIONS)["execution_mode"] == "reused_success_cache"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda repo_root: _success_log_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS, "stdout").write_text(
            "changed stdout\n",
            encoding="utf-8",
        ),
    ],
)
def test_required_bad_stdout_log_forces_group_rerun(monkeypatch, tmp_path, mutate):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    _seed_required_or_startup_success_cache(
        module,
        repo_root,
        command_plan,
        ENTRY_REQUIRED_REGRESSIONS,
    )

    mutate(repo_root)
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])

    assert required_display in calls
    assert _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)["execution_mode"] == "executed"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda repo_root: _proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).unlink(),
        lambda repo_root: _proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).write_text(
            "{bad json",
            encoding="utf-8",
        ),
    ],
)
def test_required_bad_proof_file_invalidates_success_cache_without_runner(monkeypatch, tmp_path, mutate):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    _seed_required_or_startup_success_cache(
        module,
        repo_root,
        command_plan,
        ENTRY_REQUIRED_REGRESSIONS,
    )
    success_cache = json.loads(_success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8"))
    assert "evidence/QualityGate/required_regressions.json" in {
        str(row["path"]) for row in success_cache["output_files"]
    }

    mutate(repo_root)
    decision = _reuse_decision_for(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)

    assert decision["decision"] == "run"
    assert decision["reason"] == "previous output files missing or hash mismatch"


@pytest.mark.parametrize(
    "changed_path",
    [
        "tests/test_run_quality_gate.py",
        "scripts/sync_debt_ledger.py",
        "tools/test_registry.py",
        "tools/quality_gate_shared.py",
        "tools/quality_gate_support.py",
        "tools/check_full_test_debt.py",
        "tools/collect_full_test_debt.py",
        "tools/git_hook_checks.py",
        "scripts/run_quality_gate.py",
        "tools/long_gate_cache.py",
        "tools/long_gate_collect.py",
        "tools/long_gate_fingerprint.py",
        "tools/long_gate_full_test_debt.py",
        "tools/long_gate_manifest.py",
        "tools/long_gate_paths.py",
        "tools/long_gate_schema.py",
        "tools/long_gate_summary.py",
        "tools/quality_gate_entries.py",
        "tools/quality_gate_ledger.py",
        "tools/quality_gate_operations.py",
        "tools/quality_gate_scan.py",
        "tools/test_debt_registry.py",
        "pyproject.toml",
        "requirements.txt",
        "core/services/example.py",
        "web/routes/example.py",
        "data/repositories/example.py",
        "plugins/example.py",
        "app.py",
        "app_new_ui.py",
        "config.py",
        "schema.sql",
        "templates/base.html",
        "web_new_test/templates/base.html",
        "static/app.css",
        "web_new_test/static/style.css",
        "templates_excel/批次信息.xlsx",
        "static/docs/scheduler_manual.md",
        "web_new_test/static/docs/scheduler_manual.md",
        "docs/frontend_manual_audit_and_rewrite_blueprint.md",
        ".limcode/skills/aps-full-selftest/scripts/run_full_selftest.py",
        ".limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md",
        "evidence/README.md",
        "evidence/current/README.md",
        "audit/2026-05/README.md",
        "开发文档/开发文档.md",
        "开发文档/阶段留痕与验收记录.md",
        "开发文档/技术债务治理台账.md",
    ],
)
def test_required_tracked_scope_changes_update_fingerprint(tmp_path, changed_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    before = _fingerprint_for(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)

    _write_file(repo_root, changed_path)
    after = _fingerprint_for(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)

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
        "APS_STATIC_VERSION",
        "SECRET_KEY",
        "CI",
        "PATH",
        "PYTHONPATH",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
        "PYTEST_ADDOPTS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTEST_PLUGINS",
    ],
)
def test_required_environment_changes_update_fingerprint(monkeypatch, tmp_path, env_key):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    if env_key != "PATH":
        monkeypatch.delenv(env_key, raising=False)
    before = _fingerprint_for(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)

    if env_key == "PATH":
        current_path = os.environ.get("PATH", "")
        monkeypatch.setenv(env_key, f"{current_path}{os.pathsep}/tmp/next7-path")
    else:
        monkeypatch.setenv(env_key, f"next7-{env_key.lower()}")
    after = _fingerprint_for(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)

    assert before["hash"] != after["hash"]
    assert after["components"]["environment"]["values"][env_key] == os.environ.get(env_key)


def test_unrelated_markdown_change_does_not_invalidate_required(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    _seed_required_or_startup_success_cache(
        module,
        repo_root,
        command_plan,
        ENTRY_REQUIRED_REGRESSIONS,
    )

    _write_file(repo_root, "notes/unrelated.md", "# unrelated\n")
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])

    assert required_display not in calls
    assert _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)["execution_mode"] == (
        "reused_success_cache"
    )


def test_required_invalidation_keeps_startup_success_cache_reuse(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    monkeypatch.delenv("CI", raising=False)
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)

    monkeypatch.setenv("CI", "next7-required-only")
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary = _load_summary(repo_root)

    assert required_display in calls
    assert startup_display not in calls
    assert _summary_entry(summary, ENTRY_REQUIRED_REGRESSIONS)["execution_mode"] == "executed"
    assert _summary_entry(summary, ENTRY_STARTUP_RUNTIME_REGRESSIONS)["execution_mode"] == "reused_success_cache"


def test_required_failure_does_not_refresh_success_cache_or_run_later_startup(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    monkeypatch.delenv("CI", raising=False)
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)
    previous_success = _success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        module,
        "_run_command",
        _fake_successful_command(
            command_plan,
            repo_root,
            calls,
            fail_entry_ids=(ENTRY_REQUIRED_REGRESSIONS,),
        ),
    )

    monkeypatch.setenv("CI", "next7-required-fails")
    with pytest.raises(module.QualityGateError):
        module.main(["--long-gate-cache"])

    assert required_display in calls
    assert startup_display not in calls
    assert _success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8") == previous_success


def test_explain_does_not_write_required_proof(monkeypatch, tmp_path, capsys):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root

    assert module.main(["--long-gate-cache-explain"]) == 0

    assert "required_regressions" in capsys.readouterr().out
    assert not _proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).exists()


def test_no_cache_ignores_existing_required_cache_and_does_not_write_proof(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    _seed_required_or_startup_success_cache(
        module,
        repo_root,
        command_plan,
        ENTRY_REQUIRED_REGRESSIONS,
    )
    _proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).unlink()

    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--no-long-gate-cache"])

    assert required_display in calls
    assert not _proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).exists()


def test_force_rerun_required_executes_group_instead_of_reusing(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)

    calls = _run_gate_with_fake_commands(
        module,
        monkeypatch,
        repo_root,
        command_plan,
        ["--long-gate-cache", "--long-gate-force-rerun", ENTRY_REQUIRED_REGRESSIONS],
    )
    required_summary = _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)

    assert required_display in calls
    assert startup_display not in calls
    assert required_summary["execution_mode"] == "executed"
    assert required_summary["reason"] == "forced by --long-gate-force-rerun required_regressions"


def test_force_rerun_all_executes_required_and_keeps_later_entries_planned(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)

    calls = _run_gate_with_fake_commands(
        module,
        monkeypatch,
        repo_root,
        command_plan,
        ["--long-gate-cache", "--long-gate-force-rerun-all"],
    )
    summary = _load_summary(repo_root)

    assert "python -m pytest --collect-only -q tests" in calls
    assert "python tools/check_full_test_debt.py" in calls
    assert required_display in calls
    assert startup_display in calls
    assert _summary_entry(summary, ENTRY_REQUIRED_REGRESSIONS)["reason"] == "forced by --long-gate-force-rerun-all"
    assert _summary_entry(summary, ENTRY_STARTUP_RUNTIME_REGRESSIONS)["reason"] == (
        "forced by --long-gate-force-rerun-all"
    )
    for entry_id in [
        "ruff_check_full",
        "pyright_gate_full",
        "pyright_tools_full",
        "architecture_fitness",
        "debt_ledger_sync",
        "quickref_vs_routes",
    ]:
        assert _summary_entry(summary, entry_id)["cache_status"] == "planned"
        assert not _success_path(repo_root, entry_id).exists()
