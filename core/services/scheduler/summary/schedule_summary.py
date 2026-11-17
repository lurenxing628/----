from __future__ import annotations

import time
from typing import Any, Dict

from core.services.scheduler.contracts.schedule_summary_types import (
    AlgorithmSummaryState,
    SummaryBuildContext,
)

from .schedule_summary_assembly import build_result_summary_obj
from .schedule_summary_degradation import (
    hard_constraint_names,
    summary_degradation_state,
)
from .schedule_summary_freeze import (
    collect_frozen_batch_ids,
    compute_completion_status,
    freeze_meta_dict,
)
from .summary_runtime_state import (
    build_runtime_state,
    build_summary_warnings,
    counter_dict,
)

__all__ = ["build_result_summary"]


def build_result_summary(*, ctx: SummaryBuildContext) -> Dict[str, Any]:
    runtime_state = build_runtime_state(
        batches=ctx.batches,
        summary=ctx.summary,
        best_metrics=ctx.best_metrics,
    )
    completion_status = compute_completion_status(ctx.summary)
    # From the prepared run input (ctx.t0) to this summary, on the same wall clock (time.monotonic).
    time_cost_ms = max(int((time.monotonic() - float(ctx.t0)) * 1000), 0)
    frozen_batch_ids = collect_frozen_batch_ids(ctx.operations, frozen_op_ids=ctx.frozen_op_ids)
    warnings = build_summary_warnings(summary=ctx.summary, runtime_state=runtime_state)
    freeze_state = freeze_meta_dict(ctx.freeze_meta)
    hard_constraints = hard_constraint_names(freeze_applied=bool(freeze_state.get("freeze_applied")))
    summary_degradation = summary_degradation_state(
        invalid_due_count=runtime_state.invalid_due_count,
        invalid_due_batch_ids_sample=runtime_state.invalid_due_batch_ids_sample,
    )
    algorithm_state = AlgorithmSummaryState(
        ctx=ctx,
        hard_constraints=hard_constraints,
        freeze_state=freeze_state,
        frozen_batch_ids=frozen_batch_ids,
        fallback_counts=counter_dict(ctx.algo_stats.get("fallback_counts")),
    )
    result_summary_obj = build_result_summary_obj(
        ctx=ctx,
        runtime_state=runtime_state,
        warnings=warnings,
        algorithm_state=algorithm_state,
        summary_degradation=summary_degradation,
        completion_status=completion_status,
        time_cost_ms=time_cost_ms,
    )
    return result_summary_obj
