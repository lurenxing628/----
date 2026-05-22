#!/usr/bin/env python3
"""Scan Python files for syntax/features that are not safe for Python 3.8.

The project is delivered on Python 3.8.10, so this tool has two jobs:

1. Ask the parser to parse each file as Python 3.8 grammar. Anything rejected
   here is a hard syntax compatibility problem for Python 3.8. This catches
   syntax introduced after Python 3.8, including pattern matching (3.10),
   ``except*`` (3.11), PEP 695 type parameter/type alias syntax (3.12),
   and t-strings / unparenthesized multiple exception types (3.14) when the
   host interpreter knows how to parse them.
2. Flag compatibility risks that may still parse as ordinary Python 3.8
   expressions, such as dict ``|``/``|=`` (3.9), ``list[str]`` (3.9 generic
   aliases), ``A | B`` in annotations (3.10), and starred variadic-generic
   annotations like ``tuple[*Ts]`` (3.11).

The script itself intentionally uses Python 3.8-compatible syntax.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import tokenize
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY38_FEATURE_VERSION = (3, 8)

# Reference inventory from Python What's New / language reference documents.
# Parser feature-version checks cover grammar-only entries; explicit AST checks
# cover entries that are syntactically valid expressions on Python 3.8 but whose
# semantics/runtime support only arrived later.
NEW_SYNTAX_REFERENCE = (
    ("3.9", "PEP 584", "dict merge/update operators", "explicit AST check: DICT_MERGE_OPERATOR"),
    ("3.9", "PEP 585", "built-in/stdlib collection generic aliases", "explicit annotation check"),
    ("3.10", "PEP 604", "X | Y union type operator", "explicit annotation/isinstance check"),
    ("3.10", "PEP 634/635/636", "structural pattern matching", "parser feature_version=(3, 8)"),
    ("3.11", "PEP 646", "starred variadic-generic annotations", "explicit annotation check"),
    ("3.11", "PEP 654", "Exception Groups and except*", "parser feature_version=(3, 8)"),
    ("3.12", "PEP 695", "type statement and type parameter syntax", "parser feature_version=(3, 8)"),
    ("3.12", "PEP 701", "formalized f-string grammar", "parser/tokenizer best-effort"),
    ("3.13", "PEP 696", "type parameter defaults", "parser feature_version=(3, 8); under PEP 695 syntax"),
    ("3.14", "PEP 750", "template string literals (t-strings)", "parser feature_version=(3, 8)"),
    ("3.14", "PEP 758", "unparenthesized multiple exception types", "parser feature_version=(3, 8)"),
)

SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "backups",
    "build",
    "dist",
    "evidence",
    "logs",
    "node_modules",
    "venv",
}

# PEP 585 generic aliases that are easy to confuse with ordinary Python 3.8
# syntax because expressions such as list[str] parse on 3.8 but are not
# subscriptable at runtime until 3.9.
PEP585_QUALIFIED_TARGETS = {
    "builtins.dict",
    "builtins.frozenset",
    "builtins.list",
    "builtins.set",
    "builtins.tuple",
    "builtins.type",
    "collections.ChainMap",
    "collections.Counter",
    "collections.OrderedDict",
    "collections.defaultdict",
    "collections.deque",
    "collections.abc.AsyncGenerator",
    "collections.abc.AsyncIterable",
    "collections.abc.AsyncIterator",
    "collections.abc.Awaitable",
    "collections.abc.ByteString",
    "collections.abc.Callable",
    "collections.abc.Collection",
    "collections.abc.Container",
    "collections.abc.ContextManager",
    "collections.abc.Coroutine",
    "collections.abc.Generator",
    "collections.abc.Hashable",
    "collections.abc.ItemsView",
    "collections.abc.Iterable",
    "collections.abc.Iterator",
    "collections.abc.KeysView",
    "collections.abc.Mapping",
    "collections.abc.MappingView",
    "collections.abc.MutableMapping",
    "collections.abc.MutableSequence",
    "collections.abc.MutableSet",
    "collections.abc.Reversible",
    "collections.abc.Sequence",
    "collections.abc.Set",
    "collections.abc.ValuesView",
    "contextlib.AbstractAsyncContextManager",
    "contextlib.AbstractContextManager",
    "re.Match",
    "re.Pattern",
}

BUILTIN_PEP585_NAMES = {
    "dict": "builtins.dict",
    "frozenset": "builtins.frozenset",
    "list": "builtins.list",
    "set": "builtins.set",
    "tuple": "builtins.tuple",
    "type": "builtins.type",
}


@dataclass(frozen=True)
class Finding:
    rel_path: str
    line: int
    column: int
    rule: str
    message: str
    snippet: str
    detail: str = ""
    introduced_in: str = ""
    future_annotations: bool = False
    host_parser_accepts: bool = False


@dataclass(frozen=True)
class ScanResult:
    scanned_files: int
    skipped_files: int
    findings: Tuple[Finding, ...]


def normalize_repo_path(path: str) -> str:
    normalized = os.path.normpath(str(path or "")).replace("\\", "/")
    if normalized == ".":
        return ""
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_inside_root(abs_path: str, root: str) -> bool:
    real_root = os.path.normcase(os.path.realpath(root))
    real_path = os.path.normcase(os.path.realpath(abs_path))
    return real_path == real_root or real_path.startswith(real_root + os.sep)


def _should_skip_rel_path(rel_path: str) -> bool:
    parts = [part for part in normalize_repo_path(rel_path).split("/") if part]
    return any(part in SKIP_DIR_NAMES for part in parts)


def collect_python_files(root: str, paths: Sequence[str]) -> Tuple[str, ...]:
    root_abs = os.path.abspath(root)
    collected: Set[str] = set()
    requested = list(paths or ["."])
    for raw_path in requested:
        abs_path = os.path.abspath(os.path.join(root_abs, str(raw_path)))
        if not _is_inside_root(abs_path, root_abs):
            continue
        if os.path.isfile(abs_path):
            rel_path = normalize_repo_path(os.path.relpath(abs_path, root_abs))
            if rel_path.endswith(".py") and not _should_skip_rel_path(rel_path):
                collected.add(rel_path)
            continue
        if not os.path.isdir(abs_path):
            continue
        for current_dir, dirnames, filenames in os.walk(abs_path):
            rel_dir = normalize_repo_path(os.path.relpath(current_dir, root_abs))
            dirnames[:] = [
                name
                for name in dirnames
                if name not in SKIP_DIR_NAMES
                and not _should_skip_rel_path(normalize_repo_path(os.path.join(rel_dir, name)))
            ]
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                file_abs = os.path.join(current_dir, filename)
                rel_path = normalize_repo_path(os.path.relpath(file_abs, root_abs))
                if not _should_skip_rel_path(rel_path):
                    collected.add(rel_path)
    return tuple(sorted(collected))


def read_python_source(abs_path: str) -> str:
    with tokenize.open(abs_path) as handle:
        return handle.read()


def _parse_latest(source: str, filename: str) -> ast.AST:
    return ast.parse(source, filename=filename, type_comments=True)


def _parse_as_py38(source: str, filename: str) -> ast.AST:
    try:
        return ast.parse(source, filename=filename, type_comments=True, feature_version=PY38_FEATURE_VERSION)
    except TypeError:
        # Python 3.8-era ast.parse variants may accept the minor version as an
        # int instead of a (major, minor) tuple. If neither form exists, parsing
        # with the host parser is still useful when the host is exactly 3.8.
        try:
            return ast.parse(source, filename=filename, type_comments=True, feature_version=8)  # type: ignore[arg-type]
        except TypeError:
            return ast.parse(source, filename=filename, type_comments=True)


def _source_line(source: str, line: int) -> str:
    if line <= 0:
        return ""
    lines = source.splitlines()
    if line > len(lines):
        return ""
    return lines[line - 1].strip()


def _has_future_annotations(tree: ast.AST) -> bool:
    if not isinstance(tree, ast.Module):
        return False
    for stmt in tree.body:
        if isinstance(stmt, ast.Expr) and isinstance(getattr(stmt, "value", None), ast.Constant):
            if isinstance(stmt.value.value, str):
                continue
        if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
            for alias in stmt.names:
                if alias.name == "annotations":
                    return True
            continue
        break
    return False


def _is_annotation_context(node: ast.AST) -> bool:
    current = node
    while hasattr(current, "_ast_parent"):
        parent = current._ast_parent  # type: ignore[attr-defined]
        if isinstance(parent, ast.AnnAssign) and parent.annotation is current:
            return True
        if isinstance(parent, ast.arg) and parent.annotation is current:
            return True
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) and parent.returns is current:
            return True
        current = parent
    return False


def _attach_parents(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._ast_parent = node  # type: ignore[attr-defined]
    return tree


def _infer_syntax_introduced_in(error_message: str, snippet: str) -> str:
    text = (error_message or "").lower()
    if "pattern matching" in text:
        return "3.10 / PEP 634"
    if "exception groups" in text or "except*" in (snippet or ""):
        return "3.11 / PEP 654"
    if "type parameter" in text or "type statement" in text:
        if "=" in (snippet or ""):
            return "3.12 / PEP 695 or 3.13 / PEP 696"
        return "3.12 / PEP 695"
    if "t-strings" in text:
        return "3.14 / PEP 750"
    if "except expressions without parentheses" in text:
        return "3.14 / PEP 758"
    return ""


def _collect_import_aliases(tree: ast.AST) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".")[0]
                if alias.name in {"collections", "collections.abc", "contextlib", "re"}:
                    aliases[bound_name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in {"collections", "collections.abc", "contextlib", "re"}:
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    bound_name = alias.asname or alias.name
                    aliases[bound_name] = module + "." + alias.name
    return aliases


def _qualified_name(node: ast.AST, import_aliases: Dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        if node.id in BUILTIN_PEP585_NAMES:
            return BUILTIN_PEP585_NAMES[node.id]
        return import_aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value, import_aliases)
        if prefix:
            return prefix + "." + node.attr
        return node.attr
    return ""


def _annotation_context(prefix: str, name: str) -> str:
    return prefix + name if prefix else name


class AnnotationRiskScanner(ast.NodeVisitor):
    def __init__(self, rel_path: str, source: str, future_annotations: bool, import_aliases: Dict[str, str]) -> None:
        self.rel_path = rel_path
        self.source = source
        self.future_annotations = future_annotations
        self.import_aliases = import_aliases
        self.findings: List[Finding] = []

    def _add(self, node: ast.AST, rule: str, message: str, detail: str = "", introduced_in: str = "") -> None:
        line = int(getattr(node, "lineno", 0) or 0)
        column = int(getattr(node, "col_offset", 0) or 0) + 1 if line else 0
        self.findings.append(
            Finding(
                rel_path=self.rel_path,
                line=line,
                column=column,
                rule=rule,
                message=message,
                detail=detail,
                introduced_in=introduced_in,
                snippet=_source_line(self.source, line),
                future_annotations=self.future_annotations,
                host_parser_accepts=True,
            )
        )

    def _scan_annotation(self, annotation: Optional[ast.AST], context: str) -> None:
        if annotation is None:
            return
        for node in ast.walk(annotation):
            if isinstance(node, ast.Starred):
                self._add(
                    node,
                    "PEP646_VARIADIC_GENERIC",
                    "类型注解使用 *Ts 变长泛型展开；Python 3.8 不支持该注解写法",
                    context,
                    "3.11 / PEP 646",
                )
                continue
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                self._add(
                    node,
                    "PEP604_UNION_TYPE",
                    "类型注解使用 A | B；Python 3.8 运行期不支持该 union type 写法",
                    context,
                    "3.10 / PEP 604",
                )
            elif isinstance(node, ast.Subscript):
                target = _qualified_name(node.value, self.import_aliases)
                if target in PEP585_QUALIFIED_TARGETS:
                    self._add(
                        node,
                        "PEP585_GENERIC_ALIAS",
                        "类型注解使用内置/标准库泛型别名；Python 3.8 运行期不支持该写法",
                        context + " -> " + target,
                        "3.9 / PEP 585",
                    )

    def _scan_arguments(self, args: ast.arguments, context: str) -> None:
        all_args: List[ast.arg] = []
        all_args.extend(getattr(args, "posonlyargs", []))
        all_args.extend(args.args)
        if args.vararg is not None:
            all_args.append(args.vararg)
        all_args.extend(args.kwonlyargs)
        if args.kwarg is not None:
            all_args.append(args.kwarg)
        for arg in all_args:
            self._scan_annotation(arg.annotation, _annotation_context(context, arg.arg))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        context = node.name + "::"
        self._scan_arguments(node.args, context)
        self._scan_annotation(node.returns, node.name + "::return")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        context = node.name + "::"
        self._scan_arguments(node.args, context)
        self._scan_annotation(node.returns, node.name + "::return")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._scan_annotation(node.annotation, "variable")
        self.generic_visit(node)


class RuntimeSyntaxRiskScanner(ast.NodeVisitor):
    def __init__(self, rel_path: str, source: str) -> None:
        self.rel_path = rel_path
        self.source = source
        self.findings: List[Finding] = []

    def _add(self, node: ast.AST, rule: str, message: str, detail: str = "", introduced_in: str = "") -> None:
        line = int(getattr(node, "lineno", 0) or 0)
        column = int(getattr(node, "col_offset", 0) or 0) + 1 if line else 0
        self.findings.append(
            Finding(
                rel_path=self.rel_path,
                line=line,
                column=column,
                rule=rule,
                message=message,
                detail=detail,
                introduced_in=introduced_in,
                snippet=_source_line(self.source, line),
                host_parser_accepts=True,
            )
        )

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.BitOr):
            if _is_annotation_context(node):
                self.generic_visit(node)
                return
            if isinstance(node.left, ast.Dict) or isinstance(node.right, ast.Dict):
                self._add(
                    node,
                    "PEP584_DICT_MERGE_OPERATOR",
                    "运行时代码使用 dict | dict 合并；Python 3.8 的 dict 不支持该操作符",
                    "dict merge expression",
                    "3.9 / PEP 584",
                )
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if isinstance(node.op, ast.BitOr) and isinstance(node.value, ast.Dict):
            self._add(
                node,
                "PEP584_DICT_UPDATE_OPERATOR",
                "运行时代码使用 dict |= other 更新；Python 3.8 的 dict 不支持该操作符",
                "dict update expression",
                "3.9 / PEP 584",
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        target = _qualified_name(node.func, {})
        if target in {"isinstance", "issubclass"} and len(node.args) >= 2:
            type_arg = node.args[1]
            if isinstance(type_arg, ast.BinOp) and isinstance(type_arg.op, ast.BitOr):
                self._add(
                    type_arg,
                    "PEP604_RUNTIME_UNION_TYPE",
                    "isinstance/issubclass 使用 X | Y union type；Python 3.8 不支持该写法",
                    target,
                    "3.10 / PEP 604",
                )
        self.generic_visit(node)


def _is_isinstance_type_arg(node: ast.AST) -> bool:
    parent = getattr(node, "_ast_parent", None)
    if not isinstance(parent, ast.Call) or len(parent.args) < 2 or parent.args[1] is not node:
        return False
    target = _qualified_name(parent.func, {})
    return target in {"isinstance", "issubclass"}


def _syntax_findings_for_source(rel_path: str, source: str) -> Tuple[Optional[ast.AST], List[Finding]]:
    try:
        py38_tree = _attach_parents(_parse_as_py38(source, rel_path))
        return py38_tree, []
    except SyntaxError as exc:
        host_accepts = False
        try:
            _parse_latest(source, rel_path)
            host_accepts = True
        except SyntaxError:
            host_accepts = False
        line = int(exc.lineno or 0)
        column = int(exc.offset or 0)
        message = "Python 3.8 语法解析失败"
        if host_accepts:
            message = "宿主 Python 可解析，但 Python 3.8 语法解析失败；疑似使用了 3.9+ 新语法"
        return None, [
            Finding(
                rel_path=rel_path,
                line=line,
                column=column,
                rule="PY38_PARSE_REJECTED",
                message=message,
                detail=str(exc.msg),
                introduced_in=_infer_syntax_introduced_in(str(exc.msg), _source_line(source, line)),
                snippet=_source_line(source, line),
                host_parser_accepts=host_accepts,
            )
        ]


def scan_source(rel_path: str, source: str, include_annotation_runtime: bool = True) -> Tuple[Finding, ...]:
    tree, findings = _syntax_findings_for_source(rel_path, source)
    if tree is None:
        return tuple(findings)
    if include_annotation_runtime:
        runtime_scanner = RuntimeSyntaxRiskScanner(rel_path, source)
        runtime_scanner.visit(tree)
        findings.extend(runtime_scanner.findings)
        future_annotations = _has_future_annotations(tree)
        scanner = AnnotationRiskScanner(rel_path, source, future_annotations, _collect_import_aliases(tree))
        scanner.visit(tree)
        findings.extend(scanner.findings)
    return tuple(sorted(findings, key=lambda item: (item.rel_path, item.line, item.column, item.rule)))


def scan_paths(root: str, paths: Sequence[str], include_annotation_runtime: bool = True) -> ScanResult:
    root_abs = os.path.abspath(root)
    rel_paths = collect_python_files(root_abs, paths)
    findings: List[Finding] = []
    skipped_files = 0
    for rel_path in rel_paths:
        abs_path = os.path.join(root_abs, rel_path.replace("/", os.sep))
        try:
            source = read_python_source(abs_path)
        except (OSError, UnicodeError, SyntaxError) as exc:
            skipped_files += 1
            findings.append(
                Finding(
                    rel_path=rel_path,
                    line=0,
                    column=0,
                    rule="READ_ERROR",
                    message="无法读取 Python 源文件",
                    detail=str(exc),
                    snippet="",
                )
            )
            continue
        findings.extend(scan_source(rel_path, source, include_annotation_runtime=include_annotation_runtime))
    findings.sort(key=lambda item: (item.rel_path, item.line, item.column, item.rule))
    return ScanResult(scanned_files=len(rel_paths), skipped_files=skipped_files, findings=tuple(findings))


def _summary_by_rule(findings: Iterable[Finding]) -> Dict[str, int]:
    counter: Counter = Counter(finding.rule for finding in findings)
    return dict(sorted(counter.items()))


def _summary_by_file(findings: Iterable[Finding]) -> Dict[str, int]:
    counter: Counter = Counter(finding.rel_path for finding in findings)
    return dict(sorted(counter.items()))


def format_text_report(result: ScanResult, max_examples: int) -> str:
    findings = list(result.findings)
    by_rule = _summary_by_rule(findings)
    syntax_count = by_rule.get("PY38_PARSE_REJECTED", 0)
    soft_count = len(findings) - syntax_count
    lines = [
        "Python 3.8.10 兼容语法扫描结果",
        "================================",
        f"扫描文件数: {result.scanned_files}",
        f"读取失败数: {result.skipped_files}",
        f"Python 3.8 解析器拒绝: {syntax_count}",
        f"解析可过但 Python 3.8 运行/语义风险: {soft_count}",
        f"总发现数: {len(findings)}",
        "",
        "规则来源:",
    ]
    for version, pep, feature, coverage in NEW_SYNTAX_REFERENCE:
        lines.append(f"- Python {version} {pep}: {feature}（{coverage}）")
    lines.extend([
        "",
        "按规则统计:",
    ])
    if by_rule:
        for rule, count in by_rule.items():
            lines.append(f"- {rule}: {count}")
    else:
        lines.append("- 无")
    lines.append("")
    if findings:
        lines.append(f"示例（最多 {max_examples} 条）:")
        for finding in findings[:max_examples]:
            future_note = " future_annotations" if finding.future_annotations else ""
            host_note = " host_parser_accepts" if finding.host_parser_accepts else ""
            position = f"{finding.rel_path}:{finding.line}:{finding.column}"
            lines.append(f"- [{finding.rule}]{future_note}{host_note} {position} {finding.message}")
            if finding.introduced_in:
                lines.append(f"  introduced_in: {finding.introduced_in}")
            if finding.detail:
                lines.append(f"  detail: {finding.detail}")
            if finding.snippet:
                lines.append(f"  code: {finding.snippet}")
    else:
        lines.append("未发现 Python 3.8.10 之后才支持的语法/注解兼容风险。")
    return "\n".join(lines)


def format_json_report(result: ScanResult) -> str:
    payload = {
        "scanned_files": result.scanned_files,
        "skipped_files": result.skipped_files,
        "total_findings": len(result.findings),
        "by_rule": _summary_by_rule(result.findings),
        "by_file": _summary_by_file(result.findings),
        "findings": [asdict(finding) for finding in result.findings],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="扫描仓库 Python 文件中 Python 3.8.10 不兼容的新语法和常见注解兼容风险。"
    )
    parser.add_argument("paths", nargs="*", default=["."], help="要扫描的文件或目录，默认扫描仓库根目录。")
    parser.add_argument("--root", default=REPO_ROOT, help="仓库根目录，默认自动取 tools/..。")
    parser.add_argument(
        "--syntax-only",
        action="store_true",
        help="只检查 Python 3.8 解析器会拒绝的硬语法，不检查 list[str]/A|B 这类注解运行期风险。",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告。")
    parser.add_argument("--max-examples", type=int, default=50, help="文本报告最多展示多少条示例。")
    parser.add_argument("--fail-on-hit", action="store_true", help="发现问题时以退出码 1 结束，便于接入门禁。")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = scan_paths(
        root=os.path.abspath(args.root),
        paths=args.paths,
        include_annotation_runtime=not bool(args.syntax_only),
    )
    if args.json:
        print(format_json_report(result))
    else:
        print(format_text_report(result, max_examples=max(0, int(args.max_examples))))
    if args.fail_on_hit and result.findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
