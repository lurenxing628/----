"""Interpret acceptance-time facts only; current replacement entities are irrelevant."""

import hashlib
import sqlite3

from core.models.workbench_run_candidate import reference

from .run_candidate_values import corrupt, gap, stored_json

_TABLES = {"BatchOperations": "id", "Batches": "batch_id", "Parts": "part_no",
           "Machines": "machine_id", "Operators": "operator_id", "Suppliers": "supplier_id"}


def _columns(sql, name):
    if type(sql) is not str:
        corrupt()
    # SQLite parses its own archived DDL in an empty isolated database. The
    # authorizer permits only this table's schema, never data, attached DBs or SQL functions.
    conn = sqlite3.connect(":memory:")

    def authorize(action, first, second, database, source):
        if action == sqlite3.SQLITE_CREATE_TABLE and first in (name, "sqlite_sequence") and database == "main":
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_CREATE_INDEX and second == name and first.startswith("sqlite_autoindex_"):
            return sqlite3.SQLITE_OK
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_READ) and first == "sqlite_master":
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ and first == name:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_REINDEX and first.startswith("sqlite_autoindex_"):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION and second in ("length", "typeof", "glob"):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_PRAGMA and first == "table_info" and second == name:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    try:
        conn.set_authorizer(authorize)
        conn.execute(sql)
        return [row[1] for row in conn.execute('PRAGMA table_info("' + name + '")')]
    except (sqlite3.Error, sqlite3.Warning):
        corrupt()
    finally:
        conn.close()


def _table(facts, name):
    schema, tables = facts.get("schema"), facts.get("tables")
    if type(schema) is not list or type(tables) is not dict:
        corrupt()
    if name not in tables:
        return None
    ddl = [row[3] for row in schema if type(row) is list and len(row) == 4 and row[0] == "table" and row[1] == name]
    if len(ddl) != 1 or type(tables[name]) is not list:
        corrupt()
    columns = _columns(ddl[0], name)
    if not columns:
        corrupt()
    result = []
    for row in tables[name]:
        if type(row) is not list or len(row) != len(columns):
            corrupt()
        result.append(dict(zip(columns, row)))
    return result


def _index(rows, key):
    result = {}
    for row in rows or []:
        if type(row) is not dict:
            corrupt()
        value = row.get(key)
        if type(value) not in (int, str) or value in result:
            corrupt()
        result[value] = row
    return result


def _entity_refs(facts):
    result = {}
    for row in _table(facts, "WorkbenchEntityRefs") or []:
        if row.get("active") != 1:
            continue
        key = (row.get("kind"), row.get("entity_key"))
        if any(type(item) is not str for item in key) or key in result:
            corrupt()
        result[key] = reference(row.get("ref"), stored=True)
    return result


def _operation_refs(facts):
    result = {}
    for row in _table(facts, "WorkbenchPlanSourceRefs") or []:
        if row.get("kind") != "operation" or row.get("active") != 1:
            continue
        ref, key = reference(row.get("ref"), stored=True), row.get("source_key")
        if type(key) is not str or not key.isdigit() or str(int(key)) != key or ref in result:
            corrupt()
        result[ref] = int(key)
    return result


class GenerationFacts:
    def __init__(self, capture):
        value = capture["facts_text"]
        if type(value) is not str or hashlib.sha256(value.encode("utf-8")).hexdigest() != capture["facts_hash"]:
            corrupt()
        facts = stored_json(value)
        self.tables = {name: _index(_table(facts, name), key) for name, key in _TABLES.items()}
        self.entity_refs = _entity_refs(facts)
        self.operations = _operation_refs(facts)
        self.execution = _index(capture["execution"], "operation_ref")
        for ref in self.execution:
            reference(ref, stored=True)

    def operation(self, ref, payload, gaps):
        key = self.operations.get(ref)
        if key is None:
            gaps.append(gap("operation", "source_missing"))
            return {}
        if payload is not None and (type(payload.get("op_id")) is not int or payload["op_id"] != key):
            corrupt()
        row = self.tables["BatchOperations"].get(key)
        if row is None:
            gaps.append(gap("operation", "source_missing"))
        return row or {}

    def related(self, name, key, field, gaps):
        if type(key) not in (str, int):
            gaps.append(gap(field, "source_missing"))
            return {}
        row = self.tables[name].get(key)
        if row is None:
            gaps.append(gap(field, "source_missing"))
        return row or {}
