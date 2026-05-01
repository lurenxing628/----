from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.models.scheduler_history_parser import (
    ResultSummaryParseResult,
    parse_result_summary_payload,
)

from .scheduler_summary_display import build_summary_display_state

_PARSE_USER_MESSAGES = {
    "json_decode_error": "当前版本的排产摘要解析失败，页面仅展示基础历史信息。",
    "invalid_structure": "当前版本的排产摘要结构异常，页面仅展示基础历史信息。",
}


def parse_state_from_result(result: ResultSummaryParseResult) -> Dict[str, Any]:
    user_message = _PARSE_USER_MESSAGES.get(result.reason) if result.parse_failed else None
    return result.to_parse_state(user_message=user_message)


def parse_history_summary_state(raw_summary: Any) -> Dict[str, Any]:
    return parse_state_from_result(parse_result_summary_payload(raw_summary))


def parsed_history_summary_payload(raw_summary: Any) -> Optional[Dict[str, Any]]:
    state = parse_history_summary_state(raw_summary)
    payload = state.get("payload")
    return payload if isinstance(payload, dict) else None


def decorate_history_version_options(versions: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for raw in list(versions or []):
        row = dict(raw or {})
        parse_state = parse_history_summary_state(row.get("result_summary"))
        summary_payload = parse_state.get("payload")
        display_state = build_summary_display_state(
            summary_payload if isinstance(summary_payload, dict) else None,
            result_status=row.get("result_status"),
            parse_state=parse_state,
        )
        row["result_status_label"] = str(display_state.get("result_status_label") or "")
        out.append(row)
    return out


def build_history_summary_display(
    *,
    raw_summary: Any,
    result_status: Any,
) -> Dict[str, Any]:
    parse_state = parse_history_summary_state(raw_summary)
    payload = parse_state.get("payload")
    return build_summary_display_state(
        payload if isinstance(payload, dict) else None,
        result_status=result_status,
        parse_state=parse_state,
    )


__all__ = [
    "build_history_summary_display",
    "decorate_history_version_options",
    "parse_history_summary_state",
    "parse_state_from_result",
    "parsed_history_summary_payload",
]
