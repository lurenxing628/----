"""Owned subprocess with real HTTP shutdown, an in-flight write and runtime locks."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

from web.bootstrap.launcher_contracts import (
    acquire_runtime_lock,
    release_runtime_lock,
    write_runtime_contract_file,
    write_runtime_host_port_files,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TOKEN = "isolated-cg-draining-token"


def wait_for_file(path: Path, process: subprocess.Popen, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not path.exists():
        assert process.poll() is None, f"Owned runtime exited before {path.name}"
        assert time.monotonic() < deadline, f"Timed out waiting for {path.name}"
        time.sleep(0.025)


def isolated_env(root: Path):
    env = {key: value for key, value in os.environ.items() if not key.startswith("APS_")}
    env.update({
        "APS_DB_PATH": str(root / "work.sqlite"),
        "APS_SHARED_DATA_ROOT": str(root),
        "APS_LOG_DIR": str(root / "logs"),
        "APS_BACKUP_DIR": str(root / "backups"),
        "APS_EXCEL_TEMPLATE_DIR": str(root / "templates"),
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    })
    return env


def subprocess_command(mode: str, root: Path, *extra: str):
    return [sys.executable, "-m", "tests.app_runtime.runtime_stop_draining_support", mode, str(root)] + list(extra)


@contextmanager
def running_runtime(root: Path, mode: str = "accepted") -> Iterator[subprocess.Popen]:
    with (root / "child.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            subprocess_command("serve", root, mode), cwd=str(REPO_ROOT), env=isolated_env(root),
            stdout=log, stderr=subprocess.STDOUT,
        )
        # Reap the owned child even while the parent is inside the stop poll loop.
        reaper = threading.Thread(target=process.wait)
        reaper.start()
        try:
            wait_for_file(root / "ready", process)
            yield process
        finally:
            (root / "release").touch()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()  # Only this fixture's Popen child, never a discovered PID.
                process.wait(timeout=5)
            reaper.join(timeout=5)
            assert not reaper.is_alive()


@contextmanager
def pending_http_write(root: Path, process: subprocess.Popen):
    contract = json.loads((root / "logs" / "aps_runtime.json").read_text(encoding="utf-8"))
    result = []

    def request_work():
        req = urllib.request.Request(
            "http://127.0.0.1:{}/work".format(contract["port"]), data=b"", method="POST",
        )
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=45) as response:
                result.append(response.status)
        except Exception as exc:
            result.append(exc)

    thread = threading.Thread(target=request_work)
    thread.start()
    try:
        wait_for_file(root / "work-started", process)
        yield result
    finally:
        (root / "release").touch()
        thread.join(timeout=10)
        assert not thread.is_alive()


def _wait_for_release(root: Path) -> None:
    deadline = time.monotonic() + 40.0
    while not (root / "release").exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("Test controller did not release the owned runtime")
        time.sleep(0.025)


def _handler_type(root: Path, mode: str, shutdown: threading.Event):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _reply(self, status: int, payload: bytes = b"{}") -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                if mode != "unresponsive":
                    raise

        def do_GET(self):
            self._reply(200, b'{"app":"aps","status":"ok","contract_version":1}')

        def do_POST(self):
            if self.path == "/work":
                with sqlite3.connect(str(root / "work.sqlite")) as conn:
                    conn.execute("INSERT INTO work VALUES (1, 'committed after drain')")
                    (root / "work-started").touch()
                    _wait_for_release(root)
                    conn.commit()
                (root / "committed").touch()
                self._reply(200)
                return
            if self.path != "/system/runtime/shutdown":
                self._reply(404)
                return
            (root / "shutdown-seen").touch()
            if self.headers.get("X-APS-Shutdown-Token") != TOKEN or mode == "rejected":
                self._reply(403)
                return
            (root / "accepted").touch()
            if mode == "unresponsive":
                _wait_for_release(root)
            self._reply(202)
            shutdown.set()

    return Handler


def serve_runtime(root: Path, mode: str) -> int:
    state_dir = root / "logs"
    db_path = root / "work.sqlite"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE work (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    acquire_runtime_lock(str(root), str(state_dir), exe_path=sys.executable, db_path=str(db_path))
    shutdown = threading.Event()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_type(root, mode, shutdown))
    server.daemon_threads = False
    port = server.server_address[1]
    assert port not in {63938, 51093, 56264}
    write_runtime_host_port_files(str(root), str(state_dir), "127.0.0.1", port, str(db_path))
    write_runtime_contract_file(
        str(root), "127.0.0.1", port, db_path=str(db_path), shutdown_token=TOKEN,
        ui_mode="test", log_dir=str(state_dir), backup_dir=str(root / "backups"),
        excel_template_dir=str(root / "templates"), chrome_profile_dir=str(root / "chrome-profile"),
    )
    server_thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.025})
    server_thread.start()
    try:
        (root / "ready").touch()
        deadline = time.monotonic() + 40.0
        while not shutdown.wait(0.025) and not (root / "release").exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("Test controller did not stop the owned runtime")
        if mode == "healthy":
            _wait_for_release(root)
    finally:
        server.shutdown()
        server_thread.join(timeout=5)
        server.server_close()  # Drain the real non-daemon HTTP write before unlocking.
        release_runtime_lock(str(state_dir), db_path=str(db_path))
    return 0


def stop_cli(root: Path) -> int:
    from types import SimpleNamespace

    from web.bootstrap.entrypoint import app_main
    from web.bootstrap.launcher import stop_runtime_from_dir

    return app_main(
        anchor_file=str(root / "app.py"), argv=["--runtime-stop", str(root / "logs")],
        deps=SimpleNamespace(stop_runtime_from_dir=stop_runtime_from_dir),
    )


if __name__ == "__main__":
    root_arg = Path(sys.argv[2]).resolve()
    if sys.argv[1] == "serve":
        raise SystemExit(serve_runtime(root_arg, sys.argv[3]))
    if sys.argv[1] == "stop":
        raise SystemExit(stop_cli(root_arg))
    raise SystemExit("Unknown test subprocess mode")
