"""BL-only fresh current-schema temporary databases and real engine fixtures."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g

from core.infrastructure.database import ensure_schema
from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, current_schema_contract_issues
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.test_run_jobs_support import JobCase
from web.routes.workbench.run_candidates import register_run_candidate_routes

BASE = "/api/workbench/v1/scheduling"
PRIVATE = {"version", "op_id", "candidate_key", "raw", "facts_json", "facts_hash", "artifact_json", "payload_json",
           "machine_id", "operator_id", "supplier_id", "plan_ref", "task_ref", "source_key", "entity_key", "history"}


def connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@pytest.fixture(name="candidate_case")
def candidate_case(tmp_path):
    path = tmp_path / "bl-candidates.sqlite"
    ensure_schema(str(path), schema_path=str(Path(__file__).resolve().parents[2] / "schema.sql"), backup_dir=None)
    conn = connect(path)
    assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == CURRENT_SCHEMA_VERSION
    assert current_schema_contract_issues(conn) == []
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Original lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Original operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Original part')")
    for key, value in default_snapshot_values().items():
        conn.execute("INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
    case = JobCase(conn)
    case.path = path
    case.batch("B1")
    case.op_id = case.operation()
    case.config(algo_mode="greedy", graph_candidate_weight_count=3, time_budget_seconds=60,
                ortools_enabled="no", freeze_window_enabled="no")
    case.app = Flask("bl-candidate-tests")
    with case.app.app_context():
        yield case
    conn.close()


def compute(case, settings=None):
    accepted = case.accept(settings=settings)
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    return result["run_ref"], [row["candidate_ref"] for row in result["candidates"]]


def api(case):
    bp = Blueprint("bl_candidates", __name__)
    register_run_candidate_routes(bp)
    case.app.register_blueprint(bp)
    statements = []

    @case.app.before_request
    def bind():
        g.db = connect(case.path)
        g.db.execute("PRAGMA query_only=ON")
        g.db.set_trace_callback(statements.append)

    @case.app.teardown_request
    def close(error):
        g.db.close()

    return case.app.test_client(), statements


def read(client, path, **query):
    response = client.get(BASE + path, query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    data = response.get_json()
    public(data)
    return data


def public(value):
    if type(value) is dict:
        assert not PRIVATE.intersection(value)
        for child in value.values():
            public(child)
    elif type(value) is list:
        for child in value:
            public(child)


def state(conn):
    return tuple(conn.iterdump())


@contextmanager
def retained(conn):
    before, changes = state(conn), conn.total_changes
    try:
        yield
    finally:
        assert state(conn) == before
        assert conn.total_changes == changes


def corrupt_update(conn, table, sql, args=()):
    """Fixture-only corruption with the permanent schema restored before any read."""
    triggers = list(conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (table,)))
    for row in triggers:
        conn.execute('DROP TRIGGER "' + row[0] + '"')
    conn.execute(sql, args)
    for row in triggers:
        conn.execute(row[1])
    conn.commit()


def edit_artifact(case, ref, edit):
    raw = case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (ref,)).fetchone()[0]
    artifact = json.loads(raw)
    edit(artifact)
    corrupt_update(case.conn, "WorkbenchRunCandidates", "UPDATE WorkbenchRunCandidates SET artifact_json=? WHERE candidate_ref=?",
                   (json.dumps(artifact, ensure_ascii=False), ref))


def edit_capture(case, field, edit):
    assert field in ("facts_json", "execution_json", "normalized_input_json", "baseline_json")
    raw = case.conn.execute("SELECT " + field + " FROM WorkbenchRunJobs").fetchone()[0]
    value = json.loads(raw)
    edit(value)
    encoded = json.dumps(value, ensure_ascii=False)
    sql = "UPDATE WorkbenchRunJobs SET " + field + "=?"
    args = (encoded,)
    if field == "facts_json":
        sql += ", facts_hash=?"
        args += (hashlib.sha256(encoded.encode("utf-8")).hexdigest(),)
    corrupt_update(case.conn, "WorkbenchRunJobs", sql, args)
