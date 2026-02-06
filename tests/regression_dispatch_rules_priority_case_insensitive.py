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

    print("OK")


if __name__ == "__main__":
    main()

