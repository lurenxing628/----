"""Explicit per-snapshot read scope for workbench resource queries."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_resource_query import ResourcePageRequest
from core.models.workbench_resource_status import PUBLIC_STATUS_VALUES
from core.models.workbench_resource_table_query import toolbar_scope
from core.services.workbench.facts.source_revisions import RESOURCE_SOURCE_KEYS, read_source_revisions
from core.services.workbench.facts.table_columns import sql_order
from data.repositories.workbench_resource_table_repo import WorkbenchResourceTableRepository

from .calendar_summary import resource_calendar_summary
from .metrics import WorkbenchResourceMetricsService
from .projection import project_resource
from .readiness import process_readiness, resource_readiness
from .states import ResourceChangePreparation
from .table_facts import ResourceTableFacts, capture_change_facts
from .table_states import resource_table_states

if TYPE_CHECKING:
    from .queries import WorkbenchResourceQueryService


@dataclass(frozen=True)
class ResourceReadRecord:
    identity: WorkbenchEntityIdentity
    entity: dict
    state: dict


@dataclass
class ResourceFactScope:
    reader: WorkbenchResourceQueryService
    metrics: WorkbenchResourceMetricsService
    capture_fingerprint: bool = True
    table_facts_instance: Optional[ResourceTableFacts] = None
    table_indexes: Dict[Any, Any] = field(default_factory=dict)
    table_identities: Optional[List[Dict[str, Any]]] = None
    revisions: Optional[Dict[str, int]] = None

    @property
    def conn(self):
        return self.reader.conn

    @property
    def kind(self) -> str:
        return self.reader.kind

    @property
    def logger(self):
        return self.reader.logger

    @property
    def repo(self):
        return self.reader.repo

    def state_fingerprint(self) -> Dict[str, int]:
        if self.revisions is None:
            self.revisions = read_source_revisions(self.conn, RESOURCE_SOURCE_KEYS)
        return self.revisions

    def _read_identities(self) -> List[Dict[str, Any]]:
        return WorkbenchResourceTableRepository(self.conn, self.logger).identities(
            self.metrics.identity_kinds(self.kind)
        )

    def summary_projection(self, as_of: datetime) -> Dict[str, Any]:
        counts = self.repo.summary()
        metrics = self.metrics.summary_metrics(
            {kind: self.repo.status_counts(ResourcePageRequest(kind)) for kind in PUBLIC_STATUS_VALUES}
        )
        calendar = resource_calendar_summary(self.conn, self.logger, as_of=as_of)
        process = process_readiness(self.conn, counts["part"], self.logger)
        return {
            "counts": counts,
            "metrics": metrics,
            "calendar": calendar,
            "readiness": resource_readiness(counts, metrics, calendar, process),
        }

    def detail(self, ref) -> ResourceReadRecord:
        identity = self.reader.resolve(ref)
        state = self.reader.current_with_identity(identity)
        projection = {}
        if self.kind == "op_type":
            projection = {
                "availability": self.metrics.availability(identity.entity_key),
                "availability_issues": self.metrics.availability_issues(identity.entity_key),
            }
        entity = project_resource(self.kind, identity, state, **projection)
        return ResourceReadRecord(identity, entity, state)

    def page(self, query):
        """所有涉及的列都有 SQL 键就在 SQL 里分页，否则在格子索引里筛选、排序；计数都走 SQL，工种的能力计数例外。"""
        if query.kind != self.kind:
            raise WorkbenchCommandRejected("invalid_input", "查询类型与当前资源不一致。", 400)
        order = sql_order(query)
        keys = None
        if order is None:
            index = self.table_index(query)
            keys = index.matching_keys(query)
            offset = (query.number - 1) * query.size
            rows = [index.rows[code] for code in keys[offset : offset + query.size]]
        else:
            rows = self.repo.page_rows(query, order)
        if any(row["ref"] is None for row in rows):
            raise WorkbenchCommandRejected(
                "storage_failure",
                "这条资源在资料里查不到编号，页面没有打开，数据也没有被改动。请到资料总览核对后重试。",
                500,
            )
        records = self._op_type_page(rows) if self.kind == "op_type" else self._table_page_records(rows)
        if self.kind == "op_type":
            codes = keys if keys is not None else self.repo.toolbar_keys(query)
            metrics, total = self.metrics.op_type_metrics(codes), len(codes)
        else:
            counts = self.repo.status_counts(query, keys)
            metrics, total = self.metrics.status_metrics(counts), counts["total"]
        page = {
            "number": query.number,
            "size": query.size,
            "total": total,
            "pages": max(1, (total + query.size - 1) // query.size),
            "sort": [{"field": query.sort, "direction": query.direction}],
            "metrics": metrics,
        }
        return records, page

    def _op_type_page(self, rows) -> List[ResourceReadRecord]:
        if not rows:
            return []
        self.metrics.op_type_records()
        codes = [row["business_code"] for row in rows]
        dependencies = WorkbenchResourceTableRepository(self.conn, self.logger).assigned_counts("op_type", codes)
        result = []
        for row in rows:
            code = row["business_code"]
            identity = WorkbenchEntityIdentity(row["ref"], "op_type", code, row["revision"], True)
            record = self.metrics.records["op_type"][code]
            state = {
                "identity": asdict(identity),
                "record": record,
                "profile": self.metrics.policies.get(code),
                "dependencies": dependencies[code],
            }
            entity = project_resource(
                "op_type",
                identity,
                state,
                availability=self.metrics.availability(code),
                availability_issues=self.metrics.availability_issues(code),
            )
            result.append(ResourceReadRecord(identity, entity, state))
        return result

    def table_facts(self) -> ResourceTableFacts:
        if self.table_facts_instance is not None:
            return self.table_facts_instance
        if self.table_identities is None:
            self.table_identities = self._read_identities()
        facts = ResourceTableFacts(
            self.metrics,
            self.table_identities,
            identity_kinds=self.metrics.identity_kinds(self.kind),
        )
        self.table_facts_instance = facts
        return facts

    def table_preparation(self) -> ResourceChangePreparation:
        return ResourceChangePreparation(self.table_facts())

    def table_index(self, query):
        if query.kind != self.kind:
            raise WorkbenchCommandRejected("invalid_input", "查询类型与当前资源不一致。", 400)
        key = tuple(toolbar_scope(query).items())
        if key not in self.table_indexes:
            self.table_indexes[key] = self.table_facts().index(query, self.repo.toolbar_keys(query))
        return self.table_indexes[key]

    def matching_keys(self, query):
        order = sql_order(query)
        if order is None:
            return self.table_index(query).matching_keys(query)
        if query.kind != self.kind:
            raise WorkbenchCommandRejected("invalid_input", "查询类型与当前资源不一致。", 400)
        return self.repo.toolbar_keys(query, order)

    def facets(self, query, column, search="", number=1, size=100):
        return self.table_index(query).facets(column, search, number, size)

    def facet_selection(self, query, column, search=""):
        return self.table_index(query).facet_selection(column, search)

    def _table_page_records(self, rows) -> List[ResourceReadRecord]:
        if not rows:
            return []
        codes = [row["business_code"] for row in rows]
        if self.table_facts_instance is not None:
            facts = self.table_facts_instance
        else:
            known = [
                {
                    "ref": row["ref"],
                    "kind": self.kind,
                    "entity_key": row["business_code"],
                    "revision": row["revision"],
                    "active": 1,
                }
                for row in rows
            ]
            facts = capture_change_facts(
                self.conn,
                self.logger,
                refs=(),
                codes={self.kind: codes},
                known_identities=known,
            )
        states = resource_table_states(facts, self.kind, codes)
        result = []
        for code in codes:
            identity = facts.identity(self.kind, code)
            state = states[code]
            result.append(ResourceReadRecord(identity, project_resource(self.kind, identity, state), state))
        return result
