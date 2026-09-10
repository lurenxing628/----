"""Real CalendarEngine math for internal points; production trial remains disabled."""

from datetime import datetime

import pytest

from core.errors import AppError
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.trial_calendar import estimate, original_duration
from tests.workbench.zero_duration_support import arrangement, engine, original_work, workday


@pytest.mark.parametrize("start,expected", [
    ("2026-09-09T07:59:00", "2026-09-09T08:00:00"),
    ("2026-09-09T08:00:00", "2026-09-09T08:00:00"),
    ("2026-09-09T09:17:31", "2026-09-09T09:17:31"),
    ("2026-09-09T16:00:00", "2026-09-10T08:00:00"),
    ("2026-09-12T09:00:00", "2026-09-14T08:00:00"),
])
def test_point_uses_actual_shift_boundaries(start, expected):
    first, last = estimate(engine(), original_work(), arrangement(start), allow_point=True)
    assert first == last == datetime.fromisoformat(expected)
    assert (last - first).total_seconds() == 0


def test_original_duration_retains_zero_but_does_not_enable_trial_by_default():
    original = original_work()
    hours = original_duration(original, allow_point=True)
    assert hours == {"basis": "effective_processing_hours", "setup_hours": 0, "unit_hours": 0,
                     "quantity": 3, "total_hours": 0}
    with pytest.raises(WorkbenchCommandRejected) as error:
        estimate(engine(), original, arrangement())
    assert error.value.code == "zero_or_invalid_duration"


def test_personal_calendar_and_priority_apply_to_points():
    row = dict(workday(), operator_id="O1", shift_start="13:00", shift_hours=4, efficiency=0.5)
    personal = engine(personal_rows=[row])
    assert estimate(personal, original_work(), arrangement(), allow_point=True) == (
        datetime(2026, 9, 9, 13), datetime(2026, 9, 9, 13))
    row["allow_normal"] = "no"
    denied = engine(personal_rows=[row])
    assert estimate(denied, original_work(), arrangement(), allow_point=True)[0] == datetime(2026, 9, 10, 8)
    assert estimate(denied, original_work(priority="urgent"), arrangement(), allow_point=True)[0] == datetime(2026, 9, 9, 13)


def test_previous_night_shift_still_contains_the_point():
    row = dict(workday("2026-09-08"), operator_id="O1", shift_start="22:00", shift_hours=8)
    moment = datetime(2026, 9, 9, 1)
    assert estimate(engine(personal_rows=[row]), original_work(), arrangement(moment.isoformat()), allow_point=True) == (moment, moment)


@pytest.mark.parametrize("efficiency", [None, "", 0, -1, float("inf")])
def test_unknown_or_invalid_calendar_efficiency_still_fails(efficiency):
    row = dict(workday(), operator_id="O1", efficiency=efficiency)
    with pytest.raises((AppError, ValueError)):
        estimate(engine(personal_rows=[row]), original_work(), arrangement(), allow_point=True)


@pytest.mark.parametrize("field", ["machine_ref", "operator_ref", "machine_id", "operator_id"])
def test_points_do_not_waive_resource_identity(field):
    value = arrangement()
    value[field] = None
    with pytest.raises(WorkbenchCommandRejected) as error:
        estimate(engine(), original_work(), value, allow_point=True)
    assert error.value.code == "resource_required"


@pytest.mark.parametrize("field", ["setup_hours", "unit_hours"])
@pytest.mark.parametrize("value", [None, -1, False, float("nan")])
def test_opt_in_is_not_permission_for_unknown_or_negative_work(field, value):
    original = original_work()
    original["operation"][field] = value
    with pytest.raises(WorkbenchCommandRejected) as error:
        original_duration(original, allow_point=True)
    assert error.value.code == "hours_missing"


def test_zero_quantity_preserves_positive_setup_and_target_evidence():
    original = original_work(setup=2, unit=7, quantity=0)
    assert original_duration(original, allow_point=True)["total_hours"] == 2
    assert estimate(engine(), original, arrangement(), allow_point=True) == (datetime(2026, 9, 9, 9), datetime(2026, 9, 9, 11))
    original["execution"]["target_quantity"] = None
    with pytest.raises(WorkbenchCommandRejected) as error:
        original_duration(original, allow_point=True)
    assert error.value.code == "quantity_unknown"


def test_zero_quantity_zero_setup_is_an_exact_point():
    moment = datetime(2026, 9, 9, 9)
    assert estimate(engine(), original_work(unit=7, quantity=0), arrangement(), allow_point=True) == (moment, moment)
