"""Deterministic SQLite work bounds, independent of host timing/load."""

import pytest

from core.infrastructure.migrations import v23
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_process_schema import (
    install_process,
    process_objects,
    workbench_process_contract_issues,
)
from tests.workbench.identity_metadata_support import business_snapshot, schema_snapshot, table_rows


def test_template_identity_updates_use_indexed_keys_in_large_catalog(schema_conn, record_property):
    conn = schema_conn
    for name in process_objects():
        conn.execute('DROP TRIGGER "' + name + '"')
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('identity-scale','identity scale')")
    conn.executemany("INSERT INTO PartOperations(part_no,seq,op_type_name) VALUES ('identity-scale',?,'车削')",
                     [(index,) for index in range(1, 10001)])
    conn.commit()
    with TransactionManager(conn).transaction():
        install_process(conn)
    rows = conn.execute("SELECT id FROM PartOperations WHERE part_no='identity-scale' ORDER BY seq LIMIT 20").fetchall()
    ticks = []

    def progress():
        ticks.append(1)
        return 0

    conn.set_progress_handler(progress, 1000)
    try:
        for row in rows:
            conn.execute("UPDATE PartOperations SET unit_hours=.125 WHERE id=?", (row[0],))
        conn.commit()
    finally:
        conn.set_progress_handler(None, 0)
    steps = len(ticks) * 1000
    record_property("sqlite_steps_20_updates_10000_templates", steps)
    assert steps < 25000, "Twenty keyed updates must not scan every template reference"
    assert conn.execute("SELECT COUNT(*) FROM WorkbenchEntityRefs WHERE kind='template_operation' AND active=1").fetchone()[0] == 10000
    assert conn.execute("SELECT COUNT(*) FROM PartOperations WHERE unit_hours=.125").fetchone()[0] == 20


def test_known_v22_trigger_upgrade_preserves_all_rows_and_references(schema_conn):
    conn = schema_conn
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('old-v22','原零件')")
    conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,unit_hours) VALUES ('old-v22',10,'原工序',.125)")
    for name, sql in process_objects(legacy=True).items():
        conn.execute('DROP TRIGGER "' + name + '"')
        conn.execute(sql)
    conn.commit()
    rows, refs, changes = business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"), conn.total_changes
    assert workbench_process_contract_issues(conn)
    v23.run(conn)
    assert not workbench_process_contract_issues(conn)
    assert business_snapshot(conn) == rows and table_rows(conn, "WorkbenchEntityRefs") == refs
    assert conn.total_changes == changes
    final = schema_snapshot(conn)
    v23.run(conn)
    assert schema_snapshot(conn) == final and conn.total_changes == changes


@pytest.mark.parametrize("damage", ["missing", "unknown_ddl"])
def test_unknown_trigger_damage_is_not_silently_repaired(schema_conn, damage):
    conn = schema_conn
    name = "wb_ref_template_operation_update"
    conn.execute('DROP TRIGGER "' + name + '"')
    if damage == "unknown_ddl":
        conn.execute('CREATE TRIGGER "' + name + '" AFTER UPDATE ON PartOperations BEGIN SELECT 1; END')
    conn.commit()
    before = schema_snapshot(conn), business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs")
    with pytest.raises(RuntimeError, match="missing or unrecognized"):
        v23.run(conn)
    assert (schema_snapshot(conn), business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs")) == before
