"""SQL 边界扫描器：服务层不写 SQL（sql_boundary）、仓储层不做裁决（data_policy）两条棘轮规则。

规则口径见 .codestable/roadmap/foundation-boundary-governance §4.2。
- sql_boundary 扫描 core/ 与 web/（core/infrastructure 除外）：
    conn_execute   在 conn 类接收者上调用 execute/executemany/executescript/fetchone/fetchall
    sqlite_connect 直接 sqlite3.connect(...)
    schema_probe   字符串含 sqlite_master 或以 PRAGMA 开头
    sql_literal    字符串以 SELECT/INSERT/UPDATE/DELETE/WITH/CREATE/DROP/ALTER 开头
- data_policy 扫描 data/：
    policy_import    import reject/inconsistent/fail/WorkbenchCommandRejected/WorkbenchCommandUncertain
    policy_raise     raise WorkbenchCommandRejected(...) 或调用 reject(/inconsistent(/fail(
    identifier_param 函数形参被拼进含 FROM/INTO/UPDATE/JOIN 的 SQL 里（按表名读表的逃生口）

用法：
    python -m tools.scan_sql_boundary [--rule sql_boundary|data_policy|all] [--json] [--fail-on-new]
                                      [--refresh [--allow-growth]] [--quiet-when-clean]
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from tools.boundary_baseline import (
    BoundaryBaselineError,
    EntryKey,
    compare_counts,
    default_baseline_path,
    entries_to_counts,
    load_baseline,
    render_comparison,
    total_count,
    write_baseline,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

RULE_SQL_BOUNDARY = "sql_boundary"
RULE_DATA_POLICY = "data_policy"
RULES: Tuple[str, ...] = (RULE_SQL_BOUNDARY, RULE_DATA_POLICY)

SQL_BOUNDARY_ROOTS: Tuple[str, ...] = ("core", "web")
SQL_BOUNDARY_EXCLUDED_PREFIXES: Tuple[str, ...] = ("core/infrastructure/",)
DATA_POLICY_ROOTS: Tuple[str, ...] = ("data",)

CONN_METHODS = frozenset({"execute", "executemany", "executescript", "fetchone", "fetchall"})
CONN_NAMES = frozenset({"conn", "connection", "db", "cursor", "cur"})
POLICY_NAMES = frozenset({"reject", "inconsistent", "fail", "WorkbenchCommandRejected", "WorkbenchCommandUncertain"})
POLICY_EXCEPTIONS = frozenset({"WorkbenchCommandRejected", "WorkbenchCommandUncertain"})
POLICY_CALLS = frozenset({"reject", "inconsistent", "fail"})

_SQL_LITERAL_RE = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|DROP|ALTER)\s+\S")
_PRAGMA_RE = re.compile(r"^\s*PRAGMA\s+\S")
_IDENTIFIER_SQL_RE = re.compile(r"\b(FROM|INTO|UPDATE|JOIN)\s*$|\b(FROM|INTO|UPDATE|JOIN)\s+\S*$", re.IGNORECASE)

BASELINE_NOTES = {
    RULE_SQL_BOUNDARY: "服务层不写 SQL 棘轮基线：SQL 文本只允许在 data/repositories 与 core/infrastructure；条目只减不增，刷新走 --refresh。",
    RULE_DATA_POLICY: "仓储层不做裁决棘轮基线：data/ 不得 import/raise 业务拒绝，也不得把形参当表名拼 SQL；条目只减不增，刷新走 --refresh。",
}


def _iter_python_files(repo_root: str, roots: Sequence[str], excluded_prefixes: Sequence[str] = ()) -> List[str]:
    files: List[str] = []
    for root in roots:
        base = os.path.join(repo_root, root)
        if os.path.isfile(base) and base.endswith(".py"):
            files.append(root.replace("\\", "/"))
            continue
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
            for filename in sorted(filenames):
                if not filename.endswith(".py"):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, filename), repo_root).replace("\\", "/")
                if any(rel.startswith(prefix) for prefix in excluded_prefixes):
                    continue
                files.append(rel)
    return sorted(set(files))


def _receiver_tail(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _receiver_tail(node.func)
    return None


def _is_conn_like(node: ast.AST) -> bool:
    tail = _receiver_tail(node)
    return tail is not None and tail in CONN_NAMES


def _string_parts(node: ast.AST) -> Iterable[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.JoinedStr):
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                yield value.value


def _call_name(node: ast.Call) -> Optional[str]:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def scan_sql_boundary_file(rel_path: str, source: str) -> List[Dict[str, object]]:
    """返回该文件的命中列表：{kind, line}。解析失败直接抛错，门禁 fail closed。"""
    tree = ast.parse(source, filename=rel_path)
    hits: List[Dict[str, object]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if isinstance(node.func, ast.Attribute) and node.func.attr in CONN_METHODS and _is_conn_like(node.func.value):
                hits.append({"kind": "conn_execute", "line": node.lineno})
            elif name == "connect" and isinstance(node.func, ast.Attribute) and _receiver_tail(node.func.value) == "sqlite3":
                hits.append({"kind": "sqlite_connect", "line": node.lineno})
        for text in _string_parts(node):
            if "sqlite_master" in text or _PRAGMA_RE.match(text):
                hits.append({"kind": "schema_probe", "line": getattr(node, "lineno", 0)})
            elif _SQL_LITERAL_RE.match(text):
                hits.append({"kind": "sql_literal", "line": getattr(node, "lineno", 0)})
    return hits


def _function_param_names(node: ast.AST) -> Set[str]:
    names: Set[str] = set()
    args = getattr(node, "args", None)
    if args is None:
        return names
    for arg in list(args.args) + list(args.posonlyargs) + list(args.kwonlyargs):
        names.add(arg.arg)
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    names.discard("self")
    names.discard("cls")
    return names


def _identifier_param_hits(func: ast.AST, params: Set[str]) -> List[int]:
    lines: List[int] = []
    nested: Set[int] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.BinOp):
            if id(node) in nested:
                continue
            leaves: List[ast.AST] = []
            stack = [node]
            while stack:
                current = stack.pop()
                if isinstance(current, ast.BinOp):
                    if current is not node:
                        nested.add(id(current))
                    stack.append(current.right)
                    stack.append(current.left)
                else:
                    leaves.append(current)
            for index, leaf in enumerate(leaves):
                if isinstance(leaf, ast.Name) and leaf.id in params and index > 0:
                    previous = leaves[index - 1]
                    text = "".join(_string_parts(previous))
                    if text and _IDENTIFIER_SQL_RE.search(text):
                        lines.append(node.lineno)
                        break
        elif isinstance(node, ast.JoinedStr):
            text_before = ""
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    text_before += value.value
                elif isinstance(value, ast.FormattedValue):
                    inner = value.value
                    if isinstance(inner, ast.Name) and inner.id in params and _IDENTIFIER_SQL_RE.search(text_before):
                        lines.append(node.lineno)
                        break
                    text_before += " "
    return lines


def scan_data_policy_file(rel_path: str, source: str) -> List[Dict[str, object]]:
    tree = ast.parse(source, filename=rel_path)
    hits: List[Dict[str, object]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in POLICY_NAMES:
                    hits.append({"kind": "policy_import", "line": node.lineno})
        elif isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            name = _call_name(node.exc)
            if name in POLICY_EXCEPTIONS:
                hits.append({"kind": "policy_raise", "line": node.lineno})
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if isinstance(node.func, ast.Name) and name in POLICY_CALLS:
                hits.append({"kind": "policy_raise", "line": node.lineno})
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = _function_param_names(node)
            if params:
                for line in _identifier_param_hits(node, params):
                    hits.append({"kind": "identifier_param", "line": line})
    return hits


def _read(repo_root: str, rel_path: str) -> str:
    with open(os.path.join(repo_root, rel_path), encoding="utf-8") as handle:
        return handle.read()


def scan(rule: str, repo_root: str = REPO_ROOT) -> Dict[str, object]:
    if rule == RULE_SQL_BOUNDARY:
        files = _iter_python_files(repo_root, SQL_BOUNDARY_ROOTS, SQL_BOUNDARY_EXCLUDED_PREFIXES)
        scanner = scan_sql_boundary_file
        roots: Sequence[str] = SQL_BOUNDARY_ROOTS
    elif rule == RULE_DATA_POLICY:
        files = _iter_python_files(repo_root, DATA_POLICY_ROOTS)
        scanner = scan_data_policy_file
        roots = DATA_POLICY_ROOTS
    else:
        raise ValueError(f"未知规则：{rule}")
    entries: List[Dict[str, object]] = []
    for rel_path in files:
        hits = scanner(rel_path, _read(repo_root, rel_path))
        by_kind: Dict[str, List[int]] = {}
        for hit in hits:
            by_kind.setdefault(str(hit["kind"]), []).append(int(hit["line"]))
        for kind, lines in sorted(by_kind.items()):
            entries.append({"path": rel_path, "kind": kind, "count": len(lines), "lines": sorted(lines)})
    return {
        "rule": rule,
        "scan_roots": list(roots),
        "file_count": len(files),
        "entries": entries,
        "total": sum(int(entry["count"]) for entry in entries),
    }


def render_text(result: Dict[str, object]) -> str:
    entries = list(result.get("entries") or [])
    lines = [
        f"[{result['rule']}] 扫描 {result['file_count']} 个文件，命中 {result['total']} 处，涉及 "
        f"{len({str(entry['path']) for entry in entries})} 个文件"
    ]
    by_kind: Dict[str, int] = {}
    for entry in entries:
        by_kind[str(entry["kind"])] = by_kind.get(str(entry["kind"]), 0) + int(entry["count"])
    for kind, count in sorted(by_kind.items()):
        lines.append(f"  {kind}: {count}")
    for entry in sorted(entries, key=lambda item: (-int(item["count"]), str(item["path"]), str(item["kind"])))[:15]:
        lines.append(f"  {entry['count']:3d}  {entry['path']}  ({entry['kind']}: 行 {', '.join(str(x) for x in entry['lines'][:6])})")
    return "\n".join(lines)


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SQL 边界棘轮扫描器（服务层不写 SQL / 仓储层不做裁决）")
    parser.add_argument("--rule", choices=list(RULES) + ["all"], default="all")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--fail-on-new", action="store_true", help="相对基线有新增/增加/失效条目即退出码 1；基线异常退出码 2")
    parser.add_argument("--refresh", action="store_true", help="按当前扫描结果重写基线（默认拒绝总命中数增长）")
    parser.add_argument("--allow-growth", action="store_true", help="允许 --refresh 时总命中数增长（须人工核对）")
    parser.add_argument("--quiet-when-clean", action="store_true", help="相对基线无新增时不输出")
    parser.add_argument("--repo-root", default=REPO_ROOT, help=argparse.SUPPRESS)
    return parser.parse_args(list(argv) if argv is not None else None)


def _error(message: str) -> None:
    print(f"[sql-boundary] {message}", file=sys.stderr, flush=True)


def run_rule(rule: str, args: argparse.Namespace) -> int:
    try:
        result = scan(rule, args.repo_root)
    except SyntaxError as exc:
        _error(f"源码解析失败，门禁已阻断：{exc}")
        return 2
    current = entries_to_counts(list(result["entries"]))  # type: ignore[arg-type]
    baseline_path = default_baseline_path(args.repo_root, rule)
    if args.refresh:
        try:
            previous = load_baseline(baseline_path, expected_rule=rule)
        except BoundaryBaselineError as exc:
            _error(str(exc))
            return 2
        if previous is not None and total_count(current) > total_count(previous) and not args.allow_growth:
            _error(
                f"{rule} 刷新被拒绝：总命中数 {total_count(previous)} -> {total_count(current)} 增长；"
                "请先消除新增债务，或人工核对后加 --allow-growth"
            )
            return 1
        write_baseline(
            baseline_path,
            rule=rule,
            scan_roots=list(result["scan_roots"]),  # type: ignore[arg-type]
            note=BASELINE_NOTES[rule],
            counts=current,
        )
        print(f"[{rule}] 基线已写入 {os.path.relpath(baseline_path, args.repo_root)}：{len(current)} 条目 / {total_count(current)} 处")
        return 0
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not args.fail_on_new:
        print(render_text(result), flush=True)
        return 0
    try:
        baseline = load_baseline(baseline_path, expected_rule=rule)
    except BoundaryBaselineError as exc:
        _error(str(exc))
        return 2
    comparison = compare_counts(current, baseline)
    if comparison.baseline_missing:
        _error(f"{rule} 基线缺失：{baseline_path}；请先查看扫描结果并受控执行 --refresh")
        return 2
    if comparison.clean and args.quiet_when_clean:
        return 0
    for line in render_comparison(rule, comparison):
        print(line, flush=True)
    return 1 if comparison.has_debt else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    rules = list(RULES) if args.rule == "all" else [args.rule]
    exit_code = 0
    for rule in rules:
        code = run_rule(rule, args)
        exit_code = max(exit_code, code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
