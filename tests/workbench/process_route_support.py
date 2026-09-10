"""Temporary route fixtures and independent all-table/read-query oracles."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

from core.infrastructure.database import get_connection
from core.infrastructure.migrations import v21
from core.services.workbench.process_route_preview import ProcessRoutePreviewService
from tests.workbench.identity_metadata_support import seed_resources


@pytest.fixture(name="route_conn")
def route_database(schema_conn):
    v21.run(schema_conn)
    seed_resources(schema_conn, relations=True)
    schema_conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,?)", [
        ("MILL", "数铣", "internal"), ("HEAT", "热处理", "external"), ("COAT", "表处理", "external"),
        ("UNBOUND", "无供应商工种", "external"),
    ])
    schema_conn.executemany("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days,status) VALUES (?,?,?,?,?)", [
        ("SUP-A", "早期供应商", "HEAT", 2.5, "active"),
        ("SUP-Z", "多能力供应商", "HEAT", 3.75, "active"),
        ("SUP-ZZ", "停用供应商", "HEAT", 9, "inactive"),
    ])
    schema_conn.executemany("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES (?,?)", [
        ("SUP-Z", "HEAT"), ("SUP-Z", "COAT"), ("SUP-ZZ", "COAT"),
    ])
    schema_conn.commit()
    return schema_conn


@pytest.fixture(name="typed_route_conn")
def typed_route_database(route_conn):
    conn = get_connection(":memory:")
    route_conn.backup(conn)
    yield conn
    conn.close()


def preview(conn, text):
    return ProcessRoutePreviewService(conn).preview({"mode": "text", "route_raw": text})


def raw_ref(conn, kind, key):
    row = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, key)).fetchone()
    assert row is not None
    return row[0]


def all_table_snapshot(conn):
    schema = tuple(tuple(row) for row in conn.execute("SELECT * FROM sqlite_master ORDER BY type,name"))
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return schema, {name: tuple(tuple(row) for row in conn.execute('SELECT * FROM "' + name.replace('"', '""') + '" ORDER BY rowid'))
                    for name in tables}


@contextmanager
def read_only_probe(conn):
    statements, denied = [], []

    def authorize(action, arg1, arg2, db, trigger):
        if action not in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE):
            denied.append((action, arg1, arg2))
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    conn.set_trace_callback(statements.append)
    conn.set_authorizer(authorize)
    try:
        yield statements
    finally:
        conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        conn.set_trace_callback(None)
    assert denied == []


def alphabetic_name(index):
    # No embedded numeric tokens: distinct names obey the formal route grammar.
    return "规模工种" + "".join(chr(65 + (index // (26 ** offset)) % 26) for offset in (2, 1, 0))


def seed_scale(conn, count):
    conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?, 'external')",
                     [("SCALE-O" + str(i), alphabetic_name(i)) for i in range(count)])
    conn.executemany("INSERT INTO Suppliers(supplier_id,name,default_days) VALUES (?,?,2.25)",
                     [("SCALE-S" + str(i), "规模供应商" + str(i)) for i in range(count)])
    conn.executemany("INSERT INTO WorkbenchSupplierOpTypes VALUES (?,?)",
                     [("SCALE-S" + str(i), "SCALE-O" + str(i)) for i in range(count)])
    conn.commit()
    return [{"seq": i + 1, "op_type_name": alphabetic_name(i)} for i in range(count)]
