"""UI source contracts are required; real UI rendering remains opt-in."""

from collections import Counter

from scripts import run_daily_quality_gate as daily
from tests.gate_meta.workbench_round1_registry_support import UI_REQUIRED_TARGETS, UI_SUPPLEMENTAL_TARGETS
from tools import test_registry
from tools.long_gate_manifest_environment import registry_test_environment_keys
from tools.test_registry_groups_workbench import WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
from tools.test_registry_workbench_ui import WORKBENCH_UI_BROWSER_TARGETS, WORKBENCH_UI_REQUIRED_TESTS


def test_ui_source_contracts_have_one_required_owner():
    groups = test_registry.iter_required_regression_groups()
    group = next(row for row in groups if row["group_id"] == "workbench_ui_refinement")
    assert tuple(WORKBENCH_UI_REQUIRED_TESTS) == UI_REQUIRED_TARGETS
    assert tuple(group["target_paths"]) == UI_REQUIRED_TARGETS
    assert test_registry.iter_required_tests()[-len(UI_REQUIRED_TARGETS):] == list(UI_REQUIRED_TARGETS)
    for path in UI_REQUIRED_TARGETS:
        assert [row["group_id"] for row in groups if path in row["target_paths"]] == ["workbench_ui_refinement"]
    assert "frontend/workbench/app/styles/*.css" in group["input_file_scopes"]


def test_ui_real_browser_tools_are_not_required_by_default():
    required = set(test_registry.iter_required_tests())
    assert required.isdisjoint(UI_SUPPLEMENTAL_TARGETS)
    assert "tests/app_runtime/test_ui_browser_geometry_smoke.py" not in required


def test_ui_runtime_targets_append_once_without_changing_old_supplemental_owners():
    groups = test_registry.SUPPLEMENTAL_REGRESSION_GROUPS
    assert groups[:-1] == WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS
    assert groups[-1]["group_id"] == "workbench_ui_refinement_browser"
    assert tuple(groups[-1]["target_paths"]) == UI_SUPPLEMENTAL_TARGETS
    assert tuple(WORKBENCH_UI_BROWSER_TARGETS) == UI_SUPPLEMENTAL_TARGETS[:4]
    for path in UI_SUPPLEMENTAL_TARGETS:
        assert [row["group_id"] for row in groups if path in row["target_paths"]] == ["workbench_ui_refinement_browser"]


def test_ui_complete_inventory_preserves_raw_duplicate_and_coverage_guards():
    groups = (*test_registry.REQUIRED_REGRESSION_GROUPS, *test_registry.SUPPLEMENTAL_REGRESSION_GROUPS)
    assert len({row["group_id"] for row in groups}) == len(groups)
    counts = Counter(path for row in groups for path in row["target_paths"])
    assert all(count == 1 for count in counts.values())
    supplemental = test_registry.SUPPLEMENTAL_REGRESSION_GROUPS
    paths = [path for row in supplemental for path in row["target_paths"]]
    coverage = test_registry.validate_required_regression_group_coverage(paths, supplemental)
    assert coverage["missing"] == coverage["unknown"] == coverage["duplicates"] == []


def test_ui_runtime_environment_uses_real_aggregate_consumer():
    group = test_registry.SUPPLEMENTAL_REGRESSION_GROUPS[-1]
    assert {"node_executable_realpath", "node_version"} <= set(group["env_keys"])
    assert "PATH" not in group["env_keys"]
    for path in UI_SUPPLEMENTAL_TARGETS:
        keys = registry_test_environment_keys([path])
        assert {"WORKBENCH_NODE", "WORKBENCH_BROWSER", "NODE_PATH", "NODE_OPTIONS"} <= set(keys)
    assert "WORKBENCH_BROWSER" not in registry_test_environment_keys([UI_REQUIRED_TARGETS[1]])


def test_ui_runtime_fixtures_and_dynamic_app_inputs_remain_scoped_without_becoming_targets():
    group = test_registry.SUPPLEMENTAL_REGRESSION_GROUPS[-1]
    for source in (
        "tests/workbench/dirty_guard_fixture.jsx", "tests/workbench/plan_ui_browser_harness.cjs",
        "tests/workbench/plan_ui_fixtures.cjs", "tests/workbench/run_candidate_support.py",
        "tests/workbench/wbui_gantt_display_format.cjs",
        "tests/workbench/run_compute_support.py", "tests/workbench/dashboard_support.py",
        "tests/workbench/live_environment.py", "tests/workbench/fixtures/schema-v28.sql",
        "tests/_support/excel_templates.py", "schema.sql", "app.py", "config.py",
        "web/bootstrap/static_versioning.py", "web/routes/workbench/navigation_metadata.py",
        "plugins/example.py", "scripts/workbench/ds-projection.cjs",
        "frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js",
        "static/workbench/asset-manifest.json", "static/workbench/vendor/react-18.3.1.production.min.js",
    ):
        assert daily._path_matches_any(source, group["input_file_scopes"]), source
        assert source not in group["target_paths"]
    assert {"APS_SYSTEM_JOURNAL_DIR", "APS_STATIC_VERSION"} <= set(group["env_keys"])
    assert {"DASHBOARD_DETAIL_UI_OUTPUT", "WORKBENCH_DASHBOARD_DETAIL_ONLY", "TZ"}.isdisjoint(group["env_keys"])
