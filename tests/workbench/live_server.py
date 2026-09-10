"""CLI: start a real isolated Flask fixture on port 0; no production data import."""

import argparse
import json
import os
import signal
import sqlite3
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from live_environment import (
    READY_PREFIX,
    REPO,
    create_root,
    environment,
    file_snapshot,
    freeze_assets,
    install_path_guard,
    read_identity,
    sha256,
    write_json,
)


def seed_fixture(app, root):
    from core.infrastructure.database import get_connection
    from core.services.system.system_config_service import SystemConfigService

    conn = get_connection(app.config["DATABASE_PATH"])
    try:
        SystemConfigService(conn).ensure_defaults(backup_keep_days_default=7)
        for key, value in {"auto_backup_enabled": "no", "auto_backup_cleanup_enabled": "no",
                           "auto_log_cleanup_enabled": "no", "auto_backup_interval_minutes": "120"}.items():
            conn.execute("UPDATE SystemConfig SET config_value = ? WHERE config_key = ?", (value, key))
        conn.execute("DELETE FROM OperationLogs")
        conn.executemany("INSERT INTO OperationLogs(log_level, module, action, detail) VALUES (?, ?, ?, ?)",
                         [("INFO", "isolated_browser_fixture", "seed", "Temporary row " + str(n)) for n in range(3)])
        conn.execute("DELETE FROM SystemJobState")
        jobs = [("auto_backup", {"filename": "aps_backup_probe_a.db", "size_mb": 0.1}),
                ("auto_backup_cleanup", {"deleted_count": 0}),
                ("auto_log_cleanup", {"deleted_count": 0})]
        conn.executemany("INSERT INTO SystemJobState(job_key, last_run_time, last_run_detail) VALUES (?, ?, ?)",
                         [(key, "2020-01-02 03:04:05", json.dumps(detail)) for key, detail in jobs])
        conn.commit()
        for name in ("aps_backup_probe_a.db", "aps_backup_probe_b.db"):
            with sqlite3.connect(str(root / "backups" / name)) as backup:
                conn.backup(backup)
    finally:
        conn.close()
    sentinel = "ISOLATED_LOG_BODY_NOT_FOR_DIAGNOSTIC_" + read_identity(root)["nonce"]
    for name in ("aps.log", "aps_error.log", "launcher.log"):
        with (root / "logs" / name).open("a", encoding="utf-8") as stream:
            stream.write("\n2020-01-02 03:04:05 [INFO] " + sentinel + "\n")
    return {"operation_record_count": 3, "backup_names": ["aps_backup_probe_a.db", "aps_backup_probe_b.db"],
            "backup_count": 2, "backup_interval_minutes": 120, "log_body_sentinel": sentinel,
            "instance_label": app.config["WORKBENCH_INSTANCE_LABEL"]}


def database_snapshot(path):
    with sqlite3.connect(str(path)) as conn:
        return sha256("\n".join(conn.iterdump()).encode("utf-8"))


def seed_navigation_plan(app):
    from core.infrastructure.database import get_connection
    from tests.workbench.plan_catalog_support import history, seed_operation

    conn = get_connection(app.config["DATABASE_PATH"])
    try:
        history(conn, 1, op_id=seed_operation(conn))
        conn.commit()
    finally:
        conn.close()


@contextmanager
def managed_app(root):
    from core.services.workbench.system_journal import assert_system_maintenance_ready
    from web.bootstrap.entrypoint import create_app_with_mode
    from web.bootstrap.launcher_paths import db_scope_lock_path
    from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
    from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime
    from web.bootstrap.workbench_system_restore import install_workbench_system_restore_host

    database = str(root / "db/aps-live.db")
    journal = root / "journal"
    journal.mkdir()
    assert_system_maintenance_ready(database, str(journal))
    payload = acquire_runtime_lock(str(root), cfg_log_dir=str(root / "logs"), db_path=database)
    runtime, gate = None, None
    try:
        app = create_app_with_mode("default")
        app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"] = str(journal)
        gate = app.extensions["workbench_request_lifecycle"]
        runtime = install_workbench_run_runtime(app, runtime_lock=payload)
        assert runtime.ready, runtime.status
        host = install_workbench_system_restore_host(app, runtime=runtime)
        assert host.status["state"] == "ready"
        yield app
    finally:
        gate_stopped = gate.shutdown(timeout=20) if gate is not None else True
        runtime_stopped = runtime.shutdown(timeout=20) if runtime is not None else True
        assert runtime_stopped and gate_stopped, "Managed browser fixture did not drain"
        release_runtime_lock(payload["state_dir"], db_path=database)
        locks_released = not Path(payload["path"]).exists() and not Path(db_scope_lock_path(database)).exists()
        assert locks_released
        sources = {name: str(Path(module.__file__).resolve()) for name, module in list(sys.modules.items())
                   if name.split(".")[0] in ("core", "web", "plugins", "data") and getattr(module, "__file__", None)}
        assert sources and all(REPO in Path(file).parents for file in sources.values())
        write_json(root / "managed-runtime.json", {"runtime_stopped": runtime_stopped, "gate_stopped": gate_stopped,
                                                    "locks_released": locks_released, "source_root": str(REPO), "sources": sources})


def serve(root):
    root = Path(root).resolve()
    identity = read_identity(root)
    if (root / "db/aps-live.db").exists():
        raise ValueError("Refusing to reuse a fixture database; start with a fresh temp root")
    assets = freeze_assets(root)
    env = environment(root)
    env["APS_ENV"] = "production"
    os.environ.clear()
    os.environ.update(env)
    tempfile.tempdir = str(root / "tmp")
    os.chdir(str(root))
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(REPO))
    evidence = install_path_guard(root)
    # Match the real runtime contract before the system UI can read host status.
    with managed_app(root) as app:
        return serve_http(app, root, identity, assets, env, evidence)


def serve_http(app, root, identity, assets, env, evidence):
    from jinja2 import ChoiceLoader, FileSystemLoader

    app.static_folder = str(root / "static")
    app.jinja_loader = ChoiceLoader([FileSystemLoader(str(root / "templates")), app.jinja_loader])
    expected_paths = {"DATABASE_PATH": root / "db/aps-live.db", "LOG_DIR": root / "logs",
                      "BACKUP_DIR": root / "backups", "EXCEL_TEMPLATE_DIR": root / "templates_excel"}
    for key, value in expected_paths.items():
        if Path(app.config[key]).resolve() != value:
            raise ValueError("Flask escaped the fixture path: " + key)
    app.config["WORKBENCH_INSTANCE_LABEL"] = "隔离浏览器实例 " + identity["nonce"][:12]
    seed_navigation_plan(app)
    expected = seed_fixture(app, root)
    before_db = database_snapshot(expected_paths["DATABASE_PATH"])
    before_files = file_snapshot(root)
    journal_lock = threading.Lock()

    @app.before_request
    def record_read_boundary():
        from flask import g, request
        if not request.path.startswith("/static/"):
            g.live_database_before = database_snapshot(expected_paths["DATABASE_PATH"])

    @app.after_request
    def record_real_request(response):
        from flask import g, request

        if not request.path.startswith("/static/"):
            unchanged = database_snapshot(expected_paths["DATABASE_PATH"]) == g.live_database_before
            assert unchanged, "Read-only browser request changed fixture database"
            row = {"method": request.method, "path": request.path, "status": response.status_code, "database_unchanged": unchanged}
            if request.path == "/api/workbench/v1/system/overview" and response.is_json:
                value = response.get_json(silent=True) or {}
                row["source"] = value.get("meta", {}).get("source")
                row["snapshot_ref"] = value.get("meta", {}).get("snapshot_ref")
            with journal_lock, (root / "server-requests.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row) + "\n")
        return response

    from werkzeug.serving import make_server

    from web.bootstrap.workbench_request_lifecycle import WorkbenchRequestHandler

    server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=WorkbenchRequestHandler)
    worker = threading.Thread(target=server.serve_forever, name="isolated-workbench-http", daemon=True)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_args: stop.set())
    signal.signal(signal.SIGINT, lambda *_args: stop.set())
    worker.start()
    ready = {"schema_version": 1, "url": "http://127.0.0.1:" + str(server.server_port),
             "root": str(root), "pid": os.getpid(), "expected": expected, "assets": assets,
             "paths": {key: str(value) for key, value in expected_paths.items()}, "tmpdir": env["TMPDIR"]}
    ready["system_url"] = ready["url"] + "/workbench?view=system"
    write_json(root / "server-ready.json", ready)
    print(READY_PREFIX + json.dumps(ready, ensure_ascii=False), flush=True)
    try:
        stop.wait()
    except KeyboardInterrupt:
        stop.set()
    finally:
        server.shutdown()
        worker.join(timeout=10)
        server.server_close()
        final = {"root": str(root), "stopped": not worker.is_alive(),
                 "database_unchanged": database_snapshot(expected_paths["DATABASE_PATH"]) == before_db,
                 "backups_and_templates_unchanged": file_snapshot(root) == before_files,
                 "sqlite_connections": sorted(set(evidence["sqlite_connections"])),
                 "isolation_violations": evidence["violations"]}
        write_json(root / "server-final.json", final)
        print("WB_LIVE_STOPPED " + json.dumps(final), flush=True)
    return 0 if final["stopped"] and final["database_unchanged"] and final["backups_and_templates_unchanged"] and not final["isolation_violations"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Fresh root created by live_environment.create_root")
    parser.add_argument("--temp-parent", type=Path, help="Parent directory for a new unique temp root")
    args = parser.parse_args()
    root = args.root if args.root is not None else create_root(args.temp_parent)
    print("WB_LIVE_TEMP " + str(root), flush=True)
    return serve(root)


if __name__ == "__main__":
    sys.exit(main())
