"""Bounded material reads; metadata is never allocated or repaired on query."""

from __future__ import annotations

from core.models.workbench_command import WorkbenchCommandRejected

from .base_repo import BaseRepository

_SELECT = """SELECT m.material_id, m.name, m.spec, m.unit, m.stock_qty, m.status,
    m.remark, m.created_at, r.ref, r.revision,
    (SELECT COUNT(*) FROM BatchMaterials AS b WHERE b.material_id = m.material_id) AS requirement_count
    FROM Materials AS m LEFT JOIN WorkbenchEntityRefs AS r
    ON r.kind = 'material' AND r.active = 1 AND r.entity_key = m.material_id"""
_SORTS = {"business_code": "m.material_id", "label": "m.name", "spec": "m.spec", "stock_qty": "m.stock_qty", "status": "m.status"}


class WorkbenchMaterialQueryRepository(BaseRepository):
    def table_rows(self, query="", status=None):
        where, params = self._where(query, status)
        return self.fetchall(_SELECT + where + " ORDER BY m.material_id", params)

    def get_by_ref(self, ref):
        return self.fetchone(_SELECT + " WHERE r.ref = ?", (ref,))

    def get_raw(self, business_code):
        return self.fetchone(_SELECT + " WHERE m.material_id = ?", (business_code,))

    @staticmethod
    def _where(query, status):
        conditions, params = [], []
        if query:
            conditions.append("(instr(lower(m.material_id), lower(?)) > 0 OR instr(lower(m.name), lower(?)) > 0 OR instr(lower(coalesce(m.spec, '')), lower(?)) > 0)")
            params.extend([query] * 3)
        if status is not None:
            conditions.append("m.status = ?")
            params.append(status)
        return (" WHERE " + " AND ".join(conditions) if conditions else ""), params

    def page(self, *, query, status, number, size, sort, direction):
        where, params = self._where(query, status)
        total = int(self.fetchvalue("SELECT COUNT(*) FROM Materials AS m" + where, params, default=0))
        if sort not in _SORTS or direction not in ("asc", "desc"):
            raise ValueError("Invalid material sort")
        order = _SORTS[sort] + " " + direction.upper()
        if sort != "business_code":
            order += ", m.material_id ASC"
        rows = self.fetchall(_SELECT + where + " ORDER BY " + order + " LIMIT ? OFFSET ?",
                             params + [size, (number - 1) * size])
        return rows, total

    def snapshot_state(self):
        # Retired refs are retained: revisions/count increase on every material mutation.
        refs = self.fetchone("""SELECT COUNT(*) AS instances, coalesce(SUM(revision), 0) AS revisions
            FROM WorkbenchEntityRefs WHERE kind = 'material'""")
        requirements = self.fetchall("""SELECT material_id, COUNT(*) AS amount FROM BatchMaterials
            GROUP BY material_id ORDER BY material_id""")
        return {"refs": refs, "requirements": requirements}

    def metrics(self, query):
        if query.column_filters:
            raise WorkbenchCommandRejected("invalid_input", "列筛选统计请使用物料查询服务的统一入口。", 400)
        where, params = self._where(query.query, query.status)
        return self.fetchone("""SELECT COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN m.status='active' THEN 1 ELSE 0 END),0) AS active,
            COALESCE(SUM(CASE WHEN m.status='inactive' THEN 1 ELSE 0 END),0) AS inactive,
            COALESCE(SUM(CASE WHEN m.status IS NULL OR m.status NOT IN ('active','inactive') THEN 1 ELSE 0 END),0) AS unknown,
            COALESCE(SUM(CASE WHEN m.stock_qty IS NULL THEN 1 ELSE 0 END),0) AS stock_unknown
            FROM Materials AS m""" + where, params)
