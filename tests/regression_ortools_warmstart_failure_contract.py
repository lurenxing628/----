from __future__ import annotations

import builtins
import sys
from datetime import datetime
from types import ModuleType, SimpleNamespace

import pytest


class _FakeExpr:
    def __add__(self, other):
        return _FakeExpr()

    __radd__ = __add__

    def __sub__(self, other):
        return _FakeExpr()

    def __rsub__(self, other):
        return _FakeExpr()

    def __ge__(self, other):
        return _FakeExpr()

    def __mul__(self, other):
        return _FakeExpr()

    __rmul__ = __mul__


class _FakeVar(_FakeExpr):
    pass


class _FakeCpModel:
    def NewIntVar(self, lb, ub, name):
        return _FakeVar()

    def NewIntervalVar(self, start, duration, end, name):
        return (start, duration, end, name)

    def Add(self, constraint):
        return None

    def AddNoOverlap(self, intervals):
        return None

    def Minimize(self, objective):
        return None


def _install_fake_cp_model(monkeypatch, *, status: int) -> None:
    cp_model = ModuleType("ortools.sat.python.cp_model")
    cp_model.CpModel = _FakeCpModel
    cp_model.OPTIMAL = 4
    cp_model.FEASIBLE = 2
    cp_model.MODEL_INVALID = 1
    cp_model.INFEASIBLE = 3
    cp_model.UNKNOWN = 0

    class _FakeCpSolver:
        def __init__(self):
            self.parameters = SimpleNamespace()

        def Solve(self, model):
            return int(status)

        def Value(self, var):
            return 0

    cp_model.CpSolver = _FakeCpSolver

    ortools = ModuleType("ortools")
    sat = ModuleType("ortools.sat")
    python = ModuleType("ortools.sat.python")
    python.cp_model = cp_model
    sat.python = python
    ortools.sat = sat

    monkeypatch.setitem(sys.modules, "ortools", ortools)
    monkeypatch.setitem(sys.modules, "ortools.sat", sat)
    monkeypatch.setitem(sys.modules, "ortools.sat.python", python)
    monkeypatch.setitem(sys.modules, "ortools.sat.python.cp_model", cp_model)


def _sample_inputs():
    batches = {
        "B1": SimpleNamespace(batch_id="B1", priority="normal", due_date="2026-01-01", quantity=1),
        "B2": SimpleNamespace(batch_id="B2", priority="normal", due_date="2026-01-02", quantity=1),
    }
    operations = [
        SimpleNamespace(id=1, batch_id="B1", source="internal", op_type_id="OT1", setup_hours=1.0, unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B2", source="internal", op_type_id="OT1", setup_hours=2.0, unit_hours=0.0),
    ]
    return operations, batches


def test_ortools_import_failure_is_visible(monkeypatch):
    from core.algorithms.ortools_bottleneck import OrtoolsWarmstartError, try_solve_bottleneck_batch_order

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if str(name).startswith("ortools"):
            raise ImportError("ortools missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)
    operations, batches = _sample_inputs()

    with pytest.raises(OrtoolsWarmstartError, match="依赖加载失败"):
        try_solve_bottleneck_batch_order(
            operations=operations,
            batches=batches,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            logger=None,
        )


def test_ortools_model_invalid_is_visible(monkeypatch):
    from core.algorithms.ortools_bottleneck import OrtoolsWarmstartError, try_solve_bottleneck_batch_order

    _install_fake_cp_model(monkeypatch, status=1)
    operations, batches = _sample_inputs()

    with pytest.raises(OrtoolsWarmstartError, match="模型不可用"):
        try_solve_bottleneck_batch_order(
            operations=operations,
            batches=batches,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            logger=None,
        )


def test_ortools_nonfinite_hours_is_visible(monkeypatch):
    from core.algorithms.ortools_bottleneck import OrtoolsWarmstartError, try_solve_bottleneck_batch_order

    _install_fake_cp_model(monkeypatch, status=4)
    operations, batches = _sample_inputs()
    operations[0].setup_hours = float("nan")

    with pytest.raises(OrtoolsWarmstartError, match="有限数字"):
        try_solve_bottleneck_batch_order(
            operations=operations,
            batches=batches,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            logger=None,
        )


def test_ortools_bool_hours_are_visible(monkeypatch):
    from core.algorithms.ortools_bottleneck import OrtoolsWarmstartError, try_solve_bottleneck_batch_order

    _install_fake_cp_model(monkeypatch, status=4)
    operations, batches = _sample_inputs()

    for field in ("setup_hours", "unit_hours"):
        operations, batches = _sample_inputs()
        setattr(operations[0], field, True)
        with pytest.raises(OrtoolsWarmstartError, match="布尔值"):
            try_solve_bottleneck_batch_order(
                operations=operations,
                batches=batches,
                start_dt=datetime(2026, 1, 1, 8, 0, 0),
                logger=None,
            )

    operations, batches = _sample_inputs()
    batches["B1"].quantity = True
    with pytest.raises(OrtoolsWarmstartError, match="布尔值"):
        try_solve_bottleneck_batch_order(
            operations=operations,
            batches=batches,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            logger=None,
        )


def test_ortools_negative_hour_parts_are_visible(monkeypatch):
    from core.algorithms.ortools_bottleneck import OrtoolsWarmstartError, try_solve_bottleneck_batch_order

    _install_fake_cp_model(monkeypatch, status=4)

    for field in ("setup_hours", "unit_hours"):
        operations, batches = _sample_inputs()
        setattr(operations[0], field, -1)
        with pytest.raises(OrtoolsWarmstartError, match="不能为负数"):
            try_solve_bottleneck_batch_order(
                operations=operations,
                batches=batches,
                start_dt=datetime(2026, 1, 1, 8, 0, 0),
                logger=None,
            )

    operations, batches = _sample_inputs()
    batches["B1"].quantity = -1
    with pytest.raises(OrtoolsWarmstartError, match="不能为负数"):
        try_solve_bottleneck_batch_order(
            operations=operations,
            batches=batches,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            logger=None,
        )


def test_ortools_unknown_status_is_not_reported_as_failure(monkeypatch):
    from core.algorithms.ortools_bottleneck import try_solve_bottleneck_batch_order

    _install_fake_cp_model(monkeypatch, status=0)
    operations, batches = _sample_inputs()

    assert (
        try_solve_bottleneck_batch_order(
            operations=operations,
            batches=batches,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            logger=None,
        )
        is None
    )
