from __future__ import annotations

import hashlib
from typing import Any, List, Optional

from .resource_dispatch_actual_records import TaskPlan, datetime_text, ordered_pauses, text


def idempotency_key(import_token: Optional[str], task_code: str, action: str, row_number: int) -> str:
    base = import_token or "manual"
    raw = f"resource-dispatch-actual:{base}:{task_code}:{action}:{row_number}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"resource-dispatch-actual-{digest}"


def manual_plan_token(plan: TaskPlan) -> str:
    parts: List[str] = [
        plan.task.task_code,
        _token_time("start", plan.actual_start_time),
        _token_time("finish", plan.actual_finish_time),
        f"done:{text(plan.quantity_done)}",
        f"scrapped:{text(plan.quantity_scrapped)}",
        _token_time("exception", plan.exception_time),
        f"exception_reason:{text(plan.exception_reason_code)}",
        f"exception_severity:{text(plan.exception_severity)}",
        f"exception_remark:{text(plan.exception_remark)}",
        f"remark:{text(plan.remark)}",
    ]
    for index, pause in enumerate(ordered_pauses(plan)):
        parts.extend(
            [
                f"pause:{index}",
                _token_time("pause_start", pause.start_time),
                _token_time("pause_end", pause.end_time),
                f"pause_reason:{text(pause.reason_code)}",
                f"pause_remark:{text(pause.remark)}",
            ]
        )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"manual-{digest}"


def _token_time(label: str, value: Any) -> str:
    if not text(value):
        return f"{label}:"
    return f"{label}:{datetime_text(value, field_label=label)}"
