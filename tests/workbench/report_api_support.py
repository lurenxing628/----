"""Fresh SQLite connections in query_only mode. No production app startup."""

from pathlib import Path

import pytest
from flask import Blueprint, Flask, g

from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.models.operation_execution_scope import OperationExecutionScope
from data.repositories.operation_execution_event_repo import OperationExecutionEventRepo
from tests.workbench.plan_catalog_support import candidate, history, seed_operation
from tests.workbench.plan_read_support import PlanReadApi, connect
from web.routes.workbench.reports import register_report_routes

BASE = "/api/workbench/v1/analytics"


class ReportApi(PlanReadApi):
    def get(self, suffix="", **query):
        return self.client.get(BASE + suffix, query_string=query)


def make_api(path):
    app = Flask("report-test")
    app.config["TESTING"] = True
    bp = Blueprint("report_test", __name__)
    register_report_routes(bp)
    app.register_blueprint(bp)
    api = ReportApi(app, path)

    @app.before_request
    def database():
        g.db = connect(path)
        g.db.execute("PRAGMA query_only=ON")
        g.db.set_trace_callback(api.statements.append)

    @app.teardown_request
    def close_database(error):
        g.db.close()

    return api


def event(conn, op, kind, time, **extra):
    schedule = conn.execute("SELECT id FROM Schedule WHERE version=3 AND op_id=?", (op,)).fetchone()[0]
    status = {"start": "processing", "finish": "completed", "pause": "paused", "resume": "processing", "exception": "exception"}[kind]
    repo = OperationExecutionEventRepo(conn)
    scope = OperationExecutionScope.from_values(schedule_version=3, schedule_id=schedule, op_id=op, batch_id="CAT-B",
        source_table="schedule", effective_plan_role="adopted")
    return repo.insert_event({"schedule_version": 3, "schedule_id": schedule, "op_id": op, "batch_id": "CAT-B",
        "source_table": "schedule", "effective_plan_role": "adopted", "scenario_id": None,
        "event_type": kind, "reported_status": status, "event_time": time, "created_by": "test",
        "idempotency_key": f"event-{op}-{kind}", "request_fingerprint": "test", "previous_state_revision": repo.state_revision_for_scope(scope), **extra})


@pytest.fixture(name="report_api")
def report_api(tmp_path):
    path = tmp_path / "reports.db"
    conn = connect(path)
    try:
        conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
        install_plan_identity(conn)
        op = seed_operation(conn)
        history(conn, 1, op_id=op)
        history(conn, 3, op_id=op)
        candidate(conn, 3, "adopted", source="schedule")
        candidate(conn, 3, "critical_best", op_id=op)
        conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M1','一号设备'),('M2','二号设备')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','甲班人员')")
        conn.execute("UPDATE Batches SET due_date='2026-09-01' WHERE batch_id='CAT-B'")
        conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,status) VALUES ('M1','2026-09-02 08:00:00','2026-09-02 08:30:00','active')")
        conn.execute("UPDATE Schedule SET start_time='2026-09-01 08:00:00',end_time='2026-09-02 09:00:00',machine_id='M1',operator_id='O1' WHERE version=3")
        for number in range(2, 24):
            conn.execute("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) VALUES (?,?,'CAT-B',?,'精加工')", (number, f"OP-{number:02d}", number))
            conn.execute("INSERT INTO Schedule(version,op_id,start_time,end_time,machine_id,operator_id) VALUES (3,?,'2026-09-02 08:00:00','2026-09-02 09:00:00','M1','O1')", (number,))
        event(conn, 1, "start", "2026-09-01 08:00:00", actual_machine_id="M2", actual_operator_id="O1")
        event(conn, 1, "finish", "2026-09-02 09:10:00", quantity_done=1)
        event(conn, 2, "start", "2026-09-02 08:00:00")
        event(conn, 2, "finish", "2026-09-02 09:10:01", quantity_done=1)
        event(conn, 3, "start", "2026-09-02 08:00:00")
        conn.commit()
    finally:
        conn.close()
    return make_api(path)
