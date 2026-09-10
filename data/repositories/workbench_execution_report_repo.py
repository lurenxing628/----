"""Append-only persistence. Caller must already own the ordinary command transaction."""

import uuid

from core.models.workbench_command import canonical_json


def new_ref():
    return uuid.uuid4().hex + uuid.uuid4().hex[:16]


class WorkbenchExecutionReportRepository:
    def __init__(self, conn):
        self.conn = conn

    def allocate_number(self):
        number = self.conn.execute("SELECT next_report_no FROM WorkbenchExecutionLedgerClock WHERE singleton=1").fetchone()[0]
        while True:
            value = f"BG-{number:08d}"
            number += 1
            if not self.conn.execute("SELECT 1 FROM WorkbenchProductionReports WHERE report_no=?", (value,)).fetchone():
                break
        self.conn.execute("UPDATE WorkbenchExecutionLedgerClock SET next_report_no=? WHERE singleton=1", (number,))
        return value

    def append(self, row, *, request_key):
        if not self.conn.in_transaction:
            raise RuntimeError("Report persistence requires the outer command transaction.")
        if row["sequence"] == 1:
            fields = ("report_ref", "report_no", "operation_ref", "recorded_against_task_ref", "recorded_against_plan_ref",
                      "source", "legacy_fact_ref", "recorded_at")
            self.conn.execute("INSERT INTO WorkbenchProductionReports (" + ",".join(fields) + ") VALUES (" +
                              ",".join("?" for _ in fields) + ")", [row[key] for key in fields])
        self.conn.execute("""INSERT INTO WorkbenchProductionReportRevisions
            (revision_ref, report_ref, sequence, previous_revision_ref, action, values_json, reason,
             local_operator, declared_operator, recorded_at, request_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row["revision_ref"], row["report_ref"], row["sequence"], row["previous_revision_ref"], row["action"],
             canonical_json(row["values"]), row["reason"], row["local_operator"], row["declared_operator"],
             row["revision_at"], request_key))
