"""未选中在制工序仍占用实际资源，模拟排产不写库。"""

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from core.services.scheduler.config.config_service import ConfigService
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact
from core.services.scheduler.execution.execution_snapshot import build_execution_snapshot
from core.services.scheduler.run import schedule_orchestrator
from core.services.scheduler.run.schedule_execution_resource_facts import resource_execution_snapshot
from core.services.scheduler.schedule_service import ScheduleService
from tests.schedule.service.unselected_execution_guardrails_support import (
    execution_state,
    persistent_state,
    preview,
    rows,
    seed_plan,
    start,
)


@pytest.mark.parametrize('machine_id,operator_id', [("M1", "O1")])
@pytest.mark.parametrize('graph_mode', ["off"])
def test_unselected_processing_reserves_each_actual_resource(schema_conn, machine_id, operator_id, graph_mode):
    conn = schema_conn
    seed_plan(conn)
    conn.execute("UPDATE BatchOperations SET machine_id = ?, operator_id = ? WHERE id = 20",
                 (machine_id, operator_id))
    conn.commit()
    ConfigService(conn).ensure_defaults()
    conn.execute("UPDATE ScheduleConfig SET config_value = ? WHERE config_key = 'graph_analysis_mode'", (graph_mode,))
    conn.commit()
    start(conn)
    before = execution_state(conn)
    previous_rows = rows(conn, 1)
    scheduled, _ = preview(conn)
    assert set(scheduled) == {20}
    assert scheduled[20]["start_time"] == "2026-09-08 09:00:00"
    assert execution_state(conn) == before
    assert rows(conn, 1) == previous_rows


def test_simulate_only_reserves_without_writing_a_version(schema_conn, monkeypatch):
    seed_plan(schema_conn)
    start(schema_conn)
    before = persistent_state(schema_conn)
    actual_before = execution_state(schema_conn)
    original = schedule_orchestrator.run_candidate_comparison
    outcomes = []

    def capture(**kwargs):
        outcome = original(**kwargs)
        outcomes.extend(outcome.candidates)
        return outcome

    monkeypatch.setattr(schedule_orchestrator, "run_candidate_comparison", capture)
    result = ScheduleService(schema_conn).run_schedule(["B2"], start_dt="2026-09-08 08:30:00", simulate=True)
    assert result["is_simulation"] is True
    assert result["version"] is None
    assert persistent_state(schema_conn) == before
    assert execution_state(schema_conn) == actual_before
    assert outcomes and all([row.op_id for row in item.results] == [20] for item in outcomes)
    assert all(item.results[0].start_time.strftime("%H:%M") == "09:00" for item in outcomes)


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
