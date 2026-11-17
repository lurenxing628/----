"""Batch-read original templates and paginated part lists, never allocating identity on GET."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from core.models.workbench_process_query import PROCESS_STAGES

from .base_repo import BaseRepository

_PART_SCOPE = """WITH target_part AS (
    SELECT entity_key AS part_no FROM WorkbenchEntityRefs
    WHERE ref=? AND kind='part' AND active=1
), related_groups AS (
    SELECT group_id FROM ExternalGroups WHERE part_no IN (SELECT part_no FROM target_part)
    UNION
    SELECT ext_group_id FROM PartOperations
    WHERE part_no IN (SELECT part_no FROM target_part) AND ext_group_id IS NOT NULL
) """

_SCOPED_SUPPLIERS = _PART_SCOPE + """, scoped_suppliers AS (
    SELECT supplier_id FROM PartOperations
    WHERE supplier_id IS NOT NULL
      AND (part_no IN (SELECT part_no FROM target_part)
           OR ext_group_id IN (SELECT group_id FROM related_groups))
    UNION
    SELECT supplier_id FROM ExternalGroups
    WHERE supplier_id IS NOT NULL
      AND group_id IN (SELECT group_id FROM related_groups)
) """

_STAGE_IDX_SQL = """CASE
    WHEN p.hours_confirmed_at IS NOT NULL THEN 3
    WHEN p.source_confirmed_at IS NOT NULL THEN 2
    WHEN p.route_confirmed_at IS NOT NULL
         OR (p.workflow_origin = 'legacy' AND EXISTS (
             SELECT 1 FROM PartOperations o
             WHERE o.part_no = p.part_no AND o.status = 'active'
         )) THEN 1
    ELSE 0
END"""

_SORT_SQL_MAP = {
    "business_code": "aps_text_sort_key(f.part_no)",
    "operation_count": "f.op_count",
    "stage": "f.stage_idx",
}


def _part_order_clause(field: str, direction: str) -> str:
    if field == "label":
        return f"(f.part_name IS NOT NULL) {direction}, aps_text_sort_key(f.part_name) {direction}"
    return f"{_SORT_SQL_MAP[field]} {direction}"


class WorkbenchProcessQueryRepository(BaseRepository):
    def __init__(self, conn, logger=None, *, part_ref=None):
        super().__init__(conn, logger=logger)
        self.part_ref = part_ref

    def page_parts(self, query) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
        """SQLite B-Tree / index-backed pagination for process part list."""
        clauses: List[str] = []
        params: List[Any] = []
        needle = query.query.casefold()
        if needle:
            clauses.append(
                "(INSTR(aps_casefold(CAST(p.part_no AS TEXT)), ?) > 0 "
                "OR INSTR(aps_casefold(CAST(p.part_name AS TEXT)), ?) > 0 "
                "OR (p.route_raw IS NOT NULL AND INSTR(aps_casefold(CAST(p.route_raw AS TEXT)), ?) > 0))"
            )
            params.extend((needle, needle, needle))
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        stage_filter = ""
        filter_params = list(params)
        if query.stage is not None:
            stage_filter = " WHERE stage_idx = ?"
            filter_params.append(PROCESS_STAGES.index(query.stage))
        ordering = query.ordering()
        need_op_sort = any(item["field"] == "operation_count" for item in ordering)
        op_sort_col = (
            ", (SELECT COUNT(*) FROM PartOperations o WHERE o.part_no = p.part_no AND o.status = 'active') AS op_count"
            if need_op_sort
            else ""
        )
        cte = f"""WITH matched AS (
            SELECT p.*, r.ref, r.revision, {_STAGE_IDX_SQL} AS stage_idx{op_sort_col}
            FROM Parts p
            LEFT JOIN WorkbenchEntityRefs r
              ON r.kind='part' AND r.entity_key=p.part_no AND r.active=1
            {where_sql}
        ), filtered AS (
            SELECT * FROM matched{stage_filter}
        )"""
        counts_row = self.fetchall(
            cte + """
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(stage_idx = 0), 0) AS route,
                   COALESCE(SUM(stage_idx = 1), 0) AS source,
                   COALESCE(SUM(stage_idx = 2), 0) AS hours,
                   COALESCE(SUM(stage_idx = 3), 0) AS ready
            FROM filtered""",
            tuple(filter_params),
        )[0]
        total = counts_row["total"]
        counts: Dict[str, int] = {
            stage: counts_row[stage] for stage in PROCESS_STAGES
        }
        counts["total"] = total
        offset = (query.number - 1) * query.size
        if total == 0 or offset >= total:
            return counts, []
        order_terms = [
            _part_order_clause(item["field"], "DESC" if item["direction"] == "desc" else "ASC")
            for item in ordering
        ]
        if not any(item["field"] == "business_code" for item in ordering):
            order_terms.append("aps_text_sort_key(f.part_no) ASC")
        order_terms.append("f.ref ASC")
        page_rows = self.fetchall(
            cte + f" SELECT * FROM filtered f ORDER BY {', '.join(order_terms)} LIMIT ? OFFSET ?",
            (*filter_params, query.size, offset),
        )
        self._attach_page_counts(page_rows)
        return counts, page_rows

    def _attach_page_counts(self, page_rows: List[Dict[str, Any]]) -> None:
        part_nos_json = json.dumps([row["part_no"] for row in page_rows])
        op_counts = {
            row["part_no"]: row
            for row in self.fetchall(
                """SELECT part_no,
                          COUNT(*) AS active_count,
                          COALESCE(SUM(source = 'internal'), 0) AS internal_count,
                          COALESCE(SUM(source = 'external'), 0) AS external_count
                   FROM PartOperations
                   WHERE status = 'active' AND part_no IN (SELECT value FROM json_each(?))
                   GROUP BY part_no""",
                (part_nos_json,),
            )
        }
        batch_counts = {
            row["part_no"]: row["batch_count"]
            for row in self.fetchall(
                """SELECT part_no, COUNT(*) AS batch_count
                   FROM Batches
                   WHERE part_no IN (SELECT value FROM json_each(?))
                   GROUP BY part_no""",
                (part_nos_json,),
            )
        }
        for row in page_rows:
            code = row["part_no"]
            op_stat = op_counts.get(code)
            row["active_count"] = op_stat["active_count"] if op_stat is not None else 0
            row["internal_count"] = op_stat["internal_count"] if op_stat is not None else 0
            row["external_count"] = op_stat["external_count"] if op_stat is not None else 0
            row["batch_count"] = batch_counts.get(code, 0)

    def part_table_summaries(self) -> List[Dict[str, Any]]:
        """Lightweight aggregated part rows for column_filters, facets and filtered exports."""
        return self.fetchall(
            """SELECT p.*, r.ref, r.revision,
                      COALESCE(b.amount, 0) AS batch_count,
                      COALESCE(op.active_count, 0) AS active_count,
                      COALESCE(op.internal_count, 0) AS internal_count,
                      COALESCE(op.external_count, 0) AS external_count
               FROM Parts p
               LEFT JOIN WorkbenchEntityRefs r
                 ON r.kind='part' AND r.entity_key=p.part_no AND r.active=1
               LEFT JOIN (SELECT part_no, COUNT(*) AS amount FROM Batches GROUP BY part_no) b
                 ON b.part_no=p.part_no
               LEFT JOIN (
                   SELECT part_no,
                          COUNT(*) AS active_count,
                          COALESCE(SUM(source = 'internal'), 0) AS internal_count,
                          COALESCE(SUM(source = 'external'), 0) AS external_count
                   FROM PartOperations
                   WHERE status = 'active'
                   GROUP BY part_no
               ) op ON op.part_no=p.part_no
               ORDER BY p.part_no"""
        )

    def parts(self):
        if self.part_ref is not None:
            return self.fetchall("""SELECT p.*, r.ref, r.revision,
                (SELECT COUNT(*) FROM Batches b WHERE b.part_no=p.part_no) AS batch_count
                FROM Parts p LEFT JOIN WorkbenchEntityRefs r
                  ON r.kind='part' AND r.entity_key=p.part_no AND r.active=1
                WHERE r.ref=? ORDER BY p.part_no""", (self.part_ref,))
        return self.fetchall("""SELECT p.*, r.ref, r.revision, COALESCE(b.amount,0) AS batch_count
            FROM Parts p LEFT JOIN WorkbenchEntityRefs r
              ON r.kind='part' AND r.entity_key=p.part_no AND r.active=1
            LEFT JOIN (SELECT part_no,COUNT(*) AS amount FROM Batches GROUP BY part_no) b
              ON b.part_no=p.part_no ORDER BY p.part_no""")

    def operations(self):
        scoped = self.part_ref is not None
        identity_fields = ", r.alternate_key AS ref_alternate_key" if scoped else ""
        scoped_join = (
            "JOIN (SELECT id FROM PartOperations WHERE part_no IN (SELECT part_no FROM target_part) "
            "UNION SELECT id FROM PartOperations WHERE ext_group_id IN (SELECT group_id FROM related_groups)) "
            "scoped_ops ON scoped_ops.id=o.id "
            if scoped else ""
        )
        return self.fetchall((_PART_SCOPE if scoped else "") + "SELECT o.*, r.ref, r.revision" + identity_fields + """,
            ot.op_type_id AS op_type_exists, ot.name AS op_type_label, ot.category AS op_type_category,
            tr.ref AS op_type_ref, s.supplier_id AS supplier_exists, s.name AS supplier_label,
            sr.ref AS supplier_ref, eg.group_id AS group_exists, eg.part_no AS group_part_no,
            gr.ref AS external_group_ref
            FROM PartOperations o """ + scoped_join + """LEFT JOIN WorkbenchEntityRefs r
              ON r.kind='template_operation' AND r.entity_key=CAST(o.id AS TEXT) AND r.active=1
            LEFT JOIN OpTypes ot ON ot.op_type_id=o.op_type_id
            LEFT JOIN WorkbenchEntityRefs tr ON tr.kind='op_type' AND tr.entity_key=ot.op_type_id AND tr.active=1
            LEFT JOIN Suppliers s ON s.supplier_id=o.supplier_id
            LEFT JOIN WorkbenchEntityRefs sr ON sr.kind='supplier' AND sr.entity_key=s.supplier_id AND sr.active=1
            LEFT JOIN ExternalGroups eg ON eg.group_id=o.ext_group_id
            LEFT JOIN WorkbenchEntityRefs gr ON gr.kind='template_external_group' AND gr.entity_key=eg.group_id AND gr.active=1
            ORDER BY o.part_no,o.seq,o.id""", (self.part_ref,) if scoped else ())

    def groups(self):
        scoped = self.part_ref is not None
        identity_fields = ", r.alternate_key AS ref_alternate_key" if scoped else ""
        where = "WHERE eg.group_id IN (SELECT group_id FROM related_groups) " if scoped else ""
        return self.fetchall((_PART_SCOPE if scoped else "") + "SELECT eg.*, r.ref, r.revision" + identity_fields + """, s.supplier_id AS supplier_exists,
            s.name AS supplier_label, sr.ref AS supplier_ref FROM ExternalGroups eg
            LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_external_group' AND r.entity_key=eg.group_id AND r.active=1
            LEFT JOIN Suppliers s ON s.supplier_id=eg.supplier_id
            LEFT JOIN WorkbenchEntityRefs sr ON sr.kind='supplier' AND sr.entity_key=s.supplier_id AND sr.active=1
            """ + where + "ORDER BY eg.part_no,eg.start_seq,eg.group_id", (self.part_ref,) if scoped else ())

    def catalog_references(self):
        catalogs = ("OpTypes", "Suppliers", "WorkbenchSupplierProfiles", "WorkbenchSupplierOpTypes", "WorkbenchOpTypePolicies")
        return {table: self.fetchall('SELECT * FROM "' + table + '" ORDER BY rowid') for table in catalogs}

    def supplier_references(self):
        return {
            table: self.fetchall(
                _SCOPED_SUPPLIERS
                + f'SELECT * FROM "{table}" WHERE supplier_id IN (SELECT supplier_id FROM scoped_suppliers) ORDER BY rowid',
                (self.part_ref,),
            )
            for table in ("Suppliers", "WorkbenchSupplierProfiles", "WorkbenchSupplierOpTypes")
        }

    def part_identities(self):
        return self.fetchall(
            """SELECT ref,kind,entity_key,alternate_key,revision,active
                FROM WorkbenchEntityRefs WHERE ref=? ORDER BY ref""",
            (self.part_ref,),
        )

    def shared_identities(self):
        return self.fetchall(
            """SELECT ref,kind,entity_key,alternate_key,revision,active
                FROM WorkbenchEntityRefs WHERE kind IN ('op_type','supplier') ORDER BY ref"""
        )

    def identities(self):
        return self.fetchall("""SELECT ref,kind,entity_key,alternate_key,revision,active FROM WorkbenchEntityRefs
            WHERE kind IN ('part','template_operation','template_external_group','op_type','supplier') ORDER BY ref""")
