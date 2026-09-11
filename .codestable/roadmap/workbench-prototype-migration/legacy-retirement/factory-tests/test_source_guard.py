"""Negative tests for unloaded roots, mode drift and original-tree fallback."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from source_binding import fingerprints
from source_guard import FrozenSourceGuard
from source_inventory import discover, inspect_imports


class SourceGuardTests(unittest.TestCase):
    def test_unloaded_namespace_roots_are_statically_included(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "common").mkdir()
            (root / "common/overdue_calculations.py").write_text("VALUE = 1\n")
            (root / "app.py").write_text("from common import overdue_calculations\n")
            names, scope = discover(root)
            self.assertIn("common/overdue_calculations.py", names)
            self.assertIn("common", scope["owned_import_roots"])
            self.assertEqual(inspect_imports(root, names, scope["owned_import_roots"])["missing_repo_modules"], [])
            (root / "app.py").write_text("import common.missing_module\n")
            missing = inspect_imports(root, names, scope["owned_import_roots"])["missing_repo_modules"]
            self.assertEqual(missing[0]["module"], "common.missing_module")

    def test_modes_and_all_owned_paths_are_guarded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, origin, harness = root / "source", root / "origin", root / "harness"
            for folder in (source, origin, harness):
                folder.mkdir()
                (folder / "common").mkdir()
                (folder / "common/file.py").write_text("VALUE = 1\n")
            names, scope = discover(source)
            manifest = root / "source.json"
            manifest.write_text(json.dumps({"schema_version": 2, "origin_root": str(origin), "scope": scope,
                                            "static_import_inventory": {"missing_repo_modules": []}, "files": fingerprints(source, names)}))
            guard = FrozenSourceGuard(source, harness, manifest)
            original_path = sys.path
            self.addCleanup(setattr, sys, "path", original_path)
            sys.path = list(original_path)
            guard.restrict_sys_path()
            guard.inspect_modules({"common.file": SimpleNamespace(__file__=str(source / "common/file.py"))})
            for module in (SimpleNamespace(__file__=str(origin / "common/file.py")), SimpleNamespace(__path__=[str(origin / "common")])):
                with self.assertRaises((PermissionError, RuntimeError)):
                    guard.inspect_modules({"common.file": module})
            with self.assertRaises(PermissionError):
                guard.inspect_modules({"arbitrary_plugin_alias": SimpleNamespace(__file__=str(origin / "common/file.py"))})
            before = list(sys.path)
            try:
                sys.path.append(str(origin))
                with self.assertRaises(RuntimeError):
                    guard.inspect_modules({})
            finally:
                sys.path[:] = before
            (source / "common/file.py").chmod(0o755)
            with self.assertRaises(RuntimeError):
                guard.verify_files()


if __name__ == "__main__":
    unittest.main()
