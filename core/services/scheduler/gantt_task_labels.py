from __future__ import annotations

from typing import Any, Mapping


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def detail_part_label(row: Mapping[str, Any]) -> str:
    part_no = _text(row.get("part_no"))
    part_name = _text(row.get("part_name"))
    piece_id = _text(row.get("piece_id"))
    label = " ".join(item for item in (part_no, part_name) if item).strip()
    return label or piece_id or "-"


def detail_operation_label(row: Mapping[str, Any]) -> str:
    seq = row.get("seq")
    op_type = _text(row.get("op_type_name"))
    if seq is not None and _text(seq) and op_type:
        return f"{seq}（{op_type}）"
    if op_type:
        return op_type
    return _text(seq) or "-"


def public_task_label(row: Mapping[str, Any]) -> str:
    op_code = _text(row.get("op_code"))
    if op_code:
        return op_code
    operation_label = detail_operation_label(row)
    if operation_label and operation_label != "-":
        return operation_label
    part_label = detail_part_label(row)
    if part_label and part_label != "-":
        return part_label
    batch_id = _text(row.get("batch_id"))
    if batch_id:
        return f"{batch_id} 工序"
    return "未命名工序"


__all__ = ["detail_operation_label", "detail_part_label", "public_task_label"]
