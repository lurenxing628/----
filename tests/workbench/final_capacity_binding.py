"""Bind private capacity processes to the existing G and foundation source guards."""

import hashlib
import importlib
import json
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from tests.workbench.final_foundation_live_source_guard import install
from tests.workbench.live_environment import REPO

ENV = "FACTORY_SOURCE_MANIFEST"
EXPECTED_ROOT = "WORKBENCH_CAPACITY_EXPECTED_SOURCE_ROOT"
FORBIDDEN_ORIGIN = "WORKBENCH_CAPACITY_FORBIDDEN_ORIGIN"
MANIFEST_SHA256 = "WORKBENCH_CAPACITY_MANIFEST_SHA256"
G_PATH = ".codestable/roadmap/workbench-prototype-migration/legacy-retirement/factory-tests"
G_FILES = ("source_guard.py", "source_binding.py", "source_inventory.py")
_ACTIVE: Optional["CapacitySourceBinding"] = None


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _declared_manifest(path, digest):
    if digest != os.environ.get(MANIFEST_SHA256):
        raise ValueError("Capacity source manifest does not match its declared SHA256")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    origin = Path(manifest["origin_root"]).resolve()
    expected, forbidden = os.environ.get(EXPECTED_ROOT), os.environ.get(FORBIDDEN_ORIGIN)
    if not expected or not forbidden or Path(expected).resolve() != REPO or Path(forbidden).resolve() != origin:
        raise ValueError("Capacity source root or forbidden origin does not match its explicit binding")
    if Path(manifest["root"]).resolve() != REPO or origin == REPO or origin in REPO.parents or REPO in origin.parents:
        raise ValueError("Capacity requires a distinct private source and its original-root manifest")
    return manifest


def _harness_files(harness, manifest):
    rows = {row["path"]: row for row in manifest["files"]}
    result = {}
    for name in G_FILES:
        expected = rows.get(G_PATH + "/" + name)
        path = harness / name
        if expected is None or path.is_symlink() or not path.is_file():
            raise ValueError("Copied G guard is missing from the frozen manifest: " + name)
        actual = {"bytes": path.stat().st_size, "sha256": _digest(path),
                  "mode": format(stat.S_IMODE(path.stat().st_mode), "04o")}
        if actual != {key: expected[key] for key in actual}:
            raise ValueError("Copied G guard differs from the frozen manifest: " + name)
        result[name] = actual
    return result


class CapacitySourceBinding:
    def __init__(self, path):
        self.path = path
        self.manifest_sha256 = _digest(path)
        manifest = _declared_manifest(path, self.manifest_sha256)
        self.configuration = {key: os.environ.get(key) for key in (ENV, EXPECTED_ROOT, FORBIDDEN_ORIGIN, MANIFEST_SHA256)}
        origin = Path(manifest["origin_root"]).resolve()
        self.harness = REPO.parent / "harness"
        if self.harness.is_symlink():
            raise ValueError("Capacity guard harness cannot be a symlink")
        self.harness_files = _harness_files(self.harness, manifest)
        for name in G_FILES:
            module = sys.modules.get(Path(name).stem)
            if module is not None and Path(getattr(module, "__file__", "")).resolve() != self.harness / name:
                raise ValueError("G source guard was already imported from another location: " + name)
        sys.path.insert(0, str(self.harness))
        guard_type = importlib.import_module("source_guard").FrozenSourceGuard
        self.guard = guard_type(REPO, self.harness, path)
        self.guard.restrict_sys_path()
        self.guard.inspect_modules()
        self.read_guard = install({"expected_root": str(REPO), "forbidden_roots": [str(origin)],
                                   "python_runtime_read_only": [str(root) for root in self.guard.dependencies],
                                   "capacity_manifest_sha256": self.manifest_sha256})
        self.evidence()

    def evidence(self):
        if _digest(self.path) != self.manifest_sha256:
            raise RuntimeError("Capacity source manifest changed during execution")
        self.guard.verify_files()
        if _harness_files(self.harness, self.guard.manifest) != self.harness_files:
            raise RuntimeError("Capacity source harness changed during execution")
        modules = self.guard.inspect_modules()
        origins = {}
        for name, module in list(sys.modules.items()):
            origin = getattr(getattr(module, "__spec__", None), "origin", None)
            if isinstance(origin, str) and origin not in ("built-in", "frozen"):
                origins[name] = SimpleNamespace(__file__=origin)
        self.guard.inspect_modules(origins)
        reads = self.read_guard.evidence()
        if reads["violations"]:
            raise PermissionError("Capacity source boundary recorded a forbidden operation")
        return {"manifest": str(self.path), "manifest_sha256": self.manifest_sha256,
                "aggregate_sha256": self.guard.manifest["aggregate_sha256"],
                "expected_source_root": str(REPO), "origin_root": str(self.guard.origin),
                "manifest_file_count": len(self.guard.files), "harness_files": self.harness_files,
                "sys_path": list(sys.path), "loaded_modules": modules,
                "module_spec_origins": {name: module.__file__ for name, module in origins.items()},
                "read_guard": reads, "enabled": True, "verified": True}

    def host_evidence(self, directory, *, expected_pid):
        proof = json.loads((directory / "capacity-source-binding.json").read_text(encoding="utf-8"))
        for phase in ("before", "after"):
            assert proof[phase]["enabled"] and proof[phase]["verified"]
            assert proof[phase]["manifest_sha256"] == self.manifest_sha256
            assert proof[phase]["expected_source_root"] == str(REPO)
            assert proof[phase]["origin_root"] == str(self.guard.origin)
            assert proof[phase]["read_guard"]["pid"] == expected_pid
            assert not proof[phase]["read_guard"]["violations"]
        return proof


def binding_evidence(binding):
    return binding.evidence() if binding is not None else {"enabled": False, "verified": False}


def install_capacity_binding(*, required=False):
    global _ACTIVE
    value = os.environ.get(ENV)
    if not value:
        if required or _ACTIVE is not None or any(os.environ.get(key) for key in (EXPECTED_ROOT, FORBIDDEN_ORIGIN, MANIFEST_SHA256)):
            raise ValueError("Formal private capacity requires FACTORY_SOURCE_MANIFEST before importing the host")
        return None
    path = Path(value).resolve()
    if _ACTIVE is None:
        _ACTIVE = CapacitySourceBinding(path)
    elif _ACTIVE.path != path or any(os.environ.get(key) != value for key, value in _ACTIVE.configuration.items()):
        raise ValueError("Capacity source manifest cannot change during a process")
    return _ACTIVE
