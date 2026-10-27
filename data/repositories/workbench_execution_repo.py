"""Bounded, SELECT-only execution facts; mutations live in the report repository.

Judgement (missing schema, unknown refs, row caps, ref syntax) belongs to
core.services.execution.ledger_reader; this module only returns what is stored.
"""

from typing import NoReturn

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_contract_issues
from core.infrastructure.workbench_execution_void_schema import execution_void_contract_issues
from core.shared.strict_json import load_strict_json
from data.repositories.base_repo import BaseRepository

_TASK_ROWS_SQL = """SELECT t.ref AS task_ref, t.plan_ref, r.operation_ref,
    r.operation_id AS op_id, r.version, r.kind AS identity_kind,
    r.source_table AS identity_source_table, r.source_key AS row_source_key, r.owner_key,
    s.id AS schedule_id, s.start_time, s.end_time, s.machine_id,
    s.operator_id, s.lock_status FROM WorkbenchPlanSourceRefs r
    JOIN WorkbenchTaskRefs t ON t.row_ref=r.ref AND t.plan_ref=?
    LEFT JOIN Schedule s ON r.kind='schedule_row' AND s.id=CAST(r.source_key AS INTEGER)
        AND s.op_id=r.operation_id AND s.version=r.version
    WHERE r.active=1"""


_CHUNK_SIZE = 300


def _corrupt_report_values() -> NoReturn:
    raise ValueError("已保存的报工内容无法读取。")


def stored_report_values(text):
    """One WorkbenchProductionReportRevisions.values_json, as canonical_json wrote it."""
    return load_strict_json(text, on_malformed=_corrupt_report_values)


def chunks(values):
    for start in range(0, len(values), _CHUNK_SIZE):
        yield values[start:start + _CHUNK_SIZE]


class WorkbenchExecutionRepository(BaseRepository):
    def schema_issues(self):
        """Ledger and void contract issues in storage order; empty when the schema is complete."""
        memo = schema_contract_memo(self.conn)
        return memo.get_schema(execution_ledger_contract_issues) + memo.get_schema(execution_void_contract_issues)

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
        for chunk in chunks(list(operation_refs)):
            marks = ",".join("?" for _ in chunk)
            rows.extend(self.fetchall(_TASK_ROWS_SQL + f" AND r.operation_ref IN ({marks})", [plan_ref] + chunk))
        return rows

    def cohort_task_rows(self, operation_refs, plan_ref):
        """Stream a plan once for a large cohort; keep only its requested identities.

        Small directed reads retain task_rows. A complete cohort avoids rescanning
        the same plan for each SQL parameter chunk. Other plan rows are discarded
        as they arrive; requested duplicate bindings remain visible to the reader.
        """
        selected = set(operation_refs)
        return (row for row in self.iter_rows(_TASK_ROWS_SQL, (plan_ref,)) if row["operation_ref"] in selected)

    def reports(self, refs, limit):
        """Report revisions and all report heads, grouped by operation.

        Returns (revisions, heads, count). Heads without revisions remain visible
        in heads only. count includes their outer-join rows; count > limit means
        the cap was exceeded and both results are partial.
        """
        result, heads, count = {}, {}, 0
        for chunk in chunks(list(refs)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"""SELECT p.*, v.revision_ref, v.sequence, v.previous_revision_ref,
                v.action, v.values_json, v.reason, v.local_operator, v.declared_operator,
                v.recorded_at AS revision_at, v.request_key, c.receipt_ref
                FROM WorkbenchProductionReports p
                LEFT JOIN WorkbenchProductionReportRevisions v ON v.report_ref=p.report_ref
                LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=v.request_key
                WHERE p.operation_ref IN ({marks}) ORDER BY p.report_ref, v.sequence LIMIT ?""",
                                 chunk + [limit + 1 - count])
            count += len(rows)
            if count > limit:
                break
            previous_report_ref = None
            for row in rows:
                if row["report_ref"] != previous_report_ref:
                    heads.setdefault(row["operation_ref"], []).append(row["report_ref"])
                    previous_report_ref = row["report_ref"]
                if row["revision_ref"] is None:
                    continue
                row["values"] = stored_report_values(row.pop("values_json"))
                result.setdefault(row["operation_ref"], {}).setdefault(row["report_ref"], []).append(row)
        return result, heads, count

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

    def report_header(self, *, report_ref):
        return self.fetchone("SELECT * FROM WorkbenchProductionReports WHERE report_ref=?", (report_ref,))

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
        for chunk in chunks(refs):
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
