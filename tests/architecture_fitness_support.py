"""为架构适应度测试提供共享桩件：扫描 Python 文件、检测 viewmodel 越层 import（只许 core.models 与标准库，禁 flask/web/data/core 其他子包及 import *）、用 AST 找包依赖环、收集已用稳定降级码（FieldPolicy/DegradationEvent 等）。"""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def collect_py_files(*rel_dirs: str) -> List[str]:
    files = []
    for rel_dir in rel_dirs:
        base = os.path.join(REPO_ROOT, rel_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for filename in filenames:
                if filename.endswith(".py") and (filename == "__init__.py" or not filename.startswith("__")):
                    files.append(os.path.relpath(os.path.join(dirpath, filename), REPO_ROOT).replace("\\", "/"))
    return files


def read_text(rel_path: str) -> str:
    with open(os.path.join(REPO_ROOT, rel_path), "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _import_module_function_aliases(module_ast: ast.Module) -> Set[str]:
    aliases: Set[str] = set()
    for node in module_ast.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 0 or node.module != "importlib":
            continue
        for alias in node.names:
            if alias.name == "import_module":
                aliases.add(alias.asname or alias.name)
    return aliases


def _importlib_module_aliases(module_ast: ast.Module) -> Set[str]:
    aliases: Set[str] = set()
    for node in module_ast.body:
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.name == "importlib":
                aliases.add(alias.asname or alias.name)
    return aliases


def _dynamic_import_target(
    node: ast.AST,
    *,
    import_module_aliases: Set[str],
    importlib_aliases: Set[str],
) -> Optional[str]:
    if not isinstance(node, ast.Call) or not node.args:
        return None
    first_arg = node.args[0]
    if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
        return None
    if isinstance(node.func, ast.Name):
        if node.func.id == "__import__" or node.func.id in import_module_aliases:
            return first_arg.value
        return None
    if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
        if isinstance(node.func.value, ast.Name) and node.func.value.id in importlib_aliases:
            return first_arg.value
    return None


def _is_stdlib_root_module(root: str) -> bool:
    if not root:
        return False
    if root in sys.builtin_module_names:
        return True
    try:
        spec = importlib.util.find_spec(root)
    except Exception:
        return False
    if spec is None:
        return False
    origin = getattr(spec, "origin", None)
    if origin in ("built-in", "frozen"):
        return True
    if not origin:
        return False
    origin_path = os.path.normcase(os.path.abspath(str(origin)))
    lower = origin_path.lower()
    if ("site-packages" in lower) or ("dist-packages" in lower):
        return False
    for base_prefix in (getattr(sys, "base_prefix", None), getattr(sys, "prefix", None)):
        if not base_prefix:
            continue
        prefix_path = os.path.normcase(os.path.abspath(str(base_prefix)))
        if origin_path.startswith(prefix_path + os.sep):
            return True
    return False


def _is_allowed_viewmodel_import(module_name: str) -> bool:
    module_text = str(module_name or "").strip()
    if not module_text:
        return False
    if module_text == "core.models" or module_text.startswith("core.models."):
        return True
    root = module_text.split(".", 1)[0]
    if root in ("flask", "web", "data"):
        return False
    if root == "core":
        return False
    return _is_stdlib_root_module(root)


def _record_viewmodel_import_node(violations: List[str], file_path: str, node: ast.AST) -> None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            module_name = str(alias.name or "")
            if not _is_allowed_viewmodel_import(module_name):
                violations.append(f"{file_path}:{node.lineno}: import {module_name}")
        return
    if not isinstance(node, ast.ImportFrom):
        return
    if any(alias.name == "*" for alias in node.names or []):
        violations.append(f"{file_path}:{node.lineno}: from {node.module} import *")
    if int(getattr(node, "level", 0) or 0) > 0:
        return
    module_name = str(node.module or "")
    if module_name and not _is_allowed_viewmodel_import(module_name):
        violations.append(f"{file_path}:{node.lineno}: from {module_name} import ...")


def viewmodel_import_violations(file_paths: List[str]) -> List[str]:
    violations: List[str] = []
    for file_path in file_paths:
        try:
            tree = ast.parse(read_text(file_path), filename=file_path)
        except SyntaxError as exc:
            violations.append(f"{file_path}:{getattr(exc, 'lineno', 0) or 0}: SyntaxError: {exc}")
            continue
        import_module_aliases = _import_module_function_aliases(tree)
        importlib_aliases = _importlib_module_aliases(tree)
        for node in ast.walk(tree):
            _record_viewmodel_import_node(violations, file_path, node)
            module_name = _dynamic_import_target(
                node,
                import_module_aliases=import_module_aliases,
                importlib_aliases=importlib_aliases,
            )
            if module_name and not _is_allowed_viewmodel_import(module_name):
                violations.append(f"{file_path}:{getattr(node, 'lineno', 0) or 0}: dynamic import {module_name}")
    return violations


def canonical_dependency_cycle(cycle: List[str]) -> Tuple[str, ...]:
    body = tuple(cycle[:-1])
    rotations = [body[index:] + body[:index] for index in range(len(body))]
    return min(rotations)


def find_dependency_cycles(package_dependencies: Dict[str, Set[str]]) -> List[str]:
    cycles: Set[Tuple[str, ...]] = set()

    def visit(start: str, current: str, path: List[str]) -> None:
        for dep in sorted(package_dependencies.get(current, set())):
            if dep not in package_dependencies:
                continue
            if dep == start:
                cycles.add(canonical_dependency_cycle(path + [dep]))
            elif dep not in path:
                visit(start, dep, path + [dep])

    for package_name in sorted(package_dependencies):
        visit(package_name, package_name, [package_name])
    return [" -> ".join(list(cycle) + [cycle[0]]) for cycle in sorted(cycles)]


def string_constant(node: Optional[ast.AST]) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return str(node.value)
    return None


def used_stable_degradation_codes(file_paths: List[str]) -> Set[str]:
    used_codes: Set[str] = set()
    for file_path in file_paths:
        try:
            tree = ast.parse(read_text(file_path), filename=file_path)
        except SyntaxError as exc:
            raise AssertionError(f"无法解析 {file_path}: {exc}") from exc
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                _record_stable_degradation_call(used_codes, node)
    return used_codes


def _record_stable_degradation_call(used_codes: Set[str], node: ast.Call) -> None:
    func_name = _call_function_name(node)
    keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
    if func_name == "FieldPolicy":
        _record_field_policy_codes(used_codes, keywords)
        return
    if func_name in {"add", "DegradationEvent"} and "code" in keywords:
        if func_name == "DegradationEvent" or "scope" in keywords or "message" in keywords:
            _add_code_if_present(used_codes, keywords.get("code"))
        return
    if func_name in {"_add_state_event", "_add_counted_event"} and "code" in keywords:
        _add_code_if_present(used_codes, keywords.get("code"))
        return
    if func_name == "public_degradation_event_message" and node.args:
        _add_code_if_present(used_codes, node.args[0])


def _call_function_name(node: ast.Call) -> Optional[str]:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _record_field_policy_codes(used_codes: Set[str], keywords: Dict[str, ast.AST]) -> None:
    for key in ("strict_reason_code", "compat_reason_code", "blank_reason_code"):
        _add_code_if_present(used_codes, keywords.get(key))


def _add_code_if_present(used_codes: Set[str], node: Optional[ast.AST]) -> None:
    code = string_constant(node)
    if code:
        used_codes.add(code)


__all__ = [
    "REPO_ROOT",
    "collect_py_files",
    "find_dependency_cycles",
    "read_text",
    "used_stable_degradation_codes",
    "viewmodel_import_violations",
]
