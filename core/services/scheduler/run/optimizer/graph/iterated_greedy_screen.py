"""Cheap insertion ordering; observed durations are hints, never publishable results.

Like routing insertion evaluators, this screen ranks moves before formal feasibility
work. The serial resource approximation deliberately omits calendars and gap filling.
Only SGS can decide whether a shortlisted move is feasible or improves the objective.
"""
from __future__ import annotations

from core.shared.strict_parse import is_exact_finite_number


class InsertionScreen:
    def __init__(self, search, reference):
        self.search = search
        self.rows = {}
        self.due = {}
        self.weights = {}
        self.predecessors = search.parent.predecessors
        for row in reference.candidate["results"]:
            if row.op_id not in self.predecessors:
                continue
            duration = (row.end_time - row.start_time).total_seconds() / 3600.0
            if duration < 0:
                continue
            self.rows[row.op_id] = (str(row.batch_id), row.machine_id, row.operator_id, duration,
                                    row.op_type_id or "")
            metric = search.metrics[row.op_id]
            due = metric["due_deadline_hours"]
            if is_exact_finite_number(due):
                self.due[str(row.batch_id)] = float(due)
            pressure = metric["due_pressure"]
            weighted = metric["weighted_due_pressure"]
            weighted_hours = metric["weighted_processing_hours"]
            if pressure > 0:
                self.weights[str(row.batch_id)] = weighted / pressure
            elif duration > 0 and type(weighted_hours) in (int, float) and weighted_hours > 0:
                self.weights[str(row.batch_id)] = duration / float(weighted_hours)
            else:
                self.weights[str(row.batch_id)] = 1.0
        self.supported = set(self.rows) == set(reference.order)

    def _advance_state(self, ops, ends, machines, operators, batches, families, switches):
        """Point events still finish for successors but occupy no resource and never switch types.

        A switch needs two known type identities; an unknown type resets the machine's family.
        """
        rows = self.rows
        predecessors = self.predecessors
        for op_id in ops:
            batch, machine, operator, duration, family = rows[op_id]
            ready = max((ends.get(previous, 0.0) for previous in predecessors[op_id]), default=0.0)
            finish = max(ready, machines.get(machine, 0.0), operators.get(operator, 0.0)) + duration
            ends[op_id] = finish
            if duration > 0:
                if machine:
                    machines[machine] = finish
                    previous_family = families.get(machine)
                    if previous_family and family and previous_family != family:
                        switches += 1
                    families[machine] = family
                if operator:
                    operators[operator] = finish
            batches[batch] = max(batches.get(batch, 0.0), finish)
        return switches

    def _objective_key(self, batches, switches):
        tardiness = [(batch, max(end - self.due[batch], 0.0)) for batch, end in batches.items() if batch in self.due]
        overdue, total = sum(value > 0 for _, value in tardiness), sum(value for _, value in tardiness)
        makespan = max(batches.values(), default=0.0)
        objective = self.search.report["objective_name"]
        if objective == "min_overdue":
            return overdue, total, makespan
        if objective == "min_tardiness":
            return total, overdue, makespan
        if objective == "min_weighted_tardiness":
            weighted = sum(value * self.weights[batch] for batch, value in tardiness)
            return weighted, total, overdue, makespan
        if objective == "min_changeover":
            return switches, overdue, total, makespan
        return makespan, overdue, total

    def ranked_positions(self, without, op_id, positions, *, anchor, diversify):
        """Retain the queue after its first item; an estimate never rejects a move."""
        ranked = []
        best_position, best_score = None, None
        orders = [(position, tuple(without[:position] + [op_id] + without[position:])) for position in positions]
        targets = (
            sorted({position for position, order in orders if order not in self.search.scores})
            if orders and self.supported
            else ()
        )
        target_idx = 0
        cursor = 0
        c_ends, c_machines, c_operators, c_batches, c_families = {}, {}, {}, {}, {}
        c_switches = 0
        prefix_by_pos = {}
        for position, order in orders:
            self.search._require_budget()
            known = self.search.scores.get(order)
            if known is not None:
                self.search.report["duplicate_decision_pruned"] += 1
                self.search._record_local_reuse("local_trial_reused")
                if known[1] and (best_score is None or known[0] < best_score):
                    best_position, best_score = position, known[0]
                continue
            if not self.supported:
                estimate = ()
            else:
                if position not in prefix_by_pos:
                    while target_idx < len(targets) and targets[target_idx] <= position:
                        next_pos = targets[target_idx]
                        c_switches = self._advance_state(
                            without[cursor:next_pos],
                            c_ends,
                            c_machines,
                            c_operators,
                            c_batches,
                            c_families,
                            c_switches,
                        )
                        cursor = next_pos
                        prefix_by_pos[next_pos] = (
                            dict(c_ends),
                            dict(c_machines),
                            dict(c_operators),
                            dict(c_batches),
                            dict(c_families),
                            c_switches,
                        )
                        target_idx += 1
                ends, machines, operators, batches, families, p_switches = prefix_by_pos.pop(position)
                switches = self._advance_state(
                    order[position:], ends, machines, operators, batches, families, p_switches
                )
                estimate = self._objective_key(batches, switches)
            ranked.append((estimate, abs(position - anchor), position))
        if diversify:
            # Change the hint only inside equal estimate tiers. Stronger
            # estimates keep their place; ties need not always keep the old rank.
            self.search.rnd.shuffle(ranked)
            ranked.sort(key=lambda row: row[0])
        else:
            ranked.sort()
        report = self.search.report["local_search"]
        report["screened_positions"] += len(ranked)
        return [row[-1] for row in ranked], best_position, best_score


__all__ = ["InsertionScreen"]
