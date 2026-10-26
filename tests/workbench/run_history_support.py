"""BQ-only temporary current-schema SQLite fixtures."""

import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from core.infrastructure.database import ensure_schema
from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, current_schema_contract_issues
from core.infrastructure.schema_declaration import load_schema_sql
from core.models.schedule_config_runtime_fields import default_snapshot_values
from tests.workbench.run_jobs_support import JobCase

BASE = "/api/workbench/v1/scheduling/runs"
PRIVATE = {"request_key", "input_ref", "facts_json", "facts_hash", "execution_json", "baseline_json", "normalized_input_json",
           "artifact_json", "payload_json", "candidate_key", "source_key", "entity_key", "op_id", "version", "executor_ref"}


def connect(path):
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@pytest.fixture(name="history_case")
def history_case(tmp_path):
    path = tmp_path / "bq-run-history.sqlite"
    ensure_schema(str(path), schema_path=str(Path(__file__).resolve().parents[2] / "schema.sql"), backup_dir=None)
    conn = connect(path)
    assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == CURRENT_SCHEMA_VERSION
    assert current_schema_contract_issues(conn, schema_version=CURRENT_SCHEMA_VERSION, schema_sql=load_schema_sql()) == []
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Original lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Original operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
    for key, value in default_snapshot_values().items():
        conn.execute("INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
    case = JobCase(conn)
    case.path = path
    case.batch("B1")
    case.op_id = case.operation()
    case.config(algo_mode="greedy", graph_candidate_weight_count=3, time_budget_seconds=60,
                ortools_enabled="no", freeze_window_enabled="no")
    case.app = Flask("bq-history")
    with case.app.app_context():
        yield case
    conn.close()


def public(value):
    if type(value) is dict:
        assert not PRIVATE.intersection(value)
        for item in value.values():
            public(item)
    elif type(value) is list:
        for item in value:
            public(item)


def read(client, **query):
    response = client.get(BASE, query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    result = response.get_json()
    public(result)
    return result


def dump(conn):
    return tuple(conn.iterdump())
