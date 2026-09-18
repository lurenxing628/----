"""Completion evidence for metrics; no forecast or business penalty is inferred."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Set, Tuple

from core.algorithm_contracts.priority_constants import PRIORITY_WEIGHT, normalize_priority

OperationKey = Tuple[str, int]
# This is an ordering sentinel, never a datetime or an estimated metric. Every
# finite float (including a negated maximization metric) is <= this value.
UNKNOWN_OBJECTIVE_VALUE = sys.float_info.max
OBJECTIVE_SCOPE_ALL = "all_batches"
OBJECTIVE_SCOPE_COMPLETED = "completed_batches_only"
OBJECTIVE_SCOPE_UNKNOWN = "unknown"


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
    # Every incomplete batch is explained by recorded failure evidence and no result is unexpected:
    # then the completed-subset components are trustworthy comparison keys behind ``failed_ops``.
    explained: bool = False
    # Priority weight of the dropped batches (critical 3 / urgent 2 / normal 1): reported, not fabricated tardiness.
    incomplete_work_weight: float = 0.0

    @property
    def objective_defined(self) -> bool:
        return not self.incomplete_batch_ids

    @property
    def components_known(self) -> bool:
        """The objective components describe real batches: all of them, or the explained completed subset."""
        return self.objective_defined or self.explained

    @property
    def objective_scope(self) -> str:
        if self.objective_defined:
            return OBJECTIVE_SCOPE_ALL
        return OBJECTIVE_SCOPE_COMPLETED if self.explained else OBJECTIVE_SCOPE_UNKNOWN

    @property
    def objective_score_policy(self) -> str:
        if self.objective_defined:
            return "original"
        return "completed_batches_only" if self.explained else "unknown_all_components"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": "expected_operations_complete_only_v1",
            "objective_defined": self.objective_defined,
            "objective_score_policy": self.objective_score_policy,
            "objective_scope": self.objective_scope,
            "unknown_objective_value": None if self.components_known else UNKNOWN_OBJECTIVE_VALUE,
            "incomplete_work_weight": float(self.incomplete_work_weight),
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
        explained=bool(incomplete) and not unexpected and incomplete <= failure_batches,
        incomplete_work_weight=_priority_weight_sum(batches, incomplete),
    )


def _priority_weight_sum(batches: Dict[str, Any], batch_ids: Set[str]) -> float:
    by_id = {str(bid).strip(): batch for bid, batch in batches.items() if str(bid or "").strip()}
    total = 0.0
    for bid in batch_ids:
        priority = normalize_priority(getattr(by_id.get(bid), "priority", None), default="normal")
        total += float(PRIORITY_WEIGHT.get(priority, 1.0))
    return total


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
