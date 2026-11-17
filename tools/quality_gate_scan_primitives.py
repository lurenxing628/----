"""门禁扫描原语：单次扫描的源码快照、静默回退分类、启动链样本校验与复杂度扫描。

台账核对（`quality_gate_operations`）、架构扫描门面（`architecture_scan_cache`）与严格门禁 CLI
（`quality_gate_scan`）共用这里的原语；本模块不反向导入它们。
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, cast

from .quality_gate_ledger import complexity_entry_key
from .quality_gate_shared import (
    _CLEANUP_KEYWORDS,
    _LOG_METHODS,
    _OBSERVABLE_TARGET_KEYWORDS,
    SILENT_FALLBACK_EXTERNAL_IO_CALLS,
    SILENT_FALLBACK_PURE_VALUE_CALLS,
    SILENT_FALLBACK_PURE_VALUE_METHODS,
    STARTUP_SAMPLE_EXPECTATIONS,
    QualityGateError,
    read_text_file,
    repo_abs,
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


@dataclass
class ScanFile:
    rel_path: str
    source: str
    source_lines: Optional[List[str]] = None
    tree: Optional[ast.AST] = None


class ScanContext:
    """One immutable source snapshot of repo_root for a single scan pass.

    路径必须是规范的仓库相对路径（由 repo_rel 产出），本快照不改写路径身份。
    """

    def __init__(self, repo_root: str) -> None:
        self.repo_root = repo_root
        self.files_by_path: Dict[str, ScanFile] = {}

    def file(self, rel_path: str) -> ScanFile:
        cached = self.files_by_path.get(rel_path)
        if cached is None:
            cached = ScanFile(rel_path=rel_path, source=read_text_file(repo_abs(self.repo_root, rel_path)))
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


def _find_enclosing_symbol(node: ast.AST) -> str:
    current = node
    while hasattr(current, "_ast_parent"):
        current = current._ast_parent  # type: ignore[attr-defined]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
        if isinstance(current, ast.ClassDef):
            return current.name
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
    if tail in {"_app_log_once", "_launcher_log_contract_warning", "_warn_once", "launcher_log_warning", "safe_log"}:
        return "log:warning"
    if tail == "write_launch_error":
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


def _import_from_base(node: ast.ImportFrom, rel_path: str) -> str:
    """from 导入的模块限定名；相对导入按本文件所在包展开。"""
    package = rel_path.split("/")[:-1]
    parts = package[: len(package) - node.level + 1] if node.level else []
    if node.module:
        parts.append(node.module)
    return ".".join(parts)


def _module_name_bindings(tree: ast.AST, rel_path: str) -> Dict[str, Optional[str]]:
    """本模块每个被绑定的名字 → 它导入的完整限定名。

    被 def/class/参数/赋值等本地绑定、或各处导入目标不一致的名字记 None（不可解析）；
    不在表里的裸名按内建名解析。
    """
    bindings: Dict[str, Optional[str]] = {}

    def bind(name: str, target: Optional[str]) -> None:
        if name in bindings and bindings[name] != target:
            target = None
        bindings[name] = target

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    bind(alias.asname, alias.name)
                else:
                    head = alias.name.split(".")[0]
                    bind(head, head)
        elif isinstance(node, ast.ImportFrom):
            base = _import_from_base(node, rel_path)
            for alias in node.names:
                bind(alias.asname or alias.name, f"{base}.{alias.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bind(node.name, None)
        elif isinstance(node, ast.arg):
            bind(node.arg, None)
        elif isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
            bind(node.id, None)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bind(node.name, None)
    return bindings


def _resolve_call_identity(func: ast.AST, bindings: Dict[str, Optional[str]]) -> Optional[str]:
    attrs: List[str] = []
    node = func
    while isinstance(node, ast.Attribute):
        attrs.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    head = bindings.get(node.id, node.id)
    if head is None:
        return None
    return ".".join([head, *reversed(attrs)])


def _is_broad_io_boundary(try_node: ast.Try, bindings: Dict[str, Optional[str]]) -> bool:
    """try 体至少调用一次外部 I/O，且其余调用全是纯取值转换（名单见 quality_gate_shared）。"""
    io_seen = False
    for node in _iter_body_nodes(try_node.body):
        if not isinstance(node, ast.Call):
            continue
        identity = _resolve_call_identity(node.func, bindings)
        if identity in SILENT_FALLBACK_EXTERNAL_IO_CALLS:
            io_seen = True
        elif identity in SILENT_FALLBACK_PURE_VALUE_CALLS:
            continue
        elif not (
            identity is None
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in SILENT_FALLBACK_PURE_VALUE_METHODS
        ):
            return False
    return io_seen


def classify_silent_fallback(
    try_node: ast.Try, handler: ast.ExceptHandler, bindings: Dict[str, Optional[str]]
) -> Tuple[str, Dict[str, Any]]:
    observable_channels = _collect_observable_channels(handler.body)
    cleanup_actions = _collect_cleanup_actions(try_node, handler.body)
    fallback_actions = _collect_fallback_actions(handler.body)
    control_flow = _collect_control_flow(handler.body)
    call_categories = []
    for node in _iter_body_nodes(handler.body):
        if isinstance(node, ast.Call):
            call_categories.append(_categorize_call(node))
    call_categories = sorted(set(call_categories))
    if _is_broad_io_boundary(try_node, bindings):
        fallback_kind = "broad_io_boundary"
    elif cleanup_actions:
        fallback_kind = "cleanup_best_effort"
    elif observable_channels:
        fallback_kind = "observable_degrade"
    elif fallback_actions:
        fallback_kind = "silent_default_fallback"
    else:
        fallback_kind = "silent_swallow"
    # 签名只描述处理器内容；分类只由条目顶层 fallback_kind 承载。
    signature = {
        "observable_channels": observable_channels,
        "cleanup_actions": cleanup_actions,
        "default_actions": fallback_actions,
        "control_flow": control_flow,
        "call_categories": call_categories,
    }
    return fallback_kind, signature


def scan_silent_fallback_entries(rel_path: str, *, context: ScanContext) -> List[Dict[str, Any]]:
    """单文件静默回退条目（含台账 id），按 (symbol, except_ordinal) 有序。

    except_ordinal 对每个 except Exception 处理器递增，之后才跳过两类非回退处理器：顶层最后一条
    语句是 raise 的（清理或转换后重抛），以及非遗留 silent_swallow；台账永久 id 依赖这一编号。
    """
    tree = context.ast_tree(rel_path)
    bindings = _module_name_bindings(tree, rel_path)
    handlers = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if not _is_exception_handler(handler):
                continue
            symbol = _find_enclosing_symbol(handler)
            handlers.append((symbol, handler.lineno, node, cast(ast.ExceptHandler, handler)))
    handlers.sort(key=lambda item: (item[0], item[1]))
    ordinal_map = defaultdict(int)
    entries = []
    for symbol, _line, try_node, handler in handlers:
        ordinal_map[symbol] += 1
        if isinstance(handler.body[-1], ast.Raise):
            continue
        fallback_kind, signature = classify_silent_fallback(try_node, handler, bindings)
        legacy_swallow_hit = _is_legacy_silent_swallow(handler.body)
        if fallback_kind == "silent_swallow" and not legacy_swallow_hit:
            continue
        entries.append({
            "path": rel_path,
            "symbol": symbol,
            "handler_signature": signature,
            "handler_context": ast.dump(handler, include_attributes=False),
            "except_ordinal": ordinal_map[symbol],
            "line_start": handler.lineno,
            "line_end": handler.end_lineno,
            "legacy_swallow_hit": legacy_swallow_hit,
            "fallback_kind": fallback_kind,
            "id": f"fallback:{rel_path}:{symbol}:except:{ordinal_map[symbol]}",
        })
    return entries


def validate_startup_samples(entries: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    errors = []
    matched_kinds = set()
    for sample in STARTUP_SAMPLE_EXPECTATIONS:
        matches = [
            entry
            for entry in entries
            if entry["path"] == sample.path
            and entry["symbol"] == sample.symbol
            and entry["line_start"] <= sample.line_end
            and entry["line_end"] >= sample.line_start
        ]
        if not matches:
            errors.append(f"未命中样本：{sample.path}:{sample.symbol}@{sample.line_start}-{sample.line_end}")
            continue

        def _sample_rank(
            entry: Dict[str, Any],
            target_line_start: int = sample.line_start,
            target_line_end: int = sample.line_end,
        ) -> Tuple[int, int, int]:
            line_start = entry["line_start"]
            line_end = entry["line_end"]
            overlap_start = max(line_start, target_line_start)
            overlap_end = min(line_end, target_line_end)
            overlap = overlap_end - overlap_start + 1 if overlap_end >= overlap_start else 0
            distance = abs(line_start - target_line_start) + abs(line_end - target_line_end)
            return (distance, -overlap, entry["except_ordinal"])

        matches.sort(key=_sample_rank)
        match = matches[0]
        if match["fallback_kind"] != sample.fallback_kind:
            errors.append(
                "样本分类不匹配：{}:{} 期望 {}，实际 {}".format(sample.path, sample.symbol, sample.fallback_kind, match["fallback_kind"])
            )
        matched_kinds.add(match["fallback_kind"])
    present_kinds = {entry["fallback_kind"] for entry in entries}
    missing_kinds = sorted(present_kinds - matched_kinds)
    if missing_kinds:
        errors.append("分类样本覆盖不完整：{}".format(", ".join(missing_kinds)))
    if errors:
        raise QualityGateError("启动链样本点校验失败：\n" + "\n".join(errors))
    return {
        "sample_count": len(STARTUP_SAMPLE_EXPECTATIONS),
        "fallback_kinds": sorted(matched_kinds),
    }


def complexity_scan_map(rel_path: str, *, context: ScanContext) -> Dict[str, Dict[str, Any]]:
    """单文件全部复杂度块，按 complexity_entry_key 建键；阈值过滤只在 aggregate 做一次。"""
    if importlib.util.find_spec("radon") is None:
        raise QualityGateError("缺少 radon，无法执行复杂度扫描")
    try:
        radon_complexity = importlib.import_module("radon.complexity")
    except ImportError as exc:
        raise QualityGateError("缺少 radon，无法执行复杂度扫描") from exc
    cc_visit = getattr(radon_complexity, "cc_visit", None)
    if not callable(cc_visit):
        raise QualityGateError("radon.complexity.cc_visit 不可用")
    source = context.read_text(rel_path)
    try:
        blocks = cast(Iterable[Any], cc_visit(source))
    except SyntaxError as exc:
        raise QualityGateError(f"复杂度扫描无法解析 {rel_path}：{exc}") from exc
    except Exception as exc:
        raise QualityGateError(f"复杂度扫描失败 {rel_path}：{exc}") from exc
    results: Dict[str, Dict[str, Any]] = {}
    for block in blocks:
        record = {"path": rel_path, "symbol": block.fullname, "current_value": block.complexity}
        # 同一命名空间同名的多次定义（property getter/setter、@overload、条件重定义）是同一个符号绑定，
        # 按最大复杂度计；不同类的同名方法由 radon 限定名区分。
        key = complexity_entry_key(record)
        existing = results.get(key)
        if existing is None or block.complexity > existing["current_value"]:
            results[key] = record
    return results


__all__ = [
    "ScanContext",
    "ScanFile",
    "classify_silent_fallback",
    "complexity_scan_map",
    "scan_silent_fallback_entries",
    "validate_startup_samples",
]
