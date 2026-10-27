"""现场执行作用域与时间解析边界：身份与时间按存储契约严格校验。"""

from datetime import datetime

import pytest

from core.models.operation_execution_scope import (
    OperationExecutionScope,
    parse_operation_event_time,
)


def _scope_values(**overrides):
    values = {
        "schedule_version": 1,
        "schedule_id": 100,
        "op_id": 10,
        "batch_id": "B1",
        "source_table": "schedule",
        "effective_plan_role": "adopted",
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schedule_version", "1", "schedule_version must be a positive integer"),
        ("schedule_version", 0, "schedule_version must be a positive integer"),
        ("schedule_id", True, "schedule_id must be a positive integer"),
        ("op_id", 10.0, "op_id must be a positive integer"),
        ("batch_id", "  ", "batch_id is required"),
        ("source_table", "", "source_table is required"),
        ("effective_plan_role", None, "effective_plan_role is required"),
    ],
)
def test_scope_boundary_rejects_values_outside_stored_contract(field, value, message):
    with pytest.raises(ValueError, match=message):
        OperationExecutionScope.from_values(**_scope_values(**{field: value}))


def test_scope_and_event_time_parsing_preserve_stored_contract():
    scope = OperationExecutionScope.from_values(
        **_scope_values(source_table=" schedule ", effective_plan_role=" adopted ")
    )
    assert (scope.source_table, scope.effective_plan_role) == ("schedule", "adopted")
    assert parse_operation_event_time("2026/05/01T08:00:00") == datetime(2026, 5, 1, 8, 0, 0)
    assert parse_operation_event_time("2026-05-01 08:30") == datetime(2026, 5, 1, 8, 30, 0)
    with pytest.raises(ValueError, match="event_time is required"):
        parse_operation_event_time("   ")
