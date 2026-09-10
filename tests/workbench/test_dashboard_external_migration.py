"""Real v30 -> v31 startup, mandatory backup, rollback and no invented handling."""

import hashlib
import sqlite3
from contextlib import closing

import pytest

from core.infrastructure import database
from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
    current_schema_contract_issues,
    ensure_current_schema_contract,
    get_schema_version,
)
from core.infrastructure.migrations import MIGRATIONS, v31
from core.infrastructure.workbench_dashboard_external_schema import contract_issues, objects
from tests.workbench.calibration_dashboard_migration_support import canonical_object
from tests.workbench.dashboard_external_migration_support import (
    FIXTURE_V30,
    FIXTURE_V30_SHA,
    V31_TABLES,
    assert_v31_receipt_maps_only,
    external_case_for,
    fixed_v30_connection,
    missing_v31_issues,
    seed_v30,
)
from tests.workbench.dashboard_support import api, follow
from tests.workbench.run_schema_migration_support import connect, snapshot, source_ddl


def test_frozen_v30_and_fresh_current_share_exact_thirteen_object_extension(tmp_path, schema_path, monkeypatch):
    assert hashlib.sha256(FIXTURE_V30.read_bytes()).hexdigest() == FIXTURE_V30_SHA
    assert CURRENT_SCHEMA_VERSION == 31 and MIGRATIONS[31] is v31.run
    definitions = objects()
    assert len(definitions) == 13
    assert {name for name, sql in definitions.items() if sql.startswith("CREATE TABLE")} == set(V31_TABLES)
    assert sum(sql.startswith("CREATE TRIGGER") for sql in definitions.values()) == 10
    def forbidden(*args, **kwargs):
        pytest.fail("Fresh initialization must not run a legacy migration")
    monkeypatch.setattr(database, "_migrate_with_backup_impl", forbidden)
    path = tmp_path / "fresh.db"
    database.ensure_schema(str(path), schema_path=schema_path)
    with closing(connect(path)) as fresh, closing(fixed_v30_connection(tmp_path / "old.db")) as old:
        assert get_schema_version(fresh) == 31 and not current_schema_contract_issues(fresh)
        assert set(current_schema_contract_issues(old)) == missing_v31_issues()
        assert v31.run(old) == MigrationOutcome.APPLIED and get_schema_version(old) == 30
        assert list(map(canonical_object, source_ddl(fresh))) == list(map(canonical_object, source_ddl(old)))
        assert_v31_receipt_maps_only(fresh)
        assert not any(snapshot(fresh)[name] for name in V31_TABLES)
        before, changes = snapshot(fresh), fresh.total_changes
        fresh.execute("PRAGMA query_only=ON")
        assert contract_issues(fresh) == []
        assert snapshot(fresh) == before and fresh.total_changes == changes


def test_real_nonempty_v30_upgrade_preserves_every_typed_row_ddl_backup_and_restart(tmp_path, schema_path):
    path, backups = tmp_path / "old.db", tmp_path / "backups"
    with closing(seed_v30(path)) as conn:
        before, ddl = snapshot(conn), source_ddl(conn)
        for name in ("WorkbenchOutsourcingReceipts", "WorkbenchOutsourcingFacts", "WorkbenchOutsourcingMembers",
                     "WorkbenchDashboardStates", "WorkbenchDashboardHistory", "WorkbenchRunCandidates", "WorkbenchTrialScenarios",
                     "WorkbenchProductionReports", "OperationExecutionEvents", "ScheduleHistory", "Schedule",
                     "WorkbenchTaskRefs", "WorkbenchPlanSourceRefs", "WorkbenchEntityRefs", "WorkbenchCommandReceipts"):
            assert before[name], name
        assert len(before["WorkbenchOutsourcingFacts"]) == 4 and len(before["WorkbenchOutsourcingReceipts"]) == 3
        assert len(before["WorkbenchDashboardHistory"]) == 2
        case = external_case_for(path, conn)
        with case.app.app_context():
            summary = case.read()[0]["categories"]["external"]
            assert summary["handling_supported"] is False and summary["source_gap_count"] > 0
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with closing(connect(path)) as conn:
        after = snapshot(conn)
        assert get_schema_version(conn) == 31 and not current_schema_contract_issues(conn)
        assert set(after) - set(before) == set(V31_TABLES)
        assert {key: after[key] for key in before if key != "SchemaVersion"} == {
            key: rows for key, rows in before.items() if key != "SchemaVersion"}
        assert [row for row in source_ddl(conn) if row[1] in {old[1] for old in ddl}] == ddl
        assert_v31_receipt_maps_only(conn)
        case = external_case_for(path, conn)
        with case.app.app_context():
            workspace = case.read()[0]
            current = workspace["categories"]["external"]
            for key in ("risk_count", "known_risk_count", "unknown_count", "evaluation_gaps", "source_gap_count",
                        "overdue_count", "returned_count", "unregistered_count", "receipt_count"):
                assert current[key] == summary[key], key
            items = [row for row in workspace["items"] if row["category"] == "external"]
            assert len(items) == 2 and all(row["handling"]["status"] == "new" for row in items)
            assert all(case.history(row["item_ref"]) == [] for row in items)
        assert snapshot(conn) == after
    copies = list(backups.glob("*before_migrate_v30_to_v31*.db"))
    assert len(copies) == 1
    with closing(connect(copies[0])) as conn:
        assert get_schema_version(conn) == 30 and snapshot(conn) == before and source_ddl(conn) == ddl
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with closing(connect(path)) as conn:
        assert snapshot(conn) == after
        assert v31.run(conn) == MigrationOutcome.APPLIED and snapshot(conn) == after
    assert len(list(backups.glob("*.db"))) == 1


@pytest.mark.parametrize("boundary", ("step", "probe", "actual"))
def test_failure_after_install_rolls_back_every_object_mapping_and_original_fact(tmp_path, schema_path, monkeypatch, boundary):
    path, backups = tmp_path / "failure.db", tmp_path / "backups"
    with closing(seed_v30(path)) as conn:
        before, ddl = snapshot(conn), source_ddl(conn)
    original, calls = v31.install, []
    def fail(conn):
        original(conn)
        calls.append(conn.execute("PRAGMA database_list").fetchone()[2])
        assert not contract_issues(conn)
        assert_v31_receipt_maps_only(conn)
        if boundary != "actual" or len(calls) == 2:
            raise RuntimeError("injected v31 failure after installation and backfill")
    monkeypatch.setattr(v31, "install", fail)
    with pytest.raises(RuntimeError, match="injected v31"):
        if boundary == "step":
            with closing(connect(path)) as conn:
                v31.run(conn)
        else:
            database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with closing(connect(path)) as conn:
        assert get_schema_version(conn) == 30 and snapshot(conn) == before and source_ddl(conn) == ddl
    copies = list(backups.glob("*.db"))
    assert len(calls) == (2 if boundary == "actual" else 1)
    assert len(copies) == (1 if boundary == "actual" else 0)
    if boundary == "actual":
        assert calls[-1] == str(path) and calls[0] != str(path)
    if copies:
        with closing(connect(copies[0])) as conn:
            assert snapshot(conn) == before and source_ddl(conn) == ddl


@pytest.mark.parametrize("name", tuple(objects()))
def test_current31_missing_object_is_rejected_without_repair(tmp_path, schema_path, name):
    path = tmp_path / "damaged.db"
    database.ensure_schema(str(path), schema_path=schema_path)
    with closing(connect(path)) as conn:
        kind = objects()[name].split()[1]
        conn.execute("DROP " + kind + ' "' + name + '"')
        conn.commit()
        before, ddl = snapshot(conn), source_ddl(conn)
    with pytest.raises(MigrationContractError, match="dashboard_external_schema"):
        database.ensure_schema(str(path), schema_path=schema_path)
    with closing(connect(path)) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl


def test_new_receipt_maps_only_itself_without_inventing_handling_or_replacing_old_items(tmp_path, schema_path):
    path = tmp_path / "new-receipt.db"
    seed_v30(path).close()
    database.ensure_schema(str(path), schema_path=schema_path)
    with closing(connect(path)) as conn:
        before = snapshot(conn)
        mappings = list(map(tuple, conn.execute("SELECT item_ref,outsourcing_ref FROM WorkbenchDashboardExternalItems")))
        case = external_case_for(path, conn)
        with case.app.app_context():
            payload = case.shipments.payload()
            payload["target"]["operation_refs"] = [case.shipments.operation_ref("XO4")]
            preview = case.shipments.preview(payload)
            ref = case.shipments.confirm(preview, key="v31-new-receipt-0001")["data"]["outsourcing_ref"]
            item = next(row for row in case.read()[0]["items"] if row["category"] == "external" and row["source"]["outsourcing_ref"] == ref)
            assert item["handling"]["status"] == "new" and case.history(item["item_ref"]) == []
        assert_v31_receipt_maps_only(conn)
        after = snapshot(conn)
        new_mappings = list(map(tuple, conn.execute("SELECT item_ref,outsourcing_ref FROM WorkbenchDashboardExternalItems")))
        assert set(new_mappings) - set(mappings) == {(item["item_ref"], ref)}
        assert len(new_mappings) == len(mappings) + 1 and set(mappings) <= set(new_mappings)
        changed = {"WorkbenchOutsourcingReceipts", "WorkbenchOutsourcingMembers", "WorkbenchOutsourcingFacts",
                   "WorkbenchCommandReceipts", "WorkbenchDashboardExternalItems"}
        assert {key: rows for key, rows in before.items() if key not in changed} == {
            key: rows for key, rows in after.items() if key not in changed}


def test_explicit_v30_extension_and_recorded_handling_survive_real_upgrade_exactly(tmp_path, schema_path):
    path, backups = tmp_path / "extended-v30.db", tmp_path / "backups"
    with closing(seed_v30(path)) as conn:
        conn.execute("BEGIN")
        v31.install(conn)
        conn.commit()
        case = external_case_for(path, conn)
        with case.app.app_context():
            assert case.command(case.item("external"), follow(), key="v30-existing-external-0001")["result"] == "committed"
        before, ddl = snapshot(conn), source_ddl(conn)
        assert get_schema_version(conn) == 30 and before[V31_TABLES[1]] and before[V31_TABLES[2]]
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with closing(connect(path)) as conn:
        after = snapshot(conn)
        assert get_schema_version(conn) == 31 and not current_schema_contract_issues(conn)
        assert source_ddl(conn) == ddl
        assert {key: rows for key, rows in after.items() if key != "SchemaVersion"} == {
            key: rows for key, rows in before.items() if key != "SchemaVersion"}
    copies = list(backups.glob("*before_migrate_v30_to_v31*.db"))
    assert len(copies) == 1
    with closing(connect(copies[0])) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl
    database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with closing(connect(path)) as conn:
        assert snapshot(conn) == after and source_ddl(conn) == ddl
    assert len(list(backups.glob("*.db"))) == 1


@pytest.mark.parametrize("damage", ("partial", "missing_mapping", "lost_with_receipt"))
def test_v30_partial_extension_is_never_repaired_or_remapped(tmp_path, schema_path, damage):
    path, backups = tmp_path / "partial.db", tmp_path / "backups"
    with closing(seed_v30(path)) as conn:
        conn.execute("BEGIN")
        v31.install(conn)
        conn.commit()
        if damage == "partial":
            conn.execute("DROP TRIGGER wb_dashboard_external_history_no_update")
        elif damage == "missing_mapping":
            guard = objects()["wb_dashboard_external_items_no_delete"]
            conn.execute("DROP TRIGGER wb_dashboard_external_items_no_delete")
            conn.execute("DELETE FROM WorkbenchDashboardExternalItems WHERE item_ref=(SELECT MIN(item_ref) FROM WorkbenchDashboardExternalItems)")
            conn.execute(guard)
        else:
            case = external_case_for(path, conn)
            with case.app.app_context():
                case.command(case.item("external"), follow(), key="v30-lost-external-0001")
            for name, sql in objects().items():
                if sql.startswith("CREATE TRIGGER"):
                    conn.execute('DROP TRIGGER "' + name + '"')
            for name in reversed(V31_TABLES):
                conn.execute('DROP TABLE "' + name + '"')
        conn.commit()
        before, ddl = snapshot(conn), source_ddl(conn)
    with pytest.raises(RuntimeError, match="Cannot install or repair|mappings are missing|without their original ledger"):
        database.ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with closing(connect(path)) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl and get_schema_version(conn) == 30
    assert not list(backups.glob("*.db"))


@pytest.mark.parametrize("damage", ("none", "missing", "extra", "duplicate", "wrong_receipt", "type", "category", "alias", "states", "history"))
def test_additive_mapping_assertion_rejects_missing_guessed_typed_or_invented_evidence(damage):
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.executescript("""
            CREATE TABLE WorkbenchOutsourcingReceipts(outsourcing_ref);
            CREATE TABLE WorkbenchDashboardItems(item_ref);
            CREATE TABLE WorkbenchDashboardExternalItems(item_ref,category,outsourcing_ref);
            CREATE TABLE WorkbenchDashboardExternalStates(evidence);
            CREATE TABLE WorkbenchDashboardExternalHistory(evidence);
        """)
        conn.execute("INSERT INTO WorkbenchOutsourcingReceipts VALUES (?)", ("a" * 48,))
        conn.execute("INSERT INTO WorkbenchDashboardItems VALUES (?)", ("c" * 48,))
        conn.execute("INSERT INTO WorkbenchDashboardExternalItems VALUES (?,'external',?)", ("b" * 48, "a" * 48))
        mutations = {
            "missing": "DELETE FROM WorkbenchDashboardExternalItems",
            "extra": "INSERT INTO WorkbenchDashboardExternalItems VALUES ('invented','external','guessed')",
            "duplicate": "INSERT INTO WorkbenchDashboardExternalItems SELECT * FROM WorkbenchDashboardExternalItems",
            "wrong_receipt": "UPDATE WorkbenchDashboardExternalItems SET outsourcing_ref='unknown'",
            "type": "UPDATE WorkbenchDashboardExternalItems SET item_ref=CAST(item_ref AS BLOB)",
            "category": "UPDATE WorkbenchDashboardExternalItems SET category='delivery'",
            "alias": "UPDATE WorkbenchDashboardExternalItems SET item_ref=(SELECT item_ref FROM WorkbenchDashboardItems)",
            "states": "INSERT INTO WorkbenchDashboardExternalStates VALUES ('invented')",
            "history": "INSERT INTO WorkbenchDashboardExternalHistory VALUES ('invented')",
        }
        if damage == "none":
            assert_v31_receipt_maps_only(conn)
        else:
            conn.execute(mutations[damage])
            with pytest.raises(AssertionError):
                assert_v31_receipt_maps_only(conn)


def test_current31_wrong_trigger_ddl_is_read_only_fail_closed(tmp_path, schema_path):
    path = tmp_path / "invalid.db"
    database.ensure_schema(str(path), schema_path=schema_path)
    with closing(connect(path)) as conn:
        name = "wb_dashboard_external_receipt_insert"
        conn.execute("DROP TRIGGER " + name)
        conn.execute("CREATE TRIGGER " + name + " AFTER INSERT ON WorkbenchOutsourcingReceipts BEGIN SELECT 1; END")
        conn.commit()
        before, ddl, changes = snapshot(conn), source_ddl(conn), conn.total_changes
        conn.execute("PRAGMA query_only=ON")
        assert contract_issues(conn) == ["invalid_dashboard_external_schema:" + name]
        assert conn.total_changes == changes and snapshot(conn) == before and source_ddl(conn) == ddl
        conn.execute("PRAGMA query_only=OFF")
        with pytest.raises(MigrationContractError, match="invalid_dashboard_external_schema"):
            ensure_current_schema_contract(conn)
        assert snapshot(conn) == before and source_ddl(conn) == ddl


@pytest.mark.parametrize("upgraded", (False, True))
def test_dashboard_get_never_installs_helper_or_seeds_handling(tmp_path, schema_path, monkeypatch, upgraded):
    path = tmp_path / "readonly.db"
    with closing(seed_v30(path)) as conn:
        pass
    if upgraded:
        database.ensure_schema(str(path), schema_path=schema_path)
    with closing(connect(path)) as conn:
        before, ddl = snapshot(conn), source_ddl(conn)
        case = external_case_for(path, conn)
        def query_only(path):
            connection = database.get_connection(str(path))
            connection.execute("PRAGMA query_only=ON")
            return connection
        client = api(case, monkeypatch, connect_factory=query_only)
        response = client.get("/api/workbench/v1/dashboard")
        assert response.status_code == 200, response.get_json()
        data = response.get_json()["data"]
        query = {"snapshot_ref": response.get_json()["meta"]["snapshot_ref"]}
        assert data["categories"]["external"]["handling_supported"] is upgraded
        assert data["categories"]["external"]["source_gap_count"] > 0
        for item in data["items"]:
            if item["category"] == "external":
                assert client.get("/api/workbench/v1/dashboard/items/" + item["item_ref"], query_string=query).status_code == 200
                assert client.get("/api/workbench/v1/dashboard/items/" + item["item_ref"] + "/history", query_string=query).status_code == 200
        assert snapshot(conn) == before and source_ddl(conn) == ddl
