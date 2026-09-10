"""Exclusive hours-file fixtures and full-storage preservation oracles."""

import pytest

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_calibration_adoption_schema import install
from core.services.process.workflow_state import record_confirmation
from core.services.workbench.process_file_codec import decode_process_file, encode_process_file
from core.services.workbench.process_file_hours import ProcessHoursFileOperations
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from tests.workbench.process_query_support import ref_for
from tests.workbench.process_route_support import all_table_snapshot
from tests.workbench.process_workflow_support import confirm_all, seed_workflow


@pytest.fixture(name="hours_conn")
def hours_database(schema_conn):
    conn = schema_conn
    with TransactionManager(conn).transaction():
        install(conn)
    seed_workflow(conn)
    seed_workflow(conn, "P2", catalog=False)
    conn.execute("ALTER TABLE PartOperations ADD COLUMN private_legacy BLOB")
    conn.execute("UPDATE PartOperations SET private_legacy=?,created_at='2001-02-03 04:05:06'", (b"hidden\x00\xff",))
    conn.execute("UPDATE ExternalGroups SET merge_mode='merged',total_days=6.75,end_seq=5 WHERE group_id='P1-G'")
    conn.execute("""INSERT INTO PartOperations(part_no,seq,op_type_name,op_type_id,source,supplier_id,ext_days,
        ext_group_id,setup_hours,unit_hours,private_legacy) VALUES('P1',5,'coating','TE','external','S',4.25,
        'P1-G',3.75,8.125,?)""", (b"member\x00\xff",))
    conn.execute("""INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,remark)
        VALUES('ORPHAN','P1',90,99,'merged',47.5,' untouched orphan ')""")
    conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date) VALUES('OLD','P1','old',3,'2026-10-01')")
    conn.execute("""INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,setup_hours,unit_hours)
        VALUES('OLD-OP','OLD',1,'old','internal',9,8)""")
    op = conn.execute("SELECT id FROM BatchOperations WHERE op_code='OLD-OP'").fetchone()[0]
    conn.execute("INSERT INTO Schedule(op_id,start_time,end_time) VALUES(?,?,?)", (op, "2026-10-01 08:00:00", "2026-10-01 09:00:00"))
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("UPDATE PartOperations SET ext_group_id='missing-group',supplier_id='missing-supplier' WHERE part_no='P1' AND status='deleted'")
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")
    confirm_all(conn, "P1", person="original reviewer")
    confirm_all(conn, "P2")
    return conn


def decoded(*values):
    return [{"row": index + 2, "values": {"business_code": "P1", **row}, "errors": []}
            for index, row in enumerate(values)]


def preview(conn, *values, target_ref=None, fmt=None):
    source = decoded(*values)
    if fmt is not None:
        content = encode_process_file("hours", [row["values"] for row in source], fmt).content
        source = decode_process_file("hours", content, fmt)
    return ProcessHoursFileOperations(conn).preview_rows(source, WorkbenchProcessQueryService(conn).facts(), target_ref)


def apply(conn, rows, *, ack=False, discard=None):
    with TransactionManager(conn).transaction(begin_immediate=True):
        return ProcessHoursFileOperations(conn).apply_rows(rows, discard_group_refs=[] if discard is None else discard,
                                                         confirm_zero_unit_hours=ack)


def op_rows(conn, part_no="P1"):
    return {row["seq"]: dict(row) for row in conn.execute("SELECT * FROM PartOperations WHERE part_no=? ORDER BY seq", (part_no,))}


def groups(conn):
    return {row["group_id"]: dict(row) for row in conn.execute("SELECT * FROM ExternalGroups ORDER BY group_id")}


def reconfirm_source(conn, part_no="P1"):
    with TransactionManager(conn).transaction(begin_immediate=True):
        record_confirmation(conn, part_no, "route")
        record_confirmation(conn, part_no, "source")


def confirmations(conn):
    return {table: tuple(tuple(row) for row in conn.execute("SELECT * FROM " + table + " ORDER BY rowid"))
            for table in ("WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations")}


def snapshot(conn):
    return all_table_snapshot(conn)


def part_ref(conn, code="P1"):
    return ref_for(conn, "part", code)
