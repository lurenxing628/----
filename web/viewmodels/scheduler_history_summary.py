from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from core.models.scheduler_history_parser import (
    ResultSummaryParseResult,
    parse_result_summary_payload,
)

from .scheduler_summary_display import build_summary_display_state

_PARSE_USER_MESSAGES = {
    "json_decode_error": "当前版本的排产摘要读取失败，页面仅展示基础历史信息。",
    "invalid_structure": "当前版本的排产摘要结构异常，页面仅展示基础历史信息。",
    "non_finite_number": "当前版本的排产摘要包含异常数字，页面仅展示基础历史信息。",
}

_STRATEGY_LABELS = {
    "priority_first": "优先级优先",
    "due_date_first": "交期优先",
    "weighted": "综合优先级和交期",
    "fifo": "先进先出",
    "improve": "优化排产",
    "greedy": "快速排产",
    "manual": "手动排产",
}

_VERSION_OPTION_STATUS_LABELS = {
    "success": "成功",
    "partial": "部分成功",
    "failed": "失败",
    "unknown": "有问题，需检查",
}

_MONTH_NAMES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


class ScheduleHistoryDisplayValueError(ValueError):
    """排产历史摘要里有无法安全展示的值。"""


def _strategy_display_state(value: Any) -> Dict[str, str]:
    raw = str(value or "").strip()
    if not raw:
        return {
            "label": "旧历史未记录",
            "state": "missing",
            "message": "这条历史没有记录排产方式，可能来自旧版本。",
        }
    if raw not in _STRATEGY_LABELS:
        return {
            "label": "历史记录异常",
            "state": "invalid",
            "message": "历史记录里的排产方式没有登记，页面不把它当成正常策略显示。",
        }
    return {
        "label": _STRATEGY_LABELS[raw],
        "state": "ok",
        "message": "",
    }


def strategy_display_label(value: Any) -> str:
    return _strategy_display_state(value)["label"]


def strict_strategy_display_label(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ScheduleHistoryDisplayValueError("排产历史缺少排产策略")
    if raw not in _STRATEGY_LABELS:
        raise ScheduleHistoryDisplayValueError(f"未知排产策略：{raw}")
    return _STRATEGY_LABELS[raw]


def _public_date_parts(year: Any, month: Any, day: Any) -> str:
    return f"{int(year)}年{int(month)}月{int(day)}日"


def _public_datetime_parts(year: Any, month: Any, day: Any, hour: Any, minute: Any) -> str:
    return f"{_public_date_parts(year, month, day)} {int(hour):02d}:{int(minute):02d}"


def _public_datetime_state(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int = 0,
    *,
    has_time: bool,
) -> Optional[Dict[str, int]]:
    try:
        if has_time:
            datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
        else:
            date(int(year), int(month), int(day))
    except ValueError:
        return None
    return {"year": int(year), "month": int(month), "day": int(day), "hour": int(hour), "minute": int(minute), "has_time": has_time}


def _valid_timezone_suffix(value: Optional[str]) -> bool:
    text = str(value or "").strip()
    if not text or text == "Z":
        return True
    compact = text.replace(":", "")
    if len(compact) != 5 or compact[0] not in ("+", "-") or not compact[1:].isdigit():
        return False
    return int(compact[1:3]) <= 23 and int(compact[3:5]) <= 59


def _parse_public_date_parts(value: Any) -> Optional[Dict[str, int]]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return {
            "year": value.year,
            "month": value.month,
            "day": value.day,
            "hour": value.hour,
            "minute": value.minute,
            "has_time": True,
        }
    if isinstance(value, date):
        return {
            "year": value.year,
            "month": value.month,
            "day": value.day,
            "hour": 0,
            "minute": 0,
            "has_time": False,
        }
    text = str(value or "").strip()
    if not text:
        return None
    import re

    iso = re.fullmatch(
        r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})"
        r"(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2})(?:\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?",
        text,
    )
    if iso:
        if not _valid_timezone_suffix(iso.group(7)):
            return None
        return _public_datetime_state(
            int(iso.group(1)),
            int(iso.group(2)),
            int(iso.group(3)),
            int(iso.group(4) or 0),
            int(iso.group(5) or 0),
            int(iso.group(6) or 0),
            has_time=bool(iso.group(4)),
        )
    rfc = re.fullmatch(
        r"(?:[A-Za-z]{3},\s*)?(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{1,2}))?(?:\s+[A-Za-z]{1,5})?",
        text,
    )
    if rfc:
        month = _MONTH_NAMES.get(rfc.group(2).lower())
        if month:
            return _public_datetime_state(
                int(rfc.group(3)),
                month,
                int(rfc.group(1)),
                int(rfc.group(4)),
                int(rfc.group(5)),
                int(rfc.group(6) or 0),
                has_time=True,
            )
    return None


def format_public_date(value: Any) -> str:
    parts = _parse_public_date_parts(value)
    if not parts:
        return "时间记录异常" if str(value or "").strip() else "-"
    return _public_date_parts(parts["year"], parts["month"], parts["day"])


def format_public_datetime(value: Any) -> str:
    parts = _parse_public_date_parts(value)
    if not parts:
        return "时间记录异常" if str(value or "").strip() else "-"
    return _public_datetime_parts(parts["year"], parts["month"], parts["day"], parts["hour"], parts["minute"])


def parse_state_from_result(result: ResultSummaryParseResult) -> Dict[str, Any]:
    user_message = _PARSE_USER_MESSAGES.get(result.reason) if result.parse_failed else None
    state = result.to_parse_state(user_message=user_message)
    state["raw_type"] = result.raw_type
    return state


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
        strategy_state = _strategy_display_state(row.get("strategy"))
        row["strategy_label"] = strategy_state["label"]
        row["strategy_display_state"] = strategy_state["state"]
        row["strategy_display_message"] = strategy_state["message"]
        row["schedule_time_display"] = format_public_datetime(row.get("schedule_time"))
        version_text = str(row.get("version") or "").strip()
        result_state = display_state.get("result_state") if isinstance(display_state, dict) else None
        outcome_status = str((result_state or {}).get("outcome_status") or "").strip()
        result_text = _VERSION_OPTION_STATUS_LABELS.get(outcome_status) or row["result_status_label"] or "-"
        row["version_option_label"] = f"v{version_text} · {result_text}" if version_text else result_text
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
    "format_public_date",
    "format_public_datetime",
    "parse_history_summary_state",
    "parse_state_from_result",
    "parsed_history_summary_payload",
    "ScheduleHistoryDisplayValueError",
    "strict_strategy_display_label",
    "strategy_display_label",
]
