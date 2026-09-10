"""DL-owned point-event inputs; no edits to existing fixtures or live databases."""

from core.services.workbench.trial_calendar import calendar_engine


def original_work(*, setup=0, unit=0, quantity=3, priority="normal"):
    return {"operation": {"source": "internal", "setup_hours": setup, "unit_hours": unit, "piece_id": None},
            "batch": {"quantity": quantity, "priority": priority},
            "execution": {"target_quantity": quantity, "target_basis": "batch"}}


def arrangement(start="2026-09-09T09:00:00"):
    return {"start": start, "machine_id": "M1", "operator_id": "O1",
            "machine_ref": "1" * 48, "operator_ref": "2" * 48}


def workday(day="2026-09-09", **changes):
    return dict({"date": day, "day_type": "workday", "shift_start": "08:00", "shift_hours": 8,
                 "efficiency": 1, "allow_normal": "yes", "allow_urgent": "yes"}, **changes)


def engine(*, global_rows=(), personal_rows=()):
    return calendar_engine({"WorkCalendar": list(global_rows), "OperatorCalendar": list(personal_rows),
        "WorkbenchShiftProfiles": [], "WorkbenchOperatorProfiles": [], "WorkbenchShiftPatternDays": []})
