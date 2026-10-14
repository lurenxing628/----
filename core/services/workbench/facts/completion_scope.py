"""Exact completed cohorts and missing work from shared archived projections."""

from collections import defaultdict
from typing import Any, Dict, Mapping, Optional, Sequence

from core.models.enums import DeliveryCompletionState

from .preparation_projection import preparation_summary


def _remaining_operation(row: Mapping[str, Any]) -> Dict[str, Any]:
    result = {key: value for key, value in row.items() if key != "disposition"}
    disposition = row.get("disposition") or {}
    result.update(disposition_status=disposition.get("status"), reasons=list(disposition.get("issues", [])))
    return result


def _scope_state(items, *, available):
    if not available:
        return "unavailable"
    if not items:
        return "not_applicable"
    if all(row["schedule_complete"] for row in items):
        return "complete"
    return "unavailable" if all(row["completion_state"] == DeliveryCompletionState.UNKNOWN.value for row in items) else "partial"


def project_completion_scope(
    delivery_items: Sequence[Mapping[str, Any]], work_items: Sequence[Mapping[str, Any]], *, available: bool = True,
    schedulable_coverage: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Keep batch completion, arrangement gaps and execution quantities distinct.

    ``work_items`` are public operation labels joined to the existing preparation
    rows and optional public disposition status/issues. They are full-admission
    facts, independent of resource windows and display pages.
    ``remaining_work`` summarizes unarranged operations. Batch evidence that is
    unresolved without a known missing operation stays in ``unknown_batch_refs``.
    """
    by_batch = {row["batch_ref"]: row for row in delivery_items}
    complete = sorted(ref for ref, row in by_batch.items() if available and row["schedule_complete"])
    deferred = sorted(ref for ref, row in by_batch.items() if available and row["completion_state"] == DeliveryCompletionState.DEFERRED.value)
    ordinary = sorted(ref for ref, row in by_batch.items() if available and row["completion_state"] == DeliveryCompletionState.INCOMPLETE.value)
    unknown = sorted(ref for ref, row in by_batch.items() if not available or row["completion_state"] == DeliveryCompletionState.UNKNOWN.value)
    incomplete = sorted(set(by_batch) - set(complete))
    pending = [row for row in work_items if available and not row["arranged"] and row["batch_ref"] in by_batch]
    pending.sort(key=lambda row: (row["batch_ref"], row.get("sequence") is None, row.get("sequence") or 0, row["operation_ref"]))
    unplanned_refs = [row["operation_ref"] for row in pending if row["allocation_state"] != "deferred"]
    deferred_refs = [row["operation_ref"] for row in pending if row["allocation_state"] == "deferred"]
    missing = defaultdict(list)
    for row in pending:
        missing[row["batch_ref"]].append(row)
    batches = []
    for ref in incomplete:
        row = by_batch[ref]
        rows = missing[ref]
        batches.append({"batch_ref": ref, "completion_state": row["completion_state"] if available else DeliveryCompletionState.UNKNOWN.value,
                        "issues": list(row.get("issues", [])),
                        "unplanned_operation_refs": sorted(item["operation_ref"] for item in rows if item["allocation_state"] != "deferred"),
                        "deferred_operation_refs": sorted(item["operation_ref"] for item in rows if item["allocation_state"] == "deferred"),
                        "operations": [_remaining_operation(item) for item in rows]})
    result = {"state": _scope_state(delivery_items, available=available), "source_available": available,
              "complete_batch_refs": complete, "incomplete_batch_refs": incomplete, "ordinary_incomplete_batch_refs": ordinary,
              "deferred_batch_refs": deferred, "unknown_batch_refs": unknown,
              "unplanned_operation_refs": sorted(unplanned_refs), "deferred_operation_refs": sorted(deferred_refs),
              "remaining_batches": batches, "remaining_work": preparation_summary(pending, available=available)}
    if schedulable_coverage is not None:
        result["schedulable"] = dict(schedulable_coverage)
    return result


def completion_groups(candidates: Sequence[Mapping[str, Any]]) -> Sequence[Dict[str, Any]]:
    """Group equal completed batch sets; arrangement equality remains separate."""
    groups = {}
    for candidate in candidates:
        scope = candidate["completion_scope"]
        available = scope["source_available"] and candidate["persisted_status"] == "completed"
        refs = tuple(sorted(scope["complete_batch_refs"])) if available else ()
        key = available, refs
        if key not in groups:
            groups[key] = {"source_available": available, "complete_batch_refs": list(refs), "candidate_refs": []}
        groups[key]["candidate_refs"].append(candidate["candidate_ref"])
    result = list(groups.values())
    for group in result:
        group["candidate_refs"].sort()
    result.sort(key=lambda row: (not row["source_available"], row["complete_batch_refs"], row["candidate_refs"]))
    return result
