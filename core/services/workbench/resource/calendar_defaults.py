"""Editable factory defaults with the same guarded command and receipt contract."""

from core.errors import ValidationError
from core.infrastructure.transaction import in_transaction_context
from core.models.calendar_periods import encode_periods, normalize_periods, period_hours
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
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

    def apply(self, payload, checked):
        if not self.conn.in_transaction or not in_transaction_context(self.conn):
            raise RuntimeError("Default calendar writes require a workbench command transaction.")
        current = self.snapshot()
        if current != checked:
            raise WorkbenchCommandRejected("stale_write", "默认工作时间已变化，请刷新后重新核对。")
        return self._apply_checked(payload, current)

    def _apply_checked(self, payload, current):
        if not self.conn.in_transaction or not in_transaction_context(self.conn):
            raise RuntimeError("Default calendar writes require a workbench command transaction.")
        periods = self.normalize(payload)["periods"]
        if periods == current["periods"]:
            return WorkbenchCommandOutcome("unchanged", {"subject": "calendar-defaults"})
        self.repo.set_periods(encode_periods(periods))
        return WorkbenchCommandOutcome("committed", {"subject": "calendar-defaults"})
