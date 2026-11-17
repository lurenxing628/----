"""CR-owned temporary real SQLite support. Does not start the production app."""

from datetime import datetime
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g

from core.models.workbench_dashboard import DashboardQuery
from core.services.workbench.dashboard.commands import WorkbenchDashboardCommandService
from core.services.workbench.dashboard.service import WorkbenchDashboardService
from core.services.workbench.execution.production_report import WorkbenchProductionReportService
from core.shared.local_datetime import datetime_to_us
from tests._support.sqlite_connection import open_test_connection
from tests.workbench.execution_ledger_support import publish_official_plan
from web.routes.workbench.commands import register_command_routes
from web.routes.workbench.dashboard import register_dashboard_routes
from web.routes.workbench.write_context import issue_write_context, validate_write_context
from web.runtime_host import install_wall_clock

NOW = datetime(2026, 9, 10, 12)


def connect(path):
    return open_test_connection(path)


class DashboardCase:
    def __init__(self, path, conn, operation_id: int):
        self.path, self.conn = path, conn
        self.op = operation_id
        self.app = Flask(__name__)
        self.counter = 0

    def read(self, query=None):
        reader = WorkbenchDashboardService(self.conn, context_factory=issue_write_context)
        with reader.read_snapshot():
            data = reader.read(NOW)
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
            return reader.history(ref, 1, 100)["items"]

    def plan(self, version):
        publish_official_plan(self.conn, version, [{"op_id": self.op, "machine_id": "DM1", "operator_id": "DO1",
                                                    "start_time": "2026-09-09T08:00:00", "end_time": "2026-09-09T10:00:00"}],
                              adopted_at="2026-09-08T12:00:00")

    def report(self, quantity=2, **patch):
        task = self.conn.execute("SELECT task_ref FROM Schedule WHERE version = 1 ORDER BY id ASC LIMIT 1").fetchone()[0]
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
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('DT1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('DM1','Lathe')")
    conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('DM1','DT1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('DO1','Operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('DO1','DM1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('DP1','Part')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_status) VALUES ('DB1','DP1','Part',2,'2026-09-08','no')")
    operation_id = conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,unit_hours,setup_hours) "
                                "VALUES ('DOP1','DB1',1,'DT1','Turning','internal',0.5,0)").lastrowid
    assert operation_id is not None
    case = DashboardCase(path, conn, operation_id)
    case.plan(1)
    conn.execute("INSERT INTO Materials(material_id,name,unit,stock_qty) VALUES ('DMAT','Steel','kg',900)")
    conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty,ready_status) VALUES ('DB1','DMAT',10,2,'no')")
    conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,start_us,end_us,reason_code,reason_detail) "
                 "VALUES ('DM1','2026-09-09 09:00:00','2026-09-09 11:00:00',?,?,'maintenance','Maintenance')",
                 (datetime_to_us(datetime(2026, 9, 9, 9)), datetime_to_us(datetime(2026, 9, 9, 11))))
    conn.commit()
    with case.app.app_context():
        yield case
    conn.close()


def follow(**patch):
    return {"target_status": "following", "owner": "Planner", "deadline": "2026-09-11", "action": "Check affected operation",
            "remark": "Verified against current formal schedule", **patch}


def source_rows(conn):
    names = ("Batches", "BatchOperations", "BatchMaterials", "Materials", "Schedule", "ScheduleHistory",
             "MachineDowntimes", "WorkbenchProductionReports", "WorkbenchProductionReportRevisions")
    def typed_row(row):
        return tuple((type(value).__name__, value.hex() if type(value) in (bytes, float) else value) for value in row)
    return {name: [typed_row(row) for row in conn.execute('SELECT * FROM "' + name + '" ORDER BY rowid')] for name in names}


def api(case, *, connect_factory=connect):
    app = Flask(__name__)
    install_wall_clock(app, lambda: NOW)
    bp = Blueprint("workbench", __name__)
    register_dashboard_routes(bp)
    register_command_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def bind():
        g.db = connect_factory(case.path)

    @app.teardown_request
    def close(error):
        g.db.close()

    return app.test_client()
