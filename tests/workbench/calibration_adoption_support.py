"""CO-only fixtures: frozen schema, real copies/reports and temporary SQLite files."""

import sqlite3

import pytest
from flask import Blueprint, Flask, g

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_calibration_adoption_schema import install
from core.models.workbench_template_lineage import typed_value
from core.services.workbench.calibration_adoption import WorkbenchCalibrationAdoptionService
from tests.workbench.execution_ledger_support import NOW
from tests.workbench.template_lineage_support import completed
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401
from web.routes.workbench.calibration_adoption import register_calibration_adoption_routes
from web.routes.workbench.write_context import issue_write_context, validate_write_context

PREVIEW_INTENT = {"reason": "Adopt verified completed production samples", "declared_operator": "Declared reviewer"}
INTENT = {**PREVIEW_INTENT, "confirm": True}
KEY = "calibration-adoption-request-0001"
BASE = "/api/workbench/v1/calibration/"


def service(conn, **kwargs):
    return WorkbenchCalibrationAdoptionService(conn, **{
        "integration_enabled": True, "clock": lambda: NOW, "actor_provider": lambda: "local-test-operator",
        "context_factory": issue_write_context, "context_validator": validate_write_context, **kwargs})


@pytest.fixture(name="adoption_case")
def adoption_case(lineage_case, monkeypatch):
    case = lineage_case
    with TransactionManager(case.conn).transaction():
        install(case.conn)
    case.conn.execute("PRAGMA foreign_keys=ON")
    case.app = Flask(__name__)
    case.app.config.update(TESTING=True, SECRET_KEY="co-calibration-adoption-only", WORKBENCH_CALIBRATION_ADOPTION_ENABLED=True)
    bp = Blueprint("workbench", __name__)
    register_calibration_adoption_routes(bp)

    # Existing api_endpoint uses this shared target for unknown-commit errors.
    @bp.route("/test-command-receipt/<request_key>")
    def command_receipt(request_key):
        return {"request_key": request_key}

    case.app.register_blueprint(bp)

    @case.app.before_request
    def database():
        g.db = case.conn

    monkeypatch.setattr("web.routes.workbench.calibration_adoption._service", lambda: service(case.conn,
        integration_enabled=case.app.config["WORKBENCH_CALIBRATION_ADOPTION_ENABLED"]))
    case.client = case.app.test_client()
    case.template_ref = case.lineage_repo.template(case.template_id)["template_operation_ref"]
    case.db_path = case.conn.execute("PRAGMA database_list").fetchone()[2]
    with case.app.app_context():
        yield case


@pytest.fixture(name="ready_adoption_case")
def ready_adoption_case(adoption_case):
    case = adoption_case
    case.ids, case.reports = completed(case, [1, 2, 3, 4, 5])
    return case


def token(case, *, ref=None, intent=None):
    preview = service(case.conn).preview(ref or case.template_ref, intent or PREVIEW_INTENT)
    assert preview["validation"]["can_adopt"], preview
    return preview["write_context"]["write_token"]


def connect(case, *, timeout=5):
    conn = sqlite3.connect(case.db_path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def snapshot(conn):
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {table: [tuple(tuple(typed_value(value)) for value in row) for row in
                   conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid')] for table in tables}


def assert_preserved(before, after):
    mutable = {"PartOperations", "WorkbenchEntityRefs", "WorkbenchCalibrationAdoptions",
               "WorkbenchCalibrationQuotaLocks", "WorkbenchCommandReceipts"}
    for table, rows in before.items():
        if table not in mutable:
            assert after[table] == rows, table


def assert_rejected(response, code, status):
    assert response.status_code == status, response.get_json()
    payload = response.get_json()
    assert payload["ok"] is False and payload["committed"] is False
    assert payload["error"]["code"] == code, payload
