"""Type, immutability and serialization contracts for summary build context."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import MISSING, FrozenInstanceError, fields, replace
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Union, get_type_hints

import pytest

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.services.common.build_outcome import BuildOutcome
from core.services.scheduler.contracts.schedule_summary_types import SummaryBuildContext, SummaryMetrics
from core.services.scheduler.summary.schedule_summary import serialize_end_date
from core.services.scheduler.summary.schedule_summary_assembly import _finish_time_by_batch, _positive_result_op_ids
from core.services.scheduler.summary.summary_runtime_state import _build_runtime_state
from core.services.scheduler.summary.summary_visible_degradation import safe_metrics_dict

_ROOT = Path(__file__).resolve().parents[3]
_ANNOTATIONS = {
    "cfg": "Any",
    "version": "int",
    "normalized_batch_ids": "List[str]",
    "start_dt": "datetime",
    "end_date": "Optional[Union[date, str]]",
    "batches": "Dict[str, Batch]",
    "operations": "List[BatchOperation]",
    "results": "List[ScheduleResult]",
    "summary": "Optional[ScheduleSummary]",
    "used_strategy": "SortStrategy",
    "used_params": "Dict[str, Any]",
    "algo_mode": "str",
    "objective_name": "str",
    "time_budget_seconds": "int",
    "best_score": "Optional[Tuple[float, ...]]",
    "best_metrics": "Optional[SummaryMetrics]",
    "best_order": "List[str]",
    "attempts": "List[Dict[str, Any]]",
    "improvement_trace": "List[Dict[str, Any]]",
    "frozen_op_ids": "Set[int]",
    "search_report": "Dict[str, Any]",
    "missing_internal_resource_op_ids": "Optional[Set[int]]",
    "scheduled_op_ids": "Optional[Set[int]]",
    "freeze_meta": "Optional[Dict[str, Any]]",
    "input_build_outcome": "Optional[BuildOutcome[List[Any]]]",
    "downtime_meta": "Optional[Dict[str, Any]]",
    "resource_pool_meta": "Optional[Dict[str, Any]]",
    "readiness_gate_enabled": "bool",
    "algo_stats": "Optional[Dict[str, Any]]",
    "algo_warnings": "Optional[List[str]]",
    "warning_merge_status": "Optional[Dict[str, Any]]",
    "graph_analysis_public": "Optional[Dict[str, Any]]",
    "graph_analysis_diagnostics": "Optional[Dict[str, Any]]",
    "candidate_comparison_public": "Optional[Dict[str, Any]]",
    "execution_snapshot_revision": "Optional[str]",
    "execution_snapshot_op_ids": "Optional[List[int]]",
    "execution_snapshot_op_count": "int",
    "simulate": "bool",
    "t0": "float",
}


class _MinimalMetrics:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload

    def to_dict(self) -> Dict[str, Any]:
        return self.payload


def _context() -> SummaryBuildContext:
    return SummaryBuildContext(
        cfg={},
        version=1,
        normalized_batch_ids=["B"],
        start_dt=datetime(2026, 2, 1),
        end_date=None,
        batches={"B": Batch("B", "P")},
        operations=[BatchOperation(1, "OP", "B")],
        results=[ScheduleResult(1, "OP", "B", 1, end_time=datetime(2026, 2, 2))],
        summary=ScheduleSummary(True, 1, 1, 0, [], [], 0.0),
        used_strategy=SortStrategy.PRIORITY_FIRST,
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=1,
        best_score=None,
        best_metrics=_MinimalMetrics({"overdue_count": 0}),
        best_order=["B"],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
    )


def test_annotations_resolve_to_existing_domain_types() -> None:
    assert SummaryBuildContext.__annotations__ == _ANNOTATIONS
    hints = get_type_hints(SummaryBuildContext)
    expected = {
        "end_date": Optional[Union[date, str]],
        "batches": Dict[str, Batch],
        "operations": List[BatchOperation],
        "results": List[ScheduleResult],
        "summary": Optional[ScheduleSummary],
        "used_strategy": SortStrategy,
        "best_metrics": Optional[SummaryMetrics],
        "input_build_outcome": Optional[BuildOutcome[List[Any]]],
    }
    assert {name: hints[name] for name in expected} == expected
    runtime_hints = get_type_hints(_build_runtime_state)
    for name in ("batches", "results", "summary", "best_metrics"):
        assert runtime_hints[name] == hints[name]
    assert get_type_hints(_finish_time_by_batch)["results"] == hints["results"]
    assert get_type_hints(_positive_result_op_ids)["results"] == hints["results"]


def test_dataclass_shape_defaults_and_identity_are_preserved() -> None:
    context_fields = fields(SummaryBuildContext)
    assert tuple(item.name for item in context_fields) == tuple(_ANNOTATIONS)
    assert all(item.default is MISSING and item.default_factory is MISSING for item in context_fields[:20])
    assert context_fields[20].default_factory is dict
    defaults = {item.name: item.default for item in context_fields[21:]}
    expected_defaults = dict.fromkeys(tuple(_ANNOTATIONS)[21:])
    expected_defaults.update(readiness_gate_enabled=False, execution_snapshot_op_count=0, simulate=False, t0=0.0)
    assert defaults == expected_defaults
    ctx = _context()
    new_cfg = SimpleNamespace()
    rebound = replace(ctx, cfg=new_cfg)
    assert rebound.cfg is new_cfg
    for name in _ANNOTATIONS:
        if name != "cfg":
            assert getattr(rebound, name) is getattr(ctx, name)
    assert ctx.search_report is not _context().search_report
    with pytest.raises(FrozenInstanceError):
        setattr(ctx, "version", 2)
    assert "__post_init__" not in SummaryBuildContext.__dict__


@pytest.mark.parametrize("end_date", [None, date(2026, 2, 10), "2026-02-10", datetime(2026, 2, 10, 8)])
def test_end_date_is_retained_without_coercion(end_date: Optional[Union[date, str]]) -> None:
    ctx = replace(_context(), end_date=end_date)
    assert ctx.end_date is end_date
    expected = end_date.isoformat() if isinstance(end_date, date) else end_date
    assert serialize_end_date(ctx.end_date) == expected


def test_metrics_protocol_preserves_optional_diagnostics_and_payload() -> None:
    ctx = _context()
    assert ctx.best_metrics is not None
    payload = ctx.best_metrics.to_dict()
    metrics_dict, metrics_state = safe_metrics_dict(ctx.best_metrics)
    assert metrics_dict == payload
    assert not metrics_state
    runtime = _build_runtime_state(
        svc=SimpleNamespace(_normalize_text=lambda value: str(value or "")),
        batches=ctx.batches,
        results=ctx.results,
        summary=ctx.summary,
        best_metrics=ctx.best_metrics,
    )
    assert runtime.finish_by_batch == {"B": datetime(2026, 2, 2)}
    assert runtime.invalid_due_count == runtime.unscheduled_batch_count == 0
    assert _positive_result_op_ids(ctx.results) == {1}
    assert ctx.best_metrics.to_dict() is payload
    assert type(ctx.batches) is type(ctx.used_params) is dict


def test_contract_import_has_no_reverse_business_dependency() -> None:
    module_name = "core.services.scheduler.contracts.schedule_summary_types"
    forbidden = (
        "core.algorithms",
        "core.services.scheduler.config",
        "core.services.scheduler.run",
        "core.services.scheduler.summary",
    )
    source = (_ROOT / "core/services/scheduler/contracts/schedule_summary_types.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        names = (
            [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else ([alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
        )
        assert not any(name == prefix or name.startswith(prefix + ".") for name in names for prefix in forbidden)
    code = (
        f"import importlib, json, sys; importlib.import_module({module_name!r}); "
        f"print(json.dumps([n for n in sys.modules if any(n == p or n.startswith(p + '.') for p in {forbidden!r})]))"
    )
    completed = subprocess.run([sys.executable, "-c", code], cwd=str(_ROOT), capture_output=True, text=True, check=True)
    assert json.loads(completed.stdout) == []


def test_pyright_accepts_domain_and_protocol_but_rejects_wrong_fields(tmp_path: Path) -> None:
    imports = """from datetime import date, datetime
from typing import Any, Dict
from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.algorithms.evaluation import ScheduleMetrics
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.services.common.build_outcome import BuildOutcome
from core.services.scheduler.contracts.schedule_summary_types import SummaryBuildContext, SummaryMetrics

class MinimalMetrics:
    def to_dict(self) -> Dict[str, Any]:
        return {}

real_metrics: SummaryMetrics = ScheduleMetrics(0, 0.0, 0.0, 0)
minimal_metrics: SummaryMetrics = MinimalMetrics()
"""
    values = {
        "cfg": "{}",
        "version": "1",
        "normalized_batch_ids": "['B']",
        "start_dt": "datetime(2026, 2, 1)",
        "end_date": "date(2026, 2, 10)",
        "batches": "{'B': Batch('B', 'P')}",
        "operations": "[BatchOperation(1, 'OP', 'B')]",
        "results": "[ScheduleResult(1, 'OP', 'B', 1)]",
        "summary": "ScheduleSummary(True, 1, 1, 0, [], [], 0.0)",
        "used_strategy": "SortStrategy.PRIORITY_FIRST",
        "used_params": "{}",
        "algo_mode": "'greedy'",
        "objective_name": "'min_overdue'",
        "time_budget_seconds": "1",
        "best_score": "None",
        "best_metrics": "real_metrics",
        "best_order": "['B']",
        "attempts": "[]",
        "improvement_trace": "[]",
        "frozen_op_ids": "set()",
        "input_build_outcome": "BuildOutcome([])",
    }

    def constructor(name: str, overrides: Dict[str, str]) -> str:
        args = dict(values, **overrides)
        return (
            f"\ndef {name}() -> SummaryBuildContext:\n    return SummaryBuildContext(\n"
            + "".join(f"        {key}={value},\n" for key, value in args.items())
            + "    )\n"
        )

    source = (
        imports
        + constructor("valid", {})
        + constructor(
            "valid_partial",
            {
                "end_date": "'2026-02-10'",
                "summary": "None",
                "best_metrics": "minimal_metrics",
            },
        )
    )
    invalid = {
        "end_date": "123",
        "batches": "{'B': 1}",
        "operations": "[1]",
        "results": "[1]",
        "summary": "1",
        "used_strategy": "'priority_first'",
        "best_metrics": "object()",
        "input_build_outcome": "BuildOutcome(1)",
    }
    for name, value in invalid.items():
        source += constructor("invalid_" + name, {name: value})
    fixture = tmp_path / "u01_typing_cases.py"
    fixture.write_text(source, encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pyright",
            "-p",
            str(_ROOT / "pyrightconfig.gate.json"),
            "--pythonversion",
            "3.8",
            "--outputjson",
            str(fixture),
        ],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 1, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    errors = [item for item in report["generalDiagnostics"] if item["severity"] == "error"]
    assert len(errors) == len(invalid), errors
    for name in invalid:
        assert any(f'parameter "{name}"' in item["message"] for item in errors), errors
    assert all(item["file"] == str(fixture) and item["rule"] == "reportArgumentType" for item in errors)
