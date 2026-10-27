"""Migration/restore own data contracts; current startup owns structure only."""

import pytest

from core.infrastructure import database
from core.infrastructure.migration_state import MigrationContractError
from core.infrastructure.single_pass_indexes_schema import ADDED, REMOVED


def _plan(conn):
    conn.executescript("""INSERT INTO Parts(part_no,part_name) VALUES ('P','Part');
        INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B','P',1);
        INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) VALUES (1,'B-1','B',1,'Turning');
        INSERT INTO Schedule(id,op_id,version,start_time,end_time)
            VALUES (1,1,1,'2026-10-15 08:00:00','2026-10-15 09:00:00');""")


def test_current_startup_omits_event_scan_and_probes_but_full_restore_checks_once(tmp_path, monkeypatch):
    path = str(tmp_path / "current.db")
    database.ensure_schema(path)
    with database.get_connection(path) as conn:
        _plan(conn)
    statements = []
    connect = database.get_connection

    def observed(path):
        conn = connect(path)
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(database, "get_connection", observed)
    database.ensure_schema(path)
    assert not any("FROM OperationExecutionEvents" in sql or "__schema_probe" in sql for sql in statements)
    with pytest.raises(MigrationContractError, match="missing ScheduleHistory head"):
        database.ensure_schema(path, full_data=True)
    assert sum(sql.lstrip().startswith("SELECT") and "FROM OperationExecutionEvents" in sql for sql in statements) == 1
    with connect(path) as conn:
        conn.execute("INSERT INTO ScheduleHistory(version,strategy) VALUES (1,'test')")
        conn.execute("""INSERT INTO OperationExecutionEvents(schedule_version,schedule_id,op_id,batch_id,
            source_table,effective_plan_role,event_type,reported_status,event_time,created_by,idempotency_key,
            previous_state_revision) VALUES (1,1,1,'B','schedule','adopted','start','processing',
            '2026-10-15 08:01:00','tester','bad-sequence','1:7:0')""")
    statements.clear()
    database.ensure_schema(path)
    with pytest.raises(MigrationContractError, match="bad_sequence"):
        database.ensure_schema(path, full_data=True)
    assert sum(sql.lstrip().startswith("SELECT") and "FROM OperationExecutionEvents" in sql for sql in statements) == 1


def test_v43_changes_only_declared_indexes_and_uses_single_column_lookups(tmp_path):
    path = str(tmp_path / "old.db")
    database.ensure_schema(path)
    with database.get_connection(path) as conn:
        _plan(conn)
        conn.execute("INSERT INTO ScheduleHistory(version,strategy) VALUES (1,'test')")
        for name in ADDED:
            conn.execute('DROP INDEX "' + name + '"')
        for sql in REMOVED.values():
            conn.execute(sql)
        conn.execute("UPDATE SchemaVersion SET version=42")
        before = [tuple(row) for row in conn.execute("SELECT * FROM Schedule")]
    database.ensure_schema(path, backup_dir=str(tmp_path / "backups"))
    with database.get_connection(path) as conn:
        assert [tuple(row) for row in conn.execute("SELECT * FROM Schedule")] == before
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert set(ADDED) <= indexes and not set(REMOVED) & indexes
        assert {"idx_part_operations_part", "idx_batch_operations_batch", "idx_schedule_history_version",
                "idx_schedule_candidate_rows_version_candidate"} <= indexes
        for table, column, name in (("BatchMaterials", "batch_id", "idx_batch_materials_batch"),
                                    ("BatchOperations", "supplier_id", "idx_batch_operations_supplier"),
                                    ("PartOperations", "supplier_id", "idx_part_operations_supplier")):
            plan = conn.execute("EXPLAIN QUERY PLAN SELECT id FROM " + table + " WHERE " + column + "=?", ("key",))
            assert any(name in row[3] for row in plan)


def test_actual_restore_rolls_back_a_current_schema_backup_missing_its_history_head(tmp_path):
    import logging

    from core.infrastructure.backup import BackupManager
    from core.services.system.backup_restore import run_backup_restore

    path = str(tmp_path / "live.db")
    database.ensure_schema(path)
    with database.get_connection(path) as conn:
        _plan(conn)
        conn.execute("INSERT INTO ScheduleHistory(version,strategy) VALUES (1,'test')")
    manager = BackupManager(path, str(tmp_path / "backups"))
    source = manager.backup(suffix="external")
    with database.get_connection(source) as conn:
        conn.execute("DELETE FROM ScheduleHistory")
    result = run_backup_restore(filename="external", backup_path=source, database_path=path,
        backup_dir=str(tmp_path / "backups"), manager=manager, logger=logging.getLogger(__name__),
        ensure_schema_func=database.ensure_schema)
    assert result.result.code == "verify_failed_rolled_back"
    with database.get_connection(path) as conn:
        assert conn.execute("SELECT version FROM ScheduleHistory").fetchone()[0] == 1


def test_retained_sql_readers_parse_each_row_endpoint_once(tmp_path, monkeypatch):
    from data.repositories import schedule_time_sql
    from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository

    path = str(tmp_path / "time-readers.db")
    database.ensure_schema(path)
    conn = database.get_connection(path)
    try:
        _plan(conn)
        conn.executescript("""INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name)
                VALUES (2,'B-2','B',2,'Turning'),(3,'B-3','B',3,'Turning');
            INSERT INTO Schedule(id,op_id,version,start_time,end_time) VALUES
                (2,2,1,'bad','2026-10-15 09:00:00'),
                (3,3,1,'2026-10-15 08:00:00.123456','2026-10-15 08:00:00.123456');
            UPDATE Batches SET due_date='2026-10-15';""")
        original, calls = schedule_time_sql.parse_dt_for_sql, []

        def counted(value):
            calls.append(value)
            return original(value)

        monkeypatch.setattr(schedule_time_sql, "parse_dt_for_sql", counted)
        repo = SchedulePlanQueryRepository(conn)
        common = {"version": 1, "source_table": "schedule", "candidate_id": None}
        rows = repo.list_detail_rows_between(**common, start_time="2026-10-15 08:00:00", end_time="2026-10-15 10:00:00")
        assert len(rows) == 3 and len(calls) == 8  # Two query parameters, two endpoints for each row.
        calls.clear()
        assert repo.get_plan_time_span(**common) == {"version": 1, "start_time": "2026-10-15 08:00:00", "end_time": "2026-10-15 09:00:00"}
        assert len(calls) == 6
        calls.clear()
        overdue = repo.list_overdue_base_rows(**common)
        # 逾期统计把零工时点事件算作合法安排，只有写坏的那一行无效。
        assert overdue[0]["finish_time"] == "2026-10-15 09:00:00" and overdue[0]["invalid_time_count"] == 1
        assert len(calls) == 6
    finally:
        conn.close()


def test_startup_captures_journal_once_and_wsgi_only_observes_memory(db_env, tmp_path, monkeypatch):
    from types import SimpleNamespace

    from core.services.workbench.facts.system_journal import SystemMaintenanceJournal
    from web.bootstrap import factory, workbench_system_restore
    from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
    from web.bootstrap.workbench_run_lifecycle import install_run_lifecycle
    from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime

    monkeypatch.setenv("APS_ENV", "production")
    monkeypatch.setenv("APS_SYSTEM_JOURNAL_DIR", str(tmp_path / "journal"))
    records, captures = SystemMaintenanceJournal.records, []

    def capture(journal, **kwargs):
        captures.append(journal.directory)
        return records(journal, **kwargs)

    monkeypatch.setattr(SystemMaintenanceJournal, "records", capture)
    scope = str(tmp_path / "launcher")
    payload = acquire_runtime_lock(scope, db_path=db_env)
    runtime = gate = None
    try:
        app = factory.create_app_core(ui_mode="default", enable_secret_key=False,
                                     enable_security_headers=False, enable_session_cookie_hardening=False)
        gate = app.extensions["workbench_request_lifecycle"]
        assert app.extensions["workbench_startup_maintenance_records"] == []
        runtime = install_run_lifecycle(SimpleNamespace(install_run_runtime=install_workbench_run_runtime,
            atexit_register=lambda *args: None), app, {"payload": payload})
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


@pytest.mark.parametrize("prepared", [True, False], ids=["factory-prepared", "independent-caller"])
def test_lifecycle_enters_recovery_without_recapturing_startup_journal(db_env, tmp_path, monkeypatch, prepared):
    from types import SimpleNamespace

    from flask import Flask

    from core.services.workbench.facts.system_journal import SystemMaintenanceJournal
    from web.bootstrap import factory
    from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
    from web.bootstrap.workbench_run_lifecycle import install_run_lifecycle, stop_run_runtime
    from web.bootstrap.workbench_system_restore_recovery import (
        RECOVERY,
        WorkbenchSystemRestoreRecoveryHost,
    )

    directory = tmp_path / "pending-journal"
    directory.mkdir()
    SystemMaintenanceJournal(str(directory), db_env).begin("pending-startup-request-001", "create", {})
    app = Flask(__name__)
    app.config.update(DATABASE_PATH=db_env, WORKBENCH_SYSTEM_JOURNAL_DIR=str(directory))
    original, captures, callbacks = SystemMaintenanceJournal.records, [], []

    def records(journal, **kwargs):
        captures.append(journal.directory)
        return original(journal, **kwargs)

    monkeypatch.setattr(SystemMaintenanceJournal, "records", records)
    scope = str(tmp_path / "recovery-launcher")
    payload = acquire_runtime_lock(scope, db_path=db_env)
    runtime = None
    try:
        if prepared:
            monkeypatch.setenv("APS_ENV", "production")
            monkeypatch.setenv("APS_SYSTEM_JOURNAL_DIR", str(directory))
            app = factory.create_app_core(ui_mode="default", enable_secret_key=False,
                                         enable_security_headers=False, enable_session_cookie_hardening=False)
            assert app.extensions[RECOVERY]
        state = {"payload": payload}
        deps = SimpleNamespace(install_run_runtime=lambda *args, **kwargs: pytest.fail("Recovery started a worker"),
                               atexit_register=lambda *args: callbacks.append(args))
        runtime = install_run_lifecycle(deps, app, state)
        assert isinstance(runtime, WorkbenchSystemRestoreRecoveryHost)
        assert app.extensions[RECOVERY] and not runtime.ready
        assert state["runtime"] is runtime and callbacks == [(stop_run_runtime, runtime)]
        assert len(captures) == 1
        assert app.test_client().get("/api/workbench/v1/system/restore-host").get_json()["data"]["host"]["restart_required"]
    finally:
        if runtime is not None:
            stop_run_runtime(runtime)
        release_runtime_lock(scope, expected_payload=payload)
