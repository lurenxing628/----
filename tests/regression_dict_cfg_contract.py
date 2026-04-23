from __future__ import annotations

import os
import sys
import time
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


class _StubSvc:
    logger = None

    @staticmethod
    def _normalize_text(value: Any):
        if value is None:
            return None
        s = str(value).strip()
        return s if s else None

    @staticmethod
    def _format_dt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def _run_optimizer_case(cfg: Any) -> Tuple[str, str, List[Tuple[str, str, str]]]:
    import core.services.scheduler.schedule_optimizer as schedule_optimizer
    import core.services.scheduler.schedule_optimizer_steps as schedule_optimizer_steps

    original_scheduler_cls = schedule_optimizer.GreedyScheduler
    original_time_optimizer = schedule_optimizer.time.time
    original_time_steps = schedule_optimizer_steps.time.time
    original_local_search = schedule_optimizer._run_local_search
    original_ortools = schedule_optimizer._run_ortools_warmstart

    class _RecordingScheduler:
        calls: List[Tuple[str, str, str]] = []

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
            type(self).calls.append((getattr(strategy, "value", str(strategy)), str(dispatch_mode), str(dispatch_rule)))
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
        cfg_svc = SimpleNamespace(
            VALID_STRATEGIES=("weighted",),
            VALID_DISPATCH_MODES=("batch_order", "sgs"),
            VALID_DISPATCH_RULES=("slack", "cr", "atc"),
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
        return outcome.algo_mode, outcome.objective_name, list(_RecordingScheduler.calls)
    finally:
        schedule_optimizer.GreedyScheduler = original_scheduler_cls
        schedule_optimizer.time.time = original_time_optimizer
        schedule_optimizer_steps.time.time = original_time_steps
        schedule_optimizer._run_local_search = original_local_search
        schedule_optimizer._run_ortools_warmstart = original_ortools


def _run_ortools_warmstart_case(cfg: Any) -> Tuple[bool, bool, bool]:
    import core.algorithms.ortools_bottleneck as ortools_bottleneck
    import core.services.scheduler.schedule_optimizer_steps as schedule_optimizer_steps
    from core.algorithms import SortStrategy

    called = {"solve": False, "schedule": False}
    original_solver = ortools_bottleneck.try_solve_bottleneck_batch_order

    def _fake_solver(**_kwargs):
        called["solve"] = True
        return ["B001"]

    class _Scheduler:
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
            called["schedule"] = True
            summary = SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[], duration_seconds=0.0)
            return [], summary, strategy, dict(strategy_params or {})

    ortools_bottleneck.try_solve_bottleneck_batch_order = _fake_solver
    try:
        best = schedule_optimizer_steps._run_ortools_warmstart(
            algo_mode="improve",
            cfg=cfg,
            strategy_enum=SortStrategy.PRIORITY_FIRST,
            objective_name="min_overdue",
            deadline=time.time() + 100,
            scheduler=_Scheduler(),
            algo_ops_to_schedule=[],
            batches={"B001": SimpleNamespace(batch_id="B001", priority="normal", due_date=date(2026, 1, 2), quantity=1)},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_sr_list=[],
            dispatch_mode_cfg="batch_order",
            dispatch_rule_cfg="slack",
            resource_pool=None,
            attempts=[],
            improvement_trace=[],
            best=None,
            t_begin=time.time(),
            logger=None,
        )
        return best is not None, bool(called["solve"]), bool(called["schedule"])
    finally:
        ortools_bottleneck.try_solve_bottleneck_batch_order = original_solver


def _run_summary_case(cfg: Any) -> Dict[str, Any]:
    from core.services.scheduler.schedule_summary import build_result_summary
    from core.services.scheduler.schedule_summary_types import SummaryBuildContext

    summary = SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[])
    downtime_meta = {
        "downtime_load_ok": True,
        "downtime_extend_attempted": True,
        "downtime_extend_ok": False,
        "downtime_extend_error": "mock-fail",
    }
    resource_pool_meta = {
        "resource_pool_attempted": True,
        "resource_pool_build_ok": False,
        "resource_pool_build_error": "mock-resource-pool",
    }
    summary_ctx = SummaryBuildContext(
        cfg=cfg,
        version=1,
        normalized_batch_ids=[],
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        downtime_meta=downtime_meta,
        resource_pool_meta=resource_pool_meta,
        simulate=False,
        t0=time.time(),
    )
    _, _, result_summary_obj, _, _ = build_result_summary(
        _StubSvc(),
        ctx=summary_ctx,
    )
    return result_summary_obj.get("algo") or {}


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    dict_cfg = {
        "sort_strategy": " Weighted ",
        "priority_weight": 0.4,
        "due_weight": 0.5,
        "algo_mode": " IMPROVE ",
        "objective": " MIN_WEIGHTED_TARDINESS ",
        "time_budget_seconds": 1,
        "dispatch_mode": " SGS ",
        "dispatch_rule": " CR ",
        "ortools_enabled": "yes",
        "ortools_time_limit_seconds": 5,
        "freeze_window_enabled": "yes",
        "freeze_window_days": 3,
        "auto_assign_enabled": "yes",
    }
    object_cfg = SimpleNamespace(
        sort_strategy=" Weighted ",
        priority_weight=0.4,
        due_weight=0.5,
        algo_mode=" IMPROVE ",
        objective=" MIN_WEIGHTED_TARDINESS ",
        time_budget_seconds=1,
        dispatch_mode=" SGS ",
        dispatch_rule=" CR ",
        ortools_enabled="yes",
        ortools_time_limit_seconds=5,
        freeze_window_enabled="yes",
        freeze_window_days=3,
        auto_assign_enabled="yes",
    )

    dict_algo_mode, dict_objective_name, dict_calls = _run_optimizer_case(dict_cfg)
    object_algo_mode, object_objective_name, object_calls = _run_optimizer_case(object_cfg)
    expected_calls = [
        ("weighted", "sgs", "cr"),
        ("weighted", "sgs", "slack"),
        ("weighted", "sgs", "atc"),
        ("weighted", "batch_order", "cr"),
    ]
    assert dict_algo_mode == "improve", f"dict cfg algo_mode 未归一化：{dict_algo_mode!r}"
    assert dict_objective_name == "min_weighted_tardiness", f"dict cfg objective 未归一化：{dict_objective_name!r}"
    assert dict_calls == expected_calls, f"dict cfg multi-start 组合异常：{dict_calls!r}"
    assert (dict_algo_mode, dict_objective_name, dict_calls) == (
        object_algo_mode,
        object_objective_name,
        object_calls,
    ), "dict cfg 与 object cfg 的 optimizer 结果不一致"

    dict_best, dict_solve, dict_schedule = _run_ortools_warmstart_case(dict_cfg)
    object_best, object_solve, object_schedule = _run_ortools_warmstart_case(object_cfg)
    assert (dict_best, dict_solve, dict_schedule) == (True, True, True), (
        f"dict cfg OR-Tools warm-start 未进入求解/排产：best={dict_best} solve={dict_solve} schedule={dict_schedule}"
    )
    assert (dict_best, dict_solve, dict_schedule) == (
        object_best,
        object_solve,
        object_schedule,
    ), "dict cfg 与 object cfg 的 OR-Tools warm-start 行为不一致"

    dict_algo = _run_summary_case(dict_cfg)
    object_algo = _run_summary_case(object_cfg)
    assert dict_algo.get("hard_constraints") == [
        "precedence",
        "calendar",
        "resource_machine_operator",
    ], f"dict cfg hard_constraints 错误：{dict_algo.get('hard_constraints')!r}"
    assert dict_algo.get("freeze_window") == {
        "enabled": "yes",
        "days": 3,
        "frozen_op_count": 0,
        "frozen_batch_count": 0,
        "frozen_batch_ids_sample": [],
        "degraded": False,
        "degradation_reason": None,
    }, f"dict cfg freeze_window 摘要错误：{dict_algo.get('freeze_window')!r}"
    assert dict_algo.get("downtime_avoid") == {
        "loaded_ok": True,
        "degraded": True,
        "degradation_reason": "mock-fail",
        "extend_attempted": True,
        "load_partial_fail_count": 0,
        "load_partial_fail_machines_sample": [],
        "extend_partial_fail_count": 0,
        "extend_partial_fail_machines_sample": [],
    }, f"dict cfg downtime_avoid 摘要错误：{dict_algo.get('downtime_avoid')!r}"
    assert dict_algo.get("config_snapshot", {}).get("freeze_window_enabled") == "yes", "config_snapshot 未保留 dict cfg freeze_window_enabled"
    assert dict_algo.get("config_snapshot", {}).get("freeze_window_days") == 3, "config_snapshot 未保留 dict cfg freeze_window_days"
    assert dict_algo.get("config_snapshot", {}).get("auto_assign_enabled") == "yes", "config_snapshot 未保留 dict cfg auto_assign_enabled"
    assert dict_algo.get("resource_pool") == {
        "enabled": "yes",
        "attempted": True,
        "degraded": True,
        "degradation_reason": "mock-resource-pool",
    }, f"dict cfg resource_pool 摘要错误：{dict_algo.get('resource_pool')!r}"
    assert dict_algo == object_algo, "dict cfg 与 object cfg 的 summary 摘要不一致"

    print("OK")


if __name__ == "__main__":
    main()
