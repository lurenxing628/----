import os
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


class _StubCalendar:
    @staticmethod
    def adjust_to_working_time(dt: datetime, priority=None, machine_id=None, operator_id=None) -> datetime:
        return dt

    @staticmethod
    def add_working_hours(dt: datetime, hours: float, priority=None, machine_id=None, operator_id=None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    @staticmethod
    def get_efficiency(dt: datetime, machine_id=None, operator_id=None) -> float:
        return 1.0

    @staticmethod
    def add_calendar_days(dt: datetime, days: float, machine_id=None, operator_id=None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


class _DeterministicClock:
    def __init__(self, *, start: float = 1000.0, step: float = 0.01):
        self._now = float(start)
        self._step = float(step)

    def time(self) -> float:
        current = self._now
        self._now += self._step
        return current


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import core.services.scheduler.schedule_optimizer as schedule_optimizer
    import core.services.scheduler.schedule_optimizer_steps as schedule_optimizer_steps

    original_scheduler_cls = schedule_optimizer.GreedyScheduler
    original_time_optimizer = schedule_optimizer.time.time
    original_time_steps = schedule_optimizer_steps.time.time
    original_local_search = schedule_optimizer._run_local_search
    original_ortools = schedule_optimizer._run_ortools_warmstart

    class _RecordingScheduler:
        calls: List[Tuple[str, str]] = []

        def __init__(self, calendar_service, config_service=None, logger=None):
            self.calendar = calendar_service
            self.config = config_service
            self.logger = logger

        def schedule(
            self,
            operations,
            batches,
            strategy=None,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            machine_downtimes=None,
            batch_order_override=None,
            seed_results=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool=None,
        ):
            type(self).calls.append((str(dispatch_mode), str(dispatch_rule)))
            summary = SimpleNamespace(
                success=True,
                total_ops=int(len(operations or [])),
                scheduled_ops=int(len(operations or [])),
                failed_ops=0,
                warnings=[],
                errors=[],
                duration_seconds=0.0,
            )
            return [], summary, strategy, dict(strategy_params or {})

    schedule_optimizer.GreedyScheduler = _RecordingScheduler
    clock = _DeterministicClock()
    schedule_optimizer.time.time = clock.time
    schedule_optimizer_steps.time.time = clock.time
    schedule_optimizer._run_local_search = lambda **kwargs: kwargs.get("best")
    schedule_optimizer._run_ortools_warmstart = lambda **kwargs: kwargs.get("best")

    try:
        cfg = SimpleNamespace(
            sort_strategy="priority_first",
            priority_weight=0.4,
            due_weight=0.5,
            algo_mode=" IMPROVE ",
            objective=" MIN_WEIGHTED_TARDINESS ",
            time_budget_seconds=1,
            dispatch_mode=" SGS ",
            dispatch_rule=" CR ",
            ortools_enabled="no",
        )
        cfg_svc = SimpleNamespace(
            VALID_STRATEGIES=("priority_first",),
            VALID_DISPATCH_MODES=("batch_order", "sgs"),
            VALID_DISPATCH_RULES=("slack", "cr", "atc"),
        )
        batches: Dict[str, Any] = {
            "B001": SimpleNamespace(
                batch_id="B001",
                priority="normal",
                due_date=date(2026, 1, 2),
                ready_status="yes",
                ready_date=None,
                created_at=None,
                quantity=1,
            )
        }

        _RecordingScheduler.calls = []
        outcome = schedule_optimizer.optimize_schedule(
            calendar_service=_StubCalendar(),
            cfg_svc=cfg_svc,
            cfg=cfg,
            algo_ops_to_schedule=[],
            batches=batches,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_results=[],
            resource_pool=None,
            version=1,
            logger=None,
        )
    finally:
        schedule_optimizer.GreedyScheduler = original_scheduler_cls
        schedule_optimizer.time.time = original_time_optimizer
        schedule_optimizer_steps.time.time = original_time_steps
        schedule_optimizer._run_local_search = original_local_search
        schedule_optimizer._run_ortools_warmstart = original_ortools

    expected_pairs = {
        ("batch_order", "cr"),
        ("sgs", "cr"),
        ("sgs", "slack"),
        ("sgs", "atc"),
    }
    actual_pairs = set(_RecordingScheduler.calls)
    assert outcome.algo_mode == "improve", f"outcome.algo_mode 未归一化：{outcome.algo_mode!r}"
    assert outcome.objective_name == "min_weighted_tardiness", (
        f"outcome.objective_name 未归一化：{outcome.objective_name!r}"
    )
    assert len(_RecordingScheduler.calls) == len(expected_pairs), f"multi-start 组合数异常：{_RecordingScheduler.calls!r}"
    assert actual_pairs == expected_pairs, f"multi-start 组合未去重或未规范化：{_RecordingScheduler.calls!r}"

    attempts_pairs = [
        (str(item.get("dispatch_mode")), str(item.get("dispatch_rule")))
        for item in (outcome.attempts or [])
        if isinstance(item, dict)
    ]
    assert len(attempts_pairs) == len(expected_pairs), f"attempts 数量异常：{attempts_pairs!r}"
    assert set(attempts_pairs) == expected_pairs, f"attempts 留痕未规范化：{attempts_pairs!r}"

    print("OK")


if __name__ == "__main__":
    main()
