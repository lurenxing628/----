from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _load_post_change_check_module():
    path = ROOT / ".limcode/skills/aps-post-change-check/scripts/post_change_check.py"
    spec = importlib.util.spec_from_file_location("post_change_check_contract", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_changed_files_preserve_first_git_status_columns(monkeypatch) -> None:
    module = _load_post_change_check_module()

    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout=" M core/algorithms/greedy/algo_stats.py\n?? tests/test_new.py\n")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.get_changed_files(str(ROOT)) == [
        "core/algorithms/greedy/algo_stats.py",
        "tests/test_new.py",
    ]


def test_post_change_check_fails_when_changed_file_exceeds_complexity(monkeypatch) -> None:
    module = _load_post_change_check_module()

    monkeypatch.setattr(module, "find_repo_root", lambda: str(ROOT))
    monkeypatch.setattr(module, "get_changed_files", lambda repo_root: ["core/example.py"])
    monkeypatch.setattr(module, "check_ruff", lambda repo_root, py_files: (True, []))
    monkeypatch.setattr(module, "check_architecture", lambda repo_root, changed: ([], []))
    monkeypatch.setattr(module, "check_code_quality", lambda repo_root, changed: ([], [], []))
    monkeypatch.setattr(
        module,
        "check_complexity",
        lambda repo_root, changed: (["core/example.py:10 too_big complexity=16 (rank C)"], []),
    )
    monkeypatch.setattr(module, "check_linkage_reminders", lambda changed: [])
    monkeypatch.setattr(module, "_safe_print", lambda text="": None)

    assert module.main() == 1


def test_post_change_check_fails_when_complexity_tool_is_missing(monkeypatch) -> None:
    module = _load_post_change_check_module()

    monkeypatch.setattr(module, "find_repo_root", lambda: str(ROOT))
    monkeypatch.setattr(module, "get_changed_files", lambda repo_root: ["core/example.py"])
    monkeypatch.setattr(module, "check_ruff", lambda repo_root, py_files: (True, []))
    monkeypatch.setattr(module, "check_architecture", lambda repo_root, changed: ([], []))
    monkeypatch.setattr(module, "check_code_quality", lambda repo_root, changed: ([], [], []))
    monkeypatch.setattr(module, "check_complexity", lambda repo_root, changed: ([], ["⚠ radon 未安装，跳过复杂度检查"]))
    monkeypatch.setattr(module, "check_linkage_reminders", lambda changed: [])
    monkeypatch.setattr(module, "_safe_print", lambda text="": None)

    assert module.main() == 1


def test_post_change_check_fails_when_architecture_scan_skips_file(monkeypatch) -> None:
    module = _load_post_change_check_module()

    monkeypatch.setattr(module, "find_repo_root", lambda: str(ROOT))
    monkeypatch.setattr(module, "get_changed_files", lambda repo_root: ["core/example.py"])
    monkeypatch.setattr(module, "check_ruff", lambda repo_root, py_files: (True, []))
    monkeypatch.setattr(module, "check_architecture", lambda repo_root, changed: ([], ["core/example.py - read failed"]))
    monkeypatch.setattr(module, "check_code_quality", lambda repo_root, changed: ([], [], []))
    monkeypatch.setattr(module, "check_complexity", lambda repo_root, changed: ([], []))
    monkeypatch.setattr(module, "check_linkage_reminders", lambda changed: [])
    monkeypatch.setattr(module, "_safe_print", lambda text="": None)

    assert module.main() == 1


def test_post_change_check_fails_when_code_quality_scan_skips_file(monkeypatch) -> None:
    module = _load_post_change_check_module()

    monkeypatch.setattr(module, "find_repo_root", lambda: str(ROOT))
    monkeypatch.setattr(module, "get_changed_files", lambda repo_root: ["core/example.py"])
    monkeypatch.setattr(module, "check_ruff", lambda repo_root, py_files: (True, []))
    monkeypatch.setattr(module, "check_architecture", lambda repo_root, changed: ([], []))
    monkeypatch.setattr(module, "check_code_quality", lambda repo_root, changed: ([], [], ["core/example.py - read failed"]))
    monkeypatch.setattr(module, "check_complexity", lambda repo_root, changed: ([], []))
    monkeypatch.setattr(module, "check_linkage_reminders", lambda changed: [])
    monkeypatch.setattr(module, "_safe_print", lambda text="": None)

    assert module.main() == 1
