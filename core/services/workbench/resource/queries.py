"""Shared resource query snapshots for the live workbench and its choice controls."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_resource_query import RESOURCE_KINDS
from core.models.workbench_resource_table_query import table_query_required, toolbar_scope
from data.repositories.workbench_resource_query_repo import WorkbenchResourceQueryRepository
from data.repositories.workbench_resource_table_repo import WorkbenchResourceTableRepository

from .calendar_summary import resource_calendar_summary
from .catalogs import WorkbenchResourceCatalogService
from .entities import WorkbenchResourceService
from .metrics import RESOURCE_KEYS, WorkbenchResourceMetricsService
from .projection import project_resource
from .readiness import process_readiness, resource_readiness
from .states import ResourceChangePreparation
from .suppliers import WorkbenchSupplierService
from .table_facts import ResourceTableFacts, capture_change_facts
from .table_states import resource_table_states


@dataclass(frozen=True)
class ResourceReadRecord:
    identity: WorkbenchEntityIdentity
    entity: dict
    state: dict


class WorkbenchResourceQueryService:
    def __init__(self, conn, kind, logger=None):
        if kind not in RESOURCE_KINDS:
            raise WorkbenchCommandRejected("entity_not_found", "没有这个资源页面。请从左边的资料总览重新进入。", 404)
        self.conn, self.kind = conn, kind
        self.repo = WorkbenchResourceQueryRepository(conn, logger=logger)
        self.logger = logger
        self._snapshot_metrics = None
        self._table_facts = None
        self._table_indexes = None
        self._table_identities = None
        self._identities_by_ref = None
        self._resolved_by_ref = {}
        self._snapshot_scope = None
        self._report_revisions = {}
        if kind == "supplier":
            self.domain = WorkbenchSupplierService(conn, logger=logger)
        elif kind in ("machine_group", "shift_profile"):
            self.domain = WorkbenchResourceCatalogService(conn, kind, logger=logger)
        else:
            self.domain = WorkbenchResourceService(conn, kind, logger=logger)

    @contextmanager
    def read_snapshot(self, *, capture_fingerprint=True):
        with TransactionManager(self.conn).transaction():
            previous = (self._snapshot_metrics, self._table_facts, self._table_indexes,
                        self._table_identities, self._identities_by_ref, self._resolved_by_ref,
                        self._snapshot_scope, self._report_revisions)
            try:
                self._snapshot_metrics = WorkbenchResourceMetricsService(self.conn, self.logger)
                self._table_facts, self._table_indexes = None, {}
                identities = self._read_identities() if capture_fingerprint else None
                self._table_identities = identities
                self._identities_by_ref = None if identities is None else {row["ref"]: row for row in identities}
                self._resolved_by_ref = {}
                self._snapshot_scope = None
                self._report_revisions = {}
                yield self.state_fingerprint() if capture_fingerprint else None
            finally:
                (self._snapshot_metrics, self._table_facts, self._table_indexes,
                 self._table_identities, self._identities_by_ref, self._resolved_by_ref,
                 self._snapshot_scope, self._report_revisions) = previous

    def _metrics_reader(self) -> WorkbenchResourceMetricsService:
        return self._snapshot_metrics or WorkbenchResourceMetricsService(self.conn, self.logger)

    def state_fingerprint(self):
        scope = self._snapshot_scope
        if scope is None:
            scope = self.repo.scope_state(
                self.kind, identities=self._table_identities, report_revisions=self._report_revisions
            )
            if self._snapshot_metrics is not None:
                self._snapshot_scope = scope
        return {"scope": scope,
                "metric_facts": self._metrics_reader().fingerprint_facts(self.kind),
                "table_refs": self._table_identities if self._table_identities is not None else self._read_identities()}

    def _read_identities(self):
        return WorkbenchResourceTableRepository(self.conn, self.logger).identities(self._metrics_reader().identity_kinds(self.kind))

    def create_snapshot(self):
        if self._snapshot_metrics is None or self._table_identities is None:
            return self.repo.create_relations(self.kind)
        relations = {"machine": ("op_type", "machine_group"),
                     "operator": ("op_type", "shift_profile"), "supplier": ("op_type",)}.get(self.kind, ())
        if not relations:
            return None
        facts = self._snapshot_metrics.facts
        refs = self._table_reader().identities
        result = {}
        for relation in relations:
            key = RESOURCE_KEYS[relation]
            allowed = (("external", "both") if self.kind == "supplier" else ("internal", "both")) if relation == "op_type" else None
            rows = [
                {**row, "ref": refs.get((relation, row[key]), {}).get("ref"),
                 "revision": refs.get((relation, row[key]), {}).get("revision")}
                for row in facts[relation] if allowed is None or row["category"] in allowed
            ]
            rows.sort(key=lambda item: item[key])
            result[relation] = rows
        if self.kind == "operator":
            result["shift_pattern"] = sorted(facts["shift_pattern"], key=lambda item: (item["profile_id"], item["day_offset"]))
        return result

    def preparation(self, *, refs=None, codes=None, selected_refs=(), selected_codes=None, names=None,
                    machine_authorizations=False, known_identities=()):
        if self._table_identities is not None:
            return ResourceChangePreparation(self._table_reader())
        repo = WorkbenchResourceTableRepository(self.conn, self.logger)
        if refs is not None or codes is not None:
            facts = capture_change_facts(self.conn, self.logger, refs=refs or (), codes=codes,
                                         selected_refs=selected_refs, selected_codes=selected_codes,
                                         machine_authorizations=machine_authorizations,
                                         known_identities=known_identities)
            owners = {kind: repo.name_owners(kind, values) for kind, values in (names or {}).items()}
            return ResourceChangePreparation(facts, name_reader=repo.name_owners, names=owners)
        return ResourceChangePreparation(ResourceTableFacts(self._metrics_reader(), repo.identities(),
                                                           scope_state=self._snapshot_scope,
                                                           report_revisions=self._report_revisions))

    def preparation_for(self, action, payload, *, ref=None):
        selected = [ref for value in payload.get("relationships", {}).values()
                    for ref in (value if isinstance(value, list) else [value]) if ref is not None]
        names = ({self.kind: [payload["label"]]} if self.kind in ("op_type", "machine_group", "shift_profile")
                 and "label" in payload else None)
        return self.preparation(refs=[] if ref is None else [ref],
            codes={self.kind: [payload["business_code"]]} if action == "create" else {},
            selected_refs=selected, names=names)

    def summary_projection(self):
        counts, metrics = self.repo.summary(), self._metrics_reader().summary_metrics()
        calendar = resource_calendar_summary(self.conn, self.logger)
        process = process_readiness(self.conn, counts["part"], self.logger)
        return {"counts": counts, "metrics": metrics, "calendar": calendar,
                "readiness": resource_readiness(counts, metrics, calendar, process)}

    def resolve_refs(self, refs):
        for ref in refs:
            if type(ref) is not str or len(ref) != 48 or any(char not in "0123456789abcdef" for char in ref):
                raise WorkbenchCommandRejected("entity_not_found", "这条资源记录已失效，页面没有打开。请从列表重新选择。", 404)
        if not refs:
            return []
        by_ref = (self._identities_by_ref if self._identities_by_ref is not None else {
            row["ref"]: row
            for row in WorkbenchResourceTableRepository(self.conn, self.logger).identities_by_refs(refs)
        })
        result = []
        for ref in refs:
            row = by_ref.get(ref)
            if row is None or row["kind"] != self.kind:
                raise WorkbenchCommandRejected("entity_not_found", "这条资源已经删除了。请从列表重新选择。", 404)
            self._resolved_by_ref[ref] = row
            result.append(WorkbenchEntityIdentity(row["ref"], row["kind"], row["entity_key"], int(row["revision"]), True))
        return result

    def resolve(self, ref):
        return self.resolve_refs([ref])[0]

    def current_with_identity(self, identity):
        known = self._resolved_by_ref.pop(identity.ref, None)
        preparation = self.preparation(refs=[identity.ref],
                                       known_identities=[known] if known is not None else ())
        current = preparation.current(self.kind, identity)
        return preparation.state(self.kind, current.entity_key)

    def detail(self, ref):
        identity = self.resolve(ref)
        if self._table_identities is not None:
            if self.kind == "op_type":
                return self._op_type_page([{"ref": identity.ref, "business_code": identity.entity_key,
                                           "revision": identity.revision}], self._metrics_reader())[0]
            return self._table_page_records([{"business_code": identity.entity_key}])[0]
        state = self.current_with_identity(identity)
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
        if advanced:
            index = self.table_index(query)
            keys = index.matching_keys(query)
            offset = (query.number - 1) * query.size
            rows, total = [index.rows[code] for code in keys[offset:offset + query.size]], len(keys)
        else:
            rows, total = self.repo.page(query)
            keys = None
        if any(row["ref"] is None for row in rows):
            raise WorkbenchCommandRejected("storage_failure", "这条资源在资料里查不到编号，页面没有打开，数据也没有被改动。请到资料总览核对后重试。", 500)
        metrics = self._metrics_reader()
        if self.kind == "op_type":
            records = self._op_type_page(rows, metrics)
        else:
            records = self._table_page_records(rows)
        page = {"number": query.number, "size": query.size, "total": total,
                "pages": max(1, (total + query.size - 1) // query.size), "sort": [{"field": query.sort, "direction": query.direction}],
                "metrics": metrics.metrics(self.kind, keys if keys is not None else self.toolbar_matching_keys(query))}
        return records, page

    def _op_type_page(self, rows, metrics):
        metrics.op_type_records()
        codes = [row["business_code"] for row in rows]
        dependencies = self._table_reader().op_type_dependencies(codes)
        result = []
        for row in rows:
            code = row["business_code"]
            identity = WorkbenchEntityIdentity(row["ref"], "op_type", code, row["revision"], True)
            record = metrics.records["op_type"].get(code)
            if record is None:
                raise WorkbenchCommandRejected("storage_failure", "这条资源的编号和实际记录对不上，操作没有执行。请联系维护人员核对数据。", 500)
            state = {"identity": asdict(identity), "record": record,
                     "profile": metrics.policies.get(code), "dependencies": dependencies[code]}
            entity = project_resource("op_type", identity, state, availability=metrics.availability(code),
                                      availability_issues=metrics.availability_issues(code))
            result.append(ResourceReadRecord(identity, entity, state))
        return result

    def _table_reader(self):
        if self._table_facts is not None:
            return self._table_facts
        identities = self._table_identities if self._table_identities is not None else self._read_identities()
        facts = ResourceTableFacts(self._metrics_reader(), identities, scope_state=self._snapshot_scope,
                                   identity_kinds=self._metrics_reader().identity_kinds(self.kind),
                                   report_revisions=self._report_revisions)
        if self._table_indexes is not None:
            self._table_facts = facts
        return facts

    def table_index(self, query):
        if query.kind != self.kind:
            raise WorkbenchCommandRejected("invalid_input", "查询类型与当前资源不一致。", 400)
        key = tuple(toolbar_scope(query).items())
        cache = self._table_indexes if self._table_indexes is not None else {}
        if key not in cache:
            cache[key] = self._table_reader().index(query, self.repo.toolbar_keys(query))
        return cache[key]

    def matching_keys(self, query):
        return self.table_index(query).matching_keys(query)

    def toolbar_matching_keys(self, query):
        """Toolbar-scope keys straight from SQL; column filters and business-column sorts must use matching_keys."""
        if table_query_required(query):
            raise WorkbenchCommandRejected("invalid_input", "列筛选与业务列排序请使用查询服务的 matching_keys 统一入口。", 400)
        return self.repo.toolbar_keys(query)

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
