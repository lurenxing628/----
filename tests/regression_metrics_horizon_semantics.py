import os
import sys
from datetime import datetime, timedelta


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

    from core.algorithms.evaluation import compute_metrics
    from core.algorithms.types import ScheduleResult

    # 仅外协结果：internal horizon=0 -> util_defined=False（util_avg 仍为 0.0 占位）
    st = datetime(2026, 1, 1, 8, 0, 0)
    et = st + timedelta(days=1)
    results = [
        ScheduleResult(
            op_id=1,
            op_code="E1",
            batch_id="B001",
            seq=1,
            machine_id=None,
            operator_id=None,
            start_time=st,
            end_time=et,
            source="external",
            op_type_name=None,
        )
    ]
    metrics = compute_metrics(results, batches={})
    assert metrics.makespan_internal_hours == 0.0, f"internal makespan 应为 0：{metrics.makespan_internal_hours!r}"
    assert metrics.internal_horizon_hours == 0.0, f"internal_horizon_hours 应为 0：{metrics.internal_horizon_hours!r}"
    assert metrics.util_defined is False, f"util_defined 应为 False：{metrics.util_defined!r}"

    d = metrics.to_dict()
    assert d.get("util_defined") is False, f"to_dict util_defined 异常：{d!r}"
    assert float(d.get("internal_horizon_hours") or 0.0) == 0.0, f"to_dict internal_horizon_hours 异常：{d!r}"

    print("OK")


if __name__ == "__main__":
    main()

