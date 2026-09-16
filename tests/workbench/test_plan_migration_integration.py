"""Real bootstrap/backup integration, without monkeypatching migration registration."""

import pytest

from core.infrastructure import database
from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
    current_schema_contract_issues,
    get_schema_version,
    is_truly_empty_db,
    set_schema_version,
)
from core.infrastructure.migrations import MIGRATIONS, v24, v25, v27, v28
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects
from core.infrastructure.workbench_plan_identity_schema import plan_identity_objects
from core.infrastructure.workbench_run_schema import RUN_TABLES, workbench_run_objects
from core.infrastructure.workbench_template_lineage_schema import template_lineage_objects
from core.infrastructure.workbench_trial_schema import workbench_trial_objects
from tests.workbench.dashboard_external_migration_support import V31_TABLES, assert_v31_receipt_maps_only
from tests.workbench.execution_ledger_migration_support import V27_TABLES
from tests.workbench.identity_metadata_support import connect_temp, copy_to_temp, table_rows
from tests.workbench.legacy_migration_current_support import (
    V30_TABLES,
    V32_TABLES,
    assert_v30_source_maps_only,
    assert_v32_empty,
)
from tests.workbench.plan_identity_support import (
    IDENTITY_TABLES,
    LEDGER_TABLES,
    all_refs,
    load_v23_schema,
    seed_plans,
    table_snapshot,
)
from tests.workbench.schema29_regression_support import V29_TABLES, assert_v29_source_maps_only


def test_real_fresh_schema_seeds_clock_and_fastforwards_without_migration(tmp_path, schema_path, monkeypatch):
    def migration_forbidden(*args, **kwargs):
        pytest.fail("A genuinely new database must not need a legacy migration")

    monkeypatch.setattr(database, "_migrate_with_backup_impl", migration_forbidden)
    path, backups = tmp_path / "new.db", tmp_path / "backups"
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    assert MIGRATIONS[28] is v28.run
    assert MIGRATIONS[27] is v27.run
    assert 26 in MIGRATIONS
    assert MIGRATIONS[24] is v24.run and MIGRATIONS[25] is v25.run
    with connect_temp(path) as conn:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION and current_schema_contract_issues(conn) == []
        assert table_rows(conn, "WorkbenchPlanIdentityClock") == [(1, 1)]
        assert table_rows(conn, "WorkbenchExecutionLedgerClock") == [(1, 1, 1)]
        assert all(table_rows(conn, table) == [] for table in LEDGER_TABLES[1:] + RUN_TABLES + V27_TABLES)
        assert table_rows(conn, "WorkbenchPlanSourceRefs") == table_rows(conn, "WorkbenchTaskRefs") == []
        assert is_truly_empty_db(conn)
    assert not list(backups.glob("*.db"))


@pytest.mark.parametrize("state", ["used_clock", "missing_clock", "reference_tombstone", "business_row"])
def test_empty_detection_does_not_hide_used_metadata_or_business_rows(schema_conn, state):
    conn = schema_conn
    assert is_truly_empty_db(conn)
    statements = {
        "used_clock": "UPDATE WorkbenchPlanIdentityClock SET revision=2",
        "missing_clock": "DELETE FROM WorkbenchPlanIdentityClock",
        "reference_tombstone": "INSERT INTO WorkbenchPlanSourceRefs(ref,kind,source_key,active) VALUES ('" + "a" * 48 + "','operation','old',0)",
        "business_row": "INSERT INTO Parts(part_no,part_name) VALUES ('retained','retained')",
    }
    conn.execute(statements[state])
    assert not is_truly_empty_db(conn)


def test_real_v23_upgrade_backs_up_all_rows_and_keeps_plan_refs_across_restart(mem_conn, tmp_path, schema_path):
    conn = load_v23_schema(mem_conn)
    seed_plans(conn)
    set_schema_version(conn, 23)
    conn.commit()
    before = table_snapshot(conn, exclude=("SchemaVersion",))
    backup_before = table_snapshot(conn)
    ddl_before = [tuple(row) for row in conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY name")]
    added_objects = (set(plan_identity_objects()) | set(execution_ledger_objects()) | set(workbench_run_objects()) |
                     set(template_lineage_objects()) | set(workbench_trial_objects()))
    assert not added_objects & {row[1] for row in ddl_before}
    path, backups = tmp_path / "old.db", tmp_path / "backups"
    copy_to_temp(conn, path)
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect_temp(path) as upgraded:
        assert get_schema_version(upgraded) == CURRENT_SCHEMA_VERSION and current_schema_contract_issues(upgraded) == []
        after = table_snapshot(upgraded, exclude=("SchemaVersion",))
        assert {name: after[name] for name in before} == before
        assert set(after) - set(before) == set(IDENTITY_TABLES + LEDGER_TABLES + RUN_TABLES + V27_TABLES + V29_TABLES + V30_TABLES + V31_TABLES + V32_TABLES)
        assert_v29_source_maps_only(upgraded)
        assert_v30_source_maps_only(upgraded)
        assert_v31_receipt_maps_only(upgraded)
        assert_v32_empty(upgraded)
        assert table_rows(upgraded, "WorkbenchExecutionLedgerClock") == [(1, 1, 1)]
        assert all(table_rows(upgraded, table) == [] for table in LEDGER_TABLES[1:] + RUN_TABLES + V27_TABLES)
        refs = all_refs(upgraded)
        assert refs and not upgraded.execute("PRAGMA foreign_key_check").fetchall()
    files = list(backups.glob(f"*before_migrate_v23_to_v{CURRENT_SCHEMA_VERSION}*.db"))
    assert len(files) == 1
    with connect_temp(files[0]) as backup:
        assert get_schema_version(backup) == 23
        assert table_snapshot(backup) == backup_before
        assert [tuple(row) for row in backup.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY name")] == ddl_before
        assert not added_objects & {row[0] for row in backup.execute("SELECT name FROM sqlite_master")}
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect_temp(path) as reopened:
        assert all_refs(reopened) == refs
        assert table_snapshot(reopened, exclude=("SchemaVersion",)) == after
    assert list(backups.glob("*.db")) == files


def test_current_database_missing_clock_fails_without_automatic_repair(tmp_path, schema_path):
    path = tmp_path / "damaged.db"
    database.ensure_schema(str(path), schema_path=schema_path)
    with connect_temp(path) as conn:
        conn.execute("DELETE FROM WorkbenchPlanIdentityClock")
        conn.commit()
        before = table_snapshot(conn)
    with pytest.raises(MigrationContractError, match="missing_workbench_plan_clock_state"):
        database.ensure_schema(str(path), schema_path=schema_path)
    with connect_temp(path) as conn:
        assert table_snapshot(conn) == before
