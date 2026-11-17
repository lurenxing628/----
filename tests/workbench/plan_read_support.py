"""Real SQLite and isolated Flask read routes; no production app startup or paths."""

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g

from core.models.workbench_plan_reference import WorkbenchPlanLocator
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests._support.sqlite_connection import open_test_connection
from tests.workbench.plan_catalog_support import (
    ensure_history_head,
    history,
    insert_schedule_row,
    insert_schedule_rows,
    seed_operation,
)
from web.routes.workbench.plan_reads import register_plan_read_routes
from web.runtime_host import install_wall_clock

BASE = "/api/workbench/v1/plans"
NIGHT_START = "2026-09-09T22:30:00"
NIGHT_END = "2026-09-10T06:30:00"
PRIVATE_FIELDS = {"schedule_id", "op_id", "candidate_id", "candidate_key", "scenario_id", "source_table",
                  "source_row_id", "before_version", "after_scenario_id", "locator", "seek", "revision",
                  "machine_id", "operator_id", "supplier_id", "entity_key", "fingerprint", "row_ref"}


def seed_plans(conn):
    op = seed_operation(conn)
    conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('PRIVATE-M1','Machine one')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('PRIVATE-O1','Operator one')")
    history(conn, 1, op_id=op)
    history(conn, 2, op_id=op)
    ensure_history_head(conn, 3, baseline_version=None, baseline_ref=None)
    insert_schedule_row(
        conn,
        3,
        op,
        NIGHT_START,
        NIGHT_END,
        machine_id="PRIVATE-M1",
        operator_id="PRIVATE-O1",
    )
    conn.commit()
    return op


def add_tasks(conn, count, *, start="2026-09-11T22:00:00", end="2026-09-12T02:00:00"):
    first = conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM BatchOperations").fetchone()[0]
    ids = list(range(first, first + count))
    conn.executemany("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) VALUES (?,?,'CAT-B',?,'Extra op')",
                     ((op, "EXTRA-" + str(op), op) for op in ids))
    insert_schedule_rows(
        conn,
        3,
        ({"op_id": op, "start_time": start, "end_time": end} for op in ids),
    )


class PlanReadApi:
    def __init__(self, app, path):
        self.app, self.path = app, path
        self.client = app.test_client()
        self.statements = []

    @contextmanager
    def db(self):
        conn = open_test_connection(self.path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def ref(self, version=3, role="adopted"):
        with self.db() as conn:
            return WorkbenchPlanIdentityRepository(conn).get_plan_ref(WorkbenchPlanLocator(version, role))

    def get(self, suffix="", **query):
        return self.client.get(BASE + suffix, query_string=query)

    def read(self, suffix="", **query):
        response = self.get(suffix, **query)
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.headers["Cache-Control"] == "no-store"
        payload = response.get_json()
        assert payload["meta"]["source"] == "production"
        assert payload["meta"]["time_basis"] == "factory_local"
        assert_no_private_facts(payload)
        return payload

    def state(self):
        with self.db() as conn:
            return list(conn.iterdump())


def make_api(path):
    app = Flask("plan-read-test")
    install_wall_clock(app, datetime.now)
    app.config["TESTING"] = True
    bp = Blueprint("plan_read_test", __name__)
    register_plan_read_routes(bp)
    app.register_blueprint(bp)
    api = PlanReadApi(app, path)

    @app.before_request
    def database():
        g.db = open_test_connection(path)
        g.db.execute("PRAGMA query_only = ON")
        g.db.set_trace_callback(api.statements.append)

    @app.teardown_request
    def close_database(exc):
        g.db.close()

    return api


@pytest.fixture(name="plan_api")
def plan_read_api(tmp_path):
    path = tmp_path / "plan-reads.db"
    conn = open_test_connection(path)
    try:
        conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
        conn.commit()
        seed_plans(conn)
    finally:
        conn.close()
    return make_api(path)


def assert_error(response, code, status=409):
    assert response.status_code == status, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] is False and payload["committed"] is False
    assert payload["error"]["code"] == code
    assert_no_private_facts(payload)
    return payload


def assert_no_private_facts(value):
    if isinstance(value, dict):
        assert not PRIVATE_FIELDS.intersection(value)
        for key, item in value.items():
            if key == "business_code" and set(value) == {"kind", "ref", "business_code", "label"}:
                assert value["kind"] in {"machine", "operator", "supplier"}
                assert type(item) is str and item.strip()
                continue
            assert_no_private_facts(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_private_facts(item)
    elif isinstance(value, str):
        assert "PRIVATE-" not in value
