"""One plan read transaction owns arrangements, identities and their projections."""

from contextlib import contextmanager
from datetime import datetime
from functools import cached_property
from typing import TYPE_CHECKING, Any, Dict, List, cast

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.scheduler_history_parser import ResultSummaryParseResult
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.common.bounded_plan_query import PagePlanQueryService
from core.services.workbench.facts.adoption_baseline_values import AdoptionBaselineUnavailable
from core.services.workbench.facts.zero_duration_evidence import overlaps
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .point_query import PointPlanCatalogRepository

if TYPE_CHECKING:
    from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository


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
        self._raw_sources = {}
        self._raw_tasks = {}
        self._snapshot_state = None
        self._scope_depth = 0

    def snapshot_state(self) -> Dict[str, Any]:
        if self._snapshot_state is None:
            from core.services.workbench.facts.source_revisions import PLAN_SOURCE_KEYS, read_source_revisions
            self._snapshot_state = {
                "plan_revision": self.references.read_revision(),
                "sources": read_source_revisions(self.conn, PLAN_SOURCE_KEYS),
            }
        return self._snapshot_state

    @cached_property
    def _source_repo(self) -> "WorkbenchPlanBaselineRepository":
        from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository
        return WorkbenchPlanBaselineRepository(self.conn)

    @contextmanager
    def read_scope(self):
        if self._scope_depth > 0:
            self._scope_depth += 1
            try:
                yield self
            finally:
                self._scope_depth -= 1
            return
        self._scope_depth = 1
        try:
            with read_evidence_scope(self.conn), self.references.read_bindings(
                history_reader=self.repo.history_rows,
            ):
                yield self
        finally:
            self._scope_depth = 0

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
        return {"version": entry.locator.version}

    @staticmethod
    def source_key(query):
        return query["version"]

    def source_rows(self, *, version):
        return self.repo.source_rows(version)

    def attach_points(self, rows, **query):
        prepared = self.repo.prepared_rows(**query)
        points = {row["id"]: row["_point_work"] for row in prepared if row.get("_point_work")}
        return [dict(row, _point_work=points[row.get("schedule_id", row.get("id"))])
                if row.get("schedule_id", row.get("id")) in points else row for row in rows]

    def history(self, version):
        return self.repo.get_history_identity_row(version)

    @cached_property
    def plan_query(self) -> PagePlanQueryService:
        """This transaction's only plan query; its summary-parse cache serves every reader in it."""
        return PagePlanQueryService(self.repo, self.repo.latest_version())

    def parsed_summary(self, version) -> ResultSummaryParseResult:
        # Callers read a version ``selected`` already admitted, so its history row exists.
        return self.plan_query.parse_history_summary(cast(Dict[str, Any], self.history(version)))

    def history_rows(self, version: int) -> List[Dict[str, Any]]:
        return self.repo.history_rows(version)

    def point_work(self, version):
        from .point_evidence import official_point_work
        if version not in self._points:
            self._points[version] = official_point_work(self.conn, version, context=self)
        return self._points[version]

    def adopted_source(self, plan_ref):
        from .projection import adopted_source_record
        return adopted_source_record(plan_ref, context=self)

    def adopted_task_facts(self, plan_ref):
        """The adopted plan's audited target quantities and origins, read once per transaction."""
        from .projection import read_adopted_task_facts
        if plan_ref not in self._task_work:
            self._task_work[plan_ref] = read_adopted_task_facts(self.conn, plan_ref, context=self)
        return self._task_work[plan_ref]

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
            rows = self.repo.enrich_arrangements(missing, captured_machines=self.captured_machines)
            points = {row["id"]: row["_point_work"] for row in missing if row.get("_point_work")}
            cache.update((row["schedule_id"], dict(row, _point_work=points[row["schedule_id"]])
                          if row["schedule_id"] in points else row) for row in rows)
        dt_intervals = self.repo.datetime_intervals(**query)
        return sorted(
            (cache[row["id"]] for row in prepared),
            key=lambda row: (dt_intervals[row["schedule_id"]][0], row["schedule_id"]),
        )

    def intervals(self, entry):
        return self.repo.intervals(**self.query(entry))

    def peek_source_intervals(self, **query):
        return self.repo.peek_intervals(**query)

    def scoped_rows(self, entry, scope):
        query = self.query(entry)
        source_key = self.source_key(query)
        key = (source_key, scope.range_start, scope.range_end)
        if key not in self._scoped:
            if scope.range_start is None:
                self._scoped[key] = self.detail_rows(entry)
            else:
                times = self.datetime_intervals(entry)
                range_start = datetime.fromisoformat(scope.range_start)
                range_end = datetime.fromisoformat(scope.range_end)
                complete = source_key in self._details
                rows = self._details[source_key] if complete else self.repo.prepared_rows(**query)
                selected = []
                for row in rows:
                    low, high = times[row["schedule_id"] if complete else row["id"]]
                    if overlaps(low, high, range_start, range_end):
                        selected.append(row)
                self._scoped[key] = selected if complete else self._enrich_rows(entry, selected)
        return self._scoped[key]

    def active_map(self, kind, keys):
        cache = self._entities.setdefault(kind, {})
        keys = list(dict.fromkeys(keys))
        missing = [key for key in keys if key not in cache]
        if missing:
            found = self.entities.active_map(kind, missing)
            cache.update((key, found.get(key)) for key in missing)
        return {key: cache[key] for key in keys if cache[key] is not None}

    def resources(self, rows):
        resources = self.resource_identities(rows)
        state = {
            kind: [(key, value.ref, value.revision) for key, value in sorted(mapping.items())]
            for kind, mapping in resources.items()
        }
        return resources, state

    def resource_identities(self, rows):
        resources = {}
        for kind in ("machine", "operator", "supplier", "batch"):
            keys = sorted({str(row[kind + "_id"]) for row in rows if row[kind + "_id"] not in (None, "")})
            mapping = self.active_map(kind, keys)
            if set(mapping) != set(keys):
                raise WorkbenchCommandRejected("identity_missing", "安排关联的批次、设备或人员编号缺失，请到资料总览核对。")
            resources[kind] = mapping
        return resources

    def rows_span(self, rows):
        if not rows:
            return None
        intervals = self.repo.datetime_intervals(rows[0]["version"])
        starts = []
        ends = []
        for row in rows:
            low, high = intervals[row["schedule_id"]]
            starts.append(low)
            ends.append(high)
        return {"start": min(starts).isoformat(), "end": max(ends).isoformat()}

    def rows_resource_facts(self, plan_ref, rows, resources):
        _, _, origins = self.adopted_task_facts(plan_ref) if rows else ({}, None, {})
        archived = [
            resource
            for row in rows
            for resource in origins.get(row["op_id"], {}).get("resource_directory", [])
        ]
        used_refs = set()
        for row in rows:
            for kind in ("machine", "operator"):
                key = row[kind + "_id"]
                if key not in (None, ""):
                    used_refs.add((kind, resources[kind][str(key)].ref))
            supplier = origins.get(row["op_id"], {}).get("supplier")
            if supplier is not None:
                used_refs.add(("supplier", supplier["ref"]))
        return archived, used_refs

    def task_refs(self, plan_ref, rows):
        return self.references.get_task_refs(plan_ref, ((row["schedule_id"], row["op_id"], row["version"]) for row in rows))

    def operation_refs(self, ids):
        return self.references.get_operation_refs(ids)

    def projected_tasks(self, plan_ref, rows, *, resources):
        """``resources`` are the caller's identities covering at least ``rows``."""
        from .projection import project_tasks
        cache = self._tasks.setdefault(plan_ref, {})
        missing = [row for row in rows if row["schedule_id"] not in cache]
        if missing:
            task_refs = self.task_refs(plan_ref, missing)
            operations = self.operation_refs(row["op_id"] for row in missing)
            facts = {}
            tasks = project_tasks(plan_ref, missing, task_refs, operations, resources, facts=facts, context=self)
            cache.update((row["schedule_id"], task) for row, task in zip(missing, tasks))
            self._task_resources.setdefault(plan_ref, []).extend(facts["resource_directory"])
        return [cache[row["schedule_id"]] for row in rows], {"resource_directory": list(self._task_resources.get(plan_ref, ()))}

    def row_times(self, plan_ref, row):
        return self.repo.intervals(self.resolve(plan_ref).version)[row["schedule_id"]]

    def row_datetime_interval(self, plan_ref, row):
        return self.repo.datetime_intervals(self.resolve(plan_ref).version)[row["schedule_id"]]

    def calendar_selection(self, entry, scope, plan_span):
        from .calendar_context import selected_context
        key = (scope.plan_ref, scope.range_start, scope.range_end)
        if key not in self._calendar_selections:
            self._calendar_selections[key] = selected_context(
                scope,
                self.scoped_rows(entry, scope),
                plan_span,
                intervals=self.datetime_intervals(entry),
            )
        return self._calendar_selections[key]

    def datetime_intervals(self, entry):
        return self.repo.datetime_intervals(**self.query(entry))

    def all_task_refs(self, plan_ref):
        if plan_ref not in self._task_memberships:
            rows = self.task_identities(plan_ref)
            self._task_memberships[plan_ref] = {row["ref"] for row in rows}
        return self._task_memberships[plan_ref]

    def task_identities(self, plan_ref):
        if plan_ref not in self._raw_tasks:
            self._raw_tasks[plan_ref] = self._source_repo.task_refs_by_plan(plan_ref)
        return self._raw_tasks[plan_ref]

    def source_identities(self, refs):
        keys = list(dict.fromkeys(refs))
        missing = [key for key in keys if key not in self._raw_sources]
        for start in range(0, len(missing), 400):
            chunk = missing[start:start + 400]
            rows = self._source_repo.source_refs_by_refs(chunk)
            found = {row["ref"]: row for row in rows}
            self._raw_sources.update((key, found.get(key)) for key in chunk)
        return [self._raw_sources[key] for key in keys if self._raw_sources[key] is not None]
