from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.models.scheduler_public_errors import (
    public_error_message_from_detail,
    public_safe_identifier,
    public_safe_label,
)
from core.services.scheduler.contracts.optimizer_public_search_report import project_search_report
from core.services.scheduler.run.schedule_candidate_summary import candidate_comparison_minimal_summary
from core.shared.strict_json import canonical_json

SUMMARY_SIZE_LIMIT_BYTES = 512 * 1024
_ALLOWED_MISSING_FIELDS = {"设备", "人员"}


def summary_size_bytes(obj: Dict[str, Any]) -> int:
    # Measured with the encoder that persists the summary (workbench_run_repo, official_persistence).
    return len(canonical_json(obj).encode("utf-8"))


def _guard_text(value: Any, *, max_chars: int) -> str:
    text = str(value or "").strip().replace("\r", " ").replace("\n", " ")
    return text[:max_chars]


def _search_report_minimal_summary(raw: Any) -> Dict[str, Any]:
    public_report, _diagnostics = project_search_report(raw)
    if not public_report:
        return {}
    allowed = (
        "schema_version",
        "algorithm_profile",
        "seed",
        "stop_reason",
        "best_origin",
        "time_budget_seconds",
        "runtime_ms",
        "iterations",
        "evaluated_candidates",
        "distinct_candidates",
        "accepted_candidates",
        "accepted_distinct_candidates",
        "current_accepted_candidates",
        "best_improved_candidates",
        "rejected_candidates",
        "best_score",
        "objective_name",
        "distinct_fingerprint_scope",
        "distinct_fingerprint_description",
        "best_fingerprint_changed",
        "distinct_output_scope",
        "distinct_output_description",
        "best_output_changed",
        "improved",
        "skipped_phases",
        "public_attempt_summary",
        "neighborhood_summary",
        "acceptance_summary",
        "vns_summary",
        "profile_public",
    )
    return {key: public_report[key] for key in allowed if key in public_report}


def _copy_guarded_text_fields(raw: Dict[str, Any], out: Dict[str, Any], fields: Tuple[str, ...], *, max_chars: int) -> None:
    for key in fields:
        text = _guard_text(raw.get(key), max_chars=max_chars)
        if text:
            out[key] = text


def _copy_present_int_fields(raw: Dict[str, Any], out: Dict[str, Any], fields: Tuple[str, ...]) -> None:
    # 这些计数/编号都由本次排产在进程内写入：make_public_error 只在有正整数时写 op_id/seq，
    # 缺资源样本的 seq 与降级事件的 count 恒为正整数，这里按原值保留。
    for key in fields:
        if key in raw:
            out[key] = raw[key]


def _guard_missing_fields(value: List[str]) -> List[str]:
    # missing_fields is always the 设备/人员 list from schedule_persistence_errors._missing_resource_fields.
    return [item for item in value if item in _ALLOWED_MISSING_FIELDS][:2]


def size_guard_public_error_detail(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    _copy_guarded_text_fields(raw, out, ("schema_version", "code", "severity"), max_chars=80)
    message = public_error_message_from_detail(raw)
    if message:
        out["message"] = message
    _copy_present_int_fields(raw, out, ("op_id", "seq"))
    batch_id = public_safe_identifier(raw.get("batch_id"))
    if batch_id:
        out["batch_id"] = batch_id
    # message 由 op_code / failed_op_code 现场重算；投影必须保留它们，才能对自身输出重复投影不坍塌成 "-"。
    op_code = public_safe_identifier(raw.get("op_code"))
    if op_code:
        out["op_code"] = op_code
    failed_op_code = public_safe_identifier(raw.get("failed_op_code"))
    if failed_op_code:
        out["failed_op_code"] = failed_op_code
    return out


def size_guard_missing_resource_item(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    _copy_present_int_fields(raw, out, ("seq",))
    batch_id = public_safe_identifier(raw.get("batch_id"))
    if batch_id:
        out["batch_id"] = batch_id
    op_type_name = public_safe_label(raw.get("op_type_name"))
    if op_type_name:
        out["op_type_name"] = op_type_name
    fields = _guard_missing_fields(raw["missing_fields"])
    if fields:
        out["missing_fields"] = fields
    return out


def guarded_items(raw_list: Any, limit: int, guard_fn: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_list, list):
        return []
    return [item for item in (guard_fn(raw) for raw in raw_list[:limit]) if item]


def _copy_minimal_error_fields(minimal: Dict[str, Any], result_summary_obj: Dict[str, Any]) -> None:
    if "error_count" in result_summary_obj:
        minimal["error_count"] = result_summary_obj["error_count"]
    if "failure_detail_count" in result_summary_obj:
        minimal["failure_detail_count"] = result_summary_obj["failure_detail_count"]
    if isinstance(result_summary_obj.get("public_error_details"), list):
        minimal["public_error_details"] = guarded_items(
            result_summary_obj.get("public_error_details"),
            10,
            size_guard_public_error_detail,
        )
    if isinstance(result_summary_obj.get("errors_sample"), list):
        minimal["errors_sample"] = [str(item)[:200] for item in result_summary_obj["errors_sample"][:10]]
    if result_summary_obj.get("errors_truncated"):
        minimal["errors_truncated"] = True


def _copy_minimal_missing_resource_fields(minimal: Dict[str, Any], result_summary_obj: Dict[str, Any]) -> None:
    if "missing_internal_resource_count" in result_summary_obj:
        minimal["missing_internal_resource_count"] = result_summary_obj["missing_internal_resource_count"]
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
    _copy_present_int_fields(raw, out, ("count",))
    return out


def _copy_minimal_degradation_fields(minimal: Dict[str, Any], result_summary_obj: Dict[str, Any]) -> None:
    events = result_summary_obj.get("degradation_events")
    if isinstance(events, list):
        minimal["degradation_events"] = guarded_items(events, 20, _size_guard_degradation_event)
        if len(events) > 20:
            minimal["degradation_events_truncated"] = True
    counters = result_summary_obj.get("degradation_counters")
    if isinstance(counters, dict) and counters:
        minimal["degradation_counters"] = dict(list(counters.items())[:30])
    causes = result_summary_obj.get("degraded_causes")
    if isinstance(causes, list):
        minimal["degraded_causes"] = [str(item).strip()[:120] for item in causes[:20] if str(item).strip()]
        if len(causes) > 20:
            minimal["degraded_causes_truncated"] = True


def warning_sample(warnings: Any) -> List[str]:
    if not isinstance(warnings, list):
        return []
    sample: List[str] = []
    for item in warnings:
        text = item.strip()
        if not text:
            continue
        sample.append(text[:200])
        if len(sample) >= 10:
            break
    return sample


def _copy_minimal_warning_fields(minimal: Dict[str, Any], result_summary_obj: Dict[str, Any]) -> None:
    # warning_count 只由 summary_size_guard._remember_warning_summary 在有告警时写入正整数。
    if "warning_count" in result_summary_obj:
        minimal["warning_count"] = result_summary_obj["warning_count"]
    sample = warning_sample(result_summary_obj.get("warnings_sample"))
    if sample:
        minimal["warnings_sample"] = sample
    elif isinstance(result_summary_obj.get("warnings"), list):
        sample = warning_sample(result_summary_obj.get("warnings"))
        if sample:
            minimal["warnings_sample"] = sample
    if result_summary_obj.get("warnings_truncated"):
        minimal["warnings_truncated"] = True


def _minimal_due_count_field(minimal: Dict[str, Any], result_summary_obj: Dict[str, Any], key: str) -> None:
    # 超期/临期 minimal 兜底同构：dict 非空时只留 count（丢 items），与 tier 路径互补保关键计数。
    payload = result_summary_obj.get(key)
    if isinstance(payload, dict) and payload:
        bucket: Dict[str, Any] = {"count": payload["count"]}
        if "window_days" in payload:
            bucket["window_days"] = payload["window_days"]
        minimal[key] = bucket


def _minimal_incomplete_batches_field(minimal: Dict[str, Any], result_summary_obj: Dict[str, Any]) -> None:
    payload = result_summary_obj.get("incomplete_batches")
    if not isinstance(payload, dict) or not payload:
        return
    raw_items = payload.get("items")
    items: List[Dict[str, Any]] = []
    if isinstance(raw_items, list):
        for raw in raw_items[:10]:
            if not isinstance(raw, dict):
                continue
            batch_id = public_safe_identifier(raw.get("batch_id"))
            if batch_id:
                items.append({"batch_id": batch_id})
    minimal["incomplete_batches"] = {
        "count": payload["count"],
        "items": items,
    }


def minimal_summary_for_size_guard(
    result_summary_obj: Dict[str, Any],
    *,
    original_size: int,
    diagnostics_truncated: bool,
) -> Dict[str, Any]:
    algo = result_summary_obj.get("algo")
    algo_dict = algo if isinstance(algo, dict) else {}

    minimal: Dict[str, Any] = {
        "summary_schema_version": result_summary_obj["summary_schema_version"],
        "is_simulation": result_summary_obj["is_simulation"],
        "completion_status": result_summary_obj["completion_status"],
        "readiness": dict(result_summary_obj["readiness"]),
        "version": result_summary_obj["version"],
        "strategy": result_summary_obj["strategy"],
        "counts": dict(result_summary_obj["counts"]),
        "time_cost_ms": result_summary_obj["time_cost_ms"],
        "summary_truncated": True,
        "original_size_bytes": int(original_size),
    }

    if "degraded_success" in result_summary_obj:
        minimal["degraded_success"] = result_summary_obj["degraded_success"]
    if "invalid_due_count" in result_summary_obj:
        minimal["invalid_due_count"] = result_summary_obj["invalid_due_count"]
    if "unscheduled_batch_count" in result_summary_obj:
        minimal["unscheduled_batch_count"] = result_summary_obj["unscheduled_batch_count"]
    _minimal_due_count_field(minimal, result_summary_obj, "overdue_batches")
    _minimal_due_count_field(minimal, result_summary_obj, "near_due_batches")
    _minimal_incomplete_batches_field(minimal, result_summary_obj)
    _copy_minimal_error_fields(minimal, result_summary_obj)
    _copy_minimal_missing_resource_fields(minimal, result_summary_obj)
    _copy_minimal_degradation_fields(minimal, result_summary_obj)
    _copy_minimal_warning_fields(minimal, result_summary_obj)

    minimal_algo = {
        key: algo_dict[key]
        for key in ("mode", "objective", "comparison_metric", "time_budget_seconds")
        if algo_dict.get(key) is not None
    }
    candidate_comparison = candidate_comparison_minimal_summary(algo_dict.get("candidate_comparison"))
    if candidate_comparison:
        minimal_algo["candidate_comparison"] = candidate_comparison
    search_report = _search_report_minimal_summary(algo_dict.get("search_report"))
    if search_report:
        minimal_algo["search_report"] = search_report
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
    "size_guard_missing_resource_item",
    "size_guard_public_error_detail",
    "summary_size_bytes",
    "warning_sample",
]
