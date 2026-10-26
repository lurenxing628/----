"""历史事件按完整计划身份折叠为执行事实，并复用同次读取的校验结果。"""

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from core.infrastructure.database import get_connection
from core.models import operation_execution_event as event_model
from core.models.operation_execution_scope import OperationExecutionScope
from core.services.scheduler.execution import execution_fact_provider as fact_module
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from data.repositories import operation_execution_event_repo as event_repo
from tests.workbench.plan_identity_support import load_v24_schema


def _connect(tmp_path: Path) -> sqlite3.Connection:
    conn = get_connection(str(tmp_path / "aps.db"))
    load_v24_schema(conn)
    return conn


def _seed_plan(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO Machines(machine_id, name, status)
        VALUES ('M1', '一号设备', 'active'), ('M2', '二号设备', 'active');

        INSERT INTO Operators(operator_id, name, status)
        VALUES ('O1', '张三', 'active'), ('O2', '李四', 'active');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES ('B1', 'P001', '零件一', 10, '2026-05-10', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'scheduled');

        INSERT INTO ScheduleVersionSeq(version) VALUES (1);

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES (100, 10, 'M1', 'O1', '2026-05-01 08:00:00', '2026-05-01 09:00:00', 'unlocked', 1);

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (1, 'priority_first', 1, 1, 'success', '{}', 'pytest');
        """
    )
    conn.commit()


@pytest.mark.parametrize("captured", [False, True])
def test_historical_event_flow_is_folded_once_without_resource_queries(tmp_path, monkeypatch, captured):
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        scope = OperationExecutionScope.from_values(
            schedule_version=1, schedule_id=100, op_id=10, batch_id="B1",
            source_table="schedule", effective_plan_role="adopted", scenario_id=None,
        )

        def check_fact(*, count, event_id, status, start=None, end=None, exception=False):
            capture = ProductionFactsCapture(conn) if captured else None
            provider = fact_module.ExecutionFactProvider(conn, capture=capture)
            normalized, checked, sql = [], [], []
            normalize = event_model.normalize_operation_execution_event_values
            validation_module = fact_module if captured else event_repo
            validate = validation_module.validate_operation_execution_event_sequence

            def normalize_event(**values):
                normalized.append(values)
                return normalize(**values)

            def validate_scope(events):
                checked.append(events)
                return validate(events)

            with monkeypatch.context() as patch:
                patch.setattr(event_model, "normalize_operation_execution_event_values", normalize_event)
                patch.setattr(validation_module, "validate_operation_execution_event_sequence", validate_scope)
                conn.set_trace_callback(sql.append)
                try:
                    fact = provider.facts_by_scope([scope], execution_projections=[])[scope]
                    if captured:
                        assert provider.facts_by_scope([scope], execution_projections=[])[scope] is fact
                finally:
                    conn.set_trace_callback(None)
            assert len(normalized) == count
            assert len(checked) == int(bool(count) or captured)
            assert not any(" FROM MACHINES" in statement.upper() or " FROM OPERATORS" in statement.upper() for statement in sql)
            assert (
                fact.op_id, fact.batch_id, fact.actual_status, fact.actual_start_time, fact.actual_end_time,
                fact.actual_machine_id, fact.actual_operator_id, fact.state_revision,
                fact.latest_exception_impact_minutes, fact.latest_exception_handling_status,
                fact.latest_exception_suggest_reschedule,
            ) == (
                10, "B1", status, start, end,
                "M1" if count else None, "O1" if count else None, f"10:{count}:{event_id}",
                30 if exception else None, "new" if exception else None, exception,
            )
            assert (fact.schedule_version, fact.schedule_id, fact.source_table, fact.effective_plan_role, fact.scenario_id) == (
                1, 100, "schedule", "adopted", None,
            )

        check_fact(count=0, event_id=0, status="not_started")
        previous_id = 0
        events = (
            ("start", "processing", "08:00:00"),
            ("pause", "paused", "08:20:00"),
            ("resume", "processing", "08:35:00"),
            ("exception", "exception", "08:45:00"),
            ("resume", "processing", "09:00:00"),
            ("finish", "completed", "09:30:00"),
        )
        for count, (event_type, status, time) in enumerate(events, start=1):
            is_exception = event_type == "exception"
            cursor = conn.execute(
                """
                INSERT INTO OperationExecutionEvents (
                    schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                    event_type, reported_status, event_time, actual_machine_id, actual_operator_id,
                    reason_code, severity, impact_minutes, handling_status, suggest_reschedule, created_by, idempotency_key,
                    request_fingerprint, previous_state_revision
                ) VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pytest', ?, ?, ?)
                """,
                (event_type, status, "2026-05-01 " + time,
                 "M1" if count == 1 else None, "O1" if count == 1 else None,
                 "equipment" if event_type in ("pause", "exception") else None, "high" if is_exception else None,
                 30 if is_exception else None, "new" if is_exception else None, int(is_exception),
                 f"legacy-event-{count}", f"legacy-fp-{count}", f"10:{count - 1}:{previous_id}"),
            )
            previous_id = cursor.lastrowid
            conn.commit()
            check_fact(
                count=count, event_id=previous_id, status=status, start=datetime(2026, 5, 1, 8),
                end=datetime(2026, 5, 1, 9, 30) if event_type == "finish" else None, exception=count >= 4,
            )
    finally:
        conn.close()


def _event_row(**values):
    row = {"id": 5, "schedule_version": 1, "schedule_id": 100, "op_id": 10, "batch_id": "B1",
           "source_table": "schedule", "effective_plan_role": "adopted", "scenario_id": None,
           "event_type": "start", "reported_status": "processing", "event_time": "2026-05-01 08:00:00",
           "previous_state_revision": "10:0:0"}
    row.update({column: None for column in event_model.OPERATION_EXECUTION_EVENT_COLUMNS if column not in row})
    row.update(created_by="pytest", idempotency_key="k", suggest_reschedule=0)
    row.update(values)
    return row


@pytest.mark.parametrize(("field", "value", "message"), [
    # 身份字段只归一一次（from_values），当前正式计划的三条不变量照样拦住。
    ("source_table", "schedule_candidate", "current official schedule rows"),
    ("effective_plan_role", " baseline_best ", "adopted plan"),
    ("scenario_id", "s1", "scenario preview plans"),
    # 前一状态版本在读取边界校验一次。
    ("previous_state_revision", "  ", "previous_state_revision is required"),
    # 计划身份是 SQLite INTEGER：文本、REAL 一律当损坏，不再按数字文本读通。
    ("schedule_version", "1", "schedule_version must be a positive integer"),
    ("op_id", 10.0, "op_id must be a positive integer"),
    # 可空整数列坏值报本字段文案，不被笼统的整数解析错误抢先。
    ("quantity_done", "abc", "quantity_done must be an integer"),
    ("suggest_reschedule", "2", "suggest_reschedule must be 0 or 1"),
])
def test_event_row_boundary_rejects_values_outside_the_stored_contract(field, value, message):
    with pytest.raises(ValueError, match=message):
        event_model.OperationExecutionEvent.from_row(_event_row(**{field: value}))


def test_event_row_normalizes_once_and_sequence_compares_the_normalized_values():
    event = event_model.OperationExecutionEvent.from_row(
        _event_row(source_table=" schedule ", previous_state_revision=" 10:0:0 ", quantity_done=" 3 "))
    assert (event.source_table, event.previous_state_revision, event.quantity_done) == ("schedule", "10:0:0", 3)
    event_model.validate_operation_execution_event_sequence([event])
    broken = event_model.OperationExecutionEvent.from_row(_event_row(id="x"))
    assert broken.id is None
    with pytest.raises(ValueError, match="id must be a positive integer at type='start'"):
        event_model.validate_operation_execution_event_sequence([broken])
