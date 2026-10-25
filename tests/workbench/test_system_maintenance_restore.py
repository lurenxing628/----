"""Fault injection only in our fresh disposable test DB and backup directory."""


import json
import logging
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest
from werkzeug.test import EnvironBuilder

from core.infrastructure.backup import BackupManager
from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.services.workbench.facts.run_data_context import RunDataContext
from core.services.workbench.facts.system_journal import SystemMaintenanceJournal, assert_system_maintenance_ready
from core.services.workbench.facts.system_reads import backup_signature
from core.services.workbench.system.files import SystemFileWorkspace
from tests.workbench.run_jobs_support import job_case as _job_case_fixture  # noqa: F401
from tests.workbench.system_maintenance_support import SystemTestAPI
from tests.workbench.system_restore_entrypoint_legacy_support import (
    system_api as _system_api_fixture,  # noqa: F401
)


def enable_restore(api):
    from web.bootstrap.workbench_system_restore import WorkbenchSystemRestoreHost
    host = api.app.extensions["workbench_system_restore_host"]
    assert isinstance(host, WorkbenchSystemRestoreHost)
    assert api.app.extensions["workbench_system_restore_guard"] is host
    assert host.runtime.ready and host.status["operations_available"]
    host.verify()


def test_backup_list_remains_readable_without_maintenance_directory(tmp_path):
    api = SystemTestAPI(tmp_path)
    backup = api.backup()
    api.app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"] = ""

    data = api.read("/backups")["data"]
    assert [row["filename"] for row in data["rows"] if row["record_kind"] == "backup_file"] == [Path(backup).name]
    capabilities = data["capabilities"]
    assert not capabilities["create"] and not capabilities["delete"] and not capabilities["restore"]
    assert "还没有配置维护目录" in capabilities["blocked_reason"]
    assert capabilities["restore_reason"] == capabilities["blocked_reason"]


def test_static_files_observe_stop_state_without_rereading_database_locks(system_api, monkeypatch):
    from web.bootstrap.workbench_run_runtime_lock import RunRuntimeLockProof

    calls, original = [], RunRuntimeLockProof.verify

    def verify(proof):
        calls.append(proof)
        return original(proof)

    monkeypatch.setattr(RunRuntimeLockProof, "verify", verify)
    response = system_api.client.get("/static/workbench/app/theme.js", buffered=True)
    assert response.status_code == 200 and not calls
    response.close()
    assert system_api.get("/restore-host").status_code == 200 and calls
    host = system_api.app.extensions["workbench_system_restore_host"]
    host._set_state("stopped", None)
    calls.clear()
    assert system_api.client.get("/static/workbench/app/theme.js", buffered=True).status_code == 503
    assert not calls


def test_utc_operation_logs_use_one_local_time_for_lists_details_filters_and_export(tmp_path):
    import csv
    import io

    api = SystemTestAPI(tmp_path)
    with closing(api.connect()) as conn:
        conn.executemany("INSERT INTO OperationLogs(id,log_time,log_level,module,action,detail) VALUES (?,?,?,'system','logs_cleanup',?)", [
            (1, "2026-10-15 15:59:59", "INFO", '{"deleted_count":1}'),
            (2, "2026-10-15 16:00:01", "INFO", '{"deleted_count":2}'),
        ])
        conn.execute("INSERT INTO SystemJobState(job_key,last_run_time,last_run_detail) VALUES (?,?,?)",
                     ("auto_backup_cleanup", "2026-10-16 00:00:02", '{"removed_count":0}'))
        conn.commit()
    (api.logs / "aps.log").write_text("2026-10-16 00:00:00 [INFO] fixture: local runtime log\n", encoding="utf-8")

    window = {"start": "2026-10-16", "end": "2026-10-16"}
    page = api.read("/logs", **window)
    rows = page["data"]["rows"]
    assert [(row["file"], row["time"]) for row in rows] == [
        ("OperationLogs", "2026-10-16T00:00:01"), ("aps.log", "2026-10-16T00:00:00")]
    assert json.loads(rows[0]["body"].strip()) == {"deleted_count": 2}
    previous = api.read("/logs", file="OperationLogs", start="2026-10-15", end="2026-10-15")
    assert [row["time"] for row in previous["data"]["rows"]] == ["2026-10-15T23:59:59"]
    # The detail pane keeps this same captured row; paging and export reuse it.
    query = {**window, "snapshot_ref": page["meta"]["snapshot_ref"]}
    assert api.read("/logs", **query)["data"]["rows"] == rows
    exported = api.get("/logs/export/csv", **query)
    assert exported.status_code == 200
    csv_rows = list(csv.DictReader(io.StringIO(exported.data.decode("utf-8-sig"))))
    assert [row["时间"] for row in csv_rows] == [row["time"] for row in rows]
    assert csv_rows[0]["详情"] == rows[0]["body"]

    events = api.read("/backups", type="cleanup", **window)["data"]["rows"]
    assert [(row["event_source"], row["time"]) for row in events] == [
        ("latest_job_state_only", "2026-10-16T00:00:02"), ("operation_audit", "2026-10-16T00:00:01")]
    with closing(api.connect()) as conn:
        assert [row[0] for row in conn.execute("SELECT log_time FROM OperationLogs ORDER BY id")] == [
            "2026-10-15 15:59:59", "2026-10-15 16:00:01"]


def test_due_backup_runs_after_response_on_owned_worker_and_shutdown_joins_it(system_api, monkeypatch):
    from core.services.system.system_maintenance_service import SystemMaintenanceService
    from data.repositories.system_config_repo import SystemConfigRepository
    from web.bootstrap.workbench_run_lifecycle import stop_run_runtime

    conn = system_api.connect()
    try:
        with conn:
            repo = SystemConfigRepository(conn)
            for key, value in (("auto_backup_enabled", "yes"), ("auto_backup_interval_minutes", "60"),
                               ("auto_backup_cleanup_enabled", "no"), ("auto_backup_keep_days", "7"),
                               ("auto_backup_cleanup_interval_minutes", "1440")):
                repo.set(key, value)
    finally:
        conn.close()
    # Advance the deferred check interval in this controlled test, without waiting ten seconds.
    monkeypatch.setattr(SystemMaintenanceService, "CHECK_THROTTLE_SECONDS", 0)
    entered, release = threading.Event(), threading.Event()
    threads, original = [], BackupManager.backup

    def backup(manager, *args, **kwargs):
        threads.append(threading.get_ident())
        entered.set()
        assert release.wait(5)
        return original(manager, *args, **kwargs)

    monkeypatch.setattr(BackupManager, "backup", backup)
    runtime = system_api.app.extensions["workbench_run_runtime"]
    try:
        response = system_api.client.get("/", buffered=True)
        assert response.status_code == 302
        response.close()
        assert entered.wait(3)
        assert threads == [runtime._thread.ident] and threads[0] != threading.get_ident()
        with ThreadPoolExecutor(max_workers=1) as pool:
            stopped = pool.submit(stop_run_runtime, runtime)
            assert not stopped.done()
            assert Path(runtime.proof.db_lock_path).exists()
            release.set()
            stopped.result(5)
        assert runtime.status["closed"]
        assert list(system_api.backups.glob("*_auto.db"))
    finally:
        release.set()


def test_download_requests_schedule_maintenance_after_wsgi_lifecycle_finishes(system_api, monkeypatch):
    app = system_api.app
    runtime = app.extensions["workbench_run_runtime"]
    gate = app.extensions["workbench_request_lifecycle"]
    calls = []
    monkeypatch.setattr(runtime, "request_maintenance_check", lambda: calls.append(gate.status["active"]))
    statuses = []
    environ = EnvironBuilder(path="/api/workbench/v1/entities/batch/template").get_environ()
    response = app.wsgi_app(environ, lambda status, headers: statuses.append(status))
    try:
        assert statuses == ["200 OK"]
        first_chunk = next(iter(response))
        assert not calls and gate.status["active"] == 1
        assert (first_chunk + b"".join(response)).startswith(b"PK")
        assert calls == [0]
    finally:
        response.close()
    assert calls == [0]


def test_verified_restore_uses_protection_external_result_and_new_connection(system_api):
    conn = system_api.connect()
    conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES('marker','before')")
    conn.commit()
    conn.close()
    with closing(system_api.connect()) as conn:
        before_context = RunDataContext(conn, str(system_api.journal_dir)).ref()
    log_snapshot = system_api.read("/logs")
    system_api.backup()
    row = system_api.selected()
    conn = system_api.connect()
    conn.execute("UPDATE SystemConfig SET config_value='after' WHERE config_key='marker'")
    conn.commit()
    conn.close()
    enable_restore(system_api)
    response = system_api.file_action("restore", row)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()["data"]["operation"]
    assert result["code"] == "verified" and result["state"] == "succeeded"
    assert result["source_verification"] == {"basis": "original_file_content_and_sqlite", "target": "verified",
                                            "protection": "captured", "sqlite_integrity": "passed"}
    assert not {"target_sha256", "protection_sha256", "database_after_sha256"}.intersection(result)
    assert result["protection_filename"].endswith("before_restore.db")
    states = [item["state"] for item in result["history"]]
    assert states.index("protecting") < states.index("restoring") < states.index("verifying")
    conn = system_api.connect()
    assert conn.execute("SELECT config_value FROM SystemConfig WHERE config_key='marker'").fetchone()[0] == "before"
    assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM OperationLogs WHERE action='workbench_restore'").fetchone()[0] == 1
    conn.close()
    with closing(system_api.connect()) as conn:
        context = RunDataContext(conn, str(system_api.journal_dir))
        assert context.ref() != before_context
        assert context.resolve_missing("run-before-restored-data", before_context) == "context_replaced"
    from core.models.workbench_system import query_input
    from web.routes.workbench.system_log_snapshots import resolve_log_snapshot
    scope = {"kind": "system.logs", **{key: value for key, value in query_input({}, "logs").items()
                                      if key not in ("page", "page_size")}}
    with system_api.app.app_context(), pytest.raises(WorkbenchCommandRejected) as error:
        resolve_log_snapshot(scope, log_snapshot["meta"]["snapshot_ref"])
    assert error.value.code == "snapshot_stale"
    replay = system_api.file_action("restore", row)
    assert replay.status_code == 503
    maintenance = system_api.app.test_client().get("/workbench?view=dashboard")
    assert maintenance.status_code == 503
    html = maintenance.get_data(as_text=True)
    assert 'href="/workbench?view=dashboard">重新检查启动状态</a>' in html
    assert "返回工作台" not in html
    looked_up = system_api.read("/results/system-test-request-0001")["data"]["operation"]
    assert looked_up["replayed"] is True
    assert looked_up["job_ref"] == result["job_ref"]
    assert_system_maintenance_ready(str(system_api.database), str(system_api.journal_dir))


@pytest.mark.parametrize("empty_schema_sql", [
    None,
    "PRAGMA user_version = 1",
    "CREATE TABLE SchemaVersion (version INTEGER)",
], ids=["zero-bytes", "empty-sqlite", "schema-version-only"])
def test_empty_backup_restore_preserves_database_and_protection(system_api, empty_schema_sql):
    with closing(system_api.connect()) as conn, conn:
        conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES('empty_backup_marker','original')")
    with closing(system_api.connect()) as conn:
        original = tuple(conn.iterdump())

    backup_path = system_api.backups / "aps_backup_empty.db"
    if empty_schema_sql is None:
        backup_path.write_bytes(b"")
    else:
        with closing(sqlite3.connect(str(backup_path))) as conn:
            conn.executescript(empty_schema_sql)
    selected = system_api.selected()
    enable_restore(system_api)
    response = system_api.file_action("restore", selected)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()["data"]["operation"]
    assert result["state"] == "failed"
    assert result["code"] == "backup_integrity_failed"
    assert result["database_origin"] == "unchanged"
    states = [item["state"] for item in result["history"]]
    assert "verifying" not in states and "rolling_back" not in states

    protection_path = system_api.backups / result["protection_filename"]
    for path in (system_api.database, protection_path):
        with closing(sqlite3.connect(str(path))) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            assert tuple(conn.iterdump()) == original


def test_legacy_journal_lookup_and_new_intent_replay_preserve_original_files(tmp_path, monkeypatch):
    reads, records = [], SystemMaintenanceJournal.records
    def capture(journal, **kwargs):
        reads.append(journal.directory)
        return records(journal, **kwargs)
    monkeypatch.setattr(SystemMaintenanceJournal, "records", capture)
    empty_directory = tmp_path / "empty.db.system-journal"
    empty_directory.mkdir()
    empty = SystemMaintenanceJournal(str(empty_directory), str(tmp_path / "empty.db"))
    previous = empty.admission("empty-maintenance-request-01")
    assert previous is None and reads == [str(empty_directory)]
    created, replayed = empty.begin("empty-maintenance-request-01", "create", {}, previous=previous)
    assert not replayed and created["database_scope"] == str(tmp_path / "empty.db")
    assert reads == [str(empty_directory)]
    reads.clear()
    with pytest.raises(WorkbenchCommandRejected) as error:
        empty.admission("another-empty-maintenance-request")
    assert error.value.code == "maintenance_active" and reads == [str(empty_directory)]

    database = tmp_path / "portable.db"
    directory = tmp_path / "portable.db.system-journal"
    directory.mkdir()
    old = {"version": 1, "database_scope": "a" * 64, "job_ref": "b" * 32,
           "request_key": "old-maintenance-request-01", "input_hash": "c" * 64, "record_hash": "d" * 64,
           "action": "create", "state": "succeeded", "code": "backup_verified", "message": "old saved result",
           "history": [{"state": "succeeded", "time": "2026-10-01T12:00:00"}], "updated_at": "2026-10-01T12:00:00",
           "target": {"filename": "aps_backup_saved.db", "sha256": "e" * 64}, "protection": None, "audit_persisted": True}
    original_path = directory / ("f" * 64 + ".json")
    original_path.write_text(json.dumps(old), encoding="utf-8")
    original = original_path.read_bytes()
    journal = SystemMaintenanceJournal(str(directory), str(database))
    assert journal.lookup(old["request_key"]) == old and journal.database_scope == old["database_scope"]
    assert SystemMaintenanceJournal(str(directory), str(database)).lookup_job(old["job_ref"]) == old
    public = journal.public(journal.lookup(old["request_key"]))
    assert public["job_ref"] == old["job_ref"] and public["target_sha256"] == old["target"]["sha256"]
    with pytest.raises(WorkbenchCommandRejected) as error:
        journal.begin(old["request_key"], "create", {})
    assert error.value.code == "original_intent_unavailable"
    assert original_path.read_bytes() == original
    external = SystemMaintenanceJournal(str(directory), str(tmp_path / "another.db"))
    assert external.lookup(old["request_key"]) == old
    with pytest.raises(WorkbenchCommandRejected) as error:
        external.assert_ready()
    assert error.value.code == "maintenance_origin_unavailable"

    captured = journal.records()
    reads.clear()
    assert journal.scope_from_records(captured) == old["database_scope"]
    assert journal.scope_from_records([]) == str(database) and reads == []
    row, replayed = journal.begin("new-maintenance-request-01", "create", {})
    assert reads == [str(directory)]
    assert replayed is False and row["version"] == 2 and row["intent"] == {"action": "create", "input": {}}
    assert row["database_scope"] == old["database_scope"]
    journal.record(row, "succeeded", code="backup_verified")
    new_path = directory / (row["job_ref"] + ".json")
    saved = new_path.read_bytes()
    replayed_row, replayed = journal.begin(row["request_key"], "create", {})
    assert replayed is True and same(replayed_row, row)
    assert new_path.read_bytes() == saved and original_path.read_bytes() == original
    assert len(list(directory.glob("*.json"))) == 2
    with pytest.raises(WorkbenchCommandRejected) as error:
        journal.begin(row["request_key"], "delete", {"backup_ref": "another-original-reference"})
    assert error.value.code == "request_key_conflict"
    from core.services.workbench.facts import system_journal as journal_module
    opened, binary_open = [], journal_module.open_fixed_file_for_read_binary
    def open_once(path):
        opened.append(os.fspath(path))
        return binary_open(path)
    monkeypatch.setattr(journal_module, "open_fixed_file_for_read_binary", open_once)
    bounded = {**row, "message": "已登记"}
    limit = 256 * 1024
    bounded["message"] += "x" * (limit - len(canonical_json(bounded).encode("utf-8")))
    payload = canonical_json(bounded).encode("utf-8")
    assert len(payload) == limit
    new_path.write_bytes(payload)
    assert journal._read(str(new_path))["message"] == bounded["message"]
    assert opened == [str(new_path)]
    opened.clear()
    new_path.write_bytes(payload + b" ")
    with pytest.raises(RuntimeError) as error:
        journal._read(str(new_path))
    assert str(error.value) == "维护记录超过允许大小，须人工核查。"
    assert opened == [str(new_path)]
    for content, origin in ((b"\xff", UnicodeDecodeError), (b"{", json.JSONDecodeError)):
        new_path.write_bytes(content)
        with pytest.raises(WorkbenchCommandRejected) as error:
            SystemMaintenanceJournal(str(directory), str(database)).admission("malformed-maintenance-request")
        assert error.value.code == "maintenance_unconfirmed" and isinstance(error.value.__cause__, origin)
    assert original_path.read_bytes() == original


def test_system_captures_once_and_tokens_keep_relocated_journal_scope(tmp_path, monkeypatch):
    from web.public_token_registry import resolve_public_token
    from web.routes.workbench.system_context import SCOPE

    initial = tmp_path / "original"
    initial.mkdir()
    api = SystemTestAPI(initial)
    api.journal_dir = Path(str(api.database) + ".system-journal")
    api.journal_dir.mkdir()
    api.app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"] = str(api.journal_dir)
    counts = {"records": 0, "enumerations": 0, "json_reads": 0}
    original_records, original_read, original_listdir = SystemMaintenanceJournal.records, SystemMaintenanceJournal._read, os.listdir
    def records(journal, **kwargs):
        counts["records"] += 1
        return original_records(journal, **kwargs)
    def read(journal, path):
        counts["json_reads"] += 1
        return original_read(journal, path)
    def listdir(path="."):
        if os.fspath(path) == str(api.journal_dir):
            counts["enumerations"] += 1
        return original_listdir(path)
    monkeypatch.setattr(SystemMaintenanceJournal, "records", records)
    monkeypatch.setattr(SystemMaintenanceJournal, "_read", read)
    monkeypatch.setattr(os, "listdir", listdir)
    observed = {}
    def counted(name, action, json_count, *, enumerations=1):
        counts.update(records=0, enumerations=0, json_reads=0)
        value = action()
        observed[name] = dict(counts)
        assert counts == {"records": 1, "enumerations": enumerations, "json_reads": json_count}
        return value

    blank = counted("empty_backup_list", lambda: api.read("/backups"), 0)
    assert blank["data"]["rows"] == [] and blank["data"]["capabilities"]["create"]
    with closing(api.connect()) as conn:
        empty_context = counted("empty_run_context", lambda: RunDataContext(conn, str(api.journal_dir)).ref(), 0)
    counted("empty_log_snapshot", lambda: api.read("/logs"), 0)
    for index in range(3):
        response = api.file_action("create", key="captured-journal-request-" + str(index))
        assert response.status_code == 200 and response.get_json()["data"]["operation"]["state"] == "succeeded"
    for index in range(7):
        BackupManager(str(api.database), str(api.backups)).backup(suffix="captured_" + str(index))
    assert len(list(api.backups.glob("aps_backup_*.db"))) == 10
    history = {path.name: path.read_bytes() for path in api.journal_dir.glob("*.json")}
    original_scope = str(api.database)
    (api.logs / "aps.log").write_text("2026-10-14 12:00:00 [INFO] fixture: captured log\n", encoding="utf-8")
    relocated = tmp_path / "relocated"
    initial.rename(relocated)
    api.database = relocated / "test.db"
    api.journal_dir = Path(str(api.database) + ".system-journal")
    api.backups, api.logs = relocated / "backups", relocated / "logs"
    api.app.config.update(DATABASE_PATH=str(api.database), WORKBENCH_SYSTEM_JOURNAL_DIR=str(api.journal_dir),
                          BACKUP_DIR=str(api.backups), LOG_DIR=str(api.logs))

    page = counted("relocated_ten_backup_tokens", lambda: api.read("/backups"), 3)
    rows = page["data"]["rows"]
    assert len(rows) == 10 and all(row["record_kind"] == "backup_file" for row in rows)
    tokens = [page["data"]["create_context"]["write_token"]]
    for row in rows:
        tokens.extend((row["backup_ref"], row["write_context"]["write_token"]))
    with api.app.app_context():
        assert len(tokens) == 21
        assert all(resolve_public_token(SCOPE, token, message="stale fixture token", field="write_token")["database"] == original_scope
                   for token in tokens)
    with closing(api.connect()) as conn:
        context = RunDataContext(conn, str(api.journal_dir))
        assert counted("relocated_run_context", context.ref, 3) == empty_context
        assert counted("recorded_missing_run", lambda: context.resolve_missing("missing-run-request"), 0, enumerations=0) == "unresolved"
    admitted = counted("recorded_admission", lambda: api.journal().admission("captured-journal-request-0"), 3)
    assert admitted is not None
    assert admitted["database_scope"] == original_scope
    captured = counted("recorded_log_snapshot", lambda: api.read("/logs", file="aps.log"), 3)
    assert captured["data"]["rows"]
    with (api.logs / "aps.log").open("a", encoding="utf-8") as stream:
        stream.write("2026-10-14 12:01:00 [INFO] fixture: newer log\n")
    reused = counted("recorded_log_snapshot_reuse", lambda: api.read(
        "/logs", file="aps.log", snapshot_ref=captured["meta"]["snapshot_ref"]), 3)
    assert reused["data"]["rows"] == captured["data"]["rows"]
    assert {path.name: path.read_bytes() for path in api.journal_dir.glob("*.json")} == history
    selected = rows[0]
    downloaded = counted("backup_export", lambda: api.get(
        "/backups/" + selected["backup_ref"] + "/download", snapshot_ref=page["meta"]["snapshot_ref"]), 3)
    assert downloaded.status_code == 200 and downloaded.data.startswith(b"SQLite format 3\x00")
    deleted = counted("delete_admission_and_guard", lambda: api.post(
        "/backups/delete", {"backup_ref": selected["backup_ref"]}, selected["write_context"]["write_token"],
        key="captured-delete-request-001"), 3)
    assert deleted.status_code == 200 and deleted.get_json()["data"]["operation"]["state"] == "succeeded"
    print("R02 capture counts: " + json.dumps(observed, sort_keys=True))


def test_job_lookup_and_recovery_view_share_capture_and_observe_new_requests(tmp_path, monkeypatch):
    from werkzeug.test import Client
    from werkzeug.wrappers import Response

    from web.bootstrap.workbench_system_restore import make_workbench_system_restore_recovery_app

    database, directory = tmp_path / "test.db", tmp_path / "journal"
    directory.mkdir()
    journal = SystemMaintenanceJournal(str(directory), str(database))
    row, _ = journal.begin("captured-recovery-request-001", "create", {})
    captured = journal.records()
    journal.record(row, "succeeded", code="backup_verified")
    assert journal.lookup(row["request_key"]) is row and journal.lookup_job(row["job_ref"]) is row
    assert captured[0]["state"] == "succeeded"
    app = make_workbench_system_restore_recovery_app(str(database), str(directory))
    client = Client(app, Response)
    opened, enumerated = [], []
    read, listdir = SystemMaintenanceJournal._read, os.listdir
    def captured_read(current, path):
        opened.append(path)
        return read(current, path)
    def captured_listdir(path):
        enumerated.append(path)
        return listdir(path)
    monkeypatch.setattr(SystemMaintenanceJournal, "_read", captured_read)
    monkeypatch.setattr(os, "listdir", captured_listdir)
    response = client.get("/", query_string={"reference": row["request_key"], "download": "diagnostic"})
    assert response.status_code == 200
    payload = response.json
    assert payload is not None
    assert payload["result"]["operation"]["job_ref"] == row["job_ref"]
    assert len(opened) == 1 and enumerated == [str(directory)]
    other = SystemMaintenanceJournal(str(directory), str(database))
    added, _ = other.begin("captured-recovery-request-002", "create", {})
    other.record(added, "succeeded", code="backup_verified")
    assert len(journal.records()) == 1
    assert len(journal.refresh()) == 2
    opened.clear()
    enumerated.clear()
    response = client.get("/", query_string={"reference": added["job_ref"], "kind": "job", "download": "diagnostic"})
    payload = response.json
    assert payload is not None
    assert payload["result"]["operation"]["request_key"] == added["request_key"]
    assert len(payload["recent_records"]) == 2
    assert len(opened) == 2 and enumerated == [str(directory)]


def test_job_result_reads_v2_file_over_collection_capacity_and_checks_database(tmp_path, monkeypatch):
    from werkzeug.test import Client
    from werkzeug.wrappers import Response

    from web.bootstrap.workbench_system_restore import make_workbench_system_restore_recovery_app

    api = SystemTestAPI(tmp_path)
    created = api.file_action("create").get_json()["data"]["operation"]
    original = api.journal().lookup_job(created["job_ref"])
    assert original is not None
    for index in range(2000):
        job_ref = format(index, "032x")
        row = {**original, "job_ref": job_ref, "request_key": "capacity-maintenance-request-" + str(index)}
        (api.journal_dir / (job_ref + ".json")).write_text(canonical_json(row), encoding="utf-8")
    assert len(assert_system_maintenance_ready(str(api.database), str(api.journal_dir))) == 2001
    assert api.journal().admission("capacity-maintenance-next-request") is None
    opened, enumerated = [], []
    read, listdir = SystemMaintenanceJournal._read, os.listdir
    def captured_read(current, path):
        opened.append(path)
        return read(current, path)
    def captured_listdir(path):
        if os.fspath(path) == str(api.journal_dir):
            enumerated.append(path)
        return listdir(path)
    monkeypatch.setattr(SystemMaintenanceJournal, "_read", captured_read)
    monkeypatch.setattr(os, "listdir", captured_listdir)
    response = api.get("/jobs/" + created["job_ref"])
    assert response.status_code == 200 and response.get_json()["data"]["operation"]["state"] == "succeeded"
    assert opened == [str(api.journal_dir / (created["job_ref"] + ".json"))] and not enumerated
    with pytest.raises(RuntimeError, match="不属于当前数据库"):
        SystemMaintenanceJournal(str(api.journal_dir), str(tmp_path / "another.db")).lookup_job(created["job_ref"])
    response = api.get("/backups")
    assert response.status_code == 413 and response.get_json()["error"]["code"] == "maintenance_record_capacity"
    opened.clear()
    enumerated.clear()
    recovery = Client(make_workbench_system_restore_recovery_app(str(api.database), str(api.journal_dir)), Response)
    result = recovery.get("/api/workbench/v1/system/jobs/" + created["job_ref"])
    payload = result.json
    assert result.status_code == 200 and payload is not None
    assert payload["data"]["operation"]["job_ref"] == created["job_ref"]
    assert len(opened) == 1 and not enumerated
    opened.clear()
    diagnostic = recovery.get("/", query_string={"reference": created["job_ref"], "kind": "job", "download": "diagnostic"})
    payload = diagnostic.json
    assert payload is not None
    assert payload["history_error"] and payload["result"]["operation"]["job_ref"] == created["job_ref"]
    assert len(opened) == 1 and enumerated == [str(api.journal_dir)]
    invalid = recovery.get("/", query_string={"reference": "not-a-maintenance-reference", "kind": "job"})
    assert invalid.status_code == 400


def test_old_scheduling_requests_capture_once_and_query_registered_protection(job_case, tmp_path, monkeypatch):
    from flask import Blueprint, g

    from core.services.workbench.facts import run_data_context as context_module
    from core.services.workbench.facts import system_journal as journal_module
    from tests.workbench.run_jobs_support import connection
    from web.routes.workbench.scheduling_jobs import register_scheduling_job_routes

    case = job_case
    journal_dir, backups = Path(str(case.path) + ".system-journal"), tmp_path / "protected-backups"
    journal_dir.mkdir()
    backups.mkdir()
    case.app.config.update(DATABASE_PATH=str(case.path), WORKBENCH_SYSTEM_JOURNAL_DIR=str(journal_dir),
                           BACKUP_DIR=str(backups))
    current_key, old_key = "current-scheduling-request-001", "protected-scheduling-request-001"
    queued = case.accept(current_key)
    assert queued["data"]["state"] == "queued"
    protected = backups / "aps_backup_r07_before_restore.db"
    with closing(sqlite3.connect(str(protected))) as conn, conn:
        conn.execute("CREATE TABLE WorkbenchRunJobs (request_key TEXT)")
        conn.execute("CREATE TABLE WorkbenchCommandReceipts (request_key TEXT,action TEXT)")
        conn.execute("INSERT INTO WorkbenchRunJobs VALUES (?)", (old_key,))
        conn.execute("INSERT INTO WorkbenchCommandReceipts VALUES (?, 'scheduling.run')", (old_key,))
    signature = backup_signature(str(protected))
    journal = SystemMaintenanceJournal(str(journal_dir), str(case.path))
    row, _ = journal.begin("registered-restore-request-001", "restore", {})
    journal.record(row, "succeeded", code="verified", protection={"filename": protected.name, "signature": signature})
    bp = Blueprint("r07_scheduling_requests", __name__)
    register_scheduling_job_routes(bp)
    case.app.register_blueprint(bp)
    @case.app.before_request
    def bind():
        g.db = connection(case.path)
    @case.app.teardown_request
    def close(_error):
        g.pop("db").close()
    counts = {"records": 0, "full_binary_reads": 0, "protected_stat": 0}
    records, opened, stat = SystemMaintenanceJournal.records, journal_module.open_fixed_file_for_read_binary, context_module.backup_signature
    def capture(journal, **kwargs):
        counts["records"] += 1
        return records(journal, **kwargs)
    def binary_open(path):
        if os.fspath(path) == str(protected):
            counts["full_binary_reads"] += 1
        return opened(path)
    def first_stat(path):
        counts["protected_stat"] += 1
        return stat(path)
    monkeypatch.setattr(SystemMaintenanceJournal, "records", capture)
    monkeypatch.setattr(journal_module, "open_fixed_file_for_read_binary", binary_open)
    monkeypatch.setattr(context_module, "backup_signature", first_stat)
    client, observed = case.app.test_client(), {}
    def status(name, request_key, resolution, *, found=False):
        counts.update(records=0, full_binary_reads=0, protected_stat=0)
        response = client.get("/api/workbench/v1/scheduling/requests/" + request_key)
        assert response.status_code == 200, response.get_json()
        data = response.get_json()["data"]
        observed[name] = dict(counts)
        assert data["found"] is found and data["resolution"] == resolution and data["data_context_ref"]
        assert counts == {"records": 1, "full_binary_reads": 0, "protected_stat": 0 if found else 1}
        return data

    assert status("current_found", current_key, "found", found=True)["run"]["run_ref"] == queued["run_ref"]
    status("protected_found", old_key, "context_replaced")
    status("protected_not_found", "unknown-scheduling-request", "unresolved")
    os.utime(str(protected), ns=(protected.stat().st_atime_ns, signature["mtime_ns"] + 1_000_000_000))
    status("registered_identity_changed", old_key, "unresolved")
    with protected.open("r+b") as stream:
        stream.write(b"not-a-database!!!")
    os.utime(str(protected), ns=(protected.stat().st_atime_ns, signature["mtime_ns"]))
    assert backup_signature(str(protected)) == signature
    status("sqlite_unreadable", old_key, "unresolved")
    protected.unlink()
    status("protected_missing", old_key, "unresolved")
    print("R07 query counts: " + json.dumps(observed, sort_keys=True))


def test_restore_preflight_detects_changed_original_bytes_with_same_file_metadata(tmp_path):
    database, backup_dir, journal_dir = tmp_path / "current.db", tmp_path / "backups", tmp_path / "journal"
    backup_dir.mkdir()
    journal_dir.mkdir()
    selected = backup_dir / "aps_backup_selected.db"
    for path, value in ((database, "current!"), (selected, "selected")):
        with sqlite3.connect(str(path)) as conn:
            conn.execute("CREATE TABLE marker (value TEXT)")
            conn.execute("INSERT INTO marker VALUES (?)", (value,))
    workspace = SystemFileWorkspace(database_path=str(database), backup_dir=str(backup_dir), journal_dir=str(journal_dir),
                                    logger=logging.getLogger("system-source-content-tests"))
    signature = backup_signature(str(selected))
    row, replayed, path = workspace.prepare_restore(
        request_key="source-content-request-01", intent={"backup_ref": "retained-original-reference"},
        guard=lambda: {"filename": selected.name, "signature": signature},
    )
    assert not replayed and row["source_verification"]["target"] == "captured"
    with sqlite3.connect(str(selected)) as conn:
        conn.execute("UPDATE marker SET value = ?", ("changed!",))
    os.utime(str(selected), ns=(selected.stat().st_atime_ns, signature["mtime_ns"]))
    assert same(backup_signature(str(selected)), signature)

    def restore(manager, source_path):
        return SimpleNamespace(result=manager.restore(source_path), category="error")

    result = workspace.finish_restore(row, path, restore_runner=restore, audit=lambda _result: False, confirm_host=lambda: None)
    assert result["state"] == "rolled_back" and result["code"] == "restore_failed_rolled_back"
    with sqlite3.connect(str(database)) as conn:
        assert conn.execute("SELECT value FROM marker").fetchone() == ("current!",)
    saved = workspace.journal.lookup(row["request_key"])
    assert saved is not None
    assert set(saved["target"]) == {"filename", "signature"} and set(saved["protection"]) == {"filename", "signature"}


def test_runtime_identity_is_independent_of_shutdown_and_application_secrets(tmp_path, monkeypatch):
    from flask import Flask

    from web.runtime_host import runtime_identity

    app = Flask("system-runtime-identity")
    app.config.update(DATABASE_PATH=str(tmp_path / "runtime.db"), APS_RUNTIME_OWNER="source-content-test")
    first = runtime_identity(app)
    monkeypatch.setitem(app.config, "APS_RUNTIME_SHUTDOWN_TOKEN", "shutdown-secret-for-contract")
    monkeypatch.setitem(app.config, "SECRET_KEY", "application-secret-for-contract")
    assert runtime_identity(app) == first
    assert first["db_path"] == os.path.normcase(os.path.abspath(str(tmp_path / "runtime.db")))
    assert first["owner"] == "source-content-test" and len(first["instance_id"]) == 32 and first["started_at"]
    assert not {"db_path_hash", "shutdown_token", "SECRET_KEY"}.intersection(first)
    other = Flask("another-system-runtime-identity")
    other.config.update(app.config)
    assert runtime_identity(other)["instance_id"] != first["instance_id"]
    if os.name != "nt":
        alias = tmp_path / "runtime-alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        app.config["DATABASE_PATH"] = str(alias / "runtime.db")
        assert runtime_identity(app)["db_path"] == str(alias / "runtime.db")
        assert runtime_identity(app)["instance_id"] == first["instance_id"]


@pytest.mark.parametrize("rollback_fails", [True])
def test_verify_failure_and_rollback_failure_are_distinct(system_api, monkeypatch, rollback_fails):
    system_api.backup()
    enable_restore(system_api)
    def verification(*args, **kwargs):
        raise RuntimeError("injected verify failure")
    monkeypatch.setattr("web.routes.workbench.system_actions.ensure_schema", verification)
    copy = BackupManager._copy_db_file
    def failing_copy(self, source_path, **kwargs):
        if rollback_fails and "before_restore" in source_path:
            raise OSError("injected rollback failure")
        return copy(self, source_path, **kwargs)
    monkeypatch.setattr(BackupManager, "_copy_db_file", failing_copy)
    result = system_api.file_action("restore").get_json()["data"]["operation"]
    assert result["code"] == ("verify_failed_rollback_failed" if rollback_fails else "verify_failed_rolled_back")
    assert result["state"] == ("rollback_failed" if rollback_fails else "rolled_back")
    if rollback_fails:
        with pytest.raises(ValueError, match="还没有确认结果"):
            assert_system_maintenance_ready(str(system_api.database), str(system_api.journal_dir))
        assert system_api.get("/backups").status_code == 503
        assert system_api.read("/restore-host")["data"]["host"]["operations_available"] is False


def test_drain_timeout_before_restore_records_terminal_unchanged_and_does_not_lock_recovery(system_api, monkeypatch):
    from web.bootstrap.workbench_system_restore import WorkbenchSystemRestoreHost

    system_api.backup()
    enable_restore(system_api)

    def fail_drain(self, lease):
        raise RuntimeError("Timed out draining active work before database restore.")

    monkeypatch.setattr(WorkbenchSystemRestoreHost, "_drain", fail_drain)
    response = system_api.file_action("restore")
    assert response.status_code == 200, response.get_json()
    result = response.get_json()["data"]["operation"]
    assert result["state"] == "failed"
    assert result["code"] == "busy"
    assert result["database_origin"] == "unchanged"
    assert result["terminal"] is True
    assert result["restart_required"] is True
    assert_system_maintenance_ready(str(system_api.database), str(system_api.journal_dir))
