"""Real v25 -> current startup/backup proof; migration must not run or adopt plans."""

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
    set_schema_version,
)
from core.infrastructure.migrations import MIGRATIONS, v26, v27, v28, v29, v30, v31, v32
from core.infrastructure.workbench_lineage_lookup_schema import lineage_lookup_objects
from core.infrastructure.workbench_metadata_schema import _canonical_sql
from core.infrastructure.workbench_run_schema import RUN_TABLES, install_workbench_run_schema, workbench_run_objects
from core.infrastructure.workbench_template_lineage_schema import template_lineage_objects
from core.infrastructure.workbench_trial_schema import workbench_trial_objects
from tests.workbench.dashboard_external_migration_support import (
    V31_TABLES,
    assert_v31_receipt_maps_only,
    missing_v31_issues,
)
from tests.workbench.execution_ledger_migration_support import V27_TABLES
from tests.workbench.legacy_migration_current_support import (
    V30_TABLES,
    V32_TABLES,
    assert_v30_source_maps_only,
    assert_v32_empty,
    missing_v30_issues,
    missing_v32_issues,
)
from tests.workbench.run_schema_migration_support import FIXTURE_V25, connect, seed_v25, snapshot, source_ddl
from tests.workbench.schema29_regression_support import V29_TABLES, assert_v29_source_maps_only, missing_v29_issues


def test_fixed_v25_archive_is_unchanged():
    assert hashlib.sha256(FIXTURE_V25.read_bytes()).hexdigest() == "18db92ca20538f45ff3c48045196ff7ff6fb37105dd9f7a4182c931008f9bc4e"


def test_fresh_current_fastforwards_without_scheduling(tmp_path, schema_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A fresh database must not migrate old data or execute a schedule")

    monkeypatch.setattr(database, "_migrate_with_backup_impl", forbidden)
    from core.services.workbench.run_worker import WorkbenchRunWorker

    monkeypatch.setattr(WorkbenchRunWorker, "execute", forbidden)
    path, backups = tmp_path / "fresh.db", tmp_path / "backups"
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        assert MIGRATIONS[28] is v28.run
        assert MIGRATIONS[27] is v27.run
        assert MIGRATIONS[26] is v26.run
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION and current_schema_contract_issues(conn) == []
        assert is_truly_empty_db(conn)
        assert len(template_lineage_objects()) == 15 and len(workbench_trial_objects()) == 18
        assert {name for name, sql in dict(template_lineage_objects(), **workbench_trial_objects()).items()
                if sql.startswith("CREATE TABLE")} == set(V27_TABLES)
        for table in RUN_TABLES + V27_TABLES + ("Schedule", "ScheduleHistory", "ScheduleCandidate", "WorkbenchCommandReceipts"):
            assert conn.execute('SELECT count(*) FROM "' + table + '"').fetchone()[0] == 0
    assert not list(backups.glob("*.db"))


def test_real_upgrade_backs_up_and_retains_all_v25_facts_and_refs(tmp_path, schema_path):
    path, backups = tmp_path / "legacy.db", tmp_path / "backups"
    with seed_v25(path) as conn:
        before, ddl_before = snapshot(conn), source_ddl(conn)
        assert len(before["WorkbenchProductionReports"]) == 1
        assert len(before["WorkbenchProductionReportRevisions"]) == 1
        assert len(before["WorkbenchExecutionLegacyFacts"]) == 2
        assert len(before["WorkbenchCommandReceipts"]) == 1
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        after = snapshot(conn)
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION and current_schema_contract_issues(conn) == []
        assert {name: after[name] for name in before if name != "SchemaVersion"} == {
            name: values for name, values in before.items() if name != "SchemaVersion"}
        assert set(after) - set(before) == set(RUN_TABLES + V27_TABLES + V29_TABLES + V30_TABLES + V31_TABLES + V32_TABLES)
        assert_v29_source_maps_only(conn)
        assert_v30_source_maps_only(conn)
        assert_v31_receipt_maps_only(conn)
        assert_v32_empty(conn)
        assert all(after[name] == [] for name in RUN_TABLES + V27_TABLES)
        assert [row for row in source_ddl(conn) if row[1] in {old[1] for old in ddl_before}] == ddl_before
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    files = list(backups.glob(f"*before_migrate_v25_to_v{CURRENT_SCHEMA_VERSION}*.db"))
    assert len(files) == 1
    with connect(files[0]) as conn:
        assert get_schema_version(conn) == 25 and snapshot(conn) == before and source_ddl(conn) == ddl_before
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        assert snapshot(conn) == after
        v26.run(conn)
        assert snapshot(conn) == after
    assert len(list(backups.glob("*.db"))) == 1


def test_frozen_v25_and_current_schema_share_identical_old_objects(tmp_path, schema_path):
    path = tmp_path / "fresh.db"
    database.ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as fresh, seed_v25(tmp_path / "old.db") as old:
        old.execute("BEGIN")
        assert v26.run(old) == MigrationOutcome.APPLIED
        assert v27.run(old) == MigrationOutcome.APPLIED
        assert v28.run(old) == MigrationOutcome.APPLIED
        assert v29.run(old) == MigrationOutcome.APPLIED
        assert v30.run(old) == MigrationOutcome.APPLIED
        assert v31.run(old) == MigrationOutcome.APPLIED
        assert v32.run(old) == MigrationOutcome.APPLIED
        assert get_schema_version(old) == 25
        actual = {row[1]: row[3] for row in source_ddl(fresh)}
        expected = {row[1]: row[3] for row in source_ddl(old)}
        assert actual.keys() == expected.keys()
        assert all(_canonical_sql(actual[name] or "") == _canonical_sql(expected[name] or "") for name in actual)
        assert len(workbench_run_objects()) == 14


def test_v26_step_preserves_v25_and_installs_only_empty_run_tables(tmp_path):
    with seed_v25(tmp_path / "v26-step.db") as conn:
        before, ddl = snapshot(conn), source_ddl(conn)
        assert v26.run(conn) == MigrationOutcome.APPLIED
        after = snapshot(conn)
        assert get_schema_version(conn) == 25
        assert {name: after[name] for name in before} == before
        assert set(after) - set(before) == set(RUN_TABLES)
        assert all(after[name] == [] for name in RUN_TABLES)
        assert [row for row in source_ddl(conn) if row[1] in {old[1] for old in ddl}] == ddl
        assert set(current_schema_contract_issues(conn)) == (
            {"missing_template_lineage:" + name for name in template_lineage_objects()} |
            {"missing_trial_schema:" + name for name in workbench_trial_objects()} |
            {"missing_lineage_lookup:" + name for name in lineage_lookup_objects()} |
            missing_v29_issues() | missing_v30_issues() | missing_v31_issues() | missing_v32_issues())
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert v26.run(conn) == MigrationOutcome.APPLIED
        assert snapshot(conn) == after


@pytest.mark.parametrize("damage", [
    "DROP TRIGGER wb_run_admission_immutable", "DROP TRIGGER wb_run_state_transition",
    "DROP INDEX idx_wb_run_state", "DROP TABLE WorkbenchRunCandidateTasks",
])
def test_current_damaged_run_structure_rejected_without_repair(tmp_path, schema_path, damage):
    path = tmp_path / "damaged.db"
    database.ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        conn.execute(damage)
        conn.commit()
        before, ddl = snapshot(conn), source_ddl(conn)
    with pytest.raises(MigrationContractError, match="run_schema"):
        database.ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl


def test_partial_v25_run_structure_is_not_silently_completed(tmp_path, schema_path):
    path, backups = tmp_path / "partial.db", tmp_path / "backups"
    with seed_v25(path) as conn:
        conn.execute(workbench_run_objects()["WorkbenchRunJobs"])
        conn.commit()
        before, ddl = snapshot(conn), source_ddl(conn)
    with pytest.raises((MigrationContractError, RuntimeError), match="partial run ledger"):
        database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl
    assert not list(backups.glob("*.db"))


def test_v25_with_admission_but_missing_run_tables_is_not_recreated(tmp_path, schema_path):
    path = tmp_path / "missing-run.db"
    with seed_v25(path) as conn:
        conn.execute("""INSERT INTO WorkbenchCommandReceipts
            (request_key,receipt_ref,action,context_ref,input_hash,outcome_json)
            VALUES ('lost-run-request-0001',?,'scheduling.run','old-input',?,'{}')""", ("a" * 32, "b" * 64))
        conn.commit()
        before = snapshot(conn)
    with pytest.raises((MigrationContractError, RuntimeError), match="Run admissions remain"):
        database.ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert snapshot(conn) == before


def test_v26_failure_rolls_back_every_new_object(tmp_path, monkeypatch):
    with seed_v25(tmp_path / "rollback.db") as conn:
        before, ddl = snapshot(conn), source_ddl(conn)

        def fail(connection):
            install_workbench_run_schema(connection)
            raise RuntimeError("injected v26 failure")

        monkeypatch.setattr(v26, "install_workbench_run_schema", fail)
        with pytest.raises(RuntimeError, match="injected v26 failure"):
            v26.run(conn)
        assert snapshot(conn) == before and source_ddl(conn) == ddl


def test_future_schema_is_not_downgraded(tmp_path, schema_path):
    path = tmp_path / "future.db"
    database.ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        set_schema_version(conn, CURRENT_SCHEMA_VERSION + 1)
        conn.commit()
        before, ddl = snapshot(conn), source_ddl(conn)
    with pytest.raises(MigrationContractError, match=str(CURRENT_SCHEMA_VERSION + 1)):
        database.ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl


@pytest.mark.parametrize("label", (CURRENT_SCHEMA_VERSION, CURRENT_SCHEMA_VERSION + 1))
def test_old_shape_cannot_bypass_startup_with_current_or_future_label(tmp_path, schema_path, label):
    path, backups = tmp_path / "relabeled.db", tmp_path / "backups"
    with seed_v25(path) as conn:
        set_schema_version(conn, label)
        conn.commit()
        before, ddl = snapshot(conn), source_ddl(conn)
    with pytest.raises(MigrationContractError, match="run_schema|" + str(CURRENT_SCHEMA_VERSION + 1)):
        database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl
    assert not list(backups.glob("*.db"))
