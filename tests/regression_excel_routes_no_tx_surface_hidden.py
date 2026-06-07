"""
回归测试：Excel 路由层不直接调用 *_no_tx（C02 收口）。

P5.3 REWRITE：原实现用源码文本 `"_no_tx(" in txt` 守卫，会误命中注释/字符串里的
`_no_tx(`（脆性假阳）且漏判跨行调用。改为 AST 调用检测——只在真正的函数调用
（`foo._no_tx(...)` / `_no_tx(...)` / `apply_no_tx(...)` 等被调名以 `_no_tx` 结尾）
上失败，对注释/文档串/格式化鲁棒，同时仍逐字守住「路由层不得直接调事务外变体」的
C02 架构规则（行为契约不变，仅去脆性）。
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List

from tests._support.paths import REPO_ROOT


def _called_name(func: ast.AST) -> str:
    """取被调用表达式的末段名：Name -> id；Attribute -> attr；其余 -> 空串。"""
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _no_tx_call_lines(path: Path) -> List[int]:
    """返回 path 中直接调用 `*_no_tx(...)` 的行号列表（AST 实调用，忽略注释/字符串）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: List[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _called_name(node.func).endswith("_no_tx"):
            hits.append(node.lineno)
    return hits


def test_excel_routes_no_tx_surface_hidden() -> None:
    targets = [
        REPO_ROOT / "web" / "routes" / "domains" / "scheduler" / "scheduler_excel_batches.py",
        REPO_ROOT / "web" / "routes" / "personnel_excel_operator_calendar.py",
    ]
    for path in targets:
        hits = _no_tx_call_lines(path)
        assert hits == [], f"路由层仍直接调用 *_no_tx（应走事务管理路径）：{path} 行 {hits}"
