"""Real socket, real factory/launcher/worker, retained temporary DB and assets."""

import json
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, current_schema_contract_issues
from tests.workbench.live_environment import REPO, create_root
from tests.workbench.run_live_server_support import (
    BASE,
    FORBIDDEN_PORTS,
    loaded_python_sources,
    prepare_root,
    source_comparison,
)

SCRIPT = REPO / "tests/workbench/run_live_server.py"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class Process:
    def __init__(self, root, *, reuse=False, profile="mixed"):
        self.root = root
        self.log_path = root / ("restart-output.log" if reuse else "first-output.log")
        self.stream = self.log_path.open("w", encoding="utf-8")
        args = [sys.executable, "-B", str(SCRIPT), "--root", str(root), "--profile", profile]
        if reuse:
            args.append("--reuse-root")
        self.process = subprocess.Popen(args, cwd=str(REPO), stdout=self.stream, stderr=subprocess.STDOUT)
        self.ready = None

    def wait_ready(self):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                pytest.fail(self.log_path.read_text(encoding="utf-8"))
            path = self.root / "server-ready.json"
            if path.exists():
                try:
                    ready = read_json(path)
                except json.JSONDecodeError:
                    ready = {}
                if ready.get("pid") == self.process.pid:
                    self.ready = ready
                    return ready
            time.sleep(.05)
        pytest.fail("Fixture startup timed out: " + self.log_path.read_text(encoding="utf-8"))

    def http(self, path, body=None, *, expected=200, raw=False):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = Request(self.ready["url"] + path, data=data,
                      headers={"Content-Type": "application/json"} if body is not None else {})
        try:
            response = urlopen(req, timeout=30)
        except HTTPError as exc:
            response = exc
        with response:
            payload = response.read()
            assert response.status == expected, payload.decode("utf-8", errors="replace")
            return payload if raw else json.loads(payload)

    def stop(self):
        if self.process.poll() is None:
            if self.ready is not None:
                Path(self.ready["stop_file"]).touch()
            else:
                self.process.terminate()
            self.process.wait(timeout=90)
        self.stream.close()


def wait_result(server, ref):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        data = server.http(BASE + "/runs/" + ref)["data"]
        if data["state"] not in ("queued", "running"):
            return data
        time.sleep(.05)
    pytest.fail("Run did not terminate")


def test_real_http_four_candidates_exit_backup_and_explicit_restart(tmp_path):
    root = create_root(tmp_path)
    server = Process(root)
    try:
        ready = server.wait_ready()
        assert ready["schema_database_version"] == CURRENT_SCHEMA_VERSION
        with closing(sqlite3.connect(ready["paths"]["DATABASE_PATH"])) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            assert current_schema_contract_issues(conn) == []
        assert ready["runtime"]["ready"] and ready["runtime"]["reason"] == "ready"
        assert str(REPO / "web/bootstrap/workbench_run_runtime.py") in ready["loaded_python_sources"]
        assert int(ready["url"].rsplit(":", 1)[1]) not in FORBIDDEN_PORTS
        assert Path(ready["runtime_lock"]["path"]).exists() and Path(ready["db_lock"]).exists()
        for value in list(ready["paths"].values()) + [ready["stop_file"], ready["assets"]["static"]]:
            Path(value).resolve().relative_to(root)
        assert b"workbench" in server.http("/workbench", raw=True)
        assert server.http("/api/workbench/v1/plans")["data"]
        analytics = server.http("/api/workbench/v1/analytics")
        assert analytics["data"]["summary"]["confirmed_due"] == 1
        checked = server.http(BASE + "/preflight", ready["expected"]["settings"])
        assert checked["meta"]["source"] == "production"
        ref = checked["data"]["input_ref"]
        preview = server.http(BASE + "/runs/preview", {"input_ref": ref})
        context = preview["data"]["write_context"]
        assert context["capabilities"]["scheduling.run"] is True
        invalid = server.http(BASE + "/runs", {"input_ref": ref, "write_token": None,
                              "request_key": "bs-live-invalid-0001"}, expected=409)
        assert invalid["committed"] is False
        body = {"input_ref": ref, "write_token": context["write_token"], "request_key": "bs-live-real-request-0001"}
        accepted = server.http(BASE + "/runs", body, expected=202)
        run_ref = accepted["run_ref"]
        result = wait_result(server, run_ref)
        assert result["state"] == "complete" and result["result_persisted"] is True
        assert len(result["candidates"]) == 4
        assert server.http(BASE + "/runs", body, expected=202)["replayed"] is True
        assert server.http(BASE + "/requests/" + body["request_key"])["data"]["run"]["run_ref"] == run_ref
        asset_path = next(name for name in ready["assets"]["hashes"] if name.endswith(".js"))
        asset = server.http("/" + asset_path, raw=True)
        assert asset == (Path(ready["assets"]["root"]) / asset_path).read_bytes()
    finally:
        server.stop()
    assert server.process.returncode == 0, server.log_path.read_text(encoding="utf-8")
    final = read_json(root / "server-final.json")
    assert final["events"][-3:] == ["runtime_shutdown_joined", "exit_backup_complete_under_lock", "launcher_locks_released"]
    assert final["runtime"]["closed"] and not final["runtime"]["ready"]
    assert final["assets_unchanged"] and final["files_retained"] and not final["isolation_violations"]
    assert final["python_sources"]["before"] == ready["loaded_python_sources"]
    assert not Path(ready["runtime_lock"]["path"]).exists() and not Path(ready["db_lock"]).exists()
    assert Path(final["exit_backup"]).is_file()
    for path in final["sqlite_connections"]:
        if path != ":memory:":
            Path(path).resolve().relative_to(root)
    before, after = read_json(root / "business-before.json"), read_json(root / "business-after.json")
    for table in ("Schedule", "ScheduleHistory", "ScheduleCandidate", "OperationExecutionEvents"):
        assert after[table] == before[table]
    assert len(after["WorkbenchRunJobs"]) == 1 and len(after["WorkbenchRunCandidates"]) == 4
    assert read_json(root / "write-manifest.json")["created"]
    with pytest.raises(ValueError, match="explicit --reuse-root"):
        prepare_root(root)
    restarted = Process(root, reuse=True)
    try:
        again = restarted.wait_ready()
        assert again["schema_database_version"] == CURRENT_SCHEMA_VERSION
        with closing(sqlite3.connect(again["paths"]["DATABASE_PATH"])) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            assert current_schema_contract_issues(conn) == []
        assert again["session"] != ready["session"] and again["runtime"]["ready"]
        assert restarted.http(BASE + "/runs/" + run_ref)["data"] == result
        assert restarted.http(BASE + "/requests/" + body["request_key"])["data"]["run"]["run_ref"] == run_ref
        assert restarted.http("/workbench", raw=True)
    finally:
        restarted.stop()
    assert restarted.process.returncode == 0, restarted.log_path.read_text(encoding="utf-8")
    assert len(read_json(root / "business-after.json")["WorkbenchRunJobs"]) == 1
    assert Path(final["exit_backup"]).is_file()


def test_reject_unowned_reuse_and_external_symlink(tmp_path):
    root = create_root(tmp_path)
    with pytest.raises(FileNotFoundError):
        prepare_root(root, reuse=True)
    target = tmp_path / "not-a-fixture.db"
    target.write_bytes(b"never open this")
    link = root / "db/aps-live.db"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable for this account")
    with pytest.raises(ValueError):
        prepare_root(root)
    assert target.read_bytes() == b"never open this"


def test_provenance_tracks_loaded_modules_without_unrelated_new_files():
    sources = loaded_python_sources()
    assert str(REPO / "tests/workbench/run_live_server_support.py") in sources
    before = {"existing.py": "same", "changed.py": "old", "deleted.py": "old"}
    after = {"existing.py": "same", "changed.py": "new", "late_import.py": "new"}
    result = source_comparison(before, after)
    assert result["changed"] == ["changed.py", "deleted.py"]
    assert result["loaded_after_ready"] == ["late_import.py"]


def test_guard_rejects_external_database_and_frozen_asset_writes(tmp_path):
    root = create_root(tmp_path)
    code = """
import json, sqlite3, sys
from pathlib import Path
from tests.workbench.run_live_server_support import isolate, protect_frozen_assets
root = Path(sys.argv[1])
asset = root / 'static/frozen.js'
asset.write_text('original', encoding='utf-8')
evidence = isolate(root)
protect_frozen_assets({'root': str(root / 'static')})
denied = []
for action in (lambda: sqlite3.connect(str(root.parent / 'outside-never-opened.db')),
               lambda: asset.write_text('changed', encoding='utf-8')):
    try:
        action()
    except PermissionError:
        denied.append(True)
assert denied == [True, True]
assert not (root.parent / 'outside-never-opened.db').exists()
assert asset.read_text(encoding='utf-8') == 'original'
print(json.dumps({'denied': denied, 'sqlite_connections': evidence['sqlite_connections']}))
"""
    result = subprocess.run([sys.executable, "-B", "-c", code, str(root)], cwd=str(REPO),
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"denied": [True, True], "sqlite_connections": []}


def test_pending_restore_refuses_fixture_seed_and_exit_backup_without_opening_database(tmp_path):
    from core.services.workbench.system_journal import SystemMaintenanceJournal

    root = create_root(tmp_path)
    database = root / "db/aps-live.db"
    directory = Path(str(database) + ".system-journal")
    directory.mkdir()
    journal = SystemMaintenanceJournal(str(directory), str(database))
    journal.begin("fixture-pending-restore-0001", "restore", {"backup_ref": "not-replayed"})
    original_records = {path.name: path.read_bytes() for path in directory.iterdir()}
    server = Process(root)
    try:
        server.process.wait(timeout=60)
        assert server.process.returncode != 0
    finally:
        server.stop()
    final = read_json(root / "server-final.json")
    assert final["recovery_required"] and final["exit_backup"] is None
    assert final["sqlite_connections"] == [] and final["isolation_violations"] == []
    assert "exit_backup_skipped_restore_requires_restart" in final["events"]
    assert "real_runtime_ready" not in final["events"]
    assert not database.exists() and not list((root / "backups").glob("*.db"))
    assert not Path(str(database) + ".lock").exists()
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == original_records
