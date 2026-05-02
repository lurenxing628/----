from __future__ import annotations

from core.infrastructure.errors import AppError, ErrorCode
from web.error_boundary import user_visible_app_error_message

_DIRECT_SCHEDULER_VALIDATION_FIELDS = {
    "batch_ids",
    "end_date",
    "start_dt",
    "批次",
    "排产",
    "齐套",
}


def scheduler_user_visible_app_error_message(exc: AppError) -> str:
    details = exc.details if isinstance(exc.details, dict) else {}
    if exc.code == ErrorCode.VALIDATION_ERROR:
        user_message = str(details.get("user_message") or "").strip()
        if user_message:
            return user_message
        reason = str(details.get("reason") or "").strip()
        if reason == "no_actionable_schedule_rows":
            return user_visible_app_error_message(exc)
        field = str(details.get("field") or getattr(exc, "field", "") or "").strip()
        if field in _DIRECT_SCHEDULER_VALIDATION_FIELDS and str(exc.message or "").strip():
            return str(exc.message).strip()
    return user_visible_app_error_message(exc)
