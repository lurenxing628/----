"""Explicit v29 extension install, source preservation and append-only SQL."""

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.migration_state import get_schema_version
from core.infrastructure.workbench_outsourcing_schema import contract_issues, install, objects
from tests.workbench import outsourcing_support
from tests.workbench.outsourcing_support import original_rows
from tests.workbench.outsourcing_support import outsourcing_case as _outsourcing_case  # noqa: F401


@pytest.mark.parametrize("variant", ["current", "changed_v29"])
def test_fixture_rejects_non_frozen_schema_before_creating_database(tmp_path, schema_path, monkeypatch, variant):
    source = (Path(schema_path).read_bytes() if variant == "current"
              else outsourcing_support.FROZEN_V29.read_bytes() + b"\n")
    substituted = tmp_path / "substituted.sql"
    substituted.write_bytes(source)
    monkeypatch.setattr(outsourcing_support, "FROZEN_V29", substituted)
    with pytest.raises(AssertionError):
        next(_outsourcing_case.__wrapped__(tmp_path))
    assert not (tmp_path / "outsourcing.sqlite").exists()


def remove_extension(conn):
    definitions = objects()
    for name, sql in reversed(list(definitions.items())):
        kind = sql.split()[1]
        conn.execute('DROP ' + kind + ' "' + name + '"')


def test_schema_exact_idempotent_and_migration_rollback(outsourcing_case):
    case = outsourcing_case
    assert contract_issues(case.conn) == []
    with pytest.raises(RuntimeError, match="migration transaction"):
        install(case.conn)
    before = original_rows(case.conn)
    case.conn.execute("BEGIN")
    changes = case.conn.total_changes
    install(case.conn)
    assert case.conn.total_changes == changes
    case.conn.rollback()
    remove_extension(case.conn)
    case.conn.commit()
    case.conn.execute("BEGIN")
    install(case.conn)
    assert contract_issues(case.conn) == []
    case.conn.rollback()
    assert not case.conn.execute("SELECT name FROM sqlite_master WHERE name='WorkbenchOutsourcingFacts'").fetchone()
    assert get_schema_version(case.conn) == 29
    assert original_rows(case.conn) == before


def test_partial_schema_never_repairs_or_labels_success(outsourcing_case):
    case = outsourcing_case
    case.conn.execute("DROP TRIGGER wb_outsourcing_fact_sequence")
    case.conn.commit()
    case.conn.execute("BEGIN")
    with pytest.raises(RuntimeError, match="Cannot install or repair"):
        install(case.conn)
    case.conn.rollback()
    assert "missing_outsourcing_schema:wb_outsourcing_fact_sequence" in contract_issues(case.conn)
    assert get_schema_version(case.conn) == 29


@pytest.mark.parametrize("suffix", ["OperationOrigins", "Receipts", "Members", "Facts"])
@pytest.mark.parametrize("mode", ["update", "delete", "replace"])
def test_evidence_permanent_including_sqlite_replace(outsourcing_case, suffix, mode):
    case = outsourcing_case
    case.confirm(case.preview(case.payload()))
    table = "WorkbenchOutsourcing" + suffix
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    column = "fact_ref" if suffix == "Facts" else "outsourcing_ref" if suffix == "Receipts" else "operation_ref"
    sql = {"update": "UPDATE " + table + " SET " + column + "=" + column,
           "delete": "DELETE FROM " + table, "replace": "INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table}[mode]
    with pytest.raises(sqlite3.IntegrityError):
        case.conn.execute(sql)
    case.conn.rollback()
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts").fetchone()[0] == 1


def test_new_operation_origin_trigger_has_no_shipments(outsourcing_case):
    case = outsourcing_case
    case.conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,supplier_id) "
                     "VALUES ('XO4','XB1',4,'Heat treatment','external','XS1')")
    case.conn.commit()
    ref = case.operation_ref("XO4")
    assert case.conn.execute("SELECT batch_ref FROM WorkbenchOutsourcingOperationOrigins WHERE operation_ref=?", (ref,)).fetchone()[0] == case.entity_ref("batch", "XB1")
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts").fetchone()[0] == 0


def test_install_uses_birth_batch_not_current_same_number(outsourcing_case):
    case = outsourcing_case
    old_batch = case.entity_ref("batch", "XB1")
    remove_extension(case.conn)
    case.conn.commit()
    case.conn.execute("PRAGMA foreign_keys=OFF")
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    case.conn.execute("INSERT OR REPLACE INTO Batches SELECT * FROM Batches")
    case.conn.commit()
    case.conn.execute("PRAGMA foreign_keys=ON")
    assert old_batch != case.entity_ref("batch", "XB1")
    case.conn.execute("BEGIN")
    install(case.conn)
    case.conn.commit()
    assert case.conn.execute("SELECT DISTINCT batch_ref FROM WorkbenchOutsourcingOperationOrigins").fetchone()[0] == old_batch
    from core.models.workbench_command import WorkbenchCommandRejected

    with pytest.raises(WorkbenchCommandRejected, match="所属批次实例已变化"):
        case.preview(case.payload())


def test_install_never_guesses_missing_legacy_birth(outsourcing_case):
    case = outsourcing_case
    ref = case.operation_ref("XO1")
    remove_extension(case.conn)
    guard = case.conn.execute("SELECT sql FROM sqlite_master WHERE name='wb_lineage_event_no_delete'").fetchone()[0]
    case.conn.execute("DROP TRIGGER wb_lineage_event_no_delete")
    case.conn.execute("DELETE FROM WorkbenchTemplateLineageEvents WHERE operation_ref=?", (ref,))
    case.conn.execute(guard)
    case.conn.commit()
    source = original_rows(case.conn)
    case.conn.execute("BEGIN")
    install(case.conn)
    case.conn.commit()
    assert case.conn.execute("SELECT batch_ref FROM WorkbenchOutsourcingOperationOrigins WHERE operation_ref=?", (ref,)).fetchone()[0] is None
    from core.models.workbench_command import WorkbenchCommandRejected

    with pytest.raises(WorkbenchCommandRejected, match="映射缺失"):
        case.preview(case.payload())
    assert original_rows(case.conn) == source
    assert get_schema_version(case.conn) == 29


def test_missing_ledger_with_existing_command_receipt_refuses_reinstall(outsourcing_case):
    case = outsourcing_case
    case.confirm(case.preview(case.payload()))
    remove_extension(case.conn)
    case.conn.commit()
    case.conn.execute("BEGIN")
    with pytest.raises(RuntimeError, match="receipts exist without facts"):
        install(case.conn)
    case.conn.rollback()
    assert not case.conn.execute("SELECT 1 FROM sqlite_master WHERE name='WorkbenchOutsourcingFacts'").fetchone()
