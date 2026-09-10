"""Shared fixtures must not depend on collected test modules."""

from __future__ import annotations

import ast
import subprocess
import sys

from tests._support import gantt_scenario
from tests._support import resource_dispatch_frontend_support as canonical_resource
from tests._support.dependency_boundaries import assert_import_orders
from tests._support.paths import REPO_ROOT
from tests.gantt import test_gantt_draft_save_and_preview as legacy_gantt
from tests.resource_dispatch import resource_dispatch_frontend_support as legacy_resource


def test_moved_test_helpers_keep_old_identities_and_import_orders():
    pairs = (
        (legacy_gantt, gantt_scenario, ("_connect", "_seed_base", "_draft_with_change", "_build_app", "VERSION", "SCHEMA_PATH")),
        (legacy_resource, canonical_resource, ("resource_dispatch_script_paths", "resource_dispatch_script_tags", "read_resource_dispatch_script_bundle", "extract_js_function", "RESOURCE_DISPATCH_TEMPLATE")),
    )
    for old, new, names in pairs:
        for name in names:
            assert getattr(old, name) is getattr(new, name)
        assert_import_orders(old.__name__, new.__name__, names)


def test_fixture_imports_do_not_load_collected_tests():
    script = """
import sys
from tests._support import gantt_scenario, resource_dispatch_frontend_support
assert 'tests.gantt.test_gantt_draft_save_and_preview' not in sys.modules
assert 'tests.resource_dispatch.resource_dispatch_frontend_support' not in sys.modules
assert 'app' not in sys.modules
"""
    completed = subprocess.run([sys.executable, "-c", script], cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    for module in (gantt_scenario, canonical_resource):
        for node in ast.walk(ast.parse(REPO_ROOT.joinpath(module.__file__).read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("tests."):
                assert node.module.startswith("tests._support."), (module.__name__, node.lineno)


def test_scenario_seed_and_draft_data_unchanged(tmp_path):
    conn = gantt_scenario._connect(tmp_path)
    try:
        gantt_scenario._seed_base(conn)
        rows = conn.execute("SELECT id, op_id, version FROM Schedule ORDER BY id").fetchall()
        assert [tuple(row) for row in rows] == [(70, 10, 5), (80, 20, 5), (90, 30, 5)]
        draft_id = gantt_scenario._draft_with_change(conn)
        assert conn.execute("SELECT base_version FROM ScheduleAdjustmentDraft WHERE draft_id=?", (draft_id,)).fetchone()[0] == 5
        assert [tuple(row) for row in conn.execute("SELECT id, op_id, version FROM Schedule ORDER BY id")] == [tuple(row) for row in rows]
    finally:
        conn.close()
