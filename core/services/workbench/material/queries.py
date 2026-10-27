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
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_material_query_repo import WorkbenchMaterialQueryRepository

from .table_facts import (
    damaged_material_status,
    material_counts,
    material_ordered_rows,
    material_ref,
    material_status,
    material_stock,
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


def _project(row):
    ref = material_ref(row)
    stock = material_stock(row)
    status = material_status(row)
    issues = [{"code": "stock_level_unknown", "scope": "collection", "message": "还没有设置低库存的判断标准。"}]
    if stock is None:
        issues.append({"code": "stock_unknown", "message": "库存数量还没填写。"})
    identity = WorkbenchEntityIdentity(ref, "material", row["material_id"], int(row["revision"]), True)
    entity = {"ref": identity.ref, "business_code": row["material_id"], "label": row["name"],
              "status": status, "fields": {key: row[key] for key in ("spec", "unit", "stock_qty", "remark")},
              "relationships": {"batch_requirement_count": int(row["requirement_count"])}, "issues": issues}
    return MaterialReadRecord(identity, entity, {"identity": asdict(identity), "material": row})


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
                "records": {},
                "indexes": {},
                "scopes": {},
                "orders": {},
            }
            try:
                yield self.state_fingerprint()
            finally:
                self._snapshot = previous

    def state_fingerprint(self):
        snapshot = self._snapshot
        if snapshot is not None and snapshot["fingerprint"] is not None:
            return snapshot["fingerprint"]
        state = self.repo.snapshot_state()
        fingerprint = {"state": state, "rows": self.repo.table_rows(requirements=state["requirements"])}
        if snapshot is not None:
            snapshot["fingerprint"] = fingerprint
            snapshot["by_ref"] = {row["ref"]: row for row in fingerprint["rows"] if row.get("ref") is not None}
        return fingerprint

    def _toolbar_rows(self, query):
        if self._snapshot is not None and self._snapshot["fingerprint"] is not None:
            key = tuple(toolbar_scope(query).items())
            scopes = self._snapshot["scopes"]
            if key not in scopes:
                scopes[key] = material_toolbar_rows(self._snapshot["fingerprint"]["rows"], query)
            return scopes[key]
        return self.repo.table_rows(query.query, query.status)

    def _record(self, row):
        if self._snapshot is None:
            return _project(row)
        records = self._snapshot["records"]
        code = row["material_id"]
        if code not in records:
            records[code] = _project(row)
        return records[code]

    def metrics(self, query: MaterialPageRequest):
        if query.column_filters:
            index = self.table_index(query)
            rows = [index.rows[code] for code in index.matching_keys(query)]
            counts = material_counts(rows)
        else:
            counts = self.toolbar_metrics(query)
        return {"scope": "filtered", "counts": counts,
                "basis": {"low_stock": "尚未设置低库存阈值。"},
                "issues": []}

    def toolbar_metrics(self, query: MaterialPageRequest):
        """Count the toolbar scope from its captured raw rows, or SQL without a full capture."""
        if query.column_filters:
            raise WorkbenchCommandRejected("invalid_input", "列筛选统计请使用物料查询服务的统一入口。", 400)
        if self._snapshot is not None and self._snapshot["fingerprint"] is not None:
            return material_counts(self._toolbar_rows(query))
        counts = self.repo.metrics(query.query, query.status)
        damaged = counts.pop("damaged_code")
        if damaged is not None:
            raise damaged_material_status(damaged)
        return counts

    def resolve(self, ref):
        _validate_ref(ref)
        if self._snapshot is not None and self._snapshot["fingerprint"] is not None:
            row = self._snapshot["by_ref"].get(ref)
            if row is not None:
                return self._record(row).identity
        return self._resolve_identity(ref)

    def _resolve_identity(self, ref):
        identity = self.identities.get(ref)
        if identity is None or not identity.active or identity.kind != "material":
            raise WorkbenchCommandRejected("entity_not_found", "这条物料已经不在了，请重新选择。请刷新后重新选择。", 404)
        return identity

    def detail(self, ref):
        _validate_ref(ref)
        if self._snapshot is not None and self._snapshot["fingerprint"] is not None:
            row = self._snapshot["by_ref"].get(ref)
            if row is None:
                self._resolve_identity(ref)
        else:
            identity = self._resolve_identity(ref)
            row = self.repo.get_by_ref(identity.ref)
        if row is None:
            raise WorkbenchCommandRejected("storage_failure", "物料的系统编号和实际记录对不上。请刷新重试；仍不行请联系维护人员。", 500)
        return self._record(row)

    def _ordered_rows(self, query: MaterialPageRequest):
        if self._snapshot is not None and self._snapshot["fingerprint"] is not None:
            key = (tuple(toolbar_scope(query).items()), query.sort, query.direction)
            orders = self._snapshot["orders"]
            if key not in orders:
                orders[key] = material_ordered_rows(self._toolbar_rows(query), query)
            return orders[key]
        return material_ordered_rows(self._toolbar_rows(query), query)

    def count(self, query: MaterialPageRequest) -> int:
        if query.column_filters:
            return len(self.table_index(query).matching_keys(query))
        return len(self._toolbar_rows(query))

    def page(self, query: MaterialPageRequest):
        if table_query_required(query):
            index = self.table_index(query)
            matching = index.matching_keys(query)
            start = (query.number - 1) * query.size
            page_keys = matching[start:start + query.size]
            records, total = [self._record(index.rows[code]) for code in page_keys], len(matching)
        else:
            if self._snapshot is not None and self._snapshot["fingerprint"] is not None:
                ordered = self._ordered_rows(query)
                start = (query.number - 1) * query.size
                rows, total = ordered[start:start + query.size], len(ordered)
            else:
                rows, total = self.repo.page(query=query.query, status=query.status, number=query.number,
                                             size=query.size, sort=query.sort, direction=query.direction)
            records = [self._record(row) for row in rows]
        page = {"number": query.number, "size": query.size, "total": total,
                "pages": max(1, (total + query.size - 1) // query.size),
                "sort": [{"field": query.sort, "direction": query.direction}]}
        return records, page

    def table_index(self, query):
        key = tuple(toolbar_scope(query).items())
        cache = self._snapshot["indexes"] if self._snapshot is not None else {}
        if key not in cache:
            cache[key] = material_table_index(self._toolbar_rows(query))
        return cache[key]

    def matching_rows(self, query):
        if table_query_required(query):
            index = self.table_index(query)
            return [index.rows[code] for code in index.matching_keys(query)]
        return self._ordered_rows(query)

    def facets(self, query, column, search="", number=1, size=100):
        return self.table_index(query).facets(query, column, search, number, size)

    def facet_selection(self, query, column, search="", size=100):
        return self.table_index(query).facet_selection(query, column, search, size)
