import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional


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

    本回归用例关注：seed_results 内部工序缺 machine_id 或 operator_id 时，
    仍应“按可用字段”冻结对应资源，避免后续工序重叠排产。
    """

    def adjust_to_working_time(
        self,
        dt: datetime,
        priority=None,
        machine_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(
        self,
        dt: datetime,
        hours: float,
        priority=None,
        machine_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def _build_batches():
    b1 = SimpleNamespace(
        batch_id="B001",
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )
    b2 = SimpleNamespace(
        batch_id="B002",
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )
    return {"B001": b1, "B002": b2}


def _run_case(*, dispatch_mode: str, seed_machine_id, seed_operator_id, op_machine_id: str, op_operator_id: str):
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms import GreedyScheduler, ScheduleResult

    batches = _build_batches()
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    seed_end = start_dt + timedelta(hours=1)

    # B001：冻结种子（内部工序，但故意缺失一项资源）
    seed_results = [
        ScheduleResult(
            op_id=1,
            op_code="SEED_OP",
            batch_id="B001",
            seq=1,
            machine_id=seed_machine_id,
            operator_id=seed_operator_id,
            start_time=start_dt,
            end_time=seed_end,
            source="internal",
            op_type_name=None,
        )
    ]

    # B002：待排工序（占用与 seed 相同的资源维度，用于验证是否会被推迟）
    operations = [
        SimpleNamespace(
            id=2,
            op_code="OP2",
            batch_id="B002",
            seq=1,
            source="internal",
            machine_id=op_machine_id,
            operator_id=op_operator_id,
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
    ]

    sched = GreedyScheduler(calendar_service=_StubCalendarService())
    results, summary, used_strategy, used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        seed_results=seed_results,
        dispatch_mode=dispatch_mode,
        dispatch_rule="slack",
    )
    return results, summary, used_strategy, used_params, seed_end


def main():
    for mode in ("batch_order", "sgs"):
        # Case A：seed 缺 operator_id，但有 machine_id -> 应冻结设备资源
        results, summary, _strategy, used_params, seed_end = _run_case(
            dispatch_mode=mode,
            seed_machine_id="M1",
            seed_operator_id=None,
            op_machine_id="M1",
            op_operator_id="O2",
        )
        assert used_params.get("dispatch_mode") == mode, f"dispatch_mode 解析异常：{used_params!r}"
        assert summary.failed_ops == 0, f"预期 failed_ops=0，实际 {summary.failed_ops}"
        op2 = next((r for r in results if int(r.op_id) == 2), None)
        assert op2 is not None, "缺少 op_id=2 的排程结果"
        assert op2.start_time is not None, "op_id=2 start_time 为空"
        assert (
            op2.start_time >= seed_end
        ), f"[{mode}] seed 缺 operator_id 时仍应冻结 machine=M1；期望 op2.start_time>={seed_end}，实际 {op2.start_time}"

        # Case B：seed 缺 machine_id，但有 operator_id -> 应冻结人员资源
        results, summary, _strategy, used_params, seed_end = _run_case(
            dispatch_mode=mode,
            seed_machine_id=None,
            seed_operator_id="O1",
            op_machine_id="M2",
            op_operator_id="O1",
        )
        assert used_params.get("dispatch_mode") == mode, f"dispatch_mode 解析异常：{used_params!r}"
        assert summary.failed_ops == 0, f"预期 failed_ops=0，实际 {summary.failed_ops}"
        op2 = next((r for r in results if int(r.op_id) == 2), None)
        assert op2 is not None, "缺少 op_id=2 的排程结果"
        assert op2.start_time is not None, "op_id=2 start_time 为空"
        assert (
            op2.start_time >= seed_end
        ), f"[{mode}] seed 缺 machine_id 时仍应冻结 operator=O1；期望 op2.start_time>={seed_end}，实际 {op2.start_time}"

    print("OK")


if __name__ == "__main__":
    main()

