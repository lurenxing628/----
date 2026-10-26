"""Completion evidence for metrics; no forecast or business penalty is inferred."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, FrozenSet, Iterable, Optional, Set, Tuple

from core.algorithm_contracts.date_parsers import due_exclusive, parse_date
from core.algorithm_contracts.priority_constants import PRIORITY_WEIGHT, normalize_priority
from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult
from core.models.batch import Batch

OperationKey = Tuple[str, int]
# This is an ordering sentinel, never a datetime or an estimated metric. Every
# finite float (including a negated maximization metric) is <= this value.
UNKNOWN_OBJECTIVE_VALUE = sys.float_info.max
OBJECTIVE_SCOPE_ALL = "all_batches"
OBJECTIVE_SCOPE_COMPLETED = "completed_batches_only"
OBJECTIVE_SCOPE_UNKNOWN = "unknown"


@dataclass(frozen=True)
class PreparedBatchDue:
    batch_id: str
    priority_weight: float
    due_invalid: bool
    due_exclusive: Optional[datetime]
    due_text: str


@dataclass(frozen=True)
class PreparedEvaluationContext:
    """Static facts owned by one evaluation input set; results stay dynamic."""

    expected_keys: FrozenSet[OperationKey]
    expected_by_batch: Dict[str, FrozenSet[OperationKey]]
    batch_by_op_id: Dict[int, str]
    batch_ids: FrozenSet[str]
    priority_weights: Dict[str, float]
    due_batches: Tuple[PreparedBatchDue, ...]


def prepare_evaluation_context(
    *,
    batches: Dict[str, Batch],
    expected_operations: Iterable[OpForScheduleAlgo],
    seed_results: Iterable[ScheduleResult],
) -> PreparedEvaluationContext:
    keys, expected_by_batch, batch_by_op_id = _prepare_expected_keys(expected_operations, seed_results)
    priority_weights: Dict[str, float] = {}
    due_batches = []
    # Batch keys are database primary keys: non-empty and already trimmed.
    for bid, batch in batches.items():
        priority = normalize_priority(batch.priority, default="normal")
        weight = float(PRIORITY_WEIGHT.get(priority, 1.0))
        priority_weights[bid] = weight
        due_datetime, due_text, due_invalid = parse_due_exclusive_datetime(batch.due_date)
        due_batches.append(PreparedBatchDue(
            batch_id=bid, priority_weight=weight, due_invalid=due_invalid,
            due_exclusive=due_datetime, due_text=due_text,
        ))
    return PreparedEvaluationContext(
        expected_keys=frozenset(keys), expected_by_batch=expected_by_batch, batch_by_op_id=batch_by_op_id,
        batch_ids=frozenset(priority_weights.keys() | expected_by_batch.keys()),
        priority_weights=priority_weights, due_batches=tuple(due_batches),
    )


def _due_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value).strip()


def _parse_due_date_state(value: Any) -> Tuple[Optional[date], bool]:
    if value is None:
        return None, False
    if isinstance(value, date) and not isinstance(value, datetime):
        return value, False
    if isinstance(value, datetime):
        return value.date(), False
    s = str(value).strip()
    if not s:
        return None, False
    parsed = parse_date(s)
    return parsed, parsed is None


def parse_due_exclusive_datetime(value: Any) -> Tuple[Optional[datetime], str, bool]:
    """交期指标与风险摘要共用的日期、展示文本及坏值口径。"""
    parsed, invalid = _parse_due_date_state(value)
    return due_exclusive(parsed) if parsed is not None else None, _due_text(value), invalid


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
    results: Iterable[ScheduleResult],
    *,
    prepared: PreparedEvaluationContext,
    failure_details: Iterable[Dict[str, Any]],
) -> BatchCompletion:
    expected = prepared.expected_keys
    scheduled = {_result_key(item) for item in results if _has_time_range(item)}
    failed = list(failure_details)
    failure_batches = _failure_batches(failed, prepared.batch_by_op_id) if failed else set()
    unexpected = scheduled - expected
    missing_operation_count = len(expected - scheduled)
    if (
        missing_operation_count == 0
        and not unexpected
        and not failure_batches
        and len(prepared.expected_by_batch) == len(prepared.batch_ids)
    ):
        return BatchCompletion(
            expected_operation_count=len(expected),
            missing_operation_count=0,
            unexpected_result_count=0,
            complete_batch_count=len(prepared.batch_ids),
            incomplete_batch_ids=(),
            partial_batch_ids=(),
            failure_detail_count=0,
            failure_batch_ids=(),
            explained=False,
            incomplete_work_weight=0.0,
        )
    batch_ids = set(prepared.batch_ids)
    batch_ids.update(key[0] for key in scheduled)
    batch_ids.update(failure_batches)
    if missing_operation_count == 0:
        incomplete = {bid for bid in batch_ids if not prepared.expected_by_batch.get(bid)}
        incomplete.update(key[0] for key in unexpected)
        incomplete |= failure_batches
    else:
        incomplete = _incomplete_batch_ids(batch_ids, prepared.expected_by_batch, scheduled, unexpected) | failure_batches
    return BatchCompletion(
        expected_operation_count=len(expected),
        missing_operation_count=missing_operation_count,
        unexpected_result_count=len(unexpected),
        complete_batch_count=len(batch_ids - incomplete),
        incomplete_batch_ids=tuple(sorted(incomplete)),
        partial_batch_ids=tuple(sorted(incomplete & {key[0] for key in scheduled})),
        failure_detail_count=len(failed),
        failure_batch_ids=tuple(sorted(failure_batches)),
        explained=bool(incomplete) and not unexpected and incomplete <= failure_batches,
        incomplete_work_weight=_priority_weight_sum(prepared.priority_weights, incomplete),
    )


def _priority_weight_sum(priority_weights: Dict[str, float], batch_ids: Set[str]) -> float:
    return sum((priority_weights.get(bid, 1.0) for bid in batch_ids), 0.0)


def _incomplete_batch_ids(
    batch_ids: Set[str], expected_by_batch: Dict[str, FrozenSet[OperationKey]],
    scheduled: Set[OperationKey], unexpected: Set[OperationKey],
) -> Set[str]:
    incomplete = {
        bid for bid in batch_ids
        if not expected_by_batch.get(bid) or not expected_by_batch[bid] <= scheduled
    }
    incomplete.update(key[0] for key in unexpected)
    return incomplete


def _prepare_expected_keys(
    operations: Iterable[OpForScheduleAlgo], seeds: Iterable[ScheduleResult],
) -> Tuple[Set[OperationKey], Dict[str, FrozenSet[OperationKey]], Dict[int, str]]:
    # 待排工序的批次号与正整数编号由排产输入构建保证。
    keys = {(op.batch_id, op.id) for op in operations}
    keys.update(_result_key(item) for item in seeds)
    batch_by_op_id: Dict[int, str] = {}
    expected_by_batch: Dict[str, Set[OperationKey]] = {}
    for bid, op_id in keys:
        if op_id in batch_by_op_id and batch_by_op_id[op_id] != bid:
            raise ValueError("Expected operation identity belongs to conflicting batches.")
        batch_by_op_id[op_id] = bid
        expected_by_batch.setdefault(bid, set()).add((bid, op_id))
    return keys, {bid: frozenset(batch_keys) for bid, batch_keys in expected_by_batch.items()}, batch_by_op_id


def _result_key(result: ScheduleResult) -> OperationKey:
    # 旧种子在存储边界可能缺批次号或工序编号（空串 / 0），不能作为完成证据。
    if not result.batch_id or result.op_id <= 0:
        raise ValueError("Completion evidence requires a batch and positive operation ID.")
    return result.batch_id, result.op_id


def _has_time_range(result: ScheduleResult) -> bool:
    start, end = result.start_time, result.end_time
    # Zero-duration operations are legal and still satisfy their expected ID.
    return start is not None and end is not None and end >= start


def _failure_batches(details: Iterable[Dict[str, Any]], batch_by_op_id: Dict[int, str]) -> Set[str]:
    batches: Set[str] = set()
    for detail in details:
        # Failure details come only from ScheduleRunState._failure_detail: op_id and a non-empty batch_id.
        bid = detail["batch_id"]
        matched = batch_by_op_id.get(detail["op_id"])
        if matched and matched != bid:
            raise ValueError("Failure evidence disagrees with the expected operation batch.")
        batches.add(bid)
    return batches
