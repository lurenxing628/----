"""Scanned shutdown handlers must expose failure and keep writes disabled."""

import logging
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

from core.infrastructure.backup import BackupManager
from core.infrastructure.database import get_connection
from core.services.system import SystemConfigService
from web.bootstrap import entrypoint, factory, launcher_shutdown
from web.bootstrap.workbench_run_runtime import WorkbenchRunRuntime


def _manager(db_path, tmp_path):
    return BackupManager(db_path, str(tmp_path / "backups"),
                         logger=logging.getLogger("round1.shutdown"))


def _runtime(tmp_path):
    app = SimpleNamespace(config={"DATABASE_PATH": str(tmp_path / "absent.db")},
                          extensions={}, debug=False, logger=logging.getLogger("round1.runtime"))
    return WorkbenchRunRuntime(app)


def _assert_disabled(runtime):
    for key in ("WORKBENCH_RUN_JOBS_ENABLED", "WORKBENCH_CANDIDATE_ADOPTION_ENABLED",
                "WORKBENCH_CALIBRATION_ADOPTION_ENABLED", "WORKBENCH_POINT_RENDERING_ENABLED"):
        assert runtime.app.config[key] is False
    assert not runtime.ready
    assert "workbench_run_dispatcher" not in runtime.app.extensions


def test_exit_config_read_failure_is_unknown_not_enabled(db_path, tmp_path, caplog):
    def fail(_path):
        raise sqlite3.OperationalError("round1 config unavailable")

    manager = _manager(db_path, tmp_path)
    assert launcher_shutdown.read_exit_backup_enabled(manager, fail) is None
    assert "round1 config unavailable" in caplog.text
    assert not list((tmp_path / "backups").glob("*_exit.db"))


def test_config_close_failure_propagates_and_prevents_exit_backup(db_path, tmp_path, monkeypatch, caplog):
    conn = get_connection(db_path)
    manager = _manager(db_path, tmp_path)
    calls = []

    class BrokenClose:
        def __getattr__(self, name):
            return getattr(conn, name)

        def close(self):
            raise sqlite3.OperationalError("round1 config close uncertain")

    monkeypatch.setattr(manager, "backup", lambda **kwargs: calls.append(kwargs))
    try:
        SystemConfigService(conn).set_value("auto_backup_enabled", "yes")
        read_enabled = lambda target: launcher_shutdown.read_exit_backup_enabled(target, lambda _path: BrokenClose())
        with pytest.raises(sqlite3.OperationalError, match="close uncertain"):
            read_enabled(manager)
        assert launcher_shutdown.run_exit_backup(manager, read_enabled) is False
        assert calls == []
        assert "round1 config close uncertain" in caplog.text
    finally:
        conn.close()


def test_exit_backup_failure_does_not_claim_success(db_path, tmp_path, monkeypatch, caplog):
    def fail(**_kwargs):
        raise OSError("round1 backup persistence failed")

    manager = _manager(db_path, tmp_path)
    monkeypatch.setattr(manager, "backup", fail)
    assert launcher_shutdown.run_exit_backup(manager, lambda _manager: True) is False
    assert "round1 backup persistence failed" in caplog.text
    assert not list((tmp_path / "backups").glob("*_exit.db"))


def test_runtime_start_failure_disables_every_write_without_opening_database(tmp_path, caplog):
    runtime = _runtime(tmp_path)
    runtime._start(None)
    _assert_disabled(runtime)
    assert runtime._thread is None
    assert not (tmp_path / "absent.db").exists()
    assert "runtime installation failed" in caplog.text


def test_dispatch_ownership_failure_propagates_before_queuing(tmp_path, monkeypatch, caplog):
    runtime = _runtime(tmp_path)
    runtime._publish(True, "ready")

    def fail():
        raise RuntimeError("round1 ownership changed")

    monkeypatch.setattr(runtime, "_verify", fail)
    with pytest.raises(RuntimeError, match="ownership changed"):
        runtime("a" * 48)
    _assert_disabled(runtime)
    assert runtime._stop.is_set() and runtime._queue.empty() and runtime._pending == set()
    assert "a" * 48 in caplog.text and "ownership changed" in caplog.text


def test_worker_and_reconciliation_failure_stop_without_retrying_compute(tmp_path, monkeypatch, caplog):
    runtime = _runtime(tmp_path)
    runtime._publish(True, "ready")
    calls = []

    def fail_compute(run_ref):
        calls.append(run_ref)
        raise OSError("round1 compute uncertain")

    def fail_verify():
        raise RuntimeError("round1 reconciliation unavailable")

    monkeypatch.setattr(runtime, "_execute", fail_compute)
    monkeypatch.setattr(runtime, "_verify", fail_verify)
    runtime._run_one("b" * 48)
    _assert_disabled(runtime)
    assert runtime._stop.is_set() and calls == ["b" * 48]
    assert "b" * 48 in caplog.text
    assert "compute uncertain" in caplog.text and "reconciliation unavailable" in caplog.text
    assert not (tmp_path / "absent.db").exists()


@pytest.mark.parametrize("environment,frozen,debug", [
    ("", False, True), ("", True, False), ("development", True, True),
    ("production", False, False), (" PRODUCTION ", False, False),
    ("unknown", True, True), ("default", True, True),
])
def test_prelock_debug_and_factory_use_the_same_config_source(monkeypatch, environment, frozen, debug):
    monkeypatch.setenv("APS_ENV", environment)
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    assert entrypoint.resolve_startup_debug_flag is factory.resolve_startup_debug_flag
    selected = factory._resolve_config_class()
    assert selected in factory._config_map.values()
    assert bool(selected.DEBUG) is debug
    assert entrypoint.resolve_startup_debug_flag() is debug


def test_config_selector_cold_import_has_no_concrete_config_or_application_side_effects():
    script = """
import sys
from web.bootstrap.startup_config import resolve_config_class
assert 'config' not in sys.modules and 'web.bootstrap.factory' not in sys.modules
assert not any(name.startswith('core.infrastructure.database') for name in sys.modules)
choice = type('ChosenConfig', (), {'DEBUG': False})
assert resolve_config_class({'default': choice, 'production': choice}) is choice
"""
    completed = subprocess.run([sys.executable, "-B", "-c", script],
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
