"""回归测试：tools/git_hook_checks 与 git_hook_cache 的 git 钩子行为——_project_python_executable 必须用项目 .venv（缺失则报错不退回系统 Python）、run-quality-gate/run-final-quality-gate/run-fast-static-precheck 用项目 Python 与强制 UTF8 环境调对应脚本、按 pre-push stdin/PRE_COMMIT_* ref 计算范围与每日门禁缓存（命中跳过、成功才写、失败/脏工作区不写）、staged-only ruff 缓存、_blocked_paths 拦截本地启动日志与门禁运行产物（含 Windows 路径归一化），以及 .pre-commit-config.yaml 钩子接线契约。"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest
from pre_commit.clientlib import load_config

from tools import git_hook_cache, git_hook_checks


@pytest.fixture(autouse=True)
def _clear_pre_commit_push_env(monkeypatch) -> None:
    for key in (
        "PRE_COMMIT_FROM_REF",
        "PRE_COMMIT_TO_REF",
        "PRE_COMMIT_REMOTE_BRANCH",
        "PRE_COMMIT_LOCAL_BRANCH",
        "PRE_COMMIT_REMOTE_NAME",
    ):
        monkeypatch.delenv(key, raising=False)


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_root, check=True)


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.invalid")
    _git(repo_root, "config", "user.name", "Test User")


def _commit_all(repo_root: Path, message: str = "init") -> None:
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", message)


def test_project_python_executable_prefers_windows_venv(monkeypatch, tmp_path: Path) -> None:
    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks.os, "name", "nt")

    assert git_hook_checks._project_python_executable() == str(python_path)


def test_project_python_executable_prefers_posix_venv(monkeypatch, tmp_path: Path) -> None:
    python_path = tmp_path / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    windows_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    windows_path.parent.mkdir(parents=True)
    windows_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks.os, "name", "posix")

    assert git_hook_checks._project_python_executable() == str(python_path)


def test_project_python_executable_requires_project_venv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)

    try:
        git_hook_checks._project_python_executable()
    except RuntimeError as exc:
        assert "找不到项目 .venv" in str(exc)
    else:
        raise AssertionError("missing project .venv must fail instead of using system Python")


def test_run_quality_gate_command_uses_daily_gate_and_utf8_env(monkeypatch, tmp_path: Path) -> None:
    calls = []
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setenv("APS_SKIP_QUALITY_GATE", "1")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "0")
    monkeypatch.setenv("PYTHONUTF8", "0")
    monkeypatch.setenv("PYTHONIOENCODING", "gbk")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)
    monkeypatch.setattr(
        git_hook_checks.git_hook_cache,
        "pre_push_daily_cache_hit",
        lambda executable, remote_name="", remote_ref="", scope_payload=None, ref_contexts=None: False,
    )
    monkeypatch.setattr(
        git_hook_checks.git_hook_cache,
        "write_pre_push_daily_cache",
        lambda executable, remote_name="", remote_ref="", scope_payload=None, ref_contexts=None: None,
    )

    def fake_call(command, *, cwd, env):
        calls.append((list(command), str(cwd), dict(env)))
        return 7

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert git_hook_checks.main(["run-quality-gate"]) == 7

    command, cwd, env = calls[0]
    assert command == [project_python, "scripts/run_daily_quality_gate.py"]
    assert "--require-clean-worktree" not in command
    assert "--long-gate-force-rerun" not in command
    assert "--long-gate-force-rerun-all" not in command
    assert "--long-gate-cache-explain" not in command
    assert "--no-long-gate-cache" not in command
    assert "--allow-dirty-worktree" not in command
    assert cwd == str(tmp_path)
    assert "APS_SKIP_QUALITY_GATE" not in env
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_run_quality_gate_prefers_pre_commit_pre_push_env(monkeypatch, tmp_path: Path) -> None:
    captured = {}
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setenv("PRE_COMMIT_FROM_REF", "old-sha")
    monkeypatch.setenv("PRE_COMMIT_TO_REF", "new-sha")
    monkeypatch.setenv("PRE_COMMIT_REMOTE_BRANCH", "refs/heads/main")
    monkeypatch.setenv("PRE_COMMIT_LOCAL_BRANCH", "refs/heads/topic")
    monkeypatch.setenv("PRE_COMMIT_REMOTE_NAME", "origin")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)

    def fake_hit(executable, remote_name="", remote_ref="", scope_payload=None, ref_contexts=None):
        captured["executable"] = executable
        captured["remote_name"] = remote_name
        captured["remote_ref"] = remote_ref
        captured["ref_contexts"] = list(ref_contexts or [])
        return True

    monkeypatch.setattr(git_hook_checks.git_hook_cache, "pre_push_daily_cache_hit", fake_hit)
    monkeypatch.setattr(subprocess, "call", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("skip")))

    assert git_hook_checks.main(["run-quality-gate"]) == 0

    assert captured["remote_name"] == "origin"
    assert captured["remote_ref"] == "refs/heads/main"
    assert captured["ref_contexts"] == [
        {
            "local_ref": "refs/heads/topic",
            "local_sha": "new-sha",
            "remote_ref": "refs/heads/main",
            "remote_sha": "old-sha",
        }
    ]


def test_run_quality_gate_passes_pre_commit_range_to_daily_gate(monkeypatch, tmp_path: Path) -> None:
    calls = []
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setenv("PRE_COMMIT_FROM_REF", "old-sha")
    monkeypatch.setenv("PRE_COMMIT_TO_REF", "new-sha")
    monkeypatch.setenv("PRE_COMMIT_REMOTE_BRANCH", "refs/heads/main")
    monkeypatch.setenv("PRE_COMMIT_LOCAL_BRANCH", "refs/heads/topic")
    monkeypatch.setenv("PRE_COMMIT_REMOTE_NAME", "origin")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)
    monkeypatch.setattr(
        git_hook_checks.git_hook_cache,
        "pre_push_daily_cache_hit",
        lambda executable, remote_name="", remote_ref="", scope_payload=None, ref_contexts=None: False,
    )
    monkeypatch.setattr(
        git_hook_checks.git_hook_cache,
        "write_pre_push_daily_cache",
        lambda executable, remote_name="", remote_ref="", scope_payload=None, ref_contexts=None: None,
    )

    def fake_call(command, *, cwd, env):
        del cwd, env
        calls.append(list(command))
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert git_hook_checks.main(["run-quality-gate"]) == 0

    command = calls[0]
    assert command[:2] == [project_python, "scripts/run_daily_quality_gate.py"]
    assert command[2:] == [
        "--pre-push-from-ref",
        "old-sha",
        "--pre-push-to-ref",
        "new-sha",
        "--pre-push-remote-name",
        "origin",
        "--pre-push-remote-ref",
        "refs/heads/main",
    ]


def test_run_quality_gate_skips_delete_only_pre_push(monkeypatch, tmp_path: Path) -> None:
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)
    monkeypatch.setattr(
        git_hook_checks.sys,
        "stdin",
        io.StringIO("refs/heads/topic 0000000000000000000000000000000000000000 refs/heads/topic abc\n"),
    )
    monkeypatch.setattr(
        git_hook_checks.git_hook_cache,
        "pre_push_daily_cache_hit",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("cache should not be read")),
    )
    monkeypatch.setattr(subprocess, "call", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("skip")))

    assert git_hook_checks.main(["run-quality-gate", "origin"]) == 0


def test_run_quality_gate_does_not_skip_pre_commit_all_files_push(monkeypatch, tmp_path: Path) -> None:
    calls = []
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setenv("PRE_COMMIT_REMOTE_BRANCH", "refs/heads/main")
    monkeypatch.setenv("PRE_COMMIT_LOCAL_BRANCH", "refs/heads/main")
    monkeypatch.setenv("PRE_COMMIT_REMOTE_NAME", "origin")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)
    monkeypatch.setattr(
        git_hook_checks.git_hook_cache,
        "pre_push_daily_cache_hit",
        lambda executable, remote_name="", remote_ref="", scope_payload=None, ref_contexts=None: False,
    )
    monkeypatch.setattr(
        git_hook_checks.git_hook_cache,
        "write_pre_push_daily_cache",
        lambda executable, remote_name="", remote_ref="", scope_payload=None, ref_contexts=None: None,
    )

    def fake_call(command, *, cwd, env):
        del cwd, env
        calls.append(list(command))
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert git_hook_checks.main(["run-quality-gate"]) == 0

    assert calls == [[project_python, "scripts/run_daily_quality_gate.py"]]


def test_run_final_quality_gate_command_uses_project_python_and_utf8_env(monkeypatch, tmp_path: Path) -> None:
    calls = []
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setenv("APS_SKIP_QUALITY_GATE", "1")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "0")
    monkeypatch.setenv("PYTHONUTF8", "0")
    monkeypatch.setenv("PYTHONIOENCODING", "gbk")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)

    def fake_call(command, *, cwd, env):
        calls.append((list(command), str(cwd), dict(env)))
        return 7

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert git_hook_checks.main(["run-final-quality-gate"]) == 7

    command, cwd, env = calls[0]
    assert command == [
        project_python,
        "scripts/run_quality_gate.py",
        "--require-clean-worktree",
        "--long-gate-cache",
    ]
    assert command.count("--require-clean-worktree") == 1
    assert "--long-gate-cache-explain" not in command
    assert "--no-long-gate-cache" not in command
    assert "--allow-dirty-worktree" not in command
    assert cwd == str(tmp_path)
    assert "APS_SKIP_QUALITY_GATE" not in env
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_run_fast_static_precheck_uses_project_python_and_does_not_change_daily_or_final(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls = []
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setenv("APS_SKIP_QUALITY_GATE", "1")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "0")
    monkeypatch.setenv("PYTHONUTF8", "0")
    monkeypatch.setenv("PYTHONIOENCODING", "gbk")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)

    def fake_call(command, *, cwd, env):
        calls.append((list(command), str(cwd), dict(env)))
        return 9

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert git_hook_checks.main(["run-fast-static-precheck"]) == 9

    command, cwd, env = calls[0]
    assert command == [project_python, "scripts/run_quality_gate.py", "--fast-precheck"]
    assert "--require-clean-worktree" not in command
    assert "--long-gate-cache" not in command
    assert "--long-gate-cache-explain" not in command
    assert cwd == str(tmp_path)
    assert "APS_SKIP_QUALITY_GATE" not in env
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_blocked_paths_include_launcher_log() -> None:
    assert git_hook_checks._blocked_paths(["logs/launcher.log", "tmp/prelaunch/launcher.log", "launcher.log"]) == [
        ("logs/launcher.log", "APS 本地启动日志可能包含本机路径或错误明细，不能提交"),
        ("tmp/prelaunch/launcher.log", "APS 本地启动日志可能包含本机路径或错误明细，不能提交"),
        ("launcher.log", "APS 本地启动日志可能包含本机路径或错误明细，不能提交"),
    ]


def test_blocked_paths_include_long_gate_runtime_artifacts() -> None:
    assert git_hook_checks._blocked_paths(
        [
            "evidence/QualityGate/long_gate/results/pytest_collect_all.success.json",
            "evidence/QualityGate/collect_nodeids.json",
            "evidence/QualityGate/architecture_scan_cache.json",
            "evidence/QualityGate/full_test_debt_summary.json",
            "evidence/QualityGate/startup_runtime_regressions.json",
            "evidence/QualityGate/required_regressions.json",
            "evidence/QualityGate/debt_ledger_sync.json",
            "evidence/QualityGate/ruff_check_full.json",
            "evidence/QualityGate/pyright_gate_full.json",
            "evidence/QualityGate/pyright_tools_full.json",
            "evidence/QualityGate/quickref_vs_routes.md",
        ]
    ) == [
        (
            "evidence/QualityGate/long_gate/results/pytest_collect_all.success.json",
            "长耗时门禁缓存是本地运行产物，不应该混进普通提交",
        ),
        (
            "evidence/QualityGate/collect_nodeids.json",
            "pytest collect nodeid 快照是运行产物，应由当前门禁重新生成",
        ),
        (
            "evidence/QualityGate/architecture_scan_cache.json",
            "architecture scan 文件级缓存是运行产物，应由当前门禁重新生成",
        ),
        (
            "evidence/QualityGate/full_test_debt_summary.json",
            "full-test-debt summary 是运行产物，应由当前门禁重新生成",
        ),
        (
            "evidence/QualityGate/startup_runtime_regressions.json",
            "startup regressions proof 是运行产物，应由当前门禁重新生成",
        ),
        (
            "evidence/QualityGate/required_regressions.json",
            "required regressions proof 是运行产物，应由当前门禁重新生成",
        ),
        (
            "evidence/QualityGate/debt_ledger_sync.json",
            "debt ledger sync proof 是运行产物，应由当前门禁重新生成",
        ),
        (
            "evidence/QualityGate/ruff_check_full.json",
            "ruff full proof 是运行产物，应由当前门禁重新生成",
        ),
        (
            "evidence/QualityGate/pyright_gate_full.json",
            "pyright gate proof 是运行产物，应由当前门禁重新生成",
        ),
        (
            "evidence/QualityGate/pyright_tools_full.json",
            "pyright tools proof 是运行产物，应由当前门禁重新生成",
        ),
        (
            "evidence/QualityGate/quickref_vs_routes.md",
            "quickref/routes 对账报告是运行产物，应由当前门禁重新生成",
        ),
    ]


def test_blocked_paths_normalize_windows_separators() -> None:
    assert git_hook_checks._blocked_paths(
        [
            r".\evidence\QualityGate\quickref_vs_routes.md",
            r"evidence\QualityGate\required_regressions\core.json",
        ]
    ) == [
        (
            "evidence/QualityGate/quickref_vs_routes.md",
            "quickref/routes 对账报告是运行产物，应由当前门禁重新生成",
        ),
        (
            "evidence/QualityGate/required_regressions/core.json",
            "required regressions 分组 proof 是运行产物，应由当前门禁重新生成",
        ),
    ]


def test_run_ruff_uses_staged_only_cache_helper(monkeypatch, tmp_path: Path) -> None:
    calls = []
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)

    def fake_staged_ruff(executable: str) -> int:
        calls.append(executable)
        return 3

    monkeypatch.setattr(git_hook_checks.git_hook_cache, "run_staged_ruff", fake_staged_ruff)

    assert git_hook_checks.main(["run-ruff"]) == 3

    assert calls == [project_python]


def test_staged_ruff_exports_index_content_and_reuses_pass_cache(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    target = tmp_path / "pkg" / "module.py"
    target.parent.mkdir()
    target.write_text("STAGED = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "pkg/module.py")
    target.write_text("UNSTAGED = 2\n", encoding="utf-8")

    monkeypatch.setattr(git_hook_cache, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_cache, "_python_identity", lambda executable: {"executable_realpath": executable, "version": "3.8"})
    monkeypatch.setattr(git_hook_cache, "_tool_version", lambda executable, module: "ruff 0.0.0")
    calls = []

    def fake_call(command, *, cwd, env):
        calls.append((list(command), Path(cwd), dict(env)))
        assert (Path(cwd) / "pkg" / "module.py").read_text(encoding="utf-8") == "STAGED = 1\n"
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert git_hook_cache.run_staged_ruff(sys.executable) == 0
    assert git_hook_cache.run_staged_ruff(sys.executable) == 0

    assert len(calls) == 1
    assert calls[0][0][-1] == "pkg/module.py"
    assert calls[0][2]["PYTHONUTF8"] == "1"


def test_staged_ruff_failure_does_not_write_success_cache(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    target = tmp_path / "module.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "module.py")

    monkeypatch.setattr(git_hook_cache, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        git_hook_cache,
        "_python_identity",
        lambda executable: {"executable_realpath": executable, "version": "3.8"},
    )
    monkeypatch.setattr(git_hook_cache, "_tool_version", lambda executable, module: "ruff 0.0.0")
    monkeypatch.setattr(subprocess, "call", lambda *_args, **_kwargs: 1)

    assert git_hook_cache.run_staged_ruff(sys.executable) == 1
    assert not git_hook_cache.cache_path(git_hook_cache.STAGED_RUFF_CACHE_NAME).exists()


def test_staged_ruff_cache_invalidates_when_staged_tree_changes(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    target = tmp_path / "module.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "module.py")

    monkeypatch.setattr(git_hook_cache, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_cache, "_python_identity", lambda executable: {"executable_realpath": executable, "version": "3.8"})
    monkeypatch.setattr(git_hook_cache, "_tool_version", lambda executable, module: "ruff 0.0.0")
    calls = []

    def fake_call(command, *, cwd, env):
        calls.append(list(command))
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert git_hook_cache.run_staged_ruff(sys.executable) == 0
    target.write_text("VALUE = 2\n", encoding="utf-8")
    _git(tmp_path, "add", "module.py")
    assert git_hook_cache.run_staged_ruff(sys.executable) == 0

    assert len(calls) == 2


def test_staged_ruff_no_python_files_skips_subprocess(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    notes = tmp_path / "README.md"
    notes.write_text("docs\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    monkeypatch.setattr(git_hook_cache, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        subprocess,
        "call",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("ruff should not run")),
    )

    assert git_hook_cache.run_staged_ruff(sys.executable) == 0


def test_pre_push_daily_gate_reuses_same_head_tree_cache(monkeypatch, tmp_path: Path) -> None:
    calls = []
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)
    monkeypatch.setattr(
        git_hook_checks.git_hook_cache,
        "pre_push_daily_cache_hit",
        lambda executable, remote_name="", remote_ref="", scope_payload=None, ref_contexts=None: True,
    )
    monkeypatch.setattr(git_hook_checks.git_hook_cache, "write_pre_push_daily_cache", lambda *_args, **_kwargs: calls.append("write"))
    monkeypatch.setattr(subprocess, "call", lambda *_args, **_kwargs: calls.append("call") or 0)

    assert git_hook_checks.main(["run-quality-gate", "origin", "https://example.invalid/repo.git"]) == 0

    assert calls == []


def test_pre_push_daily_gate_reads_remote_ref_from_pre_push_stdin(monkeypatch, tmp_path: Path) -> None:
    captured = {}
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)
    monkeypatch.setattr(
        git_hook_checks.sys,
        "stdin",
        io.StringIO("refs/heads/main abc refs/heads/release def\nrefs/heads/dev 123 refs/heads/release 456\n"),
    )

    def fake_hit(executable, remote_name="", remote_ref="", scope_payload=None, ref_contexts=None):
        captured["executable"] = executable
        captured["remote_name"] = remote_name
        captured["remote_ref"] = remote_ref
        captured["ref_contexts"] = list(ref_contexts or [])
        return True

    monkeypatch.setattr(git_hook_checks.git_hook_cache, "pre_push_daily_cache_hit", fake_hit)
    monkeypatch.setattr(subprocess, "call", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("daily gate should be skipped")))

    assert git_hook_checks.main(["run-quality-gate", "origin", "https://example.invalid/repo.git"]) == 0

    assert captured == {
        "executable": project_python,
        "remote_name": "origin",
        "remote_ref": "refs/heads/release",
        "ref_contexts": [
            {
                "local_ref": "refs/heads/dev",
                "local_sha": "123",
                "remote_ref": "refs/heads/release",
                "remote_sha": "456",
            },
            {
                "local_ref": "refs/heads/main",
                "local_sha": "abc",
                "remote_ref": "refs/heads/release",
                "remote_sha": "def",
            },
        ],
    }


def test_pre_push_daily_cache_refuses_dirty_worktree(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path)
    monkeypatch.setattr(git_hook_cache, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        git_hook_cache,
        "_python_identity",
        lambda executable: {"executable_realpath": executable, "version": "3.8"},
    )
    monkeypatch.setattr(git_hook_cache, "_tool_version", lambda executable, module: f"{module} 1.0")

    git_hook_cache.write_pre_push_daily_cache(sys.executable, remote_name="origin", remote_ref="refs/heads/main")
    assert git_hook_cache.pre_push_daily_cache_hit(
        sys.executable,
        remote_name="origin",
        remote_ref="refs/heads/main",
    )

    (tmp_path / "dirty.py").write_text("DIRTY = True\n", encoding="utf-8")

    assert not git_hook_cache.pre_push_daily_cache_hit(
        sys.executable,
        remote_name="origin",
        remote_ref="refs/heads/main",
    )
    with pytest.raises(git_hook_cache.HookCacheError, match="干净工作区"):
        git_hook_cache.write_pre_push_daily_cache(
            sys.executable,
            remote_name="origin",
            remote_ref="refs/heads/main",
        )


def test_pre_push_daily_cache_key_tracks_pytest_and_pyright_versions(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path)
    monkeypatch.setattr(git_hook_cache, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        git_hook_cache,
        "_python_identity",
        lambda executable: {"executable_realpath": executable, "version": "3.8"},
    )
    versions = {"ruff": "ruff 0.15.4", "pytest": "pytest 8.3.5", "pyright": "pyright 1.1.406"}
    monkeypatch.setattr(git_hook_cache, "_tool_version", lambda executable, module: versions[module])
    before, before_payload = git_hook_cache.daily_gate_cache_key(
        sys.executable,
        remote_name="origin",
        remote_ref="refs/heads/main",
    )

    versions["pytest"] = "pytest 8.3.6"
    after, after_payload = git_hook_cache.daily_gate_cache_key(
        sys.executable,
        remote_name="origin",
        remote_ref="refs/heads/main",
    )

    assert before != after
    assert before_payload["tool_versions"]["pyright"] == "pyright 1.1.406"
    assert after_payload["tool_versions"]["pytest"] == "pytest 8.3.6"


def test_pre_push_daily_cache_reuses_after_commit_message_amend(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path)
    monkeypatch.setattr(git_hook_cache, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        git_hook_cache,
        "_python_identity",
        lambda executable: {"executable_realpath": executable, "version": "3.8"},
    )
    monkeypatch.setattr(git_hook_cache, "_tool_version", lambda executable, module: f"{module} 1.0")
    scope_payload = {
        "scope_known": True,
        "reason": "pre-push ref diff",
        "changed_paths": ["README.md"],
        "changed_paths_hash": "changed-readme",
        "impact_pytest": {
            "target_paths": [],
            "target_hash": "pytest-empty",
            "selected_group_ids": [],
            "all_required_groups": False,
            "reason": "documentation-only changed paths",
        },
        "ruff": {
            "target_paths": [],
            "target_hash": "ruff-empty",
            "all_files": False,
            "reason": "no changed Python files",
        },
    }

    git_hook_cache.write_pre_push_daily_cache(
        sys.executable,
        scope_payload=scope_payload,
        ref_contexts=[
            {
                "local_ref": "refs/heads/topic",
                "local_sha": "old-local-sha",
                "remote_ref": "refs/heads/topic",
                "remote_sha": "remote-sha",
            }
        ],
    )
    _git(tmp_path, "commit", "--amend", "-q", "-m", "amended message only")

    assert git_hook_cache.pre_push_daily_cache_hit(
        sys.executable,
        scope_payload=scope_payload,
        ref_contexts=[
            {
                "local_ref": "refs/heads/topic",
                "local_sha": "new-local-sha",
                "remote_ref": "refs/heads/topic",
                "remote_sha": "remote-sha",
            }
        ],
    )


def test_pre_push_daily_cache_key_tracks_impact_scope(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path)
    monkeypatch.setattr(git_hook_cache, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        git_hook_cache,
        "_python_identity",
        lambda executable: {"executable_realpath": executable, "version": "3.8"},
    )
    monkeypatch.setattr(git_hook_cache, "_tool_version", lambda executable, module: f"{module} 1.0")

    def scope_payload(path: str) -> dict:
        return {
            "scope_known": True,
            "reason": "pre-push ref diff",
            "changed_paths": [path],
            "changed_paths_hash": "changed-" + path,
            "impact_pytest": {
                "target_paths": ["tests/test_" + path.replace(".", "_")],
                "target_hash": "pytest-" + path,
                "selected_group_ids": ["group"],
                "all_required_groups": False,
                "reason": "matched changed paths",
            },
            "ruff": {
                "target_paths": [path] if path.endswith(".py") else [],
                "target_hash": "ruff-" + path,
                "all_files": False,
                "reason": "changed Python files",
            },
        }

    readme_key, _readme_payload = git_hook_cache.daily_gate_cache_key(sys.executable, scope_payload=scope_payload("README.md"))
    python_key, python_payload = git_hook_cache.daily_gate_cache_key(
        sys.executable,
        scope_payload=scope_payload("tools/git_hook_checks.py"),
    )

    assert readme_key != python_key
    assert python_payload["extra"]["changed_paths_hash"] == "changed-tools/git_hook_checks.py"
    assert python_payload["extra"]["impact_pytest_target_hash"] == "pytest-tools/git_hook_checks.py"
    assert python_payload["extra"]["ruff_target_hash"] == "ruff-tools/git_hook_checks.py"


def test_pre_push_daily_gate_writes_cache_only_after_success(monkeypatch, tmp_path: Path) -> None:
    calls = []
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)
    monkeypatch.setattr(
        git_hook_checks.git_hook_cache,
        "pre_push_daily_cache_hit",
        lambda executable, remote_name="", remote_ref="", scope_payload=None, ref_contexts=None: False,
    )
    monkeypatch.setattr(
        git_hook_checks.git_hook_cache,
        "write_pre_push_daily_cache",
        lambda executable, remote_name="", remote_ref="", scope_payload=None, ref_contexts=None: calls.append(("write", remote_name)),
    )

    def fake_call(command, *, cwd, env):
        calls.append(("call", list(command), env["PYTHONUTF8"]))
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert git_hook_checks.main(["run-quality-gate", "origin"]) == 0

    assert calls == [
        ("call", [project_python, "scripts/run_daily_quality_gate.py"], "1"),
        ("write", "origin"),
    ]


def test_pre_push_daily_gate_failure_does_not_write_cache(monkeypatch, tmp_path: Path) -> None:
    calls = []
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)
    monkeypatch.setattr(
        git_hook_checks.git_hook_cache,
        "pre_push_daily_cache_hit",
        lambda executable, remote_name="", remote_ref="", scope_payload=None, ref_contexts=None: False,
    )
    monkeypatch.setattr(git_hook_checks.git_hook_cache, "write_pre_push_daily_cache", lambda *_args, **_kwargs: calls.append("write"))
    monkeypatch.setattr(subprocess, "call", lambda *_args, **_kwargs: 8)

    assert git_hook_checks.main(["run-quality-gate"]) == 8

    assert calls == []


def test_multi_ref_unknown_scope_command_matches_full_scope_payload(monkeypatch) -> None:
    from scripts import run_daily_quality_gate as daily_gate

    refs = [
        git_hook_checks.PrePushRef("refs/heads/a", "to-a", "refs/heads/a", "from-a"),
        git_hook_checks.PrePushRef("refs/heads/b", "to-b", "refs/heads/b", "missing-remote-b"),
    ]

    def fake_pre_push_diff_paths(from_ref, to_ref, remote_name, remote_ref=""):
        del from_ref, remote_name, remote_ref
        if to_ref == "to-a":
            return daily_gate.ChangedPathSet(["core/service.py"], True, "pre-push ref diff")
        return daily_gate.ChangedPathSet([], False, "remote object missing")

    monkeypatch.setattr(git_hook_checks, "_daily_gate_module", lambda: daily_gate)
    monkeypatch.setattr(daily_gate, "_pre_push_diff_paths", fake_pre_push_diff_paths)
    monkeypatch.setattr(daily_gate, "_git_name_only", lambda _args: [])

    scope_payload = git_hook_checks._daily_scope_for_refs(refs, remote_name="origin")
    command = git_hook_checks._daily_gate_command_for_refs("/python", refs, remote_name="origin")

    assert scope_payload["scope_known"] is False
    assert scope_payload["impact_pytest"]["all_required_groups"] is True
    assert scope_payload["ruff"]["all_files"] is True
    assert command == [
        "/python",
        "scripts/run_daily_quality_gate.py",
        "--pre-push-from-ref",
        "",
        "--pre-push-to-ref",
        "missing-multi-ref-range",
        "--pre-push-remote-name",
        "origin",
        "--pre-push-remote-ref",
        "refs/heads/a,refs/heads/b",
    ]


def test_daily_gate_module_adds_repo_root_for_direct_script_execution(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    original_path = list(sys.path)
    filtered_path = [
        path
        for path in original_path
        if path
        and Path(path).resolve() != repo_root
        and Path(path).resolve() != repo_root / "tools"
    ]
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", repo_root)
    monkeypatch.setattr(sys, "path", [str(repo_root / "tools"), *filtered_path])
    monkeypatch.delitem(sys.modules, "scripts", raising=False)
    monkeypatch.delitem(sys.modules, "scripts.run_daily_quality_gate", raising=False)

    daily_gate = git_hook_checks._daily_gate_module()

    assert str(repo_root) in sys.path
    assert daily_gate.__name__ == "scripts.run_daily_quality_gate"


def test_run_final_quality_gate_if_needed_uses_exact_head_cache(monkeypatch, tmp_path: Path) -> None:
    calls = []
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)
    monkeypatch.setattr(git_hook_checks.git_hook_cache, "final_gate_cache_hit", lambda executable: True)
    monkeypatch.setattr(subprocess, "call", lambda *_args, **_kwargs: calls.append("call") or 0)

    assert git_hook_checks.main(["run-final-quality-gate-if-needed"]) == 0

    assert calls == []


def test_run_final_quality_gate_if_needed_writes_cache_after_success(monkeypatch, tmp_path: Path) -> None:
    calls = []
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)
    monkeypatch.setattr(git_hook_checks.git_hook_cache, "final_gate_cache_hit", lambda executable: False)
    monkeypatch.setattr(git_hook_checks.git_hook_cache, "write_final_gate_cache", lambda executable: calls.append(("write", executable)))

    def fake_call(command, *, cwd, env):
        calls.append(("call", list(command)))
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert git_hook_checks.main(["run-final-quality-gate-if-needed"]) == 0

    assert calls == [
        (
            "call",
            [
                project_python,
                "scripts/run_quality_gate.py",
                "--require-clean-worktree",
                "--long-gate-cache",
            ],
        ),
        ("write", project_python),
    ]


def test_final_gate_cache_refuses_dirty_worktree(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path)
    monkeypatch.setattr(git_hook_cache, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        git_hook_cache,
        "_python_identity",
        lambda executable: {"executable_realpath": executable, "version": "3.8"},
    )
    monkeypatch.setattr(git_hook_cache, "_tool_version", lambda executable, module: f"{module} 1.0")

    git_hook_cache.write_final_gate_cache(sys.executable)
    assert git_hook_cache.final_gate_cache_hit(sys.executable)

    (tmp_path / "README.md").write_text("dirty\n", encoding="utf-8")

    assert not git_hook_cache.final_gate_cache_hit(sys.executable)
    with pytest.raises(git_hook_cache.HookCacheError, match="干净工作区"):
        git_hook_cache.write_final_gate_cache(sys.executable)


def test_main_reexecs_into_project_python_for_real_hook_entry(monkeypatch, tmp_path: Path) -> None:
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)
    monkeypatch.setattr(git_hook_checks.sys, "executable", str(tmp_path / "system-python"))
    monkeypatch.setattr(git_hook_checks.sys, "argv", ["tools/git_hook_checks.py", "run-ruff"])
    calls = []

    def fake_execv(executable, argv):
        calls.append((executable, list(argv)))
        raise SystemExit(0)

    monkeypatch.setattr(git_hook_checks.os, "execv", fake_execv)

    try:
        git_hook_checks.main()
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("真实 hook 入口必须切到项目 .venv Python 后再执行")

    assert calls == [(project_python, [project_python, "tools/git_hook_checks.py", "run-ruff"])]


def test_main_does_not_reexec_when_tests_pass_explicit_argv(monkeypatch, tmp_path: Path) -> None:
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)
    monkeypatch.setattr(git_hook_checks.sys, "executable", str(tmp_path / "system-python"))
    monkeypatch.setattr(git_hook_checks.os, "execv", lambda *_args: (_ for _ in ()).throw(AssertionError("unexpected execv")))
    monkeypatch.setattr(git_hook_checks.git_hook_cache, "run_staged_ruff", lambda executable: 0)

    assert git_hook_checks.main(["run-ruff"]) == 0


def test_same_executable_path_accepts_current_interpreter_realpath() -> None:
    assert git_hook_checks._same_executable_path(sys.executable, str(Path(sys.executable).resolve()))


def test_pre_commit_config_wires_quality_gate_and_ruff_hooks() -> None:
    config = load_config(str(Path(__file__).resolve().parents[1] / ".pre-commit-config.yaml"))
    hooks = {
        str(hook["id"]): hook
        for repo in config["repos"]
        for hook in repo["hooks"]
    }

    assert config["default_install_hook_types"] == ["pre-commit", "commit-msg", "pre-push"]
    assert hooks["ruff"]["entry"] == "python tools/git_hook_checks.py run-ruff"
    assert hooks["ruff"]["stages"] == ["pre-commit"]
    assert hooks["ruff"]["pass_filenames"] is False
    assert hooks["block-local-artifacts"]["stages"] == ["pre-commit"]
    assert hooks["block-local-artifacts"]["pass_filenames"] is False
    assert hooks["block-local-artifacts"]["always_run"] is True
    assert hooks["readable-commit-message"]["stages"] == ["commit-msg"]
    assert hooks["aps-quality-gate"]["name"] == "APS daily fast gate before push"
    assert hooks["aps-quality-gate"]["entry"] == "python tools/git_hook_checks.py run-quality-gate"
    assert hooks["aps-quality-gate"]["language"] == "system"
    assert hooks["aps-quality-gate"]["stages"] == ["pre-push"]
    assert hooks["aps-quality-gate"]["pass_filenames"] is False
    assert hooks["aps-quality-gate"]["always_run"] is True
