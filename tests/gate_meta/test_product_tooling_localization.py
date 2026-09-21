"""Shared tooling must run from a checkout without personal workflow files."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from tests._support.paths import REPO_ROOT
from tools.quality_gate_shared import QUALITY_GATE_TOOL_PATHS
from tools.scan_aps_three_gap_py38_scope import is_aps_py38_scope_path
from tools.test_registry_groups_scheduler import SCHEDULER_REQUIRED_REGRESSION_GROUPS

PRIVATE_ROOTS = (".codestable", ".limcode", ".codex", ".cursor")


def test_quality_tools_are_present_without_private_workflow_paths():
    for relative in QUALITY_GATE_TOOL_PATHS:
        assert Path(relative).parts[0] not in PRIVATE_ROOTS, relative
        assert (REPO_ROOT / relative).is_file(), relative


def test_shared_regression_inputs_do_not_scan_local_workflows():
    for group in SCHEDULER_REQUIRED_REGRESSION_GROUPS:
        for key in ("input_file_scopes", "tool_file_scopes", "config_file_scopes"):
            for pattern in group.get(key, ()):
                assert Path(pattern).parts[0] not in PRIVATE_ROOTS, (group["group_id"], pattern)


def _load(relative, monkeypatch):
    name = "localization_" + Path(relative).stem
    spec = importlib.util.spec_from_file_location(name, str(REPO_ROOT / relative))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("relative,lookup", [
    ("scripts/run_start_and_rerun_route.py", "_find_repo_root"),
    ("scripts/run_full_selftest.py", "_find_repo_root"),
    ("scripts/post_change_check.py", "find_repo_root"),
])
def test_relocated_operational_scripts_resolve_their_own_checkout(relative, lookup, monkeypatch):
    module = _load(relative, monkeypatch)
    assert Path(getattr(module, lookup)()).resolve() == REPO_ROOT.resolve()


def test_callgraph_root_and_default_output_are_checkout_local(monkeypatch):
    monkeypatch.delenv("CHECKUP_CALLGRAPH", raising=False)
    monkeypatch.syspath_prepend(str(REPO_ROOT / "tools" / "checkup"))
    module = _load("tools/checkup/callgraph_extract.py", monkeypatch)
    assert Path(module.REPO_ROOT).resolve() == REPO_ROOT.resolve()
    assert Path(module.OUT_DIR) == REPO_ROOT / ".cache" / "aps-analysis" / "callgraph"


def test_migrated_build_and_gate_tools_remain_python38_inputs():
    for name in ("tools/checkup/callgraph_extract.py", "tools/document_metadata/validate-yaml.py",
                 "scripts/run_full_selftest.py", "scripts/run_start_and_rerun_route.py"):
        assert is_aps_py38_scope_path(name), name


def test_frozen_contract_ledgers_use_a_shared_capability_pointer():
    folder = REPO_ROOT / "tests" / "fixtures" / "workbench_contracts"
    for name, key in (("acceptance-master/actions.json", "planning_path"),
                      ("acceptance-planning/action-inventory.json", "source_inventory")):
        value = json.loads((folder / name).read_text(encoding="utf-8"))
        assert value[key] == "tests/fixtures/workbench_contracts/workbench-capabilities.json"
        assert (REPO_ROOT / value[key]).is_file()


def test_full_selftest_plan_uses_current_suite_and_checks_missing_guards(tmp_path, monkeypatch):
    module = _load("scripts/run_full_selftest.py", monkeypatch)
    monkeypatch.setattr(module, "_resolve_pytest_python", lambda *_args: sys.executable)
    plan = module._build_steps(REPO_ROOT, complex_repeat=2)
    assert len(plan) == 2
    assert plan[0][1][-3:] == ["-m", "not perf", "tests"]
    assert plan[1][1][-1] == "tests/excel_data_io"
    with pytest.raises(RuntimeError, match="Required self-test sources are missing"):
        module._build_steps(tmp_path, complex_repeat=1)
    with pytest.raises(ValueError, match="at least 1"):
        module._build_steps(REPO_ROOT, complex_repeat=0)
