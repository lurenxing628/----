"""Run the original restore assertions on the concrete DH controller contract."""

from pathlib import Path

import pytest

from tests.workbench.test_system_maintenance_support import BASE, SystemTestAPI
from web.bootstrap import factory
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime
from web.bootstrap.workbench_system_restore import install_workbench_system_restore_host


class ManagedSystemAPI(SystemTestAPI):
    def __init__(self, app, root):
        self.app, self.root = app, root
        self.database = Path(app.config["DATABASE_PATH"])
        self.backups = Path(app.config["BACKUP_DIR"])
        self.logs = Path(app.config["LOG_DIR"])
        self.journal_dir = Path(app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"])
        self.client = app.test_client()

    def get(self, path, **query):
        return self.client.get(BASE + path, query_string=query, buffered=True)

    def post(self, path, input_value, token, key="system-test-request-0001"):
        return self.client.post(BASE + path, json={"request_key": key, "write_token": token,
                                                 "input": input_value}, buffered=True)


@pytest.fixture(name="system_api")
def system_api(db_env, tmp_path, monkeypatch):
    monkeypatch.setenv("APS_ENV", "production")
    journal_dir = tmp_path / "legacy-restore-journal"
    journal_dir.mkdir()
    monkeypatch.setenv("APS_SYSTEM_JOURNAL_DIR", str(journal_dir))
    scope = str(tmp_path / "legacy-restore-host")
    payload = acquire_runtime_lock(scope, db_path=db_env)
    runtime = gate = None
    try:
        app = factory.create_app_core(ui_mode="default", enable_secret_key=False,
                                     enable_security_headers=False, enable_session_cookie_hardening=False)
        app.config["TESTING"] = True
        gate = app.extensions["workbench_request_lifecycle"]
        runtime = install_workbench_run_runtime(app, runtime_lock=payload)
        install_workbench_system_restore_host(app, runtime=runtime)
        yield ManagedSystemAPI(app, tmp_path)
    finally:
        if runtime is not None:
            assert runtime.shutdown(timeout=15)
        if gate is not None:
            assert gate.shutdown(timeout=15)
        release_runtime_lock(scope, db_path=db_env)
