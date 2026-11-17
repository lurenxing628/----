"""Append-only persistence. Caller must already own the ordinary command transaction."""

import json

from core.models.hours import exact_hours_text, hours_text, stored_hours, sum_hours
from core.models.workbench_execution_input import EXTERNAL_REQUIRED_FIELDS, REQUIRED_FIELDS
from core.shared.strict_json import canonical_json


class WorkbenchExecutionReportRepository:
    def __init__(self, conn):
        self.conn = conn

    def allocate_numbers(self, count):
        if count <= 0:
            return []
        number = self.conn.execute("SELECT next_report_no FROM WorkbenchExecutionLedgerClock WHERE singleton=1").fetchone()[0]
        allocated = []
        while len(allocated) < count:
            remaining = count - len(allocated)
            step = max(remaining, 64)
            candidates = [(number + offset, f"BG-{number + offset:08d}") for offset in range(step)]
            codes = [code for _, code in candidates]
            rows = self.conn.execute(
                "SELECT report_no FROM WorkbenchProductionReports WHERE report_no IN (SELECT value FROM json_each(?))",
                (json.dumps(codes),),
            ).fetchall()
            taken = {row[0] for row in rows}
            for cand_num, cand_code in candidates:
                if cand_code not in taken:
                    allocated.append(cand_code)
                    if len(allocated) == count:
                        number = cand_num + 1
                        break
            else:
                number += step
        self.conn.execute("UPDATE WorkbenchExecutionLedgerClock SET next_report_no=? WHERE singleton=1", (number,))
        return allocated

    def _sync_operation_state(self, operation_ref):
        rows = self.conn.execute(
            """SELECT actual_start, actual_end, completed_quantity, effective_processing_hours,
                      actual_machine_ref, actual_operator_ref
               FROM WorkbenchProductionReports
               WHERE operation_ref = ? AND voided = 0""",
            (operation_ref,),
        ).fetchall()
        active_count = len(rows)
        known_qty = sum(row["completed_quantity"] for row in rows if row["completed_quantity"] is not None)
        unknown_qty_count = sum(row["completed_quantity"] is None for row in rows)
        internal_complete = int(
            bool(rows) and all(all(row[key] is not None for key in REQUIRED_FIELDS) for row in rows)
        )
        external_complete = int(
            bool(rows) and all(all(row[key] is not None for key in EXTERNAL_REQUIRED_FIELDS) for row in rows)
        )
        starts = [row["actual_start"] for row in rows if row["actual_start"]]
        ends = [row["actual_end"] for row in rows if row["actual_end"]]
        hours = sum_hours(
            None if row["effective_processing_hours"] is None else stored_hours(row["effective_processing_hours"])
            for row in rows
        )
        self.conn.execute(
            """INSERT INTO OperationExecutionStates (
                   operation_ref, active_report_count, known_completed_quantity, unknown_quantity_count,
                   internal_complete_flag, external_complete_flag, any_actual_end,
                   first_actual_start, max_actual_end, known_effective_hours_text, unknown_hour_count
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(operation_ref) DO UPDATE SET
                   active_report_count = excluded.active_report_count,
                   known_completed_quantity = excluded.known_completed_quantity,
                   unknown_quantity_count = excluded.unknown_quantity_count,
                   internal_complete_flag = excluded.internal_complete_flag,
                   external_complete_flag = excluded.external_complete_flag,
                   any_actual_end = excluded.any_actual_end,
                   first_actual_start = excluded.first_actual_start,
                   max_actual_end = excluded.max_actual_end,
                   known_effective_hours_text = excluded.known_effective_hours_text,
                   unknown_hour_count = excluded.unknown_hour_count""",
            (
                operation_ref,
                active_count,
                known_qty,
                unknown_qty_count,
                internal_complete,
                external_complete,
                int(bool(ends)),
                min(starts) if starts else None,
                max(ends) if ends else None,
                None if hours.known is None else exact_hours_text(hours.known),
                hours.unknown,
            ),
        )

    def append_void(self, fact, *, request_key):
        if not self.conn.in_transaction:
            raise RuntimeError("Report void persistence requires the outer command transaction.")
        fields = (
            "void_fact_ref",
            "report_ref",
            "original_revision_ref",
            "reason",
            "local_operator",
            "declared_operator",
            "recorded_at",
        )
        self.conn.execute(
            "INSERT INTO WorkbenchProductionReportVoids ("
            + ",".join(fields)
            + ",request_key) VALUES ("
            + ",".join("?" for _ in fields)
            + ",?)",
            [fact[key] for key in fields] + [request_key],
        )
        self.conn.execute(
            "UPDATE WorkbenchProductionReports SET voided = 1 WHERE report_ref = ?",
            (fact["report_ref"],),
        )
        operation_ref = self.conn.execute(
            "SELECT operation_ref FROM WorkbenchProductionReports WHERE report_ref = ?",
            (fact["report_ref"],),
        ).fetchone()[0]
        self._sync_operation_state(operation_ref)

    def append(self, row, *, request_key):
        if not self.conn.in_transaction:
            raise RuntimeError("Report persistence requires the outer command transaction.")
        values = row["values"]
        hours = values["effective_processing_hours"]
        stored_hours_text = None if hours is None else hours_text(hours)
        revision_params = (
            row["revision_ref"],
            row["report_ref"],
            row["sequence"],
            row["previous_revision_ref"],
            row["action"],
            canonical_json(values),
            row["reason"],
            row["local_operator"],
            row["declared_operator"],
            row["revision_at"],
            request_key,
        )
        revision_sql = """INSERT INTO WorkbenchProductionReportRevisions
            (revision_ref, report_ref, sequence, previous_revision_ref, action, values_json, reason,
             local_operator, declared_operator, recorded_at, request_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        if row["sequence"] == 1:
            self.conn.execute(
                """INSERT INTO WorkbenchProductionReports (
                       report_ref, report_no, operation_ref, recorded_against_task_ref,
                       recorded_against_plan_ref, source, recorded_at,
                       current_revision_ref, revision_count, voided,
                       actual_start, actual_end, completed_quantity, effective_processing_hours,
                       actual_machine_ref, actual_operator_ref, remark,
                       current_local_operator, current_declared_operator
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["report_ref"],
                    row["report_no"],
                    row["operation_ref"],
                    row["recorded_against_task_ref"],
                    row["recorded_against_plan_ref"],
                    row["source"],
                    row["recorded_at"],
                    row["revision_ref"],
                    values["actual_start"],
                    values["actual_end"],
                    values["completed_quantity"],
                    stored_hours_text,
                    values["actual_machine_ref"],
                    values["actual_operator_ref"],
                    values["remark"],
                    row["local_operator"],
                    row["declared_operator"],
                ),
            )
            self.conn.execute(revision_sql, revision_params)
        else:
            self.conn.execute(revision_sql, revision_params)
            self.conn.execute(
                """UPDATE WorkbenchProductionReports
                   SET current_revision_ref = ?,
                       revision_count = ?,
                       actual_start = ?,
                       actual_end = ?,
                       completed_quantity = ?,
                       effective_processing_hours = ?,
                       actual_machine_ref = ?,
                       actual_operator_ref = ?,
                       remark = ?,
                       current_local_operator = ?,
                       current_declared_operator = ?
                   WHERE report_ref = ?""",
                (
                    row["revision_ref"],
                    row["sequence"],
                    values["actual_start"],
                    values["actual_end"],
                    values["completed_quantity"],
                    stored_hours_text,
                    values["actual_machine_ref"],
                    values["actual_operator_ref"],
                    values["remark"],
                    row["local_operator"],
                    row["declared_operator"],
                    row["report_ref"],
                ),
            )
        self._sync_operation_state(row["operation_ref"])
