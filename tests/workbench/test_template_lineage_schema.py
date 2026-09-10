"""Migration boundary, no-backfill and raw SQLite evidence contracts."""

import sqlite3

import pytest

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_template_lineage_schema import contract_issues, install, objects
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import restore_snapshot, snapshot
from core.services.scheduler.batch_service import BatchService
from core.services.workbench.template_lineage_query import TemplateLineageQuery
from tests.workbench.test_execution_ledger_support import all_rows
from tests.workbench.test_template_lineage_support import create, lineage_case, origin
from tests.workbench.test_template_lineage_support import ledger_fixture as _ledger_fixture

_lineage_fixture = lineage_case


def test_install_requires_caller_and_is_idempotent_without_business_rewrites(lineage_case):
    case = lineage_case
    before = all_rows(case.conn)
    with pytest.raises(RuntimeError, match="caller"):
        install(case.conn)
    with TransactionManager(case.conn).transaction():
        install(case.conn)
        assert case.conn.in_transaction
        assert contract_issues(case.conn) == []
    assert all_rows(case.conn) == before
    assert not before["WorkbenchTemplateLineageOrigins"]
    assert not before["WorkbenchTemplateLineageEvents"]


def test_initial_install_rolls_back_all_objects_and_preserves_blobs(ledger_case):
    case = ledger_case
    case.conn.execute("UPDATE BatchOperations SET op_type_name=?,unit_hours=NULL", (sqlite3.Binary(b"\x00\xfforiginal"),))
    case.conn.commit()
    before = all_rows(case.conn)
    with pytest.raises(RuntimeError, match="test rollback"):
        with TransactionManager(case.conn).transaction():
            install(case.conn)
            raise RuntimeError("test rollback")
    assert not set(objects()) & {row[0] for row in case.conn.execute("SELECT name FROM sqlite_master")}
    assert all_rows(case.conn) == before


def test_missing_schema_blocks_real_template_create_and_read_does_not_install(ledger_case):
    case = ledger_case
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,unit_hours) VALUES ('P1',1,'T1','Turning','internal',1)")
    case.conn.commit()
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        BatchService(case.conn).create_batch_from_template("BLOCKED", "P1", 10)
    assert exc.value.code == "template_lineage_schema_missing"
    assert all_rows(case.conn) == before
    assert TemplateLineageQuery(case.conn).read([])["available"] is False
    assert all_rows(case.conn) == before


def test_partial_schema_fails_without_repair(lineage_case):
    conn = lineage_case.conn
    conn.execute("DROP TRIGGER wb_lineage_operation_update")
    before = all_rows(conn)
    with pytest.raises(RuntimeError, match="Cannot install"):
        with TransactionManager(conn).transaction():
            install(conn)
    with pytest.raises(WorkbenchCommandRejected):
        TemplateLineageQuery(conn).read([])
    assert all_rows(conn) == before
    assert contract_issues(conn) == ["missing_template_lineage:wb_lineage_operation_update"]


@pytest.mark.parametrize("table", ["WorkbenchTemplateLineageOrigins", "WorkbenchTemplateLineageEvents"])
@pytest.mark.parametrize("verb", ["DELETE", "UPDATE"])
def test_evidence_is_append_only(lineage_case, table, verb):
    case = lineage_case
    create(case)
    sql = "DELETE FROM " + table if verb == "DELETE" else "UPDATE " + table + " SET operation_ref=operation_ref"
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        case.conn.execute(sql)
    case.conn.rollback()


def test_template_blob_and_null_survive_copy_and_journal(lineage_case):
    case = lineage_case
    payload = b"\x00\xff\x80original-template"
    case.conn.execute("UPDATE PartOperations SET op_type_name=?,setup_hours=NULL,unit_hours=0", (sqlite3.Binary(payload),))
    case.conn.commit()
    before = tuple(case.conn.execute("SELECT * FROM PartOperations").fetchone())
    op_id = create(case)
    saved = origin(case, op_id)
    template = restore_snapshot(saved["template_snapshot"])
    instance = restore_snapshot(saved["instance_snapshot"])
    assert template["op_type_name"] == instance["op_type_name"] == payload
    assert instance["setup_hours"] is None and instance["unit_hours"] == 0
    assert tuple(case.conn.execute("SELECT * FROM PartOperations").fetchone()) == before
    row = case.conn.execute("SELECT typeof(op_type_name),op_type_name FROM WorkbenchTemplateLineageEvents").fetchone()
    assert tuple(row) == ("blob", payload)
    assert snapshot(template) == saved["template_snapshot"]
