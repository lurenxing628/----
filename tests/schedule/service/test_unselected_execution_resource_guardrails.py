"""未选中在制工序仍占用实际资源，模拟排产不写库。"""

import pytest

import core.services.scheduler.schedule_service as schedule_service_mod
from core.services.scheduler.config.config_service import ConfigService
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
    original = schedule_service_mod.optimize_schedule
    outcomes = []

    def capture(**kwargs):
        outcome = original(**kwargs)
        outcomes.append(outcome)
        return outcome

    monkeypatch.setattr(schedule_service_mod, "optimize_schedule", capture)
    result = ScheduleService(schema_conn).run_schedule(["B2"], start_dt="2026-09-08 08:30:00", simulate=True)
    assert result["is_simulation"] is True
    assert result["version"] is None
    assert persistent_state(schema_conn) == before
    assert execution_state(schema_conn) == actual_before
    assert outcomes and all([row.op_id for row in item.results] == [20] for item in outcomes)
    assert all(item.results[0].start_time.strftime("%H:%M") == "09:00" for item in outcomes)
