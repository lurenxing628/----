"""Real v26-to-current migration, exact old rows/types/refs and no invented origins."""

import hashlib

import pytest

from core.infrastructure.database import ensure_schema
from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
    current_schema_contract_issues,
    get_schema_version,
    is_truly_empty_db,
    set_schema_version,
)
from core.infrastructure.migrations import v27
from core.infrastructure.workbench_template_lineage_schema import template_lineage_objects
from core.infrastructure.workbench_trial_schema import workbench_trial_objects
from tests.workbench.dashboard_external_migration_support import V31_TABLES, assert_v31_receipt_maps_only
from tests.workbench.legacy_migration_current_support import (
    V30_TABLES,
    V32_TABLES,
    assert_v30_source_maps_only,
    assert_v32_empty,
)
from tests.workbench.run_schema_migration_support import connect, snapshot, source_ddl
from tests.workbench.schema29_regression_support import V29_TABLES, assert_v29_source_maps_only
from tests.workbench.trial_lineage_migration_support import FIXTURE_V26, seed_v26


def new_tables():
    return {name for name, ddl in {**template_lineage_objects(), **workbench_trial_objects()}.items()
            if ddl.startswith("CREATE TABLE")}


def test_fixed_v26_archive_is_unchanged():
    assert hashlib.sha256(FIXTURE_V26.read_bytes()).hexdigest() == "3b1565dffc6f35c6e929d0d96a9df27377865b885132ad57ffeb05e435bc2a6c"


def test_fresh_database_has_empty_trial_and_lineage_no_backfill(tmp_path, schema_path):
    path = tmp_path / "fresh.db"
    ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION
        assert current_schema_contract_issues(conn) == [] and is_truly_empty_db(conn)
        for table in new_tables():
            assert conn.execute('SELECT count(*) FROM "' + table + '"').fetchone()[0] == 0


def test_real_upgrade_keeps_completed_runs_old_execution_rows_types_and_all_refs(tmp_path, schema_path):
    path, backups = tmp_path / "existing.db", tmp_path / "backups"
    with seed_v26(path) as conn:
        before, ddl = snapshot(conn), source_ddl(conn)
        assert get_schema_version(conn) == 26
        assert len(before["WorkbenchRunJobs"]) == 1 and len(before["WorkbenchRunCandidates"]) == 4
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        after = snapshot(conn)
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION and current_schema_contract_issues(conn) == []
        assert set(after) - set(before) == new_tables() | set(V29_TABLES + V30_TABLES + V31_TABLES + V32_TABLES)
        assert_v29_source_maps_only(conn)
        assert_v30_source_maps_only(conn)
        assert_v31_receipt_maps_only(conn)
        assert_v32_empty(conn)
        assert {name: after[name] for name in before if name != "SchemaVersion"} == {
            name: rows for name, rows in before.items() if name != "SchemaVersion"}
        assert all(after[name] == [] for name in new_tables())
        assert [row for row in source_ddl(conn) if row[1] in {item[1] for item in ddl}] == ddl
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    files = list(backups.glob(f"*before_migrate_v26_to_v{CURRENT_SCHEMA_VERSION}*.db"))
    assert len(files) == 1
    with connect(files[0]) as conn:
        assert get_schema_version(conn) == 26
        assert snapshot(conn) == before and source_ddl(conn) == ddl
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        assert snapshot(conn) == after
    assert len(list(backups.glob("*.db"))) == 1


def test_new_schema_rollback_keeps_every_v26_fact_and_object(tmp_path, monkeypatch):
    with seed_v26(tmp_path / "rollback.db") as conn:
        before, ddl = snapshot(conn), source_ddl(conn)
        install = v27.install_workbench_trial_schema

        def fail(connection):
            install(connection)
            raise RuntimeError("injected v27 failure")

        monkeypatch.setattr(v27, "install_workbench_trial_schema", fail)
        with pytest.raises(RuntimeError, match="injected v27"):
            v27.run(conn)
        assert snapshot(conn) == before and source_ddl(conn) == ddl


@pytest.mark.parametrize("table", ["WorkbenchTemplateLineageOrigins", "WorkbenchTrialRows"])
def test_current_partial_structure_is_not_repaired(tmp_path, schema_path, table):
    path = tmp_path / "damaged.db"
    ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        conn.execute('DROP TABLE "' + table + '"')
        conn.commit()
        before, ddl = snapshot(conn), source_ddl(conn)
    with pytest.raises(MigrationContractError):
        ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl


def test_future_version_is_never_downgraded(tmp_path, schema_path):
    path = tmp_path / "future.db"
    ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        set_schema_version(conn, CURRENT_SCHEMA_VERSION + 1)
        conn.commit()
        before = snapshot(conn)
    with pytest.raises(MigrationContractError, match=str(CURRENT_SCHEMA_VERSION + 1)):
        ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert snapshot(conn) == before
