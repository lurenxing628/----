"""Completion evidence for metrics; no forecast or business penalty is inferred."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Set, Tuple

OperationKey = Tuple[str, int]
# This is an ordering sentinel, never a datetime or an estimated metric. Every
# finite float (including a negated maximization metric) is <= this value.
UNKNOWN_OBJECTIVE_VALUE = sys.float_info.max


@dataclass(frozen=True)
class BatchCompletion:
    expected_operation_count: int
    missing_operation_count: int
    unexpected_result_count: int
    complete_batch_count: int
    incomplete_batch_ids: Tuple[str, ...]
    partial_batch_ids: Tuple[str, ...]
    failure_detail_count: int
    failure_batch_ids: Tuple[str, ...]

    @property
    def objective_defined(self) -> bool:
        return not self.incomplete_batch_ids

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": "expected_operations_complete_only_v1",
            "objective_defined": self.objective_defined,
            "objective_score_policy": "original" if self.objective_defined else "unknown_all_components",
            "unknown_objective_value": None if self.objective_defined else UNKNOWN_OBJECTIVE_VALUE,
            "due_metrics_scope": "completed_batches_only",
            "resource_metrics_scope": "scheduled_results_only",
            "expected_operation_count": self.expected_operation_count,
            "missing_operation_count": self.missing_operation_count,
            "unexpected_result_count": self.unexpected_result_count,
            "complete_batch_count": self.complete_batch_count,
            "incomplete_batch_count": len(self.incomplete_batch_ids),
            "partial_batch_count": len(self.partial_batch_ids),
            "incomplete_batch_ids_sample": list(self.incomplete_batch_ids[:20]),
            "partial_batch_ids_sample": list(self.partial_batch_ids[:20]),
            "failure_detail_count": self.failure_detail_count,
            "failure_batch_ids_sample": list(self.failure_batch_ids[:20]),
        }


def collect_batch_completion(
    results: Iterable[Any],
    batches: Dict[str, Any],
    *,
    expected_operations: Optional[Iterable[Any]],
    seed_results: Optional[Iterable[Any]],
    failure_details: Optional[Iterable[Dict[str, Any]]],
) -> Optional[BatchCompletion]:
    if expected_operations is None:
        if seed_results is not None or failure_details is not None:
            raise ValueError("Completion evidence requires expected_operations.")
        # The historical two-argument metrics API has no operation universe.
        # Production candidate scoring must supply the explicit expected set.
        return None
    expected = _expected_keys(expected_operations, seed_results or ())
    scheduled = {_operation_key(item, result=True) for item in results if _has_time_range(item)}
    failed = list(failure_details or ())
    failure_batches = _failure_batches(failed, expected)
    batch_ids = {str(bid).strip() for bid in batches if str(bid or "").strip()}
    batch_ids.update(key[0] for key in expected | scheduled)
    batch_ids.update(failure_batches)
    unexpected = scheduled - expected
    incomplete = _incomplete_batch_ids(batch_ids, expected, scheduled) | failure_batches
    return BatchCompletion(
        expected_operation_count=len(expected),
        missing_operation_count=len(expected - scheduled),
        unexpected_result_count=len(unexpected),
        complete_batch_count=len(batch_ids - incomplete),
        incomplete_batch_ids=tuple(sorted(incomplete)),
        partial_batch_ids=tuple(sorted(incomplete & {key[0] for key in scheduled})),
        failure_detail_count=len(failed),
        failure_batch_ids=tuple(sorted(failure_batches)),
    )


def _incomplete_batch_ids(
    batch_ids: Set[str], expected: Set[OperationKey], scheduled: Set[OperationKey],
) -> Set[str]:
    expected_by_batch: Dict[str, Set[OperationKey]] = {}
    for key in expected:
        expected_by_batch.setdefault(key[0], set()).add(key)
    incomplete = {
        bid for bid in batch_ids
        if not expected_by_batch.get(bid) or not expected_by_batch[bid] <= scheduled
    }
    incomplete.update(key[0] for key in scheduled - expected)
    return incomplete


def _expected_keys(operations: Iterable[Any], seeds: Iterable[Any]) -> Set[OperationKey]:
    keys = {_operation_key(item, result=False) for item in operations}
    keys.update(_operation_key(item, result=True) for item in seeds)
    batch_by_op_id: Dict[int, str] = {}
    for bid, op_id in keys:
        if op_id in batch_by_op_id and batch_by_op_id[op_id] != bid:
            raise ValueError("Expected operation identity belongs to conflicting batches.")
        batch_by_op_id[op_id] = bid
    return keys


def _operation_key(item: Any, *, result: bool) -> OperationKey:
    bid = str(getattr(item, "batch_id", "") or "").strip()
    raw_id = getattr(item, "op_id", None) if result else getattr(item, "id", getattr(item, "op_id", None))
    if isinstance(raw_id, bool) or not isinstance(raw_id, (int, str)):
        raise ValueError("Completion evidence requires a positive operation ID.")
    op_id = int(raw_id)
    if not bid or op_id <= 0:
        raise ValueError("Completion evidence requires a batch and positive operation ID.")
    return bid, op_id


def _has_time_range(item: Any) -> bool:
    start = getattr(item, "start_time", None)
    end = getattr(item, "end_time", None)
    # Zero-duration operations are legal and still satisfy their expected ID.
    return isinstance(start, datetime) and isinstance(end, datetime) and end >= start


def _failure_batches(details: Iterable[Dict[str, Any]], expected: Set[OperationKey]) -> Set[str]:
    batch_by_op_id = {op_id: bid for bid, op_id in expected}
    batches: Set[str] = set()
    for detail in details:
        if not isinstance(detail, dict):
            raise ValueError("Completion failure evidence must be a mapping.")
        bid = str(detail.get("batch_id") or "").strip()
        op_id = detail.get("op_id")
        matched = batch_by_op_id.get(int(op_id)) if op_id is not None else None
        if matched and bid and matched != bid:
            raise ValueError("Failure evidence disagrees with the expected operation batch.")
        bid = bid or matched or ""
        if not bid:
            raise ValueError("Failure evidence cannot be attributed to a batch.")
        batches.add(bid)
    return batches
