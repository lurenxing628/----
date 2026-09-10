"""Temporary material fixtures and independent row preservation oracles."""

from __future__ import annotations

import pytest

from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.materials import WorkbenchMaterialService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.identity_metadata_support import business_snapshot, seed_resources, table_rows

KEY = "material-command-00000001"
CREATE = {"business_code": "MAT2", "label": "new steel", "fields": {}}


@pytest.fixture(name="material_conn")
def material_database(schema_conn):
    seed_resources(schema_conn, relations=True)
    return schema_conn


def identity_for(conn, code="MAT1"):
    identity = WorkbenchIdentityRepository(conn).find_active("material", code)
    assert identity is not None
    return identity


def stored_state(conn):
    return (business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"),
            table_rows(conn, "WorkbenchCommandReceipts"))


def material_row(conn, code="MAT1"):
    row = conn.execute("SELECT * FROM Materials WHERE material_id = ?", (code,)).fetchone()
    return dict(row) if row else None


def run_material(conn, action, payload, *, identity=None, key=KEY, guard=None, command=None):
    adapter = WorkbenchMaterialService(conn)
    normalized = adapter.normalize_input(action, payload)
    if identity is None and action != "create":
        identity = identity_for(conn)
    return (command or WorkbenchCommandService(conn)).execute(
        request_key=key, action="material." + action,
        context_ref=identity.ref if identity else "material.collection",
        normalized_input=normalized, guard=guard or (lambda: identity),
        mutate=lambda checked: adapter.apply(action, normalized, checked),
    )


def invalid_payloads():
    for action in ("create", "update", "delete"):
        for payload in (None, [], "", True, 0, (), {1: "bad"}):
            yield action, payload
        allowed = ("business_code", "label", "fields") if action == "create" else ("label", "fields")
        for key in ("material_id", "id", "entity_key", "ref", "entity_ref", "revision", "write_token",
                    "created_at", "stock_qty", "name", "business_code", "label", "fields"):
            if key not in allowed or action == "delete":
                yield action, {**(CREATE if action == "create" else {}), key: "bad"}
        if action == "delete":
            continue
        base = CREATE if action == "create" else {}
        for value in (None, [], (), "", True, 0):
            yield action, {**base, "fields": value}
        for key in ("material_id", "business_code", "name", "created_at", "ready_status", "low_stock",
                    "minimum_stock", "required_qty", "available_qty", "relationships", "unknown"):
            yield action, {**base, "fields": {key: "bad"}}
        for key in ("spec", "unit", "remark", "status"):
            for value in (True, False, 0, 1.5, [], {}, b"text"):
                yield action, {**base, "fields": {key: value}}
        for value in (None, "", " ", "ACTIVE", "low_stock", "legacy_unknown"):
            yield action, {**base, "fields": {"status": value}}
        for value in (True, False, None, "", "1.25", "NaN", "Infinity", [], {}, -1, -0.1,
                      float("nan"), float("inf"), -float("inf"), 10 ** 400):
            yield action, {**base, "fields": {"stock_qty": value}}
        for key in (("business_code", "label") if action == "create" else ("label",)):
            for value in (None, "", " \t\n", True, False, 123, 1.5, [], {}, b"text"):
                yield action, {**base, key: value}
    yield "create", {"label": "missing code"}
    yield "create", {"business_code": "missing label"}
