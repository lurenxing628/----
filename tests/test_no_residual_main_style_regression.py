"""门禁守卫（required）：删除 main-style collector 后，杜绝任何「def main 且无 def test_」的
regression_*.py 残留——这类文件在标准 pytest 收集器下收集 0 项、exit 0、零报错（静默假绿），
原本靠已删的 conftest collector（pytest_collect_file→子进程跑 main()）托管运行。

独立于 tools/verify_required_regressions_from_full_test_debt.py：核销器读的是「已收集集」、做
required⊄debt 的事后核销，抓不到「本应收集却因 collector 删除而根本没被收集」的文件。本守卫直接
扫文件系统 + AST，不依赖任何收集结果，是 P3.4 三条 AND 卡点的第②条硬兜底。
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent


def _has_def(tree: ast.Module, name_pred) -> bool:
    # 只认同步 def——精确对齐原 collector 正则 `^\s*def`（不匹配 `async def`）。async def test_
    # 在无 pytest-asyncio 时会被 skip、其 main() 永不执行；若把 async def test_ 误算作 has_test，
    # 会漏判「async test + main」这类静默假绿文件（原 collector 会判其为 main-style 并跑 main）。
    return any(
        isinstance(node, ast.FunctionDef) and name_pred(node.name)
        for node in ast.walk(tree)
    )


def _is_residual_main_style(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, SyntaxError):
        # 坏编码/语法错另有收集期报错兜底，不在本守卫语义内。
        return False
    has_main = _has_def(tree, lambda name: name == "main")
    has_test = _has_def(tree, lambda name: name.startswith("test_"))
    return has_main and not has_test


def test_no_residual_main_style_regression_files() -> None:
    residual = sorted(
        str(path.relative_to(TESTS_DIR.parent)).replace("\\", "/")
        for path in TESTS_DIR.glob("regression_*.py")
        if _is_residual_main_style(path)
    )
    assert residual == [], (
        "发现残留 main-style regression 文件（def main 且无 def test_）。"
        "main-style collector 已于 P3.4 删除，这类文件在标准收集器下收集 0 项 = 静默假绿，"
        "必须转为 def test_ 形态：\n" + "\n".join(residual)
    )
