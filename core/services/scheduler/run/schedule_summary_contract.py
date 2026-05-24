from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..summary.summary_count_parse import parse_summary_count


@dataclass(frozen=True)
class ScheduleSummaryContract:
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.payload)


def _summary_field(summary: Any, field: str, default: Any) -> Any:
    if isinstance(summary, dict):
        return summary.get(field, default)
    return getattr(summary, field, default)


def _summary_text_list(result_summary_obj: Dict[str, Any], summary: Any, field: str) -> List[str]:
    if isinstance(result_summary_obj, dict) and field in result_summary_obj:
        raw_items = result_summary_obj.get(field)
    else:
        raw_items = _summary_field(summary, field, [])
    if raw_items is None:
        return []
    if isinstance(raw_items, str):
        return [raw_items] if raw_items else []
    try:
        return [str(item) for item in list(raw_items or []) if str(item)]
    except Exception:
        text = str(raw_items).strip()
        return [text] if text else []


def _summary_warnings(result_summary_obj: Dict[str, Any], summary: Any) -> List[str]:
    return _summary_text_list(result_summary_obj, summary, "warnings")


def _summary_errors(result_summary_obj: Dict[str, Any], summary: Any) -> List[str]:
    return _summary_text_list(result_summary_obj, summary, "errors")


def _summary_counts(result_summary_obj: Dict[str, Any], summary: Any) -> Tuple[Dict[str, int], List[str]]:
    raw_counts = result_summary_obj.get("counts") if isinstance(result_summary_obj, dict) else {}
    counts = dict(raw_counts or {}) if isinstance(raw_counts, dict) else {}
    errors: List[str] = []
    field_specs = (
        ("total_ops", counts.get("op_count", counts.get("total_ops", _summary_field(summary, "total_ops", 0)))),
        ("scheduled_ops", counts.get("scheduled_ops", _summary_field(summary, "scheduled_ops", 0))),
        ("failed_ops", counts.get("failed_ops", _summary_field(summary, "failed_ops", 0))),
    )
    parsed = {}
    for field, raw_value in field_specs:
        parsed[field], err = parse_summary_count(raw_value, field=field)
        if err:
            errors.append(err)
    for field in ("total_ops", "scheduled_ops", "failed_ops"):
        _parsed, raw_err = parse_summary_count(_summary_field(summary, field, None), field=field)
        if raw_err and raw_err not in errors:
            errors.append(raw_err)

    total_ops = parsed["total_ops"]
    counts["op_count"] = total_ops
    counts["total_ops"] = total_ops
    counts["scheduled_ops"] = parsed["scheduled_ops"]
    counts["failed_ops"] = parsed["failed_ops"]
    return counts, errors


def _safe_count(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return int(default)


def _merge_count_errors(payload: Dict[str, Any], count_errors: List[str]) -> List[str]:
    existing = [str(item) for item in list(payload.get("summary_count_parse_errors") or []) if str(item)]
    for err in count_errors:
        if err not in existing:
            existing.append(err)
    return existing


def _append_count_warning(payload: Dict[str, Any], warning_text: str) -> None:
    payload["warnings"] = list(payload.get("warnings") or [])
    if warning_text not in payload["warnings"]:
        payload["warnings"].append(warning_text)


def _append_count_error_samples(payload: Dict[str, Any], count_errors: List[str]) -> None:
    payload["errors_sample"] = list(payload.get("errors_sample") or [])
    for err in count_errors[:10]:
        if err not in payload["errors_sample"]:
            payload["errors_sample"].append(err)


def _ensure_count_degradation_event(payload: Dict[str, Any], warning_text: str, count_errors: List[str]) -> None:
    events = list(payload.get("degradation_events") or [])
    exists = any(str(event.get("code") or "") == "summary_count_parse_failed" for event in events if isinstance(event, dict))
    if not exists:
        events.append(
            {
                "code": "summary_count_parse_failed",
                "scope": "schedule.summary.contract",
                "field": "counts",
                "message": warning_text,
                "count": len(count_errors),
            }
        )
    payload["degradation_events"] = events


def _set_count_degradation_metadata(payload: Dict[str, Any], count_errors: List[str]) -> None:
    counters = dict(payload.get("degradation_counters") or {})
    counters["summary_count_parse_failed"] = max(int(counters.get("summary_count_parse_failed") or 0), len(count_errors))
    payload["degradation_counters"] = counters
    causes = list(payload.get("degraded_causes") or [])
    if "summary_count_parse_failed" not in causes:
        causes.append("summary_count_parse_failed")
    payload["degraded_causes"] = causes
    payload["degraded_success"] = bool(payload.get("degraded_success") or payload.get("success"))


def _apply_count_error_state(payload: Dict[str, Any], count_errors: List[str], errors: List[str]) -> None:
    if not count_errors:
        return
    warning_text = "排产摘要里的数量记录异常，不能按这些数量判断结果。"
    payload["summary_count_parse_failed"] = True
    payload["summary_count_parse_errors"] = count_errors[:10]
    _append_count_warning(payload, warning_text)
    _append_count_error_samples(payload, count_errors)
    _ensure_count_degradation_event(payload, warning_text, count_errors)
    _set_count_degradation_metadata(payload, count_errors)
    payload["error_count"] = max(_safe_count(payload.get("error_count"), 0), len(payload["errors_sample"]), len(errors))


def build_summary_contract(summary: Any, *, result_summary_obj: Dict[str, Any]) -> ScheduleSummaryContract:
    payload = dict(result_summary_obj or {})
    warnings = _summary_warnings(result_summary_obj, summary)
    errors = _summary_errors(result_summary_obj, summary)
    counts, count_errors = _summary_counts(result_summary_obj, summary)
    payload.update(
        {
            "success": bool(_summary_field(summary, "success", False)),
            "total_ops": int(counts.get("total_ops") or 0),
            "scheduled_ops": int(counts.get("scheduled_ops") or 0),
            "failed_ops": int(counts.get("failed_ops") or 0),
            "warnings": list(warnings),
            "errors": list(errors),
            "duration_seconds": float(_summary_field(summary, "duration_seconds", 0.0) or 0.0),
            "degradation_events": list(payload.get("degradation_events") or []),
            "degradation_counters": dict(payload.get("degradation_counters") or {}),
            "degraded_success": bool(payload.get("degraded_success") or False),
            "degraded_causes": list(payload.get("degraded_causes") or []),
            "error_count": _safe_count(payload.get("error_count"), len(errors)),
            "errors_sample": list(payload.get("errors_sample") or errors[:10]),
            "counts": counts,
        }
    )
    _apply_count_error_state(payload, _merge_count_errors(payload, count_errors), errors)
    payload["error_count"] = max(_safe_count(payload.get("error_count"), 0), len(payload["errors_sample"]), len(errors))
    return ScheduleSummaryContract(payload=payload)
