from __future__ import annotations

import hashlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

import pytest

from tools import quality_gate_shared
from tools.long_gate_cache import evaluate_reuse
from tools.long_gate_fingerprint import fingerprint_entry
from tools.long_gate_manifest import (
    ENTRY_REQUIRED_REGRESSIONS,
    ENTRY_STARTUP_RUNTIME_REGRESSIONS,
    build_manifest_from_quality_gate_plan,
)


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def _import_run_quality_gate():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("scripts.run_quality_gate", None)
    return importlib.import_module("scripts.run_quality_gate")


def _real_quality_gate_plan() -> list[dict]:
    return list(quality_gate_shared.build_quality_gate_command_plan())


def _manifest_for(command_plan: Sequence[dict], repo_root: Path) -> dict:
    return build_manifest_from_quality_gate_plan(command_plan, repo_root=str(repo_root))


def _entry_by_id(manifest: dict, entry_id: str) -> dict:
    for entry in manifest["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError(f"missing entry_id: {entry_id}")


def _entry_display(command_plan: Sequence[dict], repo_root: Path, entry_id: str) -> str:
    return str(_entry_by_id(_manifest_for(command_plan, repo_root), entry_id)["display"])


def _fingerprint_for(command_plan: Sequence[dict], repo_root: Path, entry_id: str) -> dict:
    return fingerprint_entry(_entry_by_id(_manifest_for(command_plan, repo_root), entry_id), str(repo_root))


def _reuse_decision_for(command_plan: Sequence[dict], repo_root: Path, entry_id: str) -> dict:
    entry = _entry_by_id(_manifest_for(command_plan, repo_root), entry_id)
    fingerprint = fingerprint_entry(entry, str(repo_root))
    return evaluate_reuse(entry, fingerprint, repo_root=str(repo_root))["decision"]


def _required_proof_path(repo_root: Path) -> Path:
    return repo_root / "evidence" / "QualityGate" / "required_regressions.json"


def _startup_proof_path(repo_root: Path) -> Path:
    return repo_root / "evidence" / "QualityGate" / "startup_runtime_regressions.json"


def _success_path(repo_root: Path, entry_id: str) -> Path:
    return repo_root / "evidence" / "QualityGate" / "long_gate" / "results" / f"{entry_id}.success.json"


def _summary_path(repo_root: Path) -> Path:
    return repo_root / "evidence" / "QualityGate" / "long_gate" / "summary.json"


def _load_summary(repo_root: Path) -> dict:
    return json.loads(_summary_path(repo_root).read_text(encoding="utf-8"))


def _summary_entry(summary: dict, entry_id: str) -> dict:
    for entry in summary["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError(f"missing summary entry: {entry_id}")


def _write_file(repo_root: Path, rel_path: str, text: str = "changed\n") -> Path:
    path = repo_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _patch_gate_environment(monkeypatch, module, repo_root: Path, *, statuses: Sequence[Sequence[str]] = ()) -> None:
    if not (repo_root / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    status_rows = [list(item) for item in list(statuses or [[] for _ in range(30)])]

    def next_status() -> list[str]:
        if status_rows:
            return status_rows.pop(0)
        return []

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
    monkeypatch.setattr(module, "_git_status_lines", next_status)
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    monkeypatch.setattr(module, "pytest_distribution_version", lambda strict=False: "pytest 8.3.5")


def _summary_payload(token: str = "ok") -> dict:
    return {
        "schema_version": 1,
        "status": "passed",
        "active_xfail_count": 0,
        "collected_count": 1,
        "collection_error_count": 0,
        "fixed_count": 0,
        "max_registered_xfail": 0,
        "unexpected_failure_count": 0,
        "active_xfail_entries": [],
        "token": token,
    }


def _write_full_test_debt_outputs(repo_root: Path, token: str = "ok") -> None:
    current = repo_root / "evidence" / "QualityGate" / "current_full_test_debt.json"
    summary = repo_root / "evidence" / "QualityGate" / "full_test_debt_summary.json"
    current.parent.mkdir(parents=True, exist_ok=True)
    current.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "baseline_kind": "after_main_style_isolation",
                "importable": False,
                "importable_blockers": [],
                "generated_at": "2026-05-13T00:00:00+08:00",
                "head_sha": "deadbeef",
                "collector_argv": ["--baseline-kind", "after_main_style_isolation", "--", "tests"],
                "git_status_short_before": [],
                "worktree_clean_before": True,
                "python_executable": sys.executable,
                "python_version": sys.version.splitlines()[0],
                "pytest_version": "8.3.5",
                "pytest_args": ["tests", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"],
                "exitstatus": 0,
                "collected_nodeids": ["tests/test_cached_collect.py::test_cached_collect"],
                "collection_errors": [],
                "reports": [],
                "summary": {
                    "collected_count": 1,
                    "failed_nodeid_count": 0,
                    "collection_error_count": 0,
                    "outcome_counts": {},
                    "classification_counts": {
                        "candidate_test_debt": 0,
                        "main_style_isolation_candidate": 0,
                        "required_or_quality_gate_self_failure": 0,
                    },
                },
                "classifications": {
                    "candidate_test_debt": [],
                    "main_style_isolation_candidate": [],
                    "required_or_quality_gate_self_failure": [],
                },
                "token": token,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    summary.write_text(json.dumps(_summary_payload(token), ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _fake_successful_command(
    command_plan: Sequence[dict],
    repo_root: Path,
    calls: list[str],
    *,
    fail_required: bool = False,
) -> Callable[..., dict]:
    manifest = _manifest_for(command_plan, repo_root)
    required_display = _entry_by_id(manifest, ENTRY_REQUIRED_REGRESSIONS)["display"]
    startup_display = _entry_by_id(manifest, ENTRY_STARTUP_RUNTIME_REGRESSIONS)["display"]
    full_debt_runs = {"count": 0}

    def fake_run_command(display, args, capture_output=False):
        calls.append(str(display))
        if display == "python -m pytest --collect-only -q tests":
            return {
                "stdout": "tests/test_cached_collect.py::test_cached_collect\n",
                "stderr": "",
                "returncode": 0,
            }
        if display == "python tools/check_full_test_debt.py":
            full_debt_runs["count"] += 1
            _write_full_test_debt_outputs(repo_root, token=f"run-{full_debt_runs['count']}")
            return {
                "stdout": json.dumps(_summary_payload("runner"), ensure_ascii=False),
                "stderr": "[check-full-test-debt] ok\n",
                "returncode": 0,
            }
        if display == "python -m ruff --version":
            return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
        if display == "python -m pyright --version":
            return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
        if display == required_display:
            if fail_required:
                return {"stdout": "required failed\n", "stderr": "boom\n", "returncode": 1}
            return {"stdout": "127 files passed in 2.34s\n", "stderr": "", "returncode": 0}
        if display == startup_display:
            return {"stdout": "16 passed in 1.23s\n", "stderr": "", "returncode": 0}
        return {"stdout": "", "stderr": "", "returncode": 0}

    return fake_run_command


def _run_gate_with_fake_commands(
    module,
    monkeypatch,
    repo_root: Path,
    command_plan: Sequence[dict],
    args: Sequence[str],
    *,
    fail_required: bool = False,
) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(
        module,
        "_run_command",
        _fake_successful_command(command_plan, repo_root, calls, fail_required=fail_required),
    )
    assert module.main(list(args)) == 0
    return calls


def _seed_required_success(module, monkeypatch, repo_root: Path, command_plan: Sequence[dict]) -> None:
    _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    assert _required_proof_path(repo_root).exists()
    assert _success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).exists()


def _success_log_path(repo_root: Path, stream: str) -> Path:
    success = json.loads(_success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8"))
    return repo_root / str(success[f"{stream}_log_path"]).replace("/", "/")


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
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)

    first_calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])
    proof = json.loads(_required_proof_path(repo_root).read_text(encoding="utf-8"))
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
        lambda repo_root: _success_log_path(repo_root, "stdout").write_text("changed stdout\n", encoding="utf-8"),
    ],
)
def test_required_bad_stdout_log_forces_group_rerun(monkeypatch, tmp_path, mutate):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)

    mutate(repo_root)
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])

    assert required_display in calls
    assert _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)["execution_mode"] == "executed"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda repo_root: _required_proof_path(repo_root).unlink(),
        lambda repo_root: _required_proof_path(repo_root).write_text("{bad json", encoding="utf-8"),
    ],
)
def test_required_bad_proof_file_invalidates_success_cache_without_runner(monkeypatch, tmp_path, mutate):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    _seed_required_success(module, monkeypatch, repo_root, command_plan)
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
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)

    _write_file(repo_root, "notes/unrelated.md", "# unrelated\n")
    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--long-gate-cache"])

    assert required_display not in calls
    assert _summary_entry(_load_summary(repo_root), ENTRY_REQUIRED_REGRESSIONS)["execution_mode"] == (
        "reused_success_cache"
    )


def test_required_invalidation_keeps_startup_success_cache_reuse(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    monkeypatch.delenv("CI", raising=False)
    _patch_gate_environment(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
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
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    monkeypatch.delenv("CI", raising=False)
    _patch_gate_environment(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)
    previous_success = _success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        module,
        "_run_command",
        _fake_successful_command(command_plan, repo_root, calls, fail_required=True),
    )

    monkeypatch.setenv("CI", "next7-required-fails")
    with pytest.raises(module.QualityGateError):
        module.main(["--long-gate-cache"])

    assert required_display in calls
    assert startup_display not in calls
    assert _success_path(repo_root, ENTRY_REQUIRED_REGRESSIONS).read_text(encoding="utf-8") == previous_success


def test_explain_does_not_write_required_proof(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))

    assert module.main(["--long-gate-cache-explain"]) == 0

    assert "required_regressions" in capsys.readouterr().out
    assert not _required_proof_path(repo_root).exists()


def test_no_cache_ignores_existing_required_cache_and_does_not_write_proof(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    required_display = _entry_display(command_plan, repo_root, ENTRY_REQUIRED_REGRESSIONS)
    _seed_required_success(module, monkeypatch, repo_root, command_plan)
    _required_proof_path(repo_root).unlink()

    calls = _run_gate_with_fake_commands(module, monkeypatch, repo_root, command_plan, ["--no-long-gate-cache"])

    assert required_display in calls
    assert not _required_proof_path(repo_root).exists()


def test_force_rerun_required_executes_group_instead_of_reusing(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
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
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _real_quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
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
