"""Real full Flask app integration plus terminal catalog and snapshot boundaries."""

import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

from flask import Blueprint

from tests._support.excel_templates import point_env_at_shared
from tests.workbench.run_candidate_support import BASE, compute, read, state
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from web.routes.workbench.run_candidates import register_run_candidate_routes


def test_full_app_explicit_registration_only_temporary_connections(candidate_case, tmp_path, monkeypatch):
    case = candidate_case
    run_ref, refs = compute(case)
    for key, path in (("APS_DB_PATH", case.path), ("APS_LOG_DIR", tmp_path / "logs"), ("APS_BACKUP_DIR", tmp_path / "backups")):
        monkeypatch.setenv(key, str(path))
    monkeypatch.setenv("APS_ENV", "development")
    point_env_at_shared(monkeypatch)
    original = sqlite3.connect
    connections = []

    def guarded(path, *args, **kwargs):
        value = url2pathname(urlsplit(str(path)).path) if str(path).startswith("file:") else str(path)
        assert value == ":memory:" or Path(value).resolve() == case.path.resolve(), "Unexpected nonfixture SQLite path"
        connections.append(value)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded)
    from web.bootstrap.entrypoint import create_app_with_mode
    app = create_app_with_mode("default")
    bp = Blueprint("bl_full_app_candidates", __name__)
    register_run_candidate_routes(bp)
    app.register_blueprint(bp)
    client = app.test_client()
    before = state(case.conn)
    catalog = read(client, "/runs/" + run_ref + "/candidates")
    assert catalog["data"]["candidate_count"] == 4
    result = read(client, "/candidates/" + refs[0])
    token = result["meta"]["snapshot_ref"]
    for fmt in ("csv", "xlsx"):
        response = client.get(BASE + "/candidates/" + refs[0] + "/export", query_string={"format": fmt, "snapshot_ref": token})
        assert response.status_code == 200 and response.headers["X-Workbench-Task-Count"] == "1"
    assert state(case.conn) == before
    assert connections and str(case.path) in connections
    assert client.post(BASE + "/candidates/" + refs[0]).status_code == 405
