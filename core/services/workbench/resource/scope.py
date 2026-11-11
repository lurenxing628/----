"""Explicit per-snapshot read scope for workbench resource queries."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_resource_table_query import table_query_required, toolbar_scope
from core.services.workbench.facts.source_revisions import RESOURCE_SOURCE_KEYS, read_source_revisions
from data.repositories.workbench_resource_table_repo import WorkbenchResourceTableRepository

from .calendar_summary import resource_calendar_summary
from .metrics import RESOURCE_KEYS, WorkbenchResourceMetricsService
from .projection import project_resource
from .readiness import process_readiness, resource_readiness
from .states import ResourceChangePreparation
from .table_facts import ResourceTableFacts
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
    snapshot_scope: Optional[Dict[str, Any]] = None
    revisions: Optional[Dict[str, int]] = None
    report_revisions: Dict[str, int] = field(default_factory=dict)
    table_warmed: bool = False

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

    def _ensure_table_snapshot(self) -> None:
        if not self.capture_fingerprint:
            return
        if self.table_identities is None:
            self.table_identities = self._read_identities()
        if not self.table_warmed:
            self.snapshot_scope = self.repo.scope_state(
                self.kind, identities=self.table_identities, report_revisions=self.report_revisions
            )
            self.metrics.fingerprint_facts(self.kind)
            self.table_warmed = True

    def create_snapshot(self):
        self._ensure_table_snapshot()
        relations = {
            "machine": ("op_type", "machine_group"),
            "operator": ("op_type", "shift_profile"),
            "supplier": ("op_type",),
        }.get(self.kind, ())
        if not relations:
            return None
        facts = self.metrics.facts
        refs = self.table_facts().identities
        result = {}
        for relation in relations:
            key = RESOURCE_KEYS[relation]
            allowed = (
                (("external", "both") if self.kind == "supplier" else ("internal", "both"))
                if relation == "op_type"
                else None
            )
            rows = [
                {
                    **row,
                    "ref": refs.get((relation, row[key]), {}).get("ref"),
                    "revision": refs.get((relation, row[key]), {}).get("revision"),
                }
                for row in facts[relation]
                if allowed is None or row["category"] in allowed
            ]
            rows.sort(key=lambda item: item[key])
            result[relation] = rows
        if self.kind == "operator":
            result["shift_pattern"] = sorted(
                facts["shift_pattern"], key=lambda item: (item["profile_id"], item["day_offset"])
            )
        return result

    def summary_projection(self) -> Dict[str, Any]:
        counts, metrics = self.repo.summary(), self.metrics.summary_metrics()
        calendar = resource_calendar_summary(self.conn, self.logger)
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
        if query.kind != self.kind:
            raise WorkbenchCommandRejected("invalid_input", "查询类型与当前资源不一致。", 400)
        self._ensure_table_snapshot()
        advanced = table_query_required(query)
        if advanced:
            index = self.table_index(query)
            keys = index.matching_keys(query)
            offset = (query.number - 1) * query.size
            rows, total = [index.rows[code] for code in keys[offset : offset + query.size]], len(keys)
        else:
            rows, total = self.repo.page(query)
            keys = None
        if any(row["ref"] is None for row in rows):
            raise WorkbenchCommandRejected(
                "storage_failure",
                "这条资源在资料里查不到编号，页面没有打开，数据也没有被改动。请到资料总览核对后重试。",
                500,
            )
        records = self._op_type_page(rows) if self.kind == "op_type" else self._table_page_records(rows)
        page = {
            "number": query.number,
            "size": query.size,
            "total": total,
            "pages": max(1, (total + query.size - 1) // query.size),
            "sort": [{"field": query.sort, "direction": query.direction}],
            "metrics": self.metrics.metrics(self.kind, keys if keys is not None else self.matching_keys(query)),
        }
        return records, page

    def _op_type_page(self, rows) -> List[ResourceReadRecord]:
        self.metrics.op_type_records()
        codes = [row["business_code"] for row in rows]
        dependencies = self.table_facts().op_type_dependencies(codes)
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
        self._ensure_table_snapshot()
        if self.table_facts_instance is not None:
            return self.table_facts_instance
        if self.table_identities is None:
            self.table_identities = self._read_identities()
        facts = ResourceTableFacts(
            self.metrics,
            self.table_identities,
            scope_state=self.snapshot_scope,
            identity_kinds=self.metrics.identity_kinds(self.kind),
            report_revisions=self.report_revisions,
        )
        self.table_facts_instance = facts
        self.table_warmed = True
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
        if table_query_required(query):
            return self.table_index(query).matching_keys(query)
        if query.kind != self.kind:
            raise WorkbenchCommandRejected("invalid_input", "查询类型与当前资源不一致。", 400)
        return self.repo.toolbar_keys(query)

    def facets(self, query, column, search="", number=1, size=100):
        return self.table_index(query).facets(column, search, number, size)

    def facet_selection(self, query, column, search=""):
        return self.table_index(query).facet_selection(column, search)

    def _table_page_records(self, rows) -> List[ResourceReadRecord]:
        facts = self.table_facts()
        states = resource_table_states(facts, self.kind, [row["business_code"] for row in rows])
        result = []
        for row in rows:
            code = row["business_code"]
            identity = facts.identity(self.kind, code)
            state = states[code]
            result.append(ResourceReadRecord(identity, project_resource(self.kind, identity, state), state))
        return result
