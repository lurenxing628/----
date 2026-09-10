"""Real SQLite and isolated Flask read routes; no production app startup or paths."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g

from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.services.workbench import plan_queries
from data.repositories import schedule_time_sql
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.plan_catalog_support import candidate, history, scenario, seed_operation, selection
from web.routes.workbench.plan_reads import register_plan_read_routes

BASE = "/api/workbench/v1/plans"
NIGHT_START = "2026-09-09T22:30:00"
NIGHT_END = "2026-09-10T06:30:00"
PRIVATE_FIELDS = {"schedule_id", "op_id", "candidate_id", "candidate_key", "scenario_id", "source_table",
                  "source_row_id", "before_version", "after_scenario_id", "locator", "seek", "revision",
                  "machine_id", "operator_id", "supplier_id", "entity_key", "fingerprint", "row_ref"}


def connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def seed_plans(conn):
    op = seed_operation(conn)
    conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('PRIVATE-M1','Machine one')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('PRIVATE-O1','Operator one')")
    for version in (1, 2, 3):
        history(conn, version, op_id=op)
    adopted = candidate(conn, 3, "adopted", source="schedule")
    selection(conn, 3, "baseline_best", adopted)
    candidate(conn, 3, "critical_best", op_id=op)
    for key, status in (("PRIVATE-ACTIVE", "active"), ("PRIVATE-EXPIRED", "expired"), ("PRIVATE-PUBLISHED", "published")):
        scenario(conn, key, 3, op_id=op, status=status, candidate_id=adopted, candidate_key="adopted")
        conn.execute("UPDATE ScheduleAdjustmentScenario SET scenario_name=? WHERE scenario_id=?", (status + " display", key))
    conn.execute("UPDATE Schedule SET start_time=?,end_time=?,machine_id='PRIVATE-M1',operator_id='PRIVATE-O1' WHERE version=3",
                 (NIGHT_START, NIGHT_END))
    conn.execute("UPDATE ScheduleCandidateRows SET start_time='2026-09-11 01:00:00',end_time='2026-09-11 03:00:00'")
    conn.execute("UPDATE ScheduleAdjustmentScenarioRow SET start_time='2026-09-12 23:00:00',end_time='2026-09-13 02:00:00'")
    conn.commit()
    return op


def add_tasks(conn, count, *, start="2026-09-11 22:00:00", end="2026-09-12 02:00:00"):
    first = conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM BatchOperations").fetchone()[0]
    ids = range(first, first + count)
    conn.executemany("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) VALUES (?,?,'CAT-B',?,'Extra op')",
                     ((op, "EXTRA-" + str(op), op) for op in ids))
    conn.executemany("INSERT INTO Schedule(version,op_id,start_time,end_time) VALUES (3,?,?,?)",
                     ((op, start, end) for op in ids))


def grow_catalog_source(conn, source):
    """Three rows in exactly one source, using timestamps the parser must not touch."""
    first = conn.execute("SELECT MAX(id)+1 FROM BatchOperations").fetchone()[0]
    ids = (first, first + 1)
    conn.executemany("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) VALUES (?,?,'CAT-B',?,'Capacity op')",
                     ((op, "CAP-" + str(op), op) for op in ids))
    start, end = "2077-07-07 22:00:00", "2077-07-08 06:00:00"
    if source == "official":
        conn.execute("UPDATE Schedule SET start_time=?,end_time=? WHERE version=3", (start, end))
        conn.executemany("INSERT INTO Schedule(version,op_id,start_time,end_time) VALUES (3,?,?,?)",
                         ((op, start, end) for op in ids))
    elif source == "candidate":
        candidate_id = conn.execute("SELECT candidate_id FROM ScheduleCandidateSelection WHERE version=3 AND role='critical_best'").fetchone()[0]
        conn.execute("UPDATE ScheduleCandidateRows SET start_time=?,end_time=? WHERE candidate_id=?", (start, end, candidate_id))
        conn.executemany("INSERT INTO ScheduleCandidateRows(version,candidate_id,op_id,start_time,end_time) VALUES (3,?,?,?,?)",
                         ((candidate_id, op, start, end) for op in ids))
    elif source == "scenario":
        conn.execute("UPDATE ScheduleAdjustmentScenarioRow SET start_time=?,end_time=? WHERE scenario_id='PRIVATE-ACTIVE'", (start, end))
        conn.executemany("INSERT INTO ScheduleAdjustmentScenarioRow(scenario_id,source_table,op_id,start_time,end_time) "
                         "VALUES ('PRIVATE-ACTIVE','schedule',?,?,?)", ((op, start, end) for op in ids))
    else:
        raise ValueError("Unknown fixture source")
    return {start, end}


def prepare_capacity_case(api, monkeypatch, source):
    monkeypatch.setattr(plan_queries, "MAX_PLAN_TASKS", 2)
    with api.db() as conn:
        blocked_times = grow_catalog_source(conn, source)
        scenario(conn, "Z-SMALL", 2, op_id=1)
    parse = schedule_time_sql.parse_dt_for_sql

    def guarded(value):
        assert value not in blocked_times, "Oversized source must never enter detail time validation"
        return parse(value)

    monkeypatch.setattr(schedule_time_sql, "parse_dt_for_sql", guarded)
    return api.state()


def assert_capacity_blocked(entry):
    assert entry["capabilities"] == {"view": False, "export": False, "edit_draft": False, "adopt": False, "report_actual": False}
    assert entry["completeness"] == "unknown"
    assert entry["is_current_official"] is False
    assert entry["blocked_reasons"][0]["code"] == "plan_capacity_exceeded"


class PlanReadApi:
    def __init__(self, app, path):
        self.app, self.path = app, path
        self.client = app.test_client()
        self.statements = []

    @contextmanager
    def db(self):
        conn = connect(self.path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def ref(self, version=3, role="adopted", scenario_id=None):
        with self.db() as conn:
            return WorkbenchPlanIdentityRepository(conn).get_plan_ref(WorkbenchPlanLocator(version, role, scenario_id))

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
    app.config["TESTING"] = True
    bp = Blueprint("plan_read_test", __name__)
    register_plan_read_routes(bp)
    app.register_blueprint(bp)
    api = PlanReadApi(app, path)

    @app.before_request
    def database():
        g.db = connect(path)
        g.db.execute("PRAGMA query_only = ON")
        g.db.set_trace_callback(api.statements.append)

    @app.teardown_request
    def close_database(exc):
        g.db.close()

    return api


@pytest.fixture(name="plan_api")
def plan_read_api(tmp_path):
    path = tmp_path / "plan-reads.db"
    conn = connect(path)
    try:
        conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
        install_plan_identity(conn)
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
