from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.services.scheduler.contracts.schedule_summary_types import DEFAULT_TRUNCATION_TIERS

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
    diagnostic_attempts = optimizer_diagnostics.get("attempts")
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


def _trim_trace(algo_dict: Dict[str, Any], limit: int) -> bool:
    trace = algo_dict.get("improvement_trace")
    if isinstance(trace, list) and len(trace) > limit:
        algo_dict["improvement_trace"] = trace[:limit]
        return True
    return False


def _trim_warnings(result_summary_obj: Dict[str, Any], limit: int) -> bool:
    warnings = result_summary_obj.get("warnings")
    if isinstance(warnings, list):
        _remember_warning_summary(result_summary_obj, warnings, limit=limit)
        if len(warnings) > limit:
            result_summary_obj["warnings"] = warnings[:limit]
            return True
    return False


def _trim_errors(result_summary_obj: Dict[str, Any], limit: int) -> bool:
    public_error_details = result_summary_obj.get("public_error_details")
    errors = result_summary_obj.get("errors")
    changed = False
    if isinstance(public_error_details, list) and public_error_details:
        trimmed_details = guarded_items(public_error_details, limit, size_guard_public_error_detail)
        if trimmed_details != public_error_details:
            result_summary_obj["public_error_details"] = trimmed_details
            changed = True
        if len(public_error_details) > limit:
            result_summary_obj["errors_truncated"] = True
            changed = True
    if isinstance(errors, list) and errors:
        trimmed_errors = [str(item)[:500] for item in errors[:limit]]
        if trimmed_errors != errors:
            result_summary_obj["errors"] = trimmed_errors
            changed = True
        if len(errors) > limit:
            result_summary_obj["errors_truncated"] = True
            changed = True
    return changed


def _trim_missing_internal_resource_ops(result_summary_obj: Dict[str, Any], limit: int) -> bool:
    items = result_summary_obj.get("missing_internal_resource_ops")
    if isinstance(items, list) and items:
        trimmed_items = guarded_items(items, limit, size_guard_missing_resource_item)
        changed = trimmed_items != items
        if changed:
            result_summary_obj["missing_internal_resource_ops"] = trimmed_items
        if len(items) > limit:
            result_summary_obj["missing_internal_resource_ops_truncated"] = True
            changed = True
        return changed
    return False


def _trim_attempts(algo_dict: Dict[str, Any], limit: int) -> bool:
    attempts = algo_dict.get("attempts")
    if isinstance(attempts, list) and len(attempts) > limit:
        algo_dict["attempts"] = attempts[:limit]
        return True
    return False


def _trim_selected_batch_ids(result_summary_obj: Dict[str, Any], limit: int) -> bool:
    selected_batch_ids = result_summary_obj.get("selected_batch_ids")
    if isinstance(selected_batch_ids, list) and len(selected_batch_ids) > limit:
        result_summary_obj["selected_batch_ids"] = selected_batch_ids[:limit]
        return True
    return False


def _trim_overdue_items(result_summary_obj: Dict[str, Any], limit: int) -> bool:
    overdue_batches = result_summary_obj.get("overdue_batches")
    overdue_items = overdue_batches.get("items") if isinstance(overdue_batches, dict) else None
    if isinstance(overdue_batches, dict) and isinstance(overdue_items, list) and len(overdue_items) > limit:
        overdue_batches["items"] = overdue_items[:limit]
        return True
    return False


def _trim_near_due_items(result_summary_obj: Dict[str, Any], limit: int) -> bool:
    near_due_batches = result_summary_obj.get("near_due_batches")
    near_due_items = near_due_batches.get("items") if isinstance(near_due_batches, dict) else None
    if isinstance(near_due_batches, dict) and isinstance(near_due_items, list) and len(near_due_items) > limit:
        near_due_batches["items"] = near_due_items[:limit]
        return True
    return False


def _trim_incomplete_items(result_summary_obj: Dict[str, Any], limit: int) -> bool:
    incomplete_batches = result_summary_obj.get("incomplete_batches")
    incomplete_items = incomplete_batches.get("items") if isinstance(incomplete_batches, dict) else None
    if isinstance(incomplete_batches, dict) and isinstance(incomplete_items, list) and len(incomplete_items) > limit:
        incomplete_batches["items"] = incomplete_items[:limit]
        return True
    return False


def _trim_diagnostic_attempts(
    state: _SizeGuardState,
    *,
    optimizer_diagnostics: Dict[str, Any],
    diagnostics_dict: Dict[str, Any],
    diagnostic_attempts: Any,
    limit: int,
) -> bool:
    current_attempts = optimizer_diagnostics.get("attempts", diagnostic_attempts)
    if isinstance(current_attempts, list) and len(current_attempts) > limit:
        optimizer_diagnostics["attempts"] = current_attempts[:limit]
        _mark_diagnostics_truncated(state)
        _prune_empty_diagnostics(state.result_summary_obj, diagnostics_dict)
        return True
    return False


def _apply_truncation_tiers(
    state: _SizeGuardState,
    *,
    algo_dict: Dict[str, Any],
    diagnostics_dict: Dict[str, Any],
    optimizer_diagnostics: Dict[str, Any],
    diagnostic_attempts: Any,
) -> Optional[Dict[str, Any]]:
    obj = state.result_summary_obj
    obj["summary_truncated"] = True
    obj["original_size_bytes"] = int(state.original_size)
    for tier in DEFAULT_TRUNCATION_TIERS:
        changed = False
        changed = _trim_trace(algo_dict, tier.trace_limit) or changed
        changed = _trim_warnings(obj, tier.warning_limit) or changed
        changed = _trim_attempts(algo_dict, tier.attempt_limit) or changed
        changed = (
            _trim_diagnostic_attempts(
                state,
                optimizer_diagnostics=optimizer_diagnostics,
                diagnostics_dict=diagnostics_dict,
                diagnostic_attempts=diagnostic_attempts,
                limit=tier.attempt_limit,
            )
            or changed
        )
        if tier.selected_ids_limit is not None:
            changed = _trim_selected_batch_ids(obj, tier.selected_ids_limit) or changed
        if tier.overdue_items_limit is not None:
            changed = _trim_overdue_items(obj, tier.overdue_items_limit) or changed
            changed = _trim_incomplete_items(obj, tier.overdue_items_limit) or changed
        if tier.near_due_items_limit is not None:
            changed = _trim_near_due_items(obj, tier.near_due_items_limit) or changed
        if tier.errors_limit is not None:
            changed = _trim_errors(obj, tier.errors_limit) or changed
        if tier.missing_resource_limit is not None:
            changed = _trim_missing_internal_resource_ops(obj, tier.missing_resource_limit) or changed
        if changed and summary_size_bytes(obj) <= SUMMARY_SIZE_LIMIT_BYTES:
            return obj
    return None


def _drop_diagnostic_fallback_samples(state: _SizeGuardState, *, optimizer_diagnostics: Dict[str, Any]) -> bool:
    attempts_value = optimizer_diagnostics.get("attempts")
    if not isinstance(attempts_value, list):
        return False
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
    return changed


def _drop_diagnostic_field(
    state: _SizeGuardState,
    *,
    optimizer_diagnostics: Dict[str, Any],
    diagnostics_dict: Dict[str, Any],
    field: str,
) -> bool:
    attempts_value = optimizer_diagnostics.get("attempts")
    if not isinstance(attempts_value, list):
        return False
    changed = False
    for attempt in attempts_value:
        if isinstance(attempt, dict) and field in attempt:
            attempt.pop(field, None)
            changed = True
    if changed:
        _mark_diagnostics_truncated(state)
        _prune_empty_diagnostics(state.result_summary_obj, diagnostics_dict)
    return changed


def _drop_optimizer_diagnostics(
    state: _SizeGuardState,
    *,
    diagnostics_dict: Dict[str, Any],
) -> bool:
    if "optimizer" in diagnostics_dict:
        diagnostics_dict.pop("optimizer", None)
        _mark_diagnostics_truncated(state)
        _prune_empty_diagnostics(state.result_summary_obj, diagnostics_dict)
        return True
    return False


def _drop_all_diagnostics(state: _SizeGuardState) -> bool:
    if "diagnostics" in state.result_summary_obj:
        state.result_summary_obj.pop("diagnostics", None)
        _mark_diagnostics_truncated(state)
        return True
    return False


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
    state.result_summary_obj["summary_truncated"] = True
    state.result_summary_obj["original_size_bytes"] = int(state.original_size)
    for trim_action in actions:
        changed = trim_action()
        if state.diagnostics_truncated:
            state.result_summary_obj["diagnostics_truncated"] = True
        if changed and summary_size_bytes(state.result_summary_obj) <= SUMMARY_SIZE_LIMIT_BYTES:
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
