"""Reference solutions of the iterated greedy walk: the start pool, stagnation restarts and incumbent adoption.

A reference entry is the decoded parent order (its start-time operation order with its explicit resource
overrides) under the IG decode context (canonical profile, pick-rank keys). Capturing it is a full decode
that may reproduce the parent or drift; the capture is accounted separately from search decodes
(reproduced or divergent) and never as a rejection. A context change
that cannot capture its reference rolls back to the previous walk context, so a later resumed trial
can only fail its checkpoint check because of a real defect.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Optional

from .optimizer_graph_ready_iterated_greedy_acceptance import PoolEntry
from .optimizer_graph_ready_iterated_greedy_contract import _BudgetExhausted, ig_decode_profile
from .optimizer_graph_ready_iterated_greedy_moves import _parent_from_candidate
from .optimizer_graph_ready_profiles import GraphReadyWeightProfile


def seed_solution_pool(search: Any) -> None:
    """Offer the incumbent and every current elite to the bounded start pool (decision-key deduplicated)."""
    if search.operations is None or search.graph_context is None:
        return
    best = search._require_best()
    sources = [best]
    sources.extend(elite["candidate"] for elite in search.pool.elites)
    for candidate in sources:
        parent = _parent_from_candidate(candidate, operations=search.operations, graph_context=search.graph_context)
        if parent is None:
            continue
        search.solution_pool.add(PoolEntry(order=parent.order, score=tuple(candidate["score"]), candidate=candidate,
                                           batch_order=parent.batch_order, resource_overrides=parent.inherited,
                                           profile=search.profile))
    if not search.report["pool"]["initial_entries"]:
        search.report["pool"]["initial_entries"] = len(search.solution_pool.entries)


def activate_entry(search: Any, entry: PoolEntry) -> None:
    """Make the entry the walk's parent."""
    parent = replace(search.parent, order=entry.order, batch_order=entry.batch_order, inherited=entry.resource_overrides)
    search._set_parent(parent, entry.profile or search.profile)


def capture_reference(search: Any, entry: PoolEntry) -> Optional[PoolEntry]:
    """Decode a pool entry under the current context unless an equivalent decoded entry is already cached."""
    if entry.decoded_order and entry.checkpoints:
        return entry
    search.capturing = entry.candidate
    try:
        return search._decode_entry(entry.order)
    finally:
        search.capturing = None


def reference_for_iteration(search: Any) -> PoolEntry:
    """The walk reference; after stagnation, restart from another pool entry (bounded by the pool size)."""
    reference = search.reference
    if reference is None:
        raise RuntimeError("Iterated greedy iteration started without a reference solution.")
    if search.non_improving < search.limits.stagnation_iterations:
        return reference
    search.non_improving = 0
    seed_solution_pool(search)
    restart = search.solution_pool.pick(search.pool_rnd, exclude_entry=reference)
    if restart is None or restart.decision_key() == reference.decision_key():
        return reference
    activate_entry(search, restart)
    decoded = capture_reference(search, restart)
    if decoded is None:
        search.report["pool"]["restart_captures_failed"] += 1
        activate_entry(search, reference)
        return reference
    if decoded is not restart:
        search.solution_pool.refresh(decoded)
    search.report["pool"]["restarts"] += 1
    search.rotation.reset_sizes()
    search.idle_iterations = 0
    search.rejected_iterations = 0
    search.reference = decoded
    return decoded


def adopt_incumbent(search: Any, candidate: Dict[str, Any], profile: Optional[GraphReadyWeightProfile]) -> None:
    """Another stage improved the incumbent: base the walk on it, or keep the old walk when its capture fails."""
    search.best = candidate
    if search.operations is None or search.graph_context is None:
        return
    parent = _parent_from_candidate(candidate, operations=search.operations, graph_context=search.graph_context)
    if parent is None:
        return
    search.report["incumbent_adoptions"] += 1
    previous_parent, previous_profile, previous_reference = search.parent, search.profile, search.reference
    search._set_parent(parent, ig_decode_profile(profile or search.profile))
    entry = PoolEntry(order=parent.order, score=tuple(candidate["score"]), candidate=candidate,
                      batch_order=parent.batch_order, resource_overrides=parent.inherited, profile=search.profile)
    try:
        search._require_budget()
        decoded = capture_reference(search, entry)
    except _BudgetExhausted:
        _roll_back(search, previous_parent, previous_profile, previous_reference)
        raise
    if decoded is None:
        _roll_back(search, previous_parent, previous_profile, previous_reference)
        return
    search.solution_pool.refresh(decoded)
    search.reference = decoded
    search.non_improving = 0


def _roll_back(search: Any, parent: Any, profile: GraphReadyWeightProfile, reference: Optional[PoolEntry]) -> None:
    """The new context has no reference: restore the previous walk context (its trial caches are already gone)."""
    search.report["incumbent_adoption_rollbacks"] += 1
    search._set_parent(parent, profile, count_switch=False)
    search.reference = reference


__all__ = ["activate_entry", "adopt_incumbent", "capture_reference", "reference_for_iteration", "seed_solution_pool"]
