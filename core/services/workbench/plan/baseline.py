"""Initial-plan comparison directly over self-contained ScheduleHistory and Schedule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, cast

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import PlanReadScope
from core.services.scheduler.workbench_plan_catalog import PlanCatalogEntry, plan_catalog_entry
from core.services.workbench.facts.adoption_baseline_values import REASONS as ADOPTION_REASONS
from core.shared.local_datetime import us_to_iso

from .projection import (
    build_plan_provenance,
    project_frozen_tasks,
    project_plan,
    resource_ref,
    row_frozen_resource_entries,
    row_resource_entries,
)
from .read_context import PlanReadContext, overlaps_us

_CHANGE_FIELDS = ("start", "end", "machine_ref", "operator_ref")
_REASONS = {
    **ADOPTION_REASONS,
    "baseline_unavailable": "试调依据的那份计划摘要或明细无效，对不全，这里不显示对比。",
    "baseline_task_invalid": "对比工序的时间、批次信息或编号不完整，给不出完整对比。请刷新后重试。",
}


@dataclass(frozen=True)
class PlanBaselineFacts:
    """Off-wire evidence of one baseline read: the plan's provenance and the directory entries of the compared
    rows (none when the comparison is unavailable)."""

    provenance: Dict[str, Any]
    resource_entries: List[Dict[str, Any]]


def _unavailable(code: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    data = {
        "state": "unavailable",
        "reason_code": code,
        "reason": _REASONS[code],
        "baseline_plan": None,
        "items": [],
        "item_count": 0,
        "items_complete": False,
    }
    return data, []


def _light_before_tasks(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "task_ref": row["task_ref"],
            "operation_ref": row["operation_ref"],
            "machine_ref": row["machine_ref"],
            "operator_ref": row["operator_ref"],
            "supplier_ref": row["supplier_ref"],
            "start": us_to_iso(row["start_us"]),
            "end": us_to_iso(row["end_us"]),
            "_row": row,
        }
        for row in rows
    ]


def _light_after_tasks(rows: List[Dict[str, Any]], resources: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "task_ref": row["task_ref"],
            "operation_ref": row["operation_ref"],
            "machine_ref": resource_ref(row, "machine", resources),
            "operator_ref": resource_ref(row, "operator", resources),
            "supplier_ref": row["supplier_ref"],
            "start": us_to_iso(row["start_us"]),
            "end": us_to_iso(row["end_us"]),
            "_row": row,
        }
        for row in rows
    ]


def _by_operation(tasks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {task["operation_ref"]: task for task in tasks}


def _in_scope(task: Optional[Dict[str, Any]], start_us: Optional[int], end_us: Optional[int]) -> bool:
    if task is None:
        return False
    if start_us is None or end_us is None:
        return True
    return overlaps_us(task["_row"], start_us, end_us)


def _comparison_items(
    before_tasks: List[Dict[str, Any]],
    after_tasks: List[Dict[str, Any]],
    start_us: Optional[int],
    end_us: Optional[int],
) -> List[Dict[str, Any]]:
    before, after = _by_operation(before_tasks), _by_operation(after_tasks)
    items: List[Dict[str, Any]] = []
    for operation_ref in sorted(set(before) | set(after)):
        old, new = before.get(operation_ref), after.get(operation_ref)
        changed = [key for key in _CHANGE_FIELDS if old[key] != new[key]] if old and new else []
        change = "added" if old is None else "removed" if new is None else "changed" if changed else "unchanged"
        items.append(
            {
                "operation_ref": operation_ref,
                "change": change,
                "changed_fields": changed,
                "before": old,
                "after": new,
                "before_in_scope": _in_scope(old, start_us, end_us),
                "after_in_scope": _in_scope(new, start_us, end_us),
            }
        )
    return items


class _BaselineReader:
    def __init__(self, entry, scope, context: PlanReadContext, *, include_items=False, page=None, size=None):
        self.entry, self.scope = entry, scope
        self.context = context
        self.include_items = include_items
        self.page, self.size = page, size

    def read(self, history: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        base_version = history["baseline_version"]
        if base_version is None:
            return _unavailable("no_adoption_baseline")
        base_ref = history["baseline_ref"]
        base_history = self.context.history(base_version)
        if base_history is None:
            return _unavailable("adoption_baseline_archived")
        base_entry = plan_catalog_entry(self.context.plan_query, base_history)
        if not base_entry.can_view:
            return _unavailable("baseline_unavailable")
        before_rows = self.context.schedule_rows(base_version)
        if not before_rows:
            return _unavailable("adoption_baseline_archived")
        after_rows = self.context.detail_rows(self.entry)
        after_resources = self.context.resource_identities(after_rows)
        before_light = _light_before_tasks(before_rows)
        after_light = _light_after_tasks(after_rows, after_resources)
        return self._comparison(base_entry, base_ref, before_light, after_light, history["source_kind"], after_resources)

    def _comparison(self, base_entry, base_ref: str, before, after, basis: str, after_resources):
        start_us, end_us = self.context.scope_range_us(self.scope)
        items = _comparison_items(before, after, start_us, end_us)
        visible = [item for item in items if item["before_in_scope"] or item["after_in_scope"]]
        visible_after_rows = [item["after"]["_row"] for item in visible if item["after"] is not None]
        visible_before_rows = [item["before"]["_row"] for item in visible if item["before"] is not None]
        # Current-plan rows register live machine/operator labels first; baseline-only rows fall back to frozen labels.
        entries = row_resource_entries(visible_after_rows, after_resources) + row_frozen_resource_entries(
            visible_before_rows
        )
        data: Dict[str, Any] = {
            "state": "available",
            "reason_code": None,
            "reason": None,
            "basis": basis,
            "baseline_plan": project_plan(base_entry, base_ref),
            "comparison_scope": {
                "scope": self.scope.scope(),
                "selection": "either_side_overlap",
                "boundary": "half_open",
                "alignment": "operation_ref",
                "time_basis": "factory_local",
                "task_times": "unclipped",
            },
            "compared_fields": list(_CHANGE_FIELDS),
            "items": [],
            "item_count": len(visible),
            "items_complete": len(visible) == 0,
        }
        if not self.include_items:
            return data, entries
        target_visible = (
            visible[(self.page - 1) * self.size : self.page * self.size]
            if self.page is not None and self.size is not None
            else visible
        )
        before_page_rows = [item["before"]["_row"] for item in target_visible if item["before"] is not None]
        before_tasks = (
            {task["task_ref"]: task for task in project_frozen_tasks(base_ref, before_page_rows)}
            if before_page_rows
            else {}
        )
        out_of_scope_rows = [
            item["after"]["_row"]
            for item in target_visible
            if item["after"] is not None and not item["after_in_scope"]
        ]
        out_of_scope_tasks = {}
        if out_of_scope_rows:
            projected_out = self.context.projected_tasks(self.scope.plan_ref, out_of_scope_rows, resources=after_resources)
            out_of_scope_tasks = {task["task_ref"]: task for task in projected_out}
        compact_visible = [
            dict(
                item,
                before=(
                    None
                    if item["before"] is None
                    else before_tasks[item["before"]["task_ref"]]
                ),
                after=(
                    None
                    if item["after"] is None
                    else {"task_ref": item["after"]["task_ref"]}
                    if item["after_in_scope"]
                    else out_of_scope_tasks[item["after"]["task_ref"]]
                ),
            )
            for item in target_visible
        ]
        return (
            dict(
                data,
                items=compact_visible,
                item_count=len(visible),
                items_complete=(len(compact_visible) == len(visible)),
            ),
            entries,
        )


def build_plan_baseline(
    conn,
    *,
    entry: PlanCatalogEntry,
    scope: PlanReadScope,
    context: PlanReadContext,
    include_items: bool = False,
    page: Optional[int] = None,
    size: Optional[int] = None,
) -> Tuple[Dict[str, Any], PlanBaselineFacts]:
    if not conn.in_transaction:
        raise RuntimeError("Baseline reads require a caller-owned read transaction.")
    reader = _BaselineReader(
        entry, scope, context, include_items=include_items, page=page, size=size
    )
    with context.read_scope():
        history = cast(Dict[str, Any], context.history(entry.locator.version))
        provenance = build_plan_provenance(history)
        try:
            data, entries = reader.read(history)
        except WorkbenchCommandRejected as exc:
            if exc.code not in ("plan_unavailable", "identity_missing"):
                raise
            data, entries = _unavailable("baseline_task_invalid")
    return data, PlanBaselineFacts(provenance, entries)
