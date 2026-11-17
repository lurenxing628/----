"""Bounded original template/instance reads. This repository cannot write lineage or rule on it."""

import json

from .base_repo import BaseRepository


def _template_where(*, part_no=None, source=None, search=""):
    clauses = ["o.status='active'"]
    params = []
    if part_no is not None:
        clauses.append("o.part_no=?")
        params.append(part_no)
    if source in ("internal", "external"):
        clauses.append("o.source=?")
        params.append(source)
    elif source == "unknown":
        clauses.append("(o.source IS NULL OR o.source NOT IN ('internal', 'external'))")
    if search:
        clauses.append(
            "instr(aps_casefold("
            "COALESCE(o.part_no, '') || ' ' || COALESCE(p.part_name, '') || ' ' || "
            "COALESCE(o.op_type_name, '') || ' ' || COALESCE(CAST(o.seq AS TEXT), '')"
            "), ?) > 0"
        )
        params.append(search.casefold())
    return " AND ".join(clauses), tuple(params)


class WorkbenchCalibrationQueryRepository(BaseRepository):
    def part_identity(self, part_ref):
        """Active part identity's stored entity key, or None when the ref is no longer live."""
        return self.fetchone(
            "SELECT entity_key FROM WorkbenchEntityRefs WHERE ref=? AND kind='part' AND active=1",
            (part_ref,),
        )

    def template_rows(self, part_no, limit, *, source=None, search=""):
        """Active templates matching pushed-down filters; reads at most limit+1 rows."""
        where_sql, params = _template_where(part_no=part_no, source=source, search=search)
        return self.fetchall(
            """SELECT o.*, r.ref AS operation_ref, r.revision, p.part_name,
                      pr.ref AS part_ref
               FROM PartOperations o
               JOIN Parts p ON p.part_no=o.part_no
               JOIN WorkbenchEntityRefs r ON r.kind='template_operation' AND r.active=1
                   AND r.entity_key=CAST(o.id AS TEXT)
               JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1
                   AND pr.entity_key=o.part_no
               WHERE """
            + where_sql
            + " ORDER BY o.part_no,o.seq,o.id LIMIT ?",
            params + (limit + 1,),
        )

    def template_row(self, template_ref, *, part_no=None, source=None, search=""):
        """Point lookup for one active template by permanent ref with optional toolbar filters."""
        where_sql, params = _template_where(part_no=part_no, source=source, search=search)
        return self.fetchone(
            """SELECT o.*, r.ref AS operation_ref, r.revision, p.part_name,
                      pr.ref AS part_ref
               FROM WorkbenchEntityRefs r
               JOIN PartOperations o
                   ON o.id=CAST(r.entity_key AS INTEGER) AND CAST(o.id AS TEXT)=r.entity_key
               JOIN Parts p ON p.part_no=o.part_no
               JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1
                   AND pr.entity_key=o.part_no
               WHERE r.ref=? AND r.kind='template_operation' AND r.active=1 AND """
            + where_sql,
            (template_ref,) + params,
        )

    def candidate_instance_rows(self, part_numbers, template_refs, limit):
        """Same-part candidate instances joined with 6-column lineage origins and execution states."""
        # 没有模板就没有候选：下面的 lineage_ref IS NULL 分支本会放进同零件的未绑定实例。
        if not template_refs:
            return []
        return self.fetchall(
            """SELECT bo.id, bo.op_code, bo.batch_id, bo.piece_id, bo.seq, bo.source,
                      b.part_no, b.quantity AS batch_quantity,
                      r.ref AS operation_ref, r.active AS identity_active,
                      lo.lineage_ref, lo.template_operation_ref, lo.template_revision,
                      lo.source_eligible, lo.instance_modified,
                      COALESCE(oes.active_report_count, 0) AS active_report_count,
                      COALESCE(oes.known_completed_quantity, 0) AS known_completed_quantity,
                      COALESCE(oes.unknown_quantity_count, 0) AS unknown_quantity_count,
                      COALESCE(oes.internal_complete_flag, 0) AS internal_complete_flag,
                      COALESCE(oes.external_complete_flag, 0) AS external_complete_flag,
                      COALESCE(oes.any_actual_end, 0) AS any_actual_end,
                      oes.first_actual_start,
                      oes.max_actual_end,
                      oes.known_effective_hours_text,
                      COALESCE(oes.unknown_hour_count, 0) AS unknown_hour_count
               FROM BatchOperations bo
               JOIN Batches b ON b.batch_id=bo.batch_id
               LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1
                   AND r.source_key=CAST(bo.id AS TEXT)
               LEFT JOIN WorkbenchTemplateLineageOrigins lo ON lo.operation_ref=r.ref
               LEFT JOIN OperationExecutionStates oes ON oes.operation_ref=r.ref
               WHERE b.part_no IN (SELECT value FROM json_each(?))
                 AND (lo.lineage_ref IS NULL OR lo.template_operation_ref IN (SELECT value FROM json_each(?)))
               ORDER BY b.part_no, bo.id
               LIMIT ?""",
            (json.dumps(list(part_numbers)), json.dumps(list(template_refs)), limit + 1),
        )

    def template_candidate_instance_rows(self, part_no, template_ref, limit):
        """Point lookup of candidate instances bound to template_ref or unbound on the same part."""
        return self.fetchall(
            """SELECT bo.*, b.part_no, b.quantity AS batch_quantity,
                      r.ref AS operation_ref, r.active AS identity_active,
                      lo.lineage_ref, lo.template_operation_ref, lo.template_revision,
                      lo.source_eligible, lo.instance_modified
               FROM BatchOperations bo
               JOIN Batches b ON b.batch_id=bo.batch_id
               LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1
                   AND r.source_key=CAST(bo.id AS TEXT)
               LEFT JOIN WorkbenchTemplateLineageOrigins lo ON lo.operation_ref=r.ref
               WHERE b.part_no=? AND (lo.template_operation_ref=? OR lo.lineage_ref IS NULL)
               ORDER BY bo.id
               LIMIT ?""",
            (part_no, template_ref, limit + 1),
        )

    def selected_report_refs(self, operation_refs):
        """Narrow index-covered lookup of active report_ref and current_revision_ref for selected samples."""
        if not operation_refs:
            return {}
        rows = self.fetchall(
            """SELECT operation_ref, report_ref, current_revision_ref
               FROM WorkbenchProductionReports
               WHERE voided = 0 AND operation_ref IN (SELECT value FROM json_each(?))
               ORDER BY operation_ref, recorded_at, report_no""",
            (json.dumps(list(operation_refs)),),
        )
        result = {}
        for row in rows:
            result.setdefault(row["operation_ref"], []).append(
                (row["report_ref"], row["current_revision_ref"])
            )
        return result
