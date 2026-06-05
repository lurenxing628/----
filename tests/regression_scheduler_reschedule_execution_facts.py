"""回归测试：ScheduleService.run_schedule 重排时如何消化执行事实(execution_fact)——已开工工序作 seed_source=execution_fact 种子并固定(fixed_op_ids/locked)、已完工从优化器输入剔除但保留为种子、暂停固定且保留 paused、
执行异常且建议重排时整单拦截(6003 execution_exception_blocks_auto_reschedule)、被新版本取代的旧执行事实不再作种子、全部工序被执行事实固定时报 all_operations_fixed；
还守护重排前后 execution_snapshot 快照与现场状态变更复查(execution_state_changed)、simulate 不落正式版本。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import core.services.scheduler.schedule_service as schedule_service_mod
from core.infrastructure.errors import AppError, ValidationError
from core.models.operation_execution_scope import OperationExecutionScope
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.services.scheduler.execution_fact_provider import ExecutionFactProvider
from core.services.scheduler.operation_execution_feedback_service import OperationExecutionFeedbackService
from core.services.scheduler.schedule_service import ScheduleService
from data.repositories.operation_execution_event_repo import OperationExecutionEventRepo
from tests.regression_scheduler_reschedule_execution_minimum_guardrails import (
    _connect,
    _context,
    _counts,
    _seed_two_operation_plan,
)


def _history_summary(conn, version: int):
    row = conn.execute(
        "SELECT result_summary FROM ScheduleHistory WHERE version = ?",
        (int(version),),
    ).fetchone()
    assert row is not None
    return json.loads(row["result_summary"])


def _execution_scope(op_id: int = 10) -> OperationExecutionScope:
    return OperationExecutionScope.from_values(
        schedule_version=1,
        schedule_id=100 if int(op_id) == 10 else 101,
        op_id=int(op_id),
        batch_id="B1",
        source_table=SOURCE_SCHEDULE,
        effective_plan_role=ROLE_ADOPTED,
    )


def _execution_status(conn, op_id: int) -> str:
    scope = _execution_scope(op_id)
    state = OperationExecutionFeedbackService(conn).get_execution_state_for_scopes([scope]).get(scope)
    assert state is not None
    return str(state.current_status)


def _batch_operation_status(conn, op_id: int) -> str:
    row = conn.execute("SELECT status FROM BatchOperations WHERE id = ?", (int(op_id),)).fetchone()
    assert row is not None
    return str(row["status"])


def _seed_second_version_plan(conn) -> None:
    conn.executescript(
        """
        INSERT INTO ScheduleVersionSeq(version) VALUES (2);

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES
            (200, 10, 'M2', 'O2', '2026-05-02 08:00:00', '2026-05-02 09:00:00', 'unlocked', 2),
            (201, 20, 'M1', 'O1', '2026-05-02 09:00:00', '2026-05-02 10:00:00', 'unlocked', 2);

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (2, 'priority_first', 1, 2, 'success', '{}', 'pytest');
        """
    )
    conn.commit()


def test_reschedule_records_execution_snapshot_and_execution_seed_source(tmp_path: Path, monkeypatch) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        conn.execute("UPDATE BatchOperations SET status = 'processing' WHERE id = 10")
        conn.execute("UPDATE BatchOperations SET status = 'pending' WHERE id = 20")
        conn.commit()
        OperationExecutionFeedbackService(conn).start_operation(
            _context(),
            event_time="2026-05-01 08:30:00",
            operator_id="O1",
            machine_id="M1",
        )
        original_optimize = schedule_service_mod.optimize_schedule
        captured_calls = []

        def optimize_with_capture(**kwargs):
            captured_calls.append(
                {
                    "seed_results": list(kwargs.get("seed_results") or []),
                    "graph_ready_context": kwargs.get("graph_ready_context"),
                }
            )
            return original_optimize(**kwargs)

        monkeypatch.setattr(schedule_service_mod, "optimize_schedule", optimize_with_capture)

        result = ScheduleService(conn).run_schedule(
            ["B1"],
            start_dt="2026-05-01 08:00:00",
            created_by="pytest",
        )

        assert len(captured_calls) >= 2
        graph_calls = [call for call in captured_calls if call["graph_ready_context"] is not None]
        assert graph_calls
        for call in captured_calls:
            seeds = {int(seed["op_id"]): seed for seed in call["seed_results"]}
            assert seeds[10]["seed_source"] == "execution_fact"
            assert seeds[10]["state_revision"].startswith("10:1:")
            graph_ready_context = call["graph_ready_context"]
            if graph_ready_context is not None:
                assert 10 in graph_ready_context["fixed_op_ids"]

        candidate_rows = conn.execute(
            """
            SELECT rows.op_id, rows.lock_status
            FROM ScheduleCandidateRows rows
            JOIN ScheduleCandidate candidate
              ON candidate.id = rows.candidate_id
             AND candidate.version = rows.version
            WHERE rows.version = ?
              AND rows.op_id = 10
              AND candidate.candidate_kind = 'critical_chain'
            """,
            (int(result["version"]),),
        ).fetchall()
        assert candidate_rows
        assert {row["lock_status"] for row in candidate_rows} == {"locked"}

        summary = _history_summary(conn, int(result["version"]))
        snapshot = summary["execution_snapshot"]
        assert snapshot["execution_snapshot_revision"].startswith("execution-snapshot:")
        assert snapshot["execution_snapshot_op_ids"] == [10, 20]
        assert snapshot["execution_snapshot_op_count"] == 2
        assert snapshot["execution_snapshot_op_ids_sample"] == [10, 20]
        assert snapshot["execution_snapshot_op_ids_truncated"] is False
        assert _execution_status(conn, 10) == "processing"
        assert _batch_operation_status(conn, 10) == "processing"
        assert _batch_operation_status(conn, 20) == "scheduled"
    finally:
        conn.close()


def test_reschedule_ignores_superseded_same_op_execution_fact(tmp_path: Path, monkeypatch) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        _seed_second_version_plan(conn)
        OperationExecutionEventRepo(conn).insert_event(
            {
                "schedule_version": 1,
                "schedule_id": 100,
                "op_id": 10,
                "batch_id": "B1",
                "source_table": "schedule",
                "effective_plan_role": "adopted",
                "scenario_id": None,
                "event_type": "start",
                "reported_status": "processing",
                "event_time": "2026-05-01 08:30:00",
                "actual_machine_id": "M1",
                "actual_operator_id": "O1",
                "created_by": "pytest",
                "idempotency_key": "legacy-v1-start-for-reschedule",
                "request_fingerprint": "legacy-v1-start-for-reschedule",
                "previous_state_revision": "10:0:0",
            }
        )
        conn.commit()
        original_optimize = schedule_service_mod.optimize_schedule
        captured_seed_op_ids = []

        def optimize_with_capture(**kwargs):
            captured_seed_op_ids.append([
                int(seed.get("op_id") or 0)
                for seed in list(kwargs.get("seed_results") or [])
                if isinstance(seed, dict)
            ])
            return original_optimize(**kwargs)

        monkeypatch.setattr(schedule_service_mod, "optimize_schedule", optimize_with_capture)

        result = ScheduleService(conn).run_schedule(
            ["B1"],
            start_dt="2026-05-02 08:00:00",
            created_by="pytest",
        )

        assert int(result["version"]) > 2
        assert captured_seed_op_ids
        assert all(10 not in seed_ids for seed_ids in captured_seed_op_ids)
        assert ExecutionFactProvider(conn).facts_by_op_id_for_scopes([_execution_scope(10)])[10].last_event_schedule_version == 1
    finally:
        conn.close()


def test_paused_operation_is_fixed_and_keeps_execution_status(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        feedback = OperationExecutionFeedbackService(conn)
        started = feedback.start_operation(
            _context(),
            event_time="2026-05-01 08:20:00",
            operator_id="O1",
            machine_id="M1",
        )
        feedback.pause_operation(
            _context(revision=started.state_revision, key="pause-key"),
            event_time="2026-05-01 08:35:00",
            reason_code="equipment",
            remark="设备需要检查",
        )

        result = ScheduleService(conn).run_schedule(
            ["B1"],
            start_dt="2026-05-01 08:00:00",
            created_by="pytest",
        )

        rows = conn.execute(
            """
            SELECT op_id, machine_id, operator_id, start_time, lock_status
            FROM Schedule
            WHERE version = ?
            ORDER BY op_id
            """,
            (int(result["version"]),),
        ).fetchall()
        by_op = {int(row["op_id"]): dict(row) for row in rows}
        assert by_op[10]["start_time"] == "2026-05-01 08:20:00"
        assert by_op[10]["machine_id"] == "M1"
        assert by_op[10]["operator_id"] == "O1"
        assert by_op[10]["lock_status"] == "locked"
        assert _execution_status(conn, 10) == "paused"
    finally:
        conn.close()


def test_exception_operation_blocks_reschedule_in_item13_command(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        feedback = OperationExecutionFeedbackService(conn)
        started = feedback.start_operation(
            _context(),
            event_time="2026-05-01 08:20:00",
            operator_id="O1",
            machine_id="M1",
        )
        feedback.report_exception(
            _context(revision=started.state_revision, key="exception-key"),
            event_time="2026-05-01 08:30:00",
            reason_code="equipment",
            severity="high",
            impact_minutes=30,
            affected_machine_id="M1",
            affected_operator_id="O1",
            handling_status="new",
            suggest_reschedule="yes",
            remark="设备异常，等待处理",
        )
        fact = ExecutionFactProvider(conn).facts_by_op_id_for_scopes([_execution_scope(10)])[10]
        assert fact.latest_exception_impact_minutes == 30
        assert fact.latest_exception_handling_status == "new"
        assert fact.latest_exception_suggest_reschedule is True
        before = _counts(conn)

        with pytest.raises(AppError) as exc_info:
            ScheduleService(conn).run_schedule(
                ["B1"],
                start_dt="2026-05-01 08:00:00",
                created_by="pytest",
            )

        assert exc_info.value.code.value == "6003"
        assert exc_info.value.details["reason"] == "execution_exception_blocks_auto_reschedule"
        assert exc_info.value.details["op_ids"] == [10]
        assert "异常中" in exc_info.value.message
        assert _counts(conn) == before
        assert _execution_status(conn, 10) == "exception"
    finally:
        conn.close()


def test_completed_operation_is_removed_from_optimizer_inputs_and_kept_as_execution_seed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        feedback = OperationExecutionFeedbackService(conn)
        started = feedback.start_operation(
            _context(),
            event_time="2026-05-01 08:20:00",
            operator_id="O1",
            machine_id="M1",
        )
        feedback.finish_operation(
            _context(revision=started.state_revision, key="finish-key"),
            event_time="2026-05-01 10:30:00",
            quantity_done=10,
        )
        conn.execute("UPDATE BatchOperations SET status = 'completed' WHERE id = 10")
        conn.execute("UPDATE BatchOperations SET status = 'pending' WHERE id = 20")
        conn.commit()
        original_optimize = schedule_service_mod.optimize_schedule
        captured_calls = []

        def optimize_with_capture(**kwargs):
            captured_calls.append(
                {
                    "algo_op_ids": [
                        int(getattr(op, "id", 0) or 0)
                        for op in list(kwargs.get("algo_ops_to_schedule") or [])
                    ],
                    "seed_op_ids": [
                        int(seed.get("op_id") or 0)
                        for seed in list(kwargs.get("seed_results") or [])
                        if isinstance(seed, dict)
                    ],
                }
            )
            return original_optimize(**kwargs)

        monkeypatch.setattr(schedule_service_mod, "optimize_schedule", optimize_with_capture)

        ScheduleService(conn).run_schedule(
            ["B1"],
            start_dt="2026-05-01 08:00:00",
            created_by="pytest",
        )

        assert captured_calls
        for call in captured_calls:
            assert 10 not in call["algo_op_ids"]
            assert 20 in call["algo_op_ids"]
            assert 10 in call["seed_op_ids"]
        assert _batch_operation_status(conn, 10) == "completed"
        assert _batch_operation_status(conn, 20) == "scheduled"
    finally:
        conn.close()


def test_all_processing_operations_show_execution_fact_message_without_writing(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        feedback = OperationExecutionFeedbackService(conn)
        feedback.start_operation(
            _context(),
            event_time="2026-05-01 08:20:00",
            operator_id="O1",
            machine_id="M1",
        )
        feedback.start_operation(
            _context(op_id=20, schedule_id=101, revision="20:0:0", key="start-key-op20"),
            event_time="2026-05-01 09:20:00",
            operator_id="O2",
            machine_id="M2",
        )
        before = _counts(conn)

        with pytest.raises(ValidationError) as exc_info:
            ScheduleService(conn).run_schedule(
                ["B1"],
                start_dt="2026-05-01 08:00:00",
                created_by="pytest",
            )

        assert exc_info.value.details["reason"] == "all_operations_fixed_by_execution_facts"
        assert "都已经开工或暂停" in exc_info.value.message
        assert _counts(conn) == before
    finally:
        conn.close()


def test_reschedule_snapshot_recheck_rejects_shop_floor_change_without_formal_writes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        before = _counts(conn)
        original_optimize = schedule_service_mod.optimize_schedule
        injected = {"done": False}

        def optimize_with_shop_floor_change(**kwargs):
            if not injected["done"]:
                injected["done"] = True
                OperationExecutionFeedbackService(conn).start_operation(
                    _context(),
                    event_time="2026-05-01 08:30:00",
                    operator_id="O1",
                    machine_id="M1",
                )
            return original_optimize(**kwargs)

        monkeypatch.setattr(schedule_service_mod, "optimize_schedule", optimize_with_shop_floor_change)

        with pytest.raises(AppError) as exc_info:
            ScheduleService(conn).run_schedule(
                ["B1"],
                start_dt="2026-05-01 08:00:00",
                created_by="pytest",
            )

        assert exc_info.value.code.value == "6003"
        assert exc_info.value.details["reason"] == "execution_state_changed"
        assert "现场状态刚刚变了" in exc_info.value.message
        assert _counts(conn) == before
    finally:
        conn.close()


def test_simulate_without_execution_facts_does_not_write_formal_version(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        before = _counts(conn)

        result = ScheduleService(conn).run_schedule(
            ["B1"],
            start_dt="2026-05-01 08:00:00",
            created_by="pytest",
            simulate=True,
        )

        assert result["result_persisted"] is False
        assert result["can_open_result_version"] is False
        assert result["version"] is None
        assert "没有生成新的排程版本" in result["user_message"]
        assert _counts(conn) == before
    finally:
        conn.close()


def test_simulate_with_execution_snapshot_does_not_write_formal_version(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        OperationExecutionFeedbackService(conn).start_operation(
            _context(),
            event_time="2026-05-01 08:30:00",
            operator_id="O1",
            machine_id="M1",
        )
        before = _counts(conn)

        result = ScheduleService(conn).run_schedule(
            ["B1"],
            start_dt="2026-05-01 08:00:00",
            created_by="pytest",
            simulate=True,
        )

        assert result["result_persisted"] is False
        assert result["version"] is None
        assert _counts(conn) == before
    finally:
        conn.close()
