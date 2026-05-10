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
)

from .scheduler_degradation_presenter import (
    build_primary_degradation,
    build_summary_degradation_messages,
    degradation_display_key,
    degradation_reason_key,
    format_degradation_detail,
)

_RESULT_STATUS_LABELS = {
    "success": "成功",
    "partial": "部分成功",
    "failed": "失败",
    "simulated": "模拟排产",
    "unknown": "完成状态未知",
}
_COMPLETION_STATUS_VALUES = {"success", "partial", "failed"}
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
        message = str(item.get("message") or "").strip().replace("\r", " ").replace("\n", " ")[:500]
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


def _normalize_missing_resource_fields(value: Any) -> List[str]:
    fields = _normalize_text_list(value)
    return [item for item in fields if item in {"设备", "人员"}]


def _safe_short_display_text(value: Any, *, max_chars: int = 80) -> str:
    text = str(value or "").strip()
    text = text.replace("\r", " ").replace("\n", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text[:max_chars]


def _missing_resource_label(item: Dict[str, Any]) -> str:
    seq = _safe_positive_int(item.get("seq"))
    label_parts = [
        _safe_short_display_text(item.get("batch_id")),
        f"工序{seq}" if seq is not None else "",
        _safe_short_display_text(item.get("op_type_name") or item.get("op_code")),
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
        batch_id = _safe_short_display_text(raw_item.get("batch_id"))
        op_id = _safe_positive_int(raw_item.get("op_id"))
        seq = _safe_positive_int(raw_item.get("seq"))
        op_code = _safe_short_display_text(raw_item.get("op_code"))
        op_type_name = _safe_short_display_text(raw_item.get("op_type_name"))
        dedupe_key = (op_id, batch_id, seq, op_code, tuple(fields))
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
    return format_degradation_detail(item.get("label"), item.get("count"))


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


def _counts_from_summary(summary: Dict[str, Any]) -> Dict[str, int]:
    counts = summary.get("counts")
    if not isinstance(counts, dict):
        counts = {}

    def _to_int(value: Any) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    return {
        "scheduled_ops": _to_int(counts.get("scheduled_ops", summary.get("scheduled_ops"))),
        "failed_ops": _to_int(counts.get("failed_ops", summary.get("failed_ops"))),
        "total_ops": _to_int(counts.get("op_count", counts.get("total_ops", summary.get("total_ops")))),
    }


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


def _known_completion_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in _COMPLETION_STATUS_VALUES:
        return text
    return ""


def _completion_status_from_counts(*, status: str, scheduled_ops: int, failed_ops: int, total_ops: int) -> str:
    if status == "simulated" and scheduled_ops <= 0 and failed_ops <= 0 and total_ops <= 0:
        return "unknown"
    if failed_ops > 0 and scheduled_ops > 0:
        return "partial"
    if failed_ops > 0:
        return "failed"
    if total_ops > 0 and scheduled_ops < total_ops:
        return "partial"
    return "success"

def derive_completion_status(*, result_status: Any, summary: Optional[Dict[str, Any]]) -> str:
    summary_dict = summary if isinstance(summary, dict) else {}
    summary_status = _known_completion_status(summary_dict.get("completion_status"))
    if summary_status:
        return summary_status

    status = str(result_status or "").strip().lower()
    known_status = _known_completion_status(status)
    if known_status:
        return known_status

    counts = _counts_from_summary(summary_dict)
    return _completion_status_from_counts(
        status=status,
        scheduled_ops=int(counts.get("scheduled_ops") or 0),
        failed_ops=int(counts.get("failed_ops") or 0),
        total_ops=int(counts.get("total_ops") or 0),
    )


def result_status_display_label(*, raw_status: Any, outcome_status: Any) -> str:
    raw = str(raw_status or "").strip().lower()
    outcome = str(outcome_status or "").strip().lower()
    raw_label = _RESULT_STATUS_LABELS.get(raw, raw or "")
    outcome_label = _RESULT_STATUS_LABELS.get(outcome, outcome or "")
    if raw == "simulated" and outcome_label:
        return f"{raw_label} / {outcome_label}"
    return outcome_label or raw_label or "-"


def build_result_state(*, result_status: Any, summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw_status = str(result_status or "").strip().lower()
    outcome_status = derive_completion_status(result_status=result_status, summary=summary)
    return {
        "raw_status": raw_status,
        "outcome_status": outcome_status,
        "is_simulated": raw_status == "simulated",
        "display_label": result_status_display_label(raw_status=raw_status, outcome_status=outcome_status),
    }


def build_summary_display_state(
    summary: Optional[Dict[str, Any]],
    *,
    result_status: Any,
    parse_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    summary_dict = summary if isinstance(summary, dict) else {}
    result_state = build_result_state(result_status=result_status, summary=summary_dict)
    completion_status = str(result_state.get("outcome_status") or "")
    if not completion_status:
        completion_status = "success"
    primary_degradation = build_primary_degradation(summary_dict, result_state=result_state, completion_status=completion_status)
    secondary_degradation_messages = build_summary_degradation_messages(summary_dict)
    display_secondary_degradation_messages = build_display_secondary_degradation_messages(
        primary_degradation,
        secondary_degradation_messages,
    )
    warning_pipeline_display = _build_warning_pipeline_display(summary_dict)

    warning_messages = _normalize_text_list(summary_dict.get("warnings"))
    public_warning_messages = public_summary_warning_messages(summary_dict.get("warnings"))
    warnings_preview = public_warning_messages[:3]
    error_messages = _summary_error_messages(summary_dict)
    try:
        error_total = int(summary_dict.get("error_count") or len(error_messages))
    except Exception:
        error_total = len(error_messages)
    error_total = max(error_total, len(error_messages))
    missing_resource_items = _missing_resource_display_items(summary_dict.get("missing_internal_resource_ops"))
    try:
        missing_resource_total = int(summary_dict.get("missing_internal_resource_count") or len(missing_resource_items))
    except Exception:
        missing_resource_total = len(missing_resource_items)
    missing_resource_total = max(missing_resource_total, len(missing_resource_items))
    parse_state_dict = {
        "payload": summary if isinstance(summary, dict) else None,
        "parse_failed": False,
        "user_message": None,
        "reason": None,
    }
    if isinstance(parse_state, dict):
        parse_state_dict.update(parse_state)

    return {
        "result_state": result_state,
        "completion_status": completion_status,
        "result_status_label": str(result_state.get("display_label") or "-"),
        "primary_degradation": primary_degradation,
        "secondary_degradation_messages": secondary_degradation_messages,
        "display_secondary_degradation_messages": display_secondary_degradation_messages,
        "warning_pipeline_display": warning_pipeline_display,
        "warnings_preview": warnings_preview,
        "warning_total": len(warning_messages),
        "warning_hidden_count": max(0, len(warning_messages) - len(warnings_preview)),
        "errors_preview": error_messages[:3],
        "errors_display": error_messages,
        "error_display_count": len(error_messages),
        "error_total": error_total,
        "error_hidden_count": max(0, error_total - len(error_messages)),
        "missing_internal_resource_ops": missing_resource_items,
        "missing_internal_resource_count": missing_resource_total,
        "missing_internal_resource_hidden_count": max(0, missing_resource_total - len(missing_resource_items)),
        "errors_truncated": bool(summary_dict.get("errors_truncated")),
        "missing_internal_resource_ops_truncated": bool(summary_dict.get("missing_internal_resource_ops_truncated")),
        "summary_truncated": bool(summary_dict.get("summary_truncated")),
        "summary_parse_state": parse_state_dict,
    }


__all__ = [
    "build_display_secondary_degradation_messages",
    "build_result_state",
    "build_summary_display_state",
    "derive_completion_status",
    "result_status_display_label",
]
