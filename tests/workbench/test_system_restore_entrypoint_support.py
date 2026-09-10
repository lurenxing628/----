"""Only own temporary files, processes and OS-allocated temporary ports."""

import http.client
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Tuple

from core.services.workbench.system_journal import SystemMaintenanceJournal, file_fingerprint
from web.bootstrap.launcher_stop import _request_runtime_shutdown

BASE = "/api/workbench/v1/system"
KEY = "dp-entrypoint-restore-request-0001"
REPO = Path(__file__).resolve().parents[2]


def wait_for(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Owned test process did not reach expected state")


class ProcessHost:
    def __init__(self, root, mode="normal"):
        self.root, self.mode = Path(root).resolve(), mode
        self.root.mkdir(exist_ok=True)
        self.path = self.root / "aps.db"
        self.backups, self.journal_dir = self.root / "backups", self.root / "journal"
        self.backups.mkdir(exist_ok=True)
        self.journal_dir.mkdir(exist_ok=True)
        self._process = None

    @property
    def process(self):
        assert self._process is not None, "Owned process was not started"
        return self._process

    def journal(self):
        return SystemMaintenanceJournal(str(self.journal_dir), str(self.path))

    def start(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        env = dict(os.environ, APS_ENV="production", APS_HOST="127.0.0.1", APS_PORT=str(self.port),
                   APS_DB_PATH=str(self.path), APS_LOG_DIR=str(self.root / "logs"),
                   APS_BACKUP_DIR=str(self.backups), APS_SYSTEM_JOURNAL_DIR=str(self.journal_dir),
                   APS_EXCEL_TEMPLATE_DIR=str(self.root / "templates"), SECRET_KEY="dp-disposable-process-key")
        env.pop("WERKZEUG_RUN_MAIN", None)
        (self.root / "ready.json").unlink(missing_ok=True)
        self.log = open(self.root / "process.log", "w", encoding="utf-8")
        self._process = subprocess.Popen([sys.executable, "-m",
            "tests.workbench.test_system_restore_entrypoint_process_support", str(self.root), self.mode],
            cwd=str(REPO), env=env, stdout=self.log, stderr=subprocess.STDOUT)
        wait_for(lambda: (self.root / "ready.json").exists() or self.process.poll() is not None)
        assert self.process.poll() is None, (self.root / "process.log").read_text()
        self.ready = json.loads((self.root / "ready.json").read_text())
        assert self.ready["port"] == self.port and self.ready["pid"] == self.process.pid
        self.contract = json.loads((self.root / "logs" / "aps_runtime.json").read_text())
        self.lock_paths = [self.root / "logs" / "aps_runtime.lock", Path(str(self.path) + ".lock")]
        self.lock_bytes = [path.read_bytes() for path in self.lock_paths]
        return self

    def request(self, path, body=None, method="GET", token=None) -> Tuple[int, Any]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-APS-Shutdown-Token"] = token
        try:
            conn.request(method, path, body=json.dumps(body) if body is not None else b"", headers=headers)
            response = conn.getresponse()
            data = response.read()
            return response.status, json.loads(data) if data.startswith(b"{") else data
        finally:
            conn.close()

    def locked(self):
        assert [path.read_bytes() for path in self.lock_paths] == self.lock_bytes

    def stop(self):
        assert _request_runtime_shutdown(self.contract)
        assert self.process.wait(timeout=15) == 0, (self.root / "process.log").read_text()
        assert all(not path.exists() for path in self.lock_paths)

    def close(self):
        if self._process is not None:
            try:
                if self.process.poll() is None:
                    (self.root / "worker-release").touch()
                    (self.root / "http-release").touch()
                    (self.root / "backup-release").touch()
                    contract = getattr(self, "contract", None)
                    if contract:
                        _request_runtime_shutdown(contract)
                    try:
                        self.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        self.process.kill()  # Only this exact disposable Popen child.
                        self.process.wait(timeout=10)
            finally:
                self.log.close()

    def hashes(self):
        paths = [self.path] + list(self.backups.glob("*.db")) + list(self.journal_dir.glob("*.json"))
        return {str(path): file_fingerprint(str(path)) for path in paths if path.exists()}

    def restore_body(self):
        status, payload = self.request(BASE + "/backups")
        assert status == 200, payload
        row = next(row for row in payload["data"]["rows"] if row["filename"].endswith("_source.db"))
        return {"request_key": KEY, "write_token": row["write_context"]["write_token"],
                "input": {"backup_ref": row["backup_ref"]}}


def seed_database(host):
    from contextlib import closing

    from core.infrastructure.backup import BackupManager
    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(str(host.path), None, schema_path=str(REPO / "schema.sql"))
    with closing(get_connection(str(host.path))) as conn:
        conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES ('DP','selected')")
        conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES ('auto_backup_enabled','yes')")
        conn.commit()
    source = BackupManager(str(host.path), str(host.backups)).backup(suffix="source")
    with closing(get_connection(str(host.path))) as conn:
        conn.execute("UPDATE SystemConfig SET config_value='current' WHERE config_key='DP'")
        conn.commit()
    return Path(source)


def marker(path):
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        return conn.execute("SELECT config_value FROM SystemConfig WHERE config_key='DP'").fetchone()[0]
