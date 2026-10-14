"""Pair delivery differences over the exact shared completed batch set."""

from typing import Any, Dict, Mapping, Sequence

from core.services.workbench.facts.delivery_projection import delivery_summary


def common_completed_delivery(
    before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Use selected minus reference, without substituting partial batch finishes."""
    old, new = ({row["batch_ref"]: row for row in rows} for rows in (before, after))
    refs = sorted(ref for ref in set(old) & set(new) if old[ref]["schedule_complete"] and new[ref]["schedule_complete"])
    old_summary, new_summary = (delivery_summary([rows[ref] for ref in refs]) for rows in (old, new))
    previous, selected = old_summary["total_tardiness_hours"], new_summary["total_tardiness_hours"]
    old_overdue, new_overdue = old_summary["overdue_count"], new_summary["overdue_count"]
    return {"common_completed_batch_refs": refs,
            "common_delivery": {"before": old_summary, "after": new_summary,
                                "delay_delta_hours": None if previous is None or selected is None else selected - previous,
                                "overdue_delta_count": None if old_overdue is None or new_overdue is None else new_overdue - old_overdue}}
