from __future__ import annotations

from typing import Any, Dict, List, Set

from core.algorithms.greedy.seed import _identity_int
from core.infrastructure.errors import ValidationError
from core.models.enums import MergeMode, SourceType


def _metadata_error(op_id: int, reason: str) -> ValidationError:
    return ValidationError(
        "冻结外协工序的组身份资料缺失或不一致，系统已停止排产，没有写入新结果。",
        field="seed_results",
        details={"reason": "invalid_frozen_external_group_metadata", "op_id": op_id, "cause": reason},
    )


def _external_seed_ids(seed_results: List[Dict[str, Any]], frozen_op_ids: Set[int]) -> Set[int]:
    return {
        _identity_int(seed.get("op_id"))
        for seed in seed_results
        if _identity_int(seed.get("op_id")) in frozen_op_ids
        and str(seed.get("source") or "").strip().lower() == SourceType.EXTERNAL.value
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
    return dict(seed, _external_group_metadata={
        "op_id": op_id, "batch_id": batch_id, "ext_group_id": group_id,
    })


def with_frozen_external_seed_metadata(
    seed_results: List[Dict[str, Any]], *, frozen_op_ids: Set[int], algo_ops: List[Any],
) -> List[Dict[str, Any]]:
    # Resolve identity from the enriched, pre-filter input, never from neighbouring operations.
    external_seeds = _external_seed_ids(seed_results, frozen_op_ids)
    if not external_seeds:
        return seed_results
    by_id = _enriched_operation_lookup(algo_ops, external_seeds)
    return [
        _enrich_external_seed(seed, by_id) if _identity_int(seed.get("op_id")) in external_seeds else seed
        for seed in seed_results
    ]
