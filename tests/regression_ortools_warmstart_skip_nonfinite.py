import os
import sys
from datetime import datetime
from types import ModuleType, SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


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


def install_fake_cp_model() -> None:
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

    sys.modules["ortools"] = ortools
    sys.modules["ortools.sat"] = sat
    sys.modules["ortools.sat.python"] = python
    sys.modules["ortools.sat.python.cp_model"] = cp_model


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    install_fake_cp_model()

    from core.algorithms.ortools_bottleneck import try_solve_bottleneck_batch_order

    start_dt = datetime(2026, 1, 1, 8, 0, 0)

    b1 = SimpleNamespace(batch_id="B1", priority="normal", due_date="2025-12-31", quantity=1)
    b2 = SimpleNamespace(batch_id="B2", priority="normal", due_date="2025-12-31", quantity=1)
    batches = {"B1": b1, "B2": b2}

    # 混入 NaN/Inf：若未过滤，旧实现可能在 math.ceil(h*60) 处崩溃，或污染瓶颈识别
    ops = [
        # B1：非有限工时（应被跳过）
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
        # B1：有限工时（应保留）
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
        # B2：非有限工时（应被跳过）
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
        # B2：有限工时（应保留）
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

    order = try_solve_bottleneck_batch_order(
        operations=ops,
        batches=batches,
        start_dt=start_dt,
        time_limit_seconds=2,
        max_jobs=200,
        logger=None,
    )
    assert order is not None, "过滤非有限工时后应仍可产生 warm-start 顺序"
    assert len(order) == 2, f"期望仅包含 2 个批次，实际 order={order!r}"
    assert order == ["B1", "B2"], f"期望短工时优先（B1 在前）：order={order!r}"
    assert _FakeCpModel.interval_durations == [60, 120], (
        "CP 模型里只能出现有限工时任务，"
        f"实际 durations={_FakeCpModel.interval_durations!r}"
    )

    print("OK")


if __name__ == "__main__":
    main()
