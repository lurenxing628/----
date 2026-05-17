import os
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List


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
    def __init__(self, *, start: float = 1000.0, step: float = 0.05):
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

    class _RecordingScheduler:
        calls: List[Dict[str, Any]] = []

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
            type(self).calls.append(
                {
                    "strategy": getattr(strategy, "value", str(strategy)),
                    "dispatch_mode": str(dispatch_mode),
                    "dispatch_rule": str(dispatch_rule),
                }
            )
            summary = SimpleNamespace(
                success=True,
                total_ops=int(len(operations or [])),
                scheduled_ops=int(len(operations or [])),
                failed_ops=0,
                warnings=[],
                errors=[],
                duration_seconds=0.0,
            )
            used_params = dict(strategy_params or {})
            used_params["dispatch_mode"] = str(dispatch_mode)
            used_params["dispatch_rule"] = str(dispatch_rule)
            return [], summary, strategy, used_params

    class _StrictAwareScheduler:
        strict_mode_values: List[bool] = []

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
            strict_mode=False,
        ):
            type(self).strict_mode_values.append(bool(strict_mode))
            summary = SimpleNamespace(
                success=True,
                total_ops=int(len(operations or [])),
                scheduled_ops=int(len(operations or [])),
                failed_ops=0,
                warnings=[],
                errors=[],
                duration_seconds=0.0,
            )
            used_params = dict(strategy_params or {})
            used_params["dispatch_mode"] = str(dispatch_mode)
            used_params["dispatch_rule"] = str(dispatch_rule)
            used_params["strict_mode"] = bool(strict_mode)
            return [], summary, strategy, used_params

    schedule_optimizer.GreedyScheduler = _RecordingScheduler
    clock = _DeterministicClock()
    schedule_optimizer.time.time = clock.time
    schedule_optimizer_steps.time.time = clock.time
    try:
        cfg = SimpleNamespace(
            sort_strategy="priority_first",
            priority_weight=0.4,
            due_weight=0.5,
            ready_weight=0.1,
            holiday_default_efficiency=1.0,
            enforce_ready_default="no",
            prefer_primary_skill="no",
            algo_mode="improve",
            objective="min_overdue",
            time_budget_seconds=1,
            dispatch_mode="batch_order",
            dispatch_rule="slack",
            auto_assign_enabled="no",
            auto_assign_persist="yes",
            ortools_enabled="no",
            ortools_time_limit_seconds=5,
            freeze_window_enabled="no",
            freeze_window_days=0,
        )
        batches = {
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

        cfg_svc = SimpleNamespace(
            VALID_STRATEGIES=("priority_first", "due_date_first", "weighted", "fifo"),
            VALID_DISPATCH_MODES=("batch_order", "sgs"),
            VALID_DISPATCH_RULES=("slack", "cr", "atc"),
        )
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
        expanded_calls = list(_RecordingScheduler.calls)

        narrowed_cfg_svc = SimpleNamespace(
            VALID_STRATEGIES=("priority_first",),
            VALID_DISPATCH_MODES=("batch_order",),
            VALID_DISPATCH_RULES=("slack",),
        )
        _RecordingScheduler.calls = []
        narrowed_outcome = schedule_optimizer.optimize_schedule(
            calendar_service=_StubCalendar(),
            cfg_svc=narrowed_cfg_svc,
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

        schedule_optimizer.GreedyScheduler = _StrictAwareScheduler
        _StrictAwareScheduler.strict_mode_values = []
        strict_outcome = schedule_optimizer.optimize_schedule(
            calendar_service=_StubCalendar(),
            cfg_svc=narrowed_cfg_svc,
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
            strict_mode=True,
        )
    finally:
        schedule_optimizer.GreedyScheduler = original_scheduler_cls
        schedule_optimizer.time.time = original_time_optimizer
        schedule_optimizer_steps.time.time = original_time_steps

    call_modes = sorted({x["dispatch_mode"] for x in expanded_calls})
    assert call_modes == ["batch_order", "sgs"], f"multi-start 未扩到两种 dispatch_mode：{call_modes}"

    attempt_modes = sorted({str(x.get("dispatch_mode")) for x in (outcome.attempts or [])})
    assert attempt_modes == ["batch_order", "sgs"], f"attempts 留痕未覆盖两种 dispatch_mode：{attempt_modes}"

    narrowed_calls = list(_RecordingScheduler.calls)
    assert narrowed_calls == [
        {
            "strategy": "priority_first",
            "dispatch_mode": "batch_order",
            "dispatch_rule": "slack",
        }
    ], f"收窄 allowlist 后 optimizer 仍越权扩展尝试：{narrowed_calls!r}"

    narrowed_attempts = list(narrowed_outcome.attempts or [])
    assert len(narrowed_attempts) == 1, f"收窄 allowlist 后 attempts 数量异常：{narrowed_attempts!r}"
    only_attempt = narrowed_attempts[0]
    assert (
        str(only_attempt.get("strategy")) == "priority_first"
        and str(only_attempt.get("dispatch_mode")) == "batch_order"
        and str(only_attempt.get("dispatch_rule")) == "slack"
    ), f"收窄 allowlist 后 attempts 留痕越权：{only_attempt!r}"

    assert _StrictAwareScheduler.strict_mode_values, "strict_mode=True 应传递给支持该关键字的 scheduler"
    assert set(_StrictAwareScheduler.strict_mode_values) == {True}, _StrictAwareScheduler.strict_mode_values
    assert all(bool(item.get("used_params", {}).get("strict_mode", False)) for item in (strict_outcome.attempts or [])), (
        f"strict_mode=True 时 attempts 留痕应与 scheduler 接口一致：{strict_outcome.attempts!r}"
    )

    print("OK")


if __name__ == "__main__":
    main()
