"""Shared resource query snapshots for the live workbench and its choice controls."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_resource_query import RESOURCE_KINDS
from core.models.workbench_resource_table_query import table_query_required, toolbar_scope
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_resource_query_repo import WorkbenchResourceQueryRepository
from data.repositories.workbench_resource_table_repo import WorkbenchResourceTableRepository

from .resource_calendar_summary import resource_calendar_summary
from .resource_catalogs import WorkbenchResourceCatalogService
from .resource_entities import WorkbenchResourceService
from .resource_metrics import WorkbenchResourceMetricsService
from .resource_projection import project_resource
from .resource_readiness import process_readiness, resource_readiness
from .resource_table_facts import ResourceTableFacts
from .resource_table_states import resource_table_states
from .suppliers import WorkbenchSupplierService


@dataclass(frozen=True)
class ResourceReadRecord:
    identity: WorkbenchEntityIdentity
    entity: dict
    state: dict


class WorkbenchResourceQueryService:
    def __init__(self, conn, kind, logger=None):
        if kind not in RESOURCE_KINDS:
            raise WorkbenchCommandRejected("entity_not_found", "此资源入口不存在。", 404)
        self.conn, self.kind = conn, kind
        self.repo = WorkbenchResourceQueryRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self.logger = logger
        self._snapshot_metrics = None
        self._table_facts = None
        self._table_indexes = None
        self._table_identities = None
        if kind == "supplier":
            self.domain = WorkbenchSupplierService(conn, logger=logger)
        elif kind in ("machine_group", "shift_profile"):
            self.domain = WorkbenchResourceCatalogService(conn, kind, logger=logger)
        else:
            self.domain = WorkbenchResourceService(conn, kind, logger=logger)

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            previous = (self._snapshot_metrics, self._table_facts, self._table_indexes, self._table_identities)
            try:
                self._snapshot_metrics = WorkbenchResourceMetricsService(self.conn, self.logger)
                self._table_facts, self._table_indexes = None, {}
                self._table_identities = WorkbenchResourceTableRepository(self.conn, self.logger).identities()
                yield self.state_fingerprint()
            finally:
                self._snapshot_metrics, self._table_facts, self._table_indexes, self._table_identities = previous

    def _metrics_reader(self):
        return self._snapshot_metrics or WorkbenchResourceMetricsService(self.conn, self.logger)

    def state_fingerprint(self):
        return input_fingerprint({"scope": self.repo.scope_state(self.kind),
                                  "metric_facts": self._metrics_reader().fingerprint_facts(self.kind), "counts": self.repo.summary(),
                                  "table_refs": self._table_identities if self._table_identities is not None else WorkbenchResourceTableRepository(self.conn, self.logger).identities()})

    def summary(self):
        return self.repo.summary()

    def summary_metrics(self):
        return self._metrics_reader().summary_metrics()

    def summary_projection(self, *, clock=None):
        with TransactionManager(self.conn).transaction():
            counts, metrics = self.summary(), self.summary_metrics()
            calendar = resource_calendar_summary(self.conn, self.logger, clock=clock)
            process = process_readiness(self.conn, counts["part"], self.logger)
            return {"counts": counts, "metrics": metrics, "calendar": calendar,
                    "readiness": resource_readiness(counts, metrics, calendar, process)}

    def metrics(self, query):
        if query.kind != self.kind:
            raise WorkbenchCommandRejected("invalid_input", "查询类型与当前资源不一致。", 400)
        codes = self.matching_keys(query) if table_query_required(query) else self.repo.matching_keys(query)
        return self._metrics_reader().metrics(self.kind, codes)

    def resolve(self, ref):
        if type(ref) is not str or len(ref) != 48 or any(char not in "0123456789abcdef" for char in ref):
            raise WorkbenchCommandRejected("entity_not_found", "资源引用不正确，请从列表重新选择。", 404)
        identity = self.identities.get(ref)
        if identity is None or identity.kind != self.kind or not identity.active:
            raise WorkbenchCommandRejected("entity_not_found", "资源已不存在，旧引用不会指向同编号的新记录。", 404)
        return identity

    def detail(self, ref):
        identity = self.resolve(ref)
        state = self.domain.snapshot(identity)
        projection = {}
        if self.kind == "op_type":
            metrics = self._metrics_reader()
            projection = {"availability": metrics.availability(identity.entity_key),
                          "availability_issues": metrics.availability_issues(identity.entity_key)}
        entity = project_resource(self.kind, identity, state, **projection)
        return ResourceReadRecord(identity, entity, state)

    def page(self, query):
        if query.kind != self.kind:
            raise WorkbenchCommandRejected("invalid_input", "查询类型与当前资源不一致。", 400)
        advanced = table_query_required(query)
        rows, total = self.table_index(query).page(query) if advanced else self.repo.page(query)
        if any(row["ref"] is None for row in rows):
            raise WorkbenchCommandRejected("storage_failure", "资源永久引用缺失，未自动修补数据。", 500)
        metrics = self._metrics_reader()
        if self.kind == "op_type":
            records = self._op_type_page(rows, metrics)
        elif advanced:
            records = self._table_page_records(rows)
        else:
            records = [self.detail(row["ref"]) for row in rows]
        page = {"number": query.number, "size": query.size, "total": total,
                "pages": max(1, (total + query.size - 1) // query.size), "sort": [{"field": query.sort, "direction": query.direction}],
                "metrics": metrics.metrics(self.kind, self.matching_keys(query) if advanced else self.repo.matching_keys(query))}
        return records, page

    def _op_type_page(self, rows, metrics):
        metrics.op_type_records()
        dependencies = metrics.repo.op_type_dependencies([row["business_code"] for row in rows])
        result = []
        for row in rows:
            code = row["business_code"]
            identity = WorkbenchEntityIdentity(row["ref"], "op_type", code, row["revision"], True)
            state = {"identity": asdict(identity), "record": metrics.records["op_type"][code],
                     "profile": metrics.policies.get(code), "dependencies": dependencies[code]}
            entity = project_resource("op_type", identity, state, availability=metrics.availability(code),
                                      availability_issues=metrics.availability_issues(code))
            result.append(ResourceReadRecord(identity, entity, state))
        return result

    def _table_reader(self):
        if self._table_facts is not None:
            return self._table_facts
        identities = self._table_identities if self._table_identities is not None else WorkbenchResourceTableRepository(self.conn, self.logger).identities()
        facts = ResourceTableFacts(self._metrics_reader(), identities)
        if self._table_indexes is not None:
            self._table_facts = facts
        return facts

    def table_index(self, query):
        if query.kind != self.kind:
            raise WorkbenchCommandRejected("invalid_input", "查询类型与当前资源不一致。", 400)
        key = input_fingerprint(toolbar_scope(query))
        cache = self._table_indexes if self._table_indexes is not None else {}
        if key not in cache:
            cache[key] = self._table_reader().index(query, self.repo.toolbar_keys(query))
        return cache[key]

    def matching_keys(self, query):
        return self.table_index(query).matching_keys(query)

    def matching_rows(self, query):
        index = self.table_index(query)
        return [dict(index.rows[code]) for code in index.matching_keys(query)]

    def facets(self, query, column, search="", number=1, size=100):
        return self.table_index(query).facets(query, column, search, number, size)

    def facet_selection(self, query, column, search="", size=100):
        return self.table_index(query).facet_selection(query, column, search, size)

    def _table_page_records(self, rows):
        facts = self._table_reader()
        states = resource_table_states(facts, self.kind, [row["business_code"] for row in rows])
        result = []
        for row in rows:
            code = row["business_code"]
            identity = facts.identity(self.kind, code)
            state = states[code]
            result.append(ResourceReadRecord(identity, project_resource(self.kind, identity, state), state))
        return result
