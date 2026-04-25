from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot

from .schedule_summary_assembly import (
    _best_score_schema as best_score_schema,
)
from .schedule_summary_assembly import (
    _build_overdue_items as _build_overdue_items_impl,
)
from .schedule_summary_assembly import (
    _build_result_summary_obj,
)
from .schedule_summary_assembly import (
    _comparison_metric as comparison_metric,
)
from .schedule_summary_assembly import (
    _config_snapshot_dict as config_snapshot_dict,
)
from .schedule_summary_assembly import (
    _finish_time_by_batch as finish_time_by_batch,
)
from .schedule_summary_degradation import (
    _compute_downtime_degradation,
    _compute_resource_pool_degradation,
    _hard_constraints,
    _input_build_state,
    _metric_int,
    _metric_sample,
    _summary_degradation_state,
)
from .schedule_summary_freeze import (
    _compute_completion_status,
    _compute_result_status,
    _extract_freeze_warnings,
    _freeze_meta_dict,
    _frozen_batch_ids,
)
from .schedule_summary_types import (
    DEFAULT_TRUNCATION_TIERS,
    AlgorithmSummaryState,
    FallbackState,
    FreezeState,
    RuntimeState,
    SummaryBuildContext,
    WarningState,
)

__all__ = [
    "SUMMARY_SIZE_LIMIT_BYTES",
    "apply_summary_size_guard",
    "best_score_schema",
    "build_overdue_items",
    "cfg_value",
    "comparison_metric",
    "config_snapshot_dict",
    "due_exclusive",
    "finish_time_by_batch",
    "serialize_end_date",
    "build_result_summary",
]

SUMMARY_SIZE_LIMIT_BYTES = 512 * 1024


def cfg_value(cfg: Any, key: str, default: Any = None) -> Any:
    value = _config_snapshot_value(cfg, key)
    return default if value is None else value


def _config_snapshot_value(cfg: Any, key: str) -> Any:
    snapshot = ensure_schedule_config_snapshot(
        cfg,
        strict_mode=False,
        source="scheduler.summary.cfg_value",
    )
    return snapshot.to_dict().get(str(key or "").strip())



def serialize_end_date(end_date: Optional[Any]) -> Optional[str]:
    if end_date is None:
        return None
    if isinstance(end_date, str):
        text = end_date.strip()
        return text if text else None
    try:
        isoformat = getattr(end_date, "isoformat", None)
        if callable(isoformat):
            return str(isoformat())
    except Exception:
        pass
    text = str(end_date).strip()
    return text if text else None


def due_exclusive(due_date) -> datetime:
    if not due_date:
        return datetime.max
    return datetime(due_date.year, due_date.month, due_date.day) + timedelta(days=1)


def _warning_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, dict):
        raw_items = [value]
    elif isinstance(value, list):
        raw_items = value
    elif isinstance(value, tuple):
        raw_items = list(value)
    else:
        try:
            raw_items = list(value)
        except Exception:
            raw_items = [value]

    out: List[str] = []
    for item in raw_items:
        try:
            text = str(item)
        except Exception:
            continue
        if text:
            out.append(text)
    return out


def _merge_warning_lists(primary: Any, extra: Any) -> List[str]:
    merged = _warning_list(primary)
    seen = set(merged)
    for text in _warning_list(extra):
        if text in seen:
            continue
        seen.add(text)
        merged.append(text)
    return merged


def _dedupe_text_list(values: Any) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in values or []:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _append_summary_warning(summary: Any, message: str) -> bool:
    if isinstance(summary, dict):
        warnings = _warning_list(summary.get("warnings"))
        warnings.append(message)
        summary["warnings"] = warnings
        return True

    warnings = getattr(summary, "warnings", None)
    if isinstance(warnings, list):
        warnings.append(message)
        return True

    normalized_warnings = _warning_list(warnings)
    normalized_warnings.append(message)
    try:
        summary.warnings = normalized_warnings
        return True
    except Exception:
        return False


def _counter_dict(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, int] = {}
    for key, raw in value.items():
        try:
            count = int(raw)
        except Exception:
            continue
        if count != 0:
            out[str(key)] = int(count)
    return out


def _fallback_samples_dict(value: Any) -> Dict[str, List[Dict[str, Any]]]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, List[Dict[str, Any]]] = {}
    for key, raw in value.items():
        if not isinstance(raw, list):
            continue
        samples: List[Dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                samples.append(dict(item))
        if samples:
            out[str(key)] = samples
    return out


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


def build_overdue_items(
    svc,
    *,
    batches: Dict[str, Any],
    finish_by_batch: Dict[str, datetime],
    summary: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    return _build_overdue_items_impl(
        svc,
        batches=batches,
        finish_by_batch=finish_by_batch,
        summary=summary,
        due_exclusive_fn=due_exclusive,
        append_summary_warning_fn=_append_summary_warning,
    )


def _build_runtime_state(
    *,
    svc,
    batches: Dict[str, Any],
    results: List[Any],
    summary: Any,
    best_metrics: Optional[Any],
) -> RuntimeState:
    finish_by_batch = finish_time_by_batch(results)
    overdue_items, overdue_meta = build_overdue_items(svc, batches=batches, finish_by_batch=finish_by_batch, summary=summary)
    invalid_due_count = _metric_int(best_metrics, "invalid_due_count") or int(overdue_meta.get("invalid_due_count") or 0)
    invalid_due_batch_ids_sample = _metric_sample(best_metrics, "invalid_due_batch_ids_sample", limit=10) or list(
        overdue_meta.get("invalid_due_batch_ids_sample") or []
    )
    unscheduled_batch_ids_all = [
        str(batch_id).strip()
        for batch_id in sorted(batches.keys(), key=lambda item: str(item).strip())
        if str(batch_id).strip() and str(batch_id).strip() not in finish_by_batch
    ]
    unscheduled_batch_count = _metric_int(best_metrics, "unscheduled_batch_count") or int(len(unscheduled_batch_ids_all))
    unscheduled_batch_ids_sample = _metric_sample(best_metrics, "unscheduled_batch_ids_sample", limit=20) or list(
        unscheduled_batch_ids_all[:20]
    )
    return RuntimeState(
        finish_by_batch=finish_by_batch,
        overdue_items=overdue_items,
        invalid_due_count=int(invalid_due_count),
        invalid_due_batch_ids_sample=list(invalid_due_batch_ids_sample),
        unscheduled_batch_count=int(unscheduled_batch_count),
        unscheduled_batch_ids_sample=list(unscheduled_batch_ids_sample),
    )


def _build_warning_state(
    *,
    summary: Any,
    algo_warnings: Optional[List[str]],
    input_state: Dict[str, Any],
    runtime_state: RuntimeState,
) -> WarningState:
    summary_warnings = _warning_list(getattr(summary, "warnings", None))
    algo_warning_list = _warning_list(algo_warnings)
    all_warnings = _merge_warning_lists(summary_warnings, algo_warning_list)
    merge_context_degraded = bool(input_state.get("merge_context_degraded"))
    merge_context_events = list(input_state.get("merge_context_events") or [])
    if int(runtime_state.unscheduled_batch_count) > 0:
        sample_text = "、".join(list(runtime_state.unscheduled_batch_ids_sample or [])[:10])
        all_warnings = _merge_warning_lists(
            all_warnings,
            [f"存在 {int(runtime_state.unscheduled_batch_count)} 个批次未形成完工结果（示例批次：{sample_text}）。"],
        )
    return WarningState(
        summary_warnings=summary_warnings,
        algo_warning_list=algo_warning_list,
        all_warnings=all_warnings,
        merge_context_degraded=merge_context_degraded,
        merge_context_events=merge_context_events,
    )


def _build_freeze_state(
    *,
    cfg: Any,
    frozen_op_ids: Set[int],
    freeze_meta: Optional[Dict[str, Any]],
    all_warnings: List[str],
) -> FreezeState:
    freeze_warnings = _extract_freeze_warnings(all_warnings)
    freeze_data = _freeze_meta_dict(
        cfg,
        frozen_op_ids=frozen_op_ids,
        freeze_meta=freeze_meta,
        freeze_warnings=freeze_warnings,
    )
    merged_warnings = list(all_warnings)
    if (
        freeze_warnings
        and str(freeze_data.get("freeze_state") or "") == "degraded"
        and not bool(freeze_data.get("degradation_from_warning_fallback"))
    ):
        freeze_warning_set = {str(item) for item in freeze_warnings}
        merged_warnings = [item for item in merged_warnings if str(item) not in freeze_warning_set]
    return FreezeState(
        data=freeze_data,
        all_warnings=merged_warnings,
    )


def _build_fallback_state(algo_stats: Optional[Dict[str, Any]]) -> FallbackState:
    algo_stats_dict = algo_stats if isinstance(algo_stats, dict) else {}
    fallback_counts = _counter_dict(algo_stats_dict.get("fallback_counts"))
    fallback_samples = _fallback_samples_dict(algo_stats_dict.get("fallback_samples"))
    param_fallbacks = _counter_dict(algo_stats_dict.get("param_fallbacks"))
    return FallbackState(
        raw_stats=algo_stats_dict,
        fallback_counts=fallback_counts,
        fallback_samples=fallback_samples,
        param_fallbacks=param_fallbacks,
        legacy_external_days_defaulted_count=int(fallback_counts.get("legacy_external_days_defaulted_count") or 0),
        ortools_warmstart_failed_count=int(fallback_counts.get("ortools_warmstart_failed_count") or 0),
    )


def _merge_fallback_warnings(all_warnings: List[str], fallback_state: FallbackState) -> List[str]:
    legacy_count = int(fallback_state.legacy_external_days_defaulted_count)
    warmstart_count = int(fallback_state.ortools_warmstart_failed_count)
    if legacy_count > 0:
        all_warnings = _merge_warning_lists(all_warnings, [f"存在 {legacy_count} 道外协工序使用了历史兼容周期 1.0 天。"])
    if warmstart_count > 0:
        all_warnings = _merge_warning_lists(all_warnings, ["OR-Tools 预热失败，已回退到常规求解路径。"])
    return all_warnings


def _degraded_cause_codes(
    *,
    summary_degradation: Dict[str, Any],
) -> List[str]:
    causes: List[str] = []
    summary_events = summary_degradation.get("events") if isinstance(summary_degradation, dict) else None
    for raw_event in summary_events or ():
        if not isinstance(raw_event, dict):
            continue
        code = str(raw_event.get("code") or "").strip()
        if code in {
            "config_fallback",
            "input_fallback",
            "freeze_window_degraded",
            "downtime_avoid_degraded",
            "resource_pool_degraded",
            "merge_context_degraded",
            "summary_merge_failed",
        }:
            causes.append(code)
    return _dedupe_text_list(causes)


def _degraded_success_state(
    *,
    summary_degradation: Dict[str, Any],
    result_status: str,
) -> Tuple[bool, List[str]]:
    deduped = _degraded_cause_codes(
        summary_degradation=summary_degradation,
    )
    return result_status == "success" and bool(deduped), deduped


def build_result_summary(
    svc=None,
    *,
    ctx: Optional[SummaryBuildContext] = None,
    **kwargs,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any], str, int]:
    ctx_kwargs = dict(kwargs)
    if svc is None:
        svc = ctx_kwargs.pop("svc", None)
    else:
        ctx_kwargs.pop("svc", None)
    if ctx is None:
        ctx = SummaryBuildContext(**ctx_kwargs)
    else:
        if ctx_kwargs:
            ctx = replace(ctx, **ctx_kwargs)
    if svc is None:
        raise TypeError("build_result_summary() 缺少必需参数：svc")
    ctx = replace(
        ctx,
        cfg=ensure_schedule_config_snapshot(
            ctx.cfg,
            strict_mode=False,
            source="scheduler.summary",
        ),
    )

    runtime_state = _build_runtime_state(
        svc=svc,
        batches=ctx.batches,
        results=ctx.results,
        summary=ctx.summary,
        best_metrics=ctx.best_metrics,
    )
    result_status = _compute_result_status(ctx.summary, simulate=ctx.simulate)
    completion_status = _compute_completion_status(ctx.summary)
    time_cost_ms = int((time.time() - float(ctx.t0)) * 1000)
    frozen_batch_ids = _frozen_batch_ids(ctx.operations, frozen_op_ids=ctx.frozen_op_ids)
    input_state = _input_build_state(ctx.input_build_outcome)
    warning_state = _build_warning_state(
        summary=ctx.summary,
        algo_warnings=ctx.algo_warnings,
        input_state=input_state,
        runtime_state=runtime_state,
    )
    freeze_state = _build_freeze_state(
        cfg=ctx.cfg,
        frozen_op_ids=ctx.frozen_op_ids,
        freeze_meta=ctx.freeze_meta,
        all_warnings=list(warning_state.all_warnings),
    )
    downtime_state = _compute_downtime_degradation(ctx.cfg, downtime_meta=ctx.downtime_meta)
    resource_pool_enabled, resource_pool_degraded, resource_pool_degradation_reason, resource_pool_attempted = _compute_resource_pool_degradation(
        ctx.cfg, resource_pool_meta=ctx.resource_pool_meta
    )
    hard_constraints = _hard_constraints(
        ctx.cfg,
        downtime_degraded=bool(downtime_state.get("downtime_degraded")),
        freeze_applied=bool(freeze_state.data.get("freeze_applied")),
    )
    fallback_state = _build_fallback_state(ctx.algo_stats)
    freeze_state = replace(
        freeze_state,
        all_warnings=_merge_fallback_warnings(freeze_state.all_warnings, fallback_state),
    )
    warning_pipeline = ctx.warning_merge_status if isinstance(ctx.warning_merge_status, dict) else {}
    summary_degradation = _summary_degradation_state(
        cfg=ctx.cfg,
        input_state=input_state,
        invalid_due_count=runtime_state.invalid_due_count,
        invalid_due_batch_ids_sample=runtime_state.invalid_due_batch_ids_sample,
        legacy_external_days_defaulted_count=fallback_state.legacy_external_days_defaulted_count,
        freeze_state=freeze_state.data,
        downtime_state=downtime_state,
        resource_pool_enabled=resource_pool_enabled,
        resource_pool_degraded=resource_pool_degraded,
        resource_pool_degradation_reason=resource_pool_degradation_reason,
        ortools_warmstart_failed_count=fallback_state.ortools_warmstart_failed_count,
        merge_context_degraded=warning_state.merge_context_degraded,
        warning_merge_status=warning_pipeline,
    )
    degraded_success, degraded_causes = _degraded_success_state(
        summary_degradation=summary_degradation,
        result_status=result_status,
    )
    algorithm_state = AlgorithmSummaryState(
        ctx=ctx,
        input_state=input_state,
        downtime_state=downtime_state,
        hard_constraints=hard_constraints,
        warning_state=warning_state,
        freeze_state=freeze_state,
        frozen_batch_ids=frozen_batch_ids,
        resource_pool_meta=ctx.resource_pool_meta,
        resource_pool_enabled=resource_pool_enabled,
        resource_pool_degraded=resource_pool_degraded,
        resource_pool_degradation_reason=resource_pool_degradation_reason,
        resource_pool_attempted=resource_pool_attempted,
        warning_pipeline=warning_pipeline,
        fallback_state=fallback_state,
    )
    result_summary_obj = _build_result_summary_obj(
        svc,
        ctx=ctx,
        runtime_state=runtime_state,
        freeze_state=freeze_state,
        fallback_state=fallback_state,
        algorithm_state=algorithm_state,
        summary_degradation=summary_degradation,
        degraded_success=degraded_success,
        degraded_causes=degraded_causes,
        completion_status=completion_status,
        time_cost_ms=time_cost_ms,
        serialize_end_date_fn=serialize_end_date,
    )
    result_summary_obj = apply_summary_size_guard(result_summary_obj)
    result_summary_json = json.dumps(result_summary_obj, ensure_ascii=False)
    return runtime_state.overdue_items, result_status, result_summary_obj, result_summary_json, time_cost_ms
