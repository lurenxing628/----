"""Thin snapshot reader over structured ScheduleHistory and self-contained Schedule."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from functools import cached_property
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from core.infrastructure.connection_guards import query_only
from core.models.content import read_stored_json
from core.models.schedule_plan_role import ROLE_ADOPTED
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.services.common.plan_query import SchedulePlanQueryService
from core.services.scheduler.workbench_plan_catalog import PlanCatalogEntry, plan_catalog_entry
from core.services.workbench.facts.history_documents import HistoryDocuments
from core.shared.local_datetime import datetime_to_us, us_to_iso
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository
from data.repositories.workbench_plan_identity_repo import (
    WorkbenchPlanIdentityRepository,
    require_plan_ref_format,
    validate_plan_locator,
)

from .projection import project_tasks, public_time


def overlaps_us(row: Dict[str, Any], range_start_us: int, range_end_us: int) -> bool:
    if row["is_point_event"]:
        return range_start_us <= row["start_us"] < range_end_us
    return row["start_us"] < range_end_us and row["end_us"] > range_start_us


class PlanIdentityBindings:
    """Transaction-scoped plan identity bindings."""

    def __init__(
        self,
        conn,
        references: WorkbenchPlanIdentityRepository,
        *,
        repo: WorkbenchPlanCatalogRepository,
    ):
        if not conn.in_transaction:
            raise RuntimeError("Plan binding facts require the caller's read transaction")
        self.conn = conn
        self.references = references
        self._repo = repo
        self._changes = conn.total_changes
        self._resolved: Dict[str, WorkbenchPlanLocator] = {}
        self._plan_refs: Dict[WorkbenchPlanLocator, str] = {}
        self.plan_revision: int = references.read_revision()

    def _check_snapshot(self) -> None:
        if not self.conn.in_transaction or self.conn.total_changes != self._changes:
            raise RuntimeError("Plan binding read snapshot changed")

    def resolve_plan(self, plan_ref: object) -> WorkbenchPlanLocator:
        self._check_snapshot()
        ref = require_plan_ref_format(plan_ref)
        if ref in self._resolved:
            return self._resolved[ref]
        cached_version = self._repo.cached_version_by_ref(ref)
        if cached_version is not None:
            locator = WorkbenchPlanLocator(cached_version, ROLE_ADOPTED)
            self._resolved[ref] = locator
            self._plan_refs[locator] = ref
            return locator
        locator = self.references.fetch_plan_locator(ref)
        self._resolved[ref] = locator
        self._plan_refs[locator] = ref
        return locator

    def get_plan_ref(self, locator: Any) -> str:
        self._check_snapshot()
        normalized = validate_plan_locator(locator)
        if normalized in self._plan_refs:
            return self._plan_refs[normalized]
        cached_ref = self._repo.cached_plan_ref_by_version(normalized.version)
        if cached_ref is not None:
            self._plan_refs[normalized] = cached_ref
            self._resolved[cached_ref] = normalized
            return cached_ref
        ref = self.references.fetch_plan_ref(normalized)
        self._plan_refs[normalized] = ref
        self._resolved[ref] = normalized
        return ref


class PlanReadContext:
    def __init__(self, conn, logger=None, *, references=None, entities=None):
        if not conn.in_transaction:
            raise RuntimeError("Plan facts require a caller-owned read transaction")
        self.conn, self.logger = conn, logger
        self.references = references if references is not None else WorkbenchPlanIdentityRepository(conn, logger=logger)
        self.entities = entities if entities is not None else WorkbenchIdentityRepository(conn, logger=logger)
        self.repo = WorkbenchPlanCatalogRepository(conn, logger=logger)
        self._locators: Dict[str, WorkbenchPlanLocator] = {}
        self._selected: Dict[str, Tuple[PlanCatalogEntry, Dict[str, Union[str, bool]]]] = {}
        self._version_rows: Dict[int, List[Dict[str, Any]]] = {}
        self._scoped: Dict[Tuple[int, Optional[str], Optional[str]], List[Dict[str, Any]]] = {}
        self._entities: Dict[str, Dict[str, Any]] = {}
        self._entity_by_ref: Dict[str, Any] = {}
        self._tasks: Dict[str, Dict[int, Dict[str, Any]]] = {}
        self._calendar_selections: Dict[Tuple[str, Optional[str], Optional[str]], Any] = {}
        self._history_documents: Dict[int, HistoryDocuments] = {}
        self._gantt_graphs: Dict[int, Dict[str, Any]] = {}
        self._counts: Dict[Tuple[int, Optional[int], Optional[int]], Dict[str, Any]] = {}
        self.scope_depth = 0

    @cached_property
    def bindings(self) -> PlanIdentityBindings:
        return PlanIdentityBindings(self.conn, self.references, repo=self.repo)

    @property
    def plan_revision(self) -> int:
        return self.bindings.plan_revision

    @cached_property
    def state(self) -> Dict[str, Any]:
        from core.services.workbench.facts.source_revisions import PLAN_SOURCE_KEYS, read_source_revisions

        return {
            "plan_revision": self.plan_revision,
            "sources": read_source_revisions(self.conn, PLAN_SOURCE_KEYS),
        }

    @contextmanager
    def read_scope(self):
        if self.scope_depth > 0:
            self.scope_depth += 1
            try:
                yield self
            finally:
                self.scope_depth -= 1
            return
        self.scope_depth = 1
        try:
            with query_only(self.conn):
                _ = self.plan_revision
                yield self
        finally:
            self.scope_depth = 0

    def resolve(self, plan_ref):
        if plan_ref not in self._locators:
            self._locators[plan_ref] = self.bindings.resolve_plan(plan_ref)
        return self._locators[plan_ref]

    def plan_ref(self, locator) -> str:
        return self.bindings.get_plan_ref(locator)

    def selected(self, plan_ref) -> Tuple[PlanCatalogEntry, Dict[str, Union[str, bool]]]:
        """可查看的已选计划目录项与它的公开时间跨度；同一读作用域每个计划只解析一次。"""
        if plan_ref in self._selected:
            return self._selected[plan_ref]
        version = self.resolve(plan_ref).version
        history = self.repo.get_history_row(version)
        if history is None:
            raise WorkbenchCommandRejected("entity_not_found", "所选排产记录已不存在，请刷新列表后重新选择。", 404)
        entry = plan_catalog_entry(self.plan_query, history)
        if not entry.can_view:
            raise WorkbenchCommandRejected("plan_unavailable", "所选计划的状态、摘要或明细无效，看不了。请回计划列表查看不可用原因。")
        span = self.repo.get_plan_time_span(version=version)
        if span is None:
            raise WorkbenchCommandRejected("plan_unavailable", "所选计划没有可查看的明细。请刷新计划列表后重新选择。")
        public_span: Dict[str, Union[str, bool]] = {
            "start": public_time(span["start_time"]),
            "end": public_time(span["end_time"]),
        }
        if span["end_includes_point"]:
            public_span["end_inclusive"] = True
        self._selected[plan_ref] = (entry, public_span)
        return self._selected[plan_ref]

    def history(self, version: int) -> Optional[Dict[str, Any]]:
        return self.repo.get_history_row(int(version))

    def history_documents(self, version: int) -> HistoryDocuments:
        """已选中版本的 History 文档：同一读作用域每个版本一份，每份文档最多解码一次。"""
        if version not in self._history_documents:
            self._history_documents[version] = HistoryDocuments(cast(Dict[str, Any], self.history(version)))
        return self._history_documents[version]

    @cached_property
    def plan_query(self) -> SchedulePlanQueryService:
        return SchedulePlanQueryService(self.conn, repo=self.repo)

    def gantt_graph(self, version: int) -> Dict[str, Any]:
        """工序图不在计划头行里（体积大，单独读），同样按版本解码一次。"""
        normalized = int(version)
        if normalized not in self._gantt_graphs:
            self._gantt_graphs[normalized] = read_stored_json(self.repo.get_gantt_graph_json(normalized), dict)
        return self._gantt_graphs[normalized]

    @staticmethod
    def named_rows(raw_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Stored Schedule rows named for the readers: machine/operator names are the live ones.

        start_us/end_us are used as stored; Schedule's CHECK keeps them exact datetime-range microseconds,
        and each row's interval is read from them (``local_datetime.row_interval``).
        """
        return [
            {**row, "machine_name": row["live_machine_name"], "operator_name": row["live_operator_name"]}
            for row in raw_rows
        ]

    def schedule_rows(self, version: int) -> List[Dict[str, Any]]:
        normalized = int(version)
        if normalized not in self._version_rows:
            raw = self.repo.list_schedule_rows(version=normalized)
            self._version_rows[normalized] = self.named_rows(raw)
        return self._version_rows[normalized]

    def source_rows(self, *, version: int) -> List[Dict[str, Any]]:
        return self.schedule_rows(version)

    def detail_rows(self, entry) -> List[Dict[str, Any]]:
        return self.schedule_rows(entry.locator.version)

    @staticmethod
    def scope_range_us(scope) -> Tuple[Optional[int], Optional[int]]:
        if scope.range_start is None:
            return None, None
        return (
            datetime_to_us(datetime.fromisoformat(scope.range_start)),
            datetime_to_us(datetime.fromisoformat(scope.range_end)),
        )

    def count_and_span(self, entry, scope) -> Dict[str, Any]:
        version = int(entry.locator.version)
        start_us, end_us = self.scope_range_us(scope)
        key = (version, start_us, end_us)
        if key not in self._counts:
            self._counts[key] = self.repo.count_and_span(
                version=version, range_start_us=start_us, range_end_us=end_us
            )
        return self._counts[key]

    def schedule_page(self, entry, scope, *, limit: int, offset: int) -> List[Dict[str, Any]]:
        """One task page; its readers project start_us/end_us directly."""
        version = int(entry.locator.version)
        start_us, end_us = self.scope_range_us(scope)
        raw = self.repo.list_schedule_page(
            version=version, range_start_us=start_us, range_end_us=end_us, limit=limit, offset=offset
        )
        return self.named_rows(raw)

    def scoped_rows(self, entry, scope) -> List[Dict[str, Any]]:
        version = int(entry.locator.version)
        key = (version, scope.range_start, scope.range_end)
        if key not in self._scoped:
            if scope.range_start is None:
                self._scoped[key] = self.schedule_rows(version)
            elif version in self._version_rows:
                start_us, end_us = self.scope_range_us(scope)
                assert start_us is not None and end_us is not None
                self._scoped[key] = [
                    row for row in self._version_rows[version] if overlaps_us(row, start_us, end_us)
                ]
            else:
                start_us, end_us = self.scope_range_us(scope)
                raw = self.repo.list_schedule_rows(
                    version=version, range_start_us=start_us, range_end_us=end_us
                )
                self._scoped[key] = self.named_rows(raw)
        return self._scoped[key]

    def active_map(self, kind, keys):
        cache = self._entities.setdefault(kind, {})
        keys = list(dict.fromkeys(keys))
        missing = [key for key in keys if key not in cache]
        if missing:
            found = self.entities.active_map(kind, missing)
            cache.update((key, found.get(key)) for key in missing)
        return {key: cache[key] for key in keys if cache[key] is not None}

    def entity_by_ref(self, ref: str):
        """The identity a permanent ref names, in any state, or None; an active one also answers ``active_map``
        for its business key, which has at most one active identity."""
        if ref not in self._entity_by_ref:
            identity = self.entities.get(ref)
            self._entity_by_ref[ref] = identity
            if identity is not None and identity.active:
                self._entities.setdefault(identity.kind, {})[identity.entity_key] = identity
        return self._entity_by_ref[ref]

    def resources(self, rows):
        resources = self.resource_identities(rows)
        state = {
            kind: [(key, value.ref, value.revision) for key, value in sorted(mapping.items())]
            for kind, mapping in resources.items()
        }
        return resources, state

    def resource_identities(self, rows):
        resources = {}
        for kind in ("machine", "operator", "batch"):
            keys = sorted({str(row[kind + "_id"]) for row in rows if row[kind + "_id"] not in (None, "")})
            mapping = self.active_map(kind, keys)
            if set(mapping) != set(keys):
                raise WorkbenchCommandRejected("identity_missing", "安排关联的批次、设备或人员编号缺失，请到资料总览核对。")
            resources[kind] = mapping
        return resources

    @staticmethod
    def rows_span(rows) -> Optional[Dict[str, str]]:
        if not rows:
            return None
        return {
            "start": us_to_iso(min(row["start_us"] for row in rows)),
            "end": us_to_iso(max(row["end_us"] for row in rows)),
        }

    def projected_tasks(self, plan_ref, rows, *, resources) -> List[Dict[str, Any]]:
        """``resources`` are the caller's identities covering at least ``rows``."""
        cache = self._tasks.setdefault(plan_ref, {})
        missing = [row for row in rows if row["schedule_id"] not in cache]
        if missing:
            tasks = project_tasks(plan_ref, missing, resources)
            cache.update((row["schedule_id"], task) for row, task in zip(missing, tasks))
        return [cache[row["schedule_id"]] for row in rows]

    def calendar_selection(self, entry, scope, plan_span):
        from .calendar_context import selected_context

        key = (scope.plan_ref, scope.range_start, scope.range_end)
        if key not in self._calendar_selections:
            self._calendar_selections[key] = selected_context(scope, self.scoped_rows(entry, scope), plan_span)
        return self._calendar_selections[key]
