"""Backed-up v24 -> CURRENT startup, separately from the v25 installer step."""

import hashlib

import pytest

from core.infrastructure import database
from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
    current_schema_contract_issues,
    get_schema_version,
    is_truly_empty_db,
)
from core.infrastructure.migrations import MIGRATIONS, v25, v27, v28
from core.infrastructure.workbench_execution_ledger_schema import (
    LEGACY_COLUMNS,
    execution_ledger_contract_issues,
    execution_ledger_objects,
    install_execution_ledger,
)
from core.infrastructure.workbench_metadata_schema import _canonical_sql
from core.infrastructure.workbench_run_schema import RUN_TABLES, workbench_run_objects
from core.infrastructure.workbench_template_lineage_schema import template_lineage_objects
from core.infrastructure.workbench_trial_schema import workbench_trial_objects
from tests.workbench.dashboard_external_migration_support import V31_TABLES, assert_v31_receipt_maps_only
from tests.workbench.execution_ledger_migration_support import (
    V24_SCHEMA,
    V27_TABLES,
    connect,
    seed_v24,
    snapshot,
    without_version,
)
from tests.workbench.legacy_migration_current_support import (
    V30_TABLES,
    V32_TABLES,
    assert_v30_source_maps_only,
    assert_v32_empty,
)
from tests.workbench.plan_identity_support import LEDGER_TABLES
from tests.workbench.run_schema_migration_support import source_ddl
from tests.workbench.schema29_regression_support import V29_TABLES, assert_v29_source_maps_only


def test_fixed_v24_archive_is_unchanged():
    assert hashlib.sha256(V24_SCHEMA.read_bytes()).hexdigest() == "023f7ae15282b1cc0523f218c2b45e1ba6cb4f036d491fe7761cbd8f1f56f03c"


def test_fresh_current_is_current_without_legacy_migration(tmp_path, schema_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A fresh database must not run a legacy migration")

    monkeypatch.setattr(database, "_migrate_with_backup_impl", forbidden)
    path, backups = tmp_path / "fresh.db", tmp_path / "backups"
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    assert MIGRATIONS[28] is v28.run
    assert MIGRATIONS[25] is v25.run
    assert MIGRATIONS[27] is v27.run
    assert 26 in MIGRATIONS
    with connect(path) as conn:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION
        assert current_schema_contract_issues(conn) == []
        assert is_truly_empty_db(conn)
        assert all(conn.execute('SELECT count(*) FROM "' + table + '"').fetchone()[0] == 0
                   for table in RUN_TABLES + V27_TABLES + LEDGER_TABLES[1:])
        assert tuple(conn.execute("SELECT * FROM WorkbenchExecutionLedgerClock").fetchone()) == (1, 1, 1)
        actual = dict(conn.execute("SELECT name,sql FROM sqlite_master"))
        expected = execution_ledger_objects()
        assert len(expected) == 22
        assert all(_canonical_sql(actual[name]) == _canonical_sql(sql) for name, sql in expected.items())
    assert not list(backups.glob("*.db"))


def test_real_upgrade_preserves_every_old_row_type_identity_and_backup(tmp_path, schema_path):
    path, backups = tmp_path / "old.db", tmp_path / "backups"
    with seed_v24(path) as conn:
        before, ddl_before = snapshot(conn), source_ddl(conn)
        original = [tuple(row) for row in conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")]
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION and current_schema_contract_issues(conn) == []
        after = snapshot(conn)
        assert without_version({name: after[name] for name in before}) == without_version(before)
        assert set(after) - set(before) == set(LEDGER_TABLES + RUN_TABLES + V27_TABLES + V29_TABLES + V30_TABLES + V31_TABLES + V32_TABLES)
        assert_v29_source_maps_only(conn)
        assert_v30_source_maps_only(conn)
        assert_v31_receipt_maps_only(conn)
        assert_v32_empty(conn)
        assert all(after[table] == [] for table in RUN_TABLES + V27_TABLES + LEDGER_TABLES[2:])
        assert [row for row in source_ddl(conn) if row[1] in {old[1] for old in ddl_before}] == ddl_before
        assert tuple(conn.execute("SELECT * FROM WorkbenchExecutionLedgerClock").fetchone()) == (1, 1 + len(original), 1)
        archived = [tuple(row) for row in conn.execute(
            "SELECT " + ",".join(LEGACY_COLUMNS) + " FROM WorkbenchExecutionLegacyFacts ORDER BY id")]
        assert archived == original
        assert [tuple(row) for row in conn.execute(
            "SELECT typeof(remark),typeof(quantity_done),typeof(created_at) FROM WorkbenchExecutionLegacyFacts"
        )] == [("blob", "null", "text")] * 2
        assert conn.execute("SELECT count(*) FROM WorkbenchExecutionLegacyFacts WHERE operation_ref IS NOT NULL "
                            "AND recorded_against_task_ref IS NOT NULL AND recorded_against_plan_ref IS NOT NULL").fetchone()[0] == 2
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    files = list(backups.glob(f"*before_migrate_v24_to_v{CURRENT_SCHEMA_VERSION}*.db"))
    assert len(files) == 1
    assert list(backups.glob("*.db")) == files
    with connect(files[0]) as backup:
        assert get_schema_version(backup) == 24 and snapshot(backup) == before
        assert source_ddl(backup) == ddl_before
        assert not (set(execution_ledger_objects()) | set(workbench_run_objects()) |
                    set(template_lineage_objects()) | set(workbench_trial_objects())) & {
            row[0] for row in backup.execute("SELECT name FROM sqlite_master")}
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        conn.execute("BEGIN")
        install_execution_ledger(conn)
        conn.commit()
        assert snapshot(conn) == after
    assert len(list(backups.glob("*.db"))) == 1


@pytest.mark.parametrize("damage", [
    "DROP TRIGGER wb_execution_capture_legacy",
    "DROP INDEX idx_wb_execution_resource_history",
    "DELETE FROM WorkbenchExecutionLedgerClock",
    "DROP TABLE WorkbenchProductionReportRevisions",
])
def test_current_damaged_ledger_is_never_recreated(tmp_path, schema_path, damage):
    path = tmp_path / "damaged.db"
    with seed_v24(path):
        pass
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(tmp_path / "backups"))
    with connect(path) as conn:
        conn.execute(damage)
        conn.commit()
        before = snapshot(conn)
        ddl = list(conn.execute("SELECT name,sql FROM sqlite_master ORDER BY name"))
    with pytest.raises(MigrationContractError, match="execution_ledger"):
        database.ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert snapshot(conn) == before
        assert [tuple(row) for row in conn.execute("SELECT name,sql FROM sqlite_master ORDER BY name")] == [tuple(row) for row in ddl]


@pytest.mark.parametrize("change", [
    "DELETE FROM WorkbenchExecutionLedgerClock",
    "UPDATE WorkbenchExecutionLedgerClock SET revision=2",
    "UPDATE WorkbenchExecutionLedgerClock SET next_report_no=2",
])
def test_only_exact_unused_ledger_clock_counts_as_empty(tmp_path, schema_path, change):
    path = tmp_path / "fresh.db"
    database.ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert is_truly_empty_db(conn)
        conn.execute(change)
        assert not is_truly_empty_db(conn)


def test_migration_failure_rolls_back_archive_and_objects(tmp_path, monkeypatch):
    with seed_v24(tmp_path / "rollback.db") as conn:
        before = snapshot(conn)
        ddl = [tuple(row) for row in conn.execute("SELECT name,sql FROM sqlite_master ORDER BY name")]

        def fail_after_archive(connection):
            install_execution_ledger(connection)
            assert connection.execute("SELECT count(*) FROM WorkbenchExecutionLegacyFacts").fetchone()[0] == 2
            raise RuntimeError("injected failure after archive")

        monkeypatch.setattr(v25, "install_execution_ledger", fail_after_archive)
        with pytest.raises(RuntimeError, match="injected failure"):
            v25.run(conn)
        assert snapshot(conn) == before
        assert [tuple(row) for row in conn.execute("SELECT name,sql FROM sqlite_master ORDER BY name")] == ddl
        assert get_schema_version(conn) == 24


def test_partly_installed_v24_is_rejected_before_touching_original(tmp_path, schema_path):
    path, backups = tmp_path / "partial.db", tmp_path / "backups"
    with seed_v24(path) as conn:
        conn.execute(execution_ledger_objects()["WorkbenchExecutionLedgerClock"])
        conn.commit()
        before = snapshot(conn)
    with pytest.raises((MigrationContractError, RuntimeError), match="partial execution ledger"):
        database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        assert snapshot(conn) == before and get_schema_version(conn) == 24
    assert not list(backups.glob("*.db"))


def test_v25_step_preserves_all_old_rows_and_installs_only_execution_ledger(tmp_path):
    with seed_v24(tmp_path / "v25-step.db") as conn:
        before = snapshot(conn)
        original = [tuple(row) for row in conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")]
        assert v25.run(conn) == MigrationOutcome.APPLIED
        after = snapshot(conn)
        assert get_schema_version(conn) == 24
        assert {name: after[name] for name in before} == before
        assert set(after) - set(before) == set(LEDGER_TABLES)
        assert not (set(workbench_run_objects()) | set(template_lineage_objects()) | set(workbench_trial_objects())) & {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
        assert execution_ledger_contract_issues(conn) == []
        assert [tuple(row) for row in conn.execute(
            "SELECT " + ",".join(LEGACY_COLUMNS) + " FROM WorkbenchExecutionLegacyFacts ORDER BY id")] == original
        assert [tuple(row) for row in conn.execute(
            "SELECT typeof(remark),typeof(quantity_done),typeof(created_at) FROM WorkbenchExecutionLegacyFacts"
        )] == [("blob", "null", "text")] * 2
        assert conn.execute("SELECT count(*) FROM WorkbenchExecutionLegacyFacts WHERE operation_ref IS NOT NULL "
                            "AND recorded_against_task_ref IS NOT NULL AND recorded_against_plan_ref IS NOT NULL").fetchone()[0] == 2
        assert tuple(conn.execute("SELECT * FROM WorkbenchExecutionLedgerClock").fetchone()) == (1, 1 + len(original), 1)
        assert all(after[table] == [] for table in LEDGER_TABLES[2:])
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert v25.run(conn) == MigrationOutcome.APPLIED
        assert snapshot(conn) == after


def test_fresh_current_and_v25_step_have_identical_execution_ddl(tmp_path, schema_path):
    path = tmp_path / "fresh.db"
    database.ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as fresh, seed_v24(tmp_path / "old.db") as old:
        v25.run(old)
        assert execution_ledger_contract_issues(old) == []
        for name in execution_ledger_objects():
            lhs = fresh.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
            rhs = old.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
            assert _canonical_sql(lhs) == _canonical_sql(rhs)
