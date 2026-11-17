"""批次事实读仓储：两段式 SQL 真分页、按需闭包读取与单条原始行。"""

from __future__ import annotations

import json
from typing import Any, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from core.models.enums import BATCH_PRIORITY_RANKS, BATCH_STATUS_RANKS
from core.shared.strict_parse import JS_SAFE_INT_MAX

from .base_repo import BaseRepository
from .sql_ranks import rank_sql
from .sqlite_rows import raw_table_select_sql

BATCH_FACT_TABLES = (
    "Batches", "BatchOperations", "Parts", "PartOperations",
    "BatchMaterials", "BatchMaterialReviews", "BatchMaterialStages", "BatchMaterialArrivals",
    "BatchQuantitySplits", "Materials",
    "Machines", "MachineOpTypes", "Operators", "OperatorMachine", "OperatorSkill",
    "OpTypes", "Suppliers", "WorkbenchSupplierOpTypes", "WorkbenchOperatorProfiles",
    "WorkbenchEntityRefs", "WorkbenchOutsourcingReceipts", "BatchExternalContexts",
)
STATIC_RESOURCE_TABLES = (
    "Machines", "MachineOpTypes", "Operators", "OperatorMachine", "OperatorSkill",
    "OpTypes", "Suppliers", "WorkbenchSupplierOpTypes", "WorkbenchOperatorProfiles",
)
CHOICE_CATALOG_TABLES = ("Parts", "Machines", "Operators", "Suppliers", "OperatorMachine")


_SORT_EXPRESSIONS = {
    "business_code": "bd.batch_id", "part_no": "bd.part_no", "quantity": "bd.quantity", "due_date": "bd.norm_due",
    "priority": rank_sql("bd.priority", BATCH_PRIORITY_RANKS), "status": rank_sql("bd.derived_status", BATCH_STATUS_RANKS),
}


def _in_or_null_clause(expr: str, values: List[Any], has_none: bool, params: List[Any], *, check_text: bool = False) -> Optional[str]:
    if not values and not has_none:
        return None
    parts = [f"{expr} IS NULL"] if has_none else []
    if values:
        prefix = f"typeof({expr})='text' AND " if check_text else ""
        parts.append(f"({prefix}{expr} IN (SELECT value FROM json_each(?)))")
        params.append(json.dumps(values))
    return "(" + " OR ".join(parts) + ")"


def _scalar_filter_clauses(
    column_filters: Mapping[str, Any], norm_due_sql: str, params: List[Any]
) -> Optional[List[str]]:
    if any(not items for items in column_filters.values()):
        return None
    clauses: List[str] = []
    for key, expr, check_type in (
        ("business_code", "b.batch_id", True), ("part_no", "b.part_no", True),
        ("priority", "b.priority", True), ("due_date", norm_due_sql, False),
    ):
        if key in column_filters:
            items = column_filters[key]
            clause = _in_or_null_clause(expr, sorted({v for v in items if type(v) is str}), any(v is None for v in items), params, check_text=check_type)
            if clause is None:
                return None
            clauses.append(clause)
    if "quantity" in column_filters:
        items = column_filters["quantity"]
        ints = sorted({int(v) for v in items if (type(v) is int or (type(v) is float and v.is_integer())) and 0 <= v <= JS_SAFE_INT_MAX})
        clause = _in_or_null_clause("b.quantity", ints, any(v is None for v in items), params)
        if clause is None:
            return None
        clauses.append(clause)
    return clauses


def _build_stage1_cte(query_filter: Mapping[str, Any]) -> Optional[Tuple[str, str, List[Any]]]:
    params: List[Any] = []
    base_clauses: List[str] = []
    if query_filter["batch_ids"] is not None:
        if not query_filter["batch_ids"]:
            return None
        base_clauses.append("typeof(b.batch_id)='text' AND b.batch_id IN (SELECT value FROM json_each(?))")
        params.append(json.dumps(query_filter["batch_ids"]))
    # 批次数量由 Batches 的 CHECK 定为 1..2**53-1 的整数，直接用库里的值。
    norm_due_sql = "(CASE WHEN b.due_date IS NULL THEN NULL ELSE CAST(+b.due_date AS TEXT) END)"
    column_filters = query_filter["column_filters"]
    scalar_clauses = _scalar_filter_clauses(column_filters, norm_due_sql, params)
    if scalar_clauses is None:
        return None
    base_clauses.extend(scalar_clauses)
    if query_filter["query"]:
        needle = query_filter["query"].casefold()
        base_clauses.append(
            "(INSTR(aps_casefold(b.batch_id), ?)>0 OR INSTR(aps_casefold(b.part_no), ?)>0 "
            "OR (p.part_name IS NOT NULL AND INSTR(aps_casefold(p.part_name), ?)>0))"
        )
        params.extend((needle, needle, needle))
    base_where = " WHERE " + " AND ".join(base_clauses) if base_clauses else ""
    derived_clauses: List[str] = []
    if query_filter["status"]:
        derived_clauses.append("bd.derived_status = ?")
        params.append(query_filter["status"])
    if "status" in column_filters:
        items = column_filters["status"]
        clause = _in_or_null_clause("bd.derived_status", sorted({v for v in items if type(v) is str}), any(v is None for v in items), params, check_text=True)
        if clause is None:
            return None
        derived_clauses.append(clause)
    derived_where = " WHERE " + " AND ".join(derived_clauses) if derived_clauses else ""
    target_sql = "(CASE WHEN o.piece_id IS NOT NULL AND o.piece_id != '' THEN 1 ELSE cb.quantity END)"
    rec_ok_sql = "(CASE WHEN o.source='external' THEN COALESCE(oes.external_complete_flag,0) ELSE COALESCE(oes.internal_complete_flag,0) END)"
    cte_sql = (
        "WITH candidate_batches AS ("
        " SELECT b.batch_id, r.ref AS batch_ref, b.part_no,"
        f" b.quantity, {norm_due_sql} AS norm_due, b.priority, b.ready_status, b.status AS raw_status"
        ' FROM "Batches" b LEFT JOIN "Parts" p ON p.part_no = b.part_no'
        f' LEFT JOIN "WorkbenchEntityRefs" r ON r.kind=\'batch\' AND r.active=1 AND r.entity_key=b.batch_id{base_where}),'
        " op_eval AS ("
        " SELECT cb.batch_id, o.status AS op_stored_status,"
        f" CASE WHEN COALESCE(oes.active_report_count,0)>0 AND COALESCE(oes.known_completed_quantity,0)={target_sql}"
        f" AND COALESCE(oes.unknown_quantity_count,0)=0 AND {rec_ok_sql}=1 THEN 'complete'"
        " WHEN COALESCE(oes.known_completed_quantity,0)>0 OR COALESCE(oes.any_actual_end,0)=1 THEN 'partial'"
        " WHEN COALESCE(oes.active_report_count,0)>0 THEN 'started' ELSE 'unreported' END AS exec_state"
        ' FROM candidate_batches cb JOIN "BatchOperations" o ON o.batch_id = cb.batch_id'
        ' LEFT JOIN "WorkbenchPlanSourceRefs" psr ON psr.kind=\'operation\' AND psr.active=1 AND psr.source_key=CAST(o.id AS TEXT)'
        ' LEFT JOIN "OperationExecutionStates" oes ON oes.operation_ref = psr.ref),'
        " op_agg AS ("
        " SELECT batch_id, COUNT(*) AS op_cnt,"
        " SUM(CASE WHEN exec_state='complete' OR op_stored_status='completed' THEN 1 ELSE 0 END) AS done_cnt,"
        " MAX(CASE WHEN exec_state!='unreported' THEN 1 ELSE 0 END) AS started_flag FROM op_eval GROUP BY batch_id),"
        " batch_derived AS ("
        " SELECT cb.*, COALESCE(oa.op_cnt,0) AS op_cnt,"
        " CASE WHEN COALESCE(oa.op_cnt,0)>0 AND COALESCE(oa.done_cnt,0)=COALESCE(oa.op_cnt,0) THEN 1 ELSE 0 END AS all_complete,"
        " CASE WHEN COALESCE(oa.op_cnt,0)>0 AND COALESCE(oa.done_cnt,0)=COALESCE(oa.op_cnt,0) THEN 'completed'"
        " WHEN COALESCE(oa.started_flag,0)=1 THEN 'processing' ELSE cb.raw_status END AS derived_status,"
        ' EXISTS (SELECT 1 FROM "BatchMaterials" bm WHERE bm.batch_id=cb.batch_id) AS has_materials'
        " FROM candidate_batches cb LEFT JOIN op_agg oa ON oa.batch_id = cb.batch_id)"
    )
    return cte_sql, derived_where, params


class WorkbenchBatchFactsRepository(BaseRepository):
    def query_page_stage1(self, query_filter: Mapping[str, Any]) -> Dict[str, Any]:
        built = _build_stage1_cte(query_filter)
        if built is None:
            return {"total": 0, "completed": 0, "page_refs": []}
        cte_sql, derived_where, params = built
        stats = self.fetchone(
            f"{cte_sql} SELECT COUNT(*) AS total, COALESCE(SUM(bd.all_complete),0) AS completed FROM batch_derived bd{derived_where}",
            tuple(params),
        )
        assert stats is not None
        total = stats["total"]
        offset = (query_filter["page"] - 1) * query_filter["size"]
        if total == 0 or offset >= total:
            return {**stats, "page_refs": []}
        sort_expr = _SORT_EXPRESSIONS[query_filter["sort"]]
        direction = query_filter["direction"].upper()
        page_rows = self.fetchall(
            f"{cte_sql} SELECT bd.batch_ref FROM batch_derived bd{derived_where} "
            f"ORDER BY ({sort_expr} IS NULL) {direction}, {sort_expr} {direction}, bd.batch_id ASC LIMIT ? OFFSET ?",
            tuple(params) + (query_filter["size"], offset),
        )
        return {**stats, "page_refs": [row["batch_ref"] for row in page_rows]}

    def query_candidates_stage1(self, query_filter: Mapping[str, Any]) -> List[Dict[str, Any]]:
        built = _build_stage1_cte(query_filter)
        if built is None:
            return []
        cte_sql, derived_where, params = built
        return self.fetchall(
            f"{cte_sql} SELECT bd.batch_id, bd.batch_ref, bd.part_no, bd.quantity, "
            "bd.norm_due, bd.priority, bd.ready_status, bd.derived_status, "
            f"bd.op_cnt, bd.all_complete, bd.has_materials FROM batch_derived bd{derived_where} ORDER BY bd.batch_id ASC",
            tuple(params),
        )

    def material_readiness_tables(self, batch_ids: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
        materials = self.fetchall(
            f"{raw_table_select_sql('BatchMaterials')} WHERE batch_id IN (SELECT value FROM json_each(?)) ORDER BY rowid",
            (json.dumps(list(batch_ids)),),
        )
        req_ids = [row["id"] for row in materials]
        if not req_ids:
            return {"BatchMaterials": materials, "BatchMaterialReviews": [], "BatchMaterialArrivals": []}
        encoded = json.dumps(req_ids)
        return {
            "BatchMaterials": materials,
            "BatchMaterialReviews": self.fetchall(f"{raw_table_select_sql('BatchMaterialReviews')} WHERE requirement_id IN (SELECT value FROM json_each(?)) ORDER BY rowid", (encoded,)),
            "BatchMaterialArrivals": self.fetchall(f"{raw_table_select_sql('BatchMaterialArrivals')} WHERE requirement_id IN (SELECT value FROM json_each(?)) ORDER BY rowid", (encoded,)),
        }

    def gap_check_tables(self, batch_ids: Sequence[str]) -> Dict[str, Any]:
        operations = self.fetchall(
            'SELECT o.*, psr.ref AS operation_ref, COALESCE(oes.active_report_count,0) AS rep_cnt, '
            'COALESCE(oes.known_completed_quantity,0) AS known_qty, COALESCE(oes.unknown_quantity_count,0) AS unk_qty, '
            "CASE WHEN o.source='external' THEN COALESCE(oes.external_complete_flag,0) "
            "ELSE COALESCE(oes.internal_complete_flag,0) END AS records_complete, "
            'COALESCE(oes.any_actual_end,0) AS any_end FROM "BatchOperations" o '
            'LEFT JOIN "WorkbenchPlanSourceRefs" psr ON psr.kind=\'operation\' AND psr.active=1 AND psr.source_key=CAST(o.id AS TEXT) '
            'LEFT JOIN "OperationExecutionStates" oes ON oes.operation_ref = psr.ref '
            "WHERE o.batch_id IN (SELECT value FROM json_each(?)) ORDER BY o.rowid",
            (json.dumps(list(batch_ids)),),
        )
        op_ids = [row["id"] for row in operations]
        contexts = self.fetchall(
            f"{raw_table_select_sql('BatchExternalContexts')} WHERE operation_id IN (SELECT value FROM json_each(?)) ORDER BY rowid",
            (json.dumps(op_ids),),
        ) if op_ids else []
        return {"BatchOperations": operations, "BatchExternalContexts": contexts, **{t: self.fetchall(raw_table_select_sql(t) + " ORDER BY rowid") for t in STATIC_RESOURCE_TABLES}}

    def plan_reference_counts(self, op_ids: Optional[Sequence[int]] = None) -> Dict[int, int]:
        if op_ids is not None:
            if not op_ids:
                return {}
            rows = self.fetchall(
                "SELECT p.op_id, COUNT(*) AS reference_count FROM Schedule p "
                "WHERE p.op_id IN (SELECT value FROM json_each(?)) GROUP BY p.op_id ORDER BY p.op_id",
                (json.dumps(list(op_ids)),),
            )
            return {row["op_id"]: row["reference_count"] for row in rows}
        rows = self.fetchall("SELECT p.op_id, COUNT(*) AS reference_count FROM Schedule p JOIN BatchOperations o ON o.id=p.op_id GROUP BY p.op_id ORDER BY p.op_id")
        return {row["op_id"]: row["reference_count"] for row in rows}

    def whole_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        return {table: self.fetchall(raw_table_select_sql(table) + " ORDER BY rowid") for table in BATCH_FACT_TABLES}

    def _fetch_union_by_rowid(
        self, table: str, fixed_clauses: Sequence[str], in_clauses: Sequence[Tuple[str, Collection[Any]]]
    ) -> List[Dict[str, Any]]:
        active_in = [(clause, vals) for clause, vals in in_clauses if vals]
        if not fixed_clauses and not active_in:
            return []
        parts = list(fixed_clauses) + [clause for clause, _vals in active_in]
        params = tuple(json.dumps(list(vals)) for _clause, vals in active_in)
        return self.fetchall(
            f"{raw_table_select_sql(table)} WHERE " + " OR ".join(f"({p})" for p in parts) + " ORDER BY rowid",
            params,
        )

    def _scoped_relation_tables(self, batches: List[Dict[str, Any]], batch_ids: List[str], part_nos: Collection[str], entity_refs: List[Dict[str, Any]]) -> Dict[str, Any]:
        active_batch_refs = [row["ref"] for row in entity_refs if row["kind"] == "batch" and row["active"]]
        operations = self._fetch_union_by_rowid("BatchOperations", (), [("batch_id IN (SELECT value FROM json_each(?))", batch_ids)])
        op_ids = [row["id"] for row in operations]
        materials = self._fetch_union_by_rowid("BatchMaterials", (), [("batch_id IN (SELECT value FROM json_each(?))", batch_ids)])
        req_ids = [row["id"] for row in materials]
        tables: Dict[str, Any] = {
            "Batches": batches, "BatchOperations": operations,
            "Parts": self._fetch_union_by_rowid("Parts", (), [("part_no IN (SELECT value FROM json_each(?))", part_nos)]),
            "PartOperations": [], "BatchMaterials": materials,
            "BatchMaterialReviews": self._fetch_union_by_rowid("BatchMaterialReviews", (), [("requirement_id IN (SELECT value FROM json_each(?))", req_ids)]),
            "BatchMaterialStages": self._fetch_union_by_rowid("BatchMaterialStages", (), [("requirement_id IN (SELECT value FROM json_each(?))", req_ids), ("operation_id IN (SELECT value FROM json_each(?))", op_ids)]),
            "BatchMaterialArrivals": self._fetch_union_by_rowid("BatchMaterialArrivals", (), [("requirement_id IN (SELECT value FROM json_each(?))", req_ids)]),
            "BatchQuantitySplits": self._fetch_union_by_rowid("BatchQuantitySplits", (), [("source_batch_id IN (SELECT value FROM json_each(?))", batch_ids), ("child_batch_id IN (SELECT value FROM json_each(?))", batch_ids)]),
            "Materials": self.fetchall(raw_table_select_sql("Materials") + " ORDER BY rowid"),
            "WorkbenchEntityRefs": entity_refs,
            "WorkbenchOutsourcingReceipts": self._fetch_union_by_rowid("WorkbenchOutsourcingReceipts", (), [("batch_ref IN (SELECT value FROM json_each(?))", active_batch_refs)]),
            "BatchExternalContexts": self._fetch_union_by_rowid("BatchExternalContexts", (), [("operation_id IN (SELECT value FROM json_each(?))", op_ids)]),
        }
        for table in STATIC_RESOURCE_TABLES:
            tables[table] = self.fetchall(raw_table_select_sql(table) + " ORDER BY rowid")
        return tables

    def closure_batch_tables(self, target_refs: Sequence[str], *, include_batch_codes: bool = False) -> Dict[str, Any]:
        batch_refs = self._fetch_union_by_rowid("WorkbenchEntityRefs", (), [("kind='batch' AND ref IN (SELECT value FROM json_each(?))", target_refs)])
        batch_ids = [row["entity_key"] for row in batch_refs if row["active"]]
        batches = self._fetch_union_by_rowid("Batches", (), [("batch_id IN (SELECT value FROM json_each(?))", batch_ids)])
        if not batches:
            empty_tables: Dict[str, Any] = {table: [] for table in BATCH_FACT_TABLES}
            empty_tables["WorkbenchEntityRefs"] = batch_refs
            if include_batch_codes:
                empty_tables["batch_codes"] = self.batch_codes()
            return empty_tables
        part_nos = {row["part_no"] for row in batches}
        seen_refs = {row["ref"] for row in batch_refs}
        extra_refs = self._fetch_union_by_rowid(
            "WorkbenchEntityRefs", ("kind IN ('machine', 'operator', 'supplier', 'op_type', 'material')",), [("kind='part' AND entity_key IN (SELECT value FROM json_each(?))", part_nos)]
        )
        entity_refs = list(batch_refs) + [row for row in extra_refs if row["ref"] not in seen_refs]
        tables = self._scoped_relation_tables(batches, batch_ids, part_nos, entity_refs)
        if include_batch_codes:
            tables["batch_codes"] = self.batch_codes()
        return tables

    def import_preview_tables(self, batch_codes: Sequence[str], part_nos: Sequence[str]) -> Dict[str, Any]:
        batches = self.fetchall(
            f"{raw_table_select_sql('Batches')} WHERE typeof(batch_id)='text' AND batch_id IN (SELECT value FROM json_each(?)) ORDER BY rowid",
            (json.dumps(list(batch_codes)),),
        ) if batch_codes else []
        matched_ids = [row["batch_id"] for row in batches]
        all_parts = set(part_nos) | {row["part_no"] for row in batches}
        if not batches:
            empty: Dict[str, Any] = {table: [] for table in BATCH_FACT_TABLES}
            empty["Parts"] = self._fetch_union_by_rowid("Parts", (), [("part_no IN (SELECT value FROM json_each(?))", all_parts)])
            empty["WorkbenchEntityRefs"] = self._fetch_union_by_rowid("WorkbenchEntityRefs", (), [("kind='part' AND entity_key IN (SELECT value FROM json_each(?))", all_parts)])
            return empty
        entity_refs = self._fetch_union_by_rowid(
            "WorkbenchEntityRefs", ("kind IN ('machine', 'operator', 'supplier', 'op_type', 'material')",),
            [("kind='part' AND entity_key IN (SELECT value FROM json_each(?))", all_parts), ("kind='batch' AND entity_key IN (SELECT value FROM json_each(?))", matched_ids)],
        )
        return self._scoped_relation_tables(batches, matched_ids, all_parts, entity_refs)

    def import_apply_tables(self, *, batch_refs: Sequence[str], part_refs: Sequence[str], create_codes: Sequence[str]) -> Dict[str, Any]:
        entity_refs = self._fetch_union_by_rowid(
            "WorkbenchEntityRefs", (),
            [("kind='batch' AND ref IN (SELECT value FROM json_each(?))", batch_refs), ("kind='part' AND ref IN (SELECT value FROM json_each(?))", part_refs)],
        )
        batch_ids = [row["entity_key"] for row in entity_refs if row["kind"] == "batch" and row["active"]]
        batches = self._fetch_union_by_rowid("Batches", (), [("batch_id IN (SELECT value FROM json_each(?))", batch_ids)])
        part_nos = {row["part_no"] for row in batches} | {row["entity_key"] for row in entity_refs if row["kind"] == "part" and row["active"]}
        parts = self._fetch_union_by_rowid("Parts", (), [("part_no IN (SELECT value FROM json_each(?))", part_nos)])
        existing_codes = {
            row["batch_id"] for row in self.fetchall(
                'SELECT batch_id FROM "Batches" WHERE typeof(batch_id)=\'text\' AND batch_id IN (SELECT value FROM json_each(?))',
                (json.dumps(list(create_codes)),),
            )
        } if create_codes else set()
        return {"Batches": batches, "Parts": parts, "WorkbenchEntityRefs": entity_refs, "batch_codes": existing_codes | {row["batch_id"] for row in batches}}

    def scoped_entity_tables(self, target_refs: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
        entity_refs = self._fetch_union_by_rowid("WorkbenchEntityRefs", (), [("kind='batch' AND ref IN (SELECT value FROM json_each(?))", target_refs)])
        batch_ids = [row["entity_key"] for row in entity_refs if row["active"]]
        batches = self._fetch_union_by_rowid("Batches", (), [("batch_id IN (SELECT value FROM json_each(?))", batch_ids)])
        parts = self._fetch_union_by_rowid("Parts", (), [("part_no IN (SELECT value FROM json_each(?))", {row["part_no"] for row in batches})])
        return {"Batches": batches, "Parts": parts, "WorkbenchEntityRefs": entity_refs}

    def entity_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        return {table: self.fetchall(raw_table_select_sql(table) + " ORDER BY rowid") for table in ("Batches", "Parts", "WorkbenchEntityRefs")}

    def batch_codes(self) -> Set[str]:
        return {row["batch_id"] for row in self.fetchall('SELECT batch_id FROM "Batches"')}

    def batch_exists(self, batch_id: str) -> bool:
        return self.fetchone('SELECT 1 AS present FROM "Batches" WHERE batch_id=? LIMIT 1', (batch_id,)) is not None

    def part_row(self, part_no: str) -> Optional[Dict[str, Any]]:
        return self.fetchone(raw_table_select_sql("Parts") + " WHERE part_no=?", (part_no,))

    def _populate_single_template(self, tables: Dict[str, Any], batch_id: str, part_no: str) -> None:
        related_groups_sql = (
            'SELECT group_id FROM "ExternalGroups" WHERE part_no=? OR group_id IN ('
            'SELECT ext_group_id FROM "PartOperations" WHERE part_no=? AND ext_group_id IS NOT NULL)'
        )
        tables["ExternalGroups"] = self.fetchall(f"{raw_table_select_sql('ExternalGroups')} WHERE part_no=? OR group_id IN (SELECT ext_group_id FROM \"PartOperations\" WHERE part_no=? AND ext_group_id IS NOT NULL) ORDER BY rowid", (part_no, part_no))
        tables["PartOperations"] = self.fetchall(f"{raw_table_select_sql('PartOperations')} WHERE part_no=? OR (status='active' AND ext_group_id IN ({related_groups_sql})) ORDER BY rowid", (part_no, part_no, part_no))
        tables["WorkbenchEntityRefs"] = self.fetchall(
            f"WITH related_groups AS ({related_groups_sql}), scoped_part_ops AS ("
            f'SELECT CAST(id AS TEXT) AS entity_key FROM "PartOperations" WHERE part_no=? OR (status=\'active\' AND ext_group_id IN (SELECT group_id FROM related_groups))) '
            f"{raw_table_select_sql('WorkbenchEntityRefs')} WHERE kind IN ('part', 'machine', 'operator', 'supplier', 'op_type', 'material') "
            "OR (kind='batch' AND entity_key=?) OR (kind='template_operation' AND entity_key IN (SELECT entity_key FROM scoped_part_ops)) "
            "OR (kind='template_external_group' AND entity_key IN (SELECT group_id FROM related_groups)) ORDER BY rowid",
            (part_no, part_no, part_no, batch_id),
        )

    def single_batch_tables(
        self, batch_row: Dict[str, Any], batch_ref: str, *, include_template: bool = False,
        include_batch_codes: bool = False, all_parts: bool = False, include_instance_relations: bool = True
    ) -> Dict[str, Any]:
        batch_id, part_no = batch_row["batch_id"], batch_row["part_no"]
        operations = self.fetchall(f"{raw_table_select_sql('BatchOperations')} WHERE batch_id=? ORDER BY rowid", (batch_id,))
        if include_instance_relations:
            op_sub, req_sub = 'SELECT id FROM "BatchOperations" WHERE batch_id=?', 'SELECT id FROM "BatchMaterials" WHERE batch_id=?'
            external_contexts = self.fetchall(f"{raw_table_select_sql('BatchExternalContexts')} WHERE operation_id IN ({op_sub}) ORDER BY rowid", (batch_id,))
            batch_materials = self.fetchall(f"{raw_table_select_sql('BatchMaterials')} WHERE batch_id=? ORDER BY rowid", (batch_id,))
            reviews = self.fetchall(f"{raw_table_select_sql('BatchMaterialReviews')} WHERE requirement_id IN ({req_sub}) ORDER BY rowid", (batch_id,))
            arrivals = self.fetchall(f"{raw_table_select_sql('BatchMaterialArrivals')} WHERE requirement_id IN ({req_sub}) ORDER BY rowid", (batch_id,))
            stages = self.fetchall(f"{raw_table_select_sql('BatchMaterialStages')} WHERE requirement_id IN ({req_sub}) OR operation_id IN ({op_sub}) ORDER BY rowid", (batch_id, batch_id))
            splits = self.fetchall(f"{raw_table_select_sql('BatchQuantitySplits')} WHERE source_batch_id=? OR child_batch_id=? ORDER BY rowid", (batch_id, batch_id))
            receipts = self.fetchall(f"{raw_table_select_sql('WorkbenchOutsourcingReceipts')} WHERE batch_ref=? ORDER BY rowid", (batch_ref,))
        else:
            external_contexts, batch_materials, reviews, arrivals, stages, splits, receipts = [], [], [], [], [], [], []
        parts = self.fetchall(raw_table_select_sql("Parts") + " ORDER BY rowid") if all_parts else self.fetchall(raw_table_select_sql("Parts") + " WHERE part_no=? ORDER BY rowid", (part_no,))
        tables: Dict[str, Any] = {
            "Batches": [batch_row], "BatchOperations": operations, "Parts": parts, "BatchMaterials": batch_materials,
            "BatchMaterialReviews": reviews, "BatchMaterialStages": stages, "BatchMaterialArrivals": arrivals,
            "BatchQuantitySplits": splits, "WorkbenchOutsourcingReceipts": receipts, "BatchExternalContexts": external_contexts,
            **{table: self.fetchall(raw_table_select_sql(table) + " ORDER BY rowid") for table in STATIC_RESOURCE_TABLES},
            "Materials": self.fetchall(raw_table_select_sql("Materials") + " ORDER BY rowid") if include_instance_relations else [],
            "WorkbenchSupplierProfiles": self.fetchall(raw_table_select_sql("WorkbenchSupplierProfiles") + " ORDER BY rowid") if include_template else [],
        }
        if include_template:
            self._populate_single_template(tables, batch_id, part_no)
        else:
            tables["PartOperations"], tables["ExternalGroups"] = [], []
            kinds = "('part', 'machine', 'operator', 'supplier', 'op_type', 'material')" if include_instance_relations else "('part', 'machine', 'operator', 'supplier', 'op_type')"
            tables["WorkbenchEntityRefs"] = self.fetchall(f"{raw_table_select_sql('WorkbenchEntityRefs')} WHERE kind IN {kinds} OR (kind='batch' AND entity_key=?) ORDER BY rowid", (batch_id,))
        if include_batch_codes:
            tables["batch_codes"] = self.batch_codes()
        return tables

    def choice_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        tables = {table: self.fetchall('SELECT * FROM "' + table + '" ORDER BY rowid') for table in CHOICE_CATALOG_TABLES}
        tables["WorkbenchEntityRefs"] = self.fetchall('SELECT * FROM "WorkbenchEntityRefs" WHERE kind IN (\'part\', \'machine\', \'operator\', \'supplier\') ORDER BY rowid')
        return tables

    def batch_row(self, batch_id: str) -> Optional[Dict[str, Any]]:
        return self.fetchone(raw_table_select_sql("Batches") + " WHERE batch_id=?", (batch_id,))
