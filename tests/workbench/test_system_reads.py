"""System overview checks use fresh test databases and directories only."""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from core.services.system import workbench_overview as reads


def test_browser_contract_accepts_real_sections_and_rejects_malformed_shapes(system_data):
    conn, paths = system_data
    valid = [reads.build_system_overview(conn, **paths), reads.build_system_overview(None, **paths)]
    conn.execute("DROP TABLE SystemConfig")
    conn.commit()
    valid.append(reads.build_system_overview(conn, **paths))
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Browser contract tests require the build-host Node runtime"
    result = subprocess.run([node, str(Path(__file__).with_name("system_contract_probe.cjs"))],
                            input=json.dumps({"valid": valid}), text=True, capture_output=True, check=True, timeout=30)
    assert json.loads(result.stdout) == {"checks": 26, "invalid": 23}


@pytest.fixture
def system_data(tmp_path):
    db = tmp_path / "system.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE SystemConfig (
            id INTEGER PRIMARY KEY, config_key TEXT UNIQUE NOT NULL,
            config_value TEXT NOT NULL, description TEXT, updated_at TEXT
        );
        CREATE TABLE SystemJobState (
            id INTEGER PRIMARY KEY, job_key TEXT UNIQUE NOT NULL,
            last_run_time TEXT, last_run_detail TEXT, updated_at TEXT
        );
        CREATE TABLE OperationLogs (id INTEGER PRIMARY KEY, log_message TEXT);
    """)
    conn.commit()
    paths = {"db_path": str(db), "backup_dir": str(tmp_path / "backups"),
             "log_dir": str(tmp_path / "logs")}
    Path(paths["backup_dir"]).mkdir()
    Path(paths["log_dir"]).mkdir()
    yield conn, paths
    conn.close()


def _put_config(conn, key, value):
    conn.execute("INSERT INTO SystemConfig(config_key, config_value) VALUES (?, ?)", (key, value))


def _put_job(conn, kind, detail, time="2026-09-08 09:10:11"):
    conn.execute(
        "INSERT INTO SystemJobState(job_key, last_run_time, last_run_detail) VALUES (?, ?, ?)",
        (kind, time, json.dumps(detail)),
    )


def _tree_snapshot(root):
    result = {}
    for path in [root] + sorted(root.rglob("*")):
        info = path.lstat()
        result[str(path.relative_to(root))] = (
            info.st_mode, info.st_size, info.st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        )
    return result


def test_real_values_metadata_and_last_results_are_readonly(system_data, tmp_path, monkeypatch):
    conn, paths = system_data
    _put_config(conn, "auto_backup_enabled", "yes")
    _put_config(conn, "auto_backup_interval_minutes", "120")
    _put_job(conn, "auto_backup", {"filename": "aps_backup_recent.db", "size_mb": 0.1,
                                 "time_cost_ms": 3, "id": 912345, "target_id": 812345})
    _put_job(conn, "auto_backup_cleanup", {"error": "disk unavailable", "time_cost_ms": 5})
    _put_job(conn, "auto_log_cleanup", {"deleted_count": 0, "skipped": True,
                                      "reason": "total_le_min_keep", "total": 4})
    conn.commit()
    backup = Path(paths["backup_dir"]) / "aps_backup_recent.db"
    backup.write_bytes(b"not a verified database")
    (Path(paths["backup_dir"]) / "ignored.db").write_bytes(b"ignored")
    for filename in ("aps.log", "aps.log.1", "aps_error.log", "launcher.log", "aps_launch_error.txt"):
        (Path(paths["log_dir"]) / filename).write_bytes(b"log content")
    (Path(paths["log_dir"]) / "aps_secret_key.txt").write_bytes(b"test secret")
    before = _tree_snapshot(tmp_path)
    dump = list(conn.iterdump())
    changes = conn.total_changes
    statements = []
    conn.set_trace_callback(statements.append)

    def forbidden(*args, **kwargs):
        pytest.fail("Read projection attempted a write, a new database, or file content read")

    with monkeypatch.context() as guard:
        guard.setattr(reads.SystemConfigService, "get_snapshot", forbidden)
        guard.setattr(reads.SystemConfigService, "ensure_defaults", forbidden)
        guard.setattr(sqlite3, "connect", forbidden)
        guard.setattr(os, "makedirs", forbidden)
        guard.setattr(os, "mkdir", forbidden)
        guard.setattr("builtins.open", forbidden)
        guard.setattr("core.infrastructure.backup.BackupManager.__init__", forbidden)
        guard.setattr("core.services.system.system_maintenance_service.SystemMaintenanceService.run_if_due", forbidden)
        overview = reads.build_system_overview(conn, **paths)
    conn.set_trace_callback(None)
    assert conn.total_changes == changes
    assert list(conn.iterdump()) == dump
    assert _tree_snapshot(tmp_path) == before
    assert all(statement.lstrip().upper().startswith("SELECT ") for statement in statements)
    assert not conn.in_transaction
    assert set(overview) == {"database", "backups", "logs", "config", "maintenance"}
    assert overview["database"]["readable"] is True
    assert overview["database"]["table_count"] == 3
    assert overview["database"]["integrity_status"] == "not_checked"
    assert overview["backups"]["count"] == 1
    assert overview["backups"]["verification_status"] == "not_checked"
    assert overview["backups"]["files"][0]["size_bytes"] == backup.stat().st_size
    assert overview["backups"]["latest"]["filename"] == "aps_backup_recent.db"
    assert overview["logs"]["count"] == 5
    assert overview["logs"]["entry_count"] is None
    assert overview["logs"]["content_status"] == "not_read"
    assert overview["config"]["values"]["auto_backup_interval_minutes"] == 120
    assert overview["config"]["stored_values"]["auto_backup_interval_minutes"] == "120"
    assert overview["maintenance"]["record_count"] == 3
    jobs = overview["maintenance"]["jobs"]
    assert [job["result"]["status"] for job in jobs] == ["completed", "failed", "skipped"]
    assert jobs[1]["result"]["values"]["error"] == "disk unavailable"
    assert jobs[0]["last_run_time"] == "2026-09-08T09:10:11"
    encoded = json.dumps(overview)
    assert "912345" not in encoded and "812345" not in encoded
    assert "test secret" not in encoded and "aps_secret_key.txt" not in encoded


def test_defaults_do_not_persist_and_successful_empty_counts_are_zero(system_data):
    conn, paths = system_data
    changes = conn.total_changes
    result = reads.build_system_overview(conn, **paths)
    assert result["config"]["values"]["auto_backup_enabled"] == "no"
    assert result["config"]["values"]["auto_backup_keep_days"] == 7
    assert len(result["config"]["defaulted_fields"]) == 8
    assert result["config"]["stored_values"] == {}
    assert result["config"]["state"] == "empty"
    assert result["config"]["stored_count"] == 0
    assert result["config"]["writes_performed"] is False
    assert conn.execute("SELECT COUNT(*) FROM SystemConfig").fetchone()[0] == 0
    assert conn.total_changes == changes
    for section in ("backups", "logs"):
        assert result[section]["state"] == "empty"
        assert result[section]["count"] == 0
    assert result["maintenance"]["state"] == "empty"
    assert result["maintenance"]["record_count"] == 0
    assert all(job["status"] == "empty" for job in result["maintenance"]["jobs"])


def test_instance_backup_default_is_used_without_persistence(system_data):
    conn, paths = system_data
    result = reads.build_system_overview(conn, **paths, backup_keep_days_default=21)
    assert result["config"]["values"]["auto_backup_keep_days"] == 21
    assert "auto_backup_keep_days" in result["config"]["defaulted_fields"]
    assert conn.execute("SELECT COUNT(*) FROM SystemConfig").fetchone()[0] == 0


def test_dirty_config_is_explicit_and_not_repaired(system_data):
    conn, paths = system_data
    _put_config(conn, "auto_backup_interval_minutes", "broken")
    _put_config(conn, "auto_log_cleanup_keep_days", "999")
    conn.commit()
    result = reads.build_system_overview(conn, **paths)["config"]
    assert result["state"] == "partial"
    assert result["values"]["auto_backup_interval_minutes"] == 60
    assert result["values"]["auto_log_cleanup_keep_days"] == 365
    assert result["stored_values"]["auto_backup_interval_minutes"] == "broken"
    assert len(result["dirty_reasons"]) == 2
    assert conn.execute("SELECT config_value FROM SystemConfig WHERE config_key = ?",
                        ("auto_log_cleanup_keep_days",)).fetchone()[0] == "999"


def test_unread_missing_and_empty_are_distinct_and_do_not_create_paths(tmp_path):
    result = reads.build_system_overview(
        None, db_path=str(tmp_path / "missing.db"),
        backup_dir=str(tmp_path / "missing-backups"), log_dir="",
    )
    assert result["database"]["state"] == "not_read"
    assert result["database"]["file"]["status"] == "missing"
    assert result["backups"]["state"] == "missing"
    assert result["backups"]["count"] is None
    assert result["logs"]["state"] == "not_read"
    assert result["logs"]["count"] is None
    assert result["config"]["state"] == "not_read"
    assert result["config"]["values"] is None
    assert result["maintenance"]["record_count"] is None
    assert list(tmp_path.iterdir()) == []


def test_missing_tables_are_read_failures_not_empty_or_default_config(mem_conn):
    result = reads.build_system_overview(mem_conn, db_path=":memory:", backup_dir="", log_dir="")
    assert result["database"]["readable"] is True
    assert result["database"]["table_count"] == 0
    assert result["config"]["state"] == "error"
    assert result["config"]["values"] is None
    assert result["config"]["defaulted_fields"] is None
    assert "no such table" in result["config"]["error"]["message"]
    assert result["maintenance"]["state"] == "error"
    assert result["maintenance"]["record_count"] is None
    assert all(job["error"] for job in result["maintenance"]["jobs"])


def test_closed_connection_failure_does_not_hide_readable_files(system_data):
    conn, paths = system_data
    conn.close()
    result = reads.build_system_overview(conn, **paths)
    assert result["database"]["readable"] is False
    assert result["database"]["table_count"] is None
    assert result["config"]["state"] == "error"
    assert result["maintenance"]["state"] == "error"
    assert result["backups"]["state"] == "empty"
    assert result["logs"]["state"] == "partial"
    assert result["logs"]["files_state"] == "empty"
    assert result["logs"]["operation_record_count"] is None


def test_permission_and_single_file_failures_are_visible(system_data, monkeypatch):
    conn, paths = system_data
    for name in ("aps_backup_good.db", "aps_backup_unreadable.db"):
        (Path(paths["backup_dir"]) / name).write_bytes(b"metadata only")
    real_stat = reads.stat_regular_file
    real_listdir = os.listdir

    def fail_one_file(path):
        if str(path).endswith("unreadable.db"):
            raise PermissionError("file metadata denied")
        return real_stat(path)

    def fail_log_dir(path):
        if str(path) == paths["log_dir"]:
            raise PermissionError("directory listing denied")
        return real_listdir(path)

    monkeypatch.setattr(reads, "stat_regular_file", fail_one_file)
    monkeypatch.setattr(os, "listdir", fail_log_dir)
    result = reads.build_system_overview(conn, **paths)
    assert result["backups"]["state"] == "partial"
    assert result["backups"]["count"] is None
    assert result["backups"]["known_count"] == 1
    assert result["backups"]["latest"] is None
    assert result["backups"]["issues"][0]["error"]["code"] == "PermissionError"
    assert result["logs"]["state"] == "partial"
    assert result["logs"]["files_state"] == "error"
    assert result["logs"]["count"] is None
    assert result["logs"]["known_count"] is None
    assert result["logs"]["error"]["message"] == "directory listing denied"


@pytest.mark.parametrize("detail", [[], "text", {"deleted_count": -1}, {"deleted_count": True}])
def test_invalid_task_result_is_not_success(system_data, detail):
    conn, paths = system_data
    _put_job(conn, "auto_log_cleanup", detail)
    result = reads.build_system_overview(conn, **paths)
    job = result["maintenance"]["jobs"][2]
    assert job["status"] == "partial"
    assert job["result"]["status"] == "invalid"
    assert job["result"]["error"]


def test_bad_json_bad_time_and_unknown_detail_are_visible(system_data):
    conn, paths = system_data
    _put_job(conn, "auto_backup", {"filename": "aps_backup_old.db"}, time="not a time")
    _put_job(conn, "auto_backup_cleanup", {"private_id": 999})
    _put_job(conn, "auto_log_cleanup", {})
    conn.execute("UPDATE SystemJobState SET last_run_detail = '{broken' WHERE job_key = 'auto_log_cleanup'")
    result = reads.build_system_overview(conn, **paths)["maintenance"]
    assert result["state"] == "partial"
    assert result["jobs"][0]["last_run_time"] is None
    assert result["jobs"][0]["last_run_time_status"] == "invalid"
    assert result["jobs"][1]["result"]["status"] == "unknown"
    assert result["jobs"][2]["result"]["status"] == "invalid"
    assert "private_id" not in json.dumps(result)


def test_partial_cleanup_is_not_reported_as_success(system_data):
    conn, paths = system_data
    _put_job(conn, "auto_backup_cleanup", {"removed_count": 1, "delete_error_count": 2})
    job = reads.build_system_overview(conn, **paths)["maintenance"]["jobs"][1]
    assert job["result"]["status"] == "partial"
    assert job["result"]["values"]["delete_error_count"] == 2


def test_recent_metadata_is_bounded_but_count_is_complete(system_data):
    conn, paths = system_data
    for index in range(25):
        path = Path(paths["backup_dir"]) / f"aps_backup_{index:02d}.db"
        path.write_bytes(b"x")
        os.utime(str(path), (1700000000 + index, 1700000000 + index))
    result = reads.build_system_overview(conn, **paths)["backups"]
    assert result["count"] == 25
    assert result["known_count"] == 25
    assert len(result["files"]) == 20
    assert result["files_truncated"] is True
    assert result["files"][0]["filename"] == "aps_backup_24.db"


def test_existing_caller_transaction_is_not_committed_or_rolled_back(system_data):
    conn, paths = system_data
    _put_config(conn, "auto_backup_enabled", "yes")
    assert conn.in_transaction
    changes = conn.total_changes
    result = reads.build_system_overview(conn, **paths)
    assert result["config"]["values"]["auto_backup_enabled"] == "yes"
    assert conn.in_transaction
    assert conn.total_changes == changes
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM SystemConfig").fetchone()[0] == 0


def test_readonly_connection_and_authorizer_allow_selects_only(system_data, tmp_path):
    _, paths = system_data
    before = _tree_snapshot(tmp_path)
    conn = sqlite3.connect(Path(paths["db_path"]).as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    denied = []

    def authorize(action, arg1, arg2, database, trigger):
        if action not in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION):
            denied.append((action, arg1, arg2))
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    conn.set_authorizer(authorize)
    try:
        result = reads.build_system_overview(conn, **paths)
        assert result["database"]["state"] == "available"
        assert result["config"]["state"] == "empty"
        assert result["maintenance"]["state"] == "empty"
        assert denied == []
    finally:
        conn.close()
    assert _tree_snapshot(tmp_path) == before


def test_one_task_query_failure_preserves_other_results(system_data, monkeypatch):
    conn, paths = system_data
    _put_job(conn, "auto_backup", {"filename": "aps_backup_saved.db"})
    real_get = reads.SystemJobStateQueryService.get

    def fail_one(service, kind):
        if kind == "auto_backup_cleanup":
            raise sqlite3.OperationalError("task query denied")
        return real_get(service, kind)

    monkeypatch.setattr(reads.SystemJobStateQueryService, "get", fail_one)
    result = reads.build_system_overview(conn, **paths)["maintenance"]
    assert result["state"] == "partial"
    assert result["record_count"] is None
    assert result["known_record_count"] == 1
    assert result["jobs"][0]["result"]["status"] == "completed"
    assert result["jobs"][1]["error"]["message"] == "task query denied"
    assert result["jobs"][2]["status"] == "empty"


def test_path_is_a_file_is_an_error_not_a_missing_directory(system_data, tmp_path):
    conn, paths = system_data
    not_directory = tmp_path / "not-a-directory"
    not_directory.write_bytes(b"keep")
    paths["backup_dir"] = str(not_directory)
    result = reads.build_system_overview(conn, **paths)["backups"]
    assert result["state"] == "error"
    assert result["count"] is None
    assert result["error"]["code"] == "NotADirectoryError"
    assert not_directory.read_bytes() == b"keep"


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory"])
def test_unsafe_backup_candidates_are_not_counted_as_valid_files(system_data, tmp_path, kind):
    conn, paths = system_data
    target = tmp_path / "target"
    target.write_bytes(b"do not read")
    candidate = Path(paths["backup_dir"]) / "aps_backup_unsafe.db"
    try:
        if kind == "symlink":
            candidate.symlink_to(target)
        elif kind == "hardlink":
            os.link(str(target), str(candidate))
        else:
            candidate.mkdir()
    except (OSError, NotImplementedError):
        pytest.skip("Test host does not support creating this link type")
    result = reads.build_system_overview(conn, **paths)["backups"]
    assert result["state"] == "partial"
    assert result["count"] is None
    assert result["known_count"] == 0
    assert result["files"] == []
    assert result["issues"][0]["error"]["code"] == "UnsafeFixedFileError"


def test_disappearing_candidate_is_explicitly_missing(system_data, monkeypatch):
    conn, paths = system_data
    candidate = Path(paths["backup_dir"]) / "aps_backup_gone.db"
    candidate.write_bytes(b"x")
    real_stat = reads.stat_regular_file

    def disappeared(path):
        if str(path) == str(candidate):
            raise FileNotFoundError("candidate disappeared after listing")
        return real_stat(path)

    monkeypatch.setattr(reads, "stat_regular_file", disappeared)
    result = reads.build_system_overview(conn, **paths)["backups"]
    assert result["state"] == "partial"
    assert result["count"] is None
    assert result["issues"][0]["status"] == "missing"


def test_oversized_or_absent_task_details_do_not_imply_success(system_data):
    conn, paths = system_data
    _put_job(conn, "auto_backup", {"error": "x" * 17000})
    _put_job(conn, "auto_backup_cleanup", {})
    conn.execute("UPDATE SystemJobState SET last_run_detail = NULL WHERE job_key = 'auto_backup_cleanup'")
    jobs = reads.build_system_overview(conn, **paths)["maintenance"]["jobs"]
    assert jobs[0]["result"]["status"] == "invalid"
    assert jobs[1]["result"]["status"] == "not_recorded"
    assert jobs[0]["status"] == jobs[1]["status"] == "partial"


def test_log_files_and_operation_records_have_independent_real_counts(system_data):
    conn, paths = system_data
    conn.executemany("INSERT INTO OperationLogs(log_message) VALUES (?)",
                     [("private content one",), ("private content two",)])
    conn.commit()
    result = reads.build_system_overview(conn, **paths)["logs"]
    assert result["state"] == "available"
    assert result["files_state"] == "empty"
    assert result["count"] == 0
    assert result["operation_record_count"] == 2
    assert result["operation_records_state"] == "available"
    assert "private content" not in json.dumps(result)
    Path(paths["log_dir"]).rmdir()
    result = reads.build_system_overview(conn, **paths)["logs"]
    assert result["state"] == "partial"
    assert result["files_state"] == "missing"
    assert result["count"] is None
    assert result["operation_record_count"] == 2


def test_operation_record_count_failure_does_not_become_zero(system_data):
    conn, paths = system_data
    conn.execute("DROP TABLE OperationLogs")
    (Path(paths["log_dir"]) / "aps.log").write_bytes(b"do not read the body")
    result = reads.build_system_overview(conn, **paths)["logs"]
    assert result["state"] == "partial"
    assert result["files_state"] == "available"
    assert result["count"] == 1
    assert result["operation_record_count"] is None
    assert result["operation_records_state"] == "error"
    assert "no such table" in result["operation_records_error"]["message"]
    assert result["error"] == result["operation_records_error"]


def test_all_sections_expose_state_message_and_serializable_metadata(schema_conn):
    result = reads.build_system_overview(schema_conn, db_path=":memory:", backup_dir="", log_dir="")
    for section in result.values():
        assert section["state"] in ("available", "empty", "missing", "not_read", "error", "partial")
        assert section["message"]
        assert "status" not in section
    assert result["database"]["integrity_status"] == "not_checked"
    assert result["logs"]["operation_record_count"] == 0
    assert result["config"]["writes_performed"] is False
    json.dumps(result, allow_nan=False)
