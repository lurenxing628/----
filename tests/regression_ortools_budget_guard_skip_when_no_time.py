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
class _StubCalendar:
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: str = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: str = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, machine_id: str = None, operator_id: str = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id: str = None, operator_id: str = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


class _StubCfgSvc:
    VALID_STRATEGIES = ["priority_first", "due_date_first", "weighted", "fifo"]
    VALID_DISPATCH_RULES = ["slack", "cr", "atc"]


class _FakeTime:
    """
    让 optimize_schedule 在 OR-Tools 阶段看到 remaining<1，从而必须跳过 warm-start。
    """

    def __init__(self):
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        # 第一次用于 t_begin；之后全部返回 2.0，让 deadline(=1.0) 已过期
        return 0.0 if self.calls == 1 else 2.0


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import core.algorithms.ortools_bottleneck as ob
    import core.services.scheduler.schedule_optimizer as so

    # 打桩：如果 OR-Tools warm-start 在 remaining<1 时仍被调用，这里直接失败
    orig_try_solve = ob.try_solve_bottleneck_batch_order

    def _boom(*args, **kwargs):
        raise AssertionError("remaining<1 时不应调用 OR-Tools warm-start")

    ob.try_solve_bottleneck_batch_order = _boom

    # 打桩 time.time：制造 remaining<1 的场景
    orig_time = so.time.time
    fake_time = _FakeTime()
    so.time.time = fake_time

    try:
        batch = SimpleNamespace(
            batch_id="B001",
            priority="normal",
            due_date="2026-01-10",
            ready_status="yes",
            ready_date=None,
            created_at=None,
            quantity=1,
        )
        batches = {"B001": batch}

        op = SimpleNamespace(
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

        cfg = SimpleNamespace(
            sort_strategy="priority_first",
            priority_weight=0.4,
            due_weight=0.5,
            algo_mode="improve",
            objective="min_overdue",
            time_budget_seconds=1,
            dispatch_mode="batch_order",
            dispatch_rule="slack",
            ortools_enabled="yes",
            ortools_time_limit_seconds=5,
        )

        out = so.optimize_schedule(
            calendar_service=_StubCalendar(),
            cfg_svc=_StubCfgSvc(),
            cfg=cfg,
            algo_ops_to_schedule=[op],
            batches=batches,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_results=[],
            resource_pool=None,
            version=1,
            logger=None,
        )

        assert out is not None, "optimize_schedule 应返回 OptimizationOutcome"
        assert fake_time.calls >= 2, "fake time 未生效"
    finally:
        # 还原 monkeypatch
        ob.try_solve_bottleneck_batch_order = orig_try_solve
        so.time.time = orig_time

    print("OK")


if __name__ == "__main__":
    main()

