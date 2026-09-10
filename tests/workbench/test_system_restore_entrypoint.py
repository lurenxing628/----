"""DP end-to-end data protection through actual process startup and shutdown."""

import http.client
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from core.services.workbench.system_journal import file_fingerprint
from tests.workbench.system_restore_entrypoint_support import (
    BASE,
    KEY,
    ProcessHost,
    marker,
    seed_database,
    wait_for,
)
from web.bootstrap.launcher_shutdown import HOST_STOP_PATH
from web.bootstrap.launcher_stop import _request_runtime_shutdown


def test_writable_real_host_restore_and_fresh_process_replay_preserve_data(tmp_path):
    host = ProcessHost(tmp_path)
    source = seed_database(host)
    try:
        host.start()
        assert host.ready["runtime_ready"] and host.ready["guard_is_controller"]
        assert host.ready["candidate_enabled"] and host.ready["calibration_enabled"]
        assert host.ready["host"]["operations_available"]
        body = host.restore_body()
        status, payload = host.request(BASE + "/backups/restore", body, "POST")
        assert status == 200, payload
        result = payload["data"]["operation"]
        assert result["state"] == "succeeded" and result["code"] == "verified"
        assert result["restart_required"] and result["restart_scope"] == "restoring_process"
        assert result["target_sha256"] == file_fingerprint(str(source))
        protection = host.backups / result["protection_filename"]
        assert result["protection_sha256"] == file_fingerprint(str(protection))
        assert result["database_after_sha256"] == file_fingerprint(str(host.path))
        assert marker(host.path) == "selected" and marker(protection) == "current"
        assert payload["data"]["host"]["operations_available"] is False
        assert host.request(BASE + "/backups/restore", body, "POST")[0] == 503
        assert host.request("/system/health")[0] == 503
        host.locked()
        preserved = host.hashes()
        first_pid = host.process.pid
        host.stop()
        assert host.hashes() == preserved and not list(host.backups.glob("*_exit.db"))
    finally:
        host.close()
    restarted = ProcessHost(tmp_path)
    try:
        restarted.start()
        assert restarted.process.pid != first_pid and restarted.ready["runtime_ready"]
        status, replay = restarted.request(BASE + "/backups/restore", body, "POST")
        assert status == 200, replay
        assert replay["data"]["operation"]["replayed"] is True
        assert replay["data"]["operation"]["job_ref"] == result["job_ref"]
        assert replay["data"]["host"]["restart_required"] is False
        assert len(list(restarted.backups.glob("*before_restore.db"))) == 1
        assert marker(restarted.path) == "selected"
        restarted.stop()
        assert len(list(restarted.backups.glob("*_exit.db"))) == 1
    finally:
        restarted.close()


@pytest.mark.parametrize("rollback_fails", [False, True])
def test_real_entrypoint_rollback_outcome_and_exit_never_modify_unconfirmed_database(tmp_path, rollback_fails):
    host = ProcessHost(tmp_path, "rollback-failure" if rollback_fails else "verify-failure")
    seed_database(host)
    try:
        host.start()
        status, payload = host.request(BASE + "/backups/restore", host.restore_body(), "POST")
        assert status == 200, payload
        result = payload["data"]["operation"]
        assert result["state"] == ("rollback_failed" if rollback_fails else "rolled_back")
        assert result["terminal"] is (not rollback_fails)
        assert result["database_origin"] == ("unconfirmed" if rollback_fails else "protection_backup")
        assert marker(host.path) == ("selected" if rollback_fails else "current")
        assert marker(host.backups / result["protection_filename"]) == "current"
        host.locked()
        before = host.hashes()
        host.stop()
        assert before == host.hashes() and not list(host.backups.glob("*_exit.db"))
    finally:
        host.close()
    restarted = ProcessHost(tmp_path, "no-database" if rollback_fails else "normal")
    try:
        restarted.start()
        assert restarted.ready["runtime_ready"] is (not rollback_fails)
        status, payload = restarted.request(BASE + "/results/" + KEY)
        assert status == 200 and payload["data"]["operation"]["job_ref"] == result["job_ref"]
        restarted.stop()
    finally:
        restarted.close()


def test_actual_process_crash_keeps_durable_journal_and_restarts_without_replay_or_db_open(tmp_path):
    host = ProcessHost(tmp_path, "crash-verifying")
    seed_database(host)
    try:
        host.start()
        body = host.restore_body()
        with pytest.raises((http.client.RemoteDisconnected, ConnectionResetError)):
            host.request(BASE + "/backups/restore", body, "POST")
        assert host.process.wait(timeout=10) == 86
        row = host.journal().lookup(KEY)
        assert row is not None
        assert row["state"] == "verifying" and row["protection"]
        assert marker(host.path) == "selected"
        assert marker(host.backups / row["protection"]["filename"]) == "current"
        host.locked()
        before = host.hashes()
    finally:
        host.close()
    recovery = ProcessHost(tmp_path, "no-database")
    try:
        recovery.start()
        assert recovery.ready["runtime_ready"] is False
        status, payload = recovery.request(BASE + "/results/" + KEY)
        assert status == 200 and payload["data"]["operation"]["job_ref"] == row["job_ref"]
        assert payload["data"]["operation"]["state"] == "verifying"
        assert recovery.request(BASE + "/backups/restore", body, "POST")[0] == 503
        recovery.stop()
        assert recovery.hashes() == before
        assert len(list(recovery.backups.glob("*before_restore.db"))) == 1
    finally:
        recovery.close()


def test_real_server_stop_retains_original_locks_until_worker_finishes_and_exit_backup_completes(tmp_path):
    host = ProcessHost(tmp_path, "pause-worker")
    seed_database(host)
    try:
        host.start()
        wait_for(lambda: (host.root / "worker-entered").exists())
        assert _request_runtime_shutdown(host.contract)
        wait_for(lambda: (host.root / "worker-stopping").exists())
        assert host.process.poll() is None
        host.locked()
        assert not list(host.backups.glob("*_exit.db"))
        (host.root / "worker-release").touch()
        assert host.process.wait(timeout=20) == 0
        assert all(not path.exists() for path in host.lock_paths)
        backups = list(host.backups.glob("*_exit.db"))
        assert len(backups) == 1
        with closing(sqlite3.connect(str(backups[0]))) as conn:
            assert conn.execute("SELECT state FROM WorkbenchRunJobs").fetchone()[0] == "complete"
    finally:
        host.close()


def test_real_entrypoint_restore_drains_http_and_worker_before_protection(tmp_path):
    host = ProcessHost(tmp_path, "pause-worker")
    seed_database(host)
    try:
        host.start()
        body = host.restore_body()
        wait_for(lambda: (host.root / "worker-entered").exists())
        with ThreadPoolExecutor(2) as pool:
            held = pool.submit(host.request, "/api/workbench/v1/dp-held-response")
            try:
                wait_for(lambda: (host.root / "http-entered").exists())
                restoring = pool.submit(host.request, BASE + "/backups/restore", body, "POST")
                wait_for(lambda: (host.root / "worker-stopping").exists())
                host.locked()
                assert not list(host.backups.glob("*before_restore.db"))
                assert host.request("/scheduler/")[0] == 503
                (host.root / "worker-release").touch()
                wait_for(lambda: (host.root / "worker-computed").exists())
                assert not list(host.backups.glob("*before_restore.db")), "HTTP iterator/DB still active"
            finally:
                (host.root / "worker-release").touch()
                (host.root / "http-release").touch()
            assert held.result(timeout=10) == (200, b"first\nlast\n")
            status, payload = restoring.result(timeout=15)
            assert status == 200 and payload["data"]["operation"]["state"] == "succeeded", payload
        result = payload["data"]["operation"]
        with closing(sqlite3.connect(str(host.backups / result["protection_filename"]))) as conn:
            assert conn.execute("SELECT state FROM WorkbenchRunJobs").fetchone()[0] == "complete"
        assert host.request(HOST_STOP_PATH, method="GET", token=host.contract["shutdown_token"])[0] == 400
        host.stop()
        assert not list(host.backups.glob("*_exit.db"))
    finally:
        host.close()
