"""Initial-plan comparison, SELECT-only under the caller's transaction.

Draft evaluation reads ALL rows of its exact base (evaluate_draft), and scenario
save persists that base's source/role/candidate. New official adoptions bind their
captured official baseline through audit/receipt evidence. Other ordinary plans
have no separate initial snapshot; baseline_best is a role, not a baseline.

Compare the complete plans before filtering: include an operation if either side
overlaps the half-open Scope. Keep both whole tasks, including the side moved out
of range. Only machine/operator and times are historical arrangement fields;
legacy labels remain live joins, not historical facts. Supplier assignments need
the recorded adoption; new baselines recover identity and labels from that source.
No draft evaluation, scheduling, latest-plan fallback, or identity allocation.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.models.workbench_plan_scope import PlanReadScope
from core.services.scheduler.workbench_plan_catalog import PlanCatalogEntry, _role_entry
from core.services.workbench.facts.adoption_baseline_values import REASONS as ADOPTION_REASONS
from core.services.workbench.facts.adoption_baseline_values import AdoptionBaselineUnavailable

from .adoption_baseline import read_adoption_baseline
from .projection import project_light_tasks, project_plan
from .read_context import PlanReadContext

_CHANGE_FIELDS = ("start", "end", "machine_ref", "operator_ref")
_REASONS = {
    **ADOPTION_REASONS,
    "baseline_binding_invalid": "试调方案或初始计划编号已失效，无法对比。",
    "baseline_unavailable": "试调依据的那份计划摘要或明细无效，对不全，这里不显示对比。",
    "baseline_task_invalid": "对比工序的时间、批次信息或编号不完整，给不出完整对比。请刷新后重试。",
}


def _unavailable(code, facts):
    data = {"state": "unavailable", "reason_code": code, "reason": _REASONS[code],
            "baseline_plan": None, "items": [], "item_count": 0, "items_complete": False}
    return data, facts


def _overlaps(start, end, scope):
    from core.services.workbench.facts.zero_duration_evidence import overlaps
    return scope.range_start is None or overlaps(start, end, scope.range_start, scope.range_end)


def _by_operation(tasks):
    mapped = {task["operation_ref"]: task for task in tasks}
    if len(mapped) != len(tasks):
        raise WorkbenchCommandRejected("task_binding_invalid", "同一个计划里有工序安排重复，对不齐。请刷新后重试。")
    return mapped


def _comparison_items(before_tasks, after_tasks, scope):
    before, after = _by_operation(before_tasks), _by_operation(after_tasks)
    items = []
    for operation_ref in sorted(set(before) | set(after)):
        old, new = before.get(operation_ref), after.get(operation_ref)
        changed = [key for key in _CHANGE_FIELDS if old[key] != new[key]] if old and new else []
        change = "added" if old is None else "removed" if new is None else "changed" if changed else "unchanged"
        items.append({"operation_ref": operation_ref, "change": change, "changed_fields": changed,
                      "before": old, "after": new,
                      "before_in_scope": bool(old and _overlaps(old["start"], old["end"], scope)),
                      "after_in_scope": bool(new and _overlaps(new["start"], new["end"], scope))})
    return items


class _BaselineReader:
    def __init__(self, conn, entry, scope, context, *, include_items=False, page=None, size=None):
        self.conn, self.entry, self.scope = conn, entry, scope
        self.context, self.repo, self.references = context, context.repo, context.references
        self.include_items = include_items
        self.page, self.size = page, size
        self.facts = {}

    def read(self):
        locator = self.context.resolve(self.scope.plan_ref)
        selected = self.entry.locator
        if (locator.version, locator.plan_role) != (selected.version, selected.plan_role):
            raise WorkbenchCommandRejected("invalid_input", "所选计划已经变了，不能跨计划对比。请刷新计划列表后重新选择。", 400)
        evidence = read_adoption_baseline(self.conn, plan_ref=self.scope.plan_ref, version=locator.version,
            history=self.repo.get_history_identity_row(locator.version), facts=self.facts,
            point_annotator=lambda rows: self.context.attach_points(rows, version=rows[0]["version"]) if rows else rows,
            context=self.context)
        base = evidence["baseline"]
        base_entry = self._base_entry(base["version"])
        if base_entry is None or not base_entry.can_view:
            return _unavailable("baseline_unavailable", self.facts)
        current = self.context.detail_rows(self.entry)
        after = self._light_current_tasks(current)
        return self._comparison(
            base_entry, base["plan_ref"], evidence["tasks"], after, evidence["basis"],
            project_before=evidence["project_before"],
        )

    def _light_current_tasks(self, current):
        resources = self.context.resource_identities(current)
        source_evidence = self.context.adopted_source(self.scope.plan_ref)
        task_refs = source_evidence["selected_task_refs"]
        op_sources = source_evidence["indexed_tables"]["operation_sources"]
        operations = {row["op_id"]: op_sources[str(row["op_id"])]["ref"] for row in current}
        _, _, origins = self.context.adopted_task_facts(self.scope.plan_ref) if current else ({}, None, {})
        self.facts["resource_directory"] = [
            resource
            for row in current
            for resource in origins.get(row["op_id"], {}).get("resource_directory", [])
        ]
        return project_light_tasks(
            self.scope.plan_ref, current, task_refs, operations, resources, origins, context=self.context,
        )

    def _base_entry(self, version):
        history = self.repo.get_history_identity_row(version)
        if history is None:
            return None
        query = self.context.plan_query
        return _role_entry(query, history)

    def _comparison(self, base_entry, base_ref, before, after, basis, *, project_before):
        items = _comparison_items(before, after, self.scope)
        visible = [item for item in items if item["before_in_scope"] or item["after_in_scope"]]
        self.facts["compared_tasks"] = [
            {k: v for k, v in task.items() if k != "_row"}
            for item in visible
            for task in (item["before"], item["after"])
            if task is not None
        ]
        data = {
            "state": "available", "reason_code": None, "reason": None,
            "basis": basis, "baseline_plan": project_plan(base_entry, base_ref),
            "comparison_scope": {
                "scope": self.scope.scope(), "selection": "either_side_overlap",
                "boundary": "half_open", "alignment": "operation_ref",
                "time_basis": "factory_local", "task_times": "unclipped",
            },
            "compared_fields": list(_CHANGE_FIELDS),
            "items": [],
            "item_count": len(visible),
            "items_complete": len(visible) == 0,
        }
        if not self.include_items:
            return data, self.facts
        target_visible = (
            visible[(self.page - 1) * self.size : self.page * self.size]
            if self.page is not None and self.size is not None
            else visible
        )
        before_rows = [
            item["before"]["_row"]
            for item in target_visible
            if item["before"] is not None
        ]
        before_tasks = {task["task_ref"]: task for task in project_before(before_rows)} if before_rows else {}
        out_of_scope_rows = [
            item["after"]["_row"]
            for item in target_visible
            if item["after"] is not None and not item["after_in_scope"]
        ]
        out_of_scope_tasks = {}
        if out_of_scope_rows:
            projected_out, _ = self.context.projected_tasks(
                self.scope.plan_ref, out_of_scope_rows,
                resources=self.context.resource_identities(out_of_scope_rows))
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
        return dict(
            data,
            items=compact_visible,
            item_count=len(visible),
            items_complete=(len(compact_visible) == len(visible)),
        ), self.facts


def build_plan_baseline(
    conn,
    *,
    entry: PlanCatalogEntry,
    scope: PlanReadScope,
    context: PlanReadContext,
    include_items: bool = False,
    page: Optional[int] = None,
    size: Optional[int] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return (public DTO, PRIVATE snapshot facts), never a snapshot token itself.

    entry must be resolved by context in this same caller-owned transaction.
    Compare complete plans, then keep either-side overlap; there is no resource
    Scope today. Reference/data failures explicitly disable comparison. Storage/
    schema errors propagate. Complete sources are compared before the public
    workspace's scoped task limit and each endpoint's actual output byte limit.
    The caller includes private projection facts and read bindings in its read snapshot.
    """
    if not conn.in_transaction:
        raise RuntimeError("Baseline reads require a caller-owned read transaction.")
    reader = _BaselineReader(
        conn, entry, scope, context, include_items=include_items, page=page, size=size,
    )
    try:
        with context.read_scope():
            return reader.read()
    except AdoptionBaselineUnavailable as exc:
        return _unavailable(exc.code, reader.facts)
    except WorkbenchPlanReferenceError:
        return _unavailable("baseline_binding_invalid", reader.facts)
    except WorkbenchCommandRejected as exc:
        if exc.code not in ("plan_unavailable", "identity_missing", "task_binding_invalid"):
            raise
        return _unavailable("baseline_task_invalid", reader.facts)
