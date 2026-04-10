from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import json
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, cast

from .quality_gate_ledger import entry_sort_key
from .quality_gate_shared import (
    _CLEANUP_KEYWORDS,
    _LOG_METHODS,
    _OBSERVABLE_TARGET_KEYWORDS,
    COMPLEXITY_THRESHOLD,
    FALLBACK_KIND_VALUES,
    FILE_SIZE_LIMIT,
    STARTUP_SAMPLE_EXPECTATIONS,
    UI_MODE_SCOPE_TAG_VALUES,
    UI_MODE_STARTUP_GUARD_SYMBOLS,
    QualityGateError,
    collect_startup_scope_files,
    read_text_file,
    slugify,
)


def _ast_tree_for_file(rel_path: str) -> ast.AST:
    source = read_text_file(rel_path)
    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as exc:
        raise QualityGateError(f"无法解析 {rel_path}：{exc}") from exc
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._ast_parent = node  # type: ignore[attr-defined]
    return tree


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
    if target in {"_log_warning", "fallback_log"}:
        return "log:warning"
    if tail in _LOG_METHODS and ("logger" in target or target.endswith(tuple(_LOG_METHODS))):
        return f"log:{tail}"
    if tail == "add" and (
        "collector" in target or "degradation" in target or any(kw.arg in {"code", "scope", "message"} for kw in node.keywords)
    ):
        return "collector:add"
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
            # 这里保留所有 return 的字面量类别，现有处理器指纹与治理台账已按该口径冻结。
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


def _fingerprint_for_signature(signature: Dict[str, Any]) -> str:
    raw = json.dumps(signature, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha1:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()


def ui_mode_scope_tag(symbol: str) -> str:
    if symbol in UI_MODE_STARTUP_GUARD_SYMBOLS:
        return "startup_guard"
    return "render_bridge"


def scan_silent_fallback_entries(paths: Sequence[str]) -> List[Dict[str, Any]]:
    entries = []
    for rel_path in sorted(set([str(path).replace("\\", "/") for path in paths])):
        tree = _ast_tree_for_file(rel_path)
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
            fingerprint = _fingerprint_for_signature(signature)
            entry = {
                "path": rel_path,
                "symbol": symbol,
                "handler_fingerprint": fingerprint,
                "except_ordinal": int(ordinal_map[symbol]),
                "line_start": int(getattr(handler, "lineno", 0) or 0),
                "line_end": int(getattr(handler, "end_lineno", getattr(handler, "lineno", 0) or 0) or 0),
                "legacy_swallow_hit": legacy_swallow_hit,
                "fallback_kind": fallback_kind,
                "signature": signature,
            }
            if rel_path == "web/ui_mode.py":
                entry["scope_tag"] = ui_mode_scope_tag(symbol)
            entries.append(entry)
    _assign_silent_entry_ids(entries)
    return sorted(entries, key=entry_sort_key)


def _assign_silent_entry_ids(entries: List[Dict[str, Any]]) -> None:
    base_counts = defaultdict(int)
    for entry in entries:
        fingerprint = str(entry.get("handler_fingerprint") or "")
        short_hash = fingerprint.split(":", 1)[-1][:12]
        base_id = "fallback:{}-{}-{}".format(
            slugify(entry.get("path")),
            slugify(entry.get("symbol") or "module"),
            short_hash,
        )
        base_counts[base_id] += 1
        if base_counts[base_id] == 1:
            entry["id"] = base_id
        else:
            entry["id"] = "{}-x{}".format(base_id, int(entry.get("except_ordinal") or base_counts[base_id]))


def validate_startup_samples(entries: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if entries is None:
        entries = scan_silent_fallback_entries(collect_startup_scope_files())
    entry_list = list(entries)
    errors = []
    matched_kinds = set()
    matched_scopes = set()
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
        if sample.scope_tag is not None and str(match.get("scope_tag")) != sample.scope_tag:
            errors.append(
                "样本 scope_tag 不匹配：{}:{} 期望 {}，实际 {}".format(sample.path, sample.symbol, sample.scope_tag, match.get("scope_tag"))
            )
        matched_kinds.add(str(match.get("fallback_kind")))
        if match.get("scope_tag"):
            matched_scopes.add(str(match.get("scope_tag")))
    missing_kinds = sorted(FALLBACK_KIND_VALUES - matched_kinds)
    if missing_kinds:
        errors.append("四类分类样本覆盖不完整：{}".format(", ".join(missing_kinds)))
    missing_scopes = sorted(UI_MODE_SCOPE_TAG_VALUES - matched_scopes)
    if missing_scopes:
        errors.append("web/ui_mode.py scope 样本覆盖不完整：{}".format(", ".join(missing_scopes)))
    if errors:
        raise QualityGateError("启动链样本点校验失败：\n" + "\n".join(errors))
    return {
        "sample_count": len(STARTUP_SAMPLE_EXPECTATIONS),
        "fallback_kinds": sorted(matched_kinds),
        "scope_tags": sorted(matched_scopes),
    }


def complexity_scan_map(paths: Sequence[str], include_all: bool = False) -> Dict[str, Dict[str, Any]]:
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
    for rel_path in sorted(set([str(path).replace("\\", "/") for path in paths])):
        source = read_text_file(rel_path)
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


def scan_complexity_entries(paths: Sequence[str]) -> List[Dict[str, Any]]:
    return [results for _, results in sorted(complexity_scan_map(paths).items())]


def scan_oversize_entries(paths: Sequence[str]) -> List[Dict[str, Any]]:
    entries = []
    for rel_path in sorted(set([str(path).replace("\\", "/") for path in paths])):
        line_count = len(read_text_file(rel_path).splitlines())
        if line_count > FILE_SIZE_LIMIT:
            entries.append({"path": rel_path, "current_value": line_count, "limit": FILE_SIZE_LIMIT})
    return entries


__all__ = [
    "classify_silent_fallback",
    "scan_complexity_entries",
    "scan_oversize_entries",
    "scan_silent_fallback_entries",
    "ui_mode_scope_tag",
    "validate_startup_samples",
    "complexity_scan_map",
]
