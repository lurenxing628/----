"""Decode checkpoints for graph-mode SGS: snapshot after k picks, resume orders that share the prefix.

Why this is exact. In graph mode the loop picks, at every step, the ready operation with the
smallest (dynamic penalty, graph key, dispatch key). The dynamic components depend only on the run
state, which later picks never alter. Let P be the picks of a decode after k steps and m the largest
position of any pick in the graph-key-sorted operation order. For a new key map whose sorted order
agrees with the old one on positions 0..m, every pairwise comparison involving a prefix pick is
unchanged (operations at positions > m lose to every prefix pick under both maps), so the first k
picks and the state after them are identical. The resume entry checks exactly that prefix; any
other mismatch fails loudly. Checkpoints are an optimizer-internal acceleration for trial decodes:
they never write times for mutable operations, and the adopted candidate is still a complete decode.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, NoReturn, Optional, Sequence, Tuple

from core.algorithm_runtime.run_state import ScheduleRunState
from core.infrastructure.errors import ValidationError

from .sgs_checkpoint_inputs import input_record, input_value

CHECKPOINT_FIELD = "decode_checkpoint"
_PROGRESS_SETS = ("completed_or_fixed_op_ids", "blocked_op_ids", "ready_op_ids")
_STATIC_CONTEXT_KEYS = ("enabled", "schedulable_op_ids", "fixed_op_ids", "fixed_op_sources_by_op_id",
                        "predecessor_op_ids_by_op_id", "successor_op_ids_by_op_id", "sort_key_by_op_id",
                        "piece_scope", "score_enabled")


def _invalid(message: str, *, reason: str) -> NoReturn:
    raise ValidationError(message, field=CHECKPOINT_FIELD, details={"reason": reason})


@dataclass(frozen=True)
class DecodeCheckpoint:
    """State of one graph-mode decode after ``position`` picks, with the prefix a reuse must share."""

    position: int
    prefix_op_ids: Tuple[int, ...]
    picked_op_ids: Tuple[int, ...]
    signature: str
    state: ScheduleRunState
    next_idx: Dict[str, int]
    graph_progress: Dict[str, Any]
    warnings: Tuple[str, ...]

    @property
    def prefix_length(self) -> int:
        return len(self.prefix_op_ids)


class DecodeCheckpointRequest:
    """Pick counts at which the loop must snapshot; captured checkpoints are handed to ``sink``."""

    def __init__(self, positions: Iterable[int], sink: Callable[[DecodeCheckpoint], None], *,
                 tail_reuse: Optional[Any] = None, check_budget: Optional[Callable[[int], None]] = None) -> None:
        cleaned = set()
        for value in positions:
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                _invalid("解码断点位置必须是正整数。", reason="decode_checkpoint_bad_position")
            cleaned.add(int(value))
        if not cleaned:
            _invalid("解码断点位置不能为空。", reason="decode_checkpoint_bad_position")
        if not callable(sink):
            _invalid("解码断点必须提供接收函数。", reason="decode_checkpoint_bad_sink")
        if check_budget is not None and not callable(check_budget):
            _invalid("解码预算检查必须是函数。", reason="decode_checkpoint_bad_budget_check")
        self.positions: FrozenSet[int] = frozenset(cleaned)
        self.sink = sink
        self.signature: Optional[str] = None
        self.warnings: Tuple[str, ...] = ()
        self.captured = 0
        self.tail_reuse = tail_reuse
        self.check_budget = check_budget

    def arm(self, *, signature: str, warnings: Sequence[str]) -> None:
        self.signature = str(signature)
        self.warnings = tuple(str(item) for item in warnings)
        if self.tail_reuse is not None:
            self.tail_reuse.arm(self.signature)


def graph_key_order(graph_state: Dict[str, Any]) -> List[int]:
    """Operations sorted by graph priority key; ties by op_id so the prefix check stays conservative."""
    keys = graph_state.get("graph_priority_key_by_op_id") or {}
    if not graph_state.get("score_enabled") or not keys:
        _invalid("解码断点只支持启用图评分键的图模式派工。", reason="decode_checkpoint_requires_graph_keys")
    return sorted(keys, key=lambda op_id: (keys[op_id], op_id))


class CheckpointPlan:
    """Per-decode bookkeeping for an armed request: pick sequence plus captures at the asked positions."""

    def __init__(self, request: DecodeCheckpointRequest, *, graph_state: Dict[str, Any]) -> None:
        if request.signature is None:
            _invalid("解码断点请求尚未绑定本次解码的输入签名。", reason="decode_checkpoint_not_armed")
        self.request = request
        self.order = graph_key_order(graph_state)
        self.position_of = {op_id: index for index, op_id in enumerate(self.order)}
        self.picked: List[int] = []
        self.furthest = -1

    def record(self, op_id: int, position: int, *, state: ScheduleRunState, next_idx: Dict[str, int],
               graph_state: Dict[str, Any]) -> None:
        if self.request.tail_reuse is not None:
            return
        if op_id not in self.position_of:
            _invalid("解码断点遇到不在图评分键里的工序。", reason="decode_checkpoint_unknown_operation")
        self.picked.append(int(op_id))
        self.furthest = max(self.furthest, self.position_of[op_id])
        if position not in self.request.positions:
            return
        checkpoint = DecodeCheckpoint(
            position=int(position),
            prefix_op_ids=tuple(self.order[: self.furthest + 1]),
            picked_op_ids=tuple(self.picked),
            signature=str(self.request.signature),
            state=state.clone(),
            next_idx=dict(next_idx),
            graph_progress=snapshot_graph_progress(graph_state),
            warnings=tuple(self.request.warnings),
        )
        self.request.captured += 1
        self.request.sink(checkpoint)


def plan_decode_checkpoints(request: Optional[DecodeCheckpointRequest], *, graph_state: Optional[Dict[str, Any]]) -> Optional[CheckpointPlan]:
    if request is None:
        return None
    if graph_state is None:
        _invalid("解码断点只支持图模式派工。", reason="decode_checkpoint_requires_graph_mode")
    return CheckpointPlan(request, graph_state=graph_state)


def snapshot_graph_progress(graph_state: Dict[str, Any]) -> Dict[str, Any]:
    progress: Dict[str, Any] = {name: set(graph_state[name]) for name in _PROGRESS_SETS}
    progress["remaining_predecessor_count_by_op_id"] = dict(graph_state["remaining_predecessor_count_by_op_id"])
    progress["schedulable_op_ids"] = frozenset(graph_state["op_by_id"])
    progress["checkpoint_priority_keys"] = dict(graph_state.get("graph_priority_key_by_op_id", {}))
    if "end_time_by_op_id" in graph_state:
        progress["end_time_by_op_id"] = dict(graph_state["end_time_by_op_id"])
    return progress


def resume_graph_progress(checkpoint: DecodeCheckpoint, *, graph_state: Optional[Dict[str, Any]],
                          next_idx: Dict[str, int]) -> int:
    """Validate the prefix against the new keys, then restore graph progress; returns the pick count."""
    if graph_state is None:
        _invalid("断点续排只支持图模式派工。", reason="decode_checkpoint_requires_graph_mode")
    progress = checkpoint.graph_progress
    if progress["schedulable_op_ids"] != frozenset(graph_state["op_by_id"]):
        _invalid("断点续排的待排工序集合与断点不一致。", reason="decode_checkpoint_scope_mismatch")
    order = graph_key_order(graph_state)
    if tuple(order[: checkpoint.prefix_length]) != checkpoint.prefix_op_ids:
        _invalid("断点续排要求候选顺序在断点已排到的名次之前完全一致。", reason="decode_checkpoint_prefix_mismatch")
    for name in _PROGRESS_SETS:
        graph_state[name] = set(progress[name])
    graph_state["remaining_predecessor_count_by_op_id"] = dict(progress["remaining_predecessor_count_by_op_id"])
    if "end_time_by_op_id" in progress:
        graph_state["end_time_by_op_id"] = dict(progress["end_time_by_op_id"])
    next_idx.clear()
    next_idx.update(checkpoint.next_idx)
    return int(checkpoint.position)


def decode_input_signature(*, operations: Sequence[Any], batches: Dict[str, Any], batch_order: Dict[str, int],
                           params: Any, machine_downtimes: Any, resource_pool: Any, seed_results: Any,
                           graph_ready_context: Any, readiness_gate_enabled: bool, strict_mode: bool,
                           calendar_signature: Any, warnings: Sequence[str] = ()) -> str:
    """Digest of every decode input except the graph priority keys (the only thing a reuse may change)."""
    parts: List[Any] = [
        tuple(input_record(op, field="operations") for op in operations),
        tuple((key, input_record(batch, field="batches")) for key, batch in batches.items()),
        input_value(batch_order, field="batch_order"),
        input_value((params.dispatch_mode_key, params.dispatch_rule_spec.token, params.base_time,
                     params.end_dt_exclusive, params.strategy.value, params.auto_assign_enabled,
                     params.used_params), field="params"),
        input_value(machine_downtimes, field="machine_downtimes"),
        input_value(resource_pool, field="resource_pool"),
        tuple(_seed_signature(result) for result in list(seed_results or [])),
        _context_signature(graph_ready_context),
        bool(readiness_gate_enabled), bool(strict_mode), calendar_signature, tuple(warnings),
    ]
    return hashlib.sha1(repr(parts).encode("utf-8")).hexdigest()


def _seed_signature(result: Any) -> Any:
    from core.algorithm_contracts.schedule_point_evidence import point_seed_valid

    from ..seed import seed_external_group_key
    fields = tuple(getattr(result, name, None) for name in (
        "op_id", "op_code", "batch_id", "seq", "machine_id", "operator_id", "start_time", "end_time",
        "source", "op_type_name", "seed_source", "state_revision"))
    return input_value((fields, seed_external_group_key(result), point_seed_valid(result)), field="seed_results")


def _context_signature(context: Any) -> Any:
    if not isinstance(context, dict):
        return input_value(context, field="graph_ready_context")
    return tuple((key, input_value(context.get(key), field="graph_ready_context." + key)) for key in _STATIC_CONTEXT_KEYS)


def decode_output_digest(results: Sequence[Any], summary: Any) -> str:
    """Content digest of a decode outcome; identical digests are the equivalence proof for a resumed decode."""
    rows = tuple(
        tuple(repr(getattr(row, name, None)) for name in (
            "op_id", "op_code", "batch_id", "seq", "machine_id", "operator_id", "start_time", "end_time",
            "source", "op_type_name", "seed_source"))
        for row in results
    )
    summary_part = (
        bool(summary.success), int(summary.total_ops), int(summary.scheduled_ops), int(summary.failed_ops),
        tuple(str(item) for item in summary.warnings), tuple(str(item) for item in summary.errors),
        repr(list(getattr(summary, "failure_details", []) or [])),
    )
    return hashlib.sha1(repr((rows, summary_part)).encode("utf-8")).hexdigest()


__all__ = [
    "CHECKPOINT_FIELD",
    "CheckpointPlan",
    "DecodeCheckpoint",
    "DecodeCheckpointRequest",
    "decode_input_signature",
    "decode_output_digest",
    "graph_key_order",
    "plan_decode_checkpoints",
    "resume_graph_progress",
    "snapshot_graph_progress",
]
