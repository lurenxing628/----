import math
import os
import sys
from datetime import date, datetime


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

    from core.algorithms.dispatch_rules import DispatchInputs, DispatchRule, build_dispatch_key, mean_positive

    now = datetime(2026, 1, 1, 8, 0, 0)
    due = date(2026, 1, 2)

    # 非有限 proc_hours 应退化为 avg_proc_hours（而不是把候选错误置顶/置底）
    k_inf = build_dispatch_key(
        DispatchInputs(
            rule=DispatchRule.CR,
            priority="normal",
            due_date=due,
            est_start=now,
            est_end=now,
            proc_hours=float("inf"),
            avg_proc_hours=2.0,
            changeover_penalty=0,
            batch_order=0,
            batch_id="B_INF",
            seq=1,
            op_id=1,
        )
    )
    k_ref = build_dispatch_key(
        DispatchInputs(
            rule=DispatchRule.CR,
            priority="normal",
            due_date=due,
            est_start=now,
            est_end=now,
            proc_hours=2.0,
            avg_proc_hours=2.0,
            changeover_penalty=0,
            batch_order=0,
            batch_id="B_REF",
            seq=1,
            op_id=2,
        )
    )
    assert math.isfinite(float(k_inf[0])), f"primary 不应为非有限值：k_inf={k_inf!r}"
    assert abs(float(k_inf[0]) - float(k_ref[0])) < 1e-9, f"inf proc_hours 未按 avg_proc_hours 回退：inf={k_inf} ref={k_ref}"

    # mean_positive 仅统计有限正数
    m = mean_positive({"a": 1.0, "b": float("inf"), "c": -2.0, "d": 0.0})
    assert abs(float(m) - 1.0) < 1e-9, f"mean_positive 应忽略 Inf/非正值：m={m!r}"

    print("OK")


if __name__ == "__main__":
    main()

