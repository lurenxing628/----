"""D06 database fixtures and command harness, with independent row oracles."""

from copy import deepcopy
from uuid import uuid4

import pytest

from core.infrastructure.migration_state import ensure_schema_version
from core.infrastructure.schema_declaration import load_schema_sql
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests._support.sqlite_snapshot import table_rows
from tests.workbench.identity_metadata_support import insert_row, seed_resources

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


@pytest.fixture(name="resource_conn")
def resource_database(schema_conn):
    ensure_schema_version(schema_conn, schema_sql=load_schema_sql())
    seed_resources(schema_conn, relations=True)
    for code, category in (("OT2", "internal"), ("EXT", "external")):
        insert_row(schema_conn, "OpTypes", {"op_type_id": code, "name": code, "category": category})
    insert_row(schema_conn, "Operators", {"operator_id": "EMPTY", "name": "empty", "status": "inactive"})
    assert all(not table_rows(schema_conn, table) for table in NEW_TABLES)
    # 写入口只产出“启用”或“带登记原因的停用”：种子里停用的供应商和人员补上停用原因。
    insert_row(schema_conn, "WorkbenchSupplierProfiles", {"supplier_id": "S1", "inactive_reason": "disabled"})
    insert_row(schema_conn, "WorkbenchOperatorProfiles", {"operator_id": "EMPTY", "skills_declared": 0,
                                                          "inactive_reason": "disabled"})
    schema_conn.commit()
    return schema_conn


def identity_for(conn, kind, code=None):
    return WorkbenchIdentityRepository(conn).find_active(kind, code or ENTITY_TABLES[kind][2])


def resource_row(conn, kind, code=None):
    table, key, default = ENTITY_TABLES[kind]
    row = conn.execute(f'SELECT * FROM "{table}" WHERE "{key}"=?', (code or default,)).fetchone()
    return dict(row) if row else None


def run_resource(conn, kind, action, payload, *, code=None):
    reader = WorkbenchResourceQueryService(conn, kind)
    normalized = reader.domain.normalize_input(action, payload)
    identity = None
    if action != "create":
        identity = identity_for(conn, kind, code)
        assert identity is not None

    def guard():
        assert conn.in_transaction
        preparation = reader.preparation_for(action, normalized, ref=identity.ref if identity is not None else None)
        checked = (None if identity is None else
                   preparation.state(kind, preparation.current(kind, identity).entity_key))
        return reader.domain.prepare(action, normalized, checked, preparation)

    def mutate(change):
        assert conn.in_transaction
        outcome = reader.domain.apply_prepared(change)
        assert conn.in_transaction
        if action != "delete":
            current = identity_for(conn, kind, outcome.data["business_code"])
            assert current is not None
            snapshot = WorkbenchResourceQueryService(conn, kind).current_with_identity(current)
            assert snapshot["record"] == resource_row(conn, kind, outcome.data["business_code"])
        return outcome

    return WorkbenchCommandService(conn).execute(
        request_key="resource-test-" + uuid4().hex, action=kind + "." + action,
        context_ref=identity.ref if identity is not None else kind + ".collection",
        normalized_input=normalized, guard=guard, mutate=mutate,
    )


def create_catalog(conn, kind, code=None, fields=None):
    code = code or ENTITY_TABLES[kind][2]
    payload = {"business_code": code, "label": code,
               "fields": deepcopy(FIXED_FIELDS if kind == "shift_profile" and fields is None else fields or {})}
    run_resource(conn, kind, "create", payload)
    identity = identity_for(conn, kind, code)
    assert identity is not None
    return identity
