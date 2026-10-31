from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple, cast

from .quality_gate_ledger import (
    entry_sort_key,
    load_ledger,
    silent_entry_content_equal,
    silent_entry_has_content,
    silent_entry_key,
)
from .quality_gate_shared import (
    _CLEANUP_KEYWORDS,
    _LOG_METHODS,
    _OBSERVABLE_TARGET_KEYWORDS,
    COMPLEXITY_THRESHOLD,
    FALLBACK_KIND_VALUES,
    FILE_SIZE_LIMIT,
    STARTUP_SAMPLE_EXPECTATIONS,
    QualityGateError,
    collect_globbed_files,
    collect_startup_scope_files,
    read_text_file,
    slugify,
)


@lru_cache(maxsize=512)
def _ast_tree_for_source(rel_path: str, source: str) -> ast.AST:
    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as exc:
        raise QualityGateError(f"无法解析 {rel_path}：{exc}") from exc
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._ast_parent = node  # type: ignore[attr-defined]
    return tree


def _normalized_scan_path(path: str) -> str:
    return str(path).replace("\\", "/")


@dataclass
class ScanFile:
    rel_path: str
    source: str
    source_lines: Optional[List[str]] = None
    tree: Optional[ast.AST] = None


class ScanContext:
    """One immutable source snapshot for a single scan pass."""

    def __init__(
        self,
        *,
        read_text: Optional[Callable[[str], str]] = None,
        collect_globbed: Optional[Callable[[Sequence[str]], List[str]]] = None,
    ) -> None:
        self._read_text = read_text if read_text is not None else read_text_file
        self._collect_globbed = collect_globbed if collect_globbed is not None else collect_globbed_files
        self.files_by_path: Dict[str, ScanFile] = {}

    def normalize_path(self, path: str) -> str:
        return _normalized_scan_path(path)

    def file(self, path: str) -> ScanFile:
        rel_path = self.normalize_path(path)
        cached = self.files_by_path.get(rel_path)
        if cached is None:
            cached = ScanFile(rel_path=rel_path, source=self._read_text(rel_path))
            self.files_by_path[rel_path] = cached
        return cached

    def read_text(self, path: str) -> str:
        return self.file(path).source

    def source_lines(self, path: str) -> List[str]:
        scan_file = self.file(path)
        if scan_file.source_lines is None:
            scan_file.source_lines = scan_file.source.splitlines()
        return scan_file.source_lines

    def ast_tree(self, path: str) -> ast.AST:
        scan_file = self.file(path)
        if scan_file.tree is None:
            scan_file.tree = _ast_tree_for_source(scan_file.rel_path, scan_file.source)
        return scan_file.tree

    def collect_globbed_files(self, patterns: Sequence[str]) -> List[str]:
        return sorted(set(_normalized_scan_path(path) for path in self._collect_globbed(patterns)))


def _ast_tree_for_file(rel_path: str, *, context: Optional[ScanContext] = None) -> ast.AST:
    if context is not None:
        return context.ast_tree(rel_path)
    return _ast_tree_for_source(rel_path, read_text_file(rel_path))


def _find_enclosing_symbol(node: ast.AST) -> str:
    current = node
    while hasattr(current, "_ast_parent"):
        current = current._ast_parent  # type: ignore[attr-defined]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return str(current.name)
        if isinstance(current, ast.ClassDef):
            return str(current.name)
    return "<module>"


def _iter_body_nodes(body: Sequence[ast.stmt]) -> Iterable[ast.AST]:
    module = ast.Module(body=list(body), type_ignores=[])
    return ast.walk(module)


def _contains_keyword(text: str, keywords: Set[str]) -> bool:
    lowered = str(text or "").lower()
    for keyword in keywords:
        if keyword in lowered:
            return True
    return False


def _call_target_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return str(func.id)
    if isinstance(func, ast.Attribute):
        base = _call_target_name(func.value)
        if base:
            return base + "." + str(func.attr)
        return str(func.attr)
    if isinstance(func, ast.Call):
        return _call_target_name(func.func)
    if isinstance(func, ast.Subscript):
        return _call_target_name(func.value)
    return func.__class__.__name__


def _literal_kind(node: Optional[ast.AST]) -> str:
    if node is None:
        return "none"
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None:
            return "none"
        if value is Ellipsis:
            return "ellipsis"
        if isinstance(value, bool):
            return "bool:%s" % ("true" if value else "false")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                return "number:%s" % ("zero" if float(value) == 0.0 else "nonzero")
            except Exception:
                return "number"
        if isinstance(value, str):
            return "string:%s" % ("empty" if value == "" else "text")
    if isinstance(node, ast.Dict):
        return "dict:%s" % ("empty" if len(node.keys) == 0 else "nonempty")
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return "{}:{}".format(node.__class__.__name__.lower(), "empty" if len(node.elts) == 0 else "nonempty")
    if isinstance(node, ast.Call):
        return f"call:{_call_target_name(node.func)}"
    if isinstance(node, ast.Name):
        return "name"
    if isinstance(node, ast.Attribute):
        return f"attr:{str(node.attr)}"
    return node.__class__.__name__.lower()


def _categorize_call(node: ast.Call) -> str:
    target = _call_target_name(node.func)
    tail = target.split(".")[-1]
    if target in {"_launcher_log_contract_warning", "_log_warning", "fallback_log", "launcher_log_warning", "safe_log"}:
        return "log:warning"
    if tail in {"_app_log_once", "_launcher_log_contract_warning", "_log_startup_warning", "_warn_once", "launcher_log_warning", "safe_log"}:
        return "log:warning"
    if tail == "_write_launch_error_with_observability":
        return "log:error"
    if tail in _LOG_METHODS and ("logger" in target or target.endswith(tuple(_LOG_METHODS))):
        return f"log:{tail}"
    if tail == "add" and (
        "collector" in target or "degradation" in target or any(kw.arg in {"code", "scope", "message"} for kw in node.keywords)
    ):
        return "collector:add"
    if target == "os.kill" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == 0:
        return "call:kill_probe"
    if tail in _CLEANUP_KEYWORDS:
        return f"cleanup:{tail}"
    return f"call:{tail}"


def _subscript_key(target: ast.Subscript) -> str:
    slice_node = target.slice
    if isinstance(slice_node, ast.Constant):
        return slugify(slice_node.value)
    if hasattr(ast, "Index") and isinstance(slice_node, ast.Index):  # pragma: no cover - py38 兼容
        inner = getattr(slice_node, "value", None)
        if isinstance(inner, ast.Constant):
            return slugify(inner.value)
    return "item"


def _target_descriptor(target: ast.AST) -> str:
    if isinstance(target, ast.Name):
        return "name"
    if isinstance(target, ast.Attribute):
        return f"attr:{slugify(target.attr)}"
    if isinstance(target, ast.Subscript):
        return f"item:{_subscript_key(target)}"
    return target.__class__.__name__.lower()


def _is_default_literal(node: Optional[ast.AST]) -> bool:
    if node is None:
        return True
    kind = _literal_kind(node)
    return kind in {
        "none",
        "bool:false",
        "number:zero",
        "string:empty",
        "dict:empty",
        "list:empty",
        "tuple:empty",
        "set:empty",
    }


def _collect_fallback_actions(body: Sequence[ast.stmt]) -> List[str]:
    actions = []
    for stmt in body:
        if isinstance(stmt, ast.Return):
            # 这里保留所有 return 的字面量类别，现有分类规范与治理台账已按该口径冻结。
            # 若要改成仅统计默认值回退，必须配套刷新台账与样本基线，不能单点热改。
            actions.append(f"return:{_literal_kind(stmt.value)}")
        elif isinstance(stmt, ast.Assign):
            value_kind = _literal_kind(stmt.value)
            if _is_default_literal(stmt.value):
                actions.append(f"assign:{value_kind}")
        elif isinstance(stmt, ast.AnnAssign):
            if _is_default_literal(stmt.value):
                actions.append(f"assign:{_literal_kind(stmt.value)}")
    for node in _iter_body_nodes(body):
        if isinstance(node, ast.Assign) and _is_default_literal(node.value):
            actions.append(f"nested_assign:{_literal_kind(node.value)}")
        elif isinstance(node, ast.Return) and _is_default_literal(node.value):
            actions.append(f"nested_return:{_literal_kind(node.value)}")
    return sorted(set(actions))


def _collect_observable_channels(body: Sequence[ast.stmt]) -> List[str]:
    channels = set()
    for node in _iter_body_nodes(body):
        if isinstance(node, ast.Call):
            category = _categorize_call(node)
            if category.startswith("log:"):
                channels.add("log")
            elif category == "collector:add":
                channels.add("collector")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            else:
                targets = [cast(ast.AnnAssign, node).target]
            for target in targets:
                descriptor = _target_descriptor(target)
                if _contains_keyword(descriptor, _OBSERVABLE_TARGET_KEYWORDS):
                    channels.add("status_write")
    return sorted(channels)


def _collect_cleanup_actions(try_node: ast.Try, body: Sequence[ast.stmt]) -> List[str]:
    actions = set()
    for stmt in list(try_node.body) + list(body):
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                category = _categorize_call(node)
                if category.startswith("cleanup:"):
                    actions.add(category.split(":", 1)[1])
    return sorted(actions)


def _collect_control_flow(body: Sequence[ast.stmt]) -> List[str]:
    flow = []
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            flow.append("pass")
        elif isinstance(stmt, ast.Return):
            flow.append(f"return:{_literal_kind(stmt.value)}")
        elif isinstance(stmt, ast.Assign):
            if stmt.targets:
                flow.append(f"assign:{_target_descriptor(stmt.targets[0])}:{_literal_kind(stmt.value)}")
            else:
                flow.append(f"assign:{_literal_kind(stmt.value)}")
        elif isinstance(stmt, ast.AnnAssign):
            flow.append(f"assign:{_target_descriptor(stmt.target)}:{_literal_kind(stmt.value)}")
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            flow.append(_categorize_call(stmt.value))
        elif isinstance(stmt, ast.Try):
            flow.append("nested_try")
        elif isinstance(stmt, ast.If):
            flow.append("if")
        elif isinstance(stmt, ast.Continue):
            flow.append("continue")
        elif isinstance(stmt, ast.Break):
            flow.append("break")
        elif isinstance(stmt, ast.Raise):
            flow.append("raise")
        else:
            flow.append(stmt.__class__.__name__.lower())
    return flow


def _is_exception_handler(handler: ast.excepthandler) -> bool:
    if not isinstance(handler, ast.ExceptHandler):
        return False
    if handler.type is None:
        return False
    if isinstance(handler.type, ast.Name):
        return str(handler.type.id) == "Exception"
    if isinstance(handler.type, ast.Tuple):
        for item in handler.type.elts:
            if isinstance(item, ast.Name) and str(item.id) == "Exception":
                return True
    return False


def _is_legacy_silent_swallow(body: Sequence[ast.stmt]) -> bool:
    statements = list(body or [])
    if len(statements) != 1:
        return False
    stmt = statements[0]
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis:
        return True
    return False


def classify_silent_fallback(try_node: ast.Try, handler: ast.ExceptHandler) -> Tuple[str, Dict[str, Any]]:
    observable_channels = _collect_observable_channels(handler.body)
    cleanup_actions = _collect_cleanup_actions(try_node, handler.body)
    fallback_actions = _collect_fallback_actions(handler.body)
    control_flow = _collect_control_flow(handler.body)
    call_categories = []
    for node in _iter_body_nodes(handler.body):
        if isinstance(node, ast.Call):
            call_categories.append(_categorize_call(node))
    call_categories = sorted(set(call_categories))
    if cleanup_actions:
        fallback_kind = "cleanup_best_effort"
    elif observable_channels:
        fallback_kind = "observable_degrade"
    elif fallback_actions:
        fallback_kind = "silent_default_fallback"
    else:
        fallback_kind = "silent_swallow"
    signature = {
        "except_type": "Exception",
        "fallback_kind": fallback_kind,
        "observable_channels": observable_channels,
        "cleanup_actions": cleanup_actions,
        "default_actions": fallback_actions,
        "control_flow": control_flow,
        "call_categories": call_categories,
    }
    return fallback_kind, signature


def scan_silent_fallback_fact_entries(paths: Sequence[str], context: Optional[ScanContext] = None) -> List[Dict[str, Any]]:
    """返回静默回退单文件扫描事实，不分配最终台账 id。"""

    scan_context = context or ScanContext()
    entries = []
    for rel_path in sorted(set([_normalized_scan_path(str(path)) for path in paths])):
        tree = _ast_tree_for_file(rel_path, context=scan_context)
        handlers = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                if not _is_exception_handler(handler):
                    continue
                symbol = _find_enclosing_symbol(handler)
                handlers.append((symbol, int(getattr(handler, "lineno", 0) or 0), node, cast(ast.ExceptHandler, handler)))
        handlers.sort(key=lambda item: (str(item[0]), int(item[1])))
        ordinal_map = defaultdict(int)
        for symbol, _line, try_node, handler in handlers:
            ordinal_map[symbol] += 1
            fallback_kind, signature = classify_silent_fallback(try_node, handler)
            legacy_swallow_hit = _is_legacy_silent_swallow(handler.body)
            if fallback_kind == "silent_swallow" and not legacy_swallow_hit:
                continue
            entry = {
                "path": rel_path,
                "symbol": symbol,
                "handler_signature": signature,
                "handler_context": ast.dump(handler, include_attributes=False),
                "except_ordinal": int(ordinal_map[symbol]),
                "line_start": int(getattr(handler, "lineno", 0) or 0),
                "line_end": int(getattr(handler, "end_lineno", getattr(handler, "lineno", 0) or 0) or 0),
                "legacy_swallow_hit": legacy_swallow_hit,
                "fallback_kind": fallback_kind,
                "signature": signature,
            }
            entries.append(entry)
    return sorted(entries, key=entry_sort_key)


def scan_silent_fallback_entries(paths: Sequence[str], context: Optional[ScanContext] = None) -> List[Dict[str, Any]]:
    entries = scan_silent_fallback_fact_entries(paths, context=context)
    _assign_silent_entry_ids(entries)
    return sorted(entries, key=entry_sort_key)


def _assign_silent_entry_ids(entries: List[Dict[str, Any]]) -> None:
    for entry in entries:
        entry["id"] = "fallback:{}:{}:except:{}".format(
            entry.get("path"),
            entry.get("symbol") or "<module>",
            int(entry.get("except_ordinal") or 0),
        )


def validate_startup_samples(entries: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if entries is None:
        entries = scan_silent_fallback_entries(collect_startup_scope_files())
    entry_list = list(entries)
    errors = []
    matched_kinds = set()
    for sample in STARTUP_SAMPLE_EXPECTATIONS:
        matches = [
            entry
            for entry in entry_list
            if str(entry.get("path")) == sample.path
            and str(entry.get("symbol")) == sample.symbol
            and int(entry.get("line_start") or 0) <= sample.line_end
            and int(entry.get("line_end") or 0) >= sample.line_start
        ]
        if not matches:
            errors.append(f"未命中样本：{sample.path}:{sample.symbol}@{sample.line_start}-{sample.line_end}")
            continue
        sample_line_start = int(sample.line_start)
        sample_line_end = int(sample.line_end)

        def _sample_rank(
            entry: Dict[str, Any],
            target_line_start: int = sample_line_start,
            target_line_end: int = sample_line_end,
        ) -> Tuple[int, int, int]:
            line_start = int(entry.get("line_start") or 0)
            line_end = int(entry.get("line_end") or 0)
            overlap_start = max(line_start, target_line_start)
            overlap_end = min(line_end, target_line_end)
            overlap = overlap_end - overlap_start + 1 if overlap_end >= overlap_start else 0
            distance = abs(line_start - target_line_start) + abs(line_end - target_line_end)
            return (distance, -overlap, int(entry.get("except_ordinal") or 0))

        matches.sort(key=_sample_rank)
        match = matches[0]
        if str(match.get("fallback_kind")) != sample.fallback_kind:
            errors.append(
                "样本分类不匹配：{}:{} 期望 {}，实际 {}".format(sample.path, sample.symbol, sample.fallback_kind, match.get("fallback_kind"))
            )
        matched_kinds.add(str(match.get("fallback_kind")))
    present_kinds = {
        str(entry.get("fallback_kind"))
        for entry in entry_list
        if str(entry.get("fallback_kind")) in FALLBACK_KIND_VALUES
    }
    missing_kinds = sorted(present_kinds - matched_kinds)
    if missing_kinds:
        errors.append("四类分类样本覆盖不完整：{}".format(", ".join(missing_kinds)))
    if errors:
        raise QualityGateError("启动链样本点校验失败：\n" + "\n".join(errors))
    return {
        "sample_count": len(STARTUP_SAMPLE_EXPECTATIONS),
        "fallback_kinds": sorted(matched_kinds),
    }


def complexity_scan_map(
    paths: Sequence[str],
    include_all: bool = False,
    context: Optional[ScanContext] = None,
) -> Dict[str, Dict[str, Any]]:
    if importlib.util.find_spec("radon") is None:
        raise QualityGateError("缺少 radon，无法执行复杂度扫描")
    try:
        radon_complexity = importlib.import_module("radon.complexity")
    except ImportError as exc:
        raise QualityGateError("缺少 radon，无法执行复杂度扫描") from exc
    cc_visit = getattr(radon_complexity, "cc_visit", None)
    if not callable(cc_visit):
        raise QualityGateError("radon.complexity.cc_visit 不可用")
    results = {}
    scan_context = context or ScanContext()
    for rel_path in sorted(set([_normalized_scan_path(str(path)) for path in paths])):
        source = scan_context.read_text(rel_path)
        try:
            blocks = cast(Iterable[Any], cc_visit(source))
        except SyntaxError as exc:
            raise QualityGateError(f"复杂度扫描无法解析 {rel_path}：{exc}") from exc
        except Exception as exc:
            raise QualityGateError(f"复杂度扫描失败 {rel_path}：{exc}") from exc
        for block in blocks:
            complexity = int(getattr(block, "complexity", 0) or 0)
            if not include_all and complexity <= COMPLEXITY_THRESHOLD:
                continue
            name = str(getattr(block, "name", "") or "")
            key = f"{rel_path}:{name}"
            results[key] = {
                "path": rel_path,
                "symbol": name,
                "current_value": complexity,
                "threshold": COMPLEXITY_THRESHOLD,
                "line": int(getattr(block, "lineno", 0) or 0),
                "rank": str(getattr(block, "letter", "?")),
            }
    return results


def scan_complexity_entries(paths: Sequence[str], context: Optional[ScanContext] = None) -> List[Dict[str, Any]]:
    return [results for _, results in sorted(complexity_scan_map(paths, context=context).items())]


def scan_oversize_entries(paths: Sequence[str], context: Optional[ScanContext] = None) -> List[Dict[str, Any]]:
    scan_context = context or ScanContext()
    entries = []
    for rel_path in sorted(set([_normalized_scan_path(str(path)) for path in paths])):
        line_count = len(scan_context.source_lines(rel_path))
        if line_count > FILE_SIZE_LIMIT:
            entries.append({"path": rel_path, "current_value": line_count, "limit": FILE_SIZE_LIMIT})
    return entries


def _strict_silent_fallback_scan_entries() -> List[Dict[str, Any]]:
    """Return the entries enforced by the strict silent-fallback gate.

    The strict gate intentionally follows the repository's current quality-gate
    boundary rather than the historical full-inventory exploration scope:

    - startup scope keeps all four fallback/degradation classifications;
    - non-startup scope only continues to track legacy silent-swallow debt.

    This mirrors ``architecture_silent_scan_entries`` in
    ``tools.quality_gate_operations`` without importing it at module import time,
    avoiding a circular import for users that import this module as a scanner API.
    """

    from .quality_gate_operations import architecture_silent_scan_entries

    return architecture_silent_scan_entries()


def _strict_silent_fallback_summary(
    entries: Sequence[Dict[str, Any]],
    ledger_entries: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    by_kind: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for entry in entries:
        kind = str(entry.get("fallback_kind") or "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
    for entry in ledger_entries:
        status = str(entry.get("status") or "open")
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "scan_entry_count": len(list(entries)),
        "ledger_entry_count": len(list(ledger_entries)),
        "by_fallback_kind": dict(sorted(by_kind.items())),
        "ledger_by_status": dict(sorted(by_status.items())),
    }


def run_strict_silent_fallback_gate(*, emit_json: bool = False, quiet: bool = True) -> int:
    """Validate the current strict silent-fallback gate against the debt ledger.

    Exit code semantics:

    - ``0``: current strict scan and ledger are aligned;
    - ``2``: the strict gate detected drift or malformed ledger data.

    The default ``quiet=True`` keeps successful execution silent so it can be used
    as an acceptance-table command with "通过，无输出" semantics. Pass
    ``emit_json=True`` to print a reproducible count summary on success.
    """

    ledger = load_ledger(required=True)

    scan_entries = _strict_silent_fallback_scan_entries()
    validate_startup_samples()
    ledger_entries = list(cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or [])

    scan_by_key = {silent_entry_key(entry): entry for entry in scan_entries}
    active_ledger_entries = [entry for entry in ledger_entries if str(entry.get("status") or "open") != "fixed"]
    for entry in active_ledger_entries:
        if not silent_entry_has_content(entry):
            raise QualityGateError("静默回退条目缺少 handler_signature / handler_context 原文，请显式复核并重取内容基线：{}".format(entry.get("id")))
    ledger_by_key = {silent_entry_key(entry): entry for entry in active_ledger_entries}
    missing_in_ledger = sorted(set(scan_by_key) - set(ledger_by_key))
    missing_in_scan = sorted(set(ledger_by_key) - set(scan_by_key))
    if missing_in_ledger or missing_in_scan:
        raise QualityGateError(
            "strict silent-fallback gate drift: "
            f"missing_in_ledger={missing_in_ledger[:10]} "
            f"missing_in_scan={missing_in_scan[:10]}"
        )
    for key, current in scan_by_key.items():
        if not silent_entry_content_equal(current, ledger_by_key[key]):
            raise QualityGateError("strict silent-fallback gate handler content drift: {}".format(ledger_by_key[key].get("id")))

    if emit_json:
        print(json.dumps(_strict_silent_fallback_summary(scan_entries, ledger_entries), ensure_ascii=False, indent=2, sort_keys=True))
    elif not quiet:
        summary = _strict_silent_fallback_summary(scan_entries, ledger_entries)
        print(
            "strict silent-fallback gate passed: "
            f"scan_entry_count={summary['scan_entry_count']} "
            f"ledger_entry_count={summary['ledger_entry_count']}"
        )
    return 0


def _production_inventory_paths() -> List[str]:
    roots = ["core", "data", "web", "desktop", "plugins"]
    paths: List[str] = []
    for root in roots:
        paths.extend(collect_globbed_files([f"{root}/**/*.py"]))
    for path in ["app.py", "app_new_ui.py"]:
        try:
            read_text_file(path)
        except QualityGateError:
            continue
        paths.append(path)
    return sorted(set(paths))


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="APS quality-gate scan utilities")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="validate the current strict silent-fallback gate against 开发文档/技术债务治理台账.md",
    )
    parser.add_argument("--json", action="store_true", help="print JSON summary for --strict or --inventory-summary")
    parser.add_argument(
        "--inventory-summary",
        action="store_true",
        help="print the historical production-scope silent-fallback inventory summary",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        help="explicit Python files to scan for --inventory-summary; defaults to production inventory scope",
    )
    return parser


def _run_inventory_summary(paths: Optional[Sequence[str]], *, emit_json: bool) -> int:
    scan_paths = sorted(set(paths or _production_inventory_paths()))
    entries = scan_silent_fallback_entries(scan_paths)
    by_kind: Dict[str, int] = {}
    for entry in entries:
        kind = str(entry.get("fallback_kind") or "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
    strict_count = sum(
        1
        for entry in entries
        if str(entry.get("fallback_kind") or "") in {"silent_swallow", "silent_default_fallback"}
    )
    payload = {
        "scanned_file_count": len(scan_paths),
        "entry_count": len(entries),
        "strict_candidate_count": strict_count,
        "by_fallback_kind": dict(sorted(by_kind.items())),
    }
    if emit_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "production inventory summary: "
            f"files={payload['scanned_file_count']} entries={payload['entry_count']} "
            f"strict_candidates={payload['strict_candidate_count']} "
            f"by_fallback_kind={payload['by_fallback_kind']}"
        )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.strict:
            return run_strict_silent_fallback_gate(emit_json=bool(args.json), quiet=True)
        if args.inventory_summary:
            return _run_inventory_summary(args.paths, emit_json=bool(args.json))
        parser.print_help()
        return 0
    except QualityGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


__all__ = [
    "ScanContext",
    "ScanFile",
    "classify_silent_fallback",
    "scan_complexity_entries",
    "scan_oversize_entries",
    "scan_silent_fallback_fact_entries",
    "scan_silent_fallback_entries",
    "validate_startup_samples",
    "complexity_scan_map",
    "run_strict_silent_fallback_gate",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
