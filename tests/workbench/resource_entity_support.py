"""D06 database fixtures and command harness, with independent row oracles."""

from copy import deepcopy
from uuid import uuid4

import pytest

from core.infrastructure.migration_state import ensure_schema_version
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource_catalogs import WorkbenchResourceCatalogService
from core.services.workbench.resource_entities import WorkbenchResourceService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.identity_metadata_support import (
    business_snapshot,
    insert_row,
    schema_snapshot,
    seed_resources,
    table_rows,
)

ENTITY_TABLES = {
    "op_type": ("OpTypes", "op_type_id", "OT1"),
    "machine": ("Machines", "machine_id", "M1"),
    "operator": ("Operators", "operator_id", "O1"),
    "machine_group": ("WorkbenchMachineGroups", "group_id", "G1"),
    "shift_profile": ("WorkbenchShiftProfiles", "profile_id", "SHIFT1"),
}
NEW_TABLES = (
    "WorkbenchMachineGroups", "WorkbenchMachineGroupMembers", "WorkbenchShiftProfiles",
    "WorkbenchShiftPatternDays", "WorkbenchOperatorProfiles", "WorkbenchSupplierOpTypes",
    "WorkbenchSupplierProfiles", "WorkbenchOpTypePolicies",
)
FIXED_FIELDS = {
    "anchor_date": "2026-09-09", "cycle_days": 1,
    "pattern": [{"day_offset": 0, "is_rest": False, "shift_start": "07:15", "shift_end": "15:45"}],
}
ROTATING_FIELDS = {
    "anchor_date": "2026-02-28", "cycle_days": 3,
    "pattern": [
        {"day_offset": 0, "is_rest": False, "shift_start": "06:10", "shift_end": "14:40"},
        {"day_offset": 1, "is_rest": False, "shift_start": "22:25", "shift_end": "06:55"},
        {"day_offset": 2, "is_rest": True, "shift_start": "00:00", "shift_end": "00:00"},
    ],
}


@pytest.fixture(name="resource_conn")
def resource_database(schema_conn):
    ensure_schema_version(schema_conn)
    seed_resources(schema_conn, relations=True)
    for code, category in (("OT2", "internal"), ("EXT", "external")):
        insert_row(schema_conn, "OpTypes", {"op_type_id": code, "name": code, "category": category})
    insert_row(schema_conn, "Operators", {"operator_id": "EMPTY", "name": "empty", "status": "inactive"})
    schema_conn.commit()
    assert all(not table_rows(schema_conn, table) for table in NEW_TABLES)
    return schema_conn


def resource_service(conn, kind):
    service = WorkbenchResourceCatalogService if kind in ("machine_group", "shift_profile") else WorkbenchResourceService
    return service(conn, kind)


def identity_for(conn, kind, code=None):
    return WorkbenchIdentityRepository(conn).find_active(kind, code or ENTITY_TABLES[kind][2])


def resource_row(conn, kind, code=None):
    table, key, default = ENTITY_TABLES[kind]
    row = conn.execute(f'SELECT * FROM "{table}" WHERE "{key}"=?', (code or default,)).fetchone()
    return dict(row) if row else None


def stored_state(conn):
    return (schema_snapshot(conn), business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"),
            table_rows(conn, "WorkbenchCommandReceipts"))


def run_resource(conn, kind, action, payload, *, identity=None, code=None, command=None, key=None,
                 after_apply=None, adapter=None):
    adapter = adapter or resource_service(conn, kind)
    normalized = adapter.normalize_input(action, payload)
    if action != "create" and identity is None:
        identity = identity_for(conn, kind, code)

    def guard():
        assert conn.in_transaction
        if identity is not None:
            adapter.snapshot(identity)
        return identity

    def mutate(checked):
        assert conn.in_transaction
        outcome = adapter.apply(action, normalized, checked)
        assert conn.in_transaction
        if action != "delete":
            current = identity_for(conn, kind, outcome.data["business_code"])
            snapshot = adapter.snapshot(current)
            assert snapshot["record"] == resource_row(conn, kind, outcome.data["business_code"])
        if after_apply is not None:
            after_apply(outcome)
        return outcome

    return (command or WorkbenchCommandService(conn)).execute(
        request_key=key or "resource-test-" + uuid4().hex, action=kind + "." + action,
        context_ref=identity.ref if identity is not None else kind + ".collection",
        normalized_input=normalized, guard=guard, mutate=mutate,
    )


def create_catalog(conn, kind, code=None, fields=None):
    code = code or ENTITY_TABLES[kind][2]
    payload = {"business_code": code, "label": code,
               "fields": deepcopy(FIXED_FIELDS if kind == "shift_profile" and fields is None else fields or {})}
    run_resource(conn, kind, "create", payload)
    return identity_for(conn, kind, code)


def explicit_operator(conn):
    shift = create_catalog(conn, "shift_profile")
    run_resource(conn, "operator", "update", {
        "fields": {"status": "leave"},
        "relationships": {"shift_profile_ref": shift.ref, "skill_refs": [identity_for(conn, "op_type").ref]},
    })
    return resource_service(conn, "operator").snapshot(identity_for(conn, "operator"))


def invalid_entity_inputs():
    for kind in ("op_type", "machine", "operator"):
        for payload in (None, [], True, {"unknown": 1}, {"fields": None}, {"fields": []},
                        {"relationships": None}, {"relationships": []}, {"business_code": "changed"}):
            yield pytest.param(kind, "update", payload, id=kind + "-shape-" + repr(payload))
        for value in (None, "", " \t", True, float("nan"), 1, [], {}):
            yield kind, "update", {"label": value}
            yield kind, "create", {"business_code": value, "label": "name"}
        for value in (True, 1, float("nan"), [], {}):
            yield kind, "update", {"fields": {"remark": value}}
        hidden = ("created_at", "team_id", "op_type_id", "default_hours", "name", "revision", "ref")
        for field in hidden:
            yield kind, "update", {"fields": {field: "forbidden"}}
        for value in (None, "", "unknown", True, float("nan"), [], {}):
            field = "category" if kind == "op_type" else "status"
            yield kind, "update", {"fields": {field: value}}
        yield kind, "delete", {"label": "not allowed"}
    for key, kind in (("skill_refs", "operator"), ("shift_profile_ref", "operator"), ("group_ref", "machine"),
                      ("op_type_ref", "machine")):
        for value in ("", "OT1", "display name", True, float("nan"), {}, 1):
            yield kind, "update", {"relationships": {key: value}}
    for value in (None, [None], [True], ["f" * 48, "f" * 48], ["F" * 48], ["f" * 47], ["f" * 49]):
        yield "operator", "update", {"relationships": {"skill_refs": value}}
    yield "machine", "update", {"relationships": {"team_ref": "f" * 48}}
    yield "operator", "update", {"relationships": {"machine_refs": []}}
