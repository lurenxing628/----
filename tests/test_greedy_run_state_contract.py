from __future__ import annotations

from datetime import datetime, timedelta

from core.algorithms.greedy.run_state import ScheduleRunState
from core.algorithms.types import ScheduleResult
from core.algorithms.value_domains import INTERNAL


def test_seed_result_missing_resources_records_warning_counts_without_blocking() -> None:
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    state = ScheduleRunState(base_time=base_time)
    result = ScheduleResult(
        op_id=10,
        op_code="OP10",
        batch_id="B1",
        seq=1,
        machine_id=None,
        operator_id="",
        start_time=base_time,
        end_time=base_time + timedelta(hours=2),
        source=INTERNAL,
        op_type_name="Cut",
    )

    state.record_seed_result(result)

    assert state.seed_count == 1
    assert state.scheduled_count == 1
    assert state.failed_count == 0
    assert state.batch_progress["B1"] == result.end_time
    assert state.missing_seed_machine_count == 1
    assert state.missing_seed_operator_count == 1
    assert not state.blocked_batches


def test_dispatch_success_advances_progress_and_records_internal_usage() -> None:
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    state = ScheduleRunState(base_time=base_time)
    result = ScheduleResult(
        op_id=11,
        op_code="OP11",
        batch_id="B1",
        seq=1,
        machine_id="M1",
        operator_id="O1",
        start_time=base_time,
        end_time=base_time + timedelta(hours=1),
        source=INTERNAL,
        op_type_name="Cut",
    )

    state.record_dispatch_success(result)

    assert state.scheduled_count == 1
    assert state.batch_progress["B1"] == result.end_time
    assert state.machine_busy_hours["M1"] == 1.0
    assert state.operator_busy_hours["O1"] == 1.0
    assert state.last_op_type_by_machine["M1"] == "Cut"
