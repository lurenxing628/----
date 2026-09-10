"""Dedicated calibration fixtures; asserted lineage below exists ONLY in tests."""

from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from flask import Blueprint, Flask, g

from core.models.workbench_calibration import CalibrationCandidate, CalibrationLineage, CalibrationQuery
from core.services.workbench.calibration_samples import review_sample
from data.repositories.workbench_calibration_query_repo import WorkbenchCalibrationQueryRepository
from tests.workbench.test_execution_ledger_support import NOW, all_rows
from tests.workbench.test_execution_ledger_support import ledger_case as ledger_fixture
from web.routes.workbench.calibration import register_calibration_routes

BASE = "/api/workbench/v1/calibration"


@pytest.fixture(name="calibration_case")
def calibration_case(ledger_case):
    case = ledger_case
    case.install()
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,unit_hours) VALUES ('P1',1,'T1','Turning','internal',1)")
    case.conn.commit()
    case.template = WorkbenchCalibrationQueryRepository(case.conn).templates(CalibrationQuery())[0]
    return case


def complete_reports(case, unit_hours):
    ids = [case.op_id]
    ids.extend(case.op("CAL-" + str(index), seq=index + 2) for index in range(len(unit_hours) - 1))
    case.plan(2, ids)
    saved = []
    for index, (op_id, hours) in enumerate(zip(ids, unit_hours)):
        values = case.values(10, effective_processing_hours=hours * 10,
            actual_start="2026-09-08T00:00:00", actual_end=(datetime(2026, 9, 9, 10) + timedelta(minutes=index)).isoformat())
        saved.append(case.command("create", case.task(2, op_id), values)["data"]["rows"][0])
    return ids, saved


def reviewed(case, ids, *, lineage=True, template=None):
    template = template or case.template
    refs = [case.ledger.repo.task(case.task(2, op_id))["operation_ref"] for op_id in ids]
    projections = {row.operation_ref: row for row in case.ledger.project_operations(refs)}
    evidence = CalibrationLineage(template.operation_ref, template.revision, "test-asserted-origin") if lineage else None
    return [review_sample(CalibrationCandidate(projections[ref], "P1", "B1", "CAL", "internal", evidence), template=template, as_of=NOW)
            for ref in refs]


def schema_state(conn):
    return [tuple(row) for row in conn.execute("SELECT name,type,sql FROM sqlite_master ORDER BY name")], all_rows(conn)


@contextmanager
def inject_revision_damage(conn):
    """Temporary database only: restore identical DDL before exercising the reader."""
    triggers = list(conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='WorkbenchProductionReportRevisions'"))
    for name, _ in triggers:
        conn.execute('DROP TRIGGER "' + name + '"')
    try:
        yield
    finally:
        for _, sql in triggers:
            conn.execute(sql)
        conn.commit()


@pytest.fixture(name="calibration_api")
def calibration_api(calibration_case, monkeypatch):
    case = calibration_case

    class FrozenClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr("web.routes.workbench.calibration_read_context.datetime", FrozenClock)
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="calibration-isolated-test-secret")
    bp = Blueprint("calibration_test", __name__)
    register_calibration_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def bind_database():
        g.db = case.conn

    case.client = app.test_client()
    return case


def scope_token(case, **query):
    response = case.client.get(BASE, query_string=query)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def assert_failure(response, code, status=None):
    assert response.status_code == status if status else response.status_code >= 400
    payload = response.get_json()
    assert payload["ok"] is False and payload["committed"] is False
    assert payload["error"]["code"] == code, payload


def query_only(case):
    case.conn.commit()
    case.before_read = schema_state(case.conn)
    case.statements = []
    case.conn.set_trace_callback(case.statements.append)
    case.conn.execute("PRAGMA query_only=ON")


def assert_no_writes(case):
    assert schema_state(case.conn) == case.before_read
    assert not any(sql.lstrip().split()[0].upper() in {"CREATE", "INSERT", "UPDATE", "DELETE", "REPLACE", "ALTER", "DROP"}
                   for sql in case.statements)
