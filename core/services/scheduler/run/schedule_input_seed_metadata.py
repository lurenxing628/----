from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.algorithms.greedy.seed import _identity_int
from core.errors import ValidationError
from core.models.enums import MergeMode, SourceType

MERGED_EXECUTION_GROUP_SOURCE = "merged_execution_group"


def _metadata_error(op_id: int, reason: str) -> ValidationError:
    return ValidationError(
        "保持原安排的外协工序缺少准确组身份，系统已停止排产，没有写入新结果。",
        field="seed_results",
        details={"reason": "invalid_external_group_metadata", "op_id": op_id, "cause": reason},
    )


def _external_seed_ids(seed_results: List[Dict[str, Any]]) -> Set[int]:
    return {
        _identity_int(seed.get("op_id"))
        for seed in seed_results
        if str(seed.get("source") or "").strip().lower() == SourceType.EXTERNAL.value
    }


def _enriched_operation_lookup(algo_ops: List[Any], external_seeds: Set[int]) -> Dict[int, Any]:
    by_id: Dict[int, Any] = {}
    for op in algo_ops:
        op_id = _identity_int(getattr(op, "id", None))
        if op_id not in external_seeds:
            continue
        if op_id in by_id:
            raise _metadata_error(op_id, "duplicate_operation")
        by_id[op_id] = op
    return by_id


def _validated_batch_identity(seed: Dict[str, Any], op: Any, op_id: int) -> str:
    batch_id = str(getattr(op, "batch_id", "") or "").strip()
    if (
        not batch_id or batch_id != str(seed.get("batch_id") or "").strip()
        or str(getattr(op, "source", "") or "").strip().lower() != SourceType.EXTERNAL.value
        or _identity_int(getattr(op, "seq", None)) != _identity_int(seed.get("seq"))
    ):
        raise _metadata_error(op_id, "operation_identity_mismatch")
    return batch_id


def _enrich_external_seed(seed: Dict[str, Any], by_id: Dict[int, Any]) -> Dict[str, Any]:
    op_id = _identity_int(seed.get("op_id"))
    op = by_id.get(op_id)
    if op is None:
        raise _metadata_error(op_id, "missing_operation")
    batch_id = _validated_batch_identity(seed, op, op_id)
    if not all(hasattr(op, field) for field in ("ext_merge_mode", "ext_group_id")):
        raise _metadata_error(op_id, "missing_merge_context")
    mode = str(getattr(op, "ext_merge_mode", None) or "").strip().lower()
    if mode not in ("", MergeMode.SEPARATE.value, MergeMode.MERGED.value):
        raise _metadata_error(op_id, "invalid_merge_mode")
    if mode != MergeMode.MERGED.value:
        return seed
    group_id = str(getattr(op, "ext_group_id", None) or "").strip()
    if not group_id or bool(getattr(op, "merge_context_degraded", False)):
        raise _metadata_error(op_id, "invalid_merged_group")
    metadata = {"op_id": op_id, "batch_id": batch_id, "ext_group_id": group_id}
    piece = getattr(op, "piece_id", None)
    if piece is not None:
        metadata["piece_id"] = piece
    return dict(seed, _external_group_metadata=metadata)


def with_external_seed_metadata(
    seed_results: List[Dict[str, Any]], *, algo_ops: List[Any],
) -> List[Dict[str, Any]]:
    # All protected seeds bind to the same enriched input before their operations are filtered.
    external_seeds = _external_seed_ids(seed_results)
    if not external_seeds:
        return seed_results
    by_id = _enriched_operation_lookup(algo_ops, external_seeds)
    return [
        _enrich_external_seed(seed, by_id) if _identity_int(seed.get("op_id")) in external_seeds else seed
        for seed in seed_results
    ]


def merged_external_group_identity(op: Any, *, group: Any = None) -> Optional[Tuple[str, str, Optional[str]]]:
    """One cycle identity for enriched inputs and verified frozen-group projections."""
    mode = getattr(group, "merge_mode", None) if group is not None else getattr(op, "ext_merge_mode", None)
    group_id = getattr(group, "group_id", None) if group is not None else getattr(op, "ext_group_id", None)
    if (str(getattr(op, "source", None) or "").strip().lower() != SourceType.EXTERNAL.value
            or mode != MergeMode.MERGED.value or not group_id):
        return None
    return str(op.batch_id), str(group_id), getattr(op, "piece_id", None)


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


def with_merged_actual_group_seeds(seed_results, *, algo_ops, actual_op_ids):
    """Fix unreported cycle members without inventing reports for those operations.

    Existing locked/frozen members must already agree, in either sequence order.
    Returned IDs distinguish these derived seeds from inherited official locks.
    """
    groups = {op.id: merged_external_group_identity(op) for op in algo_ops}
    intervals = merged_actual_group_intervals(groups, seed_results, actual_op_ids)
    by_id = {seed["op_id"]: seed for seed in seed_results}
    for op_id, seed in by_id.items():
        identity = groups.get(op_id)
        if identity in intervals and (seed["start_time"], seed["end_time"]) != intervals[identity]:
            raise _actual_group_conflict(op_id)
    result, derived = list(seed_results), set()
    for op in algo_ops:
        identity = groups[op.id]
        if identity not in intervals or op.id in by_id:
            continue
        start, end = intervals[identity]
        result.append({"op_id": op.id, "op_code": getattr(op, "op_code", None), "batch_id": op.batch_id, "seq": op.seq,
                       "source": op.source, "op_type_name": getattr(op, "op_type_name", None), "machine_id": None,
                       "operator_id": None, "start_time": start, "end_time": end,
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
