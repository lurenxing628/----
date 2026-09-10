"""Dedicated disposable files; never start the normal app or inspect production data."""

import logging
import os
import sqlite3
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g

from core.infrastructure.backup import BackupManager
from core.infrastructure.database import ensure_schema
from core.services.workbench.system_journal import SystemMaintenanceJournal
from web.routes.workbench.system_routes import register_system_maintenance_routes

ROOT = Path(__file__).resolve().parents[2]
BASE = "/api/workbench/v1/system"


class SystemTestAPI:
    def __init__(self, root):
        self.root = root
        self.database = root / "test.db"
        self.backups, self.logs, self.journal_dir = [root / name for name in ("backups", "logs", "maintenance-results")]
        for directory in (self.backups, self.logs, self.journal_dir):
            directory.mkdir(exist_ok=True)
        ensure_schema(str(self.database), logging.getLogger("system-tests"), schema_path=str(ROOT / "schema.sql"))
        self.app = Flask("system-maintenance-test")
        self.app.config.update(TESTING=True, DATABASE_PATH=str(self.database), BACKUP_DIR=str(self.backups),
                               LOG_DIR=str(self.logs), BACKUP_KEEP_DAYS=7, WORKBENCH_SYSTEM_JOURNAL_DIR=str(self.journal_dir))
        bp = Blueprint("system_test", __name__)
        register_system_maintenance_routes(bp)
        self.app.register_blueprint(bp)
        @self.app.before_request
        def database():
            g.db = self.connect()
        @self.app.teardown_request
        def close(error):
            conn = g.pop("db", None)
            if conn is not None:
                conn.close()
        self.client = self.app.test_client()

    def connect(self):
        conn = sqlite3.connect(str(self.database))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def get(self, path, **query):
        return self.client.get(BASE + path, query_string=query)

    def read(self, path, **query):
        response = self.get(path, **query)
        assert response.status_code == 200, response.get_json()
        return response.get_json()

    def post(self, path, input_value, token, key="system-test-request-0001"):
        return self.client.post(BASE + path, json={"request_key": key, "write_token": token, "input": input_value})

    def backup(self):
        return BackupManager(str(self.database), str(self.backups)).backup(suffix="test")

    def selected(self):
        return self.read("/backups")["data"]["rows"][0]

    def file_action(self, action, row=None, key="system-test-request-0001"):
        if action == "create":
            token = self.read("/backups")["data"]["create_context"]["write_token"]
            data = {}
        else:
            row = row or self.selected()
            token, data = row["write_context"]["write_token"], {"backup_ref": row["backup_ref"]}
        return self.post("/backups/" + action, data, token, key)

    def journal(self):
        return SystemMaintenanceJournal(str(self.journal_dir), str(self.database))


@pytest.fixture(name="system_api")
def system_api(tmp_path, monkeypatch):
    connect = sqlite3.connect
    connections = []
    def isolated(database, *args, **kwargs):
        from urllib.parse import unquote, urlparse
        raw = os.fspath(database)
        if raw != ":memory:":
            path = unquote(urlparse(raw).path) if raw.startswith("file:") else raw
            Path(path).resolve().relative_to(tmp_path.resolve())
        connections.append(raw)
        return connect(database, *args, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", isolated)
    api = SystemTestAPI(tmp_path)
    yield api
    assert connections
