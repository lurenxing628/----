"""Private global calendar adapter. No HTTP routes, personal calendars or shift profiles."""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager, in_transaction_context
from core.models.calendar import OperatorCalendar, WorkCalendar
from core.models.calendar_periods import decode_periods, encode_periods, normalize_periods
from core.models.workbench_calendar import (
    CALENDAR_PREVIEW_TTL_SECONDS,
    CalendarRangePreview,
    calendar_date,
    calendar_domain_fields,
    calendar_range_dates,
    normalize_calendar_input,
)
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.scheduler.calendar.service import CalendarService
from data.repositories.workbench_calendar_query_repo import WorkbenchCalendarQueryRepository

from .calendar_summary import owned_hours

_CalendarRow = Union[WorkCalendar, OperatorCalendar, Dict[str, Any]]


def _date_key(value: Any) -> str:
    # get_connection enables SQLite DATE conversion. datetime is deliberately not a date key.
    if type(value) is date:
        return value.isoformat()
    try:
        return calendar_date(value)
    except ValidationError as exc:
        raise WorkbenchCommandRejected("constraint_conflict", "存储日历的日期无效，不能当作本地日期读取。") from exc


class _CalendarProjection(CalendarEngine):
    """Overlay raw/proposed global rows (keyed by date) on the existing engine, without SQL writes."""

    def __init__(self, rows: Mapping[str, _CalendarRow], periods=None):
        self.conn = None
        self.logger = None
        self.capture = None
        self._default_periods = normalize_periods(periods) if periods is not None else None
        self._default_periods_json = None
        self._default_period_hours = 0.0
        self._period_facts = {}
        if self._default_periods:
            self._default_periods_json = encode_periods(self._default_periods, normalized=True)
            _, self._default_period_hours = self._period_facts_for_json(
                self._default_periods_json, self._default_periods
            )
        else:
            self._default_periods = None
        self._public_calendar_rows = {}
        self._public_policy_cache = {}
        self._policy_cache = {}
        self._policy_operator_keys = {}
        self._segment_cache = {}
        self._rows = rows

    def _resolve_calendar_row(self, date_str: str, op_id: Optional[str]) -> Union[WorkCalendar, OperatorCalendar]:
        # 用到哪天才解析哪天：月合计多读的次月 1 日即使存坏了，也只让合计未知，不牵连本月。
        row = self._rows.get(date_str)
        return (
            (row if isinstance(row, (WorkCalendar, OperatorCalendar)) else WorkCalendar.from_row(row))
            if row is not None
            else self._default_for_date(date_str)
        )


def effective_calendar_day(day: str, row: Optional[_CalendarRow], periods=None,
               *, projection: Optional[_CalendarProjection] = None) -> Dict[str, Any]:
    # Date-key policy is deliberate: midnight may still belong to yesterday's shift.
    try:
        engine = projection if projection is not None else _CalendarProjection({day: row} if row is not None else {}, periods)
        policy = engine._policy_for_date(day)
    except OverflowError as exc:
        raise ValidationError(f"{day} 的工作时段超出了系统能处理的最后日期 9999-12-31，算不出这一天的工作时间。"
                              "请让这一天的班次在当天结束：单独设置过的改这一天，没设置过的改默认工作时间。",
                              field="date") from exc
    normal, urgent = policy.is_priority_allowed("normal"), policy.is_priority_allowed("urgent")
    working = policy.is_working()
    start, end = policy.work_window()
    return {"type": "work" if working else "rest", "day_type": policy.day_type,
            "is_working": working, "is_rest": not working, "hours": policy.shift_hours,
            "effective_hours": policy.shift_hours * policy.efficiency if working else 0.0,
            "efficiency": policy.efficiency, "eff": policy.efficiency * 100,
            "allowNormal": "yes" if normal else "no", "allowUrgent": "yes" if urgent else "no",
            "periods": decode_periods(policy.periods_json),
            "windows": [{"start": left.isoformat(), "end": right.isoformat()} for left, right in policy.work_windows()],
            "window_start": start.isoformat(timespec="seconds"), "window_end": end.isoformat(timespec="seconds")}


_ENGINE_DEFAULTED = ("shift_start", "shift_hours", "efficiency", "allow_normal", "allow_urgent")


def _is_blank_value(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def engine_read_row(row: Dict[str, Any], effective: Optional[Dict[str, Any]] = None,
                    *, fill_shift_end: bool = False) -> Dict[str, Any]:
    """空着的班次开始、工时、效率换成排产引擎对这一天的解释，空白备注归一为 None；没有空着的列就原样返回。"""
    blanks = [name for name in _ENGINE_DEFAULTED if _is_blank_value(row.get(name))]
    blank_end = fill_shift_end and _is_blank_value(row.get("shift_end")) and row.get("periods_json") is None
    blank_remark = isinstance(row.get("remark"), str) and not row["remark"].strip()
    if not blanks and not blank_end and not blank_remark:
        return row
    updates: Dict[str, Any] = {}
    if blanks or blank_end:
        if effective is None:
            effective = effective_calendar_day(row["date"], row)
        reading = {"shift_start": effective["window_start"][11:16],
                   "shift_hours": effective["hours"], "efficiency": effective["efficiency"],
                   "allow_normal": effective["allowNormal"], "allow_urgent": effective["allowUrgent"]}
        for name in blanks:
            updates[name] = reading[name]
        if blank_end:
            hours = effective["hours"]
            if 0 < hours <= 24 and effective.get("periods") is None and effective["window_end"][16:19] == ":00":
                updates["shift_end"] = effective["window_end"][11:16]
    if blank_remark:
        updates["remark"] = None
    return {**row, **updates} if updates else row


def is_working_row(row: Mapping[str, Any]) -> bool:
    return bool(row["shift_hours"] > 0 and (row.get("allow_normal") == "yes" or row.get("allow_urgent") == "yes"))


# 旧库升级加列时没有回填，这几列可能空着；日历引擎和日历页都按班表默认值解释它们。
_LEGACY_BLANK_COLUMNS = ("shift_start", "shift_end", "shift_hours", "efficiency", "allow_normal", "allow_urgent", "remark")


def _defaulted_blanks(day: str, row: Dict[str, Any], proposed: Dict[str, Any],
                      names, *, before_effective: Optional[Dict[str, Any]]) -> set:
    """旧行空着的班次列被保存规则补成具体值：未修改的空列补上后，这一天按引擎算出的时段、工时、效率都不变，就算推导列。

    补出的值和引擎原来的解释不一样（例如假期空着效率，引擎按 1 算、保存规则补成假期默认效率）仍算改写，照旧拒绝。
    """
    candidates = set(names) & set(_LEGACY_BLANK_COLUMNS)
    blanks = {name for name in candidates if _is_blank_value(row.get(name))}
    if not blanks:
        return set()
    filled = {**row, **{name: proposed.get(name) for name in blanks}}
    try:
        current = effective_calendar_day(day, row) if before_effective is None else before_effective
        return blanks if current == effective_calendar_day(day, filled) else set()
    except ValidationError:
        return set()


def _owned_effective_hours(days: List[Dict[str, Any]], projection: CalendarEngine) -> Optional[float]:
    """月合计按排产真正可用的时段算：跨夜尾巴和次日班次重叠的部分只算给次日一次。

    逐日的 effective_hours 绑在写入快照里，只看这一天自己的配置，不在这里改。
    次日（可能是下个月 1 日）的日历读不出来时合计记为未知，不拿可能重复的数字充数。
    """
    try:
        return sum(owned_hours(projection, date.fromisoformat(day["date"])) * day["effective"]["efficiency"]
                   for day in days if day["effective"]["is_working"])
    except ValueError:
        return None


def _month_stats(days: List[Dict[str, Any]], projection: CalendarEngine) -> Dict[str, Any]:
    """Count explicit rows separately from configured capacity and default overrides."""
    return {"work_days": sum(day["effective"]["is_working"] for day in days),
            "configured": sum(day["explicit"] for day in days),
            "configured_work_days": sum(day["explicit"] and day["effective"]["is_working"] for day in days),
            "rest_days": sum(day["effective"]["is_rest"] for day in days),
            "overrides": sum(day["explicit"] and day["is_weekend"] == day["effective"]["is_working"] for day in days),
            "weekend_rest": sum(day["is_weekend"] and day["effective"]["is_rest"] for day in days),
            "effective_hours": _owned_effective_hours(days, projection)}


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

    def range_states(self, start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
        """Merge raw rows with lifetime refs per date; caller owns one transaction for both reads.

        Tombstones detect absent -> created -> deleted ABA. An absent date has row=None
        and identity=None; a GET never invents a ref. A stored date that is not a real
        local date, or a row whose active refs are not exactly one, is a data conflict.
        """
        self._calendar._engine.clear_policy_cache()
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

    def _snapshot(self, day: str, states: Dict[str, Dict[str, Any]], default_periods=None,
                  *, projection: Optional[_CalendarProjection] = None) -> Dict[str, Any]:
        state = states.get(day, {"row": None, "identity": None, "history": []})
        identity = state["identity"]
        periods = self._calendar._engine.default_periods() if default_periods is None else default_periods
        return {"date": day, "explicit": state["row"] is not None,
                "calendar_ref": identity["ref"] if identity else None,
                "revision": identity["revision"] if identity else None,
                **state, "default_periods": periods,
                "effective": effective_calendar_day(day, state["row"], periods, projection=projection)}

    def snapshot(self, date_value: str) -> Dict[str, Any]:
        """Private full guard state, not public DTO: raw row, ref/revision and tombstones.

        No record differs from a stored row, even when both compute the same policy.
        Absent rows have no current ref/revision; historical refs remain in history.
        The HTTP owner must bind this full snapshot to its short-lived write context.
        """
        day = calendar_date(date_value)
        with self._tx.transaction():
            return self._snapshot(day, self.range_states(day, day))

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
            states = self.range_states(first.isoformat(), last.isoformat())
            periods = self._calendar._engine.default_periods()
            rows = {day: state["row"] for day, state in states.items() if state["row"] is not None}
            projection = _CalendarProjection(rows, periods)
            days = []
            for offset in range(count):
                day = first + timedelta(days=offset)
                snapshot = self._snapshot(day.isoformat(), states, periods, projection=projection)
                days.append({**snapshot, "day": day.day, "weekday": day.weekday(),
                             "is_weekend": day.weekday() >= 5, "is_today": day == now.date()})
            rows.update(self._following_row(last, days[-1]))
        cells = [None] * first.weekday() + days
        cells += [None] * (-len(cells) % 7)
        return {"year": year, "month": month, "as_of": now.isoformat(timespec="seconds"),
                "time_basis": "factory_local", "days": days, "cells": cells,
                "previous_month": self._adjacent(year, month, -1), "next_month": self._adjacent(year, month, 1),
                "default_periods": periods, "stats": _month_stats(days, projection)}

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

    def day_state(self, day: str, states: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """某一天的完整状态。states 必须来自同一次 range_states。"""
        return self._snapshot(day, states)

    def proposed_row(self, fields: Dict[str, Any], before: Dict[str, Any]) -> Optional[_CalendarRow]:
        """按领域规则算出这一天保存后的行；与界面走同一条一致性校验，不合规直接抛拒绝。

        fields 用的是界面字段名（type/hours/eff/allowNormal/allowUrgent/note），不经过界面的
        输入模型，所以文件可以表达界面表达不了的组合（例如假期带工时），取值合法性由调用方自己校验。
        """
        if not fields and "effective" in before:
            return before["row"]
        return self._window_checked(before["date"], self._proposed(fields, before))

    def effective_day(self, day: str, row: Optional[_CalendarRow]) -> Dict[str, Any]:
        """这一天按给定的行由日历引擎算出的实际安排（工时、效率、时间窗等），与日历页显示同一口径。"""
        return effective_calendar_day(day, row, self._calendar._engine.default_periods())

    def _proposed(self, fields: Dict[str, Any], before: Dict[str, Any]) -> Optional[_CalendarRow]:
        row = before["row"]
        if not fields:
            return row
        if row is not None:
            reading = engine_read_row(row, effective=before.get("effective"))
            payload = dict(reading)
            if row.get("day_type") == "holiday" and (
                row.get("efficiency") is None or isinstance(row.get("efficiency"), str) and not row["efficiency"].strip()
            ):
                # 假期空效率保留 None，交由领域层补假期默认效率并由 _defaulted_blanks 拦截静默改写。
                payload["efficiency"] = row.get("efficiency")
        else:
            reading = None
            payload = {"date": before["date"]}
            if "type" not in fields:
                default = self._calendar._engine._default_for_date(before["date"])
                payload.update(default.to_dict())
                payload["remark"] = None
        patch = calendar_domain_fields(fields)
        changed_shift = self._changed_shift_keys(reading, patch)
        if row is not None and "periods" not in patch:
            for key in ("shift_hours", "shift_start", "shift_end"):
                if key in patch and key not in changed_shift and not (key == "shift_end" and changed_shift):
                    del patch[key]
        self._settle_periods(row, payload, patch, fields, shift_patch=bool(changed_shift))
        payload.update(patch)
        derived = self._shift_window_is_derived(row, patch, changed_shift)
        if derived:
            # 工时或开工时刻改变而未明确结束时刻时，按当前开始时刻重新推算结束。
            payload["shift_end"] = None
        try:
            proposed = self._calendar._admin._build_work_calendar_from_payload(
                payload, requested_shift_hours=patch.get("shift_hours"))
        except ValidationError as exc:
            if exc.field == "可用工时":
                raise WorkbenchCommandRejected("constraint_conflict", exc.message) from exc
            raise
        self._check_proposed(before, patch, proposed.to_dict(), derived_shift_window=derived)
        return proposed

    @staticmethod
    def _changed_shift_keys(reading: Optional[Dict[str, Any]], patch: Dict[str, Any]) -> set:
        if patch.get("periods") is not None:
            return set()
        keys = {"shift_hours", "shift_start", "shift_end"} & patch.keys()
        if reading is None or not keys:
            return keys
        if reading.get("periods_json") not in (None, "[]") and "periods" in patch and patch.get("periods") is None:
            return keys
        return {key for key in keys if patch[key] != reading.get(key)}

    @staticmethod
    def _settle_periods(row: Optional[Dict[str, Any]], payload: Dict[str, Any], patch: Dict[str, Any],
                        fields: Dict[str, Any], *, shift_patch: bool) -> None:
        """补丁没给逐段时段时，决定原来的时段是保留、清空还是改回单班；多时段日只改班次列直接拒绝。"""
        if row is None:
            if shift_patch:
                payload["periods_json"] = None
            return
        if payload.get("periods_json") is None or "periods" in patch:
            return
        if fields.get("type") == "rest":
            patch["periods"] = []
        elif shift_patch and payload["periods_json"] == "[]":
            # 休息日存成空时段，没有逐段时间要保护；填了工时或班次起止就按单班保存，
            # 与没配置过的日期、旧的休息日行同一种结果。
            patch["periods"] = None
        elif shift_patch:
            raise ValidationError("这一天已按多时段设置，请修改逐段起止时间。", field="fields.periods")

    def _window_checked(self, day: str, row: Optional[_CalendarRow]) -> Optional[_CalendarRow]:
        """保存前先把这一天的时间窗算一遍：算不出来（例如跨出 9999-12-31）就在预检和保存前拒绝，不等写库后整批回滚。

        范围预览本来就逐日算保存后的时间窗，不走这里，免得大范围预览重复计算。
        """
        if row is not None:
            effective_calendar_day(day, row, self._calendar._engine.default_periods())
        return row

    @staticmethod
    def _shift_window_is_derived(row: Optional[Dict[str, Any]], patch: Dict[str, Any], changed_shift: set) -> bool:
        return "shift_end" not in patch and (
            bool({"shift_hours", "shift_start"} & changed_shift)
            or (
                row is not None
                and row.get("periods_json") not in (None, "[]")
                and "periods" in patch
                and patch.get("periods") is None
            )
        )

    @staticmethod
    def _derived_names(row: Dict[str, Any], patch: Dict[str, Any], derived_shift_window: bool) -> set:
        """跟着补丁或推算规则一起变的列，不算"没改的项被改写"。"""
        # 旧行只存开始和工时时，结束时刻按开始加工时补出，班次没变，不算改写。
        legacy_open_end = row["shift_end"] is None and row["shift_start"] is not None and row.get("periods_json") is None
        names = {"shift_end"} if derived_shift_window or legacy_open_end else set()
        if "periods" in patch:
            names.update(("periods_json", "shift_start", "shift_end", "shift_hours"))
        if "shift_start" in patch or "shift_end" in patch:
            names.add("shift_hours")
        return names

    def _check_proposed(self, before: Dict[str, Any], patch: Dict[str, Any], proposed: Dict[str, Any],
                        *, derived_shift_window: bool) -> None:
        row = before["row"]
        if row is not None:
            derived_names = self._derived_names(row, patch, derived_shift_window)
            changed = [name for name, value in row.items()
                       if name not in patch and name not in derived_names and proposed.get(name) != value]
            if changed and set(changed) - _defaulted_blanks(before["date"], row, proposed, changed,
                                                            before_effective=before.get("effective")):
                raise WorkbenchCommandRejected("constraint_conflict", "这一天没改的项会被规则改写，所以没有保存；请先核对原来的配置。")

    def _require_write_transaction(self) -> None:
        if not self.conn.in_transaction or not in_transaction_context(self.conn):
            raise RuntimeError("日历写入必须由外层 WorkbenchCommandService 持有写事务。")

    def _apply_checked(self, action, normalized_input, checked):
        """Consume the guard's current facts in its same outer command transaction."""
        payload = normalized_input
        if action == "confirm":
            return self.confirm(payload, checked)
        if action not in ("upsert", "delete"):
            raise ValidationError("「预览变更」不能当成保存操作。", field="action")
        return self._apply_day(action, payload, checked)

    def _apply_day(self, action, payload, before):
        with self._calendar._admin.normalization_operation(self._calendar._engine.default_periods):
            after = self._window_checked(payload["date"], self._proposed(payload["fields"], before)) if action == "upsert" else None
        return self._write(before, after)

    def _write(self, before, after) -> WorkbenchCommandOutcome:
        return self.write_days([(before, after)])[0]

    def write_days(self, changes, *, include_refs=True):
        """Apply this prepared batch; only returned new refs need a post-write read."""
        self._require_write_transaction()
        results, calendars, deleted, created = [], [], [], []
        for before, after in changes:
            day, ref = before["date"], before["calendar_ref"]
            row = after.to_dict() if isinstance(after, WorkCalendar) else after
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
        repo = self._calendar._admin.repo
        if calendars:
            repo.upsert_many(calendars)
        if deleted:
            repo.delete_many(deleted)
        if calendars or deleted:
            self._calendar._engine.clear_policy_cache()
        refs = self._query.created_refs("calendar", created) if created else {}
        for outcome in results:
            if include_refs and outcome.result == "committed" and outcome.data["calendar_ref"] is None:
                outcome.data["calendar_ref"] = refs[outcome.data["date"]]
        return results

    def _preview_days(self, request: Dict[str, Any], expected: Optional[CalendarRangePreview] = None) -> Dict[str, Any]:
        dates = calendar_range_dates(request)
        if expected is not None and dates != expected.dates:
            raise WorkbenchCommandRejected("snapshot_stale", "命中的日期已经变了，请重新点「预览变更」。")
        states = self.range_states(request["start_date"], request["end_date"])
        periods = self._calendar._engine.default_periods()
        days, calendars = [], []
        for index, day in enumerate(dates):
            before = self._snapshot(day, states, periods)
            if expected is not None and before != expected.days[index]["before"]:
                raise WorkbenchCommandRejected("snapshot_stale", "范围里的日历已经变了，请重新点「预览变更」。")
            model = self._proposed(request["fields"], before) if request["operation"] == "upsert" else None
            calendars.append(model)
            row = model.to_dict() if isinstance(model, WorkCalendar) else model
            days.append({"date": day, "before": before,
                         "after": {"explicit": row is not None, "row": row, "default_periods": periods, "effective": effective_calendar_day(day, model, periods)}})
        return {"request": request, "dates": dates, "days": days, "calendars": calendars}

    def preview(self, payload: Dict[str, Any]) -> CalendarRangePreview:
        """Read-only bounded preview. No placeholder rows, business writes or long lock.

        Weekday/weekend means Gregorian Mon-Fri/Sat-Sun, including configured holidays
        and overtime, exactly as the prototype. Conflicting hidden shift windows reject
        the preview instead of advertising hours that the domain would not save.
        """
        request, now = self.normalize("preview", payload), self._now()
        with self._tx.transaction(), self._calendar._admin.normalization_operation(self._calendar._engine.default_periods):
            facts = self._preview_days(request)
        facts.update(preview_ref=uuid.uuid4().hex, created_at=now.isoformat(timespec="seconds"),
                     expires_at=(now + timedelta(seconds=CALENDAR_PREVIEW_TTL_SECONDS)).isoformat(timespec="seconds"))
        return CalendarRangePreview(**facts)

    def confirm(self, normalized_input: Dict[str, Any], preview: CalendarRangePreview) -> WorkbenchCommandOutcome:
        """Private confirm callback, inside the same outer write transaction and receipt.

        Revalidate TTL, exact date set and current calendar facts before
        any writes. Any later failure propagates to the owner for whole-batch rollback.
        A stale preview never silently selects fresh dates or substitutes another ref.
        """
        self._require_write_transaction()
        payload = normalized_input
        if not isinstance(preview, CalendarRangePreview) or preview.preview_ref != payload["preview_ref"]:
            raise WorkbenchCommandRejected("snapshot_stale", "这份变更清单已失效，请重新点「预览变更」。")
        now = self._now().isoformat(timespec="seconds")
        if not preview.created_at <= now < preview.expires_at:
            raise WorkbenchCommandRejected("snapshot_stale", "这份变更清单已过期或内容有变化，请重新点「预览变更」。")
        with self._calendar._admin.normalization_operation(self._calendar._engine.default_periods):
            current = self._preview_days(preview.request, expected=preview)
        if current["days"] != preview.days:
            raise WorkbenchCommandRejected("snapshot_stale", "范围里的日历或命中的日期已经变了，请重新点「预览变更」。")
        results = self.write_days([(item["before"], model) for item, model in zip(current["days"], current["calendars"])])
        return WorkbenchCommandOutcome("committed" if any(item.result == "committed" for item in results) else "unchanged",
                                       {"dates": [{**item.data, "result": item.result} for item in results]})
