"""Cheap insertion ordering; observed durations are hints, never publishable results.

Like routing insertion evaluators, this screen ranks moves before formal feasibility
work. The serial resource approximation deliberately omits calendars and gap filling.
Only SGS can decide whether a shortlisted move is feasible or improves the objective.
"""
from __future__ import annotations

import math


class InsertionScreen:
    def __init__(self, search, reference):
        self.search = search
        self.rows = {}
        self.due = {}
        self.weights = {}
        self.predecessors = search.parent.predecessors
        for row in reference.candidate.get("results", ()):
            if row.op_id not in self.predecessors:
                continue
            duration = (row.end_time - row.start_time).total_seconds() / 3600.0
            if not math.isfinite(duration) or duration < 0:
                continue
            self.rows[row.op_id] = (str(row.batch_id), row.machine_id, row.operator_id, duration, row.op_type_name)
            metric = search.metrics.get(row.op_id, {})
            due = metric.get("due_deadline_hours")
            if type(due) in (int, float) and math.isfinite(due):
                self.due[str(row.batch_id)] = float(due)
            pressure = metric.get("due_pressure", 0.0)
            weighted = metric.get("weighted_due_pressure", pressure)
            self.weights[str(row.batch_id)] = weighted / pressure if pressure > 0 else 1.0
        self.supported = set(self.rows) == set(reference.order)

    def _estimate(self, order):
        if not self.supported:
            return ()
        ends, machines, operators, batches, families = {}, {}, {}, {}, {}
        switches = 0
        for op_id in order:
            batch, machine, operator, duration, family = self.rows[op_id]
            ready = max((ends.get(previous, 0.0) for previous in self.predecessors[op_id]), default=0.0)
            finish = max(ready, machines.get(machine, 0.0), operators.get(operator, 0.0)) + duration
            ends[op_id] = finish
            if machine:
                machines[machine] = finish
                switches += int(machine in families and families[machine] != family)
                families[machine] = family
            if operator:
                operators[operator] = finish
            batches[batch] = max(batches.get(batch, 0.0), finish)
        return self._objective_key(ends, batches, switches)

    def _objective_key(self, ends, batches, switches):
        tardiness = [max(end - self.due[batch], 0.0) for batch, end in batches.items() if batch in self.due]
        overdue, total = sum(value > 0 for value in tardiness), sum(tardiness)
        makespan = max(ends.values(), default=0.0)
        objective = self.search.report["objective_name"]
        if objective == "min_overdue":
            return overdue, total, makespan
        if objective == "min_tardiness":
            return total, overdue, makespan
        if objective == "min_weighted_tardiness":
            weighted = sum(max(end - self.due[batch], 0.0) * self.weights[batch]
                           for batch, end in batches.items() if batch in self.due)
            return weighted, total, overdue, makespan
        if objective == "min_changeover":
            return switches, overdue, total, makespan
        return makespan, overdue, total

    def ranked_positions(self, without, op_id, positions, *, anchor, diversify=False):
        """Retain the queue after its first item; an estimate never rejects a move."""
        ranked = []
        for position in positions:
            self.search._require_budget()
            order = tuple(without[:position] + [op_id] + without[position:])
            if order in self.search.scores:
                self.search.report["duplicate_decision_pruned"] += 1
                continue
            ranked.append((self._estimate(order), abs(position - anchor), position))
        if diversify:
            # Change the hint only inside equal estimate tiers. Stronger
            # estimates keep their place; ties need not always keep the old rank.
            self.search.rnd.shuffle(ranked)
            ranked.sort(key=lambda row: row[0])
        else:
            ranked.sort()
        report = self.search.report["local_search"]
        report["screened_positions"] += len(ranked)
        return [row[-1] for row in ranked]

    def select(self, without, op_id, positions, *, anchor, limit):
        ranked = self.ranked_positions(without, op_id, positions, anchor=anchor)
        report = self.search.report["local_search"]
        report["shortlisted_positions"] += min(len(ranked), limit)
        return ranked[:limit]


__all__ = ["InsertionScreen"]
