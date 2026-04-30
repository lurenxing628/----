from __future__ import annotations

import json
import time
from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple

from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot

from .schedule_summary_assembly import (
    _best_score_schema as best_score_schema,
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
    _summary_degradation_state,
)
from .schedule_summary_freeze import (
    _compute_completion_status,
    _compute_result_status,
    _frozen_batch_ids,
)
from .schedule_summary_types import (
    AlgorithmSummaryState,
    SummaryBuildContext,
)
from .summary_runtime_state import (
    _build_fallback_state,
    _build_freeze_state,
    _build_runtime_state,
    _build_warning_state,
    _degraded_success_state,
    _merge_fallback_warnings,
    build_overdue_items,
    due_exclusive,
)
from .summary_size_guard import (
    SUMMARY_SIZE_LIMIT_BYTES,
    apply_summary_size_guard,
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
