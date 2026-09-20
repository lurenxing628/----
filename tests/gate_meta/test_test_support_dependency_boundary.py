"""Shared fixtures must not depend on collected test modules."""

from __future__ import annotations

import ast
import subprocess
import sys

from tests._support import gantt_scenario
from tests._support import resource_dispatch_frontend_support as canonical_resource
from tests._support.dependency_boundaries import assert_import_orders
from tests._support.paths import REPO_ROOT
from tests.resource_dispatch import resource_dispatch_frontend_support as legacy_resource


def test_moved_test_helpers_keep_old_identities_and_import_orders():
    names = ("resource_dispatch_script_paths", "resource_dispatch_script_tags", "read_resource_dispatch_script_bundle", "extract_js_function", "RESOURCE_DISPATCH_TEMPLATE")
    for name in names:
        assert getattr(legacy_resource, name) is getattr(canonical_resource, name)
    assert_import_orders(legacy_resource.__name__, canonical_resource.__name__, names)


def test_fixture_imports_do_not_load_collected_tests():
    script = """
import sys
from tests._support import gantt_scenario, resource_dispatch_frontend_support
assert not [name for name in sys.modules if name.startswith('tests.') and '.test_' in name], sorted(sys.modules)
assert 'tests.resource_dispatch.resource_dispatch_frontend_support' not in sys.modules
assert 'app' not in sys.modules
"""
    completed = subprocess.run([sys.executable, "-c", script], cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    for module in (gantt_scenario, canonical_resource):
        for node in ast.walk(ast.parse(REPO_ROOT.joinpath(module.__file__).read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("tests."):
                assert node.module.startswith("tests._support."), (module.__name__, node.lineno)


def test_scenario_seed_data_unchanged(tmp_path):
    conn = gantt_scenario._connect(tmp_path)
    try:
        gantt_scenario._seed_base(conn)
        rows = conn.execute("SELECT id, op_id, version FROM Schedule ORDER BY id").fetchall()
        assert [tuple(row) for row in rows] == [(70, 10, 5), (80, 20, 5), (90, 30, 5)]
        scenario = gantt_scenario._saved_scenario(conn)
        assert (scenario.scenario_id, scenario.base_version, scenario.base_plan_role, scenario.base_source_table) == (
            gantt_scenario.SCENARIO_ID, 5, "adopted", "schedule")
        assert (scenario.status, scenario.validation_status, scenario.row_count) == ("active", "valid", 3)
        scenario_rows = conn.execute(
            "SELECT source_row_id, op_id, start_time, end_time, is_changed FROM ScheduleAdjustmentScenarioRow "
            "WHERE scenario_id = ? ORDER BY id", (scenario.scenario_id,)).fetchall()
        assert [tuple(row) for row in scenario_rows] == [
            (70, 10, "2026-05-04 08:00:00", "2026-05-04 09:00:00", "no"),
            (90, 30, "2026-05-04 11:00:00", "2026-05-04 12:00:00", "yes"),
            (80, 20, "2026-05-04 10:00:00", "2026-05-04 11:00:00", "no"),
        ]
        assert [tuple(row) for row in conn.execute("SELECT id, op_id, version FROM Schedule ORDER BY id")] == [tuple(row) for row in rows]
    finally:
        conn.close()
