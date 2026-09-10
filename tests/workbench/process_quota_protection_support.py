"""CW-only fixtures: explicit CO DDL, real adopted samples and typed history."""

import sqlite3

import pytest
from flask import Flask, g

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_calibration_adoption_schema import install
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode
from core.services.process.part_operation_hours_excel_import_service import PartOperationHoursExcelImportService
from core.services.workbench.process_file_hours import ProcessHoursFileOperations
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from core.services.workbench.process_quota_protection import ProcessQuotaProtection
from tests.workbench.calibration_adoption_support import INTENT, KEY, service, snapshot, token
from tests.workbench.process_workflow_support import confirm_all
from tests.workbench.template_lineage_support import completed
from web.routes.process_excel_part_operation_hours import (
    _build_existing_for_append,
    _build_existing_internal,
    _build_validator,
    _normalize_rows,
    _rewrite_append_preview_rows,
)


@pytest.fixture(name="quota_case")
def quota_case(lineage_case):
    case = lineage_case
    with TransactionManager(case.conn).transaction():
        install(case.conn)
    case.conn.execute("PRAGMA foreign_keys=ON")
    case.app = Flask("cw-quota-tests")
    case.app.config.update(TESTING=True, SECRET_KEY="cw-isolated-quota")
    case.template_ref = ProcessQuotaProtection(case.conn).bind("P1", 1)
    case.db_path = case.conn.execute("PRAGMA database_list").fetchone()[2]
    case.conn.execute("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours)
        VALUES('P1',2,'T1','Turning','internal',0.5,7)""")
    case.conn.execute("UPDATE Parts SET route_raw='Turning,Turning',route_parsed='yes' WHERE part_no='P1'")
    case.conn.execute("ALTER TABLE PartOperations ADD COLUMN cw_hidden BLOB")
    case.conn.execute("UPDATE PartOperations SET cw_hidden=?,created_at='2001-02-03 04:05:06'", (b"hidden\x00\xff",))
    case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=1", (b"old-plan\x00\xff",))
    case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE version=1")
    case.conn.commit()
    case.ids, case.reports = completed(case, [1, 2, 3, 4, 5])
    case.other_ref = ProcessQuotaProtection(case.conn).bind("P1", 2)
    confirm_all(case.conn)
    with case.app.app_context():
        yield case


@pytest.fixture(name="locked_quota_case")
def locked_quota_case(quota_case):
    adopt(quota_case)
    return quota_case


def adopt(case):
    return service(case.conn).confirm(case.template_ref, token(case), KEY, INTENT)


def connect(case, *, factory=sqlite3.Connection, timeout=5):
    conn = sqlite3.connect(case.db_path, factory=factory, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def file_preview(conn, *values):
    decoded = [{"row": index + 2, "values": {"business_code": "P1", **row}, "errors": []}
               for index, row in enumerate(values)]
    reader = WorkbenchProcessQueryService(conn)
    with reader.read_snapshot():
        return ProcessHoursFileOperations(conn).preview_rows(decoded, reader.facts())


def file_apply(conn, rows, *, ack=False):
    with TransactionManager(conn).transaction(begin_immediate=True):
        return ProcessHoursFileOperations(conn).apply_rows(rows, discard_group_refs=[], confirm_zero_unit_hours=ack)


def legacy_preview(conn, *values, mode=ImportMode.OVERWRITE):
    g.db = conn
    existing, meta, _ = _build_existing_internal()
    rows = _normalize_rows([{"图号": "P1", **row} for row in values])
    if mode == ImportMode.APPEND:
        existing = _build_existing_for_append(existing)
    preview = ExcelService(get_excel_backend()).preview_import(rows, "__row_id__", existing,
        validators=[_build_validator(meta)], mode=mode)
    _rewrite_append_preview_rows(preview, mode)
    PartOperationHoursExcelImportService.protect_preview_rows(preview, meta)
    return preview


def templates(conn):
    return {row["seq"]: dict(row) for row in conn.execute("SELECT * FROM PartOperations WHERE part_no='P1' ORDER BY seq")}


def preserved(before, after, *, workflow=False):
    allowed = {"PartOperations", "WorkbenchEntityRefs"}
    if workflow:
        allowed.update(("WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations", "WorkbenchCommandReceipts"))
    for table in before:
        if table not in allowed:
            assert after[table] == before[table], table


def assert_rejected(code, callback):
    from core.models.workbench_command import WorkbenchCommandRejected

    with pytest.raises(WorkbenchCommandRejected) as caught:
        callback()
    assert caught.value.code == code
