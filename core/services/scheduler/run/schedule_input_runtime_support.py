from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

from core.infrastructure.errors import AppError, ErrorCode
from core.models import BatchOperation

from .schedule_input_contracts import _build_freeze_window_seed_with_meta


def _algo_op_id(op: Any) -> int:
    try:
        return int(getattr(op, "id", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _op_seq(op: Any) -> int:
    try:
        return int(getattr(op, "seq", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _resolve_algo_ops_to_schedule(
    *,
    algo_ops: List[Any],
    frozen_op_ids: Set[int],
    execution_fixed_op_ids: Set[int],
    run_label: str,
    raise_schedule_empty_result_fn: Any,
) -> List[Any]:
    fixed_seed_op_ids = set(frozen_op_ids) | set(execution_fixed_op_ids or set())
    algo_ops_to_schedule = [op for op in algo_ops if _algo_op_id(op) not in fixed_seed_op_ids]
    if algo_ops_to_schedule:
        return algo_ops_to_schedule
    algo_op_ids = {_algo_op_id(op) for op in list(algo_ops or []) if _algo_op_id(op) > 0}
    if algo_op_ids and algo_op_ids <= set(execution_fixed_op_ids or set()):
        raise_schedule_empty_result_fn(
            f"所选工序都已经开工或暂停，不能自动移动，本次未执行{run_label}。请先按现场情况处理。",
            reason="all_operations_fixed_by_execution_facts",
        )
    raise_schedule_empty_result_fn(
        f"冻结窗口内无可调整工序，本次未执行{run_label}。",
        reason="all_operations_frozen",
    )
    return []


def _load_runtime_resource_inputs(
    svc: Any,
    *,
    cfg: Any,
    algo_ops: List[Any],
    start_dt_norm: datetime,
    algo_warnings: List[str],
    load_machine_downtimes_fn: Any,
    build_resource_pool_fn: Any,
    extend_downtime_map_for_resource_pool_fn: Any,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Any]:
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
    return downtime_meta, resource_pool_meta, downtime_map, resource_pool


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
    execution_fixed_op_ids: Set[int],
    execution_completed_op_ids: Set[int],
    execution_seed_results: List[Dict[str, Any]],
    strict_mode: bool,
    build_freeze_window_seed_fn: Any,
    load_machine_downtimes_fn: Any,
    build_resource_pool_fn: Any,
    extend_downtime_map_for_resource_pool_fn: Any,
    raise_schedule_empty_result_fn: Any,
) -> Tuple[
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

    seed_results = _merge_execution_and_freeze_seed_results(
        execution_seed_results=list(execution_seed_results or []),
        freeze_seed_results=list(seed_results or []),
    )
    _validate_completed_downstream_seed_constraints(
        seed_results=seed_results,
        operations=operations,
        execution_completed_op_ids=set(execution_completed_op_ids or set()),
    )
    algo_ops_to_schedule = _resolve_algo_ops_to_schedule(
        algo_ops=algo_ops,
        frozen_op_ids=set(frozen_op_ids),
        execution_fixed_op_ids=set(execution_fixed_op_ids or set()),
        run_label=run_label,
        raise_schedule_empty_result_fn=raise_schedule_empty_result_fn,
    )
    downtime_meta, resource_pool_meta, downtime_map, resource_pool = _load_runtime_resource_inputs(
        svc,
        cfg=cfg,
        algo_ops=algo_ops,
        start_dt_norm=start_dt_norm,
        algo_warnings=algo_warnings,
        load_machine_downtimes_fn=load_machine_downtimes_fn,
        build_resource_pool_fn=build_resource_pool_fn,
        extend_downtime_map_for_resource_pool_fn=extend_downtime_map_for_resource_pool_fn,
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


def _seed_op_id(seed: Dict[str, Any]) -> int:
    try:
        return int(seed.get("op_id") or 0)
    except (TypeError, ValueError):
        return 0


def _seed_resource(value: Any) -> str:
    return str(value or "").strip()


def _seed_batch_id(seed: Dict[str, Any]) -> str:
    return str(seed.get("batch_id") or "").strip()


def _seed_seq(seed: Dict[str, Any]) -> int:
    try:
        return int(seed.get("seq") or 0)
    except (TypeError, ValueError):
        return 0


def _seed_start(seed: Dict[str, Any]) -> Any:
    return seed.get("start_time")


def _seed_end(seed: Dict[str, Any]) -> Any:
    return seed.get("end_time")


def _downstream_operations(
    operations: List[BatchOperation],
    *,
    completed_op_id: int,
    completed_batch_id: str,
    completed_seq: int,
) -> List[BatchOperation]:
    out: List[BatchOperation] = []
    for op in list(operations or []):
        op_id = _algo_op_id(op)
        batch_id = str(getattr(op, "batch_id", "") or "").strip()
        seq = _op_seq(op)
        if op_id != int(completed_op_id) and batch_id == completed_batch_id and seq > completed_seq:
            out.append(op)
    return out


def _seed_starts_before_completed(seed: Dict[str, Any], completed_seed: Dict[str, Any]) -> bool:
    return (
        seed is not None
        and isinstance(_seed_start(seed), datetime)
        and isinstance(_seed_end(completed_seed), datetime)
        and _seed_start(seed) < _seed_end(completed_seed)
    )


def _raise_downstream_seed_conflict(*, op_id: int, completed_op_id: int) -> None:
    raise AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        "已完工的前道工序有真实完工时间，后续工序不能排在它之前。本次没有写入新排程。请刷新后重新排。",
        details={
            "reason": "execution_completed_downstream_before_actual_finish",
            "op_id": int(op_id),
            "completed_op_id": int(completed_op_id),
        },
    )


def _validate_completed_downstream_seed_constraints(
    *,
    seed_results: List[Dict[str, Any]],
    operations: List[BatchOperation],
    execution_completed_op_ids: Set[int],
) -> None:
    if not seed_results or not execution_completed_op_ids:
        return
    seed_by_op_id = {
        _seed_op_id(seed): seed
        for seed in list(seed_results or [])
        if _seed_op_id(seed) > 0
    }
    for completed_op_id in sorted(set(execution_completed_op_ids or set())):
        completed_seed = seed_by_op_id.get(int(completed_op_id))
        if completed_seed is None or not isinstance(_seed_end(completed_seed), datetime):
            continue
        completed_batch_id = _seed_batch_id(completed_seed)
        completed_seq = _seed_seq(completed_seed)
        if not completed_batch_id or completed_seq <= 0:
            continue
        for op in _downstream_operations(
            operations,
            completed_op_id=int(completed_op_id),
            completed_batch_id=completed_batch_id,
            completed_seq=completed_seq,
        ):
            op_id = _algo_op_id(op)
            seed = seed_by_op_id.get(int(op_id))
            if seed is None:
                continue
            if _seed_starts_before_completed(seed, completed_seed):
                _raise_downstream_seed_conflict(op_id=int(op_id), completed_op_id=int(completed_op_id))


def _seed_conflicts(execution_seed: Dict[str, Any], freeze_seed: Dict[str, Any]) -> bool:
    return (
        execution_seed.get("start_time") != freeze_seed.get("start_time")
        or execution_seed.get("end_time") != freeze_seed.get("end_time")
        or _seed_resource(execution_seed.get("machine_id")) != _seed_resource(freeze_seed.get("machine_id"))
        or _seed_resource(execution_seed.get("operator_id")) != _seed_resource(freeze_seed.get("operator_id"))
    )


def _raise_seed_conflict(op_id: int) -> None:
    raise AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        "现场反馈和冻结窗口里的排程记录对不上，本次没有写入新排程。请刷新后重新排。",
        details={"reason": "execution_seed_conflict", "op_id": int(op_id)},
    )


def _with_seed_source(seed: Dict[str, Any], source: str) -> Dict[str, Any]:
    out = dict(seed)
    out["seed_source"] = source
    return out


def _merge_execution_and_freeze_seed_results(
    *,
    execution_seed_results: List[Dict[str, Any]],
    freeze_seed_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    execution_by_op_id = {
        _seed_op_id(seed): _with_seed_source(seed, "execution_fact")
        for seed in list(execution_seed_results or [])
        if _seed_op_id(seed) > 0
    }
    merged: Dict[int, Dict[str, Any]] = {}
    for seed in list(freeze_seed_results or []):
        op_id = _seed_op_id(seed)
        if op_id <= 0:
            continue
        freeze_seed = _with_seed_source(seed, "freeze_window")
        execution_seed = execution_by_op_id.get(op_id)
        if execution_seed is not None:
            if _seed_conflicts(execution_seed, freeze_seed):
                _raise_seed_conflict(op_id)
            merged[op_id] = execution_seed
            continue
        merged[op_id] = freeze_seed
    for op_id, seed in execution_by_op_id.items():
        merged[int(op_id)] = seed
    return [merged[op_id] for op_id in sorted(merged)]
