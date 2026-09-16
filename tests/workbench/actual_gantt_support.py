"""Temporary real SQLite only; no product startup, schema registration or production DB."""

import json
import secrets
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g

from core.infrastructure.database import get_connection
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects, install_execution_ledger
from core.infrastructure.workbench_execution_void_schema import install_execution_voids
from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.plan_read_support import PlanReadApi, seed_plans
from web.routes.workbench.actual_gantt import register_actual_gantt_routes
from web.routes.workbench.plan_reads import register_plan_read_routes

BASE = "/api/workbench/v1/actual-gantt"


def connect(path):
    return get_connection(str(path))


def remove_ledger_from_fixture(conn):
    """v25 schema.sql includes the ledger; simulate a missing ledger only in this temp DB."""
    owned = set(execution_ledger_objects())
    objects = [tuple(row) for row in conn.execute("SELECT type,name FROM sqlite_master") if row["name"] in owned]
    for kind in ("trigger", "index", "table"):
        for actual_kind, name in reversed(objects):
            if actual_kind == kind:
                conn.execute('DROP ' + kind.upper() + ' "' + name + '"')


class ActualGanttApi(PlanReadApi):
    @contextmanager
    def db(self):
        conn = connect(self.path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()


def seed_report(conn, task, number, *, start="2026-09-08T22:00:00", end="2026-09-08T23:00:00", quantity=2, hours=1, machine="PRIVATE-M1"):
    ref, revision = secrets.token_hex(24), secrets.token_hex(24)
    request_key = "actual-fixture-" + secrets.token_hex(12)
    identities = WorkbenchIdentityRepository(conn)
    machine_ref = identities.active_map("machine", [machine])[machine].ref if machine else None
    operator_ref = identities.active_map("operator", ["PRIVATE-O1"])["PRIVATE-O1"].ref
    values = dict(actual_start=start, actual_end=end, completed_quantity=quantity, effective_processing_hours=hours,
                  actual_machine_ref=machine_ref, actual_operator_ref=operator_ref, remark="=fixture formula must be neutralized")
    conn.execute("INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_hash,outcome_json) VALUES (?,?,?,?,?,?)",
                 (request_key, secrets.token_hex(16), "fixture", task["task_ref"], "0" * 64, "{}"))
    conn.execute("INSERT INTO WorkbenchProductionReports(report_ref,report_no,operation_ref,recorded_against_task_ref,recorded_against_plan_ref,source,recorded_at) VALUES (?,?,?,?,?,'manual',?)",
                 (ref, number, task["operation_ref"], task["task_ref"], task["plan_ref"], "2026-09-09T08:00:00"))
    conn.execute("INSERT INTO WorkbenchProductionReportRevisions(revision_ref,report_ref,sequence,action,values_json,reason,local_operator,declared_operator,recorded_at,request_key) VALUES (?,?,1,'create',?,'','fixture','fixture',?,?)",
                 (revision, ref, json.dumps(values), "2026-09-09T08:00:00", request_key))
    return ref


def seed_database(path, ledger=True):
    conn = connect(path)
    try:
        conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
        if not ledger:
            remove_ledger_from_fixture(conn)
        install_plan_identity(conn)
        conn.commit()
        seed_plans(conn)
        conn.execute("UPDATE Batches SET quantity=10,due_date='2026-09-09' WHERE batch_id='CAT-B'")
        conn.execute("UPDATE Schedule SET start_time='2026-09-08 22:00:00',end_time='2026-09-09 06:00:00' WHERE version=3")
        conn.execute("UPDATE Machines SET name='精密数控加工中心甲线长中文资源名称测试设备' WHERE machine_id='PRIVATE-M1'")
        conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('ACTUAL-M2','五分厂实际改换设备乙线')")
        conn.execute("UPDATE Operators SET name='现场操作人员长中文名称甲' WHERE operator_id='PRIVATE-O1'")
        conn.execute("INSERT INTO WorkCalendar(date,shift_start,shift_hours,remark) VALUES ('2026-09-08','22:00',8,?)", (b'\x00\xffactual-calendar',))
        conn.execute("INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_hours) VALUES ('PRIVATE-O1','2026-09-08','22:00',8)")
        assert type(conn.execute("SELECT date FROM WorkCalendar").fetchone()[0]) is date
        assert type(conn.execute("SELECT date FROM OperatorCalendar").fetchone()[0]) is date
        assert type(conn.execute("SELECT due_date FROM Batches").fetchone()[0]) is date
        if ledger:
            install_execution_ledger(conn)
            install_execution_voids(conn)
        conn.commit()
    finally:
        conn.close()


def make_api(path):
    app = Flask("actual-gantt-fixture")
    app.config["TESTING"] = True
    app.config["DATABASE_PATH"] = str(path)
    bp = Blueprint("actual_gantt_test", __name__)
    register_actual_gantt_routes(bp)
    register_plan_read_routes(bp)
    app.register_blueprint(bp)
    api = ActualGanttApi(app, path)

    @app.before_request
    def database():
        g.db = connect(path)
        g.db.execute("PRAGMA query_only=ON")
        g.db.set_trace_callback(api.statements.append)
        assert type(g.db.execute("SELECT date FROM WorkCalendar").fetchone()[0]) is date

    @app.teardown_request
    def close_database(exc):
        g.db.close()

    return api


def prepare(path, ledger=True, reports=True):
    seed_database(path, ledger)
    api = make_api(path)
    if ledger and reports:
        response = api.client.get(BASE, query_string={"plan_ref": api.ref()})
        assert response.status_code == 200, response.get_data(as_text=True)
        task = response.get_json()["data"]["items"][0]["task"]
        with api.db() as conn:
            seed_report(conn, task, "FG-001")
            seed_report(conn, task, "FG-002", start="2026-09-08T22:30:00", end="2026-09-08T23:30:00", quantity=None, hours=None)
            seed_report(conn, task, "FG-003", start="2026-09-09T00:10:00", end=None, quantity=0, hours=None, machine="ACTUAL-M2")
    return api


@pytest.fixture(name="actual_api")
def actual_api_fixture(tmp_path):
    return prepare(tmp_path / "actual-gantt.db")
