"""Reject original-checkout fallback for every owned module and namespace path."""

import json
import os
import site
import sys
from pathlib import Path

from source_binding import fingerprints


def within(path, root):
    return path == root or root in path.parents


class FrozenSourceGuard:
    def __init__(self, source, harness, manifest):
        self.source, self.harness = source.resolve(), harness.resolve()
        self.manifest_path = manifest.resolve()
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if self.manifest.get("schema_version") != 2:
            raise ValueError("A static-inventory source binding v2 is required.")
        if self.manifest["static_import_inventory"]["missing_repo_modules"]:
            raise ValueError("Cannot run a source snapshot with missing owned modules.")
        self.origin = Path(self.manifest["origin_root"]).resolve()
        self.owners = set(self.manifest["scope"]["owned_import_roots"])
        self.files = {row["path"] for row in self.manifest["files"]}
        self.dependencies = [Path(sys.base_prefix).resolve()] + [Path(value).resolve() for value in site.getsitepackages()]
        self.verify_files()

    def verify_files(self):
        actual = fingerprints(self.source, [row["path"] for row in self.manifest["files"]])
        if actual != self.manifest["files"]:
            raise RuntimeError("Frozen source content or modes changed.")

    def dependency(self, path):
        return any(within(path, root) for root in self.dependencies)

    def restrict_sys_path(self):
        if self.harness.parent != self.source.parent:
            raise ValueError("The test harness itself must be copied beside the frozen source.")
        dependency_paths = [entry for entry in sys.path if entry and self.dependency(Path(entry).resolve())]
        sys.path[:] = list(dict.fromkeys([str(self.source), str(self.harness)] + dependency_paths))

    def check_read(self, value):
        if value is None or isinstance(value, int):
            return
        path = Path(os.fsdecode(value)).resolve()
        if within(path, self.origin) and not within(path, self.source) and not self.dependency(path):
            raise PermissionError("Original-checkout read fallback blocked: " + str(path))

    def _file_in_manifest(self, path):
        relative = path.relative_to(self.source).as_posix()
        if relative in self.files:
            return True
        return any(parent.relative_to(self.source).as_posix() in self.files
                   for parent in path.parents if within(parent, self.source) and parent.suffix in (".zip", ".whl"))

    def inspect_modules(self, modules=None):
        records = {}
        for name, module in (modules if modules is not None else sys.modules).items():
            top = name.split(".", 1)[0]
            filename = getattr(module, "__file__", None)
            namespaces = list(getattr(module, "__path__", ()) or ())
            paths = ([filename] if filename else []) + namespaces
            for value in paths:
                path = Path(value).resolve()
                self.check_read(path)
                if top in self.owners and not within(path, self.source):
                    raise RuntimeError("Owned module escaped frozen source: " + name + " -> " + str(path))
                if filename == value and within(path, self.source) and not self._file_in_manifest(path):
                    raise RuntimeError("Loaded repo file is absent from source manifest: " + str(path))
                if not (within(path, self.source) or within(path, self.harness) or self.dependency(path)):
                    raise RuntimeError("Unbound import location: " + name + " -> " + str(path))
            if paths and (top in self.owners or any(within(Path(value).resolve(), self.source) for value in paths)):
                records[name] = {"file": filename, "namespace_paths": namespaces}
        for entry in sys.path:
            path = Path(entry or os.getcwd()).resolve()
            if not (within(path, self.source) or within(path, self.harness) or self.dependency(path)):
                raise RuntimeError("Unbound sys.path entry: " + str(path))
        return records
