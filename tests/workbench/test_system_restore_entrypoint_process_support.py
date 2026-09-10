"""Owned subprocess driver: real entrypoint/factory/server/locks and atexit."""

import json
import os
import sqlite3
import sys
import time
from dataclasses import replace
from pathlib import Path
from urllib.parse import unquote, urlparse


def main():
    root, mode = Path(sys.argv[1]).resolve(), sys.argv[2]
    original_connect = sqlite3.connect

    def connect(path, *args, **kwargs):
        if mode == "no-database":
            raise AssertionError("Recovery startup opened SQLite")
        raw = os.fspath(path)
        if raw != ":memory:":
            actual = unquote(urlparse(raw).path) if raw.startswith("file:") else raw
            Path(actual).resolve().relative_to(root)
        return original_connect(path, *args, **kwargs)

    sqlite3.connect = connect
    from web.bootstrap import entrypoint, factory
    if mode == "no-database":
        def forbidden(*args, **kwargs):
            raise AssertionError("Recovery startup entered normal initialization")
        for name in ("ensure_schema", "bootstrap_plugins", "_init_excel_templates", "_register_exit_backup"):
            setattr(factory, name, forbidden)
        import web.bootstrap.workbench_run_runtime as run_runtime
        run_runtime.install_workbench_run_runtime = forbidden
    if mode in ("crash-verifying", "verify-failure", "rollback-failure", "pause-worker", "pause-backup"):
        install_fault(root, mode)

    make_server = factory.make_server

    def make(*args, **kwargs):
        server = make_server(*args, **kwargs)
        transport = args[2]
        app = transport.app
        runtime = app.extensions.get("workbench_run_runtime")
        host = app.extensions.get("workbench_system_restore_host")
        if mode == "pause-worker":
            start_worker(root, app, runtime)
        data = {"port": server.server_port, "pid": os.getpid(),
                "runtime_ready": bool(runtime and runtime.ready),
                "host": host.status if host is not None else None,
                "guard_is_controller": host is not None and app.extensions.get("workbench_system_restore_guard") is host,
                "run_enabled": app.config.get("WORKBENCH_RUN_JOBS_ENABLED", False),
                "candidate_enabled": app.config.get("WORKBENCH_CANDIDATE_ADOPTION_ENABLED", False),
                "calibration_enabled": app.config.get("WORKBENCH_CALIBRATION_ADOPTION_ENABLED", False)}
        temporary = root / "ready.tmp"
        temporary.write_text(json.dumps(data), encoding="utf-8")
        temporary.replace(root / "ready.json")
        return server

    factory.make_server = make
    deps = replace(entrypoint._default_deps("default"), create_app=lambda: create_app(root, mode),
                   pick_port=lambda host, port, **kwargs: (host, int(os.environ["APS_PORT"])))
    if mode == "pending-after-runtime":
        installer = deps.install_run_runtime
        def install(app, **kwargs):
            assert installer is not None
            runtime = installer(app, **kwargs)
            assert runtime.ready
            from core.services.workbench.system_journal import SystemMaintenanceJournal, file_fingerprint
            from tests.workbench.test_system_restore_entrypoint_support import KEY
            journal = SystemMaintenanceJournal(app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"], app.config["DATABASE_PATH"])
            (root / "before-maintenance.sha256").write_text(file_fingerprint(app.config["DATABASE_PATH"]), encoding="ascii")
            journal.begin(KEY, "restore", {})
            def forbidden(*args, **kwargs):
                raise AssertionError("Pending journal after runtime install must forbid further DB opens")
            sqlite3.connect = forbidden
            return runtime
        deps = replace(deps, install_run_runtime=install)
    return entrypoint.app_main(anchor_file=str(root / "app.py"), argv=[], deps=deps)


def install_fault(root, mode):
    from core.infrastructure.backup import BackupManager
    from core.services.workbench.system_journal import SystemMaintenanceJournal

    if mode == "pause-backup":
        backup = BackupManager.backup
        def paused_backup(self, suffix=None):
            if suffix and suffix.startswith("manual_"):
                (root / "backup-entered").touch()
                deadline = time.monotonic() + 20
                while not (root / "backup-release").exists():
                    if time.monotonic() >= deadline:
                        raise RuntimeError("DP test backup was not released")
                    time.sleep(0.02)
            return backup(self, suffix)
        BackupManager.backup = paused_backup
    if mode == "crash-verifying":
        original = SystemMaintenanceJournal.record
        def record(self, row, state, **values):
            result = original(self, row, state, **values)
            if state == "verifying":
                os._exit(86)
            return result
        SystemMaintenanceJournal.record = record
    if mode in ("verify-failure", "rollback-failure"):
        from web.routes.workbench import system_actions
        def verify(*args, **kwargs):
            raise RuntimeError("DP injected post-copy verification failure")
        system_actions.ensure_schema = verify
    if mode == "rollback-failure":
        copy = BackupManager._copy_db_file
        def copy_failure(self, source_path, *, locked_warning_message):
            if "before_restore" in source_path:
                raise OSError("DP injected rollback copy failure")
            return copy(self, source_path, locked_warning_message=locked_warning_message)
        BackupManager._copy_db_file = copy_failure
    if mode == "pause-worker":
        from core.services.workbench import run_worker
        compute = run_worker.compute_prepared_candidate_run
        def paused(*args, **kwargs):
            (root / "worker-entered").touch()
            deadline = time.monotonic() + 25
            while not (root / "worker-release").exists():
                if time.monotonic() >= deadline:
                    raise RuntimeError("DP test worker was not released")
                time.sleep(0.02)
            result = compute(*args, **kwargs)
            (root / "worker-computed").touch()
            return result
        run_worker.compute_prepared_candidate_run = paused


def start_worker(root, app, runtime):
    from types import SimpleNamespace

    from tests.workbench.test_system_restore_host_support import seed_worker
    case = SimpleNamespace(path=app.config["DATABASE_PATH"], app=app)
    accepted = seed_worker(case)
    (root / "worker.json").write_text(json.dumps(accepted), encoding="utf-8")
    runtime(accepted["run_ref"])
    shutdown = runtime.shutdown
    def stop(*args, **kwargs):
        (root / "worker-stopping").touch()
        return shutdown(*args, **kwargs)
    runtime.shutdown = stop


def create_app(root, mode):
    from web.bootstrap import entrypoint

    app = entrypoint.create_app_with_mode("default")
    if mode == "pause-worker":
        from flask import Response, g, stream_with_context
        @app.get("/api/workbench/v1/dp-held-response")
        def held_response():
            def stream():
                try:
                    g.db.execute("SELECT COUNT(*) FROM SystemConfig").fetchone()
                    yield b"first\n"
                    (root / "http-entered").touch()
                    deadline = time.monotonic() + 25
                    while not (root / "http-release").exists():
                        if time.monotonic() >= deadline:
                            raise RuntimeError("DP test HTTP response was not released")
                        time.sleep(0.02)
                    yield b"last\n"
                finally:
                    (root / "http-finalized").touch()
            return Response(stream_with_context(stream()), content_type="text/plain")
    return app


if __name__ == "__main__":
    sys.exit(main())
