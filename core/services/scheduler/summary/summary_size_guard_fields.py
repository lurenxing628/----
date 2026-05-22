from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from core.models.scheduler_public_errors import (
    public_error_message_from_detail,
    public_safe_identifier,
    public_safe_label,
)
from core.services.scheduler.run.schedule_candidate_summary import candidate_comparison_minimal_summary

SUMMARY_SIZE_LIMIT_BYTES = 512 * 1024
_ALLOWED_MISSING_FIELDS = {"设备", "人员"}


def summary_size_bytes(obj: Dict[str, Any]) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def size_guard_scalar(value: Any, *, max_chars: int = 200) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    return text[:max_chars]


def _guard_text(value: Any, *, max_chars: int) -> str:
    text = str(value or "").strip().replace("\r", " ").replace("\n", " ")
    return text[:max_chars]


def positive_int(value: Any) -> int:
    try:
        number = int(value or 0)
    except Exception:
        return 0
    return number if number > 0 else 0


def size_guard_dict(raw: Any, *, max_items: int = 20, max_value_chars: int = 120) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    for key, value in raw.items():
        if len(out) >= max_items:
            break
        key_text = str(key or "").strip()[:80]
        if not key_text:
            continue
        out[key_text] = size_guard_scalar(value, max_chars=max_value_chars)
    return out


def _copy_guarded_text_fields(raw: Dict[str, Any], out: Dict[str, Any], fields: Tuple[str, ...], *, max_chars: int) -> None:
    for key in fields:
        text = _guard_text(raw.get(key), max_chars=max_chars)
        if text:
            out[key] = text


def _copy_guarded_int_fields(raw: Dict[str, Any], out: Dict[str, Any], fields: Tuple[str, ...]) -> None:
    for key in fields:
        number = positive_int(raw.get(key))
        if number > 0:
            out[key] = number


def _guard_missing_fields(value: Any) -> List[str]:
    fields: List[str] = []
    for item in list(value or []):
        text = str(item or "").strip()
        if text in _ALLOWED_MISSING_FIELDS:
            fields.append(text)
    return fields[:2]


def size_guard_public_error_detail(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    _copy_guarded_text_fields(raw, out, ("schema_version", "code", "severity"), max_chars=80)
    message = public_error_message_from_detail(raw)
    if message:
        out["message"] = message
    _copy_guarded_int_fields(raw, out, ("op_id", "seq"))
    batch_id = public_safe_identifier(raw.get("batch_id"))
    if batch_id:
        out["batch_id"] = batch_id
    op_code = public_safe_identifier(raw.get("op_code"))
    if op_code:
        out["op_code"] = op_code
    fields = _guard_missing_fields(raw.get("missing_fields"))
    if fields:
        out["missing_fields"] = fields
    return out


def size_guard_missing_resource_item(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    _copy_guarded_int_fields(raw, out, ("op_id", "seq"))
    batch_id = public_safe_identifier(raw.get("batch_id"))
    if batch_id:
        out["batch_id"] = batch_id
    op_code = public_safe_identifier(raw.get("op_code"))
    if op_code:
        out["op_code"] = op_code
    op_type_name = public_safe_label(raw.get("op_type_name"))
    if op_type_name:
        out["op_type_name"] = op_type_name
    fields = _guard_missing_fields(raw.get("missing_fields"))
    if fields:
        out["missing_fields"] = fields
    return out


def guarded_items(raw_list: Any, limit: int, guard_fn: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_list, list):
        return []
    return [item for item in (guard_fn(raw) for raw in raw_list[:limit]) if item]


def _copy_minimal_error_fields(minimal: Dict[str, Any], result_summary_obj: Dict[str, Any]) -> None:
    if result_summary_obj.get("error_count") is not None:
        minimal["error_count"] = size_guard_scalar(result_summary_obj.get("error_count"), max_chars=40)
    if result_summary_obj.get("raw_error_count") is not None:
        minimal["raw_error_count"] = size_guard_scalar(result_summary_obj.get("raw_error_count"), max_chars=40)
    if isinstance(result_summary_obj.get("public_error_details"), list):
        minimal["public_error_details"] = guarded_items(
            result_summary_obj.get("public_error_details"),
            10,
            size_guard_public_error_detail,
        )
    if isinstance(result_summary_obj.get("errors_sample"), list):
        minimal["errors_sample"] = [str(item)[:200] for item in list(result_summary_obj.get("errors_sample") or [])[:10]]
    if result_summary_obj.get("errors_truncated"):
        minimal["errors_truncated"] = True


def _copy_minimal_missing_resource_fields(minimal: Dict[str, Any], result_summary_obj: Dict[str, Any]) -> None:
    if result_summary_obj.get("missing_internal_resource_count") is not None:
        minimal["missing_internal_resource_count"] = size_guard_scalar(
            result_summary_obj.get("missing_internal_resource_count"),
            max_chars=40,
        )
    if isinstance(result_summary_obj.get("missing_internal_resource_ops"), list):
        minimal["missing_internal_resource_ops"] = guarded_items(
            result_summary_obj.get("missing_internal_resource_ops"),
            10,
            size_guard_missing_resource_item,
        )
    if result_summary_obj.get("missing_internal_resource_ops_truncated"):
        minimal["missing_internal_resource_ops_truncated"] = True


def _size_guard_degradation_event(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    _copy_guarded_text_fields(raw, out, ("code", "scope", "field", "message", "sample"), max_chars=160)
    _copy_guarded_int_fields(raw, out, ("count",))
    return out


def _copy_minimal_degradation_fields(minimal: Dict[str, Any], result_summary_obj: Dict[str, Any]) -> None:
    events = result_summary_obj.get("degradation_events")
    if isinstance(events, list):
        minimal["degradation_events"] = guarded_items(events, 20, _size_guard_degradation_event)
        if len(events) > 20:
            minimal["degradation_events_truncated"] = True
    counters = size_guard_dict(result_summary_obj.get("degradation_counters"), max_items=30, max_value_chars=40)
    if counters:
        minimal["degradation_counters"] = counters
    causes = result_summary_obj.get("degraded_causes")
    if isinstance(causes, list):
        minimal["degraded_causes"] = [str(item).strip()[:120] for item in causes[:20] if str(item).strip()]
        if len(causes) > 20:
            minimal["degraded_causes_truncated"] = True


def warning_sample(warnings: Any, *, limit: int = 10) -> List[str]:
    if not isinstance(warnings, list):
        return []
    sample: List[str] = []
    for item in warnings:
        text = str(item or "").strip()
        if not text:
            continue
        sample.append(text[:200])
        if len(sample) >= limit:
            break
    return sample


def _copy_minimal_warning_fields(minimal: Dict[str, Any], result_summary_obj: Dict[str, Any]) -> None:
    warning_count = positive_int(result_summary_obj.get("warning_count"))
    if warning_count > 0:
        minimal["warning_count"] = int(warning_count)
    sample = warning_sample(result_summary_obj.get("warnings_sample"))
    if sample:
        minimal["warnings_sample"] = sample
    elif isinstance(result_summary_obj.get("warnings"), list):
        sample = warning_sample(result_summary_obj.get("warnings"))
        if sample:
            minimal["warnings_sample"] = sample
    if result_summary_obj.get("warnings_truncated"):
        minimal["warnings_truncated"] = True


def minimal_summary_for_size_guard(
    result_summary_obj: Dict[str, Any],
    *,
    original_size: int,
    diagnostics_truncated: bool,
) -> Dict[str, Any]:
    algo = result_summary_obj.get("algo")
    algo_dict = algo if isinstance(algo, dict) else {}
    overdue_batches = result_summary_obj.get("overdue_batches")
    overdue_dict = overdue_batches if isinstance(overdue_batches, dict) else {}

    minimal: Dict[str, Any] = {
        "summary_schema_version": size_guard_scalar(result_summary_obj.get("summary_schema_version") or "1.2", max_chars=20),
        "is_simulation": bool(result_summary_obj.get("is_simulation") or False),
        "completion_status": size_guard_scalar(result_summary_obj.get("completion_status"), max_chars=40),
        "readiness": size_guard_dict(result_summary_obj.get("readiness"), max_items=4, max_value_chars=40),
        "version": size_guard_scalar(result_summary_obj.get("version"), max_chars=40),
        "strategy": size_guard_scalar(result_summary_obj.get("strategy"), max_chars=80),
        "result_status": size_guard_scalar(result_summary_obj.get("result_status"), max_chars=80),
        "counts": size_guard_dict(result_summary_obj.get("counts"), max_items=20, max_value_chars=40),
        "time_cost_ms": size_guard_scalar(result_summary_obj.get("time_cost_ms"), max_chars=40),
        "summary_truncated": True,
        "original_size_bytes": int(original_size),
    }

    if result_summary_obj.get("result_status_detail") is not None:
        minimal["result_status_detail"] = size_guard_scalar(result_summary_obj.get("result_status_detail"), max_chars=200)
    if result_summary_obj.get("degraded_success") is not None:
        minimal["degraded_success"] = bool(result_summary_obj.get("degraded_success"))
    if result_summary_obj.get("invalid_due_count") is not None:
        minimal["invalid_due_count"] = size_guard_scalar(result_summary_obj.get("invalid_due_count"), max_chars=40)
    if result_summary_obj.get("unscheduled_batch_count") is not None:
        minimal["unscheduled_batch_count"] = size_guard_scalar(result_summary_obj.get("unscheduled_batch_count"), max_chars=40)
    if overdue_dict:
        minimal["overdue_batches"] = {"count": size_guard_scalar(overdue_dict.get("count"), max_chars=40)}
    _copy_minimal_error_fields(minimal, result_summary_obj)
    _copy_minimal_missing_resource_fields(minimal, result_summary_obj)
    _copy_minimal_degradation_fields(minimal, result_summary_obj)
    _copy_minimal_warning_fields(minimal, result_summary_obj)

    minimal_algo = size_guard_dict(
        {
            "mode": algo_dict.get("mode"),
            "objective": algo_dict.get("objective"),
            "comparison_metric": algo_dict.get("comparison_metric"),
            "time_budget_seconds": algo_dict.get("time_budget_seconds"),
        },
        max_items=4,
        max_value_chars=80,
    )
    candidate_comparison = candidate_comparison_minimal_summary(algo_dict.get("candidate_comparison"))
    if candidate_comparison:
        minimal_algo["candidate_comparison"] = candidate_comparison
    if minimal_algo:
        minimal["algo"] = minimal_algo
    if diagnostics_truncated or bool(result_summary_obj.get("diagnostics_truncated")):
        minimal["diagnostics_truncated"] = True
    if summary_size_bytes(minimal) <= SUMMARY_SIZE_LIMIT_BYTES:
        return minimal
    return {
        "summary_schema_version": "1.2",
        "summary_truncated": True,
        "original_size_bytes": int(original_size),
    }


__all__ = [
    "SUMMARY_SIZE_LIMIT_BYTES",
    "guarded_items",
    "minimal_summary_for_size_guard",
    "positive_int",
    "size_guard_missing_resource_item",
    "size_guard_public_error_detail",
    "summary_size_bytes",
    "warning_sample",
]
