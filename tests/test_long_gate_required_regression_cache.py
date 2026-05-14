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
from tools.long_gate_fingerprint import fingerprint_entry
from tools.long_gate_manifest import (
    ENTRY_REQUIRED_REGRESSIONS,
    ENTRY_STARTUP_RUNTIME_REGRESSIONS,
)


def _seed_required_success(module, monkeypatch, repo_root: Path, command_plan: Sequence[dict]) -> None:
    _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    assert _proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).exists()
    assert _success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).exists()


def _required_group_entries(command_plan: Sequence[dict], repo_root: Path) -> list[dict]:
    manifest = _manifest_for(command_plan, repo_root)
    return [dict(group) for group in _entry_by_id(manifest, ENTRY_REQUIRED_REGRESSIONS)["groups"]]


def _required_group_displays(command_plan: Sequence[dict], repo_root: Path) -> list[str]:
    return [str(group["display"]) for group in _required_group_entries(command_plan, repo_root)]


def _required_group_proof_paths(command_plan: Sequence[dict], repo_root: Path) -> list[Path]:
    paths = []
    for group in _required_group_entries(command_plan, repo_root):
        paths.extend(repo_root / str(path) for path in list(group.get("output_result_files") or []))
    return paths


def _assert_required_group_scope_rows_match_manifest(
    rows: Sequence[dict],
    groups: Sequence[dict],
    repo_root=None,
) -> None:
    rows_by_group = {row["group_id"]: row for row in rows}
    assert set(rows_by_group) == {group["group_id"] for group in groups}
    for group in groups:
        row = rows_by_group[group["group_id"]]
        assert row["target_paths"] == group["target_paths"]
        assert row["scope_policy_hash"] == group["scope_policy_hash"]
        assert row["input_file_scopes"] == group["input_file_scopes"]
        assert row["config_file_scopes"] == group["config_file_scopes"]
        assert row["tool_file_scopes"] == group["tool_file_scopes"]
        assert row["dependency_file_scopes"] == group["dependency_file_scopes"]
        assert row["env_keys"] == group["env_keys"]
        assert row["proof_path"]
        assert row["proof_sha256"]
        if repo_root is not None:
            expected_proof_path = str(group["output_result_files"][0])
            assert row["proof_path"] == expected_proof_path
            proof_path = repo_root / expected_proof_path
            assert proof_path.exists()
            assert row["proof_sha256"] == hashlib.sha256(proof_path.read_bytes()).hexdigest()


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
    scheduler_config = next(group for group in required["groups"] if group["group_id"] == "scheduler_config")
    quality_gate = next(group for group in required["groups"] if group["group_id"] == "quality_gate")
    analysis = next(
        group for group in required["groups"] if group["group_id"] == "scheduler_analysis_gantt_reports_week_plan"
    )
    ui_layout = next(group for group in required["groups"] if group["group_id"] == "ui_layout_presenters_system")
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
        "chrome_executable_resolution",
        "node_executable_realpath",
        "node_version",
        "PATH",
    ]:
        assert env_key in required["env_keys"]
    assert "web/routes/domains/scheduler/scheduler_config*.py" in scheduler_config["group_input_file_scopes"]
    assert "tools/long_gate_*.py" in quality_gate["group_tool_file_scopes"]
    assert "tests/long_gate_cache_helpers.py" in quality_gate["group_input_file_scopes"]
    assert {"node_executable_realpath", "node_version", "PATH"} <= set(analysis["group_env_keys"])
    assert "CI" in ui_layout["group_env_keys"]
    assert required["required_regression_group_scope_policy"]["scope_policy_hash"]
    assert "audit/**/*.md" not in required["input_file_scopes"]
    assert "开发文档/**/*.md" not in required["input_file_scopes"]
    assert required["output_result_files"] == [
        "evidence/QualityGate/required_regressions.json",
        *[group["output_result_files"][0] for group in required["groups"]],
    ]


def test_required_success_writes_proof_and_reuses_next_run(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    group_displays = _required_group_displays(command_plan, repo_root)

    first_calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
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

    assert required_display not in first_calls
    assert group_displays
    assert set(group_displays) <= set(first_calls)
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
    assert proof["execution_mode"] == "grouped"
    assert proof["test_count"] == len(required_entry["args"][4:])
    assert proof["required_target_count"] == len(required_entry["args"][4:])
    assert proof["required_target_paths"] == required_entry["args"][4:]
    assert proof["coverage"] == {"missing": [], "duplicates": [], "unknown": []}
    assert proof["group_count"] == 8
    assert proof["group_scope_policy"]["common_input_file_scopes"] == [
        "tests/conftest.py",
        "conftest.py",
        "tests/main_style_regression_runner.py",
        "tests/runtime_cleanup_helper.py",
    ]
    assert proof["group_scope_policy"]["scope_policy_hash"]
    assert {group["group_id"] for group in proof["groups"]} == {
        group["group_id"] for group in required_entry["groups"]
    }
    proof_rows_by_group = {row["group_id"]: row for row in proof["groups"]}
    first_summary_rows = _summary_entry(first_summary, ENTRY_REQUIRED_REGRESSIONS)["required_regressions_groups"]
    summary_rows_by_group = {row["group_id"]: row for row in first_summary_rows}
    _assert_required_group_scope_rows_match_manifest(proof["groups"], required_entry["groups"], repo_root)
    _assert_required_group_scope_rows_match_manifest(first_summary_rows, required_entry["groups"], repo_root)
    for group in required_entry["groups"]:
        row = proof_rows_by_group[group["group_id"]]
        assert row["target_paths"] == group["target_paths"]
        assert row["scope_policy_hash"] == group["scope_policy_hash"]
        assert row["input_file_scopes"] == group["input_file_scopes"]
        assert row["config_file_scopes"] == group["config_file_scopes"]
        assert row["tool_file_scopes"] == group["tool_file_scopes"]
        assert row["dependency_file_scopes"] == group["dependency_file_scopes"]
        assert row["env_keys"] == group["env_keys"]
        summary_row = summary_rows_by_group[group["group_id"]]
        assert summary_row["target_paths"] == group["target_paths"]
        assert summary_row["scope_policy_hash"] == group["scope_policy_hash"]
        assert summary_row["input_file_scopes"] == group["input_file_scopes"]
        assert summary_row["config_file_scopes"] == group["config_file_scopes"]
        assert summary_row["tool_file_scopes"] == group["tool_file_scopes"]
        assert summary_row["dependency_file_scopes"] == group["dependency_file_scopes"]
        assert summary_row["env_keys"] == group["env_keys"]
        group_proof = json.loads((repo_root / group["output_result_files"][0]).read_text(encoding="utf-8"))
        assert group_proof["schema_version"] == module.REQUIRED_REGRESSIONS_GROUP_PROOF_SCHEMA_VERSION
        assert group_proof["target_paths"] == group["target_paths"]
        assert group_proof["scope_policy_hash"] == group["scope_policy_hash"]
        assert group_proof["scope_policy"]["group_input_file_scopes"] == group["group_input_file_scopes"]
        assert group_proof["scope_policy"]["group_tool_file_scopes"] == group["group_tool_file_scopes"]
        assert group_proof["config_file_scopes"] == group["config_file_scopes"]
        assert group_proof["tool_file_scopes"] == group["tool_file_scopes"]
        assert group_proof["dependency_file_scopes"] == group["dependency_file_scopes"]
        assert group_proof["env_keys"] == group["env_keys"]
    assert proof["stdout_log_path"] == "evidence/QualityGate/long_gate/logs/required_regressions.stdout.log"
    assert proof["stderr_log_path"] == "evidence/QualityGate/long_gate/logs/required_regressions.stderr.log"
    stdout_log = repo_root / proof["logs"]["stdout"]["path"]
    stderr_log = repo_root / proof["logs"]["stderr"]["path"]
    assert stdout_log.exists()
    assert stderr_log.exists()
    assert proof["stdout_sha256"] == hashlib.sha256(stdout_log.read_bytes()).hexdigest()
    assert proof["stderr_sha256"] == hashlib.sha256(stderr_log.read_bytes()).hexdigest()
    assert {str(row["path"]) for row in success_cache["output_files"]} >= {
        "evidence/QualityGate/required_regressions.json",
        *[
            str(path.relative_to(repo_root)).replace("\\", "/")
            for path in _required_group_proof_paths(command_plan, repo_root)
        ],
    }

    second_calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary = _load_summary(repo_root)

    assert required_display not in second_calls
    assert not (set(group_displays) & set(second_calls))
    assert _summary_entry(summary, ENTRY_REQUIRED_REGRESSIONS)["execution_mode"] == "reused_success_cache"
    reused_rows = _summary_entry(summary, ENTRY_REQUIRED_REGRESSIONS)["required_regressions_groups"]
    assert {row["execution_mode"] for row in reused_rows} == {"covered_by_parent_reuse"}
    for row in reused_rows:
        group = next(group for group in required_entry["groups"] if group["group_id"] == row["group_id"])
        assert row["scope_policy_hash"] == group["scope_policy_hash"]
        assert row["proof_path"] == group["output_result_files"][0]
        assert row["proof_sha256"] == hashlib.sha256((repo_root / row["proof_path"]).read_bytes()).hexdigest()
        assert row["input_file_scopes"] == group["input_file_scopes"]


def test_required_parent_cache_without_group_proofs_rebuilds_parent(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    group_displays = set(_required_group_displays(command_plan, repo_root))
    _seed_required_success(module, monkeypatch, repo_root, command_plan)
    success_path = _success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS)
    success_cache = json.loads(success_path.read_text(encoding="utf-8"))
    success_cache["output_files"] = [
        row
        for row in success_cache["output_files"]
        if str(row.get("path") or "") == "evidence/QualityGate/required_regressions.json"
    ]
    success_path.write_text(json.dumps(success_cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary_entry = _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)
    refreshed_cache = json.loads(success_path.read_text(encoding="utf-8"))

    assert not (group_displays & set(calls))
    assert summary_entry["execution_mode"] == "grouped"
    assert {row["execution_mode"] for row in summary_entry["required_regressions_groups"]} == {"reused_success_cache"}
    assert {str(row["path"]) for row in refreshed_cache["output_files"]} >= {
        "evidence/QualityGate/required_regressions.json",
        *[
            str(path.relative_to(repo_root)).replace("\\", "/")
            for path in _required_group_proof_paths(command_plan, repo_root)
        ],
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda repo_root: _success_log_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS, "stdout").write_text(
            "changed stdout\n",
            encoding="utf-8",
        ),
    ],
)
def test_required_bad_stdout_log_rebuilds_parent_from_group_caches(monkeypatch, tmp_path, mutate):
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

    mutate(repo_root)
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary_entry = _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)

    assert not (set(_required_group_displays(command_plan, repo_root)) & set(calls))
    assert summary_entry["execution_mode"] == "grouped"
    assert {row["execution_mode"] for row in summary_entry["required_regressions_groups"]} == {
        "reused_success_cache"
    }


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


def test_required_single_group_input_change_only_reruns_that_group(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    groups = _required_group_entries(command_plan, repo_root)
    changed_group = next(group for group in groups if group["group_id"] == "scheduler_config")
    changed_target = changed_group["target_paths"][0]
    _seed_required_or_startup_success_cache(module, repo_root, command_plan, ENTRY_REQUIRED_REGRESSIONS)
    _seed_required_or_startup_success_cache(module, repo_root, command_plan, ENTRY_STARTUP_RUNTIME_REGRESSIONS)

    _write_file(repo_root, changed_target, "def test_changed_group_marker():\n    assert True\n")
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary_entry = _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)
    group_modes = {row["group_id"]: row["execution_mode"] for row in summary_entry["required_regressions_groups"]}

    assert changed_group["display"] in calls
    assert startup_display not in calls
    assert set(_required_group_displays(command_plan, repo_root)) & set(calls) == {changed_group["display"]}
    assert summary_entry["execution_mode"] == "grouped"
    assert group_modes["scheduler_config"] == "executed"
    assert {
        mode for group_id, mode in group_modes.items() if group_id != "scheduler_config"
    } == {"reused_success_cache"}


def test_required_group_specific_business_scope_change_only_reruns_that_group(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    groups = _required_group_entries(command_plan, repo_root)
    changed_group = next(group for group in groups if group["group_id"] == "scheduler_config")
    _seed_required_or_startup_success_cache(module, repo_root, command_plan, ENTRY_REQUIRED_REGRESSIONS)

    _write_file(
        repo_root,
        "web/routes/domains/scheduler/scheduler_config_feedback.py",
        "CONFIG_SCOPE_MARKER = True\n",
    )
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary_entry = _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)
    group_modes = {row["group_id"]: row["execution_mode"] for row in summary_entry["required_regressions_groups"]}

    assert changed_group["display"] in calls
    assert set(_required_group_displays(command_plan, repo_root)) & set(calls) == {changed_group["display"]}
    assert summary_entry["execution_mode"] == "grouped"
    assert group_modes["scheduler_config"] == "executed"
    assert {
        mode for group_id, mode in group_modes.items() if group_id != "scheduler_config"
    } == {"reused_success_cache"}


@pytest.mark.parametrize(
    "changed_path",
    [
        ".github/workflows/quality.yml",
        "tools/check_full_test_debt.py",
    ],
)
def test_required_group_owned_config_and_tool_scope_change_only_reruns_that_group(
    monkeypatch,
    tmp_path,
    changed_path,
):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    groups = _required_group_entries(command_plan, repo_root)
    quality_gate = next(group for group in groups if group["group_id"] == "quality_gate")
    _seed_required_or_startup_success_cache(module, repo_root, command_plan, ENTRY_REQUIRED_REGRESSIONS)

    _write_file(repo_root, changed_path, "QUALITY_GATE_SCOPE_MARKER = True\n")
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary_entry = _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)
    group_modes = {row["group_id"]: row["execution_mode"] for row in summary_entry["required_regressions_groups"]}

    assert quality_gate["display"] in calls
    assert set(_required_group_displays(command_plan, repo_root)) & set(calls) == {quality_gate["display"]}
    assert summary_entry["execution_mode"] == "grouped"
    assert group_modes["quality_gate"] == "executed"
    assert {mode for group_id, mode in group_modes.items() if group_id != "quality_gate"} == {
        "reused_success_cache"
    }
    proof = json.loads(_proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8"))
    _assert_required_group_scope_rows_match_manifest(proof["groups"], groups, repo_root)
    _assert_required_group_scope_rows_match_manifest(summary_entry["required_regressions_groups"], groups, repo_root)
    assert {
        row["group_id"]: row["execution_mode"] for row in proof["groups"]
    } == group_modes
    success_cache = json.loads(_success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8"))
    assert {str(row["path"]) for row in success_cache["output_files"]} >= {
        "evidence/QualityGate/required_regressions.json",
        *[
            str(path.relative_to(repo_root)).replace("\\", "/")
            for path in _required_group_proof_paths(command_plan, repo_root)
        ],
    }


def test_required_common_scope_change_reruns_all_groups(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    group_displays = _required_group_displays(command_plan, repo_root)
    _seed_required_or_startup_success_cache(module, repo_root, command_plan, ENTRY_REQUIRED_REGRESSIONS)

    _write_file(repo_root, "tools/test_registry.py", "COMMON_SCOPE_MARKER = True\n")
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary_entry = _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)

    assert set(group_displays) <= set(calls)
    assert summary_entry["execution_mode"] == "grouped"
    assert {row["execution_mode"] for row in summary_entry["required_regressions_groups"]} == {"executed"}


def test_required_group_specific_scope_not_leaked_to_other_group_fingerprints(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    manifest = _manifest_for(command_plan, repo_root)
    required_entry = _entry_by_id(manifest, ENTRY_REQUIRED_REGRESSIONS)
    scheduler_config = next(group for group in required_entry["groups"] if group["group_id"] == "scheduler_config")
    analysis = next(
        group
        for group in required_entry["groups"]
        if group["group_id"] == "scheduler_analysis_gantt_reports_week_plan"
    )

    before_parent = fingerprint_entry(required_entry, str(repo_root))
    before_config = fingerprint_entry(scheduler_config, str(repo_root))
    before_analysis = fingerprint_entry(analysis, str(repo_root))
    _write_file(
        repo_root,
        "web/routes/domains/scheduler/scheduler_config_feedback.py",
        "CONFIG_SCOPE_MARKER = True\n",
    )
    after_parent = fingerprint_entry(required_entry, str(repo_root))
    after_config = fingerprint_entry(scheduler_config, str(repo_root))
    after_analysis = fingerprint_entry(analysis, str(repo_root))

    assert before_parent["hash"] != after_parent["hash"]
    assert before_config["hash"] != after_config["hash"]
    assert before_analysis["hash"] == after_analysis["hash"]


def test_required_group_proof_tamper_reruns_only_that_group(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    groups = _required_group_entries(command_plan, repo_root)
    tampered_group = groups[0]
    other_group_ids = {str(group["group_id"]) for group in groups if group["group_id"] != tampered_group["group_id"]}
    _seed_required_or_startup_success_cache(module, repo_root, command_plan, ENTRY_REQUIRED_REGRESSIONS)
    old_parent_success = json.loads(_success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8"))
    proof_path = repo_root / tampered_group["output_result_files"][0]
    proof_path.write_text("{bad json", encoding="utf-8")

    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary_entry = _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)

    assert set(_required_group_displays(command_plan, repo_root)) & set(calls) == {tampered_group["display"]}
    assert summary_entry["execution_mode"] == "grouped"
    assert {
        row["execution_mode"]
        for row in summary_entry["required_regressions_groups"]
        if row["group_id"] == tampered_group["group_id"]
    } == {"executed"}
    assert {
        row["execution_mode"]
        for row in summary_entry["required_regressions_groups"]
        if row["group_id"] in other_group_ids
    } == {"reused_success_cache"}
    new_parent_success = json.loads(_success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8"))
    assert new_parent_success["output_files"] != old_parent_success["output_files"]
    assert {
        str(row["path"]) for row in new_parent_success["output_files"]
    } >= {
        "evidence/QualityGate/required_regressions.json",
        *[
            str(path.relative_to(repo_root)).replace("\\", "/")
            for path in _required_group_proof_paths(command_plan, repo_root)
        ],
    }


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
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    quality_gate_display = next(
        group["display"] for group in _required_group_entries(command_plan, repo_root) if group["group_id"] == "quality_gate"
    )
    ui_layout_display = next(
        group["display"]
        for group in _required_group_entries(command_plan, repo_root)
        if group["group_id"] == "ui_layout_presenters_system"
    )
    _seed_required_success(module, monkeypatch, repo_root, command_plan)

    monkeypatch.setenv("CI", "next7-required-only")
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    summary = _load_summary(repo_root)

    assert set(_required_group_displays(command_plan, repo_root)) & set(calls) == {
        quality_gate_display,
        ui_layout_display,
    }
    assert startup_display not in calls
    assert _summary_entry(summary, ENTRY_REQUIRED_REGRESSIONS)["execution_mode"] == "grouped"
    assert _summary_entry(summary, ENTRY_STARTUP_RUNTIME_REGRESSIONS)["execution_mode"] == "reused_success_cache"


def test_required_failure_does_not_refresh_success_cache_or_run_later_startup(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    monkeypatch.delenv("CI", raising=False)
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    first_group_display = _required_group_displays(command_plan, repo_root)[0]
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

    assert first_group_display in calls
    assert startup_display not in calls
    assert _success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8") == previous_success


def test_explain_does_not_write_required_proof(monkeypatch, tmp_path, capsys):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan

    assert module.main(["--long-gate-cache-explain"]) == 0

    assert "required_regressions" in capsys.readouterr().out
    assert not _proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).exists()
    assert not any(path.exists() for path in _required_group_proof_paths(command_plan, repo_root))


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
    for path in _required_group_proof_paths(command_plan, repo_root):
        path.unlink()

    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--no-long-gate-cache"])

    assert required_display in calls
    assert not _proof_path_for_entry(repo_root, ENTRY_REQUIRED_REGRESSIONS).exists()
    assert not any(path.exists() for path in _required_group_proof_paths(command_plan, repo_root))


def test_force_rerun_required_executes_group_instead_of_reusing(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    group_displays = _required_group_displays(command_plan, repo_root)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)

    calls = _run_gate_with_fake_commands(
        module,
        monkeypatch,
        repo_root,
        command_plan,
        ["--long-gate-cache", "--long-gate-force-rerun", ENTRY_REQUIRED_REGRESSIONS],
    )
    required_summary = _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)

    assert set(group_displays) <= set(calls)
    assert startup_display not in calls
    assert required_summary["execution_mode"] == "grouped"
    assert required_summary["reason"] == "forced by --long-gate-force-rerun required_regressions"
    assert {row["decision"] for row in required_summary["required_regressions_groups"]} == {"run"}


def test_force_rerun_all_executes_required_and_keeps_later_entries_planned(monkeypatch, tmp_path):
    ctx = _prepare_gate_run_context(monkeypatch, tmp_path)
    module = ctx.module
    repo_root = ctx.repo_root
    command_plan = ctx.command_plan
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    group_displays = _required_group_displays(command_plan, repo_root)
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
    assert set(group_displays) <= set(calls)
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
