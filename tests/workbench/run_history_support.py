"""BQ-only temporary current-schema SQLite fixtures."""

import logging
from datetime import datetime
from pathlib import Path

import pytest
from flask import Flask

from core.infrastructure.database import ensure_schema
from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, current_schema_contract_issues
from core.models.schedule_config_runtime_fields import default_snapshot_values
from tests._support.sqlite_connection import open_test_connection
from tests.workbench.run_jobs_support import JobCase
from web.runtime_host import install_wall_clock

BASE = "/api/workbench/v1/scheduling/runs"
PRIVATE = {"request_key", "input_ref", "facts_json", "revisions_json", "conditions_archive_json",
           "execution_json", "baseline_json", "normalized_input_json", "artifact_json", "payload_json",
           "candidate_key", "source_key", "entity_key", "op_id", "version", "executor_ref"}


@pytest.fixture(name="history_case")
def history_case(tmp_path):
    path = tmp_path / "bq-run-history.sqlite"
    ensure_schema(str(path), logging.getLogger(__name__), schema_path=str(Path(__file__).resolve().parents[2] / "schema.sql"))
    conn = open_test_connection(path, timeout=10)
    assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == CURRENT_SCHEMA_VERSION
    assert current_schema_contract_issues(conn, schema_version=CURRENT_SCHEMA_VERSION) == []
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M1','Original lathe')")
    conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Original operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
    for key, value in default_snapshot_values().items():
        conn.execute("INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
    case = JobCase(conn)
    case.path = path
    case.batch("B1")
    case.op_id = case.operation()
    case.config(algo_mode="greedy", time_budget_seconds=60, freeze_window_enabled="no")
    case.app = Flask("bq-history")
    install_wall_clock(case.app, datetime.now)
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
