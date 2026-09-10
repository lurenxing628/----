"""Current-schema /workbench server. Stop with Ctrl-C, SIGTERM or ready.stop_file."""

import argparse
import atexit
import json
import os
import signal
import sys
import threading
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench.run_live_server_support import (
    BASE,
    FORBIDDEN_PORTS,
    attach_journal,
    database_state,
    freeze_built_assets,
    inside,
    isolate,
    loaded_python_sources,
    prepare_root,
    protect_frozen_assets,
    seed_run_data,
    source_comparison,
    tree_hashes,
    write_json,
    write_manifest,
)


class LiveRunServer:
    def __init__(self, root, identity, reuse, profile="mixed"):
        self.root, self.identity, self.reuse = root, identity, reuse
        if profile not in ("mixed", "first-plan", "calibration", "outsourcing"):
            raise ValueError("Unknown fixture profile")
        self.profile = profile
        self.session = uuid.uuid4().hex
        self.directory = root / "sessions" / self.session
        self.directory.mkdir(parents=True)
        self.db = root / "db/aps-live.db"
        self.lock = self.runtime = self.app = self.server = self.worker = self.restore_host = None
        self.events = []
        self.before = tree_hashes(root)
        self.evidence = isolate(root)
        self.assets = None
        self.sources = {}
        self.final = None

    def start(self, port=0):
        from jinja2 import FileSystemLoader
        from werkzeug.serving import make_server

        from web.bootstrap import factory
        from web.bootstrap.entrypoint import create_app_with_mode
        from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock
        from web.bootstrap.workbench_request_lifecycle import WorkbenchRequestHandler
        from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime
        from web.bootstrap.workbench_system_restore import install_workbench_system_restore_host

        if port in FORBIDDEN_PORTS:
            raise ValueError("Reserved port must not be used")
        self.lock = acquire_runtime_lock(str(self.root), str(self.root / "logs"), db_path=str(self.db))
        self.events.append("launcher_locks_acquired")
        self.assets = freeze_built_assets(self.root, self.session)
        protect_frozen_assets(self.assets)
        self.app = create_app_with_mode("default")
        # Own the exit sequence explicitly; never run factory's callback after unlock.
        atexit.unregister(factory._run_exit_backup)
        if self.app.extensions.get("workbench_system_restore_recovery"):
            raise RuntimeError("Fixture startup requires maintenance recovery; database access and seeding refused")
        self.events.append("factory_schema_ready")
        paths = {"DATABASE_PATH": self.db, "LOG_DIR": self.root / "logs",
                 "BACKUP_DIR": self.root / "backups", "EXCEL_TEMPLATE_DIR": self.root / "templates_excel"}
        for key, path in paths.items():
            if inside(self.root, self.app.config[key]) != path:
                raise ValueError("Unexpected configured path: " + key)
        if self.app.debug or self.app.testing:
            raise ValueError("Fixture must use real production configuration")
        self.app.static_folder = self.assets["static"]
        self.app.jinja_loader = FileSystemLoader(self.assets["templates"])
        self.app.config["WORKBENCH_INSTANCE_LABEL"] = "Isolated run fixture " + self.identity["nonce"][:12]
        seed_path = self.root / "run-seed.json"
        if not self.reuse:
            write_json(seed_path, {**seed_run_data(self.app, include_formal=self.profile in ("mixed", "outsourcing"),
                                                  calibration=self.profile == "calibration",
                                                  outsourcing=self.profile == "outsourcing"),
                                   "fixture_profile": self.profile})
        expected = json.loads(seed_path.read_text(encoding="utf-8"))
        if expected.get("fixture_profile") != self.profile:
            raise ValueError("Explicit reuse must retain the original fixture profile")
        self.runtime = install_workbench_run_runtime(self.app, runtime_lock=self.lock)
        if not self.runtime.ready:
            raise RuntimeError("Real runtime is not ready: " + str(self.runtime.status))
        self.runtime.proof.verify()
        self.restore_host = install_workbench_system_restore_host(self.app, runtime=self.runtime)
        self.events.append("real_runtime_ready")
        before = database_state(self.db)
        write_json(self.directory / "business-before.json", before)
        write_json(self.root / "business-before.json", before)
        self.sources = loaded_python_sources()
        attach_journal(self.app, self.directory / "server-requests.jsonl")
        # HTTP requests finish before shutdown proceeds; computations use the real worker.
        self.server = make_server("127.0.0.1", port, self.app, threaded=False, request_handler=WorkbenchRequestHandler)
        if self.server.server_port in FORBIDDEN_PORTS:
            raise ValueError("OS allocated a reserved port; restart on another free port")
        self.worker = threading.Thread(target=self.server.serve_forever, name="run-fixture-http", daemon=True)
        self.worker.start()
        url = "http://127.0.0.1:" + str(self.server.server_port)
        self.ready = {"schema_version": 1, "schema_database_version": before["SchemaVersion"][0]["version"],
                      "url": url, "workbench_url": url + "/workbench", "run_url": url + "/workbench?view=run",
                      "root": str(self.root), "pid": os.getpid(), "session": self.session,
                      "ready_file": str(self.root / "server-ready.json"),
                      "stop_file": str(self.directory / "stop.request"),
                      "journal": str(self.directory / "server-requests.jsonl"),
                      "paths": {key: str(path) for key, path in paths.items()},
                      "runtime": self.runtime.status, "runtime_lock": self.lock, "loaded_python_sources": self.sources,
                      "db_lock": self.runtime.proof.db_lock_path, "expected": expected, "assets": self.assets,
                      "api": {"preflight": BASE + "/preflight", "preview": BASE + "/runs/preview",
                              "runs": BASE + "/runs", "requests": BASE + "/requests",
                              "plans": "/api/workbench/v1/plans", "analytics": "/api/workbench/v1/analytics"}}
        write_json(self.directory / "server-ready.json", self.ready)
        write_json(self.root / "server-ready.json", self.ready)
        print("WB_RUN_READY " + json.dumps(self.ready), flush=True)
        return self.ready

    def close(self):
        from core.infrastructure.backup import BackupManager
        from web.bootstrap import factory
        from web.bootstrap.launcher_runtime_lock import release_runtime_lock
        from web.bootstrap.workbench_run_lifecycle import stop_run_runtime
        from web.bootstrap.workbench_system_restore_recovery import assert_exit_system_restore_ready

        if self.final is not None:
            return self.final
        atexit.unregister(factory._run_exit_backup)
        if self.server is not None:
            if self.worker is not None and self.worker.is_alive():
                self.server.shutdown()
                self.worker.join()
            self.server.server_close()
        self.events.append("http_stopped")
        stop_run_runtime(self.runtime)
        self.events.append("runtime_shutdown_joined")
        backup = None
        recovery = self.app is not None and bool(self.app.extensions.get("workbench_system_restore_recovery") or
                    self.restore_host is not None and self.restore_host.status["restart_required"])
        if self.lock is not None and self.app is not None:
            if self.runtime is not None and self.runtime.proof is not None:
                self.runtime.proof.verify()
            manager = BackupManager(str(self.db), str(self.root / "backups"), logger=self.app.logger)
            manager._system_restore_app = self.app
            if not recovery:
                try:
                    assert_exit_system_restore_ready(manager)
                except Exception:
                    recovery = True
                    self.app.logger.exception("Fixture exit backup refused: maintenance must be verified")
            if recovery:
                self.events.append("exit_backup_skipped_restore_requires_restart")
            else:
                backup = manager.backup(suffix="run_fixture_exit_" + self.session)
                self.events.append("exit_backup_complete_under_lock")
                after = database_state(self.db)
                write_json(self.directory / "business-after.json", after)
                write_json(self.root / "business-after.json", after)
        if self.lock is not None:
            release_runtime_lock(self.lock["state_dir"], os.getpid(), str(self.db))
            if Path(self.lock["path"]).exists() or Path(str(self.db) + ".lock").exists():
                raise RuntimeError("Launcher locks were not released")
            self.events.append("launcher_locks_released")
        unchanged = self.assets is None or tree_hashes(Path(self.assets["root"])) == self.assets["hashes"]
        self.final = {"root": str(self.root), "session": self.session, "pid": os.getpid(), "stopped": True,
                      "events": self.events, "runtime": self.runtime.status if self.runtime else None,
                      "exit_backup": backup, "recovery_required": recovery,
                      "assets_unchanged": unchanged, "files_retained": self.db.exists(),
                      "sqlite_connections": sorted(set(self.evidence["sqlite_connections"])),
                      "isolation_violations": self.evidence["violations"],
                      "python_sources": source_comparison(self.sources, loaded_python_sources())}
        write_json(self.directory / "server-final.json", self.final)
        if self.lock is not None:
            write_json(self.root / "server-final.json", self.final)
            write_manifest(self.root, self.before, self.session)
        print("WB_RUN_STOPPED " + json.dumps(self.final), flush=True)
        return self.final


def serve(root, identity, *, reuse=False, port=0, profile="mixed"):
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_args: stop.set())
    fixture = LiveRunServer(root, identity, reuse, profile=profile)
    try:
        ready = fixture.start(port)
        while not stop.wait(.2):
            if Path(ready["stop_file"]).exists():
                break
    finally:
        final = fixture.close()
    return 0 if final["assets_unchanged"] and not final["isolation_violations"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Root created by live_environment.create_root")
    parser.add_argument("--temp-parent", type=Path, help="Parent for a new unique persistent temporary root")
    parser.add_argument("--reuse-root", action="store_true", help="Explicitly reuse this fixture's own database")
    parser.add_argument("--port", type=int, default=0, help="Loopback only; 0 chooses an unused port")
    parser.add_argument("--profile", choices=("mixed", "first-plan", "calibration", "outsourcing"), default="mixed")
    args = parser.parse_args()
    root, identity = prepare_root(args.root, parent=args.temp_parent, reuse=args.reuse_root)
    print("WB_RUN_TEMP " + str(root), flush=True)
    return serve(root, identity, reuse=args.reuse_root, port=args.port, profile=args.profile)


if __name__ == "__main__":
    sys.exit(main())
