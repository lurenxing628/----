from __future__ import annotations

import sqlite3
from datetime import datetime
from functools import partial
from itertools import groupby
from typing import Any, Dict, List, Optional, Set, Tuple

from core.algorithm_runtime.internal_slot import validate_internal_hours
from core.errors import AppError, ErrorCode, ValidationError
from core.models.batch_operation import BatchOperation
from core.models.enums import SourceType

from .schedule_input_seed_metadata import (
    merged_external_group_identity,
    protected_interval_problem,
    with_external_seed_metadata,
    with_merged_actual_group_seeds,
)


def _resolve_algo_ops_to_schedule(
    *,
    algo_ops: List[Any],
    frozen_op_ids: Set[int],
    execution_completed_op_ids: Set[int],
    run_label: str,
    raise_schedule_empty_result_fn: Any,
    derived_group_op_ids: Optional[Set[int]] = None,
) -> List[Any]:
    fixed_seed_op_ids = frozen_op_ids | execution_completed_op_ids
    algo_ops_to_schedule = [op for op in algo_ops if op.id not in fixed_seed_op_ids]
    if algo_ops_to_schedule:
        return algo_ops_to_schedule
    if derived_group_op_ids:
        # Unreported members still produce a plan result, but their already
        # started physical cycle has been represented by exact derived seeds.
        return []
    algo_op_ids = {op.id for op in algo_ops}
    if algo_op_ids and algo_op_ids <= execution_completed_op_ids:
        raise_schedule_empty_result_fn(
            f"所选工序都已经完工，不能自动移动，本次未执行{run_label}。请先按现场情况处理。",
            reason="all_operations_fixed_by_execution_facts",
        )
    raise_schedule_empty_result_fn(
        f"冻结窗口内无可调整工序，本次未执行{run_label}。",
        reason="all_operations_frozen",
    )
    return []


def _ensure_internal_runtime_hours(batches: Dict[str, Any], algo_ops: List[Any]) -> None:
    for op in algo_ops:
        if op.source != SourceType.INTERNAL.value:
            continue
        batch_id = op.batch_id
        batch = batches.get(batch_id)
        if batch is None:
            raise ValidationError(f"自制工序 {op.op_code or '-'} 找不到所属批次，无法计算总工时。", field="batch_id")
        # 单一真相源：直接复用算法层 internal_slot.validate_internal_hours 校验自制工时。
        # 它要求 setup/unit/quantity 都是非负有限数字：缺失（None）等读不出的值报“工时字段不合法”，
        # 负数和非有限数同样拦下；值为 0 合法，总工时 0 也合法（含 quantity==0：总量=setup，算法层按瞬时排）。
        # 此处不再手搓第二套 quantity/工时校验，避免口径分叉
        # （quantity==0 曾被错误硬拦整批，详见 issue 2026-06-24-core-algorithm-deep-review-fixes 复修讨论）。
        try:
            validate_internal_hours(op, batch)
        except ValueError as exc:
            raise ValidationError(
                f"自制工序 {op.op_code or '-'} 的工时不合法，请检查换型时间、单件工时和数量。",
                field="work_hours",
                details={
                    "reason": "invalid_internal_work_hours",
                    "op_id": int(op.id),
                    "batch_id": batch_id,
                    "op_code": op.op_code,
                },
            ) from exc


def _load_runtime_resource_inputs(
    *,
    cfg: Any,
    algo_ops: List[Any],
    resource_pool_ops: List[Any],
    start_dt_norm: datetime,
    load_machine_downtimes_fn: Any,
    build_resource_pool_fn: Any,
    extend_downtime_map_for_resource_pool_fn: Any,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Any]:
    downtime_meta: Dict[str, Any] = {}
    resource_pool_meta: Dict[str, Any] = {}
    downtime_map = load_machine_downtimes_fn(
        algo_ops=algo_ops,
        start_dt=start_dt_norm,
    )
    resource_pool = build_resource_pool_fn(
        cfg=cfg,
        algo_ops=resource_pool_ops,
        meta=resource_pool_meta,
    )
    downtime_map = extend_downtime_map_for_resource_pool_fn(
        cfg=cfg,
        resource_pool=resource_pool,
        downtime_map=downtime_map,
        start_dt=start_dt_norm,
        meta=downtime_meta,
    )
    return downtime_meta, resource_pool_meta, downtime_map, resource_pool


def prepare_runtime_seeds(
    conn: sqlite3.Connection,
    *,
    run_label: str,
    batches: Dict[str, Any],
    operations: List[BatchOperation],
    algo_ops: List[Any],
    frozen_op_ids: Set[int],
    freeze_seed_results: List[Dict[str, Any]],
    execution_completed_op_ids: Set[int],
    execution_seed_results: List[Dict[str, Any]],
    raise_schedule_empty_result_fn: Any,
    validate_fixed_operator_qualifications_fn: Any,
    validate_completed_seed_constraints_fn: Any = None,
) -> Tuple[Set[int], List[Dict[str, Any]], List[Any]]:
    seed_results = _merge_execution_and_freeze_seed_results(
        execution_seed_results=execution_seed_results,
        freeze_seed_results=freeze_seed_results,
    )
    # 合并外协组身份按本次 algo_ops 算一次，组内派生原安排和完工下游校验（含分件校验）共用。
    groups = {op.id: merged_external_group_identity(op) for op in algo_ops}
    seed_results, derived_group_ids = with_merged_actual_group_seeds(seed_results, algo_ops=algo_ops,
        groups=groups, actual_op_ids=execution_completed_op_ids)
    frozen_op_ids = frozen_op_ids | derived_group_ids
    seed_results = with_external_seed_metadata(seed_results, algo_ops=algo_ops)
    validate_seeds = validate_completed_seed_constraints_fn or partial(
        _validate_completed_downstream_seed_constraints, operations=operations,
    )
    validate_seeds(
        seed_results=seed_results,
        groups=groups,
        execution_completed_op_ids=execution_completed_op_ids,
    )
    algo_ops_to_schedule = _resolve_algo_ops_to_schedule(
        algo_ops=algo_ops,
        frozen_op_ids=frozen_op_ids,
        execution_completed_op_ids=execution_completed_op_ids,
        run_label=run_label,
        raise_schedule_empty_result_fn=raise_schedule_empty_result_fn,
        derived_group_op_ids=derived_group_ids,
    )
    _ensure_internal_runtime_hours(batches, algo_ops_to_schedule)
    validate_fixed_operator_qualifications_fn(conn, algo_ops_to_schedule)
    return frozen_op_ids, seed_results, algo_ops_to_schedule


def _seed_resource(value: Any) -> str:
    return str(value or "").strip()


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


def _raise_merged_seed_conflict(*, op_id: int, completed_op_id: int) -> None:
    raise AppError(ErrorCode.SCHEDULE_CONFLICT,
        "同一个合并外协组的原安排起止不一致，本次没有写入新排程。请核对现场记录和原安排。",
        details={"reason": "execution_merged_group_split", "op_id": op_id, "completed_op_id": completed_op_id})


def _validate_downstream_seed_pair(completed_seed, seed, *, completed_op_id, op_id, groups):
    problem = protected_interval_problem(completed_seed, seed,
        previous_group=groups.get(completed_op_id), current_group=groups.get(op_id))
    if problem == "merged_group_split":
        _raise_merged_seed_conflict(op_id=int(op_id), completed_op_id=int(completed_op_id))
    if problem == "precedence_violation":
        _raise_downstream_seed_conflict(op_id=int(op_id), completed_op_id=int(completed_op_id))


def _update_latest_completed(best, second, cand):
    rank = (cand[0], -cand[1])
    if best is None:
        return cand, None
    best_rank = (best[0], -best[1])
    if best[3] is not None and best[3] == cand[3]:
        return (cand if rank > best_rank else best), second
    if rank > best_rank:
        return cand, best
    if second is None or rank > (second[0], -second[1]):
        second = cand
    return best, second


def validate_completed_downstream_intervals(
    *,
    operations_in_scope: Any,
    groups: Dict[int, Any],
    completed_intervals: Dict[int, Dict[str, Any]],
    validate_pair_fn: Any,
) -> None:
    if not completed_intervals:
        return
    by_batch, by_group = {}, {}
    for batch_id, seq, op_id in operations_in_scope:
        by_batch.setdefault(batch_id, []).append((seq, op_id))
        group = groups.get(op_id)
        if group is not None:
            by_group.setdefault(group, []).append(op_id)
    for group_op_ids in by_group.values():
        completed_in_group = [oid for oid in group_op_ids if oid in completed_intervals]
        if not completed_in_group:
            continue
        anchor_op_id = min(completed_in_group)
        anchor_interval = completed_intervals[anchor_op_id]
        for op_id in group_op_ids:
            if op_id != anchor_op_id:
                validate_pair_fn(anchor_interval, op_id, completed_op_id=anchor_op_id)
    for pairs in by_batch.values():
        pairs.sort()
        best, second = None, None
        for _, same_seq_pairs in groupby(pairs, key=lambda item: item[0]):
            seq_op_ids = [op_id for _, op_id in same_seq_pairs]
            if best is not None:
                for op_id in seq_op_ids:
                    op_group = groups.get(op_id)
                    chosen = second if (best[3] is not None and best[3] == op_group) else best
                    if chosen is not None:
                        validate_pair_fn(chosen[2], op_id, completed_op_id=chosen[1])
            for op_id in seq_op_ids:
                interval = completed_intervals.get(op_id)
                if interval is not None:
                    best, second = _update_latest_completed(
                        best, second, (interval["end_time"], op_id, interval, groups.get(op_id)))


def _validate_completed_downstream_seed_constraints(
    *,
    seed_results: List[Dict[str, Any]],
    operations: List[BatchOperation],
    groups: Dict[int, Any],
    execution_completed_op_ids: Set[int],
) -> None:
    if not seed_results or not execution_completed_op_ids:
        return
    seed_by_op_id = {int(seed["op_id"]): seed for seed in seed_results}
    completed_intervals = {
        completed_op_id: seed_by_op_id[completed_op_id]
        for completed_op_id in execution_completed_op_ids
    }
    validate_completed_downstream_intervals(
        operations_in_scope=((op.batch_id, op.seq, op.id) for op in operations if op.id in seed_by_op_id),
        groups=groups,
        completed_intervals=completed_intervals,
        validate_pair_fn=lambda completed_seed, op_id, *, completed_op_id: _validate_downstream_seed_pair(
            completed_seed, seed_by_op_id[op_id], completed_op_id=completed_op_id, op_id=op_id, groups=groups
        ),
    )


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
    if seed.get("seed_source") == source:
        return seed
    return {**seed, "seed_source": source}


def _merge_execution_and_freeze_seed_results(
    *,
    execution_seed_results: List[Dict[str, Any]],
    freeze_seed_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    execution_by_op_id = {
        int(seed["op_id"]): _with_seed_source(seed, "execution_fact")
        for seed in execution_seed_results
    }
    merged: Dict[int, Dict[str, Any]] = {}
    for seed in freeze_seed_results:
        op_id = int(seed["op_id"])
        freeze_seed = _with_seed_source(seed, "freeze_window")
        execution_seed = execution_by_op_id.get(op_id)
        if execution_seed is not None:
            if _seed_conflicts(execution_seed, freeze_seed):
                _raise_seed_conflict(op_id)
            merged[op_id] = execution_seed
            continue
        merged[op_id] = freeze_seed
    for op_id, seed in execution_by_op_id.items():
        merged[op_id] = seed
    return [merged[op_id] for op_id in sorted(merged)]
