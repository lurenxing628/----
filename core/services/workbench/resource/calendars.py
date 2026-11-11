"""Private global calendar adapter. No HTTP routes, personal calendars or shift profiles."""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager, in_transaction_context
from core.models.workbench_calendar import (
    CALENDAR_PREVIEW_TTL_SECONDS,
    CalendarRangePreview,
    calendar_date,
    calendar_domain_fields,
    calendar_range_dates,
    form_field_error,
    normalize_calendar_input,
    require_periods_when_rest_turns_work,
)
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.scheduler.calendar.admin import CalendarAdmin, CalendarNormalizationContext
from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.workbench.facts.calendar_inputs import calendar_inputs_from_connection
from data.repositories.workbench_calendar_query_repo import WorkbenchCalendarQueryRepository

from .calendar_reading import (
    CalendarProjection,
    CalendarRow,
    effective_calendar_day,
    month_stats,
)


def _date_key(value: Any) -> str:
    # get_connection enables SQLite DATE conversion. datetime is deliberately not a date key.
    if type(value) is date:
        return value.isoformat()
    try:
        return calendar_date(value)
    except ValidationError as exc:
        raise WorkbenchCommandRejected("constraint_conflict", "存储日历的日期无效，不能当作本地日期读取。") from exc


class WorkbenchCalendarService:
    def __init__(self, conn, logger=None, *, clock: Callable[[], datetime] = datetime.now):
        self.conn = conn
        self.logger = logger
        self._clock = clock
        self._admin = CalendarAdmin(conn, logger=logger)
        self._engine: Optional[CalendarEngine] = None
        self._query = WorkbenchCalendarQueryRepository(conn, logger=logger)
        self._tx = TransactionManager(conn)

    def _base_engine(self) -> CalendarEngine:
        if self._engine is None:
            self._engine = CalendarEngine(calendar_inputs_from_connection(self.conn, public_days=()))
        return self._engine

    def _normalization_context(self) -> CalendarNormalizationContext:
        return CalendarNormalizationContext(
            self.conn,
            logger=self.logger,
            period_reader=lambda: self._base_engine().default_periods(),
        )

    def decoded_periods_for_json(self, periods_json: str) -> List[Dict[str, Any]]:
        return self._base_engine().decoded_periods_for_json(periods_json)

    @staticmethod
    def normalize(action: str, payload: Any) -> Dict[str, Any]:
        """Private pure input API; see normalize_calendar_input for the complete shapes."""
        return normalize_calendar_input(action, payload)

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is not None:
            raise ValueError("日历时钟必须使用无时区的工厂本地时间。")
        return now.replace(microsecond=0)

    def range_states(self, start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
        """Merge raw rows with lifetime refs per date; caller owns one transaction for both reads.

        Tombstones detect absent -> created -> deleted ABA. An absent date has row=None
        and identity=None; a GET never invents a ref. A stored date that is not a real
        local date, or a row whose active refs are not exactly one, is a data conflict.
        """
        self._engine = None
        rows: Dict[str, Dict[str, Any]] = {}
        for row in self._query.calendar_rows(start_date, end_date):
            row["date"] = _date_key(row["date"])
            rows[row["date"]] = row
        histories: Dict[str, List[Dict[str, Any]]] = {}
        for identity in self._query.identity_rows(start_date, end_date):
            identity["entity_key"] = _date_key(identity["entity_key"])
            histories.setdefault(identity["entity_key"], []).append(identity)
        result = {}
        for day in sorted(rows.keys() | histories.keys()):
            row, history = rows.get(day), histories.get(day, [])
            active = [item for item in history if item["active"] == 1]
            if len(active) != (1 if row is not None else 0):
                raise WorkbenchCommandRejected("constraint_conflict", "工作日历记录与编号不一致，请联系维护人员核对。")
            result[day] = {"row": row, "identity": active[0] if active else None, "history": history}
        return result

    @staticmethod
    def _snapshot(day: str, states: Dict[str, Dict[str, Any]], *, projection: CalendarProjection) -> Dict[str, Any]:
        state = states.get(day, {"row": None, "identity": None, "history": []})
        identity = state["identity"]
        return {"date": day, "explicit": state["row"] is not None,
                "calendar_ref": identity["ref"] if identity else None,
                "revision": identity["revision"] if identity else None,
                **state, "default_periods": projection.default_periods(),
                "effective": effective_calendar_day(day, state["row"], projection=projection)}

    def snapshot(self, date_value: str) -> Dict[str, Any]:
        """Private full guard state, not public DTO: raw row, ref/revision and tombstones.

        No record differs from a stored row, even when both compute the same policy.
        Absent rows have no current ref/revision; historical refs remain in history.
        The HTTP owner must bind this full snapshot to its short-lived write context.
        """
        day = calendar_date(date_value)
        if not self.conn.in_transaction:
            raise RuntimeError("日历读取必须在快照事务中执行。")
        states = self.range_states(day, day)
        return self._snapshot(day, states, projection=self.projection(states))

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
        if not self.conn.in_transaction:
            raise RuntimeError("日历读取必须在快照事务中执行。")
        states = self.range_states(first.isoformat(), last.isoformat())
        rows = {day: state["row"] for day, state in states.items() if state["row"] is not None}
        projection = CalendarProjection(rows, engine=self._base_engine())
        periods = projection.default_periods()
        days = []
        for offset in range(count):
            day = first + timedelta(days=offset)
            snapshot = self._snapshot(day.isoformat(), states, projection=projection)
            days.append({**snapshot, "day": day.day, "weekday": day.weekday(),
                         "is_weekend": day.weekday() >= 5, "is_today": day == now.date()})
        following = self._following_row(last, days[-1])
        if following:
            projection = projection.with_rows({**rows, **following})
        cells = [None] * first.weekday() + days
        cells += [None] * (-len(cells) % 7)
        return {"year": year, "month": month, "as_of": now.isoformat(timespec="seconds"),
                "time_basis": "factory_local", "days": days, "cells": cells,
                "previous_month": self._adjacent(year, month, -1), "next_month": self._adjacent(year, month, 1),
                "default_periods": periods, "stats": month_stats(days, projection)}

    def _following_row(self, last: date, tail: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """月末班次跨过零点时，才补读次月 1 日那一行：重叠段归它，月合计要扣掉。

        这一行只用于月合计，不进本月的日期状态，也不核对永久引用；读坏了只让合计未知，不牵连本月。
        """
        if last == date.max:
            return {}
        following = (last + timedelta(days=1)).isoformat()
        if tail["effective"]["window_end"] <= following + "T00:00:00":
            return {}
        # 日期是主键，按这一天查最多一行。
        rows = self._query.calendar_rows(following, following)
        return {following: {**rows[0], "date": following}} if rows else {}

    @staticmethod
    def _adjacent(year: int, month: int, delta: int) -> Optional[Dict[str, int]]:
        shifted_year, shifted_month = divmod(year * 12 + month - 1 + delta, 12)
        return {"year": shifted_year, "month": shifted_month + 1} if 1 <= shifted_year <= 9999 else None

    # ---------- 供日历文件家族使用的公开入口 ----------
    # 文件导入要一次处理上千天，逐日调 snapshot() 会开上千次事务、查上万次库（见 roadmap 4.7），
    # 所以这几个入口把"一次读回整段 / 算一天 / 写一天"拆开，由调用方持有一个事务。

    def projection(self, states: Dict[str, Dict[str, Any]]) -> CalendarProjection:
        rows = {day: state["row"] for day, state in states.items() if state["row"] is not None}
        return CalendarProjection(rows, engine=self._base_engine())

    def day_state(self, day: str, states: Dict[str, Dict[str, Any]],
                  *, projection: CalendarProjection) -> Dict[str, Any]:
        """某一天的完整状态。states 必须来自同一次 range_states。"""
        return self._snapshot(day, states, projection=projection)

    def proposed_state(
        self,
        fields: Dict[str, Any],
        before: Dict[str, Any],
        *,
        context: CalendarNormalizationContext,
        projection: CalendarProjection,
    ) -> Tuple[Optional[CalendarRow], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """按领域规则算出这一天保存后的行与生效时间窗；与界面走同一条一致性校验，不合规直接抛拒绝。

        fields 用的是界面字段名（type/periods/eff/allowNormal/allowUrgent/note），不经过界面的
        输入模型，所以文件可以表达界面表达不了的组合（例如假期带工时），取值合法性由调用方自己校验。
        """
        if not fields and "effective" in before:
            return before["row"], before["row"], before["effective"]
        model, row = self._proposed(fields, before, context=context)
        if row == before["row"] and "effective" in before:
            return model, row, before["effective"]
        return model, row, self._window_checked(before["date"], model, projection=projection)

    def _proposed(
        self,
        fields: Dict[str, Any],
        before: Dict[str, Any],
        *,
        context: CalendarNormalizationContext,
    ) -> Tuple[Optional[CalendarRow], Optional[Dict[str, Any]]]:
        row = before["row"]
        if not fields:
            return row, row
        if row is not None:
            payload = dict(row)
        else:
            payload = {"date": before["date"]}
            if "type" not in fields:
                default = self._base_engine()._default_for_date(before["date"])
                payload.update(default.to_dict())
                payload["remark"] = None
        patch = calendar_domain_fields(fields)
        require_periods_when_rest_turns_work(before["date"], row, patch)
        payload.update(patch)
        proposed = self._admin.build_work_calendar_from_payload(payload, context=context)
        return proposed, proposed.to_dict()

    @staticmethod
    def _window_checked(day: str, row: Optional[CalendarRow],
                        *, projection: CalendarProjection) -> Optional[Dict[str, Any]]:
        """保存前先把这一天的时间窗算一遍：算不出来（例如跨出 9999-12-31）就在预检和保存前拒绝，不等写库后整批回滚。

        范围预览本来就逐日算保存后的时间窗，不走这里，免得大范围预览重复计算。
        """
        if row is None:
            return None
        return effective_calendar_day(day, row, projection=projection)

    def _require_write_transaction(self) -> None:
        if not self.conn.in_transaction or not in_transaction_context(self.conn):
            raise RuntimeError("日历写入必须由外层 WorkbenchCommandService 持有写事务。")

    def apply_checked(self, action, normalized_input, checked):
        """Consume the guard's current facts in its same outer command transaction."""
        payload = normalized_input
        if action == "confirm":
            return self.confirm(payload, checked)
        if action not in ("upsert", "delete"):
            raise ValidationError("「预览变更」不能当成保存操作。", field="action")
        return self._apply_day(action, payload, checked)

    def _apply_day(self, action, payload, before):
        context = self._normalization_context()
        after, row, _ = (
            self._form_proposed(payload["fields"], before, context=context, projection=self.projection({}))
            if action == "upsert"
            else (None, None, None)
        )
        return self._write(before, after, row)

    def _form_proposed(self, fields, before, *, context, projection):
        """表单入口（单日、范围）：领域规则报的中立字段名在这里映射成界面路径。"""
        try:
            return self.proposed_state(fields, before, context=context, projection=projection)
        except ValidationError as exc:
            raise form_field_error(exc) from exc

    def _write(self, before, after, row) -> WorkbenchCommandOutcome:
        return self.write_days([(before, after, row)])[0]

    def write_days(self, changes, *, include_refs=True):
        """Apply this prepared batch; only returned new refs need a post-write read."""
        self._require_write_transaction()
        results, calendars, deleted, created = [], [], [], []
        for before, after, row in changes:
            day, ref = before["date"], before["calendar_ref"]
            changed = row != before["row"]
            results.append(WorkbenchCommandOutcome("committed" if changed else "unchanged",
                                                   {"date": day, "calendar_ref": ref}))
            if not changed:
                continue
            if after is None:
                deleted.append(day)
            else:
                calendars.append(after)
                if ref is None and include_refs:
                    created.append(day)
        repo = self._admin.repo
        if calendars:
            repo.upsert_many(calendars)
        if deleted:
            repo.delete_many(deleted)
        if calendars or deleted:
            self._engine = None
        refs = self._query.created_refs("calendar", created) if created else {}
        for outcome in results:
            if include_refs and outcome.result == "committed" and outcome.data["calendar_ref"] is None:
                outcome.data["calendar_ref"] = refs[outcome.data["date"]]
        return results

    def _preview_days(
        self,
        request: Dict[str, Any],
        expected: Optional[CalendarRangePreview] = None,
        *,
        context: CalendarNormalizationContext,
    ) -> Dict[str, Any]:
        dates = calendar_range_dates(request)
        if expected is not None and dates != expected.dates:
            raise WorkbenchCommandRejected("snapshot_stale", "命中的日期已经变了，请重新点「预览变更」。")
        states = self.range_states(request["start_date"], request["end_date"])
        projection = self.projection(states)
        periods = projection.default_periods()
        days, calendars = [], []
        for index, day in enumerate(dates):
            before = self._snapshot(day, states, projection=projection)
            if expected is not None and before != expected.days[index]["before"]:
                raise WorkbenchCommandRejected("snapshot_stale", "范围里的日历已经变了，请重新点「预览变更」。")
            if request["operation"] == "upsert":
                model, row, after_effective = self._form_proposed(
                    request["fields"], before, context=context, projection=projection
                )
            else:
                model = row = None
                after_effective = (
                    before["effective"]
                    if before["row"] is None
                    else effective_calendar_day(day, None, projection=projection)
                )
            calendars.append(model)
            days.append({"date": day, "before": before,
                         "after": {"explicit": row is not None, "row": row, "default_periods": periods,
                                   "effective": after_effective}})
        return {"request": request, "dates": dates, "days": days, "calendars": calendars}

    def preview(self, payload: Dict[str, Any]) -> CalendarRangePreview:
        """Read-only bounded preview. No placeholder rows, business writes or long lock.

        Weekday/weekend means Gregorian Mon-Fri/Sat-Sun, including configured holidays
        and overtime, exactly as the prototype. Conflicting hidden shift windows reject
        the preview instead of advertising hours that the domain would not save.
        """
        request, now = self.normalize("preview", payload), self._now()
        with self._tx.transaction():
            context = self._normalization_context()
            facts = self._preview_days(request, context=context)
        return CalendarRangePreview(
            preview_ref=uuid.uuid4().hex, created_at=now.isoformat(timespec="seconds"),
            expires_at=(now + timedelta(seconds=CALENDAR_PREVIEW_TTL_SECONDS)).isoformat(timespec="seconds"),
            request=facts["request"], dates=facts["dates"], days=facts["days"])

    def confirm(self, normalized_input: Dict[str, Any], preview: CalendarRangePreview) -> WorkbenchCommandOutcome:
        """Private confirm callback, inside the same outer write transaction and receipt.

        Revalidate TTL, exact date set and current calendar facts before
        any writes. Any later failure propagates to the owner for whole-batch rollback.
        A stale preview never silently selects fresh dates or substitutes another ref.
        """
        self._require_write_transaction()
        payload = normalized_input
        if preview.preview_ref != payload["preview_ref"]:
            raise WorkbenchCommandRejected("snapshot_stale", "这份变更清单已失效，请重新点「预览变更」。")
        now = self._now().isoformat(timespec="seconds")
        if not preview.created_at <= now < preview.expires_at:
            raise WorkbenchCommandRejected("snapshot_stale", "这份变更清单已过期或内容有变化，请重新点「预览变更」。")
        context = self._normalization_context()
        current = self._preview_days(preview.request, expected=preview, context=context)
        if current["days"] != preview.days:
            raise WorkbenchCommandRejected("snapshot_stale", "范围里的日历或命中的日期已经变了，请重新点「预览变更」。")
        results = self.write_days(
            [(item["before"], model, item["after"]["row"]) for item, model in zip(current["days"], current["calendars"])]
        )
        return WorkbenchCommandOutcome("committed" if any(item.result == "committed" for item in results) else "unchanged",
                                       {"dates": [{**item.data, "result": item.result} for item in results]})
