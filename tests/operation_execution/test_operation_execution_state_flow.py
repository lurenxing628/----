"""旧现场执行事件的行边界：身份与可空整数列只按存储契约归一一次。"""

import pytest

from core.models import operation_execution_event as event_model


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
    # scenario_id 只许 NULL：空串也是“有值”，与 schema CHECK(scenario_id IS NULL) 同一口径。
    ("scenario_id", "", "scenario preview plans"),
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
