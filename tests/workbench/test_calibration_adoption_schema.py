"""Standalone DDL hook, immutable audit/lock data and explicit missing-schema errors."""

import sqlite3

import pytest

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_calibration_adoption_schema import (
    ADOPTIONS,
    LOCKS,
    contract_issues,
    install,
    objects,
)
from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository
from tests.workbench.calibration_adoption_support import INTENT, KEY, PREVIEW_INTENT, service, snapshot, token
from tests.workbench.calibration_adoption_support import adoption_case as _adoption_case  # noqa: F401
from tests.workbench.calibration_adoption_support import ready_adoption_case as _ready_case  # noqa: F401
from tests.workbench.test_template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.test_template_lineage_support import lineage_case as _lineage_case  # noqa: F401


def _remove(conn):
    for name in reversed(objects()):
        kind = conn.execute("SELECT type FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
        conn.execute('DROP ' + kind.upper() + ' "' + name + '"')
    conn.commit()


def _schema(conn):
    return [tuple(row) for row in conn.execute("SELECT name,sql FROM sqlite_master ORDER BY name")]


def test_install_requires_outer_migration_is_idempotent_and_rolls_back(adoption_case):
    case = adoption_case
    _remove(case.conn)
    before, structure = snapshot(case.conn), _schema(case.conn)
    with pytest.raises(RuntimeError, match="transaction"):
        install(case.conn)
    with pytest.raises(RuntimeError, match="cancel"):
        with TransactionManager(case.conn).transaction():
            install(case.conn)
            assert contract_issues(case.conn) == []
            raise RuntimeError("cancel")
    assert snapshot(case.conn) == before and _schema(case.conn) == structure
    with TransactionManager(case.conn).transaction():
        install(case.conn)
    installed = _schema(case.conn)
    with TransactionManager(case.conn).transaction():
        install(case.conn)
    assert _schema(case.conn) == installed and contract_issues(case.conn) == []
    for table, rows in before.items():
        assert snapshot(case.conn)[table] == rows


@pytest.mark.parametrize("damage", ["absent", "partial", "altered"])
def test_missing_and_changed_storage_fail_closed_without_repair(adoption_case, damage):
    case = adoption_case
    if damage == "absent":
        _remove(case.conn)
    else:
        case.conn.execute("DROP TRIGGER wb_calibration_quota_lock_no_delete")
        if damage == "altered":
            case.conn.execute("CREATE TRIGGER wb_calibration_quota_lock_no_delete BEFORE DELETE ON WorkbenchCalibrationQuotaLocks BEGIN SELECT 1; END")
    case.conn.commit()
    before, structure = snapshot(case.conn), _schema(case.conn)
    repo = WorkbenchCalibrationAdoptionRepository(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        repo.read_locks([case.template_ref])
    assert error.value.code == "adoption_schema_unavailable"
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).preview(case.template_ref, PREVIEW_INTENT)
    assert error.value.code == "adoption_schema_unavailable"
    if damage != "absent":
        with pytest.raises(RuntimeError, match="Cannot install"):
            with TransactionManager(case.conn).transaction():
                install(case.conn)
    assert snapshot(case.conn) == before and _schema(case.conn) == structure


@pytest.mark.parametrize("table", [ADOPTIONS, LOCKS])
@pytest.mark.parametrize("verb", ["UPDATE", "DELETE", "REPLACE"])
def test_audit_and_lock_cannot_be_changed_deleted_or_replaced(ready_adoption_case, table, verb):
    case = ready_adoption_case
    service(case.conn).confirm(case.template_ref, token(case), KEY, INTENT)
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    before = snapshot(case.conn)
    sql = {"UPDATE": "UPDATE " + table + " SET template_operation_ref=template_operation_ref",
           "DELETE": "DELETE FROM " + table,
           "REPLACE": "INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table}[verb]
    with pytest.raises(sqlite3.IntegrityError):
        with TransactionManager(case.conn).transaction():
            case.conn.execute(sql)
    assert snapshot(case.conn) == before


def test_lock_requires_matching_audit_and_missing_lock_is_not_unlocked(ready_adoption_case):
    case = ready_adoption_case
    with pytest.raises(sqlite3.IntegrityError, match="matching adoption"):
        with TransactionManager(case.conn).transaction():
            case.conn.execute("INSERT INTO WorkbenchCalibrationQuotaLocks VALUES (?,?,?,?)", (case.template_ref, "a" * 48, 3, "now"))
    service(case.conn).confirm(case.template_ref, token(case), KEY, INTENT)
    # Damage only the temporary database, then restore identical DDL before reading.
    case.conn.execute("DROP TRIGGER wb_calibration_quota_lock_no_delete")
    case.conn.execute("DELETE FROM WorkbenchCalibrationQuotaLocks")
    case.conn.execute(objects()["wb_calibration_quota_lock_no_delete"])
    case.conn.commit()
    assert contract_issues(case.conn) == []
    with pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchCalibrationAdoptionRepository(case.conn).read_locks([case.template_ref])
    assert error.value.code == "calibration_lock_corrupt"


def test_unregistered_hook_does_not_alter_current_schema_version(adoption_case):
    case = adoption_case
    before = case.conn.execute("PRAGMA user_version").fetchone()[0]
    with TransactionManager(case.conn).transaction():
        install(case.conn)
    assert case.conn.execute("PRAGMA user_version").fetchone()[0] == before
    assert not any("Schedule" in sql or "BatchOperations" in sql or "ALTER TABLE" in sql for sql in objects().values())
