from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, cast

from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_contracts.value_domains import EXTERNAL, MERGED
from core.errors import ValidationError

MERGED_EXECUTION_GROUP_SOURCE = "merged_execution_group"


def _metadata_error(op_id: int, reason: str) -> ValidationError:
    return ValidationError(
        "保持原安排的外协工序缺少准确组身份，系统已停止排产，没有写入新结果。",
        field="seed_results",
        details={"reason": "invalid_external_group_metadata", "op_id": op_id, "cause": reason},
    )


def _enrich_external_seed(seed: Dict[str, Any], by_id: Dict[int, OpForScheduleAlgo]) -> Dict[str, Any]:
    op_id = seed["op_id"]
    op = by_id.get(op_id)
    if op is None:
        raise _metadata_error(op_id, "missing_operation")
    identity = merged_external_group_identity(op)
    if identity is None:
        return seed
    batch_id, group_id, piece = identity
    metadata = {"op_id": op_id, "batch_id": batch_id, "ext_group_id": group_id}
    if piece is not None:
        metadata["piece_id"] = piece
    return dict(seed, _external_group_metadata=metadata)


def with_external_seed_metadata(
    seed_results: List[Dict[str, Any]], *, algo_ops: List[OpForScheduleAlgo],
) -> List[Dict[str, Any]]:
    # All protected seeds bind to the same enriched input before their operations are filtered.
    # 种子与算法工序都由本次输入构建给出规范编号和来源，这里直接按字段比对。
    external_seeds = {seed["op_id"] for seed in seed_results if seed["source"] == EXTERNAL}
    if not external_seeds:
        return seed_results
    by_id = {op.id: op for op in algo_ops if op.id in external_seeds}
    return [_enrich_external_seed(seed, by_id) if seed["op_id"] in external_seeds else seed for seed in seed_results]


def merged_group_identity(
    batch_id: str, piece_id: Optional[str], *, merge_mode: Optional[str], group_id: Optional[str],
) -> Optional[Tuple[str, str, Optional[str]]]:
    """One cycle identity for enriched inputs and verified frozen-group projections.

    合并方式只在已核对的外协冻结周期记录上出现，且合并时组身份必有；调用方传入的就是这份记录。
    """
    if merge_mode != MERGED:
        return None
    return batch_id, cast(str, group_id), piece_id


def merged_external_group_identity(op: OpForScheduleAlgo) -> Optional[Tuple[str, str, Optional[str]]]:
    # 排产输入构建只给外协工序填合并方式与组身份（来自同一份已核对的冻结周期记录）。
    return merged_group_identity(op.batch_id, op.piece_id, merge_mode=op.ext_merge_mode, group_id=op.ext_group_id)


def _actual_group_conflict(op_id):
    return ValidationError(
        "同一个合并外协组的实际记录和保持安排起止不一致，系统已停止排产，没有写入新结果。",
        field="seed_results", details={"reason": "execution_merged_group_split", "op_id": op_id})


def merged_actual_group_intervals(group_identities, execution_seed_results, actual_op_ids):
    """Index exact cycles only from seeds proven by the execution guard."""
    intervals = {}
    for seed in execution_seed_results:
        op_id = seed["op_id"]
        identity = group_identities.get(op_id)
        if op_id not in actual_op_ids or identity is None:
            continue
        period = seed["start_time"], seed["end_time"]
        if identity in intervals and intervals[identity] != period:
            raise _actual_group_conflict(op_id)
        intervals[identity] = period
    return intervals


def with_merged_actual_group_seeds(seed_results, *, algo_ops, groups, actual_op_ids):
    """Fix unreported cycle members without inventing reports for those operations.

    Existing locked/frozen members must already agree, in either sequence order.
    Returned IDs distinguish these derived seeds from inherited official locks.
    ``groups`` maps every algo op id to merged_external_group_identity(op).
    """
    intervals = merged_actual_group_intervals(groups, seed_results, actual_op_ids)
    by_id = {seed["op_id"]: seed for seed in seed_results}
    for op_id, seed in by_id.items():
        identity = groups.get(op_id)
        if op_id not in actual_op_ids and identity in intervals and (seed["start_time"], seed["end_time"]) != intervals[identity]:
            raise _actual_group_conflict(op_id)
    result, derived = list(seed_results), set()
    for op in algo_ops:
        identity = groups[op.id]
        if identity not in intervals or op.id in by_id:
            continue
        start, end = intervals[identity]
        result.append({"op_id": op.id, "op_code": op.op_code, "batch_id": op.batch_id, "seq": op.seq,
                       "source": op.source, "op_type_name": op.op_type_name, "op_type_id": op.op_type_id,
                       "machine_id": None, "operator_id": None, "start_time": start, "end_time": end,
                       "seed_source": MERGED_EXECUTION_GROUP_SOURCE})
        derived.add(op.id)
    return result, derived


def protected_interval_problem(previous, current, *, previous_group=None, current_group=None):
    """Merged members share the exact interval; ordinary dependencies follow completion."""
    if previous_group is not None and previous_group == current_group:
        if (previous["start_time"], previous["end_time"]) != (current["start_time"], current["end_time"]):
            return "merged_group_split"
    elif current["start_time"] < previous["end_time"]:
        return "precedence_violation"
    return None
