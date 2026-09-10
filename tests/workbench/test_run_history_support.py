"""BQ-only temporary current-schema SQLite fixtures; synthetic ledgers are labeled as such."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g

from core.infrastructure.database import ensure_schema
from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, current_schema_contract_issues
from core.models.workbench_command import WorkbenchCommandOutcome, canonical_json
from core.models.workbench_run_job import new_run_ref
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from data.repositories.workbench_run_result_repo import WorkbenchRunResultRepository
from tests.workbench.test_run_jobs_support import JobCase
from web.routes.workbench.run_history import register_run_history_routes

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
    assert current_schema_contract_issues(conn) == []
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


def seed(case, state="queued", *, accepted="2026-09-10T12:00:00", counts=(1,), stage=None, settings=None):
    """Build a synthetic but internally consistent durable ledger using real repositories."""
    conn, repo, key = case.conn, WorkbenchRunRepository(case.conn), new_run_ref()
    ref = repo.insert(request_key=key, input_ref="private-input-" + key, settings=settings if settings is not None else case.settings(),
        facts_hash="a" * 64, facts_json='{"private":true}', projections=[], baseline={}, now=accepted)
    WorkbenchCommandRepository(conn).insert(request_key=key, receipt_ref=new_run_ref()[:32], action="scheduling.run",
        context_ref="private-input-" + key, input_hash="b" * 64, outcome=WorkbenchCommandOutcome("committed", {"run_ref": ref}))
    when = datetime.fromisoformat(accepted)
    if state != "queued":
        repo.claim(ref, new_run_ref(), (when + timedelta(minutes=1)).isoformat())
    if state in ("complete", "partial", "failed", "interrupted"):
        candidates = []
        if state in ("complete", "partial"):
            op = conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1 LIMIT 1").fetchone()[0]
            for index, count in enumerate(counts):
                assert count in (0, 1)
                candidates.append({"candidate_ref": new_run_ref(), "key": "synthetic-" + str(index), "sequence": index,
                    "status": "completed" if count else "skipped", "artifact": {"private": "not for directory"},
                    "tasks": [{"row_ref": new_run_ref(), "operation_ref": op, "payload": {"private": "do not decode"}}] if count else []})
        WorkbenchRunResultRepository(conn).save(ref, candidates)
        result = {"state": state, "result_persisted": bool(candidates), "error": None,
                  "candidates": [{"candidate_ref": item["candidate_ref"], "status": item["status"],
                                  "task_count": len(item["tasks"]), "label": "Synthetic candidate"} for item in candidates]}
        repo.finish(ref, state, result, (when + timedelta(minutes=2)).isoformat())
    if stage is not None:
        assert stage == "awaiting_reconciliation"
        repo.awaiting_reconciliation(ref)
    conn.commit()
    return ref


def api(case, authorizer=None):
    bp = Blueprint("bq_history", __name__)
    register_run_history_routes(bp)
    case.app.register_blueprint(bp)
    statements = []

    @case.app.before_request
    def bind():
        g.db = connect(case.path)
        g.db.execute("PRAGMA query_only=ON")
        g.db.set_trace_callback(statements.append)
        if authorizer is not None:
            g.db.set_authorizer(authorizer)

    @case.app.teardown_request
    def close(error):
        g.db.close()

    return case.app.test_client(), statements


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


def corrupt(conn, table, sql, args=()):
    triggers = list(conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (table,)))
    for row in triggers:
        conn.execute('DROP TRIGGER "' + row[0] + '"')
    conn.execute(sql, args)
    for row in triggers:
        conn.execute(row[1])
    conn.commit()


def edit_receipt(case, ref, edit):
    receipt = json.loads(case.conn.execute("SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?", (ref,)).fetchone()[0])
    edit(receipt)
    corrupt(case.conn, "WorkbenchRunReceipts", "UPDATE WorkbenchRunReceipts SET result_json=? WHERE run_ref=?",
            (canonical_json(receipt), ref))
