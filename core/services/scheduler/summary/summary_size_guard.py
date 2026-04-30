from __future__ import annotations

import json
from typing import Any, Dict

from .schedule_summary_types import DEFAULT_TRUNCATION_TIERS

SUMMARY_SIZE_LIMIT_BYTES = 512 * 1024


def _summary_size_bytes(obj: Dict[str, Any]) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def _size_guard_scalar(value: Any, *, max_chars: int = 200) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    return text[:max_chars]


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


def apply_summary_size_guard(result_summary_obj: Dict[str, Any]) -> Dict[str, Any]:
    original_size = _summary_size_bytes(result_summary_obj)
    if original_size <= SUMMARY_SIZE_LIMIT_BYTES:
        return result_summary_obj

    algo = result_summary_obj.get("algo")
    algo_dict = algo if isinstance(algo, dict) else {}
    trace = algo_dict.get("improvement_trace")
    warnings = result_summary_obj.get("warnings")
    attempts = algo_dict.get("attempts")
    best_batch_order = algo_dict.get("best_batch_order")
    selected_batch_ids = result_summary_obj.get("selected_batch_ids")
    overdue_batches = result_summary_obj.get("overdue_batches")
    overdue_items = overdue_batches.get("items") if isinstance(overdue_batches, dict) else None
    diagnostics = result_summary_obj.get("diagnostics")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    optimizer_diagnostics = diagnostics_dict.get("optimizer") if isinstance(diagnostics_dict.get("optimizer"), dict) else {}
    diagnostic_attempts = optimizer_diagnostics.get("attempts") if isinstance(optimizer_diagnostics, dict) else None
    diagnostics_truncated = False

    def _mark_diagnostics_truncated() -> None:
        nonlocal diagnostics_truncated
        diagnostics_truncated = True
        result_summary_obj["diagnostics_truncated"] = True

    def _prune_empty_diagnostics() -> None:
        if not isinstance(diagnostics_dict, dict):
            return
        optimizer = diagnostics_dict.get("optimizer")
        if isinstance(optimizer, dict) and not any(bool(value) for value in optimizer.values()):
            diagnostics_dict.pop("optimizer", None)
        if not any(bool(value) for value in diagnostics_dict.values()):
            result_summary_obj.pop("diagnostics", None)

    def _trim_trace(limit: int) -> None:
        if isinstance(trace, list):
            algo_dict["improvement_trace"] = trace[:limit]

    def _trim_warnings(limit: int) -> None:
        if isinstance(warnings, list):
            result_summary_obj["warnings"] = warnings[:limit]

    def _trim_attempts(limit: int) -> None:
        if isinstance(attempts, list):
            algo_dict["attempts"] = attempts[:limit]

    def _trim_best_batch_order(limit: int) -> None:
        if isinstance(best_batch_order, list):
            algo_dict["best_batch_order"] = best_batch_order[:limit]

    def _trim_selected_batch_ids(limit: int) -> None:
        if isinstance(selected_batch_ids, list):
            result_summary_obj["selected_batch_ids"] = selected_batch_ids[:limit]

    def _trim_overdue_items(limit: int) -> None:
        if isinstance(overdue_batches, dict) and isinstance(overdue_items, list):
            overdue_batches["items"] = overdue_items[:limit]

    def _trim_diagnostic_attempts(limit: int) -> None:
        if not isinstance(optimizer_diagnostics, dict) or not isinstance(diagnostic_attempts, list):
            return
        if len(diagnostic_attempts) > limit:
            optimizer_diagnostics["attempts"] = diagnostic_attempts[:limit]
            _mark_diagnostics_truncated()
            _prune_empty_diagnostics()

    def _drop_diagnostic_fallback_samples() -> None:
        if not isinstance(optimizer_diagnostics, dict):
            return
        attempts_value = optimizer_diagnostics.get("attempts")
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
            _mark_diagnostics_truncated()

    def _drop_diagnostic_field(field: str) -> None:
        if not isinstance(optimizer_diagnostics, dict):
            return
        attempts_value = optimizer_diagnostics.get("attempts")
        if not isinstance(attempts_value, list):
            return
        changed = False
        for attempt in attempts_value:
            if isinstance(attempt, dict) and field in attempt:
                attempt.pop(field, None)
                changed = True
        if changed:
            _mark_diagnostics_truncated()
            _prune_empty_diagnostics()

    def _drop_optimizer_diagnostics() -> None:
        if isinstance(diagnostics_dict, dict) and "optimizer" in diagnostics_dict:
            diagnostics_dict.pop("optimizer", None)
            _mark_diagnostics_truncated()
            _prune_empty_diagnostics()

    def _drop_all_diagnostics() -> None:
        if "diagnostics" not in result_summary_obj:
            return
        result_summary_obj.pop("diagnostics", None)
        _mark_diagnostics_truncated()

    for tier in DEFAULT_TRUNCATION_TIERS:
        _trim_trace(tier.trace_limit)
        _trim_warnings(tier.warning_limit)
        _trim_attempts(tier.attempt_limit)
        _trim_diagnostic_attempts(tier.attempt_limit)
        if tier.best_order_limit is not None:
            _trim_best_batch_order(tier.best_order_limit)
        if tier.selected_ids_limit is not None:
            _trim_selected_batch_ids(tier.selected_ids_limit)
        if tier.overdue_items_limit is not None:
            _trim_overdue_items(tier.overdue_items_limit)
        result_summary_obj["summary_truncated"] = True
        result_summary_obj["original_size_bytes"] = int(original_size)
        if _summary_size_bytes(result_summary_obj) <= SUMMARY_SIZE_LIMIT_BYTES:
            return result_summary_obj

    for trim_action in (
        _drop_diagnostic_fallback_samples,
        lambda: _drop_diagnostic_field("used_params"),
        lambda: _drop_diagnostic_field("algo_stats"),
        _drop_optimizer_diagnostics,
        _drop_all_diagnostics,
    ):
        trim_action()
        result_summary_obj["summary_truncated"] = True
        result_summary_obj["original_size_bytes"] = int(original_size)
        if diagnostics_truncated:
            result_summary_obj["diagnostics_truncated"] = True
        if _summary_size_bytes(result_summary_obj) <= SUMMARY_SIZE_LIMIT_BYTES:
            return result_summary_obj

    return _minimal_summary_for_size_guard(
        result_summary_obj,
        original_size=int(original_size),
        diagnostics_truncated=bool(diagnostics_truncated),
    )
