"""Read actual material facts once per snapshot, without metadata repair or demo fallback."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Dict

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_material_query import MaterialPageRequest
from core.models.workbench_resource_table_query import table_query_required, toolbar_scope
from core.services.workbench.facts.source_revisions import MATERIAL_SOURCE_KEYS, read_source_revisions
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_material_query_repo import WorkbenchMaterialQueryRepository

from .table_facts import (
    MaterialRow,
    material_counts,
    material_ordered_rows,
    material_row,
    material_table_index,
    material_toolbar_rows,
)


@dataclass(frozen=True)
class MaterialReadRecord:
    identity: WorkbenchEntityIdentity
    entity: Dict[str, Any]
    state: Dict[str, Any]


def _validate_ref(ref):
    if not isinstance(ref, str) or len(ref) != 48 or any(char not in "0123456789abcdef" for char in ref):
        raise WorkbenchCommandRejected("entity_not_found", "物料记录不存在，请返回列表重新选择。", 404)


def _project(row: MaterialRow):
    raw = row.raw
    issues = [{"code": "stock_level_unknown", "scope": "collection", "message": "还没有设置低库存的判断标准。"}]
    if row.stock is None:
        issues.append({"code": "stock_unknown", "message": "库存数量还没填写。"})
    identity = WorkbenchEntityIdentity(row.ref, "material", raw["material_id"], int(raw["revision"]), True)
    entity = {"ref": identity.ref, "business_code": raw["material_id"], "label": raw["name"],
              "status": row.status, "fields": {key: raw[key] for key in ("spec", "unit", "stock_qty", "remark")},
              "relationships": {"batch_requirement_count": int(raw["requirement_count"])}, "issues": issues}
    return MaterialReadRecord(identity, entity, {"identity": asdict(identity), "material": raw})


class WorkbenchMaterialQueryService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.repo = WorkbenchMaterialQueryRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self._snapshot = None

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            previous = self._snapshot
            self._snapshot = {
                "fingerprint": None,
                "rows": None,
                "by_ref": None,
                "checked": {},
                "records": {},
                "indexes": {},
                "scopes": {},
                "orders": {},
                "matches": {},
            }
            try:
                yield self.state_fingerprint()
            finally:
                self._snapshot = previous

    def state_fingerprint(self):
        snapshot = self._snapshot
        if snapshot is not None and snapshot["fingerprint"] is not None:
            return snapshot["fingerprint"]
        revisions = read_source_revisions(self.conn, MATERIAL_SOURCE_KEYS)
        fingerprint = {"revisions": revisions}
        if snapshot is not None:
            snapshot["fingerprint"] = fingerprint
        return fingerprint

    def _ensure_snapshot_rows(self):
        snapshot = self._snapshot
        if snapshot is None:
            raise RuntimeError("物料列表查询必须在 read_snapshot 内执行。")
        if snapshot["rows"] is None:
            rows = self.repo.table_rows()
            snapshot["rows"] = rows
            snapshot["by_ref"] = {row["ref"]: row for row in rows if row["ref"] is not None}
        return snapshot

    def _toolbar_rows(self, query):
        snapshot = self._ensure_snapshot_rows()
        key = tuple(toolbar_scope(query).items())
        scopes = snapshot["scopes"]
        if key not in scopes:
            scopes[key] = material_toolbar_rows(snapshot["rows"], query)
        return scopes[key]

    def _checked(self, raw) -> MaterialRow:
        """Each captured row passes the storage check once per snapshot; every query path shares it."""
        if self._snapshot is None:
            return material_row(raw)
        checked = self._snapshot["checked"]
        code = raw["material_id"]
        if code not in checked:
            checked[code] = material_row(raw)
        return checked[code]

    def _record(self, row: MaterialRow):
        if self._snapshot is None:
            return _project(row)
        records = self._snapshot["records"]
        code = row.raw["material_id"]
        if code not in records:
            records[code] = _project(row)
        return records[code]

    def metrics(self, query: MaterialPageRequest):
        if query.column_filters:
            index = self.table_index(query)
            counts = material_counts([index.rows[code].raw for code in self._matching_keys(query)])
        else:
            counts = self.toolbar_metrics(query)
        return {"scope": "filtered", "counts": counts,
                "basis": {"low_stock": "尚未设置低库存阈值。"},
                "issues": []}

    def toolbar_metrics(self, query: MaterialPageRequest):
        """Count the toolbar scope from its captured raw rows."""
        if query.column_filters:
            raise WorkbenchCommandRejected("invalid_input", "列筛选统计请使用物料查询服务的统一入口。", 400)
        return material_counts(self._toolbar_rows(query))

    def resolve_many(self, refs):
        if not refs:
            return []
        snapshot = self._snapshot
        by_ref = snapshot["by_ref"] if snapshot is not None and snapshot["rows"] is not None else {}
        missing = [ref for ref in refs if ref not in by_ref]
        identities = self.identities.map_by_refs(missing) if missing else {}
        result = []
        for ref in refs:
            if ref in by_ref:
                result.append(self._record(self._checked(by_ref[ref])).identity)
                continue
            identity = identities.get(ref)
            if identity is None or not identity.active or identity.kind != "material":
                raise WorkbenchCommandRejected("entity_not_found", "这条物料已经不在了，请重新选择。请刷新后重新选择。", 404)
            result.append(identity)
        return result

    def _resolve_identity(self, ref):
        identity = self.identities.get(ref)
        if identity is None or not identity.active or identity.kind != "material":
            raise WorkbenchCommandRejected("entity_not_found", "这条物料已经不在了，请重新选择。请刷新后重新选择。", 404)
        return identity

    def detail(self, ref):
        _validate_ref(ref)
        snapshot = self._snapshot
        if snapshot is not None and snapshot["rows"] is not None:
            row = snapshot["by_ref"].get(ref)
            if row is None:
                self._resolve_identity(ref)
        else:
            row = self.repo.get_by_ref(ref)
            if row is None:
                self._resolve_identity(ref)
        if row is None:
            raise WorkbenchCommandRejected("storage_failure", "物料的系统编号和实际记录对不上。请刷新重试；仍不行请联系维护人员。", 500)
        return self._record(self._checked(row))

    def selected_rows(self, refs):
        """Checked rows in the explicit ref order; a deleted selection is rejected, never skipped."""
        if not refs:
            return []
        snapshot = self._snapshot
        if snapshot is not None and snapshot["rows"] is not None:
            captured = snapshot["by_ref"]
            rows = [captured.get(ref) for ref in refs]
        else:
            rows = self.repo.rows_by_refs(refs)
        return [self._selected(row) for row in rows]

    def _selected(self, raw):
        if raw is None:
            raise WorkbenchCommandRejected("entity_not_found", "勾选的物料已经删除了。请刷新后重新勾选。", 404)
        return self._checked(raw)

    def _ordered_rows(self, query: MaterialPageRequest):
        snapshot = self._ensure_snapshot_rows()
        key = (tuple(toolbar_scope(query).items()), query.sort, query.direction)
        orders = snapshot["orders"]
        if key not in orders:
            orders[key] = material_ordered_rows(self._toolbar_rows(query), query)
        return orders[key]

    def _matching_keys(self, query: MaterialPageRequest):
        """One filter-and-order pass per table query; page, count and metrics share it."""
        snapshot = self._ensure_snapshot_rows()
        filters = tuple((column, condition["mode"], tuple(condition["values"]))
                        for column, condition in query.column_filters.items())
        key = (tuple(toolbar_scope(query).items()), query.sort, query.direction, filters)
        matches = snapshot["matches"]
        if key not in matches:
            matches[key] = self.table_index(query).matching_keys(query)
        return matches[key]

    def count(self, query: MaterialPageRequest) -> int:
        if query.column_filters:
            return len(self._matching_keys(query))
        return len(self._toolbar_rows(query))

    def page(self, query: MaterialPageRequest):
        if table_query_required(query):
            index = self.table_index(query)
            matching = self._matching_keys(query)
            start = (query.number - 1) * query.size
            page_keys = matching[start:start + query.size]
            records, total = [self._record(index.rows[code]) for code in page_keys], len(matching)
        else:
            ordered = self._ordered_rows(query)
            start = (query.number - 1) * query.size
            rows, total = ordered[start:start + query.size], len(ordered)
            records = [self._record(self._checked(row)) for row in rows]
        page = {"number": query.number, "size": query.size, "total": total,
                "pages": max(1, (total + query.size - 1) // query.size),
                "sort": [{"field": query.sort, "direction": query.direction}]}
        return records, page

    def table_index(self, query):
        snapshot = self._ensure_snapshot_rows()
        key = tuple(toolbar_scope(query).items())
        cache = snapshot["indexes"]
        if key not in cache:
            cache[key] = material_table_index([self._checked(row) for row in self._toolbar_rows(query)])
        return cache[key]

    def matching_rows(self, query):
        """Checked rows of the whole query scope, in query order."""
        if table_query_required(query):
            index = self.table_index(query)
            return [index.rows[code] for code in self._matching_keys(query)]
        return [self._checked(row) for row in self._ordered_rows(query)]

    def facets(self, query, column, search="", number=1, size=100):
        return self.table_index(query).facets(column, search, number, size)

    def facet_selection(self, query, column, search=""):
        return self.table_index(query).facet_selection(column, search)
