"""启动入口与工作台首页冒烟测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests._support.workbench_web_contract import canonical_boot, retired_response


def test_app_new_ui_create_app_smoke(db_env, monkeypatch) -> None:
    import importlib
    import sys

    monkeypatch.setenv("SECRET_KEY", "aps-smoke-app-new-ui-key")
    monkeypatch.delitem(sys.modules, "app_new_ui", raising=False)
    mod = importlib.import_module("app_new_ui")

    app = mod.create_app()
    if app is None:
        raise RuntimeError("app_new_ui.create_app() 返回 None")
    if not hasattr(mod, "app"):
        raise RuntimeError("app_new_ui 未导出模块级 app")
    if mod.app is None:
        raise RuntimeError("app_new_ui 模块级 app 为 None")

    client = app.test_client()
    boot = canonical_boot(client, "/", "dashboard", {})
    assert "dashboard" in boot["enabled_views"]

    r2 = client.get("/excel-demo/")
    retired_response(r2)


@pytest.mark.parametrize(("configured", "expected"), [(None, 43200), (0, 0)])
def test_static_cache_age_defaults_only_when_not_configured(db_env, monkeypatch, configured, expected) -> None:
    from web.bootstrap import app_config
    from web.bootstrap.entrypoint import create_app_with_mode

    monkeypatch.setenv("SECRET_KEY", "aps-static-cache-age-key")
    monkeypatch.setattr(app_config.Config, "SEND_FILE_MAX_AGE_DEFAULT", configured, raising=False)
    assert create_app_with_mode("new_ui").config["SEND_FILE_MAX_AGE_DEFAULT"] == expected


@pytest.mark.parametrize("module", ["app", "app_new_ui"])
def test_cold_start_defers_computation_and_excel_until_used(db_env, monkeypatch, tmp_path, module):
    monkeypatch.setenv("APS_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "cold-start-contract-key")
    script = """
import atexit, importlib, json, os, sqlite3, sys
from pathlib import Path
from urllib.parse import unquote, urlparse
original_connect = sqlite3.connect
root = Path(os.environ['APS_DB_PATH']).resolve().parent
def connect(database, *args, **kwargs):
    raw = os.fspath(database)
    if raw != ':memory:':
        path = unquote(urlparse(raw).path) if raw.startswith('file:') else raw
        Path(path).resolve().relative_to(root)
    return original_connect(database, *args, **kwargs)
sqlite3.connect = connect
app = importlib.import_module(sys.argv[1]).app
from web.bootstrap import factory
from web.bootstrap.entrypoint import _default_deps
from web.bootstrap.workbench_run_lifecycle import install_run_lifecycle, stop_run_runtime
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
atexit.unregister(factory._run_exit_backup)
scope = str(root / 'cold-start-lock')
payload = acquire_runtime_lock(scope, db_path=str(root / Path(os.environ['APS_DB_PATH']).name))
runtime = install_run_lifecycle(_default_deps('default'), app, {'payload': payload})
try:
    assert runtime.ready and app.extensions['workbench_system_restore_host'].status['operations_available']
    for name in ('openpyxl', 'core.services.workbench.run.worker',
                 'core.services.workbench.run.compute'):
        assert name not in sys.modules, name
    response = app.test_client().get('/api/workbench/v1/entities/batch/template', buffered=True)
    assert response.status_code == 200 and response.data.startswith(b'PK')
    response.close()
    assert 'openpyxl' in sys.modules
    from core.services.scheduler.schedule_lock import RUN_SCHEDULE_LOCK
    from core.services.workbench.run.worker import RUN_SCHEDULE_LOCK as worker_lock
    from core.services.workbench.run.worker_recovery import RUN_SCHEDULE_LOCK as recovery_lock
    from core.services.workbench.run.adoption_host import RUN_SCHEDULE_LOCK as adoption_lock
    from web.bootstrap.workbench_system_restore import RUN_SCHEDULE_LOCK as restore_lock
    assert all(lock is RUN_SCHEDULE_LOCK for lock in
               (worker_lock, recovery_lock, adoption_lock, restore_lock))
    print(json.dumps({'ready': runtime.ready, 'xlsx': response.status_code, 'shared_lock': True}))
finally:
    stop_run_runtime(runtime)
    release_runtime_lock(scope, db_path=app.config['DATABASE_PATH'], expected_payload=payload)
"""
    result = subprocess.run([sys.executable, "-c", script, module], cwd=str(Path(__file__).resolve().parents[2]),
                            env=os.environ.copy(), text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {"ready": True, "xlsx": 200, "shared_lock": True}
    log = (Path(os.environ["APS_LOG_DIR"]) / "launcher.log").read_text(encoding="utf-8")
    assert "python_entry" in log and "application_import_complete" in log and "schema_complete" in log
