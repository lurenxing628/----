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
    """
    最小日历服务桩：满足 GreedyScheduler.schedule 所需接口。

    本回归用例关注：seed_results 中存在有效起止时间但 op_id<=0 时，
    算法应能通过 op_code 或 (batch_id, seq) 回填真实 op_id，避免重复排产与错误统计。
    """

    def adjust_to_working_time(self, dt: datetime, priority=None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def _build_case():
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

    # 两道内部工序（同批次串行）
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
        op_type_id=None,
        op_type_name=None,
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
        op_type_id=None,
        op_type_name=None,
        supplier_id=None,
        ext_days=None,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )
    operations = [op1, op2]

    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    # seed 故意给更长的时间（2h），用于区分“复用 seed”与“重新排产 op1(1h)”
    seed_end = start_dt + timedelta(hours=2)
    return operations, batches, start_dt, seed_end


def _run(dispatch_mode: str, *, seed_op_code: str, seed_seq: int):
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms import GreedyScheduler, ScheduleResult

    operations, batches, start_dt, seed_end = _build_case()

    # 注意：op_id=0（无效），但可通过 op_code 或 (batch_id, seq) 匹配到真实工序 id=1
    seed_results = [
        ScheduleResult(
            op_id=0,
            op_code=seed_op_code,
            batch_id="B001",
            seq=int(seed_seq),
            machine_id="M1",
            operator_id="O1",
            start_time=start_dt,
            end_time=seed_end,
            source="internal",
            op_type_name=None,
        )
    ]

    sched = GreedyScheduler(calendar_service=_StubCalendarService())
    results, summary, _strategy, used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        seed_results=seed_results,
        dispatch_mode=dispatch_mode,
        dispatch_rule="slack",
    )
    return results, summary, used_params, seed_end


def main():
    # 两种派工模式都应满足：seed 回填 + 去重 + total_ops 正确
    for mode in ("batch_order", "sgs"):
        for tag, seed_op_code, seed_seq in (
            ("by_op_code", "OP1", 1),
            ("by_batch_seq", "", 1),
        ):
            results, summary, used_params, seed_end = _run(mode, seed_op_code=seed_op_code, seed_seq=seed_seq)

            assert used_params.get("dispatch_mode") == mode, f"dispatch_mode 解析异常：{used_params!r}"

            op_ids = [int(r.op_id) for r in results]
            assert all(x > 0 for x in op_ids), f"[{mode}|{tag}] 不应产出 op_id<=0 的结果，实际 op_ids={op_ids}"
            assert set(op_ids) == {1, 2}, f"[{mode}|{tag}] 应仅包含 op_id=1/2，实际 op_ids={op_ids}"
            assert len(results) == 2, f"[{mode}|{tag}] 应仅产出 2 条结果（seed+新增），实际 len={len(results)} op_ids={op_ids}"

            assert summary.total_ops == 2, f"[{mode}|{tag}] total_ops 应为 2（去重后=1+seed=1），实际 {summary.total_ops}"
            assert summary.scheduled_ops == 2, f"[{mode}|{tag}] scheduled_ops 应为 2，实际 {summary.scheduled_ops}"
            assert summary.failed_ops == 0, f"[{mode}|{tag}] failed_ops 应为 0，实际 {summary.failed_ops}"

            # 验证 seed 时间被复用：op2 应不早于 seed_end（若 seed 被丢弃或重复排产口径错误，可能早于 seed_end）
            op2 = next((r for r in results if int(r.op_id) == 2), None)
            assert op2 is not None, f"[{mode}|{tag}] 缺少 op_id=2 的排程结果"
            assert op2.start_time is not None, f"[{mode}|{tag}] op_id=2 start_time 为空"
            assert (
                op2.start_time >= seed_end
            ), f"[{mode}|{tag}] op_id=2 应不早于 seed_end={seed_end}，实际 start_time={op2.start_time}"

    print("OK")


if __name__ == "__main__":
    main()

