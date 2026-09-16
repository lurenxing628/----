"""Actual frozen v29 -> current upgrade retains facts and never invents receipts."""

import hashlib

import pytest

from core.infrastructure.database import ensure_schema
from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
    current_schema_contract_issues,
    get_schema_version,
)
from core.infrastructure.migrations import MIGRATIONS, v30
from core.infrastructure.workbench_outsourcing_schema import objects as outsourcing_objects
from core.infrastructure.workbench_plan_identity_write_guard import objects as guard_objects
from tests.workbench.dashboard_external_migration_support import V31_TABLES, assert_v31_receipt_maps_only
from tests.workbench.legacy_migration_current_support import V32_TABLES, assert_v32_empty
from tests.workbench.outsourcing_identity_migration_support import (
    FIXTURE_V29,
    FIXTURE_V29_SHA,
    expected_origins,
    seed_v29,
)
from tests.workbench.run_schema_migration_support import connect, snapshot, source_ddl


def added_tables():
    return {name for name, sql in outsourcing_objects().items() if sql.startswith("CREATE TABLE")}


def test_fixed_v29_and_fresh_current_outsourcing_storage(tmp_path, schema_path):
    assert hashlib.sha256(FIXTURE_V29.read_bytes()).hexdigest() == FIXTURE_V29_SHA
    assert CURRENT_SCHEMA_VERSION == 32 and MIGRATIONS[30] is v30.run
    path = tmp_path / "fresh.db"
    ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION and current_schema_contract_issues(conn) == []
        assert_v31_receipt_maps_only(conn)
        assert_v32_empty(conn)
        assert all(conn.execute('SELECT count(*) FROM "' + name + '"').fetchone()[0] == 0 for name in added_tables())
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
        assert names >= set(outsourcing_objects()) | set(guard_objects())


def test_real_v29_upgrade_retains_all_old_rows_and_only_maps_recorded_births(tmp_path, schema_path):
    path, backups = tmp_path / "old.db", tmp_path / "backups"
    with seed_v29(path) as conn:
        before, ddl, origins = snapshot(conn), source_ddl(conn), expected_origins(conn)
        assert get_schema_version(conn) == 29
        for name in ("WorkbenchRunCandidates", "WorkbenchTrialScenarios", "WorkbenchTemplateLineageOrigins",
                     "WorkbenchDashboardItems", "OperationExecutionEvents", "ScheduleHistory", "WorkbenchTaskRefs"):
            assert before[name], name
        assert any(batch is None for _, batch in origins)
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        after = snapshot(conn)
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION and current_schema_contract_issues(conn) == []
        assert set(after) - set(before) == added_tables() | set(V31_TABLES + V32_TABLES)
        assert_v31_receipt_maps_only(conn)
        assert_v32_empty(conn)
        assert {key: after[key] for key in before if key != "SchemaVersion"} == {
            key: value for key, value in before.items() if key != "SchemaVersion"}
        old_names = {row[1] for row in ddl}
        assert [row for row in source_ddl(conn) if row[1] in old_names] == ddl
        assert set(map(tuple, conn.execute("SELECT operation_ref,batch_ref FROM WorkbenchOutsourcingOperationOrigins"))) == origins
        for name in added_tables() - {"WorkbenchOutsourcingOperationOrigins"}:
            assert after[name] == [], name
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    copies = list(backups.glob(f"*before_migrate_v29_to_v{CURRENT_SCHEMA_VERSION}*.db"))
    assert len(copies) == 1
    with connect(copies[0]) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        assert snapshot(conn) == after
    assert len(list(backups.glob("*.db"))) == 1


def test_failed_v30_install_rolls_back_both_slices_without_altering_old_evidence(tmp_path, schema_path, monkeypatch):
    path = tmp_path / "failure.db"
    with seed_v29(path) as conn:
        before, ddl = snapshot(conn), source_ddl(conn)
    install = v30.install_workbench_outsourcing_schema

    def fail(conn):
        install(conn)
        raise RuntimeError("injected v30 failure after guards and outsourcing installation")

    monkeypatch.setattr(v30, "install_workbench_outsourcing_schema", fail)
    with pytest.raises(RuntimeError, match="injected v30"):
        ensure_schema(str(path), schema_path=schema_path, backup_dir=str(tmp_path / "backups"))
    with connect(path) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl


@pytest.mark.parametrize("kind,name", [("TRIGGER", "wb_plan_source_ref_insert_guard"),
                                      ("TRIGGER", "wb_outsourcing_fact_sequence"),
                                      ("TABLE", "WorkbenchOutsourcingFacts")])
def test_current_missing_guard_or_outsourcing_evidence_is_not_repaired(tmp_path, schema_path, kind, name):
    path = tmp_path / "damaged.db"
    ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        conn.execute("DROP " + kind + ' "' + name + '"')
        conn.commit()
        before, ddl = snapshot(conn), source_ddl(conn)
    with pytest.raises(MigrationContractError):
        ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl
