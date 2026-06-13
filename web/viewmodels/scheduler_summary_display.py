from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.models.scheduler_degradation_messages import (
    is_public_freeze_degradation_message,
    public_degradation_event_message,
    public_summary_merge_error_code,
    public_summary_warning_messages,
)
from core.models.scheduler_public_errors import (
    GENERIC_PUBLIC_ERROR_MESSAGE,
    legacy_public_error_message,
    public_error_message_from_detail,
    public_safe_identifier,
    public_safe_label,
)

from .scheduler_degradation_presenter import (
    build_primary_degradation,
    build_summary_degradation_messages,
    degradation_display_key,
    degradation_reason_key,
    format_degradation_detail,
)
from .scheduler_summary_result_state import (
    build_result_state,
    counts_from_summary,
    derive_completion_status,
    result_status_display_label,
)

_GENERIC_ERROR_MESSAGE = GENERIC_PUBLIC_ERROR_MESSAGE


def _normalize_text_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        raw_items = [value]

    out: List[str] = []
    seen = set()
    for item in raw_items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _public_error_messages(value: Any) -> List[str]:
    raw_errors = _normalize_text_list(value)
    if not raw_errors:
        return []
    out: List[str] = []
    for item in raw_errors:
        public_message = legacy_public_error_message(item)
        message = public_message if public_message else _GENERIC_ERROR_MESSAGE
        if message not in out:
            out.append(message)
    return out


def _public_error_messages_from_details(value: Any) -> List[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: List[str] = []
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        message = public_error_message_from_detail(item)
        if not message or message in seen:
            continue
        seen.add(message)
        out.append(message)
    return out


def _summary_error_messages(summary: Dict[str, Any]) -> List[str]:
    detail_messages = _public_error_messages_from_details(summary.get("public_error_details"))
    if detail_messages:
        return detail_messages

    raw_errors = summary.get("errors")
    if not raw_errors:
        raw_errors = summary.get("errors_sample")
    return _public_error_messages(raw_errors)


def _safe_positive_int(value: Any) -> Optional[int]:
    try:
        number = int(value or 0)
    except Exception:
        return None
    return number if number > 0 else None


def _non_negative_count_state(value: Any, *, fallback: int) -> Tuple[int, bool]:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return int(max(0, fallback)), False
    if isinstance(value, bool):
        return int(max(0, fallback)), True
    try:
        if isinstance(value, int):
            parsed = value
        else:
            text = str(value).strip()
            sign = text[0] if text and text[0] in ("+", "-") else ""
            digits = text[1:] if sign else text
            if not digits.isdigit():
                return int(max(0, fallback)), True
            parsed = int(text)
    except (TypeError, ValueError, OverflowError):
        return int(max(0, fallback)), True
    if parsed < 0:
        return int(max(0, fallback)), True
    return max(int(parsed), int(max(0, fallback))), False


def _normalize_missing_resource_fields(value: Any) -> List[str]:
    fields = _normalize_text_list(value)
    return [item for item in fields if item in {"设备", "人员"}]


def _missing_resource_label(item: Dict[str, Any]) -> str:
    seq = _safe_positive_int(item.get("seq"))
    label_parts = [
        public_safe_identifier(item.get("batch_id")),
        f"工序{seq}" if seq is not None else "",
        public_safe_label(item.get("op_type_name")) or public_safe_identifier(item.get("op_code")),
    ]
    label = " / ".join([part for part in label_parts if part])
    return label or "未标明工序"


def _missing_resource_display_items(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []

    out: List[Dict[str, Any]] = []
    seen = set()
    for raw_item in value:
        if not isinstance(raw_item, dict):
            continue
        fields = _normalize_missing_resource_fields(raw_item.get("missing_fields"))
        missing_text = "、".join(fields) if fields else "设备/人员"
        batch_id = public_safe_identifier(raw_item.get("batch_id"))
        op_id = _safe_positive_int(raw_item.get("op_id"))
        seq = _safe_positive_int(raw_item.get("seq"))
        op_code = public_safe_identifier(raw_item.get("op_code"))
        op_type_name = public_safe_label(raw_item.get("op_type_name"))
        dedupe_key = (op_id, batch_id, seq, op_code, op_type_name, tuple(fields))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        display_item = {
            "op_id": op_id,
            "batch_id": batch_id,
            "seq": seq,
            "op_code": op_code,
            "op_type_name": op_type_name,
            "missing_fields": fields,
        }
        out.append(
            {
                "op_id": op_id,
                "batch_id": batch_id,
                "seq": seq,
                "op_code": op_code,
                "op_type_name": op_type_name,
                "missing_fields": fields,
                "missing_text": missing_text,
                "label": _missing_resource_label(display_item),
            }
        )
    return out


def _secondary_display_label(item: Dict[str, Any]) -> str:
    return format_degradation_detail(
        item.get("label"),
        item.get("count"),
        count_parse_failed=bool(item.get("count_parse_failed")),
    )


def _primary_detail_keys(primary_degradation: Optional[Dict[str, Any]]) -> Set[Tuple[str, str, int]]:
    raw_keys = (primary_degradation or {}).get("detail_keys") if isinstance(primary_degradation, dict) else None
    if not isinstance(raw_keys, list):
        return set()
    normalized: Set[Tuple[str, str, int]] = set()
    for item in raw_keys:
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            continue
        code, label, count = item
        normalized.add((str(code or "").strip(), str(label or "").strip(), int(count or 0)))
    return normalized


def _safe_freeze_secondary_message(item: Dict[str, Any], message: str) -> bool:
    if str(item.get("code") or "").strip() != "freeze_window_degraded":
        return False
    if not is_public_freeze_degradation_message(message):
        return False
    if message == public_degradation_event_message(item.get("code")):
        return False
    return True


def _normalize_secondary_display_item(
    item: object,
    *,
    primary_detail_keys: Set[Tuple[str, str, int]],
    detail_texts: Set[str],
) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None

    label = str(item.get("label") or "").strip()
    message = str(item.get("message") or "").strip()
    display_label = _secondary_display_label(item)
    reason_key = degradation_reason_key(code=item.get("code"), label=label, count=item.get("count"))
    item_display_key = degradation_display_key(
        code=item.get("code"),
        label=label,
        count=item.get("count"),
        message=message,
    )

    hidden_by_primary = bool(reason_key in primary_detail_keys or display_label in detail_texts or label in detail_texts)
    if hidden_by_primary:
        display_label = ""
        if not _safe_freeze_secondary_message(item, message):
            message = ""
    if message in detail_texts or (not display_label and message == label):
        message = ""
    if not display_label and message:
        display_label = message
        message = ""
    if not display_label and not message:
        return None

    display_item = dict(item)
    display_item["label"] = display_label
    display_item["message"] = message
    display_item["_display_key"] = item_display_key
    return display_item


def build_display_secondary_degradation_messages(
    primary_degradation: Optional[Dict[str, Any]],
    secondary_degradation_messages: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    detail_texts = set(
        _normalize_text_list((primary_degradation or {}).get("details") if isinstance(primary_degradation, dict) else None)
    )
    detail_keys = _primary_detail_keys(primary_degradation)

    filtered: List[Dict[str, Any]] = []
    seen = set()
    for item in list(secondary_degradation_messages or []):
        display_item = _normalize_secondary_display_item(
            item,
            primary_detail_keys=detail_keys,
            detail_texts=detail_texts,
        )
        if display_item is None:
            continue
        dedupe_key = display_item.pop("_display_key", None)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        filtered.append(display_item)
    return filtered


def _safe_int_or_none(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _has_degraded_cause(summary: Dict[str, Any], code: str) -> bool:
    normalized_code = str(code or "").strip()
    if not normalized_code:
        return False

    for item in list(summary.get("degraded_causes") or []):
        if str(item or "").strip() == normalized_code:
            return True

    for item in list(summary.get("degradation_events") or []):
        if isinstance(item, dict) and str(item.get("code") or "").strip() == normalized_code:
            return True
    return False


def _build_warning_pipeline_display(summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    has_summary_merge_failed = _has_degraded_cause(summary, "summary_merge_failed")
    algo = summary.get("algo")
    warning_pipeline = algo.get("warning_pipeline") if isinstance(algo, dict) else None

    if isinstance(warning_pipeline, dict):
        summary_merge_failed = bool(warning_pipeline.get("summary_merge_failed") or False) or has_summary_merge_failed
        if not summary_merge_failed:
            return None
        return {
            "source": "warning_pipeline",
            "message": "排产提示没有完整整理。",
            "note": "部分排产提示没有完整写入历史摘要。",
            "summary_merge_failed": True,
            "summary_merge_error": public_summary_merge_error_code(warning_pipeline.get("summary_merge_error")),
            "algo_warning_count": _safe_int_or_none(warning_pipeline.get("algo_warning_count")),
            "summary_warning_count": _safe_int_or_none(warning_pipeline.get("summary_warning_count")),
        }

    if not has_summary_merge_failed:
        return None

    return {
        "source": "legacy_degraded_causes",
        "message": "排产提示没有完整整理。",
        "note": "历史摘要未记录提示整理明细。",
        "summary_merge_failed": True,
        "summary_merge_error": None,
        "algo_warning_count": None,
        "summary_warning_count": None,
    }


def build_summary_display_state(
    summary: Optional[Dict[str, Any]],
    *,
    result_status: Any,
    parse_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    summary_dict = summary if isinstance(summary, dict) else {}
    result_state = build_result_state(result_status=result_status, summary=summary_dict)
    summary_counts = counts_from_summary(summary_dict)
    summary_count_parse_failed = bool(summary_counts.get("_parse_failed"))
    completion_status = str(result_state.get("outcome_status") or "")
    if not completion_status:
        # derive_completion_status 恒返回 4 值之一、不应为空；万一为空，按裁决诚实降级
        # 为 unknown（「有问题，需检查」），不静默兜成 success。
        completion_status = "unknown"
    primary_degradation = build_primary_degradation(summary_dict, result_state=result_state, completion_status=completion_status)
    secondary_degradation_messages = build_summary_degradation_messages(summary_dict)
    display_secondary_degradation_messages = build_display_secondary_degradation_messages(
        primary_degradation,
        secondary_degradation_messages,
    )
    warning_pipeline_display = _build_warning_pipeline_display(summary_dict)

    warning_messages = _normalize_text_list(summary_dict.get("warnings"))
    public_warning_messages = public_summary_warning_messages(summary_dict.get("warnings"))
    maintenance_diagnostic_count = sum(1 for item in warning_messages if not public_summary_warning_messages([item]))
    warnings_preview = public_warning_messages[:3]
    error_messages = _summary_error_messages(summary_dict)
    error_total, error_count_parse_failed = _non_negative_count_state(
        summary_dict.get("error_count"),
        fallback=len(error_messages),
    )
    missing_resource_items = _missing_resource_display_items(summary_dict.get("missing_internal_resource_ops"))
    missing_resource_total, missing_resource_count_parse_failed = _non_negative_count_state(
        summary_dict.get("missing_internal_resource_count"),
        fallback=len(missing_resource_items),
    )
    any_count_parse_failed = bool(
        summary_count_parse_failed
        or error_count_parse_failed
        or missing_resource_count_parse_failed
    )
    parse_state_dict = {
        "payload": None,
        "parse_failed": False,
        "user_message": None,
        "reason": None,
    }
    if isinstance(parse_state, dict):
        for key in ("parse_failed", "user_message", "reason", "raw_type"):
            if key in parse_state:
                parse_state_dict[key] = parse_state.get(key)

    return {
        "result_state": result_state,
        "completion_status": completion_status,
        "result_status_label": str(result_state.get("display_label") or "-"),
        "primary_degradation": primary_degradation,
        "secondary_degradation_messages": secondary_degradation_messages,
        "display_secondary_degradation_messages": display_secondary_degradation_messages,
        "warning_pipeline_display": warning_pipeline_display,
        "warnings_preview": warnings_preview,
        "warning_total": len(public_warning_messages),
        "warning_hidden_count": max(0, len(public_warning_messages) - len(warnings_preview)),
        "warning_recorded_total": len(warning_messages),
        "warning_internal_count": maintenance_diagnostic_count,
        "maintenance_diagnostic_count": maintenance_diagnostic_count,
        "errors_preview": error_messages[:3],
        "errors_display": error_messages,
        "error_display_count": len(error_messages),
        "error_total": error_total,
        "error_total_label": "记录异常" if error_count_parse_failed else f"{error_total} 条",
        "error_count_parse_failed": error_count_parse_failed,
        "error_hidden_count": max(0, error_total - len(error_messages)),
        "missing_internal_resource_ops": missing_resource_items,
        "missing_internal_resource_count": missing_resource_total,
        "missing_internal_resource_count_label": "记录异常"
        if missing_resource_count_parse_failed
        else f"{missing_resource_total} 道工序",
        "missing_internal_resource_count_parse_failed": missing_resource_count_parse_failed,
        "missing_internal_resource_hidden_count": max(0, missing_resource_total - len(missing_resource_items)),
        "errors_truncated": bool(summary_dict.get("errors_truncated")),
        "missing_internal_resource_ops_truncated": bool(summary_dict.get("missing_internal_resource_ops_truncated")),
        "summary_truncated": bool(summary_dict.get("summary_truncated")),
        "summary_parse_state": parse_state_dict,
        "summary_count_parse_failed": any_count_parse_failed,
        "summary_count_parse_message": "排产摘要里的数量记录异常，不能按这些数量判断结果，请检查这次排产历史或日志。"
        if any_count_parse_failed
        else None,
    }


__all__ = ["build_display_secondary_degradation_messages", "build_result_state", "build_summary_display_state", "derive_completion_status", "result_status_display_label"]
