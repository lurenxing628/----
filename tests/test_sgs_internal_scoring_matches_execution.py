from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

from core.algorithms import GreedyScheduler, ScheduleResult
from core.algorithms.greedy.dispatch import sgs as sgs_module


@dataclass
class _Calendar:
    efficiency: float = 1.0

    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id=None):
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id=None):
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id=None):
        return self.efficiency

    def add_calendar_days(self, dt: datetime, days: float, machine_id=None, operator_id=None):
        return dt + timedelta(days=float(days or 0.0))


@dataclass
class _Config:
    auto_assign_enabled: str = "no"


def _batch(batch_id: str):
    return SimpleNamespace(
        batch_id=batch_id,
        priority="normal",
        due_date="2026-01-02",
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )


def test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order():
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    scheduler = GreedyScheduler(calendar_service=_Calendar(), config_service=_Config())

    batches = {"B_A": _batch("B_A"), "B_B": _batch("B_B")}
    operations = [
        SimpleNamespace(
            id=1,
            op_code="OP_A",
            batch_id="B_A",
            seq=1,
            source="internal",
            machine_id="M1",
            operator_id="O1",
            setup_hours=1.0,
            unit_hours=0.0,
            op_type_id="OT1",
            op_type_name="车削",
        ),
        SimpleNamespace(
            id=2,
            op_code="OP_B",
            batch_id="B_B",
            seq=1,
            source="internal",
            machine_id="M2",
            operator_id="O2",
            setup_hours=1.0,
            unit_hours=0.0,
            op_type_id="OT1",
            op_type_name="车削",
        ),
    ]
    seed_results = [
        ScheduleResult(
            op_id=101,
            op_code="SEED_M1_1",
            batch_id="SEED",
            seq=1,
            machine_id="M1",
            operator_id=None,
            start_time=start_dt,
            end_time=start_dt + timedelta(hours=1),
            source="internal",
            op_type_name=None,
        ),
        ScheduleResult(
            op_id=102,
            op_code="SEED_O1",
            batch_id="SEED",
            seq=2,
            machine_id=None,
            operator_id="O1",
            start_time=start_dt + timedelta(hours=1),
            end_time=start_dt + timedelta(hours=2),
            source="internal",
            op_type_name=None,
        ),
        ScheduleResult(
            op_id=103,
            op_code="SEED_M1_2",
            batch_id="SEED",
            seq=3,
            machine_id="M1",
            operator_id=None,
            start_time=start_dt + timedelta(hours=2),
            end_time=start_dt + timedelta(hours=3),
            source="internal",
            op_type_name=None,
        ),
        ScheduleResult(
            op_id=104,
            op_code="SEED_B",
            batch_id="SEED",
            seq=4,
            machine_id="M2",
            operator_id="O2",
            start_time=start_dt,
            end_time=start_dt + timedelta(hours=2),
            source="internal",
            op_type_name=None,
        ),
    ]

    def _dispatch_key_by_end(inp):
        return (inp.est_end.timestamp(), float(inp.batch_order), float(inp.seq), float(inp.op_id))

    with mock.patch.object(sgs_module, "estimate_internal_slot", wraps=sgs_module.estimate_internal_slot) as wrapped, mock.patch.object(
        sgs_module,
        "build_dispatch_key",
        side_effect=_dispatch_key_by_end,
    ):
        results, summary, _strategy, _used_params = scheduler.schedule(
            operations=operations,
            batches=batches,
            start_dt=start_dt,
            dispatch_mode="sgs",
            dispatch_rule="slack",
            batch_order_override=["B_A", "B_B"],
            seed_results=seed_results,
        )

    assert summary.failed_ops == 0
    assert wrapped.call_count >= 2, "SGS 评分阶段应调用统一估算器"
    non_seed_results = [result for result in results if result.batch_id in {"B_A", "B_B"}]
    assert [result.batch_id for result in non_seed_results] == ["B_B", "B_A"]


def test_sgs_probe_efficiency_fallback_does_not_pollute_formal_counter():
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    scheduler = GreedyScheduler(calendar_service=_Calendar(efficiency=float("inf")), config_service={"auto_assign_enabled": "yes"})

    batches = {"B1": _batch("B1")}
    operations = [
        SimpleNamespace(
            id=1,
            op_code="OP1",
            batch_id="B1",
            seq=1,
            source="internal",
            machine_id="",
            operator_id="",
            setup_hours=1.0,
            unit_hours=0.0,
            op_type_id="OT1",
            op_type_name="车削",
        )
    ]
    resource_pool = {
        "machines_by_op_type": {"OT1": ["M1"]},
        "operators_by_machine": {"M1": ["O1"]},
        "machines_by_operator": {},
        "pair_rank": {},
    }

    results, summary, _strategy, _used_params = scheduler.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        dispatch_mode="sgs",
        dispatch_rule="slack",
        resource_pool=resource_pool,
    )

    assert summary.failed_ops == 0
    assert len(results) == 1
    fallback_counts = (scheduler._last_algo_stats.get("fallback_counts") or {})
    assert int(fallback_counts.get("internal_efficiency_fallback_count") or 0) == 1
