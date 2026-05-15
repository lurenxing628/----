from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pre_commit.clientlib import load_config

from tools import git_hook_checks


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
            "evidence/QualityGate/required_regressions.json",
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
            "evidence/QualityGate/required_regressions.json",
            "required regressions proof 是运行产物，应由当前门禁重新生成",
        ),
    ]


def test_run_ruff_command_uses_project_python(monkeypatch, tmp_path: Path) -> None:
    calls = []
    project_python = str(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setattr(git_hook_checks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(git_hook_checks, "_project_python_executable", lambda: project_python)

    def fake_call(command, *, cwd):
        calls.append((list(command), str(cwd)))
        return 3

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert git_hook_checks.main(["run-ruff"]) == 3

    assert calls == [
        (
            [project_python, "-m", "ruff", "check"],
            str(tmp_path),
        )
    ]


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
    monkeypatch.setattr(subprocess, "call", lambda *_args, **_kwargs: 0)

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
