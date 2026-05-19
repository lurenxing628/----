from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.models.scheduler_public_errors import (
    public_error_message_from_detail,
    public_safe_identifier,
    public_safe_label,
)
from core.services.scheduler.run.schedule_candidate_summary import candidate_comparison_minimal_summary

from .schedule_summary_types import DEFAULT_TRUNCATION_TIERS

SUMMARY_SIZE_LIMIT_BYTES = 512 * 1024
_ALLOWED_MISSING_FIELDS = {"设备", "人员"}


@dataclass
class _SizeGuardState:
    result_summary_obj: Dict[str, Any]
    original_size: int
    diagnostics_truncated: bool = False


def _summary_size_bytes(obj: Dict[str, Any]) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def _size_guard_scalar(value: Any, *, max_chars: int = 200) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    return text[:max_chars]


def _guard_text(value: Any, *, max_chars: int) -> str:
    text = str(value or "").strip().replace("\r", " ").replace("\n", " ")
    return text[:max_chars]


def _positive_int(value: Any) -> int:
    try:
        number = int(value or 0)
    except Exception:
        return 0
    return number if number > 0 else 0


def _size_guard_dict(raw: Any, *, max_items: int = 20, max_value_chars: int = 120) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    for key, value in raw.items():
        if len(out) >= max_items:
            break
        key_text = str(key or "").strip()[:80]
        if not key_text:
            continue
        out[key_text] = _size_guard_scalar(value, max_chars=max_value_chars)
    return out


def _copy_guarded_text_fields(raw: Dict[str, Any], out: Dict[str, Any], fields: Tuple[str, ...], *, max_chars: int) -> None:
    for key in fields:
        text = _guard_text(raw.get(key), max_chars=max_chars)
        if text:
            out[key] = text


def _copy_guarded_int_fields(raw: Dict[str, Any], out: Dict[str, Any], fields: Tuple[str, ...]) -> None:
    for key in fields:
        number = _positive_int(raw.get(key))
        if number > 0:
            out[key] = number


def _guard_missing_fields(value: Any) -> List[str]:
    fields: List[str] = []
    for item in list(value or []):
        text = str(item or "").strip()
        if text in _ALLOWED_MISSING_FIELDS:
            fields.append(text)
    return fields[:2]


def _size_guard_public_error_detail(raw: Any) -> Dict[str, Any]:
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


def _size_guard_missing_resource_item(raw: Any) -> Dict[str, Any]:
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


def _guarded_items(raw_list: Any, limit: int, guard_fn: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_list, list):
        return []
    return [item for item in (guard_fn(raw) for raw in raw_list[:limit]) if item]


def _copy_minimal_error_fields(minimal: Dict[str, Any], result_summary_obj: Dict[str, Any]) -> None:
    if result_summary_obj.get("error_count") is not None:
        minimal["error_count"] = _size_guard_scalar(result_summary_obj.get("error_count"), max_chars=40)
    if result_summary_obj.get("raw_error_count") is not None:
        minimal["raw_error_count"] = _size_guard_scalar(result_summary_obj.get("raw_error_count"), max_chars=40)
    if isinstance(result_summary_obj.get("public_error_details"), list):
        minimal["public_error_details"] = _guarded_items(
            result_summary_obj.get("public_error_details"),
            10,
            _size_guard_public_error_detail,
        )
    if isinstance(result_summary_obj.get("errors_sample"), list):
        minimal["errors_sample"] = [str(item)[:200] for item in list(result_summary_obj.get("errors_sample") or [])[:10]]
    if result_summary_obj.get("errors_truncated"):
        minimal["errors_truncated"] = True


def _copy_minimal_missing_resource_fields(minimal: Dict[str, Any], result_summary_obj: Dict[str, Any]) -> None:
    if result_summary_obj.get("missing_internal_resource_count") is not None:
        minimal["missing_internal_resource_count"] = _size_guard_scalar(
            result_summary_obj.get("missing_internal_resource_count"),
            max_chars=40,
        )
    if isinstance(result_summary_obj.get("missing_internal_resource_ops"), list):
        minimal["missing_internal_resource_ops"] = _guarded_items(
            result_summary_obj.get("missing_internal_resource_ops"),
            10,
            _size_guard_missing_resource_item,
        )
    if result_summary_obj.get("missing_internal_resource_ops_truncated"):
        minimal["missing_internal_resource_ops_truncated"] = True


def _minimal_summary_for_size_guard(
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
        "summary_schema_version": _size_guard_scalar(result_summary_obj.get("summary_schema_version") or "1.2", max_chars=20),
        "is_simulation": bool(result_summary_obj.get("is_simulation") or False),
        "completion_status": _size_guard_scalar(result_summary_obj.get("completion_status"), max_chars=40),
        "readiness": _size_guard_dict(result_summary_obj.get("readiness"), max_items=4, max_value_chars=40),
        "version": _size_guard_scalar(result_summary_obj.get("version"), max_chars=40),
        "strategy": _size_guard_scalar(result_summary_obj.get("strategy"), max_chars=80),
        "result_status": _size_guard_scalar(result_summary_obj.get("result_status"), max_chars=80),
        "counts": _size_guard_dict(result_summary_obj.get("counts"), max_items=20, max_value_chars=40),
        "time_cost_ms": _size_guard_scalar(result_summary_obj.get("time_cost_ms"), max_chars=40),
        "summary_truncated": True,
        "original_size_bytes": int(original_size),
    }

    if result_summary_obj.get("result_status_detail") is not None:
        minimal["result_status_detail"] = _size_guard_scalar(result_summary_obj.get("result_status_detail"), max_chars=200)
    if result_summary_obj.get("degraded_success") is not None:
        minimal["degraded_success"] = bool(result_summary_obj.get("degraded_success"))
    if result_summary_obj.get("invalid_due_count") is not None:
        minimal["invalid_due_count"] = _size_guard_scalar(result_summary_obj.get("invalid_due_count"), max_chars=40)
    if result_summary_obj.get("unscheduled_batch_count") is not None:
        minimal["unscheduled_batch_count"] = _size_guard_scalar(result_summary_obj.get("unscheduled_batch_count"), max_chars=40)
    if overdue_dict:
        minimal["overdue_batches"] = {"count": _size_guard_scalar(overdue_dict.get("count"), max_chars=40)}
    _copy_minimal_error_fields(minimal, result_summary_obj)
    _copy_minimal_missing_resource_fields(minimal, result_summary_obj)

    minimal_algo = _size_guard_dict(
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
    if _summary_size_bytes(minimal) <= SUMMARY_SIZE_LIMIT_BYTES:
        return minimal
    return {
        "summary_schema_version": "1.2",
        "summary_truncated": True,
        "original_size_bytes": int(original_size),
    }


def _algo_dict(result_summary_obj: Dict[str, Any]) -> Dict[str, Any]:
    algo = result_summary_obj.get("algo")
    return algo if isinstance(algo, dict) else {}


def _diagnostic_context(result_summary_obj: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Any]:
    diagnostics = result_summary_obj.get("diagnostics")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    optimizer_value = diagnostics_dict.get("optimizer")
    optimizer_diagnostics = optimizer_value if isinstance(optimizer_value, dict) else {}
    diagnostic_attempts = optimizer_diagnostics.get("attempts") if isinstance(optimizer_diagnostics, dict) else None
    return diagnostics_dict, optimizer_diagnostics, diagnostic_attempts


def _mark_diagnostics_truncated(state: _SizeGuardState) -> None:
    state.diagnostics_truncated = True
    state.result_summary_obj["diagnostics_truncated"] = True


def _prune_empty_diagnostics(result_summary_obj: Dict[str, Any], diagnostics_dict: Dict[str, Any]) -> None:
    optimizer = diagnostics_dict.get("optimizer")
    if isinstance(optimizer, dict) and not any(bool(value) for value in optimizer.values()):
        diagnostics_dict.pop("optimizer", None)
    if not any(bool(value) for value in diagnostics_dict.values()):
        result_summary_obj.pop("diagnostics", None)


def _trim_trace(algo_dict: Dict[str, Any], limit: int) -> None:
    trace = algo_dict.get("improvement_trace")
    if isinstance(trace, list):
        algo_dict["improvement_trace"] = trace[:limit]


def _trim_warnings(result_summary_obj: Dict[str, Any], limit: int) -> None:
    warnings = result_summary_obj.get("warnings")
    if isinstance(warnings, list):
        result_summary_obj["warnings"] = warnings[:limit]


def _trim_errors(result_summary_obj: Dict[str, Any], limit: int) -> None:
    public_error_details = result_summary_obj.get("public_error_details")
    errors = result_summary_obj.get("errors")
    if isinstance(public_error_details, list):
        result_summary_obj["public_error_details"] = _guarded_items(public_error_details, limit, _size_guard_public_error_detail)
        if len(public_error_details) > limit:
            result_summary_obj["errors_truncated"] = True
    if isinstance(errors, list):
        result_summary_obj["errors"] = [str(item)[:500] for item in errors[:limit]]
        if len(errors) > limit:
            result_summary_obj["errors_truncated"] = True


def _trim_missing_internal_resource_ops(result_summary_obj: Dict[str, Any], limit: int) -> None:
    items = result_summary_obj.get("missing_internal_resource_ops")
    if isinstance(items, list):
        result_summary_obj["missing_internal_resource_ops"] = _guarded_items(items, limit, _size_guard_missing_resource_item)
        if len(items) > limit:
            result_summary_obj["missing_internal_resource_ops_truncated"] = True


def _trim_attempts(algo_dict: Dict[str, Any], limit: int) -> None:
    attempts = algo_dict.get("attempts")
    if isinstance(attempts, list):
        algo_dict["attempts"] = attempts[:limit]


def _trim_best_batch_order(algo_dict: Dict[str, Any], limit: int) -> None:
    best_batch_order = algo_dict.get("best_batch_order")
    if isinstance(best_batch_order, list):
        algo_dict["best_batch_order"] = best_batch_order[:limit]


def _trim_selected_batch_ids(result_summary_obj: Dict[str, Any], limit: int) -> None:
    selected_batch_ids = result_summary_obj.get("selected_batch_ids")
    if isinstance(selected_batch_ids, list):
        result_summary_obj["selected_batch_ids"] = selected_batch_ids[:limit]


def _trim_overdue_items(result_summary_obj: Dict[str, Any], limit: int) -> None:
    overdue_batches = result_summary_obj.get("overdue_batches")
    overdue_items = overdue_batches.get("items") if isinstance(overdue_batches, dict) else None
    if isinstance(overdue_batches, dict) and isinstance(overdue_items, list):
        overdue_batches["items"] = overdue_items[:limit]


def _trim_diagnostic_attempts(
    state: _SizeGuardState,
    *,
    optimizer_diagnostics: Dict[str, Any],
    diagnostics_dict: Dict[str, Any],
    diagnostic_attempts: Any,
    limit: int,
) -> None:
    if isinstance(diagnostic_attempts, list) and len(diagnostic_attempts) > limit:
        optimizer_diagnostics["attempts"] = diagnostic_attempts[:limit]
        _mark_diagnostics_truncated(state)
        _prune_empty_diagnostics(state.result_summary_obj, diagnostics_dict)


def _apply_truncation_tiers(
    state: _SizeGuardState,
    *,
    algo_dict: Dict[str, Any],
    diagnostics_dict: Dict[str, Any],
    optimizer_diagnostics: Dict[str, Any],
    diagnostic_attempts: Any,
) -> Optional[Dict[str, Any]]:
    obj = state.result_summary_obj
    for tier in DEFAULT_TRUNCATION_TIERS:
        _trim_trace(algo_dict, tier.trace_limit)
        _trim_warnings(obj, tier.warning_limit)
        _trim_attempts(algo_dict, tier.attempt_limit)
        _trim_diagnostic_attempts(
            state,
            optimizer_diagnostics=optimizer_diagnostics,
            diagnostics_dict=diagnostics_dict,
            diagnostic_attempts=diagnostic_attempts,
            limit=tier.attempt_limit,
        )
        if tier.best_order_limit is not None:
            _trim_best_batch_order(algo_dict, tier.best_order_limit)
        if tier.selected_ids_limit is not None:
            _trim_selected_batch_ids(obj, tier.selected_ids_limit)
        if tier.overdue_items_limit is not None:
            _trim_overdue_items(obj, tier.overdue_items_limit)
        if tier.errors_limit is not None:
            _trim_errors(obj, tier.errors_limit)
        if tier.missing_resource_limit is not None:
            _trim_missing_internal_resource_ops(obj, tier.missing_resource_limit)
        obj["summary_truncated"] = True
        obj["original_size_bytes"] = int(state.original_size)
        if _summary_size_bytes(obj) <= SUMMARY_SIZE_LIMIT_BYTES:
            return obj
    return None


def _drop_diagnostic_fallback_samples(state: _SizeGuardState, *, optimizer_diagnostics: Dict[str, Any]) -> None:
    attempts_value = optimizer_diagnostics.get("attempts") if isinstance(optimizer_diagnostics, dict) else None
    if not isinstance(attempts_value, list):
        return
    changed = False
    for attempt in attempts_value:
        if not isinstance(attempt, dict):
            continue
        algo_stats = attempt.get("algo_stats")
        if isinstance(algo_stats, dict) and "fallback_samples" in algo_stats:
            algo_stats.pop("fallback_samples", None)
            changed = True
    if changed:
        _mark_diagnostics_truncated(state)


def _drop_diagnostic_field(
    state: _SizeGuardState,
    *,
    optimizer_diagnostics: Dict[str, Any],
    diagnostics_dict: Dict[str, Any],
    field: str,
) -> None:
    attempts_value = optimizer_diagnostics.get("attempts") if isinstance(optimizer_diagnostics, dict) else None
    if not isinstance(attempts_value, list):
        return
    changed = False
    for attempt in attempts_value:
        if isinstance(attempt, dict) and field in attempt:
            attempt.pop(field, None)
            changed = True
    if changed:
        _mark_diagnostics_truncated(state)
        _prune_empty_diagnostics(state.result_summary_obj, diagnostics_dict)


def _drop_optimizer_diagnostics(
    state: _SizeGuardState,
    *,
    diagnostics_dict: Dict[str, Any],
) -> None:
    if "optimizer" in diagnostics_dict:
        diagnostics_dict.pop("optimizer", None)
        _mark_diagnostics_truncated(state)
        _prune_empty_diagnostics(state.result_summary_obj, diagnostics_dict)


def _drop_all_diagnostics(state: _SizeGuardState) -> None:
    if "diagnostics" in state.result_summary_obj:
        state.result_summary_obj.pop("diagnostics", None)
        _mark_diagnostics_truncated(state)


def _apply_diagnostic_drop_sequence(
    state: _SizeGuardState,
    *,
    diagnostics_dict: Dict[str, Any],
    optimizer_diagnostics: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    actions = (
        lambda: _drop_diagnostic_fallback_samples(state, optimizer_diagnostics=optimizer_diagnostics),
        lambda: _drop_diagnostic_field(
            state,
            optimizer_diagnostics=optimizer_diagnostics,
            diagnostics_dict=diagnostics_dict,
            field="used_params",
        ),
        lambda: _drop_diagnostic_field(
            state,
            optimizer_diagnostics=optimizer_diagnostics,
            diagnostics_dict=diagnostics_dict,
            field="algo_stats",
        ),
        lambda: _drop_optimizer_diagnostics(state, diagnostics_dict=diagnostics_dict),
        lambda: _drop_all_diagnostics(state),
    )
    for trim_action in actions:
        trim_action()
        state.result_summary_obj["summary_truncated"] = True
        state.result_summary_obj["original_size_bytes"] = int(state.original_size)
        if state.diagnostics_truncated:
            state.result_summary_obj["diagnostics_truncated"] = True
        if _summary_size_bytes(state.result_summary_obj) <= SUMMARY_SIZE_LIMIT_BYTES:
            return state.result_summary_obj
    return None


def apply_summary_size_guard(result_summary_obj: Dict[str, Any]) -> Dict[str, Any]:
    original_size = _summary_size_bytes(result_summary_obj)
    if original_size <= SUMMARY_SIZE_LIMIT_BYTES:
        return result_summary_obj

    state = _SizeGuardState(result_summary_obj=result_summary_obj, original_size=int(original_size))
    algo_dict = _algo_dict(result_summary_obj)
    diagnostics_dict, optimizer_diagnostics, diagnostic_attempts = _diagnostic_context(result_summary_obj)

    truncated = _apply_truncation_tiers(
        state,
        algo_dict=algo_dict,
        diagnostics_dict=diagnostics_dict,
        optimizer_diagnostics=optimizer_diagnostics,
        diagnostic_attempts=diagnostic_attempts,
    )
    if truncated is not None:
        return truncated

    trimmed = _apply_diagnostic_drop_sequence(
        state,
        diagnostics_dict=diagnostics_dict,
        optimizer_diagnostics=optimizer_diagnostics,
    )
    if trimmed is not None:
        return trimmed

    return _minimal_summary_for_size_guard(
        result_summary_obj,
        original_size=int(original_size),
        diagnostics_truncated=bool(state.diagnostics_truncated),
    )
