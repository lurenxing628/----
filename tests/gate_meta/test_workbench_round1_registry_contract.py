"""R1 registration preserves old targets and follows the real shared owners."""

import ast
from pathlib import Path

import pytest

from scripts import run_daily_quality_gate as daily
from tests.gate_meta.workbench_round1_registry_support import (
    CANDIDATE_V9_FIXTURE,
    CAPACITY_SOURCE_BINDING_ENV_KEYS,
    CAPACITY_SOURCE_BINDING_INPUTS,
    NEUTRAL_EXECUTION_FILES,
    NEUTRAL_PLAN_READ_FILES,
    ROUND1_ALGORITHM_TESTS,
    ROUND1_BROWSER_INPUTS,
    ROUND1_CANDIDATE_SCHEMA_TESTS,
    ROUND1_GATE_TESTS,
    ROUND1_INPUT_OWNERS,
    ROUND1_REQUIRED_FILES,
    ROUND1_SCANNER_SOURCES,
    ROUND1_SCANNER_TESTS,
    ROUND1_SERIAL_FILES,
    ROUND1_SUPPLEMENTAL_FILES,
    SNAPSHOT_REQUIRED_GROUPS,
    SNAPSHOT_SUPPLEMENTAL_GROUPS,
)
from tests.gate_meta.workbench_round1_registry_support import round1_targets as _round1_targets
from tools import long_gate_manifest, quality_gate_shared, test_registry
from tools.full_test_debt_shards import classify_nodeid, is_perf_nodeid
from tools.long_gate_fingerprint import fingerprint_entry, fingerprint_files
from tools.test_registry_groups_workbench import WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "tests/workbench/"


def _inventory(required):
    return (test_registry.iter_required_regression_groups() if required
            else WORKBENCH_SUPPLEMENTAL_REGRESSION_GROUPS)


def _extension_targets(required):
    files = ROUND1_REQUIRED_FILES if required else ROUND1_SUPPLEMENTAL_FILES
    paths = {PREFIX + name for names in files.values() for name in names}
    additions = (*ROUND1_GATE_TESTS, *ROUND1_ALGORITHM_TESTS, *ROUND1_SCANNER_TESTS, *ROUND1_CANDIDATE_SCHEMA_TESTS)
    return paths | set(additions) if required else paths


def _matches(group, source):
    return any(daily._path_matches_pattern(source, scope) for scope in group["input_file_scopes"])


@pytest.mark.parametrize("required,old_hash,new_count", (
    (True, "a29caf60dd21c94a53d26dd7f7cc7c07d932b4153b576e1b320411a6df3265ef", 582),
    (False, "ba009b4f3366b108382ba4057de05cb9b05fd2b8826776442b55266c309a9e6e", 85),
))
def test_round1_preserves_every_old_owner_and_target_order(required, old_hash, new_count):
    groups = _inventory(required)
    additions = _extension_targets(required)
    retained = [(group["group_id"], [path for path in _round1_targets(group) if path not in additions])
                for group in groups]
    assert test_registry.stable_registry_hash(retained) == old_hash
    targets = [path for group in groups for path in _round1_targets(group)]
    assert len(targets) == len(set(targets)) == new_count
    assert additions <= set(targets)
    if required:
        assert len(groups) == 33


@pytest.mark.parametrize("group_id,filenames,required", (
    *((key, names, True) for key, names in ROUND1_REQUIRED_FILES.items()),
    *((key, names, False) for key, names in ROUND1_SUPPLEMENTAL_FILES.items()),
))
def test_reviewed_files_append_to_exact_owner_without_promoting_browser(group_id, filenames, required):
    groups = _inventory(required)
    owner = next(group for group in groups if group["group_id"] == group_id)
    expected = [PREFIX + name for name in filenames]
    assert _round1_targets(owner)[-len(expected):] == expected
    for path in expected:
        assert [group["group_id"] for group in groups if path in group["target_paths"]] == [group_id]
        assert quality_gate_shared.quality_gate_required_test_nodeid_matches(path + "::test_contract") is required
        assert not is_perf_nodeid(path + "::test_contract")
        expected_shard = "serial" if Path(path).name in ROUND1_SERIAL_FILES else "parallel"
        assert classify_nodeid(path + "::test_contract") == expected_shard
        plan = daily._build_impact_plan(daily.ChangedPathSet([path], True, "round1"))
        assert not plan.all_required_groups, plan.reason
        assert (path in plan.target_paths) is required
        if required:
            assert group_id in plan.selected_group_ids


def test_explicit_piece_scope_algorithm_has_one_required_owner_and_real_source_scope():
    path, = ROUND1_ALGORITHM_TESTS
    source = "core/algorithms/greedy/dispatch/sgs.py"
    groups = _inventory(True)
    assert [group["group_id"] for group in groups if path in group["target_paths"]] == ["scheduler_run_core"]
    assert sum(path == target for target in test_registry.QUALITY_GATE_REQUIRED_TESTS) == 1
    assert test_registry.required_test_nodeid_matches(path + "::test_seed_end_times_require_explicit_piece_scope")
    assert all(path not in group["target_paths"] for group in _inventory(False))
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"), feature_version=(3, 8))
    assert any(isinstance(node, ast.FunctionDef) and node.name == "test_seed_end_times_require_explicit_piece_scope"
               for node in ast.walk(tree))
    owner = next(group for group in groups if group["group_id"] == "scheduler_run_core")
    assert _matches(owner, source)
    for changed in (path, source):
        plan = daily._build_impact_plan(daily.ChangedPathSet([changed], True, "round1-sgs"))
        assert not plan.all_required_groups, plan.reason
        assert "scheduler_run_core" in plan.selected_group_ids and path in plan.target_paths
    assert classify_nodeid(path + "::test_contract") == "parallel"
    assert not is_perf_nodeid(path + "::test_contract")


def test_candidate_schema_and_real_v9_fixture_keep_one_existing_required_owner():
    path, = ROUND1_CANDIDATE_SCHEMA_TESTS
    groups = _inventory(True)
    for target in (path, "tests/candidate/test_scheduler_candidate_persistence_contract.py"):
        assert [group["group_id"] for group in groups if target in group["target_paths"]] == ["scheduler_run_core"]
    owner = next(group for group in groups if group["group_id"] == "scheduler_run_core")
    assert _round1_targets(owner)[-1] == path
    assert sum(path == target for target in test_registry.QUALITY_GATE_REQUIRED_TESTS) == 1
    assert test_registry.required_test_nodeid_matches(path + "::test_candidate_schema_exists_in_fresh_database_with_expected_constraints")
    assert test_registry.required_test_nodeid_matches(path + "::test_candidate_schema_migration_keeps_candidate_tables_independent_from_schedule_history")
    assert (ROOT / path).is_file() and (ROOT / CANDIDATE_V9_FIXTURE).is_file()
    assert CANDIDATE_V9_FIXTURE in owner["input_file_scopes"]
    for group in (*groups, *_inventory(False)):
        assert CANDIDATE_V9_FIXTURE not in group["target_paths"]
    assert all(path not in group["target_paths"] for group in _inventory(False))
    for source in (path, CANDIDATE_V9_FIXTURE):
        plan = daily._build_impact_plan(daily.ChangedPathSet([source], True, "round1-candidate-schema"))
        assert not plan.all_required_groups, plan.reason
        assert "scheduler_run_core" in plan.selected_group_ids and path in plan.target_paths
        if source == CANDIDATE_V9_FIXTURE:
            assert plan.selected_group_ids == ["scheduler_run_core"]


def test_candidate_v9_fixture_content_invalidates_owner_and_required_parent(tmp_path):
    owner = next(group for group in _inventory(True) if group["group_id"] == "scheduler_run_core")
    manifest = long_gate_manifest.build_manifest_from_quality_gate_plan(
        quality_gate_shared.build_quality_gate_command_plan(), repo_root=str(tmp_path))
    parent = next(entry for entry in manifest["entries"] if entry["entry_id"] == "required_regressions")
    fixture = tmp_path / CANDIDATE_V9_FIXTURE
    fixture.parent.mkdir(parents=True)
    fixture.write_text("SELECT 9;\n", encoding="utf-8")
    before = [fingerprint_entry(entry, str(tmp_path))["hash"] for entry in (owner, parent)]
    fixture.write_text("SELECT 10;\n", encoding="utf-8")
    after = [fingerprint_entry(entry, str(tmp_path))["hash"] for entry in (owner, parent)]
    assert all(first != second for first, second in zip(before, after))


def test_candidate_v9_fixture_invalidates_real_full_execution_file_fingerprint(tmp_path):
    manifest = long_gate_manifest.build_manifest_from_quality_gate_plan(
        quality_gate_shared.build_quality_gate_command_plan(), repo_root=str(tmp_path))
    entry = next(row for row in manifest["entries"] if row["entry_id"] == "full_test_debt")
    assert CANDIDATE_V9_FIXTURE in entry["input_file_scopes"]
    fixture = tmp_path / CANDIDATE_V9_FIXTURE
    fixture.parent.mkdir(parents=True)
    fixture.write_text("SELECT 9;\n", encoding="utf-8")
    before = fingerprint_files(entry["input_file_scopes"], str(tmp_path))["content_hash"]
    fixture.write_text("SELECT 10;\n", encoding="utf-8")
    assert fingerprint_files(entry["input_file_scopes"], str(tmp_path))["content_hash"] != before


@pytest.mark.parametrize("source", ROUND1_SCANNER_SOURCES)
def test_import_resolver_has_existing_quality_gate_owner_and_registered_tool_scope(source):
    path, = ROUND1_SCANNER_TESTS
    groups = _inventory(True)
    assert [group["group_id"] for group in groups if path in group["target_paths"]] == ["quality_gate"]
    assert sum(path == target for target in test_registry.QUALITY_GATE_REQUIRED_TESTS) == 1
    assert test_registry.required_test_nodeid_matches(path + "::test_literal_bindings_preserve_aliases_scopes_and_contexts")
    assert all(path not in group["target_paths"] for group in _inventory(False))
    owner = next(group for group in groups if group["group_id"] == "quality_gate")
    assert _matches(owner, source)
    plan = daily._build_impact_plan(daily.ChangedPathSet([source], True, "round1-resolver"))
    assert "quality_gate" in plan.selected_group_ids and path in plan.target_paths
    assert plan.reason == "common quality gate scope changed: " + source
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"), feature_version=(3, 8))
    assert any(isinstance(node, ast.FunctionDef) and node.name.startswith("test_") for node in ast.walk(tree))


def test_shared_sqlite_snapshot_selects_only_actual_consumer_groups_without_fallback():
    source = "tests/_support/sqlite_snapshot.py"
    assert (ROOT / source).is_file()
    plan = daily._build_impact_plan(daily.ChangedPathSet([source], True, "round1-snapshot"))
    assert not plan.all_required_groups, plan.reason
    assert set(plan.selected_group_ids) == set(SNAPSHOT_REQUIRED_GROUPS)
    for required, expected in ((True, SNAPSHOT_REQUIRED_GROUPS), (False, SNAPSHOT_SUPPLEMENTAL_GROUPS)):
        groups = _inventory(required)
        assert {group["group_id"] for group in groups if _matches(group, source)} == set(expected)
        assert all(source not in group["target_paths"] for group in groups)
    tree = ast.parse((ROOT / source).read_text(encoding="utf-8"), feature_version=(3, 8))
    assert not any(isinstance(node, ast.FunctionDef) and node.name.startswith("test_") for node in ast.walk(tree))


@pytest.mark.parametrize("group_id", (*SNAPSHOT_REQUIRED_GROUPS, *SNAPSHOT_SUPPLEMENTAL_GROUPS))
def test_shared_sqlite_snapshot_changes_invalidate_each_consumer_fingerprint(tmp_path, group_id):
    group = next(row for row in (*_inventory(True), *_inventory(False)) if row["group_id"] == group_id)
    source = tmp_path / "tests/_support/sqlite_snapshot.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    before = fingerprint_entry(group, str(tmp_path))["hash"]
    source.write_text("VALUE = 2\n", encoding="utf-8")
    assert fingerprint_entry(group, str(tmp_path))["hash"] != before


@pytest.mark.parametrize("filename", NEUTRAL_EXECUTION_FILES)
@pytest.mark.parametrize("required", (True, False))
def test_neutral_execution_keeps_all_old_ledger_impact_owners(filename, required):
    source = "core/services/execution/" + filename
    assert (ROOT / source).is_file()
    groups = _inventory(required)
    original = {group["group_id"] for group in groups
                if _matches(group, "core/services/workbench/execution_ledger.py")}
    assert original
    selected = {group["group_id"] for group in groups if _matches(group, source)}
    assert original <= selected
    for group in groups:
        if group["group_id"] in original:
            assert _matches(group, source)
    if required:
        plan = daily._build_impact_plan(daily.ChangedPathSet([source], True, "round1"))
        assert not plan.all_required_groups, plan.reason
        assert original <= set(plan.selected_group_ids)


@pytest.mark.parametrize("filename", NEUTRAL_PLAN_READ_FILES)
@pytest.mark.parametrize("required", (True, False))
def test_shared_plan_reads_preserve_all_legacy_scheduler_impact_owners(filename, required):
    source = "core/services/common/" + filename
    assert (ROOT / source).is_file()
    groups = _inventory(required)
    original = {group["group_id"] for group in groups
                if _matches(group, "core/services/scheduler/schedule_plan_query_service.py")}
    assert original
    assert original <= {group["group_id"] for group in groups if _matches(group, source)}


@pytest.mark.parametrize("source,group_id", ROUND1_INPUT_OWNERS)
def test_round1_changed_sources_select_the_real_contract_owner(source, group_id):
    assert (ROOT / source).is_file()
    plan = daily._build_impact_plan(daily.ChangedPathSet([source], True, "round1"))
    assert not plan.all_required_groups, plan.reason
    assert group_id in plan.selected_group_ids
    owner = next(group for group in _inventory(True) if group["group_id"] == group_id)
    assert _matches(owner, source)
    assert set(owner["target_paths"]) <= set(plan.target_paths)


@pytest.mark.parametrize("source", (
    "tests/workbench/round1_field_piece_files_support.py",
    "tests/workbench/round1_field_piece_files_probe.py",
    "tests/workbench/round1_piece_point_support.py",
    "tests/gate_meta/workbench_round1_registry_support.py",
))
def test_support_and_browser_probe_are_real_inputs_never_test_targets(source):
    tree = ast.parse((ROOT / source).read_text(encoding="utf-8"), feature_version=(3, 8))
    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name.startswith("test_") for node in ast.walk(tree))
    for group in (*_inventory(True), *_inventory(False)):
        assert source not in group["target_paths"]
    assert not test_registry.required_test_nodeid_matches(source + "::test_placeholder")


@pytest.mark.parametrize("source", ROUND1_BROWSER_INPUTS)
def test_real_browser_helpers_remain_fingerprint_inputs_only(tmp_path, source):
    browser = next(group for group in _inventory(False) if group["group_id"] == "workbench_browser")
    assert source in browser["input_file_scopes"]
    path = tmp_path / source
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("before\n", encoding="utf-8")
    before = fingerprint_entry(browser, str(tmp_path))
    path.write_text("after\n", encoding="utf-8")
    assert before["hash"] != fingerprint_entry(browser, str(tmp_path))["hash"]


@pytest.mark.parametrize("source,group_id", (
    *ROUND1_INPUT_OWNERS,
    *(("core/services/execution/" + name, "workbench_execution_ledger") for name in NEUTRAL_EXECUTION_FILES),
    *(("core/services/common/" + name, "workbench_plans") for name in NEUTRAL_PLAN_READ_FILES),
    *((source, "quality_gate") for source in ROUND1_SCANNER_SOURCES),
))
def test_round1_source_changes_invalidate_owner_and_required_parent(tmp_path, source, group_id):
    owner = next(group for group in _inventory(True) if group["group_id"] == group_id)
    manifest = long_gate_manifest.build_manifest_from_quality_gate_plan(
        quality_gate_shared.build_quality_gate_command_plan(), repo_root=str(tmp_path))
    parent = next(entry for entry in manifest["entries"] if entry["entry_id"] == "required_regressions")
    path = tmp_path / source
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("before\n", encoding="utf-8")
    before = [fingerprint_entry(entry, str(tmp_path))["hash"] for entry in (owner, parent)]
    path.write_text("after\n", encoding="utf-8")
    after = [fingerprint_entry(entry, str(tmp_path))["hash"] for entry in (owner, parent)]
    assert all(old != new for old, new in zip(before, after))


def test_browser_entry_still_runs_real_browser_with_exact_download_oracle():
    source = (ROOT / (PREFIX + "test_round1_field_piece_files_browser.py")).read_text(encoding="utf-8")
    tree = ast.parse(source, feature_version=(3, 8))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert any(isinstance(node.func, ast.Name) and node.func.id == "runtime_tools" for node in calls)
    assert not any(isinstance(node.func, ast.Attribute) and node.func.attr in {"skip", "skipif", "xfail"}
                   for node in calls)
    script = (ROOT / ROUND1_BROWSER_INPUTS[0]).read_text(encoding="utf-8")
    assert "chromium.launch(" in script and "WORKBENCH_BROWSER" in script
    assert "'-m', 'tests.workbench.round1_field_piece_files_probe'" in script


@pytest.mark.parametrize("group_id", ("workbench_run_compute_capacity", "workbench_run_jobs_capacity"))
def test_capacity_source_binding_uses_exact_inputs_and_environment(group_id):
    owner = next(group for group in _inventory(False) if group["group_id"] == group_id)
    assert set(CAPACITY_SOURCE_BINDING_ENV_KEYS) <= set(owner["env_keys"])
    targets = {path for group in (*_inventory(True), *_inventory(False)) for path in group["target_paths"]}
    for source in CAPACITY_SOURCE_BINDING_INPUTS:
        assert (ROOT / source).is_file()
        assert source in owner["input_file_scopes"] and _matches(owner, source)
        assert source not in targets


@pytest.mark.parametrize("group_id", ("workbench_run_compute_capacity", "workbench_run_jobs_capacity"))
@pytest.mark.parametrize("source", CAPACITY_SOURCE_BINDING_INPUTS)
def test_capacity_source_binding_input_change_invalidates_owner(tmp_path, group_id, source):
    owner = next(group for group in _inventory(False) if group["group_id"] == group_id)
    path = tmp_path / source
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("before\n", encoding="utf-8")
    before = fingerprint_files(owner["input_file_scopes"], str(tmp_path))["content_hash"]
    path.write_text("after\n", encoding="utf-8")
    assert fingerprint_files(owner["input_file_scopes"], str(tmp_path))["content_hash"] != before


def test_capacity_source_binding_environment_stays_in_its_two_supplemental_owners():
    groups = (*_inventory(True), *_inventory(False))
    expected = ["workbench_run_compute_capacity", "workbench_run_jobs_capacity"]
    for key in CAPACITY_SOURCE_BINDING_ENV_KEYS:
        assert [group["group_id"] for group in groups if key in group["env_keys"]] == expected
