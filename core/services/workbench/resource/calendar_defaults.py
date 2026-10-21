"""Editable factory defaults with the same guarded command and receipt contract."""

import json

from core.errors import ValidationError
from core.infrastructure.transaction import in_transaction_context
from core.models.calendar_periods import normalize_periods, period_hours
from core.models.workbench_command import WorkbenchCommandOutcome
from core.services.scheduler.calendar.defaults import default_periods_from_row
from data.repositories.calendar_defaults_repo import CalendarDefaultsRepository


class WorkbenchCalendarDefaultsService:
    def __init__(self, conn):
        self.conn, self.repo = conn, CalendarDefaultsRepository(conn)

    @staticmethod
    def normalize(payload):
        if type(payload) is not dict or set(payload) != {"periods"}:
            raise ValidationError("请逐段填写默认工作时间。", field="periods")
        periods = normalize_periods(payload["periods"])
        if not periods:
            raise ValidationError("默认工作时间至少需要一个工作时段。", field="periods")
        return {"periods": periods}

    def snapshot(self):
        row = self.repo.get()
        periods = default_periods_from_row(row)
        return {"row": row, "periods": periods, "hours": period_hours(periods)}

    def _apply_checked(self, payload, current):
        if not self.conn.in_transaction or not in_transaction_context(self.conn):
            raise RuntimeError("Default calendar writes require a workbench command transaction.")
        periods = payload["periods"]
        if periods == current["periods"]:
            return WorkbenchCommandOutcome("unchanged", {"subject": "calendar-defaults"})
        self.repo.set_periods(json.dumps(periods, ensure_ascii=False, separators=(",", ":")))
        return WorkbenchCommandOutcome("committed", {"subject": "calendar-defaults"})
