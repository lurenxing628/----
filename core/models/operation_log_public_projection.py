from __future__ import annotations

import json
from typing import Any, Dict

from core.models.public_identifier_redaction import (
    REDACTED_INTERNAL_TEXT,
    is_forbidden_internal_key,
    redact_internal_text,
)


def _project_operation_log_value(value: Any) -> Any:
    if isinstance(value, dict):
        public: Dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key or "").strip()
            if not is_forbidden_internal_key(key_text):
                public[key_text] = _project_operation_log_value(child)
        return public
    if isinstance(value, (list, tuple)):
        return [_project_operation_log_value(item) for item in value]
    if isinstance(value, str):
        return redact_internal_text(value)
    return value


def _loads_detail(detail: Any) -> Any:
    if not isinstance(detail, str):
        return detail
    text = detail.strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def public_operation_log_detail_text(detail: Any) -> str:
    projected = _project_operation_log_value(_loads_detail(detail))
    if projected in (None, ""):
        return "-"
    if isinstance(projected, (dict, list)):
        return json.dumps(projected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(projected)


def public_operation_log_error_message(message: Any) -> str:
    if isinstance(message, (int, float)) and not isinstance(message, bool):
        return REDACTED_INTERNAL_TEXT
    return redact_internal_text(message)


def public_operation_log_target_id_text(target_id: Any) -> str:
    if target_id is None:
        return "-"
    text = str(target_id or "").strip()
    if not text:
        return "-"
    return REDACTED_INTERNAL_TEXT


__all__ = [
    "public_operation_log_detail_text",
    "public_operation_log_error_message",
    "public_operation_log_target_id_text",
]
