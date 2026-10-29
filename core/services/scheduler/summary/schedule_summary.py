from __future__ import annotations

import time
from typing import Any, Dict

from core.services.scheduler.contracts.schedule_summary_types import (
    AlgorithmSummaryState,
    SummaryBuildContext,
)

from .schedule_summary_assembly import _build_result_summary_obj
from .schedule_summary_degradation import (
    _compute_resource_pool_state,
    _hard_constraints,
    _summary_degradation_state,
)
from .schedule_summary_freeze import (
    _compute_completion_status,
    _freeze_meta_dict,
    _frozen_batch_ids,
)
from .summary_runtime_state import (
    _build_fallback_state,
    _build_runtime_state,
    _build_summary_warnings,
    _merge_fallback_warnings,
)

__all__ = ["build_result_summary"]


def build_result_summary(*, ctx: SummaryBuildContext) -> Dict[str, Any]:
    runtime_state = _build_runtime_state(
        batches=ctx.batches,
        results=ctx.results,
        summary=ctx.summary,
        best_metrics=ctx.best_metrics,
    )
    completion_status = _compute_completion_status(ctx.summary)
    time_cost_ms = int((time.time() - float(ctx.t0)) * 1000)
    frozen_batch_ids = _frozen_batch_ids(ctx.operations, frozen_op_ids=ctx.frozen_op_ids)
    warnings = _build_summary_warnings(summary=ctx.summary, runtime_state=runtime_state)
    freeze_state = _freeze_meta_dict(ctx.freeze_meta)
    resource_pool_enabled, resource_pool_attempted = _compute_resource_pool_state(
        ctx.cfg, resource_pool_meta=ctx.resource_pool_meta
    )
    hard_constraints = _hard_constraints(freeze_applied=bool(freeze_state.get("freeze_applied")))
    fallback_state = _build_fallback_state(ctx.algo_stats)
    warnings = _merge_fallback_warnings(warnings, fallback_state)
    summary_degradation = _summary_degradation_state(
        invalid_due_count=runtime_state.invalid_due_count,
        invalid_due_batch_ids_sample=runtime_state.invalid_due_batch_ids_sample,
        ortools_warmstart_failed_count=fallback_state.ortools_warmstart_failed_count,
    )
    algorithm_state = AlgorithmSummaryState(
        ctx=ctx,
        hard_constraints=hard_constraints,
        freeze_state=freeze_state,
        frozen_batch_ids=frozen_batch_ids,
        resource_pool_meta=ctx.resource_pool_meta,
        resource_pool_enabled=resource_pool_enabled,
        resource_pool_attempted=resource_pool_attempted,
        fallback_state=fallback_state,
    )
    result_summary_obj = _build_result_summary_obj(
        ctx=ctx,
        runtime_state=runtime_state,
        warnings=warnings,
        algorithm_state=algorithm_state,
        summary_degradation=summary_degradation,
        completion_status=completion_status,
        time_cost_ms=time_cost_ms,
    )
    return result_summary_obj
