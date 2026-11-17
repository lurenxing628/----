from __future__ import annotations

import json
from typing import Any

from core.models.content import StoredJsonCorrupt, read_stored_json


def public_operation_log_detail_text(detail: Any) -> str:
    """Display text of one stored OperationLogs.detail: NULL, or ``canonical_json`` of an object (logging.py)."""
    if detail is None:
        return "-"
    # 日志页遇到坏详情也要能打开：存的不是严格 JSON 对象（含重复键、非有限数字）时照原文显示。
    try:
        value = read_stored_json(detail, dict)
    except StoredJsonCorrupt:
        return str(detail).strip() or "-"
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = [
    "public_operation_log_detail_text",
]
