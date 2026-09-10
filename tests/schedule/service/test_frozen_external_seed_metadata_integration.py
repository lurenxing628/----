"""A14: real freeze collection, filtered optimizer input, greedy dispatch and persistence."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from core.algorithm_contracts.types import ScheduleResult
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.infrastructure.database import get_connection
from core.services.scheduler import BatchService, ConfigService, ScheduleService
from core.services.scheduler import schedule_service as service_module
from core.services.scheduler.operation_execution_feedback_service import (
    ExecutionFeedbackContext,
    OperationExecutionFeedbackService,
)


def _prepare_plan(conn, *, dispatch_mode, merge_mode="separate", with_execution=False):
    conn.execute("INSERT INTO Parts(part_no, part_name, route_parsed) VALUES ('P1', 'Part', 'yes')")
    conn.execute(
        "INSERT INTO ExternalGroups(group_id, part_no, start_seq, end_seq, merge_mode, total_days) "
        "VALUES ('G1', 'P1', 10, 20, ?, 3)",
        (merge_mode,),
    )
    for seq in (10, 20, 30):
        conn.execute(
            "INSERT INTO PartOperations(part_no, seq, op_type_name, source, ext_days, ext_group_id) "
            "VALUES ('P1', ?, 'External', 'external', ?, ?)",
            (seq, 3 if seq < 30 else 1, 'G1' if seq < 30 else None),
        )
    conn.commit()
    BatchService(conn).create_batch_from_template(
        batch_id="B1", part_no="P1", quantity=1, due_date="2026-09-30", ready_status="yes",
    )
    if with_execution:
        conn.executescript("""
            INSERT INTO Machines(machine_id, name, status) VALUES ('M1', 'Machine', 'active');
            INSERT INTO Operators(operator_id, name, status) VALUES ('O1', 'Operator', 'active');
            INSERT INTO OperatorMachine(operator_id, machine_id) VALUES ('O1', 'M1');
            INSERT INTO Batches(batch_id, part_no, quantity, due_date, ready_status, status)
            VALUES ('B2', 'P1', 1, '2026-09-30', 'yes', 'pending');
            INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_name, source, machine_id, operator_id, setup_hours)
            VALUES ('INTERNAL1', 'B2', 10, 'Internal', 'internal', 'M1', 'O1', 1);
        """)
        conn.commit()
    config = ConfigService(conn)
    config.restore_default()
    config.set_algo_mode("greedy")
    config.set_dispatch(dispatch_mode, "slack")
    config.set_freeze_window("no", 0)
    first = ScheduleService(conn).run_schedule(["B1", "B2"] if with_execution else ["B1"], start_dt="2026-09-08 08:00:00")
    return config, first


def _rows(conn, version):
    return [dict(row) for row in conn.execute(
        "SELECT * FROM Schedule WHERE version=? ORDER BY op_id", (version,),
    ).fetchall()]


def _observe_production(monkeypatch):
    captured = {"inputs": [], "calls": []}
    collect = service_module.collect_schedule_run_input
    schedule = GreedyScheduler.schedule

    def observe_input(*args, **kwargs):
        result = collect(*args, **kwargs)
        captured["inputs"].append(result)
        return result

    def observe_schedule(self, *args, **kwargs):
        outcome = schedule(self, *args, **kwargs)
        captured["calls"].append((kwargs, outcome, self._last_algo_stats))
        return outcome

    monkeypatch.setattr(service_module, "collect_schedule_run_input", observe_input)
    monkeypatch.setattr(GreedyScheduler, "schedule", observe_schedule)
    return captured


@pytest.mark.parametrize("dispatch_mode", ["batch_order", "sgs"])
def test_production_partial_frozen_group_keeps_identity_and_all_results(db_path, monkeypatch, dispatch_mode):
    conn = get_connection(db_path)
    try:
        config, first = _prepare_plan(conn, dispatch_mode=dispatch_mode)
        old_rows = _rows(conn, first["version"])
        old_history = dict(conn.execute("SELECT * FROM ScheduleHistory WHERE version=?", (first["version"],)).fetchone())
        # A real version-to-version template change leaves only the first group member in the window.
        conn.execute("UPDATE ExternalGroups SET merge_mode='merged' WHERE group_id='G1'")
        conn.commit()
        config.set_freeze_window("yes", 1)
        captured = _observe_production(monkeypatch)

        result = ScheduleService(conn).run_schedule(["B1"], start_dt="2026-09-08 08:00:00")

        collected = captured["inputs"][0]
        frozen_id = old_rows[0]["op_id"]
        assert collected.frozen_op_ids == {frozen_id}
        assert collected.freeze_meta["freeze_application_status"] == "applied"
        assert frozen_id not in {op.id for op in collected.algo_ops_to_schedule}
        assert captured["calls"]
        for kwargs, outcome, stats in captured["calls"]:
            assert frozen_id not in {op.id for op in kwargs["operations"]}
            assert [seed.op_id for seed in kwargs["seed_results"]] == [frozen_id]
            results, summary, _, _ = outcome
            assert summary.failed_ops == 0
            assert len(results) == summary.total_ops == summary.scheduled_ops == 3
            assert stats["fallback_counts"].get("seed_external_group_cache_rebuilt_count") == 1
            assert all(type(row) is ScheduleResult for row in results)
            assert asdict(results[0]) == asdict(kwargs["seed_results"][0])
            assert not any(key.startswith("_external_group") for row in results for key in vars(row))

        new_rows = _rows(conn, result["version"])
        assert len(new_rows) == 3
        assert new_rows[0]["lock_status"] == "locked"
        assert new_rows[1]["lock_status"] == "unlocked"
        assert [(row["start_time"], row["end_time"]) for row in new_rows[:2]] == [
            (old_rows[0]["start_time"], old_rows[0]["end_time"]),
        ] * 2
        assert new_rows[2]["start_time"] == old_rows[0]["end_time"]
        assert _rows(conn, first["version"]) == old_rows
        assert dict(conn.execute("SELECT * FROM ScheduleHistory WHERE version=?", (first["version"],)).fetchone()) == old_history
        assert conn.execute("SELECT COUNT(*) FROM OperationExecutionEvents").fetchone()[0] == 0
        assert "_external_group_metadata" not in str(result)
        assert "_external_group_identity" not in str(result)
    finally:
        conn.close()


@pytest.mark.parametrize("merge_mode,freeze_days", [("merged", 1), ("separate", 1), ("merged", 0)])
def test_healthy_full_group_separate_and_unfrozen_schedules_keep_existing_rows(db_path, merge_mode, freeze_days):
    conn = get_connection(db_path)
    try:
        config, first = _prepare_plan(conn, dispatch_mode="batch_order", merge_mode=merge_mode)
        before = _rows(conn, first["version"])
        config.set_freeze_window("yes" if freeze_days else "no", freeze_days)
        result = ScheduleService(conn).run_schedule(["B1"], start_dt="2026-09-08 08:00:00")
        after = _rows(conn, result["version"])
        keys = ("op_id", "machine_id", "operator_id", "start_time", "end_time")
        assert [{key: row[key] for key in keys} for row in after] == [{key: row[key] for key in keys} for row in before]
        assert _rows(conn, first["version"]) == before
        locked_count = sum(row["lock_status"] == "locked" for row in after)
        assert locked_count == (0 if not freeze_days else 2 if merge_mode == "merged" else 1)
        assert set(result) == set(first)
    finally:
        conn.close()


def test_production_freeze_metadata_keeps_existing_execution_events_and_fixed_fields(db_path, monkeypatch):
    conn = get_connection(db_path)
    try:
        config, first = _prepare_plan(conn, dispatch_mode="sgs", with_execution=True)
        fixed_row = _rows(conn, first["version"])[-1]
        op_id = fixed_row["op_id"]
        OperationExecutionFeedbackService(conn).start_operation(
            ExecutionFeedbackContext(
                schedule_version=first["version"], schedule_id=fixed_row["id"], op_id=op_id,
                batch_id="B2", expected_state_revision=f"{op_id}:0:0", created_by="pytest",
                idempotency_key="start-internal", requested_plan_role="adopted", source_table="schedule",
                effective_plan_role="adopted", scenario_id=None,
            ),
            event_time=fixed_row["start_time"], machine_id="M1", operator_id="O1",
        )
        before_events = [dict(row) for row in conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")]
        before_rows = _rows(conn, first["version"])
        conn.execute("UPDATE ExternalGroups SET merge_mode='merged' WHERE group_id='G1'")
        conn.commit()
        config.set_freeze_window("yes", 1)
        captured = _observe_production(monkeypatch)
        result = ScheduleService(conn).run_schedule(["B1", "B2"], start_dt="2026-09-08 08:00:00")
        collected = captured["inputs"][0]
        assert collected.execution_fixed_op_ids == {op_id}
        assert op_id in collected.frozen_op_ids
        fixed_seed = next(seed for seed in collected.seed_results if seed["op_id"] == op_id)
        assert fixed_seed["seed_source"] == "execution_fact"
        assert fixed_seed["state_revision"]
        assert "_external_group_metadata" not in fixed_seed
        after = _rows(conn, result["version"])
        assert len(after) == 4
        assert after[-1]["lock_status"] == "locked"
        for key in ("op_id", "start_time", "end_time", "machine_id", "operator_id"):
            assert after[-1][key] == fixed_row[key]
        assert [dict(row) for row in conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")] == before_events
        assert len(before_events) == 1
        assert _rows(conn, first["version"]) == before_rows
    finally:
        conn.close()
