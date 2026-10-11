"""Build a new production database using the existing workbench write contracts."""

import logging
import os
import sqlite3
import tempfile
import threading
import time
from contextlib import closing, contextmanager
from pathlib import Path

from .blueprint import demo_blueprint


@contextmanager
def serve_database(database, workspace, with_worker=False):
    """Own one local app, its request drain, and optionally its normal worker."""
    workspace = Path(workspace).resolve()
    database = Path(database).resolve()
    overrides = {"APS_ENV": "production", "APS_DB_PATH": str(database), "APS_LOG_DIR": str(workspace / "logs"),
                 "APS_BACKUP_DIR": str(workspace / "backups"), "APS_EXCEL_TEMPLATE_DIR": str(workspace / "templates")}
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    from web.bootstrap.factory import create_app_core
    from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
    from web.bootstrap.runtime_server import create_runtime_server
    from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime

    runtime, server, thread, lock = None, None, None, None
    app = None
    scope = str(workspace / "launcher")
    try:
        app = create_app_core(ui_mode="default", enable_secret_key=True, enable_security_headers=True,
                              enable_session_cookie_hardening=True)
        if with_worker:
            lock = acquire_runtime_lock(scope, db_path=str(database))
            runtime = install_workbench_run_runtime(app, runtime_lock=lock)
        logging.getLogger("werkzeug").setLevel(logging.WARNING)
        server = create_runtime_server(app, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, name="workbench-data-builder")
        thread.start()
        yield "http://127.0.0.1:" + str(server.server_port), app
    finally:
        if server is not None:
            server.shutdown()
            if thread is not None:
                thread.join()
            server.server_close()
        if runtime is not None and not runtime.shutdown(timeout=30):
            raise RuntimeError("排产后台尚未停止，数据库保留在构建目录。")
        if app is not None and not app.extensions["workbench_request_lifecycle"].shutdown(timeout=15):
            raise RuntimeError("业务请求尚未结束，数据库保留在构建目录。")
        if lock is not None:
            release_runtime_lock(scope, db_path=str(database))
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _configure(database, values):
    from core.infrastructure.database import get_connection
    from core.services.scheduler.config.config_service import ConfigService

    conn = get_connection(str(database))
    try:
        ConfigService(conn).save_page_config(values)
    finally:
        conn.close()


def _pending_counts(database):
    with closing(sqlite3.connect(str(database))) as conn:
        counts = {name: conn.execute("SELECT count(*) FROM " + name).fetchone()[0]
                  for name in ("Parts", "Batches", "BatchOperations", "Machines", "Operators", "BatchMaterials",
                               "Schedule", "WorkbenchRunJobs", "WorkbenchRunCandidates", "WorkbenchProductionReports",
                               "OperationExecutionEvents", "WorkbenchTrialDrafts", "WorkbenchTrialScenarios")}
        invalid_statuses = sum(conn.execute("SELECT count(*) FROM " + table + " WHERE status <> 'pending'").fetchone()[0]
                               for table in ("Batches", "BatchOperations"))
        active_rows = sum(counts[name] for name in ("Schedule", "WorkbenchRunJobs", "WorkbenchRunCandidates",
                         "WorkbenchProductionReports", "OperationExecutionEvents", "WorkbenchTrialDrafts", "WorkbenchTrialScenarios"))
        if invalid_statuses or active_rows:
            raise RuntimeError("构建库已包含排产或执行事实，不能作为首次排产数据交付。")
        return counts


def build_database(output, start_date=None):
    """Never touch an existing output; the delivered file has no scheduling history."""
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("目标数据库已存在，没有覆盖：" + str(output))
    workspace = Path(tempfile.mkdtemp(prefix="aps-wufenchang-build-"))
    database = workspace / "db" / "aps.db"
    blueprint = demo_blueprint(start_date)
    started = time.monotonic()
    from web.bootstrap.sample_http import BASE, SampleClient, SampleProgress
    from web.bootstrap.sample_injection import SampleInjector

    print("构建目录：" + str(workspace), flush=True)
    with serve_database(database, workspace) as (base_url, _app):
        client = SampleClient(base_url, request_prefix="import-")
        progress = SampleProgress(None, client)
        result = SampleInjector(client, progress, blueprint).inject()
        _configure(database, blueprint["config_patch"])
        preferences = dict(blueprint["schedule_window"], batch_refs=sorted(result["refs"]["batch"].values()))
        context = client.get(BASE + "/scheduling/preferences")["write_context"]
        client.command(BASE + "/scheduling/preferences", context, preferences)
    counts = _pending_counts(database)
    output.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(database))) as source, closing(sqlite3.connect(str(output))) as target:
        source.backup(target)
    return {"database": str(output), "counts": counts, "schedule_window": blueprint["schedule_window"],
            "config": blueprint["config_patch"], "source_adoptions": blueprint["source_adoptions"],
            "request_count": client.request_count, "elapsed_seconds": round(time.monotonic() - started, 3)}
