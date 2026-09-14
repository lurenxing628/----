"""Private global calendar adapter. No HTTP routes, personal calendars or shift profiles."""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager, in_transaction_context
from core.models.calendar import WorkCalendar
from core.models.workbench_calendar import (
    CALENDAR_PREVIEW_TTL_SECONDS,
    CalendarRangePreview,
    calendar_date,
    calendar_domain_fields,
    calendar_range_dates,
    normalize_calendar_input,
)
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected, input_fingerprint
from core.services.scheduler.calendar_engine import CalendarEngine
from core.services.scheduler.calendar_service import CalendarService
from data.repositories.workbench_calendar_query_repo import WorkbenchCalendarQueryRepository


class _CalendarProjection(CalendarEngine):
    """Overlay one raw/proposed global row on the existing engine, without SQL writes."""

    def __init__(self, row: Optional[Dict[str, Any]]):
        super().__init__(None)
        self._row = WorkCalendar.from_row(row) if row is not None else None

    def _resolve_calendar_row(self, date_str: str, op_id: Optional[str]) -> WorkCalendar:
        return self._row if self._row is not None else self._default_for_date(date_str)


def _effective(day: str, row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    # Date-key policy is deliberate: midnight may still belong to yesterday's shift.
    policy = _CalendarProjection(row)._policy_for_date(day)
    normal, urgent = policy.is_priority_allowed("normal"), policy.is_priority_allowed("urgent")
    working = policy.shift_hours > 0 and (normal or urgent)
    start, end = policy.work_window()
    return {"type": "work" if working else "rest", "day_type": policy.day_type,
            "is_working": working, "is_rest": not working, "hours": policy.shift_hours,
            "effective_hours": policy.shift_hours * policy.efficiency if working else 0.0,
            "efficiency": policy.efficiency, "eff": policy.efficiency * 100,
            "allowNormal": "yes" if normal else "no", "allowUrgent": "yes" if urgent else "no",
            "window_start": start.isoformat(timespec="seconds"), "window_end": end.isoformat(timespec="seconds")}


def _month_stats(days: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Count explicit rows separately from configured capacity and default overrides."""
    return {"work_days": sum(day["effective"]["is_working"] for day in days),
            "configured": sum(day["explicit"] for day in days),
            "configured_work_days": sum(day["explicit"] and day["effective"]["is_working"] for day in days),
            "rest_days": sum(day["effective"]["is_rest"] for day in days),
            "overrides": sum(day["explicit"] and day["is_weekend"] == day["effective"]["is_working"] for day in days),
            "weekend_rest": sum(day["is_weekend"] and day["effective"]["is_rest"] for day in days),
            "effective_hours": sum(day["effective"]["effective_hours"] for day in days)}


class WorkbenchCalendarService:
    def __init__(self, conn, logger=None, *, clock: Callable[[], datetime] = datetime.now):
        self.conn = conn
        self._clock = clock
        self._calendar = CalendarService(conn, logger=logger)
        self._query = WorkbenchCalendarQueryRepository(conn, logger=logger)
        self._tx = TransactionManager(conn)

    @staticmethod
    def normalize(action: str, payload: Any) -> Dict[str, Any]:
        """Private pure input API; see normalize_calendar_input for the complete shapes."""
        return normalize_calendar_input(action, payload)

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is not None:
            raise ValueError("日历时钟必须使用无时区的工厂本地时间。")
        return now.replace(microsecond=0)

    @staticmethod
    def _snapshot(day: str, states: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        state = states.get(day, {"row": None, "identity": None, "history": []})
        identity = state["identity"]
        return {"date": day, "explicit": state["row"] is not None,
                "calendar_ref": identity["ref"] if identity else None,
                "revision": identity["revision"] if identity else None,
                **state, "effective": _effective(day, state["row"])}

    def snapshot(self, date_value: str) -> Dict[str, Any]:
        """Private full guard state, not public DTO: raw row, ref/revision and tombstones.

        No record differs from a stored row, even when both compute the same policy.
        Absent rows have no current ref/revision; historical refs remain in history.
        The HTTP owner must bind this full snapshot to its short-lived write context.
        """
        day = calendar_date(date_value)
        with self._tx.transaction():
            return self._snapshot(day, self._query.range_states(day, day))

    def month(self, year: int, month: int) -> Dict[str, Any]:
        """Private monthly read: one-based month, real date cells, Monday-first padding.

        Counts/policies use actual domain results, not weekday guesses. No statutory
        holiday feed exists: unconfigured weekdays remain normal domain defaults.
        Rows carry internal revisions for HTTP context assembly, never for public URLs.
        """
        if type(year) is not int or type(month) is not int or not 1 <= year <= 9999 or not 1 <= month <= 12:
            raise ValidationError("年月不合法，月份应为 1 至 12。", field="month")
        first = date(year, month, 1)
        count = calendar.monthrange(year, month)[1]
        last, now = first.replace(day=count), self._now()
        with self._tx.transaction():
            states = self._query.range_states(first.isoformat(), last.isoformat())
            days = []
            for offset in range(count):
                day = first + timedelta(days=offset)
                snapshot = self._snapshot(day.isoformat(), states)
                days.append({**snapshot, "day": day.day, "weekday": day.weekday(),
                             "is_weekend": day.weekday() >= 5, "is_today": day == now.date()})
        cells = [None] * first.weekday() + days
        cells += [None] * (-len(cells) % 7)
        return {"year": year, "month": month, "as_of": now.isoformat(timespec="seconds"),
                "time_basis": "factory_local", "days": days, "cells": cells,
                "previous_month": self._adjacent(year, month, -1), "next_month": self._adjacent(year, month, 1),
                "stats": _month_stats(days)}

    @staticmethod
    def _adjacent(year: int, month: int, delta: int) -> Optional[Dict[str, int]]:
        shifted_year, shifted_month = divmod(year * 12 + month - 1 + delta, 12)
        return {"year": shifted_year, "month": shifted_month + 1} if 1 <= shifted_year <= 9999 else None

    def _proposed(self, fields: Dict[str, Any], before: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        row = before["row"]
        if not fields:
            return row
        payload = dict(row) if row is not None else {"date": before["date"]}
        if row is None and "type" not in fields:
            default = _CalendarProjection(None)._default_for_date(before["date"])
            payload.update(default.to_dict())
            payload["remark"] = None
        patch = calendar_domain_fields(fields)
        payload.update(patch)
        proposed = self._calendar._admin._build_work_calendar_from_payload(payload).to_dict()
        self._check_proposed(before, patch, proposed)
        return proposed

    def _check_proposed(self, before: Dict[str, Any], patch: Dict[str, Any], proposed: Dict[str, Any]) -> None:
        if self._calendar._admin._build_work_calendar_from_payload(proposed).to_dict() != proposed:
            raise WorkbenchCommandRejected("constraint_conflict", "填的工时换成班次的分钟数后存不稳，请核对工时。")
        if "shift_hours" in patch and abs(proposed["shift_hours"] - patch["shift_hours"]) > 1e-9:
            raise WorkbenchCommandRejected(
                "constraint_conflict", f"{before['date']} 按原班次起止算出 {proposed['shift_hours']:g} 小时，"
                f"和你填的 {patch['shift_hours']:g} 小时对不上，所以没有保存；请先核对原班次。")
        row = before["row"]
        if row is not None:
            if any(proposed.get(name) != value for name, value in row.items() if name not in patch):
                raise WorkbenchCommandRejected("constraint_conflict", "这一天没改的项会被规则改写，所以没有保存；请先核对原来的配置。")

    def _require_write_transaction(self) -> None:
        if not self.conn.in_transaction or not in_transaction_context(self.conn):
            raise RuntimeError("日历写入必须由外层 WorkbenchCommandService 持有写事务。")

    def apply(self, action: str, normalized_input: Dict[str, Any], checked: Any) -> WorkbenchCommandOutcome:
        """Private command mutate callback; never owns/commits the outer write transaction.

        For upsert/delete, checked is the server-held snapshot(date) bound to the
        write context. For confirm it is the original server-held CalendarRangePreview.
        The caller validates write_token in its guard under BEGIN IMMEDIATE, using
        this same connection. Returned outcomes are provisional until the receipt
        and domain writes commit together. Receipts contain only stable dates/refs.
        """
        self._require_write_transaction()
        payload = self.normalize(action, normalized_input)
        if action == "confirm":
            return self.confirm(payload, checked)
        if action not in ("upsert", "delete"):
            raise ValidationError("「预览变更」不能当成保存操作。", field="action")
        before = self.snapshot(payload["date"])
        if checked != before:
            raise WorkbenchCommandRejected("stale_write", "日历已变化，请刷新后重新核对。")
        after = self._proposed(payload["fields"], before) if action == "upsert" else None
        return self._write(before, after)

    def _write(self, before: Dict[str, Any], after: Optional[Dict[str, Any]]) -> WorkbenchCommandOutcome:
        ref, day = before["calendar_ref"], before["date"]
        if after == before["row"]:
            return WorkbenchCommandOutcome("unchanged", {"date": day, "calendar_ref": ref})
        if after is None:
            self._calendar.delete(day)
        else:
            self._calendar.upsert_no_tx(after)
        saved = self.snapshot(day)
        if saved["row"] != after:
            raise RuntimeError("日历保存结果与领域预览不一致，不能确认保存。")
        if after is not None and before["row"] is not None and (
                saved["calendar_ref"] != ref or saved["revision"] != before["revision"] + 1):
            raise RuntimeError("日历更新未保持永久引用及修订号，不能确认保存。")
        return WorkbenchCommandOutcome("committed", {"date": day, "calendar_ref": saved["calendar_ref"] or ref})

    def _preview_days(self, request: Dict[str, Any], expected: Optional[CalendarRangePreview] = None) -> Dict[str, Any]:
        dates = calendar_range_dates(request)
        if expected is not None and dates != expected.dates:
            raise WorkbenchCommandRejected("snapshot_stale", "命中的日期已经变了，请重新点「预览变更」。")
        states = self._query.range_states(request["start_date"], request["end_date"])
        days = []
        for index, day in enumerate(dates):
            before = self._snapshot(day, states)
            if expected is not None and before != expected.days[index]["before"]:
                raise WorkbenchCommandRejected("snapshot_stale", "范围里的日历已经变了，请重新点「预览变更」。")
            row = self._proposed(request["fields"], before) if request["operation"] == "upsert" else None
            days.append({"date": day, "before": before,
                         "after": {"explicit": row is not None, "row": row, "effective": _effective(day, row)}})
        return {"request": request, "dates": dates, "days": days}

    def preview(self, payload: Dict[str, Any]) -> CalendarRangePreview:
        """Read-only bounded preview. No placeholder rows, business writes or long lock.

        Weekday/weekend means Gregorian Mon-Fri/Sat-Sun, including configured holidays
        and overtime, exactly as the prototype. Conflicting hidden shift windows reject
        the preview instead of advertising hours that the domain would not save.
        """
        request, now = self.normalize("preview", payload), self._now()
        with self._tx.transaction():
            facts = self._preview_days(request)
        facts.update(preview_ref=uuid.uuid4().hex, created_at=now.isoformat(timespec="seconds"),
                     expires_at=(now + timedelta(seconds=CALENDAR_PREVIEW_TTL_SECONDS)).isoformat(timespec="seconds"))
        return CalendarRangePreview(**facts, fingerprint=input_fingerprint(facts))

    def confirm(self, normalized_input: Dict[str, Any], preview: CalendarRangePreview) -> WorkbenchCommandOutcome:
        """Private confirm callback, inside the same outer write transaction and receipt.

        Revalidate TTL, exact date set and every complete before/after snapshot before
        any writes. Any later failure propagates to the owner for whole-batch rollback.
        A stale preview never silently selects fresh dates or substitutes another ref.
        """
        self._require_write_transaction()
        payload = self.normalize("confirm", normalized_input)
        if not isinstance(preview, CalendarRangePreview) or preview.preview_ref != payload["preview_ref"]:
            raise WorkbenchCommandRejected("snapshot_stale", "这份变更清单已失效，请重新点「预览变更」。")
        now = self._now().isoformat(timespec="seconds")
        if not preview.created_at <= now < preview.expires_at or input_fingerprint(preview.facts()) != preview.fingerprint:
            raise WorkbenchCommandRejected("snapshot_stale", "这份变更清单已过期或内容有变化，请重新点「预览变更」。")
        current = self._preview_days(self.normalize("preview", preview.request), expected=preview)
        if current != {"request": preview.request, "dates": preview.dates, "days": preview.days}:
            raise WorkbenchCommandRejected("snapshot_stale", "范围里的日历或命中的日期已经变了，请重新点「预览变更」。")
        results = [self._write(item["before"], item["after"]["row"]) for item in current["days"]]
        return WorkbenchCommandOutcome("committed" if any(item.result == "committed" for item in results) else "unchanged",
                                       {"dates": [{**item.data, "result": item.result} for item in results]})
