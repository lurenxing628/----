"""Read-only frozen-source boundary for the foundation coordinator and host."""

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO = Path(__file__).resolve().parents[2]
ENV = "WORKBENCH_FOUNDATION_SOURCE_GUARD"
OWNED = (
    "final_foundation_live.py", "final_foundation_live_support.py",
    "final_foundation_live_source_guard.py", "final_foundation_live_nav_cases.py",
    "final_foundation_navigation_seed.py", "test_final_foundation_live.py",
    "final_foundation_live.cjs", "final_foundation_live_probe.cjs",
    "final_foundation_live_actions.cjs", "final_foundation_live_faults.cjs",
    "final_foundation_live_boot_cases.cjs", "final_foundation_live_navigation.cjs",
)
_ACTIVE = None


def inside(path, root):
    return path == root or root in path.parents


def test_snapshot():
    files = {"tests/workbench/" + name: hashlib.sha256((REPO / "tests/workbench" / name).read_bytes()).hexdigest()
             for name in OWNED}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
    return {"sha256": digest, "files": files, "ownership": "B tests only; not the original F test snapshot"}


def configuration(expected, forbidden, expected_tests=None):
    expected = Path(expected).resolve()
    forbidden = [Path(value).resolve() for value in forbidden]
    if expected != REPO or not forbidden or any(inside(expected, path) or inside(path, expected) for path in forbidden):
        raise ValueError("Run the copied entrypoint from a distinct expected frozen source root")
    runtime = sorted({str(Path(value).resolve()) for value in (sys.prefix, sys.base_prefix)})
    if any(Path(value) in forbidden or Path(value) == expected for value in runtime):
        raise ValueError("A whole source root cannot be a Python runtime exception")
    snapshot = test_snapshot()
    if expected_tests is not None and snapshot["sha256"] != expected_tests:
        raise ValueError("Unexpected B tests-only snapshot SHA256")
    return {"expected_root": str(expected), "forbidden_roots": [str(value) for value in forbidden],
            "python_runtime_read_only": runtime, "test_snapshot": snapshot}


class SourceGuard:
    def __init__(self, config):
        self.config = config
        self.expected = Path(config["expected_root"])
        if self.expected != REPO:
            raise ValueError("Host imported the guard from a different source tree")
        self.forbidden = [Path(value) for value in config["forbidden_roots"]]
        self.runtime = [Path(value) for value in config["python_runtime_read_only"]]
        self.violations = []
        self.sqlite_connections = []

    def check(self, value, event, writing=False):
        if isinstance(value, int) or value is None:
            return
        path = Path(os.fsdecode(value)).resolve()
        original = any(inside(path, root) for root in self.forbidden)
        runtime_read = not writing and any(inside(path, root) for root in self.runtime)
        if original and not runtime_read or writing and inside(path, self.expected):
            row = {"event": event, "path": str(path), "writing": writing}
            self.violations.append(row)
            raise PermissionError("Frozen source guard rejected " + json.dumps(row))

    def audit(self, event, args):
        if event == "open":
            mode, flags = args[1:3]
            writing = isinstance(mode, str) and any(char in mode for char in "wax+")
            writing = writing or isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            self.check(args[0], event, writing)
        elif event in ("os.listdir", "os.scandir"):
            self.check(args[0], event)
        elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.utime", "os.truncate"):
            self.check(args[0], event, True)
        elif event in ("os.rename", "os.link", "os.symlink"):
            self.check(args[0], event, True)
            self.check(args[1], event, True)

    def database(self, value):
        value = os.fsdecode(value)
        if value != ":memory:":
            file = unquote(urlsplit(value).path) if value.startswith("file:") else value
            self.check(file, "sqlite3.connect", True)
        self.sqlite_connections.append(value)

    def evidence(self):
        modules = {}
        for name, module in list(sys.modules.items()):
            if name.split(".", 1)[0] not in ("core", "data", "web", "plugins", "tests", "scripts"):
                continue
            file = getattr(module, "__file__", None)
            if not file:
                continue
            path = Path(file).resolve()
            if not inside(path, self.expected):
                self.violations.append({"event": "loaded_project_module", "name": name, "path": str(path)})
                raise PermissionError("Project module loaded outside the frozen source: " + name)
            modules[name] = str(path)
        return {**self.config, "pid": os.getpid(), "loaded_project_modules": modules,
                "violations": list(self.violations), "sqlite_connections": list(self.sqlite_connections),
                "original_source_or_database_fallback": False}


def install(config):
    global _ACTIVE
    if _ACTIVE is not None:
        if _ACTIVE.config != config:
            raise ValueError("Source guard configuration cannot change during a process")
        return _ACTIVE
    guard = SourceGuard(config)
    guard.evidence()
    sys.addaudithook(guard.audit)
    original_connect = sqlite3.connect

    def connect(database, *args, **kwargs):
        guard.database(database)
        return original_connect(database, *args, **kwargs)

    sqlite3.connect = connect
    os.environ[ENV] = json.dumps(config)
    _ACTIVE = guard
    return guard


def install_from_environment():
    raw = os.environ.get(ENV)
    return install(json.loads(raw)) if raw else None
