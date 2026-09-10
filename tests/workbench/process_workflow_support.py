"""Temporary process facts with explicit zero hours, groups and retained old rows."""

from __future__ import annotations

import pytest

from core.infrastructure.migration_state import get_schema_version, set_schema_version
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_process_schema import install_process, process_objects
from core.infrastructure.workbench_process_workflow_schema import WORKFLOW_TABLES
from core.services.process.workflow_state import record_confirmation
from tests._support.sqlite_snapshot import stored_state as stored_state
from tests.workbench.identity_metadata_support import business_snapshot, insert_row, schema_snapshot, table_rows
from tests.workbench.plan_identity_support import load_v23_schema


def seed_workflow(conn, part_no="P1", *, catalog=True):
    if catalog:
        insert_row(conn, "OpTypes", dict(op_type_id="TI", name="turning", category="internal"))
        insert_row(conn, "OpTypes", dict(op_type_id="TE", name="coating", category="external"))
        insert_row(conn, "Suppliers", dict(supplier_id="S", name="supplier", op_type_id="TE", status="active"))
    insert_row(conn, "Parts", dict(part_no=part_no, part_name="part", route_raw="turning,turning,coating",
                                   route_parsed="yes", remark="retained"))
    for seq in (1, 2):
        insert_row(conn, "PartOperations", dict(part_no=part_no, seq=seq, op_type_id="TI", op_type_name="turning",
                                               source="internal", setup_hours=0, unit_hours=0))
    insert_row(conn, "PartOperations", dict(part_no=part_no, seq=3, op_type_id="TE", op_type_name="coating",
                                           source="external", supplier_id="S", ext_days=2.5,
                                           ext_group_id=part_no + "-G", setup_hours=0.75, unit_hours=1.25))
    insert_row(conn, "ExternalGroups", dict(group_id=part_no + "-G", part_no=part_no, start_seq=3, end_seq=3,
                                           merge_mode="separate", supplier_id="S", remark="retained-hidden-rule"))
    insert_row(conn, "PartOperations", dict(part_no=part_no, seq=4, op_type_name="deleted", source="unknown",
                                           setup_hours=None, unit_hours=None, status="deleted"))
    conn.commit()


@pytest.fixture(name="workflow_conn")
def workflow_database(schema_conn):
    seed_workflow(schema_conn)
    return schema_conn


def confirm_all(conn, part_no="P1", person=None):
    with TransactionManager(conn).transaction():
        for stage in ("route", "source", "hours"):
            result = record_confirmation(conn, part_no, stage, person)
    assert result["ready"]
    return result


def business_rows(conn):
    return {table: rows for table, rows in business_snapshot(conn).items() if table not in WORKFLOW_TABLES}


def remove_workflow(conn):
    conn.execute("DROP INDEX idx_wb_process_confirmation_operation")
    for name in reversed(WORKFLOW_TABLES):
        conn.execute('DROP TABLE "' + name + '"')
    conn.commit()


@pytest.fixture(name="v22_workflow_conn")
def v22_workflow_database(mem_conn):
    conn = load_v23_schema(mem_conn)
    seed_workflow(conn)
    remove_workflow(conn)
    set_schema_version(conn, 22)
    conn.commit()
    assert get_schema_version(conn) == 22
    return conn


def seed_large_workflow(conn, count=10000, *, external=False):
    """Use the tested v22 identity backfill, avoiding quadratic fixture trigger work."""
    for name in process_objects():
        if name.startswith("wb_ref_template_operation_"):
            conn.execute('DROP TRIGGER "' + name + '"')
    if external:
        conn.execute("UPDATE ExternalGroups SET end_seq=? WHERE group_id='P1-G'", (count + 1,))
    values = ("TE", "coating", "external", "S", "P1-G", 2.5) if external else ("TI", "turning", "internal", None, None, None)
    conn.executemany("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_group_id,ext_days,
        setup_hours,unit_hours) VALUES('P1',?,?,?,?,?,?,?,0,1)""", [(seq,) + values for seq in range(5, count + 2)])
    with TransactionManager(conn).transaction():
        install_process(conn)
    conn.commit()
