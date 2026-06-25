from __future__ import annotations

from typing import Any, Dict, List

_DISPATCH_DETAIL_CODES = {
    "dispatch_operation_failed",
    "dispatch_operation_exception",
    "graph_blocked_after_failure",
    "missing_batch",
    "skipped_after_batch_failure",
}


def dispatch_error_summary(result_summary_obj: Dict[str, Any]) -> Dict[str, Any]:
    details = result_summary_obj.get("public_error_details") if isinstance(result_summary_obj, dict) else None
    if not isinstance(details, list):
        return {}
    total_count = _positive_int(result_summary_obj.get("failure_detail_count"))
    codes: Dict[str, int] = {}
    messages: List[str] = []
    for item in details:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        if code not in _DISPATCH_DETAIL_CODES:
            continue
        codes[code] = int(codes.get(code) or 0) + 1
        message = str(item.get("message") or "").strip()
        if message and message not in messages and len(messages) < 5:
            messages.append(message)
    if not codes:
        return {}
    return {"count": total_count or sum(codes.values()), "codes": codes, "messages_sample": messages}


def _positive_int(value: Any) -> int:
    try:
        number = int(value or 0)
    except Exception:
        return 0
    return number if number > 0 else 0


__all__ = ["dispatch_error_summary"]
