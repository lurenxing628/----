"""Bounded material reads; metadata is never allocated or repaired on query."""

from __future__ import annotations

import json
from typing import Dict, Optional, Sequence

from core.models.enums import MATERIAL_STATUS_VALUES
from core.models.workbench_resource_table_query import SqlOrder

from .base_repo import BaseRepository
from .sql_ranks import order_by

_FROM = """FROM Materials AS m LEFT JOIN WorkbenchEntityRefs AS r
    ON r.kind = 'material' AND r.active = 1 AND r.entity_key = m.material_id"""
_SELECT = """SELECT m.*, r.ref, r.revision,
    (SELECT COUNT(*) FROM BatchMaterials AS b WHERE b.material_id = m.material_id) AS requirement_count
    """ + _FROM
_TABLE_SELECT = "SELECT m.*, r.ref, r.revision " + _FROM


class WorkbenchMaterialQueryRepository(BaseRepository):
    """``order`` 参数都来自表格列定义（``facts.table_columns.sql_order``）。"""

    @staticmethod
    def _scope(query, keys: Optional[Sequence[str]] = None):
        conditions, params = [], []
        if query.status is not None:
            conditions.append("m.status = ?")
            params.append(query.status)
        if query.query:
            conditions.append(
                "(instr(lower(m.material_id), lower(?)) > 0 "
                "OR instr(lower(m.name), lower(?)) > 0 "
                "OR instr(lower(m.spec), lower(?)) > 0)"
            )
            params.extend([query.query] * 3)
        if keys is not None:
            conditions.append("m.material_id IN (SELECT value FROM json_each(?))")
            params.append(json.dumps(keys))
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return where, params

    @staticmethod
    def _order(query, order: SqlOrder):
        return order_by(order, query.direction, alias="m", status="m.status", code="m.material_id")

    def status_counts(self, query, keys: Optional[Sequence[str]] = None) -> Dict[str, int]:
        """工具栏范围（列筛选时再限到命中的 ``keys``）按状态计数，另数没填库存的条数；不读、不核对未显示的行。"""
        where, params = self._scope(query, keys)
        rows = self.fetchall(
            "SELECT m.status AS status_key, COUNT(*) AS cnt, SUM(m.stock_qty IS NULL) AS stock_unknown "
            "FROM Materials AS m" + where + " GROUP BY m.status",
            params,
        )
        counts: Dict[str, int] = dict.fromkeys(MATERIAL_STATUS_VALUES, 0)
        for row in rows:
            counts[row["status_key"]] = row["cnt"]
        counts["total"] = sum(row["cnt"] for row in rows)
        counts["stock_unknown"] = sum(row["stock_unknown"] for row in rows)
        return counts

    def page_rows(self, query, order: SqlOrder):
        where, params = self._scope(query)
        offset = (query.number - 1) * query.size
        return self.fetchall(
            _TABLE_SELECT + where + " ORDER BY " + self._order(query, order) + " LIMIT ? OFFSET ?",
            params + [query.size, offset],
        )

    def toolbar_rows(self, query, order: Optional[SqlOrder] = None):
        """工具栏范围的整行；给了 ``order`` 按它排（导出），否则按编号（建格子索引）。"""
        where, params = self._scope(query)
        by = "m.material_id ASC" if order is None else self._order(query, order)
        return self.fetchall(_TABLE_SELECT + where + " ORDER BY " + by, params)

    def requirement_counts_for(self, codes):
        rows = self.fetchall(
            """SELECT material_id, COUNT(*) AS amount
               FROM BatchMaterials
               WHERE material_id IN (SELECT value FROM json_each(?))
               GROUP BY material_id""",
            (json.dumps(list(codes)),),
        )
        return {row["material_id"]: row["amount"] for row in rows}

    def get_by_ref(self, ref):
        return self.fetchone(_SELECT + " WHERE r.ref = ?", (ref,))

    def rows_by_refs(self, refs):
        rows = self.fetchall(
            _TABLE_SELECT + " WHERE r.ref IN (SELECT value FROM json_each(?))",
            (json.dumps(list(refs)),),
        )
        by_ref = {row["ref"]: row for row in rows}
        return [by_ref.get(ref) for ref in refs]

    def get_raw(self, business_code):
        return self.fetchone(_TABLE_SELECT + " WHERE m.material_id = ?", (business_code,))
