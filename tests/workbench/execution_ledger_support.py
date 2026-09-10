"""Dedicated real temporary SQLite fixtures. No production application imports."""

import sqlite3
from datetime import datetime

import pytest

from core.infrastructure.migration_state import set_schema_version
from core.infrastructure.workbench_execution_ledger_schema import install_execution_ledger
from core.infrastructure.workbench_metadata_schema import install_metadata
from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.services.workbench.execution_ledger import ExecutionLedgerService
from core.services.workbench.production_report import WorkbenchProductionReportService
from tests.workbench.plan_identity_support import load_v24_schema

NOW = datetime(2026, 9, 10, 12)
START, END = "2026-09-09T08:00:00", "2026-09-09T10:00:00"


class LedgerCase:
    def __init__(self, conn):
        self.conn = conn
        self.ledger = ExecutionLedgerService(conn, clock=lambda: NOW)
        self.writer = WorkbenchProductionReportService(conn, clock=lambda: NOW, actor_provider=lambda: "local-os-user")
        self.count = 0

    def install(self):
        self.conn.commit()
        self.conn.execute("BEGIN")
        install_execution_ledger(self.conn)
        self.conn.commit()

    def op(self, code="OP1", *, seq=1, piece=None, batch="B1"):
        return self.conn.execute("""INSERT INTO BatchOperations(op_code,batch_id,seq,piece_id,op_type_id,op_type_name,source)
            VALUES (?,?,?,?,'T1','Turning','internal')""", (code, batch, seq, piece)).lastrowid

    def plan(self, version, ids, *, start=START, end=END):
        self.conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary,schedule_time) VALUES (?,'ledger','success','{}',?)", (version, START))
        for op_id in ids:
            self.conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (?,?,'M1','O1',?,?)", (version, op_id, start, end))
        self.conn.commit()

    def plan_ref(self, version):
        return self.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='official' AND version=? AND active=1", (version,)).fetchone()[0]

    def task(self, version, op_id):
        return self.conn.execute("""SELECT t.ref FROM WorkbenchTaskRefs t JOIN WorkbenchPlanSourceRefs r ON r.ref=t.row_ref
            JOIN WorkbenchPlanSourceRefs p ON p.ref=t.plan_ref WHERE p.kind='official' AND p.version=?
            AND r.operation_id=? AND r.active=1""", (version, op_id)).fetchone()[0]

    def ref(self, kind, key):
        return self.conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, key)).fetchone()[0]

    def values(self, quantity=1, **patch):
        return {"actual_start": START, "actual_end": END, "completed_quantity": quantity,
                "effective_processing_hours": 1.5, "actual_machine_ref": self.ref("machine", "M1"),
                "actual_operator_ref": self.ref("operator", "O1"), "remark": "", **patch}

    def command(self, action, ref, payload, *, key=None, validate_context=None):
        self.count += 1
        return self.writer.execute(action, ref, payload, request_key=key or f"ledger-command-{self.count:08d}",
            validate_context=validate_context or (lambda *_: None))

    def event(self, op_id, event_type, *, version=1, quantity=None, time=None,
              source="schedule", role="adopted", scenario=None, batch_id="B1"):
        schedule = self.conn.execute("SELECT id FROM Schedule WHERE version=? AND op_id=?", (version, op_id)).fetchone()[0]
        count, last = self.conn.execute("SELECT count(*),coalesce(max(id),0) FROM OperationExecutionEvents WHERE schedule_id=?", (schedule,)).fetchone()
        status = {"start": "processing", "finish": "completed", "pause": "paused", "resume": "processing", "exception": "exception"}[event_type]
        event = self.conn.execute("""INSERT INTO OperationExecutionEvents
            (schedule_version,schedule_id,op_id,batch_id,source_table,effective_plan_role,event_type,reported_status,event_time,
             actual_machine_id,actual_operator_id,quantity_done,created_by,idempotency_key,request_fingerprint,previous_state_revision,reason_code,severity,scenario_id)
            VALUES (?,?,?,?,?,?,?,?,?,'M1','O1',?,'old-operator',?,'old-fingerprint',?,?,?,?)""",
            (version, schedule, op_id, batch_id, source, role, event_type, status, time or (START if event_type == "start" else END), quantity,
             f"old-{schedule}-{count}-{event_type}", f"{op_id}:{count}:{last}",
             "other" if event_type in ("pause", "exception") else None, "low" if event_type == "exception" else None, scenario)).lastrowid
        self.conn.commit()
        return event


@pytest.fixture(name="ledger_case")
def ledger_case(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "execution-ledger.sqlite"))
    conn.row_factory = sqlite3.Row
    load_v24_schema(conn)
    set_schema_version(conn, 24)
    conn.commit()
    conn.execute("BEGIN")
    install_metadata(conn)
    install_plan_identity(conn)
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B1','P1',10)")
    case = LedgerCase(conn)
    case.op_id = case.op()
    case.plan(1, [case.op_id])
    yield case
    conn.close()


def all_rows(conn):
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    return {table: [tuple(row) for row in conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid')] for table in tables}
