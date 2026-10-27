"""Append-only persistence. Caller must already own the ordinary command transaction."""

import uuid

from core.shared.strict_json import canonical_json


def new_ref():
    return uuid.uuid4().hex + uuid.uuid4().hex[:16]


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
            taken = set()
            for start in range(0, len(candidates), 400):
                chunk = [code for _, code in candidates[start : start + 400]]
                placeholders = ",".join("?" for _ in chunk)
                rows = self.conn.execute(
                    f"SELECT report_no FROM WorkbenchProductionReports WHERE report_no IN ({placeholders})",
                    chunk,
                ).fetchall()
                taken.update(row[0] for row in rows)
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

    def append_void(self, fact, *, request_key):
        if not self.conn.in_transaction:
            raise RuntimeError("Report void persistence requires the outer command transaction.")
        fields = ("void_fact_ref", "report_ref", "original_revision_ref", "reason", "local_operator", "declared_operator", "recorded_at")
        self.conn.execute("INSERT INTO WorkbenchProductionReportVoids (" + ",".join(fields) + ",request_key) VALUES (" +
                          ",".join("?" for _ in fields) + ",?)", [fact[key] for key in fields] + [request_key])

    def append(self, row, *, request_key):
        if not self.conn.in_transaction:
            raise RuntimeError("Report persistence requires the outer command transaction.")
        if row["sequence"] == 1:
            fields = ("report_ref", "report_no", "operation_ref", "recorded_against_task_ref", "recorded_against_plan_ref",
                      "source", "recorded_at")
            self.conn.execute("INSERT INTO WorkbenchProductionReports (" + ",".join(fields) + ") VALUES (" +
                              ",".join("?" for _ in fields) + ")", [row[key] for key in fields])
        self.conn.execute("""INSERT INTO WorkbenchProductionReportRevisions
            (revision_ref, report_ref, sequence, previous_revision_ref, action, values_json, reason,
             local_operator, declared_operator, recorded_at, request_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row["revision_ref"], row["report_ref"], row["sequence"], row["previous_revision_ref"], row["action"],
             canonical_json(row["values"]), row["reason"], row["local_operator"], row["declared_operator"],
             row["revision_at"], request_key))
