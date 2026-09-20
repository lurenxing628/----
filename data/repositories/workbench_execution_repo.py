"""Bounded, SELECT-only execution facts; mutations live in the report repository.

Judgement (missing schema, unknown refs, row caps, ref syntax) belongs to
core.services.execution.ledger_reader; this module only returns what is stored.
"""

import json

from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_contract_issues
from core.infrastructure.workbench_execution_void_schema import execution_void_contract_issues
from data.repositories.base_repo import BaseRepository


def chunks(values, size=300):
    for start in range(0, len(values), size):
        yield values[start:start + size]


class WorkbenchExecutionRepository(BaseRepository):
    def schema_issues(self):
        """Ledger and void contract issues in storage order; empty when the schema is complete."""
        return list(execution_ledger_contract_issues(self.conn)) + list(execution_void_contract_issues(self.conn))

    def schema_version_row(self):
        """SchemaVersion 单行（id=1）原始行；不存在时为 None。"""
        return self.fetchone("SELECT version FROM SchemaVersion WHERE id=1")

    def has_execution_receipts(self):
        """是否已有任何 execution.* 命令回执。"""
        return self.fetchone("SELECT 1 FROM WorkbenchCommandReceipts WHERE action GLOB 'execution.*' LIMIT 1") is not None

    def clock(self):
        """Ledger and plan identity revisions; None when either singleton row is missing."""
        row = self.fetchone("SELECT revision FROM WorkbenchExecutionLedgerClock WHERE singleton=1")
        plan = self.fetchone("SELECT revision FROM WorkbenchPlanIdentityClock WHERE singleton=1")
        if row is None or plan is None:
            return None
        return {"ledger_revision": row["revision"], "plan_revision": plan["revision"]}

    def operation_rows(self, refs):
        """Operation identity rows keyed by ref for the given unique refs; unknown refs are absent."""
        rows = []
        for chunk in chunks(list(refs)):
            marks = ",".join("?" for _ in chunk)
            rows.extend(self.fetchall(f"""SELECT o.ref AS operation_ref, o.active AS identity_active,
                bo.*, b.quantity AS batch_quantity FROM WorkbenchPlanSourceRefs o
                LEFT JOIN BatchOperations bo ON o.active=1 AND bo.id=CAST(o.source_key AS INTEGER)
                    AND CAST(bo.id AS TEXT)=o.source_key
                LEFT JOIN Batches b ON b.batch_id=bo.batch_id
                WHERE o.kind='operation' AND o.ref IN ({marks})""", chunk))
        return {row["operation_ref"]: row for row in rows}

    def task_headers(self, refs):
        result = {}
        for chunk in chunks(list(refs)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"""SELECT t.ref AS task_ref, t.plan_ref, r.operation_ref,
            r.operation_id AS op_id, r.active AS row_active, r.kind, r.version,
            r.source_key, p.active AS plan_active FROM WorkbenchTaskRefs t
            JOIN WorkbenchPlanSourceRefs r ON r.ref=t.row_ref
            JOIN WorkbenchPlanSourceRefs p ON p.ref=t.plan_ref WHERE t.ref IN ({marks})""", chunk)
            result.update((row["task_ref"], row) for row in rows)
        return result

    def task_rows(self, operation_refs, plan_ref):
        """Active task rows of plan_ref for the operations, in storage order; duplicates are returned as stored."""
        rows = []
        if plan_ref is None:
            return rows
        for chunk in chunks(list(operation_refs)):
            marks = ",".join("?" for _ in chunk)
            rows.extend(self.fetchall(f"""SELECT t.ref AS task_ref, t.plan_ref, r.operation_ref,
                r.operation_id AS op_id, r.version, s.start_time, s.end_time, s.machine_id,
                s.operator_id, s.lock_status FROM WorkbenchPlanSourceRefs r
                JOIN WorkbenchTaskRefs t ON t.row_ref=r.ref AND t.plan_ref=?
                LEFT JOIN Schedule s ON r.kind='schedule_row' AND s.id=CAST(r.source_key AS INTEGER)
                    AND s.op_id=r.operation_id AND s.version=r.version
                WHERE r.operation_ref IN ({marks}) AND r.active=1""", [plan_ref] + chunk))
        return rows

    def page_tasks(self, plan_ref, size, after):
        """Up to size + 1 task rows after the cursor so the caller can detect a further page."""
        return self.fetchall("""SELECT t.ref AS task_ref, r.operation_ref FROM WorkbenchTaskRefs t
            JOIN WorkbenchPlanSourceRefs r ON r.ref=t.row_ref AND r.active=1
            WHERE t.plan_ref=? AND t.ref>? ORDER BY t.ref LIMIT ?""", (plan_ref, after or "", size + 1))

    def reports(self, refs, limit):
        """Report revisions grouped by operation then report; stops once more than limit rows were read.

        Returns (result, count). count > limit means the cap was exceeded and result is partial.
        """
        result, count = {}, 0
        for chunk in chunks(list(refs)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"""SELECT p.*, v.revision_ref, v.sequence, v.previous_revision_ref,
                v.action, v.values_json, v.reason, v.local_operator, v.declared_operator,
                v.recorded_at AS revision_at, v.request_key, c.receipt_ref
                FROM WorkbenchProductionReports p
                JOIN WorkbenchProductionReportRevisions v ON v.report_ref=p.report_ref
                LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=v.request_key
                WHERE p.operation_ref IN ({marks}) ORDER BY p.report_ref, v.sequence LIMIT ?""",
                                 chunk + [limit + 1 - count])
            count += len(rows)
            if count > limit:
                break
            for row in rows:
                row["values"] = json.loads(row.pop("values_json"))
                result.setdefault(row["operation_ref"], {}).setdefault(row["report_ref"], []).append(row)
        return result, count

    def legacy(self, refs, limit):
        """Legacy facts grouped by operation; (result, count) with the same cap semantics as reports."""
        result, count = {}, 0
        for chunk in chunks(list(refs)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"SELECT * FROM WorkbenchExecutionLegacyFacts WHERE operation_ref IN ({marks}) ORDER BY id LIMIT ?",
                                 chunk + [limit + 1 - count])
            count += len(rows)
            if count > limit:
                break
            for row in rows:
                result.setdefault(row["operation_ref"], []).append(row)
        return result, count

    def report_voids(self, refs, limit):
        """Void facts keyed by report_ref; (result, count) with the same cap semantics as reports."""
        result, count = {}, 0
        for chunk in chunks(list(refs)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"""SELECT v.*, c.receipt_ref FROM WorkbenchProductionReportVoids v
                JOIN WorkbenchProductionReports p ON p.report_ref=v.report_ref
                LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=v.request_key
                WHERE p.operation_ref IN ({marks}) ORDER BY v.report_ref LIMIT ?""", chunk + [limit + 1 - count])
            count += len(rows)
            if count > limit:
                break
            result.update((row["report_ref"], row) for row in rows)
        return result, count

    def unresolved_operations(self, operations):
        ids = {row["id"]: ref for ref, row in operations.items() if row["id"] is not None}
        result = set()
        for chunk in chunks(list(ids)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"""SELECT DISTINCT op_id FROM WorkbenchExecutionLegacyFacts
                WHERE (operation_ref IS NULL OR recorded_against_task_ref IS NULL) AND op_id IN ({marks})""", chunk)
            result.update(ids[row["op_id"]] for row in rows)
        return result

    def report_header(self, *, report_ref=None, report_no=None):
        if report_ref is not None:
            return self.fetchone("SELECT * FROM WorkbenchProductionReports WHERE report_ref=?", (report_ref,))
        return self.fetchone("SELECT * FROM WorkbenchProductionReports WHERE report_no=?", (report_no,))

    def report_headers(self, values, *, by_number=False):
        field = "report_no" if by_number else "report_ref"
        result = {}
        for chunk in chunks(list(values)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"SELECT * FROM WorkbenchProductionReports WHERE {field} IN ({marks})", chunk)
            result.update((row[field], row) for row in rows)
        return result

    def resources(self, refs):
        rows = []
        for chunk in chunks(sorted(set(refs))):
            marks = ",".join("?" for _ in chunk)
            rows.extend(self.fetchall(f"""SELECT e.ref, e.kind, e.entity_key AS business_code, e.active,
                CASE WHEN e.active=0 THEN NULL WHEN e.kind='machine' THEN m.name
                     WHEN e.kind='operator' THEN o.name END AS label
                FROM WorkbenchEntityRefs e
                LEFT JOIN Machines m ON e.kind='machine' AND e.active=1 AND m.machine_id=e.entity_key
                LEFT JOIN Operators o ON e.kind='operator' AND e.active=1 AND o.operator_id=e.entity_key
                WHERE e.ref IN ({marks})""", chunk))
        return [{"kind": row["kind"], "ref": row["ref"], "business_code": row["business_code"],
                 "label": row["label"] or row["business_code"], "available": bool(row["active"])} for row in rows]
