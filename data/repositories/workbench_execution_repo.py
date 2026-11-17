"""Bounded, SELECT-only execution facts; mutations live in the report repository.

Judgement (missing schema, unknown refs, row caps, ref syntax) belongs to
core.services.execution.ledger_reader; this module only returns what is stored.
"""

import json

from core.models.content import read_stored_json
from data.repositories.base_repo import BaseRepository
from data.repositories.sqlite_rows import sql_order

_TASK_ROWS_SQL = """SELECT s.task_ref, h.plan_ref, s.operation_ref,
    s.op_id, s.version, s.id AS schedule_id, s.start_time, s.end_time, s.start_us, s.end_us,
    s.machine_id, s.operator_id, s.lock_status
    FROM Schedule s
    JOIN ScheduleHistory h ON h.version=s.version
    WHERE h.plan_ref=?"""


class WorkbenchExecutionRepository(BaseRepository):
    def clock(self):
        """Ledger and plan identity revisions; None when either singleton row is missing."""
        row = self.fetchone("SELECT revision FROM WorkbenchExecutionLedgerClock WHERE singleton=1")
        plan = self.fetchone("SELECT revision FROM WorkbenchPlanIdentityClock WHERE singleton=1")
        if row is None or plan is None:
            return None
        return {"ledger_revision": row["revision"], "plan_revision": plan["revision"]}

    def operation_rows(self, refs):
        """Operation identity rows keyed by ref for the given unique refs; unknown refs are absent."""
        rows = self.fetchall(
            """SELECT o.ref AS operation_ref, o.active AS identity_active,
                bo.*, b.quantity AS batch_quantity FROM WorkbenchPlanSourceRefs o
                LEFT JOIN BatchOperations bo ON o.active=1 AND bo.id=CAST(o.source_key AS INTEGER)
                    AND CAST(bo.id AS TEXT)=o.source_key
                LEFT JOIN Batches b ON b.batch_id=bo.batch_id
                WHERE o.kind='operation' AND o.ref IN (SELECT value FROM json_each(?))""",
            (json.dumps(list(refs)),),
        )
        return {row["operation_ref"]: row for row in rows}

    def task_headers(self, refs):
        if not refs:
            return {}
        rows = self.fetchall(
            """SELECT s.task_ref, h.plan_ref, s.operation_ref, s.op_id, s.version, s.id AS schedule_id
            FROM Schedule s
            JOIN ScheduleHistory h ON h.version=s.version
            WHERE s.task_ref IN (SELECT value FROM json_each(?))""",
            (json.dumps(list(refs)),),
        )
        return {row["task_ref"]: row for row in rows}

    def task_rows(self, operation_refs, plan_ref):
        """Active task rows of plan_ref for the operations, in storage order; duplicates are returned as stored."""
        return self.fetchall(
            _TASK_ROWS_SQL + " AND s.operation_ref IN (SELECT value FROM json_each(?))",
            (plan_ref, json.dumps(list(operation_refs))),
        )

    def cohort_task_rows(self, operation_refs, plan_ref):
        """Stream a plan once for a large cohort; keep only its requested identities.

        Small directed reads retain task_rows. A complete cohort avoids rescanning
        the same plan for each SQL parameter chunk. Other plan rows are discarded
        as they arrive; requested duplicate bindings remain visible to the reader.
        """
        selected = set(operation_refs)
        return (row for row in self.iter_rows(_TASK_ROWS_SQL, (plan_ref,)) if row["operation_ref"] in selected)

    def active_reports(self, refs, limit):
        """Active (non-voided) inline report rows grouped by operation_ref, ordered by (recorded_at, report_no)."""
        rows = self.fetchall(
            """SELECT report_ref, report_no, operation_ref, recorded_against_task_ref,
                      recorded_against_plan_ref, source, recorded_at,
                      current_revision_ref, revision_count,
                      actual_start, actual_end, completed_quantity, effective_processing_hours,
                      actual_machine_ref, actual_operator_ref, remark,
                      current_local_operator, current_declared_operator
               FROM WorkbenchProductionReports
               WHERE voided = 0 AND operation_ref IN (SELECT value FROM json_each(?))
               LIMIT ?""",
            (json.dumps(list(refs)), limit + 1),
        )
        count = len(rows)
        if count > limit:
            return {}, count
        result = {}
        for row in rows:
            result.setdefault(row["operation_ref"], []).append(row)
        for group in result.values():
            group.sort(key=lambda item: (item["recorded_at"], item["report_no"]))
        return result, count

    def active_revision_count(self, refs) -> int:
        """Total revision count across active reports for the given operation_refs."""
        if not refs:
            return 0
        return self.execute(
            """SELECT COALESCE(SUM(p.revision_count), 0)
               FROM WorkbenchProductionReports p
               WHERE p.voided = 0 AND p.operation_ref IN (SELECT value FROM json_each(?))""",
            (json.dumps(list(refs)),),
        ).fetchone()[0]

    def reports(self, refs, limit):
        """Report revisions and all report heads, grouped by operation.

        Returns (revisions, heads, count). Heads without revisions remain visible
        in heads only. count includes their outer-join rows; count > limit means
        the cap was exceeded and both results are partial.
        """
        rows = self.fetchall(
            """SELECT p.*, v.revision_ref, v.sequence, v.previous_revision_ref,
                v.action, v.values_json, v.reason, v.local_operator, v.declared_operator,
                v.recorded_at AS revision_at, v.request_key, c.receipt_ref
                FROM WorkbenchProductionReports p
                LEFT JOIN WorkbenchProductionReportRevisions v ON v.report_ref=p.report_ref
                LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=v.request_key
                WHERE p.operation_ref IN (SELECT value FROM json_each(?)) LIMIT ?""",
            (json.dumps(list(refs)), limit + 1),
        )
        count = len(rows)
        if count > limit:
            return {}, {}, count
        rows.sort(key=lambda row: (sql_order(row["report_ref"]), sql_order(row["sequence"])))
        result, heads = {}, {}
        previous_report_ref = None
        for row in rows:
            if row["report_ref"] != previous_report_ref:
                heads.setdefault(row["operation_ref"], []).append(row["report_ref"])
                previous_report_ref = row["report_ref"]
            if row["revision_ref"] is None:
                continue
            row["values"] = read_stored_json(row.pop("values_json"), dict)
            result.setdefault(row["operation_ref"], {}).setdefault(row["report_ref"], []).append(row)
        return result, heads, count

    def report_voids(self, refs, limit):
        """Void facts keyed by report_ref; (result, count) with the same cap semantics as reports."""
        rows = self.fetchall(
            """SELECT v.*, c.receipt_ref FROM WorkbenchProductionReportVoids v
                JOIN WorkbenchProductionReports p ON p.report_ref=v.report_ref
                LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=v.request_key
                WHERE p.operation_ref IN (SELECT value FROM json_each(?)) LIMIT ?""",
            (json.dumps(list(refs)), limit + 1),
        )
        count = len(rows)
        if count > limit:
            return {}, count
        return {row["report_ref"]: row for row in rows}, count

    def report_header(self, *, report_ref):
        return self.fetchone("SELECT * FROM WorkbenchProductionReports WHERE report_ref=?", (report_ref,))

    def report_headers(self, values, *, by_number=False):
        field = "report_no" if by_number else "report_ref"
        if not values:
            return {}
        rows = self.fetchall(
            f"SELECT * FROM WorkbenchProductionReports WHERE {field} IN (SELECT value FROM json_each(?))",
            (json.dumps(list(values)),),
        )
        return {row[field]: row for row in rows}

    def resources(self, refs):
        rows = self.fetchall(
            """SELECT e.ref, e.kind, e.entity_key AS business_code, e.active,
                CASE WHEN e.active=0 THEN NULL WHEN e.kind='machine' THEN m.name
                     WHEN e.kind='operator' THEN o.name END AS label
                FROM WorkbenchEntityRefs e
                LEFT JOIN Machines m ON e.kind='machine' AND e.active=1 AND m.machine_id=e.entity_key
                LEFT JOIN Operators o ON e.kind='operator' AND e.active=1 AND o.operator_id=e.entity_key
                WHERE e.ref IN (SELECT value FROM json_each(?))""",
            (json.dumps(list(refs)),),
        )
        return [{"kind": row["kind"], "ref": row["ref"], "business_code": row["business_code"],
                 "label": row["label"] or row["business_code"], "available": bool(row["active"])} for row in rows]
