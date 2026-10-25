"""One plan read transaction owns arrangements, identities and their projections."""

from contextlib import contextmanager
from datetime import datetime
from functools import cached_property
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Tuple, Union, cast

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.common.bounded_plan_query import PagePlanQueryService
from core.services.workbench.facts.adoption_baseline_values import AdoptionBaselineUnavailable
from core.services.workbench.facts.zero_duration_evidence import overlaps
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .point_query import PointPlanCatalogRepository

if TYPE_CHECKING:
    from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository


class PlanReadQuery(PagePlanQueryService):
    """Permanent scenario keys reach the existing resolver exactly as stored."""
    def resolve_plan_view(self, version, role, scenario_id=None):
        if scenario_id is None:
            return self.resolve_plan(version, role)
        return self._resolve_scenario_plan(version=int(version), role=role, scenario_id=scenario_id)


class PlanReadContext:
    def __init__(self, conn, logger=None, *, references=None, entities=None, captured_machines=None, repo=None):
        if not conn.in_transaction:
            raise RuntimeError("Plan facts require a caller-owned read transaction")
        self.conn, self.logger = conn, logger
        self.references = references if references is not None else WorkbenchPlanIdentityRepository(conn, logger=logger)
        self.entities = entities if entities is not None else WorkbenchIdentityRepository(conn, logger=logger)
        self.captured_machines = captured_machines
        self.repo = repo if repo is not None else PointPlanCatalogRepository(conn, logger=logger, context=self)
        self._locators, self._selected, self._details, self._scoped = {}, {}, {}, {}
        self._enriched = {}
        self._entities, self._points, self._tasks, self._calendar_selections = {}, {}, {}, {}
        self._adopted, self._task_memberships, self._task_resources, self._task_work = {}, {}, {}, {}
        self._projected_resources = {}
        self._intervals, self._datetime_intervals, self._plan_time_maps = {}, {}, {}
        self._raw_source_selection: Union[Literal[False], Tuple[List[str], str], None] = False
        self._raw_sources = {}
        self._raw_task_selection: Union[Literal[False], Tuple[List[str], str], None] = False
        self._raw_tasks = {}

    @cached_property
    def _source_repo(self) -> "WorkbenchPlanBaselineRepository":
        from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository
        return WorkbenchPlanBaselineRepository(self.conn)

    @contextmanager
    def read_scope(self):
        with read_evidence_scope(self.conn), self.references.read_bindings(
            history_reader=self.repo.history_rows,
            scenario_reader=self.repo.get_scenario_context,
        ):
            yield self

    def resolve(self, plan_ref):
        if plan_ref not in self._locators:
            self._locators[plan_ref] = self.references.resolve_plan(plan_ref)
        return self._locators[plan_ref]

    def selected(self, plan_ref):
        from .queries import selected_plan
        if plan_ref not in self._selected:
            self._selected[plan_ref] = selected_plan(self, self.resolve(plan_ref))
        return self._selected[plan_ref]

    @staticmethod
    def query(entry):
        identity, locator = entry.plan_identity, entry.locator
        return {"version": locator.version, "source_table": identity.source_table,
                "candidate_id": identity.candidate_id, "scenario_id": locator.scenario_id}

    @staticmethod
    def source_key(query):
        return PointPlanCatalogRepository._source_key(**query)

    def source_rows(self, entry=None, **query):
        return self.repo.source_rows(**(self.query(entry) if entry is not None else query))

    def attach_points(self, rows, **query):
        prepared = self.repo.prepared_rows(**query)
        points = {row["id"]: row["_point_work"] for row in prepared if row.get("_point_work")}
        return [dict(row, _point_work=points[row.get("schedule_id", row.get("id"))])
                if row.get("schedule_id", row.get("id")) in points else row for row in rows]

    def seed_source_rows(self, rows, **query):
        """Accept raw rows already captured by this transaction's source owner."""
        key = self.source_key(query)
        if query["source_table"] == "adjustment_scenario_rows":
            valid = all(row["scenario_id"] == query["scenario_id"] for row in rows)
        else:
            valid = all(row["version"] == query["version"] for row in rows)
        if not valid:
            raise WorkbenchCommandRejected("plan_binding_invalid", "安排原件与所选计划不一致，请刷新后重试。")
        if key in self.repo._source_rows:
            raise RuntimeError("Plan arrangements already captured in this context")
        self.repo._source_rows[key] = rows

    def history(self, version):
        return self.repo.get_history_identity_row(version)

    def history_rows(self, version: int) -> List[Dict[str, Any]]:
        return self.repo.history_rows(version)

    def point_work(self, version):
        from .point_evidence import official_point_work
        if version not in self._points:
            self._points[version] = official_point_work(self.conn, version, context=self)
        return self._points[version]

    def adopted_source(self, plan_ref):
        from .projection import adopted_source_record
        return adopted_source_record(self.conn, plan_ref, context=self)

    def adoption_source(self, plan_ref, version, history, *, recorded):
        """One exact snapshot retains available, absent and classified unavailable evidence."""
        from .adoption_baseline import load_adoption_source

        raw = history.get("result_summary") if history is not None else None
        key = (plan_ref, version, raw)
        if key not in self._adopted:
            try:
                self._adopted[key] = load_adoption_source(self.conn, plan_ref=plan_ref, version=version,
                    history=history, recorded=recorded, context=self)
            except AdoptionBaselineUnavailable as exc:
                self._adopted[key] = exc.with_traceback(None)
        result = self._adopted[key]
        if isinstance(result, AdoptionBaselineUnavailable):
            raise result.with_traceback(None)
        return result

    def detail_rows(self, entry):
        query = self.query(entry)
        key = self.source_key(query)
        if key not in self._details:
            self._details[key] = self._enrich_rows(entry, self.repo.prepared_rows(**query))
        return self._details[key]

    def _enrich_rows(self, entry, prepared):
        query = self.query(entry)
        cache = self._enriched.setdefault(self.source_key(query), {})
        missing = [row for row in prepared if row["id"] not in cache]
        if missing:
            rows = self.repo.enrich_arrangements(missing, version=query["version"], captured_machines=self.captured_machines)
            points = {row["id"]: row["_point_work"] for row in missing if row.get("_point_work")}
            cache.update((row["schedule_id"], dict(row, _point_work=points[row["schedule_id"]])
                          if row["schedule_id"] in points else row) for row in rows)
        return sorted((cache[row["id"]] for row in prepared), key=lambda row: (row["start_time"], row["schedule_id"]))

    def intervals(self, entry):
        query = self.query(entry)
        return self._interval_map(query)

    def peek_source_intervals(self, **query):
        """Reuse only a completed whole-source map; never load or prove a plan.

        Scoped selections do not populate this map. It is installed only after
        all prepared rows and their parsed intervals have completed, so an
        absent/in-progress source keeps the caller's ordinary validation path.
        """
        return self._intervals.get(self.source_key(query))

    def _interval_map(self, query):
        key = self.source_key(query)
        if key not in self._intervals:
            self._intervals[key] = {row["id"]: interval for row, interval in zip(
                self.repo.prepared_rows(**query), self.repo.parsed_intervals(**query))}
        return self._intervals[key]

    def scoped_rows(self, entry, scope):
        query = self.query(entry)
        source_key = self.source_key(query)
        key = (source_key, scope.range_start, scope.range_end)
        if key not in self._scoped:
            if scope.range_start is None:
                self._scoped[key] = self.detail_rows(entry)
            else:
                times = self.intervals(entry)
                complete = source_key in self._details
                rows = self._details[source_key] if complete else self.repo.prepared_rows(**query)
                selected = []
                for row in rows:
                    low, high = times[row["schedule_id"] if complete else row["id"]]
                    if overlaps(low.replace(" ", "T"), high.replace(" ", "T"), scope.range_start, scope.range_end):
                        selected.append(row)
                self._scoped[key] = selected if complete else self._enrich_rows(entry, selected)
        return self._scoped[key]

    def admit_scope(self, entry, scope, rows):
        """Standalone projection inputs are admitted against one captured scope."""
        from .baseline import verify_selected_rows
        _, current, _ = self.selected(scope.plan_ref)
        if current.locator != entry.locator or current.plan_identity != entry.plan_identity:
            raise WorkbenchCommandRejected("invalid_input", "所选计划已经变了，不能跨计划对比。请刷新计划列表后重新选择。", 400)
        verify_selected_rows(self.detail_rows(current), rows, scope)
        return self.scoped_rows(current, scope)

    def active_map(self, kind, keys):
        cache = self._entities.setdefault(kind, {})
        keys = list(dict.fromkeys(keys))
        missing = [key for key in keys if key not in cache]
        if missing:
            found = self.entities.active_map(kind, missing)
            cache.update((key, found.get(key)) for key in missing)
        return {key: cache[key] for key in keys if cache[key] is not None}

    def resources(self, rows, *, baseline=False):
        resources, state = {}, {}
        for kind in ("machine", "operator", "supplier", "batch"):
            keys = sorted({str(row[kind + "_id"]) for row in rows if row[kind + "_id"] not in (None, "")})
            mapping = self.active_map(kind, keys)
            if set(mapping) != set(keys):
                message = ("对比工序关联的设备、人员或批次找不到编号。请刷新后重试。" if baseline else
                           "安排关联的批次、设备或人员编号缺失，请到资料总览核对。")
                raise WorkbenchCommandRejected("identity_missing", message)
            resources[kind] = mapping
            state[kind] = [(key, value.ref, value.revision) for key, value in sorted(mapping.items())]
        return resources, state

    def task_refs(self, plan_ref, rows):
        return self.references.get_task_refs(plan_ref, rows)

    def operation_refs(self, ids):
        return self.references.get_operation_refs(ids)

    def projected_tasks(self, plan_ref, entry, rows=None):
        from .projection import project_tasks
        rows = self.detail_rows(entry) if rows is None else rows
        cache = self._tasks.setdefault(plan_ref, {})
        cached_resources = self._projected_resources.get(plan_ref)
        if cached_resources is not None and cached_resources[0] is rows:
            resources, state = cached_resources[1], cached_resources[2]
        else:
            resources, state = self.resources(rows)
            self._projected_resources[plan_ref] = (rows, resources, state)
        missing = [row for row in rows if row["schedule_id"] not in cache]
        if missing:
            task_refs = self.task_refs(plan_ref, missing)
            operations = self.operation_refs(row["op_id"] for row in missing)
            facts = {}
            tasks = project_tasks(plan_ref, missing, task_refs, operations, resources, conn=self.conn, facts=facts, context=self)
            cache.update((row["schedule_id"], task) for row, task in zip(missing, tasks))
            self._task_resources.setdefault(plan_ref, []).extend(facts["resource_directory"])
        return [cache[row["schedule_id"]] for row in rows], {"resource_directory": list(self._task_resources.get(plan_ref, ()))}, resources, state

    def row_times(self, plan_ref, row):
        if plan_ref not in self._plan_time_maps:
            locator, record = self.references._resolved_record(plan_ref)
            candidate_id = int(record["owner_key"]) if record["source_table"] == "candidate_rows" else None
            query = {"version": locator.version, "source_table": record["source_table"],
                     "candidate_id": candidate_id, "scenario_id": locator.scenario_id}
            self._plan_time_maps[plan_ref] = self._interval_map(query)
        return self._plan_time_maps[plan_ref][row["schedule_id"]]

    def calendar_selection(self, entry, scope, resources, plan_span):
        from .calendar_context import selected_context
        key = (scope.plan_ref, scope.range_start, scope.range_end)
        if key not in self._calendar_selections:
            self._calendar_selections[key] = selected_context(self.conn, entry, scope,
                self.scoped_rows(entry, scope), resources, plan_span, read_context=self)
        return self._calendar_selections[key]

    def datetime_intervals(self, entry):
        key = self.source_key(self.query(entry))
        if key not in self._datetime_intervals:
            self._datetime_intervals[key] = {key: (datetime.fromisoformat(low), datetime.fromisoformat(high))
                                           for key, (low, high) in self.intervals(entry).items()}
        return self._datetime_intervals[key]

    def all_task_refs(self, plan_ref):
        if plan_ref not in self._task_memberships:
            rows = cast(List[Dict[str, Any]], self.task_identities(plan_ref))
            self._task_memberships[plan_ref] = {row["ref"] for row in rows}
        return self._task_memberships[plan_ref]

    def task_identities(self, plan_ref):
        if self._raw_task_selection is False:
            self._raw_task_selection = self._source_repo._raw_select("WorkbenchTaskRefs")
        if self._raw_task_selection is None:
            return None
        if plan_ref not in self._raw_tasks:
            columns, select = self._raw_task_selection
            self._raw_tasks[plan_ref] = self._source_repo._raw_rows(columns, select + " WHERE plan_ref=? ORDER BY rowid", [plan_ref])
        return self._raw_tasks[plan_ref]

    def source_identities(self, refs):
        if self._raw_source_selection is False:
            self._raw_source_selection = self._source_repo._raw_select("WorkbenchPlanSourceRefs")
        if self._raw_source_selection is None:
            return None
        keys = list(dict.fromkeys(refs))
        missing = [key for key in keys if key not in self._raw_sources]
        columns, select = self._raw_source_selection
        for start in range(0, len(missing), 400):
            chunk = missing[start:start + 400]
            rows = self._source_repo._raw_rows(columns, select + " WHERE ref IN (" + ",".join("?" for _ in chunk) + ") ORDER BY rowid", chunk)
            found = {row["ref"]: row for row in rows}
            self._raw_sources.update((key, found.get(key)) for key in chunk)
        return [self._raw_sources[key] for key in keys if self._raw_sources[key] is not None]
