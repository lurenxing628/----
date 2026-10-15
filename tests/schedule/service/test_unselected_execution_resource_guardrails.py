"""执行快照保留实际保护内容和原预约区间的事实差异。"""

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from core.services.scheduler.execution.execution_fact_provider import ExecutionFact
from core.services.scheduler.execution.execution_snapshot import build_execution_snapshot
from core.services.scheduler.run.schedule_execution_resource_facts import resource_execution_snapshot


def test_execution_snapshot_covers_actual_protection_and_original_reservation_content():
    start_time = datetime(2026, 9, 8, 8)
    fact = ExecutionFact(
        op_id=10, batch_id="B1", actual_status="processing", actual_start_time=start_time,
        actual_end_time=None, actual_machine_id="M1", actual_operator_id="O1",
        state_revision="10:1:100", schedule_version=1, schedule_id=100,
        source_table="schedule", effective_plan_role="adopted", target_quantity=1,
        remaining_quantity=1, execution_effective_intervals=((start_time, start_time + timedelta(hours=1)),),
        execution_protection_content={"scope_task": {"task_ref": "original-task", "source": "internal"},
            "ledger_revision": 5,
            "projection": {"reports": [{"completed_quantity": 1}], "data_gaps": []},
            "resources": {"original-machine": {"kind": "machine", "available": True, "business_code": "M1"}}},
    )
    original = build_execution_snapshot({10: fact}, [10]).revision
    assert build_execution_snapshot({10: fact}, [10, 10]).revision == original
    for changed in (
        replace(fact, actual_start_time=start_time + timedelta(seconds=1)),
        replace(fact, actual_machine_id="M2"),
        replace(fact, remaining_quantity=True),
        replace(fact, target_quantity=1.0),
        replace(fact, execution_effective_intervals=((start_time, start_time + timedelta(hours=2)),)),
        replace(fact, execution_protection_reasons=("pending-reconciliation",)),
        replace(fact, execution_protection_content=dict(fact.execution_protection_content,
            projection={"reports": [{"completed_quantity": True}], "data_gaps": []})),
        replace(fact, execution_protection_content=dict(fact.execution_protection_content,
            resources={"original-machine": {"kind": "machine", "available": 1, "business_code": "M1"}})),
    ):
        assert build_execution_snapshot({10: changed}, [10]).revision != original
    arrangement = {"schedule_id": 100, "version": 1, "op_id": 10,
                   "start_time": "2026-09-08 08:00:00", "end_time": "2026-09-08 09:00:00",
                   "machine_id": "M1", "operator_id": "O1", "total_hours": 1.0}
    resource_original = resource_execution_snapshot({10: fact}, {10: arrangement}).revision
    for changed in (dict(arrangement, end_time="2026-09-08 10:00:00"),
                    dict(arrangement, operator_id="O2"), dict(arrangement, total_hours=True)):
        assert resource_execution_snapshot({10: fact}, {10: changed}).revision != resource_original
