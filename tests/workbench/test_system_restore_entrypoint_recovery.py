"""First DB open is forbidden; real locked recovery serves only old journals."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.infrastructure.backup import BackupManager
from core.services.workbench.system_journal import SystemMaintenanceJournal
from tests.workbench.system_restore_entrypoint_support import BASE, KEY, REPO, ProcessHost
from web.bootstrap import factory
from web.bootstrap.launcher_shutdown import HOST_STOP_PATH
from web.bootstrap.workbench_system_restore_recovery import system_journal_directory


@pytest.mark.parametrize("state", ["accepted", "checking", "verifying", "rolling_back", "recovery_required"])
def test_pending_real_entrypoint_never_opens_database_and_keeps_original_receipt(tmp_path, state):
    host = ProcessHost(tmp_path, "no-database")
    host.path.write_bytes(b"DP crash-site database bytes: must not open or migrate")
    row, _ = host.journal().begin(KEY, "restore", {})
    host.journal().record(row, state)
    before = host.hashes()
    try:
        host.start()
        assert not host.ready["runtime_ready"] and not host.ready["run_enabled"]
        assert not host.ready["candidate_enabled"] and not host.ready["calibration_enabled"]
        status, payload = host.request(BASE + "/results/" + KEY)
        assert status == 200 and payload["data"]["operation"]["state"] == state
        assert payload["data"]["host"]["operations_available"] is False
        assert payload["data"]["host"]["automatic_resume"] is False
        for path in ("/workbench", "/system/health", "/scheduler/", "/static/test.css"):
            assert host.request(path)[0] == 503
        assert host.request(BASE + "/backups/restore", {}, "POST")[0] == 503
        assert host.request("/system/runtime/shutdown", method="POST", token=host.contract["shutdown_token"])[0] == 503
        assert host.request(HOST_STOP_PATH, method="POST", token="wrong-token")[0] == 403
        host.locked()
        assert host.hashes() == before
        host.stop()
        assert host.hashes() == before
        assert not (host.root / "templates").exists()
    finally:
        host.close()


@pytest.mark.parametrize("damage", ["corrupt-record", "missing-database", "unknown-terminal"])
def test_unknown_maintenance_is_read_only_but_known_original_record_remains_queryable(tmp_path, damage):
    host = ProcessHost(tmp_path, "no-database")
    row, _ = host.journal().begin(KEY, "restore", {})
    if damage == "corrupt-record":
        (host.journal_dir / "damaged.json").write_text('{"state":', encoding="utf-8")
    elif damage == "unknown-terminal":
        host.journal().record(row, "succeeded", code="unknown-success")
    before = host.hashes()
    try:
        host.start()
        status, payload = host.request(BASE + "/restore-host")
        assert status == 200 and payload["data"]["host"]["state"] == "recovery_required"
        status, payload = host.request(BASE + "/results/" + KEY)
        assert status == (503 if damage == "unknown-terminal" else 200)
        if status == 200:
            assert payload["data"]["operation"]["job_ref"] == row["job_ref"]
        assert not host.path.exists()
        host.stop()
        assert host.hashes() == before
    finally:
        host.close()


@pytest.mark.parametrize("journal_config", ["", "relative/journal"])
def test_invalid_journal_configuration_keeps_db_free_status_transport(tmp_path, monkeypatch, journal_config):
    monkeypatch.setenv("APS_DB_PATH", str(tmp_path / "no-db.db"))
    monkeypatch.setenv("APS_SYSTEM_JOURNAL_DIR", journal_config)
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid journal must not reach normal factory initialization")
    monkeypatch.setattr(factory, "ensure_schema", forbidden)
    monkeypatch.setattr(factory, "_ensure_runtime_dirs", forbidden)
    app = factory.create_app_core(ui_mode="default", enable_secret_key=False,
                                 enable_security_headers=False, enable_session_cookie_hardening=False)
    client = app.test_client()
    response = client.get(BASE + "/restore-host")
    assert response.status_code == 200
    assert response.json is not None
    assert response.json["data"]["host"]["operations_available"] is False
    assert client.get(BASE + "/results/" + KEY).status_code == 503
    assert client.get("/workbench").status_code == 503


@pytest.mark.parametrize("damage", ["pending", "corrupt"])
def test_exit_backup_refuses_before_configuration_read_or_database_open(tmp_path, monkeypatch, damage):
    path = str(tmp_path / "untouched.db")
    directory = system_journal_directory(path)
    journal = SystemMaintenanceJournal(directory, path)
    journal.begin(KEY, "restore", {})
    if damage == "corrupt":
        from pathlib import Path
        Path(directory, "corrupt.json").write_text("{", encoding="utf-8")
    def forbidden(*args, **kwargs):
        raise AssertionError("Exit backup read/open/write must remain unreachable")
    monkeypatch.setattr(factory, "get_connection", forbidden)
    monkeypatch.setattr(factory, "_is_exit_backup_enabled", forbidden)
    monkeypatch.setattr(BackupManager, "backup", forbidden)
    assert factory._run_exit_backup(BackupManager(path, str(tmp_path / "backups"))) is False


def test_real_runtime_stop_cli_stops_pending_host_without_database_or_force_kill(tmp_path):
    host = ProcessHost(tmp_path, "no-database")
    host.path.write_bytes(b"DP original crash data")
    host.journal().begin(KEY, "restore", {})
    before = host.hashes()
    script = '''
import sqlite3, sys
def forbidden(*args, **kwargs):
    raise AssertionError("Stop CLI must not open SQLite or kill a process")
sqlite3.connect = forbidden
from web.bootstrap import entrypoint, launcher_stop
launcher_stop._kill_runtime_pid = forbidden
sys.exit(entrypoint.app_main(anchor_file=sys.argv[1] + "/app.py", argv=["--runtime-stop", sys.argv[1]]))
'''
    try:
        host.start()
        with ThreadPoolExecutor(1) as pool:
            # Reap only our child, so the independent CLI can confirm PID exit.
            stopped = pool.submit(host.process.wait, 20)
            result = subprocess.run([sys.executable, "-c", script, str(host.root)], cwd=str(REPO),
                                    capture_output=True, text=True, timeout=20)
            assert result.returncode == 0, result.stdout + result.stderr
            assert stopped.result(timeout=5) == 0
        assert all(not path.exists() for path in host.lock_paths)
        assert host.hashes() == before
    finally:
        host.close()
