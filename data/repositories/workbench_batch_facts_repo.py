"""批次事实读仓储：BatchFacts 的整表快照与单条批次原始行。

整表读取只展开本模块的白名单常量，不接受调用方传表名；不做任何裁决。
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from core.models.workbench_batch import MAX_INTEGER
from core.shared.stored_dates import stored_day

from .base_repo import BaseRepository
from .sqlite_rows import raw_table_select_sql

QUERY_PARAM_CHUNK = 400
BATCH_FACT_TABLES = ("Batches", "BatchOperations", "Parts", "PartOperations", "BatchMaterials", "BatchMaterialReviews", "BatchMaterialStages", "BatchMaterialArrivals", "BatchQuantitySplits", "Materials",
                     "Machines", "MachineOpTypes", "Operators", "OperatorMachine", "OperatorSkill", "OpTypes", "Suppliers", "WorkbenchSupplierOpTypes",
                     "WorkbenchOperatorProfiles", "WorkbenchEntityRefs",
                     "WorkbenchOutsourcingReceipts", "BatchExternalContexts")
STATIC_RESOURCE_TABLES = (
    "Machines",
    "MachineOpTypes",
    "Operators",
    "OperatorMachine",
    "OperatorSkill",
    "OpTypes",
    "Suppliers",
    "WorkbenchSupplierOpTypes",
    "WorkbenchOperatorProfiles",
)
CHOICE_CATALOG_TABLES = ("Parts", "Machines", "Operators", "Suppliers", "OperatorMachine")


def _pushdown_predicates(query_filter: Mapping[str, Any]) -> Optional[List[Tuple[str, str, Sequence[Any]]]]:
    predicates: List[Tuple[str, str, Sequence[Any]]] = []
    batch_ids = query_filter["batch_ids"]
    if batch_ids is not None:
        unique_ids = sorted(set(batch_ids))
        if not unique_ids:
            return None
        predicates.append(("in", "typeof(b.batch_id)='text' AND b.batch_id IN ({marks})", unique_ids))
    column_filters = query_filter["column_filters"]
    if any(not items for items in column_filters.values()):
        return None
    for key, col in (("business_code", "batch_id"), ("part_no", "part_no"), ("priority", "priority")):
        if key in column_filters and None not in column_filters[key]:
            texts = sorted({v for v in column_filters[key] if type(v) is str})
            if not texts:
                return None
            predicates.append(("in", f"typeof(b.{col})='text' AND b.{col} IN ({{marks}})", texts))
    if "quantity" in column_filters and None not in column_filters["quantity"]:
        integers = sorted({
            int(v)
            for v in column_filters["quantity"]
            if (type(v) is int or (type(v) is float and v.is_integer())) and 0 <= v <= MAX_INTEGER
        })
        if not integers:
            return None
        predicates.append((
            "in",
            "typeof(b.quantity) IN ('integer','real') AND b.quantity>=0 "
            "AND b.quantity==CAST(b.quantity AS INTEGER) AND CAST(b.quantity AS INTEGER) IN ({marks})",
            integers,
        ))
    if "due_date" in column_filters and None not in column_filters["due_date"]:
        allowed_dates = column_filters["due_date"]
        if all(type(v) is str and stored_day(v) is not None for v in allowed_dates):
            predicates.append(("in", "typeof(b.due_date)='text' AND b.due_date IN ({marks})", sorted(set(allowed_dates))))
    if query_filter["query"]:
        needle = query_filter["query"].casefold()
        predicates.append((
            "fixed",
            '(INSTR(aps_casefold(b.batch_id), ?)>0 OR INSTR(aps_casefold(b.part_no), ?)>0 '
            'OR EXISTS (SELECT 1 FROM "Parts" p WHERE p.part_no=b.part_no AND INSTR(aps_casefold(p.part_name), ?)>0))',
            (needle, needle, needle),
        ))
    return predicates


class WorkbenchBatchFactsRepository(BaseRepository):
    def plan_reference_counts(self, op_ids: Optional[Sequence[int]] = None) -> Dict[int, int]:
        """Only live operation references affect batch maintenance, regardless of plan contents."""
        if op_ids is not None:
            ids = sorted(set(op_ids))
            counts: Dict[int, int] = {}
            for start in range(0, len(ids), QUERY_PARAM_CHUNK):
                chunk = ids[start : start + QUERY_PARAM_CHUNK]
                placeholders = ",".join("?" for _ in chunk)
                rows = self.fetchall(
                    f"""SELECT p.op_id, COUNT(*) AS reference_count
                    FROM Schedule p
                    WHERE p.op_id IN ({placeholders})
                    GROUP BY p.op_id ORDER BY p.op_id""",
                    tuple(chunk),
                )
                counts.update({row["op_id"]: row["reference_count"] for row in rows})
            return counts
        rows = self.fetchall("""SELECT p.op_id, COUNT(*) AS reference_count
            FROM Schedule p JOIN BatchOperations o ON o.id=p.op_id
            GROUP BY p.op_id ORDER BY p.op_id""")
        return {row["op_id"]: row["reference_count"] for row in rows}

    def whole_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        """按 BATCH_FACT_TABLES 顺序整表读取（rowid 序），返回 {表名: [行 dict]}。"""
        return {table: self.fetchall(raw_table_select_sql(table) + " ORDER BY rowid") for table in BATCH_FACT_TABLES}

    def _fetch_by_rowids(self, table: str, ordered_rowids: Sequence[int]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        base_sql = raw_table_select_sql(table)
        for start in range(0, len(ordered_rowids), QUERY_PARAM_CHUNK):
            chunk = ordered_rowids[start : start + QUERY_PARAM_CHUNK]
            marks = ",".join("?" for _ in chunk)
            rows.extend(self.fetchall(f"{base_sql} WHERE rowid IN ({marks}) ORDER BY rowid", tuple(chunk)))
        return rows

    def _fetch_union_by_rowid(
        self,
        table: str,
        fixed_clauses: Sequence[str],
        in_clauses: Sequence[Tuple[str, Sequence[Any]]],
    ) -> List[Dict[str, Any]]:
        active_in = [(tmpl, vals) for tmpl, vals in in_clauses if vals]
        if not fixed_clauses and not active_in:
            return []
        total_params = sum(len(vals) for _tmpl, vals in active_in)
        if total_params <= QUERY_PARAM_CHUNK:
            parts = list(fixed_clauses) + [
                tmpl.format(marks=",".join("?" for _ in vals)) for tmpl, vals in active_in
            ]
            params = tuple(v for _tmpl, vals in active_in for v in vals)
            where_sql = " OR ".join(f"({part})" for part in parts)
            return self.fetchall(f"{raw_table_select_sql(table)} WHERE {where_sql} ORDER BY rowid", params)
        escaped = table.replace('"', '""')
        rowids: Set[int] = set()
        for clause in fixed_clauses:
            rowids.update(row["rowid"] for row in self.fetchall(f'SELECT rowid AS rowid FROM "{escaped}" WHERE ({clause})'))
        for tmpl, vals in active_in:
            for start in range(0, len(vals), QUERY_PARAM_CHUNK):
                chunk = vals[start : start + QUERY_PARAM_CHUNK]
                marks = ",".join("?" for _ in chunk)
                sql = f'SELECT rowid AS rowid FROM "{escaped}" WHERE (' + tmpl.format(marks=marks) + ")"
                rowids.update(row["rowid"] for row in self.fetchall(sql, tuple(chunk)))
        return self._fetch_by_rowids(table, sorted(rowids))

    def _matched_batch_rowids(self, kind: str, tmpl: str, vals: Sequence[Any]) -> Set[int]:
        if kind == "fixed":
            return {
                row["rowid"]
                for row in self.fetchall('SELECT b.rowid AS rowid FROM "Batches" b WHERE ' + tmpl, tuple(vals))
            }
        matched: Set[int] = set()
        for start in range(0, len(vals), QUERY_PARAM_CHUNK):
            chunk = vals[start : start + QUERY_PARAM_CHUNK]
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(
                'SELECT b.rowid AS rowid FROM "Batches" b WHERE ' + tmpl.format(marks=marks),
                tuple(chunk),
            )
            matched.update(row["rowid"] for row in rows)
        return matched

    def candidate_batch_rows(self, query_filter: Mapping[str, Any]) -> List[Dict[str, Any]]:
        predicates = _pushdown_predicates(query_filter)
        if predicates is None:
            return []
        if not predicates:
            return self.fetchall(raw_table_select_sql("Batches") + " ORDER BY rowid")
        total_params = sum(len(vals) for _kind, _tmpl, vals in predicates)
        if total_params <= QUERY_PARAM_CHUNK:
            clauses = [
                "(" + tmpl.format(marks=",".join("?" for _ in vals)) + ")" if kind == "in" else tmpl
                for kind, tmpl, vals in predicates
            ]
            params = tuple(v for _kind, _tmpl, vals in predicates for v in vals)
            return self.fetchall(
                raw_table_select_sql("Batches") + " b WHERE " + " AND ".join(clauses) + " ORDER BY b.rowid",
                params,
            )
        first_kind, first_tmpl, first_vals = predicates[0]
        candidate_rowids = self._matched_batch_rowids(first_kind, first_tmpl, first_vals)
        if not candidate_rowids:
            return []
        for kind, tmpl, vals in predicates[1:]:
            candidate_rowids &= self._matched_batch_rowids(kind, tmpl, vals)
            if not candidate_rowids:
                return []
        return self._fetch_by_rowids("Batches", sorted(candidate_rowids))

    def _scoped_relation_tables(
        self,
        batches: List[Dict[str, Any]],
        batch_ids: List[str],
        part_nos: List[str],
        entity_refs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        active_batch_refs = sorted({row["ref"] for row in entity_refs if row["kind"] == "batch" and row["active"]})
        operations = self._fetch_union_by_rowid("BatchOperations", (), [("batch_id IN ({marks})", batch_ids)])
        op_ids = sorted({row["id"] for row in operations})
        materials = self._fetch_union_by_rowid("BatchMaterials", (), [("batch_id IN ({marks})", batch_ids)])
        req_ids = sorted({row["id"] for row in materials})
        tables: Dict[str, Any] = {
            "Batches": batches,
            "BatchOperations": operations,
            "Parts": self._fetch_union_by_rowid("Parts", (), [("part_no IN ({marks})", part_nos)]),
            "PartOperations": [],
            "BatchMaterials": materials,
            "BatchMaterialReviews": self._fetch_union_by_rowid(
                "BatchMaterialReviews", (), [("requirement_id IN ({marks})", req_ids)]
            ),
            "BatchMaterialStages": self._fetch_union_by_rowid(
                "BatchMaterialStages",
                (),
                [("requirement_id IN ({marks})", req_ids), ("operation_id IN ({marks})", op_ids)],
            ),
            "BatchMaterialArrivals": self._fetch_union_by_rowid(
                "BatchMaterialArrivals", (), [("requirement_id IN ({marks})", req_ids)]
            ),
            "BatchQuantitySplits": self._fetch_union_by_rowid(
                "BatchQuantitySplits",
                (),
                [("source_batch_id IN ({marks})", batch_ids), ("child_batch_id IN ({marks})", batch_ids)],
            ),
            "Materials": self.fetchall(raw_table_select_sql("Materials") + " ORDER BY rowid"),
            "WorkbenchEntityRefs": entity_refs,
            "WorkbenchOutsourcingReceipts": self._fetch_union_by_rowid(
                "WorkbenchOutsourcingReceipts", (), [("batch_ref IN ({marks})", active_batch_refs)]
            ),
            "BatchExternalContexts": self._fetch_union_by_rowid(
                "BatchExternalContexts", (), [("operation_id IN ({marks})", op_ids)]
            ),
        }
        for table in STATIC_RESOURCE_TABLES:
            tables[table] = self.fetchall(raw_table_select_sql(table) + " ORDER BY rowid")
        return tables

    def closure_batch_tables(self, target_refs: Sequence[str]) -> Dict[str, Any]:
        refs = sorted(set(target_refs))
        batch_refs = self._fetch_union_by_rowid("WorkbenchEntityRefs", (), [("kind='batch' AND ref IN ({marks})", refs)])
        batch_ids = sorted({row["entity_key"] for row in batch_refs if row["active"]})
        batches = self._fetch_union_by_rowid("Batches", (), [("batch_id IN ({marks})", batch_ids)])
        if not batches:
            empty_tables: Dict[str, Any] = {table: [] for table in BATCH_FACT_TABLES}
            empty_tables["WorkbenchEntityRefs"] = batch_refs
            return empty_tables
        part_nos = sorted({row["part_no"] for row in batches})
        entity_refs = self._fetch_union_by_rowid(
            "WorkbenchEntityRefs",
            ("kind IN ('machine', 'operator', 'supplier', 'op_type', 'material')",),
            [("kind='part' AND entity_key IN ({marks})", part_nos)],
        ) + batch_refs
        return self._scoped_relation_tables(batches, batch_ids, part_nos, entity_refs)

    def filtered_batch_tables(self, query_filter: Mapping[str, Any]) -> Dict[str, Any]:
        batches = self.candidate_batch_rows(query_filter)
        if not batches:
            return {table: [] for table in BATCH_FACT_TABLES}
        batch_ids = sorted({row["batch_id"] for row in batches})
        part_nos = sorted({row["part_no"] for row in batches})
        entity_refs = self._fetch_union_by_rowid(
            "WorkbenchEntityRefs",
            ("kind IN ('machine', 'operator', 'supplier', 'op_type', 'material')",),
            [
                ("kind='part' AND entity_key IN ({marks})", part_nos),
                ("kind='batch' AND entity_key IN ({marks})", batch_ids),
            ],
        )
        return self._scoped_relation_tables(batches, batch_ids, part_nos, entity_refs)

    def scoped_entity_tables(self, target_refs: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
        refs = sorted(set(target_refs))
        entity_refs = self._fetch_union_by_rowid("WorkbenchEntityRefs", (), [("kind='batch' AND ref IN ({marks})", refs)])
        batch_ids = sorted({row["entity_key"] for row in entity_refs if row["active"]})
        batches = self._fetch_union_by_rowid("Batches", (), [("batch_id IN ({marks})", batch_ids)])
        part_nos = sorted({row["part_no"] for row in batches})
        parts = self._fetch_union_by_rowid("Parts", (), [("part_no IN ({marks})", part_nos)])
        return {"Batches": batches, "Parts": parts, "WorkbenchEntityRefs": entity_refs}

    def batch_codes(self) -> Set[str]:
        return {row["batch_id"] for row in self.fetchall('SELECT batch_id FROM "Batches"')}

    def _populate_single_template(self, tables: Dict[str, Any], batch_id: str, part_no: str) -> None:
        related_groups_sql = (
            'SELECT group_id FROM "ExternalGroups" WHERE part_no=? OR group_id IN ('
            'SELECT ext_group_id FROM "PartOperations" WHERE part_no=? AND ext_group_id IS NOT NULL)'
        )
        tables["ExternalGroups"] = self.fetchall(
            f"{raw_table_select_sql('ExternalGroups')} WHERE part_no=? OR group_id IN ("
            'SELECT ext_group_id FROM "PartOperations" WHERE part_no=? AND ext_group_id IS NOT NULL) ORDER BY rowid',
            (part_no, part_no),
        )
        tables["PartOperations"] = self.fetchall(
            f"{raw_table_select_sql('PartOperations')} WHERE part_no=? "
            f"OR (status='active' AND ext_group_id IN ({related_groups_sql})) ORDER BY rowid",
            (part_no, part_no, part_no),
        )
        entity_refs = self.fetchall(
            f"WITH related_groups AS ({related_groups_sql}), scoped_part_ops AS ("
            'SELECT CAST(id AS TEXT) AS entity_key FROM "PartOperations" WHERE part_no=? '
            "OR (status='active' AND ext_group_id IN (SELECT group_id FROM related_groups))) "
            f"{raw_table_select_sql('WorkbenchEntityRefs')} "
            "WHERE kind IN ('part', 'machine', 'operator', 'supplier', 'op_type', 'material') "
            "OR (kind='batch' AND entity_key=?) "
            "OR (kind='template_operation' AND entity_key IN (SELECT entity_key FROM scoped_part_ops)) "
            "OR (kind='template_external_group' AND entity_key IN (SELECT group_id FROM related_groups)) ORDER BY rowid",
            (part_no, part_no, part_no, batch_id),
        )
        part_ref = next(
            (r["ref"] for r in entity_refs if r["kind"] == "part" and r["entity_key"] == part_no and r["active"] == 1),
            None,
        )
        tables["WorkbenchEntityRefs"] = entity_refs
        tables["WorkbenchProcessWorkflow"] = (
            self.fetchall(f"{raw_table_select_sql('WorkbenchProcessWorkflow')} WHERE part_ref=? ORDER BY rowid", (part_ref,))
            if part_ref is not None
            else []
        )
        tables["WorkbenchProcessOperationConfirmations"] = (
            self.fetchall(
                f"{raw_table_select_sql('WorkbenchProcessOperationConfirmations')} WHERE part_ref=? ORDER BY rowid",
                (part_ref,),
            )
            if part_ref is not None
            else []
        )

    def single_batch_tables(
        self,
        batch_row: Dict[str, Any],
        batch_ref: str,
        *,
        include_template: bool = False,
        include_batch_codes: bool = False,
        all_parts: bool = False,
        include_instance_relations: bool = True,
    ) -> Dict[str, Any]:
        batch_id, part_no = batch_row["batch_id"], batch_row["part_no"]
        operations = self.fetchall(f"{raw_table_select_sql('BatchOperations')} WHERE batch_id=? ORDER BY rowid", (batch_id,))
        if include_instance_relations:
            op_sub = 'SELECT id FROM "BatchOperations" WHERE batch_id=?'
            req_sub = 'SELECT id FROM "BatchMaterials" WHERE batch_id=?'
            external_contexts = self.fetchall(
                f"{raw_table_select_sql('BatchExternalContexts')} WHERE operation_id IN ({op_sub}) ORDER BY rowid",
                (batch_id,),
            )
            batch_materials = self.fetchall(f"{raw_table_select_sql('BatchMaterials')} WHERE batch_id=? ORDER BY rowid", (batch_id,))
            reviews = self.fetchall(
                f"{raw_table_select_sql('BatchMaterialReviews')} WHERE requirement_id IN ({req_sub}) ORDER BY rowid", (batch_id,)
            )
            arrivals = self.fetchall(
                f"{raw_table_select_sql('BatchMaterialArrivals')} WHERE requirement_id IN ({req_sub}) ORDER BY rowid", (batch_id,)
            )
            stages = self.fetchall(
                f"{raw_table_select_sql('BatchMaterialStages')} WHERE requirement_id IN ({req_sub}) "
                f"OR operation_id IN ({op_sub}) ORDER BY rowid",
                (batch_id, batch_id),
            )
            splits = self.fetchall(
                f"{raw_table_select_sql('BatchQuantitySplits')} WHERE source_batch_id=? OR child_batch_id=? ORDER BY rowid",
                (batch_id, batch_id),
            )
            receipts = self.fetchall(
                f"{raw_table_select_sql('WorkbenchOutsourcingReceipts')} WHERE batch_ref=? ORDER BY rowid", (batch_ref,)
            )
        else:
            external_contexts, batch_materials, reviews, arrivals, stages, splits, receipts = [], [], [], [], [], [], []
        parts = (
            self.fetchall(raw_table_select_sql("Parts") + " ORDER BY rowid")
            if all_parts
            else self.fetchall(raw_table_select_sql("Parts") + " WHERE part_no=? ORDER BY rowid", (part_no,))
        )
        tables: Dict[str, Any] = {
            "Batches": [batch_row], "BatchOperations": operations, "Parts": parts,
            "BatchMaterials": batch_materials, "BatchMaterialReviews": reviews,
            "BatchMaterialStages": stages, "BatchMaterialArrivals": arrivals,
            "BatchQuantitySplits": splits, "WorkbenchOutsourcingReceipts": receipts,
            "BatchExternalContexts": external_contexts,
        }
        for table in STATIC_RESOURCE_TABLES:
            tables[table] = self.fetchall(raw_table_select_sql(table) + " ORDER BY rowid")
        tables["Materials"] = self.fetchall(raw_table_select_sql("Materials") + " ORDER BY rowid") if include_instance_relations else []
        tables["WorkbenchSupplierProfiles"] = (
            self.fetchall(raw_table_select_sql("WorkbenchSupplierProfiles") + " ORDER BY rowid") if include_template else []
        )
        if include_template:
            self._populate_single_template(tables, batch_id, part_no)
        else:
            tables["PartOperations"], tables["ExternalGroups"] = [], []
            kinds = (
                "('part', 'machine', 'operator', 'supplier', 'op_type', 'material')"
                if include_instance_relations
                else "('part', 'machine', 'operator', 'supplier', 'op_type')"
            )
            tables["WorkbenchEntityRefs"] = self.fetchall(
                f"{raw_table_select_sql('WorkbenchEntityRefs')} WHERE kind IN {kinds} OR (kind='batch' AND entity_key=?) ORDER BY rowid",
                (batch_id,),
            )
        if include_batch_codes:
            tables["batch_codes"] = self.batch_codes()
        return tables

    def entity_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        """Minimal tables required for batch identity, uniqueness and part existence checks."""
        return {
            table: self.fetchall(raw_table_select_sql(table) + " ORDER BY rowid")
            for table in ("Batches", "Parts", "WorkbenchEntityRefs")
        }

    def choice_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        """Creation choices need only base catalogs, authorizations and existing refs."""
        tables = {table: self.fetchall('SELECT * FROM "' + table + '" ORDER BY rowid') for table in CHOICE_CATALOG_TABLES}
        tables["WorkbenchEntityRefs"] = self.fetchall('''SELECT * FROM "WorkbenchEntityRefs"
            WHERE kind IN ('part', 'machine', 'operator', 'supplier') ORDER BY rowid''')
        return tables

    def batch_row(self, batch_id: str) -> Optional[Dict[str, Any]]:
        return self.fetchone(raw_table_select_sql("Batches") + " WHERE batch_id=?", (batch_id,))
