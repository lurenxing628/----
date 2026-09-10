"""Never publish a writable runtime after late/unknown maintenance admission."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from core.services.workbench.system_journal import file_fingerprint
from tests.workbench.system_restore_entrypoint_support import BASE, KEY, ProcessHost, seed_database, wait_for
from tests.workbench.system_restore_host_support import restore_host as _restore_host  # noqa: F401
from web.bootstrap import factory


def test_pending_after_real_runtime_install_stops_worker_before_read_only_http_publication(tmp_path):
    host = ProcessHost(tmp_path, "pending-after-runtime")
    seed_database(host)
    try:
        host.start()
        before = (host.root / "before-maintenance.sha256").read_text(encoding="ascii")
        assert host.ready["runtime_ready"] is False and host.ready["guard_is_controller"] is False
        assert host.ready["candidate_enabled"] is False and host.ready["calibration_enabled"] is False
        assert host.request("/system/health")[0] == 503
        status, payload = host.request(BASE + "/results/" + KEY)
        assert status == 200 and payload["data"]["operation"]["state"] == "accepted"
        assert payload["data"]["host"]["operations_available"] is False
        host.locked()
        host.stop()
        assert file_fingerprint(str(host.path)) == before
        assert not list(host.backups.glob("*_exit.db"))
    finally:
        host.close()


@pytest.mark.parametrize("damage", ["pending", "unreadable"])
def test_running_host_closes_admission_on_unknown_journal_but_keeps_original_lookup(tmp_path, damage):
    host = ProcessHost(tmp_path)
    seed_database(host)
    try:
        host.start()
        row, _ = host.journal().begin(KEY, "restore", {})
        if damage == "unreadable":
            (host.journal_dir / "corrupt.json").write_text("{", encoding="utf-8")
        before = host.hashes()
        status, payload = host.request(BASE + "/restore-host")
        assert status == 200 and payload["data"]["host"]["state"] == "recovery_required"
        assert payload["data"]["host"]["operations_available"] is False
        assert host.request("/workbench")[0] == 503
        status, payload = host.request(BASE + "/results/" + KEY)
        assert status == 200 and payload["data"]["operation"]["job_ref"] == row["job_ref"]
        host.locked()
        host.stop()
        assert host.hashes() == before
    finally:
        host.close()


def test_confirmed_terminal_cannot_recreate_normal_factory_in_same_process(restore_host, monkeypatch):
    case = restore_host
    body = case.intent()
    response = case.client.post(BASE + "/backups/restore", json=body, buffered=True)
    assert response.status_code == 200 and response.json["data"]["operation"]["state"] == "succeeded"
    before = file_fingerprint(case.path)
    monkeypatch.setenv("APS_SYSTEM_JOURNAL_DIR", case.journal.directory)
    def forbidden(*args, **kwargs):
        raise AssertionError("Same-process reconstruction reached DB/template initialization")
    monkeypatch.setattr(factory, "get_connection", forbidden)
    monkeypatch.setattr(factory, "ensure_schema", forbidden)
    monkeypatch.setattr(factory, "_ensure_runtime_dirs", forbidden)
    app = factory.create_app_core(ui_mode="default", enable_secret_key=False,
                                 enable_security_headers=False, enable_session_cookie_hardening=False)
    assert app.extensions["workbench_system_restore_recovery"] is True
    client = app.test_client()
    assert client.get("/workbench").status_code == 503
    result = client.get(BASE + "/results/" + body["request_key"])
    assert result.json is not None
    assert result.status_code == 200 and result.json["data"]["operation"]["state"] == "succeeded"
    assert file_fingerprint(case.path) == before
    case.assert_locks_held()


def test_active_owned_backup_is_not_misreported_as_interrupted_restore(tmp_path):
    host = ProcessHost(tmp_path, "pause-backup")
    seed_database(host)
    try:
        host.start()
        status, payload = host.request(BASE + "/backups")
        assert status == 200
        token = payload["data"]["create_context"]["write_token"]
        body = {"request_key": KEY, "write_token": token, "input": {}}
        with ThreadPoolExecutor(1) as pool:
            backup = pool.submit(host.request, BASE + "/backups/create", body, "POST")
            try:
                wait_for(lambda: (host.root / "backup-entered").exists())
                status, payload = host.request(BASE + "/restore-host")
                assert status == 200
                assert payload["data"]["host"]["state"] == "ready"
                assert payload["data"]["host"]["operations_available"] is False
                assert payload["data"]["host"]["restart_required"] is False
            finally:
                (host.root / "backup-release").touch()
            status, payload = backup.result(timeout=10)
            assert status == 200 and payload["data"]["operation"]["state"] == "succeeded", payload
        status, payload = host.request(BASE + "/restore-host")
        assert status == 200 and payload["data"]["host"]["operations_available"] is True
        host.stop()
    finally:
        host.close()
