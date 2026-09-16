"""Real v31 -> v32 migration: exact additive DDL, preservation and rollback."""

from contextlib import closing

import pytest

from core.infrastructure import database
from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
    current_schema_contract_issues,
    get_schema_version,
)
from core.infrastructure.migrations import MIGRATIONS, v32
from core.infrastructure.workbench_execution_void_schema import execution_void_contract_issues
from core.infrastructure.workbench_outsourcing_source_schema import contract_issues as source_contract_issues
from tests.workbench.calibration_dashboard_migration_support import canonical_object
from tests.workbench.run_schema_migration_support import connect, snapshot, source_ddl
from tests.workbench.schema32_migration_support import (
    V32_TABLES,
    assert_v32_empty,
    frozen_v31,
    missing_v32_issues,
    objects,
    seed_v31,
)


def test_frozen_v31_step_and_fresh_v32_have_identical_ddl(tmp_path, schema_path, monkeypatch):
    assert CURRENT_SCHEMA_VERSION == 32 and MIGRATIONS[32] is v32.run
    def forbidden(*args, **kwargs):
        pytest.fail("Fresh schema must not migrate or create historical evidence")
    monkeypatch.setattr(database, "_migrate_with_backup_impl", forbidden)
    path = tmp_path / "fresh.db"
    database.ensure_schema(str(path), schema_path=schema_path)
    with closing(connect(path)) as fresh, closing(frozen_v31(":memory:")) as old:
        assert get_schema_version(fresh) == 32 and not current_schema_contract_issues(fresh)
        assert set(current_schema_contract_issues(old)) == missing_v32_issues()
        assert v32.run(old) == MigrationOutcome.APPLIED and get_schema_version(old) == 31
        assert list(map(canonical_object, source_ddl(old))) == list(map(canonical_object, source_ddl(fresh)))
        assert_v32_empty(fresh)
        before, changes = snapshot(fresh), fresh.total_changes
        fresh.execute("PRAGMA query_only=ON")
        assert not source_contract_issues(fresh) and not execution_void_contract_issues(fresh)
        assert snapshot(fresh) == before and fresh.total_changes == changes


def test_v31_upgrade_preserves_typed_rows_old_ddl_backup_and_restart(tmp_path, schema_path):
    path, backups = tmp_path / "v31.db", tmp_path / "backups"
    with closing(seed_v31(path)) as conn:
        before, ddl = snapshot(conn), source_ddl(conn)
        for table in ("WorkbenchProductionReports", "WorkbenchProductionReportRevisions", "WorkbenchOutsourcingReceipts",
                      "WorkbenchOutsourcingFacts", "WorkbenchOutsourcingOperationOrigins", "WorkbenchRunCandidates"):
            assert before[table], table
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with closing(connect(path)) as conn:
        after, new_ddl = snapshot(conn), source_ddl(conn)
        assert get_schema_version(conn) == 32 and not current_schema_contract_issues(conn)
        assert set(after) - set(before) == set(V32_TABLES)
        assert_v32_empty(conn)
        assert {name: after[name] for name in before if name != "SchemaVersion"} == {
            name: rows for name, rows in before.items() if name != "SchemaVersion"}
        assert [row for row in new_ddl if row[1] in {old[1] for old in ddl}] == ddl
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    copies = list(backups.glob("*before_migrate_v31_to_v32*.db"))
    assert len(copies) == 1
    with closing(connect(copies[0])) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl and get_schema_version(conn) == 31
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with closing(connect(path)) as conn:
        assert snapshot(conn) == after and source_ddl(conn) == new_ddl
        assert v32.run(conn) == MigrationOutcome.APPLIED and snapshot(conn) == after
    assert len(list(backups.glob("*.db"))) == 1


@pytest.mark.parametrize("boundary", ("step", "probe", "actual"))
def test_second_install_failure_rolls_back_both_extensions(tmp_path, schema_path, monkeypatch, boundary):
    path, backups = tmp_path / "v31.db", tmp_path / "backups"
    with closing(frozen_v31(path)) as conn:
        conn.execute("INSERT INTO Parts(part_no,part_name,remark) VALUES ('P32','Preserve',?)", (b"original\x00\xff",))
        conn.commit()
        before, ddl = snapshot(conn), source_ddl(conn)
    original, calls = v32.install_execution_voids, []
    def fail(conn):
        original(conn)
        calls.append(conn.execute("PRAGMA database_list").fetchone()[2])
        assert_v32_empty(conn)
        if boundary != "actual" or len(calls) == 2:
            raise RuntimeError("injected v32 second installer failure")
    monkeypatch.setattr(v32, "install_execution_voids", fail)
    with pytest.raises(RuntimeError, match="injected v32"):
        if boundary == "step":
            with closing(connect(path)) as conn:
                v32.run(conn)
        else:
            database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with closing(connect(path)) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl and get_schema_version(conn) == 31
    assert len(calls) == (2 if boundary == "actual" else 1)
    copies = list(backups.glob("*.db"))
    assert len(copies) == (1 if boundary == "actual" else 0)
    for copy in copies:
        with closing(connect(copy)) as conn:
            assert snapshot(conn) == before and source_ddl(conn) == ddl


@pytest.mark.parametrize("name", tuple(objects()))
def test_current_missing_object_rejected_without_repair(tmp_path, schema_path, name):
    path = tmp_path / "broken.db"
    database.ensure_schema(str(path), schema_path=schema_path)
    with closing(connect(path)) as conn:
        conn.execute('DROP ' + objects()[name].split()[1] + ' "' + name + '"')
        conn.commit()
        before, ddl = snapshot(conn), source_ddl(conn)
    with pytest.raises(MigrationContractError, match="outsourcing_source_schema|execution_void"):
        database.ensure_schema(str(path), schema_path=schema_path)
    with closing(connect(path)) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl


@pytest.mark.parametrize("name", ("wb_execution_voids_current_revision", "wb_outsourcing_source_confirmation_guard"))
def test_v31_partial_extension_is_not_silently_completed(tmp_path, schema_path, name):
    path, backups = tmp_path / "partial.db", tmp_path / "backups"
    with closing(frozen_v31(path)) as conn:
        v32.run(conn)
        conn.execute("DROP TRIGGER " + name)
        conn.commit()
        before, ddl = snapshot(conn), source_ddl(conn)
    with pytest.raises(RuntimeError, match="Cannot install or repair|Cannot repair partial"):
        database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with closing(connect(path)) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl and get_schema_version(conn) == 31
    assert not list(backups.glob("*.db"))


@pytest.mark.parametrize("name,table,check,prefix", (
    ("wb_execution_voids_no_update", "WorkbenchProductionReportVoids", execution_void_contract_issues, "invalid_execution_void:"),
    ("wb_outsourcing_source_confirmation_no_update", "WorkbenchOutsourcingSourceConfirmations", source_contract_issues, "invalid_outsourcing_source_schema:"),
))
def test_wrong_guard_definition_is_rejected_read_only(tmp_path, schema_path, name, table, check, prefix):
    path = tmp_path / "wrong-guard.db"
    database.ensure_schema(str(path), schema_path=schema_path)
    with closing(connect(path)) as conn:
        conn.execute("DROP TRIGGER " + name)
        conn.execute("CREATE TRIGGER " + name + " BEFORE UPDATE ON " + table + " BEGIN SELECT 1; END")
        conn.commit()
        before, ddl, changes = snapshot(conn), source_ddl(conn), conn.total_changes
        conn.execute("PRAGMA query_only=ON")
        assert check(conn) == [prefix + name]
        assert snapshot(conn) == before and source_ddl(conn) == ddl and conn.total_changes == changes
    with pytest.raises(MigrationContractError, match=prefix):
        database.ensure_schema(str(path), schema_path=schema_path)
    with closing(connect(path)) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl
