"""Initial-plan comparison, SELECT-only under the caller's transaction.

Draft evaluation reads ALL rows of its exact base (evaluate_draft), and scenario
save persists that base's source/role/candidate. New official adoptions bind their
captured official baseline through audit/receipt evidence. Other ordinary plans
have no separate initial snapshot; baseline_best is a role, not a baseline.

Compare the complete plans before filtering: include an operation if either side
overlaps the half-open Scope. Keep both whole tasks, including the side moved out
of range. Only machine/operator and times are historical arrangement fields;
legacy labels/supplier remain live joins, not historical facts. New adoption
baselines use captured labels and do not invent historical supplier assignments.
No draft evaluation, scheduling, latest-plan fallback, or identity allocation.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence, Tuple

from core.models.schedule_plan_role import SOURCE_ADJUSTMENT_SCENARIO_ROWS
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.models.workbench_plan_scope import MAX_PLAN_TASKS, PlanReadScope
from core.services.scheduler.workbench_plan_catalog import PlanCatalogEntry, _role_entry
from core.services.scheduler.workbench_plan_page import _PagePlanQueryService
from data.repositories.schedule_detail_query import build_schedule_detail_sql
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .plan_adoption_baseline import read_adoption_baseline
from .plan_adoption_baseline_values import REASONS as ADOPTION_REASONS
from .plan_adoption_baseline_values import AdoptionBaselineUnavailable
from .plan_projection import check_payload_size, project_plan, project_tasks, public_time

_CHANGE_FIELDS = ("start", "end", "machine_ref", "operator_ref")
_REASONS = {
    **ADOPTION_REASONS,
    "not_recorded": "该正式或代表候选计划未记录独立的初始基线，不能用当前安排冒充初始计划。",
    "baseline_binding_invalid": "场景或其持久基础计划身份已失效，不能对照；未切换到其他计划。",
    "baseline_unavailable": "持久基础计划的摘要、角色或明细无效，不能完整对照。",
    "scenario_unavailable": "所选场景不是有效的已保存预览，不能进行初始计划对照。",
    "baseline_task_invalid": "对照任务的时间、业务信息或永久身份不完整，不能返回完整对照。",
}


def _unavailable(code, facts):
    data = {"state": "unavailable", "reason_code": code, "reason": _REASONS[code],
            "baseline_plan": None, "items": [], "item_count": 0, "items_complete": False}
    facts["outcome"] = data
    return data, facts


def _complete_rows(repo, *, version, source, candidate_id=None, scenario_id=None):
    sql, extra = repo._plan_rows_sql(source_table=source, candidate_id=candidate_id, scenario_id=scenario_id)
    params = [version] + extra
    ids = repo.fetchall("SELECT id FROM (" + sql + ") LIMIT ?", params + [MAX_PLAN_TASKS + 1])
    if len(ids) > MAX_PLAN_TASKS:
        raise WorkbenchCommandRejected(
            "query_too_large", "完整基线或对照计划超过 10000 条上限，未用范围截断冒充完整对照。", 413,
        )
    detail = build_schedule_detail_sql(where_clauses=["1 = 1"], plan_rows_cte_sql=sql)
    rows = repo.fetchall(detail + " LIMIT ?", params + [MAX_PLAN_TASKS + 1])
    if len(rows) != len(ids):
        raise WorkbenchCommandRejected("plan_unavailable", "对照计划明细数量不一致，不能确认完整范围。")
    return rows


def _resource_maps(conn, rows):
    entities = WorkbenchIdentityRepository(conn)
    resources, state = {}, {}
    for kind in ("machine", "operator", "supplier", "batch"):
        keys = sorted({str(row[kind + "_id"]) for row in rows if row[kind + "_id"] not in (None, "")})
        mapping = entities.active_map(kind, keys)
        if set(keys) != set(mapping):
            raise WorkbenchCommandRejected("identity_missing", "对照任务关联的资源或批次永久身份缺失。")
        resources[kind] = mapping
        state[kind] = [(key, value.ref, value.revision) for key, value in sorted(mapping.items())]
    return resources, state


def _overlaps(start, end, scope):
    from .zero_duration_evidence import overlaps
    return scope.range_start is None or overlaps(start, end, scope.range_start, scope.range_end)


def _verify_selected_rows(rows, selected_rows, scope):
    expected = {row["schedule_id"]: {key: value for key, value in row.items() if key != "_point_work"} for row in rows
                if _overlaps(public_time(row["start_time"]), public_time(row["end_time"]), scope)}
    supplied = {row["schedule_id"]: {key: value for key, value in row.items() if key != "_point_work"} for row in selected_rows}
    if len(supplied) != len(selected_rows) or supplied != expected:
        raise WorkbenchCommandRejected(
            "invalid_input", "选定任务必须来自同一事务、同一计划和完整时间范围，不能用额外筛选后的子集对照。", 400,
        )


def _by_operation(tasks):
    mapped = {task["operation_ref"]: task for task in tasks}
    if len(mapped) != len(tasks):
        raise WorkbenchCommandRejected("task_binding_invalid", "同一计划的工序安排重复，不能唯一对齐。")
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
    def __init__(self, conn, entry, scope, selected_rows):
        from .point_plan_query import PointPlanCatalogRepository
        self.conn, self.entry, self.scope, self.selected_rows = conn, entry, scope, selected_rows
        self.repo = PointPlanCatalogRepository(conn)
        self.references = WorkbenchPlanIdentityRepository(conn)
        self.facts = {"scope": scope.scope(), "selected_plan_ref": scope.plan_ref}

    def read(self):
        locator = self.references.resolve_plan(self.scope.plan_ref)
        selected = self.entry.locator
        if locator != WorkbenchPlanLocator(selected.version, selected.plan_role, selected.scenario_id):
            raise WorkbenchCommandRejected("invalid_input", "计划引用与已解析条目不一致，不能跨计划对照。", 400)
        if locator.scenario_id is None:
            return self._adopted(locator)
        header = self.repo.get_scenario_context(locator.scenario_id)
        self.facts["scenario_header"] = header
        if (header is None or header["status"] != "active" or not self.entry.can_view
                or self.entry.plan_identity is None
                or self.entry.plan_identity.source_table != SOURCE_ADJUSTMENT_SCENARIO_ROWS):
            return _unavailable("scenario_unavailable", self.facts)
        base_locator = WorkbenchPlanLocator(header["base_version"], header["base_plan_role"])
        # resolve_plan above validates the persisted parent_ref AND exact source,
        # candidate id/key against the current base. Same-number replacements fail.
        base_ref = self.references.get_plan_ref(base_locator)
        self.facts["base_plan_ref"] = base_ref
        base_rows = _complete_rows(self.repo, version=base_locator.version, source=header["base_source_table"],
                                   candidate_id=header["base_candidate_id"])
        base_entry = self._base_entry(base_locator)
        if base_entry is None or not base_entry.can_view:
            return _unavailable("baseline_unavailable", self.facts)
        current_rows = _complete_rows(self.repo, version=locator.version, source=SOURCE_ADJUSTMENT_SCENARIO_ROWS,
                                      scenario_id=locator.scenario_id)
        if not current_rows:
            return _unavailable("scenario_unavailable", self.facts)
        _verify_selected_rows(current_rows, self.selected_rows, self.scope)
        return self._project(base_entry, base_ref, base_rows, current_rows)

    def _adopted(self, locator):
        from .plan_point_evidence import annotate_plan_points

        if locator.plan_role != "adopted":
            return _unavailable("not_recorded", self.facts)
        evidence = read_adoption_baseline(self.conn, plan_ref=self.scope.plan_ref, version=locator.version,
            history=self.repo.get_history_identity_row(locator.version), facts=self.facts,
            point_annotator=lambda rows: annotate_plan_points(self.conn, rows))
        if evidence is None:
            return _unavailable("not_recorded", self.facts)
        base = evidence["baseline"]
        base_entry = self._base_entry(WorkbenchPlanLocator(base["version"], "adopted"))
        if base_entry is None or not base_entry.can_view:
            return _unavailable("baseline_unavailable", self.facts)
        current = _complete_rows(self.repo, version=locator.version, source="schedule")
        current = annotate_plan_points(self.conn, current)
        _verify_selected_rows(current, self.selected_rows, self.scope)
        resources, state = _resource_maps(self.conn, current)
        operations = self.references.get_operation_refs(row["op_id"] for row in current)
        after = project_tasks(self.scope.plan_ref, current,
                              self.references.get_task_refs(self.scope.plan_ref, current), operations, resources, conn=self.conn)
        return self._comparison(base_entry, base["plan_ref"], evidence["tasks"], after, state, evidence["basis"])

    def _base_entry(self, locator):
        history = self.repo.get_history_identity_row(locator.version)
        self.facts["base_history"] = history
        if history is None:
            return None
        options = self.repo.list_plan_role_options(locator.version)
        self.facts["base_roles"] = options
        option = next((row for row in options if row["role"] == locator.plan_role), None)
        query = _PagePlanQueryService(self.repo, self.repo.latest_version())
        return _role_entry(query, history, query.latest, locator.plan_role, option)

    def _project(self, base_entry, base_ref, base_rows, current_rows):
        resources, resource_state = _resource_maps(self.conn, base_rows + current_rows)
        operations = self.references.get_operation_refs(row["op_id"] for row in base_rows + current_rows)
        before = project_tasks(base_ref, base_rows, self.references.get_task_refs(base_ref, base_rows), operations, resources, conn=self.conn)
        after = project_tasks(self.scope.plan_ref, current_rows,
                              self.references.get_task_refs(self.scope.plan_ref, current_rows), operations, resources, conn=self.conn)
        return self._comparison(base_entry, base_ref, before, after, resource_state, "scenario_base")

    def _comparison(self, base_entry, base_ref, before, after, resource_state, basis):
        items = _comparison_items(before, after, self.scope)
        data = {"state": "available", "reason_code": None, "reason": None,
                "basis": basis, "baseline_plan": project_plan(base_entry, base_ref),
                "comparison_scope": {"scope": self.scope.scope(), "selection": "either_side_overlap",
                                     "boundary": "half_open", "alignment": "operation_ref",
                                     "time_basis": "factory_local", "task_times": "unclipped"},
                "compared_fields": list(_CHANGE_FIELDS), "items": items,
                "item_count": len(items), "items_complete": True}
        # Admit the COMPLETE comparison, not just a small visible slice.
        check_payload_size(data)
        self.facts.update({"complete_comparison": data, "resources": resource_state})
        visible = [item for item in items if item["before_in_scope"] or item["after_in_scope"]]
        return dict(data, items=visible, item_count=len(visible)), self.facts


def build_plan_baseline(
    conn, *, entry: PlanCatalogEntry, scope: PlanReadScope,
    selected_rows: Sequence[Mapping[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return (public DTO, PRIVATE snapshot facts), never a snapshot token itself.

    entry and selected_rows must be resolved in this same caller-owned transaction;
    selected_rows is exactly the time-scoped result, without resource/subset filters.
    Compare complete plans, then keep either-side overlap; there is no resource
    Scope today. Reference/data failures explicitly disable comparison. Storage/
    schema errors propagate. Whole-plan >10000 rows or >8 MiB raises 413 even if
    the requested time slice is small. The caller must also size-check its combined
    workspace and hash these private facts with all other projection facts.
    """
    if not conn.in_transaction:
        raise RuntimeError("Baseline reads require a caller-owned read transaction.")
    reader = _BaselineReader(conn, entry, scope, selected_rows)
    try:
        return reader.read()
    except AdoptionBaselineUnavailable as exc:
        reader.facts["evidence_gap"] = exc.gap
        return _unavailable(exc.code, reader.facts)
    except WorkbenchPlanReferenceError as exc:
        reader.facts["reference_error"] = exc.code
        return _unavailable("baseline_binding_invalid", reader.facts)
    except WorkbenchCommandRejected as exc:
        if exc.code not in ("plan_unavailable", "identity_missing", "task_binding_invalid"):
            raise
        reader.facts["projection_error"] = exc.code
        return _unavailable("baseline_task_invalid", reader.facts)
