"""Install an already proved, reconverged native tail without replaying occupancy.

This helper does not decide whether two scheduling states have the same future.
The caller must establish that proof first. It prepares independent containers,
preserves the trial's changed history, and only publishes after the final budget
check. Timeline owners receive fresh identities; no live scoring cache is reused.
"""
from bisect import bisect_left
from collections import deque
from copy import copy, deepcopy
from datetime import datetime
from typing import Any, Dict

from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_runtime.native_snapshot import make_class_guard
from core.algorithm_runtime.resource_demand import ResourceDemand
from core.algorithm_runtime.resource_quality import MachineTypeState
from core.algorithm_runtime.run_state import ScheduleRunState

_STATE_GUARD = make_class_guard(ScheduleRunState)
_TYPES_GUARD = make_class_guard(MachineTypeState)
_DEMAND_GUARD = make_class_guard(ResourceDemand)
_RESULT_FIELDS = frozenset(ScheduleResult.__dataclass_fields__)
_RESULT_SCALARS = (str, int, datetime, type(None))
_GRAPH_SETS = ("completed_or_fixed_op_ids", "blocked_op_ids", "ready_op_ids")


def _supported(state, checkpoint, final):
    for candidate in (state, checkpoint.state, final.state):
        if not _STATE_GUARD(candidate) or not _TYPES_GUARD(candidate.last_op_type_by_machine):
            return False
    demand = state.last_op_type_by_machine.demand
    if demand is not None and not _DEMAND_GUARD(demand):
        return False
    # A complete capture must belong to the same reference trajectory, not just
    # an input signature shared by two different operation orders.
    return (final.picked_op_ids[:checkpoint.position] == checkpoint.picked_op_ids
            and final.state.results[:len(checkpoint.state.results)] == checkpoint.state.results)


def _copy_result(result):
    values = vars(result)
    if (type(result) is ScheduleResult and values.keys() == _RESULT_FIELDS
            and all(type(value) in _RESULT_SCALARS for value in values.values())):
        return ScheduleResult(**values)
    # Seed extensions may carry an extra witness. Preserve it without sharing
    # mutable row payloads with the reference or an earlier checkpoint.
    return deepcopy(result)


def _replace_changed_type_rows(prepared, current, reference):
    for machine, rows in current._entries.items():
        old_rows = reference._entries[machine]
        if rows == old_rows:
            continue
        final_rows = prepared._entries[machine]
        for old, changed in zip(old_rows, rows):
            if old == changed:
                continue
            index = bisect_left(final_rows, old)
            if index == len(final_rows) or final_rows[index] != old:
                return False
            # _same_types proved identical disjoint positive time/type slots.
            # Only the op_id can differ, so this replacement stays sorted.
            final_rows[index] = changed
    return True


def _clone_demand(demand):
    if demand is None:
        return None
    cloned = copy(demand)
    cloned._groups = {key: deque(value) for key, value in demand._groups.items()}
    cloned._by_id = {key: list(value) for key, value in demand._by_id.items()}
    cloned._by_token = dict(demand._by_token)
    cloned._by_batch = {key: set(value) for key, value in demand._by_batch.items()}
    cloned._window_tokens = set(demand._window_tokens)
    cloned._blocking_counts = dict(demand._blocking_counts)
    return cloned


def _prepare_types(state, checkpoint, prepared, suffix):
    current, reference = state.last_op_type_by_machine, checkpoint.state.last_op_type_by_machine
    types = prepared.last_op_type_by_machine
    if not _replace_changed_type_rows(types, current, reference):
        return False
    final_events = types.demand_events
    if final_events[:len(reference.demand_events)] != reference.demand_events:
        return False
    types.demand_events = list(current.demand_events)
    types.demand = _clone_demand(current.demand)
    # Retain the small native lifecycle transition. Resource occupancy, type
    # insertion, busy-hour accumulation and graph-edge walks are all omitted.
    for result in suffix:
        types.complete(result.op_id)
    return True


def _prepare_progress(final, graph, suffix):
    progress: Dict[str, Any] = {key: set(final.graph_progress[key]) for key in _GRAPH_SETS}
    remaining = set(graph["op_by_id"]) - graph["completed_or_fixed_op_ids"]
    suffix_ids = {row.op_id for row in suffix}
    if (len(suffix_ids) != len(suffix) or suffix_ids != remaining
            or not set(graph["op_by_id"]).issubset(progress["completed_or_fixed_op_ids"])):
        return None
    progress["remaining_predecessor_count_by_op_id"] = dict(final.graph_progress["remaining_predecessor_count_by_op_id"])
    if "end_time_by_op_id" in graph:
        progress["end_time_by_op_id"] = dict(final.graph_progress["end_time_by_op_id"])
        # Completed operations that do not feed the suffix may have changed ends.
        progress["end_time_by_op_id"].update(graph["end_time_by_op_id"])
    return progress


def _prepare_results(state, checkpoint, final, check_budget):
    cut = len(checkpoint.state.results)
    results = [_copy_result(row) for row in state.results]
    for offset, row in enumerate(final.state.results[cut:]):
        if check_budget is not None and offset % 32 == 0:
            check_budget(checkpoint.position + offset)
        results.append(_copy_result(row))
    return results


def install_reconverged_tail(checkpoint, final, *, state, next_idx, graph_state, check_budget=None):
    """Return False for an unsupported native snapshot; never weaken its proof.

    All work before the final updates is private. A budget callback may raise at
    any preparation boundary without leaving a partly installed trial result.
    The caller exits the dispatch loop immediately after a successful install.
    """
    if not _supported(state, checkpoint, final):
        return False
    if check_budget is not None:
        check_budget(checkpoint.position)
    suffix = final.state.results[len(checkpoint.state.results):]
    progress = _prepare_progress(final, graph_state, suffix)
    if progress is None:
        return False
    prepared = final.state.clone()
    if not _prepare_types(state, checkpoint, prepared, suffix):
        return False
    prepared.results = _prepare_results(state, checkpoint, final, check_budget)
    # Copy the final busy-hour totals bit for bit: the proof established equal
    # starting accumulators and identical future additions, including rounding.
    # Batch histories already complete at the join belong to the changed trial.
    prepared.batch_progress = dict(state.batch_progress)
    for batch in {graph_state["op_by_id"][row.op_id][0] for row in suffix}:
        prepared.batch_progress[batch] = final.state.batch_progress[batch]
    prepared.errors = list(state.errors)
    prepared.failure_details = deepcopy(state.failure_details)
    prepared.batch_failure_sources = deepcopy(state.batch_failure_sources)
    prepared_next = dict(final.next_idx)
    if check_budget is not None:
        check_budget(final.position - 1)
    # No callbacks or result publication can observe the intermediate updates.
    vars(state).update(vars(prepared))
    next_idx.clear()
    next_idx.update(prepared_next)
    graph_state.update(progress)
    return True


__all__ = ["install_reconverged_tail"]
