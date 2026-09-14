"""Input and diagnostic contracts for a read-only route preview."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from core.models.workbench_command import WorkbenchCommandRejected

MAX_ROUTE_OPERATIONS = 2000
MAX_ROUTE_TEXT_BYTES = 256 * 1024
# PartOperations.seq is persisted as an SQLite INTEGER.
MAX_ROUTE_SEQUENCE = (1 << 63) - 1


def route_diagnostic(code, message, *, severity="error", sequence=None):
    result = {"code": code, "severity": severity, "message": message}
    if sequence is not None:
        result["sequence"] = sequence
    return result


def check_route_capacity(count):
    if count > MAX_ROUTE_OPERATIONS:
        raise WorkbenchCommandRejected("route_too_large", "工艺路线最多允许2000道输入，未截断。", 413)


def check_route_text(text):
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError:
        raise WorkbenchCommandRejected("invalid_input", "路线文字包含无效Unicode字符。", 422) from None
    if size > MAX_ROUTE_TEXT_BYTES:
        raise WorkbenchCommandRejected("route_too_large", "路线文字不能超过256 KiB（UTF-8），未截断。", 413)


def route_sequence(value):
    if type(value) is str:
        digits = value.lstrip("0") or "0"
        if not digits.isdecimal() or len(digits) > 19:
            return None
        value = int(digits)
    return value if type(value) is int and 1 <= value <= MAX_ROUTE_SEQUENCE else None


def append_duplicate_diagnostics(sequences, diagnostics):
    for seq, count in sorted(Counter(sequences).items()):
        if count > 1:
            diagnostics.append(route_diagnostic("duplicate_sequence", f"工序号{seq}重复出现，未自动合并或丢弃。", sequence=seq))


@dataclass
class ProcessRoutePreviewInput:
    mode: str
    route_raw: str
    rows: List[Tuple[int, str]]
    diagnostics: List[Dict[str, Any]]


def _object(value, keys):
    if type(value) is not dict or set(value) != keys:
        raise WorkbenchCommandRejected("invalid_input", "预检内容缺少必填项或含有多余项，请刷新页面后重试。", 400)


def _row_input(rows):
    if type(rows) is not list:
        raise WorkbenchCommandRejected("invalid_input", "工艺内容必须逐行提交。", 422)
    check_route_capacity(len(rows))
    operations, diagnostics, raw_lines, sequences = [], [], [], []
    for index, row in enumerate(rows, 1):
        _object(row, {"seq", "op_type_name"})
        seq, name = row["seq"], row["op_type_name"]
        if type(seq) is not int or type(name) is not str:
            raise WorkbenchCommandRejected("invalid_input", "序号必须是整数且不能是bool，工种名称必须是文字。", 422)
        # Check magnitude before formatting potentially enormous Python integers.
        if route_sequence(seq) is None:
            diagnostics.append(route_diagnostic("invalid_sequence", f"第 {index} 行的工序号必须是正整数，而且不能过大。"))
            raw_lines.append("[invalid sequence] " + name)
            continue
        raw_lines.append(str(seq) + name)
        sequences.append(seq)
        if not name.strip():
            diagnostics.append(route_diagnostic("missing_operation_name", f"工序{seq}缺少工种名称。", sequence=seq))
            continue
        operations.append((seq, name.strip()))
    raw = "\n".join(raw_lines)
    check_route_text(raw)
    append_duplicate_diagnostics(sequences, diagnostics)
    return ProcessRoutePreviewInput("rows", raw, operations, diagnostics)


def normalize_route_preview_input(body):
    if type(body) is not dict or type(body.get("mode")) is not str or body["mode"] not in ("text", "rows"):
        raise WorkbenchCommandRejected("invalid_input", "预检mode必须是text或rows。", 400)
    mode = body["mode"]
    _object(body, {"mode", "route_raw"} if mode == "text" else {"mode", "rows"})
    if mode == "rows":
        return _row_input(body["rows"])
    if type(body["route_raw"]) is not str:
        raise WorkbenchCommandRejected("invalid_input", "route_raw必须是文字。", 422)
    check_route_text(body["route_raw"])
    return ProcessRoutePreviewInput(mode, body["route_raw"], [], [])
