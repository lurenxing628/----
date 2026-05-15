from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Sequence

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
from tools import long_gate_fingerprint as fingerprint_mod
from tools import quality_gate_shared
from tools.long_gate_fingerprint import fingerprint_entry
from tools.long_gate_manifest import (
    ENTRY_REQUIRED_REGRESSIONS,
    ENTRY_STARTUP_RUNTIME_REGRESSIONS,
)
from tools.test_registry import iter_required_tests


def _call_displays(calls: Sequence[Dict[str, object]]) -> List[str]:
    return [str(call["display"]) for call in calls]


def _call_by_display(calls: Sequence[Dict[str, object]], display: str) -> Dict[str, object]:
    for call in calls:
        if str(call["display"]) == display:
            return dict(call)
    raise AssertionError(f"missing call: {display}")


def _seed_required_success(module, monkeypatch, repo_root: Path, command_plan: Sequence[Dict[str, object]]) -> None:
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
    assert required_entry["output_result_files"] == ["evidence/QualityGate/required_regressions.json"]
    assert "groups" not in required_entry
    assert "required_regression_group_coverage" not in required_entry
    assert "required_regression_group_scope_policy" not in required_entry
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
        "web/routes/domains/scheduler/scheduler_config*.py",
        "web/bootstrap/*.py",
        "web/bootstrap/**/*.py",
        "web/routes/system_*.py",
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
        "docs/**/*.md",
        ".gitignore",
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
        "tests/long_gate_cache_helpers.py",
        "tests/ui_geometry_contract_data.py",
    ]:
        assert path in all_scopes
    assert "tools/quality_gate_*.py" in all_scopes
    assert "tools/long_gate_*.py" in all_scopes
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
        "APS_BROWSER_SMOKE_REQUIRED",
        "chrome_executable_resolution",
        "chrome_version",
        "chrome_executable_identity",
        "chrome_headless_preflight",
        "node_executable_realpath",
        "node_version",
        "node_browser_runtime_capability",
        "PATH",
        "NODE_OPTIONS",
        "CI",
    ]:
        assert env_key in required["env_keys"]
    assert "audit/**/*.md" not in required["input_file_scopes"]
    assert "开发文档/**/*.md" not in required["input_file_scopes"]
    assert required["output_result_files"] == ["evidence/QualityGate/required_regressions.json"]


def test_required_success_writes_parent_proof_and_reuses_next_run(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)

    first_calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    first_displays = _call_displays(first_calls)
    proof = json.loads(_proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8"))
    success_cache = json.loads(_success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8"))
    first_summary = _load_summary(repo_root)
    manifest = _manifest_for(command_plan, repo_root)
    required_entry = _entry_by_id(manifest, ENTRY_REQUIRED_REGRESSIONS)
    required_index = next(
        index
        for index, entry in enumerate(manifest["entries"], start=1)
        if entry["entry_id"] == ENTRY_REQUIRED_REGRESSIONS
    )

    assert required_display in first_displays
    collect_call = _call_by_display(first_calls, "python -m pytest --collect-only -q tests")
    full_debt_call = _call_by_display(first_calls, "python tools/check_full_test_debt.py")
    required_call = _call_by_display(first_calls, required_display)
    assert collect_call["capture_output"] is True
    assert full_debt_call["capture_output"] is True
    assert required_call["args"] == [str(arg) for arg in module._resolve_command_args(required_entry)]
    assert required_call["args"][-len(required_entry["args"][4:]) :] == required_entry["args"][4:]
    assert required_call["capture_output"] == bool(required_entry["capture_output"])
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
    assert "groups" not in proof
    assert proof["stdout_log_path"] == "evidence/QualityGate/long_gate/logs/required_regressions.stdout.log"
    assert proof["stderr_log_path"] == "evidence/QualityGate/long_gate/logs/required_regressions.stderr.log"
    assert {str(row["path"]) for row in success_cache["output_files"]} == {
        "evidence/QualityGate/required_regressions.json"
    }
    assert _summary_entry(first_summary, ENTRY_REQUIRED_REGRESSIONS)["execution_mode"] == "executed"
    assert "required_regressions_groups" not in _summary_entry(first_summary, ENTRY_REQUIRED_REGRESSIONS)

    second_calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    second_displays = _call_displays(second_calls)
    summary = _load_summary(repo_root)

    assert required_display not in second_displays
    assert _summary_entry(summary, ENTRY_REQUIRED_REGRESSIONS)["execution_mode"] == "reused_success_cache"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda repo_root: _success_log_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS, "stdout").write_text(
            "tampered\n",
            encoding="utf-8",
        ),
        lambda repo_root: _proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).write_text(
            "{bad json",
            encoding="utf-8",
        ),
    ],
)
def test_required_tampered_parent_cache_reruns_parent(monkeypatch, tmp_path, mutate):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)

    mutate(repo_root)
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary_entry = _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)

    assert required_display in _call_displays(calls)
    assert summary_entry["execution_mode"] == "executed"
    assert "required_regressions_groups" not in summary_entry


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
        "tests/long_gate_cache_helpers.py",
        "tests/ui_geometry_contract_data.py",
        ".gitignore",
        "pyproject.toml",
        "requirements.txt",
        "core/services/example.py",
        "web/routes/domains/scheduler/scheduler_config.py",
        "core/services/scheduler/config/config_field_spec.py",
        "web/bootstrap/request_services.py",
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
    required_entry = _entry_by_id(_manifest_for(command_plan, repo_root), ENTRY_REQUIRED_REGRESSIONS)
    env_overlay = dict(required_entry.get("env_overlay") or {})
    if env_key != "PATH":
        monkeypatch.delenv(env_key, raising=False)
    before = _fingerprint_for(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)

    if env_key == "PATH":
        current_path = os.environ.get("PATH", "")
        monkeypatch.setenv(env_key, f"{current_path}{os.pathsep}/tmp/next7-path")
    else:
        monkeypatch.setenv(env_key, f"next7-{env_key.lower()}")
    after = _fingerprint_for(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)

    if env_key in env_overlay:
        assert before["hash"] == after["hash"]
        assert after["components"]["environment"]["values"][env_key] == env_overlay[env_key]
        return

    assert before["hash"] != after["hash"]
    assert after["components"]["environment"]["values"][env_key] == os.environ.get(env_key)


@pytest.mark.parametrize("entry_id", [ENTRY_REQUIRED_REGRESSIONS, "full_test_debt"])
def test_browser_runtime_fingerprint_changes_update_cache_key(monkeypatch, tmp_path, entry_id):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    monkeypatch.setattr(fingerprint_mod, "_chrome_version", lambda strict=False, environment=None: "Chrome 1")
    monkeypatch.setattr(fingerprint_mod, "_chrome_executable_identity", lambda strict=False, environment=None: "identity-1")
    monkeypatch.setattr(fingerprint_mod, "_chrome_headless_preflight", lambda strict=False, environment=None: "preflight-1")
    before = _fingerprint_for(command_plan, repo_root, entry_id)

    monkeypatch.setattr(fingerprint_mod, "_chrome_version", lambda strict=False, environment=None: "Chrome 2")
    monkeypatch.setattr(fingerprint_mod, "_chrome_executable_identity", lambda strict=False, environment=None: "identity-2")
    monkeypatch.setattr(fingerprint_mod, "_chrome_headless_preflight", lambda strict=False, environment=None: "preflight-2")
    after = _fingerprint_for(command_plan, repo_root, entry_id)

    assert before["hash"] != after["hash"]


def test_required_gitignore_change_reruns_parent(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)

    _write_file(repo_root, ".gitignore", "evidence/QualityGate/\n")
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary_entry = _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)

    assert required_display in _call_displays(calls)
    assert summary_entry["execution_mode"] == "executed"


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

    assert required_display not in _call_displays(calls)
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
    displays = _call_displays(calls)

    assert required_display in displays
    assert startup_display not in displays
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
    calls: List[Dict[str, object]] = []
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

    displays = _call_displays(calls)
    assert required_display in displays
    assert startup_display not in displays
    assert _success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8") == previous_success


def test_explain_does_not_write_required_proof(monkeypatch, tmp_path, capsys):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root

    assert module.main(["--long-gate-cache-explain"]) == 0

    output = capsys.readouterr().out
    assert "required_regressions" in output
    assert "required_regressions_groups" not in output
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

    assert required_display in _call_displays(calls)
    assert not _proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).exists()


def test_force_rerun_required_executes_parent_instead_of_reusing(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)

    calls = _run_gate_with_fake_commands(
        module,
        monkeypatch,
        repo_root,
        command_plan,
        ["--long-gate-cache", "--long-gate-force-rerun", ENTRY_REQUIRED_REGRESSIONS],
    )
    required_summary = _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)
    displays = _call_displays(calls)

    assert required_display in displays
    assert startup_display not in displays
    assert required_summary["execution_mode"] == "executed"
    assert required_summary["reason"] == "forced by --long-gate-force-rerun required_regressions"


def test_force_rerun_all_executes_required_and_keeps_later_entries_planned(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)

    calls = _run_gate_with_fake_commands(
        module,
        monkeypatch,
        repo_root,
        command_plan,
        ["--long-gate-cache", "--long-gate-force-rerun-all"],
    )
    summary = _load_summary(repo_root)
    displays = _call_displays(calls)

    assert "python -m pytest --collect-only -q tests" in displays
    assert "python tools/check_full_test_debt.py" in displays
    assert required_display in displays
    assert startup_display in displays
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


def test_required_parent_scope_includes_group_registry_scope_union(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    manifest = _manifest_for(command_plan, repo_root)
    required_entry = _entry_by_id(manifest, ENTRY_REQUIRED_REGRESSIONS)

    before_parent = fingerprint_entry(required_entry, str(repo_root))
    _write_file(
        repo_root,
        "web/routes/domains/scheduler/scheduler_config_feedback.py",
        "CONFIG_SCOPE_MARKER = True\n",
    )
    after_parent = fingerprint_entry(required_entry, str(repo_root))

    assert before_parent["hash"] != after_parent["hash"]


def test_required_parent_entry_still_matches_real_command_plan():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = _manifest_for(command_plan, Path(quality_gate_shared.REPO_ROOT))
    required_entry = _entry_by_id(manifest, ENTRY_REQUIRED_REGRESSIONS)
    command_by_display = {command["display"]: command for command in command_plan}

    assert required_entry["display"] in command_by_display
    assert required_entry["args"] == command_by_display[required_entry["display"]]["args"]
    assert required_entry["args"][4:] == iter_required_tests()
    assert required_entry["output_result_files"] == ["evidence/QualityGate/required_regressions.json"]
