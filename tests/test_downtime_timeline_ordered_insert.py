from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest

from core.algorithms.greedy.dispatch.runtime_state import accumulate_busy_hours, update_machine_last_state
from core.algorithms.greedy.downtime import occupy_resource
from core.algorithms.greedy.scheduler import GreedyScheduler


@dataclass
class _Calendar:
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id=None):
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id=None):
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id=None):
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id=None, operator_id=None):
        return dt + timedelta(days=float(days or 0.0))


def test_occupy_resource_keeps_segments_sorted():
    timeline = {}
    base = datetime(2026, 1, 1, 8, 0, 0)
    occupy_resource(timeline, "M1", base + timedelta(hours=2), base + timedelta(hours=3))
    occupy_resource(timeline, "M1", base, base + timedelta(hours=1))
    occupy_resource(timeline, "M1", base + timedelta(hours=1), base + timedelta(hours=2))

    assert timeline["M1"] == [
        (base, base + timedelta(hours=1)),
        (base + timedelta(hours=1), base + timedelta(hours=2)),
        (base + timedelta(hours=2), base + timedelta(hours=3)),
    ]


def test_runtime_state_helpers_handle_seed_and_dispatch_modes():
    base = datetime(2026, 1, 1, 8, 0, 0)
    machine_busy_hours = {}
    operator_busy_hours = {}
    duration = accumulate_busy_hours(
        machine_busy_hours=machine_busy_hours,
        operator_busy_hours=operator_busy_hours,
        machine_id="M1",
        operator_id="O1",
        start_time=base,
        end_time=base + timedelta(hours=2),
    )
    assert duration == 2.0
    assert machine_busy_hours == {"M1": 2.0}
    assert operator_busy_hours == {"O1": 2.0}

    last_end_by_machine = {"M1": base + timedelta(hours=4)}
    last_op_type_by_machine = {"M1": "旧工种"}
    update_machine_last_state(
        last_end_by_machine=last_end_by_machine,
        last_op_type_by_machine=last_op_type_by_machine,
        machine_id="M1",
        end_time=base + timedelta(hours=3),
        op_type_name="新工种",
        seed_mode=True,
    )
    assert last_end_by_machine["M1"] == base + timedelta(hours=4)
    assert last_op_type_by_machine["M1"] == "旧工种"

    update_machine_last_state(
        last_end_by_machine=last_end_by_machine,
        last_op_type_by_machine=last_op_type_by_machine,
        machine_id="M1",
        end_time=base + timedelta(hours=5),
        op_type_name="新工种",
        seed_mode=True,
    )
    assert last_end_by_machine["M1"] == base + timedelta(hours=5)
    assert last_op_type_by_machine["M1"] == "新工种"

    update_machine_last_state(
        last_end_by_machine=last_end_by_machine,
        last_op_type_by_machine=last_op_type_by_machine,
        machine_id="M1",
        end_time=base + timedelta(hours=4),
        op_type_name="派工工种",
        seed_mode=False,
    )
    assert last_end_by_machine["M1"] == base + timedelta(hours=5)
    assert last_op_type_by_machine["M1"] == "派工工种"


def test_update_machine_last_state_rejects_non_datetime_end_time():
    with pytest.raises(TypeError):
        update_machine_last_state(
            last_end_by_machine={},
            last_op_type_by_machine={},
            machine_id="M1",
            end_time=cast(datetime, "2026-01-01 08:00:00"),
            op_type_name="工种",
            seed_mode=True,
        )


def test_accumulate_busy_hours_rejects_non_datetime():
    base = datetime(2026, 1, 1, 8, 0, 0)

    bad_cases = [
        {
            "start_time": cast(datetime, "2026-01-01 08:00:00"),
            "end_time": base,
        },
        {
            "start_time": base,
            "end_time": cast(datetime, "2026-01-01 09:00:00"),
        },
    ]

    for bad_case in bad_cases:
        with pytest.raises(TypeError):
            accumulate_busy_hours(
                machine_busy_hours={},
                operator_busy_hours={},
                machine_id="M1",
                operator_id="O1",
                **bad_case,
            )


def test_schedule_normalizes_unordered_machine_downtimes_once():
    scheduler = GreedyScheduler(calendar_service=_Calendar())
    base = datetime(2026, 1, 1, 8, 0, 0)
    batch = SimpleNamespace(
        batch_id="B1",
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B1",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_id="OT1",
        op_type_name="车削",
    )

    results, summary, _strategy, _params = scheduler.schedule(
        operations=[op],
        batches={"B1": batch},
        start_dt=base,
        machine_downtimes={
            "M1": [
                (base + timedelta(hours=2), base + timedelta(hours=3)),
                (base, base + timedelta(hours=1)),
                (base + timedelta(hours=1), base + timedelta(hours=2)),
            ]
        },
    )

    assert summary.failed_ops == 0
    assert len(results) == 1
    assert results[0].start_time == base + timedelta(hours=3)
