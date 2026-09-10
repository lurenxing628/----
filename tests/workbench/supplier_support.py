"""Temporary v21 supplier fixtures and independent raw-state oracles."""

from __future__ import annotations

import pytest

from core.infrastructure.migrations import v21
from core.services.process.supplier_service import SupplierService
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.suppliers import WorkbenchSupplierService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository

KEY = "supplier-command-00000001"
CREATE = {"business_code": "SUP2", "label": "New supplier", "fields": {"default_days": 2.5}}


@pytest.fixture(name="supplier_conn")
def supplier_database(schema_conn):
    v21.run(schema_conn)
    schema_conn.executemany("INSERT INTO OpTypes(op_type_id, name, category) VALUES (?, ?, ?)", [
        ("HEAT", "热处理", "external"), ("COAT", "表处理", "external"), ("MILL", "数铣", "internal"),
    ])
    schema_conn.commit()
    SupplierService(schema_conn).create("SUP1", "Legacy supplier", op_type_value="HEAT", default_days=3.5, remark="keep note")
    return schema_conn


def identity_for(conn, code="SUP1", kind="supplier"):
    result = WorkbenchIdentityRepository(conn).find_active(kind, code)
    assert result is not None
    return result


def relationships(conn, *codes):
    return {"op_type_refs": [identity_for(conn, code, "op_type").ref for code in codes]}


def supplier_row(conn, code="SUP1"):
    row = conn.execute("SELECT * FROM Suppliers WHERE supplier_id = ?", (code,)).fetchone()
    return dict(row) if row else None


def stored_state(conn):
    return tuple(conn.iterdump())


def run_supplier(conn, action, payload, *, identity=None, key=KEY, guard=None, command=None):
    adapter = WorkbenchSupplierService(conn)
    normalized = adapter.normalize_input(action, payload)
    if identity is None and action != "create":
        identity = identity_for(conn)
    return (command or WorkbenchCommandService(conn)).execute(
        request_key=key, action="supplier." + action,
        context_ref=identity.ref if identity else "supplier.collection", normalized_input=normalized,
        guard=guard or (lambda: identity), mutate=lambda checked: adapter.apply(action, normalized, checked),
    )


def invalid_payloads():
    for action in ("create", "update", "delete"):
        base = CREATE if action == "create" else {}
        for value in (None, [], (), True, 0, "", {1: "bad"}):
            yield action, value
        for key in ("id", "supplier_id", "op_type_id", "ref", "entity_key", "entity_ref", "revision", "write_token", "default_days"):
            yield action, {**base, key: "bad"}
        if action == "delete":
            for key in ("fields", "relationships", "label"):
                yield action, {key: {}}
            continue
        for value in (True, False, None, "", "1.25", "3 days", [], {}, -1, 0,
                      float("nan"), float("inf"), -float("inf"), 10 ** 400):
            yield action, {**base, "fields": {"default_days": value}}
        for value in (None, "", " ", "ACTIVE", "disabled", "unknown", True, 1, {}, []):
            yield action, {**base, "fields": {"status": value}}
        for value in (True, 1, 2.5, [], {}):
            yield action, {**base, "fields": {"remark": value}}
        for value in (None, [], "", True, 1):
            yield action, {**base, "fields": value}
            yield action, {**base, "relationships": value}
        for value in ({}, {"op_type_id": "HEAT"}, {"op_type_refs": "a" * 48}, {"op_type_refs": ["HEAT"]},
                      {"op_type_refs": [None]}, {"op_type_refs": ["a" * 48, "a" * 48]},
                      {"op_type_refs": [" " + "a" * 48]}, {"op_type_refs": [], "unknown": []}):
            yield action, {**base, "relationships": value}
        for key in ("op_type_id", "supplier_id", "inactive_reason", "created_at", "unknown"):
            yield action, {**base, "fields": {key: "bad"}}
        for key in (("business_code", "label") if action == "create" else ("label",)):
            for value in (None, "", " \t", True, 12, [], {}):
                yield action, {**base, key: value}
    yield "create", {"business_code": "SUP2", "label": "No implicit days"}
    yield "update", {"business_code": "rename forbidden"}
