"""Choose a quality-ranked starting reference and formally check any constructive order.

The due-date proposal uses observed durations only as a heuristic. Its estimates never enter
the incumbent, fingerprints, or final score: the ordinary SGS evaluator remains authoritative.
"""
from __future__ import annotations

from typing import Any, Optional

from .optimizer_graph_ready_iterated_greedy_acceptance import PoolEntry
from .optimizer_graph_ready_iterated_greedy_contract import _BudgetExhausted


def start_reference(search: Any) -> None:
    report = search.report
    report["starting_incumbent_origin"] = str(search.best.get("candidate_origin") or "baseline")
    report["starting_incumbent_score"] = list(search.best["score"])
    search._seed_solution_pool()
    selected = search.solution_pool.pick(search.pool_rnd)
    if selected is not None:
        search._activate_entry(selected)
    source = selected.candidate if selected is not None else search.best
    report["parent_origin"] = str(source.get("candidate_origin") or "baseline")
    report["parent_score"] = list(source["score"])
    search._require_budget()
    entry = _due_date_reference(search, source)
    if entry is None:
        entry = search._decode_entry(search.parent.order)
    if entry is None:
        raise _BudgetExhausted("parent_order_rejected")
    report["parent_order_score"] = list(entry.score)
    report["parent_order_consistent"] = entry.score == tuple(source["score"])
    search.reference = entry
    search.solution_pool.refresh(entry)
    report["pool"]["initial_entries"] = len(search.solution_pool.entries)


def _due_date_reference(search: Any, source: Any) -> Optional[PoolEntry]:
    seed = search.report["initial_seed"]
    if not search.limits.due_date_seed:
        seed.update(status="disabled", reason="disabled")
        return None
    if search.report["objective_name"] != "min_overdue" or search.graph_context is None:
        seed.update(status="not_applicable", reason="objective_or_context")
        return None
    from .optimizer_graph_ready_iterated_greedy_seed import build_due_date_seed

    started = search.clock()
    # Keep at least 95% of the remaining stage time for formal SGS work. The common
    # global deadline and the seed's 2048 distinct-probe safety cap still apply.
    construction_deadline = started + max(search.deadline - started, 0.0) * 0.05
    seed["construction_time_budget_ms"] = max(int((construction_deadline - started) * 1000), 0)
    proposal = build_due_date_seed(parent=search.parent, candidate=source, metrics=search.metrics,
                                   graph_context=search.graph_context, start_dt=search.start_dt,
                                   clock=search.clock, deadline=construction_deadline)
    seed.update({key: value for key, value in proposal.items() if key != "order"})
    seed["runtime_ms"] = max(int((search.clock() - started) * 1000), 0)
    order = proposal["order"]
    if order is None:
        return None
    before, improvements = search.report["decodes"], search.report["improvements"]
    try:
        entry = search._decode_entry(order)
    except _BudgetExhausted as exc:
        seed.update(status="skipped_by_budget", reason=exc.reason)
        raise
    finally:
        seed["decodes"] = search.report["decodes"] - before
    seed["incumbent_improved"] = search.report["improvements"] > improvements
    if entry is None:
        seed.update(status="rejected", reason="decode_rejected")
        return None
    seed["validated_score"] = list(entry.score)
    if entry.score > tuple(source["score"]):
        seed.update(status="rejected", reason="worse_than_source")
        return None
    seed.update(status="used_as_reference", reason=None, selected=True)
    return entry


__all__ = ["start_reference"]
