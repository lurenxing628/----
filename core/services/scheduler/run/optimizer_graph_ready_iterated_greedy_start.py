"""Choose a quality-ranked starting reference and formally check any constructive order.

The due-date proposal uses observed durations only as a heuristic. Its estimates never enter
the incumbent, fingerprints, or final score: the ordinary SGS evaluator remains authoritative.
"""
from __future__ import annotations

from typing import Any, List, Optional

from .optimizer_graph_ready_iterated_greedy_acceptance import PoolEntry
from .optimizer_graph_ready_iterated_greedy_contract import _BudgetExhausted
from .optimizer_graph_ready_iterated_greedy_reference import activate_entry, capture_reference, seed_solution_pool


def start_reference(search: Any) -> None:
    """Start from the best pool tier; a pool entry whose capture fails yields to the next one (bounded by the pool)."""
    report = search.report
    report["starting_incumbent_origin"] = str(search.best.get("candidate_origin") or "baseline")
    report["starting_incumbent_score"] = list(search.best["score"])
    seed_solution_pool(search)
    for index, entry in enumerate(_start_attempts(search)):
        activate_entry(search, entry)
        source = entry.candidate
        _describe_parent(search, source)
        search._require_budget()
        reference = _due_date_reference(search, source) if index == 0 else None
        if reference is not None:
            report["reference_basis"] = "due_date_seed"
            break
        divergences = report["reference_capture_divergences"]
        reference = capture_reference(search, entry)
        if reference is not None:
            report["reference_basis"] = "parent_order"
            report["parent_order_score"] = list(reference.score)
            # Consistent means the capture reproduced the parent's schedule, not merely its score.
            report["parent_order_consistent"] = (report["reference_capture_divergences"] == divergences
                                                 and reference.score == tuple(source["score"]))
            break
        report["pool"]["start_captures_failed"] += 1
    else:
        raise _BudgetExhausted("parent_order_rejected")
    search.reference = reference
    search.solution_pool.refresh(reference)
    report["pool"]["initial_entries"] = len(search.solution_pool.entries)


def _start_attempts(search: Any) -> List[PoolEntry]:
    """The pool's random best-tier pick first, then the remaining entries by score."""
    selected = search.solution_pool.pick(search.pool_rnd)
    if selected is None:
        return []
    rest = sorted((entry for entry in search.solution_pool.entries if entry is not selected),
                  key=lambda entry: (entry.score, entry.sequence))
    return [selected] + rest


def _describe_parent(search: Any, source: Any) -> None:
    report = search.report
    report["parent_origin"] = str(source.get("candidate_origin") or "baseline")
    report["parent_score"] = list(source["score"])
    profile = (source.get("graph_ready_profile") or {}) if isinstance(source, dict) else {}
    report["parent_profile_slug"] = profile.get("weight_profile_slug")


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
