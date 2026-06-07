"""守护新合同：try_solve_bottleneck_batch_order 遇到 NaN/Inf 工时(setup_hours)必须抛 OrtoolsWarmstartError(含"有限数字")可见报错、而非静默跳过，且报错发生在建模前——不得有任何 NewIntervalVar 区间被建出来。"""

from __future__ import annotations

from types import ModuleType, SimpleNamespace


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
    def __init__(self, name: str):
        self.name = name


class _FakeCpModel:
    interval_durations = []

    def NewIntVar(self, lb, ub, name):
        return _FakeVar(str(name))

    def NewIntervalVar(self, start, duration, end, name):
        self.interval_durations.append(int(duration))
        return (start, duration, end, name)

    def Add(self, constraint):
        return None

    def AddNoOverlap(self, intervals):
        return None

    def Minimize(self, objective):
        return None


class _FakeCpSolver:
    def __init__(self):
        self.parameters = SimpleNamespace()

    def Solve(self, model):
        return 4

    def Value(self, var):
        name = getattr(var, "name", "")
        if name.startswith("s_"):
            return int(name.split("_", 1)[1]) * 100
        return 0


def _build_fake_ortools_modules():
    cp_model = ModuleType("ortools.sat.python.cp_model")
    cp_model.CpModel = _FakeCpModel
    cp_model.CpSolver = _FakeCpSolver
    cp_model.OPTIMAL = 4
    cp_model.FEASIBLE = 2

    ortools = ModuleType("ortools")
    sat = ModuleType("ortools.sat")
    python = ModuleType("ortools.sat.python")
    python.cp_model = cp_model
    sat.python = python
    ortools.sat = sat

    return {
        "ortools": ortools,
        "ortools.sat": sat,
        "ortools.sat.python": python,
        "ortools.sat.python.cp_model": cp_model,
    }


def test_ortools_warmstart_skip_nonfinite(monkeypatch) -> None:
    import sys
    from datetime import datetime

    # 类态重置 + sys.modules 假 ortools 全家桶注入均交给 monkeypatch 自动还原（同进程不泄漏）
    monkeypatch.setattr(_FakeCpModel, "interval_durations", [])
    for name, mod in _build_fake_ortools_modules().items():
        monkeypatch.setitem(sys.modules, name, mod)

    from core.algorithms.ortools_bottleneck import OrtoolsWarmstartError, try_solve_bottleneck_batch_order

    start_dt = datetime(2026, 1, 1, 8, 0, 0)

    b1 = SimpleNamespace(batch_id="B1", priority="normal", due_date="2025-12-31", quantity=1)
    b2 = SimpleNamespace(batch_id="B2", priority="normal", due_date="2025-12-31", quantity=1)
    batches = {"B1": b1, "B2": b2}

    # 混入 NaN/Inf：新合同要求可见报错，不能再静默跳过。
    ops = [
        # B1：非有限工时（应报错）
        SimpleNamespace(
            id=1,
            op_code="OP_B1_NAN",
            batch_id="B1",
            seq=1,
            source="internal",
            op_type_id="OT01",
            setup_hours=float("nan"),
            unit_hours=0.0,
        ),
        # B1：有限工时
        SimpleNamespace(
            id=2,
            op_code="OP_B1_OK",
            batch_id="B1",
            seq=2,
            source="internal",
            op_type_id="OT01",
            setup_hours=1.0,
            unit_hours=0.0,
        ),
        # B2：非有限工时
        SimpleNamespace(
            id=3,
            op_code="OP_B2_INF",
            batch_id="B2",
            seq=1,
            source="internal",
            op_type_id="OT01",
            setup_hours=float("inf"),
            unit_hours=0.0,
        ),
        # B2：有限工时
        SimpleNamespace(
            id=4,
            op_code="OP_B2_OK",
            batch_id="B2",
            seq=2,
            source="internal",
            op_type_id="OT01",
            setup_hours=2.0,
            unit_hours=0.0,
        ),
    ]

    try:
        try_solve_bottleneck_batch_order(
            operations=ops,
            batches=batches,
            start_dt=start_dt,
            time_limit_seconds=2,
            max_jobs=200,
            logger=None,
        )
    except OrtoolsWarmstartError as exc:
        assert "有限数字" in str(exc), str(exc)
    else:
        raise AssertionError("OR-Tools warm-start 非有限工时不能静默跳过")
    assert _FakeCpModel.interval_durations == [], (
        "非有限工时应在建模前报错，"
        f"实际 durations={_FakeCpModel.interval_durations!r}"
    )
