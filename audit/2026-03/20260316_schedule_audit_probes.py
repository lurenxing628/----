from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent] + list(here.parents):
        if (p / "app.py").exists() and (p / "schema.sql").exists():
            return p
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


REPO_ROOT = find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUTPUT_PATH = REPO_ROOT / "audit" / "2026-03" / "20260316_schedule_audit_probes.json"


class _FakeSummaryService:
    logger = None

    @staticmethod
    def _normalize_text(value: Any) -> str:
        s = str(value or "").strip()
        return s

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


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


def _serialize_results(results: List[Any]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for r in results:
        serialized.append(
            {
                "op_id": int(getattr(r, "op_id", 0) or 0),
                "batch_id": str(getattr(r, "batch_id", "") or ""),
                "start_time": getattr(r, "start_time", None).isoformat() if getattr(r, "start_time", None) else None,
                "end_time": getattr(r, "end_time", None).isoformat() if getattr(r, "end_time", None) else None,
            }
        )
    return serialized


def probe_overdue_boundary() -> Dict[str, Any]:
    from core.algorithms.evaluation import compute_metrics
    from core.algorithms.types import ScheduleResult
    from core.services.scheduler.schedule_summary import _build_overdue_items

    batch = SimpleNamespace(batch_id="B001", priority="normal", due_date="2026-01-01")
    batches = {"B001": batch}
    finish = datetime(2026, 1, 1, 23, 59, 59, 500000)
    result = ScheduleResult(
        op_id=1,
        op_code="B001_01",
        batch_id="B001",
        seq=1,
        start_time=datetime(2026, 1, 1, 8, 0, 0),
        end_time=finish,
        source="internal",
    )
    metrics = compute_metrics([result], batches)
    summary = SimpleNamespace(warnings=[])
    overdue_items = _build_overdue_items(
        _FakeSummaryService(),
        batches=batches,
        finish_by_batch={"B001": finish},
        summary=summary,
    )
    return {
        "classification": "口径偏差",
        "finish_time": finish.isoformat(),
        "compute_metrics_overdue_count": int(metrics.overdue_count),
        "compute_metrics_total_tardiness_hours": float(metrics.total_tardiness_hours),
        "summary_overdue_items_count": int(len(overdue_items)),
        "split_confirmed": bool(int(metrics.overdue_count) == 1 and len(overdue_items) == 0),
    }


def probe_weighted_tardiness() -> Dict[str, Any]:
    from core.algorithms.evaluation import compute_metrics, objective_score
    from core.algorithms.types import ScheduleResult

    due_str = "2026-01-01"
    due_exclusive = datetime(2026, 1, 2, 0, 0, 0)

    batch_a = SimpleNamespace(batch_id="B_CRIT", priority="critical", due_date=due_str)
    batch_b = SimpleNamespace(batch_id="B_NORM", priority="normal", due_date=due_str)

    result_a = ScheduleResult(
        op_id=1,
        op_code="B_CRIT_01",
        batch_id="B_CRIT",
        seq=1,
        start_time=datetime(2026, 1, 1, 8, 0, 0),
        end_time=due_exclusive + timedelta(hours=10),
        source="internal",
    )
    result_b = ScheduleResult(
        op_id=2,
        op_code="B_NORM_01",
        batch_id="B_NORM",
        seq=1,
        start_time=datetime(2026, 1, 1, 8, 0, 0),
        end_time=due_exclusive + timedelta(hours=20),
        source="internal",
    )

    metrics_a = compute_metrics([result_a], {"B_CRIT": batch_a})
    metrics_b = compute_metrics([result_b], {"B_NORM": batch_b})

    current_a = objective_score("min_tardiness", metrics_a)
    current_b = objective_score("min_tardiness", metrics_b)
    weighted_a = (
        float(metrics_a.weighted_tardiness_hours),
        float(metrics_a.overdue_count),
        float(metrics_a.makespan_hours),
        float(metrics_a.changeover_count),
    )
    weighted_b = (
        float(metrics_b.weighted_tardiness_hours),
        float(metrics_b.overdue_count),
        float(metrics_b.makespan_hours),
        float(metrics_b.changeover_count),
    )

    return {
        "classification": "v2 目标态差异",
        "candidate_a": {
            "desc": "critical 批次超期 10h",
            "current_score": list(current_a),
            "weighted_score": list(weighted_a),
        },
        "candidate_b": {
            "desc": "normal 批次超期 20h",
            "current_score": list(current_b),
            "weighted_score": list(weighted_b),
        },
        "current_choice": "A" if current_a < current_b else "B",
        "weighted_choice": "A" if weighted_a < weighted_b else "B",
        "behavior_diff_confirmed": bool(current_a < current_b and weighted_b < weighted_a),
    }


def probe_multistart_scope() -> Dict[str, Any]:
    import core.services.scheduler.schedule_optimizer as schedule_optimizer

    original_scheduler_cls = schedule_optimizer.GreedyScheduler

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

    def _run_case(dispatch_mode_value: str) -> Dict[str, Any]:
        _RecordingScheduler.calls = []
        cfg = SimpleNamespace(
            sort_strategy="priority_first",
            priority_weight=0.4,
            due_weight=0.5,
            algo_mode="improve",
            objective="min_overdue",
            time_budget_seconds=1,
            dispatch_mode=dispatch_mode_value,
            dispatch_rule="slack",
            ortools_enabled="no",
        )
        cfg_svc = SimpleNamespace(
            VALID_STRATEGIES=("priority_first", "due_date_first", "weighted", "fifo"),
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
        schedule_optimizer.optimize_schedule(
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
        recorded = list(_RecordingScheduler.calls)
        return {
            "dispatch_mode_input": dispatch_mode_value,
            "unique_dispatch_modes": sorted({x["dispatch_mode"] for x in recorded}),
            "unique_dispatch_rules": sorted({x["dispatch_rule"] for x in recorded}),
            "call_count": int(len(recorded)),
        }

    schedule_optimizer.GreedyScheduler = _RecordingScheduler
    try:
        batch_order_case = _run_case("batch_order")
        sgs_case = _run_case("sgs")
    finally:
        schedule_optimizer.GreedyScheduler = original_scheduler_cls

    batch_order_locked = batch_order_case["unique_dispatch_modes"] == ["batch_order"]
    sgs_locked = sgs_case["unique_dispatch_modes"] == ["sgs"]

    return {
        "classification": "优化空间",
        "batch_order_case": batch_order_case,
        "sgs_case": sgs_case,
        "mode_lock_confirmed": bool(batch_order_locked and sgs_locked),
    }


def probe_improve_reproducibility() -> Dict[str, Any]:
    import core.services.scheduler.schedule_optimizer as schedule_optimizer
    import core.services.scheduler.schedule_optimizer_steps as schedule_optimizer_steps

    original_time_optimizer = schedule_optimizer.time.time
    original_time_steps = schedule_optimizer_steps.time.time

    cfg = SimpleNamespace(
        sort_strategy="priority_first",
        priority_weight=0.4,
        due_weight=0.5,
        algo_mode="improve",
        objective="min_overdue",
        time_budget_seconds=2,
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        ortools_enabled="no",
    )
    cfg_svc = SimpleNamespace(
        VALID_STRATEGIES=("priority_first", "due_date_first", "weighted", "fifo"),
        VALID_DISPATCH_RULES=("slack", "cr", "atc"),
    )
    batches = {
        "B001": SimpleNamespace(
            batch_id="B001",
            priority="critical",
            due_date=date(2026, 1, 1),
            ready_status="yes",
            ready_date=None,
            created_at=datetime(2025, 12, 31, 8, 0, 0),
            quantity=1,
        ),
        "B002": SimpleNamespace(
            batch_id="B002",
            priority="urgent",
            due_date=date(2026, 1, 2),
            ready_status="yes",
            ready_date=None,
            created_at=datetime(2025, 12, 31, 9, 0, 0),
            quantity=1,
        ),
        "B003": SimpleNamespace(
            batch_id="B003",
            priority="normal",
            due_date=date(2026, 1, 3),
            ready_status="yes",
            ready_date=None,
            created_at=datetime(2025, 12, 31, 10, 0, 0),
            quantity=1,
        ),
    }
    operations = [
        SimpleNamespace(
            id=1,
            op_code="B001_01",
            batch_id="B001",
            seq=1,
            source="internal",
            machine_id="M1",
            operator_id="O1",
            setup_hours=0.0,
            unit_hours=2.0,
            op_type_id="OT1",
            op_type_name="切削",
            supplier_id=None,
            ext_days=None,
            ext_group_id=None,
            ext_merge_mode=None,
            ext_group_total_days=None,
        ),
        SimpleNamespace(
            id=2,
            op_code="B002_01",
            batch_id="B002",
            seq=1,
            source="internal",
            machine_id="M1",
            operator_id="O1",
            setup_hours=0.0,
            unit_hours=2.0,
            op_type_id="OT1",
            op_type_name="切削",
            supplier_id=None,
            ext_days=None,
            ext_group_id=None,
            ext_merge_mode=None,
            ext_group_total_days=None,
        ),
        SimpleNamespace(
            id=3,
            op_code="B003_01",
            batch_id="B003",
            seq=1,
            source="internal",
            machine_id="M1",
            operator_id="O1",
            setup_hours=0.0,
            unit_hours=2.0,
            op_type_id="OT1",
            op_type_name="切削",
            supplier_id=None,
            ext_days=None,
            ext_group_id=None,
            ext_merge_mode=None,
            ext_group_total_days=None,
        ),
    ]

    def _run_once() -> Dict[str, Any]:
        clock = _DeterministicClock(start=2000.0, step=0.05)
        schedule_optimizer.time.time = clock.time
        schedule_optimizer_steps.time.time = clock.time
        outcome = schedule_optimizer.optimize_schedule(
            calendar_service=_StubCalendar(),
            cfg_svc=cfg_svc,
            cfg=cfg,
            algo_ops_to_schedule=operations,
            batches=batches,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_results=[],
            resource_pool=None,
            version=7,
            logger=None,
        )
        return {
            "best_score": list(outcome.best_score),
            "best_order": list(outcome.best_order),
            "results": _serialize_results(outcome.results),
        }

    try:
        run_a = _run_once()
        run_b = _run_once()
    finally:
        schedule_optimizer.time.time = original_time_optimizer
        schedule_optimizer_steps.time.time = original_time_steps

    return {
        "classification": "已确认可复现",
        "run_a": run_a,
        "run_b": run_b,
        "bit_exact_same": bool(run_a == run_b),
    }


def main() -> int:
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "repo_root": str(REPO_ROOT),
        "probes": {
            "overdue_boundary": probe_overdue_boundary(),
            "weighted_tardiness": probe_weighted_tardiness(),
            "multistart_scope": probe_multistart_scope(),
            "improve_reproducibility": probe_improve_reproducibility(),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(OUTPUT_PATH))
    print(
        json.dumps(
            {
                "overdue_boundary_split": payload["probes"]["overdue_boundary"]["split_confirmed"],
                "weighted_tardiness_behavior_diff": payload["probes"]["weighted_tardiness"]["behavior_diff_confirmed"],
                "multistart_mode_lock": payload["probes"]["multistart_scope"]["mode_lock_confirmed"],
                "improve_bit_exact_same": payload["probes"]["improve_reproducibility"]["bit_exact_same"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
