"""Read bounded material facts per snapshot, without whole-table prewarming."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterator, List, Optional

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_material_query import MaterialPageRequest
from core.models.workbench_resource_table_query import toolbar_scope
from core.services.workbench.facts.source_revisions import MATERIAL_SOURCE_KEYS, read_source_revisions
from core.services.workbench.facts.table_columns import sql_order
from core.shared.refs import is_ref
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_material_query_repo import WorkbenchMaterialQueryRepository

from .table_facts import MaterialRow, material_row, material_table_index


@dataclass(frozen=True)
class MaterialReadRecord:
    identity: WorkbenchEntityIdentity
    entity: Dict[str, Any]
    state: Dict[str, Any]

    def write_state(self) -> Dict[str, Any]:
        return {"identity": asdict(self.identity), "material": self.state["material"]}


def _filters(query: MaterialPageRequest):
    return tuple((column, condition["mode"], tuple(condition["values"])) for column, condition in query.column_filters.items())


def _validate_ref(ref):
    if not is_ref(ref):
        raise WorkbenchCommandRejected("entity_not_found", "物料记录不存在，请返回列表重新选择。", 404)


def _project(row: MaterialRow):
    raw = row.raw
    issues = [{"code": "stock_level_unknown", "scope": "collection", "message": "还没有设置低库存的判断标准。"}]
    if row.stock is None:
        issues.append({"code": "stock_unknown", "message": "库存数量还没填写。"})
    identity = WorkbenchEntityIdentity(row.ref, "material", raw["material_id"], raw["revision"], True)
    entity = {"ref": identity.ref, "business_code": raw["material_id"], "label": raw["name"],
              "status": raw["status"], "fields": {key: raw[key] for key in ("spec", "unit", "stock_qty", "remark")},
              "relationships": {"batch_requirement_count": raw["requirement_count"]}, "issues": issues}
    return MaterialReadRecord(identity, entity, {"identity": identity, "material": raw})


@dataclass
class MaterialFactScope:
    reader: WorkbenchMaterialQueryService
    fingerprint: Optional[Dict[str, Any]] = None
    checked: Dict[str, MaterialRow] = field(default_factory=dict)
    records: Dict[str, MaterialReadRecord] = field(default_factory=dict)
    indexes: Dict[Any, Any] = field(default_factory=dict)
    counts_by_scope: Dict[Any, Dict[str, int]] = field(default_factory=dict)
    matches: Dict[Any, List[str]] = field(default_factory=dict)

    def state_fingerprint(self) -> Dict[str, Any]:
        if self.fingerprint is None:
            self.fingerprint = {"revisions": read_source_revisions(self.reader.conn, MATERIAL_SOURCE_KEYS)}
        return self.fingerprint

    def _checked(self, raw) -> MaterialRow:
        """Each captured row passes the storage check once per snapshot; every query path shares it."""
        code = raw["material_id"]
        if code not in self.checked:
            self.checked[code] = material_row(raw)
        elif "requirement_count" in raw and "requirement_count" not in self.checked[code].raw:
            self.checked[code].raw["requirement_count"] = raw["requirement_count"]
        return self.checked[code]

    def _record(self, row: MaterialRow) -> MaterialReadRecord:
        code = row.raw["material_id"]
        if code not in self.records:
            self.records[code] = _project(row)
        return self.records[code]

    def _records_for(self, rows: List[MaterialRow]) -> List[MaterialReadRecord]:
        missing_codes = [
            row.raw["material_id"]
            for row in rows
            if row.raw["material_id"] not in self.records and "requirement_count" not in row.raw
        ]
        if missing_codes:
            counts = self.reader.repo.requirement_counts_for(missing_codes)
            for row in rows:
                code = row.raw["material_id"]
                if "requirement_count" not in row.raw:
                    row.raw["requirement_count"] = counts.get(code, 0)
        return [self._record(row) for row in rows]

    def metrics(self, query: MaterialPageRequest):
        return {"scope": "filtered", "counts": self._counts(query),
                "basis": {"low_stock": "尚未设置低库存阈值。"},
                "issues": []}

    def _counts(self, query: MaterialPageRequest):
        """One SQL count per toolbar scope and column filters; filters narrow it to the matched codes.
        Unshown rows are counted, never materialized or validated."""
        key = (tuple(toolbar_scope(query).items()), _filters(query))
        if key not in self.counts_by_scope:
            keys = self._matching_keys(query) if query.column_filters else None
            self.counts_by_scope[key] = self.reader.repo.status_counts(query, keys)
        return self.counts_by_scope[key]

    def resolve_many(self, refs) -> None:
        if not refs:
            return
        identities = self.reader.identities.map_by_refs(refs)
        for ref in refs:
            identity = identities.get(ref)
            if identity is None or not identity.active or identity.kind != "material":
                raise WorkbenchCommandRejected("entity_not_found", "这条物料已经不在了，请重新选择。请刷新后重新选择。", 404)

    def detail(self, ref) -> MaterialReadRecord:
        _validate_ref(ref)
        row = self.reader.repo.get_by_ref(ref)
        if row is None:
            self.reader._resolve_identity(ref)
            raise WorkbenchCommandRejected("storage_failure", "物料的系统编号和实际记录对不上。请刷新重试；仍不行请联系维护人员。", 500)
        return self._record(self._checked(row))

    def selected_rows(self, refs):
        """Checked rows in the explicit ref order; a deleted selection is rejected, never skipped."""
        if not refs:
            return []
        rows = self.reader.repo.rows_by_refs(refs)
        return [self._selected(row) for row in rows]

    def _selected(self, raw) -> MaterialRow:
        if raw is None:
            raise WorkbenchCommandRejected("entity_not_found", "勾选的物料已经删除了。请刷新后重新勾选。", 404)
        return self._checked(raw)

    def _matching_keys(self, query: MaterialPageRequest):
        """One filter-and-order pass per table query; page, count and metrics share it."""
        key = (tuple(toolbar_scope(query).items()), query.sort, query.direction, _filters(query))
        if key not in self.matches:
            self.matches[key] = self.table_index(query).matching_keys(query)
        return self.matches[key]

    def count(self, query: MaterialPageRequest) -> int:
        if query.column_filters:
            return len(self._matching_keys(query))
        return self._counts(query)["total"]

    def page(self, query: MaterialPageRequest):
        order = sql_order(query)
        if order is None:
            index = self.table_index(query)
            matching = self._matching_keys(query)
            start = (query.number - 1) * query.size
            page_keys = matching[start : start + query.size]
            records, total = self._records_for([index.rows[code] for code in page_keys]), len(matching)
        else:
            total = self._counts(query)["total"]
            offset = (query.number - 1) * query.size
            raw_rows = self.reader.repo.page_rows(query, order) if offset < total else []
            records = self._records_for([self._checked(row) for row in raw_rows])
        page = {"number": query.number, "size": query.size, "total": total,
                "pages": max(1, (total + query.size - 1) // query.size),
                "sort": [{"field": query.sort, "direction": query.direction}]}
        return records, page

    def table_index(self, query):
        key = tuple(toolbar_scope(query).items())
        if key not in self.indexes:
            rows = self.reader.repo.toolbar_rows(query)
            self.indexes[key] = material_table_index([self._checked(row) for row in rows])
        return self.indexes[key]

    def matching_rows(self, query):
        """Checked rows of the whole query scope, in query order."""
        order = sql_order(query)
        if order is None:
            index = self.table_index(query)
            return [index.rows[code] for code in self._matching_keys(query)]
        return [self._checked(row) for row in self.reader.repo.toolbar_rows(query, order)]

    def facets(self, query, column, search="", number=1, size=100):
        return self.table_index(query).facets(column, search, number, size)

    def facet_selection(self, query, column, search=""):
        return self.table_index(query).facet_selection(column, search)


class WorkbenchMaterialQueryService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.repo = WorkbenchMaterialQueryRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)

    @contextmanager
    def read_snapshot(self) -> Iterator[MaterialFactScope]:
        with TransactionManager(self.conn).transaction():
            scope = MaterialFactScope(reader=self)
            scope.state_fingerprint()
            yield scope

    def _resolve_identity(self, ref):
        identity = self.identities.get(ref)
        if identity is None or not identity.active or identity.kind != "material":
            raise WorkbenchCommandRejected("entity_not_found", "这条物料已经不在了，请重新选择。请刷新后重新选择。", 404)
        return identity

    def detail(self, ref) -> MaterialReadRecord:
        _validate_ref(ref)
        row = self.repo.get_by_ref(ref)
        if row is None:
            self._resolve_identity(ref)
            raise WorkbenchCommandRejected("storage_failure", "物料的系统编号和实际记录对不上。请刷新重试；仍不行请联系维护人员。", 500)
        return _project(material_row(row))
