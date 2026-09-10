"""Process identity fixtures and complete row/schema snapshots, in temporary DBs."""

from __future__ import annotations

import pytest

from core.infrastructure.migration_state import get_schema_version, set_schema_version
from core.infrastructure.migrations import v22
from core.infrastructure.workbench_process_schema import process_objects
from tests.workbench.identity_metadata_support import (
    business_snapshot,
    insert_row,
    schema_snapshot,
    seed_resources,
    table_rows,
)
from tests.workbench.plan_identity_support import legacy_schema, load_v24_schema
from tests.workbench.process_workflow_support import remove_workflow

PROCESS_CASES = {
    "template_operation": ("PartOperations", "id", 21),
    "template_external_group": ("ExternalGroups", "group_id", "EG1"),
}


def stored_process_state(conn):
    return schema_snapshot(conn), business_snapshot(conn), {
        table: table_rows(conn, table) for table in ("WorkbenchEntityRefs", "WorkbenchCommandReceipts")
    }


def legacy_process_rows(conn):
    load_v24_schema(conn)
    legacy_schema(conn)
    remove_workflow(conn)
    for name in process_objects():
        conn.execute(f'DROP TRIGGER IF EXISTS "{name}"')
    set_schema_version(conn, 21)
    seed_resources(conn, relations=True)
    insert_row(conn, "Parts", {"part_no": "P2", "part_name": "second"})
    insert_row(conn, "PartOperations", {"id": 22, "part_no": "P1", "seq": 2,
               "op_type_name": "zero-hours", "source": "internal", "setup_hours": 0, "unit_hours": 0})
    insert_row(conn, "PartOperations", {"id": 23, "part_no": "P1", "seq": 3,
               "op_type_name": "unknown-hours", "source": "legacy", "setup_hours": None, "unit_hours": None})
    conn.commit()
    assert get_schema_version(conn) == 21
    return conn


@pytest.fixture(name="process_conn", params=("legacy", "fresh"))
def process_database(request, schema_conn):
    if request.param == "legacy":
        schema_conn = request.getfixturevalue("mem_conn")
        legacy_process_rows(schema_conn)
        v22.run(schema_conn)
    else:
        v22.run(schema_conn)
        seed_resources(schema_conn, relations=True)
        insert_row(schema_conn, "Parts", {"part_no": "P2", "part_name": "second"})
        schema_conn.commit()
    return schema_conn


def process_row(conn, kind, key=None):
    table, column, default = PROCESS_CASES[kind]
    row = conn.execute(f'SELECT * FROM "{table}" WHERE "{column}"=?', (default if key is None else key,)).fetchone()
    return dict(row)
