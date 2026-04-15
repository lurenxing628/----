from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Set

from core.models import BatchOperation

from .schedule_input_contracts import _build_freeze_window_seed_with_meta


def _build_runtime_support_inputs(
    svc: Any,
    *,
    cfg: Any,
    prev_version: int,
    start_dt_norm: datetime,
    run_label: str,
    operations: List[BatchOperation],
    reschedulable_operations: List[BatchOperation],
    algo_ops: List[Any],
    strict_mode: bool,
    build_freeze_window_seed_fn: Any,
    load_machine_downtimes_fn: Any,
    build_resource_pool_fn: Any,
    extend_downtime_map_for_resource_pool_fn: Any,
    raise_schedule_empty_result_fn: Any,
) -> tuple[
    Set[int],
    List[Dict[str, Any]],
    List[str],
    Dict[str, Any],
    List[Any],
    Dict[str, Any],
    Dict[str, Any],
    Dict[str, Any],
    Any,
    int,
]:
    frozen_op_ids, seed_results, algo_warnings, freeze_meta = _build_freeze_window_seed_with_meta(
        build_freeze_window_seed_fn,
        svc,
        cfg=cfg,
        prev_version=prev_version,
        start_dt=start_dt_norm,
        operations=operations,
        reschedulable_operations=reschedulable_operations,
        strict_mode=bool(strict_mode),
    )

    algo_ops_to_schedule = [op for op in algo_ops if int(getattr(op, "id", 0) or 0) not in frozen_op_ids]
    if not algo_ops_to_schedule:
        raise_schedule_empty_result_fn(
            f"冻结窗口内无可调整工序，本次未执行{run_label}。",
            reason="all_operations_frozen",
        )

    downtime_meta: Dict[str, Any] = {}
    resource_pool_meta: Dict[str, Any] = {}
    downtime_map = load_machine_downtimes_fn(
        svc,
        algo_ops=algo_ops,
        start_dt=start_dt_norm,
        warnings=algo_warnings,
        meta=downtime_meta,
    )

    resource_pool, pool_warnings = build_resource_pool_fn(
        svc,
        cfg=cfg,
        algo_ops=algo_ops,
        meta=resource_pool_meta,
    )
    if pool_warnings:
        algo_warnings.extend(list(pool_warnings or []))

    downtime_map = extend_downtime_map_for_resource_pool_fn(
        svc,
        cfg=cfg,
        resource_pool=resource_pool,
        downtime_map=downtime_map,
        start_dt=start_dt_norm,
        warnings=algo_warnings,
        meta=downtime_meta,
    )
    optimizer_seed_version = max(int(prev_version) + 1, 1)

    return (
        set(frozen_op_ids),
        list(seed_results or []),
        list(algo_warnings or []),
        freeze_meta,
        algo_ops_to_schedule,
        downtime_meta,
        resource_pool_meta,
        downtime_map,
        resource_pool,
        optimizer_seed_version,
    )
