"""Real lazy scheduler exports keep identity and cold-import behavior."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "core.services.scheduler"
WRAPPER = PACKAGE + ".schedule_orchestrator"
EXPECTED: Dict[str, Dict[str, str]] = {
    PACKAGE: {
        "BatchService": PACKAGE + ".batch_service",
        "CalendarService": PACKAGE + ".calendar_service",
        "ConfigService": PACKAGE + ".config.config_service",
        "GanttAdjustmentDraftService": PACKAGE + ".gantt_adjustment_draft_service",
        "GanttAdjustmentScenarioService": PACKAGE + ".gantt_adjustment_scenario_service",
        "GanttAdjustmentPublishService": PACKAGE + ".gantt_adjustment_publish_service",
        "GanttAdjustmentValidationService": PACKAGE + ".gantt_adjustment_validation_service",
        "GanttService": PACKAGE + ".gantt_service",
        "OperationExecutionFeedbackService": PACKAGE + ".operation_execution_feedback_service",
        "ResourceDispatchActualRecordService": PACKAGE + ".resource_dispatch_actual_record_service",
        "ResourceDispatchExecutionService": PACKAGE + ".resource_dispatch_execution_service",
        "ResourceDispatchService": PACKAGE + ".resource_dispatch_service",
        "ScheduleService": PACKAGE + ".schedule_service",
    },
    WRAPPER: {
        "ScheduleOrchestrationOutcome": PACKAGE + ".run.schedule_orchestrator",
        "orchestrate_schedule_run": PACKAGE + ".run.schedule_orchestrator",
    },
}
CASES = [(module, name, target) for module, exports in EXPECTED.items() for name, target in exports.items()]
SOURCES = {
    PACKAGE: ROOT / "core/services/scheduler/__init__.py",
    WRAPPER: ROOT / "core/services/scheduler/schedule_orchestrator.py",
}

PROBE = r'''
import importlib
import json
import sys
from pathlib import Path

request = json.loads(sys.argv[1])
root = Path(request["root"]).resolve()
module_name = request["module"]
expected = request["expected"]
mode = request["mode"]

def real_module(name):
    module = importlib.import_module(name)
    module_file = Path(module.__file__).resolve()
    wanted = root.joinpath(*name.split("."))
    allowed = {wanted.with_suffix(".py"), wanted / "__init__.py"}
    assert module_file in allowed, (name, str(module_file), sorted(str(p) for p in allowed))
    return module

def unknown_is_rejected(module):
    try:
        getattr(module, "MissingSchedulerFinalExport")
    except AttributeError:
        return
    raise AssertionError("Unknown scheduler export was accepted")

if mode == "leaf_first":
    target = real_module(request["target"])
module = real_module(module_name)
assert tuple(module.__all__) == tuple(expected), module.__all__
unknown_is_rejected(module)

if mode == "passive":
    assert all(target not in sys.modules for target in expected.values()), sorted(sys.modules)
    assert all(name not in vars(module) for name in expected), sorted(vars(module))
    if module_name.endswith("schedule_orchestrator"):
        assert set(expected).issubset(dir(module))
    result = {"passive": True, "exports": list(expected), "unknown_rejected": True}
else:
    name = request["export"]
    if mode == "package_first":
        assert request["target"] not in sys.modules, request["target"]
        assert name not in vars(module), name
    namespace = {}
    exec("from " + module_name + " import " + name, namespace)
    target = real_module(request["target"])
    value = getattr(target, name)
    assert namespace[name] is value
    assert getattr(module, name) is value
    assert getattr(module, name) is value
    if module_name == "core.services.scheduler":
        assert vars(module)[name] is value
    else:
        assert name not in vars(module), "Compatibility wrapper unexpectedly cached the target"
    unknown_is_rejected(module)
    result = {"identity": True, "module": module_name, "export": name,
              "target": request["target"], "order": mode, "unknown_rejected": True}
print(json.dumps(result, sort_keys=True))
'''


def run_probe(tmp_path: Path, mode: str, module: str, name: str = "", target: str = "") -> Dict[str, Any]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("APS_")}
    env.update({
        "APS_ENV": "development",
        "APS_SHARED_DATA_ROOT": str(tmp_path / "runtime"),
        "APS_DB_PATH": str(tmp_path / "runtime/db/unused.db"),
        "APS_LOG_DIR": str(tmp_path / "runtime/logs"),
        "APS_BACKUP_DIR": str(tmp_path / "runtime/backups"),
        "APS_EXCEL_TEMPLATE_DIR": str(tmp_path / "runtime/templates"),
        "APS_SYSTEM_JOURNAL_DIR": str(tmp_path / "runtime/journal"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(tmp_path / "pycache"),
        "PYTHONPATH": str(ROOT),
    })
    request = {"root": str(ROOT), "module": module, "expected": EXPECTED[module],
               "mode": mode, "export": name, "target": target}
    completed = subprocess.run(
        [sys.executable, "-B", "-c", PROBE, json.dumps(request)],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    payload = json.loads(completed.stdout)
    assert isinstance(payload, dict)
    return payload


@pytest.mark.parametrize("module", (PACKAGE, WRAPPER))
def test_typechecking_declarations_match_all_real_lazy_exports(module):
    tree = ast.parse(SOURCES[module].read_text(encoding="utf-8"))
    declarations = {}
    for statement in tree.body:
        if not (isinstance(statement, ast.If) and isinstance(statement.test, ast.Name)
                and statement.test.id == "TYPE_CHECKING"):
            continue
        for node in statement.body:
            assert isinstance(node, ast.ImportFrom)
            package = PACKAGE
            target = importlib.util.resolve_name("." * node.level + str(node.module or ""), package)
            for alias in node.names:
                assert alias.asname in (None, alias.name)
                assert alias.name not in declarations
                declarations[alias.name] = target
    assert declarations == EXPECTED[module]


@pytest.mark.parametrize("module", (PACKAGE, WRAPPER))
def test_fresh_package_import_stays_passive_and_rejects_unknown(tmp_path, module):
    result = run_probe(tmp_path, "passive", module)
    assert result["passive"] is True and result["unknown_rejected"] is True
    assert result["exports"] == list(EXPECTED[module])


@pytest.mark.parametrize("module,name,target", CASES)
@pytest.mark.parametrize("order", ("package_first", "leaf_first"))
def test_fresh_import_orders_keep_every_real_export_identity(tmp_path, module, name, target, order):
    result = run_probe(tmp_path, order, module, name, target)
    assert result["identity"] is True and result["unknown_rejected"] is True
    assert (result["module"], result["export"], result["target"], result["order"]) == (module, name, target, order)


def test_final_lazy_export_guard_has_one_required_owner():
    from tools import quality_gate_shared, test_registry

    target = "tests/gate_meta/test_scheduler_lazy_exports_final.py"
    groups = test_registry.iter_required_regression_groups()
    assert [row["group_id"] for row in groups if target in row["target_paths"]] == ["scheduler_run_core"]
    assert test_registry.iter_required_tests().count(target) == 1
    assert quality_gate_shared.quality_gate_required_test_nodeid_matches(target + "::test_contract")
