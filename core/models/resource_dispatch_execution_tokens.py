from __future__ import annotations

import hashlib
from typing import Any, Mapping

from core.models.operation_execution_scope import parse_positive_execution_int


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int_text(value: Any, field_name: str) -> str:
    try:
        parsed = parse_positive_execution_int(value, field_name)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be positive") from exc
    return str(parsed)


def _required_text(value: Any, field_name: str) -> str:
    text = _text(value)
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def execution_task_key(row: Mapping[str, Any]) -> str:
    raw = "|".join(
        (
            "resource-dispatch-execution-task",
            _positive_int_text(row.get("schedule_id"), "schedule_id"),
            _positive_int_text(row.get("op_id"), "op_id"),
            _required_text(row.get("batch_id"), "batch_id"),
        )
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"exec_{digest}"


def execution_state_key(*, task_key: Any, state_revision: Any) -> str:
    task_text = _text(task_key)
    revision_text = _text(state_revision)
    if not task_text:
        raise ValueError("task_key is required")
    if not revision_text:
        raise ValueError("state_revision is required")
    raw = f"resource-dispatch-execution-state|{task_text}|{revision_text}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"state_{digest}"


__all__ = ["execution_state_key", "execution_task_key"]
