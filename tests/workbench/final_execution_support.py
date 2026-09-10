"""Private build, process lifecycle and real HTTP helpers for final Task E acceptance."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from tests.workbench.live_environment import create_root, environment, write_json
from tests.workbench.run_live_server_support import database_state
from tests.workbench.test_live_browser import runtime_tools

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(parent):
    node, browser, modules = runtime_tools()
    output = parent / "full-build"
    if output.exists():
        validate_build(output)
        return output, (node, browser, modules)
    shared = os.environ.get("FINAL_E_SHARED_BUILD")
    if shared:
        source = Path(shared).resolve()
        manifest = validate_build(source.parent.parent)
        assert manifest["build_id"] == os.environ["FINAL_E_SHARED_BUILD_ID"], "Shared build identity changed"
        shutil.copytree(str(source.parent), str(output / "static"))
        shutil.copytree(str(REPO / "templates/workbench"), str(output / "templates/workbench"))
        assert validate_build(output) == manifest
        write_json(parent / "build-proof.json", {"build_id": manifest["build_id"], "file_count": len(manifest["files"]),
            "input_count": len(manifest["inputs"]), "target": manifest["target"], "reused_from": str(source),
            "files_match": True, "inputs_match": True, "main_source": True,
            "templates": {str(file.relative_to(output)): sha(file) for file in (output / "templates").rglob("*") if file.is_file()}})
        return output, (node, browser, modules)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(parent / "pycache"))
    command = [sys.executable, "-B", str(REPO / "scripts/workbench/build.py"), "--node", node,
               "--output-dir", str(output / "static/workbench")]
    result = subprocess.run(command, cwd=str(REPO), env=env, capture_output=True, text=True, timeout=240)
    write_json(parent / "build-command.json", {"command": command, "returncode": result.returncode,
                                               "stdout": result.stdout, "stderr": result.stderr})
    assert result.returncode == 0, result.stderr
    shutil.copytree(str(REPO / "templates/workbench"), str(output / "templates/workbench"))
    manifest = validate_build(output)
    write_json(parent / "build-proof.json", {"build_id": manifest["build_id"], "file_count": len(manifest["files"]),
                                            "input_count": len(manifest["inputs"]), "target": manifest["target"],
                                            "files_match": True, "inputs_match": True, "main_source": True})
    return output, (node, browser, modules)


def validate_build(output):
    inventory = subprocess.run([sys.executable, "-B", "-c", "from build import ROOT, TOOLS, live_inputs; "
        "from asset_sources import load_json; live_inputs(ROOT, load_json(TOOLS / 'build-order.json'))"],
        cwd=str(REPO / "scripts/workbench"), capture_output=True, text=True, timeout=30)
    assert inventory.returncode == 0, inventory.stderr
    manifest = json.loads((output / "static/workbench/asset-manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        target = output / "static" / item["path"]
        assert sha(target) == item["sha256"] and target.stat().st_size == item["bytes"], item["path"]
    assert any(item["path"] == "frontend/workbench/app/main.jsx" for item in manifest["inputs"])
    for item in manifest["inputs"]:
        assert sha(REPO / item["path"]) == item["sha256"], item["path"]
    return manifest


class Host:
    def __init__(self, parent, built, runtime, profile):
        self.root = create_root(parent)
        shutil.copytree(str(built), str(self.root / "full-build"))
        self.profile = profile
        self.node, browser, modules = runtime
        self.env = environment(self.root)
        self.env.update(WORKBENCH_NODE=self.node, WORKBENCH_BROWSER=browser, NODE_PATH=modules,
                        PYTHONPYCACHEPREFIX=str(self.root / "pycache"), WORKBENCH_PYTHON=sys.executable)
        self.process = self.out = self.err = None
        self.ready = None
        self.sessions = []

    def start(self, reuse=False):
        if reuse:
            assert self.ready is not None, "Only an initialized owned host can restart"
        old_session = self.ready["session"] if self.ready else None
        port = str(urlsplit(self.ready["url"]).port) if reuse and self.ready else "0"
        self.out = (self.root / ("host-restart.out.log" if reuse else "host.out.log")).open("w", encoding="utf-8")
        self.err = (self.root / ("host-restart.err.log" if reuse else "host.err.log")).open("w", encoding="utf-8")
        command = [sys.executable, "-B", str(HERE / "final_execution_host.py"), "--root", str(self.root),
                   "--profile", self.profile, "--port", port] + (["--reuse-root"] if reuse else [])
        self.process = subprocess.Popen(command, cwd=str(self.root), env=self.env, stdout=self.out, stderr=self.err)
        deadline = time.monotonic() + 90
        ready_path = self.root / "server-ready.json"
        while True:
            assert self.process.poll() is None, "Host failed: " + str(self.root)
            if ready_path.exists():
                try:
                    current = json.loads(ready_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    current = None
                if current is not None and current["session"] != old_session:
                    self.ready = current
                    self.sessions.append(current)
                    return self
            assert time.monotonic() < deadline, "Host startup timeout: " + str(self.root)
            time.sleep(.05)

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
                raise AssertionError("Owned host required forced kill: " + str(self.root))
        if self.out:
            self.out.close()
        if self.err:
            self.err.close()
        if self.process is not None:
            assert self.process.returncode == 0, "Host shutdown failed: " + str(self.root)
            final = json.loads((self.root / "server-final.json").read_text(encoding="utf-8"))
            assert final["stopped"] and final["assets_unchanged"]
            assert final["isolation_violations"] == []
            assert final["python_sources"]["changed"] == [], final["python_sources"]["changed"]
            assert not final["recovery_required"]
            if os.environ.get("FINAL_E_SOURCE_MANIFEST"):
                binding = json.loads((self.root / ("sealed-process-" + str(self.process.pid) + ".json")).read_text(encoding="utf-8"))
                assert binding["content_and_modes_verified"] and binding["read_violations"] == []
                assert binding["source"] == str(REPO) and "error" not in binding

    def state(self):
        return database_state(self.root / "db/aps-live.db")

    def request(self, path, *, query=None, body=None, headers=None, raw=None):
        assert self.ready is not None, "HTTP requests require an initialized owned host"
        if query:
            path += "?" + urlencode(query, doseq=True)
        payload = json.dumps(body).encode("utf-8") if body is not None else raw
        request_headers = dict(headers or {})
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.ready["url"] + path, data=payload, headers=request_headers)
        try:
            response = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as response:
            return response.code, dict(response.headers), response.read()
        with response:
            return response.status, dict(response.headers), response.read()

    def json(self, path, *, query=None, body=None, status=200):
        code, _, raw = self.request(path, query=query, body=body)
        result = json.loads(raw.decode("utf-8"))
        assert code == status, (code, result)
        return result

    def browser(self, script, *args, timeout=900):
        command = [self.node, str(HERE / script), str(self.root / "server-ready.json")] + list(args)
        result = subprocess.run(command, env=self.env, cwd=str(self.root), capture_output=True, text=True, timeout=timeout)
        write_json(self.root / (script + ".command.json"), {"command": command, "returncode": result.returncode,
                                                            "stdout": result.stdout, "stderr": result.stderr})
        assert result.returncode == 0, result.stderr + result.stdout + "\n" + str(self.root)


@contextmanager
def serving(parent, built, runtime, profile):
    host = Host(parent, built, runtime, profile)
    try:
        yield host.start()
    finally:
        host.stop()


def changes(before, after):
    return {table for table in set(before) | set(after) if before.get(table) != after.get(table)}


def old_rows_preserved(before, after, allowed=()):
    for table, rows in before.items():
        if table not in allowed:
            assert all(row in after[table] for row in rows), table


def restart_preserved(before, after):
    assert changes(before, after) == {"OperationLogs", "sqlite_sequence"}
    old_rows_preserved(before, after, {"sqlite_sequence"})
    added = after["OperationLogs"][len(before["OperationLogs"]):]
    assert len(added) == 1
    assert {key: added[0][key] for key in ("module", "action", "target_type", "target_id", "log_level")} == {
        "module": "plugins", "action": "load", "target_type": "runtime", "target_id": "plugins", "log_level": "INFO"}
    old_sequences = {row["name"]: row["seq"] for row in before["sqlite_sequence"]}
    new_sequences = {row["name"]: row["seq"] for row in after["sqlite_sequence"]}
    assert new_sequences == {**old_sequences, "OperationLogs": old_sequences["OperationLogs"] + 1}
    return {"changed_tables": ["OperationLogs", "sqlite_sequence"], "startup_log": added[0], "old_rows_preserved": True}


def report_facts(report):
    # An expiring write capability is not an immutable production fact.
    return {key: value for key, value in report.items() if key != "write_context"}
