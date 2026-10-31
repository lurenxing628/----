"""Bounded material reads; metadata is never allocated or repaired on query."""

from __future__ import annotations

from .base_repo import BaseRepository

_FROM = """FROM Materials AS m LEFT JOIN WorkbenchEntityRefs AS r
    ON r.kind = 'material' AND r.active = 1 AND r.entity_key = m.material_id"""
_SELECT = """SELECT m.*, r.ref, r.revision,
    (SELECT COUNT(*) FROM BatchMaterials AS b WHERE b.material_id = m.material_id) AS requirement_count
    """ + _FROM
_TABLE_SELECT = "SELECT m.*, r.ref, r.revision " + _FROM


class WorkbenchMaterialQueryRepository(BaseRepository):
    def table_rows(self):
        rows = self.fetchall(_TABLE_SELECT + " ORDER BY m.material_id")
        counts = {row["material_id"]: row["amount"] for row in self.requirement_counts()}
        for row in rows:
            row["requirement_count"] = counts.get(row["material_id"], 0)
        return rows

    def get_by_ref(self, ref):
        return self.fetchone(_SELECT + " WHERE r.ref = ?", (ref,))

    def rows_by_refs(self, refs):
        by_ref = {}
        for start in range(0, len(refs), 400):
            chunk = refs[start:start + 400]
            marks = ",".join("?" for _ in chunk)
            for row in self.fetchall(_TABLE_SELECT + f" WHERE r.ref IN ({marks})", chunk):
                by_ref[row["ref"]] = row
        return [by_ref.get(ref) for ref in refs]

    def get_raw(self, business_code):
        return self.fetchone(_TABLE_SELECT + " WHERE m.material_id = ?", (business_code,))

    def requirement_counts(self):
        return self.fetchall("""SELECT material_id, COUNT(*) AS amount FROM BatchMaterials
            GROUP BY material_id ORDER BY material_id""")
