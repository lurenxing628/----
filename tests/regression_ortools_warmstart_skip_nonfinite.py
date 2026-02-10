import os
import sys
from datetime import datetime
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # OR-Tools 是可选依赖：未安装时直接 SKIP（退出 0）
    try:
        from ortools.sat.python import cp_model as _cp_model  # noqa: F401
    except Exception:
        print("SKIP (ortools not installed)")
        print("OK")
        return

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

    print("OK")


if __name__ == "__main__":
    main()

