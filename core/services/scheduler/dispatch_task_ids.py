from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

_TASK_ID_READABLE_RE = re.compile(r"[^0-9A-Za-z_-]+")


def _text(value: Any) -> str:
    return str(value or "").strip()


def row_identity(row: Mapping[str, Any]) -> str:
    schedule_id = row.get("schedule_id")
    if schedule_id is not None:
        return f"schedule:{schedule_id}"
    op_id = row.get("op_id")
    if op_id is not None:
        return ":".join(
            (
                "op",
                _text(op_id),
                _text(row.get("start_time")),
                _text(row.get("end_time")),
                _text(row.get("machine_id")),
                _text(row.get("operator_id")),
            )
        )
    parts = [
        _text(row.get("op_code")),
        _text(row.get("batch_id")),
        _text(row.get("piece_id")),
        _text(row.get("seq")),
        _text(row.get("start_time")),
        _text(row.get("end_time")),
        _text(row.get("machine_id")),
        _text(row.get("operator_id")),
    ]
    return "public:" + "|".join(parts)


def _task_hash_identity(normalized: Mapping[str, Any]) -> str:
    return _text(normalized.get("_row_identity")) or row_identity(normalized)


def _safe_task_id_readable_part(parts: Sequence[str]) -> str:
    readable = next((part for part in parts[:4] if part), "task")
    safe = _TASK_ID_READABLE_RE.sub("_", readable).strip("_")
    return safe or "task"


def _resource_identity_parts(normalized: Mapping[str, Any]) -> Sequence[str]:
    machine_id = _text(normalized.get("machine_id"))
    operator_id = _text(normalized.get("operator_id"))
    if machine_id or operator_id:
        return (machine_id, operator_id)
    current_id = _text(normalized.get("current_resource_id"))
    counterpart_id = _text(normalized.get("counterpart_resource_id"))
    if current_id and counterpart_id:
        return tuple(sorted((current_id, counterpart_id)))
    return (current_id, counterpart_id)


def public_task_id(normalized: Mapping[str, Any]) -> str:
    parts = [
        _text(normalized.get("op_code")),
        _text(normalized.get("batch_id")),
        _text(normalized.get("piece_id")),
        _text(normalized.get("seq")),
        _text(normalized.get("start_time")),
        _text(normalized.get("end_time")),
    ]
    parts.extend(_resource_identity_parts(normalized))
    digest = hashlib.sha1("|".join([_task_hash_identity(normalized)] + parts).encode("utf-8")).hexdigest()[:12]
    return f"task_{_safe_task_id_readable_part(parts)}_{digest}"
