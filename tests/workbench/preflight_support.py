"""Dedicated fixture: temporary SQLite and Flask, never the production app."""

import sqlite3
from contextlib import contextmanager

import pytest
from flask import Blueprint, Flask, g

from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_contract_issues
from tests.workbench.identity_metadata_support import insert_row, seed_resources
from web.routes.workbench.preflight import register_preflight_routes

BASE = "/api/workbench/v1/scheduling/preflight"


def snapshot(conn):
    return {row[0]: [tuple(item) for item in conn.execute('SELECT * FROM "' + row[0] + '" ORDER BY rowid')]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}


def seed(conn, count=1):
    seed_resources(conn, relations=True)
    conn.execute("UPDATE Machines SET status='active'")
    conn.execute("UPDATE Suppliers SET status='active'")
    for index in range(count):
        code = f"PF-{index:04d}"
        insert_row(conn, "Batches", dict(batch_id=code, part_no="P1", quantity=3, ready_status="yes", status="pending"))
        insert_row(conn, "BatchOperations", dict(op_code=code + "-1", batch_id=code, seq=1, op_type_id="OT1",
                   op_type_name="精加工", source="internal", setup_hours=0, unit_hours=0, machine_id="M1", operator_id="O1"))
    conn.commit()


def create_app(conn):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="preflight-test-only")
    bp = Blueprint("workbench", __name__)
    register_preflight_routes(bp)
    from web.routes.workbench.batches import register_batch_routes

    register_batch_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def isolated_connection():
        g.db = conn

    return app


@pytest.fixture(name="pf")
def pf(schema_conn):
    assert execution_ledger_contract_issues(schema_conn) == []
    seed(schema_conn)
    client = create_app(schema_conn).test_client()
    client.conn = schema_conn
    return client


def ref_for(conn, code="PF-0000"):
    return conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key=? AND active=1", (code,)).fetchone()[0]


def payload(client, **patch):
    return {"batch_refs": [ref_for(client.conn)], "start_date": "2026-09-09", "end_date": "2026-09-09",
            "ready_check": True, "missing_resource_policy": "auto_assign", "completed_policy": "preserve_actuals", **patch}


@contextmanager
def read_only_snapshot(conn):
    before = snapshot(conn)
    schema = [tuple(row) for row in conn.execute("SELECT * FROM sqlite_master ORDER BY name")]
    changes = conn.total_changes
    query_only = conn.execute("PRAGMA query_only").fetchone()[0]
    conn.execute("PRAGMA query_only=ON")
    try:
        # SQLite 3.35 lazily registers PRAGMA virtual tables via sqlite_master authorization.
        conn.execute("SELECT schema_version FROM pragma_schema_version").fetchall()
        conn.execute("SELECT name FROM pragma_table_info('Schedule')").fetchall()
        conn.set_authorizer(deny_writes)
        yield
    finally:
        conn.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
        conn.execute("PRAGMA query_only=" + str(query_only))
    assert snapshot(conn) == before
    assert [tuple(row) for row in conn.execute("SELECT * FROM sqlite_master ORDER BY name")] == schema
    assert conn.total_changes == changes


def checked(client, **patch):
    with read_only_snapshot(client.conn):
        response = client.post(BASE, json=payload(client, **patch))
    assert response.status_code == 200, response.get_json()
    assert response.headers["Cache-Control"] == "no-store"
    return response.get_json()["data"]


def add_op(conn, seq=2, **patch):
    insert_row(conn, "BatchOperations", dict(op_code=f"PF-0000-{seq}", batch_id="PF-0000", seq=seq,
               op_type_id="OT1", op_type_name="后序", source="internal", setup_hours=0, unit_hours=0.5,
               machine_id="M1", operator_id="O1", **patch))
    conn.commit()


def deny_writes(action, _one, _two, _db, _trigger):
    return sqlite3.SQLITE_DENY if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
            sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_DROP_TABLE) else sqlite3.SQLITE_OK
