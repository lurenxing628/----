"""回归测试：dispatch_rules.build_dispatch_key 在 proc_hours 为非有限值（inf）时应退化为 avg_proc_hours（primary 键保持有限、与正常值一致，不把候选错误置顶/置底），且 mean_positive 只统计有限正数、忽略 Inf 与非正值。"""

import math
from datetime import date, datetime


def test_dispatch_rules_nonfinite_proc_hours_safe() -> None:

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


