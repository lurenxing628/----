import json
import math
import os
import sys


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

    from core.algorithms.evaluation import ScheduleMetrics

    m = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=float("nan"),
        makespan_hours=float("inf"),
        changeover_count=0,
        weighted_tardiness_hours=float("nan"),
        makespan_internal_hours=float("inf"),
        machine_busy_hours_total=float("inf"),
        operator_busy_hours_total=float("nan"),
        machine_util_avg=float("inf"),
        operator_util_avg=float("nan"),
        machine_load_cv=float("inf"),
        operator_load_cv=float("nan"),
        internal_horizon_hours=float("inf"),
        util_defined=True,
    )
    d = m.to_dict()

    float_keys = [
        "total_tardiness_hours",
        "makespan_hours",
        "weighted_tardiness_hours",
        "makespan_internal_hours",
        "machine_busy_hours_total",
        "operator_busy_hours_total",
        "machine_util_avg",
        "operator_util_avg",
        "machine_load_cv",
        "operator_load_cv",
        "internal_horizon_hours",
    ]
    for k in float_keys:
        v = float(d.get(k, 0.0))
        assert math.isfinite(v), f"{k} 应为有限数值：{k}={v!r} d={d!r}"

    # 严格 JSON（禁止 NaN/Infinity）应可序列化
    _ = json.dumps(d, allow_nan=False)

    print("OK")


if __name__ == "__main__":
    main()

