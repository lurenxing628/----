"""Real engine artifacts, complete Flask factory and a separate-process restart."""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from flask import Blueprint

from core.models.workbench_run_history import RunHistoryScope
from core.services.workbench.run_history import WorkbenchRunHistoryQueryService
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests._support.excel_templates import point_env_at_shared
from tests.workbench.run_history_support import BASE, dump, read, seed
from tests.workbench.run_history_support import history_case as _history_case
from web.routes.workbench.run_candidates import register_run_candidate_routes
from web.routes.workbench.run_history import register_run_history_routes


def test_full_flask_app_actual_engine_run_and_only_temporary_sqlite(history_case, tmp_path, monkeypatch):
    case = history_case
    accepted = case.accept()
    worker_result = WorkbenchRunWorker(case.conn, clock=lambda: datetime(2026, 9, 10, 12, 1)).execute(accepted["run_ref"])
    assert len(worker_result["candidates"]) == 4
    for key, path in (("APS_DB_PATH", case.path), ("APS_LOG_DIR", tmp_path / "logs"), ("APS_BACKUP_DIR", tmp_path / "backups")):
        monkeypatch.setenv(key, str(path))
    monkeypatch.setenv("APS_ENV", "development")
    point_env_at_shared(monkeypatch)
    original, paths = sqlite3.connect, []

    def guard(path, *args, **kwargs):
        value = unquote(urlsplit(str(path)).path) if str(path).startswith("file:") else str(path)
        assert value == ":memory:" or Path(value).resolve() == case.path.resolve(), "Nonfixture SQLite access"
        paths.append(value)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guard)
    from web.bootstrap.entrypoint import create_app_with_mode
    app = create_app_with_mode("default")
    if not any(rule.rule == BASE and "GET" in rule.methods for rule in app.url_map.iter_rules()):
        bp = Blueprint("bq_full_app_history", __name__)
        register_run_history_routes(bp)
        app.register_blueprint(bp)
    if not any(rule.rule == BASE + "/<run_ref>/candidates" for rule in app.url_map.iter_rules()):
        candidates_bp = Blueprint("bq_full_app_candidates", __name__)
        register_run_candidate_routes(candidates_bp)
        app.register_blueprint(candidates_bp)
    client = app.test_client()
    from core.infrastructure import workbench_run_schema
    from core.services.workbench.run_jobs import WorkbenchRunService

    def forbidden(*args, **kwargs):
        raise AssertionError("History GET must not install, recover or dispatch")

    monkeypatch.setattr(workbench_run_schema, "install_workbench_run_schema", forbidden)
    monkeypatch.setattr(WorkbenchRunService, "recover_unfinished_runs", forbidden)
    monkeypatch.setattr(WorkbenchRunWorker, "execute", forbidden)
    before = dump(case.conn)
    data = read(client)["data"]
    row = data["runs"][0]
    assert row["run_ref"] == accepted["run_ref"] and row["candidate_count"] == row["task_count"] == 4
    assert row["scope_summary"]["start_date"] == "2026-09-09"
    assert row["constraint_verification"] == "not_checked_by_history"
    reopened_client = app.test_client()
    restored = read(reopened_client)["data"]["runs"][0]
    catalog = reopened_client.get(BASE + "/" + restored["run_ref"] + "/candidates")
    assert catalog.status_code == 200
    candidate_ref = catalog.get_json()["data"]["candidates"][0]["candidate_ref"]
    workspace = reopened_client.get("/api/workbench/v1/scheduling/candidates/" + candidate_ref + "/workspace")
    assert workspace.status_code == 200
    assert workspace.get_json()["data"]["candidate"]["run_ref"] == accepted["run_ref"]
    assert workspace.get_json()["data"]["task_count"] == 1
    rules = [rule for rule in app.url_map.iter_rules() if rule.rule == BASE]
    assert any("GET" in rule.methods for rule in rules)
    # The full app may still be awaiting the parent's explicit AV registration.
    assert not app.config.get("WORKBENCH_RUN_JOBS_ENABLED")
    assert dump(case.conn) == before and paths and str(case.path) in paths


def test_get_registration_coexists_with_existing_post_and_no_worker_required(history_case):
    from tests.workbench.run_history_support import api
    from web.routes.workbench.scheduling_jobs import register_scheduling_job_routes

    case = history_case
    bp = Blueprint("bq_existing_post", __name__)
    register_scheduling_job_routes(bp)
    case.app.register_blueprint(bp)
    seed(case, "failed")
    client, _ = api(case)
    assert read(client)["data"]["runs"][0]["state"] == "failed"
    assert client.post(BASE, json={}).status_code == 400
    assert client.delete(BASE).status_code == 405


def test_new_process_reopens_history_without_browser_token_cache(history_case):
    case = history_case
    refs = [seed(case, state) for state in ("complete", "partial", "failed", "interrupted")]
    expected, fingerprint = WorkbenchRunHistoryQueryService(case.conn).catalog(RunHistoryScope())
    before = dump(case.conn)
    code = '''import json, sqlite3, sys
from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, current_schema_contract_issues
from core.models.workbench_run_history import RunHistoryScope
from core.services.workbench.run_history import WorkbenchRunHistoryQueryService
conn = sqlite3.connect(sys.argv[1])
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys=ON")
assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == CURRENT_SCHEMA_VERSION
assert current_schema_contract_issues(conn) == []
conn.execute("PRAGMA query_only=ON")
data, fingerprint = WorkbenchRunHistoryQueryService(conn).catalog(RunHistoryScope())
print(json.dumps({"data": data, "fingerprint": fingerprint}))
conn.close()
'''
    completed = subprocess.run([sys.executable, "-c", code, str(case.path)], cwd=str(Path(__file__).resolve().parents[2]),
                               env=dict(os.environ), check=True, capture_output=True, text=True, timeout=30)
    actual = json.loads(completed.stdout)
    assert actual["data"] == expected and actual["fingerprint"] == fingerprint
    assert {row["run_ref"] for row in actual["data"]["runs"]} == set(refs)
    assert dump(case.conn) == before
