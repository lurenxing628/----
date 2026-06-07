#!/usr/bin/env python3
"""P7 防回潮门禁:对「自治理基线 d4589d77 以来新增(ADDED)的文件」施加三条不可回潮的硬约束。

只看 `git diff --diff-filter=A`(新增文件),删除/既有文件天然不入视野——B 阶段删既有测试
(R51 续命测试等)永不被本门禁阻断,且绝不依赖任何 KEEP/HOLD 禁删白名单。三条规则:
  ① 须含 test 函数:新增的收集型测试文件(匹配 python_files)必须含 test 函数(模块级 def test_
     或类内 test_ 方法),否则即 main-style 脚本/纯 import 空壳/async-main 伪回归(pytest 收集 0 用例);
  ② docstring:新增的收集型测试文件必须有模块级 docstring;
  ③ scope:新增的生产源文件(core/data/web/desktop/plugins + app/app_new_ui/config.py)必须落在
     某 required 回归组的 *_file_scopes glob 内,否则改它不触发任何回归(无守护)。
任一违规打印报告并 return 1。用法: python tools/scan_anti_regression_gate.py [--base-ref d4589d77]
"""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from typing import Dict, List, Optional, Sequence, Set

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.long_gate_manifest import _scope_matches_path  # noqa: E402
from tools.test_registry import (  # noqa: E402
    iter_required_regression_common_scope_policy,
    iter_required_regression_groups,
)

DEFAULT_BASE_REF = "d4589d77"
SOURCE_ROOTS = ("core/", "data/", "web/", "desktop/", "plugins/")
ROOT_SOURCE_FILES = frozenset({"app.py", "app_new_ui.py", "config.py"})
SCOPE_KEYS = ("input_file_scopes", "config_file_scopes", "tool_file_scopes", "dependency_file_scopes")


def _git_added_python_files(base_ref: str, root: str) -> List[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=A", str(base_ref), "--", "*.py"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "git diff failed").strip())
    paths = []
    for line in proc.stdout.splitlines():
        rel_path = line.strip().replace("\\", "/")
        if rel_path.endswith(".py") and os.path.isfile(os.path.join(root, rel_path)):
            paths.append(rel_path)
    return sorted(dict.fromkeys(paths))


def is_collected_test_path(rel_path: str) -> bool:
    """与 pyproject python_files=[test_*.py,*_test.py,regression_*.py] + testpaths=tests 对齐。"""
    if not rel_path.startswith("tests/"):
        return False
    name = rel_path.rsplit("/", 1)[-1]
    return name.startswith("test_") or name.endswith("_test.py") or name.startswith("regression_")


def is_production_source_path(rel_path: str) -> bool:
    return rel_path in ROOT_SOURCE_FILES or rel_path.startswith(SOURCE_ROOTS)


def _parse(root: str, rel_path: str) -> ast.Module:
    with open(os.path.join(root, rel_path), encoding="utf-8") as handle:
        return ast.parse(handle.read(), filename=rel_path)


def _has_test_function(tree: ast.AST) -> bool:
    # ast.walk 命中任意层级(含类内方法)的 test_ 函数。注:这比 pytest 默认 python_classes=Test*
    # 略宽——仅含「非 Test* 类内 test_ 方法」的文件 pytest 实际收集 0、本门禁却放行。门禁刻意宁宽勿
    # 误伤(误伤会违反 B-兼容铁律),且实测落地态 0 此类实例;若日后需对齐 pytest 收集口径再收紧。
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        for node in ast.walk(tree)
    )


def scan_missing_test_function(root: str, test_paths: Sequence[str]) -> List[str]:
    """新增收集型测试文件须含 test 函数(模块级 def test_ 或类内 test_ 方法,ast.walk 全覆盖)。
    无任何 test 函数者 = 没转 pytest 的 main-style 脚本 / 纯 import 空壳 / 只有 async def main 的伪回归——
    pytest 实际收集 0 个真实用例,放行即名存实亡的回潮。"""
    return [rel_path for rel_path in test_paths if not _has_test_function(_parse(root, rel_path))]


def scan_missing_docstring(root: str, test_paths: Sequence[str]) -> List[str]:
    return [rel_path for rel_path in test_paths if ast.get_docstring(_parse(root, rel_path)) is None]


def load_scope_globs() -> Set[str]:
    globs: Set[str] = set()
    for group in iter_required_regression_groups():
        for key in SCOPE_KEYS:
            globs.update(group.get(key) or [])
    policy = iter_required_regression_common_scope_policy()
    if isinstance(policy, dict):
        for key in SCOPE_KEYS:
            globs.update(policy.get(key) or [])
    return globs


def scan_uncovered_source(source_paths: Sequence[str], scope_globs: Set[str]) -> List[str]:
    return [
        rel_path
        for rel_path in source_paths
        if not any(_scope_matches_path(rel_path, glob) for glob in scope_globs)
    ]


def scan_added(base_ref: str, root: str) -> Dict[str, List[str]]:
    added = _git_added_python_files(base_ref, root)
    test_paths = [p for p in added if is_collected_test_path(p)]
    source_paths = [p for p in added if is_production_source_path(p)]
    return {
        "missing_test_function": scan_missing_test_function(root, test_paths),
        "missing_docstring": scan_missing_docstring(root, test_paths),
        "uncovered_source": scan_uncovered_source(source_paths, load_scope_globs()),
    }


_RULE_HINTS = {
    "missing_test_function": "新增收集型测试文件须含 test 函数(模块级 def test_ 或类内 test_ 方法),否则 pytest 收集 0 用例",
    "missing_docstring": "新增测试文件须有模块级 docstring",
    "uncovered_source": "新增生产源文件须落在某 required 回归组 scope glob 内(否则改它不触发回归)",
}


def format_report(result: Dict[str, List[str]]) -> str:
    lines = []
    for rule, hint in _RULE_HINTS.items():
        hits = result.get(rule) or []
        if hits:
            lines.append(f"✗ {rule}（{hint}）：{len(hits)} 处")
            lines.extend(f"   {path}" for path in hits)
    if not lines:
        return "防回潮门禁通过：自 base-ref 以来新增文件无 main-style / 缺 docstring / 无 scope 覆盖违规。"
    return "防回潮门禁失败：\n" + "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="P7 防回潮门禁:新增文件 main-style / docstring / scope 覆盖三约束。")
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF, help="治理基线提交,默认 d4589d77。")
    parser.add_argument("--root", default=REPO_ROOT, help="仓库根目录。")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = scan_added(str(args.base_ref), os.path.abspath(args.root))
    print(format_report(result))
    return 1 if any(result.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
