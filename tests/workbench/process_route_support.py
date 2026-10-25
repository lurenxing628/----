"""Temporary route fixtures and independent all-table/read-query oracles."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from core.services.workbench.process.route_facts import ProcessRouteFacts
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository


def load_route_reference_facts(conn):
    repo = WorkbenchProcessQueryRepository(conn)
    return ProcessRouteFacts({"parts": repo.parts(), "operations": repo.operations(), "groups": repo.groups(),
                              "references": repo.references(), "identities": repo.identities()})


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
