from __future__ import annotations

from typing import Any, Callable, Dict, List, Set

from .schedule_candidate_persistence import persist_candidate_comparison

ScheduleCorePersist = Callable[..., None]
ScheduleOperationLogger = Callable[..., None]


def persist_schedule_run_with_candidates(
    svc: Any,
    *,
    persist_schedule_core_in_tx: ScheduleCorePersist,
    log_schedule_operation: ScheduleOperationLogger,
    cfg: Any,
    version: int,
    validated_schedule_payload: Any,
    summary: Any,
    used_strategy: Any,
    used_params: Dict[str, Any],
    batches: Dict[str, Any],
    reschedulable_operations: List[Any],
    normalized_batch_ids: List[str],
    created_by: str,
    simulate: bool,
    frozen_op_ids: Set[int],
    result_status: str,
    result_summary_json: str,
    result_summary_obj: Dict[str, Any],
    missing_internal_resource_op_ids: Set[int],
    overdue_items: List[Dict[str, Any]],
    time_cost_ms: int,
    candidate_comparison: Any,
) -> None:
    with svc.tx_manager.transaction():
        persist_schedule_core_in_tx(
            svc,
            cfg=cfg,
            version=version,
            validated_schedule_payload=validated_schedule_payload,
            summary=summary,
            used_strategy=used_strategy,
            batches=batches,
            reschedulable_operations=reschedulable_operations,
            created_by=created_by,
            simulate=simulate,
            frozen_op_ids=frozen_op_ids,
            result_status=result_status,
            result_summary_json=result_summary_json,
            missing_internal_resource_op_ids=missing_internal_resource_op_ids,
        )
        if candidate_comparison is not None:
            persist_candidate_comparison(
                svc,
                version=int(version),
                candidate_comparison=candidate_comparison,
                frozen_op_ids=frozen_op_ids,
            )

    log_schedule_operation(
        svc,
        version=int(version),
        simulate=simulate,
        used_strategy=used_strategy,
        used_params=used_params,
        result_summary_obj=result_summary_obj,
        normalized_batch_ids=normalized_batch_ids,
        batches=batches,
        summary=summary,
        result_status=result_status,
        overdue_items=overdue_items,
        time_cost_ms=time_cost_ms,
    )


__all__ = ["persist_schedule_run_with_candidates"]
