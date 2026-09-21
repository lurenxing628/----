"""回归测试：前端契约里写死的后端模块路径，必须真的指向现有模块和函数。

现场实际甘特的契约要求后端给的 critical_chain.source 恰好等于某个模块路径
（frontend/workbench/app/ActualGanttContract.js），对不上就整份数据判为"没有真实算法证据"，
页面退化成"现场实际甘特未读取成功"。

2026-09-16 的分包重构（4f3a127a）把 gantt_critical_chain.py 搬进 gantt/ 子包，
后端那侧的常量（core/services/workbench/execution/actual_gantt_chain.py:12 ENGINE）跟着改了，
前端这个字符串没有——改写工具扫的是 Python import，跨语言的字符串常量它看不见。
结果 6 个浏览器用例一起红，而浏览器车道当时没人跑，红了几天没人知道。

这条测试几毫秒，不需要 Node 也不需要浏览器。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, List, Set

from tests._support.paths import REPO_ROOT

FRONTEND_ROOTS = ("frontend/workbench/app", "static/workbench/app")
# 只认 core.services.* 这一段，后面跟不跟函数名都行
_MODULE_REF = re.compile(r"\bcore\.services(?:\.[A-Za-z_][A-Za-z0-9_]*)+\b")


def _frontend_files() -> List[Path]:
    return sorted(path for root in FRONTEND_ROOTS
                  for pattern in ("*.js", "*.jsx")
                  for path in (REPO_ROOT / root).rglob(pattern))


def _references() -> Dict[str, Set[str]]:
    found: Dict[str, Set[str]] = {}
    for path in _frontend_files():
        for ref in _MODULE_REF.findall(path.read_text(encoding="utf-8", errors="replace")):
            found.setdefault(ref, set()).add(str(path.relative_to(REPO_ROOT)))
    return found


def _resolve(dotted: str) -> bool:
    """把 a.b.c 逐段往回退：最长的模块前缀存在，且剩下那一段是它里面的顶层名字。"""
    parts = dotted.split(".")
    for cut in range(len(parts), 0, -1):
        base = REPO_ROOT / Path(*parts[:cut])
        module = base.with_suffix(".py") if base.with_suffix(".py").is_file() else (
            base / "__init__.py" if (base / "__init__.py").is_file() else None)
        if module is None:
            continue
        rest = parts[cut:]
        if not rest:
            return True
        if len(rest) > 1:
            return False
        tree = ast.parse(module.read_text(encoding="utf-8"), str(module))
        return rest[0] in {node.name for node in tree.body
                           if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))} or any(
            isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == rest[0] for target in node.targets)
            for node in tree.body)
    return False


def test_frontend_pinned_backend_modules_still_exist() -> None:
    broken = {ref: files for ref, files in _references().items() if not _resolve(ref)}
    assert not broken, "前端钉的后端模块路径已经失效（搬模块时记得一起改）：\n" + "\n".join(
        f"  {ref}  ← {', '.join(sorted(files))}" for ref, files in sorted(broken.items()))


def test_the_scan_actually_finds_the_known_reference() -> None:
    """扫不到任何引用时上面那条会假绿，这里钉住已知的那一处确实被看见。"""
    refs = _references()
    assert refs, "一条 core.services.* 引用都没扫到，正则或扫描范围可能已经失配"
    assert any(ref.endswith("compute_critical_chain_from_rows") for ref in refs), (
        f"没看到关键链引擎那条引用，扫到的是：{sorted(refs)}")
