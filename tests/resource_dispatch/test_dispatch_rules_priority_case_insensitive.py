"""回归测试：dispatch_rules.build_dispatch_key 对 priority 大小写归一化——SLACK 规则下 Urgent 经 tie-break(pr_rank) 排在 normal 前、ATC 规则下 URGENT 经 PRIORITY_WEIGHT 排在 normal 前，混合/全大写写法均不影响优先级权重。"""

from datetime import date, datetime


def test_dispatch_rules_priority_case_insensitive() -> None:

    from core.algorithms.dispatch_rules import DispatchInputs, DispatchRule, build_dispatch_key

    now = datetime(2026, 1, 1, 8, 0, 0)
    due = date(2026, 1, 2)

    # SLACK：primary 一样，靠 tie-break 的 pr_rank 区分
    k_urgent = build_dispatch_key(
        DispatchInputs(
            rule=DispatchRule.SLACK,
            priority="Urgent",  # 混合大小写
            due_date=due,
            est_start=now,
            est_end=now,
            proc_hours=1.0,
            avg_proc_hours=1.0,
            changeover_penalty=0,
            batch_order=0,
            batch_id="B001",
            seq=1,
            op_id=1,
        )
    )
    k_normal = build_dispatch_key(
        DispatchInputs(
            rule=DispatchRule.SLACK,
            priority="normal",
            due_date=due,
            est_start=now,
            est_end=now,
            proc_hours=1.0,
            avg_proc_hours=1.0,
            changeover_penalty=0,
            batch_order=0,
            batch_id="B002",
            seq=1,
            op_id=2,
        )
    )
    assert k_urgent < k_normal, f"SLACK priority 大小写归一化失败：urgent={k_urgent} normal={k_normal}"

    # ATC：primary 依赖 PRIORITY_WEIGHT（urgent 应更优）
    k_urgent_atc = build_dispatch_key(
        DispatchInputs(
            rule=DispatchRule.ATC,
            priority="URGENT",  # 全大写
            due_date=due,
            est_start=now,
            est_end=now,
            proc_hours=2.0,
            avg_proc_hours=2.0,
            changeover_penalty=0,
            batch_order=0,
            batch_id="B003",
            seq=1,
            op_id=3,
        )
    )
    k_normal_atc = build_dispatch_key(
        DispatchInputs(
            rule=DispatchRule.ATC,
            priority="normal",
            due_date=due,
            est_start=now,
            est_end=now,
            proc_hours=2.0,
            avg_proc_hours=2.0,
            changeover_penalty=0,
            batch_order=0,
            batch_id="B004",
            seq=1,
            op_id=4,
        )
    )
    assert k_urgent_atc < k_normal_atc, f"ATC priority 大小写归一化失败：urgent={k_urgent_atc} normal={k_normal_atc}"


