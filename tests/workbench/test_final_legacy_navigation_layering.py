"""Dependency direction and SELECT-only typed identity service contract."""

import ast
import json
import tempfile
import unittest
from pathlib import Path

from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.services.workbench.legacy_navigation_queries import LegacyNavigationQueries, LegacyNavigationSourceMissing
from tests.workbench.final_legacy_navigation_support import prepare_database
from tests.workbench.plan_read_support import connect

ROOT = Path(__file__).resolve().parents[2]


class LegacyNavigationLayeringTests(unittest.TestCase):
    def test_web_adapters_have_no_repository_or_sql_access(self):
        for name in ("legacy_navigation.py", "legacy_navigation_plan.py"):
            tree = ast.parse((ROOT / "web/routes/workbench" / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith("data."), (name, node.lineno))
                    self.assertFalse(any("Repository" in alias.name for alias in node.names), (name, node.lineno))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, ("execute", "executemany", "executescript", "cursor", "commit", "rollback"), (name, node.lineno))

    def test_core_query_leaf_has_no_http_or_web_imports(self):
        tree = ast.parse((ROOT / "core/services/workbench/legacy_navigation_queries.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        self.assertFalse({name.split(".", 1)[0] for name in imports} & {"web", "flask", "werkzeug"})

    def test_typed_queries_need_snapshot_and_leave_storage_unchanged(self):
        with tempfile.TemporaryDirectory(prefix="aps-g-legacy-query-") as directory:
            path = Path(directory) / "queries.db"
            prepare_database(path)
            conn = connect(path)
            try:
                conn.execute("PRAGMA query_only=ON")
                before = list(conn.iterdump())
                queries = LegacyNavigationQueries(conn)
                with self.assertRaises(RuntimeError):
                    queries.latest_version()
                with queries.read_snapshot():
                    bad_role, bad_scenario = json.loads("[null, false]")
                    binding = queries.bind_plan(3, "critical_best", None)
                    self.assertEqual(binding.locator, WorkbenchPlanLocator(3, "critical_best"))
                    self.assertFalse(binding.fallback)
                    self.assertEqual(len(binding.plan_ref), 48)
                    entity = queries.entity("machine", "PRIVATE-M1")
                    self.assertIsNotNone(entity.entity_ref)
                    for value in ("3", True, 0):
                        with self.subTest(version=value), self.assertRaises(ValueError):
                            queries.version_exists(value)
                    with self.assertRaises(ValueError):
                        queries.bind_plan(3, bad_role, None)
                    with self.assertRaises(ValueError):
                        queries.bind_plan(3, "adopted", bad_scenario)
                    with self.assertRaises(ValueError):
                        queries.entity("unknown", "PRIVATE-M1")
                self.assertEqual(list(conn.iterdump()), before)
            finally:
                conn.close()

    def test_missing_sources_and_missing_role_do_not_reselect_or_repair(self):
        with tempfile.TemporaryDirectory(prefix="aps-g-legacy-missing-") as directory:
            path = Path(directory) / "queries.db"
            prepare_database(path)
            conn = connect(path)
            try:
                conn.execute("PRAGMA query_only=ON")
                before = list(conn.iterdump())
                queries = LegacyNavigationQueries(conn)
                with queries.read_snapshot():
                    with self.assertRaises(LegacyNavigationSourceMissing):
                        queries.bind_plan(999, "adopted", None)
                    with self.assertRaises(LegacyNavigationSourceMissing):
                        queries.entity("machine", "missing")
                    binding = queries.bind_plan(1, "critical_best", None)
                    self.assertTrue(binding.fallback)
                    self.assertEqual(binding.locator, WorkbenchPlanLocator(1, "critical_best"))
                    self.assertEqual(binding.plan_ref, "")
                self.assertEqual(list(conn.iterdump()), before)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
