from __future__ import annotations

import json
from typing import Any, Dict, NoReturn

from core.models.public_identifier_redaction import (
    is_forbidden_internal_key,
    redact_internal_text,
)
from core.shared.strict_json import load_strict_json


class _UnreadableDetail(Exception):
    """存储的详情不是严格 JSON（含重复键、非有限数字）：展示时照原文给出。"""


def _unreadable_detail() -> NoReturn:
    raise _UnreadableDetail


def _project_operation_log_value(value: Any) -> Any:
    if isinstance(value, dict):
        public: Dict[str, Any] = {}
        for key, child in value.items():
            if not is_forbidden_internal_key(key):
                public[key] = _project_operation_log_value(child)
        return public
    if isinstance(value, list):
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
        return load_strict_json(text, on_malformed=_unreadable_detail)
    except _UnreadableDetail:
        return text


def public_operation_log_detail_text(detail: Any) -> str:
    projected = _project_operation_log_value(_loads_detail(detail))
    if projected in (None, ""):
        return "-"
    if isinstance(projected, (dict, list)):
        return json.dumps(projected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(projected)


__all__ = [
    "public_operation_log_detail_text",
]
