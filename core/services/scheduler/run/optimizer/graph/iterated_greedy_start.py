"""Choose a quality-ranked starting reference and formally check any constructive order.

The due-date proposal uses observed durations only as a heuristic. Its estimates never enter
the incumbent, fingerprints, or final score: the ordinary SGS evaluator remains authoritative.
"""
from __future__ import annotations

from typing import Any, List, Optional

from .iterated_greedy_acceptance import PoolEntry
from .iterated_greedy_contract import _BudgetExhausted
from .iterated_greedy_reference import activate_entry, capture_reference, decode_reference, seed_solution_pool


def start_reference(search: Any) -> None:
    """Start from the best pool tier; a pool entry whose capture fails yields to the next one (bounded by the pool)."""
    seed_solution_pool(search)
    for index, entry in enumerate(_start_attempts(search)):
        activate_entry(search, entry)
        source = entry.candidate
        search._require_budget()
        reference = _due_date_reference(search, source) if index == 0 else None
        if reference is not None:
            break
        reference = capture_reference(search, entry)
        if reference is not None:
            break
    else:
        raise _BudgetExhausted("parent_order_rejected")
    search.reference = reference
    search.solution_pool.refresh(reference)


def _start_attempts(search: Any) -> List[PoolEntry]:
    """The pool's random best-tier pick first, then the remaining entries by score."""
    selected = search.solution_pool.pick(search.pool_rnd)
    if selected is None:
        return []
    rest = sorted((entry for entry in search.solution_pool.entries if entry is not selected),
                  key=lambda entry: (entry.score, entry.sequence))
    return [selected] + rest


def _due_date_reference(search: Any, source: Any) -> Optional[PoolEntry]:
    if not search.limits.due_date_seed or search.report["objective_name"] != "min_overdue":
        return None
    from .iterated_greedy_seed import build_due_date_seed

    order = build_due_date_seed(parent=search.parent, candidate=source, metrics=search.metrics,
                                graph_context=search.graph_context, start_dt=search.start_dt,
                                clock=search.clock, deadline=search.deadline)
    if order is None:
        return None
    entry = decode_reference(search, order, before=source, reference_kind="due_date_seed")
    if entry is None or entry.score > tuple(source["score"]):
        return None
    return entry


__all__ = ["start_reference"]
