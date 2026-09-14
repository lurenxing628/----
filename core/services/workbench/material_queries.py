"""Read actual material facts without defaults, metadata repair, or demo fallback."""

from __future__ import annotations

import math
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_material_query import MaterialPageRequest
from core.models.workbench_resource_table_query import table_query_required, toolbar_scope
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_material_query_repo import WorkbenchMaterialQueryRepository

from .material_table_facts import material_table_index


@dataclass(frozen=True)
class MaterialReadRecord:
    identity: WorkbenchEntityIdentity
    entity: Dict[str, Any]


def _project(row):
    if type(row.get("ref")) is not str or re.fullmatch(r"[0-9a-f]{48}", row["ref"]) is None or row.get("revision") is None:
        raise WorkbenchCommandRejected("storage_failure", "物料缺少系统编号，系统不会自动修补数据。请刷新重试；仍不行请联系维护人员。", 500)
    stock = row["stock_qty"]
    if stock is not None and (type(stock) not in (int, float) or not math.isfinite(stock) or stock < 0):
        cause = ValueError("Materials material_id={!r} stock_qty={!r}".format(row["material_id"], stock))
        raise WorkbenchCommandRejected(
            "storage_failure", "物料「{}」的库存数量不是 0 或大于 0 的有效数字，系统不会当成 0；请核对原资料。".format(row["material_id"]),
            500) from cause
    issues = [{"code": "stock_level_unknown", "scope": "collection", "message": "还没有设置低库存的判断标准。"}]
    if stock is None:
        issues.append({"code": "stock_unknown", "message": "库存数量还没填写。"})
    if row["status"] not in ("active", "inactive"):
        issues.append({"code": "status_unknown", "message": "这个物料的状态不在已知的几种里，系统保留原值。"})
    identity = WorkbenchEntityIdentity(row["ref"], "material", row["material_id"], int(row["revision"]), True)
    entity = {"ref": identity.ref, "business_code": row["material_id"], "label": row["name"],
              "status": row["status"], "fields": {key: row[key] for key in ("spec", "unit", "stock_qty", "remark")},
              "relationships": {"batch_requirement_count": int(row["requirement_count"])}, "issues": issues}
    return MaterialReadRecord(identity, entity)


class WorkbenchMaterialQueryService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.repo = WorkbenchMaterialQueryRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self._table_indexes = None

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            previous = self._table_indexes
            self._table_indexes = {}
            try:
                yield self.state_fingerprint()
            finally:
                self._table_indexes = previous

    def state_fingerprint(self):
        return input_fingerprint({"state": self.repo.snapshot_state(), "rows": self.repo.table_rows()})

    def metrics(self, query: MaterialPageRequest):
        if query.column_filters:
            index = self.table_index(query)
            rows = [index.rows[code] for code in index.matching_keys(query)]
            counts = {"total": len(rows), "active": sum(row["status"] == "active" for row in rows),
                      "inactive": sum(row["status"] == "inactive" for row in rows),
                      "unknown": sum(row["status"] not in ("active", "inactive") for row in rows),
                      "stock_unknown": sum(row["stock_qty"] is None for row in rows)}
        else:
            counts = self.repo.metrics(query)
        return {"scope": "filtered", "counts": counts,
                "basis": {"low_stock": "还没有设置低库存的判断标准，系统不会按库存为 0 或示例数量去推断。"},
                "issues": []}

    def resolve(self, ref):
        if not isinstance(ref, str) or len(ref) != 48 or any(char not in "0123456789abcdef" for char in ref):
            raise WorkbenchCommandRejected("entity_not_found", "物料记录不存在，请返回列表重新选择。", 404)
        identity = self.identities.get(ref)
        if identity is None or not identity.active or identity.kind != "material":
            raise WorkbenchCommandRejected("entity_not_found", "这条物料已经不在了，系统不会换成编号相同的新记录。请刷新后重新选择。", 404)
        return identity

    def detail(self, ref):
        identity = self.resolve(ref)
        row = self.repo.get_by_ref(identity.ref)
        if row is None:
            raise WorkbenchCommandRejected("storage_failure", "物料的系统编号和实际记录对不上。请刷新重试；仍不行请联系维护人员。", 500)
        return _project(row)

    def page(self, query: MaterialPageRequest):
        if table_query_required(query):
            rows, total = self.table_index(query).page(query)
        else:
            rows, total = self.repo.page(query=query.query, status=query.status, number=query.number,
                                         size=query.size, sort=query.sort, direction=query.direction)
        records = [_project(row) for row in rows]
        page = {"number": query.number, "size": query.size, "total": total,
                "pages": max(1, (total + query.size - 1) // query.size),
                "sort": [{"field": query.sort, "direction": query.direction}]}
        return records, page

    def table_index(self, query):
        key = input_fingerprint(toolbar_scope(query))
        cache = self._table_indexes if self._table_indexes is not None else {}
        if key not in cache:
            cache[key] = material_table_index(self.repo.table_rows(query.query, query.status), _project)
        return cache[key]

    def matching_keys(self, query):
        return self.table_index(query).matching_keys(query)

    def matching_rows(self, query):
        index = self.table_index(query)
        return [{"business_code": code, "ref": index.rows[code]["ref"], "revision": index.rows[code]["revision"]}
                for code in index.matching_keys(query)]

    def facets(self, query, column, search="", number=1, size=100):
        return self.table_index(query).facets(query, column, search, number, size)

    def facet_selection(self, query, column, search="", size=100):
        return self.table_index(query).facet_selection(query, column, search, size)
