"""Restore owns data contracts; current startup owns structure only."""

import logging
import sys
from datetime import datetime

import pytest

from core.infrastructure import database
from core.infrastructure.migration_state import MigrationContractError
from core.infrastructure.single_pass_indexes_schema import ADDED
from tests.workbench.plan_catalog_support import (
    ensure_history_head,
    insert_schedule_row,
    insert_schedule_rows,
    sync_history_from_schedule,
)

LOGGER = logging.getLogger(__name__)


def _plan(conn):
    conn.executescript("""INSERT INTO Parts(part_no,part_name) VALUES ('P','Part');
        INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B','P',1);
        INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) VALUES (1,'B-1','B',1,'Turning');""")
    ensure_history_head(conn, 1, strategy="test", schedule_time="2026-10-15T08:00:00")
    insert_schedule_row(conn, 1, 1, "2026-10-15T08:00:00", "2026-10-15T09:00:00", schedule_id=1)


def _drop_history_head_unconstrained(path: str) -> None:
    import sqlite3

    raw = sqlite3.connect(path)
    try:
        raw.execute("PRAGMA foreign_keys = OFF")
        raw.execute("DELETE FROM ScheduleHistory")
        raw.commit()
    finally:
        raw.close()


def test_current_startup_checks_structure_only_and_full_restore_checks_history_head(tmp_path, monkeypatch):
    path = str(tmp_path / "current.db")
    database.ensure_schema(path, LOGGER)
    with database.get_connection(path) as conn:
        _plan(conn)
    _drop_history_head_unconstrained(path)
    statements = []
    connect = database.get_connection

    def observed(path):
        conn = connect(path)
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(database, "get_connection", observed)
    database.ensure_schema(path, LOGGER)
    assert not any("__schema_probe" in sql for sql in statements)
    with pytest.raises(MigrationContractError, match="missing ScheduleHistory head"):
        database.ensure_schema(path, LOGGER, full_data=True)
    with connect(path) as conn:
        ensure_history_head(conn, 1, strategy="test", schedule_time="2026-10-15T08:00:00")
        sync_history_from_schedule(conn, 1)
    database.ensure_schema(path, LOGGER, full_data=True)


def test_single_pass_indexes_are_present_and_used_for_single_column_lookups(tmp_path):
    path = str(tmp_path / "current.db")
    database.ensure_schema(path, LOGGER)
    with database.get_connection(path) as conn:
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert set(ADDED) <= indexes
        assert {"idx_part_operations_part", "idx_batch_operations_batch"} <= indexes
        for table, column, name in (("BatchMaterials", "batch_id", "idx_batch_materials_batch"),
                                    ("BatchOperations", "supplier_id", "idx_batch_operations_supplier"),
                                    ("PartOperations", "supplier_id", "idx_part_operations_supplier")):
            plan = conn.execute("EXPLAIN QUERY PLAN SELECT id FROM " + table + " WHERE " + column + "=?", ("key",))
            assert any(name in row[3] for row in plan)


def test_actual_restore_rolls_back_a_current_schema_backup_missing_its_history_head(tmp_path):
    from core.infrastructure.backup import BackupManager
    from core.services.system.backup_restore import run_backup_restore

    path = str(tmp_path / "live.db")
    database.ensure_schema(path, LOGGER)
    with database.get_connection(path) as conn:
        _plan(conn)
    manager = BackupManager(path, str(tmp_path / "backups"), logger=LOGGER)
    source = manager.backup(suffix="external")
    _drop_history_head_unconstrained(source)
    result = run_backup_restore(filename="external", backup_path=source, database_path=path,
        manager=manager, logger=logging.getLogger(__name__),
        ensure_schema_func=database.ensure_schema)
    assert result.result.code == "verify_failed_rolled_back"
    with database.get_connection(path) as conn:
        assert conn.execute("SELECT version FROM ScheduleHistory").fetchone()[0] == 1


def test_retained_sql_readers_use_integer_endpoints_without_row_udf_parsing(tmp_path):
    from datetime import datetime

    from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository

    path = str(tmp_path / "time-readers.db")
    database.ensure_schema(path, LOGGER)
    conn = database.get_connection(path)
    try:
        _plan(conn)
        conn.executescript("""INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name)
                VALUES (2,'B-2','B',2,'Turning'),(3,'B-3','B',3,'Turning');
            UPDATE Batches SET due_date='2026-10-15';""")
        insert_schedule_rows(
            conn,
            1,
            [
                {"id": 2, "op_id": 2, "start_time": "2026-10-15T09:00:00", "end_time": "2026-10-15T09:30:00"},
                {"id": 3, "op_id": 3, "start_time": "2026-10-15T08:00:00.123456", "end_time": "2026-10-15T08:00:00.123456"},
            ],
        )
        conn.commit()
        repo = SchedulePlanQueryRepository(conn)
        common = {"version": 1}
        rows = repo.list_detail_rows_between(**common, start=datetime(2026, 10, 15, 8), end=datetime(2026, 10, 15, 10))
        assert len(rows) == 3
        span = repo.get_plan_time_span(**common)
        assert span is not None
        assert datetime.fromisoformat(span["start_time"]) == datetime(2026, 10, 15, 8, 0)
        assert datetime.fromisoformat(span["end_time"]) == datetime(2026, 10, 15, 9, 30)
        overdue = repo.list_overdue_base_rows(**common)
        assert datetime.fromisoformat(overdue[0]["finish_time"]) == datetime(2026, 10, 15, 9, 30)
    finally:
        conn.close()


def test_startup_captures_journal_once_and_wsgi_only_observes_memory(db_env, tmp_path, monkeypatch):
    from types import SimpleNamespace

    from core.services.workbench.facts.system_journal import SystemMaintenanceJournal
    from web.bootstrap import factory, workbench_system_restore
    from web.bootstrap.launcher_paths import current_runtime_owner
    from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
    from web.bootstrap.workbench_run_lifecycle import install_run_lifecycle
    from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime

    monkeypatch.setenv("APS_ENV", "production")
    records, captures = SystemMaintenanceJournal.records, []

    def capture(journal, **kwargs):
        captures.append(journal.directory)
        return records(journal, **kwargs)

    monkeypatch.setattr(SystemMaintenanceJournal, "records", capture)
    scope = str(tmp_path / "launcher")
    payload = acquire_runtime_lock(scope, owner=current_runtime_owner(), exe_path=sys.executable, db_path=db_env)
    runtime = gate = None
    try:
        app = factory.create_app_core()
        gate = app.extensions["workbench_request_lifecycle"]
        assert app.extensions["workbench_startup_maintenance_records"] == []
        runtime = install_run_lifecycle(SimpleNamespace(install_run_runtime=install_workbench_run_runtime),
                                        app, {"payload": payload})
        controller = app.extensions["workbench_system_restore_host"]
        assert runtime.ready and len(captures) == 1
        assert "workbench_startup_maintenance_records" not in app.extensions
        calls = {"ownership": 0, "open_maintenance": 0, "presentation_maintenance": 0}
        verify = controller.verify
        boundary = factory.is_maintenance_window_active
        presentation = workbench_system_restore.is_maintenance_window_active

        def ownership():
            calls["ownership"] += 1
            return verify()

        def at_open(*args, **kwargs):
            calls["open_maintenance"] += 1
            return boundary(*args, **kwargs)

        def at_presentation(*args, **kwargs):
            calls["presentation_maintenance"] += 1
            return presentation(*args, **kwargs)

        monkeypatch.setattr(controller, "verify", ownership)
        monkeypatch.setattr(factory, "is_maintenance_window_active", at_open)
        monkeypatch.setattr(workbench_system_restore, "is_maintenance_window_active", at_presentation)
        client = app.test_client()
        assert client.get("/api/workbench/v1/not-found", buffered=True).status_code == 404
        assert client.get("/system/health", buffered=True).status_code == 200
        assert calls == {"ownership": 0, "open_maintenance": 1, "presentation_maintenance": 0}
        response = client.get("/api/workbench/v1/system/restore-host", buffered=True)
        assert response.status_code == 200 and response.get_json()["data"]["host"]["operations_available"]
        assert calls == {"ownership": 1, "open_maintenance": 1, "presentation_maintenance": 1}
        assert len(captures) == 1
    finally:
        if runtime is not None:
            assert runtime.shutdown(timeout=15)
        if gate is not None:
            assert gate.shutdown(timeout=15)
        release_runtime_lock(scope, expected_payload=payload)


def test_lifecycle_enters_recovery_without_recapturing_startup_journal(db_env, tmp_path, monkeypatch):
    from types import SimpleNamespace

    from core.services.workbench.facts.system_journal import SystemMaintenanceJournal, system_journal_directory
    from web.bootstrap import factory
    from web.bootstrap.launcher_paths import current_runtime_owner
    from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
    from web.bootstrap.workbench_run_lifecycle import install_run_lifecycle, stop_run_runtime
    from web.bootstrap.workbench_system_restore_recovery import (
        RECOVERY,
        WorkbenchSystemRestoreRecoveryHost,
    )

    SystemMaintenanceJournal(system_journal_directory(db_env), db_env).begin(
        "pending-startup-request-001", "create", {}, now=datetime.now())
    original, captures = SystemMaintenanceJournal.records, []

    def records(journal, **kwargs):
        captures.append(journal.directory)
        return original(journal, **kwargs)

    monkeypatch.setattr(SystemMaintenanceJournal, "records", records)
    scope = str(tmp_path / "recovery-launcher")
    payload = acquire_runtime_lock(scope, owner=current_runtime_owner(), exe_path=sys.executable, db_path=db_env)
    runtime = None
    try:
        monkeypatch.setenv("APS_ENV", "production")
        app = factory.create_app_core()
        assert app.extensions[RECOVERY]
        state = {"payload": payload}
        deps = SimpleNamespace(install_run_runtime=lambda *args, **kwargs: pytest.fail("Recovery started a worker"))
        runtime = install_run_lifecycle(deps, app, state)
        assert isinstance(runtime, WorkbenchSystemRestoreRecoveryHost)
        assert app.extensions[RECOVERY] and not runtime.ready
        assert state["runtime"] is runtime
        assert len(captures) == 1
        assert app.test_client().get("/api/workbench/v1/system/restore-host").get_json()["data"]["host"]["restart_required"]
    finally:
        if runtime is not None:
            stop_run_runtime(runtime)
        release_runtime_lock(scope, expected_payload=payload)


def test_source_revision_triggers_run_on_updates_of_machines_hours_and_downtimes(tmp_path):
    """修订号触发器按列清单比较新旧行：清单里留着已删的列，建库和 INSERT 都能过，UPDATE 才报错。"""
    from datetime import datetime

    from core.infrastructure.workbench_source_revisions_schema import select_source_revisions
    from core.shared.local_datetime import datetime_to_us

    path = str(tmp_path / "revisions.db")
    database.ensure_schema(path, LOGGER)
    with database.get_connection(path) as conn:
        _plan(conn)
        operation_ref, task_ref = conn.execute("SELECT operation_ref, task_ref FROM Schedule").fetchone()
        plan_ref = conn.execute("SELECT plan_ref FROM ScheduleHistory").fetchone()[0]
        start_us = datetime_to_us(datetime(2026, 10, 15, 8))
        conn.execute("INSERT INTO Machines(machine_id, name) VALUES ('M1', 'Lathe')")
        conn.execute(
            "INSERT INTO MachineDowntimes(machine_id, start_time, end_time, start_us, end_us, reason_code) "
            "VALUES ('M1', '2026-10-15 08:00:00', '2026-10-15 09:00:00', ?, ?, 'maintenance')",
            (start_us, start_us + 3600 * 10**6),
        )
        conn.execute(
            "INSERT INTO WorkbenchProductionReports(report_ref, report_no, operation_ref, recorded_against_task_ref, "
            "recorded_against_plan_ref, source, recorded_at, effective_processing_hours) "
            "VALUES (?, 'R1', ?, ?, ?, 'manual', '2026-10-15T09:00:00', '0.1')",
            ("a" * 48, operation_ref, task_ref, plan_ref),
        )
        keys = ("machines", "machine_downtimes", "execution_ledger")
        before = select_source_revisions(conn, keys)
        conn.execute("UPDATE Machines SET name = 'Lathe 2' WHERE machine_id = 'M1'")
        conn.execute("UPDATE MachineDowntimes SET start_us = start_us + 60 * 1000000 WHERE machine_id = 'M1'")
        conn.execute("UPDATE WorkbenchProductionReports SET effective_processing_hours = '0.3' WHERE report_no = 'R1'")
        assert select_source_revisions(conn, keys) == {key: before[key] + 1 for key in keys}


@pytest.mark.parametrize("statement", [
    "INSERT INTO Machines(machine_id, name, status) VALUES ('M2', 'Mill', 'Active')",
    "INSERT INTO OperatorMachine(operator_id, machine_id, is_primary) VALUES ('O1', 'M1', '主操')",
    "INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_name) VALUES ('  ', 'B', 2, 'Turning')",
    "INSERT INTO MachineDowntimes(machine_id, start_time, end_time, start_us, end_us, reason_code) "
    "VALUES ('M1', '2026-10-15 08:00:00', '2026-10-15 08:00:00', 1, 1, 'maintenance')",
    "UPDATE Schedule SET is_point_event = 1",
], ids=["status-alias", "primary-alias", "blank-op-code", "empty-downtime", "point-event-with-duration"])
def test_storage_rejects_non_canonical_enum_values_and_time_shapes(tmp_path, statement):
    """存储只收规范值：别名只在导入入口翻译，读侧因此不再为脏值留分支。"""
    import sqlite3

    path = str(tmp_path / "checks.db")
    database.ensure_schema(path, LOGGER)
    with database.get_connection(path) as conn:
        _plan(conn)
        conn.execute("INSERT INTO Machines(machine_id, name) VALUES ('M1', 'Lathe')")
        conn.execute("INSERT INTO Operators(operator_id, name) VALUES ('O1', 'Worker')")
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            conn.execute(statement)


@pytest.mark.parametrize("statement", [
    "UPDATE Schedule SET start_us = start_us + 0.5",
    "UPDATE Schedule SET end_us = 'later'",
    "UPDATE Schedule SET end_us = 253402300800000000",
    "UPDATE MachineDowntimes SET end_us = 1.0e20",
    "UPDATE MachineDowntimes SET end_us = 'later'",
    "UPDATE ScheduleHistory SET op_count = 0.5",
    "UPDATE ScheduleHistory SET gantt_node_count = -1",
    "UPDATE ScheduleHistory SET op_count = 9007199254740992",
], ids=["fractional-us", "text-us", "beyond-datetime-max", "beyond-int64", "downtime-text-us", "fractional-count",
        "negative-count", "count-beyond-2^53"])
def test_storage_types_microsecond_and_count_columns_as_exact_integers(tmp_path, statement):
    """INTEGER 亲和存得下小数、非数字文本和超出 int64 的数，先后 CHECK 也拦不住（整数 < 文本）；列上的类型约束拦住，
    读侧因此直接用库里的值。"""
    import sqlite3
    from datetime import datetime

    from core.shared.local_datetime import datetime_to_us

    path = str(tmp_path / "integers.db")
    database.ensure_schema(path, LOGGER)
    with database.get_connection(path) as conn:
        _plan(conn)
        conn.execute("INSERT INTO Machines(machine_id, name) VALUES ('M1', 'Lathe')")
        start_us = datetime_to_us(datetime(2026, 10, 15, 8))
        conn.execute(
            "INSERT INTO MachineDowntimes(machine_id, start_time, end_time, start_us, end_us, reason_code) "
            "VALUES ('M1', '2026-10-15 08:00:00', '2026-10-15 09:00:00', ?, ?, 'maintenance')",
            (start_us, start_us + 3600 * 10**6),
        )
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            conn.execute(statement)


def _cycles(conn):
    """One row in each table that stores an external cycle in days."""
    conn.executescript("""INSERT INTO Suppliers(supplier_id, name, default_days) VALUES ('S', 'Supplier', 2);
        INSERT INTO ExternalGroups(group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id)
            VALUES ('G', 'P', 1, 1, 'merged', 2, 'S');
        INSERT INTO PartOperations(part_no, seq, op_type_name, source, supplier_id, ext_days, ext_group_id)
            VALUES ('P', 1, 'Heat', 'external', 'S', 2, 'G');""")


_CYCLE_COLUMNS = [("Suppliers", "default_days"), ("PartOperations", "ext_days"), ("ExternalGroups", "total_days"),
                  ("BatchOperations", "ext_days")]


@pytest.mark.parametrize("value", [0, -1, 36500.5, "9e999", "'later'", "X'00'"],
                         ids=["zero", "negative", "beyond-100-years", "inf", "text", "blob"])
@pytest.mark.parametrize(("table", "column"), _CYCLE_COLUMNS)
def test_storage_types_external_cycle_columns_as_days_in_one_century(tmp_path, table, column, value):
    """REAL 亲和存得下文本、±Inf、BLOB 和超过百年的数；列上的 CHECK 按写入的同一值域 (0, 36500] 天拦住，读侧直接用库里的值。"""
    import sqlite3

    path = str(tmp_path / "cycles.db")
    database.ensure_schema(path, LOGGER)
    with database.get_connection(path) as conn:
        _plan(conn)
        _cycles(conn)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            conn.execute("UPDATE " + table + " SET " + column + " = " + str(value))


def test_storage_keeps_in_range_cycles_and_bumps_their_source_revisions(tmp_path):
    """100 年本身与小数周期照收；还没设周期（NULL）只有供应商默认周期不收；改周期照常推进修订号。"""
    import sqlite3

    from core.infrastructure.workbench_source_revisions_schema import select_source_revisions

    path = str(tmp_path / "cycles.db")
    database.ensure_schema(path, LOGGER)
    with database.get_connection(path) as conn:
        _plan(conn)
        _cycles(conn)
        keys = ("suppliers", "part_operations", "external_groups", "batch_operations")
        before = select_source_revisions(conn, keys)
        for table, column in _CYCLE_COLUMNS:
            conn.execute("UPDATE " + table + " SET " + column + " = 36500")
        after = select_source_revisions(conn, keys)
        assert all(after[key] > before[key] for key in keys)
        for table, column in _CYCLE_COLUMNS:
            conn.execute("UPDATE " + table + " SET " + column + " = 0.25")
            assert conn.execute("SELECT typeof(" + column + "), " + column + " FROM " + table).fetchone()[:] == ("real", 0.25)
        for table, column in _CYCLE_COLUMNS[1:]:
            conn.execute("UPDATE " + table + " SET " + column + " = NULL")
        with pytest.raises(sqlite3.IntegrityError, match="constraint failed"):
            conn.execute("UPDATE Suppliers SET default_days = NULL")


def _context_and_arrival(conn):
    """One batch external operation with its frozen merged-group context, and one material arrival and review."""
    _cycles(conn)
    conn.executescript("""INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_name, source, supplier_id, ext_days)
            VALUES ('B-ext', 'B', 1, 'Heat', 'external', 'S', 2);
        INSERT INTO Materials(material_id, name) VALUES ('MAT', 'Steel');
        INSERT INTO BatchMaterials(id, batch_id, material_id, required_qty) VALUES (1, 'B', 'MAT', 1);
        INSERT INTO BatchMaterialArrivals(requirement_id, arrival_date, quantity) VALUES (1, '2026-10-15', 1);
        INSERT INTO BatchMaterialReviews(requirement_id, batch_quantity) VALUES (1, 5);""")
    assert conn.execute("SELECT merge_mode, total_days FROM BatchExternalContexts").fetchone()[:] == ("merged", 2.0)


@pytest.mark.parametrize(("table", "column", "value"), [
    ("BatchExternalContexts", "merge_mode", "'Merged'"),
    ("BatchExternalContexts", "merge_mode", "1"),
    ("BatchExternalContexts", "total_days", "0"),
    ("BatchExternalContexts", "total_days", "'later'"),
    ("BatchMaterialArrivals", "quantity", "'later'"),
    ("BatchMaterialArrivals", "quantity", "9e999"),
    ("BatchMaterialArrivals", "quantity", "9007199254740992"),
    ("BatchMaterialArrivals", "quantity", "X'01'"),
    ("BatchMaterialReviews", "batch_quantity", "'later'"),
    ("BatchMaterialReviews", "batch_quantity", "1.5"),
    ("BatchMaterialReviews", "batch_quantity", "-1"),
    ("BatchMaterialReviews", "batch_quantity", "9007199254740992"),
    ("BatchMaterialReviews", "batch_quantity", "0"),
    ("BatchMaterialReviews", "batch_quantity", "NULL"),
], ids=["merge-alias", "merge-number", "zero-cycle", "text-cycle", "text-arrival", "inf-arrival", "arrival-beyond-2^53",
        "blob-arrival", "text-review", "fraction-review", "negative-review", "review-beyond-2^53", "zero-review",
        "null-review"])
def test_storage_types_frozen_external_context_and_arrival_quantity(tmp_path, table, column, value):
    """外协上下文冻结的合并方式与整组周期取原外协组的同一值域；到料量取存储数量的同一规则 (0, 2**53-1]。
    REAL 亲和存得下文本、+Inf 和 BLOB，原来的 ``quantity > 0`` 也拦不住文本（数字 < 文本），列上的 CHECK 拦住。
    物料核对记下的批次数量就是当时的批次数量，取同一规则 1..2**53-1 且必填：INTEGER 亲和存得下 1.5 和文本，
    原来的 ``batch_quantity >= 0`` 都放行。"""
    import sqlite3

    path = str(tmp_path / "contexts.db")
    database.ensure_schema(path, LOGGER)
    with database.get_connection(path) as conn:
        _plan(conn)
        _context_and_arrival(conn)
        with pytest.raises(sqlite3.IntegrityError, match="(CHECK|NOT NULL) constraint failed"):
            conn.execute("UPDATE " + table + " SET " + column + " = " + value)


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "'x'", "9007199254740992", "NULL"],
                         ids=["zero", "negative", "fraction", "text", "beyond-2^53", "null"])
def test_storage_types_batch_quantity_as_every_writer_admits_it(tmp_path, value):
    """批次数量的每个写入口（表单、文件导入、复制与拆批）都按 ``is_stored_number(integer=True, positive=True)``
    收：整数 1..2**53-1。列上原来没有 CHECK，0、负数、小数和文本都能直接写进库。"""
    import sqlite3

    path = str(tmp_path / "batches.db")
    database.ensure_schema(path, LOGGER)
    with database.get_connection(path) as conn:
        _plan(conn)
        with pytest.raises(sqlite3.IntegrityError, match="constraint failed"):
            conn.execute("UPDATE Batches SET quantity = " + value)
        for legal in ("1", "9007199254740991", "'7'"):  # 数字文本按 INTEGER 亲和存成整数
            conn.execute("UPDATE Batches SET quantity = " + legal)
        assert conn.execute("SELECT typeof(quantity), quantity FROM Batches").fetchone()[:] == ("integer", 7)


def test_storage_keeps_every_frozen_context_mode_and_in_range_arrival(tmp_path):
    """两种合并方式、没有外协组时的 NULL、100 年整组周期、小数与 2**53-1 的到料量、1 到 2**53-1 的核对批量都收。"""
    path = str(tmp_path / "contexts.db")
    database.ensure_schema(path, LOGGER)
    with database.get_connection(path) as conn:
        _plan(conn)
        _context_and_arrival(conn)
        for value in ("'separate'", "'merged'", "NULL"):
            conn.execute("UPDATE BatchExternalContexts SET merge_mode = " + value)
        for value in ("36500", "0.25", "NULL"):
            conn.execute("UPDATE BatchExternalContexts SET total_days = " + value)
        for value in ("0.25", "9007199254740991"):
            conn.execute("UPDATE BatchMaterialArrivals SET quantity = " + value)
        for value in ("1", "9007199254740991"):
            conn.execute("UPDATE BatchMaterialReviews SET batch_quantity = " + value)


@pytest.mark.parametrize("instant", [-62135596800000000, -1, 0, 1 << 53, 253402300799999999],
                         ids=["datetime-min", "negative", "epoch", "beyond-2^53", "datetime-max"])
def test_storage_keeps_every_datetime_instant_as_the_same_exact_integer(tmp_path, instant):
    """时间微秒是有符号时刻：datetime 能表示的都收（负数、零、超过 2**53-1），读回来是同一个精确整数。"""
    path = str(tmp_path / "instants.db")
    database.ensure_schema(path, LOGGER)
    with database.get_connection(path) as conn:
        _plan(conn)
        conn.execute("UPDATE Schedule SET start_us = ?, end_us = ?, is_point_event = 1", (instant, instant))
        stored = conn.execute("SELECT typeof(start_us), start_us, typeof(end_us), end_us FROM Schedule").fetchone()
        assert tuple(stored) == ("integer", instant, "integer", instant)


def test_empty_file_db_bootstraps_v50_in_single_pass_and_rejects_full_data_restore(tmp_path):
    fresh_db = tmp_path / "fresh_single_pass.db"
    fresh_db.touch()
    database.ensure_schema(str(fresh_db), LOGGER)
    with database.get_connection(str(fresh_db)) as conn:
        version_row = conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()
        assert version_row is not None and int(version_row[0]) == 50
        assert int(version_row[0]) == database.CURRENT_SCHEMA_VERSION

    empty_restore_db = tmp_path / "empty_restore.db"
    empty_restore_db.touch()
    with pytest.raises(MigrationContractError, match="没有任何业务表"):
        database.ensure_schema(str(empty_restore_db), LOGGER, full_data=True)
    with database.get_connection(str(empty_restore_db)) as conn:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert tables == []
