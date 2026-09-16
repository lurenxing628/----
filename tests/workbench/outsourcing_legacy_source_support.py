"""Isolated ten-operation legacy fixture with genuinely absent birth events."""

import pytest

from core.infrastructure.workbench_outsourcing_schema import install
from tests.workbench.outsourcing_support import outsourcing_case as _outsourcing_case  # noqa: F401
from tests.workbench.test_outsourcing_schema import remove_extension


def erase_fixture_birth_evidence(conn):
    """Model pre-lineage imports in a private fixture before taking its baseline."""
    guard = conn.execute("SELECT sql FROM sqlite_master WHERE name='wb_lineage_event_no_delete'").fetchone()[0]
    conn.execute("DROP TRIGGER wb_lineage_event_no_delete")
    conn.execute("DELETE FROM WorkbenchTemplateLineageEvents WHERE event_type='created'")
    conn.execute(guard)
    name = "wb_outsourcing_operationorigins_no_update"
    guard = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
    if guard is not None:
        conn.execute('DROP TRIGGER "' + name + '"')
        conn.execute("UPDATE WorkbenchOutsourcingOperationOrigins SET batch_ref=NULL")
        conn.execute(guard[0])
    conn.commit()


@pytest.fixture(name="legacy_source_case")
def legacy_source_case(outsourcing_case):
    case = outsourcing_case
    for index in range(4, 11):
        case.conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                          "VALUES (?,'XB1',?,'XT1','Heat treatment','external','XS1',2)", ("XO" + str(index), index))
    remove_extension(case.conn)
    erase_fixture_birth_evidence(case.conn)
    case.conn.execute("BEGIN")
    install(case.conn)
    case.conn.commit()
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingOperationOrigins WHERE batch_ref IS NULL").fetchone()[0] == 10
    yield case


def evidence(conn):
    return {name: [tuple(row) for row in conn.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]
            for name in ("WorkbenchOutsourcingOperationOrigins", "WorkbenchTemplateLineageEvents")}


def assert_empty_registration(conn):
    for suffix in ("Receipts", "Members", "Facts", "SourceConfirmations"):
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcing" + suffix).fetchone()[0] == 0
