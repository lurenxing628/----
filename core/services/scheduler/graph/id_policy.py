"""Scheduler graph node ID policy helpers.

This module is pure Python and must not import NetworkX.
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Optional

OPERATION_NODE_PREFIX = "op:"
MACHINE_NODE_PREFIX = "machine:"
OPERATOR_NODE_PREFIX = "operator:"


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="ignore")
    return str(value).strip()


def normalize_operation_row_id(row_id: Any) -> Optional[str]:
    """Return canonical positive operation row id text, or None when invalid.

    Row ids represent BatchOperations.id. They must be positive integer-like
    values. bool is rejected explicitly because bool is a subclass of int.
    """
    if row_id is None or isinstance(row_id, bool):
        return None

    if isinstance(row_id, int):
        return str(row_id) if row_id > 0 else None

    if isinstance(row_id, float):
        if math.isfinite(row_id) and row_id.is_integer() and row_id > 0:
            return str(int(row_id))
        return None

    text = _clean_text(row_id)
    if text == "":
        return None

    try:
        value = Decimal(text)
    except Exception:
        return None

    if not value.is_finite() or value <= 0:
        return None
    if value != value.to_integral_value():
        return None

    return str(int(value))


def make_operation_node_id(batch_id: Any, op_code: Any, row_id: Any = None) -> str:
    """Generate stable operation graph node id.

    Prefer a valid positive BatchOperations.id. If row_id is absent or invalid,
    fall back to batch_id + op_code for pre-persistence or synthetic test data.
    """
    normalized_row_id = normalize_operation_row_id(row_id)
    if normalized_row_id is not None:
        return f"{OPERATION_NODE_PREFIX}{normalized_row_id}"

    return f"{OPERATION_NODE_PREFIX}{_clean_text(batch_id)}:{_clean_text(op_code)}"


def make_machine_node_id(machine_id: Any) -> str:
    return f"{MACHINE_NODE_PREFIX}{_clean_text(machine_id)}"


def make_operator_node_id(operator_id: Any) -> str:
    return f"{OPERATOR_NODE_PREFIX}{_clean_text(operator_id)}"


def display_id(node_id: Any) -> str:
    """Strip known graph node prefixes for human-readable diagnostics."""
    text = _clean_text(node_id)
    for prefix in (OPERATION_NODE_PREFIX, MACHINE_NODE_PREFIX, OPERATOR_NODE_PREFIX):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text
