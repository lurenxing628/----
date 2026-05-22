from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .schedule_summary_types import DEFAULT_TRUNCATION_TIERS
from .summary_size_guard_fields import (
    SUMMARY_SIZE_LIMIT_BYTES,
    guarded_items,
    minimal_summary_for_size_guard,
    positive_int,
    size_guard_missing_resource_item,
    size_guard_public_error_detail,
    summary_size_bytes,
    warning_sample,
)


@dataclass
class _SizeGuardState:
    result_summary_obj: Dict[str, Any]
    original_size: int
    diagnostics_truncated: bool = False


def _remember_warning_summary(result_summary_obj: Dict[str, Any], warnings: List[Any], *, limit: int) -> None:
    warning_count = max(positive_int(result_summary_obj.get("warning_count")), len(warnings))
    if warning_count <= 0:
        return
    result_summary_obj["warning_count"] = int(warning_count)
    if warning_count > limit:
        result_summary_obj["warnings_truncated"] = True
        sample = warning_sample(result_summary_obj.get("warnings_sample")) or warning_sample(warnings)
        if sample and not result_summary_obj.get("warnings_sample"):
            result_summary_obj["warnings_sample"] = sample


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
        _remember_warning_summary(result_summary_obj, warnings, limit=limit)
        result_summary_obj["warnings"] = warnings[:limit]


def _trim_errors(result_summary_obj: Dict[str, Any], limit: int) -> None:
    public_error_details = result_summary_obj.get("public_error_details")
    errors = result_summary_obj.get("errors")
    if isinstance(public_error_details, list):
        result_summary_obj["public_error_details"] = guarded_items(public_error_details, limit, size_guard_public_error_detail)
        if len(public_error_details) > limit:
            result_summary_obj["errors_truncated"] = True
    if isinstance(errors, list):
        result_summary_obj["errors"] = [str(item)[:500] for item in errors[:limit]]
        if len(errors) > limit:
            result_summary_obj["errors_truncated"] = True


def _trim_missing_internal_resource_ops(result_summary_obj: Dict[str, Any], limit: int) -> None:
    items = result_summary_obj.get("missing_internal_resource_ops")
    if isinstance(items, list):
        result_summary_obj["missing_internal_resource_ops"] = guarded_items(items, limit, size_guard_missing_resource_item)
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
        if summary_size_bytes(obj) <= SUMMARY_SIZE_LIMIT_BYTES:
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
        if summary_size_bytes(state.result_summary_obj) <= SUMMARY_SIZE_LIMIT_BYTES:
            return state.result_summary_obj
    return None


def apply_summary_size_guard(result_summary_obj: Dict[str, Any]) -> Dict[str, Any]:
    original_size = summary_size_bytes(result_summary_obj)
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

    return minimal_summary_for_size_guard(
        result_summary_obj,
        original_size=int(original_size),
        diagnostics_truncated=bool(state.diagnostics_truncated),
    )
