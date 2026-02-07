import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


@dataclass
class _StubCalendarService:
    """最小日历服务桩：满足 GreedyScheduler.schedule 所需接口。"""

    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: str = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: str = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id: str = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms import GreedyScheduler, ScheduleResult

    batch = SimpleNamespace(
        batch_id="B001",
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )
    batches = {"B001": batch}

    op1 = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B001",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_id="OT01",
        op_type_name="车削",
        supplier_id=None,
        ext_days=None,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )
    op2 = SimpleNamespace(
        id=2,
        op_code="OP2",
        batch_id="B001",
        seq=2,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_id="OT01",
        op_type_name="车削",
        supplier_id=None,
        ext_days=None,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )
    operations = [op1, op2]

    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    seed_end = start_dt + timedelta(hours=1)

    # 1) 重复 seed：同 op_id=1 出现两条
    # 2) 坏时间 seed：op_id=2 且 end_time<=start_time，应被忽略
    seed_results = [
        ScheduleResult(
            op_id=1,
            op_code="OP1",
            batch_id="B001",
            seq=1,
            machine_id="M1",
            operator_id="O1",
            start_time=start_dt,
            end_time=seed_end,
            source="internal",
            op_type_name=None,
        ),
        ScheduleResult(
            op_id=1,
            op_code="OP1",
            batch_id="B001",
            seq=1,
            machine_id="M1",
            operator_id="O1",
            start_time=start_dt,
            end_time=seed_end,
            source="internal",
            op_type_name=None,
        ),
        ScheduleResult(
            op_id=2,
            op_code="OP2",
            batch_id="B001",
            seq=2,
            machine_id="M1",
            operator_id="O1",
            start_time=seed_end,
            end_time=seed_end,  # bad time
            source="internal",
            op_type_name=None,
        ),
    ]

    sched = GreedyScheduler(calendar_service=_StubCalendarService())
    results, summary, _strategy, _used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        seed_results=seed_results,
        dispatch_mode="batch_order",
        dispatch_rule="slack",
    )

    op_ids = [int(r.op_id) for r in results]
    assert op_ids.count(1) == 1, f"重复 seed 应被去重，实际 op_ids={op_ids}"
    assert set(op_ids) == {1, 2}, f"应产出 op_id=1/2，实际 op_ids={op_ids}"
    assert len(results) == 2, f"应仅 2 条结果（seed+新增），实际 len={len(results)} op_ids={op_ids}"

    assert summary.total_ops == 2, f"total_ops 应为 2，实际 {summary.total_ops}"
    assert summary.scheduled_ops == 2, f"scheduled_ops 应为 2，实际 {summary.scheduled_ops}"
    assert summary.failed_ops == 0, f"failed_ops 应为 0，实际 {summary.failed_ops}"

    # warnings 应可观测（至少包含“重复 op_id”和“start_time>=end_time”）
    warn_text = "\n".join([str(x) for x in (summary.warnings or [])])
    assert "重复 op_id" in warn_text, f"应提示重复 seed，warnings={summary.warnings}"
    assert "start_time>=end_time" in warn_text, f"应提示坏时间 seed，warnings={summary.warnings}"

    # op2 应不早于 seed_end（确保 seed_end 推进了 batch_progress）
    op2_res = next((r for r in results if int(r.op_id) == 2), None)
    assert op2_res is not None and op2_res.start_time is not None
    assert op2_res.start_time >= seed_end, f"op2.start_time 应>=seed_end={seed_end}，实际 {op2_res.start_time}"

    print("OK")


if __name__ == "__main__":
    main()

