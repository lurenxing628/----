"""Reuse a reference suffix only after the trial's scheduling state reconverges.

This is an internal decode accelerator, not seed_results injection. A changed middle
is scheduled normally. At a reference checkpoint, all inputs that can affect future
fixed-resource picks must match, including remaining priorities and dependency ends.
Then independent containers install the already decoded suffix in one batch.
An optimizer must still validate an adopted trial with a separate full decode.
"""
from __future__ import annotations

from datetime import datetime

from core.algorithm_runtime.resource_quality import MachineTypeState
from core.infrastructure.errors import ValidationError

from .sgs_checkpoint_tail_bulk import install_reconverged_tail

_STATE_FIELDS = ("base_time", "external_group_cache", "machine_timeline", "operator_timeline",
                 "machine_busy_hours", "operator_busy_hours", "last_end_by_machine", "errors",
                 "blocked_batches", "failed_count", "seed_count", "initial_scheduled_count",
                 "missing_seed_machine_count", "missing_seed_operator_count", "missing_seed_machine_samples",
                 "missing_seed_operator_samples", "failure_details", "batch_failure_sources")
_PROGRESS_FIELDS = ("completed_or_fixed_op_ids", "blocked_op_ids", "ready_op_ids",
                    "remaining_predecessor_count_by_op_id")


def _type_history_without_ids(types):
    """IDs cannot break an insertion tie inside a positive, disjoint occupied segment.

Future positive operations cannot overlap these intervals. Therefore identical
time/type histories have identical changeover penalties even if the changed middle
put different operation IDs into equal slots. Zero-length/overlapping rows decline.
    """
    result = {}
    for machine, rows in types._entries.items():
        previous_end = None
        projected = []
        for start, end, _op_id, op_type in rows:
            if (type(start) is not datetime or type(end) is not datetime or start >= end
                    or (previous_end is not None and start < previous_end)):
                return None
            projected.append((start, end, op_type))
            previous_end = end
        result[machine] = projected
    return result


def _same_types(left, right):
    if type(left) is not MachineTypeState or type(right) is not MachineTypeState or dict(left) != dict(right):
        return False
    if left._entries == right._entries:
        return True
    projected = _type_history_without_ids(left)
    return projected is not None and projected == _type_history_without_ids(right)


def _same_future_state(state, reference, graph, progress):
    if state.failed_count or reference.failed_count or len(state.results) != len(reference.results):
        return False
    if any(getattr(state, field) != getattr(reference, field) for field in _STATE_FIELDS):
        return False
    if not _same_types(state.last_op_type_by_machine, reference.last_op_type_by_machine):
        return False
    if any(graph[field] != progress[field] for field in _PROGRESS_FIELDS):
        return False
    remaining = set(graph["op_by_id"]) - graph["completed_or_fixed_op_ids"]
    batches = {graph["op_by_id"][op_id][0] for op_id in remaining}
    if any(state.prev_end(batch) != reference.prev_end(batch) for batch in batches):
        return False
    old_keys = progress.get("checkpoint_priority_keys", {})
    if any(graph["graph_priority_key_by_op_id"][op_id] != old_keys.get(op_id) for op_id in remaining):
        return False
    return _same_dependency_ends(remaining, graph, progress)


def _same_dependency_ends(remaining, graph, progress):
    needed_ends = set()
    for op_id in remaining:
        needed_ends.update(graph["predecessor_op_ids_by_op_id"].get(op_id, ()))
    current_ends, old_ends = graph.get("end_time_by_op_id", {}), progress.get("end_time_by_op_id", {})
    return all(current_ends.get(op_id) == old_ends.get(op_id) for op_id in needed_ends)


class DecodeTailReuse:
    def __init__(self, checkpoints, *, check_budget=None):
        self.checkpoints = {item.position: item for item in checkpoints}
        self.final = max(checkpoints, key=lambda item: item.position) if checkpoints else None
        self.check_budget = check_budget
        self.checks = 0
        self.reused_picks = 0
        self.bulk_installs = 0
        self.reason = "state_not_reconverged"
        if self.final is None or self.final.position != len(self.final.prefix_op_ids):
            self.reason = "missing_complete_reference"

    def arm(self, signature):
        if any(item.signature != signature for item in self.checkpoints.values()):
            raise ValidationError("尾段复用的解码输入与参考解不一致。", field="decode_checkpoint",
                                  details={"reason": "decode_checkpoint_tail_signature_mismatch"})

    def try_complete(self, position, *, state, next_idx, graph_state, eligible):
        if not eligible:
            self.reason = "unsupported_native_fixed_resource_context"
            return False
        checkpoint = self.checkpoints.get(position)
        if (checkpoint is None or self.final is None or position >= self.final.position
                or self.final.position != len(graph_state["op_by_id"])):
            return False
        self.checks += 1
        if checkpoint.next_idx != next_idx:
            return False
        if not _same_future_state(state, checkpoint.state, graph_state, checkpoint.graph_progress):
            return False
        suffix = self.final.state.results[len(checkpoint.state.results):]
        if len(suffix) != self.final.position - position or self.final.state.failed_count:
            return False
        if not install_reconverged_tail(checkpoint, self.final, state=state, next_idx=next_idx,
                                       graph_state=graph_state, check_budget=self.check_budget):
            self.reason = "unsupported_native_tail_snapshot"
            return False
        self.reused_picks += len(suffix)
        self.bulk_installs += 1
        self.reason = "exact_state_reconvergence"
        return True


__all__ = ["DecodeTailReuse"]
