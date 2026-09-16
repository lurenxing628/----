"""Real upgrade and backup; metadata mappings do not invent risk handling or adoption."""

import hashlib

import pytest

from core.infrastructure.database import ensure_schema
from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
    current_schema_contract_issues,
    get_schema_version,
)
from core.infrastructure.migrations import MIGRATIONS, v29
from core.infrastructure.workbench_calibration_adoption_schema import objects as calibration_objects
from core.infrastructure.workbench_dashboard_schema import objects as dashboard_objects
from tests.workbench.calibration_dashboard_migration_support import FIXTURE_V28, FIXTURE_V28_SHA, seed_v28
from tests.workbench.dashboard_external_migration_support import V31_TABLES, assert_v31_receipt_maps_only
from tests.workbench.legacy_migration_current_support import (
    V30_EMPTY_TABLES,
    V30_TABLES,
    V32_TABLES,
    assert_v30_source_maps_only,
    assert_v32_empty,
)
from tests.workbench.run_schema_migration_support import connect, snapshot, source_ddl


def added_tables():
    return {name for name, sql in {**calibration_objects(), **dashboard_objects()}.items() if sql.startswith("CREATE TABLE")}


def test_fixed_v28_and_fresh_current_storage(tmp_path, schema_path):
    assert hashlib.sha256(FIXTURE_V28.read_bytes()).hexdigest() == FIXTURE_V28_SHA
    assert MIGRATIONS[29] is v29.run
    path = tmp_path / "fresh.db"
    ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION and current_schema_contract_issues(conn) == []
        assert all(conn.execute('SELECT count(*) FROM "' + name + '"').fetchone()[0] == 0 for name in added_tables())


def test_real_v28_upgrade_preserves_old_typed_rows_and_all_persistent_identities(tmp_path, schema_path):
    path, backups = tmp_path / "old.db", tmp_path / "backups"
    with seed_v28(path) as conn:
        before, ddl = snapshot(conn), source_ddl(conn)
        assert get_schema_version(conn) == 28
        for name in ("WorkbenchRunCandidates", "WorkbenchTrialScenarios", "WorkbenchTemplateLineageOrigins",
                     "OperationExecutionEvents", "ScheduleHistory", "WorkbenchTaskRefs"):
            assert before[name], name
        batches = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND active=1").fetchall()
        tasks = conn.execute("SELECT ref FROM WorkbenchTaskRefs").fetchall()
        downtimes = conn.execute("SELECT count(*) FROM MachineDowntimes").fetchone()[0]
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        after = snapshot(conn)
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION and current_schema_contract_issues(conn) == []
        assert set(after) - set(before) == added_tables() | set(V30_TABLES + V31_TABLES + V32_TABLES)
        assert_v30_source_maps_only(conn)
        assert_v31_receipt_maps_only(conn)
        assert_v32_empty(conn)
        assert {key: after[key] for key in before if key != "SchemaVersion"} == {
            key: value for key, value in before.items() if key != "SchemaVersion"}
        old_names = {row[1] for row in ddl}
        assert [row for row in source_ddl(conn) if row[1] in old_names] == ddl
        expected = {(category, row[0], None) for row in batches for category in ("delivery", "material")}
        expected |= {(category, None, row[0]) for row in tasks for category in ("actual", "downtime")}
        assert set(map(tuple, conn.execute("SELECT category,batch_ref,task_ref FROM WorkbenchDashboardItems"))) == expected
        assert len(after["WorkbenchDashboardDowntimeRefs"]) == downtimes
        for name in added_tables() - {"WorkbenchDashboardItems", "WorkbenchDashboardDowntimeRefs"}:
            assert after[name] == [], name
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    copies = list(backups.glob(f"*before_migrate_v28_to_v{CURRENT_SCHEMA_VERSION}*.db"))
    assert len(copies) == 1
    with connect(copies[0]) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        assert snapshot(conn) == after
    assert len(list(backups.glob("*.db"))) == 1


def test_failed_v29_probe_leaves_old_database_and_sources_unchanged(tmp_path, schema_path, monkeypatch):
    path = tmp_path / "failure.db"
    with seed_v28(path) as conn:
        before, ddl = snapshot(conn), source_ddl(conn)
    install = v29.install_workbench_dashboard_schema

    def fail(conn):
        install(conn)
        raise RuntimeError("injected v29 failure after both installs")

    monkeypatch.setattr(v29, "install_workbench_dashboard_schema", fail)
    with pytest.raises(RuntimeError, match="injected v29"):
        ensure_schema(str(path), schema_path=schema_path, backup_dir=str(tmp_path / "backups"))
    with connect(path) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl


@pytest.mark.parametrize("table", ["WorkbenchCalibrationQuotaLocks", "WorkbenchDashboardStates"])
def test_current_partial_ledger_is_not_repaired(tmp_path, schema_path, table):
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


@pytest.mark.parametrize("damage", (
    "none", "missing", "guessed_batch", "retired", "non_created", "later_birth", "extra", "type",
    *V30_EMPTY_TABLES,
))
def test_old_upgrade_metadata_checker_accepts_only_birth_mapping_and_empty_facts(damage):
    # Independent source rows exercise the assertion, not the product installer.
    with connect(":memory:") as conn:
        conn.executescript("""
            CREATE TABLE BatchOperations(id INTEGER);
            INSERT INTO BatchOperations VALUES (7),(8),(9);
            CREATE TABLE WorkbenchPlanSourceRefs(ref,source_key,kind,active);
            INSERT INTO WorkbenchPlanSourceRefs VALUES ('born','7','operation',1),
                ('unknown','8','operation',1),('not-born','9','operation',1),('retired','7','operation',0);
            CREATE TABLE WorkbenchTemplateLineageEvents(event_id,operation_ref,batch_ref,event_type);
            INSERT INTO WorkbenchTemplateLineageEvents VALUES (1,'born','birth-batch','created'),
                (2,'born','later-batch','created'),(3,'not-born','changed-batch','updated');
            CREATE TABLE WorkbenchOutsourcingOperationOrigins(operation_ref,batch_ref);
            INSERT INTO WorkbenchOutsourcingOperationOrigins VALUES
                ('born','birth-batch'),('unknown',NULL),('not-born',NULL);
        """)
        for name in V30_EMPTY_TABLES:
            conn.execute('CREATE TABLE "' + name + '"(evidence)')
        mutations = {
            "missing": "DELETE FROM WorkbenchOutsourcingOperationOrigins WHERE operation_ref='unknown'",
            "guessed_batch": "UPDATE WorkbenchOutsourcingOperationOrigins SET batch_ref='current-batch' WHERE operation_ref='unknown'",
            "retired": "INSERT INTO WorkbenchOutsourcingOperationOrigins VALUES ('retired','birth-batch')",
            "non_created": "UPDATE WorkbenchOutsourcingOperationOrigins SET batch_ref='changed-batch' WHERE operation_ref='not-born'",
            "later_birth": "UPDATE WorkbenchOutsourcingOperationOrigins SET batch_ref='later-batch' WHERE operation_ref='born'",
            "extra": "INSERT INTO WorkbenchOutsourcingOperationOrigins VALUES ('invented',NULL)",
            "type": "UPDATE WorkbenchOutsourcingOperationOrigins SET batch_ref=CAST(batch_ref AS BLOB) WHERE operation_ref='born'",
        }
        mutations.update({name: 'INSERT INTO "' + name + '" VALUES (1)' for name in V30_EMPTY_TABLES})
        if damage == "none":
            assert_v30_source_maps_only(conn)
        else:
            conn.execute(mutations[damage])
            with pytest.raises(AssertionError):
                assert_v30_source_maps_only(conn)
