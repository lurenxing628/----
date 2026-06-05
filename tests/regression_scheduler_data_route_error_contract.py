"""回归测试（AST 静态哨兵）：扫描 web/routes 下所有 data/json/api 风格路由的错误处理契约，防止退回到私有 UNKNOWN 码或固定 AppError 400。守护这些 data 路由的 except 块里 AppError 处理不返回写死的 400、通用 Exception 处理不使用私有 "UNKNOWN" 错误码；并确保至少扫到 /gantt/data 与 /resource-dispatch/data 这两条路由，避免哨兵因扫不到目标而失效。"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]


def _decorator_route_path(decorator: ast.AST) -> str:
    if not isinstance(decorator, ast.Call) or not decorator.args:
        return ""
    first_arg = decorator.args[0]
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        return str(first_arg.value)
    return ""


def _is_data_like_route(path: str) -> bool:
    normalized = str(path or "").strip().lower()
    return bool(normalized) and any(token in normalized for token in ("/data", "/json", "/api"))


def _exception_type_names(target: ast.AST) -> List[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Attribute):
        return [target.attr]
    if isinstance(target, ast.Tuple):
        names = []
        for item in target.elts:
            names.extend(_exception_type_names(item))
        return names
    return []


def _is_app_error_handler(handler: ast.ExceptHandler) -> bool:
    target = handler.type
    if target is None:
        return False
    return any(name == "AppError" for name in _exception_type_names(target))


def _is_generic_exception_handler(handler: ast.ExceptHandler) -> bool:
    target = handler.type
    if target is None:
        return True
    return any(name == "Exception" for name in _exception_type_names(target))


def _handler_int_constants(handler: ast.ExceptHandler) -> Dict[str, int]:
    values = {}
    for node in ast.walk(handler):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = node.value
        if not isinstance(target, ast.Name):
            continue
        if not isinstance(value, ast.Constant) or not isinstance(value.value, int):
            continue
        values[target.id] = int(value.value)
    return values


def _handler_returns_fixed_status(handler: ast.ExceptHandler, status_code: int) -> bool:
    int_constants = _handler_int_constants(handler)
    for node in ast.walk(handler):
        if not isinstance(node, ast.Return):
            continue
        value = node.value
        if not isinstance(value, ast.Tuple) or len(value.elts) < 2:
            continue
        status = value.elts[1]
        if isinstance(status, ast.Constant) and status.value == status_code:
            return True
        if isinstance(status, ast.Name) and int_constants.get(status.id) == status_code:
            return True
    return False


def _handler_contains_constant(handler: ast.ExceptHandler, expected: str) -> bool:
    for node in ast.walk(handler):
        if isinstance(node, ast.Constant) and node.value == expected:
            return True
    return False


def test_scheduler_data_routes_do_not_regress_to_private_unknown_or_fixed_app_error_400() -> None:
    findings = []
    discovered_routes = []

    for path in (REPO_ROOT / "web" / "routes").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        rel_path = path.relative_to(REPO_ROOT).as_posix()

        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            route_paths = [_decorator_route_path(decorator) for decorator in node.decorator_list]
            data_like_paths = [route_path for route_path in route_paths if _is_data_like_route(route_path)]
            if not data_like_paths:
                continue
            discovered_routes.extend((rel_path, node.name, route_path) for route_path in data_like_paths)

            for handler in [item for item in ast.walk(node) if isinstance(item, ast.ExceptHandler)]:
                if _is_app_error_handler(handler) and _handler_returns_fixed_status(handler, 400):
                    findings.append(f"{rel_path}:{node.name}:AppError handler returns fixed 400")
                if _is_generic_exception_handler(handler) and _handler_contains_constant(handler, "UNKNOWN"):
                    findings.append(f"{rel_path}:{node.name}:generic exception uses private UNKNOWN code")

    assert discovered_routes, "未扫描到任何 data/json/api 风格路由，错误契约哨兵失效。"
    assert any(route_path == "/gantt/data" for _path, _name, route_path in discovered_routes), discovered_routes
    assert any(route_path == "/resource-dispatch/data" for _path, _name, route_path in discovered_routes), discovered_routes
    assert findings == [], findings
