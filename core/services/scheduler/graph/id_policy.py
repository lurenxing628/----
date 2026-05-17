from __future__ import annotations

import re
from typing import Any, Optional

OPERATION_NODE_PREFIX = "op:"
MACHINE_NODE_PREFIX = "machine:"
OPERATOR_NODE_PREFIX = "operator:"

_ROW_ID_TEXT_PATTERN = re.compile(r"^0*[1-9][0-9]*(?:\.0+)?$")


class GraphNodeIdError(ValueError):
    """Raised when graph node id construction receives unsafe business identifiers."""


def _display_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _require_text_component(value: Any, *, field_name: str) -> str:
    if isinstance(value, (bytes, bytearray)):
        raise GraphNodeIdError(f"{field_name} 不能是 bytes/bytearray，避免静默解码造成节点 ID 碰撞。")
    text = "" if value is None else str(value).strip()
    if not text:
        raise GraphNodeIdError(f"{field_name} 不能为空，无法生成稳定图节点 ID。")
    return text


def normalize_operation_row_id(row_id: Any) -> Optional[int]:
    """Return a positive integer operation row id, or None for unsafe/invalid values."""
    if row_id is None or isinstance(row_id, bool) or isinstance(row_id, (bytes, bytearray)):
        return None
    text = str(row_id).strip()
    if not text or not _ROW_ID_TEXT_PATTERN.fullmatch(text):
        return None
    try:
        normalized = int(float(text))
    except Exception:
        return None
    if normalized <= 0:
        return None
    return normalized


def make_operation_node_id(batch_id: Any, op_code: Any, row_id: Any = None) -> str:
    if isinstance(row_id, (bytes, bytearray)):
        raise GraphNodeIdError("row_id 不能是 bytes/bytearray。")

    normalized_row_id = normalize_operation_row_id(row_id)
    if normalized_row_id is not None:
        return f"{OPERATION_NODE_PREFIX}{normalized_row_id}"

    batch_text = _require_text_component(batch_id, field_name="batch_id")
    op_text = _require_text_component(op_code, field_name="op_code")
    return f"{OPERATION_NODE_PREFIX}{batch_text}:{op_text}"


def make_machine_node_id(machine_id: Any) -> str:
    return f"{MACHINE_NODE_PREFIX}{_require_text_component(machine_id, field_name='machine_id')}"


def make_operator_node_id(operator_id: Any) -> str:
    return f"{OPERATOR_NODE_PREFIX}{_require_text_component(operator_id, field_name='operator_id')}"


def display_id(node_id: Any) -> str:
    """Return a human-readable id for diagnostics; intentionally tolerant."""
    text = _display_text(node_id)
    if text.startswith(OPERATION_NODE_PREFIX):
        return text[len(OPERATION_NODE_PREFIX) :]
    if text.startswith(MACHINE_NODE_PREFIX):
        return text[len(MACHINE_NODE_PREFIX) :]
    if text.startswith(OPERATOR_NODE_PREFIX):
        return text[len(OPERATOR_NODE_PREFIX) :]
    return text


__all__ = [
    "GraphNodeIdError",
    "MACHINE_NODE_PREFIX",
    "OPERATION_NODE_PREFIX",
    "OPERATOR_NODE_PREFIX",
    "display_id",
    "make_machine_node_id",
    "make_operation_node_id",
    "make_operator_node_id",
    "normalize_operation_row_id",
]
