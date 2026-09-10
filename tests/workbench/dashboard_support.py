"""CR-owned temporary real SQLite support. Does not start the production app."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g, jsonify

from core.infrastructure.workbench_dashboard_schema import install
from core.infrastructure.workbench_execution_ledger_schema import install_execution_ledger
from core.infrastructure.workbench_metadata_schema import install_metadata
from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.models.workbench_dashboard import DashboardQuery
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.dashboard import WorkbenchDashboardService
from core.services.workbench.dashboard_commands import WorkbenchDashboardCommandService
from core.services.workbench.production_report import WorkbenchProductionReportService
from web.routes.workbench.dashboard import register_dashboard_routes
from web.routes.workbench.write_context import issue_write_context, validate_write_context

NOW = datetime(2026, 9, 10, 12)


def connect(path):
    conn = sqlite3.connect(str(path), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class DashboardCase:
    def __init__(self, path, conn):
        self.path, self.conn = path, conn
        self.app = Flask(__name__)
        self.counter = 0

    def read(self, query=None):
        reader = WorkbenchDashboardService(self.conn, clock=lambda: NOW, context_factory=issue_write_context)
        with reader.read_snapshot():
            data = reader.read()
            return reader.workspace(data, query or DashboardQuery(size=100)), data

    def item(self, category="delivery"):
        return next(row for row in self.read()[0]["items"] if row["category"] == category)

    def command(self, item, payload, *, action="transition", key=None, conn=None):
        self.counter += 1
        writer = WorkbenchDashboardCommandService(conn or self.conn, clock=lambda: NOW, actor_provider=lambda: "local-test-operator")
        return writer.execute(action, item["item_ref"], payload, request_key=key or f"dashboard-test-{self.counter:08d}",
            validate_context=lambda ref, verb, facts: validate_write_context(item["write_context"]["write_token"], ref, verb, facts))

    def history(self, ref):
        reader = WorkbenchDashboardService(self.conn)
        with reader.read_snapshot():
            return reader.repo.history(ref, 1, 100)["items"]

    def plan(self, version):
        self.conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary,schedule_time) "
                          "VALUES (?,'dashboard-fixture','success',?,'2026-09-08T12:00:00')", (version, json.dumps({"scheduled_ops": 1})))
        self.conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) "
                          "VALUES (?,?,'DM1','DO1','2026-09-09T08:00:00','2026-09-09T10:00:00')", (version, self.op))

    def report(self, quantity=2, **patch):
        task = self.conn.execute("SELECT t.ref FROM WorkbenchTaskRefs t JOIN WorkbenchPlanSourceRefs p ON p.ref=t.plan_ref "
                                 "WHERE p.kind='official' AND p.version=1").fetchone()[0]
        resource = lambda kind: self.conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND active=1", (kind,)).fetchone()[0]
        values = {"actual_start": "2026-09-09T08:00:00", "actual_end": "2026-09-09T10:20:00", "completed_quantity": quantity,
                  "effective_processing_hours": 1.5, "actual_machine_ref": resource("machine"), "actual_operator_ref": resource("operator"),
                  "remark": "real fixture report", **patch}
        self.counter += 1
        return WorkbenchProductionReportService(self.conn, clock=lambda: NOW).execute("create", task, values,
            request_key=f"dashboard-report-{self.counter:08d}", validate_context=lambda *_: None)


@pytest.fixture(name="dashboard_case")
def dashboard_case(tmp_path):
    path = tmp_path / "dashboard.sqlite"
    conn = connect(path)
    conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
    conn.execute("BEGIN")
    install_metadata(conn)
    install_plan_identity(conn)
    install_execution_ledger(conn)
    install(conn)
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('DT1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('DM1','Lathe','DT1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('DO1','Operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('DO1','DM1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('DP1','Part')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_status) VALUES ('DB1','DP1','Part',2,'2026-09-08','no')")
    case = DashboardCase(path, conn)
    case.op = conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,unit_hours,setup_hours) "
                           "VALUES ('DOP1','DB1',1,'DT1','Turning','internal',0.5,0)").lastrowid
    case.plan(1)
    conn.execute("INSERT INTO Materials(material_id,name,unit,stock_qty) VALUES ('DMAT','Steel','kg',900)")
    conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty,ready_status) VALUES ('DB1','DMAT',10,2,'no')")
    conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,reason_detail) "
                 "VALUES ('DM1','2026-09-09T09:00:00','2026-09-09T11:00:00','Maintenance')")
    conn.commit()
    with case.app.app_context():
        yield case
    conn.close()


def follow(**patch):
    return {"target_status": "following", "owner": "Planner", "deadline": "2026-09-11", "action": "Check affected operation",
            "remark": "Verified against current formal schedule", **patch}


def close_payload(**patch):
    return {**follow(target_status="closed", completed_at="2026-09-10T11:00:00",
                     completion_evidence="Confirmed rescheduling review with production supervisor",
                     evidence_reference_text="Workshop record 2026-09-10-01"), **patch}


def source_rows(conn):
    names = ("Batches", "BatchOperations", "BatchMaterials", "Materials", "Schedule", "ScheduleHistory",
             "MachineDowntimes", "OperationExecutionEvents", "WorkbenchProductionReports", "WorkbenchProductionReportRevisions")
    def typed_row(row):
        return tuple((type(value).__name__, value.hex() if type(value) in (bytes, float) else value) for value in row)
    return {name: [typed_row(row) for row in conn.execute('SELECT * FROM "' + name + '" ORDER BY rowid')] for name in names}


def api(case, monkeypatch, *, connect_factory=connect):
    import web.routes.workbench.dashboard as module

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(module, "datetime", Clock)
    app = Flask(__name__)
    bp = Blueprint("workbench", __name__)
    register_dashboard_routes(bp)

    @bp.get("/api/workbench/v1/commands/<request_key>")
    def command_receipt(request_key):
        result = WorkbenchCommandService(g.db).lookup(request_key)
        return jsonify({"ok": True, "data": result, "state": "recorded" if result else "not_observed"})

    app.register_blueprint(bp)

    @app.before_request
    def bind():
        g.db = connect_factory(case.path)

    @app.teardown_request
    def close(error):
        g.db.close()

    return app.test_client()
