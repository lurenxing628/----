"""Minimal real APS fixture server, without test dump/hash middleware."""

import argparse
import atexit
import json
import os
import signal
import sys
import threading
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--db", required=True)
    p.add_argument("--ready", required=True)
    a = p.parse_args()
    repo = Path(a.repo).resolve()
    db = Path(a.db).resolve()
    sys.path.insert(0, str(repo))
    os.chdir(str(repo))
    for k, v in {
        "APS_DB_PATH": str(db),
        "APS_LOG_DIR": str(db.parent / "logs"),
        "APS_BACKUP_DIR": str(db.parent / "backups"),
        "APS_EXCEL_TEMPLATE_DIR": str(db.parent / "templates"),
        "APS_SHARED_DATA_ROOT": str(db.parent),
        "APS_ENV": "production",
    }.items():
        os.environ[k] = v
    from werkzeug.serving import make_server

    from web.bootstrap import factory
    from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
    from web.bootstrap.workbench_request_lifecycle import WorkbenchRequestHandler
    from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime
    from web.bootstrap.workbench_system_restore import install_workbench_system_restore_host

    scope = str(db.parent / "launcher")
    payload = acquire_runtime_lock(scope, db_path=str(db))
    app = factory.create_app_core(
        ui_mode="default", enable_secret_key=False, enable_security_headers=False, enable_session_cookie_hardening=False
    )
    assert Path(app.config["DATABASE_PATH"]).resolve() == db
    atexit.unregister(factory._run_exit_backup)
    app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"] = str(db.parent / "journal")
    runtime = install_workbench_run_runtime(app, runtime_lock=payload)
    assert runtime.ready, runtime.status
    host = install_workbench_system_restore_host(app, runtime=runtime)
    server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=WorkbenchRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    Path(a.ready).write_text(
        json.dumps(
            {"url": "http://127.0.0.1:" + str(server.server_port), "db": str(db), "repo": str(repo), "pid": os.getpid()}
        )
        + "\n"
    )
    try:
        stop.wait()
    finally:
        server.shutdown()
        thread.join(10)
        server.server_close()
        runtime.shutdown(timeout=20)
        host.gate.shutdown(timeout=20)
        release_runtime_lock(scope, db_path=str(db))


if __name__ == "__main__":
    main()
