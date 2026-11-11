from __future__ import annotations

import sqlite3
from datetime import datetime
from itertools import groupby
from typing import Any, Dict, List, Mapping, Set, Tuple

from core.algorithm_contracts.ordering import clean_resource_id
from core.errors import AppError, ErrorCode
from core.models.batch_operation import BatchOperation

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
    derived_group_op_ids: Set[int],
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
    operations: List[BatchOperation],
    algo_ops: List[Any],
    frozen_op_ids: Set[int],
    freeze_seed_results: List[Dict[str, Any]],
    execution_completed_op_ids: Set[int],
    execution_seed_results: List[Dict[str, Any]],
    actual_group_intervals: Mapping[Any, Tuple[datetime, datetime]],
    raise_schedule_empty_result_fn: Any,
    validate_fixed_operator_qualifications_fn: Any,
    validate_completed_seed_constraints_fn: Any = None,
) -> Tuple[Set[int], List[Dict[str, Any]], List[Any], Dict[int, Tuple[datetime, datetime]]]:
    seed_results = _merge_execution_and_freeze_seed_results(
        execution_seed_results=execution_seed_results,
        freeze_seed_results=freeze_seed_results,
    )
    # 合并外协组身份按本次 algo_ops 算一次，组内派生原安排和完工下游校验（含分件校验）共用。
    groups = {op.id: merged_external_group_identity(op) for op in algo_ops}
    seed_results, derived_group_ids, external_intervals = with_merged_actual_group_seeds(
        seed_results,
        algo_ops=algo_ops,
        groups=groups,
        actual_op_ids=execution_completed_op_ids,
        actual_group_intervals=actual_group_intervals,
    )
    frozen_op_ids = frozen_op_ids | derived_group_ids
    seed_results = with_external_seed_metadata(seed_results, algo_ops=algo_ops)
    if validate_completed_seed_constraints_fn is not None:
        validate_completed_seed_constraints_fn(
            seed_results=seed_results,
            groups=groups,
        )
    else:
        _validate_completed_downstream_seed_constraints(
            seed_results=seed_results,
            operations=operations,
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
    validate_fixed_operator_qualifications_fn(conn, algo_ops_to_schedule)
    return frozen_op_ids, seed_results, algo_ops_to_schedule, external_intervals


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
        execution_seed["start_time"] != freeze_seed["start_time"]
        or execution_seed["end_time"] != freeze_seed["end_time"]
        or clean_resource_id(execution_seed["machine_id"]) != clean_resource_id(freeze_seed["machine_id"])
        or clean_resource_id(execution_seed["operator_id"]) != clean_resource_id(freeze_seed["operator_id"])
    )


def _raise_seed_conflict(op_id: int) -> None:
    raise AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        "现场反馈和冻结窗口里的排程记录对不上，本次没有写入新排程。请刷新后重新排。",
        details={"reason": "execution_seed_conflict", "op_id": int(op_id)},
    )


def _merge_execution_and_freeze_seed_results(
    *,
    execution_seed_results: List[Dict[str, Any]],
    freeze_seed_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    execution_by_op_id = {
        int(seed["op_id"]): seed
        for seed in execution_seed_results
    }
    merged: Dict[int, Dict[str, Any]] = {}
    for freeze_seed in freeze_seed_results:
        op_id = int(freeze_seed["op_id"])
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
