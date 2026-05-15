from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools import fast_static_precheck as precheck


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_root, check=True)


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.invalid")
    _git(repo_root, "config", "user.name", "Test User")


def _commit(repo_root: Path, message: str = "init") -> None:
    _git(repo_root, "commit", "-q", "--no-gpg-sign", "-m", message)


def test_collect_changed_python_files_includes_default_worktree_sources(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    tracked = tmp_path / "tracked.py"
    deleted = tmp_path / "deleted.py"
    renamed = tmp_path / "renamed_old.py"
    tracked.write_text("VALUE = 1\n", encoding="utf-8")
    deleted.write_text("VALUE = 1\n", encoding="utf-8")
    renamed.write_text("VALUE = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.py", "deleted.py", "renamed_old.py")
    _commit(tmp_path)

    tracked.write_text("VALUE = 2\n", encoding="utf-8")
    _git(tmp_path, "mv", "renamed_old.py", "renamed 新.py")
    staged = tmp_path / "staged.py"
    staged.write_text("STAGED = True\n", encoding="utf-8")
    notes = tmp_path / "notes.md"
    notes.write_text("not python\n", encoding="utf-8")
    _git(tmp_path, "add", "staged.py", "notes.md")
    deleted.unlink()
    untracked = tmp_path / "含 空格.py"
    untracked.write_text("UNTRACKED = True\n", encoding="utf-8")
    evidence_file = tmp_path / "evidence" / "skip.py"
    evidence_file.parent.mkdir()
    evidence_file.write_text("SKIP = True\n", encoding="utf-8")

    changed = precheck.collect_changed_python_files(str(tmp_path))

    assert set(changed.paths) == {"renamed 新.py", "staged.py", "tracked.py", "含 空格.py"}
    assert changed.sources["renamed 新.py"] == ("staged",)
    assert changed.sources["staged.py"] == ("staged",)
    assert changed.sources["tracked.py"] == ("unstaged",)
    assert changed.sources["含 空格.py"] == ("untracked",)
    assert "deleted.py" not in changed.paths
    assert "notes.md" not in changed.paths
    assert "evidence/skip.py" not in changed.paths


def test_collect_changed_python_files_base_ref_does_not_use_worktree_sources(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "committed.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    calls = []

    def fake_run_git_paths(args, repo_root=precheck.REPO_ROOT):
        calls.append(list(args))
        return ["committed.py"]

    monkeypatch.setattr(precheck, "_run_git_paths", fake_run_git_paths)

    changed = precheck.collect_changed_python_files(str(tmp_path), base_ref="origin/main")

    assert changed.paths == ("committed.py",)
    assert changed.sources == {"committed.py": ("base-ref",)}
    assert calls == [["diff", "--name-only", "--diff-filter=ACMR", "-z", "origin/main...HEAD", "--"]]


def test_filter_python_targets_skips_non_files_and_runtime_paths(tmp_path: Path) -> None:
    good = tmp_path / "good.py"
    good.write_text("VALUE = 1\n", encoding="utf-8")
    dotdir = tmp_path / ".limcode" / "hooks" / "check_complexity.py"
    dotdir.parent.mkdir(parents=True)
    dotdir.write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "build").mkdir()
    skipped = tmp_path / "build" / "generated.py"
    skipped.write_text("VALUE = 1\n", encoding="utf-8")
    directory = tmp_path / "package.py"
    directory.mkdir()

    assert precheck.filter_python_targets(
        ["good.py", "./.limcode/hooks/check_complexity.py", "notes.txt", "missing.py", "build/generated.py", "package.py"],
        repo_root=str(tmp_path),
    ) == (".limcode/hooks/check_complexity.py", "good.py")


def test_main_no_targets_returns_zero_without_running_ruff(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(precheck, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(
        precheck,
        "collect_changed_python_files",
        lambda *_args, **_kwargs: precheck.ChangedPythonFiles(paths=(), sources={}),
    )
    monkeypatch.setattr(
        precheck,
        "run_ruff",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("ruff should not run")),
    )

    assert precheck.main([]) == 0

    output = capsys.readouterr().out
    assert precheck.FAST_STATIC_PRECHECK_BANNER in output
    assert precheck.NO_TARGETS_MESSAGE in output
    assert "not ruff_check_full" in output
    assert "not pyright_gate_full" in output
    assert "not pyright_tools_full" in output


def test_run_ruff_uses_list_args_and_project_cwd(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_call(command, *, cwd, env):
        calls.append((list(command), str(cwd), dict(env)))
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert precheck.run_ruff(("a.py", "含 空格.py"), repo_root=str(tmp_path)) == 0

    command, cwd, env = calls[0]
    assert command == [sys.executable, "-m", "ruff", "check", "--force-exclude", "--", "a.py", "含 空格.py"]
    assert cwd == str(tmp_path)
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_main_returns_ruff_failure_and_prints_copyable_rerun(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(precheck, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(
        precheck,
        "collect_changed_python_files",
        lambda *_args, **_kwargs: precheck.ChangedPythonFiles(
            paths=("bad path.py",),
            sources={"bad path.py": ("staged",)},
        ),
    )
    monkeypatch.setattr(precheck, "run_ruff", lambda *_args, **_kwargs: 1)

    assert precheck.main(["--print-targets"]) == 1

    captured = capsys.readouterr()
    assert "bad path.py (staged)" in captured.out
    assert precheck.PYRIGHT_SKIP_MESSAGE in captured.out
    assert "可复制复跑命令" in captured.err
    assert "bad path.py" in captured.err


def test_main_reports_git_collection_failure(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(precheck, "REPO_ROOT", str(tmp_path))

    def fail_collect(*_args, **_kwargs):
        raise precheck.FastStaticPrecheckError("git failed")

    monkeypatch.setattr(precheck, "collect_changed_python_files", fail_collect)

    assert precheck.main([]) == 2

    assert "git failed" in capsys.readouterr().err
