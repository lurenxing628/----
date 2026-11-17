"""Decision views supply frozen rows to the shared whole-batch delivery rule."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.services.workbench.facts.delivery_projection import project_delivery_batch, project_unbased_delivery_batch

from .candidate_delivery import captured_delivery_batch, captured_delivery_groups, captured_operation_ids

if TYPE_CHECKING:
    from .candidate_facts import GenerationFacts


def project_decision_delivery(facts: GenerationFacts, tasks, batch_refs, *, deferred_ids, candidate=None, available=True,
                              intervals):
    """``available`` is False only without an admission baseline: then no task is arranged against it."""
    groups = captured_delivery_groups(tasks, facts, intervals)
    incomplete = set(candidate["artifact"]["metrics"]["completion"]["incomplete_batch_ids"]) if candidate is not None else set()
    result = []
    for ref in batch_refs:
        key = facts.batch_id(ref)
        batch = facts.related("Batches", key)
        if available:
            result.append(project_delivery_batch(
                captured_delivery_batch(facts, batch, ref, groups[key], incomplete=key in incomplete),
                deferred_operation_ids=deferred_ids, scope_issues=()))
        else:
            result.append(project_unbased_delivery_batch(batch, ref, captured_operation_ids(facts, key),
                                                         deferred_operation_ids=deferred_ids))
    return result
