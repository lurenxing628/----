"""AR-only full-app fixture using production SQLite DATE conversion and temp paths."""

import uuid
from contextlib import contextmanager
from datetime import date

import pytest
from flask import g, request

from core.infrastructure.database import get_connection
from tests.workbench.execution_ledger_support import LedgerCase
from tests.workbench.report_api_support import ReportApi

EXECUTION = "/api/workbench/v1/execution"


class ReportLedgerApi(ReportApi):
    @contextmanager
    def db(self):
        conn = get_connection(str(self.path))
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def task(self, op=1):
        with self.db() as conn:
            version = conn.execute("SELECT MAX(version) FROM ScheduleHistory").fetchone()[0]
            ref = LedgerCase(conn).task(version, op)
        response = self.client.get(EXECUTION + "/tasks/" + ref)
        assert response.status_code == 200, response.get_json()
        return response.get_json()["data"]["task"]

    def values(self, quantity=1, **patch):
        with self.db() as conn:
            return LedgerCase(conn).values(quantity, **patch)

    def create(self, values=None, op=1):
        task = self.task(op)
        return self._command(EXECUTION + "/tasks/" + task["task_ref"] + "/reports",
                             task["execution"]["write_context"], values if values is not None else self.values())

    def revise(self, report, action="correct", **values):
        task = self.task()
        current = next(row for row in task["execution"]["reports"] if row["report_ref"] == report["report_ref"])
        return self._command(EXECUTION + "/reports/" + report["report_ref"] + "/" + action,
            current["write_context"], {"original_revision_ref": current["revision_ref"], "reason": "AR verified source", **values})

    def _command(self, path, context, values):
        response = self.client.post(path, json={"request_key": "ar-report-" + uuid.uuid4().hex,
            "write_token": context["write_token"], "input": values})
        assert response.status_code == 200, response.get_json()
        return response.get_json()["data"]["rows"][0]


@pytest.fixture(name="report_ledger_api")
def report_ledger_api(app_client):
    app = app_client.application
    api = ReportLedgerApi(app, app.config["DATABASE_PATH"])
    with api.db() as conn:
        conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1'),('M2','Second lathe','T1')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1'),('O1','M2')")
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity,due_date) VALUES ('B1','P1',10,'2026-09-09')")
        conn.execute("INSERT INTO WorkCalendar(date,shift_start,shift_hours) VALUES ('2026-09-09','08:00',8)")
        conn.execute("INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_hours) VALUES ('O1','2026-09-09','08:00',8)")
        case = LedgerCase(conn)
        case.op_id = case.op()
        case.plan(1, [case.op_id])
        assert type(conn.execute("SELECT due_date FROM Batches WHERE batch_id='B1'").fetchone()[0]) is date
        assert type(conn.execute("SELECT date FROM WorkCalendar").fetchone()[0]) is date

    @app.before_request
    def trace_read_only_api():
        if request.method == "GET" and request.path.startswith("/api/workbench/"):
            g.db.execute("PRAGMA query_only=ON")
            g.db.set_trace_callback(api.statements.append)

    return api
