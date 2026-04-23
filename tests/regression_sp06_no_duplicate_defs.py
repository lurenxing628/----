from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    REPO_ROOT / "core" / "services" / "scheduler" / "summary" / "schedule_summary_assembly.py",
    REPO_ROOT / "core" / "algorithms" / "evaluation.py",
    REPO_ROOT / "core" / "services" / "scheduler" / "calendar_admin.py",
]

NO_CFG_GET_TARGETS = [
    REPO_ROOT / "core" / "algorithms" / "greedy" / "config_adapter.py",
    REPO_ROOT / "core" / "algorithms" / "greedy" / "scheduler.py",
    REPO_ROOT / "core" / "services" / "scheduler" / "summary" / "schedule_summary_assembly.py",
    REPO_ROOT / "core" / "services" / "scheduler" / "summary" / "schedule_summary_degradation.py",
    REPO_ROOT / "core" / "services" / "scheduler" / "summary" / "schedule_summary_freeze.py",
]

BANNED_CFG_FALLBACK_HELPERS = {
    "cfg_get",
    "_cfg_value",
    "_cfg_yes_no_flag",
    "_cfg_freeze_window_state",
}


def _duplicate_module_functions(tree: ast.AST) -> list[str]:
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for node in getattr(tree, "body", []):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        seen[node.name] = seen.get(node.name, 0) + 1
        if seen[node.name] == 2:
            duplicates.append(node.name)
    return duplicates


def _duplicate_class_methods(tree: ast.AST) -> list[str]:
    duplicates: list[str] = []
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.ClassDef):
            continue
        seen: dict[str, int] = {}
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            seen[item.name] = seen.get(item.name, 0) + 1
            if seen[item.name] == 2:
                duplicates.append(f"{node.name}.{item.name}")
    return duplicates


def test_sp06_targets_do_not_keep_duplicate_function_definitions() -> None:
    failures: list[str] = []

    for path in TARGETS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        duplicates = _duplicate_module_functions(tree) + _duplicate_class_methods(tree)
        if duplicates:
            failures.append(f"{path.relative_to(REPO_ROOT)}: {', '.join(duplicates)}")

    assert not failures, "发现重复定义残留: " + "; ".join(failures)


def test_sp06_targets_do_not_use_cfg_get_fallback_helpers() -> None:
    failures: list[str] = []

    for path in NO_CFG_GET_TARGETS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        helper_defs: list[str] = []
        helper_calls: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in BANNED_CFG_FALLBACK_HELPERS:
                helper_defs.append(node.name)
                continue
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                callee_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                callee_name = node.func.attr
            else:
                callee_name = None
            if callee_name in BANNED_CFG_FALLBACK_HELPERS:
                helper_calls.append(str(callee_name))
        if helper_defs or helper_calls:
            failures.append(
                f"{path.relative_to(REPO_ROOT)} defs={sorted(set(helper_defs))} calls={sorted(set(helper_calls))}"
            )

    assert not failures, "仍存在本地 cfg fallback helper 残留: " + "; ".join(failures)
