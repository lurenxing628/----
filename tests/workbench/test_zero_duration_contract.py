"""Explicit zero, not a falsey fallback, cancelled negatives or rounded positive work."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.algorithm_runtime.internal_slot import validate_internal_hours
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload
from core.services.workbench.zero_duration import PointEventError, internal_duration_hours, point_event_dto


@pytest.mark.parametrize("setup,unit,quantity,total", [(0, 0, 3, 0), (0, 7, 0, 0), (2, 7, 0, 2), (0, 0.5, 3, 1.5)])
def test_zero_quantity_does_not_erase_setup(setup, unit, quantity, total):
    assert internal_duration_hours(setup, unit, quantity) == total
    assert validate_internal_hours(SimpleNamespace(setup_hours=setup, unit_hours=unit),
                                   SimpleNamespace(quantity=quantity)) == total


@pytest.mark.parametrize("field", ["setup_hours", "unit_hours", "quantity"])
@pytest.mark.parametrize("value", [None, False, True, "0", "", -1, float("inf"), float("nan"), 10 ** 20])
def test_invalid_operand_is_not_legal_zero(field, value):
    values = {"setup_hours": 0, "unit_hours": 0, "quantity": 0}
    values[field] = value
    with pytest.raises(PointEventError) as error:
        internal_duration_hours(**values)
    assert error.value.code == ("quantity_unknown" if field == "quantity" else "hours_missing")


def test_cancelled_negatives_are_not_an_engine_zero_proof():
    op, batch = SimpleNamespace(setup_hours=-1, unit_hours=1), SimpleNamespace(quantity=1)
    assert validate_internal_hours(op, batch) == 0
    with pytest.raises(PointEventError, match="不能是负数"):
        internal_duration_hours(op.setup_hours, op.unit_hours, batch.quantity)


def test_tiny_positive_and_overflow_are_not_zero():
    assert internal_duration_hours(0, 5e-324, 1) > 0
    with pytest.raises(PointEventError) as error:
        internal_duration_hours(0, 9007199254740991, 9007199254740991)
    assert error.value.code == "invalid_duration"
    with pytest.raises(PointEventError):
        internal_duration_hours(0, 0, 0.5)


def test_point_dto_preserves_time_and_has_no_display_epsilon():
    moment = datetime(2026, 9, 9, 9, 17, 31)
    assert point_event_dto(moment, moment) == {"start": "2026-09-09T09:17:31", "end": "2026-09-09T09:17:31",
        "event_kind": "point", "duration_seconds": 0, "occupies_resources": False}


@pytest.mark.parametrize("kind", ["positive", "negative", "timezone", "microsecond", "string", "unknown"])
def test_point_dto_refuses_lossy_or_nonpoint_times(kind):
    start = end = datetime(2026, 9, 9, 9)
    if kind == "positive":
        end += timedelta(seconds=1)
    elif kind == "negative":
        end -= timedelta(seconds=1)
    elif kind == "timezone":
        start = end = start.replace(tzinfo=timezone.utc)
    elif kind == "microsecond":
        start = end = start.replace(microsecond=1)
    elif kind == "string":
        start = end = start.isoformat()
    else:
        start = end = None
    with pytest.raises(PointEventError):
        point_event_dto(start, end)


def test_original_payload_still_blocks_points_including_mixed_results():
    moment = datetime(2026, 9, 9, 9)
    point = SimpleNamespace(op_id=1, machine_id="M1", operator_id="O1", source="internal",
                            start_time=moment, end_time=moment)
    positive = SimpleNamespace(op_id=2, machine_id="M1", operator_id="O1", source="internal",
                               start_time=moment, end_time=moment + timedelta(hours=1))
    for rows in ([point], [point, positive]):
        with pytest.raises(ValidationError):
            build_validated_schedule_payload(rows, allowed_op_ids={1, 2})
