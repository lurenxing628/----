from __future__ import annotations

import ast
import difflib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from tools.long_gate_schema import stable_json_hash


@dataclass(frozen=True)
class TestFunctionSpan:
    qualname: str
    nodeid_prefix: str
    node_start: int
    node_end: int
    body_start: int
    body_end: int
    body_hash: str


@dataclass(frozen=True)
class TestFileBodyShape:
    outside_body_hash: str
    spans_by_prefix: Mapping[str, TestFunctionSpan]


def _source_lines(source: str) -> List[str]:
    return str(source or "").splitlines()


def _node_end(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno", None) or getattr(node, "lineno", 0) or 0)


def _line_hash(lines: Sequence[str]) -> str:
    return stable_json_hash([str(line) for line in list(lines or [])])


def _body_range(node: ast.AST) -> Optional[Tuple[int, int]]:
    body = getattr(node, "body", None)
    if not isinstance(body, list) or not body:
        return None
    first = body[0]
    last = body[-1]
    start = int(getattr(first, "lineno", 0) or 0)
    end = _node_end(last)
    node_start = int(getattr(node, "lineno", 0) or 0)
    if start <= node_start or end < start:
        return None
    return start, end


def _span_for_function(path: str, qualname: str, node: ast.AST, lines: Sequence[str]) -> Optional[TestFunctionSpan]:
    body_range = _body_range(node)
    if body_range is None:
        return None
    body_start, body_end = body_range
    return TestFunctionSpan(
        qualname=qualname,
        nodeid_prefix=f"{path}::{qualname}",
        node_start=int(getattr(node, "lineno", 0) or 0),
        node_end=_node_end(node),
        body_start=body_start,
        body_end=body_end,
        body_hash=_line_hash(lines[body_start - 1 : body_end]),
    )


def _iter_test_function_spans(path: str, tree: ast.Module, lines: Sequence[str]) -> Iterable[TestFunctionSpan]:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            span = _span_for_function(path, node.name, node, lines)
            if span is not None:
                yield span
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                    span = _span_for_function(path, f"{node.name}::{child.name}", child, lines)
                    if span is not None:
                        yield span


def _outside_body_hash(lines: Sequence[str], spans: Sequence[TestFunctionSpan]) -> str:
    chunks: List[str] = []
    cursor = 1
    for span in sorted(spans, key=lambda item: item.body_start):
        chunks.extend(str(line) for line in lines[cursor - 1 : span.body_start - 1])
        chunks.append(f"<test-body:{span.nodeid_prefix}>")
        cursor = span.body_end + 1
    chunks.extend(str(line) for line in lines[cursor - 1 :])
    return _line_hash(chunks)


def _shape_for_source(path: str, source: str) -> Tuple[Optional[TestFileBodyShape], str]:
    try:
        tree = ast.parse(str(source or ""), filename=path)
    except SyntaxError as exc:
        return None, f"test file cannot be parsed safely: {path}: {exc}"
    lines = _source_lines(source)
    spans = list(_iter_test_function_spans(path, tree, lines))
    if not spans:
        return None, f"test file has no supported multi-line test functions: {path}"
    spans_by_prefix = {span.nodeid_prefix: span for span in spans}
    if len(spans_by_prefix) != len(spans):
        return None, f"test function nodeid prefix is ambiguous: {path}"
    return TestFileBodyShape(
        outside_body_hash=_outside_body_hash(lines, spans),
        spans_by_prefix=spans_by_prefix,
    ), ""


def _changed_lines(old_source: str, new_source: str) -> Tuple[Set[int], Set[int]]:
    old_lines = _source_lines(old_source)
    new_lines = _source_lines(new_source)
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    old_changed: Set[int] = set()
    new_changed: Set[int] = set()
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        old_changed.update(range(old_start + 1, old_end + 1))
        new_changed.update(range(new_start + 1, new_end + 1))
    return old_changed, new_changed


def _lines_inside_selected_spans(lines: Set[int], spans: Sequence[TestFunctionSpan]) -> bool:
    for line in lines:
        if not any(span.body_start <= line <= span.body_end for span in spans):
            return False
    return True


def _line_range(node: ast.AST) -> Set[int]:
    start = int(getattr(node, "lineno", 0) or 0)
    end = _node_end(node)
    return set(range(start, end + 1)) if start and end >= start else set()


def _literal_expr_is_safe(node: ast.AST, local_names: Set[str]) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.Name):
        return str(node.id) in local_names
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_literal_expr_is_safe(item, local_names) for item in node.elts)
    if isinstance(node, ast.Dict):
        keys = [item for item in node.keys if item is not None]
        return all(_literal_expr_is_safe(item, local_names) for item in keys + list(node.values))
    if isinstance(node, ast.UnaryOp):
        return _literal_expr_is_safe(node.operand, local_names)
    if isinstance(node, ast.BinOp):
        return _literal_expr_is_safe(node.left, local_names) and _literal_expr_is_safe(node.right, local_names)
    return False


def _statement_is_precise_safe(statement: ast.stmt, local_names: Set[str]) -> Tuple[bool, str]:
    if isinstance(statement, ast.Pass):
        return True, ""
    if isinstance(statement, ast.Assign):
        if any(not isinstance(target, ast.Name) for target in statement.targets):
            return False, "changed test body contains unsafe statement: Assign"
        if not _literal_expr_is_safe(statement.value, local_names):
            return False, "changed test body contains unsafe expression: Assign"
        local_names.update(str(target.id) for target in statement.targets if isinstance(target, ast.Name))
        return True, ""
    if isinstance(statement, ast.AnnAssign):
        if not isinstance(statement.target, ast.Name):
            return False, "changed test body contains unsafe statement: AnnAssign"
        if statement.value is not None and not _literal_expr_is_safe(statement.value, local_names):
            return False, "changed test body contains unsafe expression: AnnAssign"
        local_names.add(str(statement.target.id))
        return True, ""
    if isinstance(statement, ast.Assert):
        if not _literal_expr_is_safe(statement.test, local_names):
            return False, "changed test body contains unsafe expression: Assert"
        if statement.msg is not None and not _literal_expr_is_safe(statement.msg, local_names):
            return False, "changed test body contains unsafe expression: Assert"
        return True, ""
    return False, f"changed test body contains unsafe statement: {type(statement).__name__}"


def _changed_body_is_safe(source: str, path: str, changed_lines: Set[int], selected_prefixes: Sequence[str]) -> str:
    try:
        tree = ast.parse(str(source or ""), filename=path)
    except SyntaxError as exc:
        return f"test file cannot be parsed safely: {path}: {exc}"
    selected_qualnames = {str(prefix).split("::", 1)[1] for prefix in selected_prefixes if "::" in str(prefix)}
    selected_nodes: Set[ast.AST] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in selected_qualnames:
            selected_nodes.add(node)
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualname = f"{node.name}::{child.name}"
                    if qualname in selected_qualnames:
                        selected_nodes.add(child)
    for selected in selected_nodes:
        body = getattr(selected, "body", None)
        if not isinstance(body, list):
            continue
        local_names: Set[str] = set()
        for statement in body:
            safe, reason = _statement_is_precise_safe(statement, local_names)
            if not safe:
                return reason
    return ""


def _selected_function_referenced_elsewhere(source: str, path: str, selected_prefixes: Sequence[str]) -> str:
    try:
        tree = ast.parse(str(source or ""), filename=path)
    except SyntaxError as exc:
        return f"test file cannot be parsed safely: {path}: {exc}"
    selected_qualnames = {str(prefix).split("::", 1)[1] for prefix in selected_prefixes if "::" in str(prefix)}
    selected_names = {name.rsplit("::", 1)[-1] for name in selected_qualnames}
    selected_nodes: Set[ast.AST] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in selected_qualnames:
            selected_nodes.add(node)
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualname = f"{node.name}::{child.name}"
                    if qualname in selected_qualnames:
                        selected_nodes.add(child)
    inside_selected: Set[ast.AST] = set()
    for selected in selected_nodes:
        inside_selected.update(ast.walk(selected))
    for node in ast.walk(tree):
        if node in inside_selected:
            continue
        if isinstance(node, ast.Name) and node.id in selected_names:
            return "changed test function is referenced by another test body"
        if isinstance(node, ast.Attribute) and node.attr in selected_names:
            return "changed test function is referenced by another test body"
    return ""


def _nodeids_for_prefix(prefix: str, nodeids: Sequence[str]) -> List[str]:
    exact = str(prefix)
    parameterized = exact + "["
    return [str(nodeid) for nodeid in list(nodeids or []) if str(nodeid) == exact or str(nodeid).startswith(parameterized)]


def select_precise_body_nodeids(
    *,
    path: str,
    old_source: str,
    new_source: str,
    nodeids: Sequence[str],
) -> Tuple[Optional[Dict[str, Any]], str]:
    old_shape, old_error = _shape_for_source(path, old_source)
    if old_error or old_shape is None:
        return None, old_error
    new_shape, new_error = _shape_for_source(path, new_source)
    if new_error or new_shape is None:
        return None, new_error
    old_prefixes = set(old_shape.spans_by_prefix)
    new_prefixes = set(new_shape.spans_by_prefix)
    if old_prefixes != new_prefixes:
        return None, f"test function set changed: {path}"
    if old_shape.outside_body_hash != new_shape.outside_body_hash:
        return None, f"test file changed outside test function bodies: {path}"

    changed_prefixes = [
        prefix
        for prefix in sorted(new_prefixes)
        if old_shape.spans_by_prefix[prefix].body_hash != new_shape.spans_by_prefix[prefix].body_hash
    ]
    if not changed_prefixes:
        return None, f"test file changed without supported test body changes: {path}"

    old_changed, new_changed = _changed_lines(old_source, new_source)
    old_spans = [old_shape.spans_by_prefix[prefix] for prefix in changed_prefixes]
    new_spans = [new_shape.spans_by_prefix[prefix] for prefix in changed_prefixes]
    if not _lines_inside_selected_spans(old_changed, old_spans) or not _lines_inside_selected_spans(new_changed, new_spans):
        return None, f"changed lines are not limited to changed test bodies: {path}"
    unsafe_reason = _changed_body_is_safe(
        old_source,
        path,
        old_changed,
        changed_prefixes,
    ) or _changed_body_is_safe(new_source, path, new_changed, changed_prefixes)
    if unsafe_reason:
        return None, unsafe_reason
    reference_reason = _selected_function_referenced_elsewhere(new_source, path, changed_prefixes)
    if reference_reason:
        return None, reference_reason

    selected: List[str] = []
    for prefix in changed_prefixes:
        matched = _nodeids_for_prefix(prefix, nodeids)
        if not matched:
            return None, f"changed test function has no collected nodeid: {prefix}"
        selected.extend(matched)
    selected = list(dict.fromkeys(selected))
    return {
        "selection_scope": "test_function_body",
        "safe_scope_kind": "test_function_body_incremental",
        "merge_policy": "replace_reports_for_selected_nodeids",
        "changed_nodeid_prefixes": changed_prefixes,
        "changed_functions": [
            {"path": path, "qualname": prefix.split("::", 1)[1], "nodeid_prefix": prefix}
            for prefix in changed_prefixes
        ],
        "selected_nodeids": selected,
        "selected_nodeid_count": len(selected),
        "selected_nodeids_hash": stable_json_hash(selected),
        "selected_nodeids_sample": selected[:10],
        "scope_basis": [
            "test file outside-body hash matched",
            "changed lines are limited to existing test function bodies",
            "selected nodeids came from collect_nodeids mapping",
        ],
    }, ""
