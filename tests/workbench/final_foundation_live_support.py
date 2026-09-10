"""Private full-build/source checks and exact read-only business retention."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from tests.workbench.final_foundation_live_source_guard import ENV
from tests.workbench.live_environment import REPO, environment, write_json

HERE = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def source_snapshot():
    paths = set(REPO.glob("*.py")) | {REPO / "schema.sql"}
    for name in ("core", "data", "web", "plugins", "frontend/workbench", "templates/workbench", "scripts/workbench"):
        paths.update(path for path in (REPO / name).rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    paths.update(HERE.glob("final_foundation*.py"))
    paths.update(HERE.glob("final_foundation*.cjs"))
    paths.add(HERE / "test_final_foundation_live.py")
    return {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}


def runtime_tools():
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"
    node = os.environ.get("WORKBENCH_NODE") or str(bundled / "bin/node")
    browser = os.environ.get("WORKBENCH_BROWSER") or "/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
    if not Path(node).is_file() or not Path(browser).is_file():
        raise RuntimeError("Set WORKBENCH_NODE and WORKBENCH_BROWSER to installed Node and Chromium 109")
    modules = os.pathsep.join(value for value in (os.environ.get("NODE_PATH"), str(bundled / "node_modules")) if value)
    return node, browser, modules


def copy_prebuilt(root, asset_root, expected_manifest):
    asset_root = Path(asset_root).resolve()
    source_manifest = asset_root / "asset-manifest.json"
    raw = source_manifest.read_bytes()
    if expected_manifest is not None:
        assert hashlib.sha256(raw).hexdigest() == expected_manifest, "Unexpected prebuilt manifest"
    manifest = json.loads(raw)
    assert manifest["schema_version"] == 1 and manifest["target"] == "chrome109"
    assert len({row["path"] for row in manifest["files"]}) == len(manifest["files"])
    frozen = root / "full-build/static/workbench"
    for row in manifest["files"]:
        source = (asset_root.parent / row["path"]).resolve()
        relative = source.relative_to(asset_root)
        data = source.read_bytes()
        assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"], row["path"]
        target = frozen / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    frozen.mkdir(parents=True, exist_ok=True)
    (frozen / "asset-manifest.json").write_bytes(raw)
    assert source_manifest.read_bytes() == raw, "Prebuilt manifest changed during copy"


def build_private(root, env, node, asset_root=None, expected_build=None, expected_manifest=None):
    command = None
    if asset_root is not None:
        copy_prebuilt(root, asset_root, expected_manifest)
    else:
        with (root / "full-build.stdout.log").open("w", encoding="utf-8") as out, (root / "full-build.stderr.log").open("w", encoding="utf-8") as err:
            command = [sys.executable, "-B", str(REPO / "scripts/workbench/build.py"), "--node", node,
                       "--output-dir", str(root / "full-build/static/workbench")]
            result = subprocess.run(command, cwd=str(REPO), env=env, stdout=out, stderr=err, timeout=180)
        if result.returncode:
            raise RuntimeError("Private full build failed: " + str(root / "full-build.stderr.log"))
    manifest_path = root / "full-build/static/workbench/asset-manifest.json"
    manifest = read_json(manifest_path)
    assert manifest["target"] == "chrome109"
    if expected_manifest is not None:
        assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == expected_manifest, "Unexpected private manifest"
    if expected_build is not None:
        assert manifest["build_id"] == expected_build, "Unexpected full-build identity"
    for row in manifest["files"]:
        data = (root / "full-build/static" / row["path"]).read_bytes()
        assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"], row["path"]
    for row in manifest["inputs"]:
        assert hashlib.sha256((REPO / row["path"]).read_bytes()).hexdigest() == row["sha256"], row["path"]
    shutil.copytree(str(REPO / "templates/workbench"), str(root / "full-build/templates/workbench"))
    templates = []
    for source in sorted((REPO / "templates/workbench").rglob("*")):
        if source.is_file():
            relative = source.relative_to(REPO)
            frozen = root / "full-build" / relative
            source_bytes, frozen_bytes = source.read_bytes(), frozen.read_bytes()
            assert source_bytes == frozen_bytes, str(relative)
            templates.append({"source": str(relative), "frozen": str(frozen), "bytes": len(frozen_bytes),
                              "sha256": hashlib.sha256(frozen_bytes).hexdigest()})
    return {"build_id": manifest["build_id"], "files": len(manifest["files"]), "inputs": len(manifest["inputs"]),
            "manifest": str(manifest_path), "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "templates": templates, "command": command, "global_build": False,
            "prebuilt_asset_root": str(Path(asset_root).resolve()) if asset_root is not None else None}


class FoundationHost:
    def __init__(self, root, *, port=0, reuse=False, navigation_seed=False):
        self.root, self.ready = root, None
        self.navigation_seed = navigation_seed
        name = "restart" if reuse else "initial"
        self.streams = [(root / (name + suffix)).open("w", encoding="utf-8") for suffix in ("-host.stdout.log", "-host.stderr.log")]
        env = environment(root)
        env["PYTHONPYCACHEPREFIX"] = str(root / "tmp/pycache")
        entry = HERE / "final_foundation_host.py"
        if navigation_seed or ENV in env:
            identity = read_json(root / "isolation.json")
            env.update(WORKBENCH_FOUNDATION_NAV_ROOT=str(root), WORKBENCH_FOUNDATION_NAV_OWNER_PID=str(os.getpid()),
                       WORKBENCH_FOUNDATION_NAV_NONCE=identity["nonce"], WORKBENCH_FOUNDATION_NAV_ENABLED="1" if navigation_seed else "0")
            entry = HERE / "final_foundation_navigation_seed.py"
        command = [sys.executable, "-B", str(entry), "--root", str(root), "--port", str(port)]
        if reuse:
            command.append("--reuse-root")
        self.command = command
        self.process = subprocess.Popen(command, cwd=str(REPO), env=env, stdout=self.streams[0], stderr=self.streams[1])

    def wait_ready(self):
        deadline = time.monotonic() + 90
        path = self.root / "server-ready.json"
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("Main host exited before ready: " + str(self.process.returncode))
            if path.exists():
                try:
                    value = read_json(path)
                except json.JSONDecodeError:
                    time.sleep(0.05)
                    continue
                if value["pid"] == self.process.pid:
                    self.ready = value
                    assert not value["url"].endswith(":53144")
                    return value
            time.sleep(0.05)
        raise TimeoutError("Main foundation host did not become ready")

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=90)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
            write_json(self.root / "forced-host-stop.json", {"pid": self.process.pid, "command": self.command})
            raise
        finally:
            for stream in self.streams:
                stream.close()
        assert self.process.returncode == 0, "Main host did not exit normally"
        assert self.ready is not None
        final = read_json(self.root / "sessions" / self.ready["session"] / "server-final.json")
        assert final["stopped"] and final["runtime"]["closed"] and final["runtime"]["pending"] == []
        assert final["assets_unchanged"] and final["isolation_violations"] == []
        assert not Path(self.ready["runtime_lock"]["path"]).exists()
        assert not Path(self.ready["db_lock"]).exists()
        guard_path = self.root / ("foundation-source-guard-host-" + str(self.process.pid) + ".json")
        guard = read_json(guard_path) if guard_path.exists() else None
        if ENV in os.environ:
            assert guard is not None and guard["violations"] == [], "Frozen-source guard evidence is missing or failed"
        return {"pid": self.process.pid, "returncode": self.process.returncode, "command": self.command, "final": final, "source_guard": guard}


def verify_read_retention(root, first, second=None):
    first_dir = root / "sessions" / first["session"]
    original, first_after = (read_json(first_dir / name) for name in ("business-before.json", "business-after.json"))
    assert original == first_after, "Shell reads or injected client failures changed business rows"
    if second is None:
        return {"original_rows_preserved": True, "first_reads_zero_writes": True,
                "restart_applicable": False, "source": [str(first_dir)]}
    second_dir = root / "sessions" / second["session"]
    restart, restart_after = (read_json(second_dir / name) for name in ("business-before.json", "business-after.json"))
    assert restart == restart_after, "Browser reload after restart changed business rows"
    assert set(original) == set(restart)
    changed = [name for name in original if original[name] != restart[name]]
    assert set(changed) <= {"OperationLogs", "sqlite_sequence"}, changed
    assert restart["OperationLogs"][:len(original["OperationLogs"])] == original["OperationLogs"]
    added = restart["OperationLogs"][len(original["OperationLogs"]):]
    assert added and all(row["module"] == "plugins" and row["action"] == "load" for row in added)
    old_sequences = {row["name"]: row["seq"] for row in original["sqlite_sequence"]}
    new_sequences = {row["name"]: row["seq"] for row in restart["sqlite_sequence"]}
    expected = {**old_sequences, "OperationLogs": max(row["id"] for row in restart["OperationLogs"])}
    assert new_sequences == expected
    return {"original_rows_preserved": True, "first_reads_zero_writes": True, "restart_reads_zero_writes": True,
            "unchanged_tables": sorted(set(original) - set(changed)), "startup_audit_appended": added,
            "source": [str(first_dir), str(second_dir)]}
