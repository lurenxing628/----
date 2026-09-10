"""Route-file-only fixtures and independent whole-storage preservation checks."""

from typing import Any

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_resource_action import ResourceActionPreview
from core.services.workbench.process_file_codec import decode_process_file, encode_process_file
from core.services.workbench.process_file_route import ProcessRouteFileOperations
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from tests.workbench.process_query_support import ref_for, seed_process
from tests.workbench.process_route_support import all_table_snapshot
from tests.workbench.process_workflow_support import confirm_all

PART = "PROC-001"
ROUTE = "10车削20热处理30检验"
HIDDEN = b"\x00route file hidden fact\xff"


@pytest.fixture(name="route_file_conn")
def route_file_database(schema_conn):
    seed_process(schema_conn)
    schema_conn.execute("""INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,remark)
        VALUES ('UNUSED','PROC-001',70,90,'merged',7.75,'unused rule must survive')""")
    for table in ("Parts", "PartOperations", "ExternalGroups", "Batches"):
        schema_conn.execute('ALTER TABLE "' + table + '" ADD COLUMN route_file_private BLOB')
        schema_conn.execute('UPDATE "' + table + '" SET route_file_private=?', (HIDDEN,))
    schema_conn.commit()
    confirm_all(schema_conn, PART, person="fixture owner")
    return schema_conn


def decoded(*values):
    return [{"row": index, "values": value, "errors": []} for index, value in enumerate(values, 2)]


def file_rows(records, fmt="csv"):
    content = encode_process_file("route", records, fmt).content
    return decode_process_file("route", content, fmt)


def review(conn, source, target_ref=None):
    with TransactionManager(conn).transaction():
        facts = WorkbenchProcessQueryService(conn).facts()
        rows, extra = ProcessRouteFileOperations(conn).preview_rows(source, facts, target_ref)
        # The real coordinator serializes private apply data with the server preview.
        rows = ResourceActionPreview.build("process.route.import", {}, rows).as_dict()["rows"]
        return rows, extra


def apply(conn, rows, ack=None, zero: Any = False):
    with TransactionManager(conn).transaction(begin_immediate=True):
        return ProcessRouteFileOperations(conn).apply_rows(
            rows, discard_group_refs=[] if ack is None else ack, confirm_zero_unit_hours=zero)


def table(conn, name):
    return [dict(row) for row in conn.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]


def operations(conn, code=PART):
    return {row["seq"]: dict(row) for row in conn.execute("SELECT * FROM PartOperations WHERE part_no=? ORDER BY seq", (code,))}


def groups(conn, code=PART):
    return {row["group_id"]: dict(row) for row in conn.execute("SELECT * FROM ExternalGroups WHERE part_no=? ORDER BY group_id", (code,))}


def ref(conn, kind="part", code=PART):
    return ref_for(conn, kind, str(code))


def snapshot(conn):
    return all_table_snapshot(conn)


def fail_if_called(*args, **kwargs):
    raise AssertionError("Unexpected reparse or confirmation")
