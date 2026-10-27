"""Coupled resource windows propose order decisions, never resource or time results.

OR-Tools scheduling LNS unions windows on different resources. Here a bounded
connected window follows the observed machine/operator queues and DAG edges.
Moving its operations as one block can cross a barrier that single insertions
cannot improve. SGS must still validate every proposed complete order.
"""
from __future__ import annotations

from collections import defaultdict

from core.algorithm_contracts.changeover_events import type_transition
from core.errors import ValidationError

_MAX_JOINT_SIZE = 3
_INDEX_KEY = "joint_window_index"


class _WindowIndex:
    """Build resource adjacency once per decoded reference, O(n log n)."""

    def __init__(self, search, reference):
        self.positions = {op_id: rank for rank, op_id in enumerate(reference.order)}
        self.rows = {int(row.op_id): row for row in reference.candidate["results"]
                     if int(row.op_id) in self.positions}
        self.resources, self.adjacent, self.switches = {}, defaultdict(set), defaultdict(int)
        queues = defaultdict(list)
        for op_id, row in self.rows.items():
            resources = frozenset((kind, str(value)) for kind, value in (
                ("machine_id", row.machine_id), ("operator_id", row.operator_id)) if value)
            self.resources[op_id] = resources
            for resource in resources:
                queues[resource].append(op_id)
        for resource, queue in queues.items():
            search._require_budget()
            queue.sort(key=lambda op_id: (self.rows[op_id].start_time, self.rows[op_id].end_time,
                                          self.positions[op_id]))
            self._link_queue(resource, queue)

    def _link_queue(self, resource, queue):
        for left, right in zip(queue, queue[1:]):
            self.adjacent[left].add(right)
            self.adjacent[right].add(left)
        if resource[0] == "machine_id":
            self._count_switches(queue)

    def _count_switches(self, queue):
        """Adjacent timed rows switch only between two known type identities; point events are skipped."""
        rows = self.rows
        timed = [op_id for op_id in queue if rows[op_id].start_time != rows[op_id].end_time]
        for left, right in zip(timed, timed[1:]):
            if type_transition(rows[left].op_type_id, rows[right].op_type_id, left, right) == 1:
                self.switches[left] += 1
                self.switches[right] += 1


def _index_for(search, reference):
    features = search._features(reference)
    index = features.get(_INDEX_KEY)
    if index is None:
        index = _WindowIndex(search, reference)
        features[_INDEX_KEY] = index
    return index, features


def _pressure(search, index, features, op_id):
    metric = search.metrics[op_id]
    signal = features["signals"].get(op_id, 0.0)
    due_pressure = float(metric["due_pressure"])
    finish = index.rows[op_id].end_time
    objective = search.report["objective_name"]
    if objective == "min_weighted_tardiness":
        weighted = float(metric["weighted_due_pressure"])
        factor = weighted / due_pressure if due_pressure > 0 else 1.0
        return -signal * factor, -weighted, -signal, -index.positions[op_id]
    if objective == "min_changeover":
        return -index.switches[op_id], -signal, -due_pressure, -index.positions[op_id]
    if objective in ("min_overdue", "min_tardiness"):
        return -signal, -due_pressure, -int(bool(metric["is_on_critical_path"])), -index.positions[op_id]
    # Latest finish is the primary pressure for makespan-style objectives.
    return -finish.toordinal(), -finish.hour, -finish.minute, -finish.second


def _related(search, index, op_id):
    related = set(index.adjacent[op_id])
    related.update(search.parent.predecessors.get(op_id, ()))
    related.update(search.parent.successors.get(op_id, ()))
    return related.intersection(index.rows)


def _next_member(search, index, features, frontier, selected, related_by_op):
    resources = set().union(*(index.resources[op_id] for op_id in selected))
    anchor = index.rows[selected[0]].start_time

    def rank(op_id):
        novelty = len(index.resources[op_id] - resources)
        coupling = sum(op_id in neighbours for neighbours in related_by_op.values())
        distance = abs((index.rows[op_id].start_time - anchor).total_seconds())
        return (-novelty, -coupling, _pressure(search, index, features, op_id), distance, index.positions[op_id])

    return min(frontier, key=rank)


def joint_removed(search, reference, removed, size):
    """Return at most ``size`` (and three) mutable, related operation ids.

    Call only for the large-instance resource-window generator with its bounded
    destruction size. A one-operation neighbourhood stays a one-operation window.
    """
    count = min(int(size), _MAX_JOINT_SIZE, len(reference.order) - 1)
    if count <= 0 or not removed:
        return ()
    index, features = _index_for(search, reference)
    seeds = set(removed).intersection(index.rows)
    if not seeds:
        return ()
    seed = min(seeds, key=lambda op_id: (_pressure(search, index, features, op_id), index.positions[op_id]))
    selected, frontier = [seed], set()
    related_by_op = {}
    while len(selected) < count:
        search._require_budget()
        neighbours = _related(search, index, selected[-1])
        related_by_op[selected[-1]] = neighbours
        frontier.update(neighbours)
        frontier.difference_update(selected)
        if not frontier:
            break
        selected.append(_next_member(search, index, features, frontier, selected, related_by_op))
    return tuple(sorted(selected, key=index.positions.__getitem__))


def _selected_order(search, index, features, selected):
    """Topologically sort only the tiny relaxed set, pressure first."""
    pending, result = set(selected), []
    while pending:
        ready = [op_id for op_id in pending if not pending.intersection(search.parent.predecessors[op_id])]
        if not ready:
            raise ValidationError("GraphReady 联合资源窗遇到循环前后置关系。", field="graph_ready_iterated_greedy",
                                  details={"reason": "graph_ready_ig_cyclic_order"})
        picked = min(ready, key=lambda op_id: (_pressure(search, index, features, op_id), index.positions[op_id]))
        result.append(picked)
        pending.remove(picked)
    return tuple(result)


def _block_bounds(parent, selected, kept):
    positions = {op_id: rank for rank, op_id in enumerate(kept)}
    low, high = 0, len(kept)
    for op_id in selected:
        low = max(low, max((positions[previous] + 1 for previous in parent.predecessors[op_id]
                            if previous in positions), default=0))
        high = min(high, min((positions[following] for following in parent.successors[op_id]
                              if following in positions), default=len(kept)))
    return low, high


def joint_orders(search, reference, removed):
    """Propose up to two joint block moves; the kept order is never rearranged.

    The common insertion interval enforces every external DAG edge, while the
    small block's topological sort enforces its internal edges. If an untouched
    operation must stay between two selected operations there is no legal block;
    emit nothing and let ordinary insertions search that window instead.
    """
    if len(removed) < 2:
        return ()
    index, features = _index_for(search, reference)
    selected = set(removed)
    if not 2 <= len(selected) <= _MAX_JOINT_SIZE:
        return ()
    kept = tuple(op_id for op_id in reference.order if op_id not in selected)
    low, high = _block_bounds(search.parent, selected, kept)
    if low > high:
        return ()
    block = _selected_order(search, index, features, selected)
    first, last = min(index.positions[op_id] for op_id in selected), max(index.positions[op_id] for op_id in selected)
    window = search.limits.insertion_window
    targets = (max(low, min(first - window, high)), min(high, max(last - len(selected) + 1 + window, low)))
    result, seen = [], {reference.order}
    for target in targets:
        search._require_budget()
        order = kept[:target] + block + kept[target:]
        if order not in seen and _jointly_moved(order, selected, index.positions):
            result.append(order)
            seen.add(order)
        if len(result) >= 2:
            break
    return tuple(result)


def _jointly_moved(order, selected, before):
    return sum(op_id in selected and before[op_id] != rank for rank, op_id in enumerate(order)) >= 2


__all__ = ["joint_orders", "joint_removed"]
